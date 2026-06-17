# Body Runtime Truth v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**As-built branch status (2026-06-17):** implemented and branch-verified on
`maez-coherence-organism`; ledger row is `BUILT_BRANCH_VERIFIED`. The plan below
is the historical implementation recipe, not pending work. The current branch
handoff is `docs/handoffs/2026-06-17-maez-coherence-organism-progress.md`.
Live witness still requires the owner-gated merge/restart path.

**Goal:** Add one content-free runtime service witness so Maez can distinguish configured organs from working organs.

**Architecture:** `core.infra.runtime_services` owns read-only probes for service unit, port, and contract truth. `/health.body` exposes the snapshot, `capability_card` consumes the support-verifier status for support honesty organs, and `scripts.maez_runtime_services_probe` gives a terminal witness. No service is started, stopped, enabled, installed, or restarted.

**Tech Stack:** Python stdlib (`socket`, `subprocess`, `urllib.request`, `json`), existing `strict_env_flag`, existing `served_model_alias`, MiniCheck's content-free `/health` runtime contract, `unittest`.

**Post-review correction:** Runtime body truth must stay content-free. MiniCheck
health is checked with `GET /health`, not synthetic `POST /support`; SearXNG v0
uses unit/port liveness and does not issue a search query.

---

## File Map

- Create: `core/infra/runtime_services.py` - content-free runtime service registry and probes.
- Create: `tests/test_runtime_services.py` - unit tests for status rules, faked unit/port/HTTP probes, and probe CLI exit rules.
- Create: `scripts/maez_runtime_services_probe.py` - terminal witness that prints the runtime-services snapshot JSON and returns `0`, `1`, or `2`.
- Modify: `daemon/maez_daemon.py` - add `"runtime_services"` under `_body_health(...)`.
- Modify: `core/cognition/capability_card.py` - render support gate / grounding shadow from `support_honesty_status(...)`.
- Modify: `tests/test_capability_card.py` - support honesty organs degrade when the backing verifier is unavailable.
- Modify: `tests/test_maez_body_organ_view.py` - `/health.body` contains content-free `runtime_services`.
- Optionally modify: `docs/MAEZ_BUILD_LEDGER.md` - record the branch-verified body-runtime-truth row after tests pass.

---

### Task 0: Runtime Service Registry Tests

**Files:**
- Create: `tests/test_runtime_services.py`
- Create later: `core/infra/runtime_services.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_runtime_services.py` with these tests:

