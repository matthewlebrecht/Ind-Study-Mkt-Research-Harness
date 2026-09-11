#!/usr/bin/env python3
"""
H-EXECID-01 -- Executive Identification (prerequisite harness).

WHAT THIS IS FOR
----------------
`session2_priority_order.md` puts closing the `buyer_articulates` gap above everything
else: the evidence base holds 185 `buyer_acts` rows and zero `buyer_articulates` rows, so
the entire "what buyers say" half of the governing question is empty. H-EXECVOICE-01 is
the harness that fills it, and it cannot start without knowing whose statements to look
for. This harness produces that list.

It is therefore a **prerequisite harness, not an evidence harness**. It writes to
`Company_Executives` and never to `Observations`, matching the
`signal_class = prerequisite` registration `executive_identification` already carries in
`Signal_Types` (ST-0003). It makes no claim about modernization posture, so it has no
`evidence_role`, no `organizational_state`, and no evidence family.

WHY THE SOURCING WATERFALL STOPS SHORT OF AGGREGATORS
-----------------------------------------------------
The specified waterfall is: company leadership pages -> ZoomInfo -> LinkedIn People tab ->
press/business journal -> search fallback. This version implements the first-party and
search-fallback ends of it and deliberately stops before the aggregator middle.

Two reasons, and the second is the important one. The mechanical reason is that ZoomInfo
and LinkedIn serve bot-detection walls to an unauthenticated fetch, so "implementing" them
would mean recording access failures. The substantive reason is that aggregator profiles
(theorg.com, rocketreach.co, comparably.com, leadiq.com dominate these result sets) are
undated, frequently stale, and give no way to tell a current officer from one who left
three years ago. A wrong name here does not degrade gracefully: it sends H-EXECVOICE-01
searching the open web for the public statements of someone who does not hold that job,
and whatever it finds becomes `buyer_articulates` evidence attributed to a company that
never said it. That is manufactured evidence, which convention 6a rates worse than a gap.

So aggregator URLs encountered during discovery are *recorded in the run log* and not
read. A later version that wants them can start from that list, with a freshness test and
a lower source grade, as a deliberate decision rather than a default.

WHAT COUNTS AS COVERAGE
-----------------------
`absent_confirmed` is almost never correct here and the harness does not emit it. Reaching
a leadership page and extracting nobody is far more likely to be an extraction failure than
a company with no executives, so that outcome is `not_covered` / `extraction` /
`content_unstructured` -- an honest statement that the harness could not read the page.
Convention 6 requires an authoritative source that is *complete for the signal* before
absence is asserted, and a page this harness could not parse is not evidence of anything.

A company read off a real leadership page is `covered`. A company whose executives came
only from a weaker page class -- an About page that happens to name a founder -- is
`partial`, carrying the page class in `failure_detail`. That distinction is the direct
lesson of convention 16: H-SELLERCONTENT-01 reported 100% coverage while half its
providers had been read off homepage substitutes.

WEBSITE BACKFILL
----------------
Nine buyer companies have no `website` value, which blocks discovery entirely. Rather
than skip them, the harness resolves the homepage by search, scoring the *domain* against
the company name tokens and refusing below a floor, then writes the value back to
`Companies`. Convention 20: an enrichment value belongs in the target sheet. This also
closes the named `H-WAYBACK-01` coverage gap listed as a Priority 3 cheap win.

    python -m harnesses.h_execid_01.harness                  # dry run, whole universe
    python -m harnesses.h_execid_01.harness --commit
    python -m harnesses.h_execid_01.harness --limit 10       # first N companies
    python -m harnesses.h_execid_01.harness --companies C0001,A003
    python -m harnesses.h_execid_01.harness --offline        # replay the archive
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache                                     # noqa: E402
from core.db import Executive, MarketIntelDB, today                   # noqa: E402
from core.resolution import tokens                                    # noqa: E402
from core.search import BraveSearch, SearchError                      # noqa: E402
from harnesses.h_execid_01.extract import extract, html_lines         # noqa: E402
from harnesses.h_execid_01.source import (                            # noqa: E402
    AGGREGATOR_HOSTS, SiteClient, _kind_for, candidate_links, find_homepage,
    search_leadership_page)

HARNESS_ID = "H-EXECID-01"
HARNESS_NAME = "Executive Identification"
VERSION = "v1.1"
SIGNAL_TYPE = "executive_identification"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# How many candidate pages to fetch per company before giving up. Each is one HTTP
# request against someone else's site, and the marginal value drops fast: across the
# calibration set every successful read came from the top three ranked candidates.
MAX_PAGES_PER_COMPANY = 4
# Second-level expansion: when the best first-level candidate yields nobody, its own links
# are scanned once. This is what finds /who-we-are/team-members from /who-we-are.
MAX_SECOND_LEVEL = 3

# A first-party leadership page is the company own statement of who runs it: authoritative
# and current. Grade A. A weaker first-party page (About, Who We Are) is the same site but
# not a roster, so a reading off one is B -- the page was not built to be complete.
GRADE_BY_KIND = {"leadership": "A", "officers": "A", "team": "A", "about": "B",
                 "homepage": "B", "unknown": "B"}


def _log_path(stamp: str, commit: bool) -> Path:
    return OUTPUT_DIR / f"run-{stamp}{'' if commit else '-dryrun'}.json"


def backfill_website(db: MarketIntelDB, company: dict, search: BraveSearch,
                     entry: dict) -> str:
    """Resolve and record a missing homepage. Returns "" if it could not be resolved."""
    name = company["canonical_name"]
    state = str(company.get("hq_state") or "")
    try:
        url, rejected = find_homepage(search, name, state)
    except SearchError as e:
        entry["website_backfill"] = {"status": "search_failed", "detail": str(e)}
        raise
    entry["website_backfill"] = {"status": "resolved" if url else "refused",
                                 "url": url, "rejected": rejected[:8]}
    if not url:
        return ""
    ws = db.wb["Companies"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    col = headers.index("website") + 1
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == company["company_id"]:
            ws.cell(r, col).value = url
            break
    return url


def read_company(client: SiteClient, search: BraveSearch, company: dict, homepage: str,
                 entry: dict) -> tuple[list, str, str, dict]:
    """Find and read the best available page naming this company executives.

    Returns (people, page_url, page_kind, stats). `people` is empty when nothing could be
    read; the caller decides which failure that is.
    """
    name = company["canonical_name"]
    company_tokens = set(tokens(name))
    stats = {"pages_fetched": 0, "candidates": [], "aggregators": [], "rejected": [],
             # Diagnosis inputs. These three separate the failure modes that a single
             # "found nobody" outcome would otherwise collapse together -- see
             # `diagnose_failure`.
             "pages_read_ok": 0, "title_lines_seen": 0, "max_lines": 0}

    hp = client.get(homepage, kind="homepage")
    stats["pages_fetched"] += 1
    if not hp.ok:
        stats["homepage_status"] = hp.status
        stats["homepage_error"] = hp.error[:200]
        return [], homepage, "", stats

    candidates = candidate_links(hp.html, homepage, limit=8)
    stats["candidates"] = [{"score": s, "url": u} for s, u in candidates]

    best: tuple[list, str, str] = ([], "", "")
    tried: set[str] = set()

    def try_pages(pairs, budget):
        nonlocal best
        for score, url in pairs[:budget]:
            if url in tried:
                continue
            tried.add(url)
            page = client.get(url, kind=_kind_for(score), marker_score=score)
            stats["pages_fetched"] += 1
            if not page.ok:
                stats["rejected"].append({"url": url, "status": page.status,
                                          "error": page.error[:120]})
                continue
            lines = html_lines(page.html)
            ex = extract(lines, company_tokens,
                         admit_untitled=page.kind in ("leadership", "officers", "team"))
            stats["pages_read_ok"] += 1
            stats["title_lines_seen"] += ex.title_lines_seen
            stats["max_lines"] = max(stats["max_lines"], len(lines))
            stats["rejected"].extend(
                {"url": url, **r} for r in ex.rejected[:5])
            if not ex.people:
                continue
            # Prefer a reading with primary-relevance people, then more people, then a
            # stronger page class. A team page listing 18 executives beats an About page
            # naming one founder even though both parse cleanly.
            confirmed = [p for p in ex.people if p.role_relevance != "unconfirmed"]
            cur_rank = (len(ex.primary) > 0, len(confirmed), page.marker_score)
            best_rank = (len([p for p in best[0] if p.role_relevance == "primary"]) > 0,
                         len(best[0]), 0)
            if cur_rank > best_rank:
                best = (ex.people, url, page.kind)
            if ex.primary and page.marker_score >= 6:
                return True
        return False

    done = try_pages(candidates, MAX_PAGES_PER_COMPANY)

    # ---- second-level expansion ----
    #
    # Gated on `done` -- a strong reading, meaning primary-relevance people off a
    # leadership-class page -- and NOT on "found anybody". Gating on emptiness was wrong
    # and measurably so: the Kenco About page yields exactly one executive, which was
    # enough to stop the search and leave the company at `partial` while its real
    # leadership page went unvisited. A weak result is precisely the case that most needs
    # the extra look.
    if not done and candidates:
        top_url = candidates[0][1]
        page = client.get(top_url)
        if page.ok:
            deeper = candidate_links(page.html, top_url, limit=6)
            deeper = [(s, u) for s, u in deeper if u not in tried]
            stats["second_level"] = [{"score": s, "url": u} for s, u in deeper]
            done = try_pages(deeper, MAX_SECOND_LEVEL)

    # ---- search fallback, constrained to the company own host ----
    if not done:
        try:
            from core.search import host_of
            found, aggregators = search_leadership_page(search, name, host_of(homepage))
            stats["aggregators"] = aggregators
            stats["search_fallback"] = [{"score": s, "url": u} for s, u in found]
            try_pages([(s, u) for s, u in found if u not in tried], 2)
        except SearchError as e:
            stats["search_fallback_error"] = str(e)

    return best[0], best[1] or homepage, best[2], stats


# Below this many block lines, a 200 response is a JavaScript shell rather than a thin
# page. Calibrated on the pilot run: pages with real prose ran 75-348 lines, while the
# Western Express About page -- a site that renders its content client-side -- came back
# at 35. The distinction routes to a different fix (a rendering fetch, not a better
# extractor), which is the only reason it is worth separating.
MIN_PAGE_LINES = 40


def diagnose_failure(stats: dict) -> tuple[str, str, str, str]:
    """Decide which failure a "found nobody" outcome actually was.

    Collapsing these into one category was the first version mistake and it produced a
    positively misleading run: five pilot companies were recorded as
    `extraction`/`content_unstructured`, which asserts the page held the information and
    the harness could not parse it. Checking the pages by hand showed the opposite --
    Duke, Mack and Western Express publish company-history About pages that name no
    executive at all, and `title_lines_seen` was zero on every one. The harness had a
    discovery problem and was reporting a parser problem, which routes the fix to the
    wrong place and overstates how close the harness is to working.

    `title_lines_seen` is the discriminator, and it is cheap and honest: it counts lines
    anywhere in the pages read that match the closed title vocabulary. Zero of them means
    no page naming executives was ever reached. A non-zero count with no extracted pair
    means titles were present and the name/title pairing failed, which genuinely is an
    extraction bug.
    """
    if stats.get("search_fallback_error") and not stats.get("candidates"):
        # Session 10 item 6 (E37): the search never ran, so "the site published no
        # leadership link" is not established. core/search.py's own rule.
        return ("fetch", "source_unavailable", "transient",
                f"search fallback failed ({str(stats['search_fallback_error'])[:100]}); "
                f"whether a leadership page exists is unknown")
    if stats.get("homepage_status") is not None or stats.get("homepage_error"):
        return ("fetch", "source_unavailable", "transient",
                f"homepage unreachable (status {stats.get('homepage_status')}, "
                f"{str(stats.get('homepage_error', ''))[:120]})")
    if not stats["candidates"]:
        return ("discovery", "source_not_found", "source_limitation",
                "homepage published no link matching a leadership marker, and the "
                "site-constrained search fallback returned none either")
    if stats.get("pages_read_ok", 0) and stats.get("max_lines", 0) < MIN_PAGE_LINES:
        return ("fetch", "js_rendered_unreachable", "code_change",
                f"best page carried only {stats['max_lines']} block lines of visible text "
                f"(floor {MIN_PAGE_LINES}) -- content is rendered client-side")
    if stats.get("title_lines_seen", 0) == 0:
        return ("discovery", "source_not_found", "source_limitation",
                f"read {stats.get('pages_read_ok', 0)} page(s) containing no executive "
                f"title at all, so no leadership page was reached; tried "
                f"{', '.join(c['url'] for c in stats['candidates'][:3])}")
    return ("extraction", "content_unstructured", "code_change",
            f"read {stats.get('pages_read_ok', 0)} page(s) carrying "
            f"{stats['title_lines_seen']} executive title line(s), but no title had an "
            f"adjacent well-formed personal name")


def main() -> int:
    # Session 15: a Windows console defaults to cp1252, and one search-error string carrying
    # U+FFFD killed a 79-company live run at company 68 with UnicodeEncodeError. Output is
    # never worth a crash; replace what the console cannot show.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="H-EXECID-01 -- executive identification")
    ap.add_argument("--commit", action="store_true", help="write rows to the workbook")
    ap.add_argument("--offline", action="store_true", help="replay archived responses only")
    ap.add_argument("--limit", type=int, default=0, help="process only the first N")
    ap.add_argument("--companies", help="comma-separated company_ids")
    ap.add_argument("--pause", type=float, default=0.6, help="seconds between page fetches")
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = [c for c in db.companies()
                 if c.get("qualification_status") != "provider_benchmark"]
    if args.companies:
        want = {c.strip() for c in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"] in want]
    if args.limit:
        companies = companies[:args.limit]

    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = DatedCache(OUTPUT_DIR / "raw" / "pages", offline=args.offline,
                       retrieval_date=stamp, pause_seconds=args.pause)
    client = SiteClient(pages)
    search = BraveSearch(OUTPUT_DIR / "raw" / "search", offline=args.offline,
                         retrieval_date=stamp, pause_seconds=1.0)

    scope = [(c["company_id"], SIGNAL_TYPE) for c in companies]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family="", scope=scope, commit=args.commit)

    proposed: list[Executive] = []
    authoritative: set[str] = set()
    websites_filled = 0
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "companies": []}

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        entry = {"company_id": cid, "name": name}
        homepage = str(company.get("website") or "").strip()

        # ---- website backfill ----
        if not homepage:
            try:
                homepage = backfill_website(db, company, search, entry)
            except SearchError as e:
                run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                            failure_stage=e.failure_stage,
                            failure_category=e.failure_category, fix_class=e.fix_class,
                            failure_detail=f"website unknown and search failed: {e}")
                print(f"  [--] {cid} {name}: search failed -- {e}")
                log["companies"].append(entry)
                continue
            if not homepage:
                run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                            failure_stage="entity_resolution",
                            failure_category="entity_below_threshold",
                            fix_class="source_limitation",
                            failure_detail="no search result domain scored above the "
                                           "floor against the company name tokens; "
                                           "refused rather than guessed")
                print(f"  [--] {cid} {name}: homepage unresolved (refused to guess)")
                log["companies"].append(entry)
                continue
            websites_filled += 1
            print(f"  [++] {cid} {name}: website backfilled -> {homepage}")

        entry["homepage"] = homepage

        # ---- read ----
        people, page_url, page_kind, stats = read_company(client, search, company,
                                                          homepage, entry)
        entry["page_url"] = page_url
        entry["page_kind"] = page_kind
        entry["stats"] = stats
        entry["people"] = [{"name": p.full_name, "title": p.title,
                            "title_normalized": p.title_normalized,
                            "role_relevance": p.role_relevance, "layout": p.layout}
                           for p in people]

        if not people:
            stage, cat, fix, detail = diagnose_failure(stats)
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered", failure_stage=stage,
                        failure_category=cat, fix_class=fix, failure_detail=detail,
                        output_sheet="Company_Executives",
                        source_url_attempted=page_url,
                        candidates_evaluated=len(stats["candidates"]),
                        candidates_discarded=len(stats["rejected"]))
            print(f"  [--] {cid} {name}: {cat}")
            log["companies"].append(entry)
            continue

        grade = GRADE_BY_KIND.get(page_kind, "B")
        for p in people:
            low = p.role_relevance == "unconfirmed"
            variants = f"layout={p.layout}"
            if low:
                why = ("out-of-vocabulary title admitted as written (E26)"
                       if p.layout.endswith("E26") else
                       "name without adjacent title on a leadership-class page (E32)")
                variants += (f"; [low-grade: {why}; session 14 2026-09-06, convention 41; "
                             f"role unconfirmed, review before use]")
            proposed.append(Executive(
                company_id=cid, full_name=p.full_name, title=p.title,
                title_normalized=p.title_normalized, role_relevance=p.role_relevance,
                source_url=page_url, source_grade="C" if low else grade,
                retrieval_date=stamp, harness_id=HARNESS_ID, harness_version=VERSION,
                confidence_0_1=p.confidence,
                # The layout that produced the record is kept so a reviewer disagreeing
                # with one extraction can find every other record read the same way.
                name_variants=variants))

        primary = [p for p in people if p.role_relevance == "primary"]
        strong_page = page_kind in ("leadership", "officers", "team")
        if strong_page:
            authoritative.add(cid)

        if strong_page and primary:
            run.attempt(cid, SIGNAL_TYPE, outcome="covered",
                        records_written=len(people),
                        output_sheet="Company_Executives",
                        source_url_attempted=page_url,
                        candidates_evaluated=len(stats["candidates"]),
                        candidates_discarded=len(stats["rejected"]))
            print(f"  [ok] {cid} {name}: {len(people)} exec(s), {len(primary)} primary "
                  f"[{page_kind}]")
        else:
            detail = ("executives were read from a "
                      f"{page_kind or 'weaker'}-class page rather than a leadership "
                      "roster, so the list is not known to be complete"
                      if not strong_page else
                      "a leadership page was read but it named no primary-relevance "
                      "title (CEO/COO/CIO-CTO/VP Ops/Supply Chain/Manufacturing)")
            run.attempt(cid, SIGNAL_TYPE, outcome="partial",
                        failure_stage="discovery" if not strong_page else "classification",
                        failure_category="source_not_found" if not strong_page
                        else "classification_ambiguous",
                        fix_class="source_limitation",
                        failure_detail=detail,
                        records_written=len(people),
                        output_sheet="Company_Executives",
                        source_url_attempted=page_url,
                        candidates_evaluated=len(stats["candidates"]),
                        candidates_discarded=len(stats["rejected"]))
            print(f"  [~~] {cid} {name}: {len(people)} exec(s), {len(primary)} primary "
                  f"[{page_kind or 'none'}] -- partial")
        log["companies"].append(entry)

    # ---- write ----
    report = db.sync_executives(proposed, authoritative_companies=authoritative)
    run.observations_written = 0        # this harness writes no Observations, by design
    run.material_revision_notes = (
        f"Prerequisite run: {report.written} Company_Executives rows written "
        f"({len(proposed)} proposed), {websites_filled} Companies.website backfilled.")
    summary = run.close()

    n_primary = sum(1 for e in proposed if e.role_relevance == "primary")
    print()
    print(f"  {summary['companies_processed']} companies - {len(proposed)} executives "
          f"({n_primary} primary) - {pages.fetch_count} page fetches, "
          f"{search.stats()['queries_sent']} searches")
    print(f"  coverage {summary['coverage_rate']:.0%} "
          f"({summary['attempts_covered']} covered, {summary['attempts_partial']} partial, "
          f"{summary['attempts_not_covered']} not_covered)")
    print(f"  executives: {report.summary()}")
    if websites_filled:
        print(f"  websites backfilled: {websites_filled}")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")
    if report.conflicts:
        print(f"  CONFLICTS held for human review: {len(report.conflicts)}")

    log["summary"] = summary
    log["executives_sync"] = report.summary()
    log["websites_filled"] = websites_filled
    log["search_stats"] = search.stats()
    path = _log_path(stamp, args.commit)
    path.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")

    if args.commit:
        db.save()
        print(f"  committed to market_intel_db.xlsx ({summary['run_id']})")
    else:
        print("  DRY RUN -- nothing written. Re-run with --commit to write.")
    print(f"  run log: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
