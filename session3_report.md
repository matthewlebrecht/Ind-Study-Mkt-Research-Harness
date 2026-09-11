# Session 3 report — 2026-08-31 (unattended, overnight)

**Read this first:** one input file the brief names was missing, and three of the nine
tasks were not reached. Details in §0 and §9.

Per the brief, this report states **deltas from tonight's runs only**. No absolute
evidence-base totals appear anywhere in it; those get recomputed after the audits.

---

## 0. The missing input, and why the session ran anyway

`harness_advisor_response_audit_gate_2026-08-31.md` — the "full spec" for Task 1 — **is not
on disk.** What is on disk is `harness_advisor_brief_audit_gate_2026-08-31.md`, which is the
*outgoing* document: the five questions you sent Harness Advisor, not the answers.

I did not abort, and here is the reasoning, so you can disagree with it cheaply. The
session-3 brief's own "Summary of what to build" **resolves every one of the five open
questions**, and resolves several of them *against* the proposals in the outgoing brief —
no `pending_audit` value, no `records_quarantined` counter, check 9 rather than 7, an
explicit registry instead of date scoping, `reprocessing_required` derived rather than
gate-authored. A summary that reverses its own source document is a decision record, not a
paraphrase. Nothing about Task 1 required guessing at an architecture call.

One thing the summary genuinely does not contain: **the random-control exclusion
threshold.** The outgoing brief says "the threshold value itself I'll set." I set it to
**0.10** as a placeholder, chose it conservatively (a tighter threshold quarantines sooner),
and flagged it in three places: `core/audit.py::RANDOM_CONTROL_EXCLUSION_THRESHOLD`, every
artifact's `threshold_applied`, and here. **Nothing published tonight depends on it** —
everything is quarantined — so correcting it changes no reported figure.

**Open item:** either the response doc did not make it into the repo, or it was never
written. If it exists, it should be diffed against what I built.

### Step 0 hard aborts — all passed

| Check | Result |
|---|---|
| Workbook content assertions | 315 obs (185/87/43), 107 companies with evidence, 1,646 attempts, 19 runs, 814 execs, 27 reviewed — all match `CLAUDE.md` exactly |
| `git status` clean | No modified tracked files. Three untracked session-3 input docs plus `.claude/`, which are the session's inputs, not uncommitted session-2 work |
| No run with a null end timestamp | **Not evaluable as written** — `Harness_Runs` has no end-timestamp column, only `date_run`. There is no "run in progress" concept in the schema, so the condition the check exists to catch cannot obtain. Logged rather than silently passed |
| `validate_repo_db.py` | Passed, 8 checks |

---

## 1. Audit gate — built (Task 1)

**Schema.** `Observations` gained `publication_state`, `audit_verdict`, `review_source`.
`Harness_Runs` gained `publication_status`, `records_excluded_by_audit`. Four new Lookups
vocabularies. Backfill: 315 rows → `released`, 27 → `review_source = human`, 288 →
`machine`, 19 pre-gate runs → `published`.

Deliberately **not** built, per the brief: `pending_audit` as a `review_status` value, and a
`records_quarantined` counter. Exclusion is a filter at the rollup layer; a quarantined run
contributes neither numerator nor denominator, and its `Attempts` rows are excluded by join
on `run_id`.

**The never-overwrite rule now keys on provenance** — and this is the one place I
deliberately did *not* follow the brief exactly. The brief says "a re-run may overwrite any
row whose `review_source` is `machine` or empty." Taken literally, a reviewer who marks a
row `accepted` by hand in Excel and does not also change `review_source` leaves it reading
`machine`, and their review is silently overwritten on the next run — a data-loss path
straight through convention 1. I implemented protection as the **union** of the two signals:
`review_source = human` **or** a reviewed `review_status`. No harness ever writes a reviewed
status, so one appearing can only have come from a person. This protects a strict superset
of what the brief asked for and costs the gate nothing, because the audit writes
`audit_verdict`, not `review_status`. **Conservative deviation, flagged for your review.**

