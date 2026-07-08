# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Deterministic taint/privacy stamping for ledger turns.

S1 of the consolidation spine makes provenance explicit at the ledger write
door. The writer does not infer labels; callers provide them and this module
validates the provided set against the turn-kind contract.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

TAINT_LABEL_ORDER: tuple[str, ...] = (
    "owner_utterance",
    "self_generated",
    "tool_output",
    "internet_derived",
    "third_party",
)
ALLOWED_TAINT_LABELS = frozenset(TAINT_LABEL_ORDER)
ALLOWED_PRIVACY_ACCESS = frozenset(("public", "sealed_adjacent"))


DEFAULT_ALLOWED_TAINT_LABEL_SETS_BY_TURN_KIND: dict[str, frozenset[frozenset[str]]] = {
    "user_message": frozenset((frozenset(("owner_utterance",)),)),
    "model_reply": frozenset((frozenset(("self_generated",)),)),
    "tool_call": frozenset((frozenset(("self_generated",)),)),
    "tool_result": frozenset(
        (
            frozenset(("tool_output",)),
            frozenset(("tool_output", "internet_derived")),
            frozenset(("tool_output", "third_party")),
            frozenset(("tool_output", "internet_derived", "third_party")),
        )
    ),
    "daemon_cycle": frozenset((frozenset(("self_generated",)),)),
    "approval_decision": frozenset((frozenset(("owner_utterance",)),)),
    "self_mod_dialog_step": frozenset(
        (frozenset(("owner_utterance", "self_generated")),)
    ),
    "peer_message_in": frozenset((frozenset(("third_party",)),)),
    "peer_message_out": frozenset((frozenset(("self_generated",)),)),
    "system_event": frozenset(
        (
            frozenset(("self_generated",)),
            frozenset(("owner_utterance", "self_generated")),
            frozenset(("self_generated", "tool_output")),
            frozenset(("self_generated", "third_party")),
            frozenset(("self_generated", "tool_output", "internet_derived")),
        )
    ),
}

CALLER_ALLOWED_TAINT_LABEL_SETS: dict[tuple[str, str], frozenset[frozenset[str]]] = {
    ("user_message", "x6_rehearsal"): frozenset((frozenset(("self_generated",)),)),
}


class TaintStampingRefusal(ValueError):
    """Typed writer refusal for invalid taint/privacy stamping."""

    def __init__(
        self,
        message: str,
        *,
        turn_kind: str,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.turn_kind = turn_kind
        self.reason = reason


@dataclass(frozen=True)
class TurnStamp:
    taint_labels: tuple[str, ...]
    taint_labels_json: str
    privacy_access: str


def _raise(turn_kind: str, reason: str, message: str) -> None:
    raise TaintStampingRefusal(
        f"{turn_kind}: {message}",
        turn_kind=turn_kind,
        reason=reason,
    )


def _allowed_sets_for(turn_kind: str, caller: str | None) -> frozenset[frozenset[str]] | None:
    if caller:
        caller_sets = CALLER_ALLOWED_TAINT_LABEL_SETS.get((turn_kind, caller))
        if caller_sets is not None:
            return caller_sets
    return DEFAULT_ALLOWED_TAINT_LABEL_SETS_BY_TURN_KIND.get(turn_kind)


def _normalize_labels(
    turn_kind: str,
    labels: Iterable[str],
    *,
    caller: str | None,
) -> tuple[str, ...]:
    if labels is None:
        _raise(turn_kind, "taint_labels_missing", "taint_labels is required")
    if isinstance(labels, (str, bytes)):
        _raise(turn_kind, "taint_labels_not_iterable", "taint_labels must be a sequence of labels")

    raw = list(labels)
    if not raw:
        _raise(turn_kind, "taint_labels_empty", "taint_labels must not be empty")

    if any(not isinstance(label, str) for label in raw):
        _raise(turn_kind, "taint_label_not_string", "all taint labels must be strings")

    label_set = set(raw)
    if len(label_set) != len(raw):
        _raise(turn_kind, "taint_labels_duplicate", "taint_labels must not contain duplicates")

    unknown = sorted(label_set - ALLOWED_TAINT_LABELS)
    if unknown:
        _raise(
            turn_kind,
            "taint_label_unknown",
            f"unknown taint labels {unknown!r}",
        )

    ordered = tuple(label for label in TAINT_LABEL_ORDER if label in label_set)
    allowed_sets = _allowed_sets_for(turn_kind, caller)
    if allowed_sets is None:
        _raise(turn_kind, "turn_kind_unknown", f"unknown turn_kind {turn_kind!r}")
    if frozenset(ordered) not in allowed_sets:
        allowed = [sorted(s, key=TAINT_LABEL_ORDER.index) for s in allowed_sets]
        _raise(
            turn_kind,
            "taint_labels_out_of_map",
            f"taint_labels {list(ordered)!r} not allowed for caller {caller!r}; "
            f"allowed sets={allowed!r}",
        )
    return ordered


def validate_turn_stamp(
    *,
    turn_kind: str,
    taint_labels: Iterable[str],
    privacy_access: str,
    caller: str | None = None,
) -> TurnStamp:
    """Validate and canonicalize a caller-provided turn stamp."""
    labels = _normalize_labels(turn_kind, taint_labels, caller=caller)
    if privacy_access not in ALLOWED_PRIVACY_ACCESS:
        _raise(
            turn_kind,
            "privacy_access_invalid",
            f"privacy_access must be one of {sorted(ALLOWED_PRIVACY_ACCESS)!r}, got {privacy_access!r}",
        )
    labels_json = json.dumps(
        list(labels),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return TurnStamp(
        taint_labels=labels,
        taint_labels_json=labels_json,
        privacy_access=privacy_access,
    )
