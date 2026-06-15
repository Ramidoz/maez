import unittest


class SelfWebClaimProvenanceTest(unittest.TestCase):
    def test_self_web_claim_is_a_provenance_source(self):
        from memory.memory_manager import ProvenanceSource

        self.assertEqual(ProvenanceSource.SELF_WEB_CLAIM.value, "self_web_claim")

    def test_self_web_claim_defaults_to_untrusted(self):
        from memory.memory_manager import TrustTier, default_tier_for

        self.assertEqual(default_tier_for("self_web_claim"), TrustTier.UNTRUSTED)

    def test_self_web_claim_is_distinct_from_claude_tier_response(self):
        from memory.memory_manager import ProvenanceSource

        self.assertNotEqual(
            ProvenanceSource.SELF_WEB_CLAIM, ProvenanceSource.CLAUDE_TIER_RESPONSE
        )


class ProvenanceTravelsRecallChainTest(unittest.TestCase):
    def test_recall_item_carries_provenance_source(self):
        from core.dispatcher.layer1 import RecallItem

        item = RecallItem(text="t", source_type="memory_context", provenance_source="self_web_claim")
        self.assertEqual(item.provenance_source, "self_web_claim")

    def test_recall_partitions_read_provenance_source_from_metadata(self):
        from core.brain.brain_loop import recall_partitions_to_items

        partition = {"raw": [{"content": "hi", "id": "r1",
                              "metadata": {"trust_tier": "untrusted",
                                           "provenance_source": "self_web_claim"}}]}
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertEqual(items[0].provenance_source, "self_web_claim")

    def test_evidence_item_carries_origin_provenance(self):
        from core.routing.focused_cognition import EvidenceItem

        ev = EvidenceItem(local_label="E1", source_type="memory_context", text="t",
                          durable_id="d", origin_provenance="self_web_claim")
        self.assertEqual(ev.origin_provenance, "self_web_claim")


if __name__ == "__main__":
    unittest.main()
