from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path


class FreshMomentReceiptsTest(unittest.TestCase):
    def test_record_private_thought_landed_writes_content_light_row(self):
        from core.cognition.fresh_moment_receipts import (
            FRESH_MOMENT_BOND_ID,
            FRESH_MOMENT_RECEIPTS_VERSION,
            FreshMomentReceipts,
            MOMENT_PRIVATE_THOUGHT_LANDED,
        )

        with tempfile.TemporaryDirectory() as td:
            store = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            receipt_id = store.record_private_thought_landed(
                thought_id=42,
                source="lean_idle_heartbeat.v0",
                bond_id=FRESH_MOMENT_BOND_ID,
                content_sha256="0123456789abcdef",
                content_len=37,
                created_at=123.5,
            )

            rows = store.recent(limit=5)

        self.assertEqual(receipt_id, 1)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["moment_kind"], MOMENT_PRIVATE_THOUGHT_LANDED)
        self.assertEqual(row["thought_id"], 42)
        self.assertEqual(row["source"], "lean_idle_heartbeat.v0")
        self.assertEqual(row["bond_id"], FRESH_MOMENT_BOND_ID)
        self.assertEqual(row["content_sha256"], "0123456789abcdef")
        self.assertEqual(row["content_len"], 37)
        self.assertEqual(row["schema_version"], FRESH_MOMENT_RECEIPTS_VERSION)

    def test_schema_contains_no_value_judgment_columns(self):
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            store = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            columns = set(store.column_names())

        forbidden = {"salience", "score", "importance", "rank", "value", "matters"}
        self.assertTrue(forbidden.isdisjoint(columns), columns)

    def test_schema_contains_no_raw_text_columns(self):
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        with tempfile.TemporaryDirectory() as td:
            store = FreshMomentReceipts(Path(td) / "fresh_moment_receipts.db")
            columns = set(store.column_names())

        forbidden = {"content", "text", "thought_text", "raw_text", "note", "prompt"}
        self.assertTrue(forbidden.isdisjoint(columns), columns)

    def test_db_file_does_not_contain_raw_thought_text(self):
        from core.cognition.fresh_moment_receipts import FreshMomentReceipts

        secret = "SECRET PRIVATE THOUGHT TEXT"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fresh_moment_receipts.db"
            store = FreshMomentReceipts(path)
            store.record_private_thought_landed(
                thought_id=1,
                source="lean_idle_heartbeat.v0",
                bond_id="private_owner",
                content_sha256="aaaaaaaaaaaaaaaa",
                content_len=len(secret),
                created_at=1.0,
            )
            blob = path.read_bytes()

        self.assertNotIn(secret.encode(), blob)

    def test_writer_imports_no_downstream_organs(self):
        src = Path("core/cognition/fresh_moment_receipts.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        forbidden = (
            "core.evolution.wonderings",
            "core.wonderings",
            "core.evolution.wants",
            "core.wants",
            "core.cognition.salience_ledger",
            "core.evolution.dream_state",
            "core.actions.action_engine",
            "core.soul_editor",
            "core.evolution.soul_loader",
        )
        self.assertTrue(set(forbidden).isdisjoint(imported), imported)

    def test_default_path_points_to_memory(self):
        from core.cognition.fresh_moment_receipts import fresh_moment_receipts_db_path

        path = fresh_moment_receipts_db_path()

        self.assertEqual(path.name, "fresh_moment_receipts.db")
        self.assertEqual(path.parent.name, "memory")


if __name__ == "__main__":
    unittest.main()
