# Session 18 — 2026-09-15 (evening)

Ten items were handed over. **Four were already done** by work that landed after this afternoon's
brief was written, and saying so is part of the result. Five produced substantive findings. One —
the coherence pilot — could not produce the result asked for, and why is the finding.

Nothing was judged on Matthew's behalf. Two review sheets are drawn and unjudged; no observation was
released, invalidated, or deleted.

Step 0 checks ran before and after everything: `validate_repo_db.py` 15 of 15, `check_run_ledger.py`
clean, no committed row lost.

---

## Items already complete before tonight

| # | Item | State |
|---|---|---|
| 3 | Extraction-defect fix — three prerequisites | **Five** prerequisites, all built and verified on the 111 cached pages; v1.3 ran as HR-0083. Continued tonight by drawing its audit (below) |
| 4 | O00349 alongside O00529 | Both recorded: O00349 `invalidated_wrong_entity` (OVH-0011), O00529 `invalidated_extraction_defect` (OVH-0007) |
| 6 | `Observation_Validity_History` | Built; 111 determinations; O00303 converted (OVH-0001); the `Company_State_History` citations surface as check 15 warnings, which is the designed behaviour — derivations are immutable history |
| 8 | H-SEC8K-01 HR-0080 | Audited and published as v1.1; artifact `H-SEC8K-01__v1.1.json` exists. HR-0073 stays permanently quarantined |

---

## 1 — App-store feasibility, consumer-goods segment

`docs/diagnostics/appstore_feasibility_2026-09-15.md`, `scripts/probe_appstore.py`. A probe, not a
harness: no workbook row written.

**The answer is "a real but narrow segment", and the boundary is not where the question assumed.**

- **All four direct-sales consumer-goods companies have their own app**: doTERRA 7, Melaleuca 6,
  Scentsy 2, 4Life 1. They are the **only** companies in the 108 that publish consumer *commerce*
  apps, and three of them ship a second, distributor-facing tier.
- SpartanNash adds **13** through its grocery banners — the largest footprint in the population.
- **25 of 108 companies have a confirmed footprint (59 apps), but only 5 publish anything a consumer
  uses.** The other 20 publish workforce tooling: driver apps, construction field-safety apps,
  supply-chain ops. If this is ever scoped, those are two signals and must not share a key.
- A reading worth more than presence: SpartanNash's six **pharmacy** apps were last updated
  **2023-02-23** while its six grocery banner apps were updated **August 2026** — a dated
  abandonment pattern inside one company's portfolio.

**Identity was the whole job, and the probe's first pass failed the project's characteristic failure
three times in one run** — "Sun Oaks" (a fitness club) under a different *Walsh Group*, a Marietta
seafood restaurant under *Cajun Inc*, an email client under *The NFI Group LLC*. Corroborating on the
publisher's own domain refuses all three, refuses Mack Trucks for Mack Group and the Moroccan Western
Express, and **rescues** `Prime Mobile` — published by *New Prime Inc*, which is Prime Inc.'s legal
name and which convention 11 must otherwise refuse. Name-only matches are now held as candidates, not
counted; the 14 that arose are adjudicated in the diagnostic (10 confirmed, 4 refuted).

**Google Play should be the primary leg** if it is ever built: robots.txt permits `/store/search`, the
app ids are in the server-rendered HTML with no JavaScript, and the package namespace
(`com.doterra.shop`, `com.scentsy.home.prod`) is stronger identity than Apple's `sellerName`.

PRESENCE ONLY: a store search index is a discovery surface, not a registry.

## 2 — Coherence pilot: the test cannot return a result

`docs/diagnostics/coherence_pilot_execution_2026-09-15.md`. Three blockers, and the one that matters
is not the obvious one.

1. `Observation_Coherence_Tags` holds **0 rows** and there is **no writer** — the only overlay table
   in the project without one.
2. The hypothesis is stated in **COH-F**; the table accepts only **COH-D**. Reaching families means
   tagging dimensions and joining through `Coherence_Family_Dimensions` — a procedure never written
   down.
3. **The cohort does not survive the validity determinations.** Of 38 released `systems_integration`
   rows, 6 are invalid. C0002 Mack Group holds 3, of which 2 are invalid — so the over-firing cohort
   is **3 companies on released rows and 2 on valid rows**. COHP-0001 has also drifted: it records
   A019 as A048's comparison; the script now derives A032.

At that size the 60% threshold resolves to **2 of 3, or 2 of 2** — one tagging judgment on one
company decides the outcome, and 36 of the 38 rows are low-grade. Tagging the 66 cohort observations
to run that test is not worth doing. Four decisions are listed for Matthew, beginning with whether
the pilot counts invalid rows (today it does, because it may not read validity).

## 3 — Extraction defect: continued into the audit

The fix is done and run. Its consequence is that **HR-0083 is quarantined and publishes no coverage
number until audited**, so the audit was drawn: `H-FIRSTPARTY-01__v1.3__review.md`, a **census of all
30 rows** — the population is small enough that the random control is the whole run, making the
precision rate exact rather than extrapolated. O00307, the press-release bullet the fix recovered, is
row 1. Unjudged.

While drawing it, a reviewer-facing defect: the sheet told the reviewer an `unsupported` verdict means
**"Exclude the row"**, which convention 45 forbade this morning. A reviewer following it would have
asked for a deletion the code now refuses. Corrected — and the correction itself tripped the
convention 41 wall (naming the validity table in prose, inside a gate module), which was fixed by
complying rather than by exempting the module.

## 5 / item 12 — The business-journal review collapsed to 7 rows, and the old estimate is void

