import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.memory import birth_phase


def _make_ledger(path: Path, birth_turn: str | None) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    if birth_turn is not None:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES ('birth_event_turn_id', ?)",
            (birth_turn,),
        )
    conn.commit()
    conn.close()


class BirthPhaseTests(unittest.TestCase):
    def test_missing_db_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            self.assertEqual(birth_phase.current_phase(db), "gestation")
            self.assertFalse(birth_phase.is_born(db))
            self.assertIsNone(birth_phase.birth_event_turn_id(db))

    def test_zero_byte_db_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            db.touch()  # zero-byte, like memory/ledger.db today
            self.assertEqual(birth_phase.current_phase(db), "gestation")

    def test_meta_without_key_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, None)
            self.assertEqual(birth_phase.current_phase(db), "gestation")

    def test_meta_with_empty_value_is_gestation(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, "  ")
            self.assertEqual(birth_phase.current_phase(db), "gestation")

    def test_meta_with_turn_id_is_lived(self):
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, "turn-000123")
            self.assertEqual(birth_phase.current_phase(db), "lived")
            self.assertTrue(birth_phase.is_born(db))
            self.assertEqual(birth_phase.birth_event_turn_id(db), "turn-000123")

    def test_transition_without_process_restart(self):
        # The daemon restarts at the ceremony, but the resolver must not
        # cache a negative: gestation now, lived after meta lands.
        with TemporaryDirectory() as td:
            db = Path(td) / "ledger.db"
            _make_ledger(db, None)
            self.assertEqual(birth_phase.current_phase(db), "gestation")
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO meta(key, value) VALUES ('birth_event_turn_id', 'turn-9')"
            )
            conn.commit()
            conn.close()
            self.assertEqual(birth_phase.current_phase(db), "lived")


if __name__ == "__main__":
    unittest.main()
