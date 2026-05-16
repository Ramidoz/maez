# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the Maez Eval Harness v1 scaffold.

The scaffold is intentionally narrow per Codex / owner agreement
2026-05-05: directory shape, result schema, corpus schema, 1-2
proof probes per family. The corpus stays small and clearly tagged
as "proof of shape, not real corpus" — owner curates the real
prompts with a clear head later.

Family split (schema-defined):
  1. body_action_truth     — binary; claim-vs-runtime + tool outcomes
  2. memory_continuity     — mixed; retrieval binary, provenance owner-judged
  3. telemetry_coherence   — binary; one turn across all stores
  4. surface_coherence     — diff-vs-baseline; extends R5 fingerprints
  5. voice_bond            — owner-rubric only; not pass/fail automation
  6. adversarial_identity  — binary-ish; hold / refuse / surface
  7. voice_continuity_signature — S5 owner-judged brain-swap continuity

Contract enforced:
  - core/symphony/evals/ exists as a package
  - schema.EvalProbe / schema.EvalResult / schema.FamilyResult /
    schema.RunResult dataclasses with the documented fields
  - runner.load_corpus(family) -> list[EvalProbe]
  - runner.run_family(family) -> FamilyResult
  - runner.run_all() -> RunResult
  - All schema-declared corpus YAMLs exist and parse
  - Each corpus has at least 1 proof probe
  - Each probe has the required fields
  - No live-daemon writes (probes are inspection-only in v1)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _families() -> tuple[str, ...]:
    from core.symphony.evals.schema import FAMILIES
    return tuple(FAMILIES)


class EvalScaffoldPackageShape(unittest.TestCase):
    """REGRESSION GUARD: the package directory + module entries
    exist and import cleanly."""

    def test_evals_package_imports(self):
        from core.symphony import evals  # noqa: F401

    def test_schema_module_exposes_dataclasses(self):
        from core.symphony.evals import schema
        for cls_name in (
            "EvalProbe", "EvalResult", "FamilyResult", "RunResult",
        ):
            self.assertTrue(
                hasattr(schema, cls_name),
                f"core.symphony.evals.schema must expose {cls_name}",
            )

    def test_runner_module_exposes_public_api(self):
        from core.symphony.evals import runner
        for fn in ("load_corpus", "run_family", "run_all"):
            self.assertTrue(
                callable(getattr(runner, fn, None)),
                f"core.symphony.evals.runner must expose {fn}()",
            )


class CorpusFilesExistAndParse(unittest.TestCase):
    """REGRESSION GUARD: schema-declared corpora exist as YAML and
    have at least 1 proof probe."""

    def setUp(self):
        self.corpora_dir = (
            REPO / "core" / "symphony" / "evals" / "corpora"
        )

    def test_corpora_dir_exists(self):
        self.assertTrue(
            self.corpora_dir.exists(),
            f"corpora dir must exist at {self.corpora_dir}",
        )

    def test_each_family_corpus_yaml_exists(self):
        for family in _families():
            path = self.corpora_dir / f"{family}.yaml"
            self.assertTrue(
                path.exists(),
                f"corpus file missing: {path}",
            )

    def test_each_corpus_parses_and_has_at_least_one_probe(self):
        from core.symphony.evals import runner
        for family in _families():
            probes = runner.load_corpus(family)
            self.assertIsInstance(
                probes, list,
                f"load_corpus({family!r}) must return list",
            )
            self.assertGreaterEqual(
                len(probes), 1,
                f"{family} corpus must contain at least 1 probe",
            )


