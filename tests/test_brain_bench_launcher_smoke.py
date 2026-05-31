import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.brain_bench import bench
from scripts.brain_bench import probe_runner
from scripts.brain_bench.samples import ProbeSample


def _subprocess_env(repo: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("MAEZ_")
    }
    env["PYTHONPATH"] = str(repo)
    return env


def _ops_config():
    return {
        "api_family": "llama_cpp",
        "topology": "separate_server",
        "bind_host_verified": True,
        "live_daemon_disturbance": False,
        "gpu_contention": "low",
        "startup_health": "ok",
        "streaming_support": True,
        "restart_recovery": "clean",
    }


class _OpenAICompatStub(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests_seen: list[tuple[str, str]] = []

    def do_POST(self):
        _length = int(self.headers.get("content-length", "0") or 0)
        body_text = ""
        if _length:
            body_text = self.rfile.read(_length).decode("utf-8")
        self.requests_seen.append((self.path, body_text))
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.send_header("content-length", "0")
            self.send_header("connection", "close")
            self.end_headers()
            return
        body = (
            b'data: {"choices":[{"delta":{"content":"The sandbox fixture is available [E1]."}}]}\n\n'
            b"data: [DONE]\n\n"
        )
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


class BrainBenchLauncherSmokeTests(unittest.TestCase):
    def test_probe_sample_has_one_library_identity(self):
        self.assertIs(bench.ProbeSample, ProbeSample)
        self.assertIs(probe_runner.ProbeSample, ProbeSample)

    def test_launcher_module_path_completes_with_openai_compatible_stub(self):
        _OpenAICompatStub.requests_seen = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenAICompatStub)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config_path = root / "variants.json"
                packet_path = root / "packet.json"
                sandbox_root = root / "sandbox"
                config_path.write_text(
                    json.dumps(
                        [
                            {
                                "label": "owner-run-smoke",
                                "backend_family": "openai_compatible",
                                "base_url": f"http://127.0.0.1:{port}",
                                "model": "stub-model",
                                "chat_kwargs": {"num_predict": 32, "temperature": 0.1},
                                "ops": _ops_config(),
                            }
                        ]
                    )
                )

                env = _subprocess_env(Path(__file__).resolve().parents[1])
                env["MAEZ_RECALL_CITATION_RENDER_V2"] = "1"
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.brain_bench.launcher",
                        str(sandbox_root),
                        "--variants-config",
                        str(config_path),
                        "--out",
                        str(packet_path),
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=90,
                    check=False,
                )

                if result.returncode != 0:
                    self.fail(result.stderr + result.stdout)
                self.assertTrue(packet_path.exists())
                packet_text = packet_path.read_text()
                packet = json.loads(packet_text)
                debug_line = next(
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("debug_dump=")
                )
                debug_path = Path(debug_line.split("=", 1)[1])
                try:
                    debug_dump = json.loads(debug_path.read_text())
                    debug_blob = json.dumps(debug_dump)
                    self.assertEqual(packet["variants"][0]["label"], "owner-run-smoke")
                    self.assertTrue(_OpenAICompatStub.requests_seen)
                    self.assertTrue(
                        all(path == "/v1/chat/completions" for path, _body in _OpenAICompatStub.requests_seen)
                    )
                    self.assertIn("stub-model", _OpenAICompatStub.requests_seen[0][1])
                    request_prompts = [
                        json.loads(body)["messages"][0]["content"]
                        for _path, body in _OpenAICompatStub.requests_seen
                    ]
                    self.assertTrue(request_prompts)
                    self.assertTrue(
                        all(" · date:" in prompt for prompt in request_prompts)
                    )
                    self.assertFalse(
                        any("most important, repeated" in prompt for prompt in request_prompts)
                    )
                    self.assertIn('"citation_render_version": "v2"', debug_blob)
                    self.assertNotIn("probe_run must return ProbeSample rows", result.stderr)
                    fail_reasons = packet["variants"][0]["fail_reasons"]
                    self.assertNotIn("inference_failed", fail_reasons)
                    self.assertNotIn("The sandbox fixture is available", packet_text)
                    self.assertNotIn('"answer"', packet_text)
                    self.assertNotIn('"evidence":', packet_text)
                finally:
                    debug_path.unlink(missing_ok=True)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
