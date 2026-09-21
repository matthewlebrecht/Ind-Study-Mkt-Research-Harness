#!/usr/bin/env python3
"""
H-FIRSTPARTY-01 --retire-stale, under convention 45: rows the harness no longer produces are RECORDED INVALID -- the
row and its id persist -- human-reviewed rows are held, and nothing happens unless the run opts in. Since v1.3 the
status names the REASON (`invalidated_extraction_defect`, Matthew Lebrecht 2026-09-15, item 22): v1.2 classified the
whole page, v1.3 reads the article body, so a claim it stops producing from a page it re-read matched page furniture.
On a throwaway copy of the workbook.

History: built 2026-09-15 as a retirement that deleted rows (commit b21a24c, never used); converted the same day when
Matthew made the no-hard-deletion rule retroactive and ruled that retirement becomes an invalidation status.

    python core/tests/test_firstparty_retire.py
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import validity as V  # noqa: E402
from core.db import OBSERVATION_COLUMNS, MarketIntelDB, Observation, is_human_authored  # noqa: E402
from harnesses.h_firstparty_01 import harness as fp  # noqa: E402

PASS = FAIL = 0
DRY_RUN_HUMAN = ["O00303", "O00326", "O00342", "O00415", "O00424", "O00443", "O00445", "O00446", "O00463",
                 "O00470", "O00476", "O00492", "O00511", "O00523", "O00526", "O00538", "O00539", "O00555",
                 "O00561"]


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def fresh():
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    if V.SHEET in db.wb.sheetnames:
        del db.wb[V.SHEET]
    db.wb.create_sheet(V.SHEET).append(V.COLUMNS)
    return db


def obs_rows(db, harness="H-FIRSTPARTY-01"):
    ws = db.wb["Observations"]
    out = {}
    for r in range(2, ws.max_row + 1):
        v = {c: ws.cell(r, i + 1).value for i, c in enumerate(OBSERVATION_COLUMNS)}
        if v["observation_id"] and v["harness_id"] == harness:
            out[v["observation_id"]] = v
    return out


def set_cell(db, oid, col, value):
    ws = db.wb["Observations"]
    r = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == oid)
    ws.cell(r, OBSERVATION_COLUMNS.index(col) + 1).value = value


def proposal(v):
    names = {f.name for f in fields(Observation)}
    d = {k: val for k, val in v.items() if k in names}
    for k in ("publication_date", "retrieval_date", "evidence_excerpt", "reviewer_notes", "audit_verdict"):
        d[k] = "" if d.get(k) is None else str(d[k])
    return Observation(**d)


def refused(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def current(db):
    return V.current_rows(V.rows_from_sheet(db.wb[V.SHEET]))


def main() -> int:
    print("1. opt-in, and never over a subset")
    p = fp.build_parser()
    check("off unless --retire-stale is given", p.parse_args([]).retire_stale is False)
    check("--retire-stale turns it on", p.parse_args(["--retire-stale"]).retire_stale is True)
    check("refused with --companies", refused(lambda: fp.check_retire_args(p.parse_args(["--retire-stale", "--companies", "A001"]))))
    check("refused with --limit", refused(lambda: fp.check_retire_args(p.parse_args(["--retire-stale", "--limit", "5"]))))
    check("a subset run without the flag is allowed", not refused(lambda: fp.check_retire_args(p.parse_args(["--companies", "A001"]))))
    src = (ROOT / "harnesses/h_firstparty_01/harness.py").read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(r"= retire_stale\(db,", src)]
    check("main calls it in exactly one place, under `if args.retire_stale:`",
          len(calls) == 1 and "if args.retire_stale:" in src[max(0, calls[0] - 120):calls[0]])
    check("the harness no longer calls a deleting path", "retire_unreproduced" not in src and "delete_observation" not in src)

    db = fresh()
    rows = obs_rows(db)
    machine = [v for v in rows.values() if not is_human_authored(v)]
    human = [v for v in rows.values() if is_human_authored(v)]
    a, h = machine[0], human[0]
    e = next(v for v in machine if v["source_url"] not in (a["source_url"], h["source_url"]))
    d = next(v for v in machine if v["observation_id"] not in {a["observation_id"], e["observation_id"]}
             and v["source_url"] not in (a["source_url"], h["source_url"], e["source_url"]))
    in_scope = {a["company_id"], h["company_id"], d["company_id"], e["company_id"]}
    f = next(v for v in machine if v["company_id"] not in in_scope
             and v["source_url"] not in (a["source_url"], h["source_url"], e["source_url"], d["source_url"]))
    set_cell(db, d["observation_id"], "review_status", "accepted")
    gone = {x["observation_id"] for x in (a, h, d, e, f)}
    proposed = [proposal(v) for v in rows.values() if v["observation_id"] not in gone]
    read = {a["source_url"], h["source_url"], d["source_url"], f["source_url"]}
    n_before = db.wb["Observations"].max_row
    res = fp.retire_stale(db, proposed, in_scope, read)
    after = obs_rows(db)
    cur = current(db)

    print("2. a machine row that stops being produced from a re-read page is recorded invalid -- and kept")
    check(f"{a['observation_id']} is invalidated", res["invalidated"] == [a["observation_id"]])
    check("its row is still there, unchanged", after[a["observation_id"]] == a)
    check("no Observations row was removed", db.wb["Observations"].max_row == n_before)
    check("its current determination is invalidated_extraction_defect, naming the harness, the version and the reason",
          cur[a["observation_id"]]["validity_status"] == "invalidated_extraction_defect"
          and "H-FIRSTPARTY-01 v" in cur[a["observation_id"]]["basis"]
          and "ARTICLE BODY" in cur[a["observation_id"]]["basis"])

    print("3. a human-reviewed row in the same position is HELD, never invalidated")
    check(f"{h['observation_id']} is held and has no determination", h["observation_id"] in res["held"] and h["observation_id"] not in cur)
    check(f"{d['observation_id']}, human by review_status alone, is held too", d["observation_id"] in res["held"] and d["observation_id"] not in cur)

    print("4. rows the run had no evidence about are left alone")
    check(f"{e['observation_id']}: page not re-read -> no determination", e["observation_id"] not in cur and e["observation_id"] not in res["held"])
    check(f"{f['observation_id']}: company out of scope -> no determination", f["observation_id"] not in cur)

    print("5. re-running the same version writes nothing twice")
    res2 = fp.retire_stale(db, proposed, in_scope, read)
    check("the already-invalid row is reported, not re-determined", res2["invalidated"] == [] and a["observation_id"] in res2["already_invalid"])
    check("still exactly one determination", len(V.rows_from_sheet(db.wb[V.SHEET])) == 1)

    print("6. every human-reviewed FIRSTPARTY row is held when nothing is produced and every page re-read")
    db2 = fresh()
    rows2 = obs_rows(db2)
    res3 = fp.retire_stale(db2, [], {v["company_id"] for v in rows2.values()}, {v["source_url"] for v in rows2.values()})
    humans = {k for k, v in rows2.items() if is_human_authored(v)}
    live_dry = [x for x in DRY_RUN_HUMAN if x in rows2]
    check(f"all {len(humans)} human-reviewed rows held, none invalidated",
          set(res3["held"]) == humans and not humans & set(res3["invalidated"]))
    check(f"including all {len(live_dry)} human rows the body-only dry run flagged", set(live_dry) <= set(res3["held"]))
    check("no row removed", len(obs_rows(db2)) == len(rows2))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
