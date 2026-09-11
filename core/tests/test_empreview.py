"""
Tests for H-EMPREVIEW-01: robots compliance, review parsing, aggregation, verification.

The robots tests matter more here than anywhere else in the project. This is the first
harness whose named sources forbid automated collection, and the gate is what turns that
from an undocumented silence into a recorded `access_blocked` attempt. A regression that
quietly re-enabled fetching a disallowed path would be a compliance failure, not a bug.

The HTML fixture is trimmed from a real Comparably response captured 2026-08-31, so the
microdata shape under test is the shape the site actually serves.

    python -m core.tests.test_empreview
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.robots import Policy, RobotsGate, parse                       # noqa: E402
from harnesses.h_empreview_01 import reviews as rv                      # noqa: E402
from harnesses.h_empreview_01.source import (                           # noqa: E402
    candidate_slugs, slug_of, verify_company)

# --------------------------------------------------------------------------- robots

INDEED_ROBOTS = """
User-agent: *
Disallow: /cmp/_/
Disallow: /cmp/*/people

User-agent: GPTBot
User-agent: anthropic-ai
User-agent: ClaudeBot
Disallow: /cmp/
Disallow: /companies/

User-agent: Claude-User
User-agent: Claude-SearchBot
Disallow: /cmp/_/
"""

GLASSDOOR_ROBOTS = """
User-agent: *
Disallow: /about/contact/

User-agent: ClaudeBot
Disallow: /
"""


def test_indeed_reviews_path_is_disallowed_for_the_crawler_identity():
    """The measured, load-bearing fact: /cmp/ is where Indeed company reviews live."""
    disallow, _, matched = parse(INDEED_ROBOTS)
    policy = Policy(host="www.indeed.com", fetched=True, disallow=disallow,
                    matched_groups=matched)
    assert policy.blocks("/cmp/Kenco-Group/reviews") == "/cmp/"
    # The narrow * rules are also in the union, so the strictest policy wins overall.
    assert policy.blocks("/cmp/Kenco-Group/people")


def test_indeed_non_review_paths_remain_permitted():
    """The block is specific. Reporting it as a whole-site ban would overstate it."""
    disallow, _, matched = parse(INDEED_ROBOTS)
    policy = Policy(host="www.indeed.com", fetched=True, disallow=disallow,
                    matched_groups=matched)
    assert policy.blocks("/career-advice/pay-salary") == ""


def test_glassdoor_is_blocked_wholesale():
    disallow, _, matched = parse(GLASSDOOR_ROBOTS)
    policy = Policy(host="www.glassdoor.com", fetched=True, disallow=disallow,
                    matched_groups=matched)
    assert policy.blocks("/Reviews/Kenco-Group-Reviews-E38048.htm") == "/"


def test_union_takes_the_strictest_applicable_group():
    """A permissive `*` group must not override a restrictive agent group."""
    disallow, _, _ = parse(INDEED_ROBOTS)
    assert "/cmp/" in disallow          # from the ClaudeBot group
    assert "/cmp/_/" in disallow        # from the * group


def test_wildcard_and_anchor_matching():
    p = Policy(host="x", fetched=True,
               disallow={"/a/*/c", "/only$", "/pre"})
    assert p.blocks("/a/b/c")
    assert p.blocks("/pre-anything")
    assert p.blocks("/only") == "/only$"
    assert p.blocks("/a/b") == ""


def test_unfetchable_robots_does_not_silently_authorise_or_forbid():
    p = Policy(host="x", fetched=False, error="timeout")
    assert p.blocks("/anything") == ""


# ------------------------------------------------------------------- review parsing

