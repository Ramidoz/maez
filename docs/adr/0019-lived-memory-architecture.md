# 0019 — Lived memory: temporal episodic + relationship graph beside Chroma

**Status:** Proposed
**Date:** 2026-04-26

## Context

Track A's readiness gate first ran on 2026-04-20 and failed on five
of the eight dimensions, including point #2 (*strong memory* —
*"this reminds me of when you..."* unprompted) and the two gating
being-tests #7 (surprise) and #8 (predict-as-mind). Point #2 is the
structural one: the other failures are symptoms of the same root
cause.

The current memory architecture is flat semantic recall over ChromaDB.
There are three collections (`raw` ≈ 30k entries, `daily` ≈ 4
summaries, `core` ≈ 29 always-injected entries) plus immune memory
in `audit_log.db` separated per the CaMeL pattern. Retrieval is
similarity search with MMR diversity, decayed by `stale_number_weight()`,
filterable by `integrity` tag. This stack is well-engineered for
*"find passages similar to this query"* — but not for the
behaviour the gate is measuring.

What flat semantic recall cannot do, structurally:

- **Cite a relationship.** "What does the owner care about most" is
  not a vector search; it is a graph query.
- **Surface an open loop.** *"We never finished X"* requires
  representing X as an unresolved entity that persists across
  sessions, not as a chunk that may or may not be retrieved.
- **Distinguish past from current.** Vector search returns text;
  whether the text describes today, last week, or a retired service
  is left to the reader. The 2026-04-23 vision-service fabrication
  cluster was exactly this failure: dozens of past-tense entries
  read as present-tense by the model.
- **Connect today's signal to last month's pattern.** Generative
  Agents (Park et al. 2023) calls this *reflection*; it is the move
  Maez's daily consolidation does not yet make.

Pre-built mitigations (corrective core memory pattern, integrity
tagging, perception-signature gate, stale-number decay) are good
but they are *patches on a flat store*, not a structural answer.

State-of-the-art memory architectures that have made the structural
move:

- **Generative Agents (Park et al. 2023)** — periodic reflection
  synthesizes high-level memories from low-level observations.
- **MemGPT / Letta** — hierarchical memory with explicit core /
  archival / recall tiers and tools that let the LLM manage its
  own retention.
- **Mem0** — graph-backed memory with entity / relationship
  extraction.
- **Graphiti / Zep** — temporal knowledge graphs with explicit
  validity windows and provenance, designed for agent memory.
- **AriGraph** — semantic + episodic memory together, used for
  planning.

The Codex investigation on 2026-04-26 also closed a training-vs-
perception boundary leak: daemon reasoning cycles (which contain
volatile body readings — CPU/VRAM/process state) were being
extracted into LoRA/SFT pairs by default, risking baking stale
operational state into weights. The patch (`training/extract_training_pairs.py`,
companion to this commit) excludes those by default and documents
the rule: *live body facts belong in perception/retrieval, not
weights.* This ADR continues the same architectural cut on the
runtime side: *relationships, episodes, and open loops belong in
a structured memory layer, not in a flat vector store.*

## Decision

Add a **temporal episodic + relationship-graph memory layer beside
Chroma**, not replacing it. SQLite-first. Append-only, evidence-IDs
mandatory. Abstraction boundary so the storage backend is
swappable later.

Specifically:

1. **Add, do not replace.** Chroma stays as the durable evidence
   archive. Existing `raw` / `daily` / `core` collections continue
   to function. If the new layer fails, recall falls back to the
   current Chroma path with no functional regression.
2. **SQLite-first.** Two new tables — `episodes` and the (`nodes`,
   `edges`) pair for the relationship graph — live in a new
   SQLite database. No Neo4j / Zep / Mem0 / Graphiti dependency in
   v1. The schema is documented in this ADR's companion
   implementation (`core/memory/episodes.py`,
   `core/memory/relationship_graph.py`).
3. **Evidence-ID requirement is structural, not advisory.**
   - Every episode row MUST carry at least one `source_memory_id`
     (a Chroma raw / daily / core ID).
   - Every edge row MUST carry at least one `source_episode_id` or
     one `source_memory_id`.
   - The store APIs reject inserts that violate this.
