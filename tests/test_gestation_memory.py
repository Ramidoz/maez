import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution.gestation_memory import GestationMemory


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "g.db"
        self.gm = GestationMemory(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tables_exist(self):
        with sqlite3.connect(self.db) as c:
            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("gestation_claims", names)
        self.assertIn("gestation_claim_supersessions", names)

    def test_gestation_claims_update_is_aborted(self):
        with sqlite3.connect(self.db) as c:
            c.execute(
                "INSERT INTO gestation_claims "
                "(created_at, claim_text, claim_kind, type, confidence, scar, "
                " sources_json, observed_by, metadata_json) "
                "VALUES (1.0,'x','fact','milestone','witnessed',0,'[]','owner','{}')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "UPDATE gestation_claims SET claim_text='y' WHERE claim_id=1"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM gestation_claims WHERE claim_id=1")

    def test_supersessions_update_is_aborted(self):
        with sqlite3.connect(self.db) as c:
            c.execute(
                "INSERT INTO gestation_claim_supersessions "
                "(old_claim_id, replacement_claim_id, created_at) VALUES (1,2,1.0)"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "UPDATE gestation_claim_supersessions "
                    "SET old_claim_id=9 WHERE supersession_id=1"
                )
