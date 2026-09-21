# Session 17 Report — Week 4: H-PROCUREMENT-01, and the USASpending "block" root-caused

**Date:** 2026-09-13 (attended, live)
**Brief:** Week 4 harness build order: (1) H-PROCUREMENT-01, checking whether it can license
absence for `systems_integration`; (2) root-cause the USASpending / PatentsView access failure;
(3) H-VENDOR-01 and its population-0 artifact; (4) permits / local records / WARN / techstack
as one harness; (5) 8-K Item 1.05 with `Companies.public_private` if it is a clean field.
Reported per harness. This report covers items 1 and 2; later items append below.

## In one screen

| item | outcome |
|---|---|
| 2. Access root cause | **USASpending was never blocked by the network.** Its own web application firewall refused the probe's User-Agent (`IndStudyResearchBot`) on the token `ResearchBot`. **PatentsView is retired at the source** (USPTO, 2026-03-20). The Texas breach-portal timeout does not reproduce and is not the same cause. Probe fixed; convention 38 amended. |
| 1. H-PROCUREMENT-01 v1.0 | Built and run live (HR-0070): 35 rows for 33 companies, 157 `absent_confirmed` and 24 `not_covered` (same-state near-miss) attempts. **Audited: random control 30 of 35, all supported (Matthew), published.** Cannot license a `systems_integration` absence, for three measured reasons. |

State after release: 579 observations, all released, 200 human-reviewed, 195 low-grade; 70 runs;
6,597 attempts. validate 11/11, check_run_ledger clean, 13 test files pass.

## 2. The access diagnosis (done first, because item 1 depended on it)

The layered probe (DNS through the system resolver and Cloudflare DoH, TCP, TLS issuer, HTTP)
separated the three hosts that had been filed together:

- **api.usaspending.gov.** The "Web Page Blocked!" page with a client IP and an Attack ID came
  back inside a TLS session verified against Treasury's genuine Entrust certificate, carrying
  the load balancer's `BIGipServer~api.usaspending.gov` cookie. A device on this network cannot
  answer inside that session, so the page is the source's own firewall. Varying one request
  property at a time found the trigger: every User-Agent containing `ResearchBot` is refused
  (`IndStudyResearchBot/1.0`, `ResearchBot/1.0`); `Bot/1.0`, `crawler`, `Googlebot`, curl,
  python-requests and an empty UA all get 200 from the same IP, as does the harness UA on every
  endpoint (references, recipient search, award search, subawards). `www.usaspending.gov`
  answered throughout.
- **The 2026-09-01 "different network" was not one.** Today's egress IP (66.60.120.13) is the
  IP named on that day's block page; ARIN registers the block to a business network, upstream of
  the local router.
- **PatentsView.** `search.patentsview.org` is NXDOMAIN from Cloudflare DoH as well as the
  local resolver, and `patentsview.org` / `api.patentsview.org` redirect to
  `data.uspto.gov/support/transition-guide/patentsview`. USPTO shut the PatentSearch API down on
  2026-03-20 and moved PatentsView to the Open Data Portal. The source's decision; no replacement
  API path was guessed.
- **Texas (session 16).** Neither Texas host timed out: `www.texasattorneygeneral.gov` and the
  Salesforce breach page `oag.my.site.com/datasecuritybreachreport/...` both answered in under a
  second, with bot and harness UAs alike (the Salesforce list itself renders client-side). The
  one anomaly was a Cloudflare 429 on the bare apex `texasattorneygeneral.gov`, a rate limit that
  could present as a stall. Session 16 did not record which URLs timed out, so this cannot be
  confirmed; it is **not** the USASpending root cause.

Fixed: `scripts/probe_sources.py` sends the harness identity and its PatentsView probes say
"retired"; re-run, USASpending reads `ok` and the three working controls still read `ok`
(convention 37). `docs/conventions.md` 38 carries a dated amendment, including two refinements:
a block page that names your IP is not evidence the block is local, and vary one request
property at a time before blaming a route. Not changed: H-LEGAL-01's `source.py` still sends the
`ResearchBot` UA to CourtListener, which accepts it today; a latent hazard, logged.

## 1. H-PROCUREMENT-01 v1.0

**What it records.** For each buyer, federal PRIME awards with a transaction in the five years to
retrieval: contracts and IDVs (`federal_prime_contract_award`, ST-0011, family 7) and grants and
loans/guarantees/insurance (`federal_assistance_award`, ST-0012, family 2). Both IC3, grade A,
`buyer_acts`, `measured_result`, state `unknown`. Sources SRC-0020 / SRC-0005 (already
registered), archival reach. Opaque signal-type ids continue the ST-00NN series.

**`systems_integration` absence licensing: not feasible.** (1) In a prime award the company is
the seller; the description is work delivered to an agency, so routing it to a theme would make
a contractor that builds a Navy data centre look like a company modernizing its own data estate.
(2) The only buyer-side leg, subawards under the company's own prime awards, was empty under
Whiting-Turner's two largest primes, and a UEI search on subawards returns awards where the
company is the SUB. Subaward reporting is prime-self-reported and incomplete, so its silence
could not be licensed anyway. (3) No statute compels disclosure of integration work. No theme is
routed and `core/composition.py` is unchanged. An `absent_confirmed` here means "no federal prime
award in the window", nothing more.

**Identity.** Calibrated on real recipients before building, then corrected over five
row-by-row reads of full dry runs, every one of which found something the summary line hid:

