"""Intake Understanding Faculty shadow telemetry.

Default-off, observation-only. The live path may enqueue a job; all model work
and context fetching happen in the background worker.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from core.cognition.intake_faculty import IntakeRead
from core.search.search_commitment import is_clear_yes, is_search_offer_worthy


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _bucket_latency(latency_s: float) -> float:
    return round(max(0.0, latency_s) * 1000.0, 1)


def offer_snapshot(offer) -> dict[str, Any] | None:
    if offer is None:
        return None
    if isinstance(offer, dict):
        query = offer.get("offered_query") or offer.get("query") or ""
        return {
            "action_type": offer.get("action_type"),
            "stakes": offer.get("stakes"),
            "egress_class": offer.get("egress_class"),
            "executor": offer.get("executor"),
            "offered_query_hash": _hash(str(query)),
        }
    query = getattr(offer, "offered_query", "") or ""
    return {
        "action_type": getattr(offer, "action_type", None),
        "stakes": getattr(offer, "stakes", None),
        "egress_class": getattr(offer, "egress_class", None),
        "executor": getattr(offer, "executor", None),
        "offered_query_hash": _hash(query),
    }


def _hard_want_verdict(text: str) -> str:
    try:
        from core.evolution.wants import is_hard_want

        return _bool(is_hard_want(text or ""))
    except Exception:
        return "unavailable"


def _continuity_verdict(text: str) -> str:
    try:
        from core.routing.focused_cognition import dialogue_continuity_state

        state = dialogue_continuity_state(text or "")
        return _bool(bool(getattr(state, "needs_dialogue", False)))
    except Exception:
        return "unavailable"


def _continuity_kind(text: str) -> str:
    try:
        from core.routing.focused_cognition import dialogue_continuity_state

        state = dialogue_continuity_state(text or "")
        kind = getattr(getattr(state, "kind", None), "value", None)
        return str(kind or "none")
    except Exception:
        return "unavailable"


def _recall_verdict(text: str) -> str:
    try:
        from core.memory.temporal_arithmetic import is_temporal_question
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        return _bool(bool(is_temporal_question(text) or getattr(detect_temporal_anchor(text), "anchor_kind", None)))
    except Exception:
        return "unavailable"


def gate_verdicts(text: str, *, controller, channel: str, chat_id: str) -> dict[str, str]:
    """Side-effect-free snapshots of today's gates.

    If a gate cannot be evaluated read-only, log unavailable. Never call a
    method that consumes/pops state.
    """
    verdicts = {
        "is_clear_yes": _bool(is_clear_yes(text or "")),
        "hard_want": _hard_want_verdict(text or ""),
        "continuity": _continuity_verdict(text or ""),
        "continuity_kind": _continuity_kind(text or ""),
        "recall_intent": _recall_verdict(text or ""),
        "search_worthy": _bool(is_search_offer_worthy(text or "")),
        "awaiting_card": "unavailable",
    }
    try:
        if controller is not None:
            verdicts["awaiting_card"] = _bool(controller.has_awaiting_card(channel, chat_id))
    except Exception:
        verdicts["awaiting_card"] = "unavailable"
    return verdicts


def _agreement(faculty_read: IntakeRead, gate_verdicts: dict[str, str]) -> dict[str, str]:
    def cmp(name: str, faculty_bool: bool | None, gate_key: str) -> str:
        del name
        gate = gate_verdicts.get(gate_key)
        if faculty_bool is None or gate not in {"true", "false"}:
            return "n_a"
        return "agree" if (gate == "true") == faculty_bool else "disagree"

    return {
        "commitment_response": cmp(
            "commitment_response",
            faculty_read.turn_kind == "commitment_response",
            "is_clear_yes",
        ),
        "boundary": cmp(
            "boundary",
            faculty_read.turn_kind == "boundary" or faculty_read.boundary_signal in {"soft", "hard"},
            "hard_want",
        ),
        "continuity": cmp("continuity", faculty_read.turn_kind == "continuity_reference", "continuity"),
        "recall": cmp("recall", faculty_read.turn_kind == "recall_request" or faculty_read.needs == "recall", "recall_intent"),
        "search": cmp("search", faculty_read.turn_kind == "search_request" or faculty_read.needs == "search", "search_worthy"),
    }


def build_telemetry(
    *,
    message: str,
    context_turns: list[str],
    pending_offer: dict | None,
    faculty_read: IntakeRead,
    gate_verdicts: dict[str, str],
    status: str,
    latency_s: float,
    debug: bool = False,
) -> dict[str, Any]:
    context_blob = "\n".join(context_turns or [])
    rec = {
        "ts": int(time.time()),
        "turn_hash": _hash(message),
        "context_hash": _hash(context_blob),
        "turn_len": len(message or ""),
        "context_turn_count": len(context_turns or []),
        "pending_offer": offer_snapshot(pending_offer),
        "faculty_read": faculty_read.to_telemetry(debug=debug),
        "gate_verdicts": dict(gate_verdicts or {}),
        "agreements": _agreement(faculty_read, gate_verdicts or {}),
        "faculty_latency_ms": _bucket_latency(latency_s),
        "status": status,
    }
    if debug:
        rec["turn_excerpt"] = (message or "")[:160]
        rec["context_summary"] = context_blob[:360]
    return rec
