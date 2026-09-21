"""
Role-classification review verdicts: the vocabulary, the row and batch rules, the link to the
committed verdicts artifact, and the only writer.

Matthew Lebrecht, 2026-09-15 (option A of the buyer_articulates role-review report). A role review
asks ONE question of a sampled observation -- was `evidence_role` the right classification? -- and
nothing else. Its verdict is an optional, non-blocking classification of the observation, so it
lives in its own linked table keyed BY observation_id and is never written to `Observations`
(convention 44, the directionality table's shape):

  * It re-clears NEITHER identity NOR extraction. `review_source`, `review_status`, `audit_verdict`
    and every other Observations field are left exactly as they were. 39 of the first batch's 59
    rows are machine-reviewed; recording their role verdicts through apply_audit_verdict would have
    made their extraction read as human-cleared, which is the claim this table exists not to make.
  * It corrects nothing. A `buyer_acts` verdict on a `buyer_articulates` row records the reviewer's
    finding; changing the row's role is a separate decision.
  * Every row states its sample basis as numbers -- the batch's n of N, its stratum's n of N, the
    design -- and a batch must reconcile to those numbers and to its committed verdicts artifact,
    so no row can claim more coverage than was reviewed.
  * THE CONVENTION 41 WALL: no code path computing review_status, audit_verdict, publication_state
    or reprocessing_required may read this table, directly or by join, or import this module.
    validate_repo_db check 14 asserts it as a FAILURE, together with the rules below.

The writer lives here rather than in core/db.py for the same reason as core/directionality.py:
core/db.py computes gate values and is one of the modules the wall scans.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SHEET = "Observation_Role_Reviews"
COLUMNS = [
    "observation_id", "role_at_review", "role_verdict", "review_scope", "reviewer",
    "review_source", "reviewed_at", "review_run_id", "sample_design", "sample_n", "population_n",
    "stratum", "stratum_sampled_n", "stratum_population_n", "reviewer_words", "artifact", "notes",
]

# The evidence_role vocabulary (Lookups column A). role_at_review must be one of these.
ROLES = ("buyer_acts", "buyer_articulates", "provider_market_responds")
# `correct` confirms the role under review; any other value names the role the reviewer found
# instead, or says the reviewer could not place it. Never the role under review itself.
VERDICTS = ("correct", "buyer_acts", "buyer_articulates", "provider_market_responds", "other",
            "cant_tell")
SCOPE = "role_only"
# Every row's notes must say this in so many words, so a reader of one row six months on cannot
# take a role verdict for an identity or extraction clearance.
SCOPE_STATEMENT = "re-clears neither identity nor extraction"
DESIGNS = ("stratified_random", "simple_random", "census")
ARTIFACT_DIR = "harness_output/audits/"

_INT_FIELDS = ("sample_n", "population_n", "stratum_sampled_n", "stratum_population_n")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _int(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return int(_s(v)) if re.fullmatch(r"\d+", _s(v)) else None


def observation_ids(wb) -> set[str]:
    """Every observation id ever assigned (the Observation_Ids registry, convention 43), so a
    review of a row later retired still resolves. Falls back to the live sheet."""
    name = "Observation_Ids" if "Observation_Ids" in wb.sheetnames else "Observations"
    ws = wb[name]
    return {_s(r[0]) for r in ws.iter_rows(min_row=2, max_col=1, values_only=True) if r[0]}


def current_roles(wb) -> dict[str, str]:
    ws = wb["Observations"]
    headers = [c.value for c in ws[1]]
    i = headers.index("evidence_role")
    return {_s(r[0]): _s(r[i]) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}


def problems_with(row: dict, obs_ids: set[str] | None = None) -> list[str]:
    """Rules one row must satisfy on its own."""
    p = []
    oid = _s(row.get("observation_id"))
    if not oid:
        p.append("observation_id is required")
    elif obs_ids is not None and oid not in obs_ids:
        p.append(f"observation_id {oid} was never assigned")
    role = _s(row.get("role_at_review"))
    if role not in ROLES:
        p.append(f"role_at_review {role!r} is not an evidence_role ({list(ROLES)})")
    verdict = _s(row.get("role_verdict"))
    if verdict not in VERDICTS:
        p.append(f"role_verdict {verdict!r} is not one of {list(VERDICTS)}")
    elif verdict == role:
        p.append(f"role_verdict repeats the role under review ({role!r}); confirm it with 'correct'")
    if _s(row.get("review_scope")) != SCOPE:
        p.append(f"review_scope must be {SCOPE!r} -- a role review clears nothing else")
    if not _s(row.get("reviewer")):
        p.append("reviewer is required")
    if _s(row.get("review_source")) != "human":
        p.append("review_source must be 'human' -- a role verdict is a person's judgment")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _s(row.get("reviewed_at"))):
        p.append("reviewed_at must be an ISO date")
    run = _s(row.get("review_run_id"))
    if not run:
        p.append("review_run_id is required")
    elif run.startswith("HR-"):
        p.append("review_run_id names a harness run; a role review is not a harness run")
    design = _s(row.get("sample_design"))
    if design not in DESIGNS:
        p.append(f"sample_design {design!r} is not one of {list(DESIGNS)}")
    n = {f: _int(row.get(f)) for f in _INT_FIELDS}
    for f, v in n.items():
        if v is None or v < 1:
            p.append(f"{f} must be a positive integer")
    if None not in n.values():
        if n["sample_n"] > n["population_n"]:
            p.append("sample_n exceeds population_n")
        if n["stratum_sampled_n"] > n["stratum_population_n"]:
            p.append("stratum_sampled_n exceeds stratum_population_n")
        if n["stratum_sampled_n"] > n["sample_n"] or n["stratum_population_n"] > n["population_n"]:
            p.append("the stratum is larger than the batch")
        if design == "census" and n["sample_n"] != n["population_n"]:
            p.append("sample_design 'census' but sample_n < population_n")
        if design != "census" and design in DESIGNS and n["sample_n"] == n["population_n"]:
            p.append(f"sample_design {design!r} but every row of the population was reviewed")
    if not _s(row.get("stratum")):
        p.append("stratum is required")
    if verdict and verdict != "correct" and not _s(row.get("reviewer_words")):
        p.append("a verdict other than 'correct' must carry the reviewer's own words")
    art = _s(row.get("artifact"))
    if not (art.startswith(ARTIFACT_DIR) and art.endswith(".json")):
        p.append(f"artifact must be a .json path under {ARTIFACT_DIR}")
    if SCOPE_STATEMENT not in _s(row.get("notes")):
        p.append(f"notes must state that the review {SCOPE_STATEMENT}")
    return p


def _by_run(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(_s(r.get("review_run_id")), []).append(r)
    return out


def batch_problems(rows: list[dict]) -> list[str]:
    """Rules a review run must satisfy as a whole: one reviewer, date, design, sample size and
    artifact; exactly sample_n rows; each stratum holding exactly its stratum_sampled_n rows with
    one population; the strata partitioning the sample and the population; no duplicates."""
    p = []
    for run, rs in _by_run(rows).items():
        for f in ("reviewer", "reviewed_at", "sample_design", "sample_n", "population_n", "artifact"):
            vals = {_s(r.get(f)) for r in rs}
            if len(vals) > 1:
                p.append(f"{run}: {f} differs across the run ({sorted(vals)[:3]})")
        oids = [_s(r.get("observation_id")) for r in rs]
        if len(set(oids)) != len(oids):
            p.append(f"{run}: an observation is reviewed twice in the run")
        sample_n, population_n = _int(rs[0].get("sample_n")), _int(rs[0].get("population_n"))
        if sample_n is not None and len(rs) != sample_n:
            p.append(f"{run}: {len(rs)} row(s) but sample_n says {sample_n}")
        strata: dict[str, list[dict]] = {}
        for r in rs:
            strata.setdefault(_s(r.get("stratum")), []).append(r)
        sampled_sum = population_sum = 0
        for name, srows in strata.items():
            sn = {_int(r.get("stratum_sampled_n")) for r in srows}
            sp = {_int(r.get("stratum_population_n")) for r in srows}
            if len(sn) > 1 or len(sp) > 1:
                p.append(f"{run}: stratum {name!r} states more than one size")
                continue
            sn_v, sp_v = sn.pop(), sp.pop()
            if sn_v is not None and len(srows) != sn_v:
                p.append(f"{run}: stratum {name!r} holds {len(srows)} row(s) but claims {sn_v} reviewed")
            sampled_sum += sn_v or 0
            population_sum += sp_v or 0
        if sample_n is not None and sampled_sum != sample_n:
            p.append(f"{run}: strata sum to {sampled_sum} reviewed, sample_n says {sample_n}")
        if population_n is not None and population_sum != population_n:
            p.append(f"{run}: strata sum to a population of {population_sum}, population_n says {population_n}")
    return p


def artifact_problems(rows: list[dict], root: Path) -> list[str]:
    """Each run must agree, row for row and in both directions, with the committed verdicts
    artifact it names -- so the table and the artifact cannot drift apart."""
    p = []
    for run, rs in _by_run(rows).items():
        rels = {_s(r.get("artifact")) for r in rs}
        if len(rels) != 1:
            continue                                      # reported by batch_problems
        rel = rels.pop()
        path = Path(root) / rel
        if not path.is_file():
            p.append(f"{run}: artifact {rel} does not exist")
            continue
        try:
            art = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            p.append(f"{run}: artifact {rel} does not parse ({e})")
            continue
        first = rs[0]
        expect = {"table": SHEET, "review_run_id": run, "reviewer": _s(first.get("reviewer")),
                  "review_date": _s(first.get("reviewed_at")), "review_source": "human",
                  "sample_design": _s(first.get("sample_design")),
                  "sampled_n": _s(first.get("sample_n")), "population_n": _s(first.get("population_n"))}
        for k, want in expect.items():
            if _s(art.get(k)) != want:
                p.append(f"{run}: artifact {k} is {art.get(k)!r}, the table says {want!r}")
        if SCOPE_STATEMENT not in _s(art.get("scope")):
            p.append(f"{run}: artifact scope does not state that the review {SCOPE_STATEMENT}")
        av = {_s(v.get("observation_id")): v for v in art.get("verdicts") or []}
        tv = {_s(r.get("observation_id")): r for r in rs}
        if set(av) - set(tv):
            p.append(f"{run}: in the artifact, not the table: {sorted(set(av) - set(tv))[:5]}")
        if set(tv) - set(av):
            p.append(f"{run}: in the table, not the artifact: {sorted(set(tv) - set(av))[:5]}")
        strata = {f"{_s(s.get('harness_id'))} / {_s(s.get('sub_stratum'))}": s
                  for s in art.get("strata") or []}
        for oid in sorted(set(av) & set(tv)):
            a, t = av[oid], tv[oid]
            key = f"{_s(a.get('harness_id'))} / {_s(a.get('sub_stratum'))}"
            pairs = [("role_at_review", a.get("role_at_review"), t.get("role_at_review")),
                     ("role_verdict", a.get("role_verdict"), t.get("role_verdict")),
                     ("reviewer_words", a.get("reviewer_words"), t.get("reviewer_words")),
                     ("notes", a.get("note"), t.get("notes")),
                     ("stratum", key, t.get("stratum"))]
            s = strata.get(key)
            if s is None:
                p.append(f"{run}: {oid} names stratum {key!r}, absent from the artifact's strata")
            else:
                pairs += [("stratum_sampled_n", s.get("sampled_n"), t.get("stratum_sampled_n")),
                          ("stratum_population_n", s.get("population_n"), t.get("stratum_population_n"))]
            for f, av_, tv_ in pairs:
                if _s(av_) != _s(tv_):
                    p.append(f"{run}: {oid} {f} disagrees with the artifact")
    return p


def role_drift(rows: list[dict], roles: dict[str, str]) -> list[str]:
    """Observations whose CURRENT evidence_role differs from the role that was reviewed.
    Informational: a later reclassification is legitimate history, not a broken review."""
    return [f"{_s(r['observation_id'])} reviewed as {_s(r['role_at_review'])}, now "
            f"{roles.get(_s(r['observation_id'])) or '(no live row)'}"
            for r in rows if roles.get(_s(r["observation_id"])) != _s(r["role_at_review"])]


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


def append_reviews(wb, reviews: list[dict], root: Path) -> dict:
    """Append role-review verdicts. ALL OR NOTHING, and a run is written only COMPLETE.

    Refused (ValueError, nothing written) if any row breaks the row rules, if an
    (observation_id, review_run_id) already in the table holds a different value in any column
    (a verdict is never overwritten), or if the table with the batch added would break the batch
    rules or disagree with the named artifact -- so a partial run cannot be written. An identical
    row already present is a no-op. Nothing is ever updated or deleted, and `Observations` is
    never written.
    """
    if SHEET not in wb.sheetnames:
        raise ValueError(f"{SHEET} missing -- run scripts/migrate_schema.py --apply")
    ws = wb[SHEET]
    present = rows_from_sheet(ws)
    existing = {(_s(r["observation_id"]), _s(r["review_run_id"])): r for r in present}
    ids = observation_ids(wb)
    problems, to_write, noop, seen = [], [], [], set()
    for rv in reviews:
        row = {c: rv.get(c) for c in COLUMNS}
        probs = problems_with(row, ids)
        key = (_s(row["observation_id"]), _s(row["review_run_id"]))
        if key in seen:
            probs.append("the same (observation_id, review_run_id) appears twice in the batch")
        seen.add(key)
        prior = existing.get(key)
        if prior is not None:
            if any(_s(prior[c]) != _s(row[c]) for c in COLUMNS):
                probs.append("already recorded in this run with different values; a verdict is never overwritten")
            elif not probs:
                noop.append(key[0])
                continue
        if probs:
            problems.append(f"{_s(row['observation_id'])}: {probs[0]}")
        else:
            to_write.append(row)
    if not problems:
        runs = {_s(r["review_run_id"]) for r in to_write}
        combined = [r for r in present if _s(r["review_run_id"]) in runs] + to_write
        problems += batch_problems(combined) + artifact_problems(combined, root)
    if problems:
        raise ValueError(f"{len(problems)} problem(s), nothing written: " + "; ".join(problems[:6]))
    for row in to_write:
        ws.append([row[c] for c in COLUMNS])
    return {"appended": len(to_write), "noop": noop}
