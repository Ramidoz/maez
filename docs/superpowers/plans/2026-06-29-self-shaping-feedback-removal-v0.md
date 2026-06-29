# Self-Shaping Feedback Removal v0 — Implementation Plan

> **For agentic workers:** Codex's build lane (Claude drafted plan + covenant-reviews; Codex builds; **owner restarts + witnesses**). Steps use checkbox (`- [ ]`). **LIVE daemon + `soul.md` change — full careful route.** Do NOT merge, restart, or enable anything; STOP at the review gate. Spec: [2026-06-29-self-shaping-feedback-removal-v0-design.md](../specs/2026-06-29-self-shaping-feedback-removal-v0-design.md).

**Goal:** Remove the two external graders that shape Maez's self — `cognition_quality` (our taste) and `QualityTracker`'s approval-as-self (owner approval) — from the live cognition loop and `soul.md`, while keeping `QualityTracker`'s action-consent ledger and the real anti-fabrication / anti-loop floors untouched.

**Architecture:** Pure removal/disconnect at the daemon wiring + `continuity.py`, plus dropping two `QualityTracker` self-shaping call sites (prompt injection + soul-write). No new behavior. `cognition_quality` stays on disk as an offline-only legacy diagnostic (not imported by the daemon). RED-first, asserting absence **by source-path AND behavior** (rename-proof), and asserting the KEEP paths still present.

