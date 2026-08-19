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


def _ceremony_store(test):
    from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

    tmp = tempfile.TemporaryDirectory(prefix="maez-covenant-chal-")
    test.addCleanup(tmp.cleanup)
    return S7WebAuthnBootstrapStore(Path(tmp.name) / "s7_1_webauthn")


def _rendered_stub():
    from types import SimpleNamespace

    return SimpleNamespace(
        request_id="req-1",
        request_envelope_hash=H,
        rendered_text_hash="c" * 64,
        action_params_hash="d" * 64,
        authority_context_hash="e" * 64,
        maez_voice_consultation_hash=None,
        derived_aggregation_group="agg-1",
        nonce="nonce-1",
    )


class ChallengeSchemaExtensionTests(unittest.TestCase):
    """The covenant_phase2_of extension and its named seats (design §2).

    Compat gate half 1: the column is inert when null -- every existing
    challenge flow must be byte-identical in behaviour.
    """

    def test_column_exists_in_ddl_and_migration_map(self):
        import inspect
        from core.governance import s7_webauthn_bootstrap as b
        src = inspect.getsource(b)
        self.assertIn("covenant_phase2_of", src)
        # both seats: CREATE TABLE and the ALTER migration map
        create = src.index("CREATE TABLE IF NOT EXISTS s7_ceremony_challenges")
        self.assertIn("covenant_phase2_of", src[create:create + 2000])
        self.assertIn('"covenant_phase2_of": "TEXT"', src)

    def test_authorization_challenge_defaults_null_and_reader_projects_it(self):
        store = _ceremony_store(self)
        rendered = _rendered_stub()
        chal = store.create_authorization_challenge(
            rendered_statement=rendered,
            precondition_hash=H,
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-18T10:00:00Z", expires_at="2026-08-18T10:05:00Z",
            uv_required=True,
        )
        row = store.authorization_challenge_for_finish(
            challenge_id=chal["challenge_id"], session_binding="sess",
            internal_channel_binding="chan", now="2026-08-18T10:01:00Z",
        )
        self.assertIn("covenant_phase2_of", row)
        self.assertIsNone(row["covenant_phase2_of"])

    def test_stamped_challenge_round_trips(self):
        store = _ceremony_store(self)
        rendered = _rendered_stub()
        chal = store.create_authorization_challenge(
            rendered_statement=rendered,
            precondition_hash=H,
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-18T10:00:00Z", expires_at="2026-08-18T10:05:00Z",
            uv_required=True,
            covenant_phase2_of="1" * 64,
        )
        row = store.authorization_challenge_for_finish(
            challenge_id=chal["challenge_id"], session_binding="sess",
            internal_channel_binding="chan", now="2026-08-18T10:01:00Z",
        )
        self.assertEqual(row["covenant_phase2_of"], "1" * 64)

    def test_stamp_is_a_fingerprint_member(self):
        store = _ceremony_store(self)
        rendered = _rendered_stub()
        a = store.create_authorization_challenge(
            rendered_statement=rendered, precondition_hash=H,
            session_binding="s", internal_channel_binding="c",
            now="2026-08-18T10:00:00Z", expires_at="2026-08-18T10:05:00Z",
            uv_required=True,
        )
        b2 = store.create_authorization_challenge(
            rendered_statement=rendered, precondition_hash=H,
            session_binding="s", internal_channel_binding="c",
            now="2026-08-18T10:00:00Z", expires_at="2026-08-18T10:05:00Z",
            uv_required=True, covenant_phase2_of="1" * 64,
        )
        self.assertNotEqual(a["challenge_hash"], b2["challenge_hash"])


NOW = "2026-08-18T10:00:00Z"


class _CovenantVerifier:
    """Advancing sign count, like a real authenticator -- a constant count
    trips the live clone-detection in advance_sign_count (found the hard
    way: s7_clone_suspected on the second tap)."""

    package_name = "webauthn"

    def __init__(self):
        self._count = 0

    def dependency_state(self):
        return {"ok": True, "library_name": "webauthn", "library_version": "2.7.1"}

    def verify_authentication_response(self, **_kw):
        self._count += 1
        return {
            "ok": True, "credential_ref": "cred-primary", "sign_count": self._count,
            "user_presence": True, "user_verification": True,
        }


