# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""TDD tests for scripts/reconcile_ledger.py.

The script does not exist yet; subprocess invocation will fail until
it lands. Pins the CLI contract per docs/ledger/envelope-schema.md §6.2:

  - default is dry-run (no writes)
  - --apply requires MAEZ_LEDGER_WRITES=1
  - exit codes: 0 clean, 1 orphans-in-dry-run, 2 error, 3 state_c warn
  - --json single object output, --quiet silences both streams
  - era gate: meta.ledger_era_starts_at must be set and parseable
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["MAEZ_TEST_MODE"] = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "reconcile_ledger.py"
ERA_TS = 1_700_000_000.0


def _seed_ledger_via_migrate(db_path: Path, *, era: float | None) -> None:
    """Use real migrate.run, then set the era. Pass None for empty era."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from core.ledger import migrate
    finally:
        sys.path.pop(0)
    migrate.run(str(db_path))
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM meta WHERE key='ledger_era_starts_at'")
        value = "" if era is None else repr(float(era))
        conn.execute(
            "INSERT INTO meta(key, value) VALUES "
            "('ledger_era_starts_at', ?)", (value,))
        conn.commit()
    finally:
        conn.close()


def _delete_era(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM meta WHERE key='ledger_era_starts_at'")
        conn.commit()
    finally:
        conn.close()


def _make_external(path: Path, table: str, ts_col: str) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            f"CREATE TABLE {table} ("
            f" id INTEGER PRIMARY KEY AUTOINCREMENT,"
            f" {ts_col} REAL NOT NULL)"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_external_row(path: Path, table: str, ts_col: str, ts: float) -> int:
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.execute(
            f"INSERT INTO {table} ({ts_col}) VALUES (?)", (ts,))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _count_turns(db_path: Path) -> int:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    finally:
        conn.close()


def _run(args: list[str], *, env_extra: dict | None = None,
         timeout: int = 30) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MAEZ_TEST_MODE"] = "1"
    env.pop("MAEZ_LEDGER_WRITES", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True, text=True, env=env, timeout=timeout,
    )


class _Tmp(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="maez_test_reconcile_cli_")
        self.tmpdir = Path(self._tmp)
        self.ledger_db = self.tmpdir / "ledger.db"
        self.audit_db = self.tmpdir / "audit_log.db"
        self.fab_db = self.tmpdir / "fabrication_log.db"
        self.cards_db = self.tmpdir / "pending_cards.db"
        self.smod_db = self.tmpdir / "self_mod_dialogs.db"

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _full_args(self, *extras: str) -> list[str]:
        return [
            "--audit-log", str(self.audit_db),
            "--fabrication-log", str(self.fab_db),
            "--pending-cards", str(self.cards_db),
            "--self-mod-dialogs", str(self.smod_db),
            *extras,
            str(self.ledger_db),
        ]

    def _seed_clean_externals(self) -> None:
        _make_external(self.audit_db, "audit_log", "ts")
        _make_external(self.fab_db, "fabrication_events", "ts")
        _make_external(self.cards_db, "pending_cards", "created_at")
        _make_external(self.smod_db, "self_mod_dialogs", "created_at")


class CLIBasicsTests(_Tmp):
    def test_help_exits_zero(self):
        res = _run(["--help"])
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertIn("usage", res.stdout.lower())

    def test_missing_positional_exits_2(self):
        res = _run([])
        self.assertEqual(res.returncode, 2)

    def test_nonexistent_ledger_exits_2(self):
        res = _run([str(self.tmpdir / "does_not_exist.db")])
        self.assertEqual(res.returncode, 2)


class DryRunDefaultTests(_Tmp):
    def test_clean_db_exits_0(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        before = _count_turns(self.ledger_db)
        res = _run(self._full_args())
        self.assertEqual(res.returncode, 0,
            msg=f"stderr={res.stderr!r} stdout={res.stdout!r}")
        self.assertEqual(_count_turns(self.ledger_db), before)

    def test_orphans_dry_run_exits_1(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        _seed_external_row(self.audit_db, "audit_log", "ts", ERA_TS + 1.0)
        before = _count_turns(self.ledger_db)
        res = _run(self._full_args())
        self.assertEqual(res.returncode, 1,
            msg=f"stderr={res.stderr!r} stdout={res.stdout!r}")
        self.assertIn("orphan", (res.stdout + res.stderr).lower())
        self.assertEqual(_count_turns(self.ledger_db), before,
            "dry-run must not write")


class ApplyModeTests(_Tmp):
    def test_apply_enqueues_through_the_owner_never_writes_directly(self):
        # Owner-client contract (council 2026-08-24, Grok overturn 2):
        # --apply enqueues ordinary system_event repairs through the
        # admission spool; only the owner's drainer touches SQLite.
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        _seed_external_row(self.audit_db, "audit_log", "ts", ERA_TS + 1.0)
        _seed_external_row(self.audit_db, "audit_log", "ts", ERA_TS + 2.0)
        before = _count_turns(self.ledger_db)
        res = _run(self._full_args("--apply"),
                   env_extra={"MAEZ_LEDGER_WRITES": "1"})
        self.assertEqual(res.returncode, 0,
            msg=f"stderr={res.stderr!r} stdout={res.stdout!r}")
        self.assertEqual(_count_turns(self.ledger_db), before,
            "--apply must not open the ledger; the owner drains")
        from core.ledger import spool

        pending = (Path(spool.default_spool_root(self.ledger_db))
                   / "reconcile" / "pending")
        envelopes = [p for p in pending.iterdir()
                     if not p.name.startswith(".tmp-")]
        self.assertEqual(len(envelopes), 2)
        # Orphans remain visible to a dry-run until the owner drains.
        res_pending = _run(self._full_args())
        self.assertEqual(res_pending.returncode, 1)
        # Drain as the owner, then a dry-run comes back clean.
        from unittest.mock import patch as _patch

        from core.ledger import owner as ledger_owner

        ledger_owner._reset_for_tests()
        try:
            with _patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                ledger_owner.claim_ownership()
                spool.drain_once(
                    spool.default_spool_root(self.ledger_db), self.ledger_db
                )
        finally:
            ledger_owner._reset_for_tests()
        self.assertEqual(_count_turns(self.ledger_db), before + 2)
        res2 = _run(self._full_args())
        self.assertEqual(res2.returncode, 0,
            msg=f"stderr={res2.stderr!r} stdout={res2.stdout!r}")

    def test_apply_without_writes_flag_exits_2(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        _seed_external_row(self.audit_db, "audit_log", "ts", ERA_TS + 1.0)
        before = _count_turns(self.ledger_db)
        res = _run(self._full_args("--apply"))
        self.assertEqual(res.returncode, 2,
            msg=f"stderr={res.stderr!r} stdout={res.stdout!r}")
        self.assertIn("maez_ledger_writes", (res.stdout + res.stderr).lower())
        self.assertEqual(_count_turns(self.ledger_db), before)


class EraGateTests(_Tmp):
    def test_era_empty_exits_2(self):
        _seed_ledger_via_migrate(self.ledger_db, era=None)
        self._seed_clean_externals()
        res = _run(self._full_args())
        self.assertEqual(res.returncode, 2)
        self.assertIn("era", (res.stdout + res.stderr).lower())

    def test_era_missing_exits_2(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        _delete_era(self.ledger_db)
        self._seed_clean_externals()
        res = _run(self._full_args())
        self.assertEqual(res.returncode, 2)
        self.assertIn("era", (res.stdout + res.stderr).lower())


class OutputModeTests(_Tmp):
    def test_json_mode_emits_object(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        res = _run(self._full_args("--json"))
        self.assertEqual(res.returncode, 0,
            msg=f"stderr={res.stderr!r}")
        payload = json.loads(res.stdout)
        self.assertIsInstance(payload, dict)
        self.assertIn("verdict", payload)

    def test_quiet_silences_output(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        res = _run(self._full_args("--quiet"))
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, "")
        self.assertEqual(res.stderr, "")


class StateCTests(_Tmp):
    def test_state_c_exits_3(self):
        _seed_ledger_via_migrate(self.ledger_db, era=ERA_TS)
        self._seed_clean_externals()
        # Direct INSERT with was_rewritten=1 to construct State C.
        # Real production rows would come from the writer; here we
        # just need the shape.
        conn = sqlite3.connect(str(self.ledger_db))
        try:
            head = conn.execute(
                "SELECT value FROM meta WHERE key='last_chain_hash'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO turns ("
                "turn_id, tenant_id, timestamp, schema_version, turn_kind, "
                "surface, raw_text, rewritten_text, was_rewritten, "
                "taint_labels_json, privacy_access, chain_position, "
                "prev_chain_hash, chain_hash) VALUES (?, 'owner', ?, 1, "
                "'model_reply', 'chat', ?, ?, 1, ?, 'public', 1, ?, ?)",
                ("turn_state_c", ERA_TS + 100.0, "raw", "rewritten",
                 '["self_generated"]',
                 head, "b" * 64),
            )
            conn.execute(
                "UPDATE meta SET value=? WHERE key='last_chain_hash'",
                ("b" * 64,),
            )
            conn.commit()
        finally:
            conn.close()
        res = _run(self._full_args())
        self.assertEqual(res.returncode, 3,
            msg=f"stderr={res.stderr!r} stdout={res.stdout!r}")
        self.assertIn("state_c", (res.stdout + res.stderr).lower())


if __name__ == "__main__":
    unittest.main()
