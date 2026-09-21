# Two latent risks, measured: grandfathered versions, and composition's de-duplication

Diagnosis first for both. One turned out small enough to fix and is fixed; the other has not fired
and is left alone with the measurement recorded. Everything here is recomputable.

---

# Part 1 — Grandfathered versions whose row populations changed

## 1.1 What the exemption actually claims

`docs/gates/grandfathered_harness_versions.json` exempts 18 exact `(harness_id, harness_version)`
pairs from the audit gate. Every entry rests on a **hand audit performed on 2026-08-31** and its
`reason` quotes that audit's population — "27 observations human-reviewed", "248 rows cut to 79",
"10 rows committed, 2 wrong about who spoke".

That is a statement about the rows that existed on that date. The question is whether it still
describes the rows living under those version labels.

## 1.2 It does not. Measured against the workbook as committed that day

Comparing the workbook at commit `f109174` (2026-08-31, 318 observations) with today (722):

| Grandfathered pair | then | now | kept | left | added |
|---|---|---|---|---|---|
| H-SAFETY-ENV-01 v1.0 | 118 | 67 | 67 | 51 | 0 |
| H-FIRSTPARTY-01 v1.1 | 79 | 42 | 42 | 37 | 0 |
| H-SELLERCONTENT-01 v1.2 | 43 | 24 | 24 | 19 | 0 |
| **H-FMCSA-01 v1.3** | 20 | 4 | **0** | 20 | **4** |
| H-SAFETY-ENV-01 v1.1 | 13 | 0 | 0 | 13 | 0 |
| H-EXECVOICE-01 v1.1 | 8 | 0 | 0 | 8 | 0 |
| H-JOBPOST-01 v1.0 | 8 | 0 | 0 | 8 | 0 |
| H-FMCSA-01 v1.0 / H-WAYBACK-01 v1.0 / v1.1 | 7 / 8 / 11 | same | all | 0 | 0 |
| the other 8 pairs | 0 | 0 | — | — | — |

**Seven of the 18 lost rows; one gained rows; ten hold none at all.** H-FMCSA-01 v1.3 is the extreme
case: not one of the 20 rows its exemption describes is still there, and the 4 rows now under that
label were written a day *after* the exemption.

## 1.3 Where the departed rows went — nothing was lost

Every departed row was traced:

- **moved to a newer version**, because these harnesses rewrite rows under the version that last
  wrote them: SAFETY-ENV 51+13 → v1.3, FIRSTPARTY 37 → v1.2/v1.3, FMCSA 20 → v1.5, JOBPOST 8 →
  v1.1/v1.3/v1.4, SELLERCONTENT 9 → v1.3/v1.4;
- **or are pre-rule renumberings** whose claim is live under a newer id and recorded as such in
  `Observation_Ids.current_id` (EXECVOICE 8, SELLERCONTENT 10) — the known 23 from convention 43.

So `harness_version` on a row means *"the version that last wrote it"*, not *"the version that was
audited"*. The evidence base is intact; the exemption's description of it is not.

## 1.4 The actual risk, taken one claim at a time

**(a) Stale coverage numbers — NO.** `published_coverage.py` quotes only each harness's *latest*
published version; 45 older published versions are named and deliberately not quoted. Exactly one
grandfathered version is quoted today — **H-EXECID-01 v1.0** — and its population never changed
(it writes `Company_Executives`, not observations; its 58.3% is an attempts figure from HR-0013 and
still matches the 63 companies with confirmed executives). No coverage number rests on a changed
grandfathered population.

**(b) An audit sample that no longer represents its population — YES, but not where it publishes
anything.** H-FIRSTPARTY-01 v1.1 keeps 42 rows, and **27 of them are now recorded invalid** (the
HR-0083 determinations). The exemption's basis — "cut to 79 by hand audit" — describes a population
that is now 42 rows, 64% of them invalid. Nothing is published from it, but it is counted in the
evidence base and in the per-harness totals.

**(c) A structural hole — YES, and this is the one worth closing.** The exemption is keyed to
`(harness, version)`, and **a version is not a closed set**. A later run can write new rows under an
exempt version label, and those rows inherit an exemption nobody granted them. H-FMCSA-01 v1.3 did
exactly this: HR-0034 and HR-0037 (2026-09-01) wrote 4 rows into an exempt version. They were caught
by hand at the time and audited (`H-FMCSA-01__v1.3.json`), so nothing unaudited is live — but check 9
would not have required it.

## 1.5 Fixed (small)

