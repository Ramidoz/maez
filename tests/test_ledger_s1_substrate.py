# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""S1 consolidation-spine ledger substrate tests.

Pins docs/superpowers/specs/2026-07-08-consolidation-spine-v0-design.md
S1 only: row taint/provenance labels, privacy access labels, writer-assigned
chain_position, fresh-genesis shape, fail-closed populated-ledger migration,
and recent-turn round trip.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_s1_")

from core.ledger import chain, migrate, recent_turns, writer  # noqa: E402
from scripts import verify_ledger_chain  # noqa: E402


def tearDownModule():
    import shutil

    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _turn_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    finally:
        conn.close()


def _write_user(db_path: str, text: str) -> str:
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db_path)
        try:
            turn_id = w.write_turn(
                "user_message",
                text,
                surface="test",
                taint_labels=["owner_utterance"],
                privacy_access="public",
            )
        finally:
            w.close()
    assert turn_id is not None
    return turn_id


def _build_pre_s1_populated_ledger(db_path: str) -> None:
    """Create a v0004-shaped populated ledger without running migration 0005."""
    migrations_dir = Path(__file__).resolve().parents[1] / "core" / "ledger" / "migrations"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE schema_migrations ("
            " name TEXT PRIMARY KEY,"
            " applied_at REAL NOT NULL"
            ")"
        )
        for stem in (
            "0001_init",
            "0002_triggers",
            "0003_add_lifecycle_stage",
            "0004_add_audit_trace_metadata",
        ):
            conn.executescript((migrations_dir / f"{stem}.sql").read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations(name, applied_at) VALUES (?, ?)",
                (stem, time.time()),
            )
        conn.execute(
            "INSERT INTO turns ("
            "turn_id, timestamp, schema_version, turn_kind, surface, "
            "raw_text, prev_chain_hash, chain_hash"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "pre-s1-existing-row",
                1.0,
                1,
                "system_event",
                "system",
                '{"event":"old"}',
                None,
                "a" * 64,
            ),
        )
        conn.commit()
    finally:
        conn.close()


class MigrationRefusalTests(unittest.TestCase):
    def test_s1_migration_refuses_preexisting_turn_rows(self):
        db = str(Path(_TEST_DB_DIR) / f"pre_s1_{os.urandom(4).hex()}.db")
        _build_pre_s1_populated_ledger(db)
        self.assertTrue(
            hasattr(migrate, "LedgerMigrationRefusal"),
            "S1 migration refusal must be a typed error",
        )

        with self.assertRaises(migrate.LedgerMigrationRefusal):
            migrate.run(db)

        conn = sqlite3.connect(db)
        try:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(turns)").fetchall()
            }
        finally:
            conn.close()
        self.assertFalse(
            {"taint_labels_json", "privacy_access", "chain_position"} & columns,
            "refused populated ledgers must not be partially migrated",
        )


class FreshGenesisS1Tests(unittest.TestCase):
    def test_fresh_ledger_has_s1_genesis_and_verifies(self):
        db = _fresh_db("fresh_genesis")
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT taint_labels_json, privacy_access, chain_position "
                "FROM turns WHERE turn_id='genesis'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["taint_labels_json"], "[]")
        self.assertEqual(row["privacy_access"], "public")
        self.assertEqual(row["chain_position"], 0)
        self.assertEqual(verify_ledger_chain.main([db, "--quiet"]), 0)


