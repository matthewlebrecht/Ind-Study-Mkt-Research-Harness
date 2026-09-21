"""
Article typing and per-claim extraction for H-TRADEPRESS-01.

THE ONE IDEA THIS MODULE IMPLEMENTS
-----------------------------------
Extraction is **per claim, not per document** (taxonomy patch rev 2 §2.4). A publication
venue is a delivery channel, not an evidence family. One Construction Dive article can
carry a CEO quote about workforce systems (family 15, `buyer_articulates`), a reported
fact that the company deployed a platform across 40 sites (`buyer_acts`), and a reprinted
press release (family 1, routed to H-FIRSTPARTY-01) -- three observations at two families
and two roles, from one fetch.

The previous harnesses all had one artifact shape and one output shape, so this is the
first place the reader-side rule has to be written in code rather than assumed.

WHY WIRE REPRINTS ARE ROUTED AND NOT FILTERED
---------------------------------------------
Excluding them at extraction makes them invisible, which silently drops their contribution
to `signal_strength` -- and repetition is the *entire* evidence for `repeated_pattern`
(convention 19). A filter that discards instances 2..N destroys the value it was measuring.
So a detected reprint is reclassified to first-party and then run through the normal
redundancy check: already held becomes `suppressed_redundant_key` and still counts toward
strength; not held is genuinely new first-party evidence and is admitted.

The marker grading is asymmetric on purpose. A PRNewswire byline is conclusive by itself.
An "About [Company]" boilerplate footer is NOT, because outlets append boilerplate to
genuinely reported articles routinely -- treating it as conclusive would misroute real
trade journalism into first-party and quietly shrink the articulation leg this harness
exists to widen.
"""

from __future__ import annotations

import re

from core import topics
from harnesses.h_execvoice_01.quotes import classify_buyer_voice

# TWO CLASSIFIERS, AND THEY ARE NOT INTERCHANGEABLE
# --------------------------------------------------
# `classify_buyer_voice` matches how an operator TALKS -- first-person, problem-shaped,
# "we were still on spreadsheets". It is right for a quote and right for a Q&A answer.
#
# `topics.classify` matches the shared theme spine in ordinary third-person prose. It is
# what H-FIRSTPARTY-01 uses on announcements, and it is the right one for a journalist
# reporting an action.
#
# The first version used the buyer-voice classifier on journalist prose, and
# "Gilbane deployed a new document management platform last year" scored zero themes --
# so every ST-PRESSPROFILE row in the run silently failed to exist. The summary line said
# "nothing admissible", which was indistinguishable from the outlets having had nothing.

# --------------------------------------------------------------------------- wire markers

# Conclusive alone. A wire byline or an explicit label means the outlet is telling us this
# text is the company's own, not the reporter's.
WIRE_BYLINE_RE = re.compile(
    r"(?i)\b(pr\s?newswire|business\s?wire|globe\s?newswire|pr\s?web|ein\s?presswire|"
    r"accesswire|newswire\.com|cision)\b")
PRESS_RELEASE_LABEL_RE = re.compile(
    r"(?i)(^|\|)\s*press release\s*($|\||\-)|\bthis press release\b|"
    r"\bthe following press release\b")

# "Sponsored content" and "paid post" are NOT conclusive alone, and the first run measured
# why. Every trade page carries ad slots labelled "Sponsored Content", so treating the
# phrase as conclusive routes reported articles to first-party on the strength of an
# advertisement elsewhere on the page. It did exactly that to ENR's "Gilbane rolls out
# Trunk Tools AI agents across its jobsites" -- real reported coverage, filed as a press
# release, and the only observation the run produced for that company. Same lesson as the
# boilerplate footer: a marker that appears on genuine reporting routinely cannot be
# conclusive by itself.
SPONSORED_RE = re.compile(r"(?i)\bsponsored content\b|\bpaid post\b|\bsponsored by\b")

# NOT conclusive alone -- fires only in combination with the absence of a reporter byline.
BOILERPLATE_FOOTER_RE = re.compile(
    r"(?i)\babout\s+[A-Z][\w&.,'\- ]{2,50}\s*[:\n]|\bfor more information,? (?:please )?"
    r"(?:visit|contact)\b|\bforward-looking statements?\b")

# A reporter byline. Deliberately broad: its job is to *prevent* a misroute, so a false
# positive here costs one under-routed reprint while a false negative costs a genuine
# reported article being filed as first-party.
BYLINE_RE = re.compile(
    r"(?i)\b(by\s+[A-Z][a-z]+\s+[A-Z][\w'\-]+|senior (?:editor|reporter)|"
    r"staff (?:writer|reporter)|contributing editor|@[a-z0-9_]+\.com|"
    r"published by our|newsroom staff)\b")


