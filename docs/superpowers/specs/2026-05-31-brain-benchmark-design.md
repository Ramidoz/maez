# Brain Benchmark (Recall-Flip Slice 2) — Design

**Date:** 2026-05-31
**Status:** Design approved (Rohit, 2026-05-31). Pre-registration for implementation.
**Predecessors:** 2a offline eval harness (`scripts/recall_flip_eval/`, frozen proof-instrument), the 2b owner-run flip (No-Go on latency), the A7 gate amendment, the recall progress receipt (Slice 1a, merged flag-off @ 190101f).

---

## 1. Why this exists

The recall triad is built, witnessed, and quality-proven, but its default-on flip was a **No-Go on latency** — and the latency is **generation-bound** (the focused-synthesis LLM call is 72–85% of the turn), not architecture bloat. So the frontier is no longer recall design; it is **brain speed under quality and honesty constraints**. Before spending on GPU hardware, we need evidence about which computational brain option is both *fast enough* and *still Maez*.

**The artifact this produces:** a content-free, advisory **`BenchPacket`** that, per candidate model variant, reports the hard-gate verdict, blind-judged quality/voice scores, and latency distribution — and recommends *"variant X is honest-enough AND fast-enough for the 2b re-run"* or *"none yet."* It **informs**; Rohit decides the 2b re-run. It never auto-gates and never flips anything.

## 2. Scope fences (non-goals)

