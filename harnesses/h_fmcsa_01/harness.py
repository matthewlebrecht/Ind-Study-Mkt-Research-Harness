"""
H-FMCSA-01 — FMCSA Carrier Registry & Safety Extractor
======================================================

The project's first baseline harness. Chosen as the opener because it is the cleanest
possible test of the pipeline shape: a federal registry, ownership-agnostic (private
mid-size carriers are as visible as public ones), structured, attributable, and free.

Pipeline
--------
    Companies sheet -> resolve name to USDOT number(s) -> fetch carrier snapshot
                    -> derive atomic observations -> validate -> Observations sheet
                                                              -> Harness_Runs summary

The hard part is step 2, not step 3. FMCSA has ~4.5M registrants and no name index worth
trusting: "Western Express" substring-matches SOUTHWESTERN EXPRESS, a single company can
hold five active USDOT numbers, and the operating entity's registered name often shares
no token with the brand ("Mack Group" files as MACK MOLDING COMPANY INC). So resolution
is scored and tiered rather than assumed, low-confidence matches are refused rather than
guessed, and every decision is written to the run log for human review.

Evidence mapping (documented so a reviewer can argue with it)
-------------------------------------------------------------
    evidence_role      Always buyer_acts. A federal filing records what a company does,
                       never what it says about modernization.
    signal_strength    Registry descriptors (fleet size, authority, cargo) = weak_clue:
                       they are baseline facts, not modernization posture. Outcomes
                       measured over a 24-month window (out-of-service rates, crashes)
                       = measured_result. Repeated structure across entities
                       = repeated_pattern.
    organizational_state
                       unknown by default. legacy_constraint only where a measured
                       outcome is materially worse than the national average, or where
                       an active carrier has let its own registry record go stale — both
                       are observable operational strain, not inferred intent.
    source_grade       A. Primary, attributable, and re-checkable at a stable URL.

Usage
-----
    python harnesses/fmcsa_harness.py                 # dry run, prints what it would write
    python harnesses/fmcsa_harness.py --commit        # writes to market_intel_db.xlsx
    python harnesses/fmcsa_harness.py --offline       # replay from cached responses only
    python harnesses/fmcsa_harness.py --include-excluded
    python harnesses/fmcsa_harness.py --companies C0004,C0006
    python harnesses/fmcsa_harness.py --commit --force-rewrite   # discard+rebuild unreviewed rows

Re-running is safe: writes go through db.sync_observations(), which reconciles against
what is already in the sheet rather than appending blindly. A row a human has reviewed is
never overwritten — a changed claim on a reviewed row is reported as a conflict instead.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import topics  # noqa: E402
from core.db import MarketIntelDB, Observation, HarnessRun, today  # noqa: E402
from harnesses.h_fmcsa_01.source import (  # noqa: E402
    FmcsaClient, safer_snapshot_url, CENSUS_LANDING,
)

HARNESS_ID = "H-FMCSA-01"
HARNESS_NAME = "FMCSA Carrier Registry & Safety Extractor"
HARNESS_VERSION = "v1.6"
TARGET_EVIDENCE_FAMILY = "10_logistics_supply_network"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
ALIAS_PATH = Path(__file__).resolve().parent / "aliases.json"

# --- tunable thresholds (all quality gates are named, not buried in an if) ---
MIN_SCORE_TO_ACCEPT = 55          # below this the harness refuses to guess
MIN_INSPECTIONS_FOR_RATE = 20     # an OOS % on <20 inspections is noise, not a result
MIN_FLEET_FOR_CRASH_RATE = 20     # 1 crash on a 2-truck fleet is not "50 per 100 units"
STALE_MCS150_MONTHS = 24          # biennial MCS-150 update is a federal requirement
WORKFORCE_CONFLICT_RATIO = 0.25   # registry vs. Companies-sheet disagreement worth logging

_LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "L L C", "LLP", "LP", "LTD", "CO", "CORP",
    "CORPORATION", "COMPANY", "GROUP", "HOLDINGS", "THE", "USA", "US",
}


# ----------------------------------------------------------------------------
# name normalization + resolution
# ----------------------------------------------------------------------------

def normalize(name: str) -> list[str]:
    """Uppercase, strip punctuation, drop legal-form suffixes -> comparable tokens."""
    cleaned = re.sub(r"[^A-Z0-9 ]+", " ", (name or "").upper())
    tokens = [t for t in cleaned.split() if t and t not in _LEGAL_SUFFIXES]
    return tokens


def dba_variants(dba_name: str | None) -> list[str]:
    """FMCSA packs multiple DBAs into one comma-separated field."""
    if not dba_name:
        return []
    return [part.strip() for part in str(dba_name).split(",") if part.strip()]


def _months_since(date_str: str | None, relative_to: str | None = None) -> float | None:
    """Months between date_str and a reference date. Accepts MM/DD/YYYY or YYYYMMDD.

    `relative_to` should be the source snapshot's own "as of" date whenever the result
    ends up inside an observation. Measuring against today would make the row's text
    drift every time the harness runs, so an unchanged fact would conflict against its
    own stored row forever. Resolution scoring passes nothing and measures against today,
    which is correct there — it is ranking candidates now, not stating a fact.
    """
    def _parse(value):
        s = str(value).strip()
        for fmt in ("%m/%d/%Y", "%Y%m%d"):
            try:
                return dt.datetime.strptime(s[:10 if "/" in s else 8], fmt).date()
            except ValueError:
                continue
        return None

    if not date_str:
        return None
    parsed = _parse(date_str)
    if parsed is None:
        return None
    reference = _parse(relative_to) if relative_to else dt.date.today()
    if reference is None:
        reference = dt.date.today()
    return (reference - parsed).days / 30.44


def _count(n, noun: str) -> str:
    """'3,332 power units' / '1 driver' / 'n/a drivers' — reviewer-facing prose."""
    if n is None:
        return f"n/a {noun}s"
    return f"{n:,} {noun}" + ("" if n == 1 else "s")


def _iso(date_str: str | None) -> str:
    """Normalize a source date to ISO, or return '' if unparseable."""
    if not date_str:
        return ""
    s = str(date_str).strip()
    for fmt in ("%m/%d/%Y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s[:10 if "/" in s else 8], fmt).date().isoformat()
        except ValueError:
            continue
    return ""


@dataclass
class Candidate:
    row: dict
    score: int = 0
    matched_on: str = ""

    @property
    def dot(self) -> str:
        return str(self.row.get("dot_number", ""))

    @property
    def legal_name(self) -> str:
        return str(self.row.get("legal_name") or "")

    @property
    def city(self) -> str:
        return str(self.row.get("phy_city") or "").upper()

    @property
    def power_units(self) -> int:
        try:
            return int(self.row.get("power_units") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def active(self) -> bool:
        return str(self.row.get("status_code") or "").upper() == "A"


def score_candidate(company_tokens: list[str], cand: Candidate) -> tuple[int, str]:
    """Score a census row against a company's name tokens.

    Token-level comparison, not substring: this is what stops SOUTHWESTERN EXPRESS from
    matching Western Express, which a LIKE query cannot do.
    """
    best, how = 0, ""
    names = [(cand.legal_name, "legal_name")] + [
        (v, "dba_name") for v in dba_variants(cand.row.get("dba_name"))
    ]
    for raw, source in names:
        toks = normalize(raw)
        if not toks:
            continue
        if toks == company_tokens:
            base, label = 100, "exact"
        elif toks[:len(company_tokens)] == company_tokens:
            base, label = 80, "prefix"          # KENCO LOGISTIC SERVICES vs Kenco
        elif company_tokens[:len(toks)] == toks:
            base, label = 70, "truncated"       # registrant name is shorter than brand
        elif set(company_tokens) <= set(toks):
            base, label = 55, "token_subset"    # all our tokens present, out of order
        else:
            continue
        if base > best:
            best, how = base, f"{label}:{source}"

    if not best:
        return 0, "no_token_match"

    score = best
    score += 8 if cand.active else -15
    score += 5 if cand.power_units > 0 else 0
    age = _months_since(cand.row.get("mcs150_date"))
    if age is None:
        score -= 5
    elif age <= 36:
        score += 5
    elif age > 96:
        score -= 5
    return score, how


def confidence_for(score: int) -> float:
    if score >= 95:
        return 0.90
    if score >= 80:
        return 0.80
    return 0.65


@dataclass
class Resolution:
    company_id: str
    canonical_name: str
    primary: Candidate | None = None
    family: list[Candidate] = field(default_factory=list)
    confidence: float = 0.0
    search_terms: list[str] = field(default_factory=list)
    candidates_seen: int = 0
    rejected_examples: list[str] = field(default_factory=list)
    note: str = ""


def resolve_company(client: FmcsaClient, company: dict, aliases: dict) -> Resolution:
    company_id = company["company_id"]
    canonical = str(company.get("canonical_name") or "")
    state = str(company.get("hq_state") or "").strip() or None
    tokens = normalize(canonical)

    alias_entry = aliases.get(company_id, {}) if isinstance(aliases.get(company_id), dict) else {}
    variants = alias_entry.get("name_variants", [])
    seeds = [str(s) for s in alias_entry.get("usdot_seed", [])]

    res = Resolution(company_id=company_id, canonical_name=canonical)

    # A human-verified USDOT seed short-circuits scoring entirely.
    if seeds:
        rows = []
        for dot in seeds:
            rows += client.census_search(dot, None, limit=1) or []
        if rows:
            res.primary = Candidate(rows[0], score=100, matched_on="usdot_seed")
            res.confidence = 0.90
            res.note = "resolved from human-verified USDOT seed"
            return res

    # Candidate generation: the full name, then progressively looser terms.
    search_terms: list[str] = []
    if tokens:
        search_terms.append(" ".join(tokens))
        if len(tokens) > 1:
            search_terms.append(tokens[0])
    search_terms += [" ".join(normalize(v)) for v in variants]
    res.search_terms = search_terms

    seen: dict[str, Candidate] = {}
    for term in search_terms:
        if not term:
            continue
        for row in client.census_search(term, state, limit=50):
            dot = str(row.get("dot_number", ""))
            if dot and dot not in seen:
                seen[dot] = Candidate(row)
    res.candidates_seen = len(seen)

    # Score against the canonical name and every alias variant; keep the best.
    scored: list[Candidate] = []
    token_sets = [tokens] + [normalize(v) for v in variants]
    for cand in seen.values():
        best_score, best_how = 0, ""
        for ts in token_sets:
            if not ts:
                continue
            s, how = score_candidate(ts, cand)
            if s > best_score:
                best_score, best_how = s, how
        cand.score, cand.matched_on = best_score, best_how
        if best_score >= MIN_SCORE_TO_ACCEPT:
            scored.append(cand)
        elif best_score > 0:
            res.rejected_examples.append(f"{cand.legal_name} (DOT {cand.dot}, score {best_score})")

    if not scored:
        res.note = "no candidate cleared the acceptance threshold"
        res.rejected_examples = res.rejected_examples[:5]
        return res

    scored.sort(key=lambda c: (c.score, c.power_units, -(_months_since(
        c.row.get("mcs150_date")) or 999)), reverse=True)
    res.primary = scored[0]
    res.confidence = confidence_for(res.primary.score)

    # Corporate family = same city as the primary registrant. City is what separates
    # the real Kenco entities (Chattanooga) from an unrelated KENCO in Nashville.
    res.family = [c for c in scored[1:] if c.city and c.city == res.primary.city and c.active]
    return res


# ----------------------------------------------------------------------------
# observation construction
# ----------------------------------------------------------------------------

class ObservationBuilder:
    def __init__(self, company: dict, resolution: Resolution, snapshot: dict):
        self.company = company
        self.res = resolution
        self.snap = snapshot
        self.dot = str(snapshot.get("dot_number") or resolution.primary.dot)
        self.url = safer_snapshot_url(self.dot)
        self.entity = snapshot.get("legal_name") or resolution.primary.legal_name
        self.as_of = _iso(snapshot.get("data_as_of"))
        self.skipped: list[str] = []

    def _obs(self, family, topic, state, strength, text, excerpt,
             pub_date, confidence, low_grade: str = "") -> Observation:
        """`low_grade` names a relaxed corroboration-strength gate (2026-09-03 policy):
        the row is written at grade C / weak_clue / confidence <= 0.4 with the marker,
        where v1.3 refused it. The registry record itself is still an A-grade source;
        the grade marks the claim's tier for the review layer."""
        source_grade = "A"
        if low_grade:
            source_grade, strength = topics.LOW_GRADE, "weak_clue"
            confidence = min(confidence, topics.LOW_GRADE_CONFIDENCE_MAX)
            excerpt = topics.low_grade_excerpt(low_grade, excerpt)
        return Observation(
            company_id=self.company["company_id"],
            evidence_family=family,
            evidence_role="buyer_acts",
            topic=topic,
            organizational_state=state,
            signal_strength=strength,
            observation_text=text,
            evidence_excerpt=excerpt,
            source_url=self.url,
            publication_date=pub_date,
            retrieval_date=today(),
            source_grade=source_grade,
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            confidence_0_1=round(confidence, 2),
        )

    def _is_private_carriage(self) -> bool:
        """True when the registrant hauls its own freight rather than for hire.

        FMCSA's "NOT AUTHORIZED" operating-authority status means the registrant holds no
        *for-hire* authority. For a private fleet that is definitionally true and tells us
        nothing. For a carrier that classifies itself as for-hire, the same value means
        authority is lapsed, revoked, or not yet granted — a real operational signal. So
        the two cases must be told apart before either is written down.
        """
        classes = [c.lower() for c in (self.snap.get("operation_classification") or [])]
        if not classes:
            # Session 10 item 6 (F15/F26): with no classification parsed -- the QCMobile
            # path until v1.5 returned [] -- the question is UNKNOWN, not "for hire".
            return None
        # SAFER writes "Auth. For Hire" / "Exempt For Hire" / "Private(Property)";
        # QCMobile's operation-classification endpoint writes "Authorized For Hire" /
        # "Exempt For Hire" / "Private Property". Session 14: match on the phrase both
        # spell the same way, so the answer does not depend on which path served it.
        if any("for hire" in c for c in classes):
            return False
        return any("private" in c for c in classes)

    def build(self) -> list[Observation]:
        out: list[Observation] = []
        for emitter in (self.fleet_scale, self.operating_model, self.vehicle_oos,
                        self.driver_oos, self.crash_exposure, self.registry_maintenance,
                        self.workforce_conflict, self.for_hire_authority_gap,
                        self.multi_entity_structure):
            obs = emitter()
            if obs:
                out.append(obs)
        return out

    # -- individual emitters; each returns one atomic claim or None --

    def fleet_scale(self):
        pu, drivers = self.snap.get("power_units"), self.snap.get("drivers")
        if pu is None and drivers is None:
            self.skipped.append(f"fleet_scale not emitted for USDOT {self.dot}: neither "
                                f"power units nor drivers parsed from the snapshot")
            return None
        if not pu and not drivers:
            # A broker or dormant registrant has no fleet to describe. v1.3 refused this
            # as noise; the 2026-09-03 policy writes it at low grade -- the referent is
            # right and the nil return is the registrant's own -- and the reviewer sifts.
            text = (f"{self.entity} (USDOT {self.dot}) reports no power units and no "
                    f"drivers to FMCSA on its MCS-150 of {self.snap.get('mcs150_date')}: "
                    f"a nil fleet return, consistent with a broker, a holding entity or a "
                    f"dormant registration. Scale context only.")
            return self._obs("10_logistics_supply_network", "fleet_scale", "unknown",
                             "weak_clue", text,
                             f"Power Units: {pu} | Drivers: {drivers}",
                             _iso(self.snap.get("mcs150_date")), 0.4,
                             low_grade="nil fleet return (0 power units, 0 drivers)")
        mcs_date = self.snap.get("mcs150_date")
        age = _months_since(mcs_date, self.snap.get("data_as_of"))
        conf = self.res.confidence
        if age and age > STALE_MCS150_MONTHS:
            conf -= 0.10  # self-reported figure, and the company hasn't refreshed it
        miles = self.snap.get("mcs150_mileage")
        miles_txt = (f", and reported {miles:,} miles for "
                     f"{self.snap.get('mcs150_mileage_year')}") if miles else ""
        text = (f"{self.entity} (USDOT {self.dot}) reports a fleet of "
                f"{_count(pu, 'power unit')} and {_count(drivers, 'driver')} to FMCSA"
                f"{miles_txt}, per an MCS-150 filing dated {mcs_date}.")
        excerpt = (f"Power Units: {pu} | Drivers: {drivers} | "
                   f"MCS-150 Form Date: {mcs_date} | "
                   f"MCS-150 Mileage (Year): {self.snap.get('mcs150_mileage_raw')}")
        return self._obs("8_physical_footprint_capacity", "fleet_scale", "unknown",
                         "weak_clue", text, excerpt, _iso(mcs_date), conf)

    def operating_model(self):
        pu = self.snap.get("power_units") or 0
        authority = self.snap.get("authorized_for") or ""
        entity_type = self.snap.get("entity_type") or ""
        op_class = ", ".join(self.snap.get("operation_classification") or []) or "n/a"
        cargo = self.snap.get("cargo_carried") or []
        if not authority and not entity_type:
            self.skipped.append(f"operating_model not emitted for USDOT {self.dot}: neither "
                                f"authority nor entity type parsed from the snapshot")
            return None
        if pu == 0 and "Broker" in authority:
            model = ("operates as a non-asset intermediary: it holds broker authority "
                     "and reports zero power units")
            strength = "committed_action"
        elif pu > 0:
            model = (f"operates an asset-based fleet ({_count(pu, 'power unit')}) "
                     f"under {op_class} classification")
            strength = "weak_clue"
        else:
            model = f"holds FMCSA registration as {entity_type} with zero reported power units"
            strength = "weak_clue"
        cargo_txt = (f" Declared cargo categories: {', '.join(cargo[:6])}"
                     f"{' (+%d more)' % (len(cargo) - 6) if len(cargo) > 6 else ''}."
                     if cargo else "")
        # For a private or intrastate-only carrier, FMCSA reports "NOT AUTHORIZED" and
        # says so on the page: the status refers to *for-hire* authority, which a private
        # fleet is not supposed to hold. Reporting it as absent authority would read as a
        # deficiency; it is the expected state and carries no signal.
        if self._is_private_carriage():
            authority_txt = ("no for-hire operating authority, which FMCSA reports as "
                             "\"NOT AUTHORIZED\" — the expected status for private "
                             "carriage, not a compliance deficiency")
        else:
            authority_txt = authority or "none listed"
        text = (f"{self.entity} (USDOT {self.dot}) {model}. FMCSA entity type: "
                f"{entity_type}; operating authority: {authority_txt}."
                f"{cargo_txt}")
        excerpt = (f"Entity Type: {entity_type} | Operating Authority Status: "
                   f"{self.snap.get('operating_authority_status')} | AUTHORIZED FOR: "
                   f"{authority} | Power Units: {pu} | Operation Classification: {op_class}")
        return self._obs(TARGET_EVIDENCE_FAMILY, "operating_model", "unknown",
                         strength, text, excerpt, self.as_of, self.res.confidence)

    def _oos(self, kind: str, topic: str):
        insp = self.snap.get(f"{kind}_inspections")
        rate = self.snap.get(f"{kind}_oos_pct")
        natl = self.snap.get(f"{kind}_natl_avg_pct")
        oos_n = self.snap.get(f"{kind}_oos")
        if insp is None or rate is None or natl is None:
            self.skipped.append(f"{kind} OOS not emitted for USDOT {self.dot}: inspections="
                                f"{insp!r} rate={rate!r} national={natl!r} (parse gap)")
            return None
        if insp < MIN_INSPECTIONS_FOR_RATE:
            if insp == 0:
                # Nothing was inspected: there is no claim to grade, only an absence.
                self.skipped.append(f"{kind} OOS rate not emitted for USDOT {self.dot}: "
                                    f"no roadside inspection history in the window")
                return None
            # 2026-09-03 policy: below the floor the COUNTS are written at low grade with
            # no rate and no state, where v1.3 refused them. The denominator is in the text.
            text = (f"{self.entity} (USDOT {self.dot}) had {insp} {kind} roadside "
                    f"inspection(s) in the 24-month window, of which {oos_n} resulted in an "
                    f"out-of-service order. Below the {MIN_INSPECTIONS_FOR_RATE}-inspection "
                    f"floor this harness requires before stating a rate, so no rate and no "
                    f"comparison to the national average is made.")
            return self._obs("9_industrial_safety_environmental",
                             f"{kind}_out_of_service_rate" if kind != "vehicle_maintenance"
                             else "vehicle_maintenance_out_of_service_rate",
                             "unknown", "weak_clue", text,
                             f"{kind} inspections: {insp} | OOS: {oos_n} | rate withheld",
                             self.as_of, 0.4,
                             low_grade=f"{insp} inspections, below the "
                                       f"{MIN_INSPECTIONS_FOR_RATE}-inspection floor")
        delta = rate - natl
        worse = delta > 0
        state = "legacy_constraint" if worse else "unknown"
        direction = "above" if worse else "below"
        text = (f"{self.entity} (USDOT {self.dot}) recorded a {kind} out-of-service rate "
                f"of {rate}% across {insp:,} roadside inspections in the 24 months to "
                f"{self.snap.get('data_as_of')}, {abs(delta):.2f} points {direction} the "
                f"national average of {natl}%.")
        excerpt = (f"{kind.capitalize()} Inspections: {insp} | Out of Service: {oos_n} | "
                   f"Out of Service %: {rate}% | Nat'l Average %: {natl}%")
        conf = self.res.confidence
        if insp < 100:
            conf -= 0.10  # small denominator, real but noisy
        return self._obs("9_industrial_safety_environmental", topic, state,
                         "measured_result", text, excerpt, self.as_of, conf)

    def vehicle_oos(self):
        return self._oos("vehicle", "vehicle_maintenance_out_of_service_rate")

    def driver_oos(self):
        return self._oos("driver", "driver_compliance_out_of_service_rate")

    def crash_exposure(self):
        total = self.snap.get("crashes_total")
        pu = self.snap.get("power_units") or 0
        if pu <= 0:
            return None
        if not total:
            # 2026-09-03 policy: a clean 24-month record is negative evidence about a real
            # fleet, written at low grade rather than silently skipped.
            text = (f"{self.entity} (USDOT {self.dot}) reports 0 FMCSA-reportable crashes "
                    f"in the 24-month window against a fleet of {_count(pu, 'power unit')}. "
                    f"A clean record is context, not evidence of modernization.")
            return self._obs("9_industrial_safety_environmental", "crash_exposure_rate",
                             "unknown", "weak_clue", text,
                             f"Crashes (24 mo): 0 | Power Units: {pu}", self.as_of, 0.4,
                             low_grade="zero crashes in the window")
        # Normalizing by fleet size is only meaningful above a floor. One crash on a
        # two-truck private fleet is not "50 crashes per 100 power units".
        if pu >= MIN_FLEET_FOR_CRASH_RATE:
            rate_txt = f" — {total / pu * 100:.1f} per 100 power units"
        else:
            rate_txt = (f". Fleet size ({_count(pu, 'power unit')}) is below the "
                        f"{MIN_FLEET_FOR_CRASH_RATE}-unit floor this harness requires "
                        f"before normalizing, so no rate is stated")
            self.skipped.append(
                f"crash rate not normalized for USDOT {self.dot}: fleet of {pu} power "
                f"units is below the {MIN_FLEET_FOR_CRASH_RATE}-unit floor")
        text = (f"{self.entity} (USDOT {self.dot}) was involved in {total} FMCSA-reportable "
                f"crashes ({self.snap.get('crashes_fatal')} fatal, "
                f"{self.snap.get('crashes_injury')} injury, {self.snap.get('crashes_tow')} "
                f"tow-away) in the 24 months to {self.snap.get('crash_window_end')}"
                f"{rate_txt}.")
        excerpt = (f"Crashes — Fatal: {self.snap.get('crashes_fatal')} | Injury: "
                   f"{self.snap.get('crashes_injury')} | Tow: {self.snap.get('crashes_tow')} "
                   f"| Total: {total}")
        return self._obs("9_industrial_safety_environmental", "crash_exposure_rate",
                         "unknown", "measured_result", text, excerpt, self.as_of,
                         self.res.confidence)

    def registry_maintenance(self):
        """An active carrier letting its own biennial filing go stale is observable strain."""
        age = _months_since(self.snap.get("mcs150_date"), self.snap.get("data_as_of"))
        status = (self.snap.get("usdot_status") or "").upper()
        if age is None or "ACTIVE" not in status:
            return None
        if age <= STALE_MCS150_MONTHS:
            if age < STALE_MCS150_MONTHS / 2:
                return None
            # 2026-09-03 policy: inside the second half of the biennial window the filing
            # is approaching, not past, its deadline -- written at low grade, not refused.
            text = (f"{self.entity} (USDOT {self.dot}) holds ACTIVE USDOT status and its "
                    f"most recent MCS-150 filing is dated {self.snap.get('mcs150_date')} "
                    f"({age / 12:.1f} years old), inside but approaching the biennial update "
                    f"window of 49 CFR 390.19(b)(4). Not yet a lapse.")
            return self._obs("18_historical_change_disappearing_evidence",
                             "registry_record_maintenance_lag", "unknown", "weak_clue", text,
                             f"USDOT Status: {self.snap.get('usdot_status')} | MCS-150 Form "
                             f"Date: {self.snap.get('mcs150_date')}", self.as_of, 0.35,
                             low_grade=f"MCS-150 {age:.0f} months old, inside the "
                                       f"{STALE_MCS150_MONTHS}-month window")
        text = (f"{self.entity} (USDOT {self.dot}) holds ACTIVE USDOT status but its most "
                f"recent MCS-150 filing is dated {self.snap.get('mcs150_date')} "
                f"({age / 12:.1f} years old), past the biennial update required by "
                f"49 CFR 390.19(b)(4). Fleet and mileage figures for this carrier are "
                f"correspondingly stale.")
        excerpt = (f"USDOT Status: {self.snap.get('usdot_status')} | "
                   f"MCS-150 Form Date: {self.snap.get('mcs150_date')}")
        return self._obs("18_historical_change_disappearing_evidence",
                         "registry_record_maintenance_lag", "legacy_constraint",
                         "weak_clue", text, excerpt, self.as_of,
                         max(self.res.confidence - 0.05, 0.3))

    def workforce_conflict(self):
        """Registry driver count vs. the hand-qualified employee estimate."""
        drivers = self.snap.get("drivers")
        try:
            sheet_employees = int(self.company.get("employee_count") or 0)
        except (TypeError, ValueError):
            self.skipped.append(f"workforce_conflict not emitted for USDOT {self.dot}: "
                                f"Companies.employee_count is not an integer "
                                f"({self.company.get('employee_count')!r})")
            return None
        if not drivers or not sheet_employees:
            self.skipped.append(f"workforce_conflict not emitted for USDOT {self.dot}: "
                                f"drivers={drivers!r}, employee_count={sheet_employees!r}")
            return None
        if drivers <= sheet_employees * (1 + WORKFORCE_CONFLICT_RATIO):
            if drivers <= sheet_employees:
                return None
            # 2026-09-03 policy: drivers exceed recorded headcount by less than the 25%
            # band -- a disagreement too small to assert an error, written at low grade.
            text = (f"FMCSA registry lists {drivers:,} drivers for {self.entity} "
                    f"(USDOT {self.dot}), against {sheet_employees:,} total employees "
                    f"recorded in the Companies sheet (source: "
                    f"{self.company.get('employee_count_source')}). Within the "
                    f"{WORKFORCE_CONFLICT_RATIO:.0%} band this harness allows before "
                    f"asserting a conflict; the employee estimate is likely understated.")
            return self._obs("3_workforce_org_exhaust", "workforce_scale_conflict",
                             "unknown", "weak_clue", text,
                             f"Drivers: {drivers} | Companies sheet employee_count: "
                             f"{sheet_employees}", _iso(self.snap.get("mcs150_date")), 0.35,
                             low_grade="driver count exceeds headcount by less than the "
                                       "25% conflict band")
        text = (f"FMCSA registry lists {drivers:,} drivers for {self.entity} "
                f"(USDOT {self.dot}), exceeding the {sheet_employees:,} total employees "
                f"currently recorded for this company in the Companies sheet "
                f"(source: {self.company.get('employee_count_source')}). Driver headcount "
                f"alone cannot exceed total headcount — the qualification-stage estimate "
                f"is understated and needs re-sourcing.")
        excerpt = (f"Drivers: {drivers} | Companies sheet employee_count: "
                   f"{sheet_employees} ({self.company.get('employee_count_source')})")
        return self._obs("3_workforce_org_exhaust", "workforce_scale_conflict", "unknown",
                         "weak_clue", text, excerpt, _iso(self.snap.get("mcs150_date")),
                         self.res.confidence)

    def for_hire_authority_gap(self):
        """A for-hire carrier showing NOT AUTHORIZED cannot legally haul for hire.

        The inverse of the private-carriage case. This one is worth surfacing: authority
        that is lapsed, revoked, or pending is a live constraint on the business. The
        harness cannot tell those apart from the snapshot alone — a new entrant awaiting
        authority looks identical to a carrier whose authority was revoked — so the claim
        states the observable fact and hands the interpretation to a reviewer.
        """
        status = (self.snap.get("operating_authority_status") or "").upper()
        private = self._is_private_carriage()
        if private is None and "NOT AUTHORIZED" in status:
            self.skipped.append(f"for_hire_authority gap not asserted for USDOT {self.dot}: "
                                f"operation classification unavailable, so private carriage "
                                f"cannot be excluded (session 10, F26)")
            return None
        if "NOT AUTHORIZED" not in status or private:
            return None
        op_class = ", ".join(self.snap.get("operation_classification") or []) or "n/a"
        text = (f"{self.entity} (USDOT {self.dot}) classifies itself as for-hire "
                f"({op_class}) but FMCSA reports its operating authority status as "
                f"NOT AUTHORIZED, meaning it holds no active authority to haul for hire. "
                f"This snapshot cannot distinguish lapsed or revoked authority from a new "
                f"entrant whose application is still pending — a reviewer should establish "
                f"which before this is used in a finding.")
        excerpt = (f"Operating Authority Status: {self.snap.get('operating_authority_status')} "
                   f"| Operation Classification: {op_class} | USDOT Status: "
                   f"{self.snap.get('usdot_status')}")
        return self._obs(TARGET_EVIDENCE_FAMILY, "for_hire_authority_not_active",
                         "legacy_constraint", "measured_result", text, excerpt,
                         self.as_of, min(self.res.confidence, 0.7))

    def multi_entity_structure(self):
        """Distinct co-located registrants suggest a segmented operating structure.

        A second registration under the *identical* legal name is a duplicate or legacy
        USDOT record, not a separate operating entity — asserting otherwise would invent
        structure that isn't there. Those are logged, not published as evidence.
        """
        if not self.res.family:
            return None
        primary_tokens = normalize(self.res.primary.legal_name)
        distinct, duplicates = [], []
        for c in self.res.family:
            (duplicates if normalize(c.legal_name) == primary_tokens else distinct).append(c)

        for c in duplicates:
            self.skipped.append(
                f"USDOT {c.dot} shares the legal name '{c.legal_name}' with primary USDOT "
                f"{self.dot} — treated as a duplicate/legacy registration, not a distinct "
                f"entity")
        if not distinct:
            return None

        members = [self.res.primary] + distinct
        listing = "; ".join(
            f"{c.legal_name} (USDOT {c.dot}, {_count(c.power_units, 'power unit')})"
            for c in members)
        zero_pu = [c for c in distinct if c.power_units == 0]
        split = ""
        if zero_pu and self.res.primary.power_units > 0:
            verb = "holds" if len(zero_pu) == 1 else "hold"
            split = (f" {len(zero_pu)} of these {verb} active registration while reporting "
                     f"zero power units, which is the registration pattern of a "
                     f"non-asset/brokerage arm rather than a fleet.")
        text = (f"{self.res.canonical_name} appears in the FMCSA census as "
                f"{len(members)} separately registered active entities with distinct legal "
                f"names sharing a physical city ({self.res.primary.city.title()}): "
                f"{listing}.{split} Common ownership is inferred from name and shared "
                f"address, not confirmed from a corporate filing — a reviewer should "
                f"verify before this is used in a finding.")
        return self._obs(TARGET_EVIDENCE_FAMILY, "multi_entity_operating_structure",
                         "unknown", "repeated_pattern", text, listing, self.as_of, 0.55)


