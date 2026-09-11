"""
Review parsing, aggregation and interpretation for H-EMPREVIEW-01.

AGGREGATE ONLY, AND THE TAXONOMY SAYS WHY
-----------------------------------------
`docs/signal_taxonomy.md` 4a rates a Glassdoor-style review **C on its own and B in
aggregate across many reviews**, and adds the design instruction directly: "design it as a
theme-extraction-over-N-reviews harness, not a single-review extractor, or it will sit at C
forever."

So nothing here emits a row per review. One employee saying the ERP is a mess is an
anecdote; five saying it across three years is a description of the company. Every
observation this harness produces is a count over a sample, the sample size travels with
the claim, and the sample floor is enforced before any theme is even considered.

WHAT THIS HARNESS UNIQUELY CONTRIBUTES
--------------------------------------
It is the only instrument in the portfolio that can produce `legacy_constraint` at scale.

H-FIRSTPARTY-01 structurally cannot: a company press release does not announce its own
obsolescence, which is recorded as a known limitation in that harness's manifest.
H-EXECVOICE-01 can in principle, but yields 8 observations across the whole universe.
Employee reviews are the one source where the people using the systems describe them
without a communications department in between. Convention 21a is the reason that matters:
the buyer-side gap analysis is currently leaning on announcement data, and announcement
data is structurally incapable of reporting a constraint.

CLASSIFICATION REUSES THE BUYER-VOICE PATTERNS
----------------------------------------------
Employees write like operators, not like vendors -- "we still do it in spreadsheets", "the
systems don't talk to each other". That is exactly the vocabulary
`h_execvoice_01.quotes.classify_buyer_voice` was built for, so it is imported rather than
forked. Convention: the shared theme spine is not duplicated per harness, and a second copy
of these patterns would drift from the first.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

from core import topics
from harnesses.h_execvoice_01.quotes import classify_buyer_voice

# Below this many reviews, an aggregate claim is not supportable and the taxonomy's B
# grade is not earned. A company with three reviews gets `not_covered` for insufficient
# sample -- which is a statement about the sample, not about the company, and must not be
# recorded as an absence of employee concern.
MIN_REVIEWS = 5

# A theme must appear in at least this many distinct reviews to be admitted, unless a
# single review carries several distinct matched terms. Convention 32: an unsupported claim
# gets an admission threshold, not a strength downgrade. One employee using one generic
# word is not evidence of a company-wide pattern at any strength.
MIN_REVIEWS_PER_THEME = 2
MIN_TERMS_IF_SINGLE_REVIEW = 2

# Reviews shorter than this are ratings-with-a-word ("Good place to work") and carry no
# extractable content. Counted toward the sample denominator, never toward a theme.
MIN_REVIEW_CHARS = 40


@dataclass
class Review:
    text: str

    @property
    def usable(self) -> bool:
        return len(self.text) >= MIN_REVIEW_CHARS


@dataclass
class CompanyReviews:
    """One company's review page, parsed."""

    reviews: list = field(default_factory=list)
    rating_value: str = ""
    rating_count: str = ""
    review_count: str = ""
    declared_name: str = ""

    @property
    def usable_reviews(self) -> list:
        return [r for r in self.reviews if r.usable]


# --------------------------------------------------------------------------- parsing

_MICRO = r'itemprop="{prop}"\s+content="([^"]*)"'


def _micro(body: str, prop: str) -> str:
    m = re.search(_MICRO.format(prop=prop), body)
    return m.group(1).strip() if m else ""


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_page(body: str) -> CompanyReviews:
    """Parse a Comparably company-reviews page.

    Reads schema.org microdata rather than presentation markup. `reviewBody` and
    `EmployerAggregateRating` are a published contract the site maintains for search
    engines, so they survive redesigns that would break a CSS-selector scrape -- the same
    reasoning that made H-FIRSTPARTY-01 date articles from structured markup only.
    """
    out = CompanyReviews()
    out.rating_value = _micro(body, "ratingValue")
    out.rating_count = _micro(body, "ratingCount")
    out.review_count = _micro(body, "reviewCount")

    # The organisation name inside the aggregate-rating block is the page's own statement
    # of which company it is about, and is what entity resolution scores against.
    m = re.search(r'itemtype="[^"]*schema\.org/Organization"[^>]*>\s*'
                  r'<meta\s+itemprop="name"\s+content="([^"]*)"', body)
    if not m:
        m = re.search(r'<meta itemprop="name" content="([^"]*)"[^>]*>\s*'
                      r'<meta itemprop="url" content="[^"]*comparably', body)
    out.declared_name = m.group(1).strip() if m else ""

    for frag in re.findall(r'itemprop="reviewBody"[^>]*>(.*?)</', body, re.S):
        text = _text(frag)
        if text:
            out.reviews.append(Review(text=text))
    return out


# -------------------------------------------------------------------- interpretation

