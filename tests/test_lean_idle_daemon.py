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
    def _daemon(self):
        from daemon.maez_daemon import MaezDaemon

        return object.__new__(MaezDaemon)

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

    def test_time_facts_adapter_is_content_light_and_omits_none(self) -> None:
        daemon = self._daemon()

        class Rhythm:
            def rhythm_context(self):
                return {
                    "rhythm_current_gap_s": 30,
                    "rhythm_recent_gap_median_s": None,
                    "rhythm_all_time_gap_median_s": 20,
                    "rhythm_current_gap_percentile_all_time": 5,
                }

        daemon._time_sense_handle = lambda: Rhythm()

        facts = daemon._lean_idle_time_facts()

        self.assertEqual(facts.get("owner_contact_gap_s"), 30)
        self.assertEqual(facts.get("all_time_usual_gap_s"), 20)
        self.assertNotIn("recent_usual_gap_s", facts)

    def test_body_state_adapter_uses_structured_health_keys(self) -> None:
        daemon = self._daemon()
        daemon._operator_health = lambda: {
            "mode": "degraded",
            "backup_freshness_class": "unavailable",
        }
        daemon._watchdog_health = lambda: {"watchdog_state": "observing"}

        state = daemon._lean_idle_body_state()

        self.assertEqual(
            state,
            {
                "daemon_overall": "degraded",
                "backup_freshness": "unavailable",
                "watchdog": "observing",
            },
        )

    def test_recent_private_thoughts_adapter_uses_flow_gate(self) -> None:
        daemon = self._daemon()

        class Store:
            def recent(self, limit=20):
                return [
                    {
                        "content": "kept",
                        "memory_phase": "gestation",
                        "context": {
                            "source": "lean_idle_heartbeat.v0",
                            "consent_tier": "owner_private",
                            "allowed_flows": ["private_reader"],
                        },
                    },
                    {
                        "content": "leaked?",
                        "memory_phase": "gestation",
                        "context": {
                            "source": "lean_idle_heartbeat.v0",
                            "consent_tier": "owner_private",
                            "allowed_flows": ["audit_trace"],
                        },
                    },
                ]

        daemon.private_thoughts = Store()

        self.assertEqual(daemon._lean_idle_recent_private_thoughts(), ("kept",))

    def test_open_loops_adapter_is_class_only(self) -> None:
        daemon = self._daemon()

        class Wants:
            def active_wants(self, limit=50):
                return [
                    {"statement": "I want to know current process uptime."},
                    {"statement": "I want this text kept out."},
                    {"statement": "I want no prose here."},
                ]

        daemon.wants = Wants()
        daemon._want_pursuit_card_store = lambda: None

        loops = daemon._lean_idle_open_loops()

        self.assertEqual(loops["open_loop_count"], 3)
        self.assertEqual(loops["open_loop_classes"], ["wants"])
        self.assertNotIn("statement", loops)
        self.assertNotIn("uptime", repr(loops))

    def test_open_loops_adapter_counts_terminal_proposals_class_only(self) -> None:
        daemon = self._daemon()

        class Wants:
            def active_wants(self, limit=50):
                return [{"statement": "want text must not surface"}]

        class Cards:
            def list_open_by_action(self, action):
                self.action = action
                return [object(), object()]

        cards = Cards()
        daemon.wants = Wants()
        daemon._want_pursuit_card_store = lambda: cards

        loops = daemon._lean_idle_open_loops()

        self.assertEqual(cards.action, "want_terminal_proposal")
        self.assertEqual(loops["open_loop_count"], 3)
        self.assertEqual(loops["open_loop_classes"], ["wants", "proposals"])
        self.assertNotIn("want text", repr(loops))

    def test_adapters_failsoft_to_empty(self) -> None:
        daemon = self._daemon()
        daemon._time_sense_handle = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        daemon._operator_health = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        daemon._watchdog_health = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        daemon.wants = None
        daemon.private_thoughts = None

        self.assertEqual(daemon._lean_idle_time_facts(), {})
        self.assertEqual(daemon._lean_idle_body_state(), {})
        self.assertEqual(daemon._lean_idle_open_loops(), {})
        self.assertEqual(daemon._lean_idle_recent_private_thoughts(), ())

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
        self.assertEqual(
            runner.call_args.kwargs["chat_fn"].__name__,
            "chat_direct",
        )

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

    def test_daemon_seam_keeps_non_floor_safety_wakes_legacy(self) -> None:
        from daemon.maez_daemon import _lean_idle_heartbeat_eligible

        for reason, signals in (
            ("wake_new_failure", ("new_failure",)),
            ("wake_open_want", ("open_want",)),
            ("wake_memory_delta", ("memory_delta",)),
            ("wake_scheduled", ("scheduled_due",)),
            ("wake_perception_changed", ("perception_changed",)),
        ):
            with self.subTest(reason=reason):
                self.assertFalse(
                    _lean_idle_heartbeat_eligible(
                        _gate(floor=False, reason=reason, signals=signals)
                    )
                )


if __name__ == "__main__":
    unittest.main()
