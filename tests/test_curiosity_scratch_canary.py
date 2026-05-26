from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH_CURIOSITY_CANARY_SCRIPT = ROOT / "scripts" / "scratch_curiosity_e2e_canary.py"


class CuriosityScratchCanaryTests(unittest.TestCase):
    def test_scratch_curiosity_canary_runs_end_to_end(self):
        self.assertTrue(
            SCRATCH_CURIOSITY_CANARY_SCRIPT.exists(),
            "curiosity scratch E2E canary script must exist",
        )
        with tempfile.TemporaryDirectory() as td:
            scratch_root = Path(td) / "curiosity-scratch"
            result = subprocess.run(
                [os.fspath(SCRATCH_CURIOSITY_CANARY_SCRIPT), os.fspath(scratch_root)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("curiosity scratch E2E canary passed", result.stdout)
        self.assertIn("meaningfulness_score=", result.stdout)
        self.assertIn("resolution_marker_type=explicit_owner_resolved", result.stdout)
        self.assertIn("resolution_marker_utc=", result.stdout)

    def test_scratch_curiosity_canary_refuses_existing_path(self):
        self.assertTrue(
            SCRATCH_CURIOSITY_CANARY_SCRIPT.exists(),
            "curiosity scratch E2E canary script must exist",
        )
        with tempfile.TemporaryDirectory() as td:
            scratch_root = Path(td) / "existing"
            scratch_root.mkdir()
            result = subprocess.run(
                [os.fspath(SCRATCH_CURIOSITY_CANARY_SCRIPT), os.fspath(scratch_root)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses to write to an existing path", result.stderr)

    def test_scratch_curiosity_canary_refuses_repo_memory_path(self):
        result = subprocess.run(
            [
                os.fspath(SCRATCH_CURIOSITY_CANARY_SCRIPT),
                os.fspath(ROOT / "memory" / "curiosity-canary-test"),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses to write under the repo memory directory", result.stderr)

    def test_scratch_curiosity_canary_uses_explicit_checks_not_optimized_asserts(self):
        text = SCRATCH_CURIOSITY_CANARY_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("assert ", text)
        self.assertIn("curiosity object did not carry resolution marker", text)
        self.assertIn("curiosity scratch canary integrity failure", text)


if __name__ == "__main__":
    unittest.main()
