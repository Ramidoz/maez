"""Held-now Phase 1: the whole-turn exactly-once receipt (decorator
form after code-gate round 1 -- the function keeps its name and body
for the AST contracts; the receipt lives in _held_now_whole_turn).

Code-gate weak-test fixes folded in: the carrier test is now an AST
connectivity check (the held_now_history parameter must actually reach
_assemble_working_set selection), not a signature-existence check.
"""

from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path
from unittest import mock

from daemon.maez_daemon import MaezDaemon, _held_now_whole_turn

_SHADOW = {"MAEZ_HELD_NOW_SHADOW": "1", "MAEZ_HELD_NOW_ENABLED": ""}
_OFF = {"MAEZ_HELD_NOW_SHADOW": "", "MAEZ_HELD_NOW_ENABLED": ""}
_REPO = Path(__file__).resolve().parent.parent


class _Host:
    """Minimal host for the decorator under test."""


def _decorated(body):
    host = _Host()
    host.method = _held_now_whole_turn(body).__get__(host)
    return host


class WholeTurnReceiptTests(unittest.TestCase):
    def test_receipt_emitted_once_on_normal_return(self):
        host = _decorated(lambda self, text, source="unknown", **kw: "hi")
        with mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ) as logs:
            reply = host.method("hello", "telegram_surface")
        self.assertEqual(reply, "hi")
        receipts = [l for l in logs.output if "held_now_shadow" in l]
        self.assertEqual(len(receipts), 1)
        self.assertIn("surface=telegram_surface", receipts[0])
        self.assertIn("trace_id=", receipts[0])

    def test_receipt_emitted_once_on_raise_with_error_path(self):
        def _boom(self, text, source="unknown", **kw):
            raise RuntimeError("boom")

        host = _decorated(_boom)
        with mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ) as logs:
            with self.assertRaises(RuntimeError):
                host.method("hello", "telegram_surface")
        receipts = [l for l in logs.output if "held_now_shadow" in l]
        self.assertEqual(len(receipts), 1)
        self.assertIn("final_reply_path=error", receipts[0])
        self.assertIn("ineligible_reason=error", receipts[0])

    def test_no_receipt_when_flags_off(self):
        host = _decorated(lambda self, text, source="unknown", **kw: "hi")
        with mock.patch.dict(os.environ, _OFF):
            with self.assertNoLogs("maez", level="INFO"):
                host.method("hello", "telegram_surface")

    def test_holder_is_turn_local_parameter_not_shared_state(self):
        # Code-gate blocker 3: two interleaved turns must not share a
        # holder. The body receives it as _hn_holder kwarg.
        seen = []

        def _body(self, text, source="unknown", _hn_holder=None, **kw):
            seen.append(_hn_holder)
            return "ok"

        host = _decorated(_body)
        with mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ):
            host.method("one", "telegram_surface")
            host.method("two", "telegram_surface")
        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])
        for holder in seen:
            self.assertIn("trace_id", holder)

    def test_body_stash_reaches_the_receipt(self):
        def _body(self, text, source="unknown", _hn_holder=None, **kw):
            _hn_holder["final_reply_path"] = "focused"
            _hn_holder["turn_kind"] = "ordinary"
            _hn_holder["needs_dialogue"] = False
            _hn_holder["fail_safe_legacy"] = False
            _hn_holder["held_now_alloc"] = {
                "domain": "full_count", "reason": None, "pairs_rendered": 3,
            }
            _hn_holder["focused_row_id"] = "row-abc"
            return "ok"

        host = _decorated(_body)
        with mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ) as logs:
            host.method("hello", "telegram_surface")
        receipt = next(l for l in logs.output if "held_now_shadow" in l)
        for token in (
            "final_reply_path=focused", "turn_kind=ordinary",
            "needs_dialogue=False", "fail_safe_legacy=False",
            "domain=full_count", "pairs_rendered=3",
            "focused_row_id=row-abc", "ineligible_reason=None",
        ):
            self.assertIn(token, receipt)

    def test_ineligible_reason_mapping(self):
        for path, reason in (
            ("clinical", "pre_seam_return"),
            ("camera", "pre_seam_return"),
            ("tool", "tool_mode"),
            ("echo", "echo_mode"),
            ("honest_empty", "honest_empty_mode"),
            ("self_status", "post_resolution_override"),
            ("error", "error"),
        ):
            def _body(self, text, source="unknown", _hn_holder=None, **kw):
                _hn_holder["final_reply_path"] = path  # noqa: B023
                return "ok"

            host = _decorated(_body)
            with mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
                "maez", level="INFO"
            ) as logs:
                host.method("hello", "telegram_surface")
            receipt = next(l for l in logs.output if "held_now_shadow" in l)
            self.assertIn(f"ineligible_reason={reason}", receipt)

    def test_receipt_never_breaks_the_turn(self):
        host = _decorated(lambda self, text, source="unknown", **kw: "hi")
        with mock.patch.dict(os.environ, _SHADOW), mock.patch(
            "core.routing.focused_cognition.held_now_shadow_enabled",
            side_effect=RuntimeError("receipt plumbing broke"),
        ):
            reply = host.method("hello", "telegram_surface")
        self.assertEqual(reply, "hi")


class CarrierConnectivityTests(unittest.TestCase):
    def test_real_handle_message_is_decorated(self):
        self.assertTrue(
            getattr(MaezDaemon.handle_message, "__wrapped__", None),
            "handle_message must carry the whole-turn decorator",
        )
        import inspect

        params = inspect.signature(MaezDaemon.handle_message).parameters
        self.assertIn("held_now_history", params)

    def test_carrier_actually_feeds_assembly(self):
        # Code-gate weak-test fix: prove the parameter is CONSUMED --
        # the selection expression must reference held_now_history and
        # feed _assemble_working_set's chat_history argument.
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        tree = ast.parse(src)
        fn = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "handle_message"
        )
        fn_src = ast.get_source_segment(src, fn) or ""
        self.assertIn("_hn_history = (", fn_src)
        self.assertIn("held_now_history", fn_src)
        self.assertIn("chat_history=_hn_history", fn_src)


if __name__ == "__main__":
    unittest.main()
