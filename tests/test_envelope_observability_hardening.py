# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 cleanup: silent-failure + bounded-log hardening.

Closes four findings from the 12-agent post-wiring audit:

  1. ``resolve_recall_cap_chars()`` silently clamped negative values
     to 0 → produced an empty memory block with no operator signal.
     Fix: warn + return the 52_000 default on negatives or non-int.
  2. ``_populate_self_history`` swallowed ledger exceptions with no
     log → operators couldn't tell self_history population was
     failing. Fix: debug log per failure, behavior unchanged.
  3. ``recent_turns_by_kind`` lookup races / lock contention bubbled
     up as bare exceptions caught silently at the populate boundary.
     Same debug-log fix at the wrapper/caller boundary.
  4. ``cognition.log`` used a plain ``FileHandler`` — slice 3's new
     ``maez.envelope`` truncation telemetry propagates here. Fix:
     ``RotatingFileHandler`` so long-running daemons don't grow the
     log unbounded.
"""
from __future__ import annotations

import logging
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"

from core.cognition import envelope_builder as eb  # noqa: E402


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


class NegativeRecallCapEnvTests(unittest.TestCase):
    def setUp(self):
        self.cap = _LogCapture()
        self.cap.setLevel(logging.DEBUG)
        log = logging.getLogger("maez.envelope")
        log.addHandler(self.cap)
        log.setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger("maez.envelope").removeHandler(self.cap)

    def test_negative_value_returns_default_with_warning(self):
        with patch.dict(os.environ,
                        {"MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS": "-1"}):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            v = eb.resolve_recall_cap_chars()
        # Default, NOT clamped to 0.
        self.assertEqual(v, 52_000)
        # Warning emitted with the offending value visible.
        warnings = [r for r in self.cap.records
                    if r.levelno >= logging.WARNING]
        self.assertGreater(
            len(warnings), 0,
            "expected WARNING log on negative env var",
        )
        msg = " ".join(r.getMessage() for r in warnings)
        self.assertIn("-1", msg)

    def test_zero_value_passes_through(self):
        # Zero is a legitimate operator override (no recall block).
        # Don't surprise them with a default substitution.
        with patch.dict(os.environ,
                        {"MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS": "0"}):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            v = eb.resolve_recall_cap_chars()
        self.assertEqual(v, 0)

    def test_positive_value_unchanged(self):
        with patch.dict(os.environ,
                        {"MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS": "12345"}):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            v = eb.resolve_recall_cap_chars()
        self.assertEqual(v, 12_345)

    def test_non_int_still_warns_and_defaults(self):
        with patch.dict(os.environ,
                        {"MAEZ_RECALL_CAP_WITH_ENVELOPE_CHARS": "abc"}):
            os.environ.pop("MAEZ_EVIDENCE_ENVELOPE_DISABLED", None)
            v = eb.resolve_recall_cap_chars()
        self.assertEqual(v, 52_000)
        self.assertGreater(
            len([r for r in self.cap.records
                 if r.levelno >= logging.WARNING]),
            0,
        )


class SelfHistoryPopulationLoggingTests(unittest.TestCase):
    """Failures inside _populate_self_history (ledger lookup raises,
    DB locked, schema drift) MUST produce an operator-visible debug
    log. Behavior unchanged: still returns []."""

    def setUp(self):
        self.cap = _LogCapture()
        self.cap.setLevel(logging.DEBUG)
        log = logging.getLogger("maez.envelope")
        log.addHandler(self.cap)
        log.setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger("maez.envelope").removeHandler(self.cap)

    def test_lookup_failure_logs_debug(self):
        # Force the recent-turns lookup to raise.
        with patch.object(
            eb._rt, "recent_turns_by_kind",
            side_effect=RuntimeError("simulated DB lock"),
        ):
            builder = eb.BoundedEnvelopeBuilder()
            result = builder._populate_self_history(
                "/tmp/never_exists.db",
                limit=5, tenant_id="owner",
            )
        # Behavior unchanged: empty list, no exception.
        self.assertEqual(result, [])
        # Operator signal emitted at debug level.
        debug_records = [r for r in self.cap.records
                         if r.levelno == logging.DEBUG]
        self.assertGreater(
            len(debug_records), 0,
            "expected DEBUG log on self_history population failure",
        )
        msg = " ".join(r.getMessage() for r in debug_records)
        self.assertIn("self_history", msg)
        self.assertIn("simulated DB lock", msg)

    def test_no_log_on_clean_no_db(self):
        # When ledger_db_path=None, populator returns [] without
        # error — should NOT spam the log.
        builder = eb.BoundedEnvelopeBuilder()
        before = len(self.cap.records)
        result = builder._populate_self_history(
            None, limit=5, tenant_id="owner",
        )
        self.assertEqual(result, [])
        # No new log records.
        self.assertEqual(len(self.cap.records), before)


class CognitionLogRotationTests(unittest.TestCase):
    """cognition.log must use RotatingFileHandler so long-running
    daemons + slice-3's chatty maez.envelope truncation telemetry
    don't grow the file unbounded. Source-checked rather than
    behavior-tested because triggering a real rotation requires
    writing megabytes of log content."""

    def test_cognition_quality_uses_rotating_file_handler(self):
        src = Path(
            "/home/rohit/maez/core/cognition/cognition_quality.py"
        ).read_text()
        # Plain FileHandler usage in handler-attachment context is
        # the bug-class; RotatingFileHandler is the fix.
        self.assertIn(
            "RotatingFileHandler", src,
            "cognition_quality.py must use RotatingFileHandler "
            "(slice-3 envelope telemetry propagates here; plain "
            "FileHandler grows unbounded)",
        )
        # Belt + suspenders: bounds must be set non-trivially. Look
        # for maxBytes= and backupCount= as required kwargs.
        self.assertIn("maxBytes=", src)
        self.assertIn("backupCount=", src)


if __name__ == "__main__":
    unittest.main()
