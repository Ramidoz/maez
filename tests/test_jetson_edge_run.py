import unittest
from unittest import mock

import tests._jetson_edge_path  # noqa: F401
from core.body.jetson_face_facts import parse_face_facts
from jetson_presence import run


class RunBoundedTests(unittest.TestCase):
    def test_loops_n_times_then_exits(self):
        calls = {"n": 0}

        def _fake_cycle(**kwargs):
            calls["n"] += 1
            return {"sensor_state": "available", "owner_present": "unknown"}

        with (
            mock.patch.object(run, "_run_one_cycle", _fake_cycle),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            run.main(["--loops", "3"])
        self.assertEqual(calls["n"], 3)

    def test_rejects_non_positive_loop_count(self):
        for value in ("0", "-1"):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                run.main(["--loops", value])

    def test_once_runs_a_single_cycle(self):
        calls = {"n": 0}
        with (
            mock.patch.object(
                run, "_run_one_cycle", lambda **k: calls.__setitem__("n", calls["n"] + 1)
            ),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            run.main(["--once"])
        self.assertEqual(calls["n"], 1)

    def test_no_infinite_default(self):
        calls = {"n": 0}
        with (
            mock.patch.object(
                run, "_run_one_cycle", lambda **k: calls.__setitem__("n", calls["n"] + 1)
            ),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            run.main([])
        self.assertEqual(calls["n"], 1)

    def test_default_path_does_not_load_face_facts_models(self):
        calls = {"b0": 0}
        with (
            mock.patch.object(
                run, "_run_one_cycle", lambda **k: calls.__setitem__("b0", calls["b0"] + 1)
            ),
            mock.patch.object(run, "_load_face_facts_models", side_effect=AssertionError),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            run.main(["--loops", "1"])
        self.assertEqual(calls["b0"], 1)

    def test_face_facts_mode_uses_face_facts_cycle(self):
        detector = object()
        embedder = object()
        calls = []

        def _fake_cycle(**kwargs):
            calls.append(kwargs)
            return {"sensor_state": "available", "faces": []}

        with (
            mock.patch.object(run, "_run_one_cycle", side_effect=AssertionError),
            mock.patch.object(run, "_load_face_facts_models", return_value=(detector, embedder)),
            mock.patch.object(run, "_run_one_face_facts_cycle", _fake_cycle),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            run.main(["--face-facts", "--loops", "2"])
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0]["detector"], detector)
        self.assertIs(calls[0]["embedder"], embedder)
        self.assertEqual(calls[0]["cfg"].face_facts_intake_path, "/api/v1/perception/jetson/face_facts")

    def test_face_facts_mode_uses_configured_default_frame_count(self):
        calls = {"n": 0}
        cfg = run.load_config()
        cfg = type(cfg)(
            **{
                **cfg.__dict__,
                "face_facts_frames": 3,
            }
        )
        with (
            mock.patch.object(run, "load_config", return_value=cfg),
            mock.patch.object(run, "_load_face_facts_models", return_value=(object(), object())),
            mock.patch.object(
                run,
                "_run_one_face_facts_cycle",
                lambda **k: calls.__setitem__("n", calls["n"] + 1),
            ),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            run.main(["--face-facts"])
        self.assertEqual(calls["n"], 3)

    def test_releases_camera_when_cycle_raises(self):
        class FakeCamera:
            def __init__(self):
                self.released = False

            def release(self):
                self.released = True

        camera = FakeCamera()

        def _raise_cycle(**kwargs):
            raise RuntimeError("cycle failed")

        with (
            mock.patch.object(run, "Camera", lambda **kwargs: camera),
            mock.patch.object(run, "_run_one_cycle", _raise_cycle),
            self.assertRaises(RuntimeError),
        ):
            run.main([])
        self.assertTrue(camera.released)

    def test_releases_camera_when_face_facts_cycle_raises(self):
        class FakeCamera:
            def __init__(self):
                self.released = False

            def release(self):
                self.released = True

        camera = FakeCamera()

        def _raise_cycle(**kwargs):
            raise RuntimeError("face facts cycle failed")

        with (
            mock.patch.object(run, "Camera", lambda **kwargs: camera),
            mock.patch.object(run, "_load_face_facts_models", return_value=(object(), object())),
            mock.patch.object(run, "_run_one_face_facts_cycle", _raise_cycle),
            self.assertRaises(RuntimeError),
        ):
            run.main(["--face-facts"])
        self.assertTrue(camera.released)

    def test_face_facts_cycle_posts_available_geometry_packet(self):
        class FakeCamera:
            def __init__(self):
                self.released = False

            def open(self):
                return True

            def read_frame(self):
                return (True, object())

            def release(self):
                self.released = True

        class FakeDetector:
            def detect(self, frame):
                return [([1, 2, 3, 4], 0.98)], 3.0

        cfg = run.load_config()
        posted = []
        face = ([0.0] * 512, 0.98, [1, 2, 3, 4], None)
        camera = FakeCamera()
        with (
            mock.patch.object(run, "_now_ts", return_value="2026-07-01T12:00:00Z"),
            mock.patch.object(run, "_is_curtained", return_value=False),
            mock.patch.object(run, "_face_tuples_from_detections", return_value=[face]),
            mock.patch.object(run, "_post_face_facts", lambda cfg, packet: posted.append(packet)),
        ):
            packet = run._run_one_face_facts_cycle(
                cfg=cfg,
                camera=camera,
                detector=FakeDetector(),
                embedder=object(),
            )
        self.assertTrue(camera.released)
        self.assertEqual(posted, [packet])
        self.assertEqual(packet["sensor_state"], "available")
        self.assertEqual(packet["frame_quality"], "good")
        self.assertEqual(len(packet["faces"]), 1)
        self.assertIsNotNone(parse_face_facts(packet))

    def test_face_facts_cycle_curtained_posts_empty_without_opening(self):
        class FakeCamera:
            def __init__(self):
                self.opened = False
                self.released = False

            def open(self):
                self.opened = True
                raise AssertionError("curtained cycle must not open camera")

            def release(self):
                self.released = True

        cfg = run.load_config()
        posted = []
        camera = FakeCamera()
        with (
            mock.patch.object(run, "_now_ts", return_value="2026-07-01T12:00:00Z"),
            mock.patch.object(run, "_is_curtained", return_value=True),
            mock.patch.object(run, "_post_face_facts", lambda cfg, packet: posted.append(packet)),
        ):
            packet = run._run_one_face_facts_cycle(
                cfg=cfg,
                camera=camera,
                detector=object(),
                embedder=object(),
            )
        self.assertFalse(camera.opened)
        self.assertTrue(camera.released)
        self.assertEqual(packet["sensor_state"], "curtained")
        self.assertEqual(packet["faces"], [])
        self.assertIsNotNone(parse_face_facts(packet))

    def test_face_facts_cycle_open_failure_posts_error_empty(self):
        class FakeCamera:
            def __init__(self):
                self.released = False

            def open(self):
                return False

            def release(self):
                self.released = True

        cfg = run.load_config()
        posted = []
        camera = FakeCamera()
        with (
            mock.patch.object(run, "_now_ts", return_value="2026-07-01T12:00:00Z"),
            mock.patch.object(run, "_is_curtained", return_value=False),
            mock.patch.object(run, "_post_face_facts", lambda cfg, packet: posted.append(packet)),
        ):
            packet = run._run_one_face_facts_cycle(
                cfg=cfg,
                camera=camera,
                detector=object(),
                embedder=object(),
            )
        self.assertTrue(camera.released)
        self.assertEqual(packet["sensor_state"], "error")
        self.assertEqual(packet["faces"], [])
        self.assertEqual(posted, [packet])
        self.assertIsNotNone(parse_face_facts(packet))


if __name__ == "__main__":
    unittest.main()
