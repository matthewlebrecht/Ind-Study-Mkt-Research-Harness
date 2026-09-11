# Session 14 Report — Week 3 Wrap-Up (Overnight Build)

**Date:** 2026-09-06
**Brief:** session 14, eleven items (0a, 0b, 1–9). Run unattended and committed. Nine
harness runs recorded (HR-0058 to HR-0064 plus two dry runs), one migration applied twice,
one new harness package, one new registry sheet, two conventions. The FMCSA API raised no
issue; the one problem on that path was ours (the key never reached the harness) and is fixed.

## In one screen

| # | item | outcome |
|---|---|---|
| 0a | Append DR-0001 | **Done, verified identical to the preview**: 3,240 rows, `theme_not_detectable` 1,620 / `no_absence_license` 1,371 / `observed` 231 / `no_reach` 18 / `absent` 0. A DR-0002 dry run at the end of the session differs in 0 rows, so nothing was appended. |
| 0b | Stale `absence_licensed` flag | **Fixed at the root.** The flag is deleted from `core/topics.py`; `gap_report.py` reads `core/composition.py::absence_licensing`, the same declarations the derivation composes on. No theme prints "buyer silent". **cybersecurity is now "no absence license"** (formally untested, a portfolio gap); cloud_infrastructure_migration shows one released buyer row and reads "covered". §1 has the language consequence. |
| 1 | Stable observation ids | **Designed, implemented, migrated.** `Observation_Ids` registry (convention 43); a claim keeps its id across delete-and-rewrite, a retired id is never reused; 24 historical ids backfilled from git; check 10; 11-check test. No existing id renumbered. §2. |
| 2 | EXECID low-grade tier | **Built as v1.1 and committed (HR-0064)**: 110 low-grade executives (94 E26 with an out-of-vocabulary title, 16 E32 untitled), 7 new confirmed, 21 refreshed, 9 departures. Three guards were needed before the sample was clean. §3. |
| 3 | EMPREVIEW retry | **Still blocked, live (HR-0059): 107 of 108 `access_blocked`.** Glassdoor, Indeed, CareerBliss refuse by robots.txt; Comparably trips the circuit breaker. Nothing changed at the source. |
| 4 | H-VENDOR-01 | **Built and run (HR-0063), 0 rows.** 13 usable seeds, 6 pages read and about the company, 2 speakers named with titles, no theme admitted. §4. |
| 5 | TRADEPRESS live | **Run on the seeded 15-company subset (HR-0061): 5 proposed, 4 unchanged, 1 held, 0 new.** The 10 added outlets reached 4 articles and yielded nothing admissible. Full universe is blocked on `Companies.industry_primary`. §5. |
| 6 | O00369 / O00373 | **Accepted and published** (H-EXECVOICE-01 v1.5, HR-0060) via `--refresh-reviewed --refresh-ids`. Both are now low-grade: the harness's current value rests on a single generic term. O00372 (Prime Inc., `corrected`) is the third held row and was not part of the decision. |
| 7 | PQ sidecar run id | Already HR-0055 (corrected when the sheet was regenerated in session 12.5). Nothing to do. |
| 8 | FMCSA F15/F26 | **Verified live** on the QCMobile path with the webkey (dry run, v1.6): Midmark reads Private Property and its NOT AUTHORIZED status is explained as private carriage; Western Express and Kenco read Authorized For Hire; no false authority gap. Three fixes; not committed. §6. |
| 9 | Qualification rule | **Formalised** in `docs/conventions.md` 18 (amended): established platform plus active modernization hiring is a positive signal and qualifies. Archive docs annotated. |

**State (from the workbook):** 525 observations, 525 released, 0 quarantined, 151
human-reviewed, 190 low-grade; 64 runs; 6,085 attempts; 931 executives; 3,240 history rows;
549 observation ids ever assigned, 24 retired. Check 9: 37 published versions, 20 audited, 17
grandfathered, 10 quarantined runs that wrote nothing. Every check and every test passes
(validate 10/10, assert_validations, check_run_ledger, 12 test files).

## 1. The gap report's language changed, and prior write-ups are affected

The original gap report named cloud_infrastructure_migration and cybersecurity as the two
candidate divergences: provider messaging with zero buyer signal. Session 13's derivation
showed that no instrument in the portfolio may read silence on any theme as absence today,
and the flag the gap report used to say otherwise had been set before that condition
existed. As of this session:

- **cybersecurity: "no absence license".** Four providers message it, no released buyer row
  carries it, and every instrument that could see it is IC1/IC2 or presence-only. This is
  taxonomy §26's "formally untested": a gap in the portfolio, not a market finding, and not
  a divergence. What would change it is an IC3/IC4 instrument that is not presence-only
  reaching the theme: H-JOBPOST-01 once its readability denominator is accepted, or a state
  AG breach-portal harness.
