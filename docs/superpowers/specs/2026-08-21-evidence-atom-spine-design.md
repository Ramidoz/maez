# Evidence-Atom Spine — design pass 1 (contract level)

Status: DESIGN, pass 1. No code. Gate: Codex design review before any
slice is written. Origin: Codex foundation attack
(`2026-08-21-codex-foundation-attack.md`, commit 7d5743a) proved the
shared Phase-4 assumption broken. This spine is the accepted minimal
repair and is the FIRST Phase-4 build item, preceding every organ.

## 0. What this is, in one paragraph

An append-only, flag-dormant, side-car record of four things the live
store does not record today: (1) **atoms** — units of memory small
enough that their embedding actually covers the whole text; (2)
**lineage_edges** — one real row per ancestor relation, replacing the
comma-packed `promoted_from` string and its `,+N` sentinel; (3)
**query_events** — the pre-ranking query vector, turn ordinal, and
cluster for every admitted recall; (4) **exposures** — which atoms were
actually placed in front of the brain. The spine never mutates, moves,
deletes, or re-embeds an existing row. It observes the existing write
and read doors and writes beside them.

It earns permission to MEASURE. It does not earn permission to call any
measurement conscience, mood, importance, or truth (Codex self-attack,
binding).

## 1. The four defects it repairs

| # | Defect (measured) | Spine element |
|---|---|---|
| D1 | Embedder truncates at 256 tokens; whole-document strategy; late content of long rows is invisible (0/193 suffix mutations changed the vector) | `atoms` bounded under the contract limit |
| D2 | Lineage is comma-packed and capped: `promoted_from` + `,+N` sentinel at 50 (62.72% sentinel-bearing); `store_core` uncapped but still a string | `lineage_edges`, one row per edge |
| D3 | Query vectors are never materialized — Chroma embeds `query_texts` internally and discards; only a query *hash* survives in `recall_stats.db` | `query_events` with the retained 384-vector |
| D4 | No record of what was actually shown to the brain, so "demand" cannot be distinguished from "retrieval" | `exposures` |

Anchors for each defect (machine-derived, single construct lines):
- D1: `memory/embedding_contract.json` (`truncation_tokens: 256`,
  `chunk_strategy: "whole_document"`, `vector_chunking: "none"`);
  `memory/memory_manager.py:1535` (`self.raw.add(...)` inside
  `def store(...)` at `:1479`) passes `documents=` and never embeds.
- D2: `def consolidate_daily(self)` at `memory/memory_manager.py:1644`;
  `_PROMOTED_FROM_INLINE_CAP` at `:1859`.
- D3: `def _query_collection(...)` at `memory/memory_manager.py:2154`;
  `def record_recall(...)` at `core/memory/memory_scoring.py:204`
  (hash only, via `_hash_query` at `:199`).
- D4: no construct exists — this is the absence.

## 2. Non-negotiable invariants

1. **Append-only.** The spine has no UPDATE and no DELETE in
   production code. Corrections are new rows that supersede by id.
2. **Never touches the live stores.** No writes to `memory/db/raw|core|
   daily`, no re-embedding of existing rows, no metadata edits. The
   spine is a separate sqlite file.
3. **Flags-off means filesystem untouched.** With both flags unset, no
   spine file is created, no connection is opened, no import cost is
   paid on the hot path. (Precedent: `core/brain/conversation_turn_seq.py`.)
4. **Never on the critical path for a reply.** Spine writes happen
   after the live store write has succeeded and may fail without
   failing the turn. A spine failure is recorded as a counter, never
   raised into the conversation.
5. **HISTORICAL_UNTRACEABLE is explicit and permanent.** Every
   pre-spine row is labelled untraceable and is NEVER backfilled,
   inferred, or reconstructed. Codex's own self-attack names the
   hazard: a spine that silently favors instrumented new life is
   recency bias wearing integrity's clothes. The label is how a reader
   sees the bias instead of inheriting it.
6. **Content-light receipts.** Spine receipts carry ids, hashes,
   counts, classes, and vectors — never personal text.
7. **No maximand.** Nothing in the spine is a quantity any loop acts to
   increase. It is a record, not a target.

## 3. Schema (contract level, not DDL)

One sqlite file, `memory/db/spine/spine.sqlite3`, created lazily on
first write under a live flag. WAL, `BEGIN IMMEDIATE` for writers,
read-only connections elsewhere.

