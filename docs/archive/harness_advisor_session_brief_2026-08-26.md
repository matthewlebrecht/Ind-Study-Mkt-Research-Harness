# Harness Advisor — Session Brief, 2026-08-26

For the Notion revision log. Deliverable from this session: `attempts_schema_spec.md`
(Rev 4), the audit/metadata system design. Brief items 2 (portfolio visualization) and 3
(repo structure) not started.

## What got decided

**The audit system logs attempts, not failures.** A failure-only table has no denominator —
you can't distinguish a rare failure mode from a harness that quietly stopped trying. New
`Attempts` sheet, one row per (run × company × signal), append-only.

**A confirmed absence is not a failure.** CT Logistics resolving to no USDOT number is the
correct result for a freight-audit firm with no fleet. H-FMCSA-01's real resolution score
is 8/8, not 7/8. Own outcome value (`absent_confirmed`), counts as coverage.

**Two-axis failure vocabulary.** `failure_stage` (where it broke → where to invest
engineering) and `failure_category` (what kind of fix). Flattening these loses the routing.
`fix_class` adds transient / code_change / source_limitation.

**One `harness_id` per logical harness**, not per external API. `harness_id` sits on every
Observation as provenance for a *claim*, and a claim is produced by the whole pipeline —
per-API IDs would force an arbitrary "primary." Split rule: separate harnesses when they
produce independently useful signals, need independent version cadence, or one feeds
another. Shared API calls are not grounds for splitting; shared logic goes to a utilities
module.

**Harness naming:** `H-{SIGNAL_TYPE}-{NN}` going forward. `H-FMCSA-01` is grandfathered,
not renamed — its ID is written into 27 committed Observations and renaming breaks
provenance on reviewed evidence to fix a cosmetic inconsistency. `-NN` is a serial,
orthogonal to `harness_version`.

**A harness may write across multiple evidence families.** Family is a property of the
Observation, not the harness. `Harness_Runs.target_evidence_family` becomes *primary*
family; `Harness_Sources` (new junction sheet) holds the real many-to-many.

**Discard reasons reuse `failure_category`** rather than getting a parallel vocabulary.
"Why didn't this become evidence" gets exactly one controlled list.

**Redundancy suppression sits under `governance`**, not a new stage — nothing broke, a rule
fired. Constraint that matters more than the placement: redundant instances must still be
*counted*. `repeated_pattern` is a signal_strength value one step above `weak_clue`, so
repetition is itself the evidence. A dedupe classifier that drops instances 2–12 deletes
the only basis for that rating.

**`Company_Executives` gets its own sheet**, and exec identification becomes its own
harness (`H-EXECID-01`) because its output feeds several downstream harnesses. Needs
`executive_id` PK, and `publication_date` + `retrieval_date` rather than a single
`last_verified` — otherwise the review-against-cited-date convention can't be applied to
exec titles, which drift exactly like FMCSA snapshots do.

**`known_issues` on Harness_Runs becomes derived**, generated from that run's Attempts rows.
H-JOBPOST-01's "3 of 7 covered, four documented gaps" stops being a maintained string.

## Corrections made mid-session

Three things stated earlier in the session and revised once the project docs arrived:

1. **`attempted_signal` is signal-type-level, not evidence_family.** Was circulated to
   Signal Advisor before `PIVOT_UPDATE.md` was available. Signals are finer than the 18
   families, so the original rule would report a whole family as blind when only one route
   within it failed. Now two columns: signal type + parent family. **Signal Advisor needs
   to know this** — it changes the `Signal_Types` registry they're building.
2. **`Signal_Types` needs a `signal_class` column** (`evidence` / `prerequisite`), family
   nullable. Exec identification produces no evidence family. Same shape as the planned
   opportunistic enrichment of Anvil companies' blank industry/headcount fields.
3. **Coverage counting was wrong.** Original definition counted only new Observations, so
   an idempotent re-run reconciling 27 unchanged rows would have read as 27 misses —
   punishing exactly the behavior that proves stability. Split into `records_written` +
   `records_reconciled`.

Backfill recommendation also flipped: `harness_output/` already logs every resolution
decision including refusals, so resolution-stage attempts can be reconstructed for both
existing harnesses rather than written off.

## Flagged, outside this project's scope

**The `market_intel_db.xlsx` in circulation is stale.** It predates the 2026-08-22 cleanup
— still has the `Example Fleet Logistics Inc.` template row at C0001, which shifts every
pilot ID by one against CLAUDE.md's authoritative list. Its HR-0001 is H-JOBPOST-01 with 42
observations across 15 companies; CLAUDE.md says HR-0001 is H-FMCSA-01 with 27 across 8.
The Anvil-100 import is present, so the CRM import appears to have been applied to a
pre-cleanup copy. Worth confirming which file Claude Code writes to.

**Observations will breach 500 rows in Week 2.** All workbook validation is bound `X2:X500`
and rows past 500 lose validation silently. 35 observations from 8 pilots (~4.4/company)
means ~475 from H-FMCSA-01 alone across 108 companies. CLAUDE.md flags this; it hasn't been
done. Should be fixed before the Week 2 full-universe run.

**Known limitation, stated rather than papered over:** this system records candidates
*rejected*. It cannot see a false positive that was *accepted* — the Infor / "Information
Systems" bug would not have appeared in it. That failure mode belongs to `review_status`
and the Week 4 stratified review.

## Open — needs Matthew

**Storage tier for `Attempts`.** Workbook sheet with wide validation, JSONL files only, or
hybrid. Recommending hybrid (files canonical, workbook holds a bounded current-state view),
but it splits the system of record, which cuts against the "relational evidence database"
framing of the deliverable. The only decision in the spec with a real tradeoff rather than
a defensible default.

## Resume here tomorrow

- Matthew's call on the storage tier above.
- Signal Advisor's response on the two corrections (signal-type granularity, `signal_class`).
- Brief items still undesigned: **harness portfolio visualization** and **GitHub repo
  structure**. Repo structure is the more useful of the two right now — the split rule and
  the shared-utilities question from the logical-harness decision both point at it, and
  visualization is low-value until there are more than 2–3 harnesses to draw.
