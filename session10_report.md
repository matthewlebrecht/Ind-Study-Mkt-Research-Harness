# Session 10 Report — Gate Triage Resolution + Job-Posting Pipeline

**Date:** 2026-09-03
**Brief:** session 10, ten items. Everything below ran unattended; nothing is committed.
Matthew released H-FIRSTPARTY-01 v1.2 on a 30-of-169 sample before the session started
(29 supported, 1 overgraded), so that batch stands reviewed.

## The ten items, in one screen

| # | item | outcome |
|---|---|---|
| 1 | Staleness: 5 years everywhere | **Done.** One constant, `core/windows.py`, imported by both harnesses that enforce a window. No file encoded a different admission window; the 36-month figure in H-SAFETY-ENV-01 is a reported recency subset, not a gate, and is left as such with its comment corrected. CLAUDE.md's "5 years vs the 36-month standard" note is retired. |
| 2 | W8 replatform refusal → confound-admitted | **Done, H-WAYBACK-01 v1.3.** Distinct marker, same tier. Replay: 5 rows (Caddell 100% gone peak 2017, Lynden 75% peak 2021, three more), all quarantined. Convention 41 amended to say a confound is a third case. |
| 3 | Characterisation vs action | **Built, H-TRADEPRESS-01 v1.5.** New signal type ST-PRESSCHAR (`trade_press_characterization`, IC2, registered): the company describing itself or its intent as reported ("says it is integrating", "plans to deploy", "has integrated") writes as `buyer_articulates` at C / weak_clue / 0.4 with the state read from the sentence. `ACTION_RE` unchanged; journalist-only framing still generates nothing and is logged. Propagation checked: no other harness has an action regex; H-FIRSTPARTY-01 and H-EXECVOICE-01 already carry intent-vs-done through `organizational_state`. §3. |
| 4 | Outlet allowlist as a coverage question | **Scoped and applied.** Ten trade outlets added by vertical (15 refused results were exactly this class); company domains (50), vendor sites (23), aggregators (22), wires and review sites stay excluded, each with the reason. Scoping document with the LinkedIn-precedent safeguards: `docs/diagnostics/tradepress_allowlist_scoping_2026-09-03.md`. First measurement is the next live run. |
| 5 | P16 "manufacturing defect" alone | **Done, H-PRODUCTQUALITY-01 v1.4.** Bare symptom phrase writes at C / weak_clue / 0.35, state unknown, marked. |
| 6 | Bug fixes | **All eleven fixed.** §6, with one consequence to see. |
| 7 | Job-posting pipeline | **Built and run live, H-JOBPOST-01 v1.4.** Own-domain readability 13 → **17 of 108**. The "12 inline lists" were 1; the "18-platform long tail" has exactly one buildable adapter (ADP) and two robots-refused hosts. §7. |
| 8 | EXECID low-grade tier | Not scoped, per the brief. Flagged in "What needs you". |
| 9 | SAFETY-ENV S7/S25/S21 | Untouched. But see §6: the ordered S24 fix changed 64 rows' content. |
| 10 | LEGAL L14/L12/L21/L22 | No action, confirmed. |

**State:** 525 observations (387 released, 138 quarantined; 188 low-grade), 56 runs. 11
suites green; 9 validator checks; 26 bindings; ledger clean with 5 acknowledged
retirements (§6). 46 files changed or new. Nothing committed.

---

## 3. Characterisation vs action (item 3)

Trade press carries three kinds of claim about a company, and the harness admitted one:

| kind | example | now |
|---|---|---|
| action, witnessed | "Gilbane rolled out Trunk Tools AI agents across its jobsites" | `buyer_acts`, ST-PRESSPROFILE, unchanged |
| self-characterisation or intent, reported | "Gilbane said it is integrating AI…"; "Gilbane plans to deploy a new ERP in 2027" | **`buyer_articulates`, ST-PRESSCHAR, C / weak_clue / 0.4**, state from the sentence (an intent reads `target_state`) |
| journalist framing | "Gilbane is widely regarded as a leader in construction technology" | nothing, logged (`characterizations_dropped`) |

