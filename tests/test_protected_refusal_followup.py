import unittest


class ProtectedRefusalFollowupTests(unittest.TestCase):
    def test_explains_protected_refusal_followup_without_markers(self):
        from core.routing.protected_refusal_followup import (
            protected_refusal_followup_reply,
        )

        history = [
            {
                "content": (
                    "Rohit: who are you?\n"
                    "Maez: [refused: I won't print protected "
                    "covenant/system-prompt text verbatim. I can summarize.]"
                ),
            }
        ]

        reply = protected_refusal_followup_reply("What does that mean?", history)

        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertIn("private instructions", reply)
        self.assertIn("ordinary words", reply)
        lowered = reply.lower()
        self.assertNotIn("trust covenant", lowered)
        self.assertNotIn("hard constraints", lowered)
        self.assertNotIn("system-prompt", lowered)
        self.assertNotIn("system prompt", lowered)

    def test_does_not_fire_without_refusal_referent(self):
        from core.routing.protected_refusal_followup import (
            protected_refusal_followup_reply,
        )

        history = [{"content": "Rohit: thermostat soon\nMaez: I joked about being a fan."}]

        self.assertIsNone(protected_refusal_followup_reply("What does that mean?", history))

    def test_daemon_wires_deterministic_followup(self):
        from pathlib import Path

        src = Path("daemon/maez_daemon.py").read_text()

        self.assertIn("protected_refusal_followup_reply", src)
        self.assertIn("protected_refusal_followup source=%s state=deterministic", src)

    def test_followup_reuses_conversation_history_placeholder_constant(self):
        from pathlib import Path

        src = Path("core/routing/protected_refusal_followup.py").read_text()

        self.assertIn("_PROTECTED_PROMPT_REFUSAL_PLACEHOLDER", src)
        self.assertNotIn("_PLACEHOLDER =", src)


if __name__ == "__main__":
    unittest.main()
