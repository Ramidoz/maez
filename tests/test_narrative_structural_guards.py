import unittest
import subprocess
import sys
from pathlib import Path


class NarrativeStructuralGuardTests(unittest.TestCase):
    def test_no_llm_guard_scans_real_weave_and_planted_violation(self):
        from core.memory.narrative_weave import assert_no_llm_in_weave_source

        root = Path(__file__).resolve().parent.parent
        source = (root / "core" / "memory" / "narrative_weave.py").read_text(
            encoding="utf-8"
        )
        assert_no_llm_in_weave_source(source)
        with self.assertRaisesRegex(AssertionError, "LLM"):
            assert_no_llm_in_weave_source("from core.routing import llm_client\n")

    def test_no_lived_graph_guard_scans_real_sources_and_planted_violation(self):
        from scripts.validate.narrative_structural_guards import (
            assert_no_lived_graph_import_source,
            run_narrative_structural_guards,
        )

        counts = run_narrative_structural_guards(Path(__file__).resolve().parent.parent)
        self.assertGreater(counts["files"], 0)
        with self.assertRaisesRegex(AssertionError, "lived_graph"):
            assert_no_lived_graph_import_source("from core.memory import lived_graph\n")

    def test_forbidden_durable_link_writer_guard_trips_on_planted_samples(self):
        from scripts.validate.narrative_structural_guards import (
            assert_no_forbidden_link_writer_source,
            run_narrative_structural_guards,
        )

        run_narrative_structural_guards(Path(__file__).resolve().parent.parent)
        with self.assertRaisesRegex(AssertionError, "follows"):
            assert_no_forbidden_link_writer_source(
                "store.upsert_link(link_type='follows', trust='derived')\n"
            )
        with self.assertRaisesRegex(AssertionError, "same_story"):
            assert_no_forbidden_link_writer_source(
                "store.upsert_link(link_type='same_story', trust='derived')\n"
            )
        with self.assertRaisesRegex(AssertionError, "proposed"):
            assert_no_forbidden_link_writer_source(
                "store.upsert_link(link_type='same_thread', trust='proposed')\n"
            )

    def test_validator_script_runs_from_repo_root(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/validate/narrative_structural_guards.py",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("narrative structural guards OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