def wire_verdict(text: str, title: str = "", url: str = "") -> tuple[bool, str]:
    """Is this a reprinted press release? Returns (is_reprint, the marker that decided).

    Order is the marker grading table from §8.2, strongest first.
    """
    blob = f"{title}\n{text[:4000]}"
    m = WIRE_BYLINE_RE.search(blob)
    if m:
        return True, f"wire byline {m.group(0)!r} (conclusive alone)"
    m = PRESS_RELEASE_LABEL_RE.search(blob)
    if m:
        return True, f"explicit press-release label {m.group(0).strip()!r} (conclusive alone)"
    m = SPONSORED_RE.search(blob) or BOILERPLATE_FOOTER_RE.search(text)
    if m:
        if BYLINE_RE.search(blob):
            # The combination rule doing its job. Boilerplate or an ad label plus a
            # reporter byline is a reported article, which is the routine case.
            return False, ""
        return True, (f"marker {m.group(0).strip()[:40]!r} with no reporter byline "
                      f"(not conclusive alone -- fired in combination)")
    return False, ""


# ------------------------------------------------------------------- article typing

# A contributed column: the executive is the AUTHOR, not a source. IC1, because the
# subject chose the topic and wrote the words.
COLUMN_RE = re.compile(
    r"(?i)(/opinion/|/commentary/|/viewpoint/|/guest-|/contributed|/columns?/|"
    r"/perspectives?/|/thought-leadership)")
COLUMN_TEXT_RE = re.compile(
    r"(?i)\b(is (?:the )?(?:president|ceo|coo|cio|cto|chief [a-z ]{3,30}|vice president|"
    r"vp)[^.]{0,80}\.\s*(?:the views|opinions)|guest (?:column|commentary|post)|"
    r"contributed (?:column|commentary|article)|this (?:column|commentary|op-ed)|"
    r"op-ed)\b")

# Conference and panel coverage. The remarks were spoken and the reporter is paraphrasing
# from notes, which is why §8.1 caps this one grade below a printed quote.
PANEL_RE = re.compile(
    r"(?i)\b(panel(?:ist|s)?|keynote|fireside chat|breakout session|conference|summit|"
    r"symposium|expo|trade show|annual meeting|user group|during (?:his|her|their) "
    r"(?:remarks|presentation|talk))\b")


def article_type(text: str, title: str, url: str, exec_names: list[str],
                 has_attributed_quote: bool) -> tuple[str, str]:
    """Which of the four trade-press signal types this artifact is. Returns (type, why).

    Checked most-specific first. A contributed column often also mentions a conference and
    usually contains quotation marks, so testing for a column last would misfile it.
    """
    if COLUMN_RE.search(url):
        return "ST-EXECCOLUMN", f"URL shape marks a contributed column: {url}"
    m = COLUMN_TEXT_RE.search(text[:1500]) or COLUMN_TEXT_RE.search(text[-2500:])
    if m:
        return "ST-EXECCOLUMN", f"contributed-column marker {m.group(0)[:60]!r}"
    # A byline that IS the executive is the strongest column signal of all.
    head = f"{title}\n{text[:600]}"
    for nm in exec_names:
        if re.search(rf"(?i)\bby\s+{re.escape(nm)}\b", head):
            return "ST-EXECCOLUMN", f"bylined by the executive: 'By {nm}'"

    if has_attributed_quote:
        m = PANEL_RE.search(text)
        if m:
            return "ST-EXECPANEL", f"spoken-remarks context {m.group(0)!r}"
        return "ST-EXECQUOTE-REPORTED", "attributed quote in a reported article"

    return "ST-PRESSPROFILE", "reported article with no attributable quote"


# ---------------------------------------------------------- reported concrete actions

