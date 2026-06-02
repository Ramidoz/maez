from __future__ import annotations

import unittest

from core.cognition.cycle_doorman import DoormanSignals, ReasonCode, decide


def _quiet() -> DoormanSignals:
    return DoormanSignals(
        perception_changed=False,
        new_failures=0,
        open_wants=0,
        memory_delta=False,
        signal_availability_changed=False,
        scheduled_due=False,
        quiet_skips=0,
        min_floor=10,
        presence="active",
    )


class DoormanTest(unittest.TestCase):
    def test_every_salient_signal_wakes(self):
        for field, code in [
            ("perception_changed", ReasonCode.WAKE_PERCEPTION_CHANGED),
            ("memory_delta", ReasonCode.WAKE_MEMORY_DELTA),
            (
                "signal_availability_changed",
                ReasonCode.WAKE_SIGNAL_AVAILABILITY_CHANGED,
            ),
            ("scheduled_due", ReasonCode.WAKE_SCHEDULED),
        ]:
            with self.subTest(field=field):
                signals = _quiet()
                object.__setattr__(signals, field, True)
                verdict = decide(signals)
                self.assertTrue(verdict.wake, f"{field} must wake")
                self.assertEqual(verdict.reason_code, code)

        for field, code in [
            ("new_failures", ReasonCode.WAKE_NEW_FAILURE),
            ("open_wants", ReasonCode.WAKE_OPEN_WANT),
        ]:
            with self.subTest(field=field):
                signals = _quiet()
                object.__setattr__(signals, field, 1)
                verdict = decide(signals)
                self.assertTrue(verdict.wake, f"{field} must wake")
                self.assertEqual(verdict.reason_code, code)

    def test_fail_open_on_none_bundle(self):
        verdict = decide(None)
        self.assertTrue(verdict.wake)
        self.assertEqual(verdict.reason_code, ReasonCode.WAKE_FAIL_OPEN)

    def test_fail_open_on_malformed(self):
        verdict = decide(object())
        self.assertTrue(verdict.wake)
        self.assertEqual(verdict.reason_code, ReasonCode.WAKE_FAIL_OPEN)

    def test_fail_open_on_unusable_values(self):
        signals = _quiet()
        object.__setattr__(signals, "new_failures", object())

        verdict = decide(signals)

        self.assertTrue(verdict.wake)
        self.assertEqual(verdict.reason_code, ReasonCode.WAKE_FAIL_OPEN)

    def test_presence_absent_does_not_change_salient_wake(self):
        signals = _quiet()
        object.__setattr__(signals, "new_failures", 1)

        signals.presence = "active"
        active = decide(signals)
        signals.presence = "absent"
        absent = decide(signals)

        self.assertEqual((active.wake, active.reason_code), (absent.wake, absent.reason_code))

    def test_presence_alone_never_wakes(self):
        signals = _quiet()
        signals.presence = "absent"

        self.assertFalse(decide(signals).wake)

    def test_quiet_below_floor_skips(self):
        verdict = decide(_quiet())

        self.assertFalse(verdict.wake)
        self.assertEqual(verdict.reason_code, ReasonCode.SKIP_NOTHING_SALIENT)

    def test_floor_wakes_once_then_resets(self):
        signals = _quiet()
        object.__setattr__(signals, "quiet_skips", 10)

        verdict = decide(signals)

        self.assertTrue(verdict.wake)
        self.assertEqual(verdict.reason_code, ReasonCode.WAKE_MIN_FLOOR)

        next_signals = _quiet()
        object.__setattr__(next_signals, "quiet_skips", 0)
        self.assertFalse(decide(next_signals).wake)

    def test_steady_absence_does_not_repeat_wake(self):
        signals = _quiet()
        object.__setattr__(signals, "signal_availability_changed", False)

        self.assertFalse(decide(signals).wake)

    def test_signals_present_is_content_free_closed_tuple(self):
        signals = _quiet()
        object.__setattr__(signals, "new_failures", 2)

        verdict = decide(signals)

        self.assertEqual(verdict.signals_present, ("new_failure",))


if __name__ == "__main__":
    unittest.main()