# Trimmed from a real Comparably response, preserving the exact microdata shape.
FIXTURE = """
<div itemprop="aggregateRating" itemscope
     itemtype="http://schema.org/EmployerAggregateRating">
  <meta itemprop="ratingCount" content="162">
  <meta itemprop="reviewCount" content="12">
  <meta itemprop="ratingValue" content="2.4">
  <div itemprop="itemReviewed" itemscope itemtype="http://schema.org/Organization">
    <meta itemprop="name" content="Kenco Group">
    <meta itemprop="url" content="https://www.comparably.com/companies/kenco-group">
  </div>
</div>
<div class="review"><p itemprop="reviewBody">Good place.</p></div>
<div class="review"><p itemprop="reviewBody">Lots of politics at this place. Executive
leadership lacks any coherent plan and we still run the warehouse on spreadsheets that
nobody trusts.</p></div>
<div class="review"><p itemprop="reviewBody">The systems do not talk to each other so we
re-key the same order three times a day. Management knows and nothing changes.</p></div>
<div class="review"><p itemprop="reviewBody">Pay is fair and the benefits are decent for
the area, no complaints from me about how they treat people here.</p></div>
<div class="review"><p itemprop="reviewBody">Outdated software everywhere. We were still
using paper-based processes on the dock in 2024 which slowed everything down.</p></div>
<div class="review"><p itemprop="reviewBody">Great team culture and my supervisor is
genuinely supportive of career growth and development here.</p></div>
"""


def test_parses_aggregate_microdata():
    cr = rv.parse_page(FIXTURE)
    assert cr.rating_value == "2.4"
    assert cr.rating_count == "162"
    assert cr.review_count == "12"
    assert cr.declared_name == "Kenco Group"


def test_parses_review_bodies_and_filters_stubs():
    cr = rv.parse_page(FIXTURE)
    assert len(cr.reviews) == 6
    # "Good place." is below the content floor and counts to the denominator only.
    assert len(cr.usable_reviews) == 5


def test_aggregates_themes_across_reviews_not_per_review():
    cr = rv.parse_page(FIXTURE)
    findings, _ = rv.aggregate_themes(cr.usable_reviews)
    keys = {f.theme_key for f in findings}
    assert "digital_transformation_process" in keys
    dt = next(f for f in findings if f.theme_key == "digital_transformation_process")
    # Three reviewers, one finding -- never three rows.
    assert dt.review_count >= 2
    assert dt.signal_strength == "repeated_pattern"


def test_single_mention_of_one_generic_term_is_not_admitted():
    """Convention 32: an admission threshold, not a strength downgrade."""
    one = [rv.Review("We use an API for one small thing and it is fine, no other issues "
                     "worth mentioning about this employer at all.")]
    findings, below = rv.aggregate_themes(one)
    assert findings == []
    assert below


def test_employee_reviews_reach_legacy_constraint():
    """The portfolio capability this harness exists to add."""
    cr = rv.parse_page(FIXTURE)
    state, cue = rv.interpret_state([r.text for r in cr.usable_reviews])
    assert state == "legacy_constraint", (state, cue)
    assert cue


def test_sample_floor_is_a_statement_about_the_sample():
    assert rv.MIN_REVIEWS >= 5


# ------------------------------------------------------------------ identity checks

def test_verification_rejects_a_different_company():
    """Searching Comparably for "Prime Inc." returns /companies/cprime."""
    ok, score, why = verify_company("Cprime", "Prime Inc.")
    assert not ok, (score, why)


def test_verification_accepts_the_real_profile():
    ok, _, _ = verify_company("Kenco Group", "Kenco Group")
    assert ok
    ok, _, _ = verify_company("PLS Logistics Services", "PLS Logistics")
    assert ok


def test_verification_refuses_an_unnamed_profile():
    ok, _, why = verify_company("", "Kenco Group")
    assert not ok and why


def test_slug_candidates_never_guess_an_abbreviation():
    """Convention 13: full name and legal-suffix-stripped only."""
    cands = candidate_slugs("Duke Manufacturing Co.")
    assert cands == ["duke-manufacturing-co", "duke-manufacturing"]
    assert not any(len(c) <= 4 for c in cands)


def test_slug_of_extracts_the_profile_id():
    assert slug_of("https://www.comparably.com/companies/kenco-group/reviews") == "kenco-group"
    assert slug_of("https://example.com/nothing") == ""


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
    print("all empreview tests pass" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run())