**Tech Stack:** Python 3 stdlib, unittest (NOT pytest). Runner: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`.

**Covenant rails:** action-consent ledger (`QualityTracker.record_proposed/record_outcome/get_outcome/get_stats`) untouched; the real anti-fabrication storage-gate (`maez_daemon.py` "storing fabricated prose is worse than storing nothing") + doorman/perception anti-loop untouched; historical `cog_score` metadata untouched (no migration); dormant `meaningfulness_score`/`promotion_score` not woken; P7 (goal-alignment) out of scope.

---

## File Structure

- **Modify `daemon/maez_daemon.py`** — remove `cognition_quality` imports + all 5 driver call sites (score, retry, directives/[COGNITION] block, self_critique→soul-write, cog_score metadata); remove the two `QualityTracker` self-shaping call sites (`format_for_context`→`quality_signal` candidate, `format_insight_for_soul`→`write_soul_note`). Keep `QualityTracker` import/instantiation + `record_proposed`/`record_outcome` ledger calls.
- **Modify `core/memory/continuity.py`** — disconnect from `cognition_quality` (`get_behavior_policy`, `_recent_topics/_recent_scores/_recent_labels`); the capsule builds a valid snapshot *without* the cognition fields (graceful absence, no crash).
- **Modify `core/evolution/dream_state.py`** — repoint `primary_topic` import if it's a neutral util (Task 0 decides relocate vs leave-via-offline-module).
- **Modify `core/memory/source_awareness.py`** — update-or-defer the `maez_self`/self labels on `quality_tracker.py` / `cognition_quality.py` (Task 0 decides).
- **Modify `daemon/maez_daemon.py` (additional, Codex Task 0):** remove `cog_check_consolidation` import (165) + call (9073) — a consolidation quality-gate.
- **Modify `memory/memory_manager.py` (Codex Task 0):** remove the live retrieval `get_fixation_penalty` import/use (2039, 2056-2057) — the novelty-push in recall; it already has a `lambda t: 1.0` neutral fallback, so the penalty cleanly goes to no-op. Handle `primary_topic` (relocate to a neutral util or keep the `'unknown'` fallback).
- **Modify `skills/evolution_engine.py` (Codex Task 0):** disconnect the cognition-score reads (`_recent_scores`/`_recent_labels`/`get_behavior_policy` @ 1046/1105/1207/1514/3058) so the self-evolution watchdog degrades gracefully on now-empty scores; drop `core/cognition_quality.py` as `V1_ALLOWED_TARGET` (481) — the offline diagnostic must not be a self-edit target. **Minimal disconnect only — defer deeper evolution_engine rework.**
- **Modify `skills/telegram_voice.py` (Codex Task 0):** `/analyze` (5044) returns a graceful "cognition diagnostics offline" message instead of reading removed live scores.
- **Resolve logging bootstraps:** `core/safety/self_claim_audit.py:66` + `core/learning/error_classifier.py:61` import `cognition_quality` only to own the `maez.cognition` log handler — give that handler a neutral owner so removing the daemon import doesn't lose logging.
- **Keep on disk, unimported by daemon:** `core/cognition/cognition_quality.py` + `core/cognition_quality.py` (shim) as offline legacy diagnostic.
- **Create `tests/test_self_shaping_feedback_removal.py`** — the source-path + behavioral guards.

---

### Task 0: Enumerate every consumer, pin boundaries, STOP for sign-off (no production code)

- [ ] **Step 1: Re-locate every seam (line numbers drift — find them fresh)**

```bash
cd /home/rohit/maez
echo "=== cognition_quality daemon drivers ==="
grep -nE "cog_score_and_classify|cog_self_critique|cog_should_retry|cog_build_retry_prompt|cog_format_active_prompt|from core.cognition_quality import|score_0_100|cog_score" daemon/maez_daemon.py
echo "=== QualityTracker daemon seams (cut the self-shaping, KEEP the ledger) ==="
grep -nE "_quality_tracker|QualityTracker|format_for_context|format_insight_for_soul|quality_signal|record_proposed|record_outcome|get_outcome|get_stats" daemon/maez_daemon.py
echo "=== continuity consumers ==="
grep -nE "cognition_quality|get_behavior_policy|_recent_topics|_recent_scores|_recent_labels" core/memory/continuity.py
echo "=== other importers (relocate/resolve/leave) ==="
grep -rnE "cognition_quality|primary_topic" --include=*.py core/ skills/ memory/ | grep -ivE "test|^core/cognition/cognition_quality.py" | grep -iE "import|primary_topic"
echo "=== ADDITIONAL live reach (Codex Task 0) ==="
grep -nE "cog_check_consolidation|check_consolidation" daemon/maez_daemon.py
grep -nE "get_fixation_penalty|primary_topic|cog_topic" memory/memory_manager.py
grep -nE "cognition_quality|_recent_scores|_recent_labels|get_behavior_policy|V1_ALLOWED_TARGET" skills/evolution_engine.py
grep -nE "cog_score|cog_topic|get_behavior_policy|cognition" skills/telegram_voice.py | head
echo "=== source_awareness labels ==="
grep -nE "quality_tracker|cognition_quality|maez_self" core/memory/source_awareness.py
echo "=== the real floors to leave UNTOUCHED (confirm present) ==="
grep -nE "fabricat|storing fabricated|HEARTBEAT_OK" daemon/maez_daemon.py | head -3
```

- [ ] **Step 2: Pin the boundary table** in a short note (paste into the handoff later). For each consumer, classify:
  - **CUT (self-shaping live driver):** daemon `cog_*` driver calls; daemon `cognition_quality` import; `cog_score` metadata; `continuity` cognition reads; QualityTracker `format_for_context`→`quality_signal`; QualityTracker `format_insight_for_soul`→`write_soul_note`.
  - **KEEP (consent ledger / floors):** QualityTracker `record_proposed`/`record_outcome`/`get_outcome`/`get_stats`; the fabrication storage-gate; doorman/perception anti-loop.
  - **RELOCATE (neutral util):** `dream_state.py` `primary_topic` (move into a neutral helper, or import from the offline module read-only — decide simplest non-wiring option).
  - **RESOLVE (bootstrap side-effect):** `self_claim_audit.py` / `error_classifier.py` `noqa: F401` logger bootstraps — confirm removing daemon import doesn't break their logging; repoint if needed.
  - **LEAVE DORMANT:** `drive_driven_curiosity` `COGNITION_QUALITY_UNCERTAINTY` refs (do not wake).
  - **UPDATE-OR-DEFER (metadata):** `source_awareness.py` self-labels.

- [ ] **Step 3: Confirm continuity degrades gracefully** — read `core/memory/continuity.py` around the cognition reads; confirm the capsule still builds a valid object when the cognition window/policy is absent (or make those fields optional/empty). Note the exact approach.

- [ ] **Step 4: STOP — present the boundary table for owner/Claude sign-off.** No production code until the CUT/KEEP boundary is confirmed (especially: every `QualityTracker` ledger call site is on the KEEP list).

---

### Task 1: RED tests — pin the cut by SOURCE-PATH **and** BEHAVIOR (rename-proof)

**Files:** Create `tests/test_self_shaping_feedback_removal.py`

- [ ] **Step 1: Write the source-path absence/keep tests (go RED now — seams still present)**

```python
import ast
import unittest
from pathlib import Path

