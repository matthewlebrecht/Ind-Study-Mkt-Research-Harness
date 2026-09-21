"""
Audit gate: the artifact that stands between a new harness's first output and a published
coverage number.

WHY THIS EXISTS
---------------
Session 2's self-audit cut H-FIRSTPARTY-01 from 248 rows to 79 and H-EXECVOICE-01 from 10
to 8, and caught six fresh instances of the project's characteristic failure mode
(convention 16, extended by 31-33). That audit happened because a person asked for it. If
nobody had asked, 248 rows at "97% coverage" would have gone into the write-up, two thirds
of them not supporting their own claim.

So the check is made structural. A harness version's output is `quarantined` on write.
It contributes neither numerator nor denominator to any published coverage number until
an audit artifact exists at `harness_output/audits/<harness_id>__<harness_version>.json`,
and `scripts/validate_repo_db.py` check 9 fails if a published run has no artifact.

WHAT THIS MODULE IS AND IS NOT
------------------------------
It is the schema, the path convention, the exemption registry, and the derivation rules.
It is *not* the sampler and it is not the judge. Sampling is per-harness because the
strata are defined over harness-specific fields (which term matched, which URL, which
name), and judging is the part that has to be done by reading rows. A module that offered
`audit(harness)` returning a verdict would be a machine grading its own homework, which is
the exact thing the gate exists to prevent.

KEYED ON VERSION, NOT RUN
-------------------------
The artifact is `<harness_id>__<harness_version>.json`. A run is an execution; a version
is a set of extraction rules. Two runs of the same version produce output with the same
defects, so auditing per-run would re-audit identical logic and, worse, would let a
re-run of an audited version silently publish without one. The `run_id` that was actually
sampled is recorded *inside* the artifact.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "harness_output" / "audits"
GATE_DOC = ROOT / "docs" / "gates" / "gate_new_harness_output.md"
GRANDFATHER_REGISTRY = ROOT / "docs" / "gates" / "grandfathered_harness_versions.json"

VERDICTS = ("supported", "overgraded", "unsupported", "wrong_entity")

# Verdicts that remove the row from the evidence base entirely, rather than moving it down
# the strength ladder. Convention 32: a claim its own evidence does not support gets an
# admission threshold, not a downgrade to `weak_clue`.
EXCLUDING_VERDICTS = ("unsupported", "wrong_entity")

# The literal threshold, stated here once and copied into every artifact's
# `threshold_applied` field so an artifact read years from now does not depend on this
# file still saying the same thing.
#
# PROVISIONAL. The audit-gate spec (`harness_advisor_response_audit_gate_2026-08-31.md`)
# was not on disk when this was built, and the outgoing brief it answers says explicitly
# "the threshold value itself I'll set". 0.10 is a conservative placeholder: it fails a
# harness sooner than a looser number would, and everything written under it tonight is
# quarantined regardless, so a later correction changes no published figure. Flagged for
# Matthew in the session 3 report.
RANDOM_CONTROL_EXCLUSION_THRESHOLD = 0.10

# SET BY MATTHEW, 2026-09-06 (session 15): a random control drawn from a population under
# 20 -- in practice a census of a small run -- uses 0.15. On nine rows a single exclusion
# is 11.1%, and one extraction-span defect on a census of nine was quarantining eight rows
# the reviewer had judged supported. The 0.10 above stays for populations of 20 or more
# and is still the value every artifact before this date was evaluated against. The
# literal in force is stamped on each artifact as `threshold_applied`, so the rule can be
# changed again without changing what any existing artifact says.
SMALL_POPULATION_CEILING = 20
SMALL_POPULATION_THRESHOLD = 0.15


def threshold_for(population_n: int | None) -> float:
    """The exclusion threshold in force for a random control of this population size."""
    if population_n is not None and population_n < SMALL_POPULATION_CEILING:
        return SMALL_POPULATION_THRESHOLD
    return RANDOM_CONTROL_EXCLUSION_THRESHOLD


def gate_doc_hash(path: Path | None = None) -> str:
    """SHA-256 of the gate document the audit was performed against.

    The path alone is not enough. The gate is a checked-in markdown file that will be
    edited as the strata are refined, so "audited against docs/gates/..." six weeks from
    now names a document that may no longer say what the auditor read. The hash makes the
    claim checkable.
    """
    path = GATE_DOC if path is None else path
    if not path.exists():
        raise FileNotFoundError(f"gate document missing: {path}")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# Files the sampler writes alongside an artifact, in the same directory and with the same
# `harness_id` / `harness_version` fields inside them. They are inputs to human judgment,
# never records of it, and `load_artifacts` must not mistake one for the other.
# `__verdicts.json` is the judged input an artifact is BUILT FROM (scripts/write_audit_artifact.py
# reads it). It carries the same harness_id / harness_version, so without this declaration
# load_artifacts reports it as a misnamed artifact -- which it is not. Kept in version control
# deliberately: it is the record of what was put in front of the reviewer, beside the artifact
# recording what came back. Added 2026-09-20 after H-FMCSA-01 v1.7's verdicts file raised exactly
# that warning.
SIDECAR_SUFFIXES = ("__strata.json", "__verdicts.json")


def audit_path(harness_id: str, harness_version: str) -> Path:
    """The one definition of where an artifact lives. `load_artifacts` checks candidate
    files against this rather than against a pattern of its own, so the writer and the
    reader cannot drift apart."""
    return AUDIT_DIR / f"{harness_id}__{harness_version}.json"


@dataclass
class Stratum:
    """One adversarial sample. Not extrapolatable by construction -- it is drawn from
    where defects were predicted to be, so its precision rate describes that corner and
    nothing else. `selection_rule` has to be specific enough to re-execute."""

    stratum_id: str
    selection_rule: str
    sampled_n: int
    verdict_counts: dict = field(default_factory=lambda: {v: 0 for v in VERDICTS})
    population_n: int | None = None   # size of the stratum, where it is knowable

    def excluded(self) -> int:
        return sum(self.verdict_counts.get(v, 0) for v in EXCLUDING_VERDICTS)


@dataclass
class RandomControl:
    """The only sample that produces an extrapolatable precision rate.

    `population_n` is required, not optional, and is stated explicitly in the artifact.
    A precision rate without its denominator is the same error as a failure table without
    an attempts table (convention 5): it cannot distinguish "rare" from "we stopped
    looking".
    """

    sampled_n: int
    population_n: int
    verdict_counts: dict = field(default_factory=lambda: {v: 0 for v in VERDICTS})

    @property
    def precision_rate(self) -> float:
        if not self.sampled_n:
            return 0.0
        return round(self.verdict_counts.get("supported", 0) / self.sampled_n, 4)

    @property
    def exclusion_rate(self) -> float:
        if not self.sampled_n:
            return 0.0
        excluded = sum(self.verdict_counts.get(v, 0) for v in EXCLUDING_VERDICTS)
        return round(excluded / self.sampled_n, 4)


@dataclass
class AuditArtifact:
    harness_id: str
    harness_version: str
    run_id: str
    auditor: str
    population_size: int
    strata: list
    random_control: RandomControl
    row_ids_sampled: list
    verdict: str = ""             # pass / fail, derived by evaluate()
    disposition: str = ""         # what happens to the run's output
    stop_rule_triggered: list = field(default_factory=list)
    threshold_applied: float | None = None   # resolved by evaluate() from the population
    audit_date: str = ""
    gate_doc: str = ""
    gate_doc_sha256: str = ""
    # ---- optional ----
    per_row_notes: list = field(default_factory=list)
    summary_md: str = ""
    defect_introduced_in: str = ""

    def wrong_entity_total(self) -> int:
        n = self.random_control.verdict_counts.get("wrong_entity", 0)
        for s in self.strata:
            n += s.verdict_counts.get("wrong_entity", 0)
        return n

    def evaluate(self) -> "AuditArtifact":
        """Apply the stop rule. Two independent triggers, either of which quarantines.

        A wrong-entity finding is absolute and is not a rate. One row about the wrong
        company means the identity test itself is wrong, and identity defects are not
        distributed randomly -- the Prime Inc. bug produced four wrong-company rows out of
        a sample of four, and would have produced a wrong row for every press release
        mentioning any company whose name contains "prime". A threshold on that would be
        measuring the wrong thing.
        """
        if self.threshold_applied is None:
            self.threshold_applied = threshold_for(self.random_control.population_n)
        triggers = []
        we = self.wrong_entity_total()
        if we:
            triggers.append(
                f"wrong_entity: {we} row(s) attributed to the wrong company -- any "
                f"non-zero count quarantines, no rate applies")
        rate = self.random_control.exclusion_rate
        if rate > self.threshold_applied:
            triggers.append(
                f"random_control exclusion rate {rate:.2%} exceeds threshold "
                f"{self.threshold_applied:.2%} "
                f"({self.random_control.sampled_n} sampled of "
                f"{self.random_control.population_n})")
        self.stop_rule_triggered = triggers
        self.verdict = "fail" if triggers else "pass"
        self.disposition = (
            "quarantined -- harness returns for a fix; no coverage number publishes"
            if triggers else
            "released -- run may contribute to published coverage")
        return self

    def to_dict(self) -> dict:
        if not self.audit_date:
            self.audit_date = _dt.date.today().isoformat()
        if not self.gate_doc:
            self.gate_doc = str(GATE_DOC.relative_to(ROOT)).replace("\\", "/")
        if not self.gate_doc_sha256:
            self.gate_doc_sha256 = gate_doc_hash()
        d = {
            "harness_id": self.harness_id,
            "harness_version": self.harness_version,
            "run_id": self.run_id,
            "audit_date": self.audit_date,
            "auditor": self.auditor,
            "gate_doc": self.gate_doc,
            "gate_doc_sha256": self.gate_doc_sha256,
            "population_size": self.population_size,
            "strata": [asdict(s) for s in self.strata],
            "random_control": {
                **asdict(self.random_control),
                "precision_rate": self.random_control.precision_rate,
                "exclusion_rate": self.random_control.exclusion_rate,
            },
            "row_ids_sampled": list(self.row_ids_sampled),
            "threshold_applied": self.threshold_applied,
            "stop_rule_triggered": list(self.stop_rule_triggered),
            "verdict": self.verdict,
            "disposition": self.disposition,
        }
        if self.per_row_notes:
            d["per_row_notes"] = self.per_row_notes
        if self.summary_md:
            d["summary_md"] = self.summary_md
        if self.defect_introduced_in:
            d["defect_introduced_in"] = self.defect_introduced_in
        return d

    def write(self) -> Path:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        path = audit_path(self.harness_id, self.harness_version)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path


REQUIRED_FIELDS = [
    "harness_id", "harness_version", "run_id", "audit_date", "auditor", "gate_doc",
    "gate_doc_sha256", "population_size", "strata", "random_control", "row_ids_sampled",
    "threshold_applied", "stop_rule_triggered", "verdict", "disposition",
]


def validate_artifact(data: dict) -> list[str]:
    """Structural check on a loaded artifact. Returns a list of problems."""
    problems = []
    for f in REQUIRED_FIELDS:
        if f not in data:
            problems.append(f"missing required field {f!r}")
    if "threshold_applied" in data and not isinstance(
            data["threshold_applied"], (int, float)):
        problems.append("threshold_applied must be a literal number, not a reference")
    rc = data.get("random_control") or {}
    for f in ("sampled_n", "population_n", "verdict_counts"):
        if f not in rc:
            problems.append(f"random_control is missing {f!r}")
    if "verdict_counts" in rc:
        for v in VERDICTS:
            if v not in rc["verdict_counts"]:
                problems.append(f"random_control.verdict_counts is missing {v!r}")
    for i, s in enumerate(data.get("strata") or []):
        for f in ("stratum_id", "selection_rule", "sampled_n", "verdict_counts"):
            if f not in s:
                problems.append(f"strata[{i}] is missing {f!r}")
        for v in VERDICTS:
            if v not in (s.get("verdict_counts") or {}):
                problems.append(f"strata[{i}].verdict_counts is missing {v!r}")
    if data.get("verdict") not in ("pass", "fail"):
        problems.append(f"verdict must be 'pass' or 'fail', got {data.get('verdict')!r}")
    return problems


def grandfathered_added_on(path: Path | None = None) -> dict:
    """(harness_id, harness_version) -> the date_added recorded in the registry.

    The exemption is a statement about the output that EXISTED when it was granted: every
    entry rests on a hand audit performed on that date. A version is not a closed set,
    though -- a later run can write new rows under the same version label, and those rows
    would inherit an exemption nobody granted them. check 9 uses these dates to require an
    audit artifact for exactly that case (H-FMCSA-01 v1.3, which gained 4 rows on
    2026-09-01, a day after its exemption).
    """
    path = GRANDFATHER_REGISTRY if path is None else path
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(e["harness_id"], e["harness_version"]): str(e.get("date_added") or "")
            for e in data.get("grandfathered", [])}


def load_artifacts(directory: Path | None = None) -> dict:
    """Every artifact on disk, keyed (harness_id, harness_version).

    `directory` resolves at call time rather than being bound as a default argument: a
    default of `AUDIT_DIR` freezes the path at import, so anything that redirects the
    directory would silently keep reading the real one and report a clean result about a
    location nothing had been written to.

    A FILE IS AN ARTIFACT ONLY IF ITS NAME SAYS SO, and that is load-bearing rather than
    tidy. This directory holds sidecars from the sampler -- `__strata.json` -- which carry
    `harness_id` and `harness_version` at top level because they describe the same run.
    Globbing `*.json` and keying on those fields therefore loaded sample-selection files
    as though they were audit verdicts: on 2026-09-01 two of the four entries this
    function returned were strata files, and the only reason check 9 stayed green was that
    both versions happened to be quarantined so nothing looked them up. Releasing either
    one would have made the check report a freshly-written, perfectly valid artifact as
    malformed.

    That is convention 36 -- a lookup answering confidently about the wrong thing -- in
    the gate's own machinery. The test is the filename the artifact is *written* under:
    `audit_path()` is the single definition of that name, and a file whose contents do not
    round-trip to its own name is reported rather than silently skipped, because a
    misnamed real artifact is a defect and must not read as an absent one.
    """
    directory = AUDIT_DIR if directory is None else directory
    out = {}
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            out[(path.stem, "?")] = {"_parse_error": str(exc), "_path": str(path)}
            continue
        hid, ver = data.get("harness_id"), data.get("harness_version")
        if hid is None or ver is None:
            continue                       # not an artifact and not claiming to be
        if path.name != audit_path(hid, ver).name:
            # Names the sampler owns are sidecars, not artifacts, and are skipped
            # quietly. Anything else claiming an id and a version but sitting under the
            # wrong name is surfaced -- it may be an artifact nobody can find.
            if not any(path.name.endswith(sfx) for sfx in SIDECAR_SUFFIXES):
                out[(hid, f"{ver}!misnamed")] = {
                    "_misnamed": (f"{path.name} declares {hid} {ver}, which belongs in "
                                  f"{audit_path(hid, ver).name}"),
                    "_path": str(path)}
            continue
        data["_path"] = str(path)
        out[(hid, ver)] = data
    return out


def load_grandfathered(path: Path | None = None) -> set:
    """Exempt (harness_id, harness_version) pairs.

    The registry is the *only* exemption mechanism. An earlier draft scoped the check by
    date -- "first run on or after 2026-09-01" -- which fails the moment a harness lands
    either side of the boundary, which H-EMPREVIEW-01 was doing while the gate was being
    specified. An explicit list of pairs has no boundary to land on.
    """
    path = GRANDFATHER_REGISTRY if path is None else path
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(e["harness_id"], e["harness_version"]) for e in data.get("grandfathered", [])}


def derive_reprocessing_required(harness_id: str,
                                 artifacts: dict | None = None) -> dict | None:
    """Is reprocessing required for `harness_id` on the evidence of its audits?

    True when some audit artifact for the harness records `wrong_entity > 0` and has not
    been superseded by a passing audit on a *later* harness_version. A wrong-entity
    finding is a code defect, and a code defect that produced wrong rows in the sample
    produced them outside the sample too -- which is exactly the condition convention 27's
    `reprocessing_required` exists for.

    Blast radius defaults to the audited version and all versions before it. Narrowing it
    requires the artifact to carry `defect_introduced_in`, because "the bug was only in
    v1.2" is a claim about code history that someone has to have actually checked.

    Returns None when nothing requires reprocessing, otherwise a dict describing what and
    why. Derived on read; never written into an artifact, so it cannot go stale.
    """
    artifacts = load_artifacts() if artifacts is None else artifacts
    mine = {v: a for (h, v), a in artifacts.items() if h == harness_id}
    if not mine:
        return None

    def vkey(v: str) -> tuple:
        return tuple(int(p) for p in str(v).lstrip("v").split(".") if p.isdigit())

    failing = []
    for version, art in mine.items():
        we = (art.get("random_control", {}).get("verdict_counts", {}) or {}).get(
            "wrong_entity", 0)
        for s in art.get("strata") or []:
            we += (s.get("verdict_counts") or {}).get("wrong_entity", 0)
        if we:
            failing.append((version, we, art))
    if not failing:
        return None

    latest_pass = None
    for version, art in mine.items():
        if art.get("verdict") == "pass":
            if latest_pass is None or vkey(version) > vkey(latest_pass):
                latest_pass = version

    live = [(v, n, a) for v, n, a in failing
            if latest_pass is None or vkey(v) >= vkey(latest_pass)]
    if not live:
        return None

    worst_version, count, art = sorted(live, key=lambda t: vkey(t[0]))[0]
    narrowed = art.get("defect_introduced_in")
    if narrowed:
        radius = (f"{narrowed} and later versions up to {worst_version} "
                  f"(narrowed by defect_introduced_in)")
    else:
        radius = f"{worst_version} and all prior versions of {harness_id}"
    return {
        "harness_id": harness_id,
        "reprocessing_required": True,
        "reason": (f"audit of {harness_id} {worst_version} recorded {count} wrong_entity "
                   f"row(s); no passing audit on a later version supersedes it"),
        "blast_radius": radius,
        "superseded_by": latest_pass,
        "artifact": art.get("_path", ""),
    }
