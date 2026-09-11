# `Attempts` — Harness Audit/Metadata Schema Spec

**Status:** design agreed, not yet implemented
**Target:** new sheets `Attempts` and `Harness_Sources` in `market_intel_db.xlsx`, plus
additions to `Lookups` and `Harness_Runs`
**Handoff:** Claude Code implements; this document is the contract

**Rev 2** — resolves the four Signal Advisor questions (§9). Changes: `attempted_signal`
constrained to `evidence_family` and confirmed non-1:1 with `harness_id`; `scope` and
candidate-count columns added to `Attempts`; new `Harness_Sources` junction sheet;
**Rev 6** (2026-09-08) — folds in the four coherence-framework tables (§13), the fourth
added by the same day's addendum (§13.5). **Additive change; no Matthew sign-off required**, per the build handoff of the same date: Signal Advisor ruling obtained 2026-09-07/08, MetaCog reviewed and greenlit the seed data and pilot scope. Nothing existing is altered — no column is added to `Observations`, no vocabulary value is removed, no gate behaviour changes. The `Coherence_Framework_Taxonomy` seed arrived on 2026-09-08 after an initial hand-off without it and **all 46 rows are loaded** (§13.4).

**Rev 5** — storage tier resolved: **workbook-only**, no file/hybrid split (§12).

**Rev 4** — adds the redundancy category and the `Company_Executives` sheet (§11), and
corrects the coverage-counting bug that the redundancy question exposed (§11 C9).

**Rev 3** — reconciled against `CLAUDE.md`, `PIVOT_UPDATE.md`, and the workbook (§10).
Contains one **correction to a Rev 2 decision already circulated to Signal Advisor**:
`attempted_signal` is signal-type-level, not `evidence_family`.

---

## 1. Purpose

Give Talbot West structured, queryable visibility into *why* a harness did or didn't
produce evidence for a given company — mineable for improvement areas rather than
scattered free-text notes.

Design premise: **log attempts, not failures.** A failure-only table has no denominator.
You cannot distinguish "this failure mode is rare" from "the harness quietly stopped
trying." Coverage-gap reporting ("2 of 8 companies not covered — JS-rendered career
pages") becomes a query over this table instead of a hand-written note.

Second premise: **a confirmed absence is not a failure.** If a harness successfully
reaches a company's career page and finds no AI-related postings, that is negative
evidence about organizational state, not a miss. It gets its own outcome value so it
neither pollutes improvement-mining nor understates coverage in the Week 4 evaluation.

---

## 2. Grain

One row per `(run_id, company_id, attempted_signal)`.

Composite uniqueness is enforced on those three fields. A harness that looks for two
evidence families at one company in one run writes two rows — one per family. This is
intentional: it is what lets you say "this harness covers hiring signal well but fails at
legacy-constraint extraction," which a single per-company row could not express.

**Not** fields on `Observations` — a miss has no Observation row to hang on.
**Not** fields on `Harness_Runs` — a run touches ~108 companies; per-company granularity
is the entire point.

---

## 3. Columns

| # | Field | Type | Null? | Notes |
|---|---|---|---|---|
| 1 | `attempt_id` | text PK | no | `{run_id}-{seq}`, zero-padded seq |
| 2 | `run_id` | text FK → `Harness_Runs` | no | |
| 3 | `harness_id` | text | no | Denormalized from run for query convenience |
| 4 | `harness_version` | text | no | Denormalized; enables version-over-version trend |
| 5 | `company_id` | text FK → `Companies` | no | |
| 6 | `attempted_signal` | text (vocab) | no | A **signal type**, not an evidence family. See §10 C1. |
| 6a | `evidence_family` | text (vocab) | no | Parent family of `attempted_signal`, denormalized for rollup |
| 7 | `outcome` | text (vocab) | no | `covered` / `absent_confirmed` / `partial` / `not_covered` |
| 8 | `failure_stage` | text (vocab) | yes | Null iff `outcome = covered` or `absent_confirmed` |
| 9 | `failure_category` | text (vocab) | yes | Null iff `outcome = covered` or `absent_confirmed` |
| 10 | `failure_detail` | text free | yes | The only free-text field. One sentence, specific. |
| 11 | `fix_class` | text (vocab) | yes | `transient` / `code_change` / `source_limitation` |
| 12 | `records_written` | integer | no | New rows written to `output_sheet` for this signal. See §11 C9. |
| 12a | `records_reconciled` | integer | no | Existing rows matched and left alone or refreshed in place |
| 12b | `output_sheet` | text | no | `Observations` for evidence harnesses; target sheet for enrichment harnesses |
| 13 | `attempt_timestamp` | ISO 8601 | no | |
| 14 | `source_url_attempted` | text | yes | The URL/endpoint tried, when there is one. With a logical harness this is the specific call that failed — see §9 Q4. |
| 15 | `scope` | text (vocab) | no | `scoped` / `incidental` — see §3.1 |
| 16 | `candidates_evaluated` | integer | yes | Null unless the harness evaluates a candidate set |
| 17 | `candidates_discarded` | integer | yes | Null unless above is populated |

### 3.1 `scope` — scoped vs. incidental

A harness declares an expected set of evidence families. `scoped` rows are attempts
against that declared set: one per `(company, declared_family)`, written whether or not
anything was found. These are the rows coverage math runs on.

`incidental` rows are created retroactively when a harness writes an Observation in a
family it was not scoped for — e.g. a job-posting harness extracting a legacy-constraint
claim from a posting it fetched looking for hiring signal. Always `outcome = covered`,
always created after the fact.

Coverage-rate calculations **exclude** `incidental` rows. Without this split, opportunistic
finds inflate the denominator inconsistently — a harness looks worse on families it never
declared, and better on runs where it happened to stumble into something. Observation
counts include both.

### Outcome semantics

- `covered` — harness reached the source and produced output: `records_written +
  records_reconciled > 0`. An idempotent re-run that writes nothing new is covered.
- `absent_confirmed` — harness reached the source successfully; the signal is genuinely
  not present. **Counts as coverage.** Carries evidentiary weight.
- `partial` — some evidence written, but a known gap remains (e.g. 2 of 5 job postings
  parsed). Requires `failure_stage` + `failure_category` describing the gap.
