"""
Harness holds: a mechanical refusal to run a harness that is known to write bad rows.

A hold is not a note in CLAUDE.md that the next session reads past. A held harness calls
`enforce()` as the first thing its `main` does, and a refused mode stops before any cache, search
client or workbook is opened.

WHAT A HOLD REFUSES, AND WHY OFFLINE --commit IS INCLUDED
---------------------------------------------------------
Refused: every LIVE run (network, dry or not) and every --commit, offline or live.
Allowed: --offline WITHOUT --commit -- a replay of the archived cache that writes nothing to the
workbook. The measurements a hold waits on (dry runs of a fixed extractor) depend on exactly that mode.

Offline --commit is refused too, although it touches no network: replaying H-FIRSTPARTY-01's cache
re-proposes the same furniture-matched claims that were judged unsupported and deleted on 2026-09-15,
and convention 43 would re-insert them under their old ids (simulated that day: "7 inserted").

LIFTING A HOLD is removing its entry below, in a reviewed commit that says which conditions were met.
There is deliberately no environment variable or flag to bypass it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hold:
    since: str
    by: str
    reason: str
    lifts_when: tuple = field(default_factory=tuple)


EXTRACTION_PREREQUISITES = (
    "list items (<li>) are treated as article prose (O00307's press-release bullet was dropped)",
    "footer phrases cut the body only after real article prose has started, with a minimum-body fallback "
    "(Yahoo Finance's syndication notice cut whole articles to ~90 characters)",
    "consent banners are excluded (Caddell's GDPR cookie text supplied an 'analytics' match)",
    "the end-of-article marker pattern matches the site's \"Editors' picks\" (the inherited `editor.s picks` "
    "pattern matches only \"Editor's picks\")",
    "the end-of-article boundary is found before chrome is stripped (stripping first removed the markers on "
    "10 of 18 Construction Dive pages)",
    "all five verified against the 111 cached pages as test fixtures (convention 40), and the fixed extractor "
    "measured by an offline dry run before a new version is written and audited",
)

# H-TRADEPRESS-01 was held with H-FIRSTPARTY-01 from 2026-09-15 and LIFTED the same day, on Matthew Lebrecht's
# instruction, once its end-of-article typo fix landed (v1.8, which also removed two literal backspace bytes from the
# same pattern): an offline replay of v1.8 proposes exactly what the unfixed code proposes, and no live row changes.
# H-FIRSTPARTY-01 was held 2026-09-15 for the page-furniture defect and LIFTED the same day, on Matthew Lebrecht's
# instruction (item 22), once v1.3 read themes from the article body: all five extraction prerequisites landed and
# were verified on the 111 cached pages (core/tests/test_firstparty_body.py), and the offline dry run was measured
# (docs/diagnostics/firstparty_v13_dryrun_2026-09-15.md). The v1.3 run then recorded the rows it no longer produces
# as invalidated_extraction_defect, by his instruction -- the status names the reason, not merely the observation.
#
# No harness is held today. The mechanism stays: adding an entry below refuses that harness's live runs and every
# --commit, before any cache, search client or workbook is opened.
HOLDS: dict[str, Hold] = {
}


def refusal(harness_id: str, offline: bool, commit: bool) -> str | None:
    """The refusal message for this mode, or None if the mode is allowed."""
    hold = HOLDS.get(harness_id)
    if hold is None or (offline and not commit):
        return None
    mode = ("an offline --commit" if offline else "a live run" + (" with --commit" if commit else ""))
    lines = [f"REFUSED: {harness_id} is ON HOLD since {hold.since} ({hold.by}); {mode} is not allowed.",
             f"Reason: {hold.reason}",
             "Still allowed: --offline WITHOUT --commit (a replay of the archived cache; writes nothing to the workbook).",
             "Refused while held: every live run, and every --commit (offline or live).",
             "Lifts when:"]
    lines += [f"  {i}. {c}" for i, c in enumerate(hold.lifts_when, 1)]
    lines.append("To lift: remove this harness's entry from core/holds.py in a reviewed commit naming which "
                 "conditions were met.")
    return "\n".join(lines)


def enforce(harness_id: str, *, offline: bool, commit: bool) -> None:
    msg = refusal(harness_id, offline, commit)
    if msg:
        raise SystemExit(msg)
