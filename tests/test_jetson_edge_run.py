import unittest
from unittest import mock

import tests._jetson_edge_path  # noqa: F401
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


if __name__ == "__main__":
    unittest.main()
