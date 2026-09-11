# Session 3 brief — 2026-08-31 (unattended, overnight)

Read `CLAUDE.md`, then `docs/conventions.md` (authoritative over this file), then this.

**Mode:** unattended. Matthew is asleep and cannot answer questions. Where this brief is
ambiguous, take the more conservative option, log the decision, and move on. Never guess at
an architecture call — log it as an open item for Harness Advisor instead.

**Pacing:** ~45–60 minute soft cap per task. If stuck past that, log and move to the next
task. Commit incrementally, not just at the end. Use `python -u` for long runs. Never run
two harnesses concurrently — chain them.

**Git:** commits are authored as Matthew (repo-local identity is already set). Do not
rewrite prior "Claude Code" commits.

---

## Step 0 — hard abort checks

Run all of these before touching anything. If any fail, log and stop.

1. Existing workbook-confirmation content assertions (per `CLAUDE.md`).
2. `git status` clean — no uncommitted changes from session 2.
3. No rows in `Harness_Runs` with a null end timestamp (would indicate a session still
   running).
4. `python scripts/validate_repo_db.py` passes.

Content wins over file recency. Do not reconstruct the workbook — if it looks wrong, stop.

---

## Task 1 — audit gate infrastructure

Full spec: `harness_advisor_response_audit_gate_2026-08-31.md`. Summary of what to build:

**Observations — three new columns.** Do not add `pending_audit` to `review_status`.

- `publication_state` — `quarantined` / `released`. Machine-authored, freely overwritable.
- `audit_verdict` — `supported` / `overgraded` / `unsupported` / `wrong_entity`. Null until
  audited. Machine-authored, freely overwritable.
- `review_source` — `human` / `machine`.

**Rewrite the never-overwrite rule to key on provenance, not value:** a re-run may overwrite
any row whose `review_source` is `machine` or empty; it may not overwrite a row whose
`review_source` is `human`. Backfill `review_source = human` for the 27 reviewed rows.

**Harness_Runs — two new columns.**

- `publication_status` — `quarantined` / `published`
- `records_excluded_by_audit`

Do **not** add a `records_quarantined` counter. Exclusion is a filter at the rollup layer,
never a mutated count. A quarantined run contributes **neither numerator nor denominator**
to published coverage; its `Attempts` rows are excluded by join on `run_id`, not by a
duplicated status column.

**Attempts vocabulary:** split the existing `suppressed_redundant` outcome into
`suppressed_redundant_key` (deterministic dedup) and `suppressed_redundant_judged`
(classifier judgment). This closes long-open coordination item (5) — it is **not** a
`failure_category` value.

**CRITICAL — validation read-back.** Five new validated columns are being added, and all
nine dropdown validations silently vanished from this workbook for three days in August.
After writing, **reopen the saved workbook from disk** and assert every validation — the
existing set plus the new ones — is present and correctly bound. Not "we set them";
"we reopened the file and they are there." Fail the task loudly if any are missing.

### Audit artifact

Path: `harness_output/audits/<harness_id>__<harness_version>.json`. Keyed on harness
**version**, not run; `run_id` recorded inside. JSON, not markdown.

Required fields: `harness_id`, `harness_version`, `run_id`, `audit_date`, `auditor`,
`gate_doc` (path **plus content hash**), `population_size`, `strata[]` (each with
`stratum_id`, `selection_rule`, `sampled_n`, `verdict_counts` across all four verdicts),
`random_control` (`sampled_n`, `population_n` stated explicitly, verdict counts,
`precision_rate`), `row_ids_sampled`, `threshold_applied` (**literal value**, not a config
reference), `stop_rule_triggered[]`, `verdict`, `disposition`.

Optional: `per_row_notes`, `summary_md`, `defect_introduced_in`.

### Mechanical check — numbering matters

`validate_repo_db.py` currently runs **8** checks. Check 7 is the dropdown-validation check
added 2026-08-30. **The audit-gate check is #9, not #7** — an earlier brief said "seventh"
from a stale count. Before adding it, print the current check inventory and confirm the
count. Do not renumber or replace existing checks.

Check 9: for each `(harness_id, harness_version)` whose run contributes to a published
coverage number — **including runs resolving entirely to `absent_confirmed`** — require an
audit artifact at the path above, unless the pair appears in the grandfather registry.

**Grandfather registry:** a checked-in file enumerating exact `harness_id` +
`harness_version` pairs, each with a reason and date-added. Seed it with the 8 pre-gate
harnesses, plus `H-EMPREVIEW-01 v1.0` (reason: pre-gate build, audit scheduled). No date
scoping — the registry is the only exemption mechanism.

