# Session 7 Report — Post-Session-6 Follow-up

**Date:** 2026-09-02
**Brief:** `code_session_followup_2026-09-02.md` (three items; item 1 blocking)
**Model:** Claude Fable 5.1 (first session on this model)

## Summary

**1. The 120 is real, live, and not growth.** 120 = the 108-company buyer universe + the 12
provider benchmarks `P001`–`P012`, which have lived in the same `Companies` sheet since
22:39 on 2026-08-30. No duplicates, no leaked fixtures, no scope decision anywhere. The
figure in session 6's hand-off line is what `validate_repo_db.py` check 8 printed
("referential integrity holds across 120 companies") copied without its composition. Check
8 now says "120 companies (108 buyers + 12 provider benchmarks)". §1.

**2. 32 stale workbook copies deleted, recorded first.** Not 31: one more was created by the
Part B migration's `--apply` on 2026-09-02 after session 6 counted. Per-file record in
`docs/archive/stale_workbook_copies_2026-09-02.md`. The four `--apply` scripts now back up
through one helper that keeps the newest three. The 7 tracked copies in `data/archive/` are
**recommended to stay tracked**, and I acted on that recommendation only to the extent of
adding a README there; untracking is one command if you decide otherwise. §2.

**3. `cybersecurity_ot` → `cybersecurity`, applied end to end.** Four rows rewritten by a
new idempotent migration step that refuses human-reviewed rows; regression re-run and kept
as a script this time; 0 of 337 observations change theme set; every suite and check green.
§3.

**Nothing is committed.** Eleven modified files, five new, the workbook among them. The
commit command is at the end.

---

## 1. Where the 120 came from

**Established, read-only, before anything else was touched.**

| question in the brief | answer |
|---|---|
| live count or stale carry-over? | **Live.** `Companies` has 120 non-empty rows in the working tree and 120 at HEAD |
| composition | `A001`–`A100` (100) + `C0001`–`C0008` (8) + `P001`–`P012` (12). 120 distinct ids, 0 duplicates |
| by status | 107 `qualified`, 1 `pending_review`, 12 `provider_benchmark` |
| when did it become 120? | Between the `.bak` copies timestamped 22:35 and 22:39 on 2026-08-30: 108 → 120, `Observations` 35 → 73, `Harness_Runs` 5 → 6. That is the H-SELLERCONTENT-01 build |
| was the decision logged? | Yes. `SESSION_REPORT_2026-08-30.md` line 55: "Providers live in `Companies` under a new `qualification_status = provider_benchmark`", and README line 103 gives the reason (one `company_id` foreign key rather than two). CLAUDE.md's company-universe section already said the same thing in different words |
| first commit with 120 | `6b97d0b` (2026-08-31), the workbook's first commit. Every commit since has had 120 |
| does any harness iterate 120? | No. Six filter `!= provider_benchmark`, two filter on the `C`/`A` id prefix, two pass an explicit status tuple (`qualified`, `pending_review`, `soft_gate_exception`), one (H-EXECVOICE-01) reads providers deliberately for its exclusion list. All buyer denominators are 108 |

**Why the number looked like growth.** The hand-off line was assembled from
`validate_repo_db.py`'s output, and check 8 counted the whole sheet without saying what it
was made of. That is the convention 36 shape the brief anticipated: a lookup that answers
about the wrong thing (the sheet) reports success confidently about the thing you asked
(the universe). Fixed at the source: check 8 now prints the decomposition, so the next
hand-off line copied from it carries the explanation with it.

**One inaccuracy found on the way, in CLAUDE.md rather than the workbook.** It said all 8
pilots were `qualified`. C0007 PLS Logistics has been `pending_review` since 2026-08-22
(`notes`: "DELIBERATE borderline case to test soft-gate judgment"; confidence 0.45).
Harmless for coverage: both status-filtering harnesses include `pending_review`, and the
`Attempts` sheet shows C0007 attempted by 9 harnesses. CLAUDE.md corrected.

