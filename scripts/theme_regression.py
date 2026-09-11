#!/usr/bin/env python3
"""
Diff the theme spine against a git revision, over every committed Observation.

    python scripts/theme_regression.py                      # baseline = HEAD
    python scripts/theme_regression.py --baseline 127cd45   # any revision of core/topics.py

WHY THIS EXISTS
---------------
Session 6 changed `core/topics.py` (the cybersecurity/OT split) and reported "0 of 337
observations changed theme set under old vs. new spine". The check was run by hand and
not kept. The 2026-09-02 brief asked for the same check after the `cybersecurity_ot` ->
`cybersecurity` key rename, and a regression check that has to be re-invented each time
it is needed is not a regression check (convention 37). So it lives here, and its output
is the thing a session report quotes.

WHAT IT COMPARES
----------------
For every Observations row: `classify(observation_text + " " + evidence_excerpt)` under
the BASELINE module (the file at `--baseline`, loaded from git without touching the
working tree) and under the WORKING-TREE module. Keys the working tree has retired
(`RETIRED_THEME_KEYS`) are mapped forward on the baseline side before comparing, so a
pure rename is identity and anything else -- a pattern edit that moves a row, a key that
vanished without a forward mapping -- is reported as a change.

It also prints the theme inventory side by side (key, theme_id, label, pattern set) so a
rename, a split and a pattern edit each look like what they are, and it FAILS if any
`Observations.topic` still carries a retired key.

WHAT IT DOES NOT TELL YOU
-------------------------
The text is the observation's own text -- for most harnesses the sentence the harness
wrote plus its matched-term excerpt, not the source page. So this is a check on the
SPINE (does the same text route the same way?) and not on the harnesses. A pattern change
can alter what a harness would extract from the source on a re-run, and only a re-run
shows that. Say so when quoting a 0-changed result.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import topics as current  # noqa: E402

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"
TOPICS_PATH = "core/topics.py"


def load_baseline(rev: str):
    """Import `core/topics.py` as it was at `rev`, from git, under a private module name."""
    src = subprocess.run(["git", "show", f"{rev}:{TOPICS_PATH}"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8")
    if src.returncode != 0:
        raise SystemExit(f"ABORT: git show {rev}:{TOPICS_PATH} failed: {src.stderr.strip()}")
    tmp = Path(tempfile.mkdtemp(prefix="topics_baseline_")) / "topics_baseline.py"
    tmp.write_text(src.stdout, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("topics_baseline", tmp)
    mod = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules[cls.__module__]; register first.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def observations(db: Path) -> list[dict]:
    ws = openpyxl.load_workbook(db, read_only=True)["Observations"]
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows)
    out = []
    for r in rows:
        if not r or r[0] is None:
            continue
        out.append(dict(zip(hdr, r)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--baseline", default="HEAD",
                    help="git revision whose core/topics.py is the 'before' (default HEAD)")
    ap.add_argument("--verbose", action="store_true", help="list every changed row")
    args = ap.parse_args()

    base = load_baseline(args.baseline)
    forward = dict(getattr(current, "RETIRED_THEME_KEYS", {}))
    base_retired = dict(getattr(base, "RETIRED_THEME_KEYS", {}))

    print(f"baseline: {args.baseline} ({TOPICS_PATH})   working tree: {TOPICS_PATH}")
    print(f"retired keys (working tree): {forward or '{}'}")
    print()

    # ---- 1. inventory, by theme_id ----
    print("1. theme inventory (by theme_id)")
    b_by_id = {t.theme_id: t for t in base.THEMES}
    c_by_id = {t.theme_id: t for t in current.THEMES}
    inventory_changes = 0
    for tid in sorted(set(b_by_id) | set(c_by_id)):
        b, c = b_by_id.get(tid), c_by_id.get(tid)
        if b is None:
            print(f"  +  {tid:9s} NEW      key={c.key!r} label={c.label!r} "
                  f"{len(c.patterns)} pattern(s)")
            inventory_changes += 1
            continue
        if c is None:
            print(f"  -  {tid:9s} REMOVED  key={b.key!r} -- a theme_id must never be deleted")
            inventory_changes += 1
            continue
        notes = []
        if b.key != c.key:
            how = "declared retirement" if forward.get(b.key) == c.key else "UNDECLARED"
            notes.append(f"key {b.key!r} -> {c.key!r} ({how})")
        if b.label != c.label:
            notes.append(f"label {b.label!r} -> {c.label!r}")
        if list(b.patterns) != list(c.patterns):
            notes.append(f"specific patterns differ ({len(b.patterns)} -> {len(c.patterns)})")
        for attr in ("generic", "exclusions"):
            bv, cv = list(getattr(b, attr, [])), list(getattr(c, attr, []))
            if bv != cv:
                notes.append(f"{attr} differ ({len(bv)} -> {len(cv)})")
        if getattr(b, "corroboration", "any") != getattr(c, "corroboration", "any"):
            notes.append(f"corroboration {getattr(b, 'corroboration', 'any')!r} -> "
                         f"{c.corroboration!r}")
        if getattr(b, "buyer_detectable", None) != getattr(c, "buyer_detectable", None):
            notes.append(f"buyer_detectable {b.buyer_detectable} -> {c.buyer_detectable}")
        if notes:
            inventory_changes += 1
            print(f"  ~  {tid:9s} {'; '.join(notes)}")
        else:
            print(f"  =  {tid:9s} {c.key}")
    undeclared = [tid for tid in b_by_id if tid in c_by_id
                  and b_by_id[tid].key != c_by_id[tid].key
                  and forward.get(b_by_id[tid].key) != c_by_id[tid].key]
    print()

    # ---- 2. per-observation routing ----
    obs = observations(Path(args.db))
    changed = []
    for o in obs:
        text = f"{o.get('observation_text') or ''} {o.get('evidence_excerpt') or ''}"
        before = {forward.get(k, k) for k in base.classify(text)}
        after = set(current.classify(text))
        if before != after:
            changed.append((o["observation_id"], o.get("harness_id"), sorted(before),
                            sorted(after)))
    print(f"2. routing: {len(changed)} of {len(obs)} observations changed theme set "
          f"(baseline keys mapped forward through retirements)")
    if changed and (args.verbose or len(changed) <= 25):
        for oid, hid, b, a in changed:
            print(f"     {oid} {hid}: {b} -> {a}")
    elif changed:
        print(f"     (first 25 of {len(changed)}; --verbose for all)")
        for oid, hid, b, a in changed[:25]:
            print(f"     {oid} {hid}: {b} -> {a}")
    print()

    # ---- 3. the topic column itself ----
    topics_live = {str(o.get("topic")) for o in obs}
    stale = sorted(topics_live & set(forward))
    stale_rows = [o["observation_id"] for o in obs if str(o.get("topic")) in forward]
    live_theme_keys = {t.key for t in current.THEMES}
    n_theme = sum(1 for o in obs if str(o.get("topic")) in live_theme_keys)
    n_mapped = sum(1 for o in obs if current.theme_of_buyer_signal(str(o.get("topic"))))
    n_native = len(obs) - n_theme - n_mapped
    print("3. Observations.topic")
    print(f"     {n_theme} rows carry a live theme key, {n_mapped} a buyer signal key mapped "
          f"to a theme, {n_native} a harness-native topic with no theme mapping")
    if stale:
        print(f"     FAIL: {len(stale_rows)} row(s) still carry retired key(s) {stale}: "
              f"{', '.join(stale_rows[:12])}{' ...' if len(stale_rows) > 12 else ''}")
    else:
        print("     ok: no row carries a retired theme key")
    if base_retired and base_retired != forward:
        print(f"     note: baseline declared retirements {base_retired}; working tree "
              f"declares {forward}")
    print()

    failures = []
    if changed:
        failures.append(f"{len(changed)} observation(s) changed theme set")
    if stale:
        failures.append(f"retired key(s) present in Observations.topic: {stale}")
    if undeclared:
        failures.append(f"key changed without a RETIRED_THEME_KEYS entry: {undeclared}")
    if failures:
        print("REGRESSION: " + "; ".join(failures))
        return 1
    print(f"clean: {len(obs)} observations route identically under {args.baseline} and the "
          f"working tree; {inventory_changes} theme(s) differ in inventory, all declared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
