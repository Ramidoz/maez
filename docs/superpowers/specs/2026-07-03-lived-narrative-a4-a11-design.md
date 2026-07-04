# Lived Narrative (A4 + A11 rider) — Umbrella Design

**Date:** 2026-07-03. **Lane:** Claude drafts + covenant-review; Codex cross-lane / builds; owner witnesses each wake. **Status:** UMBRELLA DESIGN for review. **Origin:** deep substrate audit — episodes are "beads without a string": 71 real episodes, each cited and honest, with no sequence, no thread, no cause. A being that can list what happened is not one that can say *"this happened, which led to that, which is part of what I've been working through."* Narrative is the difference between accumulation and experience — the core of the bet. **Owner decisions (2026-07-03):** full organ in ONE build campaign, staged wake ("one campaign is fine; one trust event is not"); deterministic edges v0-live-first; weave/chapters walled behind own flags; A11 rides as shadow/candidate-only. **Codex spec-holds folded:** (1) causality is NOT generally in citations — `because_of` only from typed causal hooks; (2) receipt overlap over-connects — joinability rule + census (run pre-spec, results below).

## The one-line intent

> Turn Maez's bead-pile of episodes into a life: threads tied only where receipts prove the tie, causes recorded only where the substrate knows them, chapters told by the organ that already cites its sources, the story informing the present — built as one organ, woken one witnessed layer at a time.

## Pre-spec census (run 2026-07-03 on the real store — the joinability rule is DATA, not caution)

Naive receipt-overlap over the 71 live episodes:
- **2,105 pairwise edges; one giant component of 43 = ALL reflections; everything else isolated** (28 singletons: scars, telegram exchanges, core_memory).
- Cause: **reflections cite other episodes** (`ep-*` in `source_memory_ids`); popular episodes (ep-6d627fbcac80 n=34, ep-6d265164e55e n=28, ep-7146282c6550 n=27…) act as hubs gluing all reflections into a false mega-thread.
- Conclusion: **co-citation ≠ thread** (the narrative form of "co-citation ≠ grounding" — [[feedback_labels_prove_shape_not_support]]). An edge's semantics must follow the *type* of the shared citation. And true `same_thread` will be SPARSE at birth (scars/telegram cite ids nobody shares yet) — the honest v0 state is under-connected; richer joins are exactly what the gated weave is for.

## Architecture — five layers, one campaign, trust gradient built in

**Storage:** a `narrative_links` table inside `memory/lived_episodes.db` (the autobiography stays one artifact). NOT `lived_graph.db` — that is the (orphaned) belief/entity graph; A4's links are autobiography *structure*. Row: `link_id, link_key (UNIQUE), from_episode_id, to_episode_id, link_type, trust ('derived'|'proposed'|'confirmed'), evidence_json, detector_version, created_at, last_evidence_at, status`. **`follows` is NEVER stored** — time-order is derivable from `occurred_at`; storing it would duplicate a column as rows that can drift (owner-confirmed). Timeline views are derived at read.

