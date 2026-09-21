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

## Harnesses built (17)

| harness_id | What | Status |
|---|---|---|
| `H-FMCSA-01` v1.7 | Federal carrier registry | **Full universe 2026-09-01 (108).** 40 released observations, all released (v1.0 7, v1.3 4, v1.4 9 low-grade, v1.5 20); 8 resolve to a carrier. **v1.5's 20 rows are the pilot rows a person reviewed in Week 1-2, re-derived by the harness from the 2026-08-31 SAFER snapshot and accepted by Matthew on 2026-09-05 over the human values** (session 12.5 §2: snapshot date on all 20, counts moved on 8, no grade/strength/state/confidence changed). **v1.6 (2026-09-06): F15/F26 verified live with the QCMobile webkey** -- Midmark reads Private Property and its NOT AUTHORIZED status is explained as private carriage, Western Express and Kenco read Authorized For Hire, no false authority gap. Three fixes on that path (key read through `core.config`, national-average rates coerced from strings, "for hire" matched as both sources spell it). **The two field mappings were resolved 2026-09-15 (item 9) and the old note was half wrong.** Both fields ARE in the QCMobile record: entity type is `censusTypeId.censusTypeDesc`, and for-hire authority is `commonAuthorityStatus` / `contractAuthorityStatus` / `brokerAuthorityStatus` (A active, I inactive, absent never held). Authority had been derived from `allowedToOperate`, the USDOT registration status -- so the QCMobile path asserted AUTHORIZED for Midmark, which holds no for-hire authority and which SAFER reports NOT AUTHORIZED, collapsing the private-versus-for-hire distinction `_is_private_carriage` exists for. Fixed in `source.py`; `core/tests/test_fmcsa_qcmobile.py` (15 checks) pins it. **Measured live against the 8 committed carrier rows: `operating_authority_status` now agrees 8 of 8** (all four private-carriage registrants included). Two source differences REMAIN, not parse bugs: QCMobile's `censusTypeDesc` is single-valued where SAFER composes `CARRIER/SHIPPER`, `CARRIER/SHIPPER/BROKER` (4 of 8 differ; a pure broker, C0007, has no `censusTypeId` at all), and SAFER's AUTHORIZED FOR names the authority SCOPE where QCMobile names the KIND (4 of 8 differ). **So a live QCMobile run would still hold all 20 reviewed rows as conflicts; still not committed as a version and no row has changed.** **DECIDED 2026-09-16 (Matthew): hybrid. v1.7 BUILT, NOT COMMITTED AS A RUN.** SAFER is the authoritative record for every categorical and dated field (entity type, authority status and scope, classification, cargo, MCS-150, data date, crash window) and for the national-average OOS rates; QCMobile overlays only the carrier's own counts and rates, one extra fetch per carrier; QCMobile's sub-endpoint reads are dropped. **Measured live 2026-09-16 on the 8 resolving carriers: every overlaid field agreed exactly with SAFER.** National averages are NOT overlaid because **QCMobile serves a 2009-2010 benchmark (20.72 / 5.51) where SAFER serves the current one (22.26 / 6.67)** -- so the v1.6 QCMobile-only path measured carriers against a 16-year-old baseline. One overlay bug caught before commit: QCMobile rates are full-precision floats and would have printed `30.495969394726057` into row text; rounded to SAFER's one decimal before comparing. The overlay is skipped and logged on a QCMobile error, a USDOT mismatch, or (offline) responses from different dated partitions; a real disagreement is overlaid and logged (`source_disagreements`). **Live dry run (A024 + 8 pilots): `operating_model` text identical on all 8 reviewed rows** -- the vocabulary conflict is gone; **30 rows held**, every one two weeks of genuine data drift (as-of 08/31 -> 09/15, counts moved), i.e. the ordinary refresh decision under the session 12.5 precedent, not a v1.7 artefact. Nothing written. A full offline replay no longer works for an unrelated reason: Goodfellow's HQ correction (CA -> WA) changed its census query key, which was never archived; `--companies` replays of the pilots work. `core/tests/test_fmcsa_qcmobile.py` 28 checks. The code constant had read v1.6 while the manifest's current_version read v1.5; both now v1.7. **DECIDED AND RUN 2026-09-17 (Matthew): hybrid adopted, and the 30-row refresh accepted despite the two-week data gap because the national-averages fix alone justifies it. HR-0084, live, `--commit --refresh-reviewed`: 108 processed, 8 resolved, 39 observations -- 30 updated (every one a refreshed human-reviewed row, `review_status accepted` / `review_source human` preserved), 9 unchanged, 0 inserted, 0 held conflicts.** All 8 carriers read `safer+qcmobile` with **no QCMobile error, no skipped overlay and no source disagreement**. The 30 rows now carry v1.7 and are **QUARANTINED pending audit**; FMCSA released rows 40 -> 10, and v1.5 keeps its artifact while its rows have moved -- the population-drift pattern documented 2026-09-17. Audit sample drawn: `H-FMCSA-01__v1.7__review.md`, a CENSUS of all 30 (strata off_own_domain 30, a_graded 23, single_common_word 5; the other four empty, recorded as such). **AUDITED AND PUBLISHED 2026-09-17**: Matthew reviewed all 30 manually and judged every one `supported`; recorded row by row through `apply_audit_verdict` (review_source human) while still quarantined, then released with the version through `set_version_publication`, which moves `Harness_Runs.publication_status` and `Observations.publication_state` together and refuses without a passing artifact. Census artifact `H-FMCSA-01__v1.7.json` -- 30 of 30 supported, precision 100% exact (a census, not extrapolated), exclusions 0 against the 0.10 threshold, stop rule untriggered; the four empty strata recorded with `sampled_n` 0 and their selection rule. All 40 FMCSA rows released again. **Still no coverage percentage for this harness, and that is correct** -- see the reliability appendix |
| `H-JOBPOST-01` v1.4 | Job postings: own-domain careers pages (Workday, iCIMS, Paylocity, Greenhouse, Lever, **ADP**, inline lists) + the **Talent.com aggregator leg** | **Full universe live 2026-09-03 (108), twice.** Own-domain **17/108** readable (was 13; ADP 3 companies + OnTrac's inline list), 10 companies `access_blocked` because their Dayforce/UltiPro board hosts refuse this crawler by robots.txt; aggregator reaches 53 companies with ≥1 resolved cross-post (shallow). **All 53 rows released** (v1.1 3, v1.3 13, v1.4 16 released 2026-09-05 on Matthew's approval; v1.0/v1.2 21 earlier). PRESENCE ONLY still binds |
| `H-SELLERCONTENT-01` v1.4 | Seller/provider service pages, 4 archetypes | **Week 2's named deliverable.** 44 released in the workbook: v1.2 24 and v1.3 7 (both audited) and v1.4 13 (10 low-grade, released 2026-09-05 on Matthew's approval) |
| `H-SAFETY-ENV-01` v1.3 | OSHA + EPA ECHO merge | Full universe, 131 observations, **all released**: 67 at v1.0/v1.1 (grandfathered) and 64 refreshed to v1.3 by the ECHO paging fix (facility counts were silently capped at 100; Teichert 149) and the declared OSHA floors, **released 2026-09-04 on Matthew's standing authorization with no row individually judged** (artifact `H-SAFETY-ENV-01__v1.3.json` says so; its precision rate is undefined, not 100%) |
| `H-WAYBACK-01` v1.3 | Removed-page detection | Full universe, 31 released observations, all released (v1.3's 5 **confound-admitted** replatform rows and v1.2's 7 low-grade single-capture rows both released 2026-09-05 after individual review) |
| `H-EXECID-01` v1.1 | Executive identification (**prerequisite**, writes `Company_Executives`) | 931 execs in `Company_Executives`. **v1.1 (2026-09-06): the low-grade tier** -- an out-of-vocabulary title admitted as written (E26) or a name with no adjacent title on a leadership-class page (E32) writes `role_relevance unconfirmed`, grade C, confidence 0.3 / 0.25, a `[low-grade:` marker in `name_variants`; `db.sync_executives` accepts an empty title only on such a row; never primary, so EXECVOICE does not read them. v1.1 committed 2026-09-06 as HR-0064: 117 inserted (110 low-grade, 7 confirmed), 21 refreshed, 781 unchanged, 9 superseded (departures from re-read leadership pages); the tier needed three guards found on the first dry run (a name may not carry a role or domain word, an E26 title must be role-shaped, and a low-grade record must sit within 8 lines of a confirmed person) before its sample was clean. |
| `H-EXECVOICE-01` v1.7 | Executive candor -- attributable quotes in third-party coverage | 8 released observations, 56% coverage (47 companies blocked on no identified exec); v1.5 tightened the page identity test to FIRSTPARTY's all-token rule. **v1.5 published 2026-09-06** with O00369 / O00373 refreshed to the harness's current values by Matthew's decision (both now low-grade: generic-term only under the two-tier spine) via `--refresh-reviewed --refresh-ids`; O00372 stays held at v1.2 (corrected, not part of the decision). **v1.6 (session 15, Matthew's decision): also searches up to 4 EXECID low-grade (`unconfirmed`-role) names per company after the 2 primary; quotes graded by the unchanged rules, provenance stated in the text. Live 2026-09-06: HR-0065: 76 low-grade names searched across 30 companies (362 searches, 597 fetches); 2 new rows, both the same Brian Killinger appointment quote reprinted by two outlets, grade B / weak_clue under the normal rules, quarantined (sheet drawn); Coastal Cares produced nothing. O00372 still held.** |
| `H-EMPREVIEW-01` v1.1 | Employee review aggregate (family 4) | **Access finding, re-confirmed live 2026-09-06 (HR-0059): 107 of 108 `access_blocked`** -- Glassdoor, Indeed and CareerBliss refuse this crawler by robots.txt, Comparably trips the circuit breaker. HR-0058 the same morning is an offline replay whose failure categories are cache artifacts (`source_unavailable`), superseded by HR-0059 in meaning though not in status. Nothing has changed at the source |
| `H-TRADEPRESS-01` v1.8 | Vertical trade press: five signal types incl. **ST-PRESSCHAR** (the company describing itself, as reported) | **v1.8 (2026-09-15, item 9; code only, not run): the end-of-article marker fixed -- `editor.s picks` never matched Construction Dive's "Editors' picks", and since v1.7 (commit 15f7c18) the pattern held literal backspace bytes where `\b` was meant, so "Filed Under" and "More from" never matched either. An offline replay of v1.8 proposes exactly what the unfixed code proposes (13 proposals; no live row changes). Hold LIFTED the same day on Matthew's instruction.** 5 released observations before session 14, 15-company subset (v1.0, v1.2 audited; v1.5's 2 low-grade rows released 2026-09-05). **Live run 2026-09-06 on the seeded subset with the 10-host allowlist expansion: HR-0061, 15 companies, 5 rows proposed, 4 unchanged, 1 human-reviewed row held, 0 inserted. The added outlets reached 4 articles (Trucking Dive, Grocery Dive, AndNowUKnow, Food Logistics) and none was admissible, so the expansion has measured zero yield live.** **v1.6 (session 15): scope is every buyer with a `Companies.industry_primary` value, the SUBSET now an override -- 79 of 108 searchable** (64 from the NAICS enrichment + 15 seeded); 29 with no attributed record are still not searched. Live 2026-09-06 (HR-0066): 71 of the 79 searched before Brave's monthly quota ran out (HTTP 402; the last 8 recorded source_unavailable / transient), 9 new rows from 5 newly unlocked construction companies (5 low-grade, 3 grade B, one quote whose text names another company's CIO), judged 2026-09-06: 8 supported, O00604 unsupported and deleted (restored 2026-09-15 as a quarantined row recorded `invalidated_extraction_defect`, convention 45) (a Construction Dive sidebar teaser swept into the Q&A's last answer -- `article_body` now ends at the first end-of-article marker line, v1.7); the 8 released under the 0.15 under-20 threshold Matthew set the same day. O00376 held. **Session 15.5 (2026-09-06, $10 of Brave credit added): the 8 companies the quota interrupted (A097, A099, A100, C0002, C0003, C0005, C0007, C0008) were searched live as HR-0067 under v1.7 -- 41 articles read, nothing admissible, 8 `absent_confirmed`. The full 79-company scope has now been searched once; the harness has never written a row outside the seeded 15 plus the 5 companies HR-0066 covered.** |
| `H-PRODUCTQUALITY-01` v1.4 | Federal recall / adverse-event records, IC4 | 3 released observations, full universe. v1.1 and v1.2 audited and released; v1.4: 2 low-grade rows (split-sentence cue; the bare "manufacturing defect" symptom cue is admitted at low grade too), released 2026-09-05. Firm-name test now applies LEGAL's token-prefix rule against the seeded aliases |
| `H-FIRSTPARTY-01` v1.2 | Press releases, PR wires, business/trade journals | 230 released observations, **7 of them recorded invalid** (O00302, O00303, O00339, O00441, O00484, O00491, O00529: theme match on page furniture, judged `unsupported` by Matthew 2026-09-15, hard-deleted that day and restored exactly the same day under the retroactive no-hard-deletion rule, each `invalidated_extraction_defect`; v1.1's 61 live rows at 97% coverage; v1.2's **169 rows, 152 low-grade**, released 2026-09-03 on a 30-row sample -- the single-term rows v1.1 cut, readmitted under convention 41). **`--retire-stale` added 2026-09-15 (Matthew; opt-in, not yet used, no version bump), converted the same day to record rather than remove (convention 45):** records `invalidated_not_reproduced` only for machine rows the run no longer produces from a page it re-read this run; human-reviewed rows are held and named; refused with `--companies`/`--limit`. **v1.3 BUILT 2026-09-15, NOT RUN (the harness is held):** identity, themes, state and quotes are read from the article body only (`harnesses/h_firstparty_01/body.py`), with all five extraction prerequisites fixed and verified on the 111 pages the rows came from (`core/tests/test_firstparty_body.py`, 46 checks; fixtures `core/tests/fixtures/firstparty_pages/`, 2.7 MB gzipped, scripts removed exactly as the extractor's first step). Offline dry run of HR-0041's cache (`docs/diagnostics/firstparty_v13_dryrun_2026-09-15.md`): 113 proposals -- 79 unchanged, 31 content changed, 3 new -- and 119 live rows no longer produced: all 10 already recorded `invalidated_extraction_defect`, plus 94 machine and 15 human-reviewed rows, almost all because the theme is not in the article body; O00307's bullet recovered. **HOLD LIFTED and v1.3 RUN 2026-09-15 (item 22, Matthew): HR-0083, an offline replay of the same cache with `--commit --retire-stale`, QUARANTINED pending audit** -- 110 proposals (3 inserted, 27 refreshed, 78 unchanged, 1 held, 1 re-proposed row left as recorded invalid); 30 rows now carry v1.3 and are quarantined; **97 machine rows recorded `invalidated_extraction_defect`** (the status names the reason, by Matthew's instruction: `core/validity.py::invalidate_unreproduced` takes the status and basis); **18 human-reviewed rows HELD, not invalidated**; 11 companies moved `covered` -> `absent_confirmed` (40/65 in HR-0083 against 50/55 in HR-0041), coverage 97.2% unchanged but not published while quarantined. **Audit sample DRAWN 2026-09-15 (evening): `H-FIRSTPARTY-01__v1.3__review.md`, a CENSUS of all 30 rows** (population 30, so the random control is the whole run and its precision rate will be exact, not extrapolated); strata off_own_domain 24, a_graded 15, eponymous_name 4, suppressed_judged 4, polysemous_term 1. O00307, the press-release bullet the fix recovered, is row 1. **AUDITED AND PUBLISHED 2026-09-20**: Matthew reviewed every row manually and judged all 30 `supported`; recorded through `apply_audit_verdict` while still quarantined, then released with the version. Census artifact `H-FIRSTPARTY-01__v1.3.json` -- 30 of 30 supported, precision 100% exact, exclusions 0 against the 0.10 threshold, stop rule untriggered. **Published coverage now quotes v1.3: 105 of 108, 97.2%.** The 97 rows the fix stopped producing keep their ids and their dated determinations -- this audit judges the 30 it produces, not the 97 it does not |
| `H-BREACHPORTAL-01` v1.2 | State AG breach-notification portals (California DOJ, Washington AG), **IC4, `cybersecurity` only** | **Built and run 2026-09-06 (session 16, HR-0068): the portfolio's first licensed-absence instrument for a modernization theme.** All 108 searched for presence under the all-token identity rule; 8 companies headquartered in CA/WA are in scope for absence (Goodfellow Bros added by Matthew's ruling, HR-0069 v1.1): **7 `absent_confirmed`** (Lease Crutcher Lewis, Swinerton, Hathaway Dinwiddie, Devcon, Lynden, Teichert, Goodfellow), 1 covered (BNBuilders, listed in both states). 9 released rows (Whiting-Turner, Estes, C.R. England x2, doTERRA, OnTrac x2 via a dba clause, BNBuilders x2) after Matthew's review: 9 supported, one Estes duplicate excluded and deleted (v1.1 dedupes CA hits; O00612 restored 2026-09-15 as a quarantined row recorded `invalidated_duplicate` of O00611, convention 45). **Both versions published 2026-09-06; DR-0002 composes the seven as `absence_licensed_IC4` in 2026-W36.** Out of scope tonight: Texas (connection timeout at the network), Maryland (JS-rendered), Vermont and Montana (robots), Massachusetts and New Hampshire (403), Iowa and Indiana (PDF year lists). **v1.2 (2026-09-15, HQ correction, no code change, HR-0082, population 0, PUBLISHED 2026-09-15 on Matthew's instruction under the zero-row precedent, artifact `H-BREACHPORTAL-01__v1.2.json` -- precision undefined, not 100%; gate verified both directions): Goodfellow Bros is headquartered in Wenatchee, WA, not CA -- session 16's CA value rested on an EPA facility record. The Washington AG list (1,869 notifications, read live) holds no listing, so its scoped absence stands on the correct portal. HR-0069 (v1.1), with its stale California basis recorded in its `known_issues`, was SUPERSEDED 2026-09-15 on Matthew's instruction (item 11; it holds no observations, so check 9 accepts the disposition, and its audit artifact is kept as the record of that audit). Measured: no derived row, gap-report count or published coverage figure moved.** |
| `H-PROCUREMENT-01` v1.4 | Federal award records (USASpending): prime contracts + IDVs (family 7), grants + loans/guarantees/insurance (family 2), IC3 | **Built, run live and published 2026-09-13 (session 17, HR-0070).** 35 released rows for 33 companies (random control 30 of 35, all supported by Matthew; 5 released with the version). 157 `absent_confirmed`, 24 `not_covered` same-state near-misses awaiting human aliases (W. W. Clyde & Co., M. A. Mortenson Company, W. G. Yates & Sons, Walbridge Aldinger, Leprino Foods Dairy Products, Goodfellow Bros. California, ...). Identity: exact-token names, HQ-state corroboration, SAM parent-UEI family counted once with subsidiaries named, JVs and professional practices excluded; counts are floors. The company is the SELLER, so no theme is routed and it **cannot license a `systems_integration` absence** (session17_report.md §1). ST-0011 / ST-0012. **v1.1 (2026-09-14, alias resolution from source records): three identity paths, none rescuing a JV or professional practice, all state-gated -- an exact source-record alias form, a SAM parent on the near-miss's own recipient record that passes identity, and an ANCHOR check (the company's own registered entity holds no award in the window -> name-only near-misses without a UEI are cleared; UEI-bearing ones keep blocking). Re-run on the 12 near-miss companies (HR-0076, HR-0077): 5 rows **published 2026-09-14 on Matthew's census review (5 of 5 supported; the same-city aliases affirmed)**, artifact `H-PROCUREMENT-01__v1.1.json` -- Mortenson (alias M. A. MORTENSON COMPANY; 38 contracts + 12 IDVs, $1.82B), Walbridge and Yates (SAM parent links), Clyde (W. W. CLYDE & CO.) and Leprino (LEPRINO FOODS DAIRY PRODUCTS COMPANY, 85 USDA awards) on the same-HQ-city alias standard; Layton a clean absence (its registered entity holds none); Goodfellow and Austin Industries unresolved.** **v1.2 (2026-09-14, Matthew's rulings, HR-0078, population 0, published): CAJUN GROWERS INC and ANDERSON ENGINEERING OF MINNESOTA, LLC seeded as `not_variants`, so Cajun and Anderson Trucking are clean absences (their registered entities hold no award); and no registered entity in the HQ state clears name-only near-misses when every identity-passing registered entity elsewhere holds no award -- Graham Construction is a clean absence (GRAHAM CONSTRUCTION SERVICES, INC., MN, parent GRAHAM GROUP LTD, no award). Herzog Enterprises is REFERRED BACK: HERZOG GROUP INC. (CA, its own parent) holds 1 contract + 1 IDV, so the ruling's premise of no registered entity does not hold and HERZOG MOTOR SPORTS still blocks.** **v1.3 (2026-09-15, Matthew's identity calls, HR-0079, population 0, published): a `not_variants` name is excluded from the registered-entity search too. HERZOG GROUP INC. (Compton, CA) confirmed unrelated -> Herzog Enterprises a clean absence; Austin Industries' six UEI near-misses confirmed other firms and its 0-award absence accepted -> clean absence (logged reason reads 'no registered entity' because AUSTIN INDUSTRIES INC DELAWARE CORPORATION fails the exact-token name test). Of the 12 v1.0 near-misses only Goodfellow Bros remains unresolved (see Known data gaps).** **v1.4 (2026-09-15, HQ correction, no code change, HR-0081): Goodfellow Bros `hq_state` corrected CA -> WA (Wenatchee). GOODFELLOW BROS, LLC (UEI CLAXYN5FDP93, Wenatchee WA) passes identity in the HQ state: 3 contracts + 1 IDV, $2.8M; GOODFELLOW BROS. CALIFORNIA, LLC (Livermore) is now an out-of-state near-miss. 1 row (O00791), census sheet `H-PROCUREMENT-01__v1.4__review.md`, **judged 2026-09-15 by Matthew: supported (recorded through `apply_audit_verdict`, review_source human), and PUBLISHED the same day on his instruction (item 10): census artifact `H-PROCUREMENT-01__v1.4.json` (1 of 1 supported, pass), HR-0081 published, O00791 released; published coverage now quotes v1.4 (HR-0081, 2 of 2 scoped, 100%).** All 12 v1.0 near-misses are now resolved.** |
| `H-LOCALRECORDS-01` v1.2 | Fragmented public records, ONE harness with four sub-scopes sharing one access layer: state WARN notices (TX, UT, CA; IC4, family 3), city building permits (Chicago, Seattle, Austin Socrata; IC3, family 8), Seattle Legistar council matter titles (IC3, family 16), homepage technology markers from H-EXECID-01's archive (IC3, family 5) | **Built, run live and published 2026-09-13 (session 17, HR-0072): 127 released rows** (94 techstack, 31 permits, 2 WARN, 0 council); random control 30 of 127, all supported by Matthew; 97 released with the version. Permits place the buyers as CONTRACTOR (seller direction, like procurement); owner-role hits counted, not written. One-distinctive-token names need an exact operating-name form (canonical, SAM-verified from H-PROCUREMENT-01, or alias): the first read found bare WALSH, a Walsh plumber, a Wilmette MORTENSON CONSTRUCTION, an Elgin Yates and a council appointee named Mortenson, all refused now; stated cost Clayco Construction (Austin) and McShane Construction Company refused until aliased. **v1.1 (2026-09-14): an exact form of a verified legal name or source-record alias is accepted BEFORE name_matches (which refused Seattle's "MA Mortenson Company" for its initials). HR-0075: McShane 4 Chicago permits (alias McShane Construction Company, permit address Rosemont = HQ), Mortenson 54 Chicago permits (new) and Seattle 2 -> 3 (O00704, re-quarantined); 3 rows **published 2026-09-14 on Matthew's census review (3 of 3 supported)**, artifact `H-LOCALRECORDS-01__v1.1.json`. Clayco Construction stays refused (Austin contractor address Hutto, TX; no SAM record); Clayco not committed, its Chicago row would change only the window date.** **v1.2 (2026-09-15): a `not_variants` name is refused first as `confirmed_different_entity`; the Austin/Hutto CLAYCO CONSTRUCTION (small residential contractor, no SAM record) is a confirmed non-match by Matthew's call, not a pending alias. No accepted name changes, so no row changes and no run.** Out of scope, measured: MO WARN (Incapsula), MN WARN (perfdrive), WA WARN link gone, CA WARN before 2026-07-01 (PDFs), Chicago/SLC not on Legistar, Utah open-data domain decommissioned. No theme routed. ST-0013..ST-0016, SRC-0052 |
| `H-SEC8K-01` v1.1 | Form 8-K Item 1.05 material cybersecurity incidents (EDGAR submissions, IC4, `cybersecurity`), scoped from `SEC_Reporting_Status_History` | **Built and run 2026-09-13 (session 17 wrap-up, HR-0073), QUARANTINED, population 0.** Scope DERIVED as the current active reporters (Merit Medical, SpartanNash, Co-Diagnostics): 94 8-Ks since the rule took effect (2023-12-18), none with Item 1.05, so 3 `absent_confirmed`. Exact item-code matching from EDGAR's structured item list. Listed in `core/composition.py` as an IC4 cybersecurity instrument; reads nothing until audited and published. SpartanNash's Form 25-NSE (2025-09-22) and 15-12G (2025-10-02) were recorded 2026-09-14 on Matthew's decision as a superseding `deregistered` row (SRS-0014, `scripts/record_sec_status.py`), so the derived scope is now 2 (Merit Medical, Co-Diagnostics). **v1.1 (2026-09-15, scope correction, no code change): HR-0080 on the derived 2 (Co-Diagnostics 33 8-Ks, Merit Medical 32 since 2023-12-18; none with Item 1.05; 2 `absent_confirmed`), committed under the v1.0 label and relabeled v1.1 by Matthew's decision, audited (population 0) and PUBLISHED, artifact `H-SEC8K-01__v1.1.json`. v1.0 is never published: HR-0073, the stale 3-company scope with SpartanNash, stays permanently quarantined.** Near-zero yield is the documented consequence of the population's reporting-status mix. Requests declare `SEC_CONTACT_EMAIL` (.env). ST-0017 |
| `H-LEGAL-01` v1.2 | Federal court dockets (CourtListener) **+ NLRB case search**, IC4 | 1 observation (O00377, audited overgraded, released); NLRB 124 cases across 36 companies and 0 observations by design. v1.2 (2026-09-03) wrote nothing new |
| `H-VENDOR-01` v1.2 | Vendor and partner disclosure (family 6, §24): vendor-published customer pages seeded from EXECVOICE's excluded URLs | **v1.1 run live and published 2026-09-13 (session 17, HR-0071), population 0, documented as a bounded absence.** v1.0's zero was checked page by page and was NOT an absence (two name-test defects, one wrong entity -- the UK GRAHAM story -- one client-rendered page, one non-vendor page); fixed with core/tests/test_vendor.py. Denominator: 27 distinct seeds, 13 excluded before reading, 14 usable for 12 companies; 2 pages read (Joeris: genuine absence; SpawGlass: absence bounded by the in-sentence naming rule, two team passages with theme terms logged for decision), 8 not about the company, 2 identity_uncorroborated (UK GRAHAM; Melaleuca at stated cost), 1 retrieval gap (PENTA), 1 robots (CT Logistics), 1 fetch 403 (FCL). Artifact `H-VENDOR-01__v1.1.json`. v1.0 runs HR-0061..63 stay quarantined. IC1; not a theme instrument, so its silence licenses nothing **v1.2 (session 17 wrap-up, Matthew's design): an unnamed deployment sentence is attributed to the company only when the page TITLE names it and the sentence comes from the body with nav/header/footer/aside removed; a line break at a block element is a sentence boundary, an inline link is not. Live HR-0074: SpawGlass/Ardoq now yields 2 low-grade attributed rows (systems_integration on 'They leveraged the Microsoft Entra ID integration'; data_analytics_ai on 'using Ardoq's AI capabilities to generate process maps'), **published 2026-09-14 on Matthew's census review (2 of 2 supported)**, artifact `H-VENDOR-01__v1.2.json`; every other page outcome identical to v1.1. Two regressions caught before commit and fixed with tests: a heading fused with the next paragraph, and an inline link cutting the Entra sentence.** |

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

