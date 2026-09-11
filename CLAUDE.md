# Market Intelligence Harness Project — Current State

**This file is pure current state only.** History and rationale for decisions live in
`DECISIONS.md` (append-only, to be seeded in a dedicated session — not yet populated) and
`docs/conventions.md` (locked conventions, each with the incident that produced it — treat
this as authoritative over anything in this file if they ever conflict). This file was
rewritten 2026-08-31 after the version on disk was found to be a stale pre-Week-1 copy,
updated again at the end of the 2026-09-01 follow-up session, and again on 2026-09-02
(post-session-6 follow-up: the 120-company question, backup cleanup, theme-key rename;
then session 8: the provider-side pattern fix, four H-JOBPOST-01 keys, the readability
denominator; then session 9 overnight, 2026-09-03: the corroboration-gate policy applied
portfolio-wide, the Talent.com aggregator leg, two audits closed; then session 12,
2026-09-04/05: the SAFETY-ENV v1.3 release executed, three review sheets drawn, the
58-row review queue compiled, judged row by row and applied (eight versions published);
then session 12.5, the same day: the last 16 judged and released and FMCSA's 20 held
conflicts accepted, quarantine 138 -> 0; then session 13, 2026-09-05: the temporal schema
built -- `Company_State_History`, `core/composition.py`, reach populated, the status rollup
filter, convention 42; then session 14, 2026-09-06, the Week 3 wrap-up: DR-0001 appended,
stable observation ids (convention 43), the EXECID low-grade tier, H-VENDOR-01 built,
TRADEPRESS live, O00369/O00373 accepted, FMCSA F15/F26 verified live, the gap report
recharacterised; then session 15, the same night: `industry_primary` populated from archived
NAICS for 68 companies, TRADEPRESS v1.6 scope 15 -> 79, EXECVOICE v1.6 reading the EXECID
low-grade names; then session 10, later
2026-09-03: the unclear gates resolved, eleven bug fixes, ST-PRESSCHAR, H-JOBPOST-01 v1.4; then
session 11, the job-posting final push: two measurements, no code change). Its counts are
verified by scripts/check_run_ledger.py, which warns when this file drifts.

Independent Study Project, Matthew Lebrecht, sponsored by Talbot West (Jacob Andra).
Academic supervisor: Matt Petschick. 5 weeks, started 8/24/2026, weekly checkpoint
Tuesdays 5:15pm. Currently in Week 2 (due 8/29 — running late, in progress).

**Credentials:** API keys live in `.env` at the repo root (gitignored); `.env.example` is
the committed template. Read them through `core/config.py` — `require_key()` for keys a
harness cannot work without (it raises rather than letting the harness degrade into
writing false absence), `get_key()` for genuinely optional ones. `BRAVE_API_KEY` is
configured and working.

## Governing question

What modernization pressures do operationally complex companies articulate and act upon,
where do buyer statements/actions and seller messaging converge or diverge, and how
adequately does the provider market address the gaps?

## Target profile ("Anvil")

Large + operationally complex (Jacob's disqualifying example: a law firm). Smaller than
Fortune 500, mostly privately held — this is central to the project's value proposition.
Industries actually represented: construction/general contracting (heavy), trucking,
energy, consumer goods, medical devices, food distribution — broader than any fixed list.
Qualification is a lightweight sanity check now, not a discovery problem — Talbot West
provided the company universe directly.

## Company universe

- **8 pilot companies** (`C0001`-`C0008`: 7 `qualified` plus C0007 PLS Logistics
  `pending_review`, a deliberate borderline case since Week 1 that every harness includes
  in its buyer scope -- C0008 CT Logistics was `excluded` and was restored 2026-09-01, see
  below): Midmark, Mack Group, Duke Manufacturing,
  Western Express, Venture Logistics, Kenco Group, PLS Logistics, CT Logistics
- **100 Anvil companies** (`A001`-`A100`): Talbot West CRM export, "Project Anvil"
**The buyer universe is 108 and every harness now iterates all of it.** C0008 CT
Logistics was `excluded` until 2026-09-01 while holding 2 released observations and
being attempted by 6 of 11 harnesses, so coverage denominators differed between
harnesses for a reason unrelated to the instrument. Restored to `qualified`. A latent
divergence remains: 6 harnesses call `db.companies()` unfiltered (which would include
an `excluded` company) while 4 filter on status explicitly. They agree only because
nothing is excluded today.

**The `Companies` sheet holds 120 rows and that is not growth.** 120 = 108 buyers + the 12
provider benchmarks below, which have shared the sheet since 22:39 on 2026-08-30 (the
H-SELLERCONTENT-01 build, `SESSION_REPORT_2026-08-30.md`). Session 6's hand-off line said
"120 companies" because `validate_repo_db.py` check 8 printed the sheet's row count without
saying what it was made of; it now prints "120 companies (108 buyers + 12 provider
benchmarks)". Investigated 2026-09-02: no duplicates, no leaked fixtures, no scope decision.
Every harness excludes the P rows, by status or by id prefix, so every buyer denominator is
108. See `session7_report.md` §1.

- **12 providers/sellers** (`P001`-`P012`): stored in `Companies` with
  `qualification_status = provider_benchmark` (not a separate sheet -- avoids forking the
  `company_id` foreign key that `Observations` keys to)

## Harnesses built (12)

