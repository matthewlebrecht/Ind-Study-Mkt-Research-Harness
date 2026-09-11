# Source Lists by Evidence Family

Legend: **[API]** programmatic access · **[WEB]** browser/scrape only · **[$]** paid/limited free tier · **[PRIVATE-OK]** works for privately held companies · **[PUBLIC-ONLY]** requires public equity/debt, largely dead for this project

**Confirmed with Jacob: target companies are smaller than Fortune 500 and mostly privately held.** This changes the whole calculus. Families that depend on public-company disclosure (SEC filings, earnings calls, proxy statements) will be thin-to-empty for most of the universe — they're not a reliable backbone, just an occasional bonus when a target company happens to have public debt. The project's real value is in stitching together many individually-weak, privately-available signals into compound observations no human would systematically compile by hand. Sections below are re-flagged accordingly.

---

## 1. First-party strategy & governance
- Company newsroom / press-release pages **[WEB] [PRIVATE-OK]** — primary backbone for this family now; private companies still announce leadership hires, expansions, plant openings
- PR Newswire / Business Wire archives **[WEB] [PRIVATE-OK]** — many private companies distribute press releases this way
- Local/regional business journal profiles (Bizjournals network) **[WEB] [PRIVATE-OK]** — genuinely strong source for private mid-size companies; local business press covers them when national press doesn't
- SEC EDGAR **[API] [PUBLIC-ONLY]** — only relevant for the minority with public debt (e.g. some issue public bonds even while privately held); check but don't rely on
- Annual report archives via AnnualReports.com **[WEB] [PUBLIC-ONLY]**

*Reframed: local business journals and press-release wires are now the backbone, not SEC filings. This is a genuinely weaker family for private companies — expect thinner coverage and lean harder on families 3, 4, 8, 10 below.*

## 2. Financial & capital allocation
- USASpending.gov **[API] [PRIVATE-OK]** — grants/contracts apply regardless of ownership structure
- MSRB EMMA **[API] [PRIVATE-OK]** — some private companies issue municipal/industrial revenue bonds for facility financing; worth checking
- State/local economic development incentive databases (Good Jobs First subsidy tracker) **[WEB] [PRIVATE-OK]** — strong source: tax incentives/subsidies for facility expansion are public regardless of ownership
- County property/assessor records **[WEB] [PRIVATE-OK]** — property ownership/transactions are public record independent of company structure
- SEC EDGAR **[API] [PUBLIC-ONLY]**

## 3. Workforce & organizational exhaust
- LinkedIn Jobs + company pages **[WEB]** (no public API for this use case)
- Indeed **[WEB]**, company career pages **[WEB]**
- State WARN Act notice databases **[WEB]** — each state DOL publishes separately
- NLRB case search **[API/WEB]** — union agreements, labor disputes

## 4. Employee experience & workarounds
- Glassdoor **[WEB]**
- Indeed reviews **[WEB]**
- Blind (tech-leaning, limited coverage for industrials) **[WEB]**
- Reddit — industry-specific subreddits (r/logistics, r/manufacturing, r/supplychain) **[WEB]**
- OSHA whistleblower complaint database **[WEB]**

## 5. Technology-stack traces
- BuiltWith **[WEB/$]** — tech stack detection from web presence
- Wappalyzer **[WEB]**
- Job postings mentioning specific systems (SAP, Oracle, Manhattan Associates, etc.) **[WEB]**
- Vendor trust centers / subprocessor lists (e.g. published by SaaS vendors) **[WEB]**
- GitHub org search **[API]** — limited relevance for non-tech companies but worth checking

## 6. Vendor & partner disclosure
- Vendor case-study pages (SAP, Oracle, Microsoft, Salesforce customer stories) **[WEB]**
- Partner/reseller directories on vendor sites **[WEB]**
- G2 / Capterra reviews naming implementation partners **[WEB]**
- Conference speaker/sponsor lists (e.g. Manifest, MODEX for logistics/supply chain) **[WEB]**

## 7. Procurement & contracting
- SAM.gov **[API]** — federal contract opportunities & awards
- USASpending.gov **[API]**
- State procurement portals (varies by state) **[WEB]**
- BidNet / GovSpend **[WEB/$]** — aggregated public-sector bid data
- Sourcewell / cooperative purchasing records **[WEB]**

*Note: most useful when target company is a government contractor/supplier; less relevant if purely private-sector B2B/B2C.*

## 8. Physical footprint & capacity
- County/city building permit portals **[WEB]** — varies widely by jurisdiction
- Zoning board / planning commission minutes **[WEB]**
- CoStar / LoopNet **[WEB/$]** — commercial property listings & transactions
- Satellite imagery (Google Earth historical) **[WEB]** — facility expansion verification

## 9. Industrial, safety & environmental records
- OSHA establishment search **[API/WEB]** — inspection history, violations
- EPA ECHO **[API]** — environmental compliance/enforcement
- MSHA (if mining-adjacent) **[API]**
- State environmental agency portals **[WEB]**

