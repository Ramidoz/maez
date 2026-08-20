"""Held-now Phase 1, commit C: the whole-turn exactly-once receipt.

The wrapper owns receipt state from function entry and emits in
`finally` — normal return, early return, and raise all account for
themselves. Emission only under the held-now flags.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from daemon.maez_daemon import MaezDaemon


def _bare_daemon() -> MaezDaemon:
    return MaezDaemon.__new__(MaezDaemon)


_SHADOW = {"MAEZ_HELD_NOW_SHADOW": "1", "MAEZ_HELD_NOW_ENABLED": ""}
_OFF = {"MAEZ_HELD_NOW_SHADOW": "", "MAEZ_HELD_NOW_ENABLED": ""}


class WholeTurnReceiptTests(unittest.TestCase):
    def test_receipt_emitted_once_on_normal_return(self):
        d = _bare_daemon()
        with mock.patch.object(
            MaezDaemon, "_handle_message_body", return_value="hi"
        ), mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ) as logs:
            reply = d.handle_message("hello", "telegram_surface")
        self.assertEqual(reply, "hi")
        receipts = [l for l in logs.output if "held_now_shadow" in l]
        self.assertEqual(len(receipts), 1)
        self.assertIn("surface=telegram_surface", receipts[0])
        self.assertIn("trace_id=", receipts[0])

    def test_receipt_emitted_once_on_raise_with_error_path(self):
        d = _bare_daemon()
        with mock.patch.object(
            MaezDaemon, "_handle_message_body", side_effect=RuntimeError("boom")
        ), mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ) as logs:
            with self.assertRaises(RuntimeError):
                d.handle_message("hello", "telegram_surface")
        receipts = [l for l in logs.output if "held_now_shadow" in l]
        self.assertEqual(len(receipts), 1)
        self.assertIn("final_reply_path=error", receipts[0])

    def test_no_receipt_when_flags_off(self):
        d = _bare_daemon()
        with mock.patch.object(
            MaezDaemon, "_handle_message_body", return_value="hi"
        ), mock.patch.dict(os.environ, _OFF):
            with self.assertNoLogs("maez", level="INFO"):
                d.handle_message("hello", "telegram_surface")

    def test_body_stash_reaches_the_receipt(self):
        d = _bare_daemon()

        def _body(self, text, source="unknown", **kw):
            holder = self._held_now_turn_state
            holder["final_reply_path"] = "focused"
            holder["turn_kind"] = "ordinary"
            holder["held_now_alloc"] = {
                "domain": "full_count", "reason": None, "pairs_rendered": 3,
            }
            holder["focused_row_id"] = "row-abc"
            return "ok"

        with mock.patch.object(
            MaezDaemon, "_handle_message_body", _body
        ), mock.patch.dict(os.environ, _SHADOW), self.assertLogs(
            "maez", level="INFO"
        ) as logs:
            d.handle_message("hello", "telegram_surface")
        receipt = next(l for l in logs.output if "held_now_shadow" in l)
        for token in (
            "final_reply_path=focused", "turn_kind=ordinary",
            "domain=full_count", "pairs_rendered=3",
            "focused_row_id=row-abc",
        ):
            self.assertIn(token, receipt)

    def test_receipt_never_breaks_the_turn(self):
        # Even if emission itself explodes, the reply still returns.
        d = _bare_daemon()
        with mock.patch.object(
            MaezDaemon, "_handle_message_body", return_value="hi"
        ), mock.patch.dict(os.environ, _SHADOW), mock.patch(
            "core.routing.focused_cognition.held_now_shadow_enabled",
            side_effect=RuntimeError("receipt plumbing broke"),
        ):
            reply = d.handle_message("hello", "telegram_surface")
        self.assertEqual(reply, "hi")


class CarrierSelectionTests(unittest.TestCase):
    def test_signature_accepts_held_now_history(self):
        import inspect

        params = inspect.signature(MaezDaemon._handle_message_body).parameters
        self.assertIn("held_now_history", params)
        self.assertIsNone(params["held_now_history"].default)


if __name__ == "__main__":
    unittest.main()
