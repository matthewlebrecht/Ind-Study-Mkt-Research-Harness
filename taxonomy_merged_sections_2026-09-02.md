# signal_taxonomy.md — Merge-Ready Sections (2026-09-02)

Supersedes `taxonomy_patch_2026-08-31*.md` and v2/v3. **These sections are renumbered for
the actual document and are ready to append as-is.**

## Why the numbering changed — read before merging

The earlier patches numbered themselves §2.4, §4.6, §7, §8, §9, §10. That was written
against an assumed section-numbered document. **The real `signal_taxonomy.md` numbers its
evidence families 1–18.** So the old numbers collide directly:

| Old patch section | Would collide with |
|---|---|
| §2.4 | Family 2, financial & capital allocation |
| §4.6 (`instrument_class`) | Family 4, employee experience |
| §7 (registry) | Family 7, procurement & contracting |
| §8 (trade press rules) | Family 8, physical footprint |
| §9 (vendor rules) | Family 9, safety & environmental |

A reference to "§4.6" would have been ambiguous between the bias dimension and signal type
4f. That, rather than renumbering as such, is the real hazard that made attended merge the
right call — good instinct to hold it.

**Resolution: families keep 1–18 untouched. New cross-cutting sections take 19+.** Nothing
existing moves, so no cross-reference in the repo breaks. Append-only, as ruled.

| Was | Is now |
|---|---|
| §2.4 Channels are not families | **§19** |
| §4.6 `instrument_class` | **§20** (20.1–20.6) |
| §4.7 `retrospective_reach` | **§21** (21.1–21.4) |
| §7 Signal_Types registry | **§22** (22.1–22.7) |
| §8 H-TRADEPRESS-01 rules | **§23** |
| §9 H-VENDOR-01 rules | **§24** |
| §10 Theme vocabulary lock | **§25** |
| Gap-report amendment | **§26** |

All internal cross-references below are already rewritten to the new numbers. The
`Signal_Types` registry already carries `instrument_class`, so nothing in §20/§22 changes
what's applied — only where it's written down.

## Also required: two Legend entries

The Legend defines the five original dimensions. Append these two:

> - **Instrument class** — IC1–IC4. Whether the instrument is *capable of observing the
>   thing being looked for*, as distinct from how attributable a claim is once observed.
>   Governs what an *absence* of signal licenses. See §20.
> - **Retrospective reach** — `current_only` / `bounded` / `archival`. How far back a
>   source can speak. Scored per source, not per harness. Gates before instrument class in
>   any historical composition. See §21.

## One correction to fold into the existing text

Family 3 note reads "3a is already built and already the project's single highest-value
family." Still true for *presence* evidence. But H-JOBPOST-01's realized reach is
`current_only` (§21.2) and its coverage is bounded by client-side rendering, so the note
should not be read as licensing absence claims. Suggest appending: *"Presence-strong,
absence-weak — see §21.3."*

---

## NEW §19 — Channels are not families

**Rule.** Evidence family is determined by *who makes the claim*, not by *where the claim
surfaced*. A publication venue is a delivery channel. A single channel may carry
observations into multiple evidence families with different evidence roles.

**Corollary — extraction is per-claim, not per-document.** One artifact may yield several
observations at different families, roles, and reliability grades.

**Instances.**

- **Trade press** (H-TRADEPRESS-01) — carries family 15 exec articulation, `buyer_acts`
  behavioral reports, and reclassified first-party announcements.
- **Vendor marketing** (H-VENDOR-01) — carries family 6 buyer articulation, `buyer_acts`
  deployment facts, and `provider_market_responds` vendor framing.

**Precedent.** Consistent with the locked harness many-to-many: one `harness_id` writes
Observations across multiple evidence families via `Harness_Sources`. This section states
the reader-side version of the same rule so it does not have to be re-derived per harness.

---

## NEW §20 — Dimension 6: instrument bias class (`instrument_class`)

