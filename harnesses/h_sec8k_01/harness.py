"""
H-SEC8K-01 -- Form 8-K Item 1.05 material cybersecurity incident disclosures (IC4, cybersecurity).

WHAT IT READS AND FOR WHOM
--------------------------
Since 2023-12-18 an SEC reporting company must file a Form 8-K under Item 1.05 within four
business days of determining that a cybersecurity incident is material. The obligation attaches
to Exchange Act REPORTING STATUS, not to "public or private" ownership, so the scope is DERIVED
from `SEC_Reporting_Status_History` (core/sec_status.py::active_reporters: the latest
non-superseded row per company with status `active_reporter`) and from nothing else. No
`Companies.public_private` column exists or is consulted. Scoped narrowly first, per the
session 17 wrap-up brief: three companies today. Near-zero yield is the expected, documented
consequence of the population's reporting-status mix (most of the 108 are not SEC reporters),
not a harness defect to debug.

For each scoped company the harness reads the filer's EDGAR submissions record
(data.sec.gov/submissions/CIK##########.json, plus older index pages when the recent list does
not reach back to 2023-12-18) and takes every 8-K / 8-K/A filed on or after 2023-12-18 whose
item list includes 1.05. The item list is EDGAR's own structured field ("1.05,9.01"), matched
as an exact item code, never as a substring.

WHAT A ROW AND AN ABSENCE MEAN
------------------------------
A filing writes `cybersecurity` / `buyer_acts` / `measured_result` / grade A / state `unknown`:
an involuntary disclosure (IC4) that a MATERIAL incident occurred, nothing about the company's
security posture. A scoped company with no such filing is `absent_confirmed` -- a licensed
absence for the theme, conditional on the materiality threshold (taxonomy §20.1, §26), which
core/composition.py reads as `absence_licensed_IC4` only once a run is audited and published.
A later Form 15 / 25 in the filer's record (SpartanNash deregistered 2025-10-02) is logged: the
status table, not this harness, decides who is in scope.

ACCESS
------
SEC fair-access policy: automated requests declare a contact in the User-Agent (`SEC_CONTACT_EMAIL`
in .env, required -- www.sec.gov answers undeclared tools with 403) and stay under 10 requests a
second. robots.txt is checked; responses are archived by date.

    python harnesses/h_sec8k_01/harness.py              # dry run
    python harnesses/h_sec8k_01/harness.py --commit
    python harnesses/h_sec8k_01/harness.py --offline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import sec_status  # noqa: E402
from core.cache import DatedCache  # noqa: E402
from core.config import require_key  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from core.robots import RobotsGate  # noqa: E402

HARNESS_ID = "H-SEC8K-01"
HARNESS_NAME = "SEC Form 8-K Item 1.05 Cybersecurity Incident Reader"
VERSION = "v1.1"
SIGNAL = "sec_8k_item_105_cybersecurity"
FAMILY = "1_first_party_strategy_governance"
THEME = "cybersecurity"
RULE_EFFECTIVE = "2023-12-18"
ITEM = "1.05"
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
SUBMISSIONS = "https://data.sec.gov/submissions/"
DEREGISTRATION_FORMS = ("15-12B", "15-12G", "15-15D", "15F-12B", "15F-12G", "15F-15D", "25", "25-NSE")


class SourceError(RuntimeError):
    def __init__(self, message, failure_category="source_unavailable", fix_class="transient"):
        super().__init__(message)
        self.failure_category = failure_category
        self.fix_class = fix_class


def user_agent() -> str:
    email = require_key("SEC_CONTACT_EMAIL", "SEC's fair-access policy requires a declared contact.")
    return f"IndStudy-MarketIntel {email}"


def cik_of(source_reference: str) -> str | None:
    m = re.search(r"\bCIK\s*0*(\d{1,10})\b", str(source_reference or ""), re.I)
    return m.group(1) if m else None


def has_item(items: str, item: str = ITEM) -> bool:
    """EDGAR's item list is comma-separated codes. Exact code match only: '1.05' is in
    '1.05,9.01' and not in '1.01' or '11.05'."""
    return item in [i.strip() for i in str(items or "").split(",")]


def rows_of(block: dict) -> list[dict]:
    """A submissions 'recent' block (or an older index page) as a list of filing dicts."""
    forms = block.get("form") or []
    out = []
    for i in range(len(forms)):
        out.append({k: (block.get(k) or [None] * len(forms))[i] for k in
                    ("form", "filingDate", "reportDate", "items", "accessionNumber", "primaryDocument")})
    return out


def needs_older_pages(recent: list[dict], since: str = RULE_EFFECTIVE) -> bool:
    """True when the recent list does not reach back to `since`, so older index pages must be read."""
    dates = [r["filingDate"] for r in recent if r.get("filingDate")]
    return not dates or min(dates) > since


def item105_filings(filings: list[dict], since: str = RULE_EFFECTIVE) -> list[dict]:
    return [f for f in filings if str(f.get("form") or "") in ("8-K", "8-K/A")
            and str(f.get("filingDate") or "") >= since and has_item(f.get("items"))]


def scoped_companies(status_rows: list[dict]) -> list[dict]:
    """Derived scope: current active reporters, each with its CIK. Never a stored flag."""
    current = sec_status.current_rows(status_rows)
    out = []
    for cid in sec_status.active_reporters(status_rows):
        out.append({"company_id": cid, "cik": cik_of(current[cid]["source_reference"]),
                    "status_row": current[cid]["id"], "as_of_date": current[cid]["as_of_date"]})
    return out


def fetch_json(cache: DatedCache, url: str, key: str, ua: str) -> dict:
    def fetch() -> str:
        for attempt in range(3):
            try:
                r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=60)
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    raise SourceError(f"{type(e).__name__}: {str(e)[:150]}")
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code in (401, 403):
                raise SourceError(f"HTTP {r.status_code} from SEC for {url} -- check SEC_CONTACT_EMAIL / fair-access policy",
                                  "access_blocked", "source_limitation")
            if r.status_code >= 400:
                raise SourceError(f"HTTP {r.status_code} from SEC for {url}")
            return r.text
        raise SourceError(f"SEC did not answer for {url}")
    payload, _ = cache.get(key, ".json", fetch)
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        raise SourceError(f"non-JSON answer for {url} -- a failure, never an empty filing list",
                          "source_drift_detected", "code_change")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=f"{HARNESS_ID} -- {HARNESS_NAME}")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = {c["company_id"]: c for c in db.companies()}
    scope = scoped_companies(db.sec_status_rows())
    stamp = today()
    ua = user_agent()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp, pause_seconds=0.15)
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION, primary_family=FAMILY,
                      scope=[(s["company_id"], SIGNAL) for s in scope], signal_families={SIGNAL: FAMILY},
                      commit=args.commit)
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp, "offline": args.offline,
           "rule_effective": RULE_EFFECTIVE, "scope_rule": "sec_status.active_reporters (derived)",
           "scope": scope, "companies": []}
    print(f"{HARNESS_ID} {VERSION} -- scope derived from SEC_Reporting_Status_History: {len(scope)} active "
          f"reporter(s) {[s['company_id'] for s in scope]} ({'offline' if args.offline else 'live'})\n")
    if not args.offline:
        ok, why = RobotsGate().check(SUBMISSIONS + "CIK0000000000.json")
        log["robots"] = {"ok": ok, "reason": why}
        if not ok:
            print(f"ROBOTS REFUSED: {why}")
            return 2

    proposed: list[Observation] = []
    for s in scope:
        cid, cik = s["company_id"], s["cik"]
        name = companies[cid]["canonical_name"]
        entry = {"company_id": cid, "name": name, "cik": cik}
        if not cik:
            run.attempt(cid, SIGNAL, outcome="not_covered", failure_stage="entity_resolution",
                        failure_category="entity_no_candidate", fix_class="code_change",
                        failure_detail=f"status row {s['status_row']} carries no CIK in source_reference")
            log["companies"].append(entry)
            continue
        url = f"{SUBMISSIONS}CIK{int(cik):010d}.json"
        try:
            sub = fetch_json(cache, url, f"submissions_CIK{int(cik):010d}", ua)
            filings = rows_of(sub.get("filings", {}).get("recent", {}))
            pages_read = []
            if needs_older_pages(filings):
                for f in sub.get("filings", {}).get("files", []) or []:
                    if str(f.get("filingTo") or "") >= RULE_EFFECTIVE:
                        older = fetch_json(cache, SUBMISSIONS + f["name"], f"page_{f['name']}", ua)
                        filings += rows_of(older)
                        pages_read.append(f["name"])
        except SourceError as e:
            run.attempt(cid, SIGNAL, outcome="not_covered", failure_stage="fetch", failure_category=e.failure_category,
                        fix_class=e.fix_class, failure_detail=str(e)[:500], source_url_attempted=url)
            entry["error"] = str(e)[:300]
            log["companies"].append(entry)
            print(f"  [--] {cid} {name}: {str(e)[:120]}")
            continue
        eightks = [f for f in filings if f.get("form") in ("8-K", "8-K/A") and str(f.get("filingDate") or "") >= RULE_EFFECTIVE]
        hits = item105_filings(filings)
        dereg = sorted({(f["form"], f["filingDate"]) for f in filings if f.get("form") in DEREGISTRATION_FORMS
                        and str(f.get("filingDate") or "") >= str(s["as_of_date"])})
        entry.update({"eightk_since_rule": len(eightks), "item_105": [f["accessionNumber"] for f in hits],
                      "older_pages_read": pages_read, "deregistration_after_status_as_of": dereg,
                      "oldest_filing_read": min((f["filingDate"] for f in filings if f.get("filingDate")), default=None)})
        for f in hits:
            acc = str(f["accessionNumber"])
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{f['primaryDocument']}"
            text = (f"{name} filed a Form {f['form']} on {f['filingDate']} reporting Item 1.05 (material "
                    f"cybersecurity incident). An involuntary disclosure (IC4) required of SEC reporting "
                    f"companies within four business days of determining materiality: it records that a "
                    f"material incident occurred, not the company's security posture or modernization state.")
            excerpt = f"EDGAR CIK {int(cik):010d}; accession {acc}; form {f['form']}; items {f['items']}; filed {f['filingDate']}"
            proposed.append(Observation(
                company_id=cid, evidence_family=FAMILY, evidence_role="buyer_acts", topic=THEME,
                organizational_state="unknown", signal_strength="measured_result", observation_text=text,
                evidence_excerpt=excerpt, source_url=doc_url, publication_date=f["filingDate"], retrieval_date=stamp,
                source_grade="A", harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=0.95))
        if hits:
            run.attempt(cid, SIGNAL, outcome="covered", records_written=len(hits), source_url_attempted=url,
                        candidates_evaluated=len(eightks))
            mark = "!!"
        else:
            run.attempt(cid, SIGNAL, outcome="absent_confirmed", source_url_attempted=url,
                        candidates_evaluated=len(eightks), candidates_discarded=len(eightks))
            mark = "00"
        note = f"; deregistration filed after the status as-of date: {dereg}" if dereg else ""
        print(f"  [{mark}] {cid} {name} (CIK {int(cik)}): {len(eightks)} 8-K(s) since {RULE_EFFECTIVE}, "
              f"{len(hits)} with Item 1.05{note}")
        log["companies"].append(entry)

    report = db.sync_observations(proposed)
    run.observations_written = report.written
    summary = run.close()
    print(f"\n  {len(scope)} scoped - {len(proposed)} observations - {cache.fetch_count} fetches")
    print(f"  attempts: {summary['attempts_covered']} covered, {summary['attempts_absent_confirmed']} absent_confirmed, "
          f"{summary['attempts_not_covered']} not_covered")
    print(f"  dedupe: {report.summary()}")
    log["summary"] = summary
    log["dedupe"] = report.summary()
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
