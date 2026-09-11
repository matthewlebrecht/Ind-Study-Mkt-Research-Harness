# Session 8 Report — Pattern Fix, Diagnostic, H-JOBPOST-01 Signal Keys

**Date:** 2026-09-02
**Brief:** `code_session_pattern_fix_2026-09-02.md` (four parts), sequenced after the
company-count answer in session 7. Signal Advisor's response and the Harness Advisor ping
arrived alongside it; the Harness Advisor ping (composition order, `retrospective_reach`
figures) is **not** acted on here and is not in the brief.

## What you asked for back

**1. The gap-report diff ran, and four divergences moved.** Sellers per theme, before →
after the provider-side pattern fix, from the two captures in `docs/diagnostics/`:

| theme | sellers | share | buyers | status |
|---|---|---|---|---|
| systems_integration | **7 → 1** | 64% → 9% | 4 → 4 | covered |
| cloud_infrastructure_migration | **4 → 2** | 36% → 18% | 0 → 0 | buyer silent → **no absence instrument** |
| data_analytics_ai | **11 → 10** | 100% → 91% | 35 → 35 | covered |
| erp_core_systems | **7 → 6** | 64% → 55% | 3 → 3 | covered |
| ot_modernization | 0 → 1 | 0% → 9% | 0 → 0 | NO INSTRUMENT → no absence instrument |
| cybersecurity | 4 → 4 | 36% | 0 → 0 | buyer silent → no absence instrument |
| the other four | unchanged | | | |

**What was never a finding, stated plainly:** "64% of sellers message systems integration"
rested on the bare word "integration" for six of the seven providers. "36% message cloud
migration" rested on a lone vendor logo (Azure, AWS) for two of the four. "Every provider
messages data/AI" rested on a bare "AI" for one of the eleven, so that statement is now
false as well. None of these was a divergence that flipped from present to absent, because
none had buyer signal to begin with; what moved is how loud the seller side looked. The
direction the brief predicted is the direction it went: every change reduced provider
messaging, none increased it.

**2. The four signal keys are built and mapped.** `cloud_infrastructure_hiring`,
`cybersecurity_hiring`, `workforce_enablement_hiring`, `ot_modernization_hiring` in
`harnesses/h_jobpost_01/classifier.py` (v1.2), each in `core/topics.py::BUYER_SIGNAL_TO_THEME`,
which now covers all 10 themes. Condition 3 held from the start: a bare AWS/Azure/GCP is
not a signal, and the suite asserts it in both directions (65 checks). An offline replay of
the ~1,560 archived postings from the readable companies finds **0 hits** for the four keys,
after the first dry run produced two and both were false ("Quality Control Technician" and
"QA Document Control Specialist II" as OT modernization). Fixed and tested before anything
was written. §4.

**3. The JS-rendering denominator, measured, not estimated.** `scripts/careers_readability.py`,
from H-JOBPOST-01's own `Attempts` rows on HR-0036:

| bucket | companies | share |
|---|---:|---:|
| readable: postings parsed through a known ATS adapter | **14** | **13.0%** |
| careers page found, no ATS detectable in server-rendered HTML (JS-rendered or bespoke) | 60 | 55.6% |
| careers page found, known ATS with no adapter (dayforce 6, adp 4, ultipro 4, tenstreet 2, bamboohr 2, jobvite 2, +3) | 23 | 21.3% |
| no careers page found on own domain | 8 | 7.4% |
| known ATS adapter parsed 0 postings / adapter HTTP failure | 3 | 2.8% |

**94 of 108 companies have postings this harness structurally cannot see**, and the 14 it
can see are the ones on a modern hosted ATS, not a random draw. So absence across the four
new keys, and across the six old ones, licenses nothing. `gap_report.py` now says so:
`Theme.absence_licensed = False` for cloud, cybersecurity, workforce enablement and OT, and
their status prints "no absence instrument" instead of "buyer silent". The 23 known-ATS
companies are the cheapest way to raise the denominator: three adapters (Dayforce, ADP,
UltiPro) would add 14 companies and double it.

---

## 1. The "before" capture

Taken before any pattern change, as the brief required, to
`docs/diagnostics/gap_report_before_pattern_fix_2026-09-02.txt`. The session-7 follow-up's
refreshed `data/snapshots/gap_report.csv` was the same state, as that brief anticipated.

## 2. The pattern fix (`core/topics.py`)

