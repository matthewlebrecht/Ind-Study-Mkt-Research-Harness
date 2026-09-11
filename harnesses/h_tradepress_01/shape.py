"""
Document shape, for the identity window only.

THE PROBLEM THIS SOLVES
-----------------------
`article.is_about_company` looks for the company in the first 2,500 characters, because a
firm mentioned once in the twelfth paragraph is not the subject of a narrative article.
That is right for narrative and wrong for a document that has no single subject.

Measured across H-TRADEPRESS-01 v1.0's 28 `not_about_company` refusals: only TWO are
genuinely absent from the document (a McGough data-centre annexation piece and a Penske
Matson story, both correct refusals). In the other 26 the company is named, just past the
window -- RYCON at 7,609 in ENR's Top 400 Contractors, GILBANE at 4,563 in Construction
Exec's "New Names and Faces", LEPRINO at 15,533 in a Top 150 processors table.

A refusal saying an article is not about a company, when the article names it, is a false
statement in the record (convention 12). But the window cannot simply be widened: the
brief is explicit that loosening identity matching globally is the change that broke
Midmark last session, and convention 37 says a fix is not verified until it has been run
against the case that was already working.

WHAT ACTUALLY DISTINGUISHES THESE DOCUMENTS
-------------------------------------------
Not "tabular" -- that only covers the rankings. The two ENR Pittsburgh airport features the
brief singles out as worth admitting are ordinary narrative prose; Rycon sits at 3,426 and
5,249 as one of several named contractors on a $1.6B project.

What all of them share is that they have **no single subject**. A rankings table, a "New
Names and Faces" column, a regional roundup and a multi-contractor project feature are the
same shape for this purpose: many organisations named, none of them the one the piece is
about. A prefix window encodes "the subject is named early", which is true of narrative
with one subject and false of every one of these.

So the test is multi-subject-ness, and it is deliberately three independent signals rather
than a single loose one -- convention 16's rule that a loose pattern manufactures
confidence applies to this detector exactly as it applies to the classifiers it feeds.

CONVENTION 31 STILL GOVERNS DOWNSTREAM. This module only decides HOW MUCH of the document
the identity test may read. It never decides identity. A common dictionary word still needs
the full company phrase wherever it is found, which is why widening the window for Prime
Inc. changes nothing: "Prime" alone is still not an identity at character 12,000.
"""

from __future__ import annotations

import re

# Rankings, lists and roundups, by the words outlets actually use in titles and URLs.
# Every pattern here was taken from a refusal in the v1.0 run rather than imagined.
LISTING_TITLE_RE = re.compile(
    r"(?i)\btop\s*\d+\b|\btop\s+(?:contractors|firms|processors|companies|owners)\b|"
    r"\branking(?:s)?\b|\btoplists?\b|\bnew\s+names\s+and\s+faces\b|"
    r"\bon\s+the\s+scene\b|\bindustry\s+news\s+for\b|\bbest\s+projects?\b|"
    r"\bwho'?s\s+who\b|\bthe\s+list\b|\bpage\s+\d+\b")

LISTING_URL_RE = re.compile(
    r"(?i)/toplists?/|/top-?\d+|/rankings?/|/keywords?/|/lists?/|"
    r"new-names-and-faces|on-the-scene|industry-news-for|top_contractors")

# An organisation named with its legal form. Counting these is what catches the multi-
# contractor feature, which carries no listing vocabulary at all.
ORG_RE = re.compile(
    r"\b[A-Z][A-Za-z&.'\-]+(?:\s+[A-Z][A-Za-z&.'\-]+){0,3}\s+"
    r"(?:Inc\.?|LLC|L\.L\.C\.|Corp\.?|Corporation|Co\.|Company|Ltd\.?|LP|LLP|Group|"
    r"Construction|Contractors|Builders|Associates)\b")

# How many distinctly-named organisations make a document multi-subject. Chosen from the
# measured documents, not guessed: the two ENR Pittsburgh features name 9 and 14, while a
# single-subject Construction Dive story about one firm names 2-4 (the subject, sometimes a
# client, sometimes a vendor). Set at 6 so the ordinary reported story stays narrative.
MULTI_SUBJECT_ORG_COUNT = 6

# NO TABULAR CLAUSE, AND THE REASON IS WORTH KEEPING.
#
# The first version scored a document as tabular when most of its lines were short. It
# fired on 28 of 28 refused documents -- and on the two that are CORRECTLY refused because
# the company is genuinely absent. A detector that fires on everything is not a detector.
#
# The cause: `html_lines` returns the whole page, and every web page is mostly navigation,
# menus and footer links, all of them short. So the measure was reading site furniture, not
# article shape. That is the MedTech Dive defect exactly -- section navigation classified as
# a company's behaviour -- in a new place, and convention 36's test caught it: the signal
# did not change when the input did.
#
# What is left is deliberately narrow and every pattern below came from a refusal in the
# v1.0 run rather than from imagination.

def distinct_orgs(text: str) -> set[str]:
    """Distinctly-named organisations in the document, normalised for comparison."""
    out = set()
    for m in ORG_RE.finditer(text):
        name = re.sub(r"\s+", " ", m.group(0)).strip(" .,")
        if len(name) >= 6:
            out.add(name.lower())
    return out


def is_multi_subject(body: str, title: str, url: str) -> tuple[bool, str]:
    """(verdict, why). True where the document has no single subject.

    Takes the ARTICLE BODY, never the whole page. Passing page lines here is what made the
    first version fire on everything.

    Returns the reason as well as the verdict so a widened window is as checkable
    afterwards as a refusal is (convention 12): the run log records which signal fired.
    """
    if LISTING_URL_RE.search(url or ""):
        return True, f"URL shape marks a list or index page: {url}"
    m = LISTING_TITLE_RE.search(title or "")
    if m:
        return True, f"title marks a ranking or roundup: {m.group(0)!r}"
    orgs = distinct_orgs(body or "")
    if len(orgs) >= MULTI_SUBJECT_ORG_COUNT:
        return True, (f"names {len(orgs)} distinct organisations, so no single one is the "
                      f"subject (e.g. {', '.join(sorted(orgs)[:3])})")
    return False, ""
