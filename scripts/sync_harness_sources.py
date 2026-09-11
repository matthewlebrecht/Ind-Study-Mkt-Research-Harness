#!/usr/bin/env python3
"""
Project each manifest's `sources:` block into the `Harness_Sources` junction sheet.

The manifest is the source of truth (repo_structure_spec.md §5); the sheet is a
materialized view of it, so the workbook can answer "which harnesses depend on the FMCSA
API" without reading YAML. Composite key is (harness_id, harness_version, source_id, role)
-- role is part of the key because one harness can use one source in two roles, which
H-FMCSA-01 does: SAFER is `primary` for the claims it produces and `resolution_only` for
the name->USDOT lookup that is never cited in an Observation.

Idempotent. Re-running reconciles rather than appending.

    python scripts/sync_harness_sources.py
    python scripts/sync_harness_sources.py --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"
COLUMNS = ["harness_id", "harness_version", "source_id", "role", "notes"]


def desired_rows() -> list[dict]:
    rows = []
    for path in sorted((ROOT / "harnesses").glob("*/manifest.yaml")):
        m = yaml.safe_load(path.read_text(encoding="utf-8"))
        version = str(m["current_version"])
        for s in m.get("sources", []):
            if isinstance(s, str):
                s = {"id": s, "role": "primary"}
            rows.append({
                "harness_id": m["harness_id"],
                "harness_version": version,
                "source_id": s["id"],
                "role": s.get("role", "primary"),
                "notes": " ".join(str(s.get("notes", "")).split()) or None,
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    path = Path(args.db)
    wb = openpyxl.load_workbook(path)
    ws = wb["Harness_Sources"]

    existing = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        key = tuple(str(ws.cell(r, c).value or "") for c in range(1, 5))
        existing[key] = r

    added = 0
    for row in desired_rows():
        key = tuple(str(row[c] or "") for c in COLUMNS[:4])
        if key in existing:
            continue
        ws.append([row[c] for c in COLUMNS])
        added += 1
        print(f"  + {row['harness_id']} {row['harness_version']} "
              f"{row['source_id']} ({row['role']})")

    stale = [k for k in existing if k not in
             {tuple(str(r[c] or "") for c in COLUMNS[:4]) for r in desired_rows()}]
    for k in stale:
        print(f"  ! row {existing[k]} {k} is in the sheet but not in any manifest "
              "— left in place (historical versions are kept)")

    if not added:
        print("  Harness_Sources is current")
        return 0
    if not args.apply:
        print(f"\n{added} row(s) pending — re-run with --apply")
        return 0

    backup = path.with_name(f"{path.stem}.bak-{datetime.now():%Y%m%d-%H%M%S}{path.suffix}")
    shutil.copy2(path, backup)
    wb.save(path)
    print(f"\nadded {added} row(s); backup at {backup.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
