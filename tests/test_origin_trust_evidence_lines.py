# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Origin-Trust Evidence Lines — the provenance trust tier surfaced to the brain."""

from __future__ import annotations

import unittest


class RecallItemTrustTierTests(unittest.TestCase):
    def test_recall_item_carries_trust_tier(self):
        from core.dispatcher.layer1 import RecallItem

        item = RecallItem(text="x", source_type="memory_evidence", trust_tier="observed")
        self.assertEqual(item.trust_tier, "observed")

    def test_recall_item_trust_tier_defaults_none(self):
        from core.dispatcher.layer1 import RecallItem

        self.assertIsNone(RecallItem(text="x", source_type="memory_evidence").trust_tier)

    def test_recall_block_to_dict_includes_trust_tier(self):
        from core.dispatcher.layer1 import RecallBlock, RecallItem, SubstrateSource

        block = RecallBlock(
            source=list(SubstrateSource)[0],
            text="t",
            timestamp=None,
            freshness="fresh",
            rationale="r",
            prompt_cost=0,
            items=(
                RecallItem(
                    text="x",
                    source_type="memory_evidence",
                    trust_tier="observed",
                ),
            ),
        )
        self.assertEqual(block.to_dict()["items"][0]["trust_tier"], "observed")


class RecallPartitionsTrustTierTests(unittest.TestCase):
    def test_builder_reads_trust_tier_from_row_metadata(self):
        from core.brain.brain_loop import recall_partitions_to_items

        row = {
            "content": "GitHub reports 7 public repositories on the owner's profile",
            "metadata": {"trust_tier": "observed"},
            "id": "be9e8cf5",
        }
        items = recall_partitions_to_items({"raw": [row]}, role_source_type="memory_evidence")
        self.assertEqual(items[0].trust_tier, "observed")

    def test_builder_missing_trust_tier_is_none(self):
        from core.brain.brain_loop import recall_partitions_to_items

        row = {"content": "legacy memory", "metadata": {}, "id": "old-1"}
        items = recall_partitions_to_items({"raw": [row]}, role_source_type="memory_evidence")
        self.assertIsNone(items[0].trust_tier)


if __name__ == "__main__":
    unittest.main()
