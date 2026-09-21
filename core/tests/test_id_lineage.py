#!/usr/bin/env python3
"""
Id lineage (Matthew Lebrecht, 2026-09-15, item 20): every retired observation id whose claim is live under a newer id
records that id in Observation_Ids.current_id, so a claim's history is traceable across the pre-convention-43
renumbering; a live id records none; check 15 fails otherwise. On throwaway copies of the workbook.

    python core/tests/test_id_lineage.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import validity as V  # noqa: E402
from core.db import OBSERVATION_COLUMNS, OBSERVATION_ID_COLUMNS, MarketIntelDB, natural_key_of  # noqa: E402
from scripts import migrate_schema as M  # noqa: E402
from scripts import record_id_lineage as L  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def copy_db() -> tuple[Path, MarketIntelDB]:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    return tmp, MarketIntelDB(tmp)


def registry_rows(db) -> dict:
    ws = db.wb["Observation_Ids"]
    return {ws.cell(r, 1).value: {"row": r, **{c: ws.cell(r, i + 1).value for i, c in enumerate(OBSERVATION_ID_COLUMNS)}}
            for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value}


def set_current(db, oid, value):
    rec = registry_rows(db)[oid]
    db.wb["Observation_Ids"].cell(rec["row"], OBSERVATION_ID_COLUMNS.index("current_id") + 1).value = value


def refused(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def main() -> int:
    print("1. schema")
    check("current_id is the registry's last column in code; the migration declares the other ten and appends it",
          OBSERVATION_ID_COLUMNS[-1] == "current_id"
          and M.NEW_SHEETS["Observation_Ids"] + ["current_id"] == OBSERVATION_ID_COLUMNS
          and "self.add_registry_lineage_column()" in (ROOT / "scripts/migrate_schema.py").read_text(encoding="utf-8"))
    _, live_db = copy_db()
    check("the live workbook's registry header carries it", [c.value for c in live_db.wb["Observation_Ids"][1]][:11]
          == OBSERVATION_ID_COLUMNS)

    print("2. filling it from a registry with no lineage recorded")
    path, db = copy_db()
    reg = registry_rows(db)
    retired = sorted(o for o, r in reg.items() if r["status"] == "retired")
    for oid in retired:
        set_current(db, oid, None)
    ws = db.wb["Observations"]
    live_by_key = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value:
            live_by_key.setdefault(natural_key_of({c: ws.cell(r, i + 1).value for i, c in enumerate(OBSERVATION_COLUMNS)}),
                                   []).append(ws.cell(r, 1).value)
    check("with the column blank, check 15's rule reports every retired id", len(V.lineage_problems(db.wb)) == len(retired))
    res = L.run(db)
    after = registry_rows(db)
    check(f"all {len(retired)} retired ids are written", sorted(res["written"]) == retired and len(retired) == 23)
    check("each current_id is the one live id holding the retired id's natural key (computed independently)",
          all(live_by_key.get(reg[o]["natural_key"]) == [after[o]["current_id"]] for o in retired))
    check("no live id records a current_id", not [o for o, r in after.items() if r["status"] == "live" and r["current_id"]])
    check("nothing else in the registry changed",
          all({k: v for k, v in after[o].items() if k != "current_id"} == {k: v for k, v in reg[o].items() if k != "current_id"}
              for o in reg))
    check("the rule is satisfied afterwards", res["problems_after"] == [] and V.lineage_problems(db.wb) == [])
    check("the record carries each mapping with its retirement note",
          len(res["mapping"]) == 23 and all(m["retired_note"] is not None for m in res["mapping"]))
    again = L.run(db)
    check("re-running writes nothing", again["written"] == [] and len(again["unchanged"]) == 23)

    print("3. refusals and detection")
    path2, db2 = copy_db()
    victim = sorted(o for o, r in registry_rows(db2).items() if r["status"] == "retired")[0]
    set_current(db2, victim, "O00001")
    before = registry_rows(db2)
    check("a disagreeing current_id already recorded is refused", refused(lambda: L.run(db2)))
    check("... and nothing was written", registry_rows(db2) == before)
    check("the rule names the wrong current_id", any(victim in p for p in V.lineage_problems(db2.wb)))
    db2.save()
    out = subprocess.run([sys.executable, str(ROOT / "scripts/validate_repo_db.py"), "--db", str(path2)], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    check("check 15 FAILS on it", any("FAIL" in l and "ID LINEAGE" in l for l in out.splitlines()))
    _, db3 = copy_db()
    live_one = sorted(o for o, r in registry_rows(db3).items() if r["status"] == "live")[0]
    set_current(db3, live_one, "O00002")
    check("a live id recording a current_id is reported", any(live_one in p for p in V.lineage_problems(db3.wb)))

    print("4. an id that comes back to live drops its current_id")
    _, db4 = copy_db()
    values = {"company_id": "ZZTEST", "harness_id": "H-LINEAGETEST", "topic": "t", "source_url": "https://example.test/x"}
    rws = db4.wb["Observation_Ids"]
    rws.append(["O99990", natural_key_of(values), "ZZTEST", "H-LINEAGETEST", "t", "https://example.test/x",
                "2026-01-01", "retired", "2026-01-02", "test", "O00001"])
    oid = db4._assign_observation_id(values)
    rec = registry_rows(db4)["O99990"]
    check("re-assignment returns the retired id and clears current_id",
          oid == "O99990" and rec["status"] == "live" and rec["current_id"] is None)

    print("5. the live workbook")
    check("every retired id in the live registry records its current id, and the rule holds",
          V.lineage_problems(live_db.wb) == []
          and all(r["current_id"] for r in registry_rows(live_db).values() if r["status"] == "retired"))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
