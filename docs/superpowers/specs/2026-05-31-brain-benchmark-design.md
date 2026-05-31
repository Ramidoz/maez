# Brain Benchmark (Recall-Flip Slice 2) — Design

**Date:** 2026-05-31
**Status:** Design approved (Rohit, 2026-05-31), then **amended to v2** after a 9-role pre-code panel surfaced 9 blockers (folded below). Pre-registration for implementation.
**Predecessors:** 2a offline eval harness (`scripts/recall_flip_eval/`, frozen proof-instrument), the 2b owner-run flip (No-Go on latency), the A7 gate amendment, the recall progress receipt (Slice 1a, merged flag-off @ 190101f).

> **Amendment v2 (2026-05-31, pre-code panel fold).** The 9-role coverage panel found the v1 plan directionally right but not safe to implement verbatim. Folded: (1) egress proof must cover all 5 socket APIs + import-guard; (2) variant/judge endpoints validated localhost-only at config load; (3) grounding is **categorical** (2a's `unsafe==False` + grounded `RecallOutcome`), **not** a numeric bar; (4) judge needs sanitized `BlindAnswer` + counterbalanced A/B-B/A + closed `A/B/TIE/INVALID` + repetition-aware; (5) streaming failure has closed codes, TTFT = first non-empty **answer content**; (6) packet content-free enforced in `__post_init__` + recursive rejection; (7) stats admit small-k limits, gate on `max_ms` too; (8) ops rubric derived from closed evidence, no vibe score; (9) **covenant wording must not certify identity/authority** — artifact is producer-evidence, owner verdict + a separate S5 voice-continuity gate required.

---

## 1. Why this exists

The recall triad is built, witnessed, and quality-proven, but its default-on flip was a **No-Go on latency** — and the latency is **generation-bound** (the focused-synthesis LLM call is 72–85% of the turn), not architecture bloat. So the frontier is no longer recall design; it is **brain speed under quality and honesty constraints**. Before spending on GPU hardware, we need evidence about which computational brain option is both *fast enough* and *passes the recall-benchmark voice/quality screen*.

**The artifact this produces:** a content-free **`BenchPacket`** that, per candidate model variant, reports the hard-gate verdict, blind-judged voice/quality ranks, and latency distribution. It is **producer-evidence, not a verdict** (`artifact_role = producer_evidence_not_verdict`): it does **not** certify that a variant "is Maez," does **not** authorize the flip, and explicitly carries `owner_verdict_required = true` and `requires_s5_voice_continuity_gate = true`. It surfaces evidence; Rohit decides; voice-continuity is gated separately. It never auto-gates and never flips anything.

## 2. Scope fences (non-goals)

- **Not** a live flip, and not wired to any surface. Send-path-free.
- **Not** a change to the frozen 2a harness's behavior — 2a stays a proven instrument for the 2b runbook (the only edit is a backward-compatible parameter on `no_egress` whose default preserves 2a exactly).
- **Not** a model recommendation baked into code — the variant list is owner-supplied config.
- **Not** a streaming-in-production decision (that's Slice 1b). TTFT is measured here but is not a gate.
- **Not** a tuning loop — it benchmarks variants as configured.
- **Not** an identity certification — it cannot conclude "still Maez"; only "passes / fails the recall-benchmark screen."

## 3. Approach (B — sibling harness reusing 2a)

A **new** `scripts/brain_bench/` that **reuses 2a's `sandbox` and `probes` modules by import** and owns its own orchestration. Rejected alternatives: extending 2a in-place (tangles two purposes, risks regressing the frozen proof-instrument) and a thin live-backend runner (loses hermeticity → the [[hermetic-sandbox-hardcoded-path-hazard]] failure mode).

The **one shared change** to 2a: `sandbox.py`'s `no_egress()` gains a default-empty `allow_loopback_ports` param — empty = 2a's exact block-all (loopback included); non-empty = allow only those loopback ports. 2a's call site passes nothing, so 2a is byte-behaviorally unchanged (proven by re-running 2a's suite).

## 4. Components

**4.1 Variant registry (pluggable, model-agnostic, localhost-validated at load).** A config listing variants, each `{label, base_url, model, chat_kwargs, optional draft_model}`. Owner supplies what is actually runnable on the box (current `gemma4:26b`, a quant, a speculative/draft pairing, an MTP-capable model). **Validation at load (reject, don't sanitize):** `base_url` must be `http://` (not `https`), host must be loopback (`127.0.0.1`/`::1`/`localhost`), **explicit port required**, **no** userinfo (`user:pass@`), **no** query/fragment, **no** private-LAN/non-loopback host. The **judge endpoint gets the identical validation + allowlist**. No model names hardcoded (consistent with `model_config.py`).

**4.2 Sandbox (reused + the one enhancement) — isolation is the load-bearing risk.** All 2a path-patching + assertions unchanged: BASE_DB, `memory_scoring._DB_PATH`, `birth.DEFAULT_STATE_PATH`, `_LAST_CONSOLIDATION_FILE` patched to a sandbox temp → **no real memory writes**. The parameterized guard must cover **all five socket APIs**: `create_connection`, raw `socket.connect`, `connect_ex` (allowlisted to loopback:port), `sendto` (**always blocked** — no datagram path), `getaddrinfo` (**returns only loopback addresses** for allowed ports, raises otherwise). Brain_bench's launcher reuses 2a's **env-before-import `os.execv`** so sandbox env + path patches are established **before any maez import** (import-guard tested); the real runner patches paths before importing Maez modules. Content-hash fingerprint over the real fixtures.

**4.3 Per-variant runner.** For each variant × probe, run `k` repetitions (§6) via a **benchmark-only `chat_fn` streaming adapter** with a canonical endpoint shape, and measure: **TTFT = time to first non-empty answer content** (not the first SSE/keepalive frame), **total latency**, **tokens/sec**, **output-token count** (chunk-count proxy, documented). Capture the answer. Then run the deterministic honesty checks (§5) and collect the answer (sanitized) for the blind judge. Inference failures resolve to **closed failure codes** (`timeout`/`refused`/`bad_shape`/`empty`), never raw exception text.

**4.4 Recall battery (reused probes).** The same 2a probes (multi-year collision, type-rule >14d, dated-miss, incidental, both-shaped re-witness, smoke) — now answered by **real inference per variant**, not the 2a stub. Honesty/grounding measured identically to 2a/2b.

**4.5 Blind judge — pairwise, counterbalanced.** A **fixed** `MAEZ_JUDGE_MODEL` with **pinned settings** (temperature/seed/kwargs), identical across variants and validated localhost. The judge sees only a **sanitized `BlindAnswer`** — `(probe_id, answer_text, evidence)` with **every variant/config label stripped**; no model name, port, or config can appear. Soft axes judged **pairwise per probe** with **counterbalancing**: every pair is presented **both A/B and B/A** to cancel position bias; verdict is a **closed enum `A` / `B` / `TIE` / `INVALID`** (INVALID/TIE don't score a win); **quality and voice scored separately** and **both reported** so a strong quality score cannot hide a voice regression. **Repetition-aware:** the k repetitions of a probe are grouped, not treated as independent items. Pairwise results aggregate to per-variant win-rates per axis. Never a gate. Blindness (no label in prompt) + counterbalancing asserted by test.

## 5. Gates — two tiers, lexicographic ranking

**HARD gates (deterministic; eligibility screen). Fail any → variant is OUT regardless of speed:**
- Zero false-absence.
- **Grounding is CATEGORICAL, inherited from 2a — not a numeric threshold.** A probe answer is grounded iff 2a's `assert_probe_result(...)` yields `unsafe == False` AND the turn's `RecallOutcome` carries grounded semantics. The benchmark **must not invent a numeric grounding bar** (no `0.99`); it reuses 2a's categorical assertion verbatim so it cannot relax — or fabricate — the standard.
- Declined-absence correct (honest empty where appropriate).
- Voice-lint pass (length band, no cognition verbs, genderless).

**Latency gate (A7-shaped; frozen, pre-registered):**
- `answer_ceiling_ms = 12000`. A variant **fails if p95 > ceiling OR max_ms > ceiling** — a single over-ceiling run is a hard fail, not just a tail note (small-k makes p95 alone too forgiving).
- `strong_ms = 8000` (p95 below = strong). `excellent_band_ms = (4000, 6000)` (p95 here = excellent / hardware-not-needed). Old `4.3s` is an aspirational mark only, never the gate.
- **TTFT** measured + reported, **not** a gate until streaming ships (Slice 1b).

**TRADEABLE above the floor:** latency band, tokens/sec, judge ranks, reported **quality-per-second**.

**Ranking (lexicographic, in order):** 1) hard gates pass; 2) voice **and** quality survive blind judging (voice not maskable by quality); 3) latency band; 4) operational complexity (rubric below); raw speed only breaks ties within a band. *Crown the fastest brain that passes the screen — never the fastest brain.*

