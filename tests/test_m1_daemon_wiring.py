# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Source-level wiring tests for M1 daemon integration."""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _read(path: str) -> str:
    return (_REPO / path).read_text()


def _method_body(src: str, method_name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"method not found: {method_name}")


class M1DaemonWiringTests(unittest.TestCase):
    def test_daemon_initializes_m1_promoter_default_disabled(self):
        src = _read("daemon/maez_daemon.py")

        self.assertIn("M1LivedEpisodePromoter", src)
        self.assertIn("M1PromotionStore", src)
        self.assertIn("M1Config", src)
        self.assertIn("MAEZ_M1_LIVED_EPISODE_PROMOTION", src)
        self.assertIn('os.environ.get("MAEZ_M1_LIVED_EPISODE_PROMOTION", "0") == "1"', src)
        self.assertIn("self.m1_promoter", src)

    def test_handle_message_calls_m1_after_store_telegram_returns_raw_id(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "handle_message")

        audit_idx = body.find("reply = audit_assistant_text(")
        store_idx = body.find("_m1_raw_memory_id = self.memory.store_telegram(")
        m1_idx = body.find("self.m1_promoter.consider_audited_exchange(")
        trace_idx = body.find("_trace.stored_text_hash")

        self.assertGreater(audit_idx, 0)
        self.assertGreater(store_idx, audit_idx)
        self.assertGreater(m1_idx, store_idx)
        self.assertGreater(trace_idx, m1_idx)
        self.assertIn("raw_memory_id=_m1_raw_memory_id", body[m1_idx:m1_idx + 600])
        self.assertIn("owner_text=text", body[m1_idx:m1_idx + 600])
        self.assertIn("maez_reply=reply", body[m1_idx:m1_idx + 600])

    def test_loop_flushes_m1_on_daemon_cycle(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "_loop")
        cycle_idx = body.find("self.cycle_count += 1")
        flush_idx = body.find("self._m1_flush_due_windows()")
        reason_idx = body.find("result = self._reason(")

        self.assertGreater(cycle_idx, 0)
        self.assertGreater(flush_idx, cycle_idx)
        self.assertGreater(reason_idx, flush_idx)

    def test_health_includes_lived_episode_staleness(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "_run_health_server")

        self.assertIn("self._m1_staleness_health()", body)
        self.assertIn('"lived_episodes"', body)
        self.assertIn('"staleness"', body)

    def test_m1_does_not_import_private_thoughts(self):
        import core.memory.m1_lived_episode_promotion as m1

        src = inspect.getsource(m1)
        self.assertNotIn("private_thoughts", src)
        self.assertNotIn("PrivateThoughts", src)

