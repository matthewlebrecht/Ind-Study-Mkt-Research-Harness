#!/usr/bin/env python3
"""
H-VENDOR-01 v1.1, tested against the requirement.

Every case is one of the six pages v1.0 read and called absent, measured on the archived
HTML on 2026-09-13, restated as the behaviour the harness must have. No vendor test file
existed before v1.1, which is how a name test that could never find "SpawGlass" or
"Melaleuca" in prose survived a live run (convention 40).

    python core/tests/test_vendor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_vendor_01 import harness as V  # noqa: E402

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def co(cid, name, hq, site):
    return {"company_id": cid, "canonical_name": name, "hq_state": hq, "website": site}


def main() -> int:
    print("1. a coined one-token name is found in prose (the v1.0 defect)")
    check("'SpawGlass Holding' is named by a sentence that says 'SpawGlass'",
          V.names_company("The SpawGlass team didn't initially set out to do Enterprise Architecture.", "SpawGlass Holding"))
    check("'Melaleuca, Inc.' is named by a sentence that says 'Melaleuca'",
          V.names_company("Melaleuca partnered with XCentium to roll out a global shopping experience.", "Melaleuca, Inc."))
    check("a coined token is matched as a word, not a substring ('SpawGlassware' does not name SpawGlass)",
          not V.names_company("SpawGlassware shipped today.", "SpawGlass Holding"))
    check("a common-word name still needs the full phrase ('Prime' alone does not name Prime Inc.)",
          not V.names_company("Prime rolled out a new platform.", "Prime Inc.")
          and V.names_company("Prime Inc. rolled out a new platform.", "Prime Inc."))
    check("a two-token name is named by either distinctive token (Joeris General Contractors)",
          V.names_company("Joeris began using OpenSpace early in the project.", "Joeris General Contractors"))

    print("2. a one-token name on a third-party page needs a corroborator")
    graham = co("A026", "Graham Construction", "Omaha, NE", "https://www.grahambuilds.com")
    uk = "GRAHAM is a leading, privately owned construction company operating across the UK and the Republic of Ireland."
    check("the UK GRAHAM page (no Omaha, no Nebraska, no grahambuilds.com) is refused",
          not V.corroborates_identity("<html>" + uk + "</html>", uk, graham)[0])
    check("the same page naming Omaha would be accepted", V.corroborates_identity("", uk + " Omaha", graham)[0])
    spaw = co("A021", "SpawGlass Holding", "Selma, Texas", "https://spawglass.com")
    check("SpawGlass: the website domain in the HTML corroborates",
          V.corroborates_identity('<a href="https://spawglass.com">site</a>', "SpawGlass story", spaw)[0])
    joeris = co("A093", "Joeris General Contractors", "San Antonio, TX", "https://joeris.com")
    check("a two-distinctive-token name is not gated", V.corroborates_identity("", "nothing", joeris)[0])
    penta = co("A083", "The PENTA Building Group", "Las Vegas, NV", "https://pentabldggroup.com")
    check("PENTA: the HQ city corroborates", V.corroborates_identity("", "operational certainty in Las Vegas", penta)[0])
    check("a state CODE alone is not a corroborator (the state's full name is required)",
          not V.corroborates_identity("", "shipped to NE customers", graham)[0])
    check("the refusal says what was missing",
          "no grahambuilds.com" in V.corroborates_identity("", uk, graham)[1])

    print("3. non-vendor hosts are excluded before reading")
    check(".edu is not vendor content", V.NOT_VENDOR_TLDS.get("edu") == "university_page_not_vendor_content")
    check("a D&B directory profile is not vendor content", "dnb.com" in V.NOT_VENDOR_HOSTS)
    use, excluded = V.seeds()
    urls = [s["url"] for s in use]
    check("no .edu seed is read", not any(".edu/" in u for u in urls))
    check("the seed list ignores a leading www. (one Grant Thornton page, not two)",
          sum(1 for s in use + excluded if "grantthornton.com/services/advisory-services/technology-modernization" in s["url"]) == 1)

    # The first v1.1 dry run stripped www. from the URL it FETCHED, not only from the dedupe
    # key, and broke Joeris / OpenSpace, the page v1.0 had read. Every fetch URL must be a URL
    # exactly as EXECVOICE logged it.
    import glob
    import json
    logged = set()
    for path in glob.glob(V.SEED_GLOB):
        try:
            for e in json.loads(Path(path).read_text(encoding="utf-8")).get("excluded_vendor_urls") or []:
                logged.add(str(e["url"]))
        except json.JSONDecodeError:
            continue
    check("every usable seed is fetched at the URL EXECVOICE logged, unmodified",
          bool(use) and all(s["url"] in logged for s in use))
    check("the OpenSpace / Joeris seed keeps its www.",
          any(s["url"].startswith("https://www.openspace.ai/") for s in use))

    print("4. v1.2 page-subject attribution (title names the company; chrome excluded)")
    page = ("<html><head><title>SpawGlass Builds a Cost-Efficient Future by Mapping Its Technology Landscape</title></head>"
            "<body><header><nav><ul><li>Govern and Leverage AI Effectively. See how AI is really being deployed and used.</li>"
            "</ul></nav></header><main><article><h1>SpawGlass Builds a Cost-Efficient Future</h1>"
            "<p>The team is actively engaged in Business Process Management, using Ardoq's AI capabilities to generate process maps.</p>"
            "</article></main><footer>Leverage AI across your enterprise with our analytics platform.</footer></body></html>")
    # The harness joins the chrome-free body on BLOCK boundaries, so a heading never fuses with
    # the paragraph after it; the fixture is built the same way.
    body = "\n".join(V.body_lines(V.strip_chrome(page)))
    # The Ardoq markup verbatim (first v1.2 dry run): an inline link inside a list item must not
    # cut the sentence, or its deployment verb and theme term land in different "sentences".
    li = ('<html><head><title>SpawGlass Builds a Cost-Efficient Future</title></head><body><main><article><ul>'
          '<li aria-level="1"><strong>Automated Data Population in Just 15 Minutes:</strong> They leveraged the '
          '<a href="https://www.ardoq.com/integrations"><span>Microsoft Entra ID integration</span></a> (formerly known '
          'as Active Directory) to pull in people and departments.</li></ul></article></main></body></html>')
    li_body = "\n".join(V.body_lines(V.strip_chrome(li)))
    check("an inline link inside a list item does not cut the sentence",
          any("They leveraged the Microsoft Entra ID integration (formerly known as Active Directory)" in s
              for s in V.sentences(li_body)))
    check("that sentence is attributed on a subject page (deployment verb + integration term)",
          any(r.topic == "systems_integration" for r in V.read_page(li_body, {"company_id": "A021", "canonical_name": "SpawGlass Holding"},
                                                                     "u", "2026-09-13", {}, subject=True)))
    check("a heading still does not fuse with the paragraph after it",
          not any("SpawGlass Builds" in s and "The team" in s for s in V.sentences(body)))
    check("the page title is read", V.page_title(page).startswith("SpawGlass Builds"))
    check("navigation, header and footer text is removed before the scan",
          "Govern and Leverage" not in body and "enterprise with our analytics" not in body and "The team is actively" in body)
    spaw_co = {"company_id": "A021", "canonical_name": "SpawGlass Holding"}
    rows = V.read_page(body, spaw_co, "u", "2026-09-13", {}, subject=True)
    check("an unnamed body deployment sentence is attributed when the title names the company",
          any(r.topic == "data_analytics_ai" for r in rows))
    check("an attributed row says so and carries lower confidence",
          # the marker is required, its position is not: a generic-tier row also carries the
          # [low-grade: ...] marker, which leads the excerpt (convention 41)
          bool(rows) and all("[page-subject attribution" in r.evidence_excerpt and r.confidence_0_1 <= 0.4 for r in rows))
    check("the same sentence is NOT attributed when the title does not name the company",
          not V.read_page(body, spaw_co, "u", "2026-09-13", {}, subject=False))
    full = " ".join(V.html_lines(page))
    check("nav text is never attributed, even on a subject page, once chrome is stripped",
          not any("Govern and Leverage" in r.evidence_excerpt for r in V.read_page(body, spaw_co, "u", "2026-09-13", {}, subject=True))
          and "Govern and Leverage" in full)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