| read | defect | fix (with tests) |
|---|---|---|
| calibration | text search is substring-like (COMMACK GROUP for Mack Group, KENCOA for Kenco); one company, many UEIs, regional entities | candidates from award records (name, UEI, state); exact-token name rule; HQ-state corroboration |
| 12-co dry run | loan group has no "Award Amount" (HTTP 400) | per-group fields and sort; a 4xx is our defect, not transient |
| 12-co dry run | **WALSH & COMPANY, P.C. accepted for The Walsh Group** | professional-practice legal forms refused |
| 12-co dry run | query_variants turns "Prime Inc." into bare "Prime" | common-word names never searched bare |
| full run 1 | **"J.R. Simplot" / "JR Simplot" return nothing; "Simplot" finds it** (false absence) | names with initials or punctuation also search their rarest token |
| full run 1 | one shared token blocked clean absences (COLLIN MCSHANE, CATERING CAJUN, CRETE AREA MEDICAL CENTER); W. W. CLYDE & CO. must stay a near-miss | near-miss = every distinctive token, leading (after initials), not a public body |
| full run 2 | **ANDERSON HOLDINGS LLC accepted for Anderson Trucking Service**; Lynden 134 contracts "totalling $26,775"; future publication dates; guarantees/insurance called loans; GILBANE BUILDING refused | one-token names need their own line-of-business word; totals from per-UEI listings; dates capped at retrieval; wording; BUILDING allowed |
| full run 3 | a UEI search includes every entity registered under it as SAM parent, so Lynden double-counted (132 + 2) and the children went unnamed | awards deduplicated, family counted once, subsidiaries named |
| full run 4 | ATKINSON/CLARK, A JOINT VENTURE re-entered through the family path | JVs and practices excluded from the family and noted |

`core/tests/test_procurement.py`: 67 checks, written from the requirement, including a fixture
test of the parent-UEI path.

**Result (HR-0070).** 35 rows for 33 companies; 63 companies read absent; 12 are same-state
near-misses that need a human alias rather than a guess (W. W. Clyde & Co., M. A. Mortenson
Company, W. G. Yates & Sons, Walbridge Aldinger, Leprino Foods Dairy Products, Goodfellow Bros.
California, among others). Two readings to keep in mind: counts include subsidiaries registered
under the company's SAM parent UEI (named in each row), and same-named registrations in other
states are not counted, so figures are floors. Admiral Beverage's 346 contracts are real Defense
Logistics Agency micro-purchases (median about $600).

**Audit.** Random control 30 of 35, all supported, judged individually by Matthew; `a_graded`
and `off_own_domain` censuses of 35 (the 5 rows outside the control judged mechanically and
released with the version, the FIRSTPARTY v1.2 precedent: O00623, O00625, O00635, O00639,
O00653). Exclusion rate 0.0% against 10%. PASS, published. The review sheet truncates claims at
900 characters (display only; O00632 is intact at 1,135), not fixed during the audit.

## Files

- New: `harnesses/h_procurement_01/` (harness, manifest), `core/tests/test_procurement.py`,
  `H-PROCUREMENT-01__v1.0.json` / review / strata, this report.
- Changed: `scripts/probe_sources.py`, `scripts/register_sources.py` (ST-0011, ST-0012),
  `scripts/migrate_schema.py` (reach for SRC-0005 / SRC-0020), `docs/conventions.md` (38),
  `CLAUDE.md`, the workbook (also closes the two BREACHPORTAL v1.1 Harness_Sources rows session
  16 never synced).

## Addendum: rulings applied (2026-09-13)

- Matthew reviewed all 30 random-control rows of H-PROCUREMENT-01 v1.0: all supported. Verdicts
  recorded through `apply_audit_verdict`; artifact written (PASS, 0.0% exclusions against 10%);
  v1.0 published, releasing the 5 rows outside the control on the FIRSTPARTY v1.2 precedent.
  Committed as c0164ec.

## 3. H-VENDOR-01 v1.1: the population-0 result checked, fixed and formalised

**v1.0's zero was not an absence.** Read page by page against the archived HTML, the six pages
v1.0 had read and called absent were:

| page | what it actually was |
|---|---|
| Ardoq / SpawGlass | name-test defect: 10 prose sentences say "SpawGlass"; v1.0 demanded "SPAWGLASS HOLDING" |
| XCentium / Melaleuca | same defect: 8 sentences say "Melaleuca" |
| Autodesk / "GRAHAM" | wrong entity: the UK and Ireland contractor, not Graham Construction of Omaha (grahambuilds.com) |
| Autodesk / PENTA | retrieval gap: all 13 "PENTA" mentions are in the header and meta tags; the body loads client-side |
| University of Michigan / Suffolk's CEO | not vendor content (a dyslexia-help success story tagged by URL shape) |
| OpenSpace / Joeris | a genuine read: Tony Moreno's two quotes carry no theme term |

**v1.1 fixes** (`core/tests/test_vendor.py`, 18 checks, the first vendor tests): a coined one-token
name stands alone in a sentence (convention 31); a one-distinctive-token company on a third-party
page needs a corroborator (website domain, HQ city or HQ state name) or is refused as
`identity_uncorroborated`; a page that passes identity but serves no prose naming the company is
`js_rendered_unreachable`, never absent; `.edu` / `.gov` hosts and business directories are not
vendor content; seed dedupe ignores a leading `www.`. One regression caught on the first dry run:
the dedupe fix also stripped `www.` from the URL fetched, and Joeris / OpenSpace (the page v1.0 had
read correctly) stopped reading; fixed, with a test that every fetch URL is the logged URL.

**Seeds.** Every EXECVOICE run log: 28 logged, 27 distinct, 13 excluded before reading (10
appsruntheworld aggregators, a D&B directory profile, the Michigan page, Grant Thornton's own
page), 14 usable for 12 companies. The six seeds added by EXECVOICE's session 15 run give no usable
vendor page for a buyer.

