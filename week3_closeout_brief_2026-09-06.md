# Week 3 Close-Out Brief — 2026-09-06

For Matthew, and for MetaCog's record. Sessions 12 through 15 are done; this is the state
Week 4 (reliability evaluation and synthesis) starts from, the decisions taken tonight,
and one decision that was open when this was first written and is now settled.

## State, from the workbook

| | |
|---|---|
| Observations | 535, all released; quarantine empty |
| Human-reviewed | 161 |
| Low-grade rows (convention 41) | 195, all released |
| Harness runs | 67 |
| Attempts | 6,367 |
| Executives | 931 (821 confirmed, 110 low-grade `unconfirmed`) |
| `Company_State_History` | 6,480 rows: DR-0001 and DR-0002 (appended; standing instruction is to append each derivation as produced) |
| Observation ids ever assigned | 560, 25 retired (registry, convention 43) |
| Companies with `industry_primary` | 76 of 108 (68 written tonight from archived NAICS) |
| Audit gate | 39 published versions, 22 audited, 17 grandfathered; every check and test green |

## Decisions taken tonight and applied

1. **The 11-row queue.** All supported except O00604, which is `unsupported` and deleted:
   its "quote" was a Construction Dive sidebar teaser about Novo Construction swept into the
   last answer of a Walbridge Q&A, admitted on the `PLC` suffix false positive. Not a wrong
   speaker: an extraction span defect, fixed in H-TRADEPRESS-01 v1.7 (`article_body` now ends
   at the first end-of-article marker line) and verified on an offline replay (Walbridge 2
   rows -> 1, 14 -> 13). H-EXECVOICE-01 v1.6 (the two Killinger rows) is published.
2. **EXECID's low-grade tier is read by EXECVOICE** (v1.6, Matthew's decision). Yield on the
   first live run: 76 names, 2 rows, both the same appointment sentence. Coastal Cares
   produced nothing.
3. **`industry_primary` populated from NAICS** the safety harness had already attributed
   (never from a name); TRADEPRESS reads it and scopes 79 of 108 instead of 15.
4. **Qualification rule settled** (convention 18, amended): an established platform plus
   modernization hiring is a positive signal.

## The threshold decision, settled

H-TRADEPRESS-01 v1.6's eight surviving rows all carried Matthew's `supported` verdict but the
version's census (9 rows, 1 exclusion, 11.1%) failed the 0.10 threshold `core/audit.py` had
carried as PROVISIONAL since 2026-08-31. **Matthew set the rule on 2026-09-06: a random
control from a population under 20 uses 0.15; 0.10 stays for 20 and over.** The rule lives
in `core/audit.py::threshold_for`, the literal in force is stamped on every artifact, and
every artifact written before this date keeps the 0.10 it was evaluated against. The v1.6
artifact was re-evaluated under the new rule with the same verdicts, passes, and the version
is published: the eight rows are released and the quarantine is empty.

## What Week 4 inherits

1. **Brave search credit.** The monthly quota ran out after ~750 searches (HTTP 402); $10 of
   credit was added and the eight interrupted TRADEPRESS companies were searched as HR-0067
   (session 15.5): 41 articles read, nothing admissible. Live search-based runs are open
   again while the credit lasts.
2. **The stop-rule threshold is now set** (0.15 under 20, 0.10 at 20 and over); the
   earlier artifacts were evaluated at 0.10 and say so.
3. **One theme now has a licensed-absence instrument (session 16): `cybersecurity`, through
   H-BREACHPORTAL-01** (state AG breach portals, IC4), for the 8 companies headquartered in
   California or Washington -- 7 licensed absences and 1 listing, plus presence listings for
   5 companies elsewhere; both versions audited and published, DR-0002 composes the seven as
   `absence_licensed_IC4`. Every other theme still has no absence instrument; cloud migration is
   "covered". Prior "candidate divergence" language is superseded.
4. **32 companies without an industry** stay outside TRADEPRESS; 29 have no attributed
   record. Two written values to eyeball: 4LIFE (`construction`, one ECHO code) and J.R.
   Simplot (`logistics`).
5. **FMCSA QCMobile field mappings** (entity type, authority type) before a v1.6 commit;
   F15/F26 verified live.
6. **H-VENDOR-01** population-0 artifact, if it is to publish; the spine has no theme for
   site-capture, EA-mapping or e-commerce deployments.
7. **The 110 low-grade executives** are unreviewed reference data at grade C.
8. **O00376 and O00372** are held human rows whose re-derivation differs; the FMCSA-20
   precedent applies when a decision is wanted.
9. **Recurring lesson for the write-up, now hit 12 times:** tonight added menu text as
   executives (EXECID), navigation text as vendor deployments (VENDOR), and a sidebar teaser
   as a Q&A answer (TRADEPRESS). Each was caught by reading rows before commit, none by a
   test. Convention 16 stands as the project's characteristic failure.

## Files that matter

`session14_report.md`, `session15_report.md` (with addendum), the three review queues under
`harness_output/audits/`, `docs/conventions.md` (18, 42, 43), `CLAUDE.md`.