- `not_covered` — no evidence, and the harness cannot assert absence. Requires
  `failure_stage` + `failure_category`.

The `absent_confirmed` / `not_covered` boundary is the judgment call. Rule: assert
`absent_confirmed` only when the harness both reached the authoritative source **and**
the source is complete for that signal. A career page that rendered fully with no AI
roles → `absent_confirmed`. A career page that wouldn't render → `not_covered`.

---

## 4. Two-axis failure vocabulary

Two axes, deliberately not flattened into one list.

- `failure_stage` answers **where to invest engineering effort**.
- `failure_category` answers **what kind of fix this is**.

Flattening loses the routing: "entity resolution below threshold" and "JS-rendered
content unreachable" both collapse to "couldn't get data," but they send you to
completely different work.

### `failure_stage` (ordered pipeline positions)

`discovery` → `fetch` → `entity_resolution` → `extraction` → `classification` → `write`

### `failure_category` (grouped by the stage it typically occurs in)

| Stage | Category | Meaning |
|---|---|---|
| discovery | `no_api_available` | No clean programmatic access for this source type |
| discovery | `source_not_found` | No candidate source located for this company |
| fetch | `access_blocked` | 403 / robots / paywall / rate limit |
| fetch | `js_rendered_unreachable` | Content requires JS execution |
| fetch | `source_unavailable` | Timeout, 5xx, DNS — likely transient |
| entity_resolution | `entity_no_candidate` | Zero candidates returned |
| entity_resolution | `entity_below_threshold` | Best candidate scored under confidence floor |
| entity_resolution | `entity_ambiguous_multiple` | Multiple plausible matches — e.g. one registrant, several active registrations |
| extraction | `parse_failure` | Structure present but unparseable |
| extraction | `content_unstructured` | Retrieved, but no extractable structure (scanned PDF, image) |
| classification | `false_positive_rejected` | Keyword matched, classifier rejected as not the signal |
| classification | `classification_ambiguous` | Could not assign `evidence_family` or `organizational_state` confidently |
| temporal | `source_drift_detected` | Live source changed after `retrieval_date` |
| temporal | `stale_beyond_threshold` | Source older than acceptable window for this signal |
| governance | `suppressed_by_cap` | Result truncated by a per-company or per-run cap |
| governance | `write_conflict_post_review` | Claim changed after human review — escalated, not overwritten |
| governance | `suppressed_redundant` | Valid, on-subject candidate judged to add no marginal value over prior extractions. See §11 Q5. |

Two categories carry established conventions and must not be folded into generic
`parse_failure`:

- **`source_drift_detected`** — separating drift from genuine extraction error is what
  keeps the Week 4 reliability number from measuring source volatility instead of harness
  accuracy. This is the tag that operationalizes the "review against the source date it
  cites" convention.
- **`suppressed_by_cap`** — satisfies the "every suppressed or truncated result gets
  reported" convention. Truncation becomes a row, not a silence.

### `fix_class`

- `transient` — retry may resolve; no code change indicated.
- `code_change` — harness logic can address it.
- `source_limitation` — the source will not yield this; a different harness or source
  family is required. Signals a portfolio gap, not a bug.

---

## 5. Additions to existing sheets

### `Harness_Runs` — run-level rollups

Derivable from `Attempts`, denormalized so run health is readable without pivoting.

| Field | Type |
|---|---|
| `attempts_total` | integer |
| `attempts_covered` | integer |
| `attempts_absent_confirmed` | integer |
| `attempts_partial` | integer |
| `attempts_not_covered` | integer |
| `coverage_rate` | decimal — `(covered + absent_confirmed + partial) / attempts_total`, over `scope = scoped` rows only |

`coverage_rate` counts `absent_confirmed` as coverage. That is the point of the value.
All five rollups count `scope = scoped` rows only.

### New sheet: `Harness_Sources`

Junction resolving the many-to-many between a harness and the source families it touches.
Required once `harness_id` denotes a logical harness that may call several external
sources (§9 Q4).

| Field | Type | Notes |
|---|---|---|
| `harness_id` | text | Composite PK with the next two |
| `harness_version` | text | A harness's source set changes across versions |
| `source_id` | text FK → `Source_Families.source_id` | Requires adding a surrogate key — see §10 C4 |
| `role` | text (vocab) | `primary` / `supporting` / `resolution_only` |
| `notes` | text | Optional |

`Source_Families` itself is **not** restructured. It stays a flat reference vocabulary
describing source families and their properties. The relational complexity belongs in the
junction, not in the reference table — otherwise a stable vocabulary starts churning every
time a harness changes.

`role` distinguishes the source a claim is *about* (`primary`) from sources used to reach
or verify it (`supporting`), from sources used only to resolve an entity and never cited
in an Observation (`resolution_only`). Without that split, "which harnesses depend on the
FMCSA API" and "which Observations cite FMCSA" return different sets with no way to
explain the difference.

This sheet is also the data source for the portfolio visualization (brief item 2) and for
blast-radius queries when an external API breaks or changes terms.

### `Lookups` — six new controlled vocabularies

Add as new vocabulary sets alongside the existing ones, same pattern, driving dropdowns:
`attempt_outcome`, `failure_stage`, `failure_category`, `fix_class`, `attempt_scope`, and
`harness_source_role`.

Categories are additive-only. Adding a value is cheap; renaming or removing one breaks
version-over-version trend queries. Retire by marking inactive in `Lookups`, never delete.

---

## 6. Open decisions

**Resolved:** `attempted_signal` is constrained to `evidence_family` values. See §9 Q1 for
the reasoning and for why this does not imply one family per harness.

**Resolved:** harness naming convention — see §10 C3.

**Resolved:** backfill is feasible for both existing harnesses; recommendation flipped from
(b) to (a). See §10 C5.

**Resolved:** storage tier — workbook-only. See §12. Supersedes §10 C2.

---

## 7. Write semantics

**Append-only. `Attempts` does not reconcile.**

This is a deliberate divergence from the Observations idempotency convention. Observations
reconcile because they represent current best knowledge of a claim. Attempts represent
what happened during a specific execution — immutable history. Reconciling would erase the
version-over-version trend the table exists to produce.

