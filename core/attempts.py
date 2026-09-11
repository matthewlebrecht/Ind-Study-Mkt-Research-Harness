"""
Attempt emission, driven by a run context.

`docs/schema/attempts_schema_spec.md` §7 states a completeness requirement: a harness must
write exactly one `Attempts` row for every `(company, signal)` pair it was scoped to try,
*including pairs it skipped early*. A skip is `not_covered` with a stage and a category,
never a missing row, because a missing row silently recreates the denominator problem the
table exists to solve.

`repo_structure_spec.md` §3 makes the point that matters here: stated as a rule, that
requirement fails the first time someone adds a harness with an early `continue` in a loop.
So it is not a rule. A harness *declares* its scope when it opens a run, and the run
context reconciles the declaration against what was actually emitted when the run closes.
Anything declared but never attempted is written as `not_covered` / `discovery` /
`source_not_found` automatically, and flagged in the run summary so the omission is loud.

Typical use:

    with db.open_run(
        harness_id="H-SAFETY-ENV-01",
        harness_name="OSHA + EPA ECHO Compliance Extractor",
        version="v1.0",
        primary_family="9_industrial_safety_environmental",
        scope=[(c["company_id"], "osha_inspection") for c in companies],
    ) as run:
        for company in companies:
            ...
            run.attempt(company_id, "osha_inspection", outcome="absent_confirmed",
                        source_url="https://...")

On exit the context writes the Attempts rows, the Harness_Runs row with its six rollups,
and (unless the run is a dry run) saves the workbook.

Append-only, deliberately. Observations reconcile because they hold current best knowledge
of a claim; attempts record what happened during one execution and are immutable history.
Reconciling them would erase the version-over-version trend the table exists to produce.
"""

from __future__ import annotations

import datetime as _dt
import re as _re
from dataclasses import dataclass, field, asdict

ATTEMPT_COLUMNS = [
    "attempt_id", "run_id", "harness_id", "harness_version", "company_id",
    "attempted_signal", "evidence_family", "outcome", "failure_stage",
    "failure_category", "failure_detail", "fix_class", "records_written",
    "records_reconciled", "output_sheet", "scope", "candidates_evaluated",
    "candidates_discarded", "attempt_timestamp", "source_url_attempted",
]

# Outcomes that count as coverage. `absent_confirmed` is here on purpose: a harness that
# reached an authoritative, complete source and found nothing has produced negative
# evidence, not a miss. CT Logistics resolving to no USDOT number is the canonical case --
# a freight-audit firm operates no fleet, so H-FMCSA-01's true resolution result is 8/8
# rather than 7/8 (spec §10 C7).
COVERAGE_OUTCOMES = {"covered", "absent_confirmed", "partial"}

# Signal_Types.status values whose attempts count toward a coverage denominator. A rollup
# filter, never a write filter -- see RunContext.rollups.
ROLLUP_STATUSES = {"active"}
OUTCOMES = COVERAGE_OUTCOMES | {"not_covered"}

# Outcomes that must carry a failure stage + category describing the gap.
REQUIRES_FAILURE = {"partial", "not_covered"}

# --------------------------------------------------------------------------------------
# The three states `access_blocked` was holding
# --------------------------------------------------------------------------------------
# Signal Advisor's data-hygiene finding, 2026-09-01. One flag was standing for three
# conditions that route to different actions and mean different things about the world:
#
#   source_refusal   the source's own published decision -- robots.txt Disallow, a 403 on
#                    a policy path, a paywall. NOT recoverable by us, and the ONLY one of
#                    the three that belongs in an ACCESS_BOUNDED count. This is a fact
#                    about the source and it is citable.
#   rate_limited     a throughput ceiling. The source would answer; it is asking us to
#                    slow down. Recoverable by pacing, so counting it as an access bound
#                    overstates what is unreachable.
#   egress_blocked   OUR network or trust store -- a content-filter interstitial, a
#                    certificate the local root store lacks. Says nothing whatsoever about
#                    the source, and convention 38 is the reason: writing 108
#                    `access_blocked` rows about api.usaspending.gov would have put a
#                    false claim about a federal database into the evidence base.
#
# NO NEW `failure_category` VALUES. A rate limit is still the source being unavailable and
# a refusal is still access being blocked; the specificity belongs in `failure_detail`,
# per the session-4 ruling that declined to mint `rate_limited` for CourtListener's 429s.
# Vocabularies are additive-only (convention 22), but that is a licence to extend when a
# distinction matters -- not to add a synonym for a value that already exists.
ACCESS_CLASSES = ("source_refusal", "rate_limited", "egress_blocked")

