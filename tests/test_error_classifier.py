# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.error_classifier — structured taxonomy for Maez's
backend error surface.

Observational layer only — verifies classification correctness and
telemetry shape. Does not assert any _reason()-level behavior change
(the classifier doesn't alter behavior in this commit).
"""
from __future__ import annotations

import unittest

from core.error_classifier import (
    classify, emit_telemetry,
    ErrorClass, ClassifiedError,
    _diag_class_names,
)


# ── classification correctness ────────────────────────────────────────

class ClassifyTransport(unittest.TestCase):

    def test_connection_refused_is_backend_down(self):
        r = classify(ConnectionRefusedError("Connection refused"))
        self.assertEqual(r.error_class, ErrorClass.backend_down)
        self.assertTrue(r.retryable)
        self.assertTrue(r.likely_transient)

    def test_connection_error_is_backend_down(self):
        r = classify(ConnectionError("connection failed"))
        self.assertEqual(r.error_class, ErrorClass.backend_down)

    def test_timeout_error_is_backend_timeout(self):
        r = classify(TimeoutError("read timed out"))
        self.assertEqual(r.error_class, ErrorClass.backend_timeout)
        self.assertTrue(r.retryable)
        self.assertTrue(r.likely_transient)

    def test_connection_refused_string_pattern(self):
        # A generic Exception carrying a "connection refused" message
        # still gets classified correctly via pattern matching.
        r = classify(Exception("connection refused on 127.0.0.1:8080"))
        self.assertEqual(r.error_class, ErrorClass.backend_down)


class ClassifyGpu(unittest.TestCase):

    def test_cuda_oom_message(self):
        err = Exception(
            "ggml_backend_cuda_buffer_type_alloc_buffer: allocating "
            "1105.32 MiB on device 0: cudaMalloc failed: out of memory"
        )
        r = classify(err)
        self.assertEqual(r.error_class, ErrorClass.gpu_oom)
        self.assertFalse(r.retryable)
        self.assertTrue(r.likely_structural)

    def test_plain_cuda_oom(self):
        r = classify(Exception("CUDA error: out of memory"))
        self.assertEqual(r.error_class, ErrorClass.gpu_oom)


class ClassifyContext(unittest.TestCase):

    def test_max_model_len(self):
        r = classify(Exception("prompt exceeds the max_model_len of 32768"))
        self.assertEqual(r.error_class, ErrorClass.context_overflow)
        self.assertTrue(r.retryable)
        self.assertTrue(r.should_compress_prompt)

    def test_llama_cpp_slot_context(self):
        r = classify(Exception("slot context: 8192 tokens, prompt 9000 tokens"))
        self.assertEqual(r.error_class, ErrorClass.context_overflow)


class ClassifyModelMissing(unittest.TestCase):

    def test_model_not_found(self):
        r = classify(Exception("model not found: qwen99-fake"))
        self.assertEqual(r.error_class, ErrorClass.model_missing)
        self.assertFalse(r.retryable)
        self.assertTrue(r.likely_structural)


class ClassifyResponseParsing(unittest.TestCase):

    def test_json_decode_error(self):
        r = classify(Exception("Expecting value: line 1 column 1 (char 0)"))
        self.assertEqual(r.error_class, ErrorClass.response_malformed)
        self.assertFalse(r.retryable)

    def test_empty_response(self):
        r = classify(Exception("empty response from model"))
        self.assertEqual(r.error_class, ErrorClass.response_malformed)


class ClassifyUnknownFallback(unittest.TestCase):
    """Anything the classifier can't identify falls through to
    ErrorClass.unknown with retryable=True — behaviorally identical to
    the current bare `except Exception` path."""

    def test_unidentifiable_error_is_unknown(self):
        r = classify(Exception("something went wrong in a way we haven't seen"))
        self.assertEqual(r.error_class, ErrorClass.unknown)
        self.assertTrue(r.retryable)
        self.assertFalse(r.likely_structural)
        self.assertFalse(r.should_compress_prompt)

    def test_empty_exception_message_is_unknown(self):
        r = classify(Exception())
        self.assertEqual(r.error_class, ErrorClass.unknown)

    def test_custom_unrelated_exception_type(self):
        class MyCustom(Exception):
            pass
        r = classify(MyCustom("no match for anything"))
        self.assertEqual(r.error_class, ErrorClass.unknown)


# ── telemetry ─────────────────────────────────────────────────────────

class Telemetry(unittest.TestCase):

    def test_emit_writes_structured_line_to_cognition_logger(self):
        r = classify(Exception("cudaMalloc failed: out of memory"))

        with self.assertLogs("maez.cognition", level="INFO") as cm:
            emit_telemetry(r, surface="daemon_cycle")

        self.assertEqual(len(cm.records), 1)
        line = cm.records[0].getMessage()
        self.assertIn("error_classifier |", line)
        self.assertIn("surface=daemon_cycle", line)
        self.assertIn("class=gpu_oom", line)
        self.assertIn("structural=1", line)
        self.assertIn("retryable=0", line)

    def test_emit_truncates_long_messages(self):
        r = classify(Exception("x" * 1000))
        with self.assertLogs("maez.cognition", level="INFO") as cm:
            emit_telemetry(r, surface="test")
        line = cm.records[0].getMessage()
        # Full 1000 'x' must not appear — truncated to 200
        self.assertNotIn("x" * 500, line)

    def test_emit_never_raises_on_strange_input(self):
        # Empty classification result — should still log without error.
        r = ClassifiedError(error_class=ErrorClass.unknown)
        emit_telemetry(r, surface="test")  # must not raise


# ── diagnostics ───────────────────────────────────────────────────────

class Diagnostics(unittest.TestCase):

    def test_class_names_stable(self):
        names = _diag_class_names()
        # Catches accidental enum renames.
        self.assertIn("backend_down", names)
        self.assertIn("backend_timeout", names)
        self.assertIn("gpu_oom", names)
        self.assertIn("context_overflow", names)
        self.assertIn("model_missing", names)
        self.assertIn("response_malformed", names)
        self.assertIn("unknown", names)


if __name__ == "__main__":
    unittest.main()
