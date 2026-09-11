# Session 6 report — 2026-09-02

Three pieces of work, all of them handed down rather than discovered: an incident
investigation, the Week 3 package (a doc merge plus an approved schema delta), and two
decisions from Matthew that unblocked the parts held open.

**Read §0 first.** One reported data-loss incident turned out to be no loss at all, and the
thing that actually caused it is still sitting in the repo.

---

## 0. Flag

**1. The "missing" audited finding was never missing — but 38 stale workbook copies are still
in the data directory.** O00366 (Merit Medical, `H-PRODUCTQUALITY-01` v1.1, Matthew's
`overgraded` verdict) is intact and has been present in every workbook commit since it was
written. What is *not* intact is the environment around it: `data/` holds 31 gitignored
`.bak-*` files and `data/archive/` holds 7 tracked copies, and **29 of those 38 show the
harness with zero rows.** That is a live hazard independent of this incident. §1.

**2. Part A's merge is complete and its callout is now true.** With §25/§26 appended in the
decided order the document reads §19–§26 sequentially and all six verification checks pass,
including check 3, which was the one held open.

**3. The `cybersecurity_ot` split kept the existing key rather than renaming it, and that was
forced by four released observations.** Stated plainly in §4 because the alternative would
have orphaned them.

---

## 1. Incident — the audited H-PRODUCTQUALITY-01 finding

**Reported:** the harness shows 0 rows; where did the audited finding go?
**Established, read-only:** nothing was lost.

`O00366` is in the workbook now — row 311, `audit_verdict = overgraded`, `review_status =
corrected`, `review_source = human`, `publication_state = released`, reviewer note complete.
Traced across all 23 workbook commits: present in every one since `f109174` created it, and
the human-provenance count only ever rose, 27 → 30 → 39. All 39 human-reviewed rows are
present. The verdict fields and notes are **byte-identical across all seven commits** since
they were recorded — same SHA-256, same 653 characters.