**Locked 2026-08-31.** Scored **per signal type**, not per harness — a single harness may
span several classes (H-TRADEPRESS-01 spans IC1–IC3). Taxonomy dimension only; no DB column
at this time. Schema question deferred to Harness Advisor if it becomes filterable.

**What it measures.** Whether the instrument is *capable of observing the thing being
looked for*. Distinct from reliability, which measures how attributable a claim is once
observed.

| Code | Name | Description | Examples |
|---|---|---|---|
| IC1 | `curated_interested` | Published by a party with an interest in the impression created. Selection bias toward wins. | Company announcements, vendor case studies, contributed columns, seller discourse benchmark |
| IC2 | `third_party_characterization` | Published by a party not interested in the transaction, but selecting for newsworthiness. | Journalist profiles and features, analyst coverage |
| IC3 | `revealed_behavior` | Byproduct of operating, not addressed to an audience. Hard to game. | Job postings, building permits, FMCSA, procurement records |
| IC4 | `involuntary_disclosure` | Published over the subject's likely preference. | OSHA, EPA ECHO, legal filings, employee reviews |

### §20.1 Negative-inference rule (governance)

`instrument_class` governs what **absence** of signal licenses. This is the operative content of
the dimension; the code by itself is inert.

| Class | Inference licensed by absence |
|---|---|
| IC1 | **None.** Absence is not evidence of absence. Presence is evidence of presence, discounted for puffery. |
| IC2 | Very weak evidence of absence. |
| IC3 | Weak-to-moderate, conditional on demonstrated coverage of that company by the source. |
| IC4 | Moderate, conditional on coverage and on the source's reporting threshold. |

**Reporting rule.** A divergence resting solely on absence in an IC1 instrument is
**formally untested**, not a weak finding, and is reported as open pending an IC3 or IC4
instrument. Every confidence claim in the report cites the class of the instrument the
claim rests on.

### §20.2 Orthogonality to reliability

The axes are independent and both are required:

| Signal type | Reliability | `instrument_class` |
|---|---|---|
| Contributed exec column | High — attribution unambiguous | IC1 — worst |
| FMCSA safety record | Moderate | IC3 — good |

Reliability answers *can we trust the attribution of what we found*. `instrument_class` answers
*could this instrument have found it at all*.

### §20.3 Disambiguation from `signal_class`

`signal_class` is a **different field on the same registry rows** and holds something else.
`instrument_class` is the bias axis and nothing else. A reader who conflates the two will
misread every confidence claim in the report, because the negative-inference rule in §20.1
keys on `instrument_class` alone.

*Pending: the definition of `signal_class` is not recorded here — supply it and this note
gets sharpened against the actual confusion rather than the general one.*

### §20.4 Refused instruments

§20.1 governs absence of signal from a **functioning** instrument. An instrument that was
built, ran, and was refused is not covered by it and licenses **no inference at all**,
independent of class. See the `ACCESS_BOUNDED` gap-report status.

The three states below are distinct and must not share a flag:

| State | Meaning | Recoverable | Counts toward ACCESS_BOUNDED |
|---|---|---|---|
| Source refusal | 403, robots, paywall | No | **Yes** |
| Rate limit | Throughput ceiling | Yes — pacing | No |
| Egress block | Our own network config | Yes — config | No |

### §20.5 Class sets the ceiling; coverage sets the value

`instrument_class` bounds the negative inference available from a signal type. It does not
deliver it. The realized value is the class ceiling **discounted by the source's structural
coverage of the specific company**.

IC4 is therefore not a license. Worked example — `ST-DOCKET` is IC4, ceiling "moderate,"
realized "very weak," because federal dockets miss state-court matters and commercial
contracts routinely compel private arbitration. Worked example — `FMCSA` absence for an
entity below the reporting threshold is `entity_below_threshold`, not `absent_confirmed`,
and licenses nothing.

**Requirement.** Every source carries a **structural coverage denominator**: how many of the
108 the source can see *at all*, recorded separately from how many it returned data for.
Absence is only interpretable against that denominator.

### §20.6 Reachability test — not a taxonomy dimension

