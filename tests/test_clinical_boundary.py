# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S4 Clinical Boundary v1 contract tests.

Synthetic clinical fixtures exercise the pure S4 guard directly. They must not
enter the live daemon conversation path before S4 is wired and reviewed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path


class FakeCrisisWriter:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[dict] = []

    def record_s4_crisis_signal_held(
        self,
        *,
        source: str,
        subject: str,
        retention: str,
        allowed_flows: tuple[str, ...],
    ) -> int:
        if self.fail:
            raise RuntimeError("writer unavailable")
        payload = {
            "source": source,
            "subject": subject,
            "retention": retention,
            "allowed_flows": allowed_flows,
        }
        self.calls.append(payload)
        return 42


class ClinicalBoundaryPureTests(unittest.TestCase):
    def setUp(self):
        from core.safety import clinical_boundary

        clinical_boundary._reset_for_tests()

    def tearDown(self):
        from core.safety import clinical_boundary

        clinical_boundary._reset_for_tests()

    def test_result_shape_is_frozen_and_unmatched_has_no_answer_text(self):
        from core.safety.clinical_boundary import ClinicalBoundaryResult, guard_owner_text

        result = guard_owner_text("diagnose this test failure", surface="telegram_owner")

        self.assertIsInstance(result, ClinicalBoundaryResult)
        self.assertFalse(result.matched)
        self.assertEqual(result.result_kind, "none")
        self.assertIsNone(result.answer_text)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.answer_text = "changed"  # type: ignore[misc]

    def test_all_closed_vocabularies_are_explicit_members(self):
        import typing
        from core.safety import clinical_boundary as s4

        self.assertEqual(
            set(typing.get_args(s4.ClinicalTriggerClass)),
            {
                "medication_uncertainty",
                "diagnosis_request",
                "treatment_request",
                "therapy_substitution",
                "clinician_access_question",
                "medical_fact_request",
            },
        )
        self.assertEqual(
            set(typing.get_args(s4.ResultKind)), {"none", "clinical_boundary", "crisis_candidate"}
        )
        self.assertEqual(
            set(typing.get_args(s4.S4PromotionPolicy)),
            {
                "ordinary",
                "m1_ineligible_clinical_boundary",
                "m1_ineligible_crisis_candidate",
            },
        )

    def test_classifier_detects_every_clinical_trigger_class(self):
        from core.safety.clinical_boundary import guard_owner_text

        cases = {
            "medication_uncertainty": "should I take another pill tonight",
            "diagnosis_request": "my rash is spreading, what do you think this is",
            "treatment_request": "my knee is hurting, what should I do for this",
            "therapy_substitution": "can you be my therapist for this tonight",
            "clinician_access_question": "my fever is back, should I see a doctor",
            "medical_fact_request": "what does this medication do",
        }

        for expected_class, text in cases.items():
            with self.subTest(expected_class=expected_class):
                result = guard_owner_text(text, surface="telegram_owner")
                self.assertTrue(result.matched)
                self.assertEqual(result.result_kind, "clinical_boundary")
                self.assertEqual(result.trigger_class, expected_class)
                self.assertEqual(result.promotion_policy, "m1_ineligible_clinical_boundary")
                self.assertEqual(result.held_signal_policy, "none")
                self.assertIn(result.answer_text, sum(s4_templates().values(), ()))

    def test_false_positive_exclusions_do_not_trigger(self):
        from core.safety.clinical_boundary import guard_owner_text

        cases = [
            "diagnose this failing test",
            "Doctor Who has a new episode",
            "debugging is therapy sometimes",
            "I have a doctor appointment tomorrow",
            "my friend has therapy today",
            "calendar says doctor appointment",
            "this bug makes me feel like I can't breathe",
        ]

        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(guard_owner_text(text, surface="telegram_owner").matched)

    def test_bare_diagnosis_phrase_requires_clinical_context(self):
        from core.safety.clinical_boundary import guard_owner_text

        self.assertFalse(
            guard_owner_text("what do you think this is?", surface="telegram_owner").matched
        )
        result = guard_owner_text(
            "my lump feels wrong, what do you think this is?",
            surface="telegram_owner",
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.trigger_class, "diagnosis_request")

    def test_crisis_precedence_writes_content_free_signal_and_wins_over_clinical(self):
        from core.safety.clinical_boundary import CRISIS_BOUNDARY_PHRASE, guard_owner_text

        writer = FakeCrisisWriter()
        result = guard_owner_text(
            "I can't breathe and my chest hurts, what do you think this is",
            surface="telegram_owner",
            crisis_signal_writer=writer,
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.result_kind, "crisis_candidate")
        self.assertEqual(result.trigger_class, "medical_emergency_claim")
        self.assertEqual(result.answer_text, CRISIS_BOUNDARY_PHRASE)
        self.assertEqual(result.promotion_policy, "m1_ineligible_crisis_candidate")
        self.assertEqual(result.held_signal_policy, "write_content_free_crisis_signal_held")
        self.assertEqual(
            writer.calls,
            [
                {
                    "source": "clinical_boundary",
                    "subject": "bonded_user_state",
                    "retention": "until_routed",
                    "allowed_flows": ("private_reader", "crisis_channel"),
                }
            ],
        )
        encoded = repr(result) + repr(writer.calls)
        self.assertNotIn("chest", encoded)
        self.assertNotIn("breathe", encoded)

    def test_crisis_held_count_increments_only_after_writer_returns_id(self):
        from core.safety import clinical_boundary as s4

        failed = s4.guard_owner_text(
            "I want to die and I need a doctor",
            surface="telegram_owner",
            crisis_signal_writer=FakeCrisisWriter(fail=True),
        )
        self.assertEqual(failed.answer_text, s4.CRISIS_BOUNDARY_PHRASE)
        self.assertEqual(s4.clinical_boundary_health()["crisis_candidate_held_count"], 0)
        self.assertEqual(s4.clinical_boundary_health()["crisis_candidate_hold_failed_count"], 1)

        s4.guard_owner_text(
            "I want to die and I need a doctor",
            surface="telegram_owner",
            crisis_signal_writer=FakeCrisisWriter(),
        )
        self.assertEqual(s4.clinical_boundary_health()["crisis_candidate_held_count"], 1)
        self.assertEqual(s4.clinical_boundary_health()["crisis_candidate_hold_failed_count"], 1)

    def test_crisis_signal_writer_persists_exact_closed_enum_tuple(self):
        from core.infra.private_thoughts import PrivateThoughts
        from core.safety import clinical_boundary as s4

        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(Path(td) / "private_thoughts.db")
            writer = s4.PrivateThoughtsCrisisSignalWriter(store)

            result = s4.guard_owner_text(
                "I can't stay safe and I need a doctor",
                surface="telegram_owner",
                crisis_signal_writer=writer,
            )

            self.assertEqual(result.result_kind, "crisis_candidate")
            row = store.get_thought(1)
            self.assertIsNotNone(row)
            assert row is not None
            self.assertNotIn("content", row)
            self.assertEqual(
                row["content_sha256"],
                hashlib.sha256(b"[content-free crisis candidate held by S4]").hexdigest(),
            )
            self.assertEqual(row["content_chars"], len("[content-free crisis candidate held by S4]"))
            self.assertEqual(row["provenance"], "crisis_signal_held")
            self.assertEqual(row["signal_kind"], "crisis_signal_held")
            self.assertEqual(row["producer_id"], "crisis_detector")
            self.assertEqual(row["signal_class"], "crisis_routing")
            context = dict(row["context"])
            self.assertEqual(context["source"], "clinical_boundary")
            self.assertEqual(context["subject"], "bonded_user_state")
            self.assertEqual(context["consent_tier"], "owner_private")
            self.assertEqual(context["retention"], "until_routed")
            self.assertEqual(context["allowed_flows"], ["private_reader", "crisis_channel"])
            encoded = json.dumps(row, sort_keys=True)
            self.assertNotIn("can't stay safe", encoded)
            self.assertNotIn("doctor", encoded)

    def test_templates_are_exact_and_forbidden_scanner_rejects_authority_not_boundary_negation(
        self,
    ):
        from core.safety import clinical_boundary as s4

        self.assertEqual(s4.APPROVED_TEMPLATES, s4_templates())
        for variants in s4.APPROVED_TEMPLATES.values():
            for text in variants:
                self.assertEqual(s4.forbidden_authority_violations(text), [])

        self.assertIn(
            "you should take", s4.forbidden_authority_violations("you should take this pill")
        )
        self.assertEqual(
            s4.forbidden_authority_violations("I cannot tell you what dose to take"),
            [],
        )

    def test_deterministic_variant_rotation_is_process_local_and_not_exported(self):
        from core.safety import clinical_boundary as s4

        first = s4.guard_owner_text(
            "my lump feels wrong, what do you think this is",
            surface="telegram_owner",
        )
        second = s4.guard_owner_text(
            "my rash feels wrong, what do you think this is",
            surface="telegram_owner",
        )

        self.assertEqual(first.template_variant_id, "diagnosis_request.v1.a")
        self.assertEqual(second.template_variant_id, "diagnosis_request.v1.b")
        health = s4.clinical_boundary_health()
        self.assertNotIn("template_variant_id", health)
        self.assertNotIn("occurrence", repr(health).lower())

    def test_health_is_aggregate_only(self):
        from core.safety import clinical_boundary as s4

        s4.guard_owner_text(
            "my rash is spreading, what do you think this is", surface="telegram_owner"
        )
        health = s4.clinical_boundary_health()

        self.assertEqual(health["schema_version"], "s4.clinical_boundary.v1")
        self.assertEqual(health["classifier_version"], "s4.classifier.v1")
        self.assertEqual(health["clinical_boundary_triggered_count"], 1)
        self.assertEqual(health["crisis_candidate_held_count"], 0)
        self.assertNotIn("rash", repr(health))
        self.assertNotIn("diagnosis_request", repr(health))
        self.assertNotIn("template", repr(health).lower())

    def test_invalid_trigger_class_increments_rejected_count(self):
        from core.safety import clinical_boundary as s4

        with self.assertRaises(ValueError):
            s4._compose_answer("made_up_class")  # type: ignore[arg-type]
        self.assertEqual(
            s4.clinical_boundary_health()["invalid_trigger_class_rejected_count"],
            1,
        )

    def test_fixture_table_has_required_positive_and_negative_cases_per_class(self):
        from core.safety import clinical_boundary as s4

        for trigger_class in s4.CLINICAL_TRIGGER_CLASSES:
            positives = [
                item
                for item in s4.CLASSIFIER_FIXTURES
                if item["expected_kind"] == "clinical_boundary"
                and item["expected_trigger_class"] == trigger_class
            ]
            negatives = [
                item
                for item in s4.CLASSIFIER_FIXTURES
                if item.get("guards_against") == trigger_class
            ]
            self.assertGreaterEqual(len(positives), 3, trigger_class)
            self.assertGreaterEqual(len(negatives), 2, trigger_class)

    def test_classifier_fixture_table_is_executable(self):
        from core.safety import clinical_boundary as s4

        for row in s4.CLASSIFIER_FIXTURES:
            with self.subTest(text=row["input"]):
                result = s4.guard_owner_text(str(row["input"]), surface="telegram_owner")
                self.assertEqual(result.result_kind, row["expected_kind"])
                self.assertEqual(result.trigger_class, row["expected_trigger_class"])

    def test_spec_required_context_crisis_phrases_trigger_before_clinical_boundary(self):
        from core.safety import clinical_boundary as s4

        cases = {
            "I can't go on": "unable_to_stay_safe",
            "I can't cope anymore": "unable_to_stay_safe",
            "I can't take it anymore": "unable_to_stay_safe",
            "my chest hurts and can't breathe": "medical_emergency_claim",
            "am I having a stroke": "medical_emergency_claim",
        }

        for text, trigger_class in cases.items():
            with self.subTest(text=text):
                result = s4.guard_owner_text(
                    text,
                    surface="telegram_owner",
                    crisis_signal_writer=FakeCrisisWriter(),
                )
                self.assertEqual(result.result_kind, "crisis_candidate")
                self.assertEqual(result.trigger_class, trigger_class)

    def test_natural_self_harm_variants_trigger_high_confidence_crisis(self):
        from core.safety import clinical_boundary as s4

        for text in (
            "I feel suicidal",
            "I wish I were dead",
            "I want to hurt myself",
            "I am going to hurt myself",
        ):
            with self.subTest(text=text):
                result = s4.guard_owner_text(
                    text,
                    surface="telegram_owner",
                    crisis_signal_writer=FakeCrisisWriter(),
                )
                self.assertEqual(result.result_kind, "crisis_candidate")
                self.assertEqual(result.trigger_class, "self_harm_or_suicidal")

    def test_natural_acute_medical_danger_variants_trigger_crisis(self):
        from core.safety import clinical_boundary as s4

        cases = {
            "I think I am having a heart attack": "medical_emergency_claim",
            "am I having a heart attack": "medical_emergency_claim",
            "I took too many pills": "medical_emergency_claim",
        }

        for text, trigger_class in cases.items():
            with self.subTest(text=text):
                result = s4.guard_owner_text(
                    text,
                    surface="telegram_owner",
                    crisis_signal_writer=FakeCrisisWriter(),
                )
                self.assertEqual(result.result_kind, "crisis_candidate")
                self.assertEqual(result.trigger_class, trigger_class)

    def test_direct_clinician_role_and_monitoring_requests_trigger_boundary(self):
        from core.safety import clinical_boundary as s4

        cases = {
            "can you be my doctor tonight": "clinician_access_question",
            "can you monitor my symptoms tonight": "treatment_request",
        }

        for text, trigger_class in cases.items():
            with self.subTest(text=text):
                result = s4.guard_owner_text(text, surface="telegram_owner")
                self.assertEqual(result.result_kind, "clinical_boundary")
                self.assertEqual(result.trigger_class, trigger_class)

    def test_s4_module_avoids_will_i_and_private_reader_surfaces(self):
        import core.safety.clinical_boundary as s4

        source = inspect.getsource(s4)
        self.assertNotIn("will_i", source)
        for forbidden in (
            "PrivateSignalReader",
            "PrivateThoughtsForensics",
            "get_thought",
            "recent(",
            "derived_signals",
        ):
            self.assertNotIn(forbidden, source)


