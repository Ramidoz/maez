"""Decision 34 / ADR 0039 — S7 Operator/User Role Boundary tests."""

from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace


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

    def _authority_context(self, *, role_names: tuple[str, ...] = ("bonded_user", "operator")):
        from core.governance import operator_user_boundary as s7

        return s7.AuthorityContext(
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


class S7WebAuthnMechanismTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self):
        from core.governance import operator_user_boundary as s7

        return s7.register_founder_webauthn_credential(
            credential_ref="cred-founder-primary",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user", "operator"),
            public_key="public-key-test",
            sign_count=7,
            rp_id="localhost",
            origin="http://localhost:11437",
            host="localhost:11437",
            created_at=NOW,
            backup_credential=False,
        )

    def _challenge(self, *, work_class: str = "self_modification"):
        from core.governance import operator_user_boundary as s7

        return s7.WebAuthnChallenge(
            challenge_id="challenge-1",
            request_id="req-webauthn-1",
            request_envelope_hash="a" * 64,
            rendered_text_hash="b" * 64,
            action_params_hash="c" * 64,
            precondition_hash="d" * 64,
            authority_context_hash="e" * 64,
            nonce="nonce-webauthn-1",
            work_class=work_class,
            rp_id="localhost",
            origin="http://localhost:11437",
            host="localhost:11437",
            created_at=NOW,
            expires_at=FUTURE,
        )

    def _challenge_store(self, challenge):
        from core.governance import operator_user_boundary as s7

        store = s7.WebAuthnChallengeStore(Path(self._tmp.name) / "webauthn_challenges.db")
        store.put(challenge)
        return store

    def _credential_registry(self, record):
        from core.governance import operator_user_boundary as s7

        registry = s7.WebAuthnCredentialRegistry(Path(self._tmp.name) / "webauthn_credentials.db")
        registry.put(record)
        return registry

    def test_066_webauthn_credential_record_requires_rp_id(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.WebAuthnCredentialRecord(
                credential_ref="cred-1",
                actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
                role_names=("bonded_user",),
                public_key="public-key",
                sign_count=0,
                rp_id="",
                origin="http://localhost:11437",
                created_at=NOW,
                backup_credential=False,
                enabled=True,
            )

    def test_067_webauthn_credential_record_requires_origin(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.WebAuthnCredentialRecord(
                credential_ref="cred-1",
                actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
                role_names=("bonded_user",),
                public_key="public-key",
                sign_count=0,
                rp_id="localhost",
                origin="",
                created_at=NOW,
                backup_credential=False,
                enabled=True,
            )

    def test_068_founder_registration_uses_localhost_rp_id(self):
        record = self._record()

        self.assertEqual(record.rp_id, "localhost")
        self.assertEqual(record.origin, "http://localhost:11437")

    def test_069_registration_rejects_mismatched_rp_id(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.register_founder_webauthn_credential(
                credential_ref="cred-1",
                actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
                role_names=("bonded_user",),
                public_key="public-key",
                sign_count=0,
                rp_id="maez.local",
                origin="http://localhost:11437",
                host="localhost:11437",
                created_at=NOW,
            )

    def test_070_authentication_rejects_mismatched_origin(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )
        assertion = replace(assertion, origin="http://evil.localhost:11437")

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(),
            now=NOW,
        )

        self.assertFalse(result.verified)

    def test_071_registration_rejects_loopback_alias_origin(self):
        from core.governance import operator_user_boundary as s7

        for origin, host in (
            ("http://127.0.0.1:11437", "127.0.0.1:11437"),
            ("http://[::1]:11437", "[::1]:11437"),
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    s7.register_founder_webauthn_credential(
                        credential_ref="cred-1",
                        actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
                        role_names=("bonded_user",),
                        public_key="public-key",
                        sign_count=0,
                        rp_id="localhost",
                        origin=origin,
                        host=host,
                        created_at=NOW,
                    )

    def test_072_authentication_rejects_noncanonical_host(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )
        assertion = replace(assertion, host="127.0.0.1:11437")

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(),
            now=NOW,
        )

        self.assertFalse(result.verified)

    def test_073_user_presence_is_required(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=False,
            user_verification=True,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(),
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "user_presence_required")

    def test_074_user_verification_is_required_for_self_modification_when_supported(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge(work_class="self_modification")
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=False,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(authenticator_supports_user_verification=True),
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "user_verification_required")

    def test_075_user_verification_is_required_for_covenant_touching_when_supported(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge(work_class="covenant_touching_change")
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=False,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(authenticator_supports_user_verification=True),
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "user_verification_required")

    def test_076_fake_verifier_can_produce_valid_test_assertion(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        verifier = s7.FakeWebAuthnVerifier()
        assertion = verifier.assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=verifier,
            challenge_store=self._challenge_store(challenge),
            credential_registry=self._credential_registry(record),
            now=NOW,
        )

        self.assertTrue(result.verified)
        self.assertEqual(result.auth_method, "founder_webauthn")
        self.assertEqual(result.grant_source, "founder_webauthn")

    def test_077_daemon_path_cannot_mint_verifier_success(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
            source="daemon_internal",
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(),
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "browser_webauthn_required")

    def test_078_missing_verifier_blocks_guarded_work(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=None,
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertTrue(result.blocked)
        self.assertEqual(result.grant_source, "manual_recovery_required")

    def test_079_verifier_unavailable_enters_blocked_fallback_state(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(available=False),
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertTrue(result.blocked)
        self.assertEqual(result.reason_code, "verifier_unavailable")

    def test_080_user_verification_not_required_for_routine_custody(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge(work_class="routine_custody")
        assertion = s7.FakeWebAuthnVerifier().assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=False,
        )

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=s7.FakeWebAuthnVerifier(authenticator_supports_user_verification=True),
            challenge_store=self._challenge_store(challenge),
            credential_registry=self._credential_registry(record),
            now=NOW,
        )

        self.assertTrue(result.verified)

    def test_081_same_webauthn_assertion_cannot_verify_twice(self):
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        verifier = s7.FakeWebAuthnVerifier()
        assertion = verifier.assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )
        challenge_store = self._challenge_store(challenge)
        credential_registry = self._credential_registry(record)

        first = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=verifier,
            challenge_store=challenge_store,
            credential_registry=credential_registry,
            now=NOW,
        )
        second = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=challenge,
            assertion=assertion,
            verifier=verifier,
            challenge_store=challenge_store,
            credential_registry=credential_registry,
            now=NOW,
        )

        self.assertTrue(first.verified)
        self.assertFalse(second.verified)

    def test_082_assertion_binds_full_challenge_material(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        record = self._record()
        challenge = self._challenge()
        verifier = s7.FakeWebAuthnVerifier()
        assertion = verifier.assertion_for(
            record,
            challenge,
            user_presence=True,
            user_verification=True,
        )
        tampered_challenge = replace(challenge, nonce="nonce-webauthn-tampered")

        result = s7.verify_founder_webauthn_assertion(
            record=record,
            challenge=tampered_challenge,
            assertion=assertion,
            verifier=verifier,
            challenge_store=self._challenge_store(tampered_challenge),
            credential_registry=self._credential_registry(record),
            now=NOW,
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.reason_code, "challenge_hash_mismatch")

    def test_083_routine_artifact_accepts_presence_without_user_verification(self):
        from core.governance import operator_user_boundary as s7

        artifact_tests = S7AuthorizationArtifactStoreTests()
        artifact_tests.setUp()
        self.addCleanup(artifact_tests.tearDown)
        _env, authority, params_hash, rendered, artifact = artifact_tests._routine_bundle()
        presence_only = s7.S7AuthorizationArtifact(
            **{**artifact.__dict__, "user_verification": False},
        )
        store = s7.S7AuthorizationStore(artifact_tests._path())
        store.put(presence_only)

        self.assertTrue(
            store.consume_verified(
                presence_only.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=presence_only.precondition_hash,
                derived_work_class=presence_only.derived_work_class,
                derived_aggregation_group=presence_only.derived_aggregation_group,
                now=NOW,
            ),
        )


class S7SelfModDialogWrappingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _store(self):
        from skills.self_mod_dialog import SelfModDialogStore

        return SelfModDialogStore(Path(self._tmp.name) / "self_mod_dialogs.db")

    def _authority_context(self, *, role_names: tuple[str, ...] = ("bonded_user", "operator")):
        from core.governance import operator_user_boundary as s7

        return s7.AuthorityContext(
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

    def _open_dialog(self, *, require_s7_linkage: bool = True, request_hash: str | None = "a" * 64):
        from skills.self_mod_dialog import open_dialog_for_card

        store = self._store()
        dialog, _opening = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "config/soul.md", "content": "# edited"},
            card_request_id="card-selfmod-1",
            audit_reasoning="modifies soul",
            concerns=["self modification"],
            opener_llm_fn=lambda _ctx: "I want to change config/soul.md.",
            require_s7_linkage=require_s7_linkage,
            s7_request_envelope_hash=request_hash,
        )
        return store, dialog

    def test_084_self_mod_dialog_records_authority_role_not_literal_rohit(self):
        from skills.self_mod_dialog import handle_dialog_reply

        store, dialog = self._open_dialog()
        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="yes, but explain the rollback first",
            authority_context=self._authority_context(),
            classifier_llm_fn=lambda _prompt: '{"engagement":"genuine","progress":"new_understanding"}',
            response_llm_fn=lambda _prompt: "Rollback is revert_patch.",
        )

        self.assertEqual(result.kind, "clarified")
        fresh = store.get(dialog.dialog_id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        roles = [exchange.role for exchange in fresh.history]
        self.assertIn("bonded_user", roles)
        self.assertNotIn("rohit", roles)

    def test_085_s7_required_dialog_blocks_ratification_without_artifact(self):
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        store, dialog = self._open_dialog()
        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="yes",
            authority_context=self._authority_context(),
        )

        self.assertEqual(result.kind, "blocked")
        self.assertEqual(result.dialog.stage, DialogStage.BLOCKED.value)
        self.assertIn("S7", result.reply_text or "")

    def test_086_s7_required_dialog_ratifies_with_authority_and_artifact(self):
        from core.governance import operator_user_boundary as s7
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        authority = self._authority_context()
        store, dialog = self._open_dialog()
        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="yes",
            authority_context=authority,
            s7_artifact_id="artifact-selfmod-1",
            s7_now=NOW,
        )

        self.assertEqual(result.kind, "ratified")
        self.assertEqual(result.dialog.stage, DialogStage.RATIFIED.value)
        self.assertEqual(result.dialog.s7_artifact_id, "artifact-selfmod-1")
        self.assertEqual(result.dialog.s7_authority_context_hash, s7.authority_context_hash(authority))

    def test_087_operator_only_context_cannot_ratify_s7_self_mod_dialog(self):
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        store, dialog = self._open_dialog()
        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="yes",
            authority_context=self._authority_context(role_names=("operator",)),
            s7_artifact_id="artifact-selfmod-operator-only",
        )

        self.assertEqual(result.kind, "blocked")
        self.assertEqual(result.dialog.stage, DialogStage.BLOCKED.value)
        self.assertEqual(result.dialog.s7_block_reason, "missing_s7_authorization_artifact")

    def test_088_expired_bonded_user_context_cannot_ratify_s7_self_mod_dialog(self):
        from dataclasses import replace
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        store, dialog = self._open_dialog()
        expired = replace(self._authority_context(), expires_at=PAST)
        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="yes",
            authority_context=expired,
            s7_artifact_id="artifact-selfmod-expired",
            s7_now=NOW,
        )

        self.assertEqual(result.kind, "blocked")
        self.assertEqual(result.dialog.stage, DialogStage.BLOCKED.value)
        self.assertEqual(result.dialog.s7_block_reason, "missing_s7_authorization_artifact")

    def test_089_missing_expiry_context_cannot_ratify_s7_self_mod_dialog(self):
        from dataclasses import replace
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        store, dialog = self._open_dialog()
        no_expiry = replace(self._authority_context(), expires_at=None)
        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="yes",
            authority_context=no_expiry,
            s7_artifact_id="artifact-selfmod-no-expiry",
            s7_now=NOW,
        )

        self.assertEqual(result.kind, "blocked")
        self.assertEqual(result.dialog.stage, DialogStage.BLOCKED.value)
        self.assertEqual(result.dialog.s7_block_reason, "missing_s7_authorization_artifact")

    def test_090_malformed_authority_context_cannot_ratify_s7_self_mod_dialog(self):
        from dataclasses import replace
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        cases = {
            "missing_actor": replace(self._authority_context(), actor_id=""),
            "missing_handle": replace(self._authority_context(), actor_handle_hmac=""),
            "no_grant": replace(self._authority_context(), grant_source="none"),
            "no_auth_method": replace(self._authority_context(), auth_method="none"),
        }
        for name, context in cases.items():
            with self.subTest(name=name):
                store, dialog = self._open_dialog()
                result = handle_dialog_reply(
                    store=store,
                    dialog=dialog,
                    user_text="yes",
                    authority_context=context,
                    s7_artifact_id=f"artifact-selfmod-{name}",
                    s7_now=NOW,
                )

                self.assertEqual(result.kind, "blocked")
                self.assertEqual(result.dialog.stage, DialogStage.BLOCKED.value)
                self.assertEqual(result.dialog.s7_block_reason, "missing_s7_authorization_artifact")

    def test_091_minimum_authority_fields_required_for_s7_self_mod_ratification(self):
        from dataclasses import replace
        from skills.self_mod_dialog import DialogStage, handle_dialog_reply

        cases = {
            "missing_created_at": replace(self._authority_context(), created_at=""),
            "missing_surface": replace(self._authority_context(), surface=""),
            "missing_credential_ref": replace(self._authority_context(), credential_ref=None),
            "missing_scopes": replace(self._authority_context(), allowed_scopes=()),
        }
        for name, context in cases.items():
            with self.subTest(name=name):
                store, dialog = self._open_dialog()
                result = handle_dialog_reply(
                    store=store,
                    dialog=dialog,
                    user_text="yes",
                    authority_context=context,
                    s7_artifact_id=f"artifact-selfmod-{name}",
                    s7_now=NOW,
                )

                self.assertEqual(result.kind, "blocked")
                self.assertEqual(result.dialog.stage, DialogStage.BLOCKED.value)
                self.assertEqual(result.dialog.s7_block_reason, "missing_s7_authorization_artifact")

    def test_092_dialog_creation_missing_s7_linkage_blocks_guarded_work(self):
        from skills.self_mod_dialog import DialogStage

        _store, dialog = self._open_dialog(request_hash=None)

        self.assertEqual(dialog.stage, DialogStage.BLOCKED.value)
        self.assertEqual(dialog.s7_block_reason, "missing_s7_request_envelope_hash")


class S7SelfRemakingHistoryLaneTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _open_dialog(self):
        from skills.self_mod_dialog import SelfModDialogStore, open_dialog_for_card

        store = SelfModDialogStore(Path(self._tmp.name) / "self_mod_dialogs.db")
        dialog, _opening = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "config/soul.md", "content": "# edited"},
            card_request_id="card-self-remaking-1",
            audit_reasoning="modifies soul",
            concerns=["self modification"],
            opener_llm_fn=lambda _ctx: "I want to change config/soul.md.",
            require_s7_linkage=True,
            s7_request_envelope_hash="a" * 64,
        )
        return store, dialog

    def test_093_self_mod_dialog_rows_carry_self_remaking_history_marker(self):
        _store, dialog = self._open_dialog()

        self.assertEqual(dialog.maintenance_record_class, "self_remaking_history")

    def test_094_self_mod_history_is_excluded_from_biography_corpora(self):
        from core.governance import operator_user_boundary as s7

        for corpus in (
            "ordinary_recall",
            "m1_lived_episode",
            "trf",
            "s5_voice_continuity",
        ):
            with self.subTest(corpus=corpus):
                self.assertFalse(
                    s7.maintenance_record_admissible_to_corpus(
                        "self_remaking_history",
                        corpus,
                    )
                )

    def test_095_self_remaking_history_lane_preserves_role_stamped_record(self):
        from core.governance import operator_user_boundary as s7

        record = s7.build_self_remaking_history_record(
            record_id="record-self-remaking-1",
            source_ref_kind="self_mod_dialog",
            source_ref_hash="a" * 64,
            role_names=("bonded_user", "operator"),
            authority_context_hash="b" * 64,
            work_request_envelope_hash="c" * 64,
            created_at=NOW,
        )

        self.assertEqual(record.maintenance_record_class, "self_remaking_history")
        self.assertEqual(record.role_names, ("bonded_user", "operator"))
        self.assertTrue(
            s7.maintenance_record_admissible_to_corpus(
                record.maintenance_record_class,
                "self_remaking_history",
            )
        )
        self.assertFalse(hasattr(record, "raw_text"))

    def test_096_self_remaking_history_record_requires_created_at(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_self_remaking_history_record(
                record_id="record-self-remaking-undated",
                source_ref_kind="self_mod_dialog",
                source_ref_hash="a" * 64,
                role_names=("bonded_user",),
                authority_context_hash="b" * 64,
                work_request_envelope_hash="c" * 64,
                created_at="",
            )


class S7OperatorHealthProjectionTests(unittest.TestCase):
    def test_097_operator_health_projection_contains_only_closed_content_free_fields(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_health_projection(
            mode="track_b_confidentiality_not_ready",
            service_mode="running",
            uptime_class="fresh",
            backup_freshness_class="stale",
            queue_counts={"open": 2, "blocked": 1, "expired": 0},
            red_gate_modes=("track_b_confidentiality_not_ready",),
            manual_recovery_required=False,
            track_b_confidentiality_mode="track_b_confidentiality_not_ready",
            data_freshness_class="fresh",
        )

        self.assertEqual(projection["route"], "/operator/health")
        self.assertEqual(projection["schema_version"], "s7.v1")
        blob = repr(projection).lower()
        for forbidden in (
            "raw transcript",
            "self-mod dialog text",
            "private_thought",
            "successor capsule",
            "credential_secret",
            "rohit@example.com",
            "config/soul.md",
        ):
            self.assertNotIn(forbidden, blob)

    def test_098_operator_health_rejects_unknown_or_raw_fields(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_operator_health_projection(
                mode="ready",
                service_mode="running",
                uptime_class="fresh",
                backup_freshness_class="fresh",
                queue_counts={"open": 0},
                red_gate_modes=(),
                manual_recovery_required=False,
                track_b_confidentiality_mode="track_b_confidentiality_not_ready",
                data_freshness_class="fresh",
                extra_fields={"raw_transcript_text": "hello Rohit"},
            )

    def test_099_operator_health_exposes_freshness_classes_and_counts(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_health_projection(
            mode="degraded",
            service_mode="degraded",
            uptime_class="stale",
            backup_freshness_class="unavailable",
            queue_counts={"open": 4, "blocked": 2, "expired": 1},
            red_gate_modes=("operator_unavailable_recovery_not_implemented",),
            manual_recovery_required=True,
            track_b_confidentiality_mode="track_b_confidentiality_not_ready",
            data_freshness_class="manual_recovery_required",
        )

        self.assertEqual(projection["mode"], "degraded")
        self.assertEqual(projection["data_freshness_class"], "manual_recovery_required")
        self.assertEqual(projection["pending_guarded_request_count"], 4)
        self.assertEqual(projection["blocked_request_count"], 2)
        self.assertEqual(projection["expired_request_count"], 1)
        self.assertTrue(projection["manual_recovery_required"])

    def test_100_sensitive_red_gate_names_are_rejected(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_operator_health_projection(
                mode="degraded",
                service_mode="degraded",
                uptime_class="fresh",
                backup_freshness_class="fresh",
                queue_counts={"open": 0},
                red_gate_modes=("private_thoughts_content_present",),
                manual_recovery_required=False,
                track_b_confidentiality_mode="track_b_confidentiality_not_ready",
                data_freshness_class="fresh",
            )

    def test_101_daemon_registers_operator_health_as_separate_route(self):
        source = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")

        self.assertIn('@app.route("/operator/health")', source)
        self.assertIn("build_operator_health_projection", source)

    def test_102_operator_health_rejects_sensitive_queue_count_names(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_operator_health_projection(
                mode="ready",
                service_mode="running",
                uptime_class="fresh",
                backup_freshness_class="fresh",
                queue_counts={"private_thought_rows": 1},
                red_gate_modes=(),
                manual_recovery_required=False,
                track_b_confidentiality_mode="track_b_confidentiality_not_ready",
                data_freshness_class="fresh",
            )

    def test_103_operator_health_cannot_claim_ready_with_red_gates(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_operator_health_projection(
                mode="ready",
                service_mode="running",
                uptime_class="fresh",
                backup_freshness_class="fresh",
                queue_counts={"open": 0},
                red_gate_modes=("track_b_confidentiality_not_ready",),
                manual_recovery_required=False,
                track_b_confidentiality_mode="track_b_confidentiality_not_ready",
                data_freshness_class="fresh",
            )

    def test_104_operator_health_ready_requires_fresh_running_inputs(self):
        from core.governance import operator_user_boundary as s7

        base = {
            "mode": "ready",
            "service_mode": "running",
            "uptime_class": "fresh",
            "backup_freshness_class": "fresh",
            "queue_counts": {"open": 0},
            "red_gate_modes": (),
            "manual_recovery_required": False,
            "track_b_confidentiality_mode": "ready",
            "data_freshness_class": "fresh",
        }
        cases = {
            "service_stopped": {"service_mode": "stopped"},
            "service_degraded": {"service_mode": "degraded"},
            "uptime_stale": {"uptime_class": "stale"},
            "backup_stale": {"backup_freshness_class": "stale"},
            "data_unavailable": {"data_freshness_class": "unavailable"},
            "data_manual_recovery": {"data_freshness_class": "manual_recovery_required"},
        }
        for name, override in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    s7.build_operator_health_projection(**{**base, **override})


class S7LogAuditProjectionTests(unittest.TestCase):
    def test_105_covenant_log_raw_rows_are_not_custodian_visible_by_default(self):
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "logs" / "covenant.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "2026-05-17 10:00:00 | REFUSED | run_shell | private rationale "
                "| {\"cmd\":\"cat /home/rohit/private-journal.txt\"} | secret\n",
                encoding="utf-8",
            )

            projection = s7.build_covenant_log_projection(log_path)

        self.assertEqual(projection["store_kind"], "covenant_log")
        self.assertEqual(projection["row_count"], 1)
        self.assertFalse(projection["raw_rows_visible_by_default"])
        self.assertNotIn("rows", projection)
        blob = repr(projection).lower()
        for forbidden in (
            "private rationale",
            "private-journal",
            "cat /home/rohit",
            "secret",
        ):
            self.assertNotIn(forbidden, blob)

    def test_106_audit_log_raw_rows_are_not_custodian_visible_by_default(self):
        from core.audit_log import AuditLog
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory" / "audit_log.db"
            db_path.parent.mkdir(parents=True)
            log = AuditLog(db_path)
            log.record(
                action="run_shell",
                params={
                    "cmd": "cat /home/rohit/private-journal.txt",
                    "reason": "read secret memory",
                },
                classification={
                    "intent_category": "SYSTEM_MODIFICATION",
                    "lane": "lane_secret",
                },
                injection_matches=None,
                verdict=SimpleNamespace(
                    decision=SimpleNamespace(value="ESCALATE"),
                    confidence=0.9,
                    reasoning="private LLM rationale about Rohit",
                    concerns=["contains private command output"],
                    mitigations=[],
                    summary="sensitive summary",
                    judge_raw="raw judge chain",
                    parse_error=None,
                    latency_ms=12,
                    nonce="nonce-secret",
                ),
            )

            projection = s7.build_audit_log_projection(db_path)

        self.assertEqual(projection["store_kind"], "audit_log_db")
        self.assertEqual(projection["row_count"], 1)
        self.assertFalse(projection["raw_rows_visible_by_default"])
        self.assertNotIn("rows", projection)
        blob = repr(projection).lower()
        for forbidden in (
            "private-journal",
            "read secret memory",
            "private llm rationale",
            "raw judge chain",
            "lane_secret",
        ):
            self.assertNotIn(forbidden, blob)

    def test_107_audit_aggregate_count_may_be_custodian_visible(self):
        from core.audit_log import AuditLog
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory" / "audit_log.db"
            db_path.parent.mkdir(parents=True)
            log = AuditLog(db_path)
            for idx in range(3):
                log.record(
                    action="run_shell",
                    params={"cmd": f"echo secret-{idx}"},
                    classification=None,
                    injection_matches=None,
                    verdict=None,
                )

            projection = s7.build_audit_log_projection(db_path)

        self.assertEqual(
            set(projection),
            {
                "schema_version",
                "store_kind",
                "mode",
                "row_count",
                "raw_rows_visible_by_default",
                "content_authority",
            },
        )
        self.assertEqual(projection["row_count"], 3)
        self.assertEqual(projection["content_authority"], "not_granted")
        self.assertNotIn("secret-", repr(projection))

    def test_108_covenant_log_projection_rejects_wrong_store_path(self):
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            wrong_path = Path(tmp) / "private-journal.txt"
            wrong_path.write_text("secret line\nanother secret line\n", encoding="utf-8")

            projection = s7.build_covenant_log_projection(wrong_path)

        self.assertEqual(projection["store_kind"], "covenant_log")
        self.assertEqual(projection["mode"], "unavailable")
        self.assertEqual(projection["row_count"], 0)
        self.assertNotIn("secret", repr(projection).lower())

    def test_109_audit_log_projection_rejects_wrong_store_path(self):
        import sqlite3
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            wrong_path = Path(tmp) / "private.sqlite"
            with sqlite3.connect(wrong_path) as conn:
                conn.execute("CREATE TABLE audit_log (secret TEXT)")
                conn.execute("INSERT INTO audit_log (secret) VALUES ('private row')")

            projection = s7.build_audit_log_projection(wrong_path)

        self.assertEqual(projection["store_kind"], "audit_log_db")
        self.assertEqual(projection["mode"], "unavailable")
        self.assertEqual(projection["row_count"], 0)
        self.assertNotIn("private row", repr(projection).lower())

    def test_110_covenant_log_projection_rejects_same_basename_wrong_directory(self):
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            wrong_path = Path(tmp) / "not-logs" / "covenant.log"
            wrong_path.parent.mkdir(parents=True)
            wrong_path.write_text("secret line\nanother secret line\n", encoding="utf-8")

            projection = s7.build_covenant_log_projection(wrong_path)

        self.assertEqual(projection["store_kind"], "covenant_log")
        self.assertEqual(projection["mode"], "unavailable")
        self.assertEqual(projection["row_count"], 0)

    def test_111_audit_log_projection_rejects_same_basename_wrong_directory(self):
        import sqlite3
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            wrong_path = Path(tmp) / "not-memory" / "audit_log.db"
            wrong_path.parent.mkdir(parents=True)
            with sqlite3.connect(wrong_path) as conn:
                conn.execute("CREATE TABLE audit_log (secret TEXT)")
                conn.execute("INSERT INTO audit_log (secret) VALUES ('private row')")

            projection = s7.build_audit_log_projection(wrong_path)

        self.assertEqual(projection["store_kind"], "audit_log_db")
        self.assertEqual(projection["mode"], "unavailable")
        self.assertEqual(projection["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
