# Code Session Brief — Pattern Fix, Diagnostic, H-JOBPOST-01 Signal Keys

**Date:** 2026-09-02
**Sequencing: this entire brief comes after the company-count investigation** from the
prior session brief (why does state-at-handoff report 120 companies against a fixed 108?).
The gap-report diagnostic below is only meaningful if the company universe it runs against is
known to be correct — don't run it on an uninvestigated anomaly.

## 1. Capture current `gap_report.py` output — before anything else in this brief

Run and save the current output **before making any pattern changes**. This is the "before"
half of the diagnostic in §2 and can't be reconstructed afterward.

## 2. Fix the `systems_integration` and `cloud_infrastructure_migration` patterns

**Why this is urgent, not routine:** the buyer-side version of this exact defect (`\bLean\b`
matching too loosely) was already found and fixed in H-JOBPOST-01 last session. The
provider-side version is still live in `core/topics.py`, and it biases in the worse direction —
buyer-side over-matching makes divergences disappear (buyer looks present when they aren't);
provider-side over-matching makes divergences appear (seller looks loud when they aren't). The
project's headline findings are divergences, so this defect currently biases toward confirming
the project's own thesis. Fix before the next gap report is treated as final.

**Two-tier pattern structure**, same shape as the `ST-REMOVEDPAGE` corroboration gate (§22.5)
and for the same reason — noise correlated with signal:

- **Specific tier** — fires alone. For `systems_integration`: `\bEDI\b`, `\biPaaS\b`,
  `middleware`, `\bETL\b`.
- **Generic tier** — requires corroboration (a second hit, specific or generic, in the same
  artifact) before it counts. For `systems_integration`: `\bAPI\b`, `\bintegration\b`. Also
  move `\bLean\b`, `\bAMR\b`, `\bAI\b`, and bare vendor names into the generic tier wherever
  they currently fire alone in either theme's pattern set.
- **Named exclusion:** `"post-merger integration"` — routine phrase in mid-size industrial
  press releases, unrelated to systems interoperability. Exclude explicitly rather than relying
  on the corroboration gate to suppress it.

**`cloud_infrastructure_migration` gets the same pass.** Signal identified `\bmainframe\b`,
`legacy (system|application) modernization`, and `application modernization` as generic
legacy-estate terms, not cloud-specific ones — move to generic tier, require corroboration with
a cloud-specific term.

## 3. Re-run the diagnostic

Re-run `gap_report.py` after the pattern change and diff against the §1 capture. **Any
divergence that flips on a pattern narrowing was never a finding** — flag those explicitly in
the session report rather than letting them quietly disappear from the numbers. This is the
actual point of the exercise: converting an unfalsified worry into a measured one.

## 4. Add H-JOBPOST-01 signal keys — four themes, four conditions

Authorized by Signal Advisor, four conditions, all required:

1. **Presence-only until the JS-rendering denominator is measured.** No absence claim from any
   of these four keys until the fraction of the 108 (or however many the company-count
   investigation resolves to) whose careers pages are actually readable is known. This
   denominator now gates four themes, not one — worth prioritizing the measurement itself if it
   isn't already in progress.
2. **Keys must land in `BUYER_SIGNAL_TO_THEME`.** The mapping currently covers 6 of the
   (now 10) themes — that mapping gap is the actual defect. New signal keys that don't roll up
   through it change nothing downstream.
3. **Specific-tier patterns from the start** — don't reproduce §2's failure in new code. In
   particular: a bare `\bAWS\b` / `\bAzure\b` / `\bGCP\b` mention in a job requisition is **not**
   a cloud-migration signal on its own — nearly every IT req names a cloud provider now. Require
   migration or legacy-estate language alongside it.
4. **Buyer-side patterns stay per-harness**, not in `core/topics.py`. Additive only — doesn't
   touch the provider-side pattern set from §2.

The fourth key is `ot_modernization` (THEME-10) — controls engineers, SCADA technicians, PLC
programmers, integration techs are highly specific, high-signal requisition terms, essentially
unconfusable with anything else. This theme launches with an IC3 instrument from day one rather
than starting IC1-only.

## What I need back

Confirmation the gap-report diff ran clean (or a list of which divergences moved and by how
much), the four signal keys built and mapped, and the JS-rendering denominator measurement —
even a rough first pass — since it now gates four absence legs instead of one.
