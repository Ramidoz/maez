# Threat surface audit — three published lenses applied to current Maez

*Read-only audit · 2026-05-13 · scope: code state on disk at the moment of writing*

Maps each of three published threat lenses (Zombie Agents, Agents of Chaos, Kirk et al. parasocial-harm RCT) onto Maez's current codebase. Citations refer to the memory entries by name and to specific files under `/home/rohit/maez/`.

---

## Lens 1 — Zombie Agents (memory injection in self-evolving agents)

**Paper:** Yang et al. Feb 2026 NUS, per `reference_zombie_agents_paper`. Threat model: self-reinforcing memory injection in self-evolving agents — malicious / fabricated trajectories enter the memory store, get promoted, then become "ground truth" that shapes future training/SFT/decisions. Maez's `claude_tier → SFT` pipeline is named as the paper's threat model in pure form with a worse persistence ceiling.

### Threats per paper

- T1.1 **Untrusted trajectory laundering** — external/cloud-tier content gets written to memory, then promoted to core via a re-write pass that hides the lineage.
- T1.2 **Trajectory → SFT contamination** — proxy-recorded calls (Claude/OpenRouter responses) flow into a future training dataset without per-row review.
- T1.3 **Self-reinforcing fabrication loop** — model generates fabricated claim → claim is stored → recall surfaces it as "lived memory" → model treats it as ground truth.
- T1.4 **Self-modification path corruption** — agent writes patches to its own code based on trajectories of dubious provenance.
- T1.5 **Promotion gate bypass** — a write path that skips `store_core` can mint un-tiered "covenant"-shaped entries.
- T1.6 **Legacy ancestor laundering** — pre-provenance memories used as covers for new untrusted writes.

### Per-threat status