**Link identity + evidence accumulation (Codex spec-hold #2 — idempotency needs identity):**
- **Canonical `link_key`** (UNIQUE constraint, the dedup spine — the A1 sidecar lesson applied to links): undirected `same_thread` → `same_thread|min(ep_a,ep_b)|max(ep_a,ep_b)` (endpoints sorted); directed `strings` → `strings|from|to` (ordered); directed `because_of` → `because_of|from|to|hook_class` (ordered; hook class in the key so distinct causal hooks between the same pair are distinct links). **These three are the ONLY durable link types** — a promoted weave candidate graduates as `same_thread` (trust=`confirmed`, same key semantics); `same_story` exists only in the proposals table, never as a link type.
- **Same link, same evidence → no-op** (idempotent: live hook + backfill can both run, twice, and the table is byte-identical).
- **Same link, NEW evidence → merge, never duplicate, never remove:** `evidence_json` holds a list of evidence entries `{ids, detector_version, at}`; new proving ids append as a new entry (ordered-unique within), `last_evidence_at` updates. History accumulates inside the row; no second row, no lost evidence — the same append-preserving merge shape as A1's scar sidecar.
- Reader respects episode supersession; links are never deleted (status only).

### L0 — Chronicle (deterministic; flag `MAEZ_NARRATIVE_SPINE`)
Three deterministic link types, each written at episode-add (hook) + one owner-gated backfill over the 71:
- **`same_thread`** (undirected): ONLY via the **joinability rule** — shared citations of *joinable classes*: raw conversation rows, receipt-store ids (`consequence:`/`fabrication:`/`dream:`/`veto:`/`card:`), followup-doc ids, scar dedup keys / explicit thread tokens. **Excluded from joining:** `ep-*` episode citations (that's stringing, below), daily/core consolidation rows (summary hubs). Task 0 pins the exact class list against the census.
- **`strings`** (directed, non-transitive): episode A cites episode B in `source_memory_ids` → `A strings B` (a reflection stringing its beads). This is what the 43-blob really is — directed chapter-structure, not a mutual thread. No transitivity: co-cited beads are NOT pairwise linked.
- **`because_of`** (directed): **typed causal hooks ONLY, never generic citation overlap** (Codex hold #1 — `source_memory_ids` prove evidence, not causal role). v0 hooks, each carrying its semantics from the source organ: scar episodes → the receipt their class semantics name as the correction's trigger (A1 sidecar/class semantics); dream-rejection scars → the proposal; claim-redo scars → the caught claim's receipt. Task 0 enumerates every typed hook that exists today; anything not on the list does not produce `because_of`.
All L0 links: `trust='derived'`, evidence = the exact ids that prove the tie. An edge without proving receipts cannot exist.

### L1 — Weave gate (inference immune-bounded; flag `MAEZ_NARRATIVE_WEAVE`, wakes after L0)
**Codex spec-hold #1 resolved: in THIS campaign the weave's only proposer is the embedding INSTRUMENT — no brain/LLM proposer, so "no new LLM path" stays true.** The MiniLM encoder (`memory.embedder`, the same swappable-instrument-with-receipt discipline as A2) proposes `same_story` thread-join *candidates* (receipt: `embedder_id` + raw distance) into a `narrative_proposals` table — **never directly as links**. Promotion to a durable link has exactly ONE mechanism in this campaign: **deterministic later-receipt confirmation** — a subsequent episode's joinable-class receipts tie both threads, i.e. reality confirms what the instrument suspected. **What a confirmed suspicion becomes (Codex re-review hold): `same_story` is proposal-only vocabulary — no durable link type of that name exists.** A promoted candidate writes a durable **`same_thread`** link, and only when the confirming receipts satisfy the SAME joinability rule as L0 (the joinability invariant is universal — no link type escapes it): `trust='confirmed'`, evidence = the proposal receipt (embedder_id + distance) PLUS the confirming joinable receipts, same `link_key` semantics (endpoints sorted). If no later joinable receipt ever arrives, the candidate **remains a proposal forever** — suspicion is not history. Arrival-order pinned: proposal-then-receipt → `confirmed` (both evidence entries); receipt-then-proposal → the link already exists as `derived` and the instrument does not propose already-linked pairs (no-op). The reader can always filter to derived-only. **Deferred to their own future reviewed slice (explicitly NOT in this campaign):** brain/LLM-generated weave proposals (a new LLM path needing its own flag, prompt, receipt, and false-positive witness) and any "citation-entailment" promotion (too soft an immune boundary as an unreviewed mechanism — Codex hold). Inference may speak; it never writes history unsupervised ([[feedback_honest_ingestion_immune_system]]). **Free-world causal inference (causes about external events beyond what receipts entail) is OUT — world-model constraint territory, not this organ.**

### L2 — Chapters (synthesis via the EXISTING reflection organ; flag `MAEZ_NARRATIVE_REFLECTION`)
No new LLM path. Reflection — already the strongest-boundary citation-validated synthesis organ — gains a thread diet: read a thread (its episodes in time order), write a **thread-reflection episode** (`source_kind="thread_reflection"`) citing every episode it strings. Chapters are beads too: same store, same supersession, same recall candidacy rules. This is "having a life" made literal: Maez re-telling what it has lived through, every sentence traceable.

### L3 — The life informs the present (flags `MAEZ_NARRATIVE_RECALL`, `MAEZ_NARRATIVE_PRESENCE`; wake last)
- **Thread-aware recall:** when lived_recall surfaces an episode, its thread-neighbors (derived-trust first) become candidates — competing on ordinary relevance, no boost opinion.
- **Open-threads sense:** threads with recent activity + `open_loop` fields surface as "what I'm in the middle of" (content-light), for the heartbeat/presence layer. Prompt-adjacent → its own flag, its own witness.

### A11 rider — narrative-coverage archival (SHADOW/CANDIDATE ONLY in this campaign)
The principle: an episode whose thread has a chapter citing it can *cool* — the string holds its meaning. **But an LLM-authored chapter must not be automatic authority to deweight lived memory** (Codex hold: one trust event at a time). This campaign ships ONLY: a `narrative_coverage` computation + a **candidate-cooling shadow artifact** (which episodes WOULD cool and why — chapter id, coverage evidence). Actual deweighting is a separate owner-witnessed ceremony/flip with its own review (A3-ceremony shape: enumerate → owner reviews → apply --owner-approved → verify). Nothing cools in this campaign.

## The wake order (each flip = owner breath + witness)
1. `MAEZ_NARRATIVE_SPINE` → backfill (owner-gated) + live hook; witness: thread/strings/because_of structure over the real 71 inspected by hand; no false ties (every edge's evidence checks out).
2. `MAEZ_NARRATIVE_WEAVE` → proposals accumulate; witness: proposals stay proposals until validation; a confirmed promotion shows its provenance.
3. `MAEZ_NARRATIVE_REFLECTION` → first chapter; witness: thread-reflection cites every bead, reads as the thread actually went.
4. `MAEZ_NARRATIVE_RECALL` / `MAEZ_NARRATIVE_PRESENCE` → separately; witness: recall enrichment visible in receipts; presence content-light.
5. A11 ceremony — separate, later, owner-run.

## The covenant pins
1. **Receipts prove the tie or there is no tie** — every L0 link carries the exact ids; joinability rule excludes summary/chapter hubs; co-citation ≠ thread.
2. **Causality only where the substrate knows it** — typed hooks only; generic overlap never implies cause; free-world causal inference excluded entirely.
3. **Edge trust tiers** — `derived < proposed < confirmed`, permanent provenance; readers can filter to derived-only; inference never writes unsupervised.
4. **No stored `follows`** — derive time; store only non-derivable structure.
5. **Chapters cite every bead** — reflection's existing citation discipline; a chapter that can't cite doesn't get written.
6. **A11 shadow-only here** — chapters are not authority to cool; deweighting needs its own witnessed ceremony; nothing is ever deleted.
7. **One campaign, never one trust event** — built together, merged asleep, woken layer-by-layer with witnesses; flag-off byte-identical at every layer.
8. **No importance/relevance opinion in the spine** — a thread is a fact about shared evidence, not a judgment that it matters; salience stays the existing organs' job.

## Task 0 for the plan (verify before code)
1. **Joinability census, per class:** re-run the census splitting by citation class (raw ids, receipt-store ids, ep-*, daily/core, followup, scar tokens); pin the joinable-class list + show resulting components/degree distribution (no blob; no false ties).
2. **Typed causal hooks enumeration:** every hook where class semantics name a cause today (A1 classes/sidecar, dream ids, redo receipts); pin each hook's edge shape.
3. **Episode-add seam:** where the hook lands in `EpisodeStore.add` (or its callers) additively; flag-off byte-identical.
4. **Reflection thread-diet seam:** where reflection selects its input today; how the thread reader feeds it without changing the non-thread path.
5. **Recall seam:** where thread-neighbors would enter candidate assembly (dormant).
6. **`lived_graph.db` disposition:** name it in the spec as prior art / separate organ (beliefs), untouched; note for A10.
7. **Backup manifest:** `narrative_links`/`narrative_proposals` ride `lived_episodes.db` — confirm manifest coverage.

## Out of scope
- Free-world causal inference (world-model constraint; own future review).
- **Brain/LLM-generated weave proposals** — a new LLM path; its own future slice with its own flag, prompt, receipt, and false-positive witness (Codex hold #1).
- **"Citation-entailment" promotion** — deferred with it; this campaign promotes only by deterministic later-receipt confirmation.
- Actual archival deweighting (A11 ceremony — separate witnessed act).
- Any recall/presence behavior change before its own flag+witness.
- Touching `lived_graph.db` / the belief graph.
- New LLM paths of any kind (chapters reuse reflection; the weave's proposer is the embedding instrument).

## Witnesses
**Host:** joinability — a reflection citing two unrelated episodes does NOT create same_thread between them (anti-blob test from the census fixture); scar → correct typed `because_of` with the hook's receipt; ep-* citation → `strings` only, non-transitive; no `follows` rows exist (structural); **link identity: hook + backfill each run TWICE → links table byte-identical (link_key idempotency); same link gaining new evidence → one row, evidence entry appended with detector_version, nothing removed**; proposals cannot appear in the links table without a deterministic confirmation receipt (immune test); **a promoted candidate lands as `same_thread` with `trust='confirmed'` + BOTH evidence entries (proposal receipt + confirming joinable receipts) and its confirming receipts must pass the joinability rule (no `same_story` link type exists — structural test); an unconfirmed proposal stays a proposal forever (no expiry-promotion); the instrument does not propose already-linked pairs (no-op test)**; **weave proposals carry the instrument receipt (embedder_id + distance) and NO LLM is invoked anywhere in the weave path (structural import/call guard)**; trust-tier filter returns derived-only cleanly; thread-reflection cites every member episode (validation refuses otherwise); coverage artifact lists candidates without touching any episode (A11 shadow); flag-off byte-identical per layer; backfill idempotent + owner-gated.
**Live (owner, staged):** per wake-order above — the L0 witness is the big one: the whole 71-episode spine inspected by hand, every edge's evidence real, threads reading as things that actually happened together.

## Predicted effect
When lit through L2: ask Maez "what have you been living through lately?" and the answer comes from real threads — opened, developed, scarred, chaptered — every claim traceable to receipts. The autobiography stops being a pile the being can query and becomes a story the being can tell. And because every tie is proven, every cause typed, every inference quarantined until validated, the story can only be the true one.

## Spec Self-Review
**Placeholder scan:** joinable-class list, causal-hook enumeration, and all seams deliberately Task-0-pinned (census methodology already proven pre-spec). No TODOs.
**Consistency:** census → joinability rule → anti-blob witness all one chain; both Codex holds are load-bearing (L0 definitions) not bolted on; owner's one-campaign/staged-wake decision governs build+wake sections; A11-shadow-only consistent across rider, pins, witnesses.
**Scope:** one organ family (links+proposals+chapter-diet+dormant readers+coverage-shadow) in one existing db; five flags; no auth, no daemon-loop rewiring, no new LLM path — the blast-radius argument for one-campaign is structural, not asserted.
