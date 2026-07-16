"""Loopback-only llama-server rehearsal stub for the CUDA bench driver."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _close_sealed_entry_fd() -> None:
    prefix = "/proc/self/fd/"
    if not sys.argv[0].startswith(prefix):
        return
    try:
        os.close(int(sys.argv[0][len(prefix) :]))
    except (OSError, ValueError):
        raise SystemExit("sealed_entry_fd_invalid") from None


_close_sealed_entry_fd()


STUB_SHA256_PATH_ENV = "CUDA_BENCH_STUB_PATH"

PERSONAS = frozenset(
    {
        "healthy",
        "readiness_timeout",
        "midturn_hang",
        "crash",
        "malformed_response",
        "wrong_identity",
    }
)

_TIMINGS = {
    "prompt_per_second": 100.0,
    "predicted_per_second": 50.0,
    "predicted_n": 16,
    "prompt_n": 32,
    "draft_n": 12,
    "draft_n_accepted": 9,
}
_METADATA_EVENT = {"content": "", "stop": False, "id_slot": 0}
_CONTENT_EVENT = {"content": "stub response", "stop": False}


def _json_bytes(document: object) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sse_bytes(*events: object) -> bytes:
    return b"".join(b"data: " + _json_bytes(event) + b"\n\n" for event in events)


class _StubServer(ThreadingHTTPServer):
    daemon_threads = True
    persona: str
    alias: str
    models_empty: bool
    models_multi: bool


class _Handler(BaseHTTPRequestHandler):
    server: _StubServer
    server_version = "CudaBenchStub/1"
    sys_version = ""

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def _send_json(self, status: int, document: object) -> None:
        self._send(status, _json_bytes(document), "application/json")

    def _begin_unbounded_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            if self.server.persona == "readiness_timeout":
                self._send_json(
                    503,
                    {
                        "error": {
                            "code": 503,
                            "message": "Loading model",
                            "type": "unavailable_error",
                        }
                    },
                )
            else:
                self._send_json(200, {"status": "ok"})
            return
        if self.path == "/v1/models":
            if self.server.models_empty:
                ids: list[str] = []
            elif self.server.models_multi:
                ids = [f"{self.server.alias}-other", self.server.alias]
            elif self.server.persona == "wrong_identity":
                ids = [f"wrong-{self.server.alias}"]
            else:
                ids = [self.server.alias]
            self._send_json(200, {"data": [{"id": model_id} for model_id in ids]})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/completion":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return
        if type(payload) is not dict:
            self._send_json(400, {"error": "invalid_json"})
            return

        if payload.get("stream") is not True:
            self._send_json(200, {"content": _CONTENT_EVENT["content"], "timings": _TIMINGS})
            return

        if self.server.persona == "malformed_response":
            self._send(200, b"data: not-json\n\n", "text/event-stream")
            return
        if self.server.persona in {"midturn_hang", "crash"}:
            self._begin_unbounded_sse()
            self.wfile.write(_sse_bytes(_METADATA_EVENT))
            self.wfile.flush()
            if self.server.persona == "crash":
                os._exit(1)
            while True:
                time.sleep(60)

        terminal_event = {
            "content": "",
            "prompt": payload.get("prompt"),
            "stop": True,
            "timings": _TIMINGS,
        }
        body = _sse_bytes(_METADATA_EVENT, _CONTENT_EVENT, terminal_event)
        self._send(200, body, "text/event-stream")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    parser.add_argument("--alias", required=True)
    models = parser.add_mutually_exclusive_group()
    models.add_argument("--models-empty", action="store_true")
    models.add_argument("--models-multi", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.port != 0:
        raise SystemExit("port_forbidden")
    server = _StubServer(("127.0.0.1", 0), _Handler)
    server.persona = args.persona
    server.alias = args.alias
    server.models_empty = args.models_empty
    server.models_multi = args.models_multi
    print(f"STUB_LISTENING port={server.server_address[1]}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
