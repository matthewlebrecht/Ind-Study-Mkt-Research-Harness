# Report appendix — instruments scoped and not built

Final dispositions for the report appendix. Each entry says what was built, what was measured, and
why the instrument stops where it does. **Decided by Matthew Lebrecht: A and B on 2026-09-16, C on 2026-09-17.** **All three re-verified against the
workbook on 2026-09-20 and unchanged** -- A's cohort arithmetic (38 released `systems_integration`
rows, 6 invalid, over-firing 3 companies on released rows and 2 on valid, 36 of 38 low-grade), B's
25-of-108 and 5-consumer counts, and C's 58-of-108. The numbers are
reproducible by the script or diagnostic named in each entry; where a number is dated, it is the
state on that date.

---

## A. Coherence-framework pilot

**Disposition: framework built and scoped; insufficient evidence volume to execute meaningfully.
Not executed. No tag writer built; no reduced test run.**

### What was built

- The framework reference data, loaded verbatim and validated: 46 taxonomy rows — 22 dimensions
  (COH-D01..D22), 19 failure families (COH-F01..F19), 5 reference-only generative forces — and 127
  family-to-dimension mappings (`Coherence_Framework_Taxonomy`, `Coherence_Family_Dimensions`).
- An overlay table for observation-level tags (`Observation_Coherence_Tags`), kept separate from the
  evidence table and walled off from every module that computes an audit or publication decision
  (`validate_repo_db.py` check 11).
- The pilot's cohort: companies whose `systems_integration` evidence fires three or more times
  ("over-firing"), each matched to a comparison company by closest total observation count
  (`Coherence_Pilot_Runs`, pilot COHP-0001, `scripts/coherence_pilot.py`). Hypothesis:
  *systems_integration over-firing correlates with COH-F failure-family tags.* Exploratory success
  criterion: at least 60% of the over-firing cohort sharing a failure-family candidate, visibly above
  the comparison cohort; no significance test, by design.

### Why it was not executed

**The cohort is too small for the criterion to discriminate, and it shrank under the project's own
quality controls.** When the cohort was assembled (2026-09-08) three companies cleared the floor. By
2026-09-15, after the extraction-defect review recorded 111 observations invalid across the portfolio,
6 of the 38 released `systems_integration` observations were among them — and one of the three
over-firing companies (Mack Group) had two of its three. On valid evidence alone the cohort is
**two companies**.

At that size the 60% criterion resolves to *two of three* or *two of two*: a single tagging judgment
about a single company decides whether the pilot passes. That is not a test of the hypothesis; it is a
reading of one company. A further 36 of the 38 observations were admitted at the extractor's lowest
evidence grade, so the "over-firing" the pilot targets is almost entirely the weakest tier of
evidence.

Two smaller facts point the same way: the committed cohort had already drifted from what the same
script derives today (one comparison company differs, because total observation counts moved as later
instruments published), and the hypothesis is stated in failure families while tagging is defined
over dimensions, with the dimension-to-family synthesis procedure never specified.

### What it would take

A materially larger over-firing cohort — either more `systems_integration` evidence, or a lower floor
with the cohort then stated to be dominated by low-grade evidence — plus a written tagging procedure
and a tag writer. None is justified at current evidence volume.

Source: `docs/diagnostics/coherence_pilot_execution_2026-09-15.md`.

---

## B. App-store presence as digital telemetry

**Disposition: reported as a feasibility finding. No harness built** — the one segment where the
signal means what it appears to mean is five companies, which does not justify an instrument this
close to the deadline.

### What was measured (2026-09-15, all 108 buyers)

A feasibility probe (`scripts/probe_appstore.py`) queried Apple's public search API for every buyer
and corroborated each hit against the publisher's own website. No evidence row was written.

- **25 of 108 companies publish at least one app of their own (59 apps).**
- **Only 5 publish anything a consumer uses.** All four direct-sales consumer-goods companies have
  their own app — doTERRA (7), Melaleuca (6), Scentsy (2), 4Life (1) — and they are the only
  companies in the population that ship consumer *commerce* apps; three of the four also ship a
  separate distributor-facing app. SpartanNash adds 13 through its grocery and pharmacy banners.
- **The other 20 publish workforce, operations or business-customer tooling** — driver and shipper
  apps (nine carriers: Crete, Estes, R+L, Prime, C.R. England, Southeastern Freight, PS Logistics,
  OnTrac, Anderson Trucking), construction field apps (Whiting-Turner, Teichert, Phillips, HITT),
  supply-chain and equipment operations (Penske Logistics, UniGroup, Midmark, Duke Manufacturing,
  Co-Diagnostics), and B2B ordering or advisory tools (Nicholas and Company, J.R. Simplot). App-store
  presence therefore measures two different things in this population, and would have to be split
  into two signals if it were ever instrumented.
