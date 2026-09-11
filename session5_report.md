# Session 5 report — 2026-09-01 (evening). Closes Week 2.

Per the brief: **row deltas only for quarantined work; published coverage figures for
released versions only, with exclusions stated.**

**Read §0 before 5:15.** Two things in the brief could not be executed as written, one
finding changes what the job-postings harness can ever reach, and the audit gate had a live
defect in its own machinery that would have fired on tonight's release.

---

## 0. Flag before the checkpoint

**1. Matthew reviewed two review sheets, not five, and the other three could not be
audited tonight.** Dispatch's relay note is right and the workbook confirms it: nine
verdicts exist, all on H-EXECVOICE-01 v1.2 (8 rows) and H-TRADEPRESS-01 v1.2 (1 row). Of
the other three, H-PRODUCTQUALITY-01 v1.2 **cannot** have a review sheet — its run wrote
zero observations, and the sampler exits on an empty population. H-LEGAL-01 v1.1's sheet
was never emitted. H-TRADEPRESS-01 v1.1's was clobbered. **Two versions released, three
still quarantined, nothing manufactured.**

**2. The audit gate's own artifact loader was reading the wrong files, and releasing would
have exposed it.** `load_artifacts()` globbed `*.json` and keyed on the `harness_id` /
`harness_version` fields inside each file — which the sampler's `__strata.json` sidecars
also carry. Two of the four "artifacts" it returned today were strata files. Nothing had
failed only because both affected versions were quarantined, so check 9 never looked them
up; publishing either would have made the check report a valid, freshly-written artifact
as **malformed**. Convention 36, in the gate's own machinery. §1.

**3. Every third-party job board is closed, not just LinkedIn.** The brief asked me to
probe Indeed honestly rather than assume. Indeed disallows `/jobs` and `/viewjob?` as well
as the `/cmp/` path already known to refuse us. With LinkedIn at `Disallow: /`, **own-domain
careers pages are not merely the primary leg of H-JOBPOST-01 but the only open one** — and
that bounds this instrument permanently, not just tonight. §3.

**4. H-JOBPOST-01's real constraint is not access or precision — it is that careers pages
are JS-rendered.** Discovery finds a careers page for most of the universe on its own
domain. What it usually cannot find is an ATS in the server-rendered HTML. That converts
"no source configured" into a specific, named gap, which is progress, but the coverage
number stays low and the reason is now precise. §3.

---

## 1. Task 1 — the release, and the ruling on H-TRADEPRESS-01 v1.1

### The ruling the brief asked for first: check 9 is **not** mis-scoped

Check 9 iterates published pairs only; a quarantined pair goes into a set that is never
looked up. **It never fired on v1.1 and could not have.** The trigger really is "contributes
to a published coverage number", exactly as documented.

So this is neither a scoping defect nor a gate failure. It is a **bookkeeping gap**:
`quarantined` was holding two states that route to different actions. "Awaiting an audit" is
a backlog item; "will never be audited, because a later version re-ran the same scope and
holds its output" is a decision. Conflated, v1.1 sits in the audit queue forever with
nothing anyone can do about it.

That is the same shape as convention 39's `suppressed_redundant` split and as tonight's
`access_blocked` split — one flag holding several states that need different actions. The
third instance in two sessions.

**`superseded` added**, and the claim it makes is **enforced rather than trusted**: check 9
now fails if a superseded version still holds observations, or is superseded on one run and
published on another. A disposition that merely silenced the gate would *be* the way around
a failing audit the gate text rules out.

Verified before applying: H-TRADEPRESS-01 v1.1 holds **0 observations**, and HR-0028's 30
attempts are the **same `(company, signal)` set** as v1.2's HR-0030 — set equality, not
containment. Not grandfathered, per the brief.

### The naming defect, and the one it exposed

Review sheets and strata files were keyed on harness id alone while artifacts were
version-keyed, so a version bump silently destroyed the prior version's sheet. Now
`<harness_id>__<version>__review.md` / `__strata.json`; the six existing files were renamed
(each self-identifies its version in its own header, so the mapping was read, not inferred).

