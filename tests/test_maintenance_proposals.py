from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

from core.policies.autonomy_preferences import (
    AutonomyPreferences,
    PreferenceClass,
    PreferenceExpressedBy,
    preferences_for_bond_and_class,
)


_DIGEST_A = "hmac-sha256:" + "a" * 64
_DIGEST_B = "hmac-sha256:" + "b" * 64
_DIGEST_C = "hmac-sha256:" + "c" * 64


class MaintenanceProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "maintenance_proposals.db"
        self.pref_path = Path(self.tmp.name) / "autonomy_preferences.db"
        self.store = None

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _store(self):
        from core.policies.maintenance_proposals import MaintenanceProposals

        self.store = MaintenanceProposals(self.db_path)
        return self.store

    def _proposal(self, **overrides):
        from core.policies.maintenance_proposals import (
            EvidenceRef,
            MaintenanceProposal,
            ProposalScopeClass,
            ProposalStatus,
        )

        values = {
            "proposal_id": "proposal-1",
            "bond_id": "firstborn",
            "emitted_utc": datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            "scope_class": ProposalScopeClass.RANKING_REFINEMENT,
            "diagnosis_digest": _DIGEST_A,
            "proposed_patch_ref": "refs/heads/reddit-recall-fix",
            "predicted_effect": "Reddit-shaped queries open source-tagged rows first.",
            "sandbox_witness": None,
            "evidence_refs": (
                EvidenceRef(
                    evidence_kind="raw_memory",
                    ref_digest=_DIGEST_C,
                    observed_utc=datetime(2026, 5, 26, 11, 30, tzinfo=UTC),
                ),
            ),
            "status": ProposalStatus.PROPOSED,
            "ratified_utc": None,
            "decline_reason_digest": None,
        }
        values.update(overrides)
        return MaintenanceProposal(**values)

    def test_dataclass_refuses_missing_bond_id(self):
        with self.assertRaisesRegex(ValueError, "bond_id is required"):
            self._proposal(bond_id="")

    def test_dataclass_refuses_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "emitted_utc must be timezone-aware UTC"):
            self._proposal(emitted_utc=datetime(2026, 5, 26, 12, 0))

    def test_dataclass_refuses_empty_evidence_refs(self):
        with self.assertRaisesRegex(ValueError, "evidence_refs are required"):
            self._proposal(evidence_refs=())

    def test_dataclass_refuses_non_hmac_diagnosis_digest(self):
        with self.assertRaisesRegex(ValueError, "diagnosis_digest must be hmac-sha256"):
            self._proposal(diagnosis_digest="plain text")

    def test_append_round_trips_and_schema_has_bond_scoped_fields(self):
        store = self._store()
        proposal = self._proposal()

        store.append(proposal)
        rows = store.proposals_for_bond("firstborn")

        self.assertEqual(rows, [proposal])
        with closing(sqlite3.connect(self.db_path)) as con:
            columns = {
                row[1]
                for row in con.execute("PRAGMA table_info(maintenance_proposals)").fetchall()
            }
        self.assertIn("bond_id", columns)
        self.assertIn("scope_class", columns)
        self.assertIn("evidence_refs_json", columns)

    def test_proposals_for_bond_refuses_cross_bond_reads(self):
        store = self._store()
        store.append(self._proposal(proposal_id="a", bond_id="bond-a"))
        store.append(self._proposal(proposal_id="b", bond_id="bond-b"))

        rows = store.proposals_for_bond("bond-a")

        self.assertEqual([row.proposal_id for row in rows], ["a"])
        self.assertEqual([row.bond_id for row in rows], ["bond-a"])

    def test_duplicate_proposal_id_is_rejected(self):
        store = self._store()
        proposal = self._proposal()

        store.append(proposal)
        with self.assertRaises(sqlite3.IntegrityError):
            store.append(proposal)

    def test_emit_proposal_persists_before_diagnostic_event(self):
        from core.policies.maintenance_proposals import emit_maintenance_proposal

        store = self._store()
        proposal = self._proposal()
        events = []

        def sink(event):
            self.assertEqual(
                store.get("firstborn", "proposal-1").proposal_id,
                "proposal-1",
            )
            events.append(event)

        emit_maintenance_proposal(proposal, store=store, diagnostic_sink=sink)

        self.assertEqual(events[0]["event_type"], "MAINTENANCE_PROPOSAL_EMITTED")
        self.assertEqual(events[0]["bond_id"], "firstborn")
        self.assertEqual(events[0]["proposal_id"], "proposal-1")
        self.assertEqual(events[0]["scope_class"], "ranking_refinement")

    def test_legacy_sandbox_witness_refused_at_append_update_and_emit(self):
        from core.policies.maintenance_proposals import (
            LegacySandboxWitness,
            emit_maintenance_proposal,
        )
        from core.policies.sandbox_witnesses import (
            WitnessRefusalReason,
            WitnessRefused,
        )

        store = self._store()
        legacy = LegacySandboxWitness(
            red_tests_passed=True,
            focused_tests_passed=True,
            scratch_canary_passed=True,
            witness_digest=_DIGEST_B,
        )

        with self.assertRaises(WitnessRefused) as append_ctx:
            store.append(self._proposal(sandbox_witness=legacy))
        self.assertEqual(
            append_ctx.exception.reason,
            WitnessRefusalReason.LEGACY_WITNESS_SHAPE_REFUSED,
        )

        clean = self._proposal()
        store.append(clean)
        with self.assertRaises(WitnessRefused) as update_ctx:
            store.update(replace(clean, sandbox_witness=legacy))
        self.assertEqual(
            update_ctx.exception.reason,
            WitnessRefusalReason.LEGACY_WITNESS_SHAPE_REFUSED,
        )

        with self.assertRaises(WitnessRefused):
            emit_maintenance_proposal(
                self._proposal(proposal_id="proposal-2", sandbox_witness=legacy),
                store=store,
            )

    def test_legacy_sandbox_witness_json_reads_only_through_legacy_surface(self):
        store = self._store()
        legacy_json = (
            '{"focused_tests_passed": true, "red_tests_passed": true, '
            f'"scratch_canary_passed": true, "witness_digest": "{_DIGEST_B}"}}'
        )
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                dedent(
                    """
                    INSERT INTO maintenance_proposals (
                        proposal_id,
                        bond_id,
                        emitted_utc,
                        scope_class,
                        diagnosis_digest,
                        proposed_patch_ref,
                        predicted_effect,
                        sandbox_witness_json,
                        evidence_refs_json,
                        status,
                        ratified_utc,
                        decline_reason_digest,
                        witness_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    "legacy-row",
                    "firstborn",
                    datetime(2026, 5, 26, 12, 0, tzinfo=UTC).isoformat(),
                    "ranking_refinement",
                    _DIGEST_A,
                    "refs/heads/legacy-row",
                    "Legacy row should not authorize current witness state.",
                    legacy_json,
                    (
                        '[{"evidence_kind": "raw_memory", '
                        f'"ref_digest": "{_DIGEST_C}", '
                        '"observed_utc": "2026-05-26T11:30:00+00:00"}]'
                    ),
                    "proposed",
                    None,
                    None,
                    None,
                ),
            )
            con.commit()

        loaded = store.get("firstborn", "legacy-row")

        self.assertIsNone(loaded.sandbox_witness)
        self.assertEqual(loaded.legacy_sandbox_witness_json, legacy_json)

    def test_legacy_sandbox_witness_json_refused_at_ratification(self):
        from core.policies.maintenance_proposals import ratify_maintenance_proposal
        from core.policies.sandbox_witnesses import (
            WitnessRefusalReason,
            WitnessRefused,
        )

        store = self._store()
        preference_store = AutonomyPreferences(self.pref_path)
        legacy_json = (
            '{"focused_tests_passed": true, "red_tests_passed": true, '
            f'"scratch_canary_passed": true, "witness_digest": "{_DIGEST_B}"}}'
        )
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                dedent(
                    """
                    INSERT INTO maintenance_proposals (
                        proposal_id,
                        bond_id,
                        emitted_utc,
                        scope_class,
                        diagnosis_digest,
                        proposed_patch_ref,
                        predicted_effect,
                        sandbox_witness_json,
                        evidence_refs_json,
                        status,
                        ratified_utc,
                        decline_reason_digest,
                        witness_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    "legacy-ratify",
                    "firstborn",
                    datetime(2026, 5, 26, 12, 0, tzinfo=UTC).isoformat(),
                    "ranking_refinement",
                    _DIGEST_A,
                    "refs/heads/legacy-ratify",
                    "Legacy row should not authorize ratification.",
                    legacy_json,
                    (
                        '[{"evidence_kind": "raw_memory", '
                        f'"ref_digest": "{_DIGEST_C}", '
                        '"observed_utc": "2026-05-26T11:30:00+00:00"}]'
                    ),
                    "proposed",
                    None,
                    None,
                    None,
                ),
            )
            con.commit()

        with self.assertRaises(WitnessRefused) as ctx:
            ratify_maintenance_proposal(
                bond_id="firstborn",
                proposal_id="legacy-ratify",
                ratified_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
                store=store,
                preference_store=preference_store,
            )

        self.assertEqual(
            ctx.exception.reason,
            WitnessRefusalReason.LEGACY_WITNESS_SHAPE_REFUSED,
        )
        self.assertEqual(
            store.get("firstborn", "legacy-ratify").status.value,
            "proposed",
        )

    def test_static_guard_refuses_new_production_write_to_legacy_sandbox_witness_json(self):
        source = Path("core/policies/maintenance_proposals.py").read_text(
            encoding="utf-8"
        )
        legacy_writer_calls = [
            line.strip()
            for line in source.splitlines()
            if "_legacy_sandbox_to_json(" in line
            and not line.strip().startswith("def _legacy_sandbox_to_json")
        ]

        self.assertEqual(legacy_writer_calls, [])
        self.assertIn("legacy_sandbox_witness_json", source)

    def test_ratify_updates_status_and_writes_owner_explicit_preference(self):
        from core.policies.maintenance_proposals import ratify_maintenance_proposal
        from core.policies.sandbox_witnesses import WitnessStatus

        store = self._store()
        preference_store = AutonomyPreferences(self.pref_path)
        store.append(self._proposal())

        ratified = ratify_maintenance_proposal(
            bond_id="firstborn",
            proposal_id="proposal-1",
            ratified_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
            store=store,
            preference_store=preference_store,
        )

        self.assertEqual(ratified.status.value, "ratified")
        prefs = preferences_for_bond_and_class(
            "firstborn",
            PreferenceClass.MAINTENANCE_RATIFICATION,
            store=preference_store,
        )
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].expressed_by, PreferenceExpressedBy.OWNER_EXPLICIT)
        self.assertEqual(prefs[0].preference_id, "maintenance-ratification:proposal-1")
        self.assertEqual(prefs[0].target_field, "maintenance_proposal_ratified")
        self.assertEqual(ratified.witness_status, WitnessStatus.UNWITNESSED_BY_OMISSION)
        self.assertEqual(
            store.get("firstborn", "proposal-1").witness_status,
            WitnessStatus.UNWITNESSED_BY_OMISSION,
        )

    def test_ratification_uses_current_witness_generation(self):
        from core.policies.maintenance_proposals import ratify_maintenance_proposal
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            SandboxWitnessRecord,
            SandboxWitnesses,
            WitnessStatus,
        )

        store = self._store()
        witness_store = SandboxWitnesses(Path(self.tmp.name) / "sandbox_witnesses.db")
        preference_store = AutonomyPreferences(self.pref_path)
        store.append(self._proposal(sandbox_witness=None))
        witness_store.append(
            SandboxWitnessRecord.new(
                bond_id="firstborn",
                proposal_id="proposal-1",
                witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                observed_effect_digest=_DIGEST_A,
                predicted_effect_digest=_DIGEST_B,
                artifact_digest=_DIGEST_C,
                captured_utc=datetime(2026, 5, 26, 12, 30, tzinfo=UTC),
            )
        )

        ratified = ratify_maintenance_proposal(
            bond_id="firstborn",
            proposal_id="proposal-1",
            ratified_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
            store=store,
            preference_store=preference_store,
            witness_store=witness_store,
        )

        self.assertEqual(ratified.witness_status, WitnessStatus.WITNESSED)
        self.assertEqual(
            store.get("firstborn", "proposal-1").witness_status,
            WitnessStatus.WITNESSED,
        )

    def test_ratify_does_not_mark_proposal_ratified_when_preference_write_fails(self):
        from core.policies.maintenance_proposals import ratify_maintenance_proposal

        class BrokenPreferenceStore:
            def append(self, preference):
                raise RuntimeError("preference write failed")

        store = self._store()
        store.append(self._proposal())

        with self.assertRaisesRegex(RuntimeError, "preference write failed"):
            ratify_maintenance_proposal(
                bond_id="firstborn",
                proposal_id="proposal-1",
                ratified_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
                store=store,
                preference_store=BrokenPreferenceStore(),
            )

        self.assertEqual(store.get("firstborn", "proposal-1").status.value, "proposed")

    def test_decline_path_is_real(self):
        from core.policies.maintenance_proposals import decline_maintenance_proposal

        store = self._store()
        store.append(self._proposal())

        declined = decline_maintenance_proposal(
            bond_id="firstborn",
            proposal_id="proposal-1",
            declined_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
            decline_reason_digest=_DIGEST_B,
            store=store,
        )

        self.assertEqual(declined.status.value, "declined")
        self.assertEqual(declined.decline_reason_digest, _DIGEST_B)

    def test_architectural_scope_is_not_in_closed_vocabulary(self):
        from core.policies.maintenance_proposals import ProposalScopeClass

        self.assertNotIn("architecture_change", {scope.value for scope in ProposalScopeClass})
