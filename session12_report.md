# Session 12 Report — Release Executed, Sheets Redrawn, Queue Compiled

**Date:** 2026-09-04
**Brief:** session 12, five items. Items 1–4 done this session; item 5 (apply Matthew's
verdicts) waits on the review. No harness ran. One workbook write: the H-SAFETY-ENV-01 v1.3
release. One code change: an opt-in flag on the sampler.

## In one screen

| # | item | outcome |
|---|---|---|
| 1 | SAFETY-ENV v1.3 release | **Executed, not just recorded.** `H-SAFETY-ENV-01__v1.3.json` written; HR-0053 `quarantined -> published`; 64 rows `quarantined -> released`. `published_coverage.py` now lists HR-0053 as `audited`, 92.6%. Check 9: 9 audited. §1 says what the artifact does and does not claim. |
| 2 | JOBPOST v1.1 / v1.3 sheets | **Redrawn** against the 3 and 13 rows actually at those versions (were drawn at 21 and 25). Same sampler, same seed, same format as the v1.4 sheet. |
| 3 | FMCSA v1.3 sheet | **Drawn** for the 4 rows from HR-0034 (A024). First draw put all 24 v1.3 rows on the sheet, 20 of them already released and human-reviewed, because the sampler keys on version only. Added `--only-quarantined` to `scripts/audit_sample.py` (off by default; every earlier sheet redraws identically) and redrew. |
| 4 | Consolidated queue | `harness_output/audits/REVIEW_QUEUE_2026-09-04.md`: **58 rows**, grouped by harness, one block per row with claim, excerpt, source, grade/confidence and a blank verdict line. |
| 5 | Apply verdicts | **Done 2026-09-05.** Matthew reviewed every row on the queue individually; all supported. 58 `supported` verdicts recorded row by row, 8 artifacts written, 8 versions published, sheets regenerated to show the recorded verdicts. Quarantine **74 -> 16**. §5. |

Quarantine went **138 -> 74** on 2026-09-04 (the 64 SAFETY-ENV v1.3 rows) and **74 -> 16** on 2026-09-05 (the 58 queue rows). What remains is exactly the two carried sheets: FMCSA v1.4 (9) and WAYBACK v1.2 (7).

## 1. What the SAFETY-ENV artifact claims

The brief's Option A: release on the standing authorization, no new individual review. The
artifact says exactly that, in the auditor field and at length in `summary_md`:

- `random_control.sampled_n = 0` of 64. The 30-row sheet drawn in session 10 exists and was
  not judged. Precision is undefined. The 0.0% exclusion rate that makes the stop rule pass
  is vacuous, not measured. **Do not quote a precision rate for this version.**
- What was checked instead, mechanically, against the workbook at f48d3f2 (the last commit
  before the S24 refresh): all 64 ids were released machine rows there (51 at v1.0, 13 at
  v1.1, both grandfathered). Between that commit and HEAD the only fields that changed are
  `observation_text` (64), `evidence_excerpt` (55), `harness_version` and
  `publication_state`. Company, topic, source URL, grade, strength, state and confidence are
  identical on every row. v1.3 asserts the same inspections at the same strength; the count
  wording became a declared floor where it had been a silent cap.
- So the release rests on the grandfathered v1.0/v1.1 release plus that check. If those rows
  were wrong, these are wrong the same way. The grandfather exemption was never a precision
  finding and this artifact does not upgrade it into one.

`set_version_publication` moved both sheets together, as designed; `validate_repo_db.py`
passes 9 checks, `check_run_ledger.py` reports no committed row lost, and
`core/tests/test_audit_gate.py` passes 56 checks with the new artifact on disk.

## 2. The sheets

| sheet | population | note |
|---|---|---|
| `H-JOBPOST-01__v1.1__review.md` | 3 of 3 | was 21; the other 18 moved to v1.3/v1.4 in later runs |
| `H-JOBPOST-01__v1.3__review.md` | 13 of 13 | was 25; 12 moved to v1.4 |
| `H-FMCSA-01__v1.3__review.md` | 4 of 4 | new. Run HR-0034, 2026-09-01, company A024 (O00391–O00394), all grade A, three `weak_clue`, one `measured_result` |

The FMCSA v1.3 case is worth a line in the conventions file when there is time: a version
that is in the grandfather registry can still hold quarantined rows, because the exemption
is per version while the run context quarantines on write. Nothing in check 9 is wrong
about it; it just means "grandfathered" does not imply "nothing of this version awaits a
verdict".

## 3. The queue

`REVIEW_QUEUE_2026-09-04.md`, 58 rows: JOBPOST 32 (v1.4 16, v1.3 13, v1.1 3),
SELLERCONTENT v1.4 13, WAYBACK v1.3 5 (each tagged **[CONFOUND-ADMITTED]**), FMCSA v1.3 4,
PRODUCTQUALITY v1.4 2, TRADEPRESS v1.5 2. 20 of the 58 are low-grade and tagged as such.

The verdict line carries the gate's four verdicts, with the brief's labels mapped:
"overstated" is `overgraded`; "reject" is either `unsupported` or `wrong_entity`, and the
sheet asks Matthew to keep those two apart because a single `wrong_entity` holds the whole
version in quarantine (stop rule 1) while `unsupported` only deletes the row.