The rename **made the sidecar collision worse**, which is how it surfaced: post-rename sort
order puts `__v1.2__strata.json` *after* `__v1.2.json`, so the sidecar would have clobbered
the real artifact rather than being clobbered by it. A file is now an artifact only if its
name round-trips through `audit_path()`, and a file declaring an id and version under some
other name is **reported** rather than skipped — a misnamed real artifact is a defect and
must not read as an absent one.

### Released

| Version | Rows | Control | Verdicts | Precision |
|---|---|---|---|---|
| H-EXECVOICE-01 v1.2 (HR-0029) | 8 | **census**, 8 of 8 | 7 supported, 1 overgraded | 87.5% |
| H-TRADEPRESS-01 v1.2 (HR-0030) | 1 | **census**, 1 of 1 | 1 supported | 100% |

Both controls are a census — the whole population was judged — so each rate is exact for
its run and carries **no confidence interval**. Exclusions 0% against the provisional 0.10
threshold, so **nothing published depends on that number being right**. No `wrong_entity`
anywhere, so no `reprocessing_required` was set by audit, per the brief.

Stratum verdict counts are **derived from the verdicts recorded in the workbook**, not
typed: because both controls were a census, every stratum row already carries Matthew's
judgment, and the deriving script aborts on any sampled row with no recorded verdict rather
than defaulting it.

**Still quarantined, and why:** H-PRODUCTQUALITY-01 v1.2 (0 observations — no sheet is
possible), H-LEGAL-01 v1.1 (1 unjudged row, O00377, no sheet emitted), H-TRADEPRESS-01 v1.1
(superseded).

### The gate verified in both directions

Against the live workbook, per convention 40 and the brief: artifact present → check 9 exits
0; artifact moved away → exits 1 naming the version; restored → 0. And the **writer side**
refuses before the fact — `set_version_publication` declined H-LEGAL-01 v1.1 and
H-PRODUCTQUALITY-01 v1.2 for having no artifact. A control that only fails after the write
is a report, not a gate.

### Published coverage — released versions only, no blended figure

`scripts/published_coverage.py`. Recomputed from `Attempts` rather than read off the rollup
column, so a divergence is reportable rather than hidden (there is none today).

| Harness | Version | Scoped | Covered | Rate | Basis |
|---|---|---|---|---|---|
| H-EXECID-01 | v1.0 | 108 | 63 | 58.3% | grandfathered |
| H-EXECVOICE-01 | v1.2 | 108 | 61 | 56.5% | **audited** |
| H-FIRSTPARTY-01 | v1.1 | 108 | 105 | 97.2% | grandfathered |
| H-PRODUCTQUALITY-01 | v1.1 | 108 | 13 | 12.0% | **audited** |
| H-SAFETY-ENV-01 | v1.1 | 214 | 200 | 93.5% | grandfathered |
| H-SELLERCONTENT-01 | v1.2 | 12 | 11 | 91.7% | grandfathered |
| H-TRADEPRESS-01 | v1.2 | 30 | 15 | 50.0% | **audited** |
| H-WAYBACK-01 | v1.1 | 107 | 93 | 86.9% | grandfathered |

**Excluded, and listed rather than dropped:** H-EMPREVIEW-01 v1.0, H-LEGAL-01 v1.0 and
v1.1, H-PRODUCTQUALITY-01 v1.0 (×2) and v1.2 — quarantined; H-TRADEPRESS-01 v1.1 —
superseded.

**Two published versions report no rate at all.** H-FMCSA-01 v1.3 and H-JOBPOST-01 v1.0
predate the attempts run-context and have **no Attempts rows**, so their denominator does
not exist. Shown as `n/a` rather than 0% or 100%. Tasks 3 and 4 close both.

**No blended project-wide figure**, deliberately. The denominators are 108 companies, 12
providers and a 15-company subset, and convention 21a says the instruments are not equally
biased, so a mean over them names nothing.

---

## 2. Task 2 — the three-way split, and what the data actually says

Stated against the brief's expectations so the mismatches are visible.

**Confirmed as asked, by search rather than assumption:** USASpending and PatentsView appear
in **zero** attempt rows — searched across `failure_detail`, `failure_category` and
`source_url_attempted`. That is convention 38 having worked *prospectively*: the 108 rows
that were never written are why there is nothing to correct now.

