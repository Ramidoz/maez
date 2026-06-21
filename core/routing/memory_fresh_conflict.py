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


from core.routing.observation import _sha256


def check_memory_fresh_conflict(
    working_set,
    verifier,
    *,
    claim_limit: int = 5,
    pair_budget: int = 6,
):
    """Pair trusted-memory claims (hypothesis) against fresh items (premise);
    predict contradiction. Returns a redacted MemoryFreshConflictReceipt, or None
    if there is no trusted-memory↔fresh pair to judge. Fail-safe toward the memory:
    any non-'contradicts'/'grounded' verdict → 'ambiguous', never an accusation.
    Returns on the first contradicting pair; remaining budgeted pairs are not evaluated."""
    mems = trusted_memory_items(working_set)
    fresh = fresh_items(working_set)
    if not mems or not fresh:
        return None

    pairs = []  # (fresh_item, mem_item, claim_text)
    for mem in mems:
        for claim in extract_memory_claims(getattr(mem, "text", "") or "", limit=claim_limit):
            for fr in fresh:
                pairs.append((fr, mem, claim))
    if not pairs:
        return None

    pair_limit_exceeded = len(pairs) > pair_budget
    budgeted = pairs[:pair_budget]

    saw_unavailable = False   # verifier raised, or returned label "unavailable"
    saw_nondecisive = False   # verifier returned a real label that is neither contradicts nor grounded
    verifier_name = type(verifier).__name__
    pairs_examined = 0
    for fr, mem, claim in budgeted:
        pairs_examined += 1
        try:
            verdict = verifier.predict(getattr(fr, "text", "") or "", claim)
        except Exception:
            saw_unavailable = True
            continue
        label = getattr(verdict, "label", "unavailable")
        if label == "contradicts":
            rev = getattr(verdict, "revision", None)
            _grounded = getattr(verdict, "score", None)
            # verdict.score is the GROUNDED score (1 - P(contradiction)) per the verifier
            # protocol; the contradiction's confidence is its complement, so the receipt
            # number reads as clash STRENGTH (high = strong), not backwards.
            _confidence = round(1.0 - _grounded, 4) if _grounded is not None else None
            return MemoryFreshConflictReceipt(
                verdict="contradiction",
                mem_id=getattr(mem, "local_label", None),
                mem_label=getattr(mem, "source_type", None),
                fresh_id=getattr(fr, "local_label", None),
                fresh_label=getattr(fr, "source_type", None),
                confidence=_confidence,
                verifier=f"{verifier_name}@{rev}" if rev else verifier_name,
                mem_sha256=_sha256(claim),
                fresh_sha256=_sha256(getattr(fr, "text", "") or ""),
                reason_code="trusted_clash",
                pair_count=pairs_examined,
                pair_limit_exceeded=pair_limit_exceeded,
            )
        if label == "grounded":
            continue
        if label == "unavailable":
            saw_unavailable = True
        else:
            saw_nondecisive = True

    if saw_unavailable:
        reason_code = "verifier_unavailable"
    elif saw_nondecisive:
        reason_code = "non_decisive"
    else:
        reason_code = "clear"
    return MemoryFreshConflictReceipt(
        verdict="ambiguous" if (saw_unavailable or saw_nondecisive) else "none",
        verifier=verifier_name,
        reason_code=reason_code,
        pair_count=pairs_examined,
        pair_limit_exceeded=pair_limit_exceeded,
    )
