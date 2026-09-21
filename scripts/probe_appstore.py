#!/usr/bin/env python3
"""
FEASIBILITY PROBE -- is there an app-store footprint to read for this population?

This is NOT a harness. It writes nothing to the workbook: no run row, no attempt, no
observation, no manifest. It answers one question before anyone scopes an instrument --
does a consumer-facing mobile app exist under these companies' names at all, and if so for
whom -- and writes a dated diagnostic.

WHY THE APPLE SEARCH API AND NOT A STORE PAGE
---------------------------------------------
`itunes.apple.com/search` is Apple's own public, documented, unauthenticated search
endpoint. It returns the developer name (`sellerName`) as structured data, which is what the
identity test needs. Google Play publishes no equivalent API; the Play leg is a separate
access decision (see the diagnostic), not something to fake by scraping a search page.

IDENTITY IS THE WHOLE PROBLEM, AS EVERYWHERE ELSE IN THIS PROJECT
-----------------------------------------------------------------
App-store search is a free-text index: "Prime", "Savage", "Summit" and "Clark" all return
dozens of unrelated apps. This probe therefore reuses `core/resolution.py` -- the project's
own scorer, stopwords and floor -- rather than inventing a looser matcher, and applies
convention 11 on top: a company whose name reduces to ONE distinctive token is never matched
on that token alone; its developer name must match exactly. Every rejection is recorded, so
the refusals can be read as evidence rather than taken on trust.

    python scripts/probe_appstore.py                 # all 108 buyers
    python scripts/probe_appstore.py --ids A018,A010 # named companies
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from core import resolution  # noqa: E402

API = "https://itunes.apple.com/search"
UA = "IndStudyHarness/1.0 (academic research; contact matthewlebrecht@gmail.com)"
DEV_FLOOR = 0.55          # core/resolution.DEFAULT_FLOOR -- developer name carries identity
TITLE_FLOOR = 0.75        # an app TITLE is weaker evidence of who published it; ask for more
PAUSE = 0.7               # Apple rate-limits around 20 calls/minute


def sheet_rows(wb, name):
    it = wb[name].iter_rows(values_only=True)
    headers = list(next(it))
    return [dict(zip(headers, r)) for r in it if r and r[0] is not None]


def search(term: str, limit: int = 50) -> list[dict]:
    qs = urllib.parse.urlencode({"term": term, "entity": "software",
                                 "country": "US", "limit": limit})
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("results", [])


def distinctive(name: str) -> list[str]:
    """Name tokens that actually separate one firm from another (stopwords gone, line-of-
    business words dropped) -- the set convention 11 counts."""
    return [t for t in resolution.tokens(name) if t not in resolution.WEAK_TOKENS]


def registrable(url: str) -> str:
    """The registrable domain of a URL, lowercased ('https://www.doterra.com/US/en' ->
    'doterra.com'). Good enough for this population, which is entirely US .com/.net."""
    host = urllib.parse.urlsplit(str(url or "").strip()).netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else ""


def name_is_the_company(company: str, dev: str) -> bool:
    """True when the developer's distinctive token set EQUALS the company's.

    Equality, not containment, so 'Mack Trucks Inc.' {MACK, TRUCKS} never matches 'Mack
    Group' {MACK}. This is a CANDIDATE test, never a hit on its own -- see judge().
    """
    core, dcore = set(distinctive(company)), set(distinctive(dev))
    return bool(core) and core == dcore


def judge(company: str, site: str, app: dict) -> tuple[str, str, float]:
    """(verdict, reason, score). Verdicts: 'company', 'name_only', 'third_party', 'no'.

    ONE THING IS DECISIVE AND NOTHING ELSE IS. If the developer's own website is the
    company's registrable domain, the publisher is the company. Everything else is a
    CANDIDATE for a human, because this project has been burned nine times by a name that
    scored well and referred to somebody else -- and this probe found three more of exactly
    that kind on its first pass ('Sun Oaks', a fitness club, published by a different 'Walsh
    Group'; a Marietta seafood restaurant under 'Cajun Inc'; an email client under 'The NFI
    Group LLC').

    A DIFFERING DEVELOPER DOMAIN IS NOT PROOF OF A DIFFERENT PUBLISHER. Companies ship under
    divisional and brand domains: 'J. R. Simplot Company' publishes from
    simplotgrowersolutions.com and SpartanNash ships its grocery banners from
    shopfamilyfare.com. So a name match with a differing domain is `name_only`, not
    `third_party`; `third_party` is reserved for the case where the name does NOT match the
    publisher at all and only the app's title carries the company's name -- a distributor or
    consultant tool, which is a different finding.
    """
    dev = str(app.get("sellerName") or "")
    title = str(app.get("trackName") or "")
    dev_dom, site_dom = registrable(app.get("sellerUrl")), registrable(site)
    d_score = resolution.score(company, dev)
    t_score = resolution.score(company, title)
    if site_dom and dev_dom and dev_dom == site_dom:
        return "company", f"developer site {dev_dom} is the company's own domain", 1.0
    if name_is_the_company(company, dev):
        where = f"publishes from {dev_dom}" if dev_dom else "no developer URL published"
        return "name_only", (f"developer name {dev!r} matches the company's exactly, but {where} "
                             f"-- needs human confirmation that this is the same firm"), 1.0
    if len(distinctive(company)) > 1 and d_score >= DEV_FLOOR:
        return "name_only", (f"developer {dev!r} scores {d_score:.2f} on name; no domain "
                             f"corroboration -- needs human confirmation"), d_score
    if t_score >= TITLE_FLOOR:
        return "third_party", (f"the app title names the company but the publisher {dev!r} does "
                               f"not -- a third-party/ecosystem app"), t_score
    return "no", f"developer {dev!r} scores {d_score:.2f} < {DEV_FLOOR}", d_score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "market_intel_db.xlsx"))
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default=str(ROOT / "harness_output" / "appstore_probe.json"))
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.db, read_only=True, data_only=True)
    buyers = [c for c in sheet_rows(wb, "Companies")
              if str(c.get("qualification_status")) != "provider_benchmark"]
    if args.ids:
        want = {i.strip() for i in args.ids.split(",") if i.strip()}
        buyers = [c for c in buyers if c["company_id"] in want]
    buyers.sort(key=lambda c: c["company_id"])

    out = []
    for i, c in enumerate(buyers, 1):
        name = str(c["canonical_name"])
        term = resolution.strip_legal_suffix(name)
        rec = {"company_id": c["company_id"], "canonical_name": name, "query": term,
               "industry_primary": c.get("industry_primary"), "website": c.get("website"),
               "accepted": [], "name_only": [], "third_party": [], "rejected": [], "error": None}
        try:
            results = search(term)
        except Exception as e:                                    # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
            results = []
        for app in results:
            verdict, reason, sc = judge(name, str(c.get("website") or ""), app)
            row = {"app": app.get("trackName"), "developer": app.get("sellerName"),
                   "genre": app.get("primaryGenreName"), "released": app.get("releaseDate"),
                   "updated": app.get("currentVersionReleaseDate"),
                   "url": app.get("trackViewUrl"), "score": round(sc, 3), "reason": reason}
            rec[{"company": "accepted", "name_only": "name_only",
                 "third_party": "third_party", "no": "rejected"}[verdict]].append(row)
        # Company-level outcome. `own_app` requires domain-corroborated publisher identity.
        # `name_only_unconfirmed` is NOT a hit: it is the class this project has been burned
        # by nine times, held separately for a human to confirm or refuse.
        if rec["error"]:
            rec["outcome"] = "probe_error"
        elif rec["accepted"]:
            rec["outcome"] = "own_app"
        elif rec["name_only"]:
            rec["outcome"] = "name_only_candidate"
        elif not str(c.get("website") or "").strip():
            rec["outcome"] = "no_company_website_to_corroborate"
        else:
            rec["outcome"] = "no_own_app"
        rec["n_results"] = len(results)
        out.append(rec)
        mark = rec["outcome"] + (f" ({len(rec['accepted'])})" if rec["accepted"] else "")
        if rec["name_only"]:
            mark += f" | {len(rec['name_only'])} name-only"
        if rec["third_party"]:
            mark += f" | {len(rec['third_party'])} third-party"
        print(f"[{i:3d}/{len(buyers)}] {c['company_id']} {name[:38]:38s} "
              f"results={len(results):3d} {mark}{' ERROR ' + rec['error'] if rec['error'] else ''}")
        time.sleep(PAUSE)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    from collections import Counter
    print("")
    print("outcomes:", dict(Counter(r["outcome"] for r in out)))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
