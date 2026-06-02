# Reflection Input Hygiene v0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop reflection synthesis from digesting its own prior output by excluding `source_kind="reflection"` from the synthesis input pool — proven at the daemon-hook integration level.

**Architecture:** A single-line filter change in `run_synthesis_pass` (the live synthesis path the daemon hook calls), guarded by one integration test that drives the daemon hook `_run_reflection_synthesis_nightly`, patches `synthesize_reflections`, and asserts a reflection episode in the store never reaches the synthesis inputs. No telemetry change; dry-run / write-off preserved; nothing deleted or hidden from recall.

**Tech Stack:** Python, `unittest` (runner: `.venv/bin/python -m unittest`, **NOT pytest**), `unittest.mock`, SQLite-backed `EpisodeStore`.

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-input-hygiene-v0-design.md`

**Lane:** Codex implements, Claude cross-verifies (special attention: the test asserts at the daemon-hook level, not a helper; the filter sits before the window slice; recall/store/telemetry untouched).

---

## Task 1: Exclude reflection from the synthesis input pool (TDD, daemon-path proof)

**Files:**
- Create: `tests/test_reflection_input_hygiene.py`
- Modify: `scripts/memory_reflection/nightly_lived_memory.py:466-469`

- [ ] **Step 1: Write the failing integration test**

This is the load-bearing test. It drives the *daemon hook* (`_run_reflection_synthesis_nightly`), which calls `run_synthesis_pass(episode_store=daemon.lived_episodes, ...)`, which calls `synthesize_reflections(recent_episodes=recent, ...)`. We patch `synthesize_reflections` (a function-local import resolved from `core.memory.reflection` at call time) to capture the `recent_episodes` it receives, and assert the reflection episode in the store is absent while the real-evidence episode is present.

Create `tests/test_reflection_input_hygiene.py`:

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.memory.episodes import EpisodeStore


class _FakeDaemon:
    """Minimal daemon stand-in: the hook reads only ``.lived_episodes``."""

    def __init__(self, store: EpisodeStore) -> None:
        self.lived_episodes = store


class ReflectionInputHygieneTest(unittest.TestCase):
    def test_reflection_episode_not_passed_to_synthesize(self) -> None:
        tmp = tempfile.mkdtemp()
        store = EpisodeStore(str(Path(tmp) / "ep.db"))

        # One prior reflection (must be EXCLUDED) and one real-evidence
        # episode (must remain — the stomach still eats original food).
        refl_id = store.add(
            title="prior reflection",
            summary="an earlier synthesized thought",
            participants=["maez"],
            source_memory_ids=["core-1"],
            source_kind="reflection",
        )
        core_id = store.add(
            title="core memory",
            summary="a real evidence episode",
            participants=["maez"],
            source_memory_ids=["raw-1"],
            source_kind="core_memory",
        )
        daemon = _FakeDaemon(store)

        captured: dict = {}

        def _spy(*, recent_episodes, recent_raw, llm_call, max_reflections, drop_sink):
            captured["recent_episodes"] = list(recent_episodes)
            return []  # no candidates -> dry-run writes an empty artifact, persists nothing

        from daemon.maez_daemon import _run_reflection_synthesis_nightly

        with mock.patch.dict(
            os.environ,
            {"MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1", "MAEZ_REFLECTION_SYNTHESIS_WRITE": ""},
            clear=False,
        ), mock.patch("core.memory.reflection.synthesize_reflections", _spy):
            _run_reflection_synthesis_nightly(
                daemon,
                llm_call=lambda *a, **k: "",
                artifact_dir=Path(tmp),
            )

        self.assertIn("recent_episodes", captured, "synthesize_reflections was never called via the daemon hook")
        ids = {ep.get("id") for ep in captured["recent_episodes"]}
        kinds = {ep.get("source_kind") for ep in captured["recent_episodes"]}
        self.assertIn(core_id, ids, "real-evidence episode must still be fed to synthesis")
        self.assertNotIn(refl_id, ids, "prior reflection must NOT be fed to synthesis")
        self.assertNotIn("reflection", kinds, "no reflection episode may reach the synthesis input pool")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it FAILS**

Run: `.venv/bin/python -m unittest tests.test_reflection_input_hygiene -v`
Expected: **FAIL** on `assertNotIn(refl_id, ids)` — before the fix, the filter excludes only `telegram_exchange`, so the reflection episode reaches `recent_episodes`.

- [ ] **Step 3: Implement the one-line filter change**

In `scripts/memory_reflection/nightly_lived_memory.py`, the current input-pool builder (around lines 466-469) reads:

```python
    recent = [
        ep for ep in active
        if ep.get("source_kind") != "telegram_exchange"
    ][:recent_window_episodes]
```

Change the membership test to exclude `reflection` as well, **before** the `[:recent_window_episodes]` slice (so old reflections cannot crowd out real source episodes within the window). Also extend the adjacent comment to record the reason:

```python
    # Decision 25 / ADR 0030: telegram_exchange episodes are structural
    # biography pointers, not synthesis material. Reflection Input Hygiene
    # v0 (2026-06-02): exclude prior `reflection` episodes too — synthesis
    # must digest original evidence, never its own earlier output (no
    # laundering loop). Filter BEFORE the window slice so real source
    # episodes are not crowded out. Reflections stay stored/recallable
    # elsewhere; this narrows only this organ's input.
    recent = [
        ep for ep in active
        if ep.get("source_kind") not in ("telegram_exchange", "reflection")
    ][:recent_window_episodes]