| harness_id | What | Status |
|---|---|---|
| `H-FMCSA-01` v1.6 | Federal carrier registry | **Full universe 2026-09-01 (108).** 40 released observations, all released (v1.0 7, v1.3 4, v1.4 9 low-grade, v1.5 20); 8 resolve to a carrier. **v1.5's 20 rows are the pilot rows a person reviewed in Week 1-2, re-derived by the harness from the 2026-08-31 SAFER snapshot and accepted by Matthew on 2026-09-05 over the human values** (session 12.5 §2: snapshot date on all 20, counts moved on 8, no grade/strength/state/confidence changed). **v1.6 (2026-09-06): F15/F26 verified live with the QCMobile webkey** -- Midmark reads Private Property and its NOT AUTHORIZED status is explained as private carriage, Western Express and Kenco read Authorized For Hire, no false authority gap. Three fixes on that path (key read through `core.config`, national-average rates coerced from strings, "for hire" matched as both sources spell it). Not committed: the QCMobile record has no entity-type field and reports `Interstate` where SAFER reports the authority type, so a commit would re-open every reviewed pilot row; two field mappings for Week 4 |
| `H-JOBPOST-01` v1.4 | Job postings: own-domain careers pages (Workday, iCIMS, Paylocity, Greenhouse, Lever, **ADP**, inline lists) + the **Talent.com aggregator leg** | **Full universe live 2026-09-03 (108), twice.** Own-domain **17/108** readable (was 13; ADP 3 companies + OnTrac's inline list), 10 companies `access_blocked` because their Dayforce/UltiPro board hosts refuse this crawler by robots.txt; aggregator reaches 53 companies with ≥1 resolved cross-post (shallow). **All 53 rows released** (v1.1 3, v1.3 13, v1.4 16 released 2026-09-05 on Matthew's approval; v1.0/v1.2 21 earlier). PRESENCE ONLY still binds |
| `H-SELLERCONTENT-01` v1.4 | Seller/provider service pages, 4 archetypes | **Week 2's named deliverable.** 44 released in the workbook: v1.2 24 and v1.3 7 (both audited) and v1.4 13 (10 low-grade, released 2026-09-05 on Matthew's approval) |
| `H-SAFETY-ENV-01` v1.3 | OSHA + EPA ECHO merge | Full universe, 131 observations, **all released**: 67 at v1.0/v1.1 (grandfathered) and 64 refreshed to v1.3 by the ECHO paging fix (facility counts were silently capped at 100; Teichert 149) and the declared OSHA floors, **released 2026-09-04 on Matthew's standing authorization with no row individually judged** (artifact `H-SAFETY-ENV-01__v1.3.json` says so; its precision rate is undefined, not 100%) |
| `H-WAYBACK-01` v1.3 | Removed-page detection | Full universe, 31 released observations, all released (v1.3's 5 **confound-admitted** replatform rows and v1.2's 7 low-grade single-capture rows both released 2026-09-05 after individual review) |
| `H-EXECID-01` v1.1 | Executive identification (**prerequisite**, writes `Company_Executives`) | 931 execs in `Company_Executives`. **v1.1 (2026-09-06): the low-grade tier** -- an out-of-vocabulary title admitted as written (E26) or a name with no adjacent title on a leadership-class page (E32) writes `role_relevance unconfirmed`, grade C, confidence 0.3 / 0.25, a `[low-grade:` marker in `name_variants`; `db.sync_executives` accepts an empty title only on such a row; never primary, so EXECVOICE does not read them. v1.1 committed 2026-09-06 as HR-0064: 117 inserted (110 low-grade, 7 confirmed), 21 refreshed, 781 unchanged, 9 superseded (departures from re-read leadership pages); the tier needed three guards found on the first dry run (a name may not carry a role or domain word, an E26 title must be role-shaped, and a low-grade record must sit within 8 lines of a confirmed person) before its sample was clean. |
| `H-EXECVOICE-01` v1.7 | Executive candor -- attributable quotes in third-party coverage | 8 released observations, 56% coverage (47 companies blocked on no identified exec); v1.5 tightened the page identity test to FIRSTPARTY's all-token rule. **v1.5 published 2026-09-06** with O00369 / O00373 refreshed to the harness's current values by Matthew's decision (both now low-grade: generic-term only under the two-tier spine) via `--refresh-reviewed --refresh-ids`; O00372 stays held at v1.2 (corrected, not part of the decision). **v1.6 (session 15, Matthew's decision): also searches up to 4 EXECID low-grade (`unconfirmed`-role) names per company after the 2 primary; quotes graded by the unchanged rules, provenance stated in the text. Live 2026-09-06: HR-0065: 76 low-grade names searched across 30 companies (362 searches, 597 fetches); 2 new rows, both the same Brian Killinger appointment quote reprinted by two outlets, grade B / weak_clue under the normal rules, quarantined (sheet drawn); Coastal Cares produced nothing. O00372 still held.** |
| `H-EMPREVIEW-01` v1.1 | Employee review aggregate (family 4) | **Access finding, re-confirmed live 2026-09-06 (HR-0059): 107 of 108 `access_blocked`** -- Glassdoor, Indeed and CareerBliss refuse this crawler by robots.txt, Comparably trips the circuit breaker. HR-0058 the same morning is an offline replay whose failure categories are cache artifacts (`source_unavailable`), superseded by HR-0059 in meaning though not in status. Nothing has changed at the source |
| `H-TRADEPRESS-01` v1.7 | Vertical trade press: five signal types incl. **ST-PRESSCHAR** (the company describing itself, as reported) | 5 released observations before session 14, 15-company subset (v1.0, v1.2 audited; v1.5's 2 low-grade rows released 2026-09-05). **Live run 2026-09-06 on the seeded subset with the 10-host allowlist expansion: HR-0061, 15 companies, 5 rows proposed, 4 unchanged, 1 human-reviewed row held, 0 inserted. The added outlets reached 4 articles (Trucking Dive, Grocery Dive, AndNowUKnow, Food Logistics) and none was admissible, so the expansion has measured zero yield live.** **v1.6 (session 15): scope is every buyer with a `Companies.industry_primary` value, the SUBSET now an override -- 79 of 108 searchable** (64 from the NAICS enrichment + 15 seeded); 29 with no attributed record are still not searched. Live 2026-09-06 (HR-0066): 71 of the 79 searched before Brave's monthly quota ran out (HTTP 402; the last 8 recorded source_unavailable / transient), 9 new rows from 5 newly unlocked construction companies (5 low-grade, 3 grade B, one quote whose text names another company's CIO), judged 2026-09-06: 8 supported, O00604 unsupported and deleted (a Construction Dive sidebar teaser swept into the Q&A's last answer -- `article_body` now ends at the first end-of-article marker line, v1.7); the 8 released under the 0.15 under-20 threshold Matthew set the same day. O00376 held. **Session 15.5 (2026-09-06, $10 of Brave credit added): the 8 companies the quota interrupted (A097, A099, A100, C0002, C0003, C0005, C0007, C0008) were searched live as HR-0067 under v1.7 -- 41 articles read, nothing admissible, 8 `absent_confirmed`. The full 79-company scope has now been searched once; the harness has never written a row outside the seeded 15 plus the 5 companies HR-0066 covered.** |
| `H-PRODUCTQUALITY-01` v1.4 | Federal recall / adverse-event records, IC4 | 3 released observations, full universe. v1.1 and v1.2 audited and released; v1.4: 2 low-grade rows (split-sentence cue; the bare "manufacturing defect" symptom cue is admitted at low grade too), released 2026-09-05. Firm-name test now applies LEGAL's token-prefix rule against the seeded aliases |
| `H-FIRSTPARTY-01` v1.2 | Press releases, PR wires, business/trade journals | 230 released observations (v1.1's 61 live rows at 97% coverage; v1.2's **169 rows, 152 low-grade**, released 2026-09-03 on a 30-row sample -- the single-term rows v1.1 cut, readmitted under convention 41) |
| `H-BREACHPORTAL-01` v1.1 | State AG breach-notification portals (California DOJ, Washington AG), **IC4, `cybersecurity` only** | **Built and run 2026-09-06 (session 16, HR-0068): the portfolio's first licensed-absence instrument for a modernization theme.** All 108 searched for presence under the all-token identity rule; 8 companies headquartered in CA/WA are in scope for absence (Goodfellow Bros added by Matthew's ruling, HR-0069 v1.1): **7 `absent_confirmed`** (Lease Crutcher Lewis, Swinerton, Hathaway Dinwiddie, Devcon, Lynden, Teichert, Goodfellow), 1 covered (BNBuilders, listed in both states). 9 released rows (Whiting-Turner, Estes, C.R. England x2, doTERRA, OnTrac x2 via a dba clause, BNBuilders x2) after Matthew's review: 9 supported, one Estes duplicate excluded and deleted (v1.1 dedupes CA hits). **Both versions published 2026-09-06; DR-0002 composes the seven as `absence_licensed_IC4` in 2026-W36.** Out of scope tonight: Texas (connection timeout at the network), Maryland (JS-rendered), Vermont and Montana (robots), Massachusetts and New Hampshire (403), Iowa and Indiana (PDF year lists) |
| `H-LEGAL-01` v1.2 | Federal court dockets (CourtListener) **+ NLRB case search**, IC4 | 1 observation (O00377, audited overgraded, released); NLRB 124 cases across 36 companies and 0 observations by design. v1.2 (2026-09-03) wrote nothing new |
| `H-VENDOR-01` v1.0 | Vendor and partner disclosure (family 6, §24): vendor-published customer pages seeded from EXECVOICE's excluded URLs | **Built 2026-09-06 (session 14).** 24 seed URLs, 13 usable (8 appsruntheworld aggregator profiles and 1 provider page excluded), 11 companies, 6 pages read and about the company, 2 speakers named with titles, 0 rows: the deployments those pages describe (360 capture, EA mapping, an e-commerce platform) are not themes in the spine, and the named quotes carry no theme term. HR-0063 (HR-0062 the same morning is an offline replay whose two C0008 failures read source_unavailable instead of the live robots refusal). Quarantined, population 0. IC1 throughout; not a theme instrument in `core/composition.py`, so its silence licenses nothing |

