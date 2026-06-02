# Sleep-Consolidation Wiring v0 — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Steps use `- [ ]`.

**Goal:** Wake the dormant consolidation organs safely — fix the dream idle-gate, wire reflection synthesis flag-first with a dry-run witness, add content-free consolidation telemetry. No new inputs; growth-signals + daily→core deferred.

**Lane:** Codex implements, Claude cross-verifies (special attention: the content-free vs contentful-witness separation, the asymmetric idle rule, fail-safe). All new behavior flag-off / dry-run by default.

**Spec:** `docs/superpowers/specs/2026-06-02-sleep-consolidation-wiring-v0-design.md`

---

## Task 0: Probe — model/endpoint + flag posture (resolve the unknowns first)

**Read-only / diagnostic; no behavior change.**

- [ ] **Step 1 — `gemma4:26b` reality.** Confirm what the 3 AM consolidation *actually* runs on: trace `memory/memory_manager.py:333` `_llm_client.chat(model="gemma4:26b")` through `core/llm_client.chat` backend dispatch (`MAEZ_LLM_BACKEND`). Verify: no ollama on :11434, no gemma GGUF; the `llamacpp` backend hits :8080 (Qwen) and **ignores the requested model name**. Send one probe call through the exact consolidation path with `model="gemma4:26b"` and read the served model (`/props` `model_path`) + whether it succeeds. **Record the finding:** is consolidation silently running on Qwen with a dead label, or failing? (Expected: running on Qwen.) Do NOT fix the label yet — Task 3 telemetry will report the *actual* served model so the mismatch is visible; the label fix is a one-liner that lands with telemetry.
- [ ] **Step 2 — activity-idle signal inventory.** Find the most *provable* "last owner interaction" timestamp: `_rohit_active_until` (`:2120`, hint-only), the Telegram surface's last-message timestamp (surface-v2), UI/cockpit activity. Document which is reliable enough to *positively establish* a ≥30 min no-interaction window. If none is reliable, T1 adds a minimal last-interaction tracker (set on any owner message/UI event). The asymmetric rule requires *proving* idle, so this signal must be trustworthy.
- [ ] **Step 3 — flag posture.** Confirm there is no existing reflection-synthesis flag; the new flag is `MAEZ_REFLECTION_SYNTHESIS_ENABLED` with a sub-mode `MAEZ_REFLECTION_SYNTHESIS_WRITE` (default off→dry-run). Dream has no flag (it's a bug-fix, gated by its existing cooldown + owner-proposal model). Record the posture table.
- [ ] **Step 4:** Write findings to the slice notes. No commit (diagnostic) unless a probe script is worth keeping in `tools/probes/`.

---

## Task 1: Fix the dream idle-gate (hybrid, activity-primary, asymmetric uncertain)

**Files:** `core/evolution/dream_state.py` (`is_idle`), `daemon/maez_daemon.py` (`:8061`); Test `tests/test_dream_idle_gate.py`.

- [ ] **Step 1 — tests (the asymmetric rule, exhaustive):**

```python
# tests/test_dream_idle_gate.py
# dream_may_run(now, last_interaction_ts, active_until, camera) per spec §2:
#   requires no_owner_interaction >= 1800; fresh camera-present BLOCKS;
#   activity-uncertainty BLOCKS; camera-uncertainty does NOT block.
import unittest
from core.evolution.dream_state import dream_may_run  # new pure helper

class DreamIdleTest(unittest.TestCase):
    def test_idle_proven_camera_unavailable_fires(self):
        # 40 min no interaction, camera unavailable -> fires (camera uncertainty doesn't block)
        self.assertTrue(dream_may_run(no_interaction_secs=2400, camera="unavailable", active_until_future=False, activity_known=True))
    def test_fresh_camera_present_blocks(self):
        self.assertFalse(dream_may_run(no_interaction_secs=2400, camera="present_fresh", active_until_future=False, activity_known=True))
    def test_fresh_activity_hint_blocks(self):
        self.assertFalse(dream_may_run(no_interaction_secs=10, camera="absent", active_until_future=True, activity_known=True))
    def test_activity_uncertainty_blocks(self):
        # can't prove the no-interaction window -> DON'T fire
        self.assertFalse(dream_may_run(no_interaction_secs=2400, camera="absent", active_until_future=False, activity_known=False))
    def test_below_threshold_does_not_fire(self):
        self.assertFalse(dream_may_run(no_interaction_secs=600, camera="absent", active_until_future=False, activity_known=True))
    def test_camera_absent_with_proven_idle_fires(self):
        self.assertTrue(dream_may_run(no_interaction_secs=2400, camera="absent", active_until_future=False, activity_known=True))
```

- [ ] **Step 2:** Run → FAIL (helper absent).
- [ ] **Step 3 — implement** a pure `dream_may_run(...)` in `dream_state.py` encoding §2 exactly: `activity_known AND no_interaction_secs >= IDLE_THRESHOLD_S AND not (camera == "present_fresh") AND not active_until_future`. Activity uncertainty (`activity_known=False`) → False. Camera uncertainty (anything but `present_fresh`) → does not block. Keep `is_idle` for back-compat or route it through the new helper.
- [ ] **Step 4 — wire the daemon (`:8061`):** replace `self.dream.is_idle(None, 0.0)` with the real inputs — compute `no_interaction_secs` from the T0 activity signal, pass camera freshness from `_last_presence_snap`, pass the `_rohit_active_until` hint. Keep `should_run_now` cooldown + the owner-proposal gate untouched.
- [ ] **Step 5:** Run → PASS. Commit `fix(dream): hybrid activity-primary idle gate (asymmetric uncertain)`.

---

## Task 2: Wire reflection synthesis (flag-first, dry-run → local witness artifact)

**Files:** `daemon/maez_daemon.py` (nightly block), `scripts/memory_reflection/nightly_lived_memory.py` (reuse `run_synthesis_pass`, `:385`); Test `tests/test_reflection_dry_run_wiring.py`.

- [ ] **Step 1 — tests:** with `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1` + write-mode off, the nightly hook calls `run_synthesis_pass(dry_run=True)`, **persists nothing to durable memory**, and writes the candidate reflections + cited source ids + drops to a fresh `logs/reflection_dry_runs/<ts>.jsonl`; `maez.log` gets only the **path + content-free counts**, never the reflection text. Flag off → hook is a no-op.
- [ ] **Step 2 — implement:** add a nightly reflection hook (in the existing nightly block, e.g. ~04:00 after the 3 AM consolidation in `_consolidation_loop`, or a dedicated nightly slot). Behind `MAEZ_REFLECTION_SYNTHESIS_ENABLED`. **Extend the dry-run path to CAPTURE candidates** (the existing `dry_run=True` is count-only — surface the actual `synthesize_reflections` candidate objects: text + `source_memory_id`s + which were dropped for missing citations) and write them to the gitignored `logs/reflection_dry_runs/*.jsonl`. Add `logs/reflection_dry_runs/` to `.gitignore`. **Stage B (write):** only when `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` does `run_synthesis_pass(dry_run=False)` persist real episodes (evidence-cited, append-only) — left off this slice; the flag exists but stays 0 until the owner-witness of the dry-run passes.
- [ ] **Step 3:** Run → PASS. Commit `feat(reflection): nightly dry-run wiring + local witness artifact (persist nothing)`.

---

## Task 3: Consolidation telemetry (content-free) + the model-label fix

**Files:** `memory/memory_manager.py` (raw→daily), `core/evolution/dream_state.py` (dream), the reflection hook (Task 2); Test extends the above.

- [ ] **Step 1 — tests:** each organ emits a content-free `consolidation_telemetry` with exactly `{organ, inputs_count, outputs_count, model, duration_ms, rails_blocked, status, reason}` — numbers/enums/model-alias only; assert the field set carries **no memory/reflection text**. `model` = the **actually served** model (from `/props`), not the requested label.
- [ ] **Step 2 — implement:** emit `consolidation_telemetry` from raw→daily (`consolidate_daily`), the dream cycle, and the reflection hook. `rails_blocked` = untrusted-filter drops (consolidation) / uncited-reflection drops (reflection). **Model-label fix (the one-liner T0 deferred):** report the served model; if Task 0 confirmed `gemma4:26b` is a dead label running on Qwen, either correct the `MODEL` constant to route through the live backend OR clearly mark it — and the telemetry's `model=` now makes any future drift visible. (Do NOT change which model runs — only stop lying about it.)
- [ ] **Step 3:** Run → PASS. Commit `feat(consolidation): content-free telemetry + honest served-model reporting`.

---

## Task 4: Regression + owner-run witness

- [ ] **Step 1:** Full dream/reflection/memory-manager/consolidation suites green; flag-off + write-off = today's behavior exactly (3 AM consolidation unchanged except it now emits telemetry).
- [ ] **Step 2:** Floor both directions on a clean checkout (NOT git stash); known-unrelated trio excluded by name.
- [ ] **Step 3 — owner-run witness note** (`docs/slices/sleep-consolidation/acceptance.md`):
  - **Dream:** with the owner genuinely AFK ≥30 min (and not fresh-present on camera), the dream fires (cooldowned), produces a sane single-paragraph proposal (owner-gated), telemetry shows `organ=dream ran`. With the owner active, it does NOT fire. Activity-unprovable → does NOT fire.
  - **Reflection dry-run:** flag on → `logs/reflection_dry_runs/*.jsonl` fills with candidate reflections + citations; **nothing persisted**; owner reads a few for grounding/voice. Pass → consider flipping `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` (separate decision). Fail → keep dry-run.
  - **Telemetry:** `consolidation_telemetry` shows the *real* served model for the 3 AM consolidation (resolves the gemma question), inputs/outputs/rails_blocked, content-free.

---

## Self-Review

- **Two channels, never mixed:** `consolidation_telemetry` content-free (→ maez.log); reflection candidates contentful (→ gitignored local artifact). Tested.
- **Asymmetric idle is exhaustively tested:** activity-uncertainty blocks, camera-uncertainty doesn't, fresh-present/fresh-hint block, threshold enforced.
- **Nothing new writes durable memory this slice:** dream = proposal (owner-gated, pre-existing); reflection = dry-run (write flag stays 0); telemetry = read-only emit. Flag-off/write-off = exact current behavior.
- **The model question gets *resolved by observation*** (T0 probe + T3 honest reporting), not by guessing — and the label fix only stops the mislabel, never changes which model runs.
