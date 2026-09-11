#!/usr/bin/env python3
"""
H-PRODUCTQUALITY-01 -- federal recall and complaint records (family 11, IC4).

WHY IT IS WORTH BUILDING
------------------------
IC4, involuntary disclosure: published over the subject's likely preference. That is the
instrument class the evidence base is shortest on, and the only remaining route to
`legacy_constraint` now that family 4 is closed to compliant collection. A company does not
announce its own obsolescence, but a recall notice compels it to describe the control that
failed.

WHAT IT ADMITS
--------------
A recall whose OWN REASON TEXT names a process or systems cause. Not every recall is
evidence about modernization -- most concern a contaminated batch or a broken part -- and
admitting those would fill family 11 with rows carrying a company name and no claim.

A recall found but not admitted is not silence: the attempt records that recalls exist and
that none cited a systems cause, which is a different statement from "this company has no
recalls" and must stay distinguishable from it (convention 6).

THE IDENTITY GUARD
------------------
`recalling_firm:"Prime"` in openFDA matches every firm with that word in its name. This is
the Prime Inc. failure in a new database, and the same test applies: a coined token stands
alone, a dictionary word needs the full company phrase (convention 31). Every returned firm
name is checked against `article.is_about_company` before its recall becomes a row, and
every rejection is logged.

Output is QUARANTINED. Row counts only, no coverage number.

    python -m harnesses.h_productquality_01.harness            # dry run
    python -m harnesses.h_productquality_01.harness --commit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache, slug                                # noqa: E402
from core.db import MarketIntelDB, Observation, today                  # noqa: E402
from core import aliases, topics
from core.resolution import query_variants                                               # noqa: E402
from harnesses.h_firstparty_01 import article                          # noqa: E402
from harnesses.h_productquality_01 import sources                      # noqa: E402

HARNESS_ID = "H-PRODUCTQUALITY-01"
HARNESS_NAME = "Federal Recall & Complaint Extractor"
VERSION = "v1.4"
SIGNAL_TYPE = "product_quality_event"
EVIDENCE_FAMILY = "11_product_quality_customer_friction"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# Which companies these databases actually cover. Hand-seeded, visible and checkable, for
# the same reason H-TRADEPRESS-01's outlet map is: `Companies.industry_primary` is blank
# for all 100 Anvil rows, and inferring an industry from a name inside the harness is the
# silent guess convention 13 forbids.
#
# Everything NOT listed here is `not_covered`, with the reason -- a general contractor has
# no FDA registration and a freight carrier has no CPSC recall. Running them anyway would
# produce a wall of `absent_confirmed` rows asserting a clean record where the truth is
# that the instrument does not point at them.
# A company can sit in more than one population, and three of them did while being queried
# against one instrument. Values are lists for that reason -- see the supplements note
# below. Order is preserved and duplicate instruments are collapsed downstream.
POPULATION = {
    "C0001": ["medical_device"],   # Midmark
    # OPEN QUESTION, NOT A FIX -- logged for Harness Advisor, deliberately not decided here.
    # Duke makes commercial foodservice equipment, which is not a consumer product, so CPSC
    # may be the WRONG instrument rather than an incomplete one. If it is wrong, Duke's zero
    # is meaningless either way and the honest record is not_covered. Left as `consumer`
    # pending that judgment, because changing it is a claim about what CPSC covers.
    "C0003": ["consumer"],         # Duke Manufacturing (foodservice equipment)
    "A030": ["medical_device"],    # Merit Medical Systems
    "A019": ["medical_device"],    # Co-Diagnostics
    # A025 IPS-Integrated Project Services REMOVED from the population 2026-09-01.
    # It designs and builds pharmaceutical facilities; it does not manufacture devices and
    # holds no FDA device registration. Querying it produced an `absent_confirmed` that
    # read as "this device maker has a clean record", which is a false statement about a
    # company that makes no devices. Its zero is now an honest `not_covered` (convention 6:
    # a confirmed absence requires the source to be complete FOR THE SIGNAL, and a device
    # database is not complete for a firm outside it).
    "A005": ["food"],              # Nicholas and Company
    "A029": ["food"],              # SpartanNash
    "A050": ["food"],              # Leprino Foods
    "A041": ["food"],              # J.R. Simplot
    "A017": ["food"],              # Admiral Beverage
    # THE REAL MISS, corrected 2026-09-01. These three sell ingestible dietary supplements
    # and were queried against CPSC only. openFDA's food enforcement endpoint covers
    # dietary supplement recalls, so a live instrument existed and never ran -- their zeros
    # were absence from the wrong database. CPSC is retained because they also sell
    # non-ingestible consumer goods.
    "A010": ["consumer", "food"],  # 4LIFE (supplements)
    "A018": ["consumer"],          # Scentsy
    "A057": ["consumer", "food"],  # Melaleuca (supplements)
    "A059": ["consumer", "food"],  # doTERRA International (supplements)
    "A007": ["consumer"],          # National Product Sales
    "C0002": ["medical_device"],   # Mack Group (Mack Molding, contract medical device mfg)
}


def firm_starts_with_company(firm: str, company_name: str,
                             variants: list[str] | None = None) -> bool:
    """LEGAL's L9 rule: after dropping legal forms, the company's tokens must be a PREFIX
    of the firm's tokens. 'Certified Prime Inc' contains PRIME and is not Prime Inc.

    Tested against the canonical name AND the human-seeded aliases (core/aliases), exactly
    as H-LEGAL-01 does: Mack Group files as 'Mack Molding Company', and the first replay
    of this rule rejected all three of its recalls for not starting with GROUP."""
    norm = lambda t: [x for x in re.split(r"[^a-z0-9]+", str(t).lower()) if x]
    drop = {"inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "corp",
            "corporation", "co", "company", "plc", "the"}
    ftok = [t for t in norm(firm) if t not in drop]
    for nm in [company_name, *(variants or [])]:
        ctok = [t for t in norm(nm) if t not in drop]
        if ctok and ftok[:len(ctok)] == ctok:
            return True
    return False


def build_observation(company: dict, theme_key: str, events: list[dict], cue_by_id: dict,
                      retrieval: str, instrument: str, low_grade: str = "") -> Observation:
    """`low_grade`: the process-cause cue and the failure predicate sit in different
    sentences (2026-09-03 policy: C / weak_clue / 0.35 / state unknown, marked, not refused)."""
    theme = topics.THEMES_BY_KEY[theme_key]
    dates = sorted({e["date"][:10] for e in events if e.get("date")})
    # Repetition IS the evidence for `repeated_pattern` (convention 19): the surviving row
    # carries the instance count rather than the instances being discarded.
    if len(events) >= 3:
        strength = "repeated_pattern"
    elif len(events) == 2:
        strength = "repeated_pattern"
    else:
        strength = "weak_clue"

    text = (
        f"{company['canonical_name']} is named in {len(events)} federal "
        f"{'recall' if 'recall' in instrument else 'adverse-event'} record(s) whose stated "
        f"cause is a process or systems failure bearing on {theme.label}"
        + (f", between {dates[0]} and {dates[-1]}" if dates else "")
        + ". The cause is quoted from the company's own filed reason text, published under "
        "regulatory compulsion. This is evidence of a control that did not work, not a "
        "judgement about the company's overall quality; recalls found whose cause was not "
        "a systems cause are recorded in this run's Attempts rows, not here."
    )
    parts = []
    for e in events[:3]:
        cue = cue_by_id.get(e["identifier"], "")
        parts.append(f'[{e.get("date", "")[:10]} {e["identifier"]}] "{e["reason"][:300]}"'
                     + (f" [cue: {cue}]" if cue else ""))
    excerpt = " | ".join(parts)
    if low_grade:
        excerpt = topics.low_grade_excerpt(low_grade, excerpt)

    return Observation(
        company_id=company["company_id"],
        evidence_family=EVIDENCE_FAMILY,
        evidence_role="buyer_acts",
        topic=theme_key,
        # A recall citing a process or systems cause is the company stating that a control
        # did not hold. That is `legacy_constraint` -- the value this harness exists to
        # reach, and the only IC4 route to it left in the portfolio.
        organizational_state="unknown" if low_grade else "legacy_constraint",
        signal_strength="weak_clue" if low_grade else strength,
        observation_text=text,
        evidence_excerpt=excerpt[:2000],
        source_url=("https://api.fda.gov/" if instrument.startswith("openfda")
                    else "https://www.saferproducts.gov/" if instrument == "cpsc_recall"
                    else "https://api.nhtsa.gov/") + f"#{instrument}:{company['company_id']}",
        publication_date=dates[-1] if dates else "",
        retrieval_date=retrieval,
        # B, not A. The record is authoritative and the reason text is the firm's own, but
        # the mapping from a free-text cause to a modernization theme is this harness's
        # inference, not the regulator's. A belongs to a claim the source itself makes.
        source_grade=topics.LOW_GRADE if low_grade else "B",
        harness_id=HARNESS_ID,
        harness_version=VERSION,
        confidence_0_1=0.35 if low_grade else (0.7 if len(events) >= 2 else 0.6),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="H-PRODUCTQUALITY-01 -- federal recalls")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--companies")
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = [c for c in db.companies()
                 if c.get("qualification_status") != "provider_benchmark"]
    if args.companies:
        want = {c.strip() for c in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"] in want]

    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=0.4)

    scope = [(c["company_id"], SIGNAL_TYPE) for c in companies]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY}, commit=args.commit)
    run.publication_status = "quarantined"

    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "companies": [], "identity_rejections": []}

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        kinds = POPULATION.get(cid)
        entry = {"company_id": cid, "name": name, "population": kinds, "events": 0,
                 "matched": 0, "process_cause": 0, "instruments": []}

        if not kinds:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage="discovery", failure_category="source_not_found",
                        fix_class="source_limitation",
                        failure_detail=(
                            "outside this instrument's population: federal recall and "
                            "adverse-event databases cover firms that make physical "
                            "products, and this company is not one. Recorded not_covered "
                            "rather than absent_confirmed -- a clean FDA record for a "
                            "general contractor is not evidence of anything (convention 6)."))
            log["companies"].append(entry)
            continue

        total_events = matched_events = 0
        by_theme: dict[str, list] = {}
        low_by_theme: dict[str, list] = {}   # 2026-09-03: weak-tier causes, written at low grade
        low_reason: dict[str, str] = {}
        cue_by_id: dict[str, str] = {}
        source_error = None
        instrument_used = ""

        # Flattened across every population this company belongs to, de-duplicated while
        # preserving order. A company in two populations is queried against both.
        instruments = list(dict.fromkeys(
            i for k in kinds for i in sources.INSTRUMENTS[k]))
        # EVERY NAME VARIANT, NOT JUST THE CANONICAL ONE (convention 6a).
        # CPSC's RecallTitle matches the words in a recall headline, and a headline never
        # carries a legal form: `RecallTitle=Scentsy, Inc.` returns nothing while
        # `RecallTitle=Scentsy` returns the company's one real recall. v1.1 therefore wrote
        # `absent_confirmed` for Scentsy and doTERRA against CPSC when both have recalls --
        # false absence evidence, and the OSHA Mack Molding failure in a third database.
        #
        # `query_variants` is the same conservative ladder used elsewhere: the full name,
        # the name minus trailing legal-form suffixes, and human-seeded aliases only. It
        # never guesses an abbreviation (convention 13). Anything a looser variant drags in
        # is caught by the identity guard below, which scores the firm string the source
        # actually returned.
        variants = query_variants(name, aliases.variants_for(cid))
        entry["name_variants"] = variants

        for instrument in instruments:
            # A LADDER, NOT A UNION. `query_variants` returns names most specific first,
            # and this takes the first variant that ANSWERS, then stops.
            #
            # Unioning the variants instead was tried and reverted the same session, for a
            # reason worth keeping: openFDA returns one row per affected product, and
            # `normalise` keeps only a few fields, so genuinely distinct records collapse
            # into equal dicts. Any de-duplication across a union therefore destroyed real
            # instances -- Merit Medical's 75 records fell to 41 and its already-audited
            # systems-cause count moved from 3 to 2. That is convention 19's failure
            # exactly: a redundancy filter deleting the count it was measuring.
            #
            # First-answer-wins has neither problem. A more specific name that works is
            # never second-guessed, and a broader variant is consulted only where the
            # specific one returned nothing at all -- which is precisely the false-absence
            # case this exists to fix, and nowhere else.
            events, tried = [], []
            for variant in variants:
                url = sources.QUERY[instrument](variant)
                # The cache key carries a fingerprint of the URL, not just the instrument
                # and company. Without it, changing a query re-reads the OLD response from
                # today's partition: fixing the CPSC parameter had no effect on the second
                # run because the harness replayed the error records the broken parameter
                # had produced. A cache key that does not change when the request changes
                # is not a cache, it is a stale answer with a confident name.
                key = (f"{instrument}_{slug(cid)}_"
                       f"{hashlib.sha1(url.encode()).hexdigest()[:8]}")
                try:
                    raw, _cached = cache.get(key, ".json",
                                             lambda u=url: json.dumps(sources.fetch_json(u)))
                    payload = json.loads(raw)
                    # normalise() can raise too -- CPSC's error-record check lives there,
                    # because the failure is only visible once the payload is read.
                    got = sources.normalise(instrument, payload)
                except sources.SourceError as e:
                    source_error = e
                    tried.append({"variant": variant, "error": str(e)[:160]})
                    continue
                except RuntimeError as e:                # offline, nothing archived
                    source_error = sources.SourceError(str(e))
                    tried.append({"variant": variant, "error": str(e)[:160]})
                    continue
                tried.append({"variant": variant, "results": len(got)})
                if got:
                    events = got
                    break
            entry.setdefault("variant_queries", []).append(
                {"instrument": instrument, "tried": tried,
                 "answered_on": next((t["variant"] for t in tried if t.get("results")),
                                     None)})
            if not events and tried and all("error" in t for t in tried):
                entry["instruments"].append({"instrument": instrument,
                                             "error": tried[-1].get("error", "")})
                continue

            total_events += len(events)
            kept = 0
            for e in events:
                # THE IDENTITY GUARD. `recalling_firm:"Prime"` matches every firm whose
                # name contains that word; this is the Prime Inc. failure in a new
                # database, and the same rule applies.
                ok, why = article.is_about_company(e["firm"], name, head_chars=400)
                if ok and not firm_starts_with_company(e["firm"], name, variants):
                    # Session 10 item 6 (P14): containment is necessary, not sufficient --
                    # the same prefix rule H-LEGAL-01 applies to a docket party (L9).
                    ok, why = False, (f"firm {e['firm']!r} contains the company name but "
                                      f"does not START with it")
                if not ok:
                    log["identity_rejections"].append(
                        {"company_id": cid, "firm_returned": e["firm"],
                         "identifier": e["identifier"], "why": why[:180]})
                    continue
                kept += 1
                cause = sources.process_cause_tiered(e["reason"])
                if not cause:
                    continue
                theme_key, cue, tier = cause
                if tier != "strong":
                    low_by_theme.setdefault(theme_key, []).append(e)
                    low_reason[theme_key] = ("bare symptom phrase, no named system or cause"
                                             if tier == "weak_symptom" else
                                             "process-cause cue and failure predicate in "
                                             "different sentences")
                else:
                    by_theme.setdefault(theme_key, []).append(e)
                cue_by_id[e["identifier"]] = cue
                instrument_used = instrument
            matched_events += kept
            entry["instruments"].append({"instrument": instrument, "events": len(events),
                                         "matched_to_company": kept})

        entry["events"], entry["matched"] = total_events, matched_events
        entry["process_cause"] = sum(len(v) for v in by_theme.values())
        entry["process_cause_low_grade"] = sum(len(v) for v in low_by_theme.values())
        for k in list(low_by_theme):
            if k in by_theme:
                low_by_theme.pop(k)      # a strong record carries the theme already

        if by_theme or low_by_theme:
            obs = [build_observation(company, k, v, cue_by_id, stamp, instrument_used)
                   for k, v in sorted(by_theme.items())]
            obs += [build_observation(company, k, v, cue_by_id, stamp, instrument_used,
                                      low_grade=low_reason.get(k, "weak-tier cause"))
                    for k, v in sorted(low_by_theme.items())]
            proposed.extend(obs)
            run.attempt(cid, SIGNAL_TYPE, outcome="covered", records_written=len(obs),
                        output_sheet="Observations", candidates_evaluated=total_events,
                        candidates_discarded=total_events - entry["process_cause"])
            print(f"  [{len(obs):02d}] {cid} {name}: {entry['process_cause']} of "
                  f"{matched_events} matched record(s) cite a systems cause")
        elif source_error is not None and total_events == 0:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage=source_error.failure_stage,
                        failure_category=source_error.failure_category,
                        fix_class=source_error.fix_class,
                        failure_detail=str(source_error)[:400])
            print(f"  [!!] {cid} {name}: {source_error}")
        elif matched_events:
            # THE DISTINCTION THAT MATTERS. Recalls exist for this company and none of
            # them cited a systems cause. That is not the same claim as "no recalls", and
            # collapsing the two would let a company with fourteen contamination recalls
            # read identically to one with a spotless record.
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        candidates_evaluated=total_events,
                        candidates_discarded=total_events,
                        failure_detail=(
                            f"{matched_events} federal record(s) matched this company "
                            f"across {'/'.join(instruments)}; none cited a "
                            f"process or systems cause. Absence of a SYSTEMS-CAUSE recall, "
                            f"not absence of recalls."))
            print(f"  [00] {cid} {name}: {matched_events} record(s), no systems cause")
        else:
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        candidates_evaluated=total_events, candidates_discarded=total_events,
                        failure_detail=(
                            f"queried {'/'.join(instruments)}; "
                            f"{total_events} raw result(s), none resolving to this company "
                            f"under the identity test. The databases are authoritative and "
                            f"complete for the firms they cover, so this is a confirmed "
                            f"absence."))
            print(f"  [00] {cid} {name}: no matching federal record")
        log["companies"].append(entry)

    report = None
    if args.commit:
        # v1.0's rows rest on an admission test that has since been shown wrong, so they
        # are removed rather than reconciled. Human-reviewed rows are never touched
        # (keep_reviewed defaults True); nothing here has been reviewed.
        removed = db.delete_observations(HARNESS_ID, keep_reviewed=True)
        if removed:
            print(f"  removed {removed} row(s) from superseded version(s) before writing")
        report = db.sync_observations(proposed)
        run.observations_written = report.written
    run.material_revision_notes = (
        "v1.1 -- MATERIAL: a process-cause cue now has to share a SENTENCE with a failure "
        "predicate. v1.0 scored a MAUDE narrative in which Midmark's ECG software "
        "correctly detected a myocardial infarction as a systems failure, on the bare "
        "token 'SOFTWARE', and wrote a legacy_constraint row asserting the opposite of "
        "what the record says. Also: MAUDE/openFDA YYYYMMDD dates are normalised to ISO "
        "(v1.0 wrote 'between 20201027 and 20201027' into observation text), and the "
        "response-cache key now includes a fingerprint of the request URL, because "
        "changing a query otherwise replays the previous query's answer from the same "
        "day's partition. v1.0 first build, IC4 instrument. QUARANTINED pending audit.")
    run.reprocessing_required = (
        "Yes -- v1.0's admission test was wrong, so its rows are not valid evidence. The "
        "single v1.0 row was deleted by this run rather than left to be reconciled: "
        "sync_observations does not remove a row a fixed harness has stopped proposing, "
        "so a defect that removes rows needs an explicit deletion or the bad row survives "
        "the fix silently.")
    summary = run.close()

    in_pop = sum(1 for c in companies if c["company_id"] in POPULATION)
    print()
    print(f"  {len(companies)} companies scoped, {in_pop} inside this instrument's "
          f"population - {len(proposed)} observations proposed")
    print(f"  identity rejections: {len(log['identity_rejections'])}")
    if report:
        print(f"  dedupe: {report.summary()}")
    print("  PUBLICATION STATUS: quarantined -- row counts only, no coverage number")

    log["summary"] = {"observations": len(proposed), "in_population": in_pop,
                      "run": summary}
    out = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
    out.write_text(json.dumps(log, indent=2), encoding="utf-8")
    if args.commit:
        db.save()
        print(f"  committed to {db.path.name} ({run.run_id})")
    else:
        print("  DRY RUN -- nothing written. Re-run with --commit to write.")
    print(f"  run log: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
