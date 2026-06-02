from __future__ import annotations

import json
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _read(path: str) -> str:
    return (_REPO / path).read_text(encoding="utf-8")


def _method_body(src: str, method_name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(method_name)}\(", re.MULTILINE)
    match = pattern.search(src)
    if match is None:
        raise AssertionError(f"method not found: {method_name}")
    start = match.start()
    next_method = re.search(r"^    def \w+\(", src[start + 1 :], re.MULTILINE)
    end = start + 1 + next_method.start() if next_method else len(src)
    return src[start:end]


class _CountingEpisodes:
    def counts_by_status_and_source_kind(self):
        return {
            "total": 4,
            "active": 3,
            "superseded": 1,
            "reflection": 2,
            "by_status": {"active": 3, "superseded": 1},
            "by_source_kind": {"core_memory": 1, "reflection": 2, "followup_doc": 1},
        }


class BodyHealthProjectionTests(unittest.TestCase):
    def test_body_health_reports_organs_without_content(self):
        import daemon.maez_daemon as md

        daemon = SimpleNamespace(
            boot_time="2026-06-02T16:03:00+00:00",
            cycle_count=42,
            lived_episodes=_CountingEpisodes(),
            dream=object(),
        )
        env = {
            "MAEZ_CYCLE_DOORMAN_ENABLED": "1",
            "MAEZ_CYCLE_FOCUSED_ENABLED": "1",
            "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
            "MAEZ_REFLECTION_SYNTHESIS_WRITE": "1",
            "MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS": "1",
            "MAEZ_RECALL_TRIAD_ENABLED": "0",
        }

        with mock.patch.dict(os.environ, env, clear=True), mock.patch(
            "daemon.maez_daemon.served_model_alias", return_value="qwen36-27b"
        ):
            body = md.MaezDaemon._body_health(
                daemon,
                camera_presence={
                    "mode": "observe",
                    "sensor_state": "available",
                    "presence_state": "present",
                    "confidence_bucket": "high",
                    "enabled_until": "2026-06-03T12:00:00-05:00",
                    "last_observed_at": "2026-06-02T16:06:00-05:00",
                },
                memory_stats={"raw": 10, "daily": 2, "core": 5, "total": 17},
                reasoning_loop={
                    "stage": "self_reflection",
                    "cycle_age_seconds": 7,
                    "stage_age_seconds": 2,
                    "cycle_stalled": False,
                },
                system={
                    "cpu_percent": 12.5,
                    "ram_percent": 44.0,
                    "gpu_percent": 30,
                    "gpu_temp_c": 55,
                },
            )

        self.assertEqual(
            set(body),
            {
                "schema_version",
                "eyes",
                "memory",
                "brain",
                "body",
                "heartbeat",
                "attention",
                "cycle_mind",
                "stomach",
                "dreaming",
                "recall",
                "covenant_perimeter",
            },
        )
        self.assertEqual(body["schema_version"], "maez_body.v0")
        self.assertEqual(body["eyes"]["presence_state"], "present")
        self.assertEqual(body["memory"]["reflection"], 2)
        self.assertEqual(body["memory"]["episodes_active"], 3)
        self.assertEqual(body["memory"]["episodes_superseded"], 1)
        self.assertEqual(body["brain"]["configured_model"], md.MODEL)
        self.assertEqual(body["brain"]["served_model_alias"], "qwen36-27b")
        self.assertTrue(body["attention"]["enabled"])
        self.assertTrue(body["cycle_mind"]["enabled"])
        self.assertEqual(body["stomach"]["max_reflections"], 1)
        self.assertFalse(body["recall"]["enabled"])
        self.assertEqual(body["recall"]["mode"], "legacy")
        self.assertFalse(body["covenant_perimeter"]["screen_vision_enabled"])
        self.assertTrue(body["covenant_perimeter"]["never_delete_memory"])
        encoded = json.dumps(body, sort_keys=True)
        self.assertNotIn("private reflection text", encoded)
        self.assertNotIn("ep-", encoded)
        self.assertNotIn("source_memory_ids", encoded)
        self.assertNotIn("summary", encoded)

    def test_body_health_fails_closed_to_unknown_counts(self):
        import daemon.maez_daemon as md

        class BrokenEpisodes:
            def counts_by_status_and_source_kind(self):
                raise RuntimeError("private db unavailable")

        daemon = SimpleNamespace(cycle_count=1, lived_episodes=BrokenEpisodes(), dream=None)

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
            "daemon.maez_daemon.served_model_alias", return_value="llamacpp:unknown"
        ):
            body = md.MaezDaemon._body_health(
                daemon,
                camera_presence={},
                memory_stats={"raw": 0, "daily": 0, "core": 0, "total": 0},
                reasoning_loop={},
                system={},
            )

        self.assertEqual(body["memory"]["episode_counts_state"], "unknown")
        self.assertEqual(body["memory"]["episode_counts_error_class"], "RuntimeError")
        self.assertEqual(body["memory"]["episodes_active"], 0)
        self.assertEqual(body["brain"]["served_model_alias"], "llamacpp:unknown")


class BodyHealthWiringTests(unittest.TestCase):
    def test_health_route_adds_body_from_existing_subdicts(self):
        src = _read("daemon/maez_daemon.py")
        self.assertIn('"body": self._body_health(', src)
        self.assertIn("camera_presence=_camera_presence", src)
        self.assertIn("memory_stats=_memory_stats", src)
        self.assertIn("reasoning_loop=_reasoning_loop", src)
        self.assertIn("system=_system", src)

    def test_public_web_state_strips_body_projection(self):
        web_src = _read("skills/web_interface.py")
        route = web_src.split('@app.route("/api/maez-state")', 1)[1].split(
            "@app.route(",
            1,
        )[0]

        self.assertIn('daemon_health.pop("camera_presence", None)', route)
        self.assertIn('daemon_health.pop("body", None)', route)

    def test_debug_services_strips_body_projection(self):
        web_src = _read("skills/web_interface.py")
        route = web_src.split('@app.route("/api/debug/services")', 1)[1].split(
            "@app.route(",
            1,
        )[0]

        self.assertIn('daemon_health.pop("body", None)', route)


if __name__ == "__main__":
    unittest.main()


class BodyOrganViewFrontendTests(unittest.TestCase):
    """Source-text contract for the Slice B organ dashboard (the visual is owner-witnessed)."""

    def setUp(self):
        self.page = _read("ui/dashboard_local.html")

    def test_reads_health_body_and_renders_organs(self):
        self.assertIn("renderBody(d.body)", self.page)
        self.assertIn('id="organView"', self.page)
        for key in ("eyes", "stomach", "memory", "dreaming", "attention",
                    "cycle_mind", "recall", "brain", "heartbeat", "covenant_perimeter"):
            self.assertIn(f"'{key}'", self.page, f"organ {key} not rendered")

    def test_stays_local_only_and_read_only(self):
        # local-only banner preserved
        self.assertIn("NOT exposed through nginx", self.page)
        # lens-not-hand: the organ renderer must not POST/toggle/edit organs
        organ_js = self.page.split("renderBody(d.body)", 1)[1]
        self.assertNotIn("method: 'POST'", organ_js)
        self.assertNotIn('method:"POST"', organ_js)

    def test_no_fake_glow_when_body_absent(self):
        # honest: no body -> "awaiting" message, not a fabricated organ grid
        self.assertIn("awaiting /health.body", self.page)