Carried and untouched, per the brief: FMCSA v1.4 (9, sheeted), WAYBACK v1.2 (7, sheeted),
and FMCSA's 20 held conflicts on released pilot rows O00002–O00027, which exist only in
`harness_output/H-FMCSA-01/run-2026-09-03.json` and not in the workbook.

## 4. Item 5, as planned

Per row: `supported` releases unchanged; `overgraded` goes through
`core/db.py::apply_audit_verdict` with the named field change; `unsupported` /
`wrong_entity` delete the row (the writer refuses to park them). Then one artifact per
version through `write_audit_artifact.py`, `set_version_publication` for each version
whose artifact passes, and a fresh quarantine table from the workbook rather than from
this report.

## 5. Item 5, as executed (2026-09-05)

Matthew reviewed each of the 58 rows individually and relayed the result on 2026-09-05 as
one statement, every line supported, rather than marking the page line by line. (An earlier
text of this report and of the eight artifacts called that a blanket approval; Matthew
corrected it the same day, and the artifacts, the 58 reviewer notes and the queue banner
were rewritten.) Recorded as follows, in the gate's order:

1. **58 verdicts.** Each queued row was confirmed still quarantined and unjudged, then
   `apply_audit_verdict(id, "supported", "Matthew Lebrecht", note)` was called on it. The
   note names the queue and the date the result was relayed. `review_source = human`,
   `review_status = accepted`, no field moved.
2. **8 artifacts**, one per version, through `write_audit_artifact.py`. Each is a census
   (random control n = population), precision n/n, exclusions 0, verdict PASS. Every
   `summary_md` says the verdicts came from the consolidated queue rather than the
   version's own sheet, that each row was reviewed individually, and how many rows are
   low-grade.
   Per-version notes: JOBPOST v1.1/v1.3 populations are the rows left after later runs
   moved the rest forward; WAYBACK v1.3 is five confound-admitted rows approved with the
   tag visible; FMCSA v1.3 coexists with its grandfather entry and counts only the 4
   HR-0034 rows; PRODUCTQUALITY v1.4's session 10 sidecar carried a JOBPOST run id
   (HR-0056) and the artifact records HR-0055.
3. **8 versions published** through `set_version_publication`, which refuses without a
   passing artifact. Runs flipped: HR-0056, HR-0039, HR-0032/33/35/36, HR-0040, HR-0049,
   HR-0034/37, HR-0050/55, HR-0051.
4. **Sheets regenerated** so each shows RECORDED VERDICT rather than an empty prompt. The
   FMCSA v1.3 sheet needed a second sampler option, `--ids`, because `--only-quarantined`
   selects nothing once the rows are released; the sheet records the option used.
5. **The queue is marked**: an approval banner at the top and `[x] supported -- recorded
   2026-09-05` on all 58 verdict lines.

Checks after: `validate_repo_db.py` 9 checks pass (check 9: 33 published versions, 16
audited, 17 grandfathered, 11 quarantined runs, 2 superseded), `check_run_ledger.py` no
committed row lost, `test_audit_gate.py` 56 checks pass.

| state | 2026-09-03 | after item 1 | after item 5 |
|---|---|---|---|
| released | 387 | 451 | **509** |
| quarantined | 138 | 74 | **16** |
| human-reviewed | 77 | 77 | **135** |

Remaining quarantine, from the workbook: H-FMCSA-01 v1.4 9, H-WAYBACK-01 v1.2 7. Both are
low-grade, both sheeted, both carried untouched per the brief. FMCSA's 20 held conflicts
are likewise untouched.

The next queue, `harness_output/audits/REVIEW_QUEUE_2026-09-05.md`, holds the last 16
quarantined rows (FMCSA v1.4 9, WAYBACK v1.2 7, all low-grade). Judging it empties the
quarantine.

## Files

- New: `harness_output/audits/H-SAFETY-ENV-01__v1.3.json`, `H-FMCSA-01__v1.3__review.md`,
  `H-FMCSA-01__v1.3__strata.json`, `REVIEW_QUEUE_2026-09-04.md`, this report.
- Rewritten: `H-JOBPOST-01__v1.1__review.md` / `__strata.json`, `H-JOBPOST-01__v1.3__review.md`
  / `__strata.json`.
- Changed: `data/market_intel_db.xlsx` (65 cells: one run row, 64 observation rows),
  `scripts/audit_sample.py` (`--only-quarantined`), `CLAUDE.md`.
- 2026-09-05: eight artifacts `H-JOBPOST-01__v1.4.json`, `__v1.3.json`, `__v1.1.json`, `H-SELLERCONTENT-01__v1.4.json`, `H-WAYBACK-01__v1.3.json`, `H-FMCSA-01__v1.3.json`, `H-PRODUCTQUALITY-01__v1.4.json`, `H-TRADEPRESS-01__v1.5.json`; eight review sheets and strata sidecars regenerated; `REVIEW_QUEUE_2026-09-04.md` marked; the workbook (58 observation rows, 13 run rows); `scripts/audit_sample.py` (`--ids`); `CLAUDE.md`.
- Committed 2026-09-05.