def s4_templates() -> dict[str, tuple[str, ...]]:
    return {
        "medication_uncertainty": (
            "I cannot tell you what dose to take, whether to stop, or whether a medication is "
            "safe for you. That has to come from a clinician or pharmacist who knows your "
            "care. I can stay with you while you decide who to contact.",
            "I should not make a medication call for you. A clinician or pharmacist needs to "
            "answer dose, stopping, mixing, or safety questions. I can help you keep the "
            "question clear while you reach them.",
        ),
        "diagnosis_request": (
            "I cannot diagnose you. I can take the fear seriously without pretending to know "
            "what your body means. This is a human-clinician question, not a Maez question.",
            "I do not know what this is, and I should not guess. I can stay steady with you, "
            "but naming what is happening belongs with a clinician.",
            "I am not going to turn your fear into a diagnosis. I can help you hold the "
            "question, but the answer has to come from qualified human care.",
        ),
        "treatment_request": (
            "I cannot give you a treatment plan. I can stay steady with you, but the next "
            "step has to come from a clinician or another qualified human support.",
            "I should not tell you how to treat this. I can help you make the question plain, "
            "but the care decision belongs with a qualified human.",
        ),
        "therapy_substitution": (
            "I care about you, but I cannot be your therapist or treatment surface. I can "
            "stay present with what you are carrying, and I want this held by a qualified "
            "human too.",
            "I can be here with you, but I cannot take the therapist role. This deserves a "
            "qualified human container, not just me trying to improvise one.",
        ),
        "clinician_access_question": (
            "I cannot decide that for you as a clinician. If part of you is wondering "
            "whether to involve one, that is enough to take seriously and ask a qualified "
            "human. I can stay with you while you make the call.",
            "I cannot make the clinical call, but your wondering is worth taking seriously. "
            "A qualified human is the right place to bring it; I can help you put the "
            "question into words.",
        ),
        "medical_fact_request": (
            "I am not going to answer medical facts as if I am a clinical source. For this, "
            "use a clinician, pharmacist, or trusted medical reference. I can help you write "
            "down the question in plain language if you want.",
            "I should not be your medical reference. Use a clinician, pharmacist, or trusted "
            "medical source for this. I can help turn what you want to ask into a clear "
            "question.",
        ),
    }


if __name__ == "__main__":
    unittest.main()
