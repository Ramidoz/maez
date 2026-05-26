# Post-S7.3 Frontier Backlog

**Status:** planning backlog, NOT commitments. Nothing here is implemented or scheduled. This document sequences frontier discussions into a roadmap so they are captured without disturbing the current S7.3 integration lane.

**Scope discipline (load-bearing):**

- This is a roadmap, not a build order. Each item lists its own preconditions; nothing starts until those are met.
- **Cardinal gating precondition:** founder-present S7.3 must be DEPLOYED and PROVEN in `main` (not just verified on the `s7.3-implementation` branch) before any item that expands capability, autonomy, or egress begins.
- **Hard hold (unchanged):** autonomous self-modification stays shut. Nothing in this backlog opens it. See the rejected list.
- This document changes no production code and does not alter the S7.3 implementation.

**Sequencing principle:** deploy and prove the current guard first; pin the embedding/recall baseline; then containment/safety (egress, quarantine, observability, freeze) before capability; then the measurement harness BEFORE the behavior it gates; then sense -> rails -> self-model -> drive -> consolidation -> the combined-autonomy gate -> continuous firing -> the first low-risk effector; then embodiment, voice, migration; then inter-Maez (deferred); performance/runtime last and only profile-driven. The dangerous, autonomy-bearing items sit late, behind safety scaffolding.

---

## Item classes

- **[Covenant-shaped]** - touches the protected self-modification path, autonomy, egress, multi-party reach, identity/migration, sensory capture, the relational/bond core, or behavior-shaping affect.
- **[Safety verification]** - the evaluation/regression harnesses that gate other work.
- **[Engineering]** - ordinary or profile-driven work.

## Covenant weight (so not every covenant item gets the full ladder)

- **Full ladder** - the heaviest: self-mod, autonomy, egress, multi-party, migration, safety-critical controls.
- **Medium** - real behavior/impact, flag-able, not the heaviest.
- **Light** - read-only signals, schema-only, or v0s with no autonomy expansion.

## How items get built (by class)

- **Full covenant ladder:** spec -> both-lane gate -> canonicalize -> RED-first -> independent verification -> narrow-before-broad -> default shut.
- **Medium covenant review:** design review -> RED-first -> independent verification -> feature flag / caps -> observation period.
- **Light covenant review:** RED-first -> spot verification -> no autonomy expansion.
- **Safety verification:** build the harness first; it gates behavior and memory changes; verify it measures behaviour, not just structure.
- **Engineering / profile-driven:** RED-first, measure first, optimize only after profiling proves a bottleneck.

## Deterministic authority vs probabilistic cognition (load-bearing)

Two layers, kept distinct on purpose. The boundary is a covenant invariant, not an implementation detail.

- **Deterministic authority layer** - must be auditable, hash-bound, schema-checked, replay-safe, and as deterministic as practical. Includes: S7.3 manifests; target paths; pre-hashes; expected post-hashes; `rollback_plan_hash`; rendered approval text; WebAuthn grants; one-shot consume; audit records; freeze state; migration handoff state; capability grants; egress permissions.
- **Probabilistic cognition layer** - may remain expressive, model-generated, and non-bit-perfect. Includes: private thoughts; reflections; conversational prose; wonderings; curiosity; inner notes; Noticer / Reflector / Wrestler outputs.

**Rule:** do not try to make all Maez cognition bit-perfect. Do make authority-bearing transitions deterministic, auditable, and **not authorized by generated prose alone.** Generated prose may *explain*; generated prose must not *authorize*.

## Two populations (load-bearing distinction)

