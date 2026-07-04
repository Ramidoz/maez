from __future__ import annotations

import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.interaction_preferences.store import InteractionPreferencesStore


class InteractionPreferenceRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "interaction_preferences.db"
        self.store = InteractionPreferencesStore(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_source_ref_is_content_light_and_surface_sanitized(self):
        from core.interaction_preferences.runtime import owner_turn_source_ref

        ref = owner_turn_source_ref(
            source="telegram:surface",
            text="stop asking me so many questions",
            created_at_ms=1234,
        )

        self.assertRegex(ref, r"^owner_turn:telegram_surface:[0-9a-f]{16}:1234$")
        self.assertNotIn("stop asking", ref)

    def test_shadow_logs_would_capture_but_writes_nothing(self):
        from core.interaction_preferences.runtime import process_owner_turn_preference

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_INTERACTION_PREFERENCES_SHADOW": "1",
                "MAEZ_INTERACTION_PREFERENCES": "0",
            },
            clear=False,
        ), self.assertLogs("maez", level="INFO") as logs:
            result = process_owner_turn_preference(
                text="stop asking me so many questions",
                source="telegram_surface",
                store=self.store,
                created_at_ms=1000,
                created_at="2026-07-03T12:00:00Z",
            )

        self.assertEqual(result.mode, "shadow")
        self.assertEqual(result.action, "would_capture")
        self.assertEqual(self.store.list_all(), [])
        joined = "\n".join(logs.output)
        self.assertIn("interaction_preference_shadow", joined)
        self.assertIn("action=would_capture", joined)
        self.assertIn("owner_turn:telegram_surface", joined)

    def test_shadow_missing_default_db_creates_no_file(self):
        from core.interaction_preferences.runtime import process_owner_turn_preference

        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {
                "MAEZ_DATA": td,
                "MAEZ_INTERACTION_PREFERENCES_SHADOW": "1",
                "MAEZ_INTERACTION_PREFERENCES": "0",
            },
            clear=False,
        ):
            db_path = Path(td) / "memory" / "interaction_preferences.db"
            result = process_owner_turn_preference(
                text="stop asking me so many questions",
                source="telegram_surface",
                created_at_ms=1000,
                created_at="2026-07-03T12:00:00Z",
            )

            self.assertEqual(result.action, "would_capture")
            self.assertFalse(db_path.exists())

    def test_shadow_existing_empty_default_db_is_read_only(self):
        from core.interaction_preferences.runtime import process_owner_turn_preference

        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ,
            {
                "MAEZ_DATA": td,
                "MAEZ_INTERACTION_PREFERENCES_SHADOW": "1",
                "MAEZ_INTERACTION_PREFERENCES": "0",
            },
            clear=False,
        ):
            db_path = Path(td) / "memory" / "interaction_preferences.db"
            db_path.parent.mkdir(parents=True)
            db_path.write_bytes(b"")
            before = db_path.stat().st_size

            result = process_owner_turn_preference(
                text="stop asking me so many questions",
                source="telegram_surface",
                created_at_ms=1000,
                created_at="2026-07-03T12:00:00Z",
            )

            self.assertEqual(result.action, "would_capture")
            self.assertEqual(db_path.stat().st_size, before)

    def test_enabled_capture_writes_one_active_row(self):
        from core.interaction_preferences.runtime import process_owner_turn_preference

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_INTERACTION_PREFERENCES_SHADOW": "0",
                "MAEZ_INTERACTION_PREFERENCES": "1",
            },
            clear=False,
        ):
            result = process_owner_turn_preference(
                text="stop asking me so many questions",
                source="telegram_surface",
                store=self.store,
                created_at_ms=1000,
                created_at="2026-07-03T12:00:00Z",
            )

        self.assertEqual(result.mode, "enabled")
        self.assertEqual(result.action, "capture")
        active = self.store.active_preferences("question_cadence")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].owner_statement, "stop asking me so many questions")

    def test_conversational_retraction_supersedes_without_cli(self):
        from core.interaction_preferences.runtime import process_owner_turn_preference

        with mock.patch.dict(
            os.environ,
            {"MAEZ_INTERACTION_PREFERENCES": "1"},
            clear=False,
        ):
            process_owner_turn_preference(
                text="stop asking me so many questions",
                source="telegram_surface",
                store=self.store,
                created_at_ms=1000,
                created_at="2026-07-03T12:00:00Z",
            )
            result = process_owner_turn_preference(
                text="actually, ask away",
                source="telegram_surface",
                store=self.store,
                created_at_ms=2000,
                created_at="2026-07-03T12:01:00Z",
            )

        self.assertEqual(result.action, "retract")
        self.assertEqual(self.store.active_preferences("question_cadence"), [])
        rows = self.store.list_all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].status, "retracted")
        self.assertEqual(rows[1].owner_statement, "actually, ask away")

    def test_prompt_context_uses_owner_message_context_provenance(self):
        from core.interaction_preferences.runtime import interaction_preferences_prompt_context

        self.store.record_capture(
            preference_id="pref-1",
            preference_class="question_cadence",
            owner_statement="stop asking me so many questions",
            source_ref="owner_turn:telegram:abc123:1000",
            surface="telegram",
            statement_sha256="a" * 64,
            created_at="2026-07-03T12:00:00Z",
        )

        with mock.patch.dict(os.environ, {"MAEZ_INTERACTION_PREFERENCES": "1"}, clear=False):
            context = interaction_preferences_prompt_context(store=self.store)

        self.assertIsNotNone(context)
        assert context is not None
        self.assertIn("OWNER-STATED INTERACTION PREFERENCES", str(context))
        self.assertEqual(context.spans[0].origin_class, "owner_message_context")
        self.assertEqual(context.spans[0].source_ref, "interaction_preferences:active")