### `reprocessing_required` — derived, not gate-authored

True if declared in the manifest, **or** if any audit artifact for that `harness_id` records
`wrong_entity > 0` and has not been superseded by a passing audit on a later
`harness_version`. Default blast radius: the audited version **and all prior versions** of
that harness. Narrowing requires `defect_introduced_in` with stated justification.

### Gate documents

`docs/gates/gate_new_harness_output.md`. `CLAUDE.md` holds only the trigger — "when a new
harness produces its first output, stop and read this gate before reporting coverage" — not
the content. Load the gate fresh at the checkpoint; do not hold it in context while building
a harness.

Strata: single-common-word entity matches; off-own-domain sources; index/listing/aggregation
URLs; polysemous theme terms (integration, platform, solutions, transformation); eponymous
company names; all A-graded rows. Plus a small random control — the **only** sample that
produces an extrapolatable precision rate, with its denominator always stated.

**Suppression stratum** (Harness Advisor's flagged gap): every other stratum samples rows
that were *written*, so the gate measures precision only and cannot fail a harness for
over-suppression. Add a stratum sampled from `Attempts` rows with outcome
`suppressed_redundant_judged`; the verdict is whether the suppression was correct. It does
not need to be extrapolatable to be worth having.

**Stop rule:** any `wrong_entity` finding, or exclusions above threshold in the random
control, keeps the run quarantined and sends the harness back for a fix. No coverage number
publishes either way.

---

## Task 2 — Signal_Types registry: naming and seed

**Naming collision, resolve carefully.** `signal_class` already exists with the 2026-08-27
meaning: `evidence` / `prerequisite`, evidence family nullable when prerequisite. That is
what lets `H-EXECID-01` exist as a prerequisite harness. **Do not redefine it.**

The new instrument-bias axis is a separate field, `instrument_class`, values `IC1`–`IC4`.
Full definitions in `taxonomy_patch_2026-08-31_rev2.md`. Taxonomy dimension only — add it to
the `Signal_Types` registry, not to `Observations`.

Seed the registry with the trade press and vendor signal types from the patch (§7). Register
new sources via `scripts/register_sources.py`, then
`scripts/sync_harness_sources.py --apply`, or the validator will fail.

---

## Task 3 — H-EMPREVIEW-01 access pass

The harness is built and its access finding is real: Glassdoor, Indeed `/cmp/`, and
CareerBliss all disallow compliant automated collection. **Do not switch user-agent. Do not
attempt authenticated access.** That decision is final and correct.

Right now the finding lives only in prose, so the database reads family 4 as simply absent.
Run the harness across all 108 companies so `core/robots.py` writes `access_blocked` attempts
with citable robots.txt reasons. An access refusal is a determinate outcome in the same
family as `absent_confirmed` — it belongs in the database.

Write the `Harness_Runs` row. `publication_status = quarantined`; it contributes no coverage
number, so check 9 is not triggered.

If time is short, this is a 15-minute task — do not skip it.

---

## Task 4 — H-TRADEPRESS-01 (subset run)

**Deliberately ahead of the API harnesses.** All four of those produce `buyer_acts`, and the
evidence base is 185 `buyer_acts` to 87 `buyer_articulates`. Trade press is the only harness
in this session that widens the articulation leg, and it should be built while the session is
fresh.

Extraction rules: `taxonomy_patch_2026-08-31_rev2.md` §8. Do not improvise them.

Sources: Construction Dive, Transport Topics, FleetOwner, Food Dive, MedTech Dive and
comparable verticals matched to the company's industry.

Five signal types, **extraction is per-claim, not per-document** — one article may yield
several observations at different families and roles:

- `ST-EXECQUOTE-REPORTED` → `buyer_articulates`, full grade. **Weight the crawl toward
  this** — the highest-value articulation type available.
- `ST-EXECCOLUMN` → `buyer_articulates`, full grade.
- `ST-EXECPANEL` → `buyer_articulates`, capped −1 (paraphrase of spoken remarks).
- `ST-PRESSPROFILE` → `buyer_acts` **only**, capped −1. Splits at artifact level: a reported
  concrete action is admissible; journalist *characterization* generates no observation.
  **Hard rule — never carries `buyer_articulates`.**
- `ST-WIREREPRINT` → **reclassify to first-party, do not discard.** Route to
  H-FIRSTPARTY-01's family/role, run the normal redundancy check. If already held →
  `suppressed_redundant_key`, still counts toward `signal_strength`. If not held → genuinely
  new first-party evidence, admit it. Reclassified rows never count toward trade press
  articulation yield.

Wire marker grading: a PRNewswire / BusinessWire / GlobeNewswire byline or explicit "press
release" label is conclusive alone. An "About [Company]" boilerplate footer is **not** —
it fires only in combination with no reporter byline.

**Run against a subset of 10–15 companies**, chosen to span the industry mix (construction,
trucking, energy, consumer goods, medical devices, food distribution). Not the full 108. The
purpose is an auditable first output small enough to review properly tomorrow, not a coverage
number.

Output is quarantined. Report row counts only. Do not claim a coverage percentage.

---

## Tasks 5–8 — API harnesses, in this order

All four are `buyer_acts` producers, IC3/IC4, full universe (108) unless noted. Each:
register sources, build, run, quarantine output, emit an audit review sheet (below), commit.

**5. `H-PROCUREMENT-01`** — USASpending + SAM.gov. Note the expected shape: most of these
companies appear as award *recipients* (selling to government), not as buyers issuing RFPs.
Yield may be low and that is a finding, not a failure. Record `absent_confirmed` where the
company genuinely has no federal record.

**6. `H-PRODUCTQUALITY-01`** — federal recall and complaint databases matched to industry:
openFDA device recalls/MAUDE (medical devices), NHTSA recalls and complaints (trucking),
CPSC and FDA food recalls (consumer goods, food distribution). IC4 — involuntary disclosure,
the class the evidence base is shortest on.

**7. `H-PATENTS-01`** — PatentsView. Expect genuine absence across much of this universe;
`absent_confirmed` is the correct outcome for a company with no patent activity.

**8. `H-LEGAL-01`** — CourtListener + NLRB.

---

## Task 9 (stretch) — H-VENDOR-01

Only if Tasks 1–8 are complete and committed. Head start: 24 vendor-published customer URLs
already logged during the H-EXECVOICE-01 run.

Rules: `taxonomy_patch_2026-08-31_rev2.md` §9. Multi-role artifact — buyer quote
(`buyer_articulates`, capped −1), deployment fact (`buyer_acts`, **full grade, the strongest
leg**), vendor framing (`provider_market_responds`). Attribution gate: `ST-VENDORQUOTE`
requires a **named individual with a title**; anonymous attributions drop the quote and keep
the deployment fact.

**Accounting rule:** H-VENDOR-01 is IC1 throughout and does **not** count as progress against
the articulation-bias gap, whatever its yield. Record it as volume, not widening.

---

## Audit review sheets — required for every new harness

For each harness built tonight, emit `harness_output/audits/<harness_id>__review.md`
containing the **random control sample** as a flat table, one row per line: claim, evidence
excerpt, source URL, matched term, your own verdict, and your confidence.

This is what Matthew reads tomorrow. Do the mechanical and adversarial strata yourself; the
random control needs independent human judgment and is the sample the precision rate comes
from. Keep it to ~30 rows per harness.

---

## Explicitly out of scope tonight

- **No gap report regeneration.** No `core/topics.py` edits.
- **No absolute evidence-base totals** in the session report. State deltas from tonight's
  runs only — "H-TRADEPRESS-01 wrote N rows, quarantined." Totals get recomputed after the
  audits.
- **No re-audit of the 87 existing `buyer_articulates` rows.** Pre-gate, already audited once
  in session 2, and their stratified review is separate Week 4 work.
- **No `DECISIONS.md` seeding.** Separate session.
- **No H-PERMITS-01 or H-LOCALRECORDS-01.** Jurisdiction-fragmented across dozens of county
  portals and Granicus/Legistar instances; they need a deliberate subset design, not a
  full-universe attempt.

---

## Watch for the characteristic failure mode

Convention 16, extended by 31–33. It has hit nine times. Assume it will hit tonight.

- A single common/dictionary-word token is never an identity match. Coined tokens (MIDMARK,
  KENCO, RYCON) stand alone; dictionary words (PRIME, SUMMIT, LIBERTY) need the full company
  phrase.
- An unsupported claim gets an **admission threshold** — exclude it — not a downgrade to
  `weak_clue`.
- Read twenty rows of a new harness's output before believing its coverage number. Every
  defect worth finding last session was invisible in the run summary and obvious in the rows.
- **Check your correction against the case that was previously working, not just the case
  that was broken.** Tightening company identity fixed Prime Inc. and broke Midmark. The OSHA
  fix replaced a declared cap at 20 with an invisible one at 40.

---

## Session report

At the end, write `session3_report.md`: what was built, row deltas per harness (not totals),
which tasks were reached, open items for Harness Advisor or Signal Advisor, and anything
where this brief was ambiguous and you chose conservatively. List the review sheets awaiting
Matthew.
