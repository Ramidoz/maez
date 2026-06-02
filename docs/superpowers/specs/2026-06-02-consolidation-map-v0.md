# Consolidation Map v0 — what Maez does with its day today

**Date:** 2026-06-02
**Status:** Map / inventory (NOT a build). Grounds the heavy/sleep-consolidation design.
**Method:** 4 parallel codebase readers + live verification of the load-bearing claims (Claude-verified, not code-read alone).

---

## The headline finding (verified live)

**Maez now has *attention* but no *metabolism*.** The doorman (live) makes Maez wake less and the packet makes it think cheaper — so the quiet hours exist. But the machinery that would turn the *lived day* into *durable growth* is **built, rail-guarded, and dormant/unwired**. The day flows: every cycle stores a raw thought → 3 AM compresses the day into one *daily summary* → **and then it stops.** The daily summaries dead-end; the insight/promotion/dream organs that would integrate them into durable selfhood are all off.

The heavy/sleep-consolidation organ is therefore **mostly a wiring + scheduling + extension job on existing rail-guarded organs**, not a from-scratch build. That's the v0 conclusion.

---

## What RUNS today (live, verified)

| Organ | Reads | Writes | When | GPU? | Rails | Status |
|---|---|---|---|---|---|---|
| **Raw store** (`MemoryManager.store` `memory_manager.py:903`) | cycle thought + snapshot | one `raw_archive` row (live: **42,935**) | every contentful cycle (HEARTBEAT_OK stores nothing) | CPU (embed) | embedding-write audit, provenance validated, never-delete, self-claim-audit before store | ✅ live |
| **raw→daily consolidation** (`consolidate_daily` `:1010`, `_consolidation_loop` `daemon:6466`) | ≤500 recent raw since last marker | one `daily_consolidation` row (live: **23**) | **nightly 03:00** + startup catch-up | **GPU — `gemma4:26b`** (map-reduce distill) | untrusted-filter *before* LLM (5x.E), lineage/worst-tier stamp, `cog_check_consolidation` gate | ✅ live (marker updated 06-02T08:00Z) |
| **Nightly journal** (`_nightly_journal_loop` `daemon:6755`) | 24h logs + today's daily summary | `PROGRESS.md` entry + one `core` `[Journal]` row | **nightly 23:00** | GPU (Qwen, num_predict 4096) | evidence-envelope + `audit_assistant_text` | ✅ live (47 of 94 core rows) |
| **Developmental heartbeat** (`core/brain/developmental_heartbeat.py`) | — | one `core` row/day, `trust_tier=covenant` | daily | — | covenant tier | ✅ live (~28 core rows) |
| **Per-turn lesson re-injection** (consequence/fabrication/residue via `capability_registry.prompt_snippet`) | consequence_memory, fabrication_log (7-day), residue | next prompt | every reply/cycle | CPU | evidence-tie, fail-soft | ✅ live — but this is *recall-into-context*, not consolidation-into-self |

## What's BUILT but DORMANT / BROKEN (the empty seats)

| Organ | What it would do | Why it's not working | Rails it already has |
|---|---|---|---|
| **daily→core promotion** (`store_core(promoted_from=)` `:1257`) | promote daily summaries into durable core knowledge | **No pass ever calls it with daily ancestors.** Live: **0 `source=promotion`** core rows. The lineage/worst-tier/`PromotionBlocked` gate is excellent but never invoked on the tier pipeline | worst-wins tier inheritance, untrusted-ancestor block |
| **Reflection synthesis** (`core/memory/reflection.py`, `nightly_lived_memory.py:385`) | turn clusters of episodes into *new* surfaceable insight (Generative-Agents style) | **systemd timer NOT installed** (verified: no maez/reflection timer). Runs only by hand | evidence-required citations (drops uncited), append-only, fail-open, cap 3 |
| **Dream** (`core/evolution/dream_state.py`) | idle pattern-insight → owner-reviewed proposal | **idle gate never opens**: daemon calls `is_idle(None, 0.0)` → always `False`. Also: only emits one paragraph, no memory restructuring | NOTHING-sentinel, novelty gate, `audit_assistant_text`, S7 owner-gated soul writes |
| **Private thoughts** (`core/infra/private_thoughts.py`) | distinct private inner-residue store | producer + consumer default **OFF** (`producer_enabled=False`) | contextual-integrity envelope, closed provenance vocab, append-only |
| **promotion_score** (`memory_scoring.py:348`) | rank what deserves promotion | computed + logged but **"not yet used to route promotion"** (telemetry-only) | deterministic 6-factor, CPU |

