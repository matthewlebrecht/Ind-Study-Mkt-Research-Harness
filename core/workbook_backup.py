"""
One rolling-backup policy for every script that writes the workbook outside `core/db.py`.

WHY THIS EXISTS
---------------
Four scripts (`migrate_schema.py`, `register_sources.py`, `extend_validation.py`,
`reconstruct_workbook.py`) each copied the workbook to a fresh `.bak-<timestamp>.xlsx`
on every `--apply`, and nothing ever removed one. By 2026-09-02 there were 32 of them in
`data/` beside the live file -- near-identical names, same folder, no warning -- and 29
of them predated the audited H-PRODUCTQUALITY-01 row. Opening the wrong one is what
produced the "O00366 is missing" false alarm in sessions 5 and 6. The per-file record of
what they held is in `docs/archive/stale_workbook_copies_2026-09-02.md`.

The workbook is tracked in git and `scripts/check_run_ledger.py` compares the working
tree against HEAD, so git is the durable backup. A `.bak` guards only the window between
the last commit and a botched `--apply`. Three of them cover that window; thirty do not
cover it any better and actively harm the thing they were meant to protect.

So: one function, one name pattern, and the newest `keep` copies survive. A script that
wants a different policy passes `keep`; a script that wants no backup at all should say
so where it calls this, not by omitting the call.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

KEEP_DEFAULT = 3


def list_backups(path: Path | str) -> list[Path]:
    """Every rolling backup of `path`, oldest first (the timestamp sorts lexically)."""
    path = Path(path)
    return sorted(path.parent.glob(f"{path.stem}.bak-*{path.suffix}"), key=lambda p: p.name)


def prune_backups(path: Path | str, keep: int = KEEP_DEFAULT) -> list[Path]:
    """Delete all but the newest `keep` backups of `path`. Returns what was deleted."""
    backups = list_backups(path)
    doomed = backups[:-keep] if keep > 0 else backups
    for p in doomed:
        p.unlink()
    return doomed


def backup_workbook(path: Path | str, keep: int = KEEP_DEFAULT) -> tuple[Path, list[Path]]:
    """Copy `path` to `<stem>.bak-<YYYYmmdd-HHMMSS><suffix>` beside it, then prune.

    Returns (the new backup, the backups pruned to make room). Callers print both, so a
    deletion is reported rather than silent (convention: every suppressed result gets
    reported).
    """
    path = Path(path)
    backup = path.with_name(f"{path.stem}.bak-{datetime.now():%Y%m%d-%H%M%S}{path.suffix}")
    shutil.copy2(path, backup)
    pruned = prune_backups(path, keep)
    return backup, pruned
