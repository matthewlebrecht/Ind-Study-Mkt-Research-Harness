"""
Shared workbook layer for the Market Intelligence Harness project.

Every harness — regardless of evidence family or collection method — writes through
this module, so the Observations contract is enforced in exactly one place.

Responsibilities:
  * read the qualified company universe out of the Companies sheet
  * validate every proposed observation against the controlled vocabulary in Lookups
    (a harness that invents a vocabulary term fails loudly rather than silently
    poisoning the evidence base)
  * allocate observation_id / harness_run_id sequences
  * append rows to Observations and Harness_Runs
  * reconcile a re-run against what is already in the sheet (see sync_observations)

Nothing here is FMCSA-specific.

Re-run policy
-------------
Harnesses are meant to be re-run as sources refresh, so writing has to be idempotent.
`sync_observations()` reconciles proposed rows against existing ones on a natural key of
(company_id, harness_id, topic, source_url) and takes one of four actions:

    inserted   no existing row for that key
    unchanged  a row exists and its content fingerprint matches — left untouched
    updated    content changed and the row is machine-authored — refreshed in place,
               keeping its observation_id
    conflict   content changed but a *human* authored the row's review — NOT touched;
               reported for manual attention

That last case is the point of the whole design. Human review is the scarce input to the
Week 4 reliability evaluation, and a re-run must never silently erase it. The harness
surfaces the disagreement and lets a person decide.

The rule keys on `review_source` (provenance), not on the `review_status` *value*
(2026-08-31, audit gate). Those were the same thing only for as long as humans were the
only writers of review_status. The audit gate writes `audit_verdict` machine-side, and a
machine-set verdict must stay freely overwritable by the next run while a human-set one
must not -- a distinction the value alone cannot express. A row with `review_source`
empty or `machine` may be overwritten; a row with `review_source = human` may not.

The natural key deliberately excludes harness_version, so a version bump does not
duplicate rows. An untouched row keeps the version that produced it; a refreshed row
takes the version that refreshed it.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path

import openpyxl

WORKBOOK_PATH = Path(__file__).resolve().parent.parent / "data" / "market_intel_db.xlsx"

# Sheet-order column contract for Observations (21 columns).
OBSERVATION_COLUMNS = [
    "observation_id", "company_id", "evidence_family", "evidence_role", "topic",
    "organizational_state", "signal_strength", "observation_text", "evidence_excerpt",
    "source_url", "publication_date", "retrieval_date", "source_grade", "harness_id",
    "harness_version", "review_status", "reviewer_notes", "confidence_0_1",
    "publication_state", "audit_verdict", "review_source",
]

HARNESS_RUN_COLUMNS = [
    "harness_run_id", "harness_id", "harness_name", "version", "target_evidence_family",
    "date_run", "companies_processed_count", "observations_produced_count",
    "known_issues", "material_revision_notes", "reprocessing_required",
]

# Sheet-order column contract for Company_Executives (17 columns).
EXECUTIVE_COLUMNS = [
    "executive_id", "company_id", "full_name", "name_variants", "title",
    "title_normalized", "role_relevance", "source_url", "source_grade",
    "publication_date", "retrieval_date", "harness_id", "harness_version", "status",
    "superseded_by", "confidence_0_1", "review_status",
]

# Which Lookups column feeds which field. A-I are the original Observations/Companies
# vocabularies; J-O were added for the Attempts audit schema.
_VOCAB_COLUMNS = {
    "evidence_role": "A",
    "source_grade": "B",
    "review_status": "C",
    "signal_strength": "D",
    "organizational_state": "E",
    "qualification_status": "F",
    "evidence_family": "G",
    "industry": "H",
    "access_type": "I",
    "attempt_outcome": "J",
    "failure_stage": "K",
    "failure_category": "L",
    "fix_class": "M",
    "attempt_scope": "N",
    "harness_source_role": "O",
    "publication_state": "P",
    "audit_verdict": "Q",
    "review_source": "R",
    "publication_status": "S",
}


class SchemaError(ValueError):
    """Raised when a harness proposes a row that violates the Observations contract."""


# Fields that define whether two rows say the same thing. Deliberately excludes
# retrieval_date (changes every run), harness_version (a version bump alone is not a
# content change), and the human-owned review_status / reviewer_notes.
_FINGERPRINT_FIELDS = [
    "evidence_family", "evidence_role", "organizational_state", "signal_strength",
    "observation_text", "evidence_excerpt", "publication_date", "source_grade",
    "confidence_0_1",
]

# Identity of a claim: this company, this harness, this topic, this exact source.
_NATURAL_KEY_FIELDS = ["company_id", "harness_id", "topic", "source_url"]

# Observation_Ids -- the id registry (session 14, convention 43). One row per id ever
# assigned. `natural_key` is the four _NATURAL_KEY_FIELDS joined by "|" after _norm, so
# the registry can answer "which id did this claim have" without the row existing.
OBSERVATION_ID_COLUMNS = [
    "observation_id", "natural_key", "company_id", "harness_id", "topic", "source_url",
    "first_assigned", "status", "retired_at", "retired_note",
]


def natural_key_of(values: dict) -> str:
    return "|".join(_norm(values.get(f)) for f in _NATURAL_KEY_FIELDS)

REVIEWED_STATUSES = {"accepted", "corrected", "rejected"}

# Columns a re-run never rewrites on an existing row. `review_source` and `audit_verdict`
# join the original three because a re-run is not an audit: it may invalidate a verdict
# (handled below by clearing it when content actually changes) but it must not author one.
_PROTECTED_ON_UPDATE = {
    "observation_id", "review_status", "reviewer_notes", "review_source", "audit_verdict",
}


def is_human_authored(values: dict) -> bool:
    """Whether a row's review was authored by a person, and is therefore untouchable.

    Two independent signals, either of which protects the row:

      * `review_source = human` -- the explicit provenance flag the audit gate added.
      * `review_status` holding a reviewed value -- because no harness ever writes one.
        Every machine write sets `unreviewed`, so `accepted`/`corrected`/`rejected` can
        only have been put there by a person.

    The brief specified provenance alone ("a re-run may overwrite any row whose
    review_source is machine or empty"). Taking that literally opens a data-loss path
    that convention 1 exists to close: a reviewer who marks a row `accepted` by hand in
    Excel, and does not also change `review_source`, leaves it reading `machine` -- and
    their review silently vanishes on the next run. The OR is strictly safer, protects a
    superset of what the brief asked for, and costs nothing the gate needs, because the
    audit writes `audit_verdict` rather than `review_status`, so machine-authored
    verdicts stay freely overwritable exactly as intended. Logged as a deliberate,
    conservative deviation (session 3 report, task 1).
    """
    if _norm(values.get("review_source")).lower() == "human":
        return True
    return _norm(values.get("review_status")).lower() in REVIEWED_STATUSES


def _norm(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value).strip()


def _fingerprint(values: dict) -> str:
    payload = "\x1f".join(_norm(values.get(f)) for f in _FINGERPRINT_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class SyncReport:
    """Outcome of reconciling one harness's proposed rows against the sheet."""

    inserted: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    refreshed_reviewed: list = field(default_factory=list)
    # Rows whose content changed under an existing audit verdict, so the verdict was
    # dropped. Reported rather than silent: it is the signal that a harness fix has
    # invalidated part of an audit and the gate has to be re-run for that version.
    verdicts_cleared: list = field(default_factory=list)

    @property
    def written(self) -> int:
        return len(self.inserted) + len(self.updated)

    def summary(self) -> str:
        extra = (f" (incl. {len(self.refreshed_reviewed)} reviewed rows refreshed by "
                 f"explicit opt-in)" if self.refreshed_reviewed else "")
        cleared = (f", {len(self.verdicts_cleared)} audit verdict(s) cleared by content "
                   f"change" if self.verdicts_cleared else "")
        return (f"{len(self.inserted)} inserted, {len(self.updated)} refreshed, "
                f"{len(self.unchanged)} unchanged, {len(self.conflicts)} held for "
                f"review{extra}{cleared}")


@dataclass
class Observation:
    """One atomic, checkable claim. observation_id is assigned at write time."""

    company_id: str
    evidence_family: str
    evidence_role: str
    topic: str
    organizational_state: str
    signal_strength: str
    observation_text: str
    evidence_excerpt: str
    source_url: str
    publication_date: str
    retrieval_date: str
    source_grade: str
    harness_id: str
    harness_version: str
    confidence_0_1: float
    review_status: str = "unreviewed"
    reviewer_notes: str = ""  # human-only field; harnesses leave it blank
    # Fail-safe default: a row is quarantined unless a caller says otherwise. A harness
    # that forgets to declare its publication state gets the state that cannot inflate a
    # coverage number, rather than the one that can.
    publication_state: str = "quarantined"
    audit_verdict: str = ""      # null until an audit writes one
    review_source: str = "machine"
    observation_id: str = ""

    def as_row(self) -> list:
        d = asdict(self)
        return [d[c] for c in OBSERVATION_COLUMNS]


@dataclass
class Executive:
    """One named person holding one role at one company, as of one source snapshot.

    This is a *prerequisite* record, not evidence. It makes no claim about modernization;
    it exists so H-EXECVOICE-01 knows whose public statements to look for. It therefore
    lands in `Company_Executives` and never in `Observations`, matching the
    `signal_class = prerequisite` registration of `executive_identification` in
    `Signal_Types`.
    """

    company_id: str
    full_name: str
    title: str
    title_normalized: str
    role_relevance: str
    source_url: str
    source_grade: str
    retrieval_date: str
    harness_id: str
    harness_version: str
    confidence_0_1: float
    name_variants: str = ""
    publication_date: str = ""
    status: str = "active"
    superseded_by: str = ""
    review_status: str = "unreviewed"
    executive_id: str = ""

    def as_row(self) -> list:
        d = asdict(self)
        return [d[c] for c in EXECUTIVE_COLUMNS]

    @property
    def name_key(self) -> str:
        """Identity of the person, insensitive to punctuation, case and spacing."""
        return "".join(ch for ch in self.full_name.lower() if ch.isalpha())


@dataclass
class ExecutiveSyncReport:
    inserted: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    superseded: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)

    @property
    def written(self) -> int:
        return len(self.inserted) + len(self.updated)

    def summary(self) -> str:
        return (f"{len(self.inserted)} inserted, {len(self.updated)} refreshed, "
                f"{len(self.unchanged)} unchanged, {len(self.superseded)} superseded, "
                f"{len(self.conflicts)} held for review")


