#!/usr/bin/env python3
"""
Populate `Coherence_Pilot_Runs` -- the first falsification test of the coherence framework.

    python scripts/coherence_pilot.py            # report only
    python scripts/coherence_pilot.py --apply

Build handoff 2026-09-08 §3. The hypothesis is fixed: `systems_integration` over-firing
correlates with COH-F tag(s). This script only assembles the COHORT; it writes no tags and
reads no framework taxonomy, so it runs before the seed data lands.

POPULATION LOGIC, exactly as specified
--------------------------------------
* `over_firing`: companies whose `systems_integration` observations number >= 3, over all
  history, no trailing window.
* `comparison`: the same number of companies, each matched to one over-firing company by
  CLOSEST TOTAL observation count (all evidence, not just systems_integration) among
  companies that do not clear the threshold.

Three judgment calls the handoff leaves open, made here and stated on every row's
`hypothesis`-adjacent provenance in the report rather than silently:

1. WHICH OBSERVATIONS COUNT. All released rows carrying `topic = systems_integration`,
   regardless of grade. The hypothesis is about OVER-firing, and the low-grade tier is
   precisely where over-firing shows up -- excluding it would remove the phenomenon under
   test. 36 of the 38 systems_integration rows in the base are low-grade.
2. WHETHER PROVIDERS ARE ELIGIBLE. Moot in fact and so decided by the data: no
   `provider_benchmark` company clears the threshold, and none is near enough to be a
   nearest match. The pool is restricted to buyers anyway, because a provider's evidence
   profile (seller service pages only) makes "closest total observation count" a
   meaningless pairing.
3. TIE-BREAKING. Closest absolute difference in total count, then lowest company_id, and a
   comparison company is never used twice. Deterministic and re-runnable.

The pilot's success criterion is exploratory (>= 60% of the over-firing cohort sharing a
COH-F candidate at synthesis, visibly above the comparison cohort). No significance test is
computed here or anywhere: the handoff says explicitly not to build one.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import MarketIntelDB, today  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

PILOT_ID = "COHP-0001"
HYPOTHESIS = "systems_integration over-firing correlates with COH-F tag(s)"
FRAMEWORK_VERSION = "v0.1"
THEME = "systems_integration"
OVER_FIRING_FLOOR = 3
COLUMNS = ["pilot_id", "hypothesis", "company_id", "cohort", "systems_integration_count",
           "matched_to_company_id", "included_at", "framework_version"]


def cohorts(db_path: Path):
    wb = openpyxl.load_workbook(db_path, read_only=True, data_only=True)

    def rows(sheet):
        it = wb[sheet].iter_rows(values_only=True)
        head = list(next(it))
        return [dict(zip(head, r)) for r in it if r and r[0]]

    companies = {str(c["company_id"]): c for c in rows("Companies")}
    buyers = {cid for cid, c in companies.items()
              if str(c.get("qualification_status")) != "provider_benchmark"}
    obs = [o for o in rows("Observations")
           if str(o.get("publication_state")) == "released"]

    si = collections.Counter(str(o["company_id"]) for o in obs if str(o["topic"]) == THEME)
    total = collections.Counter(str(o["company_id"]) for o in obs)

    over = sorted((c for c in buyers if si[c] >= OVER_FIRING_FLOOR),
                  key=lambda c: (-si[c], c))
    pool = sorted(c for c in buyers if si[c] < OVER_FIRING_FLOOR and total[c] > 0)

    pairs, used = [], set()
    for cid in over:
        target = total[cid]
        best = min((c for c in pool if c not in used),
                   key=lambda c: (abs(total[c] - target), c), default=None)
        if best is None:
            break
        used.add(best)
        pairs.append((cid, best))
    return companies, si, total, pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "market_intel_db.xlsx"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = Path(args.db)
    companies, si, total, pairs = cohorts(path)

    print(f"{PILOT_ID}: {HYPOTHESIS}")
    print(f"  over-firing floor: {THEME} >= {OVER_FIRING_FLOOR}, all history, released rows\n")
    print(f"  {'cohort':<12} {'id':<6} {'company':<34} {'si':>3} {'total':>5}  matched to")
    print(f"  {'-'*12} {'-'*6} {'-'*34} {'-'*3} {'-'*5}  {'-'*10}")
    out = []
    for over_cid, comp_cid in pairs:
        for cid, cohort, match in ((over_cid, "over_firing", None),
                                   (comp_cid, "comparison", over_cid)):
            name = str(companies[cid]["canonical_name"])
            print(f"  {cohort:<12} {cid:<6} {name[:34]:<34} {si[cid]:>3} {total[cid]:>5}  "
                  f"{match or ''}")
            out.append({"pilot_id": PILOT_ID, "hypothesis": HYPOTHESIS, "company_id": cid,
                        "cohort": cohort, "systems_integration_count": si[cid],
                        "matched_to_company_id": match, "included_at": today(),
                        "framework_version": FRAMEWORK_VERSION})
    print(f"\n  {len(pairs)} pair(s), {len(out)} row(s)")

    if not args.apply:
        print("\n  DRY RUN -- nothing written. Re-run with --apply.")
        return 0

    db = MarketIntelDB(path)
    ws = db.wb["Coherence_Pilot_Runs"]
    headers = [ws.cell(1, c).value for c in range(1, len(COLUMNS) + 1)]
    if headers != COLUMNS:
        print(f"ABORT: Coherence_Pilot_Runs header drift.\n  expected {COLUMNS}\n  actual   {headers}")
        return 1
    existing = {(str(ws.cell(r, 1).value), str(ws.cell(r, 3).value))
                for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value}
    fresh = [r for r in out if (r["pilot_id"], r["company_id"]) not in existing]
    if not fresh:
        print("\n  every row already present -- nothing appended")
        return 0
    b, _ = backup_workbook(path)
    for r in fresh:
        ws.append([r[c] for c in COLUMNS])
    db.save()
    print(f"\n  appended {len(fresh)} row(s); backup {b.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
