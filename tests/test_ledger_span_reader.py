# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""S2 consolidation-spine bounded span reader tests.

Pins docs/superpowers/specs/2026-07-08-consolidation-spine-v0-design.md
S2 only: chain_position cursor semantics, frozen high-water spans, short
read-only transactions, full-row materialization, and typed chain failures.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_span_")

from core.ledger import migrate, span_reader, writer  # noqa: E402


def tearDownModule():
    import shutil

    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


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


def _write_many_users(db_path: str, count: int, prefix: str = "row") -> list[str]:
    turn_ids: list[str] = []
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db_path)
        try:
            for index in range(count):
                turn_id = w.write_turn(
                    "user_message",
                    f"{prefix}-{index:04d}",
                    surface="test",
                    taint_labels=["owner_utterance"],
                    privacy_access="public",
                )
                assert turn_id is not None
                turn_ids.append(turn_id)
        finally:
            w.close()
    return turn_ids


class SpanReaderCursorTests(unittest.TestCase):
    def test_chain_position_cursor_ignores_uuid_ordering(self):
        db = _fresh_db("uuid_order")
        uuid_values = [
            "ffffffff-ffff-4fff-8fff-ffffffffffff",
            "00000000-0000-4000-8000-000000000000",
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "11111111-1111-4111-8111-111111111111",
        ]
        with patch("core.ledger.writer.uuid.uuid4", side_effect=uuid_values):
            _write_many_users(db, len(uuid_values), prefix="position")

        result = span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(result.high_water, 4)
        self.assertEqual(
            [row["raw_text"] for row in result.rows],
            ["position-0000", "position-0001", "position-0002", "position-0003"],
        )
        self.assertEqual(
            [row["turn_id"] for row in result.rows],
            uuid_values,
            "span order must follow chain_position, not lexical turn_id ordering",
        )
        self.assertEqual([row["chain_position"] for row in result.rows], [1, 2, 3, 4])

    def test_returns_full_turn_rows_for_citation_lock_consumers(self):
        db = _fresh_db("full_rows")
        _write_user(db, "row shape")

        result = span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(len(result.rows), 1)
        row = result.rows[0]
        required_columns = {
            "turn_id",
            "tenant_id",
            "timestamp",
            "schema_version",
            "turn_kind",
            "surface",
            "raw_surface",
            "parent_turn_id",
            "correction_of",
            "model_id",
            "lora_hash",
            "soul_hash",
            "prompt_hash",
            "raw_text",
            "rewritten_text",
            "was_rewritten",
            "signals_present",
            "signals_absent",
            "evidence_envelope_json",
            "action_proposal_json",
            "audit_verdict_json",
            "will_i_json",
            "memory_read_ids",
            "memory_written_ids",
            "audit_log_id",
            "fabrication_event_id",
            "self_mod_dialog_id",
            "pending_card_id",
            "taint_labels_json",
            "privacy_access",
            "lifecycle_stage",
            "prev_chain_hash",
            "chain_hash",
            "chain_position",
        }
        self.assertTrue(required_columns <= set(row.keys()))
        self.assertEqual(row["taint_labels_json"], '["owner_utterance"]')
        self.assertEqual(row["privacy_access"], "public")


class SpanReaderHighWaterTests(unittest.TestCase):
    def test_empty_span_after_equal_high_water_returns_empty_result(self):
        db = _fresh_db("empty_span")

        result = span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(result.high_water, 0)
        self.assertEqual(result.rows, [])

    def test_single_row_span(self):
        db = _fresh_db("single_row")
        turn_id = _write_user(db, "one")

        result = span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(result.high_water, 1)
        self.assertEqual([row["turn_id"] for row in result.rows], [turn_id])
        self.assertEqual([row["chain_position"] for row in result.rows], [1])

    def test_large_span(self):
        db = _fresh_db("large_span")
        _write_many_users(db, 256, prefix="large")

        result = span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(result.high_water, 256)
        self.assertEqual(len(result.rows), 256)
        self.assertEqual(result.rows[0]["chain_position"], 1)
        self.assertEqual(result.rows[-1]["chain_position"], 256)

    def test_rows_appended_after_high_water_freeze_are_invisible_until_next_call(self):
        db = _fresh_db("frozen_high_water")
        _write_user(db, "before-freeze")
        original_load_rows = span_reader._load_turns_through_high_water
        appended: list[str] = []
        freeze_reached = threading.Event()
        append_done = threading.Event()
        append_errors: list[BaseException] = []

        def append_after_freeze() -> None:
            freeze_reached.wait(timeout=2.0)
            try:
                appended.append(_write_user(db, "after-freeze"))
            except BaseException as exc:
                append_errors.append(exc)
            finally:
                append_done.set()

        def load_after_concurrent_append(
            conn: sqlite3.Connection,
            high_water: int,
        ) -> list[dict]:
            freeze_reached.set()
            self.assertTrue(append_done.wait(timeout=2.0))
            return original_load_rows(conn, high_water)

        thread = threading.Thread(target=append_after_freeze)
        thread.start()
        try:
            with patch.object(
                span_reader,
                "_load_turns_through_high_water",
                side_effect=load_after_concurrent_append,
            ):
                result = span_reader.read_span(db, after_chain_position=0)
        finally:
            thread.join(timeout=2.0)

        self.assertFalse(append_errors)
        self.assertEqual(len(appended), 1)
        self.assertEqual(result.high_water, 1)
        self.assertEqual([row["raw_text"] for row in result.rows], ["before-freeze"])

        subsequent = span_reader.read_span(db, after_chain_position=0)
        self.assertEqual(subsequent.high_water, 2)
        self.assertEqual(
            [row["raw_text"] for row in subsequent.rows],
            ["before-freeze", "after-freeze"],
        )


