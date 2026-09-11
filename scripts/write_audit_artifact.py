#!/usr/bin/env python3
"""
Write an audit artifact from judged verdicts.

Takes a verdicts JSON, applies the stop rule via `core/audit.py`, and writes
`harness_output/audits/<harness_id>__<harness_version>.json`. The artifact is what
`validate_repo_db.py` check 9 looks for; without one, a run's coverage number cannot
publish.

The verdicts file is authored by whoever did the judging -- this script does not judge.
Shape:

  {
    "harness_id": "...", "harness_version": "...", "run_id": "...",
    "auditor": "...", "population_size": 87,
    "strata": [{"stratum_id": "...", "selection_rule": "...", "sampled_n": 4,
                "population_n": 4,
                "verdict_counts": {"supported": 4, "overgraded": 0,
                                   "unsupported": 0, "wrong_entity": 0}}],
    "random_control": {"sampled_n": 30, "population_n": 87,
                       "verdict_counts": {...}},
    "row_ids_sampled": ["O00316", ...],
    "per_row_notes": [...],            optional
    "summary_md": "...",               optional
    "defect_introduced_in": "v1.2"     optional -- narrows the reprocessing blast radius
  }

    python scripts/write_audit_artifact.py verdicts.json
    python scripts/write_audit_artifact.py verdicts.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import audit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verdicts")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))

    def counts(d):
        base = {v: 0 for v in audit.VERDICTS}
        base.update(d or {})
        return base

    strata = [audit.Stratum(stratum_id=s["stratum_id"],
                            selection_rule=s["selection_rule"],
                            sampled_n=s["sampled_n"],
                            population_n=s.get("population_n"),
                            verdict_counts=counts(s.get("verdict_counts")))
              for s in data["strata"]]
    rc = data["random_control"]
    control = audit.RandomControl(sampled_n=rc["sampled_n"],
                                  population_n=rc["population_n"],
                                  verdict_counts=counts(rc.get("verdict_counts")))

    art = audit.AuditArtifact(
        harness_id=data["harness_id"], harness_version=data["harness_version"],
        run_id=data["run_id"], auditor=data["auditor"],
        population_size=data["population_size"], strata=strata, random_control=control,
        row_ids_sampled=data.get("row_ids_sampled", []),
        per_row_notes=data.get("per_row_notes", []),
        summary_md=data.get("summary_md", ""),
        defect_introduced_in=data.get("defect_introduced_in", ""),
    ).evaluate()

    payload = art.to_dict()
    problems = audit.validate_artifact(payload)
    if problems:
        print("ARTIFACT INVALID:")
        for p in problems:
            print(f"  !!  {p}")
        return 1

    print(f"{art.harness_id} {art.harness_version}")
    print(f"  population      {art.population_size}")
    print(f"  random control  {control.sampled_n} of {control.population_n} "
          f"-- precision {control.precision_rate:.1%}, "
          f"exclusions {control.exclusion_rate:.1%} "
          f"(threshold {art.threshold_applied:.1%})")
    for s in strata:
        print(f"  stratum {s.stratum_id:22s} n={s.sampled_n:<3d} "
              f"{dict(s.verdict_counts)}")
    print(f"  VERDICT: {art.verdict.upper()}")
    for t in art.stop_rule_triggered:
        print(f"    stop rule: {t}")
    print(f"  disposition: {art.disposition}")

    reproc = audit.derive_reprocessing_required(
        art.harness_id, {**audit.load_artifacts(),
                         (art.harness_id, art.harness_version): payload})
    if reproc:
        print(f"  reprocessing_required: {reproc['reason']}")
        print(f"    blast radius: {reproc['blast_radius']}")

    if args.dry_run:
        print("\n  DRY RUN -- nothing written.")
        return 0
    path = art.write()
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
