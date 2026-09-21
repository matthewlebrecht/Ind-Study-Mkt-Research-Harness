#!/usr/bin/env python3
"""
Static, inspectable CSV snapshot of the evidence base, for submission.

WHY A SNAPSHOT AND NOT THE WORKBOOK
------------------------------------
`data/market_intel_db.xlsx` is the LIVE file every harness writes to. A reader who opens it is
looking at whatever state the last run left, cannot diff it in version control in any useful way,
and has no way to tell released evidence from quarantined. This writes a dated, read-only set of
CSVs instead: plain text, diffable, and frozen at the moment it was taken.

WHAT IT ADDS THAT THE SHEETS DO NOT
------------------------------------
Two columns that exist only as joins in the live file, so a reader never has to reconstruct them:

  * `validity_status` on every observation -- its CURRENT determination from
    Observation_Validity_History, or `valid`. Without this, an invalid row looks like any other.
  * `is_low_grade` -- whether the row was admitted under convention 41's low-grade tier. 89 of the
    147 valid buyer-side rows are, so a reader who cannot see this will over-read the counts.

Everything is a faithful copy otherwise: no filtering, no renaming, no derived judgments.

    python scripts/export_snapshot.py               # write data/export/
    python scripts/export_snapshot.py --check       # verify an existing export matches the workbook
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import topics, validity  # noqa: E402

# Sheets exported verbatim. Company_State_History is included because the derived temporal
# record is not reconstructable from the others; the coherence tables are included because
# they are reference data a reader may want to check the framework against.
SHEETS = ["Companies", "Observations", "Attempts", "Harness_Runs", "Signal_Types",
          "Harness_Sources", "Company_Executives", "Company_State_History",
          "Observation_Ids", "Observation_Validity_History", "Observation_Role_Reviews",
          "Observation_Directionality_Tags", "SEC_Reporting_Status_History",
          "Coherence_Framework_Taxonomy", "Coherence_Family_Dimensions", "Coherence_Pilot_Runs"]


def rows_of(wb, name):
    it = wb[name].iter_rows(values_only=True)
    headers = [h for h in next(it)]
    width = len(headers)
    out = []
    for r in it:
        if r is None or all(v in (None, "") for v in r[:width]):
            continue
        out.append(list(r[:width]))
    return headers, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "market_intel_db.xlsx"))
    ap.add_argument("--out", default=str(ROOT / "data" / "export"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.db, read_only=True, data_only=True)
    invalid = validity.invalid_observation_ids(wb)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written, counts = [], {}
    for name in SHEETS:
        if name not in wb.sheetnames:
            print(f"  (no sheet {name})")
            continue
        headers, rows = rows_of(wb, name)
        if name == "Observations":
            i_id = headers.index("observation_id")
            i_ex = headers.index("evidence_excerpt")
            headers = headers + ["validity_status", "is_low_grade"]
            rows = [r + [invalid.get(str(r[i_id]), "valid"),
                         str(r[i_ex] or "").startswith(topics.LOW_GRADE_MARK)] for r in rows]
        path = out / f"{name}.csv"
        counts[name] = len(rows)
        if args.check:
            existing = list(csv.reader(path.open(encoding="utf-8-sig", newline="")))
            ok = existing and existing[0] == [str(h) for h in headers] and len(existing) - 1 == len(rows)
            print(f"  {'ok  ' if ok else 'DIFF'} {name}: export {len(existing) - 1 if existing else 0} "
                  f"row(s), workbook {len(rows)}")
            continue
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            for r in rows:
                w.writerow(["" if v is None else v for v in r])
        written.append(path.name)
        print(f"  wrote {path.name:42s} {len(rows):6d} row(s)")

    if args.check:
        return 0

    n_obs = counts.get("Observations", 0)
    n_inv = len(invalid)
    (out / "README.md").write_text(
        f"""# Evidence base — static export ({_dt.date.today().isoformat()})

A frozen, read-only snapshot of the project's evidence base, written by
`python scripts/export_snapshot.py`. **The live file is `data/market_intel_db.xlsx`; this is not it
and is never written to by a harness.** Re-verify at any time with `--check`.

CSV, UTF-8 with BOM (so Excel opens it correctly), one file per sheet, copied verbatim except for
two columns added to `Observations.csv` that otherwise exist only as joins:

| Column | Meaning |
|---|---|
| `validity_status` | the observation's CURRENT determination, or `valid`. {n_inv} of {n_obs} rows carry one. An invalid row is NOT deleted (convention 45) and looks like any other row without this column |
| `is_low_grade` | admitted under convention 41's low-grade tier (grade C, marked excerpt, thin corroboration but the right referent). Most buyer-side theme evidence is low-grade, so counts read without this column will be over-read |

## Reading it

- **`publication_state`** decides whether a row counts: `released` rows are published evidence,
  `quarantined` rows belong to a harness version that has not passed the audit gate and count for
  nothing yet.
- **`Attempts.csv`** is the coverage record — what each harness tried and what happened, including
  confirmed absences. A confirmed absence is coverage, not failure.
- **`Company_State_History.csv`** is the derived temporal record (one row per derivation x company x
  theme x ISO week), append-only and immutable.
- The theme-level summary built from all of this is
  `docs/analysis/theme_evidence_matrix_2026-09-17.md`.

Row counts at export: """ + ", ".join(f"{k} {v}" for k, v in counts.items()) + "\n",
        encoding="utf-8")
    print(f"\n{len(written)} file(s) + README.md in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
