"""RED tests for the Track A.5 metacognitive loop-spiral watchdog."""

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_SRC = ROOT / "core" / "health" / "metacognitive_watchdog.py"
DAEMON_SRC = ROOT / "daemon" / "maez_daemon.py"


class MetacognitiveWatchdogDetectorTests(unittest.TestCase):
    def _watchdog(self, log_path: Path):
        from core.health.metacognitive_watchdog import (
            MetacognitiveWatchdog,
            WatchdogConfig,
        )

        config = WatchdogConfig(
            token_window_size=40,
            token_unique_ratio_threshold=0.2,
            repeated_ngram_size=5,
            repeated_ngram_ratio_threshold=0.5,
            action_window_size=12,
            action_max_cycle_length=3,
            action_repeat_threshold=3,
            scalar_window_size=5,
            scalar_variance_threshold=0.0001,
            scalar_consecutive_windows=2,
            velocity_window_size=5,
            velocity_min_seconds=5.0,
            velocity_max_seconds=60.0,
            velocity_consecutive_samples=3,
            log_path=log_path,
        )
        return MetacognitiveWatchdog(config=config)

    def test_token_repetition_triggers_halt_and_non_reconstructive_log(self):
        from core.health.metacognitive_watchdog import WatchdogHalt

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "watchdog_halts.jsonl"
            watchdog = self._watchdog(log_path)

            with self.assertRaises(WatchdogHalt) as cm:
                watchdog.observe_tokens(["alpha", "beta", "gamma", "delta", "epsilon"] * 10)

            self.assertEqual(cm.exception.detector, "token_repetition")
            row = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(row["detector"], "token_repetition")
            self.assertIn("unique_ratio", row["observed_metrics"])
            self.assertNotIn("alpha beta gamma", json.dumps(row))
            self.assertNotIn("repeated_ngram_signature", json.dumps(row))

    def test_action_loop_triggers_halt(self):
        from core.health.metacognitive_watchdog import WatchdogHalt

        with tempfile.TemporaryDirectory() as td:
            watchdog = self._watchdog(Path(td) / "watchdog_halts.jsonl")

            with self.assertRaises(WatchdogHalt) as cm:
                watchdog.observe_actions(["search", "read", "summarize"] * 4)

            self.assertEqual(cm.exception.detector, "action_loop")
            self.assertEqual(cm.exception.reason_code, "repeated_action_cycle")
            row = json.loads((Path(td) / "watchdog_halts.jsonl").read_text())
            self.assertNotIn("search", json.dumps(row))
            self.assertNotIn("sequence_signature", json.dumps(row))

    def test_drive_scalar_flatline_triggers_halt(self):
        from core.health.metacognitive_watchdog import WatchdogHalt

        with tempfile.TemporaryDirectory() as td:
            watchdog = self._watchdog(Path(td) / "watchdog_halts.jsonl")

            samples = [{"curiosity": 4.0, "caution": 6.0} for _ in range(10)]
            with self.assertRaises(WatchdogHalt) as cm:
                for sample in samples:
                    watchdog.observe_scalars(sample)

            self.assertEqual(cm.exception.detector, "drive_scalar_flatline")
            self.assertEqual(cm.exception.reason_code, "scalar_variance_flatline")

    def test_cycle_velocity_triggers_halt(self):
        from core.health.metacognitive_watchdog import WatchdogHalt

        with tempfile.TemporaryDirectory() as td:
            watchdog = self._watchdog(Path(td) / "watchdog_halts.jsonl")

            with self.assertRaises(WatchdogHalt) as cm:
                for duration in [1.0, 1.1, 1.2]:
                    watchdog.observe_cycle_duration(duration)

            self.assertEqual(cm.exception.detector, "cycle_velocity")
            self.assertEqual(cm.exception.reason_code, "cycle_duration_out_of_envelope")

    def test_normal_slow_reasoning_does_not_trigger(self):
        with tempfile.TemporaryDirectory() as td:
            watchdog = self._watchdog(Path(td) / "watchdog_halts.jsonl")

            watchdog.observe_tokens(
                "this is a long varied reasoning chain with distinct tokens "
                "about perception memory health and operator review".split()
            )
            watchdog.observe_actions(
                ["search", "read", "summarize", "reflect", "store_progress", "wait"]
            )
            for sample in [
                {"curiosity": 4.0, "caution": 6.0},
                {"curiosity": 4.3, "caution": 5.7},
                {"curiosity": 4.1, "caution": 6.1},
                {"curiosity": 4.5, "caution": 5.8},
                {"curiosity": 4.2, "caution": 6.2},
            ]:
                watchdog.observe_scalars(sample)
            for duration in [20.0, 24.0, 28.0, 22.0, 26.0]:
                watchdog.observe_cycle_duration(duration)

            self.assertFalse((Path(td) / "watchdog_halts.jsonl").exists())


class MetacognitiveWatchdogBoundaryTests(unittest.TestCase):
    def test_watchdog_module_has_no_mutation_imports_or_mutating_cognition_calls(self):
        tree = ast.parse(WATCHDOG_SRC.read_text(encoding="utf-8"))
        forbidden_import_roots = {
            "memory.memory_manager",
            "core.memory.memory_manager",
            "core.evolution.wants",
            "core.evolution.will_i",
            "core.evolution.wonderings",
            "core.evolution.soul_loader",
            "skills.evolution_engine",
        }
        forbidden_calls = {
            "self_critique",
            "get_behavior_policy",
            "write_soul_note",
            "check_proposal_trigger",
            "start_proposal_worker",
        }

        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)

        self.assertFalse(forbidden_import_roots & imports)
        self.assertFalse(forbidden_calls & calls)

    def test_daemon_exposes_safe_standby_without_ordinary_stop(self):
        src = DAEMON_SRC.read_text(encoding="utf-8")

        self.assertIn("_enter_watchdog_safe_standby", src)
        self.assertIn("_watchdog_health", src)
        self.assertIn('"safe_standby"', src)
        self.assertIn("watchdog_state", src)

        standby_start = src.index("def _enter_watchdog_safe_standby")
        standby_end = src.index("def ", standby_start + 1)
        standby_block = src[standby_start:standby_end]
        self.assertIn("operator_resume_required", standby_block)
        self.assertNotIn("self.stop(", standby_block)
        self.assertNotIn("continuity_shutdown()", standby_block)

    def test_daemon_samples_deferred_action_results_for_action_loop_detector(self):
        src = DAEMON_SRC.read_text(encoding="utf-8")

        action_start = src.index('self._mark_cycle_stage("deferred_actions")')
        action_end = src.index("# Session 11z Part 2", action_start)
        action_block = src[action_start:action_end]

        self.assertIn("execute_pending()", action_block)
        self.assertIn("execute_tier2_pending()", action_block)
        self.assertIn("observe_actions", action_block)
        self.assertIn("_enter_watchdog_safe_standby", action_block)

    def test_daemon_does_not_inject_watchdog_diagnostics_into_maez_context(self):
        src = DAEMON_SRC.read_text(encoding="utf-8")
        forbidden_fragments = [
            "watchdog_halts.jsonl",
            "halt_detector",
            "halt_reason_code",
            "watchdog diagnostic",
        ]
        reason_start = src.index("def _reason")
        reason_end = src.index("def handle_message", reason_start)
        reason_block = src[reason_start:reason_end]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, reason_block)


if __name__ == "__main__":
    unittest.main()