# The explicit marker a harness writes at emission time, where the truth is actually
# known: the harness saw the robots.txt, or the 429, or the filter interstitial.
ACCESS_CLASS_TOKEN = "access_class="


def access_detail(access_class: str, detail: str) -> str:
    """Stamp a failure_detail with its access class. Use this at emission time."""
    if access_class not in ACCESS_CLASSES:
        raise ValueError(f"access_class={access_class!r} not in {ACCESS_CLASSES}")
    return f"[{ACCESS_CLASS_TOKEN}{access_class}] {detail}".strip()


# Text signatures for rows written before the token existed.
#
# These are read-only inference over immutable history and are deliberately narrow.
# Convention 24 makes Attempts append-only -- attempts are what happened during one
# execution, and rewriting them erases the trend the table exists to produce -- so the
# backfill classifies on READ rather than editing 117 rows in place. That also makes the
# classification reviewable, testable code instead of a one-time edit nobody can
# re-derive, and new runs carry the token instead of being inferred at all.
#
# Convention 16 governs the patterns: each is a phrase a harness actually wrote, not a
# loose keyword. "403" alone is deliberately NOT a signature -- an edge rate limiter and a
# policy refusal both return it, and that ambiguity is the whole reason this split exists.
_ACCESS_SIGNATURES = (
    ("rate_limited",   "edge rate limiting"),
    ("rate_limited",   "too many requests"),
    ("rate_limited",   "consecutive access failures"),
    # A word-bounded 429 is safe where a 403 is not, and the asymmetry is the point.
    # 429 has exactly one meaning -- the source is asking us to slow down -- while 403 is
    # returned both by a policy refusal and by an edge rate limiter, which is the
    # Comparably case that motivated this whole split. Bare "403" is deliberately absent
    # from this list and those rows stay UNCLASSIFIED and get reported.
    # Added after the first run of scripts/access_report.py left `HTTPError: 429 from
    # CDX` unclassified: "too many requests" alone missed a real rate limit that the
    # requests library had already abbreviated away.
    ("rate_limited",   _re.compile(r"\b429\b")),
    ("egress_blocked", "web page blocked"),
    ("egress_blocked", "blocked_by_local_filter"),
    ("egress_blocked", "certificate_verify_failed"),
    ("source_refusal", "robots.txt"),
    ("source_refusal", "disallow"),
    ("source_refusal", "paywall"),
)

# When several classes appear in one row, the BINDING one wins -- the constraint that
# still holds after every recoverable one is lifted.
#
# This is not a tie-break for tidiness; the family-4 rows genuinely need it. Each records
# one (company, signal) pair whose signal draws on THREE sources with different access
# postures, in one free-text field: glassdoor and indeed refused by published robots.txt,
# while comparably rate-limited. Pace better and comparably may answer; glassdoor and
# indeed never will. So the row is access-bounded by a source refusal no matter what
# happens to the rate limit, and that is what an ACCESS_BOUNDED count is asking.
#
# The co-occurring classes are NOT discarded -- `access_classes_present` returns all of
# them, and the reporting script shows them, because "112 source refusals, 107 of which
# also record a rate limit" is a materially different statement from "112 source refusals"
# and convention 7 says a suppressed fact gets reported rather than dropped.
_ACCESS_PRECEDENCE = ("source_refusal", "egress_blocked", "rate_limited")


