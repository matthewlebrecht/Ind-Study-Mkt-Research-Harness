# Session 12.5 Report — Quarantine Emptied, FMCSA Conflicts Accepted

**Date:** 2026-09-05
**Brief:** Matthew's two instructions following the session 12 hand-off: the final 16
quarantined rows were each reviewed individually and are all supported; and for all 20
H-FMCSA-01 held conflicts, accept the harness's proposed values and overwrite the
human-reviewed values. Both executed. One harness ran (H-FMCSA-01 v1.5, offline replay,
`--refresh-reviewed --commit`). No code changed.

## In one screen

| # | item | outcome |
|---|---|---|
| 1 | The last 16 quarantined rows | **Released.** 16 `supported` verdicts recorded row by row; artifacts `H-FMCSA-01__v1.4.json` (9) and `H-WAYBACK-01__v1.2.json` (7) written; both versions published; `REVIEW_QUEUE_2026-09-05.md` marked. |
| 2 | FMCSA's 20 held conflicts | **Accepted.** The harness's `--refresh-reviewed` opt-in rewrote the 20 rows from the cached SAFER snapshot (run HR-0057), Matthew's acceptance was recorded on each as a `supported` verdict, `H-FMCSA-01__v1.5.json` written, v1.5 published. §2 has the field-by-field diff. |

**Quarantine: 0 of 525.** Released 525. Human-reviewed rows 151 (was 135 after session 12,
77 before it). Check 9: 36 published versions, 19 audited, 17 grandfathered, 0 quarantined
rows, 8 quarantined runs that wrote nothing (EMPREVIEW, EXECVOICE v1.4/v1.5, LEGAL v1.2,
PQ v1.0/v1.3, TRADEPRESS v1.4), 2 superseded.

## 1. The 16

Same path as the 58 on 2026-09-05: each row confirmed still quarantined and unjudged, then
`apply_audit_verdict(id, "supported", "Matthew Lebrecht", note)`, the note naming the queue
and the relay date. Each artifact is a census (9 of 9, 7 of 7), verdict PASS, and its
summary says the rows were reviewed individually on the consolidated queue rather than on
the version's own sheet. All 16 are low-grade; the artifacts say approving them endorses
the convention 41 admission for those gates (FMCSA thin-corroboration carrier matches;
WAYBACK single-capture removals).

## 2. The 20 FMCSA conflicts

**What they were.** The v1.3 run of 2026-09-01 and the v1.5 run of 2026-09-03, both
replaying the 2026-09-01 SAFER cache partition, each re-derived 20 released pilot-company
rows (O00002..O00027, C0001..C0008) and found them different from what a person had
accepted (11) or corrected (9) in Week 1-2. Under convention 35
the writer held them and reported the conflict instead of overwriting.

**The decision.** Accept the harness's values on all 20; overwrite the human values.

**How it was executed.** Through the harness's own opt-in rather than a hand edit:

```
python harnesses/h_fmcsa_01/harness.py --offline --refresh-reviewed --commit
```

A dry run first showed exactly 20 refreshed, 19 unchanged, 0 inserted, 0 held, and the
commit matched it. The refresh rewrote every non-protected column of the 20 rows, preserved
`review_status` / `review_source` / `reviewer_notes` (stamping the notes with the refresh),
cleared the now-stale `audit_verdict`, and re-versioned the rows to v1.5 in quarantine,
as any changed row is. Matthew's acceptance was then recorded on each row as a `supported`
verdict whose note names the decision, the two runs that held the conflict, and the cache
partition. The v1.5 artifact is a census of the 20 and says plainly that 20 of 20 supported
is the acceptance decision applied to each row, not an independent re-reading of 20 SAFER
snapshots. v1.5 was then published, which also flipped HR-0052 (the 2026-09-03 run that
wrote nothing). The 9 rows previously `corrected` are now `accepted`, and each note says
why: the values the correction attached to were replaced by decision.

**What actually changed.** Less than the conflict count suggests:

- All 20: `publication_date` 2026-08-23 -> 2026-08-31 (the snapshot date the cached
  SAFER page carries). That alone made every row's fingerprint differ.
- 10 rows: `observation_text` changed, and in 4 of them only in the
  stated 24-month window wording that follows from the snapshot date.
- 6 rows: the underlying counts moved between the Week 1 read and the 2026-08-31
  snapshot: Western Express (vehicle and driver out-of-service inspections and a crash
  total 616 -> 614), Venture Transport (out-of-service percentage 19.9% -> 20.1%, driver
  inspections 954 -> 950, crashes 96 -> 99). Small, and in both directions.
- No row changed `signal_strength`, `source_grade`, `organizational_state` or
  `confidence_0_1`.

