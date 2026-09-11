# signal_taxonomy.md — Patch 2026-08-31 (Rev 2)

Drop-in sections. Section numbers are proposals; renumber on merge. Nothing here changes
an existing lock — §2.4 formalizes a rule already implicit in the harness many-to-many, and
§4.6 adds a dimension without touching the existing five.

> **Rev 2 change (2026-08-31, Matthew):** the bias axis is renamed from `signal_class` to
> **`instrument_class`**, codes `SC1`–`SC4` renamed to **`IC1`–`IC4`**. Rev 1 recorded
> `signal_class` as "confirmed free and unlocked." It is not free: the Signal_Types
> registry stub built 2026-08-27 already defines `signal_class` as **evidence vs.
> prerequisite** — the distinction that lets `H-EXECID-01` exist as a prerequisite harness
> with a null evidence family. That meaning is retained unchanged. Rev 1's own §4.6.3
> warned this field name was generic enough to be quietly redefined; this rev is that
> warning being honored rather than overridden. No other rulings changed.

---

## NEW §2.4 — Channels are not families

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

## NEW §4.6 — Dimension 6: instrument bias class (`instrument_class`)

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

### §4.6.1 Negative-inference rule (governance)

`instrument_class` governs what **absence** of signal licenses. This is the operative
content of the dimension; the code by itself is inert.

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

**Access caveat (added Rev 2).** Absence licenses nothing at all — regardless of class —
when the instrument was never permitted to run. An IC4 source that returns zero because it
is closed to compliant collection is not a measurement. See the H-EMPREVIEW-01 access
finding: family 4 is an IC4 instrument whose two primary sources disallow automated
collection, so its zero is an access outcome, not an observation. Distinguish
`access_blocked` from `absent_confirmed` in any inference drawn from silence.

### §4.6.2 Orthogonality to reliability

The axes are independent and both are required:

| Signal type | Reliability | `instrument_class` |
|---|---|---|
| Contributed exec column | High — attribution unambiguous | IC1 — worst |
| FMCSA safety record | Moderate | IC3 — good |

Reliability answers *can we trust the attribution of what we found*. `instrument_class`
answers *could this instrument have found it at all*.

### §4.6.3 Field-name discipline

Two adjacent fields exist and are **not** interchangeable. Neither may be inferred from a
registry header without reading this section.

| Field | Meaning | Values | Locked |
|---|---|---|---|
| `signal_class` | Whether a signal type yields evidence or is a prerequisite enabling other harnesses. Evidence family is nullable when `prerequisite`. | `evidence` / `prerequisite` | 2026-08-27 |
| `instrument_class` | Instrument bias class — whether the instrument can observe the thing at all. Governs negative inference per §4.6.1. | `IC1`–`IC4` | 2026-08-31 |

`H-EXECID-01` is the canonical `prerequisite` case: it produces no evidence family, only
`Company_Executives` rows that other harnesses consume. Do not collapse these two fields;
Rev 1 of this patch attempted to, which is how the distinction came to be written down
explicitly.

---

## NEW §7 — Signal_Types registry

Fields: `signal_type_id` | `signal_type_name` | `evidence_family` | `signal_class` |
`instrument_class` | `status`.

`signal_type_id` uses the mnemonic vocabulary shared with the locked signal-type-first
harness convention `H-{SIGNAL_TYPE}-{NN}`, so the registry can serve as the authority for
the outstanding naming reconciliation. **IDs below are proposed, not locked**, pending that
reconciliation.

`signal_class` is populated per the 2026-08-27 definition (evidence vs. prerequisite). All
seed types below are `evidence`; the existing registry entry for executive identification
remains `prerequisite`.

### Seed — trade press (H-TRADEPRESS-01)

| signal_type_id | signal_type_name | evidence_family | signal_class | instrument_class | status |
|---|---|---|---|---|---|
| ST-EXECQUOTE-REPORTED | Exec quote in reported trade article | 15 | evidence | IC2 | active |
| ST-EXECCOLUMN | Bylined / contributed exec column | 15 | evidence | IC1 | active |
| ST-EXECPANEL | Panel / conference / keynote coverage | 15 | evidence | IC2 | active |
| ST-PRESSPROFILE | Journalist profile or feature | varies | evidence | IC2 | active |
| ST-WIREREPRINT | Reprinted press release (routing class) | per H-FIRSTPARTY-01 | evidence | IC1 | routing_only |

Note on ST-EXECQUOTE-REPORTED: the *speech* is volunteered by the exec but the *topic* is
elicited by a reporter and the publication decision is the outlet's, so it scores IC2 rather
than IC1 despite being first-party speech. This is the single most valuable articulation
type currently available and the crawl should weight toward it.

ST-WIREREPRINT is a routing class, not a terminal signal type — see §8.2.

### Seed — vendor case studies (H-VENDOR-01)

| signal_type_id | signal_type_name | evidence_family | signal_class | instrument_class | status |
|---|---|---|---|---|---|
| ST-VENDORQUOTE | Buyer quote in vendor case study | 6 | evidence | IC1 | active |
| ST-VENDORDEPLOY | Deployment fact asserted in vendor case study | 6 | evidence | IC1 | active |
| ST-VENDORFRAMING | Vendor characterization of buyer demand | 6 | evidence | IC1 | active |

---

## NEW §8 — H-TRADEPRESS-01 extraction rules

Sources: Construction Dive, Transport Topics, FleetOwner, Food Dive, MedTech Dive and
comparable verticals.

### §8.1 Role and grade by type

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

### §8.2 Wire reprint handling — reclassify, do not exclude

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

## NEW §9 — H-VENDOR-01 extraction rules

Family 6 (vendor/partner disclosure) locked previously. Roles resolved here.

### §9.1 Multi-role artifact

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

### §9.2 Attribution gate

ST-VENDORQUOTE requires a **named individual with a title**. Anonymous attributions — "a
spokesperson," "an IT Director at [Company]" — drop out of the articulation role entirely.
Retain the ST-VENDORDEPLOY fact; discard the quote.

### §9.3 Accounting rule

H-VENDOR-01 is IC1 throughout and **does not count as progress against the
articulation-bias gap**, whatever its yield. Record it as volume, not as widening.

---

## AMENDMENT — gap report status

Supersedes the prior "flag as weakest findings" handling of the two absence-based
divergences. **APPROVED by Matthew 2026-08-31.** This reverses a handling decision confirmed
earlier the same day and changes what the gap report claims: the Week 2 gap report has zero
supported divergences, not two weak ones. Recorded in the Notion Revision Log; belongs in
`DECISIONS.md` once seeded, and `gap_report.py` still prints the old framing and needs
updating in the next attended session.

| Divergence | Prior status | New status | Testable against |
|---|---|---|---|
| Cloud migration | Weak finding | **Formally untested** — IC1 absence | Job postings (IC3): legacy-stack and migration language in requisitions |
| Cybersecurity / OT | Weak finding | **Formally untested** — IC1 absence | State AG breach-notification portals (IC4); 8-K Item 1.05 for the public subset (IC4) |

Per §4.6.1, absence in an IC1 instrument licenses no negative inference. Both are reported
as open pending an IC3/IC4 instrument rather than as weak findings.

Candidate sources listed are **referred, not specced**. Harness feasibility is Harness
Advisor's call; no scoping done on this side.

**Note (Rev 2):** the cloud-migration test names job postings, and `H-JOBPOST-01` already
exists with collected data. Confirm whether this is a re-query against existing rows before
scoping it as new harness work.
