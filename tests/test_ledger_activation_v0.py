"""Ledger Activation / Disabled-State Honesty v0.

One switch (MAEZ_LEDGER_WRITES) says "writing is allowed"; a strict schema check
says "the notebook is real"; the disabled path opens no SQLite at all.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class LedgerWritesEnabled(unittest.TestCase):
    def _enabled(self, value):
        env = {} if value is None else {"MAEZ_LEDGER_WRITES": value}
        with mock.patch.dict(os.environ, env, clear=False):
            if value is None:
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
            from core.ledger.writes_flag import ledger_writes_enabled
            return ledger_writes_enabled()

    def test_true_values_enable(self):
        for v in ("1", "true", "TRUE", " true "):
            self.assertTrue(self._enabled(v), v)

    def test_false_and_unset_disable(self):
        for v in (None, "", "0", "false", "no", "off"):
            self.assertFalse(self._enabled(v), repr(v))

    def test_unrecognized_disables_with_warning(self):
        from core.ledger import writes_flag
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "yarp"}):
            with self.assertLogs("core.ledger.writes_flag", level="WARNING") as logs:
                self.assertFalse(writes_flag.ledger_writes_enabled())
        self.assertIn("unrecognized", "\n".join(logs.output).lower())


if __name__ == "__main__":
    unittest.main()
