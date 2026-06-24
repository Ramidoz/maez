from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.cognition.lean_idle_heartbeat import (
    HEARTBEAT_OK,
    HEARTBEAT_VERSION,
    LeanIdleFacts,
    build_lean_idle_prompt,
    run_lean_idle_heartbeat,
    sanitize_private_note,
)
from core.infra.private_thoughts import PrivateThoughts


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeResponse:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


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

    def test_prompt_does_not_assign_feelings(self) -> None:
        prompt = build_lean_idle_prompt(
            LeanIdleFacts(
                cycle=45,
                doorman_reason="wake_min_floor",
                self_card_text="SELF CARD\n- Body state: runtime body overall: ok",
            )
        )
        lowered = prompt.text.lower()

        for forbidden in (
            "lonely",
            "missed",
            "worried",
            "longing",
            "sad",
            "happy",
            "comforted",
            "feel about",
        ):
            self.assertNotIn(forbidden, lowered)

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

    def test_enabled_records_private_self_wondering_with_content_light_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=7,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse(
                    "<final>A quiet private note for continuity.</final>"
                ),
                model="test-model",
                private_thoughts=store,
                enabled=True,
                shadow=False,
            )

            self.assertTrue(result.intercepted)
            self.assertEqual(result.return_text, HEARTBEAT_OK)
            self.assertTrue(result.stored)
            row = store.get_thought(result.thought_id)
            assert row is not None
            self.assertEqual(row["provenance"], "self_wondering")
            self.assertEqual(row["producer_id"], "self_wondering")
            self.assertEqual(row["signal_kind"], "self_wondering")
            self.assertEqual(row["signal_class"], "self_observation")
            self.assertEqual(row["context"]["source"], HEARTBEAT_VERSION)
            self.assertEqual(row["context"]["subject"], "maez_internal_state")
            self.assertEqual(
                row["context"]["allowed_flows"],
                ["private_reader", "audit_trace"],
            )
            extra = row["context"]["extra"]
            self.assertEqual(extra["cycle"], 7)
            self.assertEqual(extra["doorman_reason"], "wake_min_floor")
            self.assertNotIn("A quiet private note", json.dumps(extra))
            self.assertNotIn("SELF CARD", json.dumps(extra))

    def test_shadow_runs_but_does_not_store_or_intercept(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=8,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse("<final>A private note.</final>"),
                model="test-model",
                private_thoughts=store,
                enabled=False,
                shadow=True,
            )

            self.assertFalse(result.intercepted)
            self.assertFalse(result.stored)
            self.assertIsNone(result.return_text)
            self.assertEqual(store.count(), 0)
            self.assertTrue(result.receipt["would_store"])
            self.assertFalse(result.receipt["stored"])

    def test_enabled_heartbeat_ok_stores_nothing_and_intercepts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")

            result = run_lean_idle_heartbeat(
                facts=LeanIdleFacts(
                    cycle=18,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse("<final>HEARTBEAT_OK</final>"),
                model="test-model",
                private_thoughts=store,
                enabled=True,
                shadow=False,
            )

            self.assertTrue(result.intercepted)
            self.assertEqual(result.return_text, HEARTBEAT_OK)
            self.assertFalse(result.stored)
            self.assertEqual(result.skip_reason, "heartbeat_ok_or_rejected")
            self.assertEqual(store.count(), 0)

    def test_duplicate_recent_output_skips_second_private_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = PrivateThoughts(db_path=Path(td) / "private_thoughts.db")
            kwargs = dict(
                facts=LeanIdleFacts(
                    cycle=9,
                    doorman_reason="wake_min_floor",
                    self_card_text="SELF CARD\n- Bond: partnership",
                ),
                chat_fn=lambda **_kwargs: _FakeResponse("<final>Same private note.</final>"),
                model="test-model",
                private_thoughts=store,
                enabled=True,
                shadow=False,
            )

            first = run_lean_idle_heartbeat(**kwargs)
            second = run_lean_idle_heartbeat(**kwargs)

            self.assertTrue(first.stored)
            self.assertFalse(second.stored)
            self.assertEqual(second.skip_reason, "duplicate_recent_output")
            self.assertEqual(store.count(), 1)

    def test_module_does_not_import_forbidden_organs(self) -> None:
        src = Path("core/cognition/lean_idle_heartbeat.py").read_text()
        for forbidden in (
            "developmental_heartbeat",
            "dream_state",
            "store_core",
            "apply_dream",
            "memory.store",
            "_ws_broadcast",
            "web_search",
            "owner replied",
            "owner seemed pleased",
        ):
            self.assertNotIn(forbidden, src)

    def test_receipt_contains_no_raw_prompt_or_output(self) -> None:
        prompt_secret = "SELF CARD SECRET RAW PROMPT"
        output_secret = "private hidden thought output"
        result = run_lean_idle_heartbeat(
            facts=LeanIdleFacts(
                cycle=17,
                doorman_reason="wake_min_floor",
                self_card_text=prompt_secret,
            ),
            chat_fn=lambda **_kwargs: _FakeResponse(f"<final>{output_secret}</final>"),
            model="test-model",
            private_thoughts=None,
            enabled=True,
            shadow=False,
        )

        rendered = json.dumps(result.receipt)
        self.assertNotIn(prompt_secret, rendered)
        self.assertNotIn(output_secret, rendered)
        self.assertIn("prompt_sha256", result.receipt)
        self.assertIn("output_sha256", result.receipt)


if __name__ == "__main__":
    unittest.main()
