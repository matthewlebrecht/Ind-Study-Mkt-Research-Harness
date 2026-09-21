"""
SEC reporting status: the vocabulary, its definitions, and the DERIVED readers.

Harness Advisor design, final (session 17 wrap-up brief, 2026-09-13). Session 17 found that
the 8-K Item 1.05 obligation follows Exchange Act reporting status as of a date, not "public
or private": of 12 buyers that appear as SEC filers, three were periodic reporters, four had
only filed Form D exemption notices, two had withdrawn registration statements, one files only
as an insider, one went private, and one filer could not be confirmed to be the company at all.
A `Companies.public_private` column would have misplaced most of them and could not have held
a change of status. So:

  * `Company_SEC_Reporting_Status_History` is a dedicated append-only table (sheet columns in
    COLUMNS; writer core/db.py::append_sec_status; integrity validate_repo_db check 12).
  * There is no `Companies.public_private` column, now or later. Anything that needs "is this
    company currently a reporter" DERIVES it here: the latest non-superseded row per company
    with `sec_reporting_status = active_reporter`. Same discipline as `reprocessing_required`:
    derived, never authored.

THE TWO DOUBTS ARE DIFFERENT THINGS
-----------------------------------
`entity_unresolved` is IDENTITY doubt. A filer entity was found, but it cannot be confirmed to
be this company, so the row asserts no status for the company at all; `source_reference` names
the candidate filer and `notes` must say why identity is unresolved. Seed case: "Lynden USA
Inc." (CIK 0001737580), a co-registrant on an oil-and-gas filer's S-3s, against Lynden, Inc.,
a Seattle logistics company.

`status_uncertain` is STATUS doubt. The company's filer entity IS confirmed -- the
`source_reference` must carry its CIK -- but its filings do not settle which status applies
(a registration with no withdrawal and no periodic reports, a Form 15 followed by further
periodic filings with no later record). `notes` must say what is unsettled.

The writer enforces the difference: an `entity_unresolved` row without an identity note, or a
`status_uncertain` row without a CIK, is refused. And neither is ever read as "not a reporter":
`identity_confirmed()` is False only for `entity_unresolved`.

`never_registered` is written only after someone has actually checked a company -- never
defaulted from absence in one search pass -- so it too requires `notes` saying what was checked.
"""

from __future__ import annotations

import re

# The design's table name is `Company_SEC_Reporting_Status_History`. The workbook TAB is `SEC_Reporting_Status_History` because Excel
# refuses sheet names longer than 31 characters (the design name is 36) and "repairs" the file
# by truncating it on open; every other tab in the workbook already respects the limit.
TABLE_NAME = "Company_SEC_Reporting_Status_History"
SHEET = "SEC_Reporting_Status_History"
COLUMNS = ["id", "company_id", "sec_reporting_status", "source_filing_type", "source_reference",
           "as_of_date", "determined_at", "determined_by", "superseded_by", "notes"]

ACTIVE_REPORTER = "active_reporter"
ENTITY_UNRESOLVED = "entity_unresolved"
STATUS_UNCERTAIN = "status_uncertain"
NEVER_REGISTERED = "never_registered"

DEFINITIONS = {
    "active_reporter": "Files periodic Exchange Act reports (10-K / 10-Q) as of the as_of_date.",
    "form_d_only": "Appears in EDGAR only through Regulation D exemption notices (Form D / D/A); never a reporter.",
    "withdrawn_registration": "Filed a registration statement and withdrew it (Form RW); never became a reporter.",
    "never_registered": "Checked and found to have no SEC registrant history. Written only after an actual check.",
    "insider_only": "Appears in EDGAR only as an insider or holder in another issuer (Forms 3/4/5, Schedule 13D/G).",
    "deregistered": "Was a reporter and terminated or suspended registration (Form 15 / 25); no current obligation.",
    ENTITY_UNRESOLVED: "IDENTITY doubt: a filer was found but cannot be confirmed to be this company; no status is asserted.",
    STATUS_UNCERTAIN: "STATUS doubt: the company's filer is confirmed (CIK), but its filings do not settle which status applies.",
}
STATUSES = tuple(DEFINITIONS)

_CIK = re.compile(r"\bCIK\s*0*\d{1,10}\b", re.I)
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def problems_with(d: dict, known_companies: set[str] | None = None) -> list[str]:
    """Why a proposed determination may not be written; empty if it may."""
    out = []
    status = str(d.get("sec_reporting_status") or "")
    if status not in STATUSES:
        out.append(f"sec_reporting_status {status!r} is not one of {list(STATUSES)}")
    if known_companies is not None and str(d.get("company_id")) not in known_companies:
        out.append(f"unknown company_id {d.get('company_id')!r}")
    if not _ISO.match(str(d.get("as_of_date") or "")):
        out.append("as_of_date must be the ISO date the evidence establishes (YYYY-MM-DD), not a load date")
    for f in ("source_reference", "determined_by"):
        if not str(d.get(f) or "").strip():
            out.append(f"{f} is required")
    notes = str(d.get("notes") or "").strip()
    ref = str(d.get("source_reference") or "")
    if status == ENTITY_UNRESOLVED and not notes:
        out.append("entity_unresolved is identity doubt: notes must say which candidate filer and why "
                   "it cannot be confirmed to be this company")
    if status == STATUS_UNCERTAIN:
        if not _CIK.search(ref):
            out.append("status_uncertain is status doubt about a CONFIRMED filer: source_reference must "
                       "carry its CIK (if the filer itself is in doubt, the status is entity_unresolved)")
        if not notes:
            out.append("status_uncertain: notes must say what the filings leave unsettled")
    if status == NEVER_REGISTERED and not notes:
        out.append("never_registered: notes must say what was checked (never defaulted from absence)")
    if status not in (NEVER_REGISTERED,) and status in STATUSES and not str(d.get("source_filing_type") or "").strip():
        out.append("source_filing_type is required for a status resting on a filing")
    return out


def rows_from_sheet(ws) -> list[dict]:
    headers = [ws.cell(1, c).value for c in range(1, len(COLUMNS) + 1)]
    if headers != COLUMNS:
        raise ValueError(f"{SHEET} header drift: {headers}")
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            out.append({c: (r[i] if i < len(r) else None) for i, c in enumerate(COLUMNS)})
    return out


def current_rows(rows: list[dict]) -> dict[str, dict]:
    """The latest non-superseded row per company_id (the design's single current row)."""
    out: dict[str, dict] = {}
    for r in rows:
        if r.get("superseded_by"):
            continue
        cid = str(r["company_id"])
        prev = out.get(cid)
        if prev is None or (str(r.get("as_of_date") or ""), str(r["id"])) > (str(prev.get("as_of_date") or ""), str(prev["id"])):
            out[cid] = r
    return out


def current_status(rows: list[dict], company_id: str) -> str | None:
    row = current_rows(rows).get(str(company_id))
    return row["sec_reporting_status"] if row else None


def active_reporters(rows: list[dict]) -> list[str]:
    """company_ids whose current status is active_reporter. The only way "currently public"
    is answered anywhere in the repo."""
    return sorted(cid for cid, r in current_rows(rows).items()
                  if r["sec_reporting_status"] == ACTIVE_REPORTER)


def identity_confirmed(status: str | None) -> bool | None:
    """None if no determination; False only for identity doubt."""
    if status is None:
        return None
    return status != ENTITY_UNRESOLVED
