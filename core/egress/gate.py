from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from core.safety.cloud_redactor import redact_for_cloud

Decision = Literal["allow", "redact", "block"]

RESERVED_DENIED_RAW = {
    "soul",
    "private_thoughts",
    "inner_residue",
    "maez_internal_reflection",
    "credential_material",
    "crisis_held_content",
}

MINIMIZABLE_PRIVATE_CONTEXT = {
    "memory",
    "lived_store",
    "owner_message_context",
    "third_party_private_context",
    "owner_screen_context",
}

NON_PRIVATE = {
    "public_fact",
    "weather_data",
    "system_bounded_query",
    "tool_result_public",
}

UNTRUSTED_EXTERNAL_OUTPUT = {
    "model_output",
}

INTENTIONAL_OUTBOUND = {
    "owner_authored_for_destination",
    "maez_authored_local_bonded_surface",
    "maez_authored_owner_third_party_transport",
    "maez_authored_public_third_party_transport",
}

# Personal-account-derived data (Reddit/Gmail/Spotify/calendar/saved posts).
# Categorical cloud-egress block by default — the outbound mirror of the
# inbound external_llm_tainted taint. Slice 1 of the Personal Data Limb Runtime.
OWNER_ACCOUNT_CONTEXT = {
    "owner_account_context",
}

KNOWN_ORIGINS = (
    RESERVED_DENIED_RAW
    | MINIMIZABLE_PRIVATE_CONTEXT
    | NON_PRIVATE
    | UNTRUSTED_EXTERNAL_OUTPUT
    | INTENTIONAL_OUTBOUND
    | OWNER_ACCOUNT_CONTEXT
    | {"unclassified"}
)


