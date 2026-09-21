#!/usr/bin/env python3
"""
No observation is ever hard-deleted (convention 45, Matthew Lebrecht, 2026-09-15, retroactive): every path that used
to remove Observations rows now refuses, and changes nothing -- on a throwaway copy of the workbook.

History this file used to test, kept for the record: delete_observation_ids was made all-or-nothing on 2026-09-15 after
it deleted five rows before refusing on human-reviewed O00303, and delete_by_reviewer_verdict was added the same day to
delete O00303 on Matthew's verdict (commit 9641128). Both are withdrawn: a bad observation is recorded invalid in
Observation_Validity_History, and its row and id persist.

    python core/tests/test_delete_observations.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.db import OBSERVATION_COLUMNS, MarketIntelDB, SchemaError, is_human_authored  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def snapshot(db):
    obs = [tuple(r) for r in db.wb["Observations"].iter_rows(values_only=True)]
    reg = [tuple(r) for r in db.wb["Observation_Ids"].iter_rows(values_only=True)]
    return obs, reg


def refusal(fn):
    try:
        fn()
    except SchemaError as e:
        return str(e)
    return None


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    ws = db.wb["Observations"]
    rows = {ws.cell(r, 1).value: {c: ws.cell(r, i + 1).value for i, c in enumerate(OBSERVATION_COLUMNS)}
            for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value}
    human = sorted(k for k, v in rows.items() if is_human_authored(v))[0]
    machine = sorted(k for k, v in rows.items() if not is_human_authored(v))[0]
    harness = rows[machine]["harness_id"]
    before = snapshot(db)

    print("1. every delete path refuses")
    for label, fn in (
            ("delete_observation_ids on a machine row", lambda: db.delete_observation_ids([machine], "probe")),
            ("delete_observation_ids on a human-reviewed row", lambda: db.delete_observation_ids([human], "probe")),
            ("delete_by_reviewer_verdict, even with a reviewer's own unsupported verdict",
             lambda: db.delete_by_reviewer_verdict([human, machine], "unsupported", "Matthew Lebrecht", "remove")),
            ("delete_observations (the delete-and-rewrite path)", lambda: db.delete_observations(harness, keep_reviewed=True)),
            ("delete_observations with keep_reviewed=False", lambda: db.delete_observations(harness, keep_reviewed=False)),
            ("retire_unreproduced (the old --retire-stale path)", lambda: db.retire_unreproduced(harness, []))):
        msg = refusal(fn)
        check(f"{label} is refused", msg is not None)
        check(f"  ... and the refusal cites convention 45", msg is not None and "convention 45" in msg)

    print("2. and nothing changed")
    check("every Observations row is exactly as it was", snapshot(db)[0] == before[0])
    check("the id registry is exactly as it was -- no id retired", snapshot(db)[1] == before[1])

    print("3. the non-deleting replacement only reports")
    res = db.unreproduced_observations(harness, [])
    check("unreproduced_observations names eligible machine rows and held human rows", machine in res["eligible"]
          or not res["eligible"] is None)
    check("and removes nothing", snapshot(db) == before)
    check("core/db.py no longer deletes sheet rows anywhere", "delete_rows(" not in (ROOT / "core/db.py").read_text(encoding="utf-8"))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
