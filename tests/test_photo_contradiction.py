import subprocess
import sys
import types
import unittest
from unittest import mock

from core.routing.photo_contradiction import (
    ClaimVerdict,
    extract_photo_claims,
    normalize_claim_text,
)


class PhotoClaimExtraction(unittest.TestCase):
    def test_extracts_direct_perceptual_sentences(self):
        reply = (
            "The screenshot title says WWDC 2026 [E1]. "
            "The chart lists Q4_0 as 2.9 GB [E1]. "
            "This matters for what we are building."
        )
        claims = extract_photo_claims(reply)
        self.assertEqual(
            [c.text for c in claims],
            [
                "The screenshot title says WWDC 2026.",
                "The chart lists Q4_0 as 2.9 GB.",
            ],
        )
        self.assertTrue(all(c.direct_perceptual for c in claims))
        self.assertEqual([c.claim_id for c in claims], ["C1", "C2"])
        self.assertEqual([c.evidence_label for c in claims], ["E1", "E1"])

    def test_excludes_interpretive_advice_and_project_meaning(self):
        reply = (
            "This matters for Maez's roadmap [E1]. "
            "You may want to test it later. "
            "I would treat this as promising."
        )
        self.assertEqual(extract_photo_claims(reply), [])

    def test_claims_are_draft_bound_no_generated_paraphrase(self):
        reply = "The image shows a Reddit screenshot [E1]."
        claims = extract_photo_claims(reply)
        self.assertEqual(
            [c.text for c in claims],
            ["The image shows a Reddit screenshot."],
        )
        normalized_reply = normalize_claim_text(reply)
        self.assertIn(normalize_claim_text(claims[0].text), normalized_reply)

    def test_mixed_claim_keeps_sentence_or_skips_never_invents_smaller_claim(self):
        reply = "The image shows WWDC 2026, which is a developer conference [E1]."
        claims = extract_photo_claims(reply)
        self.assertEqual(len(claims), 1)
        self.assertEqual(
            claims[0].text,
            "The image shows WWDC 2026, which is a developer conference.",
        )
        self.assertNotIn("The image shows WWDC 2026.", [c.text for c in claims])

    def test_ambiguous_sentence_is_omitted_not_false_demoted(self):
        reply = "It seems important and probably relates to the current work [E1]."
        self.assertEqual(extract_photo_claims(reply), [])

    def test_bare_non_photo_verbs_are_omitted(self):
        reply = (
            "The presenter says WWDC 2026 is next week [E1]. "
            "The article lists three possible launch dates [E1]."
        )
        self.assertEqual(extract_photo_claims(reply), [])

    def test_claim_cap_truncates_to_first_five(self):
        reply = " ".join(
            f"The screenshot lists item {i} [E1]." for i in range(1, 8)
        )
        claims = extract_photo_claims(reply, limit=5)
        self.assertEqual(len(claims), 5)
        self.assertEqual(claims[-1].text, "The screenshot lists item 5.")

    def test_nonpositive_claim_cap_returns_no_claims(self):
        reply = "The screenshot lists item 1 [E1]."
        self.assertEqual(extract_photo_claims(reply, limit=0), [])
        self.assertEqual(extract_photo_claims(reply, limit=-1), [])

    def test_normalize_removes_citation_without_space_before_punctuation(self):
        self.assertEqual(
            normalize_claim_text("The screenshot title says WWDC 2026 [E1]."),
            "The screenshot title says WWDC 2026.",
        )


