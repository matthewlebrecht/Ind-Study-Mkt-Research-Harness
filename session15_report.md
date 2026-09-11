# Session 15 Report — EXECID Promotion + NAICS Enrichment (Week 3 Close-Out)

**Date:** 2026-09-06
**Brief:** session 15, two items. Both done; both run live and committed. One new open item
surfaced that Week 4 inherits: the Brave search plan's monthly quota is exhausted.

## In one screen

| # | item | outcome |
|---|---|---|
| 1 | EXECVOICE reads EXECID's low-grade names | **Built as v1.6 and run live (HR-0065).** 76 low-grade names searched across 30 companies. **2 new quote rows**, both the same Brian Killinger appointment quote reprinted by two outlets, graded B / `weak_clue` by the unchanged rules, quarantined with a review sheet. Coastal Cares produced nothing. §1. |
| 2 | NAICS enrichment of `industry_primary` | **68 of 108 populated** from OSHA inspections (54) and EPA ECHO facilities (14) the safety harness had already attributed; 8 were set; **32 blank** with reasons. TRADEPRESS v1.6 reads the column: **79 of 108 searchable** (was 15). Run live: 71 searched before the search quota ran out, **9 new rows from 5 newly unlocked companies**, quarantined with a sheet. §2. |

**State (from the workbook):** 536 observations, 525 released, 11 quarantined (EXECVOICE
v1.6 2, TRADEPRESS v1.6 9), 151 human-reviewed, 195 low-grade; 66 runs; 6,351 attempts.
All checks and tests pass (validate 10/10, assert_validations, check_run_ledger, 8 test files
re-run).

## 1. EXECVOICE v1.6: the low-grade names, searched