All three Priority-1 harnesses from `session2_priority_order.md` are built and committed.

**Not yet built, next in order:** `H-VENDOR-01` is now the cheapest remaining win -- it has
24 vendor customer URLs from `H-EXECVOICE-01` plus a thin vendor tail surfaced by
H-TRADEPRESS-01's off-allowlist breakdown. Then `H-PROCUREMENT-01` (blocked on this
network, see below), `H-PATENTS-01`, `H-PERMITS-01`, `H-LOCALRECORDS-01`, `H-TECHSTACK-01`.

`H-LEGAL-01` was built 2026-09-01. **The "55 results for Kenco Group" that made it look
cheap was a full-text count, not a party count** -- its top hit is an unrelated Delaware
furniture bankruptcy. Party-scoped, Kenco has 21. The harness yields 1 row from 108
companies, which is the finding: federal dockets are overwhelmingly employment, personal
injury and ERISA matters, and being sued is not modernization evidence.

`H-PROCUREMENT-01` and `H-PATENTS-01` are blocked *here* but not blocked at the source.
Re-probed 2026-09-01 from a different network (a home router, not the school one); **no
probe outcome changed**, and the attribution is now settled rather than suspected:

- `api.usaspending.gov` is **blocked by a network appliance on this egress**, confirmed,
  not refused by Treasury. The appliance serves a "Web Page Blocked!" interstitial naming
  this machine's egress IP and an Attack ID, under an HTTP 500, on *every* endpoint
  including the API root. The separate TLS error is a third thing again: a **trust-store
  gap**, not interception -- USASpending serves a genuine Department of Treasury leaf
  issued by Entrust chaining to `Sectigo Public Server Authentication Root R46`, which
  certifi carries and this machine's 40-root Windows store does not. So it verifies in the
  harnesses' stack (`requests`) and fails in the probe's old one (`urllib`).
- `search.patentsview.org` returns NXDOMAIN from an ordinary resolver and the legacy
  `api.patentsview.org` serves an app shell -- consistent with a retired endpoint, i.e.
  the source's.

Nothing was recorded in the database either time, which was the right call both nights --
on 2026-08-31 for a reason that turned out to be wrong (a presumed intercepting middlebox),
and now for a citable one (convention 38). **Re-probe from a network without content
filtering before scoping `H-PROCUREMENT-01`;** the API itself is almost certainly fine.

`H-VENDOR-01` now has a running start: `H-EXECVOICE-01` records every vendor-published
customer page it excludes (24 URLs so far) in its run log, rather than discarding them.

## The audit gate (2026-08-31)

A new harness version's output is **quarantined on write** and publishes no coverage number
until an audit artifact exists at `harness_output/audits/<harness_id>__<harness_version>.json`.
`validate_repo_db.py` **check 9** enforces it. Exemptions come only from
`docs/gates/grandfathered_harness_versions.json` (18 pre-gate pairs). Procedure:
`docs/gates/gate_new_harness_output.md` -- load it fresh at the checkpoint, not while
building.

**The gate has been through one full cycle.** Both new harnesses were audited 2026-09-01,
passed the stop rule and are released: H-TRADEPRESS-01 v1.0 (2 rows, both `supported`) and
H-PRODUCTQUALITY-01 v1.1 (1 row, `overgraded` -- retained and downgraded, not excluded).
Check 9 reports 19 published versions: 2 audited, 17 grandfathered. Artifacts are in
`harness_output/audits/`.

All 337 observations carry a `publication_state`: **311 released, 26 quarantined.**

**Released 2026-09-01 (session 5):** H-EXECVOICE-01 v1.2 (8 rows, census control, 7
supported / 1 overgraded) and H-TRADEPRESS-01 v1.2 (1 row, census, supported). Check 9
reports 21 published versions: 4 audited, 17 grandfathered.

**Audited and released 2026-09-03:** H-LEGAL-01 v1.1 (O00377 overgraded, retained at 0.35) and
H-PRODUCTQUALITY-01 v1.2 (population 0). H-SELLERCONTENT-01 v1.3 was released by Matthew the
same morning (7 of 7 supported). Check 9: 7 audited, 17 grandfathered, 2 superseded.

**H-FIRSTPARTY-01 v1.2 was released by Matthew on 2026-09-03** (30-of-169 control, 29
supported, 1 overgraded; a FULL release -- all 169 rows including the 152 low-grade, 139 of
them released `unreviewed`). **H-SAFETY-ENV-01 v1.3 was released 2026-09-04 (session 12)**
on the standing authorization from session 10 item 2: artifact written with
`random_control.sampled_n = 0`, the 30-of-64 sheet drawn in session 10 was never judged, and
the artifact's only independent content is a mechanical check that the 64 rows are the same
ids, companies, topics, grades, strengths and confidences as the released v1.0/v1.1 rows they
replaced, with only the count wording changed. Check 9: 9 audited, 17 grandfathered.

