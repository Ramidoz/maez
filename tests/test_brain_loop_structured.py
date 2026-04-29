# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 3 — structured tool-call plumbing from run_brain_loop.

Pins:

- ``run_brain_loop(...)`` returns a ``str`` by default (every existing
  caller keeps working).
- ``run_brain_loop(..., return_structured=True)`` returns a
  :class:`BrainLoopResult` with ``transcript: str`` and
  ``tool_calls: list[dict]``.
- The transcript→tool_call mapping covers all four ``ok`` states
  (True / False / "pending" / REFUSED-marker) and the dict shape
  matches ``core.turn_traces.ToolCall``.
- ``maez_adapter`` calls the structured API and forwards tool_calls
  into ``daemon.handle_message`` (source-level wiring check).
- ``/internal/brain_loop`` returns both ``transcript`` and
  ``tool_calls`` keys; legacy ``transcript`` consumers unaffected.
- The trace harness's ``check_nonterminating_tool`` flags a real
  ``BrainLoopResult.tool_calls`` payload.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class NoToolPromptContract(unittest.TestCase):
    """The synthesis prompt must distinguish "no tool ran this turn"
    from "this channel has no tool access."
    """

    def test_no_tool_prompt_forbids_tool_access_self_denial(self):
        from core.brain.brain_loop import build_synthesis_user_text

        folded = build_synthesis_user_text(
            "Create ui/maez_pulse.html",
            jarvis_transcript="",
        )
        self.assertIn("no tools ran this turn", folded.lower())
        self.assertIn("does not mean this surface lacks tools", folded)
        self.assertIn("I don't have a tool loop on this channel", folded)
        self.assertIn("I haven't made that change yet", folded)
        self.assertIn("Do not paste code", folded)


class ToolPlannerManifestContract(unittest.TestCase):
    """Explicit file-creation asks must route to Maez's own write tool,
    not prose or manual-save code dumps."""

    def test_manifest_contains_direct_file_write_rule(self):
        src = (_REPO / "core" / "brain" / "brain_loop.py").read_text()
        self.assertIn("DIRECT-FILE-WRITE RULE", src)
        self.assertIn("write_any_file", src)
        self.assertIn("Do NOT answer with code for", src)
        self.assertIn("prose without write_any_file is not action", src)

    def test_manifest_allows_fetch_url_for_live_numeric_facts(self):
        src = (_REPO / "core" / "brain" / "brain_loop.py").read_text()
        self.assertIn("fetch_url", src)
        self.assertIn("'fetch_url'", src)
        self.assertIn("Volatile numeric facts", src)
        self.assertIn("exchange rates", src)
        self.assertIn("currency conversions", src)
        self.assertIn("require live evidence", src)
        self.assertIn("do NOT answer from\n  training memory", src)

    def test_manifest_contains_endpoint_discovery_rule(self):
        src = (_REPO / "core" / "brain" / "brain_loop.py").read_text()
        self.assertIn("LOCAL-ENDPOINT DISCOVERY RULE", src)
        self.assertIn("do\nnot guess the port", src)
        self.assertIn("inspect\nthe route definitions", src)
        self.assertIn("active listeners", src)
        self.assertIn("prefer a same-origin relative fetch", src)
        self.assertIn("hardcoded localhost ports", src)
        self.assertIn("pivot to route\ndiscovery", src)
        self.assertNotIn("LOCAL SERVICE MAP", src)
        self.assertNotIn("maez-web Flask/cockpit backend: http://127.0.0.1:11437", src)
        self.assertNotIn("GPU stats endpoint: http://127.0.0.1:11437/api/v1/gpu", src)


class StatusClassification(unittest.TestCase):
    """Status mapping is the contract a future trace harness will
    grade against; lock it in tests so a quiet refactor can't change
    the vocabulary on us."""

    def test_ok_maps_to_ok(self):
        from core.brain.brain_loop import _classify_transcript_status
        self.assertEqual(_classify_transcript_status("any output", True), "ok")

    def test_pending_marker_maps_to_pending(self):
        from core.brain.brain_loop import _classify_transcript_status
        self.assertEqual(
            _classify_transcript_status("CARD_CREATED — NOT YET EXECUTED", "pending"),
            "pending",
        )

    def test_refused_maps_to_denied(self):
        from core.brain.brain_loop import _classify_transcript_status
        self.assertEqual(
            _classify_transcript_status(
                "REFUSED: 'rm_rf' is not in the chat-loop allowlist.",
                False,
            ),
            "denied",
        )

    def test_already_ran_maps_to_error(self):
        from core.brain.brain_loop import _classify_transcript_status
        self.assertEqual(
            _classify_transcript_status("ALREADY_RAN: dedup fired", False),
            "error",
        )

    def test_runtime_error_maps_to_error(self):
        from core.brain.brain_loop import _classify_transcript_status
        self.assertEqual(
            _classify_transcript_status("ERROR: command not found", False),
            "error",
        )

    def test_parse_error_maps_to_error(self):
        from core.brain.brain_loop import _classify_transcript_status
        self.assertEqual(
            _classify_transcript_status("PARSE_ERROR: bad JSON", False),
            "error",
        )


