# Signal Advisor — Theme Vocabulary Confirmation (2026-09-02)

> **CORRECTION, 2026-09-03 (Matthew's call, session 9 brief item 5).** This document
> confirms the set of **nine** themes as complete, and all nine are supported. The tenth
> theme, `ot_modernization` (THEME-10), was minted by the split this document itself
> recommends in §1 (option A) and was decided later on 2026-09-02; it is not an addition
> to the vocabulary this document reviewed, it is the outcome of the review. There is no
> contradiction between item 1 of the summary ("set of nine complete") and item 2 ("split
> before freeze"): the freeze was at nine, the split produced ten, and both are as
> intended. The "nine → ten tension" flagged in `session6_report.md` §4 and carried in
> `session7_report.md` §5 is retracted; nothing in it needs a decision.

Reviewed `core/topics.py` and `signal_taxonomy.md`. **The set of nine is confirmed complete
and nothing pending on my side adds a theme.** Freeze at nine.

But three of the nine are not in a freezable state yet, and one of them is a defect I'd want
fixed today rather than frozen and lived with. Also: I have to correct something I've been
saying for two sessions.

---

## 0. Correction — `legacy_constraint` is not a theme

I've been calling it one since 9/1. It isn't. It's an **`organizational_state` value**
(`legacy_constraint` / `active_transition` / `target_state`), assigned per company × theme.
The taxonomy doc has it right in the H-EXECVOICE-01 notes; I read it as a theme and
propagated the error.

The correction makes the family 4 problem **worse, not smaller**, so it needs restating:

> Family 4 going dark did not remove the instrument for one theme. It removed the
> portfolio's only *inside-the-company articulation* instrument for detecting the
> `legacy_constraint` **state across all nine themes**.

And it lands directly on the temporal schema, since `Company_State_History` stores
`organizational_state` per company × theme over time. The remaining instruments that can
assign a state are dominated by IC1 announcements, and announcements report progress, not
the estate that forced it. So the state series will skew toward `active_transition` and
`target_state` **systematically, in every theme, at every time bucket** — not as noise but
as a directional bias baked into the table's primary value.

That belongs in the temporal schema design brief, not just here.

---

## 1. The blocking defect: `cybersecurity_ot` is mislabelled, not just compound

I flagged this yesterday as a split candidate on general grounds. Having read the patterns,
it's more specific than that.

The theme is labelled "cybersecurity and OT/IT convergence." Its patterns are:

`cyber ?security` · `OT security` · `IT/OT` · `zero trust` · `ransomware` ·
`security (posture|assessment|operations)` · `NIST` · `CMMC`

**Every one of those is a security term.** There is no pattern for SCADA, PLC, ICS, DCS,
historian, control system, HMI, industrial network, or plant-floor connectivity. OT
*modernization* — replacing twenty-year-old plant control systems, which is a central
modernization story for construction, energy, food distribution and manufacturing — is
currently **invisible to the classifier** in both buyer and seller content.

The theme's name promises coverage the implementation doesn't deliver. Freezing it as-is
locks in a permanent blind spot on arguably the most physical, most industry-appropriate
modernization theme in the portfolio.

**Two acceptable resolutions. Both are fine; drifting is not.**

| Option | Action |
|---|---|
| **A — Split** (my recommendation) | `cybersecurity` keeps the current patterns. New `ot_modernization` gets control-system vocabulary. Two themes, two instrument profiles: cyber tests on breach portals and 8-K Item 1.05; OT tests on permits, capex, controls-engineer requisitions. |
| **B — Rename and narrow** | Relabel to `cybersecurity` and drop `OT` from the name. Honest, cheaper, and accepts that OT modernization is out of scope for this project. |

Option A is better because OT modernization is more visible in this company class than
cybersecurity is — it leaves physical traces, and IC1 absence on cyber is nearly total
(the file's own note says so). Splitting converts a formally-untested theme into a testable
one.

**This must be decided before the freeze.** After it, a split needs a new theme ID and the
history splits with it.

---

## 2. The finding that changes the build ranking: `BUYER_SIGNAL_TO_THEME` covers 6 of 9

The mapping has six entries. The three flipped themes — `cloud_infrastructure_migration`,
`cybersecurity_ot`, `workforce_enablement` — have **no H-JOBPOST-01 signal key at all.**

So there is no `cloud_hiring` category. H-JOBPOST-01 has never been wired to cloud
migration and structurally cannot emit into it. The cloud-migration divergence rests
entirely on H-FIRSTPARTY-01 — exactly as the docstring says, and I misread the situation
yesterday.

**This revises my 9/2 ranking call.** I said suspend H-JOBPOST-01's use as the
cloud-migration absence test on JS-rendering bias grounds. The bias reasoning stands, but
the operative fact is simpler and the fix is better:

> Adding three signal keys to H-JOBPOST-01 — cloud/infrastructure, security, and frontline
> workforce technology — gives an **IC3 instrument to all three IC1-only themes** at the
> cost of a classifier category, not a harness build.

That is the cheapest high-value change available this week, cheaper than any harness on the
ranked backlog, and it addresses the articulation-bias gap more directly than anything
below rank 3.

Two conditions on it:

- The JS-rendering coverage denominator (§21.2, §20.5) still has to be measured before any
  *absence* claim is made from the new keys. **Presence** evidence is admissible immediately.
- Buyer-side patterns live per-harness, not in `topics.py`, so this doesn't touch the
  provider-side regexes. It's additive.

---

## 3. `buyer_detectable` has stopped carrying information

All nine are now True. The flip was correct in its own terms — `gap_report.py` was printing
"NO INSTRUMENT" beside a non-zero buyer count, which is a real contradiction. But flipping
a boolean fixed the symptom, and the docstring shows it:

> *"Treat a low buyer count on these three as uninformative rather than as evidence of
> buyer silence."*

That instruction exists because the boolean can't express it. A uniformly-True field tells
`gap_report.py` nothing, and the distinction it actually needs — *an instrument exists*
versus *an instrument whose silence licenses inference exists* — is exactly what
`instrument_class` was built for.

**Recommend replacing `buyer_detectable: bool` with a per-theme instrument profile**
(§25.3): which instrument classes have an active instrument for this theme, plus
`buyer_detectable_since`. Then `gap_report.py` distinguishes three states properly rather
than two, and the three flipped themes report as **IC1-only — absence uninformative**
instead of as ordinary detectable themes carrying a prose warning nobody downstream reads.

This also kills the drift risk in the current arrangement: the per-theme `note` fields now
restate instrument-class reasoning in prose ("a first-party announcement is a BIASED
instrument… absence here means 'not announced'"). That reasoning is correct and it is
§20.1, but a second uncontrolled home for it will diverge from the taxonomy within weeks.
Notes should point at the profile, not restate it.

---

## 4. Pattern noise that manufactures divergence — `systems_integration`

Not a code review, but this is theme *definition* operationalized, so it's in scope.

`systems_integration` matches on bare `\bAPI\b` and bare `\bintegration\b`, with
`min_hits=1`. Two consequences:

**M&A false positives.** "Post-merger integration" is a routine phrase in mid-size industrial
press releases and has nothing to do with systems interoperability. Every acquisition
announcement in the Anvil-100 will classify as `systems_integration`.

**Asymmetric inflation, which is the serious one.** These patterns run on both sides of the
market. Seller content is long-form marketing prose; buyer announcements are short. A
high-frequency generic term therefore inflates the seller side substantially more than the
buyer side — **manufacturing a "sellers talk, buyers don't" divergence that is a pure
artifact of pattern breadth.** That is the exact shape of finding the project exists to
detect, produced spuriously.

`systems_integration` is the highest-risk theme in the file for a false divergence.

Lower-severity, same mechanism — single generic hits sufficient to assign a theme:

| Pattern | Problem |
|---|---|
| `\bLean\b` (case-insensitive) | Matches ordinary English "lean" |
| `\bAMR\b` | Also automated meter reading, and several company names |
| `\bAI\b` | Very high base rate in current marketing copy |
| `\bAzure\b` / `\bAWS\b` / `\bGCP\b` / `\bOracle\b` | A single vendor mention isn't a migration signal |

Suggested direction, for whoever owns the file: raise `min_hits` for themes whose patterns
include generic terms, or split patterns into a specific tier that can fire alone and a
generic tier that needs corroboration. Same structure as the corroboration gate on
`ST-REMOVEDPAGE` (§22.5), and for the same reason — noise correlated with signal.

---

## 5. `workforce_enablement` — boundary still required

Carried from yesterday, unchanged. Two boundaries before freeze:

- **vs. `organizational_state = legacy_constraint`** — both surface in the same requisition
  text. Ambiguous postings will route inconsistently across sessions, undetectably.
- **vs. labour friction** — `ST-NLRB` is `out_of_theme` (§22.2) on the grounds that labour
  friction isn't modernization. `workforce_enablement` sits close enough that the ruling
  gets quietly reopened by whoever classifies the next filing.

Its patterns are reasonably specific, so this is a written-definition task, not a pattern
repair.

---

## 6. On the lock mechanism — the file already has the right principle

The `BUYER_SIGNAL_TO_THEME` comment states it exactly:

> keys are written into committed, human-reviewed Observations, and renaming them would
> break provenance for a cosmetic gain

**That is the whole theme-lock rule, already articulated, just not applied to themes.**
`Theme.key` is already a stable string identifier and `label` is already separate. So:

- **`key` freezes.** It is the identifier of record for `Company_State_History`.
- **`label` stays free.** Rename at will; it's display.
- **A split requires a new `key`.** Never repoint an existing one.
- **`note` and the written definition get versioned**, because a definition drifting under a
  frozen key corrupts a series *without splitting it* — invisible, and worse than a split.

Structural enforcement is Harness Advisor's, but the discipline needed is already 80% present
in the file.

---

## Summary for the freeze

| # | Item | Status |
|---|---|---|
| 1 | Set of nine complete, no additions pending | **Confirmed** |
| 2 | `cybersecurity_ot` mislabelled — no OT patterns exist | **Blocking. Split or rename before freeze** — *resolved 2026-09-02: split (option A), key renamed `cybersecurity`, THEME-10 `ot_modernization` minted* |
| 3 | `workforce_enablement` boundaries | **Required before freeze** |
| 4 | `key` freezes, `label` free, split needs new key, definitions versioned | **Confirmed, ready** |
| 5 | `buyer_detectable` → per-theme instrument profile + `buyer_detectable_since` | **Recommended** |
| 6 | Three themes have no H-JOBPOST-01 signal key | **Cheapest high-value fix available** |
| 7 | `systems_integration` pattern breadth | **Refer — false-divergence risk** |
| 8 | `legacy_constraint` is a state, not a theme | **My error, corrected** |

Only item 2 blocks. Everything else can land alongside the freeze or shortly after.
