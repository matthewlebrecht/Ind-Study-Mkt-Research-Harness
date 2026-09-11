# Week 3 Code Session Package — 2026-09-02

**Decision record.** Received 2026-09-02 and retained verbatim below, per the convention that
briefs and patch files are kept rather than summarised. Two independent pieces of work: Part A
a mechanical doc merge, Part B an approved schema delta.

**What was done against it, recorded here so the file is self-describing:**

- **Part A — HALTED as instructed, not completed.** Steps 1, 2 and 4 applied in full; step 3
  applied through §24 only. §25 and §26 are NOT appended. The input file's own section order
  runs 19, 20, 21, 22, 23, 24, **26, 25**, so appending in file order produces an out-of-order
  document and fails verification check 3, while reordering is an editorial decision Part A
  forbids resolving unattended. The question is with Matthew. Verification: checks 1, 2, 4, 5
  and 6 pass; check 3 returns §19–§24, sequential and gapless, short by exactly the two held
  sections.
- **Part B — built, except what depends on a table that does not exist.** `Harness_Sources`
  gained the five reach columns; `Signal_Types.status` gained §22.1's three new values;
  `core/topics.py` gained `theme_id`, `display_label`, `definition`, `definition_hash` and
  `buyer_detectable_since`. The `Company_State_History` columns could not be added: that sheet
  is the temporal/historical design and has not been built. Three of Part B's four invariants
  govern a derivation that writes it, so they are recorded as PENDING in
  `core/tests/test_schema_delta.py` rather than asserted vacuously.
- **`signal_advisor_theme_confirmation_2026-09-02.md`, cited in Part A's out-of-scope section,
  is not in the repo and was not supplied.** Not reconstructed. Nothing in this package depends
  on it — it is cited only as a decision input for Matthew.

---

Two independent pieces of work, bundled for one session. Do them in either order — they don't
depend on each other, but both are cleared to build with no open human decisions.

