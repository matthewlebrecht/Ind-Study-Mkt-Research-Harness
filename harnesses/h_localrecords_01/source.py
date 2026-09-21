"""
Shared access for H-LOCALRECORDS-01's four sub-scopes.

WHY ONE ACCESS LAYER
--------------------
The four sub-scopes read four kinds of fragmented public record (state WARN lists, city
open-data permits, a Legistar council API, archived homepages) whose access problems are the
same problems: a robots.txt policy per host, rate limits, bot-protection challenges, and
responses that must be archived by date so a row can be defended later. Four standalone
harnesses would each have re-implemented them, and each would have got one of them wrong
in its own way (convention 36: a lookup that answers about the wrong thing). So they share:

  * robots.txt checked per host under the harness identity, refusal recorded as the
    source's decision (`access_blocked`, source_refusal);
  * a bot-protection challenge recognised as the source's defence, never worked around
    (Missouri's WARN page serves Incapsula, Minnesota's redirects to perfdrive -- both
    measured 2026-09-13);
  * backoff on 429 / 5xx, and a 4xx other than 429 treated as our own malformed request;
  * the dated response archive, keyed on a fingerprint of the request (convention 36:
    a cache key that does not change when the request changes is a stale answer).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from urllib.parse import urlencode, urlparse

import requests

from core.attempts import access_detail
from core.cache import DatedCache, slug
from core.robots import RobotsGate

UA = "Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; +independent study, contact via repo)"
TIMEOUT = (15, 90)

# Literal markers of bot-protection interstitials, measured on this crawl. Specific phrases,
# not a bare "blocked" (convention 16 in the layer whose job is attribution).
BOT_CHALLENGE_RE = re.compile(
    r"_Incapsula_Resource|validate\.perfdrive\.com|/cdn-cgi/challenge-platform|"
    r"Attention Required! \| Cloudflare|<title>Just a moment\.\.\.</title>", re.I)


class AccessError(RuntimeError):
    def __init__(self, message: str, failure_category: str = "source_unavailable",
                 fix_class: str = "transient", failure_stage: str = "fetch"):
        super().__init__(message)
        self.failure_category = failure_category
        self.fix_class = fix_class
        self.failure_stage = failure_stage


class Source:
    def __init__(self, root, offline: bool, stamp: str, pause: float = 0.3):
        self.cache = DatedCache(root, offline=offline, retrieval_date=stamp, pause_seconds=pause)
        self.offline = offline
        self.gate = RobotsGate()
        self._robots: dict[str, tuple[bool, str]] = {}

    def robots(self, url: str) -> tuple[bool, str]:
        if self.offline:
            return True, ""
        host = urlparse(url).netloc
        if host not in self._robots:
            self._robots[host] = self.gate.check(url)
        return self._robots[host]

    def _fetch(self, url: str, params: dict | None, binary: bool) -> str:
        ok, why = self.robots(url)
        if not ok:
            raise AccessError(access_detail("source_refusal", f"robots.txt: {why}"),
                              "access_blocked", "source_limitation")
        delay = 3.0
        for attempt in range(4):
            try:
                r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
            except requests.exceptions.RequestException as e:
                if attempt == 3:
                    raise AccessError(f"{type(e).__name__}: {str(e)[:160]}")
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            head = r.text[:6000] if not binary else ""
            if BOT_CHALLENGE_RE.search(r.url) or (head and BOT_CHALLENGE_RE.search(head)):
                raise AccessError(access_detail(
                    "source_refusal", f"bot-protection challenge served for {url} (final URL {r.url[:120]})"),
                    "access_blocked", "source_limitation")
            if r.status_code == 429:
                raise AccessError(access_detail("rate_limited", f"HTTP 429 from {urlparse(url).netloc}"))
            if 400 <= r.status_code < 500:
                raise AccessError(f"HTTP {r.status_code} from {url}",
                                  "access_blocked" if r.status_code in (401, 403) else "source_drift_detected",
                                  "source_limitation" if r.status_code in (401, 403) else "code_change")
            if r.status_code >= 500:
                raise AccessError(f"HTTP {r.status_code} from {url}")
            body = base64.b64encode(r.content).decode() if binary else r.text
            return json.dumps({"status": r.status_code, "url": r.url, "binary": binary, "body": body})
        raise AccessError(f"{url} did not answer after retries")

    def get(self, url: str, params: dict | None = None, key: str = "", binary: bool = False):
        """(final_url, text or bytes). Archived under today's partition; offline replays."""
        fp = hashlib.sha1(json.dumps([url, params, binary], sort_keys=True).encode()).hexdigest()[:16]
        name = f"{slug(key or urlparse(url).netloc + urlparse(url).path, 60)}_{fp}"
        try:
            payload, _ = self.cache.get(name, ".json", lambda: self._fetch(url, params, binary))
        except RuntimeError as e:
            if isinstance(e, AccessError):
                raise
            raise AccessError(f"offline and not archived: {e}")
        d = json.loads(payload)
        body = base64.b64decode(d["body"]) if d.get("binary") else d["body"]
        return d.get("url", url), body

    def get_json(self, url: str, params: dict | None = None, key: str = ""):
        final, body = self.get(url, params, key)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise AccessError(f"non-JSON answer from {final[:120]} -- a failure, never an empty result",
                              "source_drift_detected", "code_change")


def soql_url(base: str, dataset: str, params: dict) -> str:
    return f"{base}/resource/{dataset}.json?" + urlencode(params)
