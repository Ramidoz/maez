from __future__ import annotations

import unittest


class SandboxWitnessVocabularyTests(unittest.TestCase):
    def test_paths_exposes_sandbox_witnesses_db(self):
        from core import paths

        self.assertEqual(
            paths.sandbox_witnesses_db().name,
            "sandbox_witnesses.db",
        )

    def test_closed_vocabularies_expose_v1_contract(self):
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            StalenessAnchorKind,
            WitnessRefusalReason,
            WitnessStatus,
        )

        self.assertEqual(
            {kind.value for kind in SandboxWitnessKind},
            {
                "worktree_red_test",
                "worktree_schema_diff",
                "scratch_db_transform",
                "dry_run_observation",
            },
        )
        self.assertIn("db_cursor", {kind.value for kind in StalenessAnchorKind})
        self.assertIn("witnessed", {status.value for status in WitnessStatus})
        self.assertIn(
            "legacy_witness_shape_refused",
            {reason.value for reason in WitnessRefusalReason},
        )
