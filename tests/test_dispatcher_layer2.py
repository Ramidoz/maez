import unittest


def _spec(*, external=False):
    from core.dispatcher.spec import (
        CompositionHint,
        CompositionSpec,
        ExternalSource,
        InventoryWitness,
        ProvenanceFraming,
        SourceAvailability,
        SubstrateSource,
    )

    substrate_sources = [SubstrateSource.TELEGRAM_SEMANTIC]
    external_sources = [ExternalSource.WEB_SEARCH] if external else []
    source_availability = {
        SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT
    }
    if external:
        source_availability[ExternalSource.WEB_SEARCH] = SourceAvailability.EXECUTABLE_PRESENT
    return CompositionSpec(
        substrate_sources=substrate_sources,
        external_sources=external_sources,
        composition_hint=(
            CompositionHint.SUBSTRATE_THEN_FETCH_IF_STALE
            if external
            else CompositionHint.SUBSTRATE_ONLY
        ),
        provenance_framing=(
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES
            if external
            else ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
        ),
        inventory_witness=InventoryWitness.PRESENT,
        source_availability=source_availability,
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )


class DispatcherLayer2Tests(unittest.TestCase):
    def test_non_repair_turn_returns_current_spec_without_store_lookup(self):
        from core.dispatcher.layer2 import Layer2RepairFSM

        fsm = Layer2RepairFSM(ttl_s=300, clock=lambda: 1000.0)
        current = _spec()

        result = fsm.apply_repair(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            current_utterance="what do you remember about qwen",
            current_spec=current,
        )

        self.assertIs(result, current)

    def test_repair_turn_inherits_same_surface_prior_spec_before_layer1_runs(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock
        from core.dispatcher.layer2 import Layer2RepairFSM
        from core.dispatcher.spec import SubstrateSource

        fsm = Layer2RepairFSM(ttl_s=300, clock=lambda: 1000.0)
        prior = _spec()
        current = _spec(external=True)
        fsm.record_completed_spec(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            spec=prior,
        )

        repaired = fsm.apply_repair(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            current_utterance="are you sure?",
            current_spec=current,
        )

        seen_sources = []

        def adapter(source):
            seen_sources.append(source)
            return [
                RecallBlock(
                    source=source,
                    text="prior topic row",
                    timestamp=1.0,
                    freshness="fresh",
                    rationale="repair inheritance",
                    prompt_cost=4,
                )
            ]

        Layer1Fanout(
            adapters={SubstrateSource.TELEGRAM_SEMANTIC: adapter},
            branch_timeout_s=0.1,
            global_deadline_s=0.2,
        ).run(repaired, utterance="are you sure?", conversation_state={})

        self.assertEqual(repaired.to_dict(), prior.to_dict())
        self.assertEqual(seen_sources, [SubstrateSource.TELEGRAM_SEMANTIC])

    def test_repair_turn_without_prior_returns_structured_refusal(self):
        from core.dispatcher.layer2 import (
            Layer2RepairFSM,
            RepairRefusal,
            RepairRefusalReason,
        )

        result = Layer2RepairFSM(ttl_s=300, clock=lambda: 1000.0).apply_repair(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            current_utterance="check again",
            current_spec=_spec(),
        )

        self.assertIsInstance(result, RepairRefusal)
        self.assertEqual(result.reason, RepairRefusalReason.NO_PRIOR_SPEC)

    def test_repair_fsm_does_not_cross_inherit_between_concurrent_surfaces(self):
        from core.dispatcher.layer2 import (
            Layer2RepairFSM,
            RepairRefusal,
            RepairRefusalReason,
        )

        fsm = Layer2RepairFSM(ttl_s=300, clock=lambda: 1000.0)
        fsm.record_completed_spec(
            bond_id="bond-1",
            surface="web",
            conversation_id="chat-1",
            spec=_spec(),
        )

        result = fsm.apply_repair(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            current_utterance="go on",
            current_spec=_spec(external=True),
        )

        self.assertIsInstance(result, RepairRefusal)
        self.assertEqual(result.reason, RepairRefusalReason.CROSS_SURFACE_REFUSED)

    def test_expired_prior_spec_refuses_before_layer1(self):
        from core.dispatcher.layer2 import (
            Layer2RepairFSM,
            RepairRefusal,
            RepairRefusalReason,
        )

        now = [1000.0]
        fsm = Layer2RepairFSM(ttl_s=5, clock=lambda: now[0])
        fsm.record_completed_spec(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            spec=_spec(),
        )
        now[0] = 1010.0

        result = fsm.apply_repair(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            current_utterance="really?",
            current_spec=_spec(external=True),
        )

        self.assertIsInstance(result, RepairRefusal)
        self.assertEqual(result.reason, RepairRefusalReason.PRIOR_SPEC_EXPIRED)

    def test_invalid_stored_spec_refuses_with_closed_reason(self):
        from core.dispatcher.layer2 import (
            Layer2RepairFSM,
            RepairRefusal,
            RepairRefusalReason,
        )

        fsm = Layer2RepairFSM(ttl_s=300, clock=lambda: 1000.0)
        fsm.record_completed_spec(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            spec=_spec(),
        )
        key = ("bond-1", "telegram", "chat-1")
        fsm._last_specs[key].spec_payload["composition_hint"] = "FRESH_ONLY"

        result = fsm.apply_repair(
            bond_id="bond-1",
            surface="telegram",
            conversation_id="chat-1",
            current_utterance="no that's not it",
            current_spec=_spec(external=True),
        )

        self.assertIsInstance(result, RepairRefusal)
        self.assertEqual(result.reason, RepairRefusalReason.MODIFIED_SPEC_INVALID)


if __name__ == "__main__":
    unittest.main()
