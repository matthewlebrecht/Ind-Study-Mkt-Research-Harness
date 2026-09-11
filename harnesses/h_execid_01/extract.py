"""
Name/title extraction from a leadership page, and title normalization.

THIS MODULE IS WHERE THIS HARNESS IS MOST LIKELY TO GO WRONG
------------------------------------------------------------
Convention 16 names the projects characteristic failure: a loose pattern does not merely
add noise, it manufactures confidence. That failure has landed three times already (the
Infor substring bug, the Wayback dated-news false positives, the SellerContent homepage
substitutes). Free-text name extraction off arbitrary marketing HTML is a richer
opportunity for it than any of those, because a plausible-looking wrong name is
indistinguishable from a right one downstream.

The specific downstream risk is concrete rather than abstract. H-EXECID-01 exists to feed
H-EXECVOICE-01, which will search the open web for what these people have said. A
fabricated or misattributed executive sends that harness looking for a person who does not
hold that job, and whatever it finds gets written into the evidence base as buyer
articulation. That is manufactured evidence, not a gap.

So extraction here is deliberately conservative in three ways:

1. **A record requires BOTH a well-formed personal name AND a recognised title**, adjacent
   to each other in the document. Neither alone is enough. A page listing names with no
   titles yields nothing; a page listing titles with no names yields nothing.

2. **Titles are matched against a closed vocabulary**, not a keyword sniff. `TITLE_RULES`
   is an ordered list of anchored patterns. Something that does not match is `other`, and
   `other` never becomes a primary-relevance record.

3. **Everything rejected is counted and sampled into the run log.** A refusal is a claim
   about the source and must be checkable afterwards (convention 12). `Extraction.rejected`
   carries why each candidate was dropped, so a reviewer can see whether the extractor was
   being appropriately strict or was silently eating a whole page.

THE THREE LAYOUTS THIS RECOGNISES
---------------------------------
Calibrated against real pages rather than guessed. The dominant layout by a wide margin is
a name on its own line followed immediately by a title on its own line (Midmark, and most
CMS leadership templates render this way once block tags become line breaks):

    Jon Wells
    President and CEO
    Jon Wells is the President and CEO of Midmark Corporation, a leader in ...

The inverse (title first) and the single-line joined form (`Name, Title` / `Name - Title`)
also occur and are handled. Prose *about* an executive -- the third line above -- is
excluded by a length ceiling plus a sentence test, because it names the same person and
would otherwise double-count them with a mangled title.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

# A title line is a label, not a sentence. Real ones are short; prose that happens to
# contain a title runs long. Calibrated on observed pages: genuine title lines ran 3-62
# chars, the shortest prose sentence containing a title ran 64.
MAX_TITLE_CHARS = 90
MAX_NAME_CHARS = 48

# Tokens that disqualify a line from being a personal name. These are the words that show
# up in navigation, section headers and company names -- the places a naive extractor
# harvests garbage from.
NAME_STOPWORDS = {
    "INC", "LLC", "LTD", "CORP", "CORPORATION", "COMPANY", "COMPANIES", "GROUP",
    "HOLDINGS", "PARTNERS", "ASSOCIATES", "ENTERPRISES", "INDUSTRIES", "SERVICES",
    "SOLUTIONS", "SYSTEMS", "TEAM", "LEADERSHIP", "MANAGEMENT", "EXECUTIVE", "BOARD",
    "DIRECTORS", "OFFICERS", "ABOUT", "CONTACT", "CAREERS", "HOME", "NEWS", "BLOG",
    "PRIVACY", "POLICY", "TERMS", "LOGIN", "SEARCH", "MENU", "SHARE", "READ", "MORE",
    "VIEW", "LEARN", "OUR", "OUR TEAM", "MEET", "STAFF", "PEOPLE", "HISTORY", "MISSION",
    "VALUES", "SERVICE", "PRODUCTS", "PROJECTS", "LOCATIONS", "SAFETY", "QUALITY",
    "CONSTRUCTION", "LOGISTICS", "TRANSPORT", "TRANSPORTATION", "MANUFACTURING",
    "ALL", "RIGHTS", "RESERVED", "COPYRIGHT", "EMAIL", "PHONE", "ADDRESS", "LINKEDIN",
    "FACEBOOK", "TWITTER", "YOUTUBE", "INSTAGRAM", "SKIP", "CONTENT", "NAVIGATION",
    # Governance-document nouns. A corporate-governance page is a list of PDF titles, and
    # "Corporate Governance Guidelines" is three capitalised tokens that satisfies the
    # name pattern exactly. Merit Medical produced precisely that as an executive, titled
    # from the adjacent link "Code of Ethics for CEO & Senior Officers" -- and because the
    # governance page then held more apparent people than the real /about/executives page,
    # it won the page-ranking too. One bad name displaced the entire correct roster.
    "CORPORATE", "GOVERNANCE", "GUIDELINES", "GUIDELINE", "CODE", "ETHICS", "CHARTER",
    "COMMITTEE", "COMPLIANCE", "POLICIES", "BYLAWS", "AUDIT", "REPORT", "REPORTS",
    "PLAN", "PROGRAM", "STATEMENT", "NOTICE", "DISCLOSURE", "INVESTOR", "INVESTORS",
    "ANNUAL", "PROXY", "FILINGS", "CONDUCT", "WHISTLEBLOWER", "NOMINATING", "COMPENSATION",
}

# Capitalised English function words and imperative verbs. A heading fragment like
# "How We" satisfies every structural test for a two-token personal name -- two
# capitalised tokens, no stopword, no digits -- and the Kenco About page duly produced
# "How We" as an executive titled "President and CEO" during calibration.
#
# That is convention 16 in miniature and it is why this set exists: the pattern was not
# noisy, it was confidently wrong, and it would have sent H-EXECVOICE-01 searching the
# open web for the public statements of a person named How We. Personal names essentially
# never contain these words, so rejecting any candidate containing one costs nothing real.
FUNCTION_WORDS = {
    "HOW", "WE", "OUR", "THE", "WHAT", "WHY", "WHEN", "WHERE", "WHO", "WHICH", "THIS",
    "THAT", "THESE", "THOSE", "WITH", "YOUR", "YOU", "IT", "ITS", "IN", "ON", "AT", "FOR",
    "AND", "OR", "BUT", "IF", "SO", "AS", "BY", "TO", "FROM", "OF", "IS", "ARE", "WAS",
    "WERE", "BE", "BEEN", "HAS", "HAVE", "HAD", "DO", "DOES", "DID", "CAN", "WILL",
    "EVERY", "MORE", "MOST", "LEARN", "GET", "READ", "SEE", "VIEW", "CONTACT", "JOIN",
    "FIND", "LET", "MAKE", "BUILD", "MEET", "NEW", "NOW", "HERE", "THERE", "WHY", "LET",
    "WORK", "WORKS", "WORKING", "BUILDING", "MOVING", "DRIVEN", "TRUSTED", "PROVEN",
    "TOGETHER", "BEYOND", "ABOVE", "FIRST", "NEXT", "ONE", "TWO", "YEARS", "YEAR",
    "TODAY", "TOMORROW", "FUTURE", "STORY", "STORIES", "CASE", "STUDY", "STUDIES",
    # Articles and imperative verbs, added after Rycon produced an executive named
    # "Become An" from the call-to-action heading "Become An Employee-Owner".
    "A", "AN", "BECOME", "BECOMING", "DISCOVER", "EXPLORE", "START", "BEGIN", "CREATE",
    "DESIGN", "DELIVER", "DELIVERING", "SERVE", "SERVING", "GROW", "GROWING", "PARTNER",
    "PARTNERING", "SUPPORT", "CHOOSE", "REQUEST", "SUBMIT", "DOWNLOAD", "SUBSCRIBE",
    "FOLLOW", "SHOP", "CALL", "CLICK", "CONTINUE", "CONTINUING", "CONNECT", "APPLY",
}

# Credential and generational suffixes that legitimately trail a name.
NAME_SUFFIX = re.compile(
    r",?\s+(?:M\.?D\.?|Ph\.?D\.?|D\.?O\.?|J\.?D\.?|C\.?P\.?A\.?|P\.?E\.?|R\.?N\.?|"
    r"MBA|CFA|PMP|Esq\.?|Jr\.?|Sr\.?|II|III|IV)\.?$", re.I)

# One name token: capitalised, allowing McDonald, O'Brien, Jean-Luc, and bare initials.
# `[a-z]*` rather than `[a-z]+` on the stem so O'Brien parses: the stem is the bare "O"
# and the apostrophe group carries "Brien". With `+` the whole name was rejected.
_TOKEN = r"(?:[A-Z][a-z]*(?:['’\-][A-Z]?[a-z]+)*|[A-Z]\.?|(?:Mc|Mac|De|Van|Von|Der|La|Le|Di|Du)[A-Z][a-z]+)"
NAME_RE = re.compile(rf"^{_TOKEN}(?:\s+{_TOKEN}){{1,3}}$")

# Giveaways that a line is prose about a person rather than a title label.
PROSE_MARKERS = re.compile(
    r"(?i)\b(is the|is our|was the|has been|joined|serves as|leads the|brings|holds a|"
    r"received|earned|graduated|oversees|began|started|prior to|before joining|"
    r"responsible for|he |she |they |his |her |their )")

# Giveaways that a line naming a role is a DOCUMENT title rather than a persons title.
# A corporate-governance page links "Code of Ethics for CEO and Senior Officers" and
# "Audit Committee Charter"; both contain a recognised title token and neither describes
# anyone. Convention 16 again: the match is real, the inference from it is not.
DOCUMENT_MARKERS = re.compile(
    r"(?i)\b(code of|guidelines?|charter|policy|policies|bylaws?|committee|"
    r"plan document|terms of|statement of|report|agreement|disclosure|form \d|"
    r"certificate|amendment)\b")

# --------------------------------------------------------------------------------------
# Title vocabulary.
#
# Ordered: the first rule that matches wins, so more specific patterns precede general
# ones ("Chief Operating Officer" before a bare "Operations" rule). Each entry is
# (normalized_key, role_relevance, pattern).
#
# `role_relevance` implements the title filter session2_priority_order.md specifies --
# CEO / COO / CIO-CTO / VP Ops / Supply Chain / Manufacturing -- as `primary`. Other
# C-suite roles are kept as `secondary` rather than discarded: they are cheap to record
# while the page is already open, they establish that the extractor read a real leadership
# page, and a CFO or Chief Transformation Officer is a plausible source of modernization
# articulation even though they are not on the primary list. Nothing outside `primary` is
# a search target for H-EXECVOICE-01 without a deliberate widening.
# --------------------------------------------------------------------------------------
TITLE_RULES: list[tuple[str, str, re.Pattern]] = [
    ("ceo", "primary", re.compile(
        r"(?i)\b(chief executive officer|CEO)\b")),
    ("coo", "primary", re.compile(
        r"(?i)\b(chief operating officer|chief operations officer|COO)\b")),
    ("cio_cto", "primary", re.compile(
        r"(?i)\b(chief information officer|chief technology officer|"
        r"chief digital officer|chief information and technology officer|"
        r"chief technical officer|CIO|CTO|CDO)\b")),
    ("chief_transformation", "primary", re.compile(
        r"(?i)\bchief (transformation|innovation|supply chain|manufacturing|"
        r"operating and technology) officer\b")),
    ("vp_operations", "primary", re.compile(
        r"(?i)\b((?:senior |executive |group |corporate |global )?"
        r"(?:vice president|VP|SVP|EVP|director)\s*(?:of |for |[,\-–—:|]\s*)*"
        r"(?:\w+ ){0,2}operations?)\b")),
    ("vp_supply_chain", "primary", re.compile(
        r"(?i)\b((?:senior |executive |group |corporate |global )?"
        r"(?:vice president|VP|SVP|EVP|director)\s*(?:of |for |[,\-–—:|]\s*)*"
        r"(?:\w+ ){0,2}(?:supply chain|logistics|procurement|distribution))\b")),
    ("vp_manufacturing", "primary", re.compile(
        r"(?i)\b((?:senior |executive |group |corporate |global )?"
        r"(?:vice president|VP|SVP|EVP|director)\s*(?:of |for |[,\-–—:|]\s*)*"
        r"(?:\w+ ){0,2}(?:manufacturing|production|engineering|"
        r"continuous improvement))\b")),
    ("vp_it", "primary", re.compile(
        r"(?i)\b((?:senior |executive |group |corporate |global )?"
        r"(?:vice president|VP|SVP|EVP|director)\s*(?:of |for |[,\-–—:|]\s*)*"
        r"(?:information technology|IT|technology|digital|systems|"
        r"information systems))\b")),
    ("president", "primary", re.compile(
        r"(?i)^(?:group |division |corporate |company )?president\b")),
    ("cfo", "secondary", re.compile(
        r"(?i)\b(chief financial officer|CFO)\b")),
    ("owner_founder", "secondary", re.compile(
        # `owner` is anchored to exclude "Employee-Owner", which is an ownership *model*
        # a construction firm advertises on a recruiting banner, not a job title. Rycon
        # produced "Become An / Employee-Owner" as an executive record on that match.
        r"(?i)\b(founder|co-founder|(?<!employee[- ])owner|chairman|chairwoman|"
        r"chair of the board|managing partner|managing director|principal)\b")),
    ("other_chief", "secondary", re.compile(
        r"(?i)\bchief [a-z ]{3,30}officer\b")),
    ("other_vp", "secondary", re.compile(
        r"(?i)\b(vice president|VP|SVP|EVP)\b")),
]


def normalize_title(raw: str) -> tuple[str, str]:
    """Map a raw title string to (normalized_key, role_relevance).

    Returns ("other", "excluded") when nothing in the closed vocabulary matches. That is
    the honest answer and it is load-bearing: an unmatched title must not be quietly
    promoted into a relevance class it did not earn.
    """
    for key, relevance, rx in TITLE_RULES:
        if rx.search(raw):
            return key, relevance
    return "other", "excluded"


def looks_like_title(line: str) -> bool:
    """True when a line reads as a job-title label rather than prose or a heading."""
    if not line or len(line) > MAX_TITLE_CHARS:
        return False
    if PROSE_MARKERS.search(line) or DOCUMENT_MARKERS.search(line):
        return False
    # A trailing period on a short line is almost always a sentence fragment, and a
    # question mark or a URL is never a title.
    if line.endswith(".") or "?" in line or "http" in line.lower():
        return False
    key, _ = normalize_title(line)
    return key != "other"


def title_shaped(line: str) -> bool:
    """A short label-shaped line -- everything looks_like_title() checks EXCEPT the closed
    vocabulary. Session 14 (E26): the line under a name that reads "Director of Fleet
    Analytics" is a title in every respect but membership in TITLE_RULES."""
    if not line or len(line) > MAX_TITLE_CHARS:
        return False
    if PROSE_MARKERS.search(line) or DOCUMENT_MARKERS.search(line):
        return False
    if line.endswith(".") or "?" in line or "http" in line.lower():
        return False
    return bool(re.search(r"[A-Za-z]", line)) and len(line.split()) <= 8


