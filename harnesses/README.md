# Harnesses

Each harness collects public evidence about companies in the Companies sheet and writes
atomic observations into the shared `Observations` table, tagged with `harness_id` and
`harness_version`, plus one summary row into `Harness_Runs`.

## Layout

| File | Role |
|---|---|
| `cache.py` | Date-partitioned response archive, shared by all harnesses. Evidence archive first, speed optimization second. |
| `db.py` | Shared workbook layer. Reads the company universe, enforces the Observations contract against the Lookups vocabulary, allocates IDs, appends rows. Not source-specific — every future harness writes through it. |
| `fmcsa_source.py` | FMCSA fetch + parse only. No project semantics. |
| `fmcsa_harness.py` | H-FMCSA-01: resolution, evidence mapping, run orchestration. |
| `fmcsa_aliases.json` | Human-seeded name variants. Each entry is a documented limit on automation. |
| `test_dedupe.py` | Regression test for the re-run policy in `db.sync_observations()`. |
| `jobpost_source.py` | H-JOBPOST-01 ATS adapters (Workday / iCIMS / Paylocity). Fetch + parse only. |
| `jobpost_classifier.py` | Posting → modernization-signal classification, behind a swappable interface. |
| `jobpost_harness.py` | H-JOBPOST-01: orchestration, aggregation, evidence mapping. |
| `jobpost_sources.json` | Per-company ATS config **and** the explicit coverage gaps. |

Setup: `pip install openpyxl requests`

---

## H-FMCSA-01 — FMCSA Carrier Registry & Safety Extractor (v1.3)

```bash
python harnesses/fmcsa_harness.py                    # dry run (default) — validates, writes nothing
python harnesses/fmcsa_harness.py --commit           # write to market_intel_db.xlsx
python harnesses/fmcsa_harness.py --offline          # replay cached responses, no network
python harnesses/fmcsa_harness.py --include-excluded # also process excluded companies
python harnesses/fmcsa_harness.py --companies C0004,C0006
python harnesses/fmcsa_harness.py --commit --force-rewrite  # discard+rebuild unreviewed rows
python harnesses/fmcsa_harness.py --commit --refresh-reviewed  # opt in to re-deriving reviewed rows
python harnesses/test_dedupe.py                             # regression test for the re-run policy
```

### Sources (neither requires an API key)

1. **FMCSA Motor Carrier Census** — Socrata dataset `az4n-8mr2` on data.transportation.gov,
   ~4.5M rows. Used for *candidate discovery* only.
2. **SAFER Company Snapshot** — `safer.fmcsa.dot.gov`. Used for *evidence extraction* once a
   USDOT number is resolved.

Set `FMCSA_WEBKEY` to prefer FMCSA's QCMobile JSON API for step 2 — same data, far less
brittle than parsing SAFER's table markup. The key is free but requires registration; the
harness works without it.

Every response is archived under `harness_output/H-FMCSA-01/raw/<retrieval-date>/`, so
`--offline` replays a run exactly and a reviewer can re-read what the harness actually saw.
The partition is by date, not by USDOT: SAFER's figures move (see below), so a flat cache
would let each re-run erase the evidence behind rows an earlier run already wrote. `--offline`
replays the most recent partition holding each response.

### Why resolution is the hard part

Name → USDOT is where this harness earns its keep, and where it fails:

- **Substring matching is wrong.** `LIKE '%WESTERN EXPRESS%'` returns SOUTHWESTERN EXPRESS,
  TENNESSEE WESTERN EXPRESS, NORTH WESTERN EXPRESS. The resolver generates candidates with a
  loose `LIKE` but *scores* on normalized token alignment, which rejects all three.
- **One company, many USDOT numbers.** Kenco holds five active Chattanooga registrations.
  The primary is chosen by score, then fleet size, then filing recency; co-located registrants
  with *distinct* names become a `multi_entity_operating_structure` observation, while a second
  registration under the *identical* name is treated as a duplicate record and logged, not
  published.
- **Brand name ≠ registered name.** Venture Logistics files as VENTURE TRANSPORT LLC — resolved
  automatically because FMCSA's `dba_name` field lists both. Mack Group files as MACK MOLDING
  COMPANY INC with no linking DBA, and needs a human alias.

Below `MIN_SCORE_TO_ACCEPT` the harness refuses to guess and records the company as unresolved
with its closest rejected candidates.

### Quality gates (all named constants at the top of the module)

| Constant | Purpose |
|---|---|
| `MIN_SCORE_TO_ACCEPT = 55` | Refuse low-confidence name matches rather than guess. |
| `MIN_INSPECTIONS_FOR_RATE = 20` | An out-of-service % on a handful of inspections is noise. |
| `MIN_FLEET_FOR_CRASH_RATE = 20` | Stops "1 crash on 2 trucks = 50 per 100 power units". |
| `STALE_MCS150_MONTHS = 24` | Biennial MCS-150 update is federally required; past it, fleet figures are stale. |
| `WORKFORCE_CONFLICT_RATIO = 0.25` | Flags registry headcount that contradicts the qualification-stage estimate. |

