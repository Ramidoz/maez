"""Cockpit V2 connector registry read model and guarded requests.

Connectors are capability doors, not memory writers. This module renders the
registry if it exists and records owner requests to connect/disconnect, while
keeping the intake-bus boundary explicit: connector facts must pass
core.intake_bus.admit before any memory surface can see them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

Clock = Callable[[], datetime]
_INTAKE_DOORWAY = "core.intake_bus.admit"


@dataclass(frozen=True)
class CockpitConnectorPaths:
    registry_file: Path
    receipt_log: Path

    @classmethod
    def defaults(cls) -> "CockpitConnectorPaths":
        from core.infra import paths

        return cls(
            registry_file=paths.config_dir() / "connector_registry.json",
            receipt_log=paths.logs_dir() / "cockpit_connector_receipts.jsonl",
        )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _append_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        f.write("\n")


def _intake_bus() -> dict[str, object]:
    return {
        "doorway": _INTAKE_DOORWAY,
        "bypass_allowed": False,
        "description": "Every connector fact passes the immune doorway before memory.",
    }


def _load_registry(path: Path) -> tuple[str, dict[str, object] | None, str | None]:
    if not path.exists():
        return "unavailable", None, "connector_registry_absent"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "unavailable", None, "connector_registry_unreadable"
    if not isinstance(parsed, dict):
        return "unavailable", None, "connector_registry_invalid"
    return "ok", parsed, None


def _connector_public(row: Mapping[str, object]) -> dict[str, object]:
    scopes = row.get("granted_scopes")
    return {
        "id": str(row.get("id") or ""),
        "label": str(row.get("label") or row.get("id") or ""),
        "connection_state": str(row.get("state") or "unknown"),
        "tier": str(row.get("tier") or "unclassified"),
        "granted_scopes": scopes if isinstance(scopes, list) else [],
        "last_activity": str(row.get("last_activity") or "unknown"),
        "intake_bus": str(row.get("intake_bus") or _INTAKE_DOORWAY),
    }


def _connectors_from_registry(registry: Mapping[str, object]) -> list[dict[str, object]]:
    rows = registry.get("connectors")
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, dict):
            public = _connector_public(row)
            if public["id"]:
                out.append(public)
    return out


def build_connectors_room(paths: CockpitConnectorPaths | None = None) -> dict[str, object]:
    """Return connector state without creating a registry file."""

    paths = paths or CockpitConnectorPaths.defaults()
    status, registry, reason = _load_registry(paths.registry_file)
    if status != "ok" or registry is None:
        return {
            "kind": "cockpit_v2_connectors",
            "status": "unavailable",
            "reason": reason,
            "connectors": [],
            "source": str(paths.registry_file),
            "intake_bus": _intake_bus(),
        }
    connectors = _connectors_from_registry(registry)
    return {
        "kind": "cockpit_v2_connectors",
        "status": "ok",
        "connectors": connectors,
        "connector_count": len(connectors),
        "source": str(paths.registry_file),
        "intake_bus": _intake_bus(),
        "autonomous_attachment_note": (
            "Maez may still propose connector attachment through the ordinary intake and approval path."
        ),
    }


def _refusal(
    connector_id: str,
    action: str,
    reason: str,
    *,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {
        "ok": False,
        "status": "refused",
        "connector_id": connector_id,
        "action": action,
        "reason": reason,
    }
    if extra:
        out.update(extra)
    return out


def _required_confirmation(action: str, connector_id: str) -> str:
    return f"{action.upper()} {connector_id}"


def apply_connector_action(
    connector_id: str,
    action: str,
    *,
    paths: CockpitConnectorPaths,
    owner_authenticated: bool,
    confirm_click_token: str | None = None,
    typed_confirmation: str | None = None,
    cockpit_v2_enabled: bool = True,
    now: Clock = _now_utc,
) -> dict[str, object]:
    """Record a guarded connector connect/disconnect request."""

    if not cockpit_v2_enabled:
        return _refusal(connector_id, action, "cockpit_v2_off")
    if not owner_authenticated:
        return _refusal(connector_id, action, "owner_auth_required")
    if action not in {"connect", "disconnect"}:
        return _refusal(connector_id, action, "invalid_connector_action")
    if confirm_click_token != "confirm":
        return _refusal(connector_id, action, "confirm_click_required")

    status, registry, reason = _load_registry(paths.registry_file)
    if status != "ok" or registry is None:
        return _refusal(connector_id, action, "connector_registry_unavailable", extra={"registry_reason": reason})
    connectors = _connectors_from_registry(registry)
    connector = next((item for item in connectors if item["id"] == connector_id), None)
    if connector is None:
        return _refusal(connector_id, action, "connector_unknown")
    if connector.get("tier") != "T2":
        return _refusal(connector_id, action, "connector_unclassified")

    required = _required_confirmation(action, connector_id)
    if typed_confirmation != required:
        return _refusal(
            connector_id,
            action,
            "typed_confirmation_required",
            extra={"required_confirmation": required, "tier": "T2"},
        )

    at = now()
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    receipt_id = f"cockpit-connector-{uuid4().hex}"
    receipt = {
        "receipt_id": receipt_id,
        "action": action,
        "connector_id": connector_id,
        "tier": "T2",
        "at": at.isoformat(),
        "intake_bus": connector.get("intake_bus") or _INTAKE_DOORWAY,
        "result": "requested",
    }
    _append_receipt(paths.receipt_log, receipt)
    return {
        "ok": True,
        "status": "applied",
        "connector_id": connector_id,
        "action": action,
        "tier": "T2",
        "receipt_id": receipt_id,
        "intake_bus": receipt["intake_bus"],
        "result": "requested",
    }