def looks_like_name(line: str, company_tokens: set[str] | None = None) -> bool:
    """True when a line is plausibly one persons name and nothing else."""
    if not line or len(line) > MAX_NAME_CHARS:
        return False
    candidate = NAME_SUFFIX.sub("", line).strip().strip(",")
    if not NAME_RE.match(candidate):
        return False
    upper_tokens = {t.upper().strip(".") for t in candidate.split()}
    if upper_tokens & NAME_STOPWORDS:
        return False
    if upper_tokens & FUNCTION_WORDS:
        return False
    # A "name" made entirely of tokens from the company name is the company, not a person.
    # Guards against harvesting "Duke Manufacturing" as an executive called Duke.
    if company_tokens and upper_tokens and upper_tokens <= company_tokens:
        return False
    # A line that is itself a recognised title is a title, never a name ("Chief Executive").
    if normalize_title(candidate)[0] != "other":
        return False
    return True


def clean_name(line: str) -> str:
    """Strip a trailing credential suffix but keep the name as written."""
    return NAME_SUFFIX.sub("", line).strip().strip(",").strip()


# --------------------------------------------------------------------------------------
# Line extraction from HTML
# --------------------------------------------------------------------------------------

_BLOCK = re.compile(
    r"(?i)</?(p|div|li|ul|ol|h[1-6]|br|td|tr|th|table|section|article|header|footer|"
    r"nav|span|a|strong|b|em|i|figcaption|dt|dd)\b[^>]*>")


