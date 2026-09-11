"""
Wayback Machine CDX access, as a shared utility.

`docs/signal_taxonomy.md` 18a asks for this to be "a reusable verification utility other
harnesses can call, not only a standalone family-18 source", so the mechanics live in core
and H-WAYBACK-01 is a thin harness over them.

Two capabilities, both cheap:

  `snapshots()`   — every archived capture of a URL or path prefix, with status codes.
  `disappeared()` — paths that were archived successfully in an earlier window and have no
                    successful capture since, while the site itself remains live.

The second is the interesting one, and it is the only signal type in the whole taxonomy
that surfaces evidence *no live-page harness can ever see*: a case study that was taken
down, a service line quietly dropped, a careers page that stopped listing a role. Per
`source_lists.md`'s own observation this may matter more for private companies
specifically, since they leave a thinner live footprint to begin with.

WHAT A DISAPPEARANCE DOES AND DOES NOT MEAN
-------------------------------------------
The diff is objective; the interpretation is not. A page can vanish because a programme was
cancelled, or because the marketing site was replatformed and every URL changed. The second
is common and is not a modernization signal at all.

So `disappeared()` reports a *site-wide replatform indicator* alongside each result: if a
large share of a domain's archived paths stop at roughly the same time, the disappearances
are almost certainly a URL migration and the caller should not read them as abandonment.
Callers are expected to degrade the claim accordingly rather than to filter silently.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass

import requests

CDX = "http://web.archive.org/cdx/search/cdx"
# CDX has no total-count field, so a response holding exactly the requested limit is
# indistinguishable from one that happened to end there. snapshots() reports the condition
# rather than letting a truncated capture set be read as a complete history.
CDX_LIMIT = 2000
# Attempts per CDX lookup before giving up and recording the failure as transient.
RETRIES = 4
UA = ("Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; "
      "academic research; +contact via repository)")


@dataclass
class Capture:
    urlkey: str
    timestamp: str          # YYYYMMDDhhmmss
    original: str
    mimetype: str
    status: str
    digest: str

    @property
    def year(self) -> int:
        return int(self.timestamp[:4])

    @property
    def iso(self) -> str:
        t = self.timestamp
        return f"{t[:4]}-{t[4:6]}-{t[6:8]}"

    @property
    def ok(self) -> bool:
        return self.status == "200"

    @property
    def archive_url(self) -> str:
        return f"https://web.archive.org/web/{self.timestamp}/{self.original}"


class WaybackClient:
    def __init__(self, cache, session: requests.Session | None = None):
        self.cache = cache
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = UA

    def snapshots(self, url: str, match_type: str = "domain", from_year: str = "2015",
                  to_year: str = "2026", limit: int = CDX_LIMIT,
                  collapse: str = "urlkey") -> tuple[list[Capture], bool]:
        """All captures for a URL or domain. `collapse=urlkey` gives one row per path.

        Returns (captures, truncated). `truncated` is True when the response holds exactly
        the requested limit, which means older captures exist but were not read.
        """
        params = {
            "url": url, "output": "json", "matchType": match_type,
            "from": from_year, "to": to_year, "limit": str(limit),
        }
        if collapse:
            params["collapse"] = collapse
        from core.cache import slug
        key = slug(f"cdx_{url}_{match_type}_{from_year}_{to_year}_{collapse}")

        def fetch() -> str:
            # CDX rate-limits aggressively and answers with 429/5xx rather than a header.
            # A run without backoff loses most of the universe to `source_unavailable`:
            # the first full pass over 107 companies completed only 28 of 99 lookups and
            # reported 32% coverage, which measured the request pacing rather than the
            # archive. Retry with exponential backoff, and let a genuine failure through to
            # be recorded as transient after the retries are spent.
            delay = 2.0
            last = None
            for attempt in range(RETRIES):
                try:
                    r = self.session.get(CDX, params=params, timeout=60)
                    if r.status_code in (429, 502, 503, 504):
                        last = requests.HTTPError(f"{r.status_code} from CDX")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    r.raise_for_status()
                    return r.text or "[]"
                except requests.RequestException as e:
                    last = e
                    time.sleep(delay)
                    delay *= 2
            raise last if last else requests.RequestException("CDX failed")

        body, _ = self.cache.get(key, ".json", fetch)
        try:
            rows = json.loads(body or "[]")
        except json.JSONDecodeError:
            return [], False
        if not rows:
            return [], False
        header, *data = rows
        idx = {name: i for i, name in enumerate(header)}

        def g(row, name):
            i = idx.get(name)
            return row[i] if i is not None and i < len(row) else ""

        caps = [Capture(urlkey=g(r, "urlkey"), timestamp=g(r, "timestamp"),
                        original=g(r, "original"), mimetype=g(r, "mimetype"),
                        status=g(r, "statuscode"), digest=g(r, "digest"))
                for r in data if g(r, "timestamp")]
        return caps, len(data) >= limit


def disappeared(captures: list[Capture], cutoff_year: int,
                min_paths_for_replatform: int = 8,
                replatform_share: float = 0.6,
                wholesale_share: float = 0.7) -> dict:
    """Split archived paths into still-seen and gone-since-cutoff, and flag replatforms.

    A path counts as disappeared when its most recent successful capture predates
    `cutoff_year` while the domain has successful captures at or after it — i.e. the
    archive kept visiting the site and stopped finding that page.

    `replatform_suspected` is True when most of a domain's disappeared paths share a single
    last-seen year. That pattern is a URL migration, not a set of independent decisions to
    remove content, and a caller reading it as abandonment would be manufacturing a finding
    out of a CMS change.
    """
    by_path: dict[str, list[Capture]] = {}
    for c in captures:
        if c.ok:
            by_path.setdefault(c.urlkey, []).append(c)

    if not by_path:
        return {"live": [], "gone": [], "replatform_suspected": False,
                "site_last_seen": None, "dominant_year": None, "gone_share": 0.0}

    last_of = {k: max(v, key=lambda c: c.timestamp) for k, v in by_path.items()}
    site_last = max(last_of.values(), key=lambda c: c.timestamp)

    live, gone = [], []
    for k, c in last_of.items():
        (gone if c.year < cutoff_year else live).append(c)

    # Two independent indicators, because they catch different migrations.
    #
    # (a) Clustered in time: most disappearances share one year. This is the classic
    #     overnight CMS cutover.
    # (b) Wholesale: most of the site's relevant paths are gone, however the dates fall.
    #     A staged migration spreads over several years and defeats (a) entirely -- Cajun
    #     Industries showed 198 of 254 paths gone with no dominant year, which is a site
    #     rebuild, not 198 separate decisions to withdraw a capability claim.
    #
    # Either one is enough to refuse the claim. The cost of a false positive here is a
    # missed signal; the cost of a false negative is a fabricated finding, and this project
    # has already been bitten once by a rule that manufactured confidence.
    replatform = False
    dominant_year = None
    gone_share = len(gone) / len(last_of) if last_of else 0.0
    if len(gone) >= min_paths_for_replatform:
        years = Counter(c.year for c in gone)
        dominant_year, n = years.most_common(1)[0]
        clustered = (n / len(gone)) >= replatform_share
        wholesale = gone_share >= wholesale_share
        replatform = clustered or wholesale

    return {
        "live": sorted(live, key=lambda c: c.timestamp, reverse=True),
        "gone": sorted(gone, key=lambda c: c.timestamp, reverse=True),
        "replatform_suspected": replatform,
        "site_last_seen": site_last,
        "dominant_year": dominant_year,
        "gone_share": round(gone_share, 3),
    }
