#!/usr/bin/env python3
"""
Draw the audit gate's samples from a quarantined run, and emit the human review sheet.

This is the *sampler*, deliberately not the judge. It selects rows into the strata that
`docs/gates/gate_new_harness_output.md` defines and lays them out for reading; it assigns
no verdicts. A module that scored its own harness's rows would be the machine grading its
own homework, which is the exact thing the gate exists to prevent.

    python scripts/audit_sample.py --harness H-TRADEPRESS-01 --version v1.0 --run HR-0021

Writes two files:

  harness_output/audits/<harness_id>__<version>__review.md   the RANDOM CONTROL, as a
                                                   flat table, one row per line -- this is
                                                   what a person reads and judges
  harness_output/audits/<harness_id>__<version>__strata.json  the adversarial strata, with
                                                   each row's evidence laid out for the
                                                   mechanical pass

BOTH ARE VERSION-KEYED, and that is a fix rather than a decoration. They were keyed on
harness id alone until 2026-09-01, so bumping a version silently overwrote the prior
version's review sheet -- destroying the one artifact human review depends on, for the
version that had not been judged yet. H-TRADEPRESS-01 v1.1's sheet was lost to exactly
this the day it was written. The audit artifact `<harness_id>__<version>.json` was already
version-keyed for the same reason (`core/audit.py`, "KEYED ON VERSION, NOT RUN"); these two
simply had not been.

The random control is separated from the strata on purpose. It is the only sample that
produces an extrapolatable precision rate, so it is the one that needs independent human
judgment; the adversarial strata are mechanical and can be judged by the same process that
built the harness.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.parse
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import audit  # noqa: E402

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"

# Deterministic sampling. A random control drawn from an unseeded RNG cannot be redrawn,
# so `row_ids_sampled` would be the only record of what was looked at and a disputed
# result could never be reproduced. The seed is recorded in the review sheet.
SEED = 20260831

POLYSEMOUS = ["integration", "platform", "solutions", "transformation", "digital",
              "modernization", "ai", "automation", "cloud", "optimization"]

INDEX_URL_RE = re.compile(
    r"(?i)(/news/?$|/press/?$|/newsroom/?$|/press-releases?/?$|/media/?$|/tag/|/topic/|"
    r"/category/|/author/|/search|/archive)")


def sheet_rows(wb, name):
    ws = wb[name]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    out = []
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        out.append({h: ws.cell(r, i + 1).value for i, h in enumerate(headers) if h})
    return out


def common_word_match(row, companies) -> bool:
    """Does this row's company name reduce to a single ordinary English word?"""
    from core.resolution import WEAK_TOKENS, tokens
    from harnesses.h_firstparty_01.article import COMMON_WORD_NAMES
    name = companies.get(str(row.get("company_id")), "")
    distinctive = [t for t in tokens(name) if t not in WEAK_TOKENS]
    return len(distinctive) <= 1 and bool(distinctive) and \
        distinctive[0].lower() in COMMON_WORD_NAMES


def eponymous(row, companies, execs) -> bool:
    """Is a quoted person's surname also a token of the employer's name?"""
    from core.resolution import tokens
    name = companies.get(str(row.get("company_id")), "")
    company_tokens = {t.upper() for t in tokens(name)}
    excerpt = str(row.get("evidence_excerpt") or "")
    for person in execs.get(str(row.get("company_id")), []):
        parts = [p for p in re.split(r"\s+", str(person)) if len(p.strip(".")) > 1]
        if parts and parts[-1].upper() in company_tokens and parts[-1] in excerpt:
            return True
    # Also catch a speaker named inline in the excerpt.
    for m in re.finditer(r"([A-Z][a-z]+(?:\s+[A-Z][A-Za-z'\-]+){1,2})\s*\(", excerpt):
        parts = m.group(1).split()
        if parts[-1].upper() in company_tokens:
            return True
    return False


def matched_terms(row) -> list[str]:
    m = re.search(r"matched:\s*(.+)$", str(row.get("evidence_excerpt") or ""))
    return [t.strip() for t in m.group(1).split(",")] if m else []


