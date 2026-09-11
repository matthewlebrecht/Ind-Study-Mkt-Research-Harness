# Session 16 Report — H-BREACHPORTAL-01, the first IC4 instrument for a theme

**Date:** 2026-09-06 (attended, live)
**Brief:** state AG breach-notification portals, scoped to states with a confirmed searchable
portal, `cybersecurity` only, IC4, meant to make a genuine licensed absence possible.

## In one screen

| step | outcome |
|---|---|
| 0. Scope check | Portals with a working searchable public list from this network: **California (DOJ) and Washington (AG)**. Companies headquartered there: **7 of 108** (CA: Swinerton, Hathaway Dinwiddie, Devcon, Teichert; WA: BNBuilders, Lynden, Lease Crutcher Lewis). Reported before building; a handful, stated as one. |
| 1. Build | `H-BREACHPORTAL-01` v1.0, signal type `state_ag_breach_notice` registered as IC4, sources SRC-0050 / SRC-0051 registered with archival reach, listed in `core/composition.py` as an instrument that sees `cybersecurity` and nothing else. Identity by the all-token rule. |
| Run (HR-0068) | 108 searched for presence, 7 scoped for absence. **6 licensed absences, 1 in-scope listing (BNBuilders), 10 rows written** across 6 companies. No access trouble on either portal. Quarantined, sheet drawn. |
| Composition | With HR-0068 published, the six read as `absence_licensed_IC4` in 2026-W36 (verified on a dry run). The derivation and the gap report were then made to ignore attempts from runs the gate has not published, so until v1.0 is audited they read nothing from it. |
| Not in scope | 8-K Item 1.05: `Companies` carries no public/private field, so the split cannot be counted from the sheet; not built. |

State: 545 observations, 535 released, 10 quarantined (all H-BREACHPORTAL-01 v1.0), 161
human-reviewed; 68 runs; 6,380 attempts. Checks 10/10, schema-delta 74/74, resolution 25/25.

## 0. Scope check, in full

HQ state came from `Companies.hq_state`; ten rows were unparsed because the CRM spells states
out ("Meridian, Idaho", "Seattle, Wash.", "SLC, UTAH"), so `core/resolution.state_code` now
reads full names and common abbreviations. Two rows still have no state: Crane Worldwide
("Houston", no state token) and Day & Ross ("Hartland, NB (US Ops)"). Goodfellow Bros has
none in the sheet; its EPA facility is in California, but a facility is not a headquarters
and it was left out of scope.

Portal probe, live, under this crawler's identity:

| state | companies | result |
|---|---|---|
| CA | 4 | searchable list, filter by organisation name, explicit empty-result marker; robots permit |
| WA | 3 | searchable list, ~1,860 notices over 38 pages, read in full; robots permit |
| TX | 6 incl. two unparsed | connection timeout at the network level on two URLs, the same behaviour as USASpending; not a source refusal, not attempted |
| MD | 2 | page loads, list is JavaScript-rendered (`js_rendered_unreachable`) |
| IA, IN | 2 each | year-by-year PDF notice lists this version does not parse |
| VT, MT | 1, 0 | robots.txt disallows this crawler |
| MA, NH | 1, 0 | HTTP 403 |
| OR | 0 | works (POST search) but no company is headquartered there |
| NY | 2 | no public list; the AG page is a reporting form |

## 1. What the harness does

Every buyer is searched against both portals for presence, because a portal lists any
organisation that notified that state's residents wherever it is based. Only a company
headquartered in the portal's state gets a scoped attempt, and only its empty result is an
absence claim. California is queried by name filter (two terms per company: the name minus
suffixes, and its first distinctive token when there are two or more); Washington is read
whole and matched locally. Every candidate organisation name then has to pass the
all-token rule before `core.resolution.resolve` scores it.

That rule was not optional. The first dry run, with the resolver alone, matched
"Kimberly-Clark Corporation" to Clark Construction, "Petersen International Underwriters"
to Petersen Inc., "Urology Austin" to Austin Industries, "Romeo Power" to Power
Construction, "Summit Financial Group" to Summit Contracting, "McCarthy & Holthus LLP" to
McCarthy Holdings and "PLS Financial Services" to PLS Logistics, each on the one word they
share: seven wrong-company rows out of seventeen. Under the all-token rule (every
distinctive company token present, extras limited to suffix words, "dba" clauses split so
"LaserShip, Inc. dba OnTrac Final Mile" still finds OnTrac) all seven are refused with the
reason logged, and the ten that remain are the company itself.

A listing is written as `buyer_acts`, `measured_result`, grade A, `organizational_state =
unknown`: it records that a breach was notified, not the company's security posture.

## 2. What it found

