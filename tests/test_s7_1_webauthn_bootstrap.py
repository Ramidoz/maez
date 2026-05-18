"""S7.1 local WebAuthn first-credential bootstrap tests."""

from __future__ import annotations

import base64
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


NOW = "2026-05-18T09:00:00+00:00"
FUTURE = "2026-05-18T09:10:00+00:00"
PAST = "2026-05-18T08:00:00+00:00"


class S71WebAuthnBootstrapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "memory" / "s7_1_webauthn"

    def tearDown(self):
        self._tmp.cleanup()

    def _store(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        return S7WebAuthnBootstrapStore(self.root)

    def test_001_empty_registry_without_bootstrap_reports_bootstrap_required(self):
        store = self._store()

        readiness = store.first_registration_readiness(now=NOW)

        self.assertEqual(
            readiness,
            {
                "ok": False,
                "error": "s7_bootstrap_required",
                "bootstrap_state": "absent",
            },
        )

    def test_002_bootstrap_cli_store_hashes_only_not_raw_token(self):
        store = self._store()

        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"a" * 32,
        )

        self.assertGreaterEqual(
            len(base64.urlsafe_b64decode(intent.raw_token + "===")),
            16,
        )
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute(
                "SELECT token_hash FROM s7_bootstrap_intents WHERE intent_id = ?",
                (intent.intent_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertNotIn(intent.raw_token, row[0])
            self.assertTrue(row[0].startswith("hmac:s7.1:bootstrap:"))

    def test_003_expired_bootstrap_token_is_rejected(self):
        store = self._store()
        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=1,
            now=PAST,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"b" * 32,
        )

        result = store.consume_for_first_primary(
            intent_id=intent.intent_id,
            raw_token=intent.raw_token,
            credential_ref="cred-primary",
            public_key="public-key",
            now=NOW,
        )

        self.assertEqual(result, {"ok": False, "error": "s7_bootstrap_invalid"})
        self.assertFalse(store.has_enabled_primary())

    def test_004_consumed_bootstrap_token_is_rejected_on_reuse(self):
        store = self._store()
        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"c" * 32,
        )

        first = store.consume_for_first_primary(
            intent_id=intent.intent_id,
            raw_token=intent.raw_token,
            credential_ref="cred-primary",
            public_key="public-key",
            now=NOW,
        )
        second = store.consume_for_first_primary(
            intent_id=intent.intent_id,
            raw_token=intent.raw_token,
            credential_ref="cred-second",
            public_key="public-key-2",
            now=NOW,
        )

        self.assertEqual(first, {"ok": True, "credential_ref": "cred-primary"})
        self.assertEqual(second, {"ok": False, "error": "s7_bootstrap_invalid"})
        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM s7_founder_webauthn_credentials "
                "WHERE credential_kind = 'primary' AND enabled = 1"
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_005_non_interactive_bootstrap_cli_invocation_is_rejected(self):
        store = self._store()

        with self.assertRaisesRegex(RuntimeError, "s7_bootstrap_non_interactive"):
            store.create_bootstrap_intent(
                purpose="register_primary",
                ttl_minutes=10,
                now=NOW,
                effective_uid=os.getuid(),
                is_interactive=False,
                tty_path=None,
                token_bytes=b"d" * 32,
            )

    def test_006_non_store_owner_uid_is_rejected(self):
        store = self._store()

        with self.assertRaisesRegex(RuntimeError, "s7_bootstrap_uid_mismatch"):
            store.create_bootstrap_intent(
                purpose="register_primary",
                ttl_minutes=10,
                now=NOW,
                effective_uid=os.getuid() + 1,
                is_interactive=True,
                tty_path="/dev/pts/test",
                token_bytes=b"e" * 32,
            )

    def test_007_only_one_unconsumed_unexpired_bootstrap_intent_may_exist(self):
        store = self._store()
        store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"f" * 32,
        )

        with self.assertRaisesRegex(RuntimeError, "s7_bootstrap_active_intent_exists"):
            store.create_bootstrap_intent(
                purpose="register_primary",
                ttl_minutes=10,
                now=NOW,
                effective_uid=os.getuid(),
                is_interactive=True,
                tty_path="/dev/pts/test",
                token_bytes=b"g" * 32,
            )

    def test_008_bootstrap_token_has_at_least_128_bits_of_entropy(self):
        store = self._store()

        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
        )

        self.assertGreaterEqual(
            len(base64.urlsafe_b64decode(intent.raw_token + "===")),
            16,
        )

    def test_009_bootstrap_ttl_cannot_exceed_ten_minutes(self):
        store = self._store()

        with self.assertRaisesRegex(ValueError, "s7_bootstrap_ttl_too_long"):
            store.create_bootstrap_intent(
                purpose="register_primary",
                ttl_minutes=11,
                now=NOW,
                effective_uid=os.getuid(),
                is_interactive=True,
                tty_path="/dev/pts/test",
            )

    def test_010_first_primary_consume_closes_bootstrap_and_invalidates_siblings(self):
        store = self._store()
        first = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"h" * 32,
        )
        store.revoke_bootstrap_intent(first.intent_id, now=NOW, effective_uid=os.getuid())
        second = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=os.getuid(),
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"i" * 32,
        )

        result = store.consume_for_first_primary(
            intent_id=second.intent_id,
            raw_token=second.raw_token,
            credential_ref="cred-primary",
            public_key="public-key",
            now=NOW,
        )

        self.assertEqual(result, {"ok": True, "credential_ref": "cred-primary"})
        self.assertEqual(store.bootstrap_state(now=NOW), "closed")
        with self.assertRaisesRegex(RuntimeError, "s7_bootstrap_closed"):
            store.create_bootstrap_intent(
                purpose="register_primary",
                ttl_minutes=10,
                now=NOW,
                effective_uid=os.getuid(),
                is_interactive=True,
                tty_path="/dev/pts/test",
            )
