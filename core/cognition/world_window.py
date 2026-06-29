"""Content-light body-state deltas for the lean idle heartbeat.

This module is deliberately a sensor projector, not a command path. It compares
coarse projections of Maez's machine-body perception snapshot across beats and
emits only neutral shadow/label phrases. Raw values stay out of prompts.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "body_state_window.v0"
_HASH_SALT = "maez.body_state_window.v0"

_TIME_EXCLUSIONS = {
    "timestamp": "duplicate_time_nerve_clock_tick",
    "day_of_week": "duplicate_time_nerve",
    "hour": "duplicate_time_nerve_clock_tick",
    "time_of_day": "duplicate_time_nerve",
}
_RAW_PRIVATE_FIELDS = frozenset({"screen_text", "screen_image", "screen_ocr"})


@dataclass(frozen=True)
class WindowDelta:
    field: str
    phrase: str
    provenance: str
    sensitivity: str


@dataclass(frozen=True)
class WindowExclusion:
    field: str
    reason: str


@dataclass(frozen=True)
class WindowResult:
    deltas: tuple[WindowDelta, ...]
    exclusions: tuple[WindowExclusion, ...]
    cold_start: bool


def default_signature_path() -> Path:
    return Path.home() / ".local" / "state" / "maez" / "world_window_signatures.json"


def maybe_collect_body_state_window(
    snapshot: Mapping[str, object],
    *,
    enabled: bool,
    signature_path: Path | None = None,
) -> WindowResult | None:
    if not enabled:
        return None
    return WorldWindow(signature_path or default_signature_path()).deltas(snapshot)


class WorldWindow:
    def __init__(self, signature_path: Path) -> None:
        self.signature_path = Path(signature_path)

    def deltas(self, snapshot: Mapping[str, object]) -> WindowResult:
        current, phrases, sensitivities, exclusions = _project_snapshot(snapshot)
        previous = self._read_signatures()
        self._write_signatures(current)
        if previous is None:
            return WindowResult(deltas=(), exclusions=tuple(exclusions), cold_start=True)

        deltas: list[WindowDelta] = []
        for field, signature in current.items():
            if previous.get(field) == signature:
                continue
            deltas.append(
                WindowDelta(
                    field=field,
                    phrase=phrases[field],
                    provenance=f"perception_snapshot.{field}",
                    sensitivity=sensitivities[field],
                )
            )
        return WindowResult(
            deltas=tuple(deltas),
            exclusions=tuple(exclusions),
            cold_start=False,
        )

    def _read_signatures(self) -> dict[str, str] | None:
        try:
            with self.signature_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return None
        except Exception:
            return None
        signatures = data.get("signatures") if isinstance(data, dict) else None
        if not isinstance(signatures, dict):
            return None
        return {str(k): str(v) for k, v in signatures.items()}

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


def _project_snapshot(
    snapshot: Mapping[str, object],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[WindowExclusion]]:
    signatures: dict[str, str] = {}
    phrases: dict[str, str] = {}
    sensitivities: dict[str, str] = {}
    exclusions: list[WindowExclusion] = []

    for field, value in snapshot.items():
        if field in _TIME_EXCLUSIONS:
            exclusions.append(WindowExclusion(field=field, reason=_TIME_EXCLUSIONS[field]))
            continue
        if field in _RAW_PRIVATE_FIELDS:
            exclusions.append(WindowExclusion(field=field, reason="raw_private"))
            continue

        projected = _project_allowed(field, value)
        if projected is None:
            exclusions.append(WindowExclusion(field=field, reason="unclassified"))
            continue
        signature, phrase, sensitivity = projected
        signatures[field] = signature
        phrases[field] = phrase
        sensitivities[field] = sensitivity

    return signatures, phrases, sensitivities, exclusions


def _project_allowed(field: str, value: object) -> tuple[str, str, str] | None:
    if field == "cpu":
        data = _mapping(value)
        load = _percent_band(data.get("percent"))
        thermal = _thermal_band(data.get("temperature_c"))
        core_count_known = "known" if data.get("core_count") is not None else "unknown"
        return (
            f"cpu:{load}:{thermal}:{core_count_known}",
            "cpu load or temperature band changed",
            "safe_delta",
        )
    if field == "ram":
        data = _mapping(value)
        return (
            f"ram:{_percent_band(data.get('percent'))}",
            "memory-use band changed",
            "safe_delta",
        )
    if field == "gpu":
        if value is None:
            return ("gpu:unavailable", "gpu availability or load band changed", "safe_delta")
        data = _mapping(value)
        memory_band = _ratio_band(data.get("memory_used_mb"), data.get("memory_total_mb"))
        return (
            "gpu:"
            f"available:{_percent_band(data.get('utilization_pct'))}:"
            f"{memory_band}:{_thermal_band(data.get('temperature_c'))}",
            "gpu availability or load band changed",
            "safe_delta",
        )
    if field == "disk":
        data = _mapping(value)
        root = _percent_band(_mapping(data.get("/")).get("percent"))
        home = _percent_band(_mapping(data.get("/home")).get("percent"))
        return (f"disk:{root}:{home}", "disk-use band changed", "safe_delta")
    if field == "network":
        data = _mapping(value)
        send = _network_band(data.get("send_rate_mbps"))
        recv = _network_band(data.get("recv_rate_mbps"))
        return (
            f"network:{send}:{recv}",
            "network-activity band changed",
            "sensitive_delta",
        )
    if field == "top_processes_cpu":
        digest = _process_set_digest(value)
        return (
            f"top_processes_cpu:{digest}",
            "active process set changed",
            "sensitive_delta",
        )
    if field == "top_processes_mem":
        digest = _process_set_digest(value)
        return (
            f"top_processes_mem:{digest}",
            "memory-heavy process set changed",
            "sensitive_delta",
        )
    return None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent_band(value: object) -> str:
    pct = _float(value)
    if pct is None:
        return "unknown"
    if pct < 20:
        return "idle"
    if pct < 50:
        return "low"
    if pct < 80:
        return "moderate"
    if pct < 95:
        return "high"
    return "saturated"


def _thermal_band(value: object) -> str:
    temp = _float(value)
    if temp is None:
        return "unknown"
    if temp < 55:
        return "cool"
    if temp < 75:
        return "warm"
    if temp < 90:
        return "hot"
    return "critical"


def _ratio_band(numerator: object, denominator: object) -> str:
    num = _float(numerator)
    den = _float(denominator)
    if num is None or den is None or den <= 0:
        return "unknown"
    return _percent_band((num / den) * 100.0)


def _network_band(value: object) -> str:
    rate = _float(value)
    if rate is None:
        return "unknown"
    if rate <= 0.01:
        return "quiet"
    if rate < 1:
        return "low"
    if rate < 10:
        return "moderate"
    return "high"


def _process_set_digest(value: object) -> str:
    names: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                name = str(item.get("name") or "").strip()
                if name:
                    names.append(name)
    joined = "\n".join(sorted(set(names)))
    return hashlib.sha256(f"{_HASH_SALT}\n{joined}".encode("utf-8")).hexdigest()[:16]
