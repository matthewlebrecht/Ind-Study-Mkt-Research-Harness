#!/usr/bin/env python3
"""
Evidence directionality: the tag table's rules, its writer, the convention 41 wall, and the backfill's
reconciliation guard (build handoff 2026-09-15), on a throwaway copy of the workbook.

    python core/tests/test_directionality.py
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import directionality as D  # noqa: E402
from core.db import MarketIntelDB  # noqa: E402
from scripts import backfill_evidence_directionality as B  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def tag(oid, value="seller_side", run="HR-TEST", notes=""):
    return {"observation_id": oid, "evidence_directionality": value, "tagged_at": "2026-09-15",
            "tagging_run_id": run, "notes": notes}


def refused(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    if D.SHEET in db.wb.sheetnames:
        del db.wb[D.SHEET]
    ws = db.wb.create_sheet(D.SHEET)
    ws.append(D.COLUMNS)
    ids = sorted(D.observation_ids(db.wb))
    a, b = ids[0], ids[1]

    print("1. vocabulary and row rules")
    check("exactly the four designed values", D.VALUES == ("buyer_side", "seller_side", "mixed", "not_applicable"))
    check("the table name fits Excel's 31-character sheet limit", len(D.SHEET) <= 31)
    check("a tag is valid without notes when it is neither mixed nor a backfill", not D.problems_with(tag(a), set(ids)))
    check("an unknown value is refused", D.problems_with(tag(a, value="sell_side")))
    check("an observation_id that does not resolve is refused", D.problems_with(tag("O99999"), set(ids)))
    check("mixed without notes is refused", any("mixed" in p for p in D.problems_with(tag(a, value="mixed"))))
    check("a backfill tag without notes is refused",
          any("backfill" in p for p in D.problems_with(tag(a, run="backfill_x_2026-09-15"))))
    check("tagged_at must be an ISO date", D.problems_with({**tag(a), "tagged_at": "15/09/2026"}))

    print("2. the writer")
    rep = D.append_tags(db.wb, [tag(a), tag(b, value="mixed", notes="both sides named")])
    check("a valid batch appends", rep["appended"] == 2 and len(D.rows_from_sheet(ws)) == 2)
    rep = D.append_tags(db.wb, [tag(a)])
    check("an identical tag is a no-op, never written twice", rep["appended"] == 0 and rep["noop"] == [a])
    check("a different value for the same (observation, run) is refused -- a tag is never overwritten",
          refused(lambda: D.append_tags(db.wb, [tag(a, value="buyer_side")])))
    before = len(D.rows_from_sheet(ws))
    check("a batch with one bad tag writes nothing at all",
          refused(lambda: D.append_tags(db.wb, [tag(ids[2]), tag("O99999")])) and len(D.rows_from_sheet(ws)) == before)
    rep = D.append_tags(db.wb, [tag(a, value="buyer_side", run="HR-OTHER")])
    check("another tagging run may tag the same observation", rep["appended"] == 1)
    check("no column was added to Observations",
          "evidence_directionality" not in [c.value for c in db.wb["Observations"][1]])

    print("3. the convention 41 wall")
    gate = ["core/db.py", "core/audit.py", "core/attempts.py", "core/composition.py",
            "scripts/write_audit_artifact.py", "scripts/published_coverage.py", "scripts/audit_sample.py",
            "scripts/check_run_ledger.py"]
    pat = re.compile(r"Observation_Directionality_Tags|core\.directionality|import\s+directionality|directionality\s+import")
    leaks = [m for m in gate if (ROOT / m).exists() and pat.search((ROOT / m).read_text(encoding="utf-8"))]
    check("no gate-computing module names the tag table or imports its module", not leaks)
    v = (ROOT / "scripts/validate_repo_db.py").read_text(encoding="utf-8").splitlines()
    begin = next(i for i, l in enumerate(v) if "DIRECTIONALITY-WALL-CHECK-BEGIN" in l and "in l" not in l)
    end = next(i for i, l in enumerate(v) if "DIRECTIONALITY-WALL-CHECK-END" in l and "in l" not in l)
    outside = [i + 1 for i, l in enumerate(v) if pat.search(l) and not begin <= i <= end]
    check("the validator reads the table only inside its fenced check", not outside)

    print("4. the backfill's reconciliation guard (restated batch, 2026-09-15)")
    def rows(n_prime, n_permit, extra=()):
        out = [{"observation_id": f"P{i}", "harness_id": "H-PROCUREMENT-01", "harness_version": "v1.0",
                "topic": "federal_prime_contracts"} for i in range(n_prime)]
        out += [{"observation_id": f"L{i}", "harness_id": "H-LOCALRECORDS-01", "harness_version": "v1.0",
                 "topic": "municipal_permits_as_contractor"} for i in range(n_permit)]
        out += [{"observation_id": f"X{i}", "harness_id": h, "harness_version": "v1.0", "topic": t}
                for i, (h, t) in enumerate(extra)]
        return out
    others = [("H-PROCUREMENT-01", "federal_assistance_awards")] * 4 + \
             [("H-LOCALRECORDS-01", "website_technology_stack")] * 94 + [("H-LOCALRECORDS-01", "warn_layoff_notice")] * 2
    # The batch was restated at 36 + 33 and AMENDED to 37 + 33 on 2026-09-15, when
    # H-PROCUREMENT-01 v1.4 published O00791 hours later. The guard is not loosened by that:
    # it still refuses any other count, in EITHER direction, which is why the old count is
    # asserted to fail here rather than simply being replaced.
    check("37 prime-contract + 33 permit rows reconcile, with the other 100 rows present",
          B.reconcile(rows(37, 33, others)) == [])
    check("assistance, techstack and WARN rows are out of scope -- left untagged, not tagged not_applicable",
          not any(B.in_scope(r) for r in rows(0, 0, others)))
    check("the pre-amendment count of 36 no longer reconciles", B.reconcile(rows(36, 33)))
    check("a prime-contract count above the batch does not reconcile", B.reconcile(rows(38, 33)))
    check("a permit count that differs from the batch does not reconcile", B.reconcile(rows(37, 32)))
    check("a permit count that differs does not reconcile", B.reconcile(rows(36, 32)))
    check("the backfill run id is a batch marker, not a harness run id",
          B.RUN_ID.startswith(D.BACKFILL_PREFIX) and not B.RUN_ID.startswith("HR-"))

    print(f"\n{PASS} passed, {FAIL} failed (worked on {tmp})")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