Reachability is **harness state, not taxonomy**. It is volatile — robots.txt changes,
paywalls move, rate limits shift — and a dimension that goes stale between sessions is worse
than none, because it gets trusted. It lives in the observation-level access flag and in the
`ACCESS_BOUNDED` status.

What is stable enough to record per signal type is the test that predicts it:

> A signal type is reachable when **(a)** either the subject or the state has an incentive to
> publish it, **and (b)** no intermediary between subject and reader has an incentive to
> enclose it.

Both conditions required. Condition (b) is the one that is usually forgotten and it is why
`instrument_class` does not predict access: an executive posting to LinkedIn is a subject
maximally motivated to be read, and the post is refused anyway.

| Source | (a) publication incentive | (b) no enclosing intermediary | Predicted | Observed |
|---|---|---|---|---|
| Own-domain careers pages | Subject — needs applicants | Self-hosted | Reachable | Reachable |
| WARN, permits, OSHA, EPA | State | None | Reachable | Reachable |
| Granicus / Legistar | State | Present but contractually suppressed | Reachable | *pending* |
| LinkedIn exec posts | Subject | Present, strong | Refused | Refused |
| Glassdoor, Indeed | Subject (reviewer) | Present — content *is* the product | Refused | Refused |
| Paywalled trade press | Publisher | Is the enclosing party | Refused | Refused |

**Known limit of the test.** It predicts *permission*, not *retrievability*. H-JOBPOST-01
passes both conditions and is still partly uncollectable because client-side rendering hides
the content from a plain fetch. Permission and retrieval are separate failures and should be
recorded separately.

---

## NEW §21 — Dimension 7: `retrospective_reach`

**Per source, not per harness** — the same grain rule as `instrument_class`. H-PROCUREMENT-01
alone spans two values (see §21.2).

**Why this qualifies as a dimension where reachability did not.** §20.6 kept reachability out
of the taxonomy because it is volatile — robots.txt changes between sessions. Retention policy
is not volatile. A court keeps dockets permanently; FMCSA's window is set by regulation. Reach
is stable enough to score and freeze.

| Value | Meaning |
|---|---|
| `current_only` | Shows present state. No dated history. Cannot speak to any past bucket. |
| `bounded` | Fixed retention window. Speaks to buckets inside it, nothing before. |
| `archival` | Durable dated record. Speaks to any bucket within the source's existence. |

### §21.1 Nominal vs. realized reach

Reach carries the same split as `instrument_class` in §20.5: **the source sets the ceiling,
our access sets the realized value.**

A paywalled trade archive is `archival` nominal and `current_only` realized, because the
archive exists and we cannot enter it. Record both. Composing on nominal reach overclaims by
exactly the size of the access gap.

Special case — **`ST-REMOVEDPAGE` is bounded by *our* crawl window, not the source's.** It is
derived from differencing our own captures, so its reach began when we started crawling and
cannot be extended backwards by any means. Record it as `bounded (self-referential)`.

### §21.2 Reach is per source, and harnesses are mixed

| Harness | Source | Reach | Confidence |
|---|---|---|---|
| H-PROCUREMENT-01 | USASpending awards | `archival` | High |
| H-PROCUREMENT-01 | SAM.gov registration status | `current_only` | High |
| H-FIRSTPARTY-01 | Dated newsroom / press archive | `archival` | High |
| H-FIRSTPARTY-01 | Current site state | `current_only` | High |
| H-JOBPOST-01 | Own-domain careers pages | **`current_only`** | High |
| H-PATENTS-01 | PatentsView | `archival` (≈18mo publication lag) | High |
| H-FEDLEGAL-01 | CourtListener dockets | `archival` | High |
| H-FEDLEGAL-01 | NLRB | `archival` (`out_of_theme`) | High |
| H-SAFETY-ENV-01 | OSHA inspections | `archival` | Medium — verify retention |
| H-SAFETY-ENV-01 | EPA ECHO compliance detail | `bounded` | Medium — verify window |
| H-LOCALRECORDS-01 | Granicus / Legistar minutes | `archival` | Medium — verify per platform |
| H-PERMITS-01 | County permits / assessor | `bounded`, **county-dependent** | Low — varies by jurisdiction |
| — | FMCSA SMS | `bounded` (rolling window) | Medium — verify window length |
| — | State AG breach portals | `bounded`–`archival`, **state-dependent** | Low — varies by statute |
| — | SEC EDGAR / 8-K | `archival` | High |
| — | WARN notices | `archival` | Medium — verify per state |
| H-TRADEPRESS-01 | Trade outlets | `archival` nominal / **`current_only` realized** | High |
| H-TRADEPRESS-01 | LinkedIn | moot — `access_bounded` | High |
| H-VENDOR-01 | Vendor case studies | `current_only` (undated, silently revised) | Medium |
| — | `ST-REMOVEDPAGE` | `bounded (self-referential)` | High |

