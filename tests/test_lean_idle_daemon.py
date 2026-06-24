from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
import unittest


def _gate(
    *,
    floor: bool = True,
    reason: str = "wake_min_floor",
    signals=("min_floor_due",),
):
    from daemon.maez_daemon import _CycleDoormanGateDecision

    return _CycleDoormanGateDecision(
        doorman_enabled=True,
        wake=True,
        reason_code=reason,
        signals_present=signals,
        floor_wake=floor,
    )


class LeanIdleDaemonTest(unittest.TestCase):
    def test_eligibility_only_allows_quiet_floor_wake(self) -> None:
        from daemon.maez_daemon import _lean_idle_heartbeat_eligible

        self.assertTrue(_lean_idle_heartbeat_eligible(_gate()))
        self.assertFalse(
            _lean_idle_heartbeat_eligible(
                _gate(floor=False, reason="wake_new_failure", signals=("new_failure",))
            )
        )
        self.assertFalse(
            _lean_idle_heartbeat_eligible(
                _gate(
                    floor=True,
                    reason="wake_min_floor",
                    signals=("min_floor_due", "open_want"),
                )
            )
        )

    def test_flag_off_never_calls_runner(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 12
        daemon.private_thoughts = None
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch(
                "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat"
            ) as runner:
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertIsNone(result)
        runner.assert_not_called()

    def test_shadow_calls_runner_but_does_not_intercept(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 13
        daemon.private_thoughts = None
        daemon._lean_idle_self_card_text = lambda: "SELF CARD"
        daemon._lean_idle_private_signal_summary = lambda: {}
        fake_result = SimpleNamespace(
            intercepted=False,
            return_text=None,
            receipt={"mode": "shadow"},
        )
        with mock.patch.dict(
            "os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1"}, clear=True
        ):
            with mock.patch(
                "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                return_value=fake_result,
            ) as runner:
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertIsNone(result)
        runner.assert_called_once()

    def test_enabled_floor_wake_returns_heartbeat_ok(self) -> None:
        from daemon.maez_daemon import MaezDaemon, _HEARTBEAT_OK

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 14
        daemon.private_thoughts = object()
        daemon._lean_idle_self_card_text = lambda: "SELF CARD"
        daemon._lean_idle_private_signal_summary = lambda: {}
        fake_result = SimpleNamespace(
            intercepted=True,
            return_text=_HEARTBEAT_OK,
            receipt={"mode": "enabled"},
        )
        with mock.patch.dict(
            "os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1"}, clear=True
        ):
            with mock.patch(
                "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                return_value=fake_result,
            ):
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertEqual(result, _HEARTBEAT_OK)

    def test_non_floor_wake_does_not_intercept_even_when_enabled(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 15
        with mock.patch.dict(
            "os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "1"}, clear=True
        ):
            with mock.patch(
                "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat"
            ) as runner:
                result = daemon._maybe_run_lean_idle_heartbeat(
                    {},
                    _gate(floor=False, reason="wake_new_failure", signals=("new_failure",)),
                )

        self.assertIsNone(result)
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
