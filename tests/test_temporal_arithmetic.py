# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for temporal arithmetic at recall (Step 5c — first real
implementation of the capability acquisition pipeline).

Hard contract: this module annotates recall items with relative-time
phrases ONLY when the surrounding question is temporal-shaped. It
must not mutate ranking, storage, or non-temporal recall.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── classifier ────────────────────────────────────────────────────


class TestIsTemporalQuestion(unittest.TestCase):
    def test_when_did_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(is_temporal_question("when did Maya start school?"))

    def test_how_long_after_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(
            is_temporal_question("how long after the move did we talk?")
        )

    def test_how_long_ago_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(is_temporal_question("how long ago was that?"))

    def test_how_recent_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(is_temporal_question("how recent is the change?"))

    def test_since_in_question_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(
            is_temporal_question("what's happened since the move?")
        )

    def test_before_in_question_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(
            is_temporal_question("what did I say before the move?")
        )

    def test_after_in_question_is_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertTrue(
            is_temporal_question("what came after the move?")
        )

    def test_normal_memory_question_is_not_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertFalse(
            is_temporal_question("what do I think about Maya?")
        )

    def test_relationship_question_is_not_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertFalse(is_temporal_question("what do I care about?"))

    def test_bare_after_in_statement_not_temporal(self):
        """'after lunch I went home' — not a question, not temporal."""
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertFalse(
            is_temporal_question("after lunch I went home"),
        )

    def test_empty_string_not_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertFalse(is_temporal_question(""))

    def test_none_not_temporal(self):
        from core.memory.temporal_arithmetic import is_temporal_question
        self.assertFalse(is_temporal_question(None))  # type: ignore[arg-type]


# ── relative_time_phrase ──────────────────────────────────────────


