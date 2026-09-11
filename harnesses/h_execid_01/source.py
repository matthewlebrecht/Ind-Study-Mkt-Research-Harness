"""
Fetching and leadership-page discovery for H-EXECID-01.

WHY DISCOVERY IS NOT A LIST OF GUESSED URL PATHS
------------------------------------------------
The obvious implementation tries `/leadership`, `/our-team`, `/about/leadership` and so on
against each domain. Measured against the actual universe, that approach is both expensive
and wrong: it costs one request per guess per company, and on the four companies used to
calibrate this module, three of four guessed paths 404 while every one of those companies
had a reachable leadership page under a path no list would have contained.

So discovery reads the homepage and follows links the site itself publishes, the same
refuse-to-guess posture `core/resolution.py` takes toward entity names and
`H-SELLERCONTENT-01` takes toward service pages. A link the site does not offer is not a
page this harness invents.

Search is the last resort, never the first, and is constrained to the company own host.
An off-host result is an aggregator profile (theorg.com, rocketreach.co, comparably.com,
leadiq.com dominate these result sets), which this version deliberately does not read --
see the harness docstring for why that is a v1.1 rather than an omission.

THE SUBSTITUTION LESSON FROM H-SELLERCONTENT-01
-----------------------------------------------
Convention 16 records that SellerContent reported 100% coverage while half its providers
had been read off homepage substitutes rather than real service pages. The same trap is
open here: a homepage often mentions a founder, so a bare homepage can yield one plausible
executive and look like success. `PageResult.kind` records what class of page a reading
actually came from, and the harness marks anything other than a genuine leadership page as
`partial`, never `covered`.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

from core.cache import DatedCache, slug
from core.resolution import tokens
from core.search import BraveSearch, SearchError, host_of

UA = ("Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; "
      "academic research; +contact via repository)")
TIMEOUT = 25

# Ranked link-text / href markers for a leadership page. Earlier entries are stronger
# evidence that a link leads to a page listing named executives, so candidates sort by
# the best marker they match. `about` alone is deliberately last and weak: an About page
# is usually company history, and treating it as a leadership page is the substitution
# failure this module exists to avoid.
LEADERSHIP_MARKERS = [
    (10, re.compile(r"(?i)(leadership|executive[- ]?team|our[- ]?executives|"
                    r"management[- ]?team|senior[- ]?(team|management|leadership))")),
    (8, re.compile(r"(?i)(officers|board[- ]of[- ]directors|corporate[- ]officers)")),
    (6, re.compile(r"(?i)(our[- ]?team|meet[- ]?the[- ]?team|our[- ]?people|"
                   r"who[- ]we[- ]are|team\b)")),
    (3, re.compile(r"(?i)(about[- ]us|about\b|company\b)")),
]

# A careers page matches "our team" as readily as a leadership page does and contains no
# executives at all. Nicholas and Company ranked `/join-our-team` above its real About
# page during calibration on exactly that collision, spending a fetch to read a job board.
# Recruiting language is excluded from candidacy rather than merely demoted, because there
# is no leadership page whose URL or link text says "apply" or "job openings".
CAREERS_MARKER = re.compile(
    r"(?i)(careers?|jobs?|join[- ]our|join[- ]us|apply|hiring|openings?|recruit|"
    r"employment|work[- ]with[- ]us|work[- ]for[- ]us|internship)")

# News and blog URLs are excluded for the same reason, and the reason is a repeat offence.
# A press release headlined "Kenco Announces Leadership Appointments" matches every
# leadership marker there is, and the site-constrained search fallback duly ranked exactly
# such an article first for Kenco and for PLS Logistics. H-WAYBACK-01 was burned by the
# identical shape -- dated news posts matching on substrings -- which convention 16 records
# as the projects characteristic failure. An article ABOUT executives is not a roster OF
# them: it names one or two people in prose, in a form the extractor would read as current
# even when the appointment it describes is six years old.
NEWS_MARKER = re.compile(
    r"(?i)(/news/|/blog/|/press/|/insights?/|/articles?/|/resources?/|/media/|"
    r"/newsroom/|/stories/|/case-stud|/20\d\d/|announce|press[- ]release)")

# Hosts that aggregate executive data rather than publishing it first-hand. Recorded when
# seen so a later version has the candidate list ready, never read as evidence in v1.0.
AGGREGATOR_HOSTS = {
    "theorg.com", "rocketreach.co", "comparably.com", "leadiq.com", "zoominfo.com",
    "linkedin.com", "crunchbase.com", "bloomberg.com", "signalhire.com", "apollo.io",
    "datanyze.com", "lusha.com", "zippia.com", "6sense.com", "cbinsights.com",
}


class PageResult:
    def __init__(self, url: str, status=None, html: str = "", error: str = "",
                 from_cache: bool = False, kind: str = "unknown", marker_score: int = 0):
        self.url = url
        self.status = status
        self.html = html
        self.error = error
        self.from_cache = from_cache
        # "leadership" | "team" | "about" | "homepage" -- what class of page this actually
        # is, so a reading off a weaker page is never reported as full coverage.
        self.kind = kind
        self.marker_score = marker_score

    @property
    def ok(self) -> bool:
        return self.status == 200 and len(self.html) > 500


class SiteClient:
    def __init__(self, cache: DatedCache):
        self.cache = cache

    def get(self, url: str, kind: str = "unknown", marker_score: int = 0) -> PageResult:
        key = "p_" + slug(url.replace("https://", "").replace("http://", ""), maxlen=110)

        def fetch() -> str:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9"})
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    body = r.read(4_000_000)
                    charset = r.headers.get_content_charset() or "utf-8"
                    return _wrap(r.status, body.decode(charset, "replace"))
            except urllib.error.HTTPError as e:
                # The status is archived alongside the body so an offline replay knows a
                # 404 was a 404 and does not reclassify it as a parse problem.
                return _wrap(e.code, e.read(200_000).decode("utf-8", "replace"))
            except urllib.error.URLError as e:
                return _wrap(0, f"URLError: {e.reason}")
            except Exception as e:                       # timeouts, bad TLS, bad redirects
                return _wrap(0, f"{type(e).__name__}: {e}")

        try:
            payload, from_cache = self.cache.get(key, ".txt", fetch)
        except RuntimeError as e:                        # offline, nothing archived
            return PageResult(url, error=str(e), kind=kind)
        status, body = _unwrap(payload)
        if status == 0:
            return PageResult(url, status=0, error=body[:200], from_cache=from_cache,
                              kind=kind)
        return PageResult(url, status=status, html=body, from_cache=from_cache,
                          kind=kind, marker_score=marker_score)


def _wrap(status: int, body: str) -> str:
    return f"{status}\n{body}"


def _unwrap(payload: str) -> tuple[int, str]:
    head, _, body = payload.partition("\n")
    try:
        return int(head), body
    except ValueError:
        return 0, payload


# --------------------------------------------------------------------------------- links

def _kind_for(score: int) -> str:
    if score >= 10:
        return "leadership"
    if score >= 8:
        return "officers"
    if score >= 6:
        return "team"
    return "about"


def candidate_links(homepage_html: str, base_url: str, limit: int = 6) -> list[tuple[int, str]]:
    """Rank same-host links that plausibly lead to a page naming executives.

    Returns (marker_score, url), strongest first. Same-host only: a leadership link
    pointing off-site is an aggregator profile, not the company own page.
    """
    parsed = urllib.parse.urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    host = host_of(base_url)
    found: dict[str, int] = {}

    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""",
                         homepage_html, re.I | re.S):
        href, text = m.group(1).strip(), re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = urllib.parse.urljoin(base + "/", href).split("#")[0].rstrip("/")
        if host_of(url) != host:
            continue
        if re.search(r"(?i)\.(pdf|jpe?g|png|gif|zip|mp4|docx?|xlsx?)$", url):
            continue
        # Normalise the scheme before de-duplicating. Sites mix absolute http:// and
        # https:// links to their own pages, and without this the same page occupies two
        # slots in a limited candidate budget.
        url = re.sub(r"^http://", "https://", url)
        # Score on the link text plus the LAST path segment first, and only fall back to
        # the full path at a heavy discount.
        #
        # The discount is what makes sibling pages rank correctly. McShane publishes its
        # executives at /who-we-are/team-members alongside /who-we-are/history,
        # /who-we-are/why-mcshane and /who-we-are/giving-back. Scoring the whole path gives
        # all four the same 6 they inherit from the shared /who-we-are prefix, and the real
        # page lost the length tiebreak and was never fetched. The leaf segment is what
        # distinguishes them.
        path = urllib.parse.urlparse(url).path
        leaf = path.rstrip("/").rsplit("/", 1)[-1]
        if CAREERS_MARKER.search(f"{text} {path}") or NEWS_MARKER.search(path):
            continue
        best = 0
        for score, rx in LEADERSHIP_MARKERS:
            if rx.search(f"{text} {leaf}"):
                best = score
                break
        if not best:
            for score, rx in LEADERSHIP_MARKERS:
                if rx.search(path):
                    best = max(1, score // 3)   # inherited from an ancestor segment only
                    break
        if best:
            found[url] = max(found.get(url, 0), best)

    if base_url.rstrip("/") in found:
        del found[base_url.rstrip("/")]          # a self-link is not a candidate
    ranked = sorted(found.items(), key=lambda kv: (-kv[1], len(kv[0])))
    return [(score, url) for url, score in ranked[:limit]]


# ------------------------------------------------------------------------------- search

def find_homepage(search: BraveSearch, company_name: str, state: str = "",
                  floor: float = 0.34) -> tuple[str, list[dict]]:
    """Resolve a company to its own website. Returns (url, rejection_log).

    Scores the *domain* against the company name tokens rather than trusting rank. A
    domain is a compressed, punctuation-free rendering of a name, so scoring is on token
    containment within the domain string: "fhpaschen.com" contains PASCHEN,
    "wadsbro.com" contains neither WADSWORTH nor BROTHERS in full and is correctly
    refused rather than guessed at.
    """
    query = f"{company_name} {state} official website".strip()
    rejected: list[dict] = []
    try:
        results = search.search(query, count=10)
    except SearchError as e:
        raise
    name_tokens = [t for t in tokens(company_name) if len(t) > 2]
    if not name_tokens:
        return "", rejected

    best, best_score = "", 0.0
    for r in results:
        host = r.host
        if host in AGGREGATOR_HOSTS or any(host.endswith("." + a) for a in AGGREGATOR_HOSTS):
            rejected.append({"url": r.url, "reason": "aggregator_host"})
            continue
        if re.search(r"(?i)(wikipedia|facebook|youtube|indeed|glassdoor|yelp|bbb\.org|"
                     r"mapquest|yellowpages|dnb\.com|manta\.com)", host):
            rejected.append({"url": r.url, "reason": "directory_host"})
            continue
        flat = re.sub(r"[^a-z0-9]", "", host.split(".")[0])
        hits = sum(1 for t in name_tokens if t.lower() in flat)
        score = hits / len(name_tokens)
        if score > best_score:
            best, best_score = f"https://{host}", score
        if score < floor:
            rejected.append({"url": r.url, "reason": f"domain_score {score:.2f} < {floor}"})

    if best_score < floor:
        return "", rejected
    return best, rejected


def search_leadership_page(search: BraveSearch, company_name: str,
                           host: str) -> tuple[list[tuple[int, str]], list[dict]]:
    """Last-resort discovery: ask the index for a leadership page on the company own host.

    Off-host results are recorded as aggregator candidates and returned in the rejection
    log rather than followed, so a later version has the list without this one acting on
    it.
    """
    query = f'site:{host} (leadership OR "executive team" OR "our team" OR management)'
    aggregators: list[dict] = []
    results = search.search(query, count=10)
    ranked: dict[str, int] = {}
    for r in results:
        if r.host != host:
            if r.host in AGGREGATOR_HOSTS:
                aggregators.append({"url": r.url, "reason": "aggregator_not_read_in_v1_0"})
            continue
        path = urllib.parse.urlparse(r.url).path
        if NEWS_MARKER.search(path) or CAREERS_MARKER.search(path):
            continue
        blob = f"{r.title} {path}"
        for score, rx in LEADERSHIP_MARKERS:
            if rx.search(blob):
                ranked[r.url] = max(ranked.get(r.url, 0), score)
                break
    out = sorted(ranked.items(), key=lambda kv: (-kv[1], len(kv[0])))
    return [(s, u) for u, s in out[:4]], aggregators
