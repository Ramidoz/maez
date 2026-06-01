import unittest

from tools.probes import brain_gateway_forced_collision_probe as probe


class ProbeSummaryTest(unittest.TestCase):
    def test_summary_detects_successful_preempt(self):
        events = [
            {
                "event": "brain_gateway_preempt_probe",
                "purpose": "owner_recall",
                "current_purpose": "daemon_cycle_generation",
                "handle_state": "present",
                "wait_ms": 4.0,
                "preempt_attempts": 1,
            },
            {
                "event": "brain_gateway_event",
                "purpose": "daemon_cycle_generation",
                "wait_ms": 1250.0,
                "preempted": True,
                "preempt_timeout": False,
            },
            {
                "event": "brain_gateway_event",
                "purpose": "owner_recall",
                "wait_ms": 1300.0,
                "preempted": False,
                "preempt_timeout": False,
            },
        ]

        summary = probe.summarize_events(events, foreground_wall_ms=5200.0)

        self.assertTrue(summary["handle_present"])
        self.assertTrue(summary["background_preempted"])
        self.assertFalse(summary["preempt_timeout"])
        self.assertEqual(summary["owner_wait_ms"], 1300.0)
        self.assertTrue(summary["slot_release_pass"])

    def test_summary_fails_on_missing_handle_or_slow_wait(self):
        events = [
            {
                "event": "brain_gateway_preempt_probe",
                "purpose": "owner_recall",
                "current_purpose": "daemon_cycle_generation",
                "handle_state": "missing",
                "wait_ms": 4.0,
                "preempt_attempts": 1,
            },
            {
                "event": "brain_gateway_event",
                "purpose": "owner_recall",
                "wait_ms": 2200.0,
                "preempted": False,
                "preempt_timeout": False,
            },
        ]

        summary = probe.summarize_events(events, foreground_wall_ms=7000.0)

        self.assertFalse(summary["handle_present"])
        self.assertFalse(summary["background_preempted"])
        self.assertFalse(summary["preempt_timeout"])
        self.assertEqual(summary["owner_wait_ms"], 2200.0)
        self.assertFalse(summary["slot_release_pass"])


if __name__ == "__main__":
    unittest.main()
