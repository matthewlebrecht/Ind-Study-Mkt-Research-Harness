"""
FMCSA source layer — fetch + parse only. No project semantics live here.

Two public sources, neither requiring an API key:

  1. FMCSA Motor Carrier Census (Socrata, data.transportation.gov, dataset az4n-8mr2)
     ~4.5M rows. Used for *candidate discovery* — searching by company name/state to
     find plausible USDOT numbers.

  2. SAFER Company Snapshot (safer.fmcsa.dot.gov/query.asp)
     Authoritative per-carrier record. Used for *evidence extraction* once a USDOT
     number is resolved: fleet size, mileage, authority, cargo, 24-month roadside
     inspection out-of-service rates vs. national average, and crash counts.

Every response is cached to disk under harness_output/<harness_id>/raw/ so a run is
reproducible and re-reviewable without re-hitting the agency.

FMCSA's own QCMobile REST API (mobile.fmcsa.dot.gov/qc/services) exposes the same
carrier record in JSON but requires a free registered webKey. If FMCSA_WEBKEY is set
in the environment this module prefers it for the snapshot step, because parsing JSON
is far less brittle than parsing SAFER's 1990s table markup.
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

import requests

from core.cache import DatedCache

CENSUS_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"
CENSUS_LANDING = "https://data.transportation.gov/Trucking-and-Motorcoach/Motor-Carrier-Census/az4n-8mr2"
SAFER_QUERY_URL = "https://safer.fmcsa.dot.gov/query.asp"
QCMOBILE_URL = "https://mobile.fmcsa.dot.gov/qc/services/carriers/{dot}"

USER_AGENT = ("Mkt_Research_Harness/1.0 (independent study project; "
              "contact matthewlebrecht@gmail.com)")
REQUEST_PAUSE_SECONDS = 1.0  # be polite to a public agency endpoint


def safer_snapshot_url(dot_number: str) -> str:
    """Human-checkable citation URL for a snapshot (what a reviewer would open)."""
    return ("https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY"
            "&query_type=queryCarrierSnapshot&query_param=USDOT"
            f"&query_string={dot_number}")


class FmcsaClient:
    """Fetches FMCSA data, archiving every response under its retrieval date.

    The cache is partitioned by date (raw/YYYY-MM-DD/...) rather than keyed by USDOT
    alone. A flat cache would let each re-run overwrite the evidence of what an earlier
    run actually read, which destroys the audit trail behind already-written observations
    — and SAFER's numbers move, so that trail is the only way to show a past row was
    correct when it was written.

    Live runs always fetch (today's partition starts empty). `offline=True` replays the
    most recent partition that holds each response.
    """

    def __init__(self, cache_dir: Path, offline: bool = False, retrieval_date: str | None = None):
        self.cache = DatedCache(cache_dir, offline=offline, retrieval_date=retrieval_date,
                                pause_seconds=REQUEST_PAUSE_SECONDS)
        # Session 14 (2026-09-06): read through core.config so a key in `.env` reaches
        # this module. It used to read os.environ directly, and nothing in this harness
        # loaded `.env`, so the first live run with a configured webkey (this morning)
        # silently took the SAFER HTML path -- exactly the "degrade into a working path
        # without saying so" that core/config.py exists to prevent.
        from core.config import get_key
        self.webkey = get_key("FMCSA_WEBKEY")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    # ---------- caching ----------

    def _cached(self, key: str, suffix: str, fetch):
        return self.cache.get(key, suffix, fetch)

    # Backwards-compatible accessors for callers and run logs.
    @property
    def retrieval_date(self) -> str:
        return self.cache.retrieval_date

    @property
    def replayed_from(self) -> dict:
        return self.cache.replayed_from

    @property
    def request_count(self) -> int:
        return self.cache.fetch_count

    # ---------- census / candidate discovery ----------

    def census_search(self, like_term: str, state: str | None, limit: int = 50) -> list[dict]:
        """Substring search over legal_name, optionally pinned to a physical state.

        Deliberately loose — this is candidate *generation*. Precision is the
        resolver's job, not the query's.
        """
        safe = like_term.upper().replace("'", "''")
        where = f"upper(legal_name) like '%{safe}%'"
        if state:
            where += f" AND phy_state='{state.upper()}'"
        params = {
            "$where": where,
            "$limit": str(limit),
            "$order": "power_units DESC",
            "$select": ("dot_number,legal_name,dba_name,phy_city,phy_state,power_units,"
                        "total_drivers,truck_units,status_code,carrier_operation,classdef,"
                        "mcs150_date,mcs150_mileage,mcs150_mileage_year,add_date,"
                        "docket1prefix,docket1,business_org_desc"),
        }
        key = "census_" + re.sub(r"[^A-Z0-9]+", "_", f"{safe}_{state or 'ANY'}_{limit}")
        body, _ = self._cached(
            key, ".json",
            lambda: self._get(CENSUS_URL, params).text,
        )
        return json.loads(body)

    # ---------- per-carrier snapshot ----------

    def carrier_snapshot(self, dot_number: str) -> dict:
        """Return a normalized carrier record for one USDOT number."""
        if self.webkey:
            body, _ = self._cached(
                f"qc_{dot_number}", ".json",
                lambda: self._get(QCMOBILE_URL.format(dot=dot_number),
                                  {"webKey": self.webkey}).text,
            )
            rec = _parse_qcmobile(json.loads(body))
            if rec:
                rec["_source"] = "qcmobile"
                # Session 10 item 6 (F15/F26): the basic carrier object carries no
                # operation classification, which left `_is_private_carriage` blind on
                # this path. QCMobile publishes the classification and cargo lists on
                # sub-endpoints; read them, and record a failure rather than pretending.
                for sub, field, key in (("operation-classification", "operationClassDesc",
                                         "operation_classification"),
                                        ("cargo-carried", "cargoClassDesc", "cargo_carried")):
                    try:
                        sb, _ = self._cached(
                            f"qc_{dot_number}_{sub}", ".json",
                            lambda s=sub: self._get(QCMOBILE_URL.format(dot=dot_number) + "/" + s,
                                                    {"webKey": self.webkey}).text)
                        content = (json.loads(sb) or {}).get("content") or []
                        rec[key] = [str(x.get(field) or "").strip() for x in content
                                    if isinstance(x, dict) and x.get(field)]
                    except Exception as exc:  # noqa: BLE001
                        rec[f"{key}_error"] = f"{type(exc).__name__}: {exc}"[:120]
                return rec
        body, _ = self._cached(
            f"safer_{dot_number}", ".html",
            lambda: self._post(SAFER_QUERY_URL, {
                "searchtype": "ANY",
                "query_type": "queryCarrierSnapshot",
                "query_param": "USDOT",
                "query_string": str(dot_number),
            }).text,
        )
        rec = parse_safer_snapshot(body)
        rec["_source"] = "safer"
        return rec

    # ---------- transport ----------

    def _get(self, url: str, params: dict) -> requests.Response:
        r = self.session.get(url, params=params, timeout=60)
        r.raise_for_status()
        return r

    def _post(self, url: str, data: dict) -> requests.Response:
        r = self.session.post(url, data=data, timeout=60)
        r.raise_for_status()
        return r


# ----------------------------------------------------------------------------
# SAFER snapshot parsing
# ----------------------------------------------------------------------------

def _flatten(markup: str) -> list[str]:
    text = html.unescape(re.sub(r"<[^>]+>", "\n", markup))
    return [line.strip() for line in text.split("\n") if line.strip()]


def _labelled(lines: list[str], label: str, offset: int = 1) -> str | None:
    """Value that follows a label cell, e.g. 'Power Units:' -> '3,332'."""
    for i, line in enumerate(lines):
        if line == label and i + offset < len(lines):
            return lines[i + offset]
    return None


def _int(value) -> int | None:
    if value is None:
        return None
    m = re.search(r"-?[\d,]+", str(value))
    return int(m.group(0).replace(",", "")) if m else None


def _pct(value) -> float | None:
    if value is None:
        return None
    m = re.search(r"([\d.]+)\s*%", str(value))
    return float(m.group(1)) if m else None


def parse_safer_snapshot(markup: str) -> dict:
    """Extract the fields the harness reasons over from a SAFER Company Snapshot."""
    lines = _flatten(markup)
    rec: dict = {"found": False}

    if "Record Not Found" in markup or "No records matching" in markup:
        return rec
    if _labelled(lines, "USDOT Number:") is None:
        return rec
    rec["found"] = True

    rec["dot_number"] = _labelled(lines, "USDOT Number:")
    rec["usdot_status"] = _labelled(lines, "USDOT Status:")
    rec["entity_type"] = _labelled(lines, "Entity Type:")
    rec["legal_name"] = _labelled(lines, "Legal Name:")
    rec["out_of_service_date"] = _labelled(lines, "Out of Service Date:")
    rec["mcs150_date"] = _labelled(lines, "MCS-150 Form Date:")
    rec["mcs150_mileage_raw"] = _labelled(lines, "MCS-150 Mileage (Year):")
    # SAFER renders this field two different ways. An authorized carrier shows
    #   Operating Authority Status: | AUTHORIZED FOR: | <the authority granted>
    # while a private or intrastate-only carrier shows
    #   Operating Authority Status: | NOT AUTHORIZED
    # Reading only the "AUTHORIZED FOR:" label silently loses the second case. The page
    # legend also contains the literal words "NOT AUTHORIZED" on *every* snapshot, so a
    # substring search over the markup is wrong — match the labelled field.
    status = _labelled(lines, "Operating Authority Status:")
    if status == "AUTHORIZED FOR:":
        rec["operating_authority_status"] = "AUTHORIZED"
        rec["authorized_for"] = _labelled(lines, "AUTHORIZED FOR:")
    else:
        rec["operating_authority_status"] = status      # e.g. "NOT AUTHORIZED"
        rec["authorized_for"] = None
    rec["mc_numbers"] = _labelled(lines, "MC/MX/FF Number(s):")
    rec["power_units"] = _int(_labelled(lines, "Power Units:"))
    rec["drivers"] = _int(_labelled(lines, "Drivers:"))

    # "The information below reflects ... as of MM/DD/YYYY."
    m = re.search(r"management information systems as of\s*([\d/]{8,10})", " ".join(lines))
    rec["data_as_of"] = m.group(1).rstrip(".") if m else None

    # DBA name label is followed immediately by the next label when empty.
    dba = _labelled(lines, "DBA Name:")
    rec["dba_name"] = None if dba in (None, "Physical Address:") else dba

    m = re.match(r"([\d,]+)\s*\((\d{4})\)", rec.get("mcs150_mileage_raw") or "")
    rec["mcs150_mileage"] = int(m.group(1).replace(",", "")) if m else None
    rec["mcs150_mileage_year"] = m.group(2) if m else None

    rec["operation_classification"] = _checked_items(lines, "Operation Classification:")
    rec["carrier_operation"] = _checked_items(lines, "Carrier Operation:")
    rec["cargo_carried"] = _checked_items(lines, "Cargo Carried:")

    rec.update(_parse_inspections(lines))
    rec.update(_parse_crashes(lines))
    rec["safety_rating"] = _labelled(lines, "Rating:")
    rec["safety_rating_date"] = _labelled(lines, "Rating Date:")
    rec["safety_review_date"] = _labelled(lines, "Review Date:")
    return rec


# The three checkbox grids appear in this order; each ends where the next begins.
_CHECKBOX_GROUPS = ["Operation Classification:", "Carrier Operation:", "Cargo Carried:"]
_CHECKBOX_TERMINATORS = _CHECKBOX_GROUPS + [
    "Inspection Type", "Crashes:", "United States Inspections", "Inspections:",
]


def _checked_items(lines: list[str], header: str) -> list[str]:
    """SAFER marks selected checkbox cells with a literal 'X' before the item label.

    Each grid must be bounded at the next grid's header — the grids sit in adjacent
    table cells, so an unbounded scan silently merges cargo types into the carrier
    operation list.
    """
    try:
        start = lines.index(header)
    except ValueError:
        return []
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] in _CHECKBOX_TERMINATORS:
            end = i
            break
    window = lines[start:end]
    items: list[str] = []
    for i, line in enumerate(window):
        if line == "X" and i + 1 < len(window):
            nxt = window[i + 1]
            if nxt not in ("X", "SAFER Layout") and len(nxt) < 60:
                items.append(nxt)
    return items


def _parse_inspections(lines: list[str]) -> dict:
    """First 'Inspection Type' block on the page is the United States block."""
    out: dict = {}
    try:
        start = lines.index("Inspection Type")
    except ValueError:
        return out
    window = lines[start: start + 40]

    def row_after(label: str, count: int) -> list[str]:
        try:
            i = window.index(label)
        except ValueError:
            return []
        return window[i + 1: i + 1 + count]

    header_span = window[1:5]  # Vehicle / Driver / Hazmat / IEP
    ncols = len([h for h in header_span if h in ("Vehicle", "Driver", "Hazmat", "IEP")])
    keys = ["vehicle", "driver", "hazmat", "iep"][:ncols]

    for label, suffix, caster in (("Inspections", "inspections", _int),
                                  ("Out of Service", "oos", _int),
                                  ("Out of Service %", "oos_pct", _pct)):
        values = row_after(label, ncols)
        for k, v in zip(keys, values):
            out[f"{k}_{suffix}"] = caster(v)

    # National average row's label carries a date suffix, so match by prefix.
    for i, line in enumerate(window):
        if line.startswith("Nat'l Average %"):
            values = window[i + 1: i + 1 + ncols + 1]
            values = [v for v in values if v.strip().endswith("%") or v.strip() == "N/A"]
            for k, v in zip(keys, values):
                out[f"{k}_natl_avg_pct"] = _pct(v)
            break
    return out


def _parse_crashes(lines: list[str]) -> dict:
    out: dict = {}
    for i, line in enumerate(lines):
        if line == "Crashes:" and lines[i + 1: i + 2] == ["Type"]:
            window = lines[i: i + 15]
            try:
                j = window.index("Crashes", 1)
            except ValueError:
                continue
            values = window[j + 1: j + 5]
            for k, v in zip(["fatal", "injury", "tow", "total"], values):
                out[f"crashes_{k}"] = _int(v)
            break
    m = re.search(r"Crashes reported to FMCSA by states for 24 months prior to:\s*([\d/]{8,10})",
                  " ".join(lines))
    if m:
        out["crash_window_end"] = m.group(1)
    return out


def _parse_qcmobile(payload: dict) -> dict | None:
    """Normalize the QCMobile JSON carrier object onto the SAFER field names."""
    carrier = (payload or {}).get("content")
    if isinstance(carrier, list):
        carrier = carrier[0] if carrier else None
    if not carrier:
        return None
    c = carrier.get("carrier", carrier)

    # Session 14 (2026-09-06), the first live read with a webkey: QCMobile serves the
    # national-average rates as STRINGS ("22.26") and the carrier's own rates as numbers,
    # so `rate - natl` raised TypeError on the first carrier. Coerce every numeric field
    # here, once, onto the types parse_safer_snapshot() already produces; an unparseable
    # value becomes None and the emitter records the parse gap rather than guessing.
    def _num(v):
        if v is None or v == "":
            return None
        try:
            return float(str(v).rstrip("%"))
        except ValueError:
            return None

    def _int(v):
        n = _num(v)
        return int(n) if n is not None else None

    return {
        "found": True,
        "dot_number": str(c.get("dotNumber", "")),
        "legal_name": c.get("legalName"),
        "dba_name": c.get("dbaName"),
        "usdot_status": "ACTIVE" if c.get("allowedToOperate") == "Y" else "NOT ALLOWED",
        "operating_authority_status": ("AUTHORIZED" if c.get("allowedToOperate") == "Y"
                                       else "NOT AUTHORIZED"),
        "authorized_for": c.get("carrierOperation", {}).get("carrierOperationDesc"),
        "power_units": _int(c.get("totalPowerUnits")),
        "drivers": _int(c.get("totalDrivers")),
        "safety_rating": c.get("safetyRating"),
        "safety_rating_date": c.get("safetyRatingDate"),
        "vehicle_inspections": _int(c.get("vehicleInsp")),
        "driver_inspections": _int(c.get("driverInsp")),
        "vehicle_oos_pct": _num(c.get("vehicleOosRate")),
        "driver_oos_pct": _num(c.get("driverOosRate")),
        "vehicle_natl_avg_pct": _num(c.get("vehicleOosRateNationalAverage")),
        "driver_natl_avg_pct": _num(c.get("driverOosRateNationalAverage")),
        "crashes_fatal": _int(c.get("fatalCrash")),
        "crashes_injury": _int(c.get("injCrash")),
        "crashes_tow": _int(c.get("towawayCrash")),
        "crashes_total": _int(c.get("crashTotal")),
        "carrier_operation": [(c.get("carrierOperation") or {}).get("carrierOperationDesc")],
        "operation_classification": [],
        "cargo_carried": [],
    }
