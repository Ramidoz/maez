# Silent organs — modules doing real work but not in the docs

## Summary
Inventoried 264 `.py` files under `core/`, `core/<subpkg>/`, `skills/`, `daemon/`,
`memory/`. After removing 69 top-level `core/*.py` shim re-exports and trivial
fixtures, **195 substantive modules** remain. **107 are not mentioned in any
canonical anatomy / north-star / life-substrate / TRACK_A / MAEZ.md / BAD doc
and are not even named in their subpackage README** — they are true silent
organs. An additional 40 modules are listed in the relevant subpackage README
only and are silent in the visual anatomy / strategy docs.

## Methodology
1. `find` over `core/`, `skills/`, `daemon/`, `memory/` (`/home/rohit/maez/`).
2. Classification:
   - **Shim** — first 7–14 lines, contains `sys.modules[__name__] = _real`
     pattern delegating to a subpackage (e.g. `core/action_engine.py` →
     `core.actions.action_engine`). Verified by reading
     `/home/rohit/maez/core/action_engine.py` and grepping for re-export
     pattern across all top-level `core/*.py`.
   - **Trivial utility** — `<50` LOC, single helper, no behavior beyond
     parameter shuffling. Counted but not deep-audited.
   - **Substantive** — everything else (≥50 LOC, has data structures, side
     effects, or named contracts).
3. For each substantive module, grep the canonical doc set for: the relative
   path (`core/x/y.py`), the dotted form (`core.x.y`), and (weakly) the bare
   basename. Hits in subpackage READMEs counted separately because a README
   that just lists every file in its directory is "named", not "documented".
4. Modules with zero canonical-doc hit AND zero README hit are *truly silent*.

## Inventory totals
- Total `.py` files in audited packages: **264**
- Shims (top-level `core/*.py` re-exports): **69**
- Trivial utilities (`__init__.py` / `__main__.py` thin wrappers, ≤50 LOC):
  ~ 27 (e.g. `core/agent_tools/__init__.py`, `core/capability_*/__main__.py`,
  `skills/presto_bridge.py`)
- Substantive modules: **195** (the audit set)
- Substantive modules referenced in at least one canonical doc (anatomy /
  north-star / life-substrate / TRACK_A / MAEZ.md / BAD): **48**
- Substantive modules named only in a subpackage README (silent in canonical):
  **40**
- **Silent organs (substantive, undocumented anywhere): 107**

## Silent organs — full list

### Critical silent organs (touch cycle / memory / audit / identity / surface)