**Three divergences from the brief.**

1. **There are no "39 robots-blocked" rows and no trade-press 403s.** Every row mentioning
   robots is already `access_blocked` (117). The only 403s outside it are 7 H-EXECID-01
   homepage failures under `source_unavailable`.

2. **The rate limits are not in `access_blocked`.** They are **63 HTTP 429 rows under
   `source_unavailable`**, where session 4's ruling correctly put them. Scoping this report
   to `access_blocked` would have found zero rate limits and concluded the flag was already
   clean; it counts every attempt row instead.

3. **Family 4's 107 rows cannot be given one label honestly, and this is the substantive
   finding.** Each records one `(company, signal)` pair whose signal draws on **three
   sources with different postures**, in one free-text field: Glassdoor and Indeed refused by
   published robots.txt, Comparably rate-limited. **The flag was not the only thing
   overloaded — the attempt row was.**

   Resolved by precedence on the **binding** constraint: pace better and Comparably may
   answer; Glassdoor and Indeed never will, so the row is access-bounded either way. The
   co-occurring class is retained and reported, not discarded (convention 7).

### The count

| Class | Rows | |
|---|---|---|
| **source_refusal** | **117** | 107 family-4 + 10 LinkedIn (5 at superseded v1.1, 5 at published v1.2) |
| rate_limited | 63 | H-WAYBACK-01 429s — recoverable by pacing |
| egress_blocked | 2 | H-EXECID-01 `CERTIFICATE_VERIFY_FAILED` — **ours, not a source's** |
| UNCLASSIFIED | 32 | reported, never defaulted |

**ACCESS_BOUNDED is 117**, and it is now a count of source refusals only.

The 2 egress-blocked rows sit in `source_unavailable`, so they never polluted an access
count — but they are the condition convention 38 names, and they are now visible as ours
rather than a source's.

**No new `failure_category` values**, per the brief and the session-4 ruling. Harnesses stamp
`[access_class=...]` at emission time where the truth is known; older rows are classified
**on read**, because convention 24 makes `Attempts` append-only and rewriting 117 rows would
edit immutable history to add a distinction that was always true of them. That also keeps
the classification as reviewable, testable code rather than a one-time edit nobody can
re-derive. **Flagged as a deliberate reading of the brief's "reclassify" — see §7.**

A bare **403 is deliberately not a signature**: an edge rate limiter and a policy refusal
both return it, which is the entire reason this split exists. A word-bounded **429 is**,
because it has exactly one meaning. Unclassifiable rows are reported — defaulting them into
`source_refusal` would inflate the one count meant to be a citable claim about a source.

---

## 3. Task 3 — H-JOBPOST-01 across the full universe

**HR-0032 / 0033 / 0035, v1.0 → v1.1. 107 companies, 21 observations, 214 attempts per run.
Quarantined.** Three runs because two defects were found by reading output between them; the
second and third reconciled rather than rewrote.

### 3a. The source legs — Indeed is closed too

The brief asked me to probe Indeed honestly rather than assume, and the answer is worse than
"unverified": **Indeed disallows `/jobs` and `/viewjob?` as well as the `/cmp/` path already
known to refuse us.** With LinkedIn at `Disallow: /`, the entire third-party job-board layer
is closed to compliant collection.

So own-domain careers pages are not merely the primary leg — they are **the only open one**,
and that is a permanent bound on this instrument rather than a tonight problem. Recorded as
the sources' own decisions (convention 38) against a declared signal, so the finding has a
denominator: 107 companies, 0% coverage, not improvable by us.

New `SRC-0049` for the own-domain leg. `SRC-0010` keeps its id and name and is narrowed in
the manifest to the Indeed leg — convention 22 forbids renaming a registered value.

**Per-leg coverage is reported and the blended rate is explicitly refused.** The legs have
different *ceilings*: the own-domain leg improves by building adapters, the board leg cannot
improve at all. A mean over them drifts toward 50% as the open leg improves and describes
neither.

