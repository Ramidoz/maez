# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for slice 1.6 shared-executor call-site migration.

Slice 1.6 replaces every ``loop.run_in_executor(None, ...)`` call with
``loop.run_in_executor(get_shared_executor(), ...)``. Passing ``None``
uses asyncio's default thread pool, which grows unbounded — the source
of the thread leak this slice closes. The shared executor in
``core/health/shared_executor.py`` is bounded (default 6 workers,
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
        # Migration uses two patterns:
        #   - LLM sites: ``run_llm_in_executor(loop, fn)`` — bounded
        #     await via asyncio.wait_for.
        #   - Non-LLM sites: ``loop.run_in_executor(get_shared_executor(),
        #     fn)`` — plain bounded pool.
        # Both route through the shared pool. Count BOTH.
        plain = self.src.count("get_shared_executor()")
        llm = self.src.count("run_llm_in_executor(")
        total = plain + llm
        self.assertGreaterEqual(
            total, 4,
            f"maez_adapter.py must use get_shared_executor() OR "
            f"run_llm_in_executor() at each of the 4 migrated "
            f"run_in_executor sites; saw {plain} plain + {llm} LLM "
            f"= {total} total.",
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
        # Migration uses two patterns:
        #   - LLM sites: ``run_llm_in_executor(loop, fn)`` — bounded
        #     await via asyncio.wait_for; helper internally calls
        #     get_shared_executor().
        #   - Non-LLM sites: ``loop.run_in_executor(get_shared_executor(),
        #     fn)`` — plain bounded pool, no awaiter timeout.
        # Both patterns route through the shared pool. Count BOTH.
        plain = self.src.count("get_shared_executor()")
        llm = self.src.count("run_llm_in_executor(")
        total = plain + llm
        self.assertGreaterEqual(
            total, 8,
            f"telegram_voice.py must use get_shared_executor() OR "
            f"run_llm_in_executor() at each of the 8 migrated "
            f"run_in_executor sites; saw {plain} plain + {llm} LLM "
            f"= {total} total.",
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


if __name__ == "__main__":
    unittest.main()
