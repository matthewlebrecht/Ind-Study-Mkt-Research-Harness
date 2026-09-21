"""
Observation validity: the vocabulary, the row and history rules, the only writer, and the citation classifier.

Matthew Lebrecht's standing rule, 2026-09-15: NO OBSERVATION, FROM ANY HARNESS, IS EVER HARD-DELETED AGAIN. A bad
observation keeps its row and its id; its invalidity is recorded here as a determination. Anything that cites it --
a Company_State_History derivation, a role review, an audit artifact -- stays structurally valid and points at
something flagged invalid, rather than at something that is no longer there.

`Observation_Validity_History` has the discipline of `SEC_Reporting_Status_History` and the coherence /
directionality tables:

  * APPEND-ONLY. One row per determination. Nothing is ever updated except `superseded_by`, the forward pointer a
    determination gets when a later one about the same observation replaces it. Nothing is deleted.
  * One CURRENT (non-superseded) determination per observation. An observation with no row is simply undetermined.
  * The observation must exist: a determination is recorded on a row that persists.
  * Vocabulary (Lookups!AF) starts with `invalidated_extraction_defect` and is additive-only (convention 22); other
    invalidation reasons are added as values, never as columns.

THE CONVENTION 41 WALL, AS AMENDED 2026-09-15 (validate_repo_db check 15, a FAILURE): validity must never feed
review_status, audit_verdict, publication_state or reprocessing_required. Matthew's decision the same day (item 19)
is that composition, published coverage and the reconciler READ AN INVALID ROW AS INVALID. So exactly three gate
modules may read validity, and only through the one read accessor `invalid_observation_ids` (READERS below; the
reconciler only inside `sync_observations`); every other gate module may not name the table or import this module,
and the readers may use nothing else from it. `wall_violations` is the scan -- the validator and the tests call it.

THREE MEASUREMENTS, NEVER A SILENT NET: every published count that invalid rows could move reports total, valid and
invalid separately (the gap report, published coverage, derivation notes, the reconciler's run summary, CLAUDE.md).
Audit artifacts are historical records and are never rewritten: their counts are what was true on their audit date,
and no live script quotes an artifact's count as a current figure.
"""

from __future__ import annotations

import re
from pathlib import Path

SHEET = "Observation_Validity_History"
COLUMNS = ["id", "observation_id", "validity_status", "as_of_date", "determined_at", "determined_by", "basis",
           "superseded_by", "notes"]
DEFINITIONS = {
    "invalidated_extraction_defect": (
        "The claim is not supported by its own evidence because extraction read the wrong text -- e.g. a theme "
        "matched on page furniture outside the article. The row and its id persist; the observation is flagged "
        "invalid, not removed."),
    "invalidated_not_reproduced": (
        "The harness that wrote the claim no longer produces it (the retirement of a row a run stopped proposing, "
        "since 2026-09-15 recorded here instead of deleting it). A machine determination unless the basis says "
        "otherwise; it says nothing about whether the claim was ever true."),
    "invalidated_duplicate": (
        "The claim duplicates another observation that stands (the basis names it); counting both would count one "
        "piece of evidence twice."),
    "invalidated_wrong_entity": (
        "The evidence is about a different entity than the company the row names -- an identity failure, not a "
        "weak claim."),
}
STATUSES = tuple(DEFINITIONS)
ID_PREFIX = "OVH-"
_ID = re.compile(r"^OVH-\d{4}$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def live_observation_ids(wb) -> set[str]:
    ws = wb["Observations"]
    return {_s(r[0]) for r in ws.iter_rows(min_row=2, max_col=1, values_only=True) if r[0]}


def registry(wb) -> dict[str, str]:
    """observation_id -> registry status ('live' / 'retired') for every id ever assigned."""
    if "Observation_Ids" not in wb.sheetnames:
        return {}
    ws = wb["Observation_Ids"]
    h = [c.value for c in ws[1]]
    i = h.index("status")
    return {_s(r[0]): _s(r[i]) for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]}