**Superseded 2026-09-13 (session 17): both attributions above were wrong.** USASpending was never blocked by the network: its own web application firewall refused the probe's User-Agent (`IndStudyResearchBot`) on the token `ResearchBot`, answering inside a TLS session verified to Treasury's certificate; the harness UA gets HTTP 200 from the same egress IP, which is also the IP of the 09-01 "different network" probe. PatentsView was retired by USPTO on 2026-03-20 and moved to the Open Data Portal (the host is NXDOMAIN on Cloudflare DoH too). The session 16 Texas timeout does not reproduce and is not the same cause. `scripts/probe_sources.py` fixed; convention 38 amended. `H-PROCUREMENT-01` is built (table above). `H-PATENTS-01` needs a new source decision (ODP bulk data), not an access fix.

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
on 2026-08-31 it was 185 / 87 / 43, and as of 2026-09-15 it is **425 / 250 / 44**
(`buyer_acts` / `buyer_articulates` / `provider_market_responds`, computed from the workbook
after the retroactive restoration of 2026-09-15 -- every row counted, including the 10 recorded invalid
(O00303 among the `buyer_acts`); `check_run_ledger.py` does not check these).
The 2026-08-31 figure stayed on this line for two weeks and was taken for the current
`buyer_articulates` count on 2026-09-15; recount from the workbook before quoting it. Both
buyer-articulation instruments are built and committed.

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