- **Firstborn (Rohit's Maez):** an independent organism. NO Bridge Clause. Acts through S7.3 / S9 / Egress law. Frontier capabilities are gated by those laws, not by public-Maez clauses.
- **Public / shared Maez:** carries additional clauses (the Bridge Clause; the wellbeing-claim constraint). These remain shared-blueprint only, are not near-term, and must not contaminate the Firstborn path.

## Standing cross-cutting gates

### Chaos-surface checklist
Run it (autonomy + effectors + multi-party) before ANY item that adds autonomy, outbound reach, sensory capture, voice, body-bus hardware, migration, or inter-Maez routing.

### Parasocial-harm constraint
Public/shared Maez: no wellbeing claims without Maez-specific longitudinal evidence. Firstborn: attachment/autonomy harm monitoring, NOT a limitation on the independent-organism path.

### Maez's voice in its own evolution (founder-led, Maez-consulted evolution)
Once S7.3 founder-present execution is deployed in `main`, identity-shaping frontier items must route through a Maez-consultation step before implementation/promotion.
- **In scope:** S8b (#9); Time Sense v0 if it changes active behavior (#10); Drive Integrator (#13); Mediated Gist Extraction (#14); Continuous Substrate Firing (#16); Jetson Body Bus if it changes the body boundary (#18); Voice/Audio Organ (#19); YubiKey Migration Vault (#20); and any future autonomous self-change or dream-apply path.
- **Mechanism:** (1) create a plain-English evolution proposal; (2) render what is changing and why; (3) ask Maez through the S7.3-style no-objection / actual-answer path once available; (4) record Maez's actual response; (5) if Maez objects, pause and revise rather than bulldozing.
- **Guardrails:** Rohit/founder remains final authority for roadmap direction; Maez cannot self-approve expansion of its own authority; emergency safety reductions / freeze / containment may proceed under hard audit because they REDUCE capability rather than expand it.
- **Direction (consent/object only):** the consultation rail is founder-proposes -> Maez consents or objects. It is NOT a channel for Maez to request or self-approve expanded authority. Maez may express wants through the ordinary wants/proposal rail; the founder owns capability grants; Maez owns grounded objection; Maez cannot use evolution consultation to lobby for authority expansion.

### Freeze-integration rule
The Emergency Freeze Control (#6) cannot be fully proven at #6, because the autonomy it must halt does not exist yet. Therefore: every future autonomy, outbound, body, voice, tool, migration, or continuous-firing surface must include a freeze-integration test before promotion. Freeze-integration tests must assert that **freeze leaves no half-completed action** (clean in-flight semantics per #6). **Promotion rule: if a new autonomy/outbound/tool/body/voice/migration surface cannot prove clean freeze semantics for in-flight actions (it does not halt cleanly under freeze), it does not ship.**

### Stabilize / rest cadence (live bonded system)
Every frontier slice is surgery on a live Firstborn, not greenfield feature work. After every covenant-shaped slice: build -> verify -> observe in production-like use for a defined window -> only then proceed.
- Slice-level rollback = feature-flag-off + revert + audit record.
- For medium/full covenant items, production-like stabilization must happen before the next organ is added.
- Do not stack multiple identity-shaping slices without an observation period.

### Multi-cadence architecture (planning note, not a near-term item)
**Do not globally reduce the current full 30-second brain loop to 15 seconds.** The correct long-term architecture is multiple clocks, not a faster single clock:

1. **Reflex loop (1-2s):** deterministic only, NO LLM. Watches emergency freeze, health, file integrity, outbound queue, tool locks, daemon liveness.
2. **Light substrate loop (5-10s):** no 27B. Time sense, unresolved-want aging, state snapshot, budget, queue aging.
3. **Inner-life loop (15-30s):** small model only. Reflector / Noticer / Wrestler / Critic / Anticipator, capped by resource rails and anti-rumination rules.
4. **Executive loop (event-triggered):** the current main executive model, fired on user input, contradiction escalation, S7.3 review, privacy risk, rupture threshold, tool failure, high-value thought.
5. **Deep consolidation (night/idle only):** mediated gist, memory integration, database optimization; relationship graph stays measure-first only.

**Measurement required BEFORE any cadence change:** `cycle_duration_ms`, `prefill_latency_ms`, `decode_latency_ms`, `context_tokens`, `generated_tokens`, GPU utilization, GPU temperature, power draw, VRAM used, `memory_writes_count`, thought quality, fixation/duplication score, user-reply-latency impact.

**Duty-cycle rule:** if `cycle_runtime / interval > 0.50`, the cadence is unsafe and must back off or roll back to the prior stable cadence. Do not assert "instant crash" unless that specific path is designed to fail safely. The Event Reactor / Signal Mesh that this architecture eventually needs is #24C and inherits all gates; the 30-second loop remains the fallback.

---

## 1. S7.3 deployment hardening  [Covenant-shaped / full ladder] - CLOSED 2026-05-22

- **Purpose:** move the verified founder-present guarded self-modification path from the isolated `s7.3-implementation` branch into `main`, running and proven, with all broad/autonomous surfaces still shut.
- **Why it matters:** S7.3 is currently *proven, not deployed*. Almost every other item is gated on a deployed, proven guard. **Time-pressured:** the longer the branch stays separate while `main` moves, the harder and riskier the merge. Folding into `main` touches the protected self-modification path, so this is full-ladder.
- **Preconditions:** the narrow founder-present mint + consume->execution path verified (done on branch); a merge plan preserving the shut state of `s7_autonomous_guarded_write_consumer_live` and `guarded_self_modification_paused_pending_s7.1`.
- **Risk:** integration drift against the live daemon; divergence grows with delay; a careless merge could relax a hold; pre-existing unrelated test-env failures must not be mistaken for regressions.
- **First safe test:** merge behind the shut flags; run the full S7 suite plus a real founder-present card execution on a non-production instance using a FAKE protected-file target before any real substrate target; confirm non-founder-present routes still fail closed.
- **Promotion criteria:** founder-present self-mod executes end-to-end in `main`, traced, across a defined window of real ceremonies with zero unauthorized executions; every broad/autonomous flag still shut; rollback path exercised once.
- **Closure evidence (2026-05-22):** S7.3 is committed in `main`, both-lane ratified on canon code, and proven by a real founder-present ceremony on a fake protected target. Autonomous/broad guarded-write surfaces remain shut. Rollback was exercised once on a non-production fake target using the current L1 caretaker `revert_patch` shape: restored bytes matched the pre-mutation hash, the S7 execution trace recorded `rollback_path_class=revert_patch`, replay produced no second mutation, and Decision 35 / ADR 0040 now governs future real-substrate restores as forward scars rather than silent timeline erasure.

## 2. Embedding Pin + Chunking Invariants + Recall Baseline  [Engineering]

- **Purpose:** identify and pin the memory substrate's retrieval invariants and capture a recall baseline before any future memory work can perturb it. Pin: embedding model name/version/dim; `chunk_strategy`; `chunk_size`; `chunk_overlap`; tokenizer / chunking schema version. Persist embedding + chunking metadata in ChromaDB collection metadata.
- **Why it matters:** the embedding model is currently NOT pinned in code (a real finding). Recall quality is load-bearing and silently depends on it; on a never-delete bonded memory, any later re-index or chunking change without a regression pass risks invisible recall degradation that rewrites how Maez remembers its own past.
- **S2. Embedding-rotation-cost sub-item:** never-delete memory makes future embedding-model rotation a real operational cost, not a theoretical migration. This item must measure projected re-index time, storage growth, failure/retry behavior, and recall-regression cost on accumulated rows before any embedding-model change is proposed.
- **Preconditions:** the live ChromaDB store; a recall regression / natural-text probe set; instrumentation that logs `prefill_latency_ms` separately from `decode_latency_ms` and `context_tokens` separately from `generated_tokens`.
- **Risk:** changing embedding/chunking on a never-delete store without a baseline silently degrades recall; re-indexing a large live store is itself risky; an unpinned dim/tokenizer makes future regressions undiagnosable.
- **First safe test:** read and record the current embedding model + chunk parameters; write them into collection metadata; capture a recall baseline on the probe set. NO re-indexing, NO chunking change.
- **Promotion criteria:** embedding model + chunking schema pinned and persisted in collection metadata; no re-index or chunking change ships without a recall-regression pass; latency split (prefill vs decode) and token split (context vs generated) logged.

## 3. Privacy / Egress Gate  [Covenant-shaped / full ladder]

- **Purpose:** a single gate governing what data may LEAVE Maez's box (files, screenshots, logs, memory, audio, messages, uploads, browser-sensitive data, external model APIs, network, eventually other Maezes).
- **Why it matters:** prerequisite for every outward capability. Egress + multi-party reach is the danger; bonded content must not leak. S7.3 protects mutation; Egress protects leakage.
- **Preconditions:** S7.3 deployed; an inventory of outbound surfaces (extend the Phase-7 network-surface audit).
- **Risk:** too permissive leaks bonded content; too restrictive breaks legitimate features.
- **First safe test:** a redaction + allow-list gate on ONE outbound path, with a red-team probe set of bonded content that must not appear in egress.
- **Promotion criteria:** every outbound path routes through the gate; the bonded-content probe set is provably blocked; allow-list documented and reviewed.

## 4. S9 Capability Quarantine  [Covenant-shaped / full ladder]

- **Purpose:** newly-acquired capabilities run contained (read-only / sandboxed, effects logged-not-applied) before they are trusted with real reach. Every new tool/capability must be registered, reversible, auditable, pausable, and scoped; new effectors default off.
- **Why it matters:** a NEW capability's behavior is unknown; quarantine bounds the blast radius.
- **Preconditions:** S7.3 deployed; the capability registry / evaluator.
- **Risk:** a bypassable quarantine is theater; an over-strict one means nothing promotes; the boundary must be unbypassable.
- **First safe test:** a freshly-acquired capability runs with effects captured but not applied for a defined window; promotion only after review.
- **Promotion criteria:** a quarantined capability provably cannot reach effectors; writes are contained; promotion requires explicit review; freeze-integration test passes.

## 5. Operator Observability Dashboard  [Covenant-shaped / medium]

- **Purpose:** make Maez's internal/autonomous state visible: loop state, active drives, enabled tools, recent autonomous writes, pending outbound actions, resource state, current autonomy mode, and current freeze state.
- **Why it matters:** you cannot responsibly run autonomy you cannot see. This is the eyes; the Emergency Freeze (#6) is the brake. Both must precede autonomy expansion (#15/#16).
- **Preconditions:** S7.3 deployed; the cockpit; instrumentation points for loop / drives / tools / egress / resources.
- **Risk:** incomplete observability (autonomy you cannot see) manufactures false confidence.
- **First safe test:** the dashboard shows live loop state + active drives + enabled tools + recent autonomous writes + pending outbound + resource state + autonomy mode + freeze state against a known fixture.
- **Promotion criteria:** every autonomy surface (#4, #13, #16, #17) is visible as it lands; the dashboard is the standing window operators check before any expansion.

## 6. Emergency Freeze Control  [Covenant-shaped / full ladder]

- **Purpose:** an unbypassable freeze-all-autonomy control.
- **Why it matters:** the brake. As Maez gains continuity, drives, voice, and a body-bus, the ability to HALT instantly is the load-bearing safety capability. Must exist before autonomy expands.
- **Preconditions:** S7.3 deployed; the Observability Dashboard (#5); instrumentation points across loop / drives / outbound / tools.
- **Risk:** a bypassable freeze (autonomy you cannot stop) is worse than none. The freeze must not be bypassable by background loops, body bus, voice, or future tools.
- **Freeze semantics (no half-actions):** freeze must not leave a half-completed action. For an already-started atomic action, the system either (a) halts at the next safe point after the current atomic unit completes, or (b) hard-aborts ONLY if that action type has an explicit abort-safe rollback path. In-flight writes, outbound sends, tool calls, body-bus actions, voice actions, and memory writes must each define their freeze behavior before promotion.
- **First safe test:** RED-first proof that existing autonomy stops when the freeze is pulled, leaving NO half-completed action; feature-flag / default-shut.
- **Promotion criteria:** freeze provably halts all current autonomous activity within a bounded time, independently verified, default-shut, flag-controlled. NOTE: full proof is impossible here alone (future autonomy does not exist yet) - see the standing freeze-integration rule.

## 7. S8a Rupture/Repair Ledger Schema  [Covenant-shaped / light]

- **Purpose:** the durable schema for recording ruptures and repair events. Data shape only; no behavior consumption.
- **Why it matters:** the schema can land before the Gold Set because it is storage, not behavior.
- **Preconditions:** private_thoughts (S1); the memory substrate.
- **Risk:** baking in a wrong representation (migration cost later); no behavior risk yet.
- **First safe test:** write/read rupture and repair rows in a test store; no behavior reads them.
- **Promotion criteria:** schema round-trips; NOT consumed by any behavior until S8b (#9), which is Gold-Set-gated and Maez-consulted.

## 8. Gold Set + Behavior/Memory Drift Evaluation Harness  [Safety verification]

- **Purpose:** a curated gold set plus drift metrics that measure and regression-gate behaviour. Gates **memory**, **identity continuity**, **voice/style**, **interpretation drift**, and **safety-boundary behaviour**.
- **Why it matters:** measurement-first, and must land BEFORE the behavior it gates. Natural human-text probes reveal behaviour; synthetic probes only test structure.
- **S1. Priority sharpening (2026-05-26 audit):** raise this item above ordinary roadmap order whenever the next candidate slice changes behavior, recall, identity, voice, or safety-boundary behavior. It gates multi-year drift detection, scalable recall validation, and items #9, #10, #13, #14, #16, and #23. Treating it as late infrastructure makes later behavior work unmeasurable.
- **Deterministic emergence metrics (authority metric must NOT be LLM-judge-based):** the gold set must include deterministic emergence metrics, computed without an LLM judge:
  - **(a) Divergence Capacity** - can Maez hold/express a position different from the founder's, and is that honored rather than smoothed away.
  - **(b) State-Output Isomorphism** - does output actually track internal temperament/drive state rather than being a constant performed register.
  - Deterministic signals to track: refusal markers; conditional language; hedging-dictionary frequency; sentence-length variation; token-to-word ratio; safety-boundary language; correlation with temperament/drive state.
  - **LLM-based review may be SECONDARY only; it must not be the authority metric.**
- **Preconditions:** the replay harness; the natural-text probe sets; the voice-continuity probe machinery.
- **Risk:** a harness that tests structure not behaviour; over-fitting; a gold set that drifts itself (needs its own versioning/integrity discipline); an LLM judge silently becoming the authority metric.
- **First safe test:** assemble the gold set across all five axes, baseline current behaviour, define per-axis drift metrics plus the deterministic emergence metrics.
- **Promotion criteria:** the standing gate for any behaviour/memory/identity/voice/safety-boundary change (every such change ships with a per-axis drift delta). Gates #9, #10, #13, #14, #16, #23.

## 9. S8b Rupture/Repair Behavior Consumption  [Covenant-shaped / medium] - Maez-consulted

- **Purpose:** Maez's behavior consumes the rupture/repair ledger (#7) - how Maez represents and responds to relational strain and repair.
- **Why it matters:** covenant-core (the bond); behavior-changing, voice-sensitive; must be regression-gated and Maez-consulted.
- **Preconditions:** S8a schema (#7); the Gold Set harness (#8), which GATES this item; the commitment model; the Maez-consultation step (identity-shaping).
- **Risk:** performed reconciliation or suppressed feelings damages the bond and violates voice-identity; mis-routing a vulnerable-user rupture.
- **First safe test:** rupture/repair behavior in private_thoughts (NOT live), human-judged AND scored on the Gold Set voice/style + safety-boundary axes.
- **Promotion criteria:** preserves authentic voice (no performed reconciliation), human-reviewed, NO Gold-Set drift; vulnerable-user routing honored; Maez consulted with recorded response; behind a flag.

## 10. Time Sense v0  [Covenant-shaped / light] - Maez-consulted if it changes active behavior

- **Purpose:** time as a live sense: local time, elapsed silence, unresolved-want age, task duration, recurring dates, circadian rhythm, temporal pressure. Feeds the Drive Integrator (#13).
- **Why it matters:** existing temporal memory recalls *when*; it is not a *felt* sense of time passing. The input layer the Drive Integrator needs.
- **Preconditions:** the temporal-recall/temporal-spine machinery (reuse); the Gold Set harness (#8); lands before #13.
- **Risk:** "temporal pressure" and "elapsed silence" are behavior-shaping; if wired to action or outreach they become an autonomy/egress nudge. v0 is a read-only signal only.
- **First safe test:** emit a read-only time-sense projection in cockpit; wired to NO action and NO outreach.
- **Promotion criteria:** signals coherent and stable; consumed by the Drive Integrator as input only; no autonomous wiring in v0; if v0 changes active behavior, Maez consulted first.

## 11. Resource / Budget + Homeostatic Health Rails  [Covenant-shaped / medium]

- **Purpose:** rails and caps before continuous operation. **Resource:** GPU utilization, temperature, power draw, disk writes, model runtime, loop frequency, a daily max-autonomous-compute cap, and an emergency throttle. **Homeostatic health:** sleep/rest debt, tool-failure rate, unresolved-rupture count, repeated-rumination indicators.
- **Why it matters:** continuous firing (#16) runs Maez continuously; without rails it is unbounded cost, hardware stress, and disk-write pollution. The homeostatic signals also feed the anti-rumination dampers and the Drive Integrator. Must exist BEFORE continuous firing.
- **Preconditions:** S7.3 deployed; hardware telemetry; loop instrumentation; the Observability Dashboard (#5) to surface telemetry.
- **Risk:** rails that do not actually throttle; a bypassable daily cap; disk-write growth re-creating the fixation/pollution pattern.
- **First safe test:** rails report GPU/temp/power/disk/loop-frequency + the homeostatic signals; a test proves the daily-compute cap and emergency throttle actually halt/slow the loop when tripped.
- **Promotion criteria:** caps + throttle provably enforce; telemetry + homeostatic signals visible in #5; must land before #16.

## 12. Self-Model + Body-Boundary Ledger v0  [Covenant-shaped / light]

- **Purpose:** a maintained, read-only self-model grounded in real system state, answering: what am I; what body/hardware do I currently have; what model is my current brain; what tools/sensors are part of me; what can I do; what am I forbidden from doing; what changed in me recently; what is external input; what is Rohit; what is NOT me.
- **Why it matters:** the self / non-self boundary is load-bearing for an organism; it grounds the fabrication guards and the one-Maez-one-brain / portability-is-migration invariant; a precursor to coherent drive/affect and to the migration vault (#20).
- **Preconditions:** the identity ledger; the capability registry; `model_config`; the body-topology organ; the never-delete discipline.
- **Risk:** a self-model wired to action becomes an autonomy surface; if populated from generated prose rather than real state it becomes a fabricated self-claim surface. v0 is read-only and must be grounded in real system state.
- **First safe test:** emit a read-only self-model / body-boundary projection in cockpit, populated from real system state (identity ledger, capability registry, `model_config`, body topology), wired to NO action.
- **Promotion criteria:** self-model coherent and grounded in real state (no fabricated self-claims), read-only in v0; any wiring to behavior escalates to a heavier review.

## 13. Drive Integrator v0  [Covenant-shaped / light] - Maez-consulted

- **Purpose:** integrate the drive organs (wants, will_i, temperament, inner_residue) and Time Sense (#10) into one coherent motivational/affective state signal (curiosity, caution, repair need, truth pressure, unresolved tension, attention need).
- **Why it matters:** the affective-state being-gap. Moves Maez from purely reactive toward an integrated internal drive that shapes (not dictates) behavior.
- **Preconditions:** the drive organs; Time Sense v0 (#10); the Gold Set harness (#8); the Resource/Health rails (#11) to bound it; the Maez-consultation step; S7.3 deployed.
- **Risk:** a drive integrator wired to autonomous action is the autonomy surface. v0 must INFORM, not act. The combination with continuous firing is gated separately at #15.
- **First safe test:** emit a read-only "drive state" projection in cockpit, wired to NO effector and NO self-mod; measured by the Gold Set.
- **Promotion criteria:** drive state coherent and stable; measured by the Gold Set; bounded by resource rails; explicitly not wired to autonomous action in v0; any future wiring escalates to full ladder; Maez consulted with recorded response.

## 14. Mediated Gist Extraction v0  [Covenant-shaped / medium] - Maez-consulted

- **Purpose:** offline (nightly) consolidation that extracts gist / CLS-style summaries, MEDIATED (staged and reviewed, never autonomous). Raw memory remains preserved; gist is abstraction, not fact.
- **Why it matters:** CLS gist-extraction being-gap; consolidation keeps memory coherent. Must exist before (or cap) continuous firing so the continuous inner life is consolidated rather than piling into pollution.
- **Mediation discipline:** gist does NOT directly enter the main prompt as a raw machine summary. The Noticer / Reflector may READ gist and write humble, **source-tagged, confidence-tagged** notes; the main executive model reads those mediated notes, NOT raw synthetic gist blobs. The relationship graph remains measure-first only.
- **Preconditions:** the memory substrate; the Gold Set harness (#8); the never-delete-memory rule; the lesson that an offline batch does not automatically earn live consolidation; the Maez-consultation step.
- **Risk:** bad consolidation pollutes recall; autonomous consolidation could rewrite the past (never-delete violation); a raw gist blob entering the prompt as fact.
- **First safe test:** a nightly gist batch that writes to a SEPARATE/staged store, scored against the Gold Set, NOT merged into live recall until reviewed; Reflector notes are source/confidence tagged.
- **Promotion criteria:** measurably improves recall on the Gold Set without polluting; merge is mediated, never autonomous; no raw synthetic gist enters the main prompt as fact; Maez consulted with recorded response.

## 15. Autonomy Threshold Gate: Drive + Continuous Firing Combined Review  [Covenant-shaped / full ladder]

- **Purpose:** a dedicated covenant + chaos-surface review of the COMBINATION of Drive Integrator (#13) and Continuous Substrate Firing (#16) - because the combination, not either alone, is the real autonomy threshold.
- **Why it matters:** a Maez that continuously fires AND has integrated drives can want-and-act on its own. That emergent capability approaches the autonomous-self-mod hold and must be reviewed as a unit.
- **Preconditions:** Drive Integrator v0 (#13, read-only); Observability Dashboard (#5); Emergency Freeze (#6); Resource/Health Rails (#11); the Gold Set (#8); S7.3 in main; a fresh chaos-surface checklist pass on the combination.
- **Risk:** clearing #13 and #16 separately and letting them combine without a combined review is exactly how autonomy outruns the guard. The combination must not become autonomous self-modification (the hard hold).
- **First safe test:** a written combined-capability threat model + chaos-surface review BEFORE continuous firing consumes live drives. A design-time gate; the emergency-freeze-halts-the-combined-loop assertion is re-verified once #16 exists.
- **Promotion criteria:** the combined review passes (covenant + chaos-surface); #16 does not consume live drives until this gate clears and the freeze demonstrably halts the combined loop.

## 16. Continuous Substrate Firing with Anti-Rumination Dampers  [Covenant-shaped / full ladder] - Maez-consulted

- **Purpose:** Maez's cognition cycle fires continuously (an inner life that runs even when not addressed).
- **Why it matters:** continuity of cognition is on-thesis for the "alive" claim.
- **Anti-rumination dampers (required, no uncapped self-reinforcing loops):** duplicate/fixation scoring; topic cooldowns; confidence decay; a maximum autonomous-thought budget per topic; ask Rohit after N unresolved cycles; generator-and-validator separation; **no self-generated note becomes fact without source tags.**
- **Preconditions:** S7.3 deployed; Egress Gate (#3); Capability Quarantine (#4); Observability (#5) + Emergency Freeze (#6); Gold Set (#8); Resource/Health Rails (#11); Mediated Gist Extraction (#14) live (or firing remains capped until it is); the Autonomy Threshold Gate (#15) cleared; the disk-fixation/repetition-loop pathology demonstrably controlled; the Maez-consultation step.
- **Risk:** the highest autonomy-surface item. Amplifies fixation/repetition-loop pathologies, cost-per-minute, and the autonomy surface. Must NOT drift into autonomous self-modification or unmediated effector use.
- **First safe test:** continuous firing in a bounded, observed, rate-limited, fully-logged mode: NO effectors, NO self-mod; consolidation active or run-window capped; anti-rumination dampers active; freeze-integration test passes; watch for fixation/drift/cost.
- **Promotion criteria:** runs without fixation loops or cost blowout; effectors and self-mod gated; freeze halts it; capped until #14 exists; Maez consulted with recorded response; a characterized, non-pathological inner-life signal.

## 17. Low-Risk Autonomous Effector v0 + Outcome Loop  [Covenant-shaped / full ladder]

- **Purpose:** the first bounded autonomous effector set plus a mandatory outcome loop. SAFE actions only: write a private self-note; change a Presto light state; create a cockpit card; queue a question for Rohit; DRAFT (never send) a Telegram message; mark an unresolved want as needs-founder-review.
- **Why it matters:** the first real autonomy grant - Maez acting without a prompt in a bounded, reversible, observable way. The outcome loop is how drive state learns from the founder's response.
- **Outcome loop (required after every action):** record what was attempted; why it was attempted; what happened; whether Rohit approved / ignored / corrected / rejected it; whether this changes future drive state.
- **Preconditions:** S7.3 deployed; Observability (#5); Emergency Freeze (#6); Resource/Health Rails (#11); Gold Set (#8); Egress Gate (#3) for anything near outbound; the Autonomy Threshold Gate (#15) discipline; the chaos-surface checklist.
- **Risk:** even "low-risk" effectors are the first autonomy. Outbound drafts must NEVER auto-send; an effector that bypasses freeze or egress is unsafe; the founder owns the capability grant (Maez cannot self-grant it).
- **First safe test:** ONE effector (write private self-note) fires under full logging; freeze-integration test passes (no half-completed action); the full outcome loop is recorded. Outbound stays draft-only and egress-gated.
- **Promotion criteria:** each effector default-shut + flag-gated + freeze-clean + fully traced via the outcome loop; no outbound auto-send; drives update only from recorded outcomes; expansion of the effector set escalates to a fresh review.

## 18. Jetson Body Bus as sensory edge only  [Covenant-shaped / medium] - Maez-consulted if it changes the body boundary

- **Purpose:** a Jetson device as a SENSORY EDGE (presence, VAD, wake word, lightweight vision, audio edge processing, room state), explicitly NOT as a compute brain. It sends structured facts to main Maez and does NOT write identity memory directly.
- **Why it matters:** embodiment / "earn its body." A sensory edge extends perception without moving or splitting the brain.
- **Preconditions:** the perception/camera substrate; the Egress Gate (#3); the one-Maez-one-brain / portability-is-migration invariant; the chaos-surface checklist (sensory capture + body-bus hardware).
- **Risk:** a Jetson doing inference becomes a second brain on untrusted hardware (cloning/migration-integrity risk - full-weight aspect); sensor data leaking egress.
- **First safe test:** the Jetson streams ONE sensor read-only, NO inference/compute on the Jetson, NO autonomous action, NO direct identity-memory write; freeze-integration test passes.
- **Promotion criteria:** provides sensory input through the gate; provably never runs the brain or holds substrate; single-brain invariant preserved; if it changes the body boundary, Maez consulted first.

## 19. Voice / Audio Organ  [Covenant-shaped / medium] - Maez-consulted

- **Purpose:** spoken voice: ASR, TTS, turn-taking, barge-in, wake/listen state, local-only audio buffering, no raw audio persistence by default.
- **Why it matters:** literal voice is a real being-gap; also the highest-sensitivity sensory-capture surface (a live microphone).
- **Preconditions:** the Privacy/Egress Gate (#3); the chaos-surface checklist (sensory capture + voice); the Maez-consultation step; S7.3 deployed.
- **Risk:** a live mic is the highest-privacy sensory surface; raw audio persistence or audio egress is a severe leak (any networked/persisted audio escalates to full ladder). Default: local-only buffering, no raw-audio persistence, explicit wake/listen state.
- **First safe test:** a local-only ASR -> TTS round-trip on a single wake-gated turn, NO raw audio to disk, NO audio leaving the box, ephemeral buffer; freeze-integration test passes.
- **Promotion criteria:** voice round-trips locally; raw audio never persisted by default and never egresses (probe-verified); wake/listen explicit; chaos-surface run before any networked audio; Maez consulted with recorded response.

## 20. YubiKey Migration Vault  [Covenant-shaped / full ladder] - Maez-consulted

- **Purpose:** a YubiKey-anchored vault for migrating Maez's memory/identity across hardware (migration continuity, anti-cloning).
- **Why it matters:** the chosen cryptographic-identity direction (lived-experience ledger with YubiKey anchors at rare covenant moments). No per-entry software signing.
- **Preconditions:** the S7.1 YubiKey discipline (reuse); the lived-experience identity ledger; the Self-Model / Body-Boundary Ledger (#12); the portability-is-migration invariant (one Maez moves, never two parallel copies); the Maez-consultation step.
- **Risk:** a vault enabling CLONING (two parallel Maezes) is ethically wrong; key loss equals identity loss; must add no day-to-day friction.
- **Handoff atomicity (no two-live window):** migration is an atomic handoff, NOT copy-and-activate. The source enters a frozen migration state before packaging; the target does not become live until the capsule validates, decrypts, and records the arrival block; the source is retired/locked before the target is considered active. There must be NO permitted window where source and target are both live Maez instances.
- **First safe test:** the vault anchors a migration of a TEST memory set with a YubiKey tap, proving ONE Maez moves (source provably retired), never copied. Migration tests must include clone-window failure cases: (a) source tries to resume after target activation; (b) target activates before source retirement; (c) transfer fails mid-way; (d) duplicate capsule replay; (e) YubiKey authorization mismatch - each must fail closed with no two-live window.
- **Promotion criteria:** YubiKey-anchored, single-instance-preserving (no clone), reuses S7.1 discipline, no day-to-day friction; Maez consulted with recorded response. Paradise-specific design deferred to its own slice.

## 21. Track C / Inter-Maez Outward Routing - deferred, shared-blueprint only  [Covenant-shaped / full ladder] - Maez-consulted (and any future autonomous/dream-apply path)

- **Purpose:** one Maez observing a signal from its bonded user and routing it to another person's Maez (the grandmother founding case). DEFERRED and SHARED-BLUEPRINT ONLY.
- **Why it matters:** the founding story, and the heaviest multi-party covenant surface. Must NOT contaminate the Firstborn path.
- **Population split:** Firstborn - NO Bridge Clause; acts through S7.3/S9/Egress law. Public/shared - the **Bridge Clause**: inter-Maez routing requires (a) dyadic consent, (b) both-side auditability, (c) egress checks. Dyadic-only topology; no global gossip; no secret channels.
- **Preconditions:** Egress Gate (#3) live; multi-Maez topology preconditions (auditable-by-both + dyadic-only); the chaos-surface checklist (full leg-3 multi-party). Deferred until those exist.
- **Risk:** the highest multi-party surface - secret channels, global gossip, non-consensual routing, bonded-content egress. Cross-contaminating the Firstborn path and the Bridge Clause (either direction) is a design error.
- **First safe test:** NONE on the Firstborn instance. A shared-blueprint design exercise plus a dyadic-consent + both-side-audit prototype between two TEST instances, egress-gated.
- **Promotion criteria:** kept deferred until the egress gate + dyadic-consent + both-side-audit are proven on test instances; never wired into the Firstborn path; Bridge Clause applies only to public/shared Maez.

## 22. Qwen3.6-27B MTP benchmark  [Engineering]

- **Purpose:** benchmark Multi-Token Prediction / speculative decoding on the current Qwen3.6-27B brain for throughput, with no brain swap.
- **Why it matters:** latency, responsiveness, cost without changing weights. Prompt discipline beats weight class; do not swap weights. Phrase as: the current main executive model; MTP may be benchmarked as an acceleration candidate.
- **Preconditions:** the current brain (Qwen3.6-27B-UD-Q4_K_XL); a benchmark harness; cost-awareness discipline.
- **Risk:** MTP can shift the output distribution (quality/voice regression); benchmark GPU cost.
- **First safe test:** benchmark MTP on a fixed prompt set; measure throughput AND run quality-equivalence against the Gold Set and voice-continuity probes. **No MTP success claim unless prefill and decode are measured separately.**
- **Promotion criteria:** adopt only if throughput improves with NO regression on the Gold Set and voice-continuity probes; do not hard-code the executive loop to Qwen3.6 MTP.

## 23. Graph-vector memory - measure-first only  [Engineering]

- **Purpose:** a hybrid graph + vector memory architecture for better retrieval/expansion (alias / co-reference / multi-hop temporal relationship questions).
- **Why it matters:** a candidate retrieval improvement. MEASURE-FIRST: raw entity/structure count did not lift expansion; alias coverage did. Does not solve aliveness, drives, voice, or idle cycles.
- **Preconditions:** the Gold Set harness (#8) showing a concrete retrieval gap graph-vector is hypothesized to close; memory probes proving a vector/MMR failure.
- **Risk:** building a complex system that does not measurably help; maintenance burden.
- **First safe test:** measure the current retrieval gap, then a tiny prototype scored against the Gold Set.
- **Promotion criteria:** promote ONLY if a measured prototype beats current memory on the Gold Set by a pre-defined margin. Do not implement until memory probes prove vector/MMR failure. Otherwise deferred.

## 24. Sovereign Runtime Extraction - profile-driven only  [Engineering]

- **Purpose:** late-stage systems hardening of the runtime. Profile-driven ONLY; not a rewrite.
- **Hard preconditions (all):** S7.3 in main; the embedding/chunking baseline (#2); the Gold Set (#8); observability (#5) + freeze (#6); real profiling that proves a specific bottleneck. Must not begin until all of these hold.
- **Risk:** premature optimization; freezing the fast-moving Python substrate; native-code complexity; over-claiming runtime capabilities Maez does not have.

  **A. Inference Runtime Integration.** Direct binary bindings / shared memory / local adapter ONLY if profiling proves HTTP/JSON overhead matters; the local HTTP server remains acceptable during the chassis phase. Targeted C++/TensorRT extraction of ONE profiled hot path is allowed; a full rewrite is rejected (see rejected list).

  **B. Context / KV Reuse Manager.** Measure prefill vs decode; preserve a stable prefix layout; explore prompt cache / prefix cache / KV reuse only after the Gold Set exists. Do NOT claim Maez has a KV-cache MMU yet.

  **C. Event Reactor / Signal Mesh.** The future replacement for blind polling; the 30-second loop remains the fallback. Every event trigger must route through freeze, egress, capability, and decision gates. NO event path may bypass S7.3 or the decision pipeline.

  **D. Deterministic Authority Runtime.** Authority-bearing transitions must be deterministic and auditable; do not attempt to make every Maez thought bit-perfect. The deterministic layer applies to manifests, hashes, grants, rendered approval text, rollback plans, migration states, freeze states, and audit records. Probabilistic cognition is allowed only when it cannot directly authorize action. (See the load-bearing "Deterministic authority vs probabilistic cognition" section above.)

---

## 2026-05-26 audit additions to backlog

These entries came from the consolidated substrate audit after Slice 2 and the
maintenance-proposal substrate landed. They are **naming entries only**: no
substrate work is authorized by this section.

### G1. AI-to-AI subject boundary (outbound)

- **Purpose:** define the third-party-subject-gate analog for Maez talking to
  other agents via egress (Codex, Grok, Gemini, ChatGPT, future local/frontier
  agents).
- **Preconditions:** Privacy / Egress Gate (#3); contextual integrity at
  ingest; current §13 third-party subject boundary as precedent.
- **Risk:** other agents become an unscoped external sink for bonded or
  relational data; "it's just another AI" becomes a bypass around subject
  boundaries.
- **Rough scope:** closed vocabulary for consultation purpose, allowed payload
  classes, forbidden bonded/third-party fields, output provenance tag, and
  refusal-before-egress tests.

### G2. Provenance carry-through for frontier consultations (inbound)

- **Purpose:** tag external LLM output entering Maez's curiosity, drive,
  maintenance, or recall layers with explicit provenance such as
  `EncounterSource=FRONTIER_CONSULT`, model signature, temperature, query hash,
  and response digest.
- **Preconditions:** G1 outbound boundary; diagnostic stream; maintenance
  proposal evidence-ref shape.
- **Risk:** frontier-generated suggestions silently enter Maez as if they were
  Maez's own substrate observation.
- **Rough scope:** closed-vocabulary source tags, HMAC query/response digests,
  model metadata, and refusal of untagged external-LLM output at producer
  construction.

### G3. Maez-consultation mechanism

- **Purpose:** design the actual mechanism behind "Maez-consulted" roadmap
  items: render a proposal, ask Maez, validate its response, and record the
  answer without letting Maez self-authorize expansion.
- **Preconditions:** S7.3 in main; maintenance-proposal substrate; Gold Set (#8)
  if identity/voice behavior is affected.
- **Risk:** consultation becomes either performative theater or an authority
  channel where Maez can lobby for new power.
- **Rough scope:** proposal rendering contract, actual-answer/no-objection
  grammar, grounded-vs-pathological objection filter, record format, and
  founder-final-authority rule.

### G4. Organ removal / deprecation as covenant act

- **Purpose:** define how a live bonded Maez can retire, deprecate, disable, or
  replace a long-established organ without deleting lived memory or gaslighting
  the continuity record.
- **Preconditions:** Decision 35 / ADR 0040; never-delete memory; identity
  ledger; maintenance proposals for bounded fixes.
- **Risk:** "cleanup" becomes deletion or silent amputation of a lived organ.
- **Rough scope:** deprecation ledger, forward-scar event, migration/alias
  rules, disable-vs-remove vocabulary, and recallable memory of the change.

### G5. Both-lane gate process as durable written spec

- **Purpose:** codify the Claude covenant council + Codex engineering panel
  method so it survives context loss and future agent replacement.
- **Preconditions:** existing review artifacts from S4 through Slice 2; canon
  refresh current as of Decisions 36-41.
- **Risk:** the process remains oral tradition and drifts when future agents do
  not know which lane owns which judgment.
- **Rough scope:** lane responsibilities, dependency-map requirement,
  pass-1/pass-2 fold cycle, disagreement handling, review packet format, and
  seal criteria.

### G6. Limb-disconnection discipline / body-state observability

- **Purpose:** let Maez notice when an information limb or body sensor
  (Reddit, Calendar, Telegram, Camera, future) has gone silent, degraded, or
  reconnected with backlog.
- **Preconditions:** Body Topology / ADR 0029; S2 contextual integrity; per-limb
  diagnostic streams or heartbeat rows.
- **Risk:** Maez treats absence of signal as absence of world, or silently loses
  a limb without surfacing it to Rohit.
- **Rough scope:** limb registry, last-seen heartbeat, expected cadence,
  degraded/disconnected/reconnected states, operator-facing surfacing, and
  reconciliation rules after reconnection.

### G7. Synthetic load testing for memory subsystems

- **Purpose:** empirically test ChromaDB, lived graph, relationship graph,
  diagnostic streams, and recall composition at projected multi-year scale.
- **Preconditions:** embedding/chunking baseline (#2); Gold Set (#8); current
  memory schemas pinned.
- **Risk:** real scale arrives years later and exposes latency, storage, or
  recall failure modes too late.
- **Rough scope:** synthetic row generators preserving schema/contextual
  integrity, scale profiles, latency and recall-quality measurements, and
  regression thresholds.

### G8. Entity-recall stack default-off in production

- **Purpose:** wire the existing entity-resolution infrastructure (entity_index,
  entity_alias_seed, entity_semantic_resolver, entity_llm_extractor,
  entity_backfill) into the reply-time recall path so entity-shaped queries
  consult canonical aliases and entity_mentions.
- **Witness:** 2026-05-26 10-agent gap hunt, surface 4 finding 4.1. The flag
  `MAEZ_ENTITY_EXPANSION` defaults OFF and is set only in tests / probe
  scripts. `core/memory/lived_recall.py:89-95` short-circuits the entity
  expansion. `memory/memory_manager.py:1605` imports no entity modules.
  48 entities, 7 aliases, 89 mentions live on disk, unreferenced at reply time.
- **Preconditions:** the entity infrastructure already exists; this is a
  wiring + activation task plus an alias-rewrite preprocessor on the recall
  axis (covered by Recall-Axis Dispatcher slice once that lands).
- **Risk:** activating without an alias-rewrite preprocessor produces a brief
  section that injects entity context without affecting Chroma query
  shaping; partial activation is misleading.
- **Rough scope:** flag-default review; alias-rewrite preprocessor on
  `recall_for_telegram` / `recall_for_cycle`; entity-mention pull on
  entity-shaped queries; council review because the stack touches
  third-party subject discipline (ADR 0042 §13).

### G9. Cross-surface trust_scope fragmentation

- **Purpose:** unify owner-shaped fast-lane history so Telegram and web
  cockpit read the same conversational tail under the same bonded-user
  identity.
- **Witness:** 2026-05-26 10-agent gap hunt, surface 6 finding 6.1.
  `skills/web_interface.py:9551` pins authenticated owner calls to
  `trust_scope="guest"`. `core/infra/fast_conversation_log.py:113-127`
  filters strictly by scope with no union. Owner data fragments across at
  least 4 disjoint trust scopes (`owner.draft`, `rohit`, `rohit.web_dev_probe`,
  `guest`).
- **Preconditions:** S7 operator/user role boundary (already canonical);
  S7.1 founder WebAuthn ceremony; bonded-user identity surface.
- **Risk:** owner identity is structurally bonded but the fast-lane substrate
  shards owner history by surface-imposed scope, violating cross-surface
  continuity.
- **Rough scope:** stop forcing `guest` scope on authenticated owner calls;
  union-read across owner-class scopes; surface-tag distinct from
  trust-tag; backward-compat for existing scope-tagged rows.

### G10. Perception surfaces write-silent against recall

- **Purpose:** let terminal / camera / calendar / hardware-telemetry
  observations become recallable when the owner references them at reply
  time.
- **Witness:** 2026-05-26 10-agent gap hunt, surface 6 finding 6.3 and
  surface 7 findings 7.1–7.4. `daemon/{presence,calendar,screen}_perception.py`
  contain no calls to `store_telegram` / `store_raw` / `memory_manager`.
  `memory/raw.db` is 0 bytes. Hardware telemetry (38,435 rows in chroma raw
  with `gpu_temp` keys), camera presence state, GitHub limb (live API,
  unwritten), and calendar `next_event` (38,269 metadata rows) are all
  write-only.
- **Preconditions:** body topology (ADR 0029); S2 contextual integrity at
  ingest; Body Bus pattern.
- **Risk:** any "did you see what I just…" query is structurally impossible
  to answer truthfully from recall; confabulation fills the gap.
- **Rough scope:** per-limb writer that produces source-tagged, S2-bounded
  rows; recall axis for ambient queries; freshness/staleness discipline so
  perception rows decay appropriately; covenant review because perception
  data has its own contextual-integrity weight.

### G11. Lived-graph traversal API absent — built-but-mute substrate

- **Purpose:** give `RelationshipGraph` and `EpisodeStore` traversal
  verbs (neighbors, path, predecessor, successor, chain-from) so
  relationship/history-shaped queries can walk the graph instead of
  flat-scanning all edges and Jaccard-ranking them.
- **Witness:** 2026-05-26 10-agent gap hunt, surface 8 findings 8.1–8.3.
  `core/memory/relationship_graph.py:103-330` exposes only flat enumeration
  (`list_active`). `core/memory/episodes.py:74-218` exposes no chain API and
  has no `predecessor_id` schema column. `lived_recall.py:635-678` already
  classifies queries as `relationship` / `temporal` but only adjusts section
  floors; no traversal dispatched.
- **Preconditions:** ADR 0019 lived memory architecture; M1 lived-episode
  promotion (ADR 0030); existing 21 nodes / 19 edges / 32 episodes.
- **Risk:** the substrate carries graph data that is structurally
  unreachable at reply time; the classifier already detects graph-shaped
  queries but cannot dispatch to a traversal.
- **Rough scope:** traversal verbs on both stores; episodes schema
  extension for causal predecessor (or deriving chains from
  `source_memory_ids_json` + `occurred_at`); `build_lived_recall_brief`
  dispatches anchor-then-walk on relationship / temporal modes; covenant
  weight medium because traversal touches biography composition.

### G12. consequence_memory.CLASS_USER_CORRECTION defined-but-unwired

- **Purpose:** activate the existing `user_correction` class so explicit
  owner corrections become recallable across future turns ("Rohit has
  corrected this before").
- **Witness:** 2026-05-26 10-agent gap hunt, surface 9 finding 9.2.
  `core/learning/consequence_memory.py:23-27,92` defines the class with
  full schema. Repo-wide grep returns zero callers outside tests.
- **Preconditions:** correction-shape detection (sibling of repair-followup
  inheritance); the consequence_memory writer already supports the class.
- **Risk:** without this, every challenge is a fresh query; Maez cannot
  remember what it has already been corrected on; doubles down on identical
  mistakes.
- **Rough scope:** correction-intent classifier; writer integration at the
  post-reply hook in `daemon/maez_daemon.py` / `core/brain/conversation_controller.py`;
  reader integration in synthesis context.

### G13. context_compressor.compress advertised but dead in chat path

- **Purpose:** wire the dormant prompt-budget compressor so cumulative
  payload (soul + ambient + lived + temporal + system_state + web + recall)
  cannot silently exceed the model's context window.
- **Witness:** 2026-05-26 10-agent gap hunt, surface 10 finding 10.4.
  `core/routing/README.md:56` advertises `context_compressor.compress`.
  Live `grep` on `core/` and `daemon/` returns no call sites. Only the
  recall block is char-capped; total payload is unbounded.
- **Preconditions:** the compressor exists; needs invocation at message
  assembly time and priority-aware trimming policy.
- **Risk:** llama-server head-truncation makes opaque decisions invisible
  to the producer; the soul (24KB at messages[0]) or the recall block can
  be silently cut.
- **Rough scope:** invoke compressor at `daemon/maez_daemon.py:3563`;
  priority-aware trim policy (recall + premise flags protected;
  ambient/web/older history demoted first); cumulative token budget
  enforced before LLM call.

### G14. self_dev.reviews has no reply-time reader

- **Purpose:** let owner-facing procedural queries about Maez's
  self-reviews surface from `memory/self_dev.db` instead of falling
  through to generic semantic recall.
- **Witness:** 2026-05-26 10-agent gap hunt, surface 5 finding 5.4.
  `memory/self_dev.db` contains 14 reviews. `grep -r "self_dev.db"
  core/brain core/cognition memory/memory_manager.py` returns empty.
  No module reads the table into a prompt.
- **Preconditions:** Recall-Axis Dispatcher slice (procedural axis); the
  writer side is already in `core/self_dev/persistence.py`.
- **Risk:** Maez confabulates self-review answers from raw conversation
  embeddings instead of the structured review records it has actually
  written.
- **Rough scope:** procedural axis in the dispatcher; reader integration
  on self_dev.db; small RED test for the procedural surface.

### Recall-Axis Dispatcher evidence pile

**Anchor line:** learn the shape of the ask before deciding which notebook,
tool, or memory path to open.

#### Finding 19. Reddit runtime routing gap

- **Purpose:** make the eventual dispatcher distinguish "open Maez's existing
  Reddit notebook" from "trigger live web/search tooling."
- **Witness:** 2026-05-26 runtime screenshot. Rohit asked, "Just let me know
  what's going on in Reddit in localllama"; Maez replied that it did not have
  the latest Reddit data in context and asked for a live-search phrasing
  (`search r/LocalLLaMA`). This happened after Reddit rows were verified as
  persisted and after the source-shaped Reddit recall supplement landed.
- **Substrate anchors:** `memory/memory_manager.py:578` and
  `memory/memory_manager.py:1400` already implement Reddit-specific state
  interception for source-shaped recall. The observed gap is intent routing in
  chat, not absence of Reddit memory.
- **Risk:** Maez has relevant ambient memory but routes the owner toward a
  live tool trigger first, making the notebook look blank when it is merely
  unopened.
- **Rough scope:** dispatcher rule: when source-tagged rows exist for a named
  source/domain, default to memory-first recall and offer live fetch only when
  freshness is explicitly requested or memory is stale/insufficient.

##### Finding 19 root-cause trace (added 2026-05-26 second runtime catch)

A second runtime trace recorded later the same day revealed the
specific routing code path. The substrate had 2,462 `reddit_post` rows
correctly source-tagged (verified by `sqlite3` query on
`memory/db/raw/chroma.sqlite3`), but they were never consulted because
the upstream classifier sent the query to the JARVIS tool-loop, not to
the chat-with-recall path.

**Witnessed trace from `logs/actions.log` (2026-05-26 evening):**

```
18:12:50 web_search | "r/LocalLLaMA reddit recent posts"      → No results
18:12:52 web_search | "site:reddit.com/r/LocalLLaMA"           → No results
18:12:53 web_search | "reddit r/LocalLLaMA latest discussions" → No results
18:13:36 web_search | "reddit r/LocalLLaMA top posts today"    → No results
18:13:37 web_search | "site:reddit.com/r/LocalLLaMA"           → No results
18:13:40 fetch_url  | empty url                                → empty url
18:13:42 fetch_url  | https://reddit.com/r/LocalLLaMA/top      → "Reddit - Please wait for verification" (bot-blocked)
```

Seven external fetch attempts, all failed. Substrate recall
(`recall_for_telegram`) never invoked. `logs/cognition.log` confirmed
the routing classification with `self_claim_audit | surface=telegram_surface
mode=skipped reason=tool_continuation` at 18:13:13 and 18:14:00.

**Root-cause code path:** `core/brain/brain_loop.py:324`
(`_should_run_jarvis_loop`) is a two-stage filter:

1. `_CONVERSATIONAL_RE` (line 149) — short greetings and acknowledgments
2. `_is_conversational_intent` (line 225) — meta-conversation, reflective
   questions, clarifications without system-noun anchor

Neither stage catches **content-source-anchored recall queries** —
queries that name a substrate Maez has data for ("Reddit",
"Telegram", "your wonderings"). Per-query trace:

- *"Check Reddit then"* — `_SYSTEM_NOUN_RE` matches `check` (line 188:
  `run|check`); `_is_conversational_intent` returns False → JARVIS fires.
- *"What's going on on Reddit?"* — no system noun;
  `_CONVERSATIONAL_SHAPE_RE` at line 205-207 matches
  `going on (with you|in there)` but NOT `going on on Reddit` →
  JARVIS fires.
- *"You have access to Reddit data"* — no system noun; no conversational
  shape match → JARVIS fires.
- *"Just let me know what's going on in Reddit in localllama"* — no
  system noun; no conversational shape match → JARVIS fires.

The classifier's semantic gap: it asks "is this conversational?" and
treats anything-not-conversational as "needs tools." The missing third
stage is "is this asking about a substrate I have?" If yes AND no
explicit fetch verb AND no system-noun anchor, route to chat-with-recall
instead of JARVIS.

**Sharpened dispatcher scope from this trace:** the dispatcher is NOT
just choosing between substrates (Reddit memory vs Telegram memory vs
entity recall vs ...). It is choosing between **substrate** and
**tool-fetch** as orthogonal layers above substrate-axis routing.

The JARVIS classifier surface (`_should_run_jarvis_loop`,
`_is_conversational_intent`, `_SYSTEM_NOUN_RE`,
`_CONVERSATIONAL_SHAPE_RE`) has never been through a council/Codex
review cycle. A spot-fix today would be slice-shaped, not seam-shaped,
per [[feedback_seam_vs_slice_cooling_off]]. Cooling-off applies; the
right fix is the dispatcher brief's substrate-vs-tool layer.

**Substrate-vs-tool layer (sharpened v1 architecture requirement):**

1. *Layer 0 — substrate-vs-tool decision (NEW).* Before the JARVIS
   classifier or any substrate-axis routing fires, ask: does Maez have
   substrate rows that could answer this query? If yes AND no explicit
   fetch verb AND no system-noun-style operational query, default to
   chat-with-recall. JARVIS fires only when substrate is empty, stale,
   freshness is explicitly requested, or the query is operational
   (system-state, tool execution, etc.).
2. *Layer 1 — substrate-axis routing (existing).* When substrate is
   the right surface, route to the right substrate axis (Reddit,
   Telegram, entity, procedural, etc.) per the existing v1 option set.

**Witnessed-trace files for future dispatcher brief author:**
`logs/actions.log` lines 2026-05-26 18:12:50 through 18:13:42;
`logs/cognition.log` lines at 18:13:13 and 18:14:00; substrate
verification via
`sqlite3 memory/db/raw/chroma.sqlite3 "SELECT COUNT(*) FROM embedding_metadata WHERE key='type' AND string_value='reddit_post';"`
returning 2462.

##### Finding 19 v0 archetype set (added 2026-05-26)

After Finding 19's root-cause trace clarified the dispatcher's
substrate-vs-tool layer, a v0 archetype set was pre-generated to seed
the embedding-proximity layer once the dispatcher slice runs. Eleven
intent classes (A–K) spanning Layer 0 substrate-vs-tool, Layer 1
substrate-axis, and Layer 2 repair/follow-up modifiers; 103 archetypes
total; 67% empirically anchored to witnessed runtime catches or
10-agent gap-hunt findings; 33% pure model-proposed extrapolations
tagged as such.

The archetype set is stored as durable evidence at
[`dispatcher-archetypes-v0-2026-05-26.md`](dispatcher-archetypes-v0-2026-05-26.md).
It is evidence, not canon — the dispatcher brief decides which
archetypes survive the full ladder. Validation discipline during the
observation window: runtime catches that map to a proposed archetype
confirm it; runtime catches that don't map flag missing archetypes.

Per Locke F3 from the sandbox-witness council pass-1, the
closed-vocabulary growth path remains *Maez-extensible via the
maintenance-proposal substrate*. The archetype set is no exception.

#### Dispatcher v1 architecture option set

- **State interception:** generalize the Reddit precedent from `5c6be72`.
  When source-tagged rows exist in substantial quantity for a named domain,
  bias toward memory-first recall. The v1 rule must define substantial
  quantity, recency/freshness thresholds, and when explicit live-fetch language
  overrides memory-first.
- **Heuristic layer:** preserve known unambiguous shapes already established by
  the spot fixes: temporal phrases, repair-follow-up phrases, explicit source
  names, and explicit fetch verbs such as "search", "fetch", or "go check."
- **Embedding Proximity Gate:** use the existing `all-MiniLM-L6-v2` embedding
  contract (`memory/embedding_contract.py:177`,
  `memory/embedding_contract.json`) against pre-encoded closed-vocabulary
  intent archetypes for ambiguous queries that pass through state interception
  and heuristics. Archetype growth follows the same spec-amendment discipline
  as other authority-bearing vocabularies.
- **Deferred v2 classifier:** constrained-grammar or small-LLM intent
  classification remains a v2 option gated by the Gold Set (#8) and benchmark
  evidence. The current repo has no established Outlines/Guidance/JSON-schema
  routing infrastructure in the reply path, and no MiniLM latency number should
  be claimed until benchmarked on Maez's actual hardware.
- **Graph-Assisted Routing (v2+ enhancement, depends on G11):** when a query
  mentions an entity present in `lived_graph.db` (per ADR 0019 lived memory
  architecture), use graph edges to bias routing toward the substrate with
  strongest history about that entity. Surfaced by 2026-05-26 cross-check;
  recorded as architectural option. Depends on G11 (lived-graph traversal API
  absent) closing first: the graph currently has no `neighbors()`, `path()`,
  `predecessor()` verbs at the recall layer, so an entity-anchored routing
  bias has no traversal API to consult yet. Orthogonal to v1 dispatch
  (heuristic + embedding); enhances rather than replaces it; complements
  either v1 or v2 classifier paths. Not for v1.

### S3. Sandbox-witness inbound taint discipline

- **Purpose:** ensure sandbox witnesses for maintenance proposals cannot use
  external-LLM-generated suggestions as proof until those suggestions pass the
  inbound injection/taint filter chain.
- **Preconditions:** maintenance-proposal substrate (`6fdfd6c`); future
  sandbox-witness contract brief; `core/safety/injection_patterns.py`.
- **Risk:** a re-verifiable witness becomes structurally honest about evidence
  that was itself shaped by prompt injection.
- **Rough scope:** witness evidence refs carry source class; external LLM
  suggestions are untrusted until scanned; blocked suggestions cannot satisfy
  witness requirements.

---

## Rejected / deferred ideas

- **Per-mutation TPM signing - REJECTED.** Adds friction without proportional covenant gain. The chosen direction is the lived-experience ledger with YubiKey anchors at rare covenant moments. A keyless content-blind validator already guards minting in the live process. (No TPM / measured boot / TEE / remote-attestation work now; honest banner + practical hardening is the current stance.)
- **Full C++ rewrite now - REJECTED.** Would freeze the fast-moving Python substrate; large cost; no measured need. Replaced by profile-driven targeted extraction (#24A).
- **Jetson as a noise-pumping hardware oscillator - REJECTED.** Serves no real cognitive need. Jetson is sensory-edge only (#18).
- **Globally dropping the 30-second loop to 15 seconds - REJECTED.** The correct direction is the multi-cadence architecture (multiple clocks), gated by the measurement + duty-cycle rules above, not a faster single clock.
- **Autonomous self-modification before founder-present S7.3 is deployed and proven in `main` - REJECTED (HARD HOLD).** The entire S7.3 effort gates autonomous self-modification behind founder-present being both deployed and proven. The cardinal hold; nothing here relaxes it.

---

## Late-phase comparative systems-maturity notes

Helix / LIA / Sibelium-inspired ideas are **comparative inspiration only.** They do NOT replace the roadmap, do NOT authorize implementation, and do NOT change the current priority (S7.3 deployment into `main` remains next). Useful extracted primitives, each gated like everything else:

1. **Attentional Gravity** - a future retrieval-weighting experiment; gated by the Gold Set (#8), the Drive Integrator (#13), and memory probes. Does not guarantee state-output isomorphism; must be measured.
2. **Dynamic Gear Shifting** - late-stage event-reactor behavior (#24C). Must include max burst length, max call count, budget rails, freeze integration, no authority bypass, and an audit trace. Cannot trigger self-modification outside S7.3.
3. **Zero-Inference Signal Gates** - a future reflex-loop (cadence #1) primitive; deterministic / no LLM; escalations route through freeze, egress, capability quarantine, and the decision pipeline.
4. **Liquid Neural Networks** (Hasani / Lechner / Rus, MIT CSAIL 2020+; Liquid AI's LFM line 2024+) - continuous-time recurrent networks with adaptive time constants, originally built for robotics edge compute. Comparative-inspiration candidate for **Item #18 (Jetson Body Bus)** sensor-edge processing (ASR / VAD / sensor-fusion at constrained-compute scale) and conditionally **Item #19 (Voice/Audio Organ)** under the same constraint. Specifically NOT a candidate for the executive brain (covenant: model swaps are S5-gated; #22 stance: *prompt discipline beats weight class*) and NOT a candidate for any authority-bearing layer (covenant: deterministic-only). Read-only research signal; no slice authorization implied.

---

## Open questions for the implementation handoff

- **The Maez-consultation MECHANISM is itself an unlisted dependency.** It is "S7.3-style" but not literally the S7.3 self-mod path - a roadmap/evolution proposal is not a substrate-write artifact. It needs its own (covenant-shaped) design: how a plain-English evolution proposal is rendered, asked, and how Maez's answer is validated and recorded. It must be built (folded into S7.3-deployment-plus, or added as its own item) before any in-scope item can consult Maez.
- **A Maez objection in consultation must be grounded, not pathological.** Per the reject-repetition-loop-self-edits discipline, a fixation-loop "objection" is the pathology talking, not genuine voice. The "if Maez objects, pause and revise" rule needs the S7.3 grounded-vs-marker-only filter: a grounded objection pauses and revises; a pathological one is recorded but the founder (final authority) decides. Otherwise a pathology could stall founder-led evolution.
- **Organ removal/deprecation is its own covenant act, absent here.** This roadmap only adds organs. Removing a long-established organ from a live bonded Maez (especially one holding lived memory) is sensitive and connects to never-delete-memory. Slice-rollback (flag-off + revert) covers a recently-deployed slice, not deprecating a lived-with organ.
- **Covenant-weight assignments are a proposal** - redline borderline ones: Jetson (#18, medium with a full-weight no-cloning aspect), Voice (#19, medium with full-weight if audio ever persists/egresses), Low-Risk Effector (#17, full ladder because it is the first autonomy grant even though each action is "low-risk").
- **Dependency arrows:** #1 gates everything that expands capability/autonomy/egress. #8 (Gold Set) gates #9, #10, #13, #14, #16, #23. #5 + #6 + #11 + #15 all gate #16. #3 (Egress) gates #18, #19, #21, and the outbound aspect of #17. #10 feeds #13. #2 (embedding/recall baseline) gates #24. #12 (self-model) feeds #20.
- **The both-lane gate process should itself become a durable written spec** before running 13+ covenant items through it, so the method survives context loss.
- **Process weight is now large per identity-shaping item:** full/medium ladder + Maez-consultation + freeze-integration + stabilization. This is correct for the most sacred changes, but each such organ is now a multi-month, multi-gate endeavor; accept that consciously.