**Two-tier admission, on `Theme`.** `patterns` is the specific tier and fires alone.
`generic` needs a second, distinct hit in the same text. `exclusions` are blanked out of
the text before either tier is searched. `corroboration` is `"any"` (a second hit of
either tier) or `"specific"` (only a specific hit corroborates). `matches()` returns the
admitted hits or nothing; `refused()` and `classify_refusals()` return what was seen and
declined, so a harness can still report the decline (convention 7). All three fields are in
`definition_hash`, so a tier edit is a definition change (§25.1).

What moved, and where the brief's list actually lived:

| theme | specific (fires alone) | generic (needs a second hit) | exclusion |
|---|---|---|---|
| systems_integration | EDI, iPaaS, middleware, ETL, systems interoperability, data integration | **API, integration** | post-merger integration |
| cloud_infrastructure_migration | cloud migration/modernization/transformation/adoption, lift and shift, data center migration/exit | mainframe, legacy system/application modernization, application modernization, **Azure, AWS, GCP** — `corroboration="specific"` | |
| data_analytics_ai | (+ agentic AI, AI agents/copilots/assistants) | **AI** | |
| erp_core_systems | ERP, S/4HANA, NetSuite, Dynamics 365, Epicor, JD Edwards, core system modernization | **SAP, Oracle, Infor** | |
| digital_transformation_process | unchanged | **Lean** | |
| warehouse_automation | unchanged | **AMR** | |

The brief said to demote Lean, AMR, AI and bare vendor names "wherever they currently fire
alone in either theme's pattern set". None of them lived in the two named themes; they
lived in four others. I applied the instruction as written, to where the terms are, and it
touched six themes rather than two. The effects on committed rows are all in §3, none
hidden. On the ERP vendor names I drew the line at products that are *only* an ERP
(S/4HANA, NetSuite, Dynamics 365, JD Edwards, Epicor stay specific) versus vendor names that
are also a database company, a three-letter word and a prefix of "information".

**Cloud got `corroboration="specific"`** because the brief's wording for it was stricter
than for integration: "require corroboration with a cloud-specific term". Two generic terms
together ("mainframe" + "AWS") describe a legacy estate and a partner logo, not a migration.

**Tests.** `test_schema_delta` §6b, 13 checks, each in both directions: bare "integration"
admits nothing, "API-led integration" admits, "post-merger integration and API governance"
does not; bare "AWS" nothing, "mainframe and AWS" nothing, "AWS cloud migration" admits and
carries AWS as evidence; bare AI / SAP / Lean / AMR nothing, each with its companion admits.

## 3. The diagnostic, both sides

### Provider side: replayed and applied

The gap report counts committed observations, so narrowing a pattern moves nothing until the
harness that wrote the rows is re-run. H-SELLERCONTENT-01 replays offline from its
2026-08-30 archive and the baseline replay reproduced the committed 43 before any change.
Under the new spine it proposes 34. Run as **v1.3, `--offline --commit --retire-stale`**
(HR-0038):

- **10 rows retired**, by name: O00224, O00229, O00233, O00238, O00248, O00253 (six
  `systems_integration` rows on "integration" alone), O00249 (P009 cloud, "Azure" alone),
  O00254 (P012 cloud, "AWS" alone), O00250 (P009 data/AI, "AI" alone), O00257 (P012 ERP,
  "SAP" alone). Exactly the ten predicted from their matched terms before the replay.
- **7 rows now at v1.3, quarantined:** 6 refreshed (text or evidence changed under the new
  rules) and 1 inserted, O00395, Argano's `ot_modernization` row on "SCADA", which the split
  made visible and the pre-fix replay had already proposed.
- **27 rows reproduced byte-for-byte** and stay at v1.2, released. Surviving rows keep their
  ids: retirement is keyed on the natural key of what the run proposed
  (`core/db.py::retire_unreproduced`), not delete-and-rewrite, so the session-4 renumbering
  side effect does not recur. A human-reviewed row is never removed by it; it is held and
  named. None was.

**Gate.** v1.3 is a new version with changed admission, so its 7 rows are quarantined on
write and the gate was loaded fresh after the run. Population 7; every adversarial stratum
sampled 0 (no A-graded rows, no off-domain URLs, no single-common-word matches: providers
are configured, not resolved); random control is a census of all 7. The review sheet is at
`harness_output/audits/H-SELLERCONTENT-01__v1.3__review.md`, for you to judge. As a
judgment aid, each row was re-classified page by page from the cache: every one admits on a
specific-tier term (O00221 Slalom cloud on "Cloud transformation" across both pages, O00395
on "SCADA", the two workforce rows on one term each at `weak_clue`). **No coverage number
for v1.3 is quoted anywhere in this report.** `published_coverage.py` lists it as
quarantined and prints only its row count.

