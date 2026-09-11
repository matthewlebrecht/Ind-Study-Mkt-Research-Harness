#!/usr/bin/env python3
"""
Extend Excel data-validation ranges in market_intel_db.xlsx.

Rows past a validation's bound range accept anything silently, so controlled
vocabularies stop being enforced without any error. This rebinds each sheet's
validations to a ceiling well above projected volume.

Targets:
  Observations   20,000   reconciles rather than appends
  Companies      20,000   fixed at 108, headroom is free
  Attempts      250,000   APPEND-ONLY: every re-run adds a full set of rows

Usage:
  python extend_validation.py --db data/market_intel_db.xlsx           # report only
  python extend_validation.py --db data/market_intel_db.xlsx --apply
"""

import argparse
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.workbook_backup import backup_workbook  # noqa: E402

TARGETS = {
    "Observations": 20_000,
    "Companies": 20_000,
    "Attempts": 250_000,
    "Company_Executives": 20_000,
    "Discards": 20_000,
    "Harness_Sources": 20_000,
}


def parse_sqref(sqref):
    """Yield (col_start, row_start, col_end, row_end) for each range in a sqref."""
    for part in str(sqref).split():
        m = re.match(r"^\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)$", part)
        if m:
            yield m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        else:
            m = re.match(r"^\$?([A-Z]+)\$?(\d+)$", part)
            if m:
                yield m.group(1), int(m.group(2)), m.group(1), int(m.group(2))


def rebind(sqref, ceiling):
    """Rewrite a sqref so every range ends at `ceiling`. Start row is preserved."""
    out = []
    for c1, r1, c2, _ in parse_sqref(sqref):
        out.append(f"{c1}{r1}:{c2}{ceiling}")
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true", help="write changes (default: report only)")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.db)
    changes = []

    for sheet_name, ceiling in TARGETS.items():
        if sheet_name not in wb.sheetnames:
            print(f"  {sheet_name:20s} — sheet absent, skipped")
            continue
        ws = wb[sheet_name]
        for dv in ws.data_validations.dataValidation:
            old = str(dv.sqref)
            new = rebind(old, ceiling)
            if old != new:
                changes.append((sheet_name, old, new))
                if args.apply:
                    dv.sqref = openpyxl.worksheet.cell_range.MultiCellRange(new)

        # warn if data already sits past the old binding
        bound = max(
            (r2 for dv in ws.data_validations.dataValidation
             for _, _, _, r2 in parse_sqref(dv.sqref)),
            default=0,
        )
        if bound and ws.max_row > bound:
            print(f"  !! {sheet_name}: {ws.max_row} rows exceed binding at {bound} "
                  f"— those rows are already unvalidated")

    for sheet, old, new in changes:
        print(f"  {sheet:20s} {old:28s} -> {new}")

    if not changes:
        print("  nothing to change")
        return

    if args.apply:
        backup, pruned = backup_workbook(args.db)
        wb.save(args.db)
        print(f"\napplied {len(changes)} change(s); backup at {backup.name}")
        if pruned:
            print(f"pruned {len(pruned)} older backup(s): {', '.join(p.name for p in pruned)}")
    else:
        print(f"\n{len(changes)} change(s) pending — re-run with --apply")


if __name__ == "__main__":
    main()
