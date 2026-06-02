# Test-Hermeticity (maez.log) v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stop tests from writing to the production `logs/maez.log` by guarding the daemon's import-time file handler behind `MAEZ_DISABLE_FILE_LOG`, set in the test harness. Live daemon logging byte-identical when the env is unset.

**Architecture:** Wrap the module-level `RotatingFileHandler` create+attach (`daemon/maez_daemon.py:2267-2275`) in an env guard; the stderr `stream_handler` stays unconditional. `tests/__init__.py` sets the env via its existing `setdefault` pattern. Two tests pin mechanism + outcome.

**Tech Stack:** Python, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-06-02-test-hermeticity-maez-log-v0-design.md`

> **Outcome-test note (deviation from spec §3, flagged for owner):** the spec's literal "snapshot `logs/maez.log` size/mtime, assert unchanged" is **flaky on a dev machine where the live daemon is running** — the daemon writes to `logs/maez.log` every cycle, so a size/mtime snapshot can change between reads independent of the test. A flaky test in a *hermeticity* slice would be self-defeating. So the outcome test below proves the same thing **daemon-immune**: drive the hook, confirm it emitted log records (sanity), and assert **no `FileHandler` is attached to the `maez` logger** — i.e. the hook's logs reach no file at all. Same guarantee ("tests don't touch the prod log"), zero flake. Owner can revert to the literal snapshot if preferred (acceptable in CI where no daemon runs).

**Lane:** owner picks Codex vs inline.

---

## Task 1: Guard the file handler + harness env + tests (TDD)

**Files:**
- Create: `tests/test_log_hermeticity.py`
- Modify: `daemon/maez_daemon.py` (2267-2275 guard)
- Modify: `tests/__init__.py` (env setdefault)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_log_hermeticity.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests must not write to the production logs/maez.log (test-hermeticity v0)."""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class MaezLogHermeticityTest(unittest.TestCase):
    def test_maez_logger_has_no_prod_file_handler_in_test_mode(self):
        import daemon.maez_daemon as md

        prod = os.path.abspath(str(md.LOG_PATH))
        maez_logger = logging.getLogger("maez")
        offenders = [
            h for h in maez_logger.handlers
            if os.path.abspath(getattr(h, "baseFilename", "") or "") == prod
        ]
        self.assertEqual(
            offenders, [],
            f"maez logger must not have a handler writing to {prod} under test mode",
        )

    def test_driving_reflection_hook_reaches_no_file_handler(self):
        import daemon.maez_daemon as md
        from tests.test_reflection_dry_run_wiring import _FakeEpisodeStore

        maez_logger = logging.getLogger("maez")

        # No file destination should exist on the maez logger in test mode.
        file_handlers_before = [h for h in maez_logger.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(file_handlers_before, [], "no FileHandler may be attached to maez logger in test mode")

        # Fake brain call carrying terminal metadata: no real llama-server, no durable write.
        def _fake_llm(_prompt):
            _fake_llm.last_finish_reason = "stop"
            _fake_llm.max_tokens = 8192
            _fake_llm.last_raw_content = "[]"
            return "[]"

        # Capture records to prove the hook actually exercised logging (sanity).
        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(record)

        cap = _Cap()
        maez_logger.addHandler(cap)
        try:
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                os.environ, {"MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1"}, clear=False
            ):
                md._run_reflection_synthesis_nightly(
                    SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                    llm_call=_fake_llm,
                    artifact_dir=Path(tmp),
                )
        finally:
            maez_logger.removeHandler(cap)

        self.assertTrue(captured, "the reflection hook should have emitted log records (sanity)")
        # And driving it created no FileHandler as a side effect — logs reached no file.
        file_handlers_after = [h for h in maez_logger.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(file_handlers_after, [], "tests must not attach a FileHandler / touch the prod log")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/python -m unittest tests.test_log_hermeticity -v`
Expected: **FAIL** — `tests/__init__.py` does not yet set `MAEZ_DISABLE_FILE_LOG`, and the daemon attaches the `RotatingFileHandler` at import, so the `maez` logger *does* have a prod file handler. Both tests fail (the prod-handler list is non-empty).

- [ ] **Step 3: Guard the file handler in the daemon**

In `daemon/maez_daemon.py`, wrap the file-handler create+attach (2267-2275) — leave the `stream_handler` (2277-2281) exactly as-is:

```python
if not (os.environ.get("MAEZ_DISABLE_FILE_LOG", "") or "").strip():
    file_handler = _logging_handlers.RotatingFileHandler(
        LOG_PATH,
        maxBytes=50 * 1024 * 1024,
        backupCount=10,
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(stream_handler)
```

