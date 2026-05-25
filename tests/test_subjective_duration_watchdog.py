from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Iterable


class SubjectiveDurationWatchdogTests(unittest.TestCase):
    def _config(self, log_path: Path, *, scalar_allowlist: Iterable[str] | None | object = ...):
        from core.health.metacognitive_watchdog import WatchdogConfig

        kwargs = {}
        if scalar_allowlist is not ...:
            kwargs["scalar_allowlist"] = scalar_allowlist
        return WatchdogConfig(
            token_window_size=40,
            action_window_size=12,
            scalar_window_size=5,
            scalar_variance_threshold=0.0001,
            scalar_consecutive_windows=2,
            velocity_window_size=5,
            log_path=log_path,
            **kwargs,
        )

    def test_default_scalar_allowlist_ignores_subjective_duration(self):
        from core.evolution.temperament import PARAMETER_SET
        from core.health.metacognitive_watchdog import MetacognitiveWatchdog

        with tempfile.TemporaryDirectory() as td:
            config = self._config(Path(td) / "watchdog.jsonl")
            self.assertTrue(
                hasattr(config, "scalar_allowlist"),
                "WatchdogConfig must expose scalar_allowlist for drive-scalar filtering",
            )
            self.assertIsInstance(config.scalar_allowlist, frozenset)
            self.assertEqual(config.scalar_allowlist, PARAMETER_SET)
            self.assertNotIn("subjective_duration", config.scalar_allowlist)

            watchdog = MetacognitiveWatchdog(config=config)
            for _ in range(20):
                watchdog.observe_scalars({"subjective_duration": 4.0})

            self.assertFalse((Path(td) / "watchdog.jsonl").exists())

    def test_temperament_scalar_still_triggers_flatline(self):
        from core.health.metacognitive_watchdog import MetacognitiveWatchdog, WatchdogHalt

        with tempfile.TemporaryDirectory() as td:
            watchdog = MetacognitiveWatchdog(config=self._config(Path(td) / "watchdog.jsonl"))

            with self.assertRaises(WatchdogHalt) as cm:
                for _ in range(20):
                    watchdog.observe_scalars({"curiosity": 4.0})

            self.assertEqual(cm.exception.detector, "drive_scalar_flatline")

    def test_scalar_allowlist_none_preserves_legacy_all_scalar_behavior(self):
        from core.health.metacognitive_watchdog import MetacognitiveWatchdog, WatchdogHalt
        from core.health.metacognitive_watchdog import WatchdogConfig

        with tempfile.TemporaryDirectory() as td:
            self.assertIn(
                "scalar_allowlist",
                WatchdogConfig.__dataclass_fields__,
                "WatchdogConfig must accept scalar_allowlist=None for legacy all-scalar mode",
            )
            watchdog = MetacognitiveWatchdog(
                config=self._config(
                    Path(td) / "watchdog.jsonl",
                    scalar_allowlist=None,
                )
            )

            with self.assertRaises(WatchdogHalt) as cm:
                for _ in range(20):
                    watchdog.observe_scalars({"unreviewed_scalar": 4.0})

            self.assertEqual(cm.exception.detector, "drive_scalar_flatline")
            self.assertEqual(cm.exception.observed_metrics["scalar"], "unreviewed_scalar")

    def test_mixed_unknown_and_known_scalars_halts_on_known_curiosity_only(self):
        from core.health.metacognitive_watchdog import MetacognitiveWatchdog, WatchdogHalt

        with tempfile.TemporaryDirectory() as td:
            watchdog = MetacognitiveWatchdog(config=self._config(Path(td) / "watchdog.jsonl"))

            with self.assertRaises(WatchdogHalt) as cm:
                for _ in range(20):
                    watchdog.observe_scalars(
                        {
                            "subjective_duration": 4.0,
                            "curiosity": 4.0,
                        }
                    )

            self.assertEqual(cm.exception.detector, "drive_scalar_flatline")
            self.assertEqual(cm.exception.observed_metrics["scalar"], "curiosity")
            self.assertEqual(watchdog.health()["scalar_names"], ["curiosity"])

    def test_non_numeric_unknown_scalars_do_not_create_health_entries(self):
        from core.health.metacognitive_watchdog import MetacognitiveWatchdog

        with tempfile.TemporaryDirectory() as td:
            watchdog = MetacognitiveWatchdog(config=self._config(Path(td) / "watchdog.jsonl"))

            for _ in range(20):
                watchdog.observe_scalars(
                    {
                        "subjective_duration": "felt-long",
                        "unreviewed_scalar": object(),
                    }
                )

            self.assertEqual(watchdog.health()["scalar_names"], [])
            self.assertFalse((Path(td) / "watchdog.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
