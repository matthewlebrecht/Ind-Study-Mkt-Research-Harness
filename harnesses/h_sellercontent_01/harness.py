#!/usr/bin/env python3
"""
H-SELLERCONTENT-01 — Provider-Market Messaging Extractor (the Week 2 seller benchmark).

WHAT THIS IS FOR
----------------
The governing question ends with "...and how adequately does the provider market address
them?" Answering it needs a measured account of what the provider market actually
messages about, expressed in the same vocabulary as the buyer-side evidence so the two can
be compared without hand-waving. That is this harness, and nothing more: CLAUDE.md's
research posture is buyer-dominant, and seller discourse is a compact comparative
benchmark, not a co-equal research population.

Every observation it produces is `evidence_family = seller_discourse`,
`evidence_role = provider_market_responds`.

THREE CONVENTIONS THIS HARNESS ESTABLISHES
------------------------------------------
1. **Providers live in `Companies` under a `P0xx` prefix**, with
   `qualification_status = provider_benchmark`. Observations key to `company_id`, so
   sellers need to be entities somewhere; giving them their own sheet would fork the
   Observations foreign key. They are deliberately not marked `excluded` — that value
   means "assessed against the buyer gate and failed", and overloading it would corrupt
   any query counting excluded buyers.

2. **`organizational_state = target_state` for all seller messaging.** The vocabulary
   describes a company's posture toward modernization. A provider's service page is not a
   statement about the provider's own systems; it is a description of the end state it is
   selling to a buyer. `target_state` is the honest mapping, and applying it uniformly
   keeps seller rows from being read as claims about the provider's internal maturity.

3. **`source_grade = B`, never A.** `docs/signal_taxonomy.md` SD-a puts the ceiling at B
   because this is self-promotional content where inflated framing is expected. An
   observation here records what a provider *messages about*, never what it has
   demonstrably delivered. The observation text is phrased to keep that distinction
   visible in the sheet rather than only in this docstring.

WHAT A "CLAIM" IS HERE
----------------------
One Observation per (provider, theme): "this provider markets capability in this
modernization theme." The atomic, checkable unit is the theme's presence on a named,
dated page, and `evidence_excerpt` carries the matched terms plus surrounding phrasing so
a reviewer can disagree with the classification without re-fetching.

Signal strength is a count, not a judgement: one page mentioning a theme is a `weak_clue`;
the same theme across both of a provider's pages, or with several distinct matched terms,
is a `repeated_pattern`. Repetition is the evidence, so — per the redundancy constraint in
attempts_schema_spec.md §11 Q5(b) — the surviving row carries the instance count rather
than the harness discarding duplicates and destroying the basis for the stronger value.

    python -m harnesses.h_sellercontent_01.harness              # dry run
    python -m harnesses.h_sellercontent_01.harness --commit
    python -m harnesses.h_sellercontent_01.harness --offline    # replay from cache
"""

from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.cache import DatedCache, slug  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from core import topics  # noqa: E402

HARNESS_ID = "H-SELLERCONTENT-01"
HARNESS_NAME = "Provider-Market Messaging Extractor"
VERSION = "v1.4"
SIGNAL_TYPE = "seller_service_page"
EVIDENCE_FAMILY = "seller_discourse"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
CONFIG_PATH = Path(__file__).resolve().parent / "sources.json"

UA = ("Mozilla/5.0 (compatible; IndStudy-MarketIntel/1.0; "
      "academic research; +contact via repository)")

# Below this, a 200 response is a shell that renders its content with JavaScript. Marking
# it `js_rendered_unreachable` rather than letting it pass as a thin page keeps the
# coverage number honest and routes the fix correctly — it needs a rendering fetch, not a
# better classifier.
#
# Calibrated against the observed distribution on the seeded provider list rather than
# guessed: genuine prose pages ran 3,000-100,000 chars of visible text, while the two
# known JS shells (Avanade, Hitachi Solutions) sat at 1,239-1,663. A 600 floor let both
# shells through as `covered`, which is how Avanade produced a single theme off two empty
# pages and still reported full coverage. 2,500 separates the two populations with room on
# either side.
MIN_TEXT_CHARS = 2_500

# A theme seen on this many distinct pages, or with this many distinct matched terms,
# is a repeated_pattern rather than a weak_clue.
REPEAT_PAGE_THRESHOLD = 2
REPEAT_TERM_THRESHOLD = 3


