"""
The article body of a first-party announcement page -- the only text H-FIRSTPARTY-01 v1.3 classifies.

WHY THIS EXISTS (2026-09-15)
----------------------------
v1.2 classified themes on `" ".join(html_lines(page.html))`: the WHOLE page, navigation, sidebars, teaser rails,
footers and cookie banners included. An offline dry run found 109 of its 230 rows with no theme match in the
article body; seven were judged `unsupported` by Matthew Lebrecht (Construction Dive "Editors' picks" teasers, the
"An Informa PLC company" footer, ENR's "Ask ENR AI" link), three more rested on Caddell's GDPR cookie banner, and
PR Newswire's own navigation ("Human Resource & Workforce Management", "Create with AI") was the commonest source
of matched terms. The pattern was fine; the TEXT was wrong -- convention 16 again.

The rule composes two precedents rather than inventing one: H-VENDOR-01 v1.2 (strip <nav>/<header>/<footer>/<aside>,
split at block elements only) and H-TRADEPRESS-01 v1.7 (keep prose blocks, stop at the first end-of-article marker
once prose has begun, cut at a site-footer phrase). A first dry run of that composition surfaced five defects, each
fixed here and each a lift condition of the hold in core/holds.py:

  1. LIST ITEMS ARE PROSE when they sit inside the article. A press release's bullets carry no terminal punctuation,
     so the prose filter dropped them (O00307: "Expanded the AI business unit, integrating machine learning ...").
     A list item is kept when it reads as a clause (MIN_LI_WORDS) and article prose both precedes and follows it --
     a related-headlines list after the last paragraph is not the article.
  2. A FOOTER PHRASE ENDS THE BODY ONLY AFTER ARTICLE PROSE HAS BEGUN. Yahoo Finance prints "This story was
     originally published on Trucking Dive. To receive daily news and insights, subscribe to ..." near the top, and
     "subscribe to" cut whole articles to ~90 characters. Before FOOTER_MIN_PROSE_CHARS of prose, a footer-phrase
     line is dropped as a notice, not treated as the end -- the minimum-body fallback.
  3. CONSENT BANNERS ARE EXCLUDED: any element whose id/class names a cookie/consent/GDPR component is removed as a
     subtree before segmentation, and a line in consent vocabulary is dropped as a backstop.
  4. THE END MARKER MATCHES "Editors' picks" in every apostrophe form. The inherited `editor.s picks` matched only
     "Editor's picks" (one character between), never Construction Dive's "Editors' picks".
  5. THE END OF THE ARTICLE IS FOUND BEFORE CHROME IS STRIPPED. On Construction Dive the "Filed Under" / "Editors'
     picks" markers sit inside <footer>/<aside>, while the teasers that follow them do not -- stripping first
     removed the markers on 10 of 18 pages and left the teasers in the body.

Scripts, styles and comments are removed first: they are not page text, and a marker string inside a script is not
page structure.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

from harnesses.h_vendor_01.harness import strip_chrome

# Mirrors H-TRADEPRESS-01's prose test (harnesses/h_tradepress_01/extract.py::_is_prose), not imported: its module
# carries the `editor.s picks` typo this module exists partly to fix.
LONG_BLOCK = 110
MEDIUM_BLOCK = 45
MIN_LI_WORDS = 6
FOOTER_MIN_PROSE_CHARS = 300
MIN_BODY_CHARS = 300
_MARKER_WINDOW = 80          # a marker is a short text node, not a sentence that happens to begin "More from ..."

_NON_TEXT = re.compile(r"(?is)<(script|style|noscript|svg|template)\b.*?</\1\s*>|<!--.*?-->")
_MARKERS = (r"filed under\b|editor\W?s?\W{0,2}\s*picks\b|recommended reading\b|related (?:articles?|stories|content|news)\b|"
            r"more from\b|most popular\b|keep up with the story\b|read next\b|trending now\b|topics covered\b")
_MARKER_HTML = re.compile(r"(?is)>\s*(" + _MARKERS + r")[^<]{0," + str(_MARKER_WINDOW) + r"}<")
_END_LINE = re.compile(r"(?i)^(" + _MARKERS + r")")
_FOOTER = re.compile(
    r"(?i)(recommended reading|editor\W?s?\W{0,2}\s*picks|sign up for|get the free (?:daily )?newsletter|share this|"
    r"copy link|most popular|related articles?|more from|filed under|topics covered|the trendline|"
    r"company announcements|subscribe to|©\s*(?:\d{4}|copyright)|\ball rights reserved\b)")
_QA_LABEL = re.compile(r"[A-Z][A-Z.'’\-]{1,20}(?:\s+[A-Z][A-Z.'’\-]{1,20}){0,3}:")
_CONSENT_ATTR = re.compile(r"(?i)cookie|consent|gdpr|onetrust|cmplz|cookielawinfo|(?:^|[\s\"'])cli-")
_CONSENT_LINE = re.compile(
    r"(?i)\bwe use cookies\b|cookie consent|\bgdpr\b|cookielawinfo|manage consent|accept all cookies|"
    r"cookie (?:settings|preferences|policy)|this website uses cookies|\bconsent to the use of\b")
_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9:-]*)\b([^>]*?)(/?)>")
_ATTR = re.compile(r"""(?is)\b(?:id|class|aria-label)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_NEVER_REMOVE = {"html", "body", "main", "article", "head"}
_BLOCK_TAGS = re.compile(
    r"(?is)</?(?:p|ul|ol|h[1-6]|div|section|article|main|table|thead|tbody|tr|td|th|blockquote|figure|figcaption|"
    r"dl|dt|dd|br|hr|header|footer|nav|aside)\b[^>]*>|</li\s*>")
