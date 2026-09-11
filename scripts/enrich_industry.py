#!/usr/bin/env python3
"""
Populate `Companies.industry_primary` from NAICS codes already in the archive.

    python scripts/enrich_industry.py            # report only
    python scripts/enrich_industry.py --apply    # write blank cells + industry_source

Session 15 item 2. The field was blank for all 100 Anvil rows, which is why H-TRADEPRESS-01
is hand-seeded to 15 companies: its outlet verticals are per company and the harness refuses
to guess an industry from a name (convention 13). This script does not guess either. It reads
NAICS codes off records another harness already attributed to the company under its own
identity gates:

  1. OSHA establishment inspections (H-SAFETY-ENV-01's archived search pages): the
     inspections whose establishment name matches the company's RESOLVED winner, each
     carrying a NAICS code. Modal sector wins if it holds >= 60% of the inspections;
     otherwise the company is AMBIGUOUS and stays blank, with the split reported.
  2. EPA ECHO facilities (same harness's archive) for companies OSHA did not resolve: the
     winner facility's FacNAICSCodes, same rule.
  3. H-FMCSA-01 as a last resort: a company resolved to a for-hire carrier of >= 100 power
     units is `trucking`. Private carriage says nothing about industry and is not used.

NAICS -> the industry vocabulary that H-TRADEPRESS-01's outlet map is keyed on. A code with
no mapping (professional services, retail, hospitality) is reported, not forced.

Existing values are never overwritten; `industry_source` records what each written value
rests on. Re-runnable.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cache import slug  # noqa: E402
from core.db import MarketIntelDB, today  # noqa: E402
from core.workbook_backup import backup_workbook  # noqa: E402
from harnesses.h_safety_env_01.source import SafetyEnvClient  # noqa: E402

SAFETY_RAW = ROOT / "harness_output" / "H-SAFETY-ENV-01" / "raw"
SAFETY_LOG = ROOT / "harness_output" / "H-SAFETY-ENV-01" / "run-2026-09-03.json"
FMCSA_LOG = ROOT / "harness_output" / "H-FMCSA-01" / "run-2026-09-03.json"
SHARE_FLOOR = 0.6
FMCSA_FLEET_FLOOR = 100

# longest prefix wins
NAICS_TO_INDUSTRY = [
    ("4244", "food"), ("4245", "food"), ("4248", "food"), ("4451", "food"), ("4452", "food"),
    ("311", "food"), ("312", "food"),
    ("339112", "medical"), ("339113", "medical"), ("339114", "medical"), ("339115", "medical"),
    ("3391", "medical"), ("3345", "medical"), ("6215", "medical"),
    ("4841", "trucking"), ("4842", "trucking"), ("484", "trucking"), ("4885", "trucking"),
    ("492", "trucking"),
    ("4931", "logistics"), ("4884", "logistics"), ("4889", "logistics"), ("488", "logistics"),
    ("42", "logistics"),
    ("2211", "energy"), ("2212", "energy"), ("2213", "energy"), ("211", "energy"),
    ("213", "energy"), ("3241", "energy"), ("562", "energy"),
    ("3256", "consumer"), ("4543", "consumer"), ("4541", "consumer"), ("3399", "consumer"),
    ("337", "consumer"), ("3152", "consumer"), ("3161", "consumer"),
    ("23", "construction"), ("5413", "construction"),
    ("31", "manufacturing"), ("32", "manufacturing"), ("33", "manufacturing"),
]
_SUFFIX = {"INC", "LLC", "CO", "COMPANY", "CORP", "CORPORATION", "LTD", "THE", "LP", "LLP",
           "INCORPORATED", "GROUP"}


def industry_of(naics: str) -> str | None:
    code = re.sub(r"\D", "", str(naics or ""))
    for prefix, ind in NAICS_TO_INDUSTRY:
        if code.startswith(prefix):
            return ind
    return None


def common_word_name(name: str) -> bool:
    """Does the company name reduce to one dictionary-word token? (convention 31)"""
    from core.resolution import WEAK_TOKENS, tokens
    from harnesses.h_firstparty_01.article import COMMON_WORD_NAMES
    distinct = [t for t in tokens(str(name or "")) if t not in WEAK_TOKENS]
    return len(distinct) == 1 and distinct[0].lower() in COMMON_WORD_NAMES


def norm(name: str) -> str:
    toks = re.sub(r"[^A-Z0-9 ]+", " ", str(name or "").upper()).split()
    return " ".join(t for t in toks if t not in _SUFFIX)


def newest(pattern: str) -> list[Path]:
    """Every archived file matching the pattern, newest partition first."""
    files = [Path(p) for p in glob.glob(str(SAFETY_RAW / "*" / pattern))]
    return sorted(files, key=lambda p: p.parent.name, reverse=True)


def osha_codes(entry: dict) -> tuple[list[str], str]:
    """NAICS codes of the inspections attributed to the company's OSHA winner."""
    res = (entry.get("resolution") or {}).get("osha") or {}
    if res.get("status") != "resolved":
        return [], ""
    variant, state, winner = entry.get("osha_variant_used"), entry.get("state"), res.get("winner")
    if not variant or not winner:
        return [], ""
    files = newest(f"{slug(f'osha_{variant}_{state}_2016')}*")
    if not files:
        return [], ""
    part = files[0].parent.name
    pages = [f for f in files if f.parent.name == part]
    seen, codes = set(), []
    w = norm(winner)
    for f in pages:
        try:
            insp, _ = SafetyEnvClient._parse_osha(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for i in insp:
            if i.activity_nr in seen:
                continue
            seen.add(i.activity_nr)
            if norm(i.establishment) == w and i.naics:
                codes.append(i.naics)
    return codes, f"OSHA establishment '{winner}' ({len(codes)} inspection(s), archive {part})"


def echo_codes(entry: dict) -> tuple[list[str], str]:
    res = (entry.get("resolution") or {}).get("echo") or {}
    if res.get("status") != "resolved":
        return [], ""
    variant, state, winner = entry.get("echo_variant_used"), entry.get("state"), res.get("winner")
    if not variant or not winner:
        return [], ""
    files = newest(f"{slug(f'echo_{variant}_{state}')}*") or newest(f"{slug(f'echo_{variant}')}*")
    if not files:
        return [], ""
    w = norm(winner)
    codes = []

    def walk(o):
        if isinstance(o, dict):
            if "FacName" in o and norm(o.get("FacName")) == w:
                for c in str(o.get("FacNAICSCodes") or "").replace(",", " ").split():
                    codes.append(c)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    try:
        walk(json.loads(files[0].read_text(encoding="utf-8")))
    except Exception:
        return [], ""
    return codes, f"EPA ECHO facility '{winner}' ({len(codes)} NAICS code(s), archive {files[0].parent.name})"


def decide(codes: list[str]) -> tuple[str | None, str]:
    """(industry or None, why)."""
    if not codes:
        return None, "no NAICS codes"
    inds = collections.Counter(industry_of(c) for c in codes)
    unmapped = inds.pop(None, 0)
    if not inds:
        return None, f"NAICS not in mapping: {sorted(set(codes))}"
    top, n = inds.most_common(1)[0]
    share = n / sum(inds.values())
    if share < SHARE_FLOOR:
        return None, f"ambiguous: {dict(inds)} (top share {share:.0%} < {SHARE_FLOOR:.0%})"
    detail = f"NAICS {collections.Counter(codes).most_common(1)[0][0]}"
    if len(set(codes)) > 1:
        detail += f" (codes {sorted(set(codes))})"
    if unmapped:
        detail += f"; {unmapped} unmapped code(s) ignored"
    return top, detail


def fmcsa_trucking() -> dict[str, str]:
    """company_id -> note, for companies resolved to a large for-hire carrier."""
    out = {}
    try:
        d = json.loads(FMCSA_LOG.read_text(encoding="utf-8"))
    except Exception:
        return out
    for e in d.get("resolution_log", []):
        if not e.get("resolved"):
            continue
        om = [o for o in e.get("observations", []) if o.get("topic") == "operating_model"]
        fs = [o for o in e.get("observations", []) if o.get("topic") == "fleet_scale"]
        text = " ".join(o.get("observation_text", "") for o in om + fs)
        m = re.search(r"fleet of ([\d,]+) power units", text)
        pu = int(m.group(1).replace(",", "")) if m else 0
        if "For Hire" in text and pu >= FMCSA_FLEET_FLOOR:
            out[e["company_id"]] = f"FMCSA: for-hire carrier, {pu:,} power units (run 2026-09-03)"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    log = json.loads(SAFETY_LOG.read_text(encoding="utf-8"))
    entries = {c["company_id"]: c for c in log["companies"]}
    trucking = fmcsa_trucking()

    db = MarketIntelDB()
    ws = db.wb["Companies"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    if "industry_source" not in headers:
        print("ABORT: Companies.industry_source missing; run scripts/migrate_schema.py --apply")
        return 1
    col = {h: i + 1 for i, h in enumerate(headers)}
    vocab = db.vocab.get("industry", set())

    results = []
    for r in range(2, ws.max_row + 1):
        cid = ws.cell(r, col["company_id"]).value
        if not cid or str(ws.cell(r, col["qualification_status"]).value) == "provider_benchmark":
            continue
        name = ws.cell(r, col["canonical_name"]).value
        existing = ws.cell(r, col["industry_primary"]).value
        if existing:
            results.append((cid, name, existing, "kept", "already set"))
            continue
        e = entries.get(str(cid), {})
        ind, why, src = None, "", ""
        codes, src = osha_codes(e)
        # Convention 31: a name that reduces to one dictionary word is never an identity
        # on its own. Prime Inc. resolved to an OSHA record "Prime Inc" carrying tire
        # retreading (326212) -- one record, a common word, and a carrier the SUBSET
        # already seeds as trucking. One or two records under such a name attribute
        # nothing here; three agreeing records would.
        if common_word_name(name) and len(codes) < 3:
            results.append((cid, name, None, "blank",
                            f"single common-word name with {len(codes)} record(s): not "
                            f"attributed (convention 31)"))
            continue
        if codes:
            ind, why = decide(codes)
            src = f"{src}: {why}"
        if ind is None:
            codes2, src2 = echo_codes(e)
            if codes2:
                ind2, why2 = decide(codes2)
                if ind2:
                    ind, why, src = ind2, why2, f"{src2}: {why2}"
                elif not src:
                    src = f"{src2}: {why2}"
        if ind is None and str(cid) in trucking:
            ind, src = "trucking", trucking[str(cid)]
        if ind and ind not in vocab:
            results.append((cid, name, None, "blocked", f"{ind!r} not in Lookups.industry; {src}"))
            continue
        if ind:
            results.append((cid, name, ind, "write", src))
            if args.apply:
                ws.cell(r, col["industry_primary"]).value = ind
                ws.cell(r, col["industry_source"]).value = f"{src}; session 15 {today()}"
        else:
            results.append((cid, name, None, "blank", src or "no OSHA / ECHO / FMCSA record attributed"))

    w = max(len(str(n)) for _, n, *_ in results)
    print(f"{'id':6} {'company':{w}}  {'industry':14} action   basis")
    for cid, name, ind, action, why in results:
        print(f"{cid:6} {str(name):{w}}  {str(ind or '-'):14} {action:8} {why[:110]}")
    counts = collections.Counter(a for *_, a, _ in results)
    print(f"\n{counts.get('write', 0)} to write, {counts.get('kept', 0)} already set, "
          f"{counts.get('blank', 0)} left blank, {counts.get('blocked', 0)} blocked on vocabulary")
    by_ind = collections.Counter(ind for _, _, ind, a, _ in results if a in ("write", "kept"))
    print("by industry:", dict(by_ind))
    if not args.apply:
        print("\nDRY RUN -- nothing written. Re-run with --apply.")
        return 0
    b, pruned = backup_workbook(db.path)
    db.save()
    print(f"\nwritten; backup {b.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
