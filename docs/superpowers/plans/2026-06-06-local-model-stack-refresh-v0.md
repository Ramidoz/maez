# Local Model Stack Refresh v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Maez's repeatable local model refresh rail: latest `llama.cpp` side-by-side, a real `:8082` vision endpoint path, content-free candidate packets, and measured judge/main/MTP bakeoffs.

**Architecture:** Keep the live main brain and judge untouched while preparing a new model lane. Repo code gains config honesty and tooling; owner-local service starts/restarts, model admission, and VRAM allocation remain owner breaths.

**Tech Stack:** Python 3.14, `unittest`, `llama.cpp` OpenAI-compatible servers, local systemd user units, Hugging Face model artifacts, existing `scripts/judge_bench` and `scripts/brain_bench`.

---

## File Map

- Create `scripts/model_refresh.py`: content-free helper CLI for runtime discovery, candidate packet writing, `/v1/models` alias verification, VRAM snapshot parsing, and service-template rendering.
- Create `tests/test_model_refresh.py`: unit tests for helper functions, packet schema, no-secret guard, service template safety, and help-flag parsing.
- Modify `skills/screen_perception.py`: remove stale hardcoded vision truth; add env-driven `MAEZ_VISION_URL`, `MAEZ_VISION_MODEL`, and derived probe host/port; tighten docstring.
- Create `tests/test_screen_perception_vision_config.py`: focused tests for vision config defaults, env overrides, probe derivation, and stale judge-port regression.
- Create `docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md`: execution relay with owner-breath boundaries and current candidate order.
- Owner-local output path: `logs/model_refresh/<timestamp>-<candidate>.json` (gitignored by existing `logs/*` rule).

## Task 1: Model Refresh Helper Skeleton + Packet Contract

**Files:**
- Create: `scripts/model_refresh.py`
- Create: `tests/test_model_refresh.py`

- [ ] **Step 1: Write failing tests for packet schema and no-secret guard**

Add this initial test file:

```python
import json
import tempfile
import unittest
from pathlib import Path

from scripts import model_refresh


class PacketTests(unittest.TestCase):
    def test_candidate_packet_required_fields_and_content_free(self):
        packet = model_refresh.build_packet(
            candidate="qwen3vl-4b",
            runtime_path="/home/rohit/llama.cpp-release/llama-deadbeef/llama-server",
            runtime_version="llama.cpp build deadbeef",
            model_repo="Qwen/Qwen3-VL-4B-Instruct-GGUF",
            model_files=["Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"],
            license="apache-2.0",
            quantization="Q4_K_M+Q8_0-mmproj",
            service_port=8082,
            load_status="not_started",
            vram_before_mib=3975,
            vram_after_load_mib=None,
            vram_after_image_mib=None,
            smoke_status="not_run",
            benchmark_status="not_run",
            latency_ms=None,
            decision="candidate",
            rollback="stop llama-vision.service; leave llama-server.service and llama-judge.service unchanged",
        )

        required = {
            "candidate",
            "runtime_path",
            "runtime_version",
            "model_repo",
            "model_files",
            "license",
            "quantization",
            "service_port",
            "load_status",
            "vram_before_mib",
            "vram_after_load_mib",
            "vram_after_image_mib",
            "smoke_status",
            "benchmark_status",
            "latency_ms",
            "decision",
            "rollback",
        }
        self.assertEqual(required, set(packet))
        encoded = json.dumps(packet)
        self.assertNotIn("restore_token", encoded)
        self.assertNotIn("data:image", encoded)
        self.assertNotIn("screen content", encoded.lower())

    def test_invalid_decision_rejected(self):
        with self.assertRaises(ValueError):
            model_refresh.build_packet(
                candidate="bad",
                runtime_path="/tmp/llama-server",
                runtime_version="x",
                model_repo="repo",
                model_files=[],
                license="unknown",
                quantization="q4",
                service_port=8082,
                load_status="not_started",
                vram_before_mib=1,
                vram_after_load_mib=None,
                vram_after_image_mib=None,
                smoke_status="not_run",
                benchmark_status="not_run",
                latency_ms=None,
                decision="ship_it_anyway",
                rollback="rollback",
            )

    def test_write_packet_uses_logs_model_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = {"candidate": "qwen3vl-4b", "decision": "candidate"}
            out = model_refresh.write_packet(packet, root=Path(tmp), timestamp="20260606T120000")
            self.assertEqual(Path(tmp) / "logs" / "model_refresh" / "20260606T120000-qwen3vl-4b.json", out)
            self.assertTrue(out.exists())
            self.assertEqual(packet, json.loads(out.read_text()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh.PacketTests
```

