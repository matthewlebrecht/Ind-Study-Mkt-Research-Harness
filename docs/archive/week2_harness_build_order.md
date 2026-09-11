# Week 2 Build Session — Harness Priority Order

Work top-down. Build, test against real API/source, write to Observations, log a
Harness_Runs row, move to next. **Session budget: ~8 hours, unsupervised — pace
yourself using the rule below, not a fixed harness count.**

## Pacing rule (read this before starting)

Don't burn hours perfecting one hard harness while the rest of the list sits untouched.
**Soft cap: ~45-60 minutes per harness to reach a working v1.** If you hit that cap
without a working version:
1. Log what's blocking it as an Attempts-style note (this is exactly the "report the gap,
   don't silently drop it" convention already in use — apply it to your own build process,
   not just harness output).
2. Move to the next harness on the list. Don't idle on one problem.
3. If you finish the full list with time remaining, circle back to whatever got skipped
   or stalled, with fresh attempts.

This matters more than usual tonight — nobody's available to unstick you if you get
wedged on something like the FMCSA entity-resolution problem did in Week 1. Treat a stall
as information (something to log and route around), not a blocker to push through alone.

**Context: Week 2 is due in 2 days total** — this is one overnight session within that
window, not the only chance to finish. Prioritize a broad, working baseline over a
narrower, more polished one.

**Note on this list:** reconstructed from Signal/Harness Advisor session summaries, not
copied directly from `signal_taxonomy.md` / `attempts_schema_spec.md`. If those files are
in the project folder, check them first — they're authoritative on exact harness IDs and
signal-type detail. Treat the order below as a strong prior, not gospel.

## Before touching any harness

**Use `build_handoff_2026-08-27.md` + `extend_validation.py` (from Harness Advisor) for
this section — they're more precise than what's below and supersede it.** Summary: a
hard-abort workbook-confirmation check first (don't build against the wrong file), then 8
schema steps (Attempts sheet, Lookups vocab columns, Signal_Types stub, Harness_Sources,
Company_Executives, Harness_Runs rollups), then run `extend_validation.py --apply`.

**Do NOT do these tonight** (explicitly deferred, confirmed):
- Fold or split CLAUDE.md / PIVOT_UPDATE.md. Decision made (split: CLAUDE.md pure
  current-state + new append-only DECISIONS.md) but execution is a separate session, not
  part of tonight's build.
- Discards sheet — no classification harness exists yet to size the sampling design
  against.
- Backfill of H-FMCSA-01 / H-JOBPOST-01 attempts — needs a person awake to judge what
  counts as an attempt in runs that predate the concept.

Once the schema steps above are done and verified, move into the harness build order
below.

**Unclear/unconfirmed — flag rather than assume:** Rev 5 also specified `manifest.yaml` +
`validate_repo_db.py` + the `db.py` run-context refactor (attempt emission moving inside
a declared scope). Harness Advisor's message says repo structure is "already written and
approved" and "doesn't block tonight" — but it's not clear whether that means it's already
built, or scheduled separately. Don't assume either way; if Claude Code has visibility
into `repo_structure_spec.md`, check there before skipping or duplicating this work.

## Build order (balanced across evidence roles — not all buyer_acts, not all buyer_says)

1. **H-SELLERDISCOURSE-01** — provider_market_responds. Consulting/SI firm websites,
   case studies, service pages. **Build this first regardless of everything else below —
   it's Week 2's explicit named deliverable** (the seller benchmark), not just another
   harness on the list.
2. **H-SAFETY-01** (OSHA + EPA ECHO merge) — buyer_acts. Clean APIs, ownership-agnostic,
   core to the Anvil industry mix (construction, manufacturing, energy).
3. **H-EXECID-01** — prerequisite, no evidence family. Build before #4 — it's a hard
   dependency (exec-identification feeds executive-candor extraction and others).
4. **H-EXECVOICE-01** — buyer_articulates. Fully designed already (sourcing priority:
   leadership pages → ZoomInfo → LinkedIn People tab → press → search fallback; title
   filter CEO/COO/CIO-CTO/VP Ops/Supply Chain/Manufacturing). Depends on #3.
5. **H-FIRSTPARTY-01** — buyer_articulates. Press releases / PR wires / local business
   journals. Signal Advisor's own suggested next pick — good proving ground for the
   upstream signal classifier if that gets built this session too.
6. **H-PROCUREMENT-01** (USASpending + SAM.gov merge) — buyer_acts. Clean API.
7. **H-PATENTS-01** (PatentsView) — buyer_acts. Clean API, cheap, fast to build.
8. **H-EMPREVIEW-01** (Glassdoor / Indeed reviews) — buyer_articulates-adjacent (employee
   voice as organizational signal). No API, web only.
9. **H-WAYBACK-01** (Wayback Machine) — cross-cutting / buyer_acts. Clean API, cheap to
   run broadly — catches removed case studies, changed job postings, abandoned pages.
10. **H-LEGAL-01** (CourtListener + NLRB merge) — buyer_acts. API/web.
11. **H-PERMITS-01** (permits + county assessor records merge) — buyer_acts. Web,
    structured but jurisdiction-varies.
12. **H-LOCALRECORDS-01** (Granicus/Legistar city & county minutes) — buyer_acts. Web.
13. **H-TRADEPRESS-01** (industry trade publications) — buyer_acts/articulates mix. Web.
14. **H-VENDOR-01** (vendor/partner case studies) — buyer_acts / provider_market_responds
    crossover. Web, likely sparse (only fires if company is a named reference customer).
15. **H-TECHSTACK-01** (BuiltWith/Wappalyzer + job-posting stack mentions) — buyer_acts.
    Partial API (paid tier), otherwise web.
16. **H-PRODUCTQUALITY-01** (CPSC recalls + BBB/Trustpilot) — buyer_acts. Partial API
    (CPSC), rest web.

Family 17 (digital-product telemetry) is shelved — don't build a harness for it, doesn't
match the Anvil-100 industry mix.

## Conventions to keep enforcing (don't relitigate, already locked in)

- Idempotent writes, never overwrite human review
- Distinguish source drift from genuine harness error (review against the date a claim
  cites, not today's live page)
- Every suppressed/truncated result gets reported, not silently dropped
- Entity resolution: score on name-token alignment, refuse to guess below confidence
  threshold, log every rejection
- New Attempts sheet: one row per (run × company × signal), log attempts not just
  failures, confirmed absence = coverage not failure
- Discard/rejected-candidate records: aggregate counts go on the Attempts row itself
  (answers ratio questions like "467 candidates, 5 real"); don't try to store every
  individual discard — sample ~200/run stratified by company+reason instead, report the
  cap. Only matters once a classification harness exists — not blocking for this session's
  harnesses, just don't build individual-discard-row storage if you get there.
- harness_id = one per logical harness (not per API); H-FMCSA-01 stays as-is, don't rename
