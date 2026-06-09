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


if __name__ == "__main__":
    unittest.main()
