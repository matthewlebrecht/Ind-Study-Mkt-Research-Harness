# Gate — new harness output

**Load this fresh at the checkpoint. Do not read it while building a harness.**

That is not a stylistic preference. If the audit criteria are visible while the extraction
rules are being written, the extraction rules get written to pass them — the harness learns
the shape of the sample rather than the shape of the evidence, and the audit stops
measuring anything. Build the harness against the source. Then stop, load this, and audit
what came out.

---

## When this fires

When a new harness — or a new **version** of an existing harness whose extraction rules
changed — produces its first output. Including a run that resolves entirely to
`absent_confirmed`: an absence claim is evidence with weight (convention 6a), and a harness
that confidently reports nothing everywhere is a harness that may simply be broken.

Until the audit artifact exists, the run's `publication_status` is `quarantined`, its rows'
`publication_state` is `quarantined`, and **no coverage number for that run is reported
anywhere** — not in the session report, not in a commit message, not in conversation.
Row counts may be reported. Coverage percentages may not.

---

## The procedure

### 1. State the population

`population_size` is the number of rows the run wrote. Everything downstream is a fraction
of a stated denominator or it is not a number at all.

### 2. Draw the adversarial strata

These sample where defects have actually been found before. They are **not**
extrapolatable — they are drawn from the corners on purpose, so their rates describe the
corner and nothing else. Never quote a stratum rate as a precision rate.

Sample every stratum that applies to the harness. A stratum with no rows in this run is
recorded with `sampled_n: 0` and its `selection_rule`, not omitted — omission is
indistinguishable from "we did not look".

| stratum_id | Selection rule | What it is looking for |
|---|---|---|
| `single_common_word` | Rows whose company match rests on one dictionary-word token (PRIME, SUMMIT, LIBERTY, MACK) rather than the full company phrase | Convention 31. The Prime Inc. bug: four press releases about four different companies. |
| `off_own_domain` | Rows whose `source_url` host is not the company's own domain | Third-party pages are about whoever the page is about, which is often not the company. |
| `index_listing_url` | Rows sourced from an index, listing, tag, category, search-results or aggregation URL | 40 of H-FIRSTPARTY-01 v1.0's rows came from PR-wire index pages — a list of headlines read as an announcement. |
| `polysemous_term` | Rows whose match term is `integration`, `platform`, `solutions`, `transformation`, `digital`, `modernization`, `ai`, `automation`, `cloud`, `optimization` | "Our integrated platform" in an earnings release is not an announcement about systems integration. |
| `eponymous_name` | Rows where a person's surname is also a token of the employer's name (McGough, Mack, Duke, Herzog, Joeris) | Proximity attribution is worthless here: every mention of the company satisfies it. Only explicit attribution counts. |
| `a_graded` | **All** rows with `source_grade = A` | Not a sample — a census. An A grade is the strongest weight the evidence base can carry, so every one of them is checked. |
| `suppressed_judged` | Rows drawn from **`Attempts`**, not Observations: outcome rows carrying `failure_category = suppressed_redundant_judged` | The only stratum that can fail a harness for **over-suppression**. Every other stratum samples rows that were written, so the gate would otherwise measure precision only and could never catch a harness that quietly threw away good evidence. The verdict here is whether the suppression was *correct*, not whether a claim was supported. It does not need to be extrapolatable to be worth having. |

### 3. Draw the random control

A simple random sample of the run's rows, drawn from the whole population with no
stratification. **This is the only sample that produces an extrapolatable precision rate**,
and its denominator (`population_n`) is stated explicitly in the artifact and in every
place the rate is ever quoted. A precision rate without its denominator is the same defect
as a failure table with no attempts table: it cannot distinguish "rare" from "we stopped
looking".

~30 rows, or the whole population if smaller.

### 4. Judge every sampled row against four verdicts

Read the row, open the source, and decide:

- **`supported`** — the evidence excerpt supports the claim the row makes, at the strength
  the row claims, about the company the row names.
- **`overgraded`** — the claim is real but the row overstates it: `committed_action` where
  the source shows an intention, `repeated_pattern` off a single instance, an A grade on a
  C source. The row survives at a lower strength.
- **`unsupported`** — the evidence does not support the claim *at all*. **Exclude the row.**
  Convention 32: do not downgrade it to `weak_clue`. A press release mentioning
  "integration" once is not an announcement about systems integration at any strength, and
  admitting it weakly still puts a false row in front of a reviewer and into every count.
  Decide admission first, strength second.
- **`wrong_entity`** — the row is about a different company, or attributes a statement to a
  person who did not make it. **Exclude the row, and see the stop rule.**

### 5. Apply the stop rule

Either of these quarantines the run. The harness goes back for a fix; **no coverage number
publishes either way**, including a corrected one computed after excluding the bad rows —
a run whose sample failed has an unknown defect rate outside the sample.

1. **Any `wrong_entity` finding, anywhere, at any count.** This is deliberately not a rate.
   One row about the wrong company means the identity test is wrong, and identity defects
   are not randomly distributed: the Prime Inc. bug had a 100% failure rate within its
   corner and 0% everywhere else. A threshold would be averaging over a population the
   defect does not live in.
2. **Random-control exclusion rate above `threshold_applied`.** Exclusions are
   `unsupported + wrong_entity`; `overgraded` is a downgrade, not an exclusion. The value
   in force is recorded as a literal in every artifact.

### 6. Write the artifact

`harness_output/audits/<harness_id>__<harness_version>.json`, keyed on **version**, not
run — a version is a set of extraction rules, and two runs of one version share its
defects. The sampled `run_id` is recorded inside. Schema and field list: `core/audit.py`.

`reprocessing_required` is **derived from the artifacts, never written into one**
(`core/audit.py::derive_reprocessing_required`). A `wrong_entity` finding that no later
passing audit supersedes sets it for the audited version **and all prior versions** of that
harness. Narrowing that radius requires `defect_introduced_in` with a stated justification,
because "the bug was only in v1.2" is a claim about code history someone has to have
actually checked.

### 7. Write the human review sheet

`harness_output/audits/<harness_id>__review.md` — the **random control sample only**, as a
flat table, one row per line: claim, evidence excerpt, source URL, matched term, the
machine's verdict, and its confidence.

The adversarial strata are mechanical and can be judged by the same process that built the
harness. The random control is the sample the precision rate comes from, and a precision
rate a harness computed about itself is not a measurement. That one needs independent human
judgment.

---

## Exemptions

`docs/gates/grandfathered_harness_versions.json`, an explicit list of
`(harness_id, harness_version)` pairs each carrying a reason and a date added. This is the
**only** exemption mechanism — there is deliberately no date scoping. A rule that says
"first run on or after 2026-09-01" has a boundary for a harness to land on, and
H-EMPREVIEW-01 was straddling exactly that boundary while this gate was being written.
A list of pairs has no boundary.

Adding a pair to the registry is a decision that gets logged, not a way around a failing
audit.