- **cloud_infrastructure_migration: "covered"** with one released buyer company (a
  FIRSTPARTY v1.2 row), so it is no longer a zero-signal theme at all.

Any sentence in an earlier report or in the Notion log that calls either of these a
"candidate divergence" or "buyer silent" is superseded by this characterisation. The report
legend now carries four rows (covered / no absence license / buyer silent / NO INSTRUMENT)
and the CSV snapshot (`data/snapshots/gap_report.csv`) is regenerated.

## 2. Stable observation ids (convention 43)

**Design.** An id belongs to its natural key (`company_id`, `harness_id`, `topic`,
`source_url`) forever. A new sheet, `Observation_Ids`, holds every id ever assigned with its
key, `first_assigned`, `status` (live / retired), `retired_at`, `retired_note`.

**Mechanics, all in `core/db.py`.** Every insert path (`append_observations`, the insert
branch of `sync_observations`) asks the registry first: a retired id for the same key is
reused and marked live again; otherwise a fresh id is allocated above the highest id ever
assigned, live or retired. Every delete path (`delete_observations`, `retire_unreproduced`)
retires the id in the registry with a note. A key that already has a live id cannot be
allocated a second one.

**Migration.** `migrate_schema.py` created the sheet and registered the 525 live ids;
`scripts/backfill_observation_ids.py` walked the workbook's 30 commits and registered the 24
ids that once existed and were renumbered or removed (nine SELLERCONTENT v1.2 rows retired by
the pattern fix, eight EXECVOICE v1.1 rows, the five session-10 renumberings, one LEGAL v1.0,
one PRODUCTQUALITY v1.3). No live id changed.

**Enforcement.** `validate_repo_db.py` check 10 fails on a live id missing from the
registry, a key that drifted, a registry id marked live with no row, or a key with two live
ids. `core/tests/test_stable_ids.py` proves the three properties on a workbook copy.

## 3. EXECID v1.1: the tier that had to be built three times

The first dry run of the tier as designed (out-of-vocabulary title admitted as written;
untitled name on a leadership page admitted) proposed 735 low-grade executives, and a sample
of 30 held two people. The rest were navigation menus: "Texas Region President", "Student
Programs" / "Engineering Internship Program", "Infrastructure Modernization" / "Overview".
Two capitalised tokens beside another short label satisfy every shape test. Convention 16.

Three guards made it a tier: a candidate name may not carry a role word ("General Counsel")
or a domain noun ("Region", "Services"); an E26 title must itself be role-shaped; and a
low-grade record must sit within 8 lines of a confirmed person, because rosters cluster and
menus do not. After that: 110 low-grade rows (94 E26, 16 E32), and a 45-row sample is people
with titles like "Director of Preconstruction", "Regional President, Mountain States",
"Controller". One dubious survivor ("Coastal Cares" with a prose title) is in the sheet at
grade C and marked. `db.sync_executives` accepts an empty title only on a row that is grade
C, `role_relevance unconfirmed`, confidence ≤ 0.4. EXECVOICE reads primary names only, so
none of this reaches the evidence base without a decision.

The same run re-read every leadership page live: 21 confirmed rows refreshed, 9 marked
superseded because a re-read authoritative page no longer lists the person.

## 4. H-VENDOR-01: built, calibrated, zero rows

Seeds: 24 URLs from the EXECVOICE logs. Nine excluded before reading (eight
appsruntheworld.com aggregator profiles, one Grant Thornton provider page). Of the 13 read
live: one host refuses by robots.txt (cioreview.com), six fail the first-party identity test
(a Tidal case study about Jackson National Life logged against Brasfield & Gorrie; a
contractor's testimonials page logged against McGough; and so on: EXECVOICE excluded these
by URL shape, not by reading them), six are about the company.

The first extraction wrote two Joeris rows from a 350-character navigation "sentence" that
happened to hold the company name, a product list and a theme term. Sentence hygiene (length
cap, navigation markers) removed them. Quote attribution now handles "said senior project
manager JB Peel" and surname-only follow-ups, and names Tony Moreno (project manager) on the
OpenSpace page; his quotes carry no spine theme. The deployments the six pages describe
(360° site capture, enterprise-architecture mapping, an e-commerce platform) are not
modernization themes in the spine, so the honest yield is zero and the run is
`absent_confirmed` for those six companies. Quarantined, population 0; an artifact can be
written on the PQ v1.2 precedent when Matthew wants it published. Not a theme instrument in
composition (§24.3: volume, not widening).

## 5. TRADEPRESS live: the expansion measured