class InteractionPreferenceHandleMessageTests(unittest.TestCase):
    def _handle_source(self) -> str:
        source = (Path(__file__).resolve().parents[1] / "daemon" / "maez_daemon.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
                return ast.get_source_segment(source, node) or ""
        raise AssertionError("handle_message not found")

    def test_handle_message_wires_preferences_before_ambient_not_final_context(self):
        source = self._handle_source()

        self.assertIn("process_owner_turn_preference", source)
        self.assertIn("interaction_preferences_prompt_context", source)
        self.assertIn('"interaction_preferences"', source)
        self.assertIn("str(_interaction_preferences_context)", source)
        self.assertLess(
            source.index("interaction_preferences_prompt_context"),
            source.index("_combined_context_block"),
        )
        self.assertLess(
            source.index("interaction_preferences_prompt_context"),
            source.index("_compose_turn_final_system_part"),
        )
        self.assertNotIn(
            "_compose_turn_final_system_part(\n            interaction_preferences",
            source,
        )

    def test_flag_off_handle_message_does_not_call_preference_runtime(self):
        from daemon import maez_daemon
        from tests.test_memory_integrity_invariant import DaemonHandleMessageContract

        helper = DaemonHandleMessageContract(methodName="test_handle_message_source_uses_audited_output")
        daemon = helper._build_daemon_for_handle_message()
        captured: dict[str, list[dict]] = {}

        with helper._handle_message_mock_stack(
            maez_daemon,
            captured,
            reply="grounded reply",
        ), mock.patch.dict(
            os.environ,
            {
                "MAEZ_INTERACTION_PREFERENCES_SHADOW": "0",
                "MAEZ_INTERACTION_PREFERENCES": "0",
            },
            clear=False,
        ), mock.patch(
            "core.interaction_preferences.runtime.process_owner_turn_preference",
            side_effect=AssertionError("detector/store should not run flag-off"),
        ) as process_mock, mock.patch(
            "core.interaction_preferences.runtime.interaction_preferences_prompt_context",
            side_effect=AssertionError("renderer should not run flag-off"),
        ) as render_mock:
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "hello",
                source="telegram_surface",
                chat_history=None,
            )

        self.assertEqual(reply, "grounded reply")
        process_mock.assert_not_called()
        render_mock.assert_not_called()
        self.assertIn("messages", captured)

    def test_enabled_ordinary_turn_logs_interaction_preferences_prompt_shape(self):
        from daemon import maez_daemon
        from tests.test_memory_integrity_invariant import DaemonHandleMessageContract

        helper = DaemonHandleMessageContract(methodName="test_handle_message_source_uses_audited_output")
        daemon = helper._build_daemon_for_handle_message()
        captured: dict[str, list[dict]] = {}
        with tempfile.TemporaryDirectory() as td:
            store = InteractionPreferencesStore(
                Path(td) / "memory" / "interaction_preferences.db"
            )
            store.record_capture(
                preference_id="pref-1",
                preference_class="question_cadence",
                owner_statement="stop asking me so many questions",
                source_ref="owner_turn:telegram:abc123:1000",
                surface="telegram_surface",
                statement_sha256="a" * 64,
                created_at="2026-07-03T12:00:00Z",
            )

            with helper._handle_message_mock_stack(
                maez_daemon,
                captured,
                reply="grounded reply",
            ), mock.patch.dict(
                os.environ,
                {
                    "MAEZ_DATA": td,
                    "MAEZ_INTERACTION_PREFERENCES_SHADOW": "0",
                    "MAEZ_INTERACTION_PREFERENCES": "1",
                },
                clear=False,
            ), self.assertLogs("maez", level="INFO") as logs:
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "hello",
                    source="telegram_surface",
                    chat_history=None,
                )

        self.assertEqual(reply, "grounded reply")
        joined = "\n".join(logs.output)
        self.assertIn("daemon_system_part_shape", joined)
        self.assertIn("interaction_preferences", joined)
        self.assertIn("OWNER-STATED INTERACTION PREFERENCES", joined)


if __name__ == "__main__":
    unittest.main()
