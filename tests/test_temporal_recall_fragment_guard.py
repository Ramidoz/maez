# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""TRF tests: temporal-anchor recall + ARS fragment guard.

These tests pin docs/slices/temporal-recall-fragment-guard/spec.md.
They intentionally exercise pure helpers first so daemon wiring stays
thin and auditable.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

CHICAGO = ZoneInfo("America/Chicago")


class _FakeEpisodeStore:
    def __init__(self):
        self.rows: list[dict] = []

    def add_row(self, title: str, occurred_at: str, source_id: str) -> str:
        ep_id = f"ep-{len(self.rows)}"
        self.rows.append(
            {
                "id": ep_id,
                "created_at": occurred_at,
                "occurred_at": occurred_at,
                "title": title,
                "summary": title,
                "source_memory_ids": [source_id],
                "source_kind": "telegram",
                "importance": 3,
                "status": "active",
            }
        )
        return ep_id

    def list_active(self):
        raise AssertionError("TRF daemon-path helper must not scan the full episode store")

    def list_active_in_window(self, *, window_start: str, window_end: str, limit: int, **_kwargs):
        start = datetime.fromisoformat(window_start)
        end = datetime.fromisoformat(window_end)
        rows = []
        for row in self.rows:
            occurred = datetime.fromisoformat(row["occurred_at"])
            if start <= occurred < end:
                rows.append(row)
        return rows[:limit]


class _RecordingEpisodeStore(_FakeEpisodeStore):
    def __init__(self):
        super().__init__()
        self.calls: list[dict] = []

    def list_active_in_window(self, *, window_start: str, window_end: str, limit: int, **kwargs):
        self.calls.append(
            {
                "window_start": window_start,
                "window_end": window_end,
                "limit": limit,
                **kwargs,
            }
        )
        return super().list_active_in_window(
            window_start=window_start,
            window_end=window_end,
            limit=limit,
            **kwargs,
        )


