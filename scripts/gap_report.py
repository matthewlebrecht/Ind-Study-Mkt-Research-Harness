#!/usr/bin/env python3
"""
Buyer signal vs. provider messaging, by modernization theme.

This is what the seller benchmark is *for*. Collecting provider messaging is only useful
next to buyer evidence in the same vocabulary, and `core/topics.py` exists so both sides
land on the same nine themes.

The report deliberately separates the reasons a theme can show no buyer signal, because
collapsing them is how a portfolio gap gets written up as a market finding:

  covered              a buyer-side instrument sees this theme and found it
  no absence license   instruments see this theme and found nothing, but none of them may
                       read its silence as absence (IC1/IC2, or IC3 declared presence-only)
                       -- taxonomy §26 "formally untested"; a PORTFOLIO gap, not a finding
  buyer silent         an instrument whose class licenses absence (IC3/IC4, not
                       presence-only) reached the theme and found nothing -- the only row
                       that is evidence about buyers
  NO INSTRUMENT        no buyer-side instrument can see this theme at all

Session 14 (2026-09-06, item 0b): which instruments see a theme and whether any licenses
absence is read from core/composition.py (THEME_INSTRUMENTS, PRESENCE_ONLY_SIGNAL_TYPES,
Signal_Types.instrument_class) -- the same declarations the Company_State_History
derivation composes on -- not from a flag on the theme. A hand-set `absence_licensed` flag
drifted from the instruments' real capability within a week; it is gone. Consequence: as
of this date NO theme prints "buyer silent", because H-JOBPOST-01 (IC3) is presence-only
until its readability denominator is accepted and every other theme instrument is IC1/IC2.
cloud_infrastructure_migration and cybersecurity, the two candidate divergences of the
original gap report, are therefore "no absence license": untested, not silent.

The middle row is weaker than it looks, and the 2026-08-31 amendment says so: as of that
date every theme is `buyer_detectable`, because H-FIRSTPARTY-01 classifies free-text
announcements through the same spine and can therefore see any of them. But an announcement
is a biased instrument -- companies announce what they are proud of and never announce the
legacy estate that forced them -- so `buyer silent` on an announcement-only theme means
"not announced", which is weaker than "not happening" and weaker than the absence of a job
posting. Those themes are **formally untested**, not weak findings and not divergences
(convention 21a).

    python scripts/gap_report.py
    python scripts/gap_report.py --csv data/snapshots/gap_report.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import composition, topics  # noqa: E402
from core.attempts import COVERAGE_OUTCOMES  # noqa: E402

DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"


def load(db_path: Path):
    wb = openpyxl.load_workbook(db_path)
    ws = wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    rows = []
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        rows.append({h: ws.cell(r, i + 1).value for i, h in enumerate(headers)})
    return rows


def buyer_universe(db_path: Path) -> int:
    """All buyer companies in Companies, the structural-coverage denominator (108)."""
    wb = openpyxl.load_workbook(db_path, read_only=True, data_only=True)
    it = wb["Companies"].iter_rows(values_only=True)
    headers = list(next(it))
    return sum(1 for r in it if r and r[0]
               and str(dict(zip(headers, r)).get("qualification_status")) != "provider_benchmark")


def published_runs(db_path: Path) -> set:
    wb = openpyxl.load_workbook(db_path, read_only=True, data_only=True)
    it = wb["Harness_Runs"].iter_rows(values_only=True)
    headers = list(next(it))
    return {str(dict(zip(headers, r)).get("harness_run_id")) for r in it
            if r and r[0] and str(dict(zip(headers, r)).get("publication_status")) == "published"}


def licensed_absence_coverage(db_path: Path, signals: set) -> set:
    """Companies a licensing (IC3/IC4, not presence-only) instrument can see at all: a scoped
    attempt with ANY coverage outcome (covered, absent_confirmed, partial) from a published
    run -- the structural-coverage denominator §20.5 says every absence claim must be quoted
    against. Session 16: H-BREACHPORTAL-01 licenses absence for cybersecurity for the
    companies headquartered in a state with a searchable portal, and the report must say
    "8 of 108", not a bare "buyer silent". Quick fix 2026-09-07: counted only
    absent_confirmed until then, which dropped the one in-scope company that WAS listed."""
    wb = openpyxl.load_workbook(db_path, read_only=True, data_only=True)
    ws = wb["Attempts"]
    it = ws.iter_rows(values_only=True)
    headers = list(next(it))
    out = set()
    pub = published_runs(db_path)          # a quarantined run's attempts license nothing yet
    for r in it:
        if not r or not r[0]:
            continue
        d = dict(zip(headers, r))
        if (str(d.get("attempted_signal")) in signals and str(d.get("scope")) == "scoped"
                and str(d.get("outcome")) in COVERAGE_OUTCOMES and str(d.get("run_id")) in pub):
            out.add(str(d.get("company_id")))
    return out


def instrument_classes(db_path: Path) -> dict:
    """signal_type_name -> instrument_class, from the registry sheet."""
    wb = openpyxl.load_workbook(db_path, read_only=True, data_only=True)
    ws = wb["Signal_Types"]
    it = ws.iter_rows(values_only=True)
    headers = list(next(it))
    out = {}
    for r in it:
        if r and r[0]:
            d = dict(zip(headers, r))
            out[str(d.get("signal_type_name"))] = str(d.get("instrument_class") or "")
    return out


def theme_of(row) -> str | None:
    """Map an observation onto the shared theme spine, or None if it does not carry one.

    Seller rows already use theme keys as their topic. Buyer rows use harness-native topic
    keys, mapped through core.topics.BUYER_SIGNAL_TO_THEME -- deliberately a mapping rather
    than a rename, because those keys are written into committed, human-reviewed rows.

    A buyer row with no mapping is not forced into a theme. Most buyer evidence so far is
    regulatory and simply is not about a modernization theme; pretending otherwise would
    invent convergence.
    """
    topic = str(row.get("topic") or "")
    if topic in topics.THEMES_BY_KEY:
        return topic
    return topics.theme_of_buyer_signal(topic)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--csv", help="also write the table to this path")
    ap.add_argument("--include-low-grade", action="store_true",
                    help="count low-grade rows (grade C, '[low-grade:' excerpt) as signal. "
                         "Off by default: they are written for review, not for the table.")
    args = ap.parse_args()

    rows = load(Path(args.db))
    ic = instrument_classes(Path(args.db))
    # 2026-09-03 corroboration-gate policy: corroboration-strength gates now WRITE at low
    # grade instead of refusing. Those rows exist so a reviewer can sift them; counting
    # them here as buyer or seller signal would let the extractor's weakest tier move the
    # headline table, which is exactly what the tier exists to prevent. They are counted
    # separately and reported.
    # Session 16: a quarantined row contributes nothing to any published number (the audit
    # gate), and this table is a published number. H-BREACHPORTAL-01's first, unaudited
    # rows briefly counted as six cybersecurity buyers here before this filter existed.
    quarantined = [r for r in rows if str(r.get("publication_state") or "") != "released"]
    rows = [r for r in rows if str(r.get("publication_state") or "") == "released"]
    low_grade = [r for r in rows if str(r.get("evidence_excerpt") or "").startswith(topics.LOW_GRADE_MARK)]
    if not args.include_low_grade:
        rows = [r for r in rows if not str(r.get("evidence_excerpt") or "").startswith(topics.LOW_GRADE_MARK)]

    buyer = defaultdict(set)     # theme -> company_ids
    seller = defaultdict(set)    # theme -> provider_ids
    unmapped_buyer = defaultdict(set)
    lg_buyer = defaultdict(set)  # theme -> company_ids carried ONLY by low-grade rows
    lg_seller = defaultdict(set)
    for r in low_grade:
        t = theme_of(r)
        if not t:
            continue
        (lg_seller if r.get("evidence_role") == "provider_market_responds" else lg_buyer)[t].add(r.get("company_id"))

    for r in rows:
        role = r.get("evidence_role")
        t = theme_of(r)
        cid = r.get("company_id")
        if role == "provider_market_responds":
            if t:
                seller[t].add(cid)
        elif role in ("buyer_acts", "buyer_articulates"):
            if t:
                buyer[t].add(cid)
            else:
                unmapped_buyer[str(r.get("topic"))].add(cid)

    n_providers = len({r["company_id"] for r in rows
                       if r.get("evidence_role") == "provider_market_responds"})
    n_buyers = len({r["company_id"] for r in rows
                    if r.get("evidence_role") in ("buyer_acts", "buyer_articulates")})

    table = []
    for theme in topics.THEMES:
        s, b = len(seller.get(theme.key, ())), len(buyer.get(theme.key, ()))
        lic = composition.absence_licensing(theme.key, ic)
        if not theme.buyer_detectable or not lic["instruments"]:
            status = "NO INSTRUMENT"
        elif b:
            status = "covered"
            if lic["licensed"]:
                # Quick fix 2026-09-07: a covered theme with a licensed instrument shows
                # its §20.5 denominator on the table too, so the licensed-absence scope is
                # not visible only when the buyer count is zero.
                covered = licensed_absence_coverage(Path(args.db), set(lic["licensing"]))
                universe = buyer_universe(Path(args.db))
                status = f"covered ({len(covered)} of {universe} under a licensed instrument)"
        elif not lic["licensed"]:
            # Instruments see the theme but none may read its silence as absence: the
            # composition writes these buckets as `no_absence_license`, and this report
            # must say the same thing. Printing "buyer silent" here would be the absence
            # claim Signal Advisor's condition 1 forbids.
            status = "no absence license"
        else:
            covered = licensed_absence_coverage(Path(args.db), set(lic["licensing"]))
            universe = buyer_universe(Path(args.db))
            status = (f"buyer silent ({len(covered)} of {universe} under a licensed instrument)"
                      if covered else f"licensed instrument unpublished (0 of {universe})")
        table.append({
            "theme": theme.key,
            "providers_messaging": s,
            "provider_share": f"{s / n_providers:.0%}" if n_providers else "-",
            "buyer_companies": b,
            "buyer_detectable": theme.buyer_detectable,
            "status": status,
            "absence_licensing_instruments": ";".join(lic["licensing"]) or "",
            "presence_only_instruments": ";".join(lic["presence_only"]) or "",
            "low_grade_sellers": len(lg_seller.get(theme.key, set()) - seller.get(theme.key, set())),
            "low_grade_buyers": len(lg_buyer.get(theme.key, set()) - buyer.get(theme.key, set())),
        })

    w = max(len(t["theme"]) for t in table)
    print(f"Buyer signal vs provider messaging   "
          f"({n_providers} providers, {n_buyers} buyer companies)\n")
    print(f"  {'theme'.ljust(w)}  sellers  share  buyers  status                 low-grade only (S/B)")
    print(f"  {'-' * w}  -------  -----  ------  ---------------------  --------------------")
    for t in table:
        print(f"  {t['theme'].ljust(w)}  {t['providers_messaging']:7d}  "
              f"{t['provider_share']:>5}  {t['buyer_companies']:6d}  {t['status']:<21s}  "
              f"{t['low_grade_sellers']:>3d} / {t['low_grade_buyers']:<3d}")
    if quarantined:
        print(f"\n  {len(quarantined)} quarantined row(s) EXCLUDED (unaudited; the gate "
              f"says they count for nothing yet).")
    n_lg = len(low_grade)
    if n_lg:
        print(f"\n  {n_lg} low-grade row(s) {'INCLUDED in' if args.include_low_grade else 'EXCLUDED from'} "
              f"the counts above (grade C, '[low-grade:' excerpt; 2026-09-03 corroboration-gate policy). "
              f"The last column is companies/providers a theme would gain from low-grade rows alone.")

    print("\nreading the table")
    universal = [t for t in table if t["provider_share"] == "100%"]
    if universal:
        print(f"  * {len(universal)} theme(s) are messaged by EVERY provider "
              f"({', '.join(t['theme'] for t in universal)}). A theme every seller claims "
              f"cannot discriminate between them and is near-useless for positioning "
              f"analysis.")
    untested = [t for t in table if t["status"] == "no absence license" and t["providers_messaging"]]
    if untested:
        print(f"  * {len(untested)} theme(s) have provider messaging and no buyer signal, and "
              f"NO instrument that may read that silence as absence: "
              f"{', '.join(t['theme'] for t in untested)}. These are FORMALLY UNTESTED "
              f"(taxonomy §26) -- a gap in this portfolio, not a finding about buyers, and "
              f"not divergences. Company_State_History composes the same buckets as "
              f"`no_absence_license`. What would change it: an IC3/IC4 instrument that is "
              f"not presence-only reaching these themes (H-JOBPOST-01 once its readability "
              f"denominator is accepted; a state AG breach-portal harness for cybersecurity).")
    silent = [t for t in table if t["status"].startswith("buyer silent") and t["providers_messaging"]]
    if silent:
        print(f"  * {len(silent)} theme(s) have provider messaging and licensed silence: "
              f"{', '.join(t['theme'] for t in silent)}. An IC3/IC4 instrument that may read "
              f"absence reached them and found nothing. Still discounted by the source's "
              f"structural coverage (§20.5) before it is quoted as a divergence.")
    blind = [t for t in table if t["status"] == "NO INSTRUMENT" and t["providers_messaging"]]
    if blind:
        print(f"  * {len(blind)} theme(s) have provider messaging and NO buyer-side "
              f"instrument: {', '.join(t['theme'] for t in blind)}. Absence of buyer signal "
              f"here says nothing about buyers — it is a gap in this portfolio and must not "
              f"be written up as a divergence.")

    if unmapped_buyer:
        total = sum(len(v) for v in unmapped_buyer.values())
        print(f"\n  {len(unmapped_buyer)} buyer topic(s) carry no theme mapping "
              f"({total} company-observations). Most buyer evidence collected so far is "
              f"regulatory and is not about a modernization theme; it is left unmapped "
              f"rather than forced into one.")
        for topic, cids in sorted(unmapped_buyer.items(), key=lambda kv: -len(kv[1]))[:8]:
            print(f"      {topic:36s} {len(cids)} companies")

    if args.csv:
        out = Path(args.csv)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            wtr = csv.DictWriter(f, fieldnames=list(table[0]))
            wtr.writeheader()
            wtr.writerows(table)
        print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
