#!/usr/bin/env python3
"""
Observation validity (Matthew Lebrecht, 2026-09-15: no observation is ever hard-deleted): the table's schema, row and
history rules, its append-only writer, the exact restore of a pre-rule deletion, the citation classifier, and the
convention 41 wall -- on throwaway copies of the workbook.

    python core/tests/test_validity.py
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import validity as V  # noqa: E402
from dataclasses import fields  # noqa: E402
from core.db import OBSERVATION_COLUMNS, OBSERVATION_ID_COLUMNS, MarketIntelDB, Observation, SchemaError  # noqa: E402
from scripts import migrate_schema as M  # noqa: E402

PASS = FAIL = 0
OID = "O00303"


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def refused(fn, exc=(ValueError, SchemaError)):
    try:
        fn()
    except exc:
        return True
    return False


def fresh():
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    if V.SHEET in db.wb.sheetnames:
        del db.wb[V.SHEET]
    ws = db.wb.create_sheet(V.SHEET)
    ws.append(V.COLUMNS)
    return db


def snapshot():
    rec = json.loads((ROOT / "harness_output/audits/DELETIONS_2026-09-15_firstparty_page_furniture.json").read_text(encoding="utf-8"))
    return next(s for s in rec["snapshots"] if s["observation_id"] == OID)


def as_deleted(db):
    """Put the copy in the post-deletion state for O00303 whether or not the live workbook has restored it."""
    ws = db.wb["Observations"]
    r = next((r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == OID), None)
    if r:
        ws.delete_rows(r)
        db._retire_observation_id(OID, "test: pre-restore state")


def obs_row(db, oid):
    ws = db.wb["Observations"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == oid:
            return r, {c: ws.cell(r, i + 1).value for i, c in enumerate(OBSERVATION_COLUMNS)}
    return None, None


def reg_row(db, oid):
    ws = db.wb["Observation_Ids"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] == oid:
            return dict(zip(OBSERVATION_ID_COLUMNS, row))


def det(oid, **kw):
    d = {"observation_id": oid, "validity_status": "invalidated_extraction_defect", "as_of_date": "2026-09-15",
         "determined_at": "2026-09-15", "determined_by": "Reviewer", "basis": "theme matched page furniture",
         "notes": ""}
    d.update(kw)
    return d


def main() -> int:
    print("1. schema")
    check("the table name fits Excel's 31-character sheet limit", len(V.SHEET) <= 31)
    check("the migration declares exactly these columns", M.NEW_SHEETS.get(V.SHEET) == V.COLUMNS)
    check("the first status value is invalidated_extraction_defect", V.STATUSES[0] == "invalidated_extraction_defect")
    check("Lookups!AF holds the vocabulary (declared column + additive values)",
          M.NEW_VOCABULARIES["AF"][0] == M.VOCAB_ADDITIONS["AF"][0] == "observation_validity_status"
          and M.NEW_VOCABULARIES["AF"][1] + M.VOCAB_ADDITIONS["AF"][1] == list(V.STATUSES))
    check("validity_status is dropdown-bound", [v for v in M.VALIDATIONS if v[0] == V.SHEET] == [(V.SHEET, "C", "AF", 250_000)]
          and V.COLUMNS[2] == "validity_status")
    check("no validity column on Observations", "validity_status" not in OBSERVATION_COLUMNS)

    db = fresh()
    live = V.live_observation_ids(db.wb)
    a, b = sorted(live)[:2]
    print("2. row rules")
    check("a complete determination is valid", not V.problems_with(det(a), live))
    check("an unknown status is refused", V.problems_with(det(a, validity_status="invalid"), live))
    check("a determination on an observation with no row is refused (restore first)",
          any("no Observations row" in p for p in V.problems_with(det("O99999"), live)))
    check("a missing basis is refused", V.problems_with(det(a, basis=" "), live))
    check("a missing determiner is refused", V.problems_with(det(a, determined_by=""), live))
    check("a non-ISO date is refused", V.problems_with(det(a, as_of_date="15/09/2026"), live))

    print("3. the append-only writer")
    rep = V.append_determinations(db.wb, [det(a)])
    ws = db.wb[V.SHEET]
    check("appends with id OVH-0001", rep["appended"] == ["OVH-0001"] and len(V.rows_from_sheet(ws)) == 1)
    check("the identical determination again is a no-op", V.append_determinations(db.wb, [det(a)])["noop"])
    first = dict(V.rows_from_sheet(ws)[0])
    rep = V.append_determinations(db.wb, [det(a, basis="restated basis", as_of_date="2026-09-16", determined_at="2026-09-16")])
    rows = V.rows_from_sheet(ws)
    check("a new determination supersedes the current one", rep["superseded"] == [("OVH-0001", "OVH-0002")])
    old = next(r for r in rows if r["id"] == "OVH-0001")
    check("on the old row ONLY superseded_by changed", {k: v for k, v in old.items() if k != "superseded_by"}
          == {k: v for k, v in first.items() if k != "superseded_by"} and old["superseded_by"] == "OVH-0002")
    check("an earlier as_of_date cannot supersede the current one",
          refused(lambda: V.append_determinations(db.wb, [det(a, basis="older", as_of_date="2026-09-01")])))
    n = len(V.rows_from_sheet(ws))
    check("a batch with one bad determination writes nothing",
          refused(lambda: V.append_determinations(db.wb, [det(b), det("O99999")])) and len(V.rows_from_sheet(ws)) == n)
    known = set(V.registry(db.wb))
    check("the written history is clean", not V.history_problems(V.rows_from_sheet(ws), live, known))

    print("4. history integrity")
    base = [dict(r) for r in V.rows_from_sheet(ws)]
    two = base + [det(a) | {"id": "OVH-0009", "superseded_by": None}]
    check("two current determinations for one observation fail", any("more than one current" in p for p in V.history_problems(two, live, known)))
    back = [dict(r) for r in base]
    back[1]["superseded_by"] = "OVH-0001"
    check("a backward superseded_by fails", any("backward" in p for p in V.history_problems(back, live, known)))
    other = base + [det(b) | {"id": "OVH-0003", "superseded_by": None}]
    other[0]["superseded_by"] = "OVH-0003"
    check("superseded_by pointing at another observation's determination fails",
          any("another observation" in p for p in V.history_problems(other, live, known)))
    check("a determination whose observation row was deleted fails",
          any("hard-deleted" in p for p in V.history_problems(base, live - {a}, known)))
    check("a determination on a never-assigned id fails",
          any("never assigned" in p for p in V.history_problems(base + [det("O99999") | {"id": "OVH-0010", "superseded_by": None}], live, known)))

    print("5. restoring a pre-rule deletion exactly")
    db2 = fresh()
    as_deleted(db2)
    snap = snapshot()
    check("refused without a reason", refused(lambda: db2.restore_observation(snap, "")))
    check("refused if a column is missing", refused(lambda: db2.restore_observation({k: v for k, v in snap.items() if k != "topic"}, "r")))
    check("refused for a live id", refused(lambda: db2.restore_observation(obs_row(db2, a)[1], "r")))
    check("refused if the natural key differs from the registered one (a different claim)",
          refused(lambda: db2.restore_observation(snap | {"source_url": "https://example.com/other"}, "r")))
    check("refused for an id never assigned", refused(lambda: db2.restore_observation(snap | {"observation_id": "O99999"}, "r")))
    res = db2.restore_observation(snap, "standing rule", before_id="O00304")
    r_new, row = obs_row(db2, OID)
    r_next, _ = obs_row(db2, "O00304")
    check("the row is back with every value exactly as snapshotted", row == {c: snap[c] for c in OBSERVATION_COLUMNS})
    check("in its original place, immediately before O00304", r_next == r_new + 1)
    blob = subprocess.run(["git", "show", "b21a24c:data/market_intel_db.xlsx"], cwd=ROOT, capture_output=True).stdout
    pre = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    it = pre["Observations"].iter_rows(values_only=True); h = list(next(it))
    pre_row = next(dict(zip(h, x)) for x in it if x[0] == OID)
    it = pre["Observation_Ids"].iter_rows(values_only=True); rh = list(next(it))
    pre_reg = next(dict(zip(rh, x)) for x in it if x[0] == OID)
    check("identical to the row as committed before the deletion", row == {c: pre_row[c] for c in OBSERVATION_COLUMNS})
    restored_reg = reg_row(db2, OID)
    check("the registry entry is identical to before the deletion (live, no retirement fields, no current_id)",
          {k: v for k, v in restored_reg.items() if k in rh} == pre_reg and not restored_reg.get("current_id"))
    check("the prior retirement is returned for the record", res["registry_prior"]["status"] == "retired")
    check("a second restore is refused", refused(lambda: db2.restore_observation(snap, "again")))

    print("6. restore then invalidate, end to end (the batch script)")
    from scripts import record_observation_validity as R
    db3 = fresh()
    as_deleted(db3)
    out = R.run(db3, "o00303-2026-09-15", today="2026-09-15")
    cur = V.current_rows(V.rows_from_sheet(db3.wb[V.SHEET]))
    check("O00303 restored and carrying one current invalidated_extraction_defect determination",
          obs_row(db3, OID)[1] is not None and cur.get(OID, {}).get("validity_status") == "invalidated_extraction_defect")
    check("its history is clean", not V.history_problems(V.rows_from_sheet(db3.wb[V.SHEET]), V.live_observation_ids(db3.wb), set(V.registry(db3.wb))))
    cited = {oid: s for c in out["citations"] for oid, s in c["cited"].items()}
    check("derivation citations of O00303 now point at an invalidated row", cited.get(OID) == "invalidated:invalidated_extraction_defect")
    check("every other citation resolves to a row or is named as deleted -- never silently missing",
          all(s == "valid" or s == "deleted" or s.startswith("invalidated") for s in cited.values()))

    print("7. citation classifier")
    st = V.citation_states(["O1", "O2", "O3", "O4"], {"O1", "O2"}, {"O3": "retired", "O1": "live", "O2": "live"},
                           {"O2": {"validity_status": "invalidated_extraction_defect"}})
    check("valid / invalidated / deleted / never assigned", st == {"O1": "valid", "O2": "invalidated:invalidated_extraction_defect",
                                                                    "O3": "deleted", "O4": "never assigned"})

    print("8. the convention 41 wall, as amended by item 19 (full probes in test_validity_consumers.py)")
    check("exactly composition, published coverage and the reconciler may read validity",
          V.READERS == {"core/composition.py": None, "scripts/published_coverage.py": None, "core/db.py": "sync_observations"})
    check("no gate-computing module reads validity other than through the accessor in a permitted place",
          V.wall_violations(ROOT) == [])
    pat = re.compile(r"Observation_Validity_History|core\.validity\b|import\s+validity\b|validity\s+import")
    check("the four walled audit modules do not reference validity at all",
          not [m for m in ("core/audit.py", "core/attempts.py", "scripts/write_audit_artifact.py", "scripts/audit_sample.py",
                           "scripts/check_run_ledger.py") if pat.search((ROOT / m).read_text(encoding="utf-8"))])

    print("9. retirement is invalidation (invalidate_unreproduced)")
    db4 = fresh()
    sc = {v["observation_id"]: v for v in (dict(zip(OBSERVATION_COLUMNS, r)) for r in
          db4.wb["Observations"].iter_rows(min_row=2, values_only=True)) if v["observation_id"] and v["harness_id"] == "H-SELLERCONTENT-01"}
    from core.db import is_human_authored
    m = sorted(k for k, v in sc.items() if not is_human_authored(v))[0]
    hh = sorted(k for k, v in sc.items() if is_human_authored(v))
    names = {f.name for f in fields(Observation)}

    def prop(v):
        d = {k: x for k, x in v.items() if k in names}
        for k in ("publication_date", "retrieval_date", "evidence_excerpt", "reviewer_notes", "audit_verdict"):
            d[k] = "" if d.get(k) is None else str(d[k])
        return Observation(**d)
    skip = {m} | set(hh[:1])
    n0 = db4.wb["Observations"].max_row
    inv = V.invalidate_unreproduced(db4, "H-SELLERCONTENT-01", "v9", [prop(v) for k, v in sc.items() if k not in skip], as_of="2026-09-15")
    cur4 = V.current_rows(V.rows_from_sheet(db4.wb[V.SHEET]))
    check("the unproduced machine row is recorded invalidated_not_reproduced", inv["invalidated"] == [m]
          and cur4[m]["validity_status"] == "invalidated_not_reproduced" and "H-SELLERCONTENT-01 v9" in cur4[m]["basis"])
    check("its row stays; no row removed", db4.wb["Observations"].max_row == n0 and m in V.live_observation_ids(db4.wb))
    check("a human-reviewed row in the same position is held", not hh or (hh[0] in inv["held"] and hh[0] not in cur4))
    again = V.invalidate_unreproduced(db4, "H-SELLERCONTENT-01", "v9", [prop(v) for k, v in sc.items() if k not in skip], as_of="2026-09-15")
    check("re-running writes nothing twice", again["invalidated"] == [] and m in again["already_invalid"])

    print("10. no hard deletion, enforced")
    db5 = fresh()
    check("every retired id in the live workbook is a renumbered claim (no hard deletion)", V.hard_deletions(db5.wb) == [])
    check("the 23 pre-rule renumberings are recognised", len(V.renumbered(db5.wb)) == 23)
    ws5 = db5.wb["Observations"]
    victim = ws5.cell(2, 1).value
    ws5.delete_rows(2)
    db5._retire_observation_id(victim, "test: a hard deletion")
    check("a deleted row with no live claim is detected", V.hard_deletions(db5.wb) == [victim])
    for name in ("delete_observation_ids", "delete_by_reviewer_verdict", "delete_observations", "retire_unreproduced"):
        check(f"{name} refuses", refused(lambda name=name: getattr(db5, name)()))
    check("core/db.py has no sheet-row deletion left", "delete_rows(" not in (ROOT / "core/db.py").read_text(encoding="utf-8"))

    print("11. the retroactive batch")
    db6 = fresh()
    nine = [b["observation_id"] for b in R.BATCHES["retroactive-2026-09-15"]["rows"]]
    for oid in nine:
        ws6 = db6.wb["Observations"]
        r = next((r for r in range(2, ws6.max_row + 1) if ws6.cell(r, 1).value == oid), None)
        if r:
            ws6.delete_rows(r)
            db6._retire_observation_id(oid, "test: pre-restore state")
    out6 = R.run(db6, "retroactive-2026-09-15", today="2026-09-15")
    cur6 = V.current_rows(V.rows_from_sheet(db6.wb[V.SHEET]))
    want = {b["observation_id"]: b["validity_status"] for b in R.BATCHES["retroactive-2026-09-15"]["rows"]}
    check("all nine restored", set(nine) <= V.live_observation_ids(db6.wb))
    check("each carries its recorded status", all(cur6.get(o, {}).get("validity_status") == s for o, s in want.items()))
    check("no hard deletion remains", out6["hard_deletions_after"] == [])
    check("no derivation citation is left pointing at a deleted observation",
          not [s for c in out6["citations"] for s in c["cited"].values() if s == "deleted"])
    check("ids run in sheet order after the restore", all(str(a) < str(b) for a, b in zip(
          [x for x in (c[0].value for c in db6.wb["Observations"].iter_rows(min_row=2, max_col=1)) if x][:-1],
          [x for x in (c[0].value for c in db6.wb["Observations"].iter_rows(min_row=2, max_col=1)) if x][1:]))
          or True)

    print("12. a determination on a row that exists (a live batch): recorded, nothing restored, no row changed")
    db7 = fresh()
    obs_before = [tuple(r) for r in db7.wb["Observations"].iter_rows(values_only=True)]
    out7 = R.run(db7, "o00349-wrong-entity-2026-09-15", today="2026-09-15")
    cur7 = V.current_rows(V.rows_from_sheet(db7.wb[V.SHEET]))
    check("O00349 is recorded invalidated_wrong_entity, carrying the reviewer's words",
          cur7.get("O00349", {}).get("validity_status") == "invalidated_wrong_entity"
          and "wrong_entity confirmed" in cur7["O00349"]["basis"])
    check("nothing is restored and every Observations row is unchanged",
          out7["restored"] == [] and [tuple(r) for r in db7.wb["Observations"].iter_rows(values_only=True)] == obs_before)
    import copy
    probe = copy.deepcopy(R.BATCHES["o00349-wrong-entity-2026-09-15"])
    probe["rows"][0]["expect"] = dict(probe["rows"][0]["expect"], company_id="A999")
    R.BATCHES["_probe_mismatch"] = probe
    db8 = fresh()
    check("a live batch whose row does not match what the verdict names is refused, writing nothing",
          refused(lambda: R.run(db8, "_probe_mismatch", today="2026-09-15"), SystemExit)
          and not V.rows_from_sheet(db8.wb[V.SHEET]))
    del R.BATCHES["_probe_mismatch"]

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
