#!/usr/bin/env python3
"""
Seed `Company_SEC_Reporting_Status_History` with the 12 companies from session 17's EDGAR pass.

Exactly the rows the Harness Advisor design fixed (session 17 wrap-up brief, 2026-09-13) --
13 rows for 12 companies, EnergySolutions contributing two -- and nothing else. In particular
the other 96 buyers get NO row: `never_registered` is written only after someone has actually
checked a company, never defaulted from absence in one search pass.

Each row's `as_of_date` is the date the evidence establishes (the filing that shows the
status), not the load date, and `source_reference` names the EDGAR filer (CIK) and the filing.
Evidence: EDGAR full-text search (efts.sec.gov) and data.sec.gov submissions, 2026-09-13, under
the declared SEC contact.

Idempotent through core/db.py::append_sec_status: an identical row or an unchanged current
status is a no-op, so re-running writes nothing.

    python scripts/load_sec_reporting_status.py            # dry run
    python scripts/load_sec_reporting_status.py --apply
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

BY = ("Claude Code, session 17: EDGAR full-text search and data.sec.gov submissions, 2026-09-13; "
      "seed fixed by the Harness Advisor design (session 17 wrap-up brief)")

# Order matters for EnergySolutions: the historical row first, then the row that supersedes it.
SEED = [
    ("A030", "active_reporter", "10-Q",
     "EDGAR CIK 0000856982 MERIT MEDICAL SYSTEMS INC (MMSI); 10-Q filed 2026-07-30, period 2026-06-30",
     "2026-07-30", ""),
    ("A029", "active_reporter", "10-Q",
     "EDGAR CIK 0000877422 SpartanNash Co; 10-Q filed 2025-08-14, period 2025-07-12",
     "2025-08-14",
     "Loaded as the design specifies. The same filer's record continues past this date with Form "
     "25-NSE (2025-09-22) and Form 15-12G (2025-10-02): evidence of deregistration after the "
     "take-private. Not written here because the seed was fixed at active_reporter; flagged in the "
     "session 17 report -- under this table's own mechanics it would be a superseding "
     "`deregistered` row as of 2025-10-02."),
    ("A019", "active_reporter", "10-Q",
     "EDGAR CIK 0001692415 Co-Diagnostics, Inc. (CODX); 10-Q filed 2026-08-13, period 2026-06-30",
     "2026-08-13", ""),
    ("A038", "form_d_only", "D",
     "EDGAR CIK 0001175806 MCCARTHY HOLDINGS, INC.; Form D filed 2011-07-01 (also 2009-11-16; REGDEX 2002)",
     "2011-07-01",
     "MCCARTHY INVESTMENT COMPANY, LLC (CIK 0001586327, Form D/A through 2025) is a different filer "
     "and is not part of this determination."),
    ("A058", "form_d_only", "D",
     "EDGAR CIK 0001486767 Crane Worldwide Logistics LLC; Form D filed 2010-03-29",
     "2010-03-29", ""),
    ("A085", "form_d_only", "D",
     "EDGAR CIK 0000932026 UniGroup, Inc.; Form D filed 2013-09-20 (also 2011-01-18; REGDEX 2005)",
     "2013-09-20",
     "Tsinghua Unigroup International Co., Ltd. (CIK 0001647753) is unrelated."),
    ("A092", "form_d_only", "D",
     "EDGAR CIK 0001810487 Herzog Enterprises, Inc.; Form D filed 2020-04-24",
     "2020-04-24", ""),
    ("A056", "withdrawn_registration", "RW",
     "EDGAR CIK 0001298004 KENAN ADVANTAGE GROUP INC; S-1 filed 2004-07-29, withdrawn by Form RW 2006-02-01",
     "2006-02-01",
     "KENAN TRANSPORT CO (CIK 0000745379), a predecessor, was a reporter until Form 15-12G "
     "(2001-04-30); a separate filer, not recorded here."),
    ("C0004", "withdrawn_registration", "RW",
     "EDGAR CIK 0001340578 Western Express Holdings, Inc.; S-1 filed 2005-11-14, withdrawn by Form RW 2009-04-14",
     "2009-04-14", ""),
    ("A041", "insider_only", "4",
     "EDGAR CIK 0001506777 J.R. Simplot Co; Forms 3 / 4 and Schedule 13G as a holder in another issuer; latest Form 4 filed 2025-03-04",
     "2025-03-04", ""),
    ("A011", "active_reporter", "10-Q",
     "EDGAR CIK 0001393744 EnergySolutions, Inc.; 10-Q filed 2013-11-12, period 2013-09-30",
     "2013-11-12",
     "Historical. Forms 15-12B and 15-15D were filed 2013-06-07 after the acquisition; periodic "
     "reporting continued under section 15(d) until the final Form 15-15D (next row)."),
    ("A011", "deregistered", "15-15D",
     "EDGAR CIK 0001393744 EnergySolutions, Inc.; final Form 15-15D filed 2014-01-27",
     "2014-01-27",
     "The FY2013 10-K (2014-03-31) and Q1 2014 10-Q (2014-05-15) were filed after this Form 15 as "
     "trailing obligations; no filings since."),
    ("A094", "entity_unresolved", "S-3",
     "EDGAR CIK 0001737580 Lynden USA Inc.; co-registrant on S-3s filed 2018-04-18 and 2021-03-10 with Lynden Energy Corp. (CIK 0001622620)",
     "2021-03-10",
     "IDENTITY doubt, not status doubt: the only filer bearing the name is a co-registrant of an "
     "oil-and-gas registrant (Lynden Energy Corp., deregistered 2016), and nothing ties it to Lynden, "
     "Inc., the Seattle logistics company. No status is asserted for the company."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    dets = [{"company_id": cid, "sec_reporting_status": st, "source_filing_type": ft,
             "source_reference": ref, "as_of_date": asof, "determined_by": BY, "notes": notes}
            for cid, st, ft, ref, asof, notes in SEED]
    assert len(dets) == 13 and len({d["company_id"] for d in dets}) == 12

    path = ROOT / "data" / "market_intel_db.xlsx"
    if args.apply:
        db = MarketIntelDB(path)
    else:
        tmp = Path(tempfile.mkdtemp()) / "dry.xlsx"
        shutil.copy(path, tmp)
        db = MarketIntelDB(tmp)
    report = db.append_sec_status(dets)
    print(f"appended {len(report['appended'])}: {report['appended']}")
    print(f"superseded {report['superseded']}")
    for n in report["noop"]:
        print(f"  no-op {n}")
    if args.apply:
        if report["appended"]:
            backup_workbook(path)
            db.save()
            print("saved market_intel_db.xlsx")
        else:
            print("nothing to write")
    else:
        print("DRY RUN (on a temporary copy) -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
