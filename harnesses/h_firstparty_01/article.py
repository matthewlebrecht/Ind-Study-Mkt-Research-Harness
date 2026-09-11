"""
Article recognition, dating and classification for H-FIRSTPARTY-01.

WHY DATING IS A FIRST-CLASS CONCERN HERE
----------------------------------------
This is the harness most exposed to the failure H-WAYBACK-01 already suffered: matching a
modernization keyword inside a dated news post and treating it as current evidence.
Convention 3 requires anything stated inside an observation to be computed from the source
snapshots own date rather than the wall clock, and convention 2 requires a reviewer to
judge a claim against the date it cites.

A press release has a real publication date and it is usually in the markup. So this
module reads it from structured metadata -- JSON-LD `datePublished`, OpenGraph
`article:published_time`, a `<time datetime=...>` element -- and never infers one from URL
text or page prose. A release the harness cannot date is recorded with an empty
`publication_date`, which is honest, rather than a guessed one, which would be worse than
no date at all because it would look checkable.

Age is then used as a filter rather than silently ignored: an announcement from 2011 is a
real historical fact but it is not evidence of current modernization posture, and mixing
the two would let the harness report a company as actively transforming on the strength of
a decade-old story.

WHY A LISTING PAGE IS NOT AN ARTICLE
------------------------------------
A newsroom index page contains every headline the company has ever published, so it
matches every theme at once and dates to nothing. Treating one as an article is how a
harness reports rich coverage while having read no content -- the shape of the
H-SELLERCONTENT-01 homepage-substitute failure. `looks_like_article` refuses them.
"""

from __future__ import annotations

import datetime as _dt
import json
import re

from core import topics

# An announcement older than this is history, not current posture. Five years is
# deliberately generous: an ERP programme announced in 2022 is plausibly still the
# companys current state, while one announced in 2016 is not evidence about today.
from core.windows import MAX_AGE_DAYS  # the project standard: five years (session 10, item 1)

# A real article carries continuous prose. A listing page carries many short headlines,
# so it can be long in total while having no paragraph of any length.
MIN_ARTICLE_CHARS = 700
MIN_LONGEST_PARAGRAPH = 180

_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

_DATE_PATTERNS = [
    # Structured markup only, in descending order of trustworthiness.
    re.compile(r'"datePublished"\s*:\s*"([^"]{8,40})"', re.I),
    re.compile(r'property=["\']article:published_time["\']\s+content=["\']([^"\']+)',
               re.I),
    re.compile(r'content=["\']([^"\']+)["\']\s+property=["\']article:published_time["\']',
               re.I),
    re.compile(r'name=["\'](?:pubdate|publish-date|date)["\']\s+content=["\']([^"\']+)',
               re.I),
    re.compile(r'<time[^>]+datetime=["\']([^"\']+)', re.I),
]


def published_date(raw_html: str) -> str:
    """ISO date from structured markup, or "" if the page does not carry one.

    Deliberately never parses prose or URL segments. A date guessed from a URL slug is a
    claim the harness cannot support, and it would be indistinguishable in the sheet from
    one the publisher actually asserted.
    """
    for rx in _DATE_PATTERNS:
        for m in rx.finditer(raw_html):
            iso = _ISO.search(m.group(1))
            if iso:
                y, mo, d = (int(x) for x in iso.groups())
                try:
                    return _dt.date(y, mo, d).isoformat()
                except ValueError:
                    continue
    # JSON-LD sometimes nests the date inside an @graph array that the flat regex misses.
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                            raw_html, re.S | re.I):
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        for node in _walk(data):
            if isinstance(node, dict):
                for field in ("datePublished", "dateCreated", "uploadDate"):
                    iso = _ISO.search(str(node.get(field) or ""))
                    if iso:
                        return "-".join(iso.groups())
    return ""


def _walk(node):
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def age_days(iso_date: str, as_of: str) -> int | None:
    """Age of a dated article relative to the runs own retrieval date.

    `as_of` is the retrieval date, not `date.today()`. Convention 3: a row that computes
    an age against the wall clock drifts against its own stored snapshot the moment it is
    read again.
    """
    if not iso_date:
        return None
    try:
        d = _dt.date.fromisoformat(iso_date)
        ref = _dt.date.fromisoformat(as_of)
    except ValueError:
        return None
    return (ref - d).days


# Wire-service index pages. These defeat the paragraph-length test because the wire pads
# each headline with a summary long enough to look like prose, so 40 observations came
# from pages titled "All Computer Software News and Press Releases from PR Newswire" --
# aggregations of unrelated companies' releases, matching themes from headlines that had
# nothing to do with the company being searched.
INDEX_TITLE_RE = re.compile(
    r"(?i)(news and press releases|all .{0,40} news |press releases from|"
    r"latest news( and)?( press)? releases|news releases \||newsroom\s*$|"
    r"press room\s*$|media center\s*$)")