### Buyer side: measured, not applied

All five buyer harnesses that read the spine replay offline. Dry runs under the new spine,
nothing written, with the identified rows:

| harness | committed | proposed | not reproduced | new |
|---|---:|---:|---|---|
| H-FIRSTPARTY-01 | 79 | 78 | O00286 (Midmark, "integration"), O00288 (Kenco, "Companies Lean on AI": both generic), O00339 (Dycom, bare "AI"), O00347 (Cache Valley, "integration") | 3 |
| H-EXECVOICE-01 | 8 | 6 | O00369 ("Our integration is key…", **human-reviewed**), O00373 ("Integrated Lean Project Delivery", **human-reviewed**) | 0 |
| H-TRADEPRESS-01 | 3 | 3 | none, after the fix below | 0 |
| H-LEGAL-01 | 1 | 1 | O00377 routes to no theme on its text; the harness still proposes 1 | |
| H-PRODUCTQUALITY-01 | 1 | 1 | none | |

**What the first tradepress dry run exposed, and what I did about it.** Under the demoted
spine H-TRADEPRESS-01 proposed **0 rows against 3 committed**, all three human-audited AI
quotes: "AI is a transformative force" (Gilbane's CEO, O00364), "an agentic AI system"
(O00376). On a provider's services page a bare "AI" is a slogan; in an attributed
executive quote it is the subject. The brief's condition 4 says buyer-side patterns stay
per harness, so the term went where the text is known to be a quote:
`harnesses/h_execvoice_01/quotes.py::BUYER_VOICE_PATTERNS["data_analytics_ai"]` gains a
case-sensitive `AI`, read by H-EXECVOICE-01, H-TRADEPRESS-01's quote path and
H-EMPREVIEW-01. "agentic AI" and "AI agents" also joined the spine's specific tier: they are
the same class as "generative AI" and had only ever matched through the bare token. Both
quote harnesses bumped to v1.3 (extraction rules changed; every committed row reproduces
unchanged; `reprocessing_required: false`, checked by replay). The spine's demotion of bare
"AI" stands as the brief instructed.

**Why nothing on the buyer side was committed.** Re-running H-FIRSTPARTY-01 with `--commit`
would refresh 13 rows and insert 3 under a new version, quarantining them behind an audit,
and would retire 4 released rows; H-EXECVOICE-01's two are human-reviewed and cannot be
touched by code at all. The brief authorised the provider-side fix and a diagnostic, not a
re-audit of four buyer harnesses. So the buyer counts in the after table are the committed
counts, and the rows above are flagged here for your call. Note the direction: every
buyer-side effect would *reduce* buyer signal, which makes divergences look larger, so
leaving them in place is the conservative choice for the thesis, not the flattering one.

### The regression script's view

`theme_regression.py` against HEAD: 11 of 328 committed rows route differently on their own
text (the buyer rows above plus rows whose *secondary* themes dropped, e.g. H-FIRSTPARTY-01
rows that carried data/AI on a bare "AI" beside their own topic). No retired key anywhere.
The script now diffs the tier fields too, so the inventory line shows exactly which tier
moved per theme.

## 4. H-JOBPOST-01 v1.2: four keys

Specific-tier from the start, with the same three rules the v1.1 classifier documents
(case-sensitive acronyms, ordinary words need a qualifier, context can veto):

- **cloud_infrastructure_hiring:** cloud/infrastructure/platform engineer or architect,
  cloud migration/modernization, lift-and-shift, data-center migration/exit; **AWS/Azure/GCP
  only beside migration or legacy-estate language**; mainframe only beside migrate/modernize/
  decommission; DevOps/SRE only beside a cloud term. Family 5 (names a system).
- **cybersecurity_hiring:** cybersecurity, information security, infosec, CISO, SOC/SIEM
  with a role, IT/OT/network/cloud security; "security engineer/analyst" needs a digital
  qualifier and is vetoed by guard/officer/loss prevention/physical. Family 3.
- **workforce_enablement_hiring:** frontline technology, deskless, workforce management
  system roles, WFM/LMS with a systems role, Kronos/UKG/Dayforce only with an administering
  role, labour management systems, training-and-adoption. Family 3.
- **ot_modernization_hiring:** SCADA/PLC/HMI/DCS (case-sensitive), **controls** engineer
  (plural), control systems engineer, industrial controls, instrumentation & controls, I&C,
  process control, historians, MES with a role, OT with a network/infrastructure qualifier.
  Family 5.

**The false positive, caught on first output.** The first offline dry run admitted two OT
rows: "Quality Control Technician" (Merit Medical) and "QA Document Control Specialist II"
(doTERRA), through `controls? (technician|specialist)`. Convention 16 on the key's first
outing, in the harness whose classifier already documents seven of these. The term is now
plural-only or "control systems", with quality/document/inventory/pest/traffic/loss/cost/
infection/access/version/revenue control vetoed by name, and both titles are in the suite as
negatives beside "Controls Engineer" and "Control Systems Engineer" as positives. Second dry
run: 0 new-key hits across the archived postings, 21 rows would refresh only because the
excerpt names the classifier version, 0 inserted. Not committed: v1.2 has not been run live,
and a replay that changes nothing but a version string is not output worth quarantining.

`ot_modernization` therefore carries `buyer_detectable=True`, `buyer_detectable_since=
"2026-09-02"` (the day an instrument first could see it, per §25.2) and
`absence_licensed=False`. `test_schema_delta` §5 now asserts a theme is detectable exactly
when some buyer key maps to it.

## 5. Plumbing that had to exist for the above

- `core/db.py::retire_unreproduced(harness_id, proposed)` and H-SELLERCONTENT-01
  `--retire-stale` (refuses a `--providers` subset, which would retire everyone else).
- `scripts/check_run_ledger.py` compares Observations **by id** and takes
  `--retired ID,ID,…`: named deliberate removals are acknowledged, any other missing row
  still aborts, a named row that is not missing warns. Verified on all three paths. Run this
  session with the ten ids above; without them it aborts, as it should.
- `scripts/careers_readability.py` (§ "What you asked for back", 3).
- `scripts/gap_report.py` "no absence instrument" status; `data/snapshots/gap_report.csv`
  regenerated.
- H-EMPREVIEW-01 reports spine refusals under `rejected` (its test for a lone "API"
  mention failed the moment the spine started declining it silently — the right failure).

## 6. Verification

11 suites green: `test_jobpost` 65 (was 42), `test_schema_delta` 54 (was 40) / 3 pending,
`test_audit_gate` 56, `test_attempts` 35, `test_tradepress` 34, `test_reconcile` 27,
`test_resolution` 25, `test_productquality` 19, plus empreview, execid and execvoice.
`validate_repo_db` 9 checks (check 9: 8 quarantined runs, 4 audited, 17 grandfathered);
`assert_validations` 26 bindings; `check_run_ledger --strict --retired <10 ids>` clean.

## 7. State at hand-off

**328 observations** (295 released, 33 quarantined), 3,671 attempts, 38 runs, 120 `Companies`
rows = 108 buyers + 12 provider benchmarks, 10 themes (all detectable, four with
`absence_licensed=False`), 1 retired theme key, 24 signal types, 26 bindings.

**Awaiting audit:** H-SELLERCONTENT-01 v1.3 (7 rows, sheet drawn) joins H-JOBPOST-01 v1.1,
H-LEGAL-01 v1.1 and H-PRODUCTQUALITY-01 v1.2.

**Not committed.** 20 modified files, the workbook among them, and these new ones:
`scripts/careers_readability.py`, `docs/diagnostics/` (two captures), the v1.3 review sheet
and strata sidecar, and the three briefs (`files.zip` duplicates them and is left untracked).

## 8. Decisions this leaves with you

1. **The buyer-side rows in §3.** Re-run H-FIRSTPARTY-01 and H-EXECVOICE-01 under the new
   spine (each a new quarantined version, each re-audited), or leave them. The two
   human-reviewed exec quotes (O00369, O00373) need your verdict either way.
2. **Judge the seven v1.3 rows** so H-SELLERCONTENT-01 can publish again at v1.3.
3. **The 23 known-ATS-no-adapter companies** are the cheapest denominator gain
   (Dayforce, ADP, UltiPro adapters: +14 companies).
4. **Harness Advisor's ping** (per-bucket access as a fourth composition stage;
   `retrospective_reach` values for `Harness_Sources`) is unanswered and untouched here.
5. **§25.4 definitions** for `systems_integration` and `cloud_infrastructure_migration`:
   Signal Advisor authorised writing those two; the text has not arrived. The tiers above
   narrowed toward the brief's terms, not toward a definition, and `Theme.definition` is
   still empty for all ten.
