"""
The shared modernization-theme spine.

The governing question asks where buyer and seller signal *converge or diverge*. That
comparison is only meaningful if both sides are classified into the same vocabulary — if
the job-posting harness emits `erp_core_systems_hiring` and a seller harness emits
`erp-modernization`, the gap analysis becomes a string-matching exercise and any
divergence it reports is an artefact of two people naming things differently.

So themes live here, once, and every harness on either side of the market maps into them.

ON THE ASYMMETRY, WHICH IS DELIBERATE
--------------------------------------
`buyer_detectable` records whether ANY buyer-side harness could surface a theme. Where it
is False, "sellers message about X and no buyer signal mentions it" is a statement about
the harness portfolio, not about the market, and must not be written up as a divergence.

STATUS CHANGE, 2026-08-31: all nine themes are now marked detectable.
-------------------------------------------------------------------
Three themes — cloud migration, cybersecurity/OT and workforce enablement — carried False
because the only buyer-side instruments were job postings and regulatory registries, none
of which had a category that could see them. H-FIRSTPARTY-01 changed that: it classifies
free-text company announcements through this same spine, so it can surface any theme, and
on its first full run it returned buyer observations on workforce enablement specifically.
Leaving the flags False made `scripts/gap_report.py` contradict itself, printing
"NO INSTRUMENT" beside a non-zero buyer count.

The flip is not a promotion to equal footing, and the per-theme notes say so. A first-party
announcement is a BIASED instrument: companies announce programmes they are proud of and
do not announce the legacy estate that forced them. So absence of buyer signal on these
three now means "not announced", which is a weaker claim than "not happening" — weaker
than the absence of a job posting, which at least reflects unguarded operational
behaviour. Cybersecurity is the extreme case: almost nothing is announced voluntarily.

Treat a low buyer count on these three as uninformative rather than as evidence of buyer
silence, and prefer H-EXECVOICE-01 or a future employee-review harness as the instrument
that could actually falsify a divergence claim there.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class Theme:
    key: str
    label: str
    patterns: list          # provider-side phrasing; buyer-side patterns live per-harness
    buyer_detectable: bool  # can any buyer-side harness built so far surface this?
    note: str = ""

    # ---- taxonomy §25, added 2026-09-02 (Part B point 2, approved by Matthew) ----
    #
    # `theme_id` is the OPAQUE, permanent identifier. `label` is a display attribute and
    # may be edited freely. The split exists because `Company_State_History` is
    # append-only and immutable: a string rename would be either a prohibited history
    # rewrite or a permanent series split, while a rename against an opaque id costs
    # nothing and a genuine SPLIT is forced to be explicit because it has to mint a new id.
    #
    # `key` is NOT replaced and NOT renamed. It is written into committed, human-reviewed
    # Observations -- O00366 carries topic `digital_transformation_process` under a human
    # `corrected` verdict -- so renaming it would break provenance on reviewed evidence
    # for a cosmetic gain. Same reasoning that grandfathered H-FMCSA-01's name and that
    # kept BUYER_SIGNAL_TO_THEME a mapping rather than a rename.
    theme_id: str = ""

    # The written definition, per §25.1: freezing the identifier is not enough, because a
    # theme whose DEFINITION drifts while its identifier holds corrupts a series without
    # splitting it and leaves no trace.
    #
    # DELIBERATELY EMPTY. §25.4 requires written boundaries -- at minimum between
    # `workforce_enablement` and both `legacy_constraint` and labour friction -- and
    # nobody has supplied them. Writing definitions here would be inventing the content
    # the section exists to demand.
    definition: str = ""

    # Date this theme first had ANY buyer-side instrument. Per §25.2 a bucket before this
    # date is NULL, not zero: the project had no capacity to observe the theme, and
    # storing that as an observed absence manufactures exactly the divergence pattern the
    # project is built to detect. `None` means never detectable.
    buyer_detectable_since: str | None = None

    _rx: list = field(default_factory=list, repr=False)

    # ---- two-tier admission, 2026-09-02 (pattern-fix brief §2) ----
    #
    # `patterns` is the SPECIFIC tier: a hit fires alone. `generic` is the tier that needs
    # corroboration -- a second, distinct hit in the same text -- before it counts, because
    # each of these words appears in ordinary prose at a rate that manufactures provider
    # messaging out of nothing (six of seven `systems_integration` provider rows rested on
    # the bare word "integration"). `corroboration` says what counts as a second hit:
    # "any" (either tier) or "specific" (only a specific-tier hit -- used where two generic
    # terms together still do not name the theme, e.g. "mainframe" + "AWS" is a legacy
    # estate and a vendor, not a cloud migration). `exclusions` are phrases blanked out
    # of the text before matching, for a named false sense ("post-merger integration").
    #
    # Same shape as the ST-REMOVEDPAGE corroboration gate (taxonomy §22.5) and for the same
    # reason: the noise is correlated with the signal, so a threshold on volume cannot
    # separate them and only a threshold on SPECIFICITY can. And it is an admission rule,
    # not a strength downgrade (convention 32): a generic-only text produces no hit at all.
    generic: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    corroboration: str = "any"

    # Whether ABSENCE of buyer signal in this theme is a licensed inference. False where
    # every buyer-side instrument is either IC1 (a first-party announcement, biased
    # against the theme) or presence-only (an H-JOBPOST-01 key gated on the careers-page
    # readability denominator, Signal Advisor 2026-09-02 condition 1). gap_report.py
    # reads it: such a theme with zero buyer signal is "no absence instrument", never
    # "buyer silent". Distinct from `buyer_detectable`, which says presence CAN be seen.
    # `absence_licensed` was removed 2026-09-06 (session 14 item 0b). Whether a
    # theme's silence may be read as absence is a property of the INSTRUMENTS that
    # see it, computed by core/composition.py::absence_licensing from the same
    # declarations the derivation uses -- not a hand-set flag that drifts.
    _rx_generic: list = field(default_factory=list, repr=False)
    _rx_excl: list = field(default_factory=list, repr=False)

    @property
    def all_patterns(self) -> list:
        """Both tiers, specific first. For inventory and display, not for admission."""
        return list(self.patterns) + list(self.generic)

    @property
    def display_label(self) -> str:
        """The mutable half of the identifier split. Alias of `label`, which four
        harnesses already read; the alias exists so §25's vocabulary is usable without
        renaming a field that is in live use."""
        return self.label

    @property
    def definition_hash(self) -> str:
        """Content hash of the theme's OPERATIVE definition, for stamping onto derived
        rows so a later definition change is a visible event rather than a silent rewrite.

        Hashed over `label`, `note`, `definition` and `patterns` together, because
        `patterns` is what actually decides routing today -- a pattern edit changes which
        observations land in the theme and is therefore a definition change in the sense
        §25.1 means, whether or not any prose moved. Once §25.4's written boundaries land
        in `definition`, they join the same hash rather than replacing it.
        """
        payload = "".join([self.key, self.label, self.note, self.definition,
                           *self.patterns, "|generic|", *self.generic,
                           "|exclusions|", *self.exclusions, self.corroboration])
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def compiled(self):
        if not self._rx:
            self._rx = [re.compile(p, re.I) for p in self.patterns]
        return self._rx

    def _compiled_generic(self):
        if not self._rx_generic and self.generic:
            self._rx_generic = [re.compile(p, re.I) for p in self.generic]
        return self._rx_generic

    def _compiled_excl(self):
        if not self._rx_excl and self.exclusions:
            self._rx_excl = [re.compile(p, re.I) for p in self.exclusions]
        return self._rx_excl

    def _hits(self, text: str) -> tuple[list[str], list[str]]:
        for rx in self._compiled_excl():
            text = rx.sub(" ", text)
        specific = []
        for rx in self.compiled():
            m = rx.search(text)
            if m:
                specific.append(m.group(0))
        generic = []
        for rx in self._compiled_generic():
            m = rx.search(text)
            if m:
                generic.append(m.group(0))
        return specific, generic

    def _admits(self, specific: list, generic: list) -> bool:
        if specific:
            return True
        return self.corroboration == "any" and len({g.lower() for g in generic}) >= 2

    def matches(self, text: str) -> list[str]:
        """The ADMITTED hits for this theme in `text`, or [] if the theme is not admitted.

        A specific-tier hit admits the theme and every generic hit rides along as
        evidence. Generic hits alone admit it only when at least two DISTINCT generic
        patterns hit and `corroboration == "any"`. Exclusion phrases are blanked before
        either tier is searched, so a named false sense cannot corroborate anything.
        """
        specific, generic = self._hits(text)
        return specific + generic if self._admits(specific, generic) else []

    def refused(self, text: str) -> list[str]:
        """Generic-tier hits that were seen but did NOT admit the theme.

        Convention 7: a suppressed result is reported, not dropped. A harness that
        wants to tell a reviewer "this text mentioned integration once and the spine
        declined it" reads this; nothing downstream may admit on it.
        """
        specific, generic = self._hits(text)
        return [] if self._admits(specific, generic) else generic

THEMES = [
    Theme(
        key="warehouse_automation",
        theme_id="THEME-01",
        buyer_detectable_since="2026-08-24",
        label="warehouse automation and fulfilment systems",
        patterns=[
            r"\bWMS\b", r"warehouse management system", r"warehouse execution",
            r"\bAS/RS\b", r"goods[- ]to[- ]person", r"pick(ing)? automation",
            r"fulfil?ment (automation|optimization)", r"material handling",
            r"warehouse (automation|robotics)", r"\bautomated storage\b",
        ],
        # AMR is also "adjustable rate mortgage" and a common initialism; needs company.
        generic=[r"\bAMR\b"],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 warehouse_systems_automation_hiring.",
    ),
    Theme(
        key="data_analytics_ai",
        theme_id="THEME-02",
        buyer_detectable_since="2026-08-24",
        label="data platforms, analytics and AI",
        patterns=[
            r"\bartificial intelligence\b", r"machine learning",
            r"\bgen(erative)?[ -]?AI\b",
            # Qualified phrases are specific in the same way "generative AI" is. Added
            # 2026-09-02 when demoting bare "AI" exposed that "an agentic AI system"
            # (Gilbane's CEO, O00376) had only ever matched through the bare token.
            r"\bagentic( AI)?\b", r"\bAI (agents?|copilots?|assistants?)\b",
            r"\bdata (platform|strategy|governance|warehouse|lake)\b",
            r"\banalytics\b", r"business intelligence", r"predictive (analytics|maintenance)",
            r"\bdata[- ]driven\b", r"\bdigital twin\b",
        ],
        # A bare "AI" on a services page is a slogan, not a capability (P009 rested on it
        # alone). It counts beside any other term in the theme.
        generic=[r"\bAI\b(?![-\w])"],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 data_analytics_ai_hiring.",
    ),
    Theme(
        key="erp_core_systems",
        theme_id="THEME-03",
        buyer_detectable_since="2026-08-24",
        label="ERP and core business systems",
        patterns=[
            r"\bERP\b", r"S/4\s?HANA", r"\bNetSuite\b", r"\bDynamics 365\b",
            r"\bEpicor\b", r"\bJD Edwards\b",
            r"core (system|platform) (modernization|migration|replacement)",
        ],
        # Vendor names that are also a database vendor, a three-letter word and a prefix
        # of "information" respectively. A product that is ONLY an ERP (S/4HANA, NetSuite,
        # Dynamics 365, JD Edwards, Epicor) stays specific; a bare vendor name needs
        # company (P012 rested on "SAP" alone).
        generic=[r"\bSAP\b", r"\bOracle\b", r"\bInfor\b"],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 erp_core_systems_hiring.",
    ),
    Theme(
        key="systems_integration",
        theme_id="THEME-04",
        buyer_detectable_since="2026-08-24",
        label="systems integration and interoperability",
        # §25.4 definition, Matthew 2026-09-03 (session 9 brief item 4). Written by the
        # project owner, not invented here; the tiers below narrow toward the brief's
        # named terms and this definition says what a generic-only match still counts as.
        definition=(
            "Connecting disparate systems or data so they work together: interfaces, "
            "middleware, data exchange, interoperability between applications. A general "
            "claim about connecting systems or data is SUFFICIENT; no named platform, "
            "vendor or protocol is required. Excludes post-merger integration (an "
            "organisational act) and integration in the manufacturing sense (assembling "
            "components). Boundary with erp_core_systems: a claim about the core platform "
            "itself is ERP; a claim about making it talk to something else is integration."),
        patterns=[
            r"\bEDI\b", r"\biPaaS\b", r"middleware", r"\bETL\b",
            r"system(s)? interoperability", r"data integration",
        ],
        # THE measured defect (2026-09-02): six of seven provider rows in this theme rested
        # on the bare word "integration" and nothing else. "API" and "integration" are
        # ordinary consulting prose; either counts only beside another hit.
        generic=[r"\bAPI\b", r"\bintegration\b"],
        # Routine in mid-size industrial press releases; unrelated to interoperability.
        exclusions=[r"post[- ]merger integration"],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 integration_engineering_hiring. Integration demand "
             "is a legacy-estate signal as much as a modernization one.",
    ),
    Theme(
        key="digital_transformation_process",
        theme_id="THEME-05",
        buyer_detectable_since="2026-08-24",
        label="digital transformation and process excellence",
        patterns=[
            r"digital transformation", r"\bmodernization\b", r"operational excellence",
            r"process (improvement|excellence|reengineering|automation)",
            r"continuous improvement", r"Six Sigma", r"change management",
            r"\bRPA\b", r"robotic process automation", r"workflow automation",
        ],
        # The provider-side twin of the H-JOBPOST-01 "Lean Beef Processing Associate"
        # fix: this universe has food distributors, and lean is an adjective there.
        generic=[r"\bLean\b"],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 digital_transformation_hiring.",
    ),
    Theme(
        key="transportation_fleet_systems",
        theme_id="THEME-06",
        buyer_detectable_since="2026-08-22",
        label="transportation and fleet systems",
        patterns=[
            r"\bTMS\b", r"transportation management system", r"telematics",
            r"route (optimization|planning)", r"fleet (management|technology|optimization)",
            r"last[- ]mile", r"freight (visibility|audit|optimization)",
        ],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 transportation_systems_hiring, plus H-FMCSA-01 "
             "registry evidence about fleet operations.",
    ),
    Theme(
        key="cloud_infrastructure_migration",
        theme_id="THEME-07",
        buyer_detectable_since="2026-08-31",
        label="cloud migration and infrastructure modernization",
        # §25.4 definition, Matthew 2026-09-03 (session 9 brief item 4).
        definition=(
            "Moving or modernising the infrastructure estate: migration to hosted or cloud "
            "platforms, retiring owned data centres or mainframes, re-platforming legacy "
            "applications, and broader infrastructure-modernisation language. Explicit "
            "cloud-provider or migration terms are NOT required; legacy-estate and "
            "infrastructure-modernisation language COUNTS. Boundary with "
            "digital_transformation_process: transformation is the programme, this theme "
            "is the estate it runs on. Boundary with erp_core_systems: replacing the "
            "application is ERP; moving where it runs is this theme."),
        patterns=[
            r"cloud (migration|modernization|transformation|adoption)",
            r"\blift and shift\b", r"\bdata cent(er|re) (migration|exit)\b",
        ],
        # Legacy-estate terms and bare vendor names are not cloud-specific (Signal
        # Advisor, 2026-09-02): "mainframe" is what is being left, "AWS" is a partner logo.
        # Each counts only beside a SPECIFIC hit -- two generic terms together ("mainframe"
        # + "application modernization") still describe an estate, not a migration.
        generic=[r"\bmainframe\b", r"legacy (system|application) modernization",
                 r"application modernization", r"\bAzure\b", r"\bAWS\b", r"\bGCP\b"],
        corroboration="specific",
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 cloud_infrastructure_hiring (2026-09-02, PRESENCE "
             "ONLY until the careers-page readability denominator is accepted -- 14 of 108 "
             "readable on the last run) and H-FIRSTPARTY-01 (2026-08-31). Previously marked "
             "undetectable because H-JOBPOST-01 had no cloud signal category. First-party "
             "announcements classify into every theme, so the instrument now exists -- "
             "but it is a BIASED one: companies announce cloud programmes they are proud "
             "of and do not announce the legacy estate driving them. Absence here means "
             "'not announced', which is weaker than 'not happening'.",
    ),
    Theme(
        # theme_id DELIBERATELY UNCHANGED. This is the continuing series from the
        # 2026-09-02 split: it keeps every pattern it had, so what classifies into it is
        # identical before and after. The label narrowed to "cybersecurity" in the split.
        #
        # KEY RENAMED `cybersecurity_ot` -> `cybersecurity`, 2026-09-02, Matthew's decision
        # (post-session-6 brief, item 3). The split had kept the old key because four
        # RELEASED observations carried it (O00225, O00230, O00234, O00255 --
        # H-SELLERCONTENT-01 provider rows P004/P005/P006/P012) and repointing an id
        # written into committed evidence is the thing convention 26 forbids. The
        # decision to rename anyway rests on two facts that convention 26's cases lacked:
        # all four rows are machine-written and unreviewed, so no human provenance moves;
        # and nothing derived exists yet -- `Company_State_History` is unbuilt -- so the
        # rename touches four cells now and would touch a series later. The rows were
        # rewritten by `scripts/migrate_schema.py::rename_topic_keys`, which reads
        # RETIRED_THEME_KEYS below and refuses to touch a human-reviewed row.
        key="cybersecurity",
        theme_id="THEME-08",
        buyer_detectable_since="2026-08-31",
        label="cybersecurity",
        patterns=[
            r"\bcyber ?security\b", r"\bOT security\b", r"\bIT/OT\b", r"zero trust",
            r"\bransomware\b", r"security (posture|assessment|operations)",
            r"\bNIST\b", r"\bCMMC\b",
        ],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 cybersecurity_hiring (2026-09-02, PRESENCE ONLY "
             "until the careers-page readability denominator is accepted) and "
             "H-FIRSTPARTY-01 (2026-08-31). Same caveat as cloud, and "
             "stronger: companies almost never announce security posture, and announcing "
             "a breach is compelled rather than volunteered. Treat a low buyer count here "
             "as uninformative rather than as evidence of buyer silence.",
    ),
    Theme(
        # NEW KEY, NEW theme_id -- a split mints an identifier rather than repointing one
        # (theme confirmation §6). Nothing historical maps here: no observation has ever
        # carried this key, so the series legitimately starts empty rather than inheriting.
        #
        # WHY IT EXISTS: THEME-08 (then keyed `cybersecurity_ot`, now `cybersecurity`)
        # was labelled "cybersecurity and OT/IT convergence" while every one of its eight
        # patterns is a security term. There was
        # no pattern for SCADA, PLC, ICS, DCS, historian, control system, HMI, industrial
        # network or plant-floor connectivity, so OT MODERNIZATION -- replacing
        # twenty-year-old plant control systems, a central story for construction, energy,
        # food distribution and manufacturing -- was invisible to the classifier on both
        # sides of the market. The name promised coverage the implementation did not
        # deliver.
        #
        # Vocabulary is Signal Advisor's named starting list, plus the expansions of each
        # acronym so long-form seller prose matches too. Terms are kept specific on
        # purpose: `historian` and `HMI` are bounded by their industrial sense here, and
        # no bare generic word (`controls`, `plant`, `network`) is admitted alone --
        # convention 31, and the same reasoning that keeps `\bLean\b` out of a job title.
        key="ot_modernization",
        theme_id="THEME-10",
        # 2026-09-02: H-JOBPOST-01 gained `ot_modernization_hiring` (controls engineers,
        # SCADA/PLC/HMI roles), so the theme launches with an IC3 instrument rather than
        # IC1-only. The date is the day the instrument first COULD see it; per §25.2 the
        # buckets before it are NULL. PRESENCE ONLY until the careers-page readability
        # denominator is accepted (14 of 108 readable on the last run) -- absence from
        # this key says nothing until then.
        buyer_detectable_since="2026-09-02",
        label="OT modernization and industrial control systems",
        patterns=[
            r"\bSCADA\b", r"\bPLC\b", r"\bICS\b", r"\bDCS\b",
            r"programmable logic controller", r"distributed control system",
            r"industrial control system", r"\bHMI\b", r"human[- ]machine interface",
            r"process historian", r"data historian",
            r"control system (upgrade|migration|modernization|replacement)",
            r"plant[- ]floor (connectivity|network|system)",
            r"industrial network", r"\bOT (network|infrastructure|modernization)\b",
            r"shop[- ]floor (connectivity|system)",
        ],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 ot_modernization_hiring (2026-09-02, PRESENCE "
             "ONLY until the careers-page readability denominator is accepted). Split out "
             "of THEME-08 (`cybersecurity`, keyed `cybersecurity_ot` until the same day) "
             "on 2026-09-02 because that theme's patterns were entirely security terms "
             "and OT modernization was invisible to the classifier. No observation has "
             "yet been written into it on either side, so its absence licenses nothing "
             "at all -- it is NOT a divergence and must not be reported as one. Signal "
             "Advisor's argument "
             "for splitting rather than renaming is that OT modernization leaves physical "
             "traces in this company class: permits, capex and controls-engineer "
             "requisitions are IC3/IC4 instruments that could actually test it, which is "
             "what converts a formally-untested theme into a testable one.",
    ),
    Theme(
        key="workforce_enablement",
        theme_id="THEME-09",
        buyer_detectable_since="2026-08-31",
        label="workforce enablement and frontline technology",
        patterns=[
            r"frontline (worker|technology|enablement)", r"workforce (management|enablement)",
            r"\bdeskless\b", r"labo(u)?r (management|productivity|standards)",
            r"training and (adoption|enablement)", r"user adoption",
        ],
        buyer_detectable=True,
        note="Buyer side: H-JOBPOST-01 workforce_enablement_hiring (2026-09-02, PRESENCE "
             "ONLY until the careers-page readability denominator is accepted) and "
             "H-FIRSTPARTY-01 (2026-08-31), which returned buyer observations "
             "on this theme in its first run. Glassdoor/Indeed review mining "
             "(H-EMPVOICE-01, not built) remains the better instrument, because it sees "
             "the frontline experience an announcement is written to flatter.",
    ),
]

THEMES_BY_KEY = {t.key: t for t in THEMES}

# Theme keys that have been RETIRED, mapped to the key that replaced them. This is the one
# place a rename is declared: `scripts/migrate_schema.py::rename_topic_keys` rewrites
# `Observations.topic` from it, `scripts/validate_repo_db.py` check 8 fails if any row
# still carries a retired key, and `scripts/theme_regression.py` treats old->new as
# identity when it diffs the classifier. A retired key is never reused and never deleted
# from this map, for the same reason vocabulary values are retired rather than removed
# (convention 22): a run log or a snapshot written before the rename must stay readable.
#
# The bar for adding an entry is the one the 2026-09-02 rename cleared: no human-reviewed
# row carries the old key, and nothing derived has been stamped with it. Once
# `Company_State_History` exists, a rename is a series split and belongs in a new
# theme_id instead (taxonomy §25.1).
RETIRED_THEME_KEYS = {
    "cybersecurity_ot": "cybersecurity",   # 2026-09-02; THEME-08 unchanged
}

for _old, _new in RETIRED_THEME_KEYS.items():
    assert _old not in THEMES_BY_KEY, f"retired theme key {_old!r} is still live"
    assert _new in THEMES_BY_KEY, f"retired key {_old!r} points at unknown key {_new!r}"
del _old, _new

# How each buyer-side harness's own signal keys roll up into the shared spine. Kept as a
# mapping rather than by renaming the harnesses' keys, because those keys are written into
# committed, human-reviewed Observations and renaming them would break provenance for a
# cosmetic gain — the same reasoning that grandfathered H-FMCSA-01's name.
BUYER_SIGNAL_TO_THEME = {
    "warehouse_systems_automation_hiring": "warehouse_automation",
    "data_analytics_ai_hiring": "data_analytics_ai",
    "erp_core_systems_hiring": "erp_core_systems",
    "integration_engineering_hiring": "systems_integration",
    "digital_transformation_hiring": "digital_transformation_process",
    "transportation_systems_hiring": "transportation_fleet_systems",
    # 2026-09-02, Signal Advisor's authorisation (four conditions, all met in
    # harnesses/h_jobpost_01/classifier.py): the mapping covered 6 of 10 themes, so three
    # flipped themes and the new OT theme had no IC3 instrument at all. Keys that do not
    # land here change nothing downstream -- this map IS the instrument's reach.
    "cloud_infrastructure_hiring": "cloud_infrastructure_migration",
    "cybersecurity_hiring": "cybersecurity",
    "workforce_enablement_hiring": "workforce_enablement",
    "ot_modernization_hiring": "ot_modernization",
}

for _k, _v in BUYER_SIGNAL_TO_THEME.items():
    assert _v in THEMES_BY_KEY, f"buyer signal {_k!r} maps to unknown theme {_v!r}"
del _k, _v


def classify(text: str, min_hits: int = 1) -> dict[str, list[str]]:
    """Return {theme_key: [matched terms]} for every theme present in `text`."""
    out = {}
    for theme in THEMES:
        hits = theme.matches(text)
        if len(hits) >= min_hits:
            out[theme.key] = hits
    return out


# ---- the low-grade tier (session 9, 2026-09-03; Matthew's corroboration-gate policy) ----
#
# A gate that refuses a claim because the PATTERN is plausible and the REFERENT is right but
# the claim is not independently strong enough is a corroboration-strength gate. From
# 2026-09-03 such gates write at low grade instead of refusing: the row exists, marked so
# the review layer can sift it, rather than the extractor deciding. Identity gates (wrong
# company, dictionary-word token, index page, eponymous trap, homepage substitution, wrong
# speaker) are untouched: a referent error is excluded at extraction, not graded.
#
# A low-grade row is recognisable by construction: source_grade C, signal_strength
# weak_clue, confidence at or under LOW_GRADE_CONFIDENCE_MAX, and an evidence_excerpt that
# begins with LOW_GRADE_MARK naming the relaxed gate. Anything downstream can filter on any
# one of the four and get the same set.
LOW_GRADE = "C"
LOW_GRADE_CONFIDENCE = 0.3
LOW_GRADE_CONFIDENCE_MAX = 0.4
LOW_GRADE_MARK = "[low-grade:"


# A CONFOUND admission is a different thing from a corroboration-strength relaxation and
# carries a different marker so the methodology write-up cannot fold them together. The
# Wayback replatform case (W8) is the instance: the removals are real and the referent is
# right, but a competing explanation (a site migration) is affirmatively supported. The
# row is written so a reviewer can weigh the confound; it is not "weak but correct".
CONFOUND_MARK = "[low-grade: confound-admitted;"


def confound_excerpt(gate: str, excerpt: str) -> str:
    return f"{CONFOUND_MARK} {gate} relaxed 2026-09-03, review before use] {excerpt}"


def low_grade_excerpt(reason: str, excerpt: str) -> str:
    """Prefix an excerpt with the standard low-grade marker naming the relaxed gate."""
    return (f"{LOW_GRADE_MARK} {reason}; corroboration-strength gate relaxed 2026-09-03, "
            f"review before use] {excerpt}")


def classify_tiered(text: str, min_hits: int = 1) -> dict[str, tuple[list[str], str]]:
    """{theme_key: (hits, tier)} where tier is "strong" (admitted by `matches`) or "weak"
    (generic-tier hits only, which `matches` declines). The weak tier is what a harness
    writes at low grade under the 2026-09-03 policy; `classify` alone still returns only
    the strong tier, so a caller that has not opted in sees no change."""
    out = {}
    for theme in THEMES:
        hits = theme.matches(text)
        if len(hits) >= min_hits:
            out[theme.key] = (hits, "strong")
            continue
        refused = theme.refused(text)
        if refused:
            out[theme.key] = (refused, "weak")
    return out


def classify_refusals(text: str) -> dict[str, list[str]]:
    """{theme_key: [generic hits]} for every theme that saw only sub-threshold generic
    hits in `text`. The complement of `classify`: what was seen and declined."""
    out = {}
    for theme in THEMES:
        refused = theme.refused(text)
        if refused:
            out[theme.key] = refused
    return out


def theme_of_buyer_signal(signal_key: str) -> str | None:
    return BUYER_SIGNAL_TO_THEME.get(signal_key)
