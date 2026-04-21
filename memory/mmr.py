# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Maximal Marginal Relevance (MMR) re-ranking.

Adapted from OpenClaw's extensions/memory-core/src/memory/mmr.ts
(MIT-licensed). Ported to Python, integrated into Maez's recall pipeline
as a diversity layer on top of Chroma distance + topic-level anti-
fixation.

MMR balances relevance with diversity by iteratively selecting the next
item that maximizes:

    score(item) = λ · relevance(item) - (1 - λ) · max_similarity(item, selected)

where relevance is 1 - distance (so lower-distance items rank higher)
and similarity is Jaccard on tokenized content.

λ = 1.0 → pure relevance (same as original ranking)
λ = 0.0 → pure diversity (ignore relevance, maximize spread)
λ = 0.7 → OpenClaw default; strong relevance, enough diversity to stop
         a single-topic result set from cloning itself across all slots.

Why this helps Maez:
  The daemon's _reason() cycle keeps fixating on disk metrics. The
  topic router's anti-fixation penalty already down-ranks "disk" as a
  category, but once the query lands on a disk-adjacent topic, the
  top-N recall still returns multiple near-duplicate disk snippets.
  MMR breaks that by forcing successive picks to bring new tokens.
"""
from __future__ import annotations

import re

# CJK unicode ranges — Maez is English-primary but the OpenClaw
# tokenizer handles CJK cleanly, so we keep the capability. No cost to
# English users; no conditional branch at call time.
_CJK_RE = re.compile(
    r"[぀-ゟ゠-ヿ"
    r"㐀-䶿一-鿿"
    r"가-힯ᄀ-ᇿ]"
)
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
# Numbers are normalized to a single token so two disk-usage snippets
# ("70.7%" and "69.9%") register as near-duplicates instead of being
# separated by their digit sequences. Without this, MMR's Jaccard sim
# sees them as less similar than they semantically are, and disk-
# fixation drift slips through diversity re-ranking.
_NUM_RE = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
_NUM_TOKEN = "__num__"

DEFAULT_LAMBDA = 0.7


def tokenize(text: str) -> set[str]:
    """Produce a token set for Jaccard comparison.

    ASCII: lowercase alphanumeric runs (`maez-daemon` → `maez`, `daemon`).
    CJK: per-character unigrams plus adjacent-pair bigrams. Only bigrams
         of ORIGINALLY adjacent characters — mixing "我喜欢hello你好" must
         NOT produce the spurious bigram "欢你".
    """
    if not text:
        return set()
    lower = text.lower()
    # Replace number runs with a single placeholder BEFORE ASCII
    # tokenization so "70.7%" and "69.9%" collapse to {__num__}.
    normalized = _NUM_RE.sub(_NUM_TOKEN, lower)
    tokens: set[str] = set(_ASCII_TOKEN_RE.findall(normalized))

    cjk_positions: list[tuple[int, str]] = []
    for i, ch in enumerate(lower):
        if _CJK_RE.match(ch):
            cjk_positions.append((i, ch))

    for idx, ch in cjk_positions:
        tokens.add(ch)
    for i in range(len(cjk_positions) - 1):
        pos_a, ch_a = cjk_positions[i]
        pos_b, ch_b = cjk_positions[i + 1]
        if pos_b == pos_a + 1:
            tokens.add(ch_a + ch_b)
    return tokens


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity in [0, 1]. Two empty sets are defined as
    perfectly similar (1.0) so we don't over-diversify vacuous content."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def mmr_rerank(
    items: list[dict],
    *,
    k: int,
    lambda_: float = DEFAULT_LAMBDA,
    content_key: str = "content",
    distance_key: str = "distance",
) -> list[dict]:
    """Re-rank `items` by MMR and return the top `k` in selection order.

    Each item is a dict with at least `content_key` (text) and
    `distance_key` (Chroma-style [0, ∞), lower = more relevant). A
    missing distance is treated as 1.0 (neutral).

    Does not mutate input items. Selection order is deterministic for
    ties — ties resolve by original list order.
    """
    if k <= 0 or not items:
        return []
    if lambda_ >= 1.0:
        # Pure relevance: just sort by distance and take top-k.
        return sorted(items, key=lambda m: m.get(distance_key) or 1.0)[:k]

    # Pre-tokenize all candidates once; this is the hot path.
    tokenized: list[set[str]] = [
        tokenize(m.get(content_key, "") or "") for m in items
    ]
    # Relevance = 1 - clamped_distance (so 0-distance items are most relevant).
    relevance: list[float] = []
    for m in items:
        d = m.get(distance_key)
        if d is None:
            d = 1.0
        d = max(0.0, min(1.0, float(d)))
        relevance.append(1.0 - d)

    selected_indices: list[int] = []
    remaining = list(range(len(items)))

    while remaining and len(selected_indices) < k:
        best_idx = None
        best_score = float("-inf")
        for i in remaining:
            if not selected_indices:
                max_sim = 0.0
            else:
                max_sim = max(
                    jaccard(tokenized[i], tokenized[j]) for j in selected_indices
                )
            score = lambda_ * relevance[i] - (1.0 - lambda_) * max_sim
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is None:
            break
        selected_indices.append(best_idx)
        remaining.remove(best_idx)

    return [items[i] for i in selected_indices]