def problems_with(d: dict, live_ids: set[str] | None = None) -> list[str]:
    """Why one determination may not be written, on its own; empty if it may."""
    p = []
    status = _s(d.get("validity_status"))
    if status not in STATUSES:
        p.append(f"validity_status {status!r} is not one of {list(STATUSES)}")
    oid = _s(d.get("observation_id"))
    if not oid:
        p.append("observation_id is required")
    elif live_ids is not None and oid not in live_ids:
        p.append(f"{oid} has no Observations row: a validity determination is recorded on a row that persists "
                 f"(restore it first -- observations are never hard-deleted)")
    for f in ("as_of_date", "determined_at"):
        if not _ISO.match(_s(d.get(f))):
            p.append(f"{f} must be an ISO date")
    for f in ("determined_by", "basis"):
        if not _s(d.get(f)):
            p.append(f"{f} is required")
    if _s(d.get("id")) and not _ID.match(_s(d.get("id"))):
        p.append(f"id {d.get('id')!r} is not of the form OVH-NNNN")
    return p


def rows_from_sheet(ws) -> list[dict]:
    headers = [ws.cell(1, c).value for c in range(1, len(COLUMNS) + 1)]
    if headers != COLUMNS:
        raise ValueError(f"{SHEET} header drift: {headers}")
    return [{c: (r[i] if i < len(r) else None) for i, c in enumerate(COLUMNS)}
            for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]]


def current_rows(rows: list[dict]) -> dict[str, dict]:
    """The non-superseded determination per observation (the last by id if the table is malformed)."""
    out: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: _s(r["id"])):
        if not _s(r.get("superseded_by")):
            out[_s(r["observation_id"])] = r
    return out


def invalid_observation_ids(wb) -> dict[str, str]:
    """{observation_id: current validity_status} for every observation currently recorded invalid.

    THE ONE READ ACCESSOR a gate module may call (READERS). An observation with no determination is valid. A workbook
    without the table has no determinations; check 15 fails on the missing table separately.
    """
    if SHEET not in wb.sheetnames:
        return {}
    return {oid: r["validity_status"] for oid, r in current_rows(rows_from_sheet(wb[SHEET])).items()
            if r["validity_status"].startswith("invalidated")}


GATE_MODULES = ("core/db.py", "core/audit.py", "core/attempts.py", "core/composition.py",
                "scripts/write_audit_artifact.py", "scripts/validate_repo_db.py", "scripts/published_coverage.py",
                "scripts/audit_sample.py", "scripts/check_run_ledger.py")
# module -> the one function it may read validity in (None: anywhere in the module). Matthew, 2026-09-15, item 19.
READERS = {"core/composition.py": None, "scripts/published_coverage.py": None, "core/db.py": "sync_observations"}
ACCESSOR = "invalid_observation_ids"
_REF = re.compile(r"Observation_Validity_History|core\.validity\b|import\s+validity\b|validity\s+import")
_ATTR = re.compile(r"\bvalidity\.(\w+)")
_IMPORT = re.compile(r"^\s*from core import validity\s*(#.*)?$")
_DEF = re.compile(r"^(\s*)def (\w+)\(")


def wall_violations(root: Path, sources: dict[str, str] | None = None) -> list[str]:
    """Every line of a gate module that reads validity other than as permitted -- `module:line`. `sources` overrides a
    module's text (tamper tests). The validator's own fenced check 15 region is exempt."""
    out = []
    for mod in GATE_MODULES:
        if sources is not None and mod in sources:
            text = sources[mod]
        else:
            path = Path(root) / mod
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        fence = None
        if mod == "scripts/validate_repo_db.py":
            b = next((i for i, l in enumerate(lines, 1) if "VALIDITY-WALL-CHECK-BEGIN" in l and "in l" not in l), 0)
            e = next((i for i, l in enumerate(lines, 1) if "VALIDITY-WALL-CHECK-END" in l and "in l" not in l), 0)
            fence = (b, e) if b and e else None
        enclosing = None
        for i, line in enumerate(lines, 1):
            d = _DEF.match(line)
            if d and len(d.group(1)) <= 4:
                enclosing = d.group(2)
            if fence and fence[0] <= i <= fence[1]:
                continue
            attrs = _ATTR.findall(line)
            if not (_REF.search(line) or attrs):
                continue
            if mod in READERS:
                if _IMPORT.match(line):
                    continue
                scope = READERS[mod]
                if (attrs and all(a == ACCESSOR for a in attrs) and not _REF.search(line)
                        and (scope is None or enclosing == scope)):
                    continue
            out.append(f"{mod}:{i}")
    return out


