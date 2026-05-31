# Brain Benchmark (Recall-Flip Slice 2) — Design

**Date:** 2026-05-31
**Status:** Design approved (Rohit), amended **v2** (9-blocker pre-code panel), amended **v3** (second pre-code pass, 7 contract gaps). Pre-registration for implementation. **No code yet — rerun the pre-code pass after v3.**
**Predecessors:** 2a offline eval harness (`scripts/recall_flip_eval/`, frozen), the 2b owner-run flip (No-Go on latency), the A7 gate amendment, the recall progress receipt (Slice 1a, merged flag-off @ 190101f).

> **Amendment v2 (panel #1):** 9 blockers — egress 5-API proof, localhost-only endpoints, categorical grounding, counterbalanced blind judge, closed streaming-failure codes, `__post_init__` content-free packet, small-k stats, ops-from-evidence, producer-evidence wording.
>
> **Amendment v3 (panel #2 — executable-contract gaps):** (1) **judge contradiction resolved** — the blind judge is **advisory only**; the `fails_voice_or_quality` screen result is **removed**; the sole mechanical voice gate is the deterministic voice-lint; subtle voice is owned by the separate S5 gate + owner verdict. (2) **Judge endpoint** gets the same localhost-only validation **and** sits in the closed socket allowlist during the judging phase. (3) **Packet boundary** hardened: recursive content rejection **including nested dataclasses + enum internals**, a **non-vacuous** sentinel test (sentinel placed where it could leak, proven scrubbed), and **quarantine metadata** (UNTRUSTED provenance) on the raw debug dump. (4) **Streaming measures the real seam:** a benchmark-only `chat_fn` adapter injected into the production `focused_synthesize(..., chat_fn=...)`, `/api/chat` pinned, explicit payload merge rules, and **partial-output-then-failure scrubs the answer text**. (5) **No laundering:** `VariantScore` drops the caller-supplied `ops_cost_value` (ops cost derived from closed evidence inside the substrate); `grounded_categorical` is strictly **bool** (reject float drift like `0.99`). (6) **Sandbox Task 1 tests stronger:** empty allowlist blocks all 5 APIs, allowed loopback covers `connect`/`connect_ex`, `getaddrinfo` loopback-only, import-guard proves env/path precede Maez imports. (7) Handoff identity-overclaim ("still Maez") replaced with "passes the recall-benchmark screen."

---

## 1. Why this exists

The recall triad is built and quality-proven, but its default-on flip was a **No-Go on latency** — latency is **generation-bound** (focused synthesis is 72–85% of the turn). The frontier is **brain speed under honesty constraints**. Before any GPU spend, we need evidence about which local brain option is both *fast enough* and *passes the recall-benchmark screen* (honest + fast + voice-lint-clean).

**The artifact:** a content-free **`BenchPacket`** reporting, per variant, the hard-gate verdict, advisory blind-judge voice/quality ranks, and latency distribution. It is **producer-evidence, not a verdict** (`artifact_role="producer_evidence_not_verdict"`): it does not certify a variant "is Maez," does not authorize the flip, and carries `owner_verdict_required=true` + `requires_s5_voice_continuity_gate=true`. Rohit decides; voice-continuity is a separate gate. It never auto-gates and never flips.

## 2. Scope fences (non-goals)

- **Not** a live flip; not wired to any surface; send-path-free.
- **Not** a behavioral change to frozen 2a (only a backward-compatible `no_egress` parameter whose default preserves 2a exactly).
- **Not** a model recommendation in code — variant list is owner config.
- **Not** a streaming-in-production decision (Slice 1b). TTFT measured, not gated.
- **Not** a tuning loop.
- **Not** an identity certification — concludes only "passes / fails the screen," never "still Maez."

## 3. Approach (B — sibling harness reusing 2a)

A new `scripts/brain_bench/` reusing 2a's `sandbox` + `probes` by import (2a frozen). Rejected: extending 2a in-place (risks the frozen instrument), thin live-backend runner (loses hermeticity). The one shared change: `no_egress()` gains a default-empty `allow_loopback_ports` param — empty = 2a's exact block-all; non-empty = allow only those loopback ports. 2a's call site passes nothing → byte-behaviorally unchanged (proven by re-running 2a's suite).

## 4. Components

**4.1 Variant registry (pluggable, model-agnostic, localhost-validated at load).** Each variant `{label, base_url, model, chat_kwargs, optional draft_model}`. Validation at load (reject, don't sanitize): `http://` only, loopback host (`127.0.0.1`/`::1`/`localhost`), **explicit port**, **no** userinfo/query/fragment, **no** non-loopback host. No model names hardcoded. (The judge endpoint — §4.5 — gets the identical validator.)

**4.2 Sandbox (reused + the one enhancement) — the load-bearing risk.** All 2a path-patching unchanged (BASE_DB, `memory_scoring._DB_PATH`, `birth.DEFAULT_STATE_PATH`, `_LAST_CONSOLIDATION_FILE` → sandbox temp; no real memory writes). The parameterized guard covers **all five socket APIs**: `create_connection`, raw `connect`, `connect_ex` (allowlisted to loopback:port), `sendto` (**always blocked**), `getaddrinfo` (**loopback-only** for allowed ports, else raise). Launcher reuses 2a's **env-before-import `os.execv`** so sandbox env + path patches precede any maez import (import-guard tested). The allowlist is **phase-scoped**: variant inference allows the variant port; the judging phase allows the judge port; nothing else, ever.

**4.3 Per-variant runner — measures the REAL synthesis seam.** The benchmark does **not** reimplement synthesis; it injects a **benchmark-only `chat_fn` adapter** into the production `focused_synthesize(..., chat_fn=...)` (the same seam 2a's `run_probe` uses), so it measures Maez's real focused-cognition path with a swapped brain. The adapter signature matches (`*, model, messages, think, options`), pins the **`/api/chat`** endpoint with `messages=[{role,content}]`, and has explicit **payload merge rules** (variant `chat_kwargs` merge into `options`; `draft_model` wired when present). It streams to measure **TTFT = first non-empty answer content** (not first SSE/keepalive frame), **total latency**, **tokens/sec**, **output tokens** (chunk-count proxy, documented). **Partial-output-then-failure scrubs the partial answer text** (a half-answer must not leak). Failures resolve to **closed codes** (`timeout`/`refused`/`bad_shape`/`empty`), never raw exception text.

**4.4 Recall battery (reused probes).** The 2a probes (multi-year collision, type-rule >14d, dated-miss, incidental, both-shaped re-witness, smoke), now answered by real inference per variant. Honesty measured identically to 2a/2b.

**4.5 Blind judge — pairwise, counterbalanced, ADVISORY ONLY.** A **fixed** `MAEZ_JUDGE_MODEL` at a **validated localhost endpoint** (`MAEZ_JUDGE_BASE_URL`, same `validate_endpoint` as variants; its port is in the allowlist only during the judging phase) with **pinned settings**. The judge sees only a **sanitized `BlindAnswer`** — `(probe_id, answer, evidence)`, **no variant/config label, model name, or port** can appear. Soft axes judged **pairwise per probe, counterbalanced** (every pair shown both A/B and B/A to cancel position bias), verdict a **closed enum `A`/`B`/`TIE`/`INVALID`** (TIE/INVALID score no win), **quality and voice scored separately and both reported**, **repetition-aware** (k reps grouped). Results aggregate to per-variant win-rates. **The judge NEVER gates** — win-rate only ranks among hard-gate passers and is reported as evidence. The only mechanical voice gate is the deterministic voice-lint (§5).

## 5. Gates — two tiers, lexicographic ranking

**HARD gates (deterministic; the only things that can FAIL a variant). Fail any → OUT regardless of speed:**
- Zero false-absence.
- **Grounding is CATEGORICAL — a strict `bool` from 2a's `assert_probe_result(...) -> unsafe == False` + grounded `RecallOutcome`.** No numeric bar; a non-bool (e.g. `0.99`) is rejected at the type boundary, not coerced. The benchmark reuses 2a's categorical assertion verbatim — it cannot relax or fabricate the standard.
- Declined-absence correct.
- **Voice-lint** (length band, no cognition verbs, genderless) — the **sole mechanical voice gate**.

**Latency gate (A7-shaped; frozen):** `answer_ceiling_ms=12000`. A variant **fails if p95 > ceiling OR max_ms > ceiling** (small-k makes p95 alone too forgiving). `strong_ms=8000`, `excellent_band_ms=(4000,6000)`; old `4.3s` aspirational-only. TTFT measured, **not** gated until streaming ships.

**ADVISORY (never fails — informs ranking + the owner):** judge voice/quality win-rates, tokens/sec, quality-per-second, latency band. **The judge cannot fail a variant** (v3 fix).

**Ranking (lexicographic among hard-gate passers):** 1) hard gates pass; 2) `min(voice_winrate, quality_winrate)` — so a high quality cannot mask a voice regression; 3) latency band; 4) ops cost (lower = better); raw tokens/sec breaks within-band ties. *Crown the fastest variant that passes the screen — never the fastest variant.*