## 10. Logistics & supply-network exhaust
- FMCSA SAFER **[WEB/API]** — fleet registration, safety records
  - *Calibration note (confirmed during pilot testing):* private/owned fleets will show **NOT AUTHORIZED** under the "Operating Authority" field. This is expected, not a data-quality flag — that field reflects for-hire common/contract carrier authority, which private fleets (companies moving their own goods, not hauling for other shippers) don't need or hold. Don't route this to manual review when the company is a private fleet.
- DOT records **[WEB]**
- ImportGenius / Panjiva **[$]** — import/export bill-of-lading data
- USA Trade Online **[API]** — census trade data
- Port authority public data (varies by port) **[WEB]**

## 11. Product, quality & customer friction
- CPSC recall database **[API]**
- BBB complaint records **[WEB]**
- Trustpilot / app store reviews **[WEB]**
- Industry-specific complaint boards **[WEB]**

## 12. Commercial & channel behavior
- Company press releases **[WEB]**
- Trade publication coverage (industry-specific, e.g. Supply Chain Dive, FreightWaves, IndustryWeek) **[WEB]**
- LinkedIn company update history **[WEB]**

## 13. Legal & dispute records
- PACER **[$] [PRIVATE-OK]** — federal court filings, applies to any company sued/suing in federal court
- CourtListener **[API] [PRIVATE-OK]** — free federal + some state court records
- State court record portals **[WEB] [PRIVATE-OK]** — varies by state, but private companies show up here just as often as public ones (often more, since disputes are less likely to settle quietly under public scrutiny)
- SEC litigation releases **[WEB] [PUBLIC-ONLY]**

## 14. Patents & IP
- USPTO Patent Public Search **[WEB]**
- Google Patents **[WEB]**
- PatentsView **[API]** — structured patent data with assignee search

## 15. Executive candor & actor networks
- Podcast search via Listen Notes **[API/$]** or Podchaser **[WEB]**
- YouTube (conference talks, panel recordings) **[WEB]**
- LinkedIn posts/articles by named executives **[WEB]**
- Industry association board bios **[WEB]**

## 16. Local & community records
- City council minutes — most run on Granicus or Legistar **[WEB]**, both searchable
- County board agendas **[WEB]**
- Local newspaper archives (often via Newspapers.com or local outlet sites) **[WEB]**

## 17. Digital-product & service telemetry
- Public status pages (statuspage.io-hosted, often at status.[company].com) **[WEB]**
- Release notes / changelogs **[WEB]**
- App store version history **[WEB]**

## 18. Historical change & disappearing evidence
- Wayback Machine **[API]** — archived site snapshots, diffable over time
- Google cache (limited availability) **[WEB]**

## Seller discourse (comparative benchmark, not a buyer family)
- Consulting/SI firm websites, service pages, case studies **[WEB]**
- Webinar libraries, event agendas (Manifest, MODEX, Gartner supply chain events) **[WEB]**
- Sales job postings at modernization providers (reveals what they're selling/hiring to sell) **[WEB]**

---

## Automation priority (revised for privately-held, sub-Fortune-500 universe)
SEC-dependent sources drop out almost entirely — they were doing a lot of the "easy API" work in the original ranking, and that work doesn't exist for most of this universe. Revised order, weighted toward what actually produces signal for private companies:

1. **OSHA + EPA ECHO** (family 9) — clean APIs, ownership-agnostic, genuinely rich for operations-heavy companies
2. **FMCSA SAFER** (family 10) — clean API/web, ownership-agnostic, directly relevant to logistics/manufacturing fleets
3. **USASpending + county property/assessor records + economic-development incentive databases** (families 2, 8) — ownership-agnostic, public regardless of private status
4. **Wayback Machine** (family 18) — cheap to run broadly, catches removed case studies/changed job postings/abandoned initiatives — arguably *more* valuable here since private companies leave a thinner live footprint to begin with
5. **PatentsView** (family 14) — clean API, ownership-agnostic
6. **Local business journals + PR wire archives** (family 1) — now doing the work SEC filings used to do; needs a scraping/aggregation approach since there's no single clean API across all regional outlets
7. **Job postings + LinkedIn + Glassdoor** (families 3, 4) — still your highest-value, hardest-to-automate sources; this doesn't change, but it's now even more clearly the crux of the whole project, since it's one of the few families where private companies expose almost as much signal as public ones
8. **Everything else** — build opportunistically as baseline pilot surfaces gaps

**The real thesis of this project, sharpened:** for a private company, no single source family gets you far. The value is entirely in family 6 (compound signals) — e.g. a permit filing + a hiring surge + a changed job-stack requirement, none individually meaningful, together indicating a real modernization program. That combinatorial work is explicitly what a human researcher wouldn't do at scale, and exactly what the harness should be built to do.