def history_problems(rows: list[dict], live_ids: set[str], known_ids: set[str]) -> list[str]:
    """Rules the table must satisfy as a whole."""
    p = []
    by_id = {}
    for r in rows:
        rid = _s(r["id"])
        if rid in by_id:
            p.append(f"duplicate id {rid}")
        by_id[rid] = r
        for prob in problems_with(r):
            p.append(f"{rid}: {prob}")
        oid = _s(r["observation_id"])
        if oid and oid not in known_ids:
            p.append(f"{rid}: {oid} was never assigned an observation id")
        elif oid and oid not in live_ids:
            p.append(f"{rid}: {oid} no longer has an Observations row -- an observation with a validity "
                     f"determination was hard-deleted")
    for r in rows:
        sup = _s(r.get("superseded_by"))
        if not sup:
            continue
        t = by_id.get(sup)
        if t is None:
            p.append(f"{r['id']}: superseded_by {sup} does not exist")
        elif _s(t["observation_id"]) != _s(r["observation_id"]):
            p.append(f"{r['id']}: superseded_by {sup} is a determination about another observation")
        elif sup <= _s(r["id"]):
            p.append(f"{r['id']}: superseded_by {sup} points backward")
    current = {}
    for r in rows:
        if not _s(r.get("superseded_by")):
            current.setdefault(_s(r["observation_id"]), []).append(_s(r["id"]))
    multi = {o: ids for o, ids in current.items() if len(ids) > 1}
    if multi:
        p.append(f"more than one current determination for {sorted(multi.items())[:4]}")
    return p


def _next_id(rows: list[dict]) -> str:
    n = max((int(_s(r["id"])[len(ID_PREFIX):]) for r in rows if _ID.match(_s(r["id"]))), default=0)
    return f"{ID_PREFIX}{n + 1:04d}"


def append_determinations(wb, determinations: list[dict]) -> dict:
    """Append validity determinations. APPEND-ONLY and ALL OR NOTHING.

    Every determination is checked before any is written. Per determination: refused if it breaks the row rules
    (including a missing Observations row); a no-op if the observation's CURRENT determination already has the same
    status and basis; refused if its as_of_date is earlier than the current one's (supersession points forward only);
    otherwise appended, and the previous current determination gets `superseded_by` -- the only field ever set on an
    existing row. Returns {"appended": [ids], "noop": [(observation_id, why)], "superseded": [(old, new)]}.
    """
    if SHEET not in wb.sheetnames:
        raise ValueError(f"{SHEET} missing -- run scripts/migrate_schema.py --apply")
    ws = wb[SHEET]
    rows = rows_from_sheet(ws)
    live = live_observation_ids(wb)
    problems = []
    for d in determinations:
        probs = problems_with(d, live)
        if probs:
            problems.append(f"{_s(d.get('observation_id'))}: {probs[0]}")
            continue
        cur = current_rows(rows).get(_s(d["observation_id"]))
        if cur and _s(d["as_of_date"]) < _s(cur["as_of_date"]):
            problems.append(f"{d['observation_id']}: as of {d['as_of_date']} cannot supersede {cur['id']} as of "
                            f"{cur['as_of_date']} -- supersession points forward only")
    if problems:
        raise ValueError(f"{len(problems)} determination(s) refused, nothing written: " + "; ".join(problems[:6]))
    report = {"appended": [], "noop": [], "superseded": []}
    for d in determinations:
        oid = _s(d["observation_id"])
        cur = current_rows(rows).get(oid)
        if cur and _s(cur["validity_status"]) == _s(d["validity_status"]) and _s(cur["basis"]) == _s(d["basis"]):
            report["noop"].append((oid, f"current determination {cur['id']} already records this"))
            continue
        row = {c: d.get(c) for c in COLUMNS}
        row["id"], row["superseded_by"] = _next_id(rows), None
        ws.append([row[c] for c in COLUMNS])
        if cur:
            i_id, i_sup = COLUMNS.index("id") + 1, COLUMNS.index("superseded_by") + 1
            for r in range(2, ws.max_row + 1):
                if _s(ws.cell(r, i_id).value) == _s(cur["id"]):
                    ws.cell(r, i_sup).value = row["id"]
                    break
            cur["superseded_by"] = row["id"]
            report["superseded"].append((cur["id"], row["id"]))
        rows.append(row)
        report["appended"].append(row["id"])
    return report


