from __future__ import annotations

import unittest

from core.cognition.lean_idle_heartbeat import (
    HEARTBEAT_VERSION,
    LeanIdleFacts,
    build_lean_idle_prompt,
    sanitize_private_note,
)


class LeanIdleHeartbeatTest(unittest.TestCase):
    def test_prompt_is_lean_and_excludes_flood_sources(self) -> None:
        prompt = build_lean_idle_prompt(
            LeanIdleFacts(
                cycle=44,
                doorman_reason="wake_min_floor",
                self_card_text="SELF CARD\n- Bond: partnership",
                private_signal_summary={"self_observation": 2},
            )
        )

        self.assertIn("LEAN IDLE HEARTBEAT", prompt.text)
        self.assertIn("SELF CARD", prompt.text)
        self.assertIn("wake_min_floor", prompt.text)
        self.assertLess(len(prompt.text), 4000)
        for forbidden in (
            "git status",
            "reddit",
            "proactive search",
            "=== EVIDENCE",
            "Memory stats:",
            "owner replied",
            "owner seemed pleased",
        ):
            self.assertNotIn(forbidden, prompt.text)
        self.assertEqual(prompt.version, HEARTBEAT_VERSION)
        self.assertIn("self_card", prompt.fact_keys)

    def test_sanitizer_accepts_private_note_and_caps_length(self) -> None:
        raw = (
            "<final>"
            + ("I notice the quiet floor wake and can carry this as a private note. " * 20)
            + "</final>"
        )

        note = sanitize_private_note(raw)

        self.assertIsNotNone(note)
        assert note is not None
        self.assertLessEqual(len(note.text), 600)
        self.assertNotIn("<final>", note.text)

    def test_sanitizer_treats_heartbeat_ok_as_no_write(self) -> None:
        note = sanitize_private_note("<final>HEARTBEAT_OK</final>")

        self.assertIsNone(note)

    def test_sanitizer_rejects_owner_addressed_or_action_output(self) -> None:
        for raw in (
            "Rohit, I should tell you this.",
            "I should search the web for this.",
            "Run a command to check the machine.",
            "Send Rohit a message later.",
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(sanitize_private_note(raw))


if __name__ == "__main__":
    unittest.main()
