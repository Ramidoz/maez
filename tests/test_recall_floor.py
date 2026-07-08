import unittest
from unittest import mock

from memory.memory_manager import (
    _apply_recall_floor,
    _passes_recall_floor,
    _recall_floor_teacher_signal,
    recall_floor_enabled,
    recall_floor_shadow_enabled,
)


class TestRecallFloorFlags(unittest.TestCase):
    def test_flags_off_by_default(self):
        self.assertFalse(recall_floor_shadow_enabled(env={}))
        self.assertFalse(recall_floor_enabled(env={}))

    def test_shadow_flag_on(self):
        self.assertTrue(
            recall_floor_shadow_enabled(env={"MAEZ_RECALL_FLOOR_SHADOW": "1"})
        )


class TestFloorPredicate(unittest.TestCase):
    def test_relevant_item_passes(self):
        self.assertTrue(_passes_recall_floor({"distance": 0.40}, floor=0.75))

    def test_irrelevant_item_fails(self):
        self.assertFalse(_passes_recall_floor({"distance": 0.90}, floor=0.75))

    def test_missing_distance_passes_failsafe(self):
        self.assertTrue(_passes_recall_floor({}, floor=0.75))

    def test_non_finite_distance_passes_failsafe(self):
        self.assertTrue(_passes_recall_floor({"distance": float("nan")}, floor=0.75))
        self.assertTrue(_passes_recall_floor({"distance": float("inf")}, floor=0.75))


class TestApplyFloor(unittest.TestCase):
    _raw = [
        {"id": "a", "distance": 0.40},
        {"id": "b", "distance": 0.90},
        {"id": "c", "distance": 0.95},
    ]

    def test_off_keeps_all(self):
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "0"}):
            self.assertEqual(_apply_recall_floor(self._raw, floor=0.75), self._raw)

    def test_on_drops_irrelevant(self):
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor(self._raw, floor=0.75)
        self.assertEqual([mem["id"] for mem in kept], ["a"])

    def test_on_all_irrelevant_returns_empty(self):
        flood = [{"id": "x", "distance": 0.85}, {"id": "y", "distance": 0.92}]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            self.assertEqual(_apply_recall_floor(flood, floor=0.75), [])


class TestApplyFloorWithFallback(unittest.TestCase):
    def test_fallback_keeps_best_n_when_floor_would_empty(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "weak-best", "distance": 0.81},
            {"id": "weak-worse", "distance": 0.95},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["weak-best"])

    def test_no_fallback_when_some_candidates_pass(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "good", "distance": 0.40},
            {"id": "weak", "distance": 0.90},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["good"])

    def test_missing_distance_still_keeps_candidate(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [{"id": "unknown-distance"}]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["unknown-distance"])

    def test_missing_distance_passer_prevents_fallback_policy(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "unknown-distance"},
            {"id": "finite-above-floor", "distance": 0.82},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["unknown-distance"])

    def test_boolean_distance_is_invalid_not_numeric_best(self):
        from memory.memory_manager import _distance_sort_key, _passes_recall_floor

        row = {"id": "bool-false", "distance": False}
        self.assertTrue(_passes_recall_floor(row, floor=0.78))
        self.assertEqual(_distance_sort_key(row), float("inf"))

    def test_non_finite_distance_passer_prevents_fallback_policy(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "nan-first", "distance": float("nan")},
            {"id": "finite-best", "distance": 0.82},
            {"id": "finite-worse", "distance": 0.95},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["nan-first"])

    def test_infinite_distance_passer_prevents_fallback_policy(self):
        from memory.memory_manager import _apply_recall_floor_with_fallback

        rows = [
            {"id": "inf-first", "distance": float("inf")},
            {"id": "finite-best", "distance": 0.82},
            {"id": "finite-worse", "distance": 0.95},
        ]
        with mock.patch.dict("os.environ", {"MAEZ_RECALL_FLOOR_ENABLED": "1"}):
            kept = _apply_recall_floor_with_fallback(rows, floor=0.78, min_keep=1)
        self.assertEqual([row["id"] for row in kept], ["inf-first"])

    def test_non_finite_distance_sorts_after_finite_distance_above_one(self):
        from memory.memory_manager import _distance_sort_key

        rows = [
            {"id": "nan-first", "distance": float("nan")},
            {"id": "inf-first", "distance": float("inf")},
            {"id": "finite-above-one", "distance": 1.2},
        ]
        ordered = sorted(rows, key=_distance_sort_key)
        self.assertEqual([row["id"] for row in ordered], ["finite-above-one", "nan-first", "inf-first"])


