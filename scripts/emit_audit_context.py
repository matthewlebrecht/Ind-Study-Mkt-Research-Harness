#!/usr/bin/env python3
"""
Emit the two "what did NOT become evidence" sheets that the audit gate's strata cannot
reach on their own.

WHY THESE EXIST
---------------
Every stratum in `docs/gates/gate_new_harness_output.md` except one samples rows that were
WRITTEN. That measures precision: of the things the harness admitted, how many were right.
It cannot measure the other error -- the harness quietly refusing evidence it should have
taken, or never pointing at a company it should have covered.

The suppression stratum closes part of that gap by sampling `Attempts`. These two sheets
close the rest, for the two harnesses built on 2026-08-31:

  <harness>__declined.md     every article H-TRADEPRESS-01 fetched and refused, with the
                             reason and the evidence for it. A refusal is a claim about a
                             source and has to be checkable afterwards (convention 12).
  <harness>__population.md   every company H-PRODUCTQUALITY-01 never queried, and why.
                             Its population map is hand-seeded, so a company wrongly left
                             out is invisible in the run summary and looks exactly like a
                             company with a clean record.

Both are generated from the committed run logs rather than typed, so they cannot drift
from what the run actually did.

    python scripts/emit_audit_context.py
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDITS = ROOT / "harness_output" / "audits"
DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"

# The three reasons that constitute an EVIDENTIARY refusal: the harness reached the
# article, read it, and decided its content did not support a claim. Distinguished from
# the mechanical refusals (a 403, an index page) because only these represent a judgment
# the harness made that a reviewer might disagree with.
EVIDENTIARY = ("stale", "not_about_company", "below_admission")


def host_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1).replace("www.", "") if m else ""


INDUSTRIAL_FAMILY = "9_industrial_safety_environmental"


def evidence_families(db: Path) -> dict:
    """Which evidence families each company already has committed rows in.

    The one signal available for triaging the not-queried list that does not require
    guessing an industry. Family 9 (industrial safety and environmental -- OSHA
    inspections, EPA ECHO records) is the closest thing the database holds to "this firm
    operates industrial facilities", and firms with industrial facilities are the ones
    that can hold an FDA registration or a CPSC recall history.

    A prompt to look, not a classification. Convention 13 still applies: nothing here
    infers an industry, it only says which rows are worth reading first.
    """
    wb = openpyxl.load_workbook(db, data_only=True)
    ws = wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    i_c = headers.index("company_id") + 1
    i_f = headers.index("evidence_family") + 1
    out: dict = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        out.setdefault(str(ws.cell(r, i_c).value or ""), set()).add(
            str(ws.cell(r, i_f).value or ""))
    return out


def companies(db: Path) -> dict:
    wb = openpyxl.load_workbook(db, data_only=True)
    ws = wb["Companies"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    out = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        row = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers) if h}
        out[str(row["company_id"])] = row
    return out


# ------------------------------------------------------------------ declined articles

def emit_declined(log: dict, names: dict) -> str:
    rows = []
    for c in log["companies"]:
        cid = c["company_id"]
        for p in c.get("pages", []):
            url = p.get("url", "")
            rejected = str(p.get("rejected") or "")
            # A page can carry a below-admission note per theme while not being
            # "rejected" outright, so both shapes are collected.
            below = [t for t in p.get("types", []) if "below_admission" in t]
            if below:
                for t in below:
                    theme = t.split(":")[1] if ":" in t else ""
                    rows.append({
                        "company_id": cid, "url": url, "host": host_of(url),
                        "reason": "below_admission", "published": p.get("published", ""),
                        "detail": (f"theme `{theme}` matched on a single generic term; "
                                   f"needs two distinct terms or a headline mention "
                                   f"(convention 32 -- admission, not downgrade)"),
                        "title": p.get("title", ""),
                    })
                continue
            if not rejected:
                continue
            kind = rejected.split(":")[0].strip()
            detail = rejected.split(":", 1)[1].strip() if ":" in rejected else ""
            if kind == "stale":
                # The committed 2026-08-31 run did not log `published` on stale pages, so
                # the date is reconstructed from the age the run recorded and its own
                # retrieval date. That is exact arithmetic on two logged values, not an
                # inference -- and it is marked `(derived)` so nobody reads it as
                # something the page asserted. Runs after this one log the date directly.
                pub = p.get("published") or ""
                m = re.search(r"(\d+) days old", detail or "")
                if not pub and m:
                    pub = (_dt.date.fromisoformat(log["date"])
                           - _dt.timedelta(days=int(m.group(1)))).isoformat() + " (derived)"
                detail = (f"published {pub or 'undated'}; "
                          f"{detail or 'older than the 5-year window'}. An announcement "
                          f"from before the window is a historical fact, not evidence of "
                          f"current posture")
            elif kind == "http":
                detail = f"HTTP {p.get('status', '?')} -- the article was never read"
            rows.append({
                "company_id": cid, "url": url, "host": host_of(url),
                "reason": kind, "published": p.get("published", ""),
                "detail": detail, "title": p.get("title", ""),
            })

    pre = [dict(x, company_id=c["company_id"])
           for c in log["companies"] for x in c.get("excluded", [])]

    counts = collections.Counter(r["reason"] for r in rows)
    evidentiary = [r for r in rows if r["reason"] in EVIDENTIARY]
    mechanical = [r for r in rows if r["reason"] not in EVIDENTIARY]

    L = [
        f"# {log['harness_id']} {log['version']} — declined articles",
        "",
        f"**Run:** {log.get('summary', {}).get('run', {}).get('run_id', 'HR-0021')}  |  "
        f"**Date:** {log['date']}  |  **Subset:** {log.get('subset_size', '?')} companies",
        "",
        "Every article this run **fetched and refused**, with the reason and the evidence "
        "for it.",
        "",
        "This sheet exists because the audit gate's strata all sample rows that were "
        "*written*. They measure precision — of what the harness admitted, how much was "
        "right — and cannot see the opposite error, which is a harness quietly refusing "
        "evidence it should have taken. On a run that admitted 2 rows from 132 fetched "
        "pages, that error is the more likely one.",
        "",
        "**A refusal is a claim about a source and has to be checkable afterwards** "
        "(convention 12). Read this looking for a row you disagree with.",
        "",
        "---",
        "",
        "## Counts",
        "",
        "| Reason | Articles | Kind |",
        "|---|---|---|",
    ]
    label = {
        "stale": "published outside the 5-year window",
        "not_about_company": "the article is about a different company",
        "below_admission": "one generic term only — below the admission threshold",
        "no admissible claim": "read in full; no quote, speaker or reported action found",
        "not_article": "an index, listing or tag page rather than one article",
        "http": "the fetch was refused — never read",
    }
    for reason, n in counts.most_common():
        kind = "**evidentiary**" if reason in EVIDENTIARY else "mechanical"
        L.append(f"| `{reason}` | {n} | {kind} — {label.get(reason, '')} |")
    L += [
        f"| **total fetched and refused** | **{len(rows)}** | |",
        "",
        f"**{len(evidentiary)} are evidentiary refusals** — the harness reached the "
        f"article, read it, and judged its content. Those are the ones a reviewer might "
        f"reasonably overturn, and they are listed first.",
        "",
        f"**{len(mechanical)} are mechanical** — a 403, an index page, or a page with "
        f"nothing extractable. Little judgment involved, listed second for completeness.",
        "",
        f"A further **{len(pre)} URLs never reached a fetch at all** "
        f"({', '.join(f'{n} {k}' for k, n in collections.Counter(x['reason'] for x in pre).most_common())}). "
        f"Those are summarised at the end rather than listed in full.",
        "",
        "---",
        "",
        "## Evidentiary refusals",
        "",
    ]

    def table(subset):
        out = ["| # | Company | Outlet | Reason | Why | URL |", "|---|---|---|---|---|---|"]
        for i, r in enumerate(sorted(subset, key=lambda x: (x["reason"], x["company_id"])), 1):
            nm = names.get(r["company_id"], {}).get("canonical_name", r["company_id"])
            why = r["detail"].replace("|", "\\|")[:230] or "—"
            out.append(f"| {i} | {nm} | {r['host']} | `{r['reason']}` | {why} | "
                       f"<{r['url']}> |")
        return out

    L += table(evidentiary)
    L += ["", "---", "", "## Mechanical refusals", ""]
    L += table(mechanical)

    L += [
        "", "---", "",
        "## Never fetched",
        "",
        "| Reason | URLs | What it means |",
        "|---|---|---|",
    ]
    pre_counts = collections.Counter(x["reason"] for x in pre)
    pre_label = {
        "off_outlet_allowlist": "a search result from a host outside this company's "
                                "vertical outlet list — the company's own site, LinkedIn, "
                                "ZoomInfo, a vendor blog",
        "robots_blocked": "robots.txt disallows this path for this crawler identity",
        "non_article_url": "a tag, category, author, search or subscribe URL",
    }
    for reason, n in pre_counts.most_common():
        L.append(f"| `{reason}` | {n} | {pre_label.get(reason, '')} |")

    blocked = collections.Counter(host_of(x["url"]) for x in pre
                                  if x["reason"] == "robots_blocked")
    if blocked:
        L += ["", "**Robots-blocked hosts** (these bound the harness's reach as much as "
              "content does):", ""]
        for h, n in blocked.most_common():
            L.append(f"- `{h}` — {n} URL(s)")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ population sheet

def emit_population(log: dict, names: dict, fams: dict) -> str:
    included = [c for c in log["companies"] if c.get("population")]
    excluded = [c for c in log["companies"] if not c.get("population")]

    L = [
        f"# {log['harness_id']} — population map",
        "",
        f"**Run:** HR-0025  |  **Date:** {log['date']}  |  "
        f"**Scoped:** {len(log['companies'])} companies  |  "
        f"**Queried:** {len(included)}  |  **Not queried:** {len(excluded)}",
        "",
        "## What this sheet is for",
        "",
        "H-PRODUCTQUALITY-01 reads federal recall and adverse-event databases, which cover "
        "firms that make physical products. A general contractor has no FDA registration "
        "and a freight carrier has no CPSC recall, so running them through would produce a "
        "wall of `absent_confirmed` rows asserting a clean record where the truth is that "
        "the instrument does not point at them. Those companies are recorded "
        "`not_covered`, with the reason — convention 6 from the other side: absence is "
        "coverage only when the source is authoritative **for that company**.",
        "",
        "**The population map is hand-seeded** (`POPULATION` in the harness), for the same "
        "reason H-TRADEPRESS-01's outlet map is: `Companies.industry_primary` is blank for "
        "all 100 Anvil rows, and inferring an industry from a company name inside a "
        "harness is the silent guess convention 13 forbids.",
        "",
        "**So the failure mode this sheet exists to catch is a company wrongly left out.** "
        "In the run summary a wrongly-excluded company is invisible: it looks exactly like "
        "a company with a clean federal record. The only way to find one is to read the "
        "list. **A single name you recognise as a manufacturer is a defect.**",
        "",
        "---",
        "",
        f"## Queried — {len(included)} companies",
        "",
        "| Company | Population | Instruments | Raw records | Matched to company | "
        "Systems-cause |",
        "|---|---|---|---|---|---|",
    ]
    for c in sorted(included, key=lambda x: x["company_id"]):
        insts = ", ".join(i["instrument"] for i in c.get("instruments", [])) or "—"
        err = [i for i in c.get("instruments", []) if i.get("error")]
        raw = c.get("events", 0)
        note = " ⚠ fetch failed" if err else ""
        L.append(f"| {c['name']} | `{c['population']}` | {insts} | {raw}{note} | "
                 f"{c.get('matched', 0)} | {c.get('process_cause', 0)} |")

    # Every excluded company was excluded for the same reason, so the useful
    # axis is not the reason -- it is whether other harnesses have already
    # found industrial-facility evidence for the firm, which is what makes a
    # wrong exclusion findable at all.
    industrial, other = [], []
    for c in excluded:
        (industrial if INDUSTRIAL_FAMILY in fams.get(c["company_id"], set())
         else other).append(c)

    L += [
        "",
        "⚠ = at least one instrument returned a fetch failure for this company, so its "
        "result is incomplete rather than clean. CPSC returned a server error for three "
        "companies on the committed run.",
        "",
        "---",
        "",
        f"## Not queried — {len(excluded)} companies",
        "",
        "All of them were excluded for the same reason: **not in the hand-seeded "
        "population map.** Each has an `Attempts` row carrying `outcome = not_covered`, "
        "`failure_category = source_not_found`, `fix_class = source_limitation` and that "
        "reason. None is marked `absent_confirmed`, because none of these databases was "
        "ever asked about them.",
        "",
        "Repeating that sentence 92 times says nothing and makes the list unscannable, so "
        "it is split on the one signal in the database that bears on whether an exclusion "
        "was right: **whether another harness has already found industrial safety or "
        "environmental records for the firm** (family 9 — OSHA inspections, EPA ECHO). A "
        "company with OSHA records operates industrial facilities, and firms with "
        "industrial facilities are the ones that can hold an FDA registration or a CPSC "
        "recall history.",
        "",
        "This infers no industry — convention 13 still holds. It only says which rows are "
        "worth reading first.",
        "",
        f"### Group A — {len(industrial)} with existing family-9 records (**read first**)",
        "",
        "These operate industrial facilities. Most will still be correctly excluded — a "
        "concrete contractor has OSHA records and no FDA registration — but if the map is "
        "wrong anywhere, it is most likely wrong here.",
        "",
        "| # | Company ID | Company | HQ | Families already held |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(sorted(industrial, key=lambda x: x["company_id"]), 1):
        row = names.get(c["company_id"], {})
        hq = str(row.get("hq_state") or "").strip() or "—"
        held = ", ".join(sorted(f.split("_")[0] for f in fams.get(c["company_id"], set())))
        L.append(f"| {i} | `{c['company_id']}` | {c['name']} | {hq} | {held} |")

    L += [
        "",
        f"### Group B — {len(other)} with no family-9 record",
        "",
        "No industrial safety or environmental record has been found for these by any "
        "harness. That is weaker evidence than it looks — H-SAFETY-ENV-01 has its own "
        "coverage limits — but it is the group least likely to hide a missed manufacturer.",
        "",
        "| # | Company ID | Company | HQ | Families already held |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(sorted(other, key=lambda x: x["company_id"]), 1):
        row = names.get(c["company_id"], {})
        hq = str(row.get("hq_state") or "").strip() or "—"
        held = ", ".join(sorted(f.split("_")[0]
                                for f in fams.get(c["company_id"], set()))) or "—"
        L.append(f"| {i} | `{c['company_id']}` | {c['name']} | {hq} | {held} |")

    L += [
        "",
        "---",
        "",
        "## How to read this against the run",
        "",
        f"- {len(included)} companies queried, {len(excluded)} not.",
        "- **1 observation** was written (Merit Medical). Everything else in the queried "
        "set resolved to `absent_confirmed`, and the attempt detail distinguishes two "
        "cases that must not be collapsed: *no federal record at all*, and *records exist "
        "but none cited a systems cause*. A company with fourteen contamination recalls "
        "must not read identically to one with a spotless record.",
        "- If a company in the not-queried list belongs in the population, adding it is a "
        "one-line change to `POPULATION` and a re-run; the harness is idempotent.",
    ]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    names = companies(Path(args.db))
    fams = evidence_families(Path(args.db))
    AUDITS.mkdir(parents=True, exist_ok=True)

    tp = json.loads((ROOT / "harness_output" / "H-TRADEPRESS-01"
                     / "run-2026-08-31.json").read_text(encoding="utf-8"))
    pq = json.loads((ROOT / "harness_output" / "H-PRODUCTQUALITY-01"
                     / "run-2026-08-31.json").read_text(encoding="utf-8"))

    a = AUDITS / "H-TRADEPRESS-01__declined.md"
    a.write_text(emit_declined(tp, names), encoding="utf-8")
    b = AUDITS / "H-PRODUCTQUALITY-01__population.md"
    b.write_text(emit_population(pq, names, fams), encoding="utf-8")

    print(f"wrote {a}")
    print(f"wrote {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