**Eight versions released 2026-09-05 on Matthew's row-by-row review of the 58-row queue
`harness_output/audits/REVIEW_QUEUE_2026-09-04.md`** (every row `supported`, recorded row by
row through `apply_audit_verdict`, one census artifact per version, all eight published):
H-JOBPOST-01 v1.4 (16), v1.3 (13) and v1.1 (3), H-SELLERCONTENT-01 v1.4 (13, 10 low-grade),
H-WAYBACK-01 v1.3 (5, all confound-admitted), H-FMCSA-01 v1.3 (4 rows from HR-0034 on A024,
drawn with the sampler's `--only-quarantined` / `--ids` flags because the version also holds
20 released human-reviewed rows; v1.3 is in the grandfather registry, and the artifact now
coexists with that entry), H-PRODUCTQUALITY-01 v1.4 (2) and H-TRADEPRESS-01 v1.5 (2). The
result was relayed as one statement (every row supported), which an earlier text of the
artifacts misdescribed as a blanket approval; corrected the same day, and every artifact's
`summary_md` records both the review and the correction. **Session 12.5 (2026-09-05)
emptied the quarantine:** the last 16 rows (H-FMCSA-01 v1.4 9, H-WAYBACK-01 v1.2 7, all
low-grade) were reviewed individually by Matthew, all supported, and released with their
artifacts; and H-FMCSA-01's **20 held conflicts** (its last two runs' re-derivation of 20
released human-reviewed pilot rows O00002..O00027) were resolved by Matthew's decision to
accept the harness's values, executed through the harness's `--refresh-reviewed` opt-in on
an offline replay (HR-0057), recorded as 20 supported verdicts, and published as v1.5
(`H-FMCSA-01__v1.5.json`, whose summary says 20/20 is the acceptance decision, not a
re-reading). Check 9: 19 audited, 17 grandfathered, **0 quarantined rows**; the 8
quarantined runs left all wrote nothing. LEGAL v1.2,
EMPREVIEW v1.1, FMCSA v1.5 and EXECVOICE v1.5 wrote nothing. H-TRADEPRESS-01 v1.1 is **`superseded`**, a disposition
added this session: it holds 0 observations and v1.2 re-ran its exact attempt scope, so
there is nothing live to audit. Check 9 enforces that claim rather than trusting it.

**The audit artifacts are now in version control.** `harness_output/**` stays ignored
except `reference_runs/` and `audits/`. Before 2026-09-01 they were not committed, so a
fresh clone failed check 9 for both audited versions -- a mechanical control that only
worked on the machine that built it. Verified: `git clone` to a temp directory and
`validate_repo_db.py` passes 9 checks there.

Verdicts are written only by `core/db.py::apply_audit_verdict`, which refuses
`unsupported` / `wrong_entity` (those rows should not exist at any strength -- delete them
and record it) and refuses an `overgraded` verdict that changes no field.

The random-control exclusion threshold was **set by Matthew on 2026-09-06** (session 15):
**0.15 for a random control drawn from a population under 20, 0.10 at 20 and over**
(`core/audit.py::threshold_for`). Before that it was 0.10 and provisional; every artifact
carries the literal it was evaluated against. The first case it decided: H-TRADEPRESS-01
v1.6, a census of 9 with 1 exclusion (11.1%), failed at 0.10 and passed at 0.15.

## The most important open problem

**Closed 2026-08-31.** The evidence base was 185 `buyer_acts` to 0 `buyer_articulates`;
it is now **185 / 87 / 43**. Both buyer-articulation instruments are built and committed.

The successor problem is **evidence quality, not evidence volume.** Both new harnesses
committed output that had to be cut hard on audit:

- `H-FIRSTPARTY-01` v1.0 produced 248 rows at 97% coverage; **163 of them rested on a
  single generic matched term** ("workforce management" 48, "integration" 26,
  "cybersecurity" 18, "ai" 12), and 40 came from PR-wire index pages. v1.1 requires two
  distinct terms or a headline mention. 248 -> 79.
- `H-EXECVOICE-01` v1.0 committed 10 rows; 2 were wrong about *who spoke*. v1.1: 10 -> 8.

Every one of those was the failure mode named below. **Assume the same of the next
harness**: the counts a new harness reports on its first run are not the number to write
down.

**2026-09-02, the provider side had the same defect and it biased toward the thesis.**
Six of seven `systems_integration` provider rows rested on the bare word "integration", two
of four cloud rows on a lone vendor name, one data/AI row on a bare "AI", one ERP row on a
bare "SAP". Buyer-side over-matching hides divergences; provider-side over-matching
manufactures them. `core/topics.py` now has a two-tier admission rule (`patterns` fire
alone, `generic` needs a second distinct hit, `exclusions` are blanked first, `corroboration`
says whether a generic pair suffices) and H-SELLERCONTENT-01 was replayed from cache as
v1.3 with `--retire-stale`: **10 rows retired, systems_integration 7 -> 1 sellers, cloud
4 -> 2, data/AI 11 -> 10, ERP 7 -> 6.** The `systems_integration` "64% of sellers" figure
was never a finding. Before/after captures: `docs/diagnostics/gap_report_*_pattern_fix_2026-09-02.txt`;
session 8 report §3. **The buyer side was measured, not applied:** 11 committed rows route
differently under the new spine (4 H-FIRSTPARTY-01 machine rows, 2 human-reviewed
H-EXECVOICE-01 rows, 1 H-LEGAL-01 row among them) and none was removed -- re-running
those harnesses under the new spine is a decision, listed in session 8 §3.

**2026-09-03, the precision/recall reset (convention 41).** Matthew's decision after session
8: a gate that refuses because the claim is thin but the referent is right is a
CORROBORATION-STRENGTH gate and now WRITES at low grade; a gate that protects the referent
(wrong company, dictionary-word token, index page, eponymous trap, wrong speaker) is an
IDENTITY gate and still refuses. Applied to every harness in session 9: 411 gates
inventoried, 20 converted in 9 harnesses, 31 identity gates confirmed unchanged, ~40
unclear ones logged for decision (`docs/diagnostics/gate_inventory_2026-09-03.md`). A
low-grade row is `source_grade C` + `weak_clue` + `confidence <= 0.4` + an
`evidence_excerpt` starting `[low-grade:`; `core/topics.py::classify_tiered()` is the
spine's side of it. **183 low-grade rows exist, all quarantined.** `gap_report.py` excludes
them by default and prints what each theme would gain from them; `--include-low-grade`
shows the table the extractor's weakest tier would produce unreviewed (systems_integration
3 -> 19 buyers, cybersecurity 0 -> 13, workforce_enablement 2 -> 27). That table is not a
finding; it is the review queue.

**Session 10 (later 2026-09-03) resolved the unclear gates.** Staleness is five years
everywhere (`core/windows.py`). The Wayback replatform refusal is admitted as a CONFOUND with
its own marker, `[low-grade: confound-admitted;` (convention 41 amendment). Characterisation
vs action is built, not relaxed: H-TRADEPRESS-01's ST-PRESSCHAR carries the company
describing itself or its intent as `buyer_articulates` at C. The PQ symptom cue
"manufacturing defect" writes at low grade. Eleven bug fixes landed (see
`session10_report.md` §6), one with a visible cost: the ECHO paging fix re-quarantined 64
H-SAFETY-ENV-01 rows whose facility counts had been silently capped at 100. H-JOBPOST-01
v1.4 added an ADP adapter and an inline-list adapter; the measured long tail has one
buildable platform, and Dayforce/UltiPro hosts refuse this crawler by robots.txt.

