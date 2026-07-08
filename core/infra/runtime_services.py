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
_CACHE_TTL_S = 15.0

JsonProbe = Callable[..., dict[str, Any]]
PortProbe = Callable[..., bool]
UnitProbe = Callable[..., dict[str, str]]
ModelAliasProbe = Callable[..., str]


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
        return {
            "name": unit,
            "scope": scope,
            "load_state": "unknown",
            "active_state": "unknown",
            "enabled_state": "unknown",
        }
    values: dict[str, str] = {}
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


def _probe_unit(
    unit: str,
    *,
    scope: str = "user",
    timeout_s: float = 0.35,
) -> dict[str, str]:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return _parse_systemctl_show(
            None,
            timed_out=False,
            unit=unit,
            scope=scope,
        )
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
        return _parse_systemctl_show(
            "",
            timed_out=True,
            unit=unit,
            scope=scope,
        )
    except OSError:
        return _parse_systemctl_show(
            None,
            timed_out=False,
            unit=unit,
            scope=scope,
        )
    return _parse_systemctl_show(
        result.stdout,
        timed_out=False,
        unit=unit,
        scope=scope,
    )


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
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
        return {
            "ok": True,
            "json": json.loads(raw.decode("utf-8") or "{}"),
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ):
        return {
            "ok": False,
            "json": {},
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }


def _required_by(*flags: str) -> list[str]:
    return [flag for flag in flags if _flag_enabled(flag)]


def _status_for(
    required_by: list[str],
    unit: dict[str, str],
    port: dict[str, Any] | None,
    contract: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    if not required_by:
        return "asleep", []

    reasons: list[str] = []
    if unit.get("load_state") not in {"loaded", "unknown"}:
        reasons.append("unit_not_loaded")
    if unit.get("active_state") not in {"active", "unknown"}:
        reasons.append("unit_inactive")
    if port is not None and not port.get("reachable", False):
        reasons.append("port_unreachable")
    if contract is not None and not contract.get("ok", False):
        reasons.append("contract_unhealthy")
    return ("degraded", reasons) if reasons else ("healthy", [])


def _support_contract(http_json: JsonProbe, *, timeout_s: float) -> dict[str, Any]:
    response = http_json(
        "GET",
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


def _generic_json_contract(
    kind: str,
    *,
    method: str,
    url: str,
    http_json: JsonProbe,
    timeout_s: float,
) -> dict[str, Any]:
    response = http_json(method, url, timeout_s=timeout_s)
    return {
        "kind": kind,
        "ok": bool(response.get("ok")),
        "latency_ms": int(response.get("latency_ms", 0) or 0),
    }


def _served_model_alias_contract(alias: str | None) -> dict[str, Any]:
    value = (alias or "").strip()
    return {
        "kind": "served_model_alias",
        "alias": value,
        "ok": bool(value) and value.lower() != "unknown",
    }


def runtime_services_snapshot(
    timeout_s: float = 0.35,
    *,
    unit_probe: UnitProbe = _probe_unit,
    port_probe: PortProbe = _probe_port,
    http_json: JsonProbe = _http_json,
    model_alias: ModelAliasProbe = served_model_alias,
    probe_daemon_http_contract: bool = True,
) -> dict[str, Any]:
    services: dict[str, dict[str, Any]] = {}

    def add_service(
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

    add_service(
        "primary_brain",
        required_by=["always"],
        unit_name="llama-server.service",
        port=("127.0.0.1", 8080),
        contract=_served_model_alias_contract(
            model_alias(default="unknown", timeout_s=timeout_s)
        ),
    )
    add_service(
        "maez_daemon",
        required_by=["always"],
        unit_name="maez.service",
        port=("127.0.0.1", 11435),
        contract=(
            _generic_json_contract(
                "daemon_health",
                method="GET",
                # /operator/health is a fast liveness payload (~5ms); /health runs perception_snapshot() (nvidia-smi, 1-3s+) and would false-degrade a healthy-but-slow daemon.
                url="http://127.0.0.1:11435/operator/health",
                http_json=http_json,
                timeout_s=timeout_s,
            )
            if probe_daemon_http_contract
            else {
                "kind": "in_process_daemon",
                "ok": True,
                "latency_ms": 0,
            }
        ),
    )
    add_service(
        "maez_web",
        required_by=_required_by(
            "MAEZ_COCKPIT_REAL_STATE",
            "MAEZ_COCKPIT_CORE",
            "MAEZ_WEB_OWNER_CORE",
            "MAEZ_S7_CEREMONY_BRIDGE_ENABLED",
        ),
        unit_name="maez-web.service",
        port=("127.0.0.1", 11437),
    )
    add_service(
        "search_body",
        required_by=_required_by("MAEZ_SEARCH_AS_SENSE_ENABLED"),
        unit_name="maez-searxng.service",
        port=("127.0.0.1", 8888),
        contract=(
            {
                "kind": "tcp_liveness_only",
                "ok": True,
                "latency_ms": 0,
            }
            if _flag_enabled("MAEZ_SEARCH_AS_SENSE_ENABLED")
            else None
        ),
    )
    support_required = _required_by(
        "MAEZ_SUPPORT_GATE_ENABLED",
        "MAEZ_GROUNDING_SHADOW_ENABLED",
    )
    add_service(
        "support_verifier",
        required_by=support_required,
        unit_name="minicheck-verifier.service",
        port=("127.0.0.1", 8083),
        contract=(
            _support_contract(http_json, timeout_s=timeout_s)
            if support_required
            else None
        ),
    )
    add_service(
        "subscription_proxy",
        required_by=[],
        unit_name="maez-subscription-proxy.service",
        port=("127.0.0.1", 11438),
    )
    add_service(
        "vision_body",
        required_by=_required_by("MAEZ_SCREEN_PERCEPTION"),
        # Real unit name (2026-07-08 witness-sprint audit): the vision body
        # runs as llama-vision.service; "maez-vision.service" never existed,
        # so the services map reported a phantom unit for the eye.
        unit_name="llama-vision.service",
        port=("127.0.0.1", 8082),
    )
    add_service(
        "overclaim_judge",
        required_by=["always"],
        unit_name="llama-judge.service",
        port=("127.0.0.1", 8081),
    )

    overall = (
        "degraded"
        if any(service["status"] == "degraded" for service in services.values())
        else "healthy"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "overall": overall,
        "generated_at": time.time(),
        "services": services,
    }


def runtime_services_snapshot_cached(timeout_s: float = 0.35) -> dict[str, Any]:
    global _CACHE, _CACHE_TS
    now = time.time()
    if _CACHE is not None and now - _CACHE_TS < _CACHE_TTL_S:
        return _CACHE
    _CACHE = runtime_services_snapshot(timeout_s=timeout_s)
    _CACHE_TS = now
    return _CACHE


def runtime_service_status(name: str, timeout_s: float = 0.35) -> dict[str, Any]:
    try:
        return runtime_services_snapshot_cached(timeout_s=timeout_s)["services"].get(
            name,
            {
                "status": "unknown",
                "degraded_reasons": ["unknown_service"],
            },
        )
    except Exception:
        return {"status": "unknown", "degraded_reasons": ["probe_failed"]}


def support_honesty_status(timeout_s: float = 0.35) -> str:
    if not (
        _flag_enabled("MAEZ_SUPPORT_GATE_ENABLED")
        or _flag_enabled("MAEZ_GROUNDING_SHADOW_ENABLED")
    ):
        return "off"
    return str(
        runtime_service_status("support_verifier", timeout_s=timeout_s).get(
            "status",
            "unknown",
        )
    )
