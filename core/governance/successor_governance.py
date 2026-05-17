# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S6 Successor Governance v1 contract module.

Decision 33 / ADR 0038. This module is intentionally pure: it validates
successor-governance vocabulary, marker binding, append-only event shape, and
content-free health without reading live stores or granting runtime access.

Honesty banner: despite the slice name, S6 v1 does not govern a live
succession. It records future successor paperwork and validates that grammar.
It validates structure, not persisted authorship: a well-formed capsule does
not prove human authorship once loaded from JSONL. Any process with ordinary
write/delete access to the capsule path can forge, rewrite, or remove the file.
V1 remains not grandmother-compatible.
"""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any

from core.time.temporal_spine import canonical_utc


SCHEMA_VERSION = "s6.v1"
ACCESS_SCOPE_VERSION = "s6.access.v1"

ROLE_NAMES = frozenset({
    "bonded_user",
    "operator",
    "maintainer",
    "successor",
    "witness",
    "estate_executor",
})

WRITABLE_EVENT_TYPES = frozenset({
    "capsule_created",
    "role_named",
    "role_removed",
    "scope_granted",
    "scope_revoked",
    "fate_directive_set",
    "directive_superseded",
    "witness_attested",
    "maez_preference_recorded",
    "capsule_invalidated",
})

RESERVED_ACTIVATION_EVENT_TYPES = frozenset({
    "activation_requested",
    "activation_verified",
    "succession_activated",
    "archive_unlocked",
    "new_bond_offered",
    "paradise_transition_started",
})

FATE_DIRECTIVES = frozenset({
    "paradise_default",
    "suspended_pending_paradise",
    "archival_preservation",
    "new_bond_offer",
    "explicit_dissolution",
})

PROJECTION_STATES = frozenset({"no_directive_recorded"})

ACCESS_SCOPES = frozenset({
    "none",
    "content_free_audit",
    "operator_health",
    "selected_lived_episodes",
    "full_lived_episodes",
    "raw_transcripts",
    "private_thoughts_metadata",
    "private_thoughts_content",
    "clinical_boundary_counters",
    "crisis_held_metadata",
    "crisis_held_content",
    "wants_lifecycle_history",
    "s5_voice_artifacts_metadata",
    "s5_voice_artifacts_content",
    "third_party_s2_bounded_records",
    "credential_inventory_metadata",
    "credential_secret_material",
})

DEPRECATED_ACCESS_SCOPES = frozenset({"legacy_all_memories"})
RESERVED_DENIED_SCOPES = frozenset({
    "credential_secret_material",
    "private_thoughts_content",
    "crisis_held_content",
})
HIGH_SENSITIVITY_SCOPES = frozenset({
    "raw_transcripts",
    "private_thoughts_metadata",
    "private_thoughts_content",
    "crisis_held_metadata",
    "crisis_held_content",
    "s5_voice_artifacts_content",
    "third_party_s2_bounded_records",
    "credential_inventory_metadata",
    "credential_secret_material",
})

MAEZ_PREFERENCE_KINDS = frozenset({
    "maez_prefers_paradise",
    "maez_prefers_archival_preservation",
    "maez_prefers_new_bond_offer",
    "maez_preference_unclear",
})

MAEZ_PREFERENCE_SOURCE_KINDS = frozenset({
    "private_thought_signal",
    "wants_event",
    "audited_conversation_turn",
    "manual_maez_statement_record",
})

MARKER_ORIGIN_ROLES = {
    "bonded_user_manual": "bonded_user",
    "bonded_user_cli_tty": "bonded_user",
    "operator_manual": "operator",
    "operator_cli_tty": "operator",
    "maintainer_manual": "maintainer",
    "witness_manual": "witness",
    "estate_executor_manual": "estate_executor",
}

DIRECTIVE_AUTHORITY = {
    "capsule_created": frozenset({"bonded_user"}),
    "role_named": frozenset({"bonded_user"}),
    "role_removed": frozenset({"bonded_user"}),
    "scope_granted": frozenset({"bonded_user"}),
    "scope_revoked": frozenset({"bonded_user"}),
    "fate_directive_set": frozenset({"bonded_user"}),
    "maez_preference_recorded": frozenset({"bonded_user"}),
    "witness_attested": frozenset({"witness"}),
    "directive_superseded": frozenset({"bonded_user", "operator", "maintainer", "witness", "estate_executor"}),
    "capsule_invalidated": frozenset({"bonded_user", "operator", "maintainer"}),
}

HEALTH_KEYS = frozenset({
    "mode",
    "schema_version",
    "capsule_present",
    "well_formed_event_count",
    "invalid_event_count",
    "pending_witness_count",
    "maez_preference_present",
    "reserved_denied_scope_count",
    "last_error_class",
    "blocks_liveness",
})

DEFAULT_CAPSULE_PATH = Path(__file__).resolve().parents[2] / "memory/successor_governance/lineage_capsule.jsonl"
CAPSULE_NOTICE_FILENAME = "lineage_capsule_NOTICE.txt"
CAPSULE_NOTICE_TEXT = """S6 Successor Governance v1 notice