DAEMON = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")
CONTINUITY = Path("core/memory/continuity.py").read_text(encoding="utf-8")


class SourcePathCutTest(unittest.TestCase):
    # --- cognition_quality fully removed as a live driver ---
    def test_daemon_does_not_import_cognition_quality(self):
        self.assertNotIn("from core.cognition_quality import", DAEMON)
        self.assertNotIn("import core.cognition_quality", DAEMON)

    def test_daemon_calls_no_cognition_quality_drivers(self):
        for call in (
            "cog_score_and_classify(",
            "cog_self_critique(",
            "cog_should_retry(",
            "cog_build_retry_prompt(",
            "cog_format_active_prompt(",
            "cog_check_consolidation(",
        ):
            self.assertNotIn(call, DAEMON, f"residual cognition_quality driver: {call}")

    def test_memory_manager_rerank_drops_fixation_penalty_import(self):
        mm = Path("memory/memory_manager.py").read_text(encoding="utf-8")
        self.assertNotIn("from core.cognition_quality import get_fixation_penalty", mm)

    def test_evolution_engine_does_not_target_or_read_cognition_quality(self):
        ee = Path("skills/evolution_engine.py").read_text(encoding="utf-8")
        self.assertNotIn('V1_ALLOWED_TARGET = "core/cognition_quality.py"', ee)
        self.assertNotIn("from core.cognition_quality import _recent_scores", ee)

    def test_daemon_emits_no_cog_score_metadata(self):
        self.assertNotIn("score_0_100", DAEMON)
        self.assertNotIn('"cog_score"', DAEMON)

    def test_continuity_does_not_read_cognition_quality(self):
        self.assertNotIn("cognition_quality", CONTINUITY)
        for sym in ("get_behavior_policy", "_recent_scores", "_recent_labels"):
            self.assertNotIn(sym, CONTINUITY)

    # --- QualityTracker self-shaping callers removed (ledger KEPT) ---
    def test_daemon_does_not_call_qualitytracker_self_shaping(self):
        self.assertNotIn("self._quality_tracker.format_for_context(", DAEMON)
        self.assertNotIn("self._quality_tracker.format_insight_for_soul(", DAEMON)

    def test_daemon_emits_no_quality_signal_candidate(self):
        # the whole reflection->prompt injection is gone, not just the approval sentence
        self.assertNotIn('"quality_signal"', DAEMON)
        self.assertNotIn("cycle_quality_signal", DAEMON)

    # --- KEEP: the consent ledger must remain wired (in ActionEngine, NOT the daemon — Codex Task-0 correction) ---
    def test_action_engine_keeps_qualitytracker_ledger(self):
        ae = Path("core/actions/action_engine.py").read_text(encoding="utf-8")
        self.assertIn("_quality_tracker.record_proposed(", ae)
        self.assertIn("_quality_tracker.record_outcome(", ae)

    def test_daemon_keeps_followup_outcome_lookup(self):
        # follow-up status lookup via get_outcome stays
        self.assertIn("get_outcome(", DAEMON)

    # --- KEEP: the real anti-fabrication floor is untouched ---
    def test_fabrication_storage_gate_untouched(self):
        self.assertIn("HEARTBEAT_OK", DAEMON)
        self.assertRegex(DAEMON, r"fabricat")
