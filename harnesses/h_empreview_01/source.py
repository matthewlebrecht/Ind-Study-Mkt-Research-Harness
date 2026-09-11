"""
Source access for H-EMPREVIEW-01, and the access findings that shaped it.

WHAT WAS MEASURED, 2026-08-31
-----------------------------
Every family-4 source in `docs/source_lists.md` was checked against its published
robots.txt for the crawler identities in `core/robots.py`, and probed live:

    glassdoor.com    robots: Disallow: /        for ClaudeBot / anthropic-ai   + HTTP 403
    indeed.com       robots: Disallow: /cmp/    for ClaudeBot / anthropic-ai   (the reviews path)
    careerbliss.com  robots: Disallow: /        for ClaudeBot
    comparably.com   robots: permitted (no AI-agent group; falls back to *)
    kununu.com       robots: permitted (explicit ClaudeBot group, no disallow rules)

So **both sources this harness was commissioned to read are unavailable to compliant
automated collection**, and not for a reason more engineering can fix. Glassdoor forbids
the whole site to this class of agent; Indeed forbids exactly the `/cmp/` path the reviews
live under while permitting the rest of the site. Selecting a user-agent string that fails
to match their blocklists would be evasion rather than compliance, and an evidence archive
built that way would rest on access the publisher explicitly declined.

Comparably is the one reachable substitute with real US coverage of this population. It is
also fragile: it served content to a slow crawl and then began returning 403 to every HTML
path after roughly fifteen requests, while continuing to serve robots.txt -- the signature
of an edge rate limiter rather than a policy decision. `PAUSE_SECONDS` is therefore set
high and `CircuitBreaker` stops the run rather than walking 108 companies into a wall.

WHY THIS IS RECORDED AS EVIDENCE RATHER THAN SWALLOWED
------------------------------------------------------
Convention 6a: a source the harness was forbidden to read and a source that genuinely held
nothing are different facts, and confusing them writes false absence. Family 4 is the
portfolio's only real instrument for `legacy_constraint` -- the thing employees say and
press releases never do. If this harness quietly returned nothing, a Week 4 reader would be
entitled to conclude that employees are not complaining about systems. They may well be;
this harness is not permitted to look.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

from core.cache import DatedCache, slug
from core.resolution import DEFAULT_FLOOR, score, strip_legal_suffix
from core.robots import RobotsGate, USER_AGENT

TIMEOUT = 25
# Comparably rate-limits aggressively. This is deliberately slower than any other harness
# in the project; the source is fragile and there is no value in being fast.
PAUSE_SECONDS = 6.0

COMPARABLY = "https://www.comparably.com"

# Declared sources and their measured access status. Written into the run log so the
# evidence base records WHY the two highest-availability sources in family 4 contributed
# nothing, rather than leaving a silence for someone to misread.
SOURCE_STATUS = {
    "glassdoor.com": {
        "taxonomy": "4a",
        "status": "policy_blocked",
        "detail": "robots.txt Disallow: / for the ClaudeBot / anthropic-ai crawler "
                  "identities; additionally returns HTTP 403 to any unauthenticated fetch",
    },
    "indeed.com": {
        "taxonomy": "4a",
        "status": "policy_blocked",
        "detail": "robots.txt Disallow: /cmp/ for the ClaudeBot / anthropic-ai crawler "
                  "identities -- company reviews live under /cmp/. The narrower "
                  "Claude-User / Claude-SearchBot groups are not restricted there, but "
                  "an unattended crawl of 108 companies is the crawler profile, not the "
                  "user-initiated one",
    },
    "careerbliss.com": {
        "taxonomy": "4a (substitute)",
        "status": "policy_blocked",
        "detail": "robots.txt Disallow: / for ClaudeBot",
    },
    "comparably.com": {
        "taxonomy": "4a (substitute)",
        "status": "permitted",
        "detail": "no AI-agent group in robots.txt; company review pages permitted under "
                  "the * group. Edge rate limiting observed after sustained access",
    },
}


class CircuitBreaker:
    """Stop the run after N consecutive access failures on one host.

    A rate limiter that has started refusing does not stop refusing because the caller kept
    asking. Walking the remaining companies would produce a long tail of identical
    `access_blocked` attempts that say nothing new, and would keep hitting a host that has
    asked to be left alone.
    """

    def __init__(self, limit: int = 6):
        self.limit = limit
        self.consecutive = 0
        self.tripped = False

    def record(self, ok: bool) -> None:
        self.consecutive = 0 if ok else self.consecutive + 1
        if self.consecutive >= self.limit:
            self.tripped = True


class PageResult:
    def __init__(self, url, status=None, html="", error="", from_cache=False,
                 blocked_reason=""):
        self.url, self.status, self.html = url, status, html
        self.error, self.from_cache = error, from_cache
        self.blocked_reason = blocked_reason

    @property
    def ok(self) -> bool:
        return self.status == 200 and len(self.html) > 2000

    @property
    def robots_blocked(self) -> bool:
        return bool(self.blocked_reason)


class ReviewSiteClient:
    """Fetches review pages, refusing anything robots.txt disallows."""

    def __init__(self, cache: DatedCache, gate: RobotsGate | None = None):
        self.cache = cache
        self.gate = gate or RobotsGate()
        self.breaker = CircuitBreaker()
        # HTTP status of the most recent live fetch, so the caller can tell an
        # access block (403) from a missing profile (404) instead of collapsing
        # both into 'source_not_found'.
        self.last_status = None

    def get(self, url: str) -> PageResult:
        allowed, why = self.gate.check(url)
        if not allowed:
            # Not a fetch failure and not recorded as one. The harness was told not to
            # look, which is a source_limitation with a citable reason.
            return PageResult(url, blocked_reason=why)

        key = "p_" + slug(url.replace("https://", ""), maxlen=110)

        def fetch() -> str:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9"})
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    return f"{r.status}\n" + r.read(3_000_000).decode(
                        r.headers.get_content_charset() or "utf-8", "replace")
            except urllib.error.HTTPError as e:
                return f"{e.code}\n" + e.read(100_000).decode("utf-8", "replace")
            except Exception as e:
                return f"0\n{type(e).__name__}: {e}"

        # Only successful responses are archived.
        #
        # `DatedCache` stores whatever the fetcher returns, which is right for a stable
        # source: a 404 is a fact about the URL worth replaying. It is wrong here. A 403
        # from an edge rate limiter is a fact about the last few minutes, and caching it
        # would make every re-run today replay a transient block as though it were the
        # source's answer -- turning a temporary throttle into permanent negative evidence
        # in the archive.
        path = self.cache.partition / f"{key}.txt"
        from_cache = path.exists()
        if from_cache:
            payload = path.read_text(encoding="utf-8")
        elif self.cache.offline:
            archived = self.cache._archived(f"{key}.txt")
            if archived is None:
                return PageResult(url, error="offline and no archived response")
            payload, from_cache = archived.read_text(encoding="utf-8"), True
        else:
            payload = fetch()
            self.cache.fetch_count += 1
            head = payload.partition("\n")[0]
            if head == "200":
                path.write_text(payload, encoding="utf-8")
            if self.cache.pause_seconds:
                import time
                time.sleep(self.cache.pause_seconds)

        head, _, body = payload.partition("\n")
        try:
            status = int(head)
        except ValueError:
            status = 0
        result = PageResult(url, status=status,
                            html=body if status == 200 else "",
                            error="" if status == 200 else body[:200],
                            from_cache=from_cache)
        if not from_cache:
            self.last_status = status
            self.breaker.record(result.ok)
        return result


# ------------------------------------------------------------------ slug resolution

def candidate_slugs(name: str) -> list[str]:
    """Comparably slugs to try, most likely first. Never a guessed abbreviation."""
    out, seen = [], set()
    for variant in (name, strip_legal_suffix(name)):
        s = re.sub(r"[^A-Za-z0-9 ]+", " ", variant or "").strip()
        s = re.sub(r"\s+", "-", s).lower()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def verify_company(page_name: str, canonical_name: str,
                   floor: float = DEFAULT_FLOOR) -> tuple[bool, float, str]:
    """Does this Comparably profile belong to the company we asked for?

    Scored with `core/resolution.py::score` -- weighted token overlap, never substrings --
    against the name the page itself declares in its schema.org Organization block.

    This is load-bearing and not a formality. Searching Comparably for "Prime Inc."
    returns `comparably.com/companies/cprime`, an unrelated software consultancy that
    shares no token with the query. Convention 31: a common token is not an identity, and
    here even the token is not shared -- rank alone would have accepted it.
    """
    if not page_name:
        return False, 0.0, "profile page declares no company name"
    s = score(canonical_name, page_name)
    if s < floor:
        return False, s, (f"profile is for {page_name!r}, which scores {s} against "
                          f"{canonical_name!r} (floor {floor})")
    return True, s, ""


def slug_of(url: str) -> str:
    m = re.search(r"/companies/([^/?#]+)", url or "")
    return m.group(1) if m else ""


def reviews_url(company_slug: str) -> str:
    return f"{COMPARABLY}/companies/{company_slug}/reviews"
