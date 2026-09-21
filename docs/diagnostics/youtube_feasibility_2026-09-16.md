# YouTube channel presence — feasibility probe, 2026-09-16

Probe, not a harness: **no harness, manifest or workbook row was written.** Reproduce with
`python scripts/probe_youtube.py`; outputs `harness_output/youtube_probe.json`,
`youtube_probe_analysis.json`, `youtube_depth_sample.json`, `execvoice_overlap_basis.json`.
LinkedIn, X/Twitter and Facebook/Instagram were not probed (settled out).

## Verdict: worth nothing as a modernization instrument

YouTube presence is broad and cleanly measurable in this population, and it is **not** a duplicate of
H-EXECVOICE-01. But it carries almost no evidence about the governing question: across 1,457 video
titles and 60 full video descriptions, it produced **no buyer-side modernization statement at all**.
The layers that might carry more (transcripts, the channel "links" and search) are closed by
robots.txt. A harness would measure presence and posting cadence reliably and answer nothing the
project is asking.

---

## 1. Access: robots.txt decides the design

`youtube.com/robots.txt` disallows, for every crawler, **`/results`** (search), **`/youtubei/`** (the
internal API the site's own pages call), `/feeds/videos.xml` and `/timedtext_video` (captions).
Channel pages, their `/videos` tab and `/watch` pages are not disallowed. So:

- **no company was looked up by searching YouTube** — search is closed;
- transcripts are closed, and a channel's own "links" section loads through `/youtubei/`;
- the probe re-reads robots.txt at start and refuses to run if either closed path has opened.

## 2. Identity: from the company to the channel, never the reverse

Discovery read each company's own homepage as H-EXECID-01 archived it — **no new fetch** — for links
to YouTube. A channel the company links from its own site is its channel by its own statement. The
fetched channel title was then scored against the company name, and a low score flagged for a
human rather than accepted or dropped.

Of 108 homepages, **63 contain a YouTube link**. What those links turned out to be:

| Kind | Companies | Note |
|---|---|---|
| Channel, confirmed | 52 | title scores ≥ 0.55 |
| Channel, name mismatch → **confirmed by hand** | 6 | titles that defeat token scoring: `RyconConstruction`, `PetersenInc`, `WalbridgeGroup`, `Simplot Company` (vs "J.R. Simplot"), `Averitt` (vs "Averitt Express"), `RL Carriers` (vs "R+L") |
| Channel, name mismatch → **refuted** | 1 | **Wadsworth Brothers** links to *Slider Revolution* — a WordPress slider plugin's channel left in the site theme |
| Embedded video / template only | 2 | Hathaway Dinwiddie (an embed); Anderson Trucking (`embed/VIDEO_ID`, a literal template placeholder) |
| Placeholder / player script | 2 | Yates (`youtube.com`), F.H. Paschen (`/iframe_api`) |

**58 of 108 companies have a confirmed company YouTube channel.** The Slider Revolution case is the
one to remember: the company's own site linked to it, so site-linking alone is not identity — the
channel still has to be about the company. (Contrast the app-store probe, where "The Walsh Group Inc"
published a fitness-club app; here the Walsh Group's site links to the Walsh Group's real channel.)

The 45 homepages with no YouTube link do **not** establish that those companies have no channel —
Whiting-Turner, for one, is linked nowhere on its homepage. Presence only.

## 3. Activity

| Most recent upload | Channels |
|---|---|
| within 3 months | 29 |
| 3–12 months | 16 |
| 1–3 years | 7 |
| 3 years or more (dormant) | 6 — Barney Trucking and Kenan Advantage (8 yrs), Penske Logistics (7), Ferreira (5), Petersen and Pacific Steel (3) |

45 of 58 posted in the last year. Cadence is measurable and would be a clean presence/recency series.

## 4. Overlap with H-EXECVOICE-01 — low, and in the wrong place to matter

Against EXECVOICE's latest run (HR-0065) for the same 58 companies:

- **19 are companies EXECVOICE cannot reach at all** (no primary executive identified) — Averitt,
  Merit Medical, the Walsh Group, Estes, R+L, C.R. England, CRST, OnTrac, Western Express, PLS and
  others. So on reach, YouTube is not a duplicate.
- 33 are EXECVOICE `absent_confirmed`; 6 are companies where EXECVOICE holds rows.
- **Titles that name an identified executive (first and last name): 6 channels** of the 40 whose
  company has identified executives — Clancy & Theys, Clyde Companies, Crete Carrier (a weekly
  "update with Tim Aschoff and Erick Kutter"), Black & Veatch, Herzog, Midmark. None of the six is a
  company where EXECVOICE holds a row.

It is also a different *kind* of source from EXECVOICE. EXECVOICE reads **third-party** coverage for
executive candour; a company's own channel is **first-party**, company-authored — H-FIRSTPARTY-01's
family, not EXECVOICE's. So "overlaps too much with EXECVOICE" is not the right verdict. The problem
is the content, below.

## 5. Signal content — the reason for the verdict

**Titles.** 1,457 recent titles across the 58 channels. 8 match a modernization theme under the
project's topic spine, across 5 companies, and none is a buyer-side statement:

- 1 false positive: Walsh's *"Red-Purple Modernization team…"* is a Chicago transit construction
  project's name.
- 7 are companies describing **what they sell**: Penske Logistics' and PLS's TMS offerings, Black &
  Veatch's OT-cybersecurity and grid-modernization services, Kenco's material-handling analytics —
  seller messaging from firms that sit in the buyer universe but provide these services.

Over the six newest titles per channel (332), the mix is recruiting and people 43, project showcase
40, product/customer 26, safety 13, community 10 — overlapping keyword buckets.

**Descriptions (depth check).** Titles are thin, so 60 full descriptions were read from `/watch`
pages — the 5 newest videos of the 12 most recently active channels. 52 had a description. **Zero
matched any theme, at either the strong or the low-grade tier.** Typical content: Crete Carrier's
weekly operations updates, HITT's intern and safety features, Averitt's driver podcast, Prime's
truck-model tours, Mortenson's construction-progress and careers videos, Duke Manufacturing's
equipment how-tos.

The one near-signal is **workforce**: recruiting, training and driver-appreciation content is the
largest share of what these channels post. That is already H-JOBPOST-01's territory, read there from
postings with a clearer claim.

## 6. What a harness would and would not deliver

Would: presence for ~58 companies with an identity test that works, and a dated posting-cadence
series.
Would not: any buyer articulation of modernization pressure (none found at title or description
depth), any absence claim (search and transcripts are closed; a homepage without a link proves
nothing), or executive candour beyond what first-party announcements already carry.

**Not worth building.**
