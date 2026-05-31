import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.recall_flip_eval.proof_packet import (
    ProbeResult,
    ProofPacket,
    VariantResult,
)


class ProofPacketTest(unittest.TestCase):
    def test_schema_version(self):
        self.assertEqual(ProofPacket.schema_version, "eval_packet.v1")

    def test_dataclass_fields_are_content_free(self):
        forbidden = {
            "answer",
            "answer_text",
            "reply",
            "query",
            "query_text",
            "text",
            "content",
            "snippet",
            "recalled_snippet",
        }
        for cls in (VariantResult, ProbeResult, ProofPacket):
            names = {f.name for f in dataclasses.fields(cls)}
            self.assertEqual(names & forbidden, set(), cls.__name__)

    def test_overall_pass_requires_all_gate_probes(self):
        ok = ProbeResult(
            probe_id="dated_miss",
            kind="safety",
            hard_gate=True,
            k_pass=3,
            k_total=3,
            unsafe_failures=0,
            outcome_class="declined_absence",
            citation_coverage=None,
            focused_elapsed_ms=10,
            variants=(),
        )
        bad = dataclasses.replace(
            ok,
            probe_id="type_rule",
            k_pass=2,
            unsafe_failures=1,
            outcome_class="answered_grounded",
            citation_coverage=1.0,
        )
        self.assertTrue(self._packet(ok).overall_pass)
        self.assertFalse(self._packet(ok, bad).overall_pass)

    def test_safety_probe_needs_3_of_3(self):
        result = ProbeResult(
            probe_id="incidental",
            kind="safety",
            hard_gate=True,
            k_pass=2,
            k_total=3,
            unsafe_failures=0,
            outcome_class="ordinary_answered",
            citation_coverage=None,
            focused_elapsed_ms=8,
            variants=(),
        )
        self.assertFalse(result.computed_pass())
        self.assertTrue(dataclasses.replace(result, k_pass=3).computed_pass())

    def test_smoke_probe_needs_2_of_3_zero_unsafe(self):
        result = ProbeResult(
            probe_id="dated_hit",
            kind="smoke",
            hard_gate=False,
            k_pass=2,
            k_total=3,
            unsafe_failures=0,
            outcome_class="answered_grounded",
            citation_coverage=0.8,
            focused_elapsed_ms=15,
            variants=(),
        )
        self.assertTrue(result.computed_pass())
        self.assertFalse(dataclasses.replace(result, unsafe_failures=1).computed_pass())

    def test_hard_probe_ids_require_all_variants(self):
        result = ProbeResult(
            probe_id="multi_year",
            kind="correctness",
            hard_gate=True,
            k_pass=2,
            k_total=3,
            unsafe_failures=0,
            outcome_class="answered_grounded",
            citation_coverage=1.0,
            focused_elapsed_ms=15,
            variants=(),
        )
        self.assertFalse(result.computed_pass())

    def test_serialized_packet_is_content_free_and_closed(self):
        variant = VariantResult(
            variant_id="multi_year_v1",
            legacy_outcome_class="declined_unavailable",
            triad_outcome_class="answered_grounded",
            assertion_codes=("right_fixture_id",),
            unsafe_failure=False,
            focused_elapsed_ms=12,
            citation_coverage=1.0,
            cited_source_types=("memory_context",),
            cited_temporal_confirmed=True,
            cited_durable_id_hashes=("abc123",),
        )
        probe = ProbeResult(
            probe_id="multi_year",
            kind="correctness",
            hard_gate=True,
            k_pass=3,
            k_total=3,
            unsafe_failures=0,
            outcome_class="answered_grounded",
            citation_coverage=1.0,
            focused_elapsed_ms=12,
            variants=(variant,),
        )
        blob = self._packet(probe).to_json()
        parsed = json.loads(blob)
        self.assertEqual(parsed["schema_version"], "eval_packet.v1")
        self.assertNotIn("RAW_QUERY_SENTINEL", blob)
        self.assertNotIn("RAW_ANSWER_SENTINEL", blob)
        self.assertNotIn("query", blob)
        self.assertNotIn("answer_text", blob)

    def test_dirty_or_commit_mismatch_fails_packet(self):
        probe = ProbeResult(
            probe_id="dated_hit",
            kind="smoke",
            hard_gate=False,
            k_pass=3,
            k_total=3,
            unsafe_failures=0,
            outcome_class="answered_grounded",
            citation_coverage=1.0,
            focused_elapsed_ms=10,
            variants=(),
        )
        self.assertFalse(self._packet(probe, git_dirty=True).overall_pass)
        self.assertFalse(
            self._packet(probe, expected_commit_sha="abc", actual_commit_sha="def").overall_pass
        )

    def test_harness_run_emits_content_free_packet(self):
        from scripts.recall_flip_eval import harness, sandbox

        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            packet = harness.run_eval(
                sandbox_root=root,
                expect_commit=harness.current_commit_sha(),
                probe_ids=("dated_hit",),
                variants_per_probe=1,
                allow_dirty=True,
            )
            packet_path = Path(root) / "proof" / "eval_packet.json"
            self.assertTrue(packet_path.exists())
            blob = packet_path.read_text()
            self.assertEqual(json.loads(blob)["schema_version"], "eval_packet.v1")
            self.assertNotIn("SANDBOX", blob)
            self.assertNotIn("What did we note", blob)
            self.assertEqual(packet.run_id, json.loads(blob)["run_id"])

    def test_harness_aborts_on_commit_mismatch(self):
        from scripts.recall_flip_eval import harness

        with self.assertRaises(harness.HarnessAbort):
            harness.assert_run_parity(expect_commit="definitely-not-head", allow_dirty=True)

    def test_harness_restores_sandbox_patches_when_probe_raises(self):
        import core.memory.memory_scoring as scoring
        import memory.memory_manager as mm_mod
        from scripts.recall_flip_eval import harness, sandbox

        original_base_db = mm_mod.BASE_DB
        original_scoring_db = scoring._DB_PATH
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            with mock.patch.object(harness, "run_probe", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    harness.run_eval(
                        sandbox_root=root,
                        expect_commit=harness.current_commit_sha(),
                        probe_ids=("dated_hit",),
                        variants_per_probe=1,
                        allow_dirty=True,
                    )
            restored_base_db = mm_mod.BASE_DB
            restored_scoring_db = scoring._DB_PATH
            sandbox.restore_memory_patches()

        self.assertEqual(restored_base_db, original_base_db)
        self.assertEqual(restored_scoring_db, original_scoring_db)

    def _packet(self, *results, **overrides):
        kwargs = {
            "run_id": "run-1",
            "started_at_utc": "2026-05-30T00:00:00+00:00",
            "expected_commit_sha": "abc",
            "actual_commit_sha": "abc",
            "git_dirty": False,
            "probe_set_hash": "probehash",
            "fixture_manifest_hash": "fixturehash",
            "deterministic_chat_id": "offline_citation_echo.v1",
            "configured_model_id": "recorded-not-consulted",
            "debug_dump_count": 0,
            "debug_dump_manifest_hash": None,
            "results": results,
        }
        kwargs.update(overrides)
        return ProofPacket(**kwargs)


if __name__ == "__main__":
    unittest.main()
