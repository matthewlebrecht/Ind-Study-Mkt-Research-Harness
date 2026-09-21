# The 8 overstated invalidation statuses from HR-0083

Finding first. A proposal is at the end, separated, so the finding can be judged on its own.
Nothing has been recorded: all 8 rows still carry the status the run gave them.

---

## 1. What happened

On 2026-09-15 H-FIRSTPARTY-01 v1.3 ran as HR-0083. v1.3 reads themes, identity, state and quotes
from the **article body** only; v1.2 had classified the whole page, including navigation, teaser
rails, footers and cookie banners. The run therefore stopped producing 97 machine-written rows, and
on Matthew's instruction (item 22) each was recorded **`invalidated_extraction_defect`** — the status
naming the reason rather than a neutral "not reproduced".

For 89 of the 97 that is the right reason. **For 8 it is not**, and the test that guards the fix says
so: their matched terms are *still present in the article body*, so page furniture was never the
problem. Something else dropped them. `core/tests/test_firstparty_body.py` section 9 pins exactly
this set so it cannot grow unnoticed.

## 2. What the 8 rows actually are

Checked against the archived pages the rows were written from (`core/tests/fixtures/firstparty_pages/`),
not inferred from the status. They fall into two groups, and **the two need opposite corrections**.

### Group A — 6 rows: the article is about a different company (status too mild)

| Rows | Company in the row | What the article is about | Company named on the page? |
|---|---|---|---|
| O00297, O00298, O00431 | National Product Sales | *"Lio Raises $30M Series A to Bring Agentic AI to Enterprise Procurement"* — a startup's funding round | **0 occurrences** of "National Product Sales" |
| O00354, O00355 | The PENTA Building Group | *"JDM Technology Group … Acquiring **Penta Technologies** and STRUXI"* — a construction-software vendor | **0** occurrences of "PENTA" |
| O00359 | ESS Companies | *"**ESS Tech, Inc.** Announces Second Quarter 2026 Financial Results"* — an energy-storage manufacturer | **0** occurrences of "ESS Companies" |

These are not extraction defects. They are **wrong-company rows**: v1.2's identity test matched a
name that appears nowhere on the page in the form claimed, and v1.3's body-scoped identity test
correctly refused them. Two of the three cases are near-miss names of the classic kind — *Penta
Technologies* is not *The PENTA Building Group*, *ESS Tech* is not *ESS Companies* — which is the
project's characteristic failure, recurring for the tenth time.

Recording them as an extraction defect **understates** the problem: it says the claim was read off
the wrong part of the right page, when in fact the page was about someone else.

### Group B — 2 rows: correct when written, then aged out (status too harsh)

| Rows | Company | Article | Why v1.3 dropped them |
|---|---|---|---|
| O00324, O00325 | McCarthy Holdings | *"…McCarthy Holdings Inc. Selects GEP SMART Software To Transform And Unify Procurement"*, published 2021-09-09 | The article crossed the project's five-year staleness line (1,832 days) **between the dry run and the run** |

The company is right, the page is genuinely about it, the terms are in the body. Nothing was ever
wrong with these rows. They simply fell outside the currency window while the fix was being applied.
Recording them as an extraction defect **overstates** the problem — it puts a defect label on
evidence that had none.

## 3. Why this matters beyond labelling

- **It is the reason to care about status vocabulary at all.** Determinations are permanent (item 21)
  and feed nothing automatically, but they are the project's record of *why* a claim is not counted.
  A wrong-company row and an out-of-date row are different findings; collapsing both into
  "extraction defect" makes the extraction fix look responsible for six identity failures it did not
  cause, and for two rows that were never defective.
- **It slightly flatters the v1.3 extraction fix.** 97 rows attributed to page furniture is the
  headline number for that change; the honest figure is 89.
- **The 6 Group A rows are evidence about identity**, not extraction, and identity is where this
  project's recurring failure lives. Counted correctly they belong with O00349 (recorded
  `invalidated_wrong_entity` on 2026-09-15), not with the cookie-banner rows.
- **No published number moves either way.** These rows are already excluded from every count as
  invalid; only the stated reason is at issue.

## 4. Why it was not corrected automatically

`core/validity.py::invalidate_unreproduced` takes the status and basis from its caller, so the run
recorded what it was told to record. The harness knows it stopped producing a row; it does **not**
know whether that was identity, staleness or extraction, because those are three different gates
inside it. Distinguishing them needed the archived pages to be read by hand — which is what produced
the table above.

---

## 5. Proposal (not applied)

Append a superseding determination for each row. The existing `superseded_by` forward pointer is
exactly the mechanism for this, and no status is reinstating, so this does not make any row valid
again — it corrects the recorded reason.

| Rows | From | To | Note |
|---|---|---|---|
| O00297, O00298, O00431, O00354, O00355, O00359 | `invalidated_extraction_defect` | **`invalidated_wrong_entity`** | Already in the vocabulary; already used for O00349 |
| O00324, O00325 | `invalidated_extraction_defect` | **`invalidated_not_reproduced`** | The closest true statement in the current vocabulary: the harness no longer produces them |

**The open question inside the proposal:** Group B is not really "not reproduced" either — it is
*aged out of the currency window*, which is a property of the evidence, not a defect in it. The
vocabulary is additive-only and has no status for it. Two options:

- **(a)** use `invalidated_not_reproduced`, accepting that the status is accurate but uninformative;
- **(b)** add `invalidated_stale` to `Lookups!AF` and use it, making the record say what happened.

Option (b) is the more honest record and costs one vocabulary entry plus its validation binding.
Option (a) writes nothing new. Either way the basis text should name the five-year window and the
date the article crossed it.

Both the group assignments and the choice between (a) and (b) are Matthew's.
