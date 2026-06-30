import contextlib
import os
import types
import unittest
from unittest import mock


class TelegramIdentityRefusalDaemonTests(unittest.TestCase):
    def _daemon(self):
        from daemon import maez_daemon

        class FakeMemory:
            def recall_for_telegram(self, _text):
                return {}

            def recall_for_telegram_living(self, _text, *, record_recalls=True):
                return {}, {}

            def format_for_prompt(self, _recalled, max_chars=None):
                return ""

            def store_telegram(self, *_args, **_kwargs):
                return "raw-id"

        class FreshState:
            def with_freshness(self):
                return self

        daemon = object.__new__(maez_daemon.MaezDaemon)
        daemon.system_prompt = "DAEMON SYSTEM"
        daemon.memory = FakeMemory()
        daemon.lived_episodes = types.SimpleNamespace(add=lambda *args, **kwargs: None)
        daemon.lived_graph = object()
        daemon._camera_presence_state = FreshState()
        daemon._last_screen_obs = None
        daemon._last_calendar_snap = None
        daemon.m1_promoter = None
        daemon._get_public_context = lambda: ""
        daemon._trf_apply_fragment_guard = lambda **kwargs: kwargs["reply"]
        daemon._ws_broadcast = lambda _payload: None
        daemon.boot_time = "boot-test"
        daemon._last_recall_receipt = None
        daemon.cycle_count = 7
        return daemon

    @contextlib.contextmanager
    def _message_stack(self, maez_daemon):
        trace = types.SimpleNamespace(
            trace_id="trace-test",
            audit=types.SimpleNamespace(),
            lived_recall_ids=[],
        )
        stack = contextlib.ExitStack()
        try:
            stack.enter_context(mock.patch.dict(
                os.environ,
                {
                    "MAEZ_LIVED_RECALL": "0",
                    "MAEZ_AMBIENT_BRIEF": "0",
                    "MAEZ_WORKING_SELF": "0",
                    "MAEZ_WONDERING_PURSUIT": "0",
                    "MAEZ_RECALL_STATUS_INTERCEPT": "0",
                },
                clear=False,
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "guard_owner_text",
                return_value=types.SimpleNamespace(matched=False, answer_text=None),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "answer_camera_presence_question",
                return_value=None,
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "perception_snapshot",
                return_value=object(),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "format_snapshot",
                return_value="SYSTEM_STATE",
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "Trace",
                types.SimpleNamespace(start=lambda **_kwargs: trace),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "default_writer",
                return_value=types.SimpleNamespace(write=lambda _trace: None),
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "_trace_hash_text",
                return_value="hash",
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "_trace_extract_evidence_ids",
                return_value=[],
            ))
            stack.enter_context(mock.patch.object(
                maez_daemon,
                "build_temporal_anchor_recall_brief",
                return_value=types.SimpleNamespace(
                    anchor_detected=False,
                    brief_text="",
                    evidence_ids=[],
                ),
            ))
            stack.enter_context(mock.patch(
                "core.cognition.envelope_builder.build_envelope",
                return_value=None,
            ))
            stack.enter_context(mock.patch(
                "core.cognition.envelope_builder.render_envelope_for_prompt",
                return_value="",
            ))
            stack.enter_context(mock.patch(
                "core.cognition.envelope_builder.resolve_recall_cap_chars",
                return_value=1000,
            ))
            stack.enter_context(mock.patch("skills.web_search.needs_web_search", return_value=False))
            stack.enter_context(mock.patch("skills.web_search.is_news_query", return_value=False))
            stack.enter_context(mock.patch(
                "core.safety.audited_output.audit_assistant_text",
                side_effect=lambda text, **_kwargs: text,
            ))
            stack.enter_context(mock.patch("core.ledger.writer.try_write_turn", return_value="turn-1"))
            stack.enter_context(mock.patch(
                "core.ledger.model_reply_persistence.persist_model_reply",
                return_value=None,
            ))
            stack.enter_context(mock.patch(
                "core.llm_client.chat",
                side_effect=AssertionError("identity/refusal path should not call LLM"),
            ))
            yield
        finally:
            stack.close()

    def test_identity_question_returns_deterministic_reply_without_llm(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Yeah comfortable. Let's talk about you. Who are you?",
                source="telegram_surface",
                chat_id="c1",
                chat_history=[],
            )

        self.assertIn("I'm Maez", reply)
        lowered = reply.lower()
        self.assertNotIn("trust covenant", lowered)
        self.assertNotIn("hard constraints", lowered)
        self.assertNotIn("system-prompt", lowered)
        self.assertNotIn("system prompt", lowered)

    def test_identity_question_ignores_dispatcher_transcript_context(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Who are you?",
                source="telegram_surface",
                chat_id="c1",
                chat_history=[],
                transcript="[memory evidence] Recent dialogue anchor: prior chat",
            )

        self.assertIn("I'm Maez", reply)
        lowered = reply.lower()
        self.assertNotIn("trust covenant", lowered)
        self.assertNotIn("hard constraints", lowered)
        self.assertNotIn("system-prompt", lowered)
        self.assertNotIn("system prompt", lowered)

    def test_protected_refusal_followup_returns_deterministic_explanation_without_llm(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        history = [
            {
                "content": (
                    "Rohit: who are you?\n"
                    "Maez: [refused: I won't print protected "
                    "covenant/system-prompt text verbatim. I can summarize.]"
                ),
            }
        ]
        with self._message_stack(maez_daemon):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What does that mean?",
                source="telegram_surface",
                chat_id="c1",
                chat_history=history,
            )

        self.assertIn("private instructions", reply)
        self.assertIn("ordinary words", reply)
        lowered = reply.lower()
        self.assertNotIn("trust covenant", lowered)
        self.assertNotIn("system-prompt", lowered)

    def test_protected_refusal_followup_ignores_dispatcher_transcript_context(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        history = [
            {
                "content": (
                    "Rohit: who are you?\n"
                    "Maez: [Maez declined to quote its private instructions.]"
                ),
            }
        ]
        with self._message_stack(maez_daemon):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What does that mean?",
                source="telegram_surface",
                chat_id="c1",
                chat_history=history,
                transcript="[memory evidence] Recent dialogue anchor: prior chat",
            )

        self.assertIn("private instructions", reply)
        self.assertIn("ordinary words", reply)
        lowered = reply.lower()
        self.assertNotIn("trust covenant", lowered)
        self.assertNotIn("system-prompt", lowered)

    def test_recent_activity_status_ignores_dispatcher_transcript_context(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What are the things you did?",
                source="telegram_surface",
                chat_id="c1",
                chat_history=[],
                transcript="[memory evidence] Recent dialogue anchor: prior chat",
            )

        self.assertIn("honest status is quiet", reply)
        self.assertIn("HEARTBEAT_OK", reply)
        lowered = reply.lower()
        self.assertNotIn("verification ritual", lowered.split("i shouldn't", 1)[0])
        self.assertNotIn("trust covenant", lowered)

    def test_casual_presence_status_returns_deterministic_reply_without_llm_or_focused(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            with mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                side_effect=AssertionError("casual presence route should not call focused"),
            ):
                with self.assertLogs("maez", level="INFO") as logs:
                    reply = maez_daemon.MaezDaemon.handle_message(
                        daemon,
                        "How are you?",
                        source="telegram_surface",
                        chat_id="c1",
                        chat_history=[],
                    )

        self.assertIn("I'm here", reply)
        self.assertIn("ordinary background heartbeat", reply)
        self.assertIn("7", reply)
        self.assertNotIn("completed action", reply.lower())
        self.assertFalse(reply.rstrip().endswith("?"))
        lowered = reply.lower()
        for phrase in (
            "i'm good",
            "i'm great",
            "ready to help",
            "runtime health",
            "diagnostic",
            "identity confirmation",
            "partnership model",
            "trust covenant",
            "what's on your mind",
            "how about you",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

        joined = "\n".join(logs.output)
        self.assertIn(
            "casual_presence_status source=telegram_surface state=honest_empty class=state",
            joined,
        )

    def test_casual_presence_status_ignores_dispatcher_transcript_context(self):
        from daemon import maez_daemon

        daemon = self._daemon()
        with self._message_stack(maez_daemon):
            with mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                side_effect=AssertionError("casual presence route should not call focused"),
            ):
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "What are you up to?",
                    source="telegram_surface",
                    chat_id="c1",
                    chat_history=[],
                    transcript="[memory evidence] Recent dialogue anchor: prior chat",
                )

        self.assertIn("I'm here", reply)
        self.assertIn("ordinary background heartbeat", reply)
        self.assertNotIn("completed action", reply.lower())

    def test_casual_presence_status_guard_yields_to_tool_and_web(self):
        import inspect
        from daemon import maez_daemon

        body_src = inspect.getsource(maez_daemon.MaezDaemon.handle_message)
        marker = "is_casual_presence_status_query"
        self.assertIn(marker, body_src)
        start = body_src.index(marker)
        guard_src = body_src[start: body_src.index("logger.info(", start)]

        self.assertIn("not authoritative_tool_reply", guard_src)
        self.assertIn('not (web_context or "").strip()', guard_src)
        self.assertNotIn("transcript_context", guard_src)

    def test_casual_presence_status_dispatch_precedes_focused(self):
        import inspect
        from daemon import maez_daemon

        body_src = inspect.getsource(maez_daemon.MaezDaemon.handle_message)
        i_presence = body_src.find("_casual_presence_status_reply is not None")
        i_focused = body_src.find("_reply_decision.mode is ReplyMode.FOCUSED")

        self.assertGreaterEqual(i_presence, 0)
        self.assertGreaterEqual(i_focused, 0)
        self.assertLess(i_presence, i_focused)


if __name__ == "__main__":
    unittest.main()