def html_lines(raw_html: str) -> list[str]:
    """Visible text as a list of block-level lines.

    Block tags become line breaks *before* markup is stripped, because the name/title
    adjacency this extractor depends on lives in the document structure. Flattening to one
    whitespace-joined string -- which is what `visible_text` does elsewhere in this
    project for keyword classification -- destroys exactly the signal needed here.
    """
    s = re.sub(r"(?is)<(script|style|noscript|svg|template)\b.*?</\1>", " ", raw_html)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = _BLOCK.sub("\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    out = []
    for line in s.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            out.append(line)
    return out


# --------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------

# Separators for the single-line joined form: "Jane Doe, Chief Operating Officer".
_JOINED = re.compile(r"\s*(?:,|–|—|\||•|\s-\s)\s*")


@dataclass
class Person:
    full_name: str
    title: str
    title_normalized: str
    role_relevance: str
    layout: str            # which of the three layouts produced this record
    confidence: float

    def key(self) -> str:
        return re.sub(r"[^a-z]", "", self.full_name.lower())


@dataclass
class Extraction:
    people: list[Person] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    lines_scanned: int = 0
    title_lines_seen: int = 0

    @property
    def primary(self) -> list[Person]:
        return [p for p in self.people if p.role_relevance == "primary"]


LOW_GRADE_CONFIDENCE = {"low_grade_E26": 0.3, "low_grade_E32": 0.25}
MAX_LOW_GRADE_PER_PAGE = 10
# A low-grade record must sit within this many lines of a CONFIRMED (vocabulary-title)
# person. Rosters cluster; navigation menus, service lists and office directories do not
# sit inside rosters. The first v1.1 dry run admitted "Texas Region President",
# "Student Programs" and "Infrastructure Modernization" as people off menu text -- two
# capitalised tokens beside another short label satisfy every shape test -- and this
# structural guard is what makes the tier a tier rather than a menu scraper.
ROSTER_NEIGHBOUR_LINES = 8
# A role-shaped label: what an out-of-vocabulary title must still look like (E26), and
# what a candidate NAME must not contain ("General Counsel" is a title, not a person).
ROLE_SHAPED_RE = re.compile(
    r"(?i)\b(director|manager|head|lead|officer|estimat\w*|superintendent|controller|"
    r"engineer|counsel|analyst|coordinator|supervisor|specialist|partner|principal|chief|"
    r"president|vp|vice|executive|foreman|administrator|architect|planner|scheduler|buyer|"
    r"purchasing|treasurer|secretary|founder|owner|chairman|chair|general|associate|"
    r"assistant|senior|junior|regional|division|department|group)\b")
# Domain nouns that appear in two-token menu labels and essentially never in a person's
# name. A candidate name carrying one is a label.
DOMAIN_WORDS = {
    "REGION", "REGIONS", "PROGRAM", "PROGRAMS", "SERVICE", "SERVICES", "SOLUTION",
    "SOLUTIONS", "ONLINE", "IMPACT", "EXPERTISE", "LEADERS", "INQUIRIES", "RECRUITING",
    "OFFICE", "OFFICES", "MODEL", "DEVELOPMENT", "NEGOTIATIONS", "INTELLIGENCE",
    "PROCUREMENT", "PROCESSING", "FABRICATION", "REUSE", "SCIENCE", "SCIENCES", "GOODS",
    "SALES", "PROJECT", "PROJECTS", "INTERNAL", "ADVISORY", "MODERNIZATION", "LEASING",
    "INDUSTRIAL", "COMMERCIAL", "RESIDENTIAL", "HEALTHCARE", "EDUCATION", "ENERGY",
    "WHOLESALE", "RETAIL", "FEATURED", "WEEKLY", "CAREER", "CAREERS", "COMMUNITY",
    "STUDENT", "STUDENTS", "COLLEGE", "UNIVERSITY", "INFRASTRUCTURE", "TECHNOLOGY",
    "FACILITIES", "FACILITY", "OPERATIONS", "STRATEGY", "STRATEGIC", "MARKETING", "FINANCE",
    "QUALITY", "SAFETY", "SUSTAINABILITY", "INNOVATION", "GLOBAL", "NATIONAL", "CENTRAL",
    "NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST", "SOUTHEAST", "MIDWEST", "MOUNTAIN",
    "PACIFIC", "ATLANTIC", "TEXAS", "FLORIDA", "CALIFORNIA", "STATES", "CONTRACT",
    "CONTRACTING", "DELIVERY", "SUPPLY", "CHAIN", "LOGISTICS", "TRANSPORT", "FREIGHT",
    "BROKERAGE", "TANK", "NATURAL", "GAS", "LIFE", "DURABLE", "CONSUMER", "BASELINE",
    "COST", "RATE", "BUSINESS", "INDUSTRY", "OVERVIEW", "HISTORY", "MISSION", "VALUES",
    "SHIPPING", "COUNTRY", "MEXICO", "CANADA", "HUMAN", "RESOURCE", "RESOURCES",
}


def name_is_label(name: str) -> bool:
    up = {t.upper().strip(".,") for t in name.split()}
    return bool(up & DOMAIN_WORDS) or bool(ROLE_SHAPED_RE.search(name))


def extract(lines: list[str], company_tokens: set[str] | None = None,
            max_people: int = 40, admit_untitled: bool = False) -> Extraction:
    """Pull (name, title) pairs out of block lines.

    Confidence reflects how much structure supported the pair, never how senior the person
    is. Same-line pairs and name-then-title pairs are the two layouts observed most often
    and score highest; title-then-name is rarer and slightly more likely to pick up an
    adjacent unrelated name, so it scores lower.
    """
    out = Extraction(lines_scanned=len(lines))
    seen: set[str] = set()
    low_grade: list[Person] = []

    def add_low(name: str, title: str, layout: str) -> None:
        """Session 14, convention 41 applied to EXECID (gate inventory E26 / E32): the
        referent is right -- a real person on the company's own leadership page -- and
        only the ROLE is thin, so the record is admitted at low grade with
        role_relevance `unconfirmed` rather than refused. Never primary; H-EXECVOICE-01
        searches primary names only, so nothing downstream reads these without opting in."""
        if name_is_label(name):
            out.rejected.append({"line": f"{name} / {title}", "reason": "low_grade_name_is_label"})
            return
        person = Person(full_name=clean_name(name), title=title.strip(),
                        title_normalized="other" if title.strip() else "unconfirmed",
                        role_relevance="unconfirmed", layout=layout,
                        confidence=LOW_GRADE_CONFIDENCE[layout])
        if person.key() in seen:
            out.rejected.append({"line": f"{name} / {title}", "reason": "duplicate_person"})
            return
        seen.add(person.key())
        low_grade.append((line_index, person))

    line_index = -1
    confirmed_at: list[int] = []

    def add(name: str, title: str, layout: str, confidence: float) -> None:
        key_norm, relevance = normalize_title(title)
        person = Person(full_name=clean_name(name), title=title.strip(),
                        title_normalized=key_norm, role_relevance=relevance,
                        layout=layout, confidence=confidence)
        if person.key() in seen:
            # Leadership pages repeat a person in a card and again in a bio heading. The
            # first (highest-confidence) reading wins; a repeat is not new information.
            out.rejected.append({"line": f"{name} / {title}", "reason": "duplicate_person"})
            return
        seen.add(person.key())
        out.people.append(person)
        confirmed_at.append(line_index)

    for i, line in enumerate(lines):
        line_index = i
        if looks_like_title(line):
            out.title_lines_seen += 1

        # ---- layout C: "Name, Title" on one line ----
        parts = _JOINED.split(line, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            if looks_like_name(left, company_tokens) and looks_like_title(right):
                add(left, right, "joined", 0.85)
                continue

        if not looks_like_name(line, company_tokens):
            continue

        # ---- layout A: name line followed by title line (dominant) ----
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if looks_like_title(nxt):
            add(line, nxt, "name_then_title", 0.9)
            continue

        # ---- layout B: title line followed by name line ----
        prv = lines[i - 1] if i > 0 else ""
        if looks_like_title(prv):
            add(line, prv, "title_then_name", 0.75)
            continue
        # E26: the adjacent line is title-shaped but outside the closed vocabulary.
        shaped = ""
        for cand in (nxt, prv):
            if cand and title_shaped(cand) and not looks_like_name(cand, company_tokens):
                shaped = cand
                break
        if shaped and ROLE_SHAPED_RE.search(shaped):
            add_low(line, shaped, "low_grade_E26")
            continue
        if shaped:
            out.rejected.append({"line": line[:80], "reason": "adjacent_label_not_role_shaped"})
            continue
        # E32: a name with no adjacent title at all -- admitted only on a page already
        # classified as a leadership roster, where a bare name is most likely a person
        # whose title sits in markup the line splitter did not preserve.
        if admit_untitled:
            add_low(line, "", "low_grade_E32")
            continue
        out.rejected.append({"line": line[:80], "reason": "name_without_adjacent_title"})
    if len(out.people) > max_people:
        out.rejected.append({"line": f"{len(out.people)} people extracted",
                             "reason": "suppressed_by_cap"})
        out.people = out.people[:max_people]
    # roster-neighbour guard: keep a low-grade record only near a confirmed person
    kept = []
    for idx, person in low_grade:
        if any(abs(idx - c) <= ROSTER_NEIGHBOUR_LINES for c in confirmed_at):
            kept.append(person)
        else:
            out.rejected.append({"line": f"{person.full_name} / {person.title}",
                                 "reason": "low_grade_no_roster_neighbour"})
    if len(kept) > MAX_LOW_GRADE_PER_PAGE:
        out.rejected.append({"line": f"{len(kept)} low-grade people extracted",
                             "reason": "suppressed_by_low_grade_cap"})
        kept = kept[:MAX_LOW_GRADE_PER_PAGE]
    out.people.extend(kept)
    return out
