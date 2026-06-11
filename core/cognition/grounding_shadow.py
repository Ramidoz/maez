"""MiniCheck grounding shadow — observation only.

Splits the final audited reply into sentences and asks an out-of-process
verifier whether each follows from the claimable evidence, writing
content-light divergence telemetry. This module gates nothing.
"""
from __future__ import annotations

import re
import hashlib
import time

from core.cognition.support_verifier import (
    SUPPORTED,
    UNAVAILABLE,
    UNSUPPORTED,
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


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def audit_summary_from_result(audit_result) -> dict:
    """Return a content-light summary using real AuditResult fields only."""
    flags = getattr(audit_result, "flags", None) or []
    mode = getattr(audit_result, "mode", "noop")
    return {
        "audit_available": mode != "judge_unavailable",
        "flag_count": len(flags),
        "flag_kinds": sorted({getattr(flag, "kind", "unknown") for flag in flags}),
        "rewritten": bool(getattr(audit_result, "rewritten", False)),
        "mode": mode,
        "skipped_reason": getattr(audit_result, "skipped_reason", None),
    }


def _claimable_chars(claimable_items) -> int:
    total = 0
    for item in claimable_items or ():
        if not isinstance(item, dict):
            continue
        total += len(str(item.get("evidence") or item.get("text") or ""))
    return total


def build_telemetry(
    shadow_id,
    ts,
    surface,
    boot_id,
    audit_summary,
    claimable_items,
    compute_result,
    *,
    debug: bool = False,
) -> dict:
    sentences = []
    for result in compute_result.get("sentences", []):
        sentence = result.get("sentence") or ""
        rec = {
            "sentence_hash": _hash(sentence),
            "verdict": result.get("verdict"),
            "score": result.get("score"),
            "latency_ms": round((result.get("latency_s") or 0.0) * 1000, 1),
        }
        if debug:
            rec["snippet"] = sentence[:120]
        sentences.append(rec)

    verdicts = [r.get("verdict") for r in compute_result.get("sentences", [])]
    return {
        "shadow_id": shadow_id,
        "ts": ts,
        "surface": surface,
        "boot_id": boot_id,
        "audit_available": audit_summary.get("audit_available"),
        "flag_count": audit_summary.get("flag_count"),
        "flag_kinds": audit_summary.get("flag_kinds"),
        "rewritten": audit_summary.get("rewritten"),
        "mode": audit_summary.get("mode"),
        "skipped_reason": audit_summary.get("skipped_reason"),
        "claimable_count": len(claimable_items or []),
        "claimable_chars": _claimable_chars(claimable_items),
        "provenance_refs": [
            _hash(str(c.get("provenance") or ""))
            for c in (claimable_items or ())
            if isinstance(c, dict)
        ],
        "sentence_count": len(verdicts),
        "unsupported_count": sum(1 for verdict in verdicts if verdict == UNSUPPORTED),
        "supported_count": sum(1 for verdict in verdicts if verdict == SUPPORTED),
        "skipped_count": compute_result.get("remaining_count", 0),
        "status": compute_result["status"],
        "sentences": sentences,
    }
