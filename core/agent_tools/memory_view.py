# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Memory introspection tools (Slice 7 — Letta-style facade).

Adapted from Letta (formerly MemGPT) memory-management API. Letta
gives the agent direct mutation tools (``update_block`` /
``archive_block``); Maez's adaptation is **read-only** at this
session — introspection only. Mutation tools come in Session 2 of
the slice behind the consent-card pattern (every memory mutation
requires owner approval, matching Maez's existing covenant for
self-evolution proposals).

This module is a thin facade over the existing ``MemoryManager``
and ``EpisodeStore`` APIs — no backend re-implementation. The
value-add is:

1. A unified view across episodes + core + daily memories the
   brain loop can consult during synthesis.
2. A compact summary the model can drop into a context block
   for self-awareness of its own memory state.
3. Token-overlap search consistent with lived_recall's tokenizer
   (so memory-view query results align with what would surface
   in the actual brief).

Cites:
- Mem-GPT / Letta (Packer et al. 2023) — original
  agent-memory-management toolset shape.
- Audit slice queue #7 in
  ``docs/audits/2026-04-29-field-alignment/FIELD_ALIGNMENT.md``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Keep summaries bounded so they fit in a small context block
# without dominating the prompt. ~600 chars is enough for a
# one-paragraph summary plus a few line items.
_SUMMARY_MAX_CHARS: int = 700

# Mirrors MemoryManager._EXCLUDED_INTEGRITY: entries flagged with
# any of these tags should not surface from owner-facing search.
# Kept inline to avoid coupling to a private name.
_EXCLUDED_INTEGRITY: frozenset[str] = frozenset({
    "stale", "fabricated", "historical_artifact", "test_failure",
})


def _safe_count(getter) -> int:
    """Best-effort counter that returns 0 on any backend failure
    (ChromaDB unreachable, transient lock, etc.). Memory introspection
    should NEVER break the synthesis path that consumes it."""
    try:
        return int(getter())
    except Exception as exc:
        logger.debug("memory_view: counter failed (returning 0): %s", exc)
        return 0


def memory_stats(mm: Any, episode_store: Any) -> dict:
    """Per-tier counts + totals for the lived memory layer.

    Returns ``{raw, daily, core, episodes, total}`` ints. Each tier
    counter is wrapped in ``_safe_count`` so a single backend
    failure (e.g. one ChromaDB collection unreachable) doesn't
    null out the whole view — the view degrades gracefully with
    zeros for unavailable tiers.
    """
    raw = _safe_count(mm.raw.count) if hasattr(mm, "raw") else 0
    daily = _safe_count(mm.daily.count) if hasattr(mm, "daily") else 0
    core = _safe_count(mm.core.count) if hasattr(mm, "core") else 0
    try:
        episodes = len(episode_store.list_active() or [])
    except Exception as exc:
        logger.debug("memory_view: episode count failed: %s", exc)
        episodes = 0
    return {
        "raw": raw,
        "daily": daily,
        "core": core,
        "episodes": episodes,
        "total": raw + daily + core + episodes,
    }


def _meta_timestamp(mem: dict) -> str:
    """Best-effort timestamp accessor. Returns empty string on
    miss so sort comparisons stay valid (empty sorts before any
    real timestamp)."""
    meta = mem.get("metadata") or {}
    ts = meta.get("timestamp") or meta.get("created_at") or ""
    return str(ts)


def list_recent_core(mm: Any, limit: int = 10) -> list[dict]:
    """Most-recent core memories, newest first. Sorts by metadata
    ``timestamp`` (or ``created_at``) descending; missing
    timestamps fall to the end."""
    try:
        cores = mm.get_all_core() or []
    except Exception as exc:
        logger.debug("memory_view: get_all_core failed: %s", exc)
        return []
    # Tie-breaker on id keeps order deterministic when two entries
    # share a timestamp (e.g. seeded fixture data).
    cores.sort(key=lambda m: (_meta_timestamp(m), str(m.get("id") or "")),
               reverse=True)
    n = max(0, int(limit))
    return cores[:n]