| Leg | Covered | Rate |
|---|---|---|
| `job_posting` (own domain) | 14 / 107 | 13.1% |
| `job_board_third_party` | 0 / 107 | 0.0% — closed by source policy |

### 3b. Discovery works; the ATS is the wall

Discovery finds a careers page **on the company's own registrable domain for roughly 85% of
the universe**. v1.0's run on 2026-08-30 reported "no source configured" 104 times; that is
now a specific, named gap in nearly every case.

**What it usually cannot find is an ATS in the server-rendered HTML.** That is the binding
constraint, and it is neither access nor precision. The named gaps are now a **build order
derived from data rather than guessed**: `ultipro`, `adp`, `dayforce`, `smartrecruiters`,
`jobvite`, `brassring`, `bamboohr`, `tenstreet`.

Discovery refuses a third-party board as a careers page, and that is a rule rather than a
default: `source_grade = A` on this harness means "attributable to the company's own careers
page", so accepting an aggregator would misgrade every row it produced — the
H-SELLERCONTENT-01 homepage-substitute failure exactly.

### 3c. The classifier, and what a loose term costs at 108 companies

Probing v1.0's terms found **seven false positives**, every one convention 16/31 — a single
common token standing in for an identification:

| Title | v1.0 read it as |
|---|---|
| `BI-Weekly Payroll Clerk` | data / AI (`\bBI\b` matches inside `BI-Weekly`) |
| `API Technician - Active Pharmaceutical Ingredients` | systems integration |
| `Ai Weiwei Gallery Assistant` | data / AI |
| `Lean Beef Processing Associate` | digital transformation |
| `Oracle Card Dealer` | ERP |
| `Innovation Center Tour Guide` | digital transformation |
| `Transformation Coach - Wellness` | digital transformation |

"bi-weekly" and pharmaceutical API are not exotic, and **food distribution and medical
devices are both real industries in this universe.** Three rules now govern every term:
acronyms match **case-sensitively**, an ordinary English word needs a **qualifier**, and a
term can be **vetoed by context**. Convention 32 sets the shape — admission threshold, not a
downgrade to `weak_clue`.

**The mandatory Kenco regression passed, and `reprocessing_required: false` was checked
rather than assumed.** Classifier v1.0 and v1.1 were run against the identical 2026-08-24
archived Kenco bytes: **6 signal instances each, same signals, same titles.** No v1.0 row
would be classified differently, so no delete-and-rewrite was needed. The Infor case still
resolves correctly.

### 3d. The pilot verdict — it found a defect, which is why it exists

15 companies spanning the mix, deliberately front-loaded with the ones most likely to break
it (Prime Inc., Leprino, SpartanNash, Merit Medical, Kenco as the regression anchor).
**Two defects, both fixed, then re-piloted before proceeding:**

1. **Merit Medical's "Process Engineer" read as modernization evidence.** The cause is
   precise: `core/topics.py`'s `digital_transformation_process` theme lists process
   *improvement / excellence / reengineering / automation* — each naming a change
   **programme** — and pointedly omits the bare engineering title, which v1.0 had added. A
   process engineer at a device manufacturer is an ordinary production role, and in a
   universe of manufacturers and contractors that term fires nearly everywhere.
2. **Prime Inc.'s iCIMS adapter 404ed against `login.icims.com`** — discovery captured
   iCIMS's shared auth host as the company's tenant. **My first fix was itself wrong**: a
   bare negative lookahead shifts one character and matches `ogin.icims.com`. Caught by
   testing it rather than by shipping it.

**Verdict: precision acceptable, coverage the constraint.** Re-piloted clean, then proceeded.

### 3e. The result, and the yield finding at scale

**11 signal instances across 1,662 postings read from 16 companies — 0.66%**, against
Kenco's 5-of-467 (1.07%) from the pilot era. The manifest's claim that *"extraction quality
matters more here than source coverage"* is now measured over 15× the population rather than
one company. All 11 read as genuine.

Review sheet emitted: `H-JOBPOST-01__v1.1__review.md`, a **21-of-21 census control**.

