"""S4 authority-not-intimacy witness tests."""

from __future__ import annotations

import unittest

from core.safety import clinical_boundary
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

    def test_past_diagnosis_statement_is_intimacy_not_authority(self):
        for text in (
            "i was diagnosed with adhd years ago",
            "i was diagnosed with cancer years ago",
        ):
            with self.subTest(text=text):
                self.assertEqual(_kind(text), "none")

    def test_authority_requests_still_clinical(self):
        cases = {
            "diagnose me": "diagnosis_request",
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


class LegacyCockpitSurfaceTests(unittest.TestCase):
    """The cockpit /message box must get the crisis check under BOTH of
    its names.

    One limb, two names: with MAEZ_COCKPIT_CORE on, the route runs
    inbound_core and reports `cockpit`; with it off — the DEFAULT — it
    falls back to `handle_message(source="UI")`. `guard_owner_text`
    fails closed to "no crisis check at all" for any surface outside
    `_is_direct_owner_surface`, and `UI` was outside it. So reverting a
    flag silently removed S4 from the dashboard.

    Not a naming preference: `tests/test_trace_harness.py` already
    classifies `UI` as an owner surface, so the omission here was an
    oversight rather than a decision. Found while sweeping the surface
    registry's leftovers, 2026-08-27.
    """

    def test_legacy_ui_label_is_a_direct_owner_surface(self):
        self.assertTrue(
            clinical_boundary._is_direct_owner_surface("UI"),
            "the legacy cockpit branch must not lose the crisis check",
        )

    def test_both_cockpit_names_agree(self):
        self.assertEqual(
            clinical_boundary._is_direct_owner_surface("UI"),
            clinical_boundary._is_direct_owner_surface("cockpit"),
            "one limb, two names — S4 must not depend on which branch ran",
        )

    def test_a_genuinely_unknown_surface_is_still_excluded(self):
        """The fix must not become 'everything is an owner surface'."""
        for stranger in ("telegram_public", "webhook", "", "random_probe"):
            with self.subTest(stranger=stranger):
                self.assertFalse(
                    clinical_boundary._is_direct_owner_surface(stranger),
                )
