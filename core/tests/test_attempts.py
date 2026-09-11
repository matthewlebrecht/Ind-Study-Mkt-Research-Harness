#!/usr/bin/env python3
"""
Assert the Attempts completeness contract against a harness that deliberately misbehaves.

`repo_structure_spec.md` §3: the completeness requirement is the difference between a rule
in a document and a property of the system. Stated as a rule it fails the first time
someone adds a harness with an early `continue` in a loop. So the test here *is* that
harness -- it declares eight companies and quietly skips three -- and the assertion is
that the run closes them out as `not_covered` anyway.

Runs against a throwaway copy of the workbook. Nothing here touches the real one.

    python core/tests/test_attempts.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.db import MarketIntelDB, WORKBOOK_PATH  # noqa: E402
from core.attempts import AttemptError  # noqa: E402

PASS = FAIL = 0


def check(label: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def expect_error(label: str, fn) -> None:
    try:
        fn()
    except AttemptError:
        check(label, True)
    else:
        check(label, False)


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(WORKBOOK_PATH, tmp)
    db = MarketIntelDB(tmp)

    pilots = [c["company_id"] for c in db.companies()][:8]
    scope = [(cid, "test_signal") for cid in pilots]

    test_access_classification()
    print("1. a harness that skips companies still produces a complete attempt set")
    run = db.open_run(harness_id="H-TEST-01", harness_name="Completeness probe",
                      version="v0.1", primary_family="3_workforce_org_exhaust",
                      scope=scope, commit=False)
    # The misbehaving harness: attempts five of eight and `continue`s past the rest.
    run.attempt(pilots[0], "test_signal", outcome="covered", records_written=2)
    run.attempt(pilots[1], "test_signal", outcome="absent_confirmed")
    run.attempt(pilots[2], "test_signal", outcome="partial", failure_stage="extraction",
                failure_category="parse_failure", fix_class="code_change",
                records_written=1)
    run.attempt(pilots[3], "test_signal", outcome="not_covered", failure_stage="fetch",
                failure_category="js_rendered_unreachable", fix_class="code_change")
    run.attempt(pilots[4], "test_signal", outcome="covered", records_reconciled=3)
    summary = run.close()

    check("all 8 declared pairs produced a row", summary["attempts_total"] == 8)
    check("3 skipped pairs were closed out", len(summary["missing_closed_out"]) == 3)
    check("skipped pairs became not_covered", summary["attempts_not_covered"] == 4)
    check("covered counted", summary["attempts_covered"] == 2)
    check("absent_confirmed counted separately", summary["attempts_absent_confirmed"] == 1)
    check("partial counted", summary["attempts_partial"] == 1)

    print("\n2. coverage_rate counts absent_confirmed as coverage")
    # covered(2) + absent_confirmed(1) + partial(1) = 4 of 8
    check("coverage_rate = 0.5", summary["coverage_rate"] == 0.5)

    print("\n3. idempotent re-runs are not punished (spec §11 C9)")
    run2 = db.open_run(harness_id="H-TEST-01", harness_name="Completeness probe",
                       version="v0.1", primary_family="3_workforce_org_exhaust",
                       scope=[(pilots[0], "test_signal")], commit=False)
    run2.attempt(pilots[0], "test_signal", outcome="covered", records_written=0,
                 records_reconciled=27)
    s2 = run2.close()
    check("a run that writes 0 and reconciles 27 is fully covered",
          s2["coverage_rate"] == 1.0 and s2["attempts_covered"] == 1)

    print("\n4. the contract refuses rows that would corrupt coverage math")
    run3 = db.open_run(harness_id="H-TEST-01", harness_name="probe", version="v0.1",
                       primary_family="3_workforce_org_exhaust", scope=[], commit=False)
    expect_error("not_covered without a stage/category is rejected",
                 lambda: run3.attempt(pilots[0], "s", outcome="not_covered"))
    expect_error("covered with no records is rejected",
                 lambda: run3.attempt(pilots[1], "s", outcome="covered"))
    expect_error("an unknown outcome is rejected",
                 lambda: run3.attempt(pilots[2], "s", outcome="probably_fine"))
    expect_error("an off-vocabulary failure_category is rejected",
                 lambda: run3.attempt(pilots[3], "s", outcome="not_covered",
                                      failure_stage="fetch",
                                      failure_category="gremlins"))
    expect_error("an incidental row that is not 'covered' is rejected",
                 lambda: run3.attempt(pilots[4], "s", outcome="not_covered",
                                      failure_stage="fetch",
                                      failure_category="access_blocked",
                                      scope="incidental"))
    run3.attempt(pilots[5], "s", outcome="absent_confirmed")
    expect_error("a duplicate (company, signal) in one run is rejected",
                 lambda: run3.attempt(pilots[5], "s", outcome="absent_confirmed"))

    print("\n5. incidental rows stay out of coverage math (spec §3.1)")
    run4 = db.open_run(harness_id="H-TEST-01", harness_name="probe", version="v0.1",
                       primary_family="3_workforce_org_exhaust",
                       scope=[(pilots[0], "declared")], commit=False)
    run4.attempt(pilots[0], "declared", outcome="covered", records_written=1)
    run4.attempt(pilots[0], "stumbled_into", outcome="covered", records_written=1,
                 scope="incidental", evidence_family="5_technology_stack_traces")
    s4 = run4.close()
    check("denominator counts only the declared pair", s4["attempts_total"] == 1)
    check("both rows still exist", len(run4.attempts) == 2)

    print("\n6. known_issues is derived, not hand-written (spec §10 C6)")
    run5 = db.open_run(harness_id="H-TEST-01", harness_name="probe", version="v0.1",
                       primary_family="3_workforce_org_exhaust",
                       scope=[(c, "s") for c in pilots[:4]], commit=False)
    for cid in pilots[:3]:
        run5.attempt(cid, "s", outcome="not_covered", failure_stage="fetch",
                     failure_category="js_rendered_unreachable", fix_class="code_change")
    run5.attempt(pilots[3], "s", outcome="covered", records_written=1)
    issues = run5.derived_known_issues()
    check("derived string names the category and count",
          "3 js_rendered_unreachable" in issues)
    check("covered companies are not listed as issues", pilots[3] not in issues)

    print("\n7. committing writes rows and leaves the rest of the workbook alone")
    before_obs = db.wb["Observations"].max_row
    before_att = db.wb["Attempts"].max_row
    run6 = db.open_run(harness_id="H-TEST-01", harness_name="probe", version="v0.1",
                       primary_family="3_workforce_org_exhaust",
                       scope=[(pilots[0], "s")], commit=True)
    run6.attempt(pilots[0], "s", outcome="absent_confirmed")
    s6 = run6.close()
    check("one attempt row appended",
          db.wb["Attempts"].max_row == before_att + 1)
    check("attempt_id is {run_id}-{seq}",
          db.wb["Attempts"].cell(before_att + 1, 1).value == f"{s6['run_id']}-00001")
    check("Observations untouched", db.wb["Observations"].max_row == before_obs)
    hr = db.wb["Harness_Runs"]
    headers = [hr.cell(1, c).value for c in range(1, hr.max_column + 1)]
    last = {h: hr.cell(hr.max_row, i + 1).value for i, h in enumerate(headers)}
    check("run row carries the rollups", last["attempts_total"] == 1
          and last["coverage_rate"] == 1.0)
    check("run row id matches the attempts", last["harness_run_id"] == s6["run_id"])

    print(f"\n{PASS} checks passed, {FAIL} failed. (worked on {tmp})")
    return 1 if FAIL else 0



def test_access_classification():
    """The three states `access_blocked` was holding (Signal Advisor, 2026-09-01).

    The discriminations that matter are the ones where the naive read is wrong, so those
    are what is asserted: 403 is ambiguous and 429 is not; a row naming several sources
    resolves to the BINDING constraint without discarding the others; and an explicit
    token beats any inference.
    """
    from core.attempts import (access_classes_present, access_detail,
                               classify_access)

    print("6. access failures split into source refusal / rate limit / egress block")

    # 403 is returned BOTH by a policy refusal and by an edge rate limiter -- the
    # Comparably case that motivated the split -- so a bare one classifies to nothing and
    # gets reported. Defaulting it would inflate the one count meant to be citable.
    check("a bare 403 is NOT classified -- it is ambiguous by construction",
          classify_access("homepage unreachable (status 403, )") is None)
    # 429 has exactly one meaning, so it is safe where 403 is not.
    check("a word-bounded 429 is a rate limit even with no other wording",
          classify_access("HTTPError: 429 from CDX") == "rate_limited")
    check("429 inside a longer number is not a rate limit -- convention 16",
          classify_access("docket 1429 filed 2020") is None)

    check("a published robots.txt policy is the source's own decision",
          classify_access("robots.txt on www.linkedin.com disallows /")
          == "source_refusal")
    check("a filter interstitial is OUR egress, never a claim about the source",
          classify_access("Web Page Blocked! attack id 8812") == "egress_blocked")
    check("a trust-store gap is ours too -- convention 38, the USASpending case",
          classify_access("[SSL: CERTIFICATE_VERIFY_FAILED] no local issuer")
          == "egress_blocked")

    # The family-4 shape: one row, three sources, different postures. Pace better and
    # comparably may answer; glassdoor and indeed never will, so the row stays
    # access-bounded either way.
    mixed = ("comparably.com returned HTTP 403 (edge rate limiting); glassdoor.com and "
             "indeed.com are both disallowed by robots.txt for this crawler identity")
    check("a mixed row resolves to the binding constraint, not the recoverable one",
          classify_access(mixed) == "source_refusal")
    check("and the co-occurring rate limit is RETAINED, not discarded (convention 7)",
          access_classes_present(mixed) == ("source_refusal", "rate_limited"))

    # The token a harness writes at emission time, where the truth is actually known,
    # outranks every inference -- including one that would have gone the other way.
    stamped = access_detail("rate_limited", "robots.txt was fine; we were throttled")
    check("an explicit access_class token beats text inference",
          classify_access(stamped) == "rate_limited")
    check("access_detail stamps a machine-readable prefix",
          access_detail("source_refusal", "x").startswith("[access_class=source_refusal]"))
    try:
        access_detail("made_up", "x")
        check("access_detail rejects an unknown class", False)
    except ValueError:
        check("access_detail rejects an unknown class", True)

    check("empty and missing detail classify to nothing rather than a default",
          classify_access("") is None and classify_access(None) is None)
    print()


if __name__ == "__main__":
    sys.exit(main())