Expected: import failure for `scripts.model_refresh`.

- [ ] **Step 3: Implement the packet helper**

Create `scripts/model_refresh.py`:

```python
#!/usr/bin/env python3
"""Content-free local model refresh helper.

This module prepares evidence packets and service templates for Maez model
refresh candidates. It never starts/stops services and never captures screen
content. Live starts/restarts remain owner breaths.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DECISIONS = {"reject", "retry_with_config", "candidate", "admitted"}
SECRET_PATTERNS = (
    "restore_token",
    "data:image",
    "screen content",
    "BEGIN PRIVATE",
)


def _ensure_content_free(packet: dict[str, Any]) -> None:
    encoded = json.dumps(packet, sort_keys=True)
    lower = encoded.lower()
    for pattern in SECRET_PATTERNS:
        if pattern.lower() in lower:
            raise ValueError(f"packet contains forbidden content marker: {pattern}")


def build_packet(
    *,
    candidate: str,
    runtime_path: str,
    runtime_version: str,
    model_repo: str,
    model_files: list[str],
    license: str,
    quantization: str,
    service_port: int,
    load_status: str,
    vram_before_mib: int | None,
    vram_after_load_mib: int | None,
    vram_after_image_mib: int | None,
    smoke_status: str,
    benchmark_status: str,
    latency_ms: int | None,
    decision: str,
    rollback: str,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    packet = {
        "candidate": candidate,
        "runtime_path": runtime_path,
        "runtime_version": runtime_version,
        "model_repo": model_repo,
        "model_files": model_files,
        "license": license,
        "quantization": quantization,
        "service_port": service_port,
        "load_status": load_status,
        "vram_before_mib": vram_before_mib,
        "vram_after_load_mib": vram_after_load_mib,
        "vram_after_image_mib": vram_after_image_mib,
        "smoke_status": smoke_status,
        "benchmark_status": benchmark_status,
        "latency_ms": latency_ms,
        "decision": decision,
        "rollback": rollback,
    }
    _ensure_content_free(packet)
    return packet


def write_packet(packet: dict[str, Any], *, root: Path, timestamp: str | None = None) -> Path:
    _ensure_content_free(packet)
    ts = timestamp or time.strftime("%Y%m%dT%H%M%S")
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(packet["candidate"])).strip("-")
    out_dir = root / "logs" / "model_refresh"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}-{candidate}.json"
    out_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-empty-packet", action="store_true")
    parser.add_argument("--candidate", default="qwen3vl-4b")
    args = parser.parse_args()
    if args.write_empty_packet:
        packet = build_packet(
            candidate=args.candidate,
            runtime_path="",
            runtime_version="",
            model_repo="",
            model_files=[],
            license="unknown",
            quantization="",
            service_port=8082,
            load_status="not_started",
            vram_before_mib=None,
            vram_after_load_mib=None,
            vram_after_image_mib=None,
            smoke_status="not_run",
            benchmark_status="not_run",
            latency_ms=None,
            decision="candidate",
            rollback="",
        )
        print(write_packet(packet, root=Path.cwd()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh.PacketTests
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/model_refresh.py tests/test_model_refresh.py
git commit -m "feat(models): add refresh packet helper"
```

Include in commit body:

```text
## Predicted effect

No live behavior changes. The new helper can write content-free local model-refresh packets under logs/model_refresh/ and rejects packet decisions outside the closed enum.
```

## Task 2: Runtime Discovery, Alias Verification, and VRAM Parsing