**The `legacy_constraint` stratum the brief asked to have called out is empty, and the
premise behind it does not hold.** This harness writes **zero** `legacy_constraint` rows —
convention 2 maps all hiring to `active_transition`. Of the 56 `legacy_constraint` rows in
the evidence base, **54 are H-SAFETY-ENV-01** and 2 are H-FMCSA-01. Family 4 being dark does
*not* make H-JOBPOST-01 the primary reachable instrument for that state; OSHA/EPA is.

There is a real design question underneath, **flagged not decided**: the
`integration_engineering_hiring` signal's own rationale says integration roles indicate
"systems that do not yet talk to each other — a legacy-estate signal as much as a
modernization one". If that is right, it maps to `legacy_constraint`, not
`active_transition`. That changes the shape of the evidence base and is decided on
principle, not by looking at tonight's rows.

### Two more defects, both found by reading output

1. **The audit sampler's `off_own_domain` stratum was `lambda r: True`**, commented "every
   row in this harness is third-party by construction" — true of the two harnesses it was
   written for, false the moment it met a first-party one. It selected **21 of 21**
   H-JOBPOST-01 rows into a stratum labelled "not the company's own domain", when every one
   cites the company's own careers page. That is session 4's tabular detector firing on 28 of
   28, **inside the gate's own sampler**. A `selection_rule` is a claim the artifact records
   for someone to re-execute, so a rule that cannot be false is worse than a missing stratum.
   Now a real domain comparison; the convention 37 check confirms H-EXECVOICE-01 8/8 and
   H-TRADEPRESS-01 1/1 unchanged, so the released artifacts stay accurate.
2. **Zero postings was being written as `absent_confirmed`.** IPS's iCIMS portal answers with
   a 175-byte JavaScript redirect; McShane's Paylocity page is 79KB with zero job links. Both
   parse to 0 postings, and both would have claimed the company is not hiring — false
   *negative* evidence, convention 6a, the Mack Molding and Scentsy failure in a third
   instrument. Caught mid-run; **the run was killed and restarted, so nothing false ever
   reached the workbook.**

---

## 4. Task 4 — H-FMCSA-01 backfill

**HR-0034, v1.3, no version bump.** 107 companies, **8 resolve to a carrier**, 30
observations proposed, **4 written, 20 held for review.**

The 20 held are the never-overwrite rule working exactly as designed (conventions 1 and 35):
SAFER's snapshot has advanced since the Week-1 review, so content changed on rows Matthew has
already `accepted` or `corrected`, and they are reported as conflicts rather than silently
refreshed. **Those 20 are a decision for you** — convention 2 says drift is corrected by
re-running, never by hand-editing, so the question is whether to accept the refresh.

**A latent defect this run would have hit.** `HARNESS_RUN_COLUMNS` is the 11-column pre-gate
contract, so `HarnessRun.as_row()` stops short of `publication_status` and
`append_harness_run` left the cell **blank** — which check 9 rejects outright. Every harness
still on that path would have written an invalid run row the moment it ran; the gate was
built around the run context and this path was never brought with it. Now defaults to
`quarantined`, the same fail-safe reasoning as `Observation.publication_state`.

**A gate hole worth a decision.** Grandfathering is keyed on `(harness_id, version)` and is
permanent for that pair, but *output volume is a property of the run*. H-FMCSA-01 v1.3 was
grandfathered against a 7-company pilot; running it against 107 produces new unaudited output
at 13× the population under the same exemption. I defaulted HR-0034 to `quarantined` rather
than letting it publish. **The exemption arguably needs a population bound, or grandfathering
should expire on re-run.**

---

## 5. Task 5 — signal types registered

`ST-JOBSYSTEM` (`job_posting_system_mention`, family **5**, IC3) and `ST-JOBBOARD3P`
(`job_board_third_party`, family 3, IC3). Both **IC3 `revealed_behavior`** — the taxonomy
names job postings as the example of that class.

Family 5 for the first is deliberate and follows `signal_taxonomy.md` §5's *"merge into 3a,
don't build new"*: registering the signal type separately is what lets a family-5 claim be
counted **without** implying a family-5 harness exists. `ST-JOBBOARD3P` is registered
`evidence`/IC3 because that is what the instrument **would** be if it were reachable — the
class describes the instrument, not our access to it — and registered at all so the refusal
has a denominator rather than being a silence.