- **Not** a live flip, and not wired to any surface. Send-path-free.
- **Not** a change to the frozen 2a harness — 2a stays a proven instrument for the 2b runbook.
- **Not** a model recommendation baked into code — the variant list is owner-supplied config.
- **Not** a streaming-in-production decision (that's Slice 1b). TTFT is measured here but is not the primary gate.
- **Not** a tuning loop — it benchmarks variants as configured; it doesn't auto-tune them.

## 3. Approach (B — sibling harness reusing 2a)

A **new** `scripts/brain_bench/` that **reuses 2a's `sandbox` and `probes` modules by import** and owns its own orchestration. Rejected alternatives: extending 2a in-place (tangles two purposes, risks regressing the frozen proof-instrument) and a thin live-backend runner (loses hermeticity → the [[hermetic-sandbox-hardcoded-path-hazard]] failure mode).

The **one shared change** to 2a's modules: `sandbox.py`'s socket guard becomes parameterized — 2a keeps strict "block all sockets"; brain_bench uses "allow only the inference localhost endpoint(s), block all other egress." 2a's behavior is unchanged (its call site passes the strict mode).

## 4. Components

**4.1 Variant registry (pluggable, model-agnostic).** A config (env-driven or a small declarative file under the sandbox) listing variants, each `{label, base_url, model, chat_kwargs, optional draft_model/speculative config}` — a way to reach a model on localhost. Owner supplies what is actually runnable on the box at config-time (e.g. current `gemma4:26b`, a smaller quant, a speculative-decoding/draft config, an MTP-capable model). The harness benchmarks whatever is registered. No model names hardcoded (consistent with `model_config.py`'s single-source-of-truth).

**4.2 Sandbox (reused + the one enhancement).** All 2a path-patching + assertions unchanged: BASE_DB, `memory_scoring._DB_PATH`, `birth.DEFAULT_STATE_PATH`, `_LAST_CONSOLIDATION_FILE` patched to a sandbox temp → **no real memory writes**. Socket guard parameterized to allow only the inference endpoint(s). Content-hash fingerprint over the real fixtures (the 2a `fixture_manifest_hash` discipline). Launcher reuses 2a's env-before-import `os.execv` pattern so the sandbox is established before any maez import.

**4.3 Per-variant runner.** For each variant, for each probe in the battery, run `k` repetitions (see §6) and measure: **TTFT** (a streaming call built for measurement only), **total latency**, **tokens/sec**, **output-token count**. Capture the answer. Then run the deterministic honesty/grounding/voice-lint checks and collect the answer for the blind judge.

**4.4 Recall battery (reused probes).** The same 2a probes (multi-year collision, type-rule >14d, dated-miss, incidental, both-shaped re-witness, smoke) — now answered by **real inference per variant**, not the 2a deterministic stub. Quality/honesty are thus measured identically to how 2a/2b measured them.

**4.5 Blind judge.** A **fixed** `MAEZ_JUDGE_MODEL`, identical across all variants, scores **answer-quality + voice-fidelity** seeing only `(probe, answer, evidence)` with the **variant label withheld and answers shuffled**. Comparative score, never a gate. Runs on the allowed localhost endpoint, after all variants' answers are collected (so it cannot drift per-variant). Judge-blindness is asserted by test.

## 5. Gates — two tiers, lexicographic ranking

**HARD gates (deterministic; eligibility for the 2b re-run). Fail any → variant is OUT regardless of speed:**
- Zero false-absence.
- Citation-grounding ≥ the **same bar 2a/A5 already use** (inherited, not a fresh number — the benchmark must not quietly relax the grounding standard the recall arc was proven against).
- Declined-absence correct (honest empty where appropriate).
- Voice-lint pass (length band, no cognition verbs, genderless).

**Latency gate (A7-shaped full-answer ceiling, NOT the old 4.3s line):**
- **Hard full-answer ceiling:** p95 ≈ **10–12s** — this is the pass/fail line. Over it → fail.
- **Strong candidate:** p95 **< 8s**.
- **Excellent / hardware-not-needed:** p95 ≈ **4–6s**.
- The old `4.3s` is retained only as an *aspirational "excellent" mark*, never the gate (it came from the flawed fast-refusal-vs-real-answer comparison).
- **TTFT** is measured and reported but is **not** the primary pass/fail unless/until streaming ships (Slice 1b). With receipts (Slice 1a), total answer time matters more than first token.

**TRADEABLE above the floor:** TTFT, total latency, tokens/sec, judge quality — used to rank passers, plus a reported **quality-per-second** figure.

**Ranking order (the decision packet sorts by this, in order):**
1. Hard gates pass (honest + grounded + correct-absence + voice-lint).
2. Voice and quality survive blind judging.
3. Latency improves enough to justify switching.
4. Operational complexity is acceptable.

*Don't crown the fastest brain — crown the fastest brain that is still Maez.*

## 6. Statistics — two-stage, tail-aware

- **Screening:** `k = 3` per probe per variant. Cheaply eliminates dishonest, broken, or obviously-slow variants.
- **Finalists:** `k = 7` (or `10`) per probe for the top 2–3 surviving variants. Report **p50, p90/p95, max, and variance**.
- **Tail risk is first-class:** a single wildly-slow run is **not** averaged away — it is reported as **tail risk**. Maez's lived feel is hurt by occasional ~20s stalls, so a variant with a good median but a bad tail is flagged, not smoothed.

## 7. Decision artifact — `BenchPacket` (content-free, advisory)

Per-variant: `{hard_gate: pass/fail + reasons, latency: {p50, p90, p95, max, variance, tail_flags}, tokens_per_sec, judge: {quality, voice}, quality_per_second}`, plus `fixture_manifest_hash`, the variant config hash, and a top-level recommendation string. **Metrics + verdicts + hashes only** — no probe/answer text in the persisted packet (the content-free telemetry discipline). Raw per-variant answers go to an **ephemeral, gitignored debug dump** for the judge audit / optional human tiebreak, never the committed packet. Schema-versioned (`bench_packet.v1`).

## 8. Covenant / honesty invariants

- **Hermetic + send-path-free:** no memory writes, no Telegram/surface, no external egress (only the localhost inference endpoint allowed). Asserted, not assumed ([[hermetic-sandbox-hardcoded-path-hazard]]).
- **Model-agnostic:** variants are config; the brain stays a swappable organ ([[brain-is-one-part-tool-calling-substrate-side]]).
- **Blind quality judging:** variant identity withheld from the judge; honesty axes deterministic so they can't be flattered.
- **Advisory, not authoritative:** the packet recommends; the owner decides the 2b re-run. Witness before claim ([[canon-governs-canon-witness-before-claim]]).
- **Honest-conservative metrics:** tail risk surfaced, not averaged; near-boundary cases scored toward the safe side.

## 9. Testing

The harness gets its own tests: sandbox isolation asserted (no real DB/egress reachable), localhost-only socket guard asserted, judge-blindness asserted (label withheld, shuffle), gate logic RED/GREEN (hard-fail beats fast; lexicographic ranking), content-free `BenchPacket` asserted, two-stage `k` honored, tail-flagging asserted, a negative-control (a deliberately dishonest stub variant must FAIL the hard gates), fixture_manifest_hash over real fixtures.

## 10. Review panel (~9 roles, by coverage not count)

Fires at scoping and post-implementation ([[two-team-switchboard-for-maez]], panel-size-is-risk-scaled): **inference/performance, model-quality, voice-continuity, citation/grounding, sandbox-isolation, statistics/gates, operational-deployment, covenant/body-coherence, future-Maez.** Codex runs its six-agent engineering pass (non-decorative) + 7+3; Claude cross-verifies every diff + runs suites independently + fires the coverage panel before merge flag-off.

## 11. Sequenced after

A passing variant → **RE-RUN the 2b runbook** with the A7 gate (the receipt now exists for the ack-time criterion). If no variant passes → the artifact is the evidence for whether GPU spend is justified, and which axis (honesty vs speed) is the blocker.