**Files:**
- Modify: `scripts/model_refresh.py`
- Modify: `tests/test_model_refresh.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
class RuntimeDiscoveryTests(unittest.TestCase):
    def test_parse_llama_help_detects_mmproj_and_mtp(self):
        help_text = """
        --mmproj FILE
        --mmproj-offload
        --spec-type none,draft,eagle3,mtp,ngram-simple
        """
        support = model_refresh.parse_llama_help(help_text)
        self.assertTrue(support["mmproj"])
        self.assertTrue(support["mmproj_offload"])
        self.assertTrue(support["mtp"])

    def test_parse_llama_help_reports_missing_mtp_without_crash(self):
        help_text = "--mmproj FILE\n--spec-type none,draft,eagle3,ngram-simple\n"
        support = model_refresh.parse_llama_help(help_text)
        self.assertTrue(support["mmproj"])
        self.assertFalse(support["mtp"])

    def test_parse_nvidia_smi_csv(self):
        row = "NVIDIA GeForce RTX 4090, 24564 MiB, 20053 MiB, 3975 MiB"
        parsed = model_refresh.parse_nvidia_smi_csv(row)
        self.assertEqual(24564, parsed["total_mib"])
        self.assertEqual(20053, parsed["used_mib"])
        self.assertEqual(3975, parsed["free_mib"])

    def test_verify_model_alias_from_models_response(self):
        response = {"data": [{"id": "maez-vision", "aliases": ["maez-vision"]}]}
        self.assertTrue(model_refresh.response_has_model_alias(response, "maez-vision"))
        self.assertFalse(model_refresh.response_has_model_alias(response, "qwen2.5-vl-3b"))
```

- [ ] **Step 2: Run failing tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh.RuntimeDiscoveryTests
```

Expected: missing functions.

- [ ] **Step 3: Implement discovery helpers**

Add to `scripts/model_refresh.py`:

```python
def parse_llama_help(help_text: str) -> dict[str, bool]:
    spec_line = ""
    for line in help_text.splitlines():
        if "--spec-type" in line:
            spec_line = line.lower()
            break
    return {
        "mmproj": "--mmproj" in help_text,
        "mmproj_offload": "--mmproj-offload" in help_text,
        "mtp": "mtp" in spec_line,
    }


def parse_nvidia_smi_csv(row: str) -> dict[str, int]:
    parts = [p.strip() for p in row.split(",")]
    if len(parts) != 4:
        raise ValueError(f"expected 4 nvidia-smi csv fields, got {len(parts)}")

    def mib(text: str) -> int:
        match = re.search(r"(\\d+)\\s*MiB", text)
        if not match:
            raise ValueError(f"missing MiB value: {text}")
        return int(match.group(1))

    return {
        "total_mib": mib(parts[1]),
        "used_mib": mib(parts[2]),
        "free_mib": mib(parts[3]),
    }


def response_has_model_alias(response: dict[str, Any], alias: str) -> bool:
    for item in response.get("data", []):
        names = {item.get("id"), item.get("model"), item.get("name")}
        names.update(item.get("aliases") or [])
        if alias in names:
            return True
    for item in response.get("models", []):
        names = {item.get("id"), item.get("model"), item.get("name")}
        names.update(item.get("aliases") or [])
        if alias in names:
            return True
    return False
```

- [ ] **Step 4: Add CLI hooks for runtime discovery**

Modify `main()`:

```python
    parser.add_argument("--llama-server", help="Path to llama-server for help/version discovery")
    parser.add_argument("--nvidia-smi-row", help="Parse one nvidia-smi CSV row and print JSON")
