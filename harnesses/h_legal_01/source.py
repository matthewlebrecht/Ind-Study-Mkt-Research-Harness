"""
CourtListener access for H-LEGAL-01, and the NLRB dependency that could not be read.

WHY `party:` AND NOT A FREE-TEXT QUERY
--------------------------------------
The session-3 probe reported "55 results for Kenco Group" and that number was quoted into
CLAUDE.md as the reason this harness was the cheapest remaining win. It is not 55 Kenco
cases. CourtListener's `q=` searches the full text of the docket INCLUDING the text of
filed documents, so `q="Kenco Group"` returns any docket in which that phrase appears
anywhere -- the top hit is a Walker Edison furniture bankruptcy in Delaware whose party
list does not contain Kenco at all.

    q="Kenco Group"        -> 55  (full text, includes unrelated dockets)
    party:"Kenco Group"    -> 21  (parties only, all genuinely Kenco)

Building on the free-text count would have written 34 unrelated dockets into the evidence
base as Kenco's litigation history: convention 16 at the scale of a whole harness, and the
number was already in a state document waiting to be trusted.

`party:` narrows but does NOT resolve identity. It is tokenized, not an exact phrase, so
`party:"Prime Inc."` returns 483 dockets including "Certified Prime Inc", "Parker's Prime,
Inc." and "Prime Excavating". Every returned party string is therefore scored by the same
identity guard the rest of the project uses, and convention 31 governs: a common word like
PRIME needs the full company phrase, not a token.

NLRB
----
Readable, and the first version of this module said otherwise. See the CORRECTION note
above `NLRB_SEARCH` below: the site's own form is a POST to /search/case that redirects to
a server-rendered GET at /search/case/<term>. The earlier "no interface" verdict came from
guessed API paths and a response-size inference, never from using the form.

It establishes labour friction, not modernization themes -- its allegation vocabulary is
statutory and names conduct, not systems. Queried, counted and reported separately from
CourtListener so the two sources are never collapsed into one coverage figure.
"""

from __future__ import annotations

import json
import time
import urllib.parse

import requests

BASE = "https://www.courtlistener.com/api/rest/v4/search/"
UA = "IndStudyResearchBot/1.0 (academic research; contact via repository)"
TIMEOUT = 60

# CourtListener answers `type=r` (RECAP dockets) without a token. Confirmed 2026-08-31 and
# again 2026-09-01 from a different network: 2.1M dockets, no credential required.
SEARCH_TYPE = "r"


class SourceError(RuntimeError):
    def __init__(self, message, failure_stage="fetch",
                 failure_category="source_unavailable", fix_class="transient"):
        super().__init__(message)
        self.failure_stage = failure_stage
        self.failure_category = failure_category
        self.fix_class = fix_class


def docket_query(name: str) -> str:
    """The search URL for one company name. Party-scoped -- see the module docstring."""
    params = {"q": f'party:"{name}"', "type": SEARCH_TYPE, "order_by": "dateFiled desc"}
    return f"{BASE}?{urllib.parse.urlencode(params)}"


