"""
Name -> external-entity resolution, with refusal logging.

`harness_advisor_brief.md` states it plainly: entity resolution is usually the harder
problem than extraction. The Week 1 pilot proved it three separate ways — substring
matching pulled SOUTHWESTERN EXPRESS for "Western Express", Venture Logistics files as
VENTURE TRANSPORT LLC, and Kenco holds five co-located registrations under one company_id.
Extraction, meanwhile, was 27/27 correct.

So this module exists to make one behaviour uniform across every harness that has to turn
a company name into somebody else's identifier:

  * score on **name tokens**, never on substrings
  * **refuse below a confidence floor** rather than returning a best guess
  * **log every rejection**, so a refusal is evidence about the source rather than silence
  * report **ambiguity** distinctly from **no candidate**, because they route to different
    `failure_category` values (`entity_ambiguous_multiple` vs `entity_no_candidate`) and to
    different fixes

WHY TOKEN SCORING RATHER THAN A STRING RATIO
--------------------------------------------
A character-level ratio scores SOUTHWESTERN EXPRESS against WESTERN EXPRESS very highly —
it contains every character of the query in order. Token-level scoring does not, because
SOUTHWESTERN and WESTERN are different tokens. The failure that actually happened is the
one a ratio cannot see, which is why the scoring here is set-based.

Corporate suffixes (INC, LLC, CORP...) are stripped before scoring. They are near-universal
and carry no discriminating information, so leaving them in inflates every score toward the
threshold and compresses the gap between the right answer and the wrong one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Legal-form tokens and other high-frequency noise. Stripped before scoring: they appear in
# most candidates, so they raise every score without separating any two of them.
STOPWORDS = {
    "INC", "INCORPORATED", "LLC", "LLP", "LP", "LTD", "LIMITED", "CORP", "CORPORATION",
    "CO", "COMPANY", "COMPANIES", "HOLDINGS", "HOLDING", "GROUP", "THE", "AND", "OF",
    "PLC", "PC", "PA", "DBA", "USA", "US", "AMERICA", "AMERICAN", "NATIONAL",
    "INTERNATIONAL", "ENTERPRISES", "ENTERPRISE", "SERVICES", "SERVICE", "SOLUTIONS",
}

# Tokens that name a line of business rather than an organisation. Kept in the token set
# but weighted down: two unrelated trucking firms both containing TRANSPORT should not
# score as a match on that basis alone.
WEAK_TOKENS = {
    "TRANSPORT", "TRANSPORTATION", "LOGISTICS", "FREIGHT", "TRUCKING", "CARRIERS",
    "CARRIER", "MANUFACTURING", "MFG", "INDUSTRIES", "INDUSTRIAL", "SUPPLY", "DISTRIBUTION",
    "CONSTRUCTION", "BUILDERS", "CONTRACTORS", "CONTRACTING", "SYSTEMS", "PRODUCTS",
}

WEAK_WEIGHT = 0.35
DEFAULT_FLOOR = 0.55
# If the runner-up scores within this of the winner, the result is ambiguous rather than
# resolved. Kenco's five co-located registrations are the case this exists for.
AMBIGUITY_MARGIN = 0.12


def tokens(name: str) -> list[str]:
    raw = re.sub(r"[^A-Za-z0-9 ]+", " ", str(name or "").upper())
    return [t for t in raw.split() if t and t not in STOPWORDS]


def _weight(token: str) -> float:
    return WEAK_WEIGHT if token in WEAK_TOKENS else 1.0


def score(query: str, candidate: str) -> float:
    """Weighted token overlap in [0, 1], asymmetric toward covering the query.

    Coverage of the *query's* tokens is what matters: a candidate with extra tokens
    ("MACK MOLDING COMPANY" for "MACK GROUP") is usually the same firm under its operating
    name, while a candidate missing query tokens usually is not. The denominator is
    therefore the query's weight, with a modest penalty for unmatched candidate tokens so
    that a long unrelated name cannot score a perfect match by containing the query.
    """
    q, c = tokens(query), tokens(candidate)
    if not q or not c:
        return 0.0
    qs, cs = set(q), set(c)
    shared = qs & cs

    q_weight = sum(_weight(t) for t in qs) or 1.0
    covered = sum(_weight(t) for t in shared)
    base = covered / q_weight

    # Penalty for candidate tokens the query does not account for. SOUTHWESTERN EXPRESS vs
    # WESTERN EXPRESS shares only EXPRESS (weak-ish) and carries SOUTHWESTERN unmatched.
    extra = sum(_weight(t) for t in cs - shared)
    c_weight = sum(_weight(t) for t in cs) or 1.0
    penalty = 0.35 * (extra / c_weight)

    return max(0.0, round(base - penalty, 4))


@dataclass
class Candidate:
    name: str
    payload: dict = field(default_factory=dict)
    score: float = 0.0


@dataclass
class Resolution:
    """Outcome of one resolution attempt. Always carries its own audit trail."""

    query: str
    status: str                     # resolved | ambiguous | no_candidate | below_threshold
    winner: Candidate | None = None
    considered: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    note: str = ""

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"

    @property
    def failure_category(self) -> str | None:
        """Route the refusal to the Attempts vocabulary."""
        return {
            "no_candidate": "entity_no_candidate",
            "below_threshold": "entity_below_threshold",
            "ambiguous": "entity_ambiguous_multiple",
        }.get(self.status)

    def as_log(self) -> dict:
        return {
            "query": self.query,
            "status": self.status,
            "winner": (self.winner.name if self.winner else None),
            "winner_score": (self.winner.score if self.winner else None),
            "note": self.note,
            # Every rejection is recorded, not just the near-misses. A refusal is a claim
            # about the source and has to be checkable after the fact.
            "rejected": [{"name": c.name, "score": c.score} for c in self.rejected[:25]],
            "considered_count": len(self.considered),
        }


def resolve(query: str, candidates, name_of=lambda c: c, floor: float = DEFAULT_FLOOR,
            margin: float = AMBIGUITY_MARGIN, accept_multiple: bool = False) -> Resolution:
    """Pick one candidate, or refuse and say why.

    `accept_multiple` is for sources where several records legitimately belong to one
    company — Kenco's five co-located USDOT registrations. It turns what would be an
    `ambiguous` refusal into a resolution whose winner is the top scorer, with the tied
    candidates retained in `considered` so the caller can process all of them.
    """
    scored = []
    for c in candidates:
        name = name_of(c)
        s = score(query, name)
        scored.append(Candidate(name=name, payload=c if isinstance(c, dict) else {}, score=s))
    scored.sort(key=lambda c: c.score, reverse=True)

    if not scored:
        return Resolution(query, "no_candidate", considered=[],
                          note="source returned no candidates")

    winner = scored[0]
    if winner.score < floor:
        return Resolution(query, "below_threshold", considered=scored, rejected=scored,
                          note=f"best candidate {winner.name!r} scored {winner.score} "
                               f"below floor {floor}")

    ties = [c for c in scored if c.score >= winner.score - margin and c.score >= floor]
    if len(ties) > 1 and not accept_multiple:
        return Resolution(query, "ambiguous", considered=scored,
                          rejected=[c for c in scored if c not in ties],
                          note=f"{len(ties)} candidates within {margin} of the top score: "
                               + ", ".join(f"{c.name} ({c.score})" for c in ties[:5]))

    return Resolution(query, "resolved", winner=winner,
                      considered=ties if accept_multiple else [winner],
                      rejected=[c for c in scored if c not in ties],
                      note=(f"{len(ties)} co-located records accepted together"
                            if accept_multiple and len(ties) > 1 else ""))


# --------------------------------------------------------------------------- query names

# Legal-form suffixes safe to strip from the TAIL of a query name. Stripping is a separate
# operation from token scoring: scoring ignores these tokens anyway, but a source's search
# box does not, and "Duke Manufacturing Co." returns nothing from OSHA where "Duke
# Manufacturing" returns three inspections.
_TAIL_SUFFIXES = re.compile(
    r"[\s,]*\b(inc|incorporated|llc|llp|lp|ltd|limited|corp|corporation|co|company|plc)\b\.?$",
    re.I)


def strip_legal_suffix(name: str) -> str:
    prev = None
    out = str(name or "").strip()
    while out != prev:
        prev = out
        out = _TAIL_SUFFIXES.sub("", out).strip(" ,.")
    return out


def query_variants(canonical_name: str, aliases: list[str] | None = None) -> list[str]:
    """Names to try against a name-keyed source, most specific first.

    Deliberately conservative, and the reason is a real near-miss: searching OSHA for the
    bare token "PLS" (from "PLS Logistics") returns "Pls Drywall And Ceilings Inc.", an
    unrelated contractor. Truncating to a distinctive-looking first token is exactly the
    kind of shortcut that produced SOUTHWESTERN EXPRESS in Week 1. So this only ever
    returns the full name, the name minus trailing legal-form suffixes, and variants a
    human explicitly seeded — never a guessed abbreviation.

    Scoring still runs on whatever the source returns, so a bad hit from any variant is
    caught downstream rather than trusted because the search box liked it.
    """
    out, seen = [], set()
    for n in [canonical_name, strip_legal_suffix(canonical_name), *(aliases or [])]:
        n = (n or "").strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


# ------------------------------------------------------------------------------- states

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE",
    "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD",
    "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "PR", "VI", "GU", "AS", "MP",
}


STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "WASH": "WA", "CALIF": "CA",
    "MICH": "MI", "PENN": "PA", "TENN": "TN", "MASS": "MA", "MINN": "MN", "WISC": "WI",
}


def state_code(value: str) -> str:
    """Extract a two-letter state code, or return "" if there isn't a valid one.

    `Companies.hq_state` is not uniform. The eight pilots hold bare codes ("OH", "VT");
    the 100 Anvil rows hold "City, ST" ("Chicago, IL"), because that is how the CRM export
    formatted them. Slicing the first two characters yields "CH" for Chicago -- and OSHA
    does not reject an unknown state, it silently searches nationally instead. So the bug
    does not surface as an error; it surfaces as a company appearing to have inspection
    history from states it does not operate in, filtered only by name scoring.

    Returning "" for anything unrecognised is deliberate: a caller that cannot get a state
    should record a coverage gap it can name, rather than issue a query whose scope it
    cannot describe.
    """
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    if raw in US_STATES:
        return raw
    tail = raw.split(",")[-1].strip()
    if tail in US_STATES:
        return tail
    # Session 16: the CRM export also spells states out ("Meridian, Idaho", "SLC, UTAH",
    # "Seattle, Wash."). Ten of 108 rows were unparsed and read as no state at all.
    tail_name = tail.rstrip(".").replace("(US OPS)", "").strip()
    if tail_name in STATE_NAMES:
        return STATE_NAMES[tail_name]
    for token in reversed(re.split(r"[\s,]+", raw)):
        if token in US_STATES:
            return token
    return ""
