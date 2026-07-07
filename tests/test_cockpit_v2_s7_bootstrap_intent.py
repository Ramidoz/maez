import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest import mock

from core.governance.s7_webauthn_bootstrap import DEFAULT_BOOTSTRAP_TTL_MINUTES
from core.governance.s7_webauthn_bootstrap import MAX_BOOTSTRAP_TTL_MINUTES
from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore


NOW = "2026-07-08T10:00:00+00:00"
REAL_CEREMONY_DB = Path("memory/s7_1_webauthn/ceremony.sqlite3")


def _sha256_or_missing(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CockpitV2S7BootstrapIntentRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        self.wi = wi
        self.wi.app.config["TESTING"] = True
        self._tmp = tempfile.TemporaryDirectory()
        self.store_root = Path(self._tmp.name) / "s7_1_webauthn"

    def tearDown(self):
        self._tmp.cleanup()

    def _post(self, *, cockpit_v2="1", owner_auth=True, payload=None):
        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": cockpit_v2}, clear=False), (
            mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=owner_auth)
        ), mock.patch.object(self.wi, "_s7_bootstrap_store_root", return_value=self.store_root), (
            mock.patch.object(self.wi, "_s7_bootstrap_now_iso", return_value=NOW)
        ):
            response = self.wi.app.test_client().post(
                "/api/v2/cockpit/s7/bootstrap-intent",
                json=payload or {},
            )
        body = response.get_json()
        response.close()
        return response.status_code, body

    def test_route_returns_404_when_cockpit_v2_is_off(self):
        status, body = self._post(cockpit_v2="0")

        self.assertEqual(status, 404)
        self.assertEqual(body["reason"], "cockpit_v2_off")
        self.assertFalse((self.store_root / "ceremony.sqlite3").exists())

    def test_route_refuses_without_owner_private_auth(self):
        status, body = self._post(owner_auth=False)

        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "owner_auth_required")
        self.assertFalse((self.store_root / "ceremony.sqlite3").exists())

    def test_minted_intent_round_trips_through_register_begin_validator(self):
        status, body = self._post()
        store = S7WebAuthnBootstrapStore(self.store_root)

        self.assertEqual(status, 200)
        self.assertEqual(body["purpose"], "register_primary")
        self.assertTrue(body["intent_id"].startswith("s7_bootstrap_"))
        self.assertTrue(body["bootstrap_token"])
        self.assertTrue(
            store.bootstrap_intent_valid(
                intent_id=body["intent_id"],
                raw_token=body["bootstrap_token"],
                now=NOW,
            )
        )

    def test_default_ttl_is_five_minutes_and_requested_ttl_clamps_to_max(self):
        status, body = self._post()
        self.assertEqual(status, 200)
        self.assertEqual(
            body["expires_at"],
            (datetime.fromisoformat(NOW) + timedelta(minutes=DEFAULT_BOOTSTRAP_TTL_MINUTES)).isoformat(),
        )

        store = S7WebAuthnBootstrapStore(self.store_root)
        store.revoke_bootstrap_intent(
            body["intent_id"],
            now=NOW,
            effective_uid=os.getuid(),
        )
        status, clamped = self._post(payload={"expires_min": MAX_BOOTSTRAP_TTL_MINUTES + 5})

        self.assertEqual(status, 200)
        self.assertEqual(
            clamped["expires_at"],
            (datetime.fromisoformat(NOW) + timedelta(minutes=MAX_BOOTSTRAP_TTL_MINUTES)).isoformat(),
        )

    def test_audit_line_is_content_light_and_does_not_persist_raw_token(self):
        status, body = self._post()
        audit_path = self.store_root / "ceremony.audit.jsonl"
        row = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])

        self.assertEqual(status, 200)
        self.assertEqual(row["event"], "bootstrap_intent_created")
        self.assertEqual(row["purpose"], "register_primary")
        self.assertEqual(row["intent_id"], body["intent_id"])
        self.assertNotIn(body["bootstrap_token"], audit_path.read_text(encoding="utf-8"))
        self.assertNotIn("bootstrap_token", audit_path.read_text(encoding="utf-8"))
        self.assertNotIn("raw_token", audit_path.read_text(encoding="utf-8"))

    def test_real_ceremony_store_is_untouched_by_route_tests(self):
        before = _sha256_or_missing(REAL_CEREMONY_DB)

        self._post()

        self.assertEqual(_sha256_or_missing(REAL_CEREMONY_DB), before)


if __name__ == "__main__":
    unittest.main()
