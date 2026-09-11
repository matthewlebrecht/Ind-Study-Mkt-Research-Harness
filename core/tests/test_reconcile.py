"""
Regression test for the re-run policy in db.sync_observations().

Runs against a throwaway copy of the workbook — it never touches the real evidence base.

    python harnesses/test_dedupe.py

The behaviour under test is the reason v1.1 exists: re-running a harness must not
duplicate rows, must refresh stale ones, and must never overwrite a human's review.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.db import MarketIntelDB, Observation, WORKBOOK_PATH, today  # noqa: E402

TEST_HARNESS = "H-TEST-DEDUPE"
checks_run = 0


def check(condition: bool, label: str) -> None:
    global checks_run
    checks_run += 1
    if not condition:
        raise AssertionError(f"FAILED: {label}")
    print(f"  ok  {label}")


def make_obs(topic: str, text: str, url: str = "https://example.invalid/a",
             confidence: float = 0.8) -> Observation:
    return Observation(
        company_id="C0001",
        evidence_family="10_logistics_supply_network",
        evidence_role="buyer_acts",
        topic=topic,
        organizational_state="unknown",
        signal_strength="weak_clue",
        observation_text=text,
        evidence_excerpt="excerpt",
        source_url=url,
        publication_date="2026-01-01",
        retrieval_date=today(),
        source_grade="A",
        harness_id=TEST_HARNESS,
        harness_version="v1.1",
        confidence_0_1=confidence,
    )


def row_count(db: MarketIntelDB) -> int:
    ws = db.wb["Observations"]
    idx = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)].index("harness_id") + 1
    return sum(1 for r in range(2, ws.max_row + 1)
               if ws.cell(r, idx).value == TEST_HARNESS)


def find_row(db: MarketIntelDB, observation_id: str) -> dict:
    ws = db.wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == observation_id:
            return {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
    raise LookupError(observation_id)


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(WORKBOOK_PATH, tmp)
    db = MarketIntelDB(tmp)
    baseline = db.wb["Observations"].max_row

    print("\n1. first write inserts")
    a, b = make_obs("alpha", "original alpha"), make_obs("beta", "original beta",
                                                        url="https://example.invalid/b")
    rep = db.sync_observations([a, b])
    check(len(rep.inserted) == 2 and rep.written == 2, "two new rows inserted")
    check(row_count(db) == 2, "sheet holds exactly 2 test rows")
    a_id = a.observation_id

    print("\n2. identical re-run is a no-op")
    rep = db.sync_observations([make_obs("alpha", "original alpha"),
                                make_obs("beta", "original beta",
                                         url="https://example.invalid/b")])
    check(len(rep.unchanged) == 2 and rep.written == 0, "both rows unchanged")
    check(row_count(db) == 2, "no duplicate rows appended")

    print("\n3. changed content on an unreviewed row refreshes in place")
    rep = db.sync_observations([make_obs("alpha", "REVISED alpha", confidence=0.6)])
    check(len(rep.updated) == 1, "one row refreshed")
    check(row_count(db) == 2, "refresh did not add a row")
    row = find_row(db, a_id)
    check(row["observation_text"] == "REVISED alpha", "text updated in place")
    check(abs(float(row["confidence_0_1"]) - 0.6) < 1e-9, "confidence updated in place")
    check(row["observation_id"] == a_id, "observation_id preserved across refresh")

    print("\n4. a human review is never overwritten")
    ws = db.wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    status_col = headers.index("review_status") + 1
    notes_col = headers.index("reviewer_notes") + 1
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == a_id:
            ws.cell(r, status_col).value = "accepted"
            ws.cell(r, notes_col).value = "checked against SAFER by MTL"
    rep = db.sync_observations([make_obs("alpha", "SECOND REVISION", confidence=0.95)])
    check(len(rep.conflicts) == 1 and rep.written == 0, "change reported as a conflict")
    row = find_row(db, a_id)
    check(row["observation_text"] == "REVISED alpha", "reviewed text left untouched")
    check(row["review_status"] == "accepted", "review_status preserved")
    check(row["reviewer_notes"] == "checked against SAFER by MTL", "reviewer_notes preserved")
    check(rep.conflicts[0]["proposed_text"] == "SECOND REVISION",
          "conflict carries the proposed text for a human to compare")

    print("\n4b. --refresh-reviewed opts in, preserves the decision, stamps a note")
    rep = db.sync_observations([make_obs("alpha", "THIRD REVISION", confidence=0.55)],
                               refresh_reviewed=True, refresh_note="[refreshed by test]")
    check(len(rep.updated) == 1 and not rep.conflicts, "reviewed row refreshed on opt-in")
    check(rep.refreshed_reviewed == [a_id], "refresh of a reviewed row is reported")
    row = find_row(db, a_id)
    check(row["observation_text"] == "THIRD REVISION", "content refreshed")
    check(row["review_status"] == "accepted", "human's review decision preserved")
    check("checked against SAFER by MTL" in row["reviewer_notes"],
          "original reviewer note kept")
    check("[refreshed by test]" in row["reviewer_notes"], "refresh stamped into notes")

    print("\n5. a repeated key inside one batch does not double-insert")
    rep = db.sync_observations([make_obs("gamma", "g1", url="https://example.invalid/g"),
                                make_obs("gamma", "g1", url="https://example.invalid/g")])
    check(len(rep.inserted) == 1 and len(rep.unchanged) == 1, "second copy deduped")
    check(row_count(db) == 3, "only one gamma row exists")

    print("\n6. force-rewrite deletes unreviewed rows and keeps reviewed ones")
    removed = db.delete_observations(TEST_HARNESS, keep_reviewed=True)
    check(removed == 2, "two unreviewed rows removed")
    check(row_count(db) == 1, "the accepted row survived")
    check(find_row(db, a_id)["review_status"] == "accepted", "survivor is the reviewed row")

    print("\n7. the rest of the evidence base was not disturbed")
    db.delete_observations(TEST_HARNESS, keep_reviewed=False)
    check(row_count(db) == 0, "test rows cleaned up")
    check(db.wb["Observations"].max_row == baseline, "row count back to baseline")

    print(f"\nAll {checks_run} checks passed. (worked on {tmp})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
