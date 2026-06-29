from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _assert_absent(testcase: unittest.TestCase, needle: str, haystack: str, label: str) -> None:
    if needle in haystack:
        testcase.fail(f"{label} still contains {needle!r}")


DAEMON = _read("daemon/maez_daemon.py")
CONTINUITY = _read("core/memory/continuity.py")
MEMORY_MANAGER = _read("memory/memory_manager.py")
EVOLUTION_ENGINE = _read("skills/evolution_engine.py")
TELEGRAM_VOICE = _read("skills/telegram_voice.py")
SELF_CLAIM_AUDIT = _read("core/safety/self_claim_audit.py")
ERROR_CLASSIFIER = _read("core/learning/error_classifier.py")
ACTION_ENGINE = _read("core/actions/action_engine.py")
DREAM_STATE = _read("core/evolution/dream_state.py")


class SourcePathCutTest(unittest.TestCase):
    def test_daemon_does_not_import_cognition_quality(self) -> None:
        _assert_absent(self, "from core.cognition_quality import", DAEMON, "daemon")
        _assert_absent(self, "import core.cognition_quality", DAEMON, "daemon")

    def test_daemon_calls_no_cognition_quality_drivers(self) -> None:
        for call in (
            "cog_score_and_classify(",
            "cog_self_critique(",
            "cog_should_retry(",
            "cog_build_retry_prompt(",
            "cog_format_active_prompt(",
            "cog_check_consolidation(",
        ):
            _assert_absent(self, call, DAEMON, "daemon")

    def test_daemon_emits_no_cog_score_metadata(self) -> None:
        _assert_absent(self, "score_0_100", DAEMON, "daemon")
        _assert_absent(self, '"cog_score"', DAEMON, "daemon")
        _assert_absent(self, "_last_cog_metadata", DAEMON, "daemon")

    def test_continuity_does_not_read_cognition_quality(self) -> None:
        _assert_absent(self, "cognition_quality", CONTINUITY, "continuity")
        for symbol in ("get_behavior_policy", "_recent_scores", "_recent_labels", "_recent_topics"):
            _assert_absent(self, symbol, CONTINUITY, "continuity")

    def test_memory_manager_rerank_drops_cognition_quality_fixation_penalty(self) -> None:
        _assert_absent(self, "from core.cognition_quality import", MEMORY_MANAGER, "memory_manager")
        _assert_absent(self, "get_fixation_penalty", MEMORY_MANAGER, "memory_manager")

    def test_evolution_engine_does_not_target_or_read_cognition_quality(self) -> None:
        _assert_absent(self, "core/cognition_quality.py", EVOLUTION_ENGINE, "evolution_engine")
        _assert_absent(self, "from core.cognition_quality import", EVOLUTION_ENGINE, "evolution_engine")
        for symbol in ("_recent_scores", "_recent_labels", "_recent_topics", "get_behavior_policy"):
            _assert_absent(self, symbol, EVOLUTION_ENGINE, "evolution_engine")

    def test_telegram_analyze_does_not_read_live_cognition_scores(self) -> None:
        _assert_absent(self, "from core.cognition_quality import", TELEGRAM_VOICE, "telegram_voice")
        for symbol in ("_recent_scores", "_recent_labels", "_recent_topics", "get_behavior_policy"):
            _assert_absent(self, symbol, TELEGRAM_VOICE, "telegram_voice")

    def test_cognition_logger_bootstraps_do_not_import_cognition_quality(self) -> None:
        _assert_absent(
            self,
            "cognition_quality as _cog_quality_bootstrap",
            SELF_CLAIM_AUDIT,
            "self_claim_audit",
        )
        _assert_absent(
            self,
            "cognition_quality as _cog_quality_bootstrap",
            ERROR_CLASSIFIER,
            "error_classifier",
        )

    def test_neutral_topic_helper_not_reached_through_cognition_quality(self) -> None:
        _assert_absent(
            self,
            "from core.cognition_quality import primary_topic",
            DREAM_STATE,
            "dream_state",
        )

    def test_daemon_does_not_call_qualitytracker_self_shaping(self) -> None:
        _assert_absent(self, "self._quality_tracker.format_for_context(", DAEMON, "daemon")
        _assert_absent(self, "self._quality_tracker.format_insight_for_soul(", DAEMON, "daemon")

    def test_daemon_emits_no_quality_signal_candidate(self) -> None:
        _assert_absent(self, '"quality_signal"', DAEMON, "daemon")
        _assert_absent(self, "cycle_quality_signal", DAEMON, "daemon")

    def test_action_engine_keeps_qualitytracker_ledger(self) -> None:
        self.assertIn("_quality_tracker.record_proposed(", ACTION_ENGINE)
        self.assertIn("_quality_tracker.record_outcome(", ACTION_ENGINE)

    def test_daemon_keeps_followup_outcome_lookup(self) -> None:
        self.assertIn("get_outcome(", DAEMON)

    def test_fabrication_storage_gate_untouched(self) -> None:
        self.assertIn("HEARTBEAT_OK", DAEMON)
        self.assertRegex(DAEMON, r"fabricat")

    def test_doorman_anti_loop_is_still_present(self) -> None:
        self.assertIn("from core.cognition.cycle_doorman import", DAEMON)
        self.assertIn("_cycle_doorman_gate_decision", DAEMON)


