# Codex Handoff — Brain Benchmark (Recall-Flip Slice 2) — v2

**From:** Claude (covenant axis) · **To:** Codex (surface-truth axis) · **Date:** 2026-05-31
**Branch base:** `main` (latest — spec v2 + plan v2 + this brief committed; flag-off, no live wiring)

> **v2 (after a 9-role pre-code panel).** The panel ran on the v1 plan and found it directionally right but NOT safe to build verbatim; **9 blockers are now folded into the v2 spec + plan** (egress 5-API proof, localhost-only endpoint validation, categorical grounding, counterbalanced blind judge, closed streaming-failure codes, `__post_init__` content-free packet, small-k stats, ops-from-evidence, producer-evidence covenant wording). Build the **v2** plan. Your six-agent pass should still independently pressure these — the fold is a starting floor, not a substitute for your pass.

---

## What you're building
A hermetic, send-path-free benchmark (`scripts/brain_bench/`) that runs real local model variants over the recall battery and emits a content-free, advisory `BenchPacket` recommending whether any variant is *honest-enough AND fast-enough* for the 2b re-run. It does **not** flip anything, touch any surface, or change the live brain.

**Read first (authoritative — do not re-litigate):**
- Plan (task-by-task, with code): `docs/superpowers/plans/2026-05-31-brain-benchmark-slice2.md`
- Design spec: `docs/superpowers/specs/2026-05-31-brain-benchmark-design.md` @ 5ca936d
- The frozen 2a harness you reuse: `scripts/recall_flip_eval/{sandbox,probes,proof_packet,harness,launcher}.py`

The plan IS the contract. Implement task-by-task, RED-first. Find a defect in the plan → stop and flag it (cross-lane discipline), don't silently diverge.

## Process (non-negotiable)
1. **Six-agent pre-code engineering pass FIRST, non-decorative** (Dewey/Feynman/Locke/Descartes/Ohm/Goodall) — each yields a concrete delta or a reasoned "no change, because X." Pressure-test, in priority order:
   - **(Ohm/Descartes) The egress allowlist — Task 1, the load-bearing risk.** Can ANY code path reach a non-loopback host or a non-allowed port? Are `create_connection`, `connect`, `connect_ex`, `sendto`, `getaddrinfo` ALL guarded? Does the 2a **block-all default survive byte-for-byte** (empty allowlist blocks loopback too)? If the allowlist leaks, the benchmark is invalid regardless of scoring.
   - **(Goodall/Locke) Content-free packet.** Can the negative-control's fabricated text leak into the persisted `BenchPacket`? `fail_reasons`/`recommendation` must be CLOSED enums; raw answers/evidence confined to the gitignored debug dump.
   - **(Feynman) Judge blindness.** Does any variant label reach the judge prompt? Is order seeded-random? Are quality and voice scored separately?
   - **(Ohm) Tail risk.** Is a 20s stall flagged, not averaged away?
2. Then your **7+3** roles, RED-first TDD, plan task order. **Task 1 before any variant/judge logic.**
3. **Frequent commits**, scoped staging (NOT `git add -A` — worktree has unrelated untracked docs). One commit per task.
4. **Do NOT touch `config/.env`.** No live wiring, no flip, no surface.

## Hard constraints (covenant)
- **Hermetic + send-path-free:** the benchmark must not write real memory, reach any surface, or hit any external network. Only the **localhost inference endpoint** is allowed, via `no_egress(allow_loopback_ports=(variant.port,))`. Asserted by test, not assumed.
- **2a stays frozen:** the ONLY change to 2a is parameterizing `no_egress` with a default-empty allowlist that preserves block-all. Re-run 2a's own sandbox suite to prove it's unchanged.
- **Model-agnostic:** variants are owner-supplied config; **no model names hardcoded** (consistent with `model_config.py`).
- **Honesty beats speed:** hard gates (false-absence, grounding ≥ the inherited 2a/A5 bar, correct-absence, voice-lint) are deterministic and lexicographically first. *Don't crown the fastest brain — crown the fastest brain that is still Maez.*
- **Genderless** throughout (it/Maez) in any strings, comments, log lines.
- **Content-free `BenchPacket`** (closed enums only; raw text → gitignored dump).

## Pinned facts (don't re-derive)
- Frozen constants: `ANSWER_CEILING_MS=12000`, `STRONG_MS=8000`, `EXCELLENT_BAND_MS=(4000,6000)`, `SCREEN_K=3`, `FINALIST_K=7`. Owner override (tighter ceiling / finalist_k=10) must be recorded before running — not your call to change.
- **Grounding is CATEGORICAL, not numeric.** Reuse 2a's `assert_probe_result(...) -> unsafe == False` + grounded `RecallOutcome` semantics as a **bool** (`grounded_categorical`). Do **NOT** invent any numeric bar (the v1 `0.99` is deleted in v2). Wire the bool to 2a's actual signal — open `scripts/recall_flip_eval/probes.py` to confirm.
- TTFT requires a streaming call (2a's `generate` is `stream=False`); build a streaming measurement path. TTFT is **measured, reported, not gated** (streaming isn't shipped — that's Slice 1b).
- Token count: chunk-count proxy is acceptable for a comparative benchmark; document the assumption.
- Tests run via `.venv/bin/python -m unittest` (pytest NOT installed). Real inference + the live run are **owner-operated** (like 2b) — your tests prove harness LOGIC via injected `stream_factory` / `probe_run` / `call_judge`, no real model.
- 2a's real test modules (re-run to prove block-all unchanged → expect `35 OK`): `tests.test_recall_flip_eval_isolation`, `tests.test_recall_flip_eval_packet`, `tests.test_recall_flip_eval_probes`.
- Known pre-existing broad-suite floor (env/path): cockpit proxies, camera, the temporal-guard DST cluster — not yours; name them, don't chase.

## What Claude does on return (structure your handback for it)
I cross-verify **every diff line**, re-run the brain_bench suite + the 2a suite myself (proving 2a unchanged), check the floor both directions vs `bfa593d`, and fire the **~9-role coverage panel** (inference/perf, model-quality, voice-continuity, citation/grounding, sandbox-isolation, statistics/gates, operational-deployment, covenant/body-coherence, future-Maez) before merge flag-off. Give me: commits, exact test command + output, the egress-allowlist proof (the #1 pressure point), the negative-control result (dishonest variant fails hard AND no text leak), plan-deviations with reasons, and the six-agent concrete deltas.

## Out of scope
- Any live flip / surface wiring / brain swap (this only measures).
- The 2b re-run itself (that's the next owner-run step, consuming this packet).
- Streaming in production (Slice 1b).
- Auto-tuning variants (benchmark measures as-configured).