Low- and medium-confidence rows are classifications I have reasoned to, not verified. They
should be confirmed against the sources before the schema freezes on them.

### §21.3 Composition rule — reach gates before class

For any historical bucket **T**, evaluate in this order. The order is the whole point.

1. **Reach gate.** Does the source's *realized* reach cover T? If no, the source is **null for
   T** — not quiet, not weak evidence, not anything. Stop here.
2. **Access gate.** Was the source accessible to us during T? If no, **null for T**. Access
   state must be stored per bucket, not as a current value (§20.4).
3. **Class rule.** Only now does `instrument_class` govern what silence means, per §20.1.

**Null is not zero.** A `current_only` source contributes nothing to Q1 2025 rather than
contributing an absence. Any implementation that stores these the same way will manufacture
staleness signal out of sources that were never able to speak.

**Highest-risk composition in the portfolio: H-JOBPOST-01.** It is IC3 — the class whose
silence is *supposed* to carry weight — paired with `current_only`, the reach that can say
nothing about the past. Composed naively it will license historical conclusions it has no
capacity to support. It is the source most likely to produce a confident wrong answer.

### §21.4 Snapshot retention — decide now, cannot be decided later

A `current_only` source becomes `bounded` **prospectively** if captures are retained. Begin
snapshot retention immediately for every `current_only` source — careers pages above all.

This is the only recommendation in this patch with a deadline attached: every week without
retention is a week of history permanently unrecoverable. Six months of retained job-post
captures converts the portfolio's most dangerous source into a usable longitudinal one. Six
months of not retaining leaves it `current_only` forever.

---

## NEW §22 — Signal_Types registry

Fields: `signal_type_id` | `signal_type_name` | `evidence_family` | `instrument_class` |
`status`.

`signal_type_id` uses the mnemonic vocabulary shared with the locked signal-type-first
harness convention `H-{SIGNAL_TYPE}-{NN}`, so the registry can serve as the authority for
the outstanding naming reconciliation. **IDs below are proposed, not locked**, pending that
reconciliation.

### §22.1 `status` vocabulary — five values

The Week 2 carried items were hard to resolve because `status` had no vocabulary for a type
that is real but produces nothing. It does now. This is a vocabulary gap, **not** a registry
schema gap — no new field is needed.

| Status | Meaning | Enters denominators? |
|---|---|---|
| `active` | Produces observations against a theme | Yes |
| `routing_only` | Valid type that reclassifies to another type and writes nothing of its own | No |
| `out_of_theme` | Reachable, produces real data, data does not bear on any modernization theme | No |
| `access_bounded` | Registered, built, ran, refused | No |
| `reference` | Produces roster or keying data consumed by other harnesses, not evidence | No |

**Hard rule.** Only `active` types enter any denominator — coverage fractions, yield rates,
`instrument_class` share, ACCESS_BOUNDED calculations. A registered-but-silent type that
leaks into a denominator dilutes every metric it touches.

Types with a non-`active` status still carry `instrument_class` **except** `reference` types,
which carry reliability but no class — see §22.4.

### Seed — trade press (H-TRADEPRESS-01)

