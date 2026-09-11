#!/usr/bin/env python3
"""
H-SAFETY-ENV-01 — OSHA + EPA ECHO Regulatory Record Extractor.

WHY THIS HARNESS, AND WHY NOW
-----------------------------
Two reasons, both from the project's own record.

First, coverage. `CLAUDE.md`'s next-task list ends with "consider OSHA next for the
manufacturing side — FMCSA barely covers manufacturers, so the three manufacturing pilots
currently have almost no evidence." That was accurate: Mack Group had 2 observations and
Duke Manufacturing 3, and Duke was deliberately chosen as the sparse-evidence test case.
Both have real OSHA inspection history. This is the harness that finds it.

Second, fit. `docs/signal_taxonomy.md` 9a/9b calls OSHA + EPA ECHO "the single cleanest,
richest, ownership-agnostic pair in the entire taxonomy". Ownership-agnostic matters more
here than anywhere else — the project's whole premise is that its target companies are
mid-size and mostly private, and regulators do not care whether a company is listed.

WHAT IT CLAIMS, AND WHAT IT REFUSES TO CLAIM
--------------------------------------------
A regulatory record is evidence about how a company runs its physical operations. It is
NOT direct evidence of modernization pressure, and the observations are written to keep
that distinction visible rather than to quietly upgrade a violation into a technology
narrative.

The defensible reading, and the one used here:

  * A **complaint- or referral-triggered** inspection is a signal that someone inside or
    adjacent to the operation escalated. That is organizational exhaust, and it is
    materially different from a `Planned` inspection, which reflects OSHA's targeting
    programme and says more about the industry's SIC code than about the company.
  * **Repeat inspections with violations** map to `legacy_constraint`: an operation with a
    recurring citation history is carrying constraints it has not resolved.
  * **A clean record maps to `unknown`, never to `target_state`.** Absence of violations is
    not evidence of modernity. Reading it as a positive signal would manufacture exactly
    the kind of confidence the Infor/"Information Systems" bug produced, on a much larger
    surface.

`absent_confirmed` is used precisely: OSHA and ECHO are authoritative and complete for
their own record, so a company with no hits genuinely has no federal inspection history in
the window. That is real negative evidence, and it counts as coverage.

    python -m harnesses.h_safety_env_01.harness              # dry run
    python -m harnesses.h_safety_env_01.harness --commit
    python -m harnesses.h_safety_env_01.harness --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import aliases, resolution  # noqa: E402
from core.cache import DatedCache  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from harnesses.h_safety_env_01.source import (  # noqa: E402
    OSHA_MAX_INSPECTIONS as OSHA_MAX, SafetyEnvClient)

HARNESS_ID = "H-SAFETY-ENV-01"
HARNESS_NAME = "OSHA + EPA ECHO Regulatory Record Extractor"
VERSION = "v1.3"
EVIDENCE_FAMILY = "9_industrial_safety_environmental"
SIGNALS = {"osha_inspection": EVIDENCE_FAMILY, "epa_echo_compliance": EVIDENCE_FAMILY}

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# Evidence window. The project's staleness standard is five years (core/windows.py, decided
# 2026-09-03); the 36-month figure below is a RECENCY SUBSET reported inside the text, not
# an admission gate, and is unchanged. A safety record is
# a pattern rather than an event, and three years is too short to distinguish "one bad
# quarter" from "a persistent condition". Ten years is collected; the 36-month subset is
# reported separately inside the observation so the recency-weighted reading stays
# available without discarding the pattern.
WINDOW_START_YEAR = 2016
RECENT_MONTHS = 36

# An inspection someone asked for, versus one OSHA scheduled.
ESCALATION_TYPES = {"complaint", "referral", "accident", "fatality"}


def search_all_variants(search_fn, variants):
    """Try every name variant; return (records, url, variant_used, tried).

    `absent_confirmed` may only be asserted once EVERY variant comes back empty. Asserting
    it after one failed lookup is the worst error this harness can make: it writes false
    negative evidence into the base, and negative evidence is exactly what the outcome
    value exists to carry weight for.

    This was not hypothetical. The first run of this harness reported Mack Group and Duke
    Manufacturing as having no OSHA record. Both have one -- Mack files as "Mack Molding",
    and "Duke Manufacturing Co." returns nothing from OSHA's search box where "Duke
    Manufacturing" returns three inspections. Six real inspections would have been recorded
    as confirmed absence.
    """
    tried = []
    url = ""
    for name in variants:
        result = search_fn(name)
        records, url = result[0], result[1]
        extra = result[2] if len(result) > 2 else False
        tried.append({"variant": name, "hits": len(records), "truncated": extra})
        if records:
            return records, url, name, tried, extra
    return [], url, None, tried, False


def months_before(iso_or_us: str, ref: date) -> int | None:
    """Age in months of an OSHA MM/DD/YYYY or ECHO MM/DD/YYYY date, against `ref`.

    Computed against the run's own retrieval date rather than the wall clock, per the
    locked convention: anything stated inside an observation must come from the source
    snapshot's own date or the row drifts against its own stored copy.
    """
    s = (iso_or_us or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            d = __import__("datetime").datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        return (ref.year - d.year) * 12 + (ref.month - d.month)
    return None


# ------------------------------------------------------------------- observation builders

def osha_observation(company, inspections, url, retrieval, truncated=False) -> Observation:
    ref = date.fromisoformat(retrieval)
    ages = [months_before(i.date_opened, ref) for i in inspections]
    recent = [i for i, a in zip(inspections, ages) if a is not None and a <= RECENT_MONTHS]
    types = Counter(i.insp_type for i in inspections)
    escalated = [i for i in inspections if i.insp_type.lower() in ESCALATION_TYPES]
    unknown_viol = sum(1 for i in inspections if i.violations is None)
    total_viol = sum(i.violations or 0 for i in inspections)
    newest = min((a for a in ages if a is not None), default=None)

    # State, then interpret — and only interpret as far as the record supports.
    if total_viol and len(inspections) > 1:
        org_state, strength = "legacy_constraint", "repeated_pattern"
        conf = 0.7
    elif total_viol:
        org_state, strength = "legacy_constraint", "weak_clue"
        conf = 0.55
    else:
        # Inspected but never cited. Says the operation was looked at, not that it is
        # modern. `unknown` is the honest value.
        org_state, strength = "unknown", "weak_clue"
        conf = 0.5

    esc_txt = (f"{len(escalated)} were complaint-, referral- or accident-triggered rather "
               f"than planned, indicating escalation from outside OSHA's targeting "
               f"programme" if escalated else
               "all were planned inspections under OSHA's targeting programme, which "
               "reflects the industry's risk profile more than this company's")

    text = (
        f"OSHA's establishment record shows {len(inspections)} inspection(s) since "
        f"{WINDOW_START_YEAR} ({len(recent)} within the last {RECENT_MONTHS} months), "
        f"carrying {total_viol} violation item(s) in total. {esc_txt}. "
        f"Inspection types: {', '.join(f'{v} {k}' for k, v in types.most_common())}. "
        f"A regulatory record evidences how the physical operation is run; it is not by "
        f"itself evidence of modernization pressure."
    )
    if newest is not None:
        text += f" Most recent inspection opened {newest} month(s) before retrieval."
    if unknown_viol:
        text += (f" {unknown_viol} inspection(s) carried no parseable violation count and "
                 f"are excluded from the violation total (S20).")
    if truncated:
        text += (" COUNT IS A FLOOR, NOT A TOTAL: OSHA returned a full page of results, "
                 "publishes no total, and its p_start/p_finish parameters do not advance "
                 "the window, so the true inspection count is at least this number and may "
                 "be materially higher.")

    excerpt = "; ".join(
        f"{i.date_opened} {i.insp_type}/{i.scope} activity {i.activity_nr}"
        f" ({i.violations} violation(s))" for i in inspections[:6])
    if len(inspections) > 6:
        excerpt += f" (+{len(inspections) - 6} more)"

    return Observation(
        company_id=company["company_id"], evidence_family=EVIDENCE_FAMILY,
        evidence_role="buyer_acts", topic="safety_inspection_history",
        organizational_state=org_state, signal_strength=strength,
        observation_text=text, evidence_excerpt=excerpt, source_url=url,
        publication_date=inspections[0].date_opened if inspections else "",
        retrieval_date=retrieval, source_grade="A",
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=conf,
    )


def echo_observation(company, facilities, url, retrieval) -> Observation:
    violating = [f for f in facilities
                 if f.compliance_status and "no violation" not in f.compliance_status.lower()
                 and f.compliance_status.lower() != "unknown"]
    snc = [f for f in facilities if f.snc_flag == "Y"]
    total_insp = sum(f.inspection_count for f in facilities)
    states = sorted({f.state for f in facilities if f.state})

    if snc or len(violating) > 1:
        org_state, strength, conf = "legacy_constraint", "repeated_pattern", 0.7
    elif violating:
        org_state, strength, conf = "legacy_constraint", "weak_clue", 0.55
    else:
        org_state, strength, conf = "unknown", "weak_clue", 0.5

    text = (
        f"EPA ECHO lists {len(facilities)} regulated facility/facilities across "
        f"{len(states)} state(s) ({', '.join(states[:6])}), with {total_insp} recorded "
        f"inspection(s). {len(violating)} facility/facilities carry a current "
        f"non-compliance status"
        + (f" and {len(snc)} is/are flagged a Significant Non-Complier" if snc else "")
        + ". Multi-site regulated footprint is a proxy for operating complexity; "
          "compliance status evidences how that footprint is managed."
    )
    excerpt = "; ".join(
        f"{f.name} ({f.city}, {f.state}) — {f.compliance_status}, "
        f"{f.inspection_count} inspection(s)" for f in facilities[:6])
    if len(facilities) > 6:
        excerpt += f" (+{len(facilities) - 6} more)"

    return Observation(
        company_id=company["company_id"], evidence_family=EVIDENCE_FAMILY,
        evidence_role="buyer_acts", topic="environmental_compliance_profile",
        organizational_state=org_state, signal_strength=strength,
        observation_text=text, evidence_excerpt=excerpt, source_url=url,
        publication_date="", retrieval_date=retrieval, source_grade="A",
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=conf,
    )


# -------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="H-SAFETY-ENV-01 — OSHA + EPA ECHO")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--companies", help="comma-separated company_ids to limit the run")
    ap.add_argument("--limit", type=int, help="process at most N companies")
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
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=0.5)
    client = SafetyEnvClient(cache)

    scope = [(c["company_id"], s) for c in companies for s in SIGNALS]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families=SIGNALS, commit=args.commit)

    alias_registry = aliases.load()
    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "companies": []}

    for c in companies:
        cid, name = c["company_id"], c["canonical_name"]
        state = resolution.state_code(c.get("hq_state"))
        variants = resolution.query_variants(name, aliases.variants_for(cid, alias_registry))
        entry = {"company_id": cid, "name": name, "state": state, "resolution": {},
                 "variants": variants}

        # ---------------------------------------------------------------- OSHA
        if not state:
            # No state means no OSHA query -- its establishment index requires one.
            # Recorded rather than skipped: a missing input is a coverage gap with a
            # nameable cause, and 100 of the 108 companies came from a CRM export whose
            # location fields were left blank pending enrichment. This is the single
            # highest-leverage enrichment task the portfolio has, since it gates every
            # state-keyed source, not just this one.
            run.attempt(cid, "osha_inspection", outcome="not_covered",
                        failure_stage="discovery", failure_category="source_not_found",
                        fix_class="code_change",
                        failure_detail="Companies.hq_state is blank; the OSHA "
                                       "establishment index requires a state to query")
            entry["osha"] = "no_state"
        else:
            try:
                inspections, url, used, tried, truncated = search_all_variants(
                    lambda n: client.osha_search(n, state, str(WINDOW_START_YEAR),
                                                 str(date.fromisoformat(stamp).year)),
                    variants)
                entry["osha_variants_tried"] = tried
                entry["osha_variant_used"] = used
                entry["osha_rows_dropped"] = client.last_dropped_rows
                client.last_dropped_rows = 0
            except (requests.RequestException, RuntimeError) as e:
                run.attempt(cid, "osha_inspection", outcome="not_covered",
                            failure_stage="fetch", failure_category="source_unavailable",
                            fix_class="transient", failure_detail=f"{type(e).__name__}: {e}")
                entry["osha"] = f"error: {e}"
            else:
                res = resolution.resolve(
                    used or name, inspections, name_of=lambda i: i.establishment,
                    accept_multiple=True)
                entry["resolution"]["osha"] = res.as_log()
                if not inspections:
                    # Authoritative source, complete for its own record, genuinely empty.
                    run.attempt(cid, "osha_inspection", outcome="absent_confirmed",
                                source_url_attempted=url, candidates_evaluated=0)
                    entry["osha"] = "absent_confirmed"
                elif not res.resolved:
                    run.attempt(cid, "osha_inspection", outcome="not_covered",
                                failure_stage="entity_resolution",
                                failure_category=res.failure_category,
                                fix_class="code_change", failure_detail=res.note,
                                source_url_attempted=url,
                                candidates_evaluated=len(inspections),
                                candidates_discarded=len(inspections))
                    entry["osha"] = res.status
                else:
                    matched = [i for i in inspections
                               if resolution.score(used, i.establishment) >= resolution.DEFAULT_FLOOR]
                    obs = osha_observation(c, matched, url, stamp, truncated)
                    proposed.append(obs)
                    # A reached cap is a governance suppression, not a miss: the harness
                    # got to the source and a declared rule fired. Outcome stays `covered`
                    # and coverage_rate is unaffected (spec §11 Q5), but the truncation
                    # becomes a queryable row instead of a silence.
                    cap_fields = {
                        "failure_stage": "governance",
                        "failure_category": "suppressed_by_cap",
                        "fix_class": "code_change",
                        "failure_detail": ("OSHA returned a full page and exposes no "
                                           "working pagination or total count, so the "
                                           "inspection count is a floor rather than a "
                                           "total"),
                    } if truncated else {}
                    run.attempt(cid, "osha_inspection", outcome="covered",
                                records_written=1, source_url_attempted=url,
                                candidates_evaluated=len(inspections),
                                candidates_discarded=len(inspections) - len(matched),
                                **cap_fields)
                    entry["osha"] = (f"{len(matched)} inspection(s)"
                                     + (" [CAPPED]" if truncated else ""))

        # ---------------------------------------------------------------- EPA ECHO
        # No state gate here, unlike OSHA: ECHO searches nationally by name, so a blank
        # hq_state costs precision rather than coverage.
        if True:
            try:
                facilities, url, used_e, tried_e, echo_truncated = search_all_variants(
                    lambda n: client.echo_search(n, state), variants)
                entry["echo_variants_tried"] = tried_e
                entry["echo_variant_used"] = used_e
            except (requests.RequestException, RuntimeError, ValueError) as e:
                run.attempt(cid, "epa_echo_compliance", outcome="not_covered",
                            failure_stage="fetch", failure_category="source_unavailable",
                            fix_class="transient", failure_detail=f"{type(e).__name__}: {e}")
                entry["echo"] = f"error: {e}"
            else:
                res = resolution.resolve(used_e or name, facilities,
                                         name_of=lambda f: f.name, accept_multiple=True)
                entry["resolution"]["echo"] = res.as_log()
                if not facilities:
                    run.attempt(cid, "epa_echo_compliance", outcome="absent_confirmed",
                                source_url_attempted=url, candidates_evaluated=0)
                    entry["echo"] = "absent_confirmed"
                elif not res.resolved:
                    run.attempt(cid, "epa_echo_compliance", outcome="not_covered",
                                failure_stage="entity_resolution",
                                failure_category=res.failure_category,
                                fix_class="code_change", failure_detail=res.note,
                                source_url_attempted=url,
                                candidates_evaluated=len(facilities),
                                candidates_discarded=len(facilities))
                    entry["echo"] = res.status
                else:
                    matched = [f for f in facilities
                               if resolution.score(used_e, f.name) >= resolution.DEFAULT_FLOOR]
                    obs = echo_observation(c, matched, url, stamp)
                    if echo_truncated:
                        obs.observation_text += (" FACILITY COUNT IS A FLOOR, NOT A TOTAL: "
                                                 "ECHO returned a full final page at the "
                                                 "declared cap.")
                    proposed.append(obs)
                    echo_cap = {
                        "failure_stage": "governance",
                        "failure_category": "suppressed_by_cap",
                        "fix_class": "code_change",
                        "failure_detail": ("ECHO returned a full final page at the declared "
                                           "cap, so the facility count is a floor"),
                    } if echo_truncated else {}
                    run.attempt(cid, "epa_echo_compliance", outcome="covered",
                                records_written=1, source_url_attempted=url,
                                candidates_evaluated=len(facilities),
                                candidates_discarded=len(facilities) - len(matched),
                                **echo_cap)
                    entry["echo"] = (f"{len(matched)} facility/facilities"
                                     + (" [CAPPED]" if echo_truncated else ""))

        log["companies"].append(entry)
        print(f"  {cid} {name[:32]:32s} osha={entry.get('osha','-'):24s} "
              f"echo={entry.get('echo','-')}")

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
