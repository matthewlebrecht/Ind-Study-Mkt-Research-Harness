#!/usr/bin/env python3
"""
Harness holds: the mechanism, and the fact that NOTHING is held today.

H-FIRSTPARTY-01 and H-TRADEPRESS-01 were both held on 2026-09-15 for the page-furniture defect and both were lifted
the same day on Matthew Lebrecht's instruction -- TRADEPRESS once its v1.8 end-of-article fix replayed with no live-row
change (item 9), FIRSTPARTY once v1.3 read themes from the article body and its dry run was measured (item 22). So the
tests here exercise the mechanism against a SYNTHETIC hold, and assert that the real registry is empty and that the
harnesses still call `holds.enforce`, so re-holding one is an entry in core/holds.py and nothing else.

    python core/tests/test_holds.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import holds  # noqa: E402

PASS = FAIL = 0
FORMERLY_HELD = {"H-FIRSTPARTY-01": "harnesses/h_firstparty_01/harness.py",
                 "H-TRADEPRESS-01": "harnesses/h_tradepress_01/harness.py"}
SYNTHETIC = holds.Hold(since="2026-09-15", by="Matthew Lebrecht", reason="a test harness writes rows from page furniture",
                       lifts_when=("the extractor reads the article body", "a dry run is measured"))


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def refused(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def main() -> int:
    print("1. nothing is held today")
    check("core/holds.py holds no entries", holds.HOLDS == {})
    for hid in FORMERLY_HELD:
        check(f"{hid}: no mode is refused",
              not any(holds.refusal(hid, offline=o, commit=c) for o in (True, False) for c in (True, False)))
        check(f"{hid}: enforce() raises nothing",
              not any(refused(lambda o=o, c=c: holds.enforce(hid, offline=o, commit=c))
                      for o in (True, False) for c in (True, False)))
    src = (ROOT / "core/holds.py").read_text(encoding="utf-8")
    check("the file records that both holds were lifted, when and why",
          "LIFTED" in src and "item 22" in src and "v1.8" in src)

    print("2. the mechanism, against a synthetic hold")
    hid = "H-TESTHOLD-01"
    holds.HOLDS[hid] = SYNTHETIC
    try:
        check("a live dry run is refused", refused(lambda: holds.enforce(hid, offline=False, commit=False)))
        check("a live --commit is refused", refused(lambda: holds.enforce(hid, offline=False, commit=True)))
        check("an offline --commit is refused", refused(lambda: holds.enforce(hid, offline=True, commit=True)))
        check("an offline dry replay is allowed", not refused(lambda: holds.enforce(hid, offline=True, commit=False)))
        msg = holds.refusal(hid, offline=False, commit=False) or ""
        check("the message names the date and who set it", "2026-09-15" in msg and "Matthew Lebrecht" in msg)
        check("... gives the reason", "Reason:" in msg and "page furniture" in msg)
        check("... says which mode is still allowed", "--offline WITHOUT --commit" in msg)
        check("... lists every lift condition", "Lifts when:" in msg and all(c in msg for c in SYNTHETIC.lifts_when))
        check("... says how to lift it", "remove this harness's entry" in msg)
        check("a harness with no entry is never refused",
              not any(refused(lambda o=o, c=c: holds.enforce("H-FMCSA-01", offline=o, commit=c))
                      for o in (True, False) for c in (True, False)))
    finally:
        del holds.HOLDS[hid]
    check("the synthetic hold is gone again", holds.HOLDS == {})

    print("3. re-holding a harness needs no harness change")
    for hid, rel in FORMERLY_HELD.items():
        src = (ROOT / rel).read_text(encoding="utf-8")
        body = src[src.index("def main()"):]
        at = body.find("holds.enforce(HARNESS_ID")
        firsts = [body.find(s) for s in ("MarketIntelDB(", "DatedCache(", "BraveSearch(") if body.find(s) >= 0]
        check(f"{hid}: main still calls holds.enforce", at >= 0)
        check(f"{hid}: before any workbook, cache or search client is opened", at >= 0 and firsts and at < min(firsts))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
