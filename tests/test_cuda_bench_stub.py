import json
import subprocess
import sys
import unittest
import urllib.error
import urllib.request

from scripts.cuda_bench_stub import STUB_SHA256_PATH_ENV


ALIAS = "qwen36-27b-mtp"
PERSONAS = {
    "healthy",
    "readiness_timeout",
    "midturn_hang",
    "crash",
    "malformed_response",
    "wrong_identity",
}


class StubTests(unittest.TestCase):
    def _spawn(self, *args: str) -> tuple[subprocess.Popen[str], int]:
        proc = subprocess.Popen(
            [sys.executable, "-B", "-m", "scripts.cuda_bench_stub", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self._close_pipes, proc)
        self.addCleanup(self._stop, proc)
        assert proc.stdout is not None
        line = proc.stdout.readline().strip()
        self.assertRegex(line, r"^STUB_LISTENING port=[1-9][0-9]*$")
        return proc, int(line.split("=", 1)[1])

    def _stop(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)

    def _close_pipes(self, proc: subprocess.Popen[str]) -> None:
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()

    def _get_json(self, port: int, path: str) -> tuple[int, object]:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}{path}", timeout=2
        ) as response:
            return response.status, json.loads(response.read())

    def _post_completion(
        self, port: int, payload: dict[str, object], *, read_all: bool = True
    ) -> tuple[str, str]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/completion",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            content_type = response.headers.get_content_type()
            if read_all:
                body = response.read().decode("utf-8")
            else:
                body = response.readline().decode("utf-8")
        return content_type, body

    def test_stub_pin_environment_name_is_frozen(self) -> None:
        self.assertEqual("CUDA_BENCH_STUB_PATH", STUB_SHA256_PATH_ENV)

    def test_healthy_persona_serves_exact_three_event_stream(self) -> None:
        proc, port = self._spawn("--persona", "healthy", "--alias", ALIAS)
        self.assertIsNone(proc.poll())

        status, health = self._get_json(port, "/health")
        self.assertEqual(200, status)
        self.assertEqual({"status": "ok"}, health)
        status, models = self._get_json(port, "/v1/models")
        self.assertEqual(200, status)
        self.assertEqual({"data": [{"id": ALIAS}]}, models)

        content_type, body = self._post_completion(
            port, {"prompt": "sentinel", "stream": True}
        )
        self.assertEqual("text/event-stream", content_type)
        lines = [line for line in body.splitlines() if line]
        self.assertEqual(3, len(lines), body)
        self.assertTrue(all(line.startswith("data: ") for line in lines), body)
        self.assertNotIn("[DONE]", body)
        events = [json.loads(line.removeprefix("data: ")) for line in lines]
        self.assertNotIn("content", events[0])
        self.assertTrue(events[1]["content"])
        self.assertEqual(
            {
                "prompt_per_second": 100.0,
                "predicted_per_second": 50.0,
                "predicted_n": 16,
                "prompt_n": 32,
                "draft_n": 12,
                "draft_n_accepted": 9,
            },
            events[2]["timings"],
        )
        self.assertEqual("", events[2]["content"])

    def test_missing_or_non_boolean_true_stream_flag_is_aggregate_json(self) -> None:
        _proc, port = self._spawn("--persona", "healthy", "--alias", ALIAS)
        for payload in (
            {"prompt": "sentinel"},
            {"prompt": "sentinel", "stream": False},
            {"prompt": "sentinel", "stream": 1},
        ):
            with self.subTest(payload=payload):
                content_type, body = self._post_completion(port, payload)
                self.assertEqual("application/json", content_type)
                self.assertNotIn("data: ", body)
                self.assertNotIn("[DONE]", body)
                document = json.loads(body)
                self.assertTrue(document["content"])
                self.assertEqual(12, document["timings"]["draft_n"])
                self.assertEqual(9, document["timings"]["draft_n_accepted"])

    def test_valid_non_object_json_is_bounded_invalid_request(self) -> None:
        proc, port = self._spawn("--persona", "healthy", "--alias", ALIAS)
        for raw in (b"[]", b"null", b'"text"', b"7"):
            with self.subTest(raw=raw):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/completion",
                    data=raw,
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(400, caught.exception.code)
                self.assertEqual(
                    {"error": "invalid_json"},
                    json.loads(caught.exception.read()),
                )

        self.assertEqual((200, {"status": "ok"}), self._get_json(port, "/health"))
        self._stop(proc)
        assert proc.stderr is not None
        self.assertNotIn("Traceback", proc.stderr.read())

    def test_readiness_timeout_persona_returns_503_forever(self) -> None:
        _proc, port = self._spawn(
            "--persona", "readiness_timeout", "--alias", ALIAS
        )
        for _ in range(2):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=2
                )
            self.assertEqual(503, caught.exception.code)

    def test_wrong_identity_and_models_shape_personas(self) -> None:
        cases = (
            (("--persona", "wrong_identity", "--alias", ALIAS), 1, False),
            (("--persona", "healthy", "--alias", ALIAS, "--models-empty"), 0, False),
            (("--persona", "healthy", "--alias", ALIAS, "--models-multi"), 2, True),
        )
        for args, count, includes_alias in cases:
            with self.subTest(args=args):
                proc, port = self._spawn(*args)
                _status, document = self._get_json(port, "/v1/models")
                ids = [item["id"] for item in document["data"]]
                self.assertEqual(count, len(ids))
                self.assertEqual(includes_alias, ALIAS in ids)
                self._stop(proc)

    def test_models_empty_and_multi_flags_are_mutually_exclusive(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "scripts.cuda_bench_stub",
                "--persona",
                "healthy",
                "--alias",
                ALIAS,
                "--models-empty",
                "--models-multi",
            ],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)

    def test_midturn_hang_emits_one_event_then_remains_alive(self) -> None:
        proc, port = self._spawn("--persona", "midturn_hang", "--alias", ALIAS)
        content_type, first_line = self._post_completion(
            port, {"prompt": "sentinel", "stream": True}, read_all=False
        )
        self.assertEqual("text/event-stream", content_type)
        self.assertTrue(first_line.startswith("data: "), first_line)
        self.assertIsNone(proc.poll())

    def test_crash_persona_exits_after_first_event(self) -> None:
        proc, port = self._spawn("--persona", "crash", "--alias", ALIAS)
        content_type, first_line = self._post_completion(
            port, {"prompt": "sentinel", "stream": True}, read_all=False
        )
        self.assertEqual("text/event-stream", content_type)
        self.assertTrue(first_line.startswith("data: "), first_line)
        self.assertNotEqual(0, proc.wait(timeout=2))

    def test_malformed_response_persona_emits_non_json_data(self) -> None:
        _proc, port = self._spawn(
            "--persona", "malformed_response", "--alias", ALIAS
        )
        content_type, body = self._post_completion(
            port, {"prompt": "sentinel", "stream": True}
        )
        self.assertEqual("text/event-stream", content_type)
        lines = [line for line in body.splitlines() if line]
        self.assertEqual(["data: not-json"], lines)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(lines[0].removeprefix("data: "))

    def test_persona_choices_are_closed(self) -> None:
        for persona in PERSONAS:
            with self.subTest(persona=persona):
                proc, _port = self._spawn("--persona", persona, "--alias", ALIAS)
                self._stop(proc)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "scripts.cuda_bench_stub",
                "--persona",
                "invented",
                "--alias",
                ALIAS,
            ],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)

    def test_any_nonzero_port_is_structurally_forbidden(self) -> None:
        for port in (1, 18080, 65535):
            with self.subTest(port=port):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "scripts.cuda_bench_stub",
                        "--persona",
                        "healthy",
                        "--alias",
                        ALIAS,
                        "--port",
                        str(port),
                    ],
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("port_forbidden", result.stderr)

    def test_stdout_has_only_the_single_flushed_listening_line(self) -> None:
        proc, port = self._spawn("--persona", "healthy", "--alias", ALIAS)
        self._get_json(port, "/health")
        self._stop(proc)
        assert proc.stdout is not None
        self.assertEqual("", proc.stdout.read())


if __name__ == "__main__":
    unittest.main()
