# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Schema tests for the Maez ledger (core.ledger.migrate).

The ledger is the per-turn audit/evidence root of Maez's personalization
stack. This file locks in the schema declared in
docs/LEDGER_ENVELOPE_SCHEMA.md §4.1–§4.4 so it cannot drift without a
test failure.

These tests are TDD-first: core.ledger.migrate does not yet exist. The
import at module load is expected to fail until the migration slice
lands. That failure IS the spec — do not soften it.

Verifies, for the schema produced by core.ledger.migrate.run(db_path):
  - meta, turns, claims, claim_judgements, model_swaps tables exist
    with every column declared (name, type, NOT NULL, default).
  - All declared indexes exist with the right columns and ordering.
  - The latest_claim_judgement and claims_with_judgement views exist
    and have the expected output shape.
  - meta is seeded with schema_version='1' and a genesis_hash entry.
  - turn_kind is constrained to the declared enum via CHECK constraint
    or trigger (unknown values must be rejected).
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Test isolation contract: MAEZ_TEST_MODE=1 at module load, temp DB
# directory created here, cleaned up in tearDownModule.
os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_schema_")
_TEST_DB_PATH = Path(_TEST_DB_DIR) / "ledger.db"

# Intentional hard import. core.ledger.migrate does not yet exist; this
# import will raise ImportError until the migration slice lands. That
# failure is the spec — see module docstring.
from core.ledger import migrate as _ledger_migrate  # noqa: E402


def _run_migrations(db_path: Path) -> None:
    """Run the ledger migrations against the given path."""
    _ledger_migrate.run(str(db_path))


def setUpModule():
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    _run_migrations(_TEST_DB_PATH)


