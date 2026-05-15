"""Camera Presence v1 legacy-disablement contract.

These source-level tests pin the dangerous legacy surfaces before implementation
touches daemon code. They intentionally mirror Calendar v1's closure style.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

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


class CameraPresenceLegacyDisablementSourceTests(unittest.TestCase):
    def setUp(self):
        self.daemon_src = _read("daemon/maez_daemon.py")
        self.loop_body = _method_body(self.daemon_src, "_loop")

    def test_daemon_does_not_import_legacy_presence_at_module_load(self):
        tree = ast.parse(self.daemon_src)
        top_level_imports = [
            node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        imported_modules = []
        for node in top_level_imports:
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            else:
                imported_modules.append(node.module or "")

        self.assertNotIn("skills.presence_perception", imported_modules)

    def test_reason_prompt_never_formats_legacy_presence_context(self):
        reason_body = _method_body(self.daemon_src, "_reason")

        self.assertNotIn("_last_presence_snap.format_for_context()", reason_body)
        self.assertNotIn("[PRESENCE]", reason_body)

    def test_signal_manifest_and_audit_do_not_treat_presence_as_grounding(self):
        self.assertNotIn("presence snapshot — live", self.daemon_src)
        self.assertNotIn("presence_snapshot: present", self.daemon_src)
        self.assertNotIn("_cycle_signals_present.append(\"presence snapshot\")", self.daemon_src)

    def test_presence_does_not_trigger_return_greeting_or_morning_briefing(self):
        self.assertNotIn("compose_return_greeting", self.loop_body)
        self.assertNotIn("_send_morning_briefing(snap)", self.loop_body)

    def test_presence_does_not_write_memory_metadata(self):
        self.assertNotIn('"rohit_present"', self.loop_body)
        self.assertNotIn("session_minutes", self.loop_body)
        self.assertNotIn("last_departure_time", self.loop_body)

    def test_presence_does_not_drive_dream_idle_or_signature_gate(self):
        self.assertNotIn("DreamState.is_idle", self.loop_body)
        self.assertNotIn("presence_state=", self.loop_body)
        self.assertNotIn("self._last_presence_snap.rohit_present", self.loop_body)

    def test_fast_lane_envelope_does_not_include_camera_presence(self):
        perception_envelope = _read("core/memory/perception_envelope.py")
        fast_prompt_builder = _read("core/infra/fast_prompt_builder.py")

        self.assertNotIn('"presence"', perception_envelope)
        self.assertNotIn("'presence'", perception_envelope)
        self.assertNotIn("presence", fast_prompt_builder.lower())

    def test_public_maez_state_does_not_expose_camera_presence(self):
        web_src = _read("skills/web_interface.py")
        route = web_src.split('@app.route("/api/maez-state")', 1)[1].split(
            "@app.route(",
            1,
        )[0]

        self.assertNotIn("presence_state", route)
        self.assertNotIn("last_observed_at", route)
        self.assertNotIn("enabled_until", route)
        self.assertIn('daemon_health.pop("camera_presence", None)', route)

    def test_public_maez_state_strips_daemon_camera_presence_payload(self):
        from skills import web_interface as wi

        with (
            patch.object(
                wi,
                "_daemon_health",
                return_value={
                    "ok": True,
                    "camera_presence": {
                        "presence_state": "present",
                        "enabled_until": "2026-05-15T12:05:00+00:00",
                        "last_observed_at": "2026-05-15T12:00:00+00:00",
                    },
                },
            ),
            patch.object(wi.memory, "memory_stats", return_value={"raw": 0, "daily": 0, "core": 0, "total": 0}),
            patch.object(wi.accounts, "count", return_value=1),
        ):
            response = wi.app.test_client().get("/api/maez-state")

        self.assertEqual(response.status_code, 200)
        daemon = response.get_json()["daemon"]
        self.assertNotIn("camera_presence", daemon)

    def test_web_explanation_surfaces_do_not_translate_camera_presence(self):
        web_src = _read("skills/web_interface.py")

        self.assertNotIn("a current presence reading", web_src)
        self.assertNotIn("tell whether you were at the desk", web_src)

    def test_static_capability_surfaces_do_not_advertise_presence_recognition(self):
        source_awareness = _read("core/memory/source_awareness.py")
        evolution_engine = _read("skills/evolution_engine.py")
        runtime_source_awareness = _read("memory/source_awareness.json")

        self.assertNotIn("'skills/presence_perception.py': ['rohit_presence']", source_awareness)
        self.assertNotIn("'skills/face_enrollment.py': ['rohit_presence']", source_awareness)
        self.assertNotIn("'skills/presence_perception.py',", evolution_engine)
        self.assertNotIn("'presence': 'skills/presence_perception.py'", evolution_engine)
        self.assertNotIn("Camera-based presence + face recognition", runtime_source_awareness)
        self.assertNotIn('"rohit_presence"', runtime_source_awareness)

    def test_v1_presence_runtime_extra_excludes_face_recognition_stack(self):
        data = tomllib.loads(_read("pyproject.toml"))
        vision_deps = data["project"]["optional-dependencies"]["vision"]
        normalized = {dep.split(">=", 1)[0] for dep in vision_deps}

        self.assertIn("opencv-python", normalized)
        self.assertIn("mediapipe", normalized)
        self.assertNotIn("face_recognition", normalized)
        self.assertNotIn("dlib", normalized)

    def test_live_presence_module_does_not_import_or_unpickle_face_enrollment(self):
        src = _read("skills/presence_perception.py")

        self.assertNotIn("face_recognition", src)
        self.assertNotIn("pickle", src)
        self.assertNotIn("rohit_embeddings.pkl", src)
        self.assertNotIn("ENROLLMENT_PATH", src)
        self.assertNotIn("person_identified", src)
        self.assertNotIn("rohit_present", src)
        self.assertNotIn("stranger", src)
        self.assertNotIn("[PRESENCE]", src)
        self.assertNotIn("format_for_context", src)
        self.assertNotIn("format_for_memory", src)

    def test_live_presence_module_keeps_no_presence_delta_history(self):
        src = _read("skills/presence_perception.py")

        self.assertNotIn("session_start", src)
        self.assertNotIn("absent_since", src)
        self.assertNotIn("last_seen", src)
        self.assertNotIn("total_sessions_today", src)
        self.assertNotIn("the owner arrived", src)
        self.assertNotIn("the owner left desk", src)

    def test_live_presence_module_releases_camera_in_finally(self):
        src = _read("skills/presence_perception.py")
        open_idx = src.find("cap = cv2.VideoCapture")
        self.assertGreater(open_idx, -1)
        window = src[open_idx : open_idx + 1400]
        self.assertIn("finally:", window)
        self.assertIn("cap.release()", window)


if __name__ == "__main__":
    unittest.main()
