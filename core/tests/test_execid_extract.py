"""
Regression tests for H-EXECID-01 name/title extraction.

Every case in `test_rejects_false_positives_found_in_calibration` is a real record this
extractor produced against a real page before being hardened. They are kept as tests
rather than as fixed code because convention 16 records loose matching as the projects
recurring failure -- it has now landed five times -- and the only durable defence is a
test that fails when a future widening reintroduces one.

    python -m pytest core/tests/test_execid_extract.py -q
    python -m core.tests.test_execid_extract          # no pytest required
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_execid_01.extract import (  # noqa: E402
    extract, html_lines, looks_like_name, looks_like_title, normalize_title)


# --------------------------------------------------------------------------- rejections

FALSE_POSITIVES = [
    # (candidate name, the page it came from, what it actually was)
    ("How We", "kencogroup.com/about", "heading fragment of 'How We Work'"),
    ("Become An", "ryconinc.com/about", "call to action 'Become An Employee-Owner'"),
    ("Corporate Governance Guidelines", "merit.com/investors/corporate-governance",
     "a PDF link on a governance page, titled from 'Code of Ethics for CEO'"),
    ("Our Team", "generic", "section heading"),
    ("Duke Manufacturing", "dukemfg.com", "the company itself, not a person"),
]


def test_rejects_false_positives_found_in_calibration():
    for name, page, what in FALSE_POSITIVES:
        assert not looks_like_name(name), f"{name!r} from {page} is {what}"


def test_accepts_real_names():
    for name in ["Jon Wells", "Kevin T. Montez", "Molly McShane", "Nicole Mouskondis",
                 "Thomas Schwieterman", "Jean-Luc Picard", "O'Brien Smith",
                 "Rob Sackett", "Cono M. Passione"]:
        assert looks_like_name(name), name


def test_company_name_is_not_a_person():
    # A "name" made only of the companys own tokens is the company.
    assert not looks_like_name("Duke Manufacturing", {"DUKE", "MANUFACTURING"})
    # But a real person who shares a token with the company still resolves.
    assert looks_like_name("Molly McShane", {"MCSHANE", "COMPANIES"})


def test_document_titles_are_not_job_titles():
    for line in ["Code of Ethics for CEO & Senior Officers", "Audit Committee Charter",
                 "Corporate Governance Guidelines", "Compensation Committee Charter"]:
        assert not looks_like_title(line), line


def test_employee_owner_is_not_a_title():
    assert not looks_like_title("Employee-Owner")


def test_prose_about_an_executive_is_not_a_title():
    assert not looks_like_title(
        "Jon Wells is the President and CEO of Midmark Corporation.")


# ----------------------------------------------------------------------- normalization

def test_primary_titles_normalize_to_the_specified_filter():
    """The filter session2_priority_order.md specifies: CEO/COO/CIO-CTO/VP Ops/SC/Mfg."""
    cases = {
        "Chief Executive Officer": ("ceo", "primary"),
        "President and CEO": ("ceo", "primary"),
        "Chief Operating Officer": ("coo", "primary"),
        "Chief Information Officer": ("cio_cto", "primary"),
        "Chief Technology Officer": ("cio_cto", "primary"),
        "Vice President of Operations": ("vp_operations", "primary"),
        "Vice President - Field Operations": ("vp_operations", "primary"),
        "Director of Nashville Operations": ("vp_operations", "primary"),
        "SVP, Supply Chain": ("vp_supply_chain", "primary"),
        "VP Manufacturing Engineering": ("vp_manufacturing", "primary"),
        "Chief Financial Officer": ("cfo", "secondary"),
        "Chief People Officer": ("other_chief", "secondary"),
    }
    for raw, expected in cases.items():
        assert normalize_title(raw) == expected, f"{raw} -> {normalize_title(raw)}"


def test_unmatched_title_is_never_promoted():
    key, relevance = normalize_title("Master Carpenter")
    assert key == "other" and relevance == "excluded"


# ------------------------------------------------------------------------- page layouts

MIDMARK_SHAPE = """
<h2>Our Leadership Team</h2>
<div><p>Jon Wells</p><p>President and CEO</p>
<p>Jon Wells is the President and CEO of Midmark Corporation, a leader in care.</p></div>
<div><p>Rob Sackett</p><p>Chief Operations Officer</p>
<p>Rob Sackett is the Chief Operations Officer for Midmark Corporation.</p></div>
"""

JOINED_SHAPE = """
<ul><li>Jane Doe, Chief Operating Officer</li>
<li>Sam Patel - Vice President of Supply Chain</li></ul>
"""


def test_name_then_title_layout():
    ex = extract(html_lines(MIDMARK_SHAPE), {"MIDMARK"})
    assert [p.full_name for p in ex.people] == ["Jon Wells", "Rob Sackett"]
    assert ex.people[0].title_normalized == "ceo"
    assert ex.people[1].role_relevance == "primary"


def test_joined_layout():
    ex = extract(html_lines(JOINED_SHAPE), set())
    assert [(p.full_name, p.title_normalized) for p in ex.people] == [
        ("Jane Doe", "coo"), ("Sam Patel", "vp_supply_chain")]


def test_a_person_is_not_recorded_twice():
    ex = extract(html_lines(MIDMARK_SHAPE + MIDMARK_SHAPE), {"MIDMARK"})
    assert len(ex.people) == 2
    assert any(r["reason"] == "duplicate_person" for r in ex.rejected)


def test_names_without_titles_yield_nothing():
    """A page listing names with no titles must produce no records at all."""
    ex = extract(html_lines("<ul><li>Jon Wells</li><li>Rob Sackett</li></ul>"), set())
    assert ex.people == []
    assert all(r["reason"] == "name_without_adjacent_title" for r in ex.rejected)


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
    print("all extraction tests pass" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run())
