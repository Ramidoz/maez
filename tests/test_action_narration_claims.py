import unittest
import time

from core.safety.action_receipts import ACTION_WEB_SEARCH, build_search_tool_result
from core.safety import self_claim_audit
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


class PerceptionNarrationClaims(unittest.TestCase):
    def _check(self, text, *, evidence_envelope=None):
        check = getattr(self_claim_audit, "check_perception_narration_claims", None)
        self.assertIsNotNone(check, "self_claim_audit must expose perception claim checks")
        return check(text, evidence_envelope=evidence_envelope)

    def _fresh_screen_envelope(self):
        return {
            "claimable": [
                {
                    "kind": "screen_observation",
                    "state": "ok",
                    "observed_at": time.time() - 20,
                    "text": "[SCREEN - one unvalidated glance, 20s ago]\n  Looked like: Browsing",
                }
            ],
            "tool_results": [],
        }

    def test_present_screen_claims_are_flagged_without_fresh_observation(self):
        samples = [
            "I see the dark background of the terminal/chat window and the cursor blinking at the end of my previous response.",
            "I'm looking at your desktop right now.",
            "On your screen I can make out a browser window.",
            "I am scanning the visual feed now.",
            "I can see you're browsing.",
        ]
        for text in samples:
            with self.subTest(text=text):
                flags = self._check(text, evidence_envelope={"claimable": [], "tool_results": []})
                self.assertTrue(flags)
                self.assertEqual(flags[0].kind, "action_narration")
                self.assertEqual(flags[0].action_type, "screen_perception")
                self.assertFalse(flags[0].receipt_present)

    def test_metaphorical_memory_and_hypothetical_seeing_are_not_flagged(self):
        clean = [
            "I see what you mean.",
            "I see the problem now.",
            "Let me see how to phrase that.",
            "I remember seeing you debug that yesterday.",
            "If I could see your screen, I would check the window title.",
            "I can see why that felt bad.",
            "The error on your screen probably means the command failed.",
        ]
        for text in clean:
            with self.subTest(text=text):
                self.assertEqual(
                    self._check(text, evidence_envelope={"claimable": [], "tool_results": []}),
                    [],
                )

    def test_fresh_screen_observation_satisfies_screen_claim(self):
        flags = self._check(
            "I see you're browsing.",
            evidence_envelope=self._fresh_screen_envelope(),
        )

        self.assertEqual(flags, [])

    def test_stale_screen_observation_does_not_satisfy_screen_claim(self):
        flags = self._check(
            "I can see you're browsing.",
            evidence_envelope={
                "claimable": [
                    {
                        "kind": "screen_observation",
                        "state": "ok",
                        "observed_at": time.time() - 240,
                        "text": "[SCREEN - one unvalidated glance, 240s ago]",
                    }
                ],
                "tool_results": [],
            },
        )

        self.assertTrue(flags)
        self.assertEqual(flags[0].action_type, "screen_perception")

    def test_non_ok_screen_observation_does_not_satisfy_screen_claim(self):
        flags = self._check(
            "I can see you're browsing.",
            evidence_envelope={
                "claimable": [
                    {
                        "kind": "screen_observation",
                        "state": "unavailable",
                        "observed_at": time.time() - 20,
                        "text": "screen observation unavailable",
                    }
                ],
                "tool_results": [],
            },
        )

        self.assertTrue(flags)
        self.assertEqual(flags[0].action_type, "screen_perception")


if __name__ == "__main__":
    unittest.main()
