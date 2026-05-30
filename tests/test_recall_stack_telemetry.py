import logging
import unittest

from core.routing.reply_mode import ReplyMode
from core.routing.recall_stack_config import resolve_recall_stack
from daemon.maez_daemon import log_recall_stack_posture


class RecallStackTelemetryTest(unittest.TestCase):
    def test_startup_line_shows_all_inputs_including_unset(self):
        env = {"MAEZ_DISPATCHER_ENABLED": "1"}

        with self.assertLogs("maez", level="INFO") as cap:
            log_recall_stack_posture(env=env)

        joined = "\n".join(cap.output)
        self.assertIn("recall_stack", joined)
        self.assertIn("mode=legacy", joined)
        self.assertIn("bundle=unset", joined)
        self.assertIn("dispatcher=set", joined)
        self.assertIn("focused=unset", joined)
        self.assertIn("living=unset", joined)

    def test_ignored_raw_flags_warn(self):
        env = {"MAEZ_DISPATCHER_ENABLED": "1"}

        with self.assertLogs("maez", level="WARNING") as cap:
            log_recall_stack_posture(env=env)

        self.assertTrue(
            any("legacy_raw_flags_ignored" in line for line in cap.output)
        )

    def test_bundle_on_no_warn(self):
        env = {"MAEZ_RECALL_TRIAD_ENABLED": "1"}

        with self.assertLogs("maez", level="INFO") as cap:
            log_recall_stack_posture(env=env)

        self.assertFalse(
            any(record.levelno >= logging.WARNING for record in cap.records)
        )

    def test_dated_denial_log_records_turn_receipt(self):
        from daemon.maez_daemon import _log_dated_recall_denial

        cfg = resolve_recall_stack(env={"MAEZ_RECALL_TRIAD_ENABLED": "1"})

        with self.assertLogs("maez", level="INFO") as cap:
            _log_dated_recall_denial(
                source="telegram_surface",
                reply_mode=ReplyMode.FOCUSED,
                recall_stack_config=cfg,
                date_addressed=True,
                carrier_receipt="consult_failed",
                had_confirmed=False,
                reply_kind="carrier_unavailable",
            )

        joined = "\n".join(cap.output)
        self.assertIn("dated_recall_denial", joined)
        self.assertIn("source=telegram_surface", joined)
        self.assertIn("reply_mode=FOCUSED", joined)
        self.assertIn("recall_stack_mode=recall_triad", joined)
        self.assertIn("carrier_receipt=consult_failed", joined)
        self.assertIn("reply_kind=carrier_unavailable", joined)


if __name__ == "__main__":
    unittest.main()
