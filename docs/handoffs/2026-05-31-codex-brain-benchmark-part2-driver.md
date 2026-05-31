# Codex Handoff — Brain Benchmark Slice 2 Part 2 (the Battery Driver)

**From:** Claude · **To:** Codex · **Date:** 2026-05-31
**Branch base:** `main` @ 28c25dd (Slice 2 part-1 core merged, production-inert).

## What you're building
Make the verified core *run*. Part 1 (the sealed test track) is merged; part 2 is the race runner: a real `probe_run`, the two-stage k=3/k=7 loop, tail-flagging, a CLI — plus two foundation cleanups. **Until this ships, no benchmark evidence is real and the 2b re-run stays blocked.**

**Read first:** plan `docs/superpowers/plans/2026-05-31-brain-benchmark-slice2-part2-driver.md` (the contract); spec `docs/superpowers/specs/2026-05-31-brain-benchmark-design.md` (v3.1); the merged core in `scripts/brain_bench/`.

## Process
- **Six-agent pre-code pass first** (non-decorative). Pressure, in order: (1) does `probe_run` drive the **production `focused_synthesize`** (mirror `scripts/recall_flip_eval/harness.py:139`), not a lookalike, with grounding = 2a's **categorical bool** (`assert_probe_result → unsafe==False`), never re-derived/numeric; (2) **two-stage isolation** — finalists re-run under the same sandbox/egress, screened-out variants can't leak into the finalist set; (3) tail vs over-ceiling stay **distinct**; (4) **fail-closed CLI** — missing/empty config errors, never falls back to `model_config`/the live model.
- Then 7+3, RED-first, plan task order. Scoped commits (NOT `git add -A`).
- **No flip, no surface, no live run.** The real benchmark is owner-operated; you make it runnable, not run it.

## Hard constraints
- **2a frozen** — reuse its seeders/asserts (`seed_dated_memory`, `harness._seed_for_probe`, `probes.assert_probe_result`), don't mutate them.
- **Hermetic** — real `probe_run` runs under `no_egress(allow_loopback_ports=(variant.port,))`; judging under the judge port only; never both open.
- **Grounding categorical** — 2a's bool, not a float. **Model-agnostic, genderless.**
- **Cleanups:** delete the vestigial `judge_pairwise(seed=...)` param (full counterbalancing supersedes it); widen `voice_lint`'s cognition regex to the canonical `think|thinking|ponder|consider|wonder|mull|reflect|feel|sense`.

## Handback shape (for Claude's cross-verify + 9-role panel)
Commits; exact test output (brain_bench + 2a both green); the `probe_run`→real-`focused_synthesize` proof; two-stage isolation proof; fail-closed-CLI proof; six-agent concrete deltas; any deviations disclosed. I re-run both suites myself, check the floor, and fire the coverage panel before merge.

## Out of scope
The real owner-run benchmark (owner's hand), the 2b re-run (consumes the packet later), streaming-in-prod (Slice 1b), the interference organ (banked).
