"""
Posting -> modernization-signal classification.

Deliberately behind an interface. The rule classifier below runs today with no API key,
is fully deterministic, and every hit is traceable to a named pattern — which is what the
Week 4 reliability evaluation needs, because a disagreement can be argued about rather
than re-sampled from a model. `LLMClassifier` is sketched at the bottom: same interface,
so it drops in without the harness changing.

Signals are what the *role* implies about the company's operating posture. Hiring a WMS
integration engineer is evidence about warehouse systems; hiring a forklift operator is
not. Most of the value is in the title — a role that touches a system usually names it —
so titles alone are classified by default and descriptions are optional.

Per project convention 2, active hiring in these categories maps to
`organizational_state = active_transition`: it is evidence of a transition underway, NOT
proof of an established internal capability.

WHY THE TERM MODEL IS NOT A LIST OF REGEXES ANY MORE (v1.1, 2026-09-01)
----------------------------------------------------------------------
v1.0 ran against 7 pilot companies. Scaling to 108 changes what a loose pattern costs:
at Kenco only 5 of 467 postings were genuine modernization roles, so a term that fires on
1% of ordinary postings produces more false rows than the harness produces true ones, and
nobody can audit the result.

Probing v1.0's terms against realistic titles found seven false positives, every one an
instance of convention 16/31 — a single common token standing in for an identification:

    "BI-Weekly Payroll Clerk"          -> data/AI      (\bBI\b matches inside BI-Weekly)
    "API Technician - Active
       Pharmaceutical Ingredients"     -> integration  (API is a pharma term too)
    "Ai Weiwei Gallery Assistant"      -> data/AI      (case-insensitive \bAI\b)
    "Lean Beef Processing Associate"   -> transform.   (this universe has food distributors)
    "Oracle Card Dealer"               -> ERP
    "Innovation Center Tour Guide"     -> transform.
    "Transformation Coach - Wellness"  -> transform.

"bi-weekly" and pharmaceutical "API" are not exotic — they appear in ordinary postings at
enormous volume, and food distribution and medical devices are both real industries in
this universe. So three rules now govern every term:

1. AN ACRONYM IS MATCHED CASE-SENSITIVELY. Real postings capitalise WMS, TMS, ERP, API,
   BI, AI. Matching them case-insensitively is what turned "Ai Weiwei" into an AI hire and
   would turn any lowercase prose use into a system mention.
2. AN ORDINARY ENGLISH WORD NEEDS A QUALIFIER. `transformation`, `innovation`, `lean`,
   `oracle`, `conveyor` do not identify anything on their own (convention 31). Each now
   requires a second phrase in the same text before it counts.
3. A TERM CAN BE VETOED BY CONTEXT. "API" beside "pharmaceutical" is not an interface.

Convention 32 decides the shape of the fix: an unsupported claim gets an ADMISSION
threshold, not a strength downgrade. A posting whose only evidence is a common word does
not become a `weak_clue` row — it produces no row, because a false row still reaches a
reviewer and still enters every count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Term:
    """One matchable term, with the conditions under which it means anything.

    `rx`        the pattern itself.
    `sensitive` match case-sensitively. Used for acronyms, whose capitalisation is the
                thing that distinguishes the acronym from an ordinary word.
    `requires`  a second pattern that must ALSO appear somewhere in the posting text.
                This is convention 31 made mechanical: a common word is admitted only
                when the fuller phrase backs it.
    `blocks`    a pattern that vetoes this term outright when present.
    """

    rx: str
    sensitive: bool = False
    requires: str = ""
    blocks: str = ""
    # Session 10 item 7 (J13): for a VENDOR or ESTATE term (AWS, Azure, GCP, mainframe,
    # devops/SRE) the missing qualifier is a corroboration-strength gap, not an identity
    # one -- the term really is about this company's IT. Such a match is admitted at LOW
    # GRADE instead of refused. Dictionary-word terms (AI, BI, Oracle, lean, innovation,
    # transformation) keep the identity refusal: the bare token names something else.
    weak_if_unqualified: bool = False

    def compile(self):
        flags = 0 if self.sensitive else re.I
        return (re.compile(self.rx, flags),
                re.compile(self.requires, re.I) if self.requires else None,
                re.compile(self.blocks, re.I) if self.blocks else None)


@dataclass
class Signal:
    key: str            # becomes the observation topic
    label: str          # human phrasing used in observation_text
    terms: list         # any admitted term => posting carries this signal
    rationale: str      # why this role type is modernization evidence


# Qualifier phrases, named once so the intent is readable at each use site.
_SYSTEMS_ROLE = (r"\b(engineer|developer|analyst|architect|administrator|specialist|"
                 r"manager|director|lead|consultant|programmer|scientist)\b")
_PROCESS_ROLE = (r"\b(engineer|manager|director|lead|specialist|coordinator|analyst|"
                 r"consultant|black belt|green belt)\b")

# Ordered most-specific first; a posting can carry several signals.
SIGNALS = [
    Signal(
        key="warehouse_systems_automation_hiring",
        label="warehouse systems and automation",
        terms=[
            Term(r"\bWMS\b", sensitive=True), Term(r"\bWES\b", sensitive=True),
            Term(r"\bWCS\b", sensitive=True), Term(r"\bAS/RS\b", sensitive=True),
            Term(r"warehouse (management|control|execution) system"),
            Term(r"automation engineer"),
            Term(r"\brobotics?\b", requires=_SYSTEMS_ROLE + r"|automation|integration"),
            # A conveyor belt mechanic maintains equipment; a conveyor controls engineer
            # builds a system. v1.0 counted both as distribution-automation investment.
            Term(r"\bconveyor\b",
                 requires=r"\b(controls?|systems?|automation|integration|"
                          r"engineer|programm\w+|PLC)\b"),
            Term(r"material handling (engineer|systems)"),
            Term(r"automation (technician|specialist|manager)"),
        ],
        rationale="Roles that build or run warehouse systems indicate active investment in "
                  "distribution automation rather than routine warehouse staffing.",
    ),
    Signal(
        key="data_analytics_ai_hiring",
        label="data, analytics and AI",
        terms=[
            Term(r"\bdata (engineer|scientist|analyst|architect)\b"),
            Term(r"\banalytics\b"),
            Term(r"machine learning"),
            Term(r"\bML\b(?!C)", sensitive=True),
            Term(r"artificial intelligence"),
            # Case-sensitive, or "Ai Weiwei" and any lowercase "ai" in prose reads as an
            # AI programme. Even capitalised, a bare AI needs a role or a companion term:
            # "AI" appears in airport codes, product names and initialisms.
            Term(r"\bAI\b", sensitive=True,
                 requires=_SYSTEMS_ROLE + r"|machine learning|artificial intelligence|"
                          r"\b(model|automation|generative|agentic)\b"),
            Term(r"business intelligence"),
            # \bBI\b matched inside "BI-Weekly", which is in a large fraction of all
            # payroll and hourly postings. Requiring a systems role plus vetoing the
            # hyphenated-adverb senses is what makes the acronym usable at all.
            Term(r"\bBI\b", sensitive=True, requires=_SYSTEMS_ROLE + r"|dashboard|report",
                 blocks=r"\bbi-?(weekly|monthly|lingual|annual)\b"),
            Term(r"data (warehouse|platform|governance)"),
            Term(r"\bPower BI\b"), Term(r"\bTableau\b"),
        ],
        rationale="Building an internal data function is the most direct hiring signal of a "
                  "modernization program.",
    ),
    Signal(
        key="erp_core_systems_hiring",
        label="ERP and core business systems",
        terms=[
            Term(r"\bERP\b", sensitive=True), Term(r"\bSAP\b", sensitive=True),
            Term(r"\bNetSuite\b"), Term(r"\bDynamics 365\b"),
            Term(r"\bJDE\b", sensitive=True), Term(r"\bJD Edwards\b"),
            # Vendor names need a boundary on BOTH sides. Bare "Infor" matches inside
            # "Information", which classified every IT manager as an ERP hire -- the
            # founding case of convention 16.
            Term(r"\bInfor\b"), Term(r"\bEpicor\b"),
            # And a boundary is not enough when the vendor name is also an ordinary noun.
            # "Oracle Card Dealer" is a real posting shape; convention 31 says the common
            # token has to be backed by the fuller phrase.
            Term(r"\bOracle\b",
                 requires=_SYSTEMS_ROLE + r"|\b(ERP|EBS|database|DBA|financials|cloud|"
                          r"apps|fusion|PL/SQL)\b"),
            Term(r"\b(systems|application) analyst\b"),
            Term(r"\bbusiness systems\b"),
        ],
        rationale="ERP and core-systems roles indicate a platform migration or an "
                  "implementation in progress.",
    ),
    Signal(
        key="integration_engineering_hiring",
        label="systems integration",
        terms=[
            Term(r"\bEDI\b", sensitive=True),
            # In pharmaceuticals and medical devices -- both in this universe -- API is
            # the Active Pharmaceutical Ingredient. Same three letters, opposite meaning.
            Term(r"\bAPI\b", sensitive=True,
                 blocks=r"\b(active pharmaceutical|pharmaceutical ingredient|"
                        r"\bAPI manufacturing\b)"),
            Term(r"integration (engineer|developer|specialist|analyst)"),
            Term(r"middleware"), Term(r"\bETL\b", sensitive=True),
            Term(r"solutions architect"),
        ],
        rationale="Integration roles indicate systems that do not yet talk to each other — a "
                  "legacy-estate signal as much as a modernization one.",
    ),
    Signal(
        key="digital_transformation_hiring",
        label="digital transformation and process engineering",
        terms=[
            Term(r"digital transformation"),
            # Bare "transformation" reached a wellness coach, and bare "innovation" a tour
            # guide. Both now need the organisational sense spelled out.
            Term(r"\btransformation\b",
                 requires=r"\b(digital|business|operational|enterprise|IT|technology|"
                          r"supply chain)\b|" + _PROCESS_ROLE),
            Term(r"modernization"),
            Term(r"continuous improvement"),
            # NOT "process engineer". core/topics.py's digital_transformation_process
            # theme lists process improvement / excellence / reengineering / automation --
            # every one of them naming a change PROGRAMME -- and pointedly omits the bare
            # engineering title. v1.0 added `engineer` to the alternation and the pilot
            # showed what that costs: Merit Medical's "Process Engineer" read as
            # modernization evidence, when a process engineer at a medical-device
            # manufacturer is an ordinary production role. In a universe of manufacturers
            # and contractors that term fires nearly everywhere and means nothing.
            Term(r"process (improvement|excellence|reengineering|automation)"),
            # "Lean Beef Processing Associate" is why this one is qualified. This universe
            # contains food distributors, and lean is an ordinary adjective there.
            Term(r"\blean\b",
                 requires=r"\b(manufacturing|six sigma|process|continuous improvement|"
                          r"kaizen|operations|transformation)\b|" + _PROCESS_ROLE,
                 blocks=r"\blean (beef|protein|meat|pork|poultry|ground|cuisine|body)\b"),
            Term(r"six sigma"),
            Term(r"\binnovation\b",
                 requires=r"\b(director|head|vp|chief|manager|lead|engineer|"
                          r"technology|digital|product|process)\b"),
        ],
        rationale="Explicit transformation and process-engineering roles show the company "
                  "naming operational change as a program.",
    ),
    Signal(
        key="transportation_systems_hiring",
        label="transportation and fleet systems",
        terms=[
            Term(r"\bTMS\b", sensitive=True),
            Term(r"transportation management system"), Term(r"telematics"),
            Term(r"fleet (systems|technology|analyst)"),
            Term(r"route (optimization|planning)"),
            Term(r"dispatch (systems|technology)"),
        ],
        rationale="TMS and telematics roles indicate investment in transportation execution "
                  "systems rather than additional drivers or dispatchers.",
    ),
    # ---- 2026-09-02: four keys authorised by Signal Advisor (pattern-fix brief §4) ----
    #
    # These give an IC3 instrument to the three themes that were IC1-only (cloud,
    # cybersecurity, workforce enablement) and launch `ot_modernization` with one. Four
    # conditions, all binding: (1) PRESENCE ONLY until the careers-page readability
    # denominator is accepted -- scripts/careers_readability.py measures it, 14 of 108 on
    # the last run -- so no absence claim rests on these keys; (2) each key lands in
    # core/topics.py BUYER_SIGNAL_TO_THEME, or it changes nothing downstream; (3) specific-
    # tier terms from the start -- a bare cloud-vendor name is NOT a migration signal, nearly
    # every IT requisition names one; (4) buyer-side patterns stay here, per harness.
    Signal(
        key="cloud_infrastructure_hiring",
        label="cloud migration and infrastructure modernization",
        terms=[
            Term(r"cloud (migration|modernization|transformation|infrastructure|platform|"
                 r"architect|engineer|operations)"),
            Term(r"\b(cloud|infrastructure|platform) (engineer|architect|administrator)\b"),
            Term(r"\blift[- ]and[- ]shift\b"),
            Term(r"data cent(er|re) (migration|consolidation|exit)"),
            # A vendor name is a requisition commonplace. It counts only beside migration
            # or legacy-estate language -- the condition Signal Advisor set explicitly.
            Term(r"\b(AWS|Azure|GCP)\b", sensitive=True, weak_if_unqualified=True,
                 requires=r"\b(migrat\w+|moderni[sz]\w+|legacy|lift[- ]and[- ]shift|"
                          r"re-?platform\w*|data cent(er|re)|infrastructure|cloud "
                          r"(engineer|architect))\b"),
            Term(r"\bmainframe\b", weak_if_unqualified=True,
                 requires=r"\b(migrat\w+|moderni[sz]\w+|decommission\w*|retire\w*|"
                          r"replace\w*)\b"),
            Term(r"\b(devops|site reliability|SRE)\b", weak_if_unqualified=True,
                 requires=r"\b(cloud|AWS|Azure|GCP|kubernetes|terraform|infrastructure)\b"),
        ],
        rationale="Cloud and infrastructure engineering roles indicate a migration off an "
                  "owned estate, or the operation of one already moved -- either way a "
                  "modernization programme rather than routine IT staffing.",
    ),
    Signal(
        key="cybersecurity_hiring",
        label="cybersecurity",
        terms=[
            Term(r"\bcyber ?security\b"), Term(r"\binformation security\b"),
            Term(r"\binfosec\b"), Term(r"\bCISO\b", sensitive=True),
            Term(r"\b(SOC|SIEM)\b", sensitive=True,
                 requires=r"\b(analyst|engineer|security|operations)\b"),
            Term(r"\b(IT|OT|network|cloud|application) security\b"),
            # "Security Officer" at a distribution centre guards a gate. The word needs
            # the digital sense spelled out, and the physical senses are vetoed outright.
            Term(r"\bsecurity (engineer|analyst|architect|administrator|operations)\b",
                 requires=r"\b(cyber|information|network|IT|OT|cloud|application|"
                          r"vulnerabilit\w+|threat|incident|SIEM|firewall)\b",
                 blocks=r"\b(security (guard|officer)|loss prevention|physical security|"
                        r"armed)\b"),
            Term(r"\b(CMMC|NIST)\b", sensitive=True,
                 requires=r"\b(compliance|security|analyst|engineer|assessor)\b"),
            Term(r"\bzero trust\b"), Term(r"\bpenetration test\w*\b"),
            Term(r"\bvulnerability management\b"),
        ],
        rationale="Security roles indicate a company staffing a posture it previously "
                  "outsourced or did not have -- almost never announced, so a requisition "
                  "is the least-guarded instrument for this theme.",
    ),
    Signal(
        key="workforce_enablement_hiring",
        label="workforce enablement and frontline technology",
        terms=[
            Term(r"\bfrontline (technology|enablement|systems|app)"),
            Term(r"\bdeskless\b"),
            Term(r"\bworkforce management (system|analyst|specialist|administrator|"
                 r"technology)\b"),
            Term(r"\bWFM\b", sensitive=True, requires=_SYSTEMS_ROLE),
            # Kronos/UKG/Dayforce are workforce-management platforms; a role that
            # administers one is a frontline-technology role, an ordinary payroll clerk
            # who uses one is not.
            Term(r"\b(Kronos|UKG|Dayforce)\b",
                 requires=r"\b(analyst|administrator|specialist|implementation|"
                          r"configuration|engineer|lead)\b"),
            Term(r"\bLMS\b", sensitive=True, requires=_SYSTEMS_ROLE),
            Term(r"\blearning (technology|systems|platform)\b"),
            Term(r"\blabou?r (management|standards) (system|engineer|analyst)\b"),
            Term(r"\b(training|learning) (and|&) (adoption|enablement)\b"),
            Term(r"\b(user|technology) adoption\b",
                 requires=r"\b(manager|lead|specialist|analyst|program)\b"),
        ],
        rationale="Roles that build or administer frontline and workforce technology "
                  "indicate investment in the tools deskless staff actually use, which a "
                  "press release flatters and a review site complains about.",
    ),
    Signal(
        key="ot_modernization_hiring",
        label="OT modernization and industrial control systems",
        terms=[
            Term(r"\b(SCADA|PLC|HMI|DCS)\b", sensitive=True),
            # First dry run of this key (2026-09-02) admitted "Quality Control Technician"
            # and "QA Document Control Specialist II" -- convention 16 on its first outing.
            # The industrial title is PLURAL ("Controls Engineer") or names the system
            # ("Control Systems Engineer"); the singular with a qualifier is quality,
            # document, inventory or pest control, and those are vetoed by name.
            Term(r"\bcontrols (engineer|technician|programmer|specialist|systems)\b",
                 blocks=r"\b(quality|document|inventory|pest|traffic|loss|cost|infection|"
                        r"access|version|revenue) controls?\b"),
            Term(r"\bcontrol systems? (engineer|technician|programmer|specialist|integrator)\b"),
            Term(r"\bindustrial (controls|automation) (engineer|technician|specialist)\b"),
            Term(r"\binstrumentation (and|&) controls?\b"), Term(r"\bI&C\b", sensitive=True),
            Term(r"\bprogrammable logic controller"),
            Term(r"\bdistributed control system"),
            Term(r"\bprocess control (engineer|technician|specialist)\b"),
            Term(r"\b(process|data) historian\b"),
            Term(r"\bMES\b", sensitive=True, requires=_SYSTEMS_ROLE),
            Term(r"\bOT\b", sensitive=True,
                 requires=r"\b(network|infrastructure|moderni[sz]\w+|engineer|systems)\b"),
        ],
        rationale="Controls, SCADA and PLC roles are the most specific requisition terms in "
                  "the whole vocabulary: they name the plant-floor systems being built or "
                  "replaced, and are essentially unconfusable with anything else.",
    ),
]

# A leadership title turns "we are hiring for this" into "we have staffed a mandate for it".
LEADERSHIP = re.compile(
    r"\b(chief|c[toix]o|vp|vice president|head of|director|senior director|"
    r"sr\.? director|manager of)\b", re.I)

# Roles that merely *mention* a system while being ordinary operational hiring.
#
# Widened for the full-universe run. The pilot set was three logistics companies; the
# Anvil-100 adds construction, energy, food distribution and medical devices, each with
# its own vocabulary of ordinary roles that name systems in passing. A recruiter posting
# is the sharpest case: it describes the systems team without being one.
EXCLUSIONS = re.compile(
    r"\b(forklift|driver|warehouse (associate|clerk|worker|selector)|picker|packer|"
    r"loader|janitor|technician trainee|cdl|"
    r"intern|internship|apprentice|"
    r"(technical |it )?recruiter|talent acquisition|"
    r"sales (representative|associate|rep)\b|account executive|"
    r"custodian|housekeep\w+|food service|line cook|"
    r"machine operator|assembler|welder|electrician apprentice)\b", re.I)


@dataclass
class Classification:
    signals: list          # signal keys
    matched_terms: dict    # signal key -> list of matched substrings
    is_leadership: bool
    rejected: dict = field(default_factory=dict)   # term -> why it was not admitted
    # Session 10 (J13): signals carried only by a weak_if_unqualified term with its
    # qualifier absent. Written at low grade by the harness, never counted as strong.
    weak_signals: list = field(default_factory=list)
    weak_terms: dict = field(default_factory=dict)


class RuleClassifier:
    """Deterministic keyword/pattern classifier. Every hit traceable to a named term.

    Refusals are returned alongside hits rather than discarded. A term that matched but
    was not admitted is the interesting case when auditing precision -- it is the
    difference between "the harness never saw this" and "the harness saw it and decided
    it did not count" (convention 7, and the reason convention 39 exists).
    """

    name = "rules"
    version = "v1.3"

    def __init__(self, signals: list | None = None):
        self.signals = signals or SIGNALS
        self._compiled = {
            s.key: [(t, *t.compile()) for t in s.terms] for s in self.signals
        }

    def classify(self, text: str) -> Classification:
        hits, terms, rejected = [], {}, {}
        weak_hits, weak_terms = [], {}
        if not text.strip():
            return Classification([], {}, False)
        # An ordinary operational role is excluded even if it names a system, so
        # "Warehouse Associate - WMS experience a plus" does not read as a systems hire.
        excluded = EXCLUSIONS.search(text)
        for signal in self.signals:
            matched = []
            weak_matched = []
            for term, rx, req, blk in self._compiled[signal.key]:
                m = rx.search(text)
                if not m:
                    continue
                if blk and blk.search(text):
                    rejected[m.group(0)] = f"vetoed by context: {term.blocks}"
                    continue
                if req and not req.search(text):
                    if term.weak_if_unqualified and not excluded:
                        weak_matched.append(m.group(0))
                        rejected[m.group(0)] = ("vendor/estate term without migration "
                                                "language; admitted at LOW GRADE (J13)")
                        continue
                    rejected[m.group(0)] = (
                        "a single common token is not an identification "
                        "(convention 31); needs: " + term.requires)
                    continue
                matched.append(m.group(0))
            if matched and not excluded:
                hits.append(signal.key)
                terms[signal.key] = sorted(set(matched))
            elif matched:
                for t in matched:
                    rejected[t] = f"operational role excluded: {excluded.group(0)}"
            if weak_matched and signal.key not in hits:
                weak_hits.append(signal.key)
                weak_terms[signal.key] = sorted(set(weak_matched))
        return Classification(hits, terms, bool(LEADERSHIP.search(text)), rejected,
                              weak_signals=weak_hits, weak_terms=weak_terms)


class LLMClassifier:
    """Same interface, model-backed. Not wired up — no API key is configured.

    To enable: set ANTHROPIC_API_KEY, implement `classify()` to send the posting text plus
    the SIGNALS definitions above and return the same Classification shape, and pass
    `--classifier llm`. Keep the signal keys identical so observations stay comparable
    across classifier versions, and bump the harness version so Harness_Runs records which
    classifier produced which rows.
    """

    name = "llm"
    version = "v0.0-unimplemented"

    def classify(self, text: str) -> Classification:  # pragma: no cover
        raise NotImplementedError(
            "LLM classifier not implemented: no ANTHROPIC_API_KEY configured. "
            "Run with --classifier rules.")


def get_classifier(name: str):
    return {"rules": RuleClassifier, "llm": LLMClassifier}[name]()


SIGNALS_BY_KEY = {s.key: s for s in SIGNALS}
