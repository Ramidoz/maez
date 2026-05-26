from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path


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

    def test_store_appends_monotonic_generations_for_same_proposal(self):
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            SandboxWitnessRecord,
            SandboxWitnesses,
            WitnessStatus,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = SandboxWitnesses(Path(tmp) / "sandbox_witnesses.db")
            first = SandboxWitnessRecord.new(
                bond_id="firstborn",
                proposal_id="proposal-1",
                witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                observed_effect_digest="hmac-sha256:" + "a" * 64,
                predicted_effect_digest="hmac-sha256:" + "b" * 64,
                artifact_digest="hmac-sha256:" + "c" * 64,
                captured_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            )

            stored_first = store.append(first)
            stored_second = store.append(
                SandboxWitnessRecord.new(
                    bond_id="firstborn",
                    proposal_id="proposal-1",
                    witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                    observed_effect_digest="hmac-sha256:" + "d" * 64,
                    predicted_effect_digest="hmac-sha256:" + "b" * 64,
                    artifact_digest="hmac-sha256:" + "e" * 64,
                    captured_utc=datetime(2026, 5, 26, 12, 5, tzinfo=UTC),
                )
            )

            self.assertEqual(stored_first.generation, 1)
            self.assertEqual(stored_second.generation, 2)
            self.assertNotEqual(stored_first.witness_id, stored_second.witness_id)
            self.assertEqual(
                store.current_for_proposal("firstborn", "proposal-1"),
                stored_second,
            )
            self.assertEqual(len(store.family_for_proposal("firstborn", "proposal-1")), 2)
            self.assertEqual(stored_second.witness_status, WitnessStatus.WITNESSED)

    def test_store_persists_staleness_anchors_for_generation(self):
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            SandboxWitnessRecord,
            SandboxWitnesses,
            StalenessAnchor,
            StalenessAnchorKind,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = SandboxWitnesses(Path(tmp) / "sandbox_witnesses.db")
            stored = store.append(
                SandboxWitnessRecord.new(
                    bond_id="firstborn",
                    proposal_id="proposal-1",
                    witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                    observed_effect_digest="hmac-sha256:" + "a" * 64,
                    predicted_effect_digest="hmac-sha256:" + "b" * 64,
                    artifact_digest="hmac-sha256:" + "c" * 64,
                    captured_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
                    staleness_anchors=(
                        StalenessAnchor(
                            anchor_kind=StalenessAnchorKind.COMMIT_HASH,
                            anchor_name="worktree",
                            anchor_value="abc123",
                        ),
                        StalenessAnchor(
                            anchor_kind=StalenessAnchorKind.DB_CURSOR,
                            anchor_name="raw_memory:reddit_post_id",
                            anchor_value="2373",
                        ),
                    ),
                )
            )

            loaded = store.current_for_proposal("firstborn", "proposal-1")

            self.assertEqual(loaded, stored)
            self.assertEqual(
                [anchor.anchor_name for anchor in loaded.staleness_anchors],
                ["worktree", "raw_memory:reddit_post_id"],
            )
