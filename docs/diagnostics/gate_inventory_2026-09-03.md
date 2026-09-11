# Gate inventory and corroboration-gate policy pass — 2026-09-03 (session 9, item 6)

**Rule applied (Matthew, 2026-09-03; convention 41).** Every point where a harness refuses
to write an observation was located and classified as one of:

- **Corroboration-strength** — the pattern is plausible and the referent is correct, but the
  claim is not independently strong enough to stand alone → **converted** to write-at-low-grade:
  `source_grade C`, `signal_strength weak_clue`, `confidence ≤ 0.4`, `evidence_excerpt` prefixed
  `[low-grade: <gate>; corroboration-strength gate relaxed 2026-09-03, review before use]`.
- **Identity-matching** — wrong company, dictionary-word-only token, PR-wire/index page,
  eponymous trap, generic-homepage substitution, wrong speaker → **unchanged**, refuse-to-write
  stays in force.
- **Unclear** — fits neither cleanly → **not converted; logged here for Matthew's decision.**

Row ids below (F1, S9, T26 …) are the ids in the four inventory transcripts this table
condenses. "Not a gate" rows (schema checks, dedupe, budget caps, dry-run mechanics,
publication defaults, universe filters) are listed once at the end rather than per harness.
Per-harness effect is the offline replay committed tonight, all output **quarantined**.

## Methodology framing

Two kinds of uncertainty were being handled the same way. **Confidence-tier uncertainty**
(how strong is this claim about the right thing?) is now captured, graded and reviewed: the
row exists and carries its tier. **Referent error** (is this even about the right thing?) is
still excluded at extraction, because a lower grade cannot rescue a row about the wrong
company or the wrong speaker — it can only put it in front of a reviewer and into a count.

## Summary by harness

| harness | gates found | converted | identity (unchanged) | unclear (logged) | version | replay result |
|---|---:|---:|---:|---:|---|---|
| core/topics.py (shared spine) | 4 | 2 | 1 | 1 | — | `classify_tiered()` added; `classify()` unchanged |
| H-SELLERCONTENT-01 | 21 | 1 (spine) | 5 | 15 | v1.3 → v1.4 | 13 rows, 10 low-grade |
| H-FIRSTPARTY-01 | 26 | 2 | 12 | 12 | v1.1 → v1.2 | 169 rows, 152 low-grade |
| H-EXECVOICE-01 (quotes.py) | 31 | 2 | 15 | 14 | v1.3 → v1.4 | 1 row, low-grade; 3 human rows held |
| H-TRADEPRESS-01 | 74 | 3 | 38 | 33 | v1.3 → v1.4 | 2 rows, low-grade; 1 human held |
| H-LEGAL-01 | 28 | 1 | 17 | 10 | v1.1 → v1.2 | 0 new rows (no non-commercial vendor docket passed identity); 1 human held |
| H-PRODUCTQUALITY-01 | 28 | 1 | 9 | 18 | v1.2 → v1.3 | 2 rows, low-grade; 1 human held |
| H-FMCSA-01 | 39 | 5 | 14 | 20 | v1.3 → v1.4 | 9 rows, low-grade; 20 human rows held |
| H-SAFETY-ENV-01 | 30 | 0 | 10 | 20 | v1.2 (unchanged) | not re-run |
| H-WAYBACK-01 | 17 | 1 | 1 | 15 | v1.1 → v1.2 | 7 rows, low-grade |
| H-JOBPOST-01 | 42 | 0 (2 deferred) | 15 | 25 | v1.3 (live run tonight) | 25 rows, 0 low-grade |
| H-EXECID-01 | 42 | 0 (3 deferred, schema) | 27 | 15 | v1.0 (unchanged) | not re-run |
| H-EMPREVIEW-01 | 29 | 2 | 6 | 21 | v1.0 → v1.1 | 0 rows (source blocked) |

**183 low-grade rows exist as of tonight, all quarantined.** `gap_report.py` excludes them
by default (`--include-low-grade` to see the counts with them).

## Converted gates (write-at-low-grade)

