# Signal Taxonomy — IndStudy 26 Signal Advisor

> **PATCH MERGED 2026-09-02.** `taxonomy_patch_2026-08-31_rev2.md` and its v2/v3 revisions
> are folded in as §§19–26 below. Those patch files are superseded but retained as decision
> record — do not delete them.
>
> Merge policy going forward is **append-only**: families 1–18 and the seller-discourse
> section keep their numbers permanently, and new cross-cutting sections take the next
> available number from 26. Nothing is inserted mid-document, so no cross-reference breaks.
>
> Open: §20.3 carries a placeholder pending the definition of `signal_class`. §25 records
> theme-lock requirements. The `cybersecurity_ot` split was decided by Matthew on 2026-09-02
> (split: `THEME-08` continues as `cybersecurity`, `THEME-10 ot_modernization` minted) and
> the continuing theme's key was renamed `cybersecurity_ot` -> `cybersecurity` the same day,
> before any derived table existed. Both live in `core/topics.py`; the retired key is
> declared in `RETIRED_THEME_KEYS` there.

Decomposes each of the 18 evidence families (+ seller discourse) into concrete signal
types, per the brief's core deliverable. This is design output for Matthew to carry into
Claude Code and the Harness Advisor project — no code, no schema changes, no Notion
updates happen here.

## Legend

- **Availability** — High / Medium / Low, for a mid-size, often privately-held company
  (not Fortune 500). Calibrated against `source_lists.md`'s private-company reframing.
- **Reliability** — the *ceiling* grade a well-executed extraction from this signal type
  can typically reach, on the locked A–D `source_grade` scale (A=primary/attributable,
  B=credible secondary, C=directional/weak, D=exclude). Actual per-observation grading
  still happens at extraction time — this is the type's realistic best case.
- **Extraction** — `API` (clean programmatic access) / `structured-scrape` (consistent
  page structure, scriptable, no API) / `unstructured-judgment` (free text or media
  requiring reading/interpretation, high per-source variance).
- **Evidence role** — `buyer_articulates` / `buyer_acts` / `provider_market_responds`
  (locked three-way split). Only seller-discourse signals should ever be
  `provider_market_responds`, per the buyer-dominant research posture.
- **Priority** — `build-now` / `build-later` / `don't-build` / `done` (already built).
- **Instrument class** — IC1–IC4. Whether the instrument is *capable of observing the
  thing being looked for*, as distinct from how attributable a claim is once observed.
  Governs what an *absence* of signal licenses. See §20.
- **Retrospective reach** — `current_only` / `bounded` / `archival`. How far back a
  source can speak. Scored per source, not per harness. Gates before instrument class in
  any historical composition. See §21.

---

## 1. First-party strategy & governance

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 1a. Company newsroom/press release (own site) | Medium | A | structured-scrape | buyer_articulates | build-later |
| 1b. PR wire distribution (PR Newswire/Business Wire) | Medium | A | structured-scrape | buyer_articulates | build-later |
| 1c. Local/regional business journal profile (Bizjournals) | High | B (A when directly quoting exec) | unstructured-judgment | buyer_articulates | build-later |
| 1d. SEC filing / annual report | Low (public-debt subset only) | A | API | buyer_articulates | don't-build (check opportunistically only) |

**Notes:** 1a and 1b are close enough in structure to share one harness rather than two.
1c is the highest-value item in this family per `source_lists.md`'s own reframing (now
doing the work SEC filings used to do), but it's genuinely expensive to build well —
no single API, hundreds of regional outlets, real per-article relevance judgment. Good
first test case for the upstream classification harness (see design section below).
**12a (commercial press release) folds into 1a/1b — don't build as a separate family-12
harness.**

## 2. Financial & capital allocation

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 2a. USASpending.gov award record | Low–Medium | A | API | buyer_acts | build-now |
| 2b. Municipal/industrial revenue bond (MSRB EMMA) | Low | A | API | buyer_acts | build-later |
| 2c. State/local economic development incentive award (Good Jobs First) | Medium | A | structured-scrape | buyer_acts | build-now |
| 2d. County property/assessor record | High | A | structured-scrape (fragmented per county) | buyer_acts | build-later |

**Notes:** 2a and 2c are both ownership-agnostic, clean, and directly evidence real
capital commitment — genuinely near the top of the whole taxonomy for effort-to-value
ratio. 2d is high-value but the per-county fragmentation cost is real; consider piloting
only on the counties where Anvil-100 companies actually concentrate rather than
attempting universal coverage.

## 3. Workforce & organizational exhaust

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 3a. Individual job posting (LinkedIn/Indeed/careers page) | High | B | unstructured-judgment | buyer_acts (weakly buyer_articulates via posting language) | done (H-JOBPOST-01) |
| 3b. Aggregate posting pattern (derived from 3a over time) | High once 3a data accrues | B | derived, not a new source | buyer_acts | build-later (Week 3+) |
| 3c. WARN Act layoff notice | Low–Medium | A | unstructured (fragmented, per-state DOL) | buyer_acts | build-later |
| 3d. NLRB case (union dispute) | Low | A | API/WEB | buyer_acts | fold into family 13, don't build separately |

**Notes:** 3a is already built and already the project's single highest-value family per
Jacob's own framing — the Kenco finding (467 postings, 5 genuine) confirms extraction
quality matters more here than source coverage. 5b (ERP-system-name job postings) should
be added as a field on this existing harness rather than spun up as a new family-5
harness. 3c is real but low-yield and it signals contraction more than modernization
pressure — worth a second look on relevance before investing.
Presence-strong, absence-weak — H-JOBPOST-01's realized reach is `current_only` and its
coverage is bounded by client-side rendering, so this note does not license absence claims.
See §21.3.

## 4. Employee experience & workarounds

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 4a. Glassdoor review (individual, tech/process complaints) | High | C (single review); B in aggregate across many reviews | unstructured-judgment, anti-scraping friction | buyer_articulates | build-later |
| 4b. Reddit thread naming the company | Low | C/D | unstructured-judgment | buyer_articulates | don't-build |
| 4c. OSHA whistleblower complaint | Low | B | structured-scrape | buyer_acts | fold into family 9, don't build separately |

**Notes:** 4a only clears a useful reliability bar in aggregate — design it as a
"theme-extraction-over-N-reviews" harness, not a single-review extractor, or it will sit
at C forever. 4b's reliability ceiling is too low to justify dedicated build effort.

## 5. Technology-stack traces

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 5a. BuiltWith/Wappalyzer detected stack | High (front-end only) | B | API ($) | buyer_acts (current-state, not pressure) | build-later |
| 5b. Job posting naming enterprise system (SAP/Oracle/Manhattan) | High | B | unstructured-judgment | buyer_acts | merge into 3a, don't build new |
| 5c. Vendor trust-center/subprocessor list | Low | B | unstructured | n/a — wrong direction for buyer-dominant posture | don't-build |
| 5d. GitHub org search | Very low | n/a | API (clean, but nothing to find) | — | don't-build |

**Notes:** This family is thinner than the original 18-family list implies once you
separate out 5b (already covered by job postings) and 5c/5d (mismatched to a
non-tech industrial/construction population). 5a is reasonable enrichment metadata but
is not itself a modernization-*pressure* signal — it describes current state, not a
gap or an action.

