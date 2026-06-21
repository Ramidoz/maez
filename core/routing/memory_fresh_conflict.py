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


from core.routing.focused_cognition import _FRESH_SOURCE_TYPES
from core.routing.photo_contradiction import (
    _SENTENCE_RE,
    _clean_sentence,
    normalize_claim_text,
)

_TRUSTED_TIERS = frozenset({"lived", "covenant"})


def trusted_memory_items(working_set):
    """EXACT, fail-closed: origin_trust ∈ {lived,covenant} AND provenance != self_web_claim.
    None / unknown trust → EXCLUDED (vague trust never counts as sacred memory)."""
    out = []
    for it in getattr(working_set, "items", ()) or ():
        trust = getattr(it, "origin_trust", None)
        if trust not in _TRUSTED_TIERS:
            continue
        if getattr(it, "origin_provenance", None) == "self_web_claim":
            continue
        out.append(it)
    return out


def fresh_items(working_set):
    return [
        it for it in (getattr(working_set, "items", ()) or ())
        if getattr(it, "source_type", None) in _FRESH_SOURCE_TYPES
    ]


def extract_memory_claims(text: str, *, limit: int = 5) -> list[str]:
    """Per-sentence claims from a memory item — NO perceptual filter (memory claims
    are not perceptual). Bounded by `limit`."""
    if limit <= 0 or not text:
        return []
    normalized = normalize_claim_text(text)
    claims: list[str] = []
    for match in _SENTENCE_RE.finditer(text):
        sentence = _clean_sentence(match.group(0))
        if not sentence:
            continue
        if normalize_claim_text(sentence) not in normalized:
            continue
        claims.append(sentence)
        if len(claims) >= limit:
            break
    return claims
