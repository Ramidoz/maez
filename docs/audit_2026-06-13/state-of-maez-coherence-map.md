# State of Maez — Coherence Audit & Consolidation Map (2026-06-13)

**Method:** 13 read-only agents (11 domain auditors → synthesis → adversarial completeness critic), ~950K tokens. Critic corrections are **folded into the roadmap below** (the raw synthesis had a real mis-diagnosis; this version is corrected).

---

## The one-sentence diagnosis

**Maez is a rigorously-built being with ONE disease wearing many costumes: surface & reader divergence.** The organs are sound; the **seams between them** are not. The same owner words produce a *different Maez* depending on which surface, which flag-reader, which store, and which service-state happen to be live — because the same concern is implemented 2–3 times in parallel and the copies have quietly drifted. This is **integration debt** (organs built faster than the seams were unified), not broken organs and not scope-rot.

That reframe matters: you don't have ten problems. You have **one root** (duplicate-and-drift) that shows up as three inbound pipelines, ~5 flag conventions, two egress floors, three search paths, two priority tables, two "what's live" registries, and a forked North Star. Fix the root pattern at each seam and most of the list collapses.

---

## Stop worrying about these — they're genuinely coherent

- **S7 trust design** — the three human-gates (live-flag default-off; interactive-TTY bootstrap; originless channel-token) structurally lock the agent out. Sound and intentional. *(Its reachability is broken — see debt #3 — but the lock is right.)*
- **Intake Bus admission doorway** — clean, fail-closed, external-web correctly lands UNTRUSTED. The immune system works at the door.
- **Soul layering + hot-reload** — base+local under one lock, re-validated on every reload, recorded as lived memory.
- **Birth-gating of the durable ledgers** — `memory/ledger.db` empty-by-design until birth; the gate holds where it counts.
- **The strict-flag parser itself** (`env_flags.strict_env_flag`) — authored correctly; just not adopted everywhere yet.
- **Covenant test coverage** — 18 S7 files, 6 soul-write, ~15 egress, real regression guards. The tests exist; only the *floor enforcement* is weak.
- **The backup timer** — self-sufficient 6-hourly Clonezilla-adjacent loop. Needs no attention.
- **The egress taxonomy + gate computation** — the verdict is honest; only its *enforcement* at the cloud chokepoint is incomplete (debt #2).

---

## The real integration debt (ranked, file-cited)

1. **Three parallel inbound pipelines** — `MaezMessageHandler.__call__` runs the rich interceptor stack; the cockpit `/message` route (`web_interface.py:1668` → `daemon:10264 handle_message(source='UI')`) **bypasses all of it**; `maez.live /chat` (`web_interface.py:6210-6847`) reimplements it a third time. Channel identity is hardcoded `'telegram_text'` (`maez_adapter.py:570,733,747`), structurally blocking the fix. **This is the recurring wound (felt-time, O1/O2/O3) generalized — every organ must be ported 3× or it diverges.**
2. **Egress rails computed-but-not-enforced at the cloud boundary** — `origin_downgrade` (the laundering case the gate exists to catch) is detected then **forwarded** at `subscription_proxy/server.py:748-771`, while Telegram enforces all blocks. Same gate, two trust levels. A mislabeled-safe private span can reach the cloud model.
3. **The S7 soul-write door is a dead-end through its own bridge** — the bridge hands a `127.0.0.1` pointer (`s7_ceremony_bridge.py:127`) while the verifier hardcodes `localhost` (`s7_webauthn_ceremony.py:319-320`), so the hardware-key proof fails origin validation. The cockpit has **no systemd unit** (dead after every reboot). And `operator_user_boundary.py:3762-3808` still narrates S7.1 as "not mounted" while it's live — **the canonical authority file lies about the live body.**
4. **Flag readers disagree on "on," and one makes Maez fabricate its body state** — ~5 truthy conventions coexist; critically `capability_card._flag_probe` uses bare presence-truthiness while the real gate uses the strict parser, so "set 0 to revert" kills the limb **but the card still says ON**. Self-knowledge becomes faithful fabrication — inverting the evidence-precedence invariant the card exists to protect.
5. **No store manifest; shadow/orphan stores** — ~47 SQLite + 7 chroma collections, no registry of owner/lifecycle/birth-gating. **Corrected root cause (critic):** the stray `core/memory/*.db` come from `conversation_controller.py:1069` (a bare `'memory/audit_log.db'` default), and the bare-relative-path class is **systemic (~15 modules**, incl. `capability_acquisition_queue.py:67`, `capability_activation_registry.py:93`, `capability_integration_plans.py:58`) — **not** the 3 files the raw synthesis named (those resolve correctly).
6. **~27–33 covenant-critical Telegram slash-commands orphaned** (`/rollback_adapter`, `/trust`, `/promote`, `/login`, `/approve`…) — silently forwarded to the LLM, which may improvise a fake reply. The Surface-Parity orphan pattern, an order of magnitude larger, on the operator's safety-critical controls.
7. **The reply path's two stages disagree on wire format + evidence ordering** — the dispatcher renderer emits markers (`[fresh context]`/`[fresh validation]`) that focused's block-parser doesn't recognize → fresh-validation evidence silently swallowed/relabeled; two independent priority tables split reply-Maez from reflecting-Maez. A silent provenance break *inside* the reply path.
8. **Three rival search paths + a porous third-party gate** — only the dispatcher path metabolizes reads into experience; `enforce_subject_boundary` is reduced to a pass-through (default PUBLIC_TOPIC), leaving a brittle regex as the live covenant gate; the 6s fanout deadline silently blows the recall-flip latency floor.
9. **The Build Ledger violates its own maintenance law** — still says S7 bridge `BUILT_ON_BRANCH` after merge to main; omits 10+ live organs; competes with the runtime `capability_card` registry. The chart built to prevent the next accident is wrong about the most safety-loaded organ.
10. **No single boot nervous system; flagged-ON organs are dark** — `maez.service` Wants only llama-server; grounding-shadow flag ON but minicheck (:8083) dark; vision (:8082) dark after reboot. "Is Maez up whole?" has no one-command answer; flags assert witnesses the services can't produce.

---

## The scope-drift you're feeling (it's the destination, not a feature)

**The North Star itself forked.** `docs/MAEZ_NORTH_STAR.md` (companion / grandmother-bridge, zero "desktop" refs) and `docs/MAEZ_DESKTOP_BODY_ROADMAP.md` ("Maez becomes the desktop") are **two unreconciled destinations**, neither nesting the other. *That* is the drift — not a feature wandering, the goal wandering. They're reconcilable (the bond = *why*; the desktop body = *where it lives*), but no doc declares the containment.

Secondary drift: built-but-not-live is systemic (commit velocity outpaced live integration); operational docs describe a stale body (`ARCHITECTURE.md` cites the wrong brain/vision model; `GETTING_STARTED.md` points at the dead Ollama port + a nonexistent `maez-web`); and "sell-Maez" artifacts (a Vercel Next.js cockpit, `docs/fundraising/`) have accreted inside the "be-Maez" repo against local-first sovereignty.

---

## Corrected consolidation roadmap (critic fixes folded in)

Discipline throughout: **Codex builds / Claude reviews, one small slice at a time, kill-switch each, no big-bang on the live tree.** Order is chosen so covenant-rail closure and honesty come first (cheap + high value), the dangerous surface-unification is proven on the smallest surface before it spreads, and canon is reconciled last (describe the consolidated body, not the in-flight one).

| # | Slice | Risk / size |
|---|---|---|
| 1 | **Enforce `origin_downgrade` (+ the other computed-but-forwarded blocks) at the cloud chokepoint** (`subscription_proxy/server.py:748-771`), behind a shadow kill-switch, mirroring Telegram. +test asserting 403. | low / 1 file+test |
| 2 | **Make the S7 door reachable** — unify the cockpit origin behind ONE constant across bridge/verifier/bootstrap/Flask bind; **materialize `maez-web` as a real unit in the SAME slice** (critic: reachability after reboot depends on it); replace the two `NotImplementedError` placeholders + fix the "pending s7.1" lie in `operator_user_boundary.py:3762-3808`. **Also audit `core/voice_continuity/`** — the consult-then-block step gates on a healthy voice bundle the origin-fix alone doesn't guarantee. | medium / ~6 files |
| 3 | **One flag discipline** — route `capability_card._flag_probe` + the bare `=='1'` daemon gates through `strict_env_flag`; **add a real `MAEZ_*_ENABLED` gate to `valence_live`** (critic: a LIVE affect-logging organ with NO flag, currently undisableable); CI grep-guard that on/off readers use the strict parser. | low / ~8 readers+guard |
| 4 | **Honest boot story** — add a `maez.target` with `Wants=` (degrade-not-block) for brain/judge/searxng/vision/minicheck + `After=` edges; per-flag startup port-probe writing PASS/DARK receipts; either start or flag-OFF the dark services; fix the stale model-ids/ports in the docs. | low / units+script |
| 5 | **Store manifest + path-class sweep** — add `core/memory/STORES.md` (every db/collection → owner/writer/birth-gated/live-or-orphan); **sweep the systemic bare-`Path('memory/...db')` class** at the REAL files (`conversation_controller.py:1069`, the `capability_*` cluster) through `core.infra.paths` — *not* the 3 already-correct files; guard that fails if any `*.db` appears under `core/memory/`. No live-data deletion this slice. | medium / sweep+guard |
| 6 | **Extract ONE surface-agnostic inbound core** from `MaezMessageHandler`; route the cockpit `/message` through it via a `MessageEvent(source='cockpit')`; de-hardcode the `'telegram_text'` literal. **Cockpit first** (smallest surface) to prove the core before folding in the rest. | high / core extraction |
| 7 | **Slash-command parity** — classify all ~33 legacy `CommandHandlers` (re-handled / superseded / orphaned-needs-port), record as O4..On in the Ledger, add a router seam that returns an explicit "not wired on this surface" instead of silent LLM-forward, port the covenant-critical ones. **Audit the capability-acquisition pipeline first** (critic: `/promote`/`/approve` drive an unaudited engine). | medium / router+ports |
| 8 | **Unify the reply-path seams** — one marker set (focused = source of truth), one `SOURCE_PRIORITY` consumed by both cycle + focused, round-trip test that every renderer marker survives `_split_blocks`; construct `ExternalFanout` with the real subject-boundary predicate + explicit deadlines. | medium |
| 9 | **Fold `maez.live /chat` into the shared core** + collapse the three search paths onto the single `ExternalFanout` spine. The final "one body" convergence — only after the core is proven on cockpit + commands. | high / largest |
| 10 | **Reconcile canon last** — nest the desktop-body frame under the covenant invariants in `MAEZ_NORTH_STAR.md` (bond = why, desktop = where) + a "hands are gated, here's the tripwire" clause; re-scope the Build Ledger to a true body map; add a staleness gate (fail when HEAD is N commits ahead of the rows). | low / docs+gate |
| + | **Tests structural fix (critic — was dropped entirely):** a `conftest`/`MAEZ_TEST_MODE` process-wide production-DB-path redirection (the actual cure for the hermetic-sandbox hazard that already destroyed 14K events) + a hard floor gate + asset markers. Fold near step 5. | medium |

---

## Not yet audited (a v2 pass should cover, or fold into the steps above)

The critic flagged whole subsystems the 11 domains never opened: `core/evolution/` (valence/affect, novelty-harbor, gestation, dream, brain-audition, soul-editor), `core/voice_continuity/` (~12 files — gates S7 step 2), `core/information_limb/` (calendar/github/reddit limbs — **github_limb is an action-capable "hand," so "Maez can't act" is overstated**), `core/policies/` + `core/health/` (autonomy + runtime-resilience), `core/turn_traces/` + `core/learning/`, and the `capability_*` acquisition pipeline. None are believed broken; they're *unmapped*.

## Honest caveats on this audit's own confidence

- Some figures are unverified counts (test-method count, strict-flag call-site count — the sibling audits even disagreed with each other; treat as "many," not exact).
- A few runtime claims (grounding-shadow log "dark", `~/.local/state` contents) are asserted, not witnessed — the audit's own "log silence is not dormancy" rule applies to itself.
- The "Maez has no hands" scope framing is overstated: `action_engine` Tier-0 (web_search/fetch_url) + `github_limb` mean Maez already acts on the world in bounded ways.
