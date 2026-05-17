"""Decision 34 / ADR 0039 — S7 Operator/User Role Boundary tests."""

from __future__ import annotations

import unittest


NOW = "2026-05-17T16:00:00+00:00"
FUTURE = "2026-05-17T17:00:00+00:00"
PAST = "2026-05-17T15:00:00+00:00"


class S7VocabularyAndAuthorityContextTests(unittest.TestCase):
    def test_001_closed_role_vocabulary_accepts_s6_roles(self):
        from core.governance import operator_user_boundary as s7

        self.assertEqual(
            s7.ROLE_NAMES,
            frozenset({
                "bonded_user",
                "operator",
                "maintainer",
                "successor",
                "witness",
                "estate_executor",
            }),
        )

    def test_002_closed_role_vocabulary_rejects_unknown_role(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.validate_role_name("therapist")

    def test_003_closed_s6_scope_vocabulary_rejects_unknown_scope(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.validate_s6_scope_name("read_everything")

    def test_004_closed_work_class_vocabulary_rejects_unknown_work_class(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.validate_work_class("limited_steward")

    def test_005_closed_auth_method_vocabulary_rejects_otp(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.validate_auth_method("otp")

    def test_006_closed_grant_source_vocabulary_rejects_unknown_source(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.validate_grant_source("trust_scope_owner")

    def test_007_authority_context_defaults_to_no_authority(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext()

        self.assertEqual(ctx.role_names, ())
        self.assertEqual(ctx.allowed_scopes, ())
        self.assertFalse(ctx.verified)
        self.assertEqual(ctx.grant_source, "none")
        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_008_verified_false_never_authorizes_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="actor-1",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=False,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_009_missing_actor_id_never_authorizes_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_010_missing_role_projection_never_authorizes_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="actor-1",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=(),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_011_missing_grant_source_never_authorizes_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="actor-1",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=("operator",),
            grant_source="none",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_012_expired_authority_context_never_authorizes_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="actor-1",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=PAST,
            expires_at=PAST,
            verified=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_013_routing_trust_scope_maps_to_no_authority(self):
        from core.governance import operator_user_boundary as s7

        for trust_scope in ("owner", "owner.draft", "guest", "public", "rohit", "maez", "unknown"):
            with self.subTest(trust_scope=trust_scope):
                ctx = s7.authority_context_from_routing_trust_scope(trust_scope)
                self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_014_legacy_owner_literals_do_not_grant_authority(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.legacy_identity_projection(
            user_id="rohit",
            role="rohit",
            is_owner=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_015_literal_rohit_rejected_as_role_context(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.AuthorityContext(role_names=("rohit",))

    def test_016_operator_authorizes_routine_custody_when_verified(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="actor-1",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertTrue(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_017_maintainer_authorizes_routine_custody_when_verified(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="actor-1",
            actor_handle_hmac="hmac:s7:actor:" + ("a" * 64),
            role_names=("maintainer",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertTrue(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_018_plain_bonded_user_context_does_not_authorize_guarded_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="bonded-1",
            actor_handle_hmac="hmac:s7:bonded:" + ("b" * 64),
            role_names=("bonded_user",),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        for work_class in (
            "destructive_user_action",
            "self_modification",
            "covenant_touching_change",
            "capability_acquisition",
            "autonomy_lowering_or_protection_reducing",
        ):
            with self.subTest(work_class=work_class):
                self.assertFalse(s7.authorizes_work(ctx, work_class, now=NOW))

    def test_019_founder_compat_projection_cannot_authorize_guarded_work(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.founder_compat_authority_context(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("b" * 64),
            roles=("bonded_user", "operator", "maintainer"),
            created_at=NOW,
            expires_at=FUTURE,
        )

        self.assertTrue(s7.authorizes_work(ctx, "routine_custody", now=NOW))
        self.assertFalse(s7.authorizes_work(ctx, "self_modification", now=NOW))
        self.assertFalse(s7.authorizes_work(ctx, "covenant_touching_change", now=NOW))
        self.assertFalse(
            s7.authorizes_work(
                ctx,
                "autonomy_lowering_or_protection_reducing",
                now=NOW,
            ),
        )


if __name__ == "__main__":
    unittest.main()
