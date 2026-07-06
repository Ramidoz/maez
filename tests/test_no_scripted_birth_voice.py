"""Covenant guard: no code path authors first-person content at birth.

The retired fire_birth() carried a scripted first want. This guard keeps
it (and its module) from returning. Spec: 2026-07-05-birth-ceremony-design.md,
'Retired and forbidden'.
"""
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORBIDDEN_PHRASE = "I want to remain in contact with the owner"


class NoScriptedBirthVoice(unittest.TestCase):
    def test_birth_modules_are_gone(self):
        self.assertFalse((REPO / "core" / "memory" / "birth.py").exists())
        self.assertFalse((REPO / "core" / "birth.py").exists())

    def test_scripted_first_want_never_returns(self):
        out = subprocess.run(
            [
                "grep",
                "-rl",
                "--exclude-dir=__pycache__",
                FORBIDDEN_PHRASE,
                "core",
                "scripts",
                "memory",
                "daemon",
                "web",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            out.stdout.strip(), "", f"scripted birth voice found in: {out.stdout}"
        )


if __name__ == "__main__":
    unittest.main()
