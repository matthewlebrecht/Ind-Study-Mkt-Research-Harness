"""
Extraction tests for H-TRADEPRESS-01.

    python core/tests/test_tradepress.py

Every case here is a real sentence from a page the first run actually fetched, not an
invented example. Three of them are regressions the first run produced and the second run
had to fix, and they are kept because the fixes pull in opposite directions -- widening
the title pattern and the action verbs raises yield, and the identity and characterisation
guards lower it. A change that improves one number by breaking the other is the exact
failure convention 33's companion lesson names: check the fix against the case that WAS
working, not only the one that was broken.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harnesses.h_tradepress_01 import extract  # noqa: E402

PASSED = FAILED = 0


def check(cond, label):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok    {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label}")


# Real text, Construction Dive, "Gilbane bets on AI in national rollout", 2024-09-10.
TRUNK_TOOLS = (
    "Dive Brief: Providence, Rhode Island-based contractor Gilbane Building Co. is "
    "betting on artificial intelligence, signing a deal with contech firm Trunk Tools to "
    "deploy its AI chatbot on jobsites across the country, according to a Sept. 10 news "
    "release. Gilbane will scale the platform beginning with ten projects representing "
    "its market sector portfolio. Previously, Gilbane used New York-based Trunk Tools' "
    "TrunkText chatbot to track nearly 21,000 documents across its work on the Baird "
    "Center in Milwaukee, which the contractor completed on a fast-track schedule in May "
    "2024. “We partnered with Trunk Tools for its innovative approach to document "
    "management and productivity enhancement,” said Karen Higgins-Carter, "
    "Gilbane’s chief information and digital officer. “We believe AI can "
    "transform our operations by refocusing our teams’ work on higher value, more "
    "strategic tasks.”"
)

# Real text, Construction Dive, "ConTech Conversations", 2023-03-08. A Q&A transcript:
# no quotation marks anywhere, all-caps speaker labels.
CONTECH = (
    "ConTech Conversations: When it comes to innovation, be intentional, says Gilbane "
    "exec. Kelly Benedict, the firm’s head of innovation and transformation, sees a "
    "lot of opportunity. Published March 8, 2023 Matthew Thibault Reporter. "
    "CONSTRUCTION DIVE: What do you do in your innovation role at Gilbane? "
    "KELLY BENEDICT: Every day is different, and every hour is different, as you can "
    "imagine. I'm chairing our Innovation Council, which is comprised of 17 people "
    "across the organization. We've landed on five areas of focus for our digital "
    "transformation: a shared roadmap and innovation for the business. We're working "
    "with the board and the executive leadership team and going through and evaluating "
    "our cyber risks, because it's going to be baked into everything we do. "
    "Recommended Reading How Gilbane used an AI tool to track 21,000 documents"
)


def main() -> int:
    print("1. compound C-suite titles (the regression that cost the best article)")
    sp = extract.speakers_in_article(TRUNK_TOOLS, "Gilbane Building Co.")
    names = [s["name"] for s in sp]
    check("Karen Higgins-Carter" in names,
          "'Gilbane's chief information and digital officer' is recognised")
    check(any("chief information" in s["title"] for s in sp),
          "the compound title is captured, not truncated at two words")

    print("\n2. the speaker gate refuses what it should")
    check(not extract.speakers_in_article(
        "said Karen Higgins-Carter, an industry analyst at Gartner.", "Gilbane"),
        "an analyst quoted about the company is not the company speaking")
    check(not extract.speakers_in_article(
        "said Karen Higgins-Carter, chief information officer.", "Gilbane"),
        "a name and title with no employer is refused -- adjacency IS the identity claim")
    check(not extract.speakers_in_article(
        "Jane Roe, the firm's chief information officer, has led three migrations.",
        "Gilbane"),
        "'the firm's' with this company nowhere nearby is refused")
    check(extract.speakers_in_article(
        "Gilbane hired Jane Roe. Jane Roe, the firm's chief information officer, "
        "has led three migrations at Gilbane.", "Gilbane"),
        "'the firm's' IS admitted when the company is named within the window")

    print("\n3. reported actions: present participle as well as past tense")
    actions, dropped = extract.reported_actions(TRUNK_TOOLS)
    verbs = " ".join(a["verb"] for a in actions).lower()
    check(actions, "the Trunk Tools deal yields at least one reported action")
    check("signing" in verbs or "completed" in verbs,
          "a present-progressive lede ('signing a deal') is a witnessed action")

    print("\n4. the hard rule's other half: characterisation is not action")
    actions, dropped = extract.reported_actions(
        "The contractor is embracing new ways of working across its sites. "
        "It has become a leader in modular construction across the region. "
        "Gilbane deployed a new warehouse management system across forty sites.")
    check(len(actions) == 1, "only the concrete action is admitted")
    check(len(dropped) == 2, "both characterisations are recorded, not silently dropped")
    check(actions and "deployed" in actions[0]["verb"], "and it is the right one")
    # A sentence carrying BOTH is admitted on its action, with the framing surfaced.
    mixed, _ = extract.reported_actions(
        "Gilbane is betting on artificial intelligence, signing a deal with Trunk Tools "
        "to deploy its AI chatbot on jobsites across the country.")
    check(len(mixed) == 1,
          "a lede that characterises AND reports a signed deal is admitted on the deal")
    check(mixed and mixed[0]["characterization_present"],
          "and the characterising framing is flagged, not hidden from the reviewer")

    print("\n5. a bare future is an intention, not a behaviour")
    actions, _ = extract.reported_actions(
        "Gilbane will deploy the platform next year and plans to migrate its ERP.")
    check(not actions, "'will deploy' / 'plans to' produce no buyer_acts row")

    print("\n6. Q&A transcripts (no quotation marks anywhere)")
    sp = extract.speakers_in_article(CONTECH, "Gilbane")
    check([s["name"] for s in sp] == ["Kelly Benedict"],
          "the interviewee is identified from 'the firm's head of innovation'")
    qa = extract.qa_passages(CONTECH, [s["name"] for s in sp])
    check(qa, "labelled answers are extracted despite there being no quote marks")
    check(all(p["name"] == "Kelly Benedict" for p in qa),
          "every passage is attributed to the identified speaker")
    joined = " ".join(p["text"] for p in qa)
    check("CONSTRUCTION DIVE" not in joined and "What do you do" not in joined,
          "the interviewer's question is NOT recorded as company speech")
    check("Recommended Reading" not in joined,
          "site furniture is cut -- a promoted headline is not the executive talking")
    check(not extract.qa_passages(CONTECH, []),
          "with no identified speaker, a transcript yields nothing")

    print("\n7. wire markers")
    check(extract.wire_verdict(TRUNK_TOOLS, "Gilbane bets on AI", "")[0] is False,
          "a bylined report that CITES a news release is not itself a reprint")
    check(extract.wire_verdict("CHICAGO /PRNewswire/ -- Acme today announced")[0],
          "a wire byline is conclusive alone")
    check(extract.wire_verdict(
        "Acme launched a platform. About Acme Corp: Acme is a leader. "
        "For more information, visit acme.com")[0],
        "boilerplate with no reporter byline routes to first-party")
    check(not extract.wire_verdict(
        "By Jane Smith, Senior Editor. Acme launched a platform. About Acme Corp: "
        "For more information, visit acme.com")[0],
        "the same boilerplate WITH a reporter byline does not -- outlets append it "
        "to genuine reporting routinely")
    check(not extract.wire_verdict(
        "By Jane Smith, Senior Editor. Gilbane rolls out Trunk Tools AI agents across "
        "its jobsites. Sponsored Content")[0],
        "an ad slot labelled 'Sponsored Content' does not route a bylined article to "
        "first-party -- every trade page carries one")
    check(extract.wire_verdict("Gilbane rolls out AI agents. Sponsored Content")[0],
          "the same label with no byline does route")

    print("\n8. article typing and the hard rule")
    check(extract.article_type("body", "t", "https://x.com/opinion/a", [], False)[0]
          == "ST-EXECCOLUMN", "an /opinion/ URL is a contributed column")
    check(extract.article_type("spoke on a panel", "t", "https://x.com/news/a", [], True)[0]
          == "ST-EXECPANEL", "spoken-remarks context caps at panel coverage")
    check(extract.article_type("plain report", "t", "https://x.com/news/a", [], True)[0]
          == "ST-EXECQUOTE-REPORTED", "an attributed quote in a report is the full-grade type")
    check(extract.article_type("plain report", "t", "https://x.com/news/a", [], False)[0]
          == "ST-PRESSPROFILE", "no attributable quote falls back to a profile")
    check(extract.ROLE_BY_TYPE["ST-PRESSPROFILE"] == "buyer_acts",
          "ST-PRESSPROFILE carries buyer_acts and there is no other value in the table")
    check(set(extract.ROLE_BY_TYPE.values()) == {"buyer_articulates", "buyer_acts"},
          "no trade-press type maps to provider_market_responds")
    check(extract.GRADE_BY_TYPE["ST-EXECPANEL"] == "C"
          and extract.GRADE_BY_TYPE["ST-EXECQUOTE-REPORTED"] == "B",
          "capped -1 is one grade below full")
    check("A" not in extract.GRADE_BY_TYPE.values(),
          "A is not reachable from a journalist-mediated source")

    print("\n9. the end-of-article marker (v1.8): every apostrophe form, and the markers the backspace bytes disabled")
    prose = ["Walbridge has rolled out a new estimating platform across its offices, the company said this week in a release.",
             "The contractor said the change would shorten preconstruction schedules on its larger federal projects this year."]
    teaser = "Colin Stoner, chief information officer for Novo Construction, describes how the firm uses artificial intelligence."
    for form in ("Editors\u2019 picks", "Editors' picks", "Editor's picks", "Editors picks", "EDITORS\u2019 PICKS",
                 "Filed Under:", "Filed Under: Commercial Building, Tech", "More from Construction Dive"):
        body = extract.article_body(prose + [form, teaser])
        check(teaser not in body and "estimating platform" in body, f"{form!r} ends the article body")
    for form in ("Editors\u2019 picks", "Editor's picks"):
        check(bool(extract._FOOTER_RE.search(form)), f"{form!r} is a footer phrase too")
    check(not re.search(r"(?i)editor.s picks", "Editors\u2019 picks"),
          "(the pre-v1.8 pattern `editor.s picks` missed Construction Dive's form -- the defect)")
    src = (Path(__file__).resolve().parents[2] / "harnesses" / "h_tradepress_01" / "extract.py").read_bytes()
    check(not [b for b in src if b < 32 and b not in (9, 10, 13)],
          "extract.py holds no control bytes (v1.7 stored backspaces where `\\b` was meant)")

    print(f"\n{PASSED} checks passed, {FAILED} failed.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