def _seed_credential(store, ref="cred-primary", kind="primary"):
    from core.governance.s7_webauthn_bootstrap import FounderWebAuthnCredentialRecord

    store.store_credential(FounderWebAuthnCredentialRecord.build(
        credential_ref=ref,
        actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
        role_names=("bonded_user",), public_key=f"pk-{ref}", sign_count=0,
        rp_id="localhost", origin="http://localhost:11437", created_at=NOW,
        backup_credential=(kind == "backup"), enabled=True, credential_kind=kind,
        label=f"{kind} key", registration_challenge_id=f"challenge-{ref}",
        attestation_format="packed",
        aaguid="00112233-4455-6677-8899-aabbccddeeff",
        authenticator_attachment="cross-platform", backup_eligible=False,
        backed_up=False, transports=("usb",), library_name="webauthn",
        library_version="2.7.1", sign_count_mode="advancing", uv_capable=True,
        uv_required_for_guarded=True, distinct_device_confidence="confirmed_distinct",
    ))


def _covenant_rendered(work_class="covenant_touching_change"):
    from types import SimpleNamespace

    return SimpleNamespace(
        request_id="req-cov-1",
        request_envelope_hash=H,
        rendered_text_hash="c" * 64,
        action_params_hash="d" * 64,
        authority_context_hash="e" * 64,
        maez_voice_consultation_hash=None,
        derived_aggregation_group="agg-cov",
        nonce="nonce-cov",
        derived_work_class=work_class,
    )


class Phase1RouteTests(unittest.TestCase):
    def setUp(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        self.tmp = tempfile.TemporaryDirectory(prefix="maez-cov-route-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bootstrap = S7WebAuthnBootstrapStore(root / "s7_1_webauthn")
        _seed_credential(self.bootstrap)
        _seed_credential(self.bootstrap, ref="cred-backup", kind="backup")
        self.phase_store = CovenantPhaseStore(root / "phases.sqlite3")
        self.service = S7LocalWebAuthnCeremonyService(
            verifier=_CovenantVerifier(),
            store_factory=lambda: self.bootstrap,
        )

    def _begin(self, rendered=None, now=NOW):
        return self.service.covenant_first_begin(
            now=now,
            rendered_statement=rendered or _covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
        )

    def _finish(self, challenge_id, rendered=None, now="2026-08-18T10:01:00Z"):
        return self.service.covenant_first_finish(
            now=now,
            rendered_statement=rendered or _covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
            request_json={
                "challenge_id": challenge_id,
                "credential_ref": "cred-primary",
                "authentication_response": {"clientDataJSON": "x"},
            },
            phase_store=self.phase_store,
        )

    def test_begin_refuses_non_covenant_work_class(self):
        r = self._begin(rendered=_covenant_rendered(work_class="self_modification"))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_work_class_required")

    def test_happy_path_writes_phase1_and_nothing_else(self):
        begun = self._begin()
        self.assertEqual(begun.status_code, 200)
        cid = begun.body["challenge_id"]
        fin = self._finish(cid)
        self.assertEqual(fin.status_code, 200, fin.body)
        binding = fin.body["phase1_binding_sha256"]
        row = self.phase_store.current_phase1(
            request_id="req-cov-1", now="2026-08-18T11:00:00Z"
        )
        self.assertEqual(row["binding_sha256"], binding)
        self.assertEqual(row["sign_count"], 1, "post-advance sign count persisted")
        self.assertEqual(row["rendered_text_hash"], "c" * 64)
        # no artifact anywhere
        import sqlite3 as _sq
        with _sq.connect(self.bootstrap.db_path) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM s7_authorization_artifacts_v2"
            ).fetchone()[0] if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='s7_authorization_artifacts_v2'"
            ).fetchone() else 0
        self.assertEqual(n, 0)

    def test_finish_replay_refused(self):
        begun = self._begin()
        cid = begun.body["challenge_id"]
        self.assertEqual(self._finish(cid).status_code, 200)
        replay = self.service.covenant_first_finish(
            now="2026-08-18T10:02:00Z",
            rendered_statement=_covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
            request_json={"challenge_id": cid, "credential_ref": "cred-primary",
                          "authentication_response": {"clientDataJSON": "x"}},
            phase_store=self.phase_store,
        )
        self.assertEqual(replay.status_code, 410)

    def test_d12_mismatch_refused(self):
        begun = self._begin()
        other = _covenant_rendered()
        other.rendered_text_hash = "9" * 64
        fin = self._finish(begun.body["challenge_id"], rendered=other)
        self.assertEqual(fin.status_code, 409)

    def test_second_tap_supersedes_live_phase1(self):
        first = self._finish(self._begin().body["challenge_id"])
        b1 = first.body["phase1_binding_sha256"]
        second = self._finish(
            self._begin(now="2026-08-18T11:58:00Z").body["challenge_id"],
            now="2026-08-18T12:00:00Z",
        )
        self.assertEqual(second.status_code, 200)
        row = self.phase_store.current_phase1(
            request_id="req-cov-1", now="2026-08-18T13:00:00Z"
        )
        self.assertEqual(row["supersedes_binding_sha256"], b1,
                         "the new tap IS the supersession act")