- **A dated maintenance signal is visible where one exists:** SpartanNash's six pharmacy apps were
  last updated 2023-02-23 while its grocery banner apps were updated in August 2026.

### Why identity was most of the work

Matching on company name reproduced the project's characteristic failure immediately. The probe's
first pass admitted a fitness club published by an unrelated "Walsh Group", a Marietta seafood
restaurant under "Cajun Inc", and an email client under "The NFI Group LLC", and it would have
matched Mack Trucks to Mack Group and a Moroccan parcel carrier to Western Express. Corroborating on
the publisher's own domain refused all of them — and also recovered a true match a name rule must
refuse (Prime Inc., which publishes under its legal name, New Prime Inc). Of 29 mechanical matches, 4
were refuted on inspection.

### If it were ever built

Google Play would be the better primary source: its robots.txt permits search, its results are in the
served HTML, and its package names carry the publisher's domain (`com.doterra.shop`). The instrument
could only ever assert presence — an app-store search index is a discovery surface, not a registry,
so no app found is not evidence of no app.

Source: `docs/diagnostics/appstore_feasibility_2026-09-15.md`.

---

## C. YouTube channel presence

**Disposition: confirmed non-signal. No harness built.** Presence is broad and cleanly measurable,
and it is *not* a duplicate of the executive-voice instrument — but a content-level check found no
buyer-side modernization evidence at all, at two depths.

### Access shaped the method

`youtube.com/robots.txt` disallows, for every crawler, **`/results`** (search), **`/youtubei/`** (the
internal API the site's own pages call), captions and the video feeds. Channel pages, their `/videos`
tab and `/watch` pages are not disallowed. So no company was looked up by searching YouTube; the
probe re-reads robots.txt at start and refuses to run if either closed path ever opens.

Discovery instead read each company's **own homepage**, as already archived by the executive-
identification harness — no new fetch — for links to YouTube. That is also the stronger identity
direction: a channel the company links from its own site is its channel by the company's own
statement.

### Presence: 58 of 108 companies

Of 108 homepages, 63 carry a YouTube link. Resolved: **52 channels confirmed by name score, 6 more
confirmed by hand** where the channel title defeats token scoring (`RyconConstruction`, `PetersenInc`,
`WalbridgeGroup`, `Simplot Company` vs "J.R. Simplot", `Averitt` vs "Averitt Express", `RL Carriers`
vs "R+L"). Two links were embedded videos or a literal `embed/VIDEO_ID` template placeholder, two were
site-theme placeholders.

**One was refused, and it is the case worth keeping:** Wadsworth Brothers' own site links to *Slider
Revolution* — a WordPress slider plugin's channel, left in the theme. Site-linking alone is therefore
not identity; the channel still has to be about the company.

45 of the 58 channels posted within the last year; 6 are dormant three years or more.

### The content check — the reason for the disposition

Presence alone would not settle this, so the content was read at two depths.

- **1,457 recent video titles** across the 58 channels. Eight matched a modernization theme under the
  project's topic spine, and **none is a buyer-side statement**: one is a false positive (Walsh's
  "Red-Purple Modernization" is the name of a Chicago transit construction project), and the other
  seven are companies describing services they **sell** — Penske Logistics' and PLS's transport
  management offerings, Black & Veatch's OT-cybersecurity and grid-modernization services, Kenco's
  materials-handling analytics.
- **60 full video descriptions**, the five newest from each of the twelve most recently active
  channels. 52 carried a description. **Zero matched any theme**, at either the strong or the
  low-grade tier.

What these channels actually post is recruiting and people content, project progress, safety and
community. Across the six newest titles per channel, recruiting/people (43) and project showcase (40)
dominate. The nearest thing to a signal is workforce — which the job-postings harness already reads,
from a source that makes a clearer claim.

### It is not an executive-voice duplicate, and that does not rescue it

Against the executive-voice harness's latest run, **19 of the 58 channel companies are ones it cannot
reach at all** (no primary executive identified), and only 6 are companies where it holds evidence.
Six channels carry video titles naming an identified executive, and none of those six is a company it
has evidence for. A company's own channel is also **first-party** content — the announcements
harness's family — not the third-party coverage the executive-voice instrument reads.

So the overlap objection fails; the instrument is not redundant. It simply does not carry the signal
the project is looking for, which is the stronger reason not to build it.

### If it were ever revisited

It would measure presence and posting cadence reliably, and nothing else. It could assert no absence:
search is closed, so a homepage without a link proves nothing about whether a channel exists.
LinkedIn, X/Twitter and Meta were not probed — settled out separately.

Source: `docs/diagnostics/youtube_feasibility_2026-09-16.md`.
