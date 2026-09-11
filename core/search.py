"""
Brave Search API client, shared by every harness that has to *find* a page rather than
being told where it is.

WHY THIS IS A CORE MODULE AND NOT PER-HARNESS
---------------------------------------------
Three harnesses need web search -- H-EXECID-01 (find a leadership page), H-EXECVOICE-01
(find podcast/interview appearances), H-FIRSTPARTY-01 (find press coverage). Putting the
client here means one place enforces quota accounting, the cache-as-evidence-archive
discipline, and the failure taxonomy, rather than three harnesses each inventing their own
and drifting.

SEARCH IS DISCOVERY, NEVER EVIDENCE
-----------------------------------
Nothing this module returns is ever cited in an Observation. A search result is a pointer;
the claim is always made against the page the pointer leads to, fetched and read
separately. This mirrors the role H-FMCSA-01 gives the FMCSA census endpoint -- used only
to resolve a name to a USDOT number, recorded in `Harness_Sources` as `resolution_only`,
never cited. A search snippet is a search engine summary of somebody else's page, and
building evidence on it would put an unaccountable intermediary inside the provenance
chain.

The corollary matters for the recurring false-confidence failure mode: search results are
*candidates to be checked*, and a caller that treats rank-1 as the answer has reintroduced
the same bug in a new place. Callers score results against the company they are looking
for and refuse below a floor, exactly as `core/resolution.py` does for entity resolution.

QUOTA AND CACHING
-----------------
Every response is archived through `core.cache.DatedCache`, so a re-run inside the same
day costs nothing and an offline replay reproduces the run exactly (convention 29). The
default pause is one second per query, which the free tier requires and the paid tiers
gain nothing by beating.

`SearchError` carries the `failure_stage` / `failure_category` the caller should record,
so quota exhaustion is never silently indistinguishable from "found nothing" -- the
distinction convention 6a exists to protect.
"""

from __future__ import annotations

import gzip
import html as _html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from core.cache import DatedCache, slug
from core.config import require_key

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_COUNT = 10
TIMEOUT = 30


class SearchError(RuntimeError):
    """A search that could not be performed, carrying its Attempts routing.

    The distinction between "the search ran and found nothing" and "the search never ran"
    is the whole point. The first is `absent_confirmed` territory; the second is
    `not_covered`, and conflating them writes false absence into the evidence base.
    """

    def __init__(self, message: str, failure_stage: str = "discovery",
                 failure_category: str = "source_unavailable",
                 fix_class: str = "transient"):
        super().__init__(message)
        self.failure_stage = failure_stage
        self.failure_category = failure_category
        self.fix_class = fix_class


@dataclass
class SearchResult:
    title: str
    url: str
    description: str
    age: str = ""

    @property
    def host(self) -> str:
        return urllib.parse.urlparse(self.url).netloc.lower().removeprefix("www.")


def _plain(text: str) -> str:
    """Brave marks query terms with <strong> tags inside titles and descriptions."""
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", text))).strip()


class BraveSearch:
    """Cached, rate-limited Brave Search client.

    `cache_root` should be the harness's own `raw/` directory, so the search responses
    that justified a run are archived beside the pages that run read.
    """

    def __init__(self, cache_root: Path | str, offline: bool = False,
                 retrieval_date: str | None = None, pause_seconds: float = 1.0,
                 country: str = "us"):
        self.cache = DatedCache(cache_root, offline=offline,
                                retrieval_date=retrieval_date, pause_seconds=pause_seconds)
        self.country = country
        self.query_count = 0          # queries actually sent to Brave (billable)
        self.cached_count = 0         # queries served from the archive
        self._key = None

    def _api_key(self) -> str:
        # Resolved lazily so an offline replay of an archived run needs no credential at
        # all. The archive is the source; requiring a key to read it would make old runs
        # unreproducible the day the key is rotated.
        if self._key is None:
            self._key = require_key(
                "BRAVE_API_KEY",
                "Web search is the discovery mechanism for H-EXECID-01, H-EXECVOICE-01 "
                "and H-FIRSTPARTY-01.")
        return self._key

    def search(self, query: str, count: int = DEFAULT_COUNT,
               freshness: str = "") -> list[SearchResult]:
        """Run one query. Raises `SearchError` if the query could not be performed."""
        params = {"q": query, "count": count, "country": self.country,
                  "result_filter": "web"}
        if freshness:
            params["freshness"] = freshness
        key = "q_" + slug(f"{query}_{count}_{freshness}", maxlen=120)

        def fetch() -> str:
            req = urllib.request.Request(
                ENDPOINT + "?" + urllib.parse.urlencode(params),
                headers={"Accept": "application/json",
                         "Accept-Encoding": "gzip",
                         "X-Subscription-Token": self._api_key()})
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    return raw.decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                raw = e.read()
                if e.headers.get("Content-Encoding") == "gzip":
                    try:
                        raw = gzip.decompress(raw)
                    except OSError:
                        pass
                # Printable only: a compressed error body pasted into an Attempts row put
                # control characters into the workbook and killed a 79-company run at
                # close (session 15, openpyxl IllegalCharacterError).
                body = "".join(ch for ch in raw[:300].decode("utf-8", "replace")
                               if ch.isprintable())[:200]
                if e.code == 402:
                    # Payment Required: the plan's monthly quota, i.e. OUR limit, not the
                    # source refusing us. Transient, and not an ACCESS_BOUNDED signal.
                    raise SearchError(
                        f"Brave monthly quota exhausted (HTTP 402, our plan's limit): {body}",
                        failure_category="source_unavailable", fix_class="transient") from e
                if e.code == 429:
                    raise SearchError(
                        f"Brave rate limit / quota exhausted (HTTP 429): {body}",
                        failure_category="access_blocked", fix_class="transient") from e
                if e.code in (401, 403):
                    raise SearchError(
                        f"Brave rejected the API key (HTTP {e.code}): {body}",
                        failure_category="access_blocked",
                        fix_class="source_limitation") from e
                raise SearchError(f"Brave HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise SearchError(f"Brave unreachable: {e.reason}") from e

        try:
            payload, from_cache = self.cache.get(key, ".json", fetch)
        except SearchError:
            raise
        except RuntimeError as e:                      # offline with nothing archived
            raise SearchError(str(e), failure_category="source_not_found",
                              fix_class="code_change") from e

        if from_cache:
            self.cached_count += 1
        else:
            self.query_count += 1

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise SearchError(f"Brave returned unparseable JSON: {e}",
                              failure_stage="extraction",
                              failure_category="parse_failure",
                              fix_class="code_change") from e

        out = []
        for item in (data.get("web") or {}).get("results") or []:
            url = item.get("url") or ""
            if not url:
                continue
            out.append(SearchResult(
                title=_plain(item.get("title") or ""),
                url=url,
                description=_plain(item.get("description") or ""),
                age=str(item.get("age") or item.get("page_age") or ""),
            ))
        return out

    def stats(self) -> dict:
        return {"queries_sent": self.query_count, "queries_from_cache": self.cached_count}


def host_of(url: str) -> str:
    """Host minus `www.`. Deliberately not a public-suffix parse.

    A real eTLD+1 needs the public suffix list, which is not vendored here. Callers use
    this to ask "is this URL on the company own site", and they answer that by comparing
    against the company known homepage host rather than by inferring an organisation from
    a domain string.
    """
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
