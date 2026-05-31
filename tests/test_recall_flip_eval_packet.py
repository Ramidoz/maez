import dataclasses
import json
import unittest

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
