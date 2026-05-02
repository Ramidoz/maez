# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""5x.F.A — cycle-scoped recall-context bag (helpers).

Per-cycle accumulation of recalled memory IDs + their
``trust_tier`` so action handlers running in the same cycle can
check whether any untrusted entry was in the LLM's prompt.

This module is the helper layer; F.A is a no-behavior-change slice
that builds the substrate. F.B (next slice) wires the daemon to
populate the bag and adds the consumer in ``_do_update_baseline``.

The bag is intentionally narrow: **memory-derived prompt context
only**. Ambient context (phone/weather/active-window) and lived-
recall episode IDs (SQLite-backed, no reliable trust_tier lookup)
are excluded BY CONSTRUCTION because ``capture`` only reads the
``core`` / ``daily`` / ``raw`` keys of the supplied dict. Anything
else is silently ignored.

Untagged legacy entries (no ``trust_tier`` metadata, pre-5x.A) are
captured with the explicit label ``"unknown"`` rather than dropped.
This matches the 5x.D.A ``_ancestor_tier_label`` semantics so F.B
can rely on ``has_untrusted`` cleanly distinguishing real
untrusted material from legacy/missing-metadata absence.

Design constraints (locked in 5x.F design conversation):

  - The bag MUST NOT be coupled to Chroma or MemoryManager. It's
    a daemon-state object; coupling here would invert the
    dependency direction and re-create the laundering risk. An
    AST-parse test in ``tests/test_cycle_recall_context.py``
    enforces this structurally.
  - ``has_untrusted`` is the boolean F.B consumes. Its semantic
    is "any-untrusted-tips" — a single ``trust_tier="untrusted"``
    entry in the bag returns True. This is the conservative
    direction; weakening it to "majority untrusted" or
    "thresholded untrusted" would hide laundering.
  - Legacy ``"unknown"`` entries are NON-DEGRADING — they do not
    trigger ``has_untrusted``. Otherwise mass legacy material in
    a cycle's recall scope would cause every baseline to
    downgrade, which is a different threat than what F.B closes.
"""
from __future__ import annotations

# Recall-tier keys that ``capture`` reads from the recalled dict.
# Other keys (e.g. a future 'ambient' or 'lived_episodes') are
# ignored. Using a constant tuple makes the contract explicit and
# greppable.
_RECALL_TIER_KEYS: tuple[str, ...] = ("core", "daily", "raw")


def make_empty() -> dict:
    """Construct a fresh, empty cycle-recall-context bag. Each call
    returns a NEW underlying ``set`` and ``dict`` so callers can
    reset between cycles without leaking prior state."""
    return {"ids": set(), "tiers_by_id": {}}


def capture(bag: dict, recalled: dict) -> dict:
    """Append the recalled-memory IDs + their tiers to ``bag``.

    Only entries under the ``core`` / ``daily`` / ``raw`` keys of
    ``recalled`` are read. Other keys are silently ignored — this
    is the structural exclusion for ambient context and any future
    non-recall data shape.

    Untagged entries (no ``metadata.trust_tier``) are captured with
    tier ``"unknown"``. Mutates ``bag`` in place AND returns it for
    chained-call ergonomics.

    Defensive: entries lacking an ``id`` field are skipped silently
    rather than raising — a malformed entry shouldn't crash the
    daemon's reasoning loop."""
    if not isinstance(recalled, dict):
        return bag
    for tier_key in _RECALL_TIER_KEYS:
        entries = recalled.get(tier_key) or []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            mid = entry.get("id")
            if not mid:
                continue
            mid = str(mid)
            meta = entry.get("metadata") or {}
            tier = meta.get("trust_tier") if isinstance(meta, dict) else None
            tier_label = str(tier) if tier else "unknown"
            bag["ids"].add(mid)
            bag["tiers_by_id"][mid] = tier_label
    return bag


def tier_for(bag: dict, memory_id: str) -> str | None:
    """Return the captured tier for a given memory ID, or ``None``
    if the ID was never captured. Callers that want a sentinel
    rather than ``None`` (e.g. for hash-key uniformity) should
    handle the absence themselves; this helper stays minimal."""
    return bag["tiers_by_id"].get(memory_id)


def has_untrusted(bag: dict) -> bool:
    """Return True iff at least one captured entry carries
    ``trust_tier="untrusted"``.

    The any-untrusted-tips semantic is intentional and conservative
    — F.B's downgrade rule fires on this boolean. Legacy/unknown
    entries do NOT contribute (non-degrading), matching 5x.D.A's
    ``_worst_known_tier`` semantics."""
    return any(tier == "untrusted" for tier in bag["tiers_by_id"].values())


__all__ = [
    "make_empty",
    "capture",
    "tier_for",
    "has_untrusted",
]