## The growth signals consolidation never touches

Verified: the 3 AM consolidation reads **only** the raw Chroma collection. It does **not** read any of these, so none of them are ever integrated/promoted:
- **Wants** (`core/evolution/wants.py`) — append-only, resolve only on *human* action; the `maez_reflection_producer` provenance exists but is **inert** (not in the allowlist). No Maez-side want producer.
- **Wonderings** (`core/evolution/wonderings.py`) — advance one probe/cycle, `resolve()` on conclusion, but no pass promotes a resolved wondering's learning into durable self-knowledge or a want. (Strong anti-fabrication rails: evidence-tie or the `(synthesis blocked — no concrete evidence tie)` sentinel.)
- **Lessons** (consequence_memory / fabrication_memory) — 7-day *window* re-injection, decay out with no promotion to permanent self-model.
- **Capability queue / builder events** — move only by human approval gates.

So growth signals are **accumulate-and-decay** or **accumulate-and-re-inject**, never consolidated.

## The gap, in one line

There is **no organ that, in the quiet the doorman now creates, reviews the day's sourced evidence (raw thoughts + resolved wonderings + lessons + wants) and integrates it into durable self-knowledge (core promotion + new insight)** — even though the rail-guarded pieces to do it mostly exist, off.

## What the heavy/sleep-consolidation design must therefore do (preview, not the design)

1. **Schedule, don't reinvent.** Wire up the dormant organs: install the reflection-synthesis pass, fix the dream idle-gate (pass real presence, not `None`), invoke daily→core promotion using `promotion_score` as the router.
2. **Run in the doorman's quiet windows / sleep phase** — the GPU is now free ~94% of the time; presence *modulates timing* (defer heavy work while Rohit's likely to speak), never gates whether it happens.
3. **Consolidate the growth signals too**, not just raw — feed resolved wonderings, lessons, and wants into the integration pass (and finally wire the inert `maez_reflection_producer` want seam, carefully).
4. **Keep every existing rail:** evidence-required citations (no blind summary becomes truth), untrusted-filter-before-LLM, worst-wins tier inheritance, append-only / supersede-not-delete, owner-gated for anything that touches soul.
5. **Resolve the model question:** the 3 AM consolidation runs on `gemma4:26b` — confirm that's intended/served (vs the Qwen primary; possibly stale). The Gemma bakeoff may interact here.

## Flags for follow-up (verified anomalies, not in scope of the map)

- **Dream idle-gate is a live bug**, not just "off": `is_idle(None, 0.0)` means the dream never fires regardless of AFK. Worth a one-line fix independent of this design.
- **Reflection timer uninstalled** — the build expects a systemd timer that isn't present on this host.
- **Consolidation model `gemma4:26b`** — a different model than the live Qwen primary; verify it's actually served and intended.

## Verification record (live, by Claude)

- `systemctl --user list-timers --all` → only `maez-backup.timer` (no reflection/lived timer).
- ChromaDB live counts: raw 42,935 / daily 23 / core 94; core `source` breakdown = 0 promotion (47 journal, ~28 heartbeat, ~18 owner).
- `core/evolution/dream_state.py:274` `is_idle`: `presence_snap is None → return False`; `daemon:8061` calls `is_idle(None, 0.0)`.
- `memory_manager.py:287` `MODEL = "gemma4:26b"`.
