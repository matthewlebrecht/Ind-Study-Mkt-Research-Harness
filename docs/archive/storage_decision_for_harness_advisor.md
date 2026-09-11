# Storage Tier — Resolved (2026-08-27)

For: Harness Advisor project, re: the open storage-tier question in
`attempts_schema_spec.md` (Rev 4).

## Decision

**Workbook-only. No hybrid, no JSONL files.** Extend the Excel data-validation range on
both `Observations` and the new `Attempts` sheet from the current `X2:X500` binding to
something comfortably large — **~20,000 rows** — rather than splitting storage between
files (canonical) and workbook (current-state view).

## Why this changes the earlier lean

Matthew confirmed this project's scope is fixed: the 108-company Anvil + pilot list, not
expanding to a larger universe within this project. That doesn't eliminate the row-count
problem you flagged — 20 harnesses running against 108 companies still projects well past
500 rows (conservatively ~4,300+) regardless of company count, since harness count is the
multiplier, not company count alone. But it does simplify the fix: for a project this
bounded, workbook-only with a wide validation range covers the real volume with a
five-minute change, no architecture split needed. The earlier hybrid recommendation was
sized for open-ended scale that this project doesn't have.

## What this means for your spec

- Drop the file-based/hybrid storage design from `attempts_schema_spec.md` — the workbook
  stays the single system of record, consistent with the "relational evidence database"
  framing of the deliverable.
- Extend validation range to ~20,000 rows on `Observations` and `Attempts`. This is an
  execution task for Claude Code, not something that needs further design here — just
  confirm the spec reflects workbook-only before Claude Code implements it.
- Everything else already decided in Rev 4 (Attempts schema, two-axis failure vocabulary,
  harness_id/naming rules, Company_Executives + H-EXECID-01, etc.) stands unchanged.

## Cleared to move on

With this resolved, the next item on your own stated priority list is **repo structure**
(ahead of portfolio visualization, per your last session brief). Go ahead.