def _registrable(url: str) -> str:
    """Registrable domain of a URL, for own-domain comparison."""
    host = urllib.parse.urlparse(str(url or "")).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def off_own_domain(row, company_sites: dict) -> bool:
    """Is this row's source_url on a domain other than the company's own?

    This used to be `lambda r: True`, with the comment "every row in this harness is
    third-party by construction". That was true of the two harnesses the sampler was
    written for and false the moment it met a first-party one: H-JOBPOST-01 cites the
    company's own careers page for every row, and the stratum labelled "not the company's
    own domain" selected all 21 of them.

    A selection rule is a claim the artifact records for someone to re-execute later, so a
    rule that cannot be false is worse than a missing stratum -- it is a false statement
    about how those rows were chosen, and it fires on 21 of 21 exactly the way session 4's
    tabular detector fired on 28 of 28. Convention 36: the pattern was fine, the thing it
    was applied to was wrong, and nothing raised an error.

    Unknown company or missing website returns False: a stratum should not fill up with
    rows whose membership could not actually be determined.
    """
    site = company_sites.get(str(row.get("company_id")))
    if not site:
        return False
    src = _registrable(row.get("source_url"))
    return bool(src) and src != _registrable(site)


def build_strata(rows, companies, execs, company_sites=None) -> list[dict]:
    """The adversarial strata. A stratum with no rows is kept, with sampled_n 0."""
    company_sites = company_sites or {}

    def sel(fn):
        return [r for r in rows if fn(r)]

    specs = [
        ("single_common_word",
         "rows whose company match rests on one dictionary-word token "
         "(article.COMMON_WORD_NAMES)",
         lambda r: common_word_match(r, companies)),
        ("off_own_domain",
         "rows whose source_url registrable domain differs from the company's website "
         "in Companies (www. and subdomains count as the same domain)",
         lambda r: off_own_domain(r, company_sites)),
        ("index_listing_url",
         "rows sourced from an index, listing, tag, category or archive URL",
         lambda r: bool(INDEX_URL_RE.search(str(r.get("source_url") or "")))),
        ("polysemous_term",
         f"rows whose matched terms are drawn only from {POLYSEMOUS}",
         lambda r: bool(matched_terms(r)) and all(
             any(p in t.lower() for p in POLYSEMOUS) for t in matched_terms(r))),
        ("eponymous_name",
         "rows where a quoted person's surname is also a token of the employer's name",
         lambda r: eponymous(r, companies, execs)),
        ("a_graded",
         "CENSUS, not a sample: every row with source_grade = A",
         lambda r: str(r.get("source_grade") or "") == "A"),
    ]
    out = []
    for sid, rule, fn in specs:
        picked = sel(fn)
        out.append({"stratum_id": sid, "selection_rule": rule,
                    "population_n": len(picked),
                    "rows": picked})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--harness", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--control", type=int, default=30)
    ap.add_argument("--only-quarantined", action="store_true",
                    help="restrict the population to rows whose publication_state is "
                         "quarantined. For a version that holds BOTH released, "
                         "human-reviewed rows and a later run's quarantined rows "
                         "(H-FMCSA-01 v1.3: 20 released from the grandfathered runs, 4 "
                         "quarantined from HR-0034), the default population would put "
                         "already-judged rows back in front of the reviewer. Off by "
                         "default so every sheet drawn before 2026-09-04 redraws "
                         "identically.")
    ap.add_argument("--ids", default="",
                    help="comma-separated observation_ids: restrict the population to "
                         "exactly these rows. The re-executable form of --only-quarantined "
                         "once the rows have been released -- a sheet regenerated after "
                         "the verdicts are recorded must still describe the population "
                         "that was judged, not whatever now sits at the version.")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(Path(args.db), data_only=True)
    company_rows = sheet_rows(wb, "Companies")
    companies = {str(c["company_id"]): str(c["canonical_name"])
                 for c in company_rows}
    company_sites = {str(c["company_id"]): str(c.get("website") or "")
                     for c in company_rows}
    execs: dict[str, list] = {}
    for e in sheet_rows(wb, "Company_Executives"):
        execs.setdefault(str(e["company_id"]), []).append(e.get("full_name"))

    rows = [r for r in sheet_rows(wb, "Observations")
            if str(r.get("harness_id")) == args.harness
            and str(r.get("harness_version")) == args.version]
    if args.only_quarantined:
        rows = [r for r in rows if str(r.get("publication_state")) == "quarantined"]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
        rows = [r for r in rows if str(r.get("observation_id")) in wanted]
        missing = wanted - {str(r.get("observation_id")) for r in rows}
        if missing:
            print(f"--ids named rows not at {args.harness} {args.version}: "
                  f"{sorted(missing)}")
            return 1
    if not rows:
        print(f"no Observations for {args.harness} {args.version}")
        return 1

    # ---- suppression stratum, drawn from Attempts rather than Observations ----
    #
    # The gap every other stratum leaves open. All of them sample rows that were WRITTEN,
    # so without this the gate measures precision only and can never fail a harness for
    # over-suppression -- for quietly throwing away good evidence.
    suppressed = [a for a in sheet_rows(wb, "Attempts")
                  if str(a.get("harness_id")) == args.harness
                  and str(a.get("harness_version")) == args.version
                  and str(a.get("failure_category") or "").startswith(
                      "suppressed_redundant")]

    strata = build_strata(rows, companies, execs, company_sites)
    strata.append({
        "stratum_id": "suppressed_judged",
        "selection_rule": ("Attempts rows carrying failure_category "
                           "suppressed_redundant_key / _judged. The verdict here is "
                           "whether the SUPPRESSION was correct, not whether a claim was "
                           "supported -- the only stratum that can fail a harness for "
                           "over-suppression."),
        "population_n": len(suppressed),
        "rows": suppressed,
    })

    rng = random.Random(SEED)
    control_n = min(args.control, len(rows))
    control = rng.sample(rows, control_n)

    audit.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- strata file, for the mechanical pass ----
    strata_out = {
        "harness_id": args.harness, "harness_version": args.version, "run_id": args.run,
        "population_size": len(rows), "seed": SEED,
        "strata": [{"stratum_id": s["stratum_id"],
                    "selection_rule": s["selection_rule"],
                    "population_n": s["population_n"],
                    "rows": [{k: (str(v) if v is not None else None)
                              for k, v in r.items()} for r in s["rows"]]}
                   for s in strata],
    }
    spath = audit.AUDIT_DIR / f"{args.harness}__{args.version}__strata.json"
    spath.write_text(json.dumps(strata_out, indent=2), encoding="utf-8")

    # ---- review sheet, for a person ----
    lines = [
        f"# {args.harness} {args.version} — random control sample",
        "",
        f"**Run:** {args.run}  |  **Population:** {len(rows)} observations  |  "
        f"**Sampled:** {control_n}  |  **Seed:** {SEED} (deterministic — redrawable)",
        "",
    ]
    if args.ids:
        lines += [
            f"> **Population restricted to named rows** (`--ids {args.ids}`): the rows "
            f"HR-0034-style runs wrote at a version that also holds earlier released, "
            f"human-reviewed rows. Those earlier rows are deliberately not on this sheet.",
            "",
        ]
    if args.only_quarantined:
        lines += [
            "> **Population restricted to rows with `publication_state = quarantined`** "
            "(`--only-quarantined`). Rows at this version that are already released and "
            "human-reviewed are deliberately not on this sheet.",
            "",
        ]
    lines += [
        "This is the **random control**: a simple random sample of the whole run, with no",
        "stratification. It is the only sample that produces an extrapolatable precision",
        "rate, and that rate is always quoted with the denominator above.",
        "",
        "The adversarial strata are in "
        f"`harness_output/audits/{args.harness}__{args.version}__strata.json` and were judged",
        "mechanically. This sheet is the part that needs independent human judgment.",
        "",
        "## How to judge",
        "",
        "- **supported** — the evidence supports the claim, at the strength claimed, "
        "about the company named.",
        "- **overgraded** — the claim is real but overstated. Survives at lower strength.",
        # NOTE: this module is a gate module behind the convention 41 wall, so it must not
        # name the validity table even in prose -- the wall scan is a literal one and it
        # caught exactly that on 2026-09-15. Say what the reviewer must know, name the
        # convention, and leave the table to docs/conventions.md.
        "- **unsupported** — the evidence does not support the claim at all. The row is "
        "**recorded invalid**: not downgraded to `weak_clue` (convention 32), and since "
        "convention 45 (2026-09-15) not deleted either — no observation is ever "
        "hard-deleted, so it keeps its row and its id and a dated determination is "
        "appended against it.",
        "- **wrong_entity** — wrong company, or a statement attributed to someone who did "
        "not make it. Recorded invalid the same way, **and the whole run stays "
        "quarantined.**",
        "",
        "---",
        "",
    ]
    judged = [r for r in control if str(r.get("audit_verdict") or "").strip()]
    if judged:
        import collections as _c
        tally = _c.Counter(str(r["audit_verdict"]).strip() for r in judged)
        excluded = sum(tally.get(v, 0) for v in ("unsupported", "wrong_entity"))
        lines[3:3] = [
            f"> **AUDITED — {len(judged)} of {control_n} judged.** "
            + ", ".join(f"{n} {v}" for v, n in tally.most_common())
            + f". Precision {tally.get('supported', 0)}/{len(judged)}; "
            f"exclusions {excluded}/{len(judged)}.",
            ">",
            "> Artifact: "
            f"`harness_output/audits/{args.harness}__{args.version}.json`. "
            "`overgraded` is a downgrade, not an exclusion — those rows survive at a "
            "lower strength.",
            "",
        ]
    # Nothing on this sheet or in the strata file is capped. Claim, Evidence and Reviewer
    # notes were cut at 900 characters and every strata field at 600, silently: on
    # H-PROCUREMENT-01 v1.0 O00632 lost its joint-venture exclusion and its page-cap
    # floor caveat, and the reviewer judged the row without them. Removed 2026-09-15.
    for i, r in enumerate(control, 1):
        terms = matched_terms(r)
        excerpt = re.sub(r"\s*\|\s*matched:.*$", "",
                         str(r.get("evidence_excerpt") or "")).strip()
        lines += [
            f"### {i}. `{r.get('observation_id')}` — "
            f"{companies.get(str(r.get('company_id')), r.get('company_id'))} — "
            f"{r.get('topic')}",
            "",
            f"| | |",
            f"|---|---|",
            f"| **Claim** | {str(r.get('observation_text') or '')} |",
            f"| **Evidence** | {excerpt} |",
            f"| **Source** | <{r.get('source_url')}> |",
            f"| **Matched terms** | {', '.join(terms) if terms else '(none recorded)'} |",
            f"| **Role / family** | {r.get('evidence_role')} / {r.get('evidence_family')} |",
            f"| **Grade / strength / state** | {r.get('source_grade')} / "
            f"{r.get('signal_strength')} / {r.get('organizational_state')} |",
            f"| **Machine confidence** | {r.get('confidence_0_1')} |",
        ]
        # Once a verdict is recorded on the row, the sheet shows it instead of an empty
        # prompt. The sheet is generated, not typed, so it has to reflect the workbook's
        # current state rather than freeze the moment it was first drawn -- otherwise the
        # audited and unaudited versions look identical and someone judges a row twice.
        verdict = str(r.get("audit_verdict") or "").strip()
        if verdict:
            notes = str(r.get("reviewer_notes") or "").strip()
            lines += [
                f"| **RECORDED VERDICT** | **{verdict}** "
                f"(review_status `{r.get('review_status')}`, "
                f"source `{r.get('review_source')}`) |",
                f"| **Reviewer notes** | {notes} |",
                f"| **Publication state** | `{r.get('publication_state')}` |",
            ]
        else:
            lines += [
                "| **YOUR VERDICT** | supported / overgraded / unsupported / wrong_entity |",
                "| **YOUR CONFIDENCE** | |",
            ]
        lines.append("")
    rpath = audit.AUDIT_DIR / f"{args.harness}__{args.version}__review.md"
    rpath.write_text("\n".join(lines), encoding="utf-8")

    print(f"population: {len(rows)} observations")
    for s in strata:
        print(f"  stratum {s['stratum_id']:22s} {s['population_n']:4d} row(s)")
    print(f"  random control          {control_n:4d} row(s) of {len(rows)}")
    print(f"\nwrote {rpath}")
    print(f"wrote {spath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
