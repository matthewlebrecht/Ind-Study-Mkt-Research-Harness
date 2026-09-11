# PIVOT UPDATE — Week 1 Checkpoint (read this before continuing any work)

This supersedes parts of `CLAUDE.md`. Don't discard that file — most of it (schema,
conventions, findings) still stands — but the priorities and the qualification approach
it describes have changed materially after a checkpoint meeting with Jacob (Talbot West).
Read this file fully before touching qualification or discovery-related code.

## What changed

**1. Discovery is dead. Qualification is now trivial.**

Jacob provided a CRM export of 100 pre-vetted companies: "Project Anvil — 100
Representative High-Potential Accounts" (already imported into `market_intel_db.xlsx`,
Companies sheet, `company_id` prefix `A0xx`, ranks 1-100). These already passed Talbot
West's own internal screening. **Do not build or run a discovery harness.** The elaborate
qualification procedure in `qualification_procedure.md` (hard gates + soft-gate scoring)
was built for an unknown universe of hundreds of companies — that problem no longer
exists. Jacob's actual qualification bar, verbatim: **"large and operationally complex"**
(his example of a clear disqualifier: a law firm).

Treat `qualification_procedure.md` as historical/reference, not the active spec. A
lightweight sanity check (does this company have real physical/operational complexity —
yes/no) is all that's needed going forward for any company outside the Anvil-100 list.
The 100 Anvil companies themselves are marked `qualified` at confidence 0.6 (Talbot West
vetted them via CRM, but we haven't independently verified size/industry per-company yet
— that verification can happen opportunistically as harnesses touch each company, not as
a dedicated pass).

**2. Industry scope is broader than originally documented.**

`source_lists.md` and `CLAUDE.md` describe the target industries as manufacturing,
supply-chain operations, and logistics. **The actual Anvil-100 list is much broader** —
heavy on construction/general contracting, plus trucking, energy, consumer goods, medical
devices, and food distribution/wholesale. "Anvil-fit" really just means large +
operationally complex, not tied to those three specific industries. Don't filter or
deprioritize evidence-family sources on the assumption the company universe is
manufacturing/logistics-only.

**3. The actual research focus has moved. This is the important one.**

Per Jacob: the "beef" of this project is now **signal identification, classification into
families, and evaluation of which signals are most valuable** — not qualification, not
discovery. This is now the central intellectual work of the entire project.

Signal examples Jacob gave directly: podcast clips, LinkedIn posts, articles, job
postings. Note these are **more granular than the 18 evidence families** already defined
in `source_lists.md`. A "signal" is closer to a specific, concrete content instance/format
within a family — e.g. within evidence family 15 (executive candor), "a LinkedIn post
authored by a named executive" and "a podcast appearance" are two distinct signal types
with different reliability and extraction requirements, even though both sit under the
same family.

**Harness granularity target: roughly one harness per signal type**, not one harness per
broad evidence family. This likely means each of the 18 families decomposes into several
concrete signal-level harnesses.

**4. A new upstream harness is worth considering: the signal-decision/classification
harness.** Something that looks at a piece of candidate content, classifies which signal
type it is, and judges whether it's worth extracting from — sitting upstream of the
per-signal extraction harnesses. This hasn't been designed yet. Worth discussing before
building it, since it shapes which of the many possible signal types actually get their
own extraction harness.

## New infrastructure to plan for (not urgent, but keep in mind)

- **Harness visualization**: eventually need a way to see the growing harness portfolio
  and how they relate/depend on each other. Not needed yet with only 2 harnesses built.
- **Audit/metadata system for AI failures**: beyond `review_status`
  (unreviewed/accepted/corrected/rejected), we need to capture *why* a harness couldn't
  find something or failed on a company — structured enough to mine for systematic
  improvement areas, not just free-text notes. Worth designing as a schema addition
  (possibly a new sheet, or new fields on Harness_Runs / Observations) once there's a
  concrete case to design against.
- **GitHub repo**: final deliverable will include a versioned code repo. If not already
  doing so, initialize git in the project folder now rather than retrofitting later.
- **Notion "word vomit" revision log**: a separate, informal Notion page (distinct from
  the polished weekly Progress Check pages) will capture raw decisions/reasoning as they
  happen. This lives on the Notion/chat side, not something Claude Code needs to write to
  directly — but flag anything decision-worthy in session summaries so it makes it there.

## What has NOT changed (still valid, keep using)

- The Observations schema and the requirement that every harness writes into it
- Data-confidence conventions (small discount for wide-but-centered stale/range figures)
- The AI/tech-hiring-signal rule (active hiring = active_transition, not proof of existing
  capability) — and the still-open Week 3 question about mixed signals (established
  platform + active hiring)
- FMCSA "NOT AUTHORIZED" calibration note for private fleets
- Idempotent harness writes, never overwrite human review
- Distinguishing source drift from genuine harness error
- The two harnesses already built (H-FMCSA-01, H-JOBPOST-01) and their observations —
  these don't need to be redone, they were run against the original 8 hand-picked pilot
  companies, which stay in the Companies sheet alongside the new 100 Anvil companies

## Immediate next steps

1. Do NOT build a discovery harness. Do NOT invest further in the soft-gate qualification
   scoring system.
2. Companies sheet now has 108 real candidate companies (8 original pilot + 100 Anvil).
   The Anvil companies have `industry_primary`, `employee_count`, `revenue_estimate` etc.
   left blank — pending, not broken. Fill in opportunistically as harnesses touch each
   company, rather than running a dedicated qualification/enrichment pass first.
3. Main task going forward: help design the signal taxonomy — decompose each of the 18
   evidence families into concrete signal types, and evaluate which are worth building
   extraction harnesses for. This is likely being discussed in a separate "Signal
   Decisions" Claude Project rather than in Claude Code directly — check with Matthew on
   where that design work is happening before duplicating it here.
4. Once specific signal types are prioritized, continue building one harness per signal
   (following the existing pattern from H-FMCSA-01 / H-JOBPOST-01: write to Observations,
   log a run in Harness_Runs, respect idempotency).