| company | HQ | scope | result |
|---|---|---|---|
| Lease Crutcher Lewis | WA | scoped | absent_confirmed |
| Swinerton | CA | scoped | absent_confirmed |
| Hathaway Dinwiddie | CA | scoped | absent_confirmed |
| Devcon Construction | CA | scoped | absent_confirmed |
| Lynden | WA | scoped | absent_confirmed |
| Teichert | CA | scoped | absent_confirmed |
| BNBuilders | WA | scoped | **listed in WA and CA** (2 rows) |
| Whiting-Turner | MD | incidental | listed in CA |
| Estes Express Lines | VA | incidental | listed in CA, two notices |
| C.R. England | UT | incidental | listed in CA and WA |
| doTERRA | UT | incidental | listed in WA |
| OnTrac | VA | incidental | listed in CA and WA as LaserShip dba OnTrac |

So: 7 covered in scope, 6 genuine licensed absences, 1 disclosed breach; and 9 presence
listings for companies outside the scope, which are evidence about them but license nothing
about anyone else. All 10 rows are quarantined on `H-BREACHPORTAL-01__v1.0__review.md`.

## 3. Does the composition read it correctly?

Yes, and the check found a rule that was missing. A dry-run derivation with HR-0068's
attempts visible composed the six scoped absences as `status = absent`, `reason =
absence_licensed_IC4`, `covering_instruments` including `state_ag_breach_notice`, in
2026-W36 (W35 is `theme_not_detectable` because cybersecurity's instrument date is
2026-08-31 and the week starts before it). BNBuilders also read as absent there, because
its two listings are quarantined and the derivation reads released rows only; once the
version is audited it flips to `observed`.

The missing rule: the derivation read attempts from every run, including runs the gate has
not published, while it read observations from released rows only. A quarantined run's
attempts must license nothing yet, for the same reason its rows count for nothing yet.
`core/composition.py::load_inputs` and `scripts/gap_report.py` now use attempts from
published runs only, and the gap report also excludes quarantined observations (it had
briefly counted the ten new rows as six cybersecurity buyers). Until v1.0 publishes, the
gap report prints **"licensed instrument unpublished (0 of 108)"** for cybersecurity and the
derivation writes no licensed absence. After it publishes, the report prints "buyer silent
(6 of 108 under a licensed instrument)", the §20.5 denominator, never a bare "buyer silent".

## 4. Access

None. Both portals permit this crawler by robots.txt and answered every request; the cache
holds 38 WA pages and one CA response per query term. The blocked states are listed in §0
with their exact failure, and none was worked around.

## 5. For Matthew

- The 10-row review sheet. Six companies, all exact-name matches; the OnTrac rows rest on
  a "dba" clause, which is worth one look.
- Whether Goodfellow Bros should be treated as California-headquartered.
- The taxonomy has no family for regulator-held cyber disclosures; the source is filed under
  family 9 with the other regulatory records and flagged for the taxonomy owner.
- A DR-0002 dry run now differs from DR-0001 in 141 rows (the session 15 releases moved
  covering instruments and six observed buckets); appending it is the usual call.

## Files

- New: `harnesses/h_breachportal_01/` (harness, manifest), SRC-0050 / SRC-0051,
  ST-BREACHNOTICE, `H-BREACHPORTAL-01__v1.0__review.md` / strata, this report.
- Changed: `core/composition.py` (instrument with a named theme list; attempts from published
  runs only), `core/resolution.py` (state names), `scripts/gap_report.py` (released rows only,
  licensed-coverage denominator), `scripts/register_sources.py`, `scripts/migrate_schema.py`
  (reach), `CLAUDE.md`, the close-out brief, `data/snapshots/gap_report.csv`, the workbook.

## Addendum: follow-up rulings applied (2026-09-06)

- O00611/O00612: one incident, one row. O00611 (full-name query) kept and supported; O00612
  deleted through `delete_observation_ids`, its id retired in the registry with the reason.
  v1.1 deduplicates California hits on the listing's own identity.
- O00616/O00617 (OnTrac, dba clause, confidence 0.74): supported. All other rows supported.
- v1.0 artifact: census 10, 9 supported, 1 excluded as a duplicate (10.0% against the 15%
  threshold for populations under 20), PASS, **published**.
- Goodfellow Bros: `hq_state` set to CA with a note; scoped attempt run as HR-0069 (v1.1,
  offline replay of the same-day cache): no listing, `absent_confirmed`. v1.1 artifact
  (population 0, the PQ v1.2 precedent) written and **published**.
- DR-0002 **appended** (3,240 rows): `absence_licensed_IC4` 7 for cybersecurity in
  2026-W36, BNBuilders `observed`; 147 rows differ from DR-0001. Standing instruction
  recorded in CLAUDE.md: append each derivation as it is produced.
- State: 544 observations, all released, 170 human-reviewed; 69 runs; quarantine empty.

