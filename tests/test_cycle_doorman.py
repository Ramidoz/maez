from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.cognition.cycle_doorman import (
    DoormanSignals,
    DoormanVerdict,
    ReasonCode,
    decide,
    salient_perception_changed,
)


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

    def test_salient_perception_ignores_system_metric_drift(self):
        previous = {
            "screen_state": "disabled",
            "screen_activity": "unknown",
            "signal_availability": "screen=absent|camera=absent",
            "disk": 70.1,
            "procs": ("python", "llama-server"),
            "git": 0,
            "timestamp": 123.0,
        }
        current = {
            "screen_state": "disabled",
            "screen_activity": "unknown",
            "signal_availability": "screen=absent|camera=absent",
            "disk": 70.6,
            "procs": ("python", "llama-server", "bash"),
            "git": 2,
            "timestamp": 456.0,
        }

        self.assertFalse(salient_perception_changed(previous, current))

    def test_salient_perception_wakes_on_screen_activity_change(self):
        previous = {
            "screen_state": "ok",
            "screen_activity": "editing code",
            "signal_availability": "screen=available|camera=absent",
        }
        current = {
            "screen_state": "ok",
            "screen_activity": "reviewing test output",
            "signal_availability": "screen=available|camera=absent",
        }

        self.assertTrue(salient_perception_changed(previous, current))

    def test_salient_perception_wakes_on_signal_availability_transition(self):
        previous = {
            "screen_state": "unavailable",
            "screen_activity": "unknown",
            "signal_availability": "screen=absent|camera=absent",
        }
        current = {
            "screen_state": "ok",
            "screen_activity": "unknown",
            "signal_availability": "screen=available|camera=absent",
        }

        self.assertTrue(salient_perception_changed(previous, current))

    def test_salient_perception_fail_opens_on_missing_or_malformed_state(self):
        current = {
            "screen_state": "disabled",
            "screen_activity": "unknown",
            "signal_availability": "screen=absent|camera=absent",
        }

        self.assertTrue(salient_perception_changed(None, current))
        self.assertTrue(salient_perception_changed(object(), current))


