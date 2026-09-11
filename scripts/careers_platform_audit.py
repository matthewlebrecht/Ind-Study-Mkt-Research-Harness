#!/usr/bin/env python3
"""
Platform-signature audit of the careers pages H-JOBPOST-01 cannot read.

    python scripts/careers_platform_audit.py                 # offline: archived HTML only
    python scripts/careers_platform_audit.py --live          # fetch pages not in the archive
    python scripts/careers_platform_audit.py --run HR-0036 --md docs/diagnostics/x.md

WHY THIS EXISTS
---------------
Session 8 measured the readability denominator: 14 of 108 careers pages parse through a
known ATS adapter. The obvious fix -- "build the three adapters for the ATSs we happened
to detect" -- was a placeholder, not a validated pick (session 9 brief, item 2). Before
building anything, this script asks the 94 unreadable companies what they actually run,
from the page itself: script and iframe hosts, embed snippets, "powered by" credits,
apply-link targets, JS-framework markers, and links out to the aggregators that cross-post
them. It is a SIGNATURE audit, not a scrape: one page per company, the page the harness
already found, read for fingerprints and not for postings.

Offline by default: the harness archived every careers page it found under
harness_output/H-JOBPOST-01/raw/<date>/discover_<cid>_<slug(url)>.html, so the audit
reproduces from that archive. `--live` fetches (robots-gated, through the harness's own
client identity) only the pages the archive lacks.

WHAT COMES OUT
--------------
A distribution of platforms across the unreadable set, split into (a) a known ATS with a
public job-board surface -- an adapter is buildable and the count says whether it is worth
it; (b) a JS-rendered careers page with no ATS surface -- needs a renderer or the
aggregator leg, not an adapter; (c) a static page that lists postings inline -- a generic
HTML parser could read it; (d) cross-post links to LinkedIn/Indeed/etc. -- evidence for the
aggregator leg's expected reach. Every company is placed in exactly one primary bucket and
the placement rule is printed, so a bucket is checkable, not a vibe.
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cache import slug  # noqa: E402

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"
RAW = ROOT / "harness_output" / "H-JOBPOST-01" / "raw"
HARNESS = "H-JOBPOST-01"

# Broader than discovery.ATS_FINGERPRINTS on purpose: discovery must only accept a
# fingerprint it can act on; an audit wants to NAME every platform, including ones nobody
# will ever build an adapter for. (name, regex over the whole HTML + URL, has_public_board)
PLATFORMS = [
    ("workday",          r"myworkdayjobs\.com|workday\.com/.*(?:careers|jobs)", True),
    ("icims",            r"[a-z0-9-]+\.icims\.com", True),
    ("paylocity",        r"recruiting\.paylocity\.com", True),
    ("greenhouse",       r"greenhouse\.io", True),
    ("lever",            r"jobs\.lever\.co|lever\.co/", True),
    ("smartrecruiters",  r"smartrecruiters\.com", True),
    ("jobvite",          r"jobvite\.com", True),
    ("ultipro_ukg",      r"ultipro\.com|ukg\.com|recruiting\.ultipro", True),
    ("adp",              r"workforcenow\.adp\.com|recruiting\.adp\.com|myjobs\.adp\.com", True),
    ("paycom",           r"paycomonline\.net", True),
    ("paycor",           r"recruitingbypaycor\.com|paycor\.com/careers|paycor\.com/.*job", True),
    ("dayforce",         r"dayforcehcm\.com|dayforce\.com", True),
    ("taleo_oracle",     r"taleo\.net|oraclecloud\.com/.*(?:hcm|recruit|careers|job)", True),
    ("successfactors",   r"successfactors\.com|jobs\.sap\.com", True),
    ("brassring",        r"brassring\.com", True),
    ("jazzhr",           r"applytojob\.com|jazz\.co|jazzhr\.com", True),
    ("bamboohr",         r"bamboohr\.com", True),
    ("applicantpro",     r"applicantpro\.com", True),
    ("isolved",          r"isolvedhire\.com|isolved\.com", True),
    ("clearcompany",     r"clearcompany\.com", True),
    ("tenstreet",        r"tenstreet\.com|driverapponline\.com|intelliapp", True),
    ("driverreach",      r"driverreach\.com", True),
    ("workable",         r"apply\.workable\.com|workable\.com", True),
    ("breezy",           r"breezy\.hr", True),
    ("recruitee",        r"recruitee\.com", True),
    ("ashby",            r"ashbyhq\.com", True),
    ("rippling",         r"ats\.rippling\.com|rippling\.com/.*jobs", True),
    ("gusto",            r"jobs\.gusto\.com", True),
    ("zoho_recruit",     r"zohorecruit\.com", True),
    ("hirebridge",       r"hirebridge\.com", True),
    ("jobtarget",        r"jobtarget\.com", True),
    ("hiringthing",      r"hiringthing\.com", True),
    ("bullhorn",         r"bullhorn\.com|bullhornstaffing", True),
    ("cornerstone",      r"csod\.com", True),
    ("avature",          r"avature\.net", True),
    ("phenom",           r"phenom\.com|phenompeople", True),
    ("eightfold",        r"eightfold\.ai", True),
    ("careerplug",       r"careerplug\.com", True),
    ("trakstar_hire",    r"hire\.trakstar\.com|recruiterbox", True),
    ("freshteam",        r"freshteam\.com", True),
    ("teamtailor",       r"teamtailor\.com", True),
    ("pinpoint",         r"pinpointhq\.com", True),
    ("comeet",           r"comeet\.com", True),
    ("hcareers",         r"hcareers\.com", True),
    ("ceridian",         r"ceridian\.com", True),
    ("crelate",          r"crelate\.com", True),
    ("exacthire",        r"exacthire\.com", True),
    ("hrmdirect",        r"hrmdirect\.com", True),
    ("newton",           r"newton\.co", True),
    ("paychex",          r"paychex\.com/.*(?:career|job)", True),
    ("jobs_dot_com_generic", r"applicantstack\.com|hireology\.com|jobscore\.com|talentreef\.com|recruiterflow", True),
]

# Cross-post evidence: a link from the company's own careers page to its board profile.
CROSSPOST = [
    ("linkedin", r"linkedin\.com/(?:company/[^\"'/\s]+/jobs|jobs)"),
    ("indeed",   r"indeed\.com/cmp/|indeed\.com/q-|indeed\.com/jobs"),
    ("glassdoor", r"glassdoor\.com/(?:job|Jobs|Job)"),
    ("ziprecruiter", r"ziprecruiter\.com"),
]

# Rendering / site-builder markers. A careers page on one of these with no ATS surface is
# either JS-rendered (needs a renderer) or a hand-maintained list (a generic parser).
FRAMEWORKS = [
    ("react/next",  r"__NEXT_DATA__|data-reactroot|/_next/static|react-dom"),
    ("angular",     r"ng-app|ng-version|angular(?:\.min)?\.js"),
    ("vue/nuxt",    r"__NUXT__|data-v-[0-9a-f]{6,}|vue(?:\.min)?\.js"),
    ("wordpress",   r"wp-content/|wp-json|wp-includes"),
    ("squarespace", r"squarespace\.com|static1\.squarespace"),
    ("wix",         r"wix\.com|wixstatic\.com|parastorage"),
    ("hubspot",     r"hs-scripts\.com|hubspot\.com|hsforms"),
    ("webflow",     r"webflow\.com|webflow\.io"),
    ("drupal",      r"/sites/default/files|drupal"),
    ("sitecore/aem", r"sitecore|/etc\.clientlibs/"),
]

# A page that lists jobs inline in server-rendered HTML: repeated posting-shaped items.
INLINE_POSTING = re.compile(
    r"(?:<(?:li|tr|article|div)[^>]*(?:class|id)=[\"'][^\"']*(?:job|position|opening|career-item|vacanc)[^\"']*[\"'][^>]*>)",
    re.I)
APPLY_LINK = re.compile(r"href=[\"']([^\"']+)[\"'][^>]*>(?:[^<]{0,40})(?:apply|view (?:all )?(?:jobs|openings|positions))", re.I)


def own_attempts(db: Path, run: str | None):
    ws = openpyxl.load_workbook(db, read_only=True)["Attempts"]
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows)
    att = [dict(zip(hdr, r)) for r in rows if r and r[0]]
    mine = [a for a in att if a["harness_id"] == HARNESS and a["attempted_signal"] == "job_posting"]
    run = run or max(a["run_id"] for a in mine)
    return run, [a for a in mine if a["run_id"] == run]


def companies(db: Path) -> dict:
    ws = openpyxl.load_workbook(db, read_only=True)["Companies"]
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows)
    return {r[0]: dict(zip(hdr, r)) for r in rows if r and r[0]}


def archived_html(cid: str, url: str) -> tuple[str, str] | None:
    """Newest archived copy of this careers page, from any partition."""
    key = f"discover_{slug(cid)}_{slug(url)}.html"
    hits = sorted(glob.glob(str(RAW / "*" / key)))
    if not hits:
        # the harness also archives the homepage under a fixed key
        return None
    p = Path(hits[-1])
    return p.read_text(encoding="utf-8", errors="replace"), p.parent.name


def hosts(html: str) -> Counter:
    c: Counter = Counter()
    for m in re.finditer(r"<(?:script|iframe|link)\b[^>]*?(?:src|href)=[\"']([^\"']+)[\"']", html, re.I):
        u = m.group(1)
        if u.startswith("//"):
            u = "https:" + u
        h = urllib.parse.urlparse(u).netloc.lower()
        if h:
            c[h] += 1
    return c


def fingerprint(html: str, url: str) -> dict:
    hay = f"{html}\n{url}"
    plats = [(n, board) for n, rx, board in PLATFORMS if re.search(rx, hay, re.I)]
    cross = [n for n, rx in CROSSPOST if re.search(rx, hay, re.I)]
    fw = [n for n, rx in FRAMEWORKS if re.search(rx, hay, re.I)]
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    inline = len(INLINE_POSTING.findall(html))
    apply_targets = []
    for m in APPLY_LINK.finditer(html):
        h = urllib.parse.urlparse(m.group(1)).netloc.lower()
        if h:
            apply_targets.append(h)
    return {"platforms": plats, "crosspost": cross, "frameworks": fw,
            "inline_posting_items": inline, "visible_chars": len(text),
            "apply_hosts": sorted(set(apply_targets)), "hosts": hosts(html)}


def bucket(fp: dict) -> tuple[str, str]:
    """Exactly one primary bucket per company, with the rule that placed it."""
    if fp["platforms"]:
        name, board = fp["platforms"][0]
        if board:
            return f"ats:{name}", f"platform fingerprint '{name}' present (public board surface)"
        return f"ats:{name}", f"platform fingerprint '{name}' present"
    if fp["inline_posting_items"] >= 3:
        return "inline_static_list", f"{fp['inline_posting_items']} posting-shaped items in server HTML, no ATS fingerprint"
    if fp["visible_chars"] < 2500 and any(f in ("react/next", "angular", "vue/nuxt") for f in fp["frameworks"]):
        return "js_rendered_shell", f"{fp['visible_chars']} visible chars and a {'/'.join(fp['frameworks'])} marker, no ATS fingerprint"
    if fp["visible_chars"] < 2500:
        return "js_rendered_shell", f"{fp['visible_chars']} visible chars, no ATS fingerprint"
    if fp["apply_hosts"]:
        return "apply_link_offsite", f"apply link(s) to {', '.join(fp['apply_hosts'][:3])}, no fingerprinted platform"
    return "static_page_no_list", f"{fp['visible_chars']} visible chars, no ATS fingerprint, no posting-shaped list"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--run")
    ap.add_argument("--live", action="store_true", help="fetch pages the archive lacks (robots-gated)")
    ap.add_argument("--md", help="write the per-company table to this markdown path")
    args = ap.parse_args()

    run, leg = own_attempts(Path(args.db), args.run)
    comp = companies(Path(args.db))
    targets = []   # (cid, name, careers_url, readable?)
    for a in leg:
        d = str(a.get("failure_detail") or "")
        cid = a["company_id"]
        name = comp.get(cid, {}).get("canonical_name", cid)
        if a["outcome"] == "covered":
            continue
        m = re.search(r"careers page found at (\S+)", d)
        if m:
            targets.append((cid, name, m.group(1).rstrip(".,"), "found"))
        elif "no careers page" in d:
            site = comp.get(cid, {}).get("website") or ""
            targets.append((cid, name, site, "none_found"))
        else:
            m2 = re.search(r"https?://\S+", d)
            targets.append((cid, name, (m2.group(0).rstrip(".,") if m2 else ""), "other"))

    fetcher = None
    if args.live:
        from harnesses.h_jobpost_01.source import JobSourceClient  # type: ignore
        from core.cache import DatedCache
        from core.db import today
        cache = DatedCache(RAW, offline=False, retrieval_date=today(), pause_seconds=0.7)
        client = JobSourceClient(cache)
        fetcher = client

    results = []
    missing = []
    for cid, name, url, how in targets:
        html = part = None
        if url:
            got = archived_html(cid, url)
            if got:
                html, part = got
            elif how == "none_found":
                hp = sorted(glob.glob(str(RAW / "*" / f"discover_{slug(cid)}_home.html")))
                if hp:
                    html, part = Path(hp[-1]).read_text(encoding="utf-8", errors="replace"), Path(hp[-1]).parent.name
        if html is None and fetcher is not None and url:
            try:
                html, status = fetcher.fetch(url, f"discover_{slug(cid)}_{slug(url)}")
                part = "live"
            except Exception as exc:  # noqa: BLE001
                missing.append((cid, name, url, f"{type(exc).__name__}: {exc}"[:80]))
                continue
        if html is None:
            missing.append((cid, name, url, "not in archive (use --live)"))
            continue
        fp = fingerprint(html, url)
        b, rule = bucket(fp)
        results.append({"cid": cid, "name": name, "url": url, "how": how, "part": part,
                        "bucket": b, "rule": rule, "fp": fp})

    n_target = len(targets)
    print(f"{HARNESS} careers-page platform audit, run {run}: {n_target} unreadable companies, "
          f"{len(results)} pages read ({sum(1 for r in results if r['part'] == 'live')} live), "
          f"{len(missing)} not read\n")

    buckets = Counter(r["bucket"] for r in results)
    print("primary bucket (one per company)")
    for b, n in buckets.most_common():
        print(f"  {n:4d}  {n / max(len(results), 1):6.1%}  {b}")

    plats = Counter(p for r in results for p, _ in r["fp"]["platforms"])
    if plats:
        print("\nevery platform fingerprint seen (a page can carry several)")
        for p, n in plats.most_common():
            print(f"  {n:4d}  {p}")
    cross = Counter(c for r in results for c in r["fp"]["crosspost"])
    print("\ncross-post links on the company's own careers page")
    for c, n in cross.most_common():
        print(f"  {n:4d}  {c}")
    if not cross:
        print("  none")
    fw = Counter(f for r in results for f in r["fp"]["frameworks"])
    print("\nrendering / site-builder markers")
    for f, n in fw.most_common():
        print(f"  {n:4d}  {f}")
    host_c: Counter = Counter()
    for r in results:
        for h in r["fp"]["hosts"]:
            host_c[h] += 1
    print("\nthird-party script/iframe hosts present on >= 3 pages (ATS or embed candidates)")
    for h, n in host_c.most_common():
        if n >= 3 and not any(x in h for x in ("googleapis", "gstatic", "google-analytics", "googletagmanager",
                                                "cloudflare", "jquery", "bootstrapcdn", "fonts.", "facebook",
                                                "doubleclick", "hotjar", "cookie", "youtube", "vimeo",
                                                "jsdelivr", "unpkg", "cdnjs", "typekit", "adobe", "linkedin.com/px")):
            print(f"  {n:4d}  {h}")

    if missing:
        print(f"\nnot read ({len(missing)})")
        for cid, name, url, why in missing:
            print(f"  {cid} {name}: {url or '(no url)'} -- {why}")

    if args.md:
        lines = [f"# {HARNESS} careers-page platform audit — run {run}", "",
                 f"{n_target} unreadable companies; {len(results)} pages read; {len(missing)} not read. "
                 "One primary bucket per company; the rule that placed it is in the last column.", "",
                 "| company | careers url | bucket | platforms | cross-post | frameworks | rule |",
                 "|---|---|---|---|---|---|---|"]
        for r in sorted(results, key=lambda x: (x["bucket"], x["cid"])):
            lines.append(f"| {r['cid']} {r['name']} | {r['url']} | `{r['bucket']}` | "
                         f"{', '.join(p for p, _ in r['fp']['platforms']) or '–'} | "
                         f"{', '.join(r['fp']['crosspost']) or '–'} | "
                         f"{', '.join(r['fp']['frameworks']) or '–'} | {r['rule']} |")
        if missing:
            lines += ["", "## Not read", ""] + [f"- {cid} {name}: {url or '(no url)'} — {why}" for cid, name, url, why in missing]
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
