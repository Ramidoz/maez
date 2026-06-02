# Reflection Max-Reflections Dial v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire an honest `MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS` dial into the daemon reflection hook (default 3, safe-fallback 3), so limited regularization can run at 1/night without a dead flag.

**Architecture:** A new env helper in `daemon/maez_daemon.py` (mirroring `_reflection_synthesis_enabled`) reads the var with default/fallback 3; `_run_reflection_synthesis_nightly` passes it as `max_reflections=` to `run_synthesis_pass`. Two tests drive the hook with `run_synthesis_pass` patched.

**Tech Stack:** Python, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-max-reflections-dial-v0-design.md`

**Lane:** owner picks Codex vs inline. Cross-verify: default-3 preserved; env reaches the hook; nothing else changes.

---

## Task 1: The max-reflections dial (TDD)

**Files:**
- Modify: `daemon/maez_daemon.py` (new helper + the `run_synthesis_pass` call in `_run_reflection_synthesis_nightly`)
- Test: `tests/test_reflection_dry_run_wiring.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_reflection_dry_run_wiring.py` (reuses the existing `SimpleNamespace`/`_FakeEpisodeStore`/`mock`/`os` imports the daemon-hook tests already use):

```python
class ReflectionMaxReflectionsDialTest(unittest.TestCase):
    def _run_hook_capturing_max(self, env):
        import daemon.maez_daemon as md
        captured = {}

        def _fake_pass(*, episode_store, llm_call, report, dry_run, max_reflections=3):
            captured["max_reflections"] = max_reflections

        with mock.patch.dict(os.environ, env, clear=True), mock.patch(
            "scripts.memory_reflection.nightly_lived_memory.run_synthesis_pass", _fake_pass
        ):
            md._run_reflection_synthesis_nightly(
                SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                llm_call=lambda *a, **k: "[]",
                artifact_dir=Path(tempfile.mkdtemp()),
            )
        return captured.get("max_reflections")

    def test_env_max_one_reaches_hook(self):
        got = self._run_hook_capturing_max(
            {"MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
             "MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS": "1"}
        )
        self.assertEqual(got, 1)

    def test_unset_keeps_default_three(self):
        got = self._run_hook_capturing_max({"MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1"})
        self.assertEqual(got, 3)

    def test_invalid_falls_back_to_three(self):
        got = self._run_hook_capturing_max(
            {"MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
             "MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS": "0"}
        )
        self.assertEqual(got, 3)
```

(If `_FakeEpisodeStore` / `Path` / `tempfile` / `SimpleNamespace` aren't already imported in this file, import them at top — check the existing daemon-hook test class first and reuse its fixtures.)

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring.ReflectionMaxReflectionsDialTest -v`
Expected: **FAIL** — `_run_reflection_synthesis_nightly` currently calls `run_synthesis_pass` without `max_reflections`, so the patched fake receives the default `3` even when env says `1` (the `test_env_max_one_reaches_hook` assertion fails).

- [ ] **Step 3: Implement the helper**

In `daemon/maez_daemon.py`, near `_reflection_synthesis_enabled`, add:

```python
def _reflection_synthesis_max_reflections(environ: object | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = (env.get("MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS", "") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 3
    return value if value >= 1 else 3
```

- [ ] **Step 4: Pass it through**

In `_run_reflection_synthesis_nightly`, add `max_reflections=` to the `run_synthesis_pass(...)` call:

```python
        run_synthesis_pass(
            episode_store=getattr(daemon, "lived_episodes"),
            llm_call=llm_call,
            report=report,
            dry_run=dry_run,
            max_reflections=_reflection_synthesis_max_reflections(),
        )
```

- [ ] **Step 5: Run to verify PASS**

Run: `.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring.ReflectionMaxReflectionsDialTest -v`
Expected: **PASS** — env `1` → `max_reflections=1`; unset → `3`; invalid → `3`.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/test_reflection_dry_run_wiring.py
git commit -m "feat(reflection): honest max-reflections-per-night dial

Daemon reflection hook now reads MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS
(default 3, safe-fallback 3 on invalid/missing) and passes it to
run_synthesis_pass, so limited regularization can run 1/night without a
dead flag. Unset = today's behavior (3). Don't let the absence of a knob
set Maez's metabolism shape."
```

---

## Task 2: Regression

- [ ] **Step 1: Targeted suites green**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_reflection_dry_run_wiring \
  tests.test_reflection_synthesis \
  tests.test_reflection_input_hygiene \
  tests.test_nightly_lived_memory \
  tests.test_consolidation_telemetry \
  -v
```

Expected: all PASS — the dial added; default-3 behavior preserved; nothing else disturbed.

- [ ] **Step 2: Floor both directions**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base; name any branch-only header.

- [ ] **Step 3: Commit (if any doc/touch)** — none expected beyond Task 1; skip if clean.

---

## Owner step (after merge — NOT in code)

Owner adds to `~/.config/maez/model.env` (no restart; next natural restart activates):

```env
MAEZ_REFLECTION_SYNTHESIS_ENABLED=1
MAEZ_REFLECTION_SYNTHESIS_WRITE=1
MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS=1
```

Then the 2-night observation window; Claude resolves provenance/citations/fair-tone after the first night.

---

## Self-Review

- **Spec coverage:** §2.1 helper → Task 1 Step 3; §2.2 pass-through → Step 4; §3 tests → Step 1 (env-reaches, unset-default, invalid-fallback); §4 unchanged → Task 2 regression; §5 regularization → Owner step. Non-goals (no default change, no restart, no code-enable) — respected.
- **Placeholder scan:** none — helper, call, and tests are concrete.
- **Type consistency:** `_reflection_synthesis_max_reflections() -> int`; `run_synthesis_pass(..., max_reflections: int = 3)` already accepts it; patch target `scripts.memory_reflection.nightly_lived_memory.run_synthesis_pass` matches the hook's function-local import.
- **One risk:** if the existing daemon-hook test class uses different fixture names than `_FakeEpisodeStore`/`SimpleNamespace`, reuse whatever it already defines (Step 1 note) — don't introduce a parallel fake.
