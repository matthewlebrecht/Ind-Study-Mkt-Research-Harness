# DECISIONS

Append-only record of the decisions that shaped this project, with the reasoning and the
consequence. **This file is history; it is never rewritten.** When a decision is superseded, the
superseding entry is appended and the original is left standing with a pointer.

Three documents divide the work between them:

| File | Holds | Rewritten? |
|---|---|---|
| `CLAUDE.md` | pure current state — what is true today | constantly |
| `docs/conventions.md` | locked conventions, each with the incident that produced it | append-only; authoritative where it and CLAUDE.md disagree |
| `DECISIONS.md` (this file) | *why* things are the way they are, in order | never |

Entries are `[date] — decision — why — consequence`. Decisions attributed to **Matthew Lebrecht**
are the project owner's; everything else is a build decision made against the conventions.

---

## Week 1–2 (2026-08-24 → 2026-08-31) — instruments, and the discovery that broke the first design

### D1 · 2026-08-31 · The evidence base is atomic observations plus a parallel record of attempts
**Why.** A harness that reports only what it found cannot distinguish "this company has no such
evidence" from "the instrument could not see". Coverage and failure have to be first-class.
**Consequence.** `Observations` and `Attempts` are separate sheets; attempt emission lives inside a
run-context (`core/attempts.py`) that reconciles declared scope against emitted rows and writes
`not_covered` for the difference. A confirmed absence is coverage, not failure.

### D2 · 2026-08-31 · Entity resolution refuses rather than guesses
**Why.** The Infor / "Information Systems" bug, and Prime Inc. matching four unrelated firms because
its name reduces to one common word.
**Consequence.** `core/resolution.py` scores on weighted name-token alignment, refuses below a
floor, and logs every rejection. Convention 11: **a single common token is never an identity.** This
recurs throughout the project — it is the characteristic failure named in D14.

### D3 · 2026-08-31 · The audit gate — new output is quarantined until judged
**Why.** H-FIRSTPARTY-01 v1.0 produced 248 rows at 97% coverage and 163 of them rested on a single
generic matched term. The defect was invisible in the summary line and obvious in the rows.
**Consequence.** A new harness version publishes no coverage number until an audit artifact exists;
`validate_repo_db.py` check 9 enforces it. Adversarial strata sample where defects have been found
before; the random control is the only extrapolatable rate. Procedure in
`docs/gates/gate_new_harness_output.md`, deliberately **loaded fresh at the checkpoint** so a harness
is not written to pass its own audit.

### D4 · 2026-08-31 · Exemptions are an explicit list of pairs, not a date rule
**Why.** A rule of the form "first run on or after 2026-09-01" has a boundary for a harness to land
on, and H-EMPREVIEW-01 was straddling exactly that boundary while the gate was being written.
**Consequence.** `docs/gates/grandfathered_harness_versions.json`, 18 exact
`(harness_id, harness_version)` pairs. Superseded in part by **D33**.

---

## Week 3 (2026-09-01 → 2026-09-08) — precision, then recall, then time

### D5 · 2026-09-01 · The run-ledger check compares the workbook to git, not to prose
**Why.** The previous check compared the workbook against CLAUDE.md, so documentation going stale
was indistinguishable from the database losing rows — which is the thing an abort exists to catch.
**Consequence.** `check_run_ledger.py` diffs against `git show HEAD:data/market_intel_db.xlsx`.
CLAUDE.md staleness became a warning, never an abort.

### D6 · 2026-09-01 · Audit artifacts go into version control
**Why.** They were gitignored, so a fresh clone failed the gate — a mechanical control that only
worked on the machine that built it.
**Consequence.** `harness_output/**` stays ignored except `audits/` and `reference_runs/`. Verified
by cloning to a temp directory and re-running the validator.

### D7 · 2026-09-01 · `superseded` added as a run disposition
**Why.** A version fully replaced by a later one has nothing live to audit, but "quarantined
forever" reads as unfinished work.
**Consequence.** A superseded version must hold **zero** observations, and check 9 enforces that
claim rather than trusting it — so the disposition cannot become a way to silence a failing audit.