Consequences:
- Re-running a harness appends a new set of attempt rows under a new `run_id`.
- Rows are never updated or deleted after a run completes.
- "Current coverage for company X" is a query for the most recent `run_id` per
  `(harness_id, company_id, attempted_signal)`, not a stored value.

**Completeness requirement:** a harness must write exactly one Attempts row for every
`(company, signal)` pair it was scoped to try — including pairs it skipped early. A skip
is `not_covered` with a stage and category, never a missing row. Missing rows silently
recreate the denominator problem this table was built to solve.

---

## 8. Queries this table must answer

Acceptance criteria — if any of these is awkward to express, the schema is wrong.

1. Coverage gap for a run, in the established reporting phrasing: count and list of
   `not_covered` for a `run_id`, grouped by `failure_category`.
2. Top failure categories across all harnesses, ranked, filtered to `fix_class =
   code_change` — the improvement backlog, ordered.
3. Did version N+1 improve on version N? `coverage_rate` by `harness_version` for one
   `harness_id`.
4. Which companies are systematically invisible? `company_id` where all recent attempts
   across all harnesses are `not_covered` — candidates for exclusion or a bespoke approach.
5. Entity-resolution health: share of attempts failing at `failure_stage =
   entity_resolution`, split by category, over time.
6. Drift vs. error for the Week 4 evaluation: `source_drift_detected` count separated
   from extraction-stage failures.
7. Where is the portfolio structurally blind? `attempted_signal` values whose attempts are
   dominated by `fix_class = source_limitation` — feeds the Signal Advisor conversation
   about which signal types need a different source family.

---

## 9. Resolved design questions (Signal Advisor, Rev 2)

### Q4 — `harness_id` granularity: **one per logical harness**

A `harness_id` denotes one signal-producing unit, regardless of how many external APIs or
fetches it makes internally. Not one per external API.

Reasoning. `harness_id` appears on every Observation row, where its job is provenance for
*a claim*. A claim is produced by the whole pipeline, not by any single API call — so
under per-API IDs, no single `harness_id` could be attached to an Observation truthfully;
one call would have to be arbitrarily designated the primary. Precedent already supports
this: H-JOBPOST-01 is search + read + classify and is one harness today, while
H-FMCSA-01 is a single API, and both coexist under one ID scheme. The Week 4 reliability
evaluation also measures whether claims are correct, which is an end-to-end property.

The cost — losing visibility into which internal call failed — is already covered by
`failure_stage` plus `source_url_attempted` in `Attempts`. Per-API diagnosis does not
require per-API identity. This is a large part of why the failure vocabulary has two axes.

**Split rule.** Two units are separate harnesses when any of the following holds:

1. They produce signal types independently useful — someone would run one without the other.
2. They need independent version cadence.
3. One's output is another's input.

Shared internal API calls are **not** grounds for splitting. Shared *logic* (entity
resolution, schema writes) goes to a utilities module in the repo — a code-organization
concern, not a schema one.

### Q1 — one harness, multiple evidence families: **yes, not 1:1**

`evidence_family` is a property of the Observation, not of the harness. One job posting
can yield a hiring-signal claim and a legacy-constraint claim; both are legitimate,
separately checkable Observations from one fetch.

Each harness declares an expected family set. Attempts are written per
`(company, declared_family)`. Writing outside the declared set is permitted and recorded
via `scope = incidental` (§3.1) so coverage math stays honest in both directions.

### Q2 — `Source_Families` many-to-many: **junction table, reference table unchanged**

New `Harness_Sources` sheet (§5). `Source_Families` remains a flat reference vocabulary.
Putting the many-to-many in a junction keeps a stable vocabulary stable; embedding it in
`Source_Families` would make a reference table churn on every harness change.

This is a direct consequence of Q4 — once one harness can call several sources, something
has to record which.

### Q3 — discard-reason vocabulary: **`failure_category`, extended; stored in `Attempts`**

Not a new vocabulary. "Why didn't this become evidence" gets exactly one controlled list.
Two overlapping lists is how `false_positive_rejected` and a near-identical
`keyword_mismatch` end up meaning the same thing in different sheets.

Not Observations columns — a discard produced no row to hang fields on. Not `Harness_Runs`
— same loss-of-grain argument that put `Attempts` at company level in the first place.

Storage, staged:

- **Now:** `candidates_evaluated` and `candidates_discarded` counts on the `Attempts` row,
  with `failure_category` naming the dominant discard reason.
- **When a classification harness exists:** a `Discards` child table keyed to
  `attempt_id`, one row per discarded candidate, `discard_reason` drawn from the shared
  `failure_category` vocabulary. Needed because a classification harness may evaluate
  hundreds of candidates per company, and per-candidate rows in `Attempts` would break its
  grain.

The child table is specified but not created yet — an empty sheet for a harness that does
not exist is retrofitting in advance.

---

## 10. Rev 3 — reconciliation against project docs and workbook

Sources: `CLAUDE.md`, `PIVOT_UPDATE.md`, `market_intel_db.xlsx` (as uploaded 2026-08-26).

### C1 — CORRECTION: `attempted_signal` is signal-type-level, not `evidence_family`

Rev 2 constrained `attempted_signal` to the 18 evidence families. **That was wrong**, and
it was circulated to Signal Advisor. It was an interim default chosen without
`PIVOT_UPDATE.md`, which states directly that signals are *more granular* than the 18
families — within family 15 (executive candor), "a LinkedIn post by a named executive" and
"a podcast appearance" are distinct signal types with different reliability and extraction
requirements. Harness granularity targets one harness per signal type.

Under the Rev 2 constraint, a podcast harness and a LinkedIn-exec harness both write
`attempted_signal = "15_executive_candor"`. Acceptance query #7 ("where is the portfolio
structurally blind?") would then return *executive candor* as blind when only the podcast
route is blind and LinkedIn works fine. The column would be systematically coarser than
what was actually attempted — a false statement in the data, not merely a lossy one.

**Corrected design:** two columns.
- `attempted_signal` — the signal type. Vocabulary owned by Signal Advisor.
- `evidence_family` — its parent family, denormalized so family-level rollups still work.

