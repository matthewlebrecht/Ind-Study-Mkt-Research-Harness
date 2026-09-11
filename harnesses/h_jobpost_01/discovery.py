"""
Careers-URL and ATS discovery, on the company's own domain only.

WHY THIS EXISTS
---------------
H-JOBPOST-01 v1.0 shipped with three hand-configured companies and a `gaps` list. That is
workable for a 7-company pilot and impossible for 108: the Anvil-100 have no careers URL on
file at all, so without discovery the harness walks the whole universe and reports "no
source configured" 104 times, which is what its 2026-08-30 run did.

OWN DOMAIN ONLY, AND THAT IS A RULE RATHER THAN A DEFAULT
---------------------------------------------------------
A third-party job board is never accepted as a company's careers page. Three reasons, and
the first is the one that matters:

1. `source_grade = A` on this harness's rows means "first-party, published by the company,
   attributable to its own careers page". A row citing an aggregator is not grade A, and
   silently substituting one would misgrade every observation it produced. This is the
   H-SELLERCONTENT-01 failure exactly -- v1.0 reported 100% coverage while half its
   providers had been read off homepage-discovery substitutes rather than their actual
   service pages (convention 16's list).
2. LinkedIn and Indeed both refuse this crawler identity outright (probed 2026-09-01:
   LinkedIn `Disallow: /`, Indeed `/jobs`, `/viewjob?` and `/cmp/`), so the substitution
   is not available even where it would be tempting.
3. An aggregator's listing for a company is not the company's own statement about what it
   is hiring for -- it is a third party's index of it, with its own staleness and its own
   inclusion rules.

WHAT DISCOVERY REFUSES TO DO
----------------------------
It does not guess. A candidate careers URL is accepted only if it is reachable on the
company's own registrable domain AND the page looks like a careers page. Where an ATS is
detected but no adapter exists, that is recorded as a NAMED gap ("greenhouse detected, no
adapter") rather than a silent miss -- a specific gap is actionable and a generic one is
not, and convention 5 says the denominator has to survive.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field

from core.cache import slug

# Paths worth trying on a company's own domain, most conventional first. Kept short on
# purpose: every entry is an HTTP request against a live origin, and a long speculative
# list is indistinguishable from scanning.
CANDIDATE_PATHS = (
    "/careers", "/careers/", "/career", "/jobs", "/about/careers",
    "/about-us/careers", "/company/careers", "/join-us", "/careers/open-positions",
    "/who-we-are/careers", "/careers/jobs",
)

# ATS fingerprints, matched against the careers page's HTML (its links, mostly).
#
# Ordered most specific first. Each is a host or path fragment that only that ATS serves,
# never a bare product name: "workday" appears in ordinary prose ("a typical workday"),
# while `myworkdayjobs.com` cannot. That is convention 31 applied to vendor detection --
# the same lesson as the classifier's `Oracle` term, in a different place.
ATS_FINGERPRINTS = (
    ("workday",         r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com"),
    # Not `login|www|secure`: those are iCIMS's own shared hosts, present on any
    # page that merely links to an iCIMS sign-in. The pilot captured
    # login.icims.com as Prime Inc.'s tenant and the adapter then 404ed against
    # it -- convention 16, a loose pattern in a new place.
    ("icims",           r"(?<![a-z0-9.-])(?!login\.|www\.|secure\.)([a-z0-9-]+)\.icims\.com"),
    ("paylocity",       r"recruiting\.paylocity\.com"),
    ("greenhouse",      r"(?:boards|job-boards)(?:-api)?\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)"),
    ("lever",           r"jobs\.lever\.co/([a-z0-9_-]+)"),
    ("smartrecruiters", r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)"),
    ("jobvite",         r"jobs\.jobvite\.com/([a-z0-9_-]+)"),
    ("ultipro",         r"([a-z0-9-]+)\.(?:recruiting\d*\.)?ultipro\.com"),
    # Session 10 item 7: capture the ADP client id so the public requisition endpoint can
    # be called; the bare-host form stays as a fallback fingerprint with no key.
    ("adp",             r"workforcenow\.adp\.com/[^\"'\s]*?cid=([0-9a-f]{8}-[0-9a-f-]{27})"),
    ("adp",             r"(?:workforcenow|recruiting)\.adp\.com"),
    ("paycom",          r"paycomonline\.net"),
    ("dayforce",        r"([a-z0-9-]+)\.dayforcehcm\.com"),
    ("taleo",           r"([a-z0-9-]+)\.taleo\.net"),
    ("brassring",       r"([a-z0-9-]+)\.brassring\.com"),
    ("jazzhr",          r"([a-z0-9-]+)\.applytojob\.com"),
    ("bamboohr",        r"([a-z0-9-]+)\.bamboohr\.com"),
    ("applicantpro",    r"([a-z0-9-]+)\.applicantpro\.com"),
    ("isolved",         r"([a-z0-9-]+)\.isolvedhire\.com"),
    ("clearcompany",    r"([a-z0-9-]+)\.clearcompany\.com"),
    ("tenstreet",       r"(?:tenstreet\.com|intelliapp\.driverapponline\.com)"),
    ("driverreach",     r"([a-z0-9-]+)\.driverreach\.com"),
)

# Adapters that can actually read postings. Everything else is detected and reported as a
# named gap -- knowing a company runs Taleo is genuinely more useful than "no source", and
# it is the input to deciding which adapter to build next.
IMPLEMENTED_ATS = {"workday", "icims", "paylocity", "greenhouse", "lever",
                   # session 10 item 7
                   "adp", "inline"}

# Boards whose HOST refuses this crawler identity by robots.txt (probed 2026-09-03, session
# 10). A company on one of these is recorded as access_blocked / source_limitation -- the
# source's own decision (convention 38) -- not as "no adapter", which would misroute the
# fix. Dayforce: 6 companies; UltiPro/UKG: 4.
ROBOTS_REFUSED_BOARDS = {
    "dayforce": "https://jobs.dayforcehcm.com/en-US/robots-probe",
    "ultipro": "https://recruiting2.ultipro.com/robots-probe",
}

# ---- inline-list parser (session 10 item 7) -------------------------------------------
# A careers page with no ATS that lists postings inline in server HTML. The audit's loose
# heuristic (class names containing "position"/"listing") over-counted this bucket to 12:
# re-measured with THIS rule against the archive, 1 of 83 unreadable pages carried a real
# list (OnTrac, 4 titles); the rest were careers-section navigation ("Benefits and Perks").
# The rule: anchors whose href looks like a job detail, whose text is title-length and not
# navigation, at least INLINE_MIN of them. Below the floor the page is not a list.
INLINE_MIN = 3
_INLINE_HREF = re.compile(
    r"(/jobs?/[^/\"']+|/careers?/[^/\"']{4,}|/positions?/|/openings?/|/opportunit|"
    r"[?&](?:job|jobid|req|posting)=|/job-|/employment/[^/\"']{4,})", re.I)
_INLINE_NAV = re.compile(
    r"^(careers?|jobs?|home|about|contact|apply now|view all|search (?:jobs|roles|careers)|"
    r"open positions|join (?:our|the) team|benefits|benefits (?:and|&) perks|internships?|"
    r"culture|why [a-z .&]+|learn more|read more|apply|details|see all jobs|explore "
    r"(?:paths|open positions)|locations|life at [a-z .&]+|our culture|key roles|"
    r"early career professionals|experienced professionals|veterans|training|"
    r"opportunities|career opportunities|recent graduates|student program)$", re.I)


# A real posting title names a ROLE and usually a place or level; a careers-section
# category page ("Estimators", "Learn More Corporate", "Craft Professionals") names
# neither. The first live run of this adapter admitted three sites' navigation as postings;
# the rule now needs a role word in a multi-word title, and at least half of the admitted
# anchors to carry a location/level qualifier (a comma, dash, pipe, bracket or digit).
_INLINE_ROLE = re.compile(
    r"\b(manager|engineer|technician|specialist|driver|analyst|director|supervisor|"
    r"coordinator|associate|clerk|operator|mechanic|superintendent|estimator|accountant|"
    r"developer|architect|planner|scheduler|foreman|electrician|welder|nurse|"
    r"representative|lead|intern|administrator|assistant|dispatcher|controller|buyer|"
    r"inspector|laborer|apprentice|officer|recruiter|designer|scientist|programmer)\b", re.I)
_INLINE_QUALIFIER = re.compile(r"[,|()\-–/]|\d")
_INLINE_LEADING_NAV = re.compile(
    r"^(learn more|join|all |view|see |information|why |our |about|meet |explore|search)", re.I)


def inline_postings(html: str, base_url: str) -> list[tuple[str, str]]:
    """(title, absolute_url) for every posting-shaped anchor on a careers page, or [] when
    the anchors look like a careers section's navigation rather than a listing."""
    import html as _html
    out: dict[str, str] = {}
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html or "",
                         re.I | re.S):
        href, body = m.group(1), m.group(2)
        text = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
        if not _INLINE_HREF.search(href):
            continue
        if not (8 <= len(text) <= 90) or _INLINE_NAV.match(text) or _INLINE_LEADING_NAV.match(text):
            continue
        if len(text.split()) < 2 or not _INLINE_ROLE.search(text):
            continue
        if re.search(r"\.(pdf|jpe?g|png|docx?)$", href, re.I):
            continue
        absolute = urllib.parse.urljoin(base_url, href).split("?")[0]
        out.setdefault(absolute, text)
    items = list(out.items())
    qualified = sum(1 for _, t in items if _INLINE_QUALIFIER.search(t))
    if len(items) < INLINE_MIN or qualified * 2 < len(items):
        return []
    return items