```python
from __future__ import annotations

import json
import unittest
from unittest import mock


class RuntimeServiceSnapshotTests(unittest.TestCase):
    def setUp(self):
        from core.infra import runtime_services as rs

        rs.invalidate_cache()
        self.addCleanup(rs.invalidate_cache)

    def _healthy_fakes(self):
        return {
            "unit_probe": lambda name, scope="user", timeout_s=0.35: {
                "name": name,
                "scope": scope,
                "load_state": "loaded",
                "active_state": "active",
                "enabled_state": "enabled",
            },
            "port_probe": lambda host, port, timeout_s=0.35: True,
            "http_json": lambda method, url, payload=None, timeout_s=0.35: {
                "ok": True,
                "json": {"verdict": "SUPPORTED", "score": 0.99, "data": []},
                "latency_ms": 1,
            },
            "model_alias": lambda default=None, timeout_s=0.35: "qwen36-27b",
        }

    def test_snapshot_shape_includes_v0_services(self):
        from core.infra import runtime_services as rs

        with mock.patch.dict("os.environ", {}, clear=True):
            snap = rs.runtime_services_snapshot(**self._healthy_fakes())

        self.assertEqual(snap["schema_version"], "maez_runtime_services.v0")
        self.assertIn(snap["overall"], {"healthy", "degraded", "unknown"})
        for key in (
            "primary_brain",
            "maez_daemon",
            "maez_web",
            "search_body",
            "support_verifier",
            "subscription_proxy",
            "vision_body",
            "overclaim_judge",
        ):
            self.assertIn(key, snap["services"])

    def test_support_verifier_asleep_when_flags_off(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        with mock.patch.dict("os.environ", {}, clear=True):
            service = rs.runtime_services_snapshot(**fakes)["services"]["support_verifier"]

        self.assertFalse(service["configured"])
        self.assertEqual(service["required_by"], [])
        self.assertEqual(service["status"], "asleep")

    def test_support_verifier_degraded_when_required_but_contract_fails(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        fakes["http_json"] = lambda method, url, payload=None, timeout_s=0.35: {
            "ok": True,
            "json": {"unexpected": True},
            "latency_ms": 2,
        }
        with mock.patch.dict("os.environ", {"MAEZ_SUPPORT_GATE_ENABLED": "1"}, clear=True):
            snap = rs.runtime_services_snapshot(**fakes)
        service = snap["services"]["support_verifier"]

        self.assertEqual(service["status"], "degraded")
        self.assertIn("contract_unhealthy", service["degraded_reasons"])
        self.assertEqual(snap["overall"], "degraded")

    def test_support_verifier_healthy_only_with_contract_fields(self):
        from core.infra import runtime_services as rs

        with mock.patch.dict("os.environ", {"MAEZ_SUPPORT_GATE_ENABLED": "1"}, clear=True):
            service = rs.runtime_services_snapshot(**self._healthy_fakes())["services"][
                "support_verifier"
            ]

        self.assertEqual(service["status"], "healthy")
        self.assertTrue(service["contract"]["ok"])
        self.assertEqual(service["contract"]["status"], "ok")
        self.assertEqual(service["contract"]["contract_name"], "minicheck_support.v1")

    def test_optional_services_do_not_degrade_overall_when_asleep(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        fakes["port_probe"] = lambda host, port, timeout_s=0.35: port not in (11438,)
        with mock.patch.dict("os.environ", {}, clear=True):
            snap = rs.runtime_services_snapshot(**fakes)

        self.assertEqual(snap["services"]["subscription_proxy"]["status"], "asleep")
        self.assertEqual(snap["overall"], "healthy")

    def test_unit_probe_handles_timeout_and_missing_systemctl(self):
        from core.infra import runtime_services as rs

        timeout = rs._parse_systemctl_show("", timed_out=True, unit="x.service", scope="user")
        missing = rs._parse_systemctl_show(None, timed_out=False, unit="x.service", scope="user")

        self.assertEqual(timeout["load_state"], "unknown")
        self.assertEqual(timeout["active_state"], "unknown")
        self.assertEqual(missing["load_state"], "unknown")
        self.assertEqual(missing["active_state"], "unknown")

    def test_probe_main_exits_two_on_degraded_required_service(self):
        from scripts import maez_runtime_services_probe as probe

        degraded = {
            "schema_version": "maez_runtime_services.v0",
            "overall": "degraded",
            "services": {"support_verifier": {"status": "degraded"}},
        }
        with mock.patch.object(probe, "runtime_services_snapshot", return_value=degraded):
            self.assertEqual(probe.main([]), 2)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_runtime_services
```

Expected: import failure for `core.infra.runtime_services` or missing functions.

- [ ] **Step 3: Implement minimal registry**

Create `core/infra/runtime_services.py` with:

```python
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from core.infra.env_flags import strict_env_flag
from core.routing.llm_client import served_model_alias

SCHEMA_VERSION = "maez_runtime_services.v0"
_CACHE: dict[str, Any] | None = None
_CACHE_TS = 0.0
_TTL_S = 15.0


def invalidate_cache() -> None:
    global _CACHE, _CACHE_TS
    _CACHE = None
    _CACHE_TS = 0.0


def _flag_enabled(name: str) -> bool:
    return strict_env_flag(name)


def _parse_systemctl_show(
    output: str | None,
    *,
    timed_out: bool,
    unit: str,
    scope: str,
) -> dict[str, str]:
    if timed_out or output is None:
        state = "unknown"
        return {
            "name": unit,
            "scope": scope,
            "load_state": state,
            "active_state": state,
            "enabled_state": state,
        }
    values = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value or "unknown"
    return {
        "name": unit,
        "scope": scope,
        "load_state": values.get("LoadState", "unknown"),
        "active_state": values.get("ActiveState", "unknown"),
        "enabled_state": values.get("UnitFileState", "unknown"),
    }


def _probe_unit(unit: str, *, scope: str = "user", timeout_s: float = 0.35) -> dict[str, str]:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return _parse_systemctl_show(None, timed_out=False, unit=unit, scope=scope)
    cmd = [
        systemctl,
        "--user" if scope == "user" else "--system",
        "show",
        unit,
        "--property=LoadState,ActiveState,UnitFileState",
        "--no-pager",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _parse_systemctl_show("", timed_out=True, unit=unit, scope=scope)
    except OSError:
        return _parse_systemctl_show(None, timed_out=False, unit=unit, scope=scope)
    return _parse_systemctl_show(result.stdout, timed_out=False, unit=unit, scope=scope)


def _probe_port(host: str, port: int, *, timeout_s: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float = 0.35,
) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read(4096)
        return {
            "ok": True,
            "json": json.loads(raw.decode("utf-8") or "{}"),
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return {
            "ok": False,
            "json": {},
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }


def _required_by(*flags: str) -> list[str]:
    return [flag for flag in flags if _flag_enabled(flag)]


def _status_for(required_by: list[str], unit: dict, port: dict | None, contract: dict | None):
    if not required_by:
        return "asleep", []
    reasons = []
    if unit.get("load_state") not in {"loaded", "unknown"}:
        reasons.append("unit_not_loaded")
    if unit.get("active_state") not in {"active", "unknown"}:
        reasons.append("unit_inactive")
    if port is not None and not port.get("reachable", False):
        reasons.append("port_unreachable")
    if contract is not None and not contract.get("ok", False):
        reasons.append("contract_unhealthy")
    return ("degraded", reasons) if reasons else ("healthy", [])


def _support_contract(
    http_json: Callable[..., dict[str, Any]],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    response = http_json(
        "POST",
        "http://127.0.0.1:8083/health",
        payload=None,
        timeout_s=timeout_s,
    )
    data = response.get("json") or {}
    contract = data.get("contract")
    status = data.get("status")
    ok = (
        bool(response.get("ok"))
        and status == "ok"
        and contract == "minicheck_support.v1"
    )
    return {
        "kind": "http_support_health",
        "ok": ok,
        "status": status if isinstance(status, str) else "unknown",
        "contract_name": contract if isinstance(contract, str) else "unknown",
        "latency_ms": int(response.get("latency_ms", 0) or 0),
    }


def runtime_services_snapshot(
    timeout_s: float = 0.35,
    *,
    unit_probe: Callable[..., dict[str, str]] = _probe_unit,
    port_probe: Callable[..., bool] = _probe_port,
    http_json: Callable[..., dict[str, Any]] = _http_json,
    model_alias: Callable[..., str] = served_model_alias,
) -> dict[str, Any]:
    del model_alias
    services: dict[str, Any] = {}

    def add(
        key: str,
        *,
        required_by: list[str],
        unit_name: str,
        port: tuple[str, int] | None = None,
        contract: dict[str, Any] | None = None,
    ) -> None:
        unit = unit_probe(unit_name, scope="user", timeout_s=timeout_s)
        port_info = None
        if port is not None:
            host, port_number = port
            port_info = {
                "host": host,
                "port": port_number,
                "reachable": port_probe(host, port_number, timeout_s=timeout_s),
            }
        status, reasons = _status_for(required_by, unit, port_info, contract)
        services[key] = {
            "configured": bool(required_by),
            "required_by": required_by,
            "unit": unit,
            "port": port_info,
            "contract": contract,
            "status": status,
            "degraded_reasons": reasons,
        }

    add("primary_brain", required_by=["always"], unit_name="llama-server.service", port=("127.0.0.1", 8080))
    add("maez_daemon", required_by=["always"], unit_name="maez.service", port=("127.0.0.1", 11435))
    add("maez_web", required_by=_required_by("MAEZ_COCKPIT_REAL_STATE", "MAEZ_COCKPIT_CORE", "MAEZ_S7_CEREMONY_BRIDGE_ENABLED"), unit_name="maez-web.service", port=("127.0.0.1", 11437))
    add("search_body", required_by=_required_by("MAEZ_SEARCH_AS_SENSE_ENABLED"), unit_name="maez-searxng.service", port=("127.0.0.1", 8888), contract={"kind": "tcp_liveness_only", "ok": True, "latency_ms": 0} if _flag_enabled("MAEZ_SEARCH_AS_SENSE_ENABLED") else None)
    support_required = _required_by("MAEZ_SUPPORT_GATE_ENABLED", "MAEZ_GROUNDING_SHADOW_ENABLED")
    support_contract = _support_contract(http_json, timeout_s=timeout_s) if support_required else None
    add("support_verifier", required_by=support_required, unit_name="minicheck-verifier.service", port=("127.0.0.1", 8083), contract=support_contract)
    add("subscription_proxy", required_by=[], unit_name="maez-subscription-proxy.service", port=("127.0.0.1", 11438))
    add("vision_body", required_by=_required_by("MAEZ_SCREEN_PERCEPTION"), unit_name="maez-vision.service", port=("127.0.0.1", 8082))
    add("overclaim_judge", required_by=[], unit_name="llama-judge.service", port=("127.0.0.1", 8081))

    overall = "degraded" if any(s["status"] == "degraded" for s in services.values()) else "healthy"
    return {
        "schema_version": SCHEMA_VERSION,
        "overall": overall,
        "generated_at": time.time(),
        "services": services,
    }


def runtime_service_status(name: str, timeout_s: float = 0.35) -> dict[str, Any]:
    return runtime_services_snapshot(timeout_s=timeout_s)["services"].get(
        name,
        {"status": "unknown", "degraded_reasons": ["unknown_service"]},
    )


def support_honesty_status(timeout_s: float = 0.35) -> str:
    if not (_flag_enabled("MAEZ_SUPPORT_GATE_ENABLED") or _flag_enabled("MAEZ_GROUNDING_SHADOW_ENABLED")):
        return "off"
    try:
        return runtime_service_status("support_verifier", timeout_s=timeout_s).get("status", "unknown")
    except Exception:
        return "unknown"
```

