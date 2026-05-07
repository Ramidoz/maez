# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Genesis-row and meta-table invariants for core.ledger.

Locks in the schema-doc contract from LEDGER_ENVELOPE_SCHEMA.md
(§4.1 meta seeding, §6.1 chain construction):

  - migrate.run() seeds meta with schema_version='1' and a 64-char-hex
    genesis_hash row.
  - The genesis row in `turns` has prev_chain_hash IS NULL and its
    chain_hash equals meta.genesis_hash.
  - Genesis chain_hash is stable: re-running migrate.run() on a fresh
    empty DB produces the same hex string (deterministic).
  - migrate.run() is idempotent: a second call against an already-
    migrated DB does not insert a second genesis row and does not
    mutate genesis_hash.
  - Genesis row metadata: tenant_id='owner', turn_kind='system_event'.

The hash recomputation is left to test_ledger_chain.py — here we
assert structural + determinism properties so this file does not
duplicate the writer's canonicalization logic and break every time
the canonical-bytes definition shifts.
"""
from __future__ import annotations

import os
import sqlite3
import string
import tempfile
import unittest
from pathlib import Path

# Same isolation contract used by test_fabrication_memory.py: opt
# into MAEZ_TEST_MODE before importing the module under test, and
# point the ledger at a temp DB so production memory/ledger.db is
# never touched.
os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_genesis_")

# Intentional hard import. core.ledger.migrate does not yet exist;
# this import will raise ImportError until the migration slice
# lands. That failure is the spec.
from core.ledger import migrate  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db_path(name: str) -> Path:
    """Allocate a brand-new empty DB file inside the test temp dir."""
    p = Path(_TEST_DB_DIR) / name
    if p.exists():
        p.unlink()
    for suffix in ("-wal", "-shm", "-journal"):
        side = p.with_name(p.name + suffix)
        if side.exists():
            side.unlink()
    return p


_LOWER_HEX = set("0123456789abcdef")


def _is_lower_hex_64(s: str) -> bool:
    """Strictly lowercase 64-char hex (sha256 by Python convention)."""
    return (
        isinstance(s, str)
        and len(s) == 64
        and all(c in _LOWER_HEX for c in s)
    )


class GenesisMetaTests(unittest.TestCase):
    """meta table is seeded with schema_version + genesis_hash."""

    def setUp(self):
        self.db_path = _fresh_db_path("genesis_meta.db")
        migrate.run(str(self.db_path))
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        self.conn.close()

    def test_schema_version_is_one(self):
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        self.assertIsNotNone(row, "meta.schema_version was not seeded")
        self.assertEqual(row[0], "1")

    def test_genesis_hash_is_64_char_hex(self):
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key='genesis_hash'"
        ).fetchone()
        self.assertIsNotNone(row, "meta.genesis_hash was not seeded")
        self.assertTrue(
            _is_lower_hex_64(row[0]),
            f"genesis_hash is not 64 lowercase hex chars: {row[0]!r}",
        )

    def test_meta_has_no_duplicate_keys(self):
        n_sv = self.conn.execute(
            "SELECT COUNT(*) FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
        n_gh = self.conn.execute(
            "SELECT COUNT(*) FROM meta WHERE key='genesis_hash'"
        ).fetchone()[0]
        self.assertEqual(n_sv, 1)
        self.assertEqual(n_gh, 1)


class GenesisRowTests(unittest.TestCase):
    """The genesis row in `turns` matches schema-doc §6.1 + §4.2."""

    def setUp(self):
        self.db_path = _fresh_db_path("genesis_row.db")
        migrate.run(str(self.db_path))
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        self.conn.close()

    def test_exactly_one_genesis_row(self):
        n = self.conn.execute(
            "SELECT COUNT(*) FROM turns WHERE prev_chain_hash IS NULL"
        ).fetchone()[0]
        self.assertEqual(n, 1, "expected exactly one genesis row")

    def test_genesis_row_chain_hash_matches_meta(self):
        row = self.conn.execute(
            "SELECT chain_hash FROM turns WHERE prev_chain_hash IS NULL"
        ).fetchone()
        self.assertIsNotNone(row)
        meta_hash = self.conn.execute(
            "SELECT value FROM meta WHERE key='genesis_hash'"
        ).fetchone()[0]
        self.assertEqual(row[0], meta_hash)

    def test_genesis_row_tenant_is_owner(self):
        row = self.conn.execute(
            "SELECT tenant_id FROM turns WHERE prev_chain_hash IS NULL"
        ).fetchone()
        self.assertEqual(row[0], "owner")

    def test_genesis_row_kind_is_system_event(self):
        row = self.conn.execute(
            "SELECT turn_kind FROM turns WHERE prev_chain_hash IS NULL"
        ).fetchone()
        self.assertEqual(row[0], "system_event")

    def test_genesis_chain_hash_is_64_char_hex(self):
        row = self.conn.execute(
            "SELECT chain_hash FROM turns WHERE prev_chain_hash IS NULL"
        ).fetchone()
        self.assertTrue(_is_lower_hex_64(row[0]))


class GenesisDeterminismTests(unittest.TestCase):
    """Two fresh-empty migrations produce the same genesis hash.

    This is the implementation-independent stand-in for asserting
    sha256("genesis" || canonical_row_bytes): if the canonicalization
    is deterministic and the seeded fields are constant, two cold
    starts must converge on the same digest.
    """

    def test_two_fresh_migrations_produce_same_genesis_hash(self):
        p1 = _fresh_db_path("genesis_det_a.db")
        p2 = _fresh_db_path("genesis_det_b.db")
        migrate.run(str(p1))
        migrate.run(str(p2))

        c1 = sqlite3.connect(p1)
        c2 = sqlite3.connect(p2)
        try:
            h1 = c1.execute(
                "SELECT value FROM meta WHERE key='genesis_hash'"
            ).fetchone()[0]
            h2 = c2.execute(
                "SELECT value FROM meta WHERE key='genesis_hash'"
            ).fetchone()[0]
        finally:
            c1.close()
            c2.close()
        self.assertEqual(
            h1, h2,
            "genesis_hash must be deterministic across fresh migrations; "
            "non-determinism implies the canonical-row-bytes recipe pulled "
            "in a non-stable field (timestamp, uuid, etc.)",
        )


class GenesisRecipeTests(unittest.TestCase):
    """Pin the chain-hash recipe to the schema doc, not just to determinism.

    Determinism alone is satisfied by `chain_hash = sha256(b"hello")`
    on every fresh DB. This test reads back whatever the migration
    actually wrote into the genesis row, applies the §6.1 canonical
    recipe (sha256 of "genesis" + JSON-with-sorted-keys), and asserts
    it matches the stored chain_hash. A migration that uses any other
    recipe — including any other byte prefix, any other JSON
    serialization, or any other digest — will fail here.

    The expected canonical row recipe (from §6.1):
      - canonical_row_bytes = JSON of the row dict
      - keys sorted, separators=(',', ':'), ensure_ascii=True
      - omits `chain_hash` and `prev_chain_hash`
      - NULL columns are included as null keys (not omitted)
      - chain_hash = sha256(("genesis" + canonical_row_bytes).encode())
    """

    def test_genesis_chain_hash_matches_canonical_recipe(self):
        import hashlib
        import json

        db_path = _fresh_db_path("genesis_recipe.db")
        migrate.run(str(db_path))

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Read every column of the genesis row.
            row = conn.execute(
                "SELECT * FROM turns WHERE prev_chain_hash IS NULL"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "no genesis row to verify recipe against")

        # Build the canonical dict: every column EXCEPT chain_hash and
        # prev_chain_hash (these two are omitted per §6.1).
        canonical_dict = {
            k: row[k] for k in row.keys()
            if k not in ("chain_hash", "prev_chain_hash")
        }

        # Canonical JSON: sorted keys, no whitespace, ensure_ascii.
        canonical_bytes = json.dumps(
            canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        expected = hashlib.sha256(
            ("genesis" + canonical_bytes).encode("utf-8")
        ).hexdigest()

        actual = row["chain_hash"]
        self.assertEqual(
            actual, expected,
            f"genesis chain_hash does not match canonical recipe.\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}\n"
            f"  canonical_bytes: {canonical_bytes!r}\n"
            f"  recipe: sha256('genesis' + canonical_bytes_utf8).hexdigest()\n"
            f"If the migration uses a different recipe, the schema doc "
            f"§6.1 must be updated AND a new schema_version published.",
        )


class GenesisIdempotenceTests(unittest.TestCase):
    """Re-running migrate.run() on an already-migrated DB is a no-op."""

    def test_second_migrate_does_not_duplicate_genesis(self):
        db_path = _fresh_db_path("genesis_idem.db")
        migrate.run(str(db_path))

        conn = sqlite3.connect(db_path)
        try:
            hash_before = conn.execute(
                "SELECT value FROM meta WHERE key='genesis_hash'"
            ).fetchone()[0]
            n_turns_before = conn.execute(
                "SELECT COUNT(*) FROM turns"
            ).fetchone()[0]
            n_genesis_before = conn.execute(
                "SELECT COUNT(*) FROM turns WHERE prev_chain_hash IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()

        migrate.run(str(db_path))

        conn = sqlite3.connect(db_path)
        try:
            hash_after = conn.execute(
                "SELECT value FROM meta WHERE key='genesis_hash'"
            ).fetchone()[0]
            n_turns_after = conn.execute(
                "SELECT COUNT(*) FROM turns"
            ).fetchone()[0]
            n_genesis_after = conn.execute(
                "SELECT COUNT(*) FROM turns WHERE prev_chain_hash IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(hash_before, hash_after,
                         "genesis_hash must not change on re-migration")
        self.assertEqual(n_turns_before, n_turns_after,
                         "re-migration must not append rows to turns")
        self.assertEqual(n_genesis_before, 1)
        self.assertEqual(n_genesis_after, 1,
                         "re-migration must not create a second genesis row")


class HeadPointerTests(unittest.TestCase):
    """meta.last_chain_hash is the truncation-defense head pointer.

    Without this, an attacker who deletes the last N rows of `turns`
    passes verification cleanly. With it, the chain walker can assert
    that the final reached row's chain_hash matches the recorded head.
    On first-run seed, the head IS the genesis row.
    """

    def test_last_chain_hash_seeded_to_genesis(self):
        db_path = _fresh_db_path("head_pointer.db")
        migrate.run(str(db_path))
        conn = sqlite3.connect(db_path)
        try:
            head_row = conn.execute(
                "SELECT value FROM meta WHERE key='last_chain_hash'"
            ).fetchone()
            genesis_row = conn.execute(
                "SELECT value FROM meta WHERE key='genesis_hash'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(head_row,
            "meta.last_chain_hash must be seeded by migrate.run()")
        self.assertIsNotNone(genesis_row)
        self.assertEqual(head_row[0], genesis_row[0],
            "On first-run seed, meta.last_chain_hash must equal "
            "meta.genesis_hash (the genesis row IS the head).")

    def test_last_chain_hash_64_char_lowercase_hex(self):
        db_path = _fresh_db_path("head_format.db")
        migrate.run(str(db_path))
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key='last_chain_hash'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertTrue(_is_lower_hex_64(row[0]),
            f"meta.last_chain_hash must be 64 lowercase hex chars; got {row[0]!r}")

    def test_idempotent_re_migration_does_not_duplicate_head(self):
        db_path = _fresh_db_path("head_idem.db")
        migrate.run(str(db_path))
        migrate.run(str(db_path))  # second call must be no-op
        conn = sqlite3.connect(db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM meta WHERE key='last_chain_hash'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 1,
            "re-migration must not duplicate the last_chain_hash meta row")


if __name__ == "__main__":
    unittest.main()