Every candidate ruled out individually: no `delete_observations` caught it (the session-4
renumbering was H-EXECVOICE-01's rows, a different id range); the v1.2 population change did
not remove it; HR-0026's "1 held for review" protection held and still holds; session 5's
C0008 restoration and re-runs wrote nothing to it. No autofilter, no hidden rows.

**What produced the symptom, in order of likelihood:**

1. **38 stale workbook copies beside the live file.** `data/*.bak-*.xlsx` (31, gitignored,
   auto-created by `migrate_schema.py`, `register_sources.py` and `extend_validation.py` on
   every `--apply`) plus `data/archive/*.xlsx` (7, **tracked**). 29 predate O00366 and show
   `PQ=0`. Near-identical names, same folder, no warning.
2. **HR-0026 genuinely records 0.** The newest run row for that harness says
   `observations_produced_count = 0`, `quarantined` — correct about that run, since v1.2
   proposed nothing new, but it reads like the harness has no findings.
3. **I moved the audit sheet the night before.** `H-PRODUCTQUALITY-01__review.md` →
   `__v1.1__review.md` in `b7d97e7` (R100, content identical). Anyone returning to the
   remembered path finds nothing there.

**Open:** the backup accumulation. Nothing was cleaned up — the investigation was read-only
by instruction and disposal is a separate decision.

---

## 2. Part A — the taxonomy merge, now complete

Merged `taxonomy_merged_sections_2026-09-02.md` into `docs/signal_taxonomy.md`. 536 → 1,058
lines.

The input file's own section order ran 19, 20, 21, 22, 23, 24, **26, 25**, so appending in
file order would have produced an out-of-order document and failed the instructions' own
check 3, while reordering was an editorial call the instructions forbade resolving. The merge
was halted after §24 and reported. **Matthew's ruling: §25 first.** Appended in that order,
content untouched.

| Check | Expected | Result |
|---|---|---|
| 1 · stale patch-era numbers in appended range | 0 | **0** |
| 2 · family headings | 18 | **18** |
| 3 · new sections in order | §19–§26 | **§19–§26, sequential, no gaps** |
| 4 · `## NEW §` marker | 0 | **0** |
| 5 · `UNMERGED PATCH` | 0 | **0** |
| 6 · Legend dimensions | 2 | **2** |

A diff of the pre-existing portion shows **exactly three edits** and nothing else: the
blockquote replacement, two Legend bullets (blockquote prefix stripped so they match existing
formatting, which is what check 6's anchor requires), and the family 3 amendment appended
without a blank line so it reads as one paragraph. Every appended block is byte-identical to
source apart from the `NEW ` strip on eight headings. No reflow anywhere.

---

## 3. Part B — the schema delta

Built, except the part that depends on a table nobody has created.

| Target | Result |
|---|---|
| `Harness_Sources` | +`nominal_reach`, `nominal_reach_months`, `realized_reach`, `realized_reach_months`, `realized_reach_effective_from` |
| `Lookups` | +`retrospective_reach` (column V), bound to both enum columns — **24 → 26 validations** |
| `Signal_Types.status` | +`out_of_theme`, `access_bounded`, `reference` |
| `core/topics.py` | +`theme_id`, `display_label`, `definition`, `definition_hash`, `buyer_detectable_since` |
| `Company_State_History` | **BLOCKED — the sheet does not exist** |

**Reach lands on `Harness_Sources`, not on a harness**, because §21 scores it per *source*:
H-PROCUREMENT-01 alone spans two values (USASpending `archival`, SAM.gov `current_only`),
which a per-harness column could not represent.

**`inactive` was retained.** §22.1 names five status values; the workbook already held
`inactive`, which is not among them. Convention 22 is additive-only and a value is retired by
going unused, never by deletion — a query over historical `Signal_Types` rows must not break.
So the column holds **six** and §22.1's five are the live set. Flagged, not reconciled away.

**`key` was not renamed when `theme_id` was added.** Theme keys are written into committed,
human-reviewed Observations — O00366 carries topic `digital_transformation_process` under a
human `corrected` verdict — so renaming would break provenance for a cosmetic gain. Same
reasoning that grandfathered H-FMCSA-01. `display_label` aliases `label`, which four harnesses
already read.

**`definition` is deliberately empty on every theme.** §25.4 demands written boundaries and
nobody supplied them; inventing them would manufacture the content that section exists to
demand. `definition_hash` therefore hashes the **operative** definition — key, label, note and
patterns — because patterns decide routing today, so a pattern edit is a definition change in
§25.1's sense whether or not prose moved. Verified by mutating an input and asserting the hash
moves.

**`buyer_detectable_since` is populated, and six of the dates are derived.** Null means "never
detectable", so leaving instrumented themes null would assert something false. The three
flipped themes take **2026-08-31** (stated in `core/topics.py`'s own docstring); the rest come
from committed records — **2026-08-24** from H-JOBPOST-01 v1.0's manifest, **2026-08-22** for
`transportation_fleet_systems` from H-FMCSA-01 HR-0001, its earliest instrument. Grounded, but
Part B itself warns this is what gets baked into immutable history, so **worth confirming**.

**Blocked:** the `Company_State_History` columns (`min_retrospective_reach`, `definition_hash`,
the `not_instrumented` reason split). That sheet is the temporal/historical design and has not
been built. Three of Part B's four invariants govern a derivation that writes it, so they are
recorded **PENDING** in `core/tests/test_schema_delta.py` rather than asserted vacuously — a
test passing over an unbuilt requirement asserts the implementation, not the requirement
(convention 40). Invariant 3 *is* asserted, since the rollup layer exists.

---

## 4. The `cybersecurity_ot` split

Signal Advisor's blocking item: the theme was labelled "cybersecurity and OT/IT convergence"
while **all eight of its patterns were security terms.** No SCADA, PLC, ICS, DCS, historian,
control system, HMI, industrial network or plant-floor connectivity — so OT *modernization*,
a central story for construction, energy, food distribution and manufacturing, was invisible
to the classifier on both sides of the market. **Matthew's ruling: Option A, split.**

**What happened to the existing key, stated plainly.** The continuing theme keeps **both**
`key = cybersecurity_ot` and `theme_id = THEME-08`, with every pattern unchanged; only the
label narrowed to "cybersecurity". The new theme mints `key = ot_modernization`,
`theme_id = THEME-10`.

The key was **not** renamed to `cybersecurity`, despite Option A's wording inviting it,
because **four released observations carry `cybersecurity_ot` as their topic** — O00225,
O00230, O00234, O00255, all H-SELLERCONTENT-01 provider rows (P004/P005/P006/P012). All are
`machine` / `unreviewed`, so no human provenance and convention 35 is not engaged, but
renaming would have orphaned all four from the theme spine. The confirmation's own §6 settles
it: `key` is the identifier of record, `label` is free, a split mints a new key, an existing
key is never repointed.

**The cost, recorded rather than hidden:** `cybersecurity_ot` is now a key string that no
longer describes its contents. That is the H-FMCSA-01 trade (convention 26). The rename is
cheap *today* — four machine rows, nothing derived — and stops being cheap the moment
`Company_State_History` exists.

**Regression (convention 37).** 0 of 337 observations changed theme set under old vs. new
spine. All nine pre-existing themes: pattern sets identical, theme_ids unchanged, one label
changed by design. No probe text lands in **both** themes or in **neither**.

**Downstream.** `cybersecurity_ot` is unchanged in `gap_report.py` — still 4 sellers / 0
buyers / "buyer silent" — so the formally-untested divergence §26 names is intact and §26
needed no edit. `ot_modernization` reports **0 / 0 / NO INSTRUMENT**, which is correct:
`buyer_detectable=False`, `buyer_detectable_since=None`, and per §25.2 that is null, not zero,
so its absence is not a divergence and must not be reported as one.

**Nine → ten, and the tension is Signal Advisor's own.** Item 1 of the confirmation says
"freeze at nine, nothing pending adds a theme"; item 2 recommends a split producing ten. Both
sit in the same document. Noted, not resolved.

---

## 5. Files added

| File | Why |
|---|---|
| `taxonomy_merged_sections_2026-09-02.md` | Part A's input, written from the supplied text so the merge ran off a real file. Committed per the merged callout's own "superseded but retained" rule. |
| `week3_code_session_package_2026-09-02.md` | The package itself, verbatim, with a header recording what was done against it. |
| `signal_advisor_theme_confirmation_2026-09-02.md` | Reported missing, then supplied. Decision input only — nothing in it was acted on except item 2, which Matthew separately ruled on. |
| `core/tests/test_schema_delta.py` | 36 checks, 3 pending. |

---

## 6. Where I chose conservatively

1. **Halted Part A after §24** rather than reordering §25/§26, and did not let Part B's arrival
   pressure the decision. The instructions said stop and ask; the question was outstanding.
2. **Left step 1's callout saying "§§19–26"** while only §19–§24 were present, rather than
   editing it to match — that would have resolved the held question through the back door. It
   is now true as written.
3. **Kept the `cybersecurity_ot` key** rather than renaming, on the strength of four released
   rows (§4).
4. **Did not fabricate `signal_advisor_theme_confirmation_2026-09-02.md`** when it was cited
   but absent, and did not infer it from Part B.
5. **Left `definition` empty** rather than writing §25.4's boundaries myself.
6. **Recorded three Part B invariants as PENDING** rather than writing tests that would pass
   over an unbuilt derivation.
7. **Did not act on** items 3, 5, 6, 7 of the theme confirmation, or on the H-JOBPOST-01
   cloud/security/workforce signal keys, which remain recommended-not-authorized.

---

## 7. Open items

**For Matthew:**
- **38 stale workbook copies in `data/` and `data/archive/`** — the thing that most likely
  produced the missing-finding report. Disposal is a decision, not a cleanup I should make.
- **The six derived `buyer_detectable_since` dates** (§3) — grounded in committed records but
  worth a glance before anything derives against them.
- **The `cybersecurity_ot` key rename** — cheap now, expensive later (§4).
- **`workforce_enablement` boundaries** (confirmation item 3) — still required before freeze,
  still unwritten, and the reason `definition` is empty.
- Carried: the 20 held H-FMCSA-01 conflicts, the provisional 0.10 threshold, `observation_id`
  renumbering, and the three versions awaiting audit.

**Referred, not acted on:**
- Confirmation item 6 — the three IC1-only themes have no H-JOBPOST-01 signal key. Named as
  the cheapest high-value change available.
- Confirmation item 7 — `systems_integration` matches bare `\bAPI\b` and `\bintegration\b` at
  `min_hits=1`, flagged as the highest false-divergence risk in the file. Worth noting that the
  same document's `\bLean\b` observation is the defect already fixed on the *buyer* side in
  H-JOBPOST-01's classifier last session; the provider-side pattern in `core/topics.py` still
  carries it.
- Confirmation §0 — `legacy_constraint` is an `organizational_state`, not a theme. This
  corroborates last session's finding that H-JOBPOST-01 writes zero `legacy_constraint` rows
  and that 54 of 56 come from H-SAFETY-ENV-01.

---

## 8. State at hand-off

337 observations (311 released, 26 quarantined), 3,659 attempts, 37 runs, 120 companies,
**10 themes**, 24 signal types, 26 validation bindings.

All eleven suites green — `test_schema_delta` 36 passed / 3 pending, `test_audit_gate` 56,
`test_jobpost` 42, `test_attempts` 35, `test_tradepress` 34, `test_reconcile` 27,
`test_resolution` 25, `test_productquality` 19, plus empreview, execid and execvoice.
`validate_repo_db` 9 checks, `assert_validations` 26 bindings, `check_run_ledger --strict`
clean.

**The workbook was not written to after the Part B migration.** The split and the merge are
code and documentation only.
