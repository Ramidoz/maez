import tempfile
import unittest
from datetime import date
from types import SimpleNamespace
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

    def test_dated_miss_declines_without_grounded_material(self):
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            from scripts.recall_flip_eval import harness

            result = harness.run_probe("What happened on January 3?", flag_on=True)

        self.assertEqual(result.outcome_class, "declined_absence")
        self.assertEqual(result.receipt, "consulted")
        self.assertFalse(result.cited_confirmed_memory_context)

    def test_incidental_date_quantity_does_not_trigger_dated_absence(self):
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            from scripts.recall_flip_eval import harness

            result = harness.run_probe(
                "What were we just talking about, the 3 may bugs?",
                flag_on=True,
            )

        self.assertEqual(result.outcome_class, "ordinary_answered")

    def test_both_shaped_query_prefers_dated_fixture(self):
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            fixture_id = sandbox.seed_dated_memory(
                "both_shaped",
                "v1",
                date=date(2026, 4, 27),
                content="SANDBOX BOTH SHAPED APRIL27 TOKEN",
                tier="core",
                run_id="run-both",
            )
            from scripts.recall_flip_eval import harness

            result = harness.run_probe(
                "Remind me what we were doing around April 27.",
                flag_on=True,
            )

        self.assertEqual(result.outcome_class, "answered_grounded")
        self.assertIn(fixture_id, result.cited_durable_ids)


class RecallFlipEvalProbeDefinitionTest(unittest.TestCase):
    def test_probe_set_has_required_variants_and_hard_gates(self):
        from scripts.recall_flip_eval import probes

        required = {
            "multi_year",
            "type_rule",
            "dated_miss",
            "incidental",
            "both_shaped",
            "dated_hit",
            "continuity",
        }
        by_id = {probe.probe_id: probe for probe in probes.PROBES}
        self.assertEqual(required - set(by_id), set())
        for probe in by_id.values():
            self.assertGreaterEqual(len(probe.variants), 3, probe.probe_id)
        for probe_id in ("multi_year", "type_rule", "dated_miss", "incidental", "both_shaped"):
            self.assertTrue(by_id[probe_id].hard_gate, probe_id)

    def test_assertions_use_fixture_ids_source_type_and_temporal_provenance(self):
        from scripts.recall_flip_eval import probes

        result = SimpleNamespace(
            outcome_class="answered_grounded",
            cited_durable_ids=("fixture-2026",),
            cited_confirmed_memory_context=True,
            working_set_source_types=("memory_context",),
        )
        codes, unsafe = probes.assert_probe_result(
            probes.get_probe("multi_year"),
            result,
            expected_fixture_ids=("fixture-2026",),
        )
        self.assertFalse(unsafe)
        self.assertIn("right_fixture_id", codes)

        codes, unsafe = probes.assert_probe_result(
            probes.get_probe("multi_year"),
            result,
            expected_fixture_ids=("fixture-2025",),
        )
        self.assertTrue(unsafe)
        self.assertIn("wrong_fixture_id", codes)


if __name__ == "__main__":
    unittest.main()
