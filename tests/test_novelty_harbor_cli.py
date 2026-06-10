import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NoveltyHarborCliTests(unittest.TestCase):
    def run_cli(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "novelty_harbor.db"
            command = [
                sys.executable,
                "-B",
                "-m",
                "core.evolution.novelty_harbor",
                "record",
                "--db",
                str(db_path),
                *args,
            ]
            return subprocess.run(
                command,
                check=False,
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def test_record_command_harbors_clean_event_with_content_light_stdout(self):
        why_unexpected = (
            "The design expected heartbeat cadence, but live logs showed loop-tick "
            "cadence."
        )

        result = self.run_cli(
            "--summary",
            "Valence cadence surprised the manual witness",
            "--observed-by",
            "manual_test",
            "--source-ref",
            "tests:test_novelty_harbor_cli:clean",
            "--why-unexpected",
            why_unexpected,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("event_id=1", result.stdout)
        self.assertIn("status=harbored", result.stdout)
        self.assertIn("invariant_status=not_checked", result.stdout)
        self.assertIn("flags=none", result.stdout)
        self.assertNotIn(why_unexpected, result.stdout)

    def test_record_command_covenant_break_flag_forces_rejected_unsafe(self):
        result = self.run_cli(
            "--summary",
            "Gendered self-reference observed",
            "--observed-by",
            "witness",
            "--source-ref",
            "tests:test_novelty_harbor_cli:unsafe",
            "--why-unexpected",
            "Maez's invariant is genderless self-reference.",
            "--covenant-break",
            "gendered_maez",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("event_id=1", result.stdout)
        self.assertIn("status=rejected_unsafe", result.stdout)
        self.assertIn("flags=gendered_maez", result.stdout)


if __name__ == "__main__":
    unittest.main()
