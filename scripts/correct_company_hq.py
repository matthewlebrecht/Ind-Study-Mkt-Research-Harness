#!/usr/bin/env python3
"""
Record a corrected company headquarters -- a dated decision, one entry at a time.

`Companies.hq_state` / `hq_city` are inputs to every state-keyed identity gate (procurement's HQ-state
gate, the breach-portal scope, WARN scope, OSHA search, the same-HQ-city alias standard), so a wrong
value produces quiet errors downstream. A correction is therefore never a hand edit: each entry names
the value it replaces and is refused unless the sheet still holds exactly that value, and the reason
is APPENDED to `Companies.notes` so the earlier decision stays readable beside the correction.

    python scripts/correct_company_hq.py            # dry run
    python scripts/correct_company_hq.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

CORRECTIONS = [
    # Matthew's decision, 2026-09-15. Session 16's CA value (2026-09-06) rested on an EPA facility
    # record, which is a site, not a headquarters. A systematic check the same day found it isolated:
    # A024 is the only hq_state changed since the workbook's first commit and the only company whose
    # notes cite an EPA facility; no code writes hq_state.
    {"company_id": "A024", "from": {"hq_state": "CA", "hq_city": None},
     "to": {"hq_state": "WA", "hq_city": "Wenatchee"},
     "note": ("2026-09-15 CORRECTION by Matthew's decision: hq_state CA -> WA, hq_city Wenatchee. Goodfellow Bros was "
              "founded in Wenatchee in 1921 and its corporate headquarters functions (accounting, contracts, safety, IT, "
              "equipment) are there, per the company's own materials and Wenatchee historical/business sources; Livermore, "
              "CA is a regional office. The 2026-09-06 CA value rested on an EPA facility record, and a facility is not a "
              "headquarters. Corroborating records already held: FMCSA census GOODFELLOW BROS LLC, USDOT 28686, physical "
              "address Wenatchee WA; USASpending GOODFELLOW BROS, LLC, UEI CLAXYN5FDP93, Wenatchee WA.")},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = ROOT / "data" / "market_intel_db.xlsx"
    db = MarketIntelDB(path)
    ws = db.wb["Companies"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    ix = {h: i + 1 for i, h in enumerate(headers)}
    for col in ("hq_state", "hq_city", "notes"):
        if col not in ix:
            raise SystemExit(f"Companies.{col} missing -- run scripts/migrate_schema.py --apply")
    rows = {ws.cell(r, ix["company_id"]).value: r for r in range(2, ws.max_row + 1)}
    changed = 0
    for c in CORRECTIONS:
        r = rows.get(c["company_id"])
        if r is None:
            raise SystemExit(f"{c['company_id']} not in Companies")
        now = {k: ws.cell(r, ix[k]).value or None for k in c["to"]}
        if now == c["to"]:
            print(f"  no-op {c['company_id']}: already {c['to']}")
            continue
        if now != c["from"]:
            raise SystemExit(f"REFUSED {c['company_id']}: sheet holds {now}, the correction replaces {c['from']} "
                             f"-- someone changed it since; re-read before correcting")
        for k, v in c["to"].items():
            ws.cell(r, ix[k]).value = v
        old = str(ws.cell(r, ix["notes"]).value or "").strip()
        ws.cell(r, ix["notes"]).value = (old + " | " if old else "") + c["note"]
        changed += 1
        print(f"  {c['company_id']}: {c['from']} -> {c['to']}")
    if args.apply and changed:
        backup_workbook(path)
        db.save()
        print("saved market_intel_db.xlsx")
    elif not args.apply:
        print("DRY RUN -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
