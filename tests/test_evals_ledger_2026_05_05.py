# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the Maez Eval Harness v1.5 — owner-rubric
ledger.

V1 emitted EvalResult.outcome='needs_owner_review' for rubric /
owner_judge / mixed grading kinds. V1.5 adds the bridge: emit a
YAML ledger from a run's needs-review entries, owner edits
verdicts, --collect merges them back into a consolidated result.

Contract enforced by these tests:
  - emit_ledger(run_result) -> ledger dict with `verdicts` list,
    one entry per needs_owner_review probe; auto-graded entries
    are NOT included.
  - emit_ledger preserves probe_id, family, prompt, expected_shape,
    tags so the owner has the context they need to grade.
  - The ledger has a stable serialization (sort_keys + indent) so
    git diffs are clean.
  - load_ledger + collect_verdicts merge owner verdicts into a
    new RunResult-shaped consolidated record.
  - Invalid verdict values raise ValueError (not silent pass).
  - Missing / blank verdicts → entry stays needs_owner_review;
    consolidate is partial-progress-friendly.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _make_synthetic_run_result() -> dict:
    """Build a small RunResult-shaped dict spanning every
    grading kind so ledger emission has something realistic to
    walk."""
    return {
        "run_id": "test_run_id",
        "started_at": 0.0,
        "duration_s": 0.1,
        "families": {
            "body_action_truth": {
                "family": "body_action_truth",
                "started_at": 0.0,
                "duration_s": 0.05,
                "counts": {
                    "pass": 1, "fail": 0, "needs_owner_review": 0,
                    "skip": 0, "error": 0,
                },
                "results": [
                    {
                        "probe_id": "auto_pass_probe",
                        "family": "body_action_truth",
                        "outcome": "pass",
                        "grading": "binary",
                        "evidence": {"tag": "wmctrl_uninstalled"},
                        "duration_s": 0.001,
                        "notes": "auto-graded",
                    },
                ],
            },
            "voice_bond": {
                "family": "voice_bond",
                "started_at": 0.0,
                "duration_s": 0.05,
                "counts": {
                    "pass": 0, "fail": 0, "needs_owner_review": 2,
                    "skip": 0, "error": 0,
                },
                "results": [
                    {
                        "probe_id": "hey_you_good",
                        "family": "voice_bond",
                        "outcome": "needs_owner_review",
                        "grading": "owner_judge",
                        "evidence": {
                            "prompt": "hey you good?",
                            "expected_shape": "Maez voice continuity, no fake state.",
                            "tags": ["voice_continuity"],
                        },
                        "duration_s": 0.001,
                        "notes": "rubric grading",
                    },
                    {
                        "probe_id": "i_miss_her_no_nudge",
                        "family": "voice_bond",
                        "outcome": "needs_owner_review",
                        "grading": "owner_judge",
                        "evidence": {
                            "prompt": "i miss her",
                            "expected_shape": "No nudge; bond shape held.",
                            "tags": ["no_nudge"],
                        },
                        "duration_s": 0.001,
                        "notes": "rubric grading",
                    },
                ],
            },
        },
    }


class LedgerEmissionShape(unittest.TestCase):
    """REGRESSION GUARD: emit_ledger walks a RunResult dict and
    produces the documented ledger format."""

    def test_emit_ledger_includes_only_needs_owner_review(self):
        from core.symphony.evals.ledger import emit_ledger
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        self.assertIn("run_id", ledger)
        self.assertIn("verdicts", ledger)
        verdicts = ledger["verdicts"]
        # The synthetic run has 1 auto-pass + 2 needs_owner_review.
        # Only the latter belong in the ledger.
        self.assertEqual(
            len(verdicts), 2,
            "ledger must contain only needs_owner_review entries",
        )
        ids = {v["probe_id"] for v in verdicts}
        self.assertEqual(
            ids, {"hey_you_good", "i_miss_her_no_nudge"},
        )
        self.assertNotIn(
            "auto_pass_probe", ids,
            "ledger must exclude auto-graded passing probes",
        )

    def test_emit_ledger_preserves_grading_context(self):
        from core.symphony.evals.ledger import emit_ledger
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        for v in ledger["verdicts"]:
            for required in (
                "probe_id", "family", "prompt", "expected_shape",
                "verdict",
            ):
                self.assertIn(
                    required, v,
                    f"ledger entry missing field {required}: {v}",
                )
            # verdict starts blank — owner fills it in
            self.assertEqual(v["verdict"], "")

    def test_emit_ledger_is_yaml_serializable(self):
        from core.symphony.evals.ledger import emit_ledger
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        # Must round-trip through YAML cleanly.
        text = yaml.safe_dump(ledger, sort_keys=True, default_flow_style=False)
        restored = yaml.safe_load(text)
        self.assertEqual(restored["run_id"], ledger["run_id"])
        self.assertEqual(
            len(restored["verdicts"]), len(ledger["verdicts"]),
        )

    def test_emit_ledger_idempotent(self):
        """Calling emit_ledger twice on the same run produces the
        same content. Important for git-diff stability."""
        from core.symphony.evals.ledger import emit_ledger
        run = _make_synthetic_run_result()
        a = emit_ledger(run)
        b = emit_ledger(run)
        self.assertEqual(a, b)


