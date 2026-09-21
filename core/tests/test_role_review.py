#!/usr/bin/env python3
"""
Role-classification reviews: the table's row, run and artifact rules, its writer, the convention 41
wall, and the first real batch (buyer_articulates, 2026-09-15), on a throwaway copy of the workbook.

    python core/tests/test_role_review.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import role_review as R  # noqa: E402
from core.db import MarketIntelDB  # noqa: E402
from scripts import load_role_review as L  # noqa: E402
from scripts import migrate_schema as M  # noqa: E402

PASS = FAIL = 0
RUN = "role_review_test_2026-09-15"
ART = "harness_output/audits/ROLE_REVIEW_test_verdicts.json"
NOTE = "Role review only; it re-clears neither identity nor extraction. 3 of 10, stratified."


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def refused(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def row(oid, verdict="correct", stratum="H-X / a", sn=2, sp=6, words="", **kw):
    r = {"observation_id": oid, "role_at_review": "buyer_articulates", "role_verdict": verdict,
         "review_scope": "role_only", "reviewer": "Reviewer", "review_source": "human",
         "reviewed_at": "2026-09-15", "review_run_id": RUN, "sample_design": "stratified_random",
         "sample_n": 3, "population_n": 10, "stratum": stratum, "stratum_sampled_n": sn,
         "stratum_population_n": sp, "reviewer_words": words, "artifact": ART, "notes": NOTE}
    r.update(kw)
    return r


def write_artifact(root: Path, rows: list[dict], **over):
    art = {"table": R.SHEET, "review_run_id": RUN, "reviewer": "Reviewer", "review_date": "2026-09-15",
           "review_source": "human", "sample_design": "stratified_random", "sampled_n": 3,
           "population_n": 10, "scope": f"ROLE only; {R.SCOPE_STATEMENT}.",
           "strata": [{"harness_id": "H-X", "sub_stratum": "a", "sampled_n": 2, "population_n": 6},
                      {"harness_id": "H-X", "sub_stratum": "b", "sampled_n": 1, "population_n": 4}],
           "verdicts": [{"observation_id": r["observation_id"], "harness_id": "H-X",
                         "sub_stratum": r["stratum"].split(" / ")[1], "role_at_review": r["role_at_review"],
                         "role_verdict": r["role_verdict"], "reviewer_words": r["reviewer_words"],
                         "note": r["notes"]} for r in rows]}
    art.update(over)
    p = root / ART
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(art), encoding="utf-8")


def main() -> int:
    work = Path(tempfile.mkdtemp())
    tmp = work / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    if R.SHEET in db.wb.sheetnames:
        del db.wb[R.SHEET]
    ws = db.wb.create_sheet(R.SHEET)
    ws.append(R.COLUMNS)
    ids = sorted(R.observation_ids(db.wb))
    a, b, c = ids[0], ids[1], ids[2]

    print("1. vocabulary, schema declaration and row rules")
    check("the table name fits Excel's 31-character sheet limit", len(R.SHEET) <= 31)
    check("the schema migration declares exactly these columns", M.NEW_SHEETS.get(R.SHEET) == R.COLUMNS)
    check("the Lookups vocabulary is exactly the module's verdicts",
          tuple(M.NEW_VOCABULARIES["AE"][1]) == R.VERDICTS and M.NEW_VOCABULARIES["AE"][0] == "role_review_verdict")
    binding = [v for v in M.VALIDATIONS if v[0] == R.SHEET]
    check("role_verdict is dropdown-bound to that vocabulary",
          binding == [(R.SHEET, "C", "AE", 250_000)] and R.COLUMNS[2] == "role_verdict")
    lookups = db.wb["Lookups"]
    roles = {lookups.cell(r, 1).value for r in range(2, lookups.max_row + 1)} - {None}
    check("role_at_review's roles are the Lookups evidence_role vocabulary", set(R.ROLES) == roles)
    check("no column was added to Observations",
          not {"role_verdict", "role_at_review", "review_scope"} & {x.value for x in db.wb["Observations"][1]})
    ok = row(a)
    check("a complete row is valid", not R.problems_with(ok, set(ids)))
    check("an unknown verdict is refused", R.problems_with(row(a, verdict="supported")))
    check("a verdict repeating the reviewed role is refused (use 'correct')",
          any("repeats" in p for p in R.problems_with(row(a, verdict="buyer_articulates"))))
    check("a scope other than role_only is refused", R.problems_with(row(a, review_scope="full")))
    check("notes that do not say the review re-clears neither identity nor extraction are refused",
          any("re-clears" in p for p in R.problems_with(row(a, notes="role review, 3 of 10"))))
    check("a machine-sourced role verdict is refused", R.problems_with(row(a, review_source="machine")))
    check("a non-'correct' verdict without the reviewer's words is refused",
          any("own words" in p for p in R.problems_with(row(a, verdict="buyer_acts"))))
    check("the same verdict with the reviewer's words is valid",
          not R.problems_with(row(a, verdict="buyer_acts", words="buyer did"), set(ids)))
    check("a harness run id is refused as a review run", R.problems_with(row(a, review_run_id="HR-0001")))
    check("a stratum claiming more reviewed than its population is refused", R.problems_with(row(a, sn=7, sp=6)))
    check("a sample larger than its population is refused", R.problems_with(row(a, sample_n=11)))
    check("'census' with sample_n below population_n is refused", R.problems_with(row(a, sample_design="census")))
    check("a missing sample basis is refused", R.problems_with(row(a, sample_n=None)))
    check("an artifact outside harness_output/audits is refused", R.problems_with(row(a, artifact="notes.json")))
    check("an observation id never assigned is refused", R.problems_with(row("O99999"), set(ids)))

    print("2. run rules, the artifact link, and the writer")
    batch = [row(a), row(b), row(c, stratum="H-X / b", sn=1, sp=4, verdict="buyer_acts", words="buyer did")]
    write_artifact(work, batch)
    obs_before = L.observations_digest(db.wb)
    check("a partial run is refused -- rows must number sample_n",
          refused(lambda: R.append_reviews(db.wb, batch[:2], work)) and not R.rows_from_sheet(ws))
    inflated = [row(a, sn=3), row(b, sn=3), batch[2]]
    check("a stratum claiming more rows reviewed than it holds is refused", R.batch_problems(inflated))
    check("strata that do not sum to the population are refused",
          R.batch_problems([row(a), row(b), row(c, stratum="H-X / b", sn=1, sp=9, verdict="buyer_acts", words="w")]))
    write_artifact(work, [batch[0], batch[1], {**batch[2], "role_verdict": "other"}])
    check("a run disagreeing with its artifact is refused",
          refused(lambda: R.append_reviews(db.wb, batch, work)) and not R.rows_from_sheet(ws))
    write_artifact(work, batch[:2])
    check("a row absent from the artifact is refused", refused(lambda: R.append_reviews(db.wb, batch, work)))
    write_artifact(work, batch, scope="full audit")
    check("an artifact whose scope does not say role-only is refused", refused(lambda: R.append_reviews(db.wb, batch, work)))
    check("a missing artifact is refused", bool(R.artifact_problems(batch, work / "nowhere")))
    write_artifact(work, batch)
    rep = R.append_reviews(db.wb, batch, work)
    check("a complete run that agrees with its artifact appends", rep["appended"] == 3 and len(R.rows_from_sheet(ws)) == 3)
    rep = R.append_reviews(db.wb, batch, work)
    check("re-appending the identical run is a no-op", rep["appended"] == 0 and len(rep["noop"]) == 3)
    check("a changed verdict for a recorded (observation, run) is refused -- never overwritten",
          refused(lambda: R.append_reviews(db.wb, [batch[0], batch[1], {**batch[2], "role_verdict": "other"}], work)))
    check("Observations is byte-for-byte unchanged by the writer", L.observations_digest(db.wb) == obs_before)
    check("role drift is reported when the reviewed role no longer matches",
          R.role_drift(batch, {a: "buyer_articulates", b: "buyer_articulates", c: "buyer_articulates"}) == [] and
          R.role_drift(batch, {a: "buyer_articulates", b: "buyer_articulates", c: "buyer_acts"}) ==
          [f"{c} reviewed as buyer_articulates, now buyer_acts"])

    print("3. the convention 41 wall")
    gate = ["core/db.py", "core/audit.py", "core/attempts.py", "core/composition.py",
            "scripts/write_audit_artifact.py", "scripts/published_coverage.py", "scripts/audit_sample.py",
            "scripts/check_run_ledger.py"]
    pat = re.compile(r"Observation_Role_Reviews|core\.role_review\b|import\s+role_review\b|role_review\s+import")
    leaks = [m for m in gate if (ROOT / m).exists() and pat.search((ROOT / m).read_text(encoding="utf-8"))]
    check("no gate-computing module names the table or imports its module", not leaks)
    v = (ROOT / "scripts/validate_repo_db.py").read_text(encoding="utf-8").splitlines()
    begin = next(i for i, l in enumerate(v) if "ROLE-REVIEW-WALL-CHECK-BEGIN" in l and "in l" not in l)
    end = next(i for i, l in enumerate(v) if "ROLE-REVIEW-WALL-CHECK-END" in l and "in l" not in l)
    outside = [i + 1 for i, l in enumerate(v) if pat.search(l) and not begin <= i <= end]
    check("the validator reads the table only inside its fenced check", not outside)
    check("the writer module never writes to Observations",
          not re.search(r"wb\[\"Observations\"\]\.(append|cell\(.*\)\.value\s*=)|delete_rows",
                        (ROOT / "core/role_review.py").read_text(encoding="utf-8")))

    print("4. the first real batch: buyer_articulates, 2026-09-15")
    real = L.rows_from_artifact(L.DEFAULT_ARTIFACT)
    check("59 rows built from the committed artifact", len(real) == 59)
    check("58 'correct' and 1 'buyer_acts', on O00303",
          sum(r["role_verdict"] == "correct" for r in real) == 58 and
          [r["observation_id"] for r in real if r["role_verdict"] != "correct"] == ["O00303"])
    check("every row passes the row rules", not [p for r in real for p in R.problems_with(r, set(ids))])
    check("the run reconciles: 59 of 249, strata partition sample and population", not R.batch_problems(real))
    check("the run agrees with its committed artifact in both directions", not R.artifact_problems(real, ROOT))
    check("O00303's row quotes the reviewer's words", "buyer did" in next(r for r in real if r["observation_id"] == "O00303")["reviewer_words"])
    obs_before = L.observations_digest(db.wb)
    rep = R.append_reviews(db.wb, real, ROOT)
    check("the real batch appends on the copy, Observations untouched",
          rep["appended"] == 59 and L.observations_digest(db.wb) == obs_before)

    print(f"\n{PASS} passed, {FAIL} failed (worked on {tmp})")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