| harness | gate (inventory id) | what it refused | now |
|---|---|---|---|
| spine | generic-tier only, `corroboration="any"` (S9/T67/R16) | one generic term, e.g. bare "integration", "AI", "SAP", "Lean", "AMR" | `classify_tiered` returns it as `weak`; each consuming harness writes it at C / weak_clue / 0.3 |
| spine | cloud `corroboration="specific"` (S10/T68/R17) | legacy-estate + vendor terms without a migration term | same, with "legacy estate / vendor named, migration not asserted" reasoning in the row |
| SELLERCONTENT | generic-only theme on a provider page (S9–S11) | theme dropped | v1.4: row at C, text says "mentions, on generic terms only" |
| FIRSTPARTY | "two distinct terms or headline" (F20) | theme dropped, logged `theme_below_threshold` | v1.2: row at C / 0.4, marker "single generic term, not in the headline"; log entry keeps `written_low_grade: true` |
| FIRSTPARTY | spine generic-only (F19) | page skipped | v1.2: row at C / 0.3 |
| EXECVOICE quotes | quote under the 60-char floor (E18) | rejected `length` | 40–59 chars admitted with `weak_reason`; confidence 0.3/0.4 |
| EXECVOICE quotes | quote whose only theme is generic-tier (E24) | rejected `no_modernization_theme` | admitted with `weak_reason`; row at C when every quote on the theme is weak |
| TRADEPRESS | wire-reprint single-term theme (T26) | silently dropped | v1.4: `build_routed_firstparty(low_grade=True)` at C / 0.4 |
| TRADEPRESS | PRESSPROFILE action single-term theme (T61) | `below_admission` note only | v1.4: `build_action(low_grade=True)` at C / weak_clue / 0.4 |
| TRADEPRESS | quote gates via quotes.py (T39, T45) | as EXECVOICE | inherited |
| LEGAL | nature-of-suit whitelist (L15) | vendor docket under ERISA / PI / blank nature dropped | v1.2: row at C / 0.35, basis says the nature is not commercial; **every identity condition still applies first** |
| FMCSA | nil fleet return (F12) | skipped as noise | v1.4: `fleet_scale` at C / 0.4, state unknown |
| FMCSA | OOS rate below 20 inspections (F17) | skipped | v1.4: the COUNTS at C / 0.4, no rate, no state; **zero inspections still skipped** (nothing to grade) |
| FMCSA | zero crashes (F19) | silently skipped | v1.4: "0 crashes" at C / 0.4 |
| FMCSA | MCS-150 inside the biennial window (F21) | skipped | v1.4: 12–24 months old written at C / 0.35 as "approaching"; the ACTIVE requirement kept |
| FMCSA | driver count within the 25% band (F25) | skipped | v1.4: at C / 0.35 |
| WAYBACK | single-capture removals (W6) | dropped **and recorded as `absent_confirmed`** | v1.2: row at C / 0.3 when no multi-capture removal exists; attempt `covered`; the absent_confirmed mislabel is gone |
| PRODUCTQUALITY | same-sentence rule, split (P17) | cue in one sentence, failure predicate in another → dropped | v1.3: at C / 0.35, state unknown; **cue with no predicate anywhere still refused** (the Midmark record is false, not weak) |
| EMPREVIEW | one review on one term (R12) | held in `themes_below_threshold` | v1.1: row at C / 0.3 |
| EMPREVIEW | sample under the 5-review floor (R10) | company `not_covered` | v1.1: themes written at C, attempt `partial`; inert today (source blocked) |

## Corroboration-strength gates NOT converted tonight, with the reason

| harness | gate | reason deferred |
|---|---|---|
| JOBPOST | `MIN_POSTINGS_FOR_VOLUME = 5` (J6) | v1.3 ran live tonight and its 25 rows are drawn for audit; changing the harness under an unaudited version would make that audit non-reproducible. Convert in v1.4 with J13. |
| JOBPOST | `requires` on AWS/Azure/GCP, mainframe, devops/SRE (J13, vendor subset only) | as above. The dictionary-word subset of `requires` (AI, BI, Oracle, lean, innovation, transformation) is identity and stays. |
| JOBPOST | iCIMS 6-page loop not flagged as truncation (J32) | a reporting bug, not a policy question: set `truncated` when the loop exits on the bound. Cheap; next JOBPOST version. |
| EXECID | out-of-vocabulary title dropped outright (E26); name without adjacent title (E32); best-page-only merge (E15); 40-person cap (E34) | executive rows, not observations; E26/E32 need `db.sync_executives` to accept an empty title (schema change). Decision needed on whether `Company_Executives` gets a low-grade tier at all. |
| SAFETY-ENV | `absent_confirmed` never written as a negative observation (S7); unknown-status facilities dropped from the violating count (S25); 2016 window (S21) | S7 would add ~100 "no record" observations and change what an absence row means; S25/S21 are text-only changes that would re-quarantine 131 grandfathered rows. All three are yours to decide. |
| SELLERCONTENT | JS-shell text floor `MIN_TEXT_CHARS` (S1) | reachability floor, not evidence weight; classifying a 1,600-char shell would grade noise. Logged as unclear. |

## Unclear — logged for Matthew's decision (not converted)

