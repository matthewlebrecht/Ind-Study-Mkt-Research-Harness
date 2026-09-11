"""
H-JOBPOST-01 — Job Postings Modernization-Signal Extractor
==========================================================

The project's second harness, and the first against a non-API evidence family.

Why this family is worth the difficulty: job postings are one of the few sources where a
private mid-size company exposes nearly as much as a public one. A company that will never
file with the SEC still has to describe, publicly and in detail, the systems it is trying
to staff. That makes hiring one of the strongest available windows into modernization
posture for exactly the companies this project studies, and the taxonomy ranks 3a the
project's single highest-value family.

Why it is hard: there is no registry. Each company publishes on whichever ATS it licenses,
so coverage is per-company integration work, and the honest output includes the companies
the harness could *not* reach. Adapters and gaps sit side by side in sources.json and gaps
are reported every run.

v1.1 (2026-09-01) — SCOPE EXPANSION, NOT A REBUILD
--------------------------------------------------
v1.0 ran against 7 pilot companies with three hand-configured adapters. v1.1 runs the full
108 and adds what that requires, without touching what already worked:

  * CAREERS-URL DISCOVERY (discovery.py), own domain only. The Anvil-100 have no careers
    URL on file, so v1.0's run on 2026-08-30 walked all 107 companies and reported "no
    source configured" 104 times.
  * TWO MORE ADAPTERS, greenhouse and lever, both keyless JSON board APIs, added because
    discovery found them rather than on a guess about what is popular.
  * A HARDENED CLASSIFIER (classifier v1.0 -> v1.1). At Kenco only 5 of 467 postings were
    genuine, so a term firing on 1% of ordinary postings produces more false rows than the
    harness produces true ones. See classifier.py for the seven false positives that
    motivated the term model.
  * THE ATTEMPTS RUN-CONTEXT. v1.0 predates core/attempts.py and wrote no Attempts rows at
    all, which is why HR-0005 has no coverage denominator and published no coverage rate.
  * THE TWO SOURCE LEGS SEPARATED. A blocked leg and an open leg must not share a
    denominator, so the third-party job boards are their own declared signal.

THE THIRD-PARTY BOARD LEG IS CLOSED, AND IT IS DECLARED RATHER THAN DROPPED
--------------------------------------------------------------------------
Probed 2026-09-01: LinkedIn publishes `Disallow: /` for this crawler identity, and Indeed
disallows `/jobs`, `/viewjob?` and `/cmp/`. Every job-posting path on both is refused, so
own-domain careers pages are not merely the primary leg but the only open one.

That is recorded as the sources' own published decisions (convention 38, the Glassdoor
precedent) against a signal declared in scope, so the finding has a denominator. No
user-agent is switched, no authenticated access is attempted, and no third-party mirror is
substituted: an evaded refusal is not access.

Pipeline
--------
    Companies sheet -> careers-URL discovery (own domain) -> per-company ATS adapter
                    -> classify each posting into modernization signals
                    -> aggregate to per-company claims -> Observations

Evidence mapping
----------------
    evidence_family    3_workforce_org_exhaust — hiring is workforce exhaust. A posting
                       naming an enterprise system also carries taxonomy 5b, which the
                       taxonomy says belongs as a FIELD on this harness rather than a
                       separate family-5 harness.
    evidence_role      buyer_acts. Posting a role is an action, not a statement of intent.
    organizational_state
                       active_transition, per project convention 2: hiring for these roles
                       is a positive modernization signal but NOT proof of an established
                       in-house capability.
    signal_strength    weak_clue for a single posting; repeated_pattern at 3+ (a cluster is
                       a program, not a backfill); committed_action when a leadership title
                       appears, because staffing a mandate outranks staffing a seat.
    source_grade       A — first-party, published by the company, attributable to its own
                       careers page. This is why discovery refuses a third-party board.

These observations are point-in-time by nature: hiring changes weekly, so a re-run is
*expected* to update them, unlike the FMCSA rows. The claim text always states its as-of
date, and the row reflects the latest run.

Usage
-----
    python harnesses/h_jobpost_01/harness.py                 # dry run, full universe
    python harnesses/h_jobpost_01/harness.py --pilot         # the 15-company checkpoint
    python harnesses/h_jobpost_01/harness.py --commit
    python harnesses/h_jobpost_01/harness.py --offline       # replay archived responses
    python harnesses/h_jobpost_01/harness.py --companies C0006
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402

from core.attempts import access_detail  # noqa: E402
from core.cache import DatedCache, slug  # noqa: E402
from core.db import MarketIntelDB, Observation, today  # noqa: E402
from core.robots import RobotsGate  # noqa: E402
from core import topics  # noqa: E402
from harnesses.h_jobpost_01 import aggregator as agg  # noqa: E402
from harnesses.h_jobpost_01 import discovery as disc  # noqa: E402
from harnesses.h_jobpost_01.classifier import SIGNALS_BY_KEY, get_classifier  # noqa: E402
from harnesses.h_jobpost_01.source import USER_AGENT, JobSourceClient  # noqa: E402

HARNESS_ID = "H-JOBPOST-01"
HARNESS_NAME = "Job Postings Modernization-Signal Extractor"
HARNESS_VERSION = "v1.4"
FAMILY_3 = "3_workforce_org_exhaust"
FAMILY_5 = "5_technology_stack_traces"

# The two legs, kept as separate declared signals so they never share a denominator.
SIGNAL_OWN = "job_posting"                    # own-domain careers pages (SRC-0049)
SIGNAL_BOARD = "job_board_third_party"        # LinkedIn (SRC-0009) + Indeed (SRC-0010)
SIGNAL_SYSTEM = "job_posting_system_mention"  # taxonomy 5b, a field on this harness

# Third-party boards, probed rather than assumed. Both refuse this crawler identity on
# every job-posting path; the URLs are the ones actually checked.
BOARD_PROBES = (
    ("LinkedIn", "https://www.linkedin.com/jobs/search/?keywords=engineer"),
    ("Indeed", "https://www.indeed.com/jobs?q=engineer"),
)

# The 15-company pilot for the internal checkpoint. Chosen to span the industry mix AND to
# front-load the companies most likely to break the classifier: Prime Inc. (a name that
# reduces to one common token), Leprino and SpartanNash (food distribution, where "lean"
# is an ordinary adjective), Merit Medical (where API means Active Pharmaceutical
# Ingredient), and Kenco (the regression anchor whose 5-of-467 ratio is the known good).
PILOT = ["C0001", "C0003", "C0004", "C0006", "A005", "A011", "A018", "A029", "A030",
         "A032", "A036", "A045", "A048", "A050", "A054"]

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "harness_output" / HARNESS_ID
CONFIG_PATH = Path(__file__).resolve().parent / "sources.json"
# Discovered configs live apart from the hand-curated ones so a machine write can never
# clobber a human's. sources.json stays authoritative where both hold a company.
DISCOVERED_PATH = Path(__file__).resolve().parent / "discovered.json"

# --- named quality gates ---
CLUSTER_FOR_PATTERN = 3      # postings in one signal before it reads as a program
MIN_POSTINGS_FOR_VOLUME = 5  # below this, total open roles is too thin to characterize
MAX_EXCERPT_TITLES = 4

# Signals whose match implies the posting named an enterprise system (taxonomy 5b).
SYSTEM_SIGNALS = {"erp_core_systems_hiring", "warehouse_systems_automation_hiring",
                  "transportation_systems_hiring",
                  # 2026-09-02: a cloud platform and a control system are both enterprise
                  # systems named in the posting (taxonomy 5b). Security and workforce
                  # roles describe a function, not a system, and stay family 3.
                  "cloud_infrastructure_hiring", "ot_modernization_hiring"}


def _confidence(count: int, leadership: bool, truncated: bool) -> float:
    conf = 0.55 if count == 1 else 0.70 if count < CLUSTER_FOR_PATTERN else 0.85
    if leadership:
        conf += 0.05
    if truncated:
        conf -= 0.05  # counts are lower bounds, so the claim is directionally safe but partial
    return max(0.3, min(conf, 0.95))


class CompanyResult:
    def __init__(self, company: dict):
        self.company = company
        self.company_id = company["company_id"]
        self.name = company["canonical_name"]
        self.postings = []
        self.by_signal: dict[str, list] = {}
        self.by_signal_weak: dict[str, list] = {}     # session 10 (J13): low-grade tier
        self.weak_terms: dict[str, set] = {}
        self.leadership: dict[str, bool] = {}
        self.matched_terms: dict[str, set] = {}
        self.rejected_terms: dict[str, str] = {}
        self.truncated = False
        self.reported_total = None
        self.notes: list[str] = []
        self.error = ""


def collect(client: JobSourceClient, classifier, company: dict, config: dict) -> CompanyResult:
    result = CompanyResult(company)
    fetched = client.fetch(result.company_id, config)
    result.postings = fetched.postings
    result.truncated = fetched.truncated
    result.notes = list(fetched.notes)
    result.reported_total = fetched.reported_total
    classify_postings(result, classifier)
    return result


def classify_postings(result: CompanyResult, classifier) -> CompanyResult:
    """Run the classifier over `result.postings`; shared by the own-domain and board legs
    so a posting means the same thing whichever source it came from."""
    for posting in result.postings:
        classification = classifier.classify(posting.text)
        result.rejected_terms.update(getattr(classification, "rejected", {}) or {})
        for key in classification.signals:
            result.by_signal.setdefault(key, []).append(posting)
            result.leadership[key] = result.leadership.get(key, False) or classification.is_leadership
            result.matched_terms.setdefault(key, set()).update(
                classification.matched_terms.get(key, []))
        for key in getattr(classification, "weak_signals", []) or []:
            if key in classification.signals:
                continue
            result.by_signal_weak.setdefault(key, []).append(posting)
            result.weak_terms.setdefault(key, set()).update(
                classification.weak_terms.get(key, []))
    return result


def build_observations(result: CompanyResult, config: dict, stamp: str,
                       classifier, *, source_label: str = "its own careers site",
                       source_grade: str = "A", volume: bool = True) -> list[Observation]:
    """`source_label` / `source_grade` / `volume` distinguish the two legs. The own-domain
    leg is first-party and A-graded and its posting count is the company's own. The
    aggregator leg is a cross-post (second-hand, B), and its count is how many
    requisitions the aggregator happened to index, which is not a hiring volume."""
    out: list[Observation] = []
    careers_url = config["careers_url"]

    def obs(topic, state, strength, text, excerpt, confidence, family=FAMILY_3,
            grade: str = "") -> Observation:
        return Observation(
            company_id=result.company_id,
            evidence_family=family,
            evidence_role="buyer_acts",
            topic=topic,
            organizational_state=state,
            signal_strength=strength,
            observation_text=text,
            evidence_excerpt=excerpt,
            source_url=careers_url,
            publication_date=stamp,   # a live board: as-of date is the publication date
            retrieval_date=stamp,
            source_grade=grade or source_grade,
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            confidence_0_1=round(confidence, 2),
        )

    total = len(result.postings)
    reported = result.reported_total

    # 1. Hiring volume — context for every signal claim below it. Own-domain leg only:
    #    an aggregator's index size is not the company's open-role count.
    if volume and total:
        volume_txt = (f"{reported:,} open postings (this run read {total:,})"
                      if reported and reported > total else f"{total:,} open postings")
        below = total < MIN_POSTINGS_FOR_VOLUME
        vol_excerpt = (f"Source: {careers_url} ({config['ats']}); postings counted {stamp}: {total}"
                       + (f"; ATS reported total: {reported}" if reported else ""))
        if below:
            # Session 10 item 7 (J6): under the characterisation floor the count is thin
            # context, not nothing -- written at low grade under convention 41.
            vol_excerpt = topics.low_grade_excerpt(
                f"{total} posting(s), below the {MIN_POSTINGS_FOR_VOLUME}-posting "
                f"characterisation floor", vol_excerpt)
        out.append(obs(
            "open_roles_volume", "unknown", "weak_clue",
            f"{result.name} listed {volume_txt} on {source_label} as of {stamp}, via "
            f"{config['ats'].title()}. This is scale context for the hiring-signal "
            f"observations alongside it, not a modernization signal on its own."
            + (" Below the floor this harness uses to characterise hiring volume." if below else ""),
            vol_excerpt, topics.LOW_GRADE_CONFIDENCE_MAX if below else 0.8,
            grade=topics.LOW_GRADE if below else ""))

    # 2. One claim per modernization signal that actually appeared.
    for key, postings in sorted(result.by_signal.items(),
                                key=lambda kv: len(kv[1]), reverse=True):
        signal = SIGNALS_BY_KEY[key]
        count = len(postings)
        leadership = result.leadership.get(key, False)
        strength = ("committed_action" if leadership
                    else "repeated_pattern" if count >= CLUSTER_FOR_PATTERN
                    else "weak_clue")
        titles = [p.title for p in postings][:MAX_EXCERPT_TITLES]
        more = f" (+{count - len(titles)} more)" if count > len(titles) else ""
        lead_txt = (" At least one is a leadership role, which indicates a staffed mandate "
                    "rather than an individual opening." if leadership else "")
        trunc_txt = (" Counts are lower bounds — this run did not read every posting."
                     if result.truncated else "")
        terms = ", ".join(sorted(result.matched_terms.get(key, []))[:6])
        # Taxonomy 5b: a posting naming an enterprise system is a technology-stack trace as
        # well as workforce exhaust. Carried as the row's family rather than as a separate
        # harness, per docs/signal_taxonomy.md §5 ("merge into 3a, don't build new").
        family = FAMILY_5 if key in SYSTEM_SIGNALS else FAMILY_3
        out.append(obs(
            key, "active_transition", strength,
            f"{result.name} is advertising {count} open role{'s' if count != 1 else ''} "
            f"in {signal.label} on {source_label} as of {stamp}: "
            f"{'; '.join(titles)}{more}.{lead_txt} {signal.rationale}{trunc_txt} "
            f"Hiring indicates a transition underway, not an established in-house "
            f"capability (project convention 2).",
            f"Matched terms: {terms}. Titles: {'; '.join(titles)}{more}. "
            f"Source: {careers_url}; classifier {classifier.name} {classifier.version}",
            _confidence(count, leadership, result.truncated), family))

    # 3. Session 10 item 7 (J13): signals carried only by a vendor/estate term without
    #    migration language. Low grade: the reviewer decides whether "AWS" in a req is a
    #    migration or a logo.
    for key, postings in sorted(result.by_signal_weak.items(),
                                key=lambda kv: len(kv[1]), reverse=True):
        if key in result.by_signal:
            continue
        signal = SIGNALS_BY_KEY[key]
        titles = [p.title for p in postings][:MAX_EXCERPT_TITLES]
        terms = ", ".join(sorted(result.weak_terms.get(key, []))[:6])
        family = FAMILY_5 if key in SYSTEM_SIGNALS else FAMILY_3
        out.append(obs(
            key, "unknown", "weak_clue",
            f"{result.name} is advertising {len(postings)} open role(s) on {source_label} "
            f"as of {stamp} that name a cloud vendor or legacy-estate term without "
            f"migration or modernization language: {'; '.join(titles)}. Vendor named, "
            f"programme not asserted; {signal.rationale}",
            topics.low_grade_excerpt(
                "vendor or estate term without migration language (J13)",
                f"Matched terms: {terms}. Titles: {'; '.join(titles)}. Source: {careers_url}; "
                f"classifier {classifier.name} {classifier.version}"),
            topics.LOW_GRADE_CONFIDENCE_MAX, family, grade=topics.LOW_GRADE))
    return out


def load_configs() -> tuple[dict, dict, dict]:
    doc = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    discovered = {}
    if DISCOVERED_PATH.exists():
        discovered = json.loads(DISCOVERED_PATH.read_text(encoding="utf-8")).get(
            "sources", {})
    return doc["sources"], doc["gaps"], discovered


def run(args) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = today()
    disc.set_stamp(stamp)
    curated, gaps, discovered = load_configs()

    cache = DatedCache(OUTPUT_DIR / "raw", offline=args.offline, retrieval_date=stamp,
                       pause_seconds=0.0 if args.offline else 0.7)
    client = JobSourceClient(cache)
    classifier = get_classifier(args.classifier)
    gate = RobotsGate()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    db = MarketIntelDB()

    statuses = ("qualified", "pending_review", "soft_gate_exception")
    companies = db.companies(statuses)
    if args.pilot:
        companies = [c for c in companies if c["company_id"].upper() in set(PILOT)]
    if args.companies:
        wanted = {c.strip().upper() for c in args.companies.split(",")}
        companies = [c for c in companies if c["company_id"].upper() in wanted]

    print(f"{HARNESS_ID} {HARNESS_VERSION} — {len(companies)} companies, classifier="
          f"{classifier.name} {classifier.version} "
          f"({'offline replay' if args.offline else 'live'})\n")

    # Both legs are declared for every company, so the blocked one has a denominator of
    # its own and the open one is never credited with its coverage.
    scope = [(c["company_id"], s) for c in companies for s in (SIGNAL_OWN, SIGNAL_BOARD)]

    def fetch_page(url: str, key: str) -> tuple:
        """Own-domain page fetch for discovery. Robots-checked, cached, never raises."""
        allowed, why = (True, "")
        try:
            allowed, why = gate.check(url)
        except Exception:
            pass                      # a robots fetch failure is not the page's verdict
        if not allowed:
            return "", f"robots:{why}"
        try:
            body, _ = cache.get(key, ".html",
                                lambda: session.get(url, timeout=30,
                                                    allow_redirects=True).text)
            return body, 200
        except Exception as exc:
            return "", f"{type(exc).__name__}"

    all_obs: list[Observation] = []
    log: list[dict] = []
    covered = 0
    board_refusals = 0

    with db.open_run(harness_id=HARNESS_ID, harness_name=HARNESS_NAME,
                     version=HARNESS_VERSION, primary_family=FAMILY_3, scope=scope,
                     signal_families={SIGNAL_OWN: FAMILY_3, SIGNAL_BOARD: FAMILY_3},
                     commit=args.commit) as run_ctx:
        # Audit gate: a new version's output is quarantined until an artifact exists.
        run_ctx.publication_status = "quarantined"

        # ---- the third-party board leg: probe every board, run the ones that permit us ----
        #
        # v1.1-v1.2 recorded only the refusals. v1.3 (2026-09-03) probes twelve boards
        # and runs an adapter for each one that both permits this crawler identity by
        # robots.txt AND answers without a bot challenge -- Talent.com today. The refused
        # boards are still recorded per company, as the sources' own decision
        # (convention 38), so the leg's denominator says what was tried.
        probes = agg.probe_boards(gate)
        refused = [p for p in probes if not p.allowed]
        runnable = [p for p in probes if p.allowed and p.adapter == "talent"]
        board_note = "; ".join(f"{p.board}: {p.why}" for p in refused) or "no refusal recorded"
        print(f"  third-party boards: {len(refused)}/{len(probes)} refuse this crawler "
              f"identity; {len(runnable)} runnable adapter(s): "
              f"{', '.join(p.board for p in runnable) or 'none'}")
        for p in probes:
            print(f"      {'REFUSED' if not p.allowed else 'allowed':<8} {p.board}: "
                  f"{(p.why or ('adapter: ' + p.adapter if p.adapter else 'no adapter'))[:88]}")
        print()
        talent = agg.TalentClient(cache, session, gate) if runnable else None
        legs = {x.strip() for x in (args.legs or "own,board").split(",")}
        board_refused_url = refused[0].url if refused else agg.BOARDS[0][1]

        for company in companies:
            cid, name = company["company_id"], company["canonical_name"]

            if "board" not in legs:
                pass                       # declared in scope; close() records the gap
            elif talent is None:
                run_ctx.attempt(
                    cid, SIGNAL_BOARD, outcome="not_covered",
                    failure_stage="fetch", failure_category="access_blocked",
                    failure_detail=access_detail(
                        "source_refusal",
                        f"{len(refused)} of {len(probes)} third-party job boards refuse "
                        f"this crawler identity by published robots.txt policy and no "
                        f"permitted board has a working adapter. {board_note}. Recorded "
                        f"as the sources' own decision (convention 38). No user-agent "
                        f"switched, no authenticated access, no third-party mirror: an "
                        f"evaded refusal is not access."),
                    fix_class="source_limitation",
                    source_url_attempted=board_refused_url)
                board_refusals += 1
            else:
                res = talent.search(company)
                bres = CompanyResult(company)
                bres.postings = res.postings
                bres.truncated = res.truncated
                bres.notes = list(res.notes)
                classify_postings(bres, classifier)
                refusal_txt = (f" {len(refused)} of {len(probes)} other boards refuse this "
                               f"crawler identity by robots.txt ({board_note}); recorded as "
                               f"their decision (convention 38).")
                bobs: list[Observation] = []
                if res.error and not res.postings:
                    cat = "access_blocked" if res.error.startswith("robots") else "source_unavailable"
                    run_ctx.attempt(cid, SIGNAL_BOARD, outcome="not_covered",
                                    failure_stage="fetch", failure_category=cat,
                                    failure_detail=(f"Talent.com search failed: {res.error}."
                                                    + refusal_txt)[:500],
                                    fix_class="transient" if cat == "source_unavailable" else "source_limitation",
                                    source_url_attempted=res.search_url)
                    print(f"  [!!] {cid} {name} (talent.com): {res.error[:80]}")
                elif not res.postings and res.candidates_seen:
                    top = "; ".join(f"{e!r} ({sc})" for e, sc, _ in res.rejected[:4])
                    run_ctx.attempt(cid, SIGNAL_BOARD, outcome="not_covered",
                                    failure_stage="entity_resolution",
                                    failure_category="entity_below_threshold",
                                    failure_detail=(f"Talent.com returned {res.candidates_seen} "
                                                    f"card(s) for {res.query!r} across "
                                                    f"{res.pages_read} page(s) and none carries "
                                                    f"an employer resolving to the company "
                                                    f"(floor {agg.DEFAULT_FLOOR}); e.g. {top}."
                                                    + refusal_txt)[:500],
                                    fix_class="source_limitation",
                                    source_url_attempted=res.search_url,
                                    candidates_evaluated=res.candidates_seen,
                                    candidates_discarded=res.candidates_seen)
                    print(f"  [--] {cid} {name} (talent.com): {res.candidates_seen} cards, "
                          f"none resolve to the company")
                elif not res.postings:
                    run_ctx.attempt(cid, SIGNAL_BOARD, outcome="absent_confirmed",
                                    source_url_attempted=res.search_url,
                                    candidates_evaluated=0)
                    print(f"  [00] {cid} {name} (talent.com): no cross-posts indexed")
                else:
                    bobs = build_observations(
                        bres, {"careers_url": res.search_url, "ats": "talent.com"}, stamp,
                        classifier, source_label=("Talent.com, a job aggregator that "
                                                  "cross-posts the company's requisitions"),
                        source_grade="B", volume=False)
                    all_obs.extend(bobs)
                    if bobs:
                        run_ctx.attempt(cid, SIGNAL_BOARD, outcome="covered",
                                        records_written=len(bobs), output_sheet="Observations",
                                        source_url_attempted=res.search_url,
                                        candidates_evaluated=res.candidates_seen,
                                        candidates_discarded=res.candidates_seen - len(res.postings))
                    else:
                        run_ctx.attempt(cid, SIGNAL_BOARD, outcome="absent_confirmed",
                                        source_url_attempted=res.search_url,
                                        candidates_evaluated=res.candidates_seen,
                                        candidates_discarded=res.candidates_seen - len(res.postings))
                    print(f"  [  ] {cid} {name} (talent.com) -> {len(res.postings)} of "
                          f"{res.candidates_seen} cards resolve, {len(bobs)} observations"
                          + (" [truncated]" if res.truncated else ""))
                    for o in bobs:
                        print(f"          - {o.topic} [{o.signal_strength}] conf={o.confidence_0_1}")
                log.append({"company_id": cid, "canonical_name": name, "leg": "board",
                            "board": "talent.com", "query": res.query,
                            "search_url": res.search_url, "pages_read": res.pages_read,
                            "cards_seen": res.candidates_seen,
                            "resolved": len(res.postings), "truncated": res.truncated,
                            "error": res.error,
                            "rejected_employers": res.rejected[:20],
                            "signals": {k: [p.title for p in v] for k, v in bres.by_signal.items()},
                            "observations": [{"topic": o.topic, "signal_strength": o.signal_strength,
                                              "confidence_0_1": o.confidence_0_1} for o in bobs]})

            if "own" not in legs:
                continue

            # ---- the open leg ----
            config = curated.get(cid) or discovered.get(cid)
            found = None
            # Session 10 item 7: re-discover when the stored config cannot be acted on --
            # no config, an ATS with no adapter (an inline list may sit behind it), or an
            # ADP host whose client id was never captured. Curated configs are never
            # overridden.
            needs_discovery = (not config
                               or (cid not in curated
                                   and (config.get("ats") not in disc.IMPLEMENTED_ATS
                                        or (config.get("ats") == "adp" and not config.get("cid")))))
            if needs_discovery and not args.offline:
                found = disc.discover(cid, company.get("website") or "", fetch_page)
                if found.careers_url:
                    discovered[cid] = found.as_config()
                    config = discovered[cid]

            if not config or config.get("ats") not in disc.IMPLEMENTED_ATS or (
                    config.get("ats") == "adp" and not config.get("cid")):
                if config and config.get("careers_url"):
                    ats = config.get("ats") or ""
                    reason = (f"careers page found at {config['careers_url']} but its ATS "
                              f"({ats or 'none detected in server-rendered HTML'}) has no "
                              f"adapter")
                    cat, stage = "content_unstructured", "extraction"
                    if ats in disc.ROBOTS_REFUSED_BOARDS:
                        # Session 10 item 7: not an adapter gap -- the board's host refuses
                        # this crawler by robots.txt (probed 2026-09-03). The source's own
                        # decision (convention 38), routed to the right fix class.
                        reason = (f"careers page found at {config['careers_url']}; postings "
                                  f"are hosted on {ats}, whose host refuses this crawler "
                                  f"identity by published robots.txt policy (probed "
                                  f"2026-09-03). No user-agent switched, no mirror: an "
                                  f"evaded refusal is not access.")
                        cat, stage = "access_blocked", "fetch"
                    elif ats == "adp":
                        reason = (f"careers page found at {config['careers_url']} on ADP "
                                  f"Workforce Now, but the client id was not present in the "
                                  f"server-rendered page, so the requisition endpoint cannot "
                                  f"be addressed")
                else:
                    reason = (found.evidence if found else
                              gaps.get(cid, "no careers source configured or discovered"))
                    cat, stage = "source_not_found", "discovery"
                print(f"  [--] {cid} {name}: {reason[:96]}")
                run_ctx.attempt(cid, SIGNAL_OWN, outcome="not_covered",
                                failure_stage=stage, failure_category=cat,
                                failure_detail=reason[:500],
                                fix_class=("source_limitation" if cat == "access_blocked"
                                           else "code_change"),
                                source_url_attempted=(company.get("website") or ""))
                log.append({"company_id": cid, "canonical_name": name, "covered": False,
                            "gap_reason": reason,
                            "tried": found.tried if found else [],
                            "rejected": found.rejected if found else []})
                continue

            try:
                result = collect(client, classifier, company, config)
            except Exception as exc:
                msg = (f"{config.get('ats')} adapter failed — "
                       f"{type(exc).__name__}: {exc}")
                print(f"  [!!] {cid} {name}: {msg[:100]}")
                run_ctx.attempt(cid, SIGNAL_OWN, outcome="not_covered",
                                failure_stage="fetch",
                                failure_category="source_unavailable",
                                failure_detail=msg[:500], fix_class="code_change",
                                source_url_attempted=config.get("careers_url", ""))
                log.append({"company_id": cid, "canonical_name": name, "covered": False,
                            "error": str(exc)})
                continue

            observations = build_observations(result, config, stamp, classifier)
            all_obs.extend(observations)
            covered += 1

            # A careers page reached and READ, listing no modernization role, is a
            # confirmed absence rather than a miss (convention 6): the authoritative
            # first-party source was reached and it is complete for this signal.
            #
            # But ZERO POSTINGS IS NOT THAT, and the distinction is convention 6a --
            # asserting absence after a lookup that did not work writes false negative
            # evidence, which is worse than a gap because it carries weight. Two live
            # cases in this run proved it rather than suggesting it: IPS-Integrated
            # Project Services' iCIMS portal answers with a 175-byte JavaScript redirect
            # to careers.ipsdb.com, and McShane's Paylocity careers page is 79KB
            # containing zero job links because the list is loaded client-side. Both
            # parse to 0 postings. A mid-size company with literally no open roles is
            # possible; two of them via different adapters on the same evening is an
            # adapter result, not a hiring fact.
            #
            # So absence is claimed only where a board was actually read. An empty parse
            # is an extraction gap and says so.
            if observations:
                run_ctx.attempt(cid, SIGNAL_OWN, outcome="covered",
                                records_written=len(observations),
                                output_sheet="Observations",
                                source_url_attempted=config["careers_url"],
                                candidates_evaluated=len(result.postings))
            elif result.postings:
                run_ctx.attempt(cid, SIGNAL_OWN, outcome="absent_confirmed",
                                source_url_attempted=config["careers_url"],
                                candidates_evaluated=len(result.postings))
            else:
                run_ctx.attempt(
                    cid, SIGNAL_OWN, outcome="not_covered",
                    failure_stage="extraction",
                    failure_category="content_unstructured",
                    failure_detail=(
                        f"{config['ats']} adapter parsed 0 postings from "
                        f"{config['careers_url']}. NOT recorded as absent_confirmed: a "
                        f"board that yields nothing is an extraction result, not "
                        f"evidence that the company is not hiring (convention 6a). "
                        f"Usually a client-side-rendered list or a redirect to another "
                        f"host."),
                    fix_class="code_change",
                    source_url_attempted=config["careers_url"])

            print(f"  [  ] {cid} {name} ({config['ats']}) -> {len(result.postings)} "
                  f"postings, {len(observations)} observations")
            for o in observations:
                print(f"          - {o.topic} [{o.signal_strength}] conf={o.confidence_0_1}")

            log.append({
                "company_id": cid, "canonical_name": name, "covered": True,
                "ats": config["ats"], "careers_url": config["careers_url"],
                "postings_read": len(result.postings),
                "ats_reported_total": result.reported_total,
                "truncated": result.truncated,
                "signals": {k: [p.title for p in v] for k, v in result.by_signal.items()},
                "rejected_terms": result.rejected_terms,
                "unmatched_sample": [p.title for p in result.postings
                                     if not any(p in v for v in result.by_signal.values())][:10],
                "observations": [{"topic": o.topic, "signal_strength": o.signal_strength,
                                  "confidence_0_1": o.confidence_0_1,
                                  "observation_text": o.observation_text}
                                 for o in observations],
            })

        print(f"\n  covered {covered}/{len(companies)} companies · {len(all_obs)} "
              f"observations · {cache.fetch_count} HTTP requests")

        report = db.sync_observations(all_obs)
        # The run context initialises this to 0 and never updates it -- it is the
        # harness's job to report what it wrote. Omitting it made HR-0032/0033 claim
        # observations_produced_count = 0 while 21 rows sat in the sheet at this version,
        # which is a run row contradicting the evidence base it produced.
        run_ctx.observations_written = report.written
        print(f"  dedupe: {report.summary()}")
        for c in report.conflicts:
            print(f"    [conflict] {c['observation_id']} {c['company_id']}/{c['topic']} "
                  f"is '{c['review_status']}' — content changed, left as-is for review")

    summary = run_ctx.summary

    # PER-LEG COVERAGE, and the blended figure is deliberately not quoted as the headline.
    # The run declares two signals with opposite access profiles: the own-domain leg can
    # be improved by building adapters, the third-party board leg cannot be improved at
    # all because both boards refuse this crawler identity. A single rate over the two
    # says nothing actionable about either -- it just drifts toward 50% as the open leg
    # improves, which is the denominator-sharing the brief ruled out.
    per_leg: dict[str, dict] = {}
    from core.attempts import COVERAGE_OUTCOMES as _COV
    for a in run_ctx.attempts:
        if a.scope != "scoped":
            continue
        leg = per_leg.setdefault(a.attempted_signal, {"n": 0, "covered": 0})
        leg["n"] += 1
        leg["covered"] += 1 if a.outcome in _COV else 0
    print(f"  attempts: {summary['attempts_total']}")
    for sig, d in sorted(per_leg.items()):
        rate = d["covered"] / d["n"] if d["n"] else 0.0
        note = ("  <- aggregators that permit this crawler (Talent.com); the major boards refuse"
                if sig == SIGNAL_BOARD else "")
        print(f"      {sig:<24} {d['covered']:>3}/{d['n']:<4} {rate:6.1%}{note}")
    print(f"      (blended run coverage_rate is {summary['coverage_rate']:.1%} and is NOT "
          f"the number to quote -- the legs have different ceilings)")

    if args.commit:
        DISCOVERED_PATH.write_text(json.dumps(
            {"_readme": [
                "Careers sources DISCOVERED by harnesses/h_jobpost_01/discovery.py.",
                "Machine-written; sources.json is hand-curated and wins where both hold",
                "a company. Every entry was found on the company's own registrable",
                "domain -- a third-party job board is never accepted as a careers page,",
                "because source_grade A on this harness means the claim is attributable",
                "to the company's own page."],
             "sources": dict(sorted(discovered.items()))}, indent=2), encoding="utf-8")
        db.save()
        print(f"  committed to {db.path.name} ({report.written} rows written, "
              f"{run_ctx.run_id})")
    else:
        print("  DRY RUN — nothing written. All rows passed schema validation. "
              "Re-run with --commit to write.")

    tag = "pilot" if args.pilot else "full"
    log_path = OUTPUT_DIR / f"run-{stamp}-{tag}{'' if args.commit else '-dryrun'}.json"
    log_path.write_text(json.dumps({
        "harness_id": HARNESS_ID, "harness_version": HARNESS_VERSION, "date_run": stamp,
        "committed": bool(args.commit), "pilot": bool(args.pilot),
        "classifier": {"name": classifier.name, "version": classifier.version},
        "board_leg": {"probes": [{"board": p.board, "allowed": p.allowed, "why": p.why,
                                  "adapter": p.adapter} for p in probes],
                      "companies_recorded_refused": board_refusals},
        "coverage": {"companies_processed": len(companies),
                     "companies_covered": covered,
                     "attempts": summary, "per_leg": per_leg},
        "thresholds": {"cluster_for_pattern": CLUSTER_FOR_PATTERN,
                       "min_postings_for_volume": MIN_POSTINGS_FOR_VOLUME},
        "sync": {"inserted": [o.observation_id for o in report.inserted],
                 "updated": [o.observation_id for o in report.updated],
                 "unchanged": [o.observation_id for o in report.unchanged],
                 "conflicts": report.conflicts},
        "company_log": log,
    }, indent=2), encoding="utf-8")
    print(f"  run log: {log_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=f"{HARNESS_ID} — {HARNESS_NAME}")
    p.add_argument("--commit", action="store_true", help="write rows to the workbook")
    p.add_argument("--offline", action="store_true", help="replay archived responses only")
    p.add_argument("--companies", help="comma-separated company_ids to limit the run")
    p.add_argument("--legs", default="own,board",
                   help="which legs to run: own, board, or own,board (default). A leg not "
                        "run is still declared and closes as not_covered.")
    p.add_argument("--pilot", action="store_true",
                   help="the 15-company industry-spanning checkpoint set")
    p.add_argument("--classifier", default="rules", choices=["rules", "llm"],
                   help="classification strategy (default: rules)")
    return run(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
