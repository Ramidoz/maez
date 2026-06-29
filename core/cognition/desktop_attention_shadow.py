"""Content-light desktop attention shadow for the lean idle heartbeat.

This is a sense projector, not a command path. It compares a class-only active
surface signature across beats and emits only "active surface changed"; raw app
classes stay out of Maez prompt, memory stores, and receipts.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from core.body.desktop_presence_state import DesktopPresenceState


SCHEMA_VERSION = "desktop_attention_shadow.v0"
_HASH_SALT = "maez.desktop_attention_shadow.v0"
_FIELD = "active_surface"


@dataclass(frozen=True)
class DesktopAttentionEntry:
    field: str
    phrase: str
    provenance: str
    sensitivity: str


@dataclass(frozen=True)
class DesktopAttentionResult:
    entries: tuple[DesktopAttentionEntry, ...]
    cold_start: bool
    sensor_state: str
    reason: str = ""
    schema_version: str = SCHEMA_VERSION

    def receipt_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "cold_start": bool(self.cold_start),
            "sensor_state": self.sensor_state,
            "reason": self.reason,
            "entry_count": len(self.entries),
            "entries": [
                {
                    "field": entry.field,
                    "provenance": entry.provenance,
                    "sensitivity": entry.sensitivity,
                }
                for entry in self.entries
            ],
        }


def default_signature_path() -> Path:
    return (
        Path.home()
        / ".local"
        / "state"
        / "maez"
        / "desktop_attention_shadow_signatures.json"
    )


def maybe_collect_desktop_attention_shadow(
    state: DesktopPresenceState,
    *,
    enabled: bool,
    signature_path: Path | None = None,
) -> DesktopAttentionResult | None:
    if not enabled:
        return None
    return DesktopAttentionShadow(signature_path or default_signature_path()).entries_for(
        state
    )


class DesktopAttentionShadow:
    def __init__(self, signature_path: Path) -> None:
        self.signature_path = Path(signature_path)

    def entries_for(self, state: DesktopPresenceState) -> DesktopAttentionResult:
        if state.sensor_state != "available" or not state.app_class:
            return DesktopAttentionResult(
                entries=(
                    DesktopAttentionEntry(
                        field="desktop_sensor_state",
                        phrase="desktop attention sense unavailable",
                        provenance="desktop_presence_state.sensor_state",
                        sensitivity="safe_label",
                    ),
                ),
                cold_start=False,
                sensor_state=str(state.sensor_state),
                reason=str(state.reason or ""),
            )

        current = {_FIELD: _signature(str(state.app_class))}
        previous = self._read_signatures()
        self._write_signatures(current)
        if previous is None:
            return DesktopAttentionResult(
                entries=(),
                cold_start=True,
                sensor_state="available",
            )
        if previous.get(_FIELD) == current[_FIELD]:
            return DesktopAttentionResult(
                entries=(),
                cold_start=False,
                sensor_state="available",
            )
        return DesktopAttentionResult(
            entries=(
                DesktopAttentionEntry(
                    field=_FIELD,
                    phrase="active surface changed",
                    provenance="desktop_presence_state.app_class",
                    sensitivity="sensitive_delta",
                ),
            ),
            cold_start=False,
            sensor_state="available",
        )

    def _read_signatures(self) -> dict[str, str] | None:
        try:
            with self.signature_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return None
        except Exception:
            return None
        if not isinstance(data, Mapping):
            return None
        signatures = data.get("signatures")
        if not isinstance(signatures, Mapping):
            return None
        return {str(key): str(value) for key, value in signatures.items()}

    def _write_signatures(self, signatures: Mapping[str, str]) -> None:
        self.signature_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.signature_path.with_suffix(self.signature_path.suffix + ".tmp")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "signatures": dict(sorted((str(k), str(v)) for k, v in signatures.items())),
        }
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
        tmp.replace(self.signature_path)


def _signature(app_class: str) -> str:
    material = f"{_HASH_SALT}:{app_class.strip().lower()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]
