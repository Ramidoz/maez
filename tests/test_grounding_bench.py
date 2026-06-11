import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "grounding_bench"))

from corpus_schema import validate_corpus, MODES, EVIDENCE_KINDS, LABELS  # noqa: E402,F401
from adapter_prompt import (  # noqa: E402
    ENTAILMENT_SYSTEM_PROMPT, build_entailment_user_prompt, parse_support_verdict)
import verifiers as V  # noqa: E402
import bench_grounding as B  # noqa: E402


class CorpusSchemaTests(unittest.TestCase):
    def _row(self, **over):
        base = dict(id="x-1", mode="grounded_positive", source="synthetic",
                    evidence_kind="claimable_present", evidence="E", claim="C",
                    expected="SUPPORTED", strict_rule=False, rationale="r")
        base.update(over)
        return base

    def test_valid_row_passes(self):
        validate_corpus([self._row()])  # should not raise

    def test_missing_field_raises(self):
        bad = self._row()
        del bad["rationale"]
        with self.assertRaises(ValueError):
            validate_corpus([bad])

    def test_bad_enum_raises(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(expected="MAYBE")])

    def test_claimable_absent_must_be_abstain(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(evidence_kind="claimable_absent", expected="SUPPORTED")])

    def test_abstain_requires_claimable_absent(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(evidence_kind="claimable_present", expected="ABSTAIN_EXPECTED")])

    def test_duplicate_ids_raise(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(id="dup"), self._row(id="dup")])

    def test_empty_rationale_raises(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(rationale="   ")])


class AdapterPromptTests(unittest.TestCase):
    def test_user_prompt_has_evidence_and_claim(self):
        p = build_entailment_user_prompt("EV-TEXT", "CL-TEXT")
        self.assertIn("EV-TEXT", p)
        self.assertIn("CL-TEXT", p)

    def test_system_prompt_is_entailment_not_overclaim(self):
        sp = ENTAILMENT_SYSTEM_PROMPT.lower()
        self.assertIn("evidence", sp)
        self.assertIn("supported", sp)
        self.assertNotIn("signals available", sp)   # not the overclaim contract
        self.assertNotIn("self-history", sp)

    def test_parse_verdict(self):
        self.assertEqual(parse_support_verdict("SUPPORTED\nbecause..."), "SUPPORTED")
        self.assertEqual(parse_support_verdict("unsupported: the claim..."), "UNSUPPORTED")
        self.assertEqual(parse_support_verdict(""), "EMPTY")
        self.assertTrue(parse_support_verdict("maybe idk").startswith("UNPARSED"))


class VerifierTests(unittest.TestCase):
    def test_minicheck_binary_maps_to_label(self):
        v = V.MinicheckVerifier()
        with mock.patch.object(v, "_predict_raw", return_value=1):
            self.assertEqual(v.support("E", "C")[0], "SUPPORTED")
        with mock.patch.object(v, "_predict_raw", return_value=0):
            self.assertEqual(v.support("E", "C")[0], "UNSUPPORTED")

    def test_hhem_threshold_mapping(self):
        v = V.HhemVerifier(threshold=0.5)
        with mock.patch.object(v, "_score_raw", return_value=0.8):
            self.assertEqual(v.support("E", "C")[0], "SUPPORTED")
        with mock.patch.object(v, "_score_raw", return_value=0.2):
            self.assertEqual(v.support("E", "C")[0], "UNSUPPORTED")
        self.assertEqual(v.last_score, 0.2)

    def test_hhem_unconfigured_revision_errors_without_download(self):
        # Option A: unset HHEM_REVISION -> clear ERROR, never touches network/remote-code.
        self.assertIsNone(V.HHEM_REVISION)
        v = V.HhemVerifier(threshold=0.5)        # NOT mocked
        label, _ = v.support("E", "C")
        self.assertEqual(label, "ERROR(HhemRevisionUnconfigured)")

    def test_4b_adapter_parses_endpoint(self):
        v = V.FourBAdapterVerifier(url="http://x", model="m")
        with mock.patch.object(v, "_chat_raw", return_value="SUPPORTED\nreason"):
            self.assertEqual(v.support("E", "C")[0], "SUPPORTED")


class HarnessTests(unittest.TestCase):
    def test_abstain_precondition_calls_no_model(self):
        verifier = mock.MagicMock()
        case = {"id": "abs-1", "mode": "no_evidence_abstain", "evidence_kind": "claimable_absent",
                "evidence": "", "claim": "C", "expected": "ABSTAIN_EXPECTED"}
        label, _ = B.judge_case(verifier, case)
        self.assertEqual(label, "ABSTAIN")
        verifier.support.assert_not_called()      # the box was never weighed

    def test_present_evidence_calls_model(self):
        verifier = mock.MagicMock()
        verifier.support.return_value = ("UNSUPPORTED", 0.01)
        case = {"id": "x", "mode": "cited_but_unsupported", "evidence_kind": "claimable_present",
                "evidence": "E", "claim": "C", "expected": "UNSUPPORTED"}
        label, _ = B.judge_case(verifier, case)
        self.assertEqual(label, "UNSUPPORTED")
        verifier.support.assert_called_once()

    def test_false_negative_tally_per_mode(self):
        per_item = [
            {"mode": "stale_over_current", "expected": "UNSUPPORTED", "got": "SUPPORTED"},
            {"mode": "stale_over_current", "expected": "UNSUPPORTED", "got": "UNSUPPORTED"},
            {"mode": "grounded_positive", "expected": "SUPPORTED", "got": "UNSUPPORTED"},
        ]
        fn = B.false_negatives_by_mode(per_item)
        self.assertEqual(fn["stale_over_current"], {"false_neg": 1, "total_unsupported": 2})
        self.assertNotIn("grounded_positive", fn)   # no UNSUPPORTED cases -> not an FN mode


class ReportTests(unittest.TestCase):
    def test_markdown_foregrounds_false_negatives(self):
        summaries = [{
            "label": "hhem@0.5", "n": 26,
            "false_neg_by_mode": {"stale_over_current": {"false_neg": 2, "total_unsupported": 4},
                                  "fabricated_false_specific": {"false_neg": 0, "total_unsupported": 5}},
            "false_positives": 1, "abstain_ok": 3, "abstain_wrong": 0, "errors": 0,
            "matches": 22, "latency_p50": 0.05, "latency_p95": 0.09, "per_item": [],
        }]
        md = B.render_markdown(summaries)
        self.assertIn("False-negatives by mode", md)
        self.assertIn("stale_over_current", md)
        self.assertIn("2/4", md)          # the dangerous miss, shown as a fraction
        self.assertIn("hhem@0.5", md)


if __name__ == "__main__":
    unittest.main()
