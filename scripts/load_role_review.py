#!/usr/bin/env python3
"""
Load a committed role-review verdicts artifact into Observation_Role_Reviews, in ONE batch.

The artifact is the record of what the reviewer said; the table is the same verdicts keyed by
observation (convention 44). Every row is built from the artifact alone -- verdict, role at
review, stratum and its coverage, the reviewer's words, the prepared note -- so the two cannot
disagree at load, and validate_repo_db check 14 keeps them from drifting afterwards.

Observations is NEVER written. The script snapshots every Observations cell before the batch and
refuses to save unless the sheet is identical afterwards: a role verdict re-clears neither identity
nor extraction, so it must not move review_source, review_status or anything else on the row.

    python scripts/load_role_review.py            # build + validate on a temporary copy
    python scripts/load_role_review.py --apply    # write (all or nothing); re-running is a no-op
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import role_review  # noqa: E402
from core.db import MarketIntelDB  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402

DEFAULT_ARTIFACT = "harness_output/audits/ROLE_REVIEW_buyer_articulates_2026-09-15_verdicts.json"


def rows_from_artifact(rel: str, root: Path = ROOT) -> list[dict]:
    art = json.loads((root / rel).read_text(encoding="utf-8"))
    strata = {(s["harness_id"], s["sub_stratum"]): s for s in art["strata"]}
    out = []
    for v in art["verdicts"]:
        s = strata[(v["harness_id"], v["sub_stratum"])]
        out.append({
            "observation_id": v["observation_id"], "role_at_review": v["role_at_review"],
            "role_verdict": v["role_verdict"], "review_scope": role_review.SCOPE,
            "reviewer": art["reviewer"], "review_source": art["review_source"],
            "reviewed_at": art["review_date"], "review_run_id": art["review_run_id"],
            "sample_design": art["sample_design"], "sample_n": art["sampled_n"],
            "population_n": art["population_n"],
            "stratum": f"{v['harness_id']} / {v['sub_stratum']}",
            "stratum_sampled_n": s["sampled_n"], "stratum_population_n": s["population_n"],
            "reviewer_words": v.get("reviewer_words") or "", "artifact": rel, "notes": v["note"],
        })
    return out


def observations_digest(wb) -> str:
    h = hashlib.sha256()
    for row in wb["Observations"].iter_rows(values_only=True):
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--artifact", default=DEFAULT_ARTIFACT)
    args = ap.parse_args()
    path = ROOT / "data" / "market_intel_db.xlsx"
    if args.apply:
        db = MarketIntelDB(path)
    else:
        tmp = Path(tempfile.mkdtemp()) / "dry.xlsx"
        shutil.copy(path, tmp)
        db = MarketIntelDB(tmp)
    rows = rows_from_artifact(args.artifact)
    before = observations_digest(db.wb)
    report = role_review.append_reviews(db.wb, rows, ROOT)
    if observations_digest(db.wb) != before:
        print("REFUSING: Observations changed while writing role reviews; nothing saved.")
        return 2
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["role_verdict"]] = counts.get(r["role_verdict"], 0) + 1
    print(f"batch {len(rows)} {counts} | appended {report['appended']} | already present {len(report['noop'])}")
    if args.apply and report["appended"]:
        backup_workbook(path)
        db.save()
        reloaded = MarketIntelDB(path)
        if observations_digest(reloaded.wb) != before:
            print("WARNING: Observations digest differs after save -- inspect before committing.")
            return 2
        print("saved market_intel_db.xlsx; Observations identical before and after")
    elif not args.apply:
        print("DRY RUN (temporary copy) -- re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
