import unittest


class BackstageLabelStripTest(unittest.TestCase):
    def test_strip_only_capability_state_preserves_citations_and_user_brackets(self):
        from core.safety.audited_output import _strip_backstage_labels

        text = "[CAPABILITY_STATE] Use [E1], keep [maybe later], keep [E10]."

        stripped = _strip_backstage_labels(text)

        self.assertNotIn("[CAPABILITY_STATE]", stripped)
        self.assertIn("[E1]", stripped)
        self.assertIn("[E10]", stripped)
        self.assertIn("[maybe later]", stripped)

    def test_strip_bare_capability_state_token(self):
        from core.safety.audited_output import _strip_backstage_labels

        stripped = _strip_backstage_labels("CAPABILITY_STATE says web sense is on.")

        self.assertEqual(stripped, "says web sense is on.")

    def test_strip_does_not_leave_space_before_punctuation(self):
        from core.safety.audited_output import _strip_backstage_labels

        stripped = _strip_backstage_labels("This is what I am building next [CAPABILITY_STATE].")

        self.assertEqual(stripped, "This is what I am building next.")

    def test_audit_early_skip_path_strips_backstage_label(self):
        from core.safety.audited_output import audit_assistant_text

        out = audit_assistant_text(
            "[CAPABILITY_STATE] Claim [E1].",
            surface="test",
            semantic_self_claim_skip_reason="fixture",
        )

        self.assertEqual(out, "Claim [E1].")


class CapabilityCardPromptTest(unittest.TestCase):
    def test_voice_boundary_instruction_forbids_echoing_capability_state_label(self):
        from core.cognition.capability_card import _VOICE_BOUNDARY_INSTRUCTION

        self.assertIn("Do not write CAPABILITY_STATE", _VOICE_BOUNDARY_INSTRUCTION)
        self.assertIn("[CAPABILITY_STATE]", _VOICE_BOUNDARY_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