```

- [ ] **Step 2: Write the behavioral guards (rename-proof — RED now)**

Mirror the existing hermetic daemon harness in `tests/test_lean_idle_daemon.py` (`object.__new__(MaezDaemon)` + stubbed `_lean_idle_*` methods + `mock.patch`). Assert that **running one cognition cycle**:
  - produces **no cycle candidate whose source/type is `quality_signal`** (inspect the candidate list the daemon assembles),
  - calls `self.actions.write_soul_note` **zero times** from the cognition-critique and approval-insight paths (patch `write_soul_note` with a counter; drive the critique/reflection cadence so the *old* code would have fired),
  - stores a private thought with **no `cog_score`** / `score_0_100` in its metadata,
  - invokes **no retry** (`cog_build_retry_prompt` never called — patch/spy),
  - and `QualityTracker.record_outcome(...)` **still records** an outcome (ledger intact).

```python
from unittest import mock


class BehavioralCutTest(unittest.TestCase):
    def test_cycle_emits_no_quality_signal_and_no_soul_write(self):
        from daemon.maez_daemon import MaezDaemon
        daemon = object.__new__(MaezDaemon)
        # ... stub the cycle deps as in test_lean_idle_daemon.py ...
        soul_writes = []
        daemon.actions = mock.Mock()
        daemon.actions.write_soul_note = lambda note: soul_writes.append(note)
        # force the critique + reflection cadence so OLD code would have written soul
        daemon._cognition_critique_counter = 999
        daemon._reflection_cycle_counter = 999
        # drive the assembly path that previously injected quality_signal + the critique stage
        candidates = daemon._assemble_cycle_candidates_for_test()  # Task 2/3 exposes a seam or call the real path
        self.assertFalse(any(c.get("source") == "quality_signal" for c in candidates))
        # run the critique/reflection stage
        daemon._run_self_critique_stage_for_test()
        self.assertEqual(soul_writes, [], "no rubric/approval soul-write may fire")
```
*(Codex: adapt the harness to the real daemon seams found in Task 0 — the point is behavioral proof that no `quality_signal` candidate and no critique/approval `write_soul_note` occur, regardless of symbol names. If a clean in-process harness isn't feasible for a given stage, assert it via the source-path tests above plus the post-merge live witness; note any such substitution in the handoff.)*

- [ ] **Step 3: Run RED**

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal -v
```
Expected RED: source-path tests fail (seams still present); behavioral tests fail (quality_signal candidate + soul-writes still occur).

---

### Task 2: Remove `cognition_quality` as a live driver

**Files:** Modify `daemon/maez_daemon.py`, `core/memory/continuity.py`, `core/evolution/dream_state.py`