| signal_type_id | signal_type_name | evidence_family | instrument_class | status |
|---|---|---|---|---|
| ST-EXECQUOTE-REPORTED | Exec quote in reported trade article | 15 | IC2 | active |
| ST-EXECCOLUMN | Bylined / contributed exec column | 15 | IC1 | active |
| ST-EXECPANEL | Panel / conference / keynote coverage | 15 | IC2 | active |
| ST-PRESSPROFILE | Journalist profile or feature | varies | IC2 | active |
| ST-WIREREPRINT | Reprinted press release (routing class) | per H-FIRSTPARTY-01 | IC1 | routing_only |

Note on ST-EXECQUOTE-REPORTED: the *speech* is volunteered by the exec but the *topic* is
elicited by a reporter and the publication decision is the outlet's, so it scores IC2 rather
than IC1 despite being first-party speech. This is the single most valuable articulation
type currently available and the crawl should weight toward it.

ST-WIREREPRINT is a routing class, not a terminal signal type — see §23.2.

### Seed — vendor case studies (H-VENDOR-01)

| signal_type_id | signal_type_name | evidence_family | instrument_class | status |
|---|---|---|---|---|
| ST-VENDORQUOTE | Buyer quote in vendor case study | 6 | IC1 | active |
| ST-VENDORDEPLOY | Deployment fact asserted in vendor case study | 6 | IC1 | active |
| ST-VENDORFRAMING | Vendor characterization of buyer demand | 6 | IC1 | active |

### §22.2 Week 2 carried types — resolved 2026-09-02

| signal_type_id | instrument_class | status | Ruling |
|---|---|---|---|
| ST-NLRB | IC4 | `out_of_theme` | Real IC4 instrument, family 13. Register it — the registry records what was considered and set aside, not only what is live. Excluded from all denominators. Pre-scoped if a labour/workforce theme is ever opened. |
| ST-LINKEDINPOST | IC1 | `access_bounded` | Class confirmed. Reachability is a separate axis and it fails the §20.6 test. See §22.3 |
| ST-DOCKET | IC4 | `active` | Class confirmed; negative inference realized at **very weak**, not the IC4 ceiling. See §20.5 |
| ST-REMOVEDPAGE | IC3 | `active`, corroboration-gated | See §22.5 |
| ST-EXECID | — (none) | `reference` | Not a signal type. See §22.4 |
| ST-EXECCOLUMN | IC1 | `active` | Grade **held at full**. See §22.6 |

### §22.3 ST-LINKEDINPOST — class and reachability are separate findings

IC1 is correct and the logged reasoning stands: self-published, topic chosen by the speaker,
framing fully subject-controlled, absence licenses nothing, does not count toward closing the
articulation-bias gap.

That is independent of whether it can be collected. Under §20.6 LinkedIn fails condition (b)
— an enclosing intermediary overrides the subject's intent to be read — and 8 of 8 URLs were
refused on 2026-09-01. Allowlisting a domain on our side does not make a source willing.

**Both are true at once and neither cancels the other.** This is the first type-level
`ACCESS_BOUNDED` case and it should be reported as one rather than sitting as an active type
with no output. Even fully reachable it would be IC1 and would not widen articulation.

### §22.4 ST-EXECID is reference data, not a signal type

Executive identification populates the roster that H-EXECVOICE-01 and others key against. It
observes no theme and bears on no divergence. It therefore takes **no `instrument_class`**.

Scoring it IC1 would be actively harmful: it inflates the portfolio's IC1 share and makes the
instrument-bias problem read as worse than it is, off a type that carries no evidence weight
at all.

It does carry **reliability**, and at high stakes — a wrong executive name silently poisons
every downstream H-EXECVOICE-01 query. This split is itself the cleanest demonstration of
§20.2: the two axes are independent, and here one applies while the other does not.

### §22.5 ST-REMOVEDPAGE — IC3, and its confounder is correlated with the theme

**IC3, not IC4.** IC4 requires publication by another party over the subject's preference — a
regulator, a court, a former employee. Removal is the subject *exercising* control, not losing
it. That the removal is detectable is an artifact of our crawl differencing, not of any
compulsion. It is revealed behavior.

