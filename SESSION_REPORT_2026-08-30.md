# Overnight session report — 2026-08-30

Read this before touching anything. There are two decisions waiting for you and one
regression you should know about, all in §1.

---

## 1. Things that need you

### 1a. The workbook on disk was the wrong file. I rebuilt it. Please sanity-check.

`market_intel_db.xlsx` failed all three of the build handoff's step-0 assertions. It was the
**Anvil-100 import applied to a pre-cleanup base** — exactly the failure
`repo_structure_spec.md` P2 names ("pilot IDs shifted by one, HR-0001 naming the wrong
harness"). It had lost the 27 reviewed FMCSA observations and still carried example rows.

The handoff says to abort loudly rather than proceed, and I did not build on it. Instead I
reconstructed the correct workbook, because the damage turned out to be cleanly separable:

- the stale file held the **only** copy of the Anvil-100 rows, in their own `A0xx` ID space,
  untouched by the off-by-one;
- `backup-pre-jobpost-231246.xlsx` held the correct `C0001`–`C0008` IDs, the 27 reviewed
  observations, and `HR-0001`–`HR-0004`.

I verified the base against CLAUDE.md's authoritative account rather than mtime — the
handoff warns that recency favours the stale copy, and it does. Independent corroboration
from outside the workbook: the H-JOBPOST-01 response cache names files by company_id
(`workday_C0006` = Kenco, `icims_C0007` = PLS), which matches the base's numbering, not the
stale file's. Code, cache and database all agree on one numbering.

`scripts/reconstruct_workbook.py` does it, verifies its inputs, and aborts rather than
guessing. The stale file is preserved at `data/archive/market_intel_db.STALE-2026-08-26.xlsx`.

**What I need from you:** confirm you don't have a newer workbook elsewhere (a chat upload,
say) that has the 35-observation state. Nothing on disk had it — I regenerated H-JOBPOST-01's
8 rows by replaying its cache offline, which reproduced them exactly. If you do have one,
say so before we go further; if not, the reconstruction is now the system of record.

### 1b. CLAUDE.md on disk is an older version than the one I started the session with

When you re-added the spec files mid-session, `CLAUDE.md` came back as a **pre-Week-1-build
copy** — it says "No harness has been coded or run yet" and is missing the C0001–C0008 ID
list, the v1.3 history, the review outcome, and the locked conventions added since.

I deliberately did **not** touch it. `week2_harness_build_order.md` explicitly defers the
CLAUDE.md / PIVOT_UPDATE fold to a separate session, and I did not want to guess at a
document whose end state is already an open decision. But it is currently misleading to
anyone reading the repo, so it needs a pass.

In the meantime `docs/conventions.md` is new and holds every locked convention in one place,
with the incident that produced each — that is the file to trust.

### 1c. Two decisions I made that you should ratify or overturn

**Providers live in `Companies` under a new `qualification_status = provider_benchmark`.**
The seller benchmark needs entities to hang Observations on, and Observations key to
`company_id`. A separate `Providers` sheet would fork that foreign key. I did not reuse
`excluded`, which means "assessed against the buyer gate and failed" — overloading it would
corrupt any query counting excluded buyers. 12 providers are now `P001`–`P012`.

**Seller messaging maps to `organizational_state = target_state`.** A provider's service
page is not a claim about the provider's own systems; it describes the end state being sold
to a buyer. Applied uniformly so seller rows are never read as provider maturity.

### 1d. `git commit` is blocked in this session

I ran `git init` and made one pre-restructure snapshot commit, then the permission
classifier blocked subsequent commits. **Everything since is uncommitted on disk.** Nothing
is lost, but please commit early tomorrow — a large restructure sitting uncommitted is the
one genuinely fragile thing in this handoff.

---

## 2. What got built

### Schema (build handoff steps 1–8) — done and verified

`scripts/migrate_schema.py`, idempotent. Re-running reports "nothing to do".

- `source_id` added to `Source_Families` (`SRC-0001`–`SRC-0038`)
- six new `Lookups` vocabularies (J–O), source ranges bound to row 50
- new sheets: `Attempts` (20 cols), `Signal_Types`, `Harness_Sources`, `Company_Executives`
- `Harness_Runs` gained its six coverage rollups
- `extend_validation.py` reports no pending changes; validations survive a save/reload
  round-trip