Every suppression is written to the run log and into the `known_issues` column of
`Harness_Runs` — a gate that fires silently is a gate that lies about coverage.

### Observations emitted

| topic | evidence_family | signal_strength |
|---|---|---|
| `fleet_scale` | `8_physical_footprint_capacity` | `weak_clue` |
| `operating_model` | `10_logistics_supply_network` | `weak_clue` / `committed_action` |
| `vehicle_maintenance_out_of_service_rate` | `9_industrial_safety_environmental` | `measured_result` |
| `driver_compliance_out_of_service_rate` | `9_industrial_safety_environmental` | `measured_result` |
| `crash_exposure_rate` | `9_industrial_safety_environmental` | `measured_result` |
| `registry_record_maintenance_lag` | `18_historical_change_disappearing_evidence` | `weak_clue` |
| `workforce_scale_conflict` | `3_workforce_org_exhaust` | `weak_clue` |
| `multi_entity_operating_structure` | `10_logistics_supply_network` | `repeated_pattern` |
| `for_hire_authority_not_active` | `10_logistics_supply_network` | `measured_result` |

`evidence_role` is always `buyer_acts` — a federal filing records what a company does, never
what it says. `source_grade` is always `A`: primary, attributable, re-checkable at a stable URL.
`organizational_state` is `unknown` by default and `legacy_constraint` only where a measured
outcome is materially worse than the national average, or an active carrier has let its own
registry record go stale.

### The operating-authority rule (v1.2)

FMCSA's `Operating Authority Status` reads `NOT AUTHORIZED` for a large share of registrants,
and it means opposite things depending on the carrier:

- **Private or intrastate-only carrier** → expected and non-informative. The status refers to
  *for-hire* authority, which a private fleet is not supposed to hold. SAFER says as much on the
  page itself. Reporting it as missing authority would read as a deficiency that isn't there, so
  `operating_model` states it as the expected status.
- **Self-classified for-hire carrier** → a real constraint. Authority is lapsed, revoked, or not
  yet granted, and the carrier cannot legally haul for hire. This emits a separate
  `for_hire_authority_not_active` observation as `legacy_constraint`, capped at
  `confidence_0_1 = 0.7` because a snapshot cannot distinguish a revoked carrier from a new
  entrant whose application is pending — the row says so and asks for a reviewer.

`_is_private_carriage()` makes the call from `Operation Classification`, treating any
`Auth. For Hire` / `Exempt For Hire` marking as for-hire regardless of other flags.

Note the parser must read the *labelled field*, not search the page: the literal words
"NOT AUTHORIZED" appear in the explanatory legend of every SAFER snapshot, including carriers
that are fully authorized. v1.1 and earlier read only the `AUTHORIZED FOR:` label, which does
not exist on a private carrier's page, so those rows silently said "none listed".

### Re-running (v1.1+)

Writes go through `db.sync_observations()`, which reconciles proposed rows against the sheet on
a natural key of `(company_id, harness_id, topic, source_url)`. Four outcomes:

| outcome | when | what happens |
|---|---|---|
| `inserted` | no row for that key | new row appended |
| `unchanged` | content fingerprint matches | row left completely untouched |
| `updated` | content changed, row still `unreviewed` | refreshed in place, keeping its `observation_id` |
| `conflict` | content changed, row already reviewed | **not touched** — reported for a human to resolve |

The conflict case is the point. Human review is the scarce input to Week 4's reliability
evaluation, so a re-run surfaces disagreement rather than erasing it. `review_status` and
`reviewer_notes` are never written by a harness.

The natural key excludes `harness_version`, so a version bump alone does not duplicate rows.
An untouched row keeps the version that produced it; a refreshed row takes the version that
refreshed it. Dry runs reconcile too, so `--commit` holds no surprises.

`--force-rewrite` deletes this harness's rows before writing, and still keeps reviewed ones.

`--refresh-reviewed` opts into re-deriving reviewed rows. It exists for one situation: the
reviewer checked rows against a *newer* source snapshot than the harness read, so the rows are
right but internally inconsistent (new figures under an old window date). It preserves
`review_status` and stamps `reviewer_notes` to record that a machine touched a reviewed row.
Never the default.

### Source drift — the finding from the first review cycle

SAFER republishes its snapshot every few days and the 24-month rolling window moves with it.
Between the 2026-08-22 run and the manual review, the snapshot advanced from 08/20 to 08/23:
Western Express gained 12 vehicle inspections, Venture's crash count went 94 → 96, and Kenco's
vehicle out-of-service rate swung a full point (9.2% → 8.2%) on 110 inspections — which is
exactly the volatility `MIN_INSPECTIONS_FOR_RATE` guards against, visible in live data.

All nine "corrections" from that review matched the live source exactly. **Zero were harness
extraction errors.** Two consequences are now baked in:

1. **Review a row against the snapshot date it cites**, not today's live page. Drift is fixed
   by re-running the harness, not by hand-editing rows. `corrected` is reserved for genuine
   harness mistakes, or the reliability metric measures the calendar instead of the harness.
2. **Anything an observation states must be computed from the snapshot's own `data_as_of`**,
   never from `date.today()`. `_months_since()` takes a `relative_to` argument for this. A row
   whose text drifts with the wall clock conflicts against its own stored copy forever.