class BehavioralCutTest(unittest.TestCase):
    def _snap(self) -> dict:
        return {
            "timestamp": "2026-06-29T00:00:00Z",
            "day_of_week": "Monday",
            "time_of_day": "morning",
            "cpu": {"percent": 1.0, "core_count": 8, "freq_mhz": 3200},
            "ram": {"used_gb": 1.0, "total_gb": 16.0, "percent": 6.0},
            "gpu": None,
            "disk": {},
            "network": {"send_rate_mbps": 0.0, "recv_rate_mbps": 0.0},
            "top_processes_cpu": [],
            "top_processes_mem": [],
        }

    def test_reason_prompt_contains_no_qualitytracker_reflection_block(self) -> None:
        from daemon.maez_daemon import MaezDaemon

        class Memory:
            def recall_for_cycle(self, _query):
                return {"core": [], "daily": [], "raw": []}

            def format_for_prompt(self, _recalled, max_chars=None):
                return ""

            def memory_stats(self):
                return {"raw": 0, "daily": 0, "core": 0}

        class Tracker:
            def format_for_context(self):
                return "[SELF-REFLECTION] Approval rate: 20%"

        @contextmanager
        def purpose(_name):
            yield

        daemon = object.__new__(MaezDaemon)
        daemon.cycle_count = 1
        daemon.system_prompt = "SOUL"
        daemon.memory = Memory()
        daemon._cycle_recall_context = {}
        daemon._last_screen_obs = None
        daemon._last_git_context = ""
        daemon._github_legacy_enabled = False
        daemon._last_github_block = None
        daemon._last_reddit_block = ""
        daemon._last_public_context = ""
        daemon._proactive_search_context = ""
        daemon._quality_tracker = Tracker()
        daemon._continuity_active = False
        daemon._continuity_capsule = None
        daemon._builder_audit_log = None
        daemon._builder_hwm = None
        daemon._builder_hwm_file = None
        daemon._cycle_feed_time_sense_line = lambda: ""
        daemon._s1b_note_residue_event = lambda *_args, **_kwargs: None

        captured: list[list[dict]] = []

        def fake_chat(*, model, messages, think, options):
            captured.append(messages)
            return SimpleNamespace(message=SimpleNamespace(content="HEARTBEAT_OK"))

        with mock.patch("daemon.maez_daemon._crc_capture", lambda *_args, **_kwargs: None), \
            mock.patch("daemon.maez_daemon._cycle_focused_enabled", return_value=False), \
            mock.patch("core.cognition.envelope_builder.build_envelope", return_value=None), \
            mock.patch("core.cognition.envelope_builder.render_envelope_for_prompt", return_value=""), \
            mock.patch("core.routing.brain_gateway.with_purpose", purpose), \
            mock.patch("core.llm_client.chat", fake_chat):
            result = daemon._reason(self._snap())

        self.assertEqual(result, "HEARTBEAT_OK")
        self.assertTrue(captured)
        prompt = captured[0][1]["content"]
        self.assertNotIn("[SELF-REFLECTION]", prompt)
        self.assertNotIn("Approval rate", prompt)

    def test_qualitytracker_ledger_still_records_outcome(self) -> None:
        from memory.quality_tracker import QualityTracker

        with tempfile.TemporaryDirectory() as td:
            tracker = QualityTracker(db_path=str(Path(td) / "quality.db"))
            tracker.record_proposed(
                "act-1",
                2,
                "write_file",
                "owner-approved action",
                {"path": "x"},
            )
            tracker.record_outcome("act-1", "approved", "ok")

            outcome = tracker.get_outcome("act-1")
            stats = tracker.get_stats(days=1)

        self.assertEqual(outcome["status"], "approved")
        self.assertEqual(stats["by_outcome"].get("approved"), 1)


if __name__ == "__main__":
    unittest.main()
