# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice-1 trace emission contract tests (Trace harness, ADR pending).

What this pins:

- The trace schema serializes deterministically to JSONL; every field
  named in `docs/handoffs/2026-04-28.md` Slice 1 is preserved.
- The writer is daily-bucketed, append-only, thread-safe, and
  **never raises** on caller path — synthesis must not break when
  tracing fails.
- ``extract_evidence_ids`` recovers the ``ep-…`` / ``core-…`` /
  ``followup-doc:…`` ids from a real lived-recall brief format.
- The daemon source imports the trace primitives + emits a trace at
  the end of ``handle_message`` (source-level wiring check, mirroring
  the Phase 6 wiring tests' style — full ``handle_message`` is too
  heavy to mock end-to-end without becoming brittle).
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DAEMON_SRC = (_REPO / "daemon" / "maez_daemon.py").read_text()


class SchemaShape(unittest.TestCase):
    def test_new_trace_id_is_unique_and_hex(self):
        from core.turn_traces.trace_schema import new_trace_id

        a = new_trace_id()
        b = new_trace_id()
        self.assertNotEqual(a, b)
        self.assertEqual(len(a), 24)
        int(a, 16)  # raises if not hex

    def test_trace_start_populates_required_fields(self):
        from core.turn_traces.trace_schema import Trace

        t = Trace.start(surface="UI", user_text="hi")
        self.assertTrue(t.trace_id)
        self.assertTrue(t.created_at)
        self.assertEqual(t.surface, "UI")
        self.assertEqual(t.user_text, "hi")
        # Defaults preserved.
        self.assertEqual(t.tool_calls, [])
        self.assertEqual(t.memory_ids, [])
        self.assertEqual(t.lived_recall_ids, [])
        self.assertFalse(t.audit.ran)

    def test_trace_caps_user_text_to_2k(self):
        from core.turn_traces.trace_schema import Trace

        t = Trace.start(surface="UI", user_text="x" * 5000)
        self.assertLessEqual(len(t.user_text), 2000)

    def test_trace_to_jsonl_round_trips(self):
        from core.turn_traces.trace_schema import (
            AuditInfo,
            ToolCall,
            Trace,
            hash_text,
        )

        t = Trace.start(surface="UI", user_text="hi")
        t.memory_ids = ["core-abc", "raw-1"]
        t.lived_recall_ids = ["ep-deadbeef"]
        t.tool_calls = [ToolCall(name="run_shell", status="ok", elapsed_ms=12)]
        t.audit = AuditInfo(ran=True, changed_output=False)
        t.final_text_hash = hash_text("hello")
        t.sent_text_hash = t.final_text_hash
        t.stored_text_hash = t.final_text_hash
        t.latency_ms = 250
        t.terminal_state = "replied"

        line = t.to_jsonl_line()
        self.assertIsInstance(line, str)
        self.assertNotIn("\n", line)  # one trace per line is invariant
        parsed = json.loads(line)
        # Every field the harness will read must round-trip.
        for key in (
            "trace_id", "created_at", "surface", "user_text", "memory_ids",
            "lived_recall_ids", "tool_calls", "audit",
            "final_text_hash", "sent_text_hash", "stored_text_hash",
            "latency_ms", "terminal_state",
        ):
            self.assertIn(key, parsed, f"missing field: {key}")
        self.assertEqual(parsed["tool_calls"][0]["name"], "run_shell")
        self.assertTrue(parsed["audit"]["ran"])
        self.assertFalse(parsed["audit"]["changed_output"])

    def test_hash_text_stable_and_short(self):
        from core.turn_traces.trace_schema import hash_text

        h1 = hash_text("the same string")
        h2 = hash_text("the same string")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)
        self.assertEqual(hash_text(""), "")

    def test_audit_changed_output_drives_invariant_check(self):
        """If pre-audit and post-audit hashes differ, the trace lets a
        future harness flag it. This is the audit-before-store
        invariant made inspectable."""
        from core.turn_traces.trace_schema import hash_text

        pre = hash_text("model raw output")
        post = hash_text("model raw output")  # audit was a no-op
        self.assertEqual(pre, post)  # invariant held

        post_modified = hash_text("audit rewrote this")
        self.assertNotEqual(pre, post_modified)  # invariant violated