`test_dedupe.py` asserts all of the above (21 checks) against a throwaway copy of the workbook.

### Known limitations

1. **Manufacturers are near-empty.** Midmark, Mack, and Duke each register 1–2 private-fleet
   trucks with no inspection history. The observations are true but thin — FMCSA is a
   logistics-family source, and this is the expected shape, not a bug.
2. **Corporate family is inferred**, from shared name prefix and physical city, never from a
   corporate filing. Those observations carry `confidence_0_1 = 0.55` and say so in their text.
3. **Dropdown validation stops at row 500** on Observations and Companies. `db.py` warns when a
   sheet crosses it.
4. **SAFER parsing is positional**, keyed to label text in 1990s table markup. A page redesign
   breaks it silently for fields that go missing rather than wrong — prefer QCMobile if a
   webKey is available.


---

## H-JOBPOST-01 — Job Postings Modernization-Signal Extractor (v1.0)

```bash
python harnesses/jobpost_harness.py                 # dry run
python harnesses/jobpost_harness.py --commit
python harnesses/jobpost_harness.py --offline       # replay archived responses
python harnesses/jobpost_harness.py --companies C0006
```

The first harness against a non-API family. Job postings are one of the few sources where a
private mid-size company exposes nearly as much as a public one: a company that will never
file with the SEC still has to publicly describe the systems it is trying to staff.

### Why coverage is the hard part

There is no registry. Each company publishes on whichever ATS it licenses, so every company
is its own integration:

| company | ATS | status |
|---|---|---|
| C0006 Kenco | Workday (`kencogroup.wd12`) | JSON API, 561 postings |
| C0007 PLS Logistics | iCIMS | HTML portal |
| C0005 Venture Logistics | Paylocity | careers page → job detail pages |
| C0001 Midmark, C0003 Duke | — | careers page renders postings via JS; no ATS in server HTML |
| C0002 Mack Group, C0004 Western Express | — | careers URL not yet identified |

**Coverage is 3 of 7.** The four gaps live in `jobpost_sources.json` next to the working
adapters, are processed every run, and are reported in `known_issues` on the `Harness_Runs`
row. A gap is never deleted to make a run look clean — a harness that hides what it could not
reach is worse than one with visible holes, because the holes stop being visible in Week 4.

Western Express is the instructive gap: large truckload carriers usually run driver recruiting
on Tenstreet or DriverReach, entirely separate from any corporate ATS. Their *driver* hiring is
high-volume and low-signal anyway, so the corporate roles are what matter — and those are the
harder ones to find.

### Classification

`RuleClassifier` — deterministic patterns, every hit traceable to a named rule, no API key.
Six signal categories: warehouse systems/automation, data-analytics-AI, ERP/core systems,
integration engineering, digital transformation, transportation systems.

An `EXCLUSIONS` pattern drops ordinary operational hiring (forklift, warehouse associate, CDL
driver) so a posting that merely *mentions* a system isn't read as a systems hire. This matters
at Kenco's scale: 467 distinct postings, overwhelmingly warehouse floor labor, with only 5
genuine modernization roles among them.

`LLMClassifier` implements the same interface and is deliberately unwired — no API key is
configured. Swapping it in requires no change to the harness; keep the signal keys identical
so observations stay comparable, and bump the harness version so `Harness_Runs` records which
classifier produced which rows.

**Pattern-writing rule learned the hard way:** vendor names need a word boundary on *both*
sides. A bare `Infor` matched inside "Infor**mation** Systems", promoting every IT manager to
an ERP hire and inflating Kenco's ERP signal from `weak_clue` to `repeated_pattern`. Signal
strength drives how much weight a finding carries later, so a sloppy pattern doesn't just add
noise — it manufactures confidence.

### Evidence mapping

`evidence_family` is always `3_workforce_org_exhaust`; `evidence_role` is `buyer_acts` (posting
a role is an action); `source_grade` is `A` (first-party, on the company's own careers page).

`organizational_state` is always `active_transition`, per project convention 2 — hiring is a
positive modernization signal but **not** proof of an established in-house capability, and every
observation says so in its own text.

`signal_strength` ladders: `weak_clue` for a single posting, `repeated_pattern` at 3+ (a cluster
is a program, not a backfill), `committed_action` when a leadership title appears, because
staffing a mandate outranks staffing a seat.

### Known limitations (v1.0)

1. **Titles only, not descriptions.** Most roles name their system in the title, but a posting
   whose modernization content is buried in the body is missed. Descriptions are one fetch per
   posting — 467 extra requests for Kenco alone.
2. **Point-in-time by nature.** Hiring changes weekly, so re-runs are *expected* to update these
   rows — unlike the FMCSA rows, where a change means the source moved. The claim text always
   states its as-of date.
3. **Absence proves nothing.** No signal may mean no modernization, or a company that hires
   through referrals, or an uncovered ATS. Never read a zero here as evidence of a laggard.
4. **iCIMS adapter is portal-only.** PLS also posts on JazzHR and Paycor; those are not covered.
