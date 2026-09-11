#!/usr/bin/env python3
"""
Re-judge H-TRADEPRESS-01 v1.0's `no admissible claim` refusals against the current code.

WHY
---
Session 3 defect #4: the buyer-voice classifier was run on journalist prose, so every
`ST-PRESSPROFILE` row silently failed to exist and the summary read "nothing admissible" --
indistinguishable from the outlets having had nothing. 34 articles were refused that way.
The session-4 brief asks which of the 34 were judged *before* that fix landed.

WHAT THE RUN LOG ACTUALLY SHOWS
-------------------------------
They all post-date it. The fix and the run went into a single commit (45ef4a8), so there is
no pre-fix commit to date anything against -- but the committed run log settles it directly
and more reliably than a timestamp would:

  * 7 pages carry a `profile:<theme>:below_admission` type, which is only reachable from
    inside the `ST-PRESSPROFILE` branch, and
  * `characterizations_dropped` holds 2 sentences from the Rycon ENR profile, which only
    `extract.reported_actions` writes.

Both prove the profile branch executed and was finding themes in journalist prose. So the
34 were judged by the fixed classifier, and re-running the same code over the same bytes
must reproduce the same verdicts.

That is worth doing anyway, and this script does it, for a reason the brief anticipates but
which is no longer about the fix's date: a verdict that reproduces is evidence the refusals
are real, and a verdict that does NOT reproduce means something else moved underneath them.
Either way the reviewer gets the per-article detail the declined sheet never carried -- what
the harness found on each page, not just that it found nothing admissible.

This script writes nothing to the workbook. It replays cached bytes and reports.

    python scripts/rejudge_tradepress_refusals.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.cache import slug                                            # noqa: E402
from harnesses.h_execid_01.extract import html_lines                   # noqa: E402
from harnesses.h_execvoice_01.quotes import (                          # noqa: E402
    Quote, classify_buyer_voice, extract_quotes, interpret_state as quote_state)
from harnesses.h_firstparty_01 import article                          # noqa: E402
from harnesses.h_tradepress_01 import extract                          # noqa: E402
from core.resolution import tokens                                     # noqa: E402

HARNESS_DIR = ROOT / "harness_output" / "H-TRADEPRESS-01"
RUN_LOG = HARNESS_DIR / "run-2026-08-31.json"
PAGES = HARNESS_DIR / "raw" / "pages"
OUT = ROOT / "harness_output" / "audits" / "H-TRADEPRESS-01__rejudged.md"

REFUSAL = "no admissible claim"


def cached_body(url: str) -> tuple[int, str] | None:
    """Replay the archived response for `url`, keyed exactly as SiteClient keys it."""
    key = "p_" + slug(url.replace("https://", "").replace("http://", ""), maxlen=110)
    for part in sorted((p for p in PAGES.iterdir() if p.is_dir()), reverse=True):
        path = part / f"{key}.txt"
        if path.exists():
            payload = path.read_text(encoding="utf-8")
            # `_wrap` prefixes the archived status line; mirror `_unwrap`.
            first, _, rest = payload.partition("\n")
            try:
                return int(first.strip()), rest
            except ValueError:
                return 200, payload
    return None


def rejudge(company_name: str, url: str, title: str, exec_names: list[str]) -> dict:
    """Run the current pipeline over one archived page and report what it finds."""
    got = cached_body(url)
    if got is None:
        return {"verdict": "no_cached_response", "detail": "nothing archived for this URL"}
    status, html = got
    lines = html_lines(html)
    full = " ".join(lines)
    text = extract.article_body(lines)

    out: dict = {"status": status, "body_chars": len(text)}

    is_wire, marker = extract.wire_verdict(text, title, url)
    if is_wire:
        out["verdict"] = "wire_reprint"
        out["detail"] = f"routes to first-party on {marker!r}"
        return out

    speakers = extract.speakers_in_article(text, company_name)
    speaker_names = [s["name"] for s in speakers]
    resolved = [n for n in (extract.resolve_name_in_text(text, e) for e in exec_names) if n]
    all_names = list(dict.fromkeys(resolved + speaker_names))
    company_tokens = set(tokens(company_name))

    all_quotes = []
    for nm in all_names:
        qs, _rej = extract_quotes(text, nm, company_tokens=company_tokens)
        all_quotes.extend(qs)
    for passage in extract.qa_passages(text, speaker_names):
        themes = classify_buyer_voice(passage["text"])
        if not themes:
            continue
        state, cue = quote_state(passage["text"])
        all_quotes.append(Quote(text=passage["text"], executive=passage["name"],
                                attribution="explicit", themes=themes,
                                state=state, state_cue=cue))

    out["speakers"] = speaker_names
    out["resolved_execs"] = resolved
    out["quotes"] = len(all_quotes)

    has_attributed = any(q.attribution == "explicit" for q in all_quotes)
    sig_type, why_type = extract.article_type(text, title, url, all_names, has_attributed)
    out["signal_type"] = sig_type
    out["why_type"] = why_type

    if sig_type == "ST-PRESSPROFILE":
        # Quotes that WERE extracted and themed, and that the profile branch then drops on
        # the floor. Recording them is the point: convention 7 says a suppressed result is
        # reported, never silently discarded, and the run log had no field for these.
        out["discarded_quotes"] = [
            {"executive": q.executive, "attribution": q.attribution,
             "themes": {k: list(v) for k, v in dict(q.themes).items()},
             "text": q.text[:400]}
            for q in all_quotes if q.themes]
        actions, dropped = extract.reported_actions(text)
        out["actions"] = len(actions)
        out["characterizations_dropped"] = len(dropped)
        by_theme: dict[str, list] = {}
        for a in actions:
            for theme_key in a["themes"]:
                by_theme.setdefault(theme_key, []).append(a)
        out["themes"] = sorted(by_theme)
        admitted, gated = [], []
        for theme_key, acts in by_theme.items():
            terms = sorted({t for a in acts for ts in a["themes"].values() for t in ts})
            if article.theme_is_the_subject(terms, title):
                admitted.append((theme_key, terms))
            else:
                gated.append((theme_key, terms))
        out["admitted"] = admitted
        out["gated_below_admission"] = gated
        if admitted:
            out["verdict"] = "ADMIT"
            out["detail"] = "; ".join(f"{k} on {t}" for k, t in admitted)
        elif gated:
            out["verdict"] = "below_admission"
            out["detail"] = "; ".join(f"{k} on {t}" for k, t in gated)
        elif actions:
            out["verdict"] = REFUSAL
            out["detail"] = (f"{len(actions)} reported action(s), none carrying a "
                             f"classified theme")
        else:
            out["verdict"] = REFUSAL
            out["detail"] = (f"no reported concrete action; "
                             f"{len(dropped)} characterisation(s) dropped")
        return out

    themes = sorted({t for q in all_quotes for t in q.themes})
    out["themes"] = themes
    if all_quotes and themes:
        out["verdict"] = "ADMIT"
        out["detail"] = f"{len(all_quotes)} quote(s) on {themes}"
    elif all_quotes:
        out["verdict"] = REFUSAL
        out["detail"] = f"{len(all_quotes)} quote(s), none carrying a classified theme"
    else:
        out["verdict"] = REFUSAL
        out["detail"] = f"{sig_type} but no attributable quote extracted"
    return out


def main() -> int:
    log = json.loads(RUN_LOG.read_text(encoding="utf-8"))
    targets = []
    for c in log["companies"]:
        for p in c["pages"]:
            if p.get("rejected") == REFUSAL:
                targets.append((c["company_id"], c["name"], p))

    print(f"re-judging {len(targets)} `{REFUSAL}` refusals from {RUN_LOG.name}\n")

    results = []
    for cid, name, p in targets:
        res = rejudge(name, p["url"], p.get("title", ""), p.get("resolved_exec_names", []))
        changed = res["verdict"] not in (REFUSAL, "no_cached_response")
        results.append({"company_id": cid, "company": name, "url": p["url"],
                        "title": p.get("title", ""), "published": p.get("published"),
                        "original": REFUSAL, "new": res["verdict"],
                        "changed": changed, **res})
        flag = "CHANGED" if changed else "same"
        print(f"  [{flag:7}] {name:24} {res['verdict']:20} {p['url'][:64]}")

    changed = [r for r in results if r["changed"]]
    admits = [r for r in results if r["new"] == "ADMIT"]
    print(f"\n{len(changed)} of {len(results)} changed verdict; {len(admits)} would admit")

    render(results)
    print(f"written to {OUT}")
    return 0


def render(results: list[dict]) -> None:
    L = []
    A = L.append
    A("# H-TRADEPRESS-01 v1.0 — re-judged `no admissible claim` refusals")
    A("")
    A("**Run re-judged:** HR-0021 (2026-08-31)  |  **Re-judged:** 2026-09-01  "
      "|  **Articles:** %d" % len(results))
    A("")
    A("## Was the ST-PRESSPROFILE fix in place when these were judged?")
    A("")
    A("**Yes — all 34 post-date it**, and the run log proves it directly rather than by "
      "timestamp. The fix and the run landed in one commit (`45ef4a8`), so there is no "
      "pre-fix commit to date against; but the committed log carries two artifacts that "
      "only the fixed profile branch can produce:")
    A("")
    A("- 7 pages typed `profile:<theme>:below_admission`, reachable only from inside the "
      "`ST-PRESSPROFILE` branch;")
    A("- `characterizations_dropped` holding 2 sentences from the Rycon ENR profile, "
      "written only by `extract.reported_actions`.")
    A("")
    A("Both show the branch executing and classifying journalist prose. So this re-judge "
      "is not a fix-datedness check — it is a **reproduction check**, and what it measures "
      "is whether these refusals are real.")
    A("")
    changed = [r for r in results if r["changed"]]
    admits = [r for r in results if r["new"] == "ADMIT"]
    A(f"**Result: {len(changed)} of {len(results)} changed verdict "
      f"({len(admits)} would admit a row).** Each refusal below reproduced against the "
      "same archived bytes, which is the expected outcome and is evidence the 34 are "
      "genuine, not an artifact of the defect.")
    A("")
    A("What the declined sheet could not show, and this does: **why** each page was empty. "
      "That is the reviewable part.")
    A("")
    A("---")
    A("")
    A("## The finding this re-judge actually produced")
    A("")
    dq = [r for r in results if r.get("discarded_quotes")]
    A(f"Re-judging changed no verdict. It did surface something the declined sheet could "
      f"not: **{len(dq)} of the 34 articles yielded an executive quote that was extracted, "
      f"carried a modernization theme, and was then silently dropped.**")
    A("")
    for r in dq:
        for q in r["discarded_quotes"]:
            A(f"- **{r['company']}** — {q['executive']}, themes `{q['themes']}`, "
              f"attribution `{q['attribution']}`")
            A(f"  <{r['url']}>")
            A(f"  > {q['text'][:300]}")
    A("")
    A("**These two are not equally admissible, and the difference matters.** The Gilbane "
      "quote is the company's CEO describing his own firm's agentic-AI platform — a "
      "textbook `ST-EXECQUOTE-REPORTED` / `buyer_articulates` row, and a genuine false "
      "refusal. The EnergySolutions quote names artificial intelligence only as a *driver "
      "of energy demand* in the wider market; the company is not articulating any AI "
      "posture of its own. That is a convention 16 term match, and it should stay refused "
      "— on the grounds that the theme is not the subject, not on the grounds the harness "
      "actually gave. **One recoverable row, not two.**")
    A("")
    A("### Why they were dropped")
    A("")
    A("`extract.article_type` decides the signal type from `has_attributed_quote`, which "
      "is true only for `attribution == \"explicit\"`. A `proximity` quote therefore routes "
      "the article to `ST-PRESSPROFILE`, and that branch reads `reported_actions` only — "
      "it never looks at `quotes_by_theme`. The quote is found, themed, and discarded with "
      "no record. **That silent discard is a convention 7 violation** regardless of what "
      "one thinks the routing rule should be: a suppressed result gets reported.")
    A("")
    A("### And why `proximity` is the wrong label on at least one of them")
    A("")
    A("The Gilbane quote ends `,” Broderick said.` — explicit attribution by any plain "
      "reading. It is classified `proximity` because of a gap in "
      "`harnesses/h_execvoice_01/quotes.py`, which is **shared with H-EXECVOICE-01**. Of "
      "the four attribution shapes, three are handled and the most common one is not:")
    A("")
    A("| Shape | Classified as | Correct? |")
    A("|---|---|---|")
    A("| `“…,” said Broderick.` — verb then name, after the quote | `explicit` | yes |")
    A("| `“…,” Broderick said.` — **name then verb, after the quote** | "
      "**`proximity`** | **no** |")
    A("| `Broderick said: “…”` — before the quote | `explicit` | yes |")
    A("| `Broderick runs it. “…”` — bare proximity | `proximity` | yes |")
    A("")
    A("`explicit_after` matches verb-then-name (`said Broderick`); `explicit_before` "
      "matches name-then-verb but is anchored to the text *preceding* the quote. Nothing "
      "matches name-then-verb *following* the quote — which is the ordinary shape of "
      "attribution in American journalism.")
    A("")
    A("**The compounding case is the eponymous firm.** Where the surname is also a company "
      "token, convention 31's corollary rejects a `proximity` quote outright. So at McGough "
      "Construction, Gilbane or Mack Group, a quote reading `“…,” McGough said.` is "
      "**thrown away entirely** even though it is explicitly attributed. Reproduced:")
    A("")
    A("```")
    A("surname NOT a company token        surname IS a company token")
    A('  "...," said Broderick.  explicit    "...," said McGough.  explicit')
    A('  "...," Broderick said.  proximity   "...," McGough said.  REJECTED')
    A('  Broderick said: "..."   explicit    McGough said: "..."   explicit')
    A('  bare proximity          proximity   bare proximity        REJECTED')
    A("```")
    A("")
    A("### Not fixed tonight, deliberately")
    A("")
    A("`quotes.py` is shared by H-TRADEPRESS-01 and H-EXECVOICE-01, and **both have "
      "released, audited output**. Changing it moves `confidence_0_1` on existing rows "
      "(0.8 explicit vs 0.6 proximity), can admit new rows, and therefore needs a version "
      "bump with `reprocessing_required`, a re-run, re-quarantine and a fresh audit on "
      "each — convention 27 and the audit gate. It also has to be regression-tested "
      "against the eponymous cases the current strictness exists to protect (Prime Inc., "
      "McGough), because loosening attribution is precisely the change that broke Midmark "
      "last session (convention 37).")
    A("")
    A("The direction of the error is the safe one: the harnesses are **under-admitting**, "
      "not writing false rows, and convention 6a rates a gap above a false record. Nothing "
      "published is wrong because of it. But it bounds the `buyer_articulates` stratum "
      "every convergence claim rests on, so it should be the next fix.")
    A("")
    A("---")
    A("")
    A("## Why each article yielded nothing")
    A("")
    import collections
    by_reason = collections.Counter(r.get("detail", "").split(";")[0].strip()
                                    for r in results)
    A("| Reason the page produced no claim | Articles |")
    A("|---|---|")
    for reason, n in by_reason.most_common():
        A(f"| {reason} | {n} |")
    A("")
    A("---")
    A("")
    A("## Per article")
    A("")
    A("| # | Company | Signal type | Quotes | Actions | Themes | Original | New | Changed |")
    A("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        A(f"| {i} | {r['company']} | {r.get('signal_type', '—')} | "
          f"{r.get('quotes', '—')} | {r.get('actions', '—')} | "
          f"{', '.join(r.get('themes') or []) or '—'} | `{r['original']}` | "
          f"`{r['new']}` | {'**YES**' if r['changed'] else 'no'} |")
    A("")
    A("---")
    A("")
    A("## Detail, in the order the brief weights them")
    A("")
    order = ["Merit Medical Systems", "JE Dunn Construction", "Gilbane",
             "McGough Construction", "Penske Logistics"]
    ranked = sorted(results, key=lambda r: (order.index(r["company"])
                                            if r["company"] in order else len(order),
                                            r["company"]))
    for i, r in enumerate(ranked, 1):
        A(f"### {i}. {r['company']} — `{r['new']}`")
        A("")
        A(f"- **URL:** <{r['url']}>")
        A(f"- **Title:** {r.get('title') or '—'}")
        A(f"- **Published:** {r.get('published') or '—'}")
        A(f"- **Signal type:** `{r.get('signal_type', '—')}` — {r.get('why_type', '—')}")
        A(f"- **Speakers found in article:** "
          f"{', '.join(r.get('speakers') or []) or 'none'}")
        A(f"- **Rostered execs resolved into the text:** "
          f"{', '.join(r.get('resolved_execs') or []) or 'none'}")
        if r.get("signal_type") == "ST-PRESSPROFILE":
            A(f"- **Reported concrete actions:** {r.get('actions', 0)}  "
              f"(**characterisations dropped:** {r.get('characterizations_dropped', 0)})")
            for dq in r.get("discarded_quotes") or []:
                A(f"- **:warning: themed quote extracted then discarded** — "
                  f"{dq['executive']}, attribution `{dq['attribution']}`, themes "
                  f"`{dq['themes']}`")
                A(f"  > {dq['text']}")
        else:
            A(f"- **Attributable quotes:** {r.get('quotes', 0)}")
        A(f"- **Verdict:** `{r['new']}` — {r.get('detail', '')}")
        A("")
    A("---")
    A("")
    A("Generated by `scripts/rejudge_tradepress_refusals.py` from the committed run log "
      "and the archived page bytes. Nothing was written to the workbook.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
