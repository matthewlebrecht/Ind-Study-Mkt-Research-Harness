"""
Stable observation ids (session 14, convention 43).

    python core/tests/test_stable_ids.py

Works on a temporary copy of the workbook. Asserts the three properties that make an id
stable: a claim keeps its id across delete-and-rewrite; a retired id is never handed to a
different claim; and the registry stays in step with the live sheet through both delete
paths. Since convention 45 nothing deletes, so a PRE-RULE deletion is simulated to exercise id reuse.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.db import MarketIntelDB, Observation, WORKBOOK_PATH, natural_key_of  # noqa: E402

PASSED = FAILED = 0


def check(label, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok       {label}")
    else:
        FAILED += 1
        print(f"  FAIL     {label}")


def obs(company, topic, url, text="t"):
    return Observation(
        company_id=company, evidence_family="1_first_party_strategy_governance",
        evidence_role="buyer_articulates", topic=topic, organizational_state="unknown",
        signal_strength="weak_clue", observation_text=text, evidence_excerpt="e",
        source_url=url, publication_date="2026-09-01", retrieval_date="2026-09-06",
        source_grade="B", harness_id="H-STABLETEST", harness_version="v0",
        confidence_0_1=0.5)


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy2(WORKBOOK_PATH, tmp)
    db = MarketIntelDB(tmp)
    reg_before = db._registry()
    highest_before = db._highest_observation_id(reg_before)
    check("registry present and every live id registered",
          reg_before["ws"] is not None
          and all(oid in reg_before["by_id"] for oid in
                  (db.wb["Observations"].cell(r, 1).value
                   for r in range(2, db.wb["Observations"].max_row + 1))
                  if oid))

    print("1. a claim keeps its id across delete-and-rewrite")
    a = obs("C0001", "stable_test_topic", "https://example.test/a")
    b = obs("C0002", "stable_test_topic", "https://example.test/b")
    rep = db.sync_observations([a, b])
    ida, idb = a.observation_id, b.observation_id
    check("fresh ids allocated above every id ever assigned",
          int(ida[1:]) == highest_before + 1 and int(idb[1:]) == highest_before + 2)
    try:
        db.delete_observations("H-STABLETEST", keep_reviewed=True)
        refused_delete = False
    except Exception:
        refused_delete = True
    check("delete_observations itself refuses (convention 45)", refused_delete)
    ws = db.wb["Observations"]
    for oid in (ida, idb):          # a pre-rule deletion, simulated, to exercise the registry's id reuse
        r = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == oid)
        ws.delete_rows(r)
        db._retire_observation_id(oid, "test: simulated pre-rule deletion")
    reg = db._registry()
    check("both ids are RETIRED in the registry, not forgotten",
          reg["by_id"][ida]["status"] == "retired" and reg["by_id"][idb]["status"] == "retired")
    a2 = obs("C0001", "stable_test_topic", "https://example.test/a", text="changed text")
    db.sync_observations([a2])
    check("re-proposing the same claim (changed text, same natural key) gets its old id back",
          a2.observation_id == ida)
    check("... and the registry marks it live again",
          db._registry()["by_id"][ida]["status"] == "live")

    print("2. a retired id is never handed to a different claim")
    c = obs("C0003", "stable_test_topic", "https://example.test/c")
    db.sync_observations([c])
    check("a NEW claim skips the retired id and takes the next number",
          c.observation_id != idb and int(c.observation_id[1:]) == highest_before + 3)

    print("3. an unreproduced row is reported, not removed (convention 45)")
    res = db.unreproduced_observations("H-STABLETEST", proposed=[c])
    check("the unreproduced row is eligible for invalidation", res["eligible"] == [ida])
    check("... and nothing was removed: its id stays live in the registry",
          db._registry()["by_id"][ida]["status"] == "live")
    check("the reproduced row is untouched and live",
          db._registry()["by_id"][c.observation_id]["status"] == "live")

    print("4. the registry key matches the row")
    key = natural_key_of({"company_id": "C0003", "harness_id": "H-STABLETEST",
                          "topic": "stable_test_topic", "source_url": "https://example.test/c"})
    check("natural key recorded verbatim",
          db._registry()["by_id"][c.observation_id]["natural_key"] == key)

    print(f"\n{PASSED} checks passed, {FAILED} failed. (worked on {tmp})")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
