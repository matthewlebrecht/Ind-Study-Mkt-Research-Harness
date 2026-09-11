# Market Intelligence Harness

Code for the **Market Intelligence Harness Project**, an Independent Study by Matthew
Lebrecht sponsored by **Talbot West**. The harness collects public evidence about
operationally complex, mostly privately held U.S. companies (federal registries, job
postings, press releases, trade press, safety and environmental records, breach portals,
court dockets, seller service pages), resolves each hit to a company, classifies it against
a shared modernization-theme spine, and writes one row per atomic checkable claim into a
workbook that serves as the project's database. Every harness logs what it attempted and not
only what it found, new output is quarantined until it passes an audit gate, and a set of
mechanical checks keeps the code and the database in agreement. The governing question is
where buyers' stated and enacted modernization pressures converge with, or diverge from,
what the provider market messages about.

**This repository holds the code only.** The evidence workbook, its backups and snapshots,
the raw response archive, run logs and audit artifacts are excluded by `.gitignore` and are
not part of this repo. Scripts that read the workbook will not run here without it.

## Repo structure

```
core/               shared library; core/db.py is the ONLY module that writes the workbook
  db.py             workbook layer, vocabulary validation, idempotent reconciliation, audit verdicts
  attempts.py       run context that makes Attempts completeness structural
  audit.py          the audit gate: artifacts, random-control stop rule, thresholds
  composition.py    temporal derivation (detectability -> realized reach -> instrument class)
  resolution.py     name -> external-entity resolution with refusal logging
  topics.py         the modernization-theme spine both sides of the market map into
  search.py         Brave Search client (key read from .env via core/config.py)
  config.py         credential access; keys come from .env, never from source
  tests/            unit tests against incidents that actually happened
harnesses/          one package per harness (h_<name>_01/): manifest.yaml is the
                    repo<->DB contract, harness.py the run, source.py the source clients,
                    sources.json / aliases.json hand-curated targets and aliases
scripts/            validate_repo_db.py (the 11 repo-vs-database checks), migrate_schema.py,
                    audit_sample.py, write_audit_artifact.py, gap_report.py,
                    derive_state_history.py, check_run_ledger.py, loaders and diagnostics
docs/               conventions.md (locked conventions with their originating incidents),
                    schema specs, gate procedure, diagnostics, archived specs
data/               company_aliases.json only; the workbook itself is not committed
CLAUDE.md           current-state summary of the project; session reports sit at the root
```

## Setup

Python 3.12+ with `openpyxl`, `requests` and `pyyaml`. Copy `.env.example` to `.env` and
fill in the keys; `core/config.py` reads them from there or from the environment. No key
is ever hardcoded in source.
