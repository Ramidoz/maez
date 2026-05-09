# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Moment Assembly Diagnostic records.

Schema evolution contract: additive-only fields, never rename existing
keys, never reorder existing semantics, and bump the relevant per-organ
schema whenever an organ's emitted shape changes. Unknown or reserved
enum values must fail in old readers instead of being silently accepted.
"""

from __future__ import annotations

from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4


MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA = 1
AUDIT_BOUNDARY = "not_audit_evidence"
DEFAULT_LOG_PATH = Path("logs/moment_assembly_diagnostic.jsonl")
THESIS_DOC_PATH = "docs/governance/ARCHITECTURAL_THESIS.md"
ARCHITECTURAL_THESIS_ADR_ID = "ARCHITECTURAL_THESIS"

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
DEPRECATION_REASONS = frozenset(
    {
        "superseded",
        "obsolete",
        "consolidated",
        "retired_for_audit",
        "retired_for_clarity",
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
    validate_record(record)
    return record


def build_bypassed_record(*, surface: str, turn_id: str) -> dict[str, Any]:
    return build_diagnostic_record(
        surface=surface,
        source_ids=[turn_id],
        assembly_path="bypassed",
        workspace_selection=_default_slot(DiagnosticState.NOT_OBSERVED),
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
    if record.get("schema_version") != MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA:
        raise ValueError("schema_version mismatch")
    if record.get("audit_boundary") != AUDIT_BOUNDARY:
        raise ValueError("audit_boundary must be not_audit_evidence")
    if not record.get("source_ids"):
        raise ValueError("record source_ids must be non-empty")
    if "thesis_doc_sha256" not in record:
        raise ValueError("thesis_doc_sha256 is required")
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


def write_bypassed_record(*, surface: str, turn_id: str, log_path: Path) -> None:
    write_diagnostic_record(
        record=build_bypassed_record(surface=surface, turn_id=turn_id),
        log_path=log_path,
    )
