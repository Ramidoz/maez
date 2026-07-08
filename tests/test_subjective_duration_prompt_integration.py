from __future__ import annotations

import ast
import contextlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "daemon" / "maez_daemon.py"
TELEGRAM = ROOT / "skills" / "telegram_voice.py"
WEB = ROOT / "skills" / "web_interface.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_node(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(_source(path), filename=str(path))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if not matches:
        raise AssertionError(f"{name} not found in {path}")
    return matches[0]


def _function_source(path: Path, name: str) -> str:
    node = _function_node(path, name)
    lines = _source(path).splitlines()
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


class _FakeMemory:
    def __init__(self) -> None:
        self.stored: list[str] = []

    def recall_for_telegram(self, text: str) -> dict:
        return {}

    def format_for_prompt(self, recalled: dict, *, max_chars: int) -> str:
        return ""

    def store_telegram(self, text: str, **kwargs) -> str:
        self.stored.append(text)
        return "raw-memory-1"


class _FreshCameraState:
    def with_freshness(self):
        return self


class _Writer:
    def write(self, trace) -> None:
        return None


class SubjectiveDurationPromptBehaviorTests(unittest.TestCase):
    def test_handle_message_without_owner_auth_does_not_insert_line_or_record_owner_contact(self):
        import daemon.maez_daemon as maez_daemon

        line_calls: list[tuple] = []
        owner_contact_events: list[dict] = []

        def fake_prompt_line(*args, **kwargs):
            line_calls.append((args, kwargs))
            return "SUBJECTIVE_DURATION_OWNER_ONLY_LINE"

        class FakeSubjectiveDuration:
            def record_salience_event(self, **kwargs):
                owner_contact_events.append(kwargs)
                return 1

        fake_subjective_duration_module = types.SimpleNamespace(
            SubjectiveDuration=mock.Mock(return_value=FakeSubjectiveDuration()),
            subjective_duration_prompt_line=mock.Mock(side_effect=fake_prompt_line),
        )

        daemon = types.SimpleNamespace(
            private_thoughts=None,
            _camera_presence_state=_FreshCameraState(),
            _last_screen_obs=None,
            _last_calendar_snap=None,
            memory=_FakeMemory(),
            system_prompt="SOUL",
            lived_episodes=object(),
            lived_graph=object(),
            _m1_lock=types.SimpleNamespace(
                __enter__=lambda self: None,
                __exit__=lambda self, exc_type, exc, tb: None,
            ),
            m1_promoter=None,
            _get_public_context=lambda: "",
            _trf_apply_fragment_guard=lambda **kwargs: kwargs["reply"],
            _ws_broadcast=lambda payload: None,
            _record_fabrication_scars_from_audit_result=lambda *args, **kwargs: None,
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(
                    os.environ,
                    {
                        "MAEZ_LIVED_RECALL": "0",
                        "MAEZ_AMBIENT_BRIEF": "0",
                        "MAEZ_WORKING_SELF": "0",
                        "MAEZ_WONDERING_PURSUIT": "0",
                    },
                    clear=False,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "guard_owner_text",
                    return_value=types.SimpleNamespace(matched=False, answer_text=None),
                )
            )
            stack.enter_context(
                mock.patch.object(maez_daemon, "answer_camera_presence_question", return_value=None)
            )
            stack.enter_context(mock.patch.object(maez_daemon, "perception_snapshot", return_value=object()))
            stack.enter_context(mock.patch.object(maez_daemon, "format_snapshot", return_value="SYSTEM_STATE"))
            stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "Trace",
                    types.SimpleNamespace(
                        start=lambda **kwargs: types.SimpleNamespace(audit=types.SimpleNamespace())
                    ),
                )
            )
            stack.enter_context(mock.patch.object(maez_daemon, "default_writer", return_value=_Writer()))
            stack.enter_context(
                mock.patch.object(maez_daemon, "_authoritative_tool_reply", return_value="patched reply")
            )
            stack.enter_context(mock.patch.object(maez_daemon, "_trace_hash_text", return_value="hash"))
            stack.enter_context(mock.patch.object(maez_daemon, "_trace_extract_evidence_ids", return_value=[]))
            stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "build_temporal_anchor_recall_brief",
                    return_value=types.SimpleNamespace(
                        anchor_detected=False,
                        brief_text="",
                        evidence_ids=[],
                    ),
                )
            )
            stack.enter_context(
                mock.patch.dict(
                    sys.modules,
                    {"core.evolution.subjective_duration": fake_subjective_duration_module},
                    clear=False,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "subjective_duration_prompt_line",
                    side_effect=fake_prompt_line,
                    create=True,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "SubjectiveDuration",
                    return_value=FakeSubjectiveDuration(),
                    create=True,
                )
            )
            stack.enter_context(mock.patch("core.cognition.envelope_builder.build_envelope", return_value=None))
            stack.enter_context(
                mock.patch("core.cognition.envelope_builder.render_envelope_for_prompt", return_value="")
            )
            stack.enter_context(
                mock.patch("core.cognition.envelope_builder.resolve_recall_cap_chars", return_value=1000)
            )
            stack.enter_context(mock.patch("skills.web_search.needs_web_search", return_value=False))
            stack.enter_context(
                mock.patch(
                    "core.safety.audited_output.audit_assistant_text",
                    side_effect=lambda text, **kwargs: text,
                )
            )
            stack.enter_context(mock.patch("core.ledger.writer.try_write_turn", return_value="turn-1"))
            stack.enter_context(
                mock.patch("core.ledger.model_reply_persistence.persist_model_reply", return_value=None)
            )
            try:
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "hey",
                    source="manual_test",
                    subjective_duration_owner_auth=None,
                )
            except TypeError as exc:
                self.fail(
                    "handle_message must accept subjective_duration_owner_auth=None "
                    f"without treating the raw turn as owner-contact: {exc}"
                )

        self.assertEqual(reply, "patched reply")
        self.assertEqual([], line_calls)
        self.assertEqual([], owner_contact_events)


