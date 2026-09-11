# Build Handoff — Schema Implementation

**For:** overnight Claude Code session, 2026-08-27
**Source specs:** `attempts_schema_spec.md` (Rev 5), `repo_structure_spec.md`

The specs carry the reasoning. This file carries the exact column orders and sequence, so
nothing gets inferred at 3am. Sheet column order is authoritative — `CLAUDE.md` treats
Observations' order as part of the schema contract, and these follow that pattern.

---

## 0. Before anything — confirm the workbook

Do not build against a workbook that fails these three assertions:

1. `Companies!A2` is `C0001` **and** `Companies!B2` is `Midmark Corporation`
2. `Findings` has no rows below the header
3. `Harness_Runs` row 2 has `harness_id = H-FMCSA-01`

Prefer the path Matthew confirms. If unconfirmed, fall back to the most recently saved
candidate — but **recency is a weak tiebreaker here**: the known-stale copy has the Anvil-100
import applied to a pre-cleanup base, so it may well carry a newer mtime than the correct
file. The content assertions above decide it, not the timestamp. Abort loudly on failure
rather than proceeding.

---

## 1. Prerequisite: add `source_id` to `Source_Families`

`Harness_Sources` needs an FK target and `Source_Families` currently has no key. Add
`source_id` as the new first column, populate `SRC-0001`… in existing row order. Non-breaking.

---

## 2. `Lookups` — six new vocabulary columns

Existing sheet is one column per vocabulary, values down. Append as columns J–O:

| Col | Vocabulary | Values |
|---|---|---|
| J | `attempt_outcome` | covered, absent_confirmed, partial, not_covered |
| K | `failure_stage` | discovery, fetch, entity_resolution, extraction, classification, temporal, governance |
| L | `failure_category` | 16 values — spec §4 table, in stage order |
| M | `fix_class` | transient, code_change, source_limitation |
| N | `attempt_scope` | scoped, incidental |
| O | `harness_source_role` | primary, supporting, resolution_only |

**Bind Lookups source ranges to row 50, not 20.** Existing validations reference
`Lookups!$G$2:$G$20`. `failure_category` has 16 values today and is explicitly
additive-only, so it will pass 19 within weeks — and a vocabulary value past the source
range silently never appears in any dropdown. This is the same failure as the 500-row
binding, on a different axis. Better still, convert the Lookups columns to Excel Tables so
they self-extend; row 50 is the minimum acceptable fix.

---

## 3. New sheet: `Attempts` (20 columns, this order)

```
attempt_id, run_id, harness_id, harness_version, company_id,
attempted_signal, evidence_family, outcome, failure_stage, failure_category,
failure_detail, fix_class, records_written, records_reconciled, output_sheet,
scope, candidates_evaluated, candidates_discarded, attempt_timestamp,
source_url_attempted
```

Validation, bound `2:250000`:

| Col | Field | Source |
|---|---|---|
| F | `attempted_signal` | `Signal_Types` — see §4 |
| G | `evidence_family` | `Lookups!$G` |
| H | `outcome` | `Lookups!$J` |
| I | `failure_stage` | `Lookups!$K` |
| J | `failure_category` | `Lookups!$L` |
| L | `fix_class` | `Lookups!$M` |
| P | `scope` | `Lookups!$N` |

Verified: a 250,000-row binding across 7 columns adds no measurable file size or save time,
since openpyxl stores it as a range reference. No reason to compromise on the number.

---

## 4. New sheet: `Signal_Types` (registry stub)

```
signal_type_id, signal_type_name, signal_class, evidence_family, status
```

`signal_class` is `evidence` or `prerequisite`; `evidence_family` is required for the former
and null for the latter (spec §11 C10).

Signal Advisor owns the contents and the taxonomy is not settled. **Seed with only what
exists today** — `carrier_registry_status` (H-FMCSA-01), `job_posting` (H-JOBPOST-01),
`executive_identification` (prerequisite, H-EXECID-01) — and leave `Attempts.attempted_signal`
as free text with no dropdown until the registry is populated. Binding a dropdown to an
unfinished vocabulary would reject valid values from harnesses built next week.

---

## 5. New sheet: `Harness_Sources`

```
harness_id, harness_version, source_id, role, notes
```

Composite key on the first three. `role` validated against `Lookups!$O`.

---

## 6. New sheet: `Company_Executives` (17 columns)

```
executive_id, company_id, full_name, name_variants, title, title_normalized,
role_relevance, source_url, source_grade, publication_date, retrieval_date,
harness_id, harness_version, status, superseded_by, confidence_0_1, review_status
```

`source_grade` and `review_status` reuse the existing Observations vocabularies —
`Lookups!$C` and `Lookups!$B`. Empty until H-EXECID-01 exists; create the sheet now so the
schema is complete for review.

---

## 7. `Harness_Runs` — six rollup columns

Append: `attempts_total`, `attempts_covered`, `attempts_absent_confirmed`,
`attempts_partial`, `attempts_not_covered`, `coverage_rate`.

All computed over `scope = scoped` rows only. `coverage_rate` counts `absent_confirmed` as
coverage.

Leave `target_evidence_family` in place, redefined as *primary* family (spec §10 C6).
`known_issues` stays for now but becomes derived once `Attempts` has data — do not delete
the column tonight.

---

## 8. Run `extend_validation.py`

After the new sheets exist, so it catches them: `Observations` and `Companies` to 20,000,
`Attempts` to 250,000. Dry run first, then `--apply`. It backs up automatically.

---

## Do NOT build tonight

**`Discards`.** No classification harness exists. The sampling design (spec §12) needs a
real harness to size against, and an empty sheet for a hypothetical harness is the
retrofitting-in-advance this project is trying to avoid.

**Backfill of H-FMCSA-01 / H-JOBPOST-01 attempts.** Feasible from `harness_output/`
resolution logs (spec §10 C5), but it requires judgment about what counts as an attempt in
runs that predate the concept. Wants a person awake.

**Folding `PIVOT_UPDATE.md` into `CLAUDE.md`.** Flagged to Matthew — the approved version
and the later recommendation describe two different end states (one doc with history
embedded, vs. `CLAUDE.md` as pure current state plus an append-only `DECISIONS.md`). Get
the call before doing either; a fold done tonight has to be re-split tomorrow if the answer
is the latter.

---

## Verification before ending the session

- `extend_validation.py --db <path>` reports no pending changes
- Every new sheet loads, and its validations survive a save/reload round-trip
- `Observations`, `Companies`, `Harness_Runs`, `Findings` row counts are unchanged
- A timestamped backup of the pre-build workbook exists
