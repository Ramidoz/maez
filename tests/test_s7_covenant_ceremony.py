# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""RED-first tests for the covenant ceremony phase store (design pass 4).

Frozen contract under test: two-phase no-mint ceremony; RULING C
parameters (24h floor, 7-day phase-1 lifetime, supersede-never-edit);
two digests with distinct domains; every constructor input persisted;
append-only supersession; the activation interlock that refuses
RULING-O consumption until 2b's owner-read receipt exists.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.governance.s7_covenant_ceremony import (
    COOLING_OFF_FLOOR_SECONDS,
    PHASE1_LIFETIME_SECONDS,
    CovenantPhaseStore,
    CovenantCeremonyRefusal,
    assemble_covenant_ceremony_evidence,
    covenant_phase1_binding,
    covenant_phase2_binding,
    revalidate_covenant_ceremony_for_consumption,
)

H = "a" * 64


def _phase1_kwargs(**over):
    kw = dict(
        request_id="req-1",
        request_envelope_hash=H,
        derived_work_class="covenant_touching_change",
        challenge_id="chal-1",
        challenge_b64_sha256="b" * 64,
        rendered_text_hash="c" * 64,
        session_binding_hash="d" * 64,
        internal_channel_binding_hash="e" * 64,
        credential_ref="cred-1",
        sign_count=7,
        challenge_created_at="2026-08-18T10:00:00Z",
        challenge_expires_at="2026-08-18T10:05:00Z",
        recorded_at="2026-08-18T10:00:30Z",
    )
    kw.update(over)
    return kw


class DigestTests(unittest.TestCase):
    def test_domains_are_distinct_and_versioned(self):
        p1 = covenant_phase1_binding(**_phase1_kwargs())
        self.assertEqual(len(p1), 64)
        p2 = covenant_phase2_binding(
            **_phase1_kwargs(challenge_id="chal-2"),
            first_phase_binding_sha256=p1,
            artifact_id="art-1",
        )
        self.assertNotEqual(p1, p2)
        # same inputs, different domain tags -> different digests
        self.assertNotEqual(
            covenant_phase1_binding(**_phase1_kwargs()),
            covenant_phase2_binding(
                **_phase1_kwargs(), first_phase_binding_sha256=H, artifact_id="a"
            ),
        )

    def test_every_input_moves_the_digest(self):
        base = covenant_phase1_binding(**_phase1_kwargs())
        for field, other in [
            ("request_id", "req-2"), ("challenge_id", "chal-9"),
            ("challenge_b64_sha256", "f" * 64), ("rendered_text_hash", "9" * 64),
            ("session_binding_hash", "8" * 64), ("credential_ref", "cred-2"),
            ("sign_count", 8), ("challenge_created_at", "2026-08-18T11:00:00Z"),
            ("recorded_at", "2026-08-18T11:00:30Z"),
        ]:
            self.assertNotEqual(
                base, covenant_phase1_binding(**_phase1_kwargs(**{field: other})),
                f"{field} must be a digest member",
            )


class PhaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="maez-covenant-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "test.sqlite3"
        self.store = CovenantPhaseStore(self.db)

    def test_phase1_insert_and_current_selection(self):
        b = self.store.insert_phase1(**_phase1_kwargs())
        row = self.store.current_phase1(
            request_id="req-1", now="2026-08-18T12:00:00Z"
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["binding_sha256"], b)
        self.assertEqual(
            row["phase_expires_at"], "2026-08-25T10:00:30Z",
            "phase lifetime is RULING C's 7 days from recorded_at",
        )

    def test_ruling_c_constants(self):
        self.assertEqual(COOLING_OFF_FLOOR_SECONDS, 24 * 3600)
        self.assertEqual(PHASE1_LIFETIME_SECONDS, 7 * 24 * 3600)

    def test_expired_phase1_is_not_current(self):
        self.store.insert_phase1(**_phase1_kwargs())
        self.assertIsNone(
            self.store.current_phase1(request_id="req-1", now="2026-08-26T00:00:00Z")
        )

    def test_supersession_is_append_only_single_successor(self):
        b1 = self.store.insert_phase1(**_phase1_kwargs())
        b2 = self.store.insert_phase1(
            **_phase1_kwargs(challenge_id="chal-2",
                             recorded_at="2026-08-18T12:00:00Z"),
            supersedes_binding_sha256=b1,
        )
        row = self.store.current_phase1(request_id="req-1", now="2026-08-18T13:00:00Z")
        self.assertEqual(row["binding_sha256"], b2, "current = the unsuperseded row")
        with self.assertRaises(CovenantCeremonyRefusal):
            self.store.insert_phase1(
                **_phase1_kwargs(challenge_id="chal-3",
                                 recorded_at="2026-08-18T12:30:00Z"),
                supersedes_binding_sha256=b1,
            )  # second successor for one predecessor

    def test_fresh_phase1_without_supersession_refused_when_live_one_exists(self):
        self.store.insert_phase1(**_phase1_kwargs())
        with self.assertRaises(CovenantCeremonyRefusal):
            self.store.insert_phase1(
                **_phase1_kwargs(challenge_id="chal-2",
                                 recorded_at="2026-08-18T12:00:00Z")
            )

    def test_phase2_requires_matured_current_phase1(self):
        b1 = self.store.insert_phase1(**_phase1_kwargs())
        # 23h59m later: immature
        with self.assertRaises(CovenantCeremonyRefusal) as c:
            self.store.insert_phase2(
                **_phase1_kwargs(challenge_id="chal-2",
                                 challenge_created_at="2026-08-19T09:59:00Z",
                                 recorded_at="2026-08-19T10:00:00Z"),
                first_phase_binding_sha256=b1,
                artifact_id="art-1",
            )
        self.assertEqual(c.exception.reason, "covenant_cooling_off_immature")
        # 24h+ later: mature (maturity measured challenge_created_at - phase1 recorded_at)
        b2 = self.store.insert_phase2(
            **_phase1_kwargs(challenge_id="chal-2",
                             challenge_created_at="2026-08-19T10:01:00Z",
                             recorded_at="2026-08-19T10:02:00Z"),
            first_phase_binding_sha256=b1,
            artifact_id="art-1",
        )
        self.assertEqual(len(b2), 64)

    def test_one_phase2_per_phase1(self):
        b1 = self.store.insert_phase1(**_phase1_kwargs())
        kw = _phase1_kwargs(challenge_id="chal-2",
                            challenge_created_at="2026-08-19T10:01:00Z",
                            recorded_at="2026-08-19T10:02:00Z")
        self.store.insert_phase2(**kw, first_phase_binding_sha256=b1, artifact_id="art-1")
        with self.assertRaises(CovenantCeremonyRefusal):
            self.store.insert_phase2(
                **_phase1_kwargs(challenge_id="chal-3",
                                 challenge_created_at="2026-08-19T11:00:00Z",
                                 recorded_at="2026-08-19T11:01:00Z"),
                first_phase_binding_sha256=b1, artifact_id="art-2",
            )

    def test_phase2_against_superseded_phase1_refused(self):
        b1 = self.store.insert_phase1(**_phase1_kwargs())
        self.store.insert_phase1(
            **_phase1_kwargs(challenge_id="chal-2", recorded_at="2026-08-18T12:00:00Z"),
            supersedes_binding_sha256=b1,
        )
        with self.assertRaises(CovenantCeremonyRefusal) as c:
            self.store.insert_phase2(
                **_phase1_kwargs(challenge_id="chal-9",
                                 challenge_created_at="2026-08-19T13:00:00Z",
                                 recorded_at="2026-08-19T13:01:00Z"),
                first_phase_binding_sha256=b1, artifact_id="art-1",
            )
        self.assertEqual(c.exception.reason, "covenant_phase1_not_current")

    def test_tampered_row_fails_seal_recompute(self):
        self.store.insert_phase1(**_phase1_kwargs())
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE s7_covenant_ceremony_phases_v1 SET recorded_at='2026-01-01T00:00:00Z'"
            )
        with self.assertRaises(CovenantCeremonyRefusal) as c:
            self.store.current_phase1(request_id="req-1", now="2026-08-18T12:00:00Z")
        self.assertEqual(c.exception.reason, "covenant_store_integrity_failure")

    def test_ddl_contract_drift_refuses(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("ALTER TABLE s7_covenant_ceremony_phases_v1 ADD COLUMN extra TEXT")
        with self.assertRaises(CovenantCeremonyRefusal):
            self.store.insert_phase1(**_phase1_kwargs())


class AssemblerAndInterlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="maez-covenant-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "test.sqlite3"
        self.store = CovenantPhaseStore(self.db)
        self.b1 = self.store.insert_phase1(**_phase1_kwargs())
        self.b2 = self.store.insert_phase2(
            **_phase1_kwargs(challenge_id="chal-2",
                             challenge_created_at="2026-08-19T10:01:00Z",
                             recorded_at="2026-08-19T10:02:00Z"),
            first_phase_binding_sha256=self.b1, artifact_id="art-1",
        )

    def test_assembles_only_from_rows(self):
        ev = assemble_covenant_ceremony_evidence(
            self.store, request_id="req-1", now="2026-08-19T11:00:00Z"
        )
        self.assertEqual(ev.ceremony_kind, "cooling_off_second_confirmation")
        self.assertEqual(ev.first_authorized_at, "2026-08-18T10:00:30Z")
        self.assertEqual(ev.second_confirmed_at, "2026-08-19T10:02:00Z")
        self.assertEqual(ev.second_confirmation_ref_hash, self.b2)

    def test_assembler_returns_none_without_phase2(self):
        store2 = CovenantPhaseStore(Path(self.tmp.name) / "t2.sqlite3")
        store2.insert_phase1(**_phase1_kwargs())
        self.assertIsNone(
            assemble_covenant_ceremony_evidence(
                store2, request_id="req-1", now="2026-08-19T11:00:00Z"
            )
        )

    def test_interlock_refuses_until_owner_read_receipt_exists(self):
        """The activation interlock: RULING-O consumption refuses while 2b's
        owner-read receipt table does not exist. Structurally non-authorizing,
        not politely unexecuted."""
        ev = assemble_covenant_ceremony_evidence(
            self.store, request_id="req-1", now="2026-08-19T11:00:00Z"
        )
        with sqlite3.connect(self.db) as conn:
            with self.assertRaises(CovenantCeremonyRefusal) as c:
                revalidate_covenant_ceremony_for_consumption(
                    connection=conn,
                    store=self.store,
                    evidence=ev,
                    request_id="req-1",
                    request_envelope_hash=H,
                    derived_work_class="covenant_touching_change",
                    artifact_id="art-1",
                    now="2026-08-19T11:00:00Z",
                )
        self.assertEqual(c.exception.reason, "owner_read_receipt_required")

    def test_revalidator_refuses_caller_built_evidence(self):
        from core.governance.operator_user_boundary import CovenantCeremonyEvidence

        forged = CovenantCeremonyEvidence(
            request_id="req-1", request_envelope_hash=H,
            ceremony_kind="cooling_off_second_confirmation",
            first_authorized_at="2026-08-18T10:00:30Z",
            second_confirmed_at="2026-08-19T10:02:00Z",
            second_confirmation_ref_hash="f" * 64,  # not the row's hash
            reviewed_equivalent_ref_hash=None,
        )
        with sqlite3.connect(self.db) as conn:
            with self.assertRaises(CovenantCeremonyRefusal) as c:
                revalidate_covenant_ceremony_for_consumption(
                    connection=conn, store=self.store, evidence=forged,
                    request_id="req-1", request_envelope_hash=H,
                    derived_work_class="covenant_touching_change",
                    artifact_id="art-1", now="2026-08-19T11:00:00Z",
                )
        self.assertIn(
            c.exception.reason,
            ("covenant_evidence_not_bound_to_rows", "owner_read_receipt_required"),
        )
        # and specifically: even with the interlock satisfied it must refuse
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE s7_consult_owner_read_receipts_v1 (artifact_id TEXT PRIMARY KEY)")
        with sqlite3.connect(self.db) as conn:
            with self.assertRaises(CovenantCeremonyRefusal) as c:
                revalidate_covenant_ceremony_for_consumption(
                    connection=conn, store=self.store, evidence=forged,
                    request_id="req-1", request_envelope_hash=H,
                    derived_work_class="covenant_touching_change",
                    artifact_id="art-1", now="2026-08-19T11:00:00Z",
                )
        self.assertEqual(c.exception.reason, "covenant_evidence_not_bound_to_rows")


if __name__ == "__main__":
    unittest.main()
