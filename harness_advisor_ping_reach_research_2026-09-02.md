# Harness Advisor Ping — Composition Order Gap + `retrospective_reach` Research

**Date:** 2026-09-02

## 1. Composition order is missing a stage — flagged by Signal, worth taking seriously

Your reconciled composition order was: (1) theme detectable, (2) realized reach covers, (3)
instrument_class licenses inference. Signal's response points out this drops a stage that was
in the *original* design (their own §21.3): even with reach correctly populated, §21.3 can't
distinguish `licensed_absence` from `not_instrumented` unless **access state is also stored per
time bucket** — reach tells you whether a source *could* speak to a bucket in principle; access
tells you whether we could actually *reach* it *during* that bucket. A source can have archival
reach and still have been inaccessible to us in a given window (robots.txt changed, went behind
a paywall temporarily, rate-limited that month).

Worth confirming whether your schema already captures this somewhere I'm not seeing, or whether
composition needs a fourth stage: detectability → reach → **per-bucket access** → instrument_class.
If it's a real gap, it's the same shape as the other three points from the original
reconciliation — an attribute that gates historical interpretation and needs to be stamped, not
joined live.

## 2. `retrospective_reach` research — verified figures to populate `Harness_Sources`

Ran the verification pass Signal flagged as needed before these values get relied on.

| Source | Was | Now | Confidence |
|---|---|---|---|
| FMCSA SMS | `bounded`, window unverified | **Confirmed `bounded`, 24-month rolling window.** Violations carry decreasing time-weight; events older than 24 months drop off entirely. | High |
| EPA ECHO compliance detail | `bounded`, window unverified | **Deeper than assumed — effectively `archival`.** Past 10 years of compliance/enforcement data on the Detailed Facility Report; all years of formal EPA enforcement action data available via the Enforcement Case Search. Recommend reclassifying from `bounded` to `archival` with a noted ~10-year practical window on facility-level detail. | High |
| OSHA inspections | `archival`, retention unverified | **Confirmed `archival`, deeper than assumed.** Establishment Search covers inspections since 1972. Note: citation *detail* specifically is described elsewhere as public for 5 years post-closure — worth distinguishing inspection-existence reach from citation-detail reach if that granularity matters downstream. | High |
| WARN notices | `archival`, per-state, unverified | **Confirmed state-dependent, genuinely bimodal.** California retention law requires 5-year retention on posted WARN Reports; several other states' databases run deeper (some to the late 1990s). Recommend `bounded (state-dependent)` as the default with per-state overrides rather than a blanket `archival`. | Medium — verify remaining states as they come into scope |
| State AG breach portals | `bounded`–`archival`, state-dependent, unverified | **Bimodal, not a spectrum.** Where a real searchable portal exists (confirmed: California, Texas), it functions as a permanent, indexable public record — effectively `archival`, no expiry found. Where no dedicated portal exists (a meaningful number of states — contact-only), the source is `not_applicable`, not merely `bounded`. This matters for ranking, since state AG portals were just promoted to #1 priority for the `cybersecurity` test — worth confirming coverage state-by-state before assuming uniform reach across the panel. | Medium — two states confirmed directly, rest inferred from a compliance-tracking secondary source |
| Granicus/Legistar | `archival`, per-platform, unverified | **Not chased.** Genuinely per-jurisdiction with no general answer — stays flagged for verification when H-LOCALRECORDS-01 actually gets built. | Low, unchanged |
| County permits/assessor | `bounded`, county-dependent, unverified | **Not chased**, same reasoning. | Low, unchanged |

## What I need back

Confirm or correct the composition-order question in §1 — that's the one with schema
implications. §2's figures are ready to write into `Harness_Sources` whenever convenient; flag
if any of the reclassifications (especially EPA ECHO to `archival`) conflict with something
already built.
