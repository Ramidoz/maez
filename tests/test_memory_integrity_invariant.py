# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Memory-integrity invariant — Commit 1 of the 2026-04-23 audit repair pass.

Invariant guarded here (birth-critical per the owner's covenant):

    Every assistant-authored text stored after Commit 1 is the same
    text that passed the final self-claim audit for its surface and
    grounding context.

Before this commit, several paths did `llm.chat() -> store -> audit ->
return`, which let unaudited fabrications land in raw memory even when
the user saw the corrected text. The fix centralizes the audit in a
single helper (`core.safety.audited_output.audit_assistant_text`) and
moves the `audit` call BEFORE every `store` on the affected paths.

These tests lock in the ordering, not the specific prose the audit
produces. If audit semantics change in the future, the assertions here
still hold as long as the invariant holds.

Covered paths:
  1. `core/safety/audited_output.audit_assistant_text` — fail-open
     contract (audit unavailable returns original text, does not
     raise, does log).
  2. `core/safety/audited_output.audit_assistant_text` — transcript
     presence auto-derives `in_tool_continuation`.
  3. `daemon/maez_daemon.MaezDaemon.handle_message` — signature
     accepts `transcript=`, `signals_present=`, `signals_absent=`.
  4. `skills/surface/maez_adapter` — no longer imports
     `core.self_claim_audit` directly (audit moved into daemon).
  5. `skills/web_interface` — web `/chat` audits before memory store
     and before trajectory log (source-level ordering assertion).
  6. `daemon._check_proactive_opinion` — source-level assertions that
     (a) the function imports `audit_assistant_text`, (b) stores the
     sent text with `type="proactive_opinion"` provenance metadata.
  7. `daemon/maez_daemon.py` retry path — source-level assertion that
     `audit_assistant_text` is invoked on `retry_content` before the
     retry's re-score.

Most tests are source-level (AST / text probe) rather than full live
daemon runs — Commit 1 is a contract change, not a behavior change,
and the contract is cheaper + more stable to assert in the source than
in a full runtime harness.
"""
from __future__ import annotations

import ast
import contextlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class AuditedOutputHelper(unittest.TestCase):
    """The helper itself. Everything else depends on it."""

    def test_import(self):
        from core.safety.audited_output import audit_assistant_text  # noqa: F401

    def test_empty_text_returns_as_is(self):
        from core.safety.audited_output import audit_assistant_text
        for empty in ("", "   ", "\n"):
            self.assertEqual(audit_assistant_text(empty, surface="t"), empty)

    def test_fail_open_on_audit_import_error(self):
        """If the audit module cannot be imported, return original text + warn.

        We simulate this by pointing MAEZ_SEMANTIC_AUDIT=0 (which causes
        the real audit to early-return noop) — functionally equivalent
        to an unavailable audit from the helper's perspective: original
        text is preserved.
        """
        from core.safety.audited_output import audit_assistant_text
        prior = os.environ.get("MAEZ_SEMANTIC_AUDIT")
        os.environ["MAEZ_SEMANTIC_AUDIT"] = "0"
        try:
            out = audit_assistant_text("hi owner", surface="t")
            self.assertEqual(out, "hi owner")
        finally:
            if prior is None:
                os.environ.pop("MAEZ_SEMANTIC_AUDIT", None)
            else:
                os.environ["MAEZ_SEMANTIC_AUDIT"] = prior

    def test_transcript_derives_in_tool_continuation(self):
        """When a non-empty transcript is passed, the audit is told to
        skip the judge — real tool stdout grounds the claim by
        construction. We assert via the underlying audit's return-shape:
        with MAEZ_SEMANTIC_AUDIT=0, both paths return the original text
        AND the helper's derived in_tool_continuation is what gets
        passed through. The important functional contract: passing
        transcript="" does not mistakenly mark tool continuation.
        """
        from core.safety.audited_output import audit_assistant_text
        out_empty = audit_assistant_text("text", surface="t", transcript="")
        out_with = audit_assistant_text("text", surface="t",
                                         transcript="some real tool stdout")
        # Both return the original text (helper is thin); the
        # observable difference is the caller contract not a return
        # value change. Assert both paths are non-raising.
        self.assertEqual(out_empty, "text")
        self.assertEqual(out_with, "text")


class DaemonHandleMessageContract(unittest.TestCase):
    """MaezDaemon.handle_message must accept the new audit-context kwargs.

    Source-level assertion via AST — avoids importing daemon.maez_daemon
    entirely, which transitively pulls in skills.calendar_perception
    which requires google-auth. google-auth is an optional [google]
    extra and CI doesn't install it, so any test that imports the
    daemon fails on CI even though the signature check itself has
    nothing to do with Google APIs.
    """

    def test_signature_accepts_transcript_and_signals(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        tree = ast.parse(src)

        # Find MaezDaemon.handle_message (method on the class, not a
        # same-named free function elsewhere).
        target: ast.FunctionDef | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "MaezDaemon":
                for sub in node.body:
                    if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and sub.name == "handle_message"):
                        target = sub
                        break
                break
        self.assertIsNotNone(
            target, "MaezDaemon.handle_message not found in "
                    "daemon/maez_daemon.py",
        )

        # Flatten args + kwonly_args into one name → default map so we
        # can assert presence + default values regardless of whether
        # they're positional or keyword-only.
        def _param_defaults(fn: ast.FunctionDef) -> dict:
            out: dict[str, ast.AST | None] = {}
            args = fn.args
            # Positional: defaults align with the TAIL of args.args.
            n_pos = len(args.args)
            n_defaults = len(args.defaults)
            for i, a in enumerate(args.args):
                di = i - (n_pos - n_defaults)
                out[a.arg] = args.defaults[di] if di >= 0 else None
            # Keyword-only: defaults align 1:1 with kwonlyargs.
            for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True):
                out[a.arg] = d
            return out

        params = _param_defaults(target)
        self.assertIn("transcript", params,
                      "handle_message must accept transcript= so the "
                      "adapter can pass jarvis tool-loop output.")
        self.assertIn("recall_items", params,
                      "handle_message must accept recall_items= so the "
                      "adapter can pass structured recall provenance.")
        self.assertIn("signals_present", params)
        self.assertIn("signals_absent", params)
        # Defaults must be safe for legacy callers (no-transcript,
        # no-manifest invocations keep working). Compare via ast.Constant.
        t_default = params["transcript"]
        self.assertIsInstance(t_default, ast.Constant)
        self.assertEqual(t_default.value, "",
                         "transcript default must be an empty string")
        for key in ("recall_items", "signals_present", "signals_absent"):
            d = params[key]
            self.assertIsInstance(d, ast.Constant)
            self.assertIsNone(d.value,
                              f"{key} default must be None")

    def test_handle_message_source_uses_audited_output(self):
        """handle_message's body should call audit_assistant_text.

        Source-level assertion — avoids spinning up the full daemon,
        which needs ChromaDB + ollama + soul files to initialize. The
        contract is: the function body must reference the helper so
        the stored reply equals the audited reply.
        """
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        # Find the handle_message definition and its body range.
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "handle_message"
            ):
                body_src = ast.get_source_segment(src, node) or ""
                self.assertIn("audit_assistant_text(", body_src,
                              "handle_message body must call "
                              "audit_assistant_text() before store_telegram().")
                # Ordering assertion on function-call patterns (opening
                # paren included) so comments mentioning the name don't
                # move the index. audit_assistant_text() call must
                # appear BEFORE store_telegram() call.
                a = body_src.find("audit_assistant_text(")
                s = body_src.find("store_telegram(")
                self.assertLess(a, s,
                                "audit_assistant_text() must be called "
                                "BEFORE store_telegram() in handle_message.")
                found = True
                break
        self.assertTrue(found, "handle_message not found in maez_daemon.py")

    def test_handle_message_keeps_tool_transcript_out_of_owner_text(self):
        """Tool transcripts are synthesis context, not owner messages.

        If adapters fold Jarvis/no-tool instructions into `text`, memory,
        web-search, traces, and lived recall all treat internal scaffolding
        as something the owner actually said. handle_message must instead
        receive clean owner text and append transcript context as a system
        message.
        """
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
                body_src = ast.get_source_segment(src, node) or ""
                self.assertIn("Tool transcripts are synthesis context", body_src)
                self.assertIn('"role": "system"', body_src)
                self.assertIn("_instruction_block_for_transcript", body_src)
                self.assertIn("_transcript_instruction_state", body_src)
                self.assertIn("daemon_transcript_instruction_state", body_src)
                self.assertNotIn("build_synthesis_user_text(", body_src)
                return
        self.fail("handle_message not found in maez_daemon.py")

    def test_dispatcher_enabled_transcript_gates_daemon_parallel_web_search(self):
        """Dispatcher transcripts are the fresh-evidence authority.

        The daemon synthesis layer must not also run its legacy
        needs_web_search branch after the dispatcher already produced a
        transcript. That was the active-path sibling of the legacy
        Telegram Pipeline A gate.
        """
        from daemon.maez_daemon import _daemon_parallel_web_search_enabled

        with mock.patch.dict("os.environ", {"MAEZ_RECALL_TRIAD_ENABLED": "1"}):
            self.assertFalse(
                _daemon_parallel_web_search_enabled(
                    "[fresh evidence] LIVE_REDDIT: recent posts"
                )
            )
            self.assertTrue(_daemon_parallel_web_search_enabled(""))

        with mock.patch.dict("os.environ", {"MAEZ_RECALL_TRIAD_ENABLED": "0"}):
            self.assertTrue(
                _daemon_parallel_web_search_enabled(
                    "[fresh evidence] LIVE_REDDIT: recent posts"
                )
            )

    def test_dispatcher_transcript_prompt_consolidates_to_one_system_message(self):
        """Dispatcher transcript context must be one system message, transcript last."""
        from daemon.maez_daemon import _consolidate_system_messages

        transcript_context = (
            "[fresh evidence] LIVE_REDDIT: recent posts\n\n"
            "HARD INSTRUCTION — dispatcher"
        )
        messages = [
            {"role": "system", "content": "daemon system prompt"},
            {"role": "user", "content": "Rohit: previous turn"},
            {"role": "assistant", "content": "Maez: previous reply"},
            {"role": "system", "content": "lived recall brief"},
            {"role": "system", "content": "ambient context"},
        ]

        consolidated = _consolidate_system_messages(
            messages,
            final_system_part=transcript_context,
        )

        system_messages = [m for m in consolidated if m.get("role") == "system"]
        self.assertEqual(len(system_messages), 1)
        self.assertEqual(consolidated[0]["role"], "system")
        self.assertEqual(consolidated[1]["role"], "user")
        self.assertEqual(consolidated[2]["role"], "assistant")
        self.assertTrue(system_messages[0]["content"].endswith(transcript_context))

        handle_src = ast.get_source_segment(
            (_REPO / "daemon" / "maez_daemon.py").read_text(),
            next(
                node
                for node in ast.walk(ast.parse((_REPO / "daemon" / "maez_daemon.py").read_text()))
                if isinstance(node, ast.FunctionDef) and node.name == "handle_message"
            ),
        ) or ""
        self.assertIn("_consolidate_system_messages", handle_src)
        self.assertIn("final_system_part=turn_final_context", handle_src)

    def _build_daemon_for_handle_message(self):
        from daemon import maez_daemon

        class FakeMemory:
            def recall_for_telegram(self, _text):
                return {}

            def format_for_prompt(self, _recalled, max_chars=None):
                return "MEMORY BLOCK"

            def store_telegram(self, *_args, **_kwargs):
                return "raw-memory-id"

        class FreshState:
            def with_freshness(self):
                return self

        daemon = object.__new__(maez_daemon.MaezDaemon)
        daemon.system_prompt = "DAEMON SYSTEM"
        daemon.memory = FakeMemory()
        daemon.lived_episodes = types.SimpleNamespace(
            add=lambda *args, **kwargs: None,
        )
        daemon.lived_graph = object()
        daemon._camera_presence_state = FreshState()
        daemon._last_screen_obs = None
        daemon._last_calendar_snap = None
        daemon.m1_promoter = None
        daemon._get_public_context = lambda: ""
        daemon._trf_apply_fragment_guard = lambda **kwargs: kwargs["reply"]
        daemon._ws_broadcast = lambda _payload: None
        daemon.boot_time = "bootA"
        daemon._last_recall_receipt = None
        return daemon

    @contextlib.contextmanager
    def _handle_message_mock_stack(
        self,
        maez_daemon,
        captured: dict[str, list[dict]],
        *,
        needs_web_search: bool = False,
        web_context: str = "",
        reply: str = "grounded reply",
    ):
        trace = types.SimpleNamespace(
            audit=types.SimpleNamespace(),
            lived_recall_ids=[],
        )

        def fake_chat(*, model, messages, think, options):
            captured["messages"] = messages
            return types.SimpleNamespace(
                message=types.SimpleNamespace(content=reply)
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
            stack.enter_context(mock.patch(
                "skills.web_search.needs_web_search",
                return_value=needs_web_search,
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.is_news_query",
                return_value=False,
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.search",
                return_value={
                    "query": "local llm",
                    "success": bool(web_context),
                    "results": [{"title": "Post"}] if web_context else [],
                    "result_count": 1 if web_context else 0,
                },
            ))
            stack.enter_context(mock.patch(
                "skills.web_search.format_for_context",
                return_value=web_context,
            ))
            stack.enter_context(mock.patch(
                "core.routing.observation.record_legacy_web_search_observation",
                return_value=None,
            ))
            stack.enter_context(mock.patch(
                "core.safety.audited_output.audit_assistant_text",
                side_effect=lambda text, **_kwargs: text,
            ))
            stack.enter_context(mock.patch(
                "core.ledger.writer.try_write_turn",
                return_value="turn-1",
            ))
            stack.enter_context(mock.patch(
                "core.ledger.model_reply_persistence.persist_model_reply",
                return_value=None,
            ))
            stack.enter_context(mock.patch(
                "core.llm_client.chat",
                side_effect=fake_chat,
            ))
            yield
        finally:
            stack.close()

    def _recall_outcome_lines(self, logs):
        return [ln for ln in logs.output if "recall_outcome" in ln]

    def test_recall_outcome_emitted_on_dated_legacy_turn(self):
        from daemon import maez_daemon

        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "0"}, clear=False
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "what did we decide around April 27?",
                    chat_id="c1",
                    source="telegram",
                )
        lines = self._recall_outcome_lines(logs)
        self.assertEqual(len(lines), 1, lines)
        line = lines[-1]
        self.assertIn("schema_version=recall_outcome.v1", line)
        self.assertIn("mode=legacy", line)
        self.assertIn("turn_kind=dated", line)
        self.assertIn("outcome_class=declined_unavailable", line)
        self.assertIn("denial_kind=carrier_unavailable", line)
        self.assertIn("receipt_or_na=na", line)
        self.assertIn("had_confirmed=na", line)
        self.assertNotIn("April 27", line)
        self.assertNotIn("decide", line)

    def test_recall_outcome_on_ordinary_turn_is_not_fabrication_class(self):
        from daemon import maez_daemon

        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "0"}, clear=False
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "what is a transformer?",
                    chat_id="c1",
                    source="telegram",
                )
        lines = self._recall_outcome_lines(logs)
        self.assertEqual(len(lines), 1, lines)
        line = lines[-1]
        self.assertIn("turn_kind=ordinary", line)
        self.assertIn("outcome_class=ordinary_answered", line)
        self.assertNotIn("answered_unverifiable", line)

    def test_recall_outcome_legacy_absence_phrase_is_declined_unverified(self):
        from daemon import maez_daemon

        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(
                maez_daemon,
                captured,
                reply="I don't remember that dated memory.",
            ), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "0"}, clear=False
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "what were we just talking about?",
                    chat_id="c1",
                    source="telegram",
                )
        lines = self._recall_outcome_lines(logs)
        self.assertEqual(len(lines), 1, lines)
        line = lines[-1]
        self.assertIn("outcome_class=declined_unverified", line)
        self.assertIn("turn_kind=continuity", line)
        self.assertIn("denial_kind=na", line)
        self.assertIn("receipt_or_na=na", line)

    def test_handle_message_sends_one_system_message_with_dispatcher_suffix(self):
        """The live daemon prompt assembly must send one system message."""
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}

        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA right now",
                source="telegram_surface",
                transcript="[fresh evidence] LIVE_REDDIT: recent posts",
                chat_history=[
                    {"content": "Rohit: earlier\nMaez: prior answer"},
                ],
            )

        self.assertEqual(reply, "grounded reply")
        system_messages = [
            message
            for message in captured["messages"]
            if message.get("role") == "system"
        ]
        self.assertEqual(len(system_messages), 1)
        self.assertIn(
            "[fresh evidence] LIVE_REDDIT: recent posts",
            system_messages[0]["content"],
        )
        self.assertIn("EVIDENCE PRESENT THIS TURN", system_messages[0]["content"])
        self.assertTrue(
            system_messages[0]["content"].rstrip().endswith(
                "the evidence above contradicts that."
            )
        )

    def test_handle_message_feeds_raw_transcript_to_detector(self):
        """Evidence detection must never scan transcript_context."""
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        seen: dict[str, str] = {}

        def _spy(*, transcript, web_context):
            seen["transcript"] = transcript
            seen["web_context"] = web_context
            from core.routing.evidence_state import EvidenceState

            return EvidenceState(evidence_present=False)

        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch(
            "core.routing.evidence_state.turn_evidence_state",
            side_effect=_spy,
        ):
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA right now",
                source="telegram_surface",
                transcript="[fresh evidence] LIVE_REDDIT: recent posts",
                chat_history=[
                    {"content": "Rohit: earlier\nMaez: prior answer"},
                ],
            )

        self.assertEqual(
            seen["transcript"],
            "[fresh evidence] LIVE_REDDIT: recent posts",
        )
        self.assertNotIn("HARD INSTRUCTION", seen["transcript"])

    def test_directive_general_on_legacy_web_turn(self):
        """Legacy web results should get the same final-tail evidence steer."""
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()
        web_context = (
            "[WEB SEARCH: 'local llm'] 2 results - 2026\n"
            "  1. Post\n"
            "     body"
        )

        with self._handle_message_mock_stack(
            maez_daemon,
            captured,
            needs_web_search=True,
            web_context=web_context,
        ):
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "what's the latest on local llms",
                source="telegram_surface",
                transcript="",
            )

        system_messages = [
            message
            for message in captured["messages"]
            if message.get("role") == "system"
        ]
        self.assertEqual(len(system_messages), 1)
        self.assertIn("web search results", system_messages[0]["content"])
        self.assertTrue(
            system_messages[0]["content"].rstrip().endswith(
                "the evidence above contradicts that."
            )
        )

    def test_no_directive_when_no_evidence(self):
        """No evidence means the steer stays absent."""
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured):
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "just chatting, nothing to look up",
                source="telegram_surface",
                transcript="",
            )

        system_messages = [
            message
            for message in captured["messages"]
            if message.get("role") == "system"
        ]
        self.assertFalse(
            any(
                "EVIDENCE PRESENT THIS TURN" in message["content"]
                for message in system_messages
            )
        )

    def test_system_part_capture_includes_evidence_directive(self):
        """The daemon system-part seam must expose the directive label."""
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs(maez_daemon.logger, level="INFO") as log_capture:
            with self._handle_message_mock_stack(maez_daemon, captured):
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "Search r/LocalLLaMA right now",
                    source="telegram_surface",
                    transcript="[fresh evidence] LIVE_REDDIT: recent posts",
                )

        joined = "\n".join(log_capture.output)
        self.assertIn("daemon_system_part_shape", joined)
        self.assertIn("evidence_precedence_directive", joined)

    def test_daemon_prompt_capture_summarizes_structure_without_full_text(self):
        """Diagnostic capture should expose prompt shape, not full prompt text."""
        from daemon import maez_daemon

        transcript_context = "[fresh evidence] LIVE_REDDIT\n\ninstruction"
        messages = [
            {
                "role": "system",
                "content": (
                    "SYSTEM-BEGIN "
                    + ("a" * 160)
                    + " SYSTEM-END\n\n"
                    + transcript_context
                ),
            },
            {"role": "assistant", "content": "prior answer"},
            {
                "role": "user",
                "content": "USER-BEGIN " + ("b" * 160) + " USER-END",
            },
        ]

        summary = maez_daemon._summarize_daemon_prompt_messages(
            messages,
            transcript_context=transcript_context,
        )

        self.assertEqual(summary["message_count"], 3)
        self.assertEqual(summary["role_sequence"], "system,assistant,user")
        self.assertEqual(summary["system_message_count"], 1)
        self.assertEqual(summary["user_message_length"], 180)
        self.assertTrue(summary["transcript_is_suffix"])
        self.assertEqual(len(summary["message_hashes"].split(",")), 3)
        self.assertIn("SYSTEM-BEGIN", summary["message_0_head"])
        self.assertIn("SYSTEM-END", summary["message_0_tail"])
        self.assertLessEqual(len(summary["message_0_head"]), 100)
        self.assertLessEqual(len(summary["message_0_tail"]), 100)
        self.assertNotIn("a" * 120, str(summary))

        with self.assertLogs(maez_daemon.logger, level="INFO") as log_capture:
            maez_daemon._log_daemon_prompt_payload_shape(
                surface="telegram_surface",
                call_purpose="llm_synthesis",
                messages=messages,
                transcript_context=transcript_context,
            )
        joined = "\n".join(log_capture.output)
        self.assertIn("daemon_prompt_payload_shape", joined)
        self.assertIn("surface=telegram_surface", joined)
        self.assertIn("call_purpose=llm_synthesis", joined)
        self.assertIn('"role_sequence": "system,assistant,user"', joined)

    def test_payload_shape_reports_evidence_directive_suffix(self):
        """Prompt capture should name the new evidence directive tail honestly."""
        from daemon import maez_daemon

        transcript_context = "[fresh evidence] LIVE_REDDIT\n\ninstruction"
        directive = (
            "EVIDENCE PRESENT THIS TURN.\n"
            "You are holding real evidence.\n"
            "the evidence above contradicts that."
        )
        messages = [
            {
                "role": "system",
                "content": f"BASE\n\n{transcript_context}\n\n{directive}",
            },
            {"role": "user", "content": "u"},
        ]

        summary = maez_daemon._summarize_daemon_prompt_messages(
            messages,
            transcript_context=transcript_context,
            evidence_directive=directive,
        )

        self.assertFalse(summary["transcript_is_suffix"])
        self.assertTrue(summary["evidence_directive_is_suffix"])

    def test_focused_replaces_megaprompt_when_flag_and_text_evidence(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("voiced answer [E1]", ["E1"], 800)
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA right now",
                source="telegram_surface",
                transcript="[memory context] r/LocalLLaMA:\n- LiquidAI LFM2.5 (67 pts)",
                chat_history=[],
            )

        self.assertEqual(reply, "voiced answer [E1]")
        fsyn.assert_called_once()
        megachat.assert_not_called()

    def test_focused_excludes_voice_surface_v1(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn:
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "what's new",
                source="voice",
                transcript="[memory context] r/x:\n- a post (1 pts)",
                chat_history=[],
            )

        fsyn.assert_not_called()

    def test_focused_legacy_when_flag_off(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn:
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA",
                source="telegram_surface",
                transcript="[memory context] r/x:\n- a post (1 pts)",
                chat_history=[],
            )

        fsyn.assert_not_called()

    def test_focused_fallback_on_error_uses_legacy_megaprompt(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
            side_effect=RuntimeError("boom"),
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy reply")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA",
                source="telegram_surface",
                transcript="[memory context] r/x:\n- a post (1 pts)",
                chat_history=[],
            )

        self.assertEqual(reply, "legacy reply")
        fsyn.assert_called_once()
        megachat.assert_called()

    def test_dated_no_match_reaches_focused_status_not_legacy(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("No dated memory [E1]", ["E1"], 200)
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy should not answer")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What did I record on January 3?",
                source="telegram_surface",
                transcript="",
                chat_history=[],
            )

        self.assertEqual(reply, "No dated memory [E1]")
        fsyn.assert_called_once()
        working_set = fsyn.call_args.args[0]
        self.assertEqual(working_set.items[0].source_type, "temporal_recall_status")
        megachat.assert_not_called()

    def test_dated_focused_error_never_falls_through_to_legacy(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
            side_effect=RuntimeError("boom"),
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy should not answer")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What did I record on January 3?",
                source="telegram_surface",
                transcript="",
                chat_history=[],
            )

        self.assertIn("I don't have a dated memory for that window", reply)
        self.assertIn("guesswork", reply)
        fsyn.assert_called_once()
        megachat.assert_not_called()

    def test_dated_empty_focused_reply_is_consulted_no_match(self):
        from daemon import maez_daemon
        from core.routing.focused_cognition import FocusedResult

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                return_value=FocusedResult("", [], 100),
            ) as fsyn, mock.patch(
                "core.routing.focused_cognition.record_focused_cognition_run",
                return_value="focused-row-1",
            ), mock.patch(
                "core.llm_client.chat",
            ) as megachat:
                megachat.return_value = types.SimpleNamespace(
                    message=types.SimpleNamespace(content="legacy should not answer")
                )
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "What did I record on January 3?",
                    source="telegram_surface",
                    transcript="",
                    chat_history=[],
                )

        self.assertIn("I don't have a dated memory for that window", reply)
        joined_logs = "\n".join(logs.output)
        self.assertIn("carrier_receipt=consulted", joined_logs)
        self.assertIn("reply_kind=no_dated_memory", joined_logs)
        fsyn.assert_called_once()
        megachat.assert_not_called()

    def test_dated_assembly_error_is_path_unavailable_not_absence(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
            ), mock.patch(
                "core.routing.focused_cognition.assemble_working_set",
                side_effect=RuntimeError("assembly boom"),
            ) as assemble, mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
            ) as fsyn, mock.patch(
                "core.routing.focused_cognition.record_focused_cognition_run",
                return_value="focused-row-1",
            ), mock.patch(
                "core.llm_client.chat",
            ) as megachat:
                megachat.return_value = types.SimpleNamespace(
                    message=types.SimpleNamespace(content="legacy should not answer")
                )
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "What did I record on January 3?",
                    source="telegram_surface",
                    transcript="",
                    chat_history=[],
                )

        self.assertIn("went to check my dated memory", reply.lower())
        self.assertIn("lookup errored out", reply.lower())
        self.assertNotIn("capability", reply.lower())
        self.assertNotIn("I don't have a dated memory", reply)
        joined_logs = "\n".join(logs.output)
        self.assertIn("carrier_receipt=consult_failed", joined_logs)
        self.assertIn("reply_kind=carrier_failed", joined_logs)
        assemble.assert_called_once()
        fsyn.assert_not_called()
        megachat.assert_not_called()

    def test_dated_voice_path_is_not_consulted_and_does_not_claim_absence(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
            ) as fsyn, mock.patch(
                "core.llm_client.chat",
            ) as megachat:
                megachat.return_value = types.SimpleNamespace(
                    message=types.SimpleNamespace(content="legacy should not answer")
                )
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "What did I record on January 3?",
                    source="voice",
                    transcript="",
                    chat_history=[],
                )

        self.assertIn("can't reach my dated memory from here right now", reply.lower())
        self.assertNotIn("I don't have a dated memory", reply)
        joined_logs = "\n".join(logs.output)
        self.assertIn("carrier_receipt=not_consulted", joined_logs)
        self.assertIn("reply_kind=carrier_unavailable", joined_logs)
        fsyn.assert_not_called()
        megachat.assert_not_called()

    def test_focused_crash_with_confirmed_item_is_transport_not_absence(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()
        transcript = (
            "[memory context] dated core:\n"
            '<RECALLED id="core-infra" date_match="exact_date">'
            "April 27 infrastructure ground truth reached context."
            "</RECALLED>"
        )

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
            side_effect=RuntimeError("boom"),
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy should not answer")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What happened around April 27?",
                source="telegram_surface",
                transcript=transcript,
                chat_history=[],
            )

        self.assertIn("I have a dated memory for that", reply)
        self.assertIn("couldn't pull it together", reply)
        self.assertNotIn("I don't have a dated memory", reply)
        fsyn.assert_called_once()
        working_set = fsyn.call_args.args[0]
        self.assertTrue(
            any(
                item.temporal_provenance
                and item.temporal_provenance.get("confirmed")
                for item in working_set.items
            )
        )
        megachat.assert_not_called()

    def test_handle_message_passes_recall_items_to_focused_assemble(self):
        from daemon import maez_daemon
        from core.dispatcher.layer1 import RecallItem
        from core.routing.focused_cognition import FocusedResult

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()
        full = (
            "INFRASTRUCTURE GROUND-TRUTH 2026-04-27 "
            + ("full incident context " * 80)
        )
        recall_items = [
            RecallItem(
                text=full,
                source_type="memory_context",
                durable_id="core-april-27",
                temporal_provenance={"method": "exact_date", "confirmed": True},
            )
        ]
        truncated_transcript = (
            "[memory context]\n"
            '<RECALLED id="core-april-27" date_match="exact_date">'
            "INFRASTRUCTURE GROUND-TRUTH under a"
        )

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            fsyn.return_value = FocusedResult("April 27 incident [E1]", ["E1"], 400)
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy should not answer")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What did we note around April 27?",
                source="telegram_surface",
                transcript=truncated_transcript,
                chat_history=[],
                recall_items=recall_items,
            )

        self.assertEqual(reply, "April 27 incident [E1]")
        fsyn.assert_called_once()
        working_set = fsyn.call_args.args[0]
        self.assertFalse(
            any(item.source_type == "temporal_recall_status" for item in working_set.items)
        )
        top = working_set.items[0]
        self.assertEqual(top.source_type, "memory_context")
        self.assertEqual(top.durable_id, "core-april-27")
        self.assertTrue(top.temporal_provenance["confirmed"])
        self.assertIn("INFRASTRUCTURE GROUND-TRUTH", top.text)
        self.assertIn("full incident context", top.text)
        megachat.assert_not_called()

    def test_handle_message_empty_recall_items_preserves_transcript_memory(self):
        from daemon import maez_daemon
        from core.routing.focused_cognition import FocusedResult

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()
        transcript = (
            "[memory context]\n"
            '<RECALLED id="core-april-27" date_match="exact_date">'
            "INFRASTRUCTURE GROUND-TRUTH 2026-04-27 full incident context"
            "</RECALLED>"
        )

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            fsyn.return_value = FocusedResult("April 27 incident [E1]", ["E1"], 400)
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy should not answer")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What did we note around April 27?",
                source="telegram_surface",
                transcript=transcript,
                chat_history=[],
                recall_items=(),
            )

        self.assertEqual(reply, "April 27 incident [E1]")
        fsyn.assert_called_once()
        working_set = fsyn.call_args.args[0]
        self.assertFalse(
            any(
                item.source_type == "temporal_recall_status"
                for item in working_set.items
            )
        )
        top = working_set.items[0]
        self.assertEqual(top.source_type, "memory_context")
        self.assertTrue(top.temporal_provenance["confirmed"])
        self.assertIn("INFRASTRUCTURE GROUND-TRUTH", top.text)
        megachat.assert_not_called()

    def test_focused_empty_no_confirmed_is_honest_absence(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("", [], 0)
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy should not answer")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What did I record on January 3?",
                source="telegram_surface",
                transcript="",
                chat_history=[],
            )

        self.assertIn("I don't have a dated memory for that window", reply)
        self.assertIn("guesswork", reply)
        fsyn.assert_called_once()
        megachat.assert_not_called()

    def test_reply_mode_resolver_drives_clinical_skip_tail_without_tail_seams(self):
        from core.routing import reply_mode
        from daemon import maez_daemon

        daemon = self._build_daemon_for_handle_message()
        daemon.memory.store_telegram = mock.Mock(wraps=daemon.memory.store_telegram)
        daemon.lived_episodes.add = mock.Mock()
        clinical = types.SimpleNamespace(
            matched=True,
            answer_text="clinical boundary reply",
            promotion_policy="m1_ineligible_clinical_boundary",
        )

        with contextlib.ExitStack() as stack:
            resolver = stack.enter_context(
                mock.patch(
                    "core.routing.reply_mode.resolve_reply_mode",
                    wraps=reply_mode.resolve_reply_mode,
                )
            )
            guard = stack.enter_context(
                mock.patch.object(maez_daemon, "guard_owner_text", return_value=clinical)
            )
            camera = stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "answer_camera_presence_question",
                    return_value="camera should not run",
                )
            )
            trace = stack.enter_context(mock.patch.object(maez_daemon.Trace, "start"))
            default_writer = stack.enter_context(
                mock.patch.object(maez_daemon, "default_writer")
            )
            needs_web = stack.enter_context(
                mock.patch("skills.web_search.needs_web_search")
            )
            llm_chat = stack.enter_context(mock.patch("core.llm_client.chat"))
            audit = stack.enter_context(
                mock.patch("core.safety.audited_output.audit_assistant_text")
            )
            ledger = stack.enter_context(mock.patch("core.ledger.writer.try_write_turn"))
            model_reply = stack.enter_context(
                mock.patch("core.ledger.model_reply_persistence.persist_model_reply")
            )

            reply = maez_daemon.MaezDaemon.handle_message(
                daemon, "clinical boundary input", source="telegram_surface"
            )

        self.assertEqual(reply, "clinical boundary reply")
        resolver.assert_called()
        guard.assert_called_once()
        camera.assert_not_called()
        trace.assert_not_called()
        default_writer.assert_not_called()
        needs_web.assert_not_called()
        llm_chat.assert_not_called()
        audit.assert_not_called()
        ledger.assert_not_called()
        model_reply.assert_not_called()
        daemon.memory.store_telegram.assert_not_called()
        daemon.lived_episodes.add.assert_not_called()

    def test_reply_mode_resolver_drives_camera_skip_tail_without_tail_seams(self):
        from core.routing import reply_mode
        from daemon import maez_daemon

        daemon = self._build_daemon_for_handle_message()
        daemon.memory.store_telegram = mock.Mock(wraps=daemon.memory.store_telegram)
        daemon.lived_episodes.add = mock.Mock()
        nonmatch = types.SimpleNamespace(
            matched=False,
            answer_text=None,
            promotion_policy="m1_eligible",
        )

        with contextlib.ExitStack() as stack:
            resolver = stack.enter_context(
                mock.patch(
                    "core.routing.reply_mode.resolve_reply_mode",
                    wraps=reply_mode.resolve_reply_mode,
                )
            )
            guard = stack.enter_context(
                mock.patch.object(maez_daemon, "guard_owner_text", return_value=nonmatch)
            )
            camera = stack.enter_context(
                mock.patch.object(
                    maez_daemon,
                    "answer_camera_presence_question",
                    return_value="camera direct reply",
                )
            )
            trace = stack.enter_context(mock.patch.object(maez_daemon.Trace, "start"))
            default_writer = stack.enter_context(
                mock.patch.object(maez_daemon, "default_writer")
            )
            needs_web = stack.enter_context(
                mock.patch("skills.web_search.needs_web_search")
            )
            llm_chat = stack.enter_context(mock.patch("core.llm_client.chat"))
            audit = stack.enter_context(
                mock.patch("core.safety.audited_output.audit_assistant_text")
            )
            ledger = stack.enter_context(mock.patch("core.ledger.writer.try_write_turn"))
            model_reply = stack.enter_context(
                mock.patch("core.ledger.model_reply_persistence.persist_model_reply")
            )

            reply = maez_daemon.MaezDaemon.handle_message(
                daemon, "is the camera active?", source="telegram_surface"
            )

        self.assertEqual(reply, "camera direct reply")
        resolver.assert_called()
        guard.assert_called_once()
        camera.assert_called_once()
        trace.assert_not_called()
        default_writer.assert_not_called()
        needs_web.assert_not_called()
        llm_chat.assert_not_called()
        audit.assert_not_called()
        ledger.assert_not_called()
        model_reply.assert_not_called()
        daemon.memory.store_telegram.assert_not_called()
        daemon.lived_episodes.add.assert_not_called()

    def test_reply_mode_resolver_drives_echo_branch_with_same_reply(self):
        from core.routing import reply_mode
        from daemon import maez_daemon

        daemon = self._build_daemon_for_handle_message()
        captured: dict[str, list[dict]] = {}
        text = (
            "For the continuity witness: dialogue anchors now strip stale prior "
            "citations before they become current evidence. Say that back in one sentence."
        )
        chat_history = [
            {"role": "user", "content": "Earlier note"},
            {
                "role": "assistant",
                "content": "[E1] stale citation that should not be repeated",
            },
        ]

        with (
            self._handle_message_mock_stack(maez_daemon, captured),
            mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
                clear=False,
            ),
            mock.patch(
                "core.routing.reply_mode.resolve_reply_mode",
                wraps=reply_mode.resolve_reply_mode,
            ) as resolver,
        ):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon, text, chat_history=chat_history, source="telegram_surface"
            )

        self.assertEqual(
            reply,
            "Dialogue anchors now strip stale prior citations before they become current evidence.",
        )
        resolver.assert_called()

    def test_dated_web_trigger_routes_to_focused_status_not_honest_empty(self):
        from core.routing import reply_mode
        from daemon import maez_daemon

        daemon = self._build_daemon_for_handle_message()
        captured: dict[str, list[dict]] = {}
        text = "What happened on May 12?"

        with (
            self._handle_message_mock_stack(
                maez_daemon,
                captured,
                needs_web_search=True,
                web_context="",
                reply="I searched and found nothing.",
            ),
            mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
                clear=False,
            ),
            mock.patch(
                "core.routing.reply_mode.resolve_reply_mode",
                wraps=reply_mode.resolve_reply_mode,
            ) as resolver,
            mock.patch("core.routing.focused_cognition.focused_synthesize") as focused,
            mock.patch(
                "core.routing.focused_cognition.record_focused_cognition_run",
                return_value="focused-row-1",
            ),
        ):
            from core.routing.focused_cognition import FocusedResult

            focused.return_value = FocusedResult("No dated memory [E1]", ["E1"], 200)
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon, text, source="telegram_surface"
            )

        self.assertEqual(reply, "No dated memory [E1]")
        resolver.assert_called()
        self.assertTrue(
            any(
                getattr(call.args[0], "date_addressed", False)
                for call in resolver.call_args_list
            )
        )
        focused.assert_called_once()

    def test_focused_telemetry_relabels_candidate_and_logs_actual_prompt(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs(maez_daemon.logger, level="INFO") as log_capture:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
            ) as fsyn, mock.patch(
                "core.routing.focused_cognition.record_focused_cognition_run",
                return_value="focused-row-1",
            ):
                from core.routing.focused_cognition import FocusedResult

                fsyn.return_value = FocusedResult("voiced answer [E1]", ["E1"], 800)
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "Search r/LocalLLaMA",
                    source="telegram_surface",
                    transcript="[memory context] r/x:\n- a post (1 pts)",
                    chat_history=[],
                )

        joined = "\n".join(log_capture.output)
        self.assertIn("call_purpose=legacy_candidate", joined)
        self.assertIn("focused_cognition_prompt_shape", joined)
        self.assertNotIn("call_purpose=llm_synthesis", joined)

    def test_focused_links_legacy_routing_observation_id_only(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()
        web_context = (
            "[WEB SEARCH: 'local llm'] 2 results - 2026\n"
            "  1. Post\n"
            "     body"
        )

        with self._handle_message_mock_stack(
            maez_daemon,
            captured,
            needs_web_search=True,
            web_context=web_context,
        ), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.observation.record_legacy_web_search_observation",
            return_value="legacy-routing-row",
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ) as rec:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("web answer [E1]", ["E1"], 800)
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "what's the latest on local llms",
                source="telegram_surface",
                transcript="",
                chat_history=[],
            )

        self.assertEqual(
            rec.call_args.kwargs["routing_observation_id"],
            "legacy-routing-row",
        )

        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-2",
        ) as rec:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult("dispatcher answer [E1]", ["E1"], 800)
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA",
                source="telegram_surface",
                transcript="[memory context] r/x:\n- a post (1 pts)",
                chat_history=[],
            )

        self.assertIsNone(rec.call_args.kwargs["routing_observation_id"])

    def test_daemon_continuity_no_anchor_falls_back_to_legacy(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy continuity reply")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What were we talking about earlier?",
                source="telegram_surface",
                transcript="[memory evidence] stale:\n- April 6 journal",
                chat_history=[],
            )

        self.assertEqual(reply, "legacy continuity reply")
        fsyn.assert_not_called()
        megachat.assert_called_once()

    def test_daemon_uncertain_continuity_no_anchor_falls_back_to_legacy(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            megachat.return_value = types.SimpleNamespace(
                message=types.SimpleNamespace(content="legacy uncertain reply")
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Anything since we were talking?",
                source="telegram_surface",
                transcript="[memory evidence] stale:\n- April 6 journal",
                chat_history=[],
            )

        self.assertEqual(reply, "legacy uncertain reply")
        fsyn.assert_not_called()
        megachat.assert_called_once()

    def test_daemon_intra_turn_echo_with_stale_evidence_uses_echo_reply(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self.assertLogs(maez_daemon.logger, level="INFO") as log_capture:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ,
                {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
            ) as fsyn, mock.patch(
                "core.llm_client.chat",
            ) as megachat:
                reply = maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    (
                        "For the continuity witness: dialogue anchors now strip stale "
                        "prior citations before they become current evidence. Say that "
                        "back in one sentence."
                    ),
                    source="telegram_surface",
                    transcript="[memory evidence] stale:\n- April 6 journal",
                    chat_history=[
                        {
                            "content": (
                                "Rohit: earlier continuity probe\n"
                                "Maez: earlier continuity answer"
                            )
                        }
                    ],
                )

        self.assertEqual(
            reply,
            "Dialogue anchors now strip stale prior citations before they become "
            "current evidence.",
        )
        fsyn.assert_not_called()
        megachat.assert_not_called()
        self.assertIn("call_purpose=echo_reply", "\n".join(log_capture.output))

    def test_daemon_continuity_with_anchor_uses_focused(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ), mock.patch(
            "core.llm_client.chat",
        ) as megachat:
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult(
                "We were discussing Reddit [E1]",
                ["E1"],
                800,
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "What were we talking about earlier?",
                source="telegram_surface",
                transcript="[memory evidence] stale:\n- April 6 journal",
                chat_history=[
                    {
                        "content": (
                            "Rohit: Search r/LocalLLaMA\n"
                            "Maez: I found LiquidAI."
                        )
                    }
                ],
            )

        self.assertEqual(reply, "We were discussing Reddit [E1]")
        fsyn.assert_called_once()
        megachat.assert_not_called()

    def test_daemon_anaphoric_with_anchor_uses_focused(self):
        from daemon import maez_daemon

        captured: dict[str, list[dict]] = {}
        daemon = self._build_daemon_for_handle_message()

        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ,
            {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
        ), mock.patch(
            "core.routing.focused_cognition.focused_synthesize",
        ) as fsyn, mock.patch(
            "core.routing.focused_cognition.record_focused_cognition_run",
            return_value="focused-row-1",
        ):
            from core.routing.focused_cognition import FocusedResult

            fsyn.return_value = FocusedResult(
                "LiquidAI matters most [E1]",
                ["E1"],
                800,
            )
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Which one matters most?",
                source="telegram_surface",
                transcript="[fresh evidence] r/LocalLLaMA:\n- LiquidAI LFM2.5\n- Reachy Mini",
                chat_history=[
                    {
                        "content": (
                            "Rohit: Search r/LocalLLaMA\n"
                            "Maez: LiquidAI and Reachy were active."
                        )
                    }
                ],
            )

        self.assertEqual(reply, "LiquidAI matters most [E1]")
        fsyn.assert_called_once()

    def test_daemon_system_part_capture_names_consolidated_blocks(self):
        """System-block capture should identify each pre-consolidation part."""
        from daemon import maez_daemon

        parts = [
            ("sys_prompt", "SYS " + ("s" * 140)),
            ("lived_brief", "LIVED " + ("l" * 140)),
            ("ambient_block", "AMBIENT " + ("a" * 140)),
            ("transcript_context", "[fresh evidence] LIVE_REDDIT\n\ninstruction"),
        ]

        summary = maez_daemon._summarize_daemon_system_parts(parts)

        self.assertEqual(summary["system_part_count"], 4)
        self.assertEqual(
            summary["system_part_labels"],
            "sys_prompt,lived_brief,ambient_block,transcript_context",
        )
        self.assertEqual(len(summary["system_part_hashes"].split(",")), 4)
        self.assertEqual(len(summary["system_part_lengths"].split(",")), 4)
        self.assertIn("SYS ", summary["system_part_0_head"])
        self.assertIn("instruction", summary["system_part_3_tail"])
        self.assertLessEqual(len(summary["system_part_1_head"]), 100)
        self.assertLessEqual(len(summary["system_part_1_tail"]), 100)
        self.assertNotIn("l" * 120, str(summary))

        with self.assertLogs(maez_daemon.logger, level="INFO") as log_capture:
            maez_daemon._log_daemon_system_part_shape(
                surface="telegram_surface",
                call_purpose="llm_synthesis",
                system_parts=parts,
            )
        joined = "\n".join(log_capture.output)
        self.assertIn("daemon_system_part_shape", joined)
        self.assertIn("surface=telegram_surface", joined)
        self.assertIn("call_purpose=llm_synthesis", joined)
        self.assertIn(
            '"system_part_labels": "sys_prompt,lived_brief,ambient_block,transcript_context"',
            joined,
        )

    def test_zero_result_web_search_uses_honest_empty_path(self):
        """A real zero-result search is anchored without the legacy false premise."""
        from daemon import maez_daemon

        class FakeMemory:
            def recall_for_telegram(self, _text):
                return {}

            def format_for_prompt(self, _recalled, max_chars=None):
                return ""

            def store_telegram(self, *_args, **_kwargs):
                return "raw-memory-id"

        class FreshState:
            def with_freshness(self):
                return self

        captured: dict[str, list[dict]] = {}

        def fake_chat(*, model, messages, think, options):
            captured["messages"] = messages
            return types.SimpleNamespace(
                message=types.SimpleNamespace(content="I searched and found nothing.")
            )

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

        trace = types.SimpleNamespace(
            audit=types.SimpleNamespace(),
            lived_recall_ids=[],
        )

        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_LIVED_RECALL": "0",
                "MAEZ_AMBIENT_BRIEF": "0",
                "MAEZ_WORKING_SELF": "0",
                "MAEZ_WONDERING_PURSUIT": "0",
            },
            clear=False,
        ), mock.patch.object(
            maez_daemon,
            "guard_owner_text",
            return_value=types.SimpleNamespace(matched=False, answer_text=None),
        ), mock.patch.object(
            maez_daemon,
            "answer_camera_presence_question",
            return_value=None,
        ), mock.patch.object(
            maez_daemon,
            "perception_snapshot",
            return_value=object(),
        ), mock.patch.object(
            maez_daemon,
            "format_snapshot",
            return_value="SYSTEM_STATE",
        ), mock.patch.object(
            maez_daemon,
            "Trace",
            types.SimpleNamespace(start=lambda **_kwargs: trace),
        ), mock.patch.object(
            maez_daemon,
            "default_writer",
            return_value=types.SimpleNamespace(write=lambda _trace: None),
        ), mock.patch.object(
            maez_daemon,
            "_trace_hash_text",
            return_value="hash",
        ), mock.patch.object(
            maez_daemon,
            "_trace_extract_evidence_ids",
            return_value=[],
        ), mock.patch.object(
            maez_daemon,
            "build_temporal_anchor_recall_brief",
            return_value=types.SimpleNamespace(
                anchor_detected=False,
                brief_text="",
                evidence_ids=[],
            ),
        ), mock.patch(
            "core.cognition.envelope_builder.build_envelope",
            return_value=None,
        ), mock.patch(
            "core.cognition.envelope_builder.render_envelope_for_prompt",
            return_value="",
        ), mock.patch(
            "core.cognition.envelope_builder.resolve_recall_cap_chars",
            return_value=1000,
        ), mock.patch(
            "skills.web_search.needs_web_search",
            return_value=True,
        ), mock.patch(
            "skills.web_search.is_news_query",
            return_value=False,
        ), mock.patch(
            "skills.web_search.search",
            return_value={
                "query": "Search r/LocalLLaMA right now",
                "success": False,
                "results": [],
                "result_count": 0,
            },
        ), mock.patch(
            "skills.web_search.format_for_context",
            return_value="[WEB SEARCH: 'Search r/LocalLLaMA right now'] No results found.",
        ), mock.patch(
            "core.safety.audited_output.audit_assistant_text",
            side_effect=lambda text, **_kwargs: text,
        ), mock.patch(
            "core.ledger.writer.try_write_turn",
            return_value="turn-1",
        ), mock.patch(
            "core.ledger.model_reply_persistence.persist_model_reply",
            return_value=None,
        ), mock.patch(
            "core.llm_client.chat",
            side_effect=fake_chat,
        ):
            reply = maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA right now",
                source="telegram_surface",
            )

        self.assertEqual(reply, "I searched and found nothing.")
        prompt_material = "\n\n".join(
            str(message.get("content") or "") for message in captured["messages"]
        )
        self.assertIn(
            'A web_search search for "Search r/LocalLLaMA right now" '
            "returned no usable results.",
            prompt_material,
        )
        self.assertNotIn("[WEB SEARCH:", prompt_material)
        self.assertNotIn("Real search results above", prompt_material)

    def test_soul_web_search_section_matches_inline_search_reality(self):
        """Soul must not teach the stale Telegram-interceptor architecture."""
        soul = (_REPO / "config" / "soul.base.md").read_text()

        self.assertNotIn("Telegram interceptor", soul)
        self.assertNotIn("do not yet have the ability to invoke web_search", soul)
        self.assertIn("web_search.py runs inline", soul)
        self.assertIn("[WEB SEARCH: '<query>'] No results found.", soul)

    def test_authoritative_currency_tool_reply_bypasses_llm_synthesis(self):
        """A deterministic currency tool result must not be re-synthesized.

        Regression: the currency tool correctly returned
        ``300.00 EUR = 350.82 USD`` but the final LLM reply ignored it
        and answered from stale web/memory text as ``$327``. Volatile
        numeric tool output is already the grounded answer.
        """
        from daemon.maez_daemon import _authoritative_tool_reply

        reply = _authoritative_tool_reply([
            {
                "name": "convert_currency",
                "status": "ok",
                "output_summary": (
                    "300.00 EUR = 350.82 USD "
                    "(rate 1.1694, date 2026-04-29, source fx)"
                ),
                "error_summary": "",
            }
        ])

        self.assertEqual(
            reply,
            "300.00 EUR = 350.82 USD "
            "(rate 1.1694, date 2026-04-29, source fx)",
        )

    def test_authoritative_stock_quote_tool_reply_bypasses_llm_synthesis(self):
        from daemon.maez_daemon import _authoritative_tool_reply

        reply = _authoritative_tool_reply([
            {
                "name": "quote_stock",
                "status": "ok",
                "output_summary": (
                    "SRXH.US = 0.1135 USD "
                    "(as of 2026-04-29 18:03:11; source stooq)"
                ),
                "error_summary": "",
            }
        ])

        self.assertEqual(
            reply,
            "SRXH.US = 0.1135 USD "
            "(as of 2026-04-29 18:03:11; source stooq)",
        )

    def test_handle_message_uses_authoritative_tool_reply_before_llm_chat(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
                body_src = ast.get_source_segment(src, node) or ""
                self.assertIn("_authoritative_tool_reply(tool_calls)", body_src)
                i_auth = body_src.find("if _reply_decision.mode is ReplyMode.TOOL:")
                i_chat = body_src.find("_llm_client.chat(")
                self.assertGreaterEqual(i_auth, 0)
                self.assertGreaterEqual(i_chat, 0)
                self.assertLess(
                    i_auth,
                    i_chat,
                    "authoritative deterministic tool output must be "
                    "checked before LLM synthesis can override it.",
                )
                return
        self.fail("handle_message not found in maez_daemon.py")

    def test_handle_message_ordering_strip_then_audit_then_store(self):
        """2026-04-23 Commit 7b invariant: stored == audited == displayed.

        The daemon's final-text pipeline inside handle_message must be:
          1. strip_tool_call_leaks (wire-format cleanup)
          2. audit_assistant_text (semantic grounding)
          3. store_telegram (persistent record)

        If strip runs AFTER store, memory captures wire-format noise
        the owner never saw. If audit runs AFTER store, memory captures
        fabrications that got rewritten for the user.

        Ordering is asserted on function-CALL patterns (with opening
        paren) so explanatory comments that mention one of the
        function names don't fool the test into reporting a false
        ordering violation.
        """
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ClassDef)
                and node.name == "MaezDaemon"
            ):
                for sub in node.body:
                    if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and sub.name == "handle_message"):
                        body = ast.get_source_segment(src, sub) or ""
                        i_strip = body.find("strip_tool_call_leaks(")
                        i_audit = body.find("audit_assistant_text(")
                        i_store = body.find("store_telegram(")
                        self.assertGreater(i_strip, 0,
                            "handle_message must CALL "
                            "strip_tool_call_leaks() on the raw reply.")
                        self.assertGreater(i_audit, 0)
                        self.assertGreater(i_store, 0)
                        self.assertLess(i_strip, i_audit,
                            "strip_tool_call_leaks() must be called "
                            "BEFORE audit_assistant_text() so the "
                            "audit sees clean wire format.")
                        self.assertLess(i_audit, i_store,
                            "audit_assistant_text() must be called "
                            "BEFORE store_telegram() so stored == audited.")
                        return
        self.fail("MaezDaemon.handle_message not found")


class AdapterNoLongerDoubleAudits(unittest.TestCase):
    """skills/surface/maez_adapter must not import the low-level audit.

    After Commit 1 the adapter passes jarvis_transcript into
    handle_message and stops doing its own self_claim_audit call on
    the synthesis reply. The imported symbol should be gone.
    """

    def test_adapter_does_not_import_self_claim_audit(self):
        src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()
        self.assertNotIn("from core.self_claim_audit import audit",
                         src)
        self.assertNotIn("core.self_claim_audit import audit as",
                         src)

    def test_adapter_does_not_post_strip_tool_call_leaks(self):
        """2026-04-23 Commit 7b: strip_tool_call_leaks moved into
        handle_message (before audit). The adapter no longer calls it
        on the returned reply — doing so would be a no-op (already
        stripped) but would signal the contract is still ambiguous.
        Scope: the __call__ handler block, NOT the other adapter call
        sites that use strip on different surfaces (e.g. self-mod-
        dialog openers, which have their own separate flow)."""
        src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()
        # Find the __call__ method and check its body.
        import ast as _ast
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if (
                isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                and node.name == "__call__"
            ):
                body = _ast.get_source_segment(src, node) or ""
                # Look for `reply = strip_tool_call_leaks(reply)`
                # specifically — that was the duplicate post-return
                # cleanup this commit removed. Other uses of
                # strip_tool_call_leaks elsewhere in the adapter
                # (e.g. on an intermediate dialog opener) are fine.
                self.assertNotIn(
                    "reply = strip_tool_call_leaks(reply)", body,
                    "adapter __call__ must not re-strip the reply "
                    "after handle_message returns — strip runs "
                    "inside handle_message before audit.",
                )
                return
        self.fail("MaezMessageHandler.__call__ not found in maez_adapter")

    def test_adapter_passes_transcript_to_handle_message(self):
        src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()
        # Look for `transcript=jarvis_transcript` (or an obvious
        # variant) in the dispatch block. This is the new contract
        # — handle_message gets the tool-loop context so its internal
        # audit knows whether to skip the judge.
        self.assertIn("transcript=jarvis_transcript", src,
                      "adapter must pass jarvis_transcript into "
                      "handle_message so the audit sees tool context.")
        self.assertIn("recall_items=jarvis_recall_items", src,
                      "adapter must pass structured recall_items into "
                      "handle_message so focused cognition gets "
                      "budget-immune provenance.")


class WebChatAuditsBeforeStore(unittest.TestCase):
    """skills/web_interface.py's /chat handler audits before memory + trajectory."""

    def test_source_ordering_audit_before_store(self):
        src = (_REPO / "skills" / "web_interface.py").read_text()
        # Locate the specific ordering region around /chat.
        chat_def = src.find('@app.route("/chat", methods=["POST"])')
        self.assertNotEqual(chat_def, -1, "/chat endpoint not found")
        # Find the end of the /chat function by locating the next
        # @app.route decorator (or EOF) so the ordering assertion
        # doesn't accidentally scan into a different handler.
        next_route = src.find('@app.route(', chat_def + 30)
        window = src[chat_def:next_route if next_route > 0 else len(src)]
        i_audit = window.find("audit_assistant_text")
        i_store = window.find("memory.store_telegram")
        i_traj = window.find("claude_router.log_trajectory")
        self.assertGreater(i_audit, 0,
                           "/chat must call audit_assistant_text.")
        self.assertLess(i_audit, i_store,
                        "audit_assistant_text must appear BEFORE "
                        "memory.store_telegram in /chat.")
        self.assertLess(i_audit, i_traj,
                        "audit_assistant_text must appear BEFORE "
                        "claude_router.log_trajectory in /chat.")


class ProactiveOpinionIsAuditedAndTagged(unittest.TestCase):
    """_check_proactive_opinion must audit before send + store with type=proactive_opinion."""

    @staticmethod
    def _proactive_window(src: str) -> str:
        """Extract the body of _check_proactive_opinion by finding the
        next top-level (4-space indent) `def` after its declaration."""
        import re as _re
        fn_start = src.find("def _check_proactive_opinion")
        assert fn_start != -1, "_check_proactive_opinion not found"
        # Find the next same-indent method definition after this one.
        m = _re.search(r"\n    def ", src[fn_start + 30:])
        end = (fn_start + 30 + m.start()) if m else len(src)
        return src[fn_start:end]

    def test_source_has_audit_before_send(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        window = self._proactive_window(src)
        i_audit = window.find("audit_assistant_text")
        i_send = window.find("_send_telegram_notice")
        self.assertGreater(i_audit, 0,
                           "proactive must call audit_assistant_text.")
        self.assertGreater(i_send, 0,
                           "proactive must reach Telegram through "
                           "_send_telegram_notice.")
        self.assertLess(i_audit, i_send,
                        "audit_assistant_text must appear BEFORE "
                        "Telegram transport in proactive.")

    def test_source_tags_provenance(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        window = self._proactive_window(src)
        self.assertIn('"type": "proactive_opinion"', window,
                      "proactive storage must carry "
                      'type="proactive_opinion" provenance.')
        self.assertIn("source_window_count", window,
                      "proactive storage should record the size of "
                      "the memory window the summary came from.")


class DaemonRetryAuditsBeforeRescore(unittest.TestCase):
    """The daemon retry path must audit retry_content before the re-score."""

    def test_source_ordering(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        # Find the retry block — unique markers in the source.
        start = src.find('Cycle %d: retry triggered')
        self.assertNotEqual(start, -1)
        end = src.find("mem_metadata = {", start)
        self.assertNotEqual(end, -1)
        window = src[start:end]
        i_audit = window.find("audit_assistant_text")
        i_rescore = window.find("cog_score_and_classify")
        # There may be multiple cog_score_and_classify calls in the
        # retry region — we want the one AFTER audit.
        self.assertGreater(i_audit, 0,
                           "retry must audit before re-score.")
        self.assertLess(i_audit, i_rescore,
                        "audit must appear BEFORE the re-score so "
                        "the retry's score reflects the text that "
                        "will be stored.")


if __name__ == "__main__":
    unittest.main()
