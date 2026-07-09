from __future__ import annotations

import contextlib
import os
import sys
import time
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock


EXPECTED_FLAG_OFF_USER_PROMPT = (
    "SYSTEM_STATE\n\n"
    "Felt time: compact present-tense time.\n\n"
    "the owner sent via telegram_surface:\n"
    "\"hey\"\n\n"
    "Respond directly and concisely.\n\n"
    "Remember: NEVER suggest touching ollama, its models, or any "
    "process that powers your reasoning."
)


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


class _FakeScreenObservation:
    state = "ok"
    success = True
    validation = "unvalidated_single_frame"

    def __init__(self, *, age_s: int, activity: str = "Browsing") -> None:
        self.activity = activity
        self.application = "Firefox"
        self.detail = "Local docs"
        self.focus_level = "browsing"
        self.timestamp = time.time() - age_s

    def format_for_context(self) -> str:
        age_seconds = int(time.time() - self.timestamp)
        return (
            f"[SCREEN - one unvalidated glance, {age_seconds}s ago]\n"
            f"  Looked like: {self.activity}\n"
            "  Application: Firefox\n"
            "  Detail: Local docs\n"
            "  Focus: browsing\n"
            "  (single frame, not cross-checked against running processes "
            "or window state - treat as a first impression, not fact)"
        )


class _Writer:
    def write(self, trace) -> None:
        return None


class _FakeSubjectiveDuration:
    db_path = Path("/tmp/maez-test-subjective-duration.db")

    def record_salience_event(self, **kwargs):
        return 1

    def current(self, **kwargs):
        return types.SimpleNamespace(surface_phrase="compact present-tense time")


