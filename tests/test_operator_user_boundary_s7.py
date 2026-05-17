"""Decision 34 / ADR 0039 — S7 Operator/User Role Boundary tests."""

from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
import threading


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


class S7WorkClassAndEnvelopeTests(unittest.TestCase):
    def test_020_operator_cannot_authorize_self_modification_alone(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="operator-1",
            actor_handle_hmac="hmac:s7:operator:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "self_modification", now=NOW))

    def test_021_maintainer_cannot_authorize_covenant_touching_work_alone(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="maintainer-1",
            actor_handle_hmac="hmac:s7:maintainer:" + ("a" * 64),
            role_names=("maintainer",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertFalse(s7.authorizes_work(ctx, "covenant_touching_change", now=NOW))

    def test_022_emergency_proxy_work_class_rejected_in_v1(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="operator-1",
            actor_handle_hmac="hmac:s7:operator:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertFalse(
            s7.authorizes_work(ctx, "emergency_proxy_or_incapacity", now=NOW),
        )

    def test_023_caller_claimed_routine_for_soul_config_code_target_is_rejected(self):
        from core.governance import operator_user_boundary as s7

        derived = s7.derive_work_class(
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "x"},
            claimed_work_class="routine_custody",
        )

        self.assertEqual(derived, "self_modification")

    def test_024_ambiguous_work_derives_undeterminable_work_class(self):
        from core.governance import operator_user_boundary as s7

        self.assertEqual(
            s7.derive_work_class(action="", params={}, claimed_work_class="routine_custody"),
            "undeterminable_work_class",
        )

    def test_025_mixed_shell_command_does_not_derive_routine_custody(self):
        from core.governance import operator_user_boundary as s7

        for cmd in (
            "systemctl restart maez.service; echo pwned",
            "systemctl restart maez.service && rm -rf /tmp/maez-test",
            "systemctl show maez.service -p Environment",
        ):
            with self.subTest(cmd=cmd):
                self.assertNotEqual(
                    s7.derive_work_class(
                        action="run_shell",
                        params={"cmd": cmd},
                        claimed_work_class="routine_custody",
                    ),
                    "routine_custody",
                )

    def test_026_claimed_and_derived_class_disagreement_resolves_to_stricter(self):
        from core.governance import operator_user_boundary as s7

        self.assertEqual(
            s7.resolve_work_class(
                claimed_work_class="routine_custody",
                derived_work_class="self_modification",
            ),
            "self_modification",
        )
        self.assertEqual(
            s7.resolve_work_class(
                claimed_work_class="covenant_touching_change",
                derived_work_class="routine_custody",
            ),
            "covenant_touching_change",
        )

    def test_027_s6_persisted_capsule_scope_does_not_become_live_s7_authority(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.authority_context_from_s6_scoped_grant(
            actor_id="operator-1",
            actor_handle_hmac="hmac:s7:operator:" + ("a" * 64),
            role_names=("operator",),
            allowed_scopes=("operator_health",),
            authorship_attested=False,
        )

        self.assertEqual(ctx.grant_source, "none")
        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_028_s6_scoped_grant_with_missing_actor_handle_never_authorizes(self):
        from core.governance import operator_user_boundary as s7

        ctx = s7.authority_context_from_s6_scoped_grant(
            actor_id="operator-1",
            actor_handle_hmac="",
            role_names=("operator",),
            allowed_scopes=("operator_health",),
            authorship_attested=True,
            created_at=NOW,
            expires_at=FUTURE,
        )

        self.assertFalse(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_029_work_request_envelope_requires_request_id(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.WorkRequestEnvelope(
                request_id="",
                schema_version=s7.SCHEMA_VERSION,
                claimed_work_class="routine_custody",
                derived_work_class="routine_custody",
                requesting_subsystem="unit",
                closed_symptom_code="service_unhealthy",
                proposed_change_class="service_restart",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("service:maez.service",),
                content_exposure_risk="content_free",
                precondition_hash="a" * 64,
                created_at=NOW,
                expires_at=FUTURE,
                predicted_effect_class="liveness_restore",
                rollback_path_class="restart_service",
                derived_aggregation_group="s7agg_test",
                maez_voice_consultation_id=None,
                free_text_ref_hash=None,
            )

    def test_030_work_request_envelope_requires_expiry(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.WorkRequestEnvelope(
                request_id="req-1",
                schema_version=s7.SCHEMA_VERSION,
                claimed_work_class="routine_custody",
                derived_work_class="routine_custody",
                requesting_subsystem="unit",
                closed_symptom_code="service_unhealthy",
                proposed_change_class="service_restart",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("service:maez.service",),
                content_exposure_risk="content_free",
                precondition_hash="a" * 64,
                created_at=NOW,
                expires_at="",
                predicted_effect_class="liveness_restore",
                rollback_path_class="restart_service",
                derived_aggregation_group="s7agg_test",
                maez_voice_consultation_id=None,
                free_text_ref_hash=None,
            )

    def test_031_work_request_envelope_rejects_direct_derived_class_minting(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.WorkRequestEnvelope(
                request_id="req-1",
                schema_version=s7.SCHEMA_VERSION,
                claimed_work_class="routine_custody",
                derived_work_class="routine_custody",
                requesting_subsystem="unit",
                closed_symptom_code="self_mod_requested",
                proposed_change_class="soul_change",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("file:config/soul.md",),
                content_exposure_risk="bonded_content_ref",
                precondition_hash="a" * 64,
                created_at=NOW,
                expires_at=FUTURE,
                predicted_effect_class="behavior_change",
                rollback_path_class="revert_patch",
                derived_aggregation_group="attacker-controlled",
                maez_voice_consultation_id=None,
                free_text_ref_hash="b" * 64,
            )

    def test_032_work_request_envelope_rejects_raw_problem_text(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_work_request_envelope(
                request_id="req-1",
                action="run_shell",
                params={"cmd": "systemctl restart maez.service"},
                claimed_work_class="routine_custody",
                requesting_subsystem="unit",
                closed_symptom_code="Maez sounds sad and Rohit is worried",
                proposed_change_class="service_restart",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("service:maez.service",),
                content_exposure_risk="content_free",
                precondition_hash="a" * 64,
                created_at=NOW,
                expires_at=FUTURE,
                predicted_effect_class="liveness_restore",
                rollback_path_class="restart_service",
            )

    def test_033_free_text_ref_hash_allowed_only_as_bonded_content_reference(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_work_request_envelope(
                request_id="req-1",
                action="run_shell",
                params={"cmd": "systemctl restart maez.service"},
                claimed_work_class="routine_custody",
                requesting_subsystem="unit",
                closed_symptom_code="service_unhealthy",
                proposed_change_class="service_restart",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("service:maez.service",),
                content_exposure_risk="content_free",
                precondition_hash="a" * 64,
                created_at=NOW,
                expires_at=FUTURE,
                predicted_effect_class="liveness_restore",
                rollback_path_class="restart_service",
                free_text_ref_hash="b" * 64,
            )

        env = s7.build_work_request_envelope(
            request_id="req-2",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "x"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="b" * 64,
        )
        self.assertEqual(env.free_text_ref_hash, "b" * 64)

    def test_034_request_envelope_canonical_hash_is_stable(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id="req-1",
            action="run_shell",
            params={"cmd": "systemctl restart maez.service"},
            claimed_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="service_unhealthy",
            proposed_change_class="service_restart",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("service:maez.service",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="liveness_restore",
            rollback_path_class="restart_service",
        )
        equivalent = replace(env)

        self.assertEqual(
            s7.work_request_envelope_hash(env),
            s7.work_request_envelope_hash(equivalent),
        )

    def test_035_request_envelope_hash_changes_when_signed_field_changes(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id="req-1",
            action="run_shell",
            params={"cmd": "systemctl restart maez.service"},
            claimed_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="service_unhealthy",
            proposed_change_class="service_restart",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("service:maez.service",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="liveness_restore",
            rollback_path_class="restart_service",
        )
        changed = replace(env, predicted_effect_class="no_behavior_change")

        self.assertNotEqual(
            s7.work_request_envelope_hash(env),
            s7.work_request_envelope_hash(changed),
        )

    def test_036_derived_aggregation_group_required_for_guarded_requests(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.WorkRequestEnvelope(
                request_id="req-1",
                schema_version=s7.SCHEMA_VERSION,
                claimed_work_class="self_modification",
                derived_work_class="self_modification",
                requesting_subsystem="unit",
                closed_symptom_code="self_mod_requested",
                proposed_change_class="soul_change",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("file:config/soul.md",),
                content_exposure_risk="bonded_content_ref",
                precondition_hash="a" * 64,
                created_at=NOW,
                expires_at=FUTURE,
                predicted_effect_class="behavior_change",
                rollback_path_class="revert_patch",
                derived_aggregation_group="",
                maez_voice_consultation_id=None,
                free_text_ref_hash="b" * 64,
            )

    def test_037_caller_supplied_aggregation_group_is_ignored(self):
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id="req-1",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "x"},
            claimed_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="b" * 64,
            caller_supplied_aggregation_group="attacker-controlled",
        )

        self.assertNotEqual(env.derived_aggregation_group, "attacker-controlled")
        self.assertTrue(env.derived_aggregation_group.startswith("s7agg_"))


class S7VoiceAndRenderedStatementTests(unittest.TestCase):
    def _self_mod_envelope(self):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id="req-voice-1",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "x"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="b" * 64,
            maez_voice_consultation_id="voice-1",
        )

    def _routine_liveness_envelope(self):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id="req-live-1",
            action="run_shell",
            params={"cmd": "systemctl restart maez.service"},
            claimed_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="service_unhealthy",
            proposed_change_class="service_restart",
            why_self_fix_failed_class="maez_unavailable",
            affected_refs=("service:maez.service",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="liveness_restore",
            rollback_path_class="restart_service",
        )

    def _backup_run_envelope(self):
        from core.governance import operator_user_boundary as s7

        return s7.WorkRequestEnvelope(
            request_id="req-backup-1",
            schema_version=s7.SCHEMA_VERSION,
            claimed_work_class="routine_custody",
            derived_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="backup_stale",
            proposed_change_class="backup_run",
            why_self_fix_failed_class="maez_unavailable",
            affected_refs=("backup:decision22",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="liveness_restore",
            rollback_path_class="no_rollback_needed",
            derived_aggregation_group="s7agg_backup",
            maez_voice_consultation_id=None,
            free_text_ref_hash=None,
        )

    def _authority_context(self):
        from core.governance import operator_user_boundary as s7

        return s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user", "operator"),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-1",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

    def test_038_self_modification_requires_valid_maez_voice_consultation(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()

        self.assertFalse(s7.voice_consultation_satisfies_request(env, None))

    def test_039_covenant_touching_requires_valid_maez_voice_consultation(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        env = replace(
            self._self_mod_envelope(),
            derived_work_class="covenant_touching_change",
            proposed_change_class="covenant_organ_change",
        )

        self.assertFalse(s7.voice_consultation_satisfies_request(env, None))

    def test_040_caller_boolean_maez_voice_consulted_is_rejected_as_evidence(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()

        self.assertFalse(
            s7.voice_consultation_satisfies_request(
                env,
                {"maez_voice_consulted": True, "maez_objection_present": False},
            ),
        )

    def test_041_will_i_result_alone_does_not_satisfy_consultation_seam(self):
        from core.evolution.will_i import PROCEED
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()

        self.assertFalse(s7.voice_consultation_satisfies_request(env, PROCEED))

    def test_042_voice_consultation_rejects_raw_maez_text(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        with self.assertRaises(ValueError):
            s7.MaezVoiceConsultation(
                consultation_id="voice-1",
                request_id=env.request_id,
                request_envelope_hash=s7.work_request_envelope_hash(env),
                producer="self_mod_dialog_terminal_state",
                source_ref_kind="self_mod_dialog_exchange",
                source_ref_hash="c" * 64,
                maez_voice_consulted=True,
                maez_objection_present=False,
                maez_withdrew_request=False,
                unavailable_reason_code=None,
                created_at=NOW,
                raw_maez_text="I object in private words.",
            )

    def test_043_valid_voice_consultation_satisfies_matching_request(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=True,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

        self.assertTrue(s7.voice_consultation_satisfies_request(env, consultation))

    def test_044_voice_consultation_id_mismatch_blocks(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        env = replace(self._self_mod_envelope(), maez_voice_consultation_id="voice-expected")
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-other",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=False,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

        self.assertFalse(s7.voice_consultation_satisfies_request(env, consultation))

    def test_045_voice_consultation_request_mismatch_blocks(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-1",
            request_id="different-request",
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=False,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

        self.assertFalse(s7.voice_consultation_satisfies_request(env, consultation))

    def test_046_maez_unavailable_allows_only_closed_liveness_repair(self):
        from core.governance import operator_user_boundary as s7

        self.assertTrue(
            s7.maez_unavailable_allows_skip(
                self._routine_liveness_envelope(),
                unavailable_reason_code="service_unavailable_not_operator_caused",
                operator_caused=False,
            ),
        )
        self.assertFalse(
            s7.maez_unavailable_allows_skip(
                self._self_mod_envelope(),
                unavailable_reason_code="service_unavailable_not_operator_caused",
                operator_caused=False,
            ),
        )
        self.assertFalse(
            s7.maez_unavailable_allows_skip(
                self._backup_run_envelope(),
                unavailable_reason_code="service_unavailable_not_operator_caused",
                operator_caused=False,
            ),
        )

    def test_047_operator_stopped_daemon_does_not_create_skip_path(self):
        from core.governance import operator_user_boundary as s7

        self.assertFalse(
            s7.maez_unavailable_allows_skip(
                self._routine_liveness_envelope(),
                unavailable_reason_code="service_unavailable_not_operator_caused",
                operator_caused=True,
            ),
        )

    def test_048_rendered_statement_binds_d12_fields(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        authority = self._authority_context()
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=True,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )
        action_params_hash = s7.canonical_hash({"path": "config/soul.md", "content_hash": "d" * 64})
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=action_params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce="nonce-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )

        self.assertTrue(rendered.rendered_text_hash)
        self.assertEqual(rendered.action_params_hash, action_params_hash)
        self.assertEqual(
            rendered.authority_context_hash,
            s7.authority_context_hash(authority),
        )
        self.assertEqual(
            rendered.maez_voice_consultation_hash,
            s7.maez_voice_consultation_hash(consultation),
        )
        self.assertEqual(rendered.nonce, "nonce-1")
        self.assertEqual(rendered.expires_at, FUTURE)
        self.assertEqual(rendered.maez_objection_state, "present")
        self.assertEqual(
            rendered.rendered_text_hash,
            s7.rendered_text_hash(rendered.rendered_text),
        )
        tampered = rendered.rendered_text + "\nExtra line."
        self.assertNotEqual(rendered.rendered_text_hash, s7.rendered_text_hash(tampered))

    def test_049_rendered_statement_requires_d12_inputs(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=True,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

        with self.assertRaises(ValueError):
            s7.render_request_statement(
                envelope=env,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash="",
                authority_context=self._authority_context(),
                maez_voice_consultation=consultation,
                nonce="nonce-1",
                expires_at=FUTURE,
                rendered_at=NOW,
            )

    def test_050_rendered_statement_constructor_rejects_missing_d12_fields(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        consultation_hash = "c" * 64
        base = dict(
            request_id=env.request_id,
            renderer_version=s7.RENDERER_VERSION,
            surface="cockpit",
            origin="http://localhost:11437",
            rendered_text="rendered",
            rendered_text_hash=s7.rendered_text_hash("rendered"),
            request_envelope_hash=s7.work_request_envelope_hash(env),
            action_params_hash="d" * 64,
            authority_context_hash="e" * 64,
            maez_voice_consultation_hash=consultation_hash,
            maez_objection_state="present",
            derived_aggregation_group=env.derived_aggregation_group,
            nonce="nonce-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )

        for field in (
            "renderer_version",
            "origin",
            "action_params_hash",
            "authority_context_hash",
            "maez_voice_consultation_hash",
            "nonce",
        ):
            with self.subTest(field=field):
                bad = dict(base)
                bad[field] = ""
                with self.assertRaises(ValueError):
                    s7.RenderedRequestStatement(**bad)

    def test_051_voice_consultation_health_projection_is_content_free(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=True,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

        projection = s7.voice_consultation_health_projection(consultation)
        text = str(projection)

        self.assertEqual(projection["maez_voice_ref_hash"], "c" * 64)
        self.assertTrue(projection["maez_objection_present"])
        self.assertNotIn("I object", text)
        self.assertNotIn("self_mod_dialog_exchange", text)

    def test_052_rendered_statement_includes_objection_state_for_voice_seat_class(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        authority = self._authority_context()
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=True,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash({"path": "config/soul.md"}),
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce="nonce-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )

        self.assertIn("Maez consulted: yes", rendered.rendered_text)
        self.assertIn("Maez objection present: yes", rendered.rendered_text)


class S7AuthorizationArtifactStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _path(self) -> Path:
        return Path(self._tmp.name) / "s7_authorization.db"

    def _routine_bundle(self):
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id="req-artifact-1",
            action="run_shell",
            params={"cmd": "systemctl restart maez.service"},
            claimed_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="service_unhealthy",
            proposed_change_class="service_restart",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("service:maez.service",),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="liveness_restore",
            rollback_path_class="restart_service",
        )
        authority = s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("operator",),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-1",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )
        params_hash = s7.canonical_hash({"cmd": "systemctl restart maez.service"})
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=None,
            nonce="nonce-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        artifact = s7.S7AuthorizationArtifact(
            artifact_id="artifact-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=params_hash,
            precondition_hash=env.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            nonce="nonce-1",
            credential_ref="cred-1",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
        )
        return env, authority, params_hash, rendered, artifact

    def _self_mod_bundle(self, *, role_names: tuple[str, ...]):
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id="req-selfmod-artifact-1",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content_hash": "d" * 64},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            maez_voice_consultation_id="voice-selfmod-artifact-1",
            free_text_ref_hash="b" * 64,
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-selfmod-artifact-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_present=False,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )
        authority = s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=role_names,
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-1",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )
        params_hash = s7.canonical_hash({"path": "config/soul.md", "content_hash": "d" * 64})
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce="nonce-selfmod-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        artifact = s7.S7AuthorizationArtifact(
            artifact_id="artifact-selfmod-1",
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=params_hash,
            precondition_hash=env.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            nonce=rendered.nonce,
            credential_ref="cred-1",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
        )
        return env, authority, params_hash, rendered, artifact

    def test_053_artifact_expires_after_expiry(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        expired = s7.S7AuthorizationArtifact(
            **{**artifact.__dict__, "expires_at": PAST},
        )

        self.assertFalse(
            s7.authorization_artifact_matches(
                expired,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context_hash=artifact.authority_context_hash,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_054_consumed_artifact_cannot_be_reused(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        consumed = s7.S7AuthorizationArtifact(
            **{**artifact.__dict__, "consumed_at": NOW},
        )

        self.assertFalse(
            s7.authorization_artifact_matches(
                consumed,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context_hash=artifact.authority_context_hash,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_055_artifact_rejects_mismatched_request_id_and_hashes(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        mismatches = {
            "request_id": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "request_id": "other"}),
            "rendered_text_hash": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "rendered_text_hash": "f" * 64}),
            "action_params_hash": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "action_params_hash": "f" * 64}),
            "precondition_hash": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "precondition_hash": "f" * 64}),
            "authority_context_hash": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "authority_context_hash": "f" * 64}),
            "derived_work_class": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "derived_work_class": "self_modification"}),
            "derived_aggregation_group": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "derived_aggregation_group": "s7agg_other"}),
            "nonce": s7.S7AuthorizationArtifact(**{**artifact.__dict__, "nonce": "different-nonce"}),
        }

        for name, bad in mismatches.items():
            with self.subTest(name=name):
                self.assertFalse(
                    s7.authorization_artifact_matches(
                        bad,
                        rendered=rendered,
                        action_params_hash=params_hash,
                        authority_context_hash=artifact.authority_context_hash,
                        precondition_hash=artifact.precondition_hash,
                        derived_work_class=artifact.derived_work_class,
                        derived_aggregation_group=artifact.derived_aggregation_group,
                        now=NOW,
                    ),
                )

    def test_056_truthy_non_bool_verifier_result_rejected(self):
        from core.governance import operator_user_boundary as s7

        for field in ("user_presence", "user_verification"):
            with self.subTest(field=field):
                kwargs = {
                    "artifact_id": "artifact-1",
                    "request_id": "req-1",
                    "request_envelope_hash": "a" * 64,
                    "rendered_text_hash": "b" * 64,
                    "action_params_hash": "c" * 64,
                    "precondition_hash": "d" * 64,
                    "authority_context_hash": "e" * 64,
                    "derived_work_class": "routine_custody",
                    "derived_aggregation_group": "s7agg_test",
                    "nonce": "nonce-1",
                    "credential_ref": "cred-1",
                    "auth_method": "founder_webauthn",
                    "grant_source": "founder_webauthn",
                    "user_presence": True,
                    "user_verification": True,
                    "created_at": NOW,
                    "expires_at": FUTURE,
                    "consumed_at": None,
                }
                kwargs[field] = 1
                with self.assertRaises(ValueError):
                    s7.S7AuthorizationArtifact(**kwargs)

        with self.assertRaises(ValueError):
            s7.S7AuthorizationArtifact(
                artifact_id="artifact-2",
                request_id="req-2",
                request_envelope_hash="a" * 64,
                rendered_text_hash="b" * 64,
                action_params_hash="c" * 64,
                precondition_hash="d" * 64,
                authority_context_hash="e" * 64,
                derived_work_class="routine_custody",
                derived_aggregation_group="s7agg_test",
                nonce="nonce-2",
                credential_ref="cred-1",
                auth_method="founder_webauthn",
                grant_source="founder_webauthn",
                user_presence=True,
                user_verification=True,
                created_at=NOW,
                expires_at=FUTURE,
                consumed_at=["truthy"],  # type: ignore[arg-type]
            )

    def test_057_artifact_store_consumes_once(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        first = store.consume_verified(
            artifact.artifact_id,
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=_authority,
            precondition_hash=artifact.precondition_hash,
            derived_work_class=artifact.derived_work_class,
            derived_aggregation_group=artifact.derived_aggregation_group,
            now=NOW,
        )
        second = store.consume_verified(
            artifact.artifact_id,
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=_authority,
            precondition_hash=artifact.precondition_hash,
            derived_work_class=artifact.derived_work_class,
            derived_aggregation_group=artifact.derived_aggregation_group,
            now=NOW,
        )

        self.assertTrue(first)
        self.assertFalse(second)

    def test_058_artifact_store_replay_across_request_ids_rejected(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        tampered_rendered = s7.RenderedRequestStatement(
            **{**rendered.__dict__, "request_id": "other"},
        )

        self.assertFalse(
            store.consume_verified(
                artifact.artifact_id,
                rendered=tampered_rendered,
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )
        self.assertTrue(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_059_timezone_expired_artifact_does_not_consume(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        expired = s7.S7AuthorizationArtifact(
            **{**artifact.__dict__, "expires_at": "2026-05-17T23:30:00+14:00"},
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(expired)

        self.assertFalse(
            store.consume_verified(
                expired.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=expired.precondition_hash,
                derived_work_class=expired.derived_work_class,
                derived_aggregation_group=expired.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_060_store_consume_rechecks_hashes_atomically(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        self.assertFalse(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash="f" * 64,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )
        self.assertTrue(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_061_superseded_request_rejects_old_artifact(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        self.assertFalse(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
                superseded_request_ids={rendered.request_id},
            ),
        )
        self.assertTrue(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_062_concurrent_double_consume_executes_once(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)
        results: list[bool] = []

        def consume() -> None:
            results.append(
                store.consume_verified(
                    artifact.artifact_id,
                    rendered=rendered,
                    action_params_hash=params_hash,
                    authority_context=_authority,
                    precondition_hash=artifact.precondition_hash,
                    derived_work_class=artifact.derived_work_class,
                    derived_aggregation_group=artifact.derived_aggregation_group,
                    now=NOW,
                ),
            )

        threads = [threading.Thread(target=consume) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 1)

    def test_063_consume_rejects_expired_authority_context_even_when_hash_matches(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._routine_bundle()
        expired_authority = replace(authority, expires_at=PAST)
        expired_authority_hash = s7.authority_context_hash(expired_authority)
        rendered_for_expired_authority = s7.RenderedRequestStatement(
            **{**rendered.__dict__, "authority_context_hash": expired_authority_hash},
        )
        artifact_for_expired_authority = s7.S7AuthorizationArtifact(
            **{**artifact.__dict__, "authority_context_hash": expired_authority_hash},
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact_for_expired_authority)

        self.assertFalse(
            store.consume_verified(
                artifact_for_expired_authority.artifact_id,
                rendered=rendered_for_expired_authority,
                action_params_hash=params_hash,
                authority_context=expired_authority,
                precondition_hash=artifact_for_expired_authority.precondition_hash,
                derived_work_class=artifact_for_expired_authority.derived_work_class,
                derived_aggregation_group=artifact_for_expired_authority.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_064_operator_only_context_cannot_consume_self_modification_artifact(self):
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._self_mod_bundle(
            role_names=("operator",),
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        self.assertFalse(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_065_bonded_user_context_can_consume_self_modification_artifact(self):
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._self_mod_bundle(
            role_names=("bonded_user", "operator"),
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        self.assertTrue(
            store.consume_verified(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )


if __name__ == "__main__":
    unittest.main()
