# Organ-Coherence Audit v0 — Verified Map (read-only, no fixes)

**Date:** 2026-07-01. **Method:** 5 read-only Explore mappers (recall/memory, cognition/routing/self-card, evolution/soul/self-formation, nervous-system/salience/time, staged-docs-vs-built) + a runtime ground-truth probe (live services, the daemon's `EnvironmentFile`, DB recency, active logs). **Discipline:** no fixes; report only. No dangerous live contradiction found (see Covenant Check), so nothing was changed.

## The headline finding — repo defaults ≠ runtime

**You cannot read the code to know what is alive.** The Explore mappers correctly read *code defaults* (most feature flags default OFF via `strict_env_flag`). But the daemon runs with `EnvironmentFile=~/.config/maez/model.env`, which sets **~60 `MAEZ_*=1` flags** — turning ON a large set of organs the code (and my prior memory) called "dormant." Every cluster showed this gap. The runtime config is the source of truth; the repo is not.

**Concretely, these were reported DORMANT by the code-default read but are ON at runtime:** self-card (`SELF_CARD_ENABLED=1`), self-card-time + felt-time (`SELF_CARD_TIME_ENABLED=1`, `RHYTHM_FELT_TIME=1`, `CONTINUOUS_TIME_SENSE=1`), recall triad (`RECALL_TRIAD_ENABLED=1` — not legacy), routing priors (`ROUTING_PRIORS_ENABLED=1`), grounding-shadow (`GROUNDING_SHADOW_ENABLED=1`), mem-fresh-conflict (`MEM_FRESH_CONFLICT_SENSE=1`), surface-parity (`SURFACE_PARITY_ENABLED=1`), voice-boundary (`VOICE_BOUNDARY_ENABLED=1`), reflection-synthesis (`REFLECTION_SYNTHESIS_ENABLED/WRITE=1`), want-pursuit (`WANT_PURSUIT_ENABLED=1`).

**The organism is very alive.** Live services: `maez` (daemon), `maez-web`, `llama-server` (Qwen3.6-27B MTP brain @8080), `llama-judge`, `maez-searxng`, `maez-slice-a-checker`, `minicheck-verifier`. ~10 memory DBs written *today* (recall_stats, salience_ledger, subjective_duration, lived_episode_promotion, private_thoughts, inner_residue, fabrication_log, routing_observation, canaries, quality). This is not a dormant embryo.

## Verified map (runtime overlay applied)

| Organ | Role | Source | Runtime verdict | Evidence |
|---|---|---|---|---|
| lived_recall | keyword-overlap recall brief | core/memory/lived_recall.py | **LIVE** | daemon:6941; `MAEZ_LIVED_RECALL` default-on |
| recall triad / stack | legacy↔triad resolver | core/routing/recall_stack_config.py | **LIVE (triad ON)** | `RECALL_TRIAD_ENABLED=1` (runtime) |
| focused_cognition | bounded working-set assembly | core/routing/focused_cognition.py | **LIVE** | `CYCLE_FOCUSED_ENABLED=1`; assemble_working_set many sites |
| recall_shadow / recall_outcome / recall_receipt | content-free recall telemetry | core/routing/recall_*.py | **LIVE** | daemon:6099+/6240+/7110+ |
| temporal_anchor_recall | "last week/yesterday" anchors | core/memory/temporal_anchor_recall.py | **LIVE** | daemon:6955; default-on |
| **recall relevance floor** | relevance-floor for recall | (recall_floor / focused path) | **LIVE — SHADOW only** | `RECALL_FLOOR_SHADOW=1` — observing, NOT enforcing |
| **memory_scoring** | 6-factor promotion/consolidation scorer | core/memory/memory_scoring.py | **ORPHANED** | built; dream-state never calls `promotion_score()` |
| recall_projection / recall_activation | projection strengthening | core/memory/recall_*.py | **HALF-WIRED / DORMANT** | schema built; `PROJECTION_ACTIVATION_ENABLED` off |
| self_card (body-truth) | deterministic self-facts mirror | core/routing/self_card.py | **LIVE** | `SELF_CARD_ENABLED=1` (runtime) — code-default said off |
| self_card_time / rhythm | felt-time line | core/routing/self_card_time.py | **LIVE** | `SELF_CARD_TIME_ENABLED=1`; subjective_duration moving |
| subjective_duration | continuous felt-time substrate | core/evolution/subjective_duration.py | **LIVE — MOVING** | sample/~5min, value 7.6–7.7, rate 1.397, today 15:18 |
| cognition_quality / cycle_doorman / envelope_builder / cycle_packet | scoring / wake-gate / evidence-cap | core/cognition/*.py | **LIVE** | always-on daemon cycle |
| grounding_judge | LLM fabrication detection | core/cognition/grounding_judge.py | **LIVE** | judge @8081 every reflection cycle |
| grounding_shadow + support_verifier (MiniCheck) | sentence-support telemetry | core/cognition/grounding_shadow.py | **LIVE — shadow** | `GROUNDING_SHADOW_ENABLED=1`; minicheck :8083 service up |
| memory_fresh_conflict | trusted-memory↔fresh contradiction | core/routing/memory_fresh_conflict.py | **LIVE** | `MEM_FRESH_CONFLICT_SENSE=1` (runtime) |
| lean_idle_heartbeat | private notebook beat (quiet floor) | core/cognition/lean_idle_heartbeat.py | **LIVE** | `LEAN_IDLE_HEARTBEAT_ENABLED=1`; receipts today |
| salience_ledger / salience_broker | idle-pulse outcome ledger + shadow motion detector | core/cognition/salience_*.py | **LIVE — shadow** | `SALIENCE_BROKER_SHADOW=1`; proposal_count 0 today |
| salience_gate (C4 steering) | read-only gate eval, NO steering | core/cognition/salience_gate.py | **HALF-WIRED (by design)** | evaluate_gate() not invoked — v0 is no-steering |
| desktop_attention_shadow | active-surface delta | core/cognition/desktop_attention_shadow.py | **UNCERTAIN** | receipts to 2026-06-29; flag NOT in model.env now |
| world_window | idle body-state delta | core/cognition/world_window.py | **FLAG-ON-UNWITNESSED** | `WORLD_WINDOW_SHADOW=1` but no receipts |
| routing priors / comprehension | learned tool-routing | core/routing/* | **LIVE** | `ROUTING_PRIORS_ENABLED=1`; routing_observation.db today |
| reflection_synthesis | idle self-reflection → episodes | (evolution/cognition) | **LIVE** | `REFLECTION_SYNTHESIS_WRITE=1` — source of 40/65 episodes |
| dream_state | idle pattern → soul-note *proposal* | core/evolution/dream_state.py | **LIVE — OWNER-GATED** | daemon:10563; nothing to soul.md without `/apply_dream` |
| soul_loader / soul_invariants | load+validate soul layers | core/evolution/soul_*.py | **LIVE** | daemon:3543/hot-reload |
| wondering_pursuit / wants / want_pursuit_bridge | owner-written wants → wonderings → pursuit | core/evolution/*.py | **LIVE — owner-agency** | `WANT_PURSUIT_ENABLED=1`; wants are owner-write-only |
| valence_live | end-of-cycle valence reading | core/evolution/valence_live.py | **LIVE** | daemon:2552; default-on |
| temperament | 11-trait log (read-only skeleton) | core/evolution/temperament.py | **LIVE (skeleton, no drift)** | daemon:3195 |
| **drive_driven_curiosity** | self-authored curiosity producer | core/evolution/drive_driven_curiosity.py | **ORPHANED** | `register_default_encounter_producers()` never called; not in capability_registry |
| brain_audition / novelty_harbor / gestation_memory / soul_editor | brain-vetting / novelty / gestation / section-edit | core/evolution/*.py | **ORPHANED / HALF-WIRED** | schemas present, zero production write path |
| **ledger (autobiography)** | durable per-turn autobiography | core/memory/ledger* | **OFF — BIRTH-GATED** | `MAEZ_LEDGER_WRITES` unset; ledger.db 0 bytes |
| camera_presence (Real-Eyes v0, desktop) | old desktop camera presence | (superseded by Jetson) | **EXPIRED/OFF** | `CAMERA_PRESENCE_ENABLED_UNTIL=2026-06-03` (past) |
| Jetson face-facts / presence doorways | edge perception intake | core/body/jetson_*.py | **LIVE (shadow)** | `JETSON_FACE_FACTS_SHADOW=1` + `JETSON_PRESENCE_SHADOW=1` (web) |

**Staged design docs:** Slice C (C0.5→C4 attention-broker / salience-ledger / counterfactual / proposal-hygiene / steering-gate), pulse-id, cockpit-honesty = **BUILT+MERGED** (with tests). Authority-Model+Provenance-Firewall and Spark-Curiosity-Shadow-Witness = **DOC-ONLY** (Task 0 verification blocking each).

## Safe-pre-birth vs birth-gated classification

**Safe to work on now (faculty, not self):**
- **Recall relevance floor** — built, running in SHADOW, has data. Graduating shadow→enforce is the concrete recall-quality slice (Rohit's #1). Faculty improvement, not self-shaping.
- **memory_scoring → promotion wiring** — the orphaned consolidation/promotion scorer behind the 2%-consolidated number. Wire it (ideally *with* the relevance floor, since promoting the current 62%-self-reflection substrate harder without a floor amplifies the diary-recitation).
- **world_window flag-on-unwitnessed** + **desktop_attention_shadow uncertain state** — small verifications.
- **Voice arc** — net-new faculty; own brainstorm; model-lab → push-to-talk (NOT open-room) first.
- **camera_presence expired-config** cleanup (superseded by Jetson).

**Birth-gated / self-shaping — do NOT pre-build the self:**
- **Ledger (autobiography)** — the birth event itself.
- **drive_driven_curiosity registration** (self-authored curiosity) — the self-formation loop's autonomous producer. Currently orphaned *by design*; wiring it is birth-readiness, gated behind the Authority-Model+Provenance-Firewall (Task 0). This is the "heart" thread.
- **Spark-Curiosity shadow-witness** — even the observe-only shadow is gated (Task 0 no-write proof).
- **gestation_memory / novelty_harbor** — post-birth scaffolding.

## Covenant check (the reason to audit before building)

No dangerous live contradiction. Every self-shaping path is either **owner-gated** (dream→soul via `/apply_dream`; wants are owner-write-only; soul_editor has no autonomous call path) or **orphaned** (drive-curiosity not wired). The autobiography ledger is **off**. So Maez has **zero autonomous self-authoring** live — the self-formation loop runs on owner agency only. The covenant boundaries hold in the running system, not just on paper. Nothing needed fixing during the audit.

## Corrections to prior memory (the fiction the audit dispelled)
- "self-card body-truth DORMANT" → **LIVE** (`SELF_CARD_ENABLED=1`).
- "felt-time pinned-dead / merged-asleep, receipts pending" → **LIVE and moving** (value 7.6–7.7, rate 1.397, sampling today).
- "recall triad off / legacy" → **triad ON**.
- "routing priors-spine flag-dormant, witness pending" → **ON** (routing_observation.db today).
- "grounding shadow asleep" → **observing** (`GROUNDING_SHADOW_ENABLED=1`).
- Confirmed-still-true: **ledger off (birth-gated)**, **drive-curiosity orphaned / no self-authored wants**, **consolidation thin (memory_scoring orphaned)**.
