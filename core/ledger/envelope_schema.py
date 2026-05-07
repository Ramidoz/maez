# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Evidence-envelope vocabulary and structural validation.

This module is the single source of truth for two coordinated artifacts
defined in ``docs/LEDGER_ENVELOPE_SCHEMA.md``:

  1. The provenance enum (§2). Every ``ClaimSlot`` in an evidence
     envelope, and every row in ``claim_judgements.provenance``, MUST
     carry one of the values declared by :data:`PROVENANCE_VALUES`.

  2. The envelope structural shape (§3). The writer accepts an
     ``evidence_envelope`` dict on ``model_reply`` / ``daemon_cycle`` /
     ``peer_message_out`` turns; this module's :func:`validate_envelope`
     enforces that any well-known slot it carries is shaped correctly.

Slice 3.0b (2026-05-07) introduces the ``self_history`` provenance value
+ slot pair to address self-history fabrications (Maez claiming "I told
you X earlier" when no such turn exists). The slot's *population* — i.e.
the bounded ledger lookback that turns prior ``model_reply`` /
``daemon_cycle`` / ``peer_message_out`` rows into ``SelfHistoryRef``
entries — is the responsibility of the envelope BUILDER (slice 3
proper, not yet built). This module only declares the vocabulary and
guards malformed payloads.
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "PROVENANCE_VALUES",
    "SELF_HISTORY_KINDS",
    "SELF_HISTORY_SUMMARY_MAX",
    "validate_provenance",
    "validate_self_history_entry",
    "validate_envelope",
]


# Provenance enum — see LEDGER_ENVELOPE_SCHEMA.md §2.
# String values are kebab-case / lowercase / no aliases.
#
# Slice 3.0b additions (2026-05-07):
#   ``self_history`` — claims about Maez's prior utterances or actions.
PROVENANCE_VALUES: frozenset[str] = frozenset({
    "owner-said",
    "tool-verified",
    "observed",
    "recalled",
    "inferred",
    "synthesized",
    "self_history",
})


# Allowed ``kind`` values inside a SelfHistoryRef. These are the
# turn_kinds that can plausibly carry a Maez utterance the daemon
# should be able to point back at.
SELF_HISTORY_KINDS: frozenset[str] = frozenset({
    "model_reply",
    "daemon_cycle",
    "peer_message_out",
})


# Bounded ledger summary length. The slot is meant to be a *cheap*
# pointer back into the ledger — anything longer, the consumer should
# fetch the row by turn_id.
SELF_HISTORY_SUMMARY_MAX = 200


def validate_provenance(value: Any) -> None:
    """Raise ValueError unless ``value`` is one of PROVENANCE_VALUES."""
    if not isinstance(value, str):
        raise ValueError(
            f"provenance must be a string, got {type(value).__name__}"
        )
    if value not in PROVENANCE_VALUES:
        raise ValueError(
            f"provenance {value!r} is not in the §2 enum "
            f"(allowed: {sorted(PROVENANCE_VALUES)})"
        )


def validate_self_history_entry(entry: Any) -> None:
    """Raise ValueError unless ``entry`` is a well-shaped SelfHistoryRef.

    Required keys: turn_id (str), timestamp (int|float), utterance_summary
    (str ≤ SELF_HISTORY_SUMMARY_MAX), kind (one of SELF_HISTORY_KINDS).
    """
    if not isinstance(entry, dict):
        raise ValueError(
            f"self_history entry must be a dict, got "
            f"{type(entry).__name__}"
        )

    turn_id = entry.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id:
        raise ValueError(
            "self_history entry missing required str turn_id"
        )

    ts = entry.get("timestamp")
    if not isinstance(ts, (int, float)) or isinstance(ts, bool):
        raise ValueError(
            "self_history entry timestamp must be int|float"
        )

    summary = entry.get("utterance_summary")
    if not isinstance(summary, str):
        raise ValueError(
            "self_history entry utterance_summary must be a string"
        )
    if len(summary) > SELF_HISTORY_SUMMARY_MAX:
        raise ValueError(
            f"self_history entry utterance_summary length "
            f"{len(summary)} exceeds bound {SELF_HISTORY_SUMMARY_MAX}"
        )

    kind = entry.get("kind")
    if kind not in SELF_HISTORY_KINDS:
        raise ValueError(
            f"self_history entry kind {kind!r} not in "
            f"{sorted(SELF_HISTORY_KINDS)}"
        )


def validate_envelope(envelope: Any) -> None:
    """Validate the well-known slots of an evidence envelope.

    The envelope is intentionally permissive — unknown keys pass through
    (forward-compatibility for future slots). Known slots, when present,
    must match the §3 shape. Slots covered:
      - claimable: list (per-claim provenance not yet enforced here;
        Slice 4 will add ClaimSlot validation).
      - forbidden: list
      - tool_results: list
      - self_history: list[SelfHistoryRef]  (slice 3.0b)
      - signals_present, signals_absent: list[str]

    None and missing slots are equivalent (slot is optional).
    """
    if envelope is None:
        return
    if not isinstance(envelope, dict):
        raise ValueError(
            f"evidence_envelope must be a dict or None, got "
            f"{type(envelope).__name__}"
        )

    # List-shaped slots: types only, contents validated per-slot below.
    for list_slot in ("claimable", "forbidden", "tool_results",
                      "self_history", "signals_present", "signals_absent"):
        if list_slot in envelope and envelope[list_slot] is not None:
            if not isinstance(envelope[list_slot], list):
                raise ValueError(
                    f"evidence_envelope.{list_slot} must be a list, "
                    f"got {type(envelope[list_slot]).__name__}"
                )

    # Per-entry validation for self_history — slice 3.0b's load-bearing
    # check. Bad entries here are how self-history fabrications would
    # leak in if the envelope builder had a bug, so we fail loud.
    for i, entry in enumerate(envelope.get("self_history") or []):
        try:
            validate_self_history_entry(entry)
        except ValueError as e:
            raise ValueError(
                f"evidence_envelope.self_history[{i}]: {e}"
            ) from e
