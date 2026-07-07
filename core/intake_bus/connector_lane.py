"""Connector lane for minimized owner-account facts.

This mirrors ``world_observation_lane``: build one bounded ``IntakeFact`` and
hand it to the shared intake-bus doorway. Raw iPhone signal JSONL remains the
prunable signal store; only state transitions and bounded owner facts enter
body memory.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any

from core.intake_bus.admit import admit
from core.intake_bus.contract import IntakeFact, PromotionPosture
from memory.memory_manager import ProvenanceSource

CONNECTOR_EGRESS_ORIGIN = "owner_account_context"
CONNECTOR_PROVENANCE_SOURCE = ProvenanceSource.TOOL_OBSERVATION

_KNOWN_IPHONE_KINDS = frozenset(
    {
        "location",
        "focus_mode",
        "arrive_home",
        "leave_home",
        "arrive_work",
        "leave_work",
        "sleep",
        "workout",
        "health",
        "heart_rate_spike",
        "mindfulness",
        "manual_note",
        "mood_check",
        "intention",
        "reflection",
        "weather",
        "commute",
        "with_people",
        "reading",
        "media_context",
        "battery",
        "now_playing",
        "custom",
    }
)

_ADMISSIBLE_IPHONE_KINDS = frozenset(
    {
        "focus_mode",
        "arrive_home",
        "leave_home",
        "arrive_work",
        "leave_work",
        "sleep",
        "workout",
        "heart_rate_spike",
        "mindfulness",
        "manual_note",
        "mood_check",
        "intention",
        "reflection",
        "weather",
        "commute",
        "with_people",
        "reading",
        "media_context",
        "custom",
    }
)

_LAST_DIGEST_BY_KIND: dict[str, str] = {}


@dataclass(frozen=True)
class ConnectorLaneDecision:
    status: str
    reason: str | None = None
    source_ref: str | None = None
    intake_status: str | None = None


class _SingleFactAdapter:
    def __init__(self, fact: IntakeFact):
        self._fact = fact
        self.admitted_body_id: str | None = None

    def oldest_pending(self):
        return self._fact

    def mark_admitted(self, source_ref: str, *, body_memory_id: str) -> None:
        self.admitted_body_id = body_memory_id
        self._fact = None


def reset_connector_lane_dedupe_for_tests() -> None:
    _LAST_DIGEST_BY_KIND.clear()


def _canonical_data(data: Any) -> str:
    return json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_for_signal(kind: str, data: dict[str, Any], connector_id: str) -> str:
    detail = _canonical_data(data)
    return "\n".join(
        [
            f"Connector fact - {connector_id} reported {kind}.",
            f"data: {detail[:1200]}",
            f"observed_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        ]
    )


def _source_ref(connector_id: str, kind: str, digest: str) -> str:
    return f"connector:{connector_id}:{kind}:{digest[:16]}"


def admit_connector_fact(
    signal: dict[str, Any],
    *,
    memory,
    connector_id: str = "iphone",
    adapter: str = "shortcuts-ingress",
    scope: str = "iphone.signals",
    shadow: bool = False,
) -> ConnectorLaneDecision:
    """Admit one minimized connector fact, or return a content-free refusal."""

    kind = signal.get("kind") if isinstance(signal, dict) else None
    if not isinstance(kind, str) or kind not in _KNOWN_IPHONE_KINDS:
        return ConnectorLaneDecision(status="refused", reason="unknown_signal_kind")

    data = signal.get("data") if isinstance(signal, dict) else {}
    if not isinstance(data, dict):
        return ConnectorLaneDecision(status="refused", reason="invalid_signal_data")

    if kind not in _ADMISSIBLE_IPHONE_KINDS:
        return ConnectorLaneDecision(status="refused", reason="raw_sample_not_admitted")

    digest = hashlib.sha256(f"{kind}:{_canonical_data(data)}".encode("utf-8")).hexdigest()
    if _LAST_DIGEST_BY_KIND.get(kind) == digest:
        return ConnectorLaneDecision(
            status="deduped",
            reason="near_identical_consecutive_signal",
            source_ref=_source_ref(connector_id, kind, digest),
        )

    source_ref = _source_ref(connector_id, kind, digest)
    if shadow:
        return ConnectorLaneDecision(status="would_admit", source_ref=source_ref)
    if memory is None:
        return ConnectorLaneDecision(status="refused", reason="memory_unavailable", source_ref=source_ref)

    fact = IntakeFact(
        source_kind=f"connector.{connector_id}.{kind}",
        source_ref=source_ref,
        content=_content_for_signal(kind, data, connector_id),
        provenance_source=CONNECTOR_PROVENANCE_SOURCE,
        egress_origin_class=CONNECTOR_EGRESS_ORIGIN,
        promotion_posture=PromotionPosture.ADMIT_TO_BODY,
        fetch_batch_id=f"{connector_id}:{kind}:{digest[:12]}",
        metadata={
            "lane": "connector",
            "connector_id": connector_id,
            "adapter": adapter,
            "scope": scope,
            "kind": kind,
            "owner_account_context": "true",
            "admission_policy": "delta_digest",
        },
    )
    outcome = admit(_SingleFactAdapter(fact), memory)
    if outcome.status in {"admitted", "already_admitted"}:
        _LAST_DIGEST_BY_KIND[kind] = digest
    return ConnectorLaneDecision(
        status=outcome.status,
        reason=outcome.reason,
        source_ref=outcome.source_ref,
        intake_status=outcome.status,
    )