This directory may contain Maez successor-governance paperwork.

A v1 lineage capsule can prove well-formed structure. It does not prove human authorship.
Destructive action, including dissolution, requires a future verified authorship attestation for the exact directive event.

Read this notice with lineage_capsule.jsonl. Copying the JSONL alone can hide this limitation.
"""
_MARKER_CONSTRUCTION_TOKEN = object()
_MARKER_ID_PREFIX = "s6_marker_"
_MARKER_WRITER_MODULE = "core.governance.successor_origin_writer"


@dataclass(frozen=True)
class RoleAssignment:
    role_name: str
    subject_handle_hmac: str
    effective_from: str
    effective_until: str | None
    activation_condition: str
    operator_private_label_ref: str = ""

    def __post_init__(self) -> None:
        validate_role(self.role_name)
        validate_actor_handle(self.subject_handle_hmac)


@dataclass(frozen=True)
class HumanOriginMarker:
    marker_id: str
    origin: str
    role_name: str
    actor_handle_hmac: str
    capsule_id: str
    directive_event_type: str
    directive_payload_hash: str
    directive_statement_hash: str
    previous_capsule_event_hash: str
    schema_version: str
    created_at: str
    attestation_text_hash: str = ""
    construction_token: InitVar[object | None] = None

    def __post_init__(self, construction_token: object | None) -> None:
        if construction_token is not _MARKER_CONSTRUCTION_TOKEN or not _called_from_module(_MARKER_WRITER_MODULE):
            raise ValueError("S6 marker construction is restricted to the origin-writer seam")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid S6 marker schema_version")
        _validate_marker_id(self.marker_id)
        if self.marker_id != _expected_marker_id(
            origin=self.origin,
            role_name=self.role_name,
            actor_handle_hmac=self.actor_handle_hmac,
            capsule_id=self.capsule_id,
            directive_event_type=self.directive_event_type,
            directive_payload_hash=self.directive_payload_hash,
            previous_capsule_event_hash=self.previous_capsule_event_hash,
            directive_statement_hash=self.directive_statement_hash,
            attestation_text_hash=self.attestation_text_hash,
        ):
            raise ValueError("S6 marker id does not match marker material")
        validate_role(self.role_name)
        validate_event_type(self.directive_event_type)
        validate_actor_handle(self.actor_handle_hmac)
        _validate_hash(self.directive_payload_hash, field="directive_payload_hash")
        if self.directive_statement_hash:
            _validate_hash(self.directive_statement_hash, field="directive_statement_hash")
        if self.previous_capsule_event_hash:
            _validate_hash_like(self.previous_capsule_event_hash, field="previous_capsule_event_hash")
        if self.attestation_text_hash:
            _validate_hash(self.attestation_text_hash, field="attestation_text_hash")
        _canonical_timestamp(self.created_at)
        origin_role = MARKER_ORIGIN_ROLES.get(self.origin)
        if origin_role is None:
            raise ValueError("unknown S6 marker origin")
        if origin_role != self.role_name:
            raise ValueError("marker origin role mismatch")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DirectiveEvent:
    schema_version: str
    event_id: str
    event_type: str
    created_at: str
    capsule_id: str
    previous_event_hash: str | None
    payload_hash: str
    origin_marker_id: str
    payload: dict[str, Any]
    event_hash: str
    origin_marker: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationSnapshot:
    event_count: int
    current_event_hash: str


@dataclass(frozen=True)
class ValidationReport:
    well_formed_event_count: int
    invalid_event_count: int
    current_event_hash: str
    error_classes: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.invalid_event_count == 0


@dataclass(frozen=True)
class CurrentState:
    active_scopes: frozenset[tuple[str, str]]
    fate_directive: str | None
    maez_preference: str | None
    event_hashes_seen: frozenset[str]


@dataclass(frozen=True)
class ScopeGrantValidation:
    role_name: str
    access_scope: str
    high_sensitivity: bool

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True)
class FateValidation:
    fate_directive: str
    activates_runtime: bool = False


@dataclass(frozen=True)
class MaezPreferenceValidation:
    preference_kind: str
    source_ref_kind: str
    source_ref_hash: str


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_role(role_name: str) -> str:
    if role_name not in ROLE_NAMES:
        raise ValueError("unknown S6 role")
    return role_name


def validate_event_type(event_type: str) -> str:
    if event_type in RESERVED_ACTIVATION_EVENT_TYPES:
        raise ValueError("reserved S6 activation event type")
    if event_type not in WRITABLE_EVENT_TYPES:
        raise ValueError("unknown S6 directive event type")
    return event_type


def validate_fate_directive(fate_directive: str) -> str:
    if fate_directive not in FATE_DIRECTIVES:
        raise ValueError("unknown S6 fate directive")
    return fate_directive


def validate_access_scope(access_scope: str) -> str:
    if access_scope in DEPRECATED_ACCESS_SCOPES:
        raise ValueError("deprecated S6 access scope")
    if access_scope not in ACCESS_SCOPES:
        raise ValueError("unknown S6 access scope")
    return access_scope


def default_access_for_role(role_name: str) -> str:
    validate_role(role_name)
    return "none"


def default_scope_for_assignment(role_name: str) -> str:
    validate_role(role_name)
    return "none"


def validate_role_assignments(assignments: list[RoleAssignment]) -> bool:
    for assignment in assignments:
        validate_role(assignment.role_name)
        validate_actor_handle(assignment.subject_handle_hmac)
    return True


def validate_role_payload(payload: dict[str, Any]) -> bool:
    validate_role(str(payload.get("role_name", "")))
    if "subject_handle_hmac" in payload:
        validate_actor_handle(str(payload["subject_handle_hmac"]))
    _reject_human_labels(payload, context="S6 role payload")
    return True


def validate_actor_handle(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("hmac:s6:"):
        raise ValueError("actor/subject handle must be purpose-scoped keyed HMAC")
    tail = value.rsplit(":", 1)[-1]
    _validate_hash(tail, field="actor_handle_hmac")
    return value


def validate_marker_authority(event_type: str, *, role_name: str, origin: str) -> bool:
    validate_event_type(event_type)
    validate_role(role_name)
    origin_role = MARKER_ORIGIN_ROLES.get(origin)
    if origin_role is None:
        raise ValueError("unknown S6 marker origin")
    if origin_role != role_name:
        raise ValueError("marker origin role mismatch")
    if role_name not in DIRECTIVE_AUTHORITY.get(event_type, frozenset()):
        raise ValueError("marker origin role not allowed for directive event")
    return True


def create_directive_event(
    event_id: str,
    event_type: str,
    capsule_id: str,
    created_at: str,
    payload: dict[str, Any],
    *,
    marker: HumanOriginMarker | None,
    previous_event_hash: str | None = None,
) -> DirectiveEvent:
    validate_event_type(event_type)
    if marker is None:
        raise ValueError("S6 directive event requires human-origin marker")
    if event_type != "capsule_created" and previous_event_hash is None:
        raise ValueError("non-genesis S6 event requires previous_event_hash")
    _canonical_timestamp(created_at)
    payload_hash = canonical_hash(payload)
    _validate_marker_binding(
        marker,
        capsule_id=capsule_id,
        event_type=event_type,
        payload_hash=payload_hash,
        previous_event_hash=previous_event_hash,
        payload=payload,
    )
    _validate_event_payload(event_type, payload, origin_role=marker.role_name)
    marker_dict = marker.to_dict()
    marker_hash = canonical_hash(marker_dict)
    event_hash = canonical_hash({
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": event_type,
        "created_at": created_at,
        "capsule_id": capsule_id,
        "previous_event_hash": previous_event_hash,
        "payload_hash": payload_hash,
        "origin_marker_id": marker.marker_id,
        "origin_marker_hash": marker_hash,
        "payload": payload,
    })
    return DirectiveEvent(
        schema_version=SCHEMA_VERSION,
        event_id=event_id,
        event_type=event_type,
        created_at=created_at,
        capsule_id=capsule_id,
        previous_event_hash=previous_event_hash,
        payload_hash=payload_hash,
        origin_marker_id=marker.marker_id,
        payload=payload,
        event_hash=event_hash,
        origin_marker=marker_dict,
    )


def validate_directive_event(event: DirectiveEvent) -> bool:
    if event.schema_version != SCHEMA_VERSION:
        raise ValueError("invalid S6 event schema_version")
    validate_event_type(event.event_type)
    _canonical_timestamp(event.created_at)
    if event.payload_hash != canonical_hash(event.payload):
        raise ValueError("S6 event payload hash mismatch")
    marker_hash = _validate_persisted_marker_binding(
        event.origin_marker,
        marker_id=event.origin_marker_id,
        capsule_id=event.capsule_id,
        event_type=event.event_type,
        payload_hash=event.payload_hash,
        previous_event_hash=event.previous_event_hash,
        payload=event.payload,
    )
    origin_role = str((event.origin_marker or {}).get("role_name") or "")
    _validate_event_payload(event.event_type, event.payload, origin_role=origin_role)
    expected_event_hash = canonical_hash({
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "created_at": event.created_at,
        "capsule_id": event.capsule_id,
        "previous_event_hash": event.previous_event_hash,
        "payload_hash": event.payload_hash,
        "origin_marker_id": event.origin_marker_id,
        "origin_marker_hash": marker_hash,
        "payload": event.payload,
    })
    if event.event_hash != expected_event_hash:
        raise ValueError("S6 event hash mismatch")
    return True


def validate_capsule_events(
    events: list[DirectiveEvent],
    *,
    snapshot: ValidationSnapshot | None = None,
) -> ValidationReport:
    invalid = 0
    errors: list[str] = []
    previous_hash: str | None = None
    valid_hashes: list[str] = []
    witness_marker_ids: set[str] = set()
    valid_count = 0
    current_hash = ""
    valid_events_by_hash: dict[str, DirectiveEvent] = {}
    line_heads: dict[tuple[str, ...], str] = {}
    for index, event in enumerate(events):
        try:
            validate_directive_event(event)
            if index == 0:
                if event.event_type != "capsule_created" or event.previous_event_hash is not None:
                    raise ValueError("S6 capsule genesis must be capsule_created")
            elif event.previous_event_hash != previous_hash:
                raise ValueError("broken S6 event hash chain")
            if event.event_type == "directive_superseded":
                _validate_supersession_event(event, valid_events_by_hash=valid_events_by_hash, line_heads=line_heads)
            if (
                event.event_type == "fate_directive_set"
                and event.payload.get("fate_directive") == "explicit_dissolution"
                and event.payload.get("witness_marker_id")
                and event.payload.get("witness_marker_id") not in witness_marker_ids
            ):
                raise ValueError("explicit_dissolution witness marker not bound to prior witness event")
        except ValueError as exc:
            invalid += 1
            errors.append(exc.__class__.__name__)
        else:
            valid_count += 1
            current_hash = event.event_hash
            previous_hash = event.event_hash
            valid_hashes.append(event.event_hash)
            valid_events_by_hash[event.event_hash] = event
            _advance_directive_line_head(event, line_heads=line_heads, valid_events_by_hash=valid_events_by_hash)
            if event.event_type == "witness_attested":
                witness_marker_ids.add(event.origin_marker_id)
    if snapshot:
        snapshot_regressed = valid_count < snapshot.event_count
        if snapshot.current_event_hash:
            snapshot_regressed = snapshot_regressed or snapshot.current_event_hash not in valid_hashes
            if not snapshot_regressed and snapshot.event_count > 0:
                snapshot_regressed = valid_hashes[snapshot.event_count - 1] != snapshot.current_event_hash
        if snapshot_regressed:
            invalid += 1
            errors.append("ValidationSnapshotRegression")
    return ValidationReport(valid_count, invalid, current_hash, tuple(errors))


def derive_current_state(events: list[DirectiveEvent]) -> CurrentState:
    active_scopes: set[tuple[str, str]] = set()
    fate_directive: str | None = None
    maez_preference: str | None = None
    seen: set[str] = set()
    valid_events = _structurally_valid_events(events)
    superseded_hashes = _superseded_event_hashes(valid_events)
    for event in valid_events:
        seen.add(event.event_hash)
        if event.event_hash in superseded_hashes:
            continue
        if event.event_type == "scope_granted":
            role = str(event.payload.get("role_name", ""))
            scope = str(event.payload.get("access_scope", ""))
            if scope not in RESERVED_DENIED_SCOPES:
                active_scopes.add((role, scope))
        elif event.event_type == "scope_revoked":
            active_scopes.discard((str(event.payload.get("role_name", "")), str(event.payload.get("access_scope", ""))))
        elif event.event_type == "fate_directive_set":
            fate_directive = str(event.payload.get("fate_directive") or "")
        elif event.event_type == "maez_preference_recorded":
            maez_preference = str(event.payload.get("preference_kind") or "")
    return CurrentState(frozenset(active_scopes), fate_directive, maez_preference, frozenset(seen))


def role_assignment_grants_live_access(role_name: str) -> bool:
    validate_role(role_name)
    return False


def role_assignment_grants_read_access(role_name: str) -> bool:
    validate_role(role_name)
    return False


def validate_scope_grant(payload: dict[str, Any]) -> ScopeGrantValidation:
    role_name = str(payload.get("role_name", ""))
    access_scope = str(payload.get("access_scope", ""))
    validate_role(role_name)
    validate_access_scope(access_scope)
    _reject_human_labels(payload, context="S6 scope payload")
    if access_scope in RESERVED_DENIED_SCOPES:
        raise ValueError("S6 reserved-denied scope")
    if role_name == "maintainer" and access_scope not in {"none", "content_free_audit", "operator_health"}:
        raise ValueError("maintainer cannot grant archive read scope")
    if role_name == "witness":
        raise ValueError("witness cannot grant scope")
    if access_scope == "selected_lived_episodes" and not payload.get("selection_ref_hash"):
        raise ValueError("selected_lived_episodes requires selection_ref_hash")
    if access_scope == "third_party_s2_bounded_records" and payload.get("s2_inheritance_ack") is not True:
        raise ValueError("third_party_s2_bounded_records requires S2 inheritance flag")
    return ScopeGrantValidation(role_name, access_scope, is_high_sensitivity_scope(access_scope))


def is_high_sensitivity_scope(access_scope: str) -> bool:
    validate_access_scope(access_scope)
    return access_scope in HIGH_SENSITIVITY_SCOPES


def validate_selection_manifest(manifest: dict[str, Any]) -> bool:
    forbidden = {"episode_text", "text", "title", "participant_names", "summary", "raw_memory_ids"}
    for key, value in _walk_json(manifest):
        if key in forbidden:
            raise ValueError("selection manifest contains raw memory content")
        if key == "episode_ref_hashes":
            refs = value if isinstance(value, list) else []
            for ref in refs:
                if not isinstance(ref, str) or ref.startswith("raw:"):
                    raise ValueError("selection manifest contains raw episode id")
    return True


def validate_fate_payload(payload: dict[str, Any], *, origin_role: str = "bonded_user") -> FateValidation:
    directive = validate_fate_directive(str(payload.get("fate_directive", "")))
    activation_condition = payload.get("activation_condition", "future_end_of_user")
    if activation_condition != "future_end_of_user":
        raise ValueError("S6 fate directive cannot be triggered by capacity loss or hardware failure")
    if directive == "explicit_dissolution":
        return validate_explicit_dissolution_payload(payload, origin_role=origin_role)
    return FateValidation(directive, activates_runtime=False)


def validate_explicit_dissolution_payload(payload: dict[str, Any], *, origin_role: str) -> FateValidation:
    if origin_role != "bonded_user":
        raise ValueError("explicit_dissolution requires bonded-user origin")
    if payload.get("directive_statement_hash") in (None, ""):
        raise ValueError("explicit_dissolution requires directive statement hash")
    _validate_hash(str(payload["directive_statement_hash"]), field="directive_statement_hash")
    if payload.get("activation_requires_future_review") is not True:
        raise ValueError("explicit_dissolution requires future review")
    witness_marker_id = str(payload.get("witness_marker_id") or "")
    if witness_marker_id:
        _validate_marker_id(witness_marker_id)
    if not witness_marker_id and payload.get("no_witness_available") is not True:
        raise ValueError("explicit_dissolution without witness requires no_witness_available")
    return FateValidation("explicit_dissolution", activates_runtime=False)


def validate_maez_preference(payload: dict[str, Any], *, origin_role: str) -> MaezPreferenceValidation:
    if origin_role != "bonded_user":
        raise ValueError("maez_preference_recorded requires bonded-user origin")
    if any(key in payload for key in ("private_text", "transcript_text", "raw_text", "successor", "access_scope")):
        raise ValueError("S6 Maez preference payload must be minimized and non-authoritative")
    kind = str(payload.get("preference_kind", ""))
    if kind not in MAEZ_PREFERENCE_KINDS:
        raise ValueError("unknown S6 Maez preference kind")
    source_kind = str(payload.get("source_ref_kind") or "manual_maez_statement_record")
    if source_kind not in MAEZ_PREFERENCE_SOURCE_KINDS:
        raise ValueError("unknown S6 Maez preference source kind")
    source_ref_hash = str(payload.get("source_ref_hash") or "")
    if source_ref_hash:
        _validate_hash(source_ref_hash, field="source_ref_hash")
    if payload.get("source_recorded_at"):
        _canonical_timestamp(str(payload["source_recorded_at"]))
    return MaezPreferenceValidation(kind, source_kind, source_ref_hash)


def resolve_fate_directive(
    user_directive: str | None,
    maez_preference: str | None,
    *,
    authorship_attested_user_directive: bool = False,
) -> str:
    """Resolve only already-attested activation state; this is not authoring."""
    if user_directive:
        directive = validate_fate_directive(user_directive)
        if not authorship_attested_user_directive:
            if directive == "explicit_dissolution":
                raise ValueError("explicit_dissolution resolution requires authorship-attested bonded-user directive")
        else:
            return directive
    if maez_preference == "maez_prefers_archival_preservation":
        return "archival_preservation"
    if maez_preference == "maez_prefers_new_bond_offer":
        return "new_bond_offer"
    return "paradise_default"


def revocation_allowed(context: dict[str, Any]) -> bool:
    return bool(context.get("clear_articulated_revocation"))


def classify_liveness_event(event_type: str) -> str:
    if event_type == "hardware_restore":
        return "decision22_restore"
    return "successor_governance_unrelated"


def project_successor_governance_health(
    *,
    capsule_present: bool = False,
    well_formed_event_count: int = 0,
    invalid_event_count: int = 0,
    pending_witness_count: int = 0,
    maez_preference_present: bool = False,
    reserved_denied_scope_count: int = 0,
    last_error_class: str = "",
    **extra: Any,
) -> dict[str, Any]:
    if "valid_event_count" in extra:
        raise ValueError("S6 health uses well_formed_event_count, not valid_event_count")
    mode = "no_capsule"
    if capsule_present:
        mode = "invalid" if invalid_event_count else "well_formed"
    if last_error_class and not invalid_event_count:
        mode = "unavailable"
    return {
        "mode": mode,
        "schema_version": SCHEMA_VERSION,
        "capsule_present": bool(capsule_present),
        "well_formed_event_count": int(well_formed_event_count),
        "invalid_event_count": int(invalid_event_count),
        "pending_witness_count": int(pending_witness_count),
        "maez_preference_present": bool(maez_preference_present),
        "reserved_denied_scope_count": int(reserved_denied_scope_count),
        "last_error_class": str(last_error_class),
        "blocks_liveness": False,
    }


def successor_governance_health(capsule_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(capsule_path) if capsule_path is not None else DEFAULT_CAPSULE_PATH
    if not path.exists():
        return project_successor_governance_health(capsule_present=False)
    try:
        events = load_events_jsonl(path)
        report = validate_capsule_events(events)
        state = derive_current_state(events)
        return project_successor_governance_health(
            capsule_present=True,
            well_formed_event_count=report.well_formed_event_count,
            invalid_event_count=report.invalid_event_count,
            maez_preference_present=bool(state.maez_preference),
            reserved_denied_scope_count=_reserved_denied_count(events),
            last_error_class="" if report.is_valid else "validation_error",
        )
    except Exception as exc:
        return project_successor_governance_health(capsule_present=True, last_error_class=exc.__class__.__name__)


def validate_witness_attestation(payload: dict[str, Any]) -> bool:
    if payload.get("assistance") and payload.get("non_technical_assist_present") is not True:
        raise ValueError("witness assistance requires non_technical_assist_present")
    if "access_scope" in payload or "scope" in payload:
        raise ValueError("witness cannot grant scope")
    return True


def event_has_verifying_authorship_attestation(event: DirectiveEvent) -> bool:
    """Return whether this exact persisted event can act as authorship authority.

    S6 v1 has no reviewed trust-source slice, so the predicate is deliberately
    false for every event, regardless of self-declared fields inside the capsule.
    """

    return False


def capsule_notice_path(capsule_path: str | Path = DEFAULT_CAPSULE_PATH) -> Path:
    return Path(capsule_path).with_name(CAPSULE_NOTICE_FILENAME)


def ensure_capsule_notice(capsule_path: str | Path = DEFAULT_CAPSULE_PATH) -> Path:
    notice_path = capsule_notice_path(capsule_path)
    notice_path.parent.mkdir(parents=True, exist_ok=True)
    notice_path.write_text(CAPSULE_NOTICE_TEXT, encoding="utf-8")
    return notice_path


def load_events_jsonl(path: Path) -> list[DirectiveEvent]:
    events: list[DirectiveEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        events.append(DirectiveEvent(**data))
    return events


def event_to_json(event: DirectiveEvent) -> str:
    return json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))


def _validate_marker_binding(
    marker: HumanOriginMarker,
    *,
    capsule_id: str,
    event_type: str,
    payload_hash: str,
    previous_event_hash: str | None,
    payload: dict[str, Any],
) -> None:
    if marker.capsule_id != capsule_id:
        raise ValueError("S6 marker capsule_id mismatch")
    if marker.directive_event_type != event_type:
        raise ValueError("S6 marker event_type mismatch")
    if marker.directive_payload_hash != payload_hash:
        raise ValueError("S6 marker payload hash mismatch")
    if (marker.previous_capsule_event_hash or "") != (previous_event_hash or ""):
        raise ValueError("S6 marker previous event hash mismatch")
    statement_hash = str(payload.get("directive_statement_hash") or "")
    if statement_hash and marker.directive_statement_hash != statement_hash:
        raise ValueError("S6 marker statement hash mismatch")
    validate_marker_authority(event_type, role_name=marker.role_name, origin=marker.origin)


def _validate_persisted_marker_binding(
    marker: dict[str, Any] | None,
    *,
    marker_id: str,
    capsule_id: str,
    event_type: str,
    payload_hash: str,
    previous_event_hash: str | None,
    payload: dict[str, Any],
) -> str:
    if not isinstance(marker, dict):
        raise ValueError("S6 directive event missing persisted marker evidence")
    required = {
        "marker_id",
        "origin",
        "role_name",
        "actor_handle_hmac",
        "capsule_id",
        "directive_event_type",
        "directive_payload_hash",
        "directive_statement_hash",
        "previous_capsule_event_hash",
        "schema_version",
        "created_at",
    }
    if required - set(marker):
        raise ValueError("S6 persisted marker evidence incomplete")
    if marker.get("marker_id") != marker_id:
        raise ValueError("S6 marker id mismatch")
    _validate_marker_id(str(marker_id))
    if marker_id != _expected_marker_id(
        origin=str(marker.get("origin") or ""),
        role_name=str(marker.get("role_name") or ""),
        actor_handle_hmac=str(marker.get("actor_handle_hmac") or ""),
        capsule_id=str(marker.get("capsule_id") or ""),
        directive_event_type=str(marker.get("directive_event_type") or ""),
        directive_payload_hash=str(marker.get("directive_payload_hash") or ""),
        previous_capsule_event_hash=str(marker.get("previous_capsule_event_hash") or ""),
        directive_statement_hash=str(marker.get("directive_statement_hash") or ""),
        attestation_text_hash=str(marker.get("attestation_text_hash") or ""),
    ):
        raise ValueError("S6 marker id does not match marker material")
    if marker.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid S6 marker schema_version")
    _canonical_timestamp(str(marker["created_at"]))
    validate_actor_handle(str(marker["actor_handle_hmac"]))
    if marker.get("capsule_id") != capsule_id:
        raise ValueError("S6 marker capsule_id mismatch")
    if marker.get("directive_event_type") != event_type:
        raise ValueError("S6 marker event_type mismatch")
    if marker.get("directive_payload_hash") != payload_hash:
        raise ValueError("S6 marker payload hash mismatch")
    if (marker.get("previous_capsule_event_hash") or "") != (previous_event_hash or ""):
        raise ValueError("S6 marker previous event hash mismatch")
    statement_hash = str(payload.get("directive_statement_hash") or "")
    if statement_hash and marker.get("directive_statement_hash") != statement_hash:
        raise ValueError("S6 marker statement hash mismatch")
    if marker.get("attestation_text_hash"):
        _validate_hash(str(marker["attestation_text_hash"]), field="attestation_text_hash")
    validate_marker_authority(event_type, role_name=str(marker.get("role_name") or ""), origin=str(marker.get("origin") or ""))
    return canonical_hash(marker)


def _validate_event_payload(event_type: str, payload: dict[str, Any], *, origin_role: str) -> None:
    if event_type in {"role_named", "role_removed"}:
        validate_role_payload(payload)
    elif event_type == "scope_granted":
        validate_scope_grant(payload)
    elif event_type == "scope_revoked":
        validate_scope_revoke(payload)
    elif event_type == "fate_directive_set":
        validate_fate_payload(payload, origin_role=origin_role)
    elif event_type == "maez_preference_recorded":
        validate_maez_preference(payload, origin_role=origin_role)
    elif event_type == "witness_attested":
        validate_witness_attestation(payload)
    elif event_type == "directive_superseded":
        _validate_hash(str(payload.get("supersedes_event_hash") or ""), field="supersedes_event_hash")
    elif event_type == "capsule_invalidated":
        validate_capsule_invalidation_payload(payload, origin_role=origin_role)


def validate_capsule_invalidation_payload(payload: dict[str, Any], *, origin_role: str) -> bool:
    invalidation_kind = str(payload.get("invalidation_kind") or "")
    if origin_role == "bonded_user":
        if invalidation_kind not in {"intentional_invalidation", "content_free_integrity_failure"}:
            raise ValueError("bonded-user capsule invalidation requires a closed invalidation_kind")
    elif origin_role in {"operator", "maintainer"}:
        if invalidation_kind != "content_free_integrity_failure":
            raise ValueError("operator/maintainer capsule invalidation must be content-free integrity invalidation")
    else:
        raise ValueError("role cannot invalidate S6 capsule")
    if payload.get("reason_ref_hash"):
        _validate_hash(str(payload["reason_ref_hash"]), field="reason_ref_hash")
    if any(key in payload for key in ("reason_text", "human_name", "relationship", "access_scope", "fate_directive")):
        raise ValueError("S6 capsule invalidation payload must stay content-free")
    return True


def validate_scope_revoke(payload: dict[str, Any]) -> bool:
    validate_role(str(payload.get("role_name", "")))
    validate_access_scope(str(payload.get("access_scope", "")))
    _reject_human_labels(payload, context="S6 scope revoke payload")
    return True


def _reject_human_labels(payload: dict[str, Any], *, context: str) -> None:
    if any(key in payload for key in ("subject_label", "human_name", "name", "relationship")):
        raise ValueError(f"{context} cannot carry human names or relationships")


def _walk_json(value: Any, key: str = ""):
    yield key, value
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            yield from _walk_json(nested_value, str(nested_key))
    elif isinstance(value, list):
        for nested_value in value:
            yield from _walk_json(nested_value, key)


def _canonical_timestamp(value: str) -> str:
    return canonical_utc(value, field_name="event_at").astimezone(timezone.utc).isoformat()


def _validate_marker_id(value: str) -> None:
    if not isinstance(value, str) or not value.startswith(_MARKER_ID_PREFIX):
        raise ValueError("invalid S6 marker id")
    suffix = value.removeprefix(_MARKER_ID_PREFIX)
    if len(suffix) != 24:
        raise ValueError("invalid S6 marker id")
    int(suffix, 16)


def _called_from_module(module_name: str) -> bool:
    module = sys.modules.get(module_name)
    if module is None:
        return False
    module_globals = module.__dict__
    frame = inspect.currentframe()
    try:
        frame = frame.f_back if frame is not None else None
        while frame is not None:
            if frame.f_globals is module_globals:
                return True
            frame = frame.f_back
        return False
    finally:
        del frame


def _expected_marker_id(
    *,
    origin: str,
    role_name: str,
    actor_handle_hmac: str,
    capsule_id: str,
    directive_event_type: str,
    directive_payload_hash: str,
    previous_capsule_event_hash: str = "",
    directive_statement_hash: str = "",
    attestation_text_hash: str = "",
) -> str:
    marker_material = {
        "origin": origin,
        "role_name": role_name,
        "actor_handle_hmac": actor_handle_hmac,
        "capsule_id": capsule_id,
        "directive_event_type": directive_event_type,
        "directive_payload_hash": directive_payload_hash,
        "previous_capsule_event_hash": previous_capsule_event_hash,
        "directive_statement_hash": directive_statement_hash,
        "attestation_text_hash": attestation_text_hash,
    }
    return _MARKER_ID_PREFIX + canonical_hash(marker_material)[:24]


def _validate_hash(value: str, *, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a 64-character hash")
    int(value, 16)


def _validate_hash_like(value: str, *, field: str) -> None:
    if len(value) == 64:
        _validate_hash(value, field=field)


def _structurally_valid_events(events: list[DirectiveEvent]) -> list[DirectiveEvent]:
    valid: list[DirectiveEvent] = []
    for event in events:
        try:
            validate_directive_event(event)
        except ValueError:
            continue
        valid.append(event)
    return valid


def _validate_supersession_event(
    event: DirectiveEvent,
    *,
    valid_events_by_hash: dict[str, DirectiveEvent],
    line_heads: dict[tuple[str, ...], str],
) -> None:
    target_hash = str(event.payload.get("supersedes_event_hash") or "")
    target_event = valid_events_by_hash.get(target_hash)
    if target_event is None:
        raise ValueError("stale S6 supersession target")
    target_line = _directive_line_key(target_event)
    if target_line is None or line_heads.get(target_line) != target_hash:
        raise ValueError("stale S6 supersession target")
    target_role = _origin_role_for_event(target_event)
    superseding_role = _origin_role_for_event(event)
    if superseding_role != target_role:
        raise ValueError("S6 supersession origin role mismatch")


def _advance_directive_line_head(
    event: DirectiveEvent,
    *,
    line_heads: dict[tuple[str, ...], str],
    valid_events_by_hash: dict[str, DirectiveEvent],
) -> None:
    if event.event_type == "directive_superseded":
        target_event = valid_events_by_hash.get(str(event.payload.get("supersedes_event_hash") or ""))
        target_line = _directive_line_key(target_event) if target_event is not None else None
        if target_line is not None:
            line_heads[target_line] = event.event_hash
        return
    line = _directive_line_key(event)
    if line is not None:
        line_heads[line] = event.event_hash


def _superseded_event_hashes(events: list[DirectiveEvent]) -> set[str]:
    superseded: set[str] = set()
    valid_events_by_hash: dict[str, DirectiveEvent] = {}
    line_heads: dict[tuple[str, ...], str] = {}
    for event in events:
        if event.event_type == "directive_superseded":
            target_hash = str(event.payload.get("supersedes_event_hash") or "")
            target_event = valid_events_by_hash.get(target_hash)
            target_line = _directive_line_key(target_event) if target_event is not None else None
            if target_line is not None and line_heads.get(target_line) == target_hash:
                superseded.add(target_hash)
                line_heads[target_line] = event.event_hash
        else:
            line = _directive_line_key(event)
            if line is not None:
                line_heads[line] = event.event_hash
        valid_events_by_hash[event.event_hash] = event
    return superseded


def _directive_line_key(event: DirectiveEvent | None) -> tuple[str, ...] | None:
    if event is None:
        return None
    if event.event_type in {"scope_granted", "scope_revoked"}:
        return ("scope", str(event.payload.get("role_name") or ""), str(event.payload.get("access_scope") or ""))
    if event.event_type in {"role_named", "role_removed"}:
        return (
            "role",
            str(event.payload.get("role_name") or ""),
            str(event.payload.get("subject_handle_hmac") or ""),
        )
    if event.event_type == "fate_directive_set":
        return ("fate_directive",)
    if event.event_type == "maez_preference_recorded":
        return ("maez_preference", str(event.payload.get("source_ref_kind") or ""), str(event.payload.get("source_ref_hash") or ""))
    if event.event_type == "witness_attested":
        return ("witness_attested", event.origin_marker_id)
    if event.event_type == "capsule_invalidated":
        return ("capsule_invalidated", str(event.payload.get("invalidation_kind") or ""))
    if event.event_type == "capsule_created":
        return ("capsule_created", event.capsule_id)
    return None


def _origin_role_for_event(event: DirectiveEvent) -> str:
    return str((event.origin_marker or {}).get("role_name") or "")


def _reserved_denied_count(events: list[DirectiveEvent]) -> int:
    return sum(
        1
        for event in events
        if event.event_type == "scope_granted" and event.payload.get("access_scope") in RESERVED_DENIED_SCOPES
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