- [ ] **Step 4: Add the CLI script**

Create `scripts/maez_runtime_services_probe.py`:

```python
from __future__ import annotations

import json
import sys

from core.infra.runtime_services import runtime_services_snapshot


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        snapshot = runtime_services_snapshot()
    except Exception as exc:
        print(json.dumps({"schema_version": "maez_runtime_services.v0", "overall": "unknown", "error_class": exc.__class__.__name__}, sort_keys=True))
        return 1
    print(json.dumps(snapshot, sort_keys=True, indent=2))
    return 2 if snapshot.get("overall") == "degraded" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_runtime_services
```

Expected: `OK`.

---

### Task 1: Body Health Integration

**Files:**
- Modify: `daemon/maez_daemon.py`
- Modify: `tests/test_maez_body_organ_view.py`

- [ ] **Step 1: Write failing body-health test**

Add to `BodyHealthProjectionTests`:

```python
    def test_body_health_includes_runtime_services(self):
        import daemon.maez_daemon as md

        daemon = SimpleNamespace(
            cycle_count=1,
            lived_episodes=None,
            dream=None,
            _github_health=lambda: {"mode": "disabled", "source_kind": "github.repo_count", "state": "disabled", "staged_records": 0, "error_class": ""},
        )
        runtime = {
            "schema_version": "maez_runtime_services.v0",
            "overall": "healthy",
            "services": {"support_verifier": {"status": "asleep"}},
        }
        with mock.patch("daemon.maez_daemon.runtime_services_snapshot", return_value=runtime), mock.patch(
            "daemon.maez_daemon.served_model_alias", return_value="qwen36-27b"
        ):
            body = md.MaezDaemon._body_health(
                daemon,
                camera_presence={},
                desktop_presence={},
                memory_stats={},
                reasoning_loop={},
                system={},
            )

        self.assertEqual(body["runtime_services"], runtime)
        encoded = json.dumps(body, sort_keys=True)
        self.assertNotIn("Maez runtime probe", encoded)
        runtime_snapshot.assert_called_once_with(
            timeout_s=0.25,
            probe_daemon_http_contract=False,
        )
```

