#!/usr/bin/env python3
"""
Record the current id of every renumbered observation id (Matthew Lebrecht, 2026-09-15, item 20).

Before convention 43 (session 14), delete-and-rewrite runs retired an id and re-inserted the same claim under a new
one. 23 such ids remain retired. Their claims were never lost, so the old rows are not restorable -- one claim would
carry two live ids -- but the trace from the old id to the claim's current id was missing. This writes it: on each
retired id's Observation_Ids row, `current_id` = the live id holding the same natural key.

Refuses, writing nothing, if any retired id's claim has no live row (a hard deletion: restore it through
core/db.py::restore_observation instead), if a claim is live under more than one id, or if a current_id already
recorded disagrees with the registry. Idempotent: an agreeing current_id is left as it is.

    python scripts/record_id_lineage.py            # dry run on a temporary copy
    python scripts/record_id_lineage.py --apply    # write; record harness_output/audits/ID_LINEAGE_2026-09-15.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import validity  # noqa: E402
from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

RECORD = "harness_output/audits/ID_LINEAGE_2026-09-15.json"


def run(db: MarketIntelDB) -> dict:
    """Fill current_id on `db` in memory. Raises SystemExit before writing anything if a guard fails."""
    wb = db.wb
    ws = wb["Observation_Ids"]
    rh = [c.value for c in ws[1]]
    if "current_id" not in rh:
        raise SystemExit("REFUSED: Observation_Ids has no current_id column -- run scripts/migrate_schema.py --apply")
    col = {h: i + 1 for i, h in enumerate(rh) if h}
    hard = validity.hard_deletions(wb)
    if hard:
        raise SystemExit(f"REFUSED, nothing written: retired id(s) whose claim has no live row {hard} -- restore them")
    ren = validity.renumbered(wb)
    rows = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value in ren}
    problems, plan = [], []
    for oid in sorted(ren):
        if len(ren[oid]) != 1:
            problems.append(f"{oid}: claim live under {ren[oid]}")
            continue
        existing = str(ws.cell(rows[oid], col["current_id"]).value or "").strip()
        if existing and existing != ren[oid][0]:
            problems.append(f"{oid}: records current_id {existing}, but its claim is live as {ren[oid][0]}")
        plan.append((oid, ren[oid][0], existing))
    if problems:
        raise SystemExit("REFUSED, nothing written: " + "; ".join(problems))
    mapping, written, unchanged = [], [], []
    for oid, current, existing in plan:
        r = rows[oid]
        mapping.append({"retired_id": oid, "current_id": current,
                        "natural_key": ws.cell(r, col["natural_key"]).value,
                        "retired_at": str(ws.cell(r, col["retired_at"]).value or "")[:10],
                        "retired_note": ws.cell(r, col["retired_note"]).value})
        if existing:
            unchanged.append(oid)
        else:
            ws.cell(r, col["current_id"]).value = current
            written.append(oid)
    return {"mapping": mapping, "written": written, "unchanged": unchanged,
            "problems_after": validity.lineage_problems(wb)}


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
    res = run(db)
    for m in res["mapping"]:
        print(f"  {m['retired_id']} -> {m['current_id']}   retired {m['retired_at']}   {m['natural_key']}")
    print(f"written {len(res['written'])}, already recorded {len(res['unchanged'])}; "
          f"lineage problems after: {res['problems_after'] or 'none'}")
    if args.apply:
        backup_workbook(path)
        db.save()
        (ROOT / RECORD).write_text(json.dumps({
            "record": "id lineage: the current id of each renumbered observation id",
            "decision": "Matthew Lebrecht, 2026-09-15 (item 20): record which new id each of the retired ids became, "
                        "so the claim's history is traceable across the renumbering",
            "column": "Observation_Ids.current_id", **res}, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8")
        print(f"saved; record {RECORD}")
    else:
        print("DRY RUN (temporary copy) -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
