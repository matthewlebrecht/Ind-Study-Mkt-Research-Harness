"""
Company_State_History derivation: the temporal schema's composition rule, as code.

WHAT THIS PRODUCES
------------------
One row per (company, theme, time bucket) stating what the project could say about that
company's modernization posture on that theme in that bucket, and -- more importantly --
what it could NOT say and why. The table is append-only and immutable: every derivation
writes a full new set of rows under a fresh `derivation_id`, and no row is ever updated.
Readers take the latest derivation. An earlier derivation stays on the sheet as the record
of what the project could see at that time.

THE COMPOSITION ORDER (week-3 package §4, taxonomy §21.3 / §25.2) -- load-bearing
--------------------------------------------------------------------------------
For a bucket T, in this order and stopping at the first gate that fails:

  1. DETECTABILITY  (capacity)  Was the theme instrumented by the START of T?
                                `Theme.buyer_detectable_since <= bucket_start`, else the
                                bucket is `theme_not_detectable`. Resolves by waiting.
  2. REACH          (capacity)  Did any instrument that can see the theme actually reach
                                this company in a way whose REALIZED reach covers T? Else
                                `no_reach`. Resolves by acquiring access.
  3. INSTRUMENT     (strength)  Only now: is there evidence (-> `observed`), and if not,
     CLASS                      does the class of a covering instrument license reading
                                the silence as absence (IC3/IC4 and not presence-only
                                -> `absent`), or not (-> `no_absence_license`)?

Null is not zero. A bucket that fails gate 1 or 2 carries no state and a reason; storing
it as an absence would manufacture the divergence pattern the project exists to detect.

THE TWO INVARIANTS THE CODE HAS TO KEEP, NOT JUST STATE
-------------------------------------------------------
* Composition reads `realized_reach` and nothing else from Harness_Sources. The string
  "nominal_reach" does not appear in this module's derivation path, and the schema-delta
  test greps for it.
* Every gating value a row was composed against is STAMPED onto the row: the theme's
  `definition_hash` and `buyer_detectable_since`, the weakest realized reach relied on
  (`min_retrospective_reach`), the instruments that covered. Nothing is joined live at
  read time, so a later change to Harness_Sources or to a theme definition is a visible
  difference between two derivations, never a silent rewrite of one.

WHAT "REACH COVERS T" MEANS HERE
--------------------------------
A source's realized reach is a property of the source; whether it reached THIS company is
the Attempts ledger. So an instrument covers bucket T for a company when one of its runs
recorded a coverage outcome (`covered` / `absent_confirmed` / `partial`) for that company
at retrieval time t, and the source's realized reach at t spans T:

    current_only   T contains t                (a snapshot speaks only to its own bucket)
    bounded (N)    t - N months <= T_end        (a rolling window ending at t)
    archival       T_start <= t                 (dated records back to the source's start)

and never to a bucket that starts after t.

with the reach in force only from `realized_reach_effective_from`. A released buyer
observation informs T on the same rule plus `publication_date <= T_end` and the five-year
staleness standard (core/windows.py).

WHICH INSTRUMENTS SEE THE THEMES
--------------------------------
Declared in THEME_INSTRUMENTS, not inferred from what happened to be written. The four
harnesses that classify buyer text through the theme spine or through explicit theme keys
are instruments for the themes. H-LEGAL-01 and H-PRODUCTQUALITY-01 occasionally route a
docket or recall to a theme; their rows count as presence when they exist, but neither is
an instrument for the themes' absence -- a federal docket does not systematically observe
modernization (taxonomy §20.5's worked example).

H-JOBPOST-01 is IC3, the class whose silence is supposed to carry weight, and it is the
portfolio's highest-risk composition (§21.3). Its keys are PRESENCE ONLY by Signal Advisor's
condition 1 until the careers-page readability denominator is accepted, so its silence
licenses nothing here regardless of class. That is a declared flag, not an inference, and
lifting it is a decision that produces a new derivation -- never an edit to an old one.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from core import topics
from core.attempts import COVERAGE_OUTCOMES
from core.windows import STALENESS_YEARS

DERIVATION_VERSION = "cs-1.0"
BUCKET_GRAIN = "week"            # ISO week, Monday .. Sunday

REACH_RANK = {"current_only": 0, "bounded": 1, "archival": 2}
BUYER_ROLES = {"buyer_acts", "buyer_articulates"}
ABSENCE_CLASSES = {"IC3", "IC4"}

STATUS_OBSERVED, STATUS_ABSENT, STATUS_NULL = "observed", "absent", "null"
REASON_OBSERVED = "observed"
REASON_NOT_DETECTABLE = "theme_not_detectable"
REASON_NO_REACH = "no_reach"
REASON_NO_LICENSE = "no_absence_license"
STATE_STATUSES = [STATUS_OBSERVED, STATUS_ABSENT, STATUS_NULL]
STATE_REASONS = [REASON_OBSERVED, "absence_licensed_IC3", "absence_licensed_IC4",
                 REASON_NO_LICENSE, REASON_NO_REACH, REASON_NOT_DETECTABLE]

# attempted_signal (as written to Attempts) -> (harness_id, which themes it can see).
# "all": classifies free text through the spine, so any theme. "keys": only the themes its
# signal keys map to in topics.BUYER_SIGNAL_TO_THEME.
THEME_INSTRUMENTS = {
    "first_party_announcement": ("H-FIRSTPARTY-01", "all"),
    "executive_public_statement": ("H-EXECVOICE-01", "all"),
    "exec_quote_reported": ("H-TRADEPRESS-01", "all"),
    "job_posting": ("H-JOBPOST-01", "keys"),
    "job_board_third_party": ("H-JOBPOST-01", "keys"),
    # Session 16: the first IC4 instrument for a modernization theme. A state AG breach
    # portal sees exactly one theme, and its silence for a company headquartered in the
    # portal's state IS licensed -- an organisation that breached 500+ residents of that
    # state and did not appear would be breaking the law, not being quiet.
    "state_ag_breach_notice": ("H-BREACHPORTAL-01", ["cybersecurity"]),
    # Session 17 wrap-up: Form 8-K Item 1.05, the IC4 instrument taxonomy §26 names for the
    # SEC-reporter subset. Scoped attempts exist only for companies whose CURRENT row in
    # SEC_Reporting_Status_History is active_reporter (derived, core/sec_status.py), so its
    # silence licenses absence for those companies and says nothing about the rest. Reads
    # nothing until a run is audited and published (attempts from published runs only).
    "sec_8k_item_105_cybersecurity": ("H-SEC8K-01", ["cybersecurity"]),
}
# Signal Advisor condition 1 (CLAUDE.md, "PRESENCE ONLY"): no absence claim from any
# H-JOBPOST-01 key until the careers-page readability denominator is accepted.
PRESENCE_ONLY_SIGNAL_TYPES = {"job_posting", "job_board_third_party"}

STATE_HISTORY_COLUMNS = [
    "state_id", "derivation_id", "derivation_version", "derived_at", "bucket_grain",
    "bucket_id", "bucket_start", "bucket_end", "company_id", "theme_id", "theme_key",
    "display_label", "definition_hash", "buyer_detectable_since", "status", "reason",
    "organizational_state", "min_retrospective_reach", "covering_instruments",
    "supporting_observation_ids", "evidence_count", "lowest_source_grade",
    "max_confidence", "staleness_years", "notes",
]


# ---------------------------------------------------------------------------------------
# inputs -- plain dicts so the derivation is testable without a workbook
# ---------------------------------------------------------------------------------------

@dataclass
class Inputs:
    companies: list                 # company_ids in scope (buyers only)
    attempts: list                  # dicts: harness_id, company_id, attempted_signal,
                                    #        outcome, scope, attempt_timestamp
    observations: list              # dicts: observation_id, company_id, harness_id,
                                    #        evidence_role, topic, publication_date,
                                    #        retrieval_date, organizational_state,
                                    #        source_grade, confidence_0_1,
                                    #        publication_state
    harness_reach: dict             # harness_id -> {"realized_reach", "realized_reach_months",
                                    #                "realized_reach_effective_from"}
    instrument_class: dict          # attempted_signal -> IC1..IC4
    themes: list = field(default_factory=lambda: list(topics.THEMES))
    invalid: dict = field(default_factory=dict)   # observation_id -> current validity_status (invalid rows only)


@dataclass
class Bucket:
    bucket_id: str
    start: _dt.date
    end: _dt.date


def _d(value) -> _dt.date | None:
    """Parse a date-ish cell. Unparseable -> None; the caller decides what that means."""
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            return _dt.datetime.strptime(s[:19] if "T" in s else s, fmt).date()
        except ValueError:
            continue
    return None


def week_buckets(start: _dt.date, end: _dt.date) -> list[Bucket]:
    """ISO weeks (Monday-start) covering start..end inclusive."""
    first = start - _dt.timedelta(days=start.weekday())
    out = []
    cur = first
    while cur <= end:
        iso = cur.isocalendar()
        out.append(Bucket(f"{iso[0]}-W{iso[1]:02d}", cur, cur + _dt.timedelta(days=6)))
        cur += _dt.timedelta(days=7)
    return out


def series_start(themes) -> _dt.date | None:
    """The series begins at the earliest date any theme became detectable. Buckets before
    that are excluded from the series rather than recorded (taxonomy §25.2)."""
    dates = [_d(t.buyer_detectable_since) for t in themes if t.buyer_detectable_since]
    return min(dates) if dates else None


def reach_covers(reach: dict, retrieved: _dt.date, bucket: Bucket) -> bool:
    """Does a source with this REALIZED reach, read at `retrieved`, speak to `bucket`?"""
    kind = str(reach.get("realized_reach") or "").strip()
    eff = _d(reach.get("realized_reach_effective_from"))
    if not kind or retrieved is None:
        return False
    if eff and retrieved < eff:
        return False
    # A read at t speaks to the bucket in progress at t (up to t) and, for bounded and
    # archival sources, to earlier buckets. It never speaks to a bucket that starts after
    # t: nothing read on 9/3 can describe the week of 9/7.
    if bucket.start > retrieved:
        return False
    if kind == "current_only":
        return bucket.start <= retrieved <= bucket.end
    if kind == "bounded":
        months = reach.get("realized_reach_months")
        try:
            months = int(months)
        except (TypeError, ValueError):
            return False
        floor = retrieved - _dt.timedelta(days=int(months * 30.44))
        return floor <= bucket.end
    if kind == "archival":
        return True
    return False


def theme_of_topic(topic: str) -> str | None:
    """Observation topic -> theme key, via a direct key or a buyer signal key."""
    if topic in topics.THEMES_BY_KEY:
        return topic
    return topics.BUYER_SIGNAL_TO_THEME.get(topic)


def instrument_sees(signal: str, theme_key: str) -> bool:
    spec = THEME_INSTRUMENTS.get(signal)
    if not spec:
        return False
    _, scope = spec
    if scope == "all":
        return True
    if isinstance(scope, (list, tuple, set)):
        return theme_key in scope
    return theme_key in set(topics.BUYER_SIGNAL_TO_THEME.values())


def absence_licensing(theme_key: str, instrument_class: dict) -> dict:
    """Which instruments see this theme, and whether any of them licenses reading silence
    as absence. Session 14 item 0b: the one place this is answered, read by both the
    derivation (through the same declarations) and scripts/gap_report.py, so a report
    cannot say "buyer silent" about a theme the derivation composes as
    `no_absence_license`.

    Returns {"instruments": [signal types that see the theme],
             "presence_only": [those whose silence is barred by declaration],
             "licensing": [those whose class is IC3/IC4 and are not presence-only],
             "licensed": bool}
    """
    sees = [s for s in THEME_INSTRUMENTS if instrument_sees(s, theme_key)]
    presence_only = [s for s in sees if s in PRESENCE_ONLY_SIGNAL_TYPES]
    licensing = [s for s in sees if s not in PRESENCE_ONLY_SIGNAL_TYPES
                 and str(instrument_class.get(s, "")) in ABSENCE_CLASSES]
    return {"instruments": sees, "presence_only": presence_only,
            "licensing": licensing, "licensed": bool(licensing)}


# ---------------------------------------------------------------------------------------
# the derivation
# ---------------------------------------------------------------------------------------

def _informing(candidates: list, harness_reach: dict, b: Bucket, stale_days: int) -> list:
    """The observations among `candidates` that speak to bucket `b`: published in time, not stale, read by a source
    whose realized reach covers the bucket. Returns [(observation, reach kind)]."""
    out = []
    for o in candidates:
        reach = harness_reach.get(str(o.get("harness_id") or "")) or {}
        retrieved = _d(o.get("retrieval_date"))
        pub = _d(o.get("publication_date")) or retrieved
        if pub is None or pub > b.end or (b.end - pub).days > stale_days:
            continue
        if not reach_covers(reach, retrieved, b):
            continue
        out.append((o, str(reach.get("realized_reach"))))
    return out


EVIDENCE_NOTE = "evidence: {total} total, {valid} valid, {invalid} invalid"


def evidence_note(informing: list, excluded: list, invalid: dict) -> str:
    """Three measurements for a bucket some invalid observation would have informed, naming what was excluded."""
    ids = "; ".join(f"{o.get('observation_id')} {invalid.get(str(o.get('observation_id')), '')}".strip()
                    for o, _ in sorted(excluded, key=lambda p: str(p[0].get("observation_id"))))
    return (EVIDENCE_NOTE.format(total=len(informing) + len(excluded), valid=len(informing), invalid=len(excluded))
            + f" (excluded as recorded invalid: {ids})")


def derive(inputs: Inputs, derived_at: _dt.date | None = None,
           derivation_id: str = "DR-0000") -> list[dict]:
    derived_at = derived_at or _dt.date.today()
    start = series_start(inputs.themes)
    if start is None:
        return []
    buckets = week_buckets(start, derived_at)
    stale_days = 365 * STALENESS_YEARS

    # index attempts: (company, signal) -> [(retrieved, outcome)]
    att: dict[tuple, list] = {}
    for a in inputs.attempts:
        if str(a.get("scope") or "scoped") != "scoped":
            continue
        if str(a.get("outcome")) not in COVERAGE_OUTCOMES:
            continue
        sig = str(a.get("attempted_signal") or "")
        if sig not in THEME_INSTRUMENTS:
            continue
        att.setdefault((str(a.get("company_id")), sig), []).append(
            (_d(a.get("attempt_timestamp")), THEME_INSTRUMENTS[sig][0]))

    # index observations: (company, theme_key) -> [obs]. Since 2026-09-15 (Matthew, item 19) an observation recorded
    # invalid is read AS invalid: it supports no bucket, and a bucket it would have informed says so in its notes --
    # evidence total, valid and invalid, with the excluded ids -- so the exclusion is visible, not a silent net.
    obs: dict[tuple, list] = {}
    obs_invalid: dict[tuple, list] = {}
    for o in inputs.observations:
        if str(o.get("publication_state") or "") != "released":
            continue
        if str(o.get("evidence_role") or "") not in BUYER_ROLES:
            continue
        tk = theme_of_topic(str(o.get("topic") or ""))
        if not tk:
            continue
        target = obs_invalid if str(o.get("observation_id")) in inputs.invalid else obs
        target.setdefault((str(o.get("company_id")), tk), []).append(o)

    rows: list[dict] = []
    seq = 0
    for cid in inputs.companies:
        for theme in inputs.themes:
            since = _d(theme.buyer_detectable_since)
            for b in buckets:
                seq += 1
                row = {
                    "state_id": None, "derivation_id": derivation_id,
                    "derivation_version": DERIVATION_VERSION,
                    "derived_at": derived_at.isoformat(), "bucket_grain": BUCKET_GRAIN,
                    "bucket_id": b.bucket_id, "bucket_start": b.start.isoformat(),
                    "bucket_end": b.end.isoformat(), "company_id": cid,
                    "theme_id": theme.theme_id, "theme_key": theme.key,
                    "display_label": theme.display_label,
                    "definition_hash": theme.definition_hash,
                    "buyer_detectable_since": theme.buyer_detectable_since,
                    "status": STATUS_NULL, "reason": None, "organizational_state": None,
                    "min_retrospective_reach": None, "covering_instruments": None,
                    "supporting_observation_ids": None, "evidence_count": 0,
                    "lowest_source_grade": None, "max_confidence": None,
                    "staleness_years": STALENESS_YEARS, "notes": None,
                }
                rows.append(row)

                # ---- 1. detectability ----
                if since is None or since > b.start:
                    row["reason"] = REASON_NOT_DETECTABLE
                    continue

                # ---- 2. reach ----
                covering: dict[str, str] = {}   # signal -> reach kind relied on
                for sig, (hid, _) in THEME_INSTRUMENTS.items():
                    if not instrument_sees(sig, theme.key):
                        continue
                    reach = inputs.harness_reach.get(hid) or {}
                    for retrieved, _h in att.get((cid, sig), []):
                        if reach_covers(reach, retrieved, b):
                            covering[sig] = str(reach.get("realized_reach"))
                            break

                informing = _informing(obs.get((cid, theme.key), []), inputs.harness_reach, b, stale_days)
                excluded = _informing(obs_invalid.get((cid, theme.key), []), inputs.harness_reach, b, stale_days)
                if excluded:
                    row["notes"] = evidence_note(informing, excluded, inputs.invalid)

                if not covering and not informing:
                    row["reason"] = REASON_NO_REACH
                    continue

                reaches = list(covering.values()) + [r for _, r in informing]
                row["min_retrospective_reach"] = min(reaches, key=lambda r: REACH_RANK.get(r, -1))
                row["covering_instruments"] = ";".join(sorted(covering)) or None

                # ---- 3. instrument class ----
                if informing:
                    def conf(o):
                        try:
                            return float(o.get("confidence_0_1") or 0)
                        except (TypeError, ValueError):
                            return 0.0
                    best = max(informing, key=lambda p: (conf(p[0]), str(p[0].get("publication_date") or "")))
                    row["status"] = STATUS_OBSERVED
                    row["reason"] = REASON_OBSERVED
                    row["organizational_state"] = best[0].get("organizational_state")
                    row["supporting_observation_ids"] = ";".join(
                        sorted(str(o.get("observation_id")) for o, _ in informing))
                    row["evidence_count"] = len(informing)
                    row["lowest_source_grade"] = max(str(o.get("source_grade") or "C")
                                                     for o, _ in informing)
                    row["max_confidence"] = conf(best[0])
                    continue

                licensing = sorted(
                    inputs.instrument_class.get(sig, "") for sig in covering
                    if sig not in PRESENCE_ONLY_SIGNAL_TYPES
                    and inputs.instrument_class.get(sig, "") in ABSENCE_CLASSES)
                if licensing:
                    row["status"] = STATUS_ABSENT
                    row["reason"] = f"absence_licensed_{licensing[-1]}"
                else:
                    row["reason"] = REASON_NO_LICENSE
    return rows


# ---------------------------------------------------------------------------------------
# loading inputs from the workbook (read side only; the writer is core/db.py)
# ---------------------------------------------------------------------------------------

def load_inputs(wb) -> Inputs:
    def sheet(name):
        ws = wb[name]
        it = ws.iter_rows(values_only=True)
        headers = list(next(it))
        return [dict(zip(headers, r)) for r in it if r and r[0] is not None]

    companies = [str(c["company_id"]) for c in sheet("Companies")
                 if str(c.get("qualification_status") or "") != "provider_benchmark"
                 and not str(c["company_id"]).startswith("P")]

    # per harness: the LATEST registered version's primary sources, weakest realized reach
    hs = sheet("Harness_Sources")
    latest: dict[str, str] = {}
    for r in hs:
        hid, ver = str(r["harness_id"]), str(r["harness_version"])
        if hid not in latest or _vkey(ver) > _vkey(latest[hid]):
            latest[hid] = ver
    harness_reach: dict[str, dict] = {}
    for r in hs:
        hid = str(r["harness_id"])
        if str(r["harness_version"]) != latest[hid] or str(r.get("role")) != "primary":
            continue
        cand = {"realized_reach": r.get("realized_reach"),
                "realized_reach_months": r.get("realized_reach_months"),
                "realized_reach_effective_from": r.get("realized_reach_effective_from")}
        cur = harness_reach.get(hid)
        if cur is None or REACH_RANK.get(str(cand["realized_reach"]), -1) < \
                REACH_RANK.get(str(cur["realized_reach"]), -1):
            harness_reach[hid] = cand

    ic = {str(s["signal_type_name"]): str(s.get("instrument_class") or "")
          for s in sheet("Signal_Types")}
    # Session 16: reach coverage comes from attempts, and an attempt from a run the gate
    # has not published licenses nothing yet -- the same rule observations already obey
    # (released only). Without this, H-BREACHPORTAL-01's first unaudited run composed six
    # licensed absences on the dry run before anyone had read a row.
    published = {str(r["harness_run_id"]) for r in sheet("Harness_Runs")
                 if str(r.get("publication_status") or "") == "published"}
    attempts = [a for a in sheet("Attempts") if str(a.get("run_id")) in published]
    # 2026-09-15 (Matthew, item 19): observations recorded invalid are read as invalid.
    from core import validity
    return Inputs(companies=companies, attempts=attempts,
                  observations=sheet("Observations"), harness_reach=harness_reach,
                  instrument_class=ic, invalid=validity.invalid_observation_ids(wb))


def _vkey(v: str) -> tuple:
    return tuple(int(p) for p in str(v).lstrip("v").split(".") if p.isdigit())


def summarize(rows: list[dict]) -> dict:
    """Counts by status/reason, and per theme, for the CLI and the report."""
    from collections import Counter
    out = {"rows": len(rows), "by_status": Counter(r["status"] for r in rows),
           "by_reason": Counter(r["reason"] for r in rows),
           "by_theme": {}, "by_bucket": {}}
    for r in rows:
        out["by_theme"].setdefault(r["theme_key"], Counter())[r["reason"]] += 1
        out["by_bucket"].setdefault(r["bucket_id"], Counter())[r["reason"]] += 1
    # Evidence citations (observation x bucket) as three measurements, from each row's evidence_count and, where an
    # invalid observation was excluded, its notes.
    import re
    pat = re.compile(r"evidence: (\d+) total, (\d+) valid, (\d+) invalid")
    ev = {"total": 0, "valid": 0, "invalid": 0, "buckets_with_invalid_excluded": 0}
    for r in rows:
        m = pat.search(str(r.get("notes") or ""))
        if m:
            ev["total"] += int(m.group(1))
            ev["valid"] += int(m.group(2))
            ev["invalid"] += int(m.group(3))
            ev["buckets_with_invalid_excluded"] += 1
        else:
            n = int(r.get("evidence_count") or 0)
            ev["total"] += n
            ev["valid"] += n
    out["evidence"] = ev
    return out