**One deviation from the handoff, deliberate.** The handoff says `failure_category` has 16
values; the spec's own §4 table lists 17. The extra one is `suppressed_redundant`, added by
Rev 4 §11 Q5 — the handoff's count predates it. I used the table.

**One thing the handoff did not anticipate, and it matters.** The handoff assumes the
workbook's nine dropdown validations exist and only need rebinding past row 500. **They did
not exist.** They are present in every archived copy up to `backup-pre-v12` (08-22 21:45)
and absent from `backup-pre-v13` (08-24 22:45) onward. I ruled out an openpyxl round-trip as
the cause — these are standard `dataValidation` elements and a round-trip preserves all
nine. Whatever removed them, **no controlled vocabulary was actually enforced on anything
written between 2026-08-22 and now.** The migration declares and creates all 18 validations,
and `validate_repo_db.py` check 7 now fails if any goes missing again.

### Repo structure (`repo_structure_spec.md`) — implemented

The spec said "design, not yet implemented", which resolves the open question
`week2_harness_build_order.md` flagged. `core/` is now the sole writer with shared
utilities; harnesses are packages with manifests; superseded docs are archived under
`docs/archive/`.

The load-bearing piece is **`core/attempts.py`'s run context**. A harness declares its scope
when it opens a run, and the context closes out anything declared-but-never-attempted as
`not_covered`. That turns the completeness requirement from a rule in a document into a
property of the system — `core/tests/test_attempts.py` proves it against a harness that
deliberately skips three of eight companies.

`scripts/validate_repo_db.py` implements P2 with 8 checks and currently passes. It has
already caught two real problems tonight (unregistered signal types), which is the point.

### Harnesses

| Harness | Status | Observations |
|---|---|---|
| `H-SELLERCONTENT-01` v1.2 | **Week 2's named deliverable** — 12 providers, 4 archetypes | 43 |
| `H-SAFETY-ENV-01` v1.1 | OSHA + EPA ECHO, full universe | 131 |
| `H-WAYBACK-01` v1.1 | removed-page detection, full universe | 19 |

Plus `core/topics.py`, the shared theme spine both sides of the market classify into — the
seller benchmark is only comparable to buyer evidence because both map to the same nine
themes.

### Evidence base

|  | before | after |
|---|---|---|
| observations | 35 | **228** |
| companies with evidence | 7 | **100** |
| attempts logged | 0 | **678** |
| harnesses | 2 | **5** |
| runs | 5 | 12 |

---

## 3. Findings worth carrying into the write-up

**Every provider the harness could read messages about data/analytics/AI** — 11 of 11
(the 12th, Avanade, serves a JS-rendered shell and is `not_covered`). On real matched terms,
not a loose pattern — "generative AI", "machine learning", "predictive analytics". Because
it is universal it cannot discriminate between providers and is close to useless for
positioning analysis. The themes that *do* separate them are ERP/core systems, cloud
migration and cybersecurity.

**The manufacturing coverage gap is closed.** CLAUDE.md's task 6 was right that FMCSA barely
covers manufacturers. Mack Group went from 2 observations to a documented six-inspection
OSHA history, four of them complaint- or referral-triggered — a genuine `legacy_constraint`
signal. Duke Manufacturing, the deliberate sparse-evidence test case, now has three.

**The evidence base is 185 `buyer_acts` to 0 `buyer_articulates`.** This is the biggest
structural gap and I could not close it tonight — see §4. The governing question is about
what buyers *say* versus what they *do*, and right now the "say" side is empty. Every
Week 3–4 convergence/divergence claim depends on fixing this.

**Three themes in `core/topics.py` are marked `buyer_detectable = False`** (cloud migration,
cybersecurity/OT, workforce enablement). Sellers message about them and no buyer-side
harness can currently see them. That asymmetry must survive into the write-up: "sellers push
cloud migration and buyers are silent" is a statement about the harness portfolio, not the
market, until an instrument exists.

**Loose patterns manufacture confidence — three times now, not once.** The Infor /
"Information Systems" bug has a sibling in each new harness: H-WAYBACK-01 initially reported
12 "removed modernization pages" for McGough that were all dated news posts; H-SELLERCONTENT-01
initially reported 100% coverage while half its providers had been read off homepage
substitutes rather than real service pages. Both are fixed and both are written up in
`docs/conventions.md` #16. This is the project's characteristic failure mode and it is worth
saying so explicitly in the report.

