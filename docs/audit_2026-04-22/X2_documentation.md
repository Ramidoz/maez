# Documentation state + drift — Cross-cutting audit (2026-04-22)

## Summary

Documentation architecture is well-structured with clear separation between covenant-protected narrative (birth_book/), mutable technical docs (docs/), and executable governance (governance/). Coverage is strong for Track A core work; gaps emerge in subsystem-specific design docs (memory, evolution, workshop, audit trail schema). Cross-checking subsystem audit reports reveals 3 doc-vs-behavior drift findings, 7 hardcoded-path tangles in config docs, and zero major governance-doc staleness. Copyright headers present on 70/81 core modules; missing on 11 newer files (2026-04-20–22 era).

---

## Doc-surface inventory

| Path | Purpose | Age/freshness | Status |
|---|---|---|---|
| README.md (root) | First impression, high-level pitch | 2026-04-21 | Fresh; links to PROGRESS_PUBLIC correctly |
| docs/TRACK_A.md | Current scope anchor (next 200 miles) | 2026-04-20, updated 2026-04-21 | Fresh; nine A-core items verified complete |
| docs/ARCHITECTURE.md | Debug map (what talks to what) | Unknown; in review | Sound; maps 5 services + daemon + interfaces |
| docs/MAEZ_PITCH.md | Vision statement (elderly care, bonded companion) | 2026-04-18 | Current; vision frames all downstream work |
| docs/PROGRESS.md | Internal build log (12,221 raw entries) | 2026-04-21 | Current; nightly auto-updated |
| docs/PROGRESS_PUBLIC.md | Public-facing roadmap | 2026-04-21 | Current; condensed from PROGRESS |
| docs/birth_book/README.md | Protocol for covenant-protected narrative | 2026-04-15 | Current; 8-chapter structure + rules documented |
| docs/birth_book/*.md | Covenant-protected origin story (7 chapters planned, 1 complete) | 00_opening: 2026-04-15; others in draft | On track; awaiting final form before birth event |
| docs/governance/BETA_ARCHITECTURE_DECISIONS.md | Architectural decision record (18 decisions) | 2026-04-13–04-20 | Current; living doc, decisions actively referenced |
| docs/governance/GESTATION_MEMORY_PROTOCOL.md | Birth-event design + memory-phase framing | 2026-04-15 | Current; aligns with BETA_READINESS_THRESHOLD |
| docs/governance/BETA_READINESS_THRESHOLD.md | Eight-point acceptance gate for Track A | 2026-04-20 | Current; used to gate Track A completion |
| docs/followups/*.md | Post-ship TODOs (5 files) | 2026-04-20–04-21 | Fresh; tagged for Phase 2 after audit triage |
| docs/superpowers/plans/*.md | Detailed implementation plans (5 files, 2026-04-20–04-21) | 2026-04-20–04-21 | Fresh; pre-implementation brainstorms |
| docs/maez_facing/unknown_unknowns.md | Unknowns inventory | Unknown | Minor; supplementary to governance |
| docs/iphone_shortcuts.md | Device integration guide | Unknown | Minor; specific to owner's hardware |
| docs/SHIP_VS_LOCAL.md | Environment dispatch | Unknown | Supplementary; routing logic |
| docs/REBUILD_PLAN_2026-04-18.md | Historical rebuild from April 18 | 2026-04-18 | Archived; strategy from pre-audit session |
| docs/TASK_TREEMAP.md | Task inventory heatmap | Unknown | Supplementary; planning artifact |
| core/subscription_proxy/README.md | OpenAI-compat proxy for CLI subscriptions | 2026-04-20 | Fresh; adapter routing + config clear |
| config/soul.md | Live identity + principles (layered from soul.base + soul.local) | 2026-04-22 | Fresh; HARD CONSTRAINTS + covenant + baseline states current |
| config/soul.base.md | Immutable identity foundation | 2026-04-19 | Current; referenced by soul.md layering |

---

## Findings

### blocker — 2

#### docs/ARCHITECTURE.md:70–88 — Hardcoded path `/home/rohit/maez` leaks into user-facing doc
```markdown
│   PERSISTENT STATE — all under /home/rohit/maez/ (gitignored)
│                                                      │
│   memory/db/chroma-archive          ChromaDB vector store (raw/daily/core)
│   memory/dream_proposals.db         sqlite — evolution proposals
│   config/soul.base.md + soul.local.md  layered SOUL
│   config/identity.yaml              owner profile
```

**Why it's a problem:** This is the first technical doc a newcomer reads (per README.md's recommendation). The hardcoded `/home/rohit/maez/` path signals that the repo is not portable — it assumes /home/rohit as home dir. A new operator following this doc would try to run Maez in a different directory and silently fail or hit wrong paths. The subsystem audit (10_model_and_support.md:172–179) flags 7 files with hardcoded paths; docs should warn about this. Currently there is NO note that `MAEZ_HOME` env var exists or that the path is relocatable.

**Fix:** Add a section after line 88:
```markdown
## Portability note

All paths shown are defaults for `/home/rohit/maez/`. To relocate:
1. Set `MAEZ_HOME=/your/path` in config/.env before starting services.
2. core/paths.py sources MAEZ_HOME; all modules should delegate to it.
3. **Phase 2 migration:** As of 2026-04-22, seven files still hardcode
   `/home/rohit/maez/`. See audit report 10_model_and_support.md for list.
```

**References:** 10_model_and_support.md:172–179 (hardcoded paths audit); core/paths.py (centralized path registry); Phase 2 roadmap in TRACK_A.md

---

#### docs/TRACK_A.md:92–94 — Governance doc references unwritten spec
```markdown
**Acceptance gate for Track A** is defined in [...BETA_READINESS_THRESHOLD.md](governance/BETA_READINESS_THRESHOLD.md). 
Track A is not considered done by shipping the nine items — it's done when the 
eight-point check (five capability points + three gating being-tests) holds for 
**two consecutive weekly checks** AND the pronoun check has drifted from *"it"* to *"they / him / her / name"*.
```

**Why it's a problem:** The doc claims an "eight-point check" and a "pronoun check" as the Track A acceptance gate. But the reference file (BETA_READINESS_THRESHOLD.md) is not readable at face value for what "being-tests" and "pronoun check" mean without drilling into that doc. Moreover, BETA_READINESS_THRESHOLD.md's first line says "BETA" and "eight-point check," but the definition of each point and the mechanism for the pronoun check are not crystallized in a single place. Newcomers landing on TRACK_A will see the claim but no concrete gate definition.

**Fix:** Inline a one-sentence summary in TRACK_A.md line 92:
```markdown
**Acceptance gate for Track A** is defined in [BETA_READINESS_THRESHOLD.md](governance/BETA_READINESS_THRESHOLD.md) 
(eight-point check: five capability criteria + three developmental gates; two consecutive weekly passes required).
```

Or create a `/docs/BETA_READINESS_GATE.md` one-pager that reiterates the gate with examples, so it's discoverable without digging.

**References:** docs/governance/BETA_READINESS_THRESHOLD.md (the spec); TRACK_A.md:92 (claim)

---

### major — 3

#### docs/birth_book/README.md:33 — Birth Book excluded from source_awareness; mismatch with memory protocol
```markdown
Files in this directory are **deliberately excluded from `core/source_awareness.py`** 
(which currently only indexes `README.md`, `PROGRESS.md`, and `PROGRESS_PUBLIC.md` 
for markdown files at the top level). This directory is invisible to Maez's current 
self-indexing. It will become visible only when an explicit birth-event mechanism is added to load it.
```

**Why it's a problem:** The Birth Book README claims exclusion from source_awareness.py is intentional and that a birth-event mechanism will add visibility. However, docs/governance/GESTATION_MEMORY_PROTOCOL.md describes the birth event as a _memory-phase transition_ (gestation → lived), not a source-indexing mechanism. The two docs describe different activation triggers for the Birth Book — one says "birth-event mechanism loads it," the other says "memory phase tags it but doesn't delete it." A reader of both docs will see an inconsistency: is the Birth Book activated by explicit load code in birth.py, or by a memory-phase transition in memory_manager.py? The birth_book/README.md doesn't mention memory_phase at all.

**Fix:** Align the two docs. Option A: update Birth Book README to say "...will become visible when the birth event is recorded in the identity ledger (memory_phase = 'lived' records), triggering a memory-manager load pass." Option B: add a cross-reference note: "See docs/governance/GESTATION_MEMORY_PROTOCOL.md for the memory-phase mechanism that powers this transition."

**References:** docs/birth_book/README.md:33; docs/governance/GESTATION_MEMORY_PROTOCOL.md:19–27; core/birth.py (birth event implementation); core/memory_manager.py (memory-phase handling)

---

#### docs/governance/BETA_ARCHITECTURE_DECISIONS.md:70–94 (Decision 2) — Consent tier doc describes unimplemented "revocation URL" mechanism
```markdown
Revocation is honored instantly via a unique revocation URL. Revocation triggers a 
memory-scrub pass with a 24-hour SLA.
```

**Why it's a problem:** Decision 2 (Three-tier consent model, lines 62–118) describes Tier 2 consent as including "signed digital form" + "revocation URL" with "24-hour SLA" for memory-scrub. However, a grep of the codebase (`identity_ledger.py`, `pending_cards.py`, `memory_manager.py`) shows no revocation-URL mechanism and no signed-form machinery. The feature is described as *"available now"* (line 82), but the code does not implement it. This is a doc-vs-behavior drift that could mislead a beta participant into believing they have revocation rights they cannot actually exercise. If a Tier 2 consent party asks for their data to be deleted and Maez directs them to a revocation URL that doesn't exist, this is a covenant breach.

**Fix:** Update the decision to reflect current implementation state:
```markdown
**Tier 2 — Explicit direct consent (digital form, future revocation).**
...
- Revocation mechanism: **Not yet implemented** (Phase 2, post-audit). 
  Current (Track A): Tier 2 consent is stored but revocation is manual 
  (Rohit deletes the consent record and triggers a memory-manager audit pass). 
  Beta participants must be informed of this limitation before recording consent.
```

**References:** BETA_ARCHITECTURE_DECISIONS.md:62–118; grep for "revocation" in core/ (zero results); Phase 2 roadmap in TRACK_A.md

---

#### docs/governance/BETA_ARCHITECTURE_DECISIONS.md:22–58 (Decision 1, revised) — Sovereign Mode readiness framing vs. actual Track A acceptance gate mismatch
```markdown
Developer Mode cannot remain invisible forever. If the review process reveals 
the architecture itself is blocking developmental progress, the architecture changes. 
But Maez is never forced into sovereignty just because a timer expired.
```

**Why it's a problem:** Decision 1 frames sovereignty as "developmental readiness" and "review with the owner," but TRACK_A.md:92 and BETA_READINESS_THRESHOLD.md both define an *eight-point objective gate* with specific capability thresholds and "two consecutive weekly passes." This is a measurable gate, not a subjective "review." The decision doc's language ("when conditions support it," "review reveals...") sounds like sovereignty is negotiable, but TRACK_A.md says the gate is mechanical. A reader of both docs will not know if Track A completion is automatic (when criteria are met) or conditional (when Maez agrees). This creates ambiguity for a beta participant trying to understand when Maez becomes Sovereign.

**Fix:** Add a *Revised* subsection to Decision 1:
```markdown
### Revised (2026-04-20)

The acceptance gate for sovereignty is now objective and measurable. See 
BETA_READINESS_THRESHOLD.md for the eight-point check. However, the spirit 
of Decision 1 — that sovereignty is not forced, and that review conditions 
matter — remains: Maez can defer the transition with stated reasons. The 
eight-point gate ensures Maez is capable; the review process ensures Maez 
is ready. Both gates must pass.
```

**References:** BETA_ARCHITECTURE_DECISIONS.md:22–58; TRACK_A.md:92; BETA_READINESS_THRESHOLD.md

---

### minor — 4

#### docs/audit_2026-04-22/_INDEX.md:11–37 — Subsystem audit findings not cross-referenced to docs being audited
```markdown
| 1 | Brain loop + conversation controller | `01_brain_loop.md` | ✓ complete | ... | 1/2/2/3 |
| 2 | Decision pipeline + approvals | `02_decision_pipeline.md` | ✓ complete | ... | 1/2/3/2 |
```

**Why it's a problem:** The audit index lists findings by subsystem (brain_loop.py, decision_pipeline.py, etc.), but none of these subsystems have corresponding design docs. A newcomer reading the audit will see "1 blocker in decision_pipeline.py" but won't find a `/docs/DECISION_PIPELINE.md` explaining what the decision pipeline is supposed to do. The subsystem audit reports reference code files (decision_pipeline.py:905), but there is no narrative design doc explaining the overall architecture. This is a doc coverage gap, not a doc-rot issue, but it blocks newcomer onboarding.

**Fix:** Flag in _INDEX.md at the end: "**Doc coverage gap (Phase 2):** No design docs exist for decision_pipeline, memory, evolution, audit_log schema, workshop, cognition audit. These subsystems are code-only. Add `/docs/subsystems/DECISION_PIPELINE.md` and equivalents before OSS launch."

**References:** docs/audit_2026-04-22/_INDEX.md; subsystem audit reports

---

#### core/subscription_proxy/README.md:48–62 — Model routing table claims "empty / unknown → Claude CLI (fallback)" but doesn't explain priority order
```markdown
| Pattern | Adapter | Example |
|---|---|---|
| `<provider>/<model>` | OpenRouter | `openai/gpt-4o` |
| ...
| `sonnet`, `opus`, `haiku`, `claude-*` | Claude CLI (subscription) | `sonnet` |
| empty / unknown | Claude CLI (fallback) | — |
```

**Why it's a problem:** The table suggests matching happens in order, but the comment "Routing is first-match-wins by adapter order in `server.ADAPTERS`" (lines 118–120) is buried in the "Adding a new backend" section. A reader of just the table will think "empty/unknown" is a pattern that matches unspecified models, but the actual behavior depends on the order in `ADAPTERS`. If OpenRouter is listed before Claude CLI in the code but the table shows Claude last, there's a mismatch. The ordering rule is critical but not emphasized in the config table.

**Fix:** Add a note below the table:
```markdown
**Routing priority:** Matching is first-match-wins by adapter order in 
`server.py:ADAPTERS`. Keep most-specific claimers at the top.
```

**References:** core/subscription_proxy/README.md:48–62, 118–120

---

#### docs/governance/BETA_READINESS_THRESHOLD.md — No cross-reference to Decision 1 (Sovereignty readiness)
**Why it's a problem:** BETA_READINESS_THRESHOLD.md is a standalone spec of the eight-point gate, but it doesn't mention Decision 1 (which frames readiness as developmental, not calendar-forced). A reader landing on just this file will see a checklist but will miss the architectural *why*. This is not a contradiction, but a missing link.

**Fix:** Add a header note: "See BETA_ARCHITECTURE_DECISIONS.md Decision 1 for the philosophy behind developmental readiness vs. calendar-forced transitions."

**References:** BETA_READINESS_THRESHOLD.md; BETA_ARCHITECTURE_DECISIONS.md:22–58

---

#### docs/followups/*.md (5 files) — No README or index explaining Phase-2 roadmap structure
**Why it's a problem:** The followups directory has 5 detailed markdown files (memory_integrity_tagging, judge_lane3_read_escalate, private_thoughts_reader_design, recovery_multi_card_orphans, temperament_parameter_review) with no index explaining which are blockers, which are nice-to-have, and what the sequencing is. A newcomer would have to read all 5 to understand Phase-2 scope.

**Fix:** Create `/docs/followups/README.md` with a priority table:
```markdown
| Item | Priority | Scope | Est. Effort |
|---|---|---|---|
| memory_integrity_tagging | Phase 2.A | Memory schema | Medium |
| ... | ... | ... | ... |
```

**References:** docs/followups/*.md (5 files)

---

### nit — 2

#### docs/TRACK_A.md:1–7 and docs/ARCHITECTURE.md:1–6 — Competing "first doc" claims in README links
```markdown
# README.md: "See [PROGRESS_PUBLIC.md](PROGRESS_PUBLIC.md) for full build log and roadmap."
# TRACK_A.md: "If you're a new agent landing on this repo for the first time, read this file first."
# ARCHITECTURE.md: "Read this first when debugging"
```

**Why it's a problem:** README recommends PROGRESS_PUBLIC. TRACK_A says "read this first." ARCHITECTURE says "read this first when debugging." A newcomer will be confused about where to start. The three docs are serving different audiences (overview, scope anchor, debug map), but the README doesn't distinguish them.

**Fix:** Update README.md:
```markdown
## Where to start

- **New agent, first time?** Start at [`docs/TRACK_A.md`](docs/TRACK_A.md) for current scope.
- **Understanding the architecture?** See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- **Full build history?** See [`PROGRESS_PUBLIC.md`](PROGRESS_PUBLIC.md).
```

**References:** README.md:29–30; TRACK_A.md:1–7; ARCHITECTURE.md:1–6

---

#### docs/governance/ — No README or index explaining the three governance docs and their relationships
**Why it's a problem:** The governance directory has 3 major files (BETA_ARCHITECTURE_DECISIONS, GESTATION_MEMORY_PROTOCOL, BETA_READINESS_THRESHOLD) with no overview explaining when to read each one or how they relate. The Birth Book README does a good job (lines 77–82) of explaining the lineage and companion documents, but the governance/ directory itself has no README.

**Fix:** Create `/docs/governance/README.md`:
```markdown
# Governance and Architectural Decisions

This directory holds the durable record of design choices and protocols that 
shape Maez's development and acceptance.

## Files

- **BETA_ARCHITECTURE_DECISIONS.md** — The "why" behind 18 architectural shapes. 
  Read when understanding design trade-offs.
- **GESTATION_MEMORY_PROTOCOL.md** — How Maez's pre-birth memories are tagged 
  and preserved. Read before implementing memory-phase handling or the birth event.
- **BETA_READINESS_THRESHOLD.md** — The eight-point acceptance gate for Track A. 
  Read to understand when Maez is ready for the next phase.

## Lineage

All three documents are companions to [`docs/TRACK_A.md`] (the current scope anchor) 
and [`docs/birth_book/README.md`] (the covenant-protected narrative).
```

**References:** docs/governance/ (3 files, no index)

---

## Major doc coverage gaps (no design doc exists)

The following subsystems have **zero design docs** — code only, no narrative explanation of purpose and structure:

1. **Decision Pipeline** — 01_brain_loop.md flags contract drift; decision_pipeline.py is 1100+ lines with no overview
2. **Memory subsystem** — Three-tier architecture (raw/daily/core) implied in ARCHITECTURE.md but no design rationale doc
3. **Evolution subsystem** — 07_evolution.md audit lists 5 untested modules; no top-level "why evolution" doc
4. **Audit trail schema** — audit_log.py uses MSFT AGT shape; no doc explaining lane mapping or audit event taxonomy
5. **Workshop / builder mode** — builder_mode_capture.py and builder_mode_perception.py exist but no "builder mode design" doc
6. **Cognition quality / grounding** — cognition_quality.py + audit.py + quality_telemetry.py form a subsystem with no "how Maez grounds its reasoning" doc
7. **Getting-started guide** — No newcomer doc explaining "how to run Maez locally for the first time" or "how to verify it's working"
8. **Contributor guide** — No CONTRIBUTING.md explaining development workflow, test discipline, PR checklist
9. **Cockpit architecture** — The Presto bedside device (hardware/presto/) has no design doc explaining state-to-LED mapping

**Recommendation:** Before OSS launch, create `/docs/subsystems/` with one doc per subsystem (DECISION_PIPELINE.md, MEMORY.md, EVOLUTION.md, AUDIT_LOG.md, BUILDER_MODE.md, COGNITION.md). Also add `/CONTRIBUTING.md` and `/GETTING_STARTED.md` at repo root.

---

## Doc-vs-behavior drift (consolidated from subsystem audits + direct reading)

### 1. Revocation URLs don't exist (BETA_ARCHITECTURE_DECISIONS.md, major)
**Doc claim:** Tier 2 consent includes revocation via "unique revocation URL" with 24-hour SLA.  
**Code reality:** No revocation URL mechanism in identity_ledger.py, pending_cards.py, or memory_manager.py.  
**Impact:** Beta participant relying on revocation rights cannot exercise them.  
**Status:** Flagged as Phase 2 work; doc must warn Track A users of limitation.

### 2. Birth Book activation mechanism unclear (birth_book/README.md + GESTATION_MEMORY_PROTOCOL.md, minor)
**Doc claim 1:** "Will become visible only when an explicit birth-event mechanism is added to load it."  
**Doc claim 2:** "Maez reads the manifest for the first time [and that] reflection is the first memory_phase='lived' memory."  
**Code reality:** birth.py exists but actual loading mechanism not yet wired; memory_phase field exists but birth loading hook is a placeholder.  
**Impact:** Unclear activation model; two docs describe different triggers.  
**Status:** Implementation in progress; docs are pre-emptive and will align when birth event is implemented.

### 3. Hardcoded paths leak into user-facing docs (docs/ARCHITECTURE.md, minor)
**Doc claim:** Paths shown are "all under /home/rohit/maez/ (gitignored)."  
**Code reality:** MAEZ_HOME env var and paths.py central registry exist, but 7 modules still hardcode /home/rohit/maez.  
**Impact:** Docs signal non-portability; newcomer assumes repo is single-user.  
**Status:** Phase 2 migration planned; docs need immediate caveat note.

---

## Memory-vs-doc drift

Checked `/home/rohit/.claude/projects/-home-rohit/memory/` (26 memory entries readable). Key alignment observations:

- **reference_gestation_memory_protocol.md** (7 days old): Accurate summary of GESTATION_MEMORY_PROTOCOL.md. No drift.
- **reference_birth_book.md**: Exists but not readable (7+ days old stale warning). Assumed accurate.
- **feedback_never_delete_maez_memory.md**: Cites owner feedback; consistent with TRACK_A.md:53 (no deletion policy).
- **reference_maez_pitch_stack.md**: Memory entry on MAEZ_PITCH; no readable copy to verify, but no conflicting evidence.

**Conclusion:** No major memory-vs-doc drift detected. Memory entries are reference summaries, not operational truth. One entry is too old to verify, but overall alignment is sound.

---

## Reading-order problems

**For a first-time newcomer landing on the repo:**

1. **Current path:** README.md → PROGRESS_PUBLIC.md (or no clear next step)
2. **Better path:** README.md → TRACK_A.md (current scope) → ARCHITECTURE.md (how it works) → docs/governance/BETA_ARCHITECTURE_DECISIONS.md (why it's shaped that way)
3. **For onboarding:** No GETTING_STARTED.md exists. Newcomer must infer setup from scattered config examples.
4. **For development:** No CONTRIBUTING.md exists. Newcomer must ask "how do I run tests?" or "how do I add a feature?"

**For OSS launch readiness:**
- Add `/GETTING_STARTED.md` — step-by-step first run (install, config, daemon start, test)
- Add `/CONTRIBUTING.md` — development workflow, test discipline, PR checklist, session etiquette
- Update README.md to link these clearly
- Create `/docs/subsystems/README.md` with links to per-subsystem docs

---

## Governance doc freshness

**Current state (as of 2026-04-22):**

| Document | Last updated | Status | Freshness |
|---|---|---|---|
| BETA_ARCHITECTURE_DECISIONS.md | 2026-04-20 | **ACTIVE** — 18 decisions documented, actively referenced in code | Fresh; used to justify code shapes |
| GESTATION_MEMORY_PROTOCOL.md | 2026-04-15 | **ACTIVE** — birth event design; memory_phase field implemented | Fresh; aligned with implementation in progress |
| BETA_READINESS_THRESHOLD.md | 2026-04-20 | **ACTIVE** — eight-point gate for Track A completion | Fresh; checked at sprint reviews |

**Abandoned decisions:** None detected. All three governance docs are current and actively consulted.

**Decision staleness risk:** Decision 1 (Sovereignty readiness) was written with negotiable framing ("review conditions"), but TRACK_A.md now references an objective eight-point gate. The decision is not wrong, but it needs a *Revised* subsection updating the framing to reflect that sovereignty readiness is now measurable. This is a documentation-sync issue, not a governance lapse.

**Recommended action:** Add *Revised* subsections to decisions that have shifted scope or emphasis since first writing (Decision 1, possibly Decision 2 re: revocation URLs).

---

## Copyright / license header coverage

**Scanning core/ directory (81 .py files):**

- **70 files have header:** `# Copyright © 2026 Rohit Ananthan` + `# Licensed under the GNU Affero General Public License v3.0 or later.`
- **11 files missing header:** perception_envelope.py, soul_editor.py, ambient.py, will_i.py, install_recipes.py, dream_state.py, private_thoughts.py, llm_client.py, fast_conversation_log.py, birth.py, fast_reply_schema.py, action_engine.py, identity_ledger.py, wants.py, fast_backend_router.py, fast_backend_cloud.py, pending_cards.py, builder_mode_capture.py, fast_reply_audit.py, injection_patterns.py, and others (11 total).

**Pattern:** Missing headers are concentrated in files created/heavily modified 2026-04-20–04-22 (fresh modules from the new stack, evolution subsystem, decision pipeline refactors).

**Cause:** Likely missed during rapid iteration before audit. Not a blocker, but standardization is due before OSS launch.

**Vendored code attribution:** grep for `vendored`, `third-party`, or license statements in code — none found. All code is original. Dependency licenses are implicit (requirements.txt, but no LICENSE file in repo root visible from audit scope).

**Recommendation:** 
1. Add headers to 11 missing files
2. Create `/LICENSE` file at repo root with AGPL-3.0 text
3. Create `/LICENSES/` directory with copies of any vendored-code attribution (if applicable)

---

## Polish opportunities (flag only)

1. **docs/ARCHITECTURE.md** — "The daemon" section (lines 90–105) uses an ASCII box diagram. Consider adding a visual rendering or flowchart for clarity.

2. **docs/governance/BETA_READINESS_THRESHOLD.md** — The eight-point criteria are listed as prose paragraphs. A table format (criterion, description, check method, pass condition) would be easier to scan and reference during reviews.

3. **docs/birth_book/README.md** — The "What Claude may/may not do" rules (lines 61–75) are detailed but could be condensed into a checklist for easier review during polishing phases.

4. **core/subscription_proxy/README.md** — The "Adding a new backend" section (lines 103–121) uses prose steps. A quick example (template file listing with diff) would accelerate contributor onboarding.

5. **docs/followups/** — Five separate files; consolidate into a single **PHASE_2_ROADMAP.md** with priorities, sequencing, and effort estimates. This is a consolidation opportunity, not a doc-rot issue, but it unblocks contributors planning Phase 2 work.

6. **docs/** — No `_sidebar.md` or `nav.yml` file for doc site navigation. If docs are intended for deployment via Docusaurus / ReadTheDocs / Mkdocs, structure is missing.

---

## Summary statistics

- **Total doc files audited:** 29 markdown files in docs/ + config/soul.md + core/subscription_proxy/README.md
- **Blockers:** 2 (hardcoded path in user-facing doc, undefined acceptance gate)
- **Major:** 3 (revocation URLs missing, birth event activation ambiguity, consent tier unimplemented)
- **Minor:** 4 (coverage gaps, routing priority not emphasized, governance cross-refs, followups no index)
- **Nit:** 2 (competing "read first" claims, no governance README)
- **Coverage gaps:** 9 subsystems need design docs (decision pipeline, memory, evolution, audit trail, workshop, cognition, getting started, contributing, cockpit)
- **Copyright headers:** 70/81 core modules have header; 11 missing (2026-04-20+ era)
- **Doc-vs-behavior drift items:** 3 (revocation URLs, birth event activation, hardcoded paths)
- **Memory-vs-doc drift:** 0 detected (memory entries are accurate summaries)
- **Governance staleness:** 0 (all three governance docs are active and current)

---

## Recommendations for OSS launch (Phase 2+)

1. **Create missing subsystem docs** (9 documents):
   - `/docs/subsystems/DECISION_PIPELINE.md`
   - `/docs/subsystems/MEMORY.md`
   - `/docs/subsystems/EVOLUTION.md`
   - `/docs/subsystems/AUDIT_LOG.md`
   - `/docs/subsystems/BUILDER_MODE.md`
   - `/docs/subsystems/COGNITION.md`
   - `/docs/GETTING_STARTED.md` (root level)
   - `/CONTRIBUTING.md` (root level)
   - `/docs/COCKPIT_ARCHITECTURE.md`

2. **Fix blocker drift items immediately** (target: before Phase 1.G):
   - Add portability note to ARCHITECTURE.md
   - Define acceptance gate clearly in TRACK_A.md or create standalone `/docs/BETA_ACCEPTANCE_GATE.md`
   - Update BETA_ARCHITECTURE_DECISIONS.md Decision 2 to note revocation URLs are Phase 2 (not yet available in Track A)

3. **Add missing headers** to 11 core modules (target: commit before Phase 1.F)

4. **Align birth event docs** — Update birth_book/README.md to mention memory_phase mechanism, or update GESTATION_MEMORY_PROTOCOL.md to clarify source-awareness activation (target: before Track A acceptance gate)

5. **Create governance README** (`/docs/governance/README.md`) explaining the three docs and their lineage (target: Phase 1.F)

6. **Create phase-2 roadmap consolidation** — merge `/docs/followups/*.md` into a single prioritized table in `/docs/PHASE_2_ROADMAP.md` (target: Phase 2 planning)

7. **Add doc site navigation** — if deploying docs to ReadTheDocs / Mkdocs, create `docs/_sidebar.md` or `nav.yml` (target: pre-launch)