class WriterStampingTests(unittest.TestCase):
    def test_enabled_writer_refuses_omitted_stamp_kwargs_with_typed_error(self):
        from core.ledger import taint_stamping

        db = _fresh_db("missing_stamp")
        before = _turn_count(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                with self.assertRaises(taint_stamping.TaintStampingRefusal):
                    w.write_turn(
                        "user_message",
                        "hi",
                        surface="test",
                    )
                with self.assertRaises(taint_stamping.TaintStampingRefusal):
                    w.write_turn(
                        "user_message",
                        "hi",
                        surface="test",
                        taint_labels=["owner_utterance"],
                    )
            finally:
                w.close()
        self.assertEqual(_turn_count(db), before)

    def test_enabled_writer_refuses_empty_taint_labels_with_typed_error(self):
        from core.ledger import taint_stamping

        db = _fresh_db("empty_taint")
        before = _turn_count(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                with self.assertRaises(taint_stamping.TaintStampingRefusal):
                    w.write_turn(
                        "user_message",
                        "hi",
                        surface="test",
                        taint_labels=[],
                        privacy_access="public",
                    )
            finally:
                w.close()
        self.assertEqual(_turn_count(db), before)

    def test_enabled_writer_refuses_none_taint_labels_with_typed_error(self):
        from core.ledger import taint_stamping

        db = _fresh_db("none_taint")
        before = _turn_count(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                with self.assertRaises(taint_stamping.TaintStampingRefusal):
                    w.write_turn(
                        "user_message",
                        "hi",
                        surface="test",
                        taint_labels=None,
                        privacy_access="public",
                    )
            finally:
                w.close()
        self.assertEqual(_turn_count(db), before)

    def test_enabled_writer_refuses_out_of_map_labels_with_typed_error(self):
        from core.ledger import taint_stamping

        db = _fresh_db("out_of_map")
        before = _turn_count(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                with self.assertRaises(taint_stamping.TaintStampingRefusal):
                    w.write_turn(
                        "user_message",
                        "hi",
                        surface="test",
                        taint_labels=["self_generated"],
                        privacy_access="public",
                    )
            finally:
                w.close()
        self.assertEqual(_turn_count(db), before)


class ChainPositionTests(unittest.TestCase):
    def test_chain_position_is_unique_and_matches_chain_walk_under_concurrency(self):
        db = _fresh_db("position_concurrent")
        count = 16
        barrier = Barrier(count)
        results: list[str | None] = [None] * count

        def worker(index: int) -> None:
            barrier.wait()
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = writer.LedgerWriter(db)
                try:
                    results[index] = w.write_turn(
                        "user_message",
                        f"concurrent-{index}",
                        surface="test",
                        taint_labels=["owner_utterance"],
                        privacy_access="public",
                    )
                finally:
                    w.close()

        with ThreadPoolExecutor(max_workers=count) as executor:
            list(executor.map(worker, range(count)))

        self.assertTrue(all(results), results)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            positions = [
                row["chain_position"]
                for row in conn.execute(
                    "SELECT chain_position FROM turns ORDER BY chain_position"
                ).fetchall()
            ]
            walked = verify_ledger_chain._load_turns_in_chain_order(conn)
        finally:
            conn.close()
        self.assertEqual(positions, list(range(count + 1)))
        self.assertEqual(
            [row["chain_position"] for row in walked],
            list(range(count + 1)),
        )

    def test_chain_position_is_not_hash_included_but_taint_and_privacy_are(self):
        base = dict(migrate.GENESIS_ROW)
        base_hash = chain.compute_chain_hash(base, None)

        moved = dict(base)
        moved["chain_position"] = 99
        self.assertEqual(chain.compute_chain_hash(moved, None), base_hash)

        tainted = dict(base)
        tainted["taint_labels_json"] = '["owner_utterance"]'
        self.assertNotEqual(chain.compute_chain_hash(tainted, None), base_hash)

        sealed = dict(base)
        sealed["privacy_access"] = "sealed_adjacent"
        self.assertNotEqual(chain.compute_chain_hash(sealed, None), base_hash)


class RecentTurnsRoundTripTests(unittest.TestCase):
    def test_taint_privacy_and_position_survive_recent_turns_read(self):
        db = _fresh_db("recent_roundtrip")
        turn_id = _write_user(db, "owner says hi")

        rows = recent_turns.recent_turns_by_kind(
            db,
            kinds=["user_message"],
            limit=10,
            include_trace_labeled=True,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["turn_id"], turn_id)
        self.assertEqual(rows[0]["taint_labels_json"], '["owner_utterance"]')
        self.assertEqual(rows[0]["privacy_access"], "public")
        self.assertEqual(rows[0]["chain_position"], 1)


if __name__ == "__main__":
    unittest.main()