**All 10** themes in `core/topics.py` are `buyer_detectable = True` (verified in code
2026-09-17; the last of them, `ot_modernization` / THEME-10, was split out of THEME-08 on
2026-09-02 and this line read "nine of the 10" until then) — `H-FIRSTPARTY-01`
classifies free-text announcements through the same spine, so it can see any theme, and
leaving three flags False made `gap_report.py` print "NO INSTRUMENT" beside a non-zero
buyer count. **This is not equal footing and the per-theme notes say so:** an announcement
is a *biased* instrument, so absence there means "not announced", which is weaker than
"not happening" and weaker than the absence of a job posting.

**CORRECTED 2026-09-17 by the theme evidence matrix** (`docs/analysis/theme_evidence_matrix_2026-09-20.md`;
the sentences this replaces said `ot_modernization` had no instrument on either side and that cloud
migration and cybersecurity had zero buyer signal — both written before the evidence that changed
them):

- **`ot_modernization` IS instrumented on both sides: 8 valid buyer-side rows** (all
  `buyer_articulates`, 7 of them low-grade, across 7 companies — H-FIRSTPARTY-01 7,
  H-TRADEPRESS-01 1) **and 1 provider row** (H-SELLERCONTENT-01). It is reached by the
  all-scope announcement and executive instruments like every other theme. What remains true
  is narrower: **no instrument LICENSES its absence** — every instrument seeing it is IC1, IC2
  or presence-only IC3 — so its silence still licenses nothing.