# ---------------------------------------------------------------------------- fetching

def visible_text(raw_html: str) -> str:
    """Strip markup to visible prose. No bs4 in this environment, and none needed."""
    s = re.sub(r"<(script|style|noscript|svg)\b.*?</\1>", " ", raw_html, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


class PageResult:
    def __init__(self, url, status=None, text="", error=None, from_cache=False,
                 discovered=False, raw=""):
        self.url, self.status, self.text = url, status, text
        self.raw = raw
        self.error, self.from_cache = error, from_cache
        # True when this page was found by homepage discovery after the configured URL
        # 404'd. Tracked because a discovered page is not necessarily the page the harness
        # was scoped to read -- homepage discovery legitimately returns a sub-industry page
        # or a bare homepage -- and a theme profile built from a substitute is not
        # comparable to one built from a real service page. The run records the
        # substitution instead of letting it disappear into a `covered` row.
        self.discovered = discovered

    @property
    def ok(self) -> bool:
        return self.status == 200 and len(self.text) >= MIN_TEXT_CHARS


class ProviderClient:
    def __init__(self, cache: DatedCache):
        self.cache = cache
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA

    def get(self, url: str) -> PageResult:
        key = slug(url.replace("https://", "").replace("http://", ""))

        def fetch() -> str:
            r = self.session.get(url, timeout=25)
            # The status is stored alongside the body so an offline replay knows a 404 was
            # a 404 and does not silently reclassify it as a parse problem.
            return json.dumps({"status": r.status_code, "body": r.text})

        try:
            payload, from_cache = self.cache.get(key, ".json", fetch)
        except requests.RequestException as e:
            return PageResult(url, error=f"{type(e).__name__}: {e}")
        except RuntimeError as e:                      # offline with nothing archived
            return PageResult(url, error=str(e))
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return PageResult(url, error="cached payload is not valid JSON")
        return PageResult(url, status=data["status"], text=visible_text(data["body"]),
                          from_cache=from_cache, raw=data["body"])

    def discover(self, homepage: str, wanted: tuple[str, ...]) -> list[str]:
        """Find plausible service/industry URLs from a homepage when a configured one 404s.

        Deliberately conservative. It returns candidates for the caller to try, and never
        guesses beyond links the homepage actually contains — the same refuse-to-guess
        posture entity resolution uses elsewhere in this project.
        """
        page = self.get(homepage)
        if page.status != 200 or not page.raw:
            return []
        body = page.raw
        base = re.match(r"^(https?://[^/]+)", homepage).group(1)
        out, seen = [], set()
        for href in re.findall(r'href=["\']([^"\']+)["\']', body):
            low = href.lower()
            if not any(w in low for w in wanted):
                continue
            if href.startswith("/"):
                href = base + href
            if not href.startswith(base) or href in seen:
                continue
            seen.add(href)
            out.append(href.split("#")[0])
        return out[:5]


# ------------------------------------------------------------------------ registration

def ensure_providers(db: MarketIntelDB, providers: list[dict], commit: bool) -> int:
    """Register providers in Companies as P0xx / provider_benchmark. Idempotent."""
    ws = db.wb["Companies"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    existing = {ws.cell(r, 1).value for r in range(2, ws.max_row + 1)}
    added = 0
    for p in providers:
        if p["provider_id"] in existing:
            continue
        values = {
            "company_id": p["provider_id"],
            "canonical_name": p["name"],
            "qualification_status": "provider_benchmark",
            "qualification_confidence_0_1": 1.0,
            "qualification_rationale":
                f"Provider-market benchmark entity ({p['archetype']}), not a buyer "
                f"candidate. Registered by {HARNESS_ID} {VERSION}.",
            "website": p["homepage"],
            "date_added": today(),
            "discovery_source_list": "harnesses/h_sellercontent_01/sources.json",
            "notes": p.get("note", ""),
        }
        ws.append([values.get(h) for h in headers])
        added += 1
    return added


def _partial_reason(results, good, substituted) -> dict:
    """Route a partial run to the failure category that names the actual gap."""
    unusable = [r for r in results if not r.ok]
    if unusable:
        shells = [r for r in unusable if r.status == 200]
        if shells:
            return {"failure_stage": "fetch",
                    "failure_category": "js_rendered_unreachable",
                    "fix_class": "code_change",
                    "failure_detail": f"{len(shells)} of {len(results)} pages returned 200 "
                                      f"with under {MIN_TEXT_CHARS} chars of visible text "
                                      f"— content is JS-rendered"}
        return {"failure_stage": "discovery", "failure_category": "source_not_found",
                "fix_class": "code_change",
                "failure_detail": f"{len(unusable)} of {len(results)} configured pages "
                                  f"unreachable (status "
                                  f"{', '.join(str(r.status) for r in unusable)})"}
    return {"failure_stage": "discovery", "failure_category": "source_not_found",
            "fix_class": "code_change",
            "failure_detail": f"{len(substituted)} page(s) read from homepage-discovery "
                              f"substitutes rather than the configured service page "
                              f"({', '.join(r.url for r in substituted)}); theme profile "
                              f"is not strictly comparable to providers read from their "
                              f"actual service pages"}


# ------------------------------------------------------------------------- observation

def build_observation(provider: dict, theme_key: str, hits: dict, pages: list[str],
                      retrieval: str, low_grade: bool = False) -> Observation:
    """`low_grade` marks a theme admitted only on generic-tier terms (no specific term on
    any page). Under the 2026-09-03 policy it is written at grade C / weak_clue /
    confidence 0.3 with the standard marker, rather than refused."""
    theme = topics.THEMES_BY_KEY[theme_key]
    terms = sorted({t.strip() for page_hits in hits.values() for t in page_hits},
                   key=str.lower)
    n_pages = len(hits)
    strength = ("repeated_pattern"
                if n_pages >= REPEAT_PAGE_THRESHOLD or len(terms) >= REPEAT_TERM_THRESHOLD
                else "weak_clue")

    # Confidence tracks how much text supported the call, not how true the marketing is.
    confidence = 0.75 if strength == "repeated_pattern" else 0.55
    grade = "B"                   # self-promotional ceiling, signal_taxonomy SD-a
    if low_grade:
        strength, confidence, grade = "weak_clue", topics.LOW_GRADE_CONFIDENCE, topics.LOW_GRADE

    detectable = ("" if theme.buyer_detectable else
                  " NOTE: no buyer-side harness can currently detect this theme, so an "
                  "absence of matching buyer evidence is an instrumentation gap rather "
                  "than a demonstrated divergence.")

    text = (
        f"{provider['name']} markets capability in {theme.label} "
        f"({n_pages} of {len(pages)} service page(s) sampled; "
        f"{len(terms)} distinct term(s) matched). This records what the provider "
        f"messages about, not work it has been shown to have delivered.{detectable}"
    )
    excerpt = f"matched terms: {', '.join(terms[:12])}"
    if low_grade:
        excerpt = topics.low_grade_excerpt(
            "generic-tier term(s) only, no specific term on any page read", excerpt)
        text = text.replace("markets capability in",
                            "mentions, on generic terms only, capability in", 1)
    if len(terms) > 12:
        excerpt += f" (+{len(terms) - 12} more)"
    # The specific pages live in the excerpt rather than in source_url -- see below.
    excerpt += " | pages: " + ", ".join(sorted(hits))

    return Observation(
        company_id=provider["provider_id"],
        evidence_family=EVIDENCE_FAMILY,
        evidence_role="provider_market_responds",
        topic=theme_key,
        organizational_state="target_state",
        signal_strength=strength,
        observation_text=text,
        evidence_excerpt=excerpt,
        # The provider homepage, deliberately, NOT the page a theme was matched on.
        #
        # db.py keys a claim on (company_id, harness_id, topic, source_url). Using the
        # matched page made that key unstable: when homepage discovery substituted a
        # different URL between runs, the same logical claim -- "this provider markets
        # ERP capability" -- hashed to a new key and inserted a second row instead of
        # reconciling with the first. The v1.0 -> v1.1 re-run produced 48 rows for 43
        # claims that way, which is idempotency failing silently rather than loudly.
        #
        # The stable identity of this claim is (provider, theme). Which pages evidenced it
        # is a property of the claim, not part of its identity, so it belongs in
        # evidence_excerpt where a reviewer can still check it.
        source_url=provider["homepage"],
        publication_date="",          # marketing pages are rarely dated; left honest
        retrieval_date=retrieval,
        source_grade=grade,
        harness_id=HARNESS_ID,
        harness_version=VERSION,
        confidence_0_1=confidence,
    )


# -------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="H-SELLERCONTENT-01 — seller benchmark")
    ap.add_argument("--commit", action="store_true", help="write rows to the workbook")
    ap.add_argument("--offline", action="store_true", help="replay archived responses only")
    ap.add_argument("--providers", help="comma-separated provider_ids to limit the run")
    ap.add_argument("--retire-stale", action="store_true",
                    help="after syncing, remove this harness's machine rows whose claim "
                         "this run did not reproduce (human-reviewed rows are held, "
                         "never removed). Use after an ADMISSION change in core/topics.py.")
    args = ap.parse_args()

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    providers = cfg["providers"]
    if args.providers:
        want = {p.strip() for p in args.providers.split(",")}
        providers = [p for p in providers if p["provider_id"] in want]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = today()
    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp)
    client = ProviderClient(cache)

    db = MarketIntelDB()
    registered = ensure_providers(db, providers, args.commit)
    if registered:
        print(f"  registered {registered} provider(s) in Companies as provider_benchmark")
    db.vocab = db._load_vocab()

    scope = [(p["provider_id"], SIGNAL_TYPE) for p in providers]
    run = db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME, version=VERSION,
                      primary_family=EVIDENCE_FAMILY, scope=scope,
                      signal_families={SIGNAL_TYPE: EVIDENCE_FAMILY},
                      commit=args.commit)

    proposed: list[Observation] = []
    log = {"harness_id": HARNESS_ID, "version": VERSION, "date": stamp,
           "offline": args.offline, "providers": []}

    for p in providers:
        pid, name = p["provider_id"], p["name"]
        entry = {"provider_id": pid, "name": name, "pages": [], "themes": {},
                 "discovery": []}
        results: list[PageResult] = []

        for page in p["pages"]:
            res = client.get(page["url"])
            # A configured URL that 404s gets one discovery attempt from the homepage
            # before being written off, mirroring the careers-URL discovery gap
            # H-JOBPOST-01 documented rather than repeating it.
            if res.status == 404:
                cands = client.discover(p["homepage"],
                                        ("service", "solution", "capabilit", "industr",
                                         "what-we-do", "consulting"))
                entry["discovery"] = cands
                for c in cands:
                    alt = client.get(c)
                    if alt.ok:
                        print(f"  [~~] {pid} {name}: {page['url']} 404 -> discovered {c}")
                        alt.discovered = True
                        res = alt
                        break
            results.append(res)
            entry["pages"].append({"url": res.url, "status": res.status,
                                   "text_chars": len(res.text), "error": res.error,
                                   "from_cache": res.from_cache,
                                   "discovered": res.discovered})

        good = [r for r in results if r.ok]
        page_urls = [r.url for r in results]

        # ---- outcome determination, before any classification ----
        if not good:
            failing = results[0] if results else None
            if failing is None or failing.error:
                stage, cat, fix = "fetch", "source_unavailable", "transient"
                detail = failing.error if failing else "no pages configured"
            elif failing.status == 404:
                stage, cat, fix = "discovery", "source_not_found", "code_change"
                detail = (f"configured service-page URL returned 404 and homepage "
                          f"discovery found no usable alternative")
            elif failing.status == 200:
                stage, cat, fix = "fetch", "js_rendered_unreachable", "code_change"
                detail = (f"200 response carried only {len(failing.text)} chars of visible "
                          f"text (floor {MIN_TEXT_CHARS}) — content is JS-rendered")
            else:
                stage, cat, fix = "fetch", "access_blocked", "code_change"
                detail = f"HTTP {failing.status}"
            run.attempt(pid, SIGNAL_TYPE, outcome="not_covered", failure_stage=stage,
                        failure_category=cat, fix_class=fix, failure_detail=detail,
                        source_url_attempted=page_urls[0] if page_urls else None,
                        candidates_evaluated=len(results), candidates_discarded=len(results))
            print(f"  [--] {pid} {name}: {cat} — {detail}")
            entry["outcome"] = "not_covered"
            log["providers"].append(entry)
            continue

        # ---- classify ----
        by_theme: dict[str, dict[str, list[str]]] = {}
        weak_by_theme: dict[str, dict[str, list[str]]] = {}
        for r in good:
            for theme_key, (hits, tier) in topics.classify_tiered(r.text).items():
                target = by_theme if tier == "strong" else weak_by_theme
                target.setdefault(theme_key, {})[r.url] = hits
        # A theme with a strong page is a strong claim; its generic-only pages ride along.
        for k in list(weak_by_theme):
            if k in by_theme:
                by_theme[k].update(weak_by_theme.pop(k))

        obs_for_provider = [build_observation(p, k, v, page_urls, stamp)
                            for k, v in sorted(by_theme.items())]
        obs_for_provider += [build_observation(p, k, v, page_urls, stamp, low_grade=True)
                             for k, v in sorted(weak_by_theme.items())]
        entry["themes_low_grade"] = {k: sorted({t for hs in v.values() for t in hs})
                                     for k, v in weak_by_theme.items()}
        proposed.extend(obs_for_provider)
        entry["themes"] = {k: sorted({t for hs in v.values() for t in hs})
                           for k, v in by_theme.items()}

        # A run is `partial` if any configured page was unusable OR if any page that did
        # work was a discovery substitute rather than the page actually scoped for. The
        # second clause is what stops the coverage number from reading 100% on a run where
        # half the providers were read off whatever the homepage happened to link to.
        substituted = [r for r in good if r.discovered]
        partial = len(good) < len(results) or bool(substituted)
        if not obs_for_provider:
            # Reached the source, read real prose, found no modernization theme. That is
            # negative evidence about this provider's positioning, not a miss.
            run.attempt(pid, SIGNAL_TYPE, outcome="absent_confirmed",
                        source_url_attempted=good[0].url,
                        candidates_evaluated=len(results),
                        candidates_discarded=len(results) - len(good))
            print(f"  [00] {pid} {name}: reached {len(good)} page(s), no modernization theme")
            entry["outcome"] = "absent_confirmed"
        else:
            run.attempt(
                pid, SIGNAL_TYPE,
                outcome="partial" if partial else "covered",
                records_written=len(obs_for_provider),
                source_url_attempted=good[0].url,
                candidates_evaluated=len(results),
                candidates_discarded=len(results) - len(good),
                **(_partial_reason(results, good, substituted) if partial else {}),
            )
            flag = "[~~]" if partial else "[ok]"
            print(f"  {flag} {pid} {name}: {len(obs_for_provider)} theme(s) — "
                  f"{', '.join(sorted(by_theme))}")
            entry["outcome"] = "partial" if partial else "covered"
        log["providers"].append(entry)

    # ---- write ----
    report = db.sync_observations(proposed)
    retired = {"removed": [], "held": []}
    if args.retire_stale:
        # Only meaningful over the full provider set: a --providers subset would retire
        # every other provider's rows for not having been proposed.
        if args.providers:
            raise SystemExit("ABORT: --retire-stale needs the full provider set, not --providers")
        retired = db.retire_unreproduced(HARNESS_ID, proposed)
    run.observations_written = report.written
    summary = run.close()

    print()
    print(f"  {summary['companies_processed']} providers · {len(proposed)} observations "
          f"· {cache.fetch_count} HTTP requests")
    print(f"  coverage {summary['coverage_rate']:.0%} "
          f"({summary['attempts_covered']} covered, "
          f"{summary['attempts_absent_confirmed']} absent_confirmed, "
          f"{summary['attempts_partial']} partial, "
          f"{summary['attempts_not_covered']} not_covered)")
    print(f"  dedupe: {report.summary()}")
    if args.retire_stale:
        print(f"  retired: {len(retired['removed'])} unreproduced machine row(s) removed "
              f"[{', '.join(retired['removed'])}]"
              + (f"; {len(retired['held'])} human-reviewed row(s) HELD "
                 f"[{', '.join(retired['held'])}]" if retired["held"] else ""))
    log["retired"] = retired
    if run.derived_known_issues():
        print(f"  issues: {run.derived_known_issues()}")

    log["summary"] = summary
    log["dedupe"] = report.summary()
    log_path = OUTPUT_DIR / f"run-{stamp}{'' if args.commit else '-dryrun'}.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    if args.commit:
        db.save()
        print(f"  committed to market_intel_db.xlsx "
              f"({report.written} rows written, {summary['run_id']})")
    else:
        print("  DRY RUN — nothing written. Re-run with --commit to write.")
    print(f"  run log: {log_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
