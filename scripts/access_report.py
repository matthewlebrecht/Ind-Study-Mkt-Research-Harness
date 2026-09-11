#!/usr/bin/env python3
"""
The three states `access_blocked` was holding, counted separately.

    python scripts/access_report.py

Signal Advisor's data-hygiene finding, 2026-09-01. One flag stood for three conditions
that mean different things about the world and route to different fixes:

  source_refusal   the source's own published decision. Not recoverable by us, and the
                   ONLY one that belongs in an ACCESS_BOUNDED count.
  rate_limited     a throughput ceiling. Recoverable by pacing, so counting it as an
                   access bound overstates what is unreachable.
  egress_blocked   our network or trust store. Says nothing about the source at all.

Counted over EVERY attempt row, not just `access_blocked` ones. That matters: the 429s
live under `source_unavailable` by the session-4 ruling that a rate limit is the source
being unavailable, so scoping this report to one failure_category would have found no rate
limits and concluded the flag was already clean.

Rows the classifier cannot place are listed as UNCLASSIFIED rather than defaulted into a
bucket. Defaulting them would inflate the one count that is supposed to be a citable claim
about a source.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.attempts import (ACCESS_CLASSES, access_classes_present,  # noqa: E402
                           classify_access)

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"

# Categories whose rows describe an access condition at all. Everything else -- a parse
# failure, an entity-resolution refusal -- is a different kind of gap and is out of scope
# here rather than silently counted as unclassified.
ACCESS_CATEGORIES = {"access_blocked", "source_unavailable", "js_rendered_unreachable"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--show-unclassified", action="store_true")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.db, read_only=True, data_only=True)
    ws = wb["Attempts"]
    it = ws.iter_rows(values_only=True)
    headers = list(next(it))
    rows = [dict(zip(headers, r)) for r in it if r and any(v is not None for v in r)]

    scoped = [a for a in rows
              if str(a.get("failure_category") or "") in ACCESS_CATEGORIES]

    by_class: dict[str, list] = defaultdict(list)
    for a in scoped:
        by_class[classify_access(a.get("failure_detail")) or "UNCLASSIFIED"].append(a)

    print(f"ACCESS FAILURES BY CLASS — {len(scoped)} row(s) across "
          f"{len(rows)} attempts")
    print("=" * 78)
    for cls in ACCESS_CLASSES + ("UNCLASSIFIED",):
        group = by_class.get(cls, [])
        print(f"\n{cls.upper()}  —  {len(group)} row(s)")
        if not group:
            print("    (none)")
            continue
        tally = Counter((str(a.get("harness_id")), str(a.get("harness_version")),
                         str(a.get("failure_category"))) for a in group)
        for (hid, ver, cat), n in sorted(tally.items(), key=lambda t: -t[1]):
            print(f"    {n:>4}  {hid:<21} {ver:<6} failure_category={cat}")
        # Convention 7: a fact the primary classification subsumes is reported, not
        # dropped. A source refusal that ALSO records a rate limit is a different
        # statement from one that does not.
        co = Counter(access_classes_present(a.get("failure_detail")) for a in group)
        multi = {k: v for k, v in co.items() if len(k) > 1}
        for combo, n in sorted(multi.items(), key=lambda t: -t[1]):
            print(f"          of which {n} also record: "
                  f"{', '.join(c for c in combo[1:])}")

    print()
    print("-" * 78)
    refusals = by_class.get("source_refusal", [])
    bounded = len(refusals)
    # Attempts is append-only (convention 24), so re-running a harness logs the same
    # refusal again: three H-JOBPOST-01 runs on 2026-09-01 turned 107 blocked companies
    # into 321 rows. The raw row count is the right denominator for "how much of the
    # attempt log is access failure" and the WRONG one for "how much of the universe is
    # access-bounded", which is a question about companies, not executions.
    distinct = {(str(a.get("harness_id")), str(a.get("company_id")),
                 str(a.get("attempted_signal"))) for a in refusals}
    companies = {c for _, c, _ in distinct}
    print(f"ACCESS_BOUNDED, raw attempt rows:            {bounded}")
    print(f"  distinct (harness, company, signal):      {len(distinct)}  "
          f"<- the quotable figure; re-runs do not inflate it")
    print(f"  distinct companies affected:              {len(companies)}")
    print(f"  excluded from that count: "
          f"{len(by_class.get('rate_limited', []))} rate-limited (recoverable by pacing), "
          f"{len(by_class.get('egress_blocked', []))} egress-blocked (our config), "
          f"{len(by_class.get('UNCLASSIFIED', []))} unclassified (not defaulted)")

    if args.show_unclassified:
        print()
        print("UNCLASSIFIED rows — the classifier refused rather than guessing:")
        seen = Counter()
        for a in by_class.get("UNCLASSIFIED", []):
            seen[(str(a.get("harness_id")), str(a.get("failure_detail"))[:100])] += 1
        for (hid, detail), n in sorted(seen.items(), key=lambda t: -t[1]):
            print(f"  {n:>4}  {hid}")
            print(f"        {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