| harness | gate | why it fits neither category |
|---|---|---|
| FIRSTPARTY, TRADEPRESS | 5-year staleness window (F18, T23) | temporal validity: right referent, real claim at its date. A third bucket ("historical context at reduced confidence") is the obvious shape; not invented here. |
| TRADEPRESS | characterisation-vs-action (T55); `ACTION_RE` excludes "integrated" and future tense (T56) | evidence-TYPE rules (who witnessed what; intent vs behaviour). "integrated" alone is arguably corroboration-strength; the harness comment argues against admitting it at any grade. |
| TRADEPRESS | outlet allowlist (T8) | partly identity (ZoomInfo/RocketReach/LinkedIn substitutes), partly a provenance scope. |
| WAYBACK | replatform refusal (W8); `RELEVANT_PATH` topical filter (W4); inside-2-year window (W7); pre-2015 (W16) | W8 is a causal confound with an affirmative competing explanation, not a weak claim; W4 is subject relevance; W7/W16 are windows. |
| FMCSA | inactive −15 and MCS-150-age scoring inside the identity test (F4, F5); private-carriage inference blind on the QCMobile path (F15/F26); missing-field skips (F11, F14, F16, F23, F24) | record currency used as identity evidence; a static defect (`operation_classification` is `[]` with `FMCSA_WEBKEY` set) that needs a fix, not a grade. |
| SAFETY-ENV | ECHO `responseset=100` undeclared cap (S24); silent short-row drops (S19); violation-count coercion to 0 (S20); parser fragility (S16) | reporting defects, not policy. S24 is the same silence convention 7 exists to prevent. |
| LEGAL | mass-action cap (L14, identity-ish); theme-from-caption route removed (L12/L21, identity); NLRB structurally incapable (L22) | co-occurrence-is-not-a-relationship tests; nothing to grade. |
| PRODUCTQUALITY | second-tier cue vocabulary, e.g. "manufacturing defect" (P16); population map (P2–P4); firm-name identity without the prefix test LEGAL applies (P14, asymmetry) | P16 names a symptom, not a system — concept-referent, not strength. P14 is a defect to align, not a gate to relax. |
| EXECVOICE, TRADEPRESS | own-domain / wire partition (E8, E9): a quote on the company's own site is refused by both harnesses when H-FIRSTPARTY-01 has no coverage | a portfolio-partition rule; the quote is lost, not graded. |
| EXECVOICE | `any`-token company test is weaker than FIRSTPARTY's `all`-token test (E15 vs F13) | identity asymmetry: the harness whose failure mode is wrong speaker uses the weaker company test. Tighten, do not loosen. |
| TRADEPRESS | `extract_quotes` rejections discarded (`qs, _rej = …`, T46); 10-page budget silent (T10) | audit gaps: the run log cannot show the refusals it made. |
| EXECID, EMPREVIEW | a failed search fallback can be reported as `source_not_found` (E37, R9) | a reporting conflation `core/search.py` says to avoid. |
| shared | `GOVERNANCE_SUPPRESSIONS` has no value for "admitted nothing because generic-only" (C6) | vocabulary gap: the largest corroboration refusals were invisible to `Attempts`. Moot for the converted harnesses (the row now exists), still true for the unconverted ones. |
| all | quarantine default, dry-run mechanics, reviewed-row conflicts, grade-D refusal, universe filters, dedupe, page/query budgets | not admission gates; listed in the transcripts, not decisions. |

## Identity gates confirmed unchanged (the ones that matter)

`is_about_company` and `COMMON_WORD_NAMES` (FIRSTPARTY, TRADEPRESS, LEGAL, PRODUCTQUALITY);
the 55-point acceptance score and token alignment (FMCSA); `party_is_company` prefix test,
caption-not-party-list, plan-party and short-token vendor exclusions (LEGAL); `resolve()`'s
0.55 floor and every `article.is_about_company` firm test (SAFETY-ENV, PRODUCTQUALITY);
eponymous-surname and full-name-absent attribution (quotes.py); soft-404, index-title,
index-URL, standing-page, aggregator and vendor-content exclusions; Talent.com employer-field
scoring (JOBPOST v1.3); `EXCLUDED_PATH` dated-post filter (WAYBACK); the classifier's
case-sensitive acronyms, dictionary-word `requires` and context `blocks` (JOBPOST); every
name/title shape test in EXECID; `verify_company` on the profile page (EMPREVIEW).

## How to find the low-grade rows

Any one of: `source_grade = C`; `signal_strength = weak_clue` with `confidence_0_1 <= 0.4`;
`evidence_excerpt` starting `[low-grade:`. `gap_report.py` excludes them unless
`--include-low-grade`. Review sheets for every version that wrote them are in
`harness_output/audits/<harness>__<version>__review.md`.
