# H-FIRSTPARTY-01 v1.3 offline dry run (2026-09-15)

**What ran.** The v1.3 harness (article-body extraction, `harnesses/h_firstparty_01/body.py`) replayed offline from the
archived search and page cache of v1.2's run HR-0041, with the run date pinned to 2026-09-03 so staleness cut-offs
match. The workbook was loaded in memory and could not be saved; nothing was written. The harness is ON HOLD
(`core/holds.py`): an offline replay without `--commit` is the only mode it allows. Compared against the 230 live
H-FIRSTPARTY-01 rows and against an unchanged v1.2 replay of the same cache.

## Counts

| | rows |
|---|---|
| live H-FIRSTPARTY-01 rows | 230 |
| reproduced by the unchanged v1.2 replay (replay fidelity) | 229 (not reproduced: O00359) |
| v1.3 proposals | 113 -- reconciler: 113 proposed = 112 valid (3 inserted, 28 refreshed, 79 unchanged, 2 held for review) + 1 recorded invalid (left as recorded) |
| unchanged | 79 |
| content changed | 31 |
| no longer produced | 119: 10 already recorded invalid, 109 not (94 machine, 15 human-reviewed) |
| new proposals (no live row) | 3 |

**Every row already recorded `invalidated_extraction_defect` is gone** (the seven page-furniture rows and the three Caddell
cookie-banner rows). **O00349 is still proposed** -- correctly: its match is in the article; it is invalid for identity
(`invalidated_wrong_entity`), and the reconciler counts it as recorded invalid and leaves it as recorded.

## Why the no-longer-produced rows are lost

| reason | all lost | not already invalid |
|---|---|---|
| theme not in the article body | 114 | 104 |
| page rejected: not about this company: distinctive token | 5 | 5 |

**Recoveries the five fixes were for.** O00307 (the press-release bullet, defect 1): proposed. The four Yahoo Finance pages the first body-only composition cut to ~90 characters (defect 2) now extract as whole articles: O00341 and O00509 are reproduced; O00474 and O00508 are not, and correctly -- their only matched term is Yahoo's `Cybersecurity` navigation label (full-page line 96), which is in neither article body.

**O00440** (A015, `ot_modernization`, matched ['PLC']): theme not in the article body; term(s) on full-page line(s) [82], none in the body. The page is Construction Dive's press-release template, which carries no end-of-article marker; its body now ends at the site's copyright line ("(c) 2025 TechTarget ... An Informa PLC company."), the same furniture O00484 and O00529 matched `PLC` on.

## Coverage the run would record

| | v1.2 replay | v1.3 replay |
|---|---|---|
| attempts_total | 108 | 108 |
| attempts_covered | 50 | 40 |
| attempts_absent_confirmed | 55 | 65 |
| attempts_not_covered | 3 | 3 |
| coverage_rate | 0.9722 | 0.9722 |

The rate does not move (a confirmed absence is coverage); ten companies move from `covered` to `absent_confirmed` --
their only first-party theme evidence was page furniture.

## Extractor behaviour on the pages it read

- 138 pages carried body statistics; end-of-article marker found on 25; consent elements removed on 35; footer notices dropped on 3; footer cut on 3; list items kept on 26 pages (181 items).
- Pages rejected as not about the company: 62 in v1.3, 64 in v1.2 (identity is now read from the body; five live rows are lost to it, listed below).

## What a run would do -- decisions, not taken here

- The harness stays ON HOLD. The five extraction prerequisites have landed and are verified on the 111 pages (`core/tests/test_firstparty_body.py`); this dry run is the measurement the hold's last condition asks for. Lifting it is Matthew's reviewed decision.
- Under convention 45 and Matthew's item 4, the 94 machine rows no longer produced would be recorded invalid, not removed. Through `--retire-stale` they would be `invalidated_not_reproduced`; whether they should instead be `invalidated_extraction_defect` (the reason for most of them) is open.
- The 15 human-reviewed rows no longer produced are HELD by the reconciler (convention 35); a machine run cannot invalidate them.
- A committed v1.3 run is quarantined until audited (the gate); its content-changed rows lose their audit verdicts.

## Rows no longer produced