`load_executives` now returns `unconfirmed`-role people too, and `select_people` searches
up to 2 primary names then up to 4 low-grade names per company (the cap keeps a ten-name
roster from spending five companies' search budget). Quote extraction and grading are
untouched; the executive record's grade does not propagate. When a quote comes through a
low-grade name, the observation text ends with a speaker record note naming the person and
saying the role is unconfirmed, and the run log counts `quotes_via_low_grade_names`.

**Yield.** 362 searches, 597 page fetches, 7 companies covered, 53 absent, 48 blocked on no
executive at all. Two rows inserted:

| id | company | speaker (EXECID record) | quote | grade | note |
|---|---|---|---|---|---|
| O00599 | Gilbane | Brian Killinger, "Head of Asset Management" (low-grade E26) | "I am drawn to Gilbane's unique combination of operational excellence and mission-driven development" (citybiz) | B, weak_clue, 0.8 | admitted on the single specific term "operational excellence" |
| O00600 | Gilbane | same | same sentence (GoLocalProv "People on the Move") | B, weak_clue, 0.8 | same appointment release, second outlet |

For the reviewer: this is one appointment-announcement pleasantry carried by two outlets,
not two claims, and "operational excellence" in a new-hire quote is a thin admission to
`digital_transformation_process`. Both rows are quarantined and on
`H-EXECVOICE-01__v1.6__review.md`. Nothing about them is forced low-grade; the rules
produced B, which is the point of the exercise: the low-grade tier reaches a person the
vocabulary missed, and the quote rules then judge the quote.

**Coastal Cares** (A070, the prose-title survivor from session 14) was searched as a name
and produced no page and no quote. Nothing needs a second look.

O00372 (Prime Inc., `corrected`) is the one held row, unchanged. The three-week-old
"blanket" and "individual" wording issue does not arise: nothing here is judged yet.

## 2. NAICS enrichment, and what it unlocked

**Method** (`scripts/enrich_industry.py`, re-runnable, writes only blank cells). For each
buyer, the OSHA inspections whose establishment name equals the company's resolved OSHA
winner are re-parsed from H-SAFETY-ENV-01's archived search pages and their NAICS codes
collected; the modal industry wins if it holds at least 60% of them. Companies OSHA did not
resolve fall back to the resolved EPA ECHO facility's NAICS codes on the same rule, then to
an FMCSA for-hire carrier record of 100+ power units (none needed it). NAICS maps to a
vocabulary of nine values that H-TRADEPRESS-01's outlet map is keyed on; six were added to
`Lookups.industry` (additive, convention 22). `Companies.industry_source` records the basis
of every written value. No name was ever read for an industry.

**Result.** 68 written: construction 47, trucking 10, logistics 6, manufacturing 5, food 3,
energy 1, medical 1 (plus the 8 pilot values already set). 32 blank:

| why blank | n | companies |
|---|---|---|
| no OSHA, ECHO or FMCSA record attributed | 29 | A002, A003, A004, A008, A012, A018, A019, A021, A025, A034, A038, A044, A047, A058*, A059, A060, A064, A065, A066, A067, A068, A074, A080, A081, A085, A087, A090, A091, A092 |
| ambiguous split | 2 | Penske Logistics (trucking / logistics 1:1), Crane Worldwide (energy / other) |
| NAICS with no mapping | 1 | NFI (452910, general merchandise retail) |
| refused, convention 31 | 1 | Prime Inc.: one OSHA record under a one-word name, and tire retreading (326212) at that |

*Crane Worldwide had an ECHO record but an ambiguous split.

Two written values deserve a second look and are marked as such in CLAUDE.md: **4LIFE**
reads `construction` off a single ECHO facility code (236220) and **J.R. Simplot** reads
`logistics` off farm-supply wholesale codes; both are what the source records, and both
sit where a reviewer can correct them by hand without the script overwriting them.

**TRADEPRESS v1.6.** Scope is now every buyer whose industry maps to an outlet vertical,
with the hand-seeded 15 as an override: 79 of 108 searchable (64 from the enrichment). The
29 with no industry are still not searched; the refusal to guess moved from the harness to
the enrichment script and is unchanged in substance.

**The live run (HR-0066).** 71 of the 79 were searched: 9 covered, 62 absent. The last 8
(A100, C0002, C0003, C0005, C0007, C0008 and two more) hit **Brave HTTP 402**, the plan's
monthly quota, after roughly 750 searches across the two harnesses tonight; they are
recorded `source_unavailable` / `transient` with the reason in the row, not as a source
refusal. Nine rows were written, all from companies the enrichment unlocked:

| id | company | theme | role | grade | flag for review |
|---|---|---|---|---|---|
| O00601 | Clayco | data_analytics_ai | buyer_acts | C low-grade | |
| O00602 | Clayco | systems_integration | buyer_articulates | C low-grade | "integration" alone |
| O00603 | Walbridge | data_analytics_ai | buyer_articulates | B repeated_pattern | |
| O00604 | Walbridge | ot_modernization | buyer_articulates | B | **quote attributed to Randy Abdallah whose text names Novo Construction's CIO** -- possible wrong speaker or wrong company |
| O00605 | Boldt | digital_transformation_process | buyer_articulates | C (ST-PRESSCHAR) | |
| O00606 | Samet | warehouse_automation | buyer_articulates | C low-grade | |
| O00607 | Samet | digital_transformation_process | buyer_articulates | B | wire reprint routed to family 1 off an ENR "People Showcase Archive" page, which looks like an index |
| O00608 | JRM | ot_modernization | buyer_articulates | C low-grade | |
| O00609 | JRM | data_analytics_ai | buyer_acts | C low-grade | |

All quarantined, on `H-TRADEPRESS-01__v1.6__review.md`. O00376 (Gilbane, human-reviewed
v1.2) is held: its re-derivation differs. O00604 is the row to read first; if it is a
wrong-speaker row the version stays quarantined under stop rule 1.

Two crashes on the way, both ours and both fixed: a Windows console encoding error when a
search-failure string carried U+FFFD (all four live harnesses now write stdout with
replacement), and an openpyxl illegal-character error when a gzip-compressed 402 body was
pasted into an Attempts row (the search client now decompresses and strips error bodies;
`append_attempts` strips control characters). HTTP 402 is now classified explicitly.

## 3. Is Week 3 closed?

Yes. What Week 4 inherits from this session, in addition to session 14's list:

1. **The Brave search quota is exhausted for the month.** Every live run of EXECVOICE,
   TRADEPRESS, EXECID's search fallback and any new search-based harness is blocked until
   the plan resets or is upgraded. The 8 TRADEPRESS companies that hit the wall are named
   in HR-0066's attempts and re-run cleanly once search is back.
2. **11 quarantined rows** on two sheets, with O00604 flagged as a possible identity failure.
3. **32 companies without an industry** stay outside TRADEPRESS; 29 have no attributed
   safety or registry record, which no enrichment from the archive can fix.
4. **Two industry values to eyeball** (4LIFE, J.R. Simplot); the script never overwrites a
   hand correction.

## Files

- New: `scripts/enrich_industry.py`; `Companies.industry_source`; six `Lookups.industry`
  values; `H-EXECVOICE-01__v1.6__review.md` / strata; `H-TRADEPRESS-01__v1.6__review.md` /
  strata; this report.
- Changed: `harnesses/h_execvoice_01/` (v1.6), `harnesses/h_tradepress_01/` (v1.6),
  `core/search.py` (402, body sanitising), `core/db.py` (`append_attempts` sanitising),
  four harnesses' stdout handling, `scripts/migrate_schema.py`, `CLAUDE.md`, the workbook
  (68 industry cells, 11 observations, 2 runs, 556 attempts).

## Addendum (2026-09-06, later): the 11-row ruling, and why O00604 is not applied

Matthew's ruling on `REVIEW_QUEUE_2026-09-06.md`: every row supported, except O00604 and the
other Walbridge row (O00603) as `overgraded` with the finding attributed to both Walbridge
and Novo Construction, read as Randy Abdallah relaying what Novo's CIO told him.

**Applied:** O00599 / O00600 supported and released; `H-EXECVOICE-01__v1.6.json` written
(census 2 of 2), v1.6 published. O00601, O00602, O00605-O00609 recorded supported with
`review_source = human` but left quarantined, because the fate of the version they share
with O00604 is not yet decided.

**Not applied, with the reason.** Before writing a dual attribution I read the cached
Construction Dive page. The sentence the row quotes ("Colin Stoner, chief information
officer for Novo Construction, describes the time saved in comparing drawings...") is not
inside Abdallah's interview. It is the **"Editors' picks" sidebar**: the teaser for a
separate 5 August 2026 Q&A with Novo's CIO, followed by an unrelated teaser about NYC
building violations. The quote extractor ran a quotation span off the end of the article
into that sidebar and attributed it to Abdallah under an explicit-attribution rule. The term
that admitted the row to `ot_modernization` is `PLC`, the British company-suffix false
positive already logged in CLAUDE.md. So the row is not Abdallah quoting Stoner; it is page
furniture with Abdallah's name attached. O00603 is two genuine Abdallah quotes about
Walbridge's own technology investment and never mentions Novo.

Under the gate's definitions that makes O00604 a quote attributed to a person who did not
say it: **`wrong_entity`**, which by stop rule 1 holds every H-TRADEPRESS-01 v1.6 row in
quarantine until the extraction defect is fixed and the version re-run. `unsupported`
(delete the row, publish the other eight) is the alternative if the reviewer reads the
defect as a bad span rather than a bad speaker. Either way there is no Walbridge-Novo
discourse in this article to attribute; Novo is also outside the 108, so no row could
carry its company_id. The decision is Matthew's and is requested in the hand-off; the
extraction defect (quote spans crossing into sidebar/teaser text) is a v1.7 fix
regardless.

