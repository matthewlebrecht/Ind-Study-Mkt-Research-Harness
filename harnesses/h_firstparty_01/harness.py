#!/usr/bin/env python3
"""
H-FIRSTPARTY-01 -- First-Party Announcements (press releases, wires, business journals).

WHAT THIS IS FOR
----------------
The second `buyer_articulates` instrument, and the one with the broadest reach. Unlike
H-EXECVOICE-01 it has no prerequisite: it needs no executive roster, so it can cover every
company in the universe including the ones whose sites name nobody.

`docs/signal_taxonomy.md` family 1 rates these sources highly and assigns them
`buyer_articulates` directly: 1a (company newsroom) and 1b (PR wire) at reliability A,
1c (local business journal) at B, "A when directly quoting an exec". This harness
implements that grading rule literally rather than picking one grade for everything.

HOW THIS DIVIDES FROM H-EXECVOICE-01
------------------------------------
Cleanly and deliberately, so one statement is never counted twice as two independent
pieces of evidence. H-EXECVOICE-01 *excludes* the company own domain and the PR wires;
this harness reads exactly those, plus business journals. The two harnesses partition the
space rather than overlapping it, which matters because the same CEO quote routinely
appears in a company press release, on a wire, and in a trade article -- and three rows
saying so is not three times the evidence.

WHY `buyer_articulates` AND NOT `buyer_acts`
--------------------------------------------
A press release announcing a completed deployment is a *statement about* an action, not an
observation of one. The `buyer_acts` rows in this project come from records the company
did not write -- a federal carrier registry, an OSHA inspection, a job posting -- where the
act is visible independently of any claim about it. Here the company is the author, so the
role is articulation, and the fact that a deployment was completed is carried by
`signal_strength = committed_action` instead. Collapsing the two would make the
convergence analysis compare seller messaging against buyer messaging while calling half
of it behaviour.

THE DATING DISCIPLINE
---------------------
This is the harness most exposed to H-WAYBACK-01 failure -- matching a modernization
keyword in a dated news post and reading it as current. Dates come from structured markup
only, never inferred; undated articles keep an empty `publication_date`; and anything older
than five years is excluded from the evidence base and reported as a governance
suppression rather than dropped in silence (convention 7).

    python -m harnesses.h_firstparty_01.harness                 # dry run
    python -m harnesses.h_firstparty_01.harness --commit
    python -m harnesses.h_firstparty_01.harness --limit 15
    python -m harnesses.h_firstparty_01.harness --offline
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
from harnesses.h_execid_01.source import AGGREGATOR_HOSTS, SiteClient  # noqa: E402
from harnesses.h_execvoice_01.harness import VENDOR_CONTENT_RE, WIRE_HOSTS  # noqa: E402
from harnesses.h_firstparty_01 import article                          # noqa: E402
from harnesses.h_firstparty_01 import body as article_body             # noqa: E402

HARNESS_ID = "H-FIRSTPARTY-01"
HARNESS_NAME = "First-Party Announcement Extractor"
VERSION = "v1.3"
SIGNAL_TYPE = "first_party_announcement"
EVIDENCE_FAMILY = "1_first_party_strategy_governance"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

MAX_PAGES_PER_COMPANY = 6

# Regional business-journal networks. `bizjournals.com` is the American City Business
# Journals umbrella covering ~40 metros, which is what makes 1c reachable at all without
# enumerating hundreds of outlets individually.
JOURNAL_HOSTS = {
    "bizjournals.com", "crainsdetroit.com", "crainscleveland.com", "crainschicago.com",
    "chicagobusiness.com", "bizjournal.com", "cityam.com", "columbusceo.com",
    "utahbusiness.com", "vermontbiz.com", "nhbr.com", "virginiabusiness.com",
    "indianapolisbusinessjournal.com", "ibj.com", "bizwest.com", "njbiz.com",
    "bizjournals.com.", "supplychaindive.com", "supplychainbrain.com",
    "manufacturingdive.com", "industryweek.com", "trucknews.com", "ttnews.com",
    "freightwaves.com", "constructiondive.com", "enr.com",
}


def classify_source(url: str, company_host: str) -> tuple[str, str, str]:
    """Return (source_class, source_grade, exclusion_reason).

    Grading follows signal_taxonomy family 1 directly: 1a/1b are A because the company is
    the author of record, 1c is B because a journalist selected and framed it. The
    taxonomy allows 1c an A "when directly quoting an exec"; that upgrade is applied by
    the caller, which is the only place that knows whether a quote was actually found.
    """
    host = host_of(url)
    if host in AGGREGATOR_HOSTS or any(host.endswith("." + a) for a in AGGREGATOR_HOSTS):
        return "", "", "executive_data_aggregator"
    if VENDOR_CONTENT_RE.search(url):
        return "", "", "vendor_customer_content_family_6"
    if re.search(r"(?i)(\.pdf$|/tag/|/tags/|/categor(y|ies)/|/search|/privacy|/terms|/author/|/topics?/)", url):
        return "", "", "non_article_url"
    if company_host and (host == company_host or host.endswith("." + company_host)):
        return "own_newsroom", "A", ""
    if host in WIRE_HOSTS:
        return "pr_wire", "A", ""
    if host in JOURNAL_HOSTS or any(host.endswith("." + j) for j in JOURNAL_HOSTS):
        return "business_journal", "B", ""
    return "", "", "not_a_first_party_or_journal_source"


def has_named_quote(text: str) -> str:
    """A directly quoted passage followed or preceded by an attribution to a named person.

    Used only for the taxonomy 1c grade upgrade, so it deliberately asks a narrower
    question than H-EXECVOICE-01 does: is there a quote attributed to *somebody* named,
    rather than to one specific executive this harness was searching for.
    """
    for m in re.finditer(r"[“\"]([^“”\"]{60,900})[”\"]", text):
        after = text[m.end():m.end() + 120]
        before = text[max(0, m.start() - 120):m.start()]
        attrib = (r"(said|says|explained|noted|added|according to|told)\s+"
                  r"(?:[A-Z][a-z]+\.?\s+){1,3}[A-Z][a-z]+")
        rev = (r"(?:[A-Z][a-z]+\.?\s+){1,3}[A-Z][a-z]+[\w,.\- ]{0,40}?"
               r"(said|says|explained|noted|added|told)")
        if re.search(attrib, after) or re.search(rev, before):
            return m.group(1)[:300]
    return ""


# Which copy of a syndicated announcement to keep. The company own newsroom is the
# source of record; a wire is a distribution channel for the same text; a journal piece
# is a third party writing about it.
SOURCE_PRIORITY = {"own_newsroom": 0, "pr_wire": 1, "business_journal": 2}


def collapse_syndication(by_key: dict) -> tuple[dict, list[dict]]:
    """Collapse the same announcement appearing on several hosts into one observation.

    A press release published on the company newsroom, pushed to PR Newswire and mirrored
    by Yahoo Finance is ONE act of articulation carried by three URLs. Kept as three rows
    it would triple the apparent weight of a single announcement, and because the natural
    key includes `source_url` the reconciler cannot see them as the same claim.

    Convention 19 governs the fix: suppression removes rows, never counts. The surviving
    row is the highest-priority source and it carries the syndication count, so the
    evidence that the announcement was distributed widely is preserved rather than
    destroyed -- the same reasoning that stopped the redundancy filter in
    H-SELLERCONTENT-01 from discarding the instances that justified `repeated_pattern`.

    Grouping is on (theme, publication_date). Two announcements by one company on the same
    day about the same theme are, in practice, one announcement.
    """
    groups: dict[tuple, list] = {}
    for (url, theme_key), v in by_key.items():
        groups.setdefault((theme_key, v["pub"] or url), []).append((url, v))

    kept: dict = {}
    suppressed: list[dict] = []
    for (theme_key, _), members in groups.items():
        members.sort(key=lambda kv: (SOURCE_PRIORITY.get(kv[1]["source_class"], 9),
                                     kv[0]))
        (win_url, win), *rest = members
        win = dict(win)
        win["syndicated"] = len(rest)
        kept[(win_url, theme_key)] = win
        for url, v in rest:
            suppressed.append({"url": url, "theme": theme_key,
                               "kept_instead": win_url,
                               "source_class": v["source_class"]})
    return kept, suppressed


def build_observation(company: dict, theme_key: str, hits: list[str], url: str,
                      source_class: str, grade: str, pub_date: str, retrieval: str,
                      state: str, cue: str, quote: str, title: str,
                      syndicated: int = 0, low_grade: str = "") -> Observation:
    """`low_grade` names the relaxed corroboration gate, or is empty for a full-strength
    row. A low-grade row is grade C / weak_clue / confidence <= 0.4 with the marker."""
    theme = topics.THEMES_BY_KEY[theme_key]
    dated = f"published {pub_date}" if pub_date else "no publication date in the markup"
    syn_note = (f"; also carried on {syndicated} other outlet(s), collapsed to this "
                f"source of record" if syndicated else "")

    # Repetition is the evidence for `repeated_pattern` (convention 19), so it is counted
    # rather than inferred from "a quote was present anywhere on the page" -- which is what
    # the first version did, labelling 161 of 248 rows `repeated_pattern` on as little as
    # one matched term.
    distinct = len({h.strip().lower() for h in hits})
    if re.search(r"(?i)\b(implemented|deployed|completed|went live|installed|invested|"
                 r"launched|opened|selected|partnered)\b", f"{quote} {' '.join(hits)}"):
        strength = "committed_action"
    elif distinct >= 3:
        strength = "repeated_pattern"
    else:
        strength = "weak_clue"
    if re.search(r"\b\d{1,3}\s?(%|percent)\b|\$\s?\d", quote):
        strength = "measured_result"
    if low_grade:
        strength = "weak_clue"

    detectable = ("" if theme.buyer_detectable else
                  " NOTE: no other buyer-side harness can detect this theme, so it "
                  "carries the portfolio-gap caveat in gap analysis.")

    text = (
        f"{company['canonical_name']} publicly announced activity in {theme.label} "
        f"via {source_class.replace('_', ' ')} ({dated}; {len(hits)} distinct term(s) "
        f"matched{syn_note}). Reading: {state.replace('_', ' ')}. This is the company own "
        f"statement about itself, not independent verification that the work was "
        f"delivered.{detectable}"
    )
    excerpt = f"matched: {', '.join(sorted(set(hits))[:10])}"
    if cue:
        excerpt += f" | state cue: {cue}"
    if quote:
        excerpt += f' | quoted: "{quote}"'
    if title:
        excerpt = f"{title} | " + excerpt
    confidence = 0.8 if grade == "A" else 0.65
    if low_grade:
        grade = topics.LOW_GRADE
        confidence = (topics.LOW_GRADE_CONFIDENCE_MAX if low_grade.startswith("single")
                      else topics.LOW_GRADE_CONFIDENCE)
        excerpt = topics.low_grade_excerpt(low_grade, excerpt)
        text = text.replace("publicly announced activity in",
                            "mentioned, on thin evidence, activity in", 1)

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
        publication_date=pub_date,
        retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID,
        harness_version=VERSION,
        confidence_0_1=confidence,
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="H-FIRSTPARTY-01 -- first-party announcements")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--companies")
    ap.add_argument("--pause", type=float, default=0.6)
    ap.add_argument("--retire-stale", action="store_true",
                    help="OPT-IN. After syncing, record invalid (convention 45: nothing is deleted) this harness's machine rows that this run no "
                         "longer produces from a page it actually re-read. Human-reviewed rows are "
                         "HELD and named, never invalidated (convention 35). Refused with --companies "
                         "or --limit. The H-SELLERCONTENT-01 --retire-stale precedent.")
    return ap


def check_retire_args(args) -> None:
    """--retire-stale is judged over the whole buyer set only: a --companies or --limit subset
    leaves every other company's rows unproposed, and they would read as no longer produced."""
    if args.retire_stale and (args.companies or args.limit):
        raise SystemExit("ABORT: --retire-stale needs the full company set, not --companies/--limit")


