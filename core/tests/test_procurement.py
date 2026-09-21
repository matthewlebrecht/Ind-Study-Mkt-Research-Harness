#!/usr/bin/env python3
"""
H-PROCUREMENT-01 identity rule, tested against the requirement rather than the code.

Every case is either a recipient USASpending actually returned for a buyer's name on
2026-09-13 (the calibration that shaped the rule) or a documented convention-31 incident
restated against this source. The matrix is the point (convention 40): for each hazard,
both the entity that must be accepted and the look-alike that must be refused.

    python core/tests/test_procurement.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_procurement_01.harness import (  # noqa: E402
    distinctive, name_matches, norm_tokens, search_terms, window)

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def accepts(company, recipient):
    return name_matches(company, recipient)[0]


def main() -> int:
    print("1. the real entity is accepted")
    check("Whiting-Turner <- WHITING-TURNER CONTRACTING COMPANY, THE",
          accepts("Whiting-Turner Contracting", "WHITING-TURNER CONTRACTING COMPANY, THE"))
    check("Midmark <- MIDMARK CORPORATION", accepts("Midmark Corporation", "MIDMARK CORPORATION"))
    check("Swinerton <- SWINERTON BUILDERS (line-of-business word)",
          accepts("Swinerton", "SWINERTON BUILDERS"))
    check("Swinerton <- SWINERTON INCORPORATED", accepts("Swinerton", "SWINERTON INCORPORATED"))
    check("JE Dunn <- J E DUNN CONSTRUCTION COMPANY (initials collapse)",
          accepts("JE Dunn Construction", "J E DUNN CONSTRUCTION COMPANY"))
    check("C.R. England <- C R ENGLAND INC", accepts("C.R. England", "C R ENGLAND INC"))
    check("The Walsh Group <- WALSH CONSTRUCTION COMPANY",
          accepts("The Walsh Group", "WALSH CONSTRUCTION COMPANY"))
    check("PLS Logistics <- PITTSBURGH LOGISTICS SYSTEMS INC DBA PLS LOGISTICS SERVICES (dba split)",
          accepts("PLS Logistics", "PITTSBURGH LOGISTICS SYSTEMS INC DBA PLS LOGISTICS SERVICES"))
    check("Prime Inc. <- PRIME INC (common word, exact full name)", accepts("Prime Inc.", "PRIME INC"))
    check("Duke Manufacturing Co. <- DUKE MANUFACTURING CO.", accepts("Duke Manufacturing Co.", "DUKE MANUFACTURING CO."))

    print("2. the look-alike is refused")
    check("Kenco Group x KENCOA AEROSPACE CORPORATION (prefix is not a token)",
          not accepts("Kenco Group", "KENCOA AEROSPACE CORPORATION"))
    check("Kenco Group x KENCO HYDRAULICS, INC.", not accepts("Kenco Group", "KENCO HYDRAULICS, INC."))
    check("Mack Group x COMMACK GROUP CORP (substring search result)",
          not accepts("Mack Group", "COMMACK GROUP CORP"))
    check("Mack Group x THE MCCORMACK GROUP", not accepts("Mack Group", "THE MCCORMACK GROUP"))
    check("Prime Inc. x PRIME COMMUNICATIONS, INC. (convention 31)",
          not accepts("Prime Inc.", "PRIME COMMUNICATIONS, INC."))
    check("Prime Inc. x FLEET PRIME INC. K-1 TRUCK SERVICE",
          not accepts("Prime Inc.", "FLEET PRIME INC. K-1 TRUCK SERVICE"))
    check("Prime Inc. x PRIME TRUCKING (a weak word does not rescue a common-word name)",
          not accepts("Prime Inc.", "PRIME TRUCKING"))
    check("C.R. England x ENGLAND LOGISTICS (initials are required)",
          not accepts("C.R. England", "ENGLAND LOGISTICS"))
    check("Duke Manufacturing x DUKE ENERGY CAROLINAS", not accepts("Duke Manufacturing Co.", "DUKE ENERGY CAROLINAS"))
    check("Whiting-Turner x WHITING-TURNER WALSH JV (a JV is another entity)",
          not accepts("Whiting-Turner Contracting", "WHITING-TURNER WALSH JV"))
    check("Swinerton x SWINERTON ABSHER JV", not accepts("Swinerton", "SWINERTON ABSHER JV"))
    check("Clark Construction Group x CLARK CONSTRUCTION GROUP - CALIFORNIA, LP (regional entity, not counted)",
          not accepts("Clark Construction Group", "CLARK CONSTRUCTION GROUP - CALIFORNIA, LP"))
    check("Power Construction x POWER CONSTRUCTION SERVICES LLC? common word needs the exact name",
          not accepts("Power Construction", "POWER ELECTRIC CONSTRUCTION"))
    # 2026-09-13 dry run: accepted for The Walsh Group, in-state, one award (a loan). The
    # suite above was green over it -- convention 40 -- so the practice forms get a matrix.
    check("The Walsh Group x WALSH & COMPANY, P. C. (professional corporation)",
          not accepts("The Walsh Group", "WALSH & COMPANY, P. C."))
    check("Midmark x MIDMARK LAW GROUP PLLC", not accepts("Midmark Corporation", "MIDMARK LAW GROUP PLLC"))
    check("Clark Construction Group x CLARK & ASSOCIATES CPAS", not accepts("Clark Construction Group", "CLARK CPAS"))
    check("Kenco Group x KENCO, P.A.", not accepts("Kenco Group", "KENCO, P.A."))
    check("The Walsh Group <- WALSH CONSTRUCTION COMPANY still accepted after the practice-form rule",
          accepts("The Walsh Group", "WALSH CONSTRUCTION COMPANY"))
    check("Kenco Group <- KENCO, INC. still accepted (INC is not a practice form)", accepts("Kenco Group", "KENCO, INC."))
    check("a practice-form refusal says so", name_matches("The Walsh Group", "WALSH & COMPANY, P. C.")[1].startswith("professional_practice"))
    check("the refusal reason distinguishes a near-miss from nothing in common",
          name_matches("Kenco Group", "KENCO HYDRAULICS, INC.")[1].startswith("near_miss")
          and name_matches("Kenco Group", "ACME LLC")[1].startswith("no distinctive"))

    # 2026-09-13 full dry run: one shared token counted as a near-miss and blocked clean
    # absences. A near-miss must be plausibly the company under a longer legal name.
    def near(company, recipient):
        return name_matches(company, recipient)[1].startswith("near_miss")
    check("near-miss: KENCO HYDRAULICS, INC. for Kenco Group", near("Kenco Group", "KENCO HYDRAULICS, INC."))
    check("near-miss: WALSH FEDERAL LLC for The Walsh Group", near("The Walsh Group", "WALSH FEDERAL LLC"))
    check("near-miss: F.H. PASCHEN, S.N. NIELSEN & ASSOCIATES LLC for F.H. Paschen",
          near("F.H. Paschen", "F.H. PASCHEN, S.N. NIELSEN & ASSOCIATES LLC"))
    check("not a near-miss: COLLIN MCSHANE (a person) for The McShane Companies",
          not near("The McShane Companies", "COLLIN MCSHANE"))
    check("not a near-miss: CATERING CAJUN LLC for Cajun Industries (token must lead)",
          not near("Cajun Industries Holdings LLC", "CATERING CAJUN LLC"))
    check("not a near-miss: NICHOLAS PETERSON for Nicholas and Company (a given name is not an identity)",
          not near("Nicholas and Company", "NICHOLAS PETERSON"))
    check("near-miss: W. W. CLYDE & CO. for Clyde Companies (leading initials skipped; a subsidiary, not an absence)",
          near("Clyde Companies", "W. W. CLYDE & CO."))
    check("but not accepted: W. W. CLYDE & CO. needs a human alias, not a guess",
          not accepts("Clyde Companies", "W. W. CLYDE & CO."))
    check("not a near-miss: CRETE AREA MEDICAL CENTER for Crete Carrier (an institution named for a town)",
          not near("Crete Carrier Corporation", "CRETE AREA MEDICAL CENTER"))
    check("not a near-miss: CITY OF CRETE for Crete Carrier", not near("Crete Carrier Corporation", "CITY OF CRETE"))
    check("still accepted: CAJUN INDUSTRIES LLC for Cajun Industries Holdings LLC",
          accepts("Cajun Industries Holdings LLC", "CAJUN INDUSTRIES LLC"))
    check("still accepted: NICHOLAS & COMPANY INC for Nicholas and Company (exact name)",
          accepts("Nicholas and Company", "NICHOLAS & COMPANY INC"))

    # 2026-09-13 full dry run, row-by-row read: a one-token surname company must be backed by
    # its own line-of-business word when it has one.
    check("Anderson Trucking Service (ATS) x ANDERSON HOLDINGS LLC (wrong entity in the dry run)",
          not accepts("Anderson Trucking Service (ATS)", "ANDERSON HOLDINGS LLC"))
    check("Anderson Trucking Service (ATS) x ANDERSON & ANDERSON, INC",
          not accepts("Anderson Trucking Service (ATS)", "ANDERSON & ANDERSON, INC"))
    check("Anderson Trucking Service (ATS) <- ANDERSON TRUCKING SERVICE INC",
          accepts("Anderson Trucking Service (ATS)", "ANDERSON TRUCKING SERVICE INC"))
    check("Penske Logistics x PENSKE TRUCK LEASING CO", not accepts("Penske Logistics", "PENSKE TRUCK LEASING CO"))
    check("Clark Construction Group <- CLARK CONSTRUCTION LLC (carries its line-of-business word)",
          accepts("Clark Construction Group", "CLARK CONSTRUCTION LLC"))
    check("The Walsh Group <- WALSH CONSTRUCTION COMPANY (no line-of-business word in the company name)",
          accepts("The Walsh Group", "WALSH CONSTRUCTION COMPANY"))
    check("Gilbane <- GILBANE BUILDING COMPANY (BUILDING is a line of business)",
          accepts("Gilbane", "GILBANE BUILDING COMPANY"))
    check("McCarthy Holdings <- MCCARTHY BUILDING COMPANIES, INC.",
          accepts("McCarthy Holdings", "MCCARTHY BUILDING COMPANIES, INC."))
    check("IPS-Integrated Project Services never searches PROJECT",
          "PROJECT" not in [t.upper() for t in search_terms(
              {"company_id": "A025", "canonical_name": "IPS-Integrated Project Services LLC"}, {})])

    print("3. helpers")
    check("norm_tokens collapses initials and drops legal words",
          norm_tokens("W.E. O'Neil Construction Co.") == ["WE", "ONEIL", "CONSTRUCTION"])
    check("parenthetical initialisms are not required tokens",
          distinctive("Engineered Structures Inc. (ESI)") == ["ENGINEERED", "STRUCTURES"])
    check("search terms add the coined core name ('Kenco Group' -> 'Kenco')",
          "KENCO" in [t.upper() for t in search_terms({"company_id": "C0006", "canonical_name": "Kenco Group"}, {})])
    check("search terms never add a bare common word ('Prime Inc.' does not search 'PRIME')",
          "PRIME" not in [t.upper() for t in search_terms({"company_id": "A054", "canonical_name": "Prime Inc."}, {})])
    check("search terms never add a short initialism ('PLS Logistics' does not search 'PLS')",
          "PLS" not in [t.upper() for t in search_terms({"company_id": "C0007", "canonical_name": "PLS Logistics"}, {})])
    # 2026-09-13: USASpending finds "Simplot" and not "J.R. Simplot" / "JR Simplot". A name
    # with initials or punctuation must search its rarest token or its absence is false.
    def terms(cid, name):
        return [t.upper() for t in search_terms({"company_id": cid, "canonical_name": name}, {})]
    check("J.R. Simplot Company searches SIMPLOT (initials break the source's text search)",
          "SIMPLOT" in terms("A041", "J.R. Simplot Company"))
    check("Rogers-O'Brien Construction searches ROGERS (punctuation)",
          "ROGERS" in terms("A097", "Rogers-O'Brien Construction"))
    check("Hathaway Dinwiddie (no initials, no punctuation) gets no single-token term",
          "DINWIDDIE" not in terms("A079", "Hathaway Dinwiddie Construction Company"))
    check("the rare-token term is never a line-of-business word ('Pacific Steel & Recycling' -> not RECYCLING? only distinctive, non-weak)",
          all(t not in ("CONSTRUCTION", "LOGISTICS") for t in terms("A028", "Pacific Steel & Recycling")))
    check("window is five years to the retrieval date", window("2026-09-13") == ("2021-09-13", "2026-09-13"))
    check("window survives 29 February", window("2028-02-29") == ("2023-02-28", "2028-02-29"))

    print("4. counting under a SAM parent UEI (source calls replaced by a fixture)")
    # 2026-09-13 full dry run: Lynden Inc's parent UEI lists its subsidiaries' awards, and its
    # child Lynden Logistics was also accepted, so summing per-UEI counts read 134 for 132
    # contracts while the total described 2 of them. Requirement: count each award once,
    # and name every subsidiary whose awards are counted.
    import harnesses.h_procurement_01.harness as HP

    def award(aid, name, uei, amount):
        return {"generated_internal_id": aid, "Award ID": aid, "Recipient Name": name,
                "Recipient UEI": uei, "Award Amount": amount, "Start Date": "2024-01-01",
                "Awarding Agency": "Department of Defense", "NAICS": {"code": "488510"},
                "Description": "freight", "_group": "contracts"}
    # A4: a joint venture registered under the parent (Clark's ATKINSON/CLARK, A JOINT VENTURE in
    # the fourth full dry run) must not re-enter through the family path.
    parent = [award("A1", "LYNDEN AIR CARGO, LLC", "CHILD1", 100.0),
              award("A2", "ALASKA MARINE LINES INC", "CHILD2", 200.0),
              award("A3", "LYNDEN LOGISTICS, INC.", "LOGUEI", 50.0),
              award("A4", "ATKINSON/LYNDEN, A JOINT VENTURE", "JVUEI", 9000.0)]
    fixture_lists = {"PARENTUEI": parent, "LOGUEI": [parent[2]]}
    fixture_counts = {"PARENTUEI": {"contracts": 4}, "LOGUEI": {"contracts": 1}}
    saved = (HP.awards_by_text, HP.counts_for_uei)
    HP.awards_by_text = lambda cache, text, group, tp: (
        [dict(a) for a in fixture_lists.get(text, [])] if group == "contracts" else [], False)
    HP.counts_for_uei = lambda cache, u, tp: fixture_counts[u]
    try:
        company = {"company_id": "A094", "canonical_name": "Lynden, Inc.", "_state": "WA"}
        acc = [({"key": "PARENTUEI", "name": "LYNDEN INC", "uei": "PARENTUEI", "states": ["WA"],
                 "awards_seen": 0, "reason": "ok"}, {"recipient_id": "p-P", "awards": {}}),
               ({"key": "LOGUEI", "name": "LYNDEN LOGISTICS, INC.", "uei": "LOGUEI", "states": ["WA"],
                 "awards_seen": 1, "reason": "ok"}, {"recipient_id": "l-C", "awards": {}})]
        res = {"accepted": acc, "refused": [], "near_same_state": [], "capped": []}
        rows, log = HP.build_rows(company, res, None, [{"start_date": "2021-09-13", "end_date": "2026-09-13"}],
                                  "2026-09-13")
        obs = rows.get(HP.SIG_CONTRACT)
        check("a parent UEI and its accepted child count each award once (3, not 4)",
              log["counts"].get("contracts") == 3 and obs is not None and "held 3 federal prime" in obs.observation_text)
        check("the combined value covers every counted award ($350)", obs is not None and "$350" in obs.observation_text)
        check("a joint venture registered under the parent is excluded and the row says so",
              obs is not None and "ATKINSON/LYNDEN, A JOINT VENTURE (1)" in obs.observation_text
              and "were not counted" in obs.observation_text and "$9,350" not in obs.observation_text)
        check("subsidiaries counted under the parent are named in the row",
              obs is not None and "LYNDEN AIR CARGO, LLC (1)" in obs.observation_text
              and "ALASKA MARINE LINES INC (1)" in obs.observation_text)
    finally:
        HP.awards_by_text, HP.counts_for_uei = saved

    print("5. v1.1 identity from source records (aliases, SAM parent links, anchors)")
    import copy
    saved2 = (HP.awards_by_text, HP.parent_names, HP.recipient_search, HP.recipient_profile, HP.counts_for_uei)

    def group_award(name, uei, state, aid):
        return {"Recipient Name": name, "Recipient UEI": uei, "recipient_id": (uei or aid) + "-C",
                "Recipient Location": {"state_code": state}, "generated_internal_id": aid, "_group": "contracts"}
    fixtures = {}
    HP.awards_by_text = lambda cache, text, group, tp: ([dict(a) for a in fixtures.get("awards", [])] if group == "contracts" else [], False)
    HP.parent_names = lambda cache, rid: fixtures.get("parents", {}).get(rid, [])
    HP.recipient_search = lambda cache, text: fixtures.get("recipients", [])
    HP.recipient_profile = lambda cache, rid: fixtures.get("profiles", {}).get(rid, {})
    HP.counts_for_uei = lambda cache, u, tp: fixtures.get("counts", {}).get(u, {})
    tp = [{"start_date": "2021-09-14", "end_date": "2026-09-14"}]
    try:
        # the brief's W. W. Clyde check: punctuation and spacing do not change the tokens
        check("W. W. Clyde: 'W. W. CLYDE & CO.' and 'W.W. CLYDE & CO.' tokenize identically (not a punctuation mismatch)",
              norm_tokens("W. W. CLYDE & CO.") == norm_tokens("W.W. CLYDE & CO.") == norm_tokens("WW CLYDE & CO") == ["WW", "CLYDE"])

        mort = {"company_id": "A039", "canonical_name": "Mortenson", "_state": "MN"}
        reg = {"A039": {"name_variants": ["M. A. MORTENSON COMPANIES, INC.", "M. A. MORTENSON COMPANY"]}}
        fixtures.clear(); fixtures["awards"] = [group_award("M. A. MORTENSON COMPANY", "GPXRWUEUHZ19", "MN", "a1")]
        res = HP.resolve_company(None, mort, reg, tp)
        check("an exact source-record alias form is accepted (M. A. MORTENSON COMPANY for Mortenson)",
              [r["name"] for r, _ in res["accepted"]] == ["M. A. MORTENSON COMPANY"])
        res = HP.resolve_company(None, mort, {}, tp)
        check("without the alias the same recipient is not accepted", not res["accepted"])
        fixtures["awards"] = [group_award("M. A. MORTENSON COMPANY", "L7URHPGSBLZ3", "VA", "a2")]
        check("an alias match still has to pass the HQ-state gate (the McLean, VA child is not counted)",
              not HP.resolve_company(None, mort, reg, tp)["accepted"])

        walb = {"company_id": "A042", "canonical_name": "Walbridge", "_state": "MI"}
        fixtures.clear()
        fixtures["awards"] = [group_award("WALBRIDGE ALDINGER LLC", "NJLSMBP6AJM7", "MI", "w1")]
        fixtures["parents"] = {"NJLSMBP6AJM7-C": ["THE WALBRIDGE GROUP, INC."]}
        check("a same-state near-miss whose SAM parent passes identity is accepted (Walbridge Aldinger -> The Walbridge Group)",
              [r["name"] for r, _ in HP.resolve_company(None, walb, {}, tp)["accepted"]] == ["WALBRIDGE ALDINGER LLC"])
        fixtures["parents"] = {"NJLSMBP6AJM7-C": ["WALBRIDGE ALDINGER LLC"]}
        check("a near-miss that is its own parent is NOT accepted", not HP.resolve_company(None, walb, {}, tp)["accepted"])

        swin = {"company_id": "A046", "canonical_name": "Swinerton", "_state": "CA"}
        fixtures.clear()
        fixtures["awards"] = [group_award("SWINERTON ABSHER JV", "GH1KEBS4H9P9", "CA", "j1")]
        fixtures["parents"] = {"GH1KEBS4H9P9-C": ["SWINERTON INCORPORATED"]}
        check("a joint venture is never rescued by a parent link", not HP.resolve_company(None, swin, {}, tp)["accepted"])

        layton = {"company_id": "A061", "canonical_name": "Layton Construction", "_state": "UT"}
        fixtures.clear()
        fixtures["awards"] = [group_award("LAYTON AUTOBODY, INC.", None, "UT", "l1"),
                              group_award("LAYTON PARTNERS, LLC", None, "UT", "l2")]
        for a in fixtures["awards"]:
            a["Recipient UEI"] = None
        fixtures["recipients"] = [{"name": "LAYTON CONSTRUCTION COMPANY, LLC", "uei": "J8CFPMLEZVN4", "id": "lc-C"}]
        fixtures["profiles"] = {"lc-C": {"state": "UT", "parent_name": "THE LAYTON COMPANIES INC"}}
        fixtures["counts"] = {"J8CFPMLEZVN4": {"contracts": 0, "idvs": 0}}
        res = HP.resolve_company(None, layton, {}, tp)
        check("anchor with no awards clears name-only (no UEI) near-misses",
              not res["near_same_state"] and len(res["cleared"]) == 2 and res["anchors"][0]["uei"] == "J8CFPMLEZVN4")
        fixtures["awards"].append(group_award("LAYTON HOMES INC", "XYZ123", "UT", "l3"))
        res = HP.resolve_company(None, layton, {}, tp)
        check("a near-miss that carries a UEI keeps blocking even with an empty anchor",
              [r["name"] for r in res["near_same_state"]] == ["LAYTON HOMES INC"])
        fixtures["counts"] = {"J8CFPMLEZVN4": {"contracts": 3}}
        res = HP.resolve_company(None, layton, {}, tp)
        check("an anchor that holds awards clears nothing", not res["cleared"] and len(res["near_same_state"]) == 3)

        fixtures.clear()
        fixtures["awards"] = [group_award("KENCO HYDRAULICS, INC.", "KH1", "TN", "k1")]
        kenco = {"company_id": "C0006", "canonical_name": "Kenco Group", "_state": "TN"}
        res = HP.resolve_company(None, kenco, {"C0006": {"name_variants": [], "not_variants": ["KENCO HYDRAULICS, INC."]}}, tp)
        check("a not_variants entry refuses the near-miss as a confirmed different entity",
              not res["near_same_state"] and res["refused"][0]["reason"].startswith("confirmed_different_entity"))
        # v1.2: no registered entity at all counts as an absence (Matthew, 2026-09-14)
        graham = {"company_id": "A026", "canonical_name": "Graham Construction", "_state": "NE"}
        fixtures.clear()
        fixtures["awards"] = [group_award("J.W. GRAHAM", None, "NE", "g1")]
        fixtures["awards"][0]["Recipient UEI"] = None
        fixtures["recipients"] = []
        res = HP.resolve_company(None, graham, {}, tp)
        check("v1.2: no registered entity in any state clears a name-only near-miss",
              not res["near_same_state"] and len(res["cleared"]) == 1 and "no registered" in res["cleared"][0]["reason"])
        fixtures["recipients"] = [{"name": "GRAHAM CONSTRUCTION SERVICES, INC.", "uei": "OUT1", "id": "go-C"}]
        fixtures["profiles"] = {"go-C": {"state": "MN", "parent_name": "GRAHAM GROUP LTD"}}
        fixtures["counts"] = {"OUT1": {"contracts": 0}}
        res = HP.resolve_company(None, graham, {}, tp)
        check("v1.2: an entity registered only outside the HQ state with no award still clears (Graham)",
              not res["near_same_state"] and len(res["cleared"]) == 1 and res["registered_elsewhere"][0]["uei"] == "OUT1")
        fixtures["counts"] = {"OUT1": {"contracts": 1, "idvs": 1}}
        res = HP.resolve_company(None, graham, {}, tp)
        check("v1.2: an entity registered outside the HQ state that HOLDS awards clears nothing (Herzog)",
              len(res["near_same_state"]) == 1 and not res["cleared"])
        fixtures["counts"] = {}
        fixtures["recipients"] = []
        fixtures["awards"].append(group_award("GRAHAM QUALITY CONTRACTING INC", "GQ1", "NE", "g2"))
        res = HP.resolve_company(None, graham, {}, tp)
        check("v1.2: with no registered entity, a UEI-bearing near-miss still blocks",
              [r["name"] for r in res["near_same_state"]] == ["GRAHAM QUALITY CONTRACTING INC"])
        # v1.3: not_variants are excluded from the registered-entity search too (Herzog, 2026-09-15)
        herzog = {"company_id": "A092", "canonical_name": "Herzog Enterprises", "_state": "MO"}
        fixtures.clear()
        fixtures["awards"] = [group_award("HERZOG MOTOR SPORTS", None, "MO", "h1")]
        fixtures["awards"][0]["Recipient UEI"] = None
        fixtures["recipients"] = [{"name": "HERZOG GROUP INC.", "uei": "RC7", "id": "hg-C"}]
        fixtures["profiles"] = {"hg-C": {"state": "CA", "parent_name": "HERZOG GROUP INC."}}
        fixtures["counts"] = {"RC7": {"contracts": 1, "idvs": 1}}
        res = HP.resolve_company(None, herzog, {}, tp)
        check("v1.3: without a ruling, an out-of-state registered entity holding awards still blocks",
              len(res["near_same_state"]) == 1 and not res["cleared"])
        res = HP.resolve_company(None, herzog, {"A092": {"name_variants": [], "not_variants": ["HERZOG GROUP INC."]}}, tp)
        check("v1.3: once it is a confirmed different firm it is not a registered entity, and the absence clears",
              not res["near_same_state"] and len(res["cleared"]) == 1 and not res["registered_elsewhere"])
        fixtures["counts"] = {}
    finally:
        HP.awards_by_text, HP.parent_names, HP.recipient_search, HP.recipient_profile, HP.counts_for_uei = saved2

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