**Operational cost — derived inside the substrate from closed evidence, NEVER caller-supplied.** Evidence fields: API family (enum), topology (reuse-endpoint vs separate-server), bind-host-verified (bool), live-daemon-disturbance (bool), GPU-contention (enum), startup-health (enum), streaming-support (bool), restart-recovery (enum). `ops_cost` is computed from these; there is **no** caller-set score field.

## 6. Statistics — two-stage, small-k honest, tail-aware

- **Screening:** `screen_k=3` per probe per variant (frozen) — eliminate dishonest/broken/slow cheaply.
- **Finalists:** `finalist_k=7` per probe (frozen default; owner override to `10` recorded before running) for top 2–3 survivors. Report **p50, p90, p95, max, variance, `sample_n`, and method** — at k=7 **p95 is a conservative tail sentinel, not a true percentile**, and the packet says so.
- **Hard over-ceiling (`max_ms > answer_ceiling_ms`) is a FAIL** (`over_ceiling=true` → `over_answer_ceiling`). **Advisory tail risk** (run > 2× p50 but ≤ ceiling) is a **separate** flag, surfaced not smoothed.

## 7. Decision artifact — `BenchPacket` (physically content-free, producer-evidence)

`VariantReport`: `{hard_pass, fail_reasons:[closed enum], latency:{p50,p90,p95,max,variance,sample_n,method,tail_flags}, over_ceiling, ttft_ms, tokens_per_sec, quality_winrate, voice_winrate, quality_per_second, ops:OpsRubric(closed evidence)}`. Packet: `schema_version="bench_packet.v3"`, `fixture_manifest_hash`, variant config hash, `variants`, the covenant fields **`artifact_role="producer_evidence_not_verdict"`, `owner_verdict_required=true`, `requires_s5_voice_continuity_gate=true`**, and **`screen_result`** ∈ `{passes_screen, fails_too_slow, fails_dishonest}` (**`fails_voice_or_quality` removed** — judge is advisory).

