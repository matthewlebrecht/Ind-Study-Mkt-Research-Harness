"""
Regression tests for H-EXECVOICE-01 quote attribution and interpretation.

Attribution is the property that makes this evidence worth more than the job postings
already in the sheet, so it is the property most worth a test. A quote attributed to the
wrong person produces a row asserting a company said something it never said, which
convention 6a rates worse than the empty column it replaces.

    python -m core.tests.test_execvoice_quotes
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_execvoice_01.quotes import (  # noqa: E402
    classify_buyer_voice, extract_quotes, interpret_state, signal_strength)

TRADE_PRESS = """
Kenco Group has expanded its automation practice this quarter. Denis Reilly, President and
CEO of Kenco, spoke at the MODEX conference last week about the companys network.
"We were still running most of our distribution centers on spreadsheets and tribal
knowledge, and that just does not scale," said Reilly. "Over the past two years we have
deployed a new warehouse management system across eleven sites and cut order cycle time by
30 percent."
An industry analyst added that "the market for warehouse automation is growing quickly and
will continue to expand through the decade."
About Kenco: Kenco is a leading provider of integrated logistics solutions to customers.
"""


def test_extracts_attributable_quotes():
    quotes, _ = extract_quotes(TRADE_PRESS, "Denis Reilly")
    assert len(quotes) == 2, [q.text[:40] for q in quotes]
    assert all(q.attribution == "explicit" for q in quotes)


def test_third_party_quote_is_not_attributed_to_the_executive():
    """The analyst quote mentions the same theme and must not be captured."""
    quotes, rejected = extract_quotes(TRADE_PRESS, "Denis Reilly")
    assert not any("industry analyst" in q.text or "through the decade" in q.text
                   for q in quotes)
    assert any(r["reason"] == "not_attributable" for r in rejected)


def test_surname_collision_is_refused():
    """A different person sharing the surname must yield nothing at all."""
    quotes, rejected = extract_quotes(TRADE_PRESS, "Sarah Reilly")
    assert quotes == []
    assert rejected[0]["reason"] == "full_name_absent_from_page"


EPONYMOUS = ('Tom McGough is chairman. Tim Reimann leads the effort at McGough '
             'Construction. "We have invested heavily in digital transformation and '
             'process automation across every project we run," he told the group at '
             'McGough headquarters last week.')


def test_eponymous_surname_requires_explicit_attribution():
    """Found in the first committed run: a quote attributed to Tom McGough off a page
    about a different person, because "McGough" appears nearby as the COMPANY name.

    Eponymous firms are everywhere in construction and trucking, so surname proximity is
    worthless there -- every mention of the employer satisfies it.
    """
    unguarded, _ = extract_quotes(EPONYMOUS, "Tom McGough")
    assert len(unguarded) == 1 and unguarded[0].attribution == "proximity"

    guarded, rejected = extract_quotes(
        EPONYMOUS, "Tom McGough", company_tokens={"MCGOUGH", "CONSTRUCTION"})
    assert guarded == []
    assert rejected[0]["reason"] == "eponymous_surname_needs_explicit_attribution"


def test_non_eponymous_executive_still_resolves_by_proximity():
    """The guard must not fire for the ordinary case."""
    page = ('Denis Reilly, CEO of Kenco, spoke. Reilly noted the shift. "We are deploying '
            'a new warehouse management system across eleven distribution sites."')
    quotes, _ = extract_quotes(page, "Denis Reilly",
                               company_tokens={"KENCO", "GROUP"})
    assert len(quotes) == 1


# ---------------------------------------------------------------------------------------
# ATTRIBUTION SHAPES, ADDED 2026-09-01 WITH THE v1.2 FIX
#
# These exist because this suite went GREEN over a live defect. Every shape it asserted was
# a shape the code already handled; the one it never asserted -- `"...," Broderick said.`,
# name then verb following the quote, and the commonest attribution in American journalism
# -- was scored `proximity` for months. The fixtures encoded what the code did rather than
# what correct attribution scoring is, so the test and the code agreed with each other
# about the wrong thing and neither could catch the other.
#
# The matrix below asserts all four orderings explicitly, so a future regression on any one
# of them fails here rather than being found by reading rows.

QUOTE_BODY = ("We are moving our entire ERP estate to the cloud this year, and we are "
              "automating the warehouse scheduling that our planners still do by hand "
              "every single morning")


def _attribution(text: str, name: str, tokens: set | None):
    quotes, rejected = extract_quotes(text, name, company_tokens=tokens)
    if quotes:
        return quotes[0].attribution
    return "REJECTED:" + (rejected[0]["reason"] if rejected else "none")


def test_all_four_attribution_shapes_for_an_ordinary_surname():
    """The full matrix for a surname that is NOT part of the employer's name."""
    lead = "CEO Ed Broderick joined the firm in 2019. "
    toks = {"GILBANE"}
    verb_then_name = lead + f'\u201c{QUOTE_BODY},\u201d said Ed Broderick. Next.'
    name_then_verb = lead + f'\u201c{QUOTE_BODY},\u201d Broderick said. Next.'
    before_quote = lead + f'Ed Broderick said: \u201c{QUOTE_BODY}.\u201d Next.'
    bare = lead + f'Ed Broderick runs it. \u201c{QUOTE_BODY}.\u201d Next.'

    assert _attribution(verb_then_name, "Ed Broderick", toks) == "explicit"
    # THE REGRESSION THIS FILE MISSED. Was "proximity" before v1.2.
    assert _attribution(name_then_verb, "Ed Broderick", toks) == "explicit"
    assert _attribution(before_quote, "Ed Broderick", toks) == "explicit"
    assert _attribution(bare, "Ed Broderick", toks) == "proximity"


