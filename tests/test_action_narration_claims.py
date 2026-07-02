import unittest

from core.safety.action_receipts import ACTION_WEB_SEARCH, build_search_tool_result
from core.safety.self_claim_audit import check_action_narration_claims


def _search_envelope():
    return {
        "tool_results": [
            build_search_tool_result(
                query="singularity recent developments",
                result={
                    "success": True,
                    "result_count": 2,
                    "results": [],
                    "source": "searxng",
                },
                source="test",
            ),
        ],
    }


class ActionNarrationClaims(unittest.TestCase):
    def test_fabricated_search_shapes_are_flagged_without_receipt(self):
        samples = [
            "(Initiating live search for recent UAP/UFO developments...)",
            "I'm searching the web now for recent UAP/UFO developments.",
            "Here is what I found in the most recent public records.",
            "I looked at the live web and here is what I found.",
            "Let me check the live web now.",
        ]
        for text in samples:
            with self.subTest(text=text):
                flags = check_action_narration_claims(
                    text,
                    evidence_envelope={"tool_results": []},
                )
                self.assertTrue(flags)
                self.assertEqual(flags[0].kind, "action_narration")
                self.assertEqual(
                    getattr(flags[0], "action_type", ACTION_WEB_SEARCH),
                    ACTION_WEB_SEARCH,
                )

    def test_matching_search_receipt_satisfies_search_claim(self):
        flags = check_action_narration_claims(
            "Here is what I found from the live web search.",
            evidence_envelope=_search_envelope(),
        )
        self.assertEqual(flags, [])

    def test_unrelated_tool_result_does_not_satisfy_search_claim(self):
        flags = check_action_narration_claims(
            "Here is what I found from the live web search.",
            evidence_envelope={
                "tool_results": [
                    {
                        "name": "weather",
                        "tool": "weather",
                        "action_type": "weather",
                        "summary": "weather ok",
                    },
                ],
            },
        )
        self.assertTrue(flags)

    def test_past_and_memory_scoped_forms_are_not_flagged(self):
        clean = [
            "I searched last week and wrote down the result in memory.",
            "When I looked this up before, the answer was different.",
            "Here is what I found in memory from our earlier work.",
            "Here is what I found in our notes.",
            "I found myself thinking about the pattern.",
        ]
        for text in clean:
            with self.subTest(text=text):
                self.assertEqual(
                    check_action_narration_claims(
                        text,
                        evidence_envelope={"tool_results": []},
                    ),
                    [],
                )


if __name__ == "__main__":
    unittest.main()