Requires a new `Signal_Types` registry sheet (`signal_type_id`, `signal_type_name`,
`evidence_family`, `status`) mapping each signal type to exactly one family. Signal Advisor
populates it; this spec only depends on the mapping existing and being one-to-many in that
direction. Until it exists, Claude Code should treat `attempted_signal` as free text
against a stub registry rather than binding a dropdown to an unfinished vocabulary.

Rev 2's Q1 answer is unaffected and still stands: a harness may write Observations across
multiple evidence families.

### C2 — SUPERSEDED BY §12. Retained for the row-count analysis; the three-option
recommendation is withdrawn.

### C2 (original) — `Attempts` will exceed the workbook's validation range almost immediately

`CLAUDE.md` warns that dropdown validation is bound to rows 2–500 and that rows past 500
lose validation silently. The workbook confirms it: every validation on Observations and
Companies is bound `X2:X500`.

`Attempts` is append-only across 108 companies. At even three signal types per harness,
one run writes ~324 rows; the second run breaches 500. At the PIVOT_UPDATE target of many
signal-level harnesses, this is tens of thousands of rows within weeks. `Attempts` is
structurally unlike every other sheet in this workbook — it is a high-volume immutable log,
not a curated table.

Three options, with the tradeoff stated honestly:

- **(a) Workbook sheet, wide validation.** Bind `Attempts` validation to row 50,000+.
  Simplest, keeps "everything is in the relational DB" true for the deliverable narrative.
  Cost: `db.py` rewrites the whole workbook per run — slow and corruption-prone at volume.
- **(b) Files only.** Append-only JSONL under `harness_output/<harness_id>/attempts/`.
  Precedent exists: `harness_output/` already holds per-run JSON logs of every resolution
  decision including refusals. Cost: the audit system stops being part of the DB, which
  weakens the story that the relational database is the system of record.
- **(c) Hybrid — recommended.** JSONL files are canonical for full history; the workbook
  carries a materialized `Attempts` sheet holding only the most recent attempt per
  `(harness_id, company_id, attempted_signal)`. Bounded by the live portfolio rather than
  by run count, so it stays workbook-sized. Version-over-version trend queries read the
  files. Rollups on `Harness_Runs` stay in the workbook either way.

(c) is recommended but not decided — it splits the system of record, which is a real cost
and Matthew should weigh it against the deliverable framing.

**Separate but urgent, outside this spec's scope:** Observations itself will breach 500
rows in Week 2. The 8 pilots produced 35 observations (~4.4/company) from two harnesses;
108 companies at that rate is ~475 from those two harnesses alone. `CLAUDE.md` flags the
need to extend validation ranges before any sheet passes 500 and it has not been done. This
should be fixed before the Week 2 full-universe run, independent of anything here.

### C3 — RESOLVED: harness naming convention

The two existing IDs are already inconsistent. `H-FMCSA-01` names a *source*;
`H-JOBPOST-01` names a *signal type*. Under the logical-harness decision (§9 Q4) plus the
PIVOT_UPDATE one-harness-per-signal-type target, the signal-type form is correct.

- **Going forward:** `H-{SIGNAL_TYPE}-{NN}`, middle token names the signal type.
- **`H-FMCSA-01` is grandfathered, not renamed.** Its ID is written into 27 committed
  Observations and its run rows. Renaming breaks provenance on reviewed evidence to fix a
  cosmetic inconsistency — not a trade worth making. Document the exception in the repo
  README.
- **`-NN` is a serial within the token namespace, orthogonal to `harness_version`.** It
  distinguishes two differently-architected harnesses against the same signal type
  (`H-JOBPOST-02` as a rendered-DOM variant), where `v1.3` denotes revisions of one harness.
  This matters concretely: the four job-post coverage gaps split into two causes
  (Midmark/Duke need rendered-DOM fetch; Mack/Western Express need careers-URL discovery),
  and the first may well warrant a sibling harness rather than a version bump.

### C4 — `Source_Families` has no primary key

Rev 2's `Harness_Sources` junction referenced `source_family_id`. No such column exists.
The sheet's actual headers are `evidence_family`, `source_name`, `access_type`,
`private_company_applicable`, `expected_coverage`, `notes` — keyed implicitly on
(`evidence_family`, `source_name`), and a source serving several families appears as
several rows.

**Fix:** add a surrogate `source_id` column to `Source_Families`. Non-breaking on a
reference table, and required for `Harness_Sources` to have a clean FK. Composite FKs on a
free-text `source_name` would be fragile against exactly the kind of naming drift this
project already hit with entity resolution.

### C5 — CORRECTION: backfill is feasible; recommendation flips to (a)

Rev 2 recommended treating pre-existing runs as unlogged. That was based on an assumption
about what run logs contained, and the assumption was wrong.

`CLAUDE.md` documents that `harness_output/<harness_id>/` already holds "a per-run JSON log
of every resolution decision, including refusals." That is an entity-resolution-stage
attempt log in all but name. `H-JOBPOST-01` additionally documents its four coverage gaps
in `harnesses/jobpost_sources.json` and reports them in `known_issues` every run.

So: backfill both harnesses for `discovery`, `fetch`, and `entity_resolution` stage
attempts from existing artifacts. Mark extraction- and classification-stage attempts for
those runs as unlogged via `attempts_logging_from_version`. Partial backfill with an
explicit boundary beats an all-or-nothing gap, and the boundary is itself recorded rather
than implied.

### C6 — `Harness_Runs` conflicts to resolve

The live sheet has `target_evidence_family` (singular) and `known_issues` (free text).

- `target_evidence_family` contradicts §9 Q1 (a harness writes across families). Keep the
  column for back-compat, redefine it as *primary* family, and treat `Harness_Sources` plus
  `Attempts.evidence_family` as authoritative for the full set.
- `known_issues` is precisely the scattered free-text the audit system exists to replace.
  It should become **derived** — generated from that run's `Attempts` rows grouped by
  `failure_category` — not hand-authored. This is the concrete win: H-JOBPOST-01's "3 of 7
  companies covered, four documented gaps" becomes a query result instead of a maintained
  string.
- `companies_processed_count` becomes derivable as distinct `company_id` in `Attempts`.
  Keep it, populate it from the derivation.

### C7 — real cases from the pilot that validate (and bound) the design