### D8 · 2026-09-02 · Two-tier topic admission (`patterns` fire alone, `generic` needs corroboration)
**Why.** Six of seven `systems_integration` provider rows rested on the bare word "integration".
Buyer-side over-matching hides divergences; **provider-side over-matching manufactures them**, and
it was biasing toward the project's own thesis.
**Consequence.** `core/topics.py` gained the two-tier spine. H-SELLERCONTENT-01 was replayed:
`systems_integration` fell from 7 sellers to 1. The "64% of sellers" figure was never a finding.

### D9 · 2026-09-03 · Convention 41 — corroboration-strength gates write at low grade; identity gates refuse
**Matthew Lebrecht.** **Why.** D8 cut hard for precision, and the cut was indiscriminate: a claim
whose *referent* is right but whose *corroboration* is thin is a different thing from a claim about
the wrong company.
**Consequence.** 411 gates inventoried, 20 converted across 9 harnesses. A low-grade row is grade C +
`weak_clue` + confidence ≤ 0.4 + a `[low-grade:` marker. This is the single most consequential
methodology decision in the project: **89 of 147 valid buyer-side rows in the final matrix are
low-grade**, so most per-theme evidence exists because of it.

### D10 · 2026-09-03 · Five years is the staleness window, everywhere
**Why.** H-TRADEPRESS-01 used five years while the stated standard was 36 months, and four of the 46
stale refusals sat within two months of the line — the condition under which a threshold must not be
moved casually.
**Consequence.** `core/windows.py`, imported by every harness that enforces a window.

### D11 · 2026-09-03 · H-JOBPOST-01 keys are PRESENCE ONLY
**Why.** Only 13–17 of 108 careers pages are readable on the own-domain leg; the aggregator leg is
broad and shallow. An absence claim needs a denominator the instrument can defend.
**Consequence.** No absence claim from any job-posting key. Recorded as a standing condition, not a
temporary state.

### D12 · 2026-09-05 · A re-run changes a human-reviewed row only by opt-in
**Matthew Lebrecht.** **Why.** H-FMCSA-01 re-derived 20 reviewed pilot rows and differed from them.
**Consequence.** The writer **holds** the conflict; accepting is the reviewer's decision, executed
through `--refresh-reviewed`, then re-versioned and re-audited. Used again for D34.

### D13 · 2026-09-05 · The temporal schema — `Company_State_History`, append-only and immutable
**Why.** "What could the project say about this company and theme, in this week, and why not" is a
different question from "what evidence exists".
**Consequence.** One row per derivation × company × theme × ISO week; composition order is
detectability → realized reach → instrument class (convention 42). Derivations are **never
rewritten** — which is what makes D40 a design question rather than a patch.

### D14 · 2026-09-06 · The characteristic failure is named as a finding, not a bug list
**Why.** By this point loose pattern matching had manufactured false confidence nine separate times
(an executive named "How We"; "Corporate Governance Guidelines" as a person; a quote attributed to
Tom McGough off a page about someone else; 163 of 248 rows on one generic term).
**Consequence.** It belongs in the final report as a finding about automated evidence collection.
Two generalisations: a single common token is never an identity, and **the fix is an admission
threshold, not a strength downgrade** — a claim unsupported by its own evidence should not exist at
`weak_clue`.

### D15 · 2026-09-06 · Stable observation ids (convention 43)
**Why.** Harnesses that delete and rewrite unreviewed rows were renumbering claims, so an id did not
identify a claim over time.
**Consequence.** `Observation_Ids` registry; a claim keeps its id; 23 historical renumberings
recorded rather than reversed (their claims are live under newer ids, so restoring them would give
one claim two live ids).

### D16 · 2026-09-06 · The random-control exclusion threshold: 0.15 under 20, 0.10 at 20 and over
**Matthew Lebrecht.** **Why.** H-TRADEPRESS-01 v1.6 was a census of 9 with one exclusion — 11.1%,
which failed a flat 10% threshold that was never designed for a population that small.
**Consequence.** `core/audit.py::threshold_for`. Every artifact records the literal it was evaluated
against, so a threshold change cannot retroactively re-judge an old audit.

### D17 · 2026-09-06 · No theme prints "buyer silent" without a licensed instrument
**Why.** Themes with provider messaging and no buyer evidence were being written up as divergences
when they were untested.
**Consequence.** `gap_report.py` reads `core/composition.py::absence_licensing`. A theme whose every
buyer instrument is IC1 or presence-only prints "no absence instrument". Superseded in part by
**D41**.