```

- [ ] **Step 4: Run the test to verify it PASSES**

Run: `.venv/bin/python -m unittest tests.test_reflection_input_hygiene -v`
Expected: **PASS** — the reflection episode is excluded; the core_memory episode remains.

- [ ] **Step 5: Confirm no telemetry change and no other input-builder escaped**

Verify there is **no** edit to `daemon/maez_daemon.py` telemetry (`inputs_count` stays `candidates + drops`) and **no** new telemetry field. Then grep for any *other* place that feeds `list_active()` into synthesis on the daemon path:

Run: `grep -rn "list_active(" scripts/memory_reflection/nightly_lived_memory.py daemon/maez_daemon.py`
Expected: the only synthesis-input builder reached by `_run_reflection_synthesis_nightly → run_synthesis_pass` is the `recent = [...]` block just edited. (Other `list_active()` callers that do NOT feed `synthesize_reflections` — e.g. counts, the CLI `main` insight-window path — are out of scope; do not change them. If any *other* call path feeds `synthesize_reflections`, filter there too and add an assertion; otherwise leave them.)

- [ ] **Step 6: Commit**

```bash
git add tests/test_reflection_input_hygiene.py scripts/memory_reflection/nightly_lived_memory.py
git commit -m "fix(reflection): exclude prior reflection episodes from synthesis inputs

Reflection Input Hygiene v0: synthesis must digest original evidence,
not its own earlier output. Filter source_kind=reflection (alongside
telegram_exchange) before the recent-window slice in run_synthesis_pass.
Proven at the daemon-hook integration level: a reflection episode in
daemon.lived_episodes never reaches synthesize_reflections. No telemetry
change; dry-run/write-off preserved; reflections stay stored/recallable."
```

---

## Task 2: Regression + owner re-run witness

**Files:**
- Modify: `docs/slices/sleep-consolidation/acceptance.md` (append a Reflection Input Hygiene witness section)

- [ ] **Step 1: Run the reflection + consolidation suites green**

Run: `.venv/bin/python -m unittest tests.test_reflection_input_hygiene tests.test_reflection_dry_run_wiring tests.test_consolidation_telemetry -v`
Expected: all PASS. (These cover the dry-run wiring, persist-nothing, and content-free telemetry invariants that must remain intact.)

- [ ] **Step 2: Floor both directions (NOT git stash)**

On a clean checkout/worktree, run the full discover before and after the change and compare counts (the known ambient floor wobbles ±1-2 from order-pollution — name any delta, do not absorb it silently):

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: failures/errors within ±2 of the `main@50f388c` base (12 failures / ~34 errors); any branch-only failure must reproduce in isolation or be named as pre-existing order-pollution. No NEW deterministic failure in reflection/consolidation tests.

- [ ] **Step 3: Owner re-run witness note**

Append to `docs/slices/sleep-consolidation/acceptance.md` a "Reflection Input Hygiene v0 — re-run witness" section stating the acceptance gate for the owner to run from `main` after merge:

```markdown
## Reflection Input Hygiene v0 — re-run witness (owner-run)

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off.

- **Recursion closed (hard gate):** a fresh `logs/reflection_dry_runs/*.jsonl`;
  resolve every candidate's `source_memory_ids` against `memory/lived_episodes.db`
  (e.g. `EpisodeStore.get(id)["source_kind"]`) — require **zero** `source_kind=reflection`
  citations. Candidates grounded only in core_memory / followup_doc / real evidence.
- **Voice (natural experiment, observe only):** if the harsh "suppresses technical
  novelty"-class framing is GONE, recursion caused it (fixed for free). If it SURVIVES
  clean inputs, open a SEPARATE voice/prompt slice — this slice changed no synthesis prompt.
- **Then, separately:** only a grounded + in-voice dry-run reopens the
  `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision (a distinct, later owner call).
```

- [ ] **Step 4: Commit**

```bash
git add docs/slices/sleep-consolidation/acceptance.md
git commit -m "docs(reflection): re-run witness note for input hygiene v0"
```

---

## Self-Review

- **Spec coverage:** §2 change → Task 1 Step 3 (filter before window slice); §3 boundary (recall/store/telemetry untouched) → Task 1 Step 5 (grep proves no other input-builder; no telemetry edit) + the test asserts the core_memory episode survives; §3 integration-witness → Task 1 Steps 1-4 (daemon-hook level, patches `synthesize_reflections`); §4 no telemetry change → Task 1 Step 5; §5 acceptance → Task 2 Step 3. Rail #2 / voice / depth-bounds are non-goals — correctly absent.
- **Placeholder scan:** none — every code/command step is concrete.
- **Type consistency:** `_run_reflection_synthesis_nightly(daemon, *, llm_call=, artifact_dir=)`, `run_synthesis_pass(episode_store=, llm_call=, report=, dry_run=)`, `synthesize_reflections(recent_episodes=, recent_raw=, llm_call=, max_reflections=, drop_sink=)`, `EpisodeStore.add(*, title, summary, participants, source_memory_ids, source_kind, ...)` — all match the live signatures verified before planning. Episode dicts expose `id` and `source_kind`.
- **The one risk** is patch resolution: `synthesize_reflections` is imported function-locally inside `run_synthesis_pass` from `core.memory.reflection`, so the patch target is `core.memory.reflection.synthesize_reflections` (resolved at call time) — verified in Task 1 Step 1.