def citation_states(cited_ids, live_ids: set[str], registry_status: dict[str, str],
                    current: dict[str, dict]) -> dict[str, str]:
    """What each cited observation id points at now:
    'valid' (a live row with no current invalidation), 'invalidated:<status>', 'deleted' (a retired id with no row --
    the pre-rule hard deletions), or 'never assigned'."""
    out = {}
    for oid in cited_ids:
        oid = _s(oid)
        if not oid:
            continue
        if oid in live_ids:
            cur = current.get(oid)
            out[oid] = f"invalidated:{cur['validity_status']}" if cur else "valid"
        elif registry_status.get(oid) == "retired":
            out[oid] = "deleted"
        else:
            out[oid] = "never assigned"
    return out


def derivation_citations(wb) -> list[dict]:
    """Every Company_State_History row with its supporting observation ids, split."""
    if "Company_State_History" not in wb.sheetnames:
        return []
    ws = wb["Company_State_History"]
    h = [c.value for c in ws[1]]
    i = {k: h.index(k) for k in ("state_id", "derivation_id", "bucket_id", "company_id", "theme_key", "status",
                                 "supporting_observation_ids")}
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        ids = [x for x in _s(r[i["supporting_observation_ids"]]).split(";") if x.strip()]
        if ids:
            out.append({k: r[v] for k, v in i.items() if k != "supporting_observation_ids"} | {"cited": ids})
    return out


def invalidate_unreproduced(db, harness_id: str, version: str, proposed: list, company_ids=None, source_urls=None,
                            as_of: str | None = None, status: str = "invalidated_not_reproduced",
                            basis: str | None = None) -> dict:
    """Retirement, under convention 45: record as invalid the rows a run no longer produces. NOTHING IS DELETED.

    `status` and `basis` exist because the default says only what the RUN observed -- that the claim is no longer
    produced -- and sometimes the reason is known and should be named instead (Matthew Lebrecht, 2026-09-15, item 22:
    the rows H-FIRSTPARTY-01 v1.3 stops producing are `invalidated_extraction_defect`, because v1.2 matched the theme
    on page furniture). The status must be a recorded one; a caller naming a status must give the basis that justifies
    it, rather than a later relabelling of rows written under the wrong reason.

    Asks core/db.py::unreproduced_observations which of this harness's machine rows the run did not re-propose
    (optionally only for `company_ids` and pages in `source_urls`), and appends an `invalidated_not_reproduced`
    determination for each that has no current determination yet. A row that is already invalid keeps its
    determination (a not-reproduced finding does not supersede, say, an extraction-defect verdict). Human-reviewed
    rows are never eligible; they come back under `held` (convention 35). The basis is stable per harness version,
    so re-running the same version writes nothing twice.
    """
    import datetime as _dt
    if SHEET not in db.wb.sheetnames:
        raise ValueError(f"{SHEET} missing -- run scripts/migrate_schema.py --apply")
    if status not in STATUSES:
        raise ValueError(f"validity_status {status!r} is not recorded; known: {list(STATUSES)}")
    if status != "invalidated_not_reproduced" and not _s(basis):
        raise ValueError(f"recording {status} rather than invalidated_not_reproduced needs a basis saying why")
    found = db.unreproduced_observations(harness_id, proposed, company_ids=company_ids, source_urls=source_urls)
    current = current_rows(rows_from_sheet(db.wb[SHEET]))
    fresh = [oid for oid in found["eligible"] if oid not in current]
    already = [oid for oid in found["eligible"] if oid in current]
    day = as_of or _dt.date.today().isoformat()
    basis = _s(basis) or (f"not reproduced by {harness_id} {version}: the run no longer proposes this claim"
                          + (" from a page it re-read" if source_urls is not None else ""))
    dets = [{"observation_id": oid, "validity_status": status, "as_of_date": day,
             "determined_at": day, "determined_by": f"{harness_id} {version} (machine run, not a reviewer)",
             "basis": basis, "notes": ""} for oid in fresh]
    rep = append_determinations(db.wb, dets) if dets else {"appended": [], "noop": [], "superseded": []}
    return {"invalidated": fresh, "already_invalid": already, "held": found["held"], "determinations": rep["appended"]}