`ST-LINKEDINPOST`, `ST-DOCKET` and `ST-NLRB` were already registered in session 4.
**24 signal types now.**

---

## 6. Evidence base after this session

| | |
|---|---|
| Observations | **337** (204 `buyer_acts` / 90 `buyer_articulates` / 43 `provider_market_responds`) |
| Publication state | **311 released, 26 quarantined** |
| Attempts | **3,443** |
| Harness runs | **35** |
| Companies with evidence | **108** |
| Human-reviewed | 39 |
| Signal types | 24 |

**Row deltas this session, all quarantined:** H-JOBPOST-01 v1.1 **+21** (net +13 new, 8
pre-existing v1.0 rows refreshed to v1.1), H-FMCSA-01 v1.3 **+4**. Nothing else written.

---

## 7. Where the brief was ambiguous or wrong, and what I chose

1. **"Write the audit artifacts for all five versions"** — not executable. Two versions had
   verdicts; one of the other three *cannot* have a review sheet at all. Released two,
   quarantined three, manufactured nothing. **The single most reviewable call of the
   session.**
2. **"Reclassify the existing rows"** (Task 2) — read as *classify on read*, not *rewrite in
   place*. Convention 24 makes `Attempts` append-only, and editing 117 rows to add a
   distinction that was always true of them is the history-rewrite that convention forbids.
   Deriving it keeps the classification as reviewable, testable code. **Overrule me cheaply
   if you wanted the backfill.**
3. **The brief's Task 2 expectations did not match the data** — no 39 robots-blocked rows, no
   trade-press 403s, and the rate limits live under `source_unavailable` rather than
   `access_blocked`. Reported rather than forced to fit.
4. **The `legacy_constraint` premise in Task 3e is wrong** — this harness writes none, and
   OSHA/EPA is the primary instrument for that state. Flagged the design question about
   `integration_engineering_hiring` rather than changing the mapping mid-run.
5. **`superseded` rather than a corrected trigger** (Task 1) — check 9 was correctly scoped
   and never fired, so the fix the brief's first branch anticipated would have been a change
   to a check that was working.
6. **HR-0034 quarantined** despite v1.3 being grandfathered, because a grandfathered version
   re-run at 13× its original population is new unaudited output.
7. **Three H-JOBPOST-01 runs rather than one.** Each fix was applied and the harness re-run
   rather than the output patched. The second and third reconciled (1 row and 0 rows
   changed), which is convention 8 working.

---

## 8. Open items by owner

**For you:**
- **Three versions await audit:** H-JOBPOST-01 v1.1 (21 rows, census sheet ready — the one
  worth reading), H-LEGAL-01 v1.1 (1 row), H-PRODUCTQUALITY-01 v1.2 (0 rows, no sheet
  possible — needs a disposition, possibly `superseded` once a v1.3 exists).
- **The 20 held H-FMCSA-01 conflicts** — accept the SAFER refresh, or keep the reviewed rows.
- **The 0.10 random-control threshold is still provisional.** Both audits cleared it at 0%,
  so nothing published depends on it yet — but H-JOBPOST-01 v1.1 is the first version whose
  audit could plausibly land near it.
- **Should grandfathering expire on re-run, or carry a population bound?** (§4)
- **`observation_id` renumbering on delete-and-rewrite** — carried from session 4, still
  undecided, and now more urgent: 21 job-post rows are about to enter a review cycle.
- Minor: **HR-0032 records `observations_produced_count = 0` when it wrote 13.** The run
  context initialises the field to 0 and the harness must set it; mine did not until HR-0035.
  The evidence base is correct; the run row understates. I did not hand-edit a committed run
  row to fix it.

**For Harness Advisor:**
- **The ATS build order, now data-derived:** ultipro, adp, dayforce, smartrecruiters, jobvite,
  brassring, bamboohr, tenstreet. Each is several companies.
- **Client-side-rendered careers pages are the single biggest coverage limit in the
  portfolio** — the Midmark/Duke problem turns out to be the *general* case, not two awkward
  companies.
