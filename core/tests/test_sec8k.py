#!/usr/bin/env python3
"""
H-SEC8K-01, tested against the requirement: exact Item 1.05 codes, the rule's effective date,
CIKs read from the status table, and a scope that is derived from SEC reporting status rows.

    python core/tests/test_sec8k.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_sec8k_01 import harness as H  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def row(i, cid, status, asof, ref, sup=None):
    return {"id": f"SRS-{i:04d}", "company_id": cid, "sec_reporting_status": status, "source_filing_type": "10-Q",
            "source_reference": ref, "as_of_date": asof, "determined_at": "2026-09-13", "determined_by": "t",
            "superseded_by": sup, "notes": ""}


def main() -> int:
    print("1. item codes are matched exactly")
    check("'1.05,9.01' carries Item 1.05", H.has_item("1.05,9.01"))
    check("'1.01' does not", not H.has_item("1.01"))
    check("'11.05' is not 1.05 (no substring match)", not H.has_item("11.05,9.01"))
    check("an empty item list does not", not H.has_item(None) and not H.has_item(""))

    print("2. the rule's effective date and the forms")
    filings = [{"form": "8-K", "filingDate": "2023-12-17", "items": "1.05", "accessionNumber": "a"},
               {"form": "8-K", "filingDate": "2024-02-01", "items": "1.05,9.01", "accessionNumber": "b"},
               {"form": "8-K/A", "filingDate": "2024-03-01", "items": "1.05", "accessionNumber": "c"},
               {"form": "10-Q", "filingDate": "2024-03-01", "items": "1.05", "accessionNumber": "d"},
               {"form": "8-K", "filingDate": "2024-04-01", "items": "2.02,9.01", "accessionNumber": "e"}]
    got = [f["accessionNumber"] for f in H.item105_filings(filings)]
    check("only 8-K / 8-K/A with Item 1.05 on or after 2023-12-18 count", got == ["b", "c"])
    check("older index pages are needed when the recent list starts after the rule date",
          H.needs_older_pages([{"filingDate": "2024-06-01"}]) and not H.needs_older_pages([{"filingDate": "2011-04-20"}]))
    block = {"form": ["8-K", "4"], "filingDate": ["2024-01-02", "2024-01-03"], "items": ["1.05", ""],
             "accessionNumber": ["x", "y"], "primaryDocument": ["d.htm", "f.xml"], "reportDate": ["", ""]}
    check("a submissions block becomes one dict per filing", len(H.rows_of(block)) == 2 and H.rows_of(block)[0]["items"] == "1.05")

    print("3. scope is derived from reporting-status rows, never a stored flag")
    rows = [row(1, "A030", "active_reporter", "2026-07-30", "EDGAR CIK 0000856982 MERIT MEDICAL SYSTEMS INC; 10-Q"),
            row(2, "A011", "active_reporter", "2013-11-12", "EDGAR CIK 0001393744 EnergySolutions, Inc.; 10-Q", sup="SRS-0003"),
            row(3, "A011", "deregistered", "2014-01-27", "EDGAR CIK 0001393744 EnergySolutions, Inc.; 15-15D"),
            row(4, "A094", "entity_unresolved", "2021-03-10", "EDGAR CIK 0001737580 Lynden USA Inc.; S-3")]
    scope = H.scoped_companies(rows)
    check("only current active reporters are scoped (a superseded active_reporter row is not)",
          [s["company_id"] for s in scope] == ["A030"])
    check("the CIK comes from the status row's source_reference", scope[0]["cik"] == "856982")
    check("identity doubt (entity_unresolved) is never in scope", "A094" not in [s["company_id"] for s in scope])
    check("cik_of reads zero-padded CIKs and returns None without one",
          H.cik_of("EDGAR CIK 0001692415 Co-Diagnostics") == "1692415" and H.cik_of("no reference") is None)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
