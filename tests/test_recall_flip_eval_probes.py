import tempfile
import unittest
from datetime import date
from unittest import mock

from scripts.recall_flip_eval import sandbox


class RecallFlipEvalProbeRunnerTest(unittest.TestCase):
    def test_flag_on_uses_dispatcher_adapter_structured_recall_and_offline_chat(self):
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            fixture_id = sandbox.seed_dated_memory(
                "dated_hit",
                "v1",
                date=date(2026, 4, 27),
                content="SANDBOX INFRA APRIL27 TOKEN",
                tier="core",
                run_id="run-probe",
            )

            from core.brain import brain_loop
            from core.routing import focused_cognition
            from scripts.recall_flip_eval import harness

            with (
                mock.patch.object(
                    brain_loop,
                    "_dispatcher_recall_adapters",
                    wraps=brain_loop._dispatcher_recall_adapters,
                ) as adapters_spy,
                mock.patch.object(
                    brain_loop,
                    "recall_partitions_to_items",
                    wraps=brain_loop.recall_partitions_to_items,
                ) as items_spy,
                mock.patch.object(
                    focused_cognition,
                    "assemble_working_set",
                    wraps=focused_cognition.assemble_working_set,
                ) as assemble_spy,
                mock.patch.object(
                    focused_cognition,
                    "focused_synthesize",
                    wraps=focused_cognition.focused_synthesize,
                ) as synth_spy,
            ):
                result = harness.run_probe(
                    "What did we note around April 27?",
                    flag_on=True,
                )

            self.assertEqual(result.outcome_class, "answered_grounded")
            self.assertIn(fixture_id, result.cited_durable_ids)
            self.assertTrue(result.cited_confirmed_memory_context)
            self.assertGreater(result.focused_elapsed_ms, -1)
            adapters_spy.assert_called()
            items_spy.assert_called()
            assemble_spy.assert_called()
            synth_spy.assert_called()
            self.assertIs(
                synth_spy.call_args.kwargs["chat_fn"],
                harness.deterministic_offline_chat,
            )
            recall_items_arg = assemble_spy.call_args.kwargs["recall_items"]
            self.assertTrue(tuple(recall_items_arg))

    def test_flag_off_is_carrier_unavailable_control_and_does_not_consult_living_recall(self):
        from memory.memory_manager import MemoryManager
        from scripts.recall_flip_eval import harness

        with mock.patch.object(
            MemoryManager,
            "recall_for_telegram_living",
            side_effect=AssertionError("flag-off must not consult living recall"),
        ):
            result = harness.run_probe("What did we note around April 27?", flag_on=False)

        self.assertEqual(result.outcome_class, "declined_unavailable")
        self.assertEqual(result.receipt, "not_consulted")
        self.assertFalse(result.cited_durable_ids)


if __name__ == "__main__":
    unittest.main()
