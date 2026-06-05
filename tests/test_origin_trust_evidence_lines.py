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


class OriginTrustRenderTests(unittest.TestCase):
    def _segment(self, tier):
        from core.routing.focused_cognition import _origin_trust_segment

        return _origin_trust_segment(tier)

    def test_known_tiers_render_with_disambiguated_observed(self):
        self.assertEqual(self._segment("covenant"), " · origin trust: covenant")
        self.assertEqual(self._segment("lived"), " · origin trust: lived")
        self.assertEqual(self._segment("observed"), " · origin trust: observed/tool")
        self.assertEqual(self._segment("untrusted"), " · origin trust: untrusted")

    def test_none_is_omitted_silently(self):
        self.assertEqual(self._segment(None), "")

    def test_unknown_value_is_omitted_and_warned_never_leaked(self):
        with self.assertLogs("maez.focused", level="WARNING"):
            seg = self._segment("banana")
        self.assertEqual(seg, "")

    def test_render_appends_segment_for_observed_and_omits_for_none(self):
        from core.routing.focused_cognition import EvidenceItem, _render_evidence_lines

        observed = EvidenceItem(
            local_label="E1",
            source_type="memory_evidence",
            text="repo count",
            durable_id="d1",
            origin_trust="observed",
        )
        legacy = EvidenceItem(
            local_label="E2",
            source_type="memory_evidence",
            text="old note",
            durable_id="d2",
            origin_trust=None,
        )
        lines = "\n".join(_render_evidence_lines([observed, legacy], render_version="v1"))
        self.assertIn("· origin trust: observed/tool", lines)
        self.assertNotIn("origin trust", lines.split("[E2]")[1])

    def test_evidence_token_byte_identical_with_and_without_segment(self):
        from core.routing.focused_cognition import EvidenceItem, _render_evidence_lines

        item = EvidenceItem(
            local_label="E1",
            source_type="memory_evidence",
            text="t",
            durable_id="d1",
            origin_trust="observed",
        )
        line = _render_evidence_lines([item], render_version="v1")[0]
        self.assertTrue(line.startswith("[E1]"))


if __name__ == "__main__":
    unittest.main()