# §8.1: where the journalist reports a concrete action -- deployed X, hired Y, opened Z --
# the journalist is a WITNESS TO BEHAVIOUR and the claim is admissible as `buyer_acts`.
# Where the journalist characterises the company's posture, the claim is context only and
# generates nothing.
#
# So this pattern set is deliberately restricted to verbs of completed, checkable action.
# Nothing here matches "is embracing", "has become a leader in", "is well positioned" --
# those are the characterisations the hard rule exists to keep out.
ACTION_RE = re.compile(
    r"(?i)\b("
    # Past tense AND present participle. The first version matched only past forms and
    # missed "signing a deal with contech firm Trunk Tools to deploy its AI chatbot on
    # jobsites across the country" -- a completed, checkable commercial act reported by a
    # bylined reporter, which is precisely what this stratum is for. Trade press writes
    # the lede in the present progressive as a matter of house style.
    #
    # Bare future ("will deploy", "plans to") is deliberately absent. That is an
    # intention, not a witnessed behaviour, and admitting it would quietly turn
    # `buyer_acts` into target-state reporting.
    #
    # "integrated" and "integrating" are ALSO deliberately absent, despite being verbs of
    # action. "Integrated" is the single worst offender in this project's history -- 26 of
    # H-FIRSTPARTY-01 v1.0's rows rested on it, and "our integrated platform" in an
    # earnings release became an announcement about systems integration. A regex cannot
    # tell the verb from the adjective, and the adjective is far more common in this
    # register, so the word is left out entirely rather than admitted and downgraded
    # (convention 32: decide admission first).
    r"(?:has |have |had |is |are )?(?:deployed|deploying|implemented|implementing|"
    r"installed|installing|rolled out|rolling out|adopted|adopting|migrated|migrating|"
    r"replaced|replacing|retired|retiring|consolidated|consolidating|automated|"
    r"automating|digiti[sz]ed|digiti[sz]ing|commissioned|commissioning|completed|"
    r"completing|opened|opening|acquired|acquiring|selected|selecting|signed|signing|"
    r"standardi[sz]ed|standardi[sz]ing|greenlit|scaling|used|using|leveraged|"
    r"leveraging|piloted|piloting|introduced|introducing|launched|launching|"
    r"upgraded|upgrading|partnered|partnering|switched|switching|expanded|expanding)"
    r"|went live (?:with|on)"
    r"|(?:added|hired|appointed|promoted) (?:a |its |their )?(?:new )?"
    r"(?:chief|vice president|vp|director|head) [a-z ]{2,40}"
    r"|(?:invested|spent) \$[\d.,]+ ?(?:million|billion|m|bn)?"
    r"|broke ground on"
    r")\b")

# Session 10 item 3 (Matthew: "build it"). Trade press carries THREE kinds of claim about a
# company, and v1.0-v1.4 admitted only the first:
#
#   ACTION            "Gilbane rolled out Trunk Tools AI agents across its jobsites"
#                     -- the journalist witnessed behaviour: buyer_acts (ST-PRESSPROFILE).
#   SELF-CHARACTERISATION / INTENT
#                     "Gilbane says it is integrating AI across its jobsites";
#                     "Gilbane plans to deploy X"; "the company has integrated Y"
#                     -- the company describing itself or its intent, as reported. That is
#                     the company ARTICULATING, second-hand: buyer_articulates, a new type
#                     ST-PRESSCHAR, grade C, weak_clue, organizational_state from the
#                     sentence (an intent reads target_state). It is not witnessed
#                     behaviour and the row says so.
#   JOURNALIST CHARACTERISATION
#                     "Gilbane is widely regarded as a leader in construction tech"
#                     -- the reporter's own framing. Neither the company acting nor the
#                     company speaking: still generates nothing, still logged.
#
# The regexes are kept apart so each kind is checkable. INTENT_RE is where "integrated"
# and the future tense live -- deliberately absent from ACTION_RE (see above), they are
# admissible as self-description once they are no longer pretending to be behaviour.
INTENT_RE = re.compile(
    r"(?i)\b("
    r"(?:plans?|planning|intends?|aims?|expects?|hopes?|wants?|is set|is looking|seeks?) "
    r"to (?:deploy|implement|install|roll out|adopt|migrate|replace|retire|consolidate|"
    r"automate|digiti[sz]e|standardi[sz]e|scale|pilot|introduce|launch|upgrade|integrate|"
    r"invest|modernize|modernise|move|transition|expand)"
    r"|will (?:deploy|implement|install|roll out|adopt|migrate|replace|retire|consolidate|"
    r"automate|digiti[sz]e|standardi[sz]e|scale|pilot|introduce|launch|upgrade|integrate|"
    r"invest|modernize|modernise|move|transition|expand)"
    r"|(?:has|have|is|are) (?:been )?(?:integrat(?:ed|ing)|focus(?:ed|ing) on|"
    r"committed to|invest(?:ed|ing) in|prioriti[sz]ing|moving toward|transitioning to|"
    r"embracing|leaning into|betting on)"
    r"|(?:is|are|remains?) (?:in the (?:process|midst) of|on a (?:path|journey|mission) to)"
    r")\b")

# The company SPEAKING through the reporter: a reporting verb with the company (or "the
# company", "the firm", "it") as its subject, or an attribution phrase.
SELF_ATTRIB_RE = re.compile(
    r"(?i)\b(said|says|stated|told|noted|added|announced|explained|according to|"
    r"in a statement|described|calls|described itself|bills itself|positions itself|"
    r"the company (?:said|says|has said))\b")

