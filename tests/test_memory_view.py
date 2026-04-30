# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Memory-view tests (Slice 7 — Letta-style introspection tools).

Adapted from Letta (formerly MemGPT) memory-management API. Letta
gives the agent direct mutation tools (``update_block``,
``archive_block``); Maez's adaptation is **read-only** in this
session — introspection tools that produce structured views of
the memory state. Mutation tools come in Session 2 of the slice
behind the consent-card pattern (every memory mutation requires
owner approval).

What this module ships (Session 1):

- ``memory_stats(mm, episode_store)`` — counts per tier (raw,
  daily, core, episodes), latest-update timestamps, brief health
  summary
- ``list_recent_core(mm, limit)`` — most-recent core memories,
  newest-first
- ``list_recent_episodes(episode_store, limit)`` — active
  episodes, newest-first
- ``search_memories(mm, query, limit)`` — token-overlap search
  across raw + daily + core, consistent with lived_recall's
  tokenizer

The module is deliberately a thin facade over existing
``MemoryManager`` and ``EpisodeStore`` APIs — no backend
re-implementation. Tests use stub stores so they don't depend on
ChromaDB.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _stub_memory_manager(*, raw_count=10, daily_count=5, core_count=3, core_data=None):
    """Minimal stand-in for ``MemoryManager``. Implements only the
    surface ``memory_view`` consumes."""
    mm = MagicMock()
    mm.raw.count.return_value = raw_count
    mm.daily.count.return_value = daily_count
    mm.core.count.return_value = core_count
    mm.get_all_core.return_value = core_data or []
    mm.get_recent_daily.return_value = []
    return mm


def _stub_episode_store(episodes=None):
    es = MagicMock()
    es.list_active.return_value = list(episodes or [])
    return es


# ── memory_stats ────────────────────────────────────────────────────


class TestMemoryStats(unittest.TestCase):
    def test_basic_counts(self):
        from core.agent_tools.memory_view import memory_stats

        mm = _stub_memory_manager(raw_count=120, daily_count=30, core_count=18)
        es = _stub_episode_store([{"id": "ep-1"}, {"id": "ep-2"}])
        stats = memory_stats(mm, es)
        self.assertEqual(stats["raw"], 120)
        self.assertEqual(stats["daily"], 30)
        self.assertEqual(stats["core"], 18)
        self.assertEqual(stats["episodes"], 2)
        self.assertEqual(stats["total"], 170)

    def test_handles_empty_store(self):
        from core.agent_tools.memory_view import memory_stats

        mm = _stub_memory_manager(raw_count=0, daily_count=0, core_count=0)
        es = _stub_episode_store([])
        stats = memory_stats(mm, es)
        self.assertEqual(stats["total"], 0)

    def test_resilient_to_count_failure(self):
        """A failing collection counter shouldn't crash the whole
        view — return what we can with defaults for failures."""
        from core.agent_tools.memory_view import memory_stats

        mm = MagicMock()
        mm.raw.count.side_effect = RuntimeError("collection unreachable")
        mm.daily.count.return_value = 5
        mm.core.count.return_value = 3
        es = _stub_episode_store([])
        stats = memory_stats(mm, es)
        self.assertEqual(stats["raw"], 0)
        self.assertEqual(stats["daily"], 5)
        self.assertEqual(stats["core"], 3)


# ── list_recent_core ────────────────────────────────────────────────