**Validation read-back.** `scripts/assert_validations.py` reopens the saved file from disk
and asserts all 24 bindings (18 existing + 4 gate + 2 taxonomy). It checks three things per
binding, not one: that a validation exists, that its `sqref` is exactly right, and that the
Lookups column it points at **actually holds values** — a range bound to an empty column is
a dropdown with no options, which a "did we set it" test cannot detect. All 24 present and
correctly bound in the reopened file.

> **Count discrepancy:** the brief says "five new validated columns are being added." I count
> four (`publication_state`, `audit_verdict`, `review_source`, `publication_status`);
> `records_excluded_by_audit` is an integer, not a controlled vocabulary. I did not invent a
> fifth. Two *further* validations were added under Task 2 (`Signal_Types.status` and
> `.instrument_class`), bringing the total to 24.

**Check 9, not 7.** Current inventory printed and confirmed before touching anything: the
validator ran **8** checks. Nothing renumbered or replaced.

**Grandfather registry:** `docs/gates/grandfathered_harness_versions.json`, 18 explicit
`(harness_id, harness_version)` pairs across 9 harnesses, each with a reason and date. No
date scoping — a date boundary is something a harness can land on, which is exactly what
H-EMPREVIEW-01 was doing.

**`reprocessing_required` is derived on read, never stored,** so it cannot go stale.

**Gate doc:** `docs/gates/gate_new_harness_output.md`. `CLAUDE.md` holds only the trigger.
The suppression stratum you flagged is in — sampled from `Attempts`, and the only stratum
that can fail a harness for *over*-suppression.

**Two bugs the gate's own tests caught in the gate:**
1. The provenance rewrite broke the previously-working hand-edited-review case (§ above).
2. `core/audit.py` bound `AUDIT_DIR` as a **default argument**, so redirecting the directory
   read the real one and reported a clean result about a location nothing had been written
   to. A stale answer with a confident name.

46 checks in `core/tests/test_audit_gate.py`, including the negative cases — a published
pair with no artifact, an artifact missing required fields, an artifact whose own verdict is
`fail`. **A check only ever observed passing is indistinguishable from one that returns
True**, so all three were built and verified to fail.

## 2. Signal_Types registry — built (Task 2)

`signal_class` **not redefined**. The instrument-bias axis is a separate column,
`instrument_class`, IC1–IC4, on `Signal_Types` only — not on `Observations`, since it is a
property of the instrument, not of any claim.

8 new types seeded (5 trade press, 3 vendor). `ST-WIREREPRINT` registered `routing_only`
against **family 1**, not 15: a wire reprint is a press release wearing a trade masthead.
All 10 pre-existing types backfilled.

**Check 5 now rejects a blank `instrument_class`** — a blank reads downstream as "unbiased",
which is true of nothing here, and would let an IC1 silence (which per §4.6.1 licenses no
inference at all) be quoted as a finding. Verified it actually fails by blanking a row.

**Two backfills are judgment calls, flagged rather than presented as settled:**
- `removed_page` → **IC3**. The observable is the *act of removal*, which is revealed
  behaviour. The counter-argument for IC4: a company removes a page precisely to un-publish
  it, so the archive discloses over its preference. **Signal Advisor's call.**
- `executive_identification` → **IC1**. A prerequisite, but the class does real work: a
  curated leadership page means the 47 companies with no identified exec license *no*
  inference that they have none.

**The taxonomy patch is NOT merged into `docs/signal_taxonomy.md`.** Its own header says
"renumber on merge", and a bad renumbering breaks every cross-reference in the repo at once.
That is an attended editorial decision. A pointer was added so the taxonomy is not silently
stale. The registry side of the patch (§4.6, §7) *is* applied.

## 3. H-EMPREVIEW-01 access pass — done (Task 3)

**HR-0020: 108 attempt rows. 107 `access_blocked` / `source_limitation`, 1
`absent_confirmed`.** Quarantined; contributes no coverage number.

Every `failure_detail` carries the citable reason, measured live at run time rather than
asserted from the manifest. No user-agent switched, no authenticated access attempted.