check 9 now honours an exemption **only for versions whose published runs all predate its
`date_added`**. A grandfathered version with a later run is audited like any other, and the failure
names the run and the exemption date it postdates.

- `core/audit.py::grandfathered_added_on()` reads the per-pair dates.
- Today: **fails nothing** — the single affected version already has its artifact. Check 9 now reads
  "35 audited, 16 grandfathered … 1 grandfathered version audited anyway (rows written after the
  exemption): H-FMCSA-01 v1.3".
- Tamper-probed both ways: removing that artifact produces the failure, restoring it clears it.
- `core/tests/test_audit_gate.py` (60 checks) covers both directions on H-WAYBACK-01 v1.0, which is
  grandfathered with no artifact.

## 1.6 Left for a decision

- **The registry's `reason` texts are now inaccurate** for the seven pairs whose populations moved.
  They are historical statements and arguably should stay as written; if they are to say what is
  true today, that is an edit to 7 entries, not a code change.
- **H-FIRSTPARTY-01 v1.1's 27 invalid rows of 42** — worth knowing when its numbers are quoted.
- **Ten exemptions now cover zero rows** and could be retired, though retiring them changes nothing
  mechanically.

---

# Part 2 — Composition: de-duplication and provenance

## 2.1 The mechanism

`core/composition.py::derive` indexes attempts as `(company_id, attempted_signal) → [(retrieved,
harness)]`. **The run id and harness version are dropped at index time.** A bucket is covered if any
attempt's retrospective reach spans it, and the loop breaks on the first that does. `covering_instruments`
stores signal names only — no run, version or source.

## 2.2 Has it fired? No — measured, not assumed

- **321** `(company, signal)` keys carry scoped coverage attempts from published runs; **251 have more
  than one**, and 73 keys are covered by six different published runs.
- **21 keys have attempts that disagree on outcome** across runs (e.g. C0008's
  `executive_public_statement`: `covered` at v1.0, `absent_confirmed` at every version since).

That looks alarming and is not, for two reasons:

1. `covered` and `absent_confirmed` are **both** coverage outcomes, so a disagreement between them
   does not change whether a bucket is licensed.
2. Reach is a property of the **harness**, not of the run, so every attempt for a key contributes the
   same reach kind. Order decides only which attempt is *credited*, not what is derived.

**The decisive test:** re-deriving the full history with the attempt list reversed (newest-first
instead of oldest-first) changes **0 of 5,400 derived rows**, on every field. There is no
de-duplication defect to fix — the derivation is order-independent today.

**Duplicates:** `Company_State_History` holds 6,480 rows across DR-0001 and DR-0002 with **zero**
duplicate `(derivation, company, theme, bucket)` keys. Duplication within a derivation is structurally
impossible; two derivations of the same key is the append-only history working as designed.

## 2.3 What is real

**Provenance, not duplication.** 1,608 derived buckets carry `covering_instruments`, and not one says
which run, version or source licensed it. Observed buckets do carry `supporting_observation_ids` (142
of them), so evidence has provenance; **licensing does not**.

The consequence is the Goodfellow case. H-BREACHPORTAL-01 v1.1 scoped Goodfellow's absence against
the **California** portal on a wrong HQ value; v1.2 re-scoped it against **Washington**. Both runs
were published, so both licensed the same absence, and the derived row could not say which. It was
resolved by a human **superseding** HR-0069 — verified today: Goodfellow's `state_ag_breach_notice`
attempts are HR-0069 (superseded, invisible to composition) and HR-0082 (published, visible), and
only the correct one now licenses. Superseded runs are excluded (3 of 83).

So the correction mechanism works, but it is **manual**: it depends on someone noticing a run is
wrong and superseding it. Nothing in composition prefers the newer attempt, and nothing records which
attempt was relied on.

## 2.4 Exposure today

The 15 licensed-absence buckets are all `cybersecurity`, all IC4, across 8 companies. The 2026-W37 and
W38 buckets each rest on a **single** instrument from a single run (`sec_8k_item_105_cybersecurity`
or `state_ag_breach_notice`), so their provenance is unambiguous in fact — just unrecorded.

## 2.5 Recommendation: leave it to Week 5

It has not fired, it cannot change a derived value as the code stands, and the one case where a stale
run could have mattered was caught and corrected. The fix worth doing later is **provenance, not
de-duplication**: add the licensing run id and version to the derived row, so a bucket can say what
licensed it. That is a schema change to `Company_State_History` (`STATE_HISTORY_COLUMNS`) plus a new
derivation — not a small change, and it rewrites nothing already appended, since derivations are
immutable.
