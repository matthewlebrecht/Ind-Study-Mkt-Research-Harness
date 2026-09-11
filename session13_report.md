# Session 13 Report — Temporal Schema Implemented; DR-0001 Dry-Run; Stable IDs Re-Flagged

**Date:** 2026-09-05
**Brief:** session 13, five items. Implements the reconciled schema delta (§19-26) now that
opaque theme ids are approved. One migration applied (5 changes). One new module, one new
script, one new sheet. **No derivation was appended:** DR-0001 was run as a dry run and its
3,240 rows are in this report; appending an immutable first derivation is Matthew's call.

## In one screen

| # | item | outcome |
|---|---|---|
| 1 | `buyer_detectable_since` before any backfill | **Already on the vocabulary (session 7); now load-bearing.** `core/composition.py` composes detectability -> realized reach -> instrument class, in that order, and `not_instrumented` is split into `theme_not_detectable` / `no_reach`. The dry run records the pre-8/31 weeks for the three flipped themes as `theme_not_detectable` (216 theme-buckets), not absence. §2. |
| 2 | Reach: nominal vs realized | Columns existed since session 7 but were EMPTY on all 47 `Harness_Sources` rows. **Populated** from §21.2 and the 2026-09-02 ping, with per-row provenance in `notes`; 15 values are Code's own classifications and say "unverified". Composition reads `realized_reach` only; `min_retrospective_reach` is stamped on every derived row. §3. |
| 3 | Opaque theme ids | `theme_id`, `display_label`, `definition_hash` were already in `core/topics.py`; the derivation now **stamps** `definition_hash`, `theme_id`, `display_label` and `buyer_detectable_since` onto every `Company_State_History` row. Nothing further was built on the vocabulary. |
| 4 | `Signal_Types.status` enforcement | **Rollup filter, never write filter, now in code:** `core/attempts.py::rollups` and `scripts/published_coverage.py` both exclude non-`active` types from the denominator by the same lookup; the Attempts write path is untouched and a test proves both halves. Inert today (every registered type is `active` except ST-WIREREPRINT `routing_only`, which nothing attempts). |
| 5 | Four invariants, mechanically | `core/tests/test_schema_delta.py` §7 turned from 3 PENDING into 17 assertions, plus §7b for the rollup filter. **74 checks pass, 0 pending.** |
| — | Stable observation ids | **Still fully open, untouched here.** Re-flagged in CLAUDE.md as a different system from the theme ids. Needs a fresh Harness Advisor brief. |

Checks after: `validate_repo_db.py` 9/9 (check 6 lists the new sheet at 250,000; check 7
now 30 validations), `assert_validations.py` clean, `check_run_ledger.py` clean,
`test_audit_gate` 56/56, `test_attempts` 35/35, `test_reconcile` 27/27.

## 1. What landed

- **`Company_State_History`** (new sheet, 25 columns, bound to 250,000 rows because it is
  append-only): one row per derivation x company x theme x ISO-week bucket. Columns stamp
  everything the row was composed against: `definition_hash`, `buyer_detectable_since`,
  `min_retrospective_reach`, `covering_instruments`, `supporting_observation_ids`,
  `derivation_version`, `staleness_years`. `status` is `observed` / `absent` / `null`;
  `reason` is `observed`, `absence_licensed_IC3`, `absence_licensed_IC4`,
  `no_absence_license`, `no_reach`, `theme_not_detectable`. Two new Lookups vocabularies
  (`state_status`, `state_reason`) and four validations bind them.
- **`core/composition.py`**: the derivation, pure over injected tables so it is testable
  without a workbook, plus a workbook loader. The instruments that can see the themes are
  DECLARED (`THEME_INSTRUMENTS`: FIRSTPARTY, EXECVOICE, TRADEPRESS see all themes through
  the spine; JOBPOST sees the themes its keys map to), and JOBPOST is declared
  `PRESENCE_ONLY` per Signal Advisor's condition 1. LEGAL and PRODUCTQUALITY rows count as
  presence when they exist but neither is an absence instrument for modernization themes
  (§20.5).
- **`core/db.py::append_state_history`**: the sole writer. Refuses a derivation_id already
  on the sheet, refuses an unstamped row, refuses a row past the reach gate without its
  `min_retrospective_reach`. Never updates.
- **`scripts/derive_state_history.py`**: dry run by default, prints the breakdown by
  status / reason / theme / bucket and the row-level delta against the previous derivation;
  `--apply` appends; `--csv` exports.