class TestListRecentCore(unittest.TestCase):
    def test_returns_recent_first(self):
        from core.agent_tools.memory_view import list_recent_core

        cores = [
            {"id": "core-1", "content": "first",
             "metadata": {"timestamp": "2026-01-01T00:00:00+00:00"}},
            {"id": "core-2", "content": "second",
             "metadata": {"timestamp": "2026-04-01T00:00:00+00:00"}},
            {"id": "core-3", "content": "third",
             "metadata": {"timestamp": "2026-02-15T00:00:00+00:00"}},
        ]
        mm = _stub_memory_manager(core_data=cores)
        result = list_recent_core(mm, limit=2)
        self.assertEqual(len(result), 2)
        # Newest first — core-2 (2026-04) before core-3 (2026-02).
        self.assertEqual(result[0]["id"], "core-2")
        self.assertEqual(result[1]["id"], "core-3")

    def test_handles_missing_timestamp(self):
        """A core memory with no timestamp shouldn't crash sorting."""
        from core.agent_tools.memory_view import list_recent_core

        cores = [
            {"id": "core-a", "content": "x", "metadata": {}},
            {"id": "core-b", "content": "y",
             "metadata": {"timestamp": "2026-04-01T00:00:00+00:00"}},
        ]
        mm = _stub_memory_manager(core_data=cores)
        result = list_recent_core(mm, limit=10)
        self.assertEqual(len(result), 2)
        # The timestamped one wins ordering.
        self.assertEqual(result[0]["id"], "core-b")

    def test_respects_limit(self):
        from core.agent_tools.memory_view import list_recent_core

        cores = [
            {"id": f"core-{i}", "content": "x",
             "metadata": {"timestamp": f"2026-04-{i:02d}T00:00:00+00:00"}}
            for i in range(1, 11)
        ]
        mm = _stub_memory_manager(core_data=cores)
        result = list_recent_core(mm, limit=3)
        self.assertEqual(len(result), 3)


# ── list_recent_episodes ────────────────────────────────────────────


class TestListRecentEpisodes(unittest.TestCase):
    def test_returns_active_only(self):
        from core.agent_tools.memory_view import list_recent_episodes

        eps = [
            {"id": "ep-1", "title": "first", "created_at": "2026-04-01..."},
            {"id": "ep-2", "title": "second", "created_at": "2026-04-15..."},
        ]
        es = _stub_episode_store(eps)
        result = list_recent_episodes(es, limit=10)
        self.assertEqual(len(result), 2)

    def test_respects_limit(self):
        from core.agent_tools.memory_view import list_recent_episodes

        eps = [{"id": f"ep-{i}"} for i in range(20)]
        es = _stub_episode_store(eps)
        result = list_recent_episodes(es, limit=5)
        self.assertEqual(len(result), 5)


# ── search_memories ─────────────────────────────────────────────────


class TestSearchMemories(unittest.TestCase):
    def test_token_overlap_matches(self):
        """Search returns memories whose content shares query
        tokens (consistent with lived_recall's tokeniser)."""
        from core.agent_tools.memory_view import search_memories

        cores = [
            {"id": "core-cont", "content": "rohit cares about continuity",
             "metadata": {}},
            {"id": "core-other",
             "content": "completely unrelated topic about plumbing",
             "metadata": {}},
        ]
        mm = _stub_memory_manager(core_data=cores)
        mm.get_recent_daily.return_value = []
        mm.recent_raw.return_value = {"results": []}
        results = search_memories(mm, query="continuity matters", limit=5)
        ids = [r["id"] for r in results]
        self.assertIn("core-cont", ids)
        # Unrelated is ranked lower or excluded.
        if "core-other" in ids:
            self.assertGreater(
                ids.index("core-other"), ids.index("core-cont"),
                "matching memory must outrank unrelated one",
            )

    def test_empty_query_returns_empty(self):
        from core.agent_tools.memory_view import search_memories

        mm = _stub_memory_manager(core_data=[
            {"id": "core-1", "content": "anything", "metadata": {}},
        ])
        mm.get_recent_daily.return_value = []
        mm.recent_raw.return_value = {"results": []}
        self.assertEqual(search_memories(mm, query="", limit=5), [])
        self.assertEqual(search_memories(mm, query="   ", limit=5), [])


# ── summary text (for prompt injection) ─────────────────────────────


