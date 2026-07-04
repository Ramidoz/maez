from __future__ import annotations

import unittest

from core.interaction_preferences.detector import detect_interaction_preference


class InteractionPreferenceDetectorTests(unittest.TestCase):
    def test_capture_matches_direct_question_cadence_preferences(self):
        for text in (
            "stop asking me so many questions",
            "please stop asking so many questions",
            "ask fewer questions",
            "don't ask so many follow-up questions",
            "don’t ask so many follow-up questions",
        ):
            with self.subTest(text=text):
                detection = detect_interaction_preference(
                    text,
                    active_question_cadence=False,
                    surface="telegram",
                )
                self.assertIsNotNone(detection)
                assert detection is not None
                self.assertEqual(detection.action, "capture")
                self.assertEqual(detection.preference_class, "question_cadence")
                self.assertEqual(detection.owner_statement, text)

    def test_capture_rejects_ambiguous_or_third_party_mentions(self):
        for text in (
            "you ask good questions",
            "why are there so many questions in this spec?",
            "can you ask me three questions?",
            "I wonder why people ask so many questions",
            "don't stop asking questions if you need to understand",
            "ask fewer questions in the test fixture",
            "the transcript says stop asking me so many questions",
        ):
            with self.subTest(text=text):
                self.assertIsNone(
                    detect_interaction_preference(
                        text,
                        active_question_cadence=False,
                        surface="telegram",
                    )
                )

    def test_quote_and_attribution_shield_rejects_reported_phrases(self):
        for text in (
            'the transcript says "stop asking me so many questions"',
            'in the log: "please stop asking so many questions"',
            'someone said "ask fewer questions"',
            "they told me 'ask fewer questions'",
            "'ask fewer questions'",
            "the quote was 'ask fewer questions'",
            "the fixture says `don't ask so many follow-up questions`",
            "the transcript says “stop asking me so many questions”",
        ):
            with self.subTest(text=text):
                self.assertIsNone(
                    detect_interaction_preference(
                        text,
                        active_question_cadence=False,
                        surface="telegram",
                    )
                )

    def test_apostrophe_in_dont_is_not_treated_as_quote_span(self):
        detection = detect_interaction_preference(
            "don't ask so many follow-up questions",
            active_question_cadence=False,
            surface="telegram",
        )

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.owner_statement, "don't ask so many follow-up questions")

    def test_unquoted_direct_statement_after_quote_can_capture(self):
        detection = detect_interaction_preference(
            'The transcript said "stop asking me so many questions", '
            "and I mean it: stop asking me so many questions",
            active_question_cadence=False,
            surface="telegram",
        )

        self.assertIsNotNone(detection)
        assert detection is not None
        self.assertEqual(detection.action, "capture")
        self.assertEqual(detection.owner_statement, "stop asking me so many questions")

    def test_retraction_requires_active_question_cadence_preference(self):
        for text in (
            "actually, ask away",
            "it's okay to ask questions again",
            "you can ask questions again",
            "ask away",
        ):
            with self.subTest(text=text):
                self.assertIsNone(
                    detect_interaction_preference(
                        text,
                        active_question_cadence=False,
                        surface="telegram",
                    )
                )

    def test_retraction_matches_when_active_preference_exists(self):
        for text in (
            "actually, ask away",
            "it's okay to ask questions again",
            "you can ask questions again",
            "ask away",
        ):
            with self.subTest(text=text):
                detection = detect_interaction_preference(
                    text,
                    active_question_cadence=True,
                    surface="telegram",
                )
                self.assertIsNotNone(detection)
                assert detection is not None
                self.assertEqual(detection.action, "retract")
                self.assertEqual(detection.preference_class, "question_cadence")
                self.assertEqual(detection.owner_statement, text)


if __name__ == "__main__":
    unittest.main()