class SubjectiveDurationPromptSourceTests(unittest.TestCase):
    def test_handle_message_contract_has_default_denied_typed_owner_auth(self):
        handle = _function_node(DAEMON, "handle_message")
        kw_defaults = {
            arg.arg: default
            for arg, default in zip(handle.args.kwonlyargs, handle.args.kw_defaults)
        }

        if "subjective_duration_owner_auth" not in kw_defaults:
            self.fail("handle_message must expose keyword-only subjective_duration_owner_auth")
        self.assertIsInstance(kw_defaults["subjective_duration_owner_auth"], ast.Constant)
        self.assertIsNone(kw_defaults["subjective_duration_owner_auth"].value)
        if "SubjectiveDurationOwnerAuth" not in _source(DAEMON):
            self.fail("daemon must define or import SubjectiveDurationOwnerAuth")

    def test_handle_message_with_typed_auth_can_insert_prompt_line_near_system_state(self):
        handle_node = _function_node(DAEMON, "handle_message")
        handle = _function_source(DAEMON, "handle_message")

        prompt_calls = [
            node
            for node in ast.walk(handle_node)
            if isinstance(node, ast.Attribute)
            and node.attr == "subjective_duration_prompt_line"
        ]
        if not prompt_calls:
            self.fail("handle_message must call subjective_duration_prompt_line")
        if "owner_contact" not in handle:
            self.fail("handle_message must dispatch owner_contact only with typed owner auth")
        system_state_idx = handle.index("system_state = format_snapshot")
        line_idx = handle.index("subjective_duration_prompt_line")
        public_context_idx = handle.index("public_ctx = self._get_public_context")
        auth_idx = handle.index("subjective_duration_owner_auth")

        self.assertLess(system_state_idx, line_idx)
        self.assertLess(line_idx, public_context_idx)
        self.assertLess(auth_idx, line_idx)
        self.assertIn("owner_contact", handle)

    def test_raw_daemon_message_route_does_not_pass_owner_auth(self):
        route = _function_source(DAEMON, "message")

        if "self.handle_message(" not in route:
            self.fail("daemon /message route must call handle_message")
        self.assertNotIn("subjective_duration_owner_auth", route)
        self.assertNotIn("SubjectiveDurationOwnerAuth", route)
        self.assertNotIn("owner_contact", route)

    def test_telegram_unauthorized_exits_before_owner_auth_prompt_construction(self):
        handler = _function_source(TELEGRAM, "_handle_message")

        if "SubjectiveDurationOwnerAuth" not in handler:
            self.fail("Telegram _handle_message must construct typed owner auth after authorization")
        if "subjective_duration_prompt_line" not in handler:
            self.fail("Telegram _handle_message must add subjective-duration prompt line after authorization")
        unauthorized_idx = handler.index("if not self._is_authorized(user_id):")
        return_idx = handler.index("return", unauthorized_idx)
        auth_idx = handler.index("SubjectiveDurationOwnerAuth")
        prompt_idx = handler.index("subjective_duration_prompt_line")

        self.assertLess(unauthorized_idx, auth_idx)
        self.assertLess(return_idx, auth_idx)
        self.assertLess(unauthorized_idx, prompt_idx)
        self.assertLess(return_idx, prompt_idx)

    def test_telegram_authorized_path_has_local_auth_checkpoint_before_typed_auth(self):
        handler = _function_source(TELEGRAM, "_handle_message")

        if "SubjectiveDurationOwnerAuth" not in handler:
            self.fail("Telegram _handle_message must construct SubjectiveDurationOwnerAuth")
        if "subjective_duration_prompt_line" not in handler:
            self.fail("Telegram _handle_message must add subjective_duration_prompt_line")
        if "telegram_authorized_user" not in handler:
            self.fail("Telegram auth proof must be telegram_authorized_user")
        auth_check_idx = handler.index("if not self._is_authorized(user_id):")
        typed_auth_idx = handler.index("SubjectiveDurationOwnerAuth")
        prompt_idx = handler.index("subjective_duration_prompt_line")

        self.assertLess(auth_check_idx, typed_auth_idx)
        self.assertLess(typed_auth_idx, prompt_idx)
        self.assertIn("telegram_authorized_user", handler[typed_auth_idx:prompt_idx])

    def test_web_owner_bridge_constructs_typed_auth_only_after_private_owner_bridge(self):
        chat = _function_source(WEB, "chat")

        if "SubjectiveDurationOwnerAuth" not in chat:
            self.fail("web /chat owner bridge must construct SubjectiveDurationOwnerAuth")
        if "subjective_duration_prompt_line" not in chat:
            self.fail("web /chat owner bridge must add subjective_duration_prompt_line")
        if "web_private_owner_bridge" not in chat:
            self.fail("web owner auth proof must be web_private_owner_bridge")
        owner_bridge_assignment_text = (
            "owner_bridge = _is_private_owner_bridge(user_full)"
            if "owner_bridge = _is_private_owner_bridge(user_full)" in chat
            else "owner_bridge = _is_owner(user_full)"
        )
        owner_bridge_assignment = chat.index(owner_bridge_assignment_text)
        first_owner_branch = chat.index("if owner_bridge:", owner_bridge_assignment)
        public_branch = chat.index("else:", first_owner_branch)
        typed_auth_idx = chat.index("SubjectiveDurationOwnerAuth")
        prompt_idx = chat.index("subjective_duration_prompt_line")

        self.assertLess(owner_bridge_assignment, typed_auth_idx)
        self.assertLess(first_owner_branch, typed_auth_idx)
        self.assertLess(typed_auth_idx, public_branch)
        self.assertLess(typed_auth_idx, prompt_idx)
        self.assertIn("web_private_owner_bridge", chat[typed_auth_idx:prompt_idx])
        self.assertNotIn("SubjectiveDurationOwnerAuth", chat[public_branch:])
        self.assertNotIn("subjective_duration_prompt_line", chat[public_branch:])

    def test_owner_auth_construction_is_not_hidden_in_route_call_keywords(self):
        for path, function_name in ((DAEMON, "message"), (WEB, "chat"), (TELEGRAM, "_handle_message")):
            function = _function_node(path, function_name)
            for call in ast.walk(function):
                if not isinstance(call, ast.Call):
                    continue
                if _call_name(call.func) != "handle_message":
                    continue
                for keyword in call.keywords:
                    self.assertNotEqual(
                        "subjective_duration_owner_auth",
                        keyword.arg,
                        f"{path}:{function_name} launders owner auth through a raw handle_message call",
                    )


if __name__ == "__main__":
    unittest.main()