`INTENT_RE` is where "integrated" and the future tense now live: they were kept out of
`ACTION_RE` because a regex cannot tell the verb from the adjective and an intention is not
behaviour. As self-description they are admissible, and the row says what it is. A sentence
must name the company (the same `is_about_company` test the action route applies) and carry
a theme. The hard invariant is extended: an ST-PRESSCHAR row must be `buyer_articulates`, as
an ST-PRESSPROFILE row must be `buyer_acts`, or the run aborts.

Spot check on synthetic text: "said it is integrating AI agents" → self, data/AI; "plans to
deploy a new ERP" → intent, ERP; "widely regarded as a leader" → dropped; "rolled out … AI
agents" → action. Offline replay (no new outlets fetched): 2 new rows, both low-grade
single-term profile rows already known; the characterisation route wrote nothing from the
archived pages, which is a statement about the 15-company subset's cached articles, not the
rule. First real measurement is the next live run.

## 6. The bug fixes (item 6)

| gate | fix | replay effect |
|---|---|---|
| FMCSA F15/F26 | QCMobile path now reads the operation-classification and cargo-carried sub-endpoints; `_is_private_carriage` is three-valued, so with no classification the for-hire authority gap is **not asserted** and the skip is recorded. **Untested against the API**: no `FMCSA_WEBKEY` is configured here. | 0 new rows; 20 human-reviewed rows held as conflicts (their "as of" text differs on replay, pre-existing) |
| FMCSA F11/F14/F16/F23/F24 | missing-field skips recorded in `known_issues` instead of silent | none |
| SAFETY-ENV S24 | ECHO paged to 500 with a full final page **declared** as a floor (`suppressed_by_cap`); an archived pre-fix page of exactly 100 is treated as a floor | **64 of 131 rows refreshed to v1.3, quarantined**: Teichert's facility count went from 100 (silently capped) to 149 [CAPPED], and OSHA full pages with no Next link are now declared floors. Item 9 said not to re-quarantine these rows; the ordered fix changed their content, so they moved. The 67 unchanged rows stay released. Review sheet drawn (30 of 64). |
| SAFETY-ENV S19/S20/S16 | rows that do not parse are counted per search; an unparseable violation count is unknown, not zero, and the text says how many are excluded; a full page with no Next link is a floor | folded into the 64 above |
| TRADEPRESS T46 | `extract_quotes` rejections kept in the page note | run-log only |
| TRADEPRESS T10 | page-budget cap recorded per company and in the run log | run-log only |
| EXECID E37 / EMPREVIEW R9 | a failed search fallback is `source_unavailable` / transient, not `source_not_found` | routing only; no replay (EXECID writes executives; EMPREVIEW's source is blocked) |
| EXECVOICE E15 | company-identity test tightened to FIRSTPARTY's all-token rule | v1.5 replay: the 5 released human rows reproduce, 3 held; **the single v1.4 low-grade row is no longer proposed**, its page fails the tightened test |
| PRODUCTQUALITY P14 | LEGAL's token-prefix rule added to the firm-name test | first replay rejected all three Mack Molding recalls for Mack Group (the rule was not consulting the seeded alias, which LEGAL's does); fixed to test canonical name **and** aliases; second replay matches them |
| shared C6 | `suppressed_generic_only` added to `GOVERNANCE_SUPPRESSIONS` and the `failure_category` vocabulary (Lookups) | none today |

**The ledger.** Five observation ids present at HEAD are gone: O00564 (EXECVOICE v1.4 low-
grade, dropped by E15), O00565–O00566 (TRADEPRESS v1.4 low-grade, renumbered), O00567–O00568
(PRODUCTQUALITY v1.3 low-grade, renumbered). The renumbering is the delete-and-rewrite side
effect flagged in session 4: those harnesses delete their unreviewed rows on commit and
reinsert them under new ids. All five were machine-written and unreviewed; the content of
four of them is back under new ids. Acknowledged with `--retired`; the ledger is clean.

## 7. Job-posting pipeline (item 7)

### What the measurement said before building

- **Inline static lists.** The audit's loose heuristic (class names containing "position" or
  "listing") counted 12. A strict rule against the archive — anchors whose href looks like a
  job detail, with a role word in a multi-word title, at least half carrying a location or
  level qualifier — finds **1** (OnTrac, 4 titles). The other eleven were careers-section
  navigation: "Benefits and Perks", "Learn More Corporate", "Estimators". The first live run
  of the adapter proved the point by admitting three sites' navigation; the rule above is
  the corrected one and it now returns nothing for those three.
