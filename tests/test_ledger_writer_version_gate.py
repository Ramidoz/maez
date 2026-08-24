# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""An ENABLED LedgerWriter must refuse to construct on a SQLite inside the
WAL-reset corruption window (< 3.51.3, `sqlite_runtime.require_fixed`).

Reporting the linked version at boot is not the same as refusing to run on
a vulnerable one. The gate is deliberately scoped to ENABLED writers so the
unborn / flag-dormant state is unchanged: a disabled writer constructs (and
no-ops) exactly as before, on any SQLite.

Each case runs in a subprocess so the linked SQLite is controlled by the
presence/absence of LD_LIBRARY_PATH=vendor/sqlite/lib, matching how the
systemd units versus a bare shell actually launch Maez processes.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_VENDOR_LIB = _REPO / "vendor" / "sqlite" / "lib"

_PROBE = r"""
import sqlite3, sys
sys.path.insert(0, sys.argv[1])
from core.infra.sqlite_runtime import has_wal_reset_fix
from core.ledger.writer import LedgerWriter
print("SQLITE", sqlite3.sqlite_version)
print("FIXED", has_wal_reset_fix())
try:
    w = LedgerWriter(sys.argv[2])
    print("CONSTRUCTED")
    w.close()
except RuntimeError as e:
    print("REFUSED", e)
"""


def _run_probe(*, vendored: bool, writes_flag: str | None) -> str:
    env = {k: v for k, v in os.environ.items()
           if k not in ("LD_LIBRARY_PATH", "MAEZ_LEDGER_WRITES")}
    env["MAEZ_TEST_MODE"] = "1"
    if vendored:
        env["LD_LIBRARY_PATH"] = str(_VENDOR_LIB)
    if writes_flag is not None:
        env["MAEZ_LEDGER_WRITES"] = writes_flag
    with tempfile.TemporaryDirectory(prefix="maez_test_version_gate_") as d:
        db = str(Path(d) / "gate.db")
        proc = subprocess.run(
            [sys.executable, "-c", _PROBE, str(_REPO), db],
            capture_output=True, text=True, timeout=60, env=env,
        )
    if proc.returncode != 0:
        raise AssertionError(
            f"probe subprocess failed:\n{proc.stdout}\n{proc.stderr}"
        )
    return proc.stdout


class WriterVersionGateTests(unittest.TestCase):
    def test_enabled_writer_refuses_on_vulnerable_sqlite(self):
        out = _run_probe(vendored=False, writes_flag="1")
        if "FIXED True" in out:
            self.skipTest(
                "system SQLite already carries the WAL-reset fix; the "
                "vulnerable-library case is not reproducible on this host"
            )
        self.assertIn("FIXED False", out)
        self.assertNotIn("CONSTRUCTED", out,
                         "an ENABLED writer must not construct on a SQLite "
                         "inside the WAL-reset corruption window")
        self.assertIn("REFUSED", out)
        self.assertIn("3.51.3", out, "refusal must name the required version")

    def test_disabled_writer_constructs_on_any_sqlite(self):
        # Unborn / dormant state must be byte-for-byte unchanged.
        out = _run_probe(vendored=False, writes_flag=None)
        self.assertIn("CONSTRUCTED", out)

    def test_enabled_writer_constructs_on_vendored_sqlite(self):
        if not _VENDOR_LIB.is_dir():
            self.skipTest("vendored SQLite not present")
        out = _run_probe(vendored=True, writes_flag="1")
        self.assertIn("FIXED True", out)
        self.assertIn("CONSTRUCTED", out)


if __name__ == "__main__":
    unittest.main()
