import unittest

from memory.memory_manager import (
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