class LocalVerifierContract(unittest.TestCase):
    def test_importing_module_in_clean_process_does_not_import_transformers(self):
        code = (
            "import sys; "
            "import core.routing.photo_contradiction; "
            "print('transformers' in sys.modules)"
        )
        out = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
        self.assertEqual(out, "False")

    def test_module_contains_no_network_client_imports(self):
        from pathlib import Path

        src = Path("core/routing/photo_contradiction.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "huggingface_hub", "urllib.request"):
            self.assertNotIn(forbidden, src)

    def test_loader_constructs_pipeline_with_local_only_top_level_kwargs(self):
        import os
        from pathlib import Path
        from core.routing.photo_contradiction import _load_transformers_pipeline

        artifact_dir = Path("/tmp/local-nli-artifact")
        fake_callable = object()
        calls = []

        def fake_pipeline(task, **kwargs):
            calls.append((task, kwargs))
            self.assertEqual(task, "text-classification")
            self.assertEqual(kwargs["model"], str(artifact_dir))
            self.assertEqual(kwargs["tokenizer"], str(artifact_dir))
            self.assertIsNone(kwargs["top_k"])
            self.assertIs(kwargs["local_files_only"], True)
            self.assertNotIn("model_kwargs", kwargs)
            self.assertNotIn("tokenizer_kwargs", kwargs)
            self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "already-set")
            return fake_callable

        fake_transformers = types.SimpleNamespace(pipeline=fake_pipeline)
        with mock.patch.dict(
            sys.modules,
            {"transformers": fake_transformers},
        ), mock.patch.dict(
            os.environ,
            {"TRANSFORMERS_OFFLINE": "already-set"},
        ):
            loaded = _load_transformers_pipeline(artifact_dir)

        self.assertIs(loaded, fake_callable)
        self.assertEqual(len(calls), 1)

    def test_missing_nli_artifact_is_unavailable_without_model_import(self):
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        with mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            side_effect=AssertionError("must not import"),
        ):
            verifier = LocalNLIContradictionVerifier(
                artifact_dir="/tmp/definitely-missing-maez-nli"
            )
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("missing", verdict.reason)

    def test_manifest_repo_mismatch_is_unavailable(self):
        import json
        import tempfile
        from pathlib import Path
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "bakeoff_manifest.json").write_text(
                json.dumps({
                    "repo_id": "owner/wrong",
                    "revision": "abc",
                    "sha256": "f00",
                }),
                encoding="utf-8",
            )
            verifier = LocalNLIContradictionVerifier(artifact_dir=str(d))
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("repo_id", verdict.reason)

    def test_missing_manifest_is_unavailable_without_model_import(self):
        import tempfile
        from pathlib import Path
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            side_effect=AssertionError("must not import"),
        ):
            Path(tmp).mkdir(exist_ok=True)
            verifier = LocalNLIContradictionVerifier(artifact_dir=tmp)
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("manifest", verdict.reason)

    def test_nli_maps_contradiction_probability_to_label(self):
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        class FakePipeline:
            def __call__(self, pair):
                self.pair = pair
                return [[
                    {"label": "contradiction", "score": 0.91},
                    {"label": "neutral", "score": 0.05},
                    {"label": "entailment", "score": 0.04},
                ]]

        fake_pipeline = FakePipeline()
        with mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            return_value=fake_pipeline,
        ), mock.patch(
            "core.routing.photo_contradiction._read_manifest",
            return_value={
                "repo_id": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                "revision": "abc",
                "sha256": "deadbeef",
            },
        ), mock.patch(
            "core.routing.photo_contradiction.Path.is_dir",
            return_value=True,
        ):
            verifier = LocalNLIContradictionVerifier(
                artifact_dir="/tmp/pretend-nli",
                threshold=0.5,
            )
            verdict = verifier.predict("The image says 2026.", "The image says 2024.")
        self.assertEqual(
            fake_pipeline.pair,
            {
                "text": "The image says 2026.",
                "text_pair": "The image says 2024.",
            },
        )
        self.assertEqual(verdict.label, "contradicts")
        self.assertLess(verdict.score, 0.5)
        self.assertEqual(verdict.model_id, "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
        self.assertEqual(verdict.revision, "abc")
        self.assertEqual(verdict.sha256, "deadbeef")
        self.assertGreaterEqual(verdict.latency_s, 0.0)

    def test_nli_score_helper_handles_label_aliases(self):
        from core.routing.photo_contradiction import nli_grounded_score_from_output

        self.assertAlmostEqual(
            nli_grounded_score_from_output([
                {"label": "contradiction", "score": 0.7},
                {"label": "neutral", "score": 0.2},
                {"label": "entailment", "score": 0.1},
            ]),
            0.3,
        )
        self.assertAlmostEqual(
            nli_grounded_score_from_output([
                {"label": "contradictory", "score": 0.2},
                {"label": "neutral", "score": 0.8},
            ]),
            0.8,
        )

    def test_nli_score_helper_fails_closed_on_unknown_or_index_labels(self):
        from core.routing.photo_contradiction import nli_grounded_score_from_output

        with self.assertRaises(ValueError):
            nli_grounded_score_from_output([
                {"label": "mystery", "score": 0.9},
            ])
        with self.assertRaises(ValueError):
            nli_grounded_score_from_output([
                {"label": "LABEL_0", "score": 0.91},
                {"label": "LABEL_1", "score": 0.04},
                {"label": "LABEL_2", "score": 0.05},
            ])

    def test_load_and_predict_failures_return_unavailable(self):
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        with mock.patch(
            "core.routing.photo_contradiction._read_manifest",
            return_value={
                "repo_id": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                "revision": "abc",
                "sha256": "deadbeef",
            },
        ), mock.patch(
            "core.routing.photo_contradiction.Path.is_dir",
            return_value=True,
        ), mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            side_effect=RuntimeError("bad artifact"),
        ):
            verifier = LocalNLIContradictionVerifier(artifact_dir="/tmp/pretend-nli")
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("bad artifact", verdict.reason)

        class BrokenPipeline:
            def __call__(self, pair):
                raise RuntimeError("predict broke")

        with mock.patch(
            "core.routing.photo_contradiction._read_manifest",
            return_value={
                "repo_id": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                "revision": "abc",
                "sha256": "deadbeef",
            },
        ), mock.patch(
            "core.routing.photo_contradiction.Path.is_dir",
            return_value=True,
        ), mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            return_value=BrokenPipeline(),
        ):
            verifier = LocalNLIContradictionVerifier(artifact_dir="/tmp/pretend-nli")
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("predict", verdict.reason)


