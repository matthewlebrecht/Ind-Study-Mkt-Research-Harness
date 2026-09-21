#!/usr/bin/env python3
"""
A person's correction of one row's evidence_role: what it changes, what it must leave alone, and
that the row's harness then HOLDS it rather than reverting it -- on a throwaway copy of the workbook.

The live case is O00303 (Matthew Lebrecht, 2026-09-15: "mark that as buyer did"), a business-journal
row H-FIRSTPARTY-01 writes as buyer_articulates. The harness is deliberately unchanged, so every
future run will keep proposing buyer_articulates; the correction survives only if the reconciler
treats the row as human-authored.

O00303 is ALSO recorded invalid (page furniture). Sections 1-6 test the human hold on a VALID corrected row, so the
copy's validity table is emptied first; section 7 restores the live fact and asserts item 19 (2026-09-15): a
re-proposal of a row recorded invalid is counted invalid and left exactly as recorded, not held as a conflict.

    python core/tests/test_role_correction.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.db import OBSERVATION_COLUMNS, MarketIntelDB, Observation, SchemaError  # noqa: E402

PASS = FAIL = 0
OID = "O00303"
NOTE = 'Reviewer\'s words: "mark that as buyer did".'


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def refused(fn):
    try:
        fn()
    except SchemaError:
        return True
    return False


def row_values(db, oid):
    ws = db.wb["Observations"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == oid:
            return {c: ws.cell(r, i + 1).value for i, c in enumerate(OBSERVATION_COLUMNS)}
    return None


def proposal_from(values, **over):
    """What the harness would propose for this claim: the row's content, machine provenance."""
    names = {f.name for f in fields(Observation)}
    d = {k: v for k, v in values.items() if k in names}
    d.update({"review_status": "unreviewed", "reviewer_notes": "", "review_source": "machine",
              "audit_verdict": "", "observation_id": ""})
    d.update(over)
    for k in ("publication_date", "retrieval_date", "evidence_excerpt", "reviewer_notes"):
        d[k] = "" if d.get(k) is None else str(d[k])
    return Observation(**d)


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "test_copy.xlsx"
    shutil.copy(ROOT / "data" / "market_intel_db.xlsx", tmp)
    db = MarketIntelDB(tmp)
    from core import validity as V
    if V.SHEET in db.wb.sheetnames:           # sections 1-6: a valid corrected row (see the docstring)
        del db.wb[V.SHEET]
    db.wb.create_sheet(V.SHEET).append(V.COLUMNS)
    before = row_values(db, OID)
    if before is None:
        # O00303 was deleted on Matthew's `unsupported` verdict (2026-09-15). The writers under test do not
        # depend on the live row: rebuild it on the copy from the deletion record's snapshot.
        import json
        rec = json.loads((ROOT / "harness_output/audits/DELETIONS_2026-09-15_firstparty_page_furniture.json")
                         .read_text(encoding="utf-8"))
        snap = next(s for s in rec["snapshots"] if s["observation_id"] == OID)
        db.wb["Observations"].append([snap.get(c) for c in OBSERVATION_COLUMNS])
        before = row_values(db, OID)
    if before["evidence_role"] != "buyer_articulates":
        # The live workbook already carries the correction; rebuild the pre-correction row on the copy.
        ws = db.wb["Observations"]
        r = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == OID)
        for col, val in (("evidence_role", "buyer_articulates"), ("review_source", "machine"),
                         ("review_status", "unreviewed"), ("reviewer_notes", None)):
            ws.cell(r, OBSERVATION_COLUMNS.index(col) + 1).value = val
        before = row_values(db, OID)

    print("1. refusals")
    check("an unknown role is refused", refused(lambda: db.apply_role_correction(OID, "buyer_said", "R", NOTE)))
    check("the row's current role is refused -- a correction must change something",
          refused(lambda: db.apply_role_correction(OID, "buyer_articulates", "R", NOTE)))
    check("a correction without a reason is refused", refused(lambda: db.apply_role_correction(OID, "buyer_acts", "R", "")))
    check("a correction without a reviewer is refused", refused(lambda: db.apply_role_correction(OID, "buyer_acts", "", NOTE)))
    check("an unknown observation is refused", refused(lambda: db.apply_role_correction("O99999", "buyer_acts", "R", NOTE)))
    check("refusals changed nothing", row_values(db, OID) == before)

    print("2. what the correction changes, and what it leaves alone")
    res = db.apply_role_correction(OID, "buyer_acts", "Matthew Lebrecht", NOTE)
    after = row_values(db, OID)
    check("evidence_role is buyer_acts", after["evidence_role"] == "buyer_acts" and res["from"] == "buyer_articulates")
    check("review_source is human and review_status corrected -- the row is now human-authored",
          after["review_source"] == "human" and after["review_status"] == "corrected")
    check("audit_verdict is untouched -- no extraction verdict is invented",
          after["audit_verdict"] == before["audit_verdict"])
    check("publication_state is untouched", after["publication_state"] == before["publication_state"])
    untouched = [c for c in OBSERVATION_COLUMNS
                 if c not in ("evidence_role", "review_source", "review_status", "reviewer_notes")]
    check("every other field is unchanged (text, family, excerpt, grade, strength, confidence...)",
          all(after[c] == before[c] for c in untouched))
    check("reviewer_notes carries a dated stamp, the reviewer, the old and new role, and the reason",
          "role correction by Matthew Lebrecht" in after["reviewer_notes"] and
          "buyer_articulates -> buyer_acts" in after["reviewer_notes"] and "mark that as buyer did" in after["reviewer_notes"])
    check("the stamp says extraction was not re-assessed", "not re-assessed" in after["reviewer_notes"])

    print("3. the next run of the unchanged harness")
    rep = db.sync_observations([proposal_from(before, evidence_role="buyer_articulates", review_status="unreviewed")])
    check("re-proposing buyer_articulates is HELD as a conflict, not written",
          [c["observation_id"] for c in rep.conflicts] == [OID] and not rep.updated)
    check("the correction survives the run", row_values(db, OID)["evidence_role"] == "buyer_acts")
    rep = db.sync_observations([proposal_from(before, evidence_role="buyer_articulates")])
    check("and it is held again on every later run -- a permanent conflict", len(rep.conflicts) == 1)

    print("4. the control: the same role edit WITHOUT human provenance is silently reverted")
    ws = db.wb["Observations"]
    other = next(r for r in range(2, ws.max_row + 1)
                 if ws.cell(r, OBSERVATION_COLUMNS.index("harness_id") + 1).value == "H-FIRSTPARTY-01"
                 and ws.cell(r, OBSERVATION_COLUMNS.index("review_source") + 1).value == "machine"
                 and ws.cell(r, OBSERVATION_COLUMNS.index("review_status") + 1).value == "unreviewed"
                 and ws.cell(r, OBSERVATION_COLUMNS.index("evidence_role") + 1).value == "buyer_articulates")
    other_id = ws.cell(other, 1).value
    orig = row_values(db, other_id)
    ws.cell(other, OBSERVATION_COLUMNS.index("evidence_role") + 1).value = "buyer_acts"
    rep = db.sync_observations([proposal_from(orig)])
    check(f"a bare edit to {other_id} is overwritten back to buyer_articulates by the next run",
          row_values(db, other_id)["evidence_role"] == "buyer_articulates" and not rep.conflicts)

    print("5. a run that stops proposing the claim")
    held = db.unreproduced_observations("H-FIRSTPARTY-01", [])
    check("the corrected row is held -- a machine run can never invalidate it", OID in held["held"] and OID not in held["eligible"])

    print("6. the text correction")
    cur = row_values(db, OID)
    new = cur["observation_text"] + " (corrected)"
    check("a text correction against text the row no longer holds is refused",
          refused(lambda: db.apply_text_correction(OID, "not the text", new, "R", "why")))
    check("identical text is refused", refused(lambda: db.apply_text_correction(OID, cur["observation_text"], cur["observation_text"], "R", "why")))
    check("no reviewer or no reason is refused",
          refused(lambda: db.apply_text_correction(OID, cur["observation_text"], new, "", "why")) and
          refused(lambda: db.apply_text_correction(OID, cur["observation_text"], new, "R", "")))
    db.apply_text_correction(OID, cur["observation_text"], new, "Matthew Lebrecht", '"Yes correct the text"')
    aft = row_values(db, OID)
    check("only observation_text and reviewer_notes changed",
          aft["observation_text"] == new and
          all(aft[c] == cur[c] for c in OBSERVATION_COLUMNS if c not in ("observation_text", "reviewer_notes")))
    check("family, excerpt, role and audit_verdict are untouched",
          (aft["evidence_family"], aft["evidence_excerpt"], aft["evidence_role"], aft["audit_verdict"]) ==
          (cur["evidence_family"], cur["evidence_excerpt"], cur["evidence_role"], cur["audit_verdict"]))
    check("the stamp keeps the previous text and says extraction was not re-assessed",
          cur["observation_text"] in aft["reviewer_notes"] and "not re-assessed" in aft["reviewer_notes"])
    rep = db.sync_observations([proposal_from(before, evidence_role="buyer_articulates")])
    check("the harness's template text is held, not rewritten over the correction",
          len(rep.conflicts) == 1 and row_values(db, OID)["observation_text"] == new)

    print("7. the same row recorded invalid (the live state): counted invalid, left as recorded (item 19)")
    V.append_determinations(db.wb, [{"observation_id": OID, "validity_status": "invalidated_extraction_defect",
                                     "as_of_date": "2026-09-15", "determined_at": "2026-09-15",
                                     "determined_by": "test fixture", "basis": "test fixture", "notes": ""}])
    recorded = row_values(db, OID)
    rep = db.sync_observations([proposal_from(before, evidence_role="buyer_articulates")])
    check("the re-proposal is counted invalid, not held as a conflict and not written",
          [i["observation_id"] for i in rep.invalid] == [OID] and not rep.conflicts and not rep.updated)
    check("the row is exactly as recorded -- correction, text and all", row_values(db, OID) == recorded)

    print(f"\n{PASS} passed, {FAIL} failed (worked on {tmp})")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
