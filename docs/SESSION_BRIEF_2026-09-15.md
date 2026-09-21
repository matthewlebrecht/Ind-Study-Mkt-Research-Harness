# Session brief — 2026-09-15

Written at the close of the session for whoever picks this up next. It assumes you cannot see that session's
conversation. Everything here is checkable in the repository; where a number is quoted, the script that recomputes it is
named. `CLAUDE.md` is the current-state file and was updated throughout; `docs/conventions.md` is authoritative where
the two ever disagree.

All decisions below were made by **Matthew Lebrecht** and relayed through a coordinator. Nothing was decided by Claude
Code. Where a decision is still open it says so.

---

## 1. What was decided today

| # | Decision | Where it now lives |
|---|---|---|
| 1–4 | **No observation is ever hard-deleted, and the rule is retroactive.** Retirement becomes an invalidation status; the extraction fix's losses stay in the base flagged invalid | convention 45 in `docs/conventions.md`; `core/validity.py`; check 15 in `scripts/validate_repo_db.py` |
| 5 | **O00349 is `wrong_entity`** | OVH-0011; `harness_output/audits/VALIDITY_2026-09-15_O00349.json` |
| 6 | **O00350, O00530, O00531 go on a sheet showing the separate entity** (Front Line Power Construction) | `harness_output/audits/REVIEW_QUEUE_2026-09-15_firstparty_page_furniture.md`, section "Added 2026-09-15 (item 6)" |
| 7 | **The three Caddell cookie-banner rows are invalidated** | OVH-0012..0014; `VALIDITY_2026-09-15_caddell_cookie_banner.json` |
| 8 | **Fix the extractor and recover O00307 and the Yahoo rows** | `harnesses/h_firstparty_01/body.py` (v1.3); `core/tests/test_firstparty_body.py` |
| 9 | **Lift the TRADEPRESS hold once its typo fix lands** | v1.8; `core/holds.py` (entry removed, history kept) |
| 10 | **Release PROCUREMENT v1.4** | `harness_output/audits/H-PROCUREMENT-01__v1.4.json`; HR-0081 published |
| 11 | **Supersede BREACHPORTAL v1.1** | HR-0069 `superseded`; check 9 accepts it (the version holds no rows) |
| 19 | **Composition, published coverage and the reconciler read an invalid row as invalid**, and every published count reports **total, valid and invalid** as three measurements — never a silent net | `core/validity.py::invalid_observation_ids` + `READERS`; `core/composition.py`; `scripts/published_coverage.py`; `scripts/gap_report.py`; `core/db.py::sync_observations` |
| 20 | **Record the current id of each renumbered observation id** | `Observation_Ids.current_id`; `scripts/record_id_lineage.py`; `ID_LINEAGE_2026-09-15.json` |
| 21 | **A determination is permanent** — no reinstating status | convention 45; documented, no code needed |
| 22 | **Lift the FIRSTPARTY hold, run v1.3, and record the rows it stops producing as `invalidated_extraction_defect`** (the status must name the reason, not be relabelled afterwards) | `core/validity.py::invalidate_unreproduced(status=, basis=)`; run HR-0083 |

### Conventions added or amended today

- **Convention 45 — no observation is ever hard-deleted** (`docs/conventions.md`). A bad observation keeps its row and
  its id; its invalidity is a determination appended to `Observation_Validity_History`. Retirement is invalidation.
  Every `core/db.py` delete path refuses. Enforced by check 15, which fails on a retired id whose claim has no live row
  and on `delete_rows(` reappearing in `core/db.py`. Both failure directions were tamper-probed.
- **Convention 41's wall, amended** (the pattern first used for coherence tags and directionality tags): a table that
  overlays observations sits behind a wall, and no gate-computing module may read it. Today validity became the first
  *permitted* reader case: exactly three modules (`core/composition.py`, `scripts/published_coverage.py`, and
  `core/db.py` inside `sync_observations` only) may read it, and only through `invalid_observation_ids`. Everything else
  is still a failure. The scan is `core/validity.py::wall_violations`; the tamper probes are in
  `core/tests/test_validity_consumers.py`.