# Journalist characterisation. Present here only so the run log can show that the split
# was actually applied rather than assumed -- these never become observations.
CHARACTERIZATION_RE = re.compile(
    r"(?i)\b(is (?:embracing|leaning into|betting on|no stranger to|well[- ]positioned)|"
    r"has become (?:a|the) leader|is among the (?:most|first)|sees? (?:itself|the future)|"
    r"is (?:widely )?(?:regarded|considered|seen) as|appears to be|seems to be)\b")

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def reported_actions(text: str, max_out: int = 6) -> tuple[list[dict], list[str]]:
    """Sentences reporting a concrete action, and the characterisations that were dropped.

    Both are returned. The dropped list is what makes the artifact-level split checkable
    afterwards -- convention 7: a suppressed result is reported, never silently discarded.
    """
    actions, dropped = [], []
    for sentence in _SENTENCE_RE.split(text):
        s = sentence.strip()
        if not (40 <= len(s) <= 600):
            continue
        m = ACTION_RE.search(s)
        char = CHARACTERIZATION_RE.search(s)
        if not m:
            # Characterisation and nothing else. This is the half of the §8.1 split that
            # generates no observation, and it is recorded rather than dropped silently
            # (convention 7) so the split is checkable afterwards.
            if char:
                dropped.append(s[:160])
            continue
        # ORDER MATTERS, and the first version had it backwards. Testing characterisation
        # first vetoed "is betting on artificial intelligence, signing a deal with contech
        # firm Trunk Tools to deploy its AI chatbot on jobsites across the country" -- a
        # sentence that opens with a characterising verb and then reports an actual signed
        # deal. Trade press writes ledes that way constantly, so a characterisation veto
        # applied ahead of the action test throws out a large share of the real behaviour.
        #
        # The split in §8.1 is between a reported ACTION and a characterisation, not
        # between clean and unclean sentences. Where both are present the action is
        # admissible, and `characterization_present` is carried through to the evidence
        # excerpt so a reviewer sees the framing rather than having it hidden from them.
        themes = topics.classify(s)
        if not themes:
            continue
        actions.append({"sentence": s, "verb": m.group(0), "themes": themes,
                        "characterization_present": bool(char)})
        if len(actions) >= max_out:
            break
    return actions, dropped


def reported_characterizations(text: str, company_name: str,
                               max_out: int = 6) -> tuple[list[dict], list[str]]:
    """Sentences in which the company describes itself or its intent (ST-PRESSCHAR
    candidates), and the journalist-only characterisations dropped.

    A sentence qualifies when: it is not already an ACTION (those route to
    ST-PRESSPROFILE); it matches INTENT_RE or CHARACTERIZATION_RE; it names the company
    (article.is_about_company on the sentence itself -- convention 31's corollary, the
    same rule the action route applies); and it carries a theme. `kind` is "self" when a
    reporting/attribution verb is present (the company is speaking through the reporter),
    else "intent" when INTENT_RE fired (reported intent, attribution implicit), else
    "journalist" -- and only "self" and "intent" become rows.
    """
    from harnesses.h_firstparty_01 import article as _article
    out, dropped = [], []
    for sentence in _SENTENCE_RE.split(text):
        s = sentence.strip()
        if not (40 <= len(s) <= 600):
            continue
        if ACTION_RE.search(s):
            continue
        intent = INTENT_RE.search(s)
        char = CHARACTERIZATION_RE.search(s)
        if not (intent or char):
            continue
        named, _why = _article.is_about_company(s, company_name, head_chars=len(s))
        if not named:
            continue
        attributed = SELF_ATTRIB_RE.search(s)
        if attributed:
            kind = "self"
        elif intent:
            kind = "intent"
        else:
            dropped.append(s[:160])
            continue
        themes = topics.classify(s)
        if not themes:
            continue
        out.append({"sentence": s, "kind": kind,
                    "cue": (attributed or intent).group(0), "themes": themes})
        if len(out) >= max_out:
            break
    return out, dropped


# ------------------------------------------------------------------ grade and strength

# The grade ladder for this harness, and the reason it stops below A.
#
# H-EXECVOICE-01 fixed B as the honest ceiling for journalist-mediated content: really
# said, but selected and framed by somebody else. Trade press is journalist-mediated by
# definition, so "Full" in §8.1's reliability column maps to B here and "Capped -1" maps
# to C. A stays unreachable.
#
# ST-EXECCOLUMN is the interesting case -- the executive authored it, which is the A
# criterion H-EXECVOICE-01 named. It is still graded B: the column passed through an
# outlet's editing and headline-writing, and grading it A would make it the first
# A-graded family-15 row in the project on the strength of an inference about an editorial
# process nobody checked. The column's distinguishing property is recorded where it
# belongs -- signal type ST-EXECCOLUMN, instrument_class IC1 -- rather than by inflating a
# grade. Conservative call, logged for Signal Advisor.
GRADE_BY_TYPE = {
    "ST-EXECQUOTE-REPORTED": "B",
    "ST-EXECCOLUMN": "B",
    "ST-EXECPANEL": "C",     # capped -1: paraphrase of spoken remarks
    "ST-PRESSPROFILE": "C",  # capped -1
    "ST-PRESSCHAR": "C",     # the company describing itself, as reported; not behaviour
}