**Result (HR-0071, live): population 0.** 2 pages read: Joeris, a genuine absence; SpawGlass, an
absence **bounded by the in-sentence naming rule**: the sentences that name SpawGlass carry no
theme term in a deployment sentence, but two passages about "the team" do ("They leveraged the
Microsoft Entra ID integration", generic tier; "using Ardoq's AI capabilities to generate process
maps", strong tier). Page-level attribution was not adopted because the same page's navigation
("Govern and Leverage AI Effectively") would be written as SpawGlass deployments; logged for a
decision. The rest: 8 not about the company, 2 identity_uncorroborated (UK GRAHAM; Melaleuca, a
probably-genuine page with no theme, refused at the stated cost), 1 retrieval gap (PENTA), 1
robots refusal (CT Logistics), 1 HTTP 403 today (FCL Builders / Equipment World).

**Artifact.** `H-VENDOR-01__v1.1.json`, population 0 on the PQ v1.2 precedent, the full denominator
in its summary, precision undefined (not 100%). Published. v1.0's runs HR-0061..HR-0063 stay
quarantined: v1.1 read a superset of their seeds, not the same scope.

## 4. H-LOCALRECORDS-01 v1.0: permits, local records, WARN and techstack as one harness

**Shape.** One harness, four sub-scopes, one access layer (`source.py`: robots per host,
bot-challenge detection, backoff, a request-fingerprinted dated archive). Each sub-scope has its
own signal type (opaque ST-0013..ST-0016), family, class and jurisdictional scope:

| sub-scope | what it reads | class | scoped absence |
|---|---|---|---|
| warn | Texas TWC yearly xlsx (1,180 notices in window), Utah DWS table (80), California EDD current fiscal-year xlsx (217) | IC4 | companies headquartered in TX, UT, CA |
| permits | Chicago, Seattle, Austin Socrata building permits | IC3 | companies headquartered in Chicago or Seattle |
| council | Seattle Legistar matter titles | IC3 | Seattle-headquartered companies |
| techstack | the 108 homepages H-EXECID-01 archived, read for specific markers | IC3 | all 108 |

**Measured before building.** Out of reach and recorded, never worked around: Missouri's WARN
page (Incapsula challenge), Minnesota's (perfdrive redirect); Washington's WARN data link is gone;
California WARN before 2026-07-01 exists only as PDFs; Chicago and Salt Lake City are not Legistar
web API clients; Utah's open-data domain is decommissioned. **Direction:** in all three permit
datasets the buyers appear as CONTRACTOR on someone else's project (Chicago: Walsh 665
general-contractor roles to 12 "owner" roles, and those owner rows are misfiled GCs or namesakes),
so permit rows record seller-side local project volume, like procurement; owner-role hits are
counted and not written. Nothing routes to a theme.

**Identity, corrected over two row reads.** The first full dry run (134 rows) wrote wrong
entities the summary hid: for The Walsh Group a bare "WALSH" (a web-portal applicant), WALSH
SERVICES INCORPORATED (a Crestwood plumber) and WALSH BROTHERS CONSTRUCTION; for Mortenson a
Wilmette masonry firm, MORTENSON CONSTRUCTION, while the real M. A. MORTENSON COMPANY (Minneapolis,
54 permits) was refused; for The Yates Companies an Elgin, Texas "Yates Construction Inc."; for
McCarthy Holdings a local "MCCARTHY CONSTRUCTION CO"; and a council row for "Appointment of Cali
Mortenson Ellis". Contact addresses could not separate them (the Walsh plumber is in Illinois too).
The exact operating-name FORM could, on every case: a name with one distinctive token now matches
only its canonical name, a legal name SAM registers for the company (loaded from released
H-PROCUREMENT-01 rows: WALSH CONSTRUCTION COMPANY, GILBANE BUILDING COMPANY, MCCARTHY BUILDING
COMPANIES, SWINERTON BUILDERS), or a human alias. A one-word name in a council title needs a
legal-form or line-of-business word after it. The second read caught a successor numeral (WALSH
CONSTRUCTION COMPANY II, LLC, 102 permits, refused on "II") and a dba clause (Layton Builders of
Texas); both fixed. `core/tests/test_localrecords.py`: 49 checks from these exact strings.