Comparably served **Midmark live** — 9 reviews, no modernization theme. That is the
harness's first `absent_confirmed` from a live fetch and the first time its extraction path
has run end-to-end outside a fixture, which closes part of v1.0's stated "not field
validated" gap. It then rate-limited exactly as documented; the circuit breaker stopped the
run rather than walking the remaining 100 companies into a wall.

## 4. H-TRADEPRESS-01 v1.0 — built, subset run (Task 4)

**HR-0021: 15 companies, ~130 articles read, 2 rows admitted.** Both
`ST-EXECQUOTE-REPORTED`, family 15, grade B, `buyer_articulates`. Quarantined. **No coverage
percentage is reported.**

The run refused 46 articles as stale, 28 as not about the company, 7 below the admission
threshold (single generic term — convention 32 working), and 39 URLs on robots.txt grounds.

Two of the 15 companies were chosen **adversarially**: Prime Inc. (single common token —
four wrong-company rows in H-FIRSTPARTY-01 v1.0) and McGough Construction (eponymous
surname — a misattributed quote in H-EXECVOICE-01 v1.0). Neither guard regressed.

Extraction is genuinely per-claim, not per-document. Trade press names its sources, so
speakers are read from the article itself, and Q&A transcripts — which carry no quotation
marks at all — are admitted via their all-caps speaker labels, but only for a speaker the
article has already identified as an officer of that company.

**Six defects found by reading output, not by tests** — see the commit message for the full
list. The two worth repeating here:
- Merit Medical produced 10 rows off 5 acquisition and recall stories, and every article
  yielded the *identical* two topics. The uniformity was the tell: the themes came from
  MedTech Dive's own section navigation, not from any article. All 10 were false.
- I ran the *buyer-voice* classifier on journalist prose, so every `ST-PRESSPROFILE` row
  silently failed to exist. The summary line said "nothing admissible", which is
  indistinguishable from the outlets having had nothing.

**And two regressions my own fixes caused**, both caught the same way: switching discovery
to `site:` queries starved the general query and dropped Gilbane from 3 rows to 0; and the
furniture filter that killed the MedTech Dive navigation also deleted the Gilbane interview,
whose Q&A speaker labels are 15-character blocks.

## 5. H-PRODUCTQUALITY-01 v1.1 — built, full universe (Task 6)

Built ahead of Tasks 5 and 7 because it is **IC4** and the only remaining route to
`legacy_constraint`.

**HR-0025: 108 companies scoped, 16 inside the instrument's population, 1 observation** —
Merit Medical, three labelling-control recalls 2016–2018, `legacy_constraint`,
`repeated_pattern`. Quarantined.

**The row-by-row audit paid for itself immediately.** v1.0 produced two rows and one was
wrong: a MAUDE narrative in which Midmark's ECG software *correctly* detected a myocardial
infarction, scored as a systems failure on the bare token "SOFTWARE", written as a
`legacy_constraint` row asserting the opposite of what the record says. v1.1 requires the
cue and a failure predicate to share a **sentence**.

That is a **version bump with `reprocessing_required`**, not an edit to v1.0. The stale row
needed an **explicit delete**: `sync_observations` does not remove a row a fixed harness has
stopped proposing, so a defect that *removes* rows survives its own fix silently otherwise.
Worth knowing generally.

**The most important thing this harness found is not an observation.** CPSC's
saferproducts.gov answers `CompanyName`, `ProductName` and `RecallDescription` queries with
an **error record dressed as an HTTP 200 result** — `Title: "Error retrieving Recalls: The
underlying provider failed on Open."` The first run recorded 4LIFE and Scentsy as
`absent_confirmed` off those. That is false absence evidence — convention 6a — and it is the
OSHA failure in a new database. Now detected and raised as a fetch failure; the query moved
to `RecallTitle`, which works.

Also fixed: the response-cache key now carries a fingerprint of the request URL. Without it,
fixing the broken CPSC query **had no effect**, because the harness replayed the broken
query's answer from the same day's cache partition. A cache key that does not change when
the request changes is not a cache.

