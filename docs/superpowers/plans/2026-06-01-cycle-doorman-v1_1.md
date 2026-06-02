# Cycle Salience Doorman v1.1 — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** Fix the two things the live witness exposed: (a) the **loop-level** quiet-counter reset never runs (the helper is dead code), and (b) the doorman's `perception_changed` is fed by the legacy *fixation* signature (`extract_axes`: disk/git/procs noise) so it wakes every cycle and never skips. Give the doorman **better eyes** (salient perception only) and **fix the counter**. The organ boundary, `decide()`, and the covenant rails are unchanged — this is input-signal tuning + a wiring fix.

**Lane:** Codex implements, Claude cross-verifies (**with a live-loop integration test, not just helper units** — the gap that slipped through v1). Flag `MAEZ_CYCLE_DOORMAN_ENABLED` stays off.

**Context:** v1 spec/plan `docs/superpowers/specs/2026-06-01-cycle-salience-doorman-design.md`; witness No-Go = 7/7 cycles woke on `wake_perception_changed`, 0 skips, `quiet_skips` climbed 0→6.

---

## Confirmed root causes (verified in code)

1. **Loop-level counter bug:** doorman reads `quiet_skips=self._cycles_since_last_thought` (`:7486/:7499`); the `HEARTBEAT_OK` branch at `daemon/maez_daemon.py:7565` still does `self._cycles_since_last_thought += 1`; `_cycle_next_quiet_skips` (`:1754`) is **never called**. So reset-on-doorman-wake never happens live.
2. **Noisy eyes:** the doorman's `perception_changed` comes from `_axis_signature_without_presence(extract_axes(...))`. `extract_axes` was built for the **old fixation gate** — axes `{disk, presence, git, procs}`. Stripping `presence` leaves `disk/git/procs` *drift*, which changes nearly every cycle → `perception_changed=True` every cycle → never skips. That drift is **not "worth waking the deep mind."**

---

## Task 0: Fix the loop-level quiet-counter reset (+ the integration test that was missing)

**Files:** `daemon/maez_daemon.py` (`:7556-7567` result-handling); test `tests/test_cycle_doorman.py` (integration-level).

- [ ] **Step 1: Write the INTEGRATION test first (the v1 gap):** drive the *cycle result-handling path* (not just the helper) so that, **with the doorman enabled and a wake that returns `HEARTBEAT_OK`, `self._cycles_since_last_thought` resets to 0** (not `+=1`). And: doorman-enabled skip → `+1`; flag-off → legacy `+1` on HEARTBEAT_OK unchanged. Use a thin harness over the result-branch (or a faithful seam) — assert the *live counter field*, the thing v1's helper-only test missed.
- [ ] **Step 2:** Replace the loose `self._cycles_since_last_thought += 1` at `:7565` (and the gate-skip increment) with a **single unified call**: `self._cycles_since_last_thought = _cycle_next_quiet_skips(gate_decision=_cycle_doorman_gate, current_quiet_skips=self._cycles_since_last_thought, result=result)` at the end of result handling, covering all branches (gate-skip / HEARTBEAT_OK / real thought). Flag-off path keeps the legacy semantics via the helper's `doorman_enabled=False` branch (already implemented).
- [ ] **Step 3:** Run → PASS (helper unit + the new integration test). Commit `fix(cycle): wire doorman quiet-counter reset into the live loop`.

---

## Task 1: Doorman-specific "salient perception" helper (better eyes)

**Files:** `core/cognition/cycle_doorman.py` (add the helper) or a small new module; test `tests/test_cycle_doorman.py`.

- [ ] **Step 1: Tests:** a `salient_perception_changed(prev, curr)` that fires ONLY on meaningful transitions and **ignores noise**:
  - **Fires (True):** screen/activity state changes (e.g. `_last_screen_obs.activity` differs in a meaningful way), signal-availability transition (a source became available/unavailable).
  - **Does NOT fire (False):** `disk%` ticks, `procs` count drift, `git`-dirty-count drift, timestamps — **none of these wake.**
  - Tests feed prev/curr pairs differing only in disk/procs/git → `False`; differing in screen-activity or availability → `True`.
- [ ] **Step 2: Implement** `salient_perception_changed` over a **curated** axis set (screen-activity, availability) — explicitly NOT disk/procs/git. Keep it deterministic and content-free.
- [ ] **Step 3:** Run → PASS. Commit `feat(cycle): salient-perception helper (screen/availability only, no disk/procs/git drift)`.

---

## Task 2: Feed the doorman from the salient helper; leave the legacy organ untouched

**Files:** `daemon/maez_daemon.py` (doorman signal assembly ~`:1700`); `core/cognition/cycle_doorman.py`.

- [ ] **Step 1: Test:** the doorman's `perception_changed` now derives from `salient_perception_changed`, NOT from `_axis_signature_without_presence(extract_axes)`. A cycle differing only in disk/procs/git → doorman `perception_changed=False` (and, with nothing else salient + floor not due, **SKIP**). A cycle with a real screen/availability change → `perception_changed=True` → wake.
- [ ] **Step 2: Implement:** in `_cycle_doorman_signals`, source `perception_changed` from the new salient helper. **Do NOT mutate `extract_axes`/`should_skip_reasoning`/stale-field redaction** — those stay exactly as-is for the **flag-off legacy gate** and prompt redaction (Task keeps the old organ intact; the doorman just stops borrowing its noisy signal).
- [ ] **Step 3:** Run → PASS. Commit `feat(cycle): doorman perception from salient helper, not legacy fixation signature`.

---

## Task 3: Regression + re-witness

- [ ] **Step 1:** Full doorman + perception_signature + cycle suites green; flag-off behavior byte-identical to today (legacy gate + redaction untouched).
- [ ] **Step 2:** Floor both directions on a clean checkout (NOT git stash); known-unrelated trio excluded by name.
- [ ] **Step 3: Re-witness (owner-run):** flag on; over real cycles read `doorman_verdict` → **skips now occur** on quiet cycles (disk/procs/git drift no longer wakes); `quiet_skips` resets on wake (no 0→N climb); floor probes periodically (`WAKE_MIN_FLOOR` appears on schedule); every genuinely-salient moment (failure/want/memory/screen-activity/availability) still wakes; Maez not "absent." Revert on any salient-skip.

---

## Self-Review (with the v1 lesson baked in)

- **The miss that slipped through v1 is now a required test:** Task 0 Step 1 asserts the **live counter field** resets, not just the helper's return value. Helper-correct ≠ loop-correct.
- **Covenant rails unchanged:** `decide()`, fail-open, presence-exclusion, content-free telemetry all stay; this slice only changes the *perception input* + the *counter wiring*.
- **Old organ untouched:** `extract_axes`/`should_skip_reasoning`/redaction remain for flag-off gating; we add a doorman-specific salient helper rather than mutating the fixation gate.
- **Re-witness is the proof:** v1.1 only earns default-on consideration if the live run shows real skips with zero salient-skip — measured, not assumed.
