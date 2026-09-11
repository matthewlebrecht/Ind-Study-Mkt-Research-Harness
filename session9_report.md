# Session 9 Report — Fix, Unblock, Volume Policy (overnight, 2026-09-03)

**Brief:** session 9, six items. Everything below ran unattended; nothing is committed.
Matthew released H-SELLERCONTENT-01 v1.3 himself before the session started (three commits
this morning), so item 1 was already closed; the rest is here.

## The six items, in one screen

| # | item | outcome |
|---|---|---|
| 1 | Publish H-SELLERCONTENT-01 v1.3 | **Already done by Matthew** (`93360c9`, 7 of 7 supported, released). Nothing to do. |
| 2 | Job-posting coverage, revised plan | **Platform audit run** over the 94 unreadable companies: no ATS worth an adapter (Dayforce leads at 6); 39 on a plain WordPress page. **Aggregator leg built and run live**: 12 boards probed, 8 refuse by robots, 3 permit but block or serve a JS shell, **Talent.com works**. H-JOBPOST-01 v1.3 live: board leg reaches **56 of 108** companies (53 with ≥1 cross-post resolved to the company), 125 cross-posted postings, 25 rows written, quarantined, review sheet drawn. Coverage target ~70–85% is **not** reached: readable-source coverage is 13% own-domain + 52% aggregator, with heavy overlap and shallow depth. §2. |
| 3 | Audit and close LEGAL v1.1, PQ v1.2 | **Both audited and published.** LEGAL's one row (O00377) judged **overgraded** and retained at confidence 0.35; PQ v1.2 is a population-0 artifact. LEGAL v1.0 marked superseded. Auditor is Claude under your brief, recorded as such in both artifacts. §3. |
| 4 | Theme definitions | **Written into `core/topics.py`** for `systems_integration` and `cloud_infrastructure_migration`, in your words; both themes now admit generic-only text at low grade under item 6. §4. |
| 5 | Nine-vs-ten theme file | **Corrected.** A dated correction header in `signal_advisor_theme_confirmation_2026-09-02.md`: nine confirmed, all supported, the tenth is the split's outcome, the tension is retracted. |
| 6 | Corroboration-gate policy, full portfolio | **Inventoried every harness (411 gates across 12 harnesses + the spine), classified, converted 20 gates in 9 harnesses, replayed all 9 offline with commit: 183 low-grade rows, all quarantined, review sheets drawn.** Full table: `docs/diagnostics/gate_inventory_2026-09-03.md`. Convention 41 written. §6. |

**State:** 517 observations (282 released, 235 quarantined), 48 runs, 4,685 attempts, 120
Companies rows. 11 suites green; 9 validator checks; 26 bindings; ledger clean (no row lost,
+189 observations, +10 runs). 52 files changed or new.

---

## 2. Job-posting coverage

### 2a. The platform-signature audit (`scripts/careers_platform_audit.py`)

Offline, from the careers pages H-JOBPOST-01 had already archived: 90 of the 94 unreadable
companies read (4 not archived). One primary bucket per company, rule printed:

| bucket | companies |
|---|---:|
| static page, no posting-shaped list, no ATS fingerprint | 27 |
| inline static list of postings in server HTML (a generic parser could read it) | 12 |
| JS-rendered shell | 9 |
| known ATS with a public board surface | 39 across **18 platforms** (dayforce 6, adp 4, ultipro/ukg 4, icims 3, jobvite 3, taleo 2, successfactors 2, tenstreet 2, bamboohr 2, nine singletons) |
| apply-link to an off-site host, no fingerprint | 5 |

58 of 90 careers pages are WordPress. Only 2 link to a job board from the company's own
page. **The 3-adapter plan was a placeholder, as the brief said**: the largest platform
covers 6 companies, and the long tail is 18 platforms for 39 companies. The bucket worth an
adapter is not an ATS at all — the 12 inline static lists.
`docs/diagnostics/careers_platform_audit_2026-09-03.md` has every company and its rule.

### 2b. The aggregator leg (`harnesses/h_jobpost_01/aggregator.py`, harness v1.3)

Twelve boards probed through `core/robots.py` under this crawler's own identity:

| board | robots.txt | reachable |
|---|---|---|
| LinkedIn, Indeed, Glassdoor, ZipRecruiter, SimplyHired, Google Jobs, Dice, Monster, Jooble | **refuse** | — |
| CareerJet | permits | JavaScript loader, no results in the HTML |
| Adzuna | permits | 403 behind a bot challenge |
| **Talent.com** | permits | **200, results in server HTML with JSON-LD** |

No user agent switched, no challenge solved, no mirror. The leg has one adapter. Talent.com's
keyword search is full-text, so "Kenco Group" returns 18 cards of which one is Kenco
("Delivery Driver — Kenco Hydraulics" is another company); every card's employer field is
scored against the canonical name at the standard resolution floor and non-resolving cards
are rejected and logged. **The identity gate is not relaxed on this leg**, by design.

