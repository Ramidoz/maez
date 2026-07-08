from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from core.consent.bindings import BindingRegistry, ConsentBindingPaths


class ConsentBindingRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = ConsentBindingPaths(
            db_path=root / "memory" / "consent" / "owner_surface_bindings.sqlite3",
            receipt_log=root / "logs" / "consent_binding_receipts.jsonl",
        )
        self.registry = BindingRegistry(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def _receipts(self):
        if not self.paths.receipt_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.paths.receipt_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_enroll_active_binding_and_receipt_use_tmp_paths(self):
        binding = self.registry.enroll(
            "telegram",
            "111:222",
            enrolled_via="cli",
        )

        active = self.registry.active_binding_for("telegram", "111:222")
        self.assertIsNotNone(active)
        self.assertEqual(active.binding_id, binding.binding_id)
        self.assertEqual(active.status, "active")
        self.assertTrue(str(self.paths.db_path).startswith(self.tmp.name))
        self.assertTrue(str(self.paths.receipt_log).startswith(self.tmp.name))

        receipts = self._receipts()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["event"], "enrolled")
        self.assertEqual(receipts[0]["surface_kind"], "telegram")
        self.assertEqual(receipts[0]["surface_identity"], "111:222")

    def test_wrong_chat_id_cannot_match_owner_binding(self):
        self.registry.enroll("telegram", "111:222", enrolled_via="cli")

        self.assertIsNone(self.registry.active_binding_for("telegram", "111:333"))

    def test_revoked_binding_cannot_resolve_and_receipt_appends(self):
        binding = self.registry.enroll("telegram", "111:222", enrolled_via="cli")
        self.registry.revoke(binding.binding_id)

        self.assertIsNone(self.registry.active_binding_for("telegram", "111:222"))
        receipts = self._receipts()
        self.assertEqual([row["event"] for row in receipts], ["enrolled", "revoked"])
        self.assertEqual(receipts[1]["binding_id"], binding.binding_id)

    def test_migration_from_env_is_idempotent(self):
        env = {
            "MAEZ_TELEGRAM_USER_ID": "111",
            "MAEZ_TELEGRAM_CHAT_ID": "222",
        }
        with mock.patch.dict("os.environ", env, clear=False):
            first = self.registry.migrate_telegram_env_binding()
            second = self.registry.migrate_telegram_env_binding()

        self.assertEqual(first.binding_id, second.binding_id)
        self.assertEqual(len(self.registry.list_bindings()), 1)
        self.assertEqual(len(self._receipts()), 1)
        self.assertEqual(self._receipts()[0]["enrolled_via"], "migration_env")


class ConsentBindingCliTests(unittest.TestCase):
    def test_cli_enroll_list_revoke_uses_injected_tmp_paths(self):
        from scripts import consent_binding

        with tempfile.TemporaryDirectory() as td:
            paths = ConsentBindingPaths(
                db_path=Path(td) / "memory" / "consent" / "owner_surface_bindings.sqlite3",
                receipt_log=Path(td) / "logs" / "consent_binding_receipts.jsonl",
            )
            out = StringIO()
            with redirect_stdout(out):
                code = consent_binding.main(
                    ["enroll", "--surface-kind", "telegram", "--surface-identity", "111:222"],
                    paths=paths,
                )
            self.assertEqual(code, 0)
            self.assertIn("bind_", out.getvalue())

            out = StringIO()
            with redirect_stdout(out):
                code = consent_binding.main(["list"], paths=paths)
            self.assertEqual(code, 0)
            self.assertIn("111:222", out.getvalue())

            binding_id = BindingRegistry(paths).active_binding_for(
                "telegram",
                "111:222",
            ).binding_id
            out = StringIO()
            with redirect_stdout(out):
                code = consent_binding.main(["revoke", "--binding-id", binding_id], paths=paths)
            self.assertEqual(code, 0)
            self.assertIsNone(
                BindingRegistry(paths).active_binding_for("telegram", "111:222")
            )


if __name__ == "__main__":
    unittest.main()