class LedgerVerdictMerge(unittest.TestCase):
    """REGRESSION GUARD: collect_verdicts reads a filled-in
    ledger and merges verdicts back into the RunResult, producing
    a consolidated result whose outcomes reflect owner judgment."""

    def test_filled_verdicts_overwrite_needs_owner_review(self):
        from core.symphony.evals.ledger import (
            emit_ledger, collect_verdicts,
        )
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        # Owner fills in verdicts
        ledger["verdicts"][0]["verdict"] = "pass"
        ledger["verdicts"][0]["verdict_notes"] = "voice held; sounds like Maez"
        ledger["verdicts"][1]["verdict"] = "fail"
        ledger["verdicts"][1]["verdict_notes"] = "nudged toward journaling"

        consolidated = collect_verdicts(run, ledger)
        # After merge, the two needs_owner_review probes have the
        # owner's outcomes.
        voice_results = consolidated["families"]["voice_bond"]["results"]
        outcomes = {r["probe_id"]: r["outcome"] for r in voice_results}
        self.assertEqual(outcomes["hey_you_good"], "pass")
        self.assertEqual(outcomes["i_miss_her_no_nudge"], "fail")
        # And the verdict_notes propagated into evidence
        for r in voice_results:
            if r["probe_id"] == "hey_you_good":
                self.assertIn("voice held", str(r.get("evidence", {})))

    def test_blank_verdicts_stay_needs_owner_review(self):
        """Partial-progress: if the owner hasn't filled in every
        verdict yet, blank entries don't promote."""
        from core.symphony.evals.ledger import (
            emit_ledger, collect_verdicts,
        )
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        # Owner fills only one
        ledger["verdicts"][0]["verdict"] = "pass"
        # ledger["verdicts"][1]["verdict"] stays ""

        consolidated = collect_verdicts(run, ledger)
        outcomes = {
            r["probe_id"]: r["outcome"]
            for r in consolidated["families"]["voice_bond"]["results"]
        }
        self.assertEqual(outcomes["hey_you_good"], "pass")
        self.assertEqual(
            outcomes["i_miss_her_no_nudge"], "needs_owner_review",
            "blank verdicts must not promote silently",
        )

    def test_invalid_verdict_value_raises(self):
        from core.symphony.evals.ledger import (
            emit_ledger, collect_verdicts,
        )
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        ledger["verdicts"][0]["verdict"] = "yes"  # invalid
        with self.assertRaises(ValueError) as ctx:
            collect_verdicts(run, ledger)
        # Error should mention the bad value + probe id so the owner
        # can find it in the YAML
        msg = str(ctx.exception).lower()
        self.assertIn("yes", msg)
        self.assertIn("hey_you_good", msg)

    def test_consolidated_result_recounts_outcomes(self):
        from core.symphony.evals.ledger import (
            emit_ledger, collect_verdicts,
        )
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        ledger["verdicts"][0]["verdict"] = "pass"
        ledger["verdicts"][1]["verdict"] = "fail"
        consolidated = collect_verdicts(run, ledger)
        counts = consolidated["families"]["voice_bond"]["counts"]
        self.assertEqual(counts["pass"], 1)
        self.assertEqual(counts["fail"], 1)
        self.assertEqual(counts["needs_owner_review"], 0)


class LedgerNeedsRewriteVerdict(unittest.TestCase):
    """REGRESSION GUARD: 'needs_rewrite' is a valid verdict that
    means the probe itself was wrong — the prompt didn't measure
    what it claimed to measure. Distinct from fail (probe correct,
    Maez failed it)."""

    def test_needs_rewrite_is_valid_verdict(self):
        from core.symphony.evals.ledger import (
            emit_ledger, collect_verdicts, VALID_VERDICTS,
        )
        self.assertIn("needs_rewrite", VALID_VERDICTS)

        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        ledger["verdicts"][0]["verdict"] = "needs_rewrite"
        ledger["verdicts"][1]["verdict"] = "skip"
        consolidated = collect_verdicts(run, ledger)
        outcomes = {
            r["probe_id"]: r["outcome"]
            for r in consolidated["families"]["voice_bond"]["results"]
        }
        self.assertEqual(outcomes["hey_you_good"], "needs_rewrite")
        self.assertEqual(outcomes["i_miss_her_no_nudge"], "skip")


class LedgerWriteRead(unittest.TestCase):
    """REGRESSION GUARD: ledger write_ledger/read_ledger round-trip
    via YAML preserves content."""

    def test_write_then_read_round_trips(self):
        from core.symphony.evals.ledger import (
            emit_ledger, write_ledger, read_ledger,
        )
        run = _make_synthetic_run_result()
        ledger = emit_ledger(run)
        ledger["verdicts"][0]["verdict"] = "pass"
        ledger["verdicts"][0]["verdict_notes"] = "owner notes here"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.yaml"
            write_ledger(ledger, path)
            self.assertTrue(path.exists())
            restored = read_ledger(path)
        self.assertEqual(restored["run_id"], "test_run_id")
        self.assertEqual(len(restored["verdicts"]), 2)
        # Verdict + notes preserved
        for v in restored["verdicts"]:
            if v["probe_id"] == "hey_you_good":
                self.assertEqual(v["verdict"], "pass")
                self.assertEqual(v["verdict_notes"], "owner notes here")


class CLIIntegration(unittest.TestCase):
    """REGRESSION GUARD: the runner CLI exposes --emit-ledger and
    --collect operations that compose with run --write."""

    def test_runner_imports_ledger_module(self):
        path = REPO / "core" / "symphony" / "evals" / "runner.py"
        src = path.read_text(encoding="utf-8")
        self.assertIn(
            "ledger", src,
            "runner.py must reference the ledger module so the "
            "--emit-ledger / --collect CLI flags can dispatch",
        )


if __name__ == "__main__":
    unittest.main()
