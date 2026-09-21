# Theme-by-theme evidence matrix (2026-09-20)

Data pull only -- no narrative, no per-theme reading. Regenerate with `python scripts/theme_evidence_matrix.py`.

**Basis.** Released rows only; every row carrying a current validity determination is excluded entirely, not netted; rows tagged `seller_side` are excluded from buyer-side counts. Quarantined-but-valid rows are shown separately and counted nowhere else.

## 1. The matrix

| # | Theme | Valid rows | buyer_articulates | buyer_acts | provider_market_responds | A | B | C | D | Buyer rows | of which low-grade | Buyer cos. | Licensed absence (cos.) | Invalid excl. | Quarantined | Coverage state |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| THEME-01 | `warehouse_automation` | **9** | 8 | 1 | 0 | 3 | 0 | 6 | 0 | **9** | 6 | 5 | — | 0 | 0 | **substantive evidence** |
| THEME-02 | `data_analytics_ai` | **56** | 37 | 8 | 11 | 19 | 17 | 20 | 0 | **45** | 19 | 24 | — | 43 | 0 | **substantive evidence** |
| THEME-03 | `erp_core_systems` | **9** | 1 | 1 | 7 | 2 | 6 | 1 | 0 | **2** | 0 | 2 | — | 1 | 0 | **thin evidence** |
| THEME-04 | `systems_integration` | **35** | 25 | 3 | 7 | 1 | 2 | 32 | 0 | **28** | 26 | 20 | — | 6 | 0 | **substantive evidence** |
| THEME-05 | `digital_transformation_process` | **53** | 37 | 9 | 7 | 9 | 19 | 25 | 0 | **46** | 24 | 30 | — | 5 | 0 | **substantive evidence** |
| THEME-06 | `transportation_fleet_systems` | **14** | 12 | 1 | 1 | 5 | 2 | 7 | 0 | **13** | 7 | 9 | — | 0 | 0 | **substantive evidence** |
| THEME-07 | `cloud_infrastructure_migration` | **7** | 2 | 1 | 4 | 0 | 3 | 4 | 0 | **3** | 2 | 3 | — | 0 | 0 | **substantive evidence** |
| THEME-08 | `cybersecurity` | **17** | 4 | 9 | 4 | 9 | 4 | 4 | 0 | **13** | 4 | 10 | 9 | 10 | 0 | **substantive evidence** |
| THEME-09 | `workforce_enablement` | **12** | 10 | 0 | 2 | 1 | 2 | 9 | 0 | **10** | 9 | 9 | — | 27 | 0 | **substantive evidence** |
| THEME-10 | `ot_modernization` | **9** | 8 | 0 | 1 | 1 | 1 | 7 | 0 | **8** | 7 | 7 | — | 16 | 0 | **substantive evidence** |
| | **total** | **221** | 144 | 33 | 44 | 50 | 56 | 115 | 0 | **177** | 104 | | | 108 | 0 | |

**Grade D is zero everywhere by construction** -- convention 4 makes D unwritable, so the column is structurally empty, not an observed result.

## 2. Coverage states, as applied

- **zero coverage** (0: none) — no instrument can license this theme's silence and no valid buyer row exists -- a portfolio gap, formally untested, NOT a market finding
- **confirmed absence** (0: none) — a licensing instrument (IC3/IC4, not presence-only) reaches this theme and found nothing -- a real 'buyer silent' finding, within its scoped denominator
- **thin evidence** (1: THEME-03) — 1-2 valid buyer-side rows -- report individually, with a small-sample caveat; do not fold into a summary
- **substantive evidence** (9: THEME-01, THEME-02, THEME-04, THEME-05, THEME-06, THEME-07, THEME-08, THEME-09, THEME-10) — more than 2 valid buyer-side rows -- enough to support a per-theme finding

The thin/substantive boundary is **2 buyer-side rows**, applied as a stated constant (`THIN_MAX`), not a judgment made row by row.

## 3. Instruments per theme

*Designed* reach (which instruments see the theme) and each instrument's class. `presence-only` means its silence is barred by declaration regardless of class; an absence is licensed only by a non-presence-only IC3/IC4 instrument.

