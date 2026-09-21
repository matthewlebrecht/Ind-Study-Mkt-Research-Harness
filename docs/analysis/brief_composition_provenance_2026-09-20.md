# Brief — composition provenance on derived rows

**This is a design question, not a fix, and it is written back rather than guessed at.** The
de-duplication half of the same open item was diagnosed on 2026-09-17 and needs nothing: it has not
fired and cannot as the code stands. What remains is provenance, and the cheapest correct version of
it is a schema change to an append-only, immutable table. That is a decision.

---

## 1. What the gap is

`core/composition.py::derive` indexes attempts as `(company_id, attempted_signal) → [(retrieved,
harness)]`. The **run id and harness version are dropped at index time**. A bucket is covered if any
attempt's retrospective reach spans it, and `covering_instruments` records the *signal names* only.

So a derived row can say *"this absence is licensed by `state_ag_breach_notice`"*. It cannot say
**which run, which harness version, or which source read** licensed it.

Observed buckets are better off: they carry `supporting_observation_ids`, so evidence has
provenance. **Licensing does not.**

## 2. Exposure today, measured

- **1,608** derived buckets carry `covering_instruments`; none names a run, version or source.
- **15** buckets are licensed absences (all `cybersecurity`, all IC4, 9 companies). The 2026-W37 and
  W38 buckets each rest on a *single* instrument from a single run, so their provenance is
  unambiguous in fact — just unrecorded.
- `Company_State_History` holds **6,480 rows** across DR-0001 and DR-0002, with zero duplicate
  `(derivation, company, theme, bucket)` keys.
- Re-deriving the whole history with the attempt list reversed changes **0 of 5,400** derived rows on
  every field. Order-independence is why the missing run id costs nothing *arithmetically* today.

## 3. Why it still matters — the case that actually happened

H-BREACHPORTAL-01 v1.1 scoped Goodfellow Bros' absence against the **California** portal on an HQ
value that turned out to be wrong; v1.2 re-scoped it against **Washington**. Both runs were
published, so both licensed the same absence, and the derived row could not say which.

It was resolved by a human **superseding** HR-0069 — verified 2026-09-17: Goodfellow's
`state_ag_breach_notice` attempts are HR-0069 (superseded, invisible to composition) and HR-0082
(published, visible), and only the correct one now licenses.

**The correction mechanism works, but it is manual.** Nothing in composition prefers the newer
attempt, and nothing records which attempt was relied on. A reader of a derived row cannot tell a
correct licence from a stale one; they have to know the run history.

## 4. Why it is not a small fix

The obvious change — add `licensing_run_id` and `licensing_harness_version` to
`STATE_HISTORY_COLUMNS` — runs into the table's central property: **derivations are immutable and
append-only**. `core/db.py::append_state_history` refuses to write a derivation id that is already
present, by design.

So the change is not "add two columns and backfill". It is:

1. a schema migration adding the columns (every existing row gets them empty);
2. a change to `derive` to carry the run id and version through the attempt index;
3. **a new derivation (DR-0003)** — the only way existing buckets acquire provenance, since DR-0001
   and DR-0002 can never be rewritten;
4. and then two derivations in the table have provenance columns and two do not, permanently.

Step 4 is the part that needs a decision rather than a patch: the table will carry a visible seam,
and every consumer has to treat "no provenance recorded" as "derived before DR-0003" rather than as
missing data.

## 5. Options

| # | Option | Cost | Consequence |
|---|---|---|---|
| A | **Leave as documented** — the property is recorded in CLAUDE.md and measured here | none | Derived rows stay unattributable. Acceptable while `cybersecurity` is the only theme with licensed absences and their provenance is unambiguous in fact |
| B | **Provenance columns + DR-0003** | schema migration, `derive` change, one new derivation, permanent seam | Future absences are attributable; the 15 existing licensed absences stay unattributed unless DR-0003 supersedes them in use |
| C | **Prefer the newest covering attempt** (ordering rule) | small code change | Changes nothing today (measured: 0 of 5,400 rows), so it buys correctness only against a *future* stale-run case — and the superseding mechanism already covers that case |
| D | **B + C together** | as B | The complete answer, and the only one that makes a derived row self-explaining |

## 6. Recommendation

**Option A for this submission; B or D in Week 5 if the derivation is going to carry weight in the
report.** The reasoning: nothing published today is wrong, the one case where a stale run could have
mattered was caught and corrected, and the fix's real cost is not the code but the permanent seam in
an immutable table — which is a worse thing to introduce hastily at the end of a project than to
schedule deliberately at the start of the next one.

If the report quotes *specific* licensed absences (the 9 `cybersecurity` companies), that is still
safe: their provenance is unambiguous in fact and is written up in this brief and in the
2026-09-17 diagnostic.

**Decision needed from Matthew:** A, B, C or D. Nothing has been changed.