- **Convention 44** (optional classifications live in their own linked table) was followed again for
  `Observation_Validity_History` and for `Observation_Ids.current_id`'s companion rule.

---

## 2. Today's commits, in order

| Hash | What |
|---|---|
| `f21f5d9` | BREACHPORTAL v1.2 published (zero-row precedent); O00791 judged supported and held; buyer_articulates role review drawn (59 of 249) |
| `f7d6d78` | `audit_sample.py`: silent 900/600-character caps on review sheets and strata files removed |
| `18e7fa1` | Role-review verdicts recorded: 59 of 249, 58 `correct`, 1 `buyer_acts` (O00303); nothing applied to Observations |
| `1f9ff57` | `Observation_Role_Reviews` built (convention 44, check 14); the 59 verdicts landed there |
| `49307b9` | O00303 reclassified `buyer_articulates` → `buyer_acts` (in place, human-authored) |
| `ba6846a` | O00303's text corrected to match the role; the extraction question left open |
| `5db97fd` | Extraction review sheet: seven page-furniture rows plus O00349 (identity) |
| `b21a24c` | FIRSTPARTY `--retire-stale` added (opt-in; human rows held) |
| `9641128` | The seven rows deleted as `unsupported` on Matthew's verdict; `delete_observation_ids` made all-or-nothing |
| `b63edd3` | FIRSTPARTY and TRADEPRESS put ON HOLD in code |
| `0b1628f` | `Observation_Validity_History` built (convention 45, check 15); O00303 restored exactly and recorded invalid |
| `63bc1ec` | No hard deletion enforced and made retroactive: every delete path refuses; retirement becomes `invalidated_not_reproduced`; nine deleted observations restored and recorded |
| `d37c514` | Invalid rows read as invalid by composition, published coverage and the reconciler; three measurements everywhere (item 19) |
| `6c1767e` | Id lineage: each of the 23 renumbered ids records its current id (item 20) |
| `8676d11` | O00349 recorded `invalidated_wrong_entity` (item 5) |
| `6f93418` | Front Line rows added to the review sheet; O00349's verdict marked (item 6) |
| `2d6638e` | The three Caddell cookie-banner rows recorded invalid (item 7) |
| `407cfd2` | FIRSTPARTY v1.3 built: article-body extraction, five prerequisites, 111 page fixtures, dry run measured — not run (item 8) |
| `ae960f2` | PROCUREMENT v1.4 released: census artifact 1 of 1 supported (item 10) |
| `d6ec8f1` | TRADEPRESS v1.8 marker fixed and its hold lifted (item 9); BREACHPORTAL v1.1 superseded (item 11) |
| `67b0f7c` | FIRSTPARTY hold lifted and v1.3 run: HR-0083, 97 rows recorded `invalidated_extraction_defect`, 18 human rows held (item 22) |

---

## 3. State as it stands

Recompute rather than trust this table: `python scripts/validate_repo_db.py`, `python scripts/check_run_ledger.py`,
`python scripts/published_coverage.py`.

- **722 observations** = 611 valid + 111 invalid. Released 689 (581 valid + 108 invalid); quarantined 33 (30 valid + 3
  invalid). 242 human-reviewed. 210 low-grade. Roles 425 `buyer_acts` / 253 `buyer_articulates` / 44
  `provider_market_responds`.
- **111 validity determinations**: 108 `invalidated_extraction_defect` (10 judged by Matthew, 97 by the v1.3 run, 1
  O00604), 1 `invalidated_duplicate`, 1 `invalidated_not_reproduced`, 1 `invalidated_wrong_entity`.
- **83 runs, 6,972 attempts.** 745 ids ever assigned, 23 retired — every one a pre-rule renumbering that now records its
  `current_id`. **Zero hard deletions.**