| id | company | topic | prior status | substantive change |
|---|---|---|---|---|
| `O00002` | Midmark | `operating_model` | accepted | none beyond the snapshot date |
| `O00003` | Midmark | `crash_exposure_rate` | accepted | text at char 134: `...shes (0 fatal, 0 injury, 1 tow-away) in the 24 months to 08/23/2026. Fleet size (2 power units) is below the 20-unit floor this harness requ` -> `...shes (0 fatal, 0 injury, 1 tow-away) in the 24 months to 08/31/2026. Fleet size (2 power units) is below the 20-unit floor this harness requ` |
| `O00005` | Mack Group | `operating_model` | accepted | none beyond the snapshot date |
| `O00007` | Duke Manufacturing | `operating_model` | accepted | none beyond the snapshot date |
| `O00008` | Duke Manufacturing | `registry_record_maintenance_lag` | accepted | none beyond the snapshot date |
| `O00010` | Western Express | `operating_model` | accepted | none beyond the snapshot date |
| `O00011` | Western Express | `vehicle_maintenance_out_of_service_rate` | corrected | excerpt: `Vehicle Inspections: 7324 \| Out of Service: 2235 \| Out of Service %: 30.5% \| Nat'l Aver ...` -> `Vehicle Inspections: 7319 \| Out of Service: 2232 \| Out of Service %: 30.5% \| Nat'l Aver ...` |
| `O00012` | Western Express | `driver_compliance_out_of_service_rate` | corrected | excerpt: `Driver Inspections: 11843 \| Out of Service: 227 \| Out of Service %: 1.9% \| Nat'l Averag ...` -> `Driver Inspections: 11830 \| Out of Service: 229 \| Out of Service %: 1.9% \| Nat'l Averag ...` |
| `O00013` | Western Express | `crash_exposure_rate` | corrected | excerpt: `Crashes — Fatal: 13 \| Injury: 172 \| Tow: 431 \| Total: 616` -> `Crashes — Fatal: 13 \| Injury: 170 \| Tow: 431 \| Total: 614` |
| `O00015` | Venture Logistics | `operating_model` | corrected | none beyond the snapshot date |
| `O00016` | Venture Logistics | `vehicle_maintenance_out_of_service_rate` | corrected | excerpt: `Vehicle Inspections: 497 \| Out of Service: 99 \| Out of Service %: 19.9% \| Nat'l Average ...` -> `Vehicle Inspections: 497 \| Out of Service: 100 \| Out of Service %: 20.1% \| Nat'l Averag ...` |
| `O00017` | Venture Logistics | `driver_compliance_out_of_service_rate` | corrected | excerpt: `Driver Inspections: 954 \| Out of Service: 10 \| Out of Service %: 1.0% \| Nat'l Average % ...` -> `Driver Inspections: 950 \| Out of Service: 10 \| Out of Service %: 1.1% \| Nat'l Average % ...` |
| `O00018` | Venture Logistics | `crash_exposure_rate` | corrected | excerpt: `Crashes — Fatal: 3 \| Injury: 33 \| Tow: 60 \| Total: 96` -> `Crashes — Fatal: 3 \| Injury: 35 \| Tow: 61 \| Total: 99` |
| `O00020` | Venture Logistics | `multi_entity_operating_structure` | accepted | none beyond the snapshot date |
| `O00022` | Kenco Group | `operating_model` | accepted | none beyond the snapshot date |
| `O00023` | Kenco Group | `vehicle_maintenance_out_of_service_rate` | corrected | text at char 145: `...8.2% across 110 roadside inspections in the 24 months to 08/23/2026, 14.06 points below the national average of 22.26%.` -> `...8.2% across 110 roadside inspections in the 24 months to 08/31/2026, 14.06 points below the national average of 22.26%.` |
| `O00024` | Kenco Group | `driver_compliance_out_of_service_rate` | corrected | text at char 144: `...1.5% across 199 roadside inspections in the 24 months to 08/23/2026, 5.17 points below the national average of 6.67%.` -> `...1.5% across 199 roadside inspections in the 24 months to 08/31/2026, 5.17 points below the national average of 6.67%.` |
| `O00025` | Kenco Group | `crash_exposure_rate` | accepted | text at char 141: `...shes (0 fatal, 0 injury, 4 tow-away) in the 24 months to 08/23/2026 — 2.5 per 100 power units.` -> `...shes (0 fatal, 0 injury, 4 tow-away) in the 24 months to 08/31/2026 — 2.5 per 100 power units.` |
| `O00026` | Kenco Group | `multi_entity_operating_structure` | accepted | none beyond the snapshot date |
| `O00027` | PLS Logistics | `operating_model` | accepted | none beyond the snapshot date |

**A note on the record.** HR-0057 wrote no Attempts rows and publishes `n/a` coverage, as
HR-0052 did before it. That is how this harness behaves on an offline replay; the run is
recorded for its 20 refreshed rows, not for coverage. The sampler's `--ids` option, added
in session 12, is what made a v1.5 sheet possible for exactly these 20 rows.

## 3. State after this session

| | 2026-09-03 | after session 12 | after 12.5 |
|---|---|---|---|
| released | 387 | 509 | **525** |
| quarantined | 138 | 16 | **0** |
| human-reviewed | 77 | 135 | **151** |
| audited versions (check 9) | 7 | 16 | **19** |

Released by harness: FIRSTPARTY 230, SAFETY-ENV 131, SELLERCONTENT 44, FMCSA 40, JOBPOST 32,
WAYBACK 31, EXECVOICE 8, TRADEPRESS 5, PRODUCTQUALITY 3, LEGAL 1.

Nothing is held for review anywhere: no quarantined rows, no held conflicts. The next run
of any harness starts the cycle again, and a re-run of H-FMCSA-01 will now reproduce the
20 rows unchanged rather than hold them.

## Files

- New: `harness_output/audits/H-FMCSA-01__v1.4.json`, `H-WAYBACK-01__v1.2.json`,
  `H-FMCSA-01__v1.5.json`, `H-FMCSA-01__v1.5__review.md`, `H-FMCSA-01__v1.5__strata.json`,
  `harness_output/H-FMCSA-01/run-2026-09-05.json` (ignored), this report.
- Rewritten: `H-FMCSA-01__v1.4__review.md` / `__strata.json`, `H-WAYBACK-01__v1.2__review.md`
  / `__strata.json` (now show the recorded verdicts), `REVIEW_QUEUE_2026-09-05.md` (marked).
- Workbook: 36 observation rows touched (16 verdicts; 20 refreshed and then verdicts), one
  new run row HR-0057, three run rows flipped to published (HR-0046, HR-0047, HR-0052 with
  HR-0057).
- `CLAUDE.md` updated.
