# Company Qualification Procedure (v1)

This turns the conceptual rubric in "Research design and rubrics" into a step-by-step
decision procedure that can be applied consistently, by a harness or a human, across the
full company universe. Maps directly to the `Companies` sheet fields
(`qualification_status`, `qualification_confidence_0_1`, `qualification_rationale`,
`soft_gate_exception_reason`).

Apply gates **in order**. Stop and exclude as soon as a hard gate fails — don't bother
scoring complexity/scale for a company that fails Gate 0.

---

## Gate 0 — Identity & Verification (hard, no exceptions)

**Question:** Can we verify this is a real, currently operating company, headquartered in
the U.S.?

**Evidence:** business registration record, active company website, recent news mention,
active LinkedIn/company page.

- Pass → continue to Gate 1
- Fail (can't verify existence, or clearly not U.S.-headquartered) → **EXCLUDE**

This is the one place where "sparse public evidence" *can* be disqualifying — per the
rubric, exclude only when identity/basic eligibility itself can't be verified, not because
evidence is thin on other dimensions.

---

## Gate 1 — Subject Relevance (hard, but deliberately low bar)

**Question:** Does the company's operating model create *plausible* exposure to
technology/systems/data/process-change/integration needs?

Per the rubric: **prior public modernization activity is not required for admission.**
This gate exists to catch companies with genuinely no plausible connection to the subject
(e.g., a business with no physical operations, no systems complexity, no process at all
that technology could touch) — it is not meant to filter out companies that just haven't
said anything about modernization yet.

- Pass (the overwhelming majority of operationally complex companies pass by default) →
  continue to Gate 2
- Fail (no plausible connection at all) → **EXCLUDE**

---

## Gate 2 — Industry Fit (semi-hard, broadly construed)

**Question:** Is the company's primary business manufacturing, supply-chain operations,
or logistics?

**Evidence:** NAICS code if available, plain-language business description, primary
revenue activity.

- Clear fit in one of the three → continue to Score A
- **Adjacent case** (e.g., a retailer with a large owned-logistics/fulfillment operation,
  a distributor that also does light manufacturing) → continue to Score A, but flag
  `industry_secondary` and note the adjacency in `qualification_rationale`
- No plausible fit to any of the three → **EXCLUDE**, unless a written exception case is
  made (rare — should be uncommon enough that it always gets a specific rationale, not a
  default path)

---

## Score A — Operating Complexity (0–5)

Award 1 point for each present (evidence-backed, not assumed):

| Signal | Point if present |
|---|---|
| Multiple physical sites/facilities | 1 |
| Owned/operated fleet or logistics network | 1 |
| Manufacturing/production operations (not just light assembly) | 1 |
| Multi-tier supply chain (multiple supplier/distributor tiers) | 1 |
| Warehousing/distribution center operations | 1 |

**Score A total: 0–5.** This score doesn't gate anything by itself — it feeds the scale
soft-gate decision below, and it's worth recording on the Companies sheet regardless of
outcome, since it's useful signal for later depth-allocation decisions (Week 3).

---

## Score B — Scale Fit (soft gate)

**Target band:** 500–5,000 employees **or** $200M–$2B revenue.

1. Check employee count against the band.
2. Check revenue against the band.
3. **Both within band** → PASS, no exception needed.
4. **Only one metric available, and it's within band** → PASS, but set
   `qualification_confidence` lower (partial data) and note which metric was missing.
5. **Outside band on one or both dimensions** → apply exception logic:

   | Factor | Weighs toward exception (still qualify) | Weighs toward exclusion |
   |---|---|---|
   | Magnitude of deviation | Minor (e.g. 400 employees vs. 500 floor) | Major (e.g. 50 employees, or $5B revenue) |
   | Score A (operating complexity) | 4 or 5 | 0–2 |
   | Subject relevance strength | Strong, well-evidenced | Weak or assumed |
   | Public evidence richness | Rich enough to be "unusually informative" per the rubric's own exception language | Sparse — can't tell if the exception is justified |

   If the exception is granted: set `qualification_status = soft_gate_exception`, and
   **write the specific reason** in `soft_gate_exception_reason` — never leave this blank
   for an exception case. If the exception is not granted → **EXCLUDE**.

---

## Baseline Coverage (informational, not a gate)

Record whether public evidence across the source families is rich, sparse, or absent for
this company. Per the rubric, **sparse evidence is a coverage condition, not grounds for
exclusion** (Gate 0 already handled the one case where thin evidence is disqualifying —
inability to verify identity). A qualified company with sparse coverage stays in the
universe; note the sparsity so it doesn't get mistaken for a harness failure later during
evaluation.

---

## Final Decision & Recording

| Outcome | `qualification_status` | Notes |
|---|---|---|
| Passed all gates cleanly | `qualified` | |
| Passed all gates, needed a scale exception | `soft_gate_exception` | Must include `soft_gate_exception_reason` |
| Failed Gate 0, 1, or 2 (no exception made) | `excluded` | State which gate failed in rationale |
| Ambiguous / needs a second look | `pending_review` | Use sparingly — this shouldn't become a dumping ground |

**`qualification_confidence` (0–1):** reflects how much of this decision rests on solid
evidence vs. inference. A company with verified employee count + clear industry fit +
strong complexity evidence should score ~0.8–1.0. A company qualified mostly on inference
(e.g., "probably has multiple sites based on job postings across 3 cities") should score
lower, e.g. 0.4–0.6 — not because the decision is wrong, but because it should be easy to
find and re-check low-confidence qualifications later.

**`qualification_rationale`:** always fill in, even for clean passes — a one-line summary
of which gates passed and why. This is what makes the decision auditable later rather than
a black box.

---

## Data Confidence Conventions

Two recurring situations need a consistent rule so confidence scoring doesn't drift
company-to-company or reviewer-to-reviewer.

### Stale or range-based size figures

Many employee/revenue figures for private companies will be a range (e.g. "500–1,000
employees" from a data broker) or several years old rather than an exact, current number.

**Rule: apply a small confidence discount, not a heavy one, when the range or stale figure
still clearly falls within the target band.** A company reported as "1,001–5,000
employees" in 2024 is good enough evidence to qualify with only a modest confidence
reduction (e.g. 0.85 → 0.75) — the uncertainty is about the exact number, not about
whether the company is in-band. Reserve heavy discounts for cases where the range itself
straddles a gate boundary (e.g. "300–600 employees" against a 500 floor) or the figure is
old enough that real drift is plausible (a 2017 figure for a growing company). Don't
conflate "imprecise" with "unreliable" — a wide but centered range is still strong
evidence.

### AI/technology hiring signals — don't misread as "already modernized"

A company posting job listings for AI engineers, data engineers, or similar
technical/modernization roles is **not** evidence that the company already has
in-house engineering/AI infrastructure — read at face value it can look like
disqualifying evidence (since the target profile assumes limited internal
capability), but it's usually the opposite: **early hiring for these roles is a leading
indicator that the company is just starting to build capability, not that it already has
it.**

**Rule: treat active AI/technical hiring as `organizational_state = active_transition`
evidence, not as a disqualifying signal.** This is exactly the kind of company the harness
should be surfacing, not excluding — it's evidence of a live modernization need, which is
squarely inside the project's subject-relevance criterion. Only treat a company as having
mature in-house capability when there's evidence of an *established* function (multi-year
job history in the role, a named engineering/data leadership title that isn't newly
created, an existing internal platform or tech blog) — not from a handful of recent
postings alone.

> **RESOLVED 2026-09-06 (session 14 item 9; docs/conventions.md 18, amended):** both
> together is a POSITIVE signal -- a company that could use process optimization -- and
> qualifies. Mixed-signal cases are no longer held at `pending_review` on this ground. The
> original question is kept below as written.
>
> **Open question, to be formalized in Week 3:** what about a company that shows *both* —
> active AI/tech hiring *and* an established internal platform? Current leaning is that
> these should still generally qualify: the opportunity isn't limited to companies with
> zero existing infrastructure, only to companies whose current infrastructure is
> inadequate or outdated relative to what's achievable. An established-but-limited or
> beatable platform is still a target, not an automatic exclusion. This isn't yet a
> formal rule — treat mixed-signal cases as `pending_review` until the pilot/baseline pass
> surfaces real examples to calibrate against.

---

## What this deliberately does *not* do

This procedure does not try to be more precise than the underlying evidence allows. Per
the rubric: *"Qualification is a reasoned judgment. Record the evidence and confidence; do
not reject a clear fit because one exact size field is unavailable."* The confidence field
exists precisely so uncertainty is visible rather than hidden behind a binary
qualified/excluded call.