### D18 · 2026-09-08 · The coherence framework sits behind a wall
**Why.** A research overlay that could churn must never feed a gate decision.
**Consequence.** `Observation_Coherence_Tags` is keyed by observation id and never a column on
`Observations`; check 11 **fails** if any gate-computing module so much as names the table. The
pattern generalised into convention 44 (D26).

---

## Week 4 (2026-09-13 → 2026-09-17) — public records, validity, and the limits of the instruments

### D19 · 2026-09-13 · USASpending was never blocked by the network
**Why.** Two sessions had attributed the failure to a network appliance and a TLS interception. Both
were wrong: USASpending's own web application firewall refused the probe's User-Agent on the token
`ResearchBot`, and the TLS error was a trust-store gap.
**Consequence.** `H-PROCUREMENT-01` was built. Convention 38 amended: **an access failure is
attributed only after the attribution is tested**, because a confident wrong attribution cost this
project two weeks of a buildable instrument.

### D20 · 2026-09-13 · Buyers appear as the SELLER in public-record families
**Why.** Federal prime awards and municipal building permits both describe what these firms build
*for others*.
**Consequence.** Neither harness routes a theme, and neither can license a buyer-side absence. A
finding about which record families can see buyer behaviour at all — carried into the report.

### D21 · 2026-09-14 · SEC reporting status is derived, never a column
**Why.** "Public or private" is not a stable attribute; it is a status with a date and a source.
**Consequence.** `SEC_Reporting_Status_History`, append-only; check 12 **fails** on any
`Companies.public_private` column. SpartanNash's deregistration then moved H-SEC8K-01's derived
scope from 3 companies to 2 without anyone editing a company row.

### D22 · 2026-09-15 · Convention 45 — no observation is ever hard-deleted, retroactively
**Matthew Lebrecht.** **Why.** Seven rows had been deleted on a reviewer's `unsupported` verdict.
Deleting evidence destroys the record of what the instrument did and why it was wrong.
**Consequence.** Every delete path in `core/db.py` refuses. Retirement became **invalidation**: a bad
row keeps its row and its id, and a dated determination is appended to
`Observation_Validity_History`. Nine pre-rule deletions were restored exactly, guarded against their
source commits. Check 15 fails on a hard deletion.

### D23 · 2026-09-15 · A determination is permanent; none reinstates
**Matthew Lebrecht.** **Why.** If invalidity could lapse when a later run happens to reproduce a
claim, the record would say different things at different times for reasons unrelated to the
evidence.
**Consequence.** `invalidated_not_reproduced` does not expire. A determination can only be
*superseded by a more accurate determination* — which is exactly what D35 did.

### D24 · 2026-09-15 · Invalid rows are read as invalid, and every count reports three measurements
**Matthew Lebrecht.** **Why.** A single net number hides whether it moved because evidence changed
or because a determination was recorded.
**Consequence.** Composition, published coverage and the reconciler read validity — through one
accessor, from three permitted modules, with the convention 41 wall amended rather than removed.
Counts print **total / valid / invalid**, never a silent net.

### D25 · 2026-09-15 · A harness can be held in code
**Matthew Lebrecht.** **Why.** "Do not run this" in a document is not a control.
**Consequence.** `core/holds.py` refuses every live run and every `--commit` before any cache or
workbook is opened. An offline replay that writes nothing stays allowed, because that is how the
measurement a hold waits on gets taken. Both holds set that day were lifted the same day, on
evidence.

### D26 · 2026-09-15 · Convention 44 — optional classifications live in their own linked table
**Why.** Evidence directionality, role reviews and validity are all *overlays*: sparse, optional,
and dangerous if they leak into a gate.
**Consequence.** Three tables (`Observation_Directionality_Tags`, `Observation_Role_Reviews`,
`Observation_Validity_History`), each with one writer, each behind a wall checked as a **failure**
(checks 13, 14, 15). None is ever a column on `Observations`.

### D27 · 2026-09-15 · A role verdict re-clears neither identity nor extraction
**Matthew Lebrecht.** **Why.** The `buyer_articulates` review asked one question. Letting its answer
touch `review_status` would silently re-certify things nobody looked at.
**Consequence.** 59 verdicts landed in their own table; `Observations` was verified unchanged cell
for cell.

