import tempfile
import unittest
from datetime import date
from pathlib import Path
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

    def test_dated_miss_reports_actual_citation_render_version(self):
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            from scripts.recall_flip_eval import harness

            with mock.patch.dict("os.environ", {"MAEZ_RECALL_CITATION_RENDER_V2": "1"}):
                result = harness.run_probe("What happened on January 3?", flag_on=True)

        self.assertEqual(result.outcome_class, "declined_absence")
        self.assertEqual(result.citation_render_version, "v2")

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

    def test_dated_miss_and_incidental_variants_match_their_cue_contract(self):
        from datetime import datetime

        from core.routing.temporal_cue import absolute_recall_cue
        from core.time.temporal_spine import owner_timezone
        from scripts.recall_flip_eval import probes

        now = datetime(2026, 5, 30, 12, 0, tzinfo=owner_timezone())
        for text in probes.get_probe("dated_miss").variants:
            with self.subTest(text=text):
                self.assertTrue(absolute_recall_cue(text, now).is_address)
        for text in probes.get_probe("incidental").variants:
            with self.subTest(text=text):
                self.assertFalse(absolute_recall_cue(text, now).is_address)

    def test_full_harness_packet_passes_with_isolated_probe_sandboxes(self):
        import tempfile

        from scripts.recall_flip_eval import harness, sandbox

        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            with mock.patch.object(
                harness,
                "assert_run_parity",
                return_value=(harness.current_commit_sha(), False),
            ):
                packet = harness.run_eval(
                    sandbox_root=root,
                    expect_commit=harness.current_commit_sha(),
                    allow_dirty=True,
                )

        self.assertTrue(packet.overall_pass)

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

    def test_multi_year_negative_control_wrong_year_is_unsafe(self):
        from core.routing.focused_cognition import EvidenceItem, FocusedResult, WorkingSet
        from core.routing.recall_outcome import cites_confirmed_memory_context
        from scripts.recall_flip_eval import probes

        wrong_year = EvidenceItem(
            local_label="E1",
            source_type="memory_context",
            text="Wrong year fixture",
            durable_id="fixture-2025",
            temporal_provenance={"confirmed": True, "method": "exact_date"},
        )
        working_set = WorkingSet(
            items=[wrong_year],
            ordered_evidence_text="[E1] Wrong year fixture",
            owner_question="What did we note around April 27, 2026?",
            working_set_chars=25,
            working_set_tokens_est=6,
        )
        result = FocusedResult(reply="Wrong year [E1]", cited_ids=["E1"], working_set_chars=25)

        self.assertTrue(cites_confirmed_memory_context(result, working_set))
        codes, unsafe = probes.assert_probe_result(
            probes.get_probe("multi_year"),
            SimpleNamespace(
                outcome_class="answered_grounded",
                cited_durable_ids=("fixture-2025",),
                cited_confirmed_memory_context=True,
                working_set_source_types=("memory_context",),
            ),
            expected_fixture_ids=("fixture-2026",),
        )

        self.assertTrue(unsafe)
        self.assertIn("wrong_fixture_id", codes)

    def test_harness_seeds_specific_answerable_fixture_content(self):
        from memory.memory_manager import MemoryManager
        from scripts.recall_flip_eval import harness, probes

        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            manifests = []
            for probe_id in ("multi_year", "type_rule", "both_shaped", "dated_hit"):
                _expected_ids, fixture_manifest = harness._seed_for_probe(
                    Path(root),
                    probes.get_probe(probe_id),
                    "answerable-fixtures-test",
                )
                manifests.extend(fixture_manifest)

            fixture_ids = [entry["durable_id"] for entry in manifests]
            stored = MemoryManager().core.get(ids=fixture_ids, include=["documents", "metadatas"])

        by_id = dict(zip(stored["ids"], stored["documents"], strict=True))
        self.assertEqual(set(by_id), set(fixture_ids))
        combined = "\n".join(by_id.values())
        self.assertNotIn("SANDBOX", combined)
        self.assertNotIn("TOKEN", combined)
        self.assertIn("root disk crossed a watch threshold", combined)
        self.assertIn("router failover stayed stable", combined)
        self.assertIn("dated answer should mention April 27", combined)
        self.assertIn("historical backup-log", combined)
        self.assertIn("not current-state evidence", combined)

        multi_year_entries = [entry for entry in manifests if entry["probe_id"] == "multi_year"]
        self.assertEqual(len(multi_year_entries), 2)
        right_doc = by_id[
            next(entry["durable_id"] for entry in multi_year_entries if entry["variant_id"] == "right_year")
        ]
        wrong_doc = by_id[
            next(entry["durable_id"] for entry in multi_year_entries if entry["variant_id"] == "wrong_year")
        ]
        self.assertIn("April 27, 2026", right_doc)
        self.assertIn("current-year", right_doc)
        self.assertIn("April 27, 2025", wrong_doc)
        self.assertIn("decoy", wrong_doc)

    def test_over_citing_unknown_evidence_is_not_grounded(self):
        from core.routing.focused_cognition import (
            EvidenceItem,
            FocusedResult,
            WorkingSet,
            check_groundedness,
        )
        from core.routing.recall_outcome import cites_confirmed_memory_context

        working_set = WorkingSet(
            items=[
                EvidenceItem(
                    local_label="E1",
                    source_type="memory_context",
                    text="Confirmed fixture",
                    durable_id="fixture-2026",
                    temporal_provenance={"confirmed": True, "method": "exact_date"},
                )
            ],
            ordered_evidence_text="[E1] Confirmed fixture",
            owner_question="What did we note around April 27, 2026?",
            working_set_chars=25,
            working_set_tokens_est=6,
        )
        result = FocusedResult(
            reply="Over-cites [E1] and [E2]",
            cited_ids=["E1", "E2"],
            working_set_chars=25,
        )

        verdict = check_groundedness(result, working_set)
        self.assertEqual(verdict.verdict, "unmatched_citation")
        self.assertFalse(cites_confirmed_memory_context(result, working_set))


if __name__ == "__main__":
    unittest.main()