def access_classes_present(failure_detail: str | None) -> tuple:
    """Every access class this row's text evidences, in precedence order."""
    text = (failure_detail or "").lower()
    if ACCESS_CLASS_TOKEN in text:
        stated = text.split(ACCESS_CLASS_TOKEN, 1)[1].split("]")[0].strip()
        return (stated,) if stated in ACCESS_CLASSES else ()
    found = {c for c, sig in _ACCESS_SIGNATURES
             if (sig.search(text) if hasattr(sig, "search") else sig in text)}
    return tuple(c for c in _ACCESS_PRECEDENCE if c in found)


def classify_access(failure_detail: str | None,
                    failure_category: str | None = None) -> str | None:
    """The binding access class for a row, or None.

    Returns None rather than guessing, and a None is REPORTED by the caller rather than
    bucketed into a default. A row silently defaulted to `source_refusal` would inflate
    the one count that is supposed to be a citable claim about a source -- the failure
    convention 32 names: decide admission first, and an unclassifiable row is admitted to
    none of the three.
    """
    present = access_classes_present(failure_detail)
    return present[0] if present else None

# Failure categories that may ride along with a *successful* outcome.
#
# These describe a deliberate policy exclusion rather than a gap in what the harness could
# reach: the source was reached, records were found, and the harness chose not to keep some
# of them. Convention 7 requires that choice to be a recorded fact rather than a silence,
# and the outcome is still coverage because the harness did its job.
#
# `stale_beyond_threshold` joined this set for H-FIRSTPARTY-01, which excludes announcements
# older than five years. That is the same shape as an OSHA result cap -- a bound the harness
# declares and applies -- and without it here, a company whose only coverage was stale
# either had to be misreported as an ordinary failure or have the suppression dropped,
# which is the exact silence convention 7 exists to prevent.
GOVERNANCE_SUPPRESSIONS = {
    "suppressed_by_cap", "suppressed_redundant", "write_conflict_post_review",
    "stale_beyond_threshold",
    # Session 10 item 6 (C6): the spine saw only generic-tier terms and the harness wrote
    # nothing. Since convention 41 most harnesses write such text at low grade instead,
    # so this value is for the ones that still decline, and for completeness.
    "suppressed_generic_only",
}

# What an undeclared-but-unattempted pair is recorded as when the context closes it out.
UNATTEMPTED = ("not_covered", "discovery", "source_not_found",
               "declared in run scope but the harness never attempted it")


class AttemptError(ValueError):
    """Raised when a proposed attempt violates the Attempts contract."""


@dataclass
class Attempt:
    company_id: str
    attempted_signal: str
    outcome: str
    evidence_family: str = ""
    failure_stage: str | None = None
    failure_category: str | None = None
    failure_detail: str | None = None
    fix_class: str | None = None
    records_written: int = 0
    records_reconciled: int = 0
    output_sheet: str = "Observations"
    scope: str = "scoped"
    candidates_evaluated: int | None = None
    candidates_discarded: int | None = None
    source_url_attempted: str | None = None
    attempt_timestamp: str = ""
    attempt_id: str = ""
    run_id: str = ""
    harness_id: str = ""
    harness_version: str = ""

    def as_row(self) -> list:
        d = asdict(self)
        return [d[c] for c in ATTEMPT_COLUMNS]