- **`cybersecurity` (THEME-08; key `cybersecurity` since the 2026-09-02 rename from
  `cybersecurity_ot`, declared in `RETIRED_THEME_KEYS`) is no longer a zero-buyer theme and is
  no longer formally untested.** It holds **12 valid buyer-side rows** — 9 breach notifications
  (`buyer_acts`, grade A, H-BREACHPORTAL-01) and 3 first-party mentions (`buyer_articulates`,
  grade C) across 9 companies — plus 4 provider rows. It is the **only** theme with a licensing
  instrument (`state_ag_breach_notice` and `sec_8k_item_105_cybersecurity`, both IC4), and the
  derivation composes **9 companies as a licensed absence**. So it is a MIXED case: real
  evidence for some companies and a real confirmed absence for others, not a blanket silence.
- **`cloud_infrastructure_migration` has 3 valid buyer-side rows** (2 `buyer_articulates`,
  1 `buyer_acts`, 3 companies) and 4 provider rows, so it too is no longer zero-buyer. It still
  has no licensing instrument, so its absence licenses nothing and `gap_report.py` prints **"no
  absence instrument"** rather than "buyer silent" for it — which is the rule that survives for
  every theme except `cybersecurity`.

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

## Evidence base snapshot (as of 2026-09-15)

**722 observations** (of which **210 low-grade**; every observation ever deleted whose claim has no other live row is restored -- the seven 2026-09-15 page-furniture rows, O00604, O00612 and O00564 -- and **112 carry a current validity determination** (122 determinations, 10 superseded): 98 `invalidated_extraction_defect`, 10 `invalidated_wrong_entity`, 3 `invalidated_not_reproduced`, 1 `invalidated_duplicate`), 108 companies with evidence, **6,972 attempts
logged**, 84 harness runs, 6,480 rows in `Company_State_History` (DR-0001 and DR-0002, both appended 2026-09-06), **931 executives** in `Company_Executives` (821 confirmed across 63 companies, 110 low-grade `unconfirmed` from EXECID v1.1).
242 observations human-reviewed, 480 unreviewed (2026-09-15, after HR-0083). 33 signal types registered. **6,972 attempts, 84 runs** (HR-0084 wrote none -- see the H-FMCSA-01 attempts gap below).
**719 released, 3 quarantined** (2026-09-20, after H-FIRSTPARTY-01 v1.3 was audited and published: **every valid row is now released**, and the only quarantined rows left are the 3 restored rows that are themselves recorded invalid. Was 716/3 as of 2026-09-15, after H-PROCUREMENT-01 v1.4's release -- 11 of the 716 are released AND invalidated, because publication_state is walled off from validity. Quarantined: O00564 (H-EXECVOICE-01 v1.4), O00604 (H-TRADEPRESS-01 v1.6) and O00612 (H-BREACHPORTAL-01 v1.0), each restored in the quarantined state it was deleted in and recorded invalid; O00791 (H-PROCUREMENT-01 v1.4) released 2026-09-15; H-BREACHPORTAL-01 v1.2, HR-0082, population 0, published the same day; H-SEC8K-01 v1.0's HR-0073, which wrote no row, stays permanently quarantined). 10 themes (THEME-01..10) in `core/topics.py`; one theme
key retired so far (`cybersecurity_ot` -> `cybersecurity`, 2026-09-02, four machine rows
rewritten by `migrate_schema.py::rename_topic_keys`).

Observations as three measurements (2026-09-20, after the Front Line wrong-entity ruling): 722 total = 610 valid + 112 invalid; released 719 = 610 valid + 109 invalid; quarantined 3 = 0 valid + 3 invalid (`python scripts/published_coverage.py` prints the same line).

