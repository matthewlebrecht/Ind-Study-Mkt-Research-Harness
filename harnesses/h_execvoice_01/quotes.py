"""
Quote extraction, attribution and interpretation for H-EXECVOICE-01.

WHAT COUNTS AS A BUYER ARTICULATING SOMETHING
---------------------------------------------
The evidence base holds 185 `buyer_acts` rows and zero `buyer_articulates` rows, so every
convergence/divergence claim in the write-up depends on this harness producing rows that
survive scrutiny. The bar is therefore set at the thing that is hardest to argue with: a
**directly quoted passage, attributable to a named executive of the company, that mentions
a modernization theme.**

Not a paraphrase, not a journalists characterisation, not a sentence that merely appears
near the persons name. A quotation mark delimited passage with a name attached to it. That
is what `docs/signal_taxonomy.md` credits family 15 with reliability A for -- direct
attributability -- and it is the only property of this evidence that makes it worth more
than the job postings already in the sheet.

The cost of that bar is yield, and the taxonomy already predicted it: 15b is marked
"don't-build (yield too low for this population)" because mid-size industrial executives
rarely appear on podcasts. Accepting a lower bar to raise the count would produce rows
that say a company articulated something it never said, which is worse than the empty
column it replaces.

TWO ATTRIBUTION TRAPS THIS GUARDS AGAINST
-----------------------------------------
1. **Surname collision.** Proximity of a surname to a quote is not attribution. "Smith
   said" on a page about three Smiths attributes nothing. So a quote is only attributed
   when the executives FULL name appears somewhere on the page (confirming the page is
   about that specific person) AND either an explicit attribution pattern binds the quote
   to the surname, or the surname sits inside a tight window around it.

2. **The company quoting itself.** A quote lifted from the companys own boilerplate --
   "About Acme: Acme is a leading provider of..." -- is marketing copy, not articulation.
   Boilerplate is filtered on its characteristic openings.

The vendor-published trap that `session2_priority_order.md` names is handled a level up in
the harness, where the host domain is known, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core import topics

# Quote length bounds. Below the floor a quoted fragment is a scare-quoted term
# ("the so-called 'digital journey'"), not a statement. Above the ceiling the closing
# quotation mark has almost certainly been mismatched across paragraphs.
MIN_QUOTE_CHARS = 60
MAX_QUOTE_CHARS = 900

# How far from the quote the surname may sit and still count as attribution when no
# explicit "said X" pattern is present. Roughly one sentence either side.
ATTRIBUTION_WINDOW = 220

# Straight and curly double quotes. Single quotes are deliberately excluded: apostrophes
# in ordinary prose make them unusable as delimiters.
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{40,1200})[”\"]")

# Explicit attribution: "<quote>," said Jane Doe / Jane Doe said / according to Jane Doe /
# Doe explained / Doe added / Doe told <outlet>.
ATTRIB_VERBS = (r"said|says|explained|explains|noted|notes|added|adds|told|tells|"
                r"recalled|recalls|argued|argues|observed|observes|continued|"
                r"commented|comments|put it|stated|states|according to")

# Company boilerplate openings. A press release "About" block sits inside quotation marks
# often enough to matter, and it is marketing copy rather than anything a person said.
# Page furniture that marks a quotation span as having crossed out of the article body:
# bylines with a date bullet, editors' picks and recommended-reading decks, newsletter and
# share boxes. Session 15 / O00604: a Construction Dive span ended inside the sidebar
# teaser for a different article about a different company.
PAGE_FURNITURE = re.compile(
    r"(?i)(\bBy [A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,2} [•·]|editors'? picks|recommended reading|"
    r"filed under:|keep up with the story|subscribe to the|sign up\b|add us on google|"
    r"copy link|select newsletter|free daily newsletter|you can unsubscribe|"
    r"related stories|read next|most popular|trending now)")

BOILERPLATE = re.compile(
    r"(?i)^\s*(about |founded in |headquartered in |[A-Z][\w&.,' -]{2,40} is a (leading|"
    r"premier|global|full-service|family-owned)|for more information|to learn more)")

# --------------------------------------------------------------------------------------
# Interpretation cues.
#
# These map a quote onto `organizational_state`. They are cues, not proof, and the harness
# records the matched cue in the observation so a Week 4 reviewer can disagree with the
# reading without re-fetching the page. Where nothing matches, the answer is `unknown` --
# convention 17s point that absence of a signal is not evidence of its opposite applies
# just as much to a quote as to a clean OSHA record.
# --------------------------------------------------------------------------------------
STATE_CUES = {
    "legacy_constraint": re.compile(
        r"(?i)\b(still (doing|using|on|rely|relies|relying)|manual(ly)?|spreadsheets?|"
        r"paper[- ]based|pen and paper|legacy (system|platform|software)|outdated|"
        r"antiquated|bottleneck|pain point|struggl(e|ed|ing)|inefficien|"
        r"(could|can)(no|n.t| not) |held us back|hard to |difficult to |"
        r"disconnected|siloed|silos)\b"),
    "active_transition": re.compile(
        r"(?i)\b(we(.re| are) (currently |now )?(implement|deploy|roll|migrat|build|"
        r"invest|integrat|modernis|moderniz|automat|pilot)|in the process of|"
        r"(have|has|we|weve|we.ve) (just )?(started|begun|launched|gone live|"
        r"implemented|deployed|rolled out|invested|installed|completed|adopted)|"
        r"underway|this year we|over the past (year|two years|few years))\b"),
    "target_state": re.compile(
        r"(?i)\b(we (will|plan to|intend to|aim to|want to|hope to|expect to|need to)|"
        r"our (goal|vision|ambition|plan|roadmap|objective) is|going to|"
        r"in the (next|coming) (year|years|months)|the future|eventually|"
        r"looking to|working toward)\b"),
}

# A metric in a quote is what separates a claim from a measured outcome.
METRIC_RE = re.compile(
    r"(\b\d{1,3}(?:\.\d+)?\s?(?:%|percent)\b|\$\s?\d|\b\d+\s?(?:x|times)\b|"
    r"\b(?:reduced|increased|cut|improved|saved|grew|dropped|fell|rose)\b[^.]{0,40}"
    r"\b\d)")

# Past-tense delivery, as distinct from intent.
COMMITTED_RE = re.compile(
    r"(?i)\b(implemented|deployed|rolled out|went live|installed|completed|"
    r"invested|acquired|replaced|migrated|automated|launched|adopted|standardi[sz]ed)\b")


# --------------------------------------------------------------------------------------
# Buyer-voice patterns.
#
# `core/topics.py` states the design explicitly: `Theme.patterns` holds provider-side
# phrasing, and "buyer-side patterns live per-harness". H-JOBPOST-01 already works this
# way, mapping its own signal keys into the shared spine rather than renaming anything.
#
# This exists because of a concrete miss found in testing. The single most valuable thing
# an operator says -- "we were still running our distribution centers on spreadsheets and
# that does not scale" -- matches NOTHING in the seller-side vocabulary. Vendors do not
# write the word "spreadsheets" on a service page; they write "digital transformation".
# The same claim, from the two sides of the market, shares no token. A harness that only
# matched seller phrasing would have recorded that quote as off-topic and thrown away the
# clearest legacy-constraint articulation in the sample.
#
# These are kept deliberately tight and multi-word. A single loose token here would be the
# fifth instance of convention 16, and the classification feeds directly into
# convergence/divergence analysis where a false theme match becomes a false finding.
# Everything still resolves to an existing theme key -- the spine is not forked, which is
# the whole reason the spine exists.
# --------------------------------------------------------------------------------------
BUYER_VOICE_PATTERNS = {
    "digital_transformation_process": [
        r"\bon spreadsheets?\b", r"\bin spreadsheets?\b", r"\bExcel spreadsheets?\b",
        r"\bpaper[- ]based\b", r"\bpen and paper\b", r"\bmanual (process|entry|work)",
        r"\bdouble[- ](entry|keying)\b", r"\bre[- ]key(ing)?\b",
        r"\btribal knowledge\b", r"\bwhiteboards?\b", r"\bclipboards?\b",
        r"\bby hand\b", r"\bpaper (tickets?|forms?|records?)\b",
    ],
    "erp_core_systems": [
        r"\bback[- ]office system", r"\bour (ERP|core system)",
        r"\bsystem of record\b", r"\bhomegrown system", r"\bgreen[- ]screen\b",
        r"\bAS/?400\b",
    ],
    "systems_integration": [
        r"\bdisconnected systems?\b", r"\bdata silos?\b", r"\bsiloed (data|systems?)\b",
        r"\bsystems (do|did)(n.t| not) talk\b", r"\btalk to each other\b",
        r"\bmultiple systems\b",
    ],
    "data_analytics_ai": [
        r"\breal[- ]time visibility\b", r"\bsingle (source of truth|pane of glass)\b",
        r"\bdata[- ]driven decision", r"\bwe (do|did)(n.t| not) (have|know)[^.]{0,30}data",
        r"\bgut (feel|instinct)\b",
        # 2026-09-02. The spine demoted bare "AI" to its generic tier (pattern-fix brief
        # §2): on a provider's services page "AI" alone is a slogan, and P009's whole
        # data/AI row rested on it. In ATTRIBUTED EXECUTIVE SPEECH the word is the
        # subject -- "AI is a transformative force" (Gilbane's CEO, O00364, human-audited)
        # is about AI and about nothing else. The dry run after the demotion dropped all
        # three human-audited H-TRADEPRESS-01 quotes and one H-EXECVOICE-01 quote on
        # exactly this. So the term lives here, per harness, where the text is known to
        # be a quote (brief §4 condition 4: buyer-side patterns stay per-harness).
        # Case-sensitive inside a case-insensitive table: "Ai Weiwei" and lowercase
        # prose "ai" must not read as the theme (H-JOBPOST-01 classifier rule 1).
        r"(?-i:\bAI\b)(?![-\w])",
    ],
    "warehouse_automation": [
        r"\bpick(ing)? and pack(ing)?\b", r"\bconveyor\b", r"\bpalleti[sz]",
    ],
    "transportation_fleet_systems": [
        r"\bdriver (app|tablet|shortage)\b", r"\bpaper logs?\b", r"\bELD\b",
        r"\bdispatch board\b", r"\bload boards?\b",
    ],
}

_BUYER_RX = {k: [re.compile(p, re.I) for p in v] for k, v in BUYER_VOICE_PATTERNS.items()}


def classify_buyer_voice(text: str) -> dict[str, list[str]]:
    """Seller-side themes plus buyer-voice equivalents, in the same theme vocabulary."""
    hits = dict(topics.classify(text))
    for theme_key, patterns in _BUYER_RX.items():
        matched = [m.group(0) for m in (rx.search(text) for rx in patterns) if m]
        if matched:
            hits.setdefault(theme_key, []).extend(matched)
    return hits


def classify_buyer_voice_tiered(text: str) -> tuple[dict, dict]:
    """(strong, weak): `strong` is classify_buyer_voice; `weak` is the spine's generic-tier
    refusals for themes with no strong hit. Under the 2026-09-03 corroboration-gate policy
    a quote with only a weak theme is written at low grade rather than refused."""
    strong = classify_buyer_voice(text)
    weak = {k: v for k, v in topics.classify_refusals(text).items() if k not in strong}
    return strong, weak


@dataclass
class Quote:
    text: str
    executive: str
    attribution: str          # "explicit" | "proximity"
    themes: dict = field(default_factory=dict)
    state: str = "unknown"
    state_cue: str = ""
    # Non-empty when the quote was admitted through a relaxed corroboration gate
    # (2026-09-03 policy): a short quote under the 60-char floor, or a theme carried on
    # generic-tier terms only. The attribution (who spoke) is never relaxed.
    weak_reason: str = ""

    @property
    def confidence(self) -> float:
        # Explicit attribution is the property that makes this evidence worth more than a
        # job posting, so it dominates the score. Length is a weak secondary signal that
        # the passage is a statement rather than a fragment.
        if self.weak_reason:
            return topics.LOW_GRADE_CONFIDENCE_MAX if self.attribution == "explicit" \
                else topics.LOW_GRADE_CONFIDENCE
        base = 0.8 if self.attribution == "explicit" else 0.6
        return round(min(0.9, base + (0.05 if len(self.text) > 200 else 0.0)), 2)


def surname(full_name: str) -> str:
    parts = [p for p in re.split(r"\s+", full_name.strip()) if len(p.strip(".")) > 1]
    return parts[-1] if parts else full_name.strip()


def interpret_state(text: str) -> tuple[str, str]:
    """Map a quote onto organizational_state, returning (state, the cue that matched).

    Order matters and is deliberate. A quote that describes both a past problem and a
    current programme -- "we were running on spreadsheets, so last year we deployed a WMS"
    -- is evidence of an active transition, which is the more informative and more
    defensible reading. Pure aspiration with no action is `target_state`; a problem
    statement with neither is `legacy_constraint`.
    """
    hits = {}
    for state, rx in STATE_CUES.items():
        m = rx.search(text)
        if m:
            hits[state] = m.group(0)
    for state in ("active_transition", "legacy_constraint", "target_state"):
        if state in hits:
            return state, hits[state]
    return "unknown", ""


def signal_strength(quotes: list[Quote]) -> str:
    """Strength of the claim a set of quotes on one theme supports.

    Repetition is the evidence for `repeated_pattern` (convention 19), so the count of
    distinct quotes is used rather than discarded.
    """
    if quotes and all(getattr(q, "weak_reason", "") for q in quotes):
        return "weak_clue"
    joined = " ".join(q.text for q in quotes)
    if METRIC_RE.search(joined):
        return "measured_result"
    if COMMITTED_RE.search(joined):
        return "committed_action"
    if len(quotes) >= 2:
        return "repeated_pattern"
    return "weak_clue"


def _explicit_following(rx, after: str, company_tokens: set | None, last: str) -> bool:
    """Does `after` open with an explicit attribution to this person?

    The name-then-verb branch needs one guard the verb-then-name branch does not, and that
    guard is the whole reason this is a function rather than a bare `rx.search`.

    At an eponymous firm the surname is also a token of the employer's name, so
    `"...," McGough Construction said.` matches name-then-verb -- and it is the COMPANY
    speaking, not the person. Accepting it would trade the error convention 31's corollary
    exists to catch for the one this fix removes, which is not a fix.

    So where the text between the surname and the verb carries another token of the company
    name, the match is refused. `"...," McGough said.` still passes: a bare surname after a
    quote refers to a person the article has already introduced, while a company is written
    "McGough Construction" or "the company".
    """
    m = rx.search(after or "")
    if m is None:
        return False
    gap = m.groupdict().get("gap") or ""
    if not gap or not company_tokens:
        return True
    others = {t.upper() for t in company_tokens} - {last.upper()}
    gap_tokens = {t.upper() for t in re.split(r"[^A-Za-z0-9]+", gap) if t}
    return not (gap_tokens & others)


def extract_quotes(text: str, full_name: str, min_len: int = MIN_QUOTE_CHARS,
                   company_tokens: set[str] | None = None
                   ) -> tuple[list[Quote], list[dict]]:
    """Pull quotes from page prose that are attributable to `full_name`.

    Returns (quotes, rejections). Rejections are returned rather than dropped so the run
    log can show whether the harness was being appropriately strict or silently discarding
    a whole page (convention 12).
    """
    rejected: list[dict] = []
    last = surname(full_name)

    # When the executive surname IS a token of the company name -- Tom McGough at McGough
    # Construction, the Mack family at Mack Group -- surname proximity stops being
    # evidence of anything. Every mention of the employer satisfies it. The first run
    # attributed a quote to Tom McGough off a page about a different person entirely,
    # purely because "McGough" appeared nearby as the company name.
    #
    # Eponymous firms are common in this universe (construction and trucking are full of
    # them), so this is not an edge case. Where it applies, only explicit attribution --
    # an actual "said McGough" -- counts.
    eponymous = bool(company_tokens and last.upper() in {t.upper() for t in company_tokens})

    # The full name must appear on the page at all. Without it, a surname match is a
    # coincidence rather than a reference to this executive -- the collision trap.
    name_rx = re.compile(re.escape(full_name), re.I)
    if not name_rx.search(text):
        loose = re.compile(
            r"\b" + re.escape(full_name.split()[0]) + r"\b[\w .'-]{0,24}?\b"
            + re.escape(last) + r"\b", re.I)
        if not loose.search(text):
            return [], [{"reason": "full_name_absent_from_page", "detail": full_name}]

    last_rx = re.compile(r"\b" + re.escape(last) + r"\b", re.I)

    # ATTRIBUTION FOLLOWING A QUOTE, IN BOTH ORDERINGS.
    #
    # v1.2 fix. The first version matched only VERB-then-name after a quote ("said
    # Broderick") and missed NAME-then-verb ("Broderick said") -- the commonest
    # attribution shape in American journalism. `explicit_before` already handled
    # name-then-verb, but it is anchored to the text PRECEDING the quote, so nothing
    # matched the ordinary `"...," Broderick said.`
    #
    # Two consequences, both measured 2026-09-01. A Construction Dive article whose
    # only quote is Gilbane's CEO on his firm's agentic-AI platform scored `proximity`,
    # which routed the whole article to ST-PRESSPROFILE and yielded nothing. And at an
    # eponymous firm the cost is worse than lost yield: a `proximity` quote is REJECTED
    # outright by the guard below, so `"...," McGough said.` was thrown away despite
    # being explicitly attributed. That is a correctness error, not conservatism.
    explicit_after = re.compile(
        r"^[\s,.’”\"]{0,6}(?:"
        r"(?:" + ATTRIB_VERBS + r")\s+[\w.\- ]{0,30}?\b" + re.escape(last) + r"\b"
        r"|\b" + re.escape(last) + r"\b(?P<gap>[\w,.\- ]{0,40}?)(?:" + ATTRIB_VERBS + r")"
        r")", re.I)
    # Both orderings occur and both are explicit. "Reilly said:" precedes a quote;
    # "said Reilly." follows the previous one and precedes the next, which is how a
    # multi-quote passage attributes its second and later quotes -- the common shape in
    # trade-press interviews, and the one the first version silently downgraded to
    # proximity.
    explicit_before = re.compile(
        r"(?:\b" + re.escape(last) + r"\b[\w,.\- ]{0,40}?(?:" + ATTRIB_VERBS + r")"
        r"|(?:" + ATTRIB_VERBS + r")\s+[\w.\- ]{0,30}?\b" + re.escape(last) + r"\b)"
        r"[\s,:.\-”\"]{0,6}$", re.I)

    out: list[Quote] = []
    seen: set[str] = set()
    for m in QUOTE_RE.finditer(text):
        body = re.sub(r"\s+", " ", m.group(1)).strip()
        # v1.7 (session 15, O00604): a quotation span that runs off the end of the article
        # into the page's sidebar -- an "Editors' picks" teaser, a byline, a newsletter
        # box -- is page furniture with a speaker's name attached, not a quote. The span
        # is rejected, not trimmed: whatever was inside the real quote marks cannot be
        # recovered once the closing mark came from another block.
        if PAGE_FURNITURE.search(body):
            rejected.append({"reason": "span_crosses_page_furniture",
                             "detail": body[:120]})
            continue
        weak_reason = ""
        if not (min_len <= len(body) <= MAX_QUOTE_CHARS):
            # The floor is a corroboration-strength gate (a fragment is thin evidence
            # about the right speaker); the ceiling is parse integrity. Since 2026-09-03
            # a quote between 40 chars and the floor is admitted at low grade.
            if 40 <= len(body) < min_len:
                weak_reason = f"short quote ({len(body)} chars, floor {min_len})"
            else:
                rejected.append({"reason": "length", "detail": f"{len(body)} chars"})
                continue
        if BOILERPLATE.match(body):
            rejected.append({"reason": "company_boilerplate", "detail": body[:70]})
            continue
        norm = re.sub(r"[^a-z0-9]", "", body.lower())[:120]
        if norm in seen:
            continue

        before = text[max(0, m.start() - ATTRIBUTION_WINDOW):m.start()]
        after = text[m.end():m.end() + ATTRIBUTION_WINDOW]
        if (_explicit_following(explicit_after, after, company_tokens, last)
                or explicit_before.search(before)):
            attribution = "explicit"
        elif eponymous:
            rejected.append({"reason": "eponymous_surname_needs_explicit_attribution",
                             "detail": f"{last} is also a company-name token"})
            continue
        elif last_rx.search(before[-120:]) or last_rx.search(after[:120]):
            attribution = "proximity"
        else:
            rejected.append({"reason": "not_attributable", "detail": body[:70]})
            continue

        themes, weak_themes = classify_buyer_voice_tiered(body)
        if not themes and weak_themes:
            themes = weak_themes
            weak_reason = (weak_reason + "; " if weak_reason else "") + \
                f"generic-tier theme term(s) only: {', '.join(sorted({t for v in weak_themes.values() for t in v}))}"
        if not themes:
            rejected.append({"reason": "no_modernization_theme", "detail": body[:70]})
            continue

        seen.add(norm)
        state, cue = interpret_state(body)
        out.append(Quote(text=body, executive=full_name, attribution=attribution,
                         themes=themes, state=state, state_cue=cue,
                         weak_reason=weak_reason))
    return out, rejected
