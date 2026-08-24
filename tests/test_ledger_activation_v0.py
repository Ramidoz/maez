"""Ledger Activation / Disabled-State Honesty v0.

One switch (MAEZ_LEDGER_WRITES) says "writing is allowed"; a strict schema check
says "the notebook is real"; the disabled path opens no SQLite at all.
"""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


class LedgerWritesEnabled(unittest.TestCase):
    def _enabled(self, value):
        env = {} if value is None else {"MAEZ_LEDGER_WRITES": value}
        with mock.patch.dict(os.environ, env, clear=False):
            if value is None:
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
            from core.ledger.writes_flag import ledger_writes_enabled
            return ledger_writes_enabled()

    def test_true_values_enable(self):
        for v in ("1", "true", "TRUE", " true "):
            self.assertTrue(self._enabled(v), v)

    def test_false_and_unset_disable(self):
        for v in (None, "", "0", "false", "no", "off"):
            self.assertFalse(self._enabled(v), repr(v))

    def test_unrecognized_disables_with_warning(self):
        from core.ledger import writes_flag
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "yarp"}):
            with self.assertLogs("core.ledger.writes_flag", level="WARNING") as logs:
                self.assertFalse(writes_flag.ledger_writes_enabled())
        self.assertIn("unrecognized", "\n".join(logs.output).lower())


class PredicateDoesNotFork(unittest.TestCase):
    def test_writer_and_reconcile_delegate_to_helper(self):
        from core.ledger import reconcile, writes_flag
        from core.ledger.writer import LedgerWriter
        wp = str(Path(tempfile.mkdtemp()) / "w.db")  # LedgerWriter requires db_path
        for v in ("1", "true", "0", "", "off", "garbage"):
            with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": v}):
                expected = writes_flag.ledger_writes_enabled()
                # close() matters now: an enabled writer holds the
                # single-owner latch until closed.
                w = LedgerWriter(wp)
                try:
                    self.assertEqual(w.is_enabled(), expected, v)
                finally:
                    w.close()
                self.assertEqual(reconcile._writes_enabled(), expected, v)

    def test_modules_no_longer_define_value_sets(self):
        import core.ledger.reconcile as r
        import core.ledger.writer as w
        self.assertFalse(hasattr(w, "_TRUE_VALUES"))
        self.assertFalse(hasattr(r, "_TRUE_VALUES"))