def retire_stale(db, proposed: list, company_ids, read_urls) -> dict:
    """Record invalid (convention 45) this harness's rows the run no longer produces -- only where it had the evidence.

    Keyed on the natural key of what the run proposed (core/db.py::unreproduced_observations), not
    delete-and-rewrite: every row keeps its id and its place, and a row the run no longer produces is
    recorded `invalidated_not_reproduced` in Observation_Validity_History (core/validity.py) rather
    than removed (convention 45).

    Stricter than the H-SELLERCONTENT-01 use: a row is eligible only if its company is in this run's
    scope AND its source page was successfully re-read in this run. A company whose search failed,
    or a page that was not fetched (page cap, fetch error, a result that no longer surfaces), is not
    evidence that the claim is gone, so those rows are left alone. A human-reviewed row is never
    invalidated: it is HELD and returned by name (convention 35).
    """
    from core import validity
    # Matthew Lebrecht, 2026-09-15 (item 22): these rows are recorded for the REASON, not merely as "not reproduced".
    # v1.2 classified themes on the whole page; v1.3 reads the article body; a row v1.3 does not reproduce from a page
    # it re-read is one whose match was page furniture -- an extraction defect.
    basis = (f"Extraction defect: {HARNESS_ID} {VERSION} reads themes, identity, state and quotes from the ARTICLE "
             f"BODY only (harnesses/h_firstparty_01/body.py). This claim was written by an earlier version that "
             f"classified the whole page -- navigation, teaser rails, footers, cookie banners -- and the page was "
             f"re-read in this run without producing it, so its match lay outside the article. Status set by "
             f"Matthew Lebrecht's instruction, 2026-09-15 (item 22); measured beforehand in "
             f"docs/diagnostics/firstparty_v13_dryrun_2026-09-15.md.")
    return validity.invalidate_unreproduced(db, HARNESS_ID, VERSION, proposed, company_ids={str(c) for c in company_ids},
                                            source_urls={str(u) for u in read_urls},
                                            status="invalidated_extraction_defect", basis=basis)


