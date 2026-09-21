#!/usr/bin/env python3
"""
Backfill `evidence_directionality = seller_side` for the rows whose side is already established by
an audit finding, in ONE batch.

Build handoff 2026-09-15 §2 named the batch as "the 35 H-PROCUREMENT-01 rows and the 127
H-LOCALRECORDS-01 rows". That did not reconcile (40 and 129 by then, and most local-records rows are
not permits), so it was escalated under §3 and nothing was written. RESTATED the same day (Signal
Advisor): the batch is exactly the rows of the two kinds the cited findings classify --

  * H-PROCUREMENT-01 `federal_prime_contracts`: "in a prime award the company is the seller";
  * H-LOCALRECORDS-01 `municipal_permits_as_contractor`: "buyer as CONTRACTOR, not OWNER" --

36 + 33 = 69 rows at the restatement. Every other row of either harness (the 4 federal assistance
awards, the 94 website technology-stack rows, the 2 WARN notices) is left UNTAGGED: the findings do
not cover them, and an absent tag is this table's correct default state, not a gap to fill with
`not_applicable`.

AMENDED the same day (2026-09-15, Matthew): the prime-contract count is **37**, not 36.
H-PROCUREMENT-01 v1.4 published O00791 (Goodfellow Bros, 3 prime contracts + 1 IDV) hours after the
restatement, and it is a `federal_prime_contracts` row of exactly the kind the cited finding
classifies -- the company delivers the work to a federal agency. It joins the same batch rather than
a new one because the batch is defined by the finding's rule, not by a snapshot, and `tagged_at` is
unchanged at 2026-09-15: the same day, so no dated record is restated. The writer's no-op semantics
mean the original 69 tags are read, matched and left exactly as written. The guard is not loosened --
it still refuses on any count other than 37 + 33.

§3 is still enforced mechanically: the batch is written only if each (harness, topic) count matches
the restated count and every id is unique; otherwise the discrepancy is printed, nothing is written,
and the script exits 2. Re-running after the batch is written is a no-op.

    python scripts/backfill_evidence_directionality.py            # reconcile + dry run on a temp copy
    python scripts/backfill_evidence_directionality.py --apply    # write (only if it reconciles)
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import directionality  # noqa: E402
from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

RUN_ID = "backfill_evidence_directionality_2026-09-15"
TAGGED_AT = "2026-09-15"

# Per harness: the topics its audit finding classifies, each with the row count at the restatement,
# and the finding cited in every tagged row's notes.
TARGETS = {
    "H-PROCUREMENT-01": {
        "topics": {"federal_prime_contracts": 37},  # 36 at the restatement + O00791 (v1.4, same day)
        "notes": ("Backfill from the H-PROCUREMENT-01 audit finding (session17_report.md §1): in a prime "
                  "award the company is the seller -- the record is work it delivers to a federal agency."),
    },
    "H-LOCALRECORDS-01": {
        "topics": {"municipal_permits_as_contractor": 33},
        "notes": ("Backfill from the H-LOCALRECORDS-01 audit finding (session17_report.md §4): the permit "
                  "names the buyer as CONTRACTOR, not OWNER -- work it builds for someone else."),
    },
}


def all_rows(wb) -> list[dict]:
    ws = wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    ix = {h: i for i, h in enumerate(headers)}
    return [{k: r[ix[k]] for k in ("observation_id", "harness_id", "harness_version", "topic")}
            for r in ws.iter_rows(min_row=2, values_only=True) if r[0] and r[ix["harness_id"]] in TARGETS]


def in_scope(row: dict) -> bool:
    return row["topic"] in TARGETS[row["harness_id"]]["topics"]


def reconcile(rows: list[dict]) -> list[str]:
    """Every reason the in-scope rows are NOT the restated batch. Empty means the batch is exact."""
    problems = []
    scoped = [r for r in rows if in_scope(r)]
    for hid, spec in TARGETS.items():
        for topic, expected in spec["topics"].items():
            n = sum(1 for r in scoped if r["harness_id"] == hid and r["topic"] == topic)
            if n != expected:
                problems.append(f"{hid} {topic}: {n} row(s), the restated batch names {expected}")
    if len({r["observation_id"] for r in scoped}) != len(scoped):
        problems.append("duplicate observation_id(s) in the batch")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = ROOT / "data" / "market_intel_db.xlsx"
    if args.apply:
        db = MarketIntelDB(path)
    else:
        tmp = Path(tempfile.mkdtemp()) / "dry.xlsx"
        shutil.copy(path, tmp)
        db = MarketIntelDB(tmp)
    rows = all_rows(db.wb)
    for hid in TARGETS:
        mine = [r for r in rows if r["harness_id"] == hid]
        print(f"{hid}: in batch {dict(Counter(r['topic'] for r in mine if in_scope(r)))} | "
              f"left untagged by design {dict(Counter(r['topic'] for r in mine if not in_scope(r)))}")
    problems = reconcile(rows)
    if problems:
        print("\nESCALATE -- the in-scope rows do not reconcile to the restated batch; NOTHING WRITTEN:")
        for p in problems:
            print(f"  - {p}")
        return 2
    tags = [{"observation_id": r["observation_id"], "evidence_directionality": "seller_side",
             "tagged_at": TAGGED_AT, "tagging_run_id": RUN_ID, "notes": TARGETS[r["harness_id"]]["notes"]}
            for r in rows if in_scope(r)]
    report = directionality.append_tags(db.wb, tags)
    print(f"batch {len(tags)} | appended {report['appended']} | already present {len(report['noop'])}")
    if args.apply and report["appended"]:
        backup_workbook(path)
        db.save()
        print("saved market_intel_db.xlsx")
    elif not args.apply:
        print("DRY RUN (temporary copy) -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
