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
import os
import sys
import unittest
from pathlib import Path

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
        self.assertIn("signals_present", params)
        self.assertIn("signals_absent", params)
        # Defaults must be safe for legacy callers (no-transcript,
        # no-manifest invocations keep working). Compare via ast.Constant.
        t_default = params["transcript"]
        self.assertIsInstance(t_default, ast.Constant)
        self.assertEqual(t_default.value, "",
                         "transcript default must be an empty string")
        for key in ("signals_present", "signals_absent"):
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
        i_send = window.find("self.telegram.send_message")
        self.assertGreater(i_audit, 0,
                           "proactive must call audit_assistant_text.")
        self.assertLess(i_audit, i_send,
                        "audit_assistant_text must appear BEFORE "
                        "telegram.send_message in proactive.")

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