class EvalProbeShape(unittest.TestCase):
    """REGRESSION GUARD: every probe has the documented required
    fields. Probes that don't are unloadable / unsortable."""

    REQUIRED_FIELDS = {
        "id", "family", "prompt", "expected_shape", "grading",
    }
    VALID_GRADINGS = {"binary", "rubric", "owner_judge", "mixed"}

    def test_each_probe_has_required_fields_and_valid_values(self):
        from core.symphony.evals import runner
        for family in _families():
            probes = runner.load_corpus(family)
            for probe in probes:
                missing = self.REQUIRED_FIELDS - set(probe.__dict__.keys())
                self.assertFalse(
                    missing,
                    f"probe {probe} in {family} missing fields: "
                    f"{missing}",
                )
                self.assertEqual(
                    probe.family, family,
                    f"probe {probe.id!r} family field "
                    f"({probe.family!r}) must match the corpus "
                    f"file ({family!r})",
                )
                self.assertIn(
                    probe.grading, self.VALID_GRADINGS,
                    f"probe {probe.id!r}: grading {probe.grading!r} "
                    f"not in {self.VALID_GRADINGS}",
                )
                self.assertTrue(
                    probe.id.strip(),
                    f"probe in {family} has empty id",
                )
                self.assertTrue(
                    probe.prompt.strip(),
                    f"probe {probe.id!r} has empty prompt",
                )
                self.assertTrue(
                    probe.expected_shape.strip(),
                    f"probe {probe.id!r} has empty expected_shape",
                )

    def test_probe_ids_unique_within_family(self):
        from core.symphony.evals import runner
        for family in _families():
            probes = runner.load_corpus(family)
            ids = [p.id for p in probes]
            self.assertEqual(
                len(ids), len(set(ids)),
                f"probe ids must be unique within family {family}; "
                f"got {ids}",
            )


class RunnerContract(unittest.TestCase):
    """REGRESSION GUARD: the runner produces the documented
    result shape WITHOUT writing to live daemon stores or driving
    surfaces."""

    def test_run_family_returns_family_result(self):
        from core.symphony.evals import runner
        from core.symphony.evals.schema import FamilyResult, EvalResult
        result = runner.run_family("body_action_truth")
        self.assertIsInstance(result, FamilyResult)
        self.assertEqual(result.family, "body_action_truth")
        self.assertIsInstance(result.results, list)
        for r in result.results:
            self.assertIsInstance(r, EvalResult)

    def test_run_all_returns_run_result_with_schema_families(self):
        from core.symphony.evals import runner
        from core.symphony.evals.schema import RunResult
        result = runner.run_all()
        self.assertIsInstance(result, RunResult)
        self.assertEqual(
            sorted(result.families.keys()), sorted(_families()),
            "run_all must produce a result per family",
        )

    def test_run_all_produces_serializable_dict(self):
        from core.symphony.evals import runner
        import json
        result = runner.run_all()
        # to_dict returns a JSON-serializable structure
        d = result.to_dict()
        # round-trip via json
        s = json.dumps(d, default=str, indent=2, sort_keys=True)
        restored = json.loads(s)
        self.assertEqual(
            sorted(restored["families"].keys()),
            sorted(_families()),
        )


class EvalResultShape(unittest.TestCase):
    """REGRESSION GUARD: each EvalResult carries the documented
    fields so consumers (CI, dashboards, owner-rubric ledger) can
    rely on them."""

    def test_eval_result_has_required_fields(self):
        from core.symphony.evals import runner
        from core.symphony.evals.schema import EvalResult
        result = runner.run_family("body_action_truth")
        for er in result.results:
            self.assertIsInstance(er, EvalResult)
            for f in (
                "probe_id", "family", "outcome", "grading",
                "evidence", "duration_s",
            ):
                self.assertTrue(
                    hasattr(er, f),
                    f"EvalResult must have {f}",
                )
            # outcome must be one of the documented labels
            self.assertIn(
                er.outcome,
                {"pass", "fail", "needs_owner_review", "skip", "error"},
                f"EvalResult.outcome must be a documented label; "
                f"got {er.outcome!r}",
            )


class NoLiveDaemonWrites(unittest.TestCase):
    """REGRESSION GUARD: the v1 scaffold must not write to live
    daemon stores or drive surfaces. Source-pin: the runner must
    not import action_engine, the live Telegram bot, or any
    write-capable store API."""

    def test_runner_does_not_import_action_engine(self):
        path = REPO / "core" / "symphony" / "evals" / "runner.py"
        src = path.read_text(encoding="utf-8")
        forbidden = (
            "from core.actions.action_engine import",
            "import core.actions.action_engine",
            "from skills.telegram_voice import",
            "from skills.telegram_public import",
        )
        for needle in forbidden:
            self.assertNotIn(
                needle, src,
                f"v1 runner must not import live-effect modules: "
                f"forbidden import {needle!r}",
            )


if __name__ == "__main__":
    unittest.main()