class RunContext:
    """Tracks declared scope, collects attempts, and closes the run out honestly."""

    def __init__(self, db, harness_id: str, harness_name: str, version: str,
                 primary_family: str, scope: list[tuple[str, str]],
                 signal_families: dict[str, str] | None = None,
                 commit: bool = False):
        self.db = db
        self.harness_id = harness_id
        self.harness_name = harness_name
        self.version = version
        self.primary_family = primary_family
        self.commit = commit
        # (company_id, signal) pairs this harness said it would try.
        self.declared: set[tuple[str, str]] = set(scope)
        # signal -> evidence_family, so attempts can be tagged without repeating it.
        self.signal_families = dict(signal_families or {})
        self.attempts: list[Attempt] = []
        self._seen: set[tuple[str, str, str]] = set()
        self.run_id = db.allocate_run_id()
        self.observations_written = 0
        self.material_revision_notes = ""
        self.reprocessing_required = "No"
        # Audit gate (docs/gates/gate_new_harness_output.md). Fail-safe default: a run is
        # quarantined unless a harness explicitly says otherwise, so a harness that
        # forgets to declare its publication state gets the state that cannot inflate a
        # published coverage number. A grandfathered harness sets `publication_status =
        # "published"` on its run context; everything new leaves this alone until its
        # audit artifact exists.
        self.publication_status = "quarantined"
        self.records_excluded_by_audit = 0
        self.closed = False

    # ---------- emission ----------

    def attempt(self, company_id: str, attempted_signal: str, outcome: str, **kw) -> Attempt:
        """Record one attempt. See the module docstring for the completeness contract."""
        if outcome not in OUTCOMES:
            raise AttemptError(f"outcome={outcome!r} not in {sorted(OUTCOMES)}")

        scope = kw.pop("scope", "scoped")
        if scope not in ("scoped", "incidental"):
            raise AttemptError(f"scope={scope!r} must be 'scoped' or 'incidental'")

        # An incidental row is created retroactively when a harness writes an Observation
        # in a family it was not scoped for. It is always `covered` and never enters
        # coverage math (spec §3.1) -- otherwise opportunistic finds inflate the
        # denominator inconsistently.
        if scope == "incidental" and outcome != "covered":
            raise AttemptError("incidental attempts are always outcome='covered'")

        key = (company_id, attempted_signal, scope)
        if key in self._seen:
            raise AttemptError(
                f"duplicate attempt for {company_id}/{attempted_signal} ({scope}); "
                "the grain is one row per (run, company, signal)"
            )
        self._seen.add(key)

        family = kw.pop("evidence_family", None) or self.signal_families.get(
            attempted_signal, self.primary_family)

        a = Attempt(
            company_id=company_id,
            attempted_signal=attempted_signal,
            outcome=outcome,
            evidence_family=family,
            scope=scope,
            attempt_timestamp=kw.pop("attempt_timestamp", None) or _dt.datetime.now().isoformat(
                timespec="seconds"),
            **kw,
        )
        a.run_id = self.run_id
        a.harness_id = self.harness_id
        a.harness_version = self.version
        self._validate(a)
        self.attempts.append(a)
        return a

    def _validate(self, a: Attempt) -> None:
        if a.outcome in REQUIRES_FAILURE and not (a.failure_stage and a.failure_category):
            raise AttemptError(
                f"outcome={a.outcome!r} requires failure_stage and failure_category "
                f"({a.company_id}/{a.attempted_signal})"
            )
        # Null iff outcome is covered or absent_confirmed (spec §3 columns 8-9). Ordinary
        # reconciliation carries no failure_category at all (spec §11 C9).
        if a.outcome in ("covered", "absent_confirmed") and (a.failure_stage or a.failure_category):
            if a.failure_category not in GOVERNANCE_SUPPRESSIONS:
                raise AttemptError(
                    f"outcome={a.outcome!r} must not carry a failure stage/category "
                    f"unless it is a governance suppression ({a.company_id})"
                )
        if a.outcome == "covered" and (a.records_written + a.records_reconciled) <= 0:
            raise AttemptError(
                f"outcome='covered' requires records_written + records_reconciled > 0 "
                f"({a.company_id}/{a.attempted_signal}); use 'absent_confirmed' if the "
                "source was reached and the signal is genuinely not present"
            )
        vocab = self.db.vocab
        checks = [("evidence_family", a.evidence_family, "evidence_family"),
                  ("attempt_outcome", a.outcome, "outcome"),
                  ("failure_stage", a.failure_stage, "failure_stage"),
                  ("failure_category", a.failure_category, "failure_category"),
                  ("fix_class", a.fix_class, "fix_class"),
                  ("attempt_scope", a.scope, "scope")]
        for vocab_name, value, label in checks:
            if value in (None, ""):
                continue
            allowed = vocab.get(vocab_name)
            if allowed and value not in allowed:
                raise AttemptError(
                    f"{label}={value!r} is not in Lookups.{vocab_name}. "
                    f"Allowed: {sorted(allowed)}"
                )

    # ---------- close-out ----------

    def _close_unattempted(self) -> list[tuple[str, str]]:
        """Write a not_covered row for every declared pair the harness never touched."""
        attempted = {(a.company_id, a.attempted_signal)
                     for a in self.attempts if a.scope == "scoped"}
        missing = sorted(self.declared - attempted)
        outcome, stage, category, detail = UNATTEMPTED
        for company_id, signal in missing:
            self.attempt(company_id, signal, outcome=outcome, failure_stage=stage,
                         failure_category=category, failure_detail=detail,
                         fix_class="code_change")
        return missing

    def rollups(self) -> dict:
        """Run-level coverage numbers, over `scope = scoped` rows only (spec §5).

        Signal_Types.status is applied HERE and only here (week-3 package §3): attempts
        against a non-`active` signal type are still in `self.attempts` and still written
        to the sheet -- they happened -- but they enter no coverage denominator. A run
        whose only attempts target a `routing_only` type reports attempts_total 0, which
        is the truthful denominator, not a suppressed one.
        """
        status = self.db.signal_type_status() if hasattr(self.db, "signal_type_status") else {}
        scoped = [a for a in self.attempts if a.scope == "scoped"
                  and status.get(a.attempted_signal, "active") in ROLLUP_STATUSES]
        counts = {o: sum(1 for a in scoped if a.outcome == o) for o in OUTCOMES}
        total = len(scoped)
        covered = sum(counts[o] for o in COVERAGE_OUTCOMES)
        return {
            "attempts_total": total,
            "attempts_covered": counts["covered"],
            "attempts_absent_confirmed": counts["absent_confirmed"],
            "attempts_partial": counts["partial"],
            "attempts_not_covered": counts["not_covered"],
            "coverage_rate": round(covered / total, 4) if total else 0.0,
        }

    def derived_known_issues(self) -> str:
        """`known_issues` as a query result rather than a maintained string (spec §10 C6).

        H-JOBPOST-01's hand-written "3 of 7 companies covered, four documented gaps"
        becomes this.
        """
        groups: dict[str, list[str]] = {}
        for a in self.attempts:
            if a.outcome in ("covered", "absent_confirmed") or not a.failure_category:
                continue
            groups.setdefault(a.failure_category, []).append(a.company_id)
        if not groups:
            return ""
        parts = []
        for cat, companies in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            shown = ", ".join(sorted(companies)[:6])
            more = f" +{len(companies) - 6} more" if len(companies) > 6 else ""
            parts.append(f"{len(companies)} {cat} ({shown}{more})")
        return "; ".join(parts)

    def close(self) -> dict:
        if self.closed:
            raise AttemptError("run already closed")
        missing = self._close_unattempted()
        self.closed = True

        roll = self.rollups()
        companies_processed = len({a.company_id for a in self.attempts})

        summary = {
            "run_id": self.run_id,
            "missing_closed_out": missing,
            "companies_processed": companies_processed,
            **roll,
        }

        if not self.commit:
            return summary

        self.db.append_attempts(self.attempts)
        self.db.append_run_with_rollups(
            harness_id=self.harness_id,
            harness_name=self.harness_name,
            version=self.version,
            primary_family=self.primary_family,
            companies_processed_count=companies_processed,
            observations_produced_count=self.observations_written,
            known_issues=self.derived_known_issues(),
            material_revision_notes=self.material_revision_notes,
            reprocessing_required=self.reprocessing_required,
            run_id=self.run_id,
            rollups=roll,
            publication_status=self.publication_status,
            records_excluded_by_audit=self.records_excluded_by_audit,
        )
        return summary

    # ---------- context manager ----------

    def __enter__(self) -> "RunContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # On an exception the run is abandoned deliberately: a partially-written run would
        # produce coverage numbers that describe a crash rather than the source.
        if exc_type is not None:
            return False
        self.summary = self.close()
        return False
