# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Append-only invariant tests for the Maez ledger.

The ledger is the root of the personalization stack
(see docs/ledger/envelope-schema.md §0). Its honesty rests on a
single load-bearing rule: rows in `turns`, `claims`, and
`claim_judgements` are NEVER updated and NEVER deleted. Corrections
are append-only — a new row that links back via `correction_of`,
or in the case of judgements a fresh row in `claim_judgements`.

§1 principle 2 names `turns` and `claims` explicitly. §10 (ratified
2026-05-06, see §10.1 edit #2) extends the immutability contract to
`claim_judgements` — Pass B and reconciliation append, never update.
This test treats all three tables as immutable. The ledger writer
must install SQLite triggers that raise on UPDATE or DELETE against
any of them. If any of these tests pass against an implementation
that lacks those triggers, the ledger has been compromised.

`meta` is intentionally exempt: it tracks `schema_version` and the
`genesis_hash`, both of which legitimately change across migrations.

This file is TDD-first. It WILL fail until `core.ledger.migrate`
exists; that failure is the point.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
import uuid
from pathlib import Path

# Test isolation contract: per the convention established in
# tests/test_fabrication_memory.py after the 2026-05-05 production
# leak, MAEZ_TEST_MODE must be set at module load and the DB path
# must be redirected away from the production ledger.db before any
# core.ledger import resolves a path.
os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_append_only_")
_TEST_DB_PATH = Path(_TEST_DB_DIR) / "ledger.db"

# Module-level seed info keyed by id(conn). Populated by _seeded_db,
# consumed by tests that need to reference seed ids. We use this
# instead of conn._seed_* attributes because sqlite3.Connection
# rejects arbitrary attribute setting.
_SEED_INFO: dict = {}


def tearDownModule():
    """Clean up the temp DB directory after the test module finishes."""
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


# Columns we expect to exist on each table. These are the column
# names from docs/ledger/envelope-schema.md §4. Each is tested for
# UPDATE refusal individually because §1 principle 2 + §10 promise
# is a per-column promise, not a "most columns" promise.
_TURNS_COLUMNS = (
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
    "prev_chain_hash",
    "chain_hash",
)

_CLAIMS_COLUMNS = (
    "claim_id",
    "turn_id",
    "tenant_id",
    "fact",
    "extracted_at",
    "extractor_version",
    "parent_turn_chain_hash",
)

_CLAIM_JUDGEMENTS_COLUMNS = (
    "judgement_id",
    "claim_id",
    "tenant_id",
    "judged_at",
    "judged_by",
    "judge_model_id",
    "provenance",
    "evidence_refs_json",
    "confidence",
    "audit_verdict",
    "parent_claim_witness",
)


def _seeded_db() -> sqlite3.Connection:
    """Return a fresh connection against a freshly-migrated ledger
    file with one valid row per immutable table, so UPDATE/DELETE
    statements have a target.

    Each test method gets its own DB file so a successful INSERT or
    a failing trigger in one test cannot affect another.

    This helper deliberately imports `core.ledger` lazily — the
    import will fail until the migrator is implemented, which is
    the desired TDD failure mode for the whole module.

    After seed inserts, this helper VERIFIES the seeds landed by
    counting rows in each immutable table. If the seed silently
    failed (e.g., a CHECK constraint added by a future migration
    rejects the placeholder values), this helper raises immediately
    rather than returning a connection where UPDATE/DELETE refusal
    would degrade to "0 rows touched, no error" — i.e., test against
    an empty table that would green-pass even with no triggers
    installed.
    """
    import hashlib

    from core.ledger import migrate  # noqa: WPS433 (lazy import is intentional)

    db_path = Path(_TEST_DB_DIR) / f"ledger_{uuid.uuid4().hex}.db"
    migrate.run(str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    now = time.time()
    turn_id = str(uuid.uuid4())

    # One valid `turns` row. Every NOT NULL column without a default
    # gets a placeholder; nullable columns are left NULL.
    conn.execute(
        """
        INSERT INTO turns (
            turn_id, tenant_id, timestamp, schema_version, turn_kind,
            surface, raw_surface, parent_turn_id, correction_of,
            model_id, lora_hash, soul_hash, prompt_hash,
            raw_text, rewritten_text, was_rewritten,
            signals_present, signals_absent,
            evidence_envelope_json, action_proposal_json,
            audit_verdict_json, will_i_json,
            memory_read_ids, memory_written_ids,
            audit_log_id, fabrication_event_id,
            self_mod_dialog_id, pending_card_id,
            prev_chain_hash, chain_hash
        ) VALUES (
            ?, 'owner', ?, 1, 'system_event',
            'system', 'ledger_test_seed', NULL, NULL,
            NULL, NULL, NULL, NULL,
            'seed turn for append-only tests', NULL, 0,
            '[]', '[]',
            NULL, NULL,
            NULL, NULL,
            '[]', '[]',
            NULL, NULL,
            NULL, NULL,
            NULL, ?
        )
        """,
        (turn_id, now, hashlib.sha256(("seed-turn-" + turn_id).encode()).hexdigest()),
    )

    # One valid `claims` row pointing at that turn.
    # parent_turn_chain_hash mirrors what was just written to turns —
    # 64-char hex so it survives any future length CHECK on hashes.
    parent_turn_chain_hash = hashlib.sha256(("seed-turn-" + turn_id).encode()).hexdigest()
    cur = conn.execute(
        """
        INSERT INTO claims (
            turn_id, tenant_id, fact, extracted_at,
            extractor_version, parent_turn_chain_hash
        ) VALUES (?, 'owner', ?, ?, ?, ?)
        """,
        (turn_id, "seed claim fact", now, "v0_seed", parent_turn_chain_hash),
    )
    claim_id = cur.lastrowid

    # One valid `claim_judgements` row pointing at that claim.
    conn.execute(
        """
        INSERT INTO claim_judgements (
            claim_id, tenant_id, judged_at, judged_by,
            judge_model_id, provenance, evidence_refs_json,
            confidence, audit_verdict, parent_claim_witness
        ) VALUES (?, 'owner', ?, 'pass_b_judge', NULL,
                  'observed', '{}', 0.5, 'grounded', ?)
        """,
        (claim_id, now, parent_turn_chain_hash),
    )

    conn.commit()

    # Verify the seeds landed. If any of these reads back zero rows,
    # we must NOT return the connection — UPDATE/DELETE refusal tests
    # against an empty table would green-pass even with no triggers
    # installed (UPDATE/DELETE on no rows is a silent success).
    n_turns = conn.execute(
        "SELECT COUNT(*) FROM turns WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()[0]
    if n_turns != 1:
        raise AssertionError(
            f"seed insert into turns did not land (rows seen: {n_turns}). "
            f"This is a setup bug, not an append-only failure — fix the "
            f"seed before reading the test results."
        )
    n_claims = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()[0]
    if n_claims != 1:
        raise AssertionError(
            f"seed insert into claims did not land (rows seen: {n_claims})."
        )
    n_judgements = conn.execute(
        "SELECT COUNT(*) FROM claim_judgements WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()[0]
    if n_judgements != 1:
        raise AssertionError(
            f"seed insert into claim_judgements did not land "
            f"(rows seen: {n_judgements})."
        )

    # Stash the seed ids in a module-level dict keyed by the connection
    # object. (sqlite3.Connection rejects arbitrary attribute setting,
    # so we cannot stash on `conn` directly.) Cleared in tearDown.
    _SEED_INFO[id(conn)] = {
        "turn_id": turn_id,
        "claim_id": claim_id,
        "parent_chain_hash": parent_turn_chain_hash,
    }
    return conn


class _AppendOnlyMixin:
    """Shared helpers for the three immutable-table TestCases."""

    table: str = ""  # overridden
    columns: tuple = ()  # overridden

    def _assert_update_refused(self, conn: sqlite3.Connection, column: str) -> None:
        """Issue an UPDATE on `column` and require it to raise.

        Precondition guard: confirm the table has at least one row.
        Without this, an UPDATE on an empty table is a silent success
        (zero rows touched, no error), which would green-pass against
        an implementation with NO append-only triggers at all.

        We accept `sqlite3.IntegrityError` (RAISE(ABORT, ...) trigger)
        or `sqlite3.OperationalError` (RAISE without ABORT, or other
        trigger-implementation choices). We do NOT accept silent
        success: that means the trigger is missing.
        """
        precount = conn.execute(
            f"SELECT COUNT(*) FROM {self.table}"
        ).fetchone()[0]
        if precount < 1:
            raise AssertionError(  # type: ignore[misc]
                f"precondition for UPDATE refusal test failed: "
                f"{self.table} is empty. _seeded_db should have "
                f"populated it; check the seed path."
            )
        with self.assertRaises(  # type: ignore[attr-defined]
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            msg=(
                f"UPDATE on {self.table}.{column} was permitted; the "
                f"append-only trigger is missing or misconfigured. "
                f"Per docs/ledger/envelope-schema.md §1 principle 2 "
                f"and §10 (ratified 2026-05-06), {self.table} is "
                f"strictly immutable."
            ),
        ):
            # Use a benign payload type; SQLite will coerce. The
            # point is that the WRITE is refused, regardless of the
            # value being written.
            conn.execute(f"UPDATE {self.table} SET {column} = ?", ("tampered",))

    def _assert_delete_refused(self, conn: sqlite3.Connection) -> None:
        """DELETE refused. Same precondition: table must be non-empty."""
        precount = conn.execute(
            f"SELECT COUNT(*) FROM {self.table}"
        ).fetchone()[0]
        if precount < 1:
            raise AssertionError(  # type: ignore[misc]
                f"precondition for DELETE refusal test failed: "
                f"{self.table} is empty."
            )
        with self.assertRaises(  # type: ignore[attr-defined]
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            msg=(
                f"DELETE on {self.table} was permitted; the "
                f"append-only trigger is missing or misconfigured."
            ),
        ):
            conn.execute(f"DELETE FROM {self.table}")


class TurnsAppendOnlyTests(unittest.TestCase, _AppendOnlyMixin):
    table = "turns"
    columns = _TURNS_COLUMNS

    def setUp(self):
        self.conn = _seeded_db()

    def tearDown(self):
        self.conn.close()

    def test_insert_valid_turn_succeeds(self):
        """A second well-formed turn must INSERT cleanly. INSERT is
        the only legal write; if INSERT itself fails the schema is
        broken in a way unrelated to the append-only invariant.
        """
        turn_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO turns (
                turn_id, tenant_id, timestamp, schema_version,
                turn_kind, surface, raw_text, was_rewritten,
                signals_present, signals_absent,
                memory_read_ids, memory_written_ids, chain_hash
            ) VALUES (?, 'owner', ?, 1, 'system_event', 'system',
                      'second valid turn', 0, '[]', '[]', '[]', '[]', ?)
            """,
            (turn_id, time.time(), "chain_hash_" + turn_id),
        )
        self.conn.commit()
        # Exclude the genesis row (turn_id='genesis', inserted by
        # migrate.run()). Seed inserts one row, this test inserts
        # one more — two non-genesis turns.
        n = self.conn.execute(
            "SELECT COUNT(*) FROM turns WHERE turn_id != 'genesis'"
        ).fetchone()[0]
        self.assertEqual(n, 2)

    def test_delete_refused(self):
        self._assert_delete_refused(self.conn)


def _make_turns_update_test(column: str):
    def test(self):
        self._assert_update_refused(self.conn, column)
    test.__name__ = f"test_update_{column}_refused"
    test.__doc__ = (
        f"UPDATE turns.{column} must raise. Per-column promise from "
        f"§1 principle 2 + §4.2 DDL — every column in the turns table "
        f"is immutable, no exceptions."
    )
    return test


for _col in _TURNS_COLUMNS:
    setattr(TurnsAppendOnlyTests,
            f"test_update_{_col}_refused",
            _make_turns_update_test(_col))


class ClaimsAppendOnlyTests(unittest.TestCase, _AppendOnlyMixin):
    table = "claims"
    columns = _CLAIMS_COLUMNS

    def setUp(self):
        self.conn = _seeded_db()

    def tearDown(self):
        self.conn.close()

    def test_insert_valid_claim_succeeds(self):
        """A second claim against the same turn must INSERT cleanly."""
        self.conn.execute(
            """
            INSERT INTO claims (
                turn_id, tenant_id, fact, extracted_at,
                extractor_version, parent_turn_chain_hash
            ) VALUES (?, 'owner', 'second claim fact', ?, 'v0_seed', ?)
            """,
            (
                _SEED_INFO[id(self.conn)]["turn_id"],
                time.time(),
                _SEED_INFO[id(self.conn)]["parent_chain_hash"],
            ),
        )
        self.conn.commit()
        n = self.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        self.assertEqual(n, 2)

    def test_delete_refused(self):
        self._assert_delete_refused(self.conn)


def _make_claims_update_test(column: str):
    def test(self):
        self._assert_update_refused(self.conn, column)
    test.__name__ = f"test_update_{column}_refused"
    test.__doc__ = (
        f"UPDATE claims.{column} must raise. §10 of the schema doc "
        f"states 'claims rows are immutable from the moment Pass A "
        f"inserts them' — every column, including claim_id."
    )
    return test


for _col in _CLAIMS_COLUMNS:
    setattr(ClaimsAppendOnlyTests,
            f"test_update_{_col}_refused",
            _make_claims_update_test(_col))


class ClaimJudgementsAppendOnlyTests(unittest.TestCase, _AppendOnlyMixin):
    """`claim_judgements` is hardline append-only.

    The schema doc went through a ratification edit (§10.1 edit #2,
    2026-05-06) that REMOVED a prior single-table UPDATE carve-out
    and replaced it with a separate `claim_judgements` table where
    Pass B writes a NEW row per judgement attempt — never updates an
    existing one. Reconciliation re-runs append; owner-manual
    overrides append; nothing UPDATEs.

    These tests verify that hardline shape. Any future "just one
    quick UPDATE for X" trigger carve-out is a regression and this
    file should fail until it's reverted.
    """

    table = "claim_judgements"
    columns = _CLAIM_JUDGEMENTS_COLUMNS

    def setUp(self):
        self.conn = _seeded_db()

    def tearDown(self):
        self.conn.close()

    def test_insert_valid_judgement_succeeds(self):
        """A second judgement for the same claim must INSERT cleanly.
        Re-judgement is how the system gets corrected — by appending
        a new row, NOT by updating the existing one. The
        latest_claim_judgement view (§4.3a) is what the cockpit
        reads to surface 'current belief'.
        """
        self.conn.execute(
            """
            INSERT INTO claim_judgements (
                claim_id, tenant_id, judged_at, judged_by,
                judge_model_id, provenance, evidence_refs_json,
                confidence, audit_verdict, parent_claim_witness
            ) VALUES (?, 'owner', ?, 'reconciliation', NULL,
                      'observed', '{}', 0.7, 'grounded', ?)
            """,
            (
                _SEED_INFO[id(self.conn)]["claim_id"],
                time.time(),
                _SEED_INFO[id(self.conn)]["parent_chain_hash"],
            ),
        )
        self.conn.commit()
        n = self.conn.execute(
            "SELECT COUNT(*) FROM claim_judgements"
        ).fetchone()[0]
        self.assertEqual(n, 2)

    def test_delete_refused(self):
        self._assert_delete_refused(self.conn)


def _make_judgement_update_test(column: str):
    def test(self):
        self._assert_update_refused(self.conn, column)
    test.__name__ = f"test_update_{column}_refused"
    test.__doc__ = (
        f"UPDATE claim_judgements.{column} must raise. Per §10.1 "
        f"edit #2 (ratified 2026-05-06): the prior single-table "
        f"UPDATE carve-out was REJECTED in favor of strict append-"
        f"only across all three tables. No column on a judgement "
        f"row is mutable, ever — including {column}."
    )
    return test


for _col in _CLAIM_JUDGEMENTS_COLUMNS:
    setattr(ClaimJudgementsAppendOnlyTests,
            f"test_update_{_col}_refused",
            _make_judgement_update_test(_col))


class MetaMutabilityTests(unittest.TestCase):
    """`meta` is intentionally NOT append-only.

    §1 principle 2 names `turns` and `claims` as immutable; §10
    extends the contract to `claim_judgements`. `meta` is excluded
    on purpose: it carries `schema_version`, which legitimately
    changes when a migration appends a new schema_version row, and
    it carries `genesis_hash`, which is set once at first run.

    These tests pin the exemption so a future "let's just lock
    every table" pass doesn't accidentally make migrations
    impossible.
    """

    def setUp(self):
        self.conn = _seeded_db()

    def tearDown(self):
        self.conn.close()

    def test_insert_new_meta_key_succeeds(self):
        """A migrator must be able to add new meta keys."""
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ("test_new_key", "v1"),
        )
        self.conn.commit()
        v = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", ("test_new_key",),
        ).fetchone()[0]
        self.assertEqual(v, "v1")

    def test_update_existing_meta_key_succeeds(self):
        """schema_version is the canonical mutable meta key. The
        whole point of this exemption is that bumping it during a
        migration must succeed silently.
        """
        # The genesis seed inserts schema_version=1 (per §4.1
        # comment). If the migrator changed that key name we want
        # this test to fail loudly rather than silently no-op, so
        # we assert the row exists first.
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", ("schema_version",),
        ).fetchone()
        self.assertIsNotNone(
            row,
            "meta.schema_version was not seeded by migrate(); "
            "the migrator contract from §4.1 is broken.",
        )

        self.conn.execute(
            "UPDATE meta SET value = ? WHERE key = ?",
            ("2", "schema_version"),
        )
        self.conn.commit()
        v = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", ("schema_version",),
        ).fetchone()[0]
        self.assertEqual(
            v, "2",
            "meta UPDATE silently failed; the meta exemption is "
            "broken and migrations cannot bump schema_version.",
        )

    def test_delete_meta_key_succeeds(self):
        """No append-only trigger should be installed on meta."""
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ("transient_key", "x"),
        )
        self.conn.commit()
        self.conn.execute(
            "DELETE FROM meta WHERE key = ?", ("transient_key",),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", ("transient_key",),
        ).fetchone()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