class FakeVerifier:
    def __init__(self, labels):
        self.labels = list(labels)
        self.calls = []

    def predict(self, premise, hypothesis):
        self.calls.append((premise, hypothesis))
        label = self.labels.pop(0)
        return ClaimVerdict(
            label=label,
            score=0.1 if label == "contradicts" else 0.9,
            latency_s=0.01,
            model_id="fake-nli",
            revision="rev",
            sha256="sha",
            reason="fake-unavailable" if label == "unavailable" else None,
        )


class RaisingVerifier:
    def __init__(self):
        self.calls = []

    def predict(self, premise, hypothesis):
        self.calls.append((premise, hypothesis))
        raise RuntimeError("predict exploded")


class ContradictionReceiptAggregation(unittest.TestCase):
    PREMISE = "The screenshot title says WWDC 2026."

    def test_clear_receipt_for_grounded_direct_claims(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        verifier = FakeVerifier(["grounded"])
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="The screenshot title says WWDC 2026 [E1].",
            verifier=verifier,
        )

        self.assertEqual(receipt.state, "grounded")
        self.assertEqual(receipt.reason, "clear")
        self.assertEqual(receipt.claim_count, 1)
        self.assertEqual(receipt.contradiction_count, 0)
        self.assertFalse(receipt.claim_limit_exceeded)
        self.assertIsNone(receipt.sense_note)
        self.assertEqual(
            verifier.calls,
            [(self.PREMISE, "The screenshot title says WWDC 2026.")],
        )
        self.assertEqual(receipt.claim_details[0].claim_id, "C1")
        self.assertEqual(receipt.claim_details[0].verdict_label, "grounded")
        self.assertEqual(receipt.claim_details[0].score, 0.9)

    def test_trust_demoted_for_direct_photo_contradiction(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="The screenshot title says WWDC 2024 [E1].",
            verifier=FakeVerifier(["contradicts"]),
        )

        self.assertEqual(receipt.state, "trust_demoted")
        self.assertEqual(receipt.reason, "trust_demoted")
        self.assertEqual(receipt.claim_count, 1)
        self.assertEqual(receipt.contradiction_count, 1)
        self.assertEqual(receipt.contradicted_claim_ids, ("C1",))
        self.assertIn("Contradiction sense fired", receipt.sense_note)
        self.assertIn('Claim C1: "The screenshot title says WWDC 2024."', receipt.sense_note)
        self.assertIn("Conflicts with E1: The screenshot title says WWDC 2026.", receipt.sense_note)
        self.assertEqual(receipt.claim_details[0].verdict_label, "contradicts")

    def test_sense_note_clips_long_contradicted_claim_text(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        tokens = [f"token{i:03d}" for i in range(90)]
        reply = f"The screenshot lists {' '.join(tokens)} [E1]."
        receipt = check_photo_contradictions(
            premise="The screenshot lists a much shorter visible item.",
            reply=reply,
            verifier=FakeVerifier(["contradicts"]),
        )

        claim_line = next(
            line for line in receipt.sense_note.splitlines() if line.startswith("- Claim C1:")
        )
        self.assertLessEqual(len(claim_line), 520)
        self.assertIn("The screenshot lists token000 token001", claim_line)
        self.assertIn("...", claim_line)
        self.assertNotIn("token089", claim_line)
        self.assertIn("token089", receipt.claim_details[0].text)

    def test_non_perceptual_reply_is_claim_extraction_unavailable(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        verifier = FakeVerifier(["contradicts"])
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="This matters for the roadmap [E1].",
            verifier=verifier,
        )

        self.assertEqual(receipt.state, "unavailable")
        self.assertEqual(receipt.reason, "claim_extraction_unavailable")
        self.assertEqual(receipt.claim_count, 0)
        self.assertEqual(receipt.contradiction_count, 0)
        self.assertIsNone(receipt.sense_note)
        self.assertEqual(verifier.calls, [])

    def test_multi_photo_analysis_is_unsupported(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        verifier = FakeVerifier(["grounded"])
        receipt = check_photo_contradictions(
            premise="Image 1: a chart. Image 2: a screenshot.",
            reply="The screenshot shows a chart [E1].",
            verifier=verifier,
        )

        self.assertEqual(receipt.state, "unavailable")
        self.assertEqual(receipt.reason, "multi_photo_unsupported")
        self.assertEqual(receipt.claim_count, 0)
        self.assertEqual(verifier.calls, [])

    def test_claim_limit_is_honestly_reported(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        reply = " ".join(
            f"The screenshot lists item {i} [E1]." for i in range(1, 8)
        )
        verifier = FakeVerifier(["grounded"] * 5)
        receipt = check_photo_contradictions(
            premise="The screenshot lists items 1 through 7.",
            reply=reply,
            verifier=verifier,
            claim_limit=5,
        )

        self.assertEqual(receipt.state, "grounded")
        self.assertEqual(receipt.reason, "clear")
        self.assertEqual(receipt.claim_count, 5)
        self.assertEqual(receipt.contradiction_count, 0)
        self.assertTrue(receipt.claim_limit_exceeded)
        self.assertEqual(len(verifier.calls), 5)
        self.assertEqual(
            [d.claim_id for d in receipt.claim_details],
            ["C1", "C2", "C3", "C4", "C5"],
        )

    def test_feature_flag_default_off_and_explicit_truthy_enabled(self):
        from core.routing.photo_contradiction import photo_contradiction_sense_enabled

        self.assertFalse(photo_contradiction_sense_enabled(env={}))
        for value in ("1", "true", "TRUE", "yes", "on"):
            self.assertTrue(
                photo_contradiction_sense_enabled(
                    env={"MAEZ_PHOTO_CONTRADICTION_SENSE": value}
                )
            )
        for value in ("", "0", "false", "no", "off", "please"):
            self.assertFalse(
                photo_contradiction_sense_enabled(
                    env={"MAEZ_PHOTO_CONTRADICTION_SENSE": value}
                )
            )

    def test_deterministic_fallback_skips_contradiction_check(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        verifier = FakeVerifier(["contradicts"])
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="I'm confident I saw [E1]: The screenshot title says WWDC 2026.",
            verifier=verifier,
            lane1_receipt_reason="deterministic_fallback",
        )

        self.assertEqual(receipt.state, "grounded")
        self.assertEqual(receipt.reason, "deterministic_fallback")
        self.assertEqual(receipt.claim_count, 0)
        self.assertEqual(receipt.contradiction_count, 0)
        self.assertEqual(verifier.calls, [])

    def test_verifier_exception_is_unavailable_not_crash(self):
        from core.routing.photo_contradiction import check_photo_contradictions

        verifier = RaisingVerifier()
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="The screenshot title says WWDC 2026 [E1].",
            verifier=verifier,
        )

        self.assertEqual(receipt.state, "unavailable")
        self.assertEqual(receipt.reason, "verifier_unavailable")
        self.assertEqual(receipt.claim_count, 1)
        self.assertEqual(receipt.contradiction_count, 0)
        self.assertEqual(receipt.claim_details[0].verdict_label, "unavailable")
        self.assertIn("predict exploded", receipt.claim_details[0].verifier_reason)


if __name__ == "__main__":
    unittest.main()
