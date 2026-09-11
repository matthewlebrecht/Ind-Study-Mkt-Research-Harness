#!/usr/bin/env python3
"""
The careers-page readability denominator for H-JOBPOST-01, measured from `Attempts`.

    python scripts/careers_readability.py            # latest H-JOBPOST-01 run
    python scripts/careers_readability.py --run HR-0036

WHY THIS EXISTS
---------------
Signal Advisor's condition on the four 2026-09-02 signal keys (cloud, cybersecurity,
workforce enablement, OT modernization): PRESENCE evidence from H-JOBPOST-01 is
admissible immediately, ABSENCE is not, until the fraction of the buyer universe whose
own-domain careers pages are actually readable is known. That fraction gates four absence
legs now, not one, so it is measured here from the run's own attempt records rather than
estimated -- the same principle as the H-FMCSA-01 population map: coverage is a measured
structural denominator, not a guess.

What "readable" means: the own-domain leg (`attempted_signal = job_posting`) reached a
careers page AND parsed at least one posting through a known ATS adapter. Everything else
is a company whose postings this harness structurally cannot see, split by why, because
the splits have different fixes (a JS renderer for one bucket, an adapter for another,
discovery for a third) and different biases (a company on a modern hosted ATS is not a
random draw from the universe).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"
HARNESS = "H-JOBPOST-01"
OWN_LEG = "job_posting"

# Order matters: first match wins. Each bucket names the structural reason and its fix class.
BUCKETS = [
    ("readable: postings parsed through a known ATS adapter",
     lambda o, d: o == "covered"),
    ("careers page found; no ATS detectable in server-rendered HTML (JS-rendered or bespoke)",
     lambda o, d: "none detected in server-rendered" in d),
    ("careers page found; known ATS with no adapter",
     lambda o, d: re.search(r"ATS \((\w+)\) has no", d) is not None),
    ("known ATS adapter parsed 0 postings",
     lambda o, d: "parsed 0 postings" in d),
    ("no careers page found on own domain",
     lambda o, d: "no careers page found" in d),
    ("ATS adapter HTTP failure",
     lambda o, d: "adapter failed" in d),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--run", help="run_id to measure (default: the harness's latest run)")
    args = ap.parse_args()

    ws = openpyxl.load_workbook(args.db, read_only=True)["Attempts"]
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows)
    att = [dict(zip(hdr, r)) for r in rows if r and r[0]]
    mine = [a for a in att if a["harness_id"] == HARNESS and a["attempted_signal"] == OWN_LEG]
    if not mine:
        raise SystemExit(f"no {HARNESS} own-domain attempts in Attempts")
    run = args.run or max(a["run_id"] for a in mine)
    leg = [a for a in mine if a["run_id"] == run]
    if not leg:
        raise SystemExit(f"no {HARNESS} own-domain attempts for run {run}")

    counts: Counter = Counter()
    ats_gap: Counter = Counter()
    other = []
    for a in leg:
        o, d = str(a.get("outcome") or ""), str(a.get("failure_detail") or "")
        for label, test in BUCKETS:
            if test(o, d):
                counts[label] += 1
                if label.startswith("careers page found; known ATS"):
                    ats_gap[re.search(r"ATS \((\w+)\)", d).group(1)] += 1
                break
        else:
            other.append((a["company_id"], o, d[:80]))
    n = len(leg)
    readable = counts.get(BUCKETS[0][0], 0)

    print(f"{HARNESS} own-domain careers-page readability, run {run} "
          f"({n} companies, version {leg[0].get('harness_version')})\n")
    for label, _ in BUCKETS:
        c = counts.get(label, 0)
        if c:
            print(f"  {c:4d}  {c / n:6.1%}  {label}")
    for cid, o, d in other:
        print(f"     1  {1 / n:6.1%}  other: {cid} {o} {d}")
    if ats_gap:
        print("\n  known ATS without an adapter, by product: "
              + ", ".join(f"{k} {v}" for k, v in ats_gap.most_common()))
    print(f"\n  READABLE DENOMINATOR: {readable} of {n} = {readable / n:.1%}")
    print(f"  {n - readable} of {n} ({(n - readable) / n:.0%}) are companies whose postings this "
          f"harness structurally cannot see.")
    print("\n  Consequence: a hiring signal that is PRESENT is evidence. A hiring signal that is\n"
          "  ABSENT is uninformative for the unreadable share, and the readable share is not a\n"
          "  random draw (it is the companies on a modern hosted ATS), so absence across the\n"
          "  readable share does not generalise either. No absence claim from any H-JOBPOST-01\n"
          "  key until this denominator is accepted (Signal Advisor, 2026-09-02, condition 1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
