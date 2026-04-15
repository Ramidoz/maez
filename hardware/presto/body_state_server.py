#!/usr/bin/env python3
"""
LAN-only bedside state relay for Pimoroni Presto.

This keeps the first networked body experiment decoupled from the main
daemon. It reads Maez's local health endpoint on 127.0.0.1 and exposes
an intentionally tiny JSON surface for the Presto over the home LAN.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 8765
LOCAL_HEALTH_URL = "http://127.0.0.1:11435/health"


def _pick_mode(health: dict) -> str:
    system = health.get("system", {})
    cpu = float(system.get("cpu_percent") or 0.0)
    gpu = float(system.get("gpu_percent") or 0.0)

    if cpu > 65 or gpu > 45:
        return "LISTEN"
    if health.get("status") != "alive":
        return "QUIET"
    return "WATCH"


def _pick_message(health: dict) -> str:
    system = health.get("system", {})
    memory = health.get("memory", {})
    cycle_count = int(health.get("cycle_count") or 0)
    cpu = float(system.get("cpu_percent") or 0.0)
    ram = float(system.get("ram_percent") or 0.0)
    gpu = float(system.get("gpu_percent") or 0.0)

    if cpu > 65:
        return f"High host load. CPU at {cpu:.0f}%."
    if gpu > 45:
        return f"Local model active. GPU at {gpu:.0f}%."
    if ram > 75:
        return f"Memory pressure up. RAM at {ram:.0f}%."
    if cycle_count <= 0:
        return "Waiting for daemon cycles."

    raw_count = int(memory.get("raw") or 0)
    return f"Cycle {cycle_count}. Raw memories: {raw_count}."


def build_state() -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(LOCAL_HEALTH_URL, timeout=1.5) as response:
            health = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 503, {
            "ok": False,
            "status": "offline",
            "mode": "QUIET",
            "title": "MAEZ",
            "message": f"Host link down: {type(exc).__name__}",
            "timestamp": int(time.time()),
        }

    system = health.get("system", {})
    state = {
        "ok": True,
        "status": health.get("status", "unknown"),
        "mode": _pick_mode(health),
        "title": "MAEZ",
        "message": _pick_message(health),
        "cycle_count": int(health.get("cycle_count") or 0),
        "uptime_seconds": int(health.get("uptime_seconds") or 0),
        "cpu_percent": float(system.get("cpu_percent") or 0.0),
        "ram_percent": float(system.get("ram_percent") or 0.0),
        "gpu_percent": float(system.get("gpu_percent") or 0.0),
        "timestamp": int(time.time()),
    }
    return 200, state


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/body-state", "/body-state/"):
            self.send_error(404)
            return

        status, payload = build_state()
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expose a tiny LAN-only body-state API for Presto.")
    parser.add_argument("--bind", default=DEFAULT_BIND)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"Serving body state on http://{args.bind}:{args.port}/body-state")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