class RetentionByTestTests(unittest.TestCase):
    """Design §2: phase-1 retention is enumerated by test, not prose.

    Every load-bearing check token in the authorize path must appear in
    the covenant_first path, or be named in the frozen exclusion list.
    """

    REQUIRED = (
        "dependency_state", "_require_mapping", "_require_text",
        "_challenge_matches_rendered_d12", "get_credential",
        "bonded_user", "verify_authentication_response",
        "user_presence", "user_verification",
        "credential_can_authorize", "advance_sign_count",
        "consume_challenge", "credential_recovery_state",
    )
    FROZEN_EXCLUSIONS = (
        "mint_authorization_artifact",          # no authority at phase 1
        "_r11_challenge_projection_hash",        # R11 admits only cutover
        "authorization_voice_seat_recheck",      # no consultation consumed
        "authorization_aggregation_recheck",     # no authorized history row
        "allow_degraded_primary_only",           # degraded flags forbidden
    )

    def _sources(self):
        import inspect
        from core.governance import s7_webauthn_ceremony as svc

        cls = svc.S7LocalWebAuthnCeremonyService
        auth = inspect.getsource(cls.authorize_begin) + inspect.getsource(
            cls.authorize_finish
        )
        cov = inspect.getsource(cls.covenant_first_begin) + inspect.getsource(
            cls.covenant_first_finish
        )
        return auth, cov

    def test_every_required_check_is_retained(self):
        auth, cov = self._sources()
        for token in self.REQUIRED:
            self.assertIn(token, auth, f"{token} vanished from the authorize path?")
            self.assertIn(token, cov, f"phase-1 route dropped required check {token}")

    def test_exclusions_are_present_in_authorize_and_absent_in_covenant(self):
        auth, cov = self._sources()
        for token in self.FROZEN_EXCLUSIONS:
            self.assertIn(token, auth, f"exclusion {token} no longer in authorize?")
            self.assertNotIn(token, cov, f"{token} leaked into the phase-1 route")


