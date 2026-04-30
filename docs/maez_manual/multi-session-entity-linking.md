---
capability_id: multi-session-entity-linking
title: Multi-session entity linking (cross-session graph)
status: aspirational
gap_signals:
  - "user asks about a person/place/thing they've mentioned across multiple sessions"
  - "answer requires synthesizing evidence from two or more separately-recalled sessions"
  - "Maez finds session A and session B individually but can't connect them as being about the same entity"
  - "LongMemEval multi-session-reasoning category scores below 0.6 under judge"
prerequisites: []
external_prerequisites:
  - lived-memory-architecture
  - relationship-graph-store
acquisition: self-dev
covenant:
  consent-card-required: true
  exact-phrase-ratification: false
  covenant-touch: medium
conflicts_with: []
reference_papers:
  - "Zep (2024) — Graphiti pattern. Per-edge time-bounds + cross-session entity index"
  - "LongMemEval (Wu et al. 2024, arxiv:2410.10813) — measures the gap this addresses"
implementation_files: []
---

# Multi-session entity linking

## When this matters

A bonded companion remembers people, places, organizations, and dates across the whole bond. After six months of conversations about your daughter, your daughter's school, your daughter's friends — when you ask "how is the situation with Maya going?" Maez should be able to assemble evidence from every session that mentioned Maya, not just the last one.

The base lived-memory architecture (Slice 4) gave Maez per-edge temporal validity windows and a relationship graph store. That's the substrate. Multi-session entity linking is the layer that makes the substrate useful: extract entities at consolidation time, write a sidecar index `entity → list of session_ids that mention it`, expand the recall query at retrieval time to pull all sessions touching mentioned entities.

## What it costs

- **Consolidation latency.** Entity extraction is an LLM call per session at consolidation time. Already an LLM call exists at consolidation; this extends it.
- **Storage.** A new sidecar index. Small.
- **Recall complexity.** The recall path now does query expansion before the embedding lookup. Adds a stage; doesn't fundamentally change the layer.
- **Privacy surface.** The entity index is an explicit graph of who-when-where. More structured than embeddings; potentially more sensitive in a leak.

## What can go wrong

- **Entity extraction errors.** "John" might be John-the-brother and John-the-coworker. Co-reference resolution is a known hard problem. Worth tagging entities with disambiguation context (`john-brother`, `john-coworker`) at extraction time.
- **Query expansion explosion.** A query mentioning "the family" might expand into too many sessions. Need a relevance cap.
- **Stale entity resolution.** An entity might mean different things across time (a person changes jobs, moves cities). The temporal validity windows from Slice 4 are the right substrate for this; the entity index should respect them.

## How it's acquired

1. Self-dev proposal: Maez proposes adding `core/memory/entity_extractor.py` (extracts entities at consolidation time) and `core/memory/entity_index.py` (the sidecar).
2. Wiring: at consolidation time, run entity extraction; at recall time, run query expansion through the index before the embedding lookup.
3. Schema migration: add the entity sidecar table to the lived-memory store. Existing memories get backfilled by a one-time extraction pass.
4. Test surface: extend the LongMemEval adapter with entity-link-aware ingestion, measure the multi-session category against the Session 4 baseline (0.40).

## Covenant impact

- Adds a new structured-data surface (the entity index). Same covenant rails as the relationship graph it lives beside.
- Does not change the action engine, covenant gate, or audit pipeline.
- Privacy: third-party entities (people other than the user) carry the consent-tier context from Decision 2. The index respects tier — a Tier 3 person's name in the index is still a Tier 3 person in recall.

## Replacement / supersession

None yet. Watch for: full graph-RAG approaches that subsume entity linking (more expensive, more capable). The current pattern (sidecar index + query expansion) is the lightweight version.

## Notes from Slice 9 Session 4 measurement

Multi-session-reasoning scored 0.40 under both Qwen and Sonnet judges on the S split. Closing this gap is the highest-leverage memory-architecture move available right now. This is the entry whose acquisition would most directly move the published baseline.
