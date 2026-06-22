from __future__ import annotations

import unittest


class SelfCapabilityQuestionTests(unittest.TestCase):
    def test_question_shape_and_capability_terms_match_today(self):
        from core.routing.self_capability_question import (
            bodyish_self_capability_candidate,
            is_self_capability_question,
        )

        text = "What's the state of your web search tools?"

        self.assertTrue(is_self_capability_question(text))
        self.assertTrue(bodyish_self_capability_candidate(text))

    def test_bodyish_without_question_shape_is_leak_candidate_not_carveout(self):
        from core.routing.self_capability_question import (
            bodyish_self_capability_candidate,
            is_self_capability_question,
        )

        text = "your web search tools are acting strange"

        self.assertFalse(is_self_capability_question(text))
        self.assertTrue(bodyish_self_capability_candidate(text))

    def test_non_body_conversation_is_not_bodyish(self):
        from core.routing.self_capability_question import (
            bodyish_self_capability_candidate,
            is_self_capability_question,
        )

        text = "how are you?"

        self.assertFalse(is_self_capability_question(text))
        self.assertFalse(bodyish_self_capability_candidate(text))

    def test_layer0_private_wrapper_delegates_to_shared_predicate(self):
        from core.dispatcher import layer0
        from core.routing.self_capability_question import is_self_capability_question

        samples = [
            "What's the state of your web search tools?",
            "what can you do?",
            "how are you?",
            "latest Anthropic news",
        ]

        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(
                    layer0._is_self_capability_question(sample),
                    is_self_capability_question(sample),
                )

    def test_golden_sample_set_pins_no_widening(self):
        from core.routing.self_capability_question import is_self_capability_question

        expected = {
            "What's the state of your web search tools?": True,
            "can you use your page read tools?": True,
            "can your search tools read this page?": True,
            "what capabilities do you have?": True,
            # The current predicate does not treat broad ability questions as
            # self-capability. Arc A reuses the existing organ; it does not
            # widen it under the cover of extraction.
            "can you read pages right now?": False,
            "what can you do?": False,
            "your web search tools are acting strange": False,
            "how are you?": False,
            "latest Anthropic news": False,
            "search the web for Anthropic": False,
        }

        for text, value in expected.items():
            with self.subTest(text=text):
                self.assertEqual(is_self_capability_question(text), value)


class ExplicitMemoryQuestionTests(unittest.TestCase):
    def test_layer0_explicit_memory_regex_is_shared(self):
        from core.dispatcher import layer0
        from core.routing.explicit_memory_question import EXPLICIT_MEMORY_RE

        self.assertIs(layer0._EXPLICIT_MEMORY_RE, EXPLICIT_MEMORY_RE)

    def test_golden_sample_set_pins_current_memory_request_shape(self):
        from core.routing.explicit_memory_question import is_explicit_memory_question

        expected = {
            "what do you remember about qwen?": True,
            "answer from memory": True,
            "what's in your notebook about yesterday?": True,
            "look in your notebook": True,
            "do you remember yesterday?": False,
            "how are you?": False,
        }

        for text, value in expected.items():
            with self.subTest(text=text):
                self.assertEqual(is_explicit_memory_question(text), value)


if __name__ == "__main__":
    unittest.main()
