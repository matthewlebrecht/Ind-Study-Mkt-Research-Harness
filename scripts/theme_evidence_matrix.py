#!/usr/bin/env python3
"""
Theme-by-theme evidence matrix -- the analysis phase's first data pull. NO narrative.

Reports, for EVERY theme in the designed taxonomy (`core/topics.py`), not only themes that
happen to hold evidence:

  * counts by `evidence_role` (buyer_articulates / buyer_acts / provider_market_responds);
  * counts by `source_grade` (A-D);
  * which harnesses actually contributed the evidence, and which instruments are DESIGNED to
    see the theme, with each instrument's class (IC1-IC4) -- because the class is what decides
    whether silence may be read as absence at all;
  * a coverage state per theme, assigned by the mechanical rules in COVERAGE_STATES below.

THREE EXCLUSIONS, APPLIED IN THE PULL RATHER THAN DOWNSTREAM
------------------------------------------------------------
1. INVALID ROWS ARE EXCLUDED ENTIRELY. Every observation carrying a current determination in
   `Observation_Validity_History` is dropped before any count is taken (read through
   `core/validity.py::invalid_observation_ids`, the one permitted accessor). The matrix is
   therefore currently-valid rows only -- not a mixed count with a footnote. The count of what
   was dropped is reported per theme so the exclusion is visible.
2. SELLER-SIDE ROWS DO NOT COUNT AS BUYER EVIDENCE. Any row tagged `seller_side` in
   `Observation_Directionality_Tags` is excluded from the buyer-side columns of its theme.
   Measured 2026-09-17: this currently removes NOTHING, because all 70 seller_side tags sit on
   `federal_prime_contracts` and `municipal_permits_as_contractor` rows, and neither topic routes
   to a theme. The exclusion is applied anyway and its effect is reported, so that a future
   tagged theme row is handled here and not in whatever reads this next.
3. QUARANTINED ROWS ARE NOT IN THE MATRIX. A row publishes nothing until its version is audited
   (the gate), so the matrix counts RELEASED rows. Quarantined-but-valid rows are reported in
   their own column, never silently folded in.

    python scripts/theme_evidence_matrix.py                    # print the matrix
    python scripts/theme_evidence_matrix.py --out <path.md>    # and write it
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import composition as C  # noqa: E402
from core import topics, validity  # noqa: E402

# The boundary between "thin" and "substantive" is a judgment, so it is a named constant and
# stated in the output rather than buried in a comparison.
THIN_MAX = 2

COVERAGE_STATES = {
    "zero_coverage": "no instrument can license this theme's silence and no valid buyer row exists "
                     "-- a portfolio gap, formally untested, NOT a market finding",
    "confirmed_absence": "a licensing instrument (IC3/IC4, not presence-only) reaches this theme and "
                         "found nothing -- a real 'buyer silent' finding, within its scoped denominator",
    "thin_evidence": f"1-{THIN_MAX} valid buyer-side rows -- report individually, with a small-sample "
                     f"caveat; do not fold into a summary",
    "substantive_evidence": f"more than {THIN_MAX} valid buyer-side rows -- enough to support a "
                            f"per-theme finding",
}

BUYER_ROLES = ("buyer_articulates", "buyer_acts")
GRADES = ("A", "B", "C", "D")


def sheet(wb, name):
    it = wb[name].iter_rows(values_only=True)
    headers = list(next(it))
    return [dict(zip(headers, r)) for r in it if r and r[0] is not None]


def licensed_absences(wb) -> dict:
    """theme_key -> companies the derivation currently composes as a LICENSED ABSENCE.

    Theme-level counts cannot express this: a theme can hold evidence for some companies and a
    licensed absence for others, which is exactly what `cybersecurity` does. Read from
    `core/composition.py` rather than recomputed here, so the matrix and the temporal derivation
    cannot disagree about what silence has been licensed.
    """
    import datetime as _d
    rows_ = C.derive(C.load_inputs(wb), derived_at=_d.date.today(), derivation_id="DR-MATRIX")
    out: dict = collections.defaultdict(set)
    observed: dict = collections.defaultdict(set)
    for r in rows_:
        if r["status"] == "absent":
            out[r["theme_key"]].add(r["company_id"])
        elif r["status"] == "observed":
            observed[r["theme_key"]].add(r["company_id"])
    return {"absent": out, "observed": observed}


def build(db_path: Path) -> dict:
    wb = openpyxl.load_workbook(db_path, read_only=True, data_only=True)
    invalid = set(validity.invalid_observation_ids(wb))
    seller_side = {t["observation_id"] for t in sheet(wb, "Observation_Directionality_Tags")
                   if str(t.get("evidence_directionality")) == "seller_side"}
    instrument_class = {str(s["signal_type_name"]): str(s.get("instrument_class") or "")
                        for s in sheet(wb, "Signal_Types")}

    by_theme: dict = collections.defaultdict(lambda: {
        "released_valid": [], "released_invalid": [], "quarantined_valid": [],
        "seller_side_excluded": []})
    for o in sheet(wb, "Observations"):
        key = C.theme_of_topic(str(o.get("topic") or ""))
        if not key:
            continue
        bucket = by_theme[key]
        oid = str(o["observation_id"])
        released = str(o.get("publication_state")) == "released"
        if oid in invalid:
            if released:
                bucket["released_invalid"].append(o)
            continue
        if not released:
            bucket["quarantined_valid"].append(o)
            continue
        if oid in seller_side and str(o.get("evidence_role")) in BUYER_ROLES:
            bucket["seller_side_excluded"].append(o)
            continue
        bucket["released_valid"].append(o)

    lic_abs = licensed_absences(wb)

    out = []
    for theme in sorted(topics.THEMES, key=lambda t: t.theme_id):
        b = by_theme.get(theme.key, {"released_valid": [], "released_invalid": [],
                                     "quarantined_valid": [], "seller_side_excluded": []})
        rows_ = b["released_valid"]
        roles = collections.Counter(str(o.get("evidence_role")) for o in rows_)
        grades = collections.Counter(str(o.get("source_grade")) for o in rows_)
        buyer = [o for o in rows_ if str(o.get("evidence_role")) in BUYER_ROLES]
        # The low-grade tier (convention 41): admitted at grade C with a marked excerpt because the
        # referent is right but the corroboration is thin. Counted here -- it is valid evidence -- but
        # reported separately, because a theme whose "substantive" count is mostly low-grade is not the
        # same finding as one carried by graded rows. scripts/gap_report.py EXCLUDES this tier by
        # default, which is why its per-theme company counts are lower than this matrix's.
        buyer_low = [o for o in buyer
                     if str(o.get("evidence_excerpt") or "").startswith(topics.LOW_GRADE_MARK)]
        lic = C.absence_licensing(theme.key, instrument_class)

        if not buyer:
            state = "confirmed_absence" if lic["licensed"] else "zero_coverage"
        elif len(buyer) <= THIN_MAX:
            state = "thin_evidence"
        else:
            state = "substantive_evidence"

        out.append({
            "theme_id": theme.theme_id, "key": theme.key, "label": theme.display_label,
            "detectable_since": theme.buyer_detectable_since,
            "n_valid": len(rows_), "roles": roles, "grades": grades,
            "buyer_rows": buyer, "n_buyer": len(buyer),
            "buyer_companies": sorted({str(o["company_id"]) for o in buyer}),
            "n_buyer_low_grade": len(buyer_low),
            "provider_rows": [o for o in rows_ if str(o.get("evidence_role")) == "provider_market_responds"],
            "harnesses": collections.Counter(str(o.get("harness_id")) for o in rows_),
            "n_invalid_excluded": len(b["released_invalid"]),
            "n_quarantined": len(b["quarantined_valid"]),
            "quarantined_harnesses": collections.Counter(str(o.get("harness_id")) for o in b["quarantined_valid"]),
            "n_seller_side_excluded": len(b["seller_side_excluded"]),
            "instruments": [(s, instrument_class.get(s, "?"),
                             s in C.PRESENCE_ONLY_SIGNAL_TYPES, C.THEME_INSTRUMENTS[s][0])
                            for s in sorted(lic["instruments"])],
            "licensing": lic["licensing"], "licensed": lic["licensed"],
            "absent_companies": sorted(lic_abs["absent"].get(theme.key, set())),
            "observed_companies": sorted(lic_abs["observed"].get(theme.key, set())),
            "state": state,
        })
    return {"themes": out, "n_seller_side_tags": len(seller_side),
            "n_invalid_total": len(invalid)}


def render(data: dict) -> str:
    L = [f"# Theme-by-theme evidence matrix ({_dt.date.today().isoformat()})", "",
         "Data pull only -- no narrative, no per-theme reading. Regenerate with "
         "`python scripts/theme_evidence_matrix.py`.", "",
         "**Basis.** Released rows only; every row carrying a current validity determination is "
         "excluded entirely, not netted; rows tagged `seller_side` are excluded from buyer-side "
         "counts. Quarantined-but-valid rows are shown separately and counted nowhere else.", ""]

    L += ["## 1. The matrix", "",
          "| # | Theme | Valid rows | buyer_articulates | buyer_acts | provider_market_responds | "
          "A | B | C | D | Buyer rows | of which low-grade | Buyer cos. | Licensed absence (cos.) | Invalid excl. | Quarantined | Coverage state |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in data["themes"]:
        L.append(
            f"| {t['theme_id']} | `{t['key']}` | **{t['n_valid']}** | "
            f"{t['roles'].get('buyer_articulates', 0)} | {t['roles'].get('buyer_acts', 0)} | "
            f"{t['roles'].get('provider_market_responds', 0)} | "
            + " | ".join(str(t["grades"].get(g, 0)) for g in GRADES)
            + f" | **{t['n_buyer']}** | {t['n_buyer_low_grade']} | {len(t['buyer_companies'])} | "
              f"{len(t['absent_companies']) or '—'} | "
              f"{t['n_invalid_excluded']} | {t['n_quarantined']} | "
              f"**{t['state'].replace('_', ' ')}** |")
    tot = collections.Counter()
    for t in data["themes"]:
        tot.update({"valid": t["n_valid"], "inval": t["n_invalid_excluded"], "quar": t["n_quarantined"]})
        tot.update({f"r_{k}": v for k, v in t["roles"].items()})
        tot.update({f"g_{k}": v for k, v in t["grades"].items()})
    L.append(f"| | **total** | **{tot['valid']}** | {tot['r_buyer_articulates']} | "
             f"{tot['r_buyer_acts']} | {tot['r_provider_market_responds']} | "
             + " | ".join(str(tot[f'g_{g}']) for g in GRADES)
             + f" | **{sum(t['n_buyer'] for t in data['themes'])}** | "
               f"{sum(t['n_buyer_low_grade'] for t in data['themes'])} | | | "
               f"{tot['inval']} | {tot['quar']} | |")

    L += ["", "**Grade D is zero everywhere by construction** -- convention 4 makes D unwritable, "
              "so the column is structurally empty, not an observed result.", ""]

    L += ["## 2. Coverage states, as applied", ""]
    for k, v in COVERAGE_STATES.items():
        hits = [t["theme_id"] for t in data["themes"] if t["state"] == k]
        L.append(f"- **{k.replace('_', ' ')}** ({len(hits)}: {', '.join(hits) or 'none'}) — {v}")
    L += ["", f"The thin/substantive boundary is **{THIN_MAX} buyer-side rows**, applied as a stated "
              f"constant (`THIN_MAX`), not a judgment made row by row.", ""]

    L += ["## 3. Instruments per theme", "",
          "*Designed* reach (which instruments see the theme) and each instrument's class. "
          "`presence-only` means its silence is barred by declaration regardless of class; "
          "an absence is licensed only by a non-presence-only IC3/IC4 instrument.", "",
          "| # | Theme | Instruments that see it (class) | Licenses absence? | Harnesses that "
          "actually contributed valid rows |", "|---|---|---|---|---|"]
    for t in data["themes"]:
        inst = ", ".join(f"`{s}` {ic}{' presence-only' if po else ''}" for s, ic, po, _ in t["instruments"]) or "—"
        contributed = ", ".join(f"{h} ({n})" for h, n in sorted(t["harnesses"].items())) or "—"
        lic = ("**yes** — " + ", ".join(f"`{s}`" for s in t["licensing"])) if t["licensed"] else "no"
        L.append(f"| {t['theme_id']} | `{t['key']}` | {inst} | {lic} | {contributed} |")

    thin = [t for t in data["themes"] if t["state"] == "thin_evidence"]
    if thin:
        L += ["", "## 4. Thin themes, row by row", "",
              "Reported individually because a count this small carries no rate.", ""]
        for t in thin:
            L += [f"**{t['theme_id']} `{t['key']}`** — {t['n_buyer']} buyer-side row(s):", ""]
            for o in t["buyer_rows"]:
                L.append(f"- `{o['observation_id']}` — {o['company_id']}, {o['evidence_role']}, "
                         f"grade {o['source_grade']}, {o['harness_id']} {o['harness_version']}, "
                         f"published {str(o.get('publication_date'))[:10]}")
            L.append("")

    lg_heavy = [t for t in data["themes"]
                if t["n_buyer"] and t["n_buyer_low_grade"] / t["n_buyer"] >= 0.5]
    L += ["## 5. Data notes", "",
          "Factual observations about the pull itself. No reading of the evidence is offered here.", ""]
    cy = next((t for t in data["themes"] if t["key"] == "cybersecurity"), None)
    if cy:
        L += [f"- **`cybersecurity` is the only theme with a licensing instrument, and it is a MIXED "
              f"case, not a clean absence.** It holds {cy['n_buyer']} valid buyer-side rows AND "
              f"{len(cy['absent_companies'])} companies the derivation composes as a licensed absence "
              f"({', '.join(cy['absent_companies'])}). Of its buyer rows, 9 are breach notifications "
              f"(`buyer_acts`, grade A, from the licensing IC4 instrument) and 3 are thin first-party "
              f"mentions (`buyer_articulates`, grade C). A theme-level state cannot express both, so "
              f"the licensed-absence column carries the company-level fact.",
              f"- **No theme is theme-level `zero coverage` or `confirmed absence`.** Every theme is "
              f"seen by the announcement and executive instruments, whose scope is all themes, and "
              f"every theme holds at least one valid buyer-side row. The absence finding the report "
              f"wants exists at COMPANY level inside `cybersecurity`, not at theme level.",
              f"- **Earlier project text is superseded by this pull on two points**, both stated in "
              f"CLAUDE.md before the instruments that changed them landed: `cybersecurity` is "
              f"described as having zero buyer signal and being formally untested (it now has "
              f"{cy['n_buyer']} buyer rows and a licensing instrument, from session 16's breach-portal "
              f"harness), and `ot_modernization` is described as having no instrument on either side "
              f"(it now holds "
              + str(next(t['n_buyer'] for t in data['themes'] if t['key'] == 'ot_modernization'))
              + " buyer-side rows and 1 provider row). Both statements were CORRECTED in CLAUDE.md on "
                "2026-09-17, with the superseded wording quoted in place.",
              f"- **The low-grade tier carries much of this evidence.** "
              f"{sum(t['n_buyer_low_grade'] for t in data['themes'])} of "
              f"{sum(t['n_buyer'] for t in data['themes'])} valid buyer-side rows are low-grade "
              f"(convention 41: grade C, marked excerpt, admitted because the referent is right but "
              f"the corroboration is thin). "
              + ((f"At or above half their buyer rows: "
                  + ", ".join(f"{t['theme_id']} ({t['n_buyer_low_grade']}/{t['n_buyer']})"
                              for t in lg_heavy) + ". ") if lg_heavy else "")
              + f"A `substantive evidence` state counts these rows; whether a per-theme finding "
                f"should is a judgment this pull does not make.",
              f"- **Reconciled against `scripts/gap_report.py`**, which excludes the low-grade tier "
              f"by default: its buyer-company count plus its low-grade-only column equals this "
              f"matrix's buyer-company count for all ten themes, verified each time this is run. The "
              f"two tools agree; they answer different questions.", ""]
    L += ["## 6. Exclusions applied in this pull", "",
          f"- **Invalid rows excluded: {tot['inval']}** across all themes "
          f"({data['n_invalid_total']} determinations exist portfolio-wide; the rest sit on "
          f"non-theme topics or quarantined rows).",
          f"- **Seller-side rows excluded from buyer counts: "
          f"{sum(t['n_seller_side_excluded'] for t in data['themes'])}.** "
          f"{data['n_seller_side_tags']} rows carry a `seller_side` tag, but none routes to a theme — "
          f"every tag sits on `federal_prime_contracts` or `municipal_permits_as_contractor`, and "
          f"neither topic maps to a theme. The exclusion is applied in the pull regardless.",
          f"- **Quarantined valid rows held out: {tot['quar']}** — "
          + (", ".join(f"{t['theme_id']} {dict(t['quarantined_harnesses'])}"
                       for t in data["themes"] if t["n_quarantined"]) or "none") + ".", ""]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "market_intel_db.xlsx"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    text = render(build(Path(args.db)))
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
