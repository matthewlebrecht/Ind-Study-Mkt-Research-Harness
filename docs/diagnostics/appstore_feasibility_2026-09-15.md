# Digital telemetry — app-store feasibility, consumer-goods segment

Feasibility probe, 2026-09-15. **No harness, no manifest, no workbook row was written**: this
answers whether an instrument is worth scoping, nothing more. Reproduce with
`python scripts/probe_appstore.py`; raw output `harness_output/appstore_probe_full.json`.

**Headline: a real but sharply bounded segment, not a clean zero — and the boundary does not fall
where "does the company have an app" falls. It falls between companies that publish a CONSUMER app
and companies that publish WORKFORCE tooling.**

---

## 1. Method, and why the identity test is most of the work

Apple's public `itunes.apple.com/search` endpoint was queried for all 108 buyers (it returns the
developer name and, usually, the developer's own website). Identity is scored with the project's own
`core/resolution.py` — same stopwords, same floor — and then corroborated:

| Tier | Test | Counted as a hit? |
|---|---|---|
| 1 | the developer's own website is the company's registrable domain | **yes — decisive** |
| 2 | the developer's distinctive token set equals the company's, no domain corroboration | **no — candidate, held for a human** |
| 3 | only the app's *title* carries the company's name | no — third-party / ecosystem app |

**The first version of this probe accepted tier 2 automatically and immediately reproduced this
project's characteristic failure — three times in one pass.** All three were refuted by reading the
app's own description:

- **A034 The Walsh Group** produced *"Sun Oaks"*, published by a different "The Walsh Group Inc":
  a fitness community app ("Not sure what time your favorite group workout is?").
- **A004 Cajun Industries** produced *"Cajun Seafood Wings & Fish — Marietta Official App"*, a
  restaurant ordering app, under "Cajun Inc".
- **A049 NFI** produced *"eMayl"*, an email client publishing from `emayl.ai`.

A fourth, **C0004 Western Express**, produced *"Colis.ma"* from `colis.ma` — a Moroccan parcel
carrier of the same trading name. A fifth, `Car Carrier - Relaxing Puzzle` by 7WARE S.R.L., scored
0.69 against **R+L Carriers** purely on the single letters R and L.

Two things the domain test got right that names alone could not: it **refused** Mack Trucks for Mack
Group and Unigroup S.p.A for UniGroup, and it **rescued** `Prime Mobile` — published by *New Prime
Inc*, which is Prime Inc.'s legal name, and which convention 11 would otherwise have to refuse.

A differing developer domain is **not** proof of a different publisher: firms ship under divisional
and brand domains. J. R. Simplot publishes from `simplotgrowersolutions.com` and SpartanNash ships
its grocery banners from `shopfamilyfare.com`. Those are name-only candidates, not third parties.

## 2. Result over the 108

| Outcome | Companies |
|---|---|
| Domain-confirmed publisher (tier 1) | **15** |
| Name-only candidates (tier 2), adjudicated by hand | 14 → **10 confirmed, 4 refuted** |
| No app found | 79 |
| **Confirmed app footprint** | **25 companies, 59 apps** |

## 3. The consumer-goods segment — the question actually asked

### Direct-sales consumer goods: 4 of 4, and the deepest footprints in the population

| Company | Apps | What they are |
|---|---|---|
| **A059 doTERRA International** | 7 | doTERRA Shop, Pro, Social, Convention 2025, Leadership Retreat 24/25, evolve |
| **A057 Melaleuca** | 6 | Melaleuca Shopping, Grow, Deals, Quick-Send, Retail Partners, Events |
| **A018 Scentsy** | 2 | Scentsy Home (consumer), Scentsy Connect (consultant-facing) |
| **A010 4LIFE** | 1 | 4Life |

**Every direct-sales company in the population has one, and they are the only companies in the whole
108 that publish consumer *commerce* apps** — Shopping and Lifestyle genre, a storefront the end
customer uses. doTERRA and Melaleuca each also ship a distributor-facing tier (Pro, Grow, Retail
Partners), so the segment shows two distinct digital products, not one.

### Other consumer-goods / food

| Company | Apps | Note |
|---|---|---|
| **A029 SpartanNash** | 13 | The largest footprint in the population — grocery banners (Family Fare, D&W Fresh Market, VG's, Dan's, Forest Hills, Fresh Madison) plus 6 pharmacy apps. Consumer-facing through its *retail banners*, not its distribution business |
| A041 J.R. Simplot | 2 | Simplot Advisor 3.0, SA3 Weather — **grower**-facing agronomy, B2B, not consumer |
| A005 Nicholas and Company | 1 | Nicco Online — B2B foodservice ordering |
| C0003 Duke Manufacturing | 1 | Sous Chef Technology — equipment control, B2B |
| A007 National Product Sales, A017 Admiral Beverage, A050 Leprino Foods | 0 | none found |