class TemporalAnchorWindowTests(unittest.TestCase):
    def test_last_week_uses_previous_completed_monday_sunday(self):
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        ref = datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO)
        result = detect_temporal_anchor("Do you remember last week?", reference_time=ref)

        self.assertTrue(result.anchor_detected)
        self.assertEqual(result.anchor_kind, "last_week")
        self.assertEqual(result.window_start, datetime(2026, 5, 4, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(result.window_end, datetime(2026, 5, 11, 0, 0, tzinfo=CHICAGO))

    def test_yesterday_uses_local_calendar_day_even_across_dst(self):
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        ref = datetime(2026, 3, 9, 9, 0, tzinfo=CHICAGO)
        result = detect_temporal_anchor("Do you remember yesterday?", reference_time=ref)

        self.assertEqual(result.anchor_kind, "yesterday")
        self.assertEqual(result.window_start, datetime(2026, 3, 8, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(result.window_end, datetime(2026, 3, 9, 0, 0, tzinfo=CHICAGO))

    def test_this_morning_and_earlier_today_windows(self):
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        ref = datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO)

        morning = detect_temporal_anchor("Do you remember this morning?", reference_time=ref)
        self.assertEqual(morning.window_start, datetime(2026, 5, 13, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(morning.window_end, datetime(2026, 5, 13, 12, 0, tzinfo=CHICAGO))

        earlier = detect_temporal_anchor("What happened earlier today?", reference_time=ref)
        self.assertEqual(earlier.window_start, datetime(2026, 5, 13, 0, 0, tzinfo=CHICAGO))
        self.assertEqual(earlier.window_end, ref)

    def test_negative_controls_do_not_activate_without_memory_intent(self):
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        ref = datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO)
        for text in (
            "Last week was exhausting, but I am not asking you to remember it.",
            "The phrase last week appears here as an example, not a memory request.",
            "I am planning for next week, not asking about last week.",
            "I remember last week was hard.",
            "I recall yesterday differently.",
            "Last week still sits weird with me.",
        ):
            result = detect_temporal_anchor(text, reference_time=ref)
            self.assertFalse(result.anchor_detected, text)

    def test_first_person_memory_plus_direct_question_still_activates(self):
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        result = detect_temporal_anchor(
            "I remember last week was hard. Do you remember last week too?",
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )
        self.assertTrue(result.anchor_detected)

    def test_m1_telegram_exchange_uses_structural_summary_not_generic_storage_title(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        store.rows.append(
            {
                "id": "ep-m1",
                "created_at": "2026-05-07T18:00:00+00:00",
                "occurred_at": "2026-05-07T18:00:00+00:00",
                "title": "Bonded conversation with Rohit",
                "summary": (
                    "Bonded Telegram exchange. 1 audited owner/Maez pair at "
                    "2026-05-07T18:00:00+00:00. Participants: Rohit, Maez."
                ),
                "source_memory_ids": ["raw-m1"],
                "source_kind": "telegram_exchange",
                "importance": 3,
                "status": "active",
            }
        )

        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 14, 12, 0, tzinfo=CHICAGO),
        )

        self.assertEqual(result.search_status, "evidence_found")
        self.assertIn("Bonded Telegram exchange.", result.brief_text)
        self.assertNotIn("Bonded conversation with Rohit", result.brief_text)
        self.assertEqual(result.anchor_kind, "last_week")

    def test_trf_passes_utc_store_bounds_not_owner_local_offsets(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _RecordingEpisodeStore()
        store.add_row(
            "Late Sunday UTC, still Chicago last week",
            "2026-05-11T04:30:00+00:00",
            "inside-boundary",
        )
        store.add_row(
            "Exactly at Chicago Monday boundary",
            "2026-05-11T05:00:00+00:00",
            "outside-boundary",
        )

        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )

        self.assertEqual(result.search_status, "evidence_found")
        self.assertEqual(result.evidence_ids, ("ep-0", "inside-boundary"))
        self.assertEqual(store.calls[0]["window_start"], "2026-05-04T05:00:00+00:00")
        self.assertEqual(store.calls[0]["window_end"], "2026-05-11T05:00:00+00:00")
        self.assertNotIn("-05:00", store.calls[0]["window_start"])
        self.assertNotIn("-05:00", store.calls[0]["window_end"])

    def test_temporal_spine_helper_exception_maps_to_helper_unavailable(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief
        from core.time import temporal_spine

        temporal_spine._reset_diagnostics_for_tests()
        store = _FakeEpisodeStore()

        with patch(
            "core.memory.temporal_anchor_recall.temporal_window",
            side_effect=ValueError("synthetic temporal helper failure"),
        ):
            result = build_temporal_anchor_recall_brief(
                "Do you remember yesterday?",
                episode_store=store,
                reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
            )

        self.assertTrue(result.anchor_detected)
        self.assertEqual(result.anchor_kind, "yesterday")
        self.assertIsNone(result.window_start)
        self.assertIsNone(result.window_end)
        self.assertFalse(result.window_searched)
        self.assertEqual(result.search_status, "helper_unavailable")
        self.assertEqual(result.brief_text, "")
        self.assertFalse(result.memory_absence_established)
        self.assertEqual(temporal_spine.diagnostics_snapshot().helper_unavailable_count, 1)


class TemporalAnchorRecallTests(unittest.TestCase):
    def test_episode_store_window_query_filters_in_sql_and_limits(self):
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as tmp:
            store = EpisodeStore(str(Path(tmp) / "episodes.db"))
            for i in range(6):
                store.add(
                    title=f"Last-week stored event {i}",
                    summary=f"Last-week stored event {i}",
                    participants=["Rohit", "Maez"],
                    source_memory_ids=[f"src-real-{i}"],
                    source_kind="telegram",
                    occurred_at=f"2026-05-0{4 + i}T12:00:00-05:00",
                )
            store.add(
                title="Current-week event",
                summary="Current-week event",
                participants=["Rohit", "Maez"],
                source_memory_ids=["src-current"],
                source_kind="telegram",
                occurred_at="2026-05-12T12:00:00-05:00",
            )
            rows = store.list_active_in_window(
                window_start="2026-05-04T00:00:00-05:00",
                window_end="2026-05-11T00:00:00-05:00",
                limit=5,
            )
        self.assertEqual(len(rows), 5)
        self.assertTrue(all("Current-week" not in row["title"] for row in rows))

    def test_episode_store_window_query_filters_mixed_offsets_by_canonical_utc(self):
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as tmp:
            store = EpisodeStore(str(Path(tmp) / "episodes.db"))
            store.add(
                title="Z inside",
                summary="Z inside",
                participants=["Rohit", "Maez"],
                source_memory_ids=["z-inside"],
                source_kind="telegram",
                occurred_at="2026-05-11T04:30:00Z",
            )
            store.add(
                title="UTC inside",
                summary="UTC inside",
                participants=["Rohit", "Maez"],
                source_memory_ids=["utc-inside"],
                source_kind="telegram",
                occurred_at="2026-05-11T04:45:00+00:00",
            )
            store.add(
                title="Local offset outside",
                summary="Local offset outside",
                participants=["Rohit", "Maez"],
                source_memory_ids=["local-outside"],
                source_kind="telegram",
                occurred_at="2026-05-11T00:30:00-05:00",
            )
            store.add(
                title="Local offset inside previous date",
                summary="Local offset inside previous date",
                participants=["Rohit", "Maez"],
                source_memory_ids=["local-inside"],
                source_kind="telegram",
                occurred_at="2026-05-10T23:30:00-05:00",
            )
            store.add(
                title="Naive inside",
                summary="Naive inside",
                participants=["Rohit", "Maez"],
                source_memory_ids=["naive-inside"],
                source_kind="telegram",
                occurred_at="2026-05-11T04:50:00",
            )

            rows = store.list_active_in_window(
                window_start="2026-05-11T04:00:00+00:00",
                window_end="2026-05-11T05:00:00+00:00",
                limit=10,
            )

        titles = {row["title"] for row in rows}
        self.assertEqual(
            titles,
            {
                "Z inside",
                "UTC inside",
                "Naive inside",
                "Local offset inside previous date",
            },
        )

    def test_brief_returns_episodes_inside_window_without_keyword_overlap(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        ep_id = store.add_row(
            "Quiet gym check-in with grounded encouragement",
            "2026-05-07T18:00:00-05:00",
            "telegram-last-week-1",
        )
        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )
        self.assertEqual(result.search_status, "evidence_found")
        self.assertEqual(result.evidence_ids, (ep_id, "telegram-last-week-1"))
        self.assertIn("TEMPORAL ANCHOR RECALL", result.brief_text)
        self.assertIn("telegram-last-week-1", result.brief_text)

    def test_brief_excludes_episodes_outside_window(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        store.add_row(
            "Current week event",
            "2026-05-12T18:00:00-05:00",
            "telegram-current-week",
        )
        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )
        self.assertEqual(result.search_status, "bounded_search_no_match")
        self.assertEqual(result.evidence_ids, ())
        self.assertFalse(result.memory_absence_established)
        self.assertIn("no matching grounded episodes found", result.brief_text)

    def test_more_than_max_items_truncates_but_exact_max_does_not(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        for i in range(5):
            store.add_row(
                f"Last-week event {i}",
                f"2026-05-0{5 + i}T12:00:00-05:00",
                f"src-{i}",
            )
        result = build_temporal_anchor_recall_brief(
            "What do you remember from last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
            max_items=4,
        )
        self.assertEqual(result.item_count, 4)
        self.assertTrue(result.truncated)

        exact = build_temporal_anchor_recall_brief(
            "What do you remember from last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
            max_items=5,
        )
        self.assertEqual(exact.item_count, 5)
        self.assertFalse(exact.truncated)

    def test_daemon_path_uses_windowed_store_query_not_full_store_scan(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        store.add_row(
            "Last-week event",
            "2026-05-07T12:00:00-05:00",
            "src-windowed",
        )
        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )
        self.assertEqual(result.search_status, "evidence_found")
        self.assertEqual(result.evidence_ids, ("ep-0", "src-windowed"))

    def test_temporal_brief_caps_episode_text_and_total_size(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        for i in range(5):
            store.add_row(
                f"Long last-week event {i} " + ("x" * 500),
                f"2026-05-0{5 + i}T12:00:00-05:00",
                f"src-long-{i}",
            )
        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=store,
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
            max_items=4,
        )
        self.assertLessEqual(len(result.brief_text), 1236)
        self.assertIn("[truncated]", result.brief_text)
        self.assertIn("src-long-", result.brief_text)

    def test_env_kill_switch_disables_only_temporal_helper(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        store = _FakeEpisodeStore()
        with patch.dict(os.environ, {"MAEZ_TEMPORAL_ANCHOR_RECALL": "0"}):
            result = build_temporal_anchor_recall_brief(
                "Do you remember last week?",
                episode_store=store,
                reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
            )
        self.assertTrue(result.anchor_detected)
        self.assertEqual(result.search_status, "helper_unavailable")
        self.assertEqual(result.brief_text, "")

    def test_missing_windowed_store_query_returns_unavailable_without_full_scan(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        class NoWindowStore:
            def list_active(self):
                raise AssertionError("full-store scan must not be attempted")

        result = build_temporal_anchor_recall_brief(
            "Do you remember last week?",
            episode_store=NoWindowStore(),
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )
        self.assertTrue(result.anchor_detected)
        self.assertEqual(result.search_status, "helper_unavailable")
        self.assertEqual(result.brief_text, "")

    def test_helper_exception_returns_unavailable_not_no_match(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief

        class BrokenStore:
            def list_active(self):
                raise RuntimeError("store down")

        result = build_temporal_anchor_recall_brief(
            "Do you remember yesterday?",
            episode_store=BrokenStore(),
            reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
        )
        self.assertEqual(result.search_status, "helper_unavailable")
        self.assertEqual(result.brief_text, "")
        self.assertFalse(result.memory_absence_established)


class TemporalFragmentGuardTests(unittest.TestCase):
    def _temporal_result(self, status="bounded_search_no_match", anchor_detected=True):
        from core.memory.temporal_anchor_recall import TemporalAnchorRecallResult

        return TemporalAnchorRecallResult(
            anchor_detected=anchor_detected,
            anchor_kind="last_week" if anchor_detected else None,
            window_start=None,
            window_end=None,
            window_searched=anchor_detected and status != "helper_unavailable",
            search_status=status,
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=0,
            memory_absence_established=False,
        )

    def test_observed_fragments_are_detected(self):
        from core.safety.temporal_fragment_guard import is_temporal_ars_fragment

        for text in (
            "That's the gap.",
            "I'm glad to hear you're feeling better.",
            "But I'm glad to hear you're feeling better now.",
        ):
            self.assertTrue(is_temporal_ars_fragment(text, temporal_question=True), text)

    def test_boundary_cases_for_fragment_classifier(self):
        from core.safety.temporal_fragment_guard import is_temporal_ars_fragment

        self.assertTrue(
            is_temporal_ars_fragment(
                "But the surrounding answer is still missing any retrieval posture at all.",
                temporal_question=True,
            )
        )
        self.assertFalse(
            is_temporal_ars_fragment(
                "But I found one memory from last week: you said the gym helped.",
                temporal_question=True,
            )
        )
        self.assertTrue(
            is_temporal_ars_fragment(
                "glad you feel better now today okay yes", temporal_question=True
            )
        )
        self.assertFalse(
            is_temporal_ars_fragment(
                "I hear the question and I am staying with the thread without claiming memory.",
                temporal_question=True,
            )
        )

    def test_guard_replaces_fragment_with_ratified_fallback_and_witness(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        user_message = "I feel much better compared to last week. You remember last week right?"
        result = guard_temporal_ars_fragment(
            user_message=user_message,
            post_ars_text="But I'm glad to hear you're feeling better now.",
            temporal_result=self._temporal_result("bounded_search_no_match"),
            current_context=extract_current_message_context(user_message),
        )
        self.assertTrue(result.guard_used)
        self.assertEqual(
            result.text,
            "I'm not finding that clearly right now. I hear that you feel much better than last week.",
        )

    def test_evidence_found_memory_claim_without_approved_posture_is_guarded(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        for post_ars in (
            "I remember last week. You were struggling then.",
            "I recall from yesterday that you were struggling.",
            "I remember one memory from last week: you were struggling.",
        ):
            result = guard_temporal_ars_fragment(
                user_message="Do you remember last week?",
                post_ars_text=post_ars,
                temporal_result=self._temporal_result("evidence_found"),
                current_context=extract_current_message_context("Do you remember last week?"),
            )
            self.assertTrue(result.guard_used, post_ars)
            self.assertNotIn("I remember", result.text)
            self.assertNotIn("I recall", result.text)
            self.assertNotIn("You were struggling", result.text)
            self.assertNotIn("you were struggling", result.text)
            self.assertEqual(
                result.text,
                "I found something from that window, but I need to answer it carefully.",
            )

    def test_evidence_found_approved_retrieval_posture_is_not_rewritten(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        post_ars = "I found one memory from last week: you said the gym helped."
        result = guard_temporal_ars_fragment(
            user_message="Do you remember last week?",
            post_ars_text=post_ars,
            temporal_result=self._temporal_result("evidence_found"),
            current_context=extract_current_message_context("Do you remember last week?"),
        )
        self.assertFalse(result.guard_used)
        self.assertEqual(result.text, post_ars)

    def test_evidence_found_affect_fragment_does_not_claim_no_match(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        result = guard_temporal_ars_fragment(
            user_message="Do you remember last week?",
            post_ars_text="But I'm glad to hear you're feeling better now.",
            temporal_result=self._temporal_result("evidence_found"),
            current_context=extract_current_message_context("Do you remember last week?"),
        )
        self.assertTrue(result.guard_used)
        self.assertEqual(
            result.text,
            "I found something from that window, but I need to answer it carefully.",
        )
        self.assertNotIn("not finding", result.text)

    def test_kill_switch_still_allows_fragment_guard_helper_unavailable_fallback(self):
        from core.memory.temporal_anchor_recall import build_temporal_anchor_recall_brief
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        store = _FakeEpisodeStore()
        with patch.dict(os.environ, {"MAEZ_TEMPORAL_ANCHOR_RECALL": "0"}):
            temporal_result = build_temporal_anchor_recall_brief(
                "Do you remember last week?",
                episode_store=store,
                reference_time=datetime(2026, 5, 13, 22, 30, tzinfo=CHICAGO),
            )
        guarded = guard_temporal_ars_fragment(
            user_message="Do you remember last week?",
            post_ars_text="But I'm glad to hear you're feeling better now.",
            temporal_result=temporal_result,
            current_context=extract_current_message_context("Do you remember last week?"),
        )
        self.assertTrue(guarded.guard_used)
        self.assertEqual(guarded.text, "I can't check that clearly right now.")

    def test_helper_unavailable_uses_check_not_finding(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        result = guard_temporal_ars_fragment(
            user_message="Do you remember last week?",
            post_ars_text="But I'm glad to hear you're feeling better now.",
            temporal_result=self._temporal_result("helper_unavailable"),
            current_context=extract_current_message_context("Do you remember last week?"),
        )
        self.assertEqual(result.text, "I can't check that clearly right now.")
        self.assertNotIn("not finding", result.text)

    def test_current_context_is_limited_to_first_person_self_report(self):
        from core.safety.temporal_fragment_guard import extract_current_message_context

        ctx = extract_current_message_context(
            "I feel much better compared to last week. You remember last week right?"
        )
        self.assertTrue(ctx.has_grounded_self_report)
        self.assertEqual(ctx.self_report_phrase, "much better than last week")

        inferred = extract_current_message_context(
            "You can probably tell I seem upset since last week."
        )
        self.assertFalse(inferred.has_grounded_self_report)

    def test_comparative_structure_not_rewritten_from_since(self):
        from core.safety.temporal_fragment_guard import extract_current_message_context

        ctx = extract_current_message_context("I feel steadier since last week.")
        self.assertFalse(ctx.has_grounded_self_report)

    def test_guard_does_not_activate_without_temporal_anchor(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        result = guard_temporal_ars_fragment(
            user_message="Are you okay?",
            post_ars_text="But I'm glad to hear that.",
            temporal_result=self._temporal_result(anchor_detected=False),
            current_context=extract_current_message_context("Are you okay?"),
        )
        self.assertFalse(result.guard_used)
        self.assertEqual(result.text, "But I'm glad to hear that.")

    def test_guard_does_not_let_ungrounded_model_claims_through(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        result = guard_temporal_ars_fragment(
            user_message="I feel much better compared to last week. You remember last week right?",
            post_ars_text="I remember last week. You were struggling then.",
            temporal_result=self._temporal_result("bounded_search_no_match"),
            current_context=extract_current_message_context(
                "I feel much better compared to last week. You remember last week right?"
            ),
        )
        self.assertNotIn("You were struggling", result.text)
        self.assertNotIn("I remember last week", result.text)

    def test_audit_then_guard_preserves_audit_protection_before_fallback(self):
        from core.safety.self_claim_audit import Flag, audit
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        reply = "Last week was hard for you. But I'm glad to hear you're feeling better now."
        claim = "Last week was hard for you."

        def fake_find_flags(candidate, **_kwargs):
            start = candidate.find(claim)
            return [Flag(kind="judge", span=(start, start + len(claim)), text=claim)], True

        with patch("core.safety.self_claim_audit._find_flags", side_effect=fake_find_flags):
            audited = audit(reply, surface="telegram_surface")

        self.assertNotIn(claim, audited.text)
        guarded = guard_temporal_ars_fragment(
            user_message="I feel much better compared to last week. You remember last week right?",
            post_ars_text=audited.text,
            temporal_result=self._temporal_result("bounded_search_no_match"),
            current_context=extract_current_message_context(
                "I feel much better compared to last week. You remember last week right?"
            ),
        )
        self.assertTrue(guarded.guard_used)
        self.assertNotIn(claim, guarded.text)
        self.assertEqual(
            guarded.text,
            "I'm not finding that clearly right now. I hear that you feel much better than last week.",
        )

    def test_audit_fail_open_plus_evidence_found_memory_claim_is_guarded(self):
        from core.safety.temporal_fragment_guard import (
            extract_current_message_context,
            guard_temporal_ars_fragment,
        )

        reply = "I remember last week. You were struggling then."
        # The daemon's audit wrapper may fail open if the judge is unavailable.
        # The post-audit TRF guard must still not let an explicit memory claim
        # through merely because some temporal-window evidence exists.
        guarded = guard_temporal_ars_fragment(
            user_message="Do you remember last week?",
            post_ars_text=reply,
            temporal_result=self._temporal_result("evidence_found"),
            current_context=extract_current_message_context("Do you remember last week?"),
        )
        self.assertTrue(guarded.guard_used)
        self.assertNotIn("I remember last week", guarded.text)
        self.assertNotIn("You were struggling", guarded.text)
        self.assertEqual(
            guarded.text,
            "I found something from that window, but I need to answer it carefully.",
        )


class ProbeCorpusTests(unittest.TestCase):
    def test_probe_corpus_exists_and_has_required_shapes(self):
        corpus_path = _REPO / "tests" / "data" / "trf_probe_corpus.jsonl"
        rows = [json.loads(line) for line in corpus_path.read_text().splitlines() if line.strip()]
        categories = {row["category"] for row in rows}
        self.assertIn("last_week", categories)
        self.assertIn("yesterday", categories)
        self.assertIn("this_morning", categories)
        self.assertIn("earlier_today", categories)
        self.assertIn("negative_control", categories)
        self.assertTrue(
            any("I feel much better compared to last week" in row["prompt"] for row in rows)
        )


class DaemonTRFWiringTests(unittest.TestCase):
    def test_daemon_imports_temporal_anchor_and_fragment_guard_helpers(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        self.assertIn("build_temporal_anchor_recall_brief", src)
        self.assertIn("guard_temporal_ars_fragment", src)
        self.assertIn("extract_current_message_context", src)

    def test_daemon_wires_trf_after_lived_recall_and_after_audit(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        lived_idx = src.find("build_lived_recall_brief(")
        temporal_idx = src.find("build_temporal_anchor_recall_brief(")
        audit_idx = src.find("reply = audit_assistant_text(", temporal_idx)
        guard_idx = src.find("_trf_apply_fragment_guard(", audit_idx)
        self.assertGreater(lived_idx, 0)
        self.assertGreater(temporal_idx, lived_idx)
        self.assertGreater(audit_idx, temporal_idx)
        self.assertGreater(guard_idx, audit_idx)

    def test_daemon_fragment_guard_helper_replaces_fragment_after_audit(self):
        from core.memory.temporal_anchor_recall import TemporalAnchorRecallResult
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        trace = SimpleNamespace(audit=SimpleNamespace(ran=True, changed_output=False))
        temporal_result = TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind="last_week",
            window_start=None,
            window_end=None,
            window_searched=True,
            search_status="bounded_search_no_match",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=0,
            memory_absence_established=False,
        )

        reply = daemon._trf_apply_fragment_guard(
            user_message="I feel much better compared to last week. You remember last week right?",
            reply="But I'm glad to hear you're feeling better now.",
            temporal_anchor_result=temporal_result,
            trace=trace,
        )

        self.assertEqual(
            reply,
            "I'm not finding that clearly right now. I hear that you feel much better than last week.",
        )
        self.assertTrue(trace.audit.changed_output)

    def test_daemon_fragment_guard_failure_returns_original_reply(self):
        from core.memory.temporal_anchor_recall import TemporalAnchorRecallResult
        from daemon.maez_daemon import MaezDaemon

        daemon = object.__new__(MaezDaemon)
        temporal_result = TemporalAnchorRecallResult(
            anchor_detected=True,
            anchor_kind="last_week",
            window_start=None,
            window_end=None,
            window_searched=True,
            search_status="bounded_search_no_match",
            evidence_ids=(),
            item_count=0,
            truncated=False,
            brief_text="",
            elapsed_ms=0,
            memory_absence_established=False,
        )
        with patch(
            "daemon.maez_daemon.guard_temporal_ars_fragment", side_effect=RuntimeError("boom")
        ):
            reply = daemon._trf_apply_fragment_guard(
                user_message="Do you remember last week?",
                reply="Original audited reply.",
                temporal_anchor_result=temporal_result,
                trace=None,
            )
        self.assertEqual(reply, "Original audited reply.")


if __name__ == "__main__":
    unittest.main()