class InnerContinuityPromptIntegrationTests(unittest.TestCase):
    def _daemon(self, *, screen_obs=None):
        daemon = types.SimpleNamespace(
            _camera_presence_state=_FreshCameraState(),
            _last_screen_obs=screen_obs,
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
        setattr(daemon, "private" + "_" + "thoughts", None)
        return daemon

    def _run_handle_message(
        self,
        *,
        env: dict[str, str],
        screen_obs=None,
        owner_auth: bool = True,
    ):
        import daemon.maez_daemon as maez_daemon
        import core.evolution as evolution_pkg
        from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth

        captured: dict[str, object] = {}

        def _chat(**kwargs):
            captured["messages"] = kwargs["messages"]
            return types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy reply")
            )

        fake_subjective_duration_module = types.SimpleNamespace(
            SubjectiveDuration=mock.Mock(return_value=_FakeSubjectiveDuration()),
            subjective_duration_prompt_line=mock.Mock(
                return_value="Felt time: compact present-tense time."
            ),
        )

        def _build_envelope(**kwargs):
            captured["build_envelope_kwargs"] = kwargs
            return None

        clean_env = {
            "MAEZ_LIVED_RECALL": "0",
            "MAEZ_AMBIENT_BRIEF": "0",
            "MAEZ_WORKING_SELF": "0",
            "MAEZ_WONDERING_PURSUIT": "0",
            "MAEZ_EVIDENCE_PRECEDENCE_ENABLED": "0",
            "MAEZ_ROUTING_PRIORS_ENABLED": "0",
            "MAEZ_ROUTING_PRIORS_SHADOW": "0",
            "MAEZ_SCREEN_PERCEPTION": "0",
        }
        clean_env.update(env)
        auth = (
            SubjectiveDurationOwnerAuth(
                surface="telegram_owner",
                proof="telegram_authorized_user",
            )
            if owner_auth
            else None
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, clean_env, clear=False))
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
            stack.enter_context(mock.patch.object(maez_daemon, "_authoritative_tool_reply", return_value=""))
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
                    evolution_pkg,
                    "subjective_duration",
                    fake_subjective_duration_module,
                    create=True,
                )
            )
            stack.enter_context(mock.patch("core.cognition.envelope_builder.build_envelope", side_effect=_build_envelope))
            stack.enter_context(
                mock.patch("core.cognition.envelope_builder.render_envelope_for_prompt", return_value="")
            )
            stack.enter_context(
                mock.patch("core.cognition.envelope_builder.resolve_recall_cap_chars", return_value=1000)
            )
            stack.enter_context(mock.patch("skills.web_search.needs_web_search", return_value=False))
            stack.enter_context(mock.patch("core.llm_client.chat", side_effect=_chat))
            stack.enter_context(
                mock.patch("core.routing.brain_gateway.with_purpose", return_value=contextlib.nullcontext())
            )
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
            reply = maez_daemon.MaezDaemon.handle_message(
                self._daemon(screen_obs=screen_obs),
                "hey",
                source="telegram_surface",
                subjective_duration_owner_auth=auth,
            )

        self.assertEqual("legacy reply", reply)
        return captured

    def test_flag_off_keeps_legacy_user_prompt_byte_identical(self):
        captured = self._run_handle_message(env={"MAEZ_INNER_CONTINUITY_FACTS": "0"})

        messages = captured["messages"]
        self.assertEqual(EXPECTED_FLAG_OFF_USER_PROMPT, messages[-1]["content"])
        self.assertNotIn("INNER CONTINUITY FACTS", messages[-1]["content"])

    def test_flag_on_inserts_inner_continuity_block_after_felt_time(self):
        with mock.patch(
            "core.routing.inner_continuity_facts.build_inner_continuity_facts",
            return_value="INNER CONTINUITY FACTS\n- dream proposals: 2 pending (#65 age 8h); oldest 8h.",
        ):
            captured = self._run_handle_message(env={"MAEZ_INNER_CONTINUITY_FACTS": "1"})

        messages = captured["messages"]
        content = messages[-1]["content"]
        felt_idx = content.index("Felt time: compact present-tense time.")
        inner_idx = content.index("INNER CONTINUITY FACTS")
        owner_idx = content.index("the owner sent via telegram_surface")
        self.assertLess(felt_idx, inner_idx)
        self.assertLess(inner_idx, owner_idx)

    def test_screen_perception_on_inserts_fresh_unvalidated_glance_after_felt_time(self):
        captured = self._run_handle_message(
            env={"MAEZ_SCREEN_PERCEPTION": "1"},
            screen_obs=_FakeScreenObservation(age_s=20),
        )

        content = captured["messages"][-1]["content"]
        felt_idx = content.index("Felt time: compact present-tense time.")
        screen_idx = content.index("[SCREEN - one unvalidated glance")
        owner_idx = content.index("the owner sent via telegram_surface")
        self.assertLess(felt_idx, screen_idx)
        self.assertLess(screen_idx, owner_idx)
        self.assertIn("Looked like: Browsing", content)
        self.assertIn("single frame, not cross-checked", content)
        self.assertNotIn("no fresh glance", content)
        claimable = captured["build_envelope_kwargs"].get("claimable") or []
        self.assertEqual(claimable[0]["kind"], "screen_observation")
        self.assertEqual(claimable[0]["state"], "ok")
        self.assertLessEqual(claimable[0]["age_s"], 180)

    def test_screen_perception_on_without_obs_inserts_honest_empty_block(self):
        captured = self._run_handle_message(env={"MAEZ_SCREEN_PERCEPTION": "1"})

        content = captured["messages"][-1]["content"]
        self.assertIn("SENSE-PRESENCE: no fresh screen glance (none this session)", content)
        self.assertIn("glances are coarse activity labels ~every 60s", content)
        self.assertIn("not on-demand vision", content)
        sense_lines = [
            line for line in content.splitlines() if line.startswith("SENSE-PRESENCE:")
        ]
        self.assertEqual(1, len(sense_lines))
        self.assertEqual([], captured["build_envelope_kwargs"].get("claimable") or [])

    def test_screen_perception_on_with_stale_obs_inserts_honest_empty_age(self):
        captured = self._run_handle_message(
            env={"MAEZ_SCREEN_PERCEPTION": "1"},
            screen_obs=_FakeScreenObservation(age_s=240),
        )

        content = captured["messages"][-1]["content"]
        self.assertIn("SENSE-PRESENCE: no fresh screen glance (last observation ", content)
        self.assertIn("s ago)", content)
        self.assertNotIn("Looked like: Browsing", content)
        self.assertEqual([], captured["build_envelope_kwargs"].get("claimable") or [])
        self.assertNotIn(
            "screen observation",
            captured["build_envelope_kwargs"].get("signals_present") or [],
        )
        self.assertIn(
            "screen observation",
            captured["build_envelope_kwargs"].get("signals_absent") or [],
        )

    def test_screen_perception_off_keeps_legacy_user_prompt_byte_identical(self):
        captured = self._run_handle_message(
            env={"MAEZ_SCREEN_PERCEPTION": "0"},
            screen_obs=_FakeScreenObservation(age_s=20),
        )

        self.assertEqual(EXPECTED_FLAG_OFF_USER_PROMPT, captured["messages"][-1]["content"])
        self.assertNotIn("[SCREEN]", captured["messages"][-1]["content"])
        self.assertNotIn("SENSE-PRESENCE", captured["messages"][-1]["content"])

    def test_screen_perception_unset_keeps_legacy_user_prompt_byte_identical(self):
        captured = self._run_handle_message(
            env={"MAEZ_SCREEN_PERCEPTION": ""},
            screen_obs=_FakeScreenObservation(age_s=20),
        )

        self.assertEqual(EXPECTED_FLAG_OFF_USER_PROMPT, captured["messages"][-1]["content"])
        self.assertNotIn("[SCREEN]", captured["messages"][-1]["content"])
        self.assertNotIn("SENSE-PRESENCE", captured["messages"][-1]["content"])

    def test_screen_perception_message_turn_does_not_capture_on_demand(self):
        with mock.patch("daemon.maez_daemon.screen_observe") as observe:
            captured = self._run_handle_message(
                env={"MAEZ_SCREEN_PERCEPTION": "1"},
                screen_obs=None,
            )

        observe.assert_not_called()
        self.assertIn("SENSE-PRESENCE: no fresh screen glance", captured["messages"][-1]["content"])

    def test_screen_perception_does_not_bypass_owner_auth_gate(self):
        captured = self._run_handle_message(
            env={"MAEZ_SCREEN_PERCEPTION": "1"},
            screen_obs=_FakeScreenObservation(age_s=20),
            owner_auth=False,
        )

        self.assertNotIn("[SCREEN]", captured["messages"][-1]["content"])

    def test_focused_prompt_includes_inner_continuity_block_when_flag_on(self):
        from core.routing.focused_cognition import WorkingSet, focused_synthesize

        captured = {}

        def _chat(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return types.SimpleNamespace(message=types.SimpleNamespace(content="ok [E1]"))

        ws = WorkingSet(
            items=[],
            ordered_evidence_text="[E1] recent dialogue anchor.",
            owner_question="What were we talking about?",
            working_set_chars=28,
            working_set_tokens_est=7,
            citation_render_version="v2",
        )

        focused_synthesize(
            ws,
            surface="telegram_surface",
            chat_fn=_chat,
            model="m",
            inner_continuity_block="INNER CONTINUITY FACTS\n- open wonderings: 1; oldest 3h.",
        )

        self.assertIn("INNER CONTINUITY FACTS", captured["system"])
        self.assertIn("open wonderings: 1", captured["system"])

    def test_focused_prompt_includes_screen_perception_block_when_passed(self):
        from core.routing.focused_cognition import WorkingSet, focused_synthesize

        captured = {}

        def _chat(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return types.SimpleNamespace(message=types.SimpleNamespace(content="ok [E1]"))

        ws = WorkingSet(
            items=[],
            ordered_evidence_text="[E1] recent dialogue anchor.",
            owner_question="What do you see?",
            working_set_chars=28,
            working_set_tokens_est=7,
            citation_render_version="v2",
        )

        focused_synthesize(
            ws,
            surface="telegram_surface",
            chat_fn=_chat,
            model="m",
            screen_perception_block="SENSE-PRESENCE: no fresh screen glance (none this session); glances are coarse activity labels ~every 60s, not on-demand vision",
        )

        self.assertIn("SENSE-PRESENCE: no fresh screen glance", captured["system"])
        self.assertIn("not on-demand vision", captured["system"])

    def test_focused_path_does_not_read_screen_perception_flag_directly(self):
        from core.routing.focused_cognition import WorkingSet, focused_synthesize

        captured = {}

        def _chat(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return types.SimpleNamespace(message=types.SimpleNamespace(content="ok [E1]"))

        ws = WorkingSet(
            items=[],
            ordered_evidence_text="[E1] recent dialogue anchor.",
            owner_question="What do you see?",
            working_set_chars=28,
            working_set_tokens_est=7,
            citation_render_version="v2",
        )

        with mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}):
            focused_synthesize(ws, surface="telegram_surface", chat_fn=_chat, model="m")

        self.assertNotIn("[SCREEN]", captured["system"])
        self.assertNotIn("SENSE-PRESENCE", captured["system"])

    def test_focused_path_does_not_read_inner_continuity_flag_directly(self):
        from core.routing.focused_cognition import WorkingSet, focused_synthesize

        captured = {}

        def _chat(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return types.SimpleNamespace(message=types.SimpleNamespace(content="ok [E1]"))

        ws = WorkingSet(
            items=[],
            ordered_evidence_text="[E1] recent dialogue anchor.",
            owner_question="What were we talking about?",
            working_set_chars=28,
            working_set_tokens_est=7,
            citation_render_version="v2",
        )

        with (
            mock.patch.dict(os.environ, {"MAEZ_INNER_CONTINUITY_FACTS": "1"}),
            mock.patch(
                "core.routing.inner_continuity_facts.build_inner_continuity_facts",
                return_value="INNER CONTINUITY FACTS\n- open wonderings: 1; oldest 3h.",
            ) as build_block,
        ):
            focused_synthesize(ws, surface="telegram_surface", chat_fn=_chat, model="m")

        build_block.assert_not_called()
        self.assertNotIn("INNER CONTINUITY FACTS", captured["system"])


if __name__ == "__main__":
    unittest.main()