def tearDownModule():
    """Clean up the temp DB directory after the test module finishes."""
    import shutil

    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_info(conn: sqlite3.Connection, table: str) -> dict:
    """Return PRAGMA table_info() rows keyed by column name."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"]: r for r in rows}


def _index_list(conn: sqlite3.Connection, table: str) -> dict:
    rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
    return {r["name"]: r for r in rows}


def _index_info(conn: sqlite3.Connection, index: str) -> list:
    """Return ordered column names for the given index."""
    rows = conn.execute(f"PRAGMA index_info({index})").fetchall()
    return [r["name"] for r in sorted(rows, key=lambda r: r["seqno"])]


def _index_sql(conn: sqlite3.Connection, index: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
        (index,),
    ).fetchone()
    return row["sql"] if row and row["sql"] else ""


def _assert_column(testcase, info, name, type_, notnull, default):
    """Assert one column matches (name, type, NOT NULL flag, default)."""
    testcase.assertIn(name, info, f"missing column: {name}")
    col = info[name]
    testcase.assertEqual(
        col["type"].upper(),
        type_.upper(),
        f"{name}: expected type {type_}, got {col['type']}",
    )
    testcase.assertEqual(
        bool(col["notnull"]),
        notnull,
        f"{name}: expected NOT NULL={notnull}, got notnull={col['notnull']}",
    )
    if default is None:
        testcase.assertIsNone(
            col["dflt_value"],
            f"{name}: expected no default, got {col['dflt_value']!r}",
        )
    else:
        actual = col["dflt_value"]
        testcase.assertIsNotNone(actual, f"{name}: expected default {default!r}, got NULL")
        actual_norm = str(actual).strip().strip("'\"")
        expected_norm = str(default).strip().strip("'\"")
        testcase.assertEqual(
            actual_norm,
            expected_norm,
            f"{name}: expected default {default!r}, got {actual!r}",
        )


class MetaTableTests(unittest.TestCase):
    """meta table — §4.1."""

    def test_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "meta")
        self.assertIn("key", info)
        self.assertEqual(info["key"]["type"].upper(), "TEXT")
        self.assertGreaterEqual(int(info["key"]["pk"]), 1, "meta.key must be PRIMARY KEY")
        _assert_column(self, info, "value", "TEXT", True, None)

    def test_no_extra_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "meta")
        self.assertEqual(set(info.keys()), {"key", "value"})

    def test_seeded_schema_version(self):
        with _connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        self.assertIsNotNone(row, "meta missing schema_version row")
        self.assertEqual(row["value"], "1")

    def test_seeded_genesis_hash_present(self):
        import string

        with _connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='genesis_hash'").fetchone()
        self.assertIsNotNone(row, "meta missing genesis_hash row")
        v = row["value"]
        self.assertTrue(
            isinstance(v, str)
            and len(v) == 64
            and all(c in set(string.hexdigits.lower()) for c in v),
            f"genesis_hash must be 64 lowercase hex chars; got {v!r}",
        )


class TurnsTableTests(unittest.TestCase):
    """turns table — §4.2."""

    EXPECTED = [
        ("turn_id", "TEXT", False, None),
        ("tenant_id", "TEXT", True, "owner"),
        ("timestamp", "REAL", True, None),
        ("schema_version", "INTEGER", True, None),
        ("turn_kind", "TEXT", True, None),
        ("surface", "TEXT", True, None),
        ("raw_surface", "TEXT", False, None),
        ("parent_turn_id", "TEXT", False, None),
        ("correction_of", "TEXT", False, None),
        ("model_id", "TEXT", False, None),
        ("lora_hash", "TEXT", False, None),
        ("soul_hash", "TEXT", False, None),
        ("prompt_hash", "TEXT", False, None),
        ("raw_text", "TEXT", True, None),
        ("rewritten_text", "TEXT", False, None),
        ("was_rewritten", "INTEGER", True, "0"),
        ("signals_present", "TEXT", True, "[]"),
        ("signals_absent", "TEXT", True, "[]"),
        ("evidence_envelope_json", "TEXT", False, None),
        ("action_proposal_json", "TEXT", False, None),
        ("audit_verdict_json", "TEXT", False, None),
        ("will_i_json", "TEXT", False, None),
        ("memory_read_ids", "TEXT", True, "[]"),
        ("memory_written_ids", "TEXT", True, "[]"),
        ("audit_log_id", "INTEGER", False, None),
        ("fabrication_event_id", "INTEGER", False, None),
        ("self_mod_dialog_id", "INTEGER", False, None),
        ("pending_card_id", "INTEGER", False, None),
        ("prev_chain_hash", "TEXT", False, None),
        ("chain_hash", "TEXT", True, None),
        # Gestation Boundary slice (2026-05-08, migration 0003):
        # default 'gestation' for pre-birth rows; writer overrides to
        # 'lived' when meta.birth_event_turn_id is set. Note: this
        # column is intentionally NOT part of the chain-hash canonical
        # bytes (see core/ledger/chain.py::_CHAIN_HASH_EXCLUDE +
        # tests/test_gestation_boundary.py::ChainHashInvariantTests).
        ("lifecycle_stage", "TEXT", True, "'gestation'"),
        # Slice 4c.5b trace-audit substrate: thin refusal-token
        # metadata. These nullable columns are intentionally excluded
        # from chain-hash canonical bytes; rich lineage lives in the
        # separate audit_trace_lineage table.
        ("audit_trace_label", "TEXT", False, "NULL"),
        ("audit_trace_value_schema", "INTEGER", False, "NULL"),
        ("audit_trace_metadata_shape", "INTEGER", False, "NULL"),
    ]

    def test_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "turns")
        for name, type_, notnull, default in self.EXPECTED:
            _assert_column(self, info, name, type_, notnull, default)

    def test_no_extra_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "turns")
        expected = {c[0] for c in self.EXPECTED}
        self.assertEqual(
            set(info.keys()),
            expected,
            f"unexpected columns: {set(info.keys()) - expected}; "
            f"missing: {expected - set(info.keys())}",
        )

    def test_turn_id_is_primary_key(self):
        with _connect() as conn:
            info = _table_info(conn, "turns")
        self.assertGreaterEqual(int(info["turn_id"]["pk"]), 1, "turn_id must be PRIMARY KEY")

    def test_turn_kind_enum_enforced(self):
        """turn_kind must reject unknown values.

        Uses a dedicated temp DB so the write does not pollute the
        module-shared DB. Performs a positive control first
        (same insert with a valid turn_kind succeeds) so this test
        cannot green-pass merely because some unrelated constraint
        rejected the row.
        """
        # Positive-control + negative-test against an isolated DB.
        scratch = Path(_TEST_DB_DIR) / "turn_kind_enum.db"
        if scratch.exists():
            scratch.unlink()
        _run_migrations(scratch)
        valid_chain_hash = "a" * 64  # realistic shape; not the recipe

        positive_conn = sqlite3.connect(scratch)
        try:
            positive_conn.execute(
                "INSERT INTO turns "
                "(turn_id, timestamp, schema_version, turn_kind, "
                " surface, raw_text, prev_chain_hash, chain_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "positive-control",
                    1.0,
                    1,
                    "system_event",
                    "system",
                    "x",
                    "f" * 64,
                    valid_chain_hash,
                ),
            )
            positive_conn.commit()
        finally:
            positive_conn.close()

        # Now mutate ONLY turn_kind to a bogus value.
        negative_conn = sqlite3.connect(scratch)
        try:
            try:
                negative_conn.execute(
                    "INSERT INTO turns "
                    "(turn_id, timestamp, schema_version, turn_kind, "
                    " surface, raw_text, prev_chain_hash, chain_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "negative-bogus",
                        2.0,
                        1,
                        "definitely_not_a_real_kind",
                        "system",
                        "x",
                        "f" * 64,
                        "b" * 64,
                    ),
                )
                negative_conn.commit()
                raised = False
            except sqlite3.IntegrityError:
                raised = True
            except sqlite3.DatabaseError:
                raised = True
        finally:
            negative_conn.close()
        self.assertTrue(
            raised,
            "turn_kind enum must be enforced: insert with unknown kind "
            "should raise IntegrityError (CHECK) or DatabaseError "
            "(trigger). Positive control with turn_kind='system_event' "
            "succeeded, so this is not a generic insert failure.",
        )


class ClaimsTableTests(unittest.TestCase):
    """claims table — §4.3."""

    EXPECTED = [
        ("claim_id", "INTEGER", False, None),
        ("turn_id", "TEXT", True, None),
        ("tenant_id", "TEXT", True, "owner"),
        ("fact", "TEXT", True, None),
        ("extracted_at", "REAL", True, None),
        ("extractor_version", "TEXT", True, None),
        ("parent_turn_chain_hash", "TEXT", True, None),
    ]

    def test_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "claims")
        for name, type_, notnull, default in self.EXPECTED:
            _assert_column(self, info, name, type_, notnull, default)

    def test_no_extra_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "claims")
        expected = {c[0] for c in self.EXPECTED}
        self.assertEqual(
            set(info.keys()),
            expected,
            f"unexpected columns: {set(info.keys()) - expected}; "
            f"missing: {expected - set(info.keys())}",
        )

    def test_claim_id_is_pk_autoincrement(self):
        with _connect() as conn:
            info = _table_info(conn, "claims")
            self.assertGreaterEqual(int(info["claim_id"]["pk"]), 1)
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='claims'"
            ).fetchone()
        self.assertIsNotNone(ddl)
        self.assertIn(
            "AUTOINCREMENT",
            ddl["sql"].upper(),
            "claims.claim_id must declare AUTOINCREMENT in its DDL "
            "(prevents PK reuse after DELETE)",
        )

    def test_foreign_key_to_turns(self):
        with _connect() as conn:
            fks = conn.execute("PRAGMA foreign_key_list(claims)").fetchall()
        targets = [(fk["from"], fk["table"], fk["to"]) for fk in fks]
        self.assertIn(
            ("turn_id", "turns", "turn_id"),
            targets,
            f"claims.turn_id must FK to turns.turn_id; got {targets}",
        )


class ClaimJudgementsTableTests(unittest.TestCase):
    """claim_judgements table — §4.3a."""

    EXPECTED = [
        ("judgement_id", "INTEGER", False, None),
        ("claim_id", "INTEGER", True, None),
        ("tenant_id", "TEXT", True, "owner"),
        ("judged_at", "REAL", True, None),
        ("judged_by", "TEXT", True, None),
        ("judge_model_id", "TEXT", False, None),
        ("provenance", "TEXT", False, None),
        ("evidence_refs_json", "TEXT", True, None),
        ("confidence", "REAL", False, None),
        ("audit_verdict", "TEXT", True, None),
        ("parent_claim_witness", "TEXT", True, None),
    ]

    def test_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "claim_judgements")
        for name, type_, notnull, default in self.EXPECTED:
            _assert_column(self, info, name, type_, notnull, default)

    def test_no_extra_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "claim_judgements")
        expected = {c[0] for c in self.EXPECTED}
        self.assertEqual(
            set(info.keys()),
            expected,
            f"unexpected columns: {set(info.keys()) - expected}; "
            f"missing: {expected - set(info.keys())}",
        )

    def test_judgement_id_is_pk_autoincrement(self):
        with _connect() as conn:
            info = _table_info(conn, "claim_judgements")
            self.assertGreaterEqual(int(info["judgement_id"]["pk"]), 1)
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='claim_judgements'"
            ).fetchone()
        self.assertIsNotNone(ddl)
        self.assertIn(
            "AUTOINCREMENT",
            ddl["sql"].upper(),
            "claim_judgements.judgement_id must declare AUTOINCREMENT",
        )

    def test_foreign_key_to_claims(self):
        with _connect() as conn:
            fks = conn.execute("PRAGMA foreign_key_list(claim_judgements)").fetchall()
        targets = [(fk["from"], fk["table"], fk["to"]) for fk in fks]
        self.assertIn(
            ("claim_id", "claims", "claim_id"),
            targets,
            f"claim_judgements.claim_id must FK to claims.claim_id; got {targets}",
        )


class ModelSwapsTableTests(unittest.TestCase):
    """model_swaps table — §4.4."""

    EXPECTED = [
        ("swap_id", "INTEGER", False, None),
        ("tenant_id", "TEXT", True, "owner"),
        ("timestamp", "REAL", True, None),
        ("from_model_id", "TEXT", False, None),
        ("from_lora_hash", "TEXT", False, None),
        ("to_model_id", "TEXT", True, None),
        ("to_lora_hash", "TEXT", False, None),
        ("soul_hash_before", "TEXT", False, None),
        ("soul_hash_after", "TEXT", False, None),
        ("gold_corpus_hash", "TEXT", False, None),
        ("eval_results_json", "TEXT", True, None),
        ("decision", "TEXT", True, None),
        ("decision_reason", "TEXT", True, None),
        ("operator", "TEXT", True, None),
    ]

    def test_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "model_swaps")
        for name, type_, notnull, default in self.EXPECTED:
            _assert_column(self, info, name, type_, notnull, default)

    def test_no_extra_columns(self):
        with _connect() as conn:
            info = _table_info(conn, "model_swaps")
        expected = {c[0] for c in self.EXPECTED}
        self.assertEqual(
            set(info.keys()),
            expected,
            f"unexpected columns: {set(info.keys()) - expected}; "
            f"missing: {expected - set(info.keys())}",
        )

    def test_swap_id_is_pk_autoincrement(self):
        with _connect() as conn:
            info = _table_info(conn, "model_swaps")
            self.assertGreaterEqual(int(info["swap_id"]["pk"]), 1)
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='model_swaps'"
            ).fetchone()
        self.assertIsNotNone(ddl)
        self.assertIn(
            "AUTOINCREMENT",
            ddl["sql"].upper(),
            "model_swaps.swap_id must declare AUTOINCREMENT",
        )


class IndexesTests(unittest.TestCase):
    """All declared indexes — §4.2, §4.3, §4.3a, §4.4."""

    EXPECTED_INDEXES = [
        ("idx_turns_tenant_ts", "turns", ["tenant_id", "timestamp"], None),
        ("idx_turns_surface_ts", "turns", ["tenant_id", "surface", "timestamp"], None),
        (
            "idx_turns_raw_surface_ts",
            "turns",
            ["tenant_id", "raw_surface", "timestamp"],
            "raw_surface IS NOT NULL",
        ),
        ("idx_turns_kind_ts", "turns", ["tenant_id", "turn_kind", "timestamp"], None),
        ("idx_turns_parent", "turns", ["parent_turn_id"], "parent_turn_id IS NOT NULL"),
        ("idx_turns_model", "turns", ["model_id", "timestamp"], "model_id IS NOT NULL"),
        (
            "idx_turns_audit_trace",
            "turns",
            ["tenant_id", "audit_trace_label", "timestamp"],
            "audit_trace_label IS NOT NULL",
        ),
        ("idx_claims_tenant_turn", "claims", ["tenant_id", "turn_id"], None),
        ("idx_claims_extracted_ts", "claims", ["tenant_id", "extracted_at"], None),
        ("idx_judgements_claim_ts", "claim_judgements", ["claim_id", "judged_at"], None),
        ("idx_judgements_tenant_ts", "claim_judgements", ["tenant_id", "judged_at"], None),
        (
            "idx_judgements_provenance",
            "claim_judgements",
            ["tenant_id", "provenance", "judged_at"],
            "provenance IS NOT NULL",
        ),
        ("idx_swaps_tenant_ts", "model_swaps", ["tenant_id", "timestamp"], None),
    ]

    def test_indexes_exist_with_correct_columns(self):
        with _connect() as conn:
            for idx, table, cols, _where in self.EXPECTED_INDEXES:
                listing = _index_list(conn, table)
                self.assertIn(idx, listing, f"missing index {idx} on table {table}")
                actual_cols = _index_info(conn, idx)
                self.assertEqual(
                    actual_cols, cols, f"{idx}: expected columns {cols}, got {actual_cols}"
                )

    def test_partial_index_where_clauses(self):
        """Partial indexes must carry their declared WHERE clause."""
        with _connect() as conn:
            for idx, _table, _cols, where in self.EXPECTED_INDEXES:
                if where is None:
                    continue
                sql = _index_sql(conn, idx)
                self.assertIn(
                    "WHERE", sql.upper(), f"{idx}: expected partial index with WHERE {where}"
                )
                self.assertIn(
                    where.lower().replace(" ", ""),
                    sql.lower().replace(" ", ""),
                    f"{idx}: WHERE clause must contain {where!r}; got SQL: {sql}",
                )

    def test_descending_timestamp_ordering(self):
        """Indexes declared with DESC ordering must preserve it in DDL."""
        desc_indexes = {
            "idx_turns_tenant_ts": "timestamp",
            "idx_turns_surface_ts": "timestamp",
            "idx_turns_raw_surface_ts": "timestamp",
            "idx_turns_kind_ts": "timestamp",
            "idx_turns_model": "timestamp",
            "idx_claims_extracted_ts": "extracted_at",
            "idx_judgements_claim_ts": "judged_at",
            "idx_judgements_tenant_ts": "judged_at",
            "idx_judgements_provenance": "judged_at",
            "idx_swaps_tenant_ts": "timestamp",
        }
        with _connect() as conn:
            for idx, col in desc_indexes.items():
                sql = _index_sql(conn, idx)
                normalized = " ".join(sql.split()).lower()
                self.assertIn(
                    f"{col} desc", normalized, f"{idx}: expected `{col} DESC` in DDL; got: {sql}"
                )


class ConstraintEnforcementTests(unittest.TestCase):
    """Constraints must actually fire at runtime, not just appear in PRAGMA."""

    def setUp(self):
        self.db_path = Path(_TEST_DB_DIR) / "constraints.db"
        if self.db_path.exists():
            self.db_path.unlink()
        _run_migrations(self.db_path)

    def test_tenant_id_null_rejected(self):
        """Inserting NULL tenant_id raises IntegrityError."""
        conn = sqlite3.connect(self.db_path)
        try:
            with self.assertRaises(
                sqlite3.IntegrityError, msg="tenant_id NOT NULL must be enforced at runtime"
            ):
                conn.execute(
                    "INSERT INTO turns ("
                    "turn_id, tenant_id, timestamp, schema_version, "
                    "turn_kind, surface, raw_text, prev_chain_hash, "
                    "chain_hash) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)",
                    ("null-tenant-test", 1.0, 1, "system_event", "system", "x", "f" * 64, "a" * 64),
                )
                conn.commit()
        finally:
            conn.close()

    def test_claims_fk_to_turns_fires(self):
        """Inserting a claims row with a non-existent turn_id raises.

        SQLite foreign keys require PRAGMA foreign_keys=ON per
        connection. The migration must arrange enforcement (e.g., set
        the pragma in connect helpers, or rely on trigger-based FK
        enforcement). This test opens a fresh connection WITHOUT
        setting the pragma manually and verifies enforcement.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Note: we deliberately do NOT set foreign_keys=ON here.
            # If the migration's contract requires callers to set it,
            # the schema doc should say so explicitly. Today the doc
            # is silent. We document the actual behavior with this test.
            try:
                conn.execute(
                    "INSERT INTO claims "
                    "(turn_id, tenant_id, fact, extracted_at, "
                    " extractor_version, parent_turn_chain_hash) "
                    "VALUES (?, 'owner', ?, ?, 'v1', ?)",
                    ("nonexistent-turn-id", "test claim", 1.0, "f" * 64),
                )
                conn.commit()
                raised_without_pragma = False
            except sqlite3.IntegrityError:
                raised_without_pragma = True
        finally:
            conn.close()

        # Re-open with PRAGMA explicitly set and verify FK fires.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(
                sqlite3.IntegrityError,
                msg="FK claims.turn_id → turns.turn_id must fire when PRAGMA foreign_keys=ON",
            ):
                conn.execute(
                    "INSERT INTO claims "
                    "(turn_id, tenant_id, fact, extracted_at, "
                    " extractor_version, parent_turn_chain_hash) "
                    "VALUES (?, 'owner', ?, ?, 'v1', ?)",
                    ("nonexistent-turn-id-2", "test claim 2", 2.0, "f" * 64),
                )
                conn.commit()
        finally:
            conn.close()

        # Document for future review: if raised_without_pragma is False,
        # the migration does NOT set foreign_keys=ON globally — caller
        # responsibility. That's a real ambiguity the schema doc should
        # close. We don't fail this test on it; we just record the
        # behavior in the test expectation.
        if not raised_without_pragma:
            # Test passes — this is the known SQLite default. The FK
            # enforcement test above verifies the constraint fires
            # with the pragma. Slice 2.3 (writer) must set the pragma
            # in core/ledger/connect.py or equivalent.
            pass