1. **Part A — Merge instructions** for `signal_taxonomy.md` (mechanical, Signal Advisor's own
   instructions — don't resolve ambiguity, stop and ask).
2. **Part B — Reconciled schema delta** (Harness Advisor's approved column additions for the
   temporal/historical schema, informed by Part A's §19–26).

---

# PART A — Merge Instructions — `signal_taxonomy.md`

For Claude Code. **Mechanical only.** Every editorial decision in this merge has already been
made; if something is ambiguous, stop and ask rather than resolving it.

Input: `taxonomy_merged_sections_2026-09-02.md`
Target: `signal_taxonomy.md`

## Do not touch

- **Family headings `## 1.` … `## 18.` and the seller-discourse section.** Numbers are frozen.
  Cross-references across the repo depend on them.
- **Signal type sub-IDs** (`1a`, `2c`, `9e`, `SD-b`, …). Frozen.
- **Family notes**, except the single amendment in step 4.
- **The existing dimension definitions in the Legend.** Append only.
- **The harness architecture tables, build order, H-EXECVOICE-01 design, upstream classifier
  section, and Harness Advisor Q&A.** Untouched by this merge.

Do not reflow, reformat, or "tidy" anything outside the four steps below.

## Step 1 — Replace the stale header callout

The document opens with a blockquote beginning `> **UNMERGED PATCH — read alongside this
file.**`. That block is now false. Replace the **entire blockquote** with:

```
> **PATCH MERGED 2026-09-02.** `taxonomy_patch_2026-08-31_rev2.md` and its v2/v3 revisions
> are folded in as §§19–26 below. Those patch files are superseded but retained as decision
> record — do not delete them.
>
> Merge policy going forward is **append-only**: families 1–18 and the seller-discourse
> section keep their numbers permanently, and new cross-cutting sections take the next
> available number from 26. Nothing is inserted mid-document, so no cross-reference breaks.
>
> Open: §20.3 carries a placeholder pending the definition of `signal_class`. §25 records
> theme-lock requirements; the `cybersecurity_ot` split decision is with Matthew and is not
> settled by this merge.
```

Leave the paragraph after it ("Decomposes each of the 18 evidence families…") unchanged.

## Step 2 — Append two Legend entries

At the end of the existing Legend bullet list, after the `**Priority**` bullet, append the two
bullets given under "Also required: two Legend entries" in the input file. Match the existing
bullet formatting exactly.

## Step 3 — Append §§19–26

Append everything from `## NEW §19 — Channels are not families` through the end of the input
file to the **end of `signal_taxonomy.md`**, after the "Questions for Harness Advisor" section.

Two edits while appending:

- Strip the leading `NEW ` from each heading. `## NEW §19 — Channels are not families` becomes
  `## §19 — Channels are not families`. The word was a patch marker.
- Do **not** carry over the input file's own header block (everything before the first
  `## NEW §19`). That is merge instruction, not document content.

## Step 4 — One amendment to the family 3 note

In the family 3 notes paragraph, locate:

```
3a is already built and already the project's single highest-value
family per Jacob's own framing
```

Append to the end of that same sentence's paragraph:

```
Presence-strong, absence-weak — H-JOBPOST-01's realized reach is `current_only` and its
coverage is bounded by client-side rendering, so this note does not license absence claims.
See §21.3.
```

Do not alter the Kenco sentence or anything else in that paragraph.

## Verification

Run these after merging. All must pass.

```bash
# 1. No stale patch-era section numbers remain in the appended range.
#    Expect ZERO hits from the appended sections.
awk '/^## §19/,0' signal_taxonomy.md | grep -nE '§(2\.4|4\.6|4\.7|7\.[0-9]|8|9|10)\b'

# 2. Family headings intact — expect exactly 18.
grep -cE '^## ([1-9]|1[0-8])\. ' signal_taxonomy.md

# 3. New sections present — expect 19 through 26, in order, no gaps.
grep -oE '^## §2?[0-9]+' signal_taxonomy.md

# 4. Patch marker fully stripped — expect ZERO.
grep -c '## NEW §' signal_taxonomy.md

# 5. Stale callout gone — expect ZERO.
grep -c 'UNMERGED PATCH' signal_taxonomy.md

# 6. Legend has seven dimensions — expect both new terms present.
grep -cE '^\- \*\*(Instrument class|Retrospective reach)\*\*' signal_taxonomy.md
```

Expected: (1) 0 · (2) 18 · (3) §19–§26 sequential · (4) 0 · (5) 0 · (6) 2

If check 1 returns hits, the renumbering is incomplete — **stop and report the line numbers**
rather than fixing them, since a wrong guess there is exactly the failure this merge was
structured to avoid.

## Explicitly out of scope for this merge

- Any change to `core/topics.py`. The theme findings are in
  `signal_advisor_theme_confirmation_2026-09-02.md` and are decision inputs for Matthew, not
  merge content.
- Adding cloud / security / workforce signal keys to H-JOBPOST-01. Recommended, not authorized.
- Resolving §20.3. Needs the `signal_class` definition, which nobody has supplied yet.
- Any `Signal_Types` registry write. The registry already carries `instrument_class`; the
  status-vocabulary expansion in §22.1 is a Harness Advisor change, not a doc merge.

---

# PART B — Reconciled Schema Delta: Signal Taxonomy §19–26

**Status:** Approved. Opaque theme IDs confirmed by Matthew. Nothing blocking — cleared to build.
**Sequencing:** After Rev 5, alongside the temporal/historical design. Nothing here changes
Rev 5's scope.

**Note on overlap with Part A:** Part A's merge is a doc-only change to `signal_taxonomy.md`
and explicitly does *not* touch `core/topics.py` or write to `Signal_Types`. Part B is the
schema work those same taxonomy sections require — they were designed together but are
separate deliverables. Do the doc merge (Part A) without waiting on the schema work (Part B),
and vice versa.

## Summary

| # | Point | Call |
|---|---|---|
| 1 | Nominal vs. realized reach | Two pairs on `Harness_Sources`, with a composition invariant and a stamping requirement. |
| 2 | Theme identifiers | **Opaque IDs (`THEME-04` etc.) — approved by Matthew, reverses the earlier frozen-string call.** |
| 3 | `Signal_Types.status` | Confirmed. Rollup filter, not write filter. |
| 4 | `buyer_detectable_since` | New column on the theme table. Not folded into reach gating. Composition order needs a third position. |

## The cross-cutting rule

Points 1, 2, and 4 are the same underlying issue: **vocabulary attributes that gate historical
interpretation and change over time.**

> **Effective-dating invariant.** Any attribute that gates historical interpretation must be
> effective-dated, and the derivation must stamp the value it composed against onto the
> derived row. It must never join the attribute live at query time.

Without this, every future change to a lookup silently rewrites what we believed — which is
precisely the failure the temporal schema exists to prevent, arriving through the lookup
tables instead of through the observation data.

## 1. `retrospective_reach` — nominal vs. realized

### Columns on `Harness_Sources`

| Column | Type | Notes |
|---|---|---|
| `nominal_reach` | enum | `current_only` \| `bounded` \| `archival` — what the source could theoretically speak to |
| `nominal_reach_months` | int, nullable | required when `nominal_reach = bounded` |
| `realized_reach` | enum | same domain — what we can actually access |
| `realized_reach_months` | int, nullable | required when `realized_reach = bounded` |
| `realized_reach_effective_from` | date | per the effective-dating invariant |

**Invariant:** reach gating in §21.3 composes on `realized_reach`. `nominal_reach` is never an
input to inference — it feeds an acquisition-backlog report only.

**Requirement for Code:** `min_retrospective_reach` on `Company_State_History` must be
**stamped with the realized value at derivation time**, not joined live against
`Harness_Sources`. A live join looks correct in every test and silently rewrites history the
first time an access gap closes.

## 2. Theme identifiers — opaque IDs (approved)

`Company_State_History` is append-only and immutable. A string rename would be either a
prohibited history rewrite or a permanent series split. Opaque IDs make rename touch only the
display label.

- `theme_id` (opaque, e.g. `THEME-04`), `display_label` (freely editable)
- `definition_hash` — hash of the written definition text, stamped onto each
  `Company_State_History` row at derivation time. Solves definition drift (separate problem
  from rename cost) without needing a full history table for a 9-value vocabulary. Same
  pattern as `gate_doc` content hash and `derivation_version`.

## 3. `Signal_Types.status` — confirmed

5-value vocabulary (`active` / `routing_only` / `out_of_theme` / `access_bounded` /
`reference`), Lookups-bound, min 50 rows per convention.

**Explicit boundary:** "only `active` rows enter any denominator" is a **rollup filter, not a
write filter**. Attempts against `access_bounded` or `out_of_theme` signal types still log to
`Attempts` — same principle as quarantined runs retaining their rows and being excluded at the
rollup layer by join, not by suppression at write. Implementing this as a write filter
silently understates the coverage denominator.

## 4. `buyer_detectable_since` — new column, not folded into reach

Reach is a property of the **source**. Detectability is a property of the **theme**. Folding
one into the other encodes a theme attribute on every source row and it will drift.

### Column (theme vocabulary table)

| Column | Type | Notes |
|---|---|---|
| `buyer_detectable_since` | date, nullable | null = never detectable; buckets before this date have no instrument capacity |

### Composition order — three stages, order is load-bearing

1. **Theme detectable in this bucket?** (`buyer_detectable_since` ≤ bucket start) — capacity gate
2. **Realized reach covers this bucket?** — capacity gate
3. **`instrument_class` licenses the inference?** — strength gate

### `not_instrumented` splits into two reasons

- `theme_not_detectable` — resolves by waiting; nothing to acquire
- `no_reach` — resolves by acquiring access; belongs on the acquisition backlog from point 1

**Immediate consequence:** the three themes that flipped `buyer_detectable=True` on
2026-08-31 land inside the 5-week evidence window. Backfill hits this on day one. Without this
column, backfill reads the pre-8/31 period as clean absence for those three themes — a
manufactured divergence baked into immutable history if it ships wrong.

## What Code needs to build

### Column additions

**`Harness_Sources`**
- `nominal_reach`, `nominal_reach_months`
- `realized_reach`, `realized_reach_months`, `realized_reach_effective_from`

**Theme vocabulary table**
- opaque `theme_id`, `display_label`
- `definition_hash`
- `buyer_detectable_since`

**`Signal_Types`**
- `status` (Lookups-bound, 5 values)

**`Company_State_History`**
- `min_retrospective_reach` — stamped, not joined
- `definition_hash` — stamped
- `not_instrumented` reason split: `theme_not_detectable` / `no_reach`

### Invariants to enforce mechanically

1. Composition reads `realized_reach`; `nominal_reach` is never an inference input.
2. Derivation stamps gating attribute values; never joins them live.
3. `Signal_Types.status` filters rollups, never writes.
4. Composition order: detectability → reach → instrument_class.

### Blocked pending human decision

None. All four points resolved 2026-09-02.
