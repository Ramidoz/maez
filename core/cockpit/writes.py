"""Guarded Cockpit V2 flag writes.

This module edits only the owner environment file and a cockpit receipt log.
It relies on the owner-reviewed registry for tier policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from core.cockpit.flags import FlagRegistryEntry, default_registry, write_policy_for_flag

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CockpitWritePaths:
    env_file: Path
    receipt_log: Path

    @classmethod
    def defaults(cls) -> "CockpitWritePaths":
        from core.infra import paths

        return cls(
            env_file=Path.home() / ".config" / "maez" / "model.env",
            receipt_log=paths.logs_dir() / "cockpit_write_receipts.jsonl",
        )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _confirmation_text(name: str, value: str) -> str:
    return f"{name}={value}"


def _refusal(
    name: str,
    reason: str,
    *,
    tier: str | None = None,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "ok": False,
        "status": "refused",
        "flag": name,
        "tier": tier,
        "reason": reason,
    }
    if extra:
        out.update(extra)
    return out


def _ceremony_pointer(name: str) -> dict[str, object]:
    if name in {"S7_LIVE_WEBAUTHN_CEREMONY", "S7_CEREMONY"}:
        return {"ceremony": "S7_CEREMONY", "ceremony_route": "/api/v1/s7/webauthn"}
    if name in {"MAEZ_LEDGER_WRITES", "BIRTH_CEREMONY"}:
        return {"ceremony": "BIRTH_CEREMONY", "ceremony_route": "/cockpit/birth"}
    return {"ceremony": "ceremony_required", "ceremony_route": None}


def _append_env_block(
    path: Path,
    *,
    name: str,
    value: str,
    entry: FlagRegistryEntry,
    at: datetime,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    block = (
        f"{prefix}# {at.date().isoformat()} cockpit-v2: {name}={value}\n"
        f"# Witness: {entry.witness_recipe}\n"
        f"# Revert: {entry.revert_line}\n"
        f"{name}={value}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(block)


def _append_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        f.write("\n")


def apply_flag_write(
    name: str,
    desired_value: str,
    *,
    paths: CockpitWritePaths,
    owner_authenticated: bool,
    confirm_click_token: str | None = None,
    typed_confirmation: str | None = None,
    cockpit_v2_enabled: bool = True,
    now: Clock = _now_utc,
    registry: Mapping[str, FlagRegistryEntry] | None = None,
) -> dict[str, object]:
    """Apply a reviewed T1/T2 flag write or return a structured refusal."""

    entries = registry if registry is not None else default_registry()
    policy = write_policy_for_flag(name, desired_value, registry=entries)
    tier = str(policy.get("tier"))
    if not cockpit_v2_enabled:
        return _refusal(name, "cockpit_v2_off", tier=tier)
    if not owner_authenticated:
        return _refusal(name, "owner_auth_required", tier=tier)
    if desired_value not in {"0", "1"}:
        return _refusal(name, "invalid_value", tier=tier)
    if not bool(policy.get("direct_write_allowed")):
        extra = _ceremony_pointer(name) if policy.get("reason") == "ceremony_only" else {}
        return _refusal(name, str(policy["reason"]), tier=tier, extra=extra)

    if tier == "T1" and confirm_click_token != "confirm":
        return _refusal(name, "confirm_click_required", tier=tier)
    if tier == "T2" and typed_confirmation != _confirmation_text(name, desired_value):
        return _refusal(
            name,
            "typed_confirmation_required",
            tier=tier,
            extra={"required_confirmation": _confirmation_text(name, desired_value)},
        )

    entry = entries[name]
    at = now()
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    receipt_id = f"cockpit-write-{uuid4().hex}"
    _append_env_block(
        paths.env_file,
        name=name,
        value=desired_value,
        entry=entry,
        at=at,
    )
    receipt = {
        "receipt_id": receipt_id,
        "action": "flag_write",
        "flag": name,
        "value": desired_value,
        "tier": tier,
        "at": at.isoformat(),
        "env_file": str(paths.env_file),
        "confirmation_kind": "typed" if tier == "T2" else "click",
        "witness_recipe": entry.witness_recipe,
        "revert_line": entry.revert_line,
    }
    _append_receipt(paths.receipt_log, receipt)
    return {
        "ok": True,
        "status": "applied",
        "flag": name,
        "value": desired_value,
        "tier": tier,
        "receipt_id": receipt_id,
        "file_state": {
            "env_file": str(paths.env_file),
            "value": desired_value,
            "appended": True,
        },
        "process_state": {
            "requires_restart": True,
            "warning": "process state changes only after restart",
        },
        "revert_line": entry.revert_line,
    }