**Corroboration gate.** A `removed_page` event may never carry a standalone observation. It
may only raise `signal_strength` on an existing observation or flag for manual review.

The reason is a confounder that is not independent of what we are measuring: the most common
benign cause of mass page removal is a site migration or CMS replacement — which is *itself a
modernization event*. A company modernizing its web estate emits a flood of removals that
read as discontinuations. The noise is correlated with the signal, which is the one condition
under which a low-grade instrument becomes worse than no instrument.

### §22.6 ST-EXECCOLUMN — grade held at full

A bylined column by a named executive is **maximally attributable**: signed, published under
their name, legally attributable to them. Reliability grades attribution. Full grade.

The instinct to cap it is a bias objection wearing a reliability costume — the pre-§20 habit
of smuggling instrument bias into the reliability score because there was nowhere else to put
it. There is somewhere else now: the column is IC1, the worst class, and §20.1 already
strips its absence of any inferential force. Capping reliability as well would penalize the
same defect twice and corrupt the axis §20.2 depends on.

**Narrow exception.** Cap one grade where the byline is corporate rather than personal — "the
[Company] team," an unnamed contributor, or an explicitly ghostwritten piece. Named
individual byline takes full grade.

### §22.7 Registry hygiene

`ST-EXECQUOTE-REPORTED` scores IC2 despite being first-party speech, because the topic is
elicited by a reporter and the publication decision is the outlet's. Recorded here because it
looks like an error on inspection and will be "corrected" by someone otherwise.

---

## NEW §23 — H-TRADEPRESS-01 extraction rules

Sources: Construction Dive, Transport Topics, FleetOwner, Food Dive, MedTech Dive and
comparable verticals.

### §23.1 Role and grade by type

| Signal type | Evidence role | Reliability |
|---|---|---|
| ST-EXECQUOTE-REPORTED | `buyer_articulates` | Full |
| ST-EXECCOLUMN | `buyer_articulates` | Full |
| ST-EXECPANEL | `buyer_articulates` | Capped −1 (paraphrase of spoken remarks) |
| ST-PRESSPROFILE | `buyer_acts` **only** | Capped −1 |

**ST-PRESSPROFILE splits at the artifact level.** Where the journalist reports a concrete
action — deployed X, hired Y, opened Z — the journalist is a witness to behavior and the
claim is admissible as `buyer_acts`. Where the journalist *characterizes* the company's
posture, the claim is context only and generates no observation.

**Hard rule: ST-PRESSPROFILE never carries `buyer_articulates`.** Journalist
characterization is not company speech and admitting it would inflate the articulation leg
the harness exists to widen.

### §23.2 Wire reprint handling — reclassify, do not exclude

Reprinted press releases are **routed, not filtered**. Excluding them at extraction makes
them invisible and silently drops their contribution to `signal_strength`, contrary to the
locked redundancy decision.

1. On wire-marker detection, reclassify the observation to first-party — family and role per
   H-FIRSTPARTY-01. Do not discard.
2. Run the normal redundancy check.
   - Already held by H-FIRSTPARTY-01 → `suppressed_redundant` in governance, **still counts
     toward `signal_strength`**.
   - Not held → genuinely new first-party evidence, admitted. Common in the Anvil-100, where
     firms frequently wire a release without posting it to their own site.
3. Reclassified observations never count toward trade press articulation yield.

**Marker grading.**

| Marker | Weight |
|---|---|
| PRNewswire / BusinessWire / GlobeNewswire byline | Conclusive alone |
| Explicit "press release" label | Conclusive alone |
| "About [Company]" boilerplate footer | **Not conclusive alone** — fires only with no reporter byline |

Boilerplate is appended to reported articles routinely; treating it as conclusive would
misroute genuine reported coverage into first-party.

---

## NEW §24 — H-VENDOR-01 extraction rules

Family 6 (vendor/partner disclosure) locked previously. Roles resolved here.

### §24.1 Multi-role artifact