**Treated with the suspicion the brief asked for.** The fast explanation (108 + 12) was
checked against three independent things before being written down: the row-level diff
of the sheet (ids, statuses, duplicates), the `.bak` timeline (which pins the change to a
four-minute window and a named build), and the harness code (which shows nothing consumes
the 120). All three agree.

---

## 2. The stale workbook copies

**Deleted:** 32 `data/market_intel_db.bak-*.xlsx` (gitignored, 7.6 MB). Session 6 counted
31; `bak-20260902-194027` was added by the Part B migration's `--apply` at 19:40 that day,
after the count. It was byte-identical to the workbook at `c00944c`.

**Recorded first**, per Matthew's decision: `docs/archive/stale_workbook_copies_2026-09-02.md`
lists every file with mtime, size, row counts for five sheets, `H-PRODUCTQUALITY-01` row
count, whether O00366 was present, human-reviewed row count, and which commit (if any) its
bytes match. Findings worth keeping from that table:

- **12 of the 32 were byte-identical to a committed workbook.** They held nothing git did
  not. The other 20 were mid-session states between commits.
- **22 of the 32 predated O00366** and showed `PQ = 0`. With the 7 archive copies that is
  the 29 session 6 counted. Those are the files that produced the false alarm.
- `shutil.copy2` preserves mtime, so a copy's filename says when the `--apply` ran and its
  mtime says when the live workbook was last saved before that. The two differ by up to
  ten hours on some rows. Worth knowing before trusting either timestamp.
- The `Companies` 108 → 120 transition is visible in the table (item 1 above).

**The 7 tracked copies in `data/archive/` — recommendation: keep them tracked.** Reasons:

1. They all predate the workbook's first commit. Git holds no other copy of the Week 1
   workbook; untracking them deletes the only pre-repository history.
2. Two are load-bearing: `reconstruct_workbook.py` reads `backup-pre-jobpost-231246` as its
   base and `STALE-2026-08-26` as the file it rescues the Anvil-100 rows from. Untracking
   makes the reconstruction unreproducible from a clone.
3. `pre-v12` / `pre-v13` are the evidence for the validation-loss finding recorded in
   `migrate_schema.py`'s docstring.
4. 188 KB total. The hazard was never their size; it was 32 near-identical names beside the
   live file. These have different name patterns (`.backup-`, `.STALE-`), sit in a
   subdirectory, and now have a README saying what they are and that they never change.

The alternative, flagged rather than chosen: untrack and move them out of the repo
(`git rm --cached data/archive/*.xlsx`), accepting that `reconstruct_workbook.py` becomes
a script that documents a procedure rather than one that can run. "Tracked" was not a
deliberate decision originally, and this is the first time it has been made one either way.

**So it does not reaccumulate.** `core/workbook_backup.py::backup_workbook(path, keep=3)`
is now the only place a `.bak` is taken. `migrate_schema.py`, `register_sources.py`,
`extend_validation.py` **and `reconstruct_workbook.py`** (the brief named three; the fourth
did it too) all call it, and each prints what was pruned. Why prune rather than stop
entirely: the workbook is tracked and `check_run_ledger.py` diffs it against HEAD, so git is
the durable backup; a `.bak` only covers the window between the last commit and a botched
`--apply`. Three copies cover that window. Thirty did not cover it better. The stronger
option (no `.bak` at all) is a one-line change to `KEEP_DEFAULT` if wanted. Sanity-tested:
five fakes plus one real backup → three remain, the real one among them.

`extend_validation.py` also used a different naming pattern (`<file>.xlsx.bak-<ts>`, suffix
last), which the `.gitignore` glob covered but the prune glob would not have. Normalised.

---

## 3. The `cybersecurity_ot` rename

### What changed

