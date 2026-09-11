#!/usr/bin/env python3
"""
H-WAYBACK-01 — Disappeared-Evidence Detector (evidence family 18).

WHY THIS SIGNAL IS DIFFERENT FROM EVERY OTHER ONE IN THE PORTFOLIO
------------------------------------------------------------------
Every other harness reads what a company currently publishes. This one reads what a
company *stopped* publishing — a case study taken down, a technology or innovation page
removed, a service line quietly dropped. `docs/signal_taxonomy.md` 18a calls it one of the
more genuinely novel signal types in the taxonomy, and notes it may matter more for private
companies specifically, since they leave a thinner live footprint to begin with.

Nothing else in the portfolio can see this. A live-page harness sees only what survived.

WHAT IT CLAIMS — AND THE ONE FAILURE MODE THAT WOULD MAKE IT WORTHLESS
----------------------------------------------------------------------
The diff is objective; the interpretation is not. A page can vanish because the initiative
behind it was cancelled, or because the marketing site was replatformed and every URL
changed at once. The second is extremely common and carries no signal whatsoever.

Reading a replatform as abandonment would be this harness's version of the Infor /
"Information Systems" bug: a loose rule manufacturing confidence rather than merely adding
noise, at a scale of dozens of companies. So `core.wayback.disappeared()` reports a
replatform indicator, and this harness *refuses to emit a modernization claim* when it
fires, recording `classification_ambiguous` instead. A run where most companies replatformed
should produce few observations, and that is the correct outcome, not a failure.

Only paths whose slug suggests modernization-relevant content are considered — case
studies, technology, innovation, digital, automation. A disappeared "contact us" page is
not evidence of anything.

    python -m harnesses.h_wayback_01.harness              # dry run
    python -m harnesses.h_wayback_01.harness --commit
    python -m harnesses.h_wayback_01.harness --offline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import resolution, wayback  # noqa: E402
from core.cache import DatedCache  # noqa: E402
from core import topics  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402

HARNESS_ID = "H-WAYBACK-01"
HARNESS_NAME = "Disappeared-Evidence Detector"
VERSION = "v1.3"
SIGNAL_TYPE = "removed_page"
EVIDENCE_FAMILY = "18_historical_change_disappearing_evidence"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# A path is only interesting if its slug suggests content about how the business runs or
# what it is building. A removed careers listing or "about us" is not evidence.
RELEVANT_PATH = re.compile(
    r"(case[-_]?stud|success[-_]?stor|customer[-_]?stor|technolog|innovat|digital|"
    r"automat|transform|capabilit|solution|modern|sustainab|initiative)", re.I)

# Excluded BEFORE relevance is tested, and this is the load-bearing half of the filter.
#
# The first version of this harness reported 12 "removed modernization pages" for McGough
# Construction. Every one was a dated news or award post under /about-us/news/ that matched
# on a substring -- "research" inside "aquatic-invasive-species-research-center", "innovat"
# inside an award title. News archives are pruned on a schedule; that is routine content
# lifecycle, not a company withdrawing a capability claim.
#
# This is the Infor / "Information Systems" failure in a new place: a loose pattern
# manufacturing confidence rather than merely adding noise. A dated article is excluded
# even when its slug matches, because the removal of one news item can never carry the
# claim this harness makes.
EXCLUDED_PATH = re.compile(
    r"(/news/|/blog/|/press|/media/|/events?/|/awards?/|/article|/post/|"
    r"/careers?/|/jobs?/|/people/|\d{4}/\d{2}/)", re.I)

# Archive coverage is sparse for mid-size private companies, so a path needs to have been
# captured at least this often before its absence means anything. A path seen once, years
# ago, is more likely an archive gap than a removal.
MIN_CAPTURES_FOR_CLAIM = 2

# Last-successful-capture before this year, while the site is still being archived, counts
# as gone. Two years back from the run date: recent enough to be current, old enough that
# an archive revisit would have happened.
CUTOFF_YEARS_BACK = 2


def build_observation(company, gone, live, site_last, retrieval, capture_counts,
                      low_grade: bool = False, confound: str = ""):
    """`low_grade`: every removed path was captured only once, so an archive gap cannot
    be excluded (2026-09-03 policy: written at C / weak_clue / 0.3, marked, not dropped)."""
    paths = sorted(gone, key=lambda c: c.timestamp, reverse=True)
    strength = "repeated_pattern" if len(paths) >= 3 else "weak_clue"
    conf = 0.6 if len(paths) >= 3 else 0.45
    grade = "B"   # the diff is solid; the interpretation is not -- taxonomy 18a
    if low_grade:
        strength, conf, grade = "weak_clue", topics.LOW_GRADE_CONFIDENCE, topics.LOW_GRADE

    listed = "; ".join(
        f"{c.original} (last successful capture {c.iso}, "
        f"{capture_counts.get(c.urlkey, 1)} captures)" for c in paths[:6])
    if len(paths) > 6:
        listed += f" (+{len(paths) - 6} more)"

    text = (
        f"{len(paths)} modernization-relevant page(s) on {company['canonical_name']}'s site "
        f"were archived successfully and have no successful capture since "
        f"{min(c.year for c in paths)}-{max(c.year for c in paths)}, while the domain "
        f"itself was still being archived as recently as {site_last.iso} "
        f"({len(live)} other path(s) still captured). Content that was published and later "
        f"removed is evidence no live-page source can show. The removal is objective; the "
        f"reason is not — a cancelled initiative and a routine content cull look identical "
        f"from the archive, so this is a prompt for investigation rather than a finding."
    )

    if low_grade:
        text += (" Every path here was captured only ONCE, so an archive gap cannot be "
                 "distinguished from a removal; this is the weakest form of the claim.")
        listed = topics.low_grade_excerpt(
            f"{len(paths)} removed path(s) captured once each, below the "
            f"{MIN_CAPTURES_FOR_CLAIM}-capture floor", listed)
    if confound:
        # Session 10 item 2: the replatform refusal is admitted as a CONFOUND, not as a
        # weak claim. Distinct marker; same mechanical tier.
        strength, conf, grade = "weak_clue", topics.LOW_GRADE_CONFIDENCE, topics.LOW_GRADE
        text += (f" CONFOUND: {confound}. The pattern is consistent with a site replatform "
                 f"rather than content removal; do not read as abandonment without "
                 f"checking the live site.")
        listed = topics.confound_excerpt("W8 replatform refusal", listed)
    return Observation(
        company_id=company["company_id"], evidence_family=EVIDENCE_FAMILY,
        evidence_role="buyer_acts", topic="removed_public_content",
        organizational_state="unknown", signal_strength=strength,
        observation_text=text, evidence_excerpt=listed,
        source_url=paths[0].archive_url,
        publication_date=paths[0].iso, retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=conf,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="H-WAYBACK-01 — disappeared evidence")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--companies")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = [c for c in db.companies()
                 if str(c["company_id"]).startswith(("C", "A"))
                 and c.get("qualification_status") != "excluded"]
    if args.companies:
        want = {x.strip() for x in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"] in want]
    if args.limit:
        companies = companies[:args.limit]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = today()
    cutoff = date.fromisoformat(stamp).year - CUTOFF_YEARS_BACK
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=2.0)
    client = wayback.WaybackClient(cache)

    scope = [(c["company_id"], SIGNAL_TYPE) for c in companies]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY}, commit=args.commit)

    proposed = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "cutoff_year": cutoff, "offline": args.offline, "companies": []}

    for c in companies:
        cid, name = c["company_id"], c["canonical_name"]
        site = (c.get("website") or "").strip()
        entry = {"company_id": cid, "name": name, "website": site}

        if not site:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage="discovery", failure_category="source_not_found",
                        fix_class="code_change",
                        failure_detail="Companies.website is blank; the CDX index is "
                                       "queried by domain")
            entry["outcome"] = "no_website"
            log["companies"].append(entry)
            print(f"  [--] {cid} {name[:34]:34s} no website on file")
            continue

        domain = re.sub(r"^https?://", "", site).strip("/").split("/")[0]
        try:
            caps, cdx_truncated = client.snapshots(
                domain, match_type="domain", from_year="2015",
                to_year=str(date.fromisoformat(stamp).year), collapse="")
        except (requests.RequestException, RuntimeError) as e:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered", failure_stage="fetch",
                        failure_category="source_unavailable", fix_class="transient",
                        failure_detail=f"{type(e).__name__}: {e}",
                        source_url_attempted=f"{wayback.CDX}?url={domain}")
            entry["outcome"] = f"error: {e}"
            log["companies"].append(entry)
            print(f"  [!!] {cid} {name[:34]:34s} {type(e).__name__}")
            continue

        cdx_url = f"{wayback.CDX}?url={domain}&matchType=domain&output=json"
        relevant = [c2 for c2 in caps
                    if RELEVANT_PATH.search(c2.urlkey)
                    and not EXCLUDED_PATH.search(c2.original)]
        counts: dict[str, int] = {}
        for c2 in relevant:
            counts[c2.urlkey] = counts.get(c2.urlkey, 0) + 1

        if not caps:
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        source_url_attempted=cdx_url, candidates_evaluated=0)
            entry["outcome"] = "no_archive_coverage"
            log["companies"].append(entry)
            print(f"  [00] {cid} {name[:34]:34s} no archived captures")
            continue

        split = wayback.disappeared(relevant, cutoff_year=cutoff)
        gone = [g for g in split["gone"] if counts.get(g.urlkey, 0) >= MIN_CAPTURES_FOR_CLAIM]
        singles = [g for g in split["gone"] if counts.get(g.urlkey, 0) < MIN_CAPTURES_FOR_CLAIM]

        entry.update({"relevant_paths": len(counts), "gone": len(gone),
                      "live": len(split["live"]),
                      "replatform_suspected": split["replatform_suspected"]})

        if split["replatform_suspected"]:
            # v1.1-v1.2 refused the claim outright. Session 10 item 2 (Matthew): admit it
            # at low grade with a DISTINCT confound marker -- the removals are real, the
            # referent is right, and a competing explanation (a site migration) is
            # affirmatively supported, which is not the same as a weak-but-correct claim.
            confound = (f"{len(split['gone'])} of {len(counts)} relevant paths gone "
                        f"({split['gone_share']:.0%}), last seen predominantly in "
                        f"{split['dominant_year']}")
            confound_paths = gone or singles or split["gone"]
            obs = build_observation(c, confound_paths, split["live"],
                                    split["site_last_seen"], stamp, counts,
                                    low_grade=not gone, confound=confound)
            proposed.append(obs)
            run.attempt(cid, SIGNAL_TYPE, outcome="covered", records_written=1,
                        source_url_attempted=cdx_url,
                        candidates_evaluated=len(counts),
                        candidates_discarded=len(counts) - len(confound_paths))
            entry["outcome"] = "replatform_suspected_confound_admitted"
            print(f"  [cf] {cid} {name[:34]:34s} replatform suspected "
                  f"({split['gone_share']:.0%} gone, peak {split['dominant_year']}) "
                  f"— written as a confound-admitted low-grade row")
        elif not gone and singles:
            # 2026-09-03 policy: single-capture removals are a corroboration-strength
            # refusal (right site, right paths, one capture each). v1.1 folded them into
            # absent_confirmed, which recorded a threshold refusal as negative evidence.
            # Now a low-grade row, and the attempt is covered.
            obs = build_observation(c, singles, split["live"], split["site_last_seen"],
                                    stamp, counts, low_grade=True)
            proposed.append(obs)
            run.attempt(cid, SIGNAL_TYPE, outcome="covered", records_written=1,
                        source_url_attempted=cdx_url, candidates_evaluated=len(counts),
                        candidates_discarded=len(counts) - len(singles))
            entry["outcome"] = f"{len(singles)} single-capture removal(s), low grade"
            print(f"  [lg] {cid} {name[:34]:34s} {len(singles)} single-capture removal(s) "
                  f"written at low grade")
        elif not gone:
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        source_url_attempted=cdx_url, candidates_evaluated=len(counts),
                        candidates_discarded=0)
            entry["outcome"] = "absent_confirmed"
            print(f"  [00] {cid} {name[:34]:34s} {len(counts)} relevant path(s), "
                  f"none removed")
        else:
            obs = build_observation(c, gone, split["live"], split["site_last_seen"],
                                    stamp, counts)
            proposed.append(obs)
            run.attempt(cid, SIGNAL_TYPE, outcome="covered", records_written=1,
                        source_url_attempted=cdx_url, candidates_evaluated=len(counts),
                        candidates_discarded=len(counts) - len(gone),
                        **({"failure_stage": "governance",
                            "failure_category": "suppressed_by_cap",
                            "fix_class": "code_change",
                            "failure_detail": (f"CDX returned the full {wayback.CDX_LIMIT} "
                                               f"-row limit; older captures were not read, "
                                               f"so absence of a path from this set is not "
                                               f"proof it was never archived")}
                           if cdx_truncated else {}))
            entry["outcome"] = f"{len(gone)} removed"
            print(f"  [ok] {cid} {name[:34]:34s} {len(gone)} removed page(s) "
                  f"of {len(counts)} relevant")

        log["companies"].append(entry)

    report = db.sync_observations(proposed)
    run.observations_written = report.written
    summary = run.close()

    print()
    print(f"  {summary['companies_processed']} companies · {len(proposed)} observations "
          f"· {cache.fetch_count} HTTP requests")
    print(f"  coverage {summary['coverage_rate']:.0%} of {summary['attempts_total']} "
          f"attempts ({summary['attempts_covered']} covered, "
          f"{summary['attempts_absent_confirmed']} absent_confirmed, "
          f"{summary['attempts_not_covered']} not_covered)")
    print(f"  dedupe: {report.summary()}")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")

    log["summary"] = summary
    log_path = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    if args.commit:
        db.save()
        print(f"  committed ({report.written} rows written, {summary['run_id']})")
    else:
        print("  DRY RUN — nothing written. Re-run with --commit to write.")
    print(f"  run log: {log_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
