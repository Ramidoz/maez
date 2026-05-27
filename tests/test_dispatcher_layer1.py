import threading
import time
import unittest


def _spec(*sources, availability=None):
    from core.dispatcher.spec import (
        CompositionHint,
        CompositionSpec,
        InventoryWitness,
        ProvenanceFraming,
        SourceAvailability,
    )

    source_availability = {
        source: SourceAvailability.EXECUTABLE_PRESENT for source in sources
    }
    if availability:
        source_availability.update(availability)
    return CompositionSpec(
        substrate_sources=list(sources),
        external_sources=[],
        composition_hint=CompositionHint.SUBSTRATE_ONLY,
        provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        inventory_witness=InventoryWitness.PRESENT,
        source_availability=source_availability,
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )


class DispatcherLayer1Tests(unittest.TestCase):
    def test_layer1_fans_out_concurrently_and_merges_in_stable_source_order(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock, RecallBranchStatus
        from core.dispatcher.spec import SubstrateSource

        barrier = threading.Barrier(2)

        def adapter(source):
            barrier.wait(timeout=1.0)
            return [
                RecallBlock(
                    source=source,
                    text=f"{source.value} row",
                    timestamp=10.0,
                    freshness="test",
                    rationale="fixture",
                    prompt_cost=3,
                )
            ]

        fanout = Layer1Fanout(
            adapters={
                SubstrateSource.TELEGRAM_SEMANTIC: adapter,
                SubstrateSource.ENTITY_INDEX: adapter,
            },
            branch_timeout_s=0.5,
            global_deadline_s=0.8,
        )

        started = time.monotonic()
        result = fanout.run(
            _spec(SubstrateSource.ENTITY_INDEX, SubstrateSource.TELEGRAM_SEMANTIC),
            utterance="qwen status",
            conversation_state={},
        )
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.25)
        self.assertEqual(
            [branch.source for branch in result.branch_results],
            [SubstrateSource.TELEGRAM_SEMANTIC, SubstrateSource.ENTITY_INDEX],
        )
        self.assertEqual(
            [branch.status for branch in result.branch_results],
            [RecallBranchStatus.SUCCESS, RecallBranchStatus.SUCCESS],
        )
        self.assertEqual(
            [block.source for block in result.recall_blocks],
            [SubstrateSource.TELEGRAM_SEMANTIC, SubstrateSource.ENTITY_INDEX],
        )

    def test_reserved_source_returns_closed_result_without_calling_adapter(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBranchStatus
        from core.dispatcher.spec import SourceAvailability, SubstrateSource

        called = []

        def forbidden(source):
            called.append(source)
            raise AssertionError("reserved source executed")

        fanout = Layer1Fanout(
            adapters={SubstrateSource.LIVED_GRAPH: forbidden},
            branch_timeout_s=0.1,
            global_deadline_s=0.2,
        )
        result = fanout.run(
            _spec(
                SubstrateSource.LIVED_GRAPH,
                availability={
                    SubstrateSource.LIVED_GRAPH: SourceAvailability.RESERVED_UNAVAILABLE
                },
            ),
            utterance="map this relationship",
            conversation_state={},
        )

        self.assertEqual(called, [])
        self.assertEqual(len(result.branch_results), 1)
        self.assertEqual(
            result.branch_results[0].status,
            RecallBranchStatus.RESERVED_UNAVAILABLE,
        )
        self.assertEqual(result.recall_blocks, ())

    def test_branch_timeout_seals_merge_and_late_result_cannot_mutate_output(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock, RecallBranchStatus
        from core.dispatcher.spec import SubstrateSource

        release = threading.Event()

        def slow_adapter(source):
            release.wait(timeout=1.0)
            return [
                RecallBlock(
                    source=source,
                    text="late row",
                    timestamp=10.0,
                    freshness="late",
                    rationale="too slow",
                    prompt_cost=2,
                )
            ]

        fanout = Layer1Fanout(
            adapters={SubstrateSource.TELEGRAM_SEMANTIC: slow_adapter},
            branch_timeout_s=0.02,
            global_deadline_s=0.05,
            cleanup_grace_s=0.005,
        )
        result = fanout.run(
            _spec(SubstrateSource.TELEGRAM_SEMANTIC),
            utterance="what do you remember?",
            conversation_state={},
        )
        before = result.to_dict()

        release.set()
        time.sleep(0.05)

        self.assertEqual(result.to_dict(), before)
        self.assertEqual(result.branch_results[0].status, RecallBranchStatus.TIMEOUT)
        self.assertEqual(result.accepted_branch_ids, ())
        self.assertEqual(result.recall_blocks, ())

    def test_partial_branch_error_does_not_abort_successful_branch(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock, RecallBranchStatus
        from core.dispatcher.spec import SubstrateSource

        def ok_adapter(source):
            return [
                RecallBlock(
                    source=source,
                    text="kept row",
                    timestamp=20.0,
                    freshness="current",
                    rationale="fixture",
                    prompt_cost=2,
                )
            ]

        def error_adapter(source):
            raise RuntimeError("sqlite locked")

        fanout = Layer1Fanout(
            adapters={
                SubstrateSource.TELEGRAM_SEMANTIC: ok_adapter,
                SubstrateSource.WONDERINGS: error_adapter,
            },
            branch_timeout_s=0.2,
            global_deadline_s=0.4,
        )
        result = fanout.run(
            _spec(SubstrateSource.TELEGRAM_SEMANTIC, SubstrateSource.WONDERINGS),
            utterance="what is going on?",
            conversation_state={},
        )

        statuses = {branch.source: branch.status for branch in result.branch_results}
        self.assertEqual(
            statuses[SubstrateSource.TELEGRAM_SEMANTIC],
            RecallBranchStatus.SUCCESS,
        )
        self.assertEqual(statuses[SubstrateSource.WONDERINGS], RecallBranchStatus.ERROR)
        self.assertEqual([block.text for block in result.recall_blocks], ["kept row"])

    def test_layer1_accepts_injected_fanout_generation_id(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock
        from core.dispatcher.spec import SubstrateSource

        def adapter(source):
            return [
                RecallBlock(
                    source=source,
                    text="kept row",
                    timestamp=30.0,
                    freshness="current",
                    rationale="fixture",
                    prompt_cost=2,
                )
            ]

        result = Layer1Fanout(
            adapters={SubstrateSource.TELEGRAM_SEMANTIC: adapter},
            branch_timeout_s=0.2,
            global_deadline_s=0.4,
        ).run(
            _spec(SubstrateSource.TELEGRAM_SEMANTIC),
            utterance="what do you remember?",
            conversation_state={},
            fanout_generation_id="turn-seal-123",
        )

        self.assertEqual(result.fanout_generation_id, "turn-seal-123")
        self.assertEqual(
            [branch.fanout_generation_id for branch in result.branch_results],
            ["turn-seal-123"],
        )

    def test_layer1_default_generation_id_still_generated_when_absent(self):
        from unittest import mock

        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock
        from core.dispatcher.spec import SubstrateSource

        def adapter(source):
            return [
                RecallBlock(
                    source=source,
                    text="kept row",
                    timestamp=30.0,
                    freshness="current",
                    rationale="fixture",
                    prompt_cost=2,
                )
            ]

        fake_uuid = mock.Mock(hex="minted-default-id")
        with mock.patch("core.dispatcher.layer1.uuid.uuid4", return_value=fake_uuid):
            result = Layer1Fanout(
                adapters={SubstrateSource.TELEGRAM_SEMANTIC: adapter},
                branch_timeout_s=0.2,
                global_deadline_s=0.4,
            ).run(
                _spec(SubstrateSource.TELEGRAM_SEMANTIC),
                utterance="what do you remember?",
                conversation_state={},
            )

        self.assertEqual(result.fanout_generation_id, "minted-default-id")
        self.assertEqual(
            [branch.fanout_generation_id for branch in result.branch_results],
            ["minted-default-id"],
        )

    def test_layer1_branch_ids_use_shared_generation_id(self):
        from core.dispatcher.layer1 import Layer1Fanout, RecallBlock
        from core.dispatcher.spec import SubstrateSource

        def adapter(source):
            return [
                RecallBlock(
                    source=source,
                    text=f"{source.value} row",
                    timestamp=30.0,
                    freshness="current",
                    rationale="fixture",
                    prompt_cost=2,
                )
            ]

        result = Layer1Fanout(
            adapters={
                SubstrateSource.TELEGRAM_SEMANTIC: adapter,
                SubstrateSource.ENTITY_INDEX: adapter,
            },
            branch_timeout_s=0.2,
            global_deadline_s=0.4,
        ).run(
            _spec(SubstrateSource.ENTITY_INDEX, SubstrateSource.TELEGRAM_SEMANTIC),
            utterance="what do you remember?",
            conversation_state={},
            fanout_generation_id="shared-turn-seal",
        )

        self.assertEqual(
            [branch.branch_id for branch in result.branch_results],
            [
                "shared-turn-seal:TELEGRAM_SEMANTIC",
                "shared-turn-seal:ENTITY_INDEX",
            ],
        )
        self.assertEqual(
            result.accepted_branch_ids,
            (
                "shared-turn-seal:TELEGRAM_SEMANTIC",
                "shared-turn-seal:ENTITY_INDEX",
            ),
        )


if __name__ == "__main__":
    unittest.main()
