#!/usr/bin/env python3
"""
H-LOCALRECORDS-01 v1.0, tested against the requirement.

Every name string below is one the sources returned on 2026-09-13 while the harness was being
scoped; every date string is one the Utah list actually carries. The matrix is the point
(convention 40): for each record-specific addition to a name, the real entity is accepted and
the look-alike is still refused.

    python core/tests/test_localrecords.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_localrecords_01 import harness as L  # noqa: E402
from harnesses.h_procurement_01.harness import name_matches  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def ok(company, raw, **kw):
    return name_matches(company, L.clean_candidate(raw, **kw))[0]


def main() -> int:
    print("1. contractor strings as the permit portals write them")
    check("'Joeris General Contractors***MAIN***' is Joeris", ok("Joeris General Contractors", "Joeris General Contractors***MAIN***"))
    check("'Bartlett Cocke General Contractors (MAIN)' is Bartlett Cocke", ok("Bartlett Cocke General Contractors", "Bartlett Cocke General Contractors (MAIN)"))
    check("'LEASE CRUTCHER LEWIS WA LLC' is Lease Crutcher Lewis (a state code is not another entity)",
          ok("Lease Crutcher Lewis", "LEASE CRUTCHER LEWIS WA LLC"))
    check("'SWINERTON BUILDERS NW' is Swinerton (a directional)", ok("Swinerton", "SWINERTON BUILDERS NW"))
    check("'BNBUILDERS INC' is BNBuilders", ok("BNBuilders", "BNBUILDERS INC"))
    check("'LYDA SWINERTON BUILDERS, INC.' is still refused for Swinerton", not ok("Swinerton", "LYDA SWINERTON BUILDERS, INC."))
    check("'S W HATHAWAY INC' is still refused for Hathaway Dinwiddie", not ok("Hathaway Dinwiddie Construction Company", "S W HATHAWAY INC"))
    check("'BNBuilders Dan Morency' (a person appended) is refused, not guessed", not ok("BNBuilders", "BNBuilders Dan Morency"))
    check("'PAUL & MARY MCSHANE' (owners who share a surname) is refused for The McShane Companies",
          not ok("The McShane Companies", "PAUL & MARY MCSHANE"))
    check("a state code is dropped only after the name has begun ('WA' alone is not stripped to nothing)",
          L.clean_candidate("WA") == "WA")

    print("2. WARN site names")
    check("'FedEx Corporation Facility (Ft. Worth)' is FedEx Corporation with facility words and the parenthetical removed",
          name_matches("FedEx Corporation", L.clean_candidate("FedEx Corporation Facility (Ft. Worth)", facility=True))[0])
    check("a site name carrying the site's city is matched once the city is dropped",
          name_matches("Estes Express Lines", L.clean_candidate("Estes Express Lines Dallas", facility=True, drop={"DALLAS"}))[0])
    check("facility words are not dropped from permit contractor strings (facility=False by default)",
          "Facility" in L.clean_candidate("Clark Facility Solutions LLC"))
    notices = [{"state": "TX", "date": dt.date(2025, 1, 2), "name": "Estes Express Lines Terminal", "city": "Dallas", "count": 60, "url": "u"},
               {"state": "TX", "date": dt.date(2025, 1, 3), "name": "Estes Park Resort", "city": "Austin", "count": 55, "url": "u"}]
    acc, ref = L.match_warn({"company_id": "A045", "canonical_name": "Estes Express Lines"}, notices)
    check("match_warn accepts the terminal and refuses the namesake resort",
          [n["name"] for n in acc] == ["Estes Express Lines Terminal"] and [n["name"] for n in ref] == ["Estes Park Resort"])

    print("3. dates as the Utah list writes them")
    check("'10/30/26' -> 2026-10-30", L.parse_date("10/30/26") == dt.date(2026, 10, 30))
    check("'01/07//09' (a doubled slash in the source) -> 2009-01-07", L.parse_date("01/07//09") == dt.date(2009, 1, 7))
    check("an ISO timestamp from Socrata parses", L.parse_date("2024-10-05T00:00:00.000") == dt.date(2024, 10, 5))
    check("garbage is None, never a guessed date", L.parse_date("n/a") is None and L.parse_date("13/45/26") is None)

    print("4. search tokens")
    check("F.H. Paschen searches PASCHEN", L.search_token("F.H. Paschen") == "PASCHEN")
    check("a common-word name searches its full phrase (Power Construction)", L.search_token("Power Construction") == "POWER CONSTRUCTION")
    check("a short initialism name searches its full name (R+L Carriers)", L.search_token("R+L Carriers") == "R+L CARRIERS")

    print("5. technology markers are specific, never bare words")
    check("'/wp-content/' is WordPress", "WordPress" in L.fingerprint('<link href="/wp-content/themes/x.css">'))
    check("prose saying 'we love WordPress' is not a WordPress fingerprint", "WordPress" not in L.fingerprint("<p>we love WordPress and HubSpot</p>"))
    check("prose saying 'Sitecore' is not a Sitecore fingerprint", "Sitecore" not in L.fingerprint("<p>our Sitecore partner</p>"))
    check("the HubSpot script host is HubSpot", "HubSpot" in L.fingerprint('<script src="//js.hs-scripts.com/123.js"></script>'))
    check("GA4 needs the gtag G- id, not any googletagmanager URL",
          "Google Analytics 4" not in L.fingerprint('<script src="https://www.googletagmanager.com/gtm.js?id=GTM-X">')
          and "Google Tag Manager" in L.fingerprint('<script src="https://www.googletagmanager.com/gtm.js?id=GTM-X">'))

    print("6. one-distinctive-token names need an exact operating-name form (full dry run, 2026-09-13)")
    L.VERIFIED.clear()
    L.VERIFIED.update({"A034": ["WALSH CONSTRUCTION COMPANY", "WALSH CONSTRUCTION GROUP LLC"],
                       "A032": ["GILBANE BUILDING COMPANY"], "A038": ["MCCARTHY BUILDING COMPANIES, INC."],
                       "A046": ["SWINERTON BUILDERS"]})
    walsh = {"company_id": "A034", "canonical_name": "The Walsh Group"}
    mort = {"company_id": "A039", "canonical_name": "Mortenson"}
    yates = {"company_id": "A044", "canonical_name": "The Yates Companies"}
    mcc = {"company_id": "A038", "canonical_name": "McCarthy Holdings"}

    def idok(company, raw):
        return L.identity_ok(company, L.clean_candidate(raw))[0]
    check("bare 'WALSH' (a web-portal applicant) is refused for The Walsh Group", not idok(walsh, "WALSH"))
    check("'WALSH SERVICES INCORPORATED' (a Crestwood plumber, also in Illinois) is refused", not idok(walsh, "WALSH SERVICES INCORPORATED"))
    check("'WALSH BROTHERS CONSTRUCTION INC' is refused", not idok(walsh, "WALSH BROTHERS CONSTRUCTION INC"))
    check("'WALSH CONSTRUCTION COMPANY II, LLC' is accepted (SAM-verified form, numeral dropped)", idok(walsh, "WALSH CONSTRUCTION COMPANY II, LLC"))
    check("'THE WALSH GROUP' is accepted (canonical form)", idok(walsh, "THE WALSH GROUP"))
    check("'MORTENSON CONSTRUCTION' (a Wilmette masonry firm) is refused for Mortenson", not idok(mort, "MORTENSON CONSTRUCTION"))
    check("'Yates Construction Inc.' (Elgin, Texas) is refused for The Yates Companies", not idok(yates, "Yates Construction Inc."))
    check("'MCCARTHY CONSTRUCTION CO' is refused for McCarthy Holdings", not idok(mcc, "MCCARTHY CONSTRUCTION CO"))
    check("'McCarthy Building Companies' is accepted (SAM-verified)", idok(mcc, "McCarthy Building Companies"))
    check("'GILBANE BUILDING COMPANY, INC.' is accepted (SAM-verified)", idok({"company_id": "A032", "canonical_name": "Gilbane"}, "GILBANE BUILDING COMPANY, INC."))
    check("'THE BOLDT COMPANY' is accepted (canonical)", idok({"company_id": "A075", "canonical_name": "The Boldt Company"}, "THE BOLDT COMPANY"))
    check("'CLAYCO INC.' is accepted (canonical, legal form dropped)", idok({"company_id": "A035", "canonical_name": "Clayco"}, "CLAYCO INC."))
    check("'Scentsy, Inc.' is accepted on a WARN list", idok({"company_id": "A018", "canonical_name": "Scentsy, Inc."}, "Scentsy, Inc."))
    check("a two-distinctive-token company is not held to exact forms (Joeris General Contractors***MAIN***)",
          idok({"company_id": "A093", "canonical_name": "Joeris General Contractors"}, "Joeris General Contractors***MAIN***"))
    layton = {"company_id": "A061", "canonical_name": "Layton Construction"}
    check("'Layton Construction Company, LLC dba Layton Builders of Texas, LLC' is accepted (a dba clause is split)",
          idok(layton, "Layton Construction Company, LLC dba Layton Builders of Texas, LLC"))
    check("a dba clause that matches no operating form is still refused ('Layton Masonry dba Layton Stone')",
          not idok(layton, "Layton Masonry dba Layton Stone"))
    check("the refusal names what was missing",
          L.identity_ok(walsh, L.clean_candidate("WALSH SERVICES INCORPORATED"))[1].startswith("single_token_unverified_form"))
    check("Joeris searches JOERIS, not GENERAL", L.search_token("Joeris General Contractors") == "JOERIS")
    check("JRM Construction Management searches its full name, not MANAGEMENT",
          L.search_token("JRM Construction Management") == "JRM CONSTRUCTION MANAGEMENT")
    L.VERIFIED.clear()

    print("7. council titles: a one-word name in prose is usually a person")

    class FakeSource:
        def __init__(self, titles):
            self.titles = titles

        def get_json(self, url, params=None, key=""):
            return [{"MatterId": i, "MatterFile": f"F{i}", "MatterTypeName": "t", "MatterIntroDate": "2023-08-29",
                     "MatterTitle": t} for i, t in enumerate(self.titles)]
    titles = ["Appointment of Cali Mortenson Ellis, as Executive Director of the Seattle Community Police Commission.",
              "AN ORDINANCE authorizing an agreement with Mortenson Construction, Inc. for the arena."]
    res = L.council_for(FakeSource(titles), {"company_id": "A039", "canonical_name": "Mortenson"})
    check("'Appointment of Cali Mortenson Ellis' (the first dry run's row) is not a Mortenson mention",
          not any("Cali Mortenson" in h["title"] for h in res["hits"]))
    check("'Mortenson Construction, Inc.' in a title is a Mortenson mention", any("Mortenson Construction" in h["title"] for h in res["hits"]))
    res2 = L.council_for(FakeSource(["AN ORDINANCE approving a contract with Lease Crutcher Lewis for Fire Station 31."]),
                         {"company_id": "A022", "canonical_name": "Lease Crutcher Lewis"})
    check("a multi-word name still matches plainly in a title", len(res2["hits"]) == 1)

    print("8. v1.1 source-record aliases (2026-09-14)")
    L.VERIFIED.clear()
    L.VERIFIED.update({"A039": ["M. A. MORTENSON COMPANIES, INC.", "M. A. MORTENSON COMPANY"],
                       "A003": ["McShane Construction Company"]})
    mort2 = {"company_id": "A039", "canonical_name": "Mortenson"}
    mcs = {"company_id": "A003", "canonical_name": "The McShane Companies"}
    check("Seattle 'MA Mortenson Company' is accepted through the recipient-name alias",
          L.identity_ok(mort2, L.clean_candidate("MA Mortenson Company"))[0])
    check("Chicago 'M. A. MORTENSON COMPANY' is accepted through the same alias",
          L.identity_ok(mort2, L.clean_candidate("M. A. MORTENSON COMPANY"))[0])
    check("Wilmette 'MORTENSON CONSTRUCTION' is still refused", not L.identity_ok(mort2, L.clean_candidate("MORTENSON CONSTRUCTION"))[0])
    check("Chicago 'MCSHANE CONSTRUCTION COMPANY, LLC' is accepted through the alias",
          L.identity_ok(mcs, L.clean_candidate("MCSHANE CONSTRUCTION COMPANY, LLC"))[0])
    L.VERIFIED.clear()
    L.VERIFIED.update({"A039": ["M. A. MORTENSON COMPANIES, INC."]})
    check("the parent-entity name ALONE does not match 'MA Mortenson Company' (COMPANIES is not COMPANY)",
          not L.identity_ok(mort2, L.clean_candidate("MA Mortenson Company"))[0])
    L.VERIFIED.clear()
    check("'CLAYCO CONSTRUCTION' stays refused for Clayco without an alias",
          not L.identity_ok({"company_id": "A035", "canonical_name": "Clayco"}, L.clean_candidate("CLAYCO CONSTRUCTION"))[0])

    print("8b. v1.2 confirmed different firms (2026-09-15)")
    saved_nv = L.NOT_VARIANTS
    L.NOT_VARIANTS = {"A035": ["CLAYCO CONSTRUCTION"]}
    clay = {"company_id": "A035", "canonical_name": "Clayco"}
    accepted, why = L.identity_ok(clay, L.clean_candidate("CLAYCO CONSTRUCTION"))
    check("the Austin 'CLAYCO CONSTRUCTION' is refused as a confirmed different entity, not a pending question",
          not accepted and why.startswith("confirmed_different_entity"))
    check("Clayco's own Chicago name 'CLAYCO INC.' is still accepted", L.identity_ok(clay, L.clean_candidate("CLAYCO INC."))[0])
    L.NOT_VARIANTS = saved_nv

    print("9. the window")
    check("five years to the retrieval date", L.window("2026-09-13") == (dt.date(2021, 9, 13), dt.date(2026, 9, 13)))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