class DoormanDaemonSeamTest(unittest.TestCase):
    def test_flag_off_uses_legacy_signature_gate(self):
        from daemon.maez_daemon import _cycle_doorman_gate_decision

        quiet = _quiet()

        skip = _cycle_doorman_gate_decision(
            doorman_enabled=False,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=5,
            min_floor=10,
            signals=quiet,
        )
        wake = _cycle_doorman_gate_decision(
            doorman_enabled=False,
            current_signature="B",
            last_thought_signature="A",
            quiet_skips=5,
            min_floor=10,
            signals=quiet,
        )

        self.assertFalse(skip.wake)
        self.assertTrue(skip.legacy_skip)
        self.assertIsNone(skip.verdict)
        self.assertTrue(wake.wake)
        self.assertFalse(wake.legacy_skip)
        self.assertIsNone(wake.verdict)

    def test_flag_on_doorman_skip_blocks_deep_call(self):
        from daemon.maez_daemon import _cycle_doorman_gate_decision

        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=0,
            min_floor=10,
            signals=_quiet(),
        )

        self.assertFalse(gate.wake)
        self.assertFalse(gate.should_call_deep_brain)
        self.assertFalse(gate.legacy_skip)
        self.assertEqual(gate.reason_code, ReasonCode.SKIP_NOTHING_SALIENT.value)

    def test_flag_on_fail_open_wakes(self):
        from daemon.maez_daemon import _cycle_doorman_gate_decision

        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=0,
            min_floor=10,
            signals=None,
        )

        self.assertTrue(gate.wake)
        self.assertTrue(gate.should_call_deep_brain)
        self.assertEqual(gate.reason_code, ReasonCode.WAKE_FAIL_OPEN.value)

    def test_doorman_verdict_summary_is_content_free(self):
        from daemon.maez_daemon import _cycle_doorman_verdict_summary

        summary = _cycle_doorman_verdict_summary(
            DoormanVerdict(
                wake=True,
                reason_code=ReasonCode.WAKE_NEW_FAILURE,
                signals_present=("new_failure",),
            ),
            quiet_skips=3,
        )

        self.assertEqual(
            set(summary),
            {"wake", "reason_code", "signals_present", "quiet_skips"},
        )
        self.assertEqual(summary["reason_code"], "wake_new_failure")
        self.assertNotIn("SECRET", str(summary))

    def test_doorman_skip_summary_is_content_free(self):
        from daemon.maez_daemon import _cycle_doorman_gate_decision, _cycle_doorman_skip_summary

        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=0,
            min_floor=10,
            signals=_quiet(),
        )

        summary = _cycle_doorman_skip_summary(gate, quiet_skips=4)

        self.assertEqual(
            set(summary),
            {"reason_code", "signals_present", "quiet_skips"},
        )
        self.assertEqual(summary["reason_code"], "skip_nothing_salient")
        self.assertNotIn("SECRET", str(summary))

    def test_floor_wake_heartbeat_resets_counter_instead_of_latching(self):
        from daemon.maez_daemon import (
            _HEARTBEAT_OK,
            _cycle_doorman_gate_decision,
            _cycle_next_quiet_skips,
        )

        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=10,
            min_floor=10,
            signals=DoormanSignals(
                perception_changed=False,
                new_failures=0,
                open_wants=0,
                memory_delta=False,
                signal_availability_changed=False,
                scheduled_due=False,
                quiet_skips=10,
                min_floor=10,
                presence="active",
            ),
        )
        self.assertTrue(gate.floor_wake)

        self.assertEqual(
            _cycle_next_quiet_skips(
                gate_decision=gate,
                current_quiet_skips=10,
                result=_HEARTBEAT_OK,
            ),
            0,
        )

    def test_doorman_skip_increments_quiet_counter(self):
        from daemon.maez_daemon import _cycle_doorman_gate_decision, _cycle_next_quiet_skips

        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=3,
            min_floor=10,
            signals=_quiet(),
        )

        self.assertEqual(
            _cycle_next_quiet_skips(
                gate_decision=gate,
                current_quiet_skips=3,
                result=None,
            ),
            4,
        )

    def test_live_counter_field_resets_after_doorman_wake_heartbeat(self):
        from daemon.maez_daemon import (
            _HEARTBEAT_OK,
            _cycle_apply_quiet_counter_result,
            _cycle_doorman_gate_decision,
        )

        daemon = SimpleNamespace(_cycles_since_last_thought=10)
        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=10,
            min_floor=10,
            signals=DoormanSignals(
                perception_changed=False,
                new_failures=0,
                open_wants=0,
                memory_delta=False,
                signal_availability_changed=False,
                scheduled_due=False,
                quiet_skips=10,
                min_floor=10,
                presence="active",
            ),
        )

        _cycle_apply_quiet_counter_result(
            daemon,
            gate_decision=gate,
            result=_HEARTBEAT_OK,
        )

        self.assertEqual(daemon._cycles_since_last_thought, 0)

    def test_live_counter_field_increments_after_doorman_skip(self):
        from daemon.maez_daemon import (
            _cycle_apply_quiet_counter_result,
            _cycle_doorman_gate_decision,
        )

        daemon = SimpleNamespace(_cycles_since_last_thought=3)
        gate = _cycle_doorman_gate_decision(
            doorman_enabled=True,
            current_signature="A",
            last_thought_signature="A",
            quiet_skips=3,
            min_floor=10,
            signals=_quiet(),
        )

        _cycle_apply_quiet_counter_result(
            daemon,
            gate_decision=gate,
            result=None,
        )

        self.assertEqual(daemon._cycles_since_last_thought, 4)

    def test_live_counter_field_preserves_legacy_heartbeat_increment_flag_off(self):
        from daemon.maez_daemon import (
            _HEARTBEAT_OK,
            _cycle_apply_quiet_counter_result,
            _cycle_doorman_gate_decision,
        )

        daemon = SimpleNamespace(_cycles_since_last_thought=3)
        gate = _cycle_doorman_gate_decision(
            doorman_enabled=False,
            current_signature="B",
            last_thought_signature="A",
            quiet_skips=3,
            min_floor=10,
            signals=_quiet(),
        )

        _cycle_apply_quiet_counter_result(
            daemon,
            gate_decision=gate,
            result=_HEARTBEAT_OK,
        )

        self.assertEqual(daemon._cycles_since_last_thought, 4)

    def test_action_failure_count_is_content_free_count(self):
        from daemon.maez_daemon import _cycle_action_failure_count

        results = [
            SimpleNamespace(success=False),
            SimpleNamespace(status="failed"),
            SimpleNamespace(outcome="approved_and_failed"),
            SimpleNamespace(success=True, status="done"),
        ]

        self.assertEqual(_cycle_action_failure_count(results), 3)

    def test_signal_availability_change_is_transition_not_steady_absence(self):
        from daemon.maez_daemon import (
            _cycle_signal_availability_changed,
            _cycle_signal_availability_key,
        )

        absent = _cycle_signal_availability_key(
            screen_obs=SimpleNamespace(success=False),
            camera_state=SimpleNamespace(sensor_state="unavailable"),
        )
        still_absent = _cycle_signal_availability_key(
            screen_obs=SimpleNamespace(success=False),
            camera_state=SimpleNamespace(sensor_state="unavailable"),
        )
        present = _cycle_signal_availability_key(
            screen_obs=SimpleNamespace(success=True),
            camera_state=SimpleNamespace(sensor_state="available"),
        )

        self.assertFalse(_cycle_signal_availability_changed(absent, still_absent))
        self.assertTrue(_cycle_signal_availability_changed(absent, present))

    def test_doorman_perception_delta_ignores_presence_axis(self):
        from daemon.maez_daemon import _cycle_doorman_signals

        current_axes = {
            "disk": 70,
            "presence": "absent",
            "git": 0,
            "procs": ("python",),
        }
        last_axes = {
            "disk": 70,
            "presence": "active",
            "git": 0,
            "procs": ("python",),
        }

        signals = _cycle_doorman_signals(
            current_axes=current_axes,
            last_thought_axes=last_axes,
            quiet_skips=0,
            min_floor=10,
            new_failures=0,
            open_wants=0,
            memory_delta=False,
            signal_availability_changed=False,
            scheduled_due=False,
            presence="absent",
        )

        self.assertFalse(signals.perception_changed)
        self.assertFalse(decide(signals).wake)


if __name__ == "__main__":
    unittest.main()
