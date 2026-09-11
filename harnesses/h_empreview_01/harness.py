#!/usr/bin/env python3
"""
H-EMPREVIEW-01 -- Employee Review Aggregate (family 4, employee experience & workarounds).

WHAT THIS HARNESS IS FOR
------------------------
It is the portfolio's only instrument that can report a `legacy_constraint` at scale.

H-FIRSTPARTY-01 supplies most of the current `buyer_articulates` evidence, and it is
structurally incapable of reporting a constraint: a company press release does not announce
its own obsolescence, which that harness records as a known limitation. H-EXECVOICE-01 can
in principle but yields 8 observations across the whole universe. Employee reviews are the
one source where the people actually operating the systems describe them with no
communications department in between -- "we still do it in spreadsheets", "the systems
don't talk to each other".

Convention 21a is why that matters right now: the buyer side of the gap analysis is leaning
on announcement data, announcements are a biased instrument, and the two live candidate
divergences sit on exactly the themes companies are least likely to announce.

AGGREGATE ONLY
--------------
`docs/signal_taxonomy.md` 4a rates a single review C and an aggregate B, with an explicit
instruction: "design it as a theme-extraction-over-N-reviews harness, not a single-review
extractor, or it will sit at C forever." So there is no row per review. Every observation
is a count over a sample, the sample size travels in the observation text, and a company
below `MIN_REVIEWS` is `not_covered` for insufficient sample -- a statement about the
sample, never about the company.

THE ACCESS FINDING, WHICH IS THE MAIN RESULT
--------------------------------------------
Both sources this harness was commissioned to read are closed to compliant automated
collection:

    glassdoor.com   robots.txt Disallow: /       for ClaudeBot / anthropic-ai  (+ HTTP 403)
    indeed.com      robots.txt Disallow: /cmp/   for ClaudeBot / anthropic-ai

That is a publisher decision, not an engineering problem, and picking a user-agent that
misses their blocklists would be evasion rather than a fix. Comparably is the one permitted
substitute with real coverage of this population, and it rate-limits hard.

The harness records all of this rather than returning a quiet zero, because family 4 is the
only place a `legacy_constraint` can come from: a silence here would license the conclusion
that employees are not complaining about systems, when the truth is that this harness is
not allowed to look. Convention 6a.

    python -m harnesses.h_empreview_01.harness                 # dry run
    python -m harnesses.h_empreview_01.harness --commit
    python -m harnesses.h_empreview_01.harness --limit 10
    python -m harnesses.h_empreview_01.harness --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache                                     # noqa: E402
from core.db import MarketIntelDB, Observation, today                 # noqa: E402
from core.robots import RobotsGate                                    # noqa: E402
from core.search import BraveSearch, SearchError                      # noqa: E402
from core import topics                                              # noqa: E402
from harnesses.h_empreview_01 import reviews as rv                    # noqa: E402
from harnesses.h_empreview_01.source import (                         # noqa: E402
    PAUSE_SECONDS, SOURCE_STATUS, ReviewSiteClient, candidate_slugs, reviews_url,
    slug_of, verify_company)

HARNESS_ID = "H-EMPREVIEW-01"
HARNESS_NAME = "Employee Review Aggregate"
VERSION = "v1.1"
SIGNAL_TYPE = "employee_review_aggregate"
EVIDENCE_FAMILY = "4_employee_experience_workarounds"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# Taxonomy 4a: C for a single review, B in aggregate. This harness only ever emits
# aggregates, so B is the grade -- and A is unreachable no matter how many reviews agree,
# because a self-selected sample of former employees is not an authoritative record.
SOURCE_GRADE = "B"

BLOCKED_NOTE = ("glassdoor.com and indeed.com are both disallowed by robots.txt for this "
                "crawler identity, so the two highest-availability family-4 sources "
                "contributed nothing to this run")


def build_observation(company: dict, finding, sample: int, state: str, cue: str,
                      url: str, rating: str, retrieval: str,
                      low_grade: bool = False) -> Observation:
    """`low_grade`: below this harness's admission threshold (a single review on a single
    term) -- written at C / weak_clue / 0.3 with the marker under the 2026-09-03 policy."""
    theme = topics.THEMES_BY_KEY[finding.theme_key]
    terms = sorted({t.strip() for t in finding.terms}, key=str.lower)

    text = (
        f"{finding.review_count} of {sample} employee review(s) for "
        f"{company['canonical_name']} reference {theme.label} "
        f"(aggregate rating {rating or 'n/a'}). Reading: {state.replace('_', ' ')}. "
        f"This is an aggregate over a self-selected sample of reviewers, not a "
        f"representative survey; a single review would not support this claim "
        f"(taxonomy 4a rates one review C and an aggregate B)."
    )
    excerpt = f"matched: {', '.join(terms[:10])}"
    if cue:
        excerpt += f" | state cue: {cue}"
    for e in finding.excerpts[:2]:
        excerpt += f' | review: "{e}"'

    # Confidence tracks how much of the sample agreed, capped well below certainty because
    # the sample is self-selected however many reviewers agree.
    confidence = round(min(0.75, 0.4 + 0.1 * finding.review_count), 2)
    grade, strength = SOURCE_GRADE, finding.signal_strength
    if low_grade:
        grade, strength, confidence = topics.LOW_GRADE, "weak_clue", topics.LOW_GRADE_CONFIDENCE
        excerpt = topics.low_grade_excerpt(
            f"{finding.review_count} review(s) on {len(set(finding.terms))} term(s), below "
            f"the admission threshold", excerpt)

    return Observation(
        company_id=company["company_id"],
        evidence_family=EVIDENCE_FAMILY,
        evidence_role="buyer_articulates",
        topic=finding.theme_key,
        organizational_state=state,
        signal_strength=strength,
        observation_text=text,
        evidence_excerpt=excerpt[:2000],
        source_url=url,
        publication_date="",       # individual reviews are undated on the page
        retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID,
        harness_version=VERSION,
        confidence_0_1=confidence,
    )


def resolve_profile(client: ReviewSiteClient, search: BraveSearch, company: dict,
                    entry: dict):
    """Find and verify this company's Comparably profile. Returns (page, url) or (None, "")."""
    name = company["canonical_name"]
    tried: list[str] = []

    for cand in candidate_slugs(name):
        url = reviews_url(cand)
        tried.append(cand)
        page = client.get(url)
        if page.robots_blocked:
            entry["robots_blocked"] = page.blocked_reason
            return None, url
        if client.breaker.tripped:
            return None, url
        if not page.ok:
            continue
        parsed = rv.parse_page(page.html)
        ok, s, why = verify_company(parsed.declared_name, name)
        entry.setdefault("verification", []).append(
            {"slug": cand, "declared": parsed.declared_name, "score": s, "ok": ok})
        if ok:
            return page, url
        entry.setdefault("rejected_profiles", []).append({"slug": cand, "why": why})

    # Search fallback, still verified. Rank is never trusted: the query for "Prime Inc."
    # returns comparably.com/companies/cprime, a different company entirely.
    try:
        results = search.search(f'site:comparably.com "{name}" reviews', count=6)
    except SearchError as e:
        entry["search_error"] = str(e)
        return None, ""
    for r in results:
        cand = slug_of(r.url)
        if not cand or cand in tried:
            continue
        tried.append(cand)
        url = reviews_url(cand)
        page = client.get(url)
        if page.robots_blocked:
            entry["robots_blocked"] = page.blocked_reason
            return None, url
        if client.breaker.tripped:
            return None, url
        if not page.ok:
            continue
        parsed = rv.parse_page(page.html)
        ok, s, why = verify_company(parsed.declared_name, name)
        entry.setdefault("verification", []).append(
            {"slug": cand, "declared": parsed.declared_name, "score": s, "ok": ok})
        if ok:
            return page, url
        entry.setdefault("rejected_profiles", []).append({"slug": cand, "why": why})

    entry["slugs_tried"] = tried
    return None, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="H-EMPREVIEW-01 -- employee review aggregate")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--companies")
    ap.add_argument("--pause", type=float, default=PAUSE_SECONDS)
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
    cache = DatedCache(OUTPUT_DIR / "raw" / "pages", offline=args.offline,
                       retrieval_date=stamp, pause_seconds=args.pause)
    gate = RobotsGate()
    client = ReviewSiteClient(cache, gate)
    search = BraveSearch(OUTPUT_DIR / "raw" / "search", offline=args.offline,
                         retrieval_date=stamp, pause_seconds=1.0)

    # Record the access status of every declared source, checked live rather than asserted.
    access = {}
    for host, meta in SOURCE_STATUS.items():
        probe = f"https://www.{host}/" if not host.startswith("www.") else f"https://{host}/"
        sample = {"glassdoor.com": "https://www.glassdoor.com/Reviews/index.htm",
                  "indeed.com": "https://www.indeed.com/cmp/Kenco-Group/reviews",
                  "careerbliss.com": "https://www.careerbliss.com/reviews/",
                  "comparably.com": "https://www.comparably.com/companies/kenco-group/reviews",
                  }.get(host, probe)
        allowed, why = gate.check(sample)
        access[host] = {**meta, "robots_allows_now": allowed, "robots_reason": why}
    for host, a in access.items():
        flag = "permitted" if a["robots_allows_now"] else "BLOCKED"
        print(f"  source {host:18s} {flag:9s} {a['robots_reason'][:76]}")
    print()

    scope = [(c["company_id"], SIGNAL_TYPE) for c in companies]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY}, commit=args.commit)

    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "source_access": access, "companies": []}

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        entry = {"company_id": cid, "name": name}

        if client.breaker.tripped:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered", failure_stage="fetch",
                        failure_category="access_blocked", fix_class="source_limitation",
                        failure_detail="run stopped early: comparably.com returned "
                                       f"{client.breaker.limit} consecutive access "
                                       f"failures, so remaining companies were not "
                                       f"requested. " + BLOCKED_NOTE)
            entry["outcome"] = "circuit_breaker"
            log["companies"].append(entry)
            continue

        page, url = resolve_profile(client, search, company, entry)

        if entry.get("robots_blocked"):
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered", failure_stage="fetch",
                        failure_category="access_blocked", fix_class="source_limitation",
                        failure_detail=f"{entry['robots_blocked']}. {BLOCKED_NOTE}",
                        source_url_attempted=url)
            print(f"  [--] {cid} {name}: robots-blocked")
            log["companies"].append(entry)
            continue

        if page is None:
            if client.breaker.tripped or client.last_status in (403, 429, 503):
                # Route on what the server actually said. Reporting a rate-limit block as
                # `source_not_found` would assert the company has no profile, which is a
                # claim about the company rather than about the connection -- the same
                # misdiagnosis H-EXECID-01 made when it recorded unreadable pages as
                # extraction failures.
                cat, detail = "access_blocked", (
                    f"comparably.com returned HTTP {client.last_status} (edge rate "
                    f"limiting); whether this company has a profile is unknown. "
                    + BLOCKED_NOTE)
            elif entry.get("search_error"):
                # Session 10 item 6 (R9): the search fallback failed, so absence of a
                # profile is not established (core/search.py's rule).
                cat, detail = "source_unavailable", (
                    f"search fallback failed ({str(entry['search_error'])[:100]}); whether "
                    f"a Comparably profile exists is unknown. " + BLOCKED_NOTE)
            else:
                cat, detail = "source_not_found", (
                    "no verified Comparably profile: "
                    f"{len(entry.get('rejected_profiles', []))} candidate profile(s) "
                    f"failed name verification, slugs tried "
                    f"{entry.get('slugs_tried', [])[:4]}. " + BLOCKED_NOTE)
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage="fetch" if cat == "source_unavailable" else "discovery",
                        failure_category=cat,
                        fix_class="transient" if cat == "source_unavailable" else "source_limitation",
                        failure_detail=detail, source_url_attempted=url or None,
                        candidates_evaluated=len(entry.get("verification", [])),
                        candidates_discarded=len(entry.get("rejected_profiles", [])))
            print(f"  [--] {cid} {name}: {cat}")
            log["companies"].append(entry)
            continue

        parsed = rv.parse_page(page.html)
        usable = parsed.usable_reviews
        entry.update({"url": url, "rating": parsed.rating_value,
                      "reviews_parsed": len(parsed.reviews), "usable": len(usable)})

        below_floor = len(usable) < rv.MIN_REVIEWS
        if below_floor and not usable:
                # A statement about the sample, never about the company. Deliberately NOT
                # absent_confirmed: too few reviews to support an aggregate is not evidence
                # that employees have nothing to say.
                run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                            failure_stage="extraction",
                            failure_category="content_unstructured",
                            fix_class="source_limitation",
                            failure_detail=f"only {len(usable)} usable review(s), below the "
                                           f"{rv.MIN_REVIEWS}-review floor an aggregate claim "
                                           f"needs (taxonomy 4a rates a single review C)",
                            source_url_attempted=url)
                print(f"  [--] {cid} {name}: {len(usable)} usable review(s), below floor")
                entry["outcome"] = "insufficient_sample"
                log["companies"].append(entry)
                continue

        if below_floor:
            # 2026-09-03 corroboration-gate policy: a sample under the 5-review floor is a
            # corroboration-strength refusal (the profile is verified as this company's;
            # the sample is thin). Themes from it are written at low grade -- grade C,
            # taxonomy 4a's single-review grade -- instead of refused. The attempt stays
            # `partial`, not `covered`, because the aggregate claim is not earned.
            entry["outcome"] = "below_floor_low_grade"
        findings, low, below = rv.aggregate_themes_tiered(usable)
        state, cue = rv.interpret_state([r.text for r in usable])
        entry.update({"themes": [(f.theme_key, f.review_count) for f in findings],
                      "themes_low_grade": [(f.theme_key, f.review_count) for f in low],
                      "themes_below_threshold": below, "state": state})

        obs = [build_observation(company, f, len(usable), state, cue, url,
                                 parsed.rating_value, stamp, low_grade=below_floor)
               for f in findings]
        obs += [build_observation(company, f, len(usable), state, cue, url,
                                  parsed.rating_value, stamp, low_grade=True) for f in low]
        proposed.extend(obs)

        if obs:
            run.attempt(cid, SIGNAL_TYPE, outcome="partial" if below_floor else "covered",
                        records_written=len(obs),
                        source_url_attempted=url, candidates_evaluated=len(usable),
                        candidates_discarded=len(parsed.reviews) - len(usable))
            print(f"  [ok] {cid} {name}: {len(obs)} theme(s) over {len(usable)} review(s) "
                  f"-- {', '.join(f.theme_key for f in findings)}")
        else:
            # Read a real sample above the floor and no reviewer mentioned systems or
            # tooling. That is negative evidence about this workforce's concerns, which is
            # a genuine result for a source dominated by pay-and-management commentary.
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        source_url_attempted=url, candidates_evaluated=len(usable),
                        candidates_discarded=len(parsed.reviews) - len(usable))
            print(f"  [00] {cid} {name}: {len(usable)} review(s), no modernization theme")
        log["companies"].append(entry)

    report = db.sync_observations(proposed)
    run.observations_written = report.written
    run.material_revision_notes = BLOCKED_NOTE
    summary = run.close()

    blocked = [h for h, a in access.items() if not a["robots_allows_now"]]
    print()
    print(f"  {summary['companies_processed']} companies - {len(proposed)} observations "
          f"- {cache.fetch_count} page fetches")
    print(f"  coverage {summary['coverage_rate']:.0%} "
          f"({summary['attempts_covered']} covered, "
          f"{summary['attempts_absent_confirmed']} absent_confirmed, "
          f"{summary['attempts_not_covered']} not_covered)")
    print(f"  dedupe: {report.summary()}")
    print(f"  sources blocked by robots.txt: {', '.join(blocked) if blocked else 'none'}")
    if client.breaker.tripped:
        print("  CIRCUIT BREAKER tripped -- comparably.com refused sustained access; "
              "remaining companies were not requested")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")

    log["summary"] = summary
    log["dedupe"] = report.summary()
    log["circuit_breaker_tripped"] = client.breaker.tripped
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
