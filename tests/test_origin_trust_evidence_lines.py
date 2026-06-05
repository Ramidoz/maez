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


if __name__ == "__main__":
    unittest.main()
