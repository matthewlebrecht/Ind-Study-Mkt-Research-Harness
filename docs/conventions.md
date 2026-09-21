# Locked conventions

Every rule this project has committed to, in one place, with the incident that produced it.
`repo_structure_spec.md` P3 is the reason this file exists: a convention scattered across
five documents is a convention that gets re-litigated.

Nothing here is provisional. Changing one of these is a decision, not a refactor.

---

## Evidence and review

**1. Idempotent writes; never overwrite human review.**
Re-running a harness reconciles against what is in the sheet on the natural key
`(company_id, harness_id, topic, source_url)`. Unchanged rows are left alone, stale
unreviewed rows refresh in place, and a claim that changed *after* a human reviewed it is
reported as a conflict for a person to resolve. Human review is the scarce input to the
Week 4 reliability evaluation; a re-run must never silently erase it.
Enforced by `core/db.py::sync_observations`, tested by `core/tests/test_reconcile.py`.

**2. Review a claim against the date it cites, not today's live page.**
If the figures match the snapshot date the row records, the row is `accepted` even when
today's page differs. Drift is corrected by re-running the harness, never by hand-editing
rows. `corrected` is reserved for genuine harness error. Otherwise the Week 4 reliability
metric measures the calendar rather than the harness — which is exactly what nearly
happened: all nine "corrections" in the 2026-08-24 review were SAFER advancing its snapshot
from 08/20 to 08/23 mid-review. Extraction accuracy at time of retrieval was 27/27.

**3. Anything stated inside an observation is computed from the source snapshot's own
date, never from the wall clock.** A row that says "3 months ago" drifts against its own
stored copy the moment it is read again.

**4. `source_grade = D` is never written.** D means "exclude from evidence base", so the
row does not belong in the evidence base. `core/db.py::validate` refuses it.

---

## Coverage and failure reporting

**5. Log attempts, not failures.** A failure-only table has no denominator: it cannot
distinguish "this failure mode is rare" from "the harness quietly stopped trying." Every
scoped `(company, signal)` pair gets exactly one `Attempts` row, including pairs the
harness skipped early. Enforced structurally by the run context in `core/attempts.py`,
which closes out anything declared-but-not-attempted as `not_covered`; tested by
`core/tests/test_attempts.py`.

**6. A confirmed absence is coverage, not a miss.** `absent_confirmed` is asserted only
when the harness both reached an authoritative source **and** that source is complete for
the signal. CT Logistics resolving to no USDOT number is correct — a freight-audit firm
operates no fleet — so H-FMCSA-01's true resolution result is 8/8, not 7/8.

**6a. `absent_confirmed` requires every name variant to have been tried.**
Asserting absence after one failed lookup writes *false negative evidence*, which is worse
than a gap because it carries weight. H-SAFETY-ENV-01 v1.0 recorded Mack Group and Duke
Manufacturing as having no OSHA record; both have one, under "Mack Molding" and "Duke
Manufacturing" respectively. Six real inspections were nearly recorded as confirmed absence.

**7. Every suppressed or truncated result is reported, never silently dropped.**
A cap that fires becomes a row (`governance` / `suppressed_by_cap`), not a silence. OSHA
serves 20 inspections per page and publishes no total; 12 of 107 companies were recorded as
having exactly "20 inspections" as though that were a total. Counts that are floors say so
inside the observation text.

**8. Idempotent re-runs are not punished.** `covered` means
`records_written + records_reconciled > 0`. A re-run that reconciles 27 unchanged rows and
writes zero new ones is fully covered. A metric that penalises correct idempotent behaviour
is worse than no metric.

**9. Coverage math counts `scope = scoped` rows only.** Incidental finds — an Observation
in a family the harness was not scoped for — are recorded and counted in observation totals
but excluded from the coverage denominator, or opportunistic finds would inflate it
inconsistently.

**10. `known_issues` is derived, not hand-written.** Generated from the run's own Attempts
rows grouped by `failure_category`. See `core/attempts.py::derived_known_issues`.

---

## Entity resolution

**11. Score on name tokens, never substrings.** A character-level ratio scores SOUTHWESTERN
EXPRESS highly against WESTERN EXPRESS — it contains every character in order. Token
scoring does not. This is the failure that actually happened.

**12. Refuse below the confidence floor; log every rejection.** A refusal is a claim about
the source and must be checkable afterwards. `entity_no_candidate`,
`entity_below_threshold` and `entity_ambiguous_multiple` are distinct because they route to
different fixes.