def _natural_keys(wb) -> tuple[dict, set]:
    from core.db import natural_key_of
    ws = wb["Observations"]
    h = [c.value for c in ws[1]]
    live_keys = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            live_keys.setdefault(natural_key_of(dict(zip(h, r))), []).append(_s(r[0]))
    reg_ws = wb["Observation_Ids"] if "Observation_Ids" in wb.sheetnames else None
    retired = set()
    if reg_ws is not None:
        rh = [c.value for c in reg_ws[1]]
        for r in reg_ws.iter_rows(min_row=2, values_only=True):
            if r and r[0] and _s(r[rh.index("status")]) == "retired":
                retired.add((_s(r[0]), _s(r[rh.index("natural_key")])))
    return live_keys, retired


def hard_deletions(wb) -> list[str]:
    """Retired observation ids whose claim has no live row anywhere: observations that were hard-deleted.
    Convention 45 requires this to be empty."""
    live_keys, retired = _natural_keys(wb)
    return sorted(oid for oid, key in retired if key not in live_keys)


def lineage_problems(wb) -> list[str]:
    """Item 20 (Matthew Lebrecht, 2026-09-15): a retired id whose claim is live records that live id as `current_id`;
    a live id records none. (A retired id whose claim has no live row is a hard deletion, reported separately.)"""
    if "Observation_Ids" not in wb.sheetnames:
        return []
    ws = wb["Observation_Ids"]
    rh = [c.value for c in next(ws.iter_rows(max_row=1))]
    if "current_id" not in rh:
        return ["Observation_Ids has no current_id column -- run scripts/migrate_schema.py --apply"]
    live_keys, _ = _natural_keys(wb)
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[0]:
            continue
        d = dict(zip(rh, r))
        oid, cur, status = _s(d.get("observation_id")), _s(d.get("current_id")), _s(d.get("status"))
        if status == "live" and cur:
            out.append(f"{oid}: live, but records current_id {cur}")
        elif status == "retired":
            owners = live_keys.get(_s(d.get("natural_key")), [])
            if len(owners) == 1 and cur != owners[0]:
                out.append(f"{oid}: current_id {cur or '(blank)'}, but its claim is live as {owners[0]}")
            elif not owners and cur:
                out.append(f"{oid}: current_id {cur}, but its claim has no live row")
    return out


def renumbered(wb) -> dict[str, list[str]]:
    """Retired ids whose claim IS live under another id: the pre-convention-43 delete-and-rewrite renumberings. The
    evidence persists; only the id changed. Not restorable as rows (that would give one claim two live ids)."""
    live_keys, retired = _natural_keys(wb)
    return {oid: live_keys[key] for oid, key in sorted(retired) if key in live_keys}