The ask was a full review of the remaining 34. Drawn from the base after HR-0083, **that population is
7**.

Of 41 business-journal `buyer_articulates` rows: **34 now carry a validity determination, 7 do not**.
And **every one of the 7 rows judged in the first role review is among the invalidated** — O00303, the
single miss, included.

**So the stratum's estimate — 1 of 8, 12.5%, 95% upper bound 18 of 42 — rests on no valid row and
must not be quoted again without saying so.** That bound was the basis for "up to 17 of its 34
unreviewed rows could be misclassified"; it no longer has an evidentiary basis.

The 7 valid rows (5 released, 2 quarantined at v1.3) are drawn as a **census**:
`ROLE_REVIEW_business_journal_census_2026-09-15.md`. Verdicts are human-only, so none is assigned.
`scripts/role_review_sheet.py` gained `--sub-kind-contains`, `--exclude-invalid`, `--exclude-reviewed`
and `--stem`, so a second pass is drawn from the current base rather than re-judging rows for a role
they no longer support; every filter and the ids it dropped print on the sheet.

## 7 — Directionality backfill re-run: 37, not 36

The guard refused the whole batch rather than writing part of it, which is what it is for. The 37th
row is **O00791** (Goodfellow Bros, PROCUREMENT v1.4, published hours after the batch was restated) —
a genuine prime-award row of exactly the kind the finding covers.

Written: **70 tags**, 1 appended and 69 matched and left as-is. Same run id and same `tagged_at`,
because the batch is defined by the finding's rule rather than by a snapshot and the date has not
changed. The guard still refuses anything other than 37 + 33. Check 13 passes.

Worth recording as behaviour, not a bug: rows those harnesses write from now on are **not** tagged
automatically, so this will recur every time a covered version publishes.

## 9 — FMCSA field mappings: the recorded blocker was half wrong, and hid a real bug

The note carried since 2026-09-06 said the QCMobile record has no entity-type field and reports
`Interstate` instead of the authority type. **Both fields are in the record**; they were read from the
wrong keys.

The consequential half: for-hire authority was derived from `allowedToOperate`, which is the **USDOT
registration status**. Midmark has `allowedToOperate = "Y"` and holds no for-hire authority, so the
QCMobile path asserted **AUTHORIZED** where SAFER reports **NOT AUTHORIZED** — collapsing exactly the
private-versus-for-hire distinction `_is_private_carriage` exists to protect. Authority lives in
`commonAuthorityStatus` / `contractAuthorityStatus` / `brokerAuthorityStatus`; entity type is
`censusTypeId.censusTypeDesc`.

**Measured live against the 8 committed carrier rows: `operating_authority_status` now agrees 8 of
8**, all four private-carriage registrants included. Two differences remain and are properties of the
sources, not parse bugs — QCMobile's `censusTypeDesc` is single-valued where SAFER composes
`CARRIER/SHIPPER/BROKER` (4 of 8 differ; a pure broker has no `censusTypeId`), and SAFER names the
authority **scope** where QCMobile names the **kind** (4 of 8 differ).

**So the original conclusion stands for a different reason:** a live QCMobile run would still hold all
20 reviewed rows as conflicts. No version committed, no row changed. `core/tests/test_fmcsa_qcmobile.py`
(15 checks) pins the mappings and the remaining gap.

**Open for Matthew:** keep SAFER authoritative for those two fields while QCMobile serves the numerics
(a hybrid, one extra fetch per carrier), or accept QCMobile's coarser vocabulary through
`--refresh-reviewed`. A policy call, not a code gap.

## 10 / item 13 — H-PRODUCTQUALITY-01 diagnosed

`docs/diagnostics/productquality_attempts_control_2026-09-15.md`.

It is **not** writing zero rows across 108. Its denominator is a 15-company hand-seeded population
map and its yield is **3 of 15**; the 93 `not_covered` are a documented convention 6 decision.

**The published coverage rate is the length of that map.** It reads **0.1389** and 15/108 =
**0.13889**; the four earlier runs read 0.1204 with 13 in the map. It moves when a company is added
and at no other time, and carries no information about whether any federal database was read.

No observation-side control can exist: the gate samples rows that were *written*, so the 3 easy
positives are audited while the **12 `absent_confirmed`** — the instrument's only substantive claims
— and the **93 population decisions** have never been sampled. The control must sample `Attempts`,
and it must ask two different questions with different verdicts rather than one pooled precision rate.

Answered mechanically tonight: the map's justification comment is stale (it says `industry_primary` is
blank for all Anvil rows; session 15 populated 68). But **the map must not be rebuilt from that
field** — 4LIFE reads `construction`, Simplot and SpartanNash read `logistics`, and Scentsy,
Co-Diagnostics and doTERRA are blank, so a rebuilt map would drop four of the five companies the
instrument exists for. Cross-checked, exactly **one** company is product-making by `industry_primary`
and absent from the map: **A027 Petersen Inc.**

## Items 11–13 (lower priority)

Not started, as instructed: grandfathered version drift, composition de-duplication/provenance
(verified still open against HEAD this afternoon), portfolio visualisation.

---

## What needs Matthew

1. **Two drawn sheets, unjudged** — the v1.3 audit census (30 rows) and the business-journal role
   census (7 rows).
2. **FMCSA**: hybrid source, or accept QCMobile's vocabulary via `--refresh-reviewed`.
3. **Coherence pilot**: four decisions, starting with whether it counts invalid rows — and whether a
   2-of-2 test is worth building a writer for.
4. **The 8 overstated invalidation statuses** from HR-0083 (carried from this afternoon, unchanged).
5. **The business-journal bound** should be withdrawn from any write-up that currently quotes it.