INDEX_URL_RE = re.compile(
    r"(?i)(prnewswire\.com/news/[^/]+/?$|prnewswire\.com/news-releases/?$|"
    r"/news/?$|/press/?$|/newsroom/?$|/press-releases/?$|/media/?$)")


def looks_like_article(lines: list[str], url: str = "",
                       title: str = "") -> tuple[bool, str]:
    """True when block lines read as one article rather than a headline index."""
    if title and INDEX_TITLE_RE.search(title):
        return False, f"index page by title: {title[:60]!r}"
    if url and INDEX_URL_RE.search(url):
        return False, "index page by URL shape (a listing, not one release)"
    total = sum(len(x) for x in lines)
    if total < MIN_ARTICLE_CHARS:
        return False, f"only {total} chars of visible text"
    longest = max((len(x) for x in lines), default=0)
    if longest < MIN_LONGEST_PARAGRAPH:
        return False, (f"longest block is {longest} chars -- reads as a headline listing, "
                       f"not an article")
    return True, ""


def theme_is_the_subject(hits: list[str], title: str) -> bool:
    """Is this announcement actually ABOUT the theme, or did it mention the word once?

    THE MEASUREMENT THAT FORCED THIS
    --------------------------------
    Of the 248 observations the first full run produced, 163 -- two thirds -- rested on a
    single matched term, and the single terms were the generic ones: "workforce
    management" (48 rows), "integration" (26), "cybersecurity" (18), "ai" (12). A Gilbane
    earnings release saying "our integrated platform" became an announcement about systems
    integration and interoperability. That is business integration, not systems
    integration, and the row asserted something the company never announced.

    Convention 16 says a loose pattern manufactures confidence rather than adding noise,
    and at 66% of output that is not noise, it is the finding.

    The admission rule: an announcement is about a theme if it says so more than once, or
    if it says so in the headline. A single generic word buried in a long release is not an
    announcement about that theme. Deliberately an ADMISSION threshold, not just a strength
    one -- these rows should not exist at `weak_clue`, because the claim itself is unsupported.
    """
    if len({h.strip().lower() for h in hits}) >= 2:
        return True
    return bool(title and any(h.strip().lower() in title.lower() for h in hits))


# --------------------------------------------------------------------------- identity

# Ordinary English words that also serve as company names in this universe. A name that
# reduces to one of these carries no identifying power by itself, so it has to be backed
# by the full company phrase. Everything NOT in here is treated as a coined name, where a
# single token is identification.
#
# This is a list rather than a dictionary lookup on purpose: no wordlist is vendored here,
# and a list that is visibly incomplete and additive is easier to reason about than a
# heuristic that silently changes behaviour as a dependency updates. Add to it whenever a
# run surfaces a false match -- that is the same additive-only posture convention 22 takes
# to controlled vocabularies.
COMMON_WORD_NAMES = {
    "prime", "summit", "pioneer", "legacy", "liberty", "sterling", "premier", "united",
    "general", "standard", "superior", "capital", "central", "continental", "empire",
    "frontier", "guardian", "heritage", "horizon", "independent", "keystone", "landmark",
    "meridian", "monarch", "paramount", "patriot", "pinnacle", "reliable", "republic",
    "sentinel", "signature", "sovereign", "titan", "triumph", "unity", "vanguard",
    "venture", "western", "eastern", "northern", "southern", "atlantic", "pacific",
    "diamond", "eagle", "falcon", "phoenix", "apex", "alpha", "omega", "delta", "vertex",
    "crown", "regal", "royal", "elite", "select", "quality", "precision", "advance",
    "advanced", "dynamic", "integrated", "unified", "core", "peak", "summit", "crest",
}