- **The long tail.** Probed one company per platform, robots-gated:

| platform | companies | finding |
|---|---:|---|
| Dayforce | 6 | board host refuses this crawler by robots.txt |
| UltiPro / UKG | 4 | board host refuses this crawler by robots.txt |
| **ADP Workforce Now** | 4 | **public JSON requisition endpoint, robots-permitted** — built |
| Jobvite, Taleo | 5 | board not reachable from the careers page (JS) |
| SuccessFactors | 2 | serves a login page |
| Tenstreet | 2 | an application form, no listing |
| BambooHR | 2 | link is the vendor homepage |

So "start with Dayforce" is not available to a compliant crawler, and the pipeline has one
adapter, not eighteen. Dayforce and UltiPro companies are now recorded as
`access_blocked` / `source_limitation` with the reason (10 companies), which routes the fix
correctly instead of "no adapter".

### What v1.4 built and ran

ADP adapter (client id captured from the careers page, paged by 50, total measured); inline
adapter (the strict rule); robots-refused board categories; re-discovery when a stored
config cannot be acted on; and the three deferred conversions — J6 (volume under the
5-posting floor at low grade), J13 (AWS/Azure/GCP, mainframe, devops/SRE without migration
language write the signal at low grade; the dictionary-word terms keep their identity
refusal), J32 (iCIMS read to the page bound is flagged truncated). Classifier v1.3, 65
checks.

Live run (HR-0056, 72 requests; discovery pages cached from the morning's run):

| | v1.3 (last night) | **v1.4** |
|---|---:|---:|
| own-domain readable | 13 / 108 | **17 / 108** (ADP: Clancy & Theys 12 postings, Petersen 19, FCL Builders 19; inline: OnTrac 4) |
| own-domain `access_blocked` (robots-refused board host) | 0 | 10 |
| aggregator leg (Talent.com) | 56 / 108 | 56 / 108 |
| rows written | 25 | 16 new or refreshed at v1.4 (1 low-grade: J6 volume) |
| presence hits on the four new keys | 1 | 1 (OnTrac, cloud, unchanged) |

Nicholas and Company (ADP) is the fourth ADP company: its client id is not in the server-
rendered page, and the row says so. The readability denominator is 17 of 108 (15.7%). Depth
is the metric from here: the 17 readable companies carry ~1,700 postings; the 56 aggregator
companies carry 125.

## What needs you

1. **Review sheets, new this session:** H-SAFETY-ENV-01 v1.3 (30 of 64 — the S24
   re-quarantine), H-JOBPOST-01 v1.4 (16), H-WAYBACK-01 v1.3 (5, all confound-admitted),
   H-TRADEPRESS-01 v1.5 (2), H-PRODUCTQUALITY-01 v1.4 (2). Last night's nine remain.
2. **SAFETY-ENV v1.3**: the 64 refreshed rows are the same inspections with honest floors;
   releasing them on the sheet restores the published count. Say if you would rather I had
   held the fix.
3. **Item 8 (EXECID)**: unchanged; the writer needs to accept an empty title before E26/E32
   can be admitted at low grade.
4. **The delete-and-rewrite renumbering** (EXECVOICE, TRADEPRESS, LEGAL, PRODUCTQUALITY,
   FMCSA `--force-rewrite`): every replay of those harnesses will retire and reinsert their
   unreviewed rows under new ids. Session 4 asked for a decision before ids appear in
   findings; that is now.
5. **FMCSA F15/F26** cannot be verified without an `FMCSA_WEBKEY`.
6. Carried, unaffected: O00369 / O00373; the Harness Advisor ping.

## Files

New: `core/windows.py`, `docs/diagnostics/tradepress_allowlist_scoping_2026-09-03.md`,
`docs/diagnostics/gap_report_after_session10_2026-09-03.txt`, review sheets and strata for
the five new versions. Modified: ten harness packages (code + manifests), `core/topics.py`,
`core/attempts.py`, `scripts/migrate_schema.py`, `scripts/register_sources.py`,
`docs/conventions.md`, `README.md`, `CLAUDE.md`, the workbook (Signal_Types + Lookups +
runs + rows), `data/snapshots/gap_report.csv`.
