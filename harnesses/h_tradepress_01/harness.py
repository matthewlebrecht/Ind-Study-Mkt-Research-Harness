#!/usr/bin/env python3
"""
H-TRADEPRESS-01 -- vertical trade press (the second `buyer_articulates` instrument).

WHY THIS ONE AND NOT THE API HARNESSES
--------------------------------------
The Priority-2 list put four API harnesses (procurement, patents, legal, recalls) ahead of
this. All four produce `buyer_acts`, and the evidence base is 185 `buyer_acts` to 87
`buyer_articulates`. Adding to the long leg does not answer the governing question; the
question asks where buyer *statements* and seller messaging converge or diverge, and only
two instruments in the whole portfolio produce buyer statements. This is the second one.

WHAT MAKES IT DIFFERENT FROM H-EXECVOICE-01
-------------------------------------------
H-EXECVOICE-01 searches the open web for any third-party page quoting a named executive.
This searches a *bounded set of vertical trade outlets* matched to the company's industry.
That is a narrower net with a much better hit rate for this population: a mid-size private
contractor is invisible to the national business press and routinely covered by
Construction Dive.

It is also the first harness where extraction is genuinely per-claim rather than
per-document (taxonomy patch rev 2 §2.4). One article yields observations at up to two
evidence families and two roles. `harnesses/h_tradepress_01/extract.py` holds that logic.

THE HARD RULE
-------------
`ST-PRESSPROFILE` NEVER carries `buyer_articulates`. A journalist characterising a
company's posture is not the company speaking, and admitting it would inflate the exact
leg this harness exists to widen -- producing the appearance of buyer articulation from
what is really trade-press editorial voice. `extract.ROLE_BY_TYPE` has no code path to
any other role, and the run refuses to write a row that violates it.

SCOPE (v1.6, session 15): EVERY BUYER WITH AN INDUSTRY, SUBSET AS OVERRIDE
------------------------------------------------------------------------
Until v1.5 the scope was a hand-seeded 15 because `Companies.industry_primary` was blank
for all 100 Anvil rows and this file refuses to guess an industry from a name. Session 15
populated that column from NAICS codes on OSHA / ECHO / FMCSA records the safety and
registry harnesses had already attributed to each company (scripts/enrich_industry.py), so
v1.6 searches every buyer whose industry maps to an outlet vertical (79 of 108 on
2026-09-06) and the SUBSET below is now an override for the 15 it names. A company with no
industry is still not searched. The original rationale for the 15 follows.

15 companies spanning the industry mix, not 108. The purpose of the first run is an
auditable output small enough to review properly, not a coverage number. Two of the 15 are
chosen adversarially: Prime Inc., whose name reduces to the single common token PRIME and
which produced four wrong-company rows in H-FIRSTPARTY-01 v1.0, and McGough Construction,
where the CEO's surname is also the company name and proximity attribution is worthless.
If the identity guards regressed, those two say so.

Output is QUARANTINED (docs/gates/gate_new_harness_output.md). Row counts only. No
coverage percentage is reported for this run.

    python -m harnesses.h_tradepress_01.harness              # dry run
    python -m harnesses.h_tradepress_01.harness --commit
    python -m harnesses.h_tradepress_01.harness --offline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache                                      # noqa: E402
from core.db import MarketIntelDB, Observation, today                  # noqa: E402
from core.resolution import tokens                                     # noqa: E402
from core.robots import RobotsGate                                     # noqa: E402
from core.search import BraveSearch, SearchError, host_of              # noqa: E402
from core import topics                                               # noqa: E402
from harnesses.h_execid_01.extract import html_lines                   # noqa: E402
from harnesses.h_execid_01.source import SiteClient                    # noqa: E402
from harnesses.h_execvoice_01.quotes import (                            # noqa: E402
    Quote, classify_buyer_voice, extract_quotes, signal_strength,
    interpret_state as quote_state)
from harnesses.h_firstparty_01 import article                          # noqa: E402
from harnesses.h_tradepress_01 import extract, shape                   # noqa: E402

HARNESS_ID = "H-TRADEPRESS-01"
HARNESS_NAME = "Vertical Trade Press Extractor"
VERSION = "v1.7"
SIGNAL_TYPES = ["exec_quote_reported", "exec_contributed_column", "exec_panel_coverage",
                "trade_press_profile", "wire_reprint_routed"]
PRIMARY_SIGNAL = "exec_quote_reported"
FAMILY_15 = "15_executive_candor_actor_networks"
FAMILY_1 = "1_first_party_strategy_governance"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# ---------------------------------------------------------------- the outlet universe
#
# Bounded on purpose. An unbounded web search is what H-EXECVOICE-01 already does; the
# value here is knowing which outlet a claim came from, so the outlets are enumerated and
# a result from anywhere else is discarded with a reason rather than quietly read.
# Session 10 item 4: expanded from the v1.1-v1.4 off-allowlist host breakdown (the run
# log counts every refused host). Added: trade outlets that were being refused as
# off-allowlist while being exactly the kind of reported journalism this harness reads.
# NOT added: executive-data aggregators (zoominfo, rocketreach, leadiq, appsruntheworld),
# vendor sites (family 6, H-VENDOR-01), PR wires and company domains (family 1,
# H-FIRSTPARTY-01), and Glassdoor/Indeed (family 4, and robots-refused). The scoping is
# in docs/diagnostics/tradepress_allowlist_scoping_2026-09-03.md. Every added host gets
# the same safeguards as the originals: is_about_company, speaker resolution, the wire
# verdict, robots.txt under this crawler's identity.
OUTLETS = {
    "construction": ["constructiondive.com", "enr.com", "forconstructionpros.com",
                     "constructionexec.com", "commercialobserver.com", "acppubs.com"],
    "trucking": ["ttnews.com", "fleetowner.com", "ccjdigital.com", "overdriveonline.com",
                 "truckinginfo.com", "freightwaves.com", "truckingdive.com"],
    "logistics": ["supplychaindive.com", "dcvelocity.com", "logisticsmgmt.com",
                  "supplychainbrain.com", "freightwaves.com", "supplychain247.com",
                  "foodlogistics.com"],
    "food": ["fooddive.com", "supermarketnews.com", "fooddive.com",
             "refrigeratedfrozenfood.com", "provisioneronline.com", "grocerydive.com",
             "andnowuknow.com", "foodlogistics.com"],
    "medical": ["medtechdive.com", "massdevice.com", "medicaldesignandoutsourcing.com"],
    "energy": ["utilitydive.com", "power-eng.com", "world-energy.org"],
    "consumer": ["consumergoods.com", "retaildive.com", "cosmeticsdesign.com"],
    "manufacturing": ["manufacturingdive.com", "industryweek.com", "assemblymag.com",
                      "thefabricator.com"],
}

# The 15-company subset, with the outlet verticals each is searched against. Industry is
# assigned here rather than read from `Companies.industry_primary`, which is blank for all
# 100 Anvil rows -- a known data gap, and guessing an industry from a name inside the
# harness would be exactly the kind of silent inference convention 13 forbids. This table
# IS the human seeding, visible and checkable, in the same spirit as company_aliases.json.
SUBSET = [
    # construction / general contracting -- the heaviest represented industry
    ("A032", ["construction"]),          # Gilbane
    ("A020", ["construction"]),          # Rycon Construction (coined name)
    ("A098", ["construction"]),          # McGough Construction (ADVERSARIAL: eponymous)
    ("A036", ["construction"]),          # JE Dunn Construction
    # trucking / freight
    ("C0004", ["trucking"]),             # Western Express
    ("A013", ["trucking"]),              # Averitt Express
    ("A054", ["trucking"]),              # Prime Inc. (ADVERSARIAL: single common word)
    # logistics / 3PL
    ("C0006", ["logistics", "trucking"]),   # Kenco Group
    ("A048", ["logistics", "trucking"]),    # Penske Logistics
    # food distribution
    ("A029", ["food", "logistics"]),     # SpartanNash
    ("A050", ["food"]),                  # Leprino Foods
    # medical devices
    ("C0001", ["medical", "manufacturing"]),   # Midmark (coined name)
    ("A030", ["medical"]),               # Merit Medical Systems
    # energy
    ("A011", ["energy"]),                # EnergySolutions
    # consumer goods
    ("A059", ["consumer"]),              # doTERRA International
]

# Companies.industry_primary value -> outlet verticals (session 15). `logistics` and the
# original `supply_chain_operations` both read the logistics outlets; `manufacturing` reads
# the manufacturing set.
INDUSTRY_TO_VERTICALS = {
    "construction": ["construction"], "trucking": ["trucking"],
    "logistics": ["logistics", "trucking"], "supply_chain_operations": ["logistics"],
    "food": ["food", "logistics"], "medical": ["medical", "manufacturing"],
    "energy": ["energy"], "consumer": ["consumer"], "manufacturing": ["manufacturing"],
}
MAX_EXECS_PER_COMPANY = 2
MAX_PAGES_PER_COMPANY = 10
# How many outlets get their own site: query. Keeps the search budget proportionate
# -- roughly 5-6 queries per company across the subset.
MAX_OUTLET_QUERIES = 4
TITLE_PRIORITY = ["ceo", "president", "coo", "cio_cto", "chief_transformation",
                  "vp_supply_chain", "vp_operations", "vp_it", "vp_manufacturing"]

JUNK_URL_RE = re.compile(
    r"(?i)(\.pdf$|/tag/|/tags/|/category/|/topic/|/author/|/search|/login|/signup|"
    r"/subscribe|/privacy|/terms|/sitemap|/events?/?$|/webinars?/)")

SOFT_404_RE = re.compile(
    r"(?i)(page not found|404 not found|does\s?n.t exist|no longer available)")


# FAMILY 15, AND ONE OF JACOB'S OWN NAMED SIGNAL TYPES (v1.1, Task 5.5).
#
# v1.0 dropped every LinkedIn URL as off-allowlist, which threw away an executive's own
# published words without recording that it had. LinkedIn now routes like any other outlet,
# so the result is a determinate access outcome rather than a silence.
#
# EXPECT AN ACCESS FINDING, AND RECORD IT HONESTLY. Measured 2026-09-01: LinkedIn's
# robots.txt publishes `Disallow: /` for this crawler identity, so `core/robots.py` refuses
# every path -- posts, profiles and company pages alike. That is a true statement about the
# source and belongs in the database, exactly as Glassdoor's does (convention 38). No
# user-agent is switched, no authenticated access is attempted, and no third-party mirror
# or scraper service is used: a refusal recorded honestly is a result, an evaded refusal is
# not evidence.
#
# CLASSIFICATION, so this is not mis-scored if access ever opens. An executive's own
# LinkedIn post is self-published and topic-chosen by the speaker, which makes it **IC1** --
# curated by an interested party, the same class as an announcement or vendor content. It
# is genuine family-15 articulation and worth having, but per taxonomy patch §4.6.1 its
# absence licenses NO inference, and it does not count as progress against the
# articulation-bias gap. Registered as its own signal type, ST-LINKEDINPOST, rather than
# folded into ST-EXECQUOTE-REPORTED, which is IC2 and scored higher for precisely the
# reason LinkedIn is not: nobody elicited it.
#
# ATTRIBUTION GATE, as for vendor quotes: the post must be authored by a named individual
# with a title whom H-EXECID-01 or the page itself identifies as an officer of that
# company. A COMPANY-PAGE post is first-party corporate speech, not executive candor, and
# routes to H-FIRSTPARTY-01's family and role instead.
LINKEDIN_HOST = "linkedin.com"
LINKEDIN_SIGNAL = "linkedin_exec_post"
LINKEDIN_COMPANY_PATH_RE = re.compile(r"(?i)/company/|/showcase/")


# Cross-vertical business/technology press, read for every company (session 10 item 4).
CROSS_VERTICAL_OUTLETS = ["cio.com", "pymnts.com", "itdigest.com"]


def outlet_hosts(verticals: list[str]) -> set[str]:
    out = set()
    for v in verticals:
        out.update(OUTLETS.get(v, ()))
    out.update(CROSS_VERTICAL_OUTLETS)
    out.add(LINKEDIN_HOST)          # every vertical; see the LinkedIn note above
    return out


def load_executives(db: MarketIntelDB) -> dict[str, list[dict]]:
    ws = db.wb["Company_Executives"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    by_company: dict[str, list[dict]] = {}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        row = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers) if h}
        if str(row.get("role_relevance") or "") != "primary":
            continue
        if str(row.get("status") or "active") != "active":
            continue
        by_company.setdefault(str(row["company_id"]), []).append(row)
    for people in by_company.values():
        people.sort(key=lambda p: (
            TITLE_PRIORITY.index(str(p.get("title_normalized")))
            if str(p.get("title_normalized")) in TITLE_PRIORITY else 99,
            str(p.get("full_name"))))
    return by_company


def firstparty_urls(db: MarketIntelDB) -> set[str]:
    """Source URLs H-FIRSTPARTY-01 already holds, for the §8.2 redundancy check."""
    ws = db.wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    i_h = headers.index("harness_id") + 1
    i_u = headers.index("source_url") + 1
    return {str(ws.cell(r, i_u).value or "").strip()
            for r in range(2, ws.max_row + 1)
            if str(ws.cell(r, i_h).value or "") == "H-FIRSTPARTY-01"}


def firstparty_claims(db: MarketIntelDB) -> set[tuple]:
    """(company_id, topic) pairs H-FIRSTPARTY-01 already holds.

    The natural key for a claim is what the claim is ABOUT (convention 30), so redundancy
    is judged on (company, topic) rather than on the URL -- a wire release reprinted at a
    trade outlet has a different URL from the same release on the wire, and keying on URL
    would call it new every time.
    """
    ws = db.wb["Observations"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    i_h = headers.index("harness_id") + 1
    i_c = headers.index("company_id") + 1
    i_t = headers.index("topic") + 1
    return {(str(ws.cell(r, i_c).value or ""), str(ws.cell(r, i_t).value or ""))
            for r in range(2, ws.max_row + 1)
            if str(ws.cell(r, i_h).value or "") == "H-FIRSTPARTY-01"}


def build_articulation(company: dict, sig_type: str, theme_key: str, quotes: list,
                       url: str, title: str, pub_date: str, retrieval: str,
                       why_type: str) -> Observation:
    """A `buyer_articulates` row: an executive of this company said this, in trade press."""
    theme = topics.THEMES_BY_KEY[theme_key]
    names = sorted({q.executive for q in quotes})
    states = [q.state for q in quotes if q.state != "unknown"]
    state = "unknown"
    for candidate in ("active_transition", "legacy_constraint", "target_state"):
        if candidate in states:
            state = candidate
            break
    explicit = [q for q in quotes if q.attribution == "explicit"]
    strength = signal_strength(quotes)
    # A paraphrase of spoken remarks cannot support the top of the strength ladder either.
    # The -1 cap in §8.1 is a reliability cap, but letting ST-EXECPANEL claim
    # `measured_result` off a reporter's notes would move the same overstatement into the
    # other column.
    if sig_type == "ST-EXECPANEL" and strength == "measured_result":
        strength = "committed_action"

    label = {"ST-EXECQUOTE-REPORTED": "was quoted in reported trade coverage",
             "ST-EXECCOLUMN": "wrote a contributed trade column",
             "ST-EXECPANEL": "was reported speaking at a panel or conference"}[sig_type]
    text = (
        f"{', '.join(names)} of {company['canonical_name']} {label} articulating "
        f"{theme.label}, in {len(quotes)} directly quoted passage(s) "
        f"({len(explicit)} with explicit attribution) on {host_of(url)}. "
        f"Reading: {state.replace('_', ' ')}. Records what the executive said as "
        f"published by a trade outlet -- not a verified account of what the company has "
        f"implemented. Typed {sig_type} because {why_type}."
    )
    parts = []
    for q in quotes[:3]:
        cue = f" [cue: {q.state_cue}]" if q.state_cue else ""
        parts.append(f'{q.executive} ({q.attribution}): "{q.text[:320]}"{cue}')
    matched = sorted({t for q in quotes for terms in q.themes.values() for t in terms})
    excerpt = " | ".join(parts) + f" | matched: {', '.join(matched[:10])}"

    confidence = round(max(q.confidence for q in quotes)
                       - (0.1 if sig_type == "ST-EXECPANEL" else 0.0), 2)
    grade = extract.GRADE_BY_TYPE[sig_type]
    weak = [q.weak_reason for q in quotes if getattr(q, "weak_reason", "")]
    if weak and len(weak) == len(quotes):
        grade = topics.LOW_GRADE
        confidence = min(confidence, topics.LOW_GRADE_CONFIDENCE_MAX)
        excerpt = topics.low_grade_excerpt("; ".join(sorted(set(weak)))[:300], excerpt)
    return Observation(
        company_id=company["company_id"], evidence_family=FAMILY_15,
        evidence_role="buyer_articulates", topic=theme_key,
        organizational_state=state, signal_strength=strength,
        observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url,
        publication_date=pub_date, retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=confidence)


def build_action(company: dict, theme_key: str, actions: list[dict], url: str,
                 title: str, pub_date: str, retrieval: str,
                 low_grade: bool = False) -> Observation:
    """A `buyer_acts` row from ST-PRESSPROFILE: a reported concrete action. `low_grade`:
    the theme rested on a single generic term (2026-09-03 policy: written at C, marked)."""
    theme = topics.THEMES_BY_KEY[theme_key]
    joined = " ".join(a["sentence"] for a in actions)
    state, cue = article.interpret_state(joined)
    if state == "unknown":
        state = "active_transition"   # a completed action is, at minimum, a transition
    strength = "repeated_pattern" if len(actions) >= 2 else "committed_action"
    text = (
        f"Trade coverage on {host_of(url)} reports {company['canonical_name']} taking "
        f"{len(actions)} concrete action(s) bearing on {theme.label}: "
        f"{'; '.join(a['verb'] for a in actions)}. Reported behaviour witnessed by a "
        f"journalist, not a statement by the company. ST-PRESSPROFILE carries buyer_acts "
        f"only -- journalist characterisation of posture was excluded and is listed in "
        f"the run log."
    )
    excerpt = " | ".join(
        f'"{a["sentence"][:280]}"'
        + (" [contains journalist characterisation as well as the action]"
           if a.get("characterization_present") else "")
        for a in actions[:3])
    matched = sorted({t for a in actions for terms in a["themes"].values() for t in terms})
    excerpt += f" | matched: {', '.join(matched[:10])}"
    grade, confidence = extract.GRADE_BY_TYPE["ST-PRESSPROFILE"], 0.6
    if low_grade:
        strength, grade, confidence = "weak_clue", topics.LOW_GRADE, topics.LOW_GRADE_CONFIDENCE_MAX
        excerpt = topics.low_grade_excerpt("single generic term, not in the headline", excerpt)
    return Observation(
        company_id=company["company_id"], evidence_family=FAMILY_15,
        evidence_role="buyer_acts", topic=theme_key,
        organizational_state=state, signal_strength=strength,
        observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url,
        publication_date=pub_date, retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=confidence)


def build_characterization(company: dict, theme_key: str, chars: list[dict], url: str,
                           title: str, pub_date: str, retrieval: str) -> Observation:
    """A `buyer_articulates` row from ST-PRESSCHAR: the company describing itself or its
    intent, as reported by a journalist. Not witnessed behaviour; the text says so."""
    theme = topics.THEMES_BY_KEY[theme_key]
    joined = " ".join(c["sentence"] for c in chars)
    state, cue = article.interpret_state(joined)
    kinds = sorted({c["kind"] for c in chars})
    if state == "unknown":
        state = "target_state" if "intent" in kinds else "unknown"
    text = (
        f"Trade coverage on {host_of(url)} reports {company['canonical_name']} describing "
        f"itself, or its intent, in {len(chars)} passage(s) bearing on {theme.label} "
        f"({', '.join(kinds)}): {'; '.join(c['cue'] for c in chars[:4])}. Reading: "
        f"{state.replace('_', ' ')}. This is the company's self-characterisation as "
        f"relayed by a reporter -- articulation, second-hand -- and NOT behaviour a "
        f"journalist witnessed. ST-PRESSCHAR (session 10 item 3)."
    )
    excerpt = " | ".join(f'[{c["kind"]}] "{c["sentence"][:280]}"' for c in chars[:3])
    matched = sorted({t for c in chars for terms in c["themes"].values() for t in terms})
    excerpt += f" | matched: {', '.join(matched[:10])}"
    return Observation(
        company_id=company["company_id"], evidence_family=FAMILY_15,
        evidence_role=extract.ROLE_BY_TYPE["ST-PRESSCHAR"], topic=theme_key,
        organizational_state=state, signal_strength="weak_clue",
        observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url,
        publication_date=pub_date, retrieval_date=retrieval,
        source_grade=extract.GRADE_BY_TYPE["ST-PRESSCHAR"],
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=0.4)


def build_routed_firstparty(company: dict, theme_key: str, hits: list[str], url: str,
                            title: str, pub_date: str, retrieval: str,
                            marker: str, low_grade: bool = False) -> Observation:
    """A reprinted press release, reclassified to family 1 per §8.2. `low_grade`: the
    theme rested on a single generic term (2026-09-03 policy: written at C, marked)."""
    theme = topics.THEMES_BY_KEY[theme_key]
    state, cue = article.interpret_state(title + " " + " ".join(hits))
    text = (
        f"{company['canonical_name']} announcement, reached as a wire reprint carried by "
        f"{host_of(url)}, bearing on {theme.label}. Reclassified from trade press to "
        f"first-party on {marker}; family and role follow H-FIRSTPARTY-01. Not counted "
        f"toward trade-press articulation yield."
    )
    excerpt = f"[wire reprint] {title[:200]} | matched: {', '.join(hits[:8])}"
    grade, confidence = "B", 0.55
    if low_grade:
        grade, confidence = topics.LOW_GRADE, topics.LOW_GRADE_CONFIDENCE_MAX
        excerpt = topics.low_grade_excerpt("single generic term, not in the headline", excerpt)
    return Observation(
        company_id=company["company_id"], evidence_family=FAMILY_1,
        evidence_role="buyer_articulates", topic=theme_key,
        organizational_state=state if state != "unknown" else "active_transition",
        signal_strength="weak_clue",
        observation_text=text,
        evidence_excerpt=excerpt,
        source_url=url, publication_date=pub_date, retrieval_date=retrieval,
        source_grade=grade, harness_id=HARNESS_ID, harness_version=VERSION,
        confidence_0_1=confidence)


def main() -> int:
    # Session 15: a Windows console defaults to cp1252, and one search-error string carrying
    # U+FFFD killed a 79-company live run at company 68 with UnicodeEncodeError. Output is
    # never worth a crash; replace what the console cannot show.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="H-TRADEPRESS-01 -- vertical trade press")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--companies")
    ap.add_argument("--pause", type=float, default=0.8)
    args = ap.parse_args()

    db = MarketIntelDB()
    by_id = {c["company_id"]: c for c in db.companies()}
    # Session 15 (v1.6): verticals come from Companies.industry_primary for every buyer
    # that has one (populated from archived NAICS codes by scripts/enrich_industry.py --
    # attributed records, not name guesses), with the hand-seeded SUBSET as an override
    # where it names a company. A company with no industry is still not searched: the
    # refusal to guess (convention 13) has moved from this file to the enrichment script.
    seeded = {cid: verts for cid, verts in SUBSET}
    subset = []
    for cid, c in by_id.items():
        if str(c.get("qualification_status") or "") == "provider_benchmark":
            continue
        if cid in seeded:
            subset.append((cid, seeded[cid]))
            continue
        ind = str(c.get("industry_primary") or "").strip()
        verts = INDUSTRY_TO_VERTICALS.get(ind)
        if verts:
            subset.append((cid, verts))
    subset.sort(key=lambda t: t[0])
    unsearched = [cid for cid in by_id if cid not in dict(subset)
                  and str(by_id[cid].get("qualification_status") or "") != "provider_benchmark"]
    print(f"  {len(subset)} companies with an outlet vertical ({len(seeded)} hand-seeded, "
          f"{len(subset) - len([c for c in subset if c[0] in seeded])} from industry_primary); "
          f"{len(unsearched)} with no industry are not searched")
    missing = [cid for cid, _ in SUBSET if cid not in by_id]
    if missing:
        print(f"  [!!] subset ids not in Companies, skipped: {missing}")
    if args.companies:
        want = {c.strip() for c in args.companies.split(",")}
        subset = [(cid, v) for cid, v in subset if cid in want]
    if args.limit:
        subset = subset[:args.limit]

    execs_by_company = load_executives(db)
    held_claims = firstparty_claims(db)
    held_urls = firstparty_urls(db)
    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = DatedCache(OUTPUT_DIR / "raw" / "pages", offline=args.offline,
                       retrieval_date=stamp, pause_seconds=args.pause)
    client = SiteClient(pages)
    search = BraveSearch(OUTPUT_DIR / "raw" / "search", offline=args.offline,
                         retrieval_date=stamp, pause_seconds=1.0)
    gate = RobotsGate()

    # LinkedIn is DECLARED IN SCOPE, not attempted incidentally (v1.1). Declaring it means
    # the run context closes out every company where no LinkedIn URL surfaced as
    # `not_covered` automatically, so the denominator is complete and the access finding
    # has one -- convention 5: a failure-only record cannot distinguish "this is rare" from
    # "the harness quietly stopped trying".
    scope = ([(cid, PRIMARY_SIGNAL) for cid, _ in subset]
             + [(cid, LINKEDIN_SIGNAL) for cid, _ in subset])
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=FAMILY_15, scope=scope,
                      signal_families={PRIMARY_SIGNAL: FAMILY_15,
                                       LINKEDIN_SIGNAL: FAMILY_15}, commit=args.commit)
    # Audit gate: first output of a new harness. Quarantined until an artifact exists.
    run.publication_status = "quarantined"

    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "subset_size": len(subset), "companies": [],
           "routed_to_firstparty": [], "characterizations_dropped": [],
           "robots_blocked": [], "window_widened": [], "off_allowlist_hosts": {},
           "multi_subject_actions_dropped": [],
           "linkedin": []}

    for cid, verticals in subset:
        company = by_id[cid]
        name = company["canonical_name"]
        hosts = outlet_hosts(verticals)
        entry = {"company_id": cid, "name": name, "verticals": verticals,
                 "pages": [], "rows": [], "excluded": []}
        people = execs_by_company.get(cid, [])[:MAX_EXECS_PER_COMPANY]
        exec_names = [str(p["full_name"]) for p in people]
        company_tokens = set(tokens(name))
        evaluated = discarded = 0
        search_failed = None
        linkedin_blocked: list[tuple[str, str]] = []

        # One `site:` query per outlet, rather than one query naming all of them.
        #
        # The first version passed the hosts as OR terms in a single query and read six
        # articles across fifteen companies: Brave treats bare hostnames as keywords, so
        # the results were dominated by the company's own site, ZoomInfo, RocketReach and
        # LinkedIn, all of which were then discarded as off-allowlist. Measured on the
        # same companies, `"JE Dunn" site:constructiondive.com` returns eight on-outlet
        # articles where the OR form returned none.
        #
        # Everything off-allowlist is still logged as excluded rather than silently
        # dropped, because `site:` is a request rather than a guarantee.
        primary_hosts = [h for v in verticals for h in OUTLETS.get(v, ())][:MAX_OUTLET_QUERIES]
        queries = [f'"{name}" site:{h}' for h in dict.fromkeys(primary_hosts)]
        queries.append(f'"{name}" (automation OR "digital transformation" OR technology '
                       f'OR "supply chain" OR modernization OR software)')
        for nm in exec_names[:1]:
            queries.append(f'"{nm}" "{name}" (said OR told OR interview OR panel)')

        # Interleaved, not concatenated. Concatenating starved the general query: the
        # site: results filled the fetch budget on their own, and Gilbane fell from 3 rows
        # to 0 between two runs because the ConTech Conversations interview -- the single
        # best piece of evidence the harness had found -- now sat behind ten site: hits
        # and was never fetched. That is convention 33's companion lesson: check a fix
        # against the case that WAS working, not only the one that was broken.
        # Round-robin gives every query a share of the budget.
        per_query = []
        for q in queries:
            try:
                per_query.append(search.search(q, count=10))
            except SearchError as e:
                search_failed = e
                break
        results = []
        for i in range(max((len(b) for b in per_query), default=0)):
            for bucket in per_query:
                if i < len(bucket):
                    results.append(bucket[i])

        if search_failed is not None:
            run.attempt(cid, PRIMARY_SIGNAL, outcome="not_covered",
                        failure_stage=search_failed.failure_stage,
                        failure_category=search_failed.failure_category,
                        fix_class=search_failed.fix_class,
                        failure_detail=str(search_failed)[:400],
                        candidates_evaluated=evaluated, candidates_discarded=discarded)
            print(f"  [!!] {cid} {name}: search failed -- {search_failed}")
            log["companies"].append(entry)
            continue

        seen_urls, fetched, attempted = set(), 0, 0
        rows_for_company: list[Observation] = []

        for r in results:
            if r.url in seen_urls:
                continue
            seen_urls.add(r.url)
            evaluated += 1
            host = host_of(r.url)
            if not (host in hosts or any(host.endswith("." + h) for h in hosts)):
                discarded += 1
                # Off-allowlist URLs are COUNTED BY HOST rather than only discarded (v1.1).
                # v1.0 dropped 239 of them with no breakdown, so nobody could see what was
                # in there. Convention 7: a suppressed result is reported, never silently
                # dropped -- and the answer to "should the allowlist expand" is a fact
                # about which hosts keep appearing, not a matter of opinion.
                log["off_allowlist_hosts"][host] =                     log["off_allowlist_hosts"].get(host, 0) + 1
                entry["excluded"].append({"url": r.url, "reason": "off_outlet_allowlist",
                                          "host": host})
                continue
            if JUNK_URL_RE.search(r.url):
                discarded += 1
                entry["excluded"].append({"url": r.url, "reason": "non_article_url"})
                continue
            if fetched >= MAX_PAGES_PER_COMPANY:
                # Session 10 item 6 (T10): the budget cap is recorded, never silent.
                entry.setdefault("page_budget_skipped", []).append(r.url)
                log.setdefault("page_budget_capped", []).append(
                    {"company_id": cid, "url": r.url})
                continue


            allowed, why = gate.check(r.url)

            # LinkedIn is routed, not discarded, and its outcome is recorded as a fact
            # about the source (v1.1). A company-page post is corporate speech and belongs
            # to H-FIRSTPARTY-01; an individual's post is family-15 articulation at IC1.
            if LINKEDIN_HOST in host:
                is_company_page = bool(LINKEDIN_COMPANY_PATH_RE.search(r.url))
                log["linkedin"].append({
                    "company_id": cid, "url": r.url, "title": r.title[:90],
                    "kind": "company_page" if is_company_page else "individual_post",
                    "robots_allowed": allowed, "robots_detail": why})
                if not allowed:
                    discarded += 1
                    # Collected, not emitted here. The Attempts grain is one row per
                    # (run, company, signal), and a company routinely surfaces several
                    # LinkedIn URLs; one attempt per URL would violate the grain and
                    # inflate the denominator. Emitted once after the URL loop.
                    linkedin_blocked.append((r.url, why))
                    entry["excluded"].append({"url": r.url, "reason": "linkedin_blocked",
                                              "detail": why})
                    continue

            if not allowed:
                discarded += 1
                entry["excluded"].append({"url": r.url, "reason": "robots_blocked",
                                          "detail": why})
                log["robots_blocked"].append({"company_id": cid, "url": r.url,
                                              "detail": why})
                continue

            page = client.get(r.url)
            if not page.ok:
                # A refused fetch does NOT consume the budget. Three of the four
                # construction outlets answer 403 to an unauthenticated request, and
                # counting those against a 10-page budget left Gilbane with three
                # Construction Dive articles out of ten slots -- a working outlet starved
                # by broken ones. The attempt is still recorded; it just does not crowd
                # out a page that can actually be read.
                attempted += 1
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "rejected": "http"})
                continue
            fetched += 1

            lines = html_lines(page.html)
            full = " ".join(lines)
            # Everything downstream reads the BODY, not the page. `full` is kept only for
            # the two tests that legitimately need the whole document: identity (the
            # company name can appear in the headline or the standfirst) and the soft-404
            # check. Classifying on the full page is what turned MedTech Dive's section
            # navigation into ten Merit Medical observations.
            text = extract.article_body(lines)
            if SOFT_404_RE.search(full[:400]) and len(full) < 1200:
                discarded += 1
                entry["pages"].append({"url": r.url, "status": page.status,
                                       "rejected": "soft_404"})
                continue

            ok, why_not = article.looks_like_article(lines, r.url, r.title)
            if ok and len(text) < 400:
                ok, why_not = False, (f"only {len(text)} chars of article prose once site "
                                      f"furniture is removed -- most likely paywalled or "
                                      f"JS-rendered")
            if not ok:
                discarded += 1
                entry["pages"].append({"url": r.url, "rejected": f"not_article: {why_not}"})
                continue

            # IDENTITY. The guard that four of H-FIRSTPARTY-01 v1.0's Prime Inc. rows
            # needed and did not have.
            # IDENTITY WINDOW, SIZED BY DOCUMENT SHAPE (v1.1).
            #
            # The 2,500-character prefix encodes "the subject is named early", which is
            # true of narrative with one subject and false of a rankings table, a "New
            # Names and Faces" column or a regional roundup. v1.0 refused 28 articles as
            # not_about_company and 26 of them NAME the company, just past the window --
            # RYCON at 7,609 in ENR's Top 400 Contractors, LEPRINO at 15,533 in a Top 150
            # table. A refusal saying an article is not about a company, when the article
            # names it, is a false statement in the record (convention 12).
            #
            # The window widens for multi-subject documents ONLY. Identity matching is not
            # loosened globally, because that is the change that broke Midmark, and
            # convention 31 still governs downstream: a common dictionary word still needs
            # the full company phrase wherever it is found, so this changes nothing for
            # Prime Inc. at any window size.
            multi, shape_why = shape.is_multi_subject(text, r.title, r.url)
            about, why_not = article.is_about_company(
                full, name, r.title, head_chars=len(full) if multi else 2500)
            if multi:
                page_note_shape = shape_why
                log["window_widened"].append(
                    {"company_id": cid, "url": r.url, "title": r.title[:90],
                     "why": shape_why[:200], "identity_passed": about})
            if not about:
                discarded += 1
                # `title` is recorded on the refusal, not just the URL. Without it a
                # reviewer checking this refusal cannot see what the harness read
                # (convention 12) -- the same gap session 3 closed for stale refusals.
                entry["pages"].append({"url": r.url, "title": r.title[:90],
                                       "multi_subject": multi,
                                       "rejected": f"not_about_company: {why_not}"})
                continue

            pub = article.published_date(page.html)
            age = article.age_days(pub, stamp)
            if age is not None and age > article.MAX_AGE_DAYS:
                discarded += 1
                # `published` and `title` are recorded here, not just on the pages that
                # survive. The first version omitted them, so the declined sheet rendered
                # 46 stale refusals as "published undated; 5906 days old" -- a
                # self-contradiction, and a reviewer checking one of those refusals could
                # not see the date the harness had actually read without opening the URL.
                # A refusal is a claim about a source and has to be checkable afterwards
                # (convention 12), which means logging the evidence for it, not just the
                # verdict.
                entry["pages"].append({"url": r.url, "title": r.title[:90],
                                       "published": pub,
                                       "rejected": f"stale: {age} days old"})
                continue

            page_note = {"url": r.url, "title": r.title[:90], "published": pub,
                         "types": []}

            # ---- §8.2 wire reprint: route, do not filter ----
            is_wire, marker = extract.wire_verdict(text, r.title, r.url)
            if is_wire:
                hits = article.classify_announcement(text)
                for theme_key, terms in hits.items():
                    # 2026-09-03 corroboration-gate policy: a single generic term is a
                    # low-grade write, not a refusal (the referent is right).
                    wire_low_grade = not article.theme_is_the_subject(terms, r.title)
                    if (cid, theme_key) in held_claims or r.url in held_urls:
                        run.attempt(cid, "wire_reprint_routed", outcome="covered",
                                    scope="incidental", evidence_family=FAMILY_1,
                                    failure_stage="governance",
                                    failure_category="suppressed_redundant_key",
                                    fix_class="source_limitation",
                                    failure_detail=(
                                        f"wire reprint at {r.url} reclassified to "
                                        f"first-party on {marker}; H-FIRSTPARTY-01 "
                                        f"already holds ({cid}, {theme_key}). Suppressed "
                                        f"as redundant on the natural key; still counts "
                                        f"toward signal_strength for the held row."),
                                    source_url_attempted=r.url)
                        page_note["types"].append(f"wire->suppressed_redundant_key:{theme_key}")
                        log["routed_to_firstparty"].append(
                            {"company_id": cid, "url": r.url, "topic": theme_key,
                             "marker": marker, "disposition": "suppressed_redundant_key"})
                        continue
                    obs = build_routed_firstparty(company, theme_key, terms, r.url,
                                                  r.title, pub, stamp, marker, low_grade=wire_low_grade)
                    rows_for_company.append(obs)
                    page_note["types"].append(f"wire->firstparty:{theme_key}")
                    log["routed_to_firstparty"].append(
                        {"company_id": cid, "url": r.url, "topic": theme_key,
                         "marker": marker, "disposition": "admitted_new_firstparty"})
                entry["pages"].append(page_note)
                continue

            # ---- reported trade coverage ----
            #
            # Two speaker sources, combined. `Company_Executives` supplies the roster;
            # the article itself supplies whoever the outlet says it is quoting. The
            # second matters more here than the first: trade press quotes the officer
            # relevant to the TOPIC -- the CIO, the head of innovation -- while a
            # leadership page ranks the CEO first, so the roster misses exactly the
            # people this instrument is best at finding. Construction Dive's interview
            # with Gilbane's head of innovation is the measured case: real articulation,
            # invisible to a roster-only search.
            speakers = extract.speakers_in_article(text, name)
            page_note["speakers"] = [{"name": s["name"], "title": s["title"],
                                      "pattern": s["pattern"]} for s in speakers]
            speaker_names = [s["name"] for s in speakers]
            # Resolve each rostered executive to the form THIS article uses, so
            # "Edward T. Broderick" on a leadership page finds "said Ed Broderick" in
            # Construction Dive. Unresolvable names are dropped rather than passed
            # through: a name the article never uses cannot be quoted in it.
            resolved = [n for n in (extract.resolve_name_in_text(text, e)
                                    for e in exec_names) if n]
            all_names = list(dict.fromkeys(resolved + speaker_names))
            page_note["resolved_exec_names"] = resolved

            quotes_by_theme: dict[str, list] = {}
            all_quotes = []
            for nm in all_names:
                qs, _rej = extract_quotes(text, nm, company_tokens=company_tokens)
                all_quotes.extend(qs)
                # Session 10 item 6 (T46): the rejections are what make the run log show
                # whether the harness was strict or blind. Kept, per quotes.py's own note.
                page_note.setdefault("quote_rejections", []).extend(
                    {"name": nm, **r} for r in _rej[:6])

            # Q&A transcripts carry no quotation marks, so extract_quotes finds nothing in
            # them. The all-caps speaker label is stronger attribution than a quotation
            # mark, not weaker -- the outlet names the speaker explicitly -- so a labelled
            # passage becomes an explicitly-attributed Quote, but ONLY for a speaker the
            # article already identified as an officer of this company.
            for passage in extract.qa_passages(text, speaker_names):
                themes = classify_buyer_voice(passage["text"])
                if not themes:
                    continue
                state, cue = quote_state(passage["text"])
                all_quotes.append(Quote(text=passage["text"], executive=passage["name"],
                                        attribution="explicit", themes=themes,
                                        state=state, state_cue=cue))

            for q in all_quotes:
                for theme_key in q.themes:
                    quotes_by_theme.setdefault(theme_key, []).append(q)

            has_attributed = any(q.attribution == "explicit" for q in all_quotes)
            sig_type, why_type = extract.article_type(
                text, r.title, r.url, all_names, has_attributed)

            if sig_type == "ST-PRESSPROFILE":
                actions, dropped = extract.reported_actions(text)
                # IN A MULTI-SUBJECT DOCUMENT, THE ACTION SENTENCE MUST NAME THE COMPANY.
                #
                # Widening the identity window (above) lets the company into a rankings
                # piece or a roundup. It must not also let the company inherit the whole
                # document's claims. Measured on the first v1.1 run, which produced two
                # new rows and both were false:
                #
                #   Rycon, from ENR's Top 400 Contractors -- all five action sentences
                #     were about GRAY CONSTRUCTION's AI adoption, quoting Gray's CEO.
                #     Rycon appears only as a row in the table.
                #   Kenco, from a supplychainbrain think-tank post -- the action sentence
                #     was a survey statistic, "Thirty-two percent are using these
                #     technologies...". Kenco is not the actor in it.
                #
                # This is the MedTech Dive defect in a new place: document-level content
                # attributed to a company that merely appears in the document. Convention
                # 31's corollary is the rule -- where many entities are present, proximity
                # attribution is worthless and only explicit naming counts. A narrative
                # article with one subject is unaffected, which is why the constraint is
                # conditioned on `multi` rather than applied everywhere.
                # APPLIED UNCONDITIONALLY, not only to multi-subject documents.
                #
                # Conditioning it on `multi` killed the Rycon rankings row and left the
                # Kenco one, whose action sentence is a survey statistic -- "Thirty-two
                # percent are using these technologies for process optimization" -- in an
                # ordinary think-tank post that no shape test flags. Kenco is not the actor
                # in that sentence, and the document being single-subject does not make it
                # so. The defect was never really about document shape; it was about
                # attributing an action to a company the sentence does not say performed
                # it.
                #
                # The cost is real and accepted: a narrative sentence using a pronoun
                # ("the company deployed...") is now refused. Convention 6a rates a gap
                # above a false record, and every drop is logged below, so the recall lost
                # is visible and recoverable rather than silent.
                #
                # Safe against convention 37: no released ST-PRESSPROFILE row exists to
                # break -- v1.0 admitted two rows and both are quote-based
                # ST-EXECQUOTE-REPORTED, which this does not touch.
                kept = []
                for a in actions:
                    named, _ = article.is_about_company(
                        a["sentence"], name, head_chars=len(a["sentence"]))
                    if named:
                        kept.append(a)
                    else:
                        log["multi_subject_actions_dropped"].append(
                            {"company_id": cid, "url": r.url, "multi_subject": multi,
                             "sentence": a["sentence"][:180],
                             "why": "the sentence reporting this action does not name the "
                                    "company, so the action belongs to some other party "
                                    "in the piece (convention 31's corollary)"})
                actions = kept
                if dropped:
                    log["characterizations_dropped"].extend(
                        {"company_id": cid, "url": r.url, "sentence": s}
                        for s in dropped[:3])
                by_theme: dict[str, list] = {}
                for a in actions:
                    for theme_key in a["themes"]:
                        by_theme.setdefault(theme_key, []).append(a)
                # Session 10 item 3: the company describing itself or its intent, as
                # reported, is articulation (ST-PRESSCHAR). Journalist-only framing is
                # still dropped and logged.
                chars, char_dropped = extract.reported_characterizations(text, name)
                if char_dropped:
                    log["characterizations_dropped"].extend(
                        {"company_id": cid, "url": r.url, "sentence": s}
                        for s in char_dropped[:3])
                char_by_theme: dict[str, list] = {}
                for ch in chars:
                    for theme_key in ch["themes"]:
                        char_by_theme.setdefault(theme_key, []).append(ch)
                for theme_key, chs in char_by_theme.items():
                    rows_for_company.append(
                        build_characterization(company, theme_key, chs, r.url, r.title,
                                               pub, stamp))
                    page_note["types"].append(f"ST-PRESSCHAR:{theme_key}")
                for theme_key, acts in by_theme.items():
                    terms = sorted({t for a in acts
                                    for ts in a["themes"].values() for t in ts})
                    action_low_grade = not article.theme_is_the_subject(terms, r.title)
                    if action_low_grade:
                        page_note["types"].append(f"profile:{theme_key}:below_admission_low_grade")
                    rows_for_company.append(
                        build_action(company, theme_key, acts, r.url, r.title, pub, stamp,
                                     low_grade=action_low_grade))
                    page_note["types"].append(f"ST-PRESSPROFILE:{theme_key}")
            else:
                for theme_key, qs in quotes_by_theme.items():
                    rows_for_company.append(
                        build_articulation(company, sig_type, theme_key, qs, r.url,
                                           r.title, pub, stamp, why_type))
                    page_note["types"].append(f"{sig_type}:{theme_key}")

            if not page_note["types"]:
                discarded += 1
                page_note["rejected"] = "no admissible claim"
            entry["pages"].append(page_note)

        # ---- LinkedIn, one attempt per company (v1.1, Task 5.5) ----
        # Companies where no LinkedIn URL surfaced at all are closed out as `not_covered`
        # by the run context on close, because the signal is declared in scope.
        if linkedin_blocked:
            urls = ", ".join(u for u, _ in linkedin_blocked[:3])
            run.attempt(cid, LINKEDIN_SIGNAL, outcome="not_covered",
                        failure_stage="fetch", failure_category="access_blocked",
                        fix_class="source_limitation",
                        candidates_evaluated=len(linkedin_blocked),
                        candidates_discarded=len(linkedin_blocked),
                        failure_detail=(
                            f"{len(linkedin_blocked)} LinkedIn URL(s) refused. LinkedIn "
                            f"publishes a robots.txt policy disallowing this crawler "
                            f"identity: {linkedin_blocked[0][1]}. Recorded as the source's "
                            f"own decision (convention 38) -- the Glassdoor precedent. No "
                            f"user-agent switched, no authenticated access attempted, no "
                            f"third-party mirror used: an evaded refusal is not evidence. "
                            f"e.g. {urls}")[:400],
                        source_url_attempted=linkedin_blocked[0][0])

        # HARD RULE enforcement, asserted rather than assumed.
        for o in rows_for_company:
            if "ST-PRESSCHAR" in o.observation_text and o.evidence_role != "buyer_articulates":

                raise SystemExit("hard rule: an ST-PRESSCHAR row is the company describing "

                                 "itself and must be buyer_articulates, never buyer_acts")

            if "ST-PRESSPROFILE" in o.observation_text and o.evidence_role != "buyer_acts":
                raise SystemExit(
                    f"ABORT: ST-PRESSPROFILE row for {cid} carries role "
                    f"{o.evidence_role!r}; §8.1 permits buyer_acts only")

        proposed.extend(rows_for_company)
        entry["rows"] = [{"role": o.evidence_role, "family": o.evidence_family,
                          "topic": o.topic, "grade": o.source_grade, "url": o.source_url}
                         for o in rows_for_company]

        if rows_for_company:
            run.attempt(cid, PRIMARY_SIGNAL, outcome="covered",
                        records_written=len(rows_for_company), output_sheet="Observations",
                        candidates_evaluated=evaluated, candidates_discarded=discarded,
                        source_url_attempted=rows_for_company[0].source_url)
            roles = {}
            for o in rows_for_company:
                roles[o.evidence_role] = roles.get(o.evidence_role, 0) + 1
            print(f"  [{len(rows_for_company):02d}] {cid} {name}: "
                  + ", ".join(f"{v} {k}" for k, v in sorted(roles.items())))
        elif evaluated == 0:
            run.attempt(cid, PRIMARY_SIGNAL, outcome="not_covered",
                        failure_stage="discovery", failure_category="source_not_found",
                        fix_class="source_limitation",
                        failure_detail=f"no search result from the {'/'.join(verticals)} "
                                       f"outlet allowlist for this company",
                        candidates_evaluated=0, candidates_discarded=0)
            print(f"  [--] {cid} {name}: no results")
        else:
            # Reached the outlets, read what they had, found nothing admissible. That is a
            # confirmed absence of trade-press articulation, not a miss -- but ONLY for
            # this bounded outlet set, which the detail says explicitly. Convention 6.
            run.attempt(cid, PRIMARY_SIGNAL, outcome="absent_confirmed",
                        candidates_evaluated=evaluated, candidates_discarded=discarded,
                        failure_detail=(
                            f"{evaluated} result(s) evaluated across the "
                            f"{'/'.join(verticals)} outlet allowlist; {fetched} article(s) "
                            f"read, {attempted} refused at fetch. No passage met the "
                            f"admission bar. Absence of trade-press articulation in THIS "
                            f"outlet set, not absence of articulation."))
            print(f"  [00] {cid} {name}: {fetched} article(s) read, nothing admissible")

        log["companies"].append(entry)

    # ---------------------------------------------------------------- write
    report = None
    if args.commit:
        # v1.2 supersedes v1.1's rows, so they are REMOVED rather than reconciled.
        #
        # sync_observations only touches rows the run actually proposes, so a corrected
        # harness that stops believing a row leaves the stale one sitting in the sheet --
        # a defect that REMOVES rows otherwise survives its own fix silently. Established
        # by H-PRODUCTQUALITY-01 v1.1's stale Midmark row.
        #
        # keep_reviewed=True: human review is never destroyed by a re-run (convention 1),
        # so a reviewed row survives the delete and is reconciled normally. Both
        # H-TRADEPRESS-01 rows are `accepted`/`human` and are protected by exactly this.
        removed = db.delete_observations(HARNESS_ID, keep_reviewed=True)
        if removed:
            print(f"  removed {removed} row(s) from superseded version(s) before writing")
        report = db.sync_observations(proposed)
        run.observations_written = report.written
    run.material_revision_notes = (
        "v1.0 first build. Subset run over 15 companies spanning construction, trucking, "
        "logistics, food distribution, medical devices, energy and consumer goods. "
        "QUARANTINED pending audit -- no coverage number is published for this run.")
    summary = run.close()

    roles = {}
    families = {}
    for o in proposed:
        roles[o.evidence_role] = roles.get(o.evidence_role, 0) + 1
        families[o.evidence_family] = families.get(o.evidence_family, 0) + 1
    print()
    print(f"  {len(subset)} companies with an outlet vertical (of 108; scope from Companies.industry_primary since v1.6) - "
          f"{len(proposed)} observations proposed")
    print(f"  by role:   {roles}")
    print(f"  by family: {families}")
    print(f"  wire reprints routed to first-party: {len(log['routed_to_firstparty'])}")
    print(f"  journalist characterisations dropped: "
          f"{len(log['characterizations_dropped'])}")
    print(f"  robots-blocked URLs: {len(log['robots_blocked'])}")
    if report:
        print(f"  dedupe: {report.summary()}")
    print("  PUBLICATION STATUS: quarantined -- row counts only, no coverage number")

    log["held"] = report.conflicts if report is not None else []
    log["summary"] = {"observations": len(proposed), "by_role": roles,
                      "by_family": families, "run": summary}
    out = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
    out.write_text(json.dumps(log, indent=2), encoding="utf-8")

    if args.commit:
        db.save()
        print(f"  committed to {db.path.name} ({run.run_id})")
    else:
        print("  DRY RUN -- nothing written. Re-run with --commit to write.")
    print(f"  run log: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
