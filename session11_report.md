# Session 11 Report — Job-Posting Coverage, Final Push

**Date:** 2026-09-03
**Brief:** session 11, four items, scoped as a final push. No code changed this session; no
harness ran; the workbook is untouched. Two measurements and an assessment.

## In one screen

| # | item | outcome |
|---|---|---|
| 1 | JSON-LD `JobPosting` scan of the archived careers pages | **Zero.** 103 companies have an archived careers page; 75 carry JSON-LD; **none of it is a JobPosting** (Organization 11, WebSite 4, WebPage 3, FAQPage 2, Event 2, LocalBusiness 2, the rest `@graph` containers). Nothing gained, nothing overlapping: the 17 deep companies are unchanged. |
| 2 | Is the Dayforce / UltiPro refusal host-wide? | **Yes for 7 of the 10, with one genuine lead for 3.** Every Dayforce tenant host (`us59.`, `us62e2.`, `globalus242.`, `www.`, bare `dayforcehcm.com`) serves a 26-byte `User-agent: * / Disallow: /`; both UltiPro recruiting hosts serve `Disallow: /` for `*` plus explicit JobBoard paths. Closed to every crawler, not to this identity. **But `jobs.dayforcehcm.com`** — the front end used by C.R. England, Power Construction and Wharton-Smith — publishes a content-signals robots.txt with no disallow, returns 200 to this crawler, and server-renders only the site record (client id, job board id); the posting list loads client-side from an API the page's JavaScript selects. Not opened: reproducing that call is a build, not a check. §2. |
| 3 | LinkedIn | Out of scope, as instructed. Unchanged. |
| 4 | Denominator and assessment | **17 deep, 53 shallow, 58 either, 50 neither, of 108.** The structural ceiling is real for this population and the reasons are enumerable. §4. |

## 1. The JSON-LD scan

Method: every `discover_<cid>_*.html` in the H-JOBPOST-01 archive (the careers page each
company's discovery landed on, plus the candidates it tried), every
`<script type="application/ld+json">` block parsed (with a trailing-comma repair), every
object walked recursively including `@graph`, any `@type` of `JobPosting` counted. No
fetches.

Result: 0 companies. The caveat that matters: JobPosting structured data lives on
posting **detail** pages, not on careers landing pages, and the archive holds detail pages
only for companies that were already readable. So the scan answers "does the landing page
embed a feed?" — it does not — and cannot answer "would the detail pages carry it?" For the
unreadable companies there is no detail-page URL to fetch, which is the same wall the
inline-list rule hit. The one adapter this could have justified is not justified by the
evidence available offline.

## 2. The robots check, and the one lead

| host class | robots.txt | companies |
|---|---:|---|
| Dayforce tenant hosts (`<tenant>.dayforcehcm.com`, `www.`, bare) | `Disallow: /` for `*` | Savage, UniGroup, Lynden (+ C.R. England's tenant host) |
| UltiPro (`recruiting.` / `recruiting2.ultipro.com`) | `Disallow: /` for `*` and `*/JobBoardView` | Austin Industries, Big-D, Crane Worldwide, Samet |
| **`jobs.dayforcehcm.com`** | content-signals file, **no disallow** | **C.R. England, Power Construction, Wharton-Smith** |

Seven of the ten are settled: the refusal is to all crawlers, uniform across tenants, and
there is no other path (`dfid.`, `static.` and `help.dayforce.com` are closed too). The
`access_blocked` / `source_limitation` recording from session 10 stands for them.

Three sit on `jobs.dayforcehcm.com`, which is open. Its tenant portal is a Next.js app
whose server-rendered state holds one query, `site-info` (client id, job board id); the
postings are fetched client-side. The hosts the page references that also permit this
crawler are `jobs.dayforcehcm.com` itself and `us252.dayforcehcm.com`, so the posting API is
probably reachable within policy — but finding it means reading the app's JavaScript for
the endpoint it calls, then reproducing that call. That is an adapter build of the same
order as ADP's, for three companies, and it was not in this session's scope. Recorded here
as the only lead this session found; the attempt rows for those three keep their
`access_blocked` category until someone builds it, because the board they link is the
closed tenant host.

## 4. Denominator and assessment

From the last live run (HR-0056, v1.4):

| measure | companies | share |
|---|---:|---:|
| deep: own-domain postings read through an adapter | 17 | 15.7% |
| shallow: at least one Talent.com cross-post resolving to the company | 53 | 49.1% |
| deep or shallow | **58** | **53.7%** |
| both | 12 | |
| neither | 50 | 46.3% |
| of the 50: careers page found, unparseable in server HTML | ~40 | |
| of the 50: no careers page found on own domain | 7 | |
| own-domain `access_blocked` (robots-refused board host) | 10 (4 of them shallow-covered) | |

Three sessions moved deep from 13 to 17 and added the shallow leg from nothing to 53. What
the measurements say about the remaining 50:

1. **They are not hiding a scrape-friendly surface.** Not as an inline list (1 of 83 under
   a strict rule), not as JSON-LD (0 of 103), not as a public ATS listing (of 18 platforms
   in the audit, ADP alone; Dayforce and UltiPro closed to everyone; Jobvite and Taleo not
   reachable from the page; SuccessFactors a login; Tenstreet a form; BambooHR a homepage).
   58 of 90 audited pages are WordPress marketing pages that link out to a board.
2. **The aggregator is broad and shallow by construction.** Talent.com indexes a handful of
   requisitions per company (Kenco's 481 appear as 1). It gives presence for half the
   universe and depth for none of it; 32 of the 53 have exactly one cross-post.
3. **The population explains it.** These are private, mid-size, operationally heavy
   companies — contractors, carriers, food distributors — whose recruiting is either a
   hosted portal behind a crawler wall, or a "join our team" page with a phone number.
   Tech-forward hiring pages are the exception. This is the EXECVOICE podcast finding in
   another family: predicted low yield, confirmed low yield, for a reason about the
   companies rather than the instrument.

**Assessment.** For this population, job-posting coverage has hit a structural ceiling at
roughly 17 deep / 58 reachable of 108 under the project's access discipline. The only
identified lever left is the `jobs.dayforcehcm.com` API (3 companies, a build). Everything
past that requires rendering JavaScript or crossing a robots line, and the project has
already decided not to do the second. Per-key absence claims remain unlicensed (condition
1 of the 2026-09-02 authorisation); presence claims from the 58 stand.

For the priority question Matthew parked: further investment here buys, at most, three
companies of depth. H-EMPREVIEW-01 sits at "source blocked" on the same discipline, so its
ceiling is at least as hard until an alternative review source is found. H-VENDOR-01 is the
one with a running start (24 vendor customer URLs logged, and session 10's allowlist scoping
counted 23 refused vendor-site results — the second-largest refused class in trade press).

## Not touched, carried

The review-sheet backlog (session 9's nine, session 10's five), the EXECID low-grade tier,
FMCSA F15/F26 verification, O00369/O00373, the Harness Advisor ping. The LinkedIn position
is unchanged and unrevisited.

## Files

New: this report. Modified: `CLAUDE.md` (denominator, JSON-LD and robots findings). No
workbook, code or harness change.