# A page has to look like a careers page before its URL is accepted. A 200 is not enough:
# many sites serve a soft-404 marketing page for any unknown path, which would let
# discovery record a careers URL that lists nothing and never says so.
CAREERS_MARKERS = re.compile(
    r"\b(careers?|job openings?|open positions?|current openings?|join our team|"
    r"employment opportunit|apply now|view (all )?jobs)\b", re.I)

SOFT_404 = re.compile(r"\b(page not found|404 error|cannot be found|no longer exists)\b",
                      re.I)


def registrable(host: str) -> str:
    """Best-effort registrable domain, for own-domain comparison.

    Deliberately naive -- last two labels -- and that is safe here because it is used only
    to compare a link against the company's OWN website, never to identify a company.
    Getting it slightly wrong for a multi-part TLD costs a rejected candidate, which is
    the direction convention 12 says to fail in.
    """
    host = (host or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


@dataclass
class Discovery:
    company_id: str
    careers_url: str = ""
    ats: str = ""
    ats_key: str = ""          # tenant/board token, where the fingerprint captured one
    cxs_url: str = ""          # workday only
    host: str = ""             # icims only
    ccid: str = ""             # adp only: the career-center id beside the client id
    evidence: str = ""
    tried: list = field(default_factory=list)
    rejected: list = field(default_factory=list)

    @property
    def usable(self) -> bool:
        if self.ats == "adp" and not self.ats_key:
            return False           # host seen, client id not captured: nothing to call
        return bool(self.careers_url and self.ats in IMPLEMENTED_ATS)

    def as_config(self) -> dict:
        cfg = {"ats": self.ats, "careers_url": self.careers_url,
               "discovered": self.evidence}
        if self.cxs_url:
            cfg["cxs_url"] = self.cxs_url
        if self.host:
            cfg["host"] = self.host
        if self.ats_key:
            cfg["board"] = self.ats_key
        if self.ats == "adp":
            cfg["cid"] = self.ats_key
            cfg["ccid"] = self.ccid or "19000101_000001"
        return cfg


def detect_ats(html: str, page_url: str = "") -> tuple:
    """(ats_name, captured_key) for the first fingerprint present, else ('', '')."""
    hay = f"{html}\n{page_url}"
    for name, pattern in ATS_FINGERPRINTS:
        m = re.search(pattern, hay, re.I)
        if m:
            groups = [g for g in (m.groups() or ()) if g]
            return name, (groups[0] if groups else "")
    return "", ""


def looks_like_careers(html: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", html or "")
    if SOFT_404.search(text[:4000]):
        return False
    return bool(CAREERS_MARKERS.search(text))


def candidate_urls(website: str) -> list:
    """Own-domain candidate careers URLs, in try order."""
    if not website:
        return []
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    parsed = urllib.parse.urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return [base + path for path in CANDIDATE_PATHS]


def careers_links_on(html: str, page_url: str, website: str) -> list:
    """Own-domain links from a homepage whose text or href mentions careers/jobs.

    The fallback for companies whose careers page is not at any conventional path. Links
    off the company's own registrable domain are dropped here rather than followed: that
    is the aggregator-substitution rule, applied at the only place it can leak in.
    """
    own = registrable(urllib.parse.urlparse(website).netloc)
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                         html or "", re.I | re.S):
        href, label = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        if not re.search(r"career|job|join|employment|opportunit", f"{href} {label}", re.I):
            continue
        absolute = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if registrable(parsed.netloc) != own:
            continue                      # third-party board -- never the careers page
        clean = absolute.split("#")[0]
        if clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out[:6]


def discover(company_id: str, website: str, fetch) -> Discovery:
    """Find a company's own careers page and the ATS behind it.

    `fetch(url, key) -> (html, status)` is injected so the caller owns transport, caching
    and robots compliance. Discovery itself makes no network policy decisions.
    """
    d = Discovery(company_id=company_id)
    if not website:
        d.evidence = "no website on file for this company"
        return d

    def consider(url: str) -> bool:
        html, status = fetch(url, f"discover_{slug(company_id)}_{slug(url)}")
        d.tried.append(f"{url} -> {status}")
        if status != 200 or not html:
            return False
        if not looks_like_careers(html):
            d.rejected.append(f"{url}: 200 but no careers markers (soft 404 or wrong page)")
            return False
        ats, key = detect_ats(html, url)
        d.careers_url, d.ats, d.ats_key = url, ats, key
        if ats == "workday":
            m = re.search(r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)",
                          html, re.I)
            if m:
                tenant, pod, site = m.group(1), m.group(2), m.group(3)
                d.cxs_url = (f"https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/"
                             f"{tenant}/{site}")
        if ats == "icims":
            m = re.search(r"(?<![a-z0-9.-])((?!login\.|www\.|secure\.)[a-z0-9-]+\.icims\.com)",
                          html, re.I)
            if m:
                d.host = m.group(1)
        if ats == "adp":
            m = re.search(r"ccId=(\d+_\d+)", html)
            d.ccid = m.group(1) if m else ""
        if not ats:
            # Session 10 item 7: no ATS surface, but a real inline list?
            listed = inline_postings(html, url)
            if len(listed) >= INLINE_MIN:
                d.ats, d.ats_key = "inline", str(len(listed))
        d.evidence = (f"{_TODAY} — discovered on own domain: {url}"
                      + (f"; ATS fingerprint {ats}" + (f" ({key})" if key else "")
                         if ats else "; no ATS fingerprint in server-rendered HTML"))
        return True

    for url in candidate_urls(website):
        if consider(url):
            return d

    # Fallback: the homepage's own careers links.
    home = website if website.startswith("http") else "https://" + website
    html, status = fetch(home, f"discover_{slug(company_id)}_home")
    d.tried.append(f"{home} -> {status}")
    if status == 200 and html:
        for url in careers_links_on(html, home, website):
            if consider(url):
                return d

    if not d.evidence:
        d.evidence = (f"no careers page found on own domain after "
                      f"{len(d.tried)} candidate(s)")
    return d


_TODAY = ""


def set_stamp(stamp: str) -> None:
    """The retrieval date recorded in discovery evidence, injected by the harness so it
    matches the run's stamp rather than the wall clock (convention 3)."""
    global _TODAY
    _TODAY = stamp
