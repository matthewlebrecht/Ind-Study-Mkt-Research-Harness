#!/usr/bin/env python3
"""
Draw a stratified ROLE-classification review sheet for one evidence_role, across harnesses.

    python scripts/role_review_sheet.py --role buyer_articulates --target 55 --floor 5 \
        --census-harness H-TRADEPRESS-01

WHAT THIS REVIEWS, AND WHAT IT DOES NOT
--------------------------------------
`scripts/audit_sample.py` draws the audit gate's samples for ONE harness version and asks
whether each claim is supported (identity, extraction, strength). That is already done for
every released version. This script asks a different, cross-harness question: was the
`evidence_role` the right classification for the row? So it samples by role across the
portfolio, stratified by `harness_id` and then by the harness's own sub-kind (channel for
H-FIRSTPARTY-01, signal type for H-TRADEPRESS-01), and assigns no verdicts.

NOTHING IS TRUNCATED, AND THAT IS CHECKED RATHER THAN PROMISED
---------------------------------------------------------------
audit_sample.py cut Claim, Evidence and Reviewer notes at 900 characters with no marker,
which silently dropped two caveats from O00632 on the H-PROCUREMENT-01 v1.0 sheet. Here
every field is written whole, and after writing the sheet the script re-reads it and
refuses (exit 1) unless every sampled row's text, excerpt, URL and notes appear verbatim.

ALLOCATION
----------
Proportional to stratum size by largest remainder, with a per-harness floor (a harness
that would get fewer than `--floor` rows gets `min(floor, population)` and the rest of the
target is re-spread over the others). A `--census-harness` then takes every row of that
harness, ON TOP of the target, so the total can exceed it; the sheet says so. Within a
harness, sub-strata are allocated proportionally the same way. Seeded, so redrawable.

Writes harness_output/audits/ROLE_REVIEW_<role>_<date>.md and ..._allocation.json. Neither
carries a top-level harness_id, so core/audit.py::load_artifacts skips both.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import random
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harnesses.h_firstparty_01 import harness as firstparty  # noqa: E402

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"
OUT_DIR = ROOT / "harness_output" / "audits"
SEED = 20260915
LOW_GRADE_PREFIX = "[low-grade:"

PURPOSE = {
    "buyer_articulates": (
        "This sheet checks one thing: **was `evidence_role = buyer_articulates` the correct "
        "classification for the row?** That is, is this genuinely the buyer making a "
        "first-person statement (the company, or an executive speaking for it), or is it "
        "misclassified -- for example a `provider_market_responds` claim (a vendor, partner "
        "or provider speaking) that got miscoded, or a `buyer_acts` observation (something "
        "the company *did*) recorded as an articulation?\n\n"
        "It is **not** re-checking identity matching (right company, right speaker) or "
        "extraction quality (claim supported at the strength stated). Both were audited per "
        "harness version before release. Judge the role only."),
}


def sheet_rows(wb, name):
    it = wb[name].iter_rows(values_only=True)
    headers = list(next(it))
    return [dict(zip(headers, r)) for r in it if r and r[0] is not None]


def allocate(pops: dict, total: int) -> dict:
    """Largest-remainder proportional allocation of `total` over `pops` (ties by key)."""
    n = sum(pops.values())
    if n == 0 or total <= 0:
        return {k: 0 for k in pops}
    quotas = {k: v * total / n for k, v in pops.items()}
    alloc = {k: min(pops[k], math.floor(q)) for k, q in quotas.items()}
    order = sorted(pops, key=lambda k: (-(quotas[k] - math.floor(quotas[k])), k))
    i = 0
    while sum(alloc.values()) < min(total, n) and i < 10 * len(order):
        k = order[i % len(order)]
        if alloc[k] < pops[k]:
            alloc[k] += 1
        i += 1
    return alloc


def allocate_with_floor(pops: dict, total: int, floor: int) -> dict:
    floored: dict = {}
    while True:
        rest = {k: v for k, v in pops.items() if k not in floored}
        alloc = allocate(rest, total - sum(floored.values()))
        new = {k: min(floor, pops[k]) for k in rest if alloc[k] < min(floor, pops[k])}
        if not new:
            alloc.update(floored)
            return alloc
        floored.update(new)


def upper_bound_zero_found(pop: int, n: int, conf: float = 0.95) -> int:
    """Largest count K of misclassified rows in a stratum of `pop` still consistent (at
    one-sided `conf`) with finding none in a simple random draw of `n` -- hypergeometric,
    so it is exact for a finite stratum. A census (n == pop) returns 0."""
    if n >= pop:
        return 0
    k = 0
    while k < pop and math.comb(pop - (k + 1), n) / math.comb(pop, n) >= 1 - conf:
        k += 1
    return k


def sub_kind(row: dict, company_host: dict) -> str:
    hid = row["harness_id"]
    exc = str(row.get("evidence_excerpt") or "")
    if hid == "H-FIRSTPARTY-01":
        cls, _, _ = firstparty.classify_source(str(row.get("source_url") or ""),
                                               company_host.get(row["company_id"], ""))
        return f"channel: {cls or 'unclassified'}"
    if hid == "H-TRADEPRESS-01":
        if "[wire reprint]" in exc:
            return "signal type: wire reprint (routed to family 1)"
        if "[self]" in exc:
            return "signal type: ST-PRESSCHAR"
        if "quoted in reported trade coverage" in str(row.get("observation_text") or ""):
            return "signal type: ST-EXECQUOTE-REPORTED"
        return "signal type: UNRECOGNISED"
    return "single signal type"


def cell(v) -> str:
    return (str(v if v is not None else "").replace("|", "\\|")
            .replace("\r\n", "<br>").replace("\n", "<br>"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--role", default="buyer_articulates")
    ap.add_argument("--target", type=int, default=55)
    ap.add_argument("--floor", type=int, default=5)
    ap.add_argument("--census-harness", action="append", default=[])
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--date", default=_dt.date.today().isoformat())
    # Scoping filters. A second pass at one stratum must be drawn from the CURRENT base: rows
    # recorded invalid since the first draw would otherwise be re-judged for a role they no
    # longer support, and rows already judged would be judged twice.
    ap.add_argument("--sub-kind-contains", default="",
                    help="restrict the population to sub-strata whose label contains this")
    ap.add_argument("--exclude-invalid", action="store_true",
                    help="drop rows carrying a current Observation_Validity_History determination")
    ap.add_argument("--exclude-reviewed", action="store_true",
                    help="drop rows already carrying a verdict in Observation_Role_Reviews")
    ap.add_argument("--stem", default="", help="output filename stem")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.db, read_only=True, data_only=True)
    companies = {c["company_id"]: c for c in sheet_rows(wb, "Companies")}
    company_host = {cid: firstparty.host_of(str(c.get("website") or ""))
                    for cid, c in companies.items() if c.get("website")}
    population = sorted((o for o in sheet_rows(wb, "Observations")
                         if o.get("evidence_role") == args.role),
                        key=lambda o: o["observation_id"])
    if not population:
        print(f"no observations with evidence_role={args.role}")
        return 1

    for o in population:
        o["_sub"] = sub_kind(o, company_host)
        exc = str(o.get("evidence_excerpt") or "")
        o["_low"] = exc.startswith(LOW_GRADE_PREFIX)
        o["_c"] = str(o.get("source_grade")) == "C"
        if o["_low"] != o["_c"]:
            print(f"  note: {o['observation_id']} low-grade marker and grade C disagree")
    # --- scoping filters, applied once _sub is known; every one is printed on the sheet ---
    filters = []
    if args.sub_kind_contains:
        before = len(population)
        population = [o for o in population if args.sub_kind_contains.lower() in o["_sub"].lower()]
        filters.append(f"sub-stratum contains {args.sub_kind_contains!r}: {before} -> "
                       f"{len(population)} rows")
    if args.exclude_invalid:
        from core import validity as _v
        invalid = set(_v.invalid_observation_ids(wb))
        gone = [o["observation_id"] for o in population if o["observation_id"] in invalid]
        population = [o for o in population if o["observation_id"] not in invalid]
        filters.append(f"excluded {len(gone)} row(s) carrying a validity determination: "
                       + (", ".join(gone) if len(gone) <= 40 else f"{len(gone)} rows"))
    if args.exclude_reviewed:
        judged = {r["observation_id"] for r in sheet_rows(wb, "Observation_Role_Reviews")}
        gone = [o["observation_id"] for o in population if o["observation_id"] in judged]
        population = [o for o in population if o["observation_id"] not in judged]
        filters.append(f"excluded {len(gone)} row(s) already judged in an earlier run: "
                       + (", ".join(gone) if len(gone) <= 40 else f"{len(gone)} rows"))
    if not population:
        print("no rows left after the scope filters")
        return 1
    bad = [o["observation_id"] for o in population if "UNRECOGNISED" in o["_sub"]]
    if bad:
        print(f"refusing: unrecognised signal type on {bad}")
        return 1

    harness_pop: dict = {}
    for o in population:
        harness_pop[o["harness_id"]] = harness_pop.get(o["harness_id"], 0) + 1
    proportional = {h: n * args.target / len(population) for h, n in harness_pop.items()}
    h_alloc = allocate_with_floor(harness_pop, args.target, args.floor)
    floored = {h for h in harness_pop if h_alloc[h] > round(proportional[h]) and
               h_alloc[h] == min(args.floor, harness_pop[h])}
    after_floor = dict(h_alloc)
    for h in args.census_harness:
        if h in harness_pop:
            h_alloc[h] = harness_pop[h]

    rng = random.Random(args.seed)
    strata, sampled = [], []
    for h in sorted(harness_pop):
        rows_h = [o for o in population if o["harness_id"] == h]
        sub_pop: dict = {}
        for o in rows_h:
            sub_pop[o["_sub"]] = sub_pop.get(o["_sub"], 0) + 1
        s_alloc = allocate(sub_pop, h_alloc[h])
        for s in sorted(sub_pop):
            rows_s = [o for o in rows_h if o["_sub"] == s]
            draw = sorted(rng.sample(rows_s, s_alloc[s]), key=lambda o: o["observation_id"])
            sampled.extend(draw)
            strata.append({
                "harness_id": h, "sub_stratum": s,
                "population_n": len(rows_s), "sampled_n": len(draw),
                "coverage": round(len(draw) / len(rows_s), 4),
                "census": len(draw) == len(rows_s),
                "low_grade_population": sum(o["_low"] for o in rows_s),
                "low_grade_sampled": sum(o["_low"] for o in draw),
                "grade_c_population": sum(o["_c"] for o in rows_s),
                "grade_c_sampled": sum(o["_c"] for o in draw),
                "zero_found_95_upper_bound_rows": upper_bound_zero_found(len(rows_s), len(draw)),
                "row_ids": [o["observation_id"] for o in draw],
            })
    harness_summary = []
    for h in sorted(harness_pop):
        drawn = [o for o in sampled if o["harness_id"] == h]
        harness_summary.append({
            "harness_id": h, "population_n": harness_pop[h],
            "proportional_share": round(proportional[h], 2),
            "allocated_after_floor": after_floor[h],
            "floor_applied": h in floored,
            "census_override": h in args.census_harness,
            "sampled_n": len(drawn),
            "coverage": round(len(drawn) / harness_pop[h], 4),
            "low_grade_population": sum(o["_low"] for o in population if o["harness_id"] == h),
            "low_grade_sampled": sum(o["_low"] for o in drawn),
            "grade_c_population": sum(o["_c"] for o in population if o["harness_id"] == h),
            "grade_c_sampled": sum(o["_c"] for o in drawn),
            "zero_found_95_upper_bound_rows": upper_bound_zero_found(harness_pop[h], len(drawn)),
        })

    stem = args.stem or f"ROLE_REVIEW_{args.role}_{args.date}"
    md_path, json_path = OUT_DIR / f"{stem}.md", OUT_DIR / f"{stem}_allocation.json"

    L = [f"# Role-classification review: `{args.role}` ({args.date})", "",
         "## Purpose", "", PURPOSE.get(args.role, f"Was `evidence_role = {args.role}` "
                                       "the correct classification?"), "",
         "## Population and draw", "",
         f"**Population:** every observation with `evidence_role = {args.role}` at the time of "
         f"drawing: **{len(population)} rows** "
         f"({sum(1 for o in population if o.get('publication_state') == 'released')} released). "
         f"**Sampled: {len(sampled)}.** **Seed:** {args.seed} (deterministic, redrawable).", "",
         ("**Scope filters applied to the population:**\n\n" +
          ("\n".join("- " + f for f in filters)) + "\n") if filters else "", "",
         f"Target {args.target}, proportional to harness size by largest remainder, floor "
         f"{args.floor} rows per contributing harness."
         + (f" Census override (every row, on top of the target): "
            f"{', '.join(args.census_harness)}." if args.census_harness else ""), "",
         "Within a harness the draw is split proportionally by channel (H-FIRSTPARTY-01, from "
         "the harness's own `classify_source`) or by signal type (H-TRADEPRESS-01, from the "
         "row's markers). A single-type harness is one sub-stratum.", "",
         "**Coverage columns.** *Coverage* is sampled / population. *Upper bound if none "
         "found* is the largest number of misclassified rows the stratum could still hold, "
         "at one-sided 95%, if the draw finds zero (hypergeometric, exact for the finite "
         "stratum; 0 for a census).", "",
         "### By harness", "",
         "| harness | population | proportional share | after floor | sampled | coverage | "
         "grade C (pop / sampled) | low-grade marker (pop / sampled) | upper bound if none found |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in harness_summary:
        how = (" (census)" if s["census_override"] else
               " (floor)" if s["floor_applied"] else "")
        L.append(f"| {s['harness_id']} | {s['population_n']} | {s['proportional_share']} | "
                 f"{s['allocated_after_floor']} | **{s['sampled_n']}**{how} | "
                 f"{s['coverage']:.0%} | {s['grade_c_population']} / {s['grade_c_sampled']} | "
                 f"{s['low_grade_population']} / {s['low_grade_sampled']} | "
                 f"{s['zero_found_95_upper_bound_rows']} of {s['population_n']} |")
    L.append(f"| **total** | {len(population)} | {args.target} | "
             f"{sum(after_floor.values())} | **{len(sampled)}** | "
             f"{len(sampled) / len(population):.0%} | "
             f"{sum(o['_c'] for o in population)} / {sum(o['_c'] for o in sampled)} | "
             f"{sum(o['_low'] for o in population)} / {sum(o['_low'] for o in sampled)} | |")
    L += ["", "### By sub-stratum", "",
          "| harness | sub-stratum | population | sampled | coverage | "
          "grade C (pop / sampled) | low-grade marker (pop / sampled) | upper bound if none found |",
          "|---|---|---|---|---|---|---|---|"]
    for s in strata:
        L.append(f"| {s['harness_id']} | {s['sub_stratum']} | {s['population_n']} | "
                 f"**{s['sampled_n']}** | {s['coverage']:.0%} | "
                 f"{s['grade_c_population']} / {s['grade_c_sampled']} | "
                 f"{s['low_grade_population']} / {s['low_grade_sampled']} | "
                 f"{s['zero_found_95_upper_bound_rows']} of {s['population_n']} |")
    L += ["", "## How to judge", "",
          "The verdict column is blank on every row. Suggested values:", "",
          f"- **correct**: `{args.role}` is right.",
          "- **buyer_acts**: the row records something the company did, not something it said.",
          "- **provider_market_responds**: the voice is a vendor, partner or provider, not the buyer.",
          "- **other**: misclassified some other way (for example, a third party's characterisation "
          "not attributable to the buyer). Say what.",
          "- **can't tell**: the sheet does not carry enough to decide.", "",
          "Rows marked **LOW-GRADE (C)** were admitted under convention 41 on a thin theme match. "
          "That grade is about theme corroboration, not role, so judge them the same way. "
          "A row marked **GRADE C** (no low-grade marker) is at C for another reason -- "
          "H-TRADEPRESS-01's ST-PRESSCHAR writes the company's relayed self-description at C "
          "by design.", "",
          "Every field below is complete. Nothing is truncated.", "", "---", ""]

    n = 0
    for s in strata:
        L += [f"## {s['harness_id']}: {s['sub_stratum']} "
              f"({s['sampled_n']} of {s['population_n']})", ""]
        for oid in s["row_ids"]:
            o = next(r for r in sampled if r["observation_id"] == oid)
            n += 1
            name = (companies.get(o["company_id"]) or {}).get("canonical_name") or ""
            flag = (" -- **LOW-GRADE (C)**" if o["_low"] else
                    " -- **GRADE C** (no low-grade marker)" if o["_c"] else "")
            L += [f"### {n}. `{oid}` -- {cell(name)} ({o['company_id']}){flag}", "",
                  "| | |", "|---|---|",
                  f"| **Source harness** | {o['harness_id']} {o.get('harness_version') or ''} |",
                  f"| **Sub-stratum** | {s['sub_stratum']} |",
                  f"| **source_grade** | {cell(o.get('source_grade'))}"
                  f"{' (low-grade)' if o['_low'] else ''} |",
                  f"| **Current evidence_role** | {cell(o.get('evidence_role'))} |",
                  f"| **Family / topic** | {cell(o.get('evidence_family'))} / {cell(o.get('topic'))} |",
                  f"| **Strength / state / confidence** | {cell(o.get('signal_strength'))} / "
                  f"{cell(o.get('organizational_state'))} / {cell(o.get('confidence_0_1'))} |",
                  f"| **Observation text** | {cell(o.get('observation_text'))} |",
                  f"| **Evidence excerpt** | {cell(o.get('evidence_excerpt'))} |",
                  f"| **Source** | {cell(o.get('source_url'))} |",
                  f"| **Published / retrieved** | {cell(o.get('publication_date'))} / "
                  f"{cell(o.get('retrieval_date'))} |",
                  f"| **Prior review** | {cell(o.get('review_source'))} / {cell(o.get('review_status'))}"
                  f"{' / ' + cell(o.get('audit_verdict')) if o.get('audit_verdict') else ''} |",
                  f"| **Existing reviewer notes** | {cell(o.get('reviewer_notes'))} |",
                  "| **ROLE VERDICT** | |",
                  "| **Reviewer note** | |", ""]

    text = "\n".join(L) + "\n"
    md_path.write_text(text, encoding="utf-8")

    # The 900-character defect was silent. Make its recurrence loud: every field must be
    # present whole in what was actually written to disk.
    written = md_path.read_text(encoding="utf-8")
    missing = [(o["observation_id"], f) for o in sampled
               for f in ("observation_text", "evidence_excerpt", "source_url", "reviewer_notes")
               if o.get(f) and cell(o[f]) not in written]
    if missing:
        print(f"REFUSING: fields not present whole on the sheet: {missing[:5]}")
        return 1

    json_path.write_text(json.dumps({
        "role": args.role, "date": args.date, "seed": args.seed, "target": args.target,
        "floor": args.floor, "census_harnesses": args.census_harness,
        "population_n": len(population), "sampled_n": len(sampled),
        "by_harness": harness_summary, "by_sub_stratum": strata,
    }, indent=2), encoding="utf-8")

    print(f"wrote {md_path.relative_to(ROOT)} ({len(text):,} chars) and "
          f"{json_path.relative_to(ROOT)}")
    for s in harness_summary:
        print(f"  {s['harness_id']:<18} pop {s['population_n']:>3}  share "
              f"{s['proportional_share']:>5}  floor-alloc {s['allocated_after_floor']:>2}  "
              f"sampled {s['sampled_n']:>2}  cov {s['coverage']:.0%}  low-grade "
              f"{s['low_grade_population']}/{s['low_grade_sampled']}  ub0 "
              f"{s['zero_found_95_upper_bound_rows']}")
    for s in strata:
        print(f"    {s['sub_stratum']:<50} pop {s['population_n']:>3} sampled "
              f"{s['sampled_n']:>2} low {s['low_grade_population']}/{s['low_grade_sampled']} "
              f"ub0 {s['zero_found_95_upper_bound_rows']}")
    print(f"  full-field check passed on {len(sampled)} rows; longest field written: "
          f"{max(len(str(o.get(f) or '')) for o in sampled for f in ('observation_text', 'evidence_excerpt', 'reviewer_notes'))} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
