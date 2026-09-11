# Harness Advisor — Audit Gate Schema Decisions (2026-08-31)

**Timing: needed tonight.** Session 3 dispatches unattended once session 2 finishes, and
the gate is the first task in that session. If any of these are still open at dispatch
time I'll have Claude Code make a provisional call and flag it, but I'd rather have your
answers baked in.

## What's new since we last talked

Session 2's self-audit caught 9 instances of the loose-pattern-matching failure mode
(conventions #16, #31–33) *before* commit — 258 candidate rows corrected down to 87 real
ones. That audit happened because I asked for it, not because anything forced it. I want
to make it structural.

The design: a new harness's first run cannot publish a coverage number until an audit
artifact exists. Output is quarantined on write, rollups exclude it, and a mechanical
check in `validate_repo_db.py` enforces the pairing — same shape as the existing
`harness_version` ↔ manifest assertion.

Sampling is adversarially stratified (single-common-word entity matches, off-own-domain
sources, index/listing URLs, polysemous theme terms, eponymous-firm names, all A-graded
rows) plus a small random control. Only the random control produces an extrapolatable
precision rate. Verdicts are four-way: supported / overgraded / unsupported /
wrong-entity.

Gate content lives in `docs/gates/*.md`, loaded at the checkpoint rather than held in
context during the build — if the audit criteria are visible while the harness is being
written, the harness gets written to pass them.

## Decisions I need from you

**1. `pending_audit` as a `review_status` value.**
Lookups vocabulary addition + validation binding. Main thing to check: interaction with
the never-overwrite-human-review rule. A re-run hitting a row that's still `pending_audit`
should presumably be free to overwrite, but one promoted to `accepted`/`corrected` by the
audit should not — is that the right line, and does it need a separate column to
distinguish "machine-set pending" from "human-set" cleanly?

**2. Rollup exclusion.**
Which `Harness_Runs` columns exclude quarantined rows? Does this need a third counter
alongside `records_written` / `records_reconciled` — e.g. `records_quarantined` — or is it
derivable? Keeping in mind the earlier lesson that counting only new Observations punished
idempotent re-runs.

**3. Audit artifact — path, filename, schema.**
Proposed: one artifact per harness-version-run, fixed path, with sample composition,
per-stratum verdict counts, the random-control precision rate with its denominator stated,
and the pass/fail call. Your call on where it lives and what's required vs. optional.

**4. The seventh mechanical check.**
Assertion: every `harness_version` in `Harness_Runs` with `records_written > 0` has a
matching audit artifact. **Must be scoped forward** — first run on or after 2026-09-01 —
with the existing 8 harnesses in an explicit grandfather list, or it fails against
everything already committed. H-EMPREVIEW-01 is running right now and may land either side
of that boundary; I want the scoping written so session 3 doesn't depend on which.

**5. Does a wrong-entity verdict set `reprocessing_required`?**
This is the one I most want your read on. A wrong-entity finding implies a code defect,
which implies unsampled rows are wrong too — so prior observations from that harness stop
being valid evidence. That's exactly the condition `reprocessing_required` exists for, but
it's currently a manifest-authored field and this would make it gate-authored. Yours to
decide.

## Bundled while we're touching vocabulary

Open item (5) from the 8/27 coordination list is still unresolved: `failure_category` has
no value for "classifier judged this instance redundant vs. prior extractions." Worth
closing in the same pass, since the gate's `unsupported` verdict (exclude entirely, per
convention #32) is adjacent to it and I don't want the two conflated.

## Stop rule, for context on why the schema has to hold this

Any wrong-entity finding, or exclusions above threshold in the random control, keeps the
run quarantined and sends the harness back for a fix. No coverage number publishes either
way. The threshold value itself I'll set — I just need the schema to be able to represent
the state.
