# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""TDD tests for core.ledger.reconcile.

Locks the contract for the cross-DB reconciliation job per
docs/ledger/envelope-schema.md §5 (cross-DB FK contract) and §6.2 (crash
semantics + reconciliation invariants).

The module under test does not yet exist; hard import below fails
with ImportError until the implementation slice lands. That is the
TDD red state.

States covered:
  - State A: no writes landed (nothing to reconcile).
  - State B: dependent rows exist in external DBs but no ledger turns
    row references them. Reconciliation writes synthetic system_event
    ledger rows (one per orphan), restoring the FK contract.
  - State C: ledger row has was_rewritten=1 but no claims rows.
    DETECT-ONLY in this slice — claim extraction is slice 4.

Era cutoff: reconciliation requires meta.ledger_era_starts_at to be
set to a non-empty parseable float. Empty string or missing row →
RuntimeError. Pre-era external rows are filtered out (not orphans).
"""
from __future__ import annotations

import os
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_reconcile_")

from core.ledger import chain, migrate, writer  # noqa: E402
from core.ledger import reconcile  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_ledger(name: str) -> str:
    # One directory per ledger: the admission spool root derives from the
    # ledger's parent dir, so sharing a parent would share spool state
    # (and the enqueue-dedup) across unrelated tests.
    base = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}"
    base.mkdir()
    path = base / "ledger.db"
    migrate.run(str(path))
    return str(path)


def _fresh_external(name: str, table: str, ts_col: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{table}_{os.urandom(4).hex()}.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            f"CREATE TABLE {table} ("
            f" id INTEGER PRIMARY KEY AUTOINCREMENT,"
            f" {ts_col} REAL NOT NULL"
            f")"
        )
        conn.commit()
    finally:
        conn.close()
    return str(path)


def _make_external_quartet(name: str) -> dict:
    return {
        "audit_log_db_path": _fresh_external(name, "audit_log", "ts"),
        "fabrication_log_db_path": _fresh_external(
            name, "fabrication_events", "ts"
        ),
        "pending_cards_db_path": _fresh_external(
            name, "pending_cards", "created_at"
        ),
        "self_mod_dialogs_db_path": _fresh_external(
            name, "self_mod_dialogs", "created_at"
        ),
    }


def _seed_ledger_era(db_path: str, era_ts: float | None) -> None:
    """Insert/replace meta.ledger_era_starts_at.

    Pass None to set an empty-string value (the sentinel for NULL/unset
    since meta.value is NOT NULL TEXT and cannot hold a real SQL NULL).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "DELETE FROM meta WHERE key = 'ledger_era_starts_at'"
        )
        value = "" if era_ts is None else repr(float(era_ts))
        conn.execute(
            "INSERT INTO meta(key, value) VALUES "
            "('ledger_era_starts_at', ?)",
            (value,),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_ledger_era(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "DELETE FROM meta WHERE key = 'ledger_era_starts_at'"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_external_row(
    db_path: str, table: str, ts_col: str, ts: float
) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            f"INSERT INTO {table} ({ts_col}) VALUES (?)", (ts,)
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _existing_writer_with_fk(
    ledger_path: str, fk_col: str, fk_id: int,
) -> str:
    """Append a system_event turn that references an external row."""
    kwargs: dict = {fk_col: fk_id}
    w = writer.LedgerWriter(ledger_path)
    try:
        tid = w.write_turn(
            "system_event", '{"event":"seed"}',
            surface="system",
            taint_labels=["self_generated"],
            privacy_access="public",
            **kwargs,
        )
    finally:
        w.close()
    assert tid is not None
    return tid


def _all_turns(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM turns ORDER BY rowid ASC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _insert_claim_for_turn(
    db_path: str, turn_id: str, parent_chain_hash: str
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO claims("
            " turn_id, tenant_id, fact, extracted_at,"
            " extractor_version, parent_turn_chain_hash"
            ") VALUES (?, 'owner', ?, ?, 'test-v1', ?)",
            (turn_id, "synthetic claim", 0.0, parent_chain_hash),
        )
        conn.commit()
    finally:
        conn.close()


def _write_model_reply(ledger_path: str, was_rewritten: bool) -> str:
    w = writer.LedgerWriter(ledger_path)
    try:
        tid = w.write_turn(
            "model_reply", "raw text",
            model_id="qwen36-27b",
            prompt_hash="p" * 64, soul_hash="s" * 64,
            evidence_envelope={"claimable": [], "forbidden": []},
            audit_verdict={"verdict": "grounded"},
            rewritten_text="rewritten" if was_rewritten else None,
            was_rewritten=was_rewritten,
            taint_labels=["self_generated"],
            privacy_access="public",
        )
    finally:
        w.close()
    assert tid is not None
    return tid


# ============ EraGate ============

class EraGateTests(unittest.TestCase):
    def test_era_empty_value_raises(self):
        ledger = _fresh_ledger("era_empty")
        ext = _make_external_quartet("era_empty")
        _seed_ledger_era(ledger, None)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertRaises(RuntimeError):
                reconcile.reconcile(ledger, dry_run=True, **ext)

    def test_era_missing_row_raises(self):
        ledger = _fresh_ledger("era_missing")
        ext = _make_external_quartet("era_missing")
        _delete_ledger_era(ledger)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertRaises(RuntimeError):
                reconcile.reconcile(ledger, dry_run=True, **ext)

    def test_era_set_no_orphans_clean(self):
        ledger = _fresh_ledger("era_clean")
        ext = _make_external_quartet("era_clean")
        _seed_ledger_era(ledger, 1000.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(result["repairs_enqueued"], 0)
        self.assertEqual(result["ledger_era_starts_at"], 1000.0)


# ============ State A ============

class CleanReconciliationTests(unittest.TestCase):
    def test_state_a_empty_external_dbs(self):
        ledger = _fresh_ledger("clean_a")
        ext = _make_external_quartet("clean_a")
        _seed_ledger_era(ledger, 500.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        for k in ("audit_log", "fabrication_events",
                  "pending_cards", "self_mod_dialogs"):
            self.assertEqual(result["orphans_found"][k], [])
        self.assertEqual(result["repairs_enqueued"], 0)

    def test_pre_era_rows_filtered_out(self):
        ledger = _fresh_ledger("clean_pre")
        ext = _make_external_quartet("clean_pre")
        era = 5000.0
        _seed_ledger_era(ledger, era)
        _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", era - 10.0)
        _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", era)
        _seed_external_row(ext["fabrication_log_db_path"],
                           "fabrication_events", "ts", era - 1.0)
        _seed_external_row(ext["pending_cards_db_path"],
                           "pending_cards", "created_at", era - 100.0)
        _seed_external_row(ext["self_mod_dialogs_db_path"],
                           "self_mod_dialogs", "created_at", era - 1.5)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(result["repairs_enqueued"], 0)

    def test_post_era_with_matching_ledger_clean(self):
        ledger = _fresh_ledger("clean_match")
        ext = _make_external_quartet("clean_match")
        era = 100.0
        _seed_ledger_era(ledger, era)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            a = _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", era + 1.0)
            _existing_writer_with_fk(ledger, "audit_log_id", a)
            f = _seed_external_row(ext["fabrication_log_db_path"],
                                   "fabrication_events", "ts", era + 2.0)
            _existing_writer_with_fk(ledger, "fabrication_event_id", f)
            p = _seed_external_row(ext["pending_cards_db_path"],
                                   "pending_cards", "created_at", era + 3.0)
            _existing_writer_with_fk(ledger, "pending_card_id", p)
            s = _seed_external_row(ext["self_mod_dialogs_db_path"],
                                   "self_mod_dialogs", "created_at", era + 4.0)
            _existing_writer_with_fk(ledger, "self_mod_dialog_id", s)
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(result["repairs_enqueued"], 0)


# ============ State B detect ============

class OrphanDetectionTests(unittest.TestCase):
    def test_single_audit_log_orphan(self):
        ledger = _fresh_ledger("orphan_audit")
        ext = _make_external_quartet("orphan_audit")
        _seed_ledger_era(ledger, 10.0)
        orphan_id = _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 11.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "orphans_found")
        self.assertEqual(result["orphans_found"]["audit_log"], [orphan_id])
        self.assertEqual(result["repairs_enqueued"], 0)

    def test_one_orphan_per_db(self):
        ledger = _fresh_ledger("orphan_each")
        ext = _make_external_quartet("orphan_each")
        _seed_ledger_era(ledger, 0.0)
        a = _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        f = _seed_external_row(ext["fabrication_log_db_path"], "fabrication_events", "ts", 2.0)
        p = _seed_external_row(ext["pending_cards_db_path"], "pending_cards", "created_at", 3.0)
        s = _seed_external_row(ext["self_mod_dialogs_db_path"], "self_mod_dialogs", "created_at", 4.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "orphans_found")
        self.assertEqual(result["orphans_found"]["audit_log"], [a])
        self.assertEqual(result["orphans_found"]["fabrication_events"], [f])
        self.assertEqual(result["orphans_found"]["pending_cards"], [p])
        self.assertEqual(result["orphans_found"]["self_mod_dialogs"], [s])
        self.assertEqual(result["repairs_enqueued"], 0)


# ============ State B repair (owner-client since 2026-08-24) ============

class OrphanRepairTests(unittest.TestCase):
    """Grok overturn 2 (council 2026-08-24): reconcile --apply is an
    OWNER-CLIENT — repairs are ordinary schema-legal system_event rows
    with FK kwargs and no authority, so they enqueue through the live
    owner's admission spool instead of constructing a direct writer
    (which would refuse against a live daemon's latch, or worse, take
    the latch while the daemon is down)."""

    def setUp(self):
        from core.ledger import owner as ledger_owner

        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def _drain(self, ledger: str) -> None:
        from core.ledger import owner as ledger_owner
        from core.ledger import spool

        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            spool.drain_once(spool.default_spool_root(ledger), ledger)

    def test_apply_enqueues_never_writes_directly(self):
        from core.ledger import spool

        ledger = _fresh_ledger("repair_audit")
        ext = _make_external_quartet("repair_audit")
        _seed_ledger_era(ledger, 0.0)
        orphan = _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(result["verdict"], "repairs_enqueued")
        self.assertEqual(result["repairs_enqueued"], 1)
        rows = _all_turns(ledger)
        self.assertEqual(
            [r for r in rows if r["turn_id"] != "genesis"], [],
            "apply must not write the ledger — the owner drains",
        )
        pending = (
            Path(spool.default_spool_root(ledger)) / "reconcile" / "pending"
        )
        envs = [json.loads(p.read_text()) for p in pending.iterdir()
                if not p.name.startswith(".tmp-")]
        self.assertEqual(len(envs), 1)
        self.assertEqual(envs[0]["kwargs"]["audit_log_id"], orphan)

        # After the owner drains, the repair row is real and chain-good.
        self._drain(ledger)
        rows = _all_turns(ledger)
        synthetic = [r for r in rows
                     if r["turn_kind"] == "system_event"
                     and r["audit_log_id"] == orphan
                     and r["turn_id"] != "genesis"]
        self.assertEqual(len(synthetic), 1)
        self.assertEqual(synthetic[0]["raw_surface"], "ledger_reconciliation")
        payload = json.loads(synthetic[0]["raw_text"])
        self.assertEqual(payload["event"], "orphan_dependent_row")
        self.assertEqual(payload["source_db"], "audit_log")
        self.assertEqual(payload["source_table"], "audit_log")
        self.assertEqual(payload["source_id"], orphan)
        self.assertEqual(payload["source_ts"], 1.0)
        self.assertEqual(
            payload["reason"],
            "ledger_write_missing_after_crash_or_legacy_write",
        )
        self.assertEqual(chain.verify_chain(rows), [])

    def test_apply_enqueues_multiple_orphans(self):
        ledger = _fresh_ledger("repair_multi")
        ext = _make_external_quartet("repair_multi")
        _seed_ledger_era(ledger, 0.0)
        a = _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        f = _seed_external_row(ext["fabrication_log_db_path"], "fabrication_events", "ts", 2.0)
        p = _seed_external_row(ext["pending_cards_db_path"], "pending_cards", "created_at", 3.0)
        s = _seed_external_row(ext["self_mod_dialogs_db_path"], "self_mod_dialogs", "created_at", 4.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(result["verdict"], "repairs_enqueued")
        self.assertEqual(result["repairs_enqueued"], 4)
        self._drain(ledger)
        rows = _all_turns(ledger)
        self.assertEqual(len([r for r in rows if r["audit_log_id"] == a]), 1)
        self.assertEqual(len([r for r in rows if r["fabrication_event_id"] == f]), 1)
        self.assertEqual(len([r for r in rows if r["pending_card_id"] == p]), 1)
        self.assertEqual(len([r for r in rows if r["self_mod_dialog_id"] == s]), 1)
        self.assertEqual(chain.verify_chain(rows), [])

    def test_idempotent_across_the_enqueue_drain_window(self):
        """A second apply BEFORE the owner drains must not double-enqueue
        (the orphan census cannot see queued repairs — the spool can)."""
        ledger = _fresh_ledger("repair_idem")
        ext = _make_external_quartet("repair_idem")
        _seed_ledger_era(ledger, 0.0)
        _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        _seed_external_row(ext["fabrication_log_db_path"], "fabrication_events", "ts", 2.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            first = reconcile.reconcile(ledger, dry_run=False, **ext)
            self.assertEqual(first["repairs_enqueued"], 2)
            second = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(second["repairs_enqueued"], 0)
        self.assertEqual(second["verdict"], "repairs_pending_drain")
        self._drain(ledger)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            third = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(third["repairs_enqueued"], 0)
        self.assertEqual(third["verdict"], "clean")
        rows = [r for r in _all_turns(ledger) if r["turn_id"] != "genesis"]
        self.assertEqual(len(rows), 2, "exactly one repair row per orphan")


# ============ State C detect ============

class StateCDetectionTests(unittest.TestCase):
    def test_was_rewritten_with_no_claims(self):
        ledger = _fresh_ledger("state_c_orphan")
        ext = _make_external_quartet("state_c_orphan")
        _seed_ledger_era(ledger, 0.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = _write_model_reply(ledger, was_rewritten=True)
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertIn(tid, result["state_c_turns"])

    def test_was_rewritten_zero_not_reported(self):
        ledger = _fresh_ledger("state_c_zero")
        ext = _make_external_quartet("state_c_zero")
        _seed_ledger_era(ledger, 0.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = _write_model_reply(ledger, was_rewritten=False)
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertNotIn(tid, result["state_c_turns"])

    def test_was_rewritten_with_claim(self):
        ledger = _fresh_ledger("state_c_satisfied")
        ext = _make_external_quartet("state_c_satisfied")
        _seed_ledger_era(ledger, 0.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = _write_model_reply(ledger, was_rewritten=True)
            rows = _all_turns(ledger)
            row = next(r for r in rows if r["turn_id"] == tid)
            _insert_claim_for_turn(ledger, tid, row["chain_hash"])
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertNotIn(tid, result["state_c_turns"])


# ============ Writes-flag gate ============

class WritesFlagGateTests(unittest.TestCase):
    def test_apply_without_flag_raises(self):
        ledger = _fresh_ledger("gate_apply_off")
        ext = _make_external_quartet("gate_apply_off")
        _seed_ledger_era(ledger, 0.0)
        _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        scrubbed = {k: v for k, v in os.environ.items()
                    if k != "MAEZ_LEDGER_WRITES"}
        scrubbed["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, scrubbed, clear=True):
            with self.assertRaises(RuntimeError):
                reconcile.reconcile(ledger, dry_run=False, **ext)

    def test_dry_run_without_flag_succeeds(self):
        ledger = _fresh_ledger("gate_dry_off")
        ext = _make_external_quartet("gate_dry_off")
        _seed_ledger_era(ledger, 0.0)
        scrubbed = {k: v for k, v in os.environ.items()
                    if k != "MAEZ_LEDGER_WRITES"}
        scrubbed["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, scrubbed, clear=True):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(result["repairs_enqueued"], 0)


# ============ Default + chain ============

class DefaultDryRunTests(unittest.TestCase):
    def test_dry_run_is_default(self):
        ledger = _fresh_ledger("default_dry")
        ext = _make_external_quartet("default_dry")
        _seed_ledger_era(ledger, 0.0)
        _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        before = _all_turns(ledger)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, **ext)  # dry_run default
        after = _all_turns(ledger)
        self.assertEqual(len(before), len(after))
        self.assertEqual(result["repairs_enqueued"], 0)
        self.assertEqual(result["verdict"], "orphans_found")


class ChainIntegrityAcrossReconciliationTests(unittest.TestCase):
    def test_chain_clean_before_and_after_repair(self):
        ledger = _fresh_ledger("chain_pre_post")
        ext = _make_external_quartet("chain_pre_post")
        _seed_ledger_era(ledger, 0.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(ledger)
            try:
                for i in range(5):
                    w.write_turn(
                        "user_message",
                        f"pre-{i}",
                        taint_labels=["owner_utterance"],
                        privacy_access="public",
                    )
            finally:
                w.close()
        before_rows = _all_turns(ledger)
        self.assertEqual(chain.verify_chain(before_rows), [])
        before_count = len(before_rows)
        _seed_external_row(ext["audit_log_db_path"], "audit_log", "ts", 1.0)
        _seed_external_row(ext["fabrication_log_db_path"], "fabrication_events", "ts", 2.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(result["repairs_enqueued"], 2)
        self.assertEqual(
            len(_all_turns(ledger)), before_count,
            "apply enqueues; only the owner's drain commits",
        )
        # Drain as the owner: the repairs join the chain cleanly.
        from core.ledger import owner as ledger_owner
        from core.ledger import spool

        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            spool.drain_once(spool.default_spool_root(ledger), ledger)
        after_rows = _all_turns(ledger)
        self.assertEqual(len(after_rows), before_count + 2)
        appended = after_rows[before_count:]
        for r in appended:
            self.assertEqual(r["turn_kind"], "system_event")
        self.assertEqual(chain.verify_chain(after_rows), [])


class MissingExternalDBTests(unittest.TestCase):
    """Missing external DB or missing table → treated as State A."""

    def test_missing_audit_log_db_treated_as_empty(self):
        ledger = _fresh_ledger("missing_audit")
        # Don't create audit_log.db at all.
        ext = _make_external_quartet("missing_audit")
        nonexistent = str(Path(_TEST_DB_DIR) / "does_not_exist.db")
        ext["audit_log_db_path"] = nonexistent
        _seed_ledger_era(ledger, 0.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(result["orphans_found"]["audit_log"], [])

    def test_missing_table_in_existing_db_treated_as_empty(self):
        ledger = _fresh_ledger("missing_table")
        # Create an external DB file but with NO table (subsystem
        # hasn't initialized yet — brand new install).
        empty_audit = str(Path(_TEST_DB_DIR) / f"empty_audit_{os.urandom(4).hex()}.db")
        sqlite3.connect(empty_audit).close()  # creates empty DB file
        ext = _make_external_quartet("missing_table")
        ext["audit_log_db_path"] = empty_audit
        _seed_ledger_era(ledger, 0.0)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        self.assertEqual(result["verdict"], "clean")
        self.assertEqual(result["orphans_found"]["audit_log"], [])


class LowEraGuardTests(unittest.TestCase):
    """Refuses --apply when era is implausibly old AND many orphans exist."""

    def test_low_era_with_many_orphans_apply_raises(self):
        ledger = _fresh_ledger("low_era_many")
        ext = _make_external_quartet("low_era_many")
        _seed_ledger_era(ledger, 0.0)  # epoch — definitely pre-2001
        # 51 orphans (one over the threshold of 50)
        for i in range(51):
            _seed_external_row(
                ext["audit_log_db_path"], "audit_log", "ts", float(i + 1)
            )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertRaises(RuntimeError) as ctx:
                reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertIn("low_era", str(ctx.exception).lower().replace(" ", "_") + " "
                      + str(ctx.exception).lower())

    def test_low_era_with_few_orphans_apply_succeeds(self):
        """Below the orphan threshold, low era is allowed (testing scenario)."""
        ledger = _fresh_ledger("low_era_few")
        ext = _make_external_quartet("low_era_few")
        _seed_ledger_era(ledger, 0.0)
        _seed_external_row(
            ext["audit_log_db_path"], "audit_log", "ts", 1.0
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(result["verdict"], "repairs_enqueued")
        self.assertEqual(result["repairs_enqueued"], 1)

    def test_low_era_force_override_works(self):
        """force_low_era=True bypasses the guard."""
        ledger = _fresh_ledger("low_era_force")
        ext = _make_external_quartet("low_era_force")
        _seed_ledger_era(ledger, 0.0)
        for i in range(51):
            _seed_external_row(
                ext["audit_log_db_path"], "audit_log", "ts", float(i + 1)
            )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(
                ledger, dry_run=False, force_low_era=True, **ext
            )
        self.assertEqual(result["verdict"], "repairs_enqueued")
        self.assertEqual(result["repairs_enqueued"], 51)

    def test_high_era_no_guard(self):
        """Realistic era (>= 2001) doesn't trigger the guard."""
        ledger = _fresh_ledger("high_era")
        ext = _make_external_quartet("high_era")
        _seed_ledger_era(ledger, 1.7e9)  # ~2023
        for i in range(51):
            _seed_external_row(
                ext["audit_log_db_path"], "audit_log", "ts", 1.7e9 + i + 1
            )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=False, **ext)
        self.assertEqual(result["verdict"], "repairs_enqueued")
        self.assertEqual(result["repairs_enqueued"], 51)

    def test_low_era_dry_run_unaffected(self):
        """Guard only applies to --apply mode; dry-run always works."""
        ledger = _fresh_ledger("low_era_dry")
        ext = _make_external_quartet("low_era_dry")
        _seed_ledger_era(ledger, 0.0)
        for i in range(51):
            _seed_external_row(
                ext["audit_log_db_path"], "audit_log", "ts", float(i + 1)
            )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            result = reconcile.reconcile(ledger, dry_run=True, **ext)
        # Should NOT raise; dry-run reports orphans without writing.
        self.assertEqual(result["verdict"], "orphans_found")
        self.assertEqual(result["repairs_enqueued"], 0)
        self.assertEqual(len(result["orphans_found"]["audit_log"]), 51)


if __name__ == "__main__":
    unittest.main()