(`os` is already imported at module top — verify; if not, it is, since the daemon uses `os.environ` extensively.)

- [ ] **Step 4: Set the env in the test harness**

In `tests/__init__.py`, add (next to the existing `MAEZ_ROUTING_OBSERVATION_DB_PATH` setdefault):

```python
os.environ.setdefault("MAEZ_DISABLE_FILE_LOG", "1")
```

- [ ] **Step 5: Run to verify PASS**

Run: `.venv/bin/python -m unittest tests.test_log_hermeticity -v`
Expected: **PASS** — `tests/__init__.py` sets the env before any daemon import; the guard skips the file handler; the hook's logs reach only stderr + the temporary capture handler; no `FileHandler` on the `maez` logger.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/__init__.py tests/test_log_hermeticity.py
git commit -m "fix(test): stop tests writing to production logs/maez.log

The daemon attaches a RotatingFileHandler to logs/maez.log at module
import, so any test importing the daemon polluted the live log (caused
two false alarms in the 2026-06-02 sleep-organ stock-take). Guard the
file-handler create+attach behind MAEZ_DISABLE_FILE_LOG (set by
tests/__init__.py); stderr stays unconditional. Live daemon byte-
identical when the env is unset. Tests pin: no prod-path FileHandler on
the maez logger, and driving the reflection hook reaches no file."
```

---

## Task 2: Regression (prove live unchanged + nothing else disturbed)

- [ ] **Step 1: Prove the guard is a no-op when the env is unset (live-identical)**

Run:

```bash
.venv/bin/python - <<'PY'
import os, logging
os.environ.pop("MAEZ_DISABLE_FILE_LOG", None)  # simulate LIVE (env absent)
import daemon.maez_daemon as md
prod = os.path.abspath(str(md.LOG_PATH))
hits = [h for h in logging.getLogger("maez").handlers
        if os.path.abspath(getattr(h, "baseFilename", "") or "") == prod]
print("LIVE-mode prod file handler attached:", len(hits) == 1)
assert len(hits) == 1, "live daemon must still attach its maez.log handler"
print("OK: live logging unchanged")
PY
```

Expected: `LIVE-mode prod file handler attached: True` / `OK`. (Run this as a standalone process so `tests/__init__.py` is NOT imported and the env is genuinely absent — proves the live path is byte-identical.)

- [ ] **Step 2: Targeted suites green (incl. the previously-polluting ones)**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_log_hermeticity \
  tests.test_reflection_dry_run_wiring \
  tests.test_nightly_lived_memory \
  tests.test_consolidation_telemetry \
  tests.test_tier2_daemon_runtime_2026_05_04 \
  -v
```

Expected: all PASS — the env guard doesn't break existing daemon/reflection/consolidation tests (the existing `RotatingFileHandler` checks are source-text assertions, unaffected by a runtime env guard).

- [ ] **Step 3: Floor both directions + confirm no live-log writes during a full run**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base; name any branch-only header.

Optionally (manual, owner): note `logs/maez.log` mtime before a full test run and after — on a machine where the daemon is **stopped**, it should be unchanged; on a running-daemon machine the daemon's own writes dominate (which is exactly why the outcome test is handler-based, not file-snapshot-based).

---

## Self-Review

- **Spec coverage:** §2.1 guard → Task 1 Step 3; §2.2 env line → Step 4; §3 mechanism test → Step 1 (`test_maez_logger_has_no_prod_file_handler_in_test_mode`); §3 outcome test → Step 1 (`test_driving_reflection_hook_reaches_no_file_handler`, adapted daemon-immune per the flagged note); §4 live-unchanged → Task 2 Step 1. Non-goals (no defer-to-main, no temp-redirect, no other file loggers) — respected.
- **Placeholder scan:** none — guard code, env line, and both tests are concrete.
- **Type consistency:** `md.LOG_PATH` is a `Path` (compared via `os.path.abspath(str(...))`); `RotatingFileHandler`/`FileHandler` expose `baseFilename`; `_run_reflection_synthesis_nightly(daemon, *, llm_call=, artifact_dir=)` and `_FakeEpisodeStore` reused from `tests/test_reflection_dry_run_wiring.py`; the fake `llm_call` carries `last_finish_reason`/`max_tokens`/`last_raw_content` (the terminal metadata `run_synthesis_pass` copies).
- **One risk:** the deviation from the spec's literal snapshot — flagged prominently above; owner to confirm the daemon-immune handler-based outcome test is acceptable (it is strictly more reliable and proves the same property).
