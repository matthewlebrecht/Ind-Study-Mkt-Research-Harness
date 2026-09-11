"""
The third-party job-board leg of H-JOBPOST-01: aggregators that permit this crawler.

WHY THIS EXISTS (session 9 brief, item 2)
-----------------------------------------
The own-domain leg reads 14 of 108 careers pages. The platform audit of the other 94
(scripts/careers_platform_audit.py) found no single ATS worth an adapter -- Dayforce leads
at 6 -- and 39 companies on a plain WordPress page that lists jobs inline or links out. An
adapter per platform cannot close that. A cross-posting aggregator can, because most
private mid-size companies feed the same requisitions to the boards whatever they run on
their own site.

WHICH BOARDS, AND WHY THE LIST IS SHORT
---------------------------------------
Every board is PROBED through core/robots.py under this crawler's own identity before a
single search runs, and a refusal is recorded as the source's decision (convention 38),
exactly as the LinkedIn and Indeed refusals have been since v1.1. Probed 2026-09-03:

    REFUSED by robots.txt:  LinkedIn, Indeed, Glassdoor, ZipRecruiter, SimplyHired,
                            Google Jobs, Dice, Monster
    ALLOWED by robots.txt:  Talent.com, Jooble, CareerJet, Adzuna
    of the allowed, actually reachable without a browser: Talent.com only
                            (Jooble and Adzuna answer 403 behind a bot challenge;
                            CareerJet serves a JavaScript loader with no results in it)

No user agent is switched, no challenge is solved, no authenticated or mirrored access is
used: an evaded refusal is not access. So the leg has one working adapter and records the
other eleven boards' answers per company, so the denominator says what was tried.

THE IDENTITY GATE IS NOT RELAXED HERE
-------------------------------------
A keyword search for "Kenco Group" on Talent.com returns 18 cards of which ONE is Kenco:
"Delivery Driver - Kenco Hydraulics" (a different company), "Group Facilitator" at six
clinics, and "Group Lead - Axiom Group". Every card carries the employer's name in its own
field, and that name is scored against the canonical company name with core/resolution.py
at the standard floor. A card whose employer does not resolve is rejected and listed, with
its score, in the run log -- the single-common-word and eponymous traps live exactly here,
and the 2026-09-03 corroboration-gate policy leaves identity gates untouched by design.
"""

from __future__ import annotations

import html as _html
import re
import time
import urllib.parse
from dataclasses import dataclass, field

from core.cache import DatedCache, slug
from core.resolution import DEFAULT_FLOOR, query_variants, score, strip_legal_suffix

from harnesses.h_jobpost_01.source import Posting, dedupe

# (board, probe URL, adapter) -- adapter None means "probe and record only".
BOARDS = [
    ("LinkedIn",     "https://www.linkedin.com/jobs/search/?keywords=engineer", None),
    ("Indeed",       "https://www.indeed.com/jobs?q=engineer", None),
    ("Glassdoor",    "https://www.glassdoor.com/Job/jobs.htm?sc.keyword=engineer", None),
    ("ZipRecruiter", "https://www.ziprecruiter.com/jobs-search?search=engineer", None),
    ("SimplyHired",  "https://www.simplyhired.com/search?q=engineer", None),
    ("Google Jobs",  "https://www.google.com/search?q=engineer+jobs&ibp=htl;jobs", None),
    ("Dice",         "https://www.dice.com/jobs?q=engineer", None),
    ("Monster",      "https://www.monster.com/jobs/search?q=engineer", None),
    ("Jooble",       "https://jooble.org/SearchResult?ukw=engineer", None),
    ("CareerJet",    "https://www.careerjet.com/search/jobs?s=engineer&l=", None),
    ("Adzuna",       "https://www.adzuna.com/search?q=engineer", None),
    ("Talent.com",   "https://www.talent.com/jobs?k=engineer&l=United+States", "talent"),
]

TALENT_SEARCH = "https://www.talent.com/jobs?k={q}&l=United+States&p={page}"
TALENT_VIEW = "https://www.talent.com/view?id={id}"
MAX_PAGES = 6            # 18 cards a page; a company with more cross-posts than ~100 is truncated and says so
STOP_AFTER_EMPTY = 2     # consecutive pages with no resolving card end the walk
RETRIES = 3
MIN_HTML = 20_000        # Talent.com's edge sometimes answers 200 with a one-line upstream error

_CARD = re.compile(r'<div data-job-id="([^"]+)" data-new-id="([^"]+)"[^>]*>(.*?)</article>', re.S)
_TITLE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_ADDRESS = re.compile(r"<address[^>]*>(.*?)</address>", re.S)
_SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S)
_DESC = re.compile(r'<p[^>]*class="[^"]*(?:description|snippet|preview)[^"]*"[^>]*>(.*?)</p>', re.S | re.I)


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Probe:
    board: str
    url: str
    allowed: bool
    why: str
    adapter: str | None


