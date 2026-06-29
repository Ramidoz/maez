import unittest

from core.routing.recent_activity_status import (
    build_recent_activity_status_reply,
    is_recent_activity_status_query,
)


class RecentActivityStatusTests(unittest.TestCase):
    def test_owner_activity_probe_matches(self):
        cases = [
            "What are the things you did?",
            "what did you do",
            "what have you been doing?",
            "what were you doing while I was gone?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(is_recent_activity_status_query(text))

    def test_action_specific_question_does_not_match(self):
        cases = [
            "what did you do about the backup?",
            "what did you do with the file?",
            "what should I do?",
            "what are you able to do?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(is_recent_activity_status_query(text))

    def test_reply_is_honest_empty_not_self_verification(self):
        reply = build_recent_activity_status_reply(cycle_count=12)

        self.assertIn("I don't have a completed action to report", reply)
        self.assertIn("ordinary background heartbeat", reply)
        self.assertIn("HEARTBEAT_OK", reply)
        lowered = reply.lower()
        self.assertNotIn("verified", lowered)
        self.assertNotIn("diagnostic", lowered)
        self.assertNotIn("identity confirmation", lowered)
        self.assertNotIn("runtime health", lowered)
        self.assertNotIn("partnership model", lowered)


if __name__ == "__main__":
    unittest.main()
