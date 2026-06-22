import unittest
from unittest import mock

from memory.memory_manager import (
    _apply_recall_floor,
    _passes_recall_floor,
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


if __name__ == "__main__":
    unittest.main()


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