---

## 6. Row deltas, tonight only

| Run | Harness | Version | Observations | Attempts | Publication |
|---|---|---|---|---|---|
| HR-0020 | H-EMPREVIEW-01 | v1.0 | 0 | 108 | quarantined |
| HR-0021 | H-TRADEPRESS-01 | v1.0 | 2 | 15 | quarantined |
| HR-0022–25 | H-PRODUCTQUALITY-01 | v1.0 → v1.1 | 1 (net, after the v1.0 delete) | 108/run | quarantined |

**3 observations written tonight, all quarantined.** 2 `buyer_articulates`, 1 `buyer_acts`.
No coverage number is claimed for any of them.

Every observation in the workbook now carries a `publication_state`: **315 released**
(pre-gate, grandfathered) and **3 quarantined** (tonight's). 27 rows are `review_source =
human`; the rest are `machine`.

## 7. Review sheets awaiting you

Both are the **random control** only, laid out one row per line with claim, evidence,
source URL, matched term, the machine's verdict and its confidence. The adversarial strata
are in the `__strata.json` files beside them and were judged mechanically.

- `harness_output/audits/H-TRADEPRESS-01__review.md` — **2 rows** (the whole population)
- `harness_output/audits/H-PRODUCTQUALITY-01__review.md` — **1 row** (the whole population)

**Added 2026-09-01, at Matthew's request** — the two sheets that cover what did *not*
become evidence, which every stratum but the suppression one is blind to:

- `harness_output/audits/H-TRADEPRESS-01__declined.md` — all **130** fetched-and-refused
  articles, split into **81 evidentiary** refusals (stale / not-about-company /
  below-admission — the harness read the article and judged it, so these are the ones you
  might overturn) and **49 mechanical** (403s, index pages). Plus a summary of the 286 URLs
  that never reached a fetch, including the robots-blocked hosts.
- `harness_output/audits/H-PRODUCTQUALITY-01__population.md` — the **92** companies never
  queried, split by whether another harness has already found family-9 records for them:
  **71 with** OSHA/EPA evidence (read first — a firm with industrial facilities is the kind
  that can hold an FDA registration) and **21 without**.

Both generated by `scripts/emit_audit_context.py` from the committed run logs, so they
cannot drift from what the runs did.

**One thing the declined sheet already surfaces:** several Rycon Construction refusals are
ENR industry-ranking articles rejected as `not_about_company` because the token RYCON is
absent from the first 2,500 characters. A rankings piece may well name the firm further
down. That is a plausible false refusal and the identity window may be too tight for that
article shape — worth your judgment, and exactly the class of error the review sheets
cannot see.

Far short of the ~30 the brief asks for, because 3 rows is the entire night's output. The
sampler (`scripts/audit_sample.py`) draws 30 when there are 30. **Neither artifact has been
written**, so both runs remain quarantined and check 9 is not triggered — writing an
artifact requires your verdicts, and a precision rate a harness computed about itself is not
a measurement.

## 7a. Verdicts recorded 2026-09-01

Matthew judged all three rows. **Both runs pass the stop rule and are released from
quarantine.** `validate_repo_db.py` check 9 now reports 19 published harness versions —
2 audited, 17 grandfathered.

| Row | Company | Verdict | Action |
|---|---|---|---|
| O00364 | Gilbane | `supported` | none; reviewer confidence 0.99 |
| O00365 | Penske Logistics | `supported` | none; reviewer confidence 0.99 |
| O00366 | Merit Medical | `overgraded` | **retained**, downgraded |

**H-TRADEPRESS-01 v1.0** — precision 2/2, exclusions 0. The control is a **census, not a
sample**: population 2, both judged, so the rate is exact for this run and carries no
useful confidence interval. It says this output is clean; it does not say the harness is
100% precise.

Reviewer confidence 0.99 is recorded in `reviewer_notes`, **not** written into
`confidence_0_1`. A reviewer's confidence in a verdict and a harness's confidence in a
claim are different quantities, and the whole point of `review_source` is keeping them
separable.

**H-PRODUCTQUALITY-01 v1.1** — the harness inferred a *process or systems failure* from a
labelling defect and asserted `legacy_constraint`, that a control did not hold. The recall
text does not establish that: missing labels may or may not be a procedure error. The row
is **retained** — three federal labelling recalls at one firm between 2016 and 2018 is a
real, checkable pattern, and convention 32's exclusion is for claims the evidence does not
support *at all*. What was unsupported is the cause attributed, not the pattern.

    organizational_state   legacy_constraint -> unknown
    signal_strength        repeated_pattern  -> weak_clue
    confidence_0_1         0.7 -> 0.5
    recall count, citations, family, role   unchanged

Precision reads 0/1. Exact, and close to meaningless as a rate on a population of one — it
means the single row was overstated in one respect and corrected, not that the harness is
0% precise. Exclusions are 0, at the floor rather than above the 10% threshold, so the stop
rule does not fire.

**Open, deliberately not fixed:** should a labelling cue alone ever justify
`legacy_constraint`? v1.1 already requires a failure predicate in the same sentence as the
cue — the fix that stopped the Midmark ECG false positive. The labelling family may need a
second condition: evidence that the labelling *control* failed, not that one label was
wrong. That is a v1.2 and a fresh audit; the artifact on disk covers v1.1 as run, and
changing the code under it would invalidate the audit that was just completed.

**New:** `core/db.py::apply_audit_verdict` is now the only path that writes `audit_verdict`
and `review_source = human`. It refuses `unsupported` / `wrong_entity` — those mean the row
should not exist at any strength, and deleting evidence is not a field update — and it
refuses an `overgraded` verdict that changes nothing, because that is a label with no
consequence.

## 8. Where the brief was ambiguous and I chose conservatively

1. **Missing spec file** (§0) — proceeded on the brief's summary; set the threshold to 0.10
   and flagged it.
2. **Never-overwrite rule** (§1) — protected a superset of what was specified.
3. **`suppressed_redundant` split** — the brief calls it "the existing `suppressed_redundant`
   outcome" and says the split "is not a `failure_category` value". On disk,
   `suppressed_redundant` **is** a `failure_category` value, and `attempt_outcome` is the
   coverage axis (`covered` / `absent_confirmed` / `partial` / `not_covered`) where
   suppression values would corrupt coverage math. I read the trailing clause as
   disambiguating the *gate's `unsupported` verdict* and added both new values to
   `failure_category`, keeping the old value present per convention 22. **Worth confirming.**
4. **`ST-PRESSPROFILE`'s evidence family** — patch §7 marks it "varies"; the registry's
   one-family-per-signal-type shape cannot express that. I pinned it to family 15 and
   narrowed the *harness* to match the registry rather than the reverse. Conservative (it
   admits less) but a real narrowing. **Open item for Harness Advisor.**
5. **Grade ladder** — "Full" maps to B and "capped −1" to C. A stays unreachable.
   `ST-EXECCOLUMN` is the arguable case: the executive authored it, which is the A criterion,
   but it passed through an outlet's editing, and grading it A would make it the first
   A-graded family-15 row in the project on the strength of an inference about an editorial
   process nobody checked. **Signal Advisor's call.**
6. **Tasks 5 and 7's access failures** — see §9. Deliberately **not** written to the
   database.

## 9. Not reached

**Tasks 5 (H-PROCUREMENT-01), 7 (H-PATENTS-01) and 8 (H-LEGAL-01) were not built.** Tasks
1–4 and 6 consumed the session; Task 4 in particular went through six defect-and-fix cycles,
each one found by reading rows.

I did probe all of their sources and made it reproducible —
`scripts/probe_sources.py`, output in `harness_output/_source_probes/`:

| Source | Outcome | Attribution |
|---|---|---|
| `api.usaspending.gov` | TLS: self-signed certificate in chain | **Probably LOCAL** |
| `api.sam.gov` | 404 on the v3 entity path | source |
| `search.patentsview.org` | DNS does not resolve | ambiguous |
| `api.patentsview.org` | HTTP 200 serving an HTML app shell | source — moved or key-gated |
| `courtlistener.com` | **OK** — 2.1M dockets, no token needed | source |
| `nlrb.gov` | **OK** | source |
| `api.fda.gov` | OK (control) | source |

**I deliberately did not write `access_blocked` attempts for USASpending or PatentsView.**
The H-EMPREVIEW-01 precedent applies when the refusal is *the source's own decision* —
Glassdoor publishes `Disallow: /`, and 107 attempt rows citing it are true statements about
the source. A TLS-interception error on one host, when every other HTTPS host in the run
verified fine, is far more likely to be this machine's network than anything USASpending
did. Writing 108 rows from it would put a false claim about a federal database into the
evidence base — the CPSC error-record mistake pointed the other way.

**Re-run the probe from a different network.** If USASpending still fails there, the failure
is the source's and a harness can record it honestly.

**H-LEGAL-01 is the cheapest remaining win** — CourtListener works with no token and returns
55 results for "Kenco Group" alone.

Also not done, all explicitly out of scope: gap report regeneration, `core/topics.py` edits,
re-audit of the 87 existing `buyer_articulates` rows, `DECISIONS.md` seeding,
H-PERMITS-01/H-LOCALRECORDS-01, and Task 9 (H-VENDOR-01, stretch).

## 10. Open items

**For you:**
- Confirm or correct the 0.10 random-control threshold (§0).
- Confirm the `failure_category` reading of the suppression split (§8.3).
- Judge the two review sheets (§7). Until you do, both runs stay quarantined — which is the
  gate working, not a blockage.
- Locate or re-request the audit-gate response doc (§0).

**For Harness Advisor:**
- `ST-PRESSPROFILE`'s "varies" evidence family versus the registry's fixed-family shape
  (§8.4).
- Whether the `H-TRADEPRESS-01` outlet allowlist should expand — 3 of 4 construction outlets
  (ENR, ForConstructionPros, ConstructionExec) answered 403 to unauthenticated fetches, and
  39 URLs were robots-blocked, concentrated on massdevice.com and
  medicaldesignandoutsourcing.com. Trade-press yield is bounded by access as much as by
  content.
- H-PRODUCTQUALITY-01's population map is hand-seeded and certainly incomplete.

**For Signal Advisor:**
- `removed_page` → IC3 vs IC4, and `executive_identification` → IC1 (§2).
- `ST-EXECCOLUMN`'s grade (§8.5).
- Merging and renumbering the taxonomy patch (§2).

**Repo hygiene:**
- `gap_report.py` still prints the pre-amendment framing for the two divergences. The
  taxonomy patch's AMENDMENT reclassifies both as **formally untested** rather than weak
  findings. Out of scope tonight, still outstanding.

---

## 11. What tonight adds to the failure-mode record

Convention 16 had been hit nine times. Tonight added **seven more**, every one found by
reading rows rather than by a test:

1. MedTech Dive's section navigation classified as Merit Medical's behaviour (10 false rows).
2. "SOFTWARE" in a narrative where the software worked, scored as a systems failure.
3. "Sponsored Content" from an ad slot routing real ENR reporting into first-party.
4. The buyer-voice classifier run on journalist prose, silently zeroing a whole signal type.
5. CPSC's error record read as confirmed absence.
6. A cache key that did not change when the query did.
7. `AUDIT_DIR` bound as a default argument, so a redirected audit directory reported a clean
   result about a location nothing was written to.

Three of those (**1, 3, 5**) are the *same* shape as a defect already in the conventions
list, in a database or a content type where nobody had looked yet. Two (**6, 7**) are a new
sibling: **a lookup that silently answers about the wrong thing** — a stale cache partition,
a frozen default path. Both reported success confidently.

And twice tonight, a fix broke a case that had been working: `site:` discovery starving the
general query, and the furniture filter deleting the Q&A labels. That is now the third and
fourth instance of the pattern the brief warned about. It deserves to be stated as strongly
as convention 33 itself: **a fix is not verified until it has been run against the case that
was already working.**
