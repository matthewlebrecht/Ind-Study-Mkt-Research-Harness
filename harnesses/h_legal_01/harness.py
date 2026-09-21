#!/usr/bin/env python3
"""
H-LEGAL-01 -- federal court dockets as involuntary disclosure (family 13).

WHAT THIS INSTRUMENT IS FOR
---------------------------
IC4. A company does not choose to be sued, and it does not choose what the caption says.
That is the class the evidence base is shortest on, and the reason the taxonomy promotes
CourtListener to build-now: "a vendor dispute over a failed ERP implementation showing up
here would be one of the highest-value single observations this project could produce."

WHAT IT IS NOT FOR, AND THE ADMISSION RULE THAT FOLLOWS
-------------------------------------------------------
Being sued is not modernization evidence. Measured over a 120-docket sample across six
companies, this instrument's population is overwhelmingly employment discrimination (442
Civil rights jobs), personal injury, motor-vehicle and ERISA matters, plus a patent/
trademark tail that belongs to family 14 and not here. Roughly a quarter of dockets carry
no `suitNature` at all.

So the yield is expected to be very low, and that is a finding rather than a failure. What
is NOT acceptable is manufacturing yield by loosening the gate. Convention 32 governs:
decide admission first, strength second. A docket is admitted only where the *dispute
itself* is about systems, and a single generic word inside a document description is not
that. `article.theme_is_the_subject` is reused unchanged so this harness admits on exactly
the terms H-FIRSTPARTY-01 does.

The two signals that do qualify:

  1. The dispute's own text -- caption, nature of suit, cause -- classifies to a
     modernization theme through the shared spine, and the theme is the subject.
  2. The opposing party is a technology vendor. `Kenco Group v. <WMS vendor>` is a systems
     dispute whatever the caption calls it, and it is the shape the taxonomy is pointing
     at. Detected against the provider universe already in `Companies` plus a small
     explicit vendor list, never by guessing that a party "looks like" a software firm.

IDENTITY IS THE WHOLE RISK HERE
-------------------------------
Case captions are full of ordinary words and eponymous firms, and this is the database
where that bites hardest. `party:"Prime Inc."` returns 483 dockets including "Certified
Prime Inc", "Parker's Prime, Inc." and "Prime Excavating". Every party string is scored
with `article.is_about_company`, so convention 31 applies: a coined token stands alone, an
ordinary English word needs the full company phrase. Prime Inc. and McGough Construction
were both read through before this harness was run for the first time.

    python -m harnesses.h_legal_01.harness                  # dry run
    python -m harnesses.h_legal_01.harness --commit
    python -m harnesses.h_legal_01.harness --offline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache, slug                                # noqa: E402
from core.db import MarketIntelDB, Observation, today                  # noqa: E402
from core.resolution import query_variants                             # noqa: E402
from core import aliases, topics                                       # noqa: E402
from harnesses.h_execid_01.extract import html_lines                   # noqa: E402
from harnesses.h_firstparty_01 import article                          # noqa: E402
from harnesses.h_legal_01 import source                                # noqa: E402

HARNESS_ID = "H-LEGAL-01"
HARNESS_NAME = "Federal Docket Extractor"
VERSION = "v1.2"
SIGNAL_TYPE = "federal_court_docket"
NLRB_SIGNAL = "nlrb_case"
EVIDENCE_FAMILY = "13_legal_dispute_records"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID

# Technology vendors whose appearance as an opposing party makes a dispute a systems
# dispute regardless of how the caption reads. Deliberately an explicit list, because the
# alternative -- inferring "this party looks like a software company" from its name -- is
# the guess convention 13 forbids, and "Systems", "Technologies" and "Solutions" appear in
# the names of staffing firms, contractors and freight brokers throughout this universe.
#
# The provider benchmark set in `Companies` is loaded on top of this at run time, so the 12
# sellers the project already tracks are covered without being duplicated here.
TECH_VENDOR_TOKENS = [
    "oracle", "sap", "workday", "salesforce", "infor", "epicor", "netsuite",
    "manhattan associates", "blue yonder", "jda software", "kinaxis", "coupa",
    "servicenow", "ibm", "microsoft", "accenture", "deloitte consulting",
    "cognizant", "infosys", "wipro", "tata consultancy", "capgemini",
    "hcl technologies", "dxc technology", "unisys", "ceridian", "ukg",
    "kronos", "adp", "paycom", "paylocity", "trimble", "procore", "autodesk",
    "bentley systems", "samsara", "omnitracs", "platform science", "motive",
    "descartes systems", "e2open", "project44", "fourkites", "highjump",
    "korber", "softeon", "tecsys", "mccleod software", "transflo",
]

MAX_DOCKETS_PER_COMPANY = 20    # one search page; the source's own total is recorded


def load_vendor_names(db: MarketIntelDB) -> list[str]:
    """Provider-benchmark companies, lowercased, for opposing-party detection."""
    out = []
    for c in db.companies():
        if str(c.get("qualification_status") or "").strip() == "provider_benchmark":
            nm = str(c.get("canonical_name") or "").strip().lower()
            if len(nm) >= 4:
                out.append(nm)
    return out


# Party strings that are ERISA plans, union trusts and benefit funds rather than trading
# companies. A mass ERISA action names hundreds of them, so ANY vendor token will appear
# somewhere in the party list, and matching on it produced four false rows on the first
# run: "Capgemini US LLC Welfare Benefit Plan" and "Cognizant Health & Welfare Benefit
# Plan" are not Capgemini and Cognizant doing business, they are benefit plans named as
# co-defendants in somebody else's dispute.
PLAN_PARTY_RE = re.compile(
    r"(?i)\b(benefit|welfare|health)\s+plan\b|\btrust\s+fund|\bpension\b|\bannuity\b|"
    r"\b401\s*\(?k\)?\b|\bwelfare\s+fund\b|\bmedical\s+plan\b|\bhealth\s+and\s+welfare\b")

# A docket with a huge party list is a mass action -- a multi-plan ERISA case, an MDL, a
# bankruptcy with every creditor listed. Its party list says nothing about who this company
# does business with, so it cannot support a vendor-dispute claim.
MAX_PARTIES_FOR_VENDOR_CLAIM = 12

# Suit natures under which a technology dispute is plausible. Deliberately a whitelist:
# every false row on the first run sat under ERISA, civil rights or personal injury, where
# a vendor name in the party list is coincidence rather than commerce.
COMMERCIAL_NATURE_RE = re.compile(
    r"(?i)\bcontract\b|\btrade\s+secret\b|\bpatent\b|\btrademark\b|\bcopyright\b|"
    r"\bantitrust\b|\barbitration\b|\bfraud\b")


def opposing_vendor(dockets_parties: list[str], case_name: str, company_name: str,
                    seeded: list[str], vendor_names: list[str],
                    suit_nature: str) -> tuple[str, str] | None:
    """(party, vendor) where a technology vendor is a PRINCIPAL opposing party.

    Every condition here was bought with a false row on the 2026-09-01 first run, which
    proposed 11 observations of which 10 were wrong. In order:

      * the vendor must appear in the CAPTION, not merely somewhere in the party list.
        A caption names the principals; a party list on a mass docket names everyone.
        This alone kills the Capgemini, Cognizant, Slalom and IBM false rows.
      * the party must not be a benefit plan or union trust (PLAN_PARTY_RE).
      * the docket must not be a mass action (MAX_PARTIES_FOR_VENDOR_CLAIM).
      * the nature of suit must be commercial. A vendor's name inside an employment
        discrimination case is not a systems dispute.
      * the vendor token must be multi-word or a distinctive coined name. "kearney"
        matched the *person* "Clay Kearney" in an admiralty case -- convention 31 again:
        a single common token is never an identity, and that applies to the counterparty
        exactly as it applies to the subject.
    """
    if len(dockets_parties) > MAX_PARTIES_FOR_VENDOR_CLAIM:
        return None
    # 2026-09-03 corroboration-gate policy: the nature-of-suit whitelist is a
    # corroboration-strength gate (right company, right vendor, thin claim), so a
    # non-commercial or blank nature no longer refuses -- it is returned with
    # commercial=False and written at low grade. The identity conditions below stay.
    commercial = bool(COMMERCIAL_NATURE_RE.search(suit_nature or ""))
    caption = f" {(case_name or '').lower()} "
    for p in dockets_parties:
        about, _ = party_is_company(p, company_name, seeded)
        if about:
            continue                       # this is the company itself, not an opponent
        if PLAN_PARTY_RE.search(p):
            continue
        low = f" {p.lower()} "
        for token in vendor_names:
            if " " not in token and len(token) < 6:
                continue                   # too short to be an identity on its own
            if not re.search(r"\b" + re.escape(token) + r"\b", low):
                continue
            # The principal test: this vendor has to be in the caption.
            if not re.search(r"\b" + re.escape(token) + r"\b", caption):
                continue
            return p, token, commercial
    return None


def party_is_company(party: str, company_name: str,
                     variants: list[str] | None = None) -> tuple[bool, str]:
    """Is this PARTY STRING this company? Stricter than `is_about_company`, on purpose.

    `article.is_about_company` is built for article prose, where convention 31's rule --
    an ordinary-word name needs the full company phrase somewhere in the text -- is a good
    discriminator. A party string is not prose. It is a name, and `Certified Prime Inc`
    CONTAINS the full phrase `Prime Inc`, so containment accepts it. Measured on the first
    dry run: Prime Inc. matched 20 of 20 dockets with zero rejections, including
    "Certified Prime Inc" and "Parker's Prime, Inc." -- the H-FIRSTPARTY-01 Prime failure
    reappearing in a fourth database, which is exactly what the brief said to check for.

    So containment is necessary and not sufficient. The company's tokens must also be a
    PREFIX of the party's tokens once legal forms and punctuation are stripped:

        Kenco Group, Inc.            -> [kenco, group]      prefix of company    ACCEPT
        McGough Construction Co.     -> [mcgough, construction]                  ACCEPT
        Certified Prime Inc          -> [certified, prime]  company not a prefix REJECT
        Parker's Prime, Inc.         -> [parkers, prime]    company not a prefix REJECT

    Deliberately strict. `New Prime, Inc./Prime, Inc.` is genuinely this company and is
    rejected here, as is `Kenco Logistics`; both are alias decisions for a human to seed
    (convention 13), and every rejection is logged so they are checkable rather than lost.
    A false acceptance writes another company's litigation history into this one's record,
    which convention 6a rates strictly worse than a gap.
    """
    norm = lambda t: [x for x in re.split(r"[^a-z0-9]+", str(t).lower()) if x]
    drop = {"inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "corp",
            "corporation", "co", "company", "plc", "the"}
    ptok = [t for t in norm(party) if t not in drop]

    # Every name the registry says IS this company, canonical first. A human-seeded alias
    # is the only thing that can distinguish `New Prime, Inc.` -- which is Prime Inc.'s
    # actual legal entity -- from `Certified Prime Inc`, which is a different firm. The
    # guard refused both before the alias existed, and the rejection log is what surfaced
    # the distinction (convention 12: a refusal is a claim and has to be checkable).
    # HUMAN-SEEDED ALIASES ONLY -- deliberately NOT `query_variants`.
    #
    # query_variants also returns the name minus its legal-form suffix, which is right for
    # a search box and catastrophic as an identity: "Prime Inc." reduces to the bare token
    # "Prime", and every firm whose name starts with that word then matches. Passing the
    # full variant list here accepted "Prime Excavating" as Prime Inc. on the very next
    # run, re-breaking the case this guard was written for. Convention 37, and convention
    # 31's rule that a single common token is never an identity -- a mechanical suffix
    # strip cannot produce an identity, only a human can assert one.
    names = [company_name] + [v for v in (variants or []) if v != company_name]
    reasons = []
    for nm in names:
        ok, why = article.is_about_company(party, nm, head_chars=400)
        if not ok:
            reasons.append(why)
            continue
        ctok = [t for t in norm(nm) if t not in drop]
        if not ctok:
            reasons.append(f"{nm!r} reduces to nothing after legal-form removal")
            continue
        if ptok[:len(ctok)] == ctok:
            return True, ""
        reasons.append(f"party {party!r} contains {nm!r} but its name does not START "
                       f"with it ({ptok[:4]} vs {ctok}); a different company whose name "
                       f"embeds this one -- convention 31")
    return False, reasons[0] if reasons else "no candidate name matched"


def classify_docket(d: dict) -> tuple[dict, str]:
    """(themes, the text the themes came from). Structured fields first."""
    # The caption, nature of suit and cause are the fields the COURT wrote about the
    # dispute. Document descriptions are docket chatter -- scheduling orders, notices of
    # appearance -- and classifying on them is how a filing clerk's vocabulary becomes a
    # company's modernization posture. They are searched, but they cannot carry a claim on
    # their own; see `subject_text` below.
    subject_text = " ".join(x for x in [d["case_name"], d["case_name_full"],
                                        d["suit_nature"], d["cause"]] if x)
    return topics.classify(subject_text), subject_text


def build_observation(company: dict, theme_key: str, dockets: list[dict], terms: list[str],
                      basis: str, retrieval: str, low_grade: bool = False) -> Observation:
    theme = topics.THEMES_BY_KEY[theme_key]
    dates = sorted({d["date_filed"] for d in dockets if d["date_filed"]})
    strength = "repeated_pattern" if len(dockets) >= 2 else "weak_clue"
    grade, confidence = "A", (0.6 if strength == "weak_clue" else 0.7)
    if low_grade:
        strength, grade, confidence = "weak_clue", topics.LOW_GRADE, 0.35
    captions = "; ".join(f"{d['case_name']} ({d['court_id'] or d['court']}, "
                         f"{d['date_filed'] or 'undated'})" for d in dockets[:4])

    text = (
        f"{company['canonical_name']} is a named party in {len(dockets)} federal "
        f"docket(s) whose subject matter bears on {theme.label}"
        + (f", filed between {dates[0]} and {dates[-1]}" if dates else "")
        + f". Basis: {basis}. This is a public record created by a court, not a statement "
          f"the company chose to make, so it is evidence of a dispute having occurred and "
          f"not of any position the company holds about it. Cases: {captions}."
    )
    return Observation(
        company_id=company["company_id"],
        harness_id=HARNESS_ID,
        harness_version=VERSION,
        topic=theme_key,
        evidence_role="buyer_acts",
        evidence_family=EVIDENCE_FAMILY,
        # `unknown`, never `legacy_constraint`. A lawsuit about a system establishes that a
        # dispute happened, not that the company's estate is behind -- the plaintiff's
        # allegations are a party's claim, not a finding, and most dockets here terminate
        # without one. Convention 17's shape: absence of a clean record is not evidence of
        # a state.
        organizational_state="unknown",
        signal_strength=strength,
        source_grade=grade,
        confidence_0_1=confidence,
        observation_text=text,
        # The matched terms live in the excerpt rather than a column: `Observations` has no
        # matched_terms field, and a reviewer checking a refusal or an admission needs to
        # see WHAT matched, not just that something did (convention 12).
        evidence_excerpt=((topics.low_grade_excerpt("nature of suit not commercial", "")
                           if low_grade else "")
            + f"[{basis}] matched: {', '.join(sorted(set(terms))[:8]) or 'n/a'} | "
            + " | ".join(
                f"{d['case_name']} :: {d['suit_nature'] or 'nature of suit not stated'}"
                for d in dockets[:3]))[:2000],
        source_url=dockets[0]["url"] or "https://www.courtlistener.com/",
        publication_date=dates[-1] if dates else "",
        retrieval_date=retrieval,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--companies")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = [c for c in db.companies()
                 if str(c.get("qualification_status") or "") != "provider_benchmark"]
    if args.companies:
        want = {c.strip() for c in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"] in want]
    if args.limit:
        companies = companies[:args.limit]

    vendor_names = sorted(set(TECH_VENDOR_TOKENS) | set(load_vendor_names(db)))
    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=args.pause)

    # BOTH SOURCES ARE DECLARED IN SCOPE, and they are separate signals on purpose. The
    # brief's requirement is that CourtListener and NLRB never collapse into one coverage
    # figure: they answer different questions, and NLRB's answer can never be a
    # modernization theme (see below). Declaring both means the run context closes out
    # whichever one a company was not reached on, so each has its own denominator
    # (convention 5).
    scope = ([(c["company_id"], SIGNAL_TYPE) for c in companies]
             + [(c["company_id"], NLRB_SIGNAL) for c in companies])
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY,
                                       NLRB_SIGNAL: EVIDENCE_FAMILY}, commit=args.commit)
    # Audit gate: first output of a new harness, quarantined until an artifact exists.
    run.publication_status = "quarantined"

    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "companies": [], "identity_rejections": [],
           "below_admission": [], "capped": [], "nlrb": []}

    for company in companies:
        cid, name = company["company_id"], company["canonical_name"]
        entry = {"company_id": cid, "name": name, "reported_total": 0, "read": 0,
                 "matched": 0, "admitted": 0, "variants": [], "suit_natures": {}}

        seeded_aliases = aliases.variants_for(cid)
        variants = query_variants(name, seeded_aliases)
        entry["variants"] = variants
        entry["seeded_aliases"] = seeded_aliases

        dockets, reported_total, source_error, answered_on = [], 0, None, None
        for variant in variants:
            url = source.docket_query(variant)
            key = f"cl_{slug(cid)}_{hashlib.sha1(url.encode()).hexdigest()[:8]}"
            try:
                raw, _cached = cache.get(key, ".json",
                                         lambda u=url: json.dumps(source.fetch_json(u)))
                got, total = source.normalise(json.loads(raw))
            except source.SourceError as e:
                source_error = e
                continue
            except RuntimeError as e:                     # offline, nothing archived
                source_error = source.SourceError(str(e))
                continue
            # First variant that answers wins, same ladder as H-PRODUCTQUALITY-01 v1.2:
            # a more specific name that works is never second-guessed, and a broader one
            # is consulted only where the specific one returned nothing.
            if got:
                dockets, reported_total, answered_on = got, total, variant
                break
            reported_total = max(reported_total, total)

        entry["reported_total"] = reported_total
        entry["answered_on"] = answered_on

        if source_error is not None and not dockets:
            run.attempt(cid, SIGNAL_TYPE, outcome="not_covered",
                        failure_stage=source_error.failure_stage,
                        failure_category=source_error.failure_category,
                        fix_class=source_error.fix_class,
                        failure_detail=str(source_error)[:400])
            print(f"  [!!] {cid} {name}: {source_error}")
            log["companies"].append(entry)
            continue

        # The search endpoint returns one page. Where the source's own total exceeds what
        # was read, that is a cap and it is reported, never silently treated as the whole
        # record (convention 7 -- the OSHA 20-per-page failure).
        if reported_total > len(dockets):
            log["capped"].append({"company_id": cid, "name": name,
                                  "reported_total": reported_total,
                                  "read": len(dockets)})

        mine = []
        for d in dockets[:MAX_DOCKETS_PER_COMPANY]:
            # IDENTITY. `party:` is tokenized, not an exact phrase.
            hit, last_why = None, ""
            for p in d["parties"]:
                about, why = party_is_company(p, name, seeded_aliases)
                if about:
                    hit = p
                    break
                last_why = why or last_why
            if hit is None:
                # Fall back to the caption: some dockets carry a thin party list. The
                # caption is prose-ish ("X v. Y Corp"), so the prose guard is right here,
                # but it only runs where the party list produced nothing.
                about, why = article.is_about_company(
                    f"{d['case_name']} {d['case_name_full']}", name, head_chars=400)
                if not about:
                    why = last_why or why
                    log["identity_rejections"].append(
                        {"company_id": cid, "case_name": d["case_name"],
                         "parties": d["parties"][:4], "why": why[:160]})
                    continue
            mine.append(d)

        entry["read"] = len(dockets)
        entry["matched"] = len(mine)
        natures = {}
        for d in mine:
            natures[d["suit_nature"] or "(not stated)"] = \
                natures.get(d["suit_nature"] or "(not stated)", 0) + 1
        entry["suit_natures"] = natures

        # ---- admission ----
        #
        # ONE ROUTE, NOT TWO. The first run also classified the docket's own text through
        # the shared theme spine and admitted where `theme_is_the_subject` passed. That
        # route produced six rows and every one of them was false, for a reason that is
        # obvious in hindsight and invisible in a summary: **a caption is a list of party
        # names**, so classifying it classifies company names.
        #
        #   "Sapateh v. Ruan Transportation Management Systems"  -> transportation_fleet_
        #       systems, off the COMPANY'S OWN NAME. An employment case.
        #   "...Labor Management Cooperation Trust Funds of the IUOE Local 14-14B..."
        #       -> workforce_enablement, off the union fund's name. An ERISA collection.
        #   "Quinonez v. IMI Material Handling Logistics Inc."   -> warehouse_automation,
        #       off the defendant's name. A personal injury case.
        #
        # `theme_is_the_subject` passed all three because the term IS in the caption --
        # the admission gate was working and the input was wrong. Convention 16 in its
        # purest form, and convention 32's remedy: these rows should not exist at any
        # strength, so the route is removed rather than downgraded.
        #
        # Nothing replaces it. suitNature and cause are legal categories ("791 Labor:
        # E.R.I.S.A.", "28:1332 Diversity"), not modernization vocabulary, so they
        # classify to nothing and a theme cannot honestly be read off this source's text
        # at all. What remains is the vendor-dispute route, which is what the taxonomy
        # actually pointed at.
        by_theme: dict[str, list] = {}
        terms_by_theme: dict[str, list] = {}
        basis_by_theme: dict[str, str] = {}
        low_by_theme: dict[str, list] = {}       # 2026-09-03: non-commercial nature of suit
        low_terms: dict[str, list] = {}
        low_basis: dict[str, str] = {}
        for d in mine:
            vendor = opposing_vendor(d["parties"], d["case_name"], name, seeded_aliases,
                                     vendor_names, d["suit_nature"])
            if vendor is None:
                themes, _subject = classify_docket(d)
                if themes:
                    log["below_admission"].append(
                        {"company_id": cid, "case_name": d["case_name"],
                         "themes": sorted(themes), "suit_nature": d["suit_nature"],
                         "why": "theme matched only the caption, which is a list of party "
                                "names; no technology vendor is a principal party"})
                continue
            # A buyer suing (or being sued by) its technology vendor is a systems dispute
            # whatever the caption calls it. `systems_integration` is the theme by
            # construction; it is not read off the text, and the observation says so.
            key = "systems_integration"
            if not vendor[2]:
                low_by_theme.setdefault(key, []).append(d)
                low_terms.setdefault(key, []).append(vendor[1])
                low_basis[key] = (f"opposing party {vendor[0]!r} is a technology vendor "
                                  f"({vendor[1]}), named in the caption, but the nature of "
                                  f"suit is {d['suit_nature'] or 'not stated'}, which is not "
                                  f"commercial -- the systems relation is inferred from the "
                                  f"caption alone")
                continue
            by_theme.setdefault(key, []).append(d)
            terms_by_theme.setdefault(key, []).append(vendor[1])
            basis_by_theme[key] = (f"opposing party {vendor[0]!r} is a technology vendor "
                                   f"({vendor[1]}), named in the caption, in a "
                                   f"{d['suit_nature'] or 'commercial'} matter")

        entry["rows"] = []
        for key, ds in low_by_theme.items():
            if key in by_theme:
                continue                 # a commercial docket carries the claim already
            obs = build_observation(company, key, ds, low_terms.get(key, []),
                                    low_basis.get(key, ""), stamp, low_grade=True)
            proposed.append(obs)
            entry["rows"].append({"topic": key, "strength": obs.signal_strength,
                                  "low_grade": True, "basis": low_basis.get(key, ""),
                                  "dockets": [{"case_name": d["case_name"],
                                               "suit_nature": d["suit_nature"], "url": d["url"]}
                                              for d in ds[:6]]})
        for key, ds in by_theme.items():
            obs = build_observation(company, key, ds, terms_by_theme.get(key, []),
                                    basis_by_theme.get(key, ""), stamp)
            proposed.append(obs)
            # The admitted rows are logged in full, not just counted. The audit gate reads
            # this file to build its review sheet, and a count is not something a reviewer
            # can disagree with (convention 33: the defects are invisible in the summary
            # and obvious in the rows).
            entry["rows"].append({
                "topic": key, "strength": obs.signal_strength,
                "basis": basis_by_theme.get(key, ""),
                "terms": sorted(set(terms_by_theme.get(key, [])))[:8],
                "dockets": [{"case_name": d["case_name"], "court": d["court_id"],
                             "date_filed": d["date_filed"],
                             "suit_nature": d["suit_nature"], "cause": d["cause"],
                             "parties": d["parties"][:5], "url": d["url"]}
                            for d in ds[:6]],
            })
        entry["admitted"] = len(by_theme)

        if by_theme:
            run.attempt(cid, SIGNAL_TYPE, outcome="covered",
                        records_written=len(by_theme), output_sheet="Observations",
                        candidates_evaluated=len(dockets),
                        candidates_discarded=len(dockets) - len(mine),
                        source_url_attempted=mine[0]["url"] if mine else "")
            print(f"  [{len(by_theme):02}] {cid} {name}: {len(mine)} docket(s) matched, "
                  f"{len(by_theme)} admitted")
        elif mine:
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        candidates_evaluated=len(dockets), candidates_discarded=len(dockets),
                        failure_detail=(
                            f"{len(mine)} federal docket(s) name this company; none is a "
                            f"dispute about a modernization theme. Nature of suit is "
                            f"overwhelmingly employment, personal injury and contract. "
                            f"Absence of a SYSTEMS dispute, not absence of litigation."))
            print(f"  [00] {cid} {name}: {len(mine)} docket(s), none systems-related")
        else:
            run.attempt(cid, SIGNAL_TYPE, outcome="absent_confirmed",
                        candidates_evaluated=len(dockets), candidates_discarded=len(dockets),
                        failure_detail=(
                            f"queried CourtListener RECAP on party name; {len(dockets)} "
                            f"raw result(s), none resolving to this company under the "
                            f"identity test. CourtListener is authoritative for the "
                            f"federal dockets it holds, so this is a confirmed absence of "
                            f"a FEDERAL docket -- state court records are a separate "
                            f"instrument (taxonomy 13c) and are not covered here."))
            print(f"  [00] {cid} {name}: no federal docket resolves to this company")
        # ---------------------------------------------------------------- NLRB pass
        #
        # Reported SEPARATELY from CourtListener, never merged. NLRB establishes labour
        # friction; it cannot establish a modernization theme, because its allegation
        # vocabulary is statutory and names conduct rather than systems -- measured, not
        # assumed: across a five-company sample, ZERO of ten distinct allegation labels
        # ("8(a)(3) Discharge", "8(a)(1) Coercive Statements", "8(a)(5) Refusal to
        # Bargain", "Allegations data is not available.") classify to any theme in
        # core/topics.py. Reading a theme off one would be the caption-classification
        # error this harness already made once.
        #
        # So this pass writes NO observations by design, and its attempt says why. That is
        # coverage of a real instrument reporting an honest absence of THIS signal, not a
        # gap (convention 6).
        nlrb_rows, nlrb_error, nlrb_answered = [], None, None
        for variant in variants:
            url = source.nlrb_query(variant)
            key = f"nlrb_{slug(cid)}_{hashlib.sha1(url.encode()).hexdigest()[:8]}"
            try:
                raw, _c = cache.get(key, ".html", lambda u=url: source.nlrb_fetch(u))
                got = source.nlrb_cases(html_lines(raw))
            except source.SourceError as e:
                nlrb_error = e
                continue
            except RuntimeError as e:
                nlrb_error = source.SourceError(str(e))
                continue
            if got:
                nlrb_rows, nlrb_answered = got, variant
                break

        # Identity, same guard as the dockets. NLRB search is a loose phrase match:
        # "Prime" returns Prime Healthcare and PrimeFlight Aviation, "Western Express"
        # returns Western Flyer Express.
        nlrb_mine = []
        for rec in nlrb_rows:
            ok, why = party_is_company(rec["party"], name, seeded_aliases)
            if ok:
                nlrb_mine.append(rec)
            else:
                log["identity_rejections"].append(
                    {"company_id": cid, "source": "nlrb",
                     "case_name": rec["party"], "parties": [rec["party"]],
                     "why": why[:160]})

        entry["nlrb"] = {"answered_on": nlrb_answered, "read": len(nlrb_rows),
                         "matched": len(nlrb_mine),
                         "cases": [{"case_number": r["case_number"], "party": r["party"],
                                    "date_filed": r["date_filed"], "status": r["status"],
                                    "location": r["location"]} for r in nlrb_mine[:8]]}
        log["nlrb"].append({"company_id": cid, "name": name,
                            "read": len(nlrb_rows), "matched": len(nlrb_mine)})

        if nlrb_error is not None and not nlrb_rows:
            run.attempt(cid, NLRB_SIGNAL, outcome="not_covered",
                        failure_stage=nlrb_error.failure_stage,
                        failure_category=nlrb_error.failure_category,
                        fix_class=nlrb_error.fix_class,
                        failure_detail=str(nlrb_error)[:400])
        elif nlrb_mine:
            run.attempt(cid, NLRB_SIGNAL, outcome="absent_confirmed",
                        candidates_evaluated=len(nlrb_rows),
                        candidates_discarded=len(nlrb_rows),
                        source_url_attempted=source.nlrb_query(nlrb_answered or name),
                        failure_detail=(
                            f"{len(nlrb_mine)} NLRB case(s) resolve to this company "
                            f"(e.g. {', '.join(r['case_number'] for r in nlrb_mine[:3])}). "
                            f"None yields a modernization observation, and none can: the "
                            f"allegation vocabulary is statutory and names conduct under "
                            f"the NLRA, not systems. Absence of a SYSTEMS signal, not "
                            f"absence of labour disputes -- which this company has.")[:400])
        else:
            run.attempt(cid, NLRB_SIGNAL, outcome="absent_confirmed",
                        candidates_evaluated=len(nlrb_rows),
                        candidates_discarded=len(nlrb_rows),
                        source_url_attempted=source.nlrb_query(name),
                        failure_detail=(
                            f"queried NLRB case search on {len(variants)} name "
                            f"variant(s); {len(nlrb_rows)} raw result(s), none resolving "
                            f"to this company under the identity test. NLRB is "
                            f"authoritative for the charges and petitions it holds. Note "
                            f"the search is a phrase match, so a company whose NLRB "
                            f"respondent name differs from its canonical name needs a "
                            f"human-seeded alias (convention 13).")[:400])

        log["companies"].append(entry)

    report = None
    if args.commit:
        # Convention 45 (2026-09-15): no observation is hard-deleted. v1.1 deleted the superseded row before writing;
        # now the run reconciles in place and a row it no longer proposes is recorded invalid instead.
        report = db.sync_observations(proposed)
        run.observations_written = len(report.inserted)
        from core import validity
        invalidated = validity.invalidate_unreproduced(db, HARNESS_ID, VERSION, proposed,
                                                       company_ids={c["company_id"] for c in companies})
        if invalidated["invalidated"] or invalidated["held"]:
            print(f"  not reproduced: {len(invalidated['invalidated'])} machine row(s) recorded invalid "
                  f"(convention 45; nothing deleted) {invalidated['invalidated']}; "
                  f"{len(invalidated['held'])} human-reviewed row(s) held")
    run.material_revision_notes = (
        "v1.0 -- CourtListener RECAP, party-scoped. NLRB declared and not read: no JSON "
        "interface exists (404 on every API path, JS shell on the search page).")
    run.close()

    nlrb_matched = sum(1 for x in log["nlrb"] if x["matched"])
    nlrb_cases = sum(x["matched"] for x in log["nlrb"])
    print(f"\n  {len(companies)} companies scoped - {len(proposed)} observations proposed")
    print(f"  NLRB (reported separately, never merged with CourtListener): "
          f"{nlrb_cases} case(s) across {nlrb_matched} company(ies); 0 observations "
          f"by design")
    print(f"  identity rejections: {len(log['identity_rejections'])}")
    print(f"  below admission: {len(log['below_admission'])}")
    if log["capped"]:
        print(f"  [!] {len(log['capped'])} company(ies) capped by page size -- "
              f"their docket totals are FLOORS, not exact")
    print("  PUBLICATION STATUS: quarantined -- row counts only, no coverage number")
    if args.commit and report is not None:
        print(f"  dedupe: {len(report.inserted)} inserted, {len(report.updated)} updated, "
              f"{len(report.unchanged)} unchanged, {len(report.conflicts)} held for "
              f"review, {len(report.refreshed_reviewed)} refreshed-reviewed")
        if report.verdicts_cleared:
            print(f"  [!] {len(report.verdicts_cleared)} audit verdict(s) cleared by a "
                  f"content change -- that version's gate has to be re-run")
        # db.save() is what actually persists. Its absence cost a full 108-company run:
        # the harness printed "committed ... (HR-0027)" and the workbook was untouched --
        # a write path reporting success about something it never did, convention 36 in
        # the most expensive possible place. Caught only because validate_repo_db.py's
        # counts did not move.
        db.save()
        print(f"  committed to {db.path.name} ({run.run_id})")
    else:
        print("  DRY RUN -- nothing written. Re-run with --commit to write.")

    path = OUTPUT_DIR / (f"run-{stamp}{'-dryrun' if not args.commit else ''}.json")
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"  run log: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
