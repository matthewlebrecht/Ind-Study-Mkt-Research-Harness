"""
H-BREACHPORTAL-01 -- State AG breach-notification portals (the first IC4 instrument
for a modernization theme).

WHY
---
Every "buyer silent" reading in the portfolio rested on IC1/IC2 sources, which license no
negative inference (taxonomy §20.1), so no theme could carry a genuine absence. A state
attorney-general breach-notification list is involuntary disclosure: an organisation that
breached 500+ residents of that state and does not appear is breaking the law, not being
quiet. That makes its silence, for a company headquartered in the state, a licensed
absence -- `absent_confirmed` on the attempt, and `absence_licensed_IC4` in
core/composition.py, which lists this signal type as an instrument for `cybersecurity`
and nothing else.

SCOPE (session 16 scope check, 2026-09-06)
------------------------------------------
Portals with a searchable public list reachable from this network: California (DOJ) and
Washington (AG). Texas times out at the connection level, Maryland renders its list in
JavaScript, Vermont and Montana refuse this crawler by robots.txt, Massachusetts and New
Hampshire return 403, Iowa and Indiana publish year-by-year PDF lists this version does not
parse. So the licensed-absence population is the companies headquartered in CA or WA:
seven of 108. That is a handful and it is stated as one.

A portal lists every organisation that notified THAT state's residents wherever it is
based, so every buyer is searched against both portals for PRESENCE (recorded as an
incidental attempt when found); only in-state companies get a scoped attempt, and only
their empty result is an absence claim.

IDENTITY
--------
Same discipline as everywhere else. The CA filter is a substring search and WA is matched
locally, so every candidate row is scored by core.resolution.resolve against the company
name; below the floor is `entity_below_threshold`, not a hit, and a one-word name is never
matched on that word alone.

    python harnesses/h_breachportal_01/harness.py              # dry run
    python harnesses/h_breachportal_01/harness.py --commit
    python harnesses/h_breachportal_01/harness.py --offline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.cache import DatedCache, slug  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from core.resolution import WEAK_TOKENS, resolve, state_code, tokens  # noqa: E402
from core.robots import RobotsGate  # noqa: E402

HARNESS_ID = "H-BREACHPORTAL-01"
HARNESS_NAME = "State AG Breach-Notification Portal Reader"
VERSION = "v1.1"
SIGNAL = "state_ag_breach_notice"
FAMILY = "9_industrial_safety_environmental"
THEME = "cybersecurity"
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
UA = "Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; +independent study, contact via repo)"
TIMEOUT = 40

CA_LIST = "https://oag.ca.gov/privacy/databreach/list"
CA_EMPTY = "There are currently no published reported breaches."
WA_LIST = "https://www.atg.wa.gov/data-breach-notifications"
WA_MAX_PAGES = 80
PORTAL_STATES = {"CA": "California DOJ", "WA": "Washington AG"}


def strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return f"{r.status}\n" + r.read(1_500_000).decode("utf-8", "replace")


def unwrap(payload: str) -> tuple[int, str]:
    head, _, body = payload.partition("\n")
    try:
        return int(head), body
    except ValueError:
        return 0, payload


def distinctive(name: str) -> list[str]:
    return [t for t in tokens(name) if t.upper() not in WEAK_TOKENS and len(t) > 2]


def query_terms(name: str) -> list[str]:
    """Substring queries for the CA filter: the name minus legal suffixes, plus its first
    distinctive token when the name has two or more (so 'Devcon Construction' also finds
    'Devcon Construction Incorporated'). A single-token name is queried as itself only."""
    d = distinctive(name)
    out = [" ".join(d)] if d else [name]
    if len(d) >= 2 and len(d[0]) >= 5:
        out.append(d[0])
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------ California
def ca_rows(cache: DatedCache, term: str) -> tuple[list[dict], str, str]:
    """(rows, url, verdict) where verdict is 'rows' / 'empty' / 'unreadable'."""
    url = CA_LIST + "?" + urllib.parse.urlencode({"field_sb24_org_name_value": term})
    payload, _ = cache.get(slug(f"ca_{term}"), ".html", lambda: fetch(url))
    status, body = unwrap(payload)
    if status != 200:
        return [], url, f"unreadable: HTTP {status}"
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [strip(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 3 and cells[0]:
            rows.append({"org": cells[0], "breach_dates": cells[1], "reported": cells[2]})
    if rows:
        return rows, url, "rows"
    if CA_EMPTY in body and f'value="{term}"' in body:
        return [], url, "empty"
    return [], url, "unreadable: neither a table nor the empty-result marker"


# ------------------------------------------------------------------ Washington
def wa_all_rows(cache: DatedCache) -> tuple[list[dict], list[str]]:
    """Every notification on the WA list, walking the pager until a page has no rows."""
    rows, problems = [], []
    for page in range(WA_MAX_PAGES):
        url = WA_LIST + (f"?page={page}" if page else "")
        try:
            payload, _ = cache.get(f"wa_page_{page:03d}", ".html", lambda u=url: fetch(u))
        except RuntimeError as e:                       # offline, nothing archived
            problems.append(f"page {page}: {e}")
            break
        status, body = unwrap(payload)
        if status != 200:
            problems.append(f"page {page}: HTTP {status}")
            break
        page_rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [strip(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) >= 4 and cells[1]:
                page_rows.append({"reported": cells[0], "org": cells[1], "breach_dates": cells[2],
                                  "affected": cells[3], "info": cells[4] if len(cells) > 4 else "",
                                  "url": url})
        if not page_rows:
            break
        rows.extend(page_rows)
    return rows, problems


# ------------------------------------------------------------------ matching
GENERIC_ORG_WORDS = {"INTERNATIONAL", "COMPANY", "COMPANIES", "THE", "USA", "US", "NORTH",
                     "AMERICA", "AMERICAN", "HOLDINGS", "GROUP", "ENTERPRISES", "INCORPORATED"}


def strict_match(name: str, org: str) -> bool:
    """H-FIRSTPARTY-01's all-token rule, applied to a listed organisation name.

    Every distinctive token of the company name must appear in the listing (prefix match,
    so 'Whiting' finds 'Whiting-Turner'), and whatever the listing adds must be a legal
    suffix or a generic organisation word. One shared token is never an identity: the
    first dry run matched 'Kimberly-Clark Corporation' to Clark Construction, 'Petersen
    International Underwriters' to Petersen Inc., 'Urology Austin' to Austin Industries,
    'Summit Financial Group' to Summit Contracting and 'PLS Financial Services' to PLS
    Logistics, each on the one word they share (convention 31). A 'dba' clause is split
    and each half tested, so 'Lasership Inc. dba OnTrac Final Mile' still finds OnTrac.
    """
    comp = [t.upper() for t in distinctive(name)]
    if not comp:
        return False
    parts = re.split(r"\s+(?:dba|d/b/a|doing business as)\s+|\(|\)|\s+aka\s+", org, flags=re.I)
    for part in parts:
        cand = [t.upper() for t in tokens(part)]
        if not cand:
            continue
        if not all(any(c == k or c.startswith(k) or k.startswith(c) for c in cand) for k in comp):
            continue
        extras = [c for c in cand if not any(c == k or c.startswith(k) or k.startswith(c) for k in comp)]
        if all(e in WEAK_TOKENS or e in GENERIC_ORG_WORDS or len(e) <= 2 for e in extras):
            return True
    return False


def match(name: str, candidates: list[dict]):
    """Candidates that pass the all-token rule, then scored by core.resolution.resolve so
    the log carries a score and a refusal reason for everything considered."""
    d = {t.upper() for t in distinctive(name)}
    pool = [c for c in candidates if d & {t.upper() for t in tokens(c["org"])}] if d else []
    strict = [c for c in pool if strict_match(name, c["org"])]
    res = resolve(name, strict, name_of=lambda c: c["org"])
    dropped = [c["org"] for c in pool if c not in strict]
    if dropped:
        res.note = (res.note + " | " if res.note else "") + \
            f"{len(dropped)} candidate(s) failed the all-token rule: {dropped[:4]}"
    return res


def build(company: dict, state: str, hit: dict, url: str, score: float, stamp: str) -> Observation:
    name = company["canonical_name"]
    portal = PORTAL_STATES[state]
    extra = f", {hit['affected']} residents affected" if hit.get("affected") else ""
    text = (f"{name} appears in the {portal} breach-notification list as \"{hit['org']}\": "
            f"breach date(s) {hit.get('breach_dates') or 'n/a'}, reported {hit.get('reported') or 'n/a'}"
            f"{extra}. An involuntary regulatory disclosure (IC4) that a security incident "
            f"occurred and was notified; it records the incident, not the company's security "
            f"posture or modernization state.")
    excerpt = " | ".join(f"{k}: {v}" for k, v in hit.items() if k != "url" and v)
    excerpt += f" | matched: {hit['org']}"
    return Observation(
        company_id=company["company_id"], evidence_family=FAMILY, evidence_role="buyer_acts",
        topic=THEME, organizational_state="unknown", signal_strength="measured_result",
        observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url,
        publication_date=_iso(hit.get("reported")), retrieval_date=stamp, source_grade="A",
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=round(min(0.95, score), 2))


def _iso(d: str | None) -> str:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(d or ""))
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=f"{HARNESS_ID} -- {HARNESS_NAME}")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--companies")
    args = ap.parse_args()

    db = MarketIntelDB()
    buyers = [c for c in db.companies() if c.get("qualification_status") != "provider_benchmark"]
    if args.companies:
        want = {x.strip() for x in args.companies.split(",")}
        buyers = [c for c in buyers if c["company_id"] in want]
    for c in buyers:
        c["_state"] = state_code(str(c.get("hq_state") or ""))
    scoped = [c for c in buyers if c["_state"] in PORTAL_STATES]
    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=1.0)
    gate = RobotsGate()
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=FAMILY, scope=[(c["company_id"], SIGNAL) for c in scoped],
                      signal_families={SIGNAL: FAMILY}, commit=args.commit)
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp, "offline": args.offline,
           "portals": {}, "scoped": [c["company_id"] for c in scoped], "companies": []}
    print(f"{HARNESS_ID} {VERSION} -- {len(buyers)} buyers searched for presence, "
          f"{len(scoped)} in-scope for licensed absence "
          f"({', '.join(f'{s} {sum(1 for c in scoped if c['_state'] == s)}' for s in PORTAL_STATES)})"
          f" ({'offline' if args.offline else 'live'})\n")

    # ---- portal access ----
    access = {}
    for st, url in (("CA", CA_LIST), ("WA", WA_LIST)):
        ok, why = gate.check(url) if not args.offline else (True, "")
        access[st] = (ok, why)
        log["portals"][st] = {"url": url, "robots_ok": ok, "robots_reason": why}
        print(f"  portal {st}: {'permitted' if ok else 'ROBOTS REFUSED: ' + why}")
    wa_rows, wa_problems = ([], ["robots"]) if not access["WA"][0] else wa_all_rows(cache)
    log["portals"]["WA"].update({"rows": len(wa_rows), "problems": wa_problems})
    print(f"  WA list: {len(wa_rows)} notification(s) read" + (f"; problems {wa_problems}" if wa_problems else ""))

    proposed: list[Observation] = []
    for c in sorted(buyers, key=lambda x: x["company_id"]):
        cid, name, st = c["company_id"], c["canonical_name"], c["_state"]
        entry = {"company_id": cid, "name": name, "hq_state": st, "scoped": st in PORTAL_STATES,
                 "ca": {}, "wa": {}, "rows": 0}
        found: list[tuple[str, dict, str, float]] = []
        # -- California: filtered query per term
        if access["CA"][0]:
            verdicts = []
            for term in query_terms(name):
                try:
                    rows, url, verdict = ca_rows(cache, term)
                except Exception as e:                       # network / offline miss
                    rows, url, verdict = [], CA_LIST, f"unreadable: {type(e).__name__}: {e}"[:160]
                res = match(name, rows)
                verdicts.append({"term": term, "verdict": verdict, "candidates": len(rows),
                                 "resolution": res.as_log()})
                if res.resolved:
                    # v1.1: two query terms for one company ("ESTES EXPRESS LINES" and
                    # "ESTES") return the same listing; one incident is one row. Keyed on
                    # the listing's own identity -- org, breach date(s), reported date.
                    hit = res.winner.payload
                    key = (hit["org"], hit.get("breach_dates"), hit.get("reported"))
                    if key not in {(h["org"], h.get("breach_dates"), h.get("reported"))
                                   for s, h, _, _ in found if s == "CA"}:
                        found.append(("CA", hit, url, res.winner.score))
            entry["ca"] = {"queries": verdicts,
                           "read": all(v["verdict"] in ("rows", "empty") for v in verdicts)}
        # -- Washington: local match over the whole list
        if wa_rows:
            res = match(name, wa_rows)
            entry["wa"] = {"resolution": res.as_log(), "read": not wa_problems}
            if res.resolved:
                found.append(("WA", res.winner.payload, res.winner.payload.get("url", WA_LIST),
                              res.winner.score))
        else:
            entry["wa"] = {"read": False, "problems": wa_problems}

        rows = [build(c, s, hit, url, score, stamp) for s, hit, url, score in found]
        proposed.extend(rows)
        entry["rows"] = len(rows)
        # -- attempts: scoped in-state companies claim absence; others only presence
        own_read = (entry["ca"].get("read") if st == "CA" else entry["wa"].get("read")) if st in PORTAL_STATES else None
        own_hits = [r for r in found if r[0] == st]
        if st in PORTAL_STATES:
            if own_hits:
                run.attempt(cid, SIGNAL, outcome="covered", records_written=len(own_hits),
                            source_url_attempted=own_hits[0][2],
                            candidates_evaluated=sum(v["candidates"] for v in entry["ca"].get("queries", [])) if st == "CA" else len(wa_rows))
                mark = "!!"
            elif own_read:
                run.attempt(cid, SIGNAL, outcome="absent_confirmed",
                            source_url_attempted=CA_LIST if st == "CA" else WA_LIST,
                            candidates_evaluated=sum(v["candidates"] for v in entry["ca"].get("queries", [])) if st == "CA" else len(wa_rows),
                            candidates_discarded=sum(v["candidates"] for v in entry["ca"].get("queries", [])) if st == "CA" else 0)
                mark = "00"
            else:
                blocked = not access[st][0]
                run.attempt(cid, SIGNAL, outcome="not_covered", failure_stage="fetch",
                            failure_category="access_blocked" if blocked else "source_unavailable",
                            fix_class="source_limitation" if blocked else "transient",
                            failure_detail=(access[st][1] if blocked else
                                            f"{PORTAL_STATES[st]} list could not be read: "
                                            + json.dumps(entry["ca"].get("queries") or entry["wa"].get("problems"), default=str)[:300]),
                            source_url_attempted=CA_LIST if st == "CA" else WA_LIST)
                mark = "--"
            other_hits = [r for r in found if r[0] != st]
            if other_hits:
                run.attempt(cid, SIGNAL, outcome="covered", scope="incidental",
                            records_written=len(other_hits), source_url_attempted=other_hits[0][2])
        else:
            mark = "!!" if found else ".."
            if found:
                run.attempt(cid, SIGNAL, outcome="covered", scope="incidental",
                            records_written=len(found), source_url_attempted=found[0][2])
        if mark != "..":
            print(f"  [{mark}] {cid} {name} ({st or '??'}): "
                  + (f"{len(found)} listing(s): " + "; ".join(f"{s} '{h['org']}'" for s, h, _, _ in found)
                     if found else "no listing" + (" -- licensed absence" if mark == "00" else "")))
        log["companies"].append(entry)

    report = db.sync_observations(proposed)
    run.observations_written = report.written
    summary = run.close()
    n_abs = summary["attempts_absent_confirmed"]
    print(f"\n  {len(buyers)} buyers searched, {len(scoped)} scoped - {len(proposed)} observations")
    print(f"  scoped outcomes: {summary['attempts_covered']} covered, {n_abs} absent_confirmed "
          f"(licensed absence), {summary['attempts_not_covered']} not_covered")
    print(f"  dedupe: {report.summary()}")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")
    log["summary"] = summary
    log["dedupe"] = report.summary()
    log["held"] = report.conflicts
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
