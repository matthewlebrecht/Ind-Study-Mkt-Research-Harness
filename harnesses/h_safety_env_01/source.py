"""
Source clients for H-SAFETY-ENV-01: OSHA establishment search and EPA ECHO.

Two external systems, one logical harness. Per attempts_schema_spec.md §9 Q4 a
`harness_id` denotes one signal-producing unit regardless of how many APIs it calls, and
these two are not independently useful for this project's purpose — both answer "what does
the regulatory record say about how this company runs its physical operations". They share
entity resolution, share a company loop, and would be versioned together.

Both responses are cached through core.cache so a run replays offline.
"""

from __future__ import annotations

import html as _html
import json
import re
from dataclasses import dataclass, field

import urllib.parse

import requests

from core.cache import DatedCache, slug

UA = ("Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; "
      "academic research; +contact via repository)")

OSHA_SEARCH = "https://www.osha.gov/ords/imis/establishment.search"

# OSHA returns 20 rows per page and gives no total count anywhere on the page. Without
# paging, a company with more than 20 inspections silently reports exactly 20 -- which is
# what v1.0 did for 12 of the 107 companies, understating every one of them with nothing in
# the row to indicate a number had been truncated.
OSHA_PAGE_SIZE = 20
ECHO_MAX_PAGES = 5            # 500 facilities; a full last page is declared as a floor
# Declared ceiling on paging. Reported as `suppressed_by_cap` when reached, per the
# standing convention that a truncated result becomes a row rather than a silence.
#
# v1.1 recorded this ceiling as unreachable because hand-built `p_start`/`p_finish` offsets
# did not advance the window, leaving 13 companies on floor counts. v1.2 follows the
# server's own `p_direction=Next` link instead and pages correctly, so the cap is now a
# real bound rather than a formality -- see `osha_search`.
OSHA_MAX_INSPECTIONS = 200
ECHO_SEARCH = "https://echodata.epa.gov/echo/echo_rest_services.get_facilities"
ECHO_QID = "https://echodata.epa.gov/echo/echo_rest_services.get_qid"


@dataclass
class OshaInspection:
    activity_nr: str
    date_opened: str
    state: str
    insp_type: str          # Complaint / Referral / Planned / Accident / Follow-up
    scope: str              # Partial / Complete / Records
    naics: str
    violations: int
    establishment: str

    @property
    def url(self) -> str:
        return f"https://www.osha.gov/ords/imis/establishment.inspection_detail?id={self.activity_nr}"


@dataclass
class EchoFacility:
    name: str
    registry_id: str
    city: str
    state: str
    compliance_status: str
    inspection_count: int
    last_inspection: str
    penalty_count: int
    snc_flag: str           # Significant Non-Complier
    naics: str
    raw: dict = field(default_factory=dict)

    @property
    def url(self) -> str:
        return ("https://echodata.epa.gov/echo/detailed_facility_report.html"
                f"?fid={self.registry_id}")