**Result (HR-0072, live), quarantined.** 127 rows: 94 techstack (WordPress, Google Tag Manager,
GA4, Cloudflare, HubSpot among the markers), 31 permits (Walsh Chicago 113, Power Construction
Chicago 433, Rogers-O'Brien Austin 192, JE Dunn Austin 228, Swinerton Austin 139, and others), 2
WARN (Merit Medical, Houston, 117 workers, 2022; Scentsy, Coppell TX, 94 workers, 2025), 0
council. Attempts: 10 scoped not_covered (7 archived homepages answered 403, 3 had no response).
Review sheet: `H-LOCALRECORDS-01__v1.0__review.md`, 30 of 127.

**For Matthew:** the review sheet; Mortenson in Seattle rests on a bare "Mortenson" contractor
string (2 permits), a canonical-form match with no address to corroborate it; Clayco Construction
(Austin, 44 permits) and McShane Construction Company (Chicago) are refused until an alias is
seeded; whether seller-side permit volume belongs in the evidence base at all.

## 5. 8-K Item 1.05: stopped and flagged (not built)

The brief said to add `Companies.public_private` if it is a clean field and to stop if it needs
real schema thought. **It needs schema thought.** The 8-K Item 1.05 obligation attaches to
Exchange Act reporting status as of a date, and "public / private" is not that variable. EDGAR
full-text search (efts.sec.gov, which answers this crawler) found 12 buyers as SEC filer entities:
only Merit Medical, SpartanNash and Co-Diagnostics look like current reporters (10-K / 10-Q /
8-K); McCarthy Holdings, Crane Worldwide, UniGroup and Herzog file Form D only; Kenan Advantage
(S-1 withdrawn) and Western Express (S-1) never became reporters; J.R. Simplot files as an
insider / holder; EnergySolutions was a reporter and went private, so the status changes over
time; "Lynden USA Inc." (S-3) may not be this Lynden. A public/private column would misplace
Simplot, the Form D filers and EnergySolutions. The field needs a controlled vocabulary, a source
and as-of date per value, and a decision on how a status change is recorded: a Harness Advisor
call. For scale: 93 Item 1.05 8-Ks since the rule took effect (2023-12-18), from 67 filers, none a
buyer.

A second decision rides with it: SEC's fair-access policy requires automated tools to declare a
contact ("Sample Company Name AdminContact@<domain>") in the User-Agent, and www.sec.gov answers
the harness identity with HTTP 403. A compliant 8-K harness needs a contact address chosen by
Matthew. Nothing was added to the schema and no 8-K harness was built.

**For Matthew (item 3):** whether a single-customer story page should attribute unnamed "the team"
passages to the customer under a stronger page test (for example, requiring the company in the
page title and excluding navigation blocks), which would likely turn SpawGlass into one or two
reviewable rows.

## Addendum: H-LOCALRECORDS-01 v1.0 ruling applied (2026-09-13)

- Matthew reviewed the 30 random-control rows on `H-LOCALRECORDS-01__v1.0__review.md`: all
  supported. Verdicts recorded through `apply_audit_verdict`; artifact
  `H-LOCALRECORDS-01__v1.0.json` written (PASS, 0.0% exclusions); v1.0 published, releasing the
  97 rows outside the control with the version, without an individual human verdict (the
  FIRSTPARTY v1.2 / PROCUREMENT v1.0 precedent). Quarantine is empty again.
- Still open, awaiting a brief: the VENDOR "the team" attribution question (item 3), the
  Mortenson / Seattle borderline permit row and the Clayco Construction and McShane
  Construction Company aliases (item 4), the procurement near-miss aliases (item 1), the
  8-K Item 1.05 reporting-status field and SEC User-Agent contact (item 5), and whether
  seller-side permit volume belongs in the evidence base.

## Session 17 wrap-up (2026-09-13): three items implemented, one on hold

### 1. H-VENDOR-01 v1.2: the stricter page test, checked on real output

The design: attribute an unnamed deployment passage to the company only when (a) the page title
names the company and (b) navigation, header and footer blocks are excluded from the sentence
scan. Measured on the Ardoq page first: the title, og:title and h1 all name SpawGlass; every
theme-laden marketing line ("Govern and Leverage AI Effectively", "AI Lens", "AI Webinars", "ERP
Transformation") sits inside header/nav; the story sits inside main/article.

What the actual output showed, run by run:

| run | SpawGlass rows | what it revealed |
|---|---|---|
| first v1.2 dry run | 1 (data_analytics_ai) | the "Entra ID" passage was missing; test also showed a heading fusing with the next paragraph |
| after joining the body on line breaks | 1 | the inline link in "They leveraged the <a>Microsoft Entra ID integration</a> (formerly ...)" was now a sentence break: verb and theme term in different pieces |
| after splitting only at block elements | **2** | as predicted |

**Result (HR-0074, live, quarantined): SpawGlass yields 2 rows, both low grade and both marked as
page-subject attributions** -- `systems_integration` on "They leveraged the Microsoft Entra ID
integration (formerly known as Active Directory) to pull in people and departments", and
`data_analytics_ai` on "using Ardoq's AI capabilities to generate process maps". No navigation
text was attributed. Every other page outcome is identical to v1.1 (Joeris: 0 deployment
sentences, 2 unthemed named quotes, 5 anonymous dropped). `core/tests/test_vendor.py`: 27 checks,
including the Ardoq list-item markup verbatim. Review sheet: `H-VENDOR-01__v1.2__review.md`
(census of 2).

### 2. H-LOCALRECORDS-01 review: no action (Matthew reviewing directly)

### 3. SEC reporting status: the design implemented

- **Table** `Company_SEC_Reporting_Status_History`, 10 columns as specified, vocabulary of 8 at
  Lookups!AC with a dropdown binding. **Workbook tab `SEC_Reporting_Status_History`:** Excel caps
  sheet names at 31 characters and the design name is 36 (openpyxl warned; Excel would "repair"
  the file by truncating it). Renamed in place after the first load, rows and binding intact;
  `core/sec_status.py` keeps `TABLE_NAME` and `SHEET`. **A deviation for confirmation.**
- **Append-only writer** `core/db.py::append_sec_status`: new row per determination;
  `superseded_by` is the only field ever set after insert; an unchanged status or an identical
  row is a no-op; an older finding cannot supersede a newer one. `entity_unresolved` (identity
  doubt: a note naming the candidate filer, no status asserted) and `status_uncertain` (status
  doubt: a CIK-confirmed filer) are refused on each other's evidence. Derived reader
  `sec_status.active_reporters`; no stored flag. `validate_repo_db.py` check 12 enforces
  integrity, forward-only supersession, one current row per company, and fails on any
  `public_private` column on any sheet. `core/tests/test_sec_status.py`: 19 checks.
- **Seed:** exactly 13 rows for the 12 companies (`scripts/load_sec_reporting_status.py`), each
  with its CIK, filing and evidence date from EDGAR under the declared contact. EnergySolutions
  is two rows (active_reporter as of its 10-Q 2013-11-12, superseded by deregistered as of the
  final Form 15-15D 2014-01-27). A re-run writes nothing. No row for the other 96 buyers.
- **Evidence that contradicts the fixed seed, flagged not acted on:** SpartanNash's EDGAR record
  shows Form 25-NSE (2025-09-22) and Form 15-12G (2025-10-02) after the 10-Q its active_reporter
  row rests on. Under the table's own mechanics that is a superseding `deregistered` row; not
  written without Matthew's decision. Lynden USA Inc. is a co-registrant of Lynden Energy Corp.
  (oil and gas) -- a strong case for the `entity_unresolved` it was given.
- **H-SEC8K-01 v1.0** (HR-0073, quarantined, population 0): scope derived from the table's
  current active reporters (3); 94 8-Ks since 2023-12-18, none with Item 1.05; 3
  `absent_confirmed`. Exact item-code matching (`core/tests/test_sec8k.py`, 11 checks). Listed in
  `core/composition.py` as an IC4 cybersecurity instrument (the BREACHPORTAL precedent); inert
  until audited and published. `SEC_CONTACT_EMAIL` lives in `.env` (gitignored); www.sec.gov
  answers 200 with it.

### Findings carried forward (now in CLAUDE.md)

- **Patents / IP is a portfolio gap:** PatentsView retired by USPTO on 2026-03-20; no
  near-term instrument path.
- **Cross-harness: buyers appear as seller / contractor, not as the commissioning buyer,** in
  both federal prime awards (H-PROCUREMENT-01) and city permits (H-LOCALRECORDS-01), found
  independently. For this universe those record families describe work done for others, so
  neither can license a buyer-side theme absence.

State: 708 observations (706 released, 2 quarantined), 74 runs, 6,815 attempts, 33 signal types,
13 SEC status rows. validate 12/12, ledger clean, 17 test files pass.

## Addendum: H-VENDOR-01 v1.2 ruling applied (2026-09-14)

- Matthew reviewed both reviewable rows (the H-VENDOR-01 v1.2 census on
  `H-VENDOR-01__v1.2__review.md`): both supported. Verdicts recorded through
  `apply_audit_verdict`; artifact `H-VENDOR-01__v1.2.json` written (census 2 of 2, 0.0%
  exclusions against the 15% threshold for populations under 20); v1.2 published. No row is
  quarantined.
- **H-SEC8K-01 v1.0 (HR-0073) is held, not published.** It has no rows to review (population 0,
  3 `absent_confirmed`). Publishing it would make `core/composition.py` read those three as
  licensed IC4 cybersecurity absences, including SpartanNash, whose deregistration (Form 15-12G,
  2025-10-02) is still an open decision on the status table. Needs an explicit go-ahead.
- Still open, awaiting a brief: the SpartanNash status row and the H-SEC8K-01 publication; the
  SEC tab-name deviation (`SEC_Reporting_Status_History`); the Mortenson / Seattle borderline
  permit row and the Clayco Construction and McShane Construction Company aliases; the
  procurement near-miss aliases; whether seller-side permit volume belongs in the evidence base;
  the email address already in the FMCSA and JOBPOST source files before any code-only export.

## Follow-up brief (2026-09-14): SpartanNash, alias resolution, directionality on hold

### 1. SpartanNash

`scripts/record_sec_status.py` (new; dated determinations after the seed, dry run by default)
appended SRS-0014: `deregistered`, `as_of_date` 2025-10-02, `source_filing_type` Form 15-12G,
source EDGAR CIK 0000877422 (Form 25-NSE 2025-09-22, Form 15-12G 2025-10-02). SRS-0002 (the
seeded `active_reporter`) now carries `superseded_by` SRS-0014. `active_reporters` dropped from
[A019, A029, A030] to [A019, A030], i.e. 2. Re-running is a no-op; check 12 OK. **H-SEC8K-01's
held run HR-0073 was scoped on 3; re-run on the derived 2 before any publication.**

### 2. Alias resolution from source records

All evidence came from USASpending recipient records (SAM registration data: name, UEI,
address, SAM parent) and the city permit portals, not web search.

**Code.** H-PROCUREMENT-01 v1.1 adds three identity paths, none of which rescues a JV or a
professional practice, all behind the HQ-state gate: (a) an exact form of a source-record
alias; (b) a same-state near-miss whose own recipient record names a SAM parent that passes
identity; (c) an anchor check: when nothing is accepted, the company's own registered entity
is looked up and its awards counted; if it holds none, near-misses without a UEI are cleared,
and near-misses with a UEI keep blocking. `not_variants` in the alias file lets a human mark a
confirmed different entity. H-LOCALRECORDS-01 v1.1 accepts an exact verified/alias form before
`name_matches`. Tests: procurement 78, localrecords 55, all 17 files pass.

**Aliases added** (`data/company_aliases.json`, each with its record cited): Mortenson
(M. A. MORTENSON COMPANIES, INC., the parent on recipient M. A. MORTENSON COMPANY's record, and
that recipient name; the parent name alone does not match the permit string "MA Mortenson
Company"); McShane Construction Company (Chicago permit contact address Rosemont, IL = HQ);
and, on the same same-HQ-city standard, W. W. CLYDE & CO. (Orem, UT), LEPRINO FOODS DAIRY
PRODUCTS COMPANY (Denver, CO) and CAJUN INDUSTRIES LLC (Baton Rouge, LA). **The last three
rest on name + HQ city, not a parent link** (each record lists itself as parent); veto any of
them and the rows go.

**W. W. Clyde first check: not a punctuation mismatch.** Every spelling tokenizes to
WW CLYDE; it was refused for the extra token.

| Company | Outcome | Evidence |
|---|---|---|
| Mortenson (A039) | **real hit** x3 | procurement: 38 contracts + 12 IDVs, $1.82B, M. A. MORTENSON COMPANY (MN). Permits: Chicago 54 (new), Seattle 2 -> 3 ("MA Mortenson Company" added) |
| Walbridge (A042) | **real hit** | 1 contract, $60M, WALBRIDGE ALDINGER LLC, SAM parent THE WALBRIDGE GROUP, INC. |
| The Yates Companies (A044) | **real hit** | 6 contracts + 2 IDVs, $232M, W. G. YATES & SONS CONSTRUCTION COMPANY, parent THE YATES COMPANIES INC |
| Clyde Companies (A012) | **real hit** (same-city alias) | 3 contracts, $116M, W. W. CLYDE & CO., Orem UT |
| Leprino Foods (A050) | **real hit** (same-city alias) | 82 contracts + 3 IDVs, $273M, all USDA cheese purchases |
| McShane (A003) | **real hit** (permits) | 4 Chicago GC permits, MCSHANE CONSTRUCTION COMPANY, LLC |
| Layton Construction (A061) | **confirmed clean absence** | registered entity LAYTON CONSTRUCTION COMPANY, LLC (UT, parent THE LAYTON COMPANIES INC) holds 0 awards; 3 name-only near-misses cleared |
| Cajun Industries (A004) | absence **pending one ruling** | registered CAJUN INDUSTRIES LLC and its parent both hold 0; 36 name-only near-misses cleared; CAJUN GROWERS INC (Cut Off, LA, small business, 1 grant) still blocks -> `not_variants`? |
| Anderson Trucking (A068) | absence **pending one ruling** | ANDERSON TRUCKING SERVICE, INC. (MN) holds 0; 10 cleared; ANDERSON ENGINEERING OF MINNESOTA, LLC (Minneapolis, veteran-owned engineering, 189 awards) blocks -> `not_variants`? |
| Goodfellow Bros (A024) | **unresolved** | GOODFELLOW BROS. CALIFORNIA, LLC (Livermore CA, 1 contract, self-parented); `Companies.hq_state` has no city, so the same-city test cannot run |
| Austin Industries (A047) | **unresolved** | AUSTIN INDUSTRIES INC DELAWARE CORPORATION has no location on its record (0 awards), so it cannot anchor; 6 UEI near-misses are other firms by name |
| Graham Construction (A026) | **unresolved** | no registered entity found; J.W. GRAHAM, GRAHAM QUALITY CONTRACTING have no UEI |
| Herzog Enterprises (A092) | **unresolved** | no registered entity found; HERZOG MOTOR SPORTS has no UEI |
| Clayco (A035), permits | **unresolved** | Austin "CLAYCO CONSTRUCTION" (44 permits) contractor address Hutto, TX, not St. Louis; no SAM/USASpending record. Not aliased; not committed (Chicago row would change only its window date) |

**Runs.** HR-0075 (LOCALRECORDS v1.1, A003/A039 permits), HR-0076 (PROCUREMENT v1.1, the 12),
HR-0077 (PROCUREMENT v1.1, A004/A012/A050 after the same-city aliases). 8 rows quarantined:
census sheets `H-PROCUREMENT-01__v1.1__review.md` (5) and `H-LOCALRECORDS-01__v1.1__review.md`
(3). O00704 (Mortenson Seattle) was a released v1.0 row and is re-quarantined by its count
change.

**For Matthew:** (1) the 8-row census; (2) the three same-city aliases; (3) `not_variants` for
CAJUN GROWERS INC and ANDERSON ENGINEERING OF MINNESOTA, LLC, which would make Cajun and ATS
clean absences; (4) whether "no registered entity at all" (Graham, Herzog) should license an
absence: a federal prime contract requires a SAM registration, but the design currently
refuses to clear without an anchor.

### 3. Seller-side evidence directionality

On hold pending the Harness Advisor. `evidence_role` untouched; no directionality tagging added.

State: 715 observations (707 released, 8 quarantined), 77 runs, 6,847 attempts, 14 SEC status
rows (active_reporter 2). validate 12/12, ledger clean, 17 test files pass.

## Addendum: alias rulings applied (2026-09-14)

- **Census review, 8 of 8 supported** (Matthew). Verdicts recorded through `apply_audit_verdict`;
  artifacts `H-PROCUREMENT-01__v1.1.json` (5 of 5) and `H-LOCALRECORDS-01__v1.1.json` (3 of 3),
  both 0.0% exclusions against the 15% threshold; both versions published. O00704 (Mortenson
  Seattle) is released again at v1.1.
- **The same-city aliases (Clyde, Leprino, Cajun) are affirmed** as seeded.
- **Different firms confirmed:** CAJUN GROWERS INC (A004) and ANDERSON ENGINEERING OF MINNESOTA,
  LLC (A068) seeded as `not_variants` in `data/company_aliases.json`.
- **No registered entity counts as an absence: H-PROCUREMENT-01 v1.2.** Before the run, the
  recipient directory showed that the premise "no registered entity at all" was not exactly true
  for either company, so the rule was built as: no registered entity in the HQ state, AND every
  identity-passing registered entity elsewhere holds no award in the window (or there is none).
  A UEI-bearing near-miss still blocks. Tests: procurement 82.
- **HR-0078 (v1.2, live, population 0, audited and published):**

| Company | Outcome |
|---|---|
| Cajun Industries (A004) | **clean absence**: CAJUN GROWERS INC refused as a different firm; CAJUN INDUSTRIES LLC holds none; 35 name-only near-misses cleared |
| Anderson Trucking (A068) | **clean absence**: ANDERSON ENGINEERING OF MINNESOTA refused as a different firm; ANDERSON TRUCKING SERVICE, INC. holds none; 10 cleared |
| Graham Construction (A026) | **clean absence**: nothing registered in NE; GRAHAM CONSTRUCTION SERVICES, INC. (MN, parent GRAHAM GROUP LTD) holds none; J.W. GRAHAM and GRAHAM QUALITY CONTRACTING INC cleared |
| Herzog Enterprises (A092) | **referred back, still `not_covered`**: HERZOG GROUP INC. (UEI RC7SWPVPWE81, CA, its own SAM parent) holds 1 contract + 1 IDV. If it is not Herzog's, a `not_variants` entry makes A092 a clean absence under the same rule; if it is, the awards are out-of-state and would need a ruling on counting |

**Still open after the rulings:** Herzog (above); Goodfellow Bros (no HQ city on `Companies` to
compare GOODFELLOW BROS. CALIFORNIA, LLC, Livermore); Austin Industries (registered entity has
no location; 6 UEI near-misses); Clayco Construction permits (Hutto, TX; no SAM record); the
H-SEC8K-01 re-run on the derived 2 active reporters; seller-side directionality (on hold for the
Harness Advisor).

State: 715 observations (715 released, 0 quarantined), 78 runs, 6,855 attempts, 14 SEC status rows.

## Evidence directionality (build handoff 2026-09-15)

### Built

- **`Observation_Directionality_Tags`** (tab name is exactly 31 characters, within Excel's limit):
  `observation_id`, `evidence_directionality`, `tagged_at`, `tagging_run_id`, `notes`. Vocabulary
  `buyer_side` / `seller_side` / `mixed` / `not_applicable` at Lookups!AD, dropdown bound on column B
  (check 7: 36 validations). `scripts/migrate_schema.py --apply`: 3 changes.
- **`core/directionality.py`**: row rules (value in vocabulary, id resolves, ISO load date, run id
  required, notes required for `mixed` and for a `backfill_` batch) and the only writer, `append_tags`:
  all-or-nothing, an identical tag is a no-op, a different value for the same (observation, run) is
  refused. The writer is not in `core/db.py` because that module computes gate values and is scanned by
  the wall.
- **Check 13**: the convention 41 wall (no gate-computing module may name the table or import the
  module; FAILURE) plus tag integrity. Verified in both directions: a probe line naming the table in
  `core/audit.py` fails the validator, and restoring it passes.
- **Convention 44** in `docs/conventions.md`: the standing pattern (an optional classification of an
  observation lives in its own linked table).
- Tests: `core/tests/test_directionality.py` 21 checks; 18 test files pass; validate 13/13.
- No change to `evidence_role`, `organizational_state` or any other axis; no column on `Observations`.

### Backfill: ESCALATED under §3, nothing written

`scripts/backfill_evidence_directionality.py` reconciles the target set before writing and exits 2 when
it does not match. It does not match, for two independent reasons.

| Harness | Handoff | Workbook | Covered by the cited finding | Not covered |
|---|---|---|---|---|
| H-PROCUREMENT-01 | 35 | **40** (35 v1.0 + 5 v1.1, released 2026-09-14) | 36 `federal_prime_contracts` ("in a prime award the company is the seller") | 4 `federal_assistance_awards` -- grants / loans, where the company is a recipient of assistance, not a seller |
| H-LOCALRECORDS-01 | 127 | **129** (126 v1.0 + 3 v1.1) | 33 `municipal_permits_as_contractor` ("buyer as CONTRACTOR, not OWNER") | 94 `website_technology_stack` (the company's own homepage) and 2 `warn_layoff_notice` (its own layoffs) |

1. **Count drift.** The 35 and 127 are the v1.0 publication counts. The alias-resolution work released
   5 procurement rows and 3 permit rows at v1.1 on 2026-09-14 (one of the permit rows, O00704, moved from
   v1.0).
2. **Coverage.** "All 127 H-LOCALRECORDS-01 rows" includes 96 that are not permits. The
   CONTRACTOR-not-OWNER finding was made about the permit sub-scope only; the techstack and WARN
   sub-scopes describe the company itself, so tagging them `seller_side` would be an inference, which the
   handoff rules out. Likewise the 4 procurement assistance rows.

**Rows the cited findings do cover: 69** (36 prime-contract + 33 permit). Nothing was backfilled, including
that subset, because §3 says to escalate rather than backfill a best-guess subset. To proceed, the handoff
needs to restate the batch -- e.g. "every `federal_prime_contracts` and `municipal_permits_as_contractor`
row" (69 today) -- and say whether the 4 assistance rows, 94 techstack rows and 2 WARN rows are
`not_applicable`, something else, or left untagged. The script's `TARGETS` is the single place to change.

State: 715 observations (715 released), 78 runs, 0 directionality tags; validate 13/13, ledger clean.

## Addendum: directionality batch restated, identity calls, 8-K re-run (2026-09-15)

### 1. Directionality backfill: written

`TARGETS` now names the kinds the cited findings cover, each with its count at the restatement:
H-PROCUREMENT-01 `federal_prime_contracts` 36 and H-LOCALRECORDS-01 `municipal_permits_as_contractor` 33.
`--apply`: **69 tags, `seller_side`**, `tagging_run_id` `backfill_evidence_directionality_2026-09-15`,
`tagged_at` 2026-09-15, each with its finding in `notes`. The 4 assistance, 94 techstack and 2 WARN rows are
left untagged by design. Re-running is a no-op; a count that drifts from 36/33 still exits 2. Check 13: 69
tags, wall holds. Tests restated to the new batch (21 checks).

### 2. Identity calls

| Company | Call | Done | Result |
|---|---|---|---|
| Herzog Enterprises (A092) | HERZOG GROUP INC. is a different firm | `not_variants`; **H-PROCUREMENT-01 v1.3**: v1.2 honoured `not_variants` only among award recipients, so the CA firm still counted as a registered entity -- the registered-entity search now excludes it too | **clean absence** (HR-0079): HERZOG MOTOR SPORTS cleared |
| Clayco (A035), permits | Austin/Hutto CLAYCO CONSTRUCTION is a different firm; do not alias | `not_variants`; **H-LOCALRECORDS-01 v1.2** refuses a `not_variants` name first as `confirmed_different_entity` | settled non-match. Clayco's attempts were already `covered` (Chicago permits); the Austin name was only a logged refusal, which now reads as settled. No row changes, so no run |
| Goodfellow Bros (A024) | add `hq_city`, then the same-city test | `Companies.hq_city` added (migration) and filled for 99 of 108 from `hq_state` (`scripts/populate_hq_city.py`, blanks only) | **not run -- referred back.** See below |
| Austin Industries (A047) | accept the 0-award absence | the six UEI near-misses as `not_variants` | **clean absence** (HR-0079): six refused as confirmed different, 76 name-only near-misses cleared |

**Goodfellow's HQ city has no source that supports the test.** `hq_state` CA was set in session 16 by ruling
from the company's EPA facility in California (that report noted a facility is not a headquarters). The FMCSA
carrier census already on disk lists **GOODFELLOW BROS LLC, Wenatchee, WA** (USDOT 28686, 440 power units,
561 drivers) and **GOODFELLOW BROS CALIFORNIA LLC, Livermore, CA** (USDOT 2768818, 55 power units). The
Livermore entity is the candidate under test, so writing Livermore as the HQ city would make the same-city
test pass by construction; writing Wenatchee contradicts `hq_state` CA. Nothing was written for A024. The
decision needed: is Goodfellow Bros headquartered in Wenatchee, WA (then GOODFELLOW BROS. CALIFORNIA, LLC is an
out-of-HQ-city subsidiary and fails the same-city standard, and `hq_state` and the H-BREACHPORTAL-01 scoping
from session 16 would need revisiting), or is there a California HQ record?

**Austin's logged reason.** The cleared reason reads "no registered entity ... anywhere" rather than naming
the registered entity: AUSTIN INDUSTRIES INC DELAWARE CORPORATION fails the exact-token name test (extra
tokens), so the matcher does not count it as the company's. The outcome is the ruling's; the wording is the
matcher's limit, recorded in the v1.3 artifact.

v1.3 artifact (population 0) written and **published** on the rulings. Tests: procurement 84,
localrecords 57.

### 3. H-SEC8K-01 re-run: HR-0080, held for your decision

Scope derived from the status table: **2 active reporters** (A019 Co-Diagnostics, A030 Merit Medical).
Co-Diagnostics 33 8-Ks and Merit Medical 32 since 2023-12-18, **none with Item 1.05**, 2 `absent_confirmed`,
0 rows. **Quarantined, not published.** Publishing v1.0 would release both HR-0080 and HR-0073 (publication is
per version) and would make `core/composition.py` read the stale run's three absences, SpartanNash's
included. The clean route is to retire HR-0073 first (there is no disposition for "stale scope" today;
`superseded` requires the later run to cover the same scope) or re-version the harness. That is part of the
audit/publish decision.

State: 715 observations (all released), 80 runs, 6,861 attempts, 69 directionality tags, 14 SEC status rows.

## Addendum: H-SEC8K-01 v1.1 published (2026-09-15)

- **Versioning: v1.1**, so the manifest shows the correction. Same code; the v1.1 manifest entry records the scope
  correction (3 -> 2 after SRS-0014) and that v1.0 is never published.
- **HR-0080 relabeled v1.0 -> v1.1**: its `Harness_Runs.version`, its 2 Attempts rows' `harness_version` and its run
  log. `material_revision_notes` on the run row records the relabel and why.
- **HR-0073 stays v1.0, permanently quarantined**, with the reason in `known_issues`: the H-VENDOR-01 v1.0 treatment,
  no new status.
- **Audit:** population 0 (65 8-Ks, 0 with Item 1.05, 2 `absent_confirmed`), artifact `H-SEC8K-01__v1.1.json`, PASS;
  v1.1 **published**. Only HR-0080 moved.
- **What publication changes:** `core/composition.py` may now read Co-Diagnostics and Merit Medical as
  `absence_licensed_IC4` for cybersecurity, beside H-BREACHPORTAL-01's seven. No derivation was appended in this step;
  the next `derive_state_history.py` run will carry it.

## Addendum: Goodfellow Bros HQ corrected to Wenatchee, WA (2026-09-15)

### The correction

`hq_state` CA -> **WA**, `hq_city` -> **Wenatchee** (Matthew: founded in Wenatchee in 1921; accounting, contracts,
safety, IT and equipment are run there; Livermore, CA is a regional office). Written by
`scripts/correct_company_hq.py`, a dated decision that refuses unless the sheet still holds the value it replaces
and appends the reason to `Companies.notes`, so session 16's note stays readable beside the correction. Records
already on disk agree: FMCSA census GOODFELLOW BROS LLC (USDOT 28686) and USASpending GOODFELLOW BROS, LLC (UEI
CLAXYN5FDP93), both at Wenatchee, WA.

### Was EPA-facility-as-HQ a pattern? No -- isolated

- Goodfellow is the **only** company whose `hq_state` changed between the workbook's first commit and now, and the
  only one whose `notes` cite an EPA facility.
- **No code writes `hq_state`.** H-SAFETY-ENV-01 searches EPA ECHO nationally when `hq_state` is blank but never writes
  a state; `scripts/enrich_industry.py` read OSHA/ECHO records for `industry_primary`, not HQ.
- The pre-git archive copies differ from the first commit only in an old one-row offset in the pilots' states
  (2026-08-22 and 08-26 copies), corrected before version control -- unrelated to EPA.

### What the CA value touched, and what was done

| Where | Effect of CA | Action |
|---|---|---|
| H-PROCUREMENT-01 | GOODFELLOW BROS. CALIFORNIA, LLC counted as a same-state near-miss; the Wenatchee entity refused as out of state | **v1.4 re-run (HR-0081): real hit.** GOODFELLOW BROS, LLC (Wenatchee WA) passes identity in the HQ state: 3 contracts + 1 IDV, $2.8M (Department of Transportation 2, Defense 2; largest the Mauna Loa access road repair, $2.6M). The Livermore LLC is now an out-of-state near-miss, not counted. Assistance: absent. **1 row quarantined, census sheet `H-PROCUREMENT-01__v1.4__review.md`** |
| H-BREACHPORTAL-01 (HR-0069, published) | the scoped absence was claimed against the California DOJ list | **v1.2 re-run (HR-0082): the Washington AG list (1,869 notifications, live) holds no Goodfellow listing -- the licensed absence stands on the correct portal.** Population 0, **quarantined for your publish decision**. HR-0069 annotated in `known_issues` |
| H-LOCALRECORDS-01 (HR-0072, published) | its WARN attempt was scoped to California | annotated in `known_issues`: WA WARN is out of scope, and WARN routes to no theme. **Permit records hold no Goodfellow entity at all** (token GOODFELLOW: 0 permits in Seattle, Chicago and Austin; 0 Seattle council matters), so there was nothing to re-run |
| H-SAFETY-ENV-01 | blank before session 16, so OSHA was never queried | not re-run; with WA set, an OSHA query for Goodfellow is now possible |

**So the same-city question resolved itself differently than the Livermore fill would have:** the Livermore LLC is a
regional registration and fails the standard, and the company's own Wenatchee registration is the hit. All 12 of the
original procurement near-misses are now resolved.

**Directionality note:** the new procurement row is `federal_prime_contracts` and is not tagged (rows written after the
backfill are not tagged automatically); the backfill script's 36-row guard now reads 37 and would exit 2 by design.

**For Matthew:** (1) the one-row census; (2) whether to publish H-BREACHPORTAL-01 v1.2 (HR-0082).

State: 716 observations (715 released, 1 quarantined), 82 runs, 6,864 attempts.