@dataclass
class AggregatorResult:
    board: str
    query: str
    search_url: str
    postings: list = field(default_factory=list)          # resolved to the company, deduped
    candidates_seen: int = 0                              # every card read
    rejected: list = field(default_factory=list)          # (employer, score, title) not resolving
    pages_read: int = 0
    truncated: bool = False
    error: str = ""
    notes: list = field(default_factory=list)


def probe_boards(gate) -> list[Probe]:
    out = []
    for board, url, adapter in BOARDS:
        try:
            ok, why = gate.check(url)
        except Exception as exc:  # noqa: BLE001 -- a robots fetch failure is not the board's verdict
            ok, why = True, f"robots.txt unreadable: {type(exc).__name__}"
        out.append(Probe(board, url, bool(ok), why or "", adapter))
    return out


class TalentClient:
    """Talent.com keyword search, cached and paginated, with the employer field scored
    against the canonical name. Never raises for a company; the error is in the result."""

    def __init__(self, cache: DatedCache, session, gate, pause: float = 0.7):
        self.cache, self.session, self.gate, self.pause = cache, session, gate, pause
        self.fetch_count = 0

    def _get(self, url: str, key: str) -> str:
        def fetch():
            last = ""
            for attempt in range(RETRIES):
                r = self.session.get(url, timeout=30, allow_redirects=True)
                self.fetch_count += 1
                if r.status_code == 200 and len(r.text) >= MIN_HTML:
                    return r.text
                last = f"HTTP {r.status_code}, {len(r.text)} bytes"
                time.sleep(self.pause * (attempt + 2))
            raise RuntimeError(f"talent.com unavailable after {RETRIES} tries: {last}")
        body, _ = self.cache.get(key, ".html", fetch)
        return body

    @staticmethod
    def parse(html: str) -> list[dict]:
        cards = []
        for job_id, new_id, body in _CARD.findall(html):
            title = _clean(_TITLE.search(body).group(1)) if _TITLE.search(body) else ""
            employer, location = "", ""
            m = _ADDRESS.search(body)
            if m:
                spans = [_clean(x) for x in _SPAN.findall(m.group(1))]
                spans = [x for x in spans if x and len(x) > 1]
                if spans:
                    employer = spans[0]
                if len(spans) > 1:
                    location = spans[-1]
            d = _DESC.search(body)
            cards.append({"job_id": job_id, "new_id": new_id, "title": title,
                          "employer": employer, "location": location,
                          "description": _clean(d.group(1)) if d else ""})
        return cards

    def search(self, company: dict, aliases: list[str] | None = None) -> AggregatorResult:
        cid = company["company_id"]
        canonical = company["canonical_name"]
        queries = query_variants(canonical, aliases)
        q = queries[0]
        first_url = TALENT_SEARCH.format(q=urllib.parse.quote_plus(strip_legal_suffix(q)), page=1)
        res = AggregatorResult(board="Talent.com", query=q, search_url=first_url)

        ok, why = self.gate.check(first_url)
        if not ok:
            res.error = f"robots: {why}"
            return res

        seen_ids: set[str] = set()
        empty_streak = 0
        for page in range(1, MAX_PAGES + 1):
            url = TALENT_SEARCH.format(q=urllib.parse.quote_plus(strip_legal_suffix(q)), page=page)
            key = f"talent_{slug(cid)}_{slug(strip_legal_suffix(q))}_p{page}"
            try:
                html = self._get(url, key)
            except Exception as exc:  # noqa: BLE001
                res.error = f"{type(exc).__name__}: {exc}"[:200]
                break
            res.pages_read = page
            cards = self.parse(html)
            if not cards:
                break
            resolved_here = 0
            for c in cards:
                if c["new_id"] in seen_ids:
                    continue
                seen_ids.add(c["new_id"])
                res.candidates_seen += 1
                s = score(canonical, c["employer"]) if c["employer"] else 0.0
                if s < DEFAULT_FLOOR:
                    if len(res.rejected) < 40:
                        res.rejected.append((c["employer"], round(s, 2), c["title"][:60]))
                    continue
                resolved_here += 1
                res.postings.append(Posting(
                    title=c["title"], location=c["location"],
                    url=TALENT_VIEW.format(id=c["new_id"]), job_id=c["new_id"],
                    description=c["description"]))
            empty_streak = 0 if resolved_here else empty_streak + 1
            if empty_streak >= STOP_AFTER_EMPTY:
                break
            if len(cards) < 10:      # short page: the result set ended
                break
        else:
            res.truncated = True
            res.notes.append(f"stopped at page cap {MAX_PAGES}; more cross-posts may exist")
        res.postings, dropped = dedupe(res.postings)
        if dropped:
            res.notes.append(f"{dropped} duplicate title+location pairs collapsed")
        return res