ROLE_BY_TYPE = {
    "ST-EXECQUOTE-REPORTED": "buyer_articulates",
    "ST-EXECCOLUMN": "buyer_articulates",
    "ST-EXECPANEL": "buyer_articulates",
    # HARD RULE (§8.1). Journalist characterisation is not company speech, and admitting
    # it would inflate the very leg this harness exists to widen. There is no code path
    # that gives ST-PRESSPROFILE any other role.
    "ST-PRESSPROFILE": "buyer_acts",
    "ST-PRESSCHAR": "buyer_articulates",   # self-description is articulation, second-hand
}


# ------------------------------------------------------- speakers named in the article
#
# WHY THIS EXISTS, AND WHY IT IS NOT A LOOSENING OF THE BAR
# ---------------------------------------------------------
# H-EXECVOICE-01 searches for quotes attributable to executives already recorded in
# `Company_Executives`. That is correct for the open web, where a page may mention a name
# with no indication of who the person is. It is the wrong instrument for trade press,
# and the first run measured exactly how wrong: Construction Dive's "ConTech Conversations"
# interview with a Gilbane technology executive yielded nothing, because the person doing
# the talking was not one of the two top-ranked primary executives on file. Trade press
# quotes the officer relevant to the TOPIC -- the CIO, the VP of innovation, the head of
# operations -- and a leadership page ranks the CEO first.
#
# The fix is not to relax attribution. It is to use the fact that trade journalism states
# its sources: "said Jane Roe, chief information officer at Gilbane". That construct
# carries the name, the title AND the employer in one span, which is strictly MORE
# identifying than matching a name against a roster, because the employer is asserted by
# the outlet rather than inferred by us.
#
# So the gate is: a name is admitted as a speaker for this company only when it appears
# adjacent to both a recognised title and this company's own name. A bare "said Jane Roe"
# is not enough, and neither is a name next to a title with no employer.
_NAME = r"[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z'’\-]+){1,2}"
# Up to four words between "chief" and "officer". The first version allowed two and missed
# "chief information and digital officer" -- Gilbane's CIO, quoted on the single best
# article the first run fetched. Compound C-suite titles are the norm rather than the
# exception in this population, where one officer often owns IT, digital and operations.
_TITLE = (r"(?:chief\s+(?:[a-z]{2,20}\s+){1,4}officer|"
          r"C[EIOFTM]O|president|(?:senior\s+|executive\s+)?vice\s+president|"
          r"(?:S|E)?VP(?:\s+of\s+[a-z]{3,20}(?:\s+[a-z]{3,20})?)?|"
          r"(?:senior\s+|managing\s+|executive\s+)?director(?:\s+of\s+[a-z]{3,20}"
          r"(?:\s+[a-z]{3,20})?)?|head\s+of\s+[a-z]{3,20}(?:\s+[a-z]{3,20})?|"
          r"general\s+manager|founder|co-founder|owner|principal)")

# Title tokens that are NOT executives of the subject company -- analysts, vendors and
# consultants quoted in the same article about the same company. Without this, a quote
# from a software vendor's VP describing what contractors ought to do would be recorded as
# the contractor articulating it, which inverts the whole buyer/seller axis the project
# is built on.
_OUTSIDER_RE = re.compile(
    r"(?i)\b(analyst|research|consultan|advisory|partner at|professor|association|"
    r"institute|council|attorney|counsel|economist)\b")


