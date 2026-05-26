from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path


class DriveCuriosityBondScopingTests(unittest.TestCase):
    def test_per_bond_hmac_keys_distinct(self):
        from core.policies.diagnostics import hmac_digest_for_bond

        master_key = bytes(range(32))

        first = hmac_digest_for_bond(
            master_key=master_key,
            bond_id="firstborn",
            value="same-content",
        )
        second = hmac_digest_for_bond(
            master_key=master_key,
            bond_id="second-bond",
            value="same-content",
        )

        self.assertRegex(first, r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(second, r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertNotEqual(first, second)

    def test_master_key_auto_initialized_with_0600_perms(self):
        from core.policies.diagnostics import (
            CuriosityDiagnosticEventType,
            ensure_master_key,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key_path = root / "memory" / "drive_curiosity_master.key"
            log_path = root / "logs" / "drive_driven_curiosity_diagnostics.jsonl"

            key = ensure_master_key(master_key_path=key_path, diagnostic_log_path=log_path)

            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            key_size = key_path.stat().st_size
            key_mode = stat.S_IMODE(key_path.stat().st_mode)

        self.assertEqual(len(key), 32)
        self.assertEqual(key_size, 32)
        self.assertEqual(key_mode, 0o600)
        self.assertEqual(rows[0]["event_type"], CuriosityDiagnosticEventType.MASTER_KEY_INITIALIZED.value)
        self.assertIsNone(rows[0]["bond_digest"])

    def test_master_key_path_distinct_from_egress_telemetry_key(self):
        from core import paths

        drive_path = paths.drive_curiosity_master_key()
        egress_path = paths.memory_dir() / "egress_telemetry.key"

        self.assertNotEqual(drive_path, egress_path)
        self.assertEqual(drive_path.name, "drive_curiosity_master.key")


if __name__ == "__main__":
    unittest.main()
