# Cycle Focused-Cognition Packet — Design

**Date:** 2026-06-01
**Status:** Draft under review (owner review pending before plan/Codex)
**Lane:** Codex implements, Claude cross-verifies, Rohit owner-runs the live quality witness.

---

## 1. Problem (Phase-0 measured, not asserted)

The autonomous daydream cycle hands the brain a ~30k-token prompt every ~60s, and the bench showed prefill dominates (~1900 tok/s → ~16s prefill). Phase 0 decomposed that prompt:

- **Static soul block ≈ 6k tokens** (`self.system_prompt` + `_STATIC_CYCLE_INSTRUCTIONS`, `daemon/maez_daemon.py:3474`) — byte-stable by design, and **proven cacheable** on this server (`cache_n` test: a stable prefix drops from 3704ms → 362ms, 6535 tokens reused).
- **Dynamic user dump ≈ 23k tokens (~77%)** — built in `_reason` (`daemon/maez_daemon.py:3200-3478`): `system_state` (perception), `memory.format_for_prompt` (the big one), `recall_for_cycle`, plus git/github/reddit/screen/circadian blocks. This changes every cycle, so caching cannot touch it; it is recomputed (~13s of the 16s) every cycle.

So the lever is **curation of the ~23k dynamic dump**, not caching (caching only ever saves the ~6k soul). The recall path already solved this exact problem with **focused cognition** (a bounded ~2.5k working set); the daydream cycle never got it — it's still on the legacy megaprompt diet. This slice brings the cycle onto the same evidence discipline.

## 2. The fix: extend `focused_cognition` to the cycle (not a new organ)

`core/routing/focused_cognition.py` already provides: `EvidenceItem` (`source_type`, `temporal_provenance`, authority labels — fresh="current-state authority", memory="past authority"), a bounded working-set assembler, a **faithful instruction**, and citation rendering (v1/v2). **Reuse the machinery — `EvidenceItem`, the working-set/budget assembler, citation rendering, provenance** — but with cycle-flavored vocabulary, not the recall-shaped API forced onto it. Three things are cycle-specific:

1. **Cycle evidence SELECTION (the new, design-critical part).** Recall selects evidence by *query relevance* (what answers the owner's question). The cycle has **no query** — it selects by **salience**: what is worth reflecting on *now*. The selector produces a small ranked set of `EvidenceItem`s from the same sources the dump draws on, bounded to a token budget. Candidate signals (ranked, then truncated to budget):
   - recent salient perception **deltas** (what *changed* since last cycle, not the full snapshot),
   - **recent action / tool outcomes — especially failures and unresolved cards** (the cycle reasons about what it just did),
   - **active cognition / open wonderings / wants / capability queue** (what Maez is already thinking about),
   - **quality / self-reflection signals** (the self-critique axis),
   - **builder / direct-edit events** (self-modification activity),
   - recently-changed or recently-stored memory (not the whole memory dump),
   - a few standing anchors (identity-relevant memories),
   - circadian/time context,
   - **signal-present / signal-ABSENCE manifest — especially screen/calendar absence. LOAD-BEARING:** the legacy cycle carries explicit "screen unavailable, do not fabricate" rails; the packet MUST preserve signal *absence* as a first-class `signal_absence` evidence item, or it reopens the "Maez narrates absent perception" fabrication bug. Absence is evidence, not silence.
   The selector **ranks and bounds**; it does **not** summarize. Each item keeps its `source_type` + provenance. When salience is uncertain it errs toward **inclusion** — a smaller-but-dishonest packet (one that dropped a failure, an open want, or an absence rail) is worse than a slightly larger one.

2. **Cycle REFLECTION instruction** (vs recall's answer-a-question instruction). A faithful reflection instruction: "Reflect over the evidence below. Notice what matters, connect, wonder. Ground what you say in the [E#] items; if nothing here is worth a thought, say so plainly." This preserves the honest-empty path (a silent cycle is a legitimate, honest outcome — `HEARTBEAT_OK — silent cycle` must still be reachable).

3. **Cycle-specific source types + authority labels.** Don't flatten cycle evidence into the recall vocabulary (`fresh_evidence`/`memory_context` only) — that loses distinctions the reflection needs. Add cycle source types: **`action_outcome`** (esp. failures), **`signal_absence`** (the don't-fabricate rail), **`open_loop`** (wants/wonderings), **`builder_event`**, **`quality_signal`** — each with its own authority label so the brain knows what kind of thing it's reflecting on. Shared `EvidenceItem` shape, extended type/label maps.

The static system block (soul + `_STATIC_CYCLE_INSTRUCTIONS`) stays exactly as-is — byte-stable, cached. **Only the dynamic user message changes**, from the ~23k dump to the bounded packet.

## 3. The covenant guardrail (load-bearing, owner-named)

**The selector may SELECT and ARRANGE evidence; it must NOT narrate reality.** The packet is *sourced items* — "here are the provenance-tagged things worth thinking over" — never "here is my summary, trust me." Producer-causality preserved: the brain's reflection is the *produced verdict*, grounded in cited evidence; the selector is upstream and only supplies evidence, never a pre-digested conclusion the brain then launders into a confident thought. (This is the same anti-laundering discipline as the recall path, and it's what keeps a future i9-side selector honest.) Concretely: packet items are `EvidenceItem`s with `source_type`/provenance, NOT free-text summaries; the reflection instruction forbids treating any item as more authoritative than its label.