def speakers_in_article(text: str, canonical_name: str,
                        max_out: int = 6) -> list[dict]:
    """Named people the article asserts are officers of THIS company.

    Returns dicts of {name, title, pattern, span}. Every pattern requires the company to
    be named inside or immediately around the construct -- that adjacency IS the identity
    claim, and it is the outlet's claim rather than ours.

    The four shapes below are the ones trade press actually uses, taken from reading the
    first run's fetched pages rather than guessed:

      "Kelly Benedict, the firm's head of innovation and transformation"   <- most common
      "Jane Roe, chief information officer at Gilbane"
      "Gilbane's chief information officer, Jane Roe"
      "The newly appointed head of innovation at ... Gilbane Building Co., Benedict has"

    The "the firm's" shape is the one that needs a guard, because "the firm" names nobody
    by itself. It is admitted only when this company's own name appears within 260
    characters, on top of the article already having passed `is_about_company`.
    """
    from core.resolution import WEAK_TOKENS, tokens as name_tokens

    distinctive = [t for t in name_tokens(canonical_name) if t not in WEAK_TOKENS]
    if not distinctive:
        return []
    # The company as it is actually written in prose, which is rarely the registered
    # name. "Gilbane Building Co." is called "Gilbane" and "Gilbane Building Co."; a
    # pattern requiring both tokens adjacent matches the second and misses the first,
    # which is how "Gilbane's chief information and digital officer" went unrecognised.
    #
    # The rule is convention 31's, unchanged: a COINED token stands alone, a dictionary
    # word must be backed by the full phrase. GILBANE, MIDMARK and KENCO identify;
    # PRIME and SUMMIT do not.
    # `tokens()` upper-cases, and prose does not. The company fragment therefore carries
    # its own inline (?i:...) rather than the whole pattern taking re.I -- _NAME depends
    # on capitalisation to tell a person's name from ordinary words, so a blanket
    # case-insensitive match would turn every "said the chief information officer" into a
    # candidate name.
    from harnesses.h_firstparty_01.article import COMMON_WORD_NAMES
    phrase = r"[\w&.,'’\-]*\s*".join(re.escape(t) for t in distinctive[:2])
    head = distinctive[0]
    if head.lower() not in COMMON_WORD_NAMES:
        company = rf"(?i:(?:{phrase}|{re.escape(head)}))"
    else:
        company = rf"(?i:{phrase})"
    company_rx = re.compile(company)

    patterns = [
        (rf"({_NAME}),\s+(?:the\s+)?(?:firm|company|contractor|carrier|builder)"
         rf"(?:'s|’s)\s+({_TITLE})", "name_thefirms_title", True),
        (rf"({_NAME}),\s+({_TITLE})\s+(?:at|of|for|with)\s+(?:[\w,.\- ]{{0,40}}\s)?"
         rf"{company}", "name_title_at_co", False),
        (rf"{company}(?:'s|’s)\s+({_TITLE}),?\s+({_NAME})", "co_title_name", False),
        (rf"({_NAME}),\s+{company}(?:'s|’s)\s+({_TITLE})", "name_co_title", False),
    ]
    out, seen = [], set()
    for rx, tag, needs_proximity in patterns:
        for m in re.finditer(rx, text):
            groups = [g for g in m.groups() if g]
            if len(groups) < 2:
                continue
            if tag == "co_title_name":
                title, name = groups[0], groups[1]
            elif tag == "name_co_title":
                name, title = groups[0], groups[1]
            else:
                name, title = groups[0], groups[1]
            name = re.sub(r"\s+", " ", name).strip(" ,")
            title = re.sub(r"\s+", " ", title).strip(" ,")
            title = re.sub(r"(?i)\s+(and|or|of|the|for|at)$", "", title).strip()
            if len(name.split()) < 2 or len(name) > 60:
                continue
            window = text[max(0, m.start() - 130):m.end() + 130]
            # An analyst, consultant or vendor quoted in the same article about the same
            # company is not the company speaking. Without this the buyer/seller axis the
            # whole project rests on would invert on a single sentence.
            if _OUTSIDER_RE.search(window):
                continue
            if needs_proximity:
                near = text[max(0, m.start() - 260):m.end() + 260]
                if not company_rx.search(near):
                    continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "title": title, "pattern": tag,
                        "span": window[:220]})
            if len(out) >= max_out:
                return out
    return out


# ------------------------------------------------------------------ Q&A transcripts
#
# A trade Q&A carries the single highest-value articulation available -- an executive
# answering questions about their own operations at length -- and it contains no quotation
# marks at all. `quotes.extract_quotes` finds nothing in one, which is why Construction
# Dive's "ConTech Conversations" interview with Gilbane's head of innovation produced zero
# rows on the first run despite being, line for line, the best evidence the harness saw.
#
# The format is an all-caps speaker label followed by that speaker's words:
#
#     CONSTRUCTION DIVE: What do you do in your innovation role at Gilbane?
#     KELLY BENEDICT: Every day is different ...
#
# This is stronger attribution than a quotation mark, not weaker: the outlet is labelling
# the speaker explicitly, and the label is machine-checkable against a speaker the article
# has already identified as an officer of this company. So a passage is admitted only when
# its label matches a name from `speakers_in_article` -- never on the label alone, which
# would let the interviewer's questions be recorded as the company speaking.
_QA_LABEL_RE = re.compile(r"(?:(?<=\.)|(?<=\?)|(?<=^)|(?<=\s))([A-Z][A-Z.'\-]{1,20}"
                          r"(?:\s+[A-Z][A-Z.'\-]{1,20}){0,3}):\s")


# Where an article's body ends and the site furniture begins. A Q&A's last answer runs to
# the end of the extracted text, which otherwise sweeps up the recommended-reading rail,
# the newsletter pitch and the footer -- and those carry modernization vocabulary of their
# own ("Tech Weekly", "digital transformation" in a promoted headline), which would be
# recorded as the executive saying it.
_FOOTER_RE = re.compile(
    # NOT "editor's note". A trade Q&A prefixes the transcript with "Editor's Note: this
    # interview has been edited for brevity and clarity", so treating it as a footer
    # marker cut the Gilbane interview down to 911 characters and deleted every answer in
    # it. "Editor's picks" IS furniture; "editor's note" is the article talking.
    r"(?i)(recommended reading|editor\W?s?\W{0,2}\s*picks|sign up for|"
    r"get the free (?:daily )?newsletter|share this|copy link|most popular|"
    r"related articles?|more from|filed under|topics covered|"
    r"the trendline|company announcements|subscribe to)")