## 6. Vendor & partner disclosure

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 6a. Vendor case-study/customer story naming the company | Low–Medium | A when found | unstructured-judgment (search across many vendor sites) | buyer_acts | build-later |
| 6b. G2/Capterra review naming implementation partner | Low | C | unstructured | buyer_acts | don't-build |
| 6c. Conference speaker/sponsor list mention | Low | B | unstructured | buyer_articulates | merge into family 15, don't build separately |

**Notes:** 6a is high-reliability when it hits but combinatorially expensive (N vendors ×
108 companies) — a strong test case for the upstream classifier, since the real problem
is deciding *whether a found case study is about one of our target companies* before
running full extraction.

## 7. Procurement & contracting

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 7a. SAM.gov federal contract award | Low–Medium | A | API | buyer_acts | build-now |
| 7b. State procurement portal bid/award | Low–Medium | A | unstructured (fragmented per state) | buyer_acts | build-later |
| 7c. BidNet/GovSpend aggregated bid data | Medium | A/B | structured-scrape ($) | buyer_acts | build-later (cost-gated) |

**Notes:** `source_lists.md` originally deprioritized this family assuming a
manufacturing/logistics-only population. The Anvil-100 mix is heavier on
construction/general contracting than originally scoped, and GCs live on public bids —
this family deserves re-weighting upward relative to the original design, and 7a in
particular is cheap enough to just build now.

## 8. Physical footprint & capacity

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 8a. Building permit record (new construction/expansion) | Medium–High | A | unstructured/structured-scrape (fragmented per jurisdiction) | buyer_acts | build-later |
| 8b. Zoning board/planning commission minutes | Medium | B (A when a verbatim exec statement is captured) | unstructured-judgment | buyer_acts / buyer_articulates | build-later (share harness with 8a) |
| 8c. CoStar/LoopNet commercial property listing | Medium | B | structured-scrape ($) | buyer_acts | build-later (cost-gated) |
| 8d. Satellite imagery comparison (Google Earth historical) | High (imagery) / requires visual interpretation | B | unstructured-judgment, visual not textual | buyer_acts | build-later, best used as a *verification* step for another source's claim, not primary discovery |

**Notes:** 8a/8b share the same municipal-portal ecosystem — one harness, not two. This
whole family has real evidentiary value (physical capex is a hard action signal) but the
per-jurisdiction fragmentation is the genuine cost driver. Pilot on the counties where
Anvil-100 companies concentrate before attempting broad coverage.

## 9. Industrial, safety & environmental records

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 9a. OSHA establishment inspection/violation record | High | A | API | buyer_acts | build-now |
| 9b. EPA ECHO compliance/enforcement record | High (mfg/industrial/construction) | A | API | buyer_acts | build-now |
| 9c. MSHA record (mining-adjacent) | Very low | A | API | buyer_acts | don't-build (opportunistic check only) |
| 9d. State environmental agency portal | Medium | A/B | unstructured/structured-scrape (fragmented per state) | buyer_acts | build-later (gap-fill only) |
| 9e. OSHA whistleblower complaint (from family 4) | Low | B | structured-scrape | buyer_acts | build alongside 9a |

**Notes:** 9a/9b remain the single cleanest, richest, ownership-agnostic pair in the
entire taxonomy — correctly the #1 priority in `source_lists.md`'s own ranking. 9c is a
near-zero-yield check given the actual Anvil-100 industry mix (no obvious mining
representation) — don't build a dedicated harness for it.

## 10. Logistics & supply-network exhaust

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 10a. FMCSA SAFER carrier record | High (fleet-operating cos) | A | API | buyer_acts | done (H-FMCSA-01) |
| 10b. Import/export bill-of-lading data (ImportGenius/Panjiva) | Medium | A | API ($) | buyer_acts | build-later (verify international exposure in Anvil-100 sample before paying for this tier) |
| 10c. USA Trade Online census trade data | High (industry-level only, not company-level) | A but low specificity | API | — | don't-build as an Observations-producing harness |
| 10d. Port authority public data | Low | B | unstructured, fragmented per port | buyer_acts | don't-build |

**Notes:** 10a is done. 10b is worth a manual spot-check of a handful of consumer
goods/medical devices/food distribution companies before committing to the paid tier —
if none of them show meaningful import/export activity, skip it.

## 11. Product, quality & customer friction

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 11a. CPSC recall record | Low–Medium | A | API | buyer_acts | build-later (cheap, opportunistic pass rather than dedicated priority) |
| 11b. BBB complaint record | Medium | C | unstructured-judgment | buyer_articulates | don't-build |
| 11c. Trustpilot/app-store review | Low | C | unstructured | buyer_articulates | don't-build (mismatched — B2B industrial population, not consumer-app) |
| 11d. Industry-specific complaint board | Low | C | unstructured | buyer_articulates | don't-build |

**Notes:** Everything in this family except 11a caps out at C reliability, which is a
weak return on build effort. 11a is worth an opportunistic API check but not a
dedicated-priority build.

## 12. Commercial & channel behavior

(Folded entirely into families 1 and 15 — see notes there. No independent signal types
survive as distinct from 1a/1b (press releases) and 15a/15c (executive visibility). The
one item worth keeping separate:)

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 12c. LinkedIn company-page update history | High | B | unstructured-judgment, strong anti-scraping barrier | buyer_articulates | build-later — flag as an infrastructure-risk item, not just a design decision (LinkedIn access is the real blocker, not extraction logic) |

