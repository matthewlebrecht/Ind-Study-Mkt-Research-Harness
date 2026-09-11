"""
Federal recall and complaint sources for H-PRODUCTQUALITY-01, and the process-cause test.

WHY THIS HARNESS IS WORTH BUILDING BEFORE THE OTHER THREE API HARNESSES
-----------------------------------------------------------------------
It is IC4 -- involuntary disclosure, published over the subject's likely preference -- and
IC4 is the class the evidence base is shortest on. It is also the only remaining route to
`legacy_constraint`. Family 4 (employee reviews) was the portfolio's one instrument for
that value and is closed to compliant collection; H-FIRSTPARTY-01 structurally cannot
produce one, because a company does not announce its own obsolescence.

A recall notice can. "Firm's electronic batch record system did not capture the deviation"
is a company describing a systems failure in its own words, under compulsion, in a public
federal database.

WHAT IS AND IS NOT ADMITTED
---------------------------
Not every recall is evidence about modernization. Most are about a contaminated batch or a
mislabelled carton and say nothing about systems at all, and admitting those would fill
family 11 with rows that carry a company name and no claim.

So the bar is: the recall's own reason text must name a **process or systems cause** that
maps onto the shared theme spine. A recall found but not admitted is not discarded -- the
attempt records that recalls exist and that none cited a systems cause, which is a
genuinely different statement from "this company has no recalls" and has to stay
distinguishable from it (convention 6).

APPLICABILITY IS NOT COVERAGE
-----------------------------
These databases cover companies that make physical products. A general contractor has no
FDA registration and a freight carrier has no CPSC recall, and running them through anyway
would produce a wall of `absent_confirmed` rows asserting a clean record where the truth is
that the instrument does not point at them. That is convention 6 again, from the other
side: absence is coverage only when the source is authoritative FOR THAT COMPANY. A company
outside an instrument's population is recorded `not_covered`, with the reason.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from core import topics

TIMEOUT = 90   # saferproducts.gov is slow; 45s timed out on 3 of 10 companies
UA = "IndStudyResearchBot/1.0 (academic research; contact via repository)"

# Which instrument applies to which kind of company. Hand-seeded for the same reason
# H-TRADEPRESS-01's outlet mapping is: `Companies.industry_primary` is blank for all 100
# Anvil rows, and inferring an industry from a company name inside a harness is the silent
# guess convention 13 forbids.
INSTRUMENTS = {
    "medical_device": ["openfda_device_recall", "openfda_device_event"],
    "food": ["openfda_food_enforcement"],
    "consumer": ["cpsc_recall"],
    "vehicle_manufacturer": ["nhtsa_recall"],
}


class SourceError(RuntimeError):
    def __init__(self, message, failure_stage="fetch", failure_category="source_unavailable",
                 fix_class="transient"):
        super().__init__(message)
        self.failure_stage = failure_stage
        self.failure_category = failure_category
        self.fix_class = fix_class


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(8_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # openFDA answers 404 for "no matching records", which is a RESULT, not a failure.
        # Reading it as an error would turn every clean company into a fetch problem and
        # destroy the distinction between "no recalls" and "could not look".
        if e.code == 404:
            return {"results": [], "_empty": True}
        raise SourceError(f"HTTP {e.code} from {urllib.parse.urlparse(url).netloc}",
                          failure_category="access_blocked" if e.code in (401, 403)
                          else "source_unavailable",
                          fix_class="source_limitation" if e.code in (401, 403)
                          else "transient") from e
    except Exception as e:
        raise SourceError(f"{type(e).__name__}: {e}") from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SourceError(f"non-JSON response from {urllib.parse.urlparse(url).netloc}",
                          failure_stage="extraction", failure_category="parse_failure",
                          fix_class="code_change") from e


# --------------------------------------------------------------------------- queries

def _q(term: str) -> str:
    return urllib.parse.quote(f'"{term}"')


def openfda_device_recall(name: str) -> str:
    return (f"https://api.fda.gov/device/recall.json?"
            f"search=recalling_firm:{_q(name)}&limit=50")


def openfda_device_event(name: str) -> str:
    return (f"https://api.fda.gov/device/event.json?"
            f"search=device.manufacturer_d_name:{_q(name)}&limit=25")


def openfda_food_enforcement(name: str) -> str:
    return (f"https://api.fda.gov/food/enforcement.json?"
            f"search=recalling_firm:{_q(name)}&limit=50")


# `RecallTitle`, not `CompanyName` / `ProductName` / `RecallDescription`. Measured against
# the live service: CompanyName and ProductName both return an ERROR RECORD dressed as a
# result -- HTTP 200, a one-element list, Title "Error retrieving Recalls: The underlying
# provider failed on Open." -- and `Manufacturer` returns nothing even for firms that
# demonstrably have recalls, because CPSC's Manufacturers array is usually empty.
#
# The first run recorded 4LIFE and Scentsy as `absent_confirmed` off those error records.
# That is FALSE ABSENCE evidence, which convention 6a rates worse than a gap because it
# carries weight, and it is the exact failure H-SAFETY-ENV-01 v1.0 hit with OSHA.
def cpsc_recall(name: str) -> str:
    return ("https://www.saferproducts.gov/RestWebServices/Recall?format=json"
            f"&RecallTitle={urllib.parse.quote(name)}")


CPSC_ERROR_TITLE = "error retrieving recalls"


def nhtsa_recall(name: str) -> str:
    return ("https://api.nhtsa.gov/products/vehicle/models?"
            f"modelYear=2024&make={urllib.parse.quote(name)}&issueType=r")


QUERY = {
    "openfda_device_recall": openfda_device_recall,
    "openfda_device_event": openfda_device_event,
    "openfda_food_enforcement": openfda_food_enforcement,
    "cpsc_recall": cpsc_recall,
    "nhtsa_recall": nhtsa_recall,
}


# ------------------------------------------------------------------- normalisation

def _iso(value) -> str:
    """YYYYMMDD or YYYY-MM-DD in, ISO out. Never guesses; an unparseable value returns ""
    rather than a fabricated date (convention 3)."""
    v = str(value or "").strip()
    if re.fullmatch(r"\d{8}", v):
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return v
    return ""


def normalise(instrument: str, payload) -> list[dict]:
    """One dict per event: {firm, date, reason, identifier, kind}."""
    out = []
    if instrument.startswith("openfda"):
        for r in (payload or {}).get("results", []):
            reason = (r.get("reason_for_recall") or r.get("root_cause_description")
                      or r.get("product_description") or "")
            if instrument == "openfda_device_event":
                texts = [t.get("text", "") for t in (r.get("mdr_text") or [])]
                reason = " ".join(texts) or reason
            # MAUDE nests the manufacturer under device[0].manufacturer_d_name; the
            # top-level `manufacturer_name` the first version read does not exist, so
            # every adverse-event record arrived with an empty firm and was refused by
            # the identity test. Safe, but it silently disabled the whole instrument --
            # 25 Midmark events reported as "0 matched to company".
            device0 = (r.get("device") or [{}])[0] if isinstance(r.get("device"), list) else {}
            out.append({
                "firm": (r.get("recalling_firm") or device0.get("manufacturer_d_name")
                         or r.get("manufacturer_name") or ""),
                # MAUDE and the enforcement endpoints return YYYYMMDD, not ISO. An
                # un-normalised date reached observation_text as "between 20201027 and
                # 20201027", which is not a date a reviewer can check against anything.
                "date": _iso(r.get("event_date_initiated")
                             or r.get("recall_initiation_date")
                             or r.get("date_received") or ""),
                "reason": reason,
                "identifier": (r.get("recall_number") or r.get("res_event_number")
                               or r.get("report_number") or ""),
                "kind": instrument,
            })
    elif instrument == "cpsc_recall":
        for r in (payload or []):
            title = str(r.get("Title") or "")
            if title.lower().startswith(CPSC_ERROR_TITLE):
                # A server-side failure served as a 200 with a result. Raised rather than
                # returned, so it lands as a fetch failure and never as a clean record.
                raise SourceError(f"CPSC returned an error record: {title[:120]}",
                                  failure_category="source_unavailable",
                                  fix_class="transient")
            firms = ", ".join(x.get("Name", "") for x in (r.get("Manufacturers") or []))
            importers = ", ".join(x.get("Name", "") for x in (r.get("Importers") or []))
            out.append({
                # CPSC's Manufacturers array is empty on most records, but its Title is
                # formatted "<Company> Recalls <product> Due to <hazard>", so the title
                # carries the identity when the structured field does not. Both are
                # handed to the identity test; neither is trusted on its own.
                "firm": firms or importers or title,
                "date": (r.get("RecallDate") or "")[:10],
                "reason": " ".join(filter(None, [
                    r.get("Description", ""),
                    " ".join(h.get("Name", "") for h in (r.get("Hazards") or [])),
                    " ".join(m.get("Name", "") for m in (r.get("Remedies") or []))])),
                "identifier": str(r.get("RecallNumber") or r.get("RecallID") or ""),
                "kind": instrument,
            })
    elif instrument == "nhtsa_recall":
        for r in (payload or {}).get("results", []):
            out.append({"firm": r.get("Manufacturer", ""), "date": "",
                        "reason": r.get("Component", ""),
                        "identifier": r.get("NHTSACampaignNumber", ""),
                        "kind": instrument})
    return out


# --------------------------------------------------------------- the process-cause test

# A recall whose stated cause is a SYSTEM or a PROCESS, as opposed to a contaminated batch
# or a broken part. These phrases are how federal recall notices describe a control that
# did not work, and they are the reason this harness can reach `legacy_constraint` when
# nothing else in the portfolio can.
#
# Deliberately narrow. "Manufacturing defect" is not here: it names a symptom, not a
# system, and admitting it would let essentially every recall through and turn the theme
# assignment into noise -- the H-FIRSTPARTY-01 generic-term failure in a new database.
PROCESS_CAUSE_RE = re.compile(
    r"(?i)\b("
    r"software|firmware|source code|algorithm|"
    r"batch record|electronic record|record[- ]keeping|documentation (?:error|failure|gap)|"
    r"data (?:entry|integrity|transfer|migration)|"
    r"labell?ing (?:error|mix[- ]?up|process|information|requirement)|mislabell?ed|"
    r"labels? (?:missing|incorrect|omitted)|missing required [a-z ]{0,20}label|"
    r"process (?:control|validation|deviation|failure)|"
    r"validation (?:failure|error|gap)|out of specification|"
    r"quality (?:system|management system|control (?:process|system))|"
    r"CAPA|corrective and preventive action|"
    r"traceability|lot (?:code|tracking)|inventory (?:control|record)|"
    r"supplier (?:control|qualification|change)|change control|"
    r"calibration|automated (?:system|inspection)|sensor|"
    r"sterilization (?:process|cycle)|environmental monitoring|"
    r"allergen (?:control|program)|sanitation (?:program|procedure)|HACCP|"
    r"packaging (?:line|process|equipment)|equipment (?:failure|malfunction)|"
    r"training (?:gap|deficien)|human error|operator error|manual (?:entry|process)"
    r")\b")

# Which theme a process cause belongs to, checked before the generic spine so that a
# software recall does not land under whatever theme its product description happens to
# mention. Ordered: the most specific mapping wins.
CAUSE_THEME = [
    (re.compile(r"(?i)\b(software|firmware|source code|algorithm|sensor|"
                r"automated (?:system|inspection)|calibration)\b"),
     "digital_transformation_process"),
    (re.compile(r"(?i)\b(batch record|electronic record|record[- ]keeping|"
                r"data (?:entry|integrity|transfer|migration)|documentation (?:error|"
                r"failure|gap)|traceability|lot (?:code|tracking)|"
                r"inventory (?:control|record))\b"),
     "erp_core_systems"),
    (re.compile(r"(?i)\b(supplier (?:control|qualification|change)|change control|"
                r"packaging (?:line|process|equipment))\b"),
     "systems_integration"),
    (re.compile(r"(?i)\b(manual (?:entry|process)|human error|operator error|"
                r"training (?:gap|deficien))\b"),
     "workforce_enablement"),
    (re.compile(r"(?i)\b(process (?:control|validation|deviation|failure)|"
                r"quality (?:system|management system|control (?:process|system))|"
                r"CAPA|corrective and preventive action|validation (?:failure|error|gap)|"
                r"labell?ing (?:error|mix[- ]?up|process|information|requirement)|"
                r"mislabell?ed|labels? (?:missing|incorrect|omitted)|"
                r"out of specification|sterilization (?:process|cycle)|"
                r"environmental monitoring|allergen (?:control|program)|"
                r"sanitation (?:program|procedure)|HACCP)\b"),
     "digital_transformation_process"),
]


# A cue word is not a cause. The failure predicate has to be in the SAME SENTENCE as the
# cue, because a recall reason text mentions systems constantly without blaming any of them.
#
# The row that forced this: a MAUDE narrative in which Midmark's ECG SOFTWARE correctly
# detected a myocardial infarction, and the physician's guide advises human interpretation
# at the borderline. The bare token "SOFTWARE" scored it as a systems failure and produced
# a `legacy_constraint` observation asserting the opposite of what the record says. That is
# convention 16 in its purest form -- one generic token manufacturing a claim -- and
# convention 32's remedy applies: the row should not exist at any strength.
FAILURE_PREDICATE_RE = re.compile(
    r"(?i)\b(fail(?:ed|ure|s)?|did not|does not|was not|were not|not (?:capture|record|"
    r"detect|perform|follow|validate)|error|incorrect|inadequate|insufficient|missing|"
    r"omitted|deviation|nonconform|non-conform|malfunction(?:ed|ing|s)?|"
    r"defect(?:ive|s)?|discrepan(?:cy|cies|t)|"
    r"unable to|lack(?:ed|ing)?|mix[- ]?up|out of specification|"
    r"not in (?:accordance|compliance)|improper|inconsistent|corrupt)\b")

_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+")


# Session 10 item 5 (Matthew): a bare symptom phrase with no named system or cause is
# sufficient to WRITE at low grade. It maps to the process theme because a manufacturing
# defect is, at minimum, a process-control outcome; the row's state is unknown and the
# marker names the gate, so the reviewer sees exactly how thin it is.
SYMPTOM_CUE_RE = re.compile(r"(?i)\bmanufacturing defects?\b")


def process_cause_tiered(reason: str) -> tuple[str, str, str] | None:
    """(theme_key, cue, tier) where tier is "strong" (cue and failure predicate in the
    SAME sentence) or "weak" (cue in one sentence, a failure predicate elsewhere in the
    narrative). 2026-09-03 corroboration-gate policy: the weak case is written at low
    grade with organizational_state unknown, where v1.2 refused it. A cue with NO failure
    predicate anywhere stays refused: the measured case (Midmark's ECG software correctly
    detecting an infarction) is a claim that is FALSE, not weak, and grading does not fix
    a false claim."""
    strong = process_cause(reason)
    if strong:
        return strong[0], strong[1], "strong"
    if not reason:
        return None
    has_predicate = bool(FAILURE_PREDICATE_RE.search(reason))
    for sentence in _SENT_SPLIT.split(reason):
        if not has_predicate:
            break
        m = PROCESS_CAUSE_RE.search(sentence)
        if not m:
            continue
        for rx, theme in CAUSE_THEME:
            hit = rx.search(sentence)
            if hit:
                return theme, hit.group(0), "weak"
        hits = topics.classify(sentence)
        if hits:
            key = sorted(hits)[0]
            return key, hits[key][0], "weak"
    sym = SYMPTOM_CUE_RE.search(reason)
    if sym:
        return "digital_transformation_process", sym.group(0), "weak_symptom"
    return None


def process_cause(reason: str) -> tuple[str, str] | None:
    """(theme_key, the cue that matched), or None if the cause is not a systems cause.

    The theme comes from the CAUSE, never from the product description. A recall of an
    "AI-enabled monitor" for a cracked housing is not evidence about AI, and letting the
    generic spine classify the whole record would say it was -- the same shape as a press
    release saying "our integrated platform" becoming a systems-integration announcement.
    """
    if not reason:
        return None
    # Sentence-scoped: the cue and the failure predicate must co-occur. Scanning the whole
    # record lets a system named in one sentence be blamed for a fault described in
    # another, which is how the Midmark ECG narrative became a legacy_constraint row.
    blaming = None
    for sentence in _SENT_SPLIT.split(reason):
        m = PROCESS_CAUSE_RE.search(sentence)
        if m and FAILURE_PREDICATE_RE.search(sentence):
            blaming = sentence
            break
    if blaming is None:
        return None
    for rx, theme in CAUSE_THEME:
        hit = rx.search(blaming)
        if hit:
            return theme, hit.group(0)
    reason = blaming
    # A process cause with no mapping falls back to the shared spine, but only if the
    # spine matches the CAUSE sentence, not the whole record.
    hits = topics.classify(reason)
    if hits:
        key = sorted(hits)[0]
        return key, hits[key][0]
    return None