class TestRelativeTimePhrase(unittest.TestCase):
    REF = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    def test_one_day_before(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF - timedelta(days=1)
        self.assertEqual(
            relative_time_phrase(ev, self.REF),
            "1 day before question",
        )

    def test_eighteen_days_before(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF - timedelta(days=18)
        self.assertEqual(
            relative_time_phrase(ev, self.REF),
            "about 18 days before question",
        )

    def test_three_weeks_before(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF - timedelta(days=21)
        out = relative_time_phrase(ev, self.REF)
        # We want a "weeks" phrasing somewhere in the 14–60 day band.
        self.assertIn("week", out)
        self.assertIn("before question", out)

    def test_about_two_months_before(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF - timedelta(days=63)
        out = relative_time_phrase(ev, self.REF)
        self.assertIn("month", out)
        self.assertIn("before question", out)

    def test_about_two_years_before(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF - timedelta(days=730)
        out = relative_time_phrase(ev, self.REF)
        self.assertIn("year", out)
        self.assertIn("before question", out)

    def test_same_day(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF.replace(hour=8)
        out = relative_time_phrase(ev, self.REF)
        self.assertIn("same day", out)

    def test_event_after_reference(self):
        from core.memory.temporal_arithmetic import relative_time_phrase
        ev = self.REF + timedelta(days=5)
        out = relative_time_phrase(ev, self.REF)
        # "after question" rather than "before question"
        self.assertIn("after question", out)
        self.assertNotIn("before question", out)


# ── annotate_recall_item ──────────────────────────────────────────


class TestAnnotateRecallItem(unittest.TestCase):
    REF = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    def test_appends_iso_date_and_relative_phrase(self):
        from core.memory.temporal_arithmetic import annotate_recall_item
        ev = datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
        out = annotate_recall_item(
            "- Past episode: Maya started school", ev, self.REF,
        )
        self.assertIn("2026-04-12", out)
        self.assertIn("18 days before question", out)
        self.assertTrue(out.startswith("- Past episode: Maya started school"))

    def test_uses_supplied_reference_time_not_walltime(self):
        from core.memory.temporal_arithmetic import annotate_recall_item
        ev = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ref = datetime(2025, 1, 11, tzinfo=timezone.utc)
        out = annotate_recall_item("text", ev, ref)
        self.assertIn("10 days before question", out)
        # Wall clock would say "many months/years before"; ensure not.
        self.assertNotIn("year", out)
        self.assertNotIn("month", out)

    def test_naive_datetimes_assumed_utc(self):
        """Naive datetime inputs should be treated as UTC (the
        episode store stores ISO timestamps with explicit UTC)."""
        from core.memory.temporal_arithmetic import annotate_recall_item
        ev = datetime(2026, 4, 12, 9, 0)
        ref = datetime(2026, 4, 30, 12, 0)
        out = annotate_recall_item("text", ev, ref)
        self.assertIn("18 days before question", out)


# ── annotate_recall_items ─────────────────────────────────────────


def _items():
    return [
        {
            "text": "- Past episode: Maya started school",
            "event_time": datetime(
                2026, 4, 12, 9, 0, tzinfo=timezone.utc,
            ),
        },
        {
            "text": "- Past episode: dad health update",
            "event_time": datetime(
                2026, 1, 15, 9, 0, tzinfo=timezone.utc,
            ),
        },
    ]


class TestAnnotateRecallItems(unittest.TestCase):
    REF = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    def test_temporal_question_annotates_dated_items(self):
        from core.memory.temporal_arithmetic import annotate_recall_items
        out = annotate_recall_items(
            _items(),
            "when did Maya start school?",
            reference_time=self.REF,
        )
        self.assertEqual(len(out), 2)
        self.assertIn("18 days before question", out[0]["text"])
        self.assertIn("2026-04-12", out[0]["text"])

    def test_non_temporal_question_leaves_items_unchanged(self):
        from core.memory.temporal_arithmetic import annotate_recall_items
        items = _items()
        before = [dict(it) for it in items]
        out = annotate_recall_items(
            items,
            "what do I think about Maya?",
            reference_time=self.REF,
        )
        self.assertEqual(out, before)

    def test_missing_event_time_leaves_item_unchanged(self):
        from core.memory.temporal_arithmetic import annotate_recall_items
        items = [
            {"text": "- Open loop: pending discussion", "event_time": None},
            _items()[0],
        ]
        out = annotate_recall_items(
            items, "when did this happen?", reference_time=self.REF,
        )
        self.assertEqual(out[0]["text"], "- Open loop: pending discussion")
        self.assertIn("18 days before question", out[1]["text"])

    def test_unparseable_event_time_string_leaves_unchanged(self):
        from core.memory.temporal_arithmetic import annotate_recall_items
        out = annotate_recall_items(
            [{"text": "x", "event_time": "definitely not a timestamp"}],
            "when did x?",
            reference_time=self.REF,
        )
        self.assertEqual(out[0]["text"], "x")

    def test_iso_string_event_time_parses(self):
        from core.memory.temporal_arithmetic import annotate_recall_items
        out = annotate_recall_items(
            [{"text": "x", "event_time": "2026-04-12T09:00:00+00:00"}],
            "when did x?",
            reference_time=self.REF,
        )
        self.assertIn("18 days before question", out[0]["text"])

    def test_default_reference_time_is_utc_now(self):
        """When reference_time is None, the boundary defaults to
        ``datetime.now(timezone.utc)``. Smoke check: annotation
        should not crash and should reference the supplied event."""
        from core.memory.temporal_arithmetic import annotate_recall_items
        ev = datetime.now(timezone.utc) - timedelta(days=3)
        out = annotate_recall_items(
            [{"text": "x", "event_time": ev}],
            "when did x?",
        )
        self.assertIn("before question", out[0]["text"])

    def test_returns_new_list_does_not_mutate_input(self):
        from core.memory.temporal_arithmetic import annotate_recall_items
        items = _items()
        snapshot = [dict(it) for it in items]
        annotate_recall_items(
            items, "when did Maya start?", reference_time=self.REF,
        )
        self.assertEqual(items, snapshot)


# ── lived recall integration ──────────────────────────────────────


class TestLivedRecallTemporalAnnotation(unittest.TestCase):
    """Integration: build_lived_recall_brief should annotate
    past-episode lines with relative time when the query is
    temporal-shaped (per is_temporal_question)."""

    def _setup(self):
        import tempfile
        from core.memory.episodes import EpisodeStore
        from core.memory.relationship_graph import RelationshipGraph

        td = tempfile.mkdtemp()
        ep_store = EpisodeStore(Path(td) / "episodes.db")
        graph = RelationshipGraph(Path(td) / "graph.db")
        return ep_store, graph

    def test_brief_annotates_past_episodes_for_temporal_query(self):
        from core.memory.lived_recall import build_lived_recall_brief

        ep_store, graph = self._setup()
        ev = datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
        ep_store.add(
            title="Maya started school",
            summary="we discussed Maya starting at the new school",
            participants=["rohit"],
            source_kind="conversation",
            source_memory_ids=["mem-1"],
            occurred_at=ev.isoformat(),
        )
        ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
        brief = build_lived_recall_brief(
            "when did Maya start school?",
            episode_store=ep_store,
            graph=graph,
            reference_time=ref,
        )
        self.assertIn("Maya started school", brief)
        self.assertIn("2026-04-12", brief)
        self.assertIn("18 days before question", brief)

    def test_brief_does_not_annotate_non_temporal_query(self):
        from core.memory.lived_recall import build_lived_recall_brief

        ep_store, graph = self._setup()
        ev = datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
        ep_store.add(
            title="Maya started school",
            summary="we discussed Maya starting at the new school",
            participants=["rohit"],
            source_kind="conversation",
            source_memory_ids=["mem-1"],
            occurred_at=ev.isoformat(),
        )
        ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
        brief = build_lived_recall_brief(
            "what do I think about Maya school?",
            episode_store=ep_store,
            graph=graph,
            reference_time=ref,
        )
        self.assertIn("Maya started school", brief)
        self.assertNotIn("before question", brief)
        self.assertNotIn("[time:", brief)


if __name__ == "__main__":
    unittest.main()
