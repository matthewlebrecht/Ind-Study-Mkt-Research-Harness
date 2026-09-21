# H-PRODUCTQUALITY-01 — why it writes ~zero rows, and why nothing can audit that

Diagnosis only. No code changed, no row written. Open item 13.

---

## 1. It is not writing zero rows across 108 companies. Its denominator is 15.

The harness carries a **hand-seeded population map** (`harnesses/h_productquality_01/harness.py:76`)
naming the 15 buyers that federal recall / adverse-event databases actually cover — medical device,
food, consumer. Every company not in that map is recorded `not_covered` with the reason *"outside
this instrument's population"*, never queried.

Latest run HR-0055, 108 attempts:

| outcome | n | meaning |
|---|---|---|
| `not_covered` | 93 | outside the population map — never queried |
| `absent_confirmed` | 12 | queried, 0 records resolved to the company |
| `covered` | 3 | a record resolved — the 3 observations (Midmark, Mack Group, Merit Medical) |

So the instrument's real yield is **3 of 15**, not 3 of 108. That part is working as designed and the
design is right: convention 6 says a confirmed absence needs the source to be complete *for the
signal*, and a device database is not complete for a general contractor. The harness already removed
A025 in 2026-09-01 for exactly that reason.

## 2. The published coverage rate measures the map, not the source

`Harness_Runs.coverage_rate` for the last four runs is **0.1389**. The population map holds **15 of
108 companies = 0.13889**. The four runs before that read 0.1204 — and the map held 13.

**The coverage rate is arithmetically identical to the size of the hand-seeded map.** It moves when a
company is added to the map and at no other time. It carries no information about whether any
federal database was successfully queried, whether the identity test worked, or whether an absence is
real. Anyone reading 13.89% as instrument performance is reading the length of a list.

## 3. Why no control exists, and why an observation-side one cannot be built

The audit gate samples **rows that were written**. This harness has written 3 (plus 2 earlier
low-grade). So:

- the 3 `covered` rows have been audited and released — and they are the easy cases, the ones where a
  record was found and matched;
- the **12 `absent_confirmed`** attempts are the harness's actual substantive claims — *"this device
  maker / food company has no federal recall record"* — and **no audit has ever sampled one**, because
  they are attempts, not observations;
- the **93 `not_covered`** decisions are claims too — *"this company is outside the population"* — and
  nothing has ever checked them either.

An observation-side control cannot reach either class. The control has to sample **attempts**.

## 4. The two questions an attempts-side control must ask — they are different questions

| Stratum | n | Question | Verdicts |
|---|---|---|---|
| `absent_confirmed` | 12 | Did the query really run, against the right database, under a name that would have matched? | `absence confirmed` / `a record exists` (instrument miss) / `wrong database for this firm` |
| `not_covered` | 93 | Is this company correctly outside the population? | `correctly out of population` / `should be in the population` (map miss) |

These need different evidence and should not be pooled into one precision rate. The second is the
undecided gate **P2–P4** ("population map") in `docs/diagnostics/gate_inventory_2026-09-03.md`.

## 5. First pass at the map question, answered mechanically today

The map's own justification comment says it is hand-seeded because *"`Companies.industry_primary` is
blank for all 100 Anvil rows"*. **That is now stale** — session 15 populated `industry_primary` for 68
companies. So the map can, for the first time, be cross-checked against independent data.

Cross-checking every buyer whose `industry_primary` is `manufacturing`, `food` or `medical` against
the map:

- **exactly one** company is product-making by `industry_primary` and absent from the map:
  **A027 Petersen Inc.** (`manufacturing`, from 3 OSHA inspections). Petersen is a Utah industrial
  fabricator — pressure vessels and defence structures — so it is very likely correctly out, but it
  is the one name a reviewer should confirm.
- **the map should NOT be rebuilt from `industry_primary`.** On the companies that matter most to
  this instrument the enrichment is wrong: **4LIFE reads `construction`** (off a single ECHO facility
  code — already flagged in CLAUDE.md as worth a second look), **J.R. Simplot** and **SpartanNash**
  read `logistics`, and Scentsy, Co-Diagnostics and doTERRA are blank. A map rebuilt from that field
  would drop four of the five companies the instrument exists for.

So the hand-seeding decision survives the cross-check — but for a better reason than the stale comment
gives, and the comment should be updated to say so.

## 6. Two population questions the code already flags and nobody has answered

Both are written in the map as open questions, not oversights:

- **C0003 Duke Manufacturing** is mapped `consumer` and queried against CPSC. Duke makes *commercial
  foodservice* equipment, which is not a consumer product — so CPSC may be the **wrong** instrument
  rather than an incomplete one. If it is wrong, Duke's zero means nothing and the honest record is
  `not_covered`. It is currently one of the 12 absences.
- **A010 / A057 / A059** (4Life, Melaleuca, doTERRA) sell ingestible supplements and were originally
  queried against CPSC only; openFDA food enforcement was added 2026-09-01. That correction is the
  precedent showing this class of error is real and was caught once already.

## 7. Recommendation

Build the attempts-side control as **two separate sheets**, not one:

1. a **census of the 12 `absent_confirmed`** — small enough to be a census, and it is where the
   instrument's only real claims live;
2. a **sample of the 93 `not_covered`**, plus the named candidate A027, asking only the population
   question.

Neither needs new harness code — both read `Attempts`. Until one exists, H-PRODUCTQUALITY-01's
absences are unverified, and its coverage rate should not be quoted as an instrument measurement at
all.
