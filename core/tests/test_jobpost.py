"""
Tests for H-JOBPOST-01 v1.1 — the classifier's term model and discovery's own-domain rule.

    python core/tests/test_jobpost.py

There was no suite for this harness at all before 2026-09-01, which is why the seven
classifier false positives below survived from v1.0: nothing asserted what the terms were
supposed to mean, so nothing could disagree with them.

Convention 40 governs what is asserted here. A suite that only checks the cases somebody
already thought of asserts the implementation rather than the requirement, so every
discrimination is tested in BOTH directions -- the false positive must not fire AND the
true positive must still fire. A classifier that returned nothing at all would pass half
of this file, and that half alone would look like success.

The negative cases are not invented. Every one is either a real title from the pilot run
or the literal shape that produced a defect:

    "Process Engineer"                 Merit Medical, pilot run 2026-09-01 -- the false
                                       positive the 15-company checkpoint existed to find
    "BI-Weekly Payroll Clerk"          \\bBI\\b matching inside a hyphenated adverb
    "API Technician - Active
       Pharmaceutical Ingredients"     API is the Active Pharmaceutical Ingredient
    "Lean Beef Processing Associate"   this universe contains food distributors
    login.icims.com                    Prime Inc., pilot run -- iCIMS's shared auth host
                                       captured as the company's tenant
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_jobpost_01.classifier import RuleClassifier  # noqa: E402
from harnesses.h_jobpost_01.discovery import (  # noqa: E402
    careers_links_on, detect_ats, looks_like_careers, registrable)

PASSED = FAILED = 0


def check(label: str, cond: bool) -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok    {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label}")


def main() -> int:
    c = RuleClassifier()

    print("1. an acronym is matched case-sensitively")
    # "Ai Weiwei" became an AI hire under case-insensitive matching. Capitalisation is the
    # only thing separating the acronym from an ordinary word or a name.
    check("'AI Program Manager' is an AI hire",
          "data_analytics_ai_hiring" in c.classify("AI Program Manager").signals)
    check("'Ai Weiwei Gallery Assistant' is not",
          not c.classify("Ai Weiwei Gallery Assistant").signals)
    check("lowercase 'ai' in prose is not an AI programme",
          not c.classify("Barista - ai no keiken wa fuyou").signals)

    print()
    print("2. a term can be vetoed by context")
    check("'BI-Weekly Payroll Clerk' is not a BI hire",
          not c.classify("BI-Weekly Payroll Clerk").signals)
    check("'Power BI Developer' still is",
          "data_analytics_ai_hiring" in c.classify("Power BI Developer").signals)
    check("pharmaceutical API is not an interface",
          not c.classify(
              "API Technician - Active Pharmaceutical Ingredients").signals)
    check("'EDI Analyst' is still an integration hire",
          "integration_engineering_hiring" in c.classify("EDI Analyst").signals)

    print()
    print("3. an ordinary English word needs a qualifier (convention 31)")
    for title in ("Oracle Card Dealer", "Lean Beef Processing Associate",
                  "Innovation Center Tour Guide", "Transformation Coach - Wellness",
                  "Conveyor Belt Maintenance Mechanic"):
        check(f"{title!r} carries no signal", not c.classify(title).signals)
    for title, sig in (("Oracle ERP Financials Analyst", "erp_core_systems_hiring"),
                       ("Lean Manufacturing Engineer", "digital_transformation_hiring"),
                       ("VP of Innovation and Technology", "digital_transformation_hiring"),
                       ("Director of Digital Transformation", "digital_transformation_hiring"),
                       ("Conveyor Controls Engineer",
                        "warehouse_systems_automation_hiring")):
        check(f"{title!r} still fires", sig in c.classify(title).signals)

    print()
    print("4. the classifier tracks core/topics.py, not its own intuition")
    # The pilot's false positive. digital_transformation_process lists process
    # improvement / excellence / reengineering / automation -- each naming a change
    # PROGRAMME -- and omits the bare engineering title. v1.0 had added `engineer`.
    check("'Process Engineer' is NOT modernization evidence",
          not c.classify("Process Engineer").signals)
    check("'Process Improvement Manager' is",
          "digital_transformation_hiring" in
          c.classify("Process Improvement Manager").signals)
    check("'Continuous Improvement Leader' is (it is in the theme spine)",
          "digital_transformation_hiring" in
          c.classify("Continuous Improvement Leader").signals)

    print()
    print("5. the founding case still holds (convention 16)")
    check("bare 'Infor' does not match inside 'Information Systems'",
          not c.classify("Information Systems Manager").signals)
    check("'Infor M3 Consultant' does match",
          "erp_core_systems_hiring" in c.classify("Infor M3 Consultant").signals)

    print()
    print("6. ordinary operational hiring is excluded even when it names a system")
    for title in ("Warehouse Associate - WMS experience a plus",
                  "Forklift Operator (RF scanner / WMS)",
                  "CDL Driver - telematics equipped",
                  "Technical Recruiter - Data Engineering team",
                  "Sales Representative - WMS software"):
        check(f"{title[:44]!r} is excluded", not c.classify(title).signals)
    check("'WMS Integration Engineer' is not excluded",
          "warehouse_systems_automation_hiring" in
          c.classify("WMS Integration Engineer").signals)

    print()
    print("7. a rejected term is reported, not discarded (convention 7)")
    rejected = c.classify("Lean Beef Processing Associate").rejected
    check("the vetoed term says why it was not admitted", bool(rejected))

    print()
    print("8. ATS detection names a host, never a product word")
    check("iCIMS's shared auth host is not a tenant",
          detect_ats('<a href="https://login.icims.com/jobs/">') == ("", ""))
    check("a real iCIMS tenant is",
          detect_ats('<a href="https://careers-plslogistics.icims.com/jobs">')
          == ("icims", "careers-plslogistics"))
    # The lookahead alone was not enough: a bare (?!login\\.) shifts one character and
    # matches "ogin.icims.com". The left boundary is what makes it correct, and this is
    # the case that proved the first fix wrong.
    check("a page linking to BOTH picks the real tenant, not 'ogin'",
          detect_ats("login.icims.com and careers-gilbane.icims.com")
          == ("icims", "careers-gilbane"))
    check("'a typical workday' is not a Workday tenant",
          detect_ats("<p>a typical workday here starts at 6am</p>") == ("", ""))
    check("a real Workday host is",
          detect_ats("https://kencogroup.wd12.myworkdayjobs.com/Kenco")[0] == "workday")

    print()
    print("9. discovery never accepts a third-party board as a careers page")
    home = "https://example.com"
    html = ('<a href="/careers">Careers</a>'
            '<a href="https://www.linkedin.com/company/x/jobs/">Our jobs on LinkedIn</a>'
            '<a href="https://www.indeed.com/cmp/X">Indeed</a>'
            '<a href="https://jobs.example.com/openings">Job openings</a>')
    links = careers_links_on(html, home, home)
    check("own-domain careers link is kept",
          any(l.endswith("/careers") for l in links))
    check("an own-domain SUBDOMAIN is kept (jobs.example.com)",
          any("jobs.example.com" in l for l in links))
    check("the LinkedIn link is dropped",
          not any("linkedin.com" in l for l in links))
    check("the Indeed link is dropped",
          not any("indeed.com" in l for l in links))
    check("registrable() sees through www.",
          registrable("www.example.com") == registrable("jobs.example.com"))

    print()
    print("10. a 200 is not enough to accept a careers URL")
    check("a soft 404 is rejected even though it says 'careers'",
          not looks_like_careers("<h1>Page Not Found</h1><p>careers</p>"))
    check("a real careers page is accepted",
          looks_like_careers("<h1>Careers</h1><p>View all jobs and apply now</p>"))
    check("an unrelated page is not",
          not looks_like_careers("<h1>Our History</h1><p>Founded in 1946.</p>"))

    print()
    print("11. the four 2026-09-02 keys: specific-tier from the start (brief §4, condition 3)")
    def sig(title):
        return c.classify(title).signals
    # cloud: a vendor name alone is a requisition commonplace, not a migration.
    check("'AWS Solutions Architect' alone is NOT cloud-migration evidence",
          "cloud_infrastructure_hiring" not in sig("AWS Solutions Architect"))
    check("'Cloud Migration Engineer (AWS)' is",
          "cloud_infrastructure_hiring" in sig("Cloud Migration Engineer (AWS)"))
    check("'Azure Infrastructure Engineer - legacy data center exit' is",
          "cloud_infrastructure_hiring" in
          sig("Azure Infrastructure Engineer - legacy data center exit"))
    check("'Mainframe Operator' alone is not; 'Mainframe Modernization Lead' is",
          "cloud_infrastructure_hiring" not in sig("Mainframe Operator")
          and "cloud_infrastructure_hiring" in sig("Mainframe Modernization Lead"))
    # cybersecurity: the physical senses of "security" are the trap in this universe.
    check("'Security Officer - Distribution Center' is NOT cybersecurity",
          "cybersecurity_hiring" not in sig("Security Officer - Distribution Center"))
    check("'Security Engineer' alone is not; 'Network Security Engineer' is",
          "cybersecurity_hiring" not in sig("Security Engineer")
          and "cybersecurity_hiring" in sig("Network Security Engineer"))
    check("'Cybersecurity Analyst' and 'SOC Analyst' are",
          "cybersecurity_hiring" in sig("Cybersecurity Analyst")
          and "cybersecurity_hiring" in sig("SOC Analyst"))
    check("'Loss Prevention Security Analyst' is vetoed",
          "cybersecurity_hiring" not in sig("Loss Prevention Security Analyst"))
    # workforce enablement: the platform name needs a systems role beside it.
    check("'Payroll Clerk (Kronos)' is NOT; 'Kronos/UKG Systems Analyst' is",
          "workforce_enablement_hiring" not in sig("Payroll Clerk (Kronos)")
          and "workforce_enablement_hiring" in sig("Kronos/UKG Systems Analyst"))
    check("'Frontline Technology Manager' and 'Workforce Management System Administrator' are",
          "workforce_enablement_hiring" in sig("Frontline Technology Manager")
          and "workforce_enablement_hiring" in
          sig("Workforce Management System Administrator"))
    # OT: the most specific vocabulary in the file. Case-sensitive acronyms.
    check("'Controls Engineer - PLC/SCADA' is ot_modernization",
          "ot_modernization_hiring" in sig("Controls Engineer - PLC/SCADA"))
    check("'Quality Control Technician' is NOT (first dry run's false positive)",
          "ot_modernization_hiring" not in sig("Quality Control Technician"))
    check("'QA Document Control Specialist II' is NOT (the other one)",
          "ot_modernization_hiring" not in sig("QA Document Control Specialist II"))
    check("'Controls Engineer' and 'Control Systems Engineer' are",
          "ot_modernization_hiring" in sig("Controls Engineer")
          and "ot_modernization_hiring" in sig("Control Systems Engineer"))
    check("'Instrumentation & Controls Technician' is",
          "ot_modernization_hiring" in sig("Instrumentation & Controls Technician"))
    check("lowercase 'plc' in prose is not (acronym is case-sensitive)",
          "ot_modernization_hiring" not in sig("warehouse associate at the plc site"))
    check("'OT Security Engineer' is cybersecurity AND ot_modernization (both are true)",
          {"cybersecurity_hiring", "ot_modernization_hiring"} <= set(sig("OT Security Engineer")))
    # And the regression anchor: nothing v1.1 admitted or refused moves.
    check("'Lean Beef Processing Associate' is still nothing",
          not sig("Lean Beef Processing Associate"))
    check("'Process Engineer' is still nothing",
          not sig("Process Engineer"))
    check("'WMS Integration Engineer' still carries warehouse + integration and nothing new",
          set(sig("WMS Integration Engineer")) ==
          {"warehouse_systems_automation_hiring", "integration_engineering_hiring"})
    # Condition 2: every key lands in the spine mapping, and the mapping now covers all ten.
    from core import topics as _topics
    check("all four keys are in BUYER_SIGNAL_TO_THEME",
          all(k in _topics.BUYER_SIGNAL_TO_THEME for k in
              ("cloud_infrastructure_hiring", "cybersecurity_hiring",
               "workforce_enablement_hiring", "ot_modernization_hiring")))
    check("every theme in the spine now has at least one H-JOBPOST-01 key mapped to it",
          {t.key for t in _topics.THEMES} <= set(_topics.BUYER_SIGNAL_TO_THEME.values()))
    check("every classifier key is either a mapped theme signal or the volume topic",
          all(s.key in _topics.BUYER_SIGNAL_TO_THEME for s in c.signals))

    print(f"\n{PASSED} checks passed, {FAILED} failed.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