def load_or_create_telemetry_key(path: Path | None = None) -> bytes:
    env_value = os.environ.get("MAEZ_EGRESS_TELEMETRY_KEY")
    if env_value:
        return env_value.encode("utf-8")
    if path is None:
        try:
            from core.infra import paths as _paths

            path = _paths.memory_dir() / "egress_telemetry.key"
        except Exception:
            path = (
                Path(__file__).resolve().parents[2]
                / "memory"
                / "egress_telemetry.key"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes()
    key = secrets.token_bytes(32)
    path.write_bytes(key)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


@dataclass(frozen=True)
class EgressSegment:
    text: str
    origin_class: str
    source_ref: str
    redaction_allowed: bool
    asserted_origin_class: str | None = None


@dataclass(frozen=True)
class EgressRequest:
    call_class: str
    destination: str
    segments: list[EgressSegment]
    caller: str
    request_id: str


@dataclass(frozen=True)
class EgressDecision:
    decision: Decision
    sanitized_segments: list[str] = field(default_factory=list)
    reason_codes: tuple[str, ...] = ()
    call_class: str = "unclassified"
    destination: str = "unknown"
    caller: str = "unknown"
    request_id: str = "unknown"
    origin_classes: tuple[str, ...] = ()
    original_char_count: int = 0

    def sanitized_text(self) -> str:
        return "".join(self.sanitized_segments)


def _block(
    *,
    reason_codes: tuple[str, ...],
    request: EgressRequest | None = None,
    origin_classes: tuple[str, ...] = (),
    original_char_count: int = 0,
) -> EgressDecision:
    return EgressDecision(
        decision="block",
        reason_codes=reason_codes,
        call_class=(request.call_class if request else "unclassified"),
        destination=(request.destination if request else "unknown"),
        caller=(request.caller if request else "unknown"),
        request_id=(request.request_id if request else "unknown"),
        origin_classes=origin_classes,
        original_char_count=original_char_count,
    )


def decide_egress(payload: EgressRequest | object) -> EgressDecision:
    if not isinstance(payload, EgressRequest):
        return _block(reason_codes=("unclassified", "raw_payload"))

    request = payload
    if request.call_class == "owner_third_party_transport_send":
        return _decide_owner_third_party_transport(request)
    if request.call_class == "public_third_party_transport_send":
        return _decide_public_third_party_transport(request)
    if request.call_class != "cloud_model_inference":
        return _block(reason_codes=("unknown_call_class",), request=request)

    return _decide_cloud_model_inference(request)


def _common_request_shape(
    request: EgressRequest,
) -> tuple[tuple[str, ...], int] | EgressDecision:
    if not request.segments:
        return _block(reason_codes=("unclassified",), request=request)

    origins = tuple(segment.origin_class for segment in request.segments)
    original_chars = sum(len(segment.text or "") for segment in request.segments)
    for segment in request.segments:
        origin = segment.origin_class
        asserted = segment.asserted_origin_class
        if origin not in KNOWN_ORIGINS:
            return _block(
                reason_codes=("unclassified",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin == "unclassified":
            return _block(
                reason_codes=("unclassified",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if asserted is not None and asserted != origin:
            return _block(
                reason_codes=("origin_downgrade",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
    return origins, original_chars


def _decide_cloud_model_inference(request: EgressRequest) -> EgressDecision:
    shape = _common_request_shape(request)
    if isinstance(shape, EgressDecision):
        return shape
    origins, original_chars = shape

    sanitized: list[str] = []
    reasons: list[str] = []
    saw_minimizable_private = False
    saw_untrusted_external = False

    for segment in request.segments:
        origin = segment.origin_class
        if origin in OWNER_ACCOUNT_CONTEXT:
            # Personal-account-derived data does not leave the local body to a
            # cloud model by default — categorical, ignores redaction_allowed.
            # The lock; producer-side tagging with this class is a later slice.
            return _block(
                reason_codes=("owner_account_context_blocked_default",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin in RESERVED_DENIED_RAW:
            return _block(
                reason_codes=("reserved_denied_raw",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin in MINIMIZABLE_PRIVATE_CONTEXT or origin in UNTRUSTED_EXTERNAL_OUTPUT:
            if not segment.redaction_allowed:
                return _block(
                    reason_codes=("private_context_redaction_not_allowed",),
                    request=request,
                    origin_classes=origins,
                    original_char_count=original_chars,
                )
            if origin in UNTRUSTED_EXTERNAL_OUTPUT:
                saw_untrusted_external = True
            else:
                saw_minimizable_private = True
            redacted = redact_for_cloud(segment.text)
            sanitized.append(redacted.text)
            continue
        if origin in NON_PRIVATE:
            sanitized.append(segment.text)
            continue
        return _block(
            reason_codes=("origin_not_permitted_for_cloud",),
            request=request,
            origin_classes=origins,
            original_char_count=original_chars,
        )

    if saw_minimizable_private or saw_untrusted_external:
        if saw_minimizable_private:
            reasons.append("minimized_private_context")
        if saw_untrusted_external:
            reasons.append("minimized_untrusted_model_output")
        decision: Decision = "redact"
    else:
        reasons.append("non_private_allowed")
        decision = "allow"

    return EgressDecision(
        decision=decision,
        sanitized_segments=sanitized,
        reason_codes=tuple(reasons),
        call_class=request.call_class,
        destination=request.destination,
        caller=request.caller,
        request_id=request.request_id,
        origin_classes=origins,
        original_char_count=original_chars,
    )


def _decide_owner_third_party_transport(request: EgressRequest) -> EgressDecision:
    shape = _common_request_shape(request)
    if isinstance(shape, EgressDecision):
        return shape
    origins, original_chars = shape
    sanitized: list[str] = []
    reasons: list[str] = []
    saw_minimized = False

    for segment in request.segments:
        origin = segment.origin_class
        if origin in RESERVED_DENIED_RAW:
            return _block(
                reason_codes=("reserved_denied_raw",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin == "maez_authored_public_third_party_transport":
            return _block(
                reason_codes=("audience_origin_mismatch",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin == "third_party_private_context":
            if not segment.redaction_allowed:
                return _block(
                    reason_codes=("private_context_redaction_not_allowed",),
                    request=request,
                    origin_classes=origins,
                    original_char_count=original_chars,
                )
            sanitized.append(redact_for_cloud(segment.text).text)
            saw_minimized = True
            continue
        if (
            origin in NON_PRIVATE
            or origin in {"memory", "lived_store", "owner_message_context"}
            or origin == "maez_authored_owner_third_party_transport"
        ):
            sanitized.append(segment.text)
            continue
        return _block(
            reason_codes=("origin_not_permitted_for_owner_transport",),
            request=request,
            origin_classes=origins,
            original_char_count=original_chars,
        )

    if saw_minimized:
        decision: Decision = "redact"
        reasons.append("minimized_private_context")
    else:
        decision = "allow"
        reasons.append("owner_transport_allowed")

    return EgressDecision(
        decision=decision,
        sanitized_segments=sanitized,
        reason_codes=tuple(reasons),
        call_class=request.call_class,
        destination=request.destination,
        caller=request.caller,
        request_id=request.request_id,
        origin_classes=origins,
        original_char_count=original_chars,
    )


def _decide_public_third_party_transport(request: EgressRequest) -> EgressDecision:
    shape = _common_request_shape(request)
    if isinstance(shape, EgressDecision):
        return shape
    origins, original_chars = shape
    sanitized: list[str] = []

    for segment in request.segments:
        origin = segment.origin_class
        if origin in RESERVED_DENIED_RAW:
            return _block(
                reason_codes=("reserved_denied_raw",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if (
            origin == "maez_authored_owner_third_party_transport"
            or origin in MINIMIZABLE_PRIVATE_CONTEXT
        ):
            return _block(
                reason_codes=("public_recipient_owner_context_blocked",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin in NON_PRIVATE or origin == "maez_authored_public_third_party_transport":
            sanitized.append(segment.text)
            continue
        return _block(
            reason_codes=("origin_not_permitted_for_public_transport",),
            request=request,
            origin_classes=origins,
            original_char_count=original_chars,
        )

    return EgressDecision(
        decision="allow",
        sanitized_segments=sanitized,
        reason_codes=("public_transport_allowed",),
        call_class=request.call_class,
        destination=request.destination,
        caller=request.caller,
        request_id=request.request_id,
        origin_classes=origins,
        original_char_count=original_chars,
    )


def decision_to_telemetry(
    decision: EgressDecision,
    *,
    key: bytes,
) -> dict:
    digest = hmac.new(
        key,
        decision.sanitized_text().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "schema_version": "maez-egress-telemetry-v1",
        "call_class": decision.call_class,
        "destination": decision.destination,
        "caller": decision.caller,
        "request_id": decision.request_id,
        "origin_classes": list(decision.origin_classes),
        "decision": decision.decision,
        "reason_codes": list(decision.reason_codes),
        "content_digest": f"hmac-sha256:{digest}",
        "original_char_count": decision.original_char_count,
        "sanitized_char_count": len(decision.sanitized_text()),
    }