- [ ] **Step 2: Verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maez_body_organ_view.BodyHealthProjectionTests.test_body_health_includes_runtime_services
```

Expected: fail because `runtime_services` is missing.

- [ ] **Step 3: Wire `_body_health`**

In `daemon/maez_daemon.py`, import:

```python
from core.infra.runtime_services import runtime_services_snapshot
```

Add to the `_body_health(...)` returned dict:

```python
            "runtime_services": runtime_services_snapshot(
                timeout_s=0.25,
                probe_daemon_http_contract=False,
            ),
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maez_body_organ_view
```

Expected: `OK`.

---

### Task 2: Capability Card Runtime Truth

**Files:**
- Modify: `core/cognition/capability_card.py`
- Modify: `tests/test_capability_card.py`

- [ ] **Step 1: Write failing tests**

Add to `FlagTests`:

```python
    def test_support_honesty_organs_render_degraded_when_verifier_unavailable(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        os.environ["MAEZ_SUPPORT_GATE_ENABLED"] = "1"
        os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SUPPORT_GATE_ENABLED", None))
        self.addCleanup(lambda: os.environ.pop("MAEZ_GROUNDING_SHADOW_ENABLED", None))

        with mock.patch(
            "core.cognition.capability_card.support_honesty_status",
            return_value="degraded",
        ):
            card = cc.capability_prompt_block(
                registry=(
                    ("support gate", cc._support_gate_probe),
                    ("grounding shadow", cc._grounding_shadow_probe),
                )
            )

        self.assertIn("support gate: degraded", card)
        self.assertIn("grounding shadow: degraded", card)

    def test_support_honesty_organs_stay_off_when_flags_off(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        with mock.patch(
            "core.cognition.capability_card.support_honesty_status",
            return_value="degraded",
        ):
            card = cc.capability_prompt_block(
                registry=(
                    ("support gate", cc._support_gate_probe),
                    ("grounding shadow", cc._grounding_shadow_probe),
                )
            )

        self.assertIn("support gate: off", card)
        self.assertIn("grounding shadow: off", card)
```

Also add `from unittest import mock` at the top if absent.

- [ ] **Step 2: Verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_capability_card.FlagTests.test_support_honesty_organs_render_degraded_when_verifier_unavailable
```

Expected: failure because `_support_gate_probe` does not exist.

- [ ] **Step 3: Implement probes**

In `core/cognition/capability_card.py`, import:

```python
from core.infra.runtime_services import support_honesty_status
```

Add:

```python
def _support_gate_probe() -> str:
    if not strict_env_flag("MAEZ_SUPPORT_GATE_ENABLED"):
        return "off"
    status = support_honesty_status()
    return "on" if status == "healthy" else status


def _grounding_shadow_probe() -> str:
    if not strict_env_flag("MAEZ_GROUNDING_SHADOW_ENABLED"):
        return "off"
    status = support_honesty_status()
    return "on" if status == "healthy" else status
```

Replace the default-registry entries for support gate and grounding shadow with these probes.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_capability_card
```

Expected: `OK`.

---

### Task 3: Ledger and Branch Verification

**Files:**
- Modify: `docs/MAEZ_BUILD_LEDGER.md`

- [ ] **Step 1: Add or update ledger row**

Add a row for Body Runtime Truth v0 with state `BUILT_BRANCH_VERIFIED`, noting `maez-coherence-organism`, `/health.body.runtime_services`, capability card support-honesty runtime truth, and no live restart.

- [ ] **Step 2: Run targeted verification**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_runtime_services \
  tests.test_minicheck_verifier_service \
  tests.test_maez_body_organ_view \
  tests.test_r2_body_capabilities_2026_05_04 \
  tests.test_capability_card \
  tests.test_support_gate
```

Expected: all targeted tests pass.

- [ ] **Step 3: Run lint**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m ruff check \
  core/infra/runtime_services.py \
  core/cognition/capability_card.py \
  daemon/maez_daemon.py \
  scripts/maez_runtime_services_probe.py \
  scripts/minicheck_verifier_service.py \
  tests/test_runtime_services.py \
  tests/test_minicheck_verifier_service.py \
  tests/test_capability_card.py \
  tests/test_maez_body_organ_view.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Commit**

Commit:

```bash
git add core/infra/runtime_services.py scripts/maez_runtime_services_probe.py scripts/minicheck_verifier_service.py daemon/maez_daemon.py core/cognition/capability_card.py tests/test_runtime_services.py tests/test_minicheck_verifier_service.py tests/test_capability_card.py tests/test_maez_body_organ_view.py docs/MAEZ_BUILD_LEDGER.md docs/superpowers/plans/2026-06-17-body-runtime-truth-v0.md
git commit -m "feat(body): add runtime service truth"
```

Commit body must include:

```text
## Predicted effect

On the branch, `/health.body.runtime_services` reports configured, reachable,
and contract truth for service-backed organs. The capability card no longer
claims support gate or grounding shadow are simply "on" when MiniCheck is
required but unavailable; it renders degraded/unknown from runtime truth.
No live daemon behavior changes until this branch is merged and restarted.
```
