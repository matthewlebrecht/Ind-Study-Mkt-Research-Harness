"""
H-PROCUREMENT-01 -- Federal award records (USASpending.gov), families 7 and 2.

WHAT IT RECORDS
---------------
For each of the 108 buyers, whether the company held federal PRIME awards in the five years
to the retrieval date (core/windows.py), and what they were:

    federal_prime_contract_award  family 7   contracts (A-D) and IDVs
    federal_assistance_award      family 2   grants and loans

Both IC3 (taxonomy §20: procurement records are the class's named example -- reported by
the government, a byproduct of operating). A row is `buyer_acts` / `measured_result` /
grade A / `organizational_state = unknown`.

WHY NO THEME ROUTING, AND WHY THIS CANNOT LICENSE A `systems_integration` ABSENCE
---------------------------------------------------------------------------------
In a prime award the company is the SELLER. The award description ("DESIGN-BUILD ...
CONSTRUCT BARRACKS", "IGF::OT::IGF ... RENOVATION") describes work delivered to an agency,
not the company's own estate, so classifying it through core/topics.py would turn a
contractor that builds a data centre for the Navy into a company modernizing its data
infrastructure -- convention 16's loose pattern applied to the wrong party. The one leg in
which the company is the BUYER, subawards under its own prime awards, was measured on
2026-09-13 and is empty where it was checked (0 subawards under Whiting-Turner's two
largest primes), and subaward reporting is prime-self-reported and known to be incomplete,
so its silence could not be licensed even if it were populated. And no statute compels a
company to disclose integration work the way breach statutes compel a breach notice. So
core/composition.py does not list either signal type as a theme instrument and its
silence licenses nothing about any theme. What it DOES license is narrower and true: an
`absent_confirmed` here means "no federal prime award in the window", a statement about
federal contracting exposure, not about modernization.

IDENTITY (the hard part, measured before building)
--------------------------------------------------
USASpending's text search is substring-like: "Mack Group" returns COMMACK GROUP and
MCCORMACK GROUP, "Kenco" returns KENCOA AEROSPACE, "Prime Inc" returns 141 recipients.
And one company files under several UEIs, some of them regional entities in other states
(Clark Construction Group LLC in MD, Clark Construction Group - California, LP; eleven
SWINERTON BUILDERS registrations across CA, HI and CO). So:

  1. Candidates come from AWARD records, not the recipient directory: each award carries
     the recipient's name, UEI and registered location, so identity is decided on the
     entities that actually hold awards in the window.
  2. Name rule (`name_matches`): every distinctive company token must be present as an
     EXACT token (initials collapsed, so C.R. England matches "C R ENGLAND" and not
     "ENGLAND LOGISTICS"); the recipient may add only line-of-business or legal-form words;
     a "dba" clause is split; a joint venture is a different legal entity and is refused;
     a company whose name reduces to one ordinary English word (PRIME, POWER, SUMMIT) must
     match in full (convention 31).
  3. Location corroboration: an entity is accepted only if its registered state is the
     company's HQ state. A same-named entity elsewhere is logged and NOT counted, so
     counts are floors for national firms with regional subsidiaries, and the text says so.
  4. Absence (convention 6a): `absent_confirmed` only when every name variant was searched
     and no awarded recipient in the company's HQ state shares a distinctive name token.
     A same-state near-miss is `not_covered` / `entity_below_threshold` -- it may be the
     company under another legal name, which is an alias for a human to seed, not an
     absence.

    python harnesses/h_procurement_01/harness.py              # dry run
    python harnesses/h_procurement_01/harness.py --commit
    python harnesses/h_procurement_01/harness.py --offline
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import aliases  # noqa: E402
from core.attempts import access_detail  # noqa: E402
from core.cache import DatedCache, slug  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from core.resolution import STOPWORDS, WEAK_TOKENS, query_variants, state_code  # noqa: E402
from core.robots import RobotsGate  # noqa: E402
from core.windows import STALENESS_YEARS  # noqa: E402
from harnesses.h_firstparty_01.article import COMMON_WORD_NAMES  # noqa: E402

HARNESS_ID = "H-PROCUREMENT-01"
HARNESS_NAME = "Federal Award Records Reader (USASpending)"
VERSION = "v1.4"
SIG_CONTRACT, FAM_CONTRACT = "federal_prime_contract_award", "7_procurement_contracting"
SIG_ASSIST, FAM_ASSIST = "federal_assistance_award", "2_financial_capital_allocation"
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
API = "https://api.usaspending.gov/api/v2"
# The portfolio's standard identity. NOT the probe's former "IndStudyResearchBot" string,
# which USASpending's WAF refuses on the token "ResearchBot" (2026-09-13 diagnosis,
# scripts/probe_sources.py). This UA is what every harness sends; it was not chosen to get
# past that rule and it identifies the project the same way.
UA = "Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; +independent study, contact via repo)"
TIMEOUT = 90
PAGE_LIMIT = 100
MAX_PAGES = 5

# One award-type group per request: the search endpoint does not mix groups.
GROUPS = {
    "contracts": ["A", "B", "C", "D"],
    "idvs": ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"],
    "grants": ["02", "03", "04", "05"],
    "loans": ["07", "08"],
}
CONTRACT_GROUPS, ASSIST_GROUPS = ("contracts", "idvs"), ("grants", "loans")

# Additions to H-FIRSTPARTY-01's ordinary-word list for names in THIS universe that reduce
# to one dictionary word. Kept local rather than added to the shared set so FIRSTPARTY's
# behaviour does not change under an unrelated build (convention 40's bundling rule).
LOCAL_COMMON_WORDS = {"power", "commercial", "coastal", "savage", "crane", "diagnostics",
                      "admiral", "product", "sales", "structures", "engineered",
                      # a given name is no more an identity than PRIME (convention 31):
                      # NICHOLAS PETERSON is a person, not Nicholas and Company
                      "nicholas"}
# Recipient-side extras that do not change who the entity is.
GENERIC_ORG_WORDS = {"INTERNATIONAL", "COMPANY", "COMPANIES", "THE", "USA", "US", "NORTH",
                     "AMERICA", "AMERICAN", "HOLDINGS", "GROUP", "ENTERPRISES", "INCORPORATED",
                     "OF", "AND", "BROS", "BROTHERS",
                     # GILBANE BUILDING COMPANY and MCCARTHY BUILDING COMPANIES were refused
                     # as near-misses in the 2026-09-13 full dry run; BUILDING is a line of
                     # business, not another entity's name
                     "BUILDING"}
# Words that are never searched as a "rarest token": IPS-Integrated Project Services searched
# PROJECT and hit the page cap on every award group (full dry run, 2026-09-13).
SEARCH_GENERIC = {"PROJECT", "PROJECTS", "MANAGEMENT", "ADVANTAGE", "WORLDWIDE", "SOLUTION",
                  "GENERAL", "BUILDING", "COMPANIES", "PRODUCTS", "ELECTRIC", "EXPRESS"}
JV_RE = re.compile(r"\b(?:J\s*V|JOINT\s+VENTURE)\b", re.I)
# Legal forms of licensed professional practices, as collapsed tokens ("P. C." -> PC).
PROFESSIONAL_FORMS = {"PC", "PLLC", "PA", "LLP", "CPA", "CPAS"}
# Words that make a recipient a public body or institution, which can share a place-name
# token with a company (CRETE) but can never be that company under a longer legal name.
PUBLIC_BODY_WORDS = {"CITY", "COUNTY", "TOWN", "TOWNSHIP", "VILLAGE", "STATE", "DISTRICT",
                     "AUTHORITY", "SCHOOL", "SCHOOLS", "UNIVERSITY", "COLLEGE", "HOSPITAL",
                     "MEDICAL", "CENTER", "CLINIC", "CHURCH", "DEPARTMENT", "COMMISSION"}
BLOCK_RE = re.compile(r"web page blocked|the url you requested has been blocked", re.I)


class SourceError(RuntimeError):
    def __init__(self, message, failure_category="source_unavailable", fix_class="transient"):
        super().__init__(message)
        self.failure_category = failure_category
        self.fix_class = fix_class


# ------------------------------------------------------------------ identity
def norm_tokens_raw(name: str) -> list[str]:
    """Upper-case tokens with runs of single letters collapsed ("C.R. England" -> CR ENGLAND,
    "J E DUNN" -> JE DUNN, "R+L" -> RL, "P. C." -> PC), legal-form words KEPT -- the
    professional-practice test needs to see them before they are stripped."""
    raw = re.sub(r"\(.*?\)", " ", str(name or ""))
    raw = re.sub(r"[^A-Za-z0-9 ]+", " ", raw.upper().replace("'", ""))
    out, run = [], ""
    for t in raw.split():
        if len(t) == 1 and t.isalpha():
            run += t
            continue
        if run:
            out.append(run)
            run = ""
        out.append(t)
    if run:
        out.append(run)
    return out


def norm_tokens(name: str) -> list[str]:
    """norm_tokens_raw with legal-form words removed, so initials compare as one token on
    both sides and INC / LLC / CORPORATION never decide a match."""
    return [t for t in norm_tokens_raw(name) if t not in STOPWORDS]


def distinctive(name: str) -> list[str]:
    return [t for t in norm_tokens(name) if t not in WEAK_TOKENS]


def is_common_word_name(name: str) -> bool:
    d = distinctive(name)
    return len(d) == 1 and (d[0].lower() in COMMON_WORD_NAMES or d[0].lower() in LOCAL_COMMON_WORDS)


def name_matches(company: str, recipient: str) -> tuple[bool, str]:
    """(match, reason). The rule in the module docstring, step 2."""
    if JV_RE.search(recipient):
        return False, "joint_venture: a JV is a separate legal entity, not the company"
    # Checked on the RAW name, before norm_tokens strips legal forms as stopwords. The first
    # dry run (2026-09-13) accepted "WALSH & COMPANY, P. C." for The Walsh Group: "P. C."
    # collapsed to the stopword PC, leaving the one token WALSH, and the firm is in Illinois.
    # A professional corporation is a licensed practice (accounting, law, medicine); the
    # buyer universe excludes professional-service firms by definition (a law firm is
    # Jacob's disqualifying example), so this is an identity refusal, not a threshold.
    raw_forms = set(norm_tokens_raw(recipient))
    if raw_forms & PROFESSIONAL_FORMS:
        return False, (f"professional_practice: legal form {sorted(raw_forms & PROFESSIONAL_FORMS)} "
                       f"is a licensed practice, not an operating company in this universe")
    comp = distinctive(company)
    if not comp:
        return False, "company name has no distinctive token"
    parts = [p for p in re.split(r"\s+(?:dba|d/b/a|doing business as)\s+", recipient, flags=re.I) if p.strip()]
    near, overlap = False, False
    common = is_common_word_name(company)
    for part in parts:
        cand = norm_tokens(part)
        if not cand:
            continue
        if set(comp) & set(cand):
            overlap = True
        # A NEAR-MISS is a recipient that could be the company under a longer legal name: it
        # carries every distinctive company token and fails only on extra words (KENCO
        # HYDRAULICS, WALSH FEDERAL LLC, "F.H. PASCHEN, S.N. NIELSEN & ASSOCIATES"). A
        # one-token company must LEAD the recipient name. Sharing one token anywhere is not
        # enough: the first full dry run (2026-09-13) blocked clean absences on COLLIN
        # MCSHANE (a person), CATERING CAJUN LLC and NICHOLAS PETERSON. A common-word company
        # has no near-miss class at all -- only its exact name identifies it.
        # "Leads" skips leading initials: W. W. CLYDE & CO. (Clyde Companies' operating
        # subsidiary, same dry run) starts with WW, and without the skip it would have read
        # as a harmless partial overlap and let Clyde record a false absence.
        lead = next((t for t in cand if len(t) > 2), cand[0])
        # A public body or institution cannot be the company under a longer legal name:
        # CRETE AREA MEDICAL CENTER blocked Crete Carrier's absence in the same dry run
        # because CRETE is also a Nebraska town.
        institution = bool(set(cand) & PUBLIC_BODY_WORDS)
        if (not common and not institution and all(k in cand for k in comp)
                and (len(comp) >= 2 or lead == comp[0])):
            near = True
        if common:
            # one dictionary word: the whole name, weak words included, must be the whole
            # recipient name -- "PRIME INC" is Prime Inc., "PRIME TRUCKING" is not provably
            if norm_tokens(company) == cand:
                return True, "exact full-name match (common-word name)"
            continue
        if not all(k in cand for k in comp):
            continue
        extras = [c for c in cand if c not in comp]
        bad = [e for e in extras if e not in WEAK_TOKENS and e not in GENERIC_ORG_WORDS]
        # A name that reduces to ONE distinctive token (usually a surname) is backed by its
        # own line-of-business word when it has one: the full dry run accepted ANDERSON
        # HOLDINGS LLC and ANDERSON & ANDERSON, INC for Anderson Trucking Service, whose name
        # is ANDERSON once TRUCKING and the parenthetical drop out. CLARK CONSTRUCTION LLC
        # carries CONSTRUCTION and still passes; a name with no such word (Midmark, Gilbane,
        # The Walsh Group) is unaffected.
        lob = [t for t in norm_tokens(company) if t in WEAK_TOKENS]
        if len(comp) == 1 and lob and not any(t in cand for t in lob):
            continue
        if not bad:
            return True, "all distinctive tokens present; extras are line-of-business/legal words"
    if near:
        return False, "near_miss: carries every distinctive token but fails the all-token rule"
    if overlap:
        return False, "partial_overlap: shares a token but could not be the company under a longer name"
    return False, "no distinctive token in common"


# ------------------------------------------------------------------ source
def _call(cache: DatedCache, method: str, path: str, body: dict | None, key: str) -> dict:
    fp = hashlib.sha1(json.dumps([method, path, body], sort_keys=True).encode()).hexdigest()[:16]
    # Convention 36: the cache key carries a fingerprint of the request, so a changed query
    # can never replay yesterday's answer under the same name.

    def fetch() -> str:
        delay = 4.0
        for attempt in range(4):
            try:
                if method == "POST":
                    r = requests.post(API + path, json=body, timeout=TIMEOUT,
                                      headers={"User-Agent": UA, "Content-Type": "application/json"})
                else:
                    r = requests.get(API + path, timeout=TIMEOUT, headers={"User-Agent": UA})
            except requests.exceptions.RequestException as e:
                if attempt == 3:
                    raise SourceError(f"{type(e).__name__}: {str(e)[:160]}")
                time.sleep(delay)
                delay *= 2
                continue
            if r.status_code in (429, 502, 503, 504) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            if BLOCK_RE.search(r.text[:4000]):
                raise SourceError(access_detail(
                    "source_refusal", f"USASpending WAF block page (HTTP {r.status_code}) for {path}"),
                    failure_category="access_blocked", fix_class="source_limitation")
            if 400 <= r.status_code < 500:
                # A 4xx other than 429 is USASpending rejecting OUR request (the first dry
                # run sent a sort key the loan mapping does not have). That is a harness
                # defect, not the source being unavailable, and must not read as transient.
                raise SourceError(f"HTTP {r.status_code} from USASpending {path}: {r.text[:160]}",
                                  failure_category="source_drift_detected", fix_class="code_change")
            if r.status_code >= 500:
                raise SourceError(f"HTTP {r.status_code} from USASpending {path}: {r.text[:160]}")
            if "json" not in r.headers.get("Content-Type", "").lower():
                raise SourceError(f"non-JSON {r.headers.get('Content-Type')!r} from {path} -- a "
                                  f"failure, never an empty result", failure_category="source_drift_detected",
                                  fix_class="code_change")
            return r.text
        raise SourceError(f"USASpending {path} did not answer after retries")

    payload, _ = cache.get(f"{slug(key, 60)}_{fp}", ".json", fetch)
    return json.loads(payload)


def window(stamp: str) -> tuple[str, str]:
    end = _dt.date.fromisoformat(stamp)
    try:
        start = end.replace(year=end.year - STALENESS_YEARS)
    except ValueError:                        # 29 February
        start = end.replace(year=end.year - STALENESS_YEARS, day=28)
    return start.isoformat(), end.isoformat()


FIELDS = ["Award ID", "Recipient Name", "Recipient UEI", "recipient_id", "Recipient Location",
          "Award Amount", "Start Date", "Awarding Agency", "NAICS", "PSC", "Description",
          "generated_internal_id"]
ASSIST_FIELDS = ["Award ID", "Recipient Name", "Recipient UEI", "recipient_id", "Recipient Location",
                 "Award Amount", "Start Date", "Awarding Agency", "CFDA Number", "Description",
                 "generated_internal_id"]
# Loans carry "Loan Value" / "Subsidy Cost" instead of "Award Amount", and the search
# endpoint refuses a sort key the group's mapping lacks (HTTP 400, first dry run 2026-09-13).
LOAN_FIELDS = ["Award ID", "Recipient Name", "Recipient UEI", "recipient_id", "Recipient Location",
               "Loan Value", "Subsidy Cost", "Start Date", "Awarding Agency", "CFDA Number",
               "Description", "generated_internal_id"]
GROUP_FIELDS = {"contracts": FIELDS, "idvs": FIELDS, "grants": ASSIST_FIELDS, "loans": LOAN_FIELDS}
GROUP_SORT = {"contracts": "Award Amount", "idvs": "Award Amount", "grants": "Award Amount",
              "loans": "Loan Value"}


def amt(a: dict) -> float:
    """The dollar figure of an award in either mapping (a loan's face value, not its subsidy cost)."""
    return float(a.get("Award Amount") or a.get("Loan Value") or 0)


def awards_by_text(cache, text: str, group: str, tp: list) -> tuple[list[dict], bool]:
    """(awards, capped) for one search text and one award-type group, largest first."""
    out, capped = [], False
    for page in range(1, MAX_PAGES + 1):
        body = {"filters": {"recipient_search_text": [text], "award_type_codes": GROUPS[group],
                            "time_period": tp},
                "fields": GROUP_FIELDS[group],
                "limit": PAGE_LIMIT, "page": page, "sort": GROUP_SORT[group], "order": "desc"}
        j = _call(cache, "POST", "/search/spending_by_award/", body, f"awards_{group}_{text}_p{page}")
        res = j.get("results") or []
        for a in res:
            a["_group"] = group
        out.extend(res)
        meta = j.get("page_metadata") or {}
        if not meta.get("hasNext"):
            break
        if page == MAX_PAGES:
            capped = True
    return out, capped


def counts_for_uei(cache, uei: str, tp: list) -> dict:
    j = _call(cache, "POST", "/search/spending_by_award_count/",
              {"filters": {"recipient_search_text": [uei], "time_period": tp}}, f"count_{uei}")
    return j.get("results") or {}


# ------------------------------------------------------------------ one company
def search_terms(company: dict, alias_reg: dict) -> list[str]:
    """query_variants (full name, minus legal suffix, human aliases) plus the name with
    stopwords and line-of-business words removed when that still leaves a coined name --
    "Kenco Group" returns nothing and "Kenco" returns KENCO recipients. Never a bare
    common word, never an initialism under five letters (convention 13's PLS lesson)."""
    name = re.sub(r"\(.*?\)", "", company["canonical_name"]).strip()
    terms = query_variants(name, aliases.variants_for(company["company_id"], alias_reg))
    if is_common_word_name(name):
        # query_variants strips the legal suffix, which turns "Prime Inc." into the bare
        # word "Prime" -- a search for every PRIME recipient in the country, capped at the
        # page limit, which buries the one that matters and floods the near-miss check.
        # Caught by core/tests/test_procurement.py before the first full run.
        terms = [t for t in terms if len(t.split()) >= 2]
    d = distinctive(name)
    if d and not is_common_word_name(name):
        core = " ".join(d)
        if len(d) >= 2 or len(d[0]) >= 5:
            terms.append(core)
    # USASpending's text search does not survive initials or in-name punctuation, measured
    # 2026-09-13: "J.R. Simplot" and "JR Simplot" return nothing while "Simplot" returns
    # J. R. SIMPLOT COMPANY (ID, 24 awards). Without this the harness would have written a
    # false absent_confirmed (convention 6a) for every such name. So for a name carrying
    # initials or punctuation, also search its longest distinctive token -- six letters or
    # more and not an ordinary word. Identity is still decided by name_matches and the
    # state gate; only recall widens.
    if len(d) >= 2 and (re.search(r"\b[A-Za-z]\.\s?[A-Za-z]\b|[.+&'\-]", name)):
        rare = sorted((t for t in d if len(t) >= 6 and t.isalpha()
                       and t.lower() not in COMMON_WORD_NAMES and t.lower() not in LOCAL_COMMON_WORDS
                       and t not in SEARCH_GENERIC),
                      key=len, reverse=True)
        if rare:
            terms.append(rare[0])
    return list(dict.fromkeys(t for t in terms if t))


def name_form(name: str) -> tuple:
    """A name reduced to its identifying tokens (legal forms and punctuation removed), for exact
    comparison against a source-record alias."""
    return tuple(norm_tokens(name))


def recipient_profile(cache, rid: str) -> dict:
    j = _call(cache, "GET", f"/recipient/{rid}/", None, f"profile_{rid}")
    loc = j.get("location") or {}
    return {"name": j.get("name"), "uei": j.get("uei"), "parent_name": j.get("parent_name"),
            "parent_uei": j.get("parent_uei"), "state": loc.get("state_code")}


def parent_names(cache, rid: str | None) -> list[str]:
    """SAM parent entity names from the recipient's USASpending profile. Both the child (-C) and
    parent (-P) levels of the same hash are read: W. G. YATES & SONS CONSTRUCTION COMPANY lists
    itself as parent at -P and THE YATES COMPANIES INC at -C (2026-09-14)."""
    if not rid:
        return []
    import re as _re
    base = _re.sub(r"-[CPR]$", "", rid)
    ids = [base + "-C", base + "-P"] if _re.search(r"-[CP]$", rid) else [rid]
    out = set()
    for i in ids:
        try:
            p = recipient_profile(cache, i)
        except SourceError:
            continue
        if p.get("parent_name"):
            out.add(p["parent_name"])
    return sorted(out)


def recipient_search(cache, text: str) -> list[dict]:
    j = _call(cache, "POST", "/recipient/", {"keyword": text, "award_type": "all", "limit": 50},
              f"recipients_{text}")
    return j.get("results") or []


def resolve_company(cache, company: dict, alias_reg: dict, tp: list) -> dict:
    name, hq = company["canonical_name"], company["_state"]
    groups: dict[str, dict] = {}
    capped_terms, terms = [], search_terms(company, alias_reg)
    for term in terms:
        for group in GROUPS:
            awards, capped = awards_by_text(cache, term, group, tp)
            if capped:
                capped_terms.append(f"{term}/{group}")
            for a in awards:
                key = a.get("Recipient UEI") or a.get("recipient_id") or a.get("Recipient Name")
                g = groups.setdefault(key, {"uei": a.get("Recipient UEI"), "recipient_id": a.get("recipient_id"),
                                            "names": set(), "states": set(), "awards": {}})
                g["names"].add(a.get("Recipient Name") or "")
                g["states"].add(((a.get("Recipient Location") or {}).get("state_code")) or "")
                g["awards"][a.get("generated_internal_id") or a.get("Award ID")] = a
    accepted, refused, near_same_state = [], [], []
    # v1.1 (2026-09-14): identity from SOURCE RECORDS for names the exact-token rule cannot see.
    # An alias counts only as an exact name form, and only if it was seeded from a source record
    # (data/company_aliases.json says which); a near-miss counts only when its own USASpending
    # profile names a SAM parent that passes identity for the company. Neither path rescues a
    # joint venture or a professional practice, and the HQ-state gate below still applies.
    entry = alias_reg.get(company["company_id"], {}) if alias_reg else {}
    alias_forms = {name_form(v) for v in entry.get("name_variants", []) if name_form(v)}
    not_forms = {name_form(v) for v in entry.get("not_variants", []) if name_form(v)}
    for key, g in groups.items():
        rname = sorted(g["names"])[0]
        ok, why = name_matches(name, rname)
        states = {s for s in g["states"] if s}
        rec = {"key": key, "name": rname, "uei": g["uei"], "states": sorted(states),
               "awards_seen": len(g["awards"]), "reason": why}
        if not ok and name_form(rname) in not_forms:
            rec["reason"] = ("confirmed_different_entity: listed under not_variants in "
                             "data/company_aliases.json by a human decision")
            refused.append(rec)
            continue
        if not ok and not why.startswith(("joint_venture", "professional_practice")):
            if alias_forms and name_form(rname) in alias_forms:
                ok, why = True, "exact form of a source-record alias (data/company_aliases.json)"
            elif why.startswith("near_miss") and hq and hq in states and g["uei"]:
                for pn in parent_names(cache, g["recipient_id"]):
                    if name_form(pn) != name_form(rname) and (
                            name_matches(name, pn)[0] or (alias_forms and name_form(pn) in alias_forms)):
                        ok, why = True, f"SAM parent entity {pn!r} on its USASpending recipient record is the company"
                        break
            rec["reason"] = why
        if not ok:
            if why.startswith("near_miss") and hq and hq in states:
                near_same_state.append(rec)
            else:
                # Every refusal is logged with its reason (conventions 7 and 12). The offline
                # replay of 2026-09-13 showed the professional-practice refusal of "WALSH &
                # COMPANY, P. C." leaving no trace, because this branch only kept near-miss
                # and JV reasons.
                refused.append(rec)
            continue
        if not hq:
            if len(distinctive(name)) >= 2:
                rec["reason"] += "; company HQ state unknown, accepted on a multi-token name"
                accepted.append((rec, g))
            else:
                rec["reason"] = "HQ state unknown and one distinctive token: location cannot corroborate"
                near_same_state.append(rec)
            continue
        if hq in states:
            rec["reason"] += f"; registered in {hq}, the company's HQ state"
            accepted.append((rec, g))
        else:
            rec["reason"] = f"name matches but registered in {sorted(states) or 'unknown state'}, not HQ {hq}: not counted"
            refused.append(rec)
    # v1.1: the ANCHOR check. When nothing was accepted but same-state near-misses block an
    # absence, look for the company's own registered entity in the recipient directory (a UEI
    # that passes identity, registered in the HQ state) and count its awards in the window. If
    # every anchor holds none, a near-miss WITHOUT a UEI is cleared: a name-only record is not a
    # registered entity, so it cannot be the company's. A near-miss that carries a UEI keeps
    # blocking (it could be an unlinked subsidiary -- W. W. CLYDE & CO. lists itself as its own
    # SAM parent), and the anchor evidence is recorded for a human.
    #
    # v1.2 (2026-09-14, Matthew's ruling): NO registered entity in the HQ state also clears them,
    # provided every identity-passing registered entity found ELSEWHERE holds no award in the window
    # (or there is none). A federal prime award requires a SAM registration, so a name-only record
    # cannot be the company's. Graham Construction: GRAHAM CONSTRUCTION SERVICES, INC. (MN, parent
    # GRAHAM GROUP LTD) holds none, so J.W. GRAHAM is cleared. Herzog Enterprises: HERZOG GROUP INC.
    # (CA) holds awards, so nothing is cleared and the question stays with a human.
    anchors, cleared, elsewhere = [], [], []
    if not accepted and near_same_state:
        seen = set()
        for term in terms:
            for r in recipient_search(cache, term):
                if not r.get("uei") or r["uei"] in seen:
                    continue
                if not (name_matches(name, r["name"])[0] or (alias_forms and name_form(r["name"]) in alias_forms)):
                    continue
                # v1.3: a human-confirmed different firm is not one of the company's registered
                # entities, here any more than among award recipients (Herzog Enterprises: HERZOG
                # GROUP INC., Compton CA, confirmed unrelated 2026-09-15).
                if name_form(r["name"]) in not_forms:
                    continue
                seen.add(r["uei"])
                prof = recipient_profile(cache, r["id"])
                n = sum(int(v or 0) for v in counts_for_uei(cache, r["uei"], tp).values())
                entry = {"name": r["name"], "uei": r["uei"], "state": prof.get("state"),
                         "parent": prof.get("parent_name"), "awards_in_window": n}
                if not prof.get("state") or (hq and prof["state"] != hq):
                    elsewhere.append(entry)
                    continue
                anchors.append(entry)
        why_clear = None
        if anchors and all(a["awards_in_window"] == 0 for a in anchors):
            why_clear = (f"cleared: the company's registered entity {anchors[0]['name']} "
                         f"(UEI {anchors[0]['uei']}, {anchors[0]['state']}) holds no award in the window, "
                         f"and a name-only record without a UEI cannot be that entity")
        elif not anchors and all(a["awards_in_window"] == 0 for a in elsewhere):
            where = ("; its registered entities elsewhere hold no award in the window: "
                     + ", ".join(f"{a['name']} (UEI {a['uei']}, {a['state'] or 'no location'})" for a in elsewhere)
                     if elsewhere else " or anywhere else")
            why_clear = ("cleared: the company has no registered (UEI-bearing) entity in its HQ state" + where
                         + "; a federal prime award requires a SAM registration, so a name-only record cannot be "
                         "the company's (v1.2, Matthew's ruling 2026-09-14)")
        if why_clear:
            keep = []
            for rec in near_same_state:
                if rec["uei"]:
                    keep.append(rec)
                else:
                    rec["reason"] = why_clear
                    cleared.append(rec)
            near_same_state = keep
            refused.extend(cleared)
    return {"terms": terms, "capped": capped_terms, "groups": len(groups), "accepted": accepted,
            "refused": refused, "near_same_state": near_same_state, "anchors": anchors,
            "cleared": cleared, "registered_elsewhere": elsewhere}


def latest_start(awards: list, end: str) -> str:
    """Most recent award start date on or before the retrieval date. An award may be dated to
    start in the future (Clark 2028-09-18, Caddell 2026-10-01 in the full dry run), and a
    publication date after retrieval breaks every staleness and composition rule."""
    return max((str(a.get("Start Date")) for a in awards
                if a.get("Start Date") and str(a.get("Start Date")) <= end), default="")


def money(x: float) -> str:
    return f"${x:,.0f}"


def build_rows(company: dict, res: dict, cache, tp: list, stamp: str) -> tuple[dict, dict]:
    """{signal: Observation or None} and a log entry with the counts."""
    name = company["canonical_name"]
    accepted = res["accepted"]
    ueis = sorted({r["uei"] for r, _ in accepted if r["uei"]})
    # Per-UEI totals from the count endpoint. Used to decide which groups to list and as a
    # FLOOR for a group whose listing hit the page cap -- never summed across UEIs: a parent
    # UEI's total already contains its children, so Lynden's parent (132) plus its accepted
    # child Lynden Logistics (2) read as 134 in the full dry run.
    per_uei = {u: counts_for_uei(cache, u, tp) for u in ueis}
    awards = {}
    for _, g in accepted:
        awards.update(g["awards"])
    # The text-search hits are whatever the NAME search happened to return (Lynden: 134
    # contracts by UEI, 2 by text, and a total over the 2). List each accepted UEI's own
    # awards so the totals, agencies and descriptions describe the counted awards.
    # A UEI search returns the awards of every entity REGISTERED UNDER that UEI as parent in
    # SAM (2026-09-13: Lynden Inc's UEI lists Lynden Air Cargo 69, Alaska Marine Lines 60,
    # Lynden Logistics 2, Knik Construction 1; JE Dunn's lists J. E. DUNN CONSTRUCTION
    # COMPANY 10). The parent link is the registrant's own declaration, a stronger identity
    # than a name match, so those awards are counted -- once, deduplicated on the award id --
    # and every such subsidiary is named in the row. Keeping only the searched UEI's own
    # awards left the totals describing 2 of Lynden's 132 contracts.
    capped_groups = set()
    for u in ueis:
        for group in GROUPS:
            if not int(per_uei[u].get(group) or 0):
                continue
            listed_u, capped = awards_by_text(cache, u, group, tp)
            if capped:
                res["capped"].append(f"UEI {u}/{group}")
                capped_groups.add(group)
            for a in listed_u:
                awards[a.get("generated_internal_id") or a.get("Award ID")] = a
    # The parent link establishes that an entity belongs to the company's family, not that
    # its award is the company's. A joint venture registered under the parent (ATKINSON/CLARK,
    # A JOINT VENTURE under Clark, fourth full dry run 2026-09-13) has partners; a professional
    # practice is not an operating company in this universe. Both are refused by name_matches,
    # and the family path must not let them back in. Excluded and counted, never dropped.
    family_excluded = Counter()
    for key in list(awards):
        a = awards[key]
        rname = str(a.get("Recipient Name") or "")
        if a.get("Recipient UEI") in ueis:
            continue
        if JV_RE.search(rname) or set(norm_tokens_raw(rname)) & PROFESSIONAL_FORMS:
            family_excluded[rname] += 1
            del awards[key]
    counts = Counter(a["_group"] for a in awards.values())
    for group in capped_groups:
        counts[group] = max(counts[group], max(int(per_uei[u].get(group) or 0) for u in ueis))
    family = Counter(a.get("Recipient Name") for a in awards.values()
                     if a.get("Recipient UEI") and a.get("Recipient UEI") not in ueis)
    no_uei = [r for r, _ in accepted if not r["uei"]]
    first = sorted(accepted, key=lambda p: (p[0]["uei"] or "~", p[0]["key"]))[0][0] if accepted else None
    rid = next((g["recipient_id"] for r, g in accepted if r is first), None)
    url = (f"https://www.usaspending.gov/recipient/{rid}/latest" if rid
           else "https://www.usaspending.gov/search")
    entities = "; ".join(f"{r['name']} (UEI {r['uei'] or 'none'}, {'/'.join(r['states'])})"
                         for r, _ in accepted)
    not_counted = [r for r in res["refused"] if not r["reason"].startswith("joint_venture")
                   and "not counted" in r["reason"]]
    floor_note = (f" {len(not_counted)} same-named registration(s) outside the HQ state were not "
                  f"counted, so the figures are floors." if not_counted else "")
    if family:
        floor_note += (" Includes awards to entities registered under the accepted UEI as parent "
                       "in SAM: " + ", ".join(f"{n} ({k})" for n, k in family.most_common(6)) + ".")
    if family_excluded:
        floor_note += (f" {sum(family_excluded.values())} award(s) to joint ventures or professional "
                       f"practices registered under the parent were not counted: "
                       + ", ".join(f"{n} ({k})" for n, k in family_excluded.most_common(4)) + ".")
    cap_note = (" The award listing hit its page cap for " + ", ".join(res["capped"]) +
                "; totals over listed awards are floors." if res["capped"] else "")
    conf = 0.85 if len(distinctive(name)) >= 2 else 0.75
    if not company["_state"]:
        conf = 0.65
    if any(not r["uei"] for r, _ in accepted):
        # A record with no UEI is a name and a state and nothing else (an SBA or Ex-Im entry
        # in the full dry run): identity is weaker than a registered entity's, so say so.
        conf = min(conf, 0.5)
        floor_note += (" One or more matched records carry no UEI, so identity rests on the "
                       "name and state alone.")
    rows, log = {}, {"counts": dict(counts), "ueis": ueis, "entities": entities}

    def listed(groups):
        return [a for a in awards.values() if a["_group"] in groups]

    # ---- contracts + IDVs ----
    n_con, n_idv = counts.get("contracts", 0), counts.get("idvs", 0)
    if n_con + n_idv:
        con = listed(("contracts",))
        total = sum(amt(a) for a in con)
        agencies = Counter(a.get("Awarding Agency") for a in con + listed(("idvs",)) if a.get("Awarding Agency"))
        naics = Counter(((a.get("NAICS") or {}).get("code") if isinstance(a.get("NAICS"), dict) else a.get("NAICS"))
                        for a in con if a.get("NAICS"))
        partial = " (over the listed awards)" if len(con) < n_con else ""
        latest = latest_start(con + listed(("idvs",)), tp[0]["end_date"])
        text = (f"{name} held {n_con} federal prime contract award(s) and {n_idv} indefinite-delivery "
                f"vehicle(s) with a transaction in the five years to {tp[0]['end_date']} (an award may have begun "
                f"earlier), a combined award value of {money(total)}{partial}, from {', '.join(f'{k} ({v})' for k, v in agencies.most_common(3))}. "
                f"Recipient: {entities}. A federal procurement record (IC3) in which the company is the "
                f"SELLER: it records federal contracting exposure, not the company's own modernization "
                f"posture, and routes to no theme.{floor_note}{cap_note}")
        top = sorted(con, key=lambda a: -amt(a))[:3]
        excerpt = " | ".join(f"{a.get('Award ID')}: {money(float(a.get('Award Amount') or 0))}, "
                             f"{a.get('Awarding Agency')}, start {a.get('Start Date')}, "
                             f"{str(a.get('Description') or '')[:120]}" for a in top)
        excerpt += f" | top NAICS: {', '.join(f'{k} ({v})' for k, v in naics.most_common(3))}"
        excerpt += f" | identity: {'; '.join(r['reason'] for r, _ in accepted)[:400]}"
        rows[SIG_CONTRACT] = Observation(
            company_id=company["company_id"], evidence_family=FAM_CONTRACT, evidence_role="buyer_acts",
            topic="federal_prime_contracts", organizational_state="unknown", signal_strength="measured_result",
            observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url, publication_date=latest,
            retrieval_date=stamp, source_grade="A", harness_id=HARNESS_ID, harness_version=VERSION,
            confidence_0_1=conf)
    # ---- assistance ----
    n_gr, n_ln = counts.get("grants", 0), counts.get("loans", 0)
    if n_gr + n_ln:
        ast = listed(ASSIST_GROUPS)
        total = sum(amt(a) for a in ast)
        latest = latest_start(ast, tp[0]["end_date"])
        value = money(total) if total else "not reported"
        text = (f"{name} received {n_gr} federal grant(s) and {n_ln} federal loan, loan-guarantee or "
                f"insurance award(s) as prime recipient with a transaction in the five years to "
                f"{tp[0]['end_date']}, a combined face value of {value} over the listed awards. Recipient: {entities}. A federal assistance record (IC3): capital the "
                f"company received, not a statement of its modernization posture.{floor_note}{cap_note}")
        excerpt = " | ".join(f"{a.get('Award ID')}: {money(float(a.get('Award Amount') or 0))}, "
                             f"{a.get('Awarding Agency')}, CFDA {a.get('CFDA Number')}, start {a.get('Start Date')}, "
                             f"{str(a.get('Description') or '')[:120]}"
                             for a in sorted(ast, key=lambda a: -amt(a))[:3])
        rows[SIG_ASSIST] = Observation(
            company_id=company["company_id"], evidence_family=FAM_ASSIST, evidence_role="buyer_acts",
            topic="federal_assistance_awards", organizational_state="unknown", signal_strength="measured_result",
            observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url, publication_date=latest,
            retrieval_date=stamp, source_grade="A", harness_id=HARNESS_ID, harness_version=VERSION,
            confidence_0_1=conf)
    log["no_uei_entities"] = [r["name"] for r in no_uei]
    return rows, log


# ------------------------------------------------------------------ run
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
    ap.add_argument("--pause", type=float, default=0.25)
    ap.add_argument("--show-rows", action="store_true",
                    help="print every proposed row in full, for reading before a commit")
    args = ap.parse_args()

    db = MarketIntelDB()
    buyers = [c for c in db.companies() if c.get("qualification_status") != "provider_benchmark"]
    if args.companies:
        want = {x.strip() for x in args.companies.split(",")}
        buyers = [c for c in buyers if c["company_id"] in want]
    for c in buyers:
        c["_state"] = state_code(str(c.get("hq_state") or ""))
    stamp = today()
    start, end = window(stamp)
    tp = [{"start_date": start, "end_date": end}]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=args.pause)
    alias_reg = aliases.load()
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=FAM_CONTRACT,
                      scope=[(c["company_id"], s) for c in buyers for s in (SIG_CONTRACT, SIG_ASSIST)],
                      signal_families={SIG_CONTRACT: FAM_CONTRACT, SIG_ASSIST: FAM_ASSIST},
                      commit=args.commit)
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp, "offline": args.offline,
           "window": tp[0], "companies": []}
    if not args.offline:
        ok, why = RobotsGate().check(API + "/search/spending_by_award/")
        log["robots"] = {"ok": ok, "reason": why}
        if not ok:
            print(f"ROBOTS REFUSED: {why}")
            return 2
    print(f"{HARNESS_ID} {VERSION} -- {len(buyers)} buyers, window {start}..{end} "
          f"({'offline' if args.offline else 'live'})\n")

    proposed: list[Observation] = []
    for c in sorted(buyers, key=lambda x: x["company_id"]):
        cid, name = c["company_id"], c["canonical_name"]
        entry = {"company_id": cid, "name": name, "hq_state": c["_state"]}
        try:
            res = resolve_company(cache, c, alias_reg, tp)
            rows, extra = build_rows(c, res, cache, tp, stamp) if res["accepted"] else ({}, {})
        except (SourceError, RuntimeError) as e:
            cat = getattr(e, "failure_category", "source_unavailable")
            fix = getattr(e, "fix_class", "transient")
            for sig in (SIG_CONTRACT, SIG_ASSIST):
                run.attempt(cid, sig, outcome="not_covered", failure_stage="fetch", failure_category=cat,
                            fix_class=fix, failure_detail=str(e)[:500], source_url_attempted=API)
            entry["error"] = str(e)[:300]
            log["companies"].append(entry)
            print(f"  [--] {cid} {name}: {str(e)[:120]}")
            continue
        entry.update({"terms": res["terms"], "recipient_groups_seen": res["groups"],
                      "accepted": [r for r, _ in res["accepted"]], "refused": res["refused"],
                      "near_same_state": res["near_same_state"], "capped": res["capped"],
                      "anchors": res.get("anchors", []), "cleared": res.get("cleared", []),
                      "registered_elsewhere": res.get("registered_elsewhere", []), **extra})
        cand_n = res["groups"]
        for sig in (SIG_CONTRACT, SIG_ASSIST):
            obs = rows.get(sig)
            if obs:
                proposed.append(obs)
                run.attempt(cid, sig, outcome="covered", records_written=1, source_url_attempted=obs.source_url,
                            candidates_evaluated=cand_n, candidates_discarded=cand_n - len(res["accepted"]))
            elif res["accepted"]:
                # The company resolved to a recipient and the source is complete for prime
                # awards: no award of this kind in the window is a read result.
                run.attempt(cid, sig, outcome="absent_confirmed", source_url_attempted=API,
                            candidates_evaluated=cand_n, candidates_discarded=cand_n - len(res["accepted"]))
            elif res["near_same_state"]:
                run.attempt(cid, sig, outcome="not_covered", failure_stage="entity_resolution",
                            failure_category="entity_below_threshold", fix_class="source_limitation",
                            failure_detail=("no recipient passed identity; "
                                            + (f"registered entity {res['anchors'][0]['name']} (UEI {res['anchors'][0]['uei']}) "
                                               f"holds {res['anchors'][0]['awards_in_window']} award(s); " if res.get("anchors") else
                                               "no registered entity of the company found; ")
                                            + "same-state near-miss(es) with a UEI that may be the company or an "
                                            "unlinked subsidiary (a decision for a human): "
                                            + "; ".join(f"{r['name']} [{'/'.join(r['states'])}] {r['reason'][:60]}"
                                                        for r in res["near_same_state"][:4]))[:500],
                            source_url_attempted=API, candidates_evaluated=cand_n, candidates_discarded=cand_n)
            else:
                run.attempt(cid, sig, outcome="absent_confirmed", source_url_attempted=API,
                            candidates_evaluated=cand_n, candidates_discarded=cand_n)
        mark = "ok" if rows else ("00" if not res["near_same_state"] else "??")
        detail = (extra.get("counts") if rows else
                  (f"near-miss {[r['name'] for r in res['near_same_state']][:3]}" if res["near_same_state"]
                   else f"no awarded recipient bears the name ({res['groups']} recipient(s) seen, "
                        f"{len(res['refused'])} refused)"))
        print(f"  [{mark}] {cid} {name} ({c['_state'] or '??'}): {detail}")
        log["companies"].append(entry)

    if args.show_rows:
        for o in proposed:
            print()
            print(f"  ---- {o.company_id} {o.topic} conf={o.confidence_0_1} pub={o.publication_date}")
            print(f"  TEXT: {o.observation_text}")
            print(f"  EXCERPT: {o.evidence_excerpt}")
            print(f"  URL: {o.source_url}")
    report = db.sync_observations(proposed)
    run.observations_written = report.written
    summary = run.close()
    print(f"\n  {len(buyers)} buyers - {len(proposed)} observations - {cache.fetch_count} API calls")
    print(f"  attempts: {summary['attempts_covered']} covered, {summary['attempts_absent_confirmed']} "
          f"absent_confirmed, {summary['attempts_not_covered']} not_covered (of {summary['attempts_total']})")
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
