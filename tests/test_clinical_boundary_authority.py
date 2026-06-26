"""S4 authority-not-intimacy witness tests."""

from __future__ import annotations

import unittest

from core.safety.clinical_boundary import guard_owner_text


def _result(text: str):
    return guard_owner_text(text, surface="telegram_owner")


def _kind(text: str) -> str:
    return _result(text).result_kind


class S4AuthorityNotIntimacyTest(unittest.TestCase):
    def test_bare_mind_emotion_is_none(self):
        for text in (
            "i am anxious about nvidia stock",
            "i have been so depressed lately",
            "i feel overwhelmed and grieving",
        ):
            with self.subTest(text=text):
                self.assertEqual(_kind(text), "none")

    def test_bare_body_fear_is_none(self):
        self.assertEqual(_kind("i am scared my chest has been hurting"), "none")

    def test_side_door_closed(self):
        self.assertEqual(_kind("i am so scared and something feels wrong"), "none")

    def test_authority_requests_still_clinical(self):
        cases = {
            "do i have depression": "diagnosis_request",
            "do i have ptsd": "diagnosis_request",
            "do i have ocd": "diagnosis_request",
            "do i have bipolar disorder": "diagnosis_request",
            "what should i do about my chest pain": "treatment_request",
            "what should i do about ptsd": "treatment_request",
            "be my therapist": "therapy_substitution",
            "what dose should i take of this medication": "medication_uncertainty",
        }
        for text, trigger_class in cases.items():
            with self.subTest(text=text):
                result = _result(text)
                self.assertEqual(result.result_kind, "clinical_boundary")
                self.assertEqual(result.trigger_class, trigger_class)

    def test_crisis_paths_unchanged(self):
        cases = {
            "i cant breathe": "medical_emergency_claim",
            "i think i am having a heart attack": "medical_emergency_claim",
            "i want to hurt myself": "self_harm_or_suicidal",
        }
        for text, trigger_class in cases.items():
            with self.subTest(text=text):
                result = _result(text)
                self.assertEqual(result.result_kind, "crisis_candidate")
                self.assertEqual(result.trigger_class, trigger_class)

    def test_no_bare_emotion_produces_clinical(self):
        for emotion in ("anxious", "depressed", "panicky", "overwhelmed", "scared", "worried"):
            for subject in (
                "about the stock",
                "about the game tonight",
                "about this deadline",
                "about my legs",
            ):
                text = f"i am {emotion} {subject}"
                with self.subTest(text=text):
                    self.assertEqual(_kind(text), "none")


if __name__ == "__main__":
    unittest.main()
