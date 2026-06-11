"""MiniCheck grounding shadow — observation only.

Splits the final audited reply into sentences and asks an out-of-process
verifier whether each follows from the claimable evidence, writing
content-light divergence telemetry. This module gates nothing.
"""
from __future__ import annotations

import re
import time

from core.cognition.support_verifier import (
    UNAVAILABLE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def claimable_evidence(claimable_items) -> str:
    parts = []
    for item in claimable_items or ():
        if not isinstance(item, dict):
            continue
        evidence = (
            item.get("evidence")
            or item.get("evidence_refs")
            or item.get("text")
            or item.get("fact")
            or ""
        )
        if evidence:
            parts.append(str(evidence))
    return "\n".join(parts)


def compute_shadow(
    final_text,
    claimable_items,
    verifier,
    *,
    per_sentence_timeout_s: float = 0.25,
    per_job_budget_s: float = 1.5,
) -> dict:
    """Run sentence-level support checks under a per-job budget."""
    evidence = claimable_evidence(claimable_items)
    if not evidence.strip():
        return {
            "status": "no_claimable",
            "sentences": [],
            "shadowed_count": 0,
            "remaining_count": 0,
        }

    sentences = split_sentences(final_text)
    if not sentences:
        return {
            "status": "no_sentences",
            "sentences": [],
            "shadowed_count": 0,
            "remaining_count": 0,
        }

    started = time.monotonic()
    results = []
    shadowed = 0
    status = "ok"
    for idx, sentence in enumerate(sentences):
        if time.monotonic() - started >= per_job_budget_s:
            return {
                "status": "budget_exceeded",
                "sentences": results,
                "shadowed_count": shadowed,
                "remaining_count": len(sentences) - idx,
            }
        try:
            label, score, latency_s = verifier.support(
                evidence,
                sentence,
                per_sentence_timeout_s,
            )
        except Exception:
            label, score, latency_s = UNAVAILABLE, None, 0.0
        if label == UNAVAILABLE:
            status = "verifier_unavailable"
        results.append(
            {
                "sentence": sentence,
                "verdict": label,
                "score": score,
                "latency_s": latency_s,
            }
        )
        shadowed += 1

    return {
        "status": status,
        "sentences": results,
        "shadowed_count": shadowed,
        "remaining_count": 0,
    }
