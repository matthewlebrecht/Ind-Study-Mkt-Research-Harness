# Session 2 Priority Order — 2026-08-31

Unattended, ~8-12 hours. Same pacing rule as last time: ~45-60 min soft cap to a working
v1 per task, log-and-move-on if stuck, circle back if time remains.

## Before anything else -- do this first, no exceptions

1. **`git add -A && git commit`** the entire uncommitted restructure from last session.
   This is the single highest-risk item carried over -- a large uncommitted restructure
   sitting on disk overnight twice in a row is not acceptable. If the permission
   classifier blocks it again, **stop and log why**, then commit in smaller pieces if
   that's what it takes. Do not proceed to new harness work with last session's changes
   still uncommitted.
2. **Commit incrementally this session too** -- after each harness, not just at the end.
   If commits get blocked again partway through, we want to lose less than a full night's
   work next time, not just repeat the same risk.
3. Replace `CLAUDE.md` on disk with the corrected version provided alongside this file.
   Do not merge/guess -- overwrite it. It reflects everything through the 8/30 session.
4. Confirmed, no further verification needed: the workbook reconstruction from last
   session is the system of record. No newer copy exists anywhere else.
5. Both of last session's decisions are ratified: providers-in-Companies with
   `provider_benchmark` status, and seller messaging mapped uniformly to
   `organizational_state = target_state`.

## Priority 1 -- close the buyer_articulates gap (this is the actual point of tonight)

A search API key (Brave Search API) should be configured as `BRAVE_API_KEY`. If it isn't
present in the environment, **stop and report this clearly** rather than silently
skipping this section again -- it blocked the entire "what buyers say" side of the
project last time and cannot silently happen twice.

1. **`H-EXECID-01`** -- exec identification, prerequisite. Sourcing priority: company
   leadership pages -> ZoomInfo -> LinkedIn People tab -> press/business-journal -> search
   fallback. Title filter: CEO/COO/CIO-CTO/VP Ops/Supply Chain/Manufacturing. Writes to
   `Company_Executives`. Hard dependency for the next item -- build this first.
2. **`H-EXECVOICE-01`** -- executive candor (podcasts, LinkedIn posts, interviews).
   Search-indexed discovery over scraping; cheap speaker-list check before video/transcript
   work. Classification trap to avoid: vendor-published content featuring a buyer exec
   belongs to family 6 (vendor/partner disclosure), not this harness.
3. **`H-FIRSTPARTY-01`** -- press releases, PR wires, local business journals. No
   prerequisite, can run independently of #1/#2 if time is short.

Getting even one of these three producing real `buyer_articulates` observations tonight
matters more than finishing the rest of the list below.

## Priority 2 -- continue the general harness list (skipped last session, still valid)

In order: `H-PROCUREMENT-01` (USASpending+SAM.gov), `H-PATENTS-01` (PatentsView),
`H-EMPREVIEW-01` (Glassdoor/Indeed), `H-LEGAL-01` (CourtListener+NLRB), `H-PERMITS-01`
(permits+assessor), `H-LOCALRECORDS-01` (Granicus/Legistar), `H-TRADEPRESS-01`,
`H-VENDOR-01`, `H-TECHSTACK-01`, `H-PRODUCTQUALITY-01`.

Already built, don't rebuild: `H-FMCSA-01`, `H-JOBPOST-01`, `H-SELLERCONTENT-01`,
`H-SAFETY-ENV-01`, `H-WAYBACK-01`.

## Priority 3 -- cheap wins, if time allows

- Fill `website` for the 8 pilot companies (`C0001`-`C0008`) -- closes a named
  `H-WAYBACK-01` coverage gap for almost no effort.
- Investigate OSHA pagination (`p_start`/`p_finish` params present but not advancing) --
  13 companies currently have floor-only counts.

## Do NOT do this session (same deferrals as before, still valid)

- `Discards` sheet -- no classification harness exists yet
- Backfill of `H-FMCSA-01`/`H-JOBPOST-01` attempts -- needs a person awake to judge
- `DECISIONS.md` seeding -- separate dedicated session, not tonight (CLAUDE.md itself
  IS being fixed tonight per step 3 above -- that part is not deferred, only the
  DECISIONS.md history-seeding is)
- Self-review of the 201 unreviewed observations -- Week 4's job, not the harness's own

## Recurring watch-item

Loose pattern matching has produced false confidence 3 times now (Infor bug, Wayback
false-positive, SellerContent inflated coverage). If a new harness reports suspiciously
clean/complete coverage, treat that as a signal to double-check before trusting it, not
a signal the harness is working well.