class TestTeacherSignal(unittest.TestCase):
    def test_tighten_only_when_diary_heavy_lowground_and_no_memory_ask(self):
        signal = _recall_floor_teacher_signal(
            diary_heavy=True,
            reply_grounding=0.0,
            asked_for_memory=False,
        )
        self.assertTrue(signal["tighten"])

    def test_warm_greeting_does_not_tighten(self):
        signal = _recall_floor_teacher_signal(
            diary_heavy=False,
            reply_grounding=0.0,
            asked_for_memory=False,
        )
        self.assertFalse(signal["tighten"])

    def test_explicit_memory_ask_does_not_tighten(self):
        signal = _recall_floor_teacher_signal(
            diary_heavy=True,
            reply_grounding=0.0,
            asked_for_memory=True,
        )
        self.assertFalse(signal["tighten"])


class TestSelfDigestKind(unittest.TestCase):
    def test_daily_consolidation_classifies_as_self_digest(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {"metadata": {"type": "daily_consolidation"}}

        self.assertEqual(_recall_candidate_kind(row), "self_digest")

    def test_nightly_journal_classifies_as_self_digest(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {"metadata": {"type": "core_memory", "source": "nightly_journal"}}

        self.assertEqual(_recall_candidate_kind(row), "self_digest")

    def test_unknown_memory_stays_unknown(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {"metadata": {"type": "core_memory", "source": "ordinary_core"}}

        self.assertEqual(_recall_candidate_kind(row), "unknown")

    def test_developmental_heartbeat_source_classifies_as_developmental_heartbeat(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {
            "content": "neutral structured continuity row",
            "metadata": {
                "type": "core_memory",
                "source": "developmental_heartbeat_2026-07-06",
            }
        }

        self.assertEqual(_recall_candidate_kind(row), "developmental_heartbeat")

    def test_developmental_heartbeat_kind_does_not_sniff_content(self):
        from memory.memory_manager import _recall_candidate_kind

        row = {
            "content": "[DEVELOPMENTAL HEARTBEAT - 2026-07-06] What I noticed: quiet.",
            "metadata": {"type": "core_memory", "source": "ordinary_core"},
        }

        self.assertEqual(_recall_candidate_kind(row), "unknown")


class TestContextFloorFlags(unittest.TestCase):
    def test_flags_off_by_default(self):
        from memory.memory_manager import (
            recall_context_floor_enabled,
            recall_context_floor_shadow_enabled,
        )

        self.assertFalse(recall_context_floor_shadow_enabled(env={}))
        self.assertFalse(recall_context_floor_enabled(env={}))

    def test_shadow_and_enabled_flags(self):
        from memory.memory_manager import (
            recall_context_floor_enabled,
            recall_context_floor_shadow_enabled,
        )

        self.assertTrue(
            recall_context_floor_shadow_enabled(
                env={"MAEZ_RECALL_CONTEXT_FLOOR_SHADOW": "1"}
            )
        )
        self.assertTrue(
            recall_context_floor_enabled(env={"MAEZ_RECALL_CONTEXT_FLOOR_ENABLED": "1"})
        )

    def test_old_type_floor_flags_do_not_wake_context_floor(self):
        from memory.memory_manager import (
            recall_context_floor_enabled,
            recall_context_floor_shadow_enabled,
        )

        old_env = {
            "MAEZ_RECALL_TYPE_FLOOR_SHADOW": "1",
            "MAEZ_RECALL_TYPE_FLOOR_ENABLED": "1",
        }

        self.assertFalse(recall_context_floor_shadow_enabled(env=old_env))
        self.assertFalse(recall_context_floor_enabled(env=old_env))


class TestMemoryAskGate(unittest.TestCase):
    def test_casual_turn_is_not_memory_ask(self):
        from memory.memory_manager import _is_recall_memory_ask

        self.assertFalse(_is_recall_memory_ask("how are you"))
        self.assertFalse(_is_recall_memory_ask("what did you do"))
        self.assertFalse(_is_recall_memory_ask("What's going on with you?"))

    def test_declarative_self_status_text_is_not_memory_ask(self):
        from memory.memory_manager import _is_recall_memory_ask

        self.assertFalse(
            _is_recall_memory_ask(
                "I don't believe you are ready yet to start refining yourself. "
                "Claude and Codex are working on you."
            )
        )

    def test_self_and_pattern_queries_are_memory_asks(self):
        from memory.memory_manager import _is_recall_memory_ask

        self.assertTrue(_is_recall_memory_ask("what have you noticed about yourself"))
        self.assertTrue(
            _is_recall_memory_ask("what patterns have you seen in your own reasoning")
        )
        self.assertTrue(_is_recall_memory_ask("what do you remember about your state"))
        self.assertTrue(_is_recall_memory_ask("what did I tell you about X last week"))
        self.assertTrue(_is_recall_memory_ask("remember what I said about X last week"))
        self.assertTrue(_is_recall_memory_ask("recall what I said about X last week"))
        self.assertTrue(_is_recall_memory_ask("show me memories about X"))


class TestContextFloorPredicate(unittest.TestCase):
    def test_casual_turn_uses_same_floor_for_all_raw_daily_kinds(self):
        from memory.memory_manager import (
            _candidate_context_floor,
            _passes_context_recall_floor,
        )

        self_digest = {
            "id": "daily",
            "distance": 0.74,
            "metadata": {"type": "daily_consolidation"},
        }
        relational = {
            "id": "relational",
            "distance": 0.74,
            "metadata": {"type": "telegram_exchange"},
        }

        for row in (self_digest, relational):
            self.assertEqual(
                _candidate_context_floor(
                    query_is_memory_ask=False,
                    base_floor=0.78,
                    casual_floor=0.72,
                    tier="raw",
                ),
                0.72,
            )
            self.assertFalse(
                _passes_context_recall_floor(
                    row,
                    query_is_memory_ask=False,
                    base_floor=0.78,
                    casual_floor=0.72,
                    tier="raw",
                )
            )

    def test_memory_ask_uses_v0_floor_for_raw_and_daily(self):
        from memory.memory_manager import _passes_context_recall_floor

        row = {
            "id": "daily",
            "distance": 0.74,
            "metadata": {"type": "daily_consolidation"},
        }

        self.assertTrue(
            _passes_context_recall_floor(
                row,
                query_is_memory_ask=True,
                base_floor=0.78,
                casual_floor=0.72,
                tier="daily",
            )
        )

    def test_memory_ask_core_is_v0_pass_through(self):
        from memory.memory_manager import _passes_context_recall_floor

        row = {
            "id": "core-high-distance",
            "distance": 0.95,
            "metadata": {"type": "core_memory", "source": "ordinary"},
        }

        self.assertTrue(
            _passes_context_recall_floor(
                row,
                query_is_memory_ask=True,
                base_floor=0.78,
                casual_floor=0.72,
                tier="core",
            )
        )

    def test_casual_core_is_pass_through_because_core_carries_bond_anchors(self):
        from memory.memory_manager import _passes_context_recall_floor

        row = {
            "id": "core-diary",
            "distance": 0.74,
            "metadata": {"type": "core_memory", "source": "nightly_journal"},
        }

        self.assertTrue(
            _passes_context_recall_floor(
                row,
                query_is_memory_ask=False,
                base_floor=0.78,
                casual_floor=0.72,
                tier="core",
            )
        )


class TestContextWholeRecallFallback(unittest.TestCase):
    def _self_digest(self, row_id, distance, *, tier="daily"):
        meta = {"type": "daily_consolidation"}
        if tier == "core":
            meta = {"type": "core_memory", "source": "nightly_journal"}
        return {"id": row_id, "distance": distance, "metadata": meta}

    def _reasoning(self, row_id, distance):
        return {"id": row_id, "distance": distance, "metadata": {"type": "reasoning"}}

    def _ids(self, partitions, tier):
        return [row["id"] for row in partitions.get(tier, [])]

    def test_casual_floor_drops_weak_raw_daily_memory_when_real_memory_exists(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-good", 0.30), self._reasoning("raw-weak", 0.74)],
            "daily": [self._self_digest("daily-diary", 0.74)],
            "core": [self._self_digest("nightly-diary", 0.75, tier="core")],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-good"])
        self.assertEqual(self._ids(filtered, "daily"), [])
        self.assertEqual(self._ids(filtered, "core"), ["nightly-diary"])
        self.assertEqual(summary["fallback_rescue_kind"], None)
        self.assertEqual(summary["would_drop_count"], 2)

    def test_fallback_rescues_best_by_distance_even_when_best_is_diary(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-weaker", 0.84)],
            "daily": [self._self_digest("daily-best", 0.74)],
            "core": [],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), [])
        self.assertEqual(self._ids(filtered, "daily"), ["daily-best"])
        self.assertEqual(summary["fallback_rescue_kind"], "best_by_distance")
        self.assertEqual(summary["fallback_rescue_id"], "daily-best")

    def test_fallback_rescues_best_by_distance_when_best_is_relational(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-best", 0.73)],
            "daily": [self._self_digest("daily-weaker", 0.74)],
            "core": [],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=False,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-best"])
        self.assertEqual(self._ids(filtered, "daily"), [])
        self.assertEqual(summary["fallback_rescue_kind"], "best_by_distance")
        self.assertEqual(summary["fallback_rescue_id"], "raw-best")

    def test_memory_ask_matches_v0_shape_with_per_tier_fallback(self):
        from memory.memory_manager import _apply_context_floor_to_partitions

        partitions = {
            "raw": [self._reasoning("raw-dropped-by-v0", 0.82)],
            "daily": [self._self_digest("daily-kept-by-v0", 0.74)],
            "core": [self._self_digest("core-pass-through", 0.95, tier="core")],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=True,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertEqual(self._ids(filtered, "raw"), ["raw-dropped-by-v0"])
        self.assertEqual(self._ids(filtered, "daily"), ["daily-kept-by-v0"])
        self.assertEqual(self._ids(filtered, "core"), ["core-pass-through"])
        self.assertEqual(summary["fallback_rescue_kind"], None)


class TestContextFloorReceiptFixture(unittest.TestCase):
    def _heartbeat(self, row_id: str, distance: float) -> dict:
        return {
            "id": row_id,
            "distance": distance,
            "content": (
                "[DEVELOPMENTAL HEARTBEAT - 2026-07-06 (Monday)] "
                "What I noticed: the system stayed mostly quiet."
            ),
            "metadata": {
                "type": "core_memory",
                "source": "developmental_heartbeat_2026-07-06",
            },
        }

    def test_casual_self_status_heartbeat_receipt_projects_majority_drop(self):
        from memory.memory_manager import (
            _apply_context_floor_to_partitions,
            _is_recall_memory_ask,
        )

        query_is_memory_ask = _is_recall_memory_ask("What's going on with you?")
        partitions = {
            "raw": [
                self._heartbeat(f"raw-heartbeat-{i}", 0.731 + (i * 0.001))
                for i in range(10)
            ],
            "daily": [
                self._heartbeat(f"daily-heartbeat-{i}", 0.745 + (i * 0.001))
                for i in range(3)
            ],
            "core": [
                self._heartbeat(f"core-heartbeat-{i}", 0.620 + (i * 0.001))
                for i in range(3)
            ],
        }

        _filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=query_is_memory_ask,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertFalse(query_is_memory_ask)
        self.assertEqual(summary["candidate_count"], 16)
        self.assertEqual(
            {row["kind"] for row in summary["decisions"]},
            {"developmental_heartbeat"},
        )
        self.assertGreater(summary["would_drop_count"], 8)

    def test_genuine_memory_ask_keeps_relevant_heartbeat_rows_reachable(self):
        from memory.memory_manager import (
            _apply_context_floor_to_partitions,
            _is_recall_memory_ask,
        )

        query_is_memory_ask = _is_recall_memory_ask(
            "what did I tell you about X last week"
        )
        partitions = {
            "raw": [self._heartbeat("raw-relevant", 0.74)],
            "daily": [self._heartbeat("daily-relevant", 0.75)],
            "core": [self._heartbeat("core-relevant", 0.90)],
        }

        filtered, summary = _apply_context_floor_to_partitions(
            partitions,
            query_is_memory_ask=query_is_memory_ask,
            base_floor=0.78,
            casual_floor=0.72,
            enforce=True,
        )

        self.assertTrue(query_is_memory_ask)
        self.assertEqual([row["id"] for row in filtered["raw"]], ["raw-relevant"])
        self.assertEqual([row["id"] for row in filtered["daily"]], ["daily-relevant"])
        self.assertEqual([row["id"] for row in filtered["core"]], ["core-relevant"])
        self.assertEqual(summary["would_drop_count"], 0)


if __name__ == "__main__":
    unittest.main()