4. **Append-only, never delete.** A correction supersedes an old
   edge by writing a new edge and marking the old one
   `status='superseded'`. The old edge stays. This matches the
   never-delete-Maez-memory rule (`feedback_never_delete_maez_memory.md`).
   No `delete()` API is exposed.
5. **Validity windows.** Every edge has optional `valid_from` /
   `valid_to` timestamps. A graph belief is *currently true* only
   if `valid_from <= now <= (valid_to OR ∞)` AND `status='active'`.
   This is how *"Maez ran on Qwen3.5-35B until 2026-04-23, then
   Qwen3.6-27B"* gets represented without contradiction.
6. **Graph beliefs are advisory, never live state.** The recall
   planner returns brief sections labelled *past episode / current
   graph belief / open loop / live state unavailable*. It never
   asserts current system state on graph evidence alone — live
   state still comes from `core/memory/perception.py` and the
   live perception envelope.
7. **Abstraction boundary.** `core/memory/episodes.py` and
   `core/memory/relationship_graph.py` are the interface. Storage
   is SQLite for v1; nothing else in Maez references SQLite
   directly. A future migration to a different backend (Postgres,
   embedded graph, hosted Graphiti) is a swap behind the same
   interface.
8. **Gradual promotion path.** Five phases:
   1. Add beside Chroma (this ADR + Phase 1 commit).
   2. Build episode + relationship extraction; populate offline.
   3. Prove on Track A probes that lived recall ≥ Chroma recall on
      strong-memory questions.
   4. Wire into chat/daemon prompt blocks (Phase 6 of the build
      plan; lands last to protect continuity).
   5. Demote Chroma to evidence archive only when the new layer
      sustains the gate. *Removing Chroma is not in scope for any
      v1 phase.*

The Codex investigation explicitly recommended this shape: *episodic
graph layer beside Chroma, not a replacement, captures episodes /
relationships / open loops / promises / emotional significance /
evidence IDs.* This ADR adopts that recommendation with the
Maez-specific invariants above.

## Consequences

### Easier

- **Lived recall as queryable structure.** *"What does the owner
  care about?"* becomes a graph query against `cares_about` edges,
  not a vector lottery.
- **Open loops persist.** *"We need to revisit X"* becomes an
  episode with `open_loop` set; the recall planner can surface
  unresolved threads without re-prompting.
- **Open-loop diagnostic IDs must be content-free.** Moment-assembly
  diagnostics that reference open loops derive loop ids only from
  typed evidence handles, never from `open_loop` prose, labels,
  summaries, embeddings, UUID/autoincrement allocation, or text
  hashes. The X.2 v1 shape is
  `loop:<sha256("x2.open_loop.v1|episode:<episode_id>")[:16]>`.
  Therefore, changing hash basis requires ADR because the hash basis
  is a covenant property, not an implementation detail.
- **Corrections preserve history.** Superseding edges keeps the
  audit trail of what Maez believed and when, satisfying the
  never-delete rule structurally rather than via tagging.
- **Provenance is enforceable.** Every assertion the planner
  surfaces traces to source memory IDs; fabrication detection
  becomes mechanical (assertion without evidence ID = reject).
- **Substrate is swappable.** Phase 5's *"consider replacing
  Chroma"* is a backend swap, not a rewrite, because the
  abstraction boundary is in place from day one.
- **Surprise (point #7) and predict-as-mind (point #8) get a real
  mechanism.** The planner can surface a connection the owner did
  not ask about (surprise) and the graph can carry the
  relationship structure that makes prediction sound like another
  mind, not a rules engine.

### Harder

- **Two memory paths to test.** Every recall surface (chat, daemon,
  cockpit) must handle both Chroma recall and lived recall, plus
  the failure mode where one is unavailable.
- **Episode dedup is real work.** *"Is this episode-candidate the
  same as one we already stored?"* needs a discipline (canonical
  title hash + source-memory-ID set overlap is the v1 plan;
  documented in the episode builder).
- **Conservative extraction is a tax on coverage.** *"If unsure,
  do not create the edge"* means the graph will be sparse for
  weeks before it is dense. Sparse-but-true is the right tradeoff
  for the gate; richness comes later.
