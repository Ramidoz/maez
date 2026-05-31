import unittest

from core.brain.brain_loop import recall_partitions_to_items


class PartitionsToItemsTest(unittest.TestCase):
    def test_exact_date_is_confirmed_memory_context(self):
        partition = {
            "core": [
                {
                    "id": "m1",
                    "content": "on April 27 X",
                    "metadata": {"temporal_match_method": "exact_date"},
                }
            ]
        }
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_type, "memory_context")
        self.assertEqual(items[0].durable_id, "m1")
        self.assertTrue(items[0].temporal_provenance["confirmed"])

    def test_month_window_is_confirmed(self):
        partition = {
            "daily": [
                {
                    "id": "m2",
                    "content": "in April Y",
                    "metadata": {"temporal_match_method": "month_window"},
                }
            ]
        }
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertTrue(items[0].temporal_provenance["confirmed"])

    def test_semantic_method_is_not_confirmed(self):
        partition = {
            "daily": [
                {
                    "id": "m3",
                    "content": "semantic fallback",
                    "metadata": {"temporal_match_method": "semantic_fallback"},
                }
            ]
        }
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertFalse(items[0].temporal_provenance["confirmed"])


if __name__ == "__main__":
    unittest.main()
