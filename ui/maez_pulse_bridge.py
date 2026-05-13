# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Local GPU pulse bridge with loopback-only CORS."""

import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.infra.http_security import is_trusted_loopback_origin


class PulseHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                parts = result.stdout.strip().split(",")
                stats = {
                    "gpu_util": int(parts[0]),
                    "mem_used": int(parts[1]),
                    "mem_total": int(parts[2]),
                }
            except Exception:
                stats = {"gpu_util": 0, "mem_used": 0, "mem_total": 1}

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            origin = self.headers.get("Origin")
            if is_trusted_loopback_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin.strip())
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8765), PulseHandler)
    print("Maez Pulse Bridge running on port 8765")
    server.serve_forever()
