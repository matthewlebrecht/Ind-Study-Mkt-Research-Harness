# Repository Structure — Design Spec

**Status:** design, not yet implemented
**Covers:** brief item 3. Answers the three questions posed there — one script per harness,
shared utilities, and where harness changelogs live relative to `harness_version`.
**Handoff:** Claude Code implements; this document is the contract.

---

## 1. Three principles the layout exists to enforce

Everything below follows from these. Where a structural choice looks fussy, it is because
one of these would otherwise be unenforceable.

**P1 — One writer.** `core/db.py` is the only module that writes to the workbook. This is
already the convention; the layout makes it structural. It matters more now than it did:
the `Attempts` completeness requirement (a row for every scoped company, including skips)
is only enforceable if writes funnel through a single place that can emit them. A harness
that writes directly cannot be made to log its own misses.

**P2 — The repo and the database must be checkable against each other.** `harness_id` and
`harness_version` appear in both. Nothing currently detects when they disagree. The stale
workbook found on 2026-08-26 — pilot IDs shifted by one, `HR-0001` naming the wrong harness
— was exactly this class of failure, and it went unnoticed because nothing could notice it.
`scripts/validate_repo_db.py` (§5) exists to make that detectable.

**P3 — Superseded documents are archived, not left in place.** `PIVOT_UPDATE.md` opens by
telling the reader it supersedes parts of `CLAUDE.md` but not to discard that file. That is
a correct instruction and an unstable arrangement: a reader who finds `CLAUDE.md` first
gets a partly-false picture, and `qualification_procedure.md` describes an approach that is
no longer active at all. Same failure shape as the stale workbook.

---

## 2. Layout

```
market-intel-harness/
├── README.md                        # runbook + entry point (Week 5 deliverable)
├── CLAUDE.md                        # single current context doc — see §6
├── .gitignore
│
├── docs/
│   ├── conventions.md               # every locked convention, one place
│   ├── source_lists.md
│   ├── signal_taxonomy.md           # owned by Signal Advisor; lands here
│   └── schema/
│       ├── attempts_schema_spec.md
│       ├── observations_schema.md
│       └── company_executives_schema.md
│   └── archive/                     # superseded; each gets a status header
│       ├── qualification_procedure.md
│       ├── PIVOT_UPDATE.md
│       └── CLAUDE_pre_pivot.md
│
├── data/
│   ├── market_intel_db.xlsx         # system of record (workbook-only, Rev 5)
│   └── snapshots/                   # generated CSV mirror, one per sheet — see §4
│
├── core/                            # shared; imported by every harness
│   ├── db.py                        # sole writer; run context manager
│   ├── attempts.py                  # attempt emission, driven by the run context
│   ├── resolution.py                # token-scored entity resolution + refusal logging
│   ├── reconcile.py                 # idempotency, conflict detection
│   ├── drift.py                     # cited-snapshot vs live comparison
│   ├── vocab.py                     # loads Lookups; validates controlled values
│   └── tests/
│       ├── test_reconcile.py        # the existing 21 idempotency checks, relocated
│       ├── test_resolution.py
│       └── test_attempts.py         # asserts completeness (§3)
│
├── harnesses/
│   ├── README.md                    # how to add a harness
│   ├── h_fmcsa_01/
│   │   ├── manifest.yaml            # the repo↔DB contract — see §5
│   │   ├── harness.py
│   │   ├── sources.json
│   │   └── tests/
│   ├── h_jobpost_01/
│   └── h_execid_01/
│
├── scripts/
│   ├── validate_repo_db.py          # P2 enforcement
│   ├── extend_validation.py         # the 250k / 20k binding fix
│   └── export_snapshots.py
│
└── harness_output/                  # gitignored except reference_runs/
    └── reference_runs/              # committed: offline-replayable pilot runs
```

### Why per-harness packages, not one script each

Each harness already carries more than code: `h_jobpost_01` has `jobpost_sources.json` with
its documented coverage gaps, plus its own tests, plus a version history. A flat
`fmcsa_harness.py` forces that material into shared directories where ownership blurs. A
directory per harness keeps a harness's config, tests, and changelog adjacent to it, and
makes adding one a copy of a template rather than edits in five places.

Directory names are the `harness_id` lowercased with hyphens as underscores
(`H-FMCSA-01` → `h_fmcsa_01`), because Python modules cannot contain hyphens. The canonical
ID lives in the manifest; the directory name is derived, never authoritative.

---

## 3. `core/` — what is shared and why

Extracted because it is genuinely common across harnesses, not because it is generic:

| Module | Extracted because |
|---|---|
| `db.py` | P1. Every harness already writes through it |
| `attempts.py` | Attempt emission must be uniform or coverage math is not comparable across harnesses |
| `resolution.py` | Name→entity resolution is the established primary failure surface. Token-level scoring, confidence floor, and refusal logging are the same problem for FMCSA, execs, and every future source |
| `reconcile.py` | Idempotency is a locked convention with 21 tests. Reimplementing it per harness guarantees drift in the one behavior that protects human review |
| `drift.py` | The cited-snapshot-vs-live distinction protects the Week 4 metric. Not something to re-derive per harness |
| `vocab.py` | Controlled vocabularies live in `Lookups`. Loading them from the workbook rather than hardcoding means a vocabulary addition does not require touching every harness |

