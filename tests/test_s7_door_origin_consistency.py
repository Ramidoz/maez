"""S7 WebAuthn DOOR origin consistency.

The human-facing ceremony pointer (skills/surface/s7_ceremony_bridge.py) must
point the owner's browser at the SAME host the WebAuthn ceremony binds to. The
ceremony binds origin "http://localhost:11437" everywhere
(core/governance/s7_webauthn_ceremony.py, s7_webauthn_bootstrap.py). py_webauthn
exact-matches the browser-reported Origin, so a pointer at 127.0.0.1 makes the
browser report "http://127.0.0.1:11437" and the ceremony REJECTS.

This canonicalizes the pointer TOWARD localhost (the already-bound origin). It
does NOT loosen the origin-binding invariant — that guard must keep rejecting
127.0.0.1, which the third test asserts.
"""

import unittest
from urllib.parse import urlsplit

NOW = "2026-05-18T10:00:00+00:00"

EXPECTED_ORIGIN = "http://localhost:11437"


class DoorOriginConsistencyTest(unittest.TestCase):
    def _pointer(self) -> str:
        from skills.surface.s7_ceremony_bridge import LiveBridgeDeps

        # ceremony_pointer_for is a pure URL builder; call it unbound to avoid
        # constructing the full pipeline-backed bridge.
        return LiveBridgeDeps.ceremony_pointer_for(
            object.__new__(LiveBridgeDeps), "card-xyz"
        )

    def test_pointer_uses_localhost_origin(self):
        pointer = self._pointer()
        self.assertTrue(
            pointer.startswith("http://localhost:11437"),
            f"pointer must canonicalize to the bound origin, got {pointer!r}",
        )

    def test_pointer_host_matches_bound_origin(self):
        pointer_host = urlsplit(self._pointer()).hostname
        origin_host = urlsplit(EXPECTED_ORIGIN).hostname
        self.assertEqual(pointer_host, origin_host)
        self.assertEqual(pointer_host, "localhost")

    def test_pointer_still_targets_cockpit_proof_route_with_card_fragment(self):
        pointer = self._pointer()
        self.assertIn("/cockpit/s7-webauthn-proof", pointer)
        self.assertTrue(pointer.endswith("#card-xyz"))

    def test_origin_binding_invariant_still_rejects_127_0_0_1(self):
        """Guard we did NOT loosen: the binding invariant must still reject
        a credential record bound to 127.0.0.1 / http://127.0.0.1:11437."""
        from core.governance.s7_webauthn_bootstrap import (
            FounderWebAuthnCredentialRecord,
        )

        def build(rp_id: str, origin: str):
            return FounderWebAuthnCredentialRecord.build(
                credential_ref="cred-guard",
                actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
                role_names=("bonded_user",),
                public_key="public-key-guard",
                sign_count=0,
                rp_id=rp_id,
                origin=origin,
                created_at=NOW,
                backup_credential=False,
                enabled=True,
                credential_kind="primary",
                label="primary key",
                registration_challenge_id="challenge-guard",
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
                distinct_device_confidence="confirmed_distinct",
            )

        # localhost binding is accepted (sanity).
        build("localhost", "http://localhost:11437")

        # 127.0.0.1 binding is rejected — invariant intact.
        with self.assertRaises(ValueError) as ctx:
            build("127.0.0.1", "http://127.0.0.1:11437")
        self.assertEqual(str(ctx.exception), "s7_origin_binding_invalid")


if __name__ == "__main__":
    unittest.main()