_LI_OPEN = re.compile(r"(?is)<li\b[^>]*>")
_LI = "\x02"


@dataclass
class Body:
    lines: list[str]
    end_marker: str = ""
    consent_elements_removed: int = 0
    consent_lines_dropped: int = 0
    footer_notices_dropped: list[str] = field(default_factory=list)
    footer_cut: str = ""
    list_items_kept: int = 0

    @property
    def text(self) -> str:
        return " ".join(self.lines)


def is_prose(block: str) -> bool:
    b = block.strip()
    if len(b) >= LONG_BLOCK:
        return True
    return len(b) >= MEDIUM_BLOCK and b.endswith((".", "!", "?", "”", '"'))


def remove_consent(html: str) -> tuple[str, int]:
    """Remove every element whose id/class/aria-label names a consent component, with its whole subtree (nesting of
    the same tag name is counted, so a banner built from nested <div>s goes as one). The document's structural roots
    are never removed."""
    out, removed, i = [], 0, 0
    tags = list(_TAG.finditer(html))
    k = 0
    while k < len(tags):
        m = tags[k]
        closing, name, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if (not closing and not selfclose and name not in _VOID and name not in _NEVER_REMOVE
                and any(_CONSENT_ATTR.search(v) for v in _ATTR.findall(attrs))):
            depth, j = 1, k + 1
            while j < len(tags) and depth:
                t = tags[j]
                if t.group(2).lower() == name and not t.group(4):
                    depth += -1 if t.group(1) else 1
                j += 1
            # A "consent" element wrapping most of the page is a site's page wrapper, not a banner: left alone.
            if depth == 0 and tags[j - 1].end() - m.start() <= len(html) // 2:
                out.append(html[i:m.start()])
                i = tags[j - 1].end()
                removed += 1
                k = j
                continue
        k += 1
    out.append(html[i:])
    return "".join(out), removed


def _segment(html: str) -> list[tuple[str, bool]]:
    """(line, is_list_item), split at block elements only; inline markup removed in place."""
    t = _LI_OPEN.sub("\n" + _LI, html)
    t = _BLOCK_TAGS.sub("\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t)
    out = []
    for raw in t.split("\n"):
        li = _LI in raw
        ln = re.sub(r"[ \t\r\f\v ]+", " ", raw.replace(_LI, " ")).strip()
        if ln:
            out.append((ln, li))
    return out


def _prose_chars(html_fragment: str) -> int:
    return sum(len(ln) for ln, _ in _segment(strip_chrome(html_fragment)) if is_prose(ln))


def _end_of_article(html: str) -> tuple[int | None, str]:
    """Where the article ends in the raw page: the first end-of-article marker after the <h1> (or the page start)
    that follows at least FOOTER_MIN_PROSE_CHARS of article prose. Found BEFORE chrome is stripped (defect 5)."""
    h1 = re.search(r"(?is)<h1\b", html)
    start = h1.start() if h1 else 0
    for m in _MARKER_HTML.finditer(html, start):
        if _prose_chars(html[start:m.start() + 1]) >= FOOTER_MIN_PROSE_CHARS:
            return m.start() + 1, m.group(1)
    return None, ""


def extract(raw_html: str) -> Body:
    html = _NON_TEXT.sub(" ", raw_html or "")
    html, consent_removed = remove_consent(html)
    pos, marker = _end_of_article(html)
    if pos is not None:
        html = html[:pos]
    segs = _segment(strip_chrome(html))

    consent_dropped = 0
    kept_segs = []
    for ln, li in segs:
        if _CONSENT_LINE.search(ln):
            consent_dropped += 1
            continue
        kept_segs.append((ln, li))
    segs = kept_segs

    prose_idx = [i for i, (ln, li) in enumerate(segs) if not li and is_prose(ln)]
    first_prose = prose_idx[0] if prose_idx else None
    last_prose = prose_idx[-1] if prose_idx else None

    body = Body(lines=[], end_marker=marker, consent_elements_removed=consent_removed,
                consent_lines_dropped=consent_dropped)
    chars = 0
    for i, (ln, li) in enumerate(segs):
        if body.lines and chars >= FOOTER_MIN_PROSE_CHARS and _END_LINE.match(ln) and len(ln) <= _MARKER_WINDOW + 20:
            body.end_marker = body.end_marker or ln
            break
        if li:
            keep = (first_prose is not None and first_prose < i < last_prose
                    and (len(ln.split()) >= MIN_LI_WORDS or is_prose(ln)))
            if keep:
                body.list_items_kept += 1
        else:
            keep = is_prose(ln) or (bool(_QA_LABEL.fullmatch(ln)) and i + 1 < len(segs) and is_prose(segs[i + 1][0]))
        if not keep:
            continue
        m = _FOOTER.search(ln)
        if m:
            if chars < FOOTER_MIN_PROSE_CHARS:
                body.footer_notices_dropped.append(ln[:160])     # defect 2: a notice, not the end
                continue
            head = ln[:m.start()].strip()
            if head:
                body.lines.append(head)
            body.footer_cut = m.group(0)
            break
        body.lines.append(ln)
        chars += len(ln)
    return body