class EvidenceIdExtraction(unittest.TestCase):
    """The lived-recall brief is a string; the trace captures the
    evidence ids it carries so a harness can verify the model cited
    what was surfaced. Format matches what
    `core.memory.lived_recall.build_lived_recall_brief` actually emits
    in production."""

    def test_extracts_episode_and_core_ids(self):
        from core.turn_traces.trace_schema import extract_evidence_ids

        brief = (
            "=== LIVED RECALL — EVIDENCE-BACKED ===\n"
            "- Past episode: OWNER PREFERENCE [ep:ep-3ad13029d805 | sources: core-da33999b1f7c]\n"
            "- Current graph belief: Rohit — cares_about → truthful continuity "
            "[episodes: ep-480ddf379c4d | sources: core-58cff6923914]\n"
        )
        ids = extract_evidence_ids(brief)
        self.assertIn("ep-3ad13029d805", ids)
        self.assertIn("ep-480ddf379c4d", ids)
        self.assertIn("core-da33999b1f7c", ids)
        self.assertIn("core-58cff6923914", ids)

    def test_extracts_followup_doc_ids(self):
        from core.turn_traces.trace_schema import extract_evidence_ids

        brief = (
            "- Open loop: (project ledger) Temperament parameter review "
            "[ep:ep-2d1b18752631 | sources: followup-doc:docs/followups/temperament_parameter_review.md]"
        )
        ids = extract_evidence_ids(brief)
        self.assertIn("ep-2d1b18752631", ids)
        self.assertIn("followup-doc:docs/followups/temperament_parameter_review.md", ids)

    def test_dedups_in_order(self):
        from core.turn_traces.trace_schema import extract_evidence_ids

        # Production ids are hex (e.g. ep-3ad13029d805); use realistic
        # shapes here so the test exercises the same regex callers see.
        brief = "ep-aaa ep-bbb ep-aaa core-1cf42b912b86 ep-bbb"
        self.assertEqual(
            extract_evidence_ids(brief),
            ["ep-aaa", "ep-bbb", "core-1cf42b912b86"],
        )

    def test_empty_or_none_returns_empty(self):
        from core.turn_traces.trace_schema import extract_evidence_ids

        self.assertEqual(extract_evidence_ids(""), [])
        self.assertEqual(extract_evidence_ids(None), [])