**The run context is where P1 becomes enforcement.** A harness declares its scope
(companies × signal types) when opening a run, and `db.py` closes the run by writing the
`Harness_Runs` row and reconciling declared scope against emitted attempts. Anything
declared but not attempted is written as `not_covered` automatically rather than going
missing. `core/tests/test_attempts.py` asserts this against a harness that deliberately
skips companies.

This is the difference between the completeness requirement being a rule in a document and
a property of the system. Stated as a rule, it fails the first time someone adds a harness
with an early `continue` in a loop.

---

## 4. The workbook in git

The workbook is committed at `data/market_intel_db.xlsx`. It is both the system of record
and the deliverable, and the stale-copy incident is the argument for version-controlling it
rather than against.

The cost is that a binary produces unreadable diffs, on a file that changes every run.
`scripts/export_snapshots.py` mitigates this by writing one CSV per sheet to
`data/snapshots/` on every commit that touches the workbook. Reviewing a commit means
reading the CSV diff; the xlsx remains authoritative. The snapshots are generated, never
edited, and never read back.

At this project's volume — 108 companies, five weeks — repo bloat is not a real concern.

---

## 5. Manifests: where changelogs live relative to `harness_version`

This is the brief's third question, and the answer is that changelogs should **not** be
prose in a `CHANGELOG.md`.

`harness_version` is a field in `Harness_Runs` and on every `Observations` row. A prose
changelog cannot be validated against it, so the two drift silently — and one specific
piece of information in that history is load-bearing for the Week 4 evaluation:
`reprocessing_required`. H-FMCSA-01 v1.2 was a material revision (a parser gap dropped
Operating Authority Status for private carriers) requiring re-derivation of 7 rows. Whether
a version requires reprocessing determines whether prior observations are still valid
evidence. That fact belongs in a field, not a paragraph.

`harnesses/<harness>/manifest.yaml`:

```yaml
harness_id: H-FMCSA-01
module: h_fmcsa_01
current_version: "1.3"
grandfathered_name: true        # named for a source, not a signal type — see spec §10 C3
signal_types: [carrier_registry_status]
declared_evidence_families: [12_regulatory_compliance]
sources: [SRC-0007]             # FK → Source_Families.source_id
versions:
  - version: "1.0"
    date: 2026-08-22
    reprocessing_required: false
    summary: Initial release. 27 observations across 8 pilots.
  - version: "1.2"
    date: 2026-08-24
    reprocessing_required: true
    affected_topics: [operating_model]
    summary: >
      Parser gap dropped Operating Authority Status for private carriers.
      7 operating_model rows re-derived.
```

`scripts/validate_repo_db.py` then asserts, mechanically:

1. Every `harness_version` in `Harness_Runs` exists in some manifest.
2. Every `harness_id` in `Observations` has a manifest.
3. Every `manifest.sources` entry resolves in `Source_Families`.
4. Every `declared_evidence_families` value is in `Lookups`.
5. Every `signal_types` value is in the `Signal_Types` registry.
6. No sheet has rows beyond its validation binding.

Check 6 catches the 500-row problem as a test failure rather than as silently unvalidated
data. Checks 1–2 catch the stale-workbook class of error. Run it in CI on every commit and
as the first step of any harness run.

---

## 6. Reconcile `CLAUDE.md` before Week 5, not during it

Currently a reader needs `CLAUDE.md` plus `PIVOT_UPDATE.md` plus the knowledge that parts
of the first are void. `qualification_procedure.md` is fully superseded and reads as active.

Recommendation: fold `PIVOT_UPDATE.md` into `CLAUDE.md` so one document describes current
state, and move both originals to `docs/archive/` with a status header. The pivot's history
is preserved and stays legible — it is genuine intellectual history of the project and
belongs in the final report — but it stops being load-bearing for anyone trying to
understand the system today.

Doing this before Week 5 matters because the handoff includes documentation and a runbook
for Talbot West. Handing over a context doc that requires a second doc to correct it is a
worse artifact than the work deserves.

---

## 7. Open

**Where `signal_taxonomy.md` lives.** Signal Advisor owns the content; the `Signal_Types`
registry is a workbook sheet that `vocab.py` reads. Whether the registry is generated from
the markdown or maintained directly in the workbook needs a call once the taxonomy is
stable. Generated is better — one source of truth — but not worth building until the
taxonomy stops moving.

**Whether `core/` should be an installable package.** Currently harnesses would import it
by path. A `pyproject.toml` and `pip install -e .` is cleaner and makes the repo look like
what a reviewer expects, which matters given the job-application framing. Low cost, worth
doing, but not a blocker.