- **No harness is held.** `core/holds.py` is empty of entries and keeps the mechanism plus the history.
- **HR-0083 (FIRSTPARTY v1.3) is QUARANTINED**, holding 30 rows. Under the audit gate it publishes nothing until an
  artifact exists at `harness_output/audits/H-FIRSTPARTY-01__v1.3.json`. **That audit is the obvious next task.**
- Check 15 warns that `Company_State_History` cites 92 invalidated observations in 294 citations. That is expected:
  derivations are immutable history. **No new derivation (DR-0003) was appended today**; a dry run is
  `python scripts/derive_state_history.py --as-of <date>`.

---

## 4. Open items, in the numbering Matthew has been using

- **12 — the 34 unreviewed business-journal rows.** Matthew said "now". It was flagged before v1.3 that reviewing them
  under v1.2 would measure the extraction bug rather than the channel. v1.3 has now run, so the sheet should be drawn
  from the current base; many of those rows are among the 97 just recorded invalid. Not started.
- **13 — the attempts-side control for H-PRODUCTQUALITY-01.** Its origin: v1.2 (HR-0026) wrote zero rows but published
  13.89% coverage — 14 `absent_confirmed`, 93 `source_not_found`, 1 covered. Every audit stratum samples rows that were
  *written*, so nothing can judge whether those absences are real. The control has to sample **attempts**, not
  observations, with verdicts like "absence confirmed" / "a record exists" / "correctly out of population". Not built.
- **14 — re-run so everything lands under one audited population.** Partly overtaken: FIRSTPARTY v1.3 has run
  (HR-0083). SELLERCONTENT still has no furniture dry run, and the rest of the portfolio is untouched.
- **23 — the Front Line identity verdicts.** O00350, O00530 and O00531 are on the review sheet with both entities shown;
  no verdict recorded. Note the consequence recorded on that sheet: with O00349 invalid, A073's `data_analytics_ai`
  weeks rest on O00350 alone.
- **24 — EXECVOICE's soft-404 detector.** See §5.
- **New today, unnumbered (suggest 25) — 8 of the 97 rows carry a status that overstates the reason.** The v1.3 run
  recorded everything it stopped producing as `invalidated_extraction_defect`, on Matthew's instruction. For 8 rows the
  real reason was different and their matched term is still in the article body: O00297, O00298, O00354, O00355, O00431
  (the body-based identity test — 'SALES', 'BUILDING' absent near the top), O00324, O00325 (staleness: the article
  crossed the five-year line between the dry run and the run), O00359 (theme admission). Whether to supersede them, and
  whether the vocabulary needs a status for identity or staleness, is Matthew's call. `core/tests/test_firstparty_body.py`
  section 9 pins the exception set so it cannot grow unnoticed.

### Items 15–18, verified against HEAD today (Matthew believed these were solved elsewhere; they are not)

- **15 — the ~40 unclear gates: PARTLY DONE.** Session 10 (`64f5b96`) decided most of them (five-year staleness in
  `core/windows.py`, the Wayback confound marker, ST-PRESSCHAR, the PQ symptom cue). **Nine remain undecided with the
  gate unchanged in code:** W4 (`RELEVANT_PATH`), W7 (2-year window), W16 (pre-2015), F4/F5 (inactive −15 and MCS-150 age
  inside the identity test), E8/E9 (own-domain refusal), P2–P4 (population map), S1 (the JS-shell text floor). The
  inventory `docs/diagnostics/gate_inventory_2026-09-03.md` was never updated and still reads "logged for decision";
  it also disagrees with itself on the count (its summary column totals 219).
- **16 — the EXECID low-grade tier: BUILT, NOT AUDITED.** The code and data are real (110 `unconfirmed` rows carrying the
  `[low-grade:` marker). But run **HR-0064 is quarantined**, there is **no audit artifact** for v1.1, and the published
  version is still v1.0 — while the **published** EXECVOICE v1.6 already reads those names
  (`harnesses/h_execvoice_01/harness.py:153`). CLAUDE.md's claim that EXECVOICE does not read them is stale. No tests
  cover the tier.
