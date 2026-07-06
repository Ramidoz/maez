import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.infra.unseal_receipts import UnsealReceipts, default_db_path


class UnsealReceiptTests(unittest.TestCase):
    def test_record_and_read_back(self):
        with TemporaryDirectory() as td:
            store = UnsealReceipts(db_path=Path(td) / "ur.db")
            rid = store.record_unseal(
                actor="rohit",
                s7_receipt_ref="s7:abc123",
                scope_kind="thought_id",
                scope_detail="thought_id=42",
                reason="debugging the recall regression",
            )
            self.assertEqual(store.count(), 1)
            row = store.recent(limit=1)[0]
            self.assertEqual(row["id"], rid)
            self.assertEqual(row["actor"], "rohit")
            self.assertEqual(row["scope_kind"], "thought_id")

    def test_scope_kind_validated(self):
        with TemporaryDirectory() as td:
            store = UnsealReceipts(db_path=Path(td) / "ur.db")
            with self.assertRaises(ValueError):
                store.record_unseal(
                    actor="rohit",
                    s7_receipt_ref="s7:x",
                    scope_kind="everything",
                    scope_detail="*",
                    reason="no",
                )

    def test_required_text_fields_are_non_empty(self):
        with TemporaryDirectory() as td:
            store = UnsealReceipts(db_path=Path(td) / "ur.db")
            valid = {
                "actor": "rohit",
                "s7_receipt_ref": "s7:x",
                "scope_kind": "range",
                "scope_detail": "1..3",
                "reason": "birth prework audit",
            }
            for field in ("actor", "s7_receipt_ref", "scope_detail", "reason"):
                params = dict(valid)
                params[field] = " "
                with self.subTest(field=field):
                    with self.assertRaises(ValueError):
                        store.record_unseal(**params)

    def test_append_only_at_sql_layer(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ur.db"
            store = UnsealReceipts(db_path=db)
            store.record_unseal(
                actor="rohit",
                s7_receipt_ref="s7:x",
                scope_kind="query",
                scope_detail="q~redacted",
                reason="r",
            )
            conn = sqlite3.connect(db)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE unseal_receipts SET actor='mallory'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM unseal_receipts")
            conn.close()

    def test_default_db_path_uses_memory_dir(self):
        with TemporaryDirectory() as td:
            memory = Path(td) / "memory"
            with patch("core.infra.unseal_receipts._paths.memory_dir", return_value=memory):
                self.assertEqual(default_db_path(), memory / "unseal_receipts.db")


if __name__ == "__main__":
    unittest.main()