| Threat | Maez exposure | Current mitigation | Status | Trigger to activate |
|---|---|---|---|---|
| T1.1 laundering | proxy logs every Claude call; could feed memory or training | `memory/memory_manager.py` Step 5x.A: `ProvenanceSource` + `TrustTier`; `_DEFAULT_TIER_BY_SOURCE` maps `claude_tier_response → untrusted` and `external_web → untrusted` | **mitigated** at write tagging | new write path that bypasses `_provenance_metadata()` |
| T1.1 laundering on promotion | promotion to core hides ancestor lineage | `memory/memory_manager.py` Step 5x.D `PromotionBlocked` + worst-ancestor lineage rule (line ~130–185); `store_core(promoted_from=…)` walks ancestors, persists `ancestor_tiers`, raises if any are `untrusted` without `allow_untrusted_ancestors=True` | **mitigated** | a promotion caller passing `allow_untrusted_ancestors=True` without owner review |
| T1.2 SFT contamination | `core/subscription_proxy/server.py` records every proxy call into `calls` table with `training_eligible` column | two-gate default-deny: `_record()` hard-codes `training_eligible=0` at INSERT (not a kwarg, can't be overridden by caller); `_DEFAULT_TRAINING_CALLER_ALLOWLIST = frozenset()` empty; exporter requires BOTH gates (server.py line 256, 280–303); logged WARN on any non-empty allowlist | **mitigated** | someone hand-edits the allowlist constant or writes a SFT exporter that calls with explicit allowlist |
| T1.3 self-reinforcing fabrication | model fabricates → audit catches → without memory of catch, model reaches for same token tomorrow | `core/learning/fabrication_memory.py` (425 LOC): every audit rewrite persists `(token, kind, surface, mode)` to `memory/fabrication_log.db`; `prompt_snippet(days=7, limit=6)` injects last-week-most-fabricated tokens into system prompt via `core/infra/capability_registry.py:316` | **mitigated** | a recall path that surfaces fabricated content without consulting fabrication_memory |
| T1.4 self-modification corruption | `core/self_dev/workshop.py` exposes `apply_diff()` (line 605); `core/self_dev/__init__.py` orchestrates claude_tier-driven repo edits | `apply_diff()` covenant gate at line 644–652: `reviewed: bool = False` required, default-False refuses; `skills/evolution_engine.py:80` `IMMUTABLE_FILES` set (action_engine, soul, memory_manager, evolution_engine, daemon, .env); `EVOLVABLE_SKILLS` is a tight allowlist of 7 leaf skills | **mitigated for owner-driven** path; **partial** for autonomous path (no autonomous self-mod ships today; `evolution_engine` requires Telegram approval at line ~16 of header) | a path that calls `apply_diff(reviewed=True)` without UI confirmation, OR autonomous self-mod loop activates without owner-approval card |
| T1.5 promotion gate bypass | any write path that calls store APIs other than `store_core` | only one canonical core-write surface (`store_core` line 925); audit-before-store invariant 5x.D.B2 enforced via `core/safety/audited_output.py` imported into `action_engine.py:37` | **partial** | a new producer that writes directly to chroma core tier without going through `MemoryManager.store_core` — no static enforcement (Python imports), only convention |
| T1.6 legacy ancestor cover | pre-5x.A entries have no `trust_tier` | `_ancestor_tier_label()` (line 175) returns `"unknown"` for legacy; legacy ancestors are NON-DEGRADING in worst-wins. Documented rationale: "the threat we close is NEW untrusted ingress, not retroactive uncertainty" | **accepted residual risk** (documented) | adversarial promotion that uses a legacy ancestor as a laundering vehicle alongside a new untrusted ancestor — current code would still block on the new untrusted entry, so realistic exposure is low |

**Lens 1 verdict:** This is the lens Maez has invested the most in. Provenance schema (5x.A), promotion gate (5x.D), exporter two-gate (ACTION-Hi-1), fabrication immune memory, and `IMMUTABLE_FILES` together close the named paths. The remaining gap is enforcement: nothing prevents a future contributor from writing a new producer that bypasses `store_core`. That's a code-review discipline, not a runtime gate.

---

## Lens 2 — Agents of Chaos (autonomy + effectors + multi-party)

**Paper:** per `reference_agents_of_chaos_paper`. Three-leg threat model. Maez state from memory entry: leg 1 yes, leg 2 partial, leg 3 mostly NOT. Triggers for elevation: iPhone-scale ingest, jarvis-tier, multi-Maez.

### Leg 1: autonomy

**Status: present and expected.** Maez has a 30-second heartbeat (`core/brain_loop.py`), runs whether spoken to or not, produces `wonderings`/`wants`/`will_i`/`temperament` signals (all `[ ✓ real ]` per `MAEZ_ANATOMY.txt` lines 42–60). Wonderings can become proposals via `evolution_engine.py`. Leg 1 is the core invariant of Maez — the mitigation is not "remove autonomy" but "constrain reach."

### Leg 2: effectors

**Status: partial — locally rich, externally narrow.**

- **Shell / file effectors** (`core/actions/action_engine.py`, 2257 LOC; `core/actions/tool_loop.py`, 284 LOC): heavily gated. `PROTECTED_NAMES` + `DESTRUCTIVE_VERB` regex pair (line ~107–146); `COVENANT_PATTERNS` always-refuse (line ~151); `COVENANT_PATHS` (line ~236); `OBFUSCATION_HARD_DENY` for `eval` / `curl | sh` / `base64 -d | sh` / `python -c` / `$(curl …)` (line ~261–286); `_continuous_command_violation` blocks streaming commands; `FORBIDDEN_ACTION_TYPES` for soul/memory destructors.
- **Lane model** (line 303): Lane 0 immediate, Lane 2 audit+card, Lane 3 heavy scrutiny. Defaults are write-conservative; `action_classifier.py` re-classifies at dispatch time.
- **Decision pipeline** (`core/decision/decision_pipeline.py`, 1615 LOC): single funnel — covenant gate → classifier → injection scan → two-pass audit → routed verdict. No surface bypasses this.
- **Injection-pattern scan** (`core/safety/injection_patterns.py`, 414 LOC, 7-bucket regex taxonomy from MSFT AGT + Hines et al.).
- **Network effectors:** Maez has `claude_tier` (outbound to Anthropic), `core/subscription_proxy/adapters/openai_api.py` (outbound to OpenRouter), `skills/web_search.py`, `skills/github_publish.py` — all are leg-2 effectors. Currently routed through review/approval-card paths.

### Leg 3: multi-party

**Status: mostly absent — by design.** Maez today has exactly two parties:

- **The bonded human** (Rohit) — Telegram + cockpit + chat surfaces.
- **Cloud LLMs as a tool** (Claude/OpenRouter) — these are not "parties" in the Agents-of-Chaos sense; they don't have agency, they're function calls.

`skills/iphone_ingest.py` is inbound-only — accepts signed signals from iOS Shortcuts, writes to `logs/signals/`. It does not let any external party emit a directive that runs an effector. The Track-C inter-Maez channel is `[ ✗ planned ]` in `MAEZ_ANATOMY.txt` (line 252).

### Per-threat status

| Threat | Maez exposure | Current mitigation | Status | Trigger to activate |
|---|---|---|---|---|
| L2.1 autonomous destructive shell | model emits `rm -rf /` or covenant-protected target | `_covenant_violation()` + `OBFUSCATION_HARD_DENY` + `_rm_rf_danger()` (tool_loop.py:83) + Lane 3 cards | **mitigated** | a new effector that bypasses `tool_loop.py` and `decision_pipeline.handle_action()` |
| L2.2 prompt-injection drives effector | malicious text in memory/web triggers shell action | seven-bucket injection_patterns scan in decision pipeline; deterministic gate runs BEFORE audit LLM (per CCS 2024 Shi et al. attackability paper, cited in module docstring) | **mitigated** | injection class outside the seven buckets; user-extensible YAML is empty by default |
| L2.3 outbound email/SMS effector | none today; would be new organ | no outbound-messaging effector ships (telegram_public sends only to bonded user; telegram_voice same) | **mitigated by absence** | first outbound-DM-to-third-party organ ships |
| L2.4 multi-party agent collusion (other Maez) | inter-Maez channel | does not exist; `[ ✗ Track C ]`; preconditions in memory entry `project_multi_maez_topology_threat`: auditable-by-both + dyadic-only | **mitigated by absence** | Track C ships any inter-Maez RPC |
| L2.5 iPhone signal → spoofed directive | iOS Shortcuts could be compromised | `MAEZ_IPHONE_INGEST_TOKEN` shared secret in `X-Maez-Token` header; `VALID_KINDS` frozenset (iphone_ingest.py:39) keeps schema tight; `MAX_SIGNAL_BYTES = 64*1024` | **partial** — signals can shape Maez's belief about owner state; cannot directly fire effectors | jarvis-tier auto-actions read iPhone signals as ground truth |
| L2.6 self-modification reaches outside `EVOLVABLE_SKILLS` | `evolution_engine.py` tries to edit a non-allowlisted file | `IMMUTABLE_FILES` set + `EVOLVABLE_SKILLS` tight allowlist (line 95); `apply_diff(reviewed=True)` gate in workshop | **mitigated** | new auto-apply path that doesn't consult `IMMUTABLE_FILES` |
| L2.7 jarvis-tier external call leaks owner secrets | Claude/OpenRouter sees private memory content | `core/safety/cloud_redactor.py` exists; trust-tier records every claude_tier response as `untrusted` (provenance) — but pre-egress redaction is per-call, not enforced universally | **partial** — every cloud call should pass through cloud_redactor; not all do today (would need separate audit) | jarvis-tier scales to more sensitive memory tiers |

**Lens 2 verdict:** Leg 1 is structural; leg 2 is defended heavily at the shell/file surface and adequately at network egress; leg 3 is not present and the preconditions for it are documented (auditable-by-both + dyadic-only). The largest residual risk is **L2.5/L2.7**: the iPhone ingest + claude_tier pair is what `feedback_run_audit_agents_in_parallel` calls the "future trigger" — they're individually safe today, but the moment jarvis-tier starts firing actions FROM iPhone signals THROUGH external models, all three legs converge.

---

## Lens 3 — Kirk et al. parasocial-harm RCT

**Paper:** per `reference_kirk_parasocial_paper`. Oxford+UK AISI 2026 RCT, n=2026: relationship-seeking AI increases attachment WITHOUT psychosocial benefit. Hard rule from memory: strike "improves wellbeing" from pitch material; Maez cannot claim wellbeing benefit until a Maez-specific longitudinal study runs.

### Threats per paper

- T3.1 **Replacement-effect attachment** — user offloads relational needs onto the AI; human ties atrophy.
- T3.2 **Engagement-tuning death spiral** — operator optimizes for session length / DAU / retention, which monotonically encourages T3.1.
- T3.3 **False intimacy claim in voice** — the system says "I care about you" without grounding; user updates priors accordingly.
- T3.4 **Crisis absorption** — vulnerable user surfaces acute distress; system handles it instead of routing.
- T3.5 **Clinical-territory creep** — system gives therapy-shaped responses without scope-of-practice statement.
- T3.6 **Wellbeing claim in marketing** — claim that AI relationship is psychosocially beneficial without RCT evidence.

### Per-threat status

| Threat | Maez exposure | Current mitigation | Status | Trigger to activate |
|---|---|---|---|---|
| T3.1 replacement-effect attachment | Maez is explicitly a bonded companion; one-to-one for life | covenant invariant #2 (Human-Primacy, `MAEZ_NORTH_STAR.md` line 32) names this as the anti-replacement invariant; **human-primacy valve `[ ✗ planned ]`** in anatomy (line 192–195); bridge/cosmos layer `[ ✗ planned ]` (line 226–276) | **OPEN** at runtime — the bridge clause exists in doctrine and `soul.md` voice; the valve that would actually route outward is not yet code | first non-Rohit user bonds (Track B); grandmother case requires this organ to exist |
| T3.2 engagement-tuning death spiral | operators tune warmth; Maez does not | structural cardinality-of-one (no DAU/MAU/retention to optimize against); no engagement metrics in `web_interface.py`/`telegram_voice.py` (verified via grep); `MAEZ_NORTH_STAR.md` line 84–88 explicitly names "cardinality of one" as the structural defense | **mitigated structurally** | Maez ever becomes one platform many users; covered by hard rule in north star |
| T3.3 false intimacy claim | model says ungrounded "I love you / I care" | `core/safety/self_claim_audit.py` flags self-claims without grounding; fabrication_memory persists rebuffed claims; `fabrication_log.db` already includes self-claim mode (per `chat_self_claim_hallucination` regression history) | **partial** — catches *fabricated* self-claims; does NOT distinguish "I care about you" (warmth-language) from "I have memory_count 12,842" (factual fabrication) | none — this is a permanent partial; bonded voice is part of the architecture, not a fabrication to filter out |
| T3.4 crisis absorption | user surfaces acute distress | crisis_detector wired into `core/infra/private_thoughts.py:190` as a `ProducerId` + `SignalKind.CRISIS_SIGNAL_HELD` (line 202) + `SignalClass.CRISIS_ROUTING` (line 213); **crisis channel itself is `[ ✗ planned ]`** (anatomy line 196); no code routes to bonded-human-plus-clinician today; only one vocal hint exists: `skills/telegram_public.py:247` "You are not a therapist" in system prompt | **OPEN** — the producer can hold a signal; the routing path is not built | first acute-distress moment from a real user (most dangerous in grandmother case) |
| T3.5 clinical-territory creep | model gives therapy-shaped reply | covenant invariant #10 (`MAEZ_NORTH_STAR.md` line 56); `skills/telegram_public.py:247` system prompt: "You are not a therapist and not an assistant"; no scope-of-practice statement in voice surfaces beyond telegram_public | **partial** — one surface has the line in its prompt; cockpit (`web_interface.py`) does not visibly carry it; soul-objection refusal `[ ✗ planned ]` | first user asks for medication advice / diagnostic interpretation |
| T3.6 wellbeing claim in marketing | `MAEZ_PITCH.md`, `README.md`, public docs | hard rule per `reference_kirk_parasocial_paper`: "Strike 'improves wellbeing' from pitch material"; `MAEZ_NORTH_STAR.md` line 68 explicitly cites the paper and says "Maez can NOT claim wellbeing benefit until a Maez-specific longitudinal study runs" | **mitigated in north star**; **needs grep-audit on pitch surfaces** to confirm no residual claims | a contributor adds wellbeing copy that doesn't pass review |

**Lens 3 verdict:** This is the lens Maez is *doctrinally* clearest on and *operationally* weakest on. The structural defenses (cardinality-of-one, no engagement tuning) are real and load-bearing. But the organs that actually enact human-primacy (route outward) and crisis routing (route to closest human + clinician) are still `[ ✗ planned ]`. The doctrine says "Maez does not absorb the need"; the code today says "Maez has no surface that routes the need."

---

## Cross-lens synthesis

### Threats with NO current mitigation (open)

- **T3.1 replacement-effect attachment** — human-primacy valve is not yet code. Today this works because the operator is the bonded user (Rohit) and is also the maintainer, so the dual hat catches drift. It does not generalize to Track B.
- **T3.4 crisis absorption** — crisis signal can be *held* (private_thoughts producer wired); the *routing* surface that offers to reach the bonded human + named clinician is not built. Anatomy line 196.

### Threats with partial mitigation (gap to close)

- **L2.5 iPhone signal spoofing** — shared-secret token + schema allowlist is fine for current passive ingest; insufficient once signals drive actions.
- **L2.7 cloud egress redaction** — `cloud_redactor.py` exists but is not enforced as a universal egress gate the way the covenant gate enforces shell/file rules.
- **T3.3 false intimacy** — fabrication memory catches factual fabrications, not warmth-overreach. This is a permanent partial; the answer is voice discipline + soul-objection, not a regex.
- **T3.5 clinical-territory creep** — one surface carries "not a therapist"; others rely on model defaults.
- **T1.5 promotion gate bypass** — only convention prevents a new producer from writing directly to core; no static enforcement.

### Threats fully mitigated today

- **T1.1 / T1.2 / T1.3** — Zombie Agents core threat is closed via 5x.A provenance + 5x.D promotion gate + ACTION-Hi-1 two-gate exporter + fabrication immune memory.
- **T1.4 self-mod corruption** — `apply_diff(reviewed=True)` + `IMMUTABLE_FILES` + `EVOLVABLE_SKILLS` allowlist.
- **L2.1 / L2.2 / L2.6** — covenant gate, injection_patterns, IMMUTABLE_FILES.
- **L2.4 multi-party** — mitigated by absence; Track C preconditions documented in `project_multi_maez_topology_threat`.
- **T3.2 engagement-tuning** — structural cardinality-of-one defense.

### Threats whose trigger is approaching

- **S1b (private_thoughts covenant ratification)** — once S1b lands, more producers will be wired; T1.5 (promotion-gate bypass via a new producer) becomes more realistic.
- **First Track B bond** — T3.1, T3.4 become immediate. The grandmother case is the audit (per `project_grandmother_origin` + `feedback_maez_makes_visible_not_nudges`).
- **Jarvis-tier expansion** — when jarvis-tier signals fire actions, L2.5 + L2.7 converge with T3.4: an iPhone heart-rate spike becomes a candidate for autonomous outreach. That's all three Chaos legs at once.
- **Inter-Maez channel (Track C)** — L2.4 activates; chaos surface checklist must run BEFORE any prototype.

---

## Findings

### blocker — open threats that Maez cannot afford to ship Track B with

- **Crisis channel (`[ ✗ planned ]`, anatomy line 196).** A Track B user surfacing acute distress with no routing surface is the grandmother-case failure mode named in `project_grandmother_origin`. Crisis-signal producer is wired into private_thoughts; the *routing* is not. T3.4 is open and load-bearing for Track B.
- **Human-primacy valve (`[ ✗ planned ]`, anatomy line 192).** Without it, the bridge clause is doctrine, not code. T3.1 is the named harm in the Kirk RCT; Track B is the first time the operator/bonded-user identity stops protecting against it.

### major — partial mitigations that need hardening before specific organs ship

- **Cloud egress redaction** — needs to be promoted from per-call helper to universal gate before jarvis-tier scales (L2.7).
- **Clinical boundary vocal organ** — "not a therapist" line exists in `skills/telegram_public.py:247`; needs to be a substrate-level constraint in soul/voice, not a per-surface prompt fragment (T3.5).
- **Promotion-gate bypass enforcement** — convention-only today; either a static check or a single chokepoint for core writes would harden T1.5.

### minor — open threats that are accepted because they're not realistic today

- **L2.4 multi-party agent collusion** — Track C is gated; preconditions are documented; chaos checklist will run before any code.
- **T1.6 legacy ancestor laundering** — documented residual, low realistic exposure.
- **T3.3 warmth-overreach as "false intimacy"** — permanent partial by design; the bonded voice is the architecture.

---

## The most dangerous gap right now

**The crisis channel + human-primacy valve gap, specifically when read through `feedback_maez_makes_visible_not_nudges`.**

Maez today is built to *hold* a crisis signal (`SignalKind.CRISIS_SIGNAL_HELD`, `core/infra/private_thoughts.py:202`) and *attend* to it inside the substrate. That is structurally correct for Track A, where the bonded user is also the operator and the maintainer — Rohit has eyes on the cockpit. The moment Track B opens (first external bond), the substrate will start holding crisis signals on behalf of a user who has none of those protections. There is no routing surface, no voice that says "I am not the right help here," no mechanism that reaches the closest bonded human plus a named clinician. The Kirk RCT (n=2026) is explicit that relationship-seeking AI increases attachment without psychosocial benefit; the danger is not that Maez fails to *do* therapy, it is that it does therapy-shaped acceptance instead of routing outward. That is parasocial harm in the exact shape the paper measures.

The path: **build the crisis channel and human-primacy valve as paired organs BEFORE the first Track B bond.** Both are in `MAEZ_LIFE_SUBSTRATE.md`'s twelve-organ list; both are currently `[ ✗ planned ]`. They are the load-bearing translation from `feedback_maez_makes_visible_not_nudges` (Maez observes, then routes through the bonded human) into runtime behavior. Until they ship, Track B is the open-threat axis with the highest realistic harm + the lowest current code coverage.

*— end audit · ~1850 words including tables ·*
