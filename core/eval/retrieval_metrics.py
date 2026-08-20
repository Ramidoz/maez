"""Deterministic retrieval metrics for the Telegram recall benchmark.

Pure functions over ranked id lists and relevant-id sets. No LLM, no
randomness, no clock — every number here is reproducible from the same
inputs, which is the property the LLM-judge harness lacks.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def recall_at_k(ranked_ids: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of relevant ids present in the top-k of the ranking.

    Returns 0.0 when there are no relevant ids (an unanswerable
    question scores through abstention_rate, not recall).
    """
    rel = set(relevant)
    if not rel or k <= 0:
        return 0.0
    top = set(ranked_ids[:k])
    return len(rel & top) / len(rel)


def ndcg_at_k(ranked_ids: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Binary-gain nDCG@k (gain 1 for relevant rows, log2 discount)."""
    rel = set(relevant)
    if not rel or k <= 0:
        return 0.0
    dcg = 0.0
    for i, row_id in enumerate(ranked_ids[:k]):
        if row_id in rel:
            dcg += 1.0 / math.log2(i + 2)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / ideal if ideal > 0 else 0.0


def evidence_hit(evidence_ids: Iterable[str], relevant: Iterable[str]) -> bool:
    """Maez-native: did any answer-bearing row reach the EVIDENCE
    partition (not merely context)? This is the number the audit's
    ingredient 4 actually asks for."""
    rel = set(relevant)
    return bool(rel) and bool(rel & set(evidence_ids))


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def tier_ids(partition: dict, tiers: Sequence[str] = ("raw", "daily", "core")) -> list[str]:
    """Flatten a recall partition ({tier: [entry, ...]}) into ids in
    list order, preserving the tier order given."""
    out: list[str] = []
    for tier in tiers:
        for entry in partition.get(tier, []) or []:
            row_id = str(entry.get("id") or "")
            if row_id:
                out.append(row_id)
    return out


def ranked_concat(evidence: dict, context: dict) -> list[str]:
    """The bench's canonical ranking: evidence tiers first (raw, daily,
    core), then context tiers. Mirrors the prompt's presentation order:
    evidence is what Maez may claim from; context is background."""
    return tier_ids(evidence) + tier_ids(context)
