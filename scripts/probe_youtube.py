#!/usr/bin/env python3
"""
FEASIBILITY PROBE -- is a company YouTube channel a signal worth an instrument?

Not a harness. Writes nothing to the workbook: no run row, no attempt, no observation, no
manifest. Output: harness_output/youtube_probe.json and a dated diagnostic.

ROBOTS FIRST, AND IT DECIDES THE DESIGN
---------------------------------------
youtube.com/robots.txt (read 2026-09-16) disallows, for every crawler, `/results` (search),
`/youtubei/` (the internal API the site's own pages call) and `/feeds/videos.xml`. So this
probe NEVER searches YouTube for a company name. Channel pages (`/@handle`, `/channel/ID`,
`/c/`, `/user/`) and their `/videos` tab are not disallowed and are the only YouTube paths
fetched; robots.txt is re-read at start and a disallowed path is refused, not requested.

IDENTITY RUNS FROM THE COMPANY TO THE CHANNEL
---------------------------------------------
Discovery reads the company's own homepage, as H-EXECID-01 archived it (no new fetch), for
links to YouTube. A channel the company links from its own site is the company's channel by
the company's own statement -- a stronger test than the reverse (a channel whose "links"
section names a domain), which is also unreachable here because YouTube serves those links
through the disallowed `/youtubei/` path. The app-store probe's first pass accepted name
matches and admitted a fitness club, a seafood restaurant and an email client; no name match
alone admits anything here.

Three things a homepage YouTube link can be besides the company's channel, each handled:
  * an embedded or linked VIDEO (`/watch`, `/embed`, `youtu.be`) -- possibly someone else's.
    Recorded as `video_link_only`; the channel behind it is not inferred.
  * a theme PLACEHOLDER (`https://youtube.com/`, `youtube.com/#`) -- recorded, not a channel.
  * a channel that is not the company's (a parent, a vendor, a trade body). The fetched
    channel title is scored against the company name and a low score is flagged
    `channel_name_mismatch` for a human -- flagged, never silently accepted or dropped.

    python scripts/probe_youtube.py              # all 108 buyers
    python scripts/probe_youtube.py --ids A018   # named companies
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import time
import urllib.robotparser
from collections import Counter
from pathlib import Path

import openpyxl
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import resolution  # noqa: E402
from harnesses.h_localrecords_01.harness import archived_homepage  # noqa: E402

UA = "Mkt_Research_Harness/1.0 (independent study feasibility probe; contact matthewlebrecht@gmail.com)"
PAUSE = 2.0
YT_LINK = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)(?:/[^\s\"'<>)]*)?", re.I)
CHANNEL_PATH = re.compile(r"^/(@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+)", re.I)
VIDEO_PATH = re.compile(r"^/(watch|embed|shorts/|live/|v/)", re.I)
NAME_FLOOR = 0.55   # core/resolution.DEFAULT_FLOOR
# YouTube's own single-segment routes, which are not channels (read off the site and robots.txt).
LEGACY_RESERVED = {"iframe_api", "results", "watch", "embed", "feed", "about", "t", "howyoutubeworks",
                   "premium", "kids", "gaming", "music", "account", "signin", "login", "signup",
                   "redirect", "attribution_link", "subscription_center", "channel", "user", "c",
                   "shorts", "live", "playlist", "api", "youtubei", "s", "yts", "creators", "ads"}


def sheet_rows(wb, name):
    it = wb[name].iter_rows(values_only=True)
    headers = list(next(it))
    return [dict(zip(headers, r)) for r in it if r and r[0] is not None]


def classify(link: str) -> tuple[str, str]:
    """(kind, normalized) for one YouTube URL found on a homepage."""
    host_path = re.sub(r"^https?://", "", link, flags=re.I)
    host, _, path = host_path.partition("/")
    path = "/" + path
    path = path.split("?")[0].split("#")[0].rstrip("/")
    if "youtu.be" in host.lower():
        return "video", link
    m = CHANNEL_PATH.match(path)
    if m:
        return "channel", "/" + m.group(1)
    if VIDEO_PATH.match(path):
        return "video", link
    if path.lower().startswith("/playlist"):
        return "playlist", link
    if path in ("", "/"):
        return "placeholder", link
    # Legacy custom URLs (youtube.com/SuffolkConstruction) still resolve to a channel. A single
    # path segment that is not one of YouTube's own top-level routes is treated as one; the
    # fetched page then has to name the company like any other channel.
    seg = path.strip("/")
    if seg and "/" not in seg and seg.lower() not in LEGACY_RESERVED and not seg.lower().endswith((".js", ".php")):
        return "channel", "/" + seg
    return "other", path


def channel_facts(html: str) -> dict:
    """Title, handle, subscriber and video counts and recent upload ages from the SERVED
    HTML of a channel's /videos tab. Everything read is in the initial page; nothing is
    requested from /youtubei/."""
    out = {}
    m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
    out["title"] = m.group(1) if m else None
    m = re.search(r'"canonicalBaseUrl":"(/@[^"]+)"', html) or re.search(r'"vanityChannelUrl":"[^"]*?(/@[^"]+)"', html)
    out["handle"] = m.group(1) if m else None
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/([^"]+)"', html)
    out["channel_id"] = m.group(1) if m else None
    m = re.search(r'"subscriberCountText":\{"simpleText":"([^"]+)"', html) or \
        re.search(r'"content":"([\d.,KMB]+ subscribers?)"', html)
    out["subscribers_text"] = m.group(1) if m else None
    m = re.search(r'"content":"([\d.,KMB]+ videos?)"', html) or re.search(r'"videosCountText":\{"runs":\[\{"text":"([^"]+)"', html)
    out["videos_text"] = m.group(1) if m else None
    # Current layout (2026): each video is a lockupMetadataViewModel carrying its title and a
    # metadata row "N views . <age> ago". The older videoRenderer/publishedTimeText shape is
    # kept as a fallback. Tab order is newest first.
    titles, ages = [], []
    for m in re.finditer(r'"lockupMetadataViewModel":\{"title":\{"content":"((?:[^"\\]|\\.)*)"\}(.{0,400})', html):
        titles.append(m.group(1))
        a = re.search(r'"content":"((?:Streamed )?\d+ \w+ ago)"', m.group(2))
        ages.append(a.group(1) if a else None)
    if not titles:
        titles = re.findall(r'"videoRenderer":\{"videoId":"[^"]+".{0,400}?"title":\{"runs":\[\{"text":"([^"]+)"', html)
        ages = re.findall(r'"publishedTimeText":\{"simpleText":"([^"]+)"', html)
    out["recent_video_titles"] = titles[:30]
    out["recent_upload_ages"] = [a for a in ages if a][:5]
    out["unavailable"] = bool(re.search(r"This channel (does not exist|is not available)|404 Not Found", html))
    return out


def months_from_age(age: str) -> float | None:
    m = re.match(r"(?:Streamed )?(\d+) (second|minute|hour|day|week|month|year)s? ago", age or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n * {"second": 0, "minute": 0, "hour": 0, "day": 1 / 30, "week": 7 / 30,
                "month": 1, "year": 12}[unit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "market_intel_db.xlsx"))
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default=str(ROOT / "harness_output" / "youtube_probe.json"))
    args = ap.parse_args()

    rp = urllib.robotparser.RobotFileParser("https://www.youtube.com/robots.txt")
    rp.read()
    for must_refuse in ("/results?search_query=x", "/youtubei/v1/browse"):
        if rp.can_fetch(UA, "https://www.youtube.com" + must_refuse):
            print(f"robots.txt no longer disallows {must_refuse}; stop and re-read it by hand")
            return 2

    wb = openpyxl.load_workbook(args.db, read_only=True, data_only=True)
    buyers = sorted((c for c in sheet_rows(wb, "Companies")
                     if str(c.get("qualification_status")) != "provider_benchmark"),
                    key=lambda c: c["company_id"])
    if args.ids:
        want = {i.strip() for i in args.ids.split(",")}
        buyers = [c for c in buyers if c["company_id"] in want]

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    out, fetched = [], 0
    for c in buyers:
        name = str(c["canonical_name"])
        rec = {"company_id": c["company_id"], "canonical_name": name, "website": c.get("website"),
               "homepage_archive_date": None, "links": {}, "channels": [], "outcome": None}
        arch = archived_homepage(c)
        if not arch:
            rec["outcome"] = "no_archived_homepage"
            out.append(rec)
            continue
        rec["homepage_archive_date"] = arch[0]
        found: dict[str, set] = {}
        for link in set(YT_LINK.findall(arch[3])):
            kind, norm = classify(link)
            found.setdefault(kind, set()).add(norm)
        rec["links"] = {k: sorted(v) for k, v in found.items()}

        for path in sorted(found.get("channel", ())):
            url = f"https://www.youtube.com{path}/videos"
            ch = {"path": path, "url": url}
            if not rp.can_fetch(UA, url):
                ch["error"] = "refused: robots.txt disallows this path"
                rec["channels"].append(ch)
                continue
            try:
                r = s.get(url, timeout=40)
                fetched += 1
                ch["http"] = r.status_code
                if r.status_code == 200:
                    ch.update(channel_facts(r.text))
                    ch["name_score"] = round(resolution.score(name, ch.get("title") or ""), 3)
            except requests.RequestException as e:
                ch["error"] = f"{type(e).__name__}: {e}"[:160]
            rec["channels"].append(ch)
            time.sleep(PAUSE)

        live = [ch for ch in rec["channels"] if ch.get("http") == 200 and not ch.get("unavailable")]
        if live:
            good = [ch for ch in live if (ch.get("name_score") or 0) >= NAME_FLOOR]
            rec["outcome"] = "channel_confirmed" if good else "channel_name_mismatch"
        elif rec["channels"]:
            rec["outcome"] = "channel_link_dead"
        elif found.get("video") or found.get("playlist"):
            rec["outcome"] = "video_link_only"
        elif found.get("placeholder") or found.get("other"):
            rec["outcome"] = "placeholder_or_other_link"
        else:
            rec["outcome"] = "no_youtube_link"
        ages = [months_from_age(a) for ch in live for a in ch.get("recent_upload_ages", [])[:1]]
        ages = [a for a in ages if a is not None]
        rec["latest_upload_months"] = round(min(ages), 1) if ages else None
        out.append(rec)
        print(f"{c['company_id']:6s} {name[:34]:34s} {rec['outcome']:26s} "
              + "; ".join(f"{ch.get('title')!r} {ch.get('subscribers_text')} "
                          f"last {ch.get('recent_upload_ages', [None])[:1]}" for ch in live)[:110])

    Path(args.out).write_text(json.dumps({"probed_at": _dt.date.today().isoformat(),
                                          "fetches": fetched, "companies": out}, indent=2),
                              encoding="utf-8")
    print("\noutcomes:", dict(Counter(r["outcome"] for r in out)), "| youtube fetches:", fetched)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