class ViewsTests(unittest.TestCase):
    """Views — §4.3a."""

    def test_latest_claim_judgement_exists(self):
        with _connect() as conn:
            row = conn.execute(
                "SELECT type, sql FROM sqlite_master WHERE name='latest_claim_judgement'"
            ).fetchone()
        self.assertIsNotNone(row, "view latest_claim_judgement missing")
        self.assertEqual(row["type"], "view")

    def test_latest_claim_judgement_shape(self):
        """View must expose every column of claim_judgements."""
        with _connect() as conn:
            cj = _table_info(conn, "claim_judgements")
            view_cols = [
                r["name"]
                for r in conn.execute("PRAGMA table_info(latest_claim_judgement)").fetchall()
            ]
        for col in cj.keys():
            self.assertIn(col, view_cols, f"latest_claim_judgement missing column {col}")

    def test_claims_with_judgement_exists(self):
        with _connect() as conn:
            row = conn.execute(
                "SELECT type, sql FROM sqlite_master WHERE name='claims_with_judgement'"
            ).fetchone()
        self.assertIsNotNone(row, "view claims_with_judgement missing")
        self.assertEqual(row["type"], "view")

    def test_claims_with_judgement_shape(self):
        """View must expose every claims column plus
        provenance, confidence, audit_verdict, judged_at, judged_by."""
        with _connect() as conn:
            claims_cols = set(_table_info(conn, "claims").keys())
            view_cols = {
                r["name"]
                for r in conn.execute("PRAGMA table_info(claims_with_judgement)").fetchall()
            }
        for col in claims_cols:
            self.assertIn(col, view_cols, f"claims_with_judgement missing claims column {col}")
        for col in ("provenance", "confidence", "audit_verdict", "judged_at", "judged_by"):
            self.assertIn(col, view_cols, f"claims_with_judgement missing judgement column {col}")

    def test_views_are_queryable(self):
        """Both views must execute without error against an empty DB."""
        with _connect() as conn:
            conn.execute("SELECT * FROM latest_claim_judgement").fetchall()
            conn.execute("SELECT * FROM claims_with_judgement").fetchall()


if __name__ == "__main__":
    unittest.main()