# Tail-of-page markers that end the article outright when met as their own block after
# prose has begun. Narrower than _FOOTER_RE on purpose: "sign up" and "subscribe" also
# appear in inline newsletter boxes mid-article and would cut a Q&A in half.
# v1.8 (2026-09-15): two defects in this pattern, both found that day. (1) `editor.s picks` allowed exactly one
# character between "editor" and "s", so it matched "Editor's picks" and never Construction Dive's "Editors' picks".
# (2) Since v1.7 (commit 15f7c18) the file held literal BACKSPACE bytes where `\b` was meant after "filed under" and
# "more from", so neither marker could ever match a line. Both fixed; core/tests/test_tradepress.py section 9.
_END_OF_ARTICLE_RE = re.compile(
    r"(?i)^(recommended reading|editor\W?s?\W{0,2}\s*picks|filed under\b.*|related (?:articles?|stories)|"
    r"more from\b.*|topics covered|most popular|read next|trending now|keep up with the story.*)$")


def qa_passages(text: str, speaker_names: list[str],
                min_len: int = 90, max_len: int = 700) -> list[dict]:
    """Answers in an interview transcript attributable to one of `speaker_names`.

    Returns dicts of {name, text}. A label that matches no identified speaker is skipped,
    so the interviewer's questions -- labelled with the outlet's name -- never become
    company speech.

    A labelled block is chunked at sentence boundaries rather than taken whole. Trade Q&As
    label the first exchange and then drop the labels, running the rest of the interview
    as alternating plain paragraphs, so the final block is the bulk of the article. Taking
    it as one passage would either exceed any length bound (and be dropped, which is what
    the first version did) or become a single 6,000-character "quote", which is not a
    quote.
    """
    if not speaker_names:
        return []
    wanted = {}
    for full in speaker_names:
        parts = [p for p in re.split(r"\s+", full.strip()) if len(p.strip(".")) > 1]
        wanted[full.upper()] = full
        if parts:
            wanted[parts[-1].upper()] = full          # surname-only label
            if len(parts) >= 2:
                wanted[f"{parts[0]} {parts[-1]}".upper()] = full

    marks = list(_QA_LABEL_RE.finditer(text))
    if len(marks) < 2:            # one label is a stray heading, not a transcript
        return []

    out = []
    for i, m in enumerate(marks):
        who = wanted.get(m.group(1).strip().upper())
        if not who:
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = re.sub(r"\s+", " ", text[m.end():end]).strip()
        cut = _FOOTER_RE.search(block)
        if cut:
            block = block[:cut.start()].strip()
        # Chunk at sentence boundaries.
        chunk = ""
        for sentence in _SENTENCE_RE.split(block):
            if len(chunk) + len(sentence) + 1 > max_len:
                if len(chunk) >= min_len:
                    out.append({"name": who, "text": chunk.strip()})
                chunk = sentence
            else:
                chunk = f"{chunk} {sentence}".strip()
        if len(chunk) >= min_len:
            out.append({"name": who, "text": chunk.strip()})
    return out


# ------------------------------------------------------------------------ article body

# The measurement that forced this: Merit Medical produced ten observations off five
# MedTech Dive articles, and every single article yielded exactly the same two topics --
# `data_analytics_ai` and `cybersecurity_ot` (the key was renamed `cybersecurity` on
# 2026-09-02; the measurement predates that). Five acquisition and recall stories, none of
# them about AI or security, all classified identically.
#
# The uniformity was the tell. The themes were not coming from the articles at all; they
# were coming from MedTech Dive's own section navigation ("AI", "Cybersecurity") and its
# recommended-reading rail, which `html_lines` returns alongside the body. The harness was
# reading the masthead and recording it as the company's behaviour.
#
# This is convention 16 in a new place -- the pattern was fine, the TEXT was wrong -- and
# it is the same shape as H-SELLERCONTENT-01 reading homepage substitutes and calling it
# coverage. A site's furniture is about the site, never about the company.
#
# The filter is the one `looks_like_article` already relies on: real prose comes in long
# blocks, furniture comes in short ones. Nav items, section links, share buttons, taxonomy
# chips and promoted headlines are all short by nature.
# A block this long is prose whatever it ends with; a block this short is
# furniture unless it ends like a sentence.
LONG_BLOCK = 110
MEDIUM_BLOCK = 45


def _is_prose(block: str) -> bool:
    """Does this block read as a sentence rather than a piece of site furniture?

    Length alone is not the discriminator, and using it alone is what broke the Gilbane
    interview: its answer paragraphs run 69-72 characters, shorter than the 80-character
    threshold that killed MedTech Dive's navigation. Two blocks of similar length, one
    prose and one furniture.

    The reliable difference is punctuation. A sentence ends in terminal punctuation; a nav
    item, a section link, a taxonomy chip and a share button do not -- "Tech Weekly",
    "Cybersecurity", "Deep Dive Opinion Library" are all noun phrases with no full stop.
    So a long block is prose, and a medium block is prose only if it actually ends like a
    sentence.
    """
    b = block.strip()
    if len(b) >= LONG_BLOCK:
        return True
    return len(b) >= MEDIUM_BLOCK and b.rstrip().endswith((".", "!", "?", "”", '"'))


