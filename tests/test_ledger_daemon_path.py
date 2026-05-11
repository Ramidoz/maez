# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Daemon ledger DB path invariants for sandbox acceptance.

Slice 2.5c needs a throwaway ledger DB without editing daemon code.
The daemon therefore must honor MAEZ_LEDGER_DB_PATH while preserving
memory/ledger.db as the production default.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def _read_daemon_ledger_path(env_extra: dict[str, str] | None = None) -> dict:
    env = os.environ.copy()
    env["MAEZ_TEST_MODE"] = "1"
    env.pop("MAEZ_LEDGER_DB_PATH", None)
    if env_extra:
        env.update(env_extra)
    code = (
        "import json\n"
        "from daemon import maez_daemon as md\n"
        "print(json.dumps({'base': str(md.BASE_DIR), "
        "'ledger': str(md.LEDGER_DB_PATH)}))\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if res.returncode != 0:
        raise AssertionError(
            f"daemon import failed rc={res.returncode}\n"
            f"stdout={res.stdout}\nstderr={res.stderr}"
        )
    return json.loads(res.stdout)


class DaemonLedgerPathTests(unittest.TestCase):
    def test_daemon_path_import_does_not_load_chromadb(self):
        code = r"""
import builtins
import json

_real_import = builtins.__import__


def _guarded_import(name, *args, **kwargs):
    if name == "chromadb" or name.startswith("chromadb."):
        raise RuntimeError(f"unexpected chromadb import: {name}")
    return _real_import(name, *args, **kwargs)


builtins.__import__ = _guarded_import
from daemon import maez_daemon as md
print(json.dumps({"ledger": str(md.LEDGER_DB_PATH)}))
"""
        env = os.environ.copy()
        env["MAEZ_TEST_MODE"] = "1"
        res = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(
            res.returncode,
            0,
            "daemon path import should not load Chroma/native vector DB "
            f"dependencies\nstdout={res.stdout}\nstderr={res.stderr}",
        )

    def test_default_ledger_path_is_memory_ledger_db(self):
        payload = _read_daemon_ledger_path()
        self.assertEqual(
            payload["ledger"],
            str(Path(payload["base"]) / "memory" / "ledger.db"),
        )

    def test_maez_ledger_db_path_overrides_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = str(Path(tmp) / "sandbox-ledger.db")
            payload = _read_daemon_ledger_path(
                {"MAEZ_LEDGER_DB_PATH": sandbox}
            )
        self.assertEqual(payload["ledger"], sandbox)


if __name__ == "__main__":
    unittest.main()