- **17 — the three SAFETY-ENV candidates: STILL OPEN.** S7 (`absent_confirmed` never written as a negative
  observation), S25 (unknown-status facilities dropped from the violating count, `harness.py:202-204`) and S21 (the 2016
  window, `harness.py:84`) are all unchanged. The manifest records them as deliberately untouched; no decision has been
  made.
- **18 — composition de-duplication and provenance: STILL OPEN.** `core/composition.py::derive` indexes every scoped
  coverage attempt from every published run with no de-duplication and no preference for a newer run; the first attempt
  whose reach covers a bucket wins. `covering_instruments` stores signal names only — no run id, harness version or
  source — and `STATE_HISTORY_COLUMNS` has no provenance column. Today's validity change is about observations and did
  not touch this.

---

## 5. Found and deliberately not fixed

- **EXECVOICE's soft-404 regex is corrupted** (`harnesses/h_execvoice_01/harness.py:129`): literal backspace bytes
  (`\x08`) where `\b` was meant, so the "404 … error/not found" branch can never match. Found by a byte scan after the
  same corruption was fixed in TRADEPRESS (introduced there by `15f7c18`). A task chip was spawned; nothing was changed.
  `core/topics.py`'s `\x1f` is a deliberate separator, not a defect.
- **The EXECID tier** (item 16 above): published EXECVOICE output rests on an unpublished, unaudited EXECID run.
- **The nine undecided gates** (item 15) and **the three SAFETY-ENV items** (item 17).
- **Composition's de-duplication and provenance** (item 18).
- **The 23 renumbered ids are not restorable as rows** — their claims are live under newer ids, so restoring them would
  give one claim two live ids. Their lineage is recorded instead (item 20).

---

## 6. Things a fresh session would otherwise rediscover the hard way

- **Holds.** `core/holds.py` refuses a harness's live runs and every `--commit` before any cache, search client or
  workbook is opened. Two harnesses were held and both were lifted today; the registry is empty. Re-holding one is an
  entry in that file and nothing else. An offline replay without `--commit` is always allowed, and is how every
  measurement today was taken.
- **The 111 page fixtures.** `core/tests/fixtures/firstparty_pages/` holds every page behind a FIRSTPARTY row, gzipped
  (2.7 MB), with `index.json` recording provenance hashes. They exist because the live cache lives under
  `harness_output/`, which git ignores — a test reading it would pass here and fail on a fresh clone, which is exactly
  what happened to the audit artifacts before 2026-09-01. Rebuild with
  `python core/tests/fixtures/firstparty_pages/build_fixtures.py`.
- **The validity table sits behind the convention 41 wall.** Read it only through `invalid_observation_ids`, and only
  from the three permitted modules. Check 15 fails on anything else, including an aliased import.
- **Historical versus live numbers.** Audit artifacts are dated records: their populations and precision rates are what
  was true on their audit date and are **never** rewritten — O00539, for instance, is still recorded `supported` in the
  FIRSTPARTY v1.2 artifact while being invalid today. Live numbers are recomputed by the scripts and carry the
  total/valid/invalid split. Derivations (`Company_State_History`) are immutable history too. `data/snapshots/gap_report.csv`
  is the exception: a living file, regenerate it after any change that moves the table.
- **The reconciler holds human-reviewed rows.** A machine run can never invalidate or overwrite one; it reports them by
  name. 18 were held by HR-0083, including O00303 (human-corrected *and* invalid) and O00539.
- **Convention 37** still applies: when a defect is fixed, re-run the case that exposed it. Every fix today was measured
  against the rows that produced it before being applied.
- **This repository has no remote and must never be pushed** (the workbook is in its history).
