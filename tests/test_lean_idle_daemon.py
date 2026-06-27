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
            def recent_by_source(self, source, *, limit=2):
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

    def test_recent_private_thoughts_uses_source_scoped_reader(self) -> None:
        from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION

        daemon = self._daemon()
        seen = {}

        class Store:
            def recent_by_source(self, source, *, limit=2, **kw):
                seen["source"] = source
                seen["limit"] = limit
                return [
                    {
                        "content": "kept",
                        "memory_phase": "gestation",
                        "context": {
                            "source": source,
                            "consent_tier": "owner_private",
                            "allowed_flows": ["private_reader"],
                        },
                    }
                ]

            def recent(self, limit=20):
                seen["used_recent"] = True
                return []

        daemon.private_thoughts = Store()

        out = daemon._lean_idle_recent_private_thoughts()

        self.assertEqual(seen["source"], HEARTBEAT_VERSION)
        self.assertEqual(seen["limit"], 2)
        self.assertNotIn("used_recent", seen)
        self.assertEqual(out, ("kept",))

    def test_salience_broker_cold_start_then_change(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_broker_baseline = None
        window1 = {
            "time_facts": {"owner_contact_gap_s": 30, "gap_percentile_all_time": 40},
            "body_state": {},
            "open_loops": {},
            "recent_private_thoughts": (),
        }
        window2 = {
            "time_facts": {"owner_contact_gap_s": 999, "gap_percentile_all_time": 95},
            "body_state": {},
            "open_loops": {},
            "recent_private_thoughts": (),
        }

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=True
        ):
            first = daemon._maybe_run_salience_broker(window1)
            second = daemon._maybe_run_salience_broker(window2)

        self.assertTrue(first["cold_start"])
        self.assertEqual(first["proposal_count"], 0)
        self.assertFalse(second["cold_start"])
        self.assertEqual(
            second["proposals"],
            [{"fact_key": "time_facts", "change_kind": "changed"}],
        )

    def test_salience_broker_off_is_noop(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_broker_baseline = None

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": ""}, clear=True
        ):
            self.assertIsNone(daemon._maybe_run_salience_broker({"time_facts": {"x": 1}}))
        self.assertIsNone(daemon._salience_broker_baseline)

    def test_salience_ledger_resolves_over_two_pulses(self) -> None:
        import pathlib
        import tempfile
        from core.cognition.salience_ledger import SalienceLedger
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._salience_run_id = "r1000_42"
        daemon._salience_ledger = SalienceLedger(
            pathlib.Path(tempfile.mkdtemp()) / "salience.db"
        )
        props_n = [{"fact_key": "time_facts", "change_kind": "changed"}]

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False
        ):
            daemon._record_salience_outcomes(
                props_n,
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                },
                strategy="changed_since_last",
                pulse_signature="sig1",
                cold_start=False,
            )
            daemon._record_salience_outcomes(
                [],
                {"note_chars": 80, "stored": True, "skip_reason": "none"},
                strategy="changed_since_last",
                pulse_signature="sig2",
                cold_start=False,
            )

        rows = daemon._salience_ledger.recent(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pulse_id"], "r1000_42.seq1")
        self.assertEqual(rows[0]["strategy"], "changed_since_last")
        self.assertIn(rows[0]["arm"], ("proposed", "control_withheld"))
        self.assertEqual(rows[0]["fact_key"], "time_facts")
        self.assertEqual(rows[0]["change_kind"], "changed")
        self.assertTrue(rows[0]["non_duplicate_stored"])

    def test_salience_pulse_id_uses_process_run_namespace(self) -> None:
        import pathlib
        import tempfile
        from core.cognition.salience_ledger import SalienceLedger
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._salience_run_id = None
        daemon._salience_ledger = SalienceLedger(
            pathlib.Path(tempfile.mkdtemp()) / "salience.db"
        )

        with (
            mock.patch.dict(
                "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False
            ),
            mock.patch("daemon.maez_daemon.time.time", side_effect=[1.234, 9.999]),
            mock.patch("daemon.maez_daemon.os.getpid", side_effect=[42, 99]),
        ):
            pulse_id = daemon._record_salience_outcomes(
                [],
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                },
                strategy="changed_since_last",
                pulse_signature="sig-run",
                cold_start=False,
            )
            pulse_id_2 = daemon._record_salience_outcomes(
                [],
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                },
                strategy="changed_since_last",
                pulse_signature="sig-run-2",
                cold_start=False,
            )

        self.assertEqual(pulse_id, "r1234_42.seq1")
        self.assertEqual(pulse_id_2, "r1234_42.seq2")
        self.assertEqual(daemon._salience_pending["pulse_id"], "r1234_42.seq2")
        rows = daemon._salience_ledger.recent(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pulse_id"], "r1234_42.seq1")

    def test_quiet_pulse_records_control_none_baseline(self) -> None:
        import pathlib
        import tempfile
        from core.cognition.salience_ledger import SalienceLedger
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._salience_ledger = SalienceLedger(
            pathlib.Path(tempfile.mkdtemp()) / "salience.db"
        )

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False
        ):
            daemon._record_salience_outcomes(
                [],
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                },
                strategy="changed_since_last",
                pulse_signature="sigA",
                cold_start=False,
            )
            daemon._record_salience_outcomes(
                [],
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                },
                strategy="changed_since_last",
                pulse_signature="sigB",
                cold_start=False,
            )

        rows = daemon._salience_ledger.recent(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["arm"], "control_none")
        self.assertEqual(
            (rows[0]["fact_key"], rows[0]["change_kind"]), ("none", "none")
        )
        self.assertEqual(rows[0]["unmoved"], 1)

    def test_cold_start_pulse_records_cold_start_arm(self) -> None:
        import pathlib
        import tempfile
        from core.cognition.salience_ledger import SalienceLedger
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._salience_ledger = SalienceLedger(
            pathlib.Path(tempfile.mkdtemp()) / "salience.db"
        )
        heartbeat_ok = {
            "note_chars": 0,
            "stored": False,
            "skip_reason": "heartbeat_ok_or_rejected",
        }

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False
        ):
            daemon._record_salience_outcomes(
                [],
                heartbeat_ok,
                strategy="changed_since_last",
                pulse_signature="sigA",
                cold_start=True,
            )
            daemon._record_salience_outcomes(
                [],
                heartbeat_ok,
                strategy="changed_since_last",
                pulse_signature="sigB",
                cold_start=False,
            )

        rows = daemon._salience_ledger.recent(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["arm"], "cold_start")
        self.assertEqual(
            (rows[0]["fact_key"], rows[0]["change_kind"]), ("none", "none")
        )

    def test_arm_does_not_change_the_outcome(self) -> None:
        import pathlib
        import tempfile
        from core.cognition.salience_ledger import SalienceLedger
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._salience_ledger = SalienceLedger(
            pathlib.Path(tempfile.mkdtemp()) / "salience.db"
        )

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False
        ):
            daemon._record_salience_outcomes(
                [{"fact_key": "time_facts", "change_kind": "changed"}],
                {
                    "note_chars": 0,
                    "stored": False,
                    "skip_reason": "heartbeat_ok_or_rejected",
                },
                strategy="changed_since_last",
                pulse_signature="sig1",
                cold_start=False,
            )
            daemon._record_salience_outcomes(
                [],
                {"note_chars": 80, "stored": True, "skip_reason": "none"},
                strategy="changed_since_last",
                pulse_signature="sig2",
                cold_start=False,
            )

        row = daemon._salience_ledger.recent(limit=5)[0]
        self.assertIn(row["arm"], ("proposed", "control_withheld"))
        self.assertEqual(row["non_duplicate_stored"], 1)

    def test_salience_off_records_nothing(self) -> None:
        import pathlib
        import tempfile
        from core.cognition.salience_ledger import SalienceLedger
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._salience_ledger = SalienceLedger(
            pathlib.Path(tempfile.mkdtemp()) / "salience.db"
        )

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": ""}, clear=False
        ):
            result = daemon._record_salience_outcomes(
                [{"fact_key": "x", "change_kind": "changed"}],
                {"note_chars": 0},
                strategy="changed_since_last",
                pulse_signature="sig-off",
                cold_start=False,
            )

        self.assertIsNone(result)
        self.assertEqual(daemon._salience_ledger.recent(), [])

    def test_salience_ledger_failure_is_failsoft_and_advances_pending(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon._salience_pending = {
            "pulse_id": "seq1",
            "strategy": "changed_since_last",
            "arm": "proposed",
            "rows": [{"fact_key": "time_facts", "change_kind": "changed"}],
            "outcome": {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok"},
        }
        daemon._salience_pulse_seq = 1
        daemon._salience_run_id = "r1000_42"

        class BrokenLedger:
            def record(self, **kwargs):
                raise OSError("locked")

        daemon._salience_ledger = BrokenLedger()

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=False
        ):
            pulse_id = daemon._record_salience_outcomes(
                [{"fact_key": "body_state", "change_kind": "changed"}],
                {"note_chars": 0, "stored": False, "skip_reason": "heartbeat_ok"},
                strategy="changed_since_last",
                pulse_signature="sig3",
                cold_start=False,
            )

        self.assertEqual(pulse_id, "r1000_42.seq2")
        self.assertEqual(daemon._salience_pending["pulse_id"], "r1000_42.seq2")
        self.assertEqual(daemon._salience_pending["rows"][0]["fact_key"], "body_state")

    def test_salience_broker_only_records_blank_heartbeat_outcome(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 1
        daemon._salience_broker_baseline = None
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._lean_idle_time_facts = lambda: {"owner_contact_gap_s": 1}
        daemon._lean_idle_body_state = lambda: {}
        daemon._lean_idle_open_loops = lambda: {}
        daemon._lean_idle_recent_private_thoughts = lambda: ()
        captured = {}
        daemon._record_salience_outcomes = (
            lambda proposals, heartbeat, *, strategy, pulse_signature, cold_start: captured.update(
                {
                    "proposals": proposals,
                    "heartbeat": heartbeat,
                    "strategy": strategy,
                    "pulse_signature": pulse_signature,
                    "cold_start": cold_start,
                }
            )
        )

        with mock.patch.dict(
            "os.environ", {"MAEZ_SALIENCE_BROKER_SHADOW": "1"}, clear=True
        ):
            self.assertIsNone(daemon._maybe_run_lean_idle_heartbeat({}, _gate()))

        self.assertEqual(captured["proposals"], [])
        self.assertEqual(captured["strategy"], "changed_since_last")
        self.assertIn("pulse_signature", captured)
        self.assertTrue(captured["cold_start"])
        self.assertEqual(
            captured["heartbeat"],
            {
                "note_chars": 0,
                "stored": False,
                "skip_reason": "heartbeat_ok_or_rejected",
            },
        )

    def test_salience_resolution_survives_heartbeat_error(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 1
        daemon.private_thoughts = None
        daemon._salience_broker_baseline = {"time_facts": "old"}
        daemon._salience_pending = None
        daemon._salience_pulse_seq = 0
        daemon._lean_idle_self_card_text = lambda: "SELF"
        daemon._lean_idle_private_signal_summary = lambda: {}
        daemon._lean_idle_time_facts = lambda: {"owner_contact_gap_s": 2}
        daemon._lean_idle_body_state = lambda: {}
        daemon._lean_idle_open_loops = lambda: {}
        daemon._lean_idle_recent_private_thoughts = lambda: ()
        captured = {}
        daemon._record_salience_outcomes = (
            lambda proposals, heartbeat, *, strategy, pulse_signature, cold_start: captured.update(
                {
                    "proposals": proposals,
                    "heartbeat": heartbeat,
                    "strategy": strategy,
                    "pulse_signature": pulse_signature,
                    "cold_start": cold_start,
                }
            )
        )

        with mock.patch.dict(
            "os.environ",
            {
                "MAEZ_SALIENCE_BROKER_SHADOW": "1",
                "MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1",
            },
            clear=True,
        ):
            with mock.patch(
                "core.cognition.lean_idle_heartbeat.run_lean_idle_heartbeat",
                side_effect=RuntimeError("boom"),
            ):
                result = daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertIsNone(result)
        self.assertEqual(
            captured["proposals"],
            [{"fact_key": "time_facts", "change_kind": "changed"}],
        )
        self.assertEqual(captured["heartbeat"]["skip_reason"], "error")
        self.assertFalse(captured["heartbeat"]["stored"])
        self.assertIn("pulse_signature", captured)
        self.assertFalse(captured["cold_start"])

    def test_heartbeat_path_default_off_keeps_broker_and_adapters_asleep(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        touched = {"count": 0}

        def touch(*args, **kwargs):
            touched["count"] += 1
            return {}

        for name in (
            "_lean_idle_time_facts",
            "_lean_idle_body_state",
            "_lean_idle_open_loops",
            "_lean_idle_recent_private_thoughts",
            "_maybe_run_salience_broker",
        ):
            setattr(daemon, name, touch)

        with mock.patch.dict(
            "os.environ",
            {
                "MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "",
                "MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED": "",
                "MAEZ_SALIENCE_BROKER_SHADOW": "",
            },
            clear=True,
        ):
            self.assertIsNone(daemon._maybe_run_lean_idle_heartbeat({}, _gate()))
        self.assertEqual(touched["count"], 0)

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

    def test_default_off_reads_no_enrichment_seams(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        calls = {"n": 0}

        def tick(*args, **kwargs):
            calls["n"] += 1
            return {}

        daemon._lean_idle_time_facts = tick
        daemon._lean_idle_body_state = tick
        daemon._lean_idle_open_loops = tick
        daemon._lean_idle_recent_private_thoughts = tick

        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(daemon._maybe_run_lean_idle_heartbeat({}, _gate()))

        self.assertEqual(calls["n"], 0)

    def test_enriched_facts_threaded_into_heartbeat(self) -> None:
        from daemon.maez_daemon import MaezDaemon
        import core.cognition.lean_idle_heartbeat as lih

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 7
        daemon.private_thoughts = None
        daemon._lean_idle_self_card_text = lambda: "SELF"
        daemon._lean_idle_private_signal_summary = lambda: {}
        daemon._lean_idle_time_facts = lambda: {"owner_contact_gap_s": 3600}
        daemon._lean_idle_body_state = lambda: {"watchdog": "ok"}
        daemon._lean_idle_open_loops = lambda: {
            "open_loop_count": 2,
            "open_loop_classes": ["wants"],
        }
        daemon._lean_idle_recent_private_thoughts = lambda: ("a prior thought",)
        captured = {}

        def capture(*, facts, **kwargs):
            captured["facts"] = facts
            return lih.LeanIdleResult(False, False, None, None, "shadow_only", {})

        with mock.patch.dict(
            "os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1"}, clear=True
        ):
            with mock.patch.object(lih, "run_lean_idle_heartbeat", capture):
                daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        facts = captured["facts"]
        self.assertEqual(facts.time_facts, {"owner_contact_gap_s": 3600})
        self.assertEqual(facts.body_state, {"watchdog": "ok"})
        self.assertEqual(facts.open_loops["open_loop_count"], 2)
        self.assertEqual(facts.recent_private_thoughts, ("a prior thought",))

    def test_heartbeat_shadow_without_broker_leaves_broker_baseline_untouched(self) -> None:
        from daemon.maez_daemon import MaezDaemon
        import core.cognition.lean_idle_heartbeat as lih

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 8
        daemon.private_thoughts = None
        daemon._salience_broker_baseline = None
        daemon._lean_idle_self_card_text = lambda: "SELF"
        daemon._lean_idle_private_signal_summary = lambda: {}
        daemon._lean_idle_time_facts = lambda: {"owner_contact_gap_s": 60}
        daemon._lean_idle_body_state = lambda: {"watchdog": "ok"}
        daemon._lean_idle_open_loops = lambda: {}
        daemon._lean_idle_recent_private_thoughts = lambda: ()

        def capture(*, facts, **kwargs):
            return lih.LeanIdleResult(False, False, None, None, "shadow_only", {})

        with mock.patch.dict(
            "os.environ", {"MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW": "1"}, clear=True
        ):
            with mock.patch.object(lih, "run_lean_idle_heartbeat", capture):
                daemon._maybe_run_lean_idle_heartbeat({}, _gate())

        self.assertIsNone(daemon._salience_broker_baseline)

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