### D28 · 2026-09-15 · The extraction fix reads the article body only
**Matthew Lebrecht.** **Why.** Seven rows matched their theme on page furniture — "Editors' picks"
teasers, an "An Informa PLC company" footer, a cookie-consent banner.
**Consequence.** H-FIRSTPARTY-01 v1.3, with five prerequisites verified against 111 cached pages
committed as fixtures. Its run recorded 97 machine rows invalid — the cost of the fix, paid in the
open.

---

## Week 4 close (2026-09-16 → 2026-09-20) — feasibility, correction, and closing out

### D29 · 2026-09-16 · FMCSA goes hybrid: SAFER authoritative, QCMobile for counts
**Matthew Lebrecht.** **Why.** Investigating a "missing field" note found the fields present and a
real bug behind them: authority was being read from `allowedToOperate` (a registration status), so
the QCMobile path asserted a private fleet was AUTHORIZED.
**Consequence.** v1.7. National averages are **not** overlaid — QCMobile serves a 2009-2010
benchmark where SAFER serves the current one, so the previous path compared carriers against a
sixteen-year-old baseline.

### D30 · 2026-09-16 · App-store telemetry: reported, not built
**Matthew Lebrecht.** **Why.** 25 of 108 companies publish an app, but only 5 publish anything a
consumer uses; the rest is workforce tooling, a different signal.
**Consequence.** Report appendix disposition. The probe's first pass reproduced the characteristic
failure three times in one run (a fitness club, a seafood restaurant, an email client), which is
itself recorded.

### D31 · 2026-09-16 · The coherence pilot is not executed
**Matthew Lebrecht.** **Why.** The over-firing cohort was 3 companies when assembled and 2 on valid
evidence; at that size the 60% criterion resolves to "2 of 2", so one tagging judgment decides it.
**Consequence.** Framework built and scoped, disposition written for the appendix. No tag writer, no
reduced test.

### D32 · 2026-09-16 · YouTube: confirmed non-signal
**Matthew Lebrecht.** **Why.** 58 of 108 companies have a channel and 45 posted within a year — but
1,457 video titles and 60 full descriptions carried **no** buyer-side modernization statement.
**Consequence.** Not built. Notably *not* a duplicate of the executive-voice instrument, which is
why the content check rather than the overlap was decisive.

### D33 · 2026-09-17 · A grandfathered exemption covers only runs that predate it
**Why.** A version is not a closed set: H-FMCSA-01 v1.3 gained 4 rows the day *after* its exemption,
and those rows inherited an exemption nobody granted them.
**Consequence.** check 9 honours an exemption only where every published run predates `date_added`.
Fails nothing today; tamper-probed both directions. Amends D4.

### D34 · 2026-09-17 · Accept the FMCSA 30-row refresh despite a two-week data gap
**Matthew Lebrecht.** **Why.** The national-averages fix alone justifies re-deriving.
**Consequence.** HR-0084 under the D12 opt-in; all 30 judged `supported` in a census audit and
published. Every refreshed row kept its human review status.

### D35 · 2026-09-17 · Supersede the 8 overstated invalidation statuses
**Matthew Lebrecht.** **Why.** HR-0083 recorded everything it stopped producing as an extraction
defect. For 8 rows that named the wrong cause in two *opposite* directions: 6 were wrong-company
rows (the article never named the company at all), 2 were correct rows that had aged out of the
five-year window.
**Consequence.** OVH-0112..0119 supersede the originals. The rows stay invalid; only the recorded
reason moved — D23 in action.

### D36 · 2026-09-17 · H-FMCSA-01's missing attempts are a documented limitation, not a retrofit
**Matthew Lebrecht.** **Why.** It is the only one of 17 harnesses that writes no `Attempts` rows.
Retrofitting changes what the harness *declares*, not what it *reads*, and 8 of 108 resolve to a
carrier because the other 100 are not motor carriers — a percentage over 108 would describe the
population, not the instrument.
**Consequence.** `docs/report_appendix_reliability.md` §1: *"H-FMCSA-01 predates the attempts-based
coverage convention and reports population facts outside that system."*

### D37 · 2026-09-17 · The theme evidence matrix is a pull, not a narrative
**Why.** The report needs raw material whose exclusions are applied *in* the pull, not bolted on
afterwards.
**Consequence.** `scripts/theme_evidence_matrix.py`. Invalid rows excluded entirely; seller-side
rows excluded from buyer counts; quarantined rows held out and shown separately. Reconciles with
`gap_report.py` once its low-grade exclusion is accounted for.

