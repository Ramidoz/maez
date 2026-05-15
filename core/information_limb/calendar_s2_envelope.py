"""Calendar v1 canonical S2 envelope guard.

This module is deliberately offline: it performs no OAuth, no Google calls, and
no storage writes. Its job is to keep the first information-limb implementation
from becoming a second interpretation of S2.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SOURCE_KIND = "calendar.event"
SCHEMA_VERSION = "calendar.s2.v1"

CANONICAL_S2_REQUIRED_FIELDS = frozenset(
    {
        "ingest_record_id",
        "schema_version",
        "source_kind",
        "source_handle_human",
        "source_instance_id",
        "source_handle_telemetry",
        "observed_at",
        "received_at",
        "expires_at",
        "sequence",
        "confidence",
        "record_state",
        "retention_class",
        "granted_flow_ids",
        "facts",
        "external_event_id",
        "external_event_id_hash",
        "source_revision",
        "source_revision_hash",
        "decision2_consent_tier",
        "consent_posture",
        "third_party_posture",
        "requested_flow_ids",
        "flow_policy_version",
        "promotion_state",
        "promotion_eligibility_reason",
        "promotion_eligibility_provenance_handle",
        "promotion_record_id",
        "redaction_state",
        "fetch_batch_id",
        "connector_version",
        "raw_field_policy_version",
        "backfill_origin",
        "provenance",
    }
)

_FORBIDDEN_CALENDAR_ALIASES = frozenset(
    {
        "consent_tier",
        "requested_flows",
        "granted_flows",
        "calendar_id",
        "event_id",
        "revision",
    }
)

_CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "decision2_consent_tier",
        "third_party_posture",
        "granted_flow_ids",
        "promotion_state",
        "promotion_eligibility_reason",
        "promotion_eligibility_provenance_handle",
        "promotion_record_id",
    }
)

_ALLOWED_CONFIDENCE = frozenset(
    {
        "provider_confirmed",
        "provider_partial",
        "redacted_safe",
        "stale_below_max",
        "unavailable",
    }
)


class CalendarS2EnvelopeError(ValueError):
    """Raised when a Calendar record would violate the canonical S2 envelope."""


def validate_connector_calendar_payload(payload: Mapping[str, Any]) -> bool:
    """Reject connector records that try to stamp S2 authority fields."""

    forbidden = sorted(set(payload) & _CONNECTOR_FORBIDDEN_AUTHORITY_FIELDS)
    if forbidden:
        raise CalendarS2EnvelopeError(f"connector authority fields are not accepted: {forbidden}")
    return True


def validate_calendar_s2_envelope(envelope: Mapping[str, Any]) -> bool:
    """Validate the canonical Calendar v1 S2 envelope shape."""

    aliases = sorted(set(envelope) & _FORBIDDEN_CALENDAR_ALIASES)
    if aliases:
        raise CalendarS2EnvelopeError(f"Calendar envelope alias fields rejected: {aliases}")

    missing = sorted(CANONICAL_S2_REQUIRED_FIELDS - set(envelope))
    if missing:
        raise CalendarS2EnvelopeError(f"Calendar S2 envelope missing fields: {missing}")

    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise CalendarS2EnvelopeError("Calendar S2 envelope schema_version mismatch")
    if envelope.get("source_kind") != SOURCE_KIND:
        raise CalendarS2EnvelopeError("Calendar S2 envelope source_kind mismatch")
    if envelope.get("confidence") not in _ALLOWED_CONFIDENCE:
        raise CalendarS2EnvelopeError("Calendar S2 envelope confidence is not allowed")
    if not isinstance(envelope.get("facts"), Mapping):
        raise CalendarS2EnvelopeError("Calendar S2 envelope facts must be an object")
    if not isinstance(envelope.get("requested_flow_ids"), list):
        raise CalendarS2EnvelopeError("Calendar S2 envelope requested_flow_ids must be a list")
    if not isinstance(envelope.get("granted_flow_ids"), list):
        raise CalendarS2EnvelopeError("Calendar S2 envelope granted_flow_ids must be a list")
    if not isinstance(envelope.get("provenance"), Mapping):
        raise CalendarS2EnvelopeError("Calendar S2 envelope provenance must be an object")
    return True
