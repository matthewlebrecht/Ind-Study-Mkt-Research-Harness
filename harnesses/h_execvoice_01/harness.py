#!/usr/bin/env python3
"""
H-EXECVOICE-01 -- Executive Candor (the first `buyer_articulates` instrument).

WHY THIS IS THE PRIORITY
------------------------
The evidence base holds 185 `buyer_acts` observations and 43 `provider_market_responds`
observations against **zero** `buyer_articulates`. The governing question asks where buyer
statements and seller messaging converge or diverge; with an empty buyer-statement column,
every convergence claim in the Week 3-4 write-up would be unfalsifiable. This harness
produces that column.

WHAT IT WILL AND WILL NOT ACCEPT AS EVIDENCE
--------------------------------------------
One thing only: a **directly quoted passage, attributable to a named executive of the
company, mentioning a modernization theme, on a dated third-party page.**

That bar costs yield, and `docs/signal_taxonomy.md` predicted exactly how much -- it marks
podcast appearances (15b) "don't-build (yield too low for this population)" because
mid-size industrial executives rarely podcast. The response to a low-yield source is not
to lower the bar until the count looks respectable. A paraphrase recorded as a quote, or a
quote attributed to the wrong person, produces a row asserting that a company said
something it never said, and that row would then anchor a divergence finding. Convention 6a
rates false evidence worse than a gap, and this is the cleanest case of it in the project.

So the harness is designed to return few, defensible rows, and to say loudly how many
companies it could not cover and why.

THE THREE EXCLUSIONS
--------------------
1. **Vendor-published content** -- the trap `session2_priority_order.md` names explicitly.
   A systems integrator case study quoting a buyer VP is family 6 (vendor/partner
   disclosure), not family 15, and it is not spontaneous articulation: it is a testimonial
   the vendor selected, edited and published to sell something. Provider domains are read
   from `Companies` (the twelve `provider_benchmark` rows), and vendor case-study URL
   shapes are excluded on top of that. Excluded URLs are recorded in the run log so
   H-VENDOR-01 can start from them rather than rediscover them.

2. **The companys own domain and the PR wires** -- that is H-FIRSTPARTY-01 territory
   (family 1). Excluding it here is what stops the same executive quote in the same press
   release from being counted twice, in two families, as two independent pieces of
   evidence.

3. **Executive-data aggregators** -- undated, unattributed, and never the origin of a
   quote.

GRADING
-------
`source_grade = B`, uniformly, and deliberately below the A that the taxonomy allows
family 15. The A ceiling in 15a belongs to content an executive authored directly -- a
LinkedIn post under their own name. This harness cannot reach that: LinkedIn serves a
bot-detection wall to an unauthenticated fetch. Everything it does reach is
journalist-mediated or conference-mediated: really said, but selected and framed by
somebody else. B is the honest grade for that, and grading it A because the family
permits A would overstate exactly the evidence the whole write-up leans on.

    python -m harnesses.h_execvoice_01.harness                 # dry run
    python -m harnesses.h_execvoice_01.harness --commit
    python -m harnesses.h_execvoice_01.harness --limit 15
    python -m harnesses.h_execvoice_01.harness --offline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache                                      # noqa: E402
from core.db import MarketIntelDB, Observation, today                  # noqa: E402
from core.resolution import tokens                                     # noqa: E402
from core.search import BraveSearch, SearchError, host_of              # noqa: E402
from core import topics                                               # noqa: E402
from harnesses.h_execid_01.extract import html_lines                   # noqa: E402
from harnesses.h_firstparty_01 import article                          # noqa: E402
from harnesses.h_execid_01.source import AGGREGATOR_HOSTS, SiteClient  # noqa: E402
from harnesses.h_execvoice_01.quotes import (                          # noqa: E402
    extract_quotes, signal_strength)

HARNESS_ID = "H-EXECVOICE-01"
HARNESS_NAME = "Executive Candor Extractor"
VERSION = "v1.7"
SIGNAL_TYPE = "executive_public_statement"
EVIDENCE_FAMILY = "15_executive_candor_actor_networks"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# Which executives are worth spending searches on, most likely to speak publicly about
# modernization first. Two per company keeps the query budget proportionate: the marginal
# fifth VP of a mid-size private firm has a vanishing chance of a quoted public statement.
TITLE_PRIORITY = ["ceo", "president", "coo", "cio_cto", "chief_transformation",
                  "vp_supply_chain", "vp_operations", "vp_it", "vp_manufacturing"]
MAX_EXECS_PER_COMPANY = 2
# Session 15 (Matthew's decision, item 1): the EXECID low-grade tier is searched too --
# people whose role is `unconfirmed` (out-of-vocabulary title, or none). Capped per company
# so a ten-name roster does not spend the search budget of five companies. Quotes found
# through these names are graded by the same rules as any other quote; the executive
# record's grade does NOT propagate to the observation. Provenance is stated in the text.
MAX_LOW_GRADE_EXECS_PER_COMPANY = 4
MAX_PAGES_PER_EXEC = 4

# PR wires and syndication. First-party announcement territory (family 1), which is
# H-FIRSTPARTY-01, not this harness.
WIRE_HOSTS = {
    "prnewswire.com", "businesswire.com", "globenewswire.com", "prweb.com",
    "einpresswire.com", "accesswire.com", "newswire.com", "marketwatch.com",
    "finance.yahoo.com", "morningstar.com", "streetinsider.com",
}

# URL shapes that mark vendor-published customer content regardless of host.
VENDOR_CONTENT_RE = re.compile(
    r"(?i)(/customers?/|/case-stud|/success-stor|/customer-stor|/testimonial|"
    r"/client-stor|/resources?/case|/why-[a-z]+/|/partners?/stories|/vendors?/|"
    r"/supplier-|/solution-provider|/company-profile)")

# Pages that cannot carry an attributable quote.
JUNK_URL_RE = re.compile(
    r"(?i)(\.pdf$|/tag/|/tags/|/category/|/author/|/search|/login|/signup|"
    r"/privacy|/terms|/sitemap)")

# A body that says "page not found" under an HTTP 200. Detected on the text rather than
# the status because the status lies.
SOFT_404_RE = re.compile(
    r"(?i)(page not found|404 not found|404[^a-z]{0,10}(error|not found)|"
    r"does\s?n.t exist|no longer available|has been removed)")


def provider_hosts(db: MarketIntelDB) -> set[str]:
    """Hosts of the twelve provider_benchmark entities, for the family-6 exclusion."""
    hosts = set()
    for c in db.companies(statuses=("provider_benchmark",)):
        site = str(c.get("website") or "").strip()
        if site:
            hosts.add(host_of(site))
    return hosts


def load_executives(db: MarketIntelDB) -> dict[str, list[dict]]:
    """Primary-relevance, active executives from Company_Executives, best titles first."""
    ws = db.wb["Company_Executives"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    by_company: dict[str, list[dict]] = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        row = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers) if h}
        rel = str(row.get("role_relevance") or "")
        if rel not in ("primary", "unconfirmed"):
            continue
        if str(row.get("status") or "active") != "active":
            continue
        row["_low_grade"] = rel == "unconfirmed"
        by_company.setdefault(str(row["company_id"]), []).append(row)
    for cid, people in by_company.items():
        people.sort(key=lambda p: (
            p["_low_grade"],
            TITLE_PRIORITY.index(str(p.get("title_normalized")))
            if str(p.get("title_normalized")) in TITLE_PRIORITY else 99,
            str(p.get("full_name"))))
    return by_company


def select_people(people: list[dict]) -> list[dict]:
    """Primary names first (capped), then low-grade names (capped separately)."""
    primary = [p for p in people if not p["_low_grade"]][:MAX_EXECS_PER_COMPANY]
    low = [p for p in people if p["_low_grade"]][:MAX_LOW_GRADE_EXECS_PER_COMPANY]
    return primary + low


def excluded_reason(url: str, company_host: str, providers: set[str]) -> str:
    """Why this result must not be read, or "" if it may be."""
    host = host_of(url)
    if JUNK_URL_RE.search(url):
        return "non_article_url"
    if host in AGGREGATOR_HOSTS or any(host.endswith("." + a) for a in AGGREGATOR_HOSTS):
        return "executive_data_aggregator"
    if host in WIRE_HOSTS:
        return "pr_wire_belongs_to_H-FIRSTPARTY-01"
    if company_host and (host == company_host or host.endswith("." + company_host)):
        return "company_own_domain_belongs_to_H-FIRSTPARTY-01"
    if host in providers:
        return "provider_published_family_6"
    if VENDOR_CONTENT_RE.search(url):
        return "vendor_customer_content_family_6"
    return ""


def build_observation(company: dict, theme_key: str, quotes: list, url: str,
                      retrieval: str, page_title: str,
                      low_grade_names: set | None = None) -> Observation:
    """One claim: this company executive publicly articulated this theme, on this page."""
    theme = topics.THEMES_BY_KEY[theme_key]
    names = sorted({q.executive for q in quotes})
    states = [q.state for q in quotes if q.state != "unknown"]
    # The most informative reading available across the quotes on this page. A quote
    # describing a live programme outranks one describing only a problem or only an
    # aspiration, matching the ordering in quotes.interpret_state.
    state = "unknown"
    for candidate in ("active_transition", "legacy_constraint", "target_state"):
        if candidate in states:
            state = candidate
            break
    strength = signal_strength(quotes)
    explicit = [q for q in quotes if q.attribution == "explicit"]
    confidence = round(max(q.confidence for q in quotes), 2)

    text = (
        f"{', '.join(names)} of {company['canonical_name']} publicly articulated "
        f"{theme.label} in {len(quotes)} directly quoted passage(s) "
        f"({len(explicit)} with explicit attribution) on {page_title or url}. "
        f"Reading: {state.replace('_', ' ')}. This records what the executive said, "
        f"as quoted by a third party -- not a verified account of what the company has "
        f"implemented."
    )
    via_low = sorted(n for n in names if n in (low_grade_names or set()))
    if via_low:
        # Provenance, not a grade: the speaker was found through a Company_Executives row
        # whose ROLE is unconfirmed (EXECID low-grade tier). The quote is graded on its own
        # merits above; a reviewer should know the title is not vocabulary-confirmed.
        text += (f" Speaker record note: {', '.join(via_low)} is listed in Company_Executives "
                 f"with an unconfirmed role (EXECID low-grade tier, session 14).")
    excerpt_parts = []
    for q in quotes[:3]:
        cue = f" [cue: {q.state_cue}]" if q.state_cue else ""
        excerpt_parts.append(f'{q.executive} ({q.attribution}): "{q.text[:320]}"{cue}')
    excerpt = " | ".join(excerpt_parts)
    matched = sorted({t for q in quotes for terms in q.themes.values() for t in terms})
    excerpt += f" | matched: {', '.join(matched[:10])}"
    grade = "B"
    weak = [q.weak_reason for q in quotes if q.weak_reason]
    if weak and len(weak) == len(quotes):
        # Every quote on this theme came through a relaxed corroboration gate
        # (2026-09-03 policy): written, marked, graded C, for the reviewer to sift.
        grade = topics.LOW_GRADE
        excerpt = topics.low_grade_excerpt("; ".join(sorted(set(weak)))[:300], excerpt)

    return Observation(
        company_id=company["company_id"],
        evidence_family=EVIDENCE_FAMILY,
        evidence_role="buyer_articulates",
        topic=theme_key,
        organizational_state=state,
        signal_strength=strength,
        observation_text=text,
        evidence_excerpt=excerpt[:2000],
        source_url=url,
        publication_date="",
        retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID,
        harness_version=VERSION,
        confidence_0_1=confidence,
    )


def main() -> int:
    # Session 15: a Windows console defaults to cp1252, and one search-error string carrying
    # U+FFFD killed a 79-company live run at company 68 with UnicodeEncodeError. Output is
    # never worth a crash; replace what the console cannot show.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="H-EXECVOICE-01 -- executive candor")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--companies")
    ap.add_argument("--pause", type=float, default=0.6)
    ap.add_argument("--refresh-reviewed", action="store_true",
                    help="also refresh rows a human has reviewed (preserves review_status, "
                         "stamps reviewer_notes). Session 14: the FMCSA precedent, applied "
                         "to O00369 / O00373 by Matthew's decision.")
    ap.add_argument("--refresh-ids", default="",
                    help="comma-separated observation_ids the refresh may touch; with "
                         "--refresh-reviewed, other reviewed rows stay held")
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = [c for c in db.companies()
                 if c.get("qualification_status") != "provider_benchmark"]
    if args.companies:
        want = {c.strip() for c in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"] in want]
    if args.limit:
        companies = companies[:args.limit]

    execs_by_company = load_executives(db)
    providers = provider_hosts(db)
    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = DatedCache(OUTPUT_DIR / "raw" / "pages", offline=args.offline,
                       retrieval_date=stamp, pause_seconds=args.pause)
    client = SiteClient(pages)
    search = BraveSearch(OUTPUT_DIR / "raw" / "search", offline=args.offline,
                         retrieval_date=stamp, pause_seconds=1.0)

    scope = [(c["company_id"], SIGNAL_TYPE) for c in companies]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY}, commit=args.commit)

    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "companies": [], "excluded_vendor_urls": []}

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        entry = {"company_id": cid, "name": name, "execs": [], "pages": [],
                 "excluded": [], "quotes": 0}
        people = select_people(execs_by_company.get(cid, []))
        low_grade_names = {str(p["full_name"]) for p in people if p["_low_grade"]}
        company_host = host_of(str(company.get("website") or ""))
        company_tokens = [t for t in tokens(name) if len(t) > 3][:3] or [name]

        # ---- the prerequisite gap, made visible in coverage math ----
        if not people:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage="discovery", failure_category="source_not_found",
                        fix_class="source_limitation",
                        failure_detail="no primary-relevance executive is recorded in "
                                       "Company_Executives, so there is no name to search "
                                       "for; blocked on H-EXECID-01 coverage for this "
                                       "company, not on this harness",
                        candidates_evaluated=0, candidates_discarded=0)
            print(f"  [--] {cid} {name}: no executive identified")
            log["companies"].append(entry)
            continue

        entry["execs"] = [{"name": p["full_name"], "title": p["title"],
                           "low_grade_record": bool(p["_low_grade"])} for p in people]
        by_theme: dict[tuple[str, str], list] = {}
        page_titles: dict[str, str] = {}
        evaluated = discarded = 0
        search_failed = None

        for person in people:
            full_name = str(person["full_name"])
            # Query 1 asks for *attributed speech*, not for appearances.
            #
            # The first version asked for "interview OR podcast OR keynote OR panel" and
            # returned podcast DIRECTORIES -- feedspot listings, Apple Podcasts pages,
            # episode descriptions -- which carry titles in quotation marks and no
            # statements at all. Eight companies produced zero rows off 61 such pages.
            # Searching for the reporting verbs instead surfaces the trade press that
            # actually quotes people: the same swap turned up a DC Velocity interview with
            # Kencos CEO and a Truck News feature quoting Prime Inc.s founder on paper
            # logs, which is a real transportation_fleet_systems articulation.
            queries = [
                f'"{full_name}" "{name}" (said OR told OR interview)',
                f'"{full_name}" "{name}" (automation OR "digital transformation" OR '
                f'technology OR "supply chain" OR modernization)',
            ]
            results = []
            for q in queries:
                try:
                    results.extend(search.search(q, count=10))
                except SearchError as e:
                    search_failed = e
                    break
            if search_failed:
                break

            seen_urls = set()
            fetched = 0
            for r in results:
                if r.url in seen_urls:
                    continue
                seen_urls.add(r.url)
                evaluated += 1
                why = excluded_reason(r.url, company_host, providers)
                if why:
                    discarded += 1
                    entry["excluded"].append({"url": r.url, "reason": why})
                    if "family_6" in why:
                        log["excluded_vendor_urls"].append(
                            {"company_id": cid, "url": r.url, "reason": why})
                    continue
                if fetched >= MAX_PAGES_PER_EXEC:
                    continue
                page = client.get(r.url)
                fetched += 1
                if not page.ok:
                    discarded += 1
                    entry["pages"].append({"url": r.url, "status": page.status,
                                           "quotes": 0})
                    continue
                text = " ".join(html_lines(page.html))

                # Soft 404. Medium and several CMS platforms serve a "page not found"
                # body under HTTP 200, which passes a status check and then costs a
                # parse. Cheap to detect and worth logging separately from a real page
                # that simply had nothing on it.
                if SOFT_404_RE.search(text[:400]) and len(text) < 1200:
                    discarded += 1
                    entry["pages"].append({"url": r.url, "status": page.status,
                                           "quotes": 0, "rejected": ["soft_404"]})
                    continue

                # The page must be about THIS company, not merely about someone with
                # this name. The search index returned a mortgage podcast by a different
                # Jon Wells and an unrelated arkmidnight.com page for the Midmark query;
                # without this guard the harness pays a fetch and a parse for each, and
                # the only thing standing between it and a misattributed quote is that
                # the other Jon Wells happened not to be quoted about automation.
                # Session 10 item 6 (E15): tightened to H-FIRSTPARTY-01's rule -- every
                # distinctive token near the top, or the full phrase for a dictionary-word
                # name -- on the harness most exposed to wrong-speaker risk. The old test
                # accepted any one token anywhere in the page.
                about_ok, _about_why = article.is_about_company(text, name)
                if not about_ok:
                    discarded += 1
                    entry["pages"].append({"url": r.url, "status": page.status,
                                           "quotes": 0,
                                           "rejected": ["company_absent_from_page"]})
                    continue

                quotes, rejected = extract_quotes(
                    text, full_name, company_tokens=set(tokens(name)))
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "quotes": len(quotes),
                                       "rejected": [x["reason"] for x in rejected[:6]]})
                if not quotes:
                    discarded += 1
                    continue
                page_titles[r.url] = r.title
                for q in quotes:
                    for theme_key in q.themes:
                        by_theme.setdefault((r.url, theme_key), []).append(q)

        if search_failed is not None:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage=search_failed.failure_stage,
                        failure_category=search_failed.failure_category,
                        fix_class=search_failed.fix_class,
                        failure_detail=str(search_failed)[:400],
                        candidates_evaluated=evaluated, candidates_discarded=discarded)
            print(f"  [!!] {cid} {name}: search failed -- {search_failed}")
            log["companies"].append(entry)
            continue

        obs = [build_observation(company, theme_key, qs, url, stamp,
                                 page_titles.get(url, ""), low_grade_names)
               for (url, theme_key), qs in sorted(by_theme.items())]
        entry["quotes_via_low_grade_names"] = sum(
            1 for qs in by_theme.values() for q in qs if q.executive in low_grade_names)
        proposed.extend(obs)
        entry["quotes"] = sum(len(v) for v in by_theme.values())
        entry["themes"] = sorted({t for _, t in by_theme})

        if obs:
            run.attempt(cid, SIGNAL_TYPE, outcome="covered", records_written=len(obs),
                        source_url_attempted=obs[0].source_url,
                        candidates_evaluated=evaluated, candidates_discarded=discarded)
            print(f"  [ok] {cid} {name}: {len(obs)} observation(s), "
                  f"{entry['quotes']} quote(s) -- {', '.join(entry['themes'])}")
        else:
            # Searched by name, reached readable third-party pages, found no attributable
            # quote on a modernization theme. That is negative evidence about this
            # executive public profile, not a harness miss -- and it is the honest and
            # expected result for most of this population, which is what the taxonomy
            # meant by "yield too low".
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        source_url_attempted=None,
                        candidates_evaluated=evaluated, candidates_discarded=discarded)
            print(f"  [00] {cid} {name}: {evaluated} result(s), no attributable quote")
        log["companies"].append(entry)

    if args.commit:
        # v1.2 supersedes v1.1's rows, so they are REMOVED rather than reconciled.
        #
        # sync_observations only touches rows the run actually proposes, so a corrected
        # harness that stops believing a row leaves the stale one sitting in the sheet --
        # a defect that REMOVES rows otherwise survives its own fix silently. Established
        # by H-PRODUCTQUALITY-01 v1.1's stale Midmark row.
        #
        # keep_reviewed=True: human review is never destroyed by a re-run (convention 1),
        # so a reviewed row survives the delete and is reconciled normally. Both
        # H-TRADEPRESS-01 rows are `accepted`/`human` and are protected by exactly this.
        removed = db.delete_observations(HARNESS_ID, keep_reviewed=True)
        if removed:
            print(f"  removed {removed} row(s) from superseded version(s) before writing")
    refresh_ids = ({i.strip() for i in args.refresh_ids.split(",") if i.strip()}
                   if args.refresh_ids else None)
    refresh_note = (
        f"{stamp}: row re-derived by {HARNESS_ID} {VERSION} from the archived page (offline "
        f"replay) by explicit opt-in; manual review decision preserved."
    ) if args.refresh_reviewed else ""
    report = db.sync_observations(proposed, refresh_reviewed=args.refresh_reviewed,
                                  refresh_note=refresh_note, refresh_ids=refresh_ids)
    run.observations_written = report.written
    summary = run.close()

    print()
    print(f"  {summary['companies_processed']} companies - {len(proposed)} observations "
          f"- {pages.fetch_count} page fetches, {search.stats()['queries_sent']} searches")
    print(f"  coverage {summary['coverage_rate']:.0%} "
          f"({summary['attempts_covered']} covered, "
          f"{summary['attempts_absent_confirmed']} absent_confirmed, "
          f"{summary['attempts_not_covered']} not_covered)")
    print(f"  dedupe: {report.summary()}")
    if log["excluded_vendor_urls"]:
        print(f"  vendor-published URLs excluded (family 6, logged for H-VENDOR-01): "
              f"{len(log['excluded_vendor_urls'])}")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")

    log["summary"] = summary
    log["dedupe"] = report.summary()
    # Session 14: a held conflict is a decision waiting for a person, so the log names it.
    # "1 held for review" with no id was how O00369 / O00373's third companion stayed
    # anonymous for four sessions.
    log["held"] = report.conflicts
    log["refreshed_reviewed"] = report.refreshed_reviewed
    log["search_stats"] = search.stats()
    path = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
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