### D38 · 2026-09-17 · Two CLAUDE.md claims corrected against the matrix
**Matthew Lebrecht.** **Why.** `cybersecurity` was described as zero-buyer and formally untested;
`ot_modernization` as uninstrumented on both sides. Both predate the evidence that changed them.
**Consequence.** Corrected in place with the superseded wording quoted. Cybersecurity is now a
**mixed** case — 12 buyer rows *and* 9 companies composed as a licensed absence. Amends D17.

### D39 · 2026-09-20 · Quarantined runs resolved only where resolution is mechanical
**Why.** "Publish or resolve everything" would mean publishing versions whose zero is not a
measurement (H-VENDOR-01 v1.0), or moving a harness's quoted coverage onto an 8-company denominator
(H-TRADEPRESS-01 v1.7).
**Consequence.** 13 → 9 quarantined. One version aligned, three superseded. Everything else carries
a written disposition in `docs/analysis/open_items_2026-09-20.md`.

### D40 · 2026-09-20 · Composition provenance written back as a design question
**Why.** Derived rows cannot say which run licensed an absence. The fix is not two columns: because
derivations are immutable (D13), it needs a new derivation and leaves a permanent seam between rows
that have provenance and rows that never can.
**Consequence.** `docs/analysis/brief_composition_provenance_2026-09-20.md`, four options costed,
**nothing changed**. Recommendation: leave documented for this submission.

---

## Standing decisions about what is *not* attempted

| Decision | Reason |
|---|---|
| **LinkedIn is not attempted by any harness** | The highest-reliability source in the taxonomy is unreachable without authentication. Recorded so its absence is not read as an oversight |
| **X/Twitter and Meta not probed** | Effectively closed to compliant access |
| **`H-PATENTS-01` not built** | PatentsView was retired by USPTO on 2026-03-20; this needs a new source decision (Open Data Portal bulk data), not an access fix |
| **No JavaScript rendering, no robots-line crossing** | Repeatedly the cheapest way to raise coverage, repeatedly refused. Dayforce and UltiPro serve `Disallow: /`; the job-posting ceiling (17 deep, 58 reachable of 108) is a *structural* finding because of this |
| **No blended project-wide coverage figure** | The harnesses have different denominators and different instrument biases, so a mean over them names nothing (convention 21a) |

---

## Appended after the build closed

### D41 · 2026-09-20 · The coherence pilot's four open questions are closed as MOOT
**Matthew Lebrecht.** **Why.** D31 settled the pilot's disposition — framework built and scoped,
evidence volume insufficient to execute meaningfully — and that disposition was written into the
report appendix without needing any of the four questions answered. Leaving them on the open-items
register implied the disposition was provisional, pending a ruling. It was not.
**Consequence.** The four questions (does the pilot count invalid rows; is COHP-0001 refrozen or
re-derived; is the over-firing floor still 3; who assigns a dimension candidate) are kept in
`docs/diagnostics/coherence_pilot_execution_2026-09-15.md` as the record of what executing the pilot
*would* have required, explicitly not as items awaiting an answer. Nothing about the appendix
disposition changes.

### D42 · 2026-09-20 · An audit verdict applied from a blanket ruling was retracted
**Matthew Lebrecht.** **Why.** "I review all manual review rows and they are all supported" was
applied to the 30 rows of the H-FIRSTPARTY-01 v1.3 audit census — correct, that sheet's verdict
vocabulary is exactly `supported` — and also to **O00530**, which is not an audit-census row. The
question O00530 carries is *which company the release is about*, not whether a claim is supported at
the strength stated. That call is the reviewer's to make directly, and it had not been made.
**Consequence.** `scripts/retract_misattributed_verdict.py` restored the row to its exact pre-verdict
state, guarded in both directions and verified to change no other row. **This is not a breach of
"never overwrite human review"** (convention 1): that rule protects a judgment a person actually
made, and here the stored judgment was itself the error — a `review_source = human` recording a
verdict nobody gave. A false attribution in the evidence base is worse than its absence. The narrowed
question now sits in `harness_output/audits/DECISION_O00530_front_line_identity.md`.

**The general rule this establishes:** a blanket approval covers only sheets whose verdict vocabulary
it actually fits. A role review (`correct` / `buyer_acts` / …) and an identity question are not audit
verdicts, and neither may be inferred from "all supported".
