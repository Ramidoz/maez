"""S7.1 local WebAuthn credential registry and restore tests."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path


NOW = "2026-05-18T10:00:00+00:00"
LATER = "2026-05-18T10:01:00+00:00"


class S71CredentialRegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "memory" / "s7_1_webauthn"

    def tearDown(self):
        self._tmp.cleanup()

    def _store(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        return S7WebAuthnBootstrapStore(self.root)

    def _record(self, credential_ref: str, *, kind: str, confidence: str = "confirmed_distinct"):
        from core.governance.s7_webauthn_bootstrap import FounderWebAuthnCredentialRecord

        return FounderWebAuthnCredentialRecord.build(
            credential_ref=credential_ref,
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user",),
            public_key=f"public-key-{credential_ref}",
            sign_count=0,
            rp_id="localhost",
            origin="http://localhost:11437",
            created_at=NOW,
            backup_credential=(kind == "backup"),
            enabled=True,
            credential_kind=kind,
            label=f"{kind} key",
            registration_challenge_id=f"challenge-{credential_ref}",
            attestation_format="packed",
            aaguid="00112233-4455-6677-8899-aabbccddeeff",
            authenticator_attachment="cross-platform",
            backup_eligible=False,
            backed_up=False,
            transports=("usb",),
            library_name="webauthn",
            library_version="2.7.0",
            sign_count_mode="advancing",
            uv_capable=True,
            uv_required_for_guarded=True,
            distinct_device_confidence=confidence,
        )

    def test_036_primary_credential_stores_sealed_s7_fields(self):
        store = self._store()
        primary = self._record("cred-primary", kind="primary")

        store.store_credential(primary)
        loaded = store.get_credential("cred-primary")

        self.assertEqual(loaded.actor_handle_hmac, primary.actor_handle_hmac)
        self.assertEqual(loaded.role_names, ("bonded_user",))
        self.assertEqual(loaded.rp_id, "localhost")
        self.assertEqual(loaded.origin, "http://localhost:11437")
        self.assertFalse(loaded.backup_credential)
        self.assertTrue(loaded.enabled)

    def test_037_backup_credential_stores_sealed_s7_fields(self):
        store = self._store()
        backup = self._record("cred-backup", kind="backup")

        store.store_credential(backup)
        loaded = store.get_credential("cred-backup")

        self.assertEqual(loaded.credential_kind, "backup")
        self.assertTrue(loaded.backup_credential)
        self.assertEqual(loaded.ceremony_kind, "founder_local_webauthn")

    def test_038_s7_1_extension_fields_persist(self):
        store = self._store()
        primary = self._record("cred-primary", kind="primary")

        store.store_credential(primary)
        loaded = store.get_credential("cred-primary")

        self.assertEqual(loaded.registration_challenge_id, "challenge-cred-primary")
        self.assertEqual(loaded.attestation_format, "packed")
        self.assertEqual(loaded.transports, ("usb",))
        self.assertEqual(loaded.library_name, "webauthn")
        self.assertEqual(loaded.sign_count_mode, "advancing")
        self.assertEqual(loaded.distinct_device_confidence, "confirmed_distinct")
        self.assertTrue(loaded.record_hash.startswith("sha256:"))

    def test_039_primary_and_backup_credential_ids_must_differ(self):
        store = self._store()
        store.store_credential(self._record("cred-shared", kind="primary"))

        with self.assertRaisesRegex(ValueError, "s7_credential_duplicate"):
            store.store_credential(self._record("cred-shared", kind="backup"))

    def test_040_backup_registration_excludes_existing_enabled_credentials(self):
        store = self._store()
        store.store_credential(self._record("cred-primary", kind="primary"))
        store.store_credential(replace(self._record("cred-disabled", kind="backup"), enabled=False))

        self.assertEqual(store.exclude_credentials_for_backup_registration(), ("cred-primary",))

    def test_041_same_physical_uncertainty_is_recorded(self):
        store = self._store()
        backup = self._record("cred-backup", kind="backup", confidence="unknown")

        store.store_credential(backup)

        self.assertEqual(
            store.get_credential("cred-backup").distinct_device_confidence,
            "unknown",
        )

    def test_042_same_device_override_leaves_status_degraded_not_ready(self):
        store = self._store()
        store.store_credential(self._record("cred-primary", kind="primary"))
        store.store_credential(
            self._record("cred-backup", kind="backup", confidence="same_device_override")
        )

        state = store.credential_recovery_state()

        self.assertEqual(state["mode"], "degraded")
        self.assertFalse(state["manual_recovery_required"])
        self.assertEqual(state["distinct_device_confidence"], "same_device_override")

    def test_043_disabled_credential_cannot_authorize(self):
        store = self._store()
        store.store_credential(replace(self._record("cred-primary", kind="primary"), enabled=False))

        self.assertFalse(store.credential_can_authorize("cred-primary"))

    def test_044_reenable_requires_existing_enabled_credential_or_fails(self):
        store = self._store()
        store.store_credential(replace(self._record("cred-primary", kind="primary"), enabled=False))

        result = store.reenable_credential(
            "cred-primary",
            authorization_id="authz-1",
            now=LATER,
        )

        self.assertEqual(result, {"ok": False, "error": "s7_credential_setup_incomplete"})

    def test_045_reenable_records_authorization_id(self):
        store = self._store()
        store.store_credential(self._record("cred-primary", kind="primary"))
        store.store_credential(replace(self._record("cred-backup", kind="backup"), enabled=False))

        result = store.reenable_credential(
            "cred-backup",
            authorization_id="authz-1",
            now=LATER,
        )

        self.assertEqual(result, {"ok": True, "credential_ref": "cred-backup"})
        self.assertEqual(store.get_credential("cred-backup").reenabled_by_authorization_id, "authz-1")

    def test_046_registry_missing_yields_manual_recovery_required_with_cause(self):
        store = self._store()
        store.db_path.unlink()

        state = store.credential_recovery_state()

        self.assertEqual(state["mode"], "manual_recovery_required")
        self.assertEqual(state["manual_recovery_cause"], "registry_missing")

    def test_047_restore_invalidates_active_bootstrap_and_challenges(self):
        store = self._store()
        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"r" * 32,
        )
        store.create_challenge(
            challenge_id="challenge-1",
            challenge_kind="register_primary",
            expires_at=LATER,
        )

        store.mark_restored(now=LATER)

        self.assertEqual(store.bootstrap_state(now=LATER), "absent")
        self.assertFalse(store.challenge_is_active("challenge-1", now=NOW))
        with closing(sqlite3.connect(store.db_path)) as conn:
            revoked_at = conn.execute(
                "SELECT revoked_at FROM s7_bootstrap_intents WHERE intent_id = ?",
                (intent.intent_id,),
            ).fetchone()[0]
        self.assertEqual(revoked_at, LATER)

    def test_048_restore_preserves_enabled_credential_records(self):
        store = self._store()
        store.store_credential(self._record("cred-primary", kind="primary"))

        store.mark_restored(now=LATER)

        self.assertIsNotNone(store.get_credential("cred-primary"))
        self.assertTrue(store.credential_can_authorize("cred-primary"))

    def test_049_restore_never_reopens_bootstrap_after_closed_marker(self):
        store = self._store()
        store.set_bootstrap_closed_at(NOW)

        store.mark_restored(now=LATER)

        self.assertEqual(store.bootstrap_state(now=LATER), "closed")

    def test_050_store_permissions_are_private(self):
        store = self._store()

        self.assertEqual(store.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(store.db_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(store.audit_path.stat().st_mode & 0o777, 0o600)

    def test_051_same_file_record_hash_detects_corruption_not_l1_tamper_resistance(self):
        store = self._store()
        store.store_credential(self._record("cred-primary", kind="primary"))

        with closing(sqlite3.connect(store.db_path)) as conn:
            conn.execute(
                "UPDATE s7_founder_webauthn_credentials SET label = ? WHERE credential_ref = ?",
                ("tampered label", "cred-primary"),
            )
            conn.commit()

        with self.assertRaisesRegex(RuntimeError, "s7_record_hash_mismatch"):
            store.get_credential("cred-primary")

    def test_decision_22_manifest_includes_s7_1_ceremony_store(self):
        manifest = json.loads(Path("scripts/backup/backup_state_manifest.json").read_text())
        paths = {entry["path"] for entry in manifest["entries"]}

        self.assertIn("memory/s7_1_webauthn", paths)


if __name__ == "__main__":
    unittest.main()