| Component | Role | Grade |
|---|---|---|
| Buyer quote (ST-VENDORQUOTE) | `buyer_articulates` | Capped −1 vs ST-EXECQUOTE-REPORTED |
| Deployment described (ST-VENDORDEPLOY) | `buyer_acts` | Full |
| Vendor framing of demand (ST-VENDORFRAMING) | `provider_market_responds` | Full |

The buyer quote is capped because vendor marketing typically composes it and obtains
approval rather than transcribing it. The **deployment fact is the strongest leg**, not the
weakest: named-customer deployment claims are checkable and carry legal exposure, so vendors
do not fabricate them.

`provider_market_responds` is reserved for the vendor's own assertions. A buyer speaking in
a vendor venue is still the buyer speaking.

### §24.2 Attribution gate

ST-VENDORQUOTE requires a **named individual with a title**. Anonymous attributions — "a
spokesperson," "an IT Director at [Company]" — drop out of the articulation role entirely.
Retain the ST-VENDORDEPLOY fact; discard the quote.

### §24.3 Accounting rule

H-VENDOR-01 is IC1 throughout and **does not count as progress against the
articulation-bias gap**, whatever its yield. Record it as volume, not as widening.

---

## NEW §26 — Gap report status (amendment)

Supersedes the prior "flag as weakest findings" handling of the two absence-based
divergences.

| Divergence | Prior status | New status | Testable against |
|---|---|---|---|
| Cloud migration | Weak finding | **Formally untested** — IC1 absence | Job postings (IC3): legacy-stack and migration language in requisitions |
| Cybersecurity / OT | Weak finding | **Formally untested** — IC1 absence | State AG breach-notification portals (IC4); 8-K Item 1.05 for the public subset (IC4) |

Per §20.1, absence in an IC1 instrument licenses no negative inference. Both are reported
as open pending an IC3/IC4 instrument rather than as weak findings.

Candidate sources listed are **referred, not specced**. Harness feasibility is Harness
Advisor's call; no scoping done on this side.

---

## NEW §25 — Theme vocabulary lock

### §25.1 The identifier is not the risk

The stated worry is renames and free-text drift splitting a company's history into two
unrelated series. That risk is real and it is the cheap one to fix:

> **Separate the stable identifier from the mutable label.** Themes carry opaque IDs
> (`THEME-04`) that never change. Human-readable names are a display attribute and may be
> edited freely. A rename then costs nothing, and a *split* is forced to be explicit because
> it requires minting a new ID.

The expensive risk is the one that survives this fix: **a theme whose definition drifts while
its identifier holds.** That corrupts a series without splitting it, and unlike a split it
leaves no trace. Freezing the string is not enough — freeze the written definition and version
it, so a definition change is a visible event.

### §25.2 Detectability start dates

Three themes flipped `buyer_detectable=True` on 2026-08-31. Before that date the project held
no buyer-side instrument for them, so the evidence history is **null, not empty**.

Every theme therefore carries a `buyer_detectable_since` date, and buckets before it are
excluded from the series rather than recorded as zero. Without this, the three flipped themes
will read as a clean absence across every historical bucket — a manufactured finding that
looks like exactly the divergence pattern the project is built to detect.

Same failure mode as §21.3. Missing capacity to observe must never be stored as an observed
absence.

### §25.3 Per-theme instrument profile

For the temporal schema's negative inference to compose, each theme records which instrument
classes can see it at all:

| Theme property | Why the schema needs it |
|---|---|
| Classes with an active instrument | A theme visible only through IC1 has quiet that licenses nothing, ever |
| Evidence roles available | `legacy_constraint` is now `buyer_acts`-only — absence of articulation is structural, not a finding |
| `buyer_detectable_since` | Per §25.2 |

### §25.4 Definition-boundary requirement

Adjacent themes must have written boundaries before freeze, or observations will route
inconsistently across sessions and the inconsistency will be invisible afterward. Boundaries
required at minimum between `workforce enablement` and (a) `legacy_constraint`, both
observable in the same requisition text, and (b) labour friction, which is `out_of_theme` per
§22.2 and sits close enough to be confused with it.

---