Nine of the 10 themes in `core/topics.py` are `buyer_detectable = True` (the tenth,
`ot_modernization` / THEME-10, was split out of THEME-08 on 2026-09-02 and has no
instrument on either side, so its absence licenses nothing) — `H-FIRSTPARTY-01`
classifies free-text announcements through the same spine, so it can see any theme, and
leaving three flags False made `gap_report.py` print "NO INSTRUMENT" beside a non-zero
buyer count. **This is not equal footing and the per-theme notes say so:** an announcement
is a *biased* instrument, so absence there means "not announced", which is weaker than
"not happening" and weaker than the absence of a job posting. Cloud migration (now 18% of
sellers after the pattern fix, was 36%) and cybersecurity (THEME-08; key `cybersecurity`
since the 2026-09-02 rename from `cybersecurity_ot`, declared in `RETIRED_THEME_KEYS`; 36%)
have provider messaging and zero buyer signal, and `gap_report.py` now prints **"no absence
instrument"** for them rather than "buyer silent": `Theme.absence_licensed = False` where
every buyer instrument is IC1 or presence-only. They are formally untested (taxonomy §26),
not weak findings and not divergences.

**H-JOBPOST-01 v1.2 carries four new signal keys** (`cloud_infrastructure_hiring`,
`cybersecurity_hiring`, `workforce_enablement_hiring`, `ot_modernization_hiring`), all in
`BUYER_SIGNAL_TO_THEME`, which now covers all 10 themes (it covered 6). Signal Advisor's four
conditions are met and one is binding on every reader: **PRESENCE ONLY.** No absence claim
from any H-JOBPOST-01 key until the careers-page readability denominator is accepted.
`python scripts/careers_readability.py` measures it from `Attempts`: **13-14 of 108 (~13%)**
readable on the own-domain leg. `scripts/careers_platform_audit.py` (2026-09-03) read the
94 unreadable careers pages from the archive: no ATS worth an adapter (Dayforce leads at 6
of 94, 18 platforms in the tail), 12 inline static lists a generic parser could read, 58 on
WordPress. So H-JOBPOST-01 v1.3 added a **third-party aggregator leg**
(`harnesses/h_jobpost_01/aggregator.py`): 12 boards probed by robots.txt under this crawler's
identity, 8 refuse, 3 permit but block or serve a JS shell, **Talent.com works**. Live
2026-09-03: 53 of 108 companies have >= 1 cross-post that resolves to them (employer field
scored at the standard floor -- the identity gate is not relaxed there), 125 postings, 5
companies with a signal, one new-key presence hit (OnTrac, `cloud_infrastructure_hiring`).
Reach is broad and shallow: Talent.com indexes a handful of a company's requisitions, not
its board. Presence only, per condition 1.

**Session 11 (2026-09-03) closed the job-posting push at a structural ceiling: 17 deep,
53 shallow, 58 reachable, 50 neither, of 108.** A JSON-LD `JobPosting` scan of all 103
archived careers pages found none (structured data lives on detail pages the archive does
not hold). Dayforce tenant hosts and UltiPro serve `Disallow: /` to every crawler, so 7 of
the 10 `access_blocked` companies are settled; `jobs.dayforcehcm.com` (C.R. England, Power
Construction, Wharton-Smith) permits this crawler but loads postings client-side -- the one
remaining lead, a build of ADP's size for three companies. Further investment past that
requires rendering JavaScript or crossing a robots line. See `session11_report.md` §4.

## Evidence base snapshot (as of the 2026-09-01 session 5)

**544 observations** (of which **195 low-grade**; O00604 deleted on audit 2026-09-06, its id retired), 108 companies with evidence, **6,381 attempts
logged**, 69 harness runs, 6,480 rows in `Company_State_History` (DR-0001 and DR-0002, both appended 2026-09-06), **931 executives** in `Company_Executives` (821 confirmed across 63 companies, 110 low-grade `unconfirmed` from EXECID v1.1).
170 observations human-reviewed, 374 unreviewed (2026-09-06, after the session 16 follow-up). 24 signal types registered.
**544 released, 0 quarantined** (as of 2026-09-06, after the session 16 follow-up; quarantine empty). 10 themes (THEME-01..10) in `core/topics.py`; one theme
key retired so far (`cybersecurity_ot` -> `cybersecurity`, 2026-09-02, four machine rows
rewritten by `migrate_schema.py::rename_topic_keys`).

By harness (released rows, 2026-09-06, end of session 15): H-FIRSTPARTY-01 230, H-SAFETY-ENV-01 131, H-SELLERCONTENT-01 44, H-FMCSA-01 40, H-JOBPOST-01 32, H-WAYBACK-01 31, H-EXECVOICE-01 8, H-TRADEPRESS-01 5, H-PRODUCTQUALITY-01 3, H-LEGAL-01 1.

**Published coverage is now a separate question from run coverage.** Run
`python scripts/published_coverage.py`: it reports only released versions, excludes
quarantined and superseded runs by name, and deliberately reports NO blended
project-wide figure. `Harness_Runs.coverage_rate` is each run's own arithmetic and
blends audited with unaudited output if read directly.

**Do not assert these numbers from memory or from this file alone.** Run
`python scripts/check_run_ledger.py`, which compares the workbook against the version
committed at HEAD and reports this file's staleness as a warning. That is the Step 0
run-count check as of 2026-09-01, and it replaces the old one that compared the workbook
against *this document* -- a design under which documentation staleness was
indistinguishable from workbook drift, which is the thing an abort exists to catch.

## Schema

