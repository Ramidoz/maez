from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.interaction_preferences.store import InteractionPreferencesStore


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "interaction_preferences.py"


class InteractionPreferencesScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "interaction_preferences.db"
        self.store = InteractionPreferencesStore(self.db_path)
        self.store.record_capture(
            preference_id="pref-1",
            preference_class="question_cadence",
            owner_statement="stop asking me so many questions",
            source_ref="owner_turn:telegram:abc123:1000",
            surface="telegram",
            statement_sha256="a" * 64,
            created_at="2026-07-03T12:00:00Z",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--db", str(self.db_path)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_list_outputs_active_verbatim_statement(self):
        result = self._run("list")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pref-1", result.stdout)
        self.assertIn("active", result.stdout)
        self.assertIn("stop asking me so many questions", result.stdout)

    def test_list_missing_db_does_not_create_empty_store(self):
        missing = Path(self.tmp.name) / "missing" / "interaction_preferences.db"

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "list", "--db", str(missing)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(missing.exists())

    def test_list_existing_empty_db_is_read_only(self):
        empty = Path(self.tmp.name) / "empty.db"
        empty.write_bytes(b"")
        before = empty.stat().st_size

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "list", "--db", str(empty)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(empty.stat().st_size, before)

    def test_show_outputs_single_preference(self):
        result = self._run("show", "pref-1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preference_id: pref-1", result.stdout)
        self.assertIn("owner_statement: stop asking me so many questions", result.stdout)

    def test_show_missing_db_does_not_create_empty_store(self):
        missing = Path(self.tmp.name) / "missing" / "interaction_preferences.db"

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "show", "pref-1", "--db", str(missing)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("not found: pref-1", result.stderr)
        self.assertFalse(missing.exists())

    def test_show_existing_empty_db_is_read_only(self):
        empty = Path(self.tmp.name) / "empty.db"
        empty.write_bytes(b"")
        before = empty.stat().st_size

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "show", "pref-1", "--db", str(empty)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("not found: pref-1", result.stderr)
        self.assertEqual(empty.stat().st_size, before)

    def test_retract_requires_owner_approved(self):
        result = self._run("retract", "pref-1", "--reason", "actually, ask away")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--owner-approved", result.stderr)
        self.assertEqual(
            [p.preference_id for p in self.store.active_preferences("question_cadence")],
            ["pref-1"],
        )

    def test_retract_with_owner_approved_supersedes(self):
        result = self._run(
            "retract",
            "pref-1",
            "--reason",
            "actually, ask away",
            "--owner-approved",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.store.active_preferences("question_cadence"), [])
        self.assertIn("retracted pref-1", result.stdout)


if __name__ == "__main__":
    unittest.main()
