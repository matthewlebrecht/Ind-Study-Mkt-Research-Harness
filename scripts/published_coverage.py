#!/usr/bin/env python3
"""
Coverage numbers that the audit gate permits to be published.

    python scripts/published_coverage.py
    python scripts/published_coverage.py --db data/market_intel_db.xlsx

WHY THIS IS A SEPARATE SCRIPT AND NOT A COLUMN
----------------------------------------------
`Harness_Runs.coverage_rate` is written by every run, audited or not. It is the run's own
arithmetic about itself and it is correct as far as it goes -- but convention 34 says a
quarantined run contributes NEITHER numerator NOR denominator to a published coverage
number, and a column cannot enforce that. Reading coverage straight off the sheet blends
audited and unaudited output into one figure, which is exactly the thing the gate exists
to prevent, and it does it silently because the numbers look fine.

So the gate's arithmetic lives here, applied on read:

  published   contributes. The version has an audit artifact whose verdict is `pass`, or
              it is grandfathered.
  quarantined contributes nothing, and is LISTED rather than dropped -- an exclusion
              nobody can see is indistinguishable from a harness that was never run
              (convention 5's lesson about denominators, applied to the gate).
  superseded  contributes nothing and needs no audit, because a later version re-ran the
              same scope and holds its output.

NO BLENDED FIGURE. There is deliberately no single project-wide coverage percentage here.
The harnesses have different denominators -- 108 companies, 12 providers, a 15-company
subset -- and different instrument biases (convention 21a), so one mean over all of them
would be a number with no referent. Per-version is the honest unit.

Coverage itself is recomputed from `Attempts` rather than read from the rollup column, on
the same principle that `check_run_ledger.py` compares against git: a figure derived from
the underlying rows can be checked, and a divergence from the stored rollup is reported
rather than hidden. Definition matches `core/attempts.py::rollups` exactly -- `scope =
scoped` rows only (convention 9), with `covered`, `absent_confirmed` and `partial` all
counting as coverage (convention 6: a confirmed absence is coverage, not a miss).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import audit  # noqa: E402
from core.attempts import COVERAGE_OUTCOMES, ROLLUP_STATUSES  # noqa: E402

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"


def rows(wb, name):
    ws = wb[name]
    it = ws.iter_rows(values_only=True)
    headers = list(next(it))
    return [dict(zip(headers, r)) for r in it if r and any(v is not None for v in r)]


def vkey(v: str) -> tuple:
    return tuple(int(p) for p in str(v).lstrip("v").split(".") if p.isdigit())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.db, read_only=True, data_only=True)
    runs = rows(wb, "Harness_Runs")
    attempts = rows(wb, "Attempts")
    obs = rows(wb, "Observations")
    # Signal_Types.status filters the denominator here exactly as core/attempts.py::rollups
    # does at write time -- the two definitions must not drift apart.
    st_status = {str(s.get("signal_type_name")): str(s.get("status") or "").strip()
                 for s in rows(wb, "Signal_Types")}

    artifacts = audit.load_artifacts()
    grandfathered = audit.load_grandfathered()

    by_run: dict[str, list] = {}
    for a in attempts:
        by_run.setdefault(str(a.get("run_id") or ""), []).append(a)

    published, quarantined, superseded = [], [], []
    for r in runs:
        hid = str(r.get("harness_id") or "")
        ver = str(r.get("version") or "")
        rid = str(r.get("harness_run_id") or "")
        status = str(r.get("publication_status") or "").strip().lower()
        scoped = [a for a in by_run.get(rid, []) if str(a.get("scope")) == "scoped"
                  and st_status.get(str(a.get("attempted_signal")), "active") in ROLLUP_STATUSES]
        covered = sum(1 for a in scoped if str(a.get("outcome")) in COVERAGE_OUTCOMES)
        rec = {
            "run_id": rid, "harness_id": hid, "version": ver,
            "scoped": len(scoped), "covered": covered,
            "rate": (covered / len(scoped)) if scoped else None,
            "stored": r.get("coverage_rate"),
            "obs": sum(1 for o in obs if str(o.get("harness_id")) == hid
                       and str(o.get("harness_version")) == ver),
            "audited": (hid, ver) in artifacts,
            "grandfathered": (hid, ver) in grandfathered,
        }
        {"published": published, "quarantined": quarantined,
         "superseded": superseded}.get(status, quarantined).append(rec)

    # Only the LATEST published version of a harness states that harness's coverage. An
    # older published version is superseded evidence, not a second opinion, and listing
    # both invites quoting whichever is higher.
    latest: dict[str, dict] = {}
    for rec in published:
        cur = latest.get(rec["harness_id"])
        if cur is None or vkey(rec["version"]) >= vkey(cur["version"]):
            latest[rec["harness_id"]] = rec

    print("PUBLISHED COVERAGE — released versions only")
    print("=" * 78)
    print(f"{'harness':<22} {'ver':<6} {'run':<8} {'scoped':>7} {'cov':>5} "
          f"{'rate':>7}  basis")
    print("-" * 78)
    divergences = []
    for hid in sorted(latest):
        rec = latest[hid]
        basis = "audited" if rec["audited"] else (
            "grandfathered" if rec["grandfathered"] else "NO ARTIFACT")
        rate = "n/a" if rec["rate"] is None else f"{rec['rate']:.1%}"
        print(f"{hid:<22} {rec['version']:<6} {rec['run_id']:<8} "
              f"{rec['scoped']:>7} {rec['covered']:>5} {rate:>7}  {basis}")
        if (rec["rate"] is not None and rec["stored"] is not None
                and abs(rec["rate"] - float(rec["stored"])) > 0.0001):
            divergences.append(
                f"{hid} {rec['version']}: recomputed {rec['rate']:.4f} vs stored "
                f"{float(rec['stored']):.4f}")

    # Compared on (harness, version), not on object identity: a version re-run twice has
    # two published rows, and identity comparison listed the second as "older than itself".
    quoted = {(r["harness_id"], r["version"]) for r in latest.values()}
    older = [r for r in published if (r["harness_id"], r["version"]) not in quoted]
    if older:
        print()
        print(f"  ({len(older)} older published version(s) not quoted above — a harness's "
              f"coverage is its latest")
        print(f"   published version, not the best of its history: "
              f"{', '.join(sorted(set(r['harness_id'] + ' ' + r['version'] for r in older)))})")

    if divergences:
        print()
        print("  RECOMPUTED COVERAGE DIVERGES FROM THE STORED ROLLUP:")
        for d in divergences:
            print(f"    !! {d}")

    print()
    print("EXCLUDED — contributes neither numerator nor denominator (convention 34)")
    print("-" * 78)
    for label, group in (("quarantined, awaiting audit", quarantined),
                         ("superseded by a later version", superseded)):
        if not group:
            continue
        print(f"  {label}:")
        for rec in sorted(group, key=lambda r: (r["harness_id"], r["version"])):
            rate = "n/a" if rec["rate"] is None else f"{rec['rate']:.1%}"
            print(f"    {rec['harness_id']:<22} {rec['version']:<6} {rec['run_id']:<8} "
                  f"{rec['obs']:>3} obs   (would be {rate}, NOT PUBLISHED)")
    if not quarantined and not superseded:
        print("  (none)")

    print()
    n_obs_released = sum(1 for o in obs
                         if str(o.get("publication_state")) == "released")
    n_obs_quar = sum(1 for o in obs
                     if str(o.get("publication_state")) == "quarantined")
    print(f"Observations: {n_obs_released} released, {n_obs_quar} quarantined "
          f"({len(obs)} total)")
    print("No blended project-wide figure is reported: the harnesses have different "
          "denominators")
    print("and different instrument biases (convention 21a), so a mean over them names "
          "nothing.")
    return 1 if divergences else 0


if __name__ == "__main__":
    raise SystemExit(main())