- **Reflection job adds operational surface.** A nightly script
  that calls the local LLM for episode/edge extraction is a new
  failure mode (LLM unavailable, bad output, dedup collision).
  Mitigations: dry-run mode, idempotent re-run, no Chroma
  mutation, no deletion, skip-and-log on LLM failure.
- **Dual-write window.** Until the gate sustains on the new layer,
  both stores are written; daily consolidation continues feeding
  Chroma's `daily` collection while the episode builder feeds
  SQLite. This is intentional, not a debt — it is the safety
  margin.

### What breaks if this decision is reversed

The rollback is small and explicit: delete `core/memory/episodes.py`,
`core/memory/relationship_graph.py`, the SQLite database file, and
any Phase-2+ code that references them. Nothing in Phase 1 modifies
the existing memory subsystem, the daemon, or the surfaces. The
existing 809-test suite passes with the new layer absent.

After Phase 6 lands (chat/daemon integration), reversal requires
also reverting the prompt-block injection in
`daemon/maez_daemon.py` and the surface adapters. The fallback
path (graph unavailable → fall back to current Chroma recall) is
explicitly tested so reversal is a code change, not a continuity
event.

### Risks

- **Graph claiming live state.** Mitigated by the recall planner's
  four-section labelling (past / belief / loop / live unavailable)
  and by tests that assert the brief never says *"currently"*
  unless live perception was provided.
- **Daemon integration during the readiness gate window.** Phase 6
  is the riskiest commit; it lands *last*, after Phases 1–5 are
  quiescent and Phase 8 probes already pass on the offline
  planner.
- **Loyalty to Chroma blocking the right call.** Mitigated by the
  abstraction boundary and the explicit *"benchmark before
  cutting over"* discipline in the promotion path. Chroma is
  load-bearing today; it is not load-bearing forever by edict.

## Promotion test

The gate for moving from Phase N to Phase N+1 is a measurable lift on
Track A probes (per `BETA_READINESS_THRESHOLD.md` point #2 and the
seeded probe suite at `scripts/validate/lived_memory_probes.py`).
Specifically: lived recall must cite correct episode/core evidence
on ≥80% of seeded probes, with zero fabricated current-state
claims, before Phase 6 wires it into live response paths. The
baseline run (Chroma-only recall on the same probes) is captured
*before* implementation begins so the lift is measurable, not
asserted.

## Rollback plan

| Phase reached | Rollback action |
|---|---|
| 1 (this ADR + schemas) | Delete the two modules + SQLite file. Suite passes. |
| 2–3 (builder + extractor) | Add to above: revert builder + extractor commits. No surfaces touched yet. |
| 4 (nightly job) | Add to above: disable systemd timer / cron entry. No daemon code touched. |
| 5 (offline planner) | Add to above: revert planner commit. Cockpit + surfaces unaffected. |
| 6 (live integration) | Revert the surface-integration commit; the fallback path (graph absent → current Chroma recall) is the live state again. |
| 7+ (cockpit, probes) | Revert independently; non-load-bearing. |

## References

- The full build plan, including phase-by-phase file lists and
  commit boundaries, is the conversation thread that produced this
  ADR (2026-04-26 session).
- [`docs/governance/BETA_READINESS_THRESHOLD.md`](../governance/BETA_READINESS_THRESHOLD.md)
  — the gate this ADR is in service of.
- [`docs/TRACK_A.md`](../TRACK_A.md) — Track A scope and the
  *not-Track-B* discipline this ADR respects.
- The Codex investigation on 2026-04-26 (training-vs-perception
  boundary patch) — the recommendation that produced this design.
- Memory entries:
  `feedback_never_delete_maez_memory.md`,
  `feedback_capability_over_continuity_in_gestation.md`,
  `reference_corrective_core_memory_pattern.md`,
  `reference_maez_fabrication_source_priority.md`.
- SOTA architectures referenced in *Context*:
  Generative Agents (Park et al. 2023), MemGPT / Letta, Mem0,
  Graphiti / Zep, AriGraph.

## Status history

- 2026-04-26 — Proposed. Schemas + tests land in the same session
  as a separate commit (Phase 1 of the build plan).