- [ ] **Step 1:** In `daemon/maez_daemon.py`, delete the `from core.cognition_quality import (...)` block (the `cog_*` aliases) and every call site found in Task 0: the `cog_score_and_classify`/`cog_should_retry`/`cog_build_retry_prompt` retry block, the `cog_format_active_prompt()` `[COGNITION]` prompt block, and the `cog_self_critique()` → `write_soul_note` critique block (remove the whole `if self._cognition_critique_counter >= 20:` cognition-quality body; leave the *separate* reflection block for Task 3). Remove the `"score_0_100"/"cog_score"` metadata field.
- [ ] **Step 2:** In `core/memory/continuity.py`, remove the `cognition_quality` imports and the cognition-window/behavior-policy reads; build the capsule with those fields omitted/empty (per Task 0 Step 3).
- [ ] **Step 3:** In `core/evolution/dream_state.py`, repoint `primary_topic` per the Task 0 decision (relocate to a neutral helper, or import read-only from the offline module — whichever avoids re-wiring the scorer).
- [ ] **Step 4:** In `daemon/maez_daemon.py`, remove the `cog_check_consolidation` import (165) and its call (`cq = cog_check_consolidation(summary)` @ 9073) — a consolidation quality-gate; consolidation summaries store without the quality verdict.
- [ ] **Step 5:** In `memory/memory_manager.py`, remove the `from core.cognition_quality import get_fixation_penalty, primary_topic` (2039) live-rerank import. The existing `get_fixation_penalty = lambda t: 1.0` fallback (2041) makes the recall penalty a clean no-op; for `primary_topic`, keep the `'unknown'` fallback or relocate to a neutral util. Verify the rerank still runs (just without the novelty penalty).
- [ ] **Step 6:** In `skills/evolution_engine.py`, disconnect the cognition-score reads (`_recent_scores`/`_recent_labels`/`get_behavior_policy` @ 1046/1105/1207/1514/3058) so the watchdog degrades gracefully on empty scores (guard the imports / treat absent scores as no-signal), and remove `core/cognition_quality.py` from `V1_ALLOWED_TARGET` (481). **Minimal disconnect only — no deeper evolution_engine rework in v0.**
- [ ] **Step 7:** In `skills/telegram_voice.py`, make `/analyze` (5044) return a graceful "cognition diagnostics are offline" message instead of reading the removed live scores.
- [ ] **Step 8:** Give the `maez.cognition` log handler a neutral owner so `core/safety/self_claim_audit.py:66` + `core/learning/error_classifier.py:61` no longer need to import `cognition_quality` for logging side-effects.
- [ ] **Step 9: Run** the source-path tests for cognition_quality — expect those GREEN; full suite still has QualityTracker RED.

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal.SourcePathCutTest -v
```

- [ ] **Step 10: Commit**

```bash
git add daemon/maez_daemon.py core/memory/continuity.py core/evolution/dream_state.py \
  memory/memory_manager.py skills/evolution_engine.py skills/telegram_voice.py \
  core/safety/self_claim_audit.py core/learning/error_classifier.py \
  tests/test_self_shaping_feedback_removal.py