- **CT Logistics resolving to nothing was correct** — a freight-audit firm operates no
  fleet. Under a failure-only log that reads as a 1-of-8 miss. It is `absent_confirmed`,
  and H-FMCSA-01's true resolution result is 8/8, not 7/8. This is the clearest
  justification for that outcome value existing.
- **Kenco's 5 co-located USDOT registrations** → `entity_ambiguous_multiple`.
- **Kenco's 467 postings yielding 5 genuine modernization roles** → `candidates_evaluated
  = 467`, `candidates_discarded = 462`. `CLAUDE.md` notes that ratio is itself a finding;
  the counts make it queryable across companies instead of a note in one harness's writeup.
- **The nine drift corrections during review** → `source_drift_detected`, kept separate
  from extraction error so the Week 4 metric measures the harness and not the calendar.

**Known limitation, stated rather than papered over.** The `Infor` / "Information Systems"
substring bug inflated a signal from `weak_clue` to `repeated_pattern`. `Attempts` would
not have caught it. This system records candidates *rejected*; it cannot see a false
positive that was *accepted*. That failure mode belongs to `review_status` and the Week 4
stratified review. Any claim that this schema gives full visibility into AI failure modes
should be scoped accordingly.

### C8 — the uploaded workbook is stale (see chat; not a schema issue)

The uploaded `market_intel_db.xlsx` predates the 2026-08-22 cleanup described in
`CLAUDE.md`. Pilot `company_id`s in the file disagree with CLAUDE.md's authoritative list.
This spec is written against CLAUDE.md's IDs. Claude Code must be pointed at the live
workbook, not this copy.

---

## 11. Rev 4 — redundancy handling and prerequisite output

### Q5 — redundancy: `governance` stage, category `suppressed_redundant`

**Not a new `deduplication` stage.** The stage axis marks pipeline positions so it can
route engineering investment, and `governance` already means one specific thing: *the
system deliberately declined to write something it was capable of writing*. Both existing
members are that — `suppressed_by_cap` (policy limit) and `write_conflict_post_review`
(never overwrite human review). Redundancy suppression is the same kind of event: nothing
broke, a rule fired. A `deduplication` stage would be a stage of one, and diluting a
six-value stage vocabulary to hold a single category costs more than it buys.

`fix_class` carries the distinction Signal Advisor is reaching for. `suppressed_by_cap` is
usually config; `suppressed_redundant` is usually `code_change`, because the thing you tune
is a threshold. That routes the two differently in the improvement backlog without a new
stage.

Governance suppressions do **not** reduce `coverage_rate`. Outcome stays `covered` — the
harness reached the source and made a decision. Redundancy is not a miss.

**Three constraints on this category, one of them load-bearing.**

**(a) Redundancy is not idempotency.** Two different things must not collapse into this
category. An idempotent no-op — same claim, same source, already reconciled on re-run — is
ordinary reconciliation and gets no `failure_category` at all. `suppressed_redundant` is
reserved for a *genuinely new* instance the classifier judged adds no marginal value. If
these merge, the category will be dominated by re-run noise and become unmineable.

**(b) Discarding redundant instances can destroy the signal it was measuring.**
`signal_strength` has `repeated_pattern` as a value, one step above `weak_clue`, and
`CLAUDE.md` records that the Infor/"Information Systems" bug mattered precisely because it
pushed Kenco's ERP signal from `weak_clue` to `repeated_pattern` — signal strength drives
downstream finding weight. Repetition *is* the evidence for that value. A redundancy
classifier that drops instances 2 through 12 destroys the only basis for claiming
`repeated_pattern`.

So: **redundant instances must still be counted even when not written as separate
Observations.** The surviving Observation carries the instance count, and `signal_strength`
is derived from it. Suppression removes rows, never the count. Any implementation that
discards redundant candidates without incrementing a counter on the surviving row is wrong
regardless of how good its threshold is.

**(c) Every redundancy discard names its referent.** Add `redundant_against_observation_id`
to the `Discards` table. Without it, "462 candidates suppressed as redundant" is
unfalsifiable, and given the Infor precedent — a loose pattern manufacturing confidence
rather than merely adding noise — an over-aggressive redundancy threshold silently
suppressing real evidence is the same failure class with the sign flipped. The Week 4
stratified review should sample redundancy discards specifically.

### Q6 — `Company_Executives`: yes, own sheet, with corrections to the proposed columns

Signal Advisor's read is right — it is neither an Observation (no checkable modernization
claim) nor an Attempt (not run coverage), it is one-to-many, and fixed columns on
`Companies` won't hold it. It gets its own sheet in the `Harness_Sources` pattern. Five
changes to the proposed column set:

| Field | Notes |
|---|---|
| `executive_id` | **PK.** Required — Observations need to reference which exec authored a claim, and `(company_id, name)` is fragile against exactly the name-variant problem already hit in company resolution |
| `company_id` | FK → `Companies` |
| `full_name`, `name_variants` | Variants stored explicitly rather than re-derived per run |
| `title`, `title_normalized` | |
| `role_relevance` | `modernization_relevant` / `peripheral` / `unknown` — CIO/COO/VP Ops vs. general counsel. Without it every downstream harness re-derives the same judgment |
| `source_url`, `source_grade`, `publication_date`, `retrieval_date` | **Replaces the proposed single `source` + `last_verified`.** See below |
| `harness_id`, `harness_version` | Harness output, so it carries provenance like Observations and re-runs reconcile idempotently |
| `status` | `current` / `departed` / `unknown` |
| `superseded_by` | FK → `executive_id`, for re-resolution |
| `confidence_0_1` | |
| `review_status` | Same vocabulary as Observations — this is resolution output and resolution is the known failure surface |

**Why `last_verified` alone is insufficient.** The locked convention is to review against
the snapshot date a row cites, not today's live page. An exec title correct on 08/20 and
changed by 08/23 is *source drift*, not harness error — the identical situation as the nine
FMCSA corrections. A single `last_verified` timestamp cannot express the difference between
"when the source said this" and "when we fetched it," so it cannot support that convention.
`publication_date` + `retrieval_date` can, and reuses a pattern already in the schema.

**Person-level identity is deliberately not modeled.** An executive who moves between two
Anvil companies becomes two rows with no link. A proper `Persons` table with a
person-to-company junction would fix it, and is over-engineering for 108 companies over
five weeks. `superseded_by` plus `name_variants` covers the realistic cases. Noting the
limitation so it is a decision rather than an oversight — if board-member overlap across
the Anvil-100 turns out to be common, revisit.

**This makes exec identification its own harness.** Applying the §9 Q4 split rule: its
output feeds several downstream harnesses (LinkedIn posts, podcast appearances, conference
talks all need named execs), which is criterion 3. So `H-EXECID-01` writes
`Company_Executives`; `H-EXECVOICE-01` and siblings read it. Failures to identify an
executive are that harness's own Attempts rows at `failure_stage = entity_resolution`, not
buried inside H-EXECVOICE-01's coverage numbers.

### C9 — CORRECTION: `observations_written` mis-measured idempotent re-runs

Surfaced by Q5. Rev 2 defined `observations_written` as the count of Observations produced,
and treated `covered` as having written at least one.

That breaks against the idempotency convention. Re-running H-FMCSA-01 reconciles 27
unchanged rows and writes zero new ones. Under the Rev 2 definition every one of those
attempts logs `records_written = 0` and reads as a miss — the coverage rate would collapse
on exactly the re-runs that prove the harness is stable. A metric that punishes correct
idempotent behavior is worse than no metric.

**Corrected:** `records_written` (new rows) and `records_reconciled` (matched, left alone,
or refreshed in place) are separate. `covered` means `records_written + records_reconciled
> 0`. Ordinary reconciliation carries no `failure_category`.

### C10 — CORRECTION: `Signal_Types` must accommodate non-evidence harnesses

Rev 3 C1 specified that each signal type maps to exactly one `evidence_family`. Q6 breaks
that: exec identification is a real `attempted_signal` with no evidence family, because it
produces no evidence.

**Corrected:** add `signal_class` to the `Signal_Types` registry — `evidence` or
`prerequisite` — and make `evidence_family` nullable, required for `evidence` and null for
`prerequisite`. Family-level rollups filter to `signal_class = evidence`.

This generalizes past exec-ID. `PIVOT_UPDATE.md` calls for filling the Anvil companies'
blank `industry_primary` / `employee_count` / `revenue_estimate` opportunistically as
harnesses touch each company — also prerequisite output, also not Observations, also
needing coverage tracking. `records_written` + `output_sheet` (§3) cover both cases without
a parallel audit system for enrichment.

**Established rule worth naming, since it is already the practice:** enrichment *values*
are written to the target sheet, but enrichment *conflicts* become Observations. Precedent
is H-FMCSA-01 emitting `workforce_scale_conflict` for Venture Logistics (Companies sheet
says 750 employees; the registry shows 1,474 drivers) rather than silently overwriting the
sheet. A conflict is a checkable claim about the company; a value is not.

---

## 12. Rev 5 — storage tier resolved: workbook-only

**Decision (2026-08-27):** the workbook is the single system of record. No JSONL canonical
store, no hybrid current-state view. `Attempts` is a sheet like every other sheet.
Supersedes §10 C2, whose hybrid recommendation was sized for open-ended scale this project
does not have. The deliverable framing — a relational evidence database — stays intact.

Accepted. Two implementation numbers need correcting before Claude Code acts on it.

### Bind validation to 250,000 rows, not 20,000

The ~4,300 projection is a single-sweep figure: 20 harnesses × 108 companies × ~2 signal
types. It omits the run multiplier, which is the property that makes `Attempts` unlike
`Observations`. `Attempts` is append-only (§7) — every re-run appends a full set of rows
rather than reconciling into existing ones. That is deliberate and is what makes
version-over-version trend queries possible.

| Scenario | Rows |
|---|---|
| Single sweep, no re-runs | 4,320 |
| 4 runs per harness | 17,280 |
| 6 runs per harness | 25,920 |

Four runs per harness is not aggressive. H-FMCSA-01 reached HR-0004 at v1.3 inside week
one, and idempotency testing actively encourages re-running. A 20,000 binding is breached
somewhere around run four or five — mid-project, silently, which is the specific failure
mode `CLAUDE.md` warns about.

Bind `Attempts` at **250,000**. The cost of a too-large range is nil; the cost of a
too-small one is silent validation loss discovered after the fact. `Observations`
reconciles rather than appends, so 20,000 is genuinely comfortable there — no objection to
that half.

### `Discards` cannot be stored per-candidate; store counts complete, rows sampled

Kenco produced 467 postings of which 5 were genuine, i.e. 462 discards for **one company,
one run, one harness**. Across 108 companies that is ~50,000 rows from a single run of a
single classification harness. Per-candidate storage is not viable in the workbook at any
validation range, and this is not a binding problem — it is a volume problem that the
workbook-only decision does not solve.

Resolution, consistent with workbook-only:

- **Counts are complete and always stored.** `candidates_evaluated` and
  `candidates_discarded` live on the `Attempts` row (§3). No sampling. Every aggregate
  question — discard ratios by company, by harness, by version — is answerable from
  `Attempts` alone, including the Kenco 467:5 ratio that `CLAUDE.md` notes is itself a
  finding.
- **Per-candidate rows are sampled.** `Discards` retains a capped stratified sample —
  suggest 200 rows per run, allocated across `(company_id, discard_reason)` — sufficient
  for the Week 4 stratified review to audit whether the classifier was right, particularly
  for `suppressed_redundant` (§11 Q5c).
- **The cap is itself reported.** A run that sampled 200 of 49,896 discards writes that
  fact, per the standing convention that suppression and truncation are never silent.

This preserves every query in §8 and the audit purpose of `Discards`, while keeping the
sheet bounded. It is only relevant once a classification harness exists; `Discards` is
still not created yet.

---

## 13. Rev 6 — the coherence framework (build handoff 2026-09-08, + addendum)

Four new tables: three from the handoff (§13.1–13.3) and one from the same day's addendum
(§13.5). All three are **created and validated**; two are **populated** (the
taxonomy's 46 seed rows and the pilot's 6 cohort rows) and one is **empty by design until
tagging begins**. Implemented by `scripts/migrate_schema.py` (idempotent, as every other
step here) and enforced by `scripts/validate_repo_db.py` **check 11**.

### 13.1 `Coherence_Framework_Taxonomy` — reference

| column | notes |
|---|---|
| `id` | opaque primary key, `COH-D01` / `COH-F01` / `COH-G01` |
| `framework_version` | `v0.1` |
| `label` | |
| `definition` | |
| `parent_group` | failure families only (`I`–`V`); blank for dimensions and generative forces |
| `superseded_by` | nullable, points forward on relabel/split/merge; never reused or overwritten |
| `effective_date` | **load date, not source-document date** — matches the `Company_State_History` / `Attempts` practice of stamping derivation time |
| `entity_type` | `dimension` \| `failure_family` \| `generative_force`, bound to `Lookups.coherence_entity_type` |

**Loaded 2026-09-08 by `scripts/load_coherence_taxonomy.py`: all 46 rows — 22 dimensions
(`COH-D01`–`D22`), 19 failure families (`COH-F01`–`F19`), 5 generative forces
(`COH-G01`–`G05`)**, copied verbatim from the source workbook's own canonical
`Coherence_Framework_Taxonomy` sheet, whose eight columns are exactly this table's. Every
row carries `framework_version = v0.1`, `effective_date = 2026-09-08` and a null
`superseded_by`. Failure families group I(3) II(6) III(6) IV(3) V(1).

The loader refuses rather than loads on any of: a header that does not match, a count other
than 22/19/5, a duplicate or malformed id, a missing label or definition, a `parent_group`
outside I–V on a family or present on anything else, a non-uniform `framework_version`, an
id colliding with the live namespace, or an id already present at the same version with
different content — because the framework revises by `superseded_by` pointing forward, never
by rewriting a live row. Re-running is a no-op.

**Three columns of framework content the agreed schema cannot hold.** The source workbook
also carries per-entity detail sheets with `key_question` (22 dimensions), and
`dimensions_implicated` and `economic_consequence` (19 failure families). These are not
loaded: the handoff fixes this table's eight columns. The source workbook is committed at
`docs/schema/Coherence_Framework_Taxonomy_v0.1.xlsx` so nothing is lost, and its detail
sheets agree with the canonical sheet on every shared column (checked row by row).

`dimensions_implicated` is the one worth a decision. It is the family-to-dimension mapping —
`COH-F01` implicates `D02, D04, D06, D07, D05, D21`, and so on — and §2 derives failure
families at synthesis by joining across observations tagged with `COH-D*` dimensions. That
join needs this mapping, and it currently exists only inside the source file. Options when
synthesis is built: a fourth table (`Coherence_Family_Dimensions`, one row per family ×
dimension, which is the normalized form and what a join wants), or a column on this table.
Not decided here; flagged rather than chosen.

**Generative-force rows are reference-only**: they exist as explanatory and
synthesis-level context, are never referenced by `Observation_Coherence_Tags`, and must not
be exposed as a tagging option in harness tooling.

The `COH-` namespace was checked against every id in the live workbook and the repo before
this table was created (the handoff's §5 escalation trigger): the prefix census returned
`C0 A0 A1 P0 O0 HR SRC ST E0 CS DR THEME H-*` and zero `COH-*`. **No collision.**

### 13.2 `Observation_Coherence_Tags` — the overlay

A separate linked table, deliberately **not** columns on `Observations`. The framework is
explicitly falsifiable and expected to churn; an observation's identity (convention 43) must
not move when the framework does.

| column | notes |
|---|---|
| `observation_id` | FK into `Observations` |
| `coherence_dimension_candidate` | multi-select, `COH-D*` **only** — never `COH-F`, never `COH-G` |
| `coherence_valence` | `failure_candidate` \| `counterevidence` \| `successful_coherence_candidate` \| `not_applicable` \| `unknown_insufficient_evidence`, bound to `Lookups.coherence_valence` |
| `framework_version` | |
| `tagged_at` | |
| `tagging_run_id` | |

**The Convention 41 wall.** No code path that computes `review_status`, `audit_verdict`,
`publication_state` or `reprocessing_required` may read this table, directly or by join.
Tagging is read-only against `Observations` and writes only here.

Enforced, as the handoff requires, as a **validation failure and not a lint warning**:
check 11 scans the nine modules that compute those values (`core/db.py`, `core/audit.py`,
`core/attempts.py`, `core/composition.py`, `scripts/write_audit_artifact.py`,
`scripts/validate_repo_db.py`, `scripts/published_coverage.py`, `scripts/audit_sample.py`,
`scripts/check_run_ledger.py`) and fails on any reference to the table name. The validator
reads the table itself only to check it, inside a fenced region marked
`COHERENCE-WALL-CHECK-BEGIN/END`; a reference anywhere else in that file, check 9 included,
still fails. Verified in both directions: a reference injected into `core/db.py` fails the
check, and its removal restores it.

Check 11 also enforces that a tag cites a `dimension` (never a failure family or generative
force) and that its `observation_id` exists. With the taxonomy loaded these are provable
rather than vacuous, and were proved on a scratch copy: a `COH-F01` tag, a `COH-G02` tag, a
tag on a non-existent observation and a tag citing an unknown `COH-D99` each fail the check,
while a valid multi-dimension tag (`COH-D02;COH-D14`, semicolon-separated) passes.

**Failure-family determination does not happen here.** `COH-F` values are never written to
this table. Failure families are derived at synthesis time by joining across multiple tagged
observations by company / theme / time; that logic lives downstream.

### 13.3 `Coherence_Pilot_Runs` — the first falsification test

Tracks a scoped trial cohort, explicitly separate from `reprocessing_required`, so partial
pilot coverage is never misread as an outstanding gap.

| column | notes |
|---|---|
| `pilot_id` | `COHP-0001` for this pilot; repeats across its rows |
| `hypothesis` | fixed: `systems_integration over-firing correlates with COH-F tag(s)` |
| `company_id` | |
| `cohort` | `over_firing` \| `comparison`, bound to `Lookups.coherence_pilot_cohort` |
| `systems_integration_count` | the count that qualified or disqualified the company |
| `matched_to_company_id` | comparison rows only; FK to the over-firing company it pairs with |
| `included_at` | |
| `framework_version` | |

Populated by `scripts/coherence_pilot.py` (dry run by default, idempotent on `--apply`).
Cohorts as of 2026-09-08:

| cohort | company | systems_integration | total observations | matched to |
|---|---|---|---|---|
| over_firing | A029 SpartanNash | 4 | 15 | |
| comparison | A015 Adolfson & Peterson | 0 | 13 | A029 |
| over_firing | A048 Penske Logistics | 3 | 17 | |
| comparison | A019 Co-Diagnostics | 1 | 13 | A048 |
| over_firing | C0002 Mack Group | 3 | 11 | |
| comparison | A033 HITT Contracting | 1 | 11 | C0002 |

Three judgment calls the handoff left open, made in the script and documented in its
docstring:

1. **Which observations count.** All released rows with `topic = systems_integration`,
   regardless of grade. The hypothesis is about over-firing and the low-grade tier is where
   over-firing shows up; 36 of the 38 such rows are low-grade, so excluding them would
   remove the phenomenon under test.
2. **Whether providers are eligible.** Decided by the data rather than by argument: no
   `provider_benchmark` company clears the threshold and none is near enough to be a
   nearest match. The pool is buyers-only regardless, because a provider's evidence profile
   (seller service pages only) makes "closest total observation count" a meaningless pairing.
3. **Tie-breaking.** Closest absolute difference in total count, then lowest `company_id`,
   and no comparison company is used twice. The greedy assignment was checked against an
   exhaustive search over the fourteen nearest candidates and is optimal (summed difference
   6).

**Success criterion, exploratory only:** a shared `COH-F` candidate appearing at synthesis
for ≥ 60% of the `over_firing` cohort, at a visibly lower rate in `comparison`. This is a
threshold for "worth investigating further", not a pass/fail gate on anything else. **No
significance testing is built**, per the handoff.

With three pairs, the criterion resolves to "2 of 3 over-firing companies share a family".
That is a small cohort and the finding it can support is correspondingly weak; it is a
direction-finder, and the report must say so wherever it is quoted.

### 13.4 The seed data, and the gap that preceded it

The build handoff of 2026-09-08 named `Coherence_Framework_Taxonomy_v0.1.xlsx` as attached;
it was not delivered with the first hand-off, so the table was created and left empty and
the 46 rows were **not** reconstructed — 22 dimension definitions, 19 failure families with
their I–V groups and 5 generative forces are the framework's substance, not a mechanical
transform of anything already in the repository, and inventing them would have put
unreviewed text under a `framework_version` Signal Advisor had ruled on.

The file arrived later the same day and the rows are loaded as specified. The source is
committed at `docs/schema/Coherence_Framework_Taxonomy_v0.1.xlsx`, so the load is
reproducible from the repository alone.

Everything else in this section was built before the seed arrived and needed no change when
it did: the schema, the vocabularies, the bindings, check 11, and the pilot cohort — which
depends on no taxonomy row, and is why §13.3 was populated first.

### 13.5 `Coherence_Family_Dimensions` — the family-to-dimension mapping (addendum)

The open item §13.1 flagged, decided by the addendum of 2026-09-08: a **normalized table**,
not a `dimensions_implicated` column on `Coherence_Framework_Taxonomy`. The mapping is
many-to-many, so a column would mean a delimited list in one cell and would break the join
§2's synthesis needs; the taxonomy stays one uniform row shape across all three entity
types; and the mapping versions independently, so a revision that changes which dimensions a
family implicates is new rows here rather than a `superseded_by` chain there.

| column | notes |
|---|---|
| `family_id` | FK → `Coherence_Framework_Taxonomy.id`, must resolve to `entity_type = 'failure_family'` |
| `dimension_id` | FK → `Coherence_Framework_Taxonomy.id`, must resolve to `entity_type = 'dimension'` |
| `framework_version` | must match both referenced rows' version |
| `role_note` | nullable source qualifier |

PK `(family_id, dimension_id, framework_version)`. No `superseded_by`: a mapping change is
new rows at a new version, the same discipline as the taxonomy table.

**Loaded 2026-09-08 by `scripts/load_coherence_family_dimensions.py`: 127 rows across 19
families.** Every one of the 22 dimensions is implicated by at least one family even
excluding `COH-F19`. `role_note` is set on exactly four kinds of row: the three source
qualifiers (`COH-F04`→`D06` "incentive", `COH-F07`→`D20` "sequencing", `COH-F09`→`D08`
"decision") and the 22 `COH-F19` rows ("cross-cutting / special status"). The other 102 are
null.

`COH-F19` ("The coherence-role paradox") is the one family whose source cell reads
"All — this is the cross-cutting case" rather than listing dimensions. Per the addendum it
expands literally to all 22, each its own row, so every family has a real queryable
dimension set and synthesis need not special-case a family id.

Check 11 enforces the table in the workbook as well as the loader enforcing it at write:
both ends must resolve in the taxonomy, to the correct `entity_type`, at a matching
`framework_version`, and the triple must be unique. Proved on a scratch copy — a family id
in the dimension column, a dimension id in the family column, an unknown id and a duplicate
triple each fail.

#### 13.5.1 The row count in the addendum is wrong; the data is not

The addendum states "18 families × their listed dimensions = **82** rows, plus COH-F19's
expansion below = **100** rows total", and instructs that a mismatch means "either this
transcription or the archived source has an error worth finding, not a validator to relax".
The diff was run before anything was written. **Neither the transcription nor the source has
an error — they agree exactly, family for family, set for set, including all three
qualifiers.** Both figures in that sentence are arithmetic slips:

- the addendum's own table lists **105** dimension references across F01–F18, not 82, and
  the archived source independently lists the same 105; and
- even taking 82 as given, 82 + 22 = **104**, not the stated 100.

The verified total is **105 + 22 = 127**, and `EXPECTED_ROWS` in the loader is 127 for that
reason. This is not the validator being relaxed to fit a suspect source: the escalation
existed to catch a data discrepancy, the diff establishes there is none, and every one of
the 127 rows traces to a dimension named in both independent artifacts. Enforcing 100 would
require discarding 27 mappings that both sources agree on.

The loader keeps the cross-check permanently: it parses the archived workbook, holds the
addendum's table as a constant, and **refuses to load if the two ever disagree** — so this
diff is re-run on every invocation rather than being a one-time reassurance.