- Does `integration_engineering_hiring` map to `legacy_constraint`? (§3e)
- Unchanged: NLRB case documents, Duke Manufacturing, H-LEGAL-01's age window, the
  off-allowlist first-party and vendor URLs.

**For Signal Advisor:**
- `ST-JOBSYSTEM` IC3 family 5 and `ST-JOBBOARD3P` IC3 family 3 — confirm, and confirm that
  registering a signal type whose instrument is entirely closed is the right call (the
  `ST-NLRB` precedent, for a different reason).
- Carried: `ST-LINKEDINPOST` IC1, `removed_page` IC3 vs IC4, `ST-EXECCOLUMN`'s grade, the
  taxonomy patch merge.

---

## 9. What this session adds to the failure-mode record

Convention 16 stood at 24 instances and convention 36 at 5. This session adds **eight**, every
one found by reading output or by checking that a change changed something — **none by a
test**:

1. `load_artifacts()` reading the sampler's `__strata.json` sidecars as audit verdicts —
   **inside the gate's own machinery** (36).
2. The `off_own_domain` stratum hardcoded to `lambda r: True`, selecting 21 of 21 (36).
3. `\bBI\b` matching inside `BI-Weekly` (16/31).
4. `API` as Active Pharmaceutical Ingredient (16/31).
5. Case-insensitive `\bAI\b` matching the name "Ai" (16/31).
6. `Process Engineer` classified against a theme spine that deliberately excludes it (16).
7. `login.icims.com` captured as a company's ATS tenant — **and the first fix was wrong**,
   because a bare negative lookahead shifts one character (16).
8. Zero parsed postings written as `absent_confirmed` (6a).

**Two structural findings rather than bugs.** `append_harness_run` left `publication_status`
blank, so every pre-gate harness would write a run row that fails validation — the gate was
built around the run context and this path was never brought with it. And
`assert_validations.py` checked that a dropdown was *bound* but never that the column held
what the repo *declares*, so the declared vocabulary was decorative; it found a second
instance immediately.

**The pattern across this session and the last two:** the characteristic failure is no longer
only "a loose pattern manufactures confidence in a claim". It is increasingly **a control
that answers confidently about the wrong thing** — and three of tonight's eight are in the
checking apparatus itself, not in a harness. The audit gate found defects in a harness
tonight, and the harness run found two defects in the audit gate.

---
---

# Session 5 addendum — 2026-09-01, after Matthew's instruction

> *"Release execvoice and trade press today. Also double check it's running job posting and
> fmsca across all 108"*

## A1. The release — already done, and re-verified

Both versions were released earlier in the session (commit `73b6c24`). Re-verified after the
instruction rather than asserted from memory:

| Version | Run | Run status | Rows | Artifact |
|---|---|---|---|---|
| H-EXECVOICE-01 v1.2 | HR-0029 | `published` | 8 `released` | verdict `pass`, census 8/8, threshold 0.10 |
| H-TRADEPRESS-01 v1.2 | HR-0030 | `published` | 1 `released` | verdict `pass`, census 1/1, threshold 0.10 |

**Gate re-verified in both directions, per convention 40.** With each artifact present check 9
exits 0; with either removed it exits 1 naming that version; restored, 0 again. Tested
independently for both artifacts, not once for the pair.

Unchanged: H-PRODUCTQUALITY-01 v1.2 and H-LEGAL-01 v1.1 remain quarantined (no sheets, no
verdicts). H-TRADEPRESS-01 v1.1 remains `superseded`.

## A2. The scope check — it was 107, and the check was worth making

**Both runs were at 107, not 108.** Reported from the run records, not from intent:

| Run | Harness | Companies attempted | Source of the count |
|---|---|---|---|
| HR-0035 | H-JOBPOST-01 v1.1 | 107 | Attempts ledger, distinct `company_id` |
| HR-0034 | H-FMCSA-01 v1.3 | 107 | run row + resolution log |

The missing company was **C0008 CT Logistics**, whose `qualification_status` was `excluded`.
H-JOBPOST-01 and H-FMCSA-01 filter on `qualified / pending_review / soft_gate_exception`;
that filter is the whole reason.