def list_recent_episodes(episode_store: Any, limit: int = 20) -> list[dict]:
    """Most-recent active episodes, newest first.
    ``EpisodeStore.list_active`` already returns newest-first."""
    try:
        active = episode_store.list_active() or []
    except Exception as exc:
        logger.debug("memory_view: list_active failed: %s", exc)
        return []
    return active[:max(0, int(limit))]


def _tokenize(text: str) -> set[str]:
    """Mirror lived_recall's tokenizer so memory-view search
    results line up with what would surface in the actual brief."""
    if not text:
        return set()
    try:
        from core.memory.lived_recall import _tokenize as _liv

        return set(_liv(text))
    except Exception:
        # Fallback: lowercase alphabetic tokens, length > 1.
        import re as _re

        return {
            t.lower() for t in _re.findall(r"[A-Za-z]+", text)
            if len(t) > 1
        }


def search_memories(
    mm: Any,
    *,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Token-overlap search across core + recent daily. Returns
    matches sorted by overlap-count descending. Empty query → ``[]``.

    Raw memories are skipped by default — they're high-volume,
    Chroma-backed, and best searched via ``MemoryManager.recall``
    which uses embeddings; the value-add of this function is
    structured-tier search (core + daily) where token overlap is
    the canonical match path.
    """
    if not query or not query.strip():
        return []
    q_toks = _tokenize(query)
    if not q_toks:
        return []
    pool: list[dict] = []
    try:
        pool.extend(mm.get_all_core() or [])
    except Exception as exc:
        logger.debug("memory_view: core fetch failed: %s", exc)
    try:
        pool.extend(mm.get_recent_daily(limit=50) or [])
    except Exception as exc:
        logger.debug("memory_view: daily fetch failed: %s", exc)
    scored: list[tuple[int, dict]] = []
    for mem in pool:
        # Honor MemoryManager's integrity exclusion list: never
        # resurface entries the owner already marked as fabricated /
        # stale / historical-artifact via the lived recall path.
        meta = mem.get("metadata") or {}
        if (meta.get("integrity") or "").strip() in _EXCLUDED_INTEGRITY:
            continue
        text = (mem.get("content") or "")
        m_toks = _tokenize(text)
        if not m_toks:
            continue
        overlap = len(q_toks & m_toks)
        if overlap > 0:
            scored.append((overlap, mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    n = max(0, int(limit))
    return [m for _, m in scored[:n]]


def summarize_for_prompt(mm: Any, episode_store: Any) -> str:
    """Compact one-paragraph summary of the memory state for
    drop-in into a system-message block. Bounded length so it
    doesn't dominate the prompt.

    Format::

        Memory state: 200 raw / 40 daily / 15 core / 8 active
        episodes (255 total). Most recent core: 'truthful continuity
        in Maez', 'grandmother case as the north_star'.

    Used by the brain loop / CLI to give the model self-awareness
    of its own memory layer without injecting full content.
    """
    stats = memory_stats(mm, episode_store)
    parts: list[str] = [
        f"Memory state: {stats['raw']} raw / {stats['daily']} daily / "
        f"{stats['core']} core / {stats['episodes']} active episodes "
        f"({stats['total']} total in tiered store)."
    ]
    cores = list_recent_core(mm, limit=2)
    if cores:
        snippets: list[str] = []
        for c in cores:
            content = (c.get("content") or "").strip().replace("\n", " ")
            if content:
                snippets.append(content[:80])
        if snippets:
            parts.append("Most recent core: " + " | ".join(snippets) + ".")
    out = " ".join(parts)
    if len(out) > _SUMMARY_MAX_CHARS:
        out = out[:_SUMMARY_MAX_CHARS - 1].rstrip() + "…"
    return out


__all__ = [
    "list_recent_core",
    "list_recent_episodes",
    "memory_stats",
    "search_memories",
    "summarize_for_prompt",
]