def is_about_company(text: str, canonical_name: str, title: str = "",
                     head_chars: int = 2500) -> tuple[bool, str]:
    """Is this article actually about this company, or did it merely match its name?

    THE FAILURE THIS EXISTS FOR
    ---------------------------
    The first version required "the first two name tokens appear anywhere in the text".
    Run against Prime Inc. -- whose name reduces to the single token PRIME once the legal
    suffix is stripped -- it accepted, as first-party evidence about a Missouri trucking
    firm, press releases about Digital Prime Technologies (a fintech), Prime Data Centers,
    Primech (Singapore facility services) and Prime Electric. Ten of thirteen observations
    for that company were about somebody else, all graded A, all `buyer_articulates`.

    That is convention 11 -- SOUTHWESTERN EXPRESS scoring highly against WESTERN EXPRESS --
    reappearing in a harness that does not go through `core/resolution.py` because it is
    not resolving against a candidate list. The lesson transfers anyway: a common token is
    not an identity.

    So the test scales with how distinctive the name is:

      * two or more distinctive tokens -> every one of them must appear
      * one or zero -> the name must appear WITH its legal form ("Prime Inc"), because a
        bare common word cannot identify anybody

    and in both cases the match must fall near the top of the document. A company
    mentioned once in the twelfth paragraph is not the subject of the article.
    """
    from core.resolution import WEAK_TOKENS, strip_legal_suffix, tokens

    head = f"{title} {text[:head_chars]}".lower()
    distinctive = [t for t in tokens(canonical_name) if t not in WEAK_TOKENS]

    if len(distinctive) >= 2:
        missing = [t for t in distinctive if t.lower() not in head]
        if missing:
            return False, f"distinctive token(s) {missing} absent near the top"
        return True, ""

    # One distinctive token or none. What matters now is whether that token is a word the
    # language already uses.
    #
    # MIDMARK, KENCO, RYCON and CLYDE are coined names: seeing one is identification, and
    # demanding the full registered phrase would throw away real coverage, since a press
    # release says "Midmark" far more often than "Midmark Corporation". PRIME is an
    # ordinary English adjective, so seeing it identifies nothing -- it matched Prime Data
    # Centers, Prime Electric and Digital Prime Technologies.
    #
    # So a coined token stands alone; a dictionary word must be backed by the full company
    # phrase.
    token = (distinctive or [""])[0].lower()
    if token and token not in COMMON_WORD_NAMES:
        if re.search(rf"\b{re.escape(token)}\b", head):
            return True, ""
        return False, f"distinctive token {token.upper()!r} absent near the top"

    words = [w for w in re.split(r"[^A-Za-z0-9]+", canonical_name) if w]
    if words:
        phrase = r"[\s,.\-]*".join(re.escape(w.lower()) for w in words)
        if re.search(rf"\b{phrase}\b", head):
            return True, ""
    bare = strip_legal_suffix(canonical_name).strip()
    return False, (f"{token.upper()!r} is an ordinary English word, so it cannot identify "
                   f"a company on its own, and the full phrase {canonical_name!r} does not "
                   f"appear near the top of the document (a bare '{bare}' match is not an "
                   f"identity -- convention 11)")


def is_announcement_url(url: str) -> bool:
    """Does this URL look like a dated announcement rather than a standing page?

    Added after the Midmark leadership-team page was accepted as an `own_newsroom`
    article: executive bios are long continuous paragraphs, so `looks_like_article`
    passes them, and the page then contributed two themes as though the company had
    announced something. A standing About or Leadership page is not an announcement no
    matter how much prose it carries.
    """
    return bool(re.search(
        r"(?i)(/news/|/press/|/press-releases?/|/newsroom/|/blog/|/media/|/article/|"
        r"/stories/|/insights?/|/announcements?/|/20\d\d/|news-releases?|press-release)",
        url))


def classify_announcement(text: str) -> dict[str, list[str]]:
    """Themes present in an announcement, in the shared spine vocabulary.

    Uses `core/topics.py` unmodified. A press release is written in the same register as
    vendor marketing -- companies announce "digital transformation initiatives", they do
    not write "we were on spreadsheets" -- so the buyer-voice patterns H-EXECVOICE-01 needs
    for interview speech are not needed here, and adding them would only widen the surface
    for a false match.
    """
    return topics.classify(text)


# ---------------------------------------------------------------------------- reading

STATE_CUES = {
    "active_transition": re.compile(
        r"(?i)\b(has (implemented|deployed|completed|launched|opened|installed|"
        r"selected|partnered)|announced the (completion|launch|opening|deployment)|"
        r"went live|is (implementing|deploying|rolling out|migrating|investing)|"
        r"has invested|breaks? ground|expansion of)\b"),
    "target_state": re.compile(
        r"(?i)\b(will (implement|deploy|open|invest|launch|begin)|plans to|"
        r"is set to|expects to|by 20\d\d|over the next (year|two years|three years|"
        r"five years)|roadmap)\b"),
}


def interpret_state(text: str) -> tuple[str, str]:
    """Map an announcement onto organizational_state.

    `legacy_constraint` is deliberately unreachable from this source. A company press
    release does not announce its own obsolescence, so a harness that could emit
    `legacy_constraint` here would only be doing so from a misread. Convention 17 in a
    different costume: the absence of a stated constraint in promotional copy is not
    evidence that none exists, and the honest values available are transition, target, or
    unknown.
    """
    for state in ("active_transition", "target_state"):
        m = STATE_CUES[state].search(text)
        if m:
            return state, m.group(0)
    return "unknown", ""
