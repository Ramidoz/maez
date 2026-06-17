# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Importing skills.web_interface must NOT boot a live MemoryManager.

Hermetic witnesses (the egress canaries) import build_claude_router_cloud_payload
from skills.web_interface; that import must not, as a side effect, construct a
live MemoryManager + chromadb. The first real web request that needs memory
still wakes it exactly as before. Run in a subprocess for true fresh-module
isolation (no in-process sys.modules / Flask pollution of the suite).
"""

from __future__ import annotations

import subprocess
import sys
import unittest
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _probe_env() -> dict[str, str]:
    env = dict(os.environ)
    env["MAEZ_SECRETS_DISABLE_NEW_LOADER"] = "1"
    env.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "test-token")
    return env


class WebInterfaceLazyMemoryTests(unittest.TestCase):
    def test_import_constructs_no_memory_manager_until_first_use(self):
        probe = "\n".join([
            "import sys",
            f"sys.path.insert(0, {str(_REPO)!r})",
            "import memory.memory_manager as mm",
            "constructed = []",
            "class _Spy:",
            "    def __init__(self, *a, **k):",
            "        constructed.append(1)",
            "    def __getattr__(self, n):",
            "        return lambda *a, **k: None",
            "mm.MemoryManager = _Spy",  # bind the spy before web_interface imports it
            "import skills.web_interface as wi",
            # the module import alone must construct zero MemoryManagers
            "assert constructed == [], 'import constructed %d MemoryManager(s)' % len(constructed)",
            # the first real attribute access wakes exactly one
            "wi.memory.recall_for_telegram",
            "assert len(constructed) == 1, 'first access constructed %d' % len(constructed)",
            "print('LAZY_OK')",
        ])
        r = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=str(_REPO), timeout=180, env=_probe_env()
        )
        self.assertIn(
            "LAZY_OK", r.stdout,
            msg=f"rc={r.returncode}\nstdout={r.stdout}\nstderr={r.stderr[-2500:]}",
        )

    def test_concurrent_first_access_constructs_one_memory_manager(self):
        probe = "\n".join([
            "import sys, threading, time",
            f"sys.path.insert(0, {str(_REPO)!r})",
            "import memory.memory_manager as mm",
            "constructed = []",
            "class _Spy:",
            "    def __init__(self, *a, **k):",
            "        time.sleep(0.05)",
            "        constructed.append(1)",
            "    def __getattr__(self, n):",
            "        return lambda *a, **k: None",
            "mm.MemoryManager = _Spy",
            "import skills.web_interface as wi",
            "threads = [threading.Thread(target=lambda: wi.memory.recall_for_telegram) for _ in range(12)]",
            "[t.start() for t in threads]",
            "[t.join() for t in threads]",
            "assert len(constructed) == 1, 'concurrent first access constructed %d' % len(constructed)",
            "print('LAZY_CONCURRENT_OK')",
        ])
        r = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=str(_REPO), timeout=180, env=_probe_env()
        )
        self.assertIn(
            "LAZY_CONCURRENT_OK", r.stdout,
            msg=f"rc={r.returncode}\nstdout={r.stdout}\nstderr={r.stderr[-2500:]}",
        )


if __name__ == "__main__":
    unittest.main()