def fetch_json(url: str, attempts: int = 4) -> dict:
    """GET with backoff on 429. CourtListener's anonymous quota is real and it is hit at
    108-company scale: the first full run stopped partway through. Backing off is the
    polite behaviour and it is also the only way this harness completes a full pass; a
    run that dies mid-universe leaves the remaining companies with no attempt row at all,
    which is the denominator failure convention 5 exists to prevent."""
    delay = 5.0
    for i in range(attempts):
        try:
            resp = requests.get(url, headers={"User-Agent": UA,
                                              "Accept": "application/json"},
                                timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise SourceError(f"{type(e).__name__}: {e}")
        if resp.status_code != 429:
            break
        if i == attempts - 1:
            raise SourceError(
                f"rate limited by CourtListener (HTTP 429) after {attempts} attempts "
                f"with backoff -- anonymous quota",
                failure_category="source_unavailable", fix_class="transient")
        time.sleep(delay)
        delay *= 2
    if resp.status_code == 429:
        # `source_unavailable`, not a new vocabulary value. Controlled vocabularies are
        # additive-only (convention 22) but that is a licence to extend them when a
        # distinction matters, not an invitation to mint a synonym: a rate limit IS the
        # source being temporarily unavailable, and the specificity belongs in
        # failure_detail where it is readable without a schema migration.
        raise SourceError("rate limited by CourtListener (HTTP 429) -- anonymous quota",
                          failure_category="source_unavailable", fix_class="transient")
    if resp.status_code >= 400:
        raise SourceError(f"HTTP {resp.status_code} from CourtListener")
    ctype = resp.headers.get("Content-Type", "")
    if "json" not in ctype.lower():
        # The same defect class as CPSC's error record dressed as a 200: a non-JSON body
        # where JSON was asked for is a failure, never an empty result set (convention 6a).
        raise SourceError(
            f"CourtListener returned {ctype!r} rather than JSON -- treated as a fetch "
            f"failure, not as zero dockets",
            failure_category="source_drift_detected", fix_class="harness_bug")
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        raise SourceError(f"undecodable JSON from CourtListener: {e}",
                          failure_category="source_drift_detected",
                          fix_class="harness_bug")


def normalise(payload: dict) -> tuple[list[dict], int]:
    """(dockets, reported_total). The total is the source's own count, not len(results).

    Both are returned because they differ whenever the result set is paged, and reporting
    len(results) as though it were the total is how a cap becomes an invisible ceiling
    (convention 7 -- and the OSHA 20-per-page failure, which was exactly this).
    """
    if not isinstance(payload, dict):
        raise SourceError(f"expected a JSON object, got {type(payload).__name__}",
                          failure_category="source_drift_detected",
                          fix_class="harness_bug")
    out = []
    for r in payload.get("results") or []:
        out.append({
            "docket_id": r.get("docket_id"),
            "case_name": (r.get("caseName") or "").strip(),
            "case_name_full": (r.get("case_name_full") or "").strip(),
            "court": (r.get("court") or "").strip(),
            "court_id": (r.get("court_id") or "").strip(),
            "date_filed": (r.get("dateFiled") or "")[:10],
            "date_terminated": (r.get("dateTerminated") or "")[:10],
            "docket_number": (r.get("docketNumber") or "").strip(),
            "suit_nature": (r.get("suitNature") or "").strip(),
            "cause": (r.get("cause") or "").strip(),
            "parties": [p for p in (r.get("party") or []) if p],
            "url": ("https://www.courtlistener.com" + r["docket_absolute_url"]
                    if r.get("docket_absolute_url") else ""),
            # Document descriptions are the richest text the search endpoint returns and
            # are what a systems dispute actually shows up in. Capped, and the cap is
            # recorded rather than assumed.
            "documents": [(d.get("description") or "").strip()
                          for d in (r.get("recap_documents") or [])[:8]
                          if (d.get("description") or "").strip()],
        })
    return out, int(payload.get("count") or 0)


# --------------------------------------------------------------------------------- NLRB
#
# CORRECTION, 2026-09-01. The first version of this module declared NLRB "declared and not
# read", on the grounds that /api/v1/cases and the other guessed API paths answer 404 and
# the search page is a 256KB shell. That conclusion was wrong, and it was wrong in this
# project's characteristic way: it was inferred from response SIZE and from paths I made
# up, without ever using the site's own form.
#
# The form is a POST to /search/case, and it redirects to a plain GET at
# /search/case/<term> which returns SERVER-RENDERED results -- company name, case number,
# date filed, status, location, region. No JavaScript, no authentication, no API key.
# `robots.txt` permits it.
#
# WHAT THE SOURCE CAN AND CANNOT SUPPORT. Case detail pages carry an `Allegations` section,
# but its contents are a closed statutory vocabulary describing conduct under the NLRA --
# "8(a)(3) Discharge", "8(a)(1) Coercive Statements", "8(a)(5) Refusal to Bargain",
# "Allegations data is not available." for representation cases. Sampled across five
# companies, ZERO of ten distinct labels classify to a modernization theme through
# core/topics.py, and none can: they name what an employer is alleged to have done to
# organising rights, never what systems it runs.
#
# So this source establishes labour friction, which is real family-3/13 coverage, and it
# cannot establish a modernization theme. Reading one off "8(a)(3) Discharge" would be the
# caption-classification error this harness already made once. Case detail pages are
# therefore NOT fetched per company: with a provably theme-free vocabulary that would be
# several hundred requests for a yield that is zero by construction.

NLRB_SEARCH = "https://www.nlrb.gov/search/case/"

# Layout furniture inside a result block, skipped when walking back for the party name.
_NLRB_CHROME = {
    "E-File", "Follow", "Sign into MyNLRB", "What is this?", "receive", "updates.",
    "to follow cases and", "Case Search Results for", "Download CSV",
}


def nlrb_query(name: str) -> str:
    return NLRB_SEARCH + urllib.parse.quote(str(name).strip())


def nlrb_fetch(url: str) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise SourceError(f"{type(e).__name__}: {e}")
    if resp.status_code >= 400:
        raise SourceError(f"HTTP {resp.status_code} from nlrb.gov")
    return resp.text


def nlrb_cases(lines: list[str]) -> list[dict]:
    """Parse rendered result blocks. Keyed on the "Case Number:" label, walking backwards
    for the respondent name, because the name is the only field with no label of its own.
    """
    rows = [ln.strip() for ln in lines if ln and ln.strip()]
    out = []
    for i, ln in enumerate(rows):
        if ln != "Case Number:" or i + 1 >= len(rows):
            continue
        rec = {"case_number": rows[i + 1], "party": "", "date_filed": "",
               "status": "", "location": "", "region": ""}
        for j in range(i - 1, max(0, i - 16), -1):
            cand = rows[j]
            if cand in _NLRB_CHROME or cand.endswith(":"):
                continue
            rec["party"] = cand
            break
        for label, key in (("Date Filed:", "date_filed"), ("Status:", "status"),
                           ("Location:", "location"), ("Region Assigned:", "region")):
            for j in range(i, min(len(rows), i + 14)):
                if rows[j] == label and j + 1 < len(rows):
                    rec[key] = rows[j + 1]
                    break
        out.append(rec)
    return out