```

Then before `return 0`:

```python
    if args.llama_server:
        proc = subprocess.run(
            [args.llama_server, "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        print(json.dumps(parse_llama_help(proc.stdout), sort_keys=True))
        return 0
    if args.nvidia_smi_row:
        print(json.dumps(parse_nvidia_smi_csv(args.nvidia_smi_row), sort_keys=True))
        return 0
```

- [ ] **Step 5: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add scripts/model_refresh.py tests/test_model_refresh.py
git commit -m "feat(models): discover runtime and model endpoint support"
```

Commit body:

```text
## Predicted effect

No live behavior changes. The refresh helper can now report whether a candidate llama.cpp runtime exposes mmproj/MTP support, parse VRAM snapshots, and verify that a served endpoint actually exposes the configured model alias.
```

## Task 3: Screen Perception Vision Config Honesty

**Files:**
- Modify: `skills/screen_perception.py`
- Create: `tests/test_screen_perception_vision_config.py`

- [ ] **Step 1: Write failing tests**

Create:

```python
import importlib
import os
import unittest
from unittest import mock


class VisionConfigTests(unittest.TestCase):
    def _load(self, env):
        with mock.patch.dict(os.environ, env, clear=False):
            import skills.screen_perception as sp
            return importlib.reload(sp)

    def test_defaults_point_to_dedicated_vision_endpoint_not_judge(self):
        sp = self._load({
            "MAEZ_VISION_URL": "",
            "MAEZ_VISION_MODEL": "",
        })
        self.assertEqual("http://127.0.0.1:8082/v1/chat/completions", sp.VISION_URL)
        self.assertEqual("maez-vision", sp.VISION_MODEL)
        self.assertEqual("127.0.0.1", sp._VISION_PROBE_HOST)
        self.assertEqual(8082, sp._VISION_PROBE_PORT)

    def test_env_overrides_url_model_and_probe_port(self):
        sp = self._load({
            "MAEZ_VISION_URL": "http://127.0.0.1:8099/v1/chat/completions",
            "MAEZ_VISION_MODEL": "qwen3vl-4b-test",
        })
        self.assertEqual("http://127.0.0.1:8099/v1/chat/completions", sp.VISION_URL)
        self.assertEqual("qwen3vl-4b-test", sp.VISION_MODEL)
        self.assertEqual(8099, sp._VISION_PROBE_PORT)

    def test_docstring_no_longer_claims_qwen25_or_port_8081_vision_service(self):
        sp = self._load({})
        doc = sp.__doc__ or ""
        self.assertNotIn("Qwen2.5-VL-3B", doc)
        self.assertNotIn("port 8081", doc)
        self.assertNotIn("llama-server-vision.service on port 8081", doc)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_screen_perception_vision_config
```

Expected: failures because defaults still point at `8081` and stale docstring text exists.

- [ ] **Step 3: Implement config helpers**

Modify top docstring in `skills/screen_perception.py` to state:

```python
"""
screen_perception.py — Screen awareness for Maez

Captures a governed screenshot of the owner's display and sends it to a
dedicated local multimodal endpoint. The endpoint is configured by
MAEZ_VISION_URL / MAEZ_VISION_MODEL and defaults to a separate local vision
server on 127.0.0.1:8082, not the grounding judge on 8081.

Screen perception remains default-off under ADR 0009 and is guarded by the
privacy curtain, active-window preflight, third-party minimization, and
egress-origin tagging.
"""
```

Add imports:

```python
from urllib.parse import urlparse
```

Replace constants:

```python
def _env_or_default(name: str, default: str) -> str:
    val = os.environ.get(name, "").strip()
    return val or default


VISION_URL = _env_or_default(
    "MAEZ_VISION_URL",
    "http://127.0.0.1:8082/v1/chat/completions",
)
VISION_MODEL = _env_or_default("MAEZ_VISION_MODEL", "maez-vision")
VISION_MAX_DIM = int(_env_or_default("MAEZ_VISION_MAX_DIM", "640"))
```

Replace probe host/port constants with:

```python
def _probe_host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 80


_VISION_PROBE_HOST, _VISION_PROBE_PORT = _probe_host_port(VISION_URL)
```

Update comments around the probe to remove the stale "Port 8081 has been dead" claim and replace it with:

```python
# Fast-fail before screenshot capture when the configured local vision
# endpoint is unavailable. The endpoint must be a real multimodal server;
# the grounding judge is text-only and is deliberately not used for vision.
```

Update the call comment above `requests.post`:

```python
    # Call the configured local multimodal vision endpoint. The model alias
    # must match /v1/models on that endpoint; stale aliases are caught by the
    # model refresh witness before live activation.
```

- [ ] **Step 4: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_screen_perception_vision_config tests.test_screen_perception_gate tests.test_screen_perception_lens tests.test_screen_perception_v1a
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_vision_config.py
git commit -m "fix(body): point screen vision config at dedicated endpoint"
```

Commit body:

```text
## Predicted effect

With MAEZ_SCREEN_PERCEPTION enabled and a real local vision server on 127.0.0.1:8082, screen perception will probe and call that dedicated multimodal endpoint instead of the text-only judge on 8081. With no vision server running, behavior remains honestly unavailable rather than calling the judge.
```

## Task 4: Service Template Rendering for `llama-vision.service`

**Files:**
- Modify: `scripts/model_refresh.py`
- Modify: `tests/test_model_refresh.py`
- Create: `docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md`

- [ ] **Step 1: Add failing service-template tests**

Append:

```python
class VisionServiceTemplateTests(unittest.TestCase):
    def test_render_vision_service_uses_8082_and_does_not_touch_judge(self):
        text = model_refresh.render_vision_service(
            runtime="/home/rohit/llama.cpp-release/llama-deadbeef/llama-server",
            model="/home/rohit/maez/models/llamacpp/vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf",
            mmproj="/home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf",
            alias="maez-vision",
            port=8082,
            ctx_size=4096,
        )
        self.assertIn("Description=llama.cpp vision server", text)
        self.assertIn("--port 8082", text)
        self.assertIn("--alias maez-vision", text)
        self.assertIn("--mmproj /home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf", text)
        self.assertNotIn("--port 8081", text)
        self.assertNotIn("llama-judge", text)

    def test_render_vision_service_rejects_judge_port(self):
        with self.assertRaises(ValueError):
            model_refresh.render_vision_service(
                runtime="/bin/llama-server",
                model="/models/v.gguf",
                mmproj="/models/mmproj.gguf",
                alias="maez-vision",
                port=8081,
                ctx_size=4096,
            )
```

- [ ] **Step 2: Run failing tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh.VisionServiceTemplateTests
```

Expected: missing function.

- [ ] **Step 3: Implement service rendering**

Add:

```python
def render_vision_service(
    *,
    runtime: str,
    model: str,
    mmproj: str,
    alias: str,
    port: int,
    ctx_size: int,
) -> str:
    if port == 8081:
        raise ValueError("vision service must not use the judge port 8081")
    if port == 8080:
        raise ValueError("vision service must not use the main brain port 8080")
    return f"""[Unit]
Description=llama.cpp vision server (Maez local multimodal endpoint)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/rohit/maez
ExecStart={runtime} \\
  -m {model} \\
  --mmproj {mmproj} \\
  --alias {alias} \\
  --host 127.0.0.1 \\
  --port {port} \\
  --ctx-size {ctx_size} \\
  --n-gpu-layers 999 \\
  --flash-attn on \\
  --cache-type-k q4_0 \\
  --cache-type-v q4_0 \\
  --image-max-tokens 1024
Restart=on-failure
Environment=GGML_VK_VISIBLE_DEVICES=0

[Install]
WantedBy=default.target
"""
```

Add CLI args:

```python
    parser.add_argument("--render-vision-service", action="store_true")
    parser.add_argument("--runtime", default="")
    parser.add_argument("--model-path", default="")
    parser.add_argument("--mmproj-path", default="")
    parser.add_argument("--alias", default="maez-vision")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--ctx-size", type=int, default=4096)
```

Add handling:

```python
    if args.render_vision_service:
        print(render_vision_service(
            runtime=args.runtime,
            model=args.model_path,
            mmproj=args.mmproj_path,
            alias=args.alias,
            port=args.port,
            ctx_size=args.ctx_size,
        ))
        return 0
```

- [ ] **Step 4: Create the execution handoff**

Create `docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md`:

````markdown
# Handoff -> Codex: Local Model Stack Refresh v0

## Job

Build the refresh rail that keeps Maez's local model stack current without disturbing the live brain/judge by default.

## Current facts

- Main brain: `:8080` / `qwen36-27b`.
- Judge: `:8081` / `maez-judge`.
- Vision: absent; `screen_perception.py` must point to `:8082`.
- Current free VRAM snapshot: about 3975 MiB. Treat this as a snapshot, not proof of always-on fit.

## First candidate

Provision candidate artifacts for `Qwen/Qwen3-VL-4B-Instruct-GGUF`:

- `Qwen3VL-4B-Instruct-Q4_K_M.gguf`
- `mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf` unless the F16 projector is intentionally chosen and VRAM allows it.

Pin source URLs and record hashes. The model GGUF is not currently on disk; only an older loose F16 projector exists.

## Owner breaths

Codex prepares files, tests, and service text. Rohit authorizes downloads, starts/stops user services, restarts Maez, and admits any live model.

## Witness order

1. Verify latest or candidate `llama.cpp` side-by-side.
2. Start `llama-vision.service` on `:8082`.
3. Verify `/v1/models` exposes `maez-vision`.
4. Run a tiny image smoke.
5. Run Full Lens witness through `observe()`.
6. Measure VRAM after load and after real image inference.
7. Only then consider judge retirement benchmark.
````

- [ ] **Step 5: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add scripts/model_refresh.py tests/test_model_refresh.py docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md
git commit -m "feat(models): render dedicated vision service template"
```

Commit body:

```text
## Predicted effect

No live services change. The refresh helper can render a local llama-vision.service template on a non-judge port, with model alias and mmproj explicitly configured for owner-reviewed installation.
```

## Task 5: Vision Smoke Helper and Alias Truth Witness

**Files:**
- Modify: `scripts/model_refresh.py`
- Modify: `tests/test_model_refresh.py`

- [ ] **Step 1: Add failing smoke helper tests**

Append:

```python
class VisionSmokeTests(unittest.TestCase):
    def test_build_tiny_image_payload_is_openai_compatible_and_small(self):
        payload = model_refresh.build_vision_smoke_payload(
            model="maez-vision",
            png_base64="abc123",
            prompt="Name the color.",
        )
        self.assertEqual("maez-vision", payload["model"])
        content = payload["messages"][0]["content"]
        self.assertEqual("text", content[0]["type"])
        self.assertEqual("image_url", content[1]["type"])
        self.assertIn("data:image/png;base64,abc123", content[1]["image_url"]["url"])
        self.assertLessEqual(payload["max_tokens"], 64)

    def test_parse_smoke_result_content_free(self):
        response = {"choices": [{"message": {"content": "The square is red."}}]}
        result = model_refresh.parse_vision_smoke_response(response, status_code=200, latency_ms=321)
        self.assertEqual({"status": "ok", "latency_ms": 321}, result)

    def test_parse_smoke_error_does_not_include_raw_body(self):
        result = model_refresh.parse_vision_smoke_response(
            {"error": "secret screen content"},
            status_code=500,
            latency_ms=123,
        )
        self.assertEqual("error", result["status"])
        self.assertEqual(500, result["status_code"])
        self.assertNotIn("secret", str(result).lower())
```

- [ ] **Step 2: Run failing tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh.VisionSmokeTests
```

Expected: missing functions.

- [ ] **Step 3: Implement smoke helpers**

Add:

```python
def build_vision_smoke_payload(*, model: str, png_base64: str, prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_base64}"}},
            ],
        }],
        "temperature": 0.0,
        "max_tokens": 64,
    }


def parse_vision_smoke_response(response: dict[str, Any], *, status_code: int, latency_ms: int) -> dict[str, Any]:
    if status_code != 200:
        return {"status": "error", "status_code": status_code, "latency_ms": latency_ms}
    choices = response.get("choices") or []
    content = ""
    if choices:
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
    return {"status": "ok" if content else "empty", "latency_ms": latency_ms}
```

- [ ] **Step 4: Add CLI note, not live network code**

Do not add live HTTP calls in this task. The live smoke will be owner-run in the witness step after the service starts. Keep this helper pure and unit-testable.

- [ ] **Step 5: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_model_refresh
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add scripts/model_refresh.py tests/test_model_refresh.py
git commit -m "feat(models): add content-free vision smoke helpers"
```

Commit body:

```text
## Predicted effect

No live behavior changes. The refresh helper can construct a bounded local vision smoke request and reduce responses to content-free status/latency evidence.
```

## Task 6: Owner-Run Candidate Provisioning Runbook

**Files:**
- Modify: `docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md`

- [ ] **Step 1: Extend the handoff with concrete owner-run commands**

Append:

````markdown
## Owner-run candidate commands

These commands are a runbook, not autonomous execution. Rohit decides when to run each.

### Download and verify candidate artifacts

Target directory:

```bash
mkdir -p /home/rohit/maez/models/llamacpp/vision
```

Candidate files:

```text
https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/Qwen3VL-4B-Instruct-Q4_K_M.gguf
https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
```

After download, record:

```bash
sha256sum /home/rohit/maez/models/llamacpp/vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf
sha256sum /home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf
```

### Runtime support probe

```bash
/home/rohit/llama.cpp-release/llama-b9124/llama-server --help | rg -- '--mmproj|--spec-type|mtp'
```

If `b9124` cannot load the candidate or lacks required support, build latest llama.cpp side-by-side under:

```text
/home/rohit/llama.cpp-release/llama-<commit>/
```

Do not overwrite `llama-b9124`.

### Render service template

```bash
cd /home/rohit/maez
.venv/bin/python -B scripts/model_refresh.py --render-vision-service \
  --runtime /home/rohit/llama.cpp-release/llama-b9124/llama-server \
  --model-path /home/rohit/maez/models/llamacpp/vision/Qwen3VL-4B-Instruct-Q4_K_M.gguf \
  --mmproj-path /home/rohit/maez/models/llamacpp/vision/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf \
  --alias maez-vision \
  --port 8082 \
  --ctx-size 4096
```

Write the rendered unit to:

```text
/home/rohit/.config/systemd/user/llama-vision.service
```

### Owner breath: start vision service

```bash
systemctl --user daemon-reload
systemctl --user start llama-vision.service
curl -s http://127.0.0.1:8082/v1/models
```

The `/v1/models` response must expose `maez-vision`; otherwise stop and fix alias/config before touching Maez.

### VRAM measurements

Record three snapshots:

```bash
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader
```

1. before starting `llama-vision.service`;
2. after `/v1/models` succeeds;
3. after a real image inference.

Do not call the service "always-on fit" from load alone. Fit means load plus real image inference plus normal daemon coexistence.
````

- [ ] **Step 2: Commit the runbook update**

```bash
git add docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md
git commit -m "docs(models): add owner-run vision provisioning runbook"
```

No `## Predicted effect`; doc/runbook only.

## Task 7: Verification Floor and Handoff Completion

**Files:**
- Existing touched files only.

- [ ] **Step 1: Run focused tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest \
  tests.test_model_refresh \
  tests.test_screen_perception_vision_config \
  tests.test_screen_perception_gate \
  tests.test_screen_perception_lens \
  tests.test_screen_perception_v1a
```

Expected: all focused tests pass.

- [ ] **Step 2: Run egress blast-radius tests**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest \
  tests.test_egress_provenance \
  tests.test_recall_origin_egress_canary \
  tests.test_privacy_egress_gate
```

Expected: all pass; screen-derived origin remains protected.

- [ ] **Step 3: Run full discover**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'
```

Expected: no new failures in touched tests. If ambient floor differs, report exact count and compare to main floor; do not hide failures.

- [ ] **Step 4: Final implementation handoff**

Report:

```text
Branch/result:
- screen perception now defaults to :8082 / maez-vision
- model_refresh helper supports packet, runtime, service, smoke helpers
- no services started/stopped
- owner-run provisioning runbook ready
- focused tests: <result>
- full discover: <result>
- next owner breath: download/verify model, start llama-vision.service, run Full Lens witness
```

- [ ] **Step 5: Commit any final doc-only correction if needed**

Only commit if Step 3 revealed a wording mismatch in the handoff. Do not alter behavior in this cleanup task.

```bash
git add docs/handoffs/2026-06-06-codex-local-model-stack-refresh-v0-execution.md
git commit -m "docs(models): clarify local model refresh witness"
```

No `## Predicted effect`; doc-only.

## Post-Plan Owner Witness

After implementation is merged and the owner runs the service breath:

1. `:8082/v1/models` exposes the configured `MAEZ_VISION_MODEL`.
2. A tiny image smoke returns `ok`.
3. `observe()` on an ordinary non-excluded window returns `state=ok`.
4. A sensitive window still returns `excluded` before capture.
5. VRAM is recorded after load and after real image inference.
6. Judge bench is run against `:8082` only if the owner wants to test judge retirement.
7. Main brain/MTP bakeoff remains separate until vision is real.
