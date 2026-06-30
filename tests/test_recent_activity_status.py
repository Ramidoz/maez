import unittest

from core.routing.recent_activity_status import (
    build_casual_presence_status_reply,
    build_recent_activity_status_reply,
    is_casual_presence_status_query,
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


class CasualPresenceStatusTests(unittest.TestCase):
    def test_direct_state_questions_match(self):
        cases = [
            "How are you?",
            "how are you",
            "how's it going with you?",
            "how are things with you?",
            "what are you up to?",
            "what's going on with you?",
            "you okay?",
            "you ok?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(is_casual_presence_status_query(text))

    def test_near_miss_prefixes_do_not_match(self):
        cases = [
            "how are you different from ChatGPT?",
            "how are you going to fix the backup?",
            "how are you able to do that?",
            "how are you planning to handle the GPU?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(is_casual_presence_status_query(text))

    def test_owner_musings_and_world_questions_do_not_match(self):
        cases = [
            "I'm bored with gadgets",
            "it's scorching hot",
            "what's going on in Reddit?",
            "what's going on with the GPU?",
            "what should I do?",
            "what are you able to do?",
            "what's up?",
            "what's going on?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(is_casual_presence_status_query(text))

    def test_state_reply_is_distinct_from_activity_reply(self):
        state_reply = build_casual_presence_status_reply(cycle_count=12)
        activity_reply = build_recent_activity_status_reply(cycle_count=12)

        self.assertNotEqual(state_reply, activity_reply)
        self.assertNotIn("completed action", state_reply.lower())
        self.assertIn("ordinary background heartbeat", state_reply)
        self.assertIn("12", state_reply)

    def test_state_reply_does_not_manufacture_feeling_or_dashboard(self):
        reply = build_casual_presence_status_reply(cycle_count=12)
        lowered = reply.lower()

        forbidden = [
            "i'm good",
            "i'm great",
            "i'm happy",
            "i'm excited",
            "i'm lonely",
            "i'm bored",
            "i'm feeling sharp",
            "ready to help",
            "runtime health",
            "diagnostic",
            "identity confirmation",
            "partnership model",
            "maintenance checklist",
            "verification ritual",
            "trust covenant",
            "what's on your mind",
            "how about you",
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

        self.assertFalse(reply.rstrip().endswith("?"))


if __name__ == "__main__":
    unittest.main()