| where | change |
|---|---|
| `core/topics.py` | THEME-08 `key = "cybersecurity"`; `theme_id`, patterns, label, note, `buyer_detectable_since` unchanged. New `RETIRED_THEME_KEYS = {"cybersecurity_ot": "cybersecurity"}`, with import-time assertions that no retired key is live and every replacement is. Comments rewritten to record the decision and the two facts it rested on (no human provenance; nothing derived yet) |
| `scripts/migrate_schema.py` | New step `rename_topic_keys`, reads the map, rewrites `Observations.topic`, **aborts** if a human-reviewed row carries a retired key (convention 35: that is a decision, not a migration). Idempotent: second run reports "no Observations row carries a retired theme key" |
| workbook | O00225, O00230, O00234, O00255 → `topic = cybersecurity`. Verified by reading the sheet back, not from the migration's own report. `review_source = machine`, `review_status = unreviewed`, `publication_state = released` on all four, unchanged |
| `scripts/validate_repo_db.py` | check 8 fails if any `Observations.topic` is a retired key; check 8's message decomposes the company count |
| `scripts/theme_regression.py` | **new**, see below |
| `core/tests/test_schema_delta.py` | §5/§5b rewritten for the new key; three checks added (retired key declared and absent from the spine; every retired key maps to a live one; no workbook row carries a retired key; the four rows carry `cybersecurity`). 36 → 40 checks |
| `docs/signal_taxonomy.md` | header note (line 12) updated: the split is decided and the key renamed; §26 row labelled "Cybersecurity (`THEME-08`, key `cybersecurity`; labelled Cybersecurity / OT until the split)". Signal Advisor's text otherwise untouched |
| `harnesses/h_tradepress_01/extract.py` | two historical comments annotated "(renamed `cybersecurity` 2026-09-02)" rather than rewritten — they describe a measurement taken under the old key |
| `gap_report.py` | no edit needed; it reads the spine. Now prints `cybersecurity  4  36%  0  buyer silent`, `ot_modernization  0  0%  0  NO INSTRUMENT` |
| README, CLAUDE.md | script table, counts, the 120 explanation, the C0007 correction, two new known-gap entries |

### The regression check, kept this time

Session 6's "0 of 337 changed" was run by hand and not committed, so the brief's "re-run
the regression check from session 6" had nothing to re-run. `scripts/theme_regression.py`
loads `core/topics.py` at a git revision (`--baseline`, default HEAD) beside the working
tree's, classifies every observation's `observation_text + evidence_excerpt` under both
with retired keys mapped forward, prints the theme inventory by `theme_id`, and fails on
any routing change, any retired key in the topic column, or any key change without a
`RETIRED_THEME_KEYS` entry.