**13. Never guess an abbreviation.** Searching OSHA for the bare token "PLS" (from "PLS
Logistics") returns "Pls Drywall And Ceilings Inc." Query variants are limited to the full
name, the name minus trailing legal-form suffixes, and human-seeded aliases in
`data/company_aliases.json`. Every alias entry is a documented limit on automation and
carries a `why`.

**14. One company_id does not map to one registrant.** Kenco holds five co-located USDOT
registrations. `resolve(accept_multiple=True)` takes them together rather than picking one
arbitrarily.

**15. Parse state codes; never slice them.** `Companies.hq_state` holds bare codes for the
pilots and `"City, ST"` for the Anvil rows. Taking the first two characters yields `"CH"`
for Chicago — and OSHA does not reject an unknown state, it silently searches nationally.
`core/resolution.py::state_code` returns `""` rather than guessing.

---

## Classification

**16. A loose pattern manufactures confidence; it does not merely add noise.**
The founding case: bare `Infor` matched inside "Information Systems" and pushed Kenco's ERP
signal from `weak_clue` to `repeated_pattern`. `signal_strength` drives downstream finding
weight, so the bug inflated a conclusion rather than adding a stray row. Vendor names need
a word boundary on *both* sides.

The same failure has since recurred eight more times in new places, which is why it leads
this section:

- H-WAYBACK-01 reported 12 "removed modernization pages" for McGough Construction; all were
  dated news posts matching on substrings like "research" inside a research-center award
  title.
- H-SELLERCONTENT-01 reported 100% coverage while half its providers had been read off
  homepage-discovery substitutes rather than their actual service pages.
- H-EXECID-01 extracted an executive named **"How We"** (a "How We Work" heading fragment)
  titled President and CEO, and another named **"Become An"** (from "Become An
  Employee-Owner").
- H-EXECID-01 extracted **"Corporate Governance Guidelines"** as a person, titled from an
  adjacent "Code of Ethics for CEO" link. That page then outranked Merit Medical's real
  `/about/executives` page on people-count, so one bad name displaced an entire correct
  roster -- the match did not add a bad row, it removed the good ones.
- H-FIRSTPARTY-01 recorded press releases about Digital Prime Technologies, Prime Data
  Centers, Primech and Prime Electric as first-party evidence about **Prime Inc.**, a
  Missouri trucking firm, because the name reduces to the single common token PRIME.
- H-FIRSTPARTY-01 rested **163 of its 248 observations on one generic matched term** --
  "workforce management" (48), "integration" (26), "cybersecurity" (18), "ai" (12). A
  Gilbane earnings release saying "our integrated platform" became an announcement about
  systems integration.
- H-EXECVOICE-01 attributed a quote to **Tom McGough** off a page about a different person,
  because "McGough" appears nearby as the *company* name.

**17. Absence of a negative is not evidence of a positive.** A clean OSHA record maps to
`organizational_state = unknown`, never `target_state`. Not being cited is not evidence of
modernity.

**18. Active AI/tech hiring means `active_transition`, not proven capability.**
Treat as mature capability only with evidence of an *established* function: multi-year
hiring history, a non-newly-created leadership title, or an existing internal platform.

*Settled 2026-09-06 (session 14 item 9, Matthew's decision):* a company that shows BOTH an
established internal platform AND active hiring specifically for implementation or
modernization roles is a **positive signal** -- read as a company whose current estate is
inadequate relative to what is achievable and that is acting on it, i.e. a process-
optimization prospect -- never as "already modernized, disqualify". This replaces the
Week 1 "current leaning" and the `pending_review` handling for mixed-signal cases in
`docs/archive/qualification_procedure.md`. Qualification status for such a company is
`qualified`, and its hiring rows carry `organizational_state = active_transition` as 18
already says. An established platform on its own, with no such hiring, is still the only
case that reads as mature capability.

**19. Repetition is the evidence for `repeated_pattern`.** A redundancy filter that
discards instances 2..N destroys the only basis for the value it was measuring. Suppression
removes rows, never counts — the surviving row carries the instance count.

**20. Enrichment values are written to the target sheet; enrichment *conflicts* become
Observations.** H-FMCSA-01 emitted a `workforce_scale_conflict` for Venture Logistics
(Companies says 750 employees; the registry shows 1,474 drivers) rather than silently
overwriting the sheet. A conflict is a checkable claim about the company; a value is not.

**21. Where the buyer side has no instrument, say so.** `core/topics.py` marks themes
`buyer_detectable = False`. "Sellers message heavily about cloud migration and no buyer
signal mentions it" is a finding only if a buyer-side instrument existed that could have
found it. Otherwise it is a statement about the harness portfolio.

**21a. An instrument existing is not the same as an instrument being unbiased.**
As of 2026-08-31 all nine themes are `buyer_detectable = True`, because H-FIRSTPARTY-01
classifies free-text company announcements through the same spine and can therefore see
any of them. Leaving three flags False after that made `gap_report.py` contradict itself,
printing "NO INSTRUMENT" beside a non-zero buyer count.

But the flag is now carrying less weight than it used to, and the write-up must not treat
all nine as equally testable. A first-party announcement is a *biased* instrument:
companies announce programmes they are proud of and never announce the legacy estate that
forced them. So on a theme visible only through announcements, absence of buyer signal
means "not announced" — weaker than "not happening", and weaker than the absence of a job
posting, which at least reflects unguarded operational behaviour. Cybersecurity is the
extreme: essentially nothing is announced voluntarily.

The two live candidate divergences (cloud migration, cybersecurity/OT) sit on exactly the
themes companies are least likely to announce. They are the weakest-supported findings in
the set, not the headline ones. The per-theme `note` fields in `core/topics.py` record
which instrument backs each flag and how biased it is; read them before quoting a
divergence.

---

## Schema and repo

**22. Controlled vocabularies are additive-only.** Adding a value is cheap; renaming or
removing one breaks version-over-version trend queries. Retire by marking inactive.

**23. Validation bindings are declared, not assumed.** The workbook's nine dropdown
validations silently disappeared between 2026-08-22 and 2026-08-24 and nobody noticed for
four days, so no controlled vocabulary was actually enforced on anything written in that
window. `scripts/migrate_schema.py::VALIDATIONS` is the declarative expected set and
`scripts/validate_repo_db.py` check 7 fails if reality diverges.

**24. `Attempts` is append-only and never reconciles.** Observations reconcile because they
hold current best knowledge of a claim; attempts record what happened during one execution
and are immutable history. Reconciling would erase the trend the table exists to produce.

**25. `harness_id` denotes one logical harness, not one external API.** Split only when the
pieces are independently useful, need independent version cadence, or one's output feeds
the other. Shared API calls are not grounds for splitting.

**26. `H-FMCSA-01` is grandfathered, not renamed.** It names a source rather than a signal
type, which is inconsistent with the `H-{SIGNAL}-{NN}` convention adopted later. Its ID is
written into 27 human-reviewed Observations; renaming breaks provenance on reviewed evidence
to fix a cosmetic inconsistency.

**27. A version bump that invalidates prior rows sets `reprocessing_required: true` in the
manifest**, with `affected_topics`. Whether a version requires reprocessing determines
whether prior observations are still valid evidence, so it is a field, not a paragraph.

**28. `core/db.py` is the only module that writes to the workbook.** A harness that writes
directly cannot be made to log its own misses.

**29. An offline replay must reproduce the run it replays.** H-SELLERCONTENT-01 v1.0 gated
homepage discovery on `not offline`, so a replay produced 38 observations at 83% coverage
where the live run produced 43 at 92%. Every page discovery needed was already archived; the
gate bought nothing and defeated the archive's only purpose.

**30. A natural key must be stable across runs.** H-SELLERCONTENT-01 v1.1 keyed claims on
the page a theme was matched on, so when discovery substituted a different URL the same
logical claim inserted a duplicate instead of reconciling — 48 rows for 43 claims.
Identity is what the claim is *about*; the evidence for it belongs in `evidence_excerpt`.

---

## Lessons generalised from the 2026-08-31 session

**31. A single common token is never an identity.**
Convention 11 was written about `core/resolution.py`, but the lesson is not confined to
candidate-list resolution: it applies anywhere a name is matched against text. The test
must scale with how distinctive the name is. A coined token (MIDMARK, KENCO, RYCON) stands
alone; an ordinary English word (PRIME, SUMMIT, LIBERTY) must be backed by the full company
phrase. See `harnesses/h_firstparty_01/article.py::is_about_company`.

The corollary caught a second time in the same session: where a person's surname is also a
token of their employer's name -- common in construction and trucking, which are full of
eponymous firms -- proximity attribution is worthless, because every mention of the
employer satisfies it. Only explicit attribution counts there.

**32. An unsupported claim gets an admission threshold, not a strength downgrade.**
The tempting fix for a weakly-evidenced row is to write it at `weak_clue` and let review
sort it out. That is wrong when the evidence does not support the claim *at all*: a press
release mentioning "integration" once is not an announcement about systems integration at
any strength, and admitting it at `weak_clue` still puts a false row in front of a
reviewer and into every count. Decide admission first, strength second.

**33. Audit a new harness's first output row by row before trusting its coverage number.**
Every defect in this section was invisible in the run summary and obvious in the rows.
H-FIRSTPARTY-01 reported 97% coverage on a run where two thirds of the observations did
not support their own claim. A high coverage number on a *new* harness is a prompt to
check, not a result -- and this is now the third time a suspiciously clean number preceded
a discovered defect.

---

## The audit gate (2026-08-31)

**34. A new harness version's output is quarantined until an audit artifact exists.**
Convention 33 was a rule that depended on somebody remembering it. The session-2 audit that
cut 258 rows to 87 happened because Matthew asked for it; nothing forced it, and nothing
would have noticed if it had been skipped. So the requirement is now structural: output
lands `publication_state = quarantined`, its run lands `publication_status = quarantined`,
a quarantined run contributes **neither numerator nor denominator** to any published
coverage number, and `validate_repo_db.py` check 9 fails if a published version has no
audit artifact. Row counts may still be reported from quarantine; coverage percentages may
not. Procedure: `docs/gates/gate_new_harness_output.md`. Exemptions live only in
`docs/gates/grandfathered_harness_versions.json` -- an explicit list of pairs, never a date
range, because a date boundary is something a harness can land on and H-EMPREVIEW-01 was
straddling exactly that boundary while the gate was written.

**35. The never-overwrite rule keys on provenance, not on a value.**
Convention 1 tested `review_status in {accepted, corrected, rejected}`. That was the same
thing as "a human wrote this" only for as long as humans were the sole writers of review
state. The audit gate writes machine-side `audit_verdict`s that must stay freely
overwritable, so the test moved to `review_source` (`human` / `machine`). Protection is the
**union** of the two signals -- `review_source = human`, or a reviewed `review_status`,
either one -- because no harness ever writes a reviewed status, so one appearing can only
have come from a person, including a person hand-editing the workbook in Excel without
touching the provenance column. Keying on provenance alone would have opened exactly that
data-loss path.

**36. A lookup that answers about the wrong thing reports success confidently.**
Two new instances in one session, and they are a distinct sibling of convention 16 rather
than another case of it: the pattern was right, the thing it was applied to was wrong, and
nothing anywhere raised an error.

- `core/audit.py` bound `AUDIT_DIR` as a **default argument**, freezing the path at import.
  Redirecting the directory then wrote to one place and read from another, and the check
  reported clean about a location nothing had been written to.
- H-PRODUCTQUALITY-01's response-cache key was `(instrument, company)` with no fingerprint
  of the request URL. Fixing a broken CPSC query had no effect, because the harness
  replayed the broken query's answer out of the same day's partition. A cache key that does
  not change when the request changes is not a cache; it is a stale answer with a confident
  name.

A third instance, 2026-09-01, and the one that shows the shape is not confined to caches
and paths. `scripts/probe_sources.py` verified TLS with `urllib` +
`ssl.create_default_context()`, which on Windows trusts the **OS certificate store**, while
every harness fetches with `requests`, which trusts **certifi**. The two stores disagree
about exactly one host, so the probe reported `api.usaspending.gov` as a TLS failure that no
harness would ever have seen, and the 2026-08-31 session recorded a source as unreachable on
the strength of it. The script whose entire job is attribution was measuring a client stack
nothing else in the repo uses.

The tell in all three cases was that a change made no difference. When a fix produces
byte-identical output, suspect the lookup before suspecting the fix.

**This is now the fastest-growing failure family in the project, and it is recurring rather
than incidental.** Five instances across four subsystems as of 2026-09-01:

| Instance | The wrong question it answered |
|---|---|
| `AUDIT_DIR` bound as a default argument | a directory nothing had been written to |
| H-PRODUCTQUALITY-01's cache key | yesterday's query, after the query was fixed |
| `probe_sources.py` verifying TLS | a trust store no harness uses |
| `q="Kenco Group"` returning 55 | the full text of filed documents, not the parties |
| NLRB "no interface exists" | invented API paths and a response-size inference, never the site's own form |

The last two are worth reading together. Both were confident numeric or categorical answers
that went straight into a state document -- the 55 became this harness's expected yield in
`CLAUDE.md`, and the "no interface" verdict removed a whole source from the portfolio for a
day. Neither was checked against the thing it claimed to describe.

**The test is cheap and it is the whole convention: change the input and assert the output
changes.** Where the lookup is a whole pipeline, run it against inputs whose answers are
already known and confirm it reproduces *those* — a re-judge that returns "nothing changed"
is indistinguishable from a re-judge that did not run. The 2026-09-01 re-judge of
H-TRADEPRESS-01's 34 refusals was verified this way before its "0 changed" was believed: it
was replayed against the 2 pages the run admitted and the 7 it gated, and reproduced all
three outcome classes.

**37. A fix is not verified until it has been run against the case that was already working.**
Convention 33's companion, stated separately because it has now fired four times. Tightening
company identity fixed Prime Inc. and broke Midmark. The OSHA fix replaced a declared cap at
20 with an invisible one at 40. In the 2026-08-31 session: switching H-TRADEPRESS-01's
discovery to `site:` queries fixed outlet targeting and starved the general query, dropping
Gilbane from 3 rows to 0 because the interview that produced them now sat behind ten site:
hits and was never fetched; and the page-furniture filter that correctly killed MedTech
Dive's navigation also deleted the Gilbane Q&A, whose speaker labels are 15-character
blocks. Both fixes were correct. Both broke something that had worked ten minutes earlier.

A fifth, 2026-09-01, this time caught by the practice rather than by the incident: rewriting
`probe_sources.py`'s transport and adding filter-interstitial detection could easily have
broken the `EXPECT_TEXT` path, whose whole point is that NLRB's `robots.txt` is a successful
fetch of something that is not JSON. The three sources that were already answering
(CourtListener JSON, NLRB text, openFDA) were re-run and confirmed still `ok` before the
change was committed.

The practice: before accepting a fix, re-run the case that motivated the *previous* fix.

**38. An access failure that might be local is not a claim about a source.**
Convention 6a says a false record is worse than a gap, and this is the case that tests it
from the other side. H-EMPREVIEW-01 wrote 107 `access_blocked` attempts citing Glassdoor's
published `Disallow: /`, which are true statements about the source. On 2026-08-31
`api.usaspending.gov` failed TLS certificate verification while every other HTTPS host in
the same run verified fine -- the signature of a TLS-intercepting middlebox on one route,
not of anything USASpending did. Writing 108 `access_blocked` rows from that would have put
a false claim about a federal database into the evidence base.

Attribute the failure before recording it: a published policy, a 401/403, or a moved
endpoint is the source's. A TLS error, a DNS failure, or a timeout on one host is
unattributed until it reproduces from somewhere else. `scripts/probe_sources.py` records
the evidence and writes nothing to the workbook.

*Amended 2026-09-13 (Week 4): the USASpending attribution above was wrong both times, and
the decision to write nothing was right both times.* It was never the network. The
"Web Page Blocked!" page with a client IP and an Attack ID was served by USASpending's own
web application firewall, behind its F5 load balancer: it arrived inside a TLS session
verified against Treasury's genuine Entrust certificate, with the load balancer's
`BIGipServer~api.usaspending.gov` cookie set on the block response, and nothing on this
network can answer inside a verified session. The trigger was the probe's User-Agent,
`IndStudyResearchBot/1.0 (...)`: the WAF matches the token `ResearchBot` (`Bot`, `crawler`,
`Googlebot`, curl, python-requests and an empty UA all pass), and the harness UA got HTTP 200
from the same egress IP on every endpoint. The 2026-09-01 "different network" was not one:
the egress IP named on that day's block page is the egress IP today. PatentsView, the other
half of the same entry, is the source's too: USPTO retired the PatentSearch API on
2026-03-20 and removed `search.patentsview.org` from public DNS (NXDOMAIN from Cloudflare
DoH as well as the local resolver). The Texas breach-portal "timeout" (session 16) did not
reproduce on either Texas host and is not the same root cause.

Two refinements to the rule, both from this case. **A block page that names your IP is
not evidence the block is local** -- server-side WAFs echo the client IP too; the test is
whether the page arrived inside a TLS session verified to the source's own certificate. And
**vary one request property at a time before blaming a route** (User-Agent, method, path,
host): the whole diagnosis was a 13-row User-Agent table, and a week of "blocked here"
sat on a string only the probe sent.

**39. Suppression must be auditable, so record which kind it was.**
`suppressed_redundant` conflated "the natural key already holds this" -- deterministic,
cheap, always right -- with "a classifier judged this instance to add nothing new", which
is a judgment call that can be wrong. Split into `suppressed_redundant_key` and
`suppressed_redundant_judged`. The second exists so the gate has a stratum to sample: every
other stratum draws from rows that were *written*, so without it the gate measures precision
only and can never fail a harness for throwing good evidence away. A gate that can only
catch over-admission is half a gate.

**40. A test suite that passes over a known-live defect is asserting the implementation,
not the requirement.**
`core/tests/test_execvoice_quotes.py` was green for months while `quotes.py` scored the
commonest attribution shape in American journalism -- `"...," Broderick said.` -- as
`proximity` instead of `explicit`. The suite was not thin: it covered surname collisions,
eponymous firms, boilerplate, off-topic quotes and the state ladder. What it never covered
was the one shape nobody had thought of, and its fixtures were written from the code's
behaviour rather than from what correct attribution scoring is. So the test and the code
agreed with each other about the wrong thing, and neither could catch the other.

This is **not** convention 16. A loose pattern manufactures confidence in a *claim*; this
manufactures confidence in the *checking apparatus*, which is worse, because it is the
thing you would otherwise use to find the first problem. It is also not convention 33: that
one says audit the rows because the summary hides defects, and this one says the tests hide
them too.

The practice, and it costs nothing: **when a defect is found by reading output, check
whether an existing test covered that code path. If it did and stayed green, the test is
wrong too, and it gets fixed in the same commit as the code.** A fix that leaves the test
untouched has left the reason the defect survived exactly where it was.

Applied 2026-09-01: the attribution fix shipped with three new cases -- the full four-shape
matrix for an ordinary surname, the eponymous person-versus-company separation, and a guard
that the fix does not *upgrade* a third-party quote. The matrix is the point. Asserting
that one shape works is what the suite already did; asserting that all four are classified
correctly is what would have caught this.

A corollary about scope. One of those new tests documents a defect it deliberately does
*not* fix -- proximity attribution ignoring an intervening explicit attribution to someone
else -- and says in the docstring that it was verified identical before and after the
change. A test that asserts less than it could, and says why, is more useful than one that
quietly bundles two fixes and makes the audit between them uninterpretable.

**41. A corroboration-strength gate writes at low grade; an identity gate refuses.**
Decided by Matthew on 2026-09-03 after the precision/recall reset at the end of session 8,
and applied across the whole portfolio in session 9. Two kinds of gate had been treated
alike. An IDENTITY gate protects the referent: wrong company, dictionary-word-only token
match, PR-wire or index page, eponymous-firm trap, generic-homepage substitution, wrong
speaker. A referent error is excluded at extraction, at any strength, exactly as
conventions 16, 31 and 32 say, and nothing in this convention loosens one. A
CORROBORATION-STRENGTH gate is different: the pattern is plausible and the referent is
right, but the claim is not independently strong enough to stand alone -- one generic term
in a long release, a quote under the length floor, an out-of-service count on too few
inspections, a vendor docket under a non-commercial nature of suit. Those gates now WRITE
the row at low grade and let the review layer sift it, rather than the extractor deciding.

A low-grade row is recognisable by construction, so any consumer can filter on any one of
four marks and get the same set: `source_grade = C`, `signal_strength = weak_clue`,
`confidence_0_1 <= 0.4`, and an `evidence_excerpt` beginning `[low-grade: <gate>;
corroboration-strength gate relaxed 2026-09-03, review before use]`. `core/topics.py`
holds the constants and `classify_tiered()`, which returns the generic-tier hits `classify()`
declines. Grade D stays unwritable (`core/db.py` refuses it); C is the floor.

Why this is an amendment to convention 32 and not its repeal: 32 said an unsupported claim
gets an admission threshold, not a downgrade, and it was written against rows whose
evidence was about the wrong thing. Where the referent is right, the cost of a refusal is
recall the reviewer never sees, and the cost of a marked low-grade row is a reviewer's
minute. The reset chose the minute. Methodologically: confidence-tier uncertainty is
captured, graded and reviewed; referent error is excluded at extraction. A gate that fits
neither cleanly (a temporal window, a causal confound like the Wayback replatform test, a
characterisation-versus-action rule) is NOT converted by default -- it is logged for a
decision. The inventory that applied this is `docs/diagnostics/gate_inventory_2026-09-03.md`.

Amended the same day (session 10, Matthew): a CONFOUND is a third case and is folded into
neither. The Wayback replatform refusal (W8) is admitted at low grade with a DISTINCT marker,
`[low-grade: confound-admitted; W8 replatform refusal relaxed 2026-09-03, review before use]`,
because the removals are real and the referent is right but a competing explanation (a site
migration) is affirmatively supported -- that is not "weak but correct" evidence, and the
methodology write-up must not count it as an ordinary corroboration-strength conversion.
Same mechanical tier (C, weak_clue, confidence <= 0.4, quarantined); different marker, so the
two sets stay separable. Also decided in session 10: the staleness standard is five years
everywhere (`core/windows.py`), so the temporal-validity gates are settled rather than a
fourth case; and journalist characterisation became its own signal type (ST-PRESSCHAR,
`buyer_articulates`) rather than a gate to relax -- an evidence-type distinction, built.

## The temporal schema (2026-09-05, session 13)

**42. A bucket the project could not observe is null with a reason, never an absence; the
reason names what would resolve it.** `Company_State_History` composes in a fixed order --
detectability, then realized reach, then instrument class -- and stops at the first gate that
fails. A bucket before a theme's `buyer_detectable_since` is `theme_not_detectable` (resolves
by waiting); a bucket no covering instrument's REALIZED reach spans is `no_reach` (resolves
by acquiring access, and is the acquisition backlog); a bucket reached only by IC1/IC2 or
presence-only instruments with nothing found is `no_absence_license` (taxonomy §26,
formally untested). Only an IC3/IC4 instrument that is not presence-only, reaching the
bucket and finding nothing, writes `absent`. Three mechanical corollaries, each asserted by
`core/tests/test_schema_delta.py` §7:

- Composition reads `realized_reach` and never `nominal_reach`; the string does not occur
  in `core/composition.py`'s derivation code. Nominal reach is the acquisition-backlog
  report, not an inference input.
- Every gating value is STAMPED on the derived row (`definition_hash`,
  `buyer_detectable_since`, `min_retrospective_reach`, `covering_instruments`) and the
  writer refuses a row past the reach gate without its stamp. Nothing is joined live: a
  later change to `Harness_Sources` or to a theme is a visible difference between two
  derivations, never a silent rewrite of one. The table is append-only and a derivation is
  written once (`core/db.py::append_state_history`).
- `Signal_Types.status` is a ROLLUP filter, never a write filter. `core/attempts.py::rollups`
  and `scripts/published_coverage.py` apply it identically; the Attempts sheet keeps every
  attempt that happened.

Incident: the three themes that became detectable on 2026-08-31 sit inside the five-week
evidence window. A backfill without the detectability gate would have written the week of
2026-08-24 as a clean absence for cloud, cybersecurity and workforce enablement -- the exact
divergence pattern the project exists to detect, manufactured and then immutable. The first
dry-run derivation (2026-09-05) records 216 such theme-buckets as `theme_not_detectable`
instead. The same derivation found that NO theme has a licensed-absence instrument today:
H-JOBPOST-01 is IC3 but presence-only until its readability denominator is accepted, and
every other theme instrument is IC1 or IC2. `Theme.absence_licensed = True` on THEME-01..06
predates that condition and is now a stale flag, logged in CLAUDE.md rather than flipped.

**43. An observation id belongs to its claim forever.** `Observation_Ids` (session 14,
2026-09-06) is the registry of every id ever assigned, keyed on the natural key
(`company_id`, `harness_id`, `topic`, `source_url`). Every insert path asks the registry
first: a claim that once had an id gets it back; a claim that never had one is allocated
a number above every id ever assigned, live or retired, so a retired id is never handed to
a different claim. Every delete path retires the id in the registry instead of forgetting
it. Existing ids were not renumbered -- the registry was backfilled from the live sheet and
from the workbook's git history (24 retired ids, `scripts/backfill_observation_ids.py`) --
so an id cited in an audit artifact, a report or the Notion log keeps meaning what it meant.
`validate_repo_db.py` check 10 fails on any live id missing from the registry, any id whose
key drifted, any registry id marked live with no row, and any key carrying two live ids.

Incident: every delete-and-rewrite replay (EXECVOICE, TRADEPRESS, LEGAL, PRODUCTQUALITY on
`--commit`; FMCSA on `--force-rewrite`) allocated fresh ids from `max(live) + 1`, which
both renumbered surviving claims and could hand a deleted claim's number to a new one on
the next run. Five ids had to be acknowledged by hand with `check_run_ledger.py --retired`
in session 10; the FMCSA 20 kept their ids in session 12.5 only because the refresh path
updates in place. The registry makes the property structural rather than a habit.

**44. An optional classification of an observation lives in its own linked table.** Any
non-blocking tag on `Observations` -- a classification that no gate requires and that not every
row needs -- is stored in a dedicated table keyed BY `observation_id` (one row per tag, with
`tagged_at` as the load date and a `tagging_run_id` naming the harness, session or batch that
produced it), never as a new column on `Observations`. This holds whether or not the tag's
vocabulary is expected to churn, so the question is not re-opened field by field. Every such
table sits behind the convention 41 wall: no module that computes `review_status`,
`audit_verdict`, `publication_state` or `reprocessing_required` may read it, directly or by join,
and `validate_repo_db.py` asserts that as a failure. Tags are sparse by design -- an untagged row
is untagged, not a default value -- and adding one corrects nothing on the row it describes.

Origin: `Observation_Coherence_Tags` (build handoff 2026-09-08) took this shape because the
coherence framework is falsifiable and expected to churn; the evidence-directionality handoff
(2026-09-15, Signal Advisor) confirmed the same shape as the standing pattern for tags that are
not expected to churn either, when `Observation_Directionality_Tags` was built (check 13,
`core/directionality.py`). The finding behind it: H-PROCUREMENT-01 and H-LOCALRECORDS-01
independently placed buyers on the selling side of their records, which `evidence_role` has no
axis to say.

Applied to a review, not a tag (2026-09-15, Matthew Lebrecht): `Observation_Role_Reviews` (check 14,
`core/role_review.py`) holds role-classification verdicts on a stratified sample. The only verdict
writer on `Observations`, `apply_audit_verdict`, could not express a role verdict and would have set
`review_source = human` on 39 machine-reviewed rows, making their extraction read as human-cleared.
So a review whose question is narrower than the audit's lives beside the row, states its scope and
sample basis on every line, and must agree with its committed artifact -- a verdict recorded where it
can be read as more than it was is a claim nobody made.

**45. No observation is ever hard-deleted.** (Matthew Lebrecht, standing rule, 2026-09-15.) An observation found to
be bad keeps its row and its id; its invalidity is a determination appended to `Observation_Validity_History`
(`core/validity.py`, check 15) -- one row per determination, forward-only `superseded_by`, the discipline of the SEC
reporting-status history. Anything citing the observation stays structurally valid and points at something flagged
invalid rather than at nothing. The table sits behind the convention 41 wall like the other observation overlays.
A row deleted before the rule is restored exactly through `core/db.py::restore_observation` and then recorded.

The rule is retroactive and covers every removal path. **Retirement is invalidation:** a row a run no longer produces
is recorded `invalidated_not_reproduced` (`core/validity.py::invalidate_unreproduced`, within the run's company scope,
human-reviewed rows held), not removed; the delete-and-rewrite harnesses reconcile in place and then call it. A
reviewer's `unsupported` or `wrong_entity` verdict is a determination too. Every `core/db.py` delete path refuses.
Mechanically: check 15 fails on any retired id whose claim has no live row, and on `delete_rows(` in `core/db.py`.
A retired id whose claim IS live under a newer id (pre-convention-43 renumbering) is not a deletion of evidence and is
not restored -- restoring it would give one claim two ids. Its row records the id the claim now carries
(`Observation_Ids.current_id`, Matthew Lebrecht, 2026-09-15), so a claim's history is traceable across the
renumbering; check 15 fails if that is missing or wrong. A determination is permanent: no status reinstates a row.

**An invalid row is read as invalid, and every count reports three measurements** (Matthew Lebrecht, 2026-09-15).
Composition, published coverage and the reconciler exclude an invalid observation from what they compute, and each
count they publish -- derivation evidence, observation totals, coverage beside the rows it rests on, the run summary's
proposed rows, the gap report's companies -- states total, valid and invalid separately, so an exclusion is seen, not
a number that quietly shrank. This amends the convention 41 wall rather than removing it: those three modules read
validity only through `core/validity.py::invalid_observation_ids` (the reconciler only in `sync_observations`), no
other gate module reads it, and validity feeds no review_status, audit_verdict, publication_state or
reprocessing_required. A re-proposed invalid row is left exactly as recorded, because refreshing it would overwrite the
evidence its determination describes. Audit artifacts are historical records: a count an artifact recorded is what
was true on its audit date and is never rewritten or quoted as a live figure; live numbers are recomputed by the
scripts. Before the change every published number it could move was measured, and the before/after is in CLAUDE.md.

Origin: seven H-FIRSTPARTY-01 rows judged `unsupported` for a page-furniture theme match were hard-deleted on
2026-09-15 (commit 9641128), leaving 12 immutable Company_State_History rows citing observations that no longer
existed and a deleted claim that an unchanged harness run would re-insert under its old id. O00303 was converted the
same day; Matthew then made the rule retroactive over all retirements, and the other six, O00604, O00612 and O00564
were restored and recorded, and every deleting path withdrawn, the same day.

