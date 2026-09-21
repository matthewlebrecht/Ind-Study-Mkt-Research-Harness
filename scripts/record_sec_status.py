#!/usr/bin/env python3
"""
Record SEC reporting-status determinations made AFTER the seed, one decision at a time.

`scripts/load_sec_reporting_status.py` holds the 13-row seed exactly as the Harness Advisor
design fixed it. A later determination is a separate, dated decision and lives here, so the seed
stays the seed and every change of status is reproducible from the repo. Each entry goes through
core/db.py::append_sec_status: a new row, `superseded_by` set on the company's previous current
row, and a no-op if it is already recorded.

    python scripts/record_sec_status.py            # dry run on a temporary copy
    python scripts/record_sec_status.py --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import sec_status  # noqa: E402
from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

DETERMINATIONS = [
    # Decision relayed 2026-09-14 (session 17 follow-up brief, item 1). Session 17 flagged the
    # contradiction and held off: EDGAR shows deregistration paperwork filed after the 10-Q the
    # seeded active_reporter row (as of 2025-08-14) rests on. as_of_date is the later of the two
    # filings; the source_filing_type is written as the brief specifies it.
    {"company_id": "A029", "sec_reporting_status": "deregistered", "source_filing_type": "Form 15-12G",
     "source_reference": "EDGAR CIK 0000877422 SpartanNash Co; Form 25-NSE filed 2025-09-22, Form 15-12G filed 2025-10-02",
     "as_of_date": "2025-10-02",
     "determined_by": "Claude Code, session 17 follow-up, on Matthew's decision relayed 2026-09-14",
     "notes": "Supersedes the seeded active_reporter row (as of the 10-Q filed 2025-08-14). Form 25-NSE "
              "(delisting, 2025-09-22) then Form 15-12G (termination of registration, 2025-10-02) after the "
              "take-private; no periodic reports since."},
]


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
    before = sec_status.active_reporters(db.sec_status_rows())
    report = db.append_sec_status(DETERMINATIONS)
    after = sec_status.active_reporters(db.sec_status_rows())
    print(f"appended {report['appended']} | superseded {report['superseded']}")
    for n in report["noop"]:
        print(f"  no-op {n}")
    print(f"active_reporters (derived): before {before} -> after {after}")
    if args.apply and report["appended"]:
        backup_workbook(path)
        db.save()
        print("saved market_intel_db.xlsx")
    elif not args.apply:
        print("DRY RUN (temporary copy) -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