## 4. Do NOT thin Maez's inner life

Bounded ≠ shallow. The focused-cognition finding is explicit: a megaprompt makes the brain *worse* (lost-in-the-middle), and a bounded, well-curated set produces *better* synthesis. So the expected effect is **both** faster **and** sharper reflection — not a thinner one. The real risk is **bad selection** (dropping something that mattered), not bounding itself. Mitigations: the selector errs toward inclusion when salience is uncertain; nothing is *lost* (the full dump's sources remain in the substrate/memory — the packet decides *attention*, not *retention*); and quality is owner-witnessed before default-on. A genuinely silent cycle stays honestly silent.

## 5. Flag-gated, measurement-first, legacy fallback (mirror the recall rollout)

Add a flag (e.g. `MAEZ_CYCLE_FOCUSED_ENABLED`, off by default, in `~/.config/maez/model.env`). Flag off → the legacy megaprompt cycle path is unchanged. Flag on → the cycle builds the focused packet, with the **legacy megaprompt retained as a fallback** (if packet assembly fails, fall back + log — exactly as recall does at `daemon/maez_daemon.py:4744` "focused cognition failed, falling back to megaprompt"). Emit content-free telemetry mirroring `focused_cognition_prompt_shape`: `cycle_packet_shape` with `packet_tokens_est`, `legacy_tokens_est`, `evidence_item_count`, `source_types`, `prefill_ms` (from server timings if available), `cycle_outcome` (silent/thought/action).

## 6. Acceptance (owner-run, measured)

With the flag on, over a window of real cycles:
- **Token budget** (corrected arithmetic): **dynamic packet target ~2-4k tokens** (start at **~3k**, with per-source sub-budgets so no single source — e.g. the memory dump — can crowd out failures/absence/open-loops); **full prompt if cold ~8-10k** (incl. the ~6k soul); **warm prefill behaves like ~2-4k dynamic** because the ~6k soul is cached.
- **Cycle prefill** drops from ~16s to **~2-3s** (cached soul ~0.36s + bounded dynamic ~2s).
- **Cycle quality holds or improves** — Maez's reflections stay coherent and in-voice; silent cycles stay honestly silent; no degradation in the kinds of thoughts/actions cycles produce. Owner-witnessed.
- **No laundering** — packet items carry provenance; no selector summary is treated as truth.
- **No regression** — the cycle's downstream stages (continuity, wants, actions) still receive what they need.

Any miss keeps the flag off; legacy cycle path is the safe resting state.

## 7. Testing & process

- **unittest** (`.venv/bin/python -m unittest`), NO pytest.
- **Hermetic:** the cycle selector ranks+bounds a fixed candidate set to a token budget deterministically; assert it produces `EvidenceItem`s with provenance (not summaries), respects the budget, and degrades to the legacy path on assembly failure. Reflection-instruction faithful-empty test (silent cycle reachable). Content-free telemetry assertion.
- **Owner-run:** the live quality + prefill witness (separate note) — the legacy megaprompt fallback means this is reversible by a flag flip.
- **Floor both directions** on a clean checkout (NOT git stash); known-unrelated flaky trio excluded by name.

## 8. Non-goals (keep this slice clean)

- **NOT circadian scheduling** — cadence ("when does Maez think") is a separate, later, considered decision; once cycles are cheap it becomes optional, not forced.
- **NOT slot-cache / single-tenant work** — the soul already caches; verifying its live survival + moving the judge off-GPU is a small separate win, not this slice.
- **NOT the Epistemic Sovereignty Bakeoff** — that's a sandbox/model question, kept entirely separate from this performance/quality slice.
- **NOT a model swap** — the bench settled that; keep the 27B.