def main() -> int:
    args = build_parser().parse_args()
    # ON HOLD since 2026-09-15 (core/holds.py): refuses every live run and every --commit before anything is
    # opened; an offline dry replay is still allowed.
    from core import holds
    holds.enforce(HARNESS_ID, offline=args.offline, commit=args.commit)
    check_retire_args(args)

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
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY}, commit=args.commit)

    proposed: list[Observation] = []
    read_urls: set[str] = set()     # pages fetched successfully this run (--retire-stale eligibility)
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "companies": [], "suppressed_stale": []}

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        company_host = host_of(str(company.get("website") or ""))
        entry = {"company_id": cid, "name": name, "pages": [], "excluded": []}
        name_tokens = {t for t in tokens(name) if len(t) > 2}

        queries = [
            f'"{name}" (announces OR announced OR "press release") '
            f'(technology OR automation OR software OR system OR investment OR facility)',
            f'"{name}" ("digital transformation" OR ERP OR "supply chain technology" '
            f'OR modernization OR robotics OR "warehouse management")',
        ]
        results = []
        failed = None
        for q in queries:
            try:
                results.extend(search.search(q, count=10))
            except SearchError as e:
                failed = e
                break
        if failed is not None:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage=failed.failure_stage,
                        failure_category=failed.failure_category,
                        fix_class=failed.fix_class, failure_detail=str(failed)[:400])
            print(f"  [!!] {cid} {name}: search failed -- {failed}")
            log["companies"].append(entry)
            continue

        evaluated = discarded = fetched = 0
        stale = 0
        by_key: dict[tuple[str, str], dict] = {}
        seen_urls: set[str] = set()

        for r in results:
            if r.url in seen_urls:
                continue
            seen_urls.add(r.url)
            evaluated += 1
            source_class, grade, why = classify_source(r.url, company_host)
            if why:
                discarded += 1
                entry["excluded"].append({"url": r.url, "reason": why})
                continue
            if fetched >= MAX_PAGES_PER_COMPANY:
                continue
            page = client.get(r.url)
            fetched += 1
            if not page.ok:
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status})
                continue
            read_urls.add(r.url)

            lines = html_lines(page.html)
            is_article, why_not = article.looks_like_article(lines, r.url, r.title)
            if not is_article:
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "rejected": why_not})
                continue
            # v1.3 (2026-09-15): identity, themes, state and quotes are read from the ARTICLE BODY only
            # (body.py). v1.2 read the whole page -- navigation, teaser rails, footers, cookie banners -- and 109 of
            # its 230 rows had no theme match in the article. The page-shape test above still reads the whole page:
            # being a listing is a property of the page, not of its body.
            extracted = article_body.extract(page.html)
            text = extracted.text
            body_info = {"body_chars": len(text), "end_marker": extracted.end_marker,
                         "consent_elements_removed": extracted.consent_elements_removed,
                         "consent_lines_dropped": extracted.consent_lines_dropped,
                         "footer_notices_dropped": extracted.footer_notices_dropped,
                         "footer_cut": extracted.footer_cut, "list_items_kept": extracted.list_items_kept}
            if len(text) < article_body.MIN_BODY_CHARS:
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status, "body": body_info,
                                       "rejected": f"no article body extracted ({len(text)} chars)"})
                continue

            # The article must be about THIS company, not merely surfaced by a search for
            # its name. See article.is_about_company for the Prime Inc. failure that set
            # the strictness here.
            about, why_not_about = article.is_about_company(text, name, r.title)
            if not about:
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "rejected": f"not about this company: {why_not_about}"})
                continue

            pub = article.published_date(page.html)

            # A standing page on the company site is not an announcement. Accepted only if
            # the URL is announcement-shaped or the page carries a real publication date --
            # otherwise the Midmark leadership-team page counts as first-party news.
            if source_class == "own_newsroom" and not article.is_announcement_url(r.url) \
                    and not pub:
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "rejected": "standing page, not a dated announcement"})
                continue
            age = article.age_days(pub, stamp)
            if age is not None and age > article.MAX_AGE_DAYS:
                stale += 1
                log["suppressed_stale"].append({"company_id": cid, "url": r.url,
                                                "published": pub, "age_days": age})
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "rejected": f"stale ({pub}, {age} days)"})
                continue

            tiered = topics.classify_tiered(text)
            themes = {k: v for k, (v, t) in tiered.items() if t == "strong"}
            weak_themes = {k: v for k, (v, t) in tiered.items() if t == "weak"}
            if not themes and not weak_themes:
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "source_class": source_class, "themes": [], "body": body_info})
                continue
            state, cue = article.interpret_state(text)
            quote = has_named_quote(text)
            # Taxonomy 1c: a business journal piece rises to A when it directly quotes an
            # executive, because the attribution is then first-party inside a second-party
            # frame.
            effective_grade = "A" if (grade == "B" and quote) else grade
            entry["pages"].append({"url": r.url, "status": page.status,
                                   "source_class": source_class, "grade": effective_grade,
                                   "published": pub, "themes": sorted(themes),
                                   "has_quote": bool(quote), "body": body_info})
            for theme_key, hits in themes.items():
                # Admission threshold: see article.theme_is_the_subject. A single generic
                # word in a long release is not an announcement about that theme. Since
                # 2026-09-03 (corroboration-gate policy) that is a LOW-GRADE write, not a
                # refusal: the referent is right, the claim is thin, the reviewer decides.
                low_grade = ""
                if not article.theme_is_the_subject(hits, f"{r.title} {r.description}"):
                    entry.setdefault("theme_below_threshold", []).append(
                        {"url": r.url, "theme": theme_key, "hits": hits,
                         "written_low_grade": True})
                    low_grade = "single generic term, not in the headline"
                by_key[(r.url, theme_key)] = {
                    "hits": hits, "source_class": source_class,
                    "grade": effective_grade, "pub": pub, "state": state, "cue": cue,
                    "quote": quote, "title": r.title, "low_grade": low_grade}
            for theme_key, hits in weak_themes.items():
                if (r.url, theme_key) in by_key:
                    continue
                entry.setdefault("theme_below_threshold", []).append(
                    {"url": r.url, "theme": theme_key, "hits": hits,
                     "written_low_grade": True, "tier": "generic_only"})
                by_key[(r.url, theme_key)] = {
                    "hits": hits, "source_class": source_class,
                    "grade": effective_grade, "pub": pub, "state": state, "cue": cue,
                    "quote": quote, "title": r.title,
                    "low_grade": "generic-tier term(s) only"}

        by_key, syndicated = collapse_syndication(by_key)
        obs = [build_observation(company, theme_key, v["hits"], url, v["source_class"],
                                 v["grade"], v["pub"], stamp, v["state"], v["cue"],
                                 v["quote"], v["title"], v.get("syndicated", 0),
                                 low_grade=v.get("low_grade", ""))
               for (url, theme_key), v in sorted(by_key.items())]
        proposed.extend(obs)
        entry["observations"] = len(obs)
        entry["syndicated_suppressed"] = syndicated

        # Convention 7: a suppression that fires becomes a recorded governance fact on the
        # attempt, never a silence.
        governance = {}
        if syndicated:
            governance = {"failure_stage": "governance",
                          "failure_category": "suppressed_redundant",
                          "failure_detail": f"{len(syndicated)} syndicated copy(ies) of "
                                            f"an announcement already counted from its "
                                            f"source of record; the surviving row carries "
                                            f"the instance count"}
        if stale:
            governance = {"failure_stage": "temporal",
                          "failure_category": "stale_beyond_threshold",
                          "failure_detail": f"{stale} article(s) excluded as older than "
                                            f"{article.MAX_AGE_DAYS // 365} years"}

        if obs:
            run.attempt(cid, SIGNAL_TYPE, outcome="covered", records_written=len(obs),
                        source_url_attempted=obs[0].source_url,
                        candidates_evaluated=evaluated, candidates_discarded=discarded,
                        **governance)
            print(f"  [ok] {cid} {name}: {len(obs)} observation(s) from "
                  f"{len({u for u, _ in by_key})} article(s)"
                  + (f" ({stale} stale suppressed)" if stale else ""))
        elif fetched:
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        candidates_evaluated=evaluated, candidates_discarded=discarded,
                        **governance)
            print(f"  [00] {cid} {name}: read {fetched} article(s), no modernization theme")
        else:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage="discovery", failure_category="source_not_found",
                        fix_class="source_limitation",
                        failure_detail=f"{evaluated} search result(s), none on a "
                                       f"first-party or business-journal source",
                        candidates_evaluated=evaluated, candidates_discarded=discarded)
            print(f"  [--] {cid} {name}: no first-party source among {evaluated} results")
        log["companies"].append(entry)

    report = db.sync_observations(proposed)
    retired = {"invalidated": [], "held": []}
    if args.retire_stale:
        retired = retire_stale(db, proposed, [c["company_id"] for c in companies], read_urls)
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
    if args.retire_stale:
        print(f"  not reproduced: {len(retired['invalidated'])} machine row(s) no longer produced from a re-read "
              f"page recorded invalid (convention 45; nothing deleted) [{', '.join(retired['invalidated'])}]"
              + (f"; {len(retired['held'])} human-reviewed row(s) HELD, not invalidated "
                 f"[{', '.join(retired['held'])}]" if retired["held"] else ""))
    if log["suppressed_stale"]:
        print(f"  stale articles suppressed (>{article.MAX_AGE_DAYS // 365}y): "
              f"{len(log['suppressed_stale'])}")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")

    log["summary"] = summary
    log["dedupe"] = report.summary()
    log["retired"] = retired
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
