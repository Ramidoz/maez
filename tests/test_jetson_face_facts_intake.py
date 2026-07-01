import os
import unittest
from unittest import mock

import skills.web_interface  # noqa: E402,F401


class FaceFactsIntakeEndpointTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web

        self.web = web
        self.secret_patch = mock.patch.object(self.web, "get_secret", return_value=None)
        self.secret_patch.start()
        self.addCleanup(self.secret_patch.stop)
        self.client = web.app.test_client()

    def _valid_face(self, **over):
        face = {
            "embedding": [0.125] * 512,
            "det_score": 0.98,
            "box": [1.0, 2.0, 3.0, 4.0],
            "track_id": None,
        }
        face.update(over)
        return face

    def _valid_body(self, **over):
        body = {
            "schema_version": "jetson_face_facts.v0",
            "model_id": "buffalo_s/scrfd_500m+w600k_mbf",
            "sensor_state": "available",
            "frame_quality": "good",
            "ts": "2026-07-01T12:00:00Z",
            "faces": [self._valid_face()],
        }
        body.update(over)
        return body

    def _post(self, body=None, *, token="secret"):
        headers = {}
        if token is not None:
            headers["X-Maez-Jetson-Token"] = token
        return self.client.post(
            "/api/v1/perception/jetson/face_facts",
            json=body if body is not None else self._valid_body(),
            headers=headers,
        )

    def test_flag_off_404_mutates_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(self.web, "_jetson_write_face_facts_receipt") as receipt:
                resp = self._post()
                self.assertEqual(resp.status_code, 404)
                receipt.assert_not_called()
                self.assertFalse(hasattr(self.web, "_JETSON_FACE_FACTS_STORE"))

    def test_bad_or_missing_token_401(self):
        env = {"MAEZ_JETSON_FACE_FACTS_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_face_facts_receipt") as receipt:
                self.assertEqual(self._post(token="wrong").status_code, 401)
                self.assertEqual(self._post(token=None).status_code, 401)
                receipt.assert_not_called()

    def test_extra_frame_key_is_400(self):
        env = {"MAEZ_JETSON_FACE_FACTS_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            resp = self._post({**self._valid_body(), "room_occupancy": 1})
            self.assertEqual(resp.status_code, 400)

    def test_valid_one_face_packet_returns_200_and_drops_payload(self):
        env = {"MAEZ_JETSON_FACE_FACTS_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_face_facts_receipt") as receipt:
                resp = self._post()
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.get_json()["ok"])
                self.assertEqual(resp.get_json()["face_count"], 1)
                receipt.assert_called_once()
                self.assertFalse(hasattr(self.web, "_JETSON_FACE_FACTS_STORE"))

    def test_zero_detection_packet_receipts_face_count_zero(self):
        env = {"MAEZ_JETSON_FACE_FACTS_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertLogs("maez.web", level="INFO") as logs:
                resp = self._post(self._valid_body(faces=[]))
            self.assertEqual(resp.status_code, 200)
            joined = "\n".join(logs.output)
            self.assertIn("jetson_face_facts_intake", joined)
            self.assertIn("face_count=0", joined)
            self.assertNotIn("owner_absent", joined)
            self.assertNotIn("room_empty", joined)
            self.assertNotIn("no_one_here", joined)

    def test_receipt_is_content_light(self):
        env = {"MAEZ_JETSON_FACE_FACTS_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertLogs("maez.web", level="INFO") as logs:
                resp = self._post()
            self.assertEqual(resp.status_code, 200)
            joined = "\n".join(logs.output)
            self.assertIn("model_id=buffalo_s/scrfd_500m+w600k_mbf", joined)
            self.assertIn("sensor_state=available", joined)
            self.assertIn("frame_quality=good", joined)
            self.assertIn("face_count=1", joined)
            self.assertNotIn("0.125", joined)
            self.assertNotIn("owner_absent", joined)
            self.assertNotIn("room_empty", joined)
            self.assertNotIn("no_one_here", joined)

    def test_intake_does_not_touch_fresh_moment_receipts(self):
        import core.cognition.fresh_moment_receipts as fmr

        env = {"MAEZ_JETSON_FACE_FACTS_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(fmr, "FreshMomentReceipts") as fake_store:
                resp = self._post()
                self.assertEqual(resp.status_code, 200)
                fake_store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
