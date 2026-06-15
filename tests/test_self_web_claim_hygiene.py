import unittest
from unittest import mock


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


class _FakeCollection:
    def __init__(self):
        self.add_calls = []

    def add(self, *, ids, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        })


def _mm_with_fakes():
    from memory.memory_manager import MemoryManager

    mm = MemoryManager.__new__(MemoryManager)
    mm.raw = _FakeCollection()
    mm.core = _FakeCollection()
    return mm


class StoreTelegramTurnLinkIdTest(unittest.TestCase):
    def test_store_telegram_persists_turn_link_id(self):
        mm = _mm_with_fakes()
        mid = mm.store_telegram(
            "the owner: hi\nMaez: here",
            provenance_source="user_utterance",
            trust_tier="lived",
            turn_link_id="turn-xyz",
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["turn_link_id"], "turn-xyz")

    def test_store_telegram_omits_turn_link_id_when_not_given(self):
        mm = _mm_with_fakes()
        mm.store_telegram(
            "the owner: hi\nMaez: here",
            provenance_source="user_utterance",
            trust_tier="lived",
        )
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertNotIn("turn_link_id", meta)


class StoreSplitDecisionTest(unittest.TestCase):
    def test_web_grounded_on_splits_into_two_linked_records(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="news about X",
                                    reply="X did Y", web_grounded=True, hygiene_enabled=True)
        self.assertEqual(len(specs), 2)
        owner = [s for s in specs if s.is_owner_record][0]
        reply = [s for s in specs if not s.is_owner_record][0]
        self.assertEqual(owner.provenance_source, "user_utterance")
        self.assertEqual(owner.trust_tier, "lived")
        self.assertEqual(reply.provenance_source, "self_web_claim")
        self.assertEqual(reply.trust_tier, "untrusted")
        self.assertEqual(owner.turn_link_id, reply.turn_link_id)
        self.assertNotIn("Maez:", owner.content)
        self.assertNotIn("the owner", reply.content)

    def test_non_web_grounded_keeps_single_combined_record(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="hi", reply="hello",
                                    web_grounded=False, hygiene_enabled=True)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].provenance_source, "user_utterance")
        self.assertEqual(specs[0].trust_tier, "lived")
        self.assertIn("Maez:", specs[0].content)

    def test_flag_off_keeps_single_combined_record_even_web_grounded(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="news about X",
                                    reply="X did Y", web_grounded=True, hygiene_enabled=False)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].trust_tier, "lived")


class M1OwnerIdOnlyTest(unittest.TestCase):
    def test_promotion_receives_owner_id_only_on_split(self):
        from daemon.maez_daemon import m1_raw_memory_id_for_promotion
        chosen = m1_raw_memory_id_for_promotion(owner_id="owner-1", reply_id="reply-1")
        self.assertEqual(chosen, "owner-1")
        self.assertNotEqual(chosen, "reply-1")

    def test_promotion_id_is_owner_when_unsplit(self):
        from daemon.maez_daemon import m1_raw_memory_id_for_promotion
        self.assertEqual(
            m1_raw_memory_id_for_promotion(owner_id="combined-1", reply_id=None),
            "combined-1",
        )


class RecallExclusionTest(unittest.TestCase):
    def _items(self, *triples):
        # triples: (source_type, text, origin_provenance)
        from core.dispatcher.layer1 import RecallItem
        return tuple(RecallItem(text=t, source_type=st, durable_id=t,
                                trust_tier=("untrusted" if op else None),
                                provenance_source=op) for st, t, op in triples)

    def _assemble(self, *, recall_items, web_context, enabled):
        from core.routing.focused_cognition import assemble_working_set
        env = {"MAEZ_SELF_CLAIM_HYGIENE_ENABLED": "1" if enabled else "0"}
        with mock.patch.dict("os.environ", env):
            return assemble_working_set(
                transcript="", web_context=web_context,
                owner_question="news about Anthropic", recall_items=recall_items)

    def test_self_web_claim_excluded_when_fresh_present(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "old Anthropic claim", "self_web_claim")),
            web_context="Anthropic released a new model today.", enabled=True)
        self.assertIsNotNone(ws)
        self.assertNotIn("old Anthropic claim", [it.text for it in ws.items])

    def test_self_web_claim_kept_and_labeled_when_no_fresh(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "old Anthropic claim", "self_web_claim")),
            web_context="", enabled=True)
        kept = [it for it in ws.items if it.text == "old Anthropic claim"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].origin_provenance, "self_web_claim")

    def test_external_web_untrusted_not_excluded_when_fresh(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "prior web observation", "external_web")),
            web_context="Something fresh happened today.", enabled=True)
        self.assertIn("prior web observation", [it.text for it in ws.items])

    def test_flag_off_keeps_self_web_claim_even_with_fresh(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "old Anthropic claim", "self_web_claim")),
            web_context="Anthropic released a new model today.", enabled=False)
        self.assertIn("old Anthropic claim", [it.text for it in ws.items])


if __name__ == "__main__":
    unittest.main()
