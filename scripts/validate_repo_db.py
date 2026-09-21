#!/usr/bin/env python3
"""
Assert that the repo and the database agree. P2 enforcement.

`repo_structure_spec.md` §1 P2: `harness_id` and `harness_version` appear in both the code
and the workbook, and until now nothing detected when they disagreed. The stale workbook
found on 2026-08-26 -- pilot IDs shifted by one, HR-0001 naming the wrong harness -- was
exactly this class of failure, and it went unnoticed for four days because nothing could
notice it.

Checks (spec §5, plus two added after that failure):

  1. Every harness_version in Harness_Runs exists in some manifest.
  2. Every harness_id in Observations has a manifest.
  3. Every manifest.sources entry resolves in Source_Families.
  4. Every declared_evidence_families value is in Lookups.
  5. Every signal_types value is in the Signal_Types registry.
  6. No sheet has rows beyond its validation binding.
  7. Every expected data validation actually exists.          [added]
  8. Referential integrity across the sheets' foreign keys.   [added]
  9. Every published harness version has an audit artifact.   [added 2026-08-31]

Check 7 exists because the workbook's 9 dropdown validations silently disappeared between
2026-08-22 and 2026-08-24 and nobody noticed. Check 6 catches vocabularies lapsing past
their binding; check 7 catches them never being bound at all.

Check 9 is the audit gate (docs/gates/gate_new_harness_output.md). It is numbered 9, not
7: an earlier draft of the spec called it "the seventh mechanical check" from a count that
predated checks 7 and 8. Nothing here is renumbered or replaced.

Run in CI on every commit and as the first step of any harness run.

    python scripts/validate_repo_db.py
    python scripts/validate_repo_db.py --quiet     # exit code only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "market_intel_db.xlsx"
HARNESS_DIR = ROOT / "harnesses"

sys.path.insert(0, str(ROOT))
from scripts.migrate_schema import VALIDATIONS, LOOKUPS_CEILING  # noqa: E402
from core import audit, topics  # noqa: E402


class Report:
    def __init__(self):
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def ok(self, msg):
        self.passes.append(msg)

    def fail(self, msg):
        self.failures.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def load_manifests() -> dict[str, dict]:
    out = {}
    for path in sorted(HARNESS_DIR.glob("*/manifest.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["_path"] = path.relative_to(ROOT)
        out[data["harness_id"]] = data
    return out


def col_values(ws, col_letter: str, ceiling: int) -> set[str]:
    idx = openpyxl.utils.column_index_from_string(col_letter)
    return {str(ws.cell(r, idx).value).strip()
            for r in range(2, min(ws.max_row, ceiling) + 1)
            if ws.cell(r, idx).value not in (None, "")}


def sheet_column(ws, name: str) -> int | None:
    for c in range(1, ws.max_column + 1):
        if ws.cell(1, c).value == name:
            return c
    return None


def distinct(ws, name: str) -> set[str]:
    c = sheet_column(ws, name)
    if c is None:
        return set()
    return {str(ws.cell(r, c).value).strip()
            for r in range(2, ws.max_row + 1)
            if ws.cell(r, c).value not in (None, "")}


def validate(db_path: Path) -> Report:
    rep = Report()
    wb = openpyxl.load_workbook(db_path)
    manifests = load_manifests()

    if not manifests:
        rep.fail("no harness manifests found under harnesses/*/manifest.yaml")
        return rep
    rep.ok(f"{len(manifests)} manifest(s): {', '.join(sorted(manifests))}")

    # ---- 1. every harness_version in Harness_Runs exists in some manifest ----
    hr = wb["Harness_Runs"]
    hid_c, ver_c = sheet_column(hr, "harness_id"), sheet_column(hr, "version")
    seen_runs = 0
    for r in range(2, hr.max_row + 1):
        hid = hr.cell(r, hid_c).value
        ver = str(hr.cell(r, ver_c).value or "").strip()
        if not hid:
            continue
        seen_runs += 1
        m = manifests.get(hid)
        if m is None:
            rep.fail(f"Harness_Runs row {r}: harness_id {hid!r} has no manifest")
            continue
        known = {str(v["version"]).strip() for v in m.get("versions", [])}
        if ver not in known:
            rep.fail(f"Harness_Runs row {r}: {hid} version {ver!r} is not in "
                     f"{m['_path']} (knows {sorted(known)})")
    rep.ok(f"check 1: {seen_runs} run row(s) resolve to a manifest version")

    # ---- 2. every harness_id in Observations has a manifest ----
    obs = wb["Observations"]
    obs_harnesses = distinct(obs, "harness_id")
    for hid in sorted(obs_harnesses):
        if hid not in manifests:
            rep.fail(f"Observations cite harness_id {hid!r} with no manifest")
    rep.ok(f"check 2: {len(obs_harnesses)} harness_id(s) in Observations all have manifests")

    # ---- 3. manifest sources resolve in Source_Families ----
    sf = wb["Source_Families"]
    source_ids = distinct(sf, "source_id")
    for hid, m in manifests.items():
        for s in m.get("sources", []):
            sid = s["id"] if isinstance(s, dict) else s
            if sid not in source_ids:
                rep.fail(f"{m['_path']}: source {sid!r} does not resolve in Source_Families")
    rep.ok(f"check 3: all manifest sources resolve ({len(source_ids)} source_ids known)")

    # ---- 4. declared_evidence_families are in Lookups ----
    lk = wb["Lookups"]
    families = col_values(lk, "G", LOOKUPS_CEILING)
    for hid, m in manifests.items():
        for fam in m.get("declared_evidence_families", []):
            if fam not in families:
                rep.fail(f"{m['_path']}: evidence_family {fam!r} is not in Lookups")
    rep.ok("check 4: all declared evidence families are in the Lookups vocabulary")

    # ---- 5. signal_types are registered ----
    st = wb["Signal_Types"]
    registered = distinct(st, "signal_type_name")
    for hid, m in manifests.items():
        for sig in m.get("signal_types", []):
            if sig not in registered:
                rep.fail(f"{m['_path']}: signal_type {sig!r} is not in the Signal_Types "
                         "registry")
    # signal_class / evidence_family consistency (spec §11 C10)
    cls_c = sheet_column(st, "signal_class")
    fam_c = sheet_column(st, "evidence_family")
    for r in range(2, st.max_row + 1):
        nm = st.cell(r, sheet_column(st, "signal_type_name")).value
        if not nm:
            continue
        cls = str(st.cell(r, cls_c).value or "").strip()
        fam = st.cell(r, fam_c).value
        if cls == "evidence" and not fam:
            rep.fail(f"Signal_Types {nm!r}: signal_class='evidence' requires an "
                     "evidence_family")
        if cls == "prerequisite" and fam:
            rep.fail(f"Signal_Types {nm!r}: signal_class='prerequisite' must have a null "
                     "evidence_family")
        if cls not in ("evidence", "prerequisite"):
            rep.fail(f"Signal_Types {nm!r}: signal_class {cls!r} must be 'evidence' or "
                     "'prerequisite'")
    # instrument_class (taxonomy patch rev 2 §4.6) must be populated, and is a DIFFERENT
    # axis from signal_class -- §4.6.3 exists because rev 1 of the patch collapsed them.
    # A blank is not a neutral default: downstream it reads as "this instrument has no
    # bias", which is true of nothing in this project. IC1 absence licenses no inference
    # at all, and a blank would let an IC1 silence be quoted as a finding.
    ic_c = sheet_column(st, "instrument_class")
    if ic_c is None:
        rep.fail("Signal_Types has no instrument_class column; run "
                 "scripts/migrate_schema.py --apply")
    else:
        blank = []
        for r in range(2, st.max_row + 1):
            nm = st.cell(r, sheet_column(st, "signal_type_name")).value
            if not nm:
                continue
            ic = str(st.cell(r, ic_c).value or "").strip()
            if not ic:
                blank.append(str(nm))
            elif ic not in ("IC1", "IC2", "IC3", "IC4"):
                rep.fail(f"Signal_Types {nm!r}: instrument_class {ic!r} must be IC1-IC4")
        if blank:
            rep.fail(f"Signal_Types with no instrument_class: {', '.join(blank)} — a "
                     "blank class reads downstream as 'unbiased' and would let an IC1 "
                     "silence be quoted as a finding")
    rep.ok(f"check 5: {len(registered)} signal type(s) registered and internally consistent")

    # ---- 6. no sheet has rows beyond its validation binding ----
    bindings: dict[str, int] = {}
    for sheet, col, src, ceiling in VALIDATIONS:
        bindings[sheet] = min(bindings.get(sheet, ceiling), ceiling)
    for sheet, ceiling in bindings.items():
        rows = wb[sheet].max_row
        if rows > ceiling:
            rep.fail(f"{sheet} has {rows} rows but validation binds only to {ceiling:,} — "
                     f"rows past that accept anything silently")
    rep.ok(f"check 6: no sheet exceeds its validation binding "
           f"({', '.join(f'{s} {wb[s].max_row}/{c:,}' for s, c in sorted(bindings.items()))})")

    # ---- 7. every expected validation exists ----
    missing, wrong = [], []
    for sheet, col, src, ceiling in VALIDATIONS:
        want_sqref = f"{col}2:{col}{ceiling}"
        want_f1 = f"Lookups!${src}$2:${src}${LOOKUPS_CEILING}"
        found = None
        for dv in wb[sheet].data_validations.dataValidation:
            if str(dv.sqref) == want_sqref:
                found = dv
                break
        if found is None:
            missing.append(f"{sheet}!{col}")
        elif found.formula1 != want_f1:
            wrong.append(f"{sheet}!{col} -> {found.formula1} (expected {want_f1})")
    if missing:
        rep.fail(f"data validations MISSING on {', '.join(missing)} — controlled "
                 "vocabularies are not being enforced. Run scripts/migrate_schema.py --apply")
    if wrong:
        rep.fail("data validations point at the wrong range: " + "; ".join(wrong))
    if not missing and not wrong:
        rep.ok(f"check 7: all {len(VALIDATIONS)} expected data validations present and correct")

    # ---- 8. referential integrity ----
    companies = distinct(wb["Companies"], "company_id")
    run_ids = distinct(hr, "harness_run_id")

    bad = distinct(obs, "company_id") - companies
    if bad:
        rep.fail(f"Observations reference unknown company_id(s): {sorted(bad)[:5]}")

    att = wb["Attempts"]
    if att.max_row > 1:
        bad = distinct(att, "company_id") - companies
        if bad:
            rep.fail(f"Attempts reference unknown company_id(s): {sorted(bad)[:5]}")
        bad = distinct(att, "run_id") - run_ids
        if bad:
            rep.fail(f"Attempts reference unknown run_id(s): {sorted(bad)[:5]}")

    ce = wb["Company_Executives"]
    if ce.max_row > 1:
        bad = distinct(ce, "company_id") - companies
        if bad:
            rep.fail(f"Company_Executives reference unknown company_id(s): {sorted(bad)[:5]}")

    hs = wb["Harness_Sources"]
    if hs.max_row > 1:
        bad = distinct(hs, "source_id") - source_ids
        if bad:
            rep.fail(f"Harness_Sources reference unknown source_id(s): {sorted(bad)[:5]}")

    # A theme key retired in core/topics.py must not survive on any row: a row keyed to a
    # string the spine no longer knows is orphaned from every theme-level rollup, and
    # gap_report.py would silently count it as an unmapped buyer topic.
    retired = distinct(obs, "topic") & set(topics.RETIRED_THEME_KEYS)
    if retired:
        rep.fail(f"Observations carry retired theme key(s) {sorted(retired)} -- run "
                 "scripts/migrate_schema.py --apply (rename_topic_keys)")

    dup = len(distinct(wb["Companies"], "company_id"))
    total = sum(1 for r in range(2, wb["Companies"].max_row + 1)
                if wb["Companies"].cell(r, 1).value)
    if dup != total:
        rep.fail(f"Companies has duplicate company_id values ({total} rows, {dup} distinct)")

    # Say what the company count is made of. "120 companies" on its own reads as growth
    # of a universe that has been fixed at 108 since Week 1 (2026-09-02 brief, item 1).
    cws = wb["Companies"]
    c_hdr = [cws.cell(1, c).value for c in range(1, cws.max_column + 1)]
    i_qs = c_hdr.index("qualification_status") + 1
    n_prov = sum(1 for r in range(2, cws.max_row + 1)
                 if cws.cell(r, 1).value and cws.cell(r, i_qs).value == "provider_benchmark")
    rep.ok(f"check 8: referential integrity holds across {len(companies)} companies "
           f"({len(companies) - n_prov} buyers + {n_prov} provider benchmarks), "
           f"{obs.max_row - 1} observations, {max(att.max_row - 1, 0)} attempts")

    # ---- 9. audit gate: a published harness version has an audit artifact ----
    #
    # Scoped to what actually publishes, not to what wrote rows. A run whose
    # publication_status is `quarantined` contributes neither numerator nor denominator to
    # any coverage figure, so it has nothing to audit yet -- quarantine IS the pre-audit
    # state. A run resolving entirely to absent_confirmed is emphatically in scope: it
    # publishes a coverage number without writing an observation, and a harness that
    # confidently reports nothing everywhere is a harness that may simply be broken
    # (convention 6a).
    hr_headers = [hr.cell(1, c).value for c in range(1, hr.max_column + 1)]
    if "publication_status" not in hr_headers:
        rep.fail("Harness_Runs has no publication_status column — the audit gate cannot "
                 "be enforced. Run scripts/migrate_schema.py --apply")
    else:
        i_hid = hr_headers.index("harness_id")
        i_ver = hr_headers.index("version")
        i_pub = hr_headers.index("publication_status")
        i_run = hr_headers.index("harness_run_id")
        i_date = hr_headers.index("date_run") if "date_run" in hr_headers else None

        # Observations per (harness_id, harness_version), so a `superseded` claim can be
        # checked against the sheet instead of believed.
        obs_by_version: dict[tuple, int] = {}
        _oh = [obs.cell(1, c).value for c in range(1, obs.max_column + 1)]
        if "harness_id" in _oh and "harness_version" in _oh:
            _oi, _ovi = _oh.index("harness_id") + 1, _oh.index("harness_version") + 1
            for r in range(2, obs.max_row + 1):
                if obs.cell(r, 1).value is None:
                    continue
                k = (str(obs.cell(r, _oi).value or "").strip(),
                     str(obs.cell(r, _ovi).value or "").strip())
                obs_by_version[k] = obs_by_version.get(k, 0) + 1

        published: dict[tuple, list] = {}
        run_dates: dict[tuple, list] = {}
        quarantined = set()
        superseded: dict[tuple, list] = {}
        for r in range(2, hr.max_row + 1):
            if hr.cell(r, 1).value is None:
                continue
            pair = (str(hr.cell(r, i_hid + 1).value or "").strip(),
                    str(hr.cell(r, i_ver + 1).value or "").strip())
            status = str(hr.cell(r, i_pub + 1).value or "").strip().lower()
            run_id = str(hr.cell(r, i_run + 1).value or "").strip()
            run_date = ""
            if i_date is not None:
                _d = hr.cell(r, i_date + 1).value
                run_date = (_d.isoformat()[:10] if hasattr(_d, "isoformat")
                            else str(_d or "").strip()[:10])
            if status == "published":
                published.setdefault(pair, []).append(run_id)
                run_dates.setdefault(pair, []).append((run_id, run_date))
            elif status == "quarantined":
                quarantined.add(pair)
            elif status == "superseded":
                superseded.setdefault(pair, []).append(run_id)
            else:
                rep.fail(f"Harness_Runs {run_id}: publication_status is "
                         f"{status or '(blank)'!r}, expected 'published', 'quarantined' "
                         f"or 'superseded'")

        grandfathered = audit.load_grandfathered()
        artifacts = audit.load_artifacts()

        # A GRANDFATHERED VERSION IS NOT A CLOSED SET. The exemption records a hand audit of the
        # output that existed on its date_added; a later run can write new rows under the same
        # version label, and those rows would inherit an exemption nobody granted them. So the
        # exemption is honoured only for versions whose published runs all predate it: a
        # grandfathered version with a run dated AFTER date_added is audited like any other.
        # Measured 2026-09-17: exactly one version has ever done this -- H-FMCSA-01 v1.3, which
        # gained 4 rows from HR-0034 on 2026-09-01, the day after its exemption. It was caught
        # by hand at the time and has an artifact, so this rule fails nothing today; it removes
        # the reliance on catching the next one by hand.
        added_on = audit.grandfathered_added_on()
        post_exemption = {}
        for pair in sorted(grandfathered):
            since = added_on.get(pair, "")
            later = [f"{rid} ({d})" for rid, d in run_dates.get(pair, []) if since and d and d > since]
            if later:
                post_exemption[pair] = later

        missing, malformed, failing = [], [], []
        for pair, run_ids in sorted(published.items()):
            if pair in grandfathered and pair not in post_exemption:
                continue
            art = artifacts.get(pair)
            if art is None:
                why = ("" if pair not in post_exemption else
                       f" — GRANDFATHERED, but run(s) {', '.join(post_exemption[pair])} wrote to "
                       f"it after its exemption on {added_on.get(pair)}, so those rows were never "
                       f"audited by anyone")
                missing.append(f"{pair[0]} {pair[1]} (runs {', '.join(run_ids)}) — "
                               f"expected {audit.audit_path(*pair).name}{why}")
                continue
            problems = audit.validate_artifact(art)
            if problems:
                malformed.append(f"{pair[0]} {pair[1]}: {'; '.join(problems[:3])}")
            elif art.get("verdict") == "fail":
                failing.append(f"{pair[0]} {pair[1]}: audit verdict is 'fail' "
                               f"({'; '.join(art.get('stop_rule_triggered') or [])})")

        # `superseded` asserts that nothing of a version is live, so there is nothing to
        # audit. That is a checkable claim and it is checked here rather than taken on
        # trust: a disposition that merely silences the gate would BE the way around a
        # failing audit that the gate text rules out. A superseded version still holding
        # observations has live output nobody judged, and fails.
        live_superseded = []
        for pair, run_ids in sorted(superseded.items()):
            n = obs_by_version.get(pair, 0)
            if n:
                live_superseded.append(
                    f"{pair[0]} {pair[1]} (runs {', '.join(run_ids)}) still holds {n} "
                    f"observation(s) — a superseded version must hold none, or its "
                    f"output is live and unaudited")
            if pair in published:
                live_superseded.append(
                    f"{pair[0]} {pair[1]} is marked superseded on {', '.join(run_ids)} "
                    f"but published on another run — a version is one or the other")
        if live_superseded:
            rep.fail("version(s) marked superseded with live output: "
                     + " | ".join(live_superseded))

        if missing:
            rep.fail("published harness version(s) with NO audit artifact — a coverage "
                     "number is being reported for output nobody has audited: "
                     + " | ".join(missing))
        if malformed:
            rep.fail("audit artifact(s) missing required fields: " + " | ".join(malformed))
        if failing:
            rep.fail("harness version(s) published despite a FAILING audit — the stop "
                     "rule quarantines these: " + " | ".join(failing))

        # Orphan artifacts are a warning, not a failure: auditing a version that has not
        # published yet is exactly the intended order of operations.
        # A version audited and published, then superseded by a later version, keeps its artifact as the record of
        # that audit: not an orphan (2026-09-15, H-BREACHPORTAL-01 v1.1).
        orphans = [f"{h} {v}" for (h, v) in artifacts
                   if (h, v) not in published and (h, v) not in quarantined and (h, v) not in superseded]
        if orphans:
            rep.warn(f"audit artifact(s) with no matching Harness_Runs row: "
                     f"{', '.join(sorted(orphans))}")

        # reprocessing_required is derived on read, never stored, so it cannot go stale.
        for harness_id in sorted({h for h, _ in artifacts}):
            verdict = audit.derive_reprocessing_required(harness_id, artifacts)
            if verdict:
                rep.warn(f"reprocessing_required for {harness_id}: {verdict['reason']}; "
                         f"blast radius {verdict['blast_radius']}")

        if not (missing or malformed or failing or live_superseded):
            gf = len([p for p in published if p in grandfathered and p not in post_exemption])
            tail = (f", {len(superseded)} superseded" if superseded else "")
            rep.ok(f"check 9: {len(published)} published harness version(s) — "
                   f"{len(published) - gf} audited, {gf} grandfathered, "
                   f"{len(quarantined)} quarantined run(s) not yet publishing" + tail
                   + (f"; {len(post_exemption)} grandfathered version(s) audited anyway "
                      f"(rows written after the exemption): "
                      f"{', '.join(f'{h} {v}' for h, v in sorted(post_exemption))}"
                      if post_exemption else ""))

    # ---- 10. the observation-id registry agrees with the live sheet (convention 43) ----
    if "Observation_Ids" not in wb.sheetnames:
        rep.fail("Observation_Ids sheet missing — run scripts/migrate_schema.py --apply")
    else:
        from core.db import natural_key_of
        reg = wb["Observation_Ids"]
        rh = [reg.cell(1, c).value for c in range(1, reg.max_column + 1)]
        registry = {}
        dup_ids = []
        for r in range(2, reg.max_row + 1):
            rec = {h: reg.cell(r, i + 1).value for i, h in enumerate(rh) if h}
            oid = str(rec.get("observation_id") or "").strip()
            if not oid:
                continue
            if oid in registry:
                dup_ids.append(oid)
            registry[oid] = rec
        obs_ws = wb["Observations"]
        oh = [obs_ws.cell(1, c).value for c in range(1, obs_ws.max_column + 1)]
        live = {}
        for r in range(2, obs_ws.max_row + 1):
            row = {h: obs_ws.cell(r, i + 1).value for i, h in enumerate(oh) if h}
            oid = str(row.get("observation_id") or "").strip()
            if oid:
                live[oid] = natural_key_of(row)
        unregistered = sorted(o for o in live if o not in registry)
        key_drift = sorted(o for o in live if o in registry
                           and str(registry[o].get("natural_key") or "") != live[o])
        stale_live = sorted(o for o, rec in registry.items()
                            if str(rec.get("status")) == "live" and o not in live)
        live_keys = {}
        for o, k in live.items():
            live_keys.setdefault(k, []).append(o)
        forks = {k: v for k, v in live_keys.items() if len(v) > 1}
        if dup_ids:
            rep.fail(f"Observation_Ids holds duplicate id(s): {dup_ids[:5]}")
        if unregistered:
            rep.fail(f"{len(unregistered)} live observation id(s) not in the registry: "
                     f"{unregistered[:5]} — run scripts/migrate_schema.py --apply")
        if key_drift:
            rep.fail(f"{len(key_drift)} id(s) whose natural key differs from the registry "
                     f"(an id was reassigned to a different claim): {key_drift[:5]}")
        if stale_live:
            rep.fail(f"{len(stale_live)} registry id(s) marked live with no Observations "
                     f"row (a delete path bypassed the registry): {stale_live[:5]}")
        if forks:
            rep.fail(f"{len(forks)} natural key(s) carry two live ids: "
                     f"{list(forks.values())[:3]}")
        if not (dup_ids or unregistered or key_drift or stale_live or forks):
            retired = sum(1 for rec in registry.values() if str(rec.get("status")) == "retired")
            rep.ok(f"check 10: observation-id registry agrees with the live sheet "
                   f"({len(live)} live, {retired} retired, {len(registry)} ids ever assigned)")

    # COHERENCE-WALL-CHECK-BEGIN  (this block reads the tag table only to VALIDATE it,
    # never to compute a gate value; the scan below exempts exactly this fenced region and
    # still fails on any reference elsewhere in this file, check 9 included)
    # ---- 11. the coherence framework's walls (build handoff 2026-09-08) ----
    #
    # THE CONVENTION 41 WALL, §2 of the handoff. Tagging is a research overlay on the
    # evidence base and must never feed the gate: no code path that computes
    # review_status, audit_verdict, publication_state or reprocessing_required may read
    # Observation_Coherence_Tags, directly or by join. Asserted as a source scan over the
    # modules that compute those, because that is the level at which the rule is
    # checkable at all -- and asserted as a FAILURE, not a warning, per the handoff.
    coh_sheets = ("Coherence_Framework_Taxonomy", "Observation_Coherence_Tags",
                  "Coherence_Pilot_Runs", "Coherence_Family_Dimensions")
    if not all(s in wb.sheetnames for s in coh_sheets):
        rep.fail("coherence framework sheet(s) missing: "
                 + ", ".join(s for s in coh_sheets if s not in wb.sheetnames)
                 + " -- run scripts/migrate_schema.py --apply")
    else:
        GATE_MODULES = ["core/db.py", "core/audit.py", "core/attempts.py",
                        "core/composition.py", "scripts/write_audit_artifact.py",
                        "scripts/validate_repo_db.py", "scripts/published_coverage.py",
                        "scripts/audit_sample.py", "scripts/check_run_ledger.py"]
        _self = (ROOT / "scripts/validate_repo_db.py").read_text(encoding="utf-8").splitlines()
        _begin = next((i for i, l in enumerate(_self, 1)
                       if "COHERENCE-WALL-CHECK-BEGIN" in l and "in l" not in l), 0)
        _end = next((i for i, l in enumerate(_self, 1)
                     if "COHERENCE-WALL-CHECK-END" in l and "in l" not in l), 0)

        def in_fence(lineno):
            return bool(_begin) and bool(_end) and _begin <= lineno <= _end

        leaks = []
        for mod in GATE_MODULES:
            path = ROOT / mod
            if not path.exists():
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "Observation_Coherence_Tags" not in line:
                    continue
                if mod == "scripts/validate_repo_db.py" and in_fence(i):
                    continue
                leaks.append(f"{mod}:{i}")
        if leaks:
            rep.fail("CONVENTION 41 WALL BREACHED: gate-computing module(s) reference "
                     "Observation_Coherence_Tags -- " + ", ".join(leaks) + ". Tagging must "
                     "not feed review_status / audit_verdict / publication_state / "
                     "reprocessing_required. Escalate, do not work around.")

        # The tag table carries DIMENSIONS only: never a failure family (derived
        # downstream at synthesis) and never a generative force (reference-only).
        tax = {}
        tw = wb["Coherence_Framework_Taxonomy"]
        th = [tw.cell(1, c).value for c in range(1, tw.max_column + 1)]
        for r in range(2, tw.max_row + 1):
            row = {h: tw.cell(r, i + 1).value for i, h in enumerate(th) if h}
            if row.get("id"):
                tax[str(row["id"]).strip()] = str(row.get("entity_type") or "")
        tg = wb["Observation_Coherence_Tags"]
        gh = [tg.cell(1, c).value for c in range(1, tg.max_column + 1)]
        obs_ids = {str(wb["Observations"].cell(r, 1).value)
                   for r in range(2, wb["Observations"].max_row + 1)
                   if wb["Observations"].cell(r, 1).value}
        bad_kind, unknown, orphan = [], [], []
        for r in range(2, tg.max_row + 1):
            row = {h: tg.cell(r, i + 1).value for i, h in enumerate(gh) if h}
            oid = str(row.get("observation_id") or "").strip()
            if not oid:
                continue
            if oid not in obs_ids:
                orphan.append(oid)
            for cand in str(row.get("coherence_dimension_candidate") or "").split(";"):
                cand = cand.strip()
                if not cand:
                    continue
                if cand not in tax:
                    unknown.append(cand)
                elif tax[cand] != "dimension":
                    bad_kind.append(f"{cand} ({tax[cand]})")
        if orphan:
            rep.fail(f"Observation_Coherence_Tags rows reference unknown observation_id(s): "
                     f"{sorted(set(orphan))[:5]}")
        if unknown:
            rep.fail(f"Observation_Coherence_Tags cites id(s) absent from "
                     f"Coherence_Framework_Taxonomy: {sorted(set(unknown))[:5]}")
        if bad_kind:
            rep.fail(f"Observation_Coherence_Tags may cite DIMENSIONS only (handoff §2); "
                     f"found {sorted(set(bad_kind))[:5]}")
        # The family-to-dimension mapping (addendum 2026-09-08): both ends must resolve in
        # the taxonomy, to the right entity_type and the same framework_version, and the
        # (family, dimension, version) triple is the primary key.
        fd = wb["Coherence_Family_Dimensions"]
        fh = [fd.cell(1, c).value for c in range(1, fd.max_column + 1)]
        ver = {}
        for r in range(2, tw.max_row + 1):
            row = {h: tw.cell(r, i + 1).value for i, h in enumerate(th) if h}
            if row.get("id"):
                ver[str(row["id"]).strip()] = str(row.get("framework_version") or "")
        fd_bad, fd_seen, fd_dupes = [], set(), []
        for r in range(2, fd.max_row + 1):
            row = {h: fd.cell(r, i + 1).value for i, h in enumerate(fh) if h}
            fam, dim = str(row.get("family_id") or "").strip(), str(row.get("dimension_id") or "").strip()
            fv = str(row.get("framework_version") or "").strip()
            if not fam:
                continue
            for rid, want in ((fam, "failure_family"), (dim, "dimension")):
                if rid not in tax:
                    fd_bad.append(f"{fam}/{dim}: {rid} absent from the taxonomy")
                elif tax[rid] != want:
                    fd_bad.append(f"{fam}/{dim}: {rid} is {tax[rid]!r}, must be {want!r}")
                elif ver.get(rid) != fv:
                    fd_bad.append(f"{fam}/{dim}: {rid} is {ver.get(rid)!r}, mapping says {fv!r}")
            key = (fam, dim, fv)
            if key in fd_seen:
                fd_dupes.append(key)
            fd_seen.add(key)
        if fd_bad:
            rep.fail(f"Coherence_Family_Dimensions: {len(fd_bad)} bad reference(s) — "
                     f"{fd_bad[:4]}")
        if fd_dupes:
            rep.fail(f"Coherence_Family_Dimensions: duplicate (family, dimension, version) "
                     f"triple(s): {fd_dupes[:4]}")

        if not (leaks or orphan or unknown or bad_kind or fd_bad or fd_dupes):
            n_tax = len(tax)
            kinds = {}
            for v in tax.values():
                kinds[v] = kinds.get(v, 0) + 1
            n_tags = sum(1 for r in range(2, tg.max_row + 1) if tg.cell(r, 1).value)
            n_pilot = sum(1 for r in range(2, wb["Coherence_Pilot_Runs"].max_row + 1)
                          if wb["Coherence_Pilot_Runs"].cell(r, 1).value)
            rep.ok(f"check 11: coherence framework walls hold — {n_tax} taxonomy row(s) "
                   f"{kinds or '(unseeded)'}, {len(fd_seen)} family-dimension mapping(s), "
                   f"{n_tags} tag(s), {n_pilot} pilot row(s); no gate module reads the tag "
                   f"table")
    # COHERENCE-WALL-CHECK-END

    # ---- 12. SEC reporting status history (Harness Advisor design, session 17 wrap-up) ----
    # Append-only integrity, forward-only supersession, one current row per company, and the
    # standing rule that no sheet ever carries a public/private column: "is this company
    # currently a reporter" is derived from this table (core/sec_status.py), never stored.
    from core import sec_status as _sec
    pp = [name for name in wb.sheetnames
          if "public_private" in [str(wb[name].cell(1, c).value or "").strip().lower()
                                  for c in range(1, wb[name].max_column + 1)]]
    if pp:
        rep.fail(f"a public_private column exists on {pp} -- reporting status is derived from "
                 f"{_sec.SHEET}, never stored as a column (session 17 design)")
    if _sec.SHEET not in wb.sheetnames:
        rep.fail(f"{_sec.SHEET} missing -- run scripts/migrate_schema.py --apply")
    else:
        try:
            srows = _sec.rows_from_sheet(wb[_sec.SHEET])
        except ValueError as e:
            srows = None
            rep.fail(str(e))
        if srows is not None:
            by_id = {str(r["id"]): r for r in srows}
            bad = []
            if len(by_id) != len(srows):
                bad.append("duplicate id")
            for r in srows:
                probs = _sec.problems_with(r, companies)
                if probs:
                    bad.append(f"{r['id']}: {probs[0]}")
                sup = str(r.get("superseded_by") or "")
                if sup:
                    nxt = by_id.get(sup)
                    if nxt is None:
                        bad.append(f"{r['id']}: superseded_by {sup} does not exist")
                    elif str(nxt["company_id"]) != str(r["company_id"]):
                        bad.append(f"{r['id']}: superseded by another company's row {sup}")
                    elif str(nxt["as_of_date"]) < str(r["as_of_date"]) or sup == str(r["id"]):
                        bad.append(f"{r['id']}: superseded_by points backward ({sup})")
            current = {}
            for r in srows:
                if not r.get("superseded_by"):
                    current.setdefault(str(r["company_id"]), []).append(r["id"])
            multi = {k: v for k, v in current.items() if len(v) > 1}
            if multi:
                bad.append(f"more than one current (non-superseded) row for {sorted(multi)[:4]}")
            if bad:
                rep.fail(f"{_sec.SHEET}: " + "; ".join(bad[:6]))
            else:
                counts = {}
                for r in _sec.current_rows(srows).values():
                    counts[r["sec_reporting_status"]] = counts.get(r["sec_reporting_status"], 0) + 1
                rep.ok(f"check 12: SEC reporting status history holds -- {len(srows)} row(s), "
                       f"{len(current)} company current status(es) {counts or '(unseeded)'}; "
                       f"no public_private column anywhere")

    # DIRECTIONALITY-WALL-CHECK-BEGIN  (reads the tag table only to VALIDATE it; the scan below
    # exempts exactly this fenced region and still fails on any reference elsewhere in this file)
    # ---- 13. evidence directionality (build handoff 2026-09-15) ----
    #
    # THE CONVENTION 41 WALL, as for coherence tagging: no code path that computes review_status,
    # audit_verdict, publication_state or reprocessing_required may read the directionality tag
    # table, directly or by join, or import its module. A source scan, asserted as a FAILURE.
    import re
    from core import directionality as _dir
    if _dir.SHEET not in wb.sheetnames:
        rep.fail(f"{_dir.SHEET} missing -- run scripts/migrate_schema.py --apply")
    else:
        DIR_GATE_MODULES = ["core/db.py", "core/audit.py", "core/attempts.py",
                            "core/composition.py", "scripts/write_audit_artifact.py",
                            "scripts/validate_repo_db.py", "scripts/published_coverage.py",
                            "scripts/audit_sample.py", "scripts/check_run_ledger.py"]
        _src = (ROOT / "scripts/validate_repo_db.py").read_text(encoding="utf-8").splitlines()
        _db = next((i for i, l in enumerate(_src, 1)
                    if "DIRECTIONALITY-WALL-CHECK-BEGIN" in l and "in l" not in l), 0)
        _de = next((i for i, l in enumerate(_src, 1)
                    if "DIRECTIONALITY-WALL-CHECK-END" in l and "in l" not in l), 0)
        _pat = re.compile(r"Observation_Directionality_Tags|core\.directionality|import\s+directionality"
                          r"|directionality\s+import")
        dir_leaks = []
        for mod in DIR_GATE_MODULES:
            path = ROOT / mod
            if not path.exists():
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not _pat.search(line):
                    continue
                if mod == "scripts/validate_repo_db.py" and _db and _de and _db <= i <= _de:
                    continue
                dir_leaks.append(f"{mod}:{i}")
        if dir_leaks:
            rep.fail("CONVENTION 41 WALL BREACHED: gate-computing module(s) reference the "
                     "directionality tag table or module -- " + ", ".join(dir_leaks) + ". Tagging "
                     "must not feed review_status / audit_verdict / publication_state / "
                     "reprocessing_required. Escalate, do not work around.")
        try:
            drows = _dir.rows_from_sheet(wb[_dir.SHEET])
        except ValueError as e:
            drows = None
            rep.fail(str(e))
        if drows is not None:
            ids = _dir.observation_ids(wb)
            dbad, dkeys, ddupes = [], set(), []
            for r in drows:
                probs = _dir.problems_with(r, ids)
                if probs:
                    dbad.append(f"{r['observation_id']}: {probs[0]}")
                key = (str(r["observation_id"]), str(r["tagging_run_id"]))
                if key in dkeys:
                    ddupes.append(key)
                dkeys.add(key)
            if dbad:
                rep.fail(f"{_dir.SHEET}: {len(dbad)} bad row(s) -- {dbad[:4]}")
            if ddupes:
                rep.fail(f"{_dir.SHEET}: duplicate (observation_id, tagging_run_id) pair(s): {ddupes[:4]}")
            if not (dir_leaks or dbad or ddupes):
                by_value, by_run = {}, {}
                for r in drows:
                    by_value[r["evidence_directionality"]] = by_value.get(r["evidence_directionality"], 0) + 1
                    by_run[r["tagging_run_id"]] = by_run.get(r["tagging_run_id"], 0) + 1
                rep.ok(f"check 13: evidence directionality wall holds -- {len(drows)} tag(s) "
                       f"{by_value or '(none yet)'} across {len(by_run)} tagging run(s); no gate "
                       f"module reads the tag table")
    # DIRECTIONALITY-WALL-CHECK-END

    # ROLE-REVIEW-WALL-CHECK-BEGIN  (reads the role-review table only to VALIDATE it; the scan below
    # exempts exactly this fenced region and still fails on any reference elsewhere in this file)
    # ---- 14. role-classification reviews (Matthew Lebrecht, 2026-09-15; convention 44) ----
    #
    # A role verdict must not claim more than it is. Each of these is a FAILURE:
    #   (a) THE CONVENTION 41 WALL: a gate-computing module names the table or imports its module,
    #       which would let a role verdict feed review_status / audit_verdict / publication_state /
    #       reprocessing_required;
    #   (b) a row that is not scoped role_only, does not state that it re-clears neither identity
    #       nor extraction, is not human-sourced, repeats the reviewed role as its verdict, gives a
    #       non-'correct' verdict without the reviewer's words, or lacks a coherent numeric sample
    #       basis;
    #   (c) a run whose rows do not number exactly its sample_n, a stratum holding a different number
    #       of rows than it claims reviewed, or strata that do not partition the sample and the
    #       population -- so no row can claim coverage that was not reviewed;
    #   (d) a run that disagrees, row for row or in either direction, with the committed verdicts
    #       artifact it names.
    # A reviewed observation whose evidence_role has changed since is a WARNING: that is history.
    import re
    from core import role_review as _rr
    if _rr.SHEET not in wb.sheetnames:
        rep.fail(f"{_rr.SHEET} missing -- run scripts/migrate_schema.py --apply")
    else:
        RR_GATE_MODULES = ["core/db.py", "core/audit.py", "core/attempts.py",
                           "core/composition.py", "scripts/write_audit_artifact.py",
                           "scripts/validate_repo_db.py", "scripts/published_coverage.py",
                           "scripts/audit_sample.py", "scripts/check_run_ledger.py"]
        _rsrc = (ROOT / "scripts/validate_repo_db.py").read_text(encoding="utf-8").splitlines()
        _rb = next((i for i, l in enumerate(_rsrc, 1)
                    if "ROLE-REVIEW-WALL-CHECK-BEGIN" in l and "in l" not in l), 0)
        _re_end = next((i for i, l in enumerate(_rsrc, 1)
                        if "ROLE-REVIEW-WALL-CHECK-END" in l and "in l" not in l), 0)
        _rpat = re.compile(r"Observation_Role_Reviews|core\.role_review\b|import\s+role_review\b"
                           r"|role_review\s+import")
        rr_leaks = []
        for mod in RR_GATE_MODULES:
            path = ROOT / mod
            if not path.exists():
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not _rpat.search(line):
                    continue
                if mod == "scripts/validate_repo_db.py" and _rb and _re_end and _rb <= i <= _re_end:
                    continue
                rr_leaks.append(f"{mod}:{i}")
        if rr_leaks:
            rep.fail("CONVENTION 41 WALL BREACHED: gate-computing module(s) reference the role-review "
                     "table or module -- " + ", ".join(rr_leaks) + ". A role verdict must not feed "
                     "review_status / audit_verdict / publication_state / reprocessing_required. "
                     "Escalate, do not work around.")
        try:
            rrows = _rr.rows_from_sheet(wb[_rr.SHEET])
        except ValueError as e:
            rrows = None
            rep.fail(str(e))
        if rrows is not None:
            rids = _rr.observation_ids(wb)
            rbad = []
            for r in rrows:
                probs = _rr.problems_with(r, rids)
                if probs:
                    rbad.append(f"{r['observation_id']}: {probs[0]}")
            rbatch = _rr.batch_problems(rrows)
            rart = _rr.artifact_problems(rrows, ROOT)
            for label, items in (("bad row(s)", rbad), ("run problem(s)", rbatch),
                                 ("disagreement(s) with the verdicts artifact", rart)):
                if items:
                    rep.fail(f"{_rr.SHEET}: {len(items)} {label} -- {items[:4]}")
            drift = _rr.role_drift(rrows, _rr.current_roles(wb))
            if drift:
                rep.warn(f"{_rr.SHEET}: {len(drift)} reviewed observation(s) whose evidence_role has "
                         f"changed since review -- {drift[:4]}")
            if not (rr_leaks or rbad or rbatch or rart):
                by_verdict, runs = {}, set()
                for r in rrows:
                    by_verdict[r["role_verdict"]] = by_verdict.get(r["role_verdict"], 0) + 1
                    runs.add(r["review_run_id"])
                rep.ok(f"check 14: role reviews hold -- {len(rrows)} verdict(s) "
                       f"{by_verdict or '(none yet)'} across {len(runs)} run(s), each role-only, "
                       f"reconciled to its sample and its artifact; no gate module reads the table")
    # ROLE-REVIEW-WALL-CHECK-END

    # VALIDITY-WALL-CHECK-BEGIN  (reads the validity table only to VALIDATE it; the scan below exempts exactly
    # this fenced region and still fails on any reference elsewhere in this file)
    # ---- 15. observation validity history (Matthew Lebrecht, 2026-09-15: no observation is hard-deleted) ----
    #
    # FAILURES: (a) the convention 41 wall -- a gate-computing module names the validity table or imports its
    # module; (b) a malformed determination; (c) broken history -- a superseded_by that is missing, backward or
    # about another observation, or more than one current determination for an observation; (d) a determination
    # on an observation whose row is gone (an invalid observation must persist); (e) a Company_State_History row
    # citing an id that was never assigned.
    # WARNINGS: derivation rows citing DELETED observations (retired ids, the pre-rule hard deletions) or
    # INVALIDATED ones -- named so they are seen, not failures, because derivations are immutable history.
    import re
    from core import validity as _val
    if _val.SHEET not in wb.sheetnames:
        rep.fail(f"{_val.SHEET} missing -- run scripts/migrate_schema.py --apply")
    else:
        # Amended 2026-09-15 (Matthew, item 19): composition, published coverage and the reconciler read an invalid
        # row as invalid, through core/validity.py::invalid_observation_ids only (the reconciler only inside
        # sync_observations). Any other read from a gate module is still a breach.
        val_leaks = _val.wall_violations(ROOT)
        if val_leaks:
            rep.fail("CONVENTION 41 WALL BREACHED: gate-computing module(s) read observation validity other than "
                     "through invalid_observation_ids in a permitted reader -- " + ", ".join(val_leaks) + ". "
                     "Validity must not feed review_status / audit_verdict / publication_state / "
                     "reprocessing_required. Escalate, do not work around.")
        try:
            vrows = _val.rows_from_sheet(wb[_val.SHEET])
        except ValueError as e:
            vrows = None
            rep.fail(str(e))
        if vrows is not None:
            v_live = _val.live_observation_ids(wb)
            v_reg = _val.registry(wb)
            v_hist = _val.history_problems(vrows, v_live, set(v_reg))
            if v_hist:
                rep.fail(f"{_val.SHEET}: {len(v_hist)} problem(s) -- {v_hist[:4]}")
            v_cur = _val.current_rows(vrows)
            v_never, v_deleted, v_invalid = set(), {}, {}
            for d in _val.derivation_citations(wb):
                for oid, state in _val.citation_states(d["cited"], v_live, v_reg, v_cur).items():
                    if state == "never assigned":
                        v_never.add(oid)
                    elif state == "deleted":
                        v_deleted.setdefault(oid, 0)
                        v_deleted[oid] += 1
                    elif state.startswith("invalidated"):
                        v_invalid.setdefault(oid, 0)
                        v_invalid[oid] += 1
            if v_never:
                rep.fail(f"Company_State_History cites observation id(s) never assigned: {sorted(v_never)[:6]}")
            if v_deleted:
                rep.warn(f"Company_State_History cites {len(v_deleted)} DELETED observation(s) (retired ids, no row) "
                         f"in {sum(v_deleted.values())} citation(s): {sorted(v_deleted)} -- restore and record "
                         f"validity, or leave as named history")
            if v_invalid:
                rep.warn(f"Company_State_History cites {len(v_invalid)} INVALIDATED observation(s) in "
                         f"{sum(v_invalid.values())} citation(s): {sorted(v_invalid)}")
            v_hard = _val.hard_deletions(wb)
            if v_hard:
                rep.fail(f"NO HARD DELETION (convention 45): {len(v_hard)} retired observation id(s) whose claim has "
                         f"no row -- {v_hard[:6]}. Restore them through core/db.py::restore_observation and record "
                         f"their validity.")
            v_db_deletes = "delete_rows(" in (ROOT / "core/db.py").read_text(encoding="utf-8")
            if v_db_deletes:
                rep.fail("NO HARD DELETION (convention 45): core/db.py deletes sheet rows again")
            v_renum = _val.renumbered(wb)
            v_lineage = _val.lineage_problems(wb)
            if v_lineage:
                rep.fail(f"ID LINEAGE (item 20): {len(v_lineage)} registry row(s) whose current_id is wrong -- "
                         f"{v_lineage[:4]}. Run scripts/record_id_lineage.py.")
            if not (val_leaks or v_hist or v_never or v_hard or v_db_deletes or v_lineage):
                by_status = {}
                for r in v_cur.values():
                    by_status[r["validity_status"]] = by_status.get(r["validity_status"], 0) + 1
                rep.ok(f"check 15: observation validity history holds -- {len(vrows)} determination(s), "
                       f"{len(v_cur)} current {by_status or '(none yet)'}; every determined observation still has "
                       f"its row; no hard deletion ({len(v_renum)} pre-rule id(s) renumbered onto live claims, each "
                       f"recording its current_id); "
                       f"gate modules read validity only through invalid_observation_ids in "
                       f"{', '.join(sorted(_val.READERS))}")
    # VALIDITY-WALL-CHECK-END

    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    rep = validate(Path(args.db))

    if not args.quiet:
        for p in rep.passes:
            print(f"  ok    {p}")
        for w in rep.warnings:
            print(f"  warn  {w}")
        for f in rep.failures:
            print(f"  FAIL  {f}")
        print()
        print("repo and database agree" if not rep.failures
              else f"{len(rep.failures)} disagreement(s) between repo and database")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