# Employee-voice cues for organizational_state. Framed from the inside: an employee does
# not say "we are undergoing a digital transformation", they say the tools are old or that
# something new got rolled out.
STATE_CUES = {
    "legacy_constraint": re.compile(
        r"(?i)\b(outdated|antiquated|ancient|obsolete|old(er)? (system|software|"
        r"technology|equipment)|still (use|using|on|doing)|manual(ly)?|spreadsheets?|"
        r"paper[- ]?work|by hand|double[- ](entry|work)|no (real[- ]time |proper |good )?"
        r"(system|software|tools?)|lack of (technology|systems?|tools?)|"
        r"clunky|slow system|crash(es|ing)?|broken|held back|behind the times|"
        r"stuck in the|dark ages|do(n.t| not) talk to each other|siloed)\b"),
    "active_transition": re.compile(
        r"(?i)\b(new (system|software|erp|wms|tms|platform|technology)|"
        r"rolling out|rolled out|implement(ed|ing)|upgrad(e|ed|ing)|"
        r"transition(ing)? to|migrat(ed|ing)|just (got|started using)|"
        r"recently (added|adopted|launched)|investing in (technology|automation))\b"),
}


def interpret_state(texts: list[str]) -> tuple[str, str]:
    """Map a set of reviews onto organizational_state, returning (state, matched cue).

    `legacy_constraint` wins ties here, which is the opposite of the precedence
    H-EXECVOICE-01 uses on executive quotes, and the asymmetry is deliberate. An executive
    describing an old system alongside a new programme is describing a transition they are
    leading. An employee describing both is usually describing a rollout that has not
    reached them -- the constraint is the lived condition and the transition is the thing
    being promised. The count of reviews behind each reading travels in the observation, so
    a reviewer can disagree with this ordering without re-fetching.
    """
    hits: dict[str, str] = {}
    joined = " || ".join(texts)
    for state, rx in STATE_CUES.items():
        m = rx.search(joined)
        if m:
            hits[state] = m.group(0)
    for state in ("legacy_constraint", "active_transition"):
        if state in hits:
            return state, hits[state]
    return "unknown", ""


@dataclass
class ThemeFinding:
    theme_key: str
    review_count: int
    terms: list
    excerpts: list

    @property
    def admitted(self) -> bool:
        return (self.review_count >= MIN_REVIEWS_PER_THEME
                or len(set(self.terms)) >= MIN_TERMS_IF_SINGLE_REVIEW)

    @property
    def signal_strength(self) -> str:
        # Repetition across independent reviewers is the evidence here (convention 19),
        # so strength counts reviewers, not words.
        if self.review_count >= 4:
            return "repeated_pattern"
        if self.review_count >= MIN_REVIEWS_PER_THEME:
            return "repeated_pattern"
        return "weak_clue"


def aggregate_themes(reviews: list) -> tuple[list, dict]:
    """Classify each review, then aggregate hits per theme across the sample."""
    per_theme: dict[str, ThemeFinding] = {}
    for r in reviews:
        for theme_key, terms in classify_buyer_voice(r.text).items():
            f = per_theme.setdefault(
                theme_key, ThemeFinding(theme_key, 0, [], []))
            f.review_count += 1
            f.terms.extend(terms)
            if len(f.excerpts) < 3:
                f.excerpts.append(r.text[:240])
    # Since 2026-09-02 the spine itself declines a lone generic term ("API" once, and
    # nothing else) before this harness ever sees it. Convention 7 still applies: the
    # decline is counted here so a reviewer can see "N reviews mentioned integration and
    # none carried a specific term", rather than the mention vanishing. It is reported
    # under `rejected`, never fed into `per_theme` -- repetition across reviewers is this
    # harness's admission rule for what the spine ADMITTED per text, not a way around
    # what the spine declined.
    spine_refused: dict[str, int] = {}
    for r in reviews:
        for theme_key in topics.classify_refusals(r.text):
            spine_refused[theme_key] = spine_refused.get(theme_key, 0) + 1
    admitted = [f for f in per_theme.values() if f.admitted]
    rejected = {k: v.review_count for k, v in per_theme.items() if not v.admitted}
    for k, n in spine_refused.items():
        if k not in per_theme:
            rejected[k] = n
    return sorted(admitted, key=lambda f: -f.review_count), rejected


def aggregate_themes_tiered(reviews: list) -> tuple[list, list, dict]:
    """(admitted, low_grade, rejected_counts). `low_grade` are the ThemeFindings below
    this harness's admission threshold (one review, one term) -- a corroboration-strength
    refusal that the 2026-09-03 policy writes at low grade instead. Spine-level generic-
    only refusals stay in `rejected_counts` only: there is no ThemeFinding to write."""
    per_theme: dict[str, ThemeFinding] = {}
    for r in reviews:
        for theme_key, terms in classify_buyer_voice(r.text).items():
            f = per_theme.setdefault(theme_key, ThemeFinding(theme_key, 0, [], []))
            f.review_count += 1
            f.terms.extend(terms)
            if len(f.excerpts) < 3:
                f.excerpts.append(r.text[:240])
    admitted, rejected = aggregate_themes(reviews)
    low = [f for f in per_theme.values() if not f.admitted]
    return admitted, sorted(low, key=lambda f: -f.review_count), rejected
