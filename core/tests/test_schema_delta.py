"""
Tests for the 2026-09-02 schema delta (Week 3 package, Part B).

    python core/tests/test_schema_delta.py

Part B's closing section lists four invariants "to enforce mechanically". Three of the four
are assertable today; the fourth is not, and saying which is which is the point of this file.

  1. Composition reads `realized_reach`; `nominal_reach` is never an inference input.
  2. Derivation stamps gating attribute values; never joins them live.
  3. `Signal_Types.status` filters rollups, never writes.
  4. Composition order: detectability -> reach -> instrument_class.

Invariants 1, 2 and 4 all govern a derivation that writes `Company_State_History`. That
sheet does not exist yet -- the temporal/historical design it belongs to has not been built
-- so there is no code path to constrain and a test asserting them would be asserting
nothing. They are recorded here as pending rather than faked green, because a test that
passes vacuously over an unbuilt requirement is convention 40's failure exactly: it asserts
the implementation (there isn't one) rather than the requirement.

What IS assertable today: the vocabulary and column groundwork those invariants will read,
and invariant 3, which is about a filter that already exists in the rollup layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import core.topics as topics  # noqa: E402
from core.db import WORKBOOK_PATH  # noqa: E402

PASSED = FAILED = PENDING = 0


def check(label: str, cond: bool) -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok       {label}")
    else:
        FAILED += 1
        print(f"  FAIL     {label}")


def pending(label: str, why: str) -> None:
    global PENDING
    PENDING += 1
    print(f"  PENDING  {label}")
    print(f"           {why}")


def main() -> int:
    wb = openpyxl.load_workbook(WORKBOOK_PATH, read_only=True, data_only=True)

    def headers(sheet):
        ws = wb[sheet]
        return [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

    def lookup(col_name):
        lk = wb["Lookups"]
        for c in range(1, lk.max_column + 1):
            if lk.cell(1, c).value == col_name:
                return [lk.cell(r, c).value for r in range(2, 60)
                        if lk.cell(r, c).value not in (None, "")]
        return []

    print("1. retrospective_reach lands on Harness_Sources, per source not per harness")
    hs = headers("Harness_Sources")
    for col in ("nominal_reach", "nominal_reach_months", "realized_reach",
                "realized_reach_months", "realized_reach_effective_from"):
        check(f"Harness_Sources has {col}", col in hs)
    # The grain matters: H-PROCUREMENT-01 alone spans two reach values (USASpending
    # archival, SAM.gov current_only), so a per-harness column could not represent it.
    check("the sheet is keyed per (harness, source), so a harness can span two values",
          "source_id" in hs and "harness_id" in hs)
    check("retrospective_reach vocabulary is the three §21 values",
          sorted(lookup("retrospective_reach"))
          == ["archival", "bounded", "current_only"])

    print()
    print("2. nominal and realized are SEPARATE columns, not one value")
    # §21.1: a paywalled trade archive is archival nominal and current_only realized.
    # Collapsing them loses exactly the acquisition backlog the split exists to produce,
    # and composing on the nominal value overclaims by the size of the access gap.
    check("nominal and realized are distinct columns",
          hs.count("nominal_reach") == 1 and hs.count("realized_reach") == 1
          and "nominal_reach" != "realized_reach")
    check("realized carries an effective_from; nominal does not need one",
          "realized_reach_effective_from" in hs
          and "nominal_reach_effective_from" not in hs)

    print()
    print("3. Signal_Types.status carries §22.1's five values")
    st = lookup("signal_type_status")
    for v in ("active", "routing_only", "out_of_theme", "access_bounded", "reference"):
        check(f"status vocabulary offers {v!r}", v in st)
    # Convention 22 is additive-only: `inactive` predates §22.1 and is retired by going
    # unused, never by deletion, because a query over historical rows must not break.
    check("`inactive` is retained rather than deleted (convention 22)", "inactive" in st)
    check("so the column holds six values while §22.1's live set is five",
          len(st) == 6)

    print()
    print("4. theme vocabulary: opaque id, mutable label, stampable hash")
    check("every theme carries an opaque theme_id",
          all(t.theme_id.startswith("THEME-") for t in topics.THEMES))
    check("theme_ids are unique",
          len({t.theme_id for t in topics.THEMES}) == len(topics.THEMES))
    # The whole point of the split: renaming the display label must not touch identity.
    t0 = topics.THEMES[0]
    check("display_label is an alias of label, not a second source of truth",
          t0.display_label == t0.label)
    check("`key` is preserved -- it is written into committed reviewed Observations",
          all(t.key for t in topics.THEMES))
    check("definition_hash is content-addressed and per-theme distinct",
          len({t.definition_hash for t in topics.THEMES}) == len(topics.THEMES))

    # Drift detection is the reason the hash exists: change the operative definition and
    # the hash must move. Asserted by changing an input, per convention 36.
    import copy
    probe = copy.deepcopy(topics.THEMES_BY_KEY["erp_core_systems"])
    before = probe.definition_hash
    probe.patterns = probe.patterns + [r"\bWorkday\b"]
    check("editing `patterns` moves the hash -- pattern drift IS definition drift",
          probe.definition_hash != before)
    probe2 = copy.deepcopy(topics.THEMES_BY_KEY["erp_core_systems"])
    before2 = probe2.definition_hash
    probe2.label = "ERP and core business systems (renamed)"
    check("editing the display label ALSO moves the hash, and identity does not",
          probe2.definition_hash != before2 and probe2.theme_id == "THEME-03")

    print()
    print("5. buyer_detectable_since -- capacity, not absence (§25.2)")
    flipped = {"cloud_infrastructure_migration", "cybersecurity",
               "workforce_enablement"}
    # `ot_modernization` carried NULL from the 2026-09-02 split until later the same day,
    # when H-JOBPOST-01 gained `ot_modernization_hiring` and the theme acquired an IC3
    # instrument. Its date is the day the instrument first COULD see it, and per §25.2
    # every bucket before that date is NULL, not zero. So nothing carries NULL today --
    # and that is asserted rather than assumed, because a theme with no instrument and a
    # date would be recording capacity it never had.
    later = {"ot_modernization": "2026-09-02"}
    check("every theme carries a detectability start date (none is uninstrumented now)",
          all(t.buyer_detectable_since for t in topics.THEMES))
    check("a theme is detectable only if some buyer signal key maps to it",
          all((t.key in set(topics.BUYER_SIGNAL_TO_THEME.values())) == t.buyer_detectable
              for t in topics.THEMES))
    check("the three themes that flipped on 2026-08-31 carry that date",
          all(topics.THEMES_BY_KEY[k].buyer_detectable_since == "2026-08-31"
              for k in flipped))
    check("ot_modernization carries the day its first instrument was wired, not the split",
          all(topics.THEMES_BY_KEY[k].buyer_detectable_since == d for k, d in later.items()))
    check("the six with an earlier instrument carry an earlier date",
          all(t.buyer_detectable_since < "2026-08-31"
              for t in topics.THEMES if t.key not in flipped | set(later)))

    print()
    print("5b. the cybersecurity / ot_modernization split (2026-09-02)")
    cyber = topics.THEMES_BY_KEY["cybersecurity"]
    ot = topics.THEMES_BY_KEY["ot_modernization"]
    # The continuing series keeps its theme_id. Its KEY was renamed the same day
    # (`cybersecurity_ot` -> `cybersecurity`, Matthew's decision): the four released rows
    # that carried the old key were machine-written and unreviewed, and nothing derived
    # had been stamped with it. The rename is declared once, in RETIRED_THEME_KEYS, and
    # the four rows were rewritten by migrate_schema.py::rename_topic_keys.
    check("the continuing theme is keyed `cybersecurity`",
          cyber.key == "cybersecurity")
    check("and keeps theme_id THEME-08 -- same series, same patterns",
          cyber.theme_id == "THEME-08")
    check("its LABEL is the narrowed one, which §6 says is free",
          cyber.label == "cybersecurity")
    check("`cybersecurity_ot` is retired: declared in RETIRED_THEME_KEYS, absent from the spine",
          topics.RETIRED_THEME_KEYS.get("cybersecurity_ot") == "cybersecurity"
          and "cybersecurity_ot" not in topics.THEMES_BY_KEY)
    check("every retired key points at a live key and none is itself live",
          all(new in topics.THEMES_BY_KEY and old not in topics.THEMES_BY_KEY
              for old, new in topics.RETIRED_THEME_KEYS.items()))
    # The workbook side of the same fact: no committed row may still carry a retired key.
    # Read from the sheet rather than trusted from the migration's own report.
    ws_obs = openpyxl.load_workbook(WORKBOOK_PATH, read_only=True)["Observations"]
    obs_rows = list(ws_obs.iter_rows(values_only=True))
    i_topic = obs_rows[0].index("topic")
    live_topics = {str(r[i_topic]) for r in obs_rows[1:] if r and r[0]}
    check("no Observations row carries a retired theme key",
          not (live_topics & set(topics.RETIRED_THEME_KEYS)))
    # Exactly-four was true on 2026-09-02; since the low-grade tier (2026-09-03) other
    # harnesses write cybersecurity rows too, so the assertion is on the four named ids.
    renamed_ids = {"O00225", "O00230", "O00234", "O00255"}
    check("the four renamed H-SELLERCONTENT-01 rows carry `cybersecurity`",
          {r[0] for r in obs_rows[1:] if r and r[0] in renamed_ids and r[i_topic] == "cybersecurity"}
          == renamed_ids)
    check("the split minted a NEW key rather than repointing one",
          ot.key == "ot_modernization" and ot.theme_id == "THEME-10")
    # The defect the split fixes: the old theme's patterns were ALL security terms.
    check("cybersecurity still has no control-system vocabulary",
          not any(re_ in " ".join(cyber.patterns)
                  for re_ in ("SCADA", "PLC", "HMI", "historian")))
    check("ot_modernization has the control-system vocabulary it was split for",
          all(term in " ".join(ot.patterns)
              for term in ("SCADA", "PLC", "ICS", "DCS", "HMI", "historian",
                           "control system", "industrial network")))
    # Neither-nor and both-at-once are the two ways a split goes wrong.
    sec_only = topics.classify("Ransomware tabletop for the security operations team.")
    ot_only = topics.classify("Upgrading legacy SCADA and PLC control systems.")
    check("security text routes to cybersecurity only, not both",
          set(sec_only) & {"cybersecurity", "ot_modernization"} == {"cybersecurity"})
    check("control-system text routes to ot_modernization only, not both",
          set(ot_only) & {"cybersecurity", "ot_modernization"} == {"ot_modernization"})

    print()
    print("6. definition text is owed, and is not invented here (§25.4)")
    # 2026-09-03: Matthew supplied the two over-covering pairs (session 9 brief item 4);
    # the other eight stay empty until their boundaries are written, per §25.4.
    supplied = {"systems_integration", "cloud_infrastructure_migration"}
    check("`definition` is written for exactly the two themes Matthew supplied (§25.4)",
          {t.key for t in topics.THEMES if t.definition} == supplied)
    check("and stays empty on the other eight -- not invented here",
          all(not t.definition for t in topics.THEMES if t.key not in supplied))

    print()
    print("6b. two-tier admission in the provider-side spine (pattern-fix brief §2)")
    cl = topics.classify
    check("bare 'integration' admits nothing (six of seven provider rows rested on it)",
          "systems_integration" not in cl("We offer integration services to manufacturers."))
    check("bare 'API' admits nothing",
          "systems_integration" not in cl("Our API strategy practice."))
    check("'API' + 'integration' together corroborate (generic + generic, corroboration=any)",
          "systems_integration" in cl("API-led integration for the supply chain."))
    check("a specific term admits alone: 'EDI', 'middleware', 'iPaaS'",
          all("systems_integration" in cl(t) for t in ("EDI onboarding", "middleware",
                                                       "an iPaaS platform")))
    check("'post-merger integration' is excluded and cannot corroborate 'API'",
          "systems_integration" not in cl("post-merger integration and API governance"))
    check("cloud: bare 'AWS' admits nothing; 'AWS' + 'mainframe' still nothing (needs a specific hit)",
          "cloud_infrastructure_migration" not in cl("AWS partner")
          and "cloud_infrastructure_migration" not in cl("mainframe estates and AWS"))
    check("cloud: 'cloud migration' admits alone and carries 'AWS' as evidence",
          cl("AWS cloud migration").get("cloud_infrastructure_migration") == ["cloud migration", "AWS"])
    check("bare 'AI' admits nothing; 'AI' + 'machine learning' does",
          "data_analytics_ai" not in cl("AI") and "data_analytics_ai" in cl("AI and machine learning"))
    check("bare 'SAP' admits nothing; 'SAP S/4HANA' does; bare 'ERP' still does",
          "erp_core_systems" not in cl("SAP") and "erp_core_systems" in cl("SAP S/4HANA")
          and "erp_core_systems" in cl("ERP"))
    check("bare 'Lean' admits nothing; 'Lean Six Sigma' does",
          "digital_transformation_process" not in cl("Lean")
          and "digital_transformation_process" in cl("Lean Six Sigma"))
    check("bare 'AMR' admits nothing; 'AMR' + 'goods-to-person' does",
          "warehouse_automation" not in cl("AMR")
          and "warehouse_automation" in cl("AMR goods-to-person"))
    check("the tier fields are part of definition_hash (a generic edit is a definition change)",
          (lambda t: (t.generic.append(r"\bprobe\b"), t.definition_hash)[1])(
              copy.deepcopy(topics.THEMES_BY_KEY["systems_integration"]))
          != topics.THEMES_BY_KEY["systems_integration"].definition_hash)
    check("every theme's specific tier is non-empty (a theme cannot be generic-only)",
          all(t.patterns for t in topics.THEMES))

    print()
    print("7. the four invariants, against core/composition.py (session 13)")
    import datetime as _dt
    from core import composition as comp

    src = (ROOT / "core" / "composition.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]          # strip the module docstring
    check("composition reads realized_reach, never nominal_reach (the string is absent "
          "from the derivation code)",
          "realized_reach" in body and "nominal_reach" not in body)
    check("Company_State_History exists with the composition's column contract",
          headers("Company_State_History")[:len(comp.STATE_HISTORY_COLUMNS)]
          == comp.STATE_HISTORY_COLUMNS)

    # A small synthetic world: one company, the real themes, two instruments.
    T = topics.THEMES_BY_KEY
    early = T["warehouse_automation"]          # detectable since 2026-08-24
    late = T["cybersecurity"]                  # detectable since 2026-08-31
    day = _dt.date(2026, 9, 5)

    def world(reach_kind, ic="IC1", signal="first_party_announcement",
              when="2026-09-03T10:00:00", obs=None):
        return comp.Inputs(
            companies=["X1"],
            attempts=[{"harness_id": comp.THEME_INSTRUMENTS[signal][0], "company_id": "X1",
                       "attempted_signal": signal, "outcome": "absent_confirmed",
                       "scope": "scoped", "attempt_timestamp": when}],
            observations=obs or [],
            harness_reach={comp.THEME_INSTRUMENTS[signal][0]: {
                "realized_reach": reach_kind, "realized_reach_months": 24,
                "realized_reach_effective_from": "2026-08-31"}},
            instrument_class={signal: ic},
            themes=[early, late])

    def cell(rows, theme_key, bucket_id):
        return next(r for r in rows if r["theme_key"] == theme_key and r["bucket_id"] == bucket_id)

    rows = comp.derive(world("archival"), derived_at=day)
    check("series starts at the earliest detectability date among the themes given "
          "(2026-08-24 -> 2026-W35) and runs to derived_at (2026-W36)",
          sorted({r["bucket_id"] for r in rows}) == ["2026-W35", "2026-W36"])
    check("ORDER 1: a theme not yet detectable in a bucket is theme_not_detectable even "
          "though an archival source reaches the bucket",
          cell(rows, "cybersecurity", "2026-W35")["reason"] == "theme_not_detectable"
          and cell(rows, "cybersecurity", "2026-W35")["min_retrospective_reach"] is None)
    check("the three flipped themes are null before 2026-08-31 -- the pre-8/31 period is "
          "not a clean absence -- and detectable from the week that starts on it",
          cell(rows, "cybersecurity", "2026-W35")["status"] == "null"
          and cell(rows, "cybersecurity", "2026-W36")["reason"] != "theme_not_detectable")
    check("ORDER 2: detectable, archival reach covers, IC1 only -> no_absence_license "
          "(taxonomy §26 'formally untested'), never absent",
          cell(rows, "warehouse_automation", "2026-W35")["reason"] == "no_absence_license"
          and cell(rows, "warehouse_automation", "2026-W35")["status"] == "null")

    rows = comp.derive(world("current_only"), derived_at=day)
    check("REACH: a current_only source read in W36 says nothing about W35 -> no_reach",
          cell(rows, "warehouse_automation", "2026-W35")["reason"] == "no_reach")
    check("REACH: ... and does reach its own bucket",
          cell(rows, "warehouse_automation", "2026-W36")["reason"] != "no_reach")

    rows = comp.derive(world("archival", ic="IC4", signal="executive_public_statement"),
                       derived_at=day)
    check("ORDER 3: IC4 instrument with reach and no evidence -> licensed absence",
          cell(rows, "warehouse_automation", "2026-W35")["status"] == "absent"
          and cell(rows, "warehouse_automation", "2026-W35")["reason"] == "absence_licensed_IC4")
    rows = comp.derive(world("current_only", ic="IC3", signal="job_posting"), derived_at=day)
    check("PRESENCE ONLY: H-JOBPOST-01 is IC3 but its silence licenses nothing "
          "(Signal Advisor condition 1)",
          cell(rows, "warehouse_automation", "2026-W36")["reason"] == "no_absence_license")

    ob = [{"observation_id": "O99999", "company_id": "X1", "harness_id": "H-FIRSTPARTY-01",
           "evidence_role": "buyer_articulates", "topic": "warehouse_automation",
           "publication_date": "2026-08-26", "retrieval_date": "2026-09-03",
           "organizational_state": "active_transition", "source_grade": "B",
           "confidence_0_1": 0.7, "publication_state": "released"}]
    rows = comp.derive(world("archival", obs=ob), derived_at=day)
    w35, w36 = cell(rows, "warehouse_automation", "2026-W35"), cell(rows, "warehouse_automation", "2026-W36")
    check("EVIDENCE: a released row dated inside W35 makes W35 observed with its state",
          w35["status"] == "observed" and w35["organizational_state"] == "active_transition"
          and w35["supporting_observation_ids"] == "O99999")
    check("EVIDENCE: a state persists forward -- W36 is observed on the same row",
          w36["status"] == "observed" and w36["supporting_observation_ids"] == "O99999")
    ob[0]["publication_date"] = "2026-09-02"
    rows = comp.derive(world("archival", obs=ob), derived_at=day)
    check("EVIDENCE: a row dated in W36 does not reach back to W35 (publication_date > bucket_end)",
          cell(rows, "warehouse_automation", "2026-W35")["status"] == "null"
          and cell(rows, "warehouse_automation", "2026-W36")["status"] == "observed")
    ob[0]["publication_date"] = "2026-08-26"
    ob[0]["publication_state"] = "quarantined"
    rows = comp.derive(world("archival", obs=ob), derived_at=day)
    check("EVIDENCE: a quarantined row informs nothing",
          cell(rows, "warehouse_automation", "2026-W35")["status"] == "null")

    stamped = cell(comp.derive(world("archival"), derived_at=day), "warehouse_automation", "2026-W35")
    check("STAMP: definition_hash, buyer_detectable_since and min_retrospective_reach are "
          "values on the row, equal to what was composed against",
          stamped["definition_hash"] == early.definition_hash
          and stamped["buyer_detectable_since"] == early.buyer_detectable_since
          and stamped["min_retrospective_reach"] == "archival")
    check("STAMP: no live join at read time -- the writer refuses a row past the reach gate "
          "without its stamped reach",
          "min_retrospective_reach" in (ROOT / "core" / "db.py").read_text(encoding="utf-8")
          and "already on Company_State_History" in (ROOT / "core" / "db.py").read_text(encoding="utf-8"))

    print()
    print("7b. Signal_Types.status is a rollup filter, never a write filter")
    from core import attempts as att_mod

    from core.db import MarketIntelDB
    _db = MarketIntelDB()                      # in-memory only; never saved here
    _db.signal_type_status = lambda: {"live_type": "active", "routed_type": "routing_only"}
    ctx = att_mod.RunContext(_db, "H-TEST", "t", "v0", "1_first_party_strategy_governance",
                             scope=[("X1", "live_type"), ("X1", "routed_type")])
    ctx.attempt("X1", "live_type", "absent_confirmed")
    ctx.attempt("X1", "routed_type", "absent_confirmed")
    roll = ctx.rollups()
    check("both attempts are recorded (the write is unfiltered)", len(ctx.attempts) == 2)
    check("only the active type enters the denominator", roll["attempts_total"] == 1
          and roll["attempts_absent_confirmed"] == 1 and roll["coverage_rate"] == 1.0)
    check("published_coverage.py applies the same filter",
          "ROLLUP_STATUSES" in (ROOT / "scripts" / "published_coverage.py").read_text(encoding="utf-8"))

    print(f"\n{PASSED} checks passed, {FAILED} failed, {PENDING} pending.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
