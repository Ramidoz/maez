# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Moment Assembly Diagnostic records.

Schema evolution contract: additive-only fields, never rename existing
keys, never reorder existing semantics, and bump the relevant per-organ
schema whenever an organ's emitted shape changes. Unknown or reserved
enum values must fail in old readers instead of being silently accepted.
"""

from __future__ import annotations

import contextvars
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from types import TracebackType
from typing import Any
from uuid import uuid4


MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA = 2
AUDIT_BOUNDARY = "not_audit_evidence"
DEFAULT_LOG_PATH = Path("logs/moment_assembly_diagnostic.jsonl")
THESIS_DOC_PATH = "docs/governance/ARCHITECTURAL_THESIS.md"
ARCHITECTURAL_THESIS_ADR_ID = "ARCHITECTURAL_THESIS"
BYPASS_NOTE_MAX_CHARS = 500
_LOGGER = logging.getLogger(__name__)
_WRITE_FAILURE_WARNED_KEYS: set[tuple[str, str]] = set()
_READ_FAILURE_WARNED_PATHS: set[Path] = set()
_CURRENT_TURN: contextvars.ContextVar[MomentAssemblyTurn | None] = contextvars.ContextVar(
    "moment_assembly_turn",
    default=None,
)

PRESSURE_NAMES = (
    "truth",
    "continuity",
    "absence",
    "owner_load",
    "covenant",
    "substrate",
    "resonance",
    "narrative",
    "anticipation_error",
)
CANDIDATE_SOURCE_NAMES = (
    "recent_conversation",
    "self_history",
    "lived_recall",
    "open_loops",
    "counterevidence",
    "body_state",
    "covenant_boundaries",
    "future_projection_rules",
)
TOPOLOGY_NAMES = ("euclidean", "poincare")
ORGAN_SCHEMA_VERSION = 1
OPEN_LOOP_REGISTRY_SCHEMA_VERSION = 1
OPEN_LOOP_ID_BASIS_VERSION = 1
OPEN_LOOP_HASH_INPUT_PREFIX = "x2.open_loop.v1|episode:"
OPEN_LOOP_AGE_BUCKET_CUTOFF_VERSION = 1
OPEN_LOOP_AGE_HYSTERESIS_DAYS = 0.25
DEPRECATION_REASONS = frozenset(
    {
        "superseded",
        "obsolete",
        "consolidated",
        "retired_for_audit",
        "retired_for_clarity",
    }
)
BYPASS_REASONS = frozenset(
    {
        "not_called",
        "early_return",
        "exception",
        "deliberate_skip",
        "unspecified",
    }
)
NEXT_SURFACE_VALUES = frozenset(
    {
        "cli",
        "telegram_text",
        "telegram_recovery",
        "web_owner",
        "daemon_cycle",
        "unknown",
    }
)
PRESSURE_DELTA_VALUES = frozenset({"down", "flat", "up", "unknown"})
SELF_WORKSPACE_NEED_VALUES = frozenset(CANDIDATE_SOURCE_NAMES + ("unknown",))
PREDICTION_STATUSES = frozenset({"predicted", "deliberate_skip"})
EPISTEMIC_PRECISION_VALUES = frozenset({"low", "medium", "high", "unknown"})
OPEN_LOOP_KINDS = frozenset(
    {
        "project_followup",
        "conversation_revisit",
        "pending_promise",
        "unresolved_repair",
        "continuity_gap",
        "unknown",
    }
)
OPEN_LOOP_ORIGINS = frozenset({"maez_first_person", "project_doc"})
OPEN_LOOP_PROVENANCE_STATUSES = frozenset({"live", "rot_suspected", "unreachable", "archived"})
OPEN_LOOP_AGE_BUCKETS = frozenset({"fresh", "recent", "stale", "long_running"})
_OPEN_LOOP_AGE_CUTOFFS_DAYS: tuple[tuple[str, float], ...] = (
    ("fresh", 2.0),
    ("recent", 14.0),
    ("stale", 90.0),
)
OPEN_LOOP_ENTRY_KEYS = frozenset(
    {
        "loop_id",
        "prior_loop_ids",
        "loop_origin",
        "loop_kind",
        "provenance_status",
        "age_bucket",
        "age_bucket_cutoff_version",
        "evidence_count",
        "source_episode_ids",
        "source_memory_ids",
        "epistemic_precision",
    }
)
ANTICIPATION_METHOD_VALUES = frozenset(
    {
        "deterministic_source_pattern_v1",
        "deliberate_skip_covenant_boundary_v1",
    }
)
ANTICIPATION_TARGET_KEYS = frozenset(
    {
        "next_surface",
        "next_pressure_delta",
        "next_self_workspace_need",
    }
)
FORBIDDEN_ANTICIPATION_VALUE_KEYS = frozenset(
    {
        "model_confidence",
        "logit_confidence",
        "hidden_state_confidence",
        "llm_verbal_confidence",
        "verbal_confidence",
    }
)


class DiagnosticState(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
    NOT_OBSERVED = "not_observed"
    EMITTED_NULL = "emitted_null"
    EMITTED_VALUE = "emitted_value"
    ERROR = "error"
    DEPRECATED = "deprecated"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_repo_file(path: str) -> str:
    try:
        return hashlib.sha256((_repo_root() / path).read_bytes()).hexdigest()
    except OSError:
        return ""


def _organ_key(group: str, name: str | None = None) -> str:
    return group if name is None else f"{group}.{name}"


def default_contributing_schemas() -> dict[str, int]:
    schemas: dict[str, int] = {}
    for name in PRESSURE_NAMES:
        schemas[_organ_key("pressure", name)] = ORGAN_SCHEMA_VERSION
        schemas[_organ_key("pressure_delta", name)] = ORGAN_SCHEMA_VERSION
    for name in CANDIDATE_SOURCE_NAMES:
        schemas[_organ_key("candidate_source", name)] = ORGAN_SCHEMA_VERSION
    for name in TOPOLOGY_NAMES:
        schemas[_organ_key("bond_topology", name)] = ORGAN_SCHEMA_VERSION
    for name in (
        "workspace_selection",
        "anticipation",
        "surprise_delta",
        "interpretation_candidates",
    ):
        schemas[_organ_key(name)] = ORGAN_SCHEMA_VERSION
    return schemas


def build_slot(
    state: str | DiagnosticState,
    *,
    value: Any,
    source_ids: list[str],
    schema_version: int = ORGAN_SCHEMA_VERSION,
    error_class: str = "",
    deprecated_at_schema_version: int | None = None,
    deprecation_reason: str = "",
) -> dict[str, Any]:
    try:
        state_value = DiagnosticState(state).value
    except ValueError as exc:
        raise ValueError(f"unknown diagnostic state: {state!r}") from exc
    slot: dict[str, Any] = {
        "schema_version": schema_version,
        "state": state_value,
        "value": value,
        "source_ids": list(source_ids),
    }
    if error_class:
        slot["error_class"] = error_class
    if deprecated_at_schema_version is not None:
        slot["deprecated_at_schema_version"] = deprecated_at_schema_version
    if deprecation_reason:
        slot["deprecation_reason"] = deprecation_reason
    validate_slot("slot", slot)
    return slot


def validate_slot(name: str, slot: dict[str, Any]) -> None:
    if "state" not in slot:
        raise ValueError(f"{name}: state is required")
    try:
        state = DiagnosticState(slot["state"])
    except ValueError as exc:
        raise ValueError(f"{name}: unknown diagnostic state {slot['state']!r}") from exc
    if "schema_version" not in slot:
        raise ValueError(f"{name}: schema_version is required")
    if "value" not in slot:
        raise ValueError(f"{name}: value is required")
    if "source_ids" not in slot or not isinstance(slot["source_ids"], list):
        raise ValueError(f"{name}: source_ids list is required")
    if name == "anticipation" and state is DiagnosticState.EMITTED_VALUE:
        _validate_anticipation_value(slot["value"], slot["source_ids"])
        return
    if (
        name in {"open_loops", "candidate_sources.open_loops"}
        and state is DiagnosticState.EMITTED_VALUE
    ):
        _validate_open_loops_value(slot["value"], slot["source_ids"])
        return
    if name == "surprise_delta" and state in {
        DiagnosticState.EMITTED_VALUE,
        DiagnosticState.NOT_OBSERVED,
    }:
        _validate_surprise_delta_value(
            value=slot["value"],
            source_ids=slot["source_ids"],
            state=state,
        )
        return
    if state in {DiagnosticState.NOT_IMPLEMENTED, DiagnosticState.NOT_OBSERVED}:
        if slot["value"] is not None:
            raise ValueError(f"{name}: {state.value} requires value None")
        if slot["source_ids"]:
            raise ValueError(f"{name}: {state.value} requires empty source_ids")
    if state is DiagnosticState.EMITTED_VALUE and not slot["source_ids"]:
        raise ValueError(f"{name}: emitted_value requires non-empty source_ids")
    if state is DiagnosticState.EMITTED_NULL:
        if slot["value"] is not None:
            raise ValueError(f"{name}: emitted_null requires value None")
        if not slot["source_ids"]:
            raise ValueError(f"{name}: emitted_null requires non-empty source_ids")
    if state is DiagnosticState.ERROR and not slot.get("error_class"):
        raise ValueError(f"{name}: error requires error_class")
    if state is DiagnosticState.DEPRECATED:
        if slot["value"] is not None:
            raise ValueError(f"{name}: deprecated requires value None")
        if slot["source_ids"]:
            raise ValueError(f"{name}: deprecated requires empty source_ids")
        if "deprecated_at_schema_version" not in slot:
            raise ValueError(f"{name}: deprecated requires deprecated_at_schema_version")
        reason = slot.get("deprecation_reason")
        if not reason:
            raise ValueError(f"{name}: deprecated requires deprecation_reason")
        if reason not in DEPRECATION_REASONS:
            raise ValueError(f"{name}: unknown deprecation_reason {reason!r}")


def _default_slot(state: DiagnosticState = DiagnosticState.NOT_IMPLEMENTED) -> dict[str, Any]:
    return build_slot(state, value=None, source_ids=[])


def _typed_ledger_source_ids(source_ids: list[str]) -> list[str]:
    return [
        source_id
        for source_id in source_ids
        if isinstance(source_id, str) and source_id.startswith("ledger:")
    ]


def _all_unknown_targets(targets: dict[str, Any]) -> bool:
    pressure_delta = targets.get("next_pressure_delta")
    workspace_need = targets.get("next_self_workspace_need")
    return (
        targets.get("next_surface") == "unknown"
        and isinstance(pressure_delta, dict)
        and set(pressure_delta) == set(PRESSURE_NAMES)
        and all(value == "unknown" for value in pressure_delta.values())
        and workspace_need == ["unknown"]
    )


def _validate_anticipation_targets(targets: Any) -> None:
    if not isinstance(targets, dict):
        raise ValueError("anticipation targets must be an object")
    if set(targets) != ANTICIPATION_TARGET_KEYS:
        raise ValueError("anticipation targets must have exactly the closed target keys")
    next_surface = targets["next_surface"]
    if next_surface not in NEXT_SURFACE_VALUES:
        raise ValueError(f"next_surface must be one of {sorted(NEXT_SURFACE_VALUES)!r}")
    pressure_delta = targets["next_pressure_delta"]
    if not isinstance(pressure_delta, dict):
        raise ValueError("next_pressure_delta must be an object")
    if set(pressure_delta) != set(PRESSURE_NAMES):
        raise ValueError("next_pressure_delta pressure keys drifted from PRESSURE_NAMES")
    for name, value in pressure_delta.items():
        if value not in PRESSURE_DELTA_VALUES:
            raise ValueError(f"next_pressure_delta.{name} has unknown direction {value!r}")
    workspace_need = targets["next_self_workspace_need"]
    if not isinstance(workspace_need, list) or not workspace_need:
        raise ValueError("next_self_workspace_need must be a non-empty list")
    if len(set(workspace_need)) != len(workspace_need):
        raise ValueError("next_self_workspace_need must not contain duplicates")
    for value in workspace_need:
        if value not in SELF_WORKSPACE_NEED_VALUES:
            raise ValueError(
                "next_self_workspace_need must use the closed candidate-source vocabulary"
            )


def _validate_epistemic_precision(
    *,
    precision: Any,
    source_ids: list[str],
    targets: dict[str, Any],
    prediction_status: str,
) -> None:
    if precision not in EPISTEMIC_PRECISION_VALUES:
        raise ValueError("epistemic_precision must use the closed precision vocabulary")
    ledger_source_count = len(set(_typed_ledger_source_ids(source_ids)))
    if precision == "high" and ledger_source_count < 3:
        raise ValueError("epistemic_precision=high requires at least 3 typed ledger sources")
    if precision == "medium" and ledger_source_count < 2:
        raise ValueError("epistemic_precision=medium requires at least 2 typed ledger sources")
    if precision == "low" and ledger_source_count < 1:
        raise ValueError("epistemic_precision=low requires at least 1 typed ledger source")
    if precision in {"low", "medium", "high"} and ledger_source_count != len(source_ids):
        raise ValueError("epistemic_precision evidence must be typed ledger source_ids")
    if precision == "unknown" and source_ids:
        raise ValueError("epistemic_precision=unknown must not carry ledger evidence")
    if (
        precision == "unknown"
        and prediction_status == "predicted"
        and not _all_unknown_targets(targets)
    ):
        raise ValueError("epistemic_precision=unknown requires unknown-safe targets")


def _validate_anticipation_value(value: Any, source_ids: list[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError("anticipation value must be an object")
    forbidden = FORBIDDEN_ANTICIPATION_VALUE_KEYS.intersection(value)
    if forbidden:
        raise ValueError(
            "anticipation value must not carry model_confidence/logit/hidden-state fields"
        )
    required = {
        "prediction_id",
        "predicted_at_turn_id",
        "prediction_status",
        "targets",
        "epistemic_precision",
        "method",
        "expires_after_turns",
        "predicted_at_wall_clock",
    }
    actual = set(value)
    missing = sorted(required - actual)
    if missing:
        raise ValueError(f"anticipation value missing required field(s): {missing!r}")
    extra = sorted(actual - required)
    if extra:
        raise ValueError(f"anticipation value has unknown field(s): {extra!r}")
    for key in ("prediction_id", "predicted_at_turn_id", "predicted_at_wall_clock"):
        if not isinstance(value[key], str) or not value[key]:
            raise ValueError(f"anticipation {key} must be a non-empty string")
    try:
        datetime.fromisoformat(value["predicted_at_wall_clock"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("anticipation predicted_at_wall_clock must be ISO-8601") from exc
    if value["prediction_status"] not in PREDICTION_STATUSES:
        raise ValueError("prediction_status must use the closed status vocabulary")
    if value["method"] not in ANTICIPATION_METHOD_VALUES:
        raise ValueError("anticipation method must use the closed method vocabulary")
    if not isinstance(value["expires_after_turns"], int) or value["expires_after_turns"] < 0:
        raise ValueError("expires_after_turns must be a non-negative integer")
    _validate_anticipation_targets(value["targets"])
    if value["prediction_status"] == "deliberate_skip" and not _all_unknown_targets(
        value["targets"]
    ):
        raise ValueError("deliberate_skip requires unknown-safe targets")
    _validate_epistemic_precision(
        precision=value["epistemic_precision"],
        source_ids=source_ids,
        targets=value["targets"],
        prediction_status=value["prediction_status"],
    )


def _validate_surprise_delta_value(
    *,
    value: Any,
    source_ids: list[str],
    state: DiagnosticState,
) -> None:
    if not source_ids or len(source_ids) != 1:
        raise ValueError("surprise_delta requires exactly one prediction_record_id source")
    if not isinstance(source_ids[0], str) or not source_ids[0]:
        raise ValueError("surprise_delta prediction_record_id source must be non-empty")
    if not isinstance(value, dict):
        raise ValueError("surprise_delta value must be an object")
    if set(value) != {"prediction_record_id", "matches", "surprise_score"}:
        raise ValueError("surprise_delta value must use the exact X.1 field set")
    if value["prediction_record_id"] != source_ids[0]:
        raise ValueError("surprise_delta source_ids must point to prediction_record_id")
    if state is DiagnosticState.NOT_OBSERVED:
        if value["matches"] is not None or value["surprise_score"] is not None:
            raise ValueError("not_observed surprise_delta requires null match/score")
        return
    matches = value["matches"]
    if not isinstance(matches, dict):
        raise ValueError("surprise_delta matches must be an object")
    if set(matches) != {
        "next_surface",
        "next_pressure_delta",
        "next_self_workspace_need",
    }:
        raise ValueError("surprise_delta matches must use the exact target keys")
    if not isinstance(matches["next_surface"], bool):
        raise ValueError("surprise_delta next_surface match must be boolean")
    if not isinstance(matches["next_self_workspace_need"], bool):
        raise ValueError("surprise_delta next_self_workspace_need match must be boolean")
    pressure = matches["next_pressure_delta"]
    if not isinstance(pressure, dict) or set(pressure) != {"matched", "total"}:
        raise ValueError("surprise_delta pressure match must be {matched,total}")
    if pressure["total"] != len(PRESSURE_NAMES):
        raise ValueError("surprise_delta pressure total drifted from PRESSURE_NAMES")
    if not (0 <= pressure["matched"] <= pressure["total"]):
        raise ValueError("surprise_delta matched pressure count out of bounds")
    if not isinstance(value["surprise_score"], int | float):
        raise ValueError("surprise_delta surprise_score must be numeric")
    if not (0.0 <= float(value["surprise_score"]) <= 1.0):
        raise ValueError("surprise_delta surprise_score must be in [0, 1]")


def _validate_loop_id(loop_id: Any) -> None:
    if not isinstance(loop_id, str):
        raise ValueError("open_loop loop_id must be a string")
    if not loop_id.startswith("loop:") or len(loop_id) != 21:
        raise ValueError("open_loop loop_id must use loop:<16-hex> shape")
    suffix = loop_id.removeprefix("loop:")
    if any(ch not in "0123456789abcdef" for ch in suffix):
        raise ValueError("open_loop loop_id must use loop:<16-hex> shape")


def _validate_open_loop_entry(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError("open_loop entry must be an object")
    extra = sorted(set(entry) - OPEN_LOOP_ENTRY_KEYS)
    if extra:
        raise ValueError(f"open_loop entry has unknown field(s): {extra!r}")
    missing = sorted(OPEN_LOOP_ENTRY_KEYS - set(entry))
    if missing:
        raise ValueError(f"open_loop entry missing required field(s): {missing!r}")
    _validate_loop_id(entry["loop_id"])
    prior_ids = entry["prior_loop_ids"]
    if not isinstance(prior_ids, list):
        raise ValueError("open_loop prior_loop_ids must be a list")
    for prior_id in prior_ids:
        _validate_loop_id(prior_id)
    if entry["loop_origin"] not in OPEN_LOOP_ORIGINS:
        raise ValueError("open_loop loop_origin must use the closed origin vocabulary")
    if entry["loop_kind"] not in OPEN_LOOP_KINDS:
        raise ValueError("open_loop loop_kind must use the closed kind vocabulary")
    if entry["provenance_status"] not in OPEN_LOOP_PROVENANCE_STATUSES:
        raise ValueError("open_loop provenance_status must use the closed status vocabulary")
    if entry["age_bucket"] not in OPEN_LOOP_AGE_BUCKETS:
        raise ValueError("open_loop age_bucket must use the closed bucket vocabulary")
    if entry["age_bucket_cutoff_version"] != OPEN_LOOP_AGE_BUCKET_CUTOFF_VERSION:
        raise ValueError("open_loop age_bucket_cutoff_version drifted")
    if not isinstance(entry["evidence_count"], int) or entry["evidence_count"] < 1:
        raise ValueError("open_loop evidence_count must be a positive integer")
    source_episode_ids = entry["source_episode_ids"]
    source_memory_ids = entry["source_memory_ids"]
    if (
        not isinstance(source_episode_ids, list)
        or len(source_episode_ids) != 1
        or not isinstance(source_episode_ids[0], str)
        or not source_episode_ids[0]
    ):
        raise ValueError("open_loop source_episode_ids must contain exactly one episode id")
    if not isinstance(source_memory_ids, list) or not source_memory_ids:
        raise ValueError("open_loop source_memory_ids must be a non-empty list")
    if not all(isinstance(source_id, str) and source_id for source_id in source_memory_ids):
        raise ValueError("open_loop source_memory_ids must be non-empty strings")
    if entry["epistemic_precision"] not in EPISTEMIC_PRECISION_VALUES:
        raise ValueError("open_loop epistemic_precision must use the closed precision vocabulary")
    precision = _open_loop_precision(source_memory_ids)
    if entry["epistemic_precision"] != precision:
        raise ValueError("open_loop epistemic_precision does not match source quality")


def _validate_open_loops_value(value: Any, source_ids: list[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError("open_loops value must be an object")
    required = {
        "registry_schema_version",
        "loop_id_basis_version",
        "observed_at_wall_clock",
        "loop_count",
        "top_loops",
        "omitted_loop_count",
    }
    extra = sorted(set(value) - required)
    if extra:
        raise ValueError(f"open_loops value has unknown field(s): {extra!r}")
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"open_loops value missing required field(s): {missing!r}")
    if value["registry_schema_version"] != OPEN_LOOP_REGISTRY_SCHEMA_VERSION:
        raise ValueError("open_loops registry_schema_version drifted")
    if value["loop_id_basis_version"] != OPEN_LOOP_ID_BASIS_VERSION:
        raise ValueError("open_loops loop_id_basis_version drifted")
    _parse_iso8601(
        str(value["observed_at_wall_clock"]),
        field_name="open_loops.observed_at_wall_clock",
    )
    if not isinstance(value["loop_count"], int) or value["loop_count"] < 0:
        raise ValueError("open_loops loop_count must be a non-negative integer")
    if not isinstance(value["omitted_loop_count"], int) or value["omitted_loop_count"] < 0:
        raise ValueError("open_loops omitted_loop_count must be a non-negative integer")
    top_loops = value["top_loops"]
    if not isinstance(top_loops, list):
        raise ValueError("open_loops top_loops must be a list")
    if value["loop_count"] < len(top_loops):
        raise ValueError("open_loops loop_count cannot be less than top_loops length")
    if value["omitted_loop_count"] != value["loop_count"] - len(top_loops):
        raise ValueError("open_loops omitted_loop_count must match omitted loops")
    if not top_loops and source_ids != ["diagnostic:open_loops:empty"]:
        raise ValueError("empty open_loops slot must use diagnostic empty source id")
    seen: set[str] = set()
    for entry in top_loops:
        _validate_open_loop_entry(entry)
        loop_id = entry["loop_id"]
        if loop_id in seen:
            raise ValueError(f"open-loop hash collision for {loop_id}")
        seen.add(loop_id)
    expected_source_ids = sorted(
        {
            source
            for entry in top_loops
            for source in (entry["source_episode_ids"] + entry["source_memory_ids"])
        }
    )
    if top_loops and sorted(source_ids) != expected_source_ids:
        raise ValueError("open_loops source_ids must match top_loop evidence ids")


def _filled_slots(names: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return {name: _default_slot() for name in names}


def _decoder_note(thesis_sha: str) -> dict[str, str]:
    return {
        "purpose": (
            "Observation-only moment assembly diagnostic. These records may "
            "shape future engineering attention but are not audit evidence."
        ),
        "architectural_thesis_path": THESIS_DOC_PATH,
        "thesis_doc_sha256": thesis_sha,
        "architectural_thesis_adr_id": ARCHITECTURAL_THESIS_ADR_ID,
        "audit_boundary": AUDIT_BOUNDARY,
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso8601(value: str, *, field_name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def loop_id_for_episode(episode_id: str) -> str:
    if not isinstance(episode_id, str) or not episode_id:
        raise ValueError("episode_id is required for open-loop hash")
    digest = hashlib.sha256(
        f"{OPEN_LOOP_HASH_INPUT_PREFIX}{episode_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"loop:{digest}"


def derive_open_loop_age_bucket(
    *,
    created_at: str,
    observed_at_wall_clock: str,
    prior_age_bucket: str | None = None,
) -> str:
    created = _parse_iso8601(created_at, field_name="open_loop.created_at")
    observed = _parse_iso8601(
        observed_at_wall_clock,
        field_name="open_loop.observed_at_wall_clock",
    )
    age_days = max(0.0, (observed - created).total_seconds() / 86_400.0)
    bucket = "long_running"
    for candidate, cutoff in _OPEN_LOOP_AGE_CUTOFFS_DAYS:
        if age_days < cutoff:
            bucket = candidate
            break
    if prior_age_bucket in OPEN_LOOP_AGE_BUCKETS:
        ordered = ("fresh", "recent", "stale", "long_running")
        idx = ordered.index(prior_age_bucket)
        lower = _OPEN_LOOP_AGE_CUTOFFS_DAYS[idx - 1][1] if idx > 0 else None
        upper = (
            _OPEN_LOOP_AGE_CUTOFFS_DAYS[idx][1] if idx < len(_OPEN_LOOP_AGE_CUTOFFS_DAYS) else None
        )
        if lower is not None and abs(age_days - lower) <= OPEN_LOOP_AGE_HYSTERESIS_DAYS:
            return prior_age_bucket
        if upper is not None and abs(age_days - upper) <= OPEN_LOOP_AGE_HYSTERESIS_DAYS:
            return prior_age_bucket
    return bucket


def _open_loop_origin(episode: dict[str, Any]) -> str:
    if (
        episode.get("source_kind") == "followup_doc"
        or episode.get("authorship") == "project_doc"
        or episode.get("memory_voice") == "external_to_maez"
    ):
        return "project_doc"
    return "maez_first_person"


def _open_loop_kind(episode: dict[str, Any]) -> str:
    source_kind = str(episode.get("source_kind") or "")
    text = str(episode.get("open_loop") or "").lower()
    if source_kind == "followup_doc":
        return "project_followup"
    if any(token in text for token in ("promise", "follow up", "follow-up", "owe")):
        return "pending_promise"
    if any(token in text for token in ("repair", "fix", "regression", "broken")):
        return "unresolved_repair"
    if any(token in text for token in ("continuity", "restart", "memory gap", "amnesia")):
        return "continuity_gap"
    if any(token in text for token in ("revisit", "return to", "circle back", "pending")):
        return "conversation_revisit"
    return "unknown"


def _open_loop_precision(source_memory_ids: list[str]) -> str:
    count = len(set(source_memory_ids))
    if count >= 3:
        return "high"
    if count >= 2:
        return "medium"
    if count >= 1:
        return "low"
    return "unknown"


def _build_open_loop_entry(
    *,
    episode: dict[str, Any],
    observed_at_wall_clock: str,
    provenance_status: str,
    prior_loop_ids: list[str] | None = None,
    prior_age_bucket: str | None = None,
) -> dict[str, Any]:
    episode_id = str(episode.get("id") or "")
    source_memory_ids = [str(source) for source in (episode.get("source_memory_ids") or [])]
    created_at = str(episode.get("created_at") or "")
    return {
        "loop_id": loop_id_for_episode(episode_id),
        "prior_loop_ids": list(prior_loop_ids or []),
        "loop_origin": _open_loop_origin(episode),
        "loop_kind": _open_loop_kind(episode),
        "provenance_status": provenance_status,
        "age_bucket": derive_open_loop_age_bucket(
            created_at=created_at,
            observed_at_wall_clock=observed_at_wall_clock,
            prior_age_bucket=prior_age_bucket,
        ),
        "age_bucket_cutoff_version": OPEN_LOOP_AGE_BUCKET_CUTOFF_VERSION,
        "evidence_count": len(set([episode_id, *source_memory_ids])),
        "source_episode_ids": [episode_id],
        "source_memory_ids": source_memory_ids,
        "epistemic_precision": _open_loop_precision(source_memory_ids),
    }


def build_open_loops_slot(
    *,
    episodes: list[dict[str, Any]],
    observed_at_wall_clock: str | None = None,
    max_loops: int = 5,
    provenance_status: str = "live",
) -> dict[str, Any]:
    observed = observed_at_wall_clock or _utc_now_iso()
    _parse_iso8601(observed, field_name="open_loops.observed_at_wall_clock")
    if provenance_status not in OPEN_LOOP_PROVENANCE_STATUSES:
        raise ValueError(f"unknown provenance_status {provenance_status!r}")
    if max_loops <= 0:
        raise ValueError("max_loops must be positive")
    open_loop_episodes = [episode for episode in episodes if episode.get("open_loop")]
    entries = [
        _build_open_loop_entry(
            episode=episode,
            observed_at_wall_clock=observed,
            provenance_status=provenance_status,
        )
        for episode in open_loop_episodes
    ]
    seen: set[str] = set()
    for entry in entries:
        loop_id = str(entry["loop_id"])
        if loop_id in seen:
            raise ValueError(f"open-loop hash collision for {loop_id}")
        seen.add(loop_id)
    created_by_loop_id = {
        loop_id_for_episode(str(episode.get("id") or "")): str(episode.get("created_at") or "")
        for episode in open_loop_episodes
    }
    entries.sort(key=lambda entry: entry["loop_id"])
    entries.sort(
        key=lambda entry: _parse_iso8601(
            created_by_loop_id[str(entry["loop_id"])],
            field_name="open_loop.created_at",
        ),
        reverse=True,
    )
    selected = entries[:max_loops]
    value = {
        "registry_schema_version": OPEN_LOOP_REGISTRY_SCHEMA_VERSION,
        "loop_id_basis_version": OPEN_LOOP_ID_BASIS_VERSION,
        "observed_at_wall_clock": observed,
        "loop_count": len(entries),
        "top_loops": selected,
        "omitted_loop_count": max(0, len(entries) - len(selected)),
    }
    source_ids: list[str]
    if entries:
        source_ids = sorted(
            {
                source
                for entry in selected
                for source in (entry["source_episode_ids"] + entry["source_memory_ids"])
            }
        )
    else:
        source_ids = ["diagnostic:open_loops:empty"]
    slot = {
        "schema_version": ORGAN_SCHEMA_VERSION,
        "state": DiagnosticState.EMITTED_VALUE.value,
        "value": value,
        "source_ids": source_ids,
    }
    validate_slot("candidate_sources.open_loops", slot)
    return slot


def build_anticipation_slot(
    *,
    prediction_id: str,
    predicted_at_turn_id: str,
    targets: dict[str, Any],
    epistemic_precision: str,
    method: str,
    expires_after_turns: int,
    predicted_at_wall_clock: str | None = None,
    source_ids: list[str],
    prediction_status: str = "predicted",
) -> dict[str, Any]:
    value = {
        "prediction_id": prediction_id,
        "predicted_at_turn_id": predicted_at_turn_id,
        "prediction_status": prediction_status,
        "targets": targets,
        "epistemic_precision": epistemic_precision,
        "method": method,
        "expires_after_turns": expires_after_turns,
        "predicted_at_wall_clock": predicted_at_wall_clock or _utc_now_iso(),
    }
    slot = {
        "schema_version": ORGAN_SCHEMA_VERSION,
        "state": DiagnosticState.EMITTED_VALUE.value,
        "value": value,
        "source_ids": list(source_ids),
    }
    validate_slot("anticipation", slot)
    return slot


def build_surprise_delta_slot(
    *,
    prediction_record_id: str,
    matched_surface: bool | None = None,
    matched_pressure_count: int | None = None,
    total_pressure_count: int | None = None,
    matched_workspace_need: bool | None = None,
    surprise_score: float | None = None,
    expired_without_observation: bool = False,
) -> dict[str, Any]:
    if expired_without_observation:
        slot = {
            "schema_version": ORGAN_SCHEMA_VERSION,
            "state": DiagnosticState.NOT_OBSERVED.value,
            "value": {
                "prediction_record_id": prediction_record_id,
                "matches": None,
                "surprise_score": None,
            },
            "source_ids": [prediction_record_id],
        }
        validate_slot("surprise_delta", slot)
        return slot
    if matched_surface is None or matched_workspace_need is None:
        raise ValueError("observed surprise_delta requires surface and workspace matches")
    if matched_pressure_count is None or total_pressure_count is None:
        raise ValueError("observed surprise_delta requires pressure match counts")
    if surprise_score is None:
        surface_score = 1.0 if matched_surface else 0.0
        pressure_score = matched_pressure_count / total_pressure_count
        workspace_score = 1.0 if matched_workspace_need else 0.0
        surprise_score = round(1.0 - ((surface_score + pressure_score + workspace_score) / 3.0), 6)
    slot = {
        "schema_version": ORGAN_SCHEMA_VERSION,
        "state": DiagnosticState.EMITTED_VALUE.value,
        "value": {
            "prediction_record_id": prediction_record_id,
            "matches": {
                "next_surface": bool(matched_surface),
                "next_pressure_delta": {
                    "matched": int(matched_pressure_count),
                    "total": int(total_pressure_count),
                },
                "next_self_workspace_need": bool(matched_workspace_need),
            },
            "surprise_score": float(surprise_score),
        },
        "source_ids": [prediction_record_id],
    }
    validate_slot("surprise_delta", slot)
    return slot


def build_diagnostic_record(
    *,
    surface: str,
    source_ids: list[str],
    pressure_vector: dict[str, dict[str, Any]] | None = None,
    pressure_delta: dict[str, dict[str, Any]] | None = None,
    candidate_sources: dict[str, dict[str, Any]] | None = None,
    bond_topology: dict[str, dict[str, Any]] | None = None,
    workspace_selection: dict[str, Any] | None = None,
    anticipation: dict[str, Any] | None = None,
    surprise_delta: dict[str, Any] | None = None,
    interpretation_candidates: dict[str, Any] | None = None,
    assembly_path: str = "observed",
    source_id_synthetic: bool | None = None,
    bypass_reason: str = "",
    bypass_note: str = "",
    lifecycle_phase: str = "",
) -> dict[str, Any]:
    thesis_sha = _sha256_repo_file(THESIS_DOC_PATH)
    record = {
        "schema_version": MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA,
        "created_at": time.time(),
        "record_id": str(uuid4()),
        "surface": surface,
        "assembly_path": assembly_path,
        "source_ids": list(source_ids),
        "audit_boundary": AUDIT_BOUNDARY,
        "thesis_doc_sha256": thesis_sha,
        "decoder_note": _decoder_note(thesis_sha),
        "contributing_schemas": default_contributing_schemas(),
        "pressure_vector": pressure_vector or _filled_slots(PRESSURE_NAMES),
        "pressure_delta": pressure_delta or _filled_slots(PRESSURE_NAMES),
        "candidate_sources": candidate_sources or _filled_slots(CANDIDATE_SOURCE_NAMES),
        "workspace_selection": workspace_selection or _default_slot(),
        "anticipation": anticipation or _default_slot(),
        "surprise_delta": surprise_delta or _default_slot(),
        "bond_topology": bond_topology or _filled_slots(TOPOLOGY_NAMES),
        "interpretation_candidates": interpretation_candidates or _default_slot(),
    }
    if source_id_synthetic is not None:
        record["source_id_synthetic"] = bool(source_id_synthetic)
    if bypass_reason:
        record["bypass_reason"] = bypass_reason
    if assembly_path == "bypassed" or bypass_note:
        record["bypass_note"] = bypass_note
    if lifecycle_phase:
        record["lifecycle_phase"] = lifecycle_phase
    validate_record(record)
    return record


def build_bypassed_record(
    *,
    surface: str,
    turn_id: str,
    bypass_reason: str,
    lifecycle_phase: str,
    source_id_synthetic: bool = False,
    bypass_note: str = "",
) -> dict[str, Any]:
    return build_diagnostic_record(
        surface=surface,
        source_ids=[turn_id],
        assembly_path="bypassed",
        workspace_selection=_default_slot(DiagnosticState.NOT_OBSERVED),
        source_id_synthetic=source_id_synthetic,
        bypass_reason=bypass_reason,
        bypass_note=bypass_note,
        lifecycle_phase=lifecycle_phase,
    )


def _validate_group(
    *,
    record: dict[str, Any],
    group_name: str,
    schema_group: str,
) -> None:
    group = record[group_name]
    if not isinstance(group, dict):
        raise ValueError(f"{group_name}: group must be object")
    for name, slot in group.items():
        validate_slot(f"{group_name}.{name}", slot)
        expected = record["contributing_schemas"].get(_organ_key(schema_group, name))
        if expected != slot["schema_version"]:
            raise ValueError(f"{group_name}.{name}: schema_version mismatch")


def validate_record(record: dict[str, Any]) -> None:
    if record.get("schema_version") not in {1, MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA}:
        raise ValueError("schema_version mismatch")
    if record.get("audit_boundary") != AUDIT_BOUNDARY:
        raise ValueError("audit_boundary must be not_audit_evidence")
    if not record.get("source_ids"):
        raise ValueError("record source_ids must be non-empty")
    if "thesis_doc_sha256" not in record:
        raise ValueError("thesis_doc_sha256 is required")
    if record.get("assembly_path") == "bypassed":
        if "source_id_synthetic" not in record:
            raise ValueError("bypassed record requires source_id_synthetic")
        reason = record.get("bypass_reason")
        if reason not in BYPASS_REASONS:
            raise ValueError(f"unknown bypass_reason {reason!r}")
        if record.get("schema_version") >= 2 or "bypass_note" in record:
            _validate_bypass_note(record.get("bypass_note", ""))
        if not record.get("lifecycle_phase"):
            raise ValueError("bypassed record requires lifecycle_phase")
    schemas = record.get("contributing_schemas")
    if not isinstance(schemas, dict):
        raise ValueError("contributing_schemas is required")
    _validate_group(record=record, group_name="pressure_vector", schema_group="pressure")
    _validate_group(
        record=record,
        group_name="pressure_delta",
        schema_group="pressure_delta",
    )
    _validate_group(
        record=record,
        group_name="candidate_sources",
        schema_group="candidate_source",
    )
    _validate_group(record=record, group_name="bond_topology", schema_group="bond_topology")
    for name in (
        "workspace_selection",
        "anticipation",
        "surprise_delta",
        "interpretation_candidates",
    ):
        slot = record[name]
        validate_slot(name, slot)
        if record["contributing_schemas"].get(_organ_key(name)) != slot["schema_version"]:
            raise ValueError(f"{name}: schema_version mismatch")


def write_diagnostic_record(*, record: dict[str, Any], log_path: Path) -> None:
    validate_record(record)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def normalize_diagnostic_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(record)
    if (
        normalized.get("schema_version") == 1
        and normalized.get("assembly_path") == "bypassed"
        and "bypass_note" not in normalized
    ):
        normalized["bypass_note"] = ""
    return normalized


def _read_diagnostic_records(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(normalize_diagnostic_record(json.loads(line)))
        except json.JSONDecodeError as exc:
            _warn_jsonl_replay_skip_once(
                log_path=log_path,
                line_no=line_no,
                error=exc,
            )
    return records


def _warn_jsonl_replay_skip_once(
    *,
    log_path: Path,
    line_no: int,
    error: json.JSONDecodeError,
) -> None:
    try:
        key = log_path.resolve()
    except OSError:
        key = log_path
    if key in _READ_FAILURE_WARNED_PATHS:
        return
    _READ_FAILURE_WARNED_PATHS.add(key)
    _LOGGER.warning(
        "jsonl_replay_skip path=%s line=%s error=%s",
        log_path,
        line_no,
        error,
    )


def write_anticipation_record(
    *,
    surface: str,
    turn_id: str | None,
    anticipation: dict[str, Any],
    log_path: Path = DEFAULT_LOG_PATH,
    mark_current_turn_observed: bool = False,
) -> str:
    source_id = str(turn_id) if turn_id else f"completion:{surface}:{uuid4()}"
    surprise_delta = build_slot(
        DiagnosticState.EMITTED_NULL,
        value=None,
        source_ids=[str(anticipation["value"]["prediction_id"])],
    )
    record = build_diagnostic_record(
        surface=surface,
        source_ids=[source_id],
        assembly_path="observed",
        anticipation=anticipation,
        surprise_delta=surprise_delta,
        source_id_synthetic=not bool(turn_id),
    )
    write_diagnostic_record(record=record, log_path=log_path)
    record_id = str(record["record_id"])
    if mark_current_turn_observed:
        mark_current_moment_assembly_observed(record_id=record_id)
    return record_id


def write_open_loops_record(
    *,
    surface: str,
    turn_id: str | None,
    open_loops: dict[str, Any],
    log_path: Path = DEFAULT_LOG_PATH,
    mark_current_turn_observed: bool = False,
) -> str:
    source_id = str(turn_id) if turn_id else f"completion:{surface}:{uuid4()}"
    candidate_sources = _filled_slots(CANDIDATE_SOURCE_NAMES)
    candidate_sources["open_loops"] = open_loops
    record = build_diagnostic_record(
        surface=surface,
        source_ids=[source_id],
        assembly_path="observed",
        candidate_sources=candidate_sources,
        source_id_synthetic=not bool(turn_id),
    )
    write_diagnostic_record(record=record, log_path=log_path)
    record_id = str(record["record_id"])
    if mark_current_turn_observed:
        mark_current_moment_assembly_observed(record_id=record_id)
    return record_id


def _reconciled_prediction_record_ids(records: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for record in records:
        slot = record.get("surprise_delta") or {}
        source_ids = slot.get("source_ids") or []
        value = slot.get("value") or {}
        prediction_id = value.get("prediction_record_id") if isinstance(value, dict) else None
        if prediction_id and source_ids == [prediction_id]:
            out.add(str(prediction_id))
    return out


def find_latest_unreconciled_anticipation(
    *,
    log_path: Path = DEFAULT_LOG_PATH,
) -> dict[str, Any] | None:
    records = _read_diagnostic_records(log_path)
    reconciled = _reconciled_prediction_record_ids(records)
    for record in reversed(records):
        slot = record.get("anticipation") or {}
        if slot.get("state") != DiagnosticState.EMITTED_VALUE.value:
            continue
        record_id = str(record.get("record_id") or "")
        if not record_id or record_id in reconciled:
            continue
        value = slot.get("value") or {}
        if not isinstance(value, dict):
            continue
        if int(value.get("expires_after_turns") or 0) <= 0:
            continue
        return record
    return None


def reconcile_latest_anticipation(
    *,
    surface: str,
    turn_id: str | None,
    observed_surface: str,
    observed_pressure_delta: dict[str, str],
    observed_self_workspace_need: list[str],
    log_path: Path = DEFAULT_LOG_PATH,
) -> str | None:
    prediction = find_latest_unreconciled_anticipation(log_path=log_path)
    if prediction is None:
        return None
    targets = prediction["anticipation"]["value"]["targets"]
    if set(observed_pressure_delta) != set(PRESSURE_NAMES):
        _write_pressure_schema_drift_record(
            surface=surface,
            turn_id=turn_id,
            prediction_record_id=str(prediction["record_id"]),
            log_path=log_path,
        )
        raise ValueError("pressure_schema_drift: observed_pressure_delta keys drifted")
    predicted_pressure = targets["next_pressure_delta"]
    matched_pressure_count = sum(
        1
        for name in PRESSURE_NAMES
        if predicted_pressure.get(name) == observed_pressure_delta.get(name)
    )
    surprise_delta = build_surprise_delta_slot(
        prediction_record_id=str(prediction["record_id"]),
        matched_surface=targets["next_surface"] == observed_surface,
        matched_pressure_count=matched_pressure_count,
        total_pressure_count=len(PRESSURE_NAMES),
        matched_workspace_need=set(targets["next_self_workspace_need"])
        == set(observed_self_workspace_need),
    )
    source_id = str(turn_id) if turn_id else f"completion:{surface}:{uuid4()}"
    record = build_diagnostic_record(
        surface=surface,
        source_ids=[source_id],
        assembly_path="observed",
        anticipation=_default_slot(DiagnosticState.NOT_OBSERVED),
        surprise_delta=surprise_delta,
        source_id_synthetic=not bool(turn_id),
    )
    write_diagnostic_record(record=record, log_path=log_path)
    return str(record["record_id"])


def _write_pressure_schema_drift_record(
    *,
    surface: str,
    turn_id: str | None,
    prediction_record_id: str,
    log_path: Path,
) -> str:
    source_id = str(turn_id) if turn_id else f"completion:{surface}:{uuid4()}"
    record = build_diagnostic_record(
        surface=surface,
        source_ids=[source_id],
        assembly_path="observed",
        anticipation=_default_slot(DiagnosticState.NOT_OBSERVED),
        surprise_delta=build_slot(
            DiagnosticState.ERROR,
            value=None,
            source_ids=[prediction_record_id],
            error_class="pressure_schema_drift",
        ),
        source_id_synthetic=not bool(turn_id),
    )
    write_diagnostic_record(record=record, log_path=log_path)
    return str(record["record_id"])


def expire_latest_anticipation(
    *,
    surface: str,
    turn_id: str | None,
    log_path: Path = DEFAULT_LOG_PATH,
) -> str | None:
    prediction = find_latest_unreconciled_anticipation(log_path=log_path)
    if prediction is None:
        return None
    surprise_delta = build_surprise_delta_slot(
        prediction_record_id=str(prediction["record_id"]),
        expired_without_observation=True,
    )
    source_id = str(turn_id) if turn_id else f"completion:{surface}:{uuid4()}"
    record = build_diagnostic_record(
        surface=surface,
        source_ids=[source_id],
        assembly_path="observed",
        anticipation=_default_slot(DiagnosticState.NOT_OBSERVED),
        surprise_delta=surprise_delta,
        source_id_synthetic=not bool(turn_id),
    )
    write_diagnostic_record(record=record, log_path=log_path)
    return str(record["record_id"])


def write_bypassed_record(*, surface: str, turn_id: str, log_path: Path) -> None:
    record = build_bypassed_record(
        surface=surface,
        turn_id=turn_id,
        bypass_reason="not_called",
        lifecycle_phase="turn_close",
        bypass_note="",
    )
    write_diagnostic_record(record=record, log_path=log_path)


def complete_moment_assembly_turn(
    *,
    surface: str,
    turn_id: str | None,
    diagnostic_observed: bool,
    bypass_reason: str,
    lifecycle_phase: str,
    bypass_note: str = "",
    log_path: Path = DEFAULT_LOG_PATH,
) -> str | None:
    """Close an owner-private turn with exactly one diagnostic completion row.

    X.0.2 uses this as an allowlisted production seam. When a future
    organ has already emitted an observed diagnostic row, callers pass
    ``diagnostic_observed=True`` and this helper does not add a bypass row.
    """
    if diagnostic_observed:
        return None
    source_id_synthetic = not bool(turn_id)
    source_id = str(turn_id) if turn_id else f"completion:{surface}:{uuid4()}"
    record = build_bypassed_record(
        surface=surface,
        turn_id=source_id,
        bypass_reason=bypass_reason,
        lifecycle_phase=lifecycle_phase,
        source_id_synthetic=source_id_synthetic,
        bypass_note=bypass_note,
    )
    write_diagnostic_record(record=record, log_path=log_path)
    return str(record["record_id"])


def _validate_bypass_note(note: Any) -> None:
    if not isinstance(note, str):
        raise ValueError("bypass_note must be a string")
    if len(note) > BYPASS_NOTE_MAX_CHARS:
        raise ValueError("bypass_note exceeds 500 characters")
    if "\n" in note or "\r" in note:
        raise ValueError("bypass_note must be single-line")
    if "Traceback (" in note:
        raise ValueError("bypass_note must not contain tracebacks")


def _exception_bypass_note(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    note = f"{type(exc).__name__}: {exc}"
    return note[:BYPASS_NOTE_MAX_CHARS]


def _warn_diagnostic_write_failure_once(
    *,
    surface: str,
    lifecycle_phase: str,
    error: BaseException,
) -> None:
    key = (surface, lifecycle_phase)
    if key in _WRITE_FAILURE_WARNED_KEYS:
        return
    _WRITE_FAILURE_WARNED_KEYS.add(key)
    _LOGGER.warning(
        "moment assembly diagnostic write failed (surface=%s lifecycle_phase=%s): %s",
        surface,
        lifecycle_phase,
        error,
    )


class MomentAssemblyTurn:
    """Runtime closure guard for one owner-private turn."""

    def __init__(
        self,
        *,
        surface: str,
        turn_id: str | None,
        lifecycle_phase: str,
        log_path: Path = DEFAULT_LOG_PATH,
    ) -> None:
        self.surface = surface
        self.turn_id = turn_id
        self.lifecycle_phase = lifecycle_phase
        self.log_path = log_path
        self._completed = False
        self.observed_record_id = ""
        self._token: contextvars.Token[MomentAssemblyTurn | None] | None = None

    def __enter__(self) -> MomentAssemblyTurn:
        self._token = _CURRENT_TURN.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._token is not None:
            _CURRENT_TURN.reset(self._token)
            self._token = None
        if not self._completed:
            reason = "exception" if exc_type is not None else "not_called"
            note = _exception_bypass_note(exc) if exc_type is not None else ""
            self._write_bypass(reason=reason, note=note)
        return False

    def mark_observed(self, *, record_id: str = "") -> None:
        if self._completed:
            raise RuntimeError("moment assembly turn already completed")
        if not record_id:
            raise ValueError("record_id is required for observed moment assembly turns")
        self.observed_record_id = record_id
        self._completed = True

    def _write_bypass(self, *, reason: str, note: str) -> None:
        if self._completed:
            raise RuntimeError("moment assembly turn already completed")
        try:
            complete_moment_assembly_turn(
                surface=self.surface,
                turn_id=self.turn_id,
                diagnostic_observed=False,
                bypass_reason=reason,
                bypass_note=note,
                lifecycle_phase=self.lifecycle_phase,
                log_path=self.log_path,
            )
            self._completed = True
        except Exception as write_exc:
            _warn_diagnostic_write_failure_once(
                surface=self.surface,
                lifecycle_phase=self.lifecycle_phase,
                error=write_exc,
            )
            self._completed = True


def moment_assembly_turn(
    *,
    surface: str,
    turn_id: str | None,
    lifecycle_phase: str,
    log_path: Path = DEFAULT_LOG_PATH,
) -> MomentAssemblyTurn:
    return MomentAssemblyTurn(
        surface=surface,
        turn_id=turn_id,
        lifecycle_phase=lifecycle_phase,
        log_path=log_path,
    )


def mark_current_moment_assembly_observed(*, record_id: str = "") -> None:
    current = _CURRENT_TURN.get()
    if current is None:
        raise RuntimeError("no active moment assembly turn")
    current.mark_observed(record_id=record_id)