By harness (released rows, 2026-09-15 after HR-0083, computed from the workbook; invalid in brackets, valid = total minus invalid): H-FIRSTPARTY-01 203 [108], H-SAFETY-ENV-01 131, H-LOCALRECORDS-01 129, H-SELLERCONTENT-01 44, H-PROCUREMENT-01 41, H-FMCSA-01 40, H-JOBPOST-01 32, H-WAYBACK-01 31, H-TRADEPRESS-01 13, H-EXECVOICE-01 10, H-BREACHPORTAL-01 9, H-PRODUCTQUALITY-01 3, H-VENDOR-01 2, H-LEGAL-01 1. Quarantined: H-FIRSTPARTY-01 30 (v1.3), H-EXECVOICE-01 1, H-TRADEPRESS-01 1, H-BREACHPORTAL-01 1.

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
assigned, 742 ids of which 23 retired -- every one a pre-rule renumbering whose claim is live under a newer id, which
its row records in `current_id` (item 20, 2026-09-15; blank on live ids);
every insert consults it; since convention 45 nothing retires an id, and check 15 fails on a retired id whose
claim has no row; check 10 keeps it in step with the live sheet). `Harness_Sources` now carries reach on all rows (`nominal_reach`, `realized_reach`,
months, `realized_reach_effective_from` = the harness's first run date); provenance per row
is in its `notes` (taxonomy §21.2, the 2026-09-02 ping, or "Code 2026-09-05, unverified").

**`SEC_Reporting_Status_History`** (session 17 wrap-up, Harness Advisor design, final): the design's table `Company_SEC_Reporting_Status_History`, on a workbook tab named `SEC_Reporting_Status_History` because Excel caps sheet names at 31 characters and the design name is 36 (`core/sec_status.py` keeps both names). Columns `id`, `company_id`, `sec_reporting_status`, `source_filing_type`, `source_reference`, `as_of_date` (what the evidence establishes), `determined_at` (load date), `determined_by`, `superseded_by` (forward pointer only), `notes`; 8-value vocabulary at Lookups!AC. Append-only through `core/db.py::append_sec_status`: a status change is a new row plus `superseded_by` on the old one, an unchanged status or identical row is a no-op, an older finding cannot supersede a newer one. `entity_unresolved` (identity doubt: no status asserted) and `status_uncertain` (status doubt about a CIK-confirmed filer) are enforced as different things. Seeded with exactly 13 rows for 12 companies (`scripts/load_sec_reporting_status.py`), plus later dated determinations in `scripts/record_sec_status.py` (SRS-0014, SpartanNash `deregistered`, 2026-09-14); the other 96 buyers have NO row -- `never_registered` is written only after an actual check. **There is no `Companies.public_private` column, now or later:** "currently a reporter" is derived (`sec_status.active_reporters`), and check 12 fails on any such column.

**`Observation_Directionality_Tags`** (build handoff 2026-09-15, Signal Advisor, finalized): `observation_id`, `evidence_directionality` (`buyer_side` / `seller_side` / `mixed` / `not_applicable`, Lookups!AD), `tagged_at` (load date), `tagging_run_id`, `notes` (required for `mixed` and for any `backfill_` batch). Optional and sparse, across every `evidence_role`; corrects nothing. Writer `core/directionality.py::append_tags` (all-or-nothing, identical tag a no-op, never overwrites). **Convention 44, the standing pattern:** any optional, non-blocking classification of an observation lives in its own linked table, never a column on `Observations`. **Convention 41 wall, check 13:** no gate-computing module may name the table or import `core.directionality` -- a FAILURE, verified in both directions. **70 tags, all `seller_side`**, batch `backfill_evidence_directionality_2026-09-15` (restated by Signal Advisor after the 162-row batch was escalated): every `federal_prime_contracts` and `municipal_permits_as_contractor` row. **Re-run 2026-09-15 at 37 + 33 (Matthew, item 7):** H-PROCUREMENT-01 v1.4 published O00791 hours after the restatement, so the reconciliation guard refused the whole batch rather than writing part of it; the count is now 37 with the reason in the script's docstring, the guard still refuses anything else, and the original 69 tags were matched and left exactly as written (1 appended, 69 no-op). Same `tagged_at`, same run id: the batch is defined by the finding's rule, not by a snapshot. The other 100 rows of those two harnesses (4 assistance awards, 94 techstack, 2 WARN) are deliberately untagged -- an absent tag is the table's default state, not a gap. Rows those harnesses write from now on are not tagged automatically.

**`Observation_Role_Reviews`** (Matthew Lebrecht, 2026-09-15; option A of the buyer_articulates role-review report; convention 44, the directionality table's shape): one row per ROLE-classification verdict -- `observation_id`, `role_at_review`, `role_verdict` (`correct` / `buyer_acts` / `buyer_articulates` / `provider_market_responds` / `other` / `cant_tell`, Lookups!AE, `correct` confirming the reviewed role), `review_scope` (`role_only`), `reviewer`, `review_source` (`human`), `reviewed_at`, `review_run_id`, the numeric sample basis (`sample_design`, `sample_n`, `population_n`, `stratum`, `stratum_sampled_n`, `stratum_population_n`), `reviewer_words`, `artifact` (the committed verdicts JSON the run must agree with) and `notes`. **A role verdict re-clears neither identity nor extraction and is never written to `Observations`:** `review_source`, `review_status` and `audit_verdict` stay as they were (verified cell for cell against HEAD on the first load). Writer `core/role_review.py::append_reviews` (all-or-nothing, a run written only complete, identical row a no-op, never overwrites); loader `scripts/load_role_review.py`, which builds every row from the artifact and refuses to save if `Observations` changed. **Check 14** (FAILURES): the convention 41 wall (no gate module names the table or imports the module); every row role-only, stating in its notes that it re-clears neither identity nor extraction, human-sourced, a verdict other than the reviewed role, the reviewer's words on any non-`correct` verdict, a coherent numeric sample basis; every run exactly `sample_n` rows with each stratum holding exactly the rows it claims and the strata partitioning sample and population; every run agreeing row for row, both directions, with its artifact. A reviewed row whose `evidence_role` later changes is a warning. **First run `role_review_buyer_articulates_2026-09-15`: 59 rows, 58 `correct`, 1 `buyer_acts` (O00303, "mark that as buyer did"); O00303 then reclassified to `buyer_acts` by Matthew's decision (`core/db.py::apply_role_correction`), so check 14 WARNS on it by design (the table keeps the role as reviewed); the H-FIRSTPARTY-01 change was declined. Later the same day seven of the 59 reviewed rows, O00303 among them, were deleted as `unsupported` (page furniture); check 14 warns on all seven ("no live row") and still reconciles to the verdicts artifact. O00303 was then restored under the no-hard-deletion rule, and the other six the same day, so check 14 now warns on one: O00303 "reviewed as buyer_articulates, now buyer_acts" (its role correction came back with it). A role verdict of `correct` on a row later recorded invalid is not a contradiction: the review asked about role only.**

**`Observation_Validity_History`** (Matthew Lebrecht, 2026-09-15, standing rule: **no observation, from any harness, is ever hard-deleted again**): `id` (OVH-NNNN), `observation_id`, `validity_status` (Lookups!AF, additive-only: `invalidated_extraction_defect`, `invalidated_not_reproduced` -- what retirement became, `invalidated_duplicate`, `invalidated_wrong_entity`), `as_of_date`, `determined_at`, `determined_by`, `basis`, `superseded_by`, `notes`. Append-only like `SEC_Reporting_Status_History`: one row per determination, nothing updated but the forward pointer `superseded_by`, one current determination per observation, and a determined observation must keep its row. Writer `core/validity.py::append_determinations` (all-or-nothing); pre-rule deletions come back through `core/db.py::restore_observation` (exact snapshot, own id, original sheet position, registry id back to live with its retirement fields cleared -- the registry keeps no history, so the restoration record carries it). **Check 15** (FAILURES): the convention 41 wall; malformed rows; broken history; a determination on an observation with no row; a derivation citing a never-assigned id; **a HARD DELETION -- any retired registry id whose claim has no live row (`validity.hard_deletions`)**; and `delete_rows(` anywhere in `core/db.py`. Both enforcement failures tamper-probed. WARNINGS: derivations citing deleted (retired) or invalidated observations. **Every delete path now refuses** (`delete_observations`, `delete_observation_ids`, `delete_by_reviewer_verdict`, `retire_unreproduced`, each raising with convention 45); **retirement is invalidation**: `core/db.py::unreproduced_observations` only reports, and `core/validity.py::invalidate_unreproduced` records `invalidated_not_reproduced` for machine rows a run no longer proposes within its company scope (human rows held, an already-invalid row left as it is, basis stable per harness version). EXECVOICE, LEGAL, PRODUCTQUALITY and TRADEPRESS on `--commit`, FMCSA on `--force-rewrite`, and FIRSTPARTY/SELLERCONTENT `--retire-stale` call it after syncing -- none has been run since; unlike delete-and-rewrite, a `--companies` subset commit no longer touches rows of companies outside the subset. **Determinations: OVH-0001 O00303 (batch `o00303-2026-09-15`, record `VALIDITY_2026-09-15_O00303.json`); OVH-0002..0010, batch `retroactive-2026-09-15`, record `VALIDITY_2026-09-15_retroactive.json`: the six other furniture rows (`invalidated_extraction_defect`, snapshots guarded against `b21a24c`), O00604 (`invalidated_extraction_defect`, from `f563dcd`), O00612 (`invalidated_duplicate` of O00611, from `769d6e2`), O00564 (`invalidated_not_reproduced`, from `f0411b1`)** -- each guarded equal to its source commit and absent from its removing commit, restored to its original sheet position, every other Observations row unchanged; **OVH-0011: O00349 `invalidated_wrong_entity`** (item 5, Matthew 2026-09-15: "O00349: wrong_entity confirmed"; batch `o00349-wrong-entity-2026-09-15`, the script's `live` source -- a determination on a row that exists, guarded to match the row the verdict names, with every Observations row unchanged; record `VALIDITY_2026-09-15_O00349.json`); **OVH-0012..0014: O00539, O00542, O00544 `invalidated_extraction_defect`** (item 7, Matthew 2026-09-15: the Caddell cookie-banner rows are removed, i.e. recorded invalid; batch `caddell-cookie-banner-2026-09-15`, `live` source; record `VALIDITY_2026-09-15_caddell_cookie_banner.json`) -- each row's single matched term, "analytics", occurs only in the site's GDPR Cookie Consent banner, after the page's copyright line. **O00539 was one of the 30 rows of the H-FIRSTPARTY-01 v1.2 random control, judged `supported` on 2026-09-03**; that artifact (29 of 30 supported) is a historical record and is not rewritten. Company_State_History cites 92 invalidated observations in 294 citations after HR-0083 (check 15 warns; DR-0001 and DR-0002 are immutable history and are not re-derived). **O00349 moved one derived value on a dry derivation:** A073 `data_analytics_ai` W35/W36 stays observed but rests on O00350 alone, so its organizational_state reads `unknown` instead of O00349's `target_state` -- and O00350 is itself a Front Line Power Construction release, under item 6 review (sheet section added, no verdict yet). No coverage rate and no gap-report count moved. **Item 7 moved three published numbers:** a dry derivation reads A076 `data_analytics_ai` W35/W36 as null `no_absence_license` instead of observed (observed buckets 243 -> 241), because the three cookie-banner rows were its only evidence; the gap report's low-grade-only buyers for `data_analytics_ai` 6 -> 5; and with low-grade counted, `data_analytics_ai` buyers 42 valid -> 41 valid + 1 invalid-only (A076). No coverage rate moved. **Not restorable: the 23 renumbered ids** -- their claims are live under newer ids, so a restored row would give one claim two live ids; check 15 counts them as acknowledged. **Their lineage is recorded (Matthew, item 20, 2026-09-15):** `Observation_Ids.current_id` on each retired row holds the live id its claim now carries (SELLERCONTENT O00224..O00257 -> O00403..O00412, EXECVOICE O00277..O00284 -> O00368..O00375, LEGAL O00367 -> O00377, TRADEPRESS O00565/O00566 -> O00591/O00592, PRODUCTQUALITY O00567/O00568 -> O00593/O00594), written by `scripts/record_id_lineage.py` (refuses on a hard deletion, a forked claim or a disagreeing value; idempotent), record `ID_LINEAGE_2026-09-15.json`; check 15 FAILS on a retired id whose current_id is not its claim's live id and on a live id carrying one; an id that comes back to live (re-assignment or restore) drops it. The registry's `retired_at` on all 23 reads 2026-09-06, the session 14 backfill date, not the date each renumbering happened. **A determination is permanent** (Matthew, item 21): `invalidated_not_reproduced` does not lapse if a later run reproduces the claim, and there is no reinstating status. **Consumers read an invalid row AS invalid, and report three measurements** (Matthew, item 19, 2026-09-15): `core/composition.py` excludes it from every bucket and writes `evidence: N total, V valid, I invalid (excluded as recorded invalid: ...)` in the bucket's `notes`, with evidence citations summarised the same way; `scripts/published_coverage.py` prints observation counts as total/valid/invalid and, beside each attempt-based rate (which validity cannot move), `cov-inv` (covered attempts resting only on invalid rows) and the rate without them; the reconciler (`core/db.py::sync_observations`) counts a re-proposed invalid row under `invalid` and leaves it exactly as recorded -- neither refreshed nor held -- and its run summary reads `N proposed = V valid (...) + I recorded invalid`; `scripts/gap_report.py` counts companies on valid rows and prints total and invalid-only beside them. **The convention 41 wall is amended, not removed:** those three gate modules read validity only through `core/validity.py::invalid_observation_ids` (the reconciler only inside `sync_observations`), every other gate module still may not, and validity still feeds no review_status, audit_verdict, publication_state or reprocessing_required -- `validity.wall_violations`, check 15, tamper-probed in `core/tests/test_validity_consumers.py`. **Measured before the change, on 2026-09-15:** no published coverage rate moved and no covered attempt rests only on invalid rows; the default gap-report table did not move; the low-grade-only buyer count for `ot_modernization` went 14 -> 13 (A073, O00529); a dry derivation keeps every status (243 observed, 15 licensed absences) and six buckets (A015, A046, A051 `data_analytics_ai`, W35/W36) rest on fewer rows (evidence 4 -> 1, 2 -> 1, 2 -> 1; state and confidence unchanged). DR-0001/DR-0002 are immutable and were not re-derived; no DR-0003 appended. **Audit artifacts are historical records, never rewritten:** `H-BREACHPORTAL-01__v1.0` (population 10 incl. O00612), `H-TRADEPRESS-01__v1.6` (9 incl. O00604) and the FIRSTPARTY v1.2 / EXECVOICE v1.4 strata files record what was true on their audit dates; live numbers are recomputed by the scripts, which read artifacts only for whether a version was audited. **The v1.3 run (HR-0083, item 22) added 97 determinations**, all `invalidated_extraction_defect`, all `determined_by` "H-FIRSTPARTY-01 v1.3 (machine run, not a reviewer)": `core/validity.py::invalidate_unreproduced` takes `status` and `basis`, so a caller that knows the reason records it rather than writing `invalidated_not_reproduced` and relabelling afterwards (a named status must carry a basis). **CLOSED 2026-09-17 (Matthew): the 8 were superseded** -- batch `hr0083-overstated-2026-09-17`, record `VALIDITY_2026-09-17_hr0083_overstated.json`, OVH-0112..0119 superseding OVH-0017/0018/0051/0038/0039/0042/0031/0032. Read against the cached pages, they were two OPPOSITE errors, not one: **six are `invalidated_wrong_entity`** -- the article never names the company (Lio funding round: 'National Product Sales' 0 times; JDM/Penta Technologies: 'PENTA Building' 0 times though 'Penta' 18; ESS Tech: 'ESS Companies' 0 times though 'ESS' 72) -- and **two are `invalidated_not_reproduced`**, the McCarthy rows, which were correct when written and crossed the five-year line on 2026-09-08, seven days before HR-0083 (1,832 days old). The rows stay invalid and unchanged; only the recorded reason moved. Current determinations: 100 `invalidated_extraction_defect`, 7 `invalidated_wrong_entity`, 3 `invalidated_not_reproduced`, 1 `invalidated_duplicate` (119 rows, 111 current). Matthew chose `invalidated_not_reproduced` over adding an `invalidated_stale` status. Diagnosis `docs/diagnostics/hr0083_overstated_statuses_2026-09-17.md`. (historical: as run, 8 of the 97 were not lost to extraction) -- O00297, O00298, O00354, O00355 and O00431 to the body-based identity test ('SALES', 'BUILDING' absent near the top of the body), O00324 and O00325 to staleness (their article crossed the five-year line after the dry run), O00359 to theme admission -- and their matched terms are still in the article body, so the status overstates the reason. Superseding them with a more accurate determination, and whether the vocabulary needs a status for identity or staleness, is Matthew's decision; `core/tests/test_firstparty_body.py` section 9 pins the exception set so it cannot grow unnoticed.

Repo structure: `core/` is the sole writer, with shared utilities (entity resolution,
attempt-run-context, topic classification). Harnesses are packages with `manifest.yaml`
structured version history.

Four mechanical checks, and they answer different questions:

| Script | Question |
|---|---|
| `scripts/validate_repo_db.py` | do the repo and the database agree? 15 checks: the audit gate (9), the observation-id registry (10), the coherence-framework walls (11), the SEC reporting-status history and the no-`public_private`-column rule (12), the evidence-directionality wall and tag integrity (13), the role-review wall, row and run rules and artifact agreement (14), the observation-validity wall as amended by item 19 (only composition, published coverage and the reconciler read validity, through one accessor), history integrity, derivation citations and no hard deletion (15) |
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

## Findings carried forward for Week 4 synthesis

- **App-store presence is a real instrument for exactly one segment, and it measures something
  different everywhere else.** Feasibility probe 2026-09-15 over all 108
  (`docs/diagnostics/appstore_feasibility_2026-09-15.md`, `scripts/probe_appstore.py`; a probe, not a
  harness -- no workbook row written). **25 of 108 companies have a confirmed app footprint (59 apps),
  but only 5 publish anything a consumer uses.** All four direct-sales consumer-goods firms have one
  (doTERRA 7, Melaleuca 6, Scentsy 2, 4Life 1) and they are the only companies in the population
  shipping consumer COMMERCE apps; SpartanNash adds 13 through its grocery banners, six of which --
  all its pharmacy apps -- have not been updated since 2023-02-23 while the grocery banners were
  updated in August 2026, a dated abandonment pattern visible inside one portfolio. The other 20
  confirmed companies publish **workforce tooling** (driver, field-safety, supply-chain), which is a
  different signal and must not share a key with the consumer one. Identity is the whole difficulty:
  the probe's first pass accepted name matches and reproduced this project's characteristic failure
  three times in one run (a fitness club under a different "Walsh Group", a Marietta seafood
  restaurant under "Cajun Inc", an email client under "The NFI Group LLC"); publisher-domain
  corroboration refuses those, refuses Mack Trucks for Mack Group, and rescues `Prime Mobile` under
  Prime Inc.'s legal name New Prime Inc. **Google Play is the better leg if this is ever scoped**:
  robots.txt permits `/store/search`, the app ids are in the server-rendered HTML with no JavaScript,
  and the package namespace (`com.doterra.shop`, `com.scentsy.home.prod`) is stronger identity than
  Apple's. PRESENCE ONLY -- a store search index is a discovery surface, not a registry, so it
  licenses no absence.

- **YouTube channel presence: probed 2026-09-16, not worth an instrument**
  (`docs/diagnostics/youtube_feasibility_2026-09-16.md`, `scripts/probe_youtube.py`; a probe, no
  workbook row). robots.txt closes `/results`, `/youtubei/` and captions, so discovery reads the
  company's OWN archived homepage for a channel link and then checks the channel names the company.
  **58 of 108 have a confirmed channel**, 45 posting within a year; one site linked a WordPress
  plugin's channel (Wadsworth, *Slider Revolution*) and was refused. Not a duplicate of EXECVOICE --
  19 of the 58 are companies EXECVOICE cannot reach, and a company channel is first-party, not
  third-party coverage. But **1,457 titles and 60 full descriptions carried no buyer-side
  modernization statement**: 8 title theme matches were 1 false positive (a transit project named
  "Red-Purple Modernization") and 7 companies describing services they sell; descriptions matched
  nothing even at low grade. Content is recruiting, projects, safety, community. LinkedIn, X and Meta
  were not probed (settled out).
- **Patents / IP is a portfolio gap with no near-term instrument path.** PatentsView is dead at the source: USPTO retired the PatentSearch API on 2026-03-20 and moved PatentsView to the Open Data Portal (`search.patentsview.org` is NXDOMAIN on Cloudflare DoH as well as locally; the legacy hosts redirect to the ODP transition guide). This is not an access problem to fix; `H-PATENTS-01` would need a new source decision (ODP bulk data), and until then family 14 has no instrument and its silence is formally untested.
- **Buyers appear as the SELLER, not the commissioning buyer, in two independent public-record families.** `H-PROCUREMENT-01` (federal prime awards: the company delivers work to an agency; the only buyer-side leg, subawards under its own primes, was empty where measured) and `H-LOCALRECORDS-01` (city building permits: Walsh 665 general-contractor roles to 12 misfiled owner roles in Chicago; Seattle and Austin name only the contractor) found the same structural pattern without sharing code. For a construction-heavy universe, public procurement and permit records describe what these firms build for others, not what they commission for themselves -- so neither can license a buyer-side theme absence, and neither routes to a theme. A finding about which record families can see buyer behaviour at all, not a defect in either harness.

## Known data gaps

- **H-FMCSA-01 emits NO attempts and never has -- LOGGED AS A DOCUMENTED LIMITATION, NOT TO BE
  RETROFITTED** (Matthew, 2026-09-17; `docs/report_appendix_reliability.md` §1). It is the only one
  of 17 harnesses that writes no `Attempts` rows, in any of its ten runs, and does not use the
  `core/attempts.py` run-context. Consequences, all long-standing: `published_coverage.py` reports it
  as `scoped 0 / n/a`, so **the carrier registry has never contributed a coverage percentage and none
  should be quoted for it**; and because `core/composition.py` licenses buckets from attempts, it
  licenses no absence whatever it observes. Its 40 observations are unaffected -- all released, all
  human-reviewed. The appendix wording: *"H-FMCSA-01 predates the attempts-based coverage convention
  and reports population facts outside that system."* 8 of 108 resolve to a carrier because the other
  100 are mostly not motor carriers, so a percentage over 108 would describe the population, not the
  instrument. Retrofitting would change what the harness declares, not what it reads; deliberately not
  done this close to the deadline.

- **Grandfathered exemptions describe populations that have since moved; the structural hole is
  CLOSED (2026-09-17)** (`docs/diagnostics/grandfathered_and_composition_exposure_2026-09-17.md`).
  Measured against the workbook committed on the exemption date: **7 of the 18 pairs lost rows, 1
  gained rows, 10 now hold none**. Every departed row either moved to a newer version (these
  harnesses rewrite rows under the version that last wrote them) or is one of the 23 pre-rule
  renumberings -- nothing was lost. **No coverage number is affected**: published coverage quotes
  only each harness's latest published version, and the one grandfathered version it quotes
  (H-EXECID-01 v1.0) never changed. The real hole was that **a version is not a closed set** --
  H-FMCSA-01 v1.3 gained 4 rows from HR-0034/HR-0037 the day after its exemption, which would have
  inherited it. **check 9 now honours an exemption only for versions whose published runs all
  predate its `date_added`** (`core/audit.py::grandfathered_added_on`); it fails nothing today
  (that version already has its artifact) and is tamper-probed both ways in
  `core/tests/test_audit_gate.py` (60 checks). Still open, not mechanical: the `reason` texts of the
  7 moved pairs are now inaccurate as descriptions of today, and **H-FIRSTPARTY-01 v1.1 keeps 42
  rows of which 27 are recorded invalid**.

- **The coherence pilot cannot return a result, and the blocker is not the missing writer**
  (2026-09-15 evening, `docs/diagnostics/coherence_pilot_execution_2026-09-15.md`).
  `Observation_Coherence_Tags` holds **0 rows and there is no `core/coherence.py`** -- the only
  overlay table in the project without a writer. The hypothesis is stated in COH-F while the table
  accepts only COH-D, so reaching families means tagging dimensions and joining through
  `Coherence_Family_Dimensions` at synthesis, a procedure never written down. And the cohort does not
  survive the determinations: of 38 released `systems_integration` rows **6 are invalid**, C0002 Mack
  Group has 3 of which 2 are invalid, so the over-firing cohort is **3 companies on released rows and
  2 on valid rows**. At that size the 60% threshold resolves to 2-of-3 or 2-of-2 and one tagging
  judgment on one company decides it. COHP-0001 has also drifted -- it names A019 as A048's
  comparison; the script now derives A032. Tagging the 66 cohort observations is not worth it until
  the cohort is bigger. **The four decisions listed in that diagnostic were CLOSED AS MOOT 2026-09-20
  (Matthew): the disposition was finalised without them** -- framework built and scoped, evidence
  volume insufficient to execute, written up in the report appendix -- so they are not pending a
  ruling and are kept only as the record of what executing the pilot would have required.
- **H-PRODUCTQUALITY-01's coverage rate is the length of its population map, not a measurement**
  (2026-09-15 evening, `docs/diagnostics/productquality_attempts_control_2026-09-15.md`). Its
  denominator is the 15-company hand-seeded map, not 108, and its yield is 3 of 15. `coverage_rate`
  is **0.1389 and 15/108 = 0.13889**; the four earlier runs read 0.1204 with 13 in the map. It moves
  only when a company is added to the map. No observation-side control can reach the **12
  `absent_confirmed`** (the instrument's only real claims) or the **93 population decisions** --
  the control must sample `Attempts` and ask two different questions with different verdicts. The
  map's justification comment ("`industry_primary` is blank for all 100 Anvil rows") is stale since
  session 15, but the map must NOT be rebuilt from that field: 4LIFE reads `construction`, Simplot
  and SpartanNash read `logistics`, Scentsy / Co-Diagnostics / doTERRA are blank, so a rebuilt map
  would drop four of the five companies the instrument exists for. Cross-checked, exactly one company
  is product-making by `industry_primary` and absent from the map: **A027 Petersen Inc.**

- ~~`evidence_directionality` backfill escalated~~ **CLOSED 2026-09-15:** the batch was restated to the rows the cited findings cover and written; **70 tags** after the same-day re-run at 37 prime-contract rows (O00791, PROCUREMENT v1.4). A row of a covered kind written after a batch is NOT tagged automatically -- the guard refuses and the batch is re-run deliberately.
- **`Companies.hq_city` added 2026-09-15** (Matthew): 99 of 108 filled by `scripts/populate_hq_city.py` from what `hq_state` already says; 8 blank (the pilots' bare state codes). **Goodfellow Bros CLOSED 2026-09-15:** `hq_state` corrected CA -> WA and `hq_city` Wenatchee by Matthew's decision (`scripts/correct_company_hq.py`, which refuses unless the sheet still holds the value being replaced and appends the reason to `notes`); the CA value had rested on an EPA facility record. Systematic check the same day: the only `hq_state` change since the workbook's first commit, the only company whose notes cite an EPA facility, and no code writes `hq_state` -- isolated, not a pattern. Crane Worldwide ("Houston") and doTERRA ("Pleasant Grove") carry a city in `hq_state`; `hq_city` took it, `hq_state` left as is.
- **8-K Item 1.05: built on the Harness Advisor's reporting-status design (session 17 wrap-up).** `SEC_Reporting_Status_History` seeded; `H-SEC8K-01` scoped to the derived active reporters (2 since SpartanNash's deregistration; v1.1 published 2026-09-15), 0 Item 1.05 filings. ~~SpartanNash status~~ **CLOSED 2026-09-14:** superseding `deregistered` row as of 2025-10-02 (Form 15-12G), SRS-0014 supersedes SRS-0002; `active_reporters` 3 -> 2. Also a deviation to confirm: the workbook tab is `SEC_Reporting_Status_History` (Excel's 31-character limit), not the design's 36-character name.
- ~~`Theme.absence_licensed` stale~~ **CLOSED 2026-09-06 (session 14 item 0b).** The flag
  is gone; `gap_report.py` reads `core/composition.py::absence_licensing`. **Since session 16
  one theme has a licensed-absence instrument: `cybersecurity`, through H-BREACHPORTAL-01
  (IC4), for the 7 companies headquartered in California or Washington.** The gap report
  prints "buyer silent (7 of 108 under a licensed instrument)" for it -- the §20.5
  structural-coverage denominator, never a bare "buyer silent". Every other theme still has
  none, so for them nothing prints "buyer silent".
  **CORRECTED 2026-09-17 (theme evidence matrix): `cybersecurity` is NOT formally untested and is
  not a zero-buyer theme.** It carries 12 valid buyer-side rows across 9 companies (9 of them
  grade-A breach notifications from H-BREACHPORTAL-01 itself) alongside 9 companies composed as a
  licensed absence — evidence and confirmed absence at once, which is a market finding for those
  companies rather than a portfolio gap. The gap report reads `covered (10 of 108 under a licensed
  instrument)` for it. `cloud_infrastructure_migration` now shows 3 released buyer rows across 3
  companies and reads "covered".
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
  43).** `Observation_Ids` registry; a claim keeps its id, a retired id is never reused for
  another claim (and since convention 45 nothing deletes); 24 historical ids backfilled from git;
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
- ~~`audit_sample.py` silently truncated review material~~ **CLOSED 2026-09-15.** Claim,
  Evidence and Reviewer notes were cut at 900 characters on the review sheet and every field
  at 600 in the strata file, with no marker. On the H-PROCUREMENT-01 v1.0 sheet O00632 (1,135
  chars) lost its joint-venture exclusion and page-cap floor caveat before it was judged
  (the verdict stands; session17_report.md recorded it as display-only). All four caps
  removed, none retained. Regression (convention 37): re-drawing H-PROCUREMENT-01 v1.4 and
  v1.0 reproduced the same row ids in the same order in every stratum; the only text changes
  are fields that grew past the old caps (O00632's Claim 900 -> 1,135; 54 strata fields past
  600, each HEAD value an exact prefix), besides recorded-verdict fields that reflect the
  workbook. The committed judged sheets were left as drawn.
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
- 475 unreviewed observations (2026-09-15) -- deliberately not self-reviewed by the
  harness that produced them. The 249 `buyer_articulates` rows are the highest-value
  stratum: the ones every convergence claim rests on. **A ROLE-classification review of
  them was drawn 2026-09-15** (is `buyer_articulates` the right role -- not identity or
  extraction, both already audited): 59 of 249, proportional by harness with a floor of 5
  (FIRSTPARTY 45 split by channel 26 PR wire / 11 own newsroom / 8 business journal;
  EXECVOICE 5 of 10; TRADEPRESS all 9 across its three signal types), every field
  untruncated, seed 20260915. `harness_output/audits/ROLE_REVIEW_buyer_articulates_2026-09-15.md`
  and `_allocation.json`, drawn by `scripts/role_review_sheet.py`. **Judged by Matthew
  2026-09-15: 58 `correct`, 1 `buyer_acts` (O00303, business journal, "mark that as buyer
  did")**, recorded in `Observation_Role_Reviews` and `_verdicts.json`, not on the rows.
  Unweighted 1 of 59; stratified estimate ~5 of 249 (2.1%), joint 95% upper bound 61 of 249.
  **SUPERSEDED 2026-09-15 (evening, item 12): that estimate no longer rests on any valid row.**
  Drawn again from the base after HR-0083, the business-journal stratum is 41 rows, of which **34
  carry a validity determination and 7 do not** -- and **all 7 rows judged in the first review are
  among the invalidated**, O00303 (the single miss) included. So the 12.5% rate and the 18-of-42
  bound were computed entirely on rows now recorded invalid and must not be quoted again without
  saying so. The remaining review population is the **7 valid rows** (5 released, 2 quarantined at
  v1.3), drawn as a CENSUS in
  `harness_output/audits/ROLE_REVIEW_business_journal_census_2026-09-15.md` -- unjudged, verdicts are
  human-only. `scripts/role_review_sheet.py` gained `--sub-kind-contains`, `--exclude-invalid`,
  `--exclude-reviewed` and `--stem` so a second pass is drawn from the current base; every filter and
  the ids it dropped are printed on the sheet.
  (historical) Business journal 1 of 8 of 42 (12.5%), 95% upper bound 18 of 42 -- up to 17 of its 34
  unreviewed rows; own newsroom <= 12 of 58, PR wire <= 12 of 130, EXECVOICE <= 3 of 10,
  TRADEPRESS exact 0. The miss sits where H-FIRSTPARTY-01's "the company is the author"
  rationale for `buyer_articulates` does not hold (a journalist wrote it). **Decided
  2026-09-15: O00303 reclassified to `buyer_acts`; the H-FIRSTPARTY-01 change declined**, so
  the business-journal stratum's classification behaviour is unchanged by design and the
  bound above still describes its unreviewed rows.
- ~~**O00303 is a PERMANENT held conflict, by design (2026-09-15).**~~ **SUPERSEDED the same day: O00303
  was deleted, then restored and recorded `invalidated_extraction_defect` (OVH-0001) -- a human-authored row
  recorded invalid, so since item 19 the reconciler counts its re-proposal as invalid and leaves it as recorded
  rather than holding it as a conflict** -- on Matthew's `unsupported` verdict (its theme match was page furniture) through
  `core/db.py::delete_by_reviewer_verdict`; the conflict is gone (simulated next run: 0 held, 1 inserted --
  see the page-furniture deletions entry below). History as recorded: Matthew reclassified it
  `buyer_articulates` -> `buyer_acts` in place (`core/db.py::apply_role_correction`:
  `review_source = human`, `review_status = corrected`, dated stamp in `reviewer_notes`;
  `audit_verdict`, text and family untouched; not a new version) and declined the harness
  change. H-FIRSTPARTY-01 writes `buyer_articulates` on every row, so every run that re-derives
  this claim proposes the old role, the reconciler HOLDS the human-authored row, and the run's
  dedupe line counts it under "held for review" -- on every run, indefinitely. Expected, not a
  regression. A run that stops finding the article cannot delete it either (held). **Text
  corrected the same day** (Matthew: "Yes correct the text"; `core/db.py::apply_text_correction`,
  only the two articulation phrases changed): it now reads "was reported acting, in an article
  matched by term to data platforms, analytics and AI ... a journalist's report of what the
  company did -- the theme match not re-assessed". `evidence_family` stays 1 (the source is a
  business journal, taxonomy 1c; a family classifies the source, not the role). **Still open:**
  whether the article ("Adolfson & Peterson starts 2 Texas high school projects") bears on that
  theme at all -- an extraction question the correction deliberately does not close.
- **H-FIRSTPARTY-01 role handling: Matthew wants a fix (2026-09-15), options reported, nothing
  built.** The harness hard-codes `buyer_articulates`; none of its classification-time signals
  (channel, first named quote on the page, page-level state cue) separates O00303 from the seven
  business-journal rows judged `correct`.
- **Seven H-FIRSTPARTY-01 rows deleted as `unsupported` (Matthew Lebrecht, 2026-09-15: "Oh yeah agreed they're
  all unsupported and should be removed").** O00302, O00303, O00339, O00441, O00484, O00491, O00529: each row's
  only theme match on its cached page was furniture outside the article (Construction Dive "Editors' picks"
  teasers, the "An Informa PLC company" footer, ENR's "Ask ENR AI" link). Sheet
  `REVIEW_QUEUE_2026-09-15_firstparty_page_furniture.md` (verdicts marked); record with the deleted rows whole
  `DELETIONS_2026-09-15_firstparty_page_furniture.json`. Deleted through the new
  `core/db.py::delete_by_reviewer_verdict` (the only path that may delete a human-reviewed row, and only as the
  reviewer's own `unsupported`/`wrong_entity` verdict); the same commit made `delete_observation_ids` all-or-nothing
  -- it used to delete bottom-up and raise mid-batch, removing five of these rows before refusing on O00303 in a
  simulation. **All seven restored the same day and recorded invalid (convention 45, retroactive); the deleting path
  itself now refuses.** Consequences: (1) the rows exist again, so an unchanged H-FIRSTPARTY-01 run no longer
  re-inserts them -- it counts all seven as recorded invalid and leaves them as recorded (item 19); v1.3 ran on
  2026-09-15 (HR-0083) and does not produce any of them;
  the hold on FIRSTPARTY and TRADEPRESS stands until the extraction fix lands; (2) the 12 Company_State_History rows
  (DR-0001/DR-0002, 2026-W35/W36; A015, A046, A051) now cite rows that exist and are flagged invalid, which check 15
  warns on; (3) O00349 (Power Construction, same Bechtel/Kiewit article as O00529): Matthew confirmed `wrong_entity`
  2026-09-15, recorded OVH-0011. **A second Power Construction identity case CLOSED 2026-09-20:** the three
  rows citing the Front Line Power Construction press release (O00530, and O00350 / O00531 whose
  extraction-defect status was superseded) are all `invalidated_wrong_entity` -- the release is about a
  Houston utility contractor, and A073's name matched only as a SUBSTRING of it. Batch
  `front-line-2026-09-20`, OVH-0120..0122. A073 is now the company whose name has produced two separate
  wrong-entity cases, both from its two dictionary words.
- **NO HARNESS IS HELD (2026-09-15). Both holds set that day were lifted the same day by Matthew Lebrecht:**
  H-TRADEPRESS-01 once its v1.8 marker fix replayed with no live-row change (item 9), H-FIRSTPARTY-01 once v1.3 read
  themes from the article body and its dry run was measured (item 22), after which v1.3 was run and committed
  (HR-0083). `core/holds.py` keeps the mechanism and the history; re-holding a harness is an entry there and nothing
  else (`core/tests/test_holds.py` exercises it against a synthetic hold). `core/holds.py` is checked first in each harness's `main`: every live run and every `--commit` (offline
  too -- an offline replay of FIRSTPARTY's cache re-inserts the deleted claims) exits with the reason, the date and
  the lift conditions. Still allowed: `--offline` without `--commit`, a dry replay that writes nothing to the
  workbook. FIRSTPARTY lifts when all five extraction prerequisites land and are verified on the 111 cached pages
  (list items as prose; footer phrases only after article prose begins, with a minimum-body fallback; consent
  banners excluded; the end-marker pattern matching "Editors' picks"; the article boundary found before chrome is
  stripped) and a dry run of the fixed extractor is measured. TRADEPRESS was held as a precaution pending its own
  offline dry run; that run showed its rows did not rest on furniture, and the hold was lifted with v1.8. Lifting = removing the entry in a reviewed commit; there is no bypass flag. **2026-09-15 (item 8):
  FIRSTPARTY's lift conditions are now met in substance -- the five prerequisites are built into v1.3 and verified on
  the 111 pages, and the offline dry run is measured (`docs/diagnostics/firstparty_v13_dryrun_2026-09-15.md`) -- but
  the hold is NOT lifted: that is Matthew's reviewed decision, and a run would record ~94 machine rows invalid.**
- **No hard deletion (Matthew Lebrecht, 2026-09-15; convention 45, retroactive) -- enforced.** Every delete path
  refuses; retirement is `invalidated_not_reproduced`; every deleted observation whose claim had no live row is
  restored and recorded (10 determinations at adoption; 14 after items 5 and 7); check 15 fails on a hard deletion. **Decided by Matthew 2026-09-15:**
  (19) composition, published coverage and the reconciler read invalid rows as invalid, and every published count
  reports total, valid and invalid -- BUILT (see `Observation_Validity_History` above); (20) record the current id of
  each of the 23 renumbered ids -- BUILT (`Observation_Ids.current_id`); (21) a determination is permanent, no reinstating status.
- **Composition reads every published attempt with no de-duplication, no preference for
  the newer run, and no provenance on the derived row. MEASURED 2026-09-17: the de-duplication half
  has not fired and cannot, as the code stands; the provenance half is real and deferred to Week 5**
  (`docs/diagnostics/grandfathered_and_composition_exposure_2026-09-17.md`). 251 of 321
  (company, signal) keys carry attempts from more than one published run and 21 disagree on outcome,
  but `covered` and `absent_confirmed` both license coverage and reach is a property of the HARNESS,
  not the run -- so **re-deriving the whole history with the attempt list reversed changes 0 of 5,400
  derived rows on every field**. `Company_State_History` holds 6,480 rows with zero duplicate
  (derivation, company, theme, bucket) keys. What is real is provenance: 1,608 buckets carry
  `covering_instruments` and none names the run, version or source that licensed it (observed buckets
  do carry `supporting_observation_ids`). The Goodfellow case was corrected only because a human
  SUPERSEDED HR-0069 -- verified: its stale California attempt is now invisible to composition and
  HR-0082's Washington attempt licenses alone. The Week 5 fix is provenance columns plus a new
  derivation, not de-duplication. (read 2026-09-15; a property to
  know, not a bug fixed). `core/composition.py::derive` indexes attempts by (company,
  signal) across all published runs, and a bucket is covered if ANY one attempt's reach
  spans it; `covering_instruments` stores signal names only, not run ids, versions or the
  source read. So a correction run does not displace the attempt it corrects -- the stale
  one keeps licensing until its run is superseded -- and nothing on a derived row says which
  run licensed it. Seen on Goodfellow Bros: with H-BREACHPORTAL-01 v1.1 (HR-0069, California,
  stale basis) and v1.2 (HR-0082, Washington) both published, 2026-W36's
  `absence_licensed_IC4` rested on both. v1.1 was superseded 2026-09-15 (item 11) and no
  derived row changed; check 9 no longer counts a superseded version's artifact as an
  orphan. The property itself -- no de-duplication, no newer-run preference, no
  provenance column -- is unchanged (verified against HEAD 2026-09-15: still open).
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
- `DECISIONS.md` -- **POPULATED 2026-09-20**: 40 dated decisions with reasoning and consequence,
  append-only and never rewritten, closing with the standing decisions about what is deliberately
  NOT attempted. Written so the repo is a readable submission artifact on its own, without the
  Notion revision log
- `docs/analysis/` -- analysis-phase deliverables. First: `theme_evidence_matrix_2026-09-20.md`,
  the theme-by-theme evidence matrix (`python scripts/theme_evidence_matrix.py`), a pure data
  pull over all 10 designed themes -- role and grade splits, contributing harnesses, instrument
  classes, licensed absences and a coverage state per theme. Invalid rows excluded entirely,
  seller_side-tagged rows excluded from buyer counts, quarantined rows held out and shown
  separately. Reconciles with `gap_report.py` once its low-grade exclusion is accounted for.
- `docs/report_appendix_dispositions.md` (coherence pilot, app-store, YouTube -- all three scoped and
  NOT built) / `docs/report_appendix_reliability.md` (documented limitations) -- report appendices
- `docs/analysis/open_items_2026-09-20.md` -- everything still open, split into what needs Matthew's
  judgment and what is parked deliberately; `brief_composition_provenance_2026-09-20.md` is the one
  design question written back rather than guessed at
- `data/export/` -- **static read-only CSV snapshot** of the evidence base for inspection
  (`scripts/export_snapshot.py`, re-verifiable with `--check`); adds each observation's current
  `validity_status` and `is_low_grade`, which exist only as joins in the live workbook
- `docs/conventions.md` -- locked conventions with their originating incidents, treat as
  authoritative
- `docs/archive/` -- superseded specs and docs
- Notion "Revision Log (Raw)" (separate system, not in this repo) -- session-by-session
  raw decision log across all three Claude Projects