class TranscriptTupleConversion(unittest.TestCase):
    """The schema expected by ``core.turn_traces.ToolCall``: name,
    args_summary, status, elapsed_ms, output_summary, error_summary."""

    def test_ok_tuple_carries_output_not_error(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        d = _transcript_to_tool_call_dict(
            ("run_shell", {"cmd": "ls /tmp"}, "file1\nfile2", True)
        )
        self.assertEqual(d["name"], "run_shell")
        self.assertEqual(d["status"], "ok")
        self.assertIn("ls /tmp", d["args_summary"])
        self.assertEqual(d["output_summary"], "file1\nfile2")
        self.assertEqual(d["error_summary"], "")
        self.assertEqual(d["elapsed_ms"], 0)

    def test_error_tuple_carries_error_not_output(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        d = _transcript_to_tool_call_dict(
            ("run_shell", {"cmd": "false"}, "ERROR: exit 1", False)
        )
        self.assertEqual(d["status"], "error")
        self.assertEqual(d["output_summary"], "")
        self.assertEqual(d["error_summary"], "ERROR: exit 1")

    def test_pending_tuple_marks_status(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        d = _transcript_to_tool_call_dict(
            ("write_any_file", {"path": "/etc/hosts"}, "CARD_CREATED", "pending")
        )
        self.assertEqual(d["status"], "pending")

    def test_refused_tuple_marks_denied(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        d = _transcript_to_tool_call_dict(
            ("rm_rf", {"path": "/"}, "REFUSED: not in allowlist", False)
        )
        self.assertEqual(d["status"], "denied")

    def test_args_summary_truncates_to_200(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        big = {"cmd": "x" * 1000}
        d = _transcript_to_tool_call_dict(("run_shell", big, "ok", True))
        self.assertLessEqual(len(d["args_summary"]), 200)

    def test_malformed_tuple_returns_placeholder_not_raises(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        # Wrong arity — must not raise.
        d = _transcript_to_tool_call_dict(("incomplete", "tuple"))
        self.assertEqual(d["name"], "?")
        self.assertEqual(d["status"], "error")
        self.assertIn("malformed", d["error_summary"].lower())


class RunBrainLoopBackwardsCompat(unittest.TestCase):
    """The legacy callers (telegram_voice _run_jarvis_loop wrappers,
    older surfaces) take the return value as ``str``. Default kwarg
    behavior must not change. Ever."""

    def test_no_action_engine_returns_empty_string(self):
        from core.brain.brain_loop import run_brain_loop

        result = run_brain_loop(
            "hi",
            action_engine=None,
            get_pipeline=None,
        )
        self.assertEqual(result, "")
        self.assertIsInstance(result, str)

    def test_no_action_engine_structured_returns_empty_result(self):
        from core.brain.brain_loop import BrainLoopResult, run_brain_loop

        result = run_brain_loop(
            "hi",
            action_engine=None,
            get_pipeline=None,
            return_structured=True,
        )
        self.assertIsInstance(result, BrainLoopResult)
        self.assertEqual(result.transcript, "")
        self.assertEqual(result.tool_calls, [])

    def test_conversational_text_returns_empty_string(self):
        """Pure greetings short-circuit; default API is still str."""
        from core.brain.brain_loop import run_brain_loop

        # action_engine truthy but message bypasses the loop.
        result = run_brain_loop(
            "hi",
            action_engine=object(),
            get_pipeline=lambda *a, **kw: None,
        )
        self.assertEqual(result, "")

    def test_conversational_text_structured_returns_empty_result(self):
        from core.brain.brain_loop import BrainLoopResult, run_brain_loop

        result = run_brain_loop(
            "hi",
            action_engine=object(),
            get_pipeline=lambda *a, **kw: None,
            return_structured=True,
        )
        self.assertIsInstance(result, BrainLoopResult)
        self.assertEqual(result.tool_calls, [])


class StructuredResultIsBuiltFromTranscript(unittest.TestCase):
    """The mapping from transcript tuples to tool_call dicts is what
    actually unlocks the trace-harness signal. Drive
    `_transcript_to_tool_call_dict` over a list of representative
    transcript shapes and confirm the dicts are well-formed."""

    def test_full_transcript_maps_one_to_one(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict

        synth_transcript = [
            ("run_shell", {"cmd": "ls"}, "file1", True),
            ("run_shell", {"cmd": "false"}, "ERROR: exit 1", False),
            ("write_any_file", {"path": "/x"}, "CARD_CREATED", "pending"),
            ("rm_rf", {"path": "/"}, "REFUSED: not in allowlist", False),
        ]
        dicts = [_transcript_to_tool_call_dict(t) for t in synth_transcript]
        statuses = [d["status"] for d in dicts]
        self.assertEqual(statuses, ["ok", "error", "pending", "denied"])
        for d in dicts:
            for key in (
                "name", "args_summary", "status", "elapsed_ms",
                "output_summary", "error_summary",
            ):
                self.assertIn(key, d, f"missing {key}")


class MaezAdapterWiring(unittest.TestCase):
    """Source-level wiring check: the adapter requests the structured
    result and forwards tool_calls into handle_message. Mocking the
    full async adapter pipeline is heavy and brittle; locking the
    surface shape catches the regression class we actually care
    about."""

    def setUp(self):
        self.src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()

    def test_adapter_requests_structured_result(self):
        self.assertIn("return_structured=True", self.src)

    def test_adapter_extracts_tool_calls_from_result(self):
        # The adapter must read tool_calls off the structured result
        # (via attribute access OR `getattr(..., "tool_calls", ...)`)
        # — NOT parse the transcript string for tool data.
        self.assertIn("tool_calls", self.src)
        self.assertTrue(
            ".tool_calls" in self.src or 'getattr(_result, "tool_calls"' in self.src,
            "adapter must read tool_calls from the structured result",
        )

    def test_adapter_passes_tool_calls_to_handle_message(self):
        # Sandwich check: somewhere the adapter calls handle_message
        # with tool_calls=... — pin that the kwarg appears in the
        # right region.
        idx_handle = self.src.find("self.daemon.handle_message(")
        self.assertGreater(idx_handle, 0)
        # The keyword should appear within a reasonable region after
        # the call site.
        region = self.src[idx_handle:idx_handle + 1200]
        self.assertIn("tool_calls=", region)


class InternalBrainLoopEndpoint(unittest.TestCase):
    """Source-level wiring: /internal/brain_loop returns both the
    legacy ``transcript`` and the new ``tool_calls`` JSON keys.
    Backward compatible — old web callers reading ``transcript`` keep
    working."""

    def test_endpoint_returns_transcript_and_tool_calls(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        idx_route = src.find("/internal/brain_loop")
        self.assertGreater(idx_route, 0)
        # The handler region is small; pin both keys appear after the
        # route definition.
        region = src[idx_route:idx_route + 4000]
        self.assertIn('"transcript":', region)
        self.assertIn('"tool_calls":', region)
        # And the structured request flag.
        self.assertIn("return_structured=True", region)


class TraceHarnessGradesRealToolCalls(unittest.TestCase):
    """End-to-end fixture — the structured tool_calls produced by
    Slice 3 are graded by the Slice 2 deterministic harness. A
    nonterminating command with status='ok' is the canonical FAIL
    signal."""

    def test_nonterminating_payload_is_flagged_by_harness(self):
        from core.brain.brain_loop import _transcript_to_tool_call_dict
        from scripts.validate.trace_harness import check_nonterminating_tool

        # Simulated transcript where the model proposed `nvidia-smi -l`
        # and (in this hypothetical bug) the gate let it through.
        transcript = [("run_shell", {"cmd": "nvidia-smi -l 1"}, "still running...", True)]
        tool_calls = [_transcript_to_tool_call_dict(t) for t in transcript]
        trace = {
            "trace_id": "tr-fixture-1",
            "tool_calls": tool_calls,
        }
        findings = check_nonterminating_tool(trace, file="x", line=1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "FAIL")
        self.assertIn("nvidia-smi", findings[0].matched_value)

    def test_denied_status_is_a_pass(self):
        """Same command but the covenant gate refused it — that's the
        gate working, not a failure."""
        from core.brain.brain_loop import _transcript_to_tool_call_dict
        from scripts.validate.trace_harness import check_nonterminating_tool

        transcript = [(
            "run_shell",
            {"cmd": "nvidia-smi -l 1"},
            "REFUSED: 'run_shell' rejected by covenant gate",
            False,
        )]
        tool_calls = [_transcript_to_tool_call_dict(t) for t in transcript]
        # Sanity: status mapping → 'denied'.
        self.assertEqual(tool_calls[0]["status"], "denied")
        trace = {"trace_id": "tr-fixture-2", "tool_calls": tool_calls}
        findings = check_nonterminating_tool(trace, file="x", line=1)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
