# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Happy-path tests for core.ledger.writer.

Locks the production-write contract for the ledger writer:
  - Disabled by default; opt-in via MAEZ_LEDGER_WRITES.
  - One-row append computes prev/chain hashes correctly.
  - Many-row append maintains chain integrity (verify_chain clean).
  - Head pointer (meta.last_chain_hash) tracks the tail.
  - Determinism across fresh DBs given pinned inputs.
  - Each turn_kind accepts a minimal valid payload.
  - close() releases the connection.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_writer_")

from core.ledger import writer  # noqa: E402
from core.ledger import chain, migrate  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


_LOWER_HEX = set("0123456789abcdef")


def _is_lower_hex_64(s: object) -> bool:
    return (
        isinstance(s, str)
        and len(s) == 64
        and all(c in _LOWER_HEX for c in s)
    )


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _scrub_ledger_env() -> dict:
    env = dict(os.environ)
    env.pop("MAEZ_LEDGER_WRITES", None)
    return env


def _read_meta(db_path: str, key: str) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _read_turn(db_path: str, turn_id: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def _all_turns_in_chain_order(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM turns ORDER BY rowid ASC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _count_turns(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    finally:
        conn.close()
    return n


class EnablementTests(unittest.TestCase):
    def test_disabled_by_default_when_env_unset(self):
        db_path = _fresh_db("enable_default")
        with patch.dict(os.environ, _scrub_ledger_env(), clear=True):
            os.environ["MAEZ_TEST_MODE"] = "1"
            w = writer.LedgerWriter(db_path)
            try:
                self.assertFalse(w.is_enabled(),
                    "MAEZ_LEDGER_WRITES unset → writer must be disabled by default")
                result = w.write_turn("user_message", "hello")
                self.assertIsNone(result,
                    "Disabled writer.write_turn must return None")
            finally:
                w.close()
        self.assertEqual(_count_turns(db_path), 1,
            "Disabled writer must NOT insert any turn row beyond genesis")

    def test_enabled_for_truthy_values(self):
        for value in ("1", "true", "True", "TRUE"):
            with self.subTest(value=value):
                db_path = _fresh_db(f"enable_{value}")
                with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": value}):
                    w = writer.LedgerWriter(db_path)
                    try:
                        self.assertTrue(w.is_enabled())
                        turn_id = w.write_turn("user_message", "hello")
                        self.assertIsNotNone(turn_id)
                        self.assertIsInstance(turn_id, str)
                        self.assertIsNotNone(_read_turn(db_path, turn_id))
                    finally:
                        w.close()


class WriteUserMessageTests(unittest.TestCase):
    def test_first_user_message_after_genesis(self):
        db_path = _fresh_db("single_user_msg")
        genesis_hash = _read_meta(db_path, "genesis_hash")
        self.assertEqual(_read_meta(db_path, "last_chain_hash"), genesis_hash)

        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                turn_id = w.write_turn(
                    "user_message", "hello world",
                    surface="telegram", raw_surface="telegram_text",
                )
            finally:
                w.close()

        self.assertEqual(len(turn_id), 36)
        self.assertEqual(turn_id.count("-"), 4)

        row = _read_turn(db_path, turn_id)
        self.assertEqual(row["turn_kind"], "user_message")
        self.assertEqual(row["raw_text"], "hello world")
        self.assertEqual(row["tenant_id"], "owner")
        self.assertEqual(row["surface"], "telegram")
        self.assertEqual(row["raw_surface"], "telegram_text")
        self.assertTrue(_is_lower_hex_64(row["chain_hash"]))
        self.assertEqual(row["prev_chain_hash"], genesis_hash)
        self.assertEqual(_read_meta(db_path, "last_chain_hash"), row["chain_hash"])


class ChainIntegrityTests(unittest.TestCase):
    def test_50_user_messages_chain_verifies_clean(self):
        db_path = _fresh_db("chain_50")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                ids = []
                for i in range(50):
                    tid = w.write_turn("user_message", f"message {i}")
                    self.assertIsNotNone(tid)
                    ids.append(tid)
            finally:
                w.close()

        self.assertEqual(len(set(ids)), 50, "every turn_id must be unique")
        rows = _all_turns_in_chain_order(db_path)
        self.assertEqual(len(rows), 51)
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [],
            f"chain corrupted after writer appends: {violations!r}")

    def test_head_pointer_equals_tail_after_many_writes(self):
        db_path = _fresh_db("head_50")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                last_id = None
                for i in range(50):
                    last_id = w.write_turn("user_message", f"msg {i}")
            finally:
                w.close()
        tail = _read_turn(db_path, last_id)
        self.assertEqual(_read_meta(db_path, "last_chain_hash"), tail["chain_hash"])
        rows = _all_turns_in_chain_order(db_path)
        self.assertEqual(chain.verify_chain(rows), [])
        self.assertEqual(rows[-1]["chain_hash"], tail["chain_hash"])


class PerKindWriteTests(unittest.TestCase):
    """Each turn_kind writes successfully with its minimal valid payload."""

    def _assert_clean_chain(self, db_path: str) -> None:
        rows = _all_turns_in_chain_order(db_path)
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [],
            f"chain dirty after kind write: {violations!r}")

    def _write_minimal(self, kind: str, db_path: str, **kwargs) -> str:
        raw_text = kwargs.pop("raw_text")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                tid = w.write_turn(kind, raw_text, **kwargs)
            finally:
                w.close()
        self.assertIsNotNone(tid, f"{kind!r} minimal payload must succeed")
        row = _read_turn(db_path, tid)
        self.assertEqual(row["turn_kind"], kind)
        self.assertTrue(_is_lower_hex_64(row["chain_hash"]))
        self._assert_clean_chain(db_path)
        return tid

    def test_user_message_minimal(self):
        self._write_minimal("user_message", _fresh_db("kind_user"), raw_text="hi")

    def test_model_reply_minimal(self):
        self._write_minimal(
            "model_reply", _fresh_db("kind_model"),
            raw_text="reply", model_id="qwen36-27b",
            prompt_hash="p" * 64, soul_hash="s" * 64,
            evidence_envelope={"claimable": [], "forbidden": []},
            audit_verdict={"verdict": "grounded"},
        )

    def test_tool_call_minimal(self):
        self._write_minimal(
            "tool_call", _fresh_db("kind_tool_call"),
            raw_text="run_shell ls",
            action_proposal={"tool": "run_shell", "args": {"cmd": "ls"}},
        )

    def test_tool_result_minimal(self):
        db = _fresh_db("kind_tool_result")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                parent = w.write_turn(
                    "tool_call", "run_shell ls",
                    action_proposal={"tool": "run_shell", "args": {}},
                )
            finally:
                w.close()
        self._write_minimal(
            "tool_result", db,
            raw_text="output", parent_turn_id=parent,
        )

    def test_daemon_cycle_minimal(self):
        self._write_minimal(
            "daemon_cycle", _fresh_db("kind_daemon"),
            raw_text="thinking", model_id="qwen36-27b",
            prompt_hash="p" * 64, soul_hash="s" * 64,
            evidence_envelope={"claimable": [], "forbidden": []},
            audit_verdict={"verdict": "grounded"},
        )

    def test_approval_decision_minimal(self):
        self._write_minimal(
            "approval_decision", _fresh_db("kind_approval"),
            raw_text='{"event":"approved"}',
            audit_verdict={"verdict": "grounded"},
            pending_card_id=42,
        )

    def test_self_mod_dialog_step_minimal(self):
        self._write_minimal(
            "self_mod_dialog_step", _fresh_db("kind_selfmod"),
            raw_text="dialog step",
            audit_verdict={"verdict": "grounded"},
            self_mod_dialog_id=7,
        )

    def test_peer_message_in_minimal(self):
        db = _fresh_db("kind_peer_in")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                parent = w.write_turn("system_event", '{"event":"x"}')
            finally:
                w.close()
        self._write_minimal(
            "peer_message_in", db,
            raw_text="peer hello", parent_turn_id=parent,
        )

    def test_peer_message_out_minimal(self):
        self._write_minimal(
            "peer_message_out", _fresh_db("kind_peer_out"),
            raw_text="hello peer",
            evidence_envelope={"claimable": [], "forbidden": []},
            audit_verdict={"verdict": "grounded"},
        )

    def test_system_event_minimal(self):
        self._write_minimal(
            "system_event", _fresh_db("kind_system"),
            raw_text='{"event":"startup"}',
        )


class EraInitTests(unittest.TestCase):
    """Writer sets meta.ledger_era_starts_at on first non-genesis write."""

    def _read_era(self, db_path: str) -> str | None:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key='ledger_era_starts_at'"
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def test_era_unset_after_migrate_only(self):
        """Fresh migrated DB has no era set — only writer sets it."""
        db_path = _fresh_db("era_unset")
        era = self._read_era(db_path)
        # migrate.run does NOT seed the era row. It's the writer's job.
        self.assertTrue(
            era is None or not (era or "").strip(),
            f"era should be unset on fresh migrate; got {era!r}",
        )

    def test_first_write_sets_era(self):
        db_path = _fresh_db("era_first")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                w.write_turn("user_message", "first ever")
            finally:
                w.close()
        era_str = self._read_era(db_path)
        self.assertIsNotNone(era_str)
        # Should be a parseable float.
        era_float = float(era_str)
        self.assertGreater(era_float, 0)

    def test_second_write_does_not_change_era(self):
        db_path = _fresh_db("era_second")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                w.write_turn("user_message", "first")
                era_after_first = self._read_era(db_path)
                # Sleep imperceptibly to ensure if era WERE updated, the
                # value would differ.
                import time as _time
                _time.sleep(0.01)
                w.write_turn("user_message", "second")
                era_after_second = self._read_era(db_path)
            finally:
                w.close()
        self.assertEqual(
            era_after_first, era_after_second,
            "era must NOT change on subsequent writes — only set on first",
        )

    def test_era_set_atomically_with_first_row(self):
        """Era is set in the same transaction as the first INSERT.

        Verified by reading meta.ledger_era_starts_at AFTER the write
        and confirming it matches the turn's timestamp.
        """
        db_path = _fresh_db("era_atomic")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            try:
                tid = w.write_turn("user_message", "atomic check")
            finally:
                w.close()
        row = _read_turn(db_path, tid)
        era_str = self._read_era(db_path)
        # Era stored as repr(float). Parse and compare to row timestamp.
        era_float = float(era_str)
        self.assertAlmostEqual(
            era_float, row["timestamp"], places=4,
            msg=f"era ({era_float}) should equal first row's timestamp ({row['timestamp']})",
        )


class LifecycleTests(unittest.TestCase):
    def test_close_prevents_further_writes(self):
        db_path = _fresh_db("lifecycle_close")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db_path)
            tid = w.write_turn("user_message", "before close")
            self.assertIsNotNone(tid)
            w.close()
            with self.assertRaises(
                (sqlite3.ProgrammingError, sqlite3.Error,
                 ValueError, RuntimeError)
            ):
                w.write_turn("user_message", "after close")


if __name__ == "__main__":
    unittest.main()
