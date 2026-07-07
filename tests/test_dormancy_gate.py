import sqlite3
import tempfile
import unittest
from pathlib import Path


class DormancyGateTests(unittest.TestCase):
    def test_clause_a_unknown_provenance_is_red_and_names_class(self):
        from core.governance.dormancy_gate import clause_a

        with tempfile.TemporaryDirectory() as td:
            memory_dir = Path(td)
            self._create_wants_db(memory_dir / "wants.db", ["explicit_api", "dream_authored"])

            result = clause_a(memory_dir=memory_dir)

        self.assertFalse(result.ok)
        self.assertIn("dream_authored", result.detail)
        self.assertIn("1", result.detail)

    def test_clause_a_empty_or_missing_stores_are_green(self):
        from core.governance.dormancy_gate import clause_a

        with tempfile.TemporaryDirectory() as td:
            memory_dir = Path(td)
            self._create_wants_db(memory_dir / "wants.db", [])
            self._create_wonderings_db(memory_dir / "wonderings.db", [])

            result = clause_a(memory_dir=memory_dir)

        self.assertTrue(result.ok)
        self.assertIn("no authored provenance", result.detail)

    def test_clause_b_s7_armed_is_red(self):
        from core.governance.dormancy_gate import clause_b

        result = clause_b(env={"S7_LIVE_WEBAUTHN_CEREMONY": "1"})

        self.assertFalse(result.ok)
        self.assertIn("armed", result.detail)

    def test_clause_b_s7_disarmed_is_green(self):
        from core.governance.dormancy_gate import clause_b

        result = clause_b(env={})

        self.assertTrue(result.ok)
        self.assertIn("not armed", result.detail)

    def test_clause_a_does_not_create_missing_real_shaped_stores(self):
        from core.governance.dormancy_gate import clause_a

        with tempfile.TemporaryDirectory() as td:
            memory_dir = Path(td)
            result = clause_a(memory_dir=memory_dir)

            self.assertTrue(result.ok)
            self.assertEqual(list(memory_dir.iterdir()), [])

    @staticmethod
    def _create_wants_db(path: Path, provenances: list[str]) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE want_events (provenance TEXT NOT NULL)")
            for provenance in provenances:
                conn.execute("INSERT INTO want_events (provenance) VALUES (?)", (provenance,))

    @staticmethod
    def _create_wonderings_db(path: Path, sources: list[str]) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE wonderings (source TEXT)")
            for source in sources:
                conn.execute("INSERT INTO wonderings (source) VALUES (?)", (source,))


if __name__ == "__main__":
    unittest.main()
