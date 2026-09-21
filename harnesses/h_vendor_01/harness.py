"""
H-VENDOR-01 -- Vendor and partner disclosure (taxonomy family 6, extraction rules §24)
=====================================================================================

WHAT IT READS
-------------
Vendor-published customer pages -- case studies, customer stories, testimonials -- that
name one of the 108 buyer companies. It does not search for them: the seed list is the set
of vendor URLs H-EXECVOICE-01 EXCLUDED as `vendor_customer_content_family_6` while looking
for executive quotes (24 URLs as of 2026-09-03, logged rather than discarded for exactly
this build). A page that EXECVOICE excluded because a provider published it is not read
here either: `provider_published_family_6` is a provider's own service page, which is
H-SELLERCONTENT-01's material, not a customer disclosure.

THE THREE COMPONENTS OF ONE PAGE (§24.1)
----------------------------------------
    ST-VENDORDEPLOY   buyer_acts            a sentence that names the company and describes a
                                            deployment ("X implemented Y", "X rolled out Z").
                                            Named-customer deployment claims carry legal
                                            exposure, so this is the STRONGEST leg. Grade B.
    ST-VENDORQUOTE    buyer_articulates     a quoted passage attributed to a NAMED person with
                                            a title at the company (§24.2). Vendor marketing
                                            composes and clears these, so the grade is capped
                                            one step below a reported executive quote: C.
                                            Anonymous attributions are counted and dropped.
    ST-VENDORFRAMING  provider_market_responds
                                            the vendor's own framing of demand. COUNTED, NOT
                                            WRITTEN: Observations keys company_id to
                                            Companies, and the vendor is not a company in the
                                            sheet. Logged per page so the count is visible.

Themes come from the shared spine (core/topics.py, two-tier admission). A theme admitted on
the generic tier alone is written at low grade with the standard marker (convention 41).

WHAT IT REFUSES
---------------
* A seed page that is not about the company (H-FIRSTPARTY-01's identity test), recorded as
  `false_positive_rejected` -- EXECVOICE excluded the URL by its shape, not by reading it.
* Executive-data aggregators (appsruntheworld.com): undated profile pages, not vendor
  content; the session 10 allowlist scoping declined them as a reading source.
* A quote whose attribution names no person with a title, or a person whose attribution does
  not tie them to the company (wrong-speaker guard, convention 16's McGough lesson).
* Any URL its host's robots.txt disallows for this crawler.

ACCOUNTING (§24.3)
------------------
IC1 throughout. Volume, not widening: nothing here counts as progress against the
articulation-bias gap, and core/composition.py does not list this harness as a theme
instrument, so its silence licenses nothing.

    python harnesses/h_vendor_01/harness.py              # dry run
    python harnesses/h_vendor_01/harness.py --commit
    python harnesses/h_vendor_01/harness.py --offline    # replay archived pages
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import topics  # noqa: E402
from core.cache import DatedCache  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from core.resolution import STATE_NAMES, WEAK_TOKENS, state_code, tokens  # noqa: E402
from core.robots import RobotsGate  # noqa: E402
from core.search import host_of  # noqa: E402
from harnesses.h_execid_01.extract import html_lines  # noqa: E402
from harnesses.h_execid_01.source import SiteClient  # noqa: E402
from harnesses.h_firstparty_01.article import COMMON_WORD_NAMES, is_about_company  # noqa: E402

HARNESS_ID = "H-VENDOR-01"
HARNESS_NAME = "Vendor & Partner Disclosure Reader"
VERSION = "v1.2"
FAMILY = "6_vendor_partner_disclosure"
SIGNAL_DEPLOY = "vendor_case_study_deployment_fact"
SIGNAL_QUOTE = "vendor_case_study_buyer_quote"
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
SEED_GLOB = str(ROOT / "harness_output" / "H-EXECVOICE-01" / "run-*.json")

# Hosts EXECVOICE tagged as vendor content by URL shape that are not vendor content.
NOT_VENDOR_HOSTS = {"appsruntheworld.com": "executive_data_aggregator_not_vendor_content",
                    # v1.1: a business directory profile is not a vendor's customer page
                    # (EXECVOICE logged a dnb.com profile against Scentsy, 2026-09-06)
                    "dnb.com": "business_directory_not_vendor_content"}
# v1.1: a university or government page is never vendor content. v1.0 read a University of
# Michigan dyslexia-help "success story" about Suffolk's CEO as a vendor page because EXECVOICE
# tagged it by URL shape, and it counted toward an absence.
NOT_VENDOR_TLDS = {"edu": "university_page_not_vendor_content",
                   "gov": "government_page_not_vendor_content"}

DEPLOY_RE = re.compile(
    r"\b(implement\w*|deploy\w*|adopt\w*|roll(?:ed|ing|s)?\s+out|migrat\w*|standardi[sz]\w*|"
    r"went\s+live|go(?:es|ing)?\s+live|launch\w*|select\w*|chose|choosing|switch\w*|"
    r"replac\w*|upgrad\w*|leverag\w*|partner\w*\s+with|turned\s+to|us(?:e|es|ed|ing)\b)",
    re.I)
QUOTE_RE = re.compile(r"[“\"]([^”\"]{60,700})[”\"]")
TITLE_WORDS = (r"(?:Chief|Officer|Director|Manager|President|VP|Vice\s+President|CEO|CIO|"
               r"CTO|COO|CFO|Head|Lead|Superintendent|Engineer|Controller|Owner|Partner|"
               r"Founder|Principal|Executive|Supervisor|Coordinator|Analyst|Administrator)")
PERSON = r"([A-Z][a-z]+(?:\s+[A-Z][A-Za-z'\-]+){1,2})"
ATTRIB_RE = re.compile(
    rf"(?:said|says|explains?|explained|adds?|added|notes?|noted|according\s+to|[—–\-])"
    rf"\s*{PERSON},?\s+(?:the\s+|its\s+|who\s+is\s+)?([A-Za-z&/,\s]{{2,70}}?{TITLE_WORDS}[A-Za-z&/,\s]{{0,40}})")
FRAMING_RE = re.compile(
    r"\b(companies|manufacturers|contractors|fleets|distributors|organizations|firms|"
    r"carriers|builders|operators)\b.{0,90}\b(need|needs|struggl\w*|face|facing|are\s+looking|"
    r"challenge\w*|pressure\w*|can(?:no)?t\s+afford|must)\b", re.I)


def seeds() -> tuple[list[dict], list[dict]]:
    """(usable seeds, excluded seeds) from every EXECVOICE run log, deduped on (company, url)."""
    seen: set[tuple[str, str]] = set()
    use, excluded = [], []
    for path in sorted(glob.glob(SEED_GLOB)):
        try:
            log = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for e in log.get("excluded_vendor_urls") or []:
            # v1.1: "grantthornton.com" and "www.grantthornton.com" are one page
            key = (str(e["company_id"]), re.sub(r"^(https?://)www\.", r"\1", str(e["url"])))
            if key in seen:
                continue
            seen.add(key)
            # The normalised form is the DEDUPE key only. The first v1.1 dry run fetched the
            # stripped URL, and openspace.ai without www served a page that no longer read as
            # about Joeris -- the one page v1.0 had read correctly (convention 37).
            rec = {"company_id": key[0], "url": str(e["url"]), "execvoice_reason": e.get("reason"),
                   "seed_log": Path(path).name}
            host = host_of(key[1])
            base = ".".join(host.split(".")[-2:])
            tld = host.rsplit(".", 1)[-1]
            if e.get("reason") != "vendor_customer_content_family_6":
                rec["excluded"] = f"{e.get('reason')}: provider's own page, H-SELLERCONTENT-01 material"
                excluded.append(rec)
            elif base in NOT_VENDOR_HOSTS:
                rec["excluded"] = NOT_VENDOR_HOSTS[base]
                excluded.append(rec)
            elif tld in NOT_VENDOR_TLDS:
                rec["excluded"] = NOT_VENDOR_TLDS[tld]
                excluded.append(rec)
            else:
                use.append(rec)
    return use, excluded


MAX_SENTENCE_CHARS = 350

# v1.2 (session 17 wrap-up, Matthew's design): page chrome is removed before any sentence scan.
# Measured on the Ardoq / SpawGlass page: every theme-laden marketing line ("Govern and Leverage
# AI Effectively", "AI Lens", "AI Webinars", "ERP Transformation") sits inside <header>/<nav>,
# and the customer story sits inside <main>/<article>.
CHROME_RE = re.compile(r"(?is)<(nav|header|footer|aside)\b[^>]*>.*?</\1\s*>")


def strip_chrome(raw_html: str) -> str:
    """The page with navigation, header, footer and aside blocks removed (repeated, because a
    <nav> is usually nested inside a <header>)."""
    prev, out = None, raw_html or ""
    while prev != out:
        prev, out = out, CHROME_RE.sub(" ", out)
    return out


# True block-level elements only. An inline element (a, span, strong, em, b, i) is part of the
# running sentence: on the Ardoq page "They leveraged the <a><span>Microsoft Entra ID
# integration</span></a> (formerly known as Active Directory) ..." is ONE sentence, and
# H-EXECID-01's html_lines, which breaks at inline tags as well, cut it into three pieces once
# v1.2 started splitting sentences on line breaks (first v1.2 dry run, 2026-09-13).
_BLOCK_TAGS = re.compile(
    r"(?is)</?(?:p|li|ul|ol|h[1-6]|div|section|article|main|table|thead|tbody|tr|td|th|"
    r"blockquote|figure|figcaption|dl|dt|dd|br|hr|header|footer|nav|aside)\b[^>]*>")


def body_lines(raw_html: str) -> list[str]:
    """Visible text split at block boundaries only; inline markup is removed in place."""
    import html as _html
    t = re.sub(r"(?is)<(script|style|noscript|svg|template)\b.*?</\1>", " ", raw_html or "")
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = _BLOCK_TAGS.sub("\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t)
    return [ln for ln in (re.sub(r"[ \t\r\f\v\u00a0]+", " ", x).strip() for x in t.split("\n")) if ln]


def page_title(raw_html: str) -> str:
    """<title>, else og:title, else the first <h1>."""
    import html as _html
    for pattern in (r"(?is)<title[^>]*>(.*?)</title>", r'(?is)<meta[^>]+property="og:title"[^>]+content="([^"]*)"',
                    r"(?is)<h1[^>]*>(.*?)</h1>"):
        m = re.search(pattern, raw_html or "")
        if m:
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _html.unescape(m.group(1)))).strip()
            if t:
                return t
    return ""
NAV_RE = re.compile(
    r"(?i)(sign in|skip to|talk to an expert|read more|learn more|read story|show previous|"
    r"show next|dig deeper|case study\b|next article|previous article|most recent articles|"
    r"platform overview|privacy policy|terms of use|subscribe|cookie)")


def sentences(text: str) -> list[str]:
    """Prose sentences only. Navigation and card decks flatten into 'sentences' hundreds of
    characters long that mention the company, a product and a theme term all at once --
    the first dry run wrote two Joeris rows off exactly that (convention 16). A sentence
    is prose if it is short enough to be one and carries no navigation furniture."""
    out = []
    # v1.2: a line break is a boundary too. The chrome-free body keeps html_lines' block
    # breaks, so a heading with no full stop ("SpawGlass Builds a Cost-Efficient Future")
    # no longer fuses with the paragraph after it into one "sentence" that names the company
    # (caught by core/tests/test_vendor.py section 4 before the v1.2 run was read).
    for s in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = s.strip()
        if 30 < len(s) <= MAX_SENTENCE_CHARS and not NAV_RE.search(s):
            out.append(s)
    return out


def names_company(sentence: str, name: str) -> bool:
    """Does this sentence name the company?

    v1.0 demanded the full canonical string whenever the name had one long token, so
    "SpawGlass Holding" and "Melaleuca, Inc." were never found in sentences that say
    "SpawGlass" (10 on the Ardoq page) and "Melaleuca" (8 on the XCentium page): two of the
    six pages v1.0 read and called absent. Convention 31 is the actual rule: a COINED token
    stands alone; an ordinary word needs the full phrase. Page-level identity is decided
    separately (is_about_company plus corroborates_identity)."""
    distinct = [t for t in tokens(name) if len(t) > 2 and t not in WEAK_TOKENS]
    up = sentence.upper()
    if len(distinct) >= 2:
        return any(re.search(rf"\b{re.escape(t)}\b", up) for t in distinct)
    if len(distinct) == 1 and distinct[0].lower() not in COMMON_WORD_NAMES:
        return bool(re.search(rf"\b{re.escape(distinct[0])}\b", up))
    words = [w.upper() for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    if not words:
        return False
    phrase = r"[\s,.\-]*".join(re.escape(w) for w in words)
    return bool(re.search(rf"\b{phrase}\b", up))


_STATE_FULL = {}
for _full, _code in STATE_NAMES.items():
    if len(_full) > 4:
        _STATE_FULL.setdefault(_code, _full)


def corroborates_identity(raw_html: str, text: str, company: dict) -> tuple[bool, str]:
    """v1.1 identity gate for a name that reduces to ONE distinctive token.

    v1.0 accepted Autodesk's story about GRAHAM, the UK and Ireland contractor, as evidence
    about Graham Construction of Omaha (grahambuilds.com): the token and even "GRAHAM
    Construction" were on the page. A single token on a third-party page is not an identity
    unless the page also carries something only this company has: its website domain, its
    HQ city, or its HQ state. Measured on the six v1.0 pages: SpawGlass (domain, Texas),
    Joeris (San Antonio, Texas), PENTA (Las Vegas) pass; the UK GRAHAM page carries none and
    is refused. Cost, stated: XCentium's genuine Melaleuca page carries none either and is
    refused too. An identity gate, so it refuses rather than writing low-grade (convention 41).
    Names with two or more distinctive tokens are not gated here."""
    name = company["canonical_name"]
    distinct = [t for t in tokens(name) if len(t) > 2 and t not in WEAK_TOKENS]
    if len(distinct) >= 2:
        return True, "multi-token name"
    hq = str(company.get("hq_state") or "")
    st = state_code(hq)
    city = hq.split(",")[0].strip() if "," in hq else ""
    domain = re.sub(r"^https?://(www\.)?", "", str(company.get("website") or "")).strip("/").lower()
    low = text.lower()
    if domain and domain in (raw_html or "").lower():
        return True, f"website domain {domain} on page"
    if city and re.search(rf"\b{re.escape(city.lower())}\b", low):
        return True, f"HQ city {city} on page"
    full = _STATE_FULL.get(st, "")
    if full and re.search(rf"\b{re.escape(full.lower())}\b", low):
        return True, f"HQ state {full.title()} on page"
    return False, (f"one distinctive token ({distinct[0] if distinct else name}) and no corroborator "
                   f"on the page: no {domain or 'website'}, no {city or 'HQ city'}, no "
                   f"{full.title() or 'HQ state'}")


def company_near(text: str, pos: int, name: str, radius: int = 300) -> bool:
    return names_company(text[max(0, pos - radius): pos + radius], name)


# "said senior project manager JB Peel" / "says CIO Jane Doe" -- verb, lowercase title, Name
ATTRIB_TITLE_FIRST_RE = re.compile(
    rf"(?:said|says|explains?|explained|adds?|added|notes?|noted|according\s+to)\s+"
    rf"(?:the\s+|its\s+)?((?:[a-z][a-z&/\-]*\s+){{0,5}}(?:{TITLE_WORDS.lower()}|"
    rf"{TITLE_WORDS})(?:\s+[a-z][a-z&/\-]*){{0,4}})\s+{PERSON}", re.I)
# "Moreno said" / "said Peel" -- a surname alone, resolved against a speaker the page has
# already introduced with a title
SURNAME_SAID_RE = re.compile(r"(?:\b([A-Z][a-z]+)\s+(?:said|says|added|explained|noted)\b|"
                             r"\b(?:said|says|added|explained|noted)\s+([A-Z][a-z]+)\b)")


def speakers_on_page(text: str) -> dict[str, tuple[str, int]]:
    """{surname: (full name, position)} for every person the page attributes with a title,
    in either order ("said title Name" or "Name, Title")."""
    out: dict[str, tuple[str, int]] = {}
    for m in ATTRIB_TITLE_FIRST_RE.finditer(text):
        title, person = " ".join(m.group(1).split()), m.group(2)
        if plausible(person, title):
            out.setdefault(person.split()[-1], (f"{person} ({title})", m.start()))
    for m in ATTRIB_RE.finditer(text):
        person, title = m.group(1), " ".join(m.group(2).split())
        if plausible(person, title):
            out.setdefault(person.split()[-1], (f"{person} ({title})", m.start()))
    return out


def plausible(person: str, title: str) -> bool:
    """A headline fragment is not a speaker. H-EXECID-01's name test (stopwords, function
    words, shape) plus a title that reads as a label: the first run named a speaker
    'Efficient Future (by Mapping Its Technology Landscape Executive)'."""
    from harnesses.h_execid_01.extract import looks_like_name
    return looks_like_name(person) and 1 <= len(title.split()) <= 7 and len(title) <= 60


def attribute(text: str, quote_end: int, quote_start: int, speakers: dict) -> str | None:
    """Named speaker with title for the quote ending at quote_end, or None (anonymous)."""
    window = text[quote_end: quote_end + 220]
    before = text[max(0, quote_start - 120): quote_start]
    for chunk in (window, before):
        m = ATTRIB_TITLE_FIRST_RE.search(chunk)
        if m and plausible(m.group(2), " ".join(m.group(1).split())):
            return f"{m.group(2)} ({' '.join(m.group(1).split())})"
        m = ATTRIB_RE.search(chunk)
        if m and plausible(m.group(1), " ".join(m.group(2).split())):
            return f"{m.group(1)} ({' '.join(m.group(2).split())})"
    m = SURNAME_SAID_RE.search(window[:80])
    if m:
        surname = m.group(1) or m.group(2)
        if surname in speakers:
            return speakers[surname][0]
    return None


def theme_hits(text: str) -> dict:
    """{theme_key: (hits, tier)} through the shared two-tier spine."""
    return topics.classify_tiered(text)


def build(company: dict, theme_key: str, role: str, signal: str, passages: list[str],
          speaker: str, url: str, stamp: str, tier: str, hits: list[str],
          attributed: bool = False) -> Observation:
    theme = topics.THEMES_BY_KEY[theme_key]
    name = company["canonical_name"]
    low = tier != "strong"
    if signal == SIGNAL_DEPLOY:
        text = (f"{name} is described on a vendor-published customer page as having deployed "
                f"or adopted technology bearing on {theme.label} ({len(passages)} passage(s)). "
                f"A named-customer deployment claim by the vendor; the vendor is the interested "
                f"party (IC1), and the fact is checkable rather than the framing.")
        grade, conf, strength, state = "B", 0.5, "weak_clue", "active_transition"
        excerpt = " | ".join(p[:300] for p in passages[:3])
        if attributed:
            # v1.2: no passage names the company; each is attributed to it because the page is
            # a single-customer story whose TITLE names the company, and the sentence was read
            # from the page body with navigation, header and footer removed. Weaker identity
            # than a named sentence, so lower confidence, and the text says so.
            text = (f"{name} is the subject of a vendor-published customer page (named in its title) "
                    f"whose body describes a deployment bearing on {theme.label} ({len(passages)} "
                    f"passage(s)) without naming the company in the sentence. Attributed by page "
                    f"subject; the vendor is the interested party (IC1).")
            conf = 0.4
            excerpt = "[page-subject attribution: company in page title; sentence does not name it] " + excerpt
    else:
        text = (f"{speaker} of {name} is quoted on a vendor-published customer page articulating "
                f"{theme.label} ({len(passages)} passage(s)). Vendor marketing composes and "
                f"clears such quotes, so this is graded one step below a reported executive "
                f"quote (§24.1) and records what the page attributes, not a verified statement.")
        grade, conf, strength, state = "C", 0.45, "weak_clue", "unknown"
        excerpt = " | ".join(f'{speaker}: "{p[:280]}"' for p in passages[:3])
    excerpt += f" | matched: {', '.join(sorted(set(hits))[:8])}"
    if low:
        grade, conf = topics.LOW_GRADE, topics.LOW_GRADE_CONFIDENCE
        excerpt = topics.low_grade_excerpt(
            f"generic-tier theme term(s) only: {', '.join(sorted(set(hits))[:4])}; "
            f"corroboration-strength gate relaxed 2026-09-06 (H-VENDOR-01 v1.0)", excerpt)
    return Observation(
        company_id=company["company_id"], evidence_family=FAMILY, evidence_role=role,
        topic=theme_key, organizational_state=state, signal_strength=strength,
        observation_text=text, evidence_excerpt=excerpt[:2000], source_url=url,
        publication_date="", retrieval_date=stamp, source_grade=grade,
        harness_id=HARNESS_ID, harness_version=VERSION, confidence_0_1=conf)


def read_page(text: str, company: dict, url: str, stamp: str, entry: dict,
              subject: bool = False) -> list[Observation]:
    """`text` is the page body with chrome removed (v1.2). `subject` is True only when the page
    title names the company; then a deployment sentence that does not name it is attributed."""
    name = company["canonical_name"]
    out: list[Observation] = []
    # ---- deployment facts ----
    by_theme: dict[str, tuple[list, list, str]] = {}
    named_any: dict[str, bool] = {}
    attributed_sentences = 0
    for s in sentences(text):
        if not DEPLOY_RE.search(s):
            continue
        named = names_company(s, name)
        if not named and not subject:
            continue
        themed = theme_hits(s)
        if themed and not named:
            attributed_sentences += 1
        for tk, (hits, tier) in themed.items():
            named_any[tk] = named_any.get(tk, False) or named
            cur = by_theme.setdefault(tk, ([], [], "weak"))
            cur[0].append(s)
            cur[1].extend(hits)
            if tier == "strong":
                by_theme[tk] = (cur[0], cur[1], "strong")
    for tk, (passages, hits, tier) in by_theme.items():
        out.append(build(company, tk, "buyer_acts", SIGNAL_DEPLOY, passages, "", url, stamp,
                         tier, hits, attributed=not named_any.get(tk, False)))
    entry["deploy_sentences"] = sum(len(v[0]) for v in by_theme.values())
    entry["deploy_sentences_attributed_by_title"] = attributed_sentences
    # ---- quotes (§24.2 attribution gate) ----
    quotes_by: dict[tuple[str, str], tuple[list, list, str]] = {}
    anonymous, unconfirmed, unthemed = 0, 0, 0
    speakers = speakers_on_page(text)
    for m in QUOTE_RE.finditer(text):
        q = m.group(1).strip()
        if len(q) > 700 or NAV_RE.search(q):
            continue
        person = attribute(text, m.end(), m.start(), speakers)
        if not person:
            anonymous += 1
            continue
        # Wrong-speaker guard: the person must be tied to the company somewhere near where
        # the page attributes them, not merely present on a page about the company.
        surname = person.split(" (")[0].split()[-1]
        intro_pos = speakers.get(surname, ("", m.end()))[1]
        if not (company_near(text, m.end(), name) or company_near(text, intro_pos, name)):
            unconfirmed += 1
            continue
        th = theme_hits(q)
        if not th:
            unthemed += 1
            continue
        for tk, (hits, tier) in th.items():
            cur = quotes_by.setdefault((tk, person), ([], [], "weak"))
            cur[0].append(q)
            cur[1].extend(hits)
            if tier == "strong":
                quotes_by[(tk, person)] = (cur[0], cur[1], "strong")
    entry["quotes_named_but_unthemed"] = unthemed
    entry["speakers_named_on_page"] = sorted(v[0] for v in speakers.values())
    for (tk, person), (passages, hits, tier) in quotes_by.items():
        out.append(build(company, tk, "buyer_articulates", SIGNAL_QUOTE, passages, person, url,
                         stamp, tier, hits))
    entry["quotes_anonymous_dropped"] = anonymous
    entry["quotes_speaker_unconfirmed_dropped"] = unconfirmed
    entry["quotes_written"] = len(quotes_by)
    # ---- vendor framing: counted, not written ----
    entry["framing_sentences_counted_not_written"] = sum(1 for s in sentences(text)
                                                         if FRAMING_RE.search(s))
    return out


def main() -> int:
    # Session 15: a Windows console defaults to cp1252, and one search-error string carrying
    # U+FFFD killed a 79-company live run at company 68 with UnicodeEncodeError. Output is
    # never worth a crash; replace what the console cannot show.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=f"{HARNESS_ID} -- {HARNESS_NAME}")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--companies")
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--show-rows", action="store_true",
                    help="print every proposed row in full, for reading before a commit")
    args = ap.parse_args()

    db = MarketIntelDB()
    companies = {c["company_id"]: c for c in db.companies()
                 if c.get("qualification_status") != "provider_benchmark"}
    use, excluded = seeds()
    if args.companies:
        want = {c.strip() for c in args.companies.split(",")}
        use = [s for s in use if s["company_id"] in want]
    by_company: dict[str, list[dict]] = {}
    for s in use:
        if s["company_id"] in companies:
            by_company.setdefault(s["company_id"], []).append(s)

    stamp = today()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = DatedCache(OUTPUT_DIR / "raw" / "pages", offline=args.offline,
                       retrieval_date=stamp, pause_seconds=args.pause)
    client = SiteClient(pages)
    gate = RobotsGate()
    scope = [(cid, sig) for cid in by_company for sig in (SIGNAL_DEPLOY, SIGNAL_QUOTE)]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=FAMILY, scope=scope,
                      signal_families={SIGNAL_DEPLOY: FAMILY, SIGNAL_QUOTE: FAMILY},
                      commit=args.commit)
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp, "offline": args.offline,
           "seed_count": len(use), "seeds_excluded": excluded, "companies": []}
    proposed: list[Observation] = []
    print(f"{HARNESS_ID} {VERSION} -- {len(by_company)} companies from {len(use)} seed URL(s) "
          f"({len(excluded)} seed(s) excluded) ({'offline' if args.offline else 'live'})\n")

    for cid, seed_list in sorted(by_company.items()):
        company = companies[cid]
        name = company["canonical_name"]
        entry = {"company_id": cid, "name": name, "pages": []}
        rows: list[Observation] = []
        read_ok, not_about, fetch_fail, robots_block, js_gap = 0, 0, 0, 0, 0
        for seed in seed_list:
            url = seed["url"]
            page_entry = {"url": url}
            allowed, why = gate.check(url) if not args.offline else (True, "")
            if not allowed:
                robots_block += 1
                page_entry["rejected"] = f"robots: {why}"
                entry["pages"].append(page_entry)
                continue
            page = client.get(url)
            if not page.ok:
                fetch_fail += 1
                page_entry["rejected"] = f"fetch {page.status}: {page.error[:100]}"
                entry["pages"].append(page_entry)
                continue
            text = " ".join(html_lines(page.html))
            about, about_why = is_about_company(text, name)
            if not about:
                not_about += 1
                page_entry["rejected"] = f"not_about_company: {about_why}"
                entry["pages"].append(page_entry)
                continue
            ok_id, id_why = corroborates_identity(page.html, text, company)
            if not ok_id:
                not_about += 1
                page_entry["rejected"] = f"identity_uncorroborated: {id_why}"
                entry["pages"].append(page_entry)
                continue
            page_entry["identity"] = id_why
            if not any(names_company(sn, name) for sn in sentences(text)):
                # v1.1: the page is about the company by its title and header but carries no
                # prose sentence naming it -- Autodesk's PENTA story, whose body is loaded
                # client-side (13 mentions, all in the header and meta tags). Nothing was read,
                # so nothing may be called absent.
                js_gap += 1
                page_entry["rejected"] = ("retrieval_gap: page passes identity but no prose sentence "
                                          "names the company (body not in the served HTML)")
                entry["pages"].append(page_entry)
                continue
            read_ok += 1
            title = page_title(page.html)
            subject = bool(title) and names_company(title, name)
            body = "\n".join(body_lines(strip_chrome(page.html)))
            page_entry["title"] = title[:200]
            page_entry["subject_in_title"] = subject
            found = read_page(body, company, url, stamp, page_entry, subject=subject)
            page_entry["observations"] = len(found)
            rows.extend(found)
            entry["pages"].append(page_entry)

        n_seed = len(seed_list)
        for sig, role in ((SIGNAL_DEPLOY, "buyer_acts"), (SIGNAL_QUOTE, "buyer_articulates")):
            mine = [o for o in rows if o.evidence_role == role]
            if mine:
                run.attempt(cid, sig, outcome="covered", records_written=len(mine),
                            source_url_attempted=mine[0].source_url,
                            candidates_evaluated=n_seed, candidates_discarded=n_seed - read_ok)
            elif read_ok:
                run.attempt(cid, sig, outcome="absent_confirmed",
                            source_url_attempted=seed_list[0]["url"],
                            candidates_evaluated=n_seed, candidates_discarded=n_seed - read_ok)
            elif js_gap and not fetch_fail:
                run.attempt(cid, sig, outcome="not_covered", failure_stage="fetch",
                            failure_category="js_rendered_unreachable", fix_class="source_limitation",
                            failure_detail=f"{js_gap} seed page(s) pass identity but serve no prose naming "
                                           f"the company (body rendered client-side); {not_about} not "
                                           f"about the company, {robots_block} robots-refused",
                            source_url_attempted=seed_list[0]["url"],
                            candidates_evaluated=n_seed, candidates_discarded=n_seed)
            elif robots_block and not fetch_fail and not not_about:
                run.attempt(cid, sig, outcome="not_covered", failure_stage="fetch",
                            failure_category="access_blocked", fix_class="source_limitation",
                            failure_detail="every seed URL's host disallows this crawler by robots.txt",
                            source_url_attempted=seed_list[0]["url"],
                            candidates_evaluated=n_seed, candidates_discarded=n_seed)
            elif not_about and not fetch_fail:
                run.attempt(cid, sig, outcome="not_covered", failure_stage="entity_resolution",
                            failure_category="false_positive_rejected", fix_class="source_limitation",
                            failure_detail="seed page(s) are not about this company under the "
                                           "first-party identity test; EXECVOICE excluded them by "
                                           "URL shape, not by reading them",
                            source_url_attempted=seed_list[0]["url"],
                            candidates_evaluated=n_seed, candidates_discarded=n_seed)
            else:
                run.attempt(cid, sig, outcome="not_covered", failure_stage="fetch",
                            failure_category="source_unavailable", fix_class="transient",
                            failure_detail=f"{fetch_fail} seed fetch(es) failed, {not_about} not "
                                           f"about the company, {robots_block} robots-refused",
                            source_url_attempted=seed_list[0]["url"],
                            candidates_evaluated=n_seed, candidates_discarded=n_seed)
        proposed.extend(rows)
        entry["observations"] = len(rows)
        mark = "ok" if rows else ("00" if read_ok else "--")
        print(f"  [{mark}] {cid} {name}: {n_seed} seed(s), {read_ok} read, {len(rows)} observation(s)")
        log["companies"].append(entry)

    if args.show_rows:
        for o in proposed:
            print()
            print(f"  ---- {o.company_id} {o.topic} {o.evidence_role} grade={o.source_grade} conf={o.confidence_0_1}")
            print(f"  TEXT: {o.observation_text}")
            print(f"  EXCERPT: {o.evidence_excerpt}")
            print(f"  URL: {o.source_url}")
    report = db.sync_observations(proposed)
    run.observations_written = report.written
    summary = run.close()
    print(f"\n  {len(by_company)} companies - {len(proposed)} observations - "
          f"{pages.fetch_count} page fetches")
    print(f"  coverage {summary['coverage_rate']:.0%} ({summary['attempts_covered']} covered, "
          f"{summary['attempts_absent_confirmed']} absent_confirmed, "
          f"{summary['attempts_not_covered']} not_covered)")
    print(f"  dedupe: {report.summary()}")
    framing = sum(p.get("framing_sentences_counted_not_written", 0)
                  for e in log["companies"] for p in e["pages"])
    anon = sum(p.get("quotes_anonymous_dropped", 0) for e in log["companies"] for p in e["pages"])
    print(f"  vendor framing sentences counted, not written (no provider entity): {framing}; "
          f"anonymous quotes dropped (§24.2): {anon}")
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")
    log["summary"] = summary
    log["dedupe"] = report.summary()
    log["held"] = report.conflicts
    path = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
    path.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    if args.commit:
        db.save()
        print(f"  committed to market_intel_db.xlsx ({summary['run_id']})")
    else:
        print("  DRY RUN -- nothing written. Re-run with --commit to write.")
    print(f"  run log: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
