"""Trusted-memory ↔ fresh-evidence contradiction SENSE (shadow detector v0).

Reuses the VERIFIER SHAPE from photo_contradiction (ContradictionVerifier /
ClaimVerdict / LocalNLIContradictionVerifier) but emits its OWN redacted receipt
— it must NEVER log claim/memory/fresh text. Fail-safe toward the memory:
unavailable / low-confidence → 'ambiguous', never a contradiction accusation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryFreshConflictReceipt:
    """Content-light by construction — NO field carries claim/memory/fresh text."""
    verdict: str  # "contradiction" | "none" | "ambiguous"
    mem_id: str | None = None
    mem_label: str | None = None
    fresh_id: str | None = None
    fresh_label: str | None = None
    confidence: float | None = None
    verifier: str | None = None
    mem_sha256: str | None = None
    fresh_sha256: str | None = None
    reason_code: str | None = None
    pair_count: int = 0
    pair_limit_exceeded: bool = False


def memory_fresh_conflict_sense_enabled(env=os.environ) -> bool:
    value = (env.get("MAEZ_MEM_FRESH_CONFLICT_SENSE", "") or "").strip().lower()
    return value in ("1", "true", "yes", "on")
