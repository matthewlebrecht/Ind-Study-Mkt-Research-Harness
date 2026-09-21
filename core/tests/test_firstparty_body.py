#!/usr/bin/env python3
"""
H-FIRSTPARTY-01 v1.3's article-body extractor (harnesses/h_firstparty_01/body.py) against its five requirements, and
against the 111 pages the harness's rows came from (convention 40: the fix is verified on the pages that exposed the
defect, with expectations established independently of this extractor -- reviewer verdicts, the review sheet's
recorded page positions, and the O00307 bullet).

The five requirements (core/holds.py::EXTRACTION_PREREQUISITES):
  1. list items inside the article are prose
  2. a footer phrase ends the body only after article prose has begun (minimum-body fallback)
  3. consent banners are excluded
  4. the end-of-article marker matches "Editors' picks" in every apostrophe form
  5. the end of the article is found before chrome is stripped

    python core/tests/test_firstparty_body.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from core import validity as V  # noqa: E402
from harnesses.h_execid_01.extract import html_lines  # noqa: E402
from harnesses.h_firstparty_01 import body as B  # noqa: E402
from harnesses.h_vendor_01.harness import body_lines, strip_chrome  # noqa: E402

PASS = FAIL = 0
FIX = ROOT / "core" / "tests" / "fixtures" / "firstparty_pages"
P = "<p>" + "The company completed the rollout of its new order management system across all of its sites. " * 3 + "</p>"
TEASER = "Teaser: a rival contractor adopts artificial intelligence to compare drawing packages, in a story long enough to read as prose."


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def has(text: str, term: str) -> bool:
    return bool(re.search(r"\b" + re.escape(term) + r"\b", text, re.I))


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def main() -> int:
    print("1. list items inside the article are prose")
    b = B.extract(f"<html><body><h1>Results</h1>{P}<ul><li>Expanded the AI business unit, integrating machine learning "
                  f"capabilities into the platform</li><li>Home</li></ul>{P}<ul><li>Another company launches an unrelated "
                  f"artificial intelligence platform for builders today</li></ul></body></html>")
    check("a clause-length bullet between paragraphs is kept (O00307's shape)", "Expanded the AI business unit" in b.text)
    check("a one-word list item (navigation) is not", "Home" not in b.lines)
    check("a list after the last paragraph (related headlines) is not the article", "Another company launches" not in b.text)

    print("2. a footer phrase ends the body only after article prose has begun")
    b = B.extract(f"<h1>Acquisition</h1><p>This story was originally published on Trucking Dive. To receive daily news and "
                  f"insights, subscribe to our free daily Trucking Dive newsletter.</p>{P}{P}<p>Sign up for our newsletter to "
                  f"get more stories like this one delivered to your inbox every day.</p><p>{TEASER}</p>")
    check("the syndication notice before the article is dropped as a notice, not taken as the end (Yahoo's shape)",
          len(b.footer_notices_dropped) == 1 and "order management system" in b.text)
    check("a footer phrase after the article ends it", b.footer_cut.lower() == "sign up for" and TEASER not in b.text)
    check("the body keeps the whole article, not ~90 characters", len(b.text) > 500)

    print("3. consent banners are excluded")
    b = B.extract(f"<h1>Promotions</h1>{P}<div id=\"cookie-law-info-bar\"><div class=\"cli-bar\"><p>Analytical cookies are "
                  f"used to understand how visitors interact with the website. Analytics cookies store consent.</p></div></div>")
    check("a cookie-consent container is removed with its nested subtree (Caddell's shape)",
          b.consent_elements_removed == 1 and not has(b.text, "analytics"))
    b = B.extract(f"<h1>Expansion</h1><p>The bakery expanded its cookie production line with automated ovens, doubling output "
                  f"of its chocolate chip cookies across three plants this year.</p>{P}")
    check("an article about actual cookies is not a consent banner", "cookie production line" in b.text)
    b = B.extract(f"<html><body><div class=\"cookie-consent-wrapper\"><h1>Launch</h1>{P}{P}</div></body></html>")
    check("a 'consent' element wrapping most of the page is left alone", "order management system" in b.text)
    b = B.extract(f"<h1>News</h1>{P}<p>We use cookies on our website to give you the most relevant experience by remembering "
                  f"your preferences and repeat visits.</p>")
    check("a consent sentence outside any marked container is dropped by the line backstop",
          b.consent_lines_dropped == 1 and "We use cookies" not in b.text)

    print("4. the end-of-article marker matches \"Editors' picks\" in every apostrophe form")
    inherited = re.compile(r"(?i)editor.s picks")
    check("(the inherited pattern `editor.s picks` misses Construction Dive's form -- the defect)",
          not inherited.search("Editors’ picks") and not inherited.search("Editors' picks"))
    for form in ("Editors’ picks", "Editors' picks", "Editor's picks", "Editors picks", "EDITORS’ PICKS"):
        b = B.extract(f"<h1>Award</h1>{P}{P}<h2>{form}</h2><p>{TEASER}</p>")
        check(f"{form!r} ends the article", TEASER not in b.text and bool(b.end_marker))

    print("5. the end of the article is found before chrome is stripped")
    page = (f"<h1>Award</h1>{P}{P}<aside><h3>Editors’ picks</h3></aside><div class=\"rail\"><p>{TEASER}</p></div>"
            f"<footer><p>Construction Dive is published by TechTarget, Inc. An Informa PLC company.</p></footer>")
    b = B.extract(page)
    check("a marker inside <aside> still ends the article, so the teaser after it is not read", TEASER not in b.text)
    check("(stripping chrome first would have removed the marker and kept the teaser -- the defect)",
          TEASER in " ".join(body_lines(strip_chrome(page))))
    b = B.extract(f"<h1>Award</h1><div><span>More from Construction Dive</span></div>{P}{P}")
    check("a marker before any article prose does not end the article", "order management system" in b.text)

    print("6. the fixtures")
    index = json.loads((FIX / "index.json").read_text(encoding="utf-8"))
    pages = index["pages"]
    check(f"{len(pages)} page fixtures, none missing", len(pages) == 111 and not index["urls_without_a_cached_page"])
    texts = {}
    bad = []
    for url, meta in pages.items():
        t = gzip.decompress((FIX / meta["file"]).read_bytes()).decode("utf-8")
        if hashlib.sha256(t.encode("utf-8")).hexdigest() != meta["fixture_sha256"]:
            bad.append(url)
        texts[url] = t
    check("every fixture matches the hash recorded when it was built", not bad)

    wb = openpyxl.load_workbook(ROOT / "data" / "market_intel_db.xlsx", read_only=True, data_only=True)
    it = wb["Observations"].iter_rows(values_only=True)
    h = list(next(it))
    rows = {r[0]: dict(zip(h, r)) for r in it if r and r[0]}
    invalid = V.invalid_observation_ids(wb)
    bodies = {url: B.extract(t) for url, t in texts.items()}

    def terms(oid):
        m = re.search(r"matched: ([^|]+)", str(rows[oid]["evidence_excerpt"] or ""))
        return [x.strip() for x in m.group(1).split(",")] if m else []

    def body_of(oid):
        return bodies[rows[oid]["source_url"]].text

    bodies_by_id = {o: rows[o]["source_url"] for o in rows if rows[o]["source_url"] in bodies}

    print("7. every body is text the page actually carries")
    invented = [u for u, bd in bodies.items() if not all(squash(ln) in squash(" ".join(html_lines(texts[u]))) for ln in bd.lines)]
    check("no body line is absent from the page's own visible text", not invented)
    leaks = [u for u, bd in bodies.items() if re.search(r"(?i)cookielawinfo|we use cookies|gdpr cookie", bd.text)]
    check("no body carries consent-banner text", not leaks)

    print("8. rows a REVIEWER judged to rest on page furniture: the matched term is not in the body")
    det = {r["observation_id"]: r for r in V.rows_from_sheet(wb[V.SHEET]) if not r["superseded_by"]}
    judged = sorted(o for o, s in invalid.items() if s == "invalidated_extraction_defect"
                    and rows[o]["harness_id"] == "H-FIRSTPARTY-01" and "Matthew Lebrecht" in det[o]["determined_by"])
    check(f"the fixture set covers all {len(judged)} reviewer-judged rows",
          len(judged) == 10 and all(rows[o]["source_url"] in bodies for o in judged))
    for oid in judged:
        check(f"{oid}: none of {terms(oid)} is in its article body", not [t for t in terms(oid) if has(body_of(oid), t)])

    print("9. rows the v1.3 RUN recorded: the status names extraction, and the 8 it did not fit")
    # HR-0083 recorded every row it stopped producing as `invalidated_extraction_defect`, on Matthew Lebrecht's
    # instruction (2026-09-15, item 22). For 89 of the 97 that IS the reason. Eight were dropped for other reasons
    # and their matched term was still in the article body, so the status named the wrong cause -- in two OPPOSITE
    # directions. Matthew superseded all eight on 2026-09-17 (batch hr0083-overstated-2026-09-17):
    #   * six are `invalidated_wrong_entity` -- the article never names the company at all;
    #   * two are `invalidated_not_reproduced` -- the McCarthy rows, correct when written, which crossed the
    #     five-year currency line on 2026-09-08, seven days before the run.
    # This section pins BOTH halves: what the run recorded, and that the exception set has not grown. The invariant
    # that matters going forward is the last check -- no row still recorded as an extraction defect BY THE HARNESS
    # may still carry its matched term in the body, because that is precisely the signature of a mislabelled row.
    CORRECTED = {
        "O00297": "invalidated_wrong_entity",   # the Lio funding release never names National Product Sales
        "O00298": "invalidated_wrong_entity",
        "O00431": "invalidated_wrong_entity",
        "O00354": "invalidated_wrong_entity",   # the release is about Penta Technologies, not PENTA Building Group
        "O00355": "invalidated_wrong_entity",
        "O00359": "invalidated_wrong_entity",   # the release is about ESS Tech, Inc., not ESS Companies
        "O00324": "invalidated_not_reproduced",  # McCarthy: aged out of the five-year window
        "O00325": "invalidated_not_reproduced",
    }
    machine = sorted(o for o, st in invalid.items() if st == "invalidated_extraction_defect"
                     and rows[o]["harness_id"] == "H-FIRSTPARTY-01" and "Matthew Lebrecht" not in det[o]["determined_by"])
    # 97 recorded by the run, minus the 8 superseded on 2026-09-17 (wrong entity / aged out), minus
    # O00350 and O00531, superseded on 2026-09-20 when Matthew ruled the Front Line Power Construction
    # press release a wrong-entity case -- the second time an extraction-defect label was found to be
    # carrying an identity failure. Each subtraction is a REVIEWER moving a row out of the machine's
    # status, which is why the filter excludes rows determined by a person.
    check(f"the run's extraction-defect rows are the 87 it still fits, all by the harness and not a reviewer",
          len(machine) == 87 and all(det[o]["determined_by"].startswith("H-FIRSTPARTY-01") for o in machine))
    check("all 8 corrected rows now carry the superseding status, recorded by a reviewer",
          all(invalid.get(o) == want and "Matthew Lebrecht" in det[o]["determined_by"]
              for o, want in CORRECTED.items()))
    check("the correction split six wrong-entity rows from two that merely aged out",
          sorted(o for o, w in CORRECTED.items() if w == "invalidated_wrong_entity") ==
          ["O00297", "O00298", "O00354", "O00355", "O00359", "O00431"]
          and sorted(o for o, w in CORRECTED.items() if w == "invalidated_not_reproduced") == ["O00324", "O00325"])
    still_matching = sorted(o for o in machine if o in bodies_by_id and [t for t in terms(o) if has(body_of(o), t)])
    check("NO row still recorded an extraction defect by the harness carries its matched term in the body "
          "(the exception set is closed; a new one here is a new mislabelled row)",
          still_matching == [])
    corrected_still_matching = sorted(o for o in CORRECTED if o in bodies_by_id
                                      and [t for t in terms(o) if has(body_of(o), t)])
    check("and the corrected rows are exactly the ones whose terms ARE still in the body",
          corrected_still_matching == sorted(set(CORRECTED) - {"O00431"}))

    print("10. rows whose match is recorded as genuinely in the article keep it")
    check("O00349: its match is in the Bechtel/Kiewit article body (sheet: page lines 65-75)",
          any(has(body_of("O00349"), t) for t in terms("O00349")))
    check("O00530: 'operational excellence' is in the Front Line release body (sheet: line 448)",
          has(body_of("O00530"), "operational excellence"))
    check("O00350: its matched terms, all PR Newswire navigation on the sheet, are not in the body",
          not any(has(body_of("O00350"), t) for t in terms("O00350")))
    check("O00531: 'Workforce Management', PR Newswire navigation on the sheet, is not in the body",
          not has(body_of("O00531"), "Workforce Management"))
    check("O00307: the press-release bullet 'Expanded the AI business unit' is in the body (defect 1)",
          "Expanded the AI business unit" in body_of("O00307"))

    print("11. the page families that exposed the defects")
    yahoo = [u for u in bodies if "finance.yahoo.com" in u]
    check(f"all {len(yahoo)} Yahoo Finance pages keep at least {B.MIN_BODY_CHARS} characters of article (defect 2)",
          yahoo and all(len(bodies[u].text) >= B.MIN_BODY_CHARS for u in yahoo))
    check("... and none keeps the syndication notice", not [u for u in yahoo if "originally published on" in bodies[u].text])
    cd = [u for u in bodies if "constructiondive.com" in u]
    check(f"no Construction Dive body ({len(cd)} pages) carries the Informa/TechTarget footer",
          not [u for u in cd if re.search(r"Informa PLC|TechTarget", bodies[u].text)])
    check("every Construction Dive body ends at an end-of-article marker or a site footer (defects 4 and 5; the "
          "press-release template carries no marker and ends at its copyright line)",
          all(bodies[u].end_marker or bodies[u].footer_cut for u in cd))
    b = B.extract(f"<h1>Additions</h1>{P}{P}<p>© 2025 TechTarget, Inc. or its subsidiaries. All rights reserved. An Informa PLC "
                  f"company.</p><p>{TEASER}</p>")
    check("a copyright line after the article ends it", "TechTarget" not in b.text and TEASER not in b.text)
    prn = [u for u in bodies if "prnewswire.com" in u]
    nav = {"Human Resource & Workforce Management", "Create with AI", "Data Analytics", "Artificial Intelligence"}
    check(f"no PR Newswire body ({len(prn)} pages) carries a navigation label as a line",
          not [u for u in prn if nav & set(bodies[u].lines)])
    check("every PR Newswire body carries its release dateline (the article was found, not just the chrome removed)",
          all("/PRNewswire/" in bodies[u].text for u in prn))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