@dataclass
class HarnessRun:
    harness_id: str
    harness_name: str
    version: str
    target_evidence_family: str
    date_run: str
    companies_processed_count: int
    observations_produced_count: int
    known_issues: str
    material_revision_notes: str
    reprocessing_required: str = "No"
    harness_run_id: str = ""

    def as_row(self) -> list:
        d = asdict(self)
        return [d[c] for c in HARNESS_RUN_COLUMNS]


class MarketIntelDB:
    """Thin, explicit wrapper over the workbook. Open -> mutate -> save()."""

    def __init__(self, path: Path | str = WORKBOOK_PATH):
        self.path = Path(path)
        self.wb = openpyxl.load_workbook(self.path)
        self._assert_headers()
        self.vocab = self._load_vocab()

    # ---------- integrity ----------

    def _assert_headers(self) -> None:
        """Fail at startup if the sheet no longer matches the documented contract."""
        checks = [("Observations", OBSERVATION_COLUMNS),
                  ("Harness_Runs", HARNESS_RUN_COLUMNS),
                  ("Company_Executives", EXECUTIVE_COLUMNS)]
        if "Observation_Ids" in self.wb.sheetnames:
            checks.append(("Observation_Ids", OBSERVATION_ID_COLUMNS))
        for sheet, expected in checks:
            ws = self.wb[sheet]
            actual = [ws.cell(1, i + 1).value for i in range(len(expected))]
            if actual != expected:
                raise SchemaError(
                    f"{sheet} header drift.\n  expected: {expected}\n  actual:   {actual}"
                )

    def _load_vocab(self) -> dict[str, set[str]]:
        ws = self.wb["Lookups"]
        vocab: dict[str, set[str]] = {}
        for field_name, col in _VOCAB_COLUMNS.items():
            values = set()
            for r in range(2, ws.max_row + 1):
                v = ws[f"{col}{r}"].value
                if v not in (None, ""):
                    values.add(str(v).strip())
            vocab[field_name] = values
        return vocab

    def validate(self, obs: Observation) -> None:
        for field_name in ("evidence_family", "evidence_role", "organizational_state",
                           "signal_strength", "source_grade", "review_status",
                           "publication_state", "review_source"):
            value = getattr(obs, field_name)
            allowed = self.vocab[field_name]
            if value not in allowed:
                raise SchemaError(
                    f"{field_name}={value!r} is not in Lookups. Allowed: {sorted(allowed)}"
                )
        # audit_verdict is the one gate column that is legitimately empty most of the
        # time -- null means "not audited", which is a distinct state from all four
        # verdicts and must not be forced into one.
        if obs.audit_verdict and obs.audit_verdict not in self.vocab["audit_verdict"]:
            raise SchemaError(
                f"audit_verdict={obs.audit_verdict!r} is not in Lookups. "
                f"Allowed: {sorted(self.vocab['audit_verdict'])} or empty"
            )
        if obs.source_grade == "D":
            raise SchemaError(
                "source_grade D means 'exclude from evidence base' — do not write the row."
            )
        if not 0.0 <= float(obs.confidence_0_1) <= 1.0:
            raise SchemaError(f"confidence_0_1 out of range: {obs.confidence_0_1}")
        if obs.company_id not in {c["company_id"] for c in self.companies()}:
            raise SchemaError(f"unknown company_id {obs.company_id!r}")
        for required in ("observation_text", "source_url", "retrieval_date", "topic"):
            if not str(getattr(obs, required)).strip():
                raise SchemaError(f"{required} must not be empty")

    # ---------- reads ----------

    def companies(self, statuses: tuple[str, ...] | None = None) -> list[dict]:
        ws = self.wb["Companies"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        out = []
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, 1).value is None:
                continue
            row = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers) if h}
            if statuses is None or row.get("qualification_status") in statuses:
                out.append(row)
        return out

    def set_qualification_status(self, company_id: str, status: str,
                                 reason: str = "") -> dict:
        """Change one company's qualification_status, with the vocabulary enforced.

        This is a decision about the UNIVERSE, not about evidence, and it is the single
        input every harness's coverage denominator derives from -- so it belongs behind
        the same writer as everything else (convention 28) rather than being poked into
        the sheet by whichever harness happens to notice.

        Returns what changed so the caller reports rather than assumes.
        """
        allowed = self.vocab.get("qualification_status", set())
        if allowed and status not in allowed:
            raise SchemaError(f"qualification_status={status!r} is not in Lookups. "
                              f"Allowed: {sorted(allowed)}")
        ws = self.wb["Companies"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        i_id = headers.index("company_id") + 1
        i_q = headers.index("qualification_status") + 1
        for r in range(2, ws.max_row + 1):
            if _norm(ws.cell(r, i_id).value) != company_id:
                continue
            before = _norm(ws.cell(r, i_q).value)
            ws.cell(r, i_q).value = status
            if reason and "notes" in headers:
                i_n = headers.index("notes") + 1
                prior = _norm(ws.cell(r, i_n).value)
                stamp = f"[{today()}] qualification_status {before} -> {status}: {reason}"
                ws.cell(r, i_n).value = f"{prior} {stamp}".strip() if prior else stamp
            return {"company_id": company_id, "from": before, "to": status}
        raise SchemaError(f"no company with id {company_id!r}")

    def _next_id(self, sheet: str, prefix: str, width: int) -> int:
        ws = self.wb[sheet]
        highest = 0
        for r in range(2, ws.max_row + 1):
            v = ws.cell(r, 1).value
            if isinstance(v, str) and v.startswith(prefix):
                try:
                    highest = max(highest, int(v[len(prefix):]))
                except ValueError:
                    continue
        return highest + 1

    # ---------- writes ----------

    def append_observations(self, observations: list[Observation]) -> list[Observation]:
        for obs in observations:
            self.validate(obs)
        ws = self.wb["Observations"]
        for obs in observations:
            obs.observation_id = self._assign_observation_id(asdict(obs))
            ws.append(obs.as_row())
        self._warn_validation_range(ws, "Observations")
        return observations

    # ---------- the id registry (session 14, convention 43) ----------

    def _registry(self) -> dict:
        """Observation_Ids indexed two ways: by id and by natural key (all ids ever
        assigned to that key, oldest first). Absent sheet -> empty, and allocation falls
        back to the pre-registry rule so an unmigrated workbook still works."""
        out = {"by_id": {}, "by_key": {}, "ws": None}
        if "Observation_Ids" not in self.wb.sheetnames:
            return out
        ws = self.wb["Observation_Ids"]
        out["ws"] = ws
        for r in range(2, ws.max_row + 1):
            oid = _norm(ws.cell(r, 1).value)
            if not oid:
                continue
            rec = {h: ws.cell(r, i + 1).value for i, h in enumerate(OBSERVATION_ID_COLUMNS)}
            rec["row"] = r
            out["by_id"][oid] = rec
            out["by_key"].setdefault(_norm(rec.get("natural_key")), []).append(rec)
        return out

    def _highest_observation_id(self, registry: dict) -> int:
        highest = self._next_id("Observations", "O", 5) - 1
        for oid in registry["by_id"]:
            try:
                highest = max(highest, int(oid[1:]))
            except ValueError:
                continue
        return highest

    def _assign_observation_id(self, values: dict, registry: dict | None = None) -> str:
        """The id for this claim: its retired id if it ever had one, else a fresh one
        above every id ever assigned. Registers the assignment when the sheet exists."""
        reg = registry if registry is not None else self._registry()
        key = natural_key_of(values)
        prior = [r for r in reg["by_key"].get(key, []) if _norm(r.get("status")) != "live"]
        if prior:
            rec = prior[-1]                       # the id readers saw most recently
            oid = _norm(rec["observation_id"])
            if reg["ws"] is not None:
                ws = reg["ws"]
                ws.cell(rec["row"], OBSERVATION_ID_COLUMNS.index("status") + 1).value = "live"
                ws.cell(rec["row"], OBSERVATION_ID_COLUMNS.index("retired_at") + 1).value = None
                rec["status"] = "live"
            return oid
        live = [r for r in reg["by_key"].get(key, []) if _norm(r.get("status")) == "live"]
        if live:
            # the caller is inserting a key that already has a live id: that is the
            # sync path's job to reconcile, and allocating a second id would fork it
            raise SchemaError(f"natural key already has live id {live[-1]['observation_id']}: "
                              f"{key}")
        oid = "O%05d" % (self._highest_observation_id(reg) + 1)
        if reg["ws"] is not None:
            ws = reg["ws"]
            ws.append([oid, key] + [_norm(values.get(f)) for f in _NATURAL_KEY_FIELDS]
                      + [today(), "live", None, None])
            rec = {"observation_id": oid, "natural_key": key, "status": "live",
                   "row": ws.max_row}
            reg["by_id"][oid] = rec
            reg["by_key"].setdefault(key, []).append(rec)
        return oid

    def _retire_observation_id(self, oid: str, note: str, registry: dict | None = None) -> None:
        reg = registry if registry is not None else self._registry()
        rec = reg["by_id"].get(oid)
        if rec is None or reg["ws"] is None:
            return
        ws = reg["ws"]
        ws.cell(rec["row"], OBSERVATION_ID_COLUMNS.index("status") + 1).value = "retired"
        ws.cell(rec["row"], OBSERVATION_ID_COLUMNS.index("retired_at") + 1).value = today()
        ws.cell(rec["row"], OBSERVATION_ID_COLUMNS.index("retired_note") + 1).value = note[:200]
        rec["status"] = "retired"

    def register_live_observations(self) -> int:
        """Backfill: every Observations row not yet in the registry is registered live.
        Idempotent; returns how many were added."""
        reg = self._registry()
        if reg["ws"] is None:
            raise SchemaError("Observation_Ids sheet missing; run scripts/migrate_schema.py")
        ws = self.wb["Observations"]
        headers = [ws.cell(1, c).value for c in range(1, len(OBSERVATION_COLUMNS) + 1)]
        added = 0
        for r in range(2, ws.max_row + 1):
            oid = _norm(ws.cell(r, 1).value)
            if not oid or oid in reg["by_id"]:
                continue
            values = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
            key = natural_key_of(values)
            reg["ws"].append([oid, key] + [_norm(values.get(f)) for f in _NATURAL_KEY_FIELDS]
                             + [_norm(values.get("retrieval_date")) or today(), "live",
                                None, None])
            reg["by_id"][oid] = {"observation_id": oid, "natural_key": key,
                                 "status": "live", "row": reg["ws"].max_row}
            added += 1
        return added

    def _observation_rows(self) -> dict[tuple, dict]:
        """Index existing Observations rows by natural key."""
        ws = self.wb["Observations"]
        headers = [ws.cell(1, c).value for c in range(1, len(OBSERVATION_COLUMNS) + 1)]
        index: dict[tuple, dict] = {}
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, 1).value is None:
                continue
            values = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
            key = tuple(_norm(values.get(f)) for f in _NATURAL_KEY_FIELDS)
            index[key] = {"row": r, "values": values, "fingerprint": _fingerprint(values)}
        return index

    def sync_observations(self, observations: list[Observation],
                          refresh_reviewed: bool = False,
                          refresh_note: str = "",
                          refresh_ids: set[str] | None = None) -> SyncReport:
        """Idempotent write. See the module docstring for the reconciliation policy.

        `refresh_reviewed` opts into updating rows a human has already reviewed. It exists
        for one specific situation: the reviewer verified a row against a *newer* version
        of the source than the harness read, so the row is right but internally
        inconsistent. Refreshing re-derives the whole row from one coherent snapshot.

        It is never the default, it preserves `review_status` (the human's decision
        stands), and it stamps `reviewer_notes` with `refresh_note` so the sheet records
        that a machine touched a reviewed row and why.

        `refresh_ids` (session 14) narrows the opt-in to named rows: a decision to accept
        the harness's values on O00369 and O00373 is not a decision about every other
        reviewed row the same run happens to re-derive differently. Those stay held.
        """
        for obs in observations:
            self.validate(obs)

        ws = self.wb["Observations"]
        existing = self._observation_rows()
        report = SyncReport()
        registry = self._registry()

        for obs in observations:
            proposed = asdict(obs)
            key = tuple(_norm(proposed.get(f)) for f in _NATURAL_KEY_FIELDS)
            prior = existing.get(key)

            if prior is None:
                obs.observation_id = self._assign_observation_id(proposed, registry)
                ws.append(obs.as_row())
                # Index it so a duplicate key within the same batch is caught too.
                existing[key] = {"row": ws.max_row, "values": proposed,
                                 "fingerprint": _fingerprint(proposed)}
                report.inserted.append(obs)
                continue

            obs.observation_id = str(prior["values"].get("observation_id") or "")
            if _fingerprint(proposed) == prior["fingerprint"]:
                report.unchanged.append(obs)
                continue

            status = _norm(prior["values"].get("review_status")).lower()
            is_reviewed = is_human_authored(prior["values"])
            may_refresh = refresh_reviewed and (
                refresh_ids is None or obs.observation_id in refresh_ids)
            if is_reviewed and not may_refresh:
                report.conflicts.append({
                    "observation_id": obs.observation_id,
                    "company_id": obs.company_id,
                    "topic": obs.topic,
                    "review_status": status,
                    "review_source": _norm(prior["values"].get("review_source")),
                    "existing_text": _norm(prior["values"].get("observation_text")),
                    "proposed_text": obs.observation_text,
                })
                continue

            # Changed: refresh in place, preserving the row's identity and the human's
            # review decision. reviewer_notes is only written when a reviewed row is
            # deliberately refreshed, so the sheet shows a machine touched it and why.
            row = prior["row"]
            for i, col in enumerate(OBSERVATION_COLUMNS, start=1):
                if col in _PROTECTED_ON_UPDATE:
                    continue
                ws.cell(row, i).value = proposed[col]
            # The content changed, so any audit verdict on this row was reached against
            # text that no longer exists. Clearing it is not losing information: keeping
            # it would assert that a claim nobody has looked at was found supported.
            verdict_col = OBSERVATION_COLUMNS.index("audit_verdict") + 1
            if _norm(ws.cell(row, verdict_col).value):
                ws.cell(row, verdict_col).value = None
                report.verdicts_cleared.append(obs.observation_id)
            if is_reviewed and refresh_note:
                notes_col = OBSERVATION_COLUMNS.index("reviewer_notes") + 1
                existing_note = _norm(ws.cell(row, notes_col).value)
                ws.cell(row, notes_col).value = (
                    f"{existing_note} {refresh_note}".strip() if existing_note else refresh_note)
                report.refreshed_reviewed.append(obs.observation_id)
            prior["fingerprint"] = _fingerprint(proposed)
            report.updated.append(obs)

        self._warn_validation_range(ws, "Observations")
        return report

    def apply_audit_verdict(self, observation_id: str, verdict: str, auditor: str,
                            notes: str, review_status: str = "accepted",
                            publication_state: str = "released",
                            **field_updates) -> dict:
        """Record a human audit decision on one Observation row.

        This is the only path by which `audit_verdict` and `review_source = human` are
        written, and it is deliberately narrow: it takes an observation_id rather than a
        query, so a verdict is applied to a row somebody actually named.

        `field_updates` carries the downgrade that an `overgraded` verdict implies. The
        gate's four verdicts are not four labels for the same action -- `supported`
        changes nothing, `overgraded` means the row survives at a lower strength and
        therefore MUST change something, and `unsupported` / `wrong_entity` mean the row
        should not exist at all (convention 32) and are refused here, because deleting
        evidence is not a field update and should not be reachable through one.

        Writing `review_source = human` is what makes the row untouchable by the next
        run (convention 35). That is the point: a person has now looked at it.
        """
        if verdict not in self.vocab["audit_verdict"]:
            raise SchemaError(f"audit_verdict={verdict!r} is not in Lookups. "
                              f"Allowed: {sorted(self.vocab['audit_verdict'])}")
        if verdict in ("unsupported", "wrong_entity"):
            raise SchemaError(
                f"{verdict!r} means the row should not exist at any strength "
                f"(convention 32). Remove it with delete_observations() and record the "
                f"removal in the audit artifact -- do not park it here at a lower grade.")
        if verdict == "overgraded" and not field_updates:
            raise SchemaError(
                "an 'overgraded' verdict means the row survives at a LOWER strength, so "
                "it must change something. Pass the downgrade (signal_strength, "
                "organizational_state, source_grade, confidence_0_1) or the verdict is "
                "a label with no consequence.")

        ws = self.wb["Observations"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        row = None
        for r in range(2, ws.max_row + 1):
            if _norm(ws.cell(r, 1).value) == observation_id:
                row = r
                break
        if row is None:
            raise SchemaError(f"no Observation with id {observation_id!r}")

        def put(col, value):
            ws.cell(row, headers.index(col) + 1).value = value

        before = {c: ws.cell(row, headers.index(c) + 1).value
                  for c in ("signal_strength", "organizational_state", "source_grade",
                            "confidence_0_1")}

        for col, value in field_updates.items():
            if col not in headers:
                raise SchemaError(f"unknown Observations column {col!r}")
            if col in _PROTECTED_ON_UPDATE:
                raise SchemaError(f"{col!r} is set by this method, not passed as an update")
            put(col, value)

        put("audit_verdict", verdict)
        put("review_source", "human")
        put("review_status", review_status)
        put("publication_state", publication_state)
        stamp = f"[{today()} audit by {auditor}; verdict {verdict}] {notes}".strip()
        existing = _norm(ws.cell(row, headers.index("reviewer_notes") + 1).value)
        put("reviewer_notes", f"{existing} {stamp}".strip() if existing else stamp)

        after = {c: ws.cell(row, headers.index(c) + 1).value for c in before}
        changed = {c: (before[c], after[c]) for c in before if before[c] != after[c]}
        return {"observation_id": observation_id, "verdict": verdict, "changed": changed}

    def set_version_publication(self, harness_id: str, version: str, status: str,
                                *, require_artifact: bool = True) -> dict:
        """Move one harness VERSION out of quarantine, in both sheets at once.

        The gate's state lives in two places -- `Harness_Runs.publication_status` decides
        whether a coverage number may be quoted, `Observations.publication_state` decides
        whether a row may be counted -- and they have to move together. Flipping one and
        not the other produces a version whose rows are released but whose coverage is
        quarantined, or the reverse, and nothing downstream would notice.

        `require_artifact` is on by default and this is the important part: a release
        refuses unless the audit artifact is already on disk and its own verdict is
        `pass`. Without that this method would be a way to publish unaudited output
        through the writer that the gate is supposed to constrain -- check 9 would catch
        it afterwards, but a control that only fails after the fact is a report, not a
        gate. The flag exists for `superseded`, which asserts the opposite of a release
        (nothing is live, so nothing needed auditing) and therefore has no artifact.

        Returns what moved, so the caller reports rather than assumes.
        """
        from core import audit as _audit

        if status not in self.vocab.get("publication_status", set()):
            raise SchemaError(
                f"publication_status={status!r} is not in Lookups. Allowed: "
                f"{sorted(self.vocab.get('publication_status', []))}")

        if status == "published" and require_artifact:
            art = _audit.load_artifacts().get((harness_id, version))
            if art is None:
                raise SchemaError(
                    f"refusing to publish {harness_id} {version}: no audit artifact at "
                    f"{_audit.audit_path(harness_id, version).name}. The gate releases a "
                    f"version once it has been judged, not once someone is confident.")
            problems = _audit.validate_artifact(art)
            if problems:
                raise SchemaError(f"refusing to publish {harness_id} {version}: its "
                                  f"audit artifact is malformed -- {'; '.join(problems[:3])}")
            if art.get("verdict") != "pass":
                raise SchemaError(
                    f"refusing to publish {harness_id} {version}: its audit verdict is "
                    f"{art.get('verdict')!r} -- {'; '.join(art.get('stop_rule_triggered') or [])}")

        hr = self.wb["Harness_Runs"]
        hh = [hr.cell(1, c).value for c in range(1, hr.max_column + 1)]
        i_h, i_v = hh.index("harness_id") + 1, hh.index("version") + 1
        i_s, i_r = hh.index("publication_status") + 1, hh.index("harness_run_id") + 1
        runs = []
        for r in range(2, hr.max_row + 1):
            if hr.cell(r, 1).value is None:
                continue
            if (_norm(hr.cell(r, i_h).value) == harness_id
                    and _norm(hr.cell(r, i_v).value) == version):
                was = _norm(hr.cell(r, i_s).value)
                hr.cell(r, i_s).value = status
                runs.append({"run_id": _norm(hr.cell(r, i_r).value),
                             "from": was, "to": status})

        # `superseded` asserts nothing of the version is live, so it must not drag rows
        # into a released state. Only a release touches Observations.
        obs_state = {"published": "released"}.get(status)
        rows = []
        if obs_state:
            ws = self.wb["Observations"]
            oh = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
            i_oh, i_ov = oh.index("harness_id") + 1, oh.index("harness_version") + 1
            i_ps = oh.index("publication_state") + 1
            for r in range(2, ws.max_row + 1):
                if ws.cell(r, 1).value is None:
                    continue
                if (_norm(ws.cell(r, i_oh).value) == harness_id
                        and _norm(ws.cell(r, i_ov).value) == version):
                    was = _norm(ws.cell(r, i_ps).value)
                    if was != obs_state:
                        ws.cell(r, i_ps).value = obs_state
                        rows.append({"observation_id": _norm(ws.cell(r, 1).value),
                                     "from": was, "to": obs_state})

        if not runs:
            raise SchemaError(f"no Harness_Runs row for {harness_id} {version} -- "
                              f"nothing to move")
        return {"harness_id": harness_id, "version": version, "status": status,
                "runs": runs, "observations": rows}

    def retire_unreproduced(self, harness_id: str, proposed: list) -> dict:
        """Remove this harness's MACHINE rows whose claim the current run no longer makes.

        `sync_observations` is insert-or-refresh: a claim the harness used to make and
        now does not simply stays in the sheet, published, under the old version. That is
        the wrong default after an ADMISSION change -- the 2026-09-02 pattern fix removed
        the bare-word matches that six `systems_integration` provider rows rested on, and
        a row whose only evidence has been ruled inadmissible is not a finding that
        happens to be stale; it was never a finding. So the harness re-run retires it.

        Unlike `delete_observations` this is keyed on the natural key of what the run
        proposed, so surviving rows keep their observation_ids (no renumbering -- the
        session 4 side effect). A human-reviewed row is never removed: it is HELD and
        returned, because a person's verdict on a row is a decision this code cannot
        overrule (convention 35).

        Returns {"removed": [observation_id...], "held": [observation_id...]}.
        """
        keep = {tuple(_norm(getattr(o, f)) for f in _NATURAL_KEY_FIELDS) for o in proposed}
        registry = self._registry()
        ws = self.wb["Observations"]
        headers = [ws.cell(1, c).value for c in range(1, len(OBSERVATION_COLUMNS) + 1)]
        removed: list[str] = []
        held: list[str] = []
        for r in range(ws.max_row, 1, -1):
            values = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
            if _norm(values.get("harness_id")) != harness_id:
                continue
            key = tuple(_norm(values.get(f)) for f in _NATURAL_KEY_FIELDS)
            if key in keep:
                continue
            oid = str(values.get("observation_id") or "")
            if is_human_authored(values):
                held.append(oid)
                continue
            ws.delete_rows(r)
            self._retire_observation_id(oid, f"retire_unreproduced by {harness_id}", registry)
            removed.append(oid)
        return {"removed": sorted(removed), "held": sorted(held)}

    def delete_observation_ids(self, observation_ids: list[str], note: str) -> list[str]:
        """Remove NAMED rows -- the audit gate's `unsupported` / `wrong_entity` outcome
        (convention 32: such a claim should not exist at any strength). Refuses a row a
        human has reviewed, because a verdict that deletes is itself the human decision
        and must be recorded on the artifact, not overwritten in the sheet. Retires each
        id in the registry (convention 43) with the note. Returns the ids removed."""
        ws = self.wb["Observations"]
        headers = [ws.cell(1, c).value for c in range(1, len(OBSERVATION_COLUMNS) + 1)]
        wanted = {str(i) for i in observation_ids}
        registry = self._registry()
        removed: list[str] = []
        for r in range(ws.max_row, 1, -1):
            oid = _norm(ws.cell(r, 1).value)
            if oid not in wanted:
                continue
            values = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
            if is_human_authored(values):
                raise SchemaError(f"{oid} carries a human review; record the exclusion "
                                  f"on the audit artifact rather than deleting it here")
            ws.delete_rows(r)
            self._retire_observation_id(oid, note, registry)
            removed.append(oid)
        missing = sorted(wanted - set(removed))
        if missing:
            raise SchemaError(f"no Observations row for {missing}")
        return sorted(removed)

    def delete_observations(self, harness_id: str, keep_reviewed: bool = True) -> int:
        """Remove a harness's rows. Used only by an explicit --force-rewrite."""
        ws = self.wb["Observations"]
        headers = [ws.cell(1, c).value for c in range(1, len(OBSERVATION_COLUMNS) + 1)]
        h_idx = headers.index("harness_id") + 1
        r_idx = headers.index("review_status") + 1
        registry = self._registry()
        removed = 0
        for r in range(ws.max_row, 1, -1):
            if _norm(ws.cell(r, h_idx).value) != harness_id:
                continue
            if keep_reviewed and _norm(ws.cell(r, r_idx).value).lower() in REVIEWED_STATUSES:
                continue
            oid = _norm(ws.cell(r, 1).value)
            ws.delete_rows(r)
            self._retire_observation_id(oid, f"delete_observations by {harness_id}", registry)
            removed += 1
        return removed

    # ---------- executives ----------

    _EXEC_FINGERPRINT = ["title", "title_normalized", "role_relevance", "source_url",
                         "source_grade", "publication_date", "confidence_0_1", "status"]

    def _executive_rows(self) -> dict[tuple, dict]:
        ws = self.wb["Company_Executives"]
        headers = [ws.cell(1, c).value for c in range(1, len(EXECUTIVE_COLUMNS) + 1)]
        index: dict[tuple, dict] = {}
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, 1).value is None:
                continue
            values = {h: ws.cell(r, i + 1).value for i, h in enumerate(headers)}
            name_key = "".join(ch for ch in _norm(values.get("full_name")).lower()
                               if ch.isalpha())
            key = (_norm(values.get("company_id")), name_key)
            index[key] = {"row": r, "values": values, "name_key": name_key}
        return index

    def sync_executives(self, executives: list[Executive],
                        authoritative_companies: set[str] | None = None
                        ) -> ExecutiveSyncReport:
        """Idempotent write to Company_Executives, keyed on (company_id, name).

        The natural key deliberately excludes `harness_id`. A person is a person: if a
        second harness later identifies the same executive from a different source, that
        should reconcile with the existing row rather than create a second one.

        DEPARTURE DETECTION IS GATED, NOT AUTOMATIC
        -------------------------------------------
        `authoritative_companies` is the set of company_ids for which this run actually
        succeeded in reading a genuine leadership page. Only those companies can have
        previously-active rows marked `superseded` when a person is no longer listed.

        Without that gate, an ordinary transient failure -- a timeout, a 403, a site
        redesign that breaks discovery -- would mark a company entire executive roster as
        departed, which is the same class of error as convention 6a: writing confident
        negative information from a source that was never successfully read. Absence of a
        name in a page you failed to fetch is not evidence that the person left.

        Rows a human has reviewed are never superseded or overwritten silently; they are
        reported as conflicts, matching the Observations policy.
        """
        ws = self.wb["Company_Executives"]
        existing = self._executive_rows()
        report = ExecutiveSyncReport()
        seq = self._next_id("Company_Executives", "E", 5)
        proposed_keys: set[tuple] = set()

        for ex in executives:
            for required in ("company_id", "full_name", "source_url"):
                if not str(getattr(ex, required)).strip():
                    raise SchemaError(f"Executive.{required} must not be empty")
            # Session 14 (2026-09-06), the EXECID low-grade tier: a title may be empty
            # ONLY on a row that says so in every field a reader would check -- grade C,
            # role_relevance `unconfirmed`, confidence at or under the low-grade cap. A
            # blank title on an ordinary row is still the schema error it always was.
            low_grade_row = (ex.source_grade == "C" and ex.role_relevance == "unconfirmed"
                             and float(ex.confidence_0_1) <= 0.4)
            if not str(ex.title).strip() and not low_grade_row:
                raise SchemaError("Executive.title must not be empty unless the row is a "
                                  "low-grade unconfirmed-role record (source_grade C, "
                                  "role_relevance unconfirmed, confidence <= 0.4)")
            if ex.source_grade not in self.vocab["source_grade"]:
                raise SchemaError(f"source_grade={ex.source_grade!r} is not in Lookups")
            if ex.source_grade == "D":
                raise SchemaError("source_grade D means exclude from the evidence base")
            if ex.company_id not in {c["company_id"] for c in self.companies()}:
                raise SchemaError(f"unknown company_id {ex.company_id!r}")

            key = (ex.company_id, ex.name_key)
            proposed_keys.add(key)
            prior = existing.get(key)
            values = asdict(ex)

            if prior is None:
                ex.executive_id = "E%05d" % seq
                seq += 1
                ws.append(ex.as_row())
                existing[key] = {"row": ws.max_row, "values": values,
                                 "name_key": ex.name_key}
                report.inserted.append(ex)
                continue

            ex.executive_id = str(prior["values"].get("executive_id") or "")
            same = all(_norm(values.get(f)) == _norm(prior["values"].get(f))
                       for f in self._EXEC_FINGERPRINT)
            if same:
                report.unchanged.append(ex)
                continue
            if _norm(prior["values"].get("review_status")).lower() in REVIEWED_STATUSES:
                report.conflicts.append({
                    "executive_id": ex.executive_id, "company_id": ex.company_id,
                    "full_name": ex.full_name,
                    "existing_title": _norm(prior["values"].get("title")),
                    "proposed_title": ex.title,
                })
                continue
            for i, col in enumerate(EXECUTIVE_COLUMNS, start=1):
                if col in ("executive_id", "review_status"):
                    continue
                ws.cell(prior["row"], i).value = values[col]
            report.updated.append(ex)

        # ---- gated departure detection ----
        for key, prior in existing.items():
            company_id, _ = key
            if authoritative_companies is None or company_id not in authoritative_companies:
                continue
            if key in proposed_keys:
                continue
            if _norm(prior["values"].get("status")).lower() != "active":
                continue
            if _norm(prior["values"].get("review_status")).lower() in REVIEWED_STATUSES:
                report.conflicts.append({
                    "executive_id": _norm(prior["values"].get("executive_id")),
                    "company_id": company_id,
                    "full_name": _norm(prior["values"].get("full_name")),
                    "existing_title": _norm(prior["values"].get("title")),
                    "proposed_title": "(no longer listed on the leadership page)",
                })
                continue
            status_col = EXECUTIVE_COLUMNS.index("status") + 1
            ws.cell(prior["row"], status_col).value = "superseded"
            report.superseded.append(_norm(prior["values"].get("executive_id")))

        self._warn_validation_range(ws, "Company_Executives")
        return report

    def append_harness_run(self, run: HarnessRun,
                           publication_status: str = "quarantined") -> HarnessRun:
        """Append a run row from a pre-gate harness, WITH a publication status.

        `HARNESS_RUN_COLUMNS` is the 11-column contract from before the audit gate, so
        `as_row()` stops short of `publication_status` and this method used to leave the
        cell blank. Blank is not a valid value -- `validate_repo_db.py` check 9 rejects it
        outright -- so every harness still on the bare `HarnessRun` path (H-FMCSA-01 among
        them) would write a run row that fails validation the moment it ran. The gate was
        built around the run context and this path was never brought with it.

        The default is `quarantined` for the same fail-safe reason
        `Observation.publication_state` defaults that way: the state a forgetful caller
        lands in must be the one that cannot inflate a published number. A grandfathered
        VERSION still satisfies check 9's artifact requirement, but a fresh RUN of it --
        especially one against a far larger population than the version was grandfathered
        against -- is new output nobody has audited, and it should not publish by default.
        """
        if publication_status not in self.vocab.get("publication_status", set()):
            raise SchemaError(
                f"publication_status={publication_status!r} is not in Lookups. Allowed: "
                f"{sorted(self.vocab.get('publication_status', []))}")
        ws = self.wb["Harness_Runs"]
        run.harness_run_id = "HR-%04d" % self._next_id("Harness_Runs", "HR-", 4)
        row = run.as_row()
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        row += [None] * (len(headers) - len(row))
        for col, value in (("publication_status", publication_status),
                           ("records_excluded_by_audit", 0)):
            if col in headers:
                row[headers.index(col)] = value
        ws.append(row)
        return run

    # ---------- attempts / run context ----------

    def allocate_run_id(self) -> str:
        """Reserve the next HR id up front.

        `attempt_id` is `{run_id}-{seq}` (spec §3), so the run id has to exist before the
        first attempt is emitted rather than being assigned when the run row is appended.
        """
        return "HR-%04d" % self._next_id("Harness_Runs", "HR-", 4)

    def open_run(self, harness_id: str, harness_name: str, version: str,
                 primary_family: str, scope, signal_families=None, commit: bool = False):
        """Open a run context. See core/attempts.py for the completeness contract."""
        from core.attempts import RunContext

        return RunContext(self, harness_id=harness_id, harness_name=harness_name,
                          version=version, primary_family=primary_family,
                          scope=list(scope), signal_families=signal_families,
                          commit=commit)

    def append_attempts(self, attempts: list) -> list:
        """Append-only. Attempts never reconcile -- they are immutable run history (§7)."""
        from core.attempts import ATTEMPT_COLUMNS

        ws = self.wb["Attempts"]
        # attempt_id sequence is per-run, so it restarts at 1 for each run_id.
        seq: dict[str, int] = {}
        from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

        for a in attempts:
            n = seq.get(a.run_id, 0) + 1
            seq[a.run_id] = n
            a.attempt_id = f"{a.run_id}-{n:05d}"
            # A failure_detail that quotes a raw error body can carry control characters
            # openpyxl refuses (session 15: a gzip-compressed Brave 402 body). Strip them
            # here rather than lose the whole run at close -- the row's meaning survives.
            ws.append([ILLEGAL_CHARACTERS_RE.sub("?", v) if isinstance(v, str) else v
                       for v in a.as_row()])
        self._warn_validation_range(ws, "Attempts", ceiling=250_000)
        return attempts

    def signal_type_status(self) -> dict[str, str]:
        """signal_type_name -> Signal_Types.status. Read by the ROLLUP layer only.

        §22.1 / week-3 package §3: `status` is a rollup filter, never a write filter. An
        attempt against a `routing_only` / `out_of_theme` / `access_bounded` / `reference`
        signal type is still an attempt that happened and is still written to Attempts;
        it is excluded from a coverage denominator by this lookup at rollup time. Filtering
        at write would silently understate the denominator -- the failure the Attempts
        sheet exists to prevent.
        """
        ws = self.wb["Signal_Types"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        i_n, i_s = headers.index("signal_type_name") + 1, headers.index("status") + 1
        out = {}
        for r in range(2, ws.max_row + 1):
            name = ws.cell(r, i_n).value
            if name:
                out[str(name)] = str(ws.cell(r, i_s).value or "").strip()
        return out

    def append_state_history(self, rows: list[dict]) -> list[str]:
        """Append one derivation's rows to Company_State_History. APPEND-ONLY, IMMUTABLE.

        Refuses if the derivation_id already exists on the sheet (a derivation is written
        once) or if any row lacks the stamped gating values (definition_hash,
        buyer_detectable_since, and -- where the row got past the reach gate --
        min_retrospective_reach). Those stamps are the whole reason the table can be
        immutable: a row that had to be joined back to Harness_Sources or core/topics.py
        to be interpreted would be rewritten by every change to either.
        """
        from core.composition import STATE_HISTORY_COLUMNS

        ws = self.wb["Company_State_History"]
        headers = [ws.cell(1, c).value for c in range(1, len(STATE_HISTORY_COLUMNS) + 1)]
        if headers != STATE_HISTORY_COLUMNS:
            raise SchemaError("Company_State_History header drift; run scripts/migrate_schema.py")
        if not rows:
            return []
        did = {str(r.get("derivation_id")) for r in rows}
        if len(did) != 1:
            raise SchemaError(f"one derivation per append, got {sorted(did)}")
        did = did.pop()
        i_d = STATE_HISTORY_COLUMNS.index("derivation_id") + 1
        for r in range(2, ws.max_row + 1):
            if _norm(ws.cell(r, i_d).value) == did:
                raise SchemaError(f"derivation {did} already on Company_State_History; "
                                  f"derivations are never rewritten -- run a new one")
        for row in rows:
            if not row.get("definition_hash") or not row.get("theme_id"):
                raise SchemaError("unstamped row: definition_hash / theme_id missing")
            if row.get("reason") not in ("theme_not_detectable", "no_reach") \
                    and not row.get("min_retrospective_reach"):
                raise SchemaError(f"row past the reach gate without a stamped "
                                  f"min_retrospective_reach: {row}")
        seq = self._next_id("Company_State_History", "CS-", 6)
        ids = []
        for row in rows:
            row["state_id"] = f"CS-{seq:06d}"
            seq += 1
            ws.append([row.get(c) for c in STATE_HISTORY_COLUMNS])
            ids.append(row["state_id"])
        self._warn_validation_range(ws, "Company_State_History", ceiling=250_000)
        return ids

    def latest_derivation_id(self) -> str | None:
        ws = self.wb["Company_State_History"]
        best = None
        for r in range(2, ws.max_row + 1):
            v = ws.cell(r, 2).value
            if v and (best is None or str(v) > best):
                best = str(v)
        return best

    def append_run_with_rollups(self, harness_id: str, harness_name: str, version: str,
                                primary_family: str, companies_processed_count: int,
                                observations_produced_count: int, known_issues: str,
                                material_revision_notes: str, reprocessing_required: str,
                                run_id: str, rollups: dict,
                                publication_status: str = "quarantined",
                                records_excluded_by_audit: int = 0) -> str:
        """Write the Harness_Runs row including its six derived coverage columns.

        `target_evidence_family` keeps its column but now means the *primary* family; a
        harness may write across several (spec §10 C6). `Harness_Sources` plus
        `Attempts.evidence_family` are authoritative for the full set.

        `publication_status` defaults to `quarantined` for the same fail-safe reason
        `Observation.publication_state` does: the state a forgetful caller lands in
        should be the one that cannot inflate a published number. A quarantined run's
        coverage columns are still computed and still written -- they are simply not
        published, and every rollup that reports coverage filters the run out by
        `publication_status` and its Attempts rows out by join on `run_id`.
        """
        ws = self.wb["Harness_Runs"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        values = {
            "harness_run_id": run_id,
            "harness_id": harness_id,
            "harness_name": harness_name,
            "version": version,
            "target_evidence_family": primary_family,
            "date_run": today(),
            "companies_processed_count": companies_processed_count,
            "observations_produced_count": observations_produced_count,
            "known_issues": known_issues,
            "material_revision_notes": material_revision_notes,
            "reprocessing_required": reprocessing_required,
            "publication_status": publication_status,
            "records_excluded_by_audit": records_excluded_by_audit,
            **rollups,
        }
        missing = [k for k in values if k not in headers]
        if missing:
            raise SchemaError(
                f"Harness_Runs is missing column(s) {missing}; run scripts/migrate_schema.py"
            )
        ws.append([values.get(h) for h in headers])
        return run_id

    @staticmethod
    def _warn_validation_range(ws, name: str, ceiling: int = 20_000) -> None:
        """Warn before rows fall outside the sheet's dropdown-validation binding.

        Rows past a validation's bound range accept anything silently, so a controlled
        vocabulary stops being enforced with no error anywhere. The ceiling defaults to
        the 20,000 that scripts/extend_validation.py binds; Attempts passes 250,000
        because it is append-only.
        """
        if ws.max_row > ceiling:
            print(f"  [WARN] {name} now has {ws.max_row} rows — dropdown validation "
                  f"stops at row {ceiling:,}. Extend the dataValidation sqref ranges "
                  f"(scripts/extend_validation.py).")

    def save(self, path: Path | str | None = None) -> Path:
        target = Path(path) if path else self.path
        self.wb.save(target)
        return target


def today() -> str:
    return _dt.date.today().isoformat()