### 3.1 `atoms`
- `atom_id` TEXT PK — deterministic: `sha256(content_hash || ordinal)`.
- `content_hash` TEXT — sha256 of the atom's exact bytes. **The
  hash-twin rule:** identical bytes ⇒ identical `content_hash`. Any
  residual/novelty computation MUST treat a twin as reconstructable
  with residual 0. (Today exact duplicates score 0.9712 — the headline
  pathology.)
- `body_row_id` TEXT — the live-store row this atom was derived from.
- `ordinal` INTEGER — atom index within that row, 0-based, stable.
- `token_count` INTEGER — measured with the contract tokenizer, not
  estimated. **Invariant: `token_count <= contract.truncation_tokens`.**
- `role` TEXT — structural class only (`owner_utterance`,
  `maez_response`, `observation`, `reasoning`, `digest`, `external`).
  Derived from the existing container boundary, never from an LLM.
- `provenance_source`, `trust_tier` TEXT — copied verbatim from the
  body row (`ProvenanceSource` at `memory/memory_manager.py:78`,
  `TrustTier` at `:93`). Never re-derived, never upgraded.
- `created_ts` REAL, `spine_version` INTEGER.

**Atomization rule (v0, deterministic, no model):** split at the
production container boundary first (owner part / Maez part — the same
boundary that made 88.54% of telegram containers parseable in both
lanes), then, if a part still exceeds the token limit, split at
paragraph, then sentence, then hard token window. Every split is
recorded; no part is dropped. A long exchange therefore becomes
several atoms whose vectors each cover their whole text — the first
thing in the system for which that is true.

**Open question A (for the gate):** atomization is an authored
ontology (Codex). Splitting an exchange may destroy an interactional
whole. Mitigation proposed: atoms are additive — the body row remains
the unit of record and every atom carries `body_row_id`, so any
consumer may recompose. The spine never claims the atom is the meaning.

### 3.2 `lineage_edges`
- `child_id`, `parent_id` TEXT — real ids, one row per edge.
- `relation` TEXT — `consolidated_from`, `promoted_from`,
  `derived_from`, `atom_of`.
- `edge_ts` REAL, `spine_version` INTEGER.
- **Invariant: for any child, `count(edges) == the producer's own
  declared ancestor count`** (`promoted_from_count` already exists at
  the daily path — it is the untruncated count, so the equality is
  checkable today).
- Pre-spine ancestry is NOT synthesized. A child whose parents predate
  the spine gets exactly one edge to the sentinel parent
  `HISTORICAL_UNTRACEABLE`, with the declared count recorded alongside.

### 3.3 `query_events`
- `query_event_id` TEXT PK, `channel`, `chat_id`,
  `turn_seq` INTEGER (from `core/brain/conversation_turn_seq.py` —
  already built and already idempotent), `event_identity` TEXT.
- `vector` BLOB — the **pre-ranking** 384-float query embedding.
- `vector_source` TEXT — which encoder produced it.
- `n_requested` INTEGER, `collection` TEXT, `issued_ts` REAL.
- **Never post-ranking.** The winners are `exposures`, not this table.

**Hazard H1 (must be gated, do not hand-wave):** retaining the query
vector requires switching `_query_collection` from `query_texts=` to
`query_embeddings=`, which changes WHICH encoder embeds the query —
today Chroma's internal `ONNXMiniLM_L6_V2`
(`memory/embedder.py:92`), versus `get_encoder()`
(`memory/embedder.py:47`) on our side. These are nominally the same
model but not proven bit-identical in this repo. **Required witness
before any cutover:** N≥200 real queries embedded both ways; report
max cosine deviation and top-k set equality. Kill number: if top-10 set
equality is below 99% or max deviation exceeds 1e-4, the cutover does
not happen and the spine instead records the vector on a shadow path
without altering the live query. Recall behavior must not shift as a
side effect of instrumentation.

### 3.4 `exposures`
- `query_event_id` TEXT, `atom_id` TEXT (or `body_row_id` when the
  exposed unit predates atomization), `rank` INTEGER,
  `distance` REAL, `partition` TEXT (`evidence` / `context` — the
  living-recall partitions already exist), `shown` INTEGER (0/1 —
  retrieved-but-trimmed is not the same as shown), `exposed_ts` REAL.

This is the table that lets a later organ distinguish *reached for*
from *found* from *actually used*. It is the missing half of D3.

## 4. Slice plan (each slice = one gate)