| Path (under `/home/rohit/maez/`) | LOC | What it does | Doc that should mention it |
| --- | --- | --- | --- |
| `core/cognition/moment_assembly_diagnostic.py` | 2846 | Schema + recorder for the "Moment Assembly Diagnostic" — the master organ-by-organ trace of every cycle. Owns the additive-only schema contract; 56 importers across the daemon. | MAEZ_ANATOMY (organ diagram), TRACK_A (diagnostic surface) |
| `core/cognition/envelope_builder.py` | 971 | Slice 3 evidence-envelope builder: enforces the 3K-token / 12K-char cap, assembles the audit envelope. Cited in `SLICE_3_0d_TOKEN_BUDGET_MEMO.md` but not the canonical set. | MAEZ_ANATOMY (audit), MAEZ_LIFE_SUBSTRATE |
| `core/cognition/audit_policy.py` | 150 | Slice 4c.5b refusal policy that keeps projection-influenced rows from contaminating the audit trace. Hard rule encoded in code, missing from BAD. | MAEZ_LIFE_SUBSTRATE, BAD |
| `core/cognition/perception_signature.py` | 178 | Perception-delta signature for fixation-prevention — the disk-fixation observation referenced in user-memory is implemented here. | MAEZ_ANATOMY (cognition box) |
| `core/memory/lived_recall.py` | 1342 | ADR 0019 Phase 5 — lived-recall planner that builds the four-section recall brief used by the cycle. **Cited in `feedback_test_with_natural_human_texts` user memory ("probe `build_lived_recall_brief` directly") but absent from anatomy.** | MAEZ_ANATOMY (memory ring), MAEZ_LIFE_SUBSTRATE |
| `core/memory/recall_projection.py` | 408 | Slice 4a/4b recall projection read-models + shadow strengthening rule. Production-influencing. | MAEZ_LIFE_SUBSTRATE |
| `core/memory/recall_activation.py` | 68 | Cold-recall activation gate (Slice 4c.5c) — production socket for projection activation. | MAEZ_LIFE_SUBSTRATE |
| `core/memory/recall_activation_config.py` | 49 | Env-var contract for `recall_activation.py`. | MAEZ_LIFE_SUBSTRATE |
| `core/memory/cycle_recall_context.py` | 118 | 5x.F.A — cycle-scoped recall-context bag; per-cycle accumulation of recalled memory IDs. | MAEZ_ANATOMY |
| `core/memory/working_self.py` | 687 | Goal-driven retrieval module modeled on Conway & Pleydell-Pearce (2000). Substantial cognitive-architecture module. | MAEZ_ANATOMY, MAEZ_NORTH_STAR |
| `core/memory/baseline_observations.py` | 468 | F1.A baseline observation store + lexical detector — the post-5x memory-provenance arc. **Closely tied to the Zombie-Agents user memory.** | MAEZ_LIFE_SUBSTRATE, BAD ADR (provenance) |
| `core/memory/belief_simulator.py` | 500 | "What would the owner push back on?" simulator (ADR 0019 v1.3, owner-anchored 2026-04-27). 19 importers. | MAEZ_ANATOMY, MAEZ_LIFE_SUBSTRATE |
| `core/memory/temporal_echo.py` | 286 | Temporal-echo finder (ADR 0019 v1.2). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/temporal_arithmetic.py` | 259 | Recall-time temporal arithmetic — first capability produced by the capability-acquisition pipeline. **Living proof of D20 closing the loop, but unmentioned.** | MAEZ_ANATOMY, BAD (D20 proof) |
| `core/memory/entity_index.py` | 715 | Entity sidecar substrate (Step 5e) — prerequisite to multi-session entity linking. | MAEZ_LIFE_SUBSTRATE |
| `core/memory/entity_backfill.py` | 811 | Deterministic entity-index backfill (Step 5f). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/entity_llm_extractor.py` | 745 | Offline LLM entity extraction batch (Step 5m). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/entity_semantic_resolver.py` | 357 | Semantic entity resolver (Step 5n). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/entity_semantic_suggester.py` | 424 | Semantic-mapping suggester + auditor (Step 5p). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/entity_alias_seed.py` | 444 | Owner-curated entity alias seeding (Step 5g). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/entity_alias_suggester.py` | 572 | Alias-candidate suggester (Step 5l). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/relationship_extractor.py` | 358 | Relationship-extractor for the lived-memory layer (ADR 0019 Phase 3). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/relationship_graph.py` | 330 | Append-only temporal relationship graph (ADR 0019). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/episodes.py` | 161 | Append-only episode store (ADR 0019). | MAEZ_LIFE_SUBSTRATE |
| `core/memory/episode_builder.py` | 506 | Episode promotion logic (ADR 0019 Phase 2). | MAEZ_LIFE_SUBSTRATE |
| `core/safety/premise_audit.py` | 411 | Premise-acceptance audit — the 2026-04-27 incident class ("owner reframes Maez's suggestion as approval"). Production safety gate. | MAEZ_LIFE_SUBSTRATE, BAD |
| `core/safety/output_command_guard.py` | 177 | Output-side command guard — refuses dangerous commands emitted as text (fenced code) in replies. 2026-04-23 gap closure. | MAEZ_LIFE_SUBSTRATE, BAD (safety boundary) |
| `core/safety/audit_signal_manifest.py` | 146 | Fallback-default builder for the self-claim audit's signal manifest — fixes the 2026-05-05 wmctrl "grounding-context starvation" incident. | MAEZ_LIFE_SUBSTRATE |
| `core/brain/continuity_ledger.py` | 95 | Compact continuity-probe ledger summaries for Maez's self-continuity. | MAEZ_ANATOMY, MAEZ_NORTH_STAR |
| `core/brain/conversation_history.py` | 93 | Chat-history → `messages[]` conversion. Fixes the 2026-04-24 04:53 contextless-followup incident — *cycle-affecting*. | MAEZ_ANATOMY |
| `core/brain/developmental_heartbeat.py` | 169 | Daily developmental heartbeat — once-per-day audited core memory about what changed in Maez's stance. **Identity-shaping**. | MAEZ_ANATOMY, MAEZ_NORTH_STAR, BAD |
| `core/brain/return_greeting.py` | 68 | Presence-return greeting composer (replaces hardcoded "Welcome back the owner"). Surface-affecting. | MAEZ_ANATOMY |
| `core/decision/recent_action_context.py` | 192 | Surfaces preceding card outcomes to the cycle narration path. R3.5 from 2026-05-04 symphony audit — fixes "system idle, holding quiet" 12s after a real action. *Cycle-affecting*. | MAEZ_ANATOMY |
| `core/actions/shell_failure_detector.py` | 191 | Recognises tool-failure patterns in shell output even when returncode==0. *Cycle-affecting* — feeds the consequence pipeline. | MAEZ_LIFE_SUBSTRATE |
| `core/ledger/envelope_schema.py` | 203 | Source of truth for the evidence-envelope vocabulary cited in `LEDGER_ENVELOPE_SCHEMA.md`. Not present in canonical set. | MAEZ_LIFE_SUBSTRATE, BAD |
| `core/ledger/model_reply_persistence.py` | 211 | Owner-private `model_reply` persistence — Slice 4c.5a autobiographical continuity for Maez's own replies. *Identity-affecting* (closes the "Maez can't remember what it just said" gap). | MAEZ_ANATOMY, BAD |
| `core/ledger/reconcile.py` | 265 | §6.2 cross-DB ledger reconciliation across audit_log / fabrication_events / pending_cards / etc. | MAEZ_LIFE_SUBSTRATE |
| `core/ledger/recent_turns.py` | 124 | Bounded ledger lookback by `turn_kind`. Foundation for the envelope builder's `self_history`. | MAEZ_LIFE_SUBSTRATE |
| `core/agent_tools/memory_view.py` | 237 | Letta-style memory-introspection tools (Slice 7) — Maez reads its own memory. **Architectural milestone — first read-only self-introspection facade.** | MAEZ_ANATOMY, MAEZ_NORTH_STAR |
| `core/evolution/wondering_pursuit.py` | 875 | When-to-Assist + How-to-Assist module for proactive engagement with owner wonderings. *Surface-affecting*. | MAEZ_ANATOMY, BAD |
| `daemon/wondering_cycle.py` | 423 | One exploratory probe per daemon cycle. Owns the autonomous-probe rail. *Cycle-affecting*. | MAEZ_ANATOMY (cycle), BAD |
| `memory/quality_tracker.py` | 369 | Reasoning quality feedback loop — records every proposed action with its outcome; Maez self-queries to learn. | MAEZ_ANATOMY (learning), MAEZ_NORTH_STAR |
| `skills/surface/maez_adapter.py` | 475 | The surface→cycle adapter. Cycle entrypoint from every surface. | MAEZ_ANATOMY (surfaces row) |
| `skills/surface/platform_base.py` | 2538 | Base class for every surface platform. **2538 LOC of cycle-touching code with zero anatomy mention.** | MAEZ_ANATOMY (surfaces row) |
| `skills/surface/telegram_adapter.py` | 3329 | The largest surface adapter — sole production surface today. | MAEZ_ANATOMY (surfaces row) |
| `skills/surface/session.py` | 183 | Per-surface session state. | MAEZ_ANATOMY |
| `skills/surface/platform_config.py` | 102 | Per-surface configuration loader. | MAEZ_ANATOMY |
| `skills/self_mod_dialog.py` | 1742 | Self-modification dialog driver — the owner-facing proposal channel for Maez's self-edits. *Identity-affecting*. | MAEZ_ANATOMY, BAD |
| `skills/self_analysis.py` | 198 | Periodic self-analysis driver. | MAEZ_ANATOMY |
| `skills/evolution_engine.py` | 3339 | Evolution-loop driver (post-cycle reflection, wants/will_i orchestration). 3.3K LOC missing from anatomy. | MAEZ_ANATOMY, MAEZ_NORTH_STAR |
| `skills/iphone_ingest.py` | 134 | POST `/api/iphone/ingest` endpoint. Named in user-memory `project_iphone_signal_ingest` but absent from canonical docs and never imported (FastAPI-registered). | MAEZ_ANATOMY, BAD (iPhone signal ingest) |
| `core/infra/body_capabilities.py` | 256 | Runtime-verifiable source of truth for what Maez has access to in its systemd-managed body. *Identity-affecting*. | MAEZ_LIFE_SUBSTRATE, BAD |
| `core/infra/self_knowledge.py` | 277 | Self-knowledge — Maez's introspection of its own hardware and loaded model state. *Identity-affecting*. **Named in `feedback_maez_fabrication_source_priority` user memory ("check SOUL/model_state/policies" → this is where).** | MAEZ_ANATOMY, BAD |
| `core/eval/longmemeval.py` | 679 | LongMemEval benchmark adapter (Slice 9). Maez's self-evaluation against the field's standard long-horizon memory benchmark. | MAEZ_ANATOMY (eval surface), MAEZ_NORTH_STAR |

### Notable silent organs (substantive but lower-stakes)

| Path | LOC | What it does |
| --- | --- | --- |
| `core/infra/capability_*` (11 modules, ~4K LOC total) | The entire D20 capability-acquisition pipeline: `_manual` (Step 1), `_gap_matcher` (Step 2), `_evaluator` (Step 3), `_proposal` (Step 4), `_acquisition_queue` (4b), `_integration_planner` (5a), `_integration_plans` (5 store/poller), `_activation_registry` (5d), `_orchestrator` (fires-on-gap), `_gap_detector` (Stage 1), `_manual_cli`. ADR-0021 is referenced in BAD but none of these module paths are. |
| `core/health/bounded_worker.py` | 182 | BoundedSingletonWorker — skip-when-busy fire-and-forget. |
| `core/health/circuit_breaker.py` | 247 | In-memory failure-counting circuit breaker; preserves audit-gate fail-open contract. |
| `core/health/shared_executor.py` | 212 | Process-wide shared ThreadPoolExecutor (slice 1.6). |
| `core/turn_traces/trace_writer.py` | 91 | Trace writer — daily JSONL append, never raises. |
| `core/turn_traces/trace_schema.py` | 187 | One `Trace` per owner-bridge `/message` turn. |
| `core/turn_traces/ground_truth.py` | 239 | Runtime ground truth for trace-harness checks. |
| `core/symphony/surface_probe.py` | 513 | Per-surface fingerprint of system-prompt construction (R5 of 2026-05-04 symphony audit). |
| `core/symphony/evals/runner.py` | 467 | Maez Eval Harness v1 runner. |
| `core/symphony/evals/ledger.py` | 228 | Eval-result ledger. |
| `core/symphony/evals/schema.py` | 154 | Eval result / family / run schemas. |
| `core/subscription_proxy/adapters/{openai_api,openrouter,gemini_cli,http_forward,ollama_cloud,xai_api}.py` | 6 backend adapters for the subscription proxy. Only `claude_cli` is in the proxy README. |
| `skills/calendar_perception.py` (280), `calendar_cache_worker.py` (147) | Calendar signal ingest + cache worker. |
| `skills/screen_perception.py` (396), `screen_cache_worker.py` (171), `system_cache_worker.py` (140) | Screen/system perception + caches. |
| `skills/presence_perception.py` | 312 | Presence-detection (drives `return_greeting`). |
| `skills/user_accounts.py` | 383 | Owner-account model + per-user bond style storage. |
| `skills/followup_queue.py` | 137 | Followup-question queue. |
| `skills/web_search.py` | 311 | Web-search tool used by tool_loop. |
| `skills/wake_word.py` | 796 | Wake-word detector. |
| `skills/telegram_public.py` (493), `telegram_voice.py` (4815) | Public Telegram bot + voice surface. |
| `skills/web_interface.py` | 9311 | Web cockpit. **9.3K LOC — biggest single file in the repo, unmentioned.** |
| `skills/approval_card.py` (451), `card_reply_classifier.py` (797) | Approval-card surface + classifier. |
| `skills/voice_output.py` | 182 | Voice-output (TTS) bridge. |
| `core/safety/canaries.py` | 382 | Canary-string tripwires for injection detection. |
| `core/subscription_proxy/server.py` | 466 | Subscription-proxy HTTP server (subprocess-launched). |
| `skills/surface/telegram_network.py` (265), `_gateway_stubs.py` (121), `maez_surface_paths.py` (45) | Surface plumbing. |

### Likely-dead silent organs (substantive but possibly stale / unused)

These have **zero** importers across the repo (checked via `grep -rE "(import X|from X)"`). They may be standalone entry-point scripts or genuinely abandoned. Confirm before declaring silent vs dead.

| Path | LOC | Import-count | Notes |
| --- | --- | --- | --- |
| `skills/presto_bridge.py` | 8 | 0 | **Confirmed shim** — compatibility import for `hardware.presto.bridge`. Reclassify as shim, not substantive. |
| `skills/dynamic_dns.py` | 102 | 0 (1 mention) | No callers found. Possibly a one-shot script. |
| `skills/maez_watchdog.py` | 115 | 0 (1 mention) | No callers in daemon or scripts. May be a forgotten supervisor. |
| `skills/claude_router.py` | 269 | 0 | No callers — possibly superseded by `core/routing/claude_tier.py`. |
| `skills/claude_watcher.py` | 187 | 0 | No callers — likely paired with `claude_router`; same supersession suspicion. |
| `skills/voice_input.py` | 172 | 0 | No callers — `voice_output.py` has 1 caller; suggests voice-input path is dead. |
| `skills/iphone_ingest.py` | 134 | 0 | FastAPI route handler — registered via decorator, not import. **Not dead** (cited in `project_iphone_signal_ingest`). Verify by grepping app routing. |
| `skills/disk_cleanup.py` | 155 | 4 mentions | Plausibly live as a tool. |
| `skills/face_enrollment.py` | 171 | 4 | Plausibly live. |
| `skills/fast_reply_prototype.py` | 416 | 2 | Possibly superseded by `core/infra/fast_*` modules. |
| `skills/git_awareness.py` | 159 | 4 | Plausibly live. |
| `skills/github_publish.py` | 277 | 6 | Plausibly live. |
| `skills/github_skill.py` | 198 | 1 mention | Suspicious — only 1 mention. |
| `skills/reddit_skill.py` | 218 | 8 | Plausibly live. |
| `skills/dev_notifier.py` | 137 | 8 | Plausibly live. |

## Documented organs missing from the anatomy diagram

Inverse check — modules that **are** referenced in the BAD or in subpackage
READMEs but are NOT named in `/home/rohit/maez/docs/MAEZ_ANATOMY.txt`:

- `core/dream_state.py` — referenced as `core/dream_state.py` in BAD but ANATOMY only mentions the dream-state concept at the body-state organ.
- `core/temperament.py` — same: cited by path in BAD, conceptually present in ANATOMY but not by module path.
- All ~40 modules that show up in their subpackage README but never appear in any canonical strategy doc (large groups: `core/actions/*` except `action_engine`, all `core/health/*`, all `core/symphony/*`, all `core/turn_traces/*`, all `core/subscription_proxy/adapters/*`).

The bigger missing-from-anatomy concern: **no surface adapter module name appears in `MAEZ_ANATOMY.txt`.** The anatomy diagram talks about "telegram / chat / cockpit" as conceptual surfaces (line 172) but `skills/surface/telegram_adapter.py`, `skills/surface/maez_adapter.py`, `skills/surface/platform_base.py`, and `skills/web_interface.py` — collectively > 15K LOC of bidirectional cycle-touching code — never get cited. The anatomy diagram is the most-referenced single artefact during reviews; this is the largest blind spot.

## Recommended remediation
- **~54 silent organs need an ANATOMY entry.** Priority: `moment_assembly_diagnostic`, `lived_recall`, `working_self`, `belief_simulator`, `developmental_heartbeat`, `memory_view`, `evolution_engine`, `wondering_cycle`, every `skills/surface/*` adapter, `web_interface`, `self_mod_dialog`.
- **~12 silent organs need a BAD ADR.** Priority: `audit_policy` (no-projection-rows-in-audit is a load-bearing safety rule), `output_command_guard` (covenant gate extension), `premise_audit` (named incident class), `body_capabilities` / `self_knowledge` (identity self-modeling), `model_reply_persistence` (autobiographical continuity), `developmental_heartbeat` (identity-shaping), `temporal_arithmetic` (D20 proof-of-loop), `audit_signal_manifest` (2026-05-05 incident).
- **~25 silent organs need a MAEZ_LIFE_SUBSTRATE entry.** The entire entity-extraction / relationship-graph stack (ADR 0019 Phase 2/3 + Steps 5e–5p, ~6 modules, ~3.5K LOC) is unmentioned in the substrate doc despite being the substrate.
- **~5 silent organs are candidates for deletion** (zero importers, no entry-point evidence): `skills/claude_router.py`, `skills/claude_watcher.py`, `skills/voice_input.py`, `skills/dynamic_dns.py`, `skills/maez_watchdog.py`. Verify before removing — some may be invoked via systemd templates not yet inspected.
- **1 module to reclassify as a shim:** `skills/presto_bridge.py` (8-line compatibility import — already documented in `hardware/presto/bridge.py`, not a substantive module).