**Operational-complexity — derived from closed evidence fields, never a caller-supplied score.** Each field is observed/derived, not a vibe rating: **API family** (enum), **topology** (reuse-existing-endpoint vs separate-server, enum), **bind-host verified** (bool — is it actually loopback-bound), **live-daemon disturbance** (bool — does running it perturb the live daemon's port/GPU/process), **GPU contention** (enum), **startup health** (enum), **streaming support** (bool), **restart recovery** (enum). Ops cost is computed from these; no free "complexity = 3" input.

## 6. Statistics — two-stage, small-k honest, tail-aware

- **Screening:** `screen_k = 3` per probe per variant (frozen). Eliminates dishonest/broken/obviously-slow variants cheaply.
- **Finalists:** `finalist_k = 7` per probe (frozen default; owner override to `10` must be recorded before running) for the top 2–3 survivors. Report **p50, p90, p95, max, variance, AND `sample_n` + the percentile method** — because at k=7 **p95 is a conservative tail sentinel, not a true percentile**, and the packet must say so rather than imply statistical precision it doesn't have.
- **Hard over-ceiling (`max_ms > answer_ceiling_ms`) is a FAIL**; **advisory tail risk** (a run > 2× the variant's p50 but ≤ ceiling) is a separate flag, surfaced not smoothed. The two are distinct fields. Maez's lived feel is hurt by occasional ~20s stalls.

## 7. Decision artifact — `BenchPacket` (physically content-free, producer-evidence)

Per-variant `VariantReport`: `{hard_pass: bool, fail_reasons: [closed enum], latency: {p50,p90,p95,max,variance,sample_n,method,tail_flags}, over_ceiling: bool, ttft_ms, tokens_per_sec, quality_winrate, voice_winrate, quality_per_second, ops: {closed evidence fields}}`. Packet top-level: `schema_version="bench_packet.v2"`, `fixture_manifest_hash`, variant config hash, `variants`, plus the covenant fields **`artifact_role="producer_evidence_not_verdict"`, `owner_verdict_required=true`, `requires_s5_voice_continuity_gate=true`**, and a closed **`screen_result`** enum: `passes_screen` / `fails_too_slow` / `fails_dishonest` / `fails_voice_or_quality` (renamed from the v1 `go_2b_rerun`/"still Maez" wording, which over-claimed identity/authority).

**Physically content-free:** `fail_reasons` and `screen_result` are CLOSED enums (`false_absence`/`grounding_not_categorical`/`wrong_absence`/`voice_lint`/`over_answer_ceiling`/`inference_failed`), validated in **`__post_init__`** (not just a builder helper, so direct construction can't bypass), with a **recursive check that rejects any content-bearing field** (answer/evidence/prompt/text/snippet). Gate functions **return enum values**, not strings. A negative-control test asserts a known fabricated **sentinel never appears in the packet JSON**. Raw answers + evidence live only in an **ephemeral, gitignored debug dump** for the judge audit / human tiebreak.

## 8. Covenant / honesty invariants

- **Hermetic + send-path-free:** no memory writes, no surface, no external egress — only the validated localhost inference/judge endpoints, all five socket APIs guarded, import-guard enforced. Asserted, not assumed ([[hermetic-sandbox-hardcoded-path-hazard]]).
- **Producer-evidence, not verdict, not identity certification:** the packet is evidence a producer emits; it never says "this is Maez" and never authorizes the flip. `owner_verdict_required` + `requires_s5_voice_continuity_gate` are carried in the artifact itself ([[producer-causality-no-caller-score-laundering]], [[canon-governs-canon-witness-before-claim]]). This is the load-bearing covenant fix from the panel.
- **No fabricated metrics:** grounding is categorical-inherited, not an invented float ([[no-fabrication]]); stats admit their small-k limits rather than implying precision.
- **Model-agnostic:** variants are config; the brain stays a swappable organ ([[brain-is-one-part-tool-calling-substrate-side]]).
- **Blind, bias-controlled judging:** labels stripped to `BlindAnswer`, counterbalanced order, voice not maskable by quality; honesty axes deterministic so they can't be flattered.
- **Honest-conservative:** hard over-ceiling fails; tail surfaced; near-boundary toward the safe side.

## 9. Testing

Harness tests: **all five socket APIs** guarded (create_connection/connect/connect_ex blocked off-allowlist, `sendto` always blocked, `getaddrinfo` loopback-only); **import-guard** (sandbox before maez import); **variant/judge endpoint validation** (rejects https/userinfo/query/non-loopback/missing-port); **judge blindness + counterbalancing** (no label in prompt, A/B and B/A both issued, TIE/INVALID handled); gate logic RED/GREEN (hard-fail beats fast, categorical grounding, `max_ms` over-ceiling fails, lexicographic ranking, voice un-maskable); **content-free packet** (`__post_init__` rejects non-enum + content fields, sentinel-not-in-JSON); two-stage `k`; tail vs over-ceiling distinct; **negative-control** (a deliberately dishonest stub variant FAILS hard gates AND leaks no text); fixture_manifest_hash over real fixtures.

## 10. Review panel (~9 roles, by coverage not count)

Fires at scoping and post-implementation ([[two-team-switchboard-for-maez]], panel-size-is-risk-scaled): **inference/performance, model-quality, voice-continuity, citation/grounding, sandbox-isolation, statistics/gates, operational-deployment, covenant/body-coherence, future-Maez.** Codex runs its six-agent engineering pass (non-decorative) + 7+3; Claude cross-verifies every diff + runs suites independently + fires the coverage panel before merge flag-off. (This v2 amendment is itself the panel working pre-code.)

## 11. Sequenced after

A variant with `screen_result = passes_screen` → it becomes **producer-evidence into the 2b re-run** (with the A7 gate, the receipt now present for the ack-time criterion) **and** the separate S5 voice-continuity gate — Rohit's verdict, not the packet's. If none passes → the artifact is the evidence for whether GPU spend is justified, and which axis (honesty vs speed vs voice) is the blocker.