class Phase2GateTests(unittest.TestCase):
    """authorize begin/finish gates for RULING-O classes (design §4)."""

    def setUp(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        self.tmp = tempfile.TemporaryDirectory(prefix="maez-cov-p2-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bootstrap = S7WebAuthnBootstrapStore(root / "s7_1_webauthn")
        _seed_credential(self.bootstrap)
        _seed_credential(self.bootstrap, ref="cred-backup", kind="backup")
        self.phase_store = CovenantPhaseStore(root / "phases.sqlite3")
        self.service = S7LocalWebAuthnCeremonyService(
            verifier=_CovenantVerifier(),
            store_factory=lambda: self.bootstrap,
        )

    def _phase1(self, recorded_at=NOW):
        return self.phase_store.insert_phase1(
            **{**_phase1_kwargs(request_id="req-cov-1",
                                rendered_text_hash="c" * 64,
                                recorded_at=recorded_at)}
        )

    def _begin(self, now, phase_store="default"):
        return self.service.authorize_begin(
            now=now,
            rendered_statement=_covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
            covenant_phase_store=(
                self.phase_store if phase_store == "default" else phase_store
            ),
        )

    def test_covenant_class_without_phase_store_refused(self):
        r = self._begin(now=NOW, phase_store=None)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_phase_store_required")

    def test_covenant_class_without_phase1_refused(self):
        r = self._begin(now=NOW)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_phase1_required")

    def test_immature_phase1_refused_at_begin(self):
        self._phase1(recorded_at=NOW)
        r = self._begin(now="2026-08-19T09:00:00Z")  # 23h later
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_cooling_off_immature")

    def test_matured_phase1_stamps_the_challenge(self):
        b1 = self._phase1(recorded_at=NOW)
        r = self._begin(now="2026-08-19T10:01:00Z")  # 24h+
        self.assertEqual(r.status_code, 200, r.body)
        row = self.bootstrap.authorization_challenge_for_finish(
            challenge_id=r.body["challenge_id"],
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-19T10:02:00Z",
        )
        self.assertEqual(row["covenant_phase2_of"], b1)

    def test_non_covenant_class_never_stamps(self):
        r = self.service.authorize_begin(
            now=NOW,
            rendered_statement=_covenant_rendered(work_class="self_modification"),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
        )
        self.assertEqual(r.status_code, 200, r.body)
        row = self.bootstrap.authorization_challenge_for_finish(
            challenge_id=r.body["challenge_id"],
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-18T10:01:00Z",
        )
        self.assertIsNone(row["covenant_phase2_of"])

    def _finish(self, challenge_id, now, phase_store="default"):
        return self.service.authorize_finish(
            now=now,
            envelope=_covenant_rendered(),
            rendered_statement=_covenant_rendered(),
            precondition_hash="f" * 64,
            maez_voice_consultation=None,
            session_binding="sess", internal_channel_binding="chan",
            request_json={"challenge_id": challenge_id,
                          "credential_ref": "cred-primary",
                          "authentication_response": {"clientDataJSON": "x"}},
            covenant_phase_store=(
                self.phase_store if phase_store == "default" else phase_store
            ),
        )

    def test_finish_refuses_unstamped_challenge_for_covenant_class(self):
        """A covenant-class finish on a challenge with no stamp: refused
        BEFORE verification (the stamp gate precedes everything after D12)."""
        b1 = self._phase1(recorded_at=NOW)
        del b1
        # craft an UNstamped authorize challenge for the same statement
        chal = self.bootstrap.create_authorization_challenge(
            rendered_statement=_covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-19T10:01:00Z", expires_at="2026-08-19T10:06:00Z",
            uv_required=True,
        )
        r = self._finish(chal["challenge_id"], now="2026-08-19T10:02:00Z")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_phase1_required")

    def test_finish_refuses_stamp_pointing_at_missing_phase1(self):
        chal = self.bootstrap.create_authorization_challenge(
            rendered_statement=_covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-19T10:01:00Z", expires_at="2026-08-19T10:06:00Z",
            uv_required=True, covenant_phase2_of="9" * 64,
        )
        r = self._finish(chal["challenge_id"], now="2026-08-19T10:02:00Z")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_phase1_unknown")

    def test_finish_refuses_covenant_class_without_phase_store(self):
        chal = self.bootstrap.create_authorization_challenge(
            rendered_statement=_covenant_rendered(),
            precondition_hash="f" * 64,
            session_binding="sess", internal_channel_binding="chan",
            now="2026-08-19T10:01:00Z", expires_at="2026-08-19T10:06:00Z",
            uv_required=True, covenant_phase2_of="9" * 64,
        )
        r = self._finish(chal["challenge_id"], now="2026-08-19T10:02:00Z",
                         phase_store=None)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.body["error"], "s7_covenant_phase_store_required")


class MintFollowupAndWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="maez-cov-wire-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "phases.sqlite3"
        self.store = CovenantPhaseStore(self.db)

    def test_read_only_store_never_creates_the_table(self):
        """The daemon's single-callsite rule: no creation authority on the
        live request path."""
        p = Path(self.tmp.name) / "fresh.sqlite3"
        ro = CovenantPhaseStore(p, create=False)
        self.assertIsNone(ro.current_phase1(request_id="r", now=NOW))
        import sqlite3 as _sq
        with _sq.connect(p) as conn:
            self.assertIsNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='s7_covenant_ceremony_phases_v1'"
            ).fetchone())
        with self.assertRaises(CovenantCeremonyRefusal) as c:
            ro.insert_phase1(**_phase1_kwargs())
        self.assertEqual(c.exception.reason, "covenant_store_unprovisioned")

    def test_phase2_after_mint_helper_writes_the_row(self):
        from core.governance.s7_webauthn_ceremony import _covenant_phase2_after_mint

        b1 = self.store.insert_phase1(**_phase1_kwargs(request_id="req-cov-1"))
        challenge = {
            "challenge_b64": "abc123",
            "rendered_text_hash": "c" * 64,
            "session_binding_hash": "d" * 64,
            "internal_channel_binding_hash": "e" * 64,
            "created_at": "2026-08-19T10:01:00Z",
            "expires_at": "2026-08-19T10:06:00Z",
            "covenant_phase2_of": b1,
        }
        result = _covenant_phase2_after_mint(
            phase_store=self.store,
            rendered_statement=_covenant_rendered(),
            challenge=challenge,
            challenge_id="chal-p2",
            credential_ref="cred-primary",
            sign_count=2,
            artifact_id="art-99",
            now="2026-08-19T10:02:00Z",
        )
        self.assertIsNone(result, "success returns None (no refusal)")
        p2 = self.store.phase2_for_request(request_id="req-cov-1")
        self.assertEqual(p2["artifact_id"], "art-99")
        self.assertEqual(p2["first_phase_binding_sha256"], b1)

    def test_finish_source_calls_the_helper_after_mint(self):
        import inspect
        from core.governance import s7_webauthn_ceremony as svc

        src = inspect.getsource(svc.S7LocalWebAuthnCeremonyService.authorize_finish)
        mint_at = src.index("mint_authorization_artifact(")
        self.assertIn("_covenant_phase2_after_mint", src[mint_at:],
                      "phase-2 row write must follow the mint")

    def test_consume_seat_wires_the_covenant_revalidator(self):
        """Dataflow pin: the sole SQL updater calls the covenant revalidator
        for highest-risk classes. Live proof belongs to the witness."""
        import inspect
        from core.governance import operator_user_boundary as oub

        src = inspect.getsource(oub.consume_for_execution_on_connection)
        self.assertIn("revalidate_covenant_ceremony_for_consumption", src)
        self.assertIn("_highest_risk_ceremony_required", src)