## 13. Legal & dispute records

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 13a. Federal court filing (CourtListener) | Medium | A | API | buyer_acts | build-now |
| 13b. Federal court filing (PACER) | Medium | A | API ($) | buyer_acts | build-later (redundant with 13a's free tier for most cases; use only to fill CourtListener gaps) |
| 13c. State court record | High (per source_lists' own note — private companies show up here often) | A | unstructured, fragmented per state | buyer_acts | build-later |
| 13d. NLRB case | Low | A | API/WEB | buyer_acts | build alongside 13a |

**Notes:** CourtListener is underrated in the original ranking — free, clean API,
explicitly `PRIVATE-OK`. A vendor dispute over a failed ERP implementation showing up
here would be one of the highest-value single observations this project could produce.
Worth promoting to build-now alongside the API-family sources.

## 14. Patents & IP

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 14a. PatentsView assignee-search patent record | Medium (concentrated in medical devices subset; thin elsewhere) | A | API | buyer_acts | build-now |

**Notes:** Clean, cheap, ownership-agnostic. Expect thin-but-real coverage, concentrated
wherever the Anvil-100 list has R&D-heavy companies (medical devices most likely;
construction/trucking/food distribution likely near-zero). Whether a given patent
signals `active_transition` or existing `target_state` capability is an extraction-time
judgment call on subject matter, not a taxonomy-level distinction.

## 15. Executive candor & actor networks

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 15a. LinkedIn post/article authored by a named executive | Medium (highly person-dependent) | A | unstructured-judgment; requires first identifying which execs even exist per company | buyer_articulates | build-later |
| 15b. Podcast appearance | Low | A when found | unstructured-judgment + paid search API | buyer_articulates | don't-build (yield too low for this population; opportunistic manual check only) |
| 15c. Conference talk/panel recording (YouTube) | Low–Medium | A | unstructured-judgment, video/transcript pipeline (different tech stack than text scraping) | buyer_articulates | build-later |
| 15d. Industry association board bio | Low–Medium | B | unstructured | buyer_articulates (weak — curated/promotional, not spontaneous) | don't-build |
| 15e. Conference speaker/sponsor list (from family 6) | Low | B | unstructured | buyer_articulates | build alongside 15c |

**Notes:** 15a has the highest per-instance reliability ceiling in the entire taxonomy
(A, directly attributable) — but it has a real prerequisite cost: identifying who the
relevant named executives even are for each of the 108 companies, before any monitoring
can start. That identification step is itself worth designing as a small enrichment task
before treating 15a as build-ready. 15b's population mismatch (mid-size industrial execs
rarely podcast) makes it the clearest "don't build" in this family despite matching
Jacob's own example list.

## 16. Local & community records

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 16a. City council minutes (Granicus/Legistar) | Medium | B (A when verbatim exec testimony) | unstructured-judgment, but concentrated on 2 common platforms | buyer_articulates / buyer_acts | build-later |
| 16b. County board agenda | Medium | B | same platform dynamics as 16a | buyer_acts | build alongside 16a |
| 16c. Local newspaper archive | Medium | B | unstructured, fragmented per outlet | buyer_articulates | build-later, lower priority than 16a/16b |

**Notes:** 16a/16b look as fragmented as 8/13 on paper, but most municipalities run on
just two platforms (Granicus and Legistar), which is a real structural advantage over
permit portals or state court systems — worth exploiting before assuming this family is
as expensive as the others.

## 17. Digital-product & service telemetry

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 17a. Public status page (statuspage.io) | Low | B | structured-scrape | buyer_acts | don't-build |
| 17b. Release notes/changelog | Very low | B | structured-scrape | buyer_acts | don't-build |
| 17c. App store version history | Low | B | structured-scrape | buyer_acts | don't-build (opportunistic only) |

**Notes: flag this whole family for an explicit deprioritization decision, not a
signal-by-signal one.** All three signal types are built around consumer-facing digital
products and fit SaaS/tech companies far better than construction, trucking, energy,
food distribution, or general industrial manufacturers. Given the confirmed Anvil-100
industry mix, expected yield across this entire family is close to zero. Recommend
Matthew and Jacob explicitly sign off on shelving family 17 rather than letting it die by
attrition signal-by-signal.

## 18. Historical change & disappearing evidence

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| 18a. Wayback Machine snapshot diff (job pages, case studies, service pages) | High | B (the diff is objective; the interpretation of *why* is judgment) | API | buyer_acts | build-now |

**Notes:** One of the more genuinely novel signal types in the whole taxonomy — it
surfaces *removed* evidence (a dropped case study, a quietly cancelled initiative, a
changed job requirement) that no live-page harness would ever see. Per `source_lists.md`'s
own observation, this may be *more* valuable for private companies specifically, since
they leave a thinner live footprint to begin with. Clean API, high availability, build
now.

## Seller discourse (comparative benchmark only — not a buyer family)

| Signal Type | Availability | Reliability | Extraction | Evidence Role | Priority |
|---|---|---|---|---|---|
| SD-a. Consulting/SI firm service page/case study | High | B (self-promotional, expect inflated framing) | unstructured | provider_market_responds | build-later (Week 2) |
| SD-b. Webinar library/event agenda (Manifest, MODEX, Gartner) | Medium | B | unstructured | provider_market_responds | build-later (Week 2) |
| SD-c. Sales job posting at a modernization provider | Medium | B | unstructured-judgment | provider_market_responds | build-later (Week 2) — but essentially free: reuse H-JOBPOST-01's existing infrastructure pointed at provider companies instead of buyer companies |

**Notes:** All three are correctly scheduled for Week 2 per the syllabus ("establish
seller benchmark"), not Week 1 — nothing here is being deprioritized, just sequenced.

---

## Harness architecture: grouping by source, not by family

Revising the build-order logic itself, per the correction: a harness is bound to one
underlying **source type** — one API, one platform, one content ecosystem — not to one
evidence family and not to one signal type. Most sources feed more than one family,
which is the actual reason the family-by-family view above overstated the harness
count. This section regroups everything around that unit and re-ranks the full list in
one pass.

### Proposed harness groupings

| Harness | Source(s) | Families fed | Priority | Why grouped this way |
|---|---|---|---|---|
| H-FMCSA-01 | FMCSA SAFER | 10 | done | — |
| H-JOBPOST-01 | LinkedIn/Indeed/career pages | 3, 5 (ERP-name field), seller discourse SD-c (same infra pointed at providers) | done — extend | one scraping/classification pipeline, three uses |
| H-SAFETY-ENV-01 | OSHA (inspections + whistleblower) + EPA ECHO | 9 | build now | same shape of problem as FMCSA — resolve company name → agency ID → pull record. Cheapest possible next harness given H-FMCSA-01 already solved that resolution pattern once |
| H-FEDSPEND-01 | USASpending.gov + SAM.gov | 2, 7 | build now | both federal award/contract systems; one integration produces rows in two families |
| H-FEDLEGAL-01 | CourtListener + NLRB case search | 13 | build now | both federal case-search systems; free and clean, promoted from the original ranking |
| H-WAYBACK-01 | Wayback Machine | 18 | build now | unique "removed evidence" signal; worth designing as a reusable verification utility other harnesses can call, not only a standalone family-18 source |
| H-PATENTSVIEW-01 | PatentsView | 14 | build now | cheap, clean, thin-but-real coverage |
| H-COUNTYREC-01 | Building permit portals + county property/assessor records | 8, 2 | build later | same jurisdictions, same access pattern — pilot on the counties where Anvil-100 companies actually sit, not all counties |
| H-MUNIMEETING-01 | Granicus/Legistar (city council + county board + zoning minutes) | 16, 8 | build later | more tractable than it looks — most municipalities run one of two platforms |
| H-FIRSTPARTY-01 | Company press releases + PR wire + local business journals | 1, 12 | build later | real value, real search-then-classify cost — good proving ground for the upstream classifier |
| H-VENDOR-01 | Vendor case studies + G2/Capterra | 6 | build later | combinatorial search cost (many vendors × 108 companies) |
| H-EXECVOICE-01 | LinkedIn posts + YouTube talks + conference speaker lists | 15 | build later | blocked on one prerequisite — identifying named executives per company |
| H-EMPVOICE-01 | Glassdoor + Indeed reviews + Reddit | 4 | build later | needs an aggregate-theme design (single reviews cap at C), plus real scraping friction |
| H-TRADEDATA-01 | ImportGenius/Panjiva + port authority data | 10 | build later | check international exposure in a sample of Anvil-100 before paying for the tier |
| H-STATEGOV-01 | State court records + state procurement portals + WARN databases + state environmental portals | 13, 7, 3, 9 | build later | one framework, per-state adapters — build adapters only for states where Anvil-100 companies concentrate |
| H-CPSC-01 | CPSC recall database | 11 | build later, cheap/opportunistic | free API, low yield |
| H-LINKEDINCO-01 | LinkedIn company page updates | 12 | build later | infrastructure risk (anti-scraping), not just a design call |
| H-BUILTWITH-01 | BuiltWith/Wappalyzer | 5 | build later | enrichment metadata, not itself a pressure signal |
| H-SATELLITE-01 | Satellite imagery diffing | 8 | build later | different technical paradigm (visual, not text) — use to verify claims from other sources, not for primary discovery |
| H-SELLERCONTENT-01 | Consulting/SI firm sites + webinar libraries | seller discourse | build later (Week 2) | scheduled, not urgent |

**Not building, full stop:** MSHA, GitHub org search, vendor trust centers/subprocessor
lists, BBB/Trustpilot/industry complaint boards, podcast search, industry association
board bios, MSRB EMMA (demoting this one from my earlier build-later call — niche, and
it doesn't cluster with anything higher-value). Rationale for each is already in the
family tables above.

**Family 17 — left in, restated plainly:** statuspage.io / release notes / app-store
version history are built for consumer-facing digital products, and the confirmed
Anvil-100 mix (construction, trucking, energy, consumer goods, medical devices, food
distribution) doesn't produce that shape of company. Expected yield is close to zero.
I'm treating this as shelved rather than spending further design effort decomposing it.

### Full re-ranked build order

1. H-FMCSA-01 — done
2. H-JOBPOST-01 — done, extend for the 5b field + SD-c reuse
3. H-SAFETY-ENV-01 (OSHA + EPA ECHO)
4. H-FEDSPEND-01 (USASpending + SAM.gov)
5. H-FEDLEGAL-01 (CourtListener + NLRB)
6. H-WAYBACK-01
7. H-PATENTSVIEW-01
8. H-COUNTYREC-01 (permits + assessor)
9. H-MUNIMEETING-01 (Granicus/Legistar)
10. H-FIRSTPARTY-01 (press/PR/local business journals)
11. H-VENDOR-01
12. H-EXECVOICE-01
13. H-EMPVOICE-01
14. H-TRADEDATA-01
15. H-STATEGOV-01
16. H-CPSC-01
17. H-LINKEDINCO-01
18. H-BUILTWITH-01
19. H-SATELLITE-01
20. H-SELLERCONTENT-01 (Week 2, scheduled not urgent)

18 net-new harnesses (plus the 2 already built) cover all 18 families + seller
discourse — down from the 30–35 estimate my first pass landed on, once sources are
grouped by actual technical integration point instead of by evidence family. Nothing
here is final; this is the working ranking until something in Weeks 2–3 changes it.

---

## H-EXECVOICE-01: exec-identification prerequisite + extraction design

Family 15 (15a LinkedIn posts, 15c conference talks/speaker lists) is worthless without
knowing which named person to watch per company. No public equivalent of a proxy
statement exists for privately-held companies, so this has to be built once, per
company, before H-EXECVOICE-01 can run at all.

### Prerequisite: exec identification

Sourcing, ranked by reliability/availability for this population:

1. **Company "Leadership"/"About" page** — highest priority. Structure varies
   company-to-company but each individual page is stable once found, so this is
   `structured-scrape`, not full unstructured judgment. Reliability A.
2. **ZoomInfo/data-broker record** — the project already pulls ZoomInfo employee
   ranges for Companies; worth checking whether that same access surfaces leadership
   contacts as a byproduct before building or paying for anything new.
3. **LinkedIn company page "People" tab, filtered by title** — high availability, same
   anti-scraping risk already flagged on H-LINKEDINCO-01.
4. **Press release / local business journal announcing a leadership hire** — dual
   purpose, also a genuine H-FIRSTPARTY-01 signal in its own right.
5. **Targeted search fallback** (`"[Company]" "VP Supply Chain"` etc.) for companies
   where 1–4 come up empty.

**Title filter:** CEO/President, COO, CIO/CTO or VP IT, VP Operations, VP Supply
Chain/Logistics, VP Manufacturing/Plant Ops, and the rare "Head of Digital
Transformation" title when it exists. Deprioritizing sales/marketing/HR/legal
leadership *for this family specifically* — not irrelevant everywhere, but less likely
to speak to modernization pressure.

**Output:** a one-time (or infrequently refreshed) enrichment pass per company
producing a short name/title/source/confidence list — not itself a watch harness, just
the input list H-EXECVOICE-01 monitors. Storage question sent to Harness Advisor as
item 6 below.

### H-EXECVOICE-01 itself: per-signal-type approach, given the exec list

**15a (LinkedIn posts/articles):** LinkedIn has no public API and real anti-scraping
risk (same barrier as H-LINKEDINCO-01 and the People-tab lookup above). Recommend
search-engine-indexed discovery (site-restricted search for the named exec) over
direct profile scraping or credential-based access — lower recall, but doesn't fight
LinkedIn's bot detection or require login. Needs a relevance filter before extraction:
not every post by a named exec is a signal (a picnic photo isn't; a post about an ERP
rollout is) — same shape of exclusion problem the job-posting harness already solved
for ordinary operational hiring vs. genuine modernization roles.

**15c (conference talks) + 15e (speaker lists, merged from 6c):** sequence cheap before
expensive. Conference speaker lists/session bios are `structured-scrape` and don't
require video — check those first as a filter. Only invest in YouTube search +
transcript extraction (a genuinely different technical pipeline from text scraping) for
execs who already show up as public conference speakers, rather than blindly searching
video for all 108 companies' named execs.

**Organizational_state guidance specific to this family:** executive candor is the one
signal type where `organizational_state` is often stated directly in the source's own
words rather than inferred — "we're mid-overhaul" (`active_transition`), "we finally
finished replacing the WMS" (`target_state`), "we're still running 20-year-old systems"
(`legacy_constraint`). Worth flagging as a reliability advantage unique to this family.

**One classification trap worth flagging to the upstream classifier design:** a video
or post can *feature* a buyer-side exec while being *published by* a vendor (a
"customer testimonial" on a consulting firm's channel). Evidence_role should follow the
publisher, not the speaker — that content is `provider_market_responds` / family 6
(vendor disclosure), not `buyer_articulates` / family 15, even though the words come
from the buyer's own exec. This is exactly the kind of ambiguity the classifier's
step-2 signal-type classification needs to resolve, not something to leave to whichever
extractor happens to find it first.

---

## Open design question: the upstream signal-classification harness

Jacob's proposal: a harness that looks at a piece of candidate content and (a)
classifies which signal type it is, (b) judges whether it's worth extracting from,
*before* a per-signal extractor runs. Conceptual decision logic, in order:

1. **Subject match check** — is the target company actually and unambiguously the
   subject of this content, or is it a false positive (the FMCSA harness's own
   "SOUTHWESTERN EXPRESS" vs. "Western Express" substring problem, generalized to text
   content)? Fail here → discard, log as `subject_mismatch`.
2. **Signal-type classification** — map the content to one of the ~30–35 signal types
   in this taxonomy, or to `no_match`. This determines which per-signal extractor (if
   any) should receive it downstream.
3. **Concreteness check** — does the content contain an actual checkable claim, or is
   it pure marketing/boilerplate with nothing extractable? Fail here → discard, log as
   `no_checkable_claim`.
4. **Marginal-value check** — is this instance meaningfully different from what's
   already been extracted for this company/signal type, or is it redundant (the Kenco
   finding: 467 postings, 5 genuine — most instances of a high-volume signal type add
   nothing new)? Low marginal value → either discard or downgrade extraction priority,
   log as `redundant_instance`.
5. **Route** — pass content + classified signal type to the matching per-signal
   extractor, or discard with a structured reason.

**Discard-reason mapping, now that the Attempts/Harness_Sources spec (Rev 2) exists.**
This harness's discards aren't a new vocabulary — they're `failure_category` values on
an Attempts row, same as any other harness's misses:

- Step 1 (subject mismatch) → `entity_no_candidate` / `entity_below_threshold` /
  `entity_ambiguous_multiple` (entity_resolution stage) — already covered, no gap.
- Step 3 (no checkable claim) → `content_unstructured` or `parse_failure`
  (extraction stage) — already covered, no gap.
- Step 4 (redundant/low marginal value) → **no existing category fits.** The closest,
  `suppressed_by_cap`, is about truncation by a declared cap, not about a classifier
  judging an individual instance low-value relative to what's already on file. This is
  a real gap worth naming to Harness Advisor directly rather than overloading an
  existing category, since §9 Q3 explicitly anticipates this harness ("when a
  classification harness exists: a Discards child table...") — this is that harness,
  so now is the right moment to close the gap rather than retrofit later.

This design is conceptual only; implementation is Claude Code's job once Matthew is
ready.

---

## Questions for Harness Advisor — status

The four questions above are resolved by the Attempts/Harness_Sources spec (Rev 2):

1. **One harness, multiple evidence families — yes, not 1:1.** `evidence_family` is a
   property of the Observation, not the harness. Confirms every multi-family grouping
   in the harness architecture above is architecturally sound as designed.
2. **Source_Families many-to-many — via new `Harness_Sources` junction sheet**,
   keyed on `(harness_id, harness_version, source_family_id)`. `Source_Families` itself
   stays a flat reference table.
3. **Discard-reason vocabulary — folded into `failure_category`**, not a separate
   list, stored on the new `Attempts` sheet (grain: one row per run × company ×
   attempted signal). Staged: `candidates_evaluated`/`candidates_discarded` counts now,
   a per-candidate `Discards` child table once a classification harness actually
   exists.
4. **`harness_id` granularity — one per logical harness, not one per external API.**
   Confirms H-SAFETY-ENV-01, H-FEDSPEND-01, H-FEDLEGAL-01, H-COUNTYREC-01, and
   H-MUNIMEETING-01 are all legitimate as single harnesses, each with its own
   `Harness_Sources` rows for OSHA/EPA, USASpending/SAM.gov, etc. Split rule for future
   grouping calls: separate harnesses only when the pieces are independently useful,
   need independent version cadence, or one's output feeds the other as input — shared
   API calls alone are not grounds for splitting.

**New follow-ups to send back:**

5. `failure_category` has no value for "classifier judged this instance redundant
   relative to prior extractions" — every discovery/fetch/entity/extraction/
   classification/temporal/governance category covers a different kind of miss, and
   none covers low marginal value on an otherwise valid, on-subject candidate. Worth a
   fifth category, maybe under a `deduplication` stage or added to `governance`
   alongside `suppressed_by_cap` — Harness Advisor's call which.
6. **Where does the H-EXECVOICE-01 prerequisite output live?** Identifying named
   executives per company (name, title, source, confidence — see the exec-ID design
   note above) is neither an Observation (no checkable modernization claim) nor an
   Attempt (it's Companies-side enrichment, not harness-run coverage). It's naturally
   one-to-many — a company can have several relevant execs — so it doesn't fit cleanly
   as fixed columns on Companies the way employee_count/revenue_estimate do. Likely
   needs its own small child sheet in the `Harness_Sources`-style pattern (e.g.
   `Company_Executives`: company_id, name, title, source, confidence,
   last_verified), but that's a schema call, not mine to make.

## §19 — Channels are not families

**Rule.** Evidence family is determined by *who makes the claim*, not by *where the claim
surfaced*. A publication venue is a delivery channel. A single channel may carry
observations into multiple evidence families with different evidence roles.

**Corollary — extraction is per-claim, not per-document.** One artifact may yield several
observations at different families, roles, and reliability grades.

**Instances.**

- **Trade press** (H-TRADEPRESS-01) — carries family 15 exec articulation, `buyer_acts`
  behavioral reports, and reclassified first-party announcements.
- **Vendor marketing** (H-VENDOR-01) — carries family 6 buyer articulation, `buyer_acts`
  deployment facts, and `provider_market_responds` vendor framing.

**Precedent.** Consistent with the locked harness many-to-many: one `harness_id` writes
Observations across multiple evidence families via `Harness_Sources`. This section states
the reader-side version of the same rule so it does not have to be re-derived per harness.

---

## §20 — Dimension 6: instrument bias class (`instrument_class`)

**Locked 2026-08-31.** Scored **per signal type**, not per harness — a single harness may
span several classes (H-TRADEPRESS-01 spans IC1–IC3). Taxonomy dimension only; no DB column
at this time. Schema question deferred to Harness Advisor if it becomes filterable.

**What it measures.** Whether the instrument is *capable of observing the thing being
looked for*. Distinct from reliability, which measures how attributable a claim is once
observed.

| Code | Name | Description | Examples |
|---|---|---|---|
| IC1 | `curated_interested` | Published by a party with an interest in the impression created. Selection bias toward wins. | Company announcements, vendor case studies, contributed columns, seller discourse benchmark |
| IC2 | `third_party_characterization` | Published by a party not interested in the transaction, but selecting for newsworthiness. | Journalist profiles and features, analyst coverage |
| IC3 | `revealed_behavior` | Byproduct of operating, not addressed to an audience. Hard to game. | Job postings, building permits, FMCSA, procurement records |
| IC4 | `involuntary_disclosure` | Published over the subject's likely preference. | OSHA, EPA ECHO, legal filings, employee reviews |

### §20.1 Negative-inference rule (governance)

`instrument_class` governs what **absence** of signal licenses. This is the operative content of
the dimension; the code by itself is inert.

| Class | Inference licensed by absence |
|---|---|
| IC1 | **None.** Absence is not evidence of absence. Presence is evidence of presence, discounted for puffery. |
| IC2 | Very weak evidence of absence. |
| IC3 | Weak-to-moderate, conditional on demonstrated coverage of that company by the source. |
| IC4 | Moderate, conditional on coverage and on the source's reporting threshold. |

**Reporting rule.** A divergence resting solely on absence in an IC1 instrument is
**formally untested**, not a weak finding, and is reported as open pending an IC3 or IC4
instrument. Every confidence claim in the report cites the class of the instrument the
claim rests on.

### §20.2 Orthogonality to reliability

The axes are independent and both are required:

| Signal type | Reliability | `instrument_class` |
|---|---|---|
| Contributed exec column | High — attribution unambiguous | IC1 — worst |
| FMCSA safety record | Moderate | IC3 — good |

Reliability answers *can we trust the attribution of what we found*. `instrument_class` answers
*could this instrument have found it at all*.

### §20.3 Disambiguation from `signal_class`

`signal_class` is a **different field on the same registry rows** and holds something else.
`instrument_class` is the bias axis and nothing else. A reader who conflates the two will
misread every confidence claim in the report, because the negative-inference rule in §20.1
keys on `instrument_class` alone.

*Pending: the definition of `signal_class` is not recorded here — supply it and this note
gets sharpened against the actual confusion rather than the general one.*

### §20.4 Refused instruments

§20.1 governs absence of signal from a **functioning** instrument. An instrument that was
built, ran, and was refused is not covered by it and licenses **no inference at all**,
independent of class. See the `ACCESS_BOUNDED` gap-report status.

The three states below are distinct and must not share a flag:

| State | Meaning | Recoverable | Counts toward ACCESS_BOUNDED |
|---|---|---|---|
| Source refusal | 403, robots, paywall | No | **Yes** |
| Rate limit | Throughput ceiling | Yes — pacing | No |
| Egress block | Our own network config | Yes — config | No |

### §20.5 Class sets the ceiling; coverage sets the value

`instrument_class` bounds the negative inference available from a signal type. It does not
deliver it. The realized value is the class ceiling **discounted by the source's structural
coverage of the specific company**.

IC4 is therefore not a license. Worked example — `ST-DOCKET` is IC4, ceiling "moderate,"
realized "very weak," because federal dockets miss state-court matters and commercial
contracts routinely compel private arbitration. Worked example — `FMCSA` absence for an
entity below the reporting threshold is `entity_below_threshold`, not `absent_confirmed`,
and licenses nothing.

**Requirement.** Every source carries a **structural coverage denominator**: how many of the
108 the source can see *at all*, recorded separately from how many it returned data for.
Absence is only interpretable against that denominator.

### §20.6 Reachability test — not a taxonomy dimension

Reachability is **harness state, not taxonomy**. It is volatile — robots.txt changes,
paywalls move, rate limits shift — and a dimension that goes stale between sessions is worse
than none, because it gets trusted. It lives in the observation-level access flag and in the
`ACCESS_BOUNDED` status.

What is stable enough to record per signal type is the test that predicts it:

> A signal type is reachable when **(a)** either the subject or the state has an incentive to
> publish it, **and (b)** no intermediary between subject and reader has an incentive to
> enclose it.

Both conditions required. Condition (b) is the one that is usually forgotten and it is why
`instrument_class` does not predict access: an executive posting to LinkedIn is a subject
maximally motivated to be read, and the post is refused anyway.

| Source | (a) publication incentive | (b) no enclosing intermediary | Predicted | Observed |
|---|---|---|---|---|
| Own-domain careers pages | Subject — needs applicants | Self-hosted | Reachable | Reachable |
| WARN, permits, OSHA, EPA | State | None | Reachable | Reachable |
| Granicus / Legistar | State | Present but contractually suppressed | Reachable | *pending* |
| LinkedIn exec posts | Subject | Present, strong | Refused | Refused |
| Glassdoor, Indeed | Subject (reviewer) | Present — content *is* the product | Refused | Refused |
| Paywalled trade press | Publisher | Is the enclosing party | Refused | Refused |

**Known limit of the test.** It predicts *permission*, not *retrievability*. H-JOBPOST-01
passes both conditions and is still partly uncollectable because client-side rendering hides
the content from a plain fetch. Permission and retrieval are separate failures and should be
recorded separately.

---

## §21 — Dimension 7: `retrospective_reach`

**Per source, not per harness** — the same grain rule as `instrument_class`. H-PROCUREMENT-01
alone spans two values (see §21.2).

**Why this qualifies as a dimension where reachability did not.** §20.6 kept reachability out
of the taxonomy because it is volatile — robots.txt changes between sessions. Retention policy
is not volatile. A court keeps dockets permanently; FMCSA's window is set by regulation. Reach
is stable enough to score and freeze.

| Value | Meaning |
|---|---|
| `current_only` | Shows present state. No dated history. Cannot speak to any past bucket. |
| `bounded` | Fixed retention window. Speaks to buckets inside it, nothing before. |
| `archival` | Durable dated record. Speaks to any bucket within the source's existence. |

### §21.1 Nominal vs. realized reach

Reach carries the same split as `instrument_class` in §20.5: **the source sets the ceiling,
our access sets the realized value.**

A paywalled trade archive is `archival` nominal and `current_only` realized, because the
archive exists and we cannot enter it. Record both. Composing on nominal reach overclaims by
exactly the size of the access gap.

Special case — **`ST-REMOVEDPAGE` is bounded by *our* crawl window, not the source's.** It is
derived from differencing our own captures, so its reach began when we started crawling and
cannot be extended backwards by any means. Record it as `bounded (self-referential)`.

### §21.2 Reach is per source, and harnesses are mixed

| Harness | Source | Reach | Confidence |
|---|---|---|---|
| H-PROCUREMENT-01 | USASpending awards | `archival` | High |
| H-PROCUREMENT-01 | SAM.gov registration status | `current_only` | High |
| H-FIRSTPARTY-01 | Dated newsroom / press archive | `archival` | High |
| H-FIRSTPARTY-01 | Current site state | `current_only` | High |
| H-JOBPOST-01 | Own-domain careers pages | **`current_only`** | High |
| H-PATENTS-01 | PatentsView | `archival` (≈18mo publication lag) | High |
| H-FEDLEGAL-01 | CourtListener dockets | `archival` | High |
| H-FEDLEGAL-01 | NLRB | `archival` (`out_of_theme`) | High |
| H-SAFETY-ENV-01 | OSHA inspections | `archival` | Medium — verify retention |
| H-SAFETY-ENV-01 | EPA ECHO compliance detail | `bounded` | Medium — verify window |
| H-LOCALRECORDS-01 | Granicus / Legistar minutes | `archival` | Medium — verify per platform |
| H-PERMITS-01 | County permits / assessor | `bounded`, **county-dependent** | Low — varies by jurisdiction |
| — | FMCSA SMS | `bounded` (rolling window) | Medium — verify window length |
| — | State AG breach portals | `bounded`–`archival`, **state-dependent** | Low — varies by statute |
| — | SEC EDGAR / 8-K | `archival` | High |
| — | WARN notices | `archival` | Medium — verify per state |
| H-TRADEPRESS-01 | Trade outlets | `archival` nominal / **`current_only` realized** | High |
| H-TRADEPRESS-01 | LinkedIn | moot — `access_bounded` | High |
| H-VENDOR-01 | Vendor case studies | `current_only` (undated, silently revised) | Medium |
| — | `ST-REMOVEDPAGE` | `bounded (self-referential)` | High |

Low- and medium-confidence rows are classifications I have reasoned to, not verified. They
should be confirmed against the sources before the schema freezes on them.

### §21.3 Composition rule — reach gates before class

For any historical bucket **T**, evaluate in this order. The order is the whole point.

1. **Reach gate.** Does the source's *realized* reach cover T? If no, the source is **null for
   T** — not quiet, not weak evidence, not anything. Stop here.
2. **Access gate.** Was the source accessible to us during T? If no, **null for T**. Access
   state must be stored per bucket, not as a current value (§20.4).
3. **Class rule.** Only now does `instrument_class` govern what silence means, per §20.1.

**Null is not zero.** A `current_only` source contributes nothing to Q1 2025 rather than
contributing an absence. Any implementation that stores these the same way will manufacture
staleness signal out of sources that were never able to speak.

**Highest-risk composition in the portfolio: H-JOBPOST-01.** It is IC3 — the class whose
silence is *supposed* to carry weight — paired with `current_only`, the reach that can say
nothing about the past. Composed naively it will license historical conclusions it has no
capacity to support. It is the source most likely to produce a confident wrong answer.

### §21.4 Snapshot retention — decide now, cannot be decided later

A `current_only` source becomes `bounded` **prospectively** if captures are retained. Begin
snapshot retention immediately for every `current_only` source — careers pages above all.

This is the only recommendation in this patch with a deadline attached: every week without
retention is a week of history permanently unrecoverable. Six months of retained job-post
captures converts the portfolio's most dangerous source into a usable longitudinal one. Six
months of not retaining leaves it `current_only` forever.

---

## §22 — Signal_Types registry

Fields: `signal_type_id` | `signal_type_name` | `evidence_family` | `instrument_class` |
`status`.

`signal_type_id` uses the mnemonic vocabulary shared with the locked signal-type-first
harness convention `H-{SIGNAL_TYPE}-{NN}`, so the registry can serve as the authority for
the outstanding naming reconciliation. **IDs below are proposed, not locked**, pending that
reconciliation.

### §22.1 `status` vocabulary — five values

The Week 2 carried items were hard to resolve because `status` had no vocabulary for a type
that is real but produces nothing. It does now. This is a vocabulary gap, **not** a registry
schema gap — no new field is needed.

| Status | Meaning | Enters denominators? |
|---|---|---|
| `active` | Produces observations against a theme | Yes |
| `routing_only` | Valid type that reclassifies to another type and writes nothing of its own | No |
| `out_of_theme` | Reachable, produces real data, data does not bear on any modernization theme | No |
| `access_bounded` | Registered, built, ran, refused | No |
| `reference` | Produces roster or keying data consumed by other harnesses, not evidence | No |

**Hard rule.** Only `active` types enter any denominator — coverage fractions, yield rates,
`instrument_class` share, ACCESS_BOUNDED calculations. A registered-but-silent type that
leaks into a denominator dilutes every metric it touches.

Types with a non-`active` status still carry `instrument_class` **except** `reference` types,
which carry reliability but no class — see §22.4.

### Seed — trade press (H-TRADEPRESS-01)

| signal_type_id | signal_type_name | evidence_family | instrument_class | status |
|---|---|---|---|---|
| ST-EXECQUOTE-REPORTED | Exec quote in reported trade article | 15 | IC2 | active |
| ST-EXECCOLUMN | Bylined / contributed exec column | 15 | IC1 | active |
| ST-EXECPANEL | Panel / conference / keynote coverage | 15 | IC2 | active |
| ST-PRESSPROFILE | Journalist profile or feature | varies | IC2 | active |
| ST-WIREREPRINT | Reprinted press release (routing class) | per H-FIRSTPARTY-01 | IC1 | routing_only |

Note on ST-EXECQUOTE-REPORTED: the *speech* is volunteered by the exec but the *topic* is
elicited by a reporter and the publication decision is the outlet's, so it scores IC2 rather
than IC1 despite being first-party speech. This is the single most valuable articulation
type currently available and the crawl should weight toward it.

ST-WIREREPRINT is a routing class, not a terminal signal type — see §23.2.

### Seed — vendor case studies (H-VENDOR-01)

| signal_type_id | signal_type_name | evidence_family | instrument_class | status |
|---|---|---|---|---|
| ST-VENDORQUOTE | Buyer quote in vendor case study | 6 | IC1 | active |
| ST-VENDORDEPLOY | Deployment fact asserted in vendor case study | 6 | IC1 | active |
| ST-VENDORFRAMING | Vendor characterization of buyer demand | 6 | IC1 | active |

### §22.2 Week 2 carried types — resolved 2026-09-02

| signal_type_id | instrument_class | status | Ruling |
|---|---|---|---|
| ST-NLRB | IC4 | `out_of_theme` | Real IC4 instrument, family 13. Register it — the registry records what was considered and set aside, not only what is live. Excluded from all denominators. Pre-scoped if a labour/workforce theme is ever opened. |
| ST-LINKEDINPOST | IC1 | `access_bounded` | Class confirmed. Reachability is a separate axis and it fails the §20.6 test. See §22.3 |
| ST-DOCKET | IC4 | `active` | Class confirmed; negative inference realized at **very weak**, not the IC4 ceiling. See §20.5 |
| ST-REMOVEDPAGE | IC3 | `active`, corroboration-gated | See §22.5 |
| ST-EXECID | — (none) | `reference` | Not a signal type. See §22.4 |
| ST-EXECCOLUMN | IC1 | `active` | Grade **held at full**. See §22.6 |

### §22.3 ST-LINKEDINPOST — class and reachability are separate findings

IC1 is correct and the logged reasoning stands: self-published, topic chosen by the speaker,
framing fully subject-controlled, absence licenses nothing, does not count toward closing the
articulation-bias gap.

That is independent of whether it can be collected. Under §20.6 LinkedIn fails condition (b)
— an enclosing intermediary overrides the subject's intent to be read — and 8 of 8 URLs were
refused on 2026-09-01. Allowlisting a domain on our side does not make a source willing.

**Both are true at once and neither cancels the other.** This is the first type-level
`ACCESS_BOUNDED` case and it should be reported as one rather than sitting as an active type
with no output. Even fully reachable it would be IC1 and would not widen articulation.

### §22.4 ST-EXECID is reference data, not a signal type

Executive identification populates the roster that H-EXECVOICE-01 and others key against. It
observes no theme and bears on no divergence. It therefore takes **no `instrument_class`**.

Scoring it IC1 would be actively harmful: it inflates the portfolio's IC1 share and makes the
instrument-bias problem read as worse than it is, off a type that carries no evidence weight
at all.

It does carry **reliability**, and at high stakes — a wrong executive name silently poisons
every downstream H-EXECVOICE-01 query. This split is itself the cleanest demonstration of
§20.2: the two axes are independent, and here one applies while the other does not.

### §22.5 ST-REMOVEDPAGE — IC3, and its confounder is correlated with the theme

**IC3, not IC4.** IC4 requires publication by another party over the subject's preference — a
regulator, a court, a former employee. Removal is the subject *exercising* control, not losing
it. That the removal is detectable is an artifact of our crawl differencing, not of any
compulsion. It is revealed behavior.

**Corroboration gate.** A `removed_page` event may never carry a standalone observation. It
may only raise `signal_strength` on an existing observation or flag for manual review.

The reason is a confounder that is not independent of what we are measuring: the most common
benign cause of mass page removal is a site migration or CMS replacement — which is *itself a
modernization event*. A company modernizing its web estate emits a flood of removals that
read as discontinuations. The noise is correlated with the signal, which is the one condition
under which a low-grade instrument becomes worse than no instrument.

### §22.6 ST-EXECCOLUMN — grade held at full

A bylined column by a named executive is **maximally attributable**: signed, published under
their name, legally attributable to them. Reliability grades attribution. Full grade.

The instinct to cap it is a bias objection wearing a reliability costume — the pre-§20 habit
of smuggling instrument bias into the reliability score because there was nowhere else to put
it. There is somewhere else now: the column is IC1, the worst class, and §20.1 already
strips its absence of any inferential force. Capping reliability as well would penalize the
same defect twice and corrupt the axis §20.2 depends on.

**Narrow exception.** Cap one grade where the byline is corporate rather than personal — "the
[Company] team," an unnamed contributor, or an explicitly ghostwritten piece. Named
individual byline takes full grade.

### §22.7 Registry hygiene

`ST-EXECQUOTE-REPORTED` scores IC2 despite being first-party speech, because the topic is
elicited by a reporter and the publication decision is the outlet's. Recorded here because it
looks like an error on inspection and will be "corrected" by someone otherwise.

---

## §23 — H-TRADEPRESS-01 extraction rules

Sources: Construction Dive, Transport Topics, FleetOwner, Food Dive, MedTech Dive and
comparable verticals.

### §23.1 Role and grade by type

| Signal type | Evidence role | Reliability |
|---|---|---|
| ST-EXECQUOTE-REPORTED | `buyer_articulates` | Full |
| ST-EXECCOLUMN | `buyer_articulates` | Full |
| ST-EXECPANEL | `buyer_articulates` | Capped −1 (paraphrase of spoken remarks) |
| ST-PRESSPROFILE | `buyer_acts` **only** | Capped −1 |

**ST-PRESSPROFILE splits at the artifact level.** Where the journalist reports a concrete
action — deployed X, hired Y, opened Z — the journalist is a witness to behavior and the
claim is admissible as `buyer_acts`. Where the journalist *characterizes* the company's
posture, the claim is context only and generates no observation.

**Hard rule: ST-PRESSPROFILE never carries `buyer_articulates`.** Journalist
characterization is not company speech and admitting it would inflate the articulation leg
the harness exists to widen.

### §23.2 Wire reprint handling — reclassify, do not exclude

Reprinted press releases are **routed, not filtered**. Excluding them at extraction makes
them invisible and silently drops their contribution to `signal_strength`, contrary to the
locked redundancy decision.

1. On wire-marker detection, reclassify the observation to first-party — family and role per
   H-FIRSTPARTY-01. Do not discard.
2. Run the normal redundancy check.
   - Already held by H-FIRSTPARTY-01 → `suppressed_redundant` in governance, **still counts
     toward `signal_strength`**.
   - Not held → genuinely new first-party evidence, admitted. Common in the Anvil-100, where
     firms frequently wire a release without posting it to their own site.
3. Reclassified observations never count toward trade press articulation yield.

**Marker grading.**

| Marker | Weight |
|---|---|
| PRNewswire / BusinessWire / GlobeNewswire byline | Conclusive alone |
| Explicit "press release" label | Conclusive alone |
| "About [Company]" boilerplate footer | **Not conclusive alone** — fires only with no reporter byline |

Boilerplate is appended to reported articles routinely; treating it as conclusive would
misroute genuine reported coverage into first-party.

---

## §24 — H-VENDOR-01 extraction rules

Family 6 (vendor/partner disclosure) locked previously. Roles resolved here.

### §24.1 Multi-role artifact

| Component | Role | Grade |
|---|---|---|
| Buyer quote (ST-VENDORQUOTE) | `buyer_articulates` | Capped −1 vs ST-EXECQUOTE-REPORTED |
| Deployment described (ST-VENDORDEPLOY) | `buyer_acts` | Full |
| Vendor framing of demand (ST-VENDORFRAMING) | `provider_market_responds` | Full |

The buyer quote is capped because vendor marketing typically composes it and obtains
approval rather than transcribing it. The **deployment fact is the strongest leg**, not the
weakest: named-customer deployment claims are checkable and carry legal exposure, so vendors
do not fabricate them.

`provider_market_responds` is reserved for the vendor's own assertions. A buyer speaking in
a vendor venue is still the buyer speaking.

### §24.2 Attribution gate

ST-VENDORQUOTE requires a **named individual with a title**. Anonymous attributions — "a
spokesperson," "an IT Director at [Company]" — drop out of the articulation role entirely.
Retain the ST-VENDORDEPLOY fact; discard the quote.

### §24.3 Accounting rule

H-VENDOR-01 is IC1 throughout and **does not count as progress against the
articulation-bias gap**, whatever its yield. Record it as volume, not as widening.

---

## §25 — Theme vocabulary lock

### §25.1 The identifier is not the risk

The stated worry is renames and free-text drift splitting a company's history into two
unrelated series. That risk is real and it is the cheap one to fix:

> **Separate the stable identifier from the mutable label.** Themes carry opaque IDs
> (`THEME-04`) that never change. Human-readable names are a display attribute and may be
> edited freely. A rename then costs nothing, and a *split* is forced to be explicit because
> it requires minting a new ID.

The expensive risk is the one that survives this fix: **a theme whose definition drifts while
its identifier holds.** That corrupts a series without splitting it, and unlike a split it
leaves no trace. Freezing the string is not enough — freeze the written definition and version
it, so a definition change is a visible event.

### §25.2 Detectability start dates

Three themes flipped `buyer_detectable=True` on 2026-08-31. Before that date the project held
no buyer-side instrument for them, so the evidence history is **null, not empty**.

Every theme therefore carries a `buyer_detectable_since` date, and buckets before it are
excluded from the series rather than recorded as zero. Without this, the three flipped themes
will read as a clean absence across every historical bucket — a manufactured finding that
looks like exactly the divergence pattern the project is built to detect.

Same failure mode as §21.3. Missing capacity to observe must never be stored as an observed
absence.

### §25.3 Per-theme instrument profile

For the temporal schema's negative inference to compose, each theme records which instrument
classes can see it at all:

| Theme property | Why the schema needs it |
|---|---|
| Classes with an active instrument | A theme visible only through IC1 has quiet that licenses nothing, ever |
| Evidence roles available | `legacy_constraint` is now `buyer_acts`-only — absence of articulation is structural, not a finding |
| `buyer_detectable_since` | Per §25.2 |

### §25.4 Definition-boundary requirement

Adjacent themes must have written boundaries before freeze, or observations will route
inconsistently across sessions and the inconsistency will be invisible afterward. Boundaries
required at minimum between `workforce enablement` and (a) `legacy_constraint`, both
observable in the same requisition text, and (b) labour friction, which is `out_of_theme` per
§22.2 and sits close enough to be confused with it.

---

## §26 — Gap report status (amendment)

Supersedes the prior "flag as weakest findings" handling of the two absence-based
divergences.

| Divergence | Prior status | New status | Testable against |
|---|---|---|---|
| Cloud migration | Weak finding | **Formally untested** — IC1 absence | Job postings (IC3): legacy-stack and migration language in requisitions |
| Cybersecurity (`THEME-08`, key `cybersecurity`; labelled "Cybersecurity / OT" until the 2026-09-02 split) | Weak finding | **Formally untested** — IC1 absence | State AG breach-notification portals (IC4); 8-K Item 1.05 for the public subset (IC4) |

Per §20.1, absence in an IC1 instrument licenses no negative inference. Both are reported
as open pending an IC3/IC4 instrument rather than as weak findings.

Candidate sources listed are **referred, not specced**. Harness feasibility is Harness
Advisor's call; no scoping done on this side.

---