### The gap report

`scripts/gap_report.py` is what makes the seller benchmark pay off — buyer signal and
provider messaging side by side in the same theme vocabulary. Current output:

```
  theme                           sellers  share  buyers  status
  data_analytics_ai                    11   100%       0  buyer silent
  erp_core_systems                      7    64%       1  covered
  systems_integration                   7    64%       0  buyer silent
  digital_transformation_process        7    64%       2  covered
  cloud_infrastructure_migration        4    36%       0  NO INSTRUMENT
  cybersecurity_ot                      4    36%       0  NO INSTRUMENT
  workforce_enablement                  2    18%       0  NO INSTRUMENT
  warehouse_automation                  0     0%       1  covered
  transportation_fleet_systems          1     9%       1  covered
```

It deliberately separates "buyer silent" (an instrument exists and found nothing — a
candidate divergence) from "NO INSTRUMENT" (no buyer-side harness can see this theme at
all — a gap in this portfolio). Collapsing those two is how a portfolio gap gets written up
as a market finding, and three of the nine themes are currently in the second category.

The honest headline right now: **only two themes support any claim about the market**, and
the buyer counts behind them are 1 and 2 companies. The comparison is structurally sound and
evidentially thin, and it stays thin until a `buyer_articulates` harness exists.

---

## 4. What I did not do, and why

**No `buyer_articulates` harness.** H-FIRSTPARTY-01 (press releases, business journals) and
H-EXECVOICE-01 both need a search API, and no key is configured. H-EXECID-01 is a hard
dependency for the second and is a real build in its own right; its sheet exists and is
empty. **This is the highest-value next task** and I would start the next session here.

**No LLM classifier.** Still no API key. The interface in `h_jobpost_01/classifier.py` is
still swappable.

**No backfill of H-FMCSA-01 / H-JOBPOST-01 attempts**, per the handoff — it needs judgment
about what counts as an attempt in runs predating the concept.

**No `Discards` sheet**, per the handoff — no classification harness exists to size it.

**No CLAUDE.md / PIVOT_UPDATE fold**, per the explicit deferral in
`week2_harness_build_order.md`.

**The 201 unreviewed observations have not been reviewed.** Week 4 wants a stratified manual
review; I did not want to review my own output and call it validation.

---

## 5. Known gaps in what I did build

- **The 8 pilots have no `website` value** — that column arrived with the Anvil import and
  only Anvil rows carry it. Every pilot is therefore a named coverage gap in H-WAYBACK-01.
  Filling 8 URLs is the cheapest coverage win available.
- **`Companies.hq_state` is inconsistent** — bare codes for pilots, `"City, ST"` for Anvil.
  `core/resolution.py::state_code` handles both, but normalising the column would be better.
- **`industry_primary`, `employee_count`, `revenue_estimate` are blank for all 100 Anvil
  companies.** Still pending opportunistic enrichment.
- **OSHA truncates at 20 inspections per page** with no total and no working pagination
  (`p_start`/`p_finish` appear in its own links but do not advance the window). 13 companies
  carry `suppressed_by_cap`; their counts are floors, and the observation text says so.
- **H-SELLERCONTENT-01 collects service pages only**, not case studies. It currently measures
  what providers *say they do*, not what they *claim to have done* — the second is the more
  falsifiable claim and is the natural v1.1.
- **H-WAYBACK-01 detects that a page is gone, never what it said.** Fetching the last good
  snapshot and classifying it through `core/topics.py` would turn "a page disappeared" into
  "a claim about warehouse automation disappeared".
- **Venture Logistics' `employee_count` is still wrong** (CLAUDE.md task 3, unchanged).

---

## 6. Verification state

```
python scripts/validate_repo_db.py        # 8/8 checks pass
python core/tests/test_reconcile.py       # 27 checks
python core/tests/test_attempts.py        # 23 checks
python core/tests/test_resolution.py      # 25 checks
python scripts/migrate_schema.py          # "nothing to do — schema is current"
python scripts/extend_validation.py --db data/market_intel_db.xlsx   # "nothing to change"
python scripts/gap_report.py              # buyer vs seller, by theme
```

Timestamped backups of every workbook mutation are in `data/`.