class DaemonThreadingTests(unittest.TestCase):
    def test_helper_returns_none_for_non_covenant_and_unprovisioned(self):
        from types import SimpleNamespace

        from daemon.maez_daemon import _covenant_evidence_for_authorization

        tmp = tempfile.TemporaryDirectory(prefix="maez-cov-daemon-")
        self.addCleanup(tmp.cleanup)
        store = SimpleNamespace(db_path=Path(tmp.name) / "ceremony.sqlite3")
        self.assertIsNone(_covenant_evidence_for_authorization(
            store, _covenant_rendered(work_class="self_modification"), NOW
        ))
        # covenant class, unprovisioned store: None, never a raise
        self.assertIsNone(_covenant_evidence_for_authorization(
            store, _covenant_rendered(), NOW
        ))

    def test_helper_assembles_from_a_complete_ceremony(self):
        from types import SimpleNamespace

        from daemon.maez_daemon import _covenant_evidence_for_authorization

        tmp = tempfile.TemporaryDirectory(prefix="maez-cov-daemon-")
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "ceremony.sqlite3"
        ps = CovenantPhaseStore(db)
        b1 = ps.insert_phase1(**_phase1_kwargs(request_id="req-cov-1"))
        ps.insert_phase2(
            **_phase1_kwargs(request_id="req-cov-1", challenge_id="chal-2",
                             challenge_created_at="2026-08-19T10:01:00Z",
                             recorded_at="2026-08-19T10:02:00Z"),
            first_phase_binding_sha256=b1, artifact_id="art-1",
        )
        ev = _covenant_evidence_for_authorization(
            SimpleNamespace(db_path=db), _covenant_rendered(), "2026-08-19T11:00:00Z"
        )
        self.assertIsNotNone(ev)
        self.assertEqual(ev.ceremony_kind, "cooling_off_second_confirmation")

    def test_both_construction_sites_thread_the_evidence(self):
        import inspect

        import daemon.maez_daemon as dm

        src = inspect.getsource(dm)
        self.assertEqual(
            src.count("covenant_ceremony_evidence=_covenant_evidence_for_authorization("),
            2,
            "both S7ExecutionAuthorization sites must thread the evidence",
        )
