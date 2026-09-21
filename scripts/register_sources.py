#!/usr/bin/env python3
"""
Add new reference rows to `Source_Families` and `Signal_Types`.

Both sheets are reference vocabularies that `scripts/validate_repo_db.py` checks manifests
against (checks 3 and 5). A new harness that cites a source or a signal type nothing has
used before needs the registry row to exist first, or validation fails.

Additive-only, matching convention 22: this script inserts rows that are missing and
leaves existing ones alone. It never renames or deletes, because renaming a controlled
value breaks version-over-version trend queries against rows already written.

    python scripts/register_sources.py
    python scripts/register_sources.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.workbook_backup import backup_workbook  # noqa: E402
DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"

# (source_id, evidence_family, source_name, access_type, private_company_applicable,
#  expected_coverage, notes)
NEW_SOURCES = [
    # ---- 2026-09-13, Week 4: H-LOCALRECORDS-01's techstack sub-scope ----
    # SRC-0016 is BuiltWith / Wappalyzer (paid, third-party detection). This is the company's
    # own served homepage read for specific markers, a different source with different reach.
    ("SRC-0052", "5_technology_stack_traces",
     "Company homepage as served (own domain), technology markers",
     "WEB", "Yes", "Strong",
     "The company's own homepage HTML, read for specific front-end markers (asset hosts, "
     "generator tags, platform paths such as /wp-content/ or js.hs-scripts.com), never bare "
     "words. Front end only: what the public site is built on, not internal systems. "
     "current_only. Read from H-EXECID-01's dated archive by H-LOCALRECORDS-01."),
    # ---- state AG breach-notification portals, for H-BREACHPORTAL-01 (session 16) ----
    # The portfolio's first IC4 instrument for the cybersecurity theme (taxonomy §26). The
    # taxonomy has no cyber family; these are regulatory disclosure records, so they are
    # filed with the other regulator-held involuntary records (family 9) and flagged for
    # the taxonomy owner. A portal lists every organisation that notified THAT state's
    # residents, wherever it is headquartered: presence is searchable for all 108, but a
    # licensed ABSENCE is claimed only for companies headquartered in the portal's state.
    ("SRC-0050", "9_industrial_safety_environmental",
     "California DOJ data-breach notification list (oag.ca.gov/privacy/databreach/list)",
     "WEB", "Yes", "Strong",
     "IC4 involuntary disclosure. Every breach affecting 500+ California residents since "
     "2012, filed by organisation name, filterable by name (field_sb24_org_name_value). An "
     "empty result carries the page's own marker ('There are currently no published "
     "reported breaches.'), so absence is a read result, not a parse failure. robots.txt "
     "permits this crawler. Read by H-BREACHPORTAL-01."),
    ("SRC-0051", "9_industrial_safety_environmental",
     "Washington AG data-breach notifications (atg.wa.gov/data-breach-notifications)",
     "WEB", "Yes", "Strong",
     "IC4 involuntary disclosure. Every breach affecting 500+ Washington residents since "
     "2015, a paginated list (~38 pages of 50) read in full and matched locally by name -- "
     "the site's search form is a POST with a Drupal build id, so the whole list is the "
     "reliable path. robots.txt permits this crawler. Read by H-BREACHPORTAL-01."),
    ("SRC-0039", "1_first_party_strategy_governance",
     "Company leadership / executive team pages", "WEB", "Yes", "Moderate-Strong",
     "First-party statement of who runs the company. Strong for private mid-size firms, "
     "which typically publish a leadership page even when they publish little else. "
     "Read by H-EXECID-01."),
    ("SRC-0041", "4_employee_experience_workarounds",
     "Comparably company review pages", "WEB", "Yes", "Sparse-Moderate",
     "Employee review aggregate. Used as the family-4 substitute because Glassdoor "
     "(robots Disallow: / for AI crawler identities) and Indeed (/cmp/ disallowed) are "
     "both closed to compliant automated collection. Rate-limits aggressively. Read by "
     "H-EMPREVIEW-01."),
    ("SRC-0040", "1_first_party_strategy_governance",
     "Brave Search API (web index)", "API", "Yes", "Strong",
     "Cross-family DISCOVERY mechanism, not an evidence source. Used to locate first-party "
     "pages when a URL is unknown; never cited in an Observation or a Company_Executives "
     "row, which always cite the page the result points to. Filed under family 1 because "
     "that is where it was first used -- the family is not a constraint on which harnesses "
     "may use it, and H-EXECVOICE-01 and H-FIRSTPARTY-01 use it against families 15 and 1 "
     "respectively. Harnesses record it in Harness_Sources with role=resolution_only."),
    # ---- trade press, for H-TRADEPRESS-01 (taxonomy patch rev 2 §8) ----
    # Registered as two outlet families rather than one row per title. That matches how
    # this sheet is already used ("Trade publications", "Local business journal
    # (Bizjournals)"), and it matches reality: the Industry Dive titles share a platform,
    # a URL shape and a robots policy, so they succeed and fail together. SRC-0029
    # ("Trade publications", filed under family 12) stays as-is and is cited as
    # `supporting`; splitting these out gives H-TRADEPRESS-01 checkable provenance for
    # which outlet a claim came from, which one generic row cannot.
    ("SRC-0042", "15_executive_candor_actor_networks",
     "Industry Dive vertical trade titles (Construction Dive, Supply Chain Dive, "
     "Food Dive, MedTech Dive, Utility Dive)", "WEB", "Yes", "Moderate",
     "Reported trade journalism carrying attributable executive quotes. IC2: the speech "
     "is volunteered but the topic is elicited by a reporter and the publication decision "
     "is the outlet's. Shared platform, URL shape and robots policy across titles. Read "
     "by H-TRADEPRESS-01."),
    ("SRC-0043", "15_executive_candor_actor_networks",
     "Trucking and freight trade press (Transport Topics, FleetOwner, CCJ, Overdrive)",
     "WEB", "Yes", "Moderate",
     "Vertical trade journalism for the trucking and logistics half of the universe, "
     "which the Industry Dive network covers less densely. IC2. Read by H-TRADEPRESS-01."),
    # ---- federal recall / adverse-event databases, for H-PRODUCTQUALITY-01 ----
    # SRC-0027 (CPSC recalls) already exists and is reused; these are the two openFDA
    # endpoints and NHTSA, which the original taxonomy row did not distinguish.
    ("SRC-0044", "11_product_quality_customer_friction",
     "openFDA device recall and MAUDE adverse-event APIs", "API", "Yes", "Strong",
     "IC4 involuntary disclosure. Authoritative and complete for firms holding an FDA "
     "device registration, and silent about everyone else -- which is why "
     "H-PRODUCTQUALITY-01 records companies outside that population as not_covered rather "
     "than absent_confirmed. Answers HTTP 404 for 'no matching records', which is a result "
     "and not a failure."),
    ("SRC-0045", "11_product_quality_customer_friction",
     "openFDA food enforcement API", "API", "Yes", "Strong",
     "IC4. Food recall enforcement reports. Same population caveat as SRC-0044."),
    ("SRC-0046", "11_product_quality_customer_friction",
     "NHTSA recalls and complaints API", "API", "Yes", "Moderate",
     "IC4. Applies to vehicle and equipment MANUFACTURERS, not to the carriers operating "
     "the vehicles -- a freight carrier has no NHTSA recall, and running one through would "
     "produce a clean record that means nothing. Carrier-side behaviour is H-FMCSA-01."),

    # ---- federal legal records, for H-LEGAL-01 ----
    ("SRC-0047", "13_legal_dispute_records",
     "CourtListener RECAP federal docket search API", "API", "Yes", "Strong",
     "IC4 involuntary disclosure: a company chooses neither to be sued nor what the "
     "caption says. Free, keyless, 2.1M dockets. MUST be queried party-scoped: the default "
     "`q=` searches the full text of filed DOCUMENTS, so q=\"Kenco Group\" returns 55 "
     "dockets of which the top hit is an unrelated furniture bankruptcy, while "
     "party:\"Kenco Group\" returns 21 that are all genuinely Kenco. `party:` is still "
     "tokenized rather than an exact phrase -- party:\"Prime Inc.\" returns 483 including "
     "Certified Prime Inc and Prime Excavating -- so every returned party string is scored "
     "by the identity guard. Holds FEDERAL dockets only; state court records are taxonomy "
     "13c and a separate instrument."),
    ("SRC-0048", "13_legal_dispute_records",
     "NLRB case search", "WEB", "Yes", "Moderate",
     "IC4. DECLARED AND NOT READ as of 2026-09-01, for lack of an interface rather than a "
     "policy: robots.txt permits the crawl, but /api/v1/cases, the JSON search endpoint "
     "and the advanced-search path all answer 404 with a 230KB HTML body, and "
     "/search/case/<term> returns a 256KB JavaScript application shell with no static "
     "markup to parse. Declared rather than dropped so the dependency and its status are "
     "recorded (the NHTSA/SRC-0046 pattern). Logged for Harness Advisor."),
    # ---- 2026-09-01, session 5 task 3a: splitting H-JOBPOST-01's bundled sources ----
    #
    # SRC-0010 is registered as "Indeed + career pages", which bundles two legs with
    # OPPOSITE access profiles into one id. A blocked leg and an open leg must not share
    # a denominator: coverage against the bundle cannot say whether a miss was a company
    # with no discoverable careers page or a source that refuses us outright.
    #
    # Convention 22 forbids renaming a registered value, so SRC-0010 keeps its id and
    # name and is narrowed IN THE MANIFEST to the Indeed leg; the own-domain leg becomes
    # its own source here.
    #
    # Probed honestly 2026-09-01 rather than assumed, as the brief required, and the
    # answer was worse than "unverified": Indeed disallows '/jobs' and '/viewjob?' as well
    # as the '/cmp/' path already known to refuse us. Every job-posting path on Indeed is
    # closed to this crawler identity, so the entire third-party job-board layer --
    # LinkedIn (SRC-0009) and Indeed both -- is unavailable to compliant collection, and
    # own-domain career pages are not merely the primary leg but the ONLY open one.
    ("SRC-0049", "3_workforce_org_exhaust",
     "Company careers pages (own domain)", "WEB", "Yes", "Moderate-Strong",
     "The open leg split out of SRC-0010 on 2026-09-01. A company's own careers page, "
     "reached from its own domain and cited as the source_url -- never a third-party job "
     "board, and never an ATS internal endpoint as the citation. This is the only "
     "family-3 job-posting source still reachable: LinkedIn (SRC-0009) publishes "
     "Disallow: / and Indeed (SRC-0010) disallows /jobs, /viewjob? and /cmp/ for this "
     "crawler identity, both confirmed by probe. Coverage is bounded by careers-URL "
     "discovery and by ATS adapter support, not by access policy. Read by H-JOBPOST-01."),

]

# (signal_type_id, signal_type_name, signal_class, evidence_family, status,
#  instrument_class)
#
# signal_class='prerequisite' REQUIRES a null evidence_family and 'evidence' REQUIRES a
# non-null one; validate_repo_db.py check 5 enforces both directions.
#
# instrument_class is a DIFFERENT axis from signal_class and the two are never inferred
# from one another (taxonomy patch rev 2 §4.6.3). signal_class = does this yield evidence
# or enable another harness. instrument_class = could this instrument have observed the
# thing at all, which is what governs whether an absence means anything.
NEW_SIGNAL_TYPES = [
    # ---- session 16: the first licensed-absence instrument for cybersecurity ----
    ("ST-BREACHNOTICE", "state_ag_breach_notice", "evidence",
     "9_industrial_safety_environmental", "active", "IC4"),
    ("ST-0008", "executive_public_statement", "evidence",
     "15_executive_candor_actor_networks", "active", "IC2"),
    ("ST-0009", "first_party_announcement", "evidence",
     "1_first_party_strategy_governance", "active", "IC1"),
    ("ST-0010", "employee_review_aggregate", "evidence",
     "4_employee_experience_workarounds", "active", "IC4"),

    # ---- trade press (taxonomy patch rev 2 §7) ----
    # IC2 rather than IC1 despite being first-party speech: the exec volunteers the words,
    # but the reporter picks the topic and the outlet decides whether to publish. The most
    # valuable articulation type currently available -- the crawl weights toward it.
    ("ST-EXECQUOTE-REPORTED", "exec_quote_reported", "evidence",
     "15_executive_candor_actor_networks", "active", "IC2"),
    # A contributed column is written by the subject for publication, so it is IC1: high
    # reliability (attribution is unambiguous) and worst-case bias. §4.6.2's example of
    # why the two axes cannot be collapsed.
    ("ST-EXECCOLUMN", "exec_contributed_column", "evidence",
     "15_executive_candor_actor_networks", "active", "IC1"),
    ("ST-EXECPANEL", "exec_panel_coverage", "evidence",
     "15_executive_candor_actor_networks", "active", "IC2"),
    ("ST-PRESSPROFILE", "trade_press_profile", "evidence",
     "15_executive_candor_actor_networks", "active", "IC2"),
    # Routing class, not a terminal signal type (§8.2). A wire reprint is a press release
    # that reached us through a trade outlet; it is first-party evidence wearing a trade
    # masthead, so it routes to H-FIRSTPARTY-01's family and role and never counts toward
    # trade-press articulation yield. Its family is family 1 for exactly that reason.
    ("ST-WIREREPRINT", "wire_reprint_routed", "evidence",
     "1_first_party_strategy_governance", "routing_only", "IC1"),

    # ---- vendor case studies (taxonomy patch rev 2 §7) ----
    # All IC1: a vendor case study exists to sell the vendor. Presence is evidence of
    # presence discounted for puffery; absence licenses nothing whatsoever.
    ("ST-VENDORQUOTE", "vendor_case_study_buyer_quote", "evidence",
     "6_vendor_partner_disclosure", "active", "IC1"),
    ("ST-VENDORDEPLOY", "vendor_case_study_deployment_fact", "evidence",
     "6_vendor_partner_disclosure", "active", "IC1"),
    ("ST-VENDORFRAMING", "vendor_demand_characterization", "evidence",
     "6_vendor_partner_disclosure", "active", "IC1"),

    # ---- federal recall / adverse-event records (H-PRODUCTQUALITY-01) ----
    # IC4: published over the subject's likely preference, under regulatory compulsion.
    # The class the evidence base is shortest on, and the only remaining route to
    # `legacy_constraint` now that family 4 is closed to compliant collection.
    ("ST-RECALLCAUSE", "product_quality_event", "evidence",
     "11_product_quality_customer_friction", "active", "IC4"),

    # ---- federal court dockets (H-LEGAL-01) ----
    # IC4, and the purest instance of the class in the portfolio: the subject does not
    # choose to be a party and does not write the caption. Note what its ABSENCE licenses,
    # which is narrow -- no federal docket about systems is not "no dispute about systems",
    # because most commercial disputes are resolved in state court or in arbitration and
    # never appear here at all.
    ("ST-DOCKET", "federal_court_docket", "evidence",
     "13_legal_dispute_records", "active", "IC4"),

    # ---- executive LinkedIn posts (H-TRADEPRESS-01 v1.1, taxonomy family 15) ----
    # IC1, and registered separately from ST-EXECQUOTE-REPORTED on purpose. A LinkedIn post
    # is self-published and topic-chosen by the speaker: curated by an interested party,
    # the same class as an announcement. ST-EXECQUOTE-REPORTED is IC2 and scored higher for
    # exactly the reason this is not -- a reporter elicited it and an editor chose to run
    # it. Folding the two together would let the weaker instrument inherit the stronger
    # one's score.
    #
    # Registered even though it currently yields nothing: LinkedIn's robots.txt refuses
    # this crawler identity, so the type exists to name the instrument and record that its
    # silence is an ACCESS fact, not an absence of executive speech. Per taxonomy patch
    # §4.6.1 an IC1 absence licenses no inference at all.
    ("ST-LINKEDINPOST", "linkedin_exec_post", "evidence",
     "15_executive_candor_actor_networks", "active", "IC1"),

    # ---- NLRB unfair-labour-practice and representation cases (H-LEGAL-01 v1.1) ----
    # IC4: a company chooses neither to be charged nor what the charge says. Registered as
    # `evidence` because it IS evidence -- of labour friction -- even though this harness
    # writes no observations from it. The allegation vocabulary is statutory and names
    # conduct under the NLRA, never systems, so it cannot carry a modernization theme;
    # 0 of 10 sampled labels classify. Kept separate from ST-DOCKET so CourtListener and
    # NLRB never share a coverage denominator.
    ("ST-NLRB", "nlrb_case", "evidence",
     "13_legal_dispute_records", "active", "IC4"),

    # ---- 2026-09-01, session 5 task 5: H-JOBPOST-01 v1.1's two new signals ----
    #
    # Both IC3 `revealed_behavior`, and the taxonomy names this instrument as the example
    # of the class: "byproduct of operating, not addressed to an audience. Hard to game.
    # Job postings, building permits, FMCSA, procurement records."
    #
    # taxonomy 5b, and family 5 rather than family 3 deliberately. A requisition naming
    # SAP or a WMS is a technology-stack trace as well as workforce exhaust, and
    # signal_taxonomy.md §5 is explicit that it belongs as a FIELD on this harness --
    # "merge into 3a, don't build new" -- rather than as a separate family-5 harness.
    # Registering it separately is what lets a family-5 claim be counted without implying
    # a family-5 harness exists.
    ("ST-JOBSYSTEM", "job_posting_system_mention", "evidence",
     "5_technology_stack_traces", "active", "IC3"),

    # The closed leg. Registered as `evidence` and IC3 because that is what it WOULD be if
    # it were reachable -- the class describes the instrument, not our access to it -- and
    # registered at all so the refusal has a denominator rather than being a silence.
    # It writes no observations today and is expected to write none: LinkedIn publishes
    # Disallow: / and Indeed disallows /jobs, /viewjob? and /cmp/ for this crawler
    # identity, both confirmed by probe on 2026-09-01.
    #
    # NOT folded into `job_posting` (ST-0002), and that is the whole point: a blocked leg
    # sharing a denominator with an open one makes coverage uninterpretable, because a
    # miss could be either a company with no discoverable careers page or a source that
    # refuses everyone. Distinct from ST-LINKEDINPOST, which is an executive's authored
    # post (IC1, curated, family 15) rather than a job requisition.
    ("ST-JOBBOARD3P", "job_board_third_party", "evidence",
     "3_workforce_org_exhaust", "active", "IC3"),
    # Session 10 item 3: the company describing itself or its intent as reported by a
    # journalist. IC2 like reported quotes -- mediated, but the words are the company's.
    ("ST-PRESSCHAR", "trade_press_characterization", "evidence",
     "15_executive_candor_actor_networks", "active", "IC2"),

    # ---- 2026-09-13, Week 4: H-PROCUREMENT-01 (USASpending) ----
    # Opaque numeric ids, continuing ST-0001..ST-0010: the name column carries the meaning,
    # so the id never has to be renamed when the meaning is refined (convention 22).
    # IC3 per taxonomy §20 ("procurement records" is the class's named example): an award
    # is a byproduct of operating, reported by the government over no preference of the
    # recipient's. Neither type is a THEME instrument -- in these records the company is
    # the SELLER to the government, so the text describes work delivered, not the
    # company's own estate -- and core/composition.py does not list them.
    ("ST-0011", "federal_prime_contract_award", "evidence",
     "7_procurement_contracting", "active", "IC3"),
    ("ST-0012", "federal_assistance_award", "evidence",
     "2_financial_capital_allocation", "active", "IC3"),

    # ---- 2026-09-13, Week 4: H-LOCALRECORDS-01's four sub-scopes ----
    # WARN notices are compelled by statute and published over the employer's preference: IC4.
    # Permits, council matters and served-page markers are byproducts of operating: IC3.
    # None is a theme instrument (core/composition.py is unchanged).
    ("ST-0013", "state_warn_notice", "evidence",
     "3_workforce_org_exhaust", "active", "IC4"),
    ("ST-0014", "municipal_permit_as_contractor", "evidence",
     "8_physical_footprint_capacity", "active", "IC3"),
    ("ST-0015", "council_matter_title_mention", "evidence",
     "16_local_community_records", "active", "IC3"),
    ("ST-0016", "website_technology_fingerprint", "evidence",
     "5_technology_stack_traces", "active", "IC3"),

    # ---- 2026-09-13, session 17 wrap-up: H-SEC8K-01 ----
    # Form 8-K Item 1.05 is compelled by rule and filed over the company's preference: IC4.
    # Filed under family 1 with SEC EDGAR (SRC-0004); the taxonomy has no cyber family, the
    # same note H-BREACHPORTAL-01 carries. A cybersecurity theme instrument in
    # core/composition.py, scoped to current SEC reporters.
    ("ST-0017", "sec_8k_item_105_cybersecurity", "evidence",
     "1_first_party_strategy_governance", "active", "IC4"),
]


def _existing(ws, col: int) -> set:
    return {str(ws.cell(r, col).value).strip()
            for r in range(2, ws.max_row + 1)
            if ws.cell(r, col).value not in (None, "")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    path = Path(args.db)
    wb = openpyxl.load_workbook(path)
    actions: list[str] = []

    sf = wb["Source_Families"]
    have = _existing(sf, 1)
    for row in NEW_SOURCES:
        if row[0] in have:
            print(f"  skip  {row[0]} already registered")
            continue
        sf.append(list(row))
        actions.append(f"Source_Families += {row[0]} ({row[2]})")

    st = wb["Signal_Types"]
    have_ids = _existing(st, 1)
    have_names = _existing(st, 2)
    # Written by header name, not by tuple position: instrument_class was appended to this
    # sheet after the first three rows below were authored, and a positional append would
    # have silently written the class into whatever column happened to be sixth.
    st_headers = [st.cell(1, c).value for c in range(1, st.max_column + 1)]
    st_fields = ["signal_type_id", "signal_type_name", "signal_class", "evidence_family",
                 "status", "instrument_class"]
    missing_cols = [f for f in st_fields if f not in st_headers]
    if missing_cols:
        raise SystemExit(f"ABORT: Signal_Types is missing column(s) {missing_cols}; "
                         f"run scripts/migrate_schema.py --apply first")
    for row in NEW_SIGNAL_TYPES:
        if row[0] in have_ids or row[1] in have_names:
            print(f"  skip  {row[1]} already registered")
            continue
        values = dict(zip(st_fields, row))
        st.append([values.get(h) for h in st_headers])
        actions.append(f"Signal_Types += {row[0]} ({row[1]}, {row[2]}, {values['instrument_class']})")

    for a in actions:
        print(f"  add   {a}")
    if not actions:
        print("  nothing to do")
        return 0

    if not args.apply:
        print("\n  DRY RUN -- re-run with --apply to write.")
        return 0

    backup, pruned = backup_workbook(path)
    wb.save(path)
    print(f"\n  saved {path.name} (backup {backup.name})")
    if pruned:
        print(f"  pruned {len(pruned)} older backup(s): {', '.join(p.name for p in pruned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