def article_body(lines: list[str]) -> str:
    """The article's prose, with site furniture removed.

    Takes the block list from `html_lines` rather than joined text, because the block
    boundaries are the only signal available for telling a nav item from a sentence once
    the markup is gone.

    THE MEASUREMENT THAT FORCED THIS
    --------------------------------
    Merit Medical produced ten observations off five MedTech Dive articles, and every one
    of the five yielded exactly the same two topics -- `data_analytics_ai` and
    `cybersecurity_ot` (renamed `cybersecurity` 2026-09-02). Five acquisition and recall
    stories, none of them about AI or
    security, all classified identically. The uniformity was the tell: the themes were
    coming from MedTech Dive's own section navigation and its recommended-reading rail,
    not from any article. The harness was reading the masthead and recording it as the
    company's behaviour. Convention 16 in a new place -- the pattern was fine, the TEXT
    was wrong -- and the same shape as H-SELLERCONTENT-01 reading homepage substitutes.

    A Q&A speaker label is the one piece of legitimate content that is tiny.
    "KELLY BENEDICT:" is fifteen characters, and dropping it makes the interview read as
    anonymous prose. It is kept when the block that follows it is prose, which nav items
    are not followed by.
    """
    kept, prose = [], [_is_prose(ln) for ln in lines]
    for i, raw in enumerate(lines):
        ln = raw.strip()
        # v1.7 (session 15, O00604): the end-of-article markers are SHORT lines --
        # "Editors' picks", "Recommended Reading" -- so the prose filter dropped them
        # before `_FOOTER_RE` ever saw the joined body, and the teaser prose that follows
        # them ("Colin Stoner, chief information officer for Novo Construction, describes
        # ...") survived as a long block and became the last answer of a Walbridge Q&A.
        # The marker's POSITION is the boundary: once one is seen after real prose has
        # started, nothing below it is the article.
        if kept and _END_OF_ARTICLE_RE.search(ln):
            break
        if prose[i]:
            kept.append(ln)
        elif _QA_LABEL_ONLY_RE.fullmatch(ln) and i + 1 < len(lines) and prose[i + 1]:
            kept.append(ln)
    body = " ".join(kept)
    cut = _FOOTER_RE.search(body)
    if cut:
        body = body[:cut.start()]
    return body.strip()


# A block that is nothing but an all-caps speaker label.
_QA_LABEL_ONLY_RE = re.compile(r"[A-Z][A-Z.'’\-]{1,20}(?:\s+[A-Z][A-Z.'’\-]{1,20}){0,3}:")


# --------------------------------------------------------- names as the article writes them

def resolve_name_in_text(text: str, full_name: str) -> str | None:
    """The form of `full_name` this article actually uses, or None.

    Company_Executives records the name from a leadership page -- "Edward T. Broderick".
    Trade press writes "Ed Broderick". `quotes.extract_quotes` requires the full name to
    appear on the page before it will attribute anything, which is the right guard against
    a surname collision, and it means the recorded form silently fails against the form
    the outlet uses. A Construction Dive article whose entire lede is "said Ed Broderick"
    produced nothing for exactly this reason.

    The relaxation is narrow, and it is a prefix test rather than a nickname list:

      * the SURNAME must match exactly -- that is the identifying token
      * the first name in the text must share a prefix of at least two characters with
        the recorded first name, in one direction or the other

    So Ed -> Edward and Rob -> Robert resolve; Bill -> William does not, and neither does
    Alan Broderick, which is the case that matters. Nicknames that do not share a prefix
    are missed. That is the conservative direction: a missed quote is a gap, an
    attribution to the wrong person is false evidence, and convention 6a rates false
    evidence worse than a gap.
    """
    parts = [p for p in re.split(r"\s+", full_name.strip()) if len(p.strip(".")) > 1]
    if len(parts) < 2:
        return None
    first, last = parts[0], parts[-1]
    if re.search(rf"\b{re.escape(full_name)}\b", text):
        return full_name
    for m in re.finditer(
            rf"\b([A-Z][a-z]+)\.?\s+(?:[A-Z]\.?\s+)?{re.escape(last)}\b", text):
        cand = m.group(1)
        a, b = cand.lower(), first.lower()
        if len(a) >= 2 and len(b) >= 2 and (a.startswith(b[:2]) or b.startswith(a[:2])):
            if a == b or a.startswith(b) or b.startswith(a):
                return f"{cand} {last}"
    return None
