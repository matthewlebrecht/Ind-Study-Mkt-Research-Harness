#!/usr/bin/env python3
"""
Populate `Companies.hq_city` (approved 2026-09-15) -- BLANKS ONLY, never a guess, never an overwrite.

The same-HQ-city identity standard (session 17 alias work: McShane, Clyde, Leprino, Cajun) compares a
candidate record's city with the company's HQ city, and `Companies` had no city column: 97 buyers carry
"City, ST" in `hq_state` (the Talbot West CRM export's format), 11 do not. This fills `hq_city` from
what `hq_state` already says:

  * "City, ST"            -> the city part;
  * a bare 2-letter code  -> left blank (the 8 pilots; no city on record);
  * any other bare value  -> that value, because `hq_state` holds a city there, not a state
                             (Crane Worldwide "Houston", doTERRA "Pleasant Grove"); the hq_state
                             defect itself is logged, not fixed here.

A city from any other source is entered only through SOURCED below, with its record cited. A
corrected headquarters (state and city together) is a separate dated decision in
scripts/correct_company_hq.py -- Goodfellow Bros (A024), corrected to Wenatchee, WA on 2026-09-15.

    python scripts/populate_hq_city.py            # dry run
    python scripts/populate_hq_city.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

# company_id -> (city, citation). Empty until a city is established from a record.
SOURCED: dict[str, tuple[str, str]] = {}


def city_from_hq_state(value) -> str | None:
    v = str(value or "").strip()
    if not v:
        return None
    if "," in v:
        return v.split(",")[0].strip() or None
    if re.fullmatch(r"[A-Za-z]{2}", v):
        return None
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = ROOT / "data" / "market_intel_db.xlsx"
    db = MarketIntelDB(path)
    ws = db.wb["Companies"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    if "hq_city" not in headers:
        raise SystemExit("Companies.hq_city missing -- run scripts/migrate_schema.py --apply")
    ix = {h: i + 1 for i, h in enumerate(headers)}
    filled, kept, blank = [], 0, []
    for r in range(2, ws.max_row + 1):
        cid = ws.cell(r, ix["company_id"]).value
        if not cid or str(cid).startswith("P"):
            continue
        if ws.cell(r, ix["hq_city"]).value not in (None, ""):
            kept += 1
            continue
        city = SOURCED[cid][0] if cid in SOURCED else city_from_hq_state(ws.cell(r, ix["hq_state"]).value)
        if city:
            ws.cell(r, ix["hq_city"]).value = city
            filled.append((cid, city))
        else:
            blank.append((cid, ws.cell(r, ix["canonical_name"]).value, ws.cell(r, ix["hq_state"]).value))
    print(f"filled {len(filled)} | already set {kept} | left blank {len(blank)}")
    for cid, name, hq in blank:
        print(f"  blank: {cid} {name} (hq_state {hq!r})")
    odd = [(c, v) for c, v in filled if c in ("A058", "A059")]
    if odd:
        print(f"  note: hq_state holds a city, not a state, for {odd} -- hq_state not changed")
    if args.apply and filled:
        backup_workbook(path)
        db.save()
        print("saved market_intel_db.xlsx")
    elif not args.apply:
        print("DRY RUN -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
