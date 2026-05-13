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
  4. ``maez.log`` used a plain ``FileHandler`` on the daemon's
     ``maez`` logger. Slice 3's new ``maez.envelope`` truncation
     telemetry is a CHILD of ``maez`` (not of ``maez.cognition``),
     so its records propagate up to that handler and land in
     ``logs/maez.log``. Fix: ``RotatingFileHandler`` on the daemon
     ``maez`` logger so long-running daemons don't grow it
     unbounded. ``cognition.log`` also got a rotating handler as
     hygiene for the cognition-specific records emitted directly
     by ``cognition_quality.py``, but that file is NOT the
     envelope-telemetry sink.
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
        with patch.object(eb, "_has_turns_table", return_value=True), patch.object(
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


class MaezLogRotationTests(unittest.TestCase):
    """maez.log (the daemon's primary log) must use a rotating
    handler. The maez.envelope logger is a CHILD of maez, not of
    maez.cognition — so envelope truncation telemetry propagates
    up to the daemon's `maez` handler at maez_daemon.py:290 and
    lands in maez.log, NOT cognition.log.

    Reviewer-flagged 2026-05-08: the prior commit rotated
    cognition.log, which was wrong-room — slice-3's chatty
    envelope telemetry doesn't even reach that file.
    """

    def test_daemon_maez_logger_uses_rotating_file_handler(self):
        src = Path(
            "/home/rohit/maez/daemon/maez_daemon.py"
        ).read_text()
        # Plain FileHandler attached to the `maez` logger is the
        # bug-class; the file_handler line at module scope must be
        # a RotatingFileHandler with explicit bounds.
        self.assertIn(
            "RotatingFileHandler", src,
            "daemon/maez_daemon.py must use RotatingFileHandler on "
            "the `maez` logger — the envelope propagation path "
            "lands here, plain FileHandler grows unbounded.",
        )
        self.assertIn("maxBytes=", src)
        self.assertIn("backupCount=", src)


class CognitionLogRotationTests(unittest.TestCase):
    """cognition_quality.py also rotates its own maez.cognition
    handler. NOT load-bearing for slice-3 envelope telemetry
    (envelope is a maez child, not a maez.cognition child), but
    still good hygiene because maez.cognition can be chatty under
    high-cycle load. Pinned for completeness."""

    def test_cognition_quality_uses_rotating_file_handler(self):
        src = Path(
            "/home/rohit/maez/core/cognition/cognition_quality.py"
        ).read_text()
        self.assertIn("RotatingFileHandler", src)
        self.assertIn("maxBytes=", src)
        self.assertIn("backupCount=", src)


if __name__ == "__main__":
    unittest.main()
