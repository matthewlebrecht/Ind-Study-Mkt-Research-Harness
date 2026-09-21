# Open items at close of build — 2026-09-20

Everything still open, with its disposition. Written for the final pass before report writing, so a
reader can tell at a glance what is **finished**, what is **deliberately parked**, and what is
**waiting on Matthew specifically**. Nothing here is guessed at: judgments that belong to the
reviewer are flagged, not made.

---

## A. Waiting on Matthew — judgment, not work

These cannot be closed by anyone else: an audit verdict and a role verdict are human-sourced by
construction (`review_source = human`; check 14 enforces it for role reviews).

| # | Item | Size | State |
|---|---|---|---|
| ~~A1~~ | ~~H-FIRSTPARTY-01 v1.3 audit~~ | 30 rows | **CLOSED 2026-09-20.** Matthew judged all 30 `supported`; artifact written, version published, coverage 97.2% now quoted |
| A2 | **Business-journal role census** — `ROLE_REVIEW_business_journal_census_2026-09-15.md` | 7 rows | Drawn 2026-09-15, unjudged. The stratum's earlier estimate rests entirely on rows now recorded invalid, so this census is what replaces it |
| ~~A3~~ | ~~O00530 — Front Line identity~~ | 1 row | **CLOSED 2026-09-20.** Judged `supported`: the row stands as written |
| A4 | **Composition provenance — option A/B/C/D** | design | `docs/analysis/brief_composition_provenance_2026-09-20.md`. Recommendation is A for this submission |
| A5 | **Coherence pilot — four decisions** | design | `docs/diagnostics/coherence_pilot_execution_2026-09-15.md` §6. Disposition already written for the report appendix (not executed); the decisions matter only if it is ever revived |

## B. Parked deliberately, with the reason recorded

| # | Item | Why it is parked |
|---|---|---|
| B1 | **H-EXECID-01 v1.1 unaudited** (HR-0064, quarantined) | It wrote 117 `Company_Executives` rows, not observations, so the gate's sampler — which samples `Observations` — does not fit it. Meanwhile published H-EXECVOICE-01 v1.6 *reads* its low-grade names. Real and known (item 16); auditing it needs a sampler that can draw from `Company_Executives`, which is a build, not a judgment |
| B2 | **H-EMPREVIEW-01 has no published version** (4 quarantined runs) | Its finding is an access finding: 107 of 108 `access_blocked`. Publishing it would make a 0.9% coverage line quotable, and one of the four runs (HR-0058) is an offline replay whose failure categories are cache artifacts. `set_version_publication` moves every run of a version together, so publishing v1.1 would publish that run too. **A real design question, not a quick fix** |
| B3 | **H-TRADEPRESS-01 v1.7 quarantined** (HR-0067, 0 rows) | Publishing it would move the harness's quoted coverage from v1.6's 158-company denominator to v1.7's **8-company** one, because published coverage quotes the latest published version. Left quarantined deliberately: the 8-company completion run is real, but it is not the harness's coverage |
| B4 | **H-VENDOR-01 v1.0 quarantined** (HR-0062, HR-0063) | Session 17's recorded decision: v1.0's zero was *not* an absence (two name-test defects, a wrong entity, a client-rendered page). Left quarantined so the zero is never read as a measurement |
| B5 | **H-SEC8K-01 v1.0 quarantined** (HR-0073) | Permanently, by decision: stale 3-company scope including SpartanNash after deregistration. v1.1 is the published one |
| B6 | **H-EXECVOICE-01 v1.4 quarantined** (HR-0042, 1 row) | Its single row, O00564, is recorded `invalidated_not_reproduced`. It cannot be marked `superseded` (check 9 requires a superseded version to hold no observations) and should not be published (that would release an invalid row). Quarantine is the correct terminal state |
| B7 | **H-FMCSA-01 emits no attempts** | Logged as a documented limitation, not retrofitted (Matthew, 2026-09-17): `docs/report_appendix_reliability.md` §1 |
| B8 | **Nine undecided gates; three SAFETY-ENV items** | `docs/diagnostics/gate_inventory_2026-09-03.md`. Unchanged in code; each is a policy call |
| B9 | **EXECVOICE soft-404 regex corrupted** | `harnesses/h_execvoice_01/harness.py:129` holds literal backspace bytes where `\b` was meant, so the "404 … not found" branch cannot match. Found 2026-09-15, deliberately not bundled into another change; fixing it means a new version and a re-run |
| B10 | **H-FIRSTPARTY-01 role handling** | The harness hard-codes `buyer_articulates`; no classification-time signal separates the one business-journal miss from the rows judged correct. Options reported 2026-09-15, nothing built |

## C. Closed in this pass

| Item | Resolution |
|---|---|
| **Quarantined runs that resolve mechanically** | 13 → 9. H-TRADEPRESS-01 v1.5 aligned (published on one run, quarantined on another — same version, same audit). H-PRODUCTQUALITY-01 v1.0 and v1.3 and H-TRADEPRESS-01 v1.4 marked `superseded`: each holds 0 observations and is earlier than a published version whose run re-ran its scope. No coverage figure moved |
| **Misnamed-artifact warning** | `__verdicts.json` declared a sidecar in `core/audit.py` — it is the judged input an artifact is built from, not a misnamed artifact |
| **Grandfathered `reason` texts inaccurate** | Not rewritten (they are dated statements about what was audited). Each entry now carries `population_at_exemption`, and the file carries a note explaining why 7 of 18 populations have moved |
| **REVIEW_QUEUE_2026-09-06 "re-ruling requested"** | Resolved: O00603 is `accepted` / `supported`; O00604 is recorded `invalidated_extraction_defect` (2026-09-15). Nothing outstanding on that sheet |
| **Front Line trio** | Narrowed from 3 rows to 1 (A3 above) |
| **The 8 overstated HR-0083 statuses** | Superseded 2026-09-17: 6 `invalidated_wrong_entity`, 2 `invalidated_not_reproduced` |
| **Grandfathered structural hole** | Closed 2026-09-17: check 9 honours an exemption only for versions whose published runs all predate its `date_added` |
| **Composition de-duplication** | Measured 2026-09-17: has not fired and cannot as the code stands (0 of 5,400 derived rows change when attempt order is reversed). Only provenance remains — A4 |

## D. Standing state

- **8 quarantined runs**, all with a recorded disposition above (B1–B6).
- **6 superseded versions**, each asserting nothing live is held — enforced by check 9.
- **53 published versions**: 37 audited, 16 grandfathered.
- **722 observations**: 719 released (611 valid, 108 invalid), 3 quarantined — **every valid row is
  now released**, and the only quarantined rows left are the 3 restored rows that are themselves
  recorded invalid.
- **One review sheet remains unjudged**: the business-journal role census (A2, 7 rows). Its verdict
  vocabulary is `correct` / `buyer_acts` / …, not `supported`, so it is not covered by an audit
  verdict and was deliberately not inferred.
