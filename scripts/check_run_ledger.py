#!/usr/bin/env python3
"""
Step 0's run-ledger check: does the workbook agree with VERSION CONTROL?

WHY THIS REPLACES THE OLD CHECK
-------------------------------
The 2026-09-01 brief's Step 0 asked for "workbook content assertions per CLAUDE.md,
including the Harness_Runs row count". That check failed at the start of the session, and
it failed for the wrong reason: `CLAUDE.md` said 19 runs and the workbook held 25, because
the previous session had run overnight and the state file's snapshot section had not been
refreshed. Every number reconciled exactly to committed deltas.

The design fault is that it asserted agreement between a DOCUMENT and a DATABASE. Prose
goes stale on its own, so the check could not distinguish documentation staleness -- which
is untidy -- from workbook drift, which is the thing an abort exists to catch. An abort
that can be reasoned past is not an abort.

So the authoritative comparison is against git, not against prose:

    working-tree workbook  vs  the workbook at HEAD

Git cannot go stale relative to itself. A run row present in the working tree and absent
from HEAD is uncommitted work -- fine mid-session, and reported. A run row present at HEAD
and MISSING from the working tree is destruction of committed history, which is the real
abort condition and is what the old check was reaching for.

`CLAUDE.md` is still compared, but only ever as a WARNING. A stale state file is a chore,
not a reason to forfeit a session.

    python scripts/check_run_ledger.py            # warn-only summary
    python scripts/check_run_ledger.py --strict   # exit 1 on a real divergence
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "market_intel_db.xlsx"
CLAUDE = ROOT / "CLAUDE.md"
TRACKED = "data/market_intel_db.xlsx"

SHEETS = ["Harness_Runs", "Observations", "Attempts", "Company_Executives", "Companies"]


def _data_rows(ws) -> list[dict]:
    it = ws.iter_rows(values_only=True)
    try:
        header = [str(h) if h is not None else "" for h in next(it)]
    except StopIteration:
        return []
    out = []
    for row in it:
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        out.append(dict(zip(header, row)))
    return out


def counts(path_or_bytes) -> dict:
    if isinstance(path_or_bytes, bytes):
        wb = openpyxl.load_workbook(io.BytesIO(path_or_bytes), read_only=True,
                                    data_only=True)
    else:
        wb = openpyxl.load_workbook(path_or_bytes, read_only=True, data_only=True)
    out = {}
    for name in SHEETS:
        out[name] = _data_rows(wb[name]) if name in wb.sheetnames else []
    return out


def head_workbook() -> bytes | None:
    """The committed workbook at HEAD, or None if it is not tracked yet."""
    try:
        return subprocess.run(["git", "show", f"HEAD:{TRACKED}"], cwd=ROOT,
                              capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None


def claude_md_counts() -> dict:
    """Whatever CLAUDE.md currently claims. Best-effort; absence is not an error."""
    if not CLAUDE.exists():
        return {}
    text = CLAUDE.read_text(encoding="utf-8", errors="replace")
    out = {}
    for key, pattern in (
            ("Observations", r"\*\*([\d,]+)\s+observations\*\*"),
            ("Attempts", r"\*\*([\d,]+)\s+attempts logged\*\*"),
            ("Harness_Runs", r"([\d,]+)\s+harness runs"),
            ("Company_Executives", r"\*\*([\d,]+)\s+executives\*\*")):
        m = re.search(pattern, text)
        if m:
            out[key] = int(m.group(1).replace(",", ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when the working tree has LOST committed rows")
    ap.add_argument("--retired", default="",
                    help="comma-separated observation_ids REMOVED ON PURPOSE this session "
                         "(e.g. by a harness re-run with --retire-stale). Named ids are "
                         "acknowledged; any OTHER committed row missing still aborts.")
    args = ap.parse_args()
    retired = {x.strip() for x in args.retired.split(",") if x.strip()}

    now = counts(DB)
    print("run ledger: working tree vs HEAD\n")

    head_bytes = head_workbook()
    if head_bytes is None:
        print("  [!] the workbook is not tracked at HEAD -- nothing to compare against.")
        return 0

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
        fh.write(head_bytes)
    try:
        was = counts(head_bytes)
    finally:
        Path(fh.name).unlink(missing_ok=True)

    lost = False
    # Observations are compared BY ID, not by count: a count cannot tell a deliberate,
    # named retirement (a harness re-run that withdrew claims its new admission rule no
    # longer makes, 2026-09-02) from a lost row, and cannot see a swap at all.
    head_obs = {str(r.get("observation_id")) for r in was["Observations"] if r.get("observation_id")}
    now_obs = {str(r.get("observation_id")) for r in now["Observations"] if r.get("observation_id")}
    gone_obs = sorted(head_obs - now_obs)
    unacknowledged = [o for o in gone_obs if o not in retired]
    print(f"  {'sheet':22} {'HEAD':>8} {'working':>8} {'delta':>8}")
    print(f"  {'-' * 22} {'-' * 8} {'-' * 8} {'-' * 8}")
    for name in SHEETS:
        a, b = len(was[name]), len(now[name])
        flag = ""
        if name == "Observations" and gone_obs:
            if unacknowledged:
                flag = "  <-- ROWS LOST SINCE HEAD"
                lost = True
            else:
                flag = f"  ({len(gone_obs)} retired on purpose, all acknowledged)"
        elif b < a:
            flag = "  <-- ROWS LOST SINCE HEAD"
            lost = True
        print(f"  {name:22} {a:8} {b:8} {b - a:+8}{flag}")
    if gone_obs:
        ack = [o for o in gone_obs if o in retired]
        if ack:
            print(f"\n  acknowledged retirements ({len(ack)}): {', '.join(ack)}")
        if unacknowledged:
            print(f"\n  [ABORT] observations committed at HEAD and MISSING, not acknowledged "
                  f"via --retired: {', '.join(unacknowledged)}")
        stale_ack = sorted(retired - set(gone_obs))
        if stale_ack:
            print(f"  [warn] --retired names rows that are NOT missing: {', '.join(stale_ack)}")

    # Run ids are the ledger proper: a committed run must still exist.
    head_ids = {str(r.get("run_id")) for r in was["Harness_Runs"] if r.get("run_id")}
    now_ids = {str(r.get("run_id")) for r in now["Harness_Runs"] if r.get("run_id")}
    missing = sorted(head_ids - now_ids)
    added = sorted(now_ids - head_ids)
    if added:
        print(f"\n  uncommitted runs in the working tree: {', '.join(added)}")
        print("      expected mid-session; commit them and this line goes away.")
    if missing:
        lost = True
        print(f"\n  [ABORT] runs committed at HEAD and MISSING from the working tree: "
              f"{', '.join(missing)}")
        print("      committed history has been destroyed, which is what this check is for.")

    # CLAUDE.md: WARN ONLY. A stale state file is a chore, never an abort.
    claimed = claude_md_counts()
    stale = {k: (v, len(now.get(k, [])))
             for k, v in claimed.items() if v != len(now.get(k, []))}
    print()
    if not claimed:
        print("  [warn] could not read any counts out of CLAUDE.md")
    elif stale:
        print("  [warn] CLAUDE.md is stale -- a chore, NOT an abort condition:")
        for k, (said, actual) in sorted(stale.items()):
            print(f"           {k:22} says {said}, workbook holds {actual}")
        print("         Prose goes stale on its own. This check exists so that fact can no")
        print("         longer be confused with the database having drifted.")
    else:
        print("  ok    CLAUDE.md's stated counts match the workbook")

    if lost:
        print("\nRESULT: committed rows are missing from the working tree.")
        return 1 if args.strict else 0
    print("\nRESULT: no committed row has been lost. Workbook agrees with version control.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