The harness's scope is a hand-seeded 15-company subset with per-company outlet verticals;
`Companies.industry_primary` is blank for all 100 Anvil rows and the module refuses to guess
(convention 13), so a full-universe run is a data-enrichment task first. The subset ran live
with the 10-host expansion: 5 rows proposed, 4 already in the sheet, 1 human-reviewed row
held because its re-derivation differs, 0 new. The added outlets produced 4 article reads
(Trucking Dive, Grocery Dive, AndNowUKnow, Food Logistics) and nothing admissible. The run's
held id was not captured because the harness did not log conflicts until this session; it
does now.

## 6. FMCSA F15/F26, and why it is not committed

The webkey was set, and the first live run still took the SAFER HTML path: `source.py` read
the key from the process environment and nothing loaded `.env` for it. Fixed to read
through `core.config`. Then QCMobile served the national-average rates as strings and the
first carrier crashed on `rate - natl`; every numeric field is now coerced once. Then the
private-carriage test matched SAFER's "Auth. For Hire" but not QCMobile's "Authorized For
Hire"; it now matches "for hire". With those three, on C0001 / C0004 / C0006: classification
read from the sub-endpoint, private carriage recognised, no false authority gap, no
unknown-classification skip. F15/F26 resolve. Recorded as v1.6.

Not committed, because the QCMobile record has no entity-type field and reports
`Interstate` where SAFER reports the authority type, so every operating_model row differs in
text from the reviewed pilot rows and a commit would re-open all 20 as conflicts again. Two
field mappings for Week 4.

## 7. Runs recorded this session

| run | harness | what |
|---|---|---|
| HR-0058 | EMPREVIEW v1.1 | offline replay; failure categories are cache artifacts (`source_unavailable`) |
| HR-0059 | EMPREVIEW v1.1 | live: 107 `access_blocked`, the truthful record |
| HR-0060 | EXECVOICE v1.5 | O00369 / O00373 refreshed; published |
| HR-0061 | TRADEPRESS v1.5 | live subset, 0 new rows |
| HR-0062 | VENDOR v1.0 | offline replay of the live dry run; C0008 reads `source_unavailable` |
| HR-0063 | VENDOR v1.0 | live: C0008 `access_blocked`, the truthful record |
| HR-0064 | EXECID v1.1 | 117 executives inserted |

HR-0058 and HR-0062 exist because an offline replay cannot re-run a robots check or a
circuit breaker and records the missing response as unavailable. Both are superseded in
meaning by the live run that follows them; `superseded` is a per-version status, so they
keep `quarantined`. Lesson for the conventions file: commit access findings live.

## 8. Is Week 3 closed?

Yes for everything the brief listed. What Week 4 inherits, none of it a blocker:

1. **No licensed-absence instrument exists.** Every "silent" theme is formally untested
   until H-JOBPOST-01's readability denominator is accepted or an IC3/IC4 harness lands.
2. **`Companies.industry_primary` is blank**, which caps TRADEPRESS at 15 companies. OSHA
   inspection records in the SAFETY-ENV archive carry NAICS codes; that is the cheapest
   enrichment path.
3. **FMCSA QCMobile field mappings** (entity type, authority type) before a v1.6 commit.
4. **H-VENDOR-01 population-0 artifact** if it is to publish; and the spine has no theme
   for site-capture, EA-mapping or e-commerce deployments, which is a scope statement rather
   than a gap.
5. **The EXECID low-grade tier is unreviewed**: 110 rows at grade C in `Company_Executives`,
   never read by EXECVOICE unless promoted.
6. **DR-0002 is identical to DR-0001**; the history table changes when a run writes or
   changes a released buyer row, and W37 opens on 2026-09-07 with `ot_modernization`
   detectable for the first time.

## Files

- New: `core/composition.py::absence_licensing`; `Observation_Ids` sheet;
  `scripts/backfill_observation_ids.py`; `core/tests/test_stable_ids.py`;
  `harnesses/h_vendor_01/` (package, manifest); `H-EXECVOICE-01__v1.5.json` and its sheet;
  this report.
- Changed: `core/db.py` (registry, `refresh_ids`, empty-title rule), `core/topics.py` (flag
  removed), `scripts/gap_report.py`, `scripts/migrate_schema.py` (registry sheet, vocabulary,
  validation, SRC-0018 reach), `scripts/validate_repo_db.py` (check 10),
  `harnesses/h_execid_01/` (v1.1), `harnesses/h_execvoice_01/harness.py` (refresh flags, held
  logging), `harnesses/h_fmcsa_01/` (v1.6), `harnesses/h_tradepress_01/harness.py` (held
  logging), `docs/conventions.md` (18 amended, 43), two archive docs, `CLAUDE.md`,
  `data/snapshots/gap_report.csv`, the workbook.
