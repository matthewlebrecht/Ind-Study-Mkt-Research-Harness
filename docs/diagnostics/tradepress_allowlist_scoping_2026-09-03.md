# H-TRADEPRESS-01 outlet allowlist — scoping (session 10, item 4)

**Question as framed by Matthew:** treat the allowlist as a coverage question, not purely an
identity question. Which sites or patterns are candidates, and what identity safeguards
travel with them? Template: the LinkedIn precedent of 2026-09-01 — added to the allowlist,
scored IC1, robots-probed under this crawler's own identity, refusal recorded, no user-agent
switching.

## The evidence: what the harness has been refusing

Every off-allowlist result is counted by host in the run log (v1.1 onward). From the
2026-09-03 replay across the 15-company subset, the refused hosts fall into five classes:

| class | hosts (count of refused results) | disposition |
|---|---|---|
| **Trade / business press not yet listed** | supplychain247.com (2), truckingdive.com (2), foodlogistics.com (2), grocerydive.com (2), andnowuknow.com (2), cio.com (1), itdigest.com (1), pymnts.com (1), acppubs.com (1), commercialobserver.com (1) | **Added** — 15 refused results were the kind of reported journalism this harness exists to read |
| Company's own domain | jedunn.com (11), kencogroup.com (8), gilbaneco.com (6), penskelogistics.com (6), mcgough.com (4), midmark.com (4), averitt.com (3), gopenske.com (3), doterra.com (3), careers.leprino.com (2) | Not added: family 1, owned by H-FIRSTPARTY-01 (partition rule E9). 50 results, the single largest refused class — this is coverage that belongs to a different harness, and H-FIRSTPARTY-01 already reads it |
| Executive-data aggregators | appsruntheworld.com (10), zoominfo.com (6), leadiq.com (4), rocketreach.co (2) | Not added as a reading source: undated profiles, no quotes, no reported actions — nothing this harness's four signal types can carry. Robots probed this session and recorded below |
| Vendor / systems-integrator sites | scnsoft.com (3), kinaxis.com (3), appinventiv.com (3), meritsolutions.com (3), rib-software.com (2), theaccessgroup.com (2), westerncomputer.com (2), experionglobal.com (2), ttms.com (2), softwebsolutions.com (1) | Not added: family 6 vendor customer content, the H-VENDOR-01 queue (23 results, the second-largest class — a real coverage finding for that build) |
| PR wires, review sites, podcasts | prweb.com (3), prnewswire.com (2), glassdoor.com (9), indeed.com (2), podcasts.apple.com (2) | Not added: wires are family 1 (H-FIRSTPARTY-01 reads them); Glassdoor/Indeed are family 4 and robots-refused; podcasts have no text |

## What was added, and the safeguards that travel with it

Added to `OUTLETS` by vertical: `truckingdive.com` (trucking); `supplychain247.com`,
`foodlogistics.com` (logistics); `grocerydive.com`, `andnowuknow.com`, `foodlogistics.com`
(food); `commercialobserver.com`, `acppubs.com` (construction). Added for every vertical as
`CROSS_VERTICAL_OUTLETS`: `cio.com`, `pymnts.com`, `itdigest.com`.

Every added host is read under exactly the safeguards the original outlets have, none of
which is relaxed by this expansion:

1. **robots.txt under this crawler's identity**, per URL, refusal recorded (`robots_blocked`).
2. **`is_about_company`** on the article (all distinctive tokens near the top, or the full
   phrase for a dictionary-word name) and, for action sentences, on the sentence itself.
3. **Speaker resolution**: a quote is attributed only to a rostered or article-identified
   executive whose name resolves; eponymous surnames need explicit attribution.
4. **Wire verdict**: a reprinted press release on any of these hosts routes to family 1.
5. **Signal typing**: reported quote / column / panel / profile / (new) characterisation,
   each with its own grade ceiling (B or C, never A).

The identity risk of an outlet is not the outlet; it is the article-level tests above, which
apply identically to a new host and an old one. That is why the expansion is safe to make on
coverage grounds alone.

## The aggregator question, answered separately

Matthew's framing names ZoomInfo/RocketReach-type sites. Probed 2026-09-03 through
`core/robots.py` under this crawler's identity for the record:

| host | value for this harness | recommendation |
|---|---|---|
| zoominfo.com, rocketreach.co, leadiq.com, appsruntheworld.com | executive names and titles, undated; no quotes, no reported actions | Not a trade-press source. If used at all, the consumer is H-EXECID-01 (roster completion) at grade C with a freshness test, which its own docstring already sketches as "a later version can start from that list with a freshness test and a lower source grade". That is the LinkedIn-precedent shape: declare, score low, robots-gate, record. Out of scope for H-TRADEPRESS-01. |

## Expected effect and how to measure it

The 15 refused trade-press results become candidates on the next live run. Each still has to
pass the article-level tests, so the yield is bounded above by 15 articles across 15
companies. Measure it the same way the refusal was measured: the run log's
`off_allowlist_hosts` should no longer list these ten hosts, and the per-page notes will
show what each article yielded or why it was declined. The offline replay committed tonight
(HR-0051) does not fetch new hosts, so the first measurement is the next live run.
