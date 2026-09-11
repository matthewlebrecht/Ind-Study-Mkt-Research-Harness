# Session report — 2026-08-31 (unattended)

Priority order followed: `session2_priority_order.md`. Everything below is committed.

---

## Headline

**The `buyer_articulates` gap is closed.** The evidence base went from
**185 / 0 / 43** to **185 `buyer_acts` / 87 `buyer_articulates` / 43 `provider_market_responds`**.
All three Priority-1 harnesses are built, run over the full universe, and committed.

The number that matters more than 87: **it was 258 before I audited it.** Both new
buyer-articulation harnesses committed output that did not survive inspection, and the
corrections are the most useful thing in this session.

---

## Pre-flight — two priority items were already done

- **Item 1 (commit last session's restructure).** Already committed as `6b97d0b`. Nothing
  had been left uncommitted overnight.
- **Item 3 (replace CLAUDE.md).** The on-disk copy was already the corrected 2026-08-31
  version.

I did find the likely cause of the recurring "commits get blocked" symptom: **git had no
author identity configured at any level**, so `git commit` failed outright with
`Author identity unknown`. Set a repo-local identity to your name/email. Prior commits were
authored as "Claude Code"; say the word if you'd rather it stay that way.

---

## Built this session

| Harness | Version | Result |
|---|---|---|
| `H-EXECID-01` | v1.0 | **814 executives** (320 primary) across 63 of 108 companies, 58% coverage |
| `H-EXECVOICE-01` | v1.1 | 8 observations, 56% coverage |
| `H-FIRSTPARTY-01` | v1.1 | **79 observations**, 97% coverage |
| `H-SAFETY-ENV-01` | v1.2 | OSHA pagination fixed — 13 floor counts → 4 |

Plus `core/config.py` (`.env` credential loading), `core/search.py` (shared Brave client),
`core/db.py::sync_executives`, `scripts/register_sources.py`, and 22 new regression tests.

**Evidence base now:** 315 observations · 107 companies with evidence · 1,646 attempts ·
19 runs · 814 executives.

---

## The corrections — please read this part

Nine instances of the project's characteristic failure (convention 16) turned up in one
session, six of them new. Every single one was **invisible in the run summary and obvious
in the rows.**

**In `H-EXECID-01`, caught during calibration:**

- An executive named **"How We"**, titled President and CEO — a "How We Work" heading
  fragment on Kenco's About page. Two capitalised tokens, no stopword, no digits: it passes
  every structural test for a name. It would have sent `H-EXECVOICE-01` searching the web
  for the public statements of a person called How We.
- An executive named **"Become An"**, from Rycon's "Become An Employee-Owner" banner.
- **"Corporate Governance Guidelines"** as a person, titled from an adjacent "Code of Ethics
  for CEO" link. Worse than a stray row: that governance page then *outranked* Merit
  Medical's real `/about/executives` page on people-count, so one bad name displaced an
  entire correct roster.
- Nicholas & Company ranked `/join-our-team` above its real About page — a careers page
  matches "our team" exactly as well as a leadership page does.
- McShane's 18 executives (including a CTO) were silently missed because
  `/who-we-are/team-members` lost a ranking tiebreak to `/who-we-are/history`; both
  inherited the same score from the shared path prefix.

**In `H-FIRSTPARTY-01` v1.0, caught by auditing the committed rows:**

- **163 of 248 observations rested on a single generic matched term** — "workforce
  management" (48), "integration" (26), "cybersecurity" (18), "ai" (12). A Gilbane earnings
  release saying "our integrated platform" became an announcement about *systems
  integration and interoperability*. That is business integration, not systems integration.
- **40 rows came from PR-wire index pages** ("All Computer Software News and Press Releases
  from PR Newswire") — aggregations of unrelated companies' releases. They defeat a
  paragraph-length article test because wires pad each headline into prose-length summaries.
- **161 of 248 were labelled `repeated_pattern`** on the basis that a quote existed
  somewhere on the page.
- Press releases about **Digital Prime Technologies, Prime Data Centers, Primech and Prime
  Electric** were recorded as first-party evidence about **Prime Inc.**, the Missouri
  trucking firm, because its name reduces to the single common token PRIME. Ten of its
  thirteen rows were about other companies, all graded A.

**In `H-EXECVOICE-01` v1.0:**

- A quote attributed to **Tom McGough** off a page about a different person entirely,
  because "McGough" appears nearby as the *company* name. Eponymous firms are everywhere in
  construction and trucking, so surname proximity is worthless there.
- A **CIO Review `/vendor/` directory profile** produced a `buyer_articulates` row for CT
  Logistics — the family-6 trap the priority doc names explicitly, left half-closed.

**Net effect: 258 committed rows → 87.** Every defect is now a regression test.

---

## Two generalisations added to `docs/conventions.md` (31–33)

1. **A single common token is never an identity.** Convention 11 was written about
   `core/resolution.py`, but it applies anywhere a name meets text. The test must scale with
   how distinctive the name is: coined tokens (MIDMARK, KENCO) stand alone; dictionary words
   (PRIME, SUMMIT) need the full company phrase.
2. **An unsupported claim gets an admission threshold, not a strength downgrade.** Writing a
   weakly-evidenced row at `weak_clue` and letting review sort it out is wrong when the
   evidence does not support the claim *at all* — it still enters every count and still
   costs reviewer time.
3. **Audit a new harness's first output row by row before trusting its coverage number.**

---

## Findings worth your attention (not bugs)

**Executive voice is a genuinely low-yield source, and the taxonomy already said so.**
`docs/signal_taxonomy.md` marks podcasts (15b) "don't-build — yield too low for this
population." The run confirms it empirically: across 108 companies and 377 fetched pages,
**8 observations**. Mid-size private industrial executives rarely speak on the record. The
early runs returned podcast *directories* — episode listings with titles in quotation marks
and no statements — which is why the query now asks for reporting verbs rather than
appearances. I did **not** lower the evidence bar to raise the count; `absent_confirmed` is
the honest and common outcome here.

**Buyers and sellers describe the same condition with no shared vocabulary.** The single
most valuable thing an operator says — *"we were still running our distribution centers on
spreadsheets, and that just does not scale"* — matches **nothing** in the seller-side theme
patterns, because vendors write "digital transformation" where operators write
"spreadsheets". A seller-only vocabulary silently drops the buyer half of the market. This
is now handled by `quotes.BUYER_VOICE_PATTERNS`, resolving into the same theme keys so the
spine is not forked. **This asymmetry is itself a finding for the write-up.**

**`H-EXECVOICE-01`'s coverage gap is really `H-EXECID-01`'s.** 47 of 108 companies have no
identified executive, so there is no name to search for. The attempts record that
dependency explicitly rather than hiding it. Raising exec coverage raises both.

---

## One decision I made that you should confirm

**All nine themes in `core/topics.py` are now `buyer_detectable = True`.** Cloud migration,
cybersecurity/OT and workforce enablement previously carried `False` because job postings
and registries could not see them. `H-FIRSTPARTY-01` classifies free text through the same
spine, so it *can* — and it returned workforce-enablement buyer observations on its first
run. Leaving the flags made `gap_report.py` print "NO INSTRUMENT" beside a non-zero buyer
count, which is self-contradictory output.

**This is not equal footing, and I have written that into both the code and convention 21a.**
An announcement is a *biased* instrument: companies announce what they are proud of and
never announce the legacy estate that forced them. Absence there means "not announced" —
weaker than "not happening", and weaker than the absence of a job posting.

It matters because the gap report now shows exactly two candidate divergences — **cloud
migration and cybersecurity/OT**, each messaged by 36% of providers with zero buyer signal —
and both sit on precisely the themes companies are least likely to announce. **Treat them
as the weakest-supported findings in the set, not the headline ones.** If you disagree with
the flip, reverting is three flags in `core/topics.py`.

---

## Also closed

- **All 9 missing `website` values** (8 pilots + A024) resolved by search and written back
  to `Companies`, scoring the domain against name tokens and refusing below a floor.
  Closes the named `H-WAYBACK-01` gap — Priority 3 item 1.
- **OSHA pagination** — Priority 3 item 2. v1.1 concluded the source could not be paged;
  the parameters were right and the values were wrong. The page's own pagination link
  carries `p_start=` *empty* with `p_finish` as a cursor. Following the link the server
  publishes, rather than reconstructing one, pages correctly. **13 companies capped at 20
  are now 4 capped at 40** — the cursor cycles after two pages, so 40 is a real remaining
  ceiling and those 4 are marked `[CAPPED]` floors rather than reported as exact.
  (The first version of my fix reported 40 as complete, which would have replaced a
  *declared* cap at 20 with an *invisible* one at 40. Caught before commit.)
- `Attempts` contract gap: `stale_beyond_threshold` is a governance suppression but was not
  in the allowlist, so a company whose only coverage was stale could not be reported at all.
  This crashed the first `H-FIRSTPARTY-01` run — and the run context correctly abandoned the
  run rather than committing a partial one.

---

## Not done

- Priority 2 harnesses (`H-PROCUREMENT-01`, `H-PATENTS-01`, `H-EMPREVIEW-01`, …) — not
  started. Priority 1 plus the audit and rework consumed the session.
- The deferrals in the priority doc (`Discards` sheet, attempt backfill, `DECISIONS.md`
  seeding, self-review of unreviewed observations) were left alone as instructed.

## Suggested next session

1. **Review a stratified sample of the 87 `buyer_articulates` rows.** They are the newest,
   least battle-tested evidence in the base and every convergence claim rests on them.
   Two things I'd check first: own-domain "Our People"-style pages that carry a publication
   date and slip through as announcements, and articles where "AI" appears because the
   company *serves* AI infrastructure rather than adopting it.
2. `H-EMPREVIEW-01` (Glassdoor/Indeed) — the unbiased counterpart to first-party
   announcements, and the instrument that could actually falsify a workforce-enablement or
   legacy-constraint claim.
3. `H-VENDOR-01` has a running start: 24 vendor-published customer URLs are already
   recorded in the `H-EXECVOICE-01` run log rather than discarded.

## Verification

`scripts/validate_repo_db.py` passes all 8 checks. All 97 test checks pass across five
test modules. Committed incrementally — 7 commits, nothing left uncommitted.