# ----------------------------------------------------------------------------
# run
# ----------------------------------------------------------------------------

def run(args) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = FmcsaClient(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=today())
    aliases = json.loads(ALIAS_PATH.read_text(encoding="utf-8")) if ALIAS_PATH.exists() else {}
    db = MarketIntelDB()

    statuses = ["qualified", "pending_review", "soft_gate_exception"]
    if args.include_excluded:
        statuses.append("excluded")
    companies = db.companies(tuple(statuses))
    if args.companies:
        wanted = {c.strip().upper() for c in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"].upper() in wanted]
    if not companies:
        print("No companies selected.")
        return 1

    all_obs: list[Observation] = []
    issues: list[str] = []
    log: list[dict] = []

    print(f"{HARNESS_ID} {HARNESS_VERSION} — {len(companies)} companies "
          f"({'offline replay' if args.offline else 'live'})\n")

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        res = resolve_company(client, company, aliases)

        entry = {
            "company_id": cid, "canonical_name": name,
            "hq_state": company.get("hq_state"),
            "search_terms": res.search_terms,
            "candidates_seen": res.candidates_seen,
            "resolved": bool(res.primary),
            "observations": [],
        }

        if not res.primary:
            msg = (f"{cid} {name}: unresolved — {res.note}"
                   + (f" (closest rejected: {'; '.join(res.rejected_examples[:2])})"
                      if res.rejected_examples else ""))
            print(f"  [--] {msg}")
            issues.append(msg)
            entry["note"] = res.note
            entry["rejected_examples"] = res.rejected_examples
            log.append(entry)
            continue

        snap = client.carrier_snapshot(res.primary.dot)
        if not snap.get("found"):
            msg = f"{cid} {name}: USDOT {res.primary.dot} resolved but snapshot not found"
            print(f"  [!!] {msg}")
            issues.append(msg)
            log.append(entry)
            continue

        builder = ObservationBuilder(company, res, snap)
        observations = builder.build()
        all_obs.extend(observations)
        issues.extend(builder.skipped)

        entry.update({
            "usdot": res.primary.dot,
            "matched_entity": res.primary.legal_name,
            "match_score": res.primary.score,
            "matched_on": res.primary.matched_on,
            "resolution_confidence": res.confidence,
            "family_entities": [
                {"usdot": c.dot, "legal_name": c.legal_name, "power_units": c.power_units}
                for c in res.family
            ],
            "rejected_examples": res.rejected_examples[:5],
            "snapshot_source": snap.get("_source"),
            "observations": [
                {"topic": o.topic, "evidence_family": o.evidence_family,
                 "signal_strength": o.signal_strength,
                 "organizational_state": o.organizational_state,
                 "confidence_0_1": o.confidence_0_1, "observation_text": o.observation_text}
                for o in observations
            ],
        })
        log.append(entry)

        flag = "  " if res.confidence >= 0.8 else "? "
        print(f"  [{flag}] {cid} {name} -> USDOT {res.primary.dot} "
              f"{res.primary.legal_name} (score {res.primary.score}, "
              f"{res.primary.matched_on}, conf {res.confidence:.2f}) "
              f"-> {len(observations)} observations")
        for o in observations:
            print(f"          - {o.topic} [{o.signal_strength}/{o.organizational_state}] "
                  f"conf={o.confidence_0_1}")
        if res.family:
            print(f"          + {len(res.family)} related entities in "
                  f"{res.primary.city.title()}")

    resolved = sum(1 for e in log if e["resolved"])
    print(f"\n  resolved {resolved}/{len(companies)} companies · "
          f"{len(all_obs)} observations · {client.request_count} HTTP requests")

    stamp = today()
    report = None

    refresh_note = (
        f"{stamp}: row re-derived by {HARNESS_ID} {HARNESS_VERSION} from the SAFER "
        f"snapshot retrieved {stamp}, so all figures and the stated 24-month window come "
        f"from one coherent source date. Manual review decision preserved."
    ) if args.refresh_reviewed else ""

    if args.commit and args.force_rewrite:
        removed = db.delete_observations(HARNESS_ID, keep_reviewed=True)
        print(f"  --force-rewrite: removed {removed} unreviewed {HARNESS_ID} rows "
              f"(reviewed rows kept)")
    # Dry runs reconcile too, so --commit holds no surprises.
    report = db.sync_observations(all_obs, refresh_reviewed=args.refresh_reviewed,
                                  refresh_note=refresh_note)

    if report.conflicts:
        issues.append(
            f"{len(report.conflicts)} observation(s) changed since a human reviewed them "
            f"and were left untouched: "
            + "; ".join(f"{c['observation_id']} ({c['company_id']}/{c['topic']}, "
                        f"{c['review_status']})" for c in report.conflicts))

    run_record = HarnessRun(
        harness_id=HARNESS_ID,
        harness_name=HARNESS_NAME,
        version=HARNESS_VERSION,
        target_evidence_family=TARGET_EVIDENCE_FAMILY,
        date_run=today(),
        companies_processed_count=len(companies),
        observations_produced_count=report.written,
        known_issues=" | ".join(issues) if issues else "None recorded",
        material_revision_notes=(
            "v1.3 — MATERIAL: raw-response cache is now partitioned by retrieval date, so "
            "a re-run archives rather than overwrites the evidence an earlier run read. "
            "Added --refresh-reviewed, an explicit opt-in to re-derive reviewed rows that "
            "preserves review_status. Used here to resolve the 2026-08-22 review: SAFER "
            "advanced its snapshot from 08/20 to 08/23 mid-review, so nine hand-corrected "
            "rows carried 08/23 figures under an 08/20 window date. All rows now sit on "
            "one source date. No harness extraction errors were found in that review. "
            "v1.2 — MATERIAL: fixed a parser gap that dropped FMCSA's Operating Authority "
            "Status for private carriers (rows previously read 'operating authority: none "
            "listed' where the source says NOT AUTHORIZED). Added the private-carriage "
            "rule: NOT AUTHORIZED is the expected, non-informative status for a private or "
            "intrastate-only fleet, but a real constraint for a self-classified for-hire "
            "carrier, which now emits a for_hire_authority_not_active observation. "
            "Affected operating_model rows were refreshed by this run. "
            "v1.1 — writes made idempotent via db.sync_observations(); a reviewed row is "
            "never overwritten."),
        reprocessing_required="Yes — operating_model rows for private carriers were "
                              "re-derived; no other topics affected.",
    )

    print(f"  dedupe: {report.summary()}")
    for c in report.conflicts:
        print(f"    [conflict] {c['observation_id']} {c['company_id']}/{c['topic']} "
              f"is '{c['review_status']}' — content changed, left as-is for review")

    if args.commit:
        db.append_harness_run(run_record)
        db.save()
        print(f"  committed to {db.path.name} "
              f"({report.written} rows written, {run_record.harness_run_id})")
    else:
        print("  DRY RUN — nothing written. All rows passed schema validation. "
              "Re-run with --commit to write.")

    log_path = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
    log_path.write_text(json.dumps({
        "harness_id": HARNESS_ID,
        "harness_version": HARNESS_VERSION,
        "date_run": stamp,
        "committed": bool(args.commit),
        "sources": {
            "census": CENSUS_LANDING,
            "snapshot": "https://safer.fmcsa.dot.gov/CompanySnapshot.aspx",
        },
        "thresholds": {
            "min_score_to_accept": MIN_SCORE_TO_ACCEPT,
            "min_inspections_for_rate": MIN_INSPECTIONS_FOR_RATE,
            "stale_mcs150_months": STALE_MCS150_MONTHS,
        },
        "companies_processed": len(companies),
        "companies_resolved": resolved,
        "observations_produced": len(all_obs),
        "sync": {
            "refreshed_reviewed": report.refreshed_reviewed,
            "cache_partition": client.retrieval_date,
            "replayed_from": client.replayed_from,
            "inserted": [o.observation_id for o in report.inserted],
            "updated": [o.observation_id for o in report.updated],
            "unchanged": [o.observation_id for o in report.unchanged],
            "conflicts": report.conflicts,
        },
        "known_issues": issues,
        "resolution_log": log,
    }, indent=2), encoding="utf-8")
    print(f"  run log: {log_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=f"{HARNESS_ID} — {HARNESS_NAME}")
    p.add_argument("--commit", action="store_true", help="write rows to the workbook")
    p.add_argument("--offline", action="store_true", help="replay cached responses only")
    p.add_argument("--include-excluded", action="store_true",
                   help="also process companies excluded from the universe (negative test)")
    p.add_argument("--companies", help="comma-separated company_ids to limit the run")
    p.add_argument("--refresh-reviewed", action="store_true",
                   help="also refresh rows a human has reviewed (preserves review_status "
                        "and stamps reviewer_notes). Use when the reviewer verified rows "
                        "against a newer source snapshot than the harness read.")
    p.add_argument("--force-rewrite", action="store_true",
                   help="delete this harness's unreviewed rows before writing "
                        "(reviewed rows are always kept)")
    return run(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
