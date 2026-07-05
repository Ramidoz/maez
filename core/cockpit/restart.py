"""Guarded Cockpit V2 service restarts with boot witness receipts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

Clock = Callable[[], datetime]
Runner = Callable[[list[str]], "CommandResult"]

_ALLOWED_SERVICES = frozenset({"maez.service", "maez-web.service"})


@dataclass(frozen=True)
class CommandResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class CockpitRestartPaths:
    receipt_log: Path

    @classmethod
    def defaults(cls) -> "CockpitRestartPaths":
        from core.infra import paths

        return cls(receipt_log=paths.logs_dir() / "cockpit_restart_receipts.jsonl")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def default_runner(cmd: list[str]) -> CommandResult:
    completed = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _required_confirmation(service: str) -> str:
    return f"restart {service}"


def _refusal(
    service: str,
    reason: str,
    *,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "ok": False,
        "status": "refused",
        "service": service,
        "tier": "T2",
        "reason": reason,
    }
    if extra:
        out.update(extra)
    return out


def _main_pid(service: str, runner: Runner) -> int:
    result = runner(["systemctl", "show", "-p", "MainPID", "--value", service])
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError:
        return 0


def _active_state(service: str, runner: Runner) -> str:
    result = runner(["systemctl", "is-active", service])
    state = (result.stdout or "").strip()
    return state or ("active" if result.returncode == 0 else "failed")


def _boot_log_tail(service: str, runner: Runner) -> str:
    result = runner(["journalctl", "-u", service, "-n", "80", "--no-pager"])
    return result.stdout or result.stderr or ""


def _hints(log_tail: str) -> dict[str, object]:
    matching_lines = []
    for line in log_tail.splitlines():
        lowered = line.lower()
        if any(token in lowered for token in ("segv", "segfault", "coredump", "core dump", "dumped core")):
            matching_lines.append(line)
    lowered_tail = log_tail.lower()
    return {
        "segv_detected": "segv" in lowered_tail or "segfault" in lowered_tail,
        "coredump_detected": (
            "coredump" in lowered_tail
            or "core dump" in lowered_tail
            or "dumped core" in lowered_tail
        ),
        "matching_lines": matching_lines,
    }


def _append_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        f.write("\n")


def _safe_main_pid(service: str, runner: Runner) -> int:
    try:
        return _main_pid(service, runner)
    except Exception:
        return 0


def _safe_active_state(service: str, runner: Runner) -> str:
    try:
        return _active_state(service, runner)
    except Exception:
        return "unknown"


def _safe_boot_log_tail(service: str, runner: Runner) -> tuple[str, str | None]:
    try:
        return _boot_log_tail(service, runner), None
    except Exception as exc:
        return "", str(exc)


def _result_and_receipt(
    *,
    service: str,
    paths: CockpitRestartPaths,
    at: datetime,
    status: str,
    receipt_id: str,
    pre_pid: int,
    post_pid: int,
    active_state: str,
    restart_returncode: int | None,
    log_tail: str,
    hints: dict[str, object],
    error: str | None = None,
) -> dict[str, object]:
    boot_witness: dict[str, object] = {
        "log_tail": log_tail,
        "hints": hints,
    }
    if error:
        boot_witness["error"] = error
    receipt = {
        "receipt_id": receipt_id,
        "action": "service_restart",
        "service": service,
        "tier": "T2",
        "status": status,
        "at": at.isoformat(),
        "pre_pid": pre_pid,
        "post_pid": post_pid,
        "active_state": active_state,
        "restart_returncode": restart_returncode,
        "boot_witness": boot_witness,
    }
    _append_receipt(paths.receipt_log, receipt)
    return {
        "ok": status == "restarted",
        "status": status,
        "service": service,
        "tier": "T2",
        "receipt_id": receipt_id,
        "pre_pid": pre_pid,
        "post_pid": post_pid,
        "active_state": active_state,
        "boot_witness": boot_witness,
    }


def restart_service(
    service: str,
    *,
    paths: CockpitRestartPaths,
    owner_authenticated: bool,
    cockpit_v2_enabled: bool,
    typed_confirmation: str | None,
    runner: Runner = default_runner,
    now: Clock = _now_utc,
) -> dict[str, object]:
    """Restart an allowed service and write an honest boot-witness receipt."""

    if not cockpit_v2_enabled:
        return _refusal(service, "cockpit_v2_off")
    if not owner_authenticated:
        return _refusal(service, "owner_auth_required")
    if service not in _ALLOWED_SERVICES:
        return _refusal(service, "unsupported_service")
    required = _required_confirmation(service)
    if typed_confirmation != required:
        return _refusal(
            service,
            "typed_confirmation_required",
            extra={"required_confirmation": required},
        )

    at = now()
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    receipt_id = f"cockpit-restart-{uuid4().hex}"
    pre_pid = _safe_main_pid(service, runner)
    try:
        restart_result = runner(["systemctl", "restart", service])
        restart_returncode: int | None = restart_result.returncode
        error = None
    except Exception as exc:
        restart_returncode = None
        error = str(exc)
    post_pid = _safe_main_pid(service, runner)
    active_state = _safe_active_state(service, runner)
    log_tail, log_error = _safe_boot_log_tail(service, runner)
    if log_error and error:
        error = f"{error}; log_tail: {log_error}"
    elif log_error:
        error = f"log_tail: {log_error}"
    hints = _hints(log_tail)
    status = "restarted" if restart_returncode == 0 and active_state == "active" else "failed"
    return _result_and_receipt(
        service=service,
        paths=paths,
        at=at,
        status=status,
        receipt_id=receipt_id,
        pre_pid=pre_pid,
        post_pid=post_pid,
        active_state=active_state,
        restart_returncode=restart_returncode,
        log_tail=log_tail,
        hints=hints,
        error=error,
    )
