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
        quarantined = set()
        superseded: dict[tuple, list] = {}
        for r in range(2, hr.max_row + 1):
            if hr.cell(r, 1).value is None:
                continue
            pair = (str(hr.cell(r, i_hid + 1).value or "").strip(),
                    str(hr.cell(r, i_ver + 1).value or "").strip())
            status = str(hr.cell(r, i_pub + 1).value or "").strip().lower()
            run_id = str(hr.cell(r, i_run + 1).value or "").strip()
            if status == "published":
                published.setdefault(pair, []).append(run_id)
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

        missing, malformed, failing = [], [], []
        for pair, run_ids in sorted(published.items()):
            if pair in grandfathered:
                continue
            art = artifacts.get(pair)
            if art is None:
                missing.append(f"{pair[0]} {pair[1]} (runs {', '.join(run_ids)}) — "
                               f"expected {audit.audit_path(*pair).name}")
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
        orphans = [f"{h} {v}" for (h, v) in artifacts
                   if (h, v) not in published and (h, v) not in quarantined]
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
            gf = len([p for p in published if p in grandfathered])
            tail = (f", {len(superseded)} superseded" if superseded else "")
            rep.ok(f"check 9: {len(published)} published harness version(s) — "
                   f"{len(published) - gf} audited, {gf} grandfathered, "
                   f"{len(quarantined)} quarantined run(s) not yet publishing" + tail)

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
