# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for memory.memory_manager.format_for_prompt — age-relative framing.

Contract (2026-04-21): on top of the retrieval-truth attribution contract,
recalled entries must also be prefixed with age-relative language so the LLM
cannot mistake stored content as live. The block opens with a PAST
OBSERVATIONS header making the past-ness explicit at the first token.
"""

import os
import re
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory_manager import MemoryManager  # noqa: E402


def _mm():
    # format_for_prompt is a pure method over `recalled` — we don't need
    # a real DB. Instantiate without calling __init__ to avoid spinning
    # up chroma collections.
    return MemoryManager.__new__(MemoryManager)


class _RecallCollection:
    def __init__(self):
        self._rows = []

    def add(self, *, ids, documents, metadatas):
        for mem_id, doc, meta in zip(ids, documents, metadatas, strict=False):
            self._rows.append({
                "id": mem_id,
                "document": doc,
                "metadata": dict(meta or {}),
            })

    def count(self):
        return len(self._rows)

    def get(self, ids=None, include=None, limit=None, where=None):
        rows = list(self._rows)
        if ids is not None:
            wanted = set(ids)
            rows = [row for row in rows if row["id"] in wanted]
        if where:
            rows = [
                row for row in rows
                if all(row["metadata"].get(k) == v for k, v in where.items())
            ]
        if limit is not None:
            rows = rows[:limit]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["document"] for row in rows],
            "metadatas": [dict(row["metadata"]) for row in rows],
        }

    def query(self, *, query_texts, n_results):
        query = (query_texts[0] if query_texts else "").lower()
        terms = {term for term in re.findall(r"[a-z0-9]+", query) if len(term) > 2}

        def distance(row):
            content = row["document"].lower()
            hits = sum(1 for term in terms if term in content)
            return 1.0 - min(0.9, hits * 0.2)

        rows = sorted(self._rows, key=distance)[:n_results]
        return {
            "ids": [[row["id"] for row in rows]],
            "documents": [[row["document"] for row in rows]],
            "metadatas": [[dict(row["metadata"]) for row in rows]],
            "distances": [[distance(row) for row in rows]],
        }


def _temp_memory_manager():
    mm = MemoryManager.__new__(MemoryManager)
    mm.core = _RecallCollection()
    mm.daily = _RecallCollection()
    mm.raw = _RecallCollection()
    return mm


class FormatForPromptAgeFramingTests(unittest.TestCase):
    def test_format_for_prompt_prefixes_age_relative(self):
        mm = _mm()
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                {
                    "id": "raw-a",
                    "content": "cpu temperature spiked to 82C",
                    "metadata": {
                        "timestamp": two_hours_ago.isoformat(),
                        "cycle": 42,
                    },
                }
            ],
        }
        out = mm.format_for_prompt(recalled)
        self.assertTrue(
            "2 hours ago" in out or "2h ago" in out,
            f"expected age-relative '2 hours ago' or '2h ago' in output; got:\n{out}",
        )

    def test_format_for_prompt_has_past_framing_header(self):
        mm = _mm()
        recalled = {
            "core": [{"id": "c1", "content": "i am Maez"}],
            "daily": [],
            "raw": [],
        }
        out = mm.format_for_prompt(recalled)
        self.assertIn("PAST OBSERVATIONS", out)
        # Header must appear near the top (before the content)
        self.assertLess(out.index("PAST OBSERVATIONS"), out.index("i am Maez"))

    def test_format_for_prompt_handles_missing_timestamp(self):
        mm = _mm()
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                {
                    "id": "raw-notime",
                    "content": "something happened",
                    "metadata": {"cycle": 7},  # no timestamp
                }
            ],
        }
        # Must not raise
        out = mm.format_for_prompt(recalled)
        self.assertTrue(
            "earlier" in out.lower() or "previously" in out.lower(),
            f"expected fallback 'earlier'/'previously' for missing timestamp; got:\n{out}",
        )

    def test_format_for_prompt_handles_empty_recalled(self):
        mm = _mm()
        out = mm.format_for_prompt({"core": [], "daily": [], "raw": []})
        self.assertEqual(out, "")

    def test_format_for_prompt_handles_unix_float_timestamp(self):
        mm = _mm()
        ts = time.time() - (3 * 24 * 3600)  # 3 days ago
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                {
                    "id": "raw-b",
                    "content": "disk usage at 91%",
                    "metadata": {"timestamp": ts, "cycle": 100},
                }
            ],
        }
        out = mm.format_for_prompt(recalled)
        self.assertTrue(
            "3 days ago" in out or "3d ago" in out,
            f"expected '3 days ago' or '3d ago' for unix-float ts; got:\n{out}",
        )


class AbsoluteDateWindowTests(unittest.TestCase):
    def _now(self):
        from datetime import datetime

        from core.time.temporal_spine import owner_timezone

        # Fixed owner-local "today" = 2026-05-30 for determinism.
        return datetime(2026, 5, 30, 12, 0, tzinfo=owner_timezone())

    def test_exact_date_named_month_day(self):
        from memory.memory_manager import _absolute_date_window

        w = _absolute_date_window(
            "what did we note around April 6 about infra?",
            self._now(),
        )
        self.assertIsNotNone(w)
        assert w is not None
        self.assertEqual(w.method, "exact_date")
        # "around" uses symmetric tolerance; April 6 includes April 4..8.
        self.assertLessEqual(w.start_utc.date().isoformat(), "2026-04-04")
        self.assertGreaterEqual(w.end_utc.date().isoformat(), "2026-04-08")
        self.assertIn("April", w.label)

    def test_exact_iso_date_forward_tolerance_only(self):
        from memory.memory_manager import _absolute_date_window

        w = _absolute_date_window("2026-04-06 infra note", self._now())
        self.assertIsNotNone(w)
        assert w is not None
        self.assertEqual(w.method, "exact_date")
        # Plain date starts on the owner-local day and extends forward for the
        # next-morning nightly journal; it does not widen backward.
        self.assertEqual(w.start_utc.date().isoformat(), "2026-04-06")
        self.assertGreaterEqual(w.end_utc.date().isoformat(), "2026-04-08")

    def test_month_window_last_month(self):
        from memory.memory_manager import _absolute_date_window

        w = _absolute_date_window("what were we working on last month?", self._now())
        self.assertIsNotNone(w)
        assert w is not None
        self.assertEqual(w.method, "month_window")
        self.assertEqual(w.start_utc.date().isoformat(), "2026-04-01")

    def test_bare_may_is_not_a_month_cue(self):
        from memory.memory_manager import _absolute_date_window

        self.assertIsNone(
            _absolute_date_window("maybe we should check the logs", self._now())
        )
        self.assertIsNone(
            _absolute_date_window("you may have noted something", self._now())
        )
        self.assertIsNotNone(_absolute_date_window("what about May 6?", self._now()))
        self.assertIsNotNone(
            _absolute_date_window("anything in May 2026?", self._now())
        )

    def test_no_temporal_cue_returns_none(self):
        from memory.memory_manager import _absolute_date_window

        self.assertIsNone(
            _absolute_date_window(
                "what's the infra ground-truth you noted earlier?",
                self._now(),
            )
        )
        self.assertIsNone(_absolute_date_window("how are you?", self._now()))


class AbsoluteDateRecallTests(unittest.TestCase):
    def _mm_with_dated_core(self):
        mm = _temp_memory_manager()
        mm.core.add(
            ids=["c_apr6"],
            documents=["[Journal] infrastructure ground-truth fabrication-class incident"],
            metadatas=[{
                "type": "core_memory",
                "source": "nightly_journal",
                "timestamp": "2026-04-07T04:00:02+00:00",
            }],
        )
        mm.core.add(
            ids=["c_may"],
            documents=["[Journal] May progress on living recall"],
            metadatas=[{
                "type": "core_memory",
                "source": "nightly_journal",
                "timestamp": "2026-05-20T04:00:00+00:00",
            }],
        )
        return mm

    def test_april_date_ask_surfaces_april_row_labeled(self):
        mm = self._mm_with_dated_core()
        ev, ctx = mm.recall_for_telegram_living(
            "what did we note around April 6 about the infrastructure?",
            record_recalls=False,
        )
        core_text = " ".join(m.get("content", "") for m in (ctx.get("core") or []))
        self.assertIn("fabrication-class", core_text)
        self.assertNotIn("May progress", core_text)
        apr = [m for m in ctx["core"] if "fabrication" in m.get("content", "")][0]
        self.assertEqual(apr["metadata"]["temporal_match_method"], "exact_date")
        self.assertTrue(apr["metadata"]["date_confirmed"])
        self.assertEqual(ev.get("core"), [])
        ev_all = " ".join(
            m.get("content", "")
            for tier in ("core", "daily", "raw")
            for m in (ev.get(tier) or [])
        )
        self.assertNotIn("fabrication-class", ev_all)

    def test_persisted_chroma_metadata_not_mutated(self):
        mm = self._mm_with_dated_core()
        mm.recall_for_telegram_living(
            "around April 6 infra",
            record_recalls=False,
            half_life_days=90,
            evidence_recency_days=14,
        )
        raw = mm.core.get(ids=["c_apr6"], include=["metadatas"])["metadatas"][0]
        self.assertNotIn("temporal_match_method", raw)

    def test_date_only_no_memory_returns_no_recall(self):
        mm = self._mm_with_dated_core()
        ev, ctx = mm.recall_for_telegram_living(
            "what about January 3?",
            record_recalls=False,
        )
        self.assertEqual(ctx.get("core"), [])
        self.assertEqual(ctx.get("daily"), [])
        self.assertEqual(ev.get("core"), [])

    def test_empty_window_with_topic_is_semantic_fallback_labeled(self):
        mm = self._mm_with_dated_core()
        ev, ctx = mm.recall_for_telegram_living(
            "what about the infrastructure on January 3?",
            record_recalls=False,
        )
        self.assertEqual(ev.get("core"), [])
        rows = (ctx.get("core") or []) + (ctx.get("daily") or [])
        if rows:
            self.assertTrue(
                any(
                    r["metadata"].get("temporal_match_method")
                    == "semantic_fallback"
                    for r in rows
                )
            )
            self.assertFalse(
                any(r["metadata"].get("date_confirmed") for r in rows)
            )


class FormatForPromptBudgetTests(unittest.TestCase):
    """`max_chars` parameter — drops raw RECALLED blocks from the
    tail until the assembled block fits the budget. Core + daily are
    never dropped (they are the always-injected anchor layer).

    Closes the 2026-04-28 incident where a TRELLIS-shaped query
    produced a 23K-token recall block; combined with sys_prompt and
    Phase-6 lived brief, the request exceeded llama-server's 32K ctx
    and the daemon's /message endpoint returned a 400 instead of a
    reply.
    """

    def _big_raw(self, n: int) -> list:
        ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        return [
            {
                "id": f"raw-{i:03d}",
                "content": "x" * 1000,  # 1KB body each
                "metadata": {"timestamp": ts, "cycle": i},
            }
            for i in range(n)
        ]

    def test_default_no_cap_preserves_all_entries(self):
        mm = _mm()
        recalled = {"core": [], "daily": [], "raw": self._big_raw(20)}
        out = mm.format_for_prompt(recalled)
        for i in range(20):
            self.assertIn(f"raw-{i:03d}", out)
        self.assertNotIn("truncated", out)

    def test_max_chars_drops_raw_tail(self):
        mm = _mm()
        recalled = {"core": [], "daily": [], "raw": self._big_raw(20)}
        out = mm.format_for_prompt(recalled, max_chars=8000)
        self.assertLessEqual(len(out), 8000 + 200)  # +slack for truncation marker
        self.assertIn("truncated", out)
        # Earlier entries (top of the raw list) must survive.
        self.assertIn("raw-000", out)
        # Tail entries must have been dropped.
        self.assertNotIn("raw-019", out)

    def test_max_chars_preserves_core_even_when_tight(self):
        mm = _mm()
        recalled = {
            "core": [{"id": "core-canonical", "content": "I am Maez."}],
            "daily": [],
            "raw": self._big_raw(20),
        }
        out = mm.format_for_prompt(recalled, max_chars=4000)
        self.assertIn("core-canonical", out)
        self.assertIn("I am Maez.", out)

    def test_max_chars_keeps_end_observations_marker(self):
        mm = _mm()
        recalled = {"core": [], "daily": [], "raw": self._big_raw(20)}
        out = mm.format_for_prompt(recalled, max_chars=8000)
        # Both opening header and closing footer must remain so the
        # model still treats the block as past-tense scoped.
        self.assertIn("PAST OBSERVATIONS", out)
        self.assertIn("END PAST OBSERVATIONS", out)


class RedditSourceAwareRecallTests(unittest.TestCase):
    """Reply-path recall should open Maez's own Reddit notebook when
    the owner asks a Reddit-shaped question.

    This is retrieval ranking, not substrate writing: Reddit rows are
    already persisted with source=reddit/r/<sub>. The conversational
    path must prefer recent source-matched rows when the query names
    Reddit / a subreddit, without making Reddit globally dominate
    generic LLM questions.
    """

    class _FakeCore:
        def count(self):
            return 0

    class _FakeDaily:
        def count(self):
            return 0

    class _FakeRaw:
        def __init__(self, rows, get_rows=None):
            self._rows = rows
            self._get_rows = get_rows or rows

        def count(self):
            return max(len(self._rows), len(self._get_rows))

        def query(self, query_texts, n_results):
            rows = self._rows[:n_results]
            return {
                "ids": [[r["id"] for r in rows]],
                "documents": [[r["content"] for r in rows]],
                "metadatas": [[r["metadata"] for r in rows]],
                "distances": [[r["distance"] for r in rows]],
            }

        def get(self, where=None, include=None, limit=None):
            rows = self._get_rows
            if where:
                rows = [
                    r for r in rows
                    if all(r["metadata"].get(k) == v for k, v in where.items())
                ]
            if limit is not None:
                rows = rows[:limit]
            return {
                "ids": [r["id"] for r in rows],
                "documents": [r["content"] for r in rows],
                "metadatas": [r["metadata"] for r in rows],
            }

    def _manager_with_raw(self, rows, get_rows=None):
        mm = _mm()
        mm.core = self._FakeCore()
        mm.daily = self._FakeDaily()
        mm.raw = self._FakeRaw(rows, get_rows=get_rows)
        return mm

    def test_reddit_specific_query_prefers_recent_matching_subreddit_row(self):
        now = datetime.now(timezone.utc)
        mm = self._manager_with_raw([
            {
                "id": "generic-close",
                "content": "A generic web note about local LLM model releases.",
                "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                "distance": 0.10,
            },
            {
                "id": "reddit-local",
                "content": "[REDDIT r/LocalLLaMA post abc] Qwen local inference discussion",
                "metadata": {
                    "timestamp": now.isoformat(),
                    "type": "reddit_post",
                    "source": "reddit/r/LocalLLaMA",
                    "reddit_post_id": "abc",
                },
                "distance": 0.45,
            },
        ])

        with mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]):
            recalled = mm.recall_for_telegram("what is happening in local LLMs on Reddit?")

        self.assertEqual(recalled["raw"][0]["id"], "reddit-local")
        self.assertEqual(
            recalled["raw"][0]["metadata"].get("source"),
            "reddit/r/LocalLLaMA",
        )

    def test_generic_llm_query_does_not_make_reddit_win_automatically(self):
        now = datetime.now(timezone.utc)
        mm = self._manager_with_raw([
            {
                "id": "generic-close",
                "content": "A generic technical note about local LLM model releases.",
                "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                "distance": 0.10,
            },
            {
                "id": "reddit-local",
                "content": "[REDDIT r/LocalLLaMA post abc] Qwen local inference discussion",
                "metadata": {
                    "timestamp": now.isoformat(),
                    "type": "reddit_post",
                    "source": "reddit/r/LocalLLaMA",
                    "reddit_post_id": "abc",
                },
                "distance": 0.45,
            },
        ])

        with mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]):
            recalled = mm.recall_for_telegram("what is new in local LLMs?")

        self.assertEqual(recalled["raw"][0]["id"], "generic-close")

    def test_reddit_specific_query_supplements_recent_source_rows_missed_by_vector_search(self):
        now = datetime.now(timezone.utc)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-close",
                    "content": "A generic web note about local LLM model releases.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.10,
                },
            ],
            get_rows=[
                {
                    "id": "reddit-local",
                    "content": "[REDDIT r/LocalLLaMA post abc] Qwen local inference discussion",
                    "metadata": {
                        "timestamp": now.isoformat(),
                        "type": "reddit_post",
                        "source": "reddit/r/LocalLLaMA",
                        "reddit_post_id": "abc",
                    },
                    "distance": 0.45,
                },
            ],
        )

        with mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]):
            recalled = mm.recall_for_telegram("what is happening in local LLMs on Reddit?")

        self.assertEqual(recalled["raw"][0]["id"], "reddit-local")

    def test_reddit_source_supplement_sorts_before_truncating_old_chroma_rows(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=14)
        old_rows = [
            {
                "id": f"old-{i}",
                "content": f"[REDDIT r/LocalLLaMA post old{i}] old discussion",
                "metadata": {
                    "timestamp": old.isoformat(),
                    "type": "reddit_post",
                    "source": "reddit/r/LocalLLaMA",
                    "reddit_post_id": f"old{i}",
                },
                "distance": 0.20,
            }
            for i in range(101)
        ]
        fresh = {
            "id": "fresh-reddit-local",
            "content": "[REDDIT r/LocalLLaMA post fresh] fresh local inference discussion",
            "metadata": {
                "timestamp": now.isoformat(),
                "type": "reddit_post",
                "source": "reddit/r/LocalLLaMA",
                "reddit_post_id": "fresh",
            },
            "distance": 0.45,
        }
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-close",
                    "content": "A generic web note about local LLM model releases.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.10,
                },
            ],
            get_rows=old_rows + [fresh],
        )

        with mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]):
            recalled = mm.recall_for_telegram("what is happening in local LLMs on Reddit?")

        self.assertEqual(recalled["raw"][0]["id"], "fresh-reddit-local")

    def test_last_evening_query_supplements_recent_telegram_exchanges(self):
        now = datetime(2026, 5, 26, 18, 50, tzinfo=timezone.utc)
        last_evening = now - timedelta(hours=14)
        this_morning = now - timedelta(hours=3)
        too_old = now - timedelta(hours=30)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-remember",
                    "content": "A generic note about remembering old conversations.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-this-morning",
                    "content": "the owner (telegram_surface): Morning Maez\nMaez: Morning.",
                    "metadata": {
                        "timestamp": this_morning.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-last-evening",
                    "content": (
                        "the owner (telegram_surface): How's the Reddit community doing?\n"
                        "Maez: The Reddit pipeline is currently silent."
                    ),
                    "metadata": {
                        "timestamp": last_evening.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-too-old",
                    "content": "the owner (telegram_surface): older unrelated exchange",
                    "metadata": {
                        "timestamp": too_old.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("You remember what I was talking last evening?")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-evening")
        self.assertNotIn(
            "telegram-this-morning",
            [row["id"] for row in recalled["raw"][:3]],
        )
        self.assertNotIn("telegram-too-old", [row["id"] for row in recalled["raw"]])

    def test_reddit_last_night_query_prefers_conversation_over_reddit_posts(self):
        now = datetime(2026, 5, 26, 18, 50, tzinfo=timezone.utc)
        last_night = now - timedelta(hours=14)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-close",
                    "content": "A generic note about Reddit.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "fresh-reddit-post",
                    "content": "[REDDIT r/LocalLLaMA post abc] fresh model discussion",
                    "metadata": {
                        "timestamp": now.isoformat(),
                        "type": "reddit_post",
                        "source": "reddit/r/LocalLLaMA",
                        "reddit_post_id": "abc",
                    },
                    "distance": 0.45,
                },
                {
                    "id": "telegram-last-night",
                    "content": (
                        "the owner (telegram_surface): How's the Reddit community doing?\n"
                        "Maez: The Reddit pipeline is currently silent."
                    ),
                    "metadata": {
                        "timestamp": last_night.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("What did I ask you about Reddit last night?")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-night")
        self.assertIn("fresh-reddit-post", [row["id"] for row in recalled["raw"]])

    def test_temporal_followup_inherits_recent_temporal_question(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        last_night = now - timedelta(hours=15)
        previous_question = now - timedelta(minutes=18)
        previous_followup = now - timedelta(minutes=1)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-check-again",
                    "content": "No anomalies detected.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-previous-followup",
                    "content": (
                        "the owner (telegram_surface): You sure?\n"
                        "Maez: No. I don't have a record of last evening."
                    ),
                    "metadata": {
                        "timestamp": previous_followup.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-previous-temporal-question",
                    "content": (
                        "the owner (telegram_surface): You remember what I was talking last evening?\n"
                        "Maez: I don't have a record of our conversation from last evening."
                    ),
                    "metadata": {
                        "timestamp": previous_question.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-last-night",
                    "content": (
                        "the owner (telegram_surface): How's the Reddit community doing?\n"
                        "Maez: The Reddit pipeline is currently silent."
                    ),
                    "metadata": {
                        "timestamp": last_night.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("Check again")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-night")
        self.assertNotIn(
            "telegram-previous-followup",
            [row["id"] for row in recalled["raw"][:3]],
        )

    def test_check_again_without_prior_temporal_question_stays_semantic(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        previous_followup = now - timedelta(minutes=1)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-check-again",
                    "content": "No anomalies detected.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-previous-nontemporal",
                    "content": (
                        "the owner (telegram_surface): How is the system?\n"
                        "Maez: Quiet and stable."
                    ),
                    "metadata": {
                        "timestamp": previous_followup.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("Check again")

        self.assertEqual(recalled["raw"][0]["id"], "generic-check-again")

    def test_this_morning_query_supplements_morning_telegram_exchanges(self):
        now = datetime(2026, 5, 26, 16, 30, tzinfo=timezone.utc)
        this_morning = now - timedelta(hours=8)
        too_old = now - timedelta(hours=20)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-morning",
                    "content": "A generic note about mornings.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-this-morning",
                    "content": (
                        "the owner (telegram_surface): Maez I'm starting the day.\n"
                        "Maez: Good morning, Rohit."
                    ),
                    "metadata": {
                        "timestamp": this_morning.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-too-old",
                    "content": "the owner (telegram_surface): older exchange",
                    "metadata": {
                        "timestamp": too_old.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("What were we talking about this morning?")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-this-morning")
        self.assertNotIn("telegram-too-old", [row["id"] for row in recalled["raw"]])

    def test_earlier_today_query_supplements_today_telegram_exchanges(self):
        now = datetime(2026, 5, 26, 21, 0, tzinfo=timezone.utc)
        earlier_today = now - timedelta(hours=5)
        too_old = now - timedelta(hours=20)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-earlier",
                    "content": "Generic note about earlier discussions.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-earlier-today",
                    "content": (
                        "the owner (telegram_surface): Quick question about the audit.\n"
                        "Maez: Audit is on aa29bb0."
                    ),
                    "metadata": {
                        "timestamp": earlier_today.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-too-old",
                    "content": "the owner (telegram_surface): older exchange",
                    "metadata": {
                        "timestamp": too_old.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("What did we talk about earlier today?")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-earlier-today")
        self.assertNotIn("telegram-too-old", [row["id"] for row in recalled["raw"]])

    def test_yesterday_afternoon_query_supplements_yesterday_afternoon_exchanges(self):
        now = datetime(2026, 5, 26, 14, 0, tzinfo=timezone.utc)
        yesterday_afternoon = now - timedelta(hours=22)
        yesterday_morning = now - timedelta(hours=30)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-yesterday",
                    "content": "Generic note about yesterday.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-yesterday-afternoon",
                    "content": (
                        "the owner (telegram_surface): How did Slice 2 land?\n"
                        "Maez: Slice 2 is live at fbe78e1."
                    ),
                    "metadata": {
                        "timestamp": yesterday_afternoon.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-yesterday-morning",
                    "content": "the owner (telegram_surface): Morning check-in yesterday.",
                    "metadata": {
                        "timestamp": yesterday_morning.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("What did we discuss yesterday afternoon?")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-yesterday-afternoon")
        self.assertNotIn(
            "telegram-yesterday-morning",
            [row["id"] for row in recalled["raw"]],
        )

    def _temporal_followup_setup(self, now, repair_phrase):
        last_night = now - timedelta(hours=15)
        previous_question = now - timedelta(minutes=18)
        previous_followup = now - timedelta(minutes=1)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": f"generic-{repair_phrase.replace(' ', '-').replace(',', '').replace('?', '').strip('-')}",
                    "content": "No anomalies detected.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-previous-followup",
                    "content": (
                        "the owner (telegram_surface): You sure?\n"
                        "Maez: No. I don't have a record of last evening."
                    ),
                    "metadata": {
                        "timestamp": previous_followup.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-previous-temporal-question",
                    "content": (
                        "the owner (telegram_surface): You remember what I was talking last evening?\n"
                        "Maez: I don't have a record of our conversation from last evening."
                    ),
                    "metadata": {
                        "timestamp": previous_question.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-last-night",
                    "content": (
                        "the owner (telegram_surface): How's the Reddit community doing?\n"
                        "Maez: The Reddit pipeline is currently silent."
                    ),
                    "metadata": {
                        "timestamp": last_night.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )
        return mm

    def test_really_inherits_recent_temporal_question(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        mm = self._temporal_followup_setup(now, "really")
        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("Really?")
        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-night")

    def test_are_you_certain_inherits_recent_temporal_question(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        mm = self._temporal_followup_setup(now, "are you certain")
        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("Are you certain?")
        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-night")

    def test_no_thats_not_it_inherits_recent_temporal_question(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        mm = self._temporal_followup_setup(now, "no thats not it")
        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("No, that's not it.")
        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-night")

    def test_go_on_inherits_recent_temporal_question(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        mm = self._temporal_followup_setup(now, "go on")
        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("Go on")
        self.assertEqual(recalled["raw"][0]["id"], "telegram-last-night")

    def test_really_without_prior_temporal_question_stays_semantic(self):
        now = datetime(2026, 5, 26, 19, 8, tzinfo=timezone.utc)
        previous_followup = now - timedelta(minutes=1)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-really",
                    "content": "No anomalies detected.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-previous-nontemporal",
                    "content": (
                        "the owner (telegram_surface): How is the system?\n"
                        "Maez: Quiet and stable."
                    ),
                    "metadata": {
                        "timestamp": previous_followup.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )
        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("Really?")
        self.assertEqual(recalled["raw"][0]["id"], "generic-really")

    def test_two_days_ago_query_supplements_two_day_old_exchanges(self):
        now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
        two_days_ago = now - timedelta(hours=48)
        too_recent = now - timedelta(hours=20)
        mm = self._manager_with_raw(
            rows=[
                {
                    "id": "generic-days",
                    "content": "Generic note.",
                    "metadata": {"timestamp": now.isoformat(), "type": "reasoning"},
                    "distance": 0.08,
                },
            ],
            get_rows=[
                {
                    "id": "telegram-two-days",
                    "content": (
                        "the owner (telegram_surface): The canon refresh discussion.\n"
                        "Maez: Decisions 36-40 minted."
                    ),
                    "metadata": {
                        "timestamp": two_days_ago.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
                {
                    "id": "telegram-too-recent",
                    "content": "the owner (telegram_surface): yesterday's chat",
                    "metadata": {
                        "timestamp": too_recent.isoformat(),
                        "type": "telegram_exchange",
                        "trust_tier": "lived",
                    },
                    "distance": 0.50,
                },
            ],
        )

        with (
            mock.patch("memory.memory_manager._now_seconds", return_value=now.timestamp()),
            mock.patch("memory.mmr.mmr_rerank", side_effect=lambda rows, k, lambda_: rows[:k]),
        ):
            recalled = mm.recall_for_telegram("What did we discuss two days ago?")

        self.assertEqual(recalled["raw"][0]["id"], "telegram-two-days")
        self.assertNotIn(
            "telegram-too-recent",
            [row["id"] for row in recalled["raw"]],
        )


class GetRecentDailyTests(unittest.TestCase):
    """``get_recent_daily(limit)`` was added 2026-04-27 to close the
    silent AttributeError gap in the lived-memory nightly job. Mirror
    of ``get_all_core``'s shape so the builder consumes both with no
    translation. Sort is newest-first by metadata timestamp, falling
    back to the daily-YYYY-MM-DD- id prefix."""

    def _mm_with_fake_daily(self, items):
        """Build a MemoryManager stub whose .daily collection returns
        the supplied items via Chroma's get/count contract."""

        class FakeDaily:
            def __init__(self, rows):
                self._rows = rows

            def count(self):
                return len(self._rows)

            def get(self, include=None):
                return {
                    "ids": [r["id"] for r in self._rows],
                    "documents": [r["content"] for r in self._rows],
                    "metadatas": [r["metadata"] for r in self._rows],
                }

        mm = _mm()
        mm.daily = FakeDaily(items)
        return mm

    def test_empty_collection_returns_empty_list(self):
        mm = self._mm_with_fake_daily([])
        self.assertEqual(mm.get_recent_daily(limit=5), [])

    def test_returns_newest_first_by_timestamp(self):
        items = [
            {
                "id": "daily-2026-04-22-aaa",
                "content": "older",
                "metadata": {"timestamp": "2026-04-22T08:00:00+00:00"},
            },
            {
                "id": "daily-2026-04-26-bbb",
                "content": "newer",
                "metadata": {"timestamp": "2026-04-26T08:00:00+00:00"},
            },
            {
                "id": "daily-2026-04-24-ccc",
                "content": "middle",
                "metadata": {"timestamp": "2026-04-24T08:00:00+00:00"},
            },
        ]
        mm = self._mm_with_fake_daily(items)
        out = mm.get_recent_daily(limit=10)
        self.assertEqual(
            [r["id"] for r in out],
            [
                "daily-2026-04-26-bbb",
                "daily-2026-04-24-ccc",
                "daily-2026-04-22-aaa",
            ],
        )
        self.assertEqual(out[0]["content"], "newer")

    def test_limit_caps_returned_count(self):
        items = [
            {
                "id": f"daily-2026-04-{day:02d}-x",
                "content": f"day {day}",
                "metadata": {"timestamp": f"2026-04-{day:02d}T08:00:00+00:00"},
            }
            for day in range(1, 11)
        ]
        mm = self._mm_with_fake_daily(items)
        self.assertEqual(len(mm.get_recent_daily(limit=3)), 3)

    def test_limit_zero_returns_empty(self):
        items = [
            {
                "id": "daily-2026-04-22-aaa",
                "content": "x",
                "metadata": {"timestamp": "2026-04-22T08:00:00+00:00"},
            }
        ]
        mm = self._mm_with_fake_daily(items)
        self.assertEqual(mm.get_recent_daily(limit=0), [])

    def test_falls_back_to_id_prefix_when_timestamp_missing(self):
        items = [
            {"id": "daily-2026-04-20-x", "content": "older", "metadata": {}},
            {"id": "daily-2026-04-26-x", "content": "newer", "metadata": {}},
        ]
        mm = self._mm_with_fake_daily(items)
        out = mm.get_recent_daily(limit=5)
        self.assertEqual(out[0]["id"], "daily-2026-04-26-x")
        self.assertEqual(out[1]["id"], "daily-2026-04-20-x")

    def test_shape_matches_get_all_core(self):
        items = [
            {
                "id": "daily-2026-04-26-x",
                "content": "summary text",
                "metadata": {"timestamp": "2026-04-26T08:00:00+00:00", "date": "2026-04-26"},
            }
        ]
        mm = self._mm_with_fake_daily(items)
        out = mm.get_recent_daily(limit=5)
        self.assertEqual(len(out), 1)
        row = out[0]
        # Same keys as get_all_core's output: id / content / metadata.
        self.assertEqual(set(row.keys()), {"id", "content", "metadata"})
        self.assertEqual(row["content"], "summary text")
        self.assertEqual(row["metadata"]["date"], "2026-04-26")


if __name__ == "__main__":
    unittest.main()