class SpanReaderChainVerificationTests(unittest.TestCase):
    def test_chain_tamper_inside_span_raises_typed_error(self):
        db = _fresh_db("tamper")
        _write_user(db, "untampered")
        conn = sqlite3.connect(db)
        try:
            conn.execute("DROP TRIGGER turns_no_update")
            conn.execute(
                "UPDATE turns SET raw_text = ? WHERE chain_position = 1",
                ("tampered",),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(span_reader.SpanChainVerificationError) as raised:
            span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(raised.exception.high_water, 1)
        self.assertEqual(raised.exception.after_chain_position, 0)
        self.assertTrue(raised.exception.violations)
        self.assertIn(
            "chain",
            raised.exception.reason,
            "typed span errors must identify chain verification failure",
        )

    def test_structural_chain_failure_raises_chain_typed_error(self):
        db = _fresh_db("structural_tamper")
        _write_user(db, "orphan me")
        conn = sqlite3.connect(db)
        try:
            conn.execute("DROP TRIGGER turns_no_delete")
            conn.execute("DELETE FROM turns WHERE turn_id = 'genesis'")
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(span_reader.SpanChainVerificationError) as raised:
            span_reader.read_span(db, after_chain_position=0)

        self.assertEqual(raised.exception.high_water, 1)
        self.assertEqual(raised.exception.violations[0]["reason"], "chain_no_genesis")


class SpanReaderContentionTests(unittest.TestCase):
    def test_connection_is_closed_before_chain_verification_work(self):
        db = _fresh_db("close_before_verify")
        _write_user(db, "verify after close")
        real_open = span_reader._open_readonly
        real_verify = span_reader.chain.verify_chain
        opened: list[object] = []

        class ConnectionProxy:
            def __init__(self, conn: sqlite3.Connection) -> None:
                self._conn = conn
                self.closed = False

            @property
            def in_transaction(self) -> bool:
                return self._conn.in_transaction

            def execute(self, *args, **kwargs):
                return self._conn.execute(*args, **kwargs)

            def close(self) -> None:
                self.closed = True
                self._conn.close()

        def tracked_open(path: str):
            proxy = ConnectionProxy(real_open(path))
            opened.append(proxy)
            return proxy

        def assert_closed_before_verify(rows: list[dict]) -> list[dict]:
            self.assertTrue(opened)
            self.assertTrue(
                opened[0].closed,
                "span reader must close SQLite before chain verification work",
            )
            return real_verify(rows)

        with patch.object(span_reader, "_open_readonly", side_effect=tracked_open), \
             patch.object(
                 span_reader.chain,
                 "verify_chain",
                 side_effect=assert_closed_before_verify,
             ):
            result = span_reader.read_span(db, after_chain_position=0)

        self.assertEqual([row["raw_text"] for row in result.rows], ["verify after close"])

    def test_read_during_active_begin_immediate_writer_does_not_deadlock(self):
        db = _fresh_db("begin_immediate_contention")
        _write_user(db, "committed-before-writer")
        writer_conn = sqlite3.connect(db, isolation_level=None, check_same_thread=False)
        writer_conn.execute("PRAGMA busy_timeout = 5000")
        writer_conn.execute("BEGIN IMMEDIATE")
        try:
            started = time.monotonic()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    span_reader.read_span,
                    db,
                    after_chain_position=0,
                )
                result = future.result(timeout=2.0)
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 2.0)
            self.assertEqual([row["raw_text"] for row in result.rows], ["committed-before-writer"])

            commit_started = time.monotonic()
            writer_conn.execute("COMMIT")
            self.assertLess(
                time.monotonic() - commit_started,
                1.0,
                "span reads must not leave a transaction that stalls the active writer",
            )
        finally:
            try:
                writer_conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            writer_conn.close()


class SpanReaderReadOnlyTests(unittest.TestCase):
    def test_missing_db_is_not_created_by_read_only_open(self):
        missing = Path(_TEST_DB_DIR) / f"missing_{os.urandom(4).hex()}.db"

        with self.assertRaises(span_reader.SpanReadError):
            span_reader.read_span(str(missing), after_chain_position=0)

        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
