"""Flag-gate coverage for the live valence organ.

Covenant: every live organ must be disableable (rails before hands). The gate is
DEFAULT-ON (absent => preserve live behavior) and uses the strict {1,true,yes,on}
parser so a footgun value like ``"0"`` genuinely DISABLES the organ.

Critical contract: when disabled, the entrypoint returns ``None``. The daemon
(daemon/maez_daemon.py:2256-2259) treats a ``None`` return as "keep the
audit_flag_buffer, do not clear" — so disabling the organ never silently drops
honesty-audit flags.

Tests pass an explicit ``log_path`` on every call so the real telemetry log is
never touched, and patch ``os.environ`` so the live process env is never mutated.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.evolution.valence_live import read_and_log_valence, valence_live_enabled

FLAG = "MAEZ_VALENCE_LIVE_ENABLED"

_KW = dict(
    audit_flags=["completion_rail"],
    open_want_count=2,
    continuity_state={"capsule_expected": False, "capsule_present": False},
    now="2026-06-13T00:00:00Z",
)


class ValenceLiveFlagGate(unittest.TestCase):
    def test_unset_returns_reading_and_writes_one_line(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            env = {k: v for k, v in __import__("os").environ.items() if k != FLAG}
            with patch.dict("os.environ", env, clear=True):
                reading = read_and_log_valence(log_path=log, **_KW)
            self.assertIsNotNone(reading)
            self.assertTrue(log.exists())
            lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            json.loads(lines[0])

    def test_zero_disables_returns_none_and_no_file_write(self):
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            with patch.dict("os.environ", {FLAG: "0"}, clear=False):
                reading = read_and_log_valence(log_path=log, **_KW)
            self.assertIsNone(reading)
            self.assertFalse(log.exists())

    def test_off_values_disable(self):
        for val in ("0", "false", "no", "off", "junk", "2", "disable"):
            with self.subTest(val=val):
                with TemporaryDirectory() as d:
                    log = Path(d) / "v.jsonl"
                    with patch.dict("os.environ", {FLAG: val}, clear=False):
                        reading = read_and_log_valence(log_path=log, **_KW)
                    self.assertIsNone(reading)
                    self.assertFalse(log.exists())

    def test_on_values_enable(self):
        for val in ("1", "true", "yes", "on", "TRUE", "  On  "):
            with self.subTest(val=val):
                with TemporaryDirectory() as d:
                    log = Path(d) / "v.jsonl"
                    with patch.dict("os.environ", {FLAG: val}, clear=False):
                        reading = read_and_log_valence(log_path=log, **_KW)
                    self.assertIsNotNone(reading)
                    self.assertTrue(log.exists())
                    lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
                    self.assertEqual(len(lines), 1)

    def test_disabled_returns_none_for_buffer_preserve_contract(self):
        # The daemon clears the audit_flag_buffer ONLY when the reading is not
        # None. A disabled organ must return None so disabling never drops
        # honesty-audit flags.
        with TemporaryDirectory() as d:
            log = Path(d) / "v.jsonl"
            with patch.dict("os.environ", {FLAG: "off"}, clear=False):
                reading = read_and_log_valence(log_path=log, **_KW)
            self.assertIsNone(reading)

    def test_enabled_truth_table_direct(self):
        cases = {
            "1": True,
            "true": True,
            "yes": True,
            "on": True,
            "TRUE": True,
            "  on ": True,
            "0": False,
            "false": False,
            "no": False,
            "off": False,
            "junk": False,
            "": True,  # absent-equivalent (explicit empty) => ON
            "  ": True,  # whitespace-only => ON (strips to empty)
        }
        for val, expected in cases.items():
            with self.subTest(val=val):
                with patch.dict("os.environ", {FLAG: val}, clear=False):
                    self.assertEqual(valence_live_enabled(), expected)

    def test_enabled_unset_is_on(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != FLAG}
        with patch.dict("os.environ", env, clear=True):
            self.assertTrue(valence_live_enabled())


if __name__ == "__main__":
    unittest.main()