Run **before** applying the migration (baseline = HEAD, i.e. session 6's spine):

```
1. theme inventory: THEME-01..07, 09, 10 identical; THEME-08 key 'cybersecurity_ot' -> 'cybersecurity' (declared retirement)
2. routing: 0 of 337 observations changed theme set
3. Observations.topic: FAIL: 4 row(s) still carry retired key(s) ['cybersecurity_ot']: O00225, O00230, O00234, O00255
```

Run **after**:

```
2. routing: 0 of 337 observations changed theme set
3. Observations.topic: 135 rows carry a live theme key, 7 a buyer signal key mapped to a theme, 195 a harness-native topic with no theme mapping
   ok: no row carries a retired theme key
clean: 337 observations route identically under HEAD and the working tree; 1 theme(s) differ in inventory, all declared.
```

**What that 0 does and does not say.** The text classified is the observation's own text,
which for most harnesses is the sentence the harness wrote, not the source page. So it is a
check on the spine (same text, same routing) and not on the harnesses. A pattern change can
alter what a harness would extract on a re-run; only a re-run shows that. There was no
pattern change here, so the caveat is recorded for the next use, not this one. After the
commit, the baseline to compare against session 6's spine is `--baseline 127cd45`.

### What was deliberately left carrying the old string

- **`observation_text` on the four rows** still reads "markets capability in cybersecurity
  and OT/IT convergence (2 of 2 service pages)". That is what H-SELLERCONTENT-01 wrote at
  retrieval, using the label of the time. The brief asked to propagate the *key*; the text
  is a record of what was written, and a re-run under the current label would regenerate it
  as "markets capability in cybersecurity". Flagged in CLAUDE.md. If you want the text
  rewritten too, say so; it is four cells and machine-authored.
- **`data/snapshots/gap_report.csv`** is a 2026-08-30 snapshot (tracked) and still lists
  `cybersecurity_ot` at 4 / 36% / NO INSTRUMENT. It is dated output, not a binding.
- **Run logs under `harness_output/`** (gitignored) carry the old key in H-FIRSTPARTY-01's
  and H-SELLERCONTENT-01's 08-30/08-31 decision logs. Historical; untouched.
- **`definition_hash` for THEME-08 changed**, because `key` is in the hash payload. Nothing
  has been stamped with a hash yet (no `Company_State_History`), so this has no consequence
  today. It is exactly the thing that would have had a consequence later, which is the
  reason for renaming now.
- **`session6_report.md`** still says the key was kept and why. It was true when written;
  this report is the record of the reversal.

### Verification

Eleven suites: `test_schema_delta` **40 passed / 3 pending** (was 36), `test_audit_gate` 56,
`test_jobpost` 42, `test_attempts` 35, `test_tradepress` 34, `test_reconcile` 27,
`test_resolution` 25, `test_productquality` 19, plus empreview, execid and execvoice, all
exit 0. `validate_repo_db` 9 checks pass; `assert_validations` 26 bindings; `check_run_ledger
--strict` clean, including "CLAUDE.md's stated counts match the workbook" after the edits.
`migrate_schema.py` report mode after apply: "nothing to do -- schema is current".

---

## 4. State at hand-off

337 observations (311 released, 26 quarantined), 3,659 attempts, 37 runs, **120 `Companies`
rows = 108 buyers + 12 provider benchmarks**, 10 themes, 1 retired theme key, 24 signal
types, 26 validation bindings. One `.bak` in `data/` (the one this session's `--apply` took).

**Uncommitted.** Modified: `CLAUDE.md`, `README.md`, `core/topics.py`,
`core/tests/test_schema_delta.py`, `data/market_intel_db.xlsx`, `docs/signal_taxonomy.md`,
`harnesses/h_tradepress_01/extract.py`, `scripts/{migrate_schema,register_sources,
extend_validation,reconstruct_workbook,validate_repo_db}.py`. New: `core/workbook_backup.py`,
`scripts/theme_regression.py`, `data/archive/README.md`,
`docs/archive/stale_workbook_copies_2026-09-02.md`, this report, and the brief itself
(`code_session_followup_2026-09-02.md`, which was untracked when the session started).

## 5. Carried, not bundled (unchanged from session 6's list)

Nine-vs-ten theme freeze tension (Signal Advisor); the six derived `buyer_detectable_since`
dates; `workforce_enablement` boundaries (§25.4); held H-FMCSA-01 conflicts; the 0.10
threshold; `observation_id` renumbering. New from this session, minor: the four rows'
`observation_text` (above), and `data/snapshots/gap_report.csv` is a snapshot nobody has
refreshed since 08-30 — decide whether it is a dated artifact or a living file.

---

## 6. Follow-up (same day, `code_session7_followup_2026-09-02.md`)

- **`observation_text` on the four rows regenerated** by a new idempotent step,
  `migrate_schema.py::relabel_observation_text` (machine rows only; aborts on human
  provenance). A faithful re-run changes two things, not one: the label becomes
  "cybersecurity", and the trailing "NOTE: no buyer-side harness can currently detect this
  theme" sentence is dropped, because H-SELLERCONTENT-01's template only appends it while
  `buyer_detectable` is False and THEME-08 flipped on 2026-08-31, the day after these rows
  were written. Verified by reading the four cells back; no other row carried the old label.
- **`data/snapshots/gap_report.csv` refreshed** from the current spine: `cybersecurity`
  4 / 36% / 0 / buyer silent, `ot_modernization` 0 / 0% / 0 / NO INSTRUMENT, and the buyer
  counts now reflect the 337-row base rather than the 08-30 state (e.g. `data_analytics_ai`
  0 -> 35 buyer companies). Matthew confirmed it is a living file, not a dated snapshot.
- **Regression against session 6's spine** (`--baseline 127cd45`): 0 of 337 changed, one
  inventory difference, declared. All 11 suites, 9 validator checks, 26 bindings, ledger clean.
- Session 7's main work was already committed as `8d439bf` before this brief arrived; this
  follow-up is its own commit.