| row | company | topic | review | reason |
|---|---|---|---|---|
| O00285 | C0001 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00295 | C0008 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00297 | A007 | data_analytics_ai | machine | page rejected: not about this company: distinctive token |
| O00298 | A007 | digital_transformation_process | machine | page rejected: not about this company: distinctive token |
| O00299 | A012 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00301 | A015 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [112, 238], none in the body |
| O00302 | A015 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [116, 242], none in the body |
| O00303 | A015 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [112, 238], none in the body |
| O00306 | A019 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00309 | A026 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [120, 125, 254], none in the body |
| O00310 | A026 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00311 | A027 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00312 | A029 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00313 | A029 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00314 | A029 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00316 | A031 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00317 | A033 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [124, 270], none in the body |
| O00322 | A037 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [120, 246], none in the body |
| O00329 | A046 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00330 | A047 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00339 | A051 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [240], none in the body |
| O00345 | A065 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00348 | A072 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00350 | A073 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00354 | A083 | data_analytics_ai | machine | page rejected: not about this company: distinctive token |
| O00355 | A083 | workforce_enablement | machine | page rejected: not about this company: distinctive token |
| O00357 | A088 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [127, 133, 241, 258], none in the body |
| O00358 | A088 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [122, 230, 248], none in the body |
| O00361 | A097 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00363 | A098 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [53, 134, 142, 353], none in the body |
| O00413 | C0001 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00414 | C0002 | systems_integration | machine | theme not in the article body; term(s) on full-page line(s) [11], none in the body |
| O00415 | C0002 | systems_integration | human | theme not in the article body; term(s) on full-page line(s) [11], none in the body |
| O00417 | C0002 | systems_integration | machine | theme not in the article body; term(s) on full-page line(s) [11], none in the body |
| O00424 | C0006 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00425 | C0007 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00427 | C0008 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00429 | A002 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00431 | A007 | workforce_enablement | machine | page rejected: not about this company: distinctive token |
| O00432 | A011 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00435 | A012 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00436 | A015 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [275], none in the body |
| O00437 | A015 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [279], none in the body |
| O00438 | A015 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [275], none in the body |
| O00440 | A015 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [82], none in the body |
| O00441 | A015 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [6], none in the body |
| O00443 | A019 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00444 | A019 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00445 | A019 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00446 | A019 | systems_integration | human | theme not in the article body; term(s) on full-page line(s) [442], none in the body |
| O00447 | A019 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00448 | A019 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00449 | A026 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [12, 136], none in the body |
| O00450 | A026 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [303], none in the body |
| O00454 | A026 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00455 | A027 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00458 | A029 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00460 | A029 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00463 | A029 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00464 | A029 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00465 | A031 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00466 | A031 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00467 | A032 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00470 | A033 | cybersecurity | human | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00471 | A033 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [307], none in the body |
| O00472 | A033 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [284], none in the body |
| O00474 | A035 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00476 | A035 | ot_modernization | human | theme not in the article body; term(s) on full-page line(s) [311], none in the body |
| O00477 | A035 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00480 | A036 | systems_integration | machine | theme not in the article body; term(s) on full-page line(s) [132], none in the body |
| O00482 | A037 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [283], none in the body |
| O00484 | A039 | ot_modernization | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [301], none in the body |
| O00485 | A039 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [256], none in the body |
| O00486 | A039 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [293], none in the body |
| O00487 | A043 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00489 | A043 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00491 | A046 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [256], none in the body |
| O00492 | A046 | ot_modernization | human | theme not in the article body; term(s) on full-page line(s) [293], none in the body |
| O00493 | A046 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00494 | A047 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00498 | A048 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00501 | A048 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00506 | A051 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [277], none in the body |
| O00508 | A052 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00511 | A052 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00513 | A055 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00514 | A056 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [69, 209], none in the body |
| O00515 | A056 | systems_integration | machine | theme not in the article body; term(s) on full-page line(s) [66], none in the body |
| O00516 | A056 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [69, 198], none in the body |
| O00517 | A056 | systems_integration | machine | theme not in the article body; term(s) on full-page line(s) [66], none in the body |
| O00518 | A064 | systems_integration | machine | theme not in the article body; term(s) on full-page line(s) [127], none in the body |
| O00519 | A065 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00522 | A072 | digital_transformation_process | machine | theme not in the article body; term(s) on full-page line(s) [15], none in the body |
| O00523 | A072 | digital_transformation_process | human | theme not in the article body; term(s) on full-page line(s) [15], none in the body |
| O00524 | A072 | digital_transformation_process | machine | theme not in the article body; term(s) on full-page line(s) [15], none in the body |
| O00525 | A072 | digital_transformation_process | machine | theme not in the article body; term(s) on full-page line(s) [15], none in the body |
| O00526 | A072 | digital_transformation_process | human | theme not in the article body; term(s) on full-page line(s) [15], none in the body |
| O00528 | A072 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00529 | A073 | ot_modernization | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [284], none in the body |
| O00531 | A073 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00533 | A075 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [245, 262], none in the body |
| O00534 | A075 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [293], none in the body |
| O00535 | A075 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [236, 253], none in the body |
| O00536 | A075 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [284], none in the body |
| O00538 | A075 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00539 | A076 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [125, 127, 149, 150], none in the body |
| O00542 | A076 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [142, 144, 166, 167], none in the body |
| O00544 | A076 | data_analytics_ai | INVALID (invalidated_extraction_defect) | theme not in the article body; term(s) on full-page line(s) [134, 136, 158, 159], none in the body |
| O00546 | A080 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116, 488], none in the body |
| O00548 | A082 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00549 | A084 | cybersecurity | machine | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00553 | A088 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [289], none in the body |
| O00554 | A088 | ot_modernization | machine | theme not in the article body; term(s) on full-page line(s) [280], none in the body |
| O00555 | A090 | cybersecurity | human | theme not in the article body; term(s) on full-page line(s) [96], none in the body |
| O00558 | A090 | data_analytics_ai | machine | theme not in the article body; term(s) on full-page line(s) [12, 581], none in the body |
| O00560 | A097 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00561 | A097 | workforce_enablement | human | theme not in the article body; term(s) on full-page line(s) [116], none in the body |
| O00562 | A098 | digital_transformation_process | machine | theme not in the article body; term(s) on full-page line(s) [49], none in the body |
| O00563 | A098 | workforce_enablement | machine | theme not in the article body; term(s) on full-page line(s) [116], none in the body |

