# Report appendix — reliability limitations

Known limitations of the evidence base that a reader needs in order to interpret its numbers
correctly. These are documented deliberately rather than fixed: each is recorded with what it does
and does not affect, so a figure is never quoted as if the limitation were not there.

---

## 1. H-FMCSA-01 reports population facts outside the attempts-based coverage system

**H-FMCSA-01 predates the attempts-based coverage convention and reports population facts outside
that system.** It is the only one of the project's seventeen harnesses that writes no `Attempts`
rows, and it never has — none in any of its ten runs, including the most recent (HR-0084,
2026-09-17). Sixteen harnesses use the shared run-context (`core/attempts.py`), which makes a
harness declare its scope on open and reconciles what it declared against what it emitted, writing
`not_covered` for the difference. The carrier-registry harness was built before that convention
existed and was never retrofitted.

### What follows from it

- **The carrier registry has never contributed a coverage percentage, and none should be quoted for
  it.** `scripts/published_coverage.py` reports it as `scoped 0 / n/a`, which is accurate: with no
  attempts there is no denominator. Its line in any coverage table is legitimately blank, not
  missing.
- **It licenses no absence in the temporal derivation.** `core/composition.py` licenses a
  company × theme × week bucket from attempts, so nothing this harness reads can license one. Its
  evidence still appears as observations; it simply never makes a bucket "covered".
- **Its observations are unaffected.** All 40 rows are live, audited and released, and they are the
  most heavily reviewed output in the project: every one is human-reviewed, and the 30 rows of the
  current version were judged row by row in a census audit (2026-09-17, all supported).

### Why this is honest rather than a hole

What the harness reports is a **population fact, not a coverage rate**: of the 108 buyers, **8
resolve to a carrier in the federal registry** under an identity test that refuses to guess. The
other 100 are not failures of retrieval — most of these companies are not motor carriers and have
no USDOT registration to find. A coverage percentage over 108 would therefore describe the
population's composition rather than the instrument's reach, and would read as 7% "coverage" for an
instrument that found everything there was to find.

Retrofitting the run-context would change what the harness *declares*, not what it *reads*: the same
8 carriers, plus 100 rows recording that the remaining companies are outside the registry. That is
a real improvement in comparability and a real cost in build time, and it was **deliberately not
taken** (Matthew Lebrecht, 2026-09-17) with the project close to its deadline. The limitation is
recorded here instead.

### Where to check it

`python scripts/published_coverage.py` (the harness's `n/a` line); `Attempts` holds rows for sixteen
harness ids and none for `H-FMCSA-01`; `harnesses/h_fmcsa_01/harness.py` imports no run-context.
Found and measured 2026-09-17 while verifying run HR-0084.