class LedgerIsInitialized(unittest.TestCase):
    def _fresh(self, name):
        return str(Path(tempfile.mkdtemp()) / f"{name}.db")

    def test_true_on_migrated_db(self):
        from core.ledger import migrate
        p = self._fresh("ok")
        migrate.run(p)
        self.assertTrue(migrate.ledger_is_initialized(p))

    def test_false_on_zero_byte_and_missing(self):
        from core.ledger import migrate
        missing = self._fresh("missing")
        self.assertFalse(migrate.ledger_is_initialized(missing))   # no file
        self.assertFalse(Path(missing).exists())                   # read-only: not created
        zero = self._fresh("zero")
        Path(zero).touch()
        self.assertFalse(migrate.ledger_is_initialized(zero))      # 0 bytes

    def test_true_after_one_real_write(self):
        # LIFECYCLE: last_chain_hash advances on write — a written-to ledger must
        # STILL be initialized. This catches the bug of requiring last==genesis.
        import os as _os
        from core.ledger import migrate
        from core.ledger.writer import try_write_turn
        p = self._fresh("written")
        migrate.run(p)
        with mock.patch.dict(_os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            self.assertTrue(try_write_turn(p, "user_message", "hello",
                                           surface="telegram_surface", parent_turn_id=None,
                                           taint_labels=["owner_utterance"],
                                           privacy_access="public"))
        self.assertTrue(migrate.ledger_is_initialized(p))          # still a real ledger

    def test_false_on_last_chain_hash_dangling(self):
        from core.ledger import migrate
        p = self._fresh("dangling")
        migrate.run(p)
        conn = sqlite3.connect(p)
        conn.execute("UPDATE meta SET value='deadbeef' WHERE key='last_chain_hash'")
        conn.commit()
        conn.close()
        self.assertFalse(migrate.ledger_is_initialized(p))

    def test_false_on_genesis_hash_mismatch(self):
        from core.ledger import migrate
        p = self._fresh("badanchor")
        migrate.run(p)
        conn = sqlite3.connect(p)
        conn.execute("UPDATE meta SET value='deadbeef' WHERE key='genesis_hash'")
        conn.commit()
        conn.close()
        self.assertFalse(migrate.ledger_is_initialized(p))

    def test_false_on_missing_genesis_row(self):
        # tables + meta keys exist but NO genesis row (a half-built notebook).
        # turns is append-only, so construct this with bare tables rather than
        # DELETE-ing from a migrated DB (which the append-only rule rejects).
        from core.ledger import migrate
        p = self._fresh("nogen")
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("CREATE TABLE turns (turn_id TEXT, chain_hash TEXT)")
        conn.execute("INSERT INTO meta VALUES ('genesis_hash', 'abc')")
        conn.execute("INSERT INTO meta VALUES ('last_chain_hash', 'abc')")
        conn.commit()
        conn.close()
        self.assertFalse(migrate.ledger_is_initialized(p))

    def test_never_raises_on_garbage(self):
        from core.ledger import migrate
        p = self._fresh("garbage")
        Path(p).write_text("this is not a sqlite database at all")
        self.assertFalse(migrate.ledger_is_initialized(p))         # no exception


# evidence_envelope shape is the SAME one tests/test_model_reply_persistence.py
# uses and is VERIFIED to write on an initialized+enabled ledger (returns a uuid).
_PERSIST_KW = dict(
    raw_text="audited reply text",
    surface="telegram_surface",
    parent_turn_id=None,
    model_id="qwen36-27b",
    prompt_material={"p": 1},
    soul_material={"s": 1},
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


class ModelReplyGate(unittest.TestCase):
    def test_disabled_opens_no_sqlite(self):
        # HEADLINE: ledger off → silent no-op, NO SQLite opened, no warning.
        from core.ledger import model_reply_persistence as mrp
        os.environ.pop("MAEZ_LEDGER_WRITES", None)
        with mock.patch("core.ledger.model_reply_persistence.sqlite3.connect") as conn:
            out = mrp.persist_model_reply(db_path="/nonexistent/ledger.db", **_PERSIST_KW)
        self.assertIsNone(out)
        conn.assert_not_called()

    def test_enabled_uninitialized_warns_once_no_write(self):
        from core.ledger import model_reply_persistence as mrp
        from core.ledger import model_reply_persistence_warning as warn
        warn._WARNED_KEYS.clear()
        zero = str(Path(tempfile.mkdtemp()) / "z.db")
        Path(zero).touch()  # enabled but uninitialized
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.model_reply_persistence", level="WARNING") as logs:
                out1 = mrp.persist_model_reply(db_path=zero, **_PERSIST_KW)
                out2 = mrp.persist_model_reply(db_path=zero, **_PERSIST_KW)
        self.assertIsNone(out1)
        self.assertIsNone(out2)
        joined = "\n".join(logs.output).lower()
        self.assertIn("uninitialized", joined)
        self.assertIn("run ledger init", joined)
        self.assertEqual(joined.count("uninitialized"), 1)  # once per process

    def test_enabled_initialized_proceeds(self):
        from core.ledger import migrate
        from core.ledger import model_reply_persistence as mrp
        db = str(Path(tempfile.mkdtemp()) / "real.db")
        migrate.run(db)
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            out = mrp.persist_model_reply(db_path=db, **_PERSIST_KW)
        self.assertTrue(out)  # initialized + enabled → writes a model_reply turn id


class InitCLI(unittest.TestCase):
    def test_init_creates_and_verifies_idempotent(self):
        import subprocess
        from core.ledger import migrate
        db = str(Path(tempfile.mkdtemp()) / "cli.db")
        cmd = [sys.executable, "-B", "-m", "core.ledger.init", db]
        r1 = subprocess.run(cmd, cwd=REPO_ROOT,
                            capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertIn("ledger initialized", r1.stdout.lower())
        self.assertTrue(migrate.ledger_is_initialized(db))
        # idempotent: second run still succeeds
        r2 = subprocess.run(cmd, cwd=REPO_ROOT,
                            capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertTrue(migrate.ledger_is_initialized(db))


class NoDaemonAutoInit(unittest.TestCase):
    def test_daemon_does_not_auto_initialize_the_ledger(self):
        # Initialization is a deliberate OWNER act (the CLI). The daemon must
        # never silently build the production ledger at startup. This guard locks
        # that in so a future change can't quietly start auto-initializing.
        src = (REPO_ROOT / "daemon" / "maez_daemon.py").read_text()
        self.assertNotIn("migrate.run", src)
        self.assertNotIn("core.ledger.init", src)


if __name__ == "__main__":
    unittest.main()
