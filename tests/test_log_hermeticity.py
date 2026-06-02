# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests must not write to the production logs/maez.log (test-hermeticity v0).

The daemon attaches a RotatingFileHandler to logs/maez.log at module import.
Under the test harness (MAEZ_DISABLE_FILE_LOG=1, set in tests/__init__.py) that
handler must be skipped so test runs cannot pollute Maez's live diary.
"""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class MaezLogHermeticityTest(unittest.TestCase):
    def test_maez_logger_has_no_prod_file_handler_in_test_mode(self):
        """Mechanism: the maez logger has no handler pointed at the prod log path."""
        import daemon.maez_daemon as md

        prod = os.path.abspath(str(md.LOG_PATH))
        maez_logger = logging.getLogger("maez")
        offenders = [
            h for h in maez_logger.handlers
            if os.path.abspath(getattr(h, "baseFilename", "") or "") == prod
        ]
        self.assertEqual(
            offenders, [],
            f"maez logger must not have a handler writing to {prod} under test mode",
        )

    def test_reflection_hook_emits_records_without_file_handler(self):
        """Outcome (daemon-immune): the hook emits log records, but the maez logger
        has no FileHandler — so those records have no file destination and cannot
        reach logs/maez.log. Stronger than a (flaky, daemon-contended) file snapshot."""
        import daemon.maez_daemon as md
        from tests.test_reflection_dry_run_wiring import _FakeEpisodeStore

        maez_logger = logging.getLogger("maez")

        file_handlers_before = [h for h in maez_logger.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(
            file_handlers_before, [],
            "no FileHandler may be attached to the maez logger in test mode",
        )

        # Fake brain call carrying terminal metadata: no real llama-server, no durable write.
        def _fake_llm(_prompt):
            _fake_llm.last_finish_reason = "stop"
            _fake_llm.max_tokens = 8192
            _fake_llm.last_raw_content = "[]"
            return "[]"

        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(record)

        cap = _Cap()
        maez_logger.addHandler(cap)
        try:
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
                os.environ, {"MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1"}, clear=False
            ):
                md._run_reflection_synthesis_nightly(
                    SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
                    llm_call=_fake_llm,
                    artifact_dir=Path(tmp),
                )
        finally:
            maez_logger.removeHandler(cap)

        self.assertTrue(captured, "the reflection hook should have emitted log records (sanity)")
        file_handlers_after = [h for h in maez_logger.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(
            file_handlers_after, [],
            "driving the hook must not attach a FileHandler / give records a file route",
        )


if __name__ == "__main__":
    unittest.main()
