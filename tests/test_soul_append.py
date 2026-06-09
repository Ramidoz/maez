"""Task 3 — self-authored soul notes route to the LOCAL layer and dedupe.

Prevents the append-rot from re-accumulating: the legacy writer appended to the
soul.md mirror (overwritten by the loader) with no dedup. The fix routes through
soul_loader.append_soul_note -> soul.local.md, content-deduped.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import core.evolution.soul_loader as sl


class SoulAppend(unittest.TestCase):
    def test_routes_to_local_and_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "soul.local.md"
            with mock.patch("core.infra.paths.soul_local_path", return_value=local):
                r1 = sl.append_soul_note("disk fixation lesson: stop repeating")
                self.assertIn("disk fixation lesson: stop repeating", local.read_text())
                self.assertIn("appended", r1.lower())

                # identical note (content) must NOT duplicate, regardless of timestamp
                r2 = sl.append_soul_note("disk fixation lesson: stop repeating")
                self.assertEqual(
                    local.read_text().count("disk fixation lesson: stop repeating"), 1
                )
                self.assertIn("skipped", r2.lower())

    def test_empty_note_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "soul.local.md"
            with mock.patch("core.infra.paths.soul_local_path", return_value=local):
                r = sl.append_soul_note("   ")
                self.assertIn("skipped", r.lower())
                self.assertFalse(local.exists())

    def test_substring_distinct_note_still_appends(self):
        # Codex catch: dedupe must be EXACT note-body match, not substring.
        # A shorter distinct note contained inside an older one must still append.
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "soul.local.md"
            with mock.patch("core.infra.paths.soul_local_path", return_value=local):
                sl.append_soul_note("disk fixation lesson: stop repeating with detail")
                r = sl.append_soul_note("disk fixation lesson: stop repeating")
                self.assertIn("appended", r.lower())  # distinct, must NOT be skipped
                txt = local.read_text()
                self.assertIn("disk fixation lesson: stop repeating with detail", txt)
                self.assertEqual(
                    txt.count("] disk fixation lesson: stop repeating"), 2
                )

    def test_multiparagraph_note_dedupes(self):
        # Codex round-2 catch: a note body with a blank line must still dedupe
        # exactly (records delimited by timestamp boundary, not blank lines).
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "soul.local.md"
            with mock.patch("core.infra.paths.soul_local_path", return_value=local):
                r1 = sl.append_soul_note("lesson one\n\nlesson two")
                r2 = sl.append_soul_note("lesson one\n\nlesson two")
                self.assertIn("appended", r1.lower())
                self.assertIn("skipped", r2.lower())
                self.assertEqual(local.read_text().count("lesson two"), 1)

    def test_note_with_inline_timestamp_dedupes(self):
        # Same promise, harder text: a note whose body contains a literal
        # [YYYY-MM-DD HH:MM] must not be mistaken for a record boundary.
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "soul.local.md"
            with mock.patch("core.infra.paths.soul_local_path", return_value=local):
                note = "remember the meeting at [2026-04-01 10:00] today"
                r1 = sl.append_soul_note(note)
                r2 = sl.append_soul_note(note)
                self.assertIn("appended", r1.lower())
                self.assertIn("skipped", r2.lower())
                self.assertEqual(local.read_text().count("remember the meeting"), 1)


if __name__ == "__main__":
    unittest.main()
