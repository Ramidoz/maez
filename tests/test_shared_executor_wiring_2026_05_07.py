# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for slice 1.6 shared-executor call-site migration.

Slice 1.6 replaces every ``loop.run_in_executor(None, ...)`` call with
``loop.run_in_executor(get_shared_executor(), ...)``. Passing ``None``
uses asyncio's default thread pool, which grows unbounded — the source
of the thread leak this slice closes. The shared executor in
``core/health/shared_executor.py`` is bounded (default 8 workers,
configurable via the ``MAEZ_SHARED_EXECUTOR_MAX_WORKERS`` env var).

Inventory pinned by these tests:
  - skills/surface/maez_adapter.py: 4 sites
  - skills/telegram_voice.py:       8 sites
  - daemon/maez_daemon.py:          must call shutdown_shared_executor
                                    on stop so worker threads do not
                                    outlive the process.

Style mirrors test_dream_worker_wiring_2026_05_07.py and
test_wake_word_wiring_2026_05_07.py — read the source as text and
assert specific substrings / regex counts. No production import,
no daemon construction.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# Regex used by multiple tests: matches `run_in_executor(` followed by
# any whitespace/newlines, then the literal `None` token (word-bounded).
# This is the exact unbounded-default-pool shape slice 1.6 eliminates.
_UNBOUNDED_RE = re.compile(r"run_in_executor\(\s*None\b")


class SharedExecutorModuleTests(unittest.TestCase):
    """The shared executor primitive must exist and expose the public
    API the call sites consume."""

    @classmethod
    def setUpClass(cls):
        cls.module_path = REPO / "core" / "health" / "shared_executor.py"

    def test_shared_executor_module_exists(self):
        self.assertTrue(
            self.module_path.is_file(),
            f"{self.module_path} must exist — slice 1.6 primitive",
        )
        src = self.module_path.read_text()
        self.assertGreater(
            len(src.strip()), 0,
            "core/health/shared_executor.py must be non-empty",
        )
        self.assertIn(
            "def get_shared_executor",
            src,
            "shared_executor.py must define get_shared_executor()",
        )
        self.assertIn(
            "def shutdown_shared_executor",
            src,
            "shared_executor.py must define shutdown_shared_executor()",
        )

    def test_env_var_safe_fallback_in_shared_executor(self):
        """The bound must be configurable via env var so an operator
        can tune the worker count without a code change."""
        src = self.module_path.read_text()
        self.assertIn(
            "MAEZ_SHARED_EXECUTOR_MAX_WORKERS",
            src,
            "shared_executor.py must read MAEZ_SHARED_EXECUTOR_MAX_WORKERS "
            "so the worker bound is operator-tunable",
        )


class MaezAdapterCallSiteTests(unittest.TestCase):
    """skills/surface/maez_adapter.py — 4 migrated sites expected."""

    @classmethod
    def setUpClass(cls):
        cls.path = REPO / "skills" / "surface" / "maez_adapter.py"
        cls.src = cls.path.read_text()

    def test_no_unbounded_run_in_executor_in_maez_adapter(self):
        matches = _UNBOUNDED_RE.findall(self.src)
        self.assertEqual(
            len(matches), 0,
            f"maez_adapter.py must not call run_in_executor(None, ...); "
            f"that uses asyncio's unbounded default thread pool. "
            f"Found {len(matches)} unmigrated call site(s). "
            f"Replace each with run_in_executor(get_shared_executor(), ...).",
        )

    def test_maez_adapter_imports_get_shared_executor(self):
        ok = (
            "from core.health.shared_executor import" in self.src
            or "import core.health.shared_executor" in self.src
        )
        self.assertTrue(
            ok,
            "maez_adapter.py must import from core.health.shared_executor",
        )

    def test_maez_adapter_uses_get_shared_executor_call(self):
        # Slice 1.6 follow-up: production uses plain
        # ``loop.run_in_executor(get_shared_executor(), fn)`` at all
        # call sites. ``run_llm_in_executor`` was rolled back from
        # production (ghost-turn risk on side-effect-mutating LLM
        # calls); see core/health/shared_executor.py docstring.
        count = self.src.count("get_shared_executor()")
        self.assertGreaterEqual(
            count, 4,
            f"maez_adapter.py must call get_shared_executor() at each "
            f"of the 4 migrated run_in_executor sites; saw {count}. "
            f"All sites use plain loop.run_in_executor("
            f"get_shared_executor(), fn).",
        )


class TelegramVoiceCallSiteTests(unittest.TestCase):
    """skills/telegram_voice.py — 8 migrated sites expected."""

    @classmethod
    def setUpClass(cls):
        cls.path = REPO / "skills" / "telegram_voice.py"
        cls.src = cls.path.read_text()

    def test_no_unbounded_run_in_executor_in_telegram_voice(self):
        matches = _UNBOUNDED_RE.findall(self.src)
        self.assertEqual(
            len(matches), 0,
            f"telegram_voice.py must not call run_in_executor(None, ...). "
            f"Found {len(matches)} unmigrated call site(s). "
            f"Replace each with run_in_executor(get_shared_executor(), ...).",
        )

    def test_telegram_voice_imports_get_shared_executor(self):
        ok = (
            "from core.health.shared_executor import" in self.src
            or "import core.health.shared_executor" in self.src
        )
        self.assertTrue(
            ok,
            "telegram_voice.py must import from core.health.shared_executor",
        )

    def test_telegram_voice_uses_get_shared_executor_call(self):
        # Slice 1.6 follow-up: production uses plain
        # ``loop.run_in_executor(get_shared_executor(), fn)`` at all
        # call sites. ``run_llm_in_executor`` was rolled back from
        # production (ghost-turn risk on side-effect-mutating LLM
        # calls); see core/health/shared_executor.py docstring.
        count = self.src.count("get_shared_executor()")
        self.assertGreaterEqual(
            count, 8,
            f"telegram_voice.py must call get_shared_executor() at each "
            f"of the 8 migrated run_in_executor sites; saw {count}.",
        )


class DaemonShutdownTests(unittest.TestCase):
    """daemon/maez_daemon.py.stop() must shut the shared executor down
    on exit so worker threads don't outlive the process."""

    def test_daemon_calls_shutdown_shared_executor(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        self.assertIn(
            "shutdown_shared_executor",
            src,
            "daemon/maez_daemon.py must call shutdown_shared_executor "
            "during stop() so the bounded worker threads are joined "
            "before process exit.",
        )

    def test_daemon_uses_wait_false(self):
        """Slice 1.6 follow-up: daemon stop() must call
        shutdown_shared_executor with wait=False. With wait=True, a
        sync LLM call wedged on a dead llama.cpp would block stop()
        forever (the original slice 1.6 review caught this and
        verified empirically with a 2s blocked worker)."""
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        self.assertIn(
            "shutdown_shared_executor(wait=False",
            src,
            "daemon stop() must use shutdown_shared_executor("
            "wait=False, ...) so a wedged worker thread doesn't "
            "block daemon shutdown indefinitely",
        )


if __name__ == "__main__":
    unittest.main()
