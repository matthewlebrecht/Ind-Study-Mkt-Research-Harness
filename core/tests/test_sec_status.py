#!/usr/bin/env python3
"""
SEC reporting status history: the append-only mechanics and the derived reader, tested against
the Harness Advisor design (session 17 wrap-up brief) on a throwaway copy of the workbook.

    python core/tests/test_sec_status.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import sec_status as S  # noqa: E402
from core.db import MarketIntelDB, SchemaError  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def det(cid, status, asof, ref="EDGAR CIK 0000000001 X; Form D filed", ftype="D", notes="n"):
    return {"company_id": cid, "sec_reporting_status": status, "source_filing_type": ftype,
            "source_reference": ref, "as_of_date": asof, "determined_by": "test", "notes": notes}


def raises(fn):
    try:
        fn()
    except SchemaError:
        return True
    return False


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    if S.SHEET in db.wb.sheetnames:
        del db.wb[S.SHEET]
    ws = db.wb.create_sheet(S.SHEET)
    ws.append(S.COLUMNS)

    print("1. vocabulary and the two doubts")
    check("exactly the eight designed values", list(S.STATUSES) == [
        "active_reporter", "form_d_only", "withdrawn_registration", "never_registered",
        "insider_only", "deregistered", "entity_unresolved", "status_uncertain"])
    check("entity_unresolved without an identity note is refused",
          any("identity" in p for p in S.problems_with(det("A094", "entity_unresolved", "2021-03-10", notes=""))))
    check("status_uncertain without a CIK is refused (a doubted filer is entity_unresolved, not status_uncertain)",
          any("CIK" in p for p in S.problems_with(det("A094", "status_uncertain", "2021-03-10", ref="some filer"))))
    check("status_uncertain with a confirmed CIK and a note is accepted",
          not S.problems_with(det("A094", "status_uncertain", "2021-03-10", ref="EDGAR CIK 0001737580 X")))
    check("identity_confirmed is False only for entity_unresolved",
          S.identity_confirmed("entity_unresolved") is False and S.identity_confirmed("status_uncertain") is True
          and S.identity_confirmed(None) is None)
    check("never_registered needs a note saying what was checked",
          any("checked" in p for p in S.problems_with(det("A001", "never_registered", "2026-09-13", ftype="", notes=""))))
    check("as_of_date must be an ISO evidence date", any("as_of_date" in p for p in S.problems_with(det("A001", "form_d_only", "09/13/2026"))))
    check("an unknown status is refused", any("not one of" in p for p in S.problems_with(det("A001", "public", "2026-09-13"))))

    print("2. append-only mechanics")
    r1 = db.append_sec_status([det("A011", "active_reporter", "2013-11-12", ref="EDGAR CIK 0001393744 10-Q", ftype="10-Q"),
                               det("A011", "deregistered", "2014-01-27", ref="EDGAR CIK 0001393744 15-15D", ftype="15-15D")])
    rows = db.sec_status_rows()
    check("a status change is two rows", len(r1["appended"]) == 2 and len(rows) == 2)
    hist = next(r for r in rows if r["sec_reporting_status"] == "active_reporter")
    check("the historical row keeps its as_of_date and gets superseded_by", hist["as_of_date"] == "2013-11-12"
          and hist["superseded_by"] == r1["appended"][1])
    check("the new row is independent (no superseded_by)",
          next(r for r in rows if r["sec_reporting_status"] == "deregistered")["superseded_by"] in (None, ""))
    r2 = db.append_sec_status([det("A011", "active_reporter", "2013-11-12", ref="EDGAR CIK 0001393744 10-Q", ftype="10-Q"),
                               det("A011", "deregistered", "2014-01-27", ref="EDGAR CIK 0001393744 15-15D", ftype="15-15D")])
    check("re-loading the same two rows writes nothing (identical rows are no-ops)",
          not r2["appended"] and len(db.sec_status_rows()) == 2)
    r3 = db.append_sec_status([det("A011", "deregistered", "2026-09-13", ref="EDGAR CIK 0001393744 no filings since 2014", ftype="15-15D")])
    check("re-confirming an unchanged current status is a no-op, even with a newer as_of_date",
          not r3["appended"] and "unchanged" in r3["noop"][0][2])
    check("an older determination cannot supersede a newer current row",
          raises(lambda: db.append_sec_status([det("A011", "form_d_only", "2010-01-01")])))
    check("a refused determination writes nothing", len(db.sec_status_rows()) == 2)

    print("3. the derived reader (no stored public/private flag)")
    db.append_sec_status([det("A030", "active_reporter", "2026-07-30", ref="EDGAR CIK 0000856982 10-Q", ftype="10-Q"),
                          det("A085", "form_d_only", "2013-09-20")])
    rows = db.sec_status_rows()
    check("active_reporters derives from the latest non-superseded row", S.active_reporters(rows) == ["A030"])
    check("a deregistered company with a historical active_reporter row is not a current reporter",
          "A011" not in S.active_reporters(rows) and S.current_status(rows, "A011") == "deregistered")
    check("a company never determined has no status (None), not a default",
          S.current_status(rows, "A001") is None)
    check("no Companies.public_private column exists", "public_private" not in
          [db.wb["Companies"].cell(1, c).value for c in range(1, db.wb["Companies"].max_column + 1)])

    print(f"\n{PASS} passed, {FAIL} failed (worked on {tmp})")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