### A maintenance signal, worth more than presence

SpartanNash's **six pharmacy apps were all last updated 2023-02-23**, while its six grocery banner
apps were updated **August 2026**. That is a legible, dated abandonment pattern inside one company's
own portfolio — the kind of reading app-store data supports that a careers page or a press release
does not.

## 4. Why "does it have an app" is the wrong question for the other 90%

Of the 25 confirmed companies, only **5** publish anything a consumer uses (the four direct-sales
firms plus SpartanNash). The remaining 20 publish **workforce and operations tooling**:

- **driver / fleet**: Crete Carrier Mobile, Estes4Me, ATS Driver, ATS FreightMatch, Prime Mobile,
  CRE Toolbox, SEFL, PS Logistics, OnTrac OnRoute
- **field safety** (all construction): Whiting-Turner *Target Zero*, Teichert Safety App, Phillips
  SmartTrack, HITT *Co|Lab Tours*
- **supply-chain ops**: Penske Supply Chain Insight / ClearChain / CellScan, UniGroup Flex & Stride,
  Midmark RTLS, Co-Diagnostics PCR Pro

So an app-store instrument pointed at this population would mostly measure **workforce enablement**,
not consumer digital maturity. If it is scoped, those are two different signals and must not share a
key — routing them together would manufacture exactly the kind of false convergence the
`systems_integration` pattern fix had to undo.

## 5. Google Play — better than expected, and better than Apple on identity

Checked tonight rather than assumed:

- **robots.txt permits it.** `play.google.com/robots.txt` disallows `/store/purchase`,
  `/store/apps/datasafety*`, `/store/xhr`, `/store/account` and named editorial pages. It does
  **not** disallow `/store/search` or `/store/apps/details` for `*`.
- **It is readable without rendering JavaScript.** `GET /store/search?q=...&c=apps` returns HTTP 200
  and the app ids are present in the server-rendered HTML (doterra: 10 distinct ids; scentsy: 29).
  Unlike Dayforce and the Maryland breach portal, this does not need a browser.
- **The package id carries identity for free**: `com.doterra.shop`, `com.doterra.social`,
  `com.scentsy.home.prod`, `com.scentsy.connect.prod`. A reverse-domain namespace is *stronger*
  identity evidence than Apple's `sellerName`, and Apple supplies a developer URL only sometimes. It
  also separates third parties cleanly — `com.rainfocus.eventapp.doTERRALeadershipRetreat25` is
  RainFocus's event platform, not doTERRA's own code.

**If this is scoped, Google Play should be the primary leg and Apple the corroborating one** — the
opposite of how it was approached here.

## 6. Feasibility verdict

**Buildable, cheap, and PRESENCE ONLY.** Conditions, if it is scoped:

1. **No absence claim from this instrument.** An app-store search index is a discovery surface, not a
   registry. 4 of 29 mechanical hits were refuted on inspection, and the recall side is worse than
   the precision side: a company with a common-word name and no developer URL cannot be resolved at
   all. Absence here means "not found by search", which licenses nothing — the same condition
   H-JOBPOST-01 operates under.
2. **Identity must rest on the publisher's domain or package namespace**, never on name tokens. This
   probe's first pass is the evidence.
3. **Consumer apps and workforce apps are different signals** (§4).
4. The population is **small by construction**: 5 consumer-facing companies. That is a legitimate
   finding about an operationally-complex, mostly-B2B universe, but it is not a portfolio-wide
   instrument and must not be scoped as one.

## 7. Adjudication of the 14 name-only candidates (for the record)

**Confirmed (10):** A014 Crete Carrier (`Crete Carrier Mobile`, exact legal name, ships on Transflo),
A018 Scentsy (2), A029 SpartanNash (13, banner domains), A031 Whiting-Turner (`Target Zero`, their
safety programme), A033 HITT (`Co|Lab Tours` from `colab.build`, HITT's own Co|Lab), A041 J.R.
Simplot (2, own grower-solutions division), A045 Estes (`Estes4Me`), A052 R+L Carriers (1 of 2),
A085 UniGroup (2), C0003 Duke Manufacturing (`Sous Chef Technology` from `souscheftech.com`).

**Refuted (4):** A004 Cajun Industries, A034 The Walsh Group, A049 NFI, C0004 Western Express — each
with grounds in §1. Also refuted within A052: `Car Carrier - Relaxing Puzzle` (7WARE S.R.L.).