Live run tonight (HR-0039, 466 requests):

| | |
|---|---|
| companies with ≥1 cross-post resolved to them | **53 of 108** |
| cross-posted postings resolved | 125 (32 companies with exactly 1; top: Swinerton 26, Savage 10, McCarthy 8) |
| companies with a modernization signal from cross-posts | 5 |
| new-key presence hits | **1**: OnTrac, "GCP Cloud Platform Engineer" → `cloud_infrastructure_hiring` |
| board leg coverage (covered + absent_confirmed) | 56/108 = 51.9% |
| own-domain leg | 13/108 readable this run (was 14: the Walsh iCIMS tenant answered 404 live) |
| rows written | 25 (7 new, 18 refreshed from v1.1), quarantined; sheet at `harness_output/audits/H-JOBPOST-01__v1.3__review.md` |

**What the number means.** The aggregator does reach half the universe, which no adapter
plan does, but it reaches it *shallowly*: Talent.com indexes a handful of a company's
requisitions, not its board (Kenco's 481 Workday postings appear as 1). It is the single
largest coverage jump available and it is a presence instrument only. The realistic
combined figure after this session is **56 of 108 reachable for presence** (13 deep, 43
shallow), not 70–85%. Closing the gap further is the 12 inline-static-list companies (a
generic parser), then Dayforce (6). Companies still unreachable are already classified
through the failure vocabulary (`access_blocked`, `entity_below_threshold`,
`source_not_found`, `content_unstructured`) with the reason in each attempt row; nothing is
a silent gap.

### 2c. The gate on v1.3

Loaded fresh after the run. Population 25; `a_graded` stratum 18 (own-domain rows),
`off_own_domain` 7 (the Talent.com rows, B-graded); random control is a census of 25.
**No coverage number for v1.3 is quoted anywhere in this report.**

## 3. The two audits

**H-LEGAL-01 v1.1, O00377** (Rogers-O'Brien Construction v. Microsoft, W.D. Tex. 2020,
breach of contract): verdict **overgraded**. The referent is right; "bears on systems
integration" rests only on the opposing party being a technology vendor. Retained at
`weak_clue` with confidence 0.6 → 0.35, source grade A kept (the docket is an A record; the
inference is what confidence carries). Under item 6's rule this is a corroboration-strength
weakness, and grading it is the right disposition. Artifact written, run published, LEGAL
v1.0 (0 rows, superseded by v1.1's identical scope) marked `superseded`.

**H-PRODUCTQUALITY-01 v1.2**: population 0 (HR-0026 wrote nothing new; 1 covered = O00366
already audited at v1.1; 14 absent; 93 outside the population map, listed one by one in the
population sheet). Artifact says precision is undefined, not 100%, and licenses the coverage
number only. Published.

Both artifacts name the auditor as Claude Code under your brief and say that is weaker than
independent human judgment. Check 9: 7 audited, 17 grandfathered, 2 superseded.

## 4. Definitions

Your two definitions are in `core/topics.py` as `Theme.definition` (the §25.4 slot), with
boundary sentences against the adjacent themes. `test_schema_delta` now asserts exactly
those two are written and the other eight stay empty. They are part of `definition_hash`.

## 6. The corroboration-gate pass

### 6a. Inventory

Four parallel read-only passes, one per group of harnesses, produced 411 gate rows with
file:line, condition, what happens instead, the quoted rationale, and a proposed class. I
re-classified where they disagreed with each other or with the rule. Counts:

| class | gates | action |
|---|---:|---|
| corroboration-strength | 31 | 20 converted tonight; 11 deferred with a stated reason (JOBPOST v1.3 reproducibility, EXECID schema, SAFETY-ENV re-quarantine cost) |
| identity-matching | 170 | unchanged |
| unclear / not a gate | 210 | logged; ~40 are real decisions for you, the rest are dedupe, budgets, schema, quarantine mechanics |

### 6b. The mechanism

`core/topics.py`: `classify_tiered()` returns `(hits, "strong"|"weak")`; `classify()` is
unchanged so nothing that has not opted in moves. A low-grade row is recognisable by any one
of four marks: `source_grade C`, `weak_clue`, `confidence ≤ 0.4`, `evidence_excerpt` starting
`[low-grade: <gate>; corroboration-strength gate relaxed 2026-09-03, review before use]`.
Grade D stays unwritable. `gap_report.py` **excludes low-grade rows by default** and reports
them in a separate column (`--include-low-grade` to see the counts with them).

### 6c. What was converted, and what it produced

| harness | version | gates converted | replay (offline, committed, quarantined) |
|---|---|---|---|
| SELLERCONTENT | v1.4 | generic-only theme on a provider page | 13 rows, 10 low-grade — the ten claims the 2026-09-02 fix retired, now present and marked |
| FIRSTPARTY | v1.2 | single-term-not-in-headline; generic-only page | **169 rows, 152 low-grade** — the 163 single-term rows v1.1 cut, back at C for review |
| EXECVOICE | v1.4 | short quote (40–59 chars); generic-only theme in a quote | 1 low-grade row; 3 human-reviewed rows held (conflicts, not overwritten) |
| TRADEPRESS | v1.4 | single-term theme on wire and profile routes; quote gates inherited | 2 low-grade rows; 1 human row held |
| LEGAL | v1.2 | nature-of-suit whitelist | 0 new rows: no vendor docket passed identity with a non-commercial nature |
| PRODUCTQUALITY | v1.3 | same-sentence rule, split | 2 low-grade rows; cue-without-predicate still refused |
| FMCSA | v1.4 | nil fleet; OOS counts under 20 inspections; zero crashes; MCS-150 12–24 months; drivers within the 25% band | 9 low-grade rows; 20 human-reviewed rows held |
| WAYBACK | v1.2 | single-capture removals (and the `absent_confirmed` mislabel they caused) | 7 low-grade rows |
| EMPREVIEW | v1.1 | one-review-one-term; sample under the 5-review floor | 0 rows (source blocked) |

Every replay reproduced its prior rows identically (no ids lost; the ledger confirms). The
"held" counts are proposals whose content differs from a human-reviewed row — reported as
conflicts and never written, by convention 35. FMCSA's 20 held rows are the 2026-08 reviewed
rows whose "as of" text differs on replay, not a policy effect.

**What the 183 low-grade rows are about:** workforce_enablement 35, systems_integration 34,
digital_transformation 27, ot_modernization 22, data_analytics_ai 19, cybersecurity 14,
removed_public_content 7, transportation 6. That distribution is itself the finding the
2026-09-02 session predicted: the generic vocabulary lands on exactly the themes the project
was least able to see.

### 6d. Effect on the gap report

Default (low-grade excluded), from `docs/diagnostics/gap_report_after_session9_2026-09-03.txt`:
the strong-tier table moved only where tonight's live and replay runs added strong rows —
cloud 0 → 1 buyer (OnTrac), ot_modernization 0 → 1, digital transformation 13 → 16,
systems_integration 4 → 3. With `--include-low-grade`: systems_integration 3 → 19 buyers and
1 → 7 sellers, cybersecurity 0 → 13, workforce_enablement 2 → 27, ot_modernization 1 → 14.
**That second table is what the extractor's weakest tier would say if nobody reviewed it**,
which is why it is not the default.

### 6e. Convention 41

Written into `docs/conventions.md`: corroboration-strength gates write at low grade,
identity gates refuse, gates that fit neither are logged rather than guessed; with the four
marks and the amendment to convention 32 spelled out.

## What needs you

1. **Review sheets for nine new versions** (SELLERCONTENT v1.4, FIRSTPARTY v1.2 — a random
   control of 30 from 169 —, EXECVOICE v1.4, TRADEPRESS v1.4, PQ v1.3, FMCSA v1.4, WAYBACK
   v1.2, JOBPOST v1.3; LEGAL v1.2 and EMPREVIEW v1.1 have no rows). Until judged, none
   publishes a coverage number; published coverage today is unchanged.
2. **The ~40 unclear gates** in the inventory's decision table, of which the staleness
   window, the Wayback replatform refusal, and the characterisation-vs-action rule are the
   three with real evidence behind them.
3. **JOBPOST v1.4 scope**: the two deferred conversions (volume floor; vendor-name subset of
   `requires`), the iCIMS truncation flag, and whether to build the inline-static-list parser
   (12 companies) before any ATS adapter.
4. **EXECID**: whether `Company_Executives` gets a low-grade tier at all (needs the writer
   to accept an empty title).
5. **SAFETY-ENV**: three corroboration-strength candidates whose conversion would
   re-quarantine 131 grandfathered rows or change what an absence row means.
6. Parked, unchanged: O00369 / O00373 (EXECVOICE's held human rows — v1.4 re-proposed one
   low-grade row and held the conflicts, so the review sheet shows the comparison); the
   Harness Advisor ping.

## Files

New: `harnesses/h_jobpost_01/aggregator.py`, `scripts/careers_platform_audit.py`,
`docs/diagnostics/gate_inventory_2026-09-03.md`, `docs/diagnostics/careers_platform_audit_2026-09-03.md`,
`docs/diagnostics/gap_report_after_session9_2026-09-03.txt`, two audit artifacts, nine review
sheets and strata sidecars. Modified: `core/topics.py`, `scripts/gap_report.py`,
`docs/conventions.md`, `signal_advisor_theme_confirmation_2026-09-02.md`, ten harness
packages (code + manifest), `core/tests/test_schema_delta.py`, the workbook, `CLAUDE.md`,
`README.md`. Not committed.