- **Reach populated** on `Harness_Sources` (migration step `populate_reach`, writes only
  into empty cells; `realized_reach_effective_from` = the harness's first run date).
- **Rollup filter** for `Signal_Types.status`, in both places coverage is computed.
- **Convention 42** in `docs/conventions.md`.

## 2. The composition rule as implemented, and one interpretation it needed

The approved order is applied literally, with one reading the package left open and one it
did not anticipate:

- **Buckets are ISO weeks (Monday start)**, and the series begins at the earliest
  `buyer_detectable_since` across themes (2026-08-22, so 2026-W34) and runs to the derivation
  date. Buckets before the series start are excluded, per §25.2, rather than written as
  null. Weeks were chosen because the brief's concern is the pre-8/31 period *inside* the
  five-week window; months would not resolve it and quarters would hide it.
- **Detectability compares to bucket START, as the package says.** Consequence:
  `ot_modernization` (detectable since 2026-09-02) is `theme_not_detectable` through
  2026-W36 and first detectable in W37. Conservative; noted in CLAUDE.md so the first rows
  are not read as a defect.
- **"Reach covers T" is per company, from the Attempts ledger, not from the source alone.**
  An instrument covers bucket T for a company when one of its runs recorded a coverage
  outcome for that company at time t and the source's realized reach at t spans T:
  `current_only` speaks only to the bucket containing t; `bounded (N)` to buckets whose end
  is within N months before t; `archival` to any bucket that started by t. A read never
  speaks to a bucket that starts after it. This is what makes H-JOBPOST-01 (IC3,
  `current_only`) unable to say anything about last week, which §21.3 names as the
  portfolio's highest-risk composition.
- **A released buyer observation informs T** on the same reach rule plus
  `publication_date <= T_end` within the five-year staleness standard, so a state persists
  forward from its evidence date and never backward. The bucket takes the state of the
  highest-confidence informing row.

## 3. DR-0001, dry run (as of 2026-09-05)

108 companies x 10 themes x 3 buckets (W34-W36) = 3,240 rows.

| reason | rows | meaning |
|---|---|---|
| `theme_not_detectable` | 1,620 | all of W34 (no theme was instrumented by Mon 8/17); W34-W35 for the three flipped themes; all three weeks for `ot_modernization` |
| `no_absence_license` | 1,371 | reached, nothing found, and no covering instrument may read silence as absence |
| `observed` | 231 | a released buyer row informs the bucket (W35 88, W36 143; states: unknown 128, active_transition 67, target_state 36) |
| `no_reach` | 18 | A009, A010, A062 in W35: no instrument reached them that week |
| `absent` | **0** | see below |

**The finding the dry run produced: no theme has a licensed-absence instrument today.**
Every reached, evidence-free theme-bucket is `no_absence_license`. H-JOBPOST-01 is IC3 but
presence-only until its readability denominator is accepted; FIRSTPARTY is IC1; EXECVOICE
and TRADEPRESS are IC2. `Theme.absence_licensed = True` on THEME-01..06 was set on
2026-08-31, before the presence-only condition was stated, and `gap_report.py` still prints
"buyer silent" from it. The derivation does not read that flag, so the history is right
either way; the flag and the gap report are logged as stale in CLAUDE.md, not flipped.

`min_retrospective_reach` is stamped as the weakest reach relied on: `archival` on the 630
W35 rows reached only by FIRSTPARTY, `current_only` on the 738 W36 rows where JOBPOST also
covered. Reach in force per harness (weakest realized reach among its latest version's
primary sources): FIRSTPARTY / LEGAL / PRODUCTQUALITY archival; SAFETY-ENV bounded 120;
FMCSA bounded 24; WAYBACK bounded 0 (self-referential, grows with retention); JOBPOST,
EXECVOICE, TRADEPRESS, SELLERCONTENT, EXECID, EMPREVIEW current_only.

To append it:

```
python scripts/derive_state_history.py --apply
```

Any later derivation prints its delta against DR-0001 before writing, and refuses to write
an identical one without `--force`.

## 4. Not done, and why

- **DR-0001 is not on the sheet.** The table is immutable and the first rows set the
  precedent; the brief said "before any backfill runs", which reads as backfill being a
  separate step. The dry run above is the full preview.
- **The ping's fourth stage (per-bucket access)** is not a separate column. It is
  satisfied structurally: reach coverage is computed from Attempts with coverage outcomes,
  so an `access_blocked` attempt covers nothing and the bucket is `no_reach`. Whether that
  is enough, or whether access should be stamped explicitly, remains the advisor's open
  question.
- **Reach values marked unverified** (15 sources) are Code's classifications. Listed in
  CLAUDE.md; correcting one is a hand edit followed by a new derivation.
- **Stable observation ids**: nothing built, nothing designed. Re-flagged.

## Files

- New: `core/composition.py`, `scripts/derive_state_history.py`, this report.
- Changed: `core/db.py` (`append_state_history`, `latest_derivation_id`,
  `signal_type_status`), `core/attempts.py` (`ROLLUP_STATUSES`, filter in `rollups`),
  `scripts/published_coverage.py` (same filter), `scripts/migrate_schema.py` (sheet,
  vocabularies, `REACH_VALUES`, `populate_reach`, 4 validations),
  `core/tests/test_schema_delta.py` (§7 asserted, §7b added), `docs/conventions.md` (42),
  `CLAUDE.md`, `data/market_intel_db.xlsx` (schema only: new sheet with header, 47 reach
  rows, 2 Lookups columns; no observation, attempt or run row changed).
