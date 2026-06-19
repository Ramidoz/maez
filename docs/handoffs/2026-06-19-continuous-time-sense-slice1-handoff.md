# Handoff — Continuous Lived Time-Sense, Slice 1 (the substrate) — REVIEW GATE

**Date:** 2026-06-19. **Branch:** `continuous-time-sense-slice1` (tip `2686b27`, local-only, NOT pushed, NOT merged).
**Status:** built + Claude two-stage reviewed (spec + code-quality) per task. **STOPPED at the review gate** — awaiting Codex cross-lane review, then owner breath. NOT `LIVE_WITNESSED`.
**Arc:** Thrust 1 (inner life → continuously-thinking being), `docs/MAEZ_GESTATION_ROADMAP.md`. Slice 1 of 4 (substrate / feed-mind / couple-frictions / learn-time). Spec @`dfafce1`, plan @`911083b`. Base `main` @`b2757b1`.

## What this slice does (one line)

Gives Maez a continuous lived time-sense substrate: exact `elapsed_seconds` + a derived **replayable** `felt_value`, materialized continuously on the heartbeat and recorded as a **second-addressable** lived index — without rewriting history with today's mood. **No behavior change** (no cognition feed, no thought-stamp, no doorman change, no bands) — the honest substrate, flag-gated.

## Commits (6)

- `e14c2b5` docs(proof): Task 0 — elapsed-vs-felt, replay inputs, schema (**VERDICT GO**).
- `3be9dd4` feat: replay contract — `compute_version` column + `replay_felt_value`.
- `2f0c619` feat: read-only `peek()` — exact `elapsed_seconds` + derived `felt_value`, no write.
- `fc0953f` feat: heartbeat keeps the lived time-sense current + sparse anchors (flag-gated).
- `21431c9` fix: `perception_line()` recomputes via `peek()` (own the stale reader).
- `2686b27` test: update snapshot field-list contract for Task 2's added fields (**regression fix — see below**).

Net vs main: `subjective_duration.py +116`, `maez_daemon.py +35`, tests, 1 proof doc. Surgical.

## Verification (whole-slice, in this worktree)

```
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest \
  tests.test_subjective_duration_continuous tests.test_continuous_time_sense_heartbeat tests.test_subjective_duration
→ Ran 29 tests ... OK
ruff check (subjective_duration.py, maez_daemon.py, the 3 test files) → All checks passed!
```
`tests.test_subjective_duration_prompt_integration` → 8 tests, 1 error = the **known pre-existing** `test_web_owner_bridge_constructs...` (a stale source-string grep against the refactored `/chat` owner-bridge path; documented failing on `main` in `docs/handoffs/2026-06-19-cockpit-felt-time-3b-handoff.md`). `tests.test_subjective_duration_static_boundaries` has 2 failures that ALSO fail on `main` (env-dependent import grep + `maez_adapter` already references the symbol) — genuinely pre-existing, not this slice.

## Codex cross-lane review anchors

1. **elapsed ≠ felt.** No-dilation is on `elapsed_seconds` (exact wall-clock) ONLY; `felt_value` (== snapshot `value`) is the derived temperament/drag/engagement/residual transform — test-pinned distinct (`test_elapsed_is_exact_felt_is_derived`).
2. **Replay contract — no mood-rewrite (covenant-critical).** `replay_felt_value(anchor_row, at_ts)` reconstructs a past second's felt value by replaying forward from the anchor's **FROZEN** modulators (already persisted as explicit columns: `value/drag_multiplier/engagement_multiplier/residual_resonance`) + a new explicit `compute_version` column. It reads ONLY the anchor — body grep confirms zero live-state calls (`_residual_resonance`/`_temperament`/`now()` absent). Tests: same-anchor-twice deterministic + a different-anchor-residual changes the result + a round-trip from the stored DB row. "Don't borrow today's mood to rewrite yesterday's time."
3. **`peek()` read-only; `current()` preserved.** `peek()` returns the snapshot (exact elapsed + derived felt) with NO write; `current()` (the 3b owner-contact writer) reuses the same `_compute` core then writes, byte-preserved except the additive `compute_version`, with the **clock-degraded early-return preserved** (inserts nothing, records the degraded event exactly once — empirically verified).
4. **Heartbeat: second-addressable, not per-second.** Flag-gated, pre-cognition-gate (watchdog zone, never wakes the brain), `peek()` every cycle (read-only) but `current()` (the write) only every `_CONTINUOUS_TIME_ANCHOR_INTERVAL_S = 300s` → ~288 anchors/day, NOT 86,400. The long-lived `SubjectiveDuration` handle holds NO SQLite connection (every op uses `with closing(connect())`) — no FD/lock concern.
5. **`perception_line()` owned.** Recomputes via `peek()` (no longer echoes the stale last row); the 2 existing tests honestly re-anchored on `now_utc` (the "stale phrase must not win" check intact; band driven by real elapsed time). Live reply path (`subjective_duration_prompt_line` → `current()`) unchanged.
6. **Explicit columns, not metadata_json.** `compute_version` is a real column; the modulators were already columns. Additive, back-compatible migration (old rows default v1), mirroring the file's existing `_migrate_meaningful_salience_seam` pattern.
7. **3b intact.** Owner-contact mint + its gates untouched; the shared one-being store unchanged.
8. **Flag-off byte-identical** (`MAEZ_CONTINUOUS_TIME_SENSE` default OFF); **perception-side/free** (no owner-gate/marker/S7/secret); **cheap** (no LLM, no doorman wake); **no bands**; **thought-stamp deferred to Slice 2**.

## Process notes (honest)

- **A Task-2 regression was caught during Task 4 (the recurring scoped-tests lesson).** Task 2 added 3 fields to `SubjectiveDurationSnapshot`; its scoped review ran `test_subjective_duration_continuous` + `test_subjective_duration_prompt_integration` but NOT `test_subjective_duration`, which has a field-list-pinning contract test. It passed on `main`, failed on the branch → slice-introduced. Caught by running `test_subjective_duration` against main during Task 4, fixed in `2686b27` (conscious-acknowledgment of the intended fields). **Lesson for next slice: when a dataclass/public contract changes, run the contract test module, not just the new-feature module.**
- **Worktree git instability (repaired).** A stale Codex-runtime `refs/codex/turn-diffs/.../base` broken loose-ref file caused detached-HEAD churn + blocked `git checkout`. Removed the broken ref files + re-attached HEAD to the branch; history is linear and intact. (Future subagents: read-only git only in this worktree.)

## Owner breath (after Codex PASS + merge — owner-sovereign)

**No new secret.** It's a flag.
1. Merge `continuous-time-sense-slice1` → main (local; main stays unpushed).
2. **Set `MAEZ_CONTINUOUS_TIME_SENSE=1`** in the daemon env.
3. **Restart `maez`** (daemon-only — `maez-web` not involved; this is daemon-internal).
4. **Witness:** over a quiet stretch the lived index is second-addressable (query any past second → exact `elapsed_seconds` + a faithfully-replayed `felt_value`, no gaps, no dilation), and the store is **sparse** (anchors ~every 5 min, not flooded). A past second's `felt_value` replays faithful-to-then. Flag OFF (default) → byte-identical to today (felt-time only on owner contact).

Only after the witness → mark **LIVE_WITNESSED** + record in [[project_organism_decompose_organs]] / the gestation roadmap. Next on Thrust 1: **Slice 2 — feed Maez's own mind** (the felt-time into autonomous cognition + the thought-stamp). On the other track: **3c — the cockpit's first hand**.