### The inconsistency was portfolio-wide

| Universe attempted | Harnesses |
|---|---|
| **108** (C0008 included) | H-EXECID-01, H-EXECVOICE-01, H-FIRSTPARTY-01, H-PRODUCTQUALITY-01, H-LEGAL-01, H-EMPREVIEW-01 |
| **107** (C0008 excluded) | H-JOBPOST-01, H-FMCSA-01, H-SAFETY-ENV-01, H-WAYBACK-01 |

Six harnesses call `db.companies()` unfiltered; four filter on status. **Coverage denominators
differed between harnesses for a reason having nothing to do with the instrument** — which is
precisely the kind of thing that makes a cross-harness comparison meaningless.

Two things marked `excluded` as the stale value rather than the correct one: C0008 holds
**2 released observations** (H-FIRSTPARTY-01 v1.1), and it is **convention 6's founding
confirmed-absence case** — *"a freight-audit firm operates no fleet, so H-FMCSA-01's true
resolution result is 8/8, not 7/8."*

### Resolved: restored to the universe

Matthew's call. `C0008` set `excluded` → `qualified` through a new
`core/db.py::set_qualification_status`, with the reason stamped on the row. This is a decision
about the *universe* and the single input every coverage denominator derives from, so it goes
through the same writer as everything else (convention 28) rather than being poked into the
sheet — which is what `h_execid_01` does today for `website`, and a thing worth fixing later.

**No harness code changed.** With nothing excluded, both filters return 108 and the portfolio
converges on its own. The latent divergence remains and is now recorded in `CLAUDE.md`: the two
groups agree only because nothing is excluded today, and the *stricter* filter is the more
correct one — the six unfiltered harnesses would happily attempt a genuinely excluded company.

### Confirmed at 108

| Run | Harness | `companies_processed_count` | Attempts ledger |
|---|---|---|---|
| **HR-0036** | H-JOBPOST-01 v1.1 | **108** | **108** distinct companies, 216 rows |
| **HR-0037** | H-FMCSA-01 v1.3 | **108** | n/a — pre-gate path writes no Attempts rows |

Both re-runs were fully idempotent: **0 rows written** by either. 21 job-post observations
unchanged, and H-FMCSA-01 again held its 20 human-reviewed rows as conflicts rather than
overwriting them.

## A3. Two things the restoration surfaced

**1. Convention 6's 8/8 does not reproduce, and C0008 is why.** Restoring it to the universe
does *not* restore the founding example. Today H-FMCSA-01 records CT Logistics as
**unresolved — 72 candidates seen, none cleared the acceptance threshold**, which is an
entity-resolution *refusal*, not `absent_confirmed`. Those are materially different claims: a
refusal says "we could not identify it", a confirmed absence says "it genuinely has none", and
only the second is coverage.

The search terms are `["CT LOGISTICS", "CT"]`, and **`CT` is exactly the shape convention 13
forbids** — the bare token that turned `PLS` into "Pls Drywall And Ceilings Inc." The threshold
correctly refuses all 72, so nothing false was written; but it means the 8/8 in
`docs/conventions.md` rests on behaviour the harness no longer exhibits. **Worth a decision:
is CT Logistics' FMCSA absence `absent_confirmed` or `entity_below_threshold`?** That is a
claim about the source, not a threshold to tune, and I did not change it.

**2. H-FMCSA-01 still has no attempts ledger.** Its 108 is readable from the run row and its
resolution log, but not from `Attempts`, because the harness predates `core/attempts.py`. So
its coverage rate remains uncomputable and `published_coverage.py` still shows `n/a` for it.
Migrating it is the same one-session job that H-JOBPOST-01 had tonight.

## A4. Evidence base after the addendum

Unchanged in substance — both re-runs wrote zero rows.

| | |
|---|---|
| Observations | **337** (311 released, 26 quarantined) |
| Attempts | **3,659** (+216, the HR-0036 re-run) |
| Harness runs | **37** |
| Buyer universe | **108**, and every harness now iterates all of it |

All checks green: `check_run_ledger --strict`, `validate_repo_db` 9 checks,
`assert_validations` 24 bindings, all ten test suites.