class SafetyEnvClient:
    def __init__(self, cache: DatedCache):
        self.cache = cache
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self.last_dropped_rows = 0   # S19: result rows that did not parse this search

    # ------------------------------------------------------------------ OSHA

    def osha_search(self, name: str, state: str, start_year: str,
                    end_year: str) -> tuple[list[OshaInspection], str, bool]:
        """Search OSHA's establishment index. Returns (inspections, url).

        The parameter names are lowercase (`state`, `office`, `officetype`). The
        documented mixed-case form fields silently return "your search did not return any
        results" for every query, which is indistinguishable from a genuine absence — the
        exact shape of failure that would have been recorded as `absent_confirmed` and
        quietly become negative evidence about companies that in fact have inspection
        history. Verified by finding known hits (Duke Manufacturing, Mack Molding) that
        the mixed-case form reported as empty.

        Returns (inspections, url, truncated). `truncated` is True when paging stopped at
        the declared cap with records still unread.
        """
        base = {
            "p_logger": "1", "establishment": name, "state": state,
            "officetype": "all", "office": "all", "sitezip": "",
            "p_case": "all", "p_violations_exist": "both",
            "startmonth": "01", "startday": "01", "startyear": start_year,
            "endmonth": "12", "endday": "31", "endyear": end_year,
        }
        first_url = requests.Request("GET", OSHA_SEARCH, params=base).prepare().url

        out: list[OshaInspection] = []
        seen: set[str] = set()
        params = dict(base)
        page_no = 0
        saw_partial_page = False

        # Follow OSHA's OWN "next" link rather than constructing an offset.
        #
        # v1.1 built `p_start`/`p_finish` by hand and found they did not advance the
        # window: offsets 0, 20 and 40 returned identical rows, so paging was abandoned and
        # 13 companies were left holding floor counts of exactly 20 marked
        # `suppressed_by_cap`.
        #
        # The parameters were right; the values were not. The page's own pagination link
        # carries `p_start=` EMPTY with `p_finish` acting as a cursor, plus `p_sort`,
        # `p_desc`, `p_direction=Next`, `p_show`, and a rewritten date window and
        # `sitezip=100000`. Reconstructing that by hand is guesswork; taking the link the
        # server publishes is not. Verified against Kroger/TN, which yields 31 distinct
        # inspections this way against the 20 the offset loop reported as a floor.
        #
        # The result set wraps rather than ending -- page 3 re-serves page 1 -- so the
        # terminator is "no new activity numbers", which is also what protects against a
        # cycle.
        while page_no < OSHA_MAX_INSPECTIONS // OSHA_PAGE_SIZE:
            key = slug(f"osha_{name}_{state}_{start_year}_p{page_no}")

            def fetch(_p=params) -> str:
                r = self.session.get(OSHA_SEARCH, params=_p, timeout=40)
                r.raise_for_status()
                return r.text

            body, _ = self.cache.get(key, ".html", fetch)
            page, dropped = self._parse_osha(body)
            self.last_dropped_rows += dropped
            if len(page) < OSHA_PAGE_SIZE:
                saw_partial_page = True
            fresh = [i for i in page if i.activity_nr not in seen]
            if not fresh:
                # The cursor wraps rather than terminating: after two pages the "Next"
                # link re-serves content already seen. Whether that means "the result set
                # ended" or "the server will not page any further" is decided by how full
                # the repeated page is.
                #
                # A FULL page of already-seen rows means the window is still saturated and
                # the true total is unknown and at least what we hold -- Teichert/CA stops
                # at exactly 40 this way, which is 2 x 20 and therefore suspicious in the
                # same way 20 was in v1.1. Reporting that as complete would replace a
                # visible cap at 20 with an invisible one at 40, which is worse: the first
                # was declared, and this one would look like a measurement.
                #
                # The test is whether ANY page in the sequence came back short, not just
                # the repeated one. A short page anywhere means the result set was
                # exhausted at that point; which page the wrap happens to echo back is an
                # artefact of the cursor, not information about the total. Kroger/TN
                # returns a short page and totals 31, and 31 is real.
                return out, first_url, not saw_partial_page
            for i in fresh:
                seen.add(i.activity_nr)
            out.extend(fresh)

            nxt = self._next_params(body)
            if nxt is None:
                # Session 10 item 6 (S16): no Next link on a FULL page is either the true
                # end or a markup change this parser no longer recognises. Report a floor
                # in that case; a short page with no link is genuinely the end.
                return out, first_url, len(page) >= OSHA_PAGE_SIZE
            params = nxt
            page_no += 1

        # Hit the declared ceiling with a live next link still on the page: genuinely
        # truncated, and reported as such rather than passed off as complete.
        return out, first_url, True

    @staticmethod
    def _next_params(body: str) -> dict | None:
        """Query parameters from the result page's own `p_direction=Next` link."""
        m = re.search(r'href="establishment\.search\?([^"]*p_direction=Next[^"]*)"', body)
        if not m:
            return None
        query = _html.unescape(m.group(1))
        return dict(urllib.parse.parse_qsl(query, keep_blank_values=True))

    @staticmethod
    def _parse_osha(body: str) -> tuple[list[OshaInspection], int]:
        """(inspections, rows_dropped). Session 10 item 6 (S19): a result row that does
        not parse is COUNTED, so the observation can say how many the count omits."""
        if "did not return any results" in body:
            return [], 0
        out = []
        dropped = 0
        # One <tr> per inspection. Anchored on the detail link so header and layout rows
        # cannot be mistaken for results.
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            if "inspection_detail?id=" not in row:
                continue
            cells = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            # checkbox, #, activity, date, RID, ST, type, scope, SIC, NAICS, violations, name
            if len(cells) < 12:
                dropped += 1
                continue
            viol = cells[10].replace("\xa0", "").strip()
            out.append(OshaInspection(
                activity_nr=cells[2], date_opened=cells[3], state=cells[5],
                insp_type=cells[6], scope=cells[7], naics=cells[9],
                # S20: an unparseable count is UNKNOWN, not zero. Zero flipped the
                # observation into the "never cited" reading.
                violations=int(viol) if viol.isdigit() else None,
                establishment=cells[11],
            ))
        return out, dropped

    # ------------------------------------------------------------------ EPA ECHO

    def echo_search(self, name: str, state: str = "") -> tuple[list[EchoFacility], str]:
        """Two-step ECHO lookup: get_facilities returns a QueryID, get_qid returns rows.

        `state` is optional. ECHO indexes facilities by name nationally, which matters
        because 100 of the 108 companies came from a CRM export with `hq_state` left blank
        -- OSHA's establishment index requires a state and cannot degrade this way, so
        without the national fallback the entire Anvil list would be uncoverable by both
        sources rather than one.

        A national search returns far more noise (a bare surname like "Teichert" returns
        152 facilities), which is handled downstream by token scoring rather than here.
        """
        key = slug(f"echo_{name}_{state or 'US'}")
        params = {"output": "JSON", "p_fn": name}
        if state:
            params["p_st"] = state

        def fetch() -> str:
            r = self.session.get(ECHO_SEARCH, params=params, timeout=40)
            r.raise_for_status()
            res = r.json().get("Results", {})
            qid = res.get("QueryID")
            if not qid or str(res.get("QueryRows", "0")) == "0":
                return json.dumps({"Facilities": [], "QueryRows": res.get("QueryRows", "0")})
            # Session 10 item 6 (S24): `responseset=100` was an undeclared cap. Page the
            # query id up to ECHO_MAX_PAGES and DECLARE truncation if the last page was
            # full, the same shape as the OSHA cap (convention 7).
            all_fac = []
            truncated = False
            for pageno in range(1, ECHO_MAX_PAGES + 1):
                r2 = self.session.get(ECHO_QID, params={"output": "JSON", "qid": qid,
                                                        "pageno": pageno, "responseset": "100"},
                                      timeout=40)
                r2.raise_for_status()
                page = (r2.json().get("Results", {}) or {}).get("Facilities", []) or []
                all_fac.extend(page)
                if len(page) < 100:
                    break
            else:
                truncated = True
            return json.dumps({"Facilities": all_fac, "QueryRows": res.get("QueryRows"),
                               "Truncated": truncated})

        body, _ = self.cache.get(key, ".json", fetch)
        data = json.loads(body)
        url = ("https://echodata.epa.gov/echo/echo_rest_services.get_facilities"
               f"?output=JSON&p_fn={requests.utils.quote(name)}"
               + (f"&p_st={state}" if state else ""))
        facilities = [self._facility(f) for f in data.get("Facilities", [])]
        # An archived pre-v1.3 response holds at most 100 with no flag: treat a full 100
        # as truncated, which is the honest direction (a floor, not a total).
        truncated = bool(data.get("Truncated")) or (len(facilities) >= 100 and "Truncated" not in data)
        return facilities, url, truncated

    @staticmethod
    def _facility(f: dict) -> EchoFacility:
        def i(v):
            try:
                return int(str(v or "0").replace(",", ""))
            except ValueError:
                return 0
        return EchoFacility(
            name=f.get("FacName") or "",
            registry_id=f.get("RegistryID") or "",
            city=f.get("FacCity") or "",
            state=f.get("FacState") or "",
            compliance_status=f.get("FacComplianceStatus") or "Unknown",
            inspection_count=i(f.get("FacInspectionCount")),
            last_inspection=f.get("FacDateLastInspection") or "",
            penalty_count=i(f.get("FacPenaltyCount")),
            snc_flag=f.get("FacSNCFlg") or "N",
            naics=f.get("FacNAICSCodes") or "",
            raw=f,
        )