- **S0 — tables + writer, fully dormant.** Schema, lazy-create,
  flags (`MAEZ_EVIDENCE_SPINE_SHADOW` / `MAEZ_EVIDENCE_SPINE_ENABLED`,
  declared via `def _entry(...)` at `core/cockpit/flags.py:65`, read via
  `def strict_env_flag(...)` at `core/infra/env_flags.py:23`). Witness:
  flags-off ⇒ no file, no connection, no import on the hot path.
- **S1 — atomization, shadow.** Observe every successful raw write,
  derive atoms, write `atoms` + `atom_of` edges. Nothing reads them.
  Witness: token-count invariant holds on 100% of atoms; twin rule
  demonstrated on a known duplicate pair; live store bytes unchanged
  (sha256 of the store files before/after, the check Codex used).
- **S2 — lineage edges.** Emit real edges at `consolidate_daily` and
  `store_core`. Witness: edge-count equality against
  `promoted_from_count` on 100% of new consolidations; sentinel parent
  used for pre-spine ancestors and never elsewhere.
- **S3 — query events.** Gated behind hazard H1's parity witness.
  Witness: one query event per admitted recall, each with a 384-vector,
  a turn ordinal, and a channel/cluster; recall top-k unchanged.
- **S4 — exposures.** Bind winners and shown-set to their query event.
  Witness: every exposure joins to an existing query event; `shown`
  distinguishes trimmed from used.

Only after S1–S4 have run in shadow do the organs attach:
examined-life (prospective), residual demand (amended), Return Parallax
(its byte-equality witness is an `atoms.content_hash` join — it cannot
fire before S1).

## 5. Pre-registered falsifiers (kill numbers)

Codex's eight, restated with the repo's own numbers as the "today"
column, plus two of mine (F9, F10):

| # | Falsifier | Today | Kill |
|---|---|---|---|
| F1 | Exact-duplicate residual under the twin rule | 0.9712 | > 1e-6 ⇒ kill |
| F2 | Neighborhood stability, k=5 vs k=20 Jaccard on the tail | 0.416 | < 0.70 ⇒ kill |
| F3 | Lineage count equality (edges vs declared count) | 62.72% sentinel | < 100% ⇒ kill |
| F4 | Atom token count vs contract limit | n/a | any atom > limit ⇒ kill |
| F5 | Query events per admitted recall | 0 | < 1.0 ⇒ kill |
| F6 | Suffix visibility: appended distinct text changes the atom vector | 0/193 | < 95% of long rows ⇒ kill |
| F7 | UNRECONCILABLE / HISTORICAL_UNTRACEABLE never silently reclassified | n/a | any transition ⇒ kill |
| F8 | Live store bytes unchanged across a shadow week (sha256) | n/a | any change ⇒ kill |
| F9 | Recall parity: top-10 set equality before/after instrumentation | n/a | < 99% ⇒ cutover blocked (H1) |
| F10 | Turn latency added by spine writes, p95 | n/a | > 25 ms ⇒ kill |

F6 is the one that proves the whole exercise: it is the exact probe
Codex used to break us, re-run against atoms instead of rows. If atoms
do not restore suffix visibility, the spine has not repaired D1 and
nothing downstream is trustworthy.

## 6. What this design does NOT claim

- It does not claim atoms are the units of meaning. They are units of
  *visibility*.
- It does not claim a complete lineage. It claims an *honest* one: what
  is known is recorded exactly, what is unknowable is labelled and
  stays labelled.
- It does not claim that recording demand makes anything important.
  Importance remains the amended residual-demand organ's claim to earn,
  later, with its own kill numbers.
- It does not make Maez's replies better today. Under shadow flags
  nothing about the live conversation changes — that is the point.

## 7. Questions carried into the Codex design gate

1. **Open question A** (§3.1): does atomization destroy interactional
   wholes, and is `body_row_id` recomposition a sufficient mitigation?
2. **Hazard H1** (§3.3): is the encoder-parity witness the right gate,
   or should query vectors be captured on a pure shadow path forever,
   never altering the live query call?
3. Is `exposures.shown` derivable at the real seam, or does the
   prompt-assembly boundary make "shown" unknowable without a second
   receipt at the prompt wrap?
4. Atom `role` derivation reuses the container boundary that parsed
   88.54% of telegram rows in both lanes. What happens to the other
   11.46% — one whole-row atom (may exceed the limit) or a hard token
   window (may cut mid-sentence)? Both are honest; which is less
   misleading downstream?
5. Retention: the spine grows without bound by construction
   (append-only). What is the honest retention story — and does any
   retention policy violate invariant 1?
