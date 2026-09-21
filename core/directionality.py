"""
Evidence directionality: the vocabulary, the row rules, and the only writer.

Build handoff 2026-09-15 (Signal Advisor, finalized). `evidence_directionality` says which side of a
transaction the company sits on in the evidence -- `buyer_side`, `seller_side`, `mixed` or
`not_applicable`. It is an OPTIONAL, NON-BLOCKING classification of an observation, so it lives
in its own linked table keyed BY observation_id and is never a column on `Observations`
(convention 44, the standing pattern for any tag of this kind).

  * It applies across every `evidence_role` and corrects nothing: `evidence_role`,
    `organizational_state` and every other axis are untouched.
  * Sparse by design: an observation with no row is untagged, not "not_applicable".
  * THE CONVENTION 41 WALL: no code path computing review_status, audit_verdict,
    publication_state or reprocessing_required may read this table, directly or by join, and
    none may import this module. validate_repo_db check 13 asserts it as a FAILURE.

The writer lives here rather than in core/db.py because core/db.py computes gate values and is
one of the modules the wall scans.
"""

from __future__ import annotations

import re

SHEET = "Observation_Directionality_Tags"
COLUMNS = ["observation_id", "evidence_directionality", "tagged_at", "tagging_run_id", "notes"]
VALUES = ("buyer_side", "seller_side", "mixed", "not_applicable")

# A backfill batch is marked by its tagging_run_id, distinguishable from live harness tagging,
# and must cite the finding it rests on (handoff §2).
BACKFILL_PREFIX = "backfill_"


def observation_ids(wb) -> set[str]:
    ws = wb["Observations"]
    return {str(r[0]).strip() for r in ws.iter_rows(min_row=2, max_col=1, values_only=True) if r[0]}


def problems_with(row: dict, obs_ids: set[str] | None = None) -> list[str]:
    p = []
    oid = str(row.get("observation_id") or "").strip()
    if not oid:
        p.append("observation_id is required")
    elif obs_ids is not None and oid not in obs_ids:
        p.append(f"observation_id {oid} does not resolve in Observations")
    value = row.get("evidence_directionality")
    if value not in VALUES:
        p.append(f"evidence_directionality {value!r} is not one of {list(VALUES)}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row.get("tagged_at") or "")):
        p.append("tagged_at must be an ISO date (the load date)")
    run = str(row.get("tagging_run_id") or "").strip()
    if not run:
        p.append("tagging_run_id is required")
    notes = str(row.get("notes") or "").strip()
    if value == "mixed" and not notes:
        p.append("a mixed tag needs notes giving the rationale")
    if run.startswith(BACKFILL_PREFIX) and not notes:
        p.append("a backfilled tag needs notes citing the finding it rests on")
    return p


def rows_from_sheet(ws) -> list[dict]:
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    if [h for h in headers if h] != COLUMNS:
        raise ValueError(f"{SHEET} header is {headers}, expected {COLUMNS}")
    out = []
    for r in ws.iter_rows(min_row=2, max_col=len(COLUMNS), values_only=True):
        if all(v in (None, "") for v in r):
            continue
        out.append({h: r[i] for i, h in enumerate(COLUMNS)})
    return out


def append_tags(wb, tags: list[dict]) -> dict:
    """Append directionality tags. ALL OR NOTHING.

    The whole batch is refused (ValueError, nothing written) if any tag breaks the row rules,
    names an observation_id that does not resolve, or gives an (observation_id, tagging_run_id)
    pair already in the table a DIFFERENT value. An identical tag already present is a no-op,
    so re-running a batch never writes twice. Nothing is ever updated or deleted.
    """
    if SHEET not in wb.sheetnames:
        raise ValueError(f"{SHEET} missing -- run scripts/migrate_schema.py --apply")
    ws = wb[SHEET]
    existing = {(str(r["observation_id"]), str(r["tagging_run_id"])): r for r in rows_from_sheet(ws)}
    ids = observation_ids(wb)
    problems, to_write, noop, seen = [], [], [], set()
    for t in tags:
        row = {c: t.get(c) for c in COLUMNS}
        probs = problems_with(row, ids)
        key = (str(row["observation_id"]), str(row["tagging_run_id"]))
        if key in seen:
            probs.append("the same (observation_id, tagging_run_id) appears twice in the batch")
        seen.add(key)
        prior = existing.get(key)
        if prior is not None:
            if prior["evidence_directionality"] != row["evidence_directionality"]:
                probs.append(f"already tagged {prior['evidence_directionality']!r} in this run; "
                             f"a tag is never overwritten")
            elif not probs:
                noop.append(key[0])
                continue
        if probs:
            problems.append(f"{row['observation_id']}: {probs[0]}")
        else:
            to_write.append(row)
    if problems:
        raise ValueError(f"{len(problems)} tag(s) refused, nothing written: " + "; ".join(problems[:6]))
    for row in to_write:
        ws.append([row[c] for c in COLUMNS])
    return {"appended": len(to_write), "noop": noop}
