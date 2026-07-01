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


if __name__ == "__main__":
    unittest.main()