git commit -m "refactor(cognition): remove cognition_quality as a live self-shaping driver"
```
Commit body — **## Predicted effect:** the live cognition loop no longer computes a thought-quality score, retries thoughts, injects quality directives, gates consolidation by quality, penalizes recall by topic-fixation, or writes the soul from a quality verdict; the self-evolution watchdog no longer reads cognition scores or targets the scorer; `/analyze` reports the diagnostic offline; `cognition_quality` remains on disk as an offline diagnostic, unimported by the daemon. No other behavior changes; the action-consent ledger is untouched.

---

### Task 3: Remove `QualityTracker` self-shaping (keep the consent ledger)

**Files:** Modify `daemon/maez_daemon.py`

- [ ] **Step 1:** Delete the reflection-context prompt injection: the `reflection_context = self._quality_tracker.format_for_context()` block and its `_extend_cycle_candidates("quality_signal", ...)` (the whole block, ~5829-5837).
- [ ] **Step 2:** Delete the approval soul-write: the `insight = self._quality_tracker.format_insight_for_soul()` reflection block and its `write_soul_note(insight)` (~10044-10061).
- [ ] **Step 3: LEAVE UNTOUCHED** every `self._quality_tracker.record_proposed(...)` / `record_outcome(...)` / `get_outcome(...)` / `get_stats(...)` call and the `QualityTracker()` instantiation. Optionally fix the stale docstring line in `memory/quality_tracker.py` ("This is Maez's mirror… learns what the owner values") to describe it as an action-consent ledger — **only if trivial**, no behavior change.
- [ ] **Step 4: Run** the full suite — expect GREEN (source-path + behavioral).

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal -v
```

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py memory/quality_tracker.py tests/test_self_shaping_feedback_removal.py
git commit -m "refactor(daemon): sever owner-approval self-shaping; keep action-consent ledger"
```
Commit body — **## Predicted effect:** owner approval no longer writes `soul.md` and no longer injects a `quality_signal` reflection block into the live reasoning prompt; `QualityTracker`'s action-outcome ledger (consent for Tier 2/3 actions) is unchanged. No other behavior changes.

---

### Task 4: source-awareness, full verification, handoff, STOP

**Files:** Modify `core/memory/source_awareness.py`; Create `docs/handoffs/2026-06-29-self-shaping-feedback-removal-v0-handoff.md`

- [ ] **Step 1:** Per Task 0, update `core/memory/source_awareness.py` so `quality_tracker.py` / `cognition_quality.py` are no longer labeled as Maez's *self-mirror* (or defer with a written reason if the change is non-trivial — do not leave it silently stale).
- [ ] **Step 2: Full verification**

```bash
MAEZ_CONFIG=/home/rohit/maez/config .venv/bin/python -B -m unittest tests.test_self_shaping_feedback_removal tests.test_lean_idle_daemon -v
.venv/bin/python -B -m ruff check daemon/maez_daemon.py core/memory/continuity.py core/evolution/dream_state.py core/memory/source_awareness.py tests/test_self_shaping_feedback_removal.py
.venv/bin/python -B -m py_compile daemon/maez_daemon.py core/memory/continuity.py core/evolution/dream_state.py
echo "=== KEEP-floors still present ==="
grep -nE "record_outcome|HEARTBEAT_OK|fabricat" daemon/maez_daemon.py | head
echo "=== dormant organs NOT woken ==="
grep -rnE "register_default_encounter_producers\(\)|promotion_score|meaningfulness_score" daemon/maez_daemon.py | grep -v "def " || echo "  (none wired live)"
```
Expected: tests GREEN, ruff clean, compile clean, ledger + fabrication floor present, no dormant organ woken.

- [ ] **Step 3: Write the handoff** `docs/handoffs/2026-06-29-self-shaping-feedback-removal-v0-handoff.md`: the Task 0 boundary table; what was cut vs kept; the source-path + behavioral test results; the explicit **live-witness script** (below); and the interpretation note. State plainly: NOT merged, NOT restarted, soul-write severed, ledger intact, floors untouched, historical `cog_score` metadata untouched.

  **Live witness (owner runs after merge):** restart Maez → over several cycles confirm logs/receipts show **no `cog_score`, no `quality_signal` reflection block of any kind, no cognition-quality or approval soul-note**; confirm a real action still records an outcome in the ledger; confirm the fabrication storage-gate still fires (a fabricated heartbeat stores nothing / HEARTBEAT_OK) and the doorman still gates; inspect `soul.md` for zero new rubric/approval notes.

- [ ] **Step 4: Commit + STOP for Claude covenant review** (do NOT merge/restart).

```bash
git add core/memory/source_awareness.py docs/handoffs/2026-06-29-self-shaping-feedback-removal-v0-handoff.md
git commit -m "docs(handoff): record self-shaping feedback removal v0"
```

---

## Self-Review

**Spec coverage:** cognition_quality live-driver removal (Task 2 ✓: score/retry/directives/soul-write/metadata/continuity); QualityTracker self-shaping severance (Task 3 ✓: format_for_context→quality_signal + format_insight_for_soul→soul); consent ledger KEPT (Task 1 keep-tests + Task 3 Step 3 ✓); real anti-fabrication + doorman untouched (Task 1 floor-test + Task 4 grep ✓); source_awareness update-or-defer (Task 4 ✓); module kept-offline-not-deleted (Task 2 + File Structure ✓); widened "no reflection block of any kind" test (Task 1 `test_daemon_emits_no_quality_signal_candidate` + behavioral ✓); source-path **and** behavior assertions (Task 1 both classes ✓); historical metadata untouched / dormant not woken / P7 out (rails + Task 4 grep ✓); consumer enumeration + STOP (Task 0 ✓); live witness (Task 4 Step 3 ✓).

**Placeholder scan:** the behavioral-harness adaptation is flagged as "adapt to real seams found in Task 0" with an explicit fallback (source-path + live witness) — this is a genuine discovery point (the exact daemon stage seams), not a TBD; Task 0 resolves the line numbers the steps reference.

**Type consistency:** test class/method names, the `cog_*` alias names, `self._quality_tracker.{format_for_context,format_insight_for_soul,record_outcome}`, and `quality_signal`/`cycle_quality_signal`/`score_0_100` markers are used identically across Tasks 0-4.