class TestSummarizeForPrompt(unittest.TestCase):
    """A compact summary the brain loop or CLI can drop into a
    context block to give the model self-awareness of its own
    memory state. One short paragraph; bounded length."""

    def test_summary_includes_counts(self):
        from core.agent_tools.memory_view import summarize_for_prompt

        mm = _stub_memory_manager(raw_count=200, daily_count=40, core_count=15)
        es = _stub_episode_store([{"id": f"ep-{i}"} for i in range(8)])
        summary = summarize_for_prompt(mm, es)
        self.assertIn("200", summary)
        self.assertIn("15", summary)
        self.assertIn("40", summary)
        self.assertIn("8", summary)

    def test_summary_is_bounded(self):
        from core.agent_tools.memory_view import summarize_for_prompt

        mm = _stub_memory_manager()
        es = _stub_episode_store([])
        summary = summarize_for_prompt(mm, es)
        # Compact — fits in a small context block.
        self.assertLess(len(summary), 800)


class TestSliceSevenAuditFixes(unittest.TestCase):
    """Regressions for findings raised by the parallel-audit pass."""

    def test_search_excludes_fabricated_integrity(self):
        """search_memories must honour MemoryManager's integrity
        exclusion list — fabricated/stale/historical entries never
        resurface."""
        from core.agent_tools.memory_view import search_memories

        cores = [
            {"id": "core-clean", "content": "rohit cares about continuity",
             "metadata": {}},
            {"id": "core-fab", "content": "rohit cares about continuity",
             "metadata": {"integrity": "fabricated"}},
            {"id": "core-hist", "content": "rohit cares about continuity",
             "metadata": {"integrity": "historical_artifact"}},
        ]
        mm = _stub_memory_manager(core_data=cores)
        ids = [r["id"] for r in search_memories(mm, query="continuity",
                                                limit=10)]
        self.assertIn("core-clean", ids)
        self.assertNotIn("core-fab", ids)
        self.assertNotIn("core-hist", ids)

    def test_recent_core_tie_breaker_is_stable(self):
        """Two cores sharing a timestamp must produce a deterministic
        order across runs (id-based tiebreak)."""
        from core.agent_tools.memory_view import list_recent_core

        cores = [
            {"id": "core-a", "content": "x",
             "metadata": {"timestamp": "2026-04-01T00:00:00+00:00"}},
            {"id": "core-b", "content": "y",
             "metadata": {"timestamp": "2026-04-01T00:00:00+00:00"}},
        ]
        mm = _stub_memory_manager(core_data=cores)
        first = [m["id"] for m in list_recent_core(mm, limit=2)]
        # Second pass on the same data — must match.
        second = [m["id"] for m in list_recent_core(mm, limit=2)]
        self.assertEqual(first, second)

    def test_summary_handles_fully_empty_store(self):
        """0 raw / 0 daily / 0 core / 0 episodes should still
        produce a valid one-line summary."""
        from core.agent_tools.memory_view import summarize_for_prompt

        mm = _stub_memory_manager(raw_count=0, daily_count=0, core_count=0)
        es = _stub_episode_store([])
        out = summarize_for_prompt(mm, es)
        self.assertTrue(out.startswith("Memory state:"))

    def test_search_zero_overlap_returns_empty(self):
        from core.agent_tools.memory_view import search_memories

        mm = _stub_memory_manager(core_data=[
            {"id": "c1", "content": "alpha beta gamma", "metadata": {}},
        ])
        self.assertEqual(
            search_memories(mm, query="zzz qqq", limit=10),
            [],
        )

    def test_search_pulls_from_daily_branch(self):
        """daily entries must be searchable, not just core."""
        from core.agent_tools.memory_view import search_memories

        mm = _stub_memory_manager(core_data=[])
        mm.get_recent_daily.return_value = [
            {"id": "daily-1", "content": "continuity matters here",
             "metadata": {}},
        ]
        ids = [r["id"] for r in search_memories(mm, query="continuity",
                                                limit=5)]
        self.assertIn("daily-1", ids)


if __name__ == "__main__":
    unittest.main()