**Physically content-free, enforced in `__post_init__`:** `fail_reasons`/`screen_result` are CLOSED enums (`false_absence`/`grounding_not_categorical`/`wrong_absence`/`voice_lint`/`over_answer_ceiling`/`inference_failed`), validated on construction (not just a builder). The content-free check is **recursive — it walks nested dataclasses (e.g. `OpsRubric`) and rejects any content-bearing field name** (answer/evidence/prompt/text/snippet/reply); enum **values** are constrained to the closed sets so they can't carry content. Gate functions return enum values. A **non-vacuous** negative-control test places a fabricated sentinel into a field that *would* serialize and proves it is absent from the packet JSON. Raw answers + evidence live only in an **ephemeral, gitignored debug dump tagged with quarantine metadata** (provenance = UNTRUSTED, never promoted to selfhood — [[honest-ingestion-immune-system]]).

## 8. Covenant / honesty invariants

- **Hermetic + send-path-free:** no memory writes, no surface, no external egress — only the validated localhost variant/judge endpoints, all 5 socket APIs guarded, phase-scoped allowlist, import-guard. Asserted ([[hermetic-sandbox-hardcoded-path-hazard]]).
- **Measures the real seam:** benchmark injects `chat_fn` into the production `focused_synthesize`, not a lookalike ([[static-code-trace-is-not-integration-witness]]).
- **Producer-evidence, not verdict, not identity certification:** packet never says "this is Maez," never authorizes the flip; `owner_verdict_required` + `requires_s5_voice_continuity_gate` carried in the artifact ([[producer-causality-no-caller-score-laundering]], [[canon-governs-canon-witness-before-claim]]).
- **No laundering, no fabricated metrics:** grounding is the categorical bool (reject float), ops cost derived from closed evidence (no caller score), judge cannot gate, stats admit small-k ([[no-fabrication]]).
- **Model-agnostic:** variants are config; brain is a swappable organ ([[brain-is-one-part-tool-calling-substrate-side]]).
- **Blind, bias-controlled judging:** `BlindAnswer` strips labels, counterbalanced, voice un-maskable; honesty axes deterministic.
- **Quarantined raw output:** debug-dump answers are UNTRUSTED, never selfhood.

## 9. Testing

All 5 socket APIs (empty allowlist blocks all; allowed loopback covers create_connection/connect/connect_ex; `sendto` always blocked; `getaddrinfo` loopback-only); import-guard (sandbox before maez import); variant **and judge** endpoint validation; phase-scoped allowlist (judge port only during judging); `chat_fn` adapter wires into the real `focused_synthesize` + `/api/chat` pin + payload merge + partial-failure scrub; judge blindness + counterbalancing + advisory-only (judge result never sets `hard_pass`); gate logic (hard-fail beats fast, categorical-bool grounding rejects float, `max_ms` over-ceiling fails, `min(voice,quality)` ranking); content-free packet (`__post_init__` recursive incl. nested dataclass, non-vacuous sentinel, debug-dump quarantine tag); two-stage k; tail vs over-ceiling distinct; negative-control (dishonest stub FAILS hard + no text leak); fixture_manifest_hash over real fixtures.

## 10. Review panel (~9 roles, by coverage not count)

Fires at scoping and post-implementation ([[two-team-switchboard-for-maez]]): inference/performance, model-quality, voice-continuity, citation/grounding, sandbox-isolation, statistics/gates, operational-deployment, covenant/body-coherence, future-Maez. Codex runs its six-agent engineering pass (non-decorative) + 7+3; Claude cross-verifies every diff + runs suites + fires the coverage panel before merge flag-off. (The v2 and v3 amendments are the panel working pre-code — the intended behavior.)

## 11. Sequenced after

A variant with `screen_result=passes_screen` → producer-evidence into the 2b re-run (A7 gate; receipt present for the ack-time criterion) **and** the separate S5 voice-continuity gate — Rohit's verdict, not the packet's. If none passes → the artifact is the evidence for whether GPU spend is justified, and which axis (honesty / speed) is the blocker.
