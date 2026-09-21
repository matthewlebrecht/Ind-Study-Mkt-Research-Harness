# Coherence pilot — attempt to execute the scoped test, 2026-09-15

Asked for: run the scoped test — companies with `systems_integration` firing ≥ 3 times, a matched
comparison group on total observation count, and `COH-F` tag co-occurrence checked against the 60%
exploratory threshold.

**The test cannot return a result, and the reason is not that it ran and found nothing.** Three
things block it, one of them structural. Everything below is recomputable; no workbook row was
written by this diagnostic.

---

## 1. What exists, and what does not

| Piece | State |
|---|---|
| Cohort assembly (`scripts/coherence_pilot.py`) | **Built and populated.** `Coherence_Pilot_Runs` holds COHP-0001, 6 rows: 3 over-firing, 3 matched comparisons |
| Framework taxonomy | **Loaded.** 46 rows — 22 dimensions COH-D01..D22, 19 failure families COH-F01..F19, 5 generative forces |
| Family → dimension join | **Loaded.** `Coherence_Family_Dimensions`, 127 mappings, 19 families × 22 dimensions |
| `Observation_Coherence_Tags` | **Empty — 0 rows** |
| A writer for that table | **Does not exist.** There is no `core/coherence.py` |

Every other overlay table in this project has a single dedicated writer enforcing its row rules —
`core/directionality.py::append_tags`, `core/validity.py::append_determinations`,
`core/role_review.py::append_reviews`. The coherence tag table has the sheet and the validator
(check 11) but no writer. Nothing can put a tag in it without writing that module first.

## 2. The hypothesis is stated in COH-F; the table only holds COH-D

`Coherence_Pilot_Runs.hypothesis` reads *"systems_integration over-firing correlates with COH-F
tag(s)"*. But the tag table's column is `coherence_dimension_candidate`, and check 11 constrains
tagging to `COH-D*` dimensions only — a COH-F value cannot be written there and the validator fails
if one is.

This is not a contradiction, it is an unstated two-step: observations are tagged with **dimensions**,
and families are reached by joining through `Coherence_Family_Dimensions` at synthesis. That join is
loaded and usable. But it means "check COH-F tag co-occurrence" is shorthand for a procedure —
tag 66 observations with COH-D candidates, then join 19 families × 22 dimensions — that has never
been specified, let alone run.

## 3. The over-firing cohort does not survive the validity determinations

The cohort was assembled 2026-09-08. Since then 111 observations have been recorded invalid. The
pilot script counts **released** rows and — correctly, under the convention 41 wall — does not read
validity at all. So the cohort it produced counts rows that are now recorded invalid.

Recomputed today, released `systems_integration` rows = 38, of which **6 are recorded invalid**:

| Company | systems_integration rows (all released) | valid only | clears the floor of 3? |
|---|---|---|---|
| A029 SpartanNash | 4 | 4 | yes → yes |
| A048 Penske Logistics | 3 | 3 | yes → yes |
| **C0002 Mack Group** | **3** | **1** | **yes → NO** |

**The over-firing cohort is 3 companies on all released rows and 2 companies on valid rows only.**
C0002 leaves it: two of its three `systems_integration` rows are recorded
`invalidated_extraction_defect`.

Two further facts about the same population, both load-bearing for how this gets written up:

- **36 of the 38 released `systems_integration` rows are low-grade.** The pilot's own design note
  says so and admits them deliberately, on the grounds that over-firing is where the low-grade tier
  shows up. That is defensible, but it means the phenomenon under test is almost entirely the
  extractor's weakest admission tier.
- The committed cohort has **already drifted**. COHP-0001 records A019 Co-Diagnostics as A048's
  matched comparison; re-running the same script today derives **A032 Gilbane** instead, because
  total observation counts moved as later harness versions published. The pilot rows are a dated
  record, not a reproducible derivation.

## 4. What the 60% threshold resolves to at this cohort size

The success criterion is exploratory: ≥ 60% of the over-firing cohort sharing a COH-F candidate,
visibly above the comparison cohort. No significance test, by the handoff's own instruction.

- On the committed cohort of **3**: 60% → **2 of 3 companies**.
- On the valid-rows cohort of **2**: 60% → **2 of 2 companies**.

Either way **a single tagging judgment on a single company decides whether the pilot passes or
fails** — and the tagging is the interpretive step no procedure exists for. A threshold applied to a
cohort this small cannot separate a real pattern from one tagger's reading of one company.

## 5. What executing it would actually take

1. Write `core/coherence.py::append_tags` — all-or-nothing, idempotent, refusing non-`COH-D` values,
   behind the convention 41 wall, as the other three overlay writers are.
2. Tag the cohort. **66 valid released observations** across the 7 companies involved:

   | Cohort | Company | released | valid |
   |---|---|---|---|
   | over_firing | A029 SpartanNash | 15 | 9 |
   | over_firing | A048 Penske Logistics | 14 | 12 |
   | over_firing | C0002 Mack Group *(leaves on valid rows)* | 12 | 10 |
   | comparison | A015 Adolfson & Peterson | 15 | 7 |
   | comparison | A019 Co-Diagnostics *(as committed)* | 10 | 6 |
   | comparison | A032 Gilbane *(as re-derived)* | 14 | 13 |
   | comparison | A033 HITT Contracting | 12 | 9 |

3. Decide, before tagging, the three things the cohort drift exposes: whether the pilot counts
   invalid rows, whether the cohort is refrozen or re-derived, and who assigns a dimension candidate.

Step 3 is a judgment about the framework, not a coding task, and steps 1–2 are wasted if it goes the
other way.

## 6. Recommendation

**Do not tag 66 observations to run a 2-of-2 test.** The blocking problem is not the missing writer;
it is that the cohort is too small for the threshold to mean anything, and it shrank further under
the validity determinations. The cheapest thing that would make this pilot informative is a larger
over-firing cohort — which means either lowering the floor below 3 (and stating that the cohort is
then dominated by the low-grade tier) or waiting for more `systems_integration` evidence.

**CLOSED AS MOOT, 2026-09-20 (Matthew).** The disposition below was finalised without answering
these: the framework is built and scoped, the evidence volume is insufficient to execute the test
meaningfully, and that is what the report appendix records
(`docs/report_appendix_dispositions.md` §A). The four questions only bear on a run that is not
going to happen, so they are not open items awaiting a ruling. They are kept here as the record
of what executing the pilot would have required:

1. Does the pilot count observations recorded invalid? (Today it does, because it may not read
   validity — so this is a design question, not a bug.)
2. Is COHP-0001 refrozen as committed, or re-derived and appended as COHP-0002?
3. Is the over-firing floor still 3, given that it now yields 2 companies on valid rows?
4. Who assigns `coherence_dimension_candidate`, and against what written procedure?