| # | Theme | Instruments that see it (class) | Licenses absence? | Harnesses that actually contributed valid rows |
|---|---|---|---|---|
| THEME-01 | `warehouse_automation` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-FIRSTPARTY-01 (7), H-JOBPOST-01 (1), H-TRADEPRESS-01 (1) |
| THEME-02 | `data_analytics_ai` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-EXECVOICE-01 (2), H-FIRSTPARTY-01 (31), H-JOBPOST-01 (3), H-SELLERCONTENT-01 (11), H-TRADEPRESS-01 (8), H-VENDOR-01 (1) |
| THEME-03 | `erp_core_systems` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-FIRSTPARTY-01 (1), H-JOBPOST-01 (1), H-SELLERCONTENT-01 (7) |
| THEME-04 | `systems_integration` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-EXECVOICE-01 (1), H-FIRSTPARTY-01 (23), H-JOBPOST-01 (1), H-LEGAL-01 (1), H-SELLERCONTENT-01 (7), H-TRADEPRESS-01 (1), H-VENDOR-01 (1) |
| THEME-05 | `digital_transformation_process` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-EXECVOICE-01 (6), H-FIRSTPARTY-01 (29), H-JOBPOST-01 (6), H-PRODUCTQUALITY-01 (3), H-SELLERCONTENT-01 (7), H-TRADEPRESS-01 (2) |
| THEME-06 | `transportation_fleet_systems` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-EXECVOICE-01 (1), H-FIRSTPARTY-01 (11), H-JOBPOST-01 (1), H-SELLERCONTENT-01 (1) |
| THEME-07 | `cloud_infrastructure_migration` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-FIRSTPARTY-01 (2), H-JOBPOST-01 (1), H-SELLERCONTENT-01 (4) |
| THEME-08 | `cybersecurity` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only, `sec_8k_item_105_cybersecurity` IC4, `state_ag_breach_notice` IC4 | **yes** — `state_ag_breach_notice`, `sec_8k_item_105_cybersecurity` | H-BREACHPORTAL-01 (9), H-FIRSTPARTY-01 (4), H-SELLERCONTENT-01 (4) |
| THEME-09 | `workforce_enablement` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-FIRSTPARTY-01 (10), H-SELLERCONTENT-01 (2) |
| THEME-10 | `ot_modernization` | `exec_quote_reported` IC2, `executive_public_statement` IC2, `first_party_announcement` IC1, `job_board_third_party` IC3 presence-only, `job_posting` IC3 presence-only | no | H-FIRSTPARTY-01 (7), H-SELLERCONTENT-01 (1), H-TRADEPRESS-01 (1) |

## 4. Thin themes, row by row

Reported individually because a count this small carries no rate.

**THEME-03 `erp_core_systems`** — 2 buyer-side row(s):

- `O00032` — C0006, buyer_acts, grade A, H-JOBPOST-01 v1.4, published 2026-09-03
- `O00300` — A012, buyer_articulates, grade A, H-FIRSTPARTY-01 v1.3, published 2023-01-26

## 5. Data notes

Factual observations about the pull itself. No reading of the evidence is offered here.

- **`cybersecurity` is the only theme with a licensing instrument, and it is a MIXED case, not a clean absence.** It holds 13 valid buyer-side rows AND 9 companies the derivation composes as a licensed absence (A019, A022, A024, A030, A046, A079, A086, A094, A099). Of its buyer rows, 9 are breach notifications (`buyer_acts`, grade A, from the licensing IC4 instrument) and 3 are thin first-party mentions (`buyer_articulates`, grade C). A theme-level state cannot express both, so the licensed-absence column carries the company-level fact.
- **No theme is theme-level `zero coverage` or `confirmed absence`.** Every theme is seen by the announcement and executive instruments, whose scope is all themes, and every theme holds at least one valid buyer-side row. The absence finding the report wants exists at COMPANY level inside `cybersecurity`, not at theme level.
- **Earlier project text is superseded by this pull on two points**, both stated in CLAUDE.md before the instruments that changed them landed: `cybersecurity` is described as having zero buyer signal and being formally untested (it now has 13 buyer rows and a licensing instrument, from session 16's breach-portal harness), and `ot_modernization` is described as having no instrument on either side (it now holds 8 buyer-side rows and 1 provider row). Both statements were CORRECTED in CLAUDE.md on 2026-09-17, with the superseded wording quoted in place.
- **The low-grade tier carries much of this evidence.** 104 of 177 valid buyer-side rows are low-grade (convention 41: grade C, marked excerpt, admitted because the referent is right but the corroboration is thin). At or above half their buyer rows: THEME-01 (6/9), THEME-04 (26/28), THEME-05 (24/46), THEME-06 (7/13), THEME-07 (2/3), THEME-09 (9/10), THEME-10 (7/8). A `substantive evidence` state counts these rows; whether a per-theme finding should is a judgment this pull does not make.
- **Reconciled against `scripts/gap_report.py`**, which excludes the low-grade tier by default: its buyer-company count plus its low-grade-only column equals this matrix's buyer-company count for all ten themes, verified each time this is run. The two tools agree; they answer different questions.

## 6. Exclusions applied in this pull

- **Invalid rows excluded: 108** across all themes (111 determinations exist portfolio-wide; the rest sit on non-theme topics or quarantined rows).
- **Seller-side rows excluded from buyer counts: 0.** 70 rows carry a `seller_side` tag, but none routes to a theme — every tag sits on `federal_prime_contracts` or `municipal_permits_as_contractor`, and neither topic maps to a theme. The exclusion is applied in the pull regardless.
- **Quarantined valid rows held out: 0** — none.

