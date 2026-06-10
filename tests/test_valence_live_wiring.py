import inspect
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
os.environ.pop("MAEZ_SEMANTIC_AUDIT", None)

from core.safety import audit_flag_buffer, audited_output, self_claim_audit  # noqa: E402


class _FakeAuditResult:
    def __init__(self, text, flags=()):
        self.text = text
        self.flags = list(flags)
        self.rewritten = False
        self.mode = "noop"


class AuditedOutputValenceWiringTests(unittest.TestCase):
    def setUp(self):
        audit_flag_buffer.clear()

    def tearDown(self):
        audit_flag_buffer.clear()

    def test_audit_assistant_text_side_records_flag_kinds_after_audit(self):
        result = _FakeAuditResult(
            "audited text",
            flags=[
                SimpleNamespace(kind="completion_rail"),
                SimpleNamespace(kind="judge"),
            ],
        )

        with patch.object(self_claim_audit, "audit", return_value=result):
            returned = audited_output.audit_assistant_text(
                "raw text",
                surface="test",
                signals_present=[],
                signals_absent=[],
            )

        self.assertEqual(returned, "audited text")
        self.assertEqual(audit_flag_buffer.peek(), ["completion_rail", "judge"])

    def test_audit_assistant_text_returns_audited_text_when_side_record_raises(self):
        result = _FakeAuditResult(
            "audited text",
            flags=[SimpleNamespace(kind="completion_rail")],
        )

        with patch.object(self_claim_audit, "audit", return_value=result):
            with patch.object(audit_flag_buffer, "push", side_effect=RuntimeError("boom")):
                with self.assertLogs("maez.audited_output", level="WARNING"):
                    returned = audited_output.audit_assistant_text(
                        "raw text",
                        surface="test",
                        signals_present=[],
                        signals_absent=[],
                    )

        self.assertEqual(returned, "audited text")

    def test_shared_audit_flag_buffer_helper_records_direct_daemon_flags(self):
        audited_output._buffer_audit_flags(
            [
                SimpleNamespace(kind="completion_rail"),
                SimpleNamespace(kind="judge"),
            ]
        )

        self.assertEqual(audit_flag_buffer.peek(), ["completion_rail", "judge"])

    def test_shared_audit_flag_buffer_helper_warns_when_side_record_fails(self):
        with patch.object(audit_flag_buffer, "push", side_effect=RuntimeError("boom")):
            with self.assertLogs("maez.audited_output", level="WARNING") as logs:
                audited_output._buffer_audit_flags(
                    [SimpleNamespace(kind="completion_rail")]
                )

        self.assertIn("audit flag side-record failed", "\n".join(logs.output))


class DaemonValenceWiringTests(unittest.TestCase):
    def setUp(self):
        audit_flag_buffer.clear()

    def tearDown(self):
        audit_flag_buffer.clear()

    def test_cycle_valence_helper_clears_buffer_after_successful_read(self):
        from daemon import maez_daemon

        audit_flag_buffer.push("completion_rail")
        daemon = SimpleNamespace(
            _continuity_active=True,
            _continuity_capsule={"current_mode": "orientation"},
        )
        sentinel = object()

        with patch(
            "core.evolution.valence_live.read_and_log_valence",
            return_value=sentinel,
        ) as read:
            maez_daemon._read_and_log_cycle_valence(
                daemon,
                open_wants_count=3,
                now="2026-06-10T00:00:00+00:00",
            )

        read.assert_called_once_with(
            audit_flags=["completion_rail"],
            open_want_count=3,
            continuity_state={
                "capsule_expected": True,
                "capsule_present": True,
            },
            now="2026-06-10T00:00:00+00:00",
        )
        self.assertEqual(audit_flag_buffer.peek(), [])

    def test_cycle_valence_helper_keeps_buffer_when_read_returns_none(self):
        from daemon import maez_daemon

        audit_flag_buffer.push("judge")
        daemon = SimpleNamespace(_continuity_active=False, _continuity_capsule=None)

        with patch(
            "core.evolution.valence_live.read_and_log_valence",
            return_value=None,
        ):
            with patch.object(maez_daemon.logger, "debug"):
                maez_daemon._read_and_log_cycle_valence(
                    daemon,
                    open_wants_count=1,
                    now="2026-06-10T00:00:00+00:00",
                )

        self.assertEqual(audit_flag_buffer.peek(), ["judge"])

    def test_cycle_valence_helper_keeps_buffer_when_read_raises(self):
        from daemon import maez_daemon

        audit_flag_buffer.push("judge")
        daemon = SimpleNamespace(_continuity_active=True, _continuity_capsule=None)

        with patch(
            "core.evolution.valence_live.read_and_log_valence",
            side_effect=RuntimeError("boom"),
        ):
            with patch.object(maez_daemon.logger, "warning"):
                maez_daemon._read_and_log_cycle_valence(
                    daemon,
                    open_wants_count=1,
                    now="2026-06-10T00:00:00+00:00",
                )

        self.assertEqual(audit_flag_buffer.peek(), ["judge"])

    def test_open_wants_count_uses_uncapped_active_wants(self):
        from daemon import maez_daemon

        class Wants:
            def __init__(self):
                self.calls = []

            def active_wants(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return [object()] * 75

        wants = Wants()

        self.assertEqual(
            maez_daemon._count_cycle_open_wants(SimpleNamespace(wants=wants)),
            75,
        )
        self.assertEqual(wants.calls, [((), {})])

    def test_cycle_audit_flag_helper_records_direct_audit_result_flags(self):
        from daemon import maez_daemon

        maez_daemon._buffer_cycle_audit_flags(
            SimpleNamespace(
                flags=[
                    SimpleNamespace(kind="completion_rail"),
                    SimpleNamespace(kind="judge"),
                ]
            )
        )

        self.assertEqual(audit_flag_buffer.peek(), ["completion_rail", "judge"])

    def test_cycle_audit_flag_helper_swallows_buffering_failures(self):
        from daemon import maez_daemon

        with patch(
            "core.safety.audited_output._buffer_audit_flags",
            side_effect=RuntimeError("boom"),
        ):
            with patch.object(maez_daemon.logger, "warning"):
                maez_daemon._buffer_cycle_audit_flags(
                    SimpleNamespace(flags=[SimpleNamespace(kind="completion_rail")])
                )

        self.assertEqual(audit_flag_buffer.peek(), [])

    def test_direct_daemon_response_audit_buffers_flags_after_audit(self):
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon.MaezDaemon._loop)
        audit_idx = src.index("_audit_result = _sc_audit(")
        buffer_idx = src.index("_buffer_cycle_audit_flags(_audit_result", audit_idx)
        rewrite_idx = src.index("if _audit_result.rewritten:", audit_idx)

        self.assertLess(audit_idx, buffer_idx)
        self.assertLess(buffer_idx, rewrite_idx)

    def test_structural_wiring_valence_read_runs_after_post_cycle_surfaces(self):
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon.MaezDaemon._loop)
        followup_idx = src.index('self._mark_cycle_stage("followup_delivery")')
        opinion_idx = src.index("_check_proactive_opinion(")
        dream_idx = src.index('self._mark_cycle_stage("dream_check")')
        valence_idx = src.index("_read_and_log_cycle_valence(")
        sleep_idx = src.index('self._mark_cycle_stage("cycle_sleep")')

        self.assertLess(followup_idx, valence_idx)
        self.assertLess(opinion_idx, valence_idx)
        self.assertLess(dream_idx, valence_idx)
        self.assertLess(valence_idx, sleep_idx)


if __name__ == "__main__":
    unittest.main()