def test_eponymous_firm_separates_the_person_from_the_company():
    """The sharp case, and the one the fix could most easily have broken.

    At an eponymous firm a `proximity` quote is rejected outright, so scoring
    name-then-verb correctly is not a yield question -- it decides whether a genuinely
    attributed quote survives at all. But the same shape written about the COMPANY
    (`"...," McGough Construction said.`) must stay rejected, or the fix has simply traded
    one error for the other.
    """
    lead = "CEO Tom McGough joined the firm in 2019. "
    toks = {"MCGOUGH", "CONSTRUCTION"}
    person = lead + f'\u201c{QUOTE_BODY},\u201d McGough said. Next.'
    company = lead + f'\u201c{QUOTE_BODY},\u201d McGough Construction said. Next.'
    bare = lead + f'Tom McGough runs it. \u201c{QUOTE_BODY}.\u201d Next.'

    # Accepted now; thrown away entirely before v1.2.
    assert _attribution(person, "Tom McGough", toks) == "explicit"
    # Still refused: the company is speaking, not the person.
    assert _attribution(company, "Tom McGough", toks).startswith("REJECTED")
    # Still refused: convention 31's corollary, untouched by this fix.
    assert _attribution(bare, "Tom McGough", toks).startswith("REJECTED")


def test_name_then_verb_does_not_upgrade_a_third_party_quote():
    """The fix must not make somebody else's quote EXPLICITLY attributed to our executive.

    Scope note, because this test deliberately asserts less than it looks like it should.
    The page below still yields a `proximity` quote for Reilly off a quote the article
    attributes to Hoffman, and it did so identically before the v1.2 fix -- verified by
    running HEAD's quotes.py against this exact fixture. That is a pre-existing weakness in
    proximity attribution (an executive named earlier in the page picks up a later quote),
    NOT something this change introduced, and fixing it here would make the v1.2 re-audit
    uninterpretable by bundling two behavioural changes into one version.

    What this test does assert is the thing the fix could have broken: name-then-verb
    matching must key on OUR surname, so a quote followed by `Hoffman said.` must not be
    promoted to `explicit`. Logged for a later version:
    proximity attribution ignores an intervening explicit attribution to someone else.
    """
    page = ('Denis Reilly, CEO of Kenco, spoke at the conference. An analyst at a rival '
            'firm disagreed. “The market for warehouse automation and cloud migration '
            'will keep expanding through the decade,” Hoffman said. Next.')
    quotes, _ = extract_quotes(page, "Denis Reilly", company_tokens={"KENCO", "GROUP"})
    assert all(q.attribution != "explicit" for q in quotes),         [(q.text[:40], q.attribution) for q in quotes]


def test_company_boilerplate_is_not_articulation():
    page = ('Jane Doe, CEO. "About Acme: Acme is a leading provider of warehouse '
            'automation and supply chain technology services to customers nationwide," '
            'said Doe.')
    quotes, rejected = extract_quotes(page, "Jane Doe")
    assert quotes == []
    assert any(r["reason"] == "company_boilerplate" for r in rejected)


def test_offtopic_quote_is_rejected():
    page = ('Jane Doe, CEO of Acme, spoke Tuesday. "We are proud to sponsor the county '
            'fair again this year and to support our local community groups," said Doe.')
    quotes, rejected = extract_quotes(page, "Jane Doe")
    assert quotes == []
    assert any(r["reason"] == "no_modernization_theme" for r in rejected)


# ------------------------------------------------------------------ buyer-voice patterns

def test_buyer_voice_catches_what_seller_vocabulary_misses():
    """The founding case for BUYER_VOICE_PATTERNS.

    Vendors write "digital transformation"; operators say "spreadsheets". Both are the
    same theme and they share no token, so a seller-only vocabulary drops the buyer half.
    """
    from core import topics
    operator_phrasing = ("we were still running the whole operation on spreadsheets and "
                         "tribal knowledge")
    assert topics.classify(operator_phrasing) == {}
    assert "digital_transformation_process" in classify_buyer_voice(operator_phrasing)


def test_buyer_voice_resolves_into_existing_theme_keys_only():
    """The shared spine must not be forked -- that is the whole reason it exists."""
    from core import topics
    from harnesses.h_execvoice_01.quotes import BUYER_VOICE_PATTERNS
    unknown = set(BUYER_VOICE_PATTERNS) - set(topics.THEMES_BY_KEY)
    assert not unknown, f"buyer-voice patterns invented theme keys: {unknown}"


# ------------------------------------------------------------------------ interpretation

def test_state_prefers_the_live_programme_reading():
    """A quote naming both a past problem and a current programme is a transition."""
    state, _ = interpret_state(
        "we were on spreadsheets, so last year we deployed a new WMS across the network")
    assert state == "active_transition"


def test_state_cues():
    assert interpret_state("we are still using paper-based processes")[0] == \
        "legacy_constraint"
    assert interpret_state("our goal is a single system of record by 2027")[0] == \
        "target_state"
    assert interpret_state("the weather was pleasant at the conference")[0] == "unknown"


def test_signal_strength_ladder():
    class Q:
        def __init__(self, t):
            self.text = t
    assert signal_strength([Q("we cut cycle time by 30 percent")]) == "measured_result"
    assert signal_strength([Q("we deployed a new WMS")]) == "committed_action"
    assert signal_strength([Q("we think about automation"),
                            Q("automation matters to us")]) == "repeated_pattern"
    assert signal_strength([Q("we think about automation")]) == "weak_clue"


def _run() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  ok    {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {name}: {e}")
    print()
    print("all quote tests pass" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run())