Sheets: `Companies`, `Observations` (core atomic-evidence table, bound 2:20,000),
`Harness_Runs` (has 6 coverage rollup columns), `Attempts` (append-only, bound 2:250,000
-- NOT the same ceiling as Observations, it grows with every re-run), `Signal_Types`
(registry stub -- seeded with only `carrier_registry_status`, `job_posting`,
`executive_identification`; left as free text, not yet dropdown-bound, since the full
taxonomy isn't finalized), `Harness_Sources` (junction table, harness-to-source
many-to-many), `Company_Executives` (17 cols, 931 rows; written only by `core/db.py::sync_executives`, keyed on `(company_id, name)`, with departure detection gated on having actually read a leadership page),
`Source_Families` (reference, now has a `source_id` key), `Lookups` (27 controlled
vocabulary columns, all source ranges bound to row 50 minimum), **`Company_State_History`**
(session 13, 2026-09-05: 25 columns, append-only and immutable, one row per derivation x
company x theme x ISO-week bucket; written only by `core/db.py::append_state_history`,
derived by `core/composition.py`, driven by `scripts/derive_state_history.py`). **Standing
instruction (Matthew, 2026-09-06): append each derivation as it is produced -- do not hold
for sign-off unless the dry-run diff looks like it needs a second look.** DR-0001 and DR-0002
are on the sheet; the derivation reads released rows and attempts from PUBLISHED runs only.
**Four coherence-framework tables** (build handoff 2026-09-08 + addendum, spec Rev 6 §13):
`Coherence_Framework_Taxonomy` (reference; **46 rows loaded 2026-09-08** -- 22 dimensions
COH-D01..D22, 19 failure families COH-F01..F19 in groups I-V, 5 reference-only generative
forces COH-G01..G05 -- verbatim from `docs/schema/Coherence_Framework_Taxonomy_v0.1.xlsx`
via `scripts/load_coherence_taxonomy.py`, which refuses on count, id, group, version or
collision problems and is a no-op on re-run), `Observation_Coherence_Tags` (the overlay, keyed BY
observation_id and never a column on `Observations`, so the framework can churn without
moving an id), `Coherence_Pilot_Runs` (**populated**: COHP-0001, 3 over-firing companies
and 3 matched comparisons, `scripts/coherence_pilot.py`), and `Coherence_Family_Dimensions`
(**127 rows loaded**, the many-to-many family-to-dimension mapping §2's synthesis join needs;
`scripts/load_coherence_family_dimensions.py`, which parses the archived source AND holds the
addendum's transcription as a constant and refuses if they disagree). **The addendum's stated
row count of 100 is an arithmetic slip and the data is sound** -- its own table and the
archived source independently list 105 references across F01-F18, plus COH-F19 expanded to
all 22 = 127; spec §13.5.1. **The convention 41 wall is
mechanical: `validate_repo_db.py` check 11 FAILS if any of the nine gate-computing modules
so much as names `Observation_Coherence_Tags`**, and tagging may cite `COH-D*` dimensions
only. Verified in both directions.
**`Observation_Ids`** (session 14, convention 43: the id registry, one row per id ever
assigned, 549 ids of which 24 retired; every insert consults it, every delete retires
into it; check 10 keeps it in step with the live sheet). `Harness_Sources` now carries reach on all rows (`nominal_reach`, `realized_reach`,
months, `realized_reach_effective_from` = the harness's first run date); provenance per row
is in its `notes` (taxonomy §21.2, the 2026-09-02 ping, or "Code 2026-09-05, unverified").

Repo structure: `core/` is the sole writer, with shared utilities (entity resolution,
attempt-run-context, topic classification). Harnesses are packages with `manifest.yaml`
structured version history.

Four mechanical checks, and they answer different questions:

| Script | Question |
|---|---|
| `scripts/validate_repo_db.py` | do the repo and the database agree? 11 checks: the audit gate (9), the observation-id registry (10), the coherence-framework walls (11) |
| `scripts/assert_validations.py` | are all 24 dropdown bindings present in the SAVED file? |
| `scripts/check_run_ledger.py` | has the working tree LOST anything committed at HEAD? Observations compared by id; `--retired ID,ID` acknowledges named deliberate removals, anything else missing still aborts |
| `scripts/theme_regression.py` | does `core/topics.py` route every observation the same way as at a given git revision (`--baseline`, default HEAD), with retired keys mapped forward? |
| `scripts/careers_readability.py` | what fraction of the 108 can H-JOBPOST-01 actually read? The denominator that gates every absence claim from its keys |
| `scripts/coherence_pilot.py` | which companies are in the coherence pilot's over-firing and comparison cohorts? Dry run by default; `--apply` appends, idempotent |
| `scripts/load_coherence_taxonomy.py` | load the framework's 46 reference rows verbatim from the source workbook, refusing on any shape or namespace problem |
| `scripts/load_coherence_family_dimensions.py` | load the 127 family-to-dimension mappings, diffing the archived source against the addendum's transcription and refusing if they disagree |
| `scripts/derive_state_history.py` | what could the project say about each company x theme x week, and why not? Dry run by default; `--apply` appends an immutable derivation. Composition order detectability -> realized reach -> instrument class (convention 42) |

`check_run_ledger.py` is the Step 0 run-count check as of 2026-09-01. It compares the
workbook against `git show HEAD:data/market_intel_db.xlsx`, because git cannot go stale
relative to itself. A run present in the working tree and absent at HEAD is uncommitted
work and is reported; a run present at HEAD and MISSING from the working tree is destroyed
history and is the abort (`--strict` exits 1; both paths are verified, not merely observed
passing). **`CLAUDE.md` staleness is a warning there and never an abort** -- prose goes
stale on its own, and the old check could not tell that apart from the database drifting.

## Known conventions (see docs/conventions.md for full detail + incidents)

- Idempotent writes, never overwrite human review
- Distinguish source drift from genuine harness error
- Every suppressed/truncated result gets reported, not silently dropped
- Entity resolution: score on name-token alignment, refuse to guess below confidence
  threshold, log every rejection
- Confirmed absence = coverage, not failure (`absent_confirmed` outcome)
- Attempt emission lives inside a run-context (`core/attempts.py`) -- a harness declares
  scope on open, close reconciles declared vs. emitted and auto-writes `not_covered` for
  gaps. Structural, not a written rule that breaks on the first early `continue`.
- **Recurring failure mode, now hit 9 times: loose pattern matching manufactures false
  confidence.** Week 1-2: the Infor/"Information Systems" bug, a Wayback false-positive on
  dated news posts, SellerContent's inflated coverage from homepage substitutes. The
  2026-08-31 session added six more, all caught by auditing output rather than by tests:
  an executive named "How We" (Kenco heading fragment); one named "Become An" (Rycon
  call-to-action); "Corporate Governance Guidelines" as a person, which also outranked and
  displaced Merit Medical's real roster; Prime Inc. matching Digital Prime Technologies /
  Prime Data Centers / Primech / Prime Electric because its name reduces to one common
  word; 163 of 248 first-party rows resting on a single generic term; and a quote
  attributed to Tom McGough off a page about someone else because "McGough" is also the
  company name.

  This is now unambiguously **the** characteristic failure of the project and belongs in
  the final report as a finding about automated evidence collection, not as a list of
  fixed bugs. Two generalisations earned this session: **(a)** a single common token is
  never an identity — convention 11's lesson recurs wherever names are matched, not just
  in `core/resolution.py`; **(b)** the fix is an *admission* threshold, not a strength
  downgrade — a claim unsupported by its own evidence should not exist at `weak_clue`.

- **GATE: when a new harness produces its first output, stop and read
  `docs/gates/gate_new_harness_output.md` before reporting any coverage number.** Load it
  fresh at that checkpoint -- do not hold it in context while building the harness, or the
  harness gets written to pass the audit rather than to read the source. Output is
  quarantined until an audit artifact exists; `validate_repo_db.py` check 9 enforces it.

- **Audit first-run output row by row before trusting a coverage number.** Every defect
  above was invisible in the summary line and obvious in the rows. A high coverage number
  on a new harness is a prompt to check, not a result.
- Seller messaging maps to `organizational_state = target_state` uniformly -- a provider's
  service page describes what's being sold, not the provider's own maturity.
- **Convention 41 (2026-09-03): corroboration-strength gates write at low grade; identity
  gates refuse; gates that fit neither are logged, not guessed.** Amends 32 for rows whose
  referent is right. The four marks of a low-grade row are in `core/topics.py`.

## Known data gaps

- ~~`Theme.absence_licensed` stale~~ **CLOSED 2026-09-06 (session 14 item 0b).** The flag
  is gone; `gap_report.py` reads `core/composition.py::absence_licensing`. **Since session 16
  one theme has a licensed-absence instrument: `cybersecurity`, through H-BREACHPORTAL-01
  (IC4), for the 7 companies headquartered in California or Washington.** The gap report
  prints "buyer silent (7 of 108 under a licensed instrument)" for it -- the §20.5
  structural-coverage denominator, never a bare "buyer silent". Every other theme still has
  none, so for them nothing prints "buyer silent": cybersecurity, the last zero-buyer theme with provider messaging,
  is FORMALLY UNTESTED (taxonomy §26), a portfolio gap, not a market finding.
  cloud_infrastructure_migration now shows one released buyer row and reads "covered".
  **Language already used for these two as "candidate divergences" in earlier write-ups
  and the Notion log is superseded by this characterisation.**
- **Reach values marked "unverified" on `Harness_Sources`** (SRC-0003, 0009, 0010, 0013,
  0017, 0027, 0033, 0034, 0038, 0039, 0040, 0041, 0044, 0045, 0046) are Code's
  classifications made while populating on 2026-09-05, not the advisor's. Each row's
  `notes` says so. Confirm before any finding rests on one; correcting a value is a hand
  edit the migration will not overwrite, followed by a new derivation.
- **`ot_modernization` is `theme_not_detectable` through 2026-W36** because its date
  (2026-09-02) is later than that week's Monday and the approved rule compares to bucket
  START. It becomes detectable in 2026-W37. Conservative by design; noted so the first
  history rows are not misread as a defect.
- ~~Stable/immutable OBSERVATION ids~~ **CLOSED 2026-09-06 (session 14 item 1, convention
  43).** `Observation_Ids` registry; a claim keeps its id across delete-and-rewrite, a
  retired id is never reused for another claim; 24 historical ids backfilled from git;
  check 10; `core/tests/test_stable_ids.py`. No existing id was renumbered.
- **An already-low-grade row judged `overgraded` has almost nowhere to go.** Convention 41
  admits corroboration-weak rows AT low grade (`source_grade C`, `weak_clue`), so when a
  reviewer downgrades one, `signal_strength` is already at the bottom of its ladder and
  `source_grade` is already at C because D is unwritable (convention 4). Hit on O00470
  (HITT, H-FIRSTPARTY-01 v1.2, 2026-09-03): only `organizational_state` and
  `confidence_0_1` could absorb it. The grading scheme may genuinely be unable to express
  "weaker than the weakest admissible row", and convention 32 would say such a claim
  should not exist rather than sit at the floor. An admission-rule question for a future
  version; not settled by that audit. Same wall as the Prime Inc. O00372 downgrade, now
  reached from the other direction.
- **`PLC` fires as an `ot_modernization` term on five H-FIRSTPARTY-01 v1.2 rows** (O00476
  Clayco, O00502 Leprino, O00434 EnergySolutions, O00492 Swinerton, O00452 Graham) and is
  lowercase in at least two, where in a press release it is more likely the British company
  suffix "...plc" than a programmable logic controller. Raised with the reviewer before the
  2026-09-03 audit; all five were affirmed `supported` without amendment, and each row's
  reviewer_notes records that the concern was raised and the verdict given anyway. Cheap to
  revise if the reading changes.

- **`audit_sample.py` prints `Matched terms | (none recorded)` on every H-SELLERCONTENT-01
  row** while the terms are present on the Evidence line. `matched_terms()` parses the
  `| matched: ...` shape H-FIRSTPARTY-01 writes and does not understand this harness's
  `matched terms: ...` excerpt format. A DISPLAY defect, not missing evidence: the v1.3
  census was judged from Evidence and the verdicts are sound. Deliberately NOT fixed under
  the live v1.3 audit -- changing the sampler while an audit is open makes any re-audit
  uninterpretable, the same bundling rule the quotes.py fix was held to. Logged 2026-09-03.
- **Prose/sheet mismatch on O00221 (Slalom, v1.3).** `session8_report.md` §3 says the row
  admits on "Cloud transformation"; the review sheet records `AWS, Cloud Migration,
  mainframe`. Matthew judged the sheet, and the verdict's reviewer note says so explicitly,
  so provenance is unambiguous. Which text is right is OPEN and was not resolved by the
  audit. The raw 2026-08-30 Slalom captures are on disk and can settle it.

- ~~8 pilot companies have no `website` value~~ **CLOSED 2026-08-31.** All 9 missing
  websites (the 8 pilots plus A024) were resolved by search and written back to
  `Companies` by `H-EXECID-01`, which scores the domain against company name tokens and
  refuses below a floor rather than guessing.
- `Companies.hq_state` format is inconsistent (bare codes for pilots, "City, ST" for
  Anvil) -- `core/resolution.py::state_code` handles both, but normalizing would be cleaner
- ~~`industry_primary` blank for all 100 Anvil companies~~ **68 populated 2026-09-06 (session
  15)** by `scripts/enrich_industry.py` from NAICS codes on OSHA inspections (54) and EPA ECHO
  facilities (14) that H-SAFETY-ENV-01 had already attributed to the company, modal sector at
  >= 60% share, never from a name; `Companies.industry_source` records each basis. Distribution:
  {'manufacturing': 5, 'logistics': 6, 'supply_chain_operations': 3, 'construction': 47, 'blank': 32, 'food': 3, 'energy': 1, 'trucking': 10, 'medical': 1}. Left blank: 29 with no attributed OSHA/ECHO/FMCSA record, 2 ambiguous (Penske
  Logistics trucking/logistics split, Crane Worldwide), 1 unmapped NAICS (NFI, 452910 retail),
  1 refused under convention 31 (Prime Inc., one record under a common-word name). Two written
  values are worth a second look: 4LIFE reads `construction` off a single ECHO facility code and
  J.R. Simplot reads `logistics` off farm-supply wholesale codes. `employee_count` and
  `revenue_estimate` remain blank.
- ~~OSHA truncates at 20 inspections/page, no working pagination~~ **MOSTLY CLOSED
  2026-08-31.** v1.1 concluded the source could not be paged; the parameters were right
  and the values were wrong. Following the server's own `p_direction=Next` link (rather
  than constructing `p_start`/`p_finish`) pages correctly. 13 companies capped at 20 are
  now 4 capped at 40 -- the cursor cycles after two pages, so 40 is a real remaining
  ceiling and those 4 are honestly marked `[CAPPED]` floors, not silently reported as
  exact.
- Venture Logistics' `employee_count` is still wrong (known since Week 1, unresolved)
- ~~**3 versions awaiting audit** (H-PRODUCTQUALITY-01 v1.2, H-LEGAL-01 v1.1,
  H-JOBPOST-01 v1.1).~~ **CLOSED 2026-09-05.** The first two were audited 2026-09-03;
  H-JOBPOST-01 v1.1's 3 remaining rows were released 2026-09-05 on the review queue.
- ~~`harness_output/audits/` is gitignored, so a fresh clone fails check 9~~ **CLOSED
  2026-09-01 (session 4 task B).** The directory is un-ignored and verified on a clone.
- 298 unreviewed observations -- deliberately not self-reviewed by the harness that
  produced them; waiting for Week 4's stratified human review. The 90 `buyer_articulates`
  rows are the highest-value stratum to review first: they are the newest, the least
  battle-tested, and the ones every convergence claim rests on.
- ~~`quotes.py` misclassifies the commonest attribution shape in American journalism~~
  **CLOSED 2026-09-01.** `"...," Broderick said.` -- name then verb, following the quote --
  now scores `explicit`. Both harnesses bumped to v1.2 and re-run. H-EXECVOICE-01: 8 rows
  unchanged in number, one confidence 0.65 -> 0.85. H-TRADEPRESS-01: 2 -> 3, the new row
  being the false refusal that found the bug (Gilbane's CEO on agentic AI). At an eponymous
  firm the person and the company are separable -- `"...," McGough said.` is explicit while
  `"...," McGough Construction said.` stays rejected. **Still open, logged not bundled:**
  proximity attribution ignores an intervening explicit attribution to someone else, so an
  executive named earlier in a page can pick up a later quote the article attributes to a
  different speaker. Pre-existing, verified identical before and after the fix.
- ~~H-TRADEPRESS-01's staleness window is 5 years while the project standard is 36 months~~
  **CLOSED 2026-09-03 (session 10, item 1): five years IS the standard**, `core/windows.py`,
  imported by both harnesses that enforce a window. Historical note follows.
- (historical) H-TRADEPRESS-01's staleness window was **5 years while the project standard was 36
  months**, so it is already more permissive than spec. Four of the 46 stale refusals sit
  within ~2 months of the line and two are the most on-theme articles in the bucket
  (Western Express / Platform Science fleet-wide; SpartanNash micro-fulfillment). Noticed
  only after looking at what sits on the far side of the line, which is exactly the
  condition under which a threshold must not move. **Deliberately unchanged 2026-09-01.**
  If revisited, it is decided on principle first and everything is re-run.
- `H-EXECVOICE-01` covers only 61 of 108 companies, because 47 have no identified
  executive. That is an `H-EXECID-01` coverage gap, not an `H-EXECVOICE-01` one, and the
  attempts record it as such. Raising exec coverage raises both.
- LinkedIn (taxonomy 15a, the highest-reliability source in the whole taxonomy) is
  unreachable without authentication and is not attempted by any harness.
- ~~Quarantined rows await review~~ **CLOSED 2026-09-05 (session 12.5): 0 quarantined,
  0 held conflicts.** 138 at the start of session 12; the 58-row queue
  (`REVIEW_QUEUE_2026-09-04.md`) and the 16-row queue (`REVIEW_QUEUE_2026-09-05.md`) were
  each judged row by row by Matthew, all supported, and both files are marked. All 188
  low-grade rows are released. The next harness run that writes or changes a row starts
  the cycle again.
- **A re-run now changes released, human-reviewed rows only by opt-in.** The FMCSA
  precedent (session 12.5): when a re-derivation differs from a reviewed row, the writer
  holds it; the decision to accept is Matthew's, executed through `--refresh-reviewed`,
  re-versioned and re-audited. Every row of H-FMCSA-01 is now human-reviewed, so any
  future FMCSA change will be a held conflict, never a silent update.
- ~~**Delete-and-rewrite renumbering**~~ **CLOSED 2026-09-06 by convention 43:** those
  harnesses still delete and reinsert unreviewed rows, but a reinserted claim now gets its
  own id back from the registry, so nothing renumbers.
- ~~**EXECID low-grade tier** (session 10 item 8)~~ **CLOSED 2026-09-06 (session 14 item 2):**
  H-EXECID-01 v1.1, see the harness table.
  `docs/diagnostics/gate_inventory_2026-09-03.md` lists the ~40 unclear gates and the
  deferred conversions (JOBPOST v1.4 scope, EXECID's title schema, three SAFETY-ENV items).
- **Buyer-side rows the new spine no longer supports, measured and left in place
  (2026-09-02):** H-FIRSTPARTY-01 O00286, O00288, O00339, O00347 (machine; bare
  "integration", "Lean on AI", bare "AI"), H-LEGAL-01 O00377 (released, overgraded).
  H-EXECVOICE-01 O00369 and O00373 were **resolved 2026-09-06**: Matthew accepted the
  harness's current values (both now low-grade at v1.5, published). Offline replays under the new spine:
  H-FIRSTPARTY-01 78 proposed vs 79 committed (3 new, 4 gone), H-EXECVOICE-01 6 vs 8,
  H-TRADEPRESS-01 3 vs 3 after the buyer-voice "AI" term. Re-running and re-auditing them
  under the new spine is a decision for Matthew; each becomes a new quarantined version.
- ~~H-SELLERCONTENT-01 v1.3's 7 rows need the human random-control judgment before v1.3 can
  publish~~ **CLOSED 2026-09-03** (7 of 7 supported, released by Matthew); v1.4's 13 rows
  followed on 2026-09-05. The 27 v1.2 rows that reproduced unchanged stay released.
- ~~32 stale `.bak-*` workbook copies in `data/`~~ **CLOSED 2026-09-02.** Deleted after
  their contents were recorded per file in `docs/archive/stale_workbook_copies_2026-09-02.md`.
  The four `--apply` scripts now back up through `core/workbook_backup.py`, which keeps the
  newest three. The 7 tracked copies in `data/archive/` stay tracked (they predate the first
  commit and two are inputs to `reconstruct_workbook.py`); `data/archive/README.md` says so.
- ~~The four `cybersecurity` observations still carry the old label in `observation_text`~~
  **CLOSED 2026-09-02 (session 7 follow-up).** Regenerated by
  `migrate_schema.py::relabel_observation_text` to what a re-run would write: label
  "cybersecurity", and the "no buyer-side harness can detect this theme" sentence dropped
  because THEME-08 has been buyer-detectable since 2026-08-31. `data/snapshots/gap_report.csv`
  is a **living file** (Matthew, 2026-09-02), refreshed the same day; regenerate it with
  `python scripts/gap_report.py --csv data/snapshots/gap_report.csv` after any spine change.
  The ignored run logs under `harness_output/` still carry `cybersecurity_ot` as dated artifacts.

## Documentation structure

- `CLAUDE.md` (this file) -- pure current state
- `DECISIONS.md` -- append-only history/rationale, not yet created
- `docs/conventions.md` -- locked conventions with their originating incidents, treat as
  authoritative
- `docs/archive/` -- superseded specs and docs
- Notion "Revision Log (Raw)" (separate system, not in this repo) -- session-by-session
  raw decision log across all three Claude Projects