## Rows whose content changes

| row | company | topic | fields |
|---|---|---|---|
| O00291 | C0006 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00293 | C0006 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00294 | C0006 | data_analytics_ai | observation_text, evidence_excerpt |
| O00300 | A012 | erp_core_systems | evidence_excerpt |
| O00304 | A019 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00305 | A019 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00307 | A019 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00308 | A019 | data_analytics_ai | evidence_excerpt |
| O00315 | A029 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00318 | A033 | data_analytics_ai | observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00319 | A033 | digital_transformation_process | observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00320 | A034 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00321 | A035 | data_analytics_ai | observation_text |
| O00324 | A038 | data_analytics_ai | observation_text, evidence_excerpt |
| O00326 | A038 | workforce_enablement | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00327 | A039 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00328 | A043 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00332 | A048 | data_analytics_ai | evidence_excerpt |
| O00333 | A048 | transportation_fleet_systems | evidence_excerpt |
| O00335 | A048 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00337 | A048 | data_analytics_ai | observation_text, evidence_excerpt |
| O00342 | A052 | data_analytics_ai | observation_text, evidence_excerpt |
| O00343 | A052 | transportation_fleet_systems | observation_text, evidence_excerpt |
| O00344 | A055 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00349 | A073 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt |
| O00351 | A075 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00353 | A080 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00360 | A097 | data_analytics_ai | signal_strength, observation_text, evidence_excerpt, source_grade, confidence_0_1 |
| O00478 | A036 | data_analytics_ai | evidence_excerpt |
| O00504 | A051 | cybersecurity | evidence_excerpt |
| O00510 | A052 | systems_integration | evidence_excerpt |

## New proposals

| company | topic | source |
|---|---|---|
| A099 | data_analytics_ai | https://www.prnewswire.com/news-releases/autonomous-construction-equipment-company-teleo-announces-customer-deals-and-global-expansion-with-new-dealer-partner-network-301765472.html |
| A099 | systems_integration | https://www.prnewswire.com/news-releases/autonomous-construction-equipment-company-teleo-announces-customer-deals-and-global-expansion-with-new-dealer-partner-network-301765472.html |
| A099 | transportation_fleet_systems | https://www.prnewswire.com/news-releases/autonomous-construction-equipment-company-teleo-announces-customer-deals-and-global-expansion-with-new-dealer-partner-network-301765472.html |