class WriterContract(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_trace(self, **overrides):
        from core.turn_traces.trace_schema import Trace, hash_text

        t = Trace.start(surface=overrides.get("surface", "UI"), user_text="hi")
        t.final_text_hash = t.sent_text_hash = t.stored_text_hash = hash_text("ok")
        t.terminal_state = overrides.get("terminal_state", "replied")
        return t

    def test_writes_one_jsonl_line_per_trace(self):
        from core.turn_traces.trace_writer import TraceWriter

        w = TraceWriter(self.tmp_path)
        self.assertTrue(w.write(self._make_trace()))
        self.assertTrue(w.write(self._make_trace()))

        files = list(self.tmp_path.glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        lines = files[0].read_text().splitlines()
        self.assertEqual(len(lines), 2)
        for ln in lines:
            json.loads(ln)  # raises if any line is malformed

    def test_writer_creates_parent_dir_lazily(self):
        from core.turn_traces.trace_writer import TraceWriter

        deep = self.tmp_path / "deep" / "nested" / "traces"
        self.assertFalse(deep.exists())
        w = TraceWriter(deep)
        self.assertTrue(w.write(self._make_trace()))
        self.assertTrue(deep.exists())

    def test_writer_never_raises_on_filesystem_error(self):
        from core.turn_traces.trace_writer import TraceWriter

        # Point at a path that cannot be created (a file standing in
        # for the parent directory).
        blocker = self.tmp_path / "blocker"
        blocker.write_text("not a directory")
        bad_dir = blocker / "subdir"
        w = TraceWriter(bad_dir)
        # Must return False, must NOT raise.
        result = w.write(self._make_trace())
        self.assertFalse(result)

    def test_writer_never_raises_on_serialization_error(self):
        from core.turn_traces.trace_writer import TraceWriter

        w = TraceWriter(self.tmp_path)

        class _Unserializable:
            """A dict carrying this becomes non-JSON-serializable."""

        # Pass a dict directly so the writer's json.dumps fallback
        # handles it. Must return False, must NOT raise.
        result = w.write({"trace_id": "x", "bad": _Unserializable()})
        self.assertFalse(result)

    def test_writer_thread_safe(self):
        from core.turn_traces.trace_writer import TraceWriter

        w = TraceWriter(self.tmp_path)

        def _spam():
            for _ in range(20):
                w.write(self._make_trace())

        threads = [threading.Thread(target=_spam) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        files = list(self.tmp_path.glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        lines = files[0].read_text().splitlines()
        # 4 threads × 20 writes = 80 lines, all parseable.
        self.assertEqual(len(lines), 80)
        for ln in lines:
            json.loads(ln)


class DaemonImportsTraceModule(unittest.TestCase):
    """Source-level wiring check — same style as Phase 6's
    `tests/test_lived_recall_prompting.py`. Mocking the full
    `handle_message` is heavy and brittle; what we want to lock is the
    structural shape: the trace primitives are imported, a trace is
    started at handle_message entry, and `default_writer().write(...)`
    is called before the function returns."""

    def test_imports_trace_primitives(self):
        self.assertIn(
            "from core.turn_traces import",
            _DAEMON_SRC,
            "daemon must import the trace primitives",
        )
        for name in ("Trace", "AuditInfo", "ToolCall"):
            self.assertIn(
                name,
                _DAEMON_SRC,
                f"daemon import line missing {name!r}",
            )

    def test_imports_default_writer(self):
        self.assertIn("default_writer", _DAEMON_SRC)

    def test_starts_trace_in_handle_message(self):
        # Trace.start(...) must appear inside handle_message. We pin
        # this by requiring the literal `Trace.start(` after the
        # `def handle_message` line.
        idx_def = _DAEMON_SRC.find("def handle_message(")
        self.assertGreater(idx_def, 0)
        idx_start = _DAEMON_SRC.find("Trace.start(", idx_def)
        self.assertGreater(
            idx_start, 0,
            "Trace.start(...) must be called inside handle_message",
        )

    def test_writes_trace_before_return(self):
        # The default_writer().write(...) call must appear before the
        # `return reply` at the bottom of handle_message. Locate the
        # final `return reply` (audited reply path) and check that
        # `.write(` appears between handle_message's def and that
        # return.
        idx_def = _DAEMON_SRC.find("def handle_message(")
        # The audited-output return is `return reply` at the end.
        idx_return = _DAEMON_SRC.find("return reply", idx_def)
        self.assertGreater(idx_return, 0)
        idx_write = _DAEMON_SRC.rfind(".write(", idx_def, idx_return)
        self.assertGreater(
            idx_write, 0,
            "trace writer .write(...) must be called before return",
        )


class HandleMessageNeverBreaksOnTraceFailure(unittest.TestCase):
    """A failing TraceWriter must NOT propagate. The simplest proof is
    to import the writer and call it with a clearly-broken target, then
    assert no exception escapes. The daemon's call site is wrapped in
    try/except per the slice contract; this test checks the writer's
    own failure-mode contract end-to-end."""

    def test_write_failure_does_not_propagate(self):
        from core.turn_traces.trace_writer import TraceWriter
        from core.turn_traces.trace_schema import Trace, hash_text

        # A path under a regular file → mkdir will fail → write returns
        # False. The test asserts no exception leaks regardless.
        with tempfile.NamedTemporaryFile() as f:
            bad_dir = Path(f.name) / "cannot_be_a_dir"
            w = TraceWriter(bad_dir)
            t = Trace.start(surface="UI", user_text="hi")
            t.final_text_hash = hash_text("ok")
            t.terminal_state = "replied"
            try:
                ok = w.write(t)
            except Exception as e:
                self.fail(f"writer must not raise; got {e!r}")
            self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
