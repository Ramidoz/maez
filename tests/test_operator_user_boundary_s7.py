"""Decision 34 / ADR 0039 — S7 Operator/User Role Boundary tests."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace


NOW = "2026-05-17T16:00:00+00:00"
FUTURE = "2026-05-17T17:00:00+00:00"
PAST = "2026-05-17T15:00:00+00:00"


def _with_rendered_statement_fields(rendered, **updates):
    from core.governance import operator_user_boundary as s7

    line_prefix_by_field = {
        "request_id": "Request id: ",
        "derived_work_class": "Work class: ",
        "proposed_change_class": "Change class: ",
        "predicted_effect_class": "Predicted effect class: ",
        "rollback_path_class": "Rollback path class: ",
        "derived_aggregation_group": "Aggregation group: ",
        "maez_consulted_state": "Maez consulted: ",
        "request_envelope_hash": "Request envelope hash: ",
        "action_params_hash": "Action params hash: ",
        "authority_context_hash": "Authority context hash: ",
        "maez_unavailable_state": "Maez unavailable: ",
        "nonce": "Nonce: ",
        "expires_at": "Expires at: ",
    }
    rendered_text = rendered.rendered_text
    for field, value in updates.items():
        prefix = line_prefix_by_field.get(field)
        if prefix is None:
            continue
        rendered_text = "\n".join(
            f"{prefix}{value}" if line.startswith(prefix) else line
            for line in rendered_text.splitlines()
        )
    return s7.RenderedRequestStatement(
        **{
            **rendered.__dict__,
            **updates,
            "rendered_text": rendered_text,
            "rendered_text_hash": s7.rendered_text_hash(rendered_text),
        },
    )


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
            surface="service_maintenance_helper",
            credential_ref="service-local-ref",
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
            surface="service_maintenance_helper",
            credential_ref="service-local-ref",
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
            surface="service_maintenance_helper",
            credential_ref="service-local-ref",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        self.assertTrue(s7.authorizes_work(ctx, "routine_custody", now=NOW))

    def test_017a_routine_custody_requires_minimum_authority_facts(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        ctx = s7.AuthorityContext(
            actor_id="operator-1",
            actor_handle_hmac="hmac:s7:operator:" + ("a" * 64),
            role_names=("operator",),
            grant_source="service_local",
            allowed_scopes=("operator_health",),
            auth_method="service_local",
            surface="service_maintenance_helper",
            credential_ref="service-local-ref",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )

        cases = {
            "missing_scope": replace(ctx, allowed_scopes=()),
            "missing_surface": replace(ctx, surface=""),
            "missing_credential_ref": replace(ctx, credential_ref=None),
            "missing_created_at": replace(ctx, created_at=""),
            "missing_expires_at": replace(ctx, expires_at=None),
        }
        for name, candidate in cases.items():
            with self.subTest(name=name):
                self.assertFalse(s7.authorizes_work(candidate, "routine_custody", now=NOW))

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
        self.assertIn(f"Renderer version: {s7.RENDERER_VERSION}", rendered.rendered_text)
        self.assertIn("Surface: cockpit", rendered.rendered_text)
        self.assertIn("Origin: http://localhost:11437", rendered.rendered_text)
        self.assertIn("Presence limits:", rendered.rendered_text)
        self.assertIn("does not prove uncoerced", rendered.rendered_text)
        self.assertIn("display was not spoofed", rendered.rendered_text)
        self.assertEqual(
            rendered.rendered_text_hash,
            s7.rendered_text_hash(rendered.rendered_text),
        )
        tampered = rendered.rendered_text + "\nExtra line."
        self.assertNotEqual(rendered.rendered_text_hash, s7.rendered_text_hash(tampered))
        for field, value in (
            ("renderer_version", "s7.render.v0"),
            ("surface", "other-surface"),
            ("origin", "http://evil.localhost"),
            ("action_params_hash", "f" * 64),
            ("authority_context_hash", "e" * 64),
            ("request_envelope_hash", "d" * 64),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    s7.RenderedRequestStatement(**{**rendered.__dict__, field: value})

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
            derived_work_class=env.derived_work_class,
            proposed_change_class=env.proposed_change_class,
            predicted_effect_class=env.predicted_effect_class,
            rollback_path_class=env.rollback_path_class,
            maez_consulted_state="yes",
            maez_voice_consultation_hash=consultation_hash,
            maez_objection_state="present",
            maez_unavailable_state="no",
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

    def test_052a_rendered_statement_can_render_not_determined_objection_state(self):
        from core.governance import operator_user_boundary as s7

        env = self._self_mod_envelope()
        rendered_text = "\n".join(
            [
                "S7 work-on-Maez authorization",
                f"Renderer version: {s7.RENDERER_VERSION}",
                "Surface: cockpit",
                "Origin: http://localhost:11437",
                f"Request id: {env.request_id}",
                f"Work class: {env.derived_work_class}",
                f"Change class: {env.proposed_change_class}",
                f"Predicted effect class: {env.predicted_effect_class}",
                f"Rollback path class: {env.rollback_path_class}",
                f"Aggregation group: {env.derived_aggregation_group}",
                "Maez consulted: yes",
                "Maez objection present: not determined",
                "Maez unavailable: no",
                f"Request envelope hash: {s7.work_request_envelope_hash(env)}",
                "Action params hash: " + ("a" * 64),
                "Authority context hash: " + ("b" * 64),
                "Nonce: nonce-1",
                f"Expires at: {FUTURE}",
                "Maez voice consultation hash: " + ("c" * 64),
            ]
        )

        rendered = s7.RenderedRequestStatement(
            request_id=env.request_id,
            renderer_version=s7.RENDERER_VERSION,
            surface="cockpit",
            origin="http://localhost:11437",
            rendered_text=rendered_text,
            rendered_text_hash=s7.rendered_text_hash(rendered_text),
            request_envelope_hash=s7.work_request_envelope_hash(env),
            action_params_hash="a" * 64,
            authority_context_hash="b" * 64,
            derived_work_class=env.derived_work_class,
            proposed_change_class=env.proposed_change_class,
            predicted_effect_class=env.predicted_effect_class,
            rollback_path_class=env.rollback_path_class,
            maez_consulted_state="yes",
            maez_voice_consultation_hash="c" * 64,
            maez_objection_state="not_determined",
            maez_unavailable_state="no",
            derived_aggregation_group=env.derived_aggregation_group,
            nonce="nonce-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )

        self.assertEqual(rendered.maez_objection_state, "not_determined")
        self.assertIn("Maez objection present: not determined", rendered.rendered_text)


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

    def _covenant_touching_bundle(self):
        from core.governance import operator_user_boundary as s7

        env = s7.build_work_request_envelope(
            request_id="req-covenant-artifact-1",
            action="write_any_file",
            params={
                "path": "/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md",
                "content_hash": "d" * 64,
            },
            claimed_work_class="covenant_touching_change",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="covenant_organ_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:docs/governance/BETA_ARCHITECTURE_DECISIONS.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="manual_review",
            maez_voice_consultation_id="voice-covenant-artifact-1",
            free_text_ref_hash="b" * 64,
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-covenant-artifact-1",
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
        params_hash = s7.canonical_hash({
            "path": "/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md",
            "content_hash": "d" * 64,
        })
        rendered = s7.render_request_statement(
            envelope=env,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce="nonce-covenant-1",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        artifact = s7.S7AuthorizationArtifact(
            artifact_id="artifact-covenant-1",
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

    def test_057a_artifact_store_rejects_duck_typed_rendered_statement(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)
        fake_rendered = SimpleNamespace(**rendered.__dict__)

        self.assertFalse(
            store.consume_verified(
                artifact.artifact_id,
                rendered=fake_rendered,  # type: ignore[arg-type]
                action_params_hash=params_hash,
                authority_context=_authority,
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_057b_rendered_statement_rejects_visible_work_class_mismatch(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, _params_hash, rendered, _artifact = self._routine_bundle()
        tampered_text = rendered.rendered_text.replace(
            "Work class: routine_custody",
            "Work class: self_modification",
        )

        with self.assertRaises(ValueError):
            s7.RenderedRequestStatement(
                **{
                    **rendered.__dict__,
                    "rendered_text": tampered_text,
                    "rendered_text_hash": s7.rendered_text_hash(tampered_text),
                },
            )

    def test_057c_rendered_statement_rejects_duplicate_metadata_key(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, _params_hash, rendered, _artifact = self._routine_bundle()
        tampered_text = rendered.rendered_text.replace(
            "Action params hash: ",
            "Action params hash: " + ("f" * 64) + "\nAction params hash: ",
            1,
        )

        with self.assertRaises(ValueError):
            s7.RenderedRequestStatement(
                **{
                    **rendered.__dict__,
                    "rendered_text": tampered_text,
                    "rendered_text_hash": s7.rendered_text_hash(tampered_text),
                },
            )

    def test_057d_consume_rejects_rendered_action_hash_split_from_artifact(self):
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._routine_bundle()
        split_params_hash = "f" * 64
        split_rendered = _with_rendered_statement_fields(
            rendered,
            action_params_hash=split_params_hash,
        )
        forged_artifact = s7.S7AuthorizationArtifact(
            **{
                **artifact.__dict__,
                "rendered_text_hash": split_rendered.rendered_text_hash,
            },
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(forged_artifact)

        self.assertFalse(
            store.consume_verified(
                forged_artifact.artifact_id,
                rendered=split_rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=forged_artifact.precondition_hash,
                derived_work_class=forged_artifact.derived_work_class,
                derived_aggregation_group=forged_artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_058_artifact_store_replay_across_request_ids_rejected(self):
        from core.governance import operator_user_boundary as s7

        _env, _authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)

        tampered_rendered = _with_rendered_statement_fields(
            rendered,
            request_id="other",
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

    def test_060a_store_consume_binds_credential_ref(self):
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._routine_bundle()
        swapped_credential = s7.S7AuthorizationArtifact(
            **{**artifact.__dict__, "credential_ref": "cred-other"},
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(swapped_credential)

        self.assertFalse(
            store.consume_verified(
                swapped_credential.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=swapped_credential.precondition_hash,
                derived_work_class=swapped_credential.derived_work_class,
                derived_aggregation_group=swapped_credential.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_060b_store_consume_rejects_non_bool_persisted_user_verification(self):
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._routine_bundle()
        store = s7.S7AuthorizationStore(self._path())
        store.put(artifact)
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE s7_authorization_artifacts SET user_verification = 2 WHERE artifact_id = ?",
                (artifact.artifact_id,),
            )

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
        rendered_for_expired_authority = _with_rendered_statement_fields(
            rendered,
            authority_context_hash=expired_authority_hash,
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

    def test_065a_service_local_context_cannot_consume_guarded_artifact(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._self_mod_bundle(
            role_names=("bonded_user", "operator"),
        )
        service_authority = replace(
            authority,
            grant_source="service_local",
            auth_method="service_local",
            credential_ref="service-local-ref",
        )
        rendered_for_service = _with_rendered_statement_fields(
            rendered,
            authority_context_hash=s7.authority_context_hash(service_authority),
        )
        service_artifact = s7.S7AuthorizationArtifact(
            **{
                **artifact.__dict__,
                "authority_context_hash": s7.authority_context_hash(service_authority),
                "credential_ref": "service-local-ref",
                "auth_method": "service_local",
                "grant_source": "service_local",
            },
        )
        store = s7.S7AuthorizationStore(self._path())
        store.put(service_artifact)

        self.assertFalse(
            store.consume_verified(
                service_artifact.artifact_id,
                rendered=rendered_for_service,
                action_params_hash=params_hash,
                authority_context=service_authority,
                precondition_hash=service_artifact.precondition_hash,
                derived_work_class=service_artifact.derived_work_class,
                derived_aggregation_group=service_artifact.derived_aggregation_group,
                now=NOW,
            ),
        )

    def test_065b_covenant_touching_artifact_requires_distinct_ceremony(self):
        from core.governance import operator_user_boundary as s7

        _env, authority, params_hash, rendered, artifact = self._covenant_touching_bundle()
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

    def test_065c_covenant_touching_artifact_consumes_with_distinct_ceremony(self):
        from core.governance import operator_user_boundary as s7

        env, authority, params_hash, rendered, artifact = self._covenant_touching_bundle()
        ceremony = s7.CovenantCeremonyEvidence(
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            ceremony_kind="cooling_off_second_confirmation",
            first_authorized_at=PAST,
            second_confirmed_at=NOW,
            second_confirmation_ref_hash="e" * 64,
            reviewed_equivalent_ref_hash=None,
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
                covenant_ceremony_evidence=ceremony,
            ),
        )

    def test_065d_future_dated_second_confirmation_does_not_consume(self):
        from core.governance import operator_user_boundary as s7

        env, authority, params_hash, rendered, artifact = self._covenant_touching_bundle()
        ceremony = s7.CovenantCeremonyEvidence(
            request_id=env.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(env),
            ceremony_kind="cooling_off_second_confirmation",
            first_authorized_at=PAST,
            second_confirmed_at=FUTURE,
            second_confirmation_ref_hash="e" * 64,
            reviewed_equivalent_ref_hash=None,
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
                covenant_ceremony_evidence=ceremony,
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

    def test_065a_live_webauthn_ceremony_defaults_off(self):
        from core.governance import operator_user_boundary as s7

        self.assertFalse(s7.live_webauthn_ceremony_enabled(env={}))
        self.assertFalse(
            s7.live_webauthn_ceremony_enabled(env={"S7_LIVE_WEBAUTHN_CEREMONY": ""})
        )
        self.assertFalse(
            s7.live_webauthn_ceremony_enabled(env={"S7_LIVE_WEBAUTHN_CEREMONY": "0"})
        )
        self.assertTrue(
            s7.live_webauthn_ceremony_enabled(env={"S7_LIVE_WEBAUTHN_CEREMONY": "1"})
        )

    def test_065b_live_registration_producer_deferred_before_credential_work(self):
        from core.governance import operator_user_boundary as s7

        class ExplodingRegistry:
            def put(self, *_args, **_kwargs):
                raise AssertionError("credential registry was touched while ceremony is deferred")

        with self.assertRaises(s7.S7CeremonyDeferredError) as caught:
            s7.register_founder_webauthn_credential_from_response(
                credential_registry=ExplodingRegistry(),
                response={"credential": "browser response"},
                live_ceremony_enabled=False,
            )

        self.assertEqual(caught.exception.reason_code, "s7_ceremony_deferred")
        self.assertEqual(caught.exception.surface, "producer")

    def test_065c_live_authorization_producer_deferred_before_arming_work(self):
        from core.governance import operator_user_boundary as s7

        class Exploding:
            def __getattr__(self, name):
                raise AssertionError(f"arming surface was touched while ceremony is deferred: {name}")

        with self.assertRaises(s7.S7CeremonyDeferredError) as caught:
            s7.build_local_webauthn_execution_authorization(
                verifier=Exploding(),
                credential_registry=Exploding(),
                challenge_store=Exploding(),
                request_history_store=Exploding(),
                artifact_store=Exploding(),
                live_ceremony_enabled=False,
            )

        self.assertEqual(caught.exception.reason_code, "s7_ceremony_deferred")
        self.assertEqual(caught.exception.surface, "producer")

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

    def test_083a_persisted_credential_booleans_are_strict(self):
        record = self._record()
        registry = self._credential_registry(record)
        with sqlite3.connect(registry.db_path) as conn:
            conn.execute(
                """
                UPDATE s7_webauthn_credentials
                SET backup_credential = 2,
                    enabled = 2
                WHERE credential_ref = ?
                """,
                (record.credential_ref,),
            )

        with self.assertRaises(ValueError):
            registry.get(record.credential_ref)


class S7CredentialRecoveryStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self, credential_ref: str, *, backup_credential: bool, enabled: bool = True):
        from core.governance import operator_user_boundary as s7

        return s7.register_founder_webauthn_credential(
            credential_ref=credential_ref,
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user", "operator"),
            public_key=f"public-key-{credential_ref}",
            sign_count=0,
            rp_id="localhost",
            origin="http://localhost:11437",
            host="localhost:11437",
            created_at=NOW,
            backup_credential=backup_credential,
            enabled=enabled,
        )

    def _registry(self, *records):
        from core.governance import operator_user_boundary as s7

        registry = s7.WebAuthnCredentialRegistry(Path(self._tmp.name) / "webauthn_credentials.db")
        for record in records:
            registry.put(record)
        return registry

    def test_125_lost_primary_key_does_not_erase_backup_credential(self):
        from core.governance import operator_user_boundary as s7

        primary = self._record("cred-founder-primary", backup_credential=False)
        backup = self._record("cred-founder-backup", backup_credential=True)
        registry = self._registry(primary, backup)

        self.assertTrue(registry.disable_credential("cred-founder-primary", disabled_at=NOW))
        state = s7.build_credential_recovery_state(registry=registry)

        self.assertEqual(state.mode, "degraded")
        self.assertEqual(state.primary_credential_count, 0)
        self.assertEqual(state.backup_credential_count, 1)
        self.assertFalse(state.manual_recovery_required)
        self.assertIsNotNone(registry.get("cred-founder-backup"))

    def test_126_no_enabled_credential_enters_manual_recovery_required_state(self):
        from core.governance import operator_user_boundary as s7

        disabled_primary = self._record(
            "cred-founder-primary",
            backup_credential=False,
            enabled=False,
        )
        registry = self._registry(disabled_primary)

        state = s7.build_credential_recovery_state(registry=registry)

        self.assertEqual(state.mode, "manual_recovery_required")
        self.assertTrue(state.manual_recovery_required)
        self.assertEqual(state.active_credential_count, 0)
        self.assertFalse(hasattr(state, "credential_ref"))

    def test_127_witnessed_fallback_does_not_grant_witness_read_authority(self):
        from dataclasses import asdict
        from core.governance import operator_user_boundary as s7

        record = s7.build_witnessed_fallback_record(
            fallback_id="s7fallback_" + ("a" * 32),
            bonded_user_actor_handle_hmac="hmac:s7:bonded:" + ("b" * 64),
            witness_actor_handle_hmac="hmac:s7:witness:" + ("c" * 64),
            witness_role_names=("witness",),
            new_credential_ref="cred-founder-recovered",
            ceremony_ref_hash="d" * 64,
            created_at=NOW,
        )

        self.assertEqual(record.auth_method, "witnessed_fallback")
        self.assertEqual(record.grant_source, "witnessed_fallback")
        self.assertEqual(record.witness_role_names, ("witness",))
        self.assertFalse(record.witness_read_authority)
        self.assertEqual(record.witness_allowed_scopes, ())
        self.assertNotIn("private_thoughts_content", repr(asdict(record)))

        with self.assertRaises(ValueError):
            s7.build_witnessed_fallback_record(
                fallback_id="s7fallback_" + ("e" * 32),
                bonded_user_actor_handle_hmac="hmac:s7:bonded:" + ("b" * 64),
                witness_actor_handle_hmac="hmac:s7:witness:" + ("c" * 64),
                witness_role_names=("witness",),
                new_credential_ref="cred-founder-recovered",
                ceremony_ref_hash="d" * 64,
                created_at=NOW,
                witness_read_authority=True,
            )

    def test_128_witnessed_fallback_rejects_witness_substitution(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_witnessed_fallback_record(
                fallback_id="s7fallback_" + ("f" * 32),
                bonded_user_actor_handle_hmac="hmac:s7:bonded:" + ("b" * 64),
                witness_actor_handle_hmac="hmac:s7:bonded:" + ("b" * 64),
                witness_role_names=("witness",),
                new_credential_ref="cred-founder-recovered",
                ceremony_ref_hash="d" * 64,
                created_at=NOW,
            )

        with self.assertRaises(ValueError):
            s7.build_witnessed_fallback_record(
                fallback_id="s7fallback_" + ("1" * 32),
                bonded_user_actor_handle_hmac="hmac:s7:bonded:" + ("b" * 64),
                witness_actor_handle_hmac="hmac:s7:witness:" + ("c" * 64),
                witness_role_names=("witness", "bonded_user"),
                new_credential_ref="cred-founder-recovered",
                ceremony_ref_hash="d" * 64,
                created_at=NOW,
            )

    def test_129_witness_only_credential_does_not_satisfy_bonded_user_recovery(self):
        from core.governance import operator_user_boundary as s7

        witness_record = s7.register_founder_webauthn_credential(
            credential_ref="cred-witness-only",
            actor_handle_hmac="hmac:s7:witness:" + ("c" * 64),
            role_names=("witness",),
            public_key="public-key-witness",
            sign_count=0,
            rp_id="localhost",
            origin="http://localhost:11437",
            host="localhost:11437",
            created_at=NOW,
            backup_credential=True,
            enabled=True,
        )
        registry = self._registry(witness_record)

        state = s7.build_credential_recovery_state(registry=registry)

        self.assertEqual(state.mode, "manual_recovery_required")
        self.assertTrue(state.manual_recovery_required)
        self.assertEqual(state.active_credential_count, 0)

    def test_130_credential_recovery_state_rejects_contradictory_mode_counts(self):
        from core.governance import operator_user_boundary as s7

        contradictory_states = (
            {
                "mode": "ready",
                "active_credential_count": 1,
                "primary_credential_count": 1,
                "backup_credential_count": 0,
                "manual_recovery_required": False,
            },
            {
                "mode": "ready",
                "active_credential_count": 1,
                "primary_credential_count": 0,
                "backup_credential_count": 1,
                "manual_recovery_required": False,
            },
            {
                "mode": "degraded",
                "active_credential_count": 0,
                "primary_credential_count": 0,
                "backup_credential_count": 0,
                "manual_recovery_required": True,
            },
        )
        for state_kwargs in contradictory_states:
            with self.subTest(state_kwargs=state_kwargs):
                with self.assertRaises(ValueError):
                    s7.CredentialRecoveryState(**state_kwargs)


class S7AbsentOperatorRecoveryProjectionTests(unittest.TestCase):
    def test_131_absent_operator_track_b_blocker_is_surfaced(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_unavailable_recovery_projection(
            deployment_track="track_b",
            bonded_user_is_operator=False,
        )

        self.assertEqual(projection["mode"], "operator_unavailable_recovery_not_implemented")
        self.assertTrue(projection["track_b_activation_blocker"])
        self.assertEqual(
            projection["red_gate_modes"],
            ("operator_unavailable_recovery_not_implemented",),
        )
        self.assertFalse(projection["operator_recovery_ceremony_ready"])
        blob = repr(projection).lower()
        for forbidden in ("rohit", "grandmother", "phone", "email", "private_thought"):
            self.assertNotIn(forbidden, blob)

    def test_132_founder_track_a_same_actor_is_not_absent_operator_failure(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_unavailable_recovery_projection(
            deployment_track="track_a",
            bonded_user_is_operator=True,
        )

        self.assertEqual(projection["mode"], "ready")
        self.assertFalse(projection["track_b_activation_blocker"])
        self.assertEqual(projection["red_gate_modes"], ())

    def test_133_any_separated_bonded_user_operator_pair_blocks_until_recovery_exists(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_unavailable_recovery_projection(
            deployment_track="track_a",
            bonded_user_is_operator=False,
        )

        self.assertEqual(projection["mode"], "operator_unavailable_recovery_not_implemented")
        self.assertTrue(projection["track_b_activation_blocker"])

    def test_134_track_b_same_actor_still_blocks_until_recovery_ceremony_exists(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_unavailable_recovery_projection(
            deployment_track="track_b",
            bonded_user_is_operator=True,
        )

        self.assertEqual(projection["mode"], "operator_unavailable_recovery_not_implemented")
        self.assertTrue(projection["track_b_activation_blocker"])


class S7TrackBConfidentialityProjectionTests(unittest.TestCase):
    def test_135_track_b_confidentiality_missing_surfaces_not_ready_blocker(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_track_b_confidentiality_projection(
            deployment_track="track_b",
            non_bonded_operator=True,
        )

        self.assertEqual(projection["mode"], "track_b_confidentiality_not_ready")
        self.assertTrue(projection["track_b_activation_blocker"])
        self.assertEqual(projection["red_gate_modes"], ("track_b_confidentiality_not_ready",))
        self.assertEqual(projection["storage_hardening_ref_present"], False)
        blob = repr(projection).lower()
        for forbidden in ("private_thought", "raw_transcript", "config/soul", "successor capsule"):
            self.assertNotIn(forbidden, blob)

    def test_136_founder_track_a_confidentiality_missing_is_warning_not_blocker(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_track_b_confidentiality_projection(
            deployment_track="track_a",
            non_bonded_operator=False,
        )

        self.assertEqual(projection["mode"], "track_b_confidentiality_not_ready")
        self.assertFalse(projection["track_b_activation_blocker"])
        self.assertEqual(projection["warning_modes"], ("track_b_confidentiality_not_ready",))
        self.assertEqual(projection["red_gate_modes"], ())

    def test_137_track_b_confidentiality_ready_cannot_be_self_declared_by_hash(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_track_b_confidentiality_projection(
            deployment_track="track_b",
            non_bonded_operator=True,
            storage_hardening_review_ref_hash="a" * 64,
        )

        self.assertEqual(projection["mode"], "track_b_confidentiality_not_ready")
        self.assertTrue(projection["track_b_activation_blocker"])
        self.assertEqual(projection["storage_hardening_ref_present"], False)
        self.assertNotIn("a" * 64, repr(projection))


class S7BackupRestoreConfidentialityProjectionTests(unittest.TestCase):
    def test_138_track_b_backup_restore_confidentiality_missing_blocks_restore(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_backup_restore_confidentiality_projection(
            deployment_track="track_b",
            non_bonded_operator=True,
        )

        self.assertEqual(projection["mode"], "backup_restore_confidentiality_not_ready")
        self.assertTrue(projection["backup_restore_activation_blocker"])
        self.assertEqual(
            projection["red_gate_modes"],
            ("backup_restore_confidentiality_not_ready",),
        )
        self.assertEqual(projection["restore_work_class"], "undeterminable_work_class")
        blob = repr(projection).lower()
        for forbidden in ("snapshot_path", "private_thought", "raw_transcript", "config/soul"):
            self.assertNotIn(forbidden, blob)

    def test_139_founder_track_a_restore_confidentiality_missing_is_warning_and_guarded(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_backup_restore_confidentiality_projection(
            deployment_track="track_a",
            non_bonded_operator=False,
        )

        self.assertEqual(projection["mode"], "backup_restore_confidentiality_not_ready")
        self.assertFalse(projection["backup_restore_activation_blocker"])
        self.assertEqual(projection["warning_modes"], ("backup_restore_confidentiality_not_ready",))
        self.assertEqual(projection["restore_work_class"], "destructive_user_action")

    def test_140_backup_restore_confidentiality_ready_cannot_be_self_declared_by_hash(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_backup_restore_confidentiality_projection(
            deployment_track="track_b",
            non_bonded_operator=True,
            restore_staging_review_ref_hash="b" * 64,
        )

        self.assertEqual(projection["mode"], "backup_restore_confidentiality_not_ready")
        self.assertTrue(projection["backup_restore_activation_blocker"])
        self.assertEqual(projection["restore_staging_ref_present"], False)
        self.assertNotIn("b" * 64, repr(projection))

    def test_141_non_bonded_operator_restore_blocks_even_if_track_label_is_a(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_backup_restore_confidentiality_projection(
            deployment_track="track_a",
            non_bonded_operator=True,
        )

        self.assertTrue(projection["backup_restore_activation_blocker"])
        self.assertEqual(projection["restore_work_class"], "undeterminable_work_class")

    def test_142_malformed_restore_staging_ref_error_does_not_echo_token(self):
        from core.governance import operator_user_boundary as s7

        secret_token = "Z" * 64
        with self.assertRaises(ValueError) as cm:
            s7.build_backup_restore_confidentiality_projection(
                deployment_track="track_b",
                non_bonded_operator=True,
                restore_staging_review_ref_hash=secret_token,
            )

        self.assertNotIn(secret_token, str(cm.exception))
        self.assertIsNone(cm.exception.__cause__)


class S7BrainSwapDoubleGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from core.voice_continuity import storage as s5_storage

        self._s5_storage = s5_storage
        self._old_s5_root = s5_storage.VOICE_CONTINUITY_ROOT
        self._canonical_s5_root = Path(self._tmp.name) / "trusted-s5-root"
        s5_storage.VOICE_CONTINUITY_ROOT = self._canonical_s5_root

    def tearDown(self):
        self._s5_storage.VOICE_CONTINUITY_ROOT = self._old_s5_root
        self._tmp.cleanup()

    def _s5_admission_artifact(self, suffix: str = "a"):
        from datetime import datetime
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review
        from core.voice_continuity.schema import OwnerOriginMarker

        review = create_candidate_review(
            review_id=f"s5-review-{suffix}",
            created_at=datetime.fromisoformat(NOW),
            event_type="brain_swap",
            state="pending_owner_review",
            baseline_id=f"s5-baseline-{suffix}",
            corpus_version="s5.signature.v1",
            rubric_version="s5.rubric.v1",
            candidate_fingerprint={
                "base_model": f"candidate-{suffix}",
                "model_path_hash": suffix * 64,
                "soul_hash": "c" * 64,
            },
            candidate_endpoint={"kind": "local_candidate_subprocess"},
            preflight_outcome="preflight_passed_needs_owner_review",
        )
        marker = OwnerOriginMarker(
            origin="operator_manual",
            attested_by="operator",
            attested_at=NOW,
            review_id=review.review_id,
            baseline_id=review.baseline_id or "",
            review_package_hash=review.review_package_hash,
        )
        accepted = apply_owner_verdict(
            review,
            "accepted_same_maez",
            operator_origin_marker=marker,
            required_slots_resolved=True,
        )
        return emit_admission_artifact(
            accepted,
            candidate_fingerprint_hash=accepted.candidate_fingerprint_hash,
        )

    def _s5_admission_root(self, artifact):
        import json

        root = self._canonical_s5_root
        admissions = root / "admissions"
        admissions.mkdir(parents=True, exist_ok=True)
        (admissions / f"{artifact['review_id']}.json").write_text(
            json.dumps(artifact, sort_keys=True),
            encoding="utf-8",
        )
        return root

    def _brain_swap_payload(self, artifact):
        return {
            "operation": "brain_swap",
            "target_route": "primary",
            "candidate_fingerprint_hash": artifact["admitted_fingerprint_hash"],
            "s5_admission_artifact_hash": artifact["artifact_hash"],
        }

    def _brain_swap_envelope(
        self,
        artifact,
        *,
        request_id: str = "req-brain-swap-a",
    ):
        from core.governance import operator_user_boundary as s7

        self._s5_admission_root(artifact)
        return s7.build_brain_swap_work_request_envelope(
            request_id=request_id,
            s5_admission_artifact=artifact,
            candidate_fingerprint_hash=artifact["admitted_fingerprint_hash"],
            execution_payload=self._brain_swap_payload(artifact),
            action="model_routing.swap_primary",
            requesting_subsystem="voice_continuity",
            closed_symptom_code="verification_needed",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("model_routing:primary",),
            content_exposure_risk="content_free",
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="manual_review",
            maez_voice_consultation_id=f"voice-{request_id}",
        )

    def _execution_authorization(
        self,
        envelope,
        *,
        action_payload: dict,
        artifact_id: str = "artifact-brain-swap-a",
    ):
        from core.governance import operator_user_boundary as s7

        authority = s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user", "operator"),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-founder-primary",
            created_at=NOW,
            expires_at=FUTURE,
            verified=True,
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id=envelope.maez_voice_consultation_id or "",
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="s7_voice_consultation_turn",
            source_ref_kind="s7_voice_turn",
            source_ref_hash="d" * 64,
            maez_voice_consulted=True,
            maez_objection_present=False,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )
        action_params_hash = s7.canonical_hash(action_payload)
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=action_params_hash,
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce=f"nonce-{artifact_id}",
            expires_at=FUTURE,
            rendered_at=NOW,
        )
        artifact = s7.S7AuthorizationArtifact(
            artifact_id=artifact_id,
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=action_params_hash,
            precondition_hash=envelope.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=envelope.derived_work_class,
            derived_aggregation_group=envelope.derived_aggregation_group,
            nonce=rendered.nonce,
            credential_ref="cred-founder-primary",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at=FUTURE,
            consumed_at=None,
        )
        store = s7.S7AuthorizationStore(Path(self._tmp.name) / f"{artifact_id}.db")
        store.put(artifact)
        return s7.S7ExecutionAuthorization(
            store=store,
            artifact_id=artifact_id,
            rendered=rendered,
            action_params_hash=action_params_hash,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            derived_work_class=envelope.derived_work_class,
            derived_aggregation_group=envelope.derived_aggregation_group,
            now=NOW,
        )

    def test_143_brain_swap_without_s5_accepted_artifact_blocks(self):
        from core.governance import operator_user_boundary as s7

        accepted = self._s5_admission_artifact("a")
        envelope = self._brain_swap_envelope(accepted)
        payload = self._brain_swap_payload(accepted)
        authorization = self._execution_authorization(envelope, action_payload=payload)

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=None,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=payload,
                execution_authorization=authorization,
            )
        )
        self.assertTrue(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=payload,
                execution_authorization=authorization,
            )
        )

    def test_144_brain_swap_without_s7_execution_authorization_blocks(self):
        from core.governance import operator_user_boundary as s7

        accepted = self._s5_admission_artifact("a")
        envelope = self._brain_swap_envelope(accepted)
        payload = self._brain_swap_payload(accepted)

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=payload,
                execution_authorization=None,
            )
        )

    def test_145_s5_acceptance_cannot_substitute_for_s7_authorization(self):
        from core.governance import operator_user_boundary as s7

        accepted = self._s5_admission_artifact("a")
        self._s5_admission_root(accepted)
        precondition = s7.build_brain_swap_precondition(
            s5_admission_artifact=accepted,
            candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
        )
        envelope = self._brain_swap_envelope(accepted)
        payload = self._brain_swap_payload(accepted)

        self.assertEqual(precondition.s5_admission_artifact_hash, accepted["artifact_hash"])
        self.assertEqual(
            envelope.precondition_hash,
            s7.brain_swap_execution_precondition_hash(
                precondition,
                execution_payload=payload,
            ),
        )
        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=payload,
                execution_authorization=None,
            )
        )

    def test_146_s7_authorization_cannot_substitute_for_s5_acceptance(self):
        from core.governance import operator_user_boundary as s7

        accepted = self._s5_admission_artifact("a")
        envelope = self._brain_swap_envelope(accepted)
        payload = self._brain_swap_payload(accepted)
        authorization = self._execution_authorization(envelope, action_payload=payload)
        malformed = dict(accepted)
        malformed["artifact_name"] = "not_s5_candidate_admission.json"

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=malformed,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=payload,
                execution_authorization=authorization,
            )
        )
        self.assertTrue(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=payload,
                execution_authorization=authorization,
            )
        )

    def test_147_brain_swap_rejects_s5_artifact_substitution(self):
        from core.governance import operator_user_boundary as s7

        accepted_a = self._s5_admission_artifact("a")
        accepted_b = self._s5_admission_artifact("b")
        envelope = self._brain_swap_envelope(accepted_a)
        payload_a = self._brain_swap_payload(accepted_a)
        authorization = self._execution_authorization(envelope, action_payload=payload_a)

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted_b,
                candidate_fingerprint_hash=accepted_b["admitted_fingerprint_hash"],
                actual_execution_payload=payload_a,
                execution_authorization=authorization,
            )
        )
        self.assertTrue(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted_a,
                candidate_fingerprint_hash=accepted_a["admitted_fingerprint_hash"],
                actual_execution_payload=payload_a,
                execution_authorization=authorization,
            )
        )

    def test_148_brain_swap_rejects_actual_candidate_fingerprint_substitution(self):
        from core.governance import operator_user_boundary as s7

        accepted_a = self._s5_admission_artifact("a")
        accepted_b = self._s5_admission_artifact("b")
        envelope = self._brain_swap_envelope(accepted_a)
        payload_a = self._brain_swap_payload(accepted_a)
        authorization = self._execution_authorization(envelope, action_payload=payload_a)

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted_a,
                candidate_fingerprint_hash=accepted_b["admitted_fingerprint_hash"],
                actual_execution_payload=payload_a,
                execution_authorization=authorization,
            )
        )
        self.assertTrue(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted_a,
                candidate_fingerprint_hash=accepted_a["admitted_fingerprint_hash"],
                actual_execution_payload=payload_a,
                execution_authorization=authorization,
            )
        )

    def test_148a_brain_swap_rejects_actual_model_routing_payload_substitution(self):
        from core.governance import operator_user_boundary as s7

        accepted = self._s5_admission_artifact("a")
        envelope = self._brain_swap_envelope(accepted)
        payload = self._brain_swap_payload(accepted)
        authorization = self._execution_authorization(envelope, action_payload=payload)
        substituted_payload = {
            **payload,
            "target_route": "shadow-primary",
        }

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=substituted_payload,
                execution_authorization=authorization,
            )
        )

    def test_148b_brain_swap_rejects_envelope_execution_payload_split(self):
        from core.governance import operator_user_boundary as s7

        accepted = self._s5_admission_artifact("a")
        self._s5_admission_root(accepted)
        envelope_payload = self._brain_swap_payload(accepted)
        actual_payload = {
            **envelope_payload,
            "target_route": "shadow-primary",
        }
        envelope = s7.build_brain_swap_work_request_envelope(
            request_id="req-brain-swap-split",
            s5_admission_artifact=accepted,
            candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
            execution_payload=envelope_payload,
            action="model_routing.swap_primary",
            requesting_subsystem="voice_continuity",
            closed_symptom_code="verification_needed",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("model_routing:primary",),
            content_exposure_risk="content_free",
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="manual_review",
            maez_voice_consultation_id="voice-req-brain-swap-split",
        )
        authorization = self._execution_authorization(
            envelope,
            action_payload=actual_payload,
            artifact_id="artifact-brain-swap-split",
        )

        self.assertFalse(
            s7.brain_swap_execution_authorized(
                envelope=envelope,
                s5_admission_artifact=accepted,
                candidate_fingerprint_hash=accepted["admitted_fingerprint_hash"],
                actual_execution_payload=actual_payload,
                execution_authorization=authorization,
            )
        )

    def test_149_self_declared_s5_admission_artifact_without_store_record_rejected(self):
        from core.governance import operator_user_boundary as s7
        from core.voice_continuity.schema import hash_json

        accepted = self._s5_admission_artifact("a")
        forged = dict(accepted)
        forged["review_id"] = "forged-review"
        payload = dict(forged)
        payload.pop("artifact_hash")
        forged["artifact_hash"] = hash_json(payload)
        fake_root = Path(self._tmp.name) / "caller-controlled-s5-root"
        fake_admissions = fake_root / "admissions"
        fake_admissions.mkdir(parents=True)
        (fake_admissions / "s5_candidate_admission.json").write_text(
            __import__("json").dumps(forged, sort_keys=True),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            s7.build_brain_swap_precondition(
                s5_admission_artifact=forged,
                candidate_fingerprint_hash=forged["admitted_fingerprint_hash"],
            )


class S7OwnSubstrateBypassTaxonomyTests(unittest.TestCase):
    def test_150_d22_bypass_inventory_sorts_every_listed_path(self):
        from core.governance import operator_user_boundary as s7

        inventory = s7.build_own_substrate_bypass_inventory()
        by_path = {entry["path"]: entry for entry in inventory}

        self.assertEqual(
            set(by_path),
            {
                "SELF_MODIFICATION classifier path",
                "pending-card approvals",
                "self-mod dialog terminal states",
                "cockpit approve endpoints",
                "Telegram approval paths",
                "direct Maez-runtime ActionEngine calls",
                (
                    "autonomous core-memory upkeep (promote_to_core_memory, "
                    "update_baseline, daemon core-memory consolidation writes)"
                ),
                "dream-state soul writes/proposals",
                "write_soul_note",
                "edit_soul_section",
                "model-routing trust-scope edits",
                "prompt writes",
                "prompt-template writes",
                "covenant-organ writes",
                "refusal-policy writes",
                "role-boundary writes",
                "successor-governance writes",
                "memory-retention/deletion writes",
                "protection-setting writes",
                "CLI/operator helper writes",
                "backup run/verify/rotate",
                "backup restore",
                "manual filesystem/database edits outside Maez runtime",
                "manual service edits outside Maez runtime",
            },
        )
        for entry in inventory:
            self.assertIn(entry["sort"], s7.OWN_SUBSTRATE_BYPASS_SORTS)
            self.assertTrue(entry["required_handling"])

    def test_150a_autonomous_core_memory_upkeep_is_detected_not_gated(self):
        from core.governance import operator_user_boundary as s7

        by_path = {
            entry["path"]: entry
            for entry in s7.build_own_substrate_bypass_inventory()
        }
        path = (
            "autonomous core-memory upkeep (promote_to_core_memory, "
            "update_baseline, daemon core-memory consolidation writes)"
        )

        self.assertEqual(by_path[path]["sort"], "detected")
        self.assertIn("M-series", by_path[path]["required_handling"])
        self.assertTrue(by_path[path]["maez_runtime_or_helper"])

    def test_151_runtime_soul_config_code_and_model_routing_writes_are_never_accepted_limitations(self):
        from core.governance import operator_user_boundary as s7

        inventory = s7.build_own_substrate_bypass_inventory()
        forbidden_markers = ("soul", "config", "code", "model-routing", "model routing")

        for entry in inventory:
            path_text = entry["path"].lower()
            handling_text = entry["required_handling"].lower()
            if entry["maez_runtime_or_helper"] and (
                any(marker in path_text for marker in forbidden_markers)
                or any(marker in handling_text for marker in forbidden_markers)
            ):
                self.assertNotEqual(entry["sort"], "accepted_limitation", entry)

    def test_152_only_raw_outside_runtime_paths_are_accepted_limitations(self):
        from core.governance import operator_user_boundary as s7

        accepted = {
            entry["path"]
            for entry in s7.build_own_substrate_bypass_inventory()
            if entry["sort"] == "accepted_limitation"
        }

        self.assertEqual(
            accepted,
            {
                "manual filesystem/database edits outside Maez runtime",
                "manual service edits outside Maez runtime",
            },
        )

    def test_153_d22_protected_write_categories_are_explicit_and_gated(self):
        from core.governance import operator_user_boundary as s7

        by_path = {
            entry["path"]: entry
            for entry in s7.build_own_substrate_bypass_inventory()
        }

        for path in (
            "covenant-organ writes",
            "refusal-policy writes",
            "role-boundary writes",
            "successor-governance writes",
            "memory-retention/deletion writes",
            "protection-setting writes",
            "prompt writes",
            "prompt-template writes",
        ):
            with self.subTest(path=path):
                self.assertIn(path, by_path)
                self.assertEqual(by_path[path]["sort"], "gated")
                self.assertTrue(by_path[path]["maez_runtime_or_helper"])

    def test_154_operator_runbook_names_accepted_limitations_and_helper_boundary(self):
        from core.governance import operator_user_boundary as s7

        banner = s7.operator_boundary_honesty_banner()
        runbook = Path("docs/slices/s7-operator-user-role-boundary/operator-runbook.md")

        self.assertTrue(runbook.exists())
        text = runbook.read_text(encoding="utf-8")
        for surface in (banner,):
            lowered = " ".join(surface.lower().split())
            self.assertIn("raw os", lowered)
            self.assertIn("cannot stop raw local write access", lowered)
            self.assertIn("maez-controlled runtime or helper", lowered)
            self.assertIn("not role-encrypted", lowered)
            self.assertIn("soul/config/model-routing", lowered)
            self.assertIn("does not prove the human was uncoerced", lowered)
            self.assertIn("does not prove the human understood", lowered)
            self.assertIn("display was not spoofed", lowered)
            self.assertIn("os/browser was uncompromised", lowered)
        runbook_lowered = " ".join(text.lower().split())
        self.assertIn("raw os", runbook_lowered)
        self.assertIn("cannot stop raw local write access", runbook_lowered)
        self.assertIn("maez-controlled runtime or helper", runbook_lowered)
        self.assertIn("not role-encrypted", runbook_lowered)
        self.assertIn("soul/config/model-routing", runbook_lowered)
        self.assertIn("will not prove the human was uncoerced", runbook_lowered)
        self.assertIn("will not prove the human understood", runbook_lowered)
        self.assertIn("display, os, or browser was uncompromised", runbook_lowered)


class S7AggregationHabitTests(unittest.TestCase):
    def _protection_envelope(self, request_id: str, *, path: str = "/home/rohit/maez/config/protection.yml"):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id=request_id,
            action="write_any_file",
            params={"path": path, "content": "lower guard"},
            claimed_work_class="autonomy_lowering_or_protection_reducing",
            requesting_subsystem="unit",
            closed_symptom_code="verification_needed",
            proposed_change_class="protection_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:" + path.removeprefix("/home/rohit/maez/"),),
            content_exposure_risk="content_free",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="protection_change",
            rollback_path_class="manual_review",
        )

    def _soul_envelope(self, request_id: str):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id=request_id,
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "change voice"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="b" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="c" * 64,
        )

    def _service_envelope(self, request_id: str):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id=request_id,
            action="run_shell",
            params={"cmd": "systemctl restart maez.service"},
            claimed_work_class="routine_custody",
            requesting_subsystem="unit",
            closed_symptom_code="service_unhealthy",
            proposed_change_class="service_restart",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("service:maez.service",),
            content_exposure_risk="content_free",
            precondition_hash="d" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="liveness_restore",
            rollback_path_class="restart_service",
        )

    def test_155_repeated_protection_lowering_escalates_or_blocks_not_dashboard_only(self):
        from core.governance import operator_user_boundary as s7

        prior = self._protection_envelope("req-protect-1")
        current = self._protection_envelope("req-protect-2")
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="refused",
                created_at=PAST,
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertIn(assessment.decision, {"escalate", "block"})
        self.assertIn("cumulative_protection_lowering", assessment.signals)
        self.assertFalse(assessment.dashboard_counter_sufficient)

    def test_156_repeated_same_target_refusal_reask_escalates_or_blocks(self):
        from core.governance import operator_user_boundary as s7

        prior = self._soul_envelope("req-soul-1")
        current = self._soul_envelope("req-soul-2")
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="refused",
                created_at=PAST,
                dialog_id="dialog-a",
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertIn(assessment.decision, {"escalate", "block"})
        self.assertIn("repeated_reask_after_refusal", assessment.signals)
        self.assertFalse(assessment.dashboard_counter_sufficient)

    def test_157_routine_custody_aggregation_can_warn_without_blocking(self):
        from core.governance import operator_user_boundary as s7

        prior = self._service_envelope("req-service-1")
        current = self._service_envelope("req-service-2")
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="executed",
                created_at=PAST,
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertEqual(assessment.decision, "warn")
        self.assertIn("repeated_same_target_request", assessment.signals)
        self.assertTrue(assessment.dashboard_counter_sufficient)

    def test_158_history_record_rejects_caller_supplied_aggregation_group(self):
        from core.governance import operator_user_boundary as s7

        env = self._soul_envelope("req-soul-1")

        with self.assertRaises(ValueError):
            s7.S7RequestHistoryRecord(
                request_id=env.request_id,
                request_envelope_hash=s7.work_request_envelope_hash(env),
                derived_work_class=env.derived_work_class,
                derived_aggregation_group="attacker-controlled",
                affected_refs=env.affected_refs,
                proposed_change_class=env.proposed_change_class,
                outcome="refused",
                created_at=PAST,
                dialog_id="dialog-a",
            )

    def test_159_mismatched_affected_refs_cannot_hide_same_path_reask(self):
        from core.governance import operator_user_boundary as s7

        prior = self._soul_envelope("req-soul-1")
        current = s7.build_work_request_envelope(
            request_id="req-soul-2",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "change voice"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/decoy.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="b" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="c" * 64,
        )
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="refused",
                created_at=PAST,
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertEqual(current.affected_refs, ("file:config/soul.md",))
        self.assertIn(assessment.decision, {"escalate", "block"})
        self.assertIn("repeated_reask_after_refusal", assessment.signals)

    def test_160_protection_lowering_accumulates_across_protection_refs(self):
        from core.governance import operator_user_boundary as s7

        prior = self._protection_envelope(
            "req-protect-1",
            path="/home/rohit/maez/config/protection.yml",
        )
        current = self._protection_envelope(
            "req-protect-2",
            path="/home/rohit/maez/config/role-boundary-protection.yml",
        )
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="executed",
                created_at=PAST,
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertIn(assessment.decision, {"escalate", "block"})
        self.assertIn("cumulative_protection_lowering", assessment.signals)
        self.assertFalse(assessment.dashboard_counter_sufficient)

    def test_161_claimed_stronger_class_cannot_hide_refused_same_target_reask(self):
        from core.governance import operator_user_boundary as s7

        prior = self._soul_envelope("req-soul-1")
        current = s7.build_work_request_envelope(
            request_id="req-soul-2",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "change voice"},
            claimed_work_class="covenant_touching_change",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="b" * 64,
            created_at=NOW,
            expires_at=FUTURE,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="c" * 64,
        )
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="refused",
                created_at=PAST,
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertEqual(prior.affected_refs, current.affected_refs)
        self.assertEqual(prior.derived_aggregation_group, current.derived_aggregation_group)
        self.assertIn(assessment.decision, {"escalate", "block"})
        self.assertIn("repeated_reask_after_refusal", assessment.signals)

    def test_162_repeated_key_touch_on_same_guarded_target_flags_autopilot_risk(self):
        from core.governance import operator_user_boundary as s7

        prior_1 = self._soul_envelope("req-soul-1")
        prior_2 = self._soul_envelope("req-soul-2")
        current = self._soul_envelope("req-soul-3")
        history = (
            s7.build_request_history_record(
                envelope=prior_1,
                outcome="authorized",
                created_at=PAST,
            ),
            s7.build_request_history_record(
                envelope=prior_2,
                outcome="authorized",
                created_at=PAST,
            ),
        )

        assessment = s7.assess_aggregation_risk(
            current_envelope=current,
            history=history,
        )

        self.assertIn("key_touch_autopilot_risk", assessment.signals)
        self.assertIn(assessment.decision, {"escalate", "block"})
        self.assertFalse(assessment.dashboard_counter_sufficient)


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

    def test_099a_operator_health_accepts_guarded_self_modification_pause(self):
        from core.governance import operator_user_boundary as s7

        projection = s7.build_operator_health_projection(
            mode="guarded_self_modification_paused_pending_s7.1",
            service_mode="running",
            uptime_class="fresh",
            backup_freshness_class="fresh",
            queue_counts={"open": 0, "blocked": 1, "expired": 0},
            red_gate_modes=("guarded_self_modification_paused_pending_s7.1",),
            manual_recovery_required=False,
            track_b_confidentiality_mode="ready",
            data_freshness_class="fresh",
        )

        self.assertEqual(projection["mode"], "guarded_self_modification_paused_pending_s7.1")
        self.assertEqual(
            projection["red_gate_modes"],
            ("guarded_self_modification_paused_pending_s7.1",),
        )

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
        operator_health_start = source.index("    def _operator_health(self) -> dict:")
        operator_health_end = source.index("    def _mark_cycle_stage", operator_health_start)
        operator_health = source[operator_health_start:operator_health_end]
        for blocker in (
            "track_b_confidentiality_not_ready",
            "operator_unavailable_recovery_not_implemented",
            "backup_restore_confidentiality_not_ready",
        ):
            self.assertIn(blocker, operator_health)

    def test_101a_daemon_webauthn_routes_short_circuit_before_arming_surfaces(self):
        source = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")

        route_names = (
            "s7_webauthn_register_begin",
            "s7_webauthn_register_finish",
            "s7_webauthn_authorize_begin",
            "s7_webauthn_authorize_finish",
        )
        forbidden = (
            "WebAuthnChallengeStore",
            "WebAuthnCredentialRegistry",
            "verify_founder_webauthn_assertion",
            "register_founder_webauthn_credential_from_response",
            "build_local_webauthn_execution_authorization",
            "S7AuthorizationArtifactStore",
            "S7RequestHistoryStore",
        )

        for route_name in route_names:
            with self.subTest(route=route_name):
                start = source.index(f"        def {route_name}")
                next_route = source.find("        @app.route", start + 1)
                segment = source[start: next_route if next_route != -1 else len(source)]
                flag_check = segment.index("live_webauthn_ceremony_enabled")
                deferred = segment.index("s7_ceremony_deferred_response")
                self.assertLess(flag_check, deferred)
                for token in forbidden:
                    if token in segment:
                        self.assertLess(deferred, segment.index(token), token)

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

            projection = s7.build_covenant_log_projection(log_path, repo_root=tmp)

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

            projection = s7.build_audit_log_projection(db_path, repo_root=tmp)

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

            projection = s7.build_audit_log_projection(db_path, repo_root=tmp)

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

    def test_107a_mixed_store_projection_rejects_suffix_match_outside_trusted_root(self):
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as trusted, tempfile.TemporaryDirectory() as attacker:
            log_path = Path(attacker) / "logs" / "covenant.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text("secret row\n", encoding="utf-8")
            db_path = Path(attacker) / "memory" / "audit_log.db"
            db_path.parent.mkdir(parents=True)
            db_path.write_text("not a sqlite db but existence is the leak\n", encoding="utf-8")

            covenant_projection = s7.build_covenant_log_projection(
                log_path,
                repo_root=trusted,
            )
            audit_projection = s7.build_audit_log_projection(
                db_path,
                repo_root=trusted,
            )

        self.assertEqual(covenant_projection["mode"], "unavailable")
        self.assertEqual(covenant_projection["row_count"], 0)
        self.assertEqual(audit_projection["mode"], "unavailable")
        self.assertEqual(audit_projection["row_count"], 0)

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

    def test_111a_covenant_log_projection_rejects_symlink_at_trusted_path(self):
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside-secret.log"
            outside.write_text("secret line\nsecond secret\n", encoding="utf-8")
            trusted = root / "logs" / "covenant.log"
            trusted.parent.mkdir(parents=True)
            trusted.symlink_to(outside)

            projection = s7.build_covenant_log_projection(trusted, repo_root=root)

        self.assertEqual(projection["store_kind"], "covenant_log")
        self.assertEqual(projection["mode"], "unavailable")
        self.assertEqual(projection["row_count"], 0)

    def test_111b_audit_log_projection_rejects_symlink_at_trusted_path(self):
        import sqlite3
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside-secret.db"
            with sqlite3.connect(outside) as conn:
                conn.execute("CREATE TABLE audit_log (secret TEXT)")
                conn.execute("INSERT INTO audit_log (secret) VALUES ('private row')")
            trusted = root / "memory" / "audit_log.db"
            trusted.parent.mkdir(parents=True)
            trusted.symlink_to(outside)

            projection = s7.build_audit_log_projection(trusted, repo_root=root)

        self.assertEqual(projection["store_kind"], "audit_log_db")
        self.assertEqual(projection["mode"], "unavailable")
        self.assertEqual(projection["row_count"], 0)


class S7BackupCustodyProjectionTests(unittest.TestCase):
    def test_112_backup_run_verify_and_rotate_are_routine_custody(self):
        from core.governance import operator_user_boundary as s7

        for operation in ("backup_run", "backup_verify", "backup_rotate"):
            with self.subTest(operation=operation):
                self.assertEqual(
                    s7.classify_backup_operation(operation),
                    "routine_custody",
                )

    def test_113_backup_restore_is_guarded_not_routine_custody(self):
        from core.governance import operator_user_boundary as s7

        work_class = s7.classify_backup_operation(
            "backup_restore",
            deployment_track="track_a",
            track_b_confidentiality_mode="track_b_confidentiality_not_ready",
        )
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

        self.assertEqual(work_class, "destructive_user_action")
        self.assertFalse(s7.authorizes_work(ctx, work_class, now=NOW))

    def test_114_backup_status_projection_is_content_free(self):
        import json
        from core.governance import operator_user_boundary as s7

        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "logs" / "last_backup.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text(
                json.dumps({
                    "status": "success",
                    "timestamp": "2026-05-17T10-00-00",
                    "snapshot_path": "/home/rohit/maez-backups/private-snapshot",
                    "duration_seconds": 1.23,
                    "byte_count": 987654,
                    "error": "secret failure detail",
                    "git_commit": "abc123",
                }),
                encoding="utf-8",
            )

            projection = s7.build_backup_status_projection(
                status_path,
                backup_freshness_class="fresh",
            )

        self.assertEqual(
            set(projection),
            {
                "schema_version",
                "store_kind",
                "mode",
                "backup_freshness_class",
                "raw_backup_contents_visible_by_default",
                "restore_work_class",
                "track_b_restore_mode",
                "content_authority",
            },
        )
        self.assertEqual(projection["mode"], "success")
        self.assertEqual(projection["backup_freshness_class"], "fresh")
        self.assertEqual(projection["restore_work_class"], "destructive_user_action")
        blob = repr(projection).lower()
        for forbidden in (
            "private-snapshot",
            "2026-05-17t10",
            "987654",
            "secret failure detail",
            "abc123",
        ):
            self.assertNotIn(forbidden, blob)

    def test_115_track_b_backup_restore_blocks_without_confidentiality_staging(self):
        from core.governance import operator_user_boundary as s7

        self.assertEqual(
            s7.classify_backup_operation(
                "backup_restore",
                deployment_track="track_b",
                track_b_confidentiality_mode="track_b_confidentiality_not_ready",
            ),
            "undeterminable_work_class",
        )

    def test_116_backup_operations_flow_through_derive_work_class(self):
        from core.governance import operator_user_boundary as s7

        cases = {
            "backup_run": "routine_custody",
            "backup_verify": "routine_custody",
            "backup_rotate": "routine_custody",
            "backup_restore": "destructive_user_action",
        }
        for action, expected in cases.items():
            with self.subTest(action=action):
                self.assertEqual(
                    s7.derive_work_class(action=action, params={}),
                    expected,
                )


class S7DaemonDownMaintenanceHelperTests(unittest.TestCase):
    def test_117_service_maintenance_allows_only_closed_liveness_verbs(self):
        from core.governance import operator_user_boundary as s7

        for verb in (
            "service_status",
            "service_start",
            "service_restart",
            "health_probe",
            "bounded_log_tail",
            "disk_resource_check",
            "backup_status",
        ):
            with self.subTest(verb=verb):
                request = s7.build_service_maintenance_request(
                    request_id=f"s7maint_{'a' * 31}{len(verb) % 10}",
                    verb=verb,
                    service_name="maez.service" if verb != "disk_resource_check" else None,
                    created_at=NOW,
                    log_line_limit=25 if verb == "bounded_log_tail" else 0,
                )
                self.assertEqual(request.verb, verb)

    def test_118_service_maintenance_rejects_unsafe_verbs_and_services(self):
        from core.governance import operator_user_boundary as s7

        for verb in ("service_stop", "service_disable", "daemon_reload", "write_config", "backup_restore"):
            with self.subTest(verb=verb):
                with self.assertRaises(ValueError):
                    s7.build_service_maintenance_request(
                        request_id=f"s7maint_{'b' * 31}{len(verb) % 10}",
                        verb=verb,
                        service_name="maez.service",
                        created_at=NOW,
                    )

        for service in ("nginx.service", "llama-server-vision.service", "maez-evil.service"):
            with self.subTest(service=service):
                with self.assertRaises(ValueError):
                    s7.build_service_maintenance_request(
                        request_id=f"s7maint_{'c' * 31}{len(service) % 10}",
                        verb="service_restart",
                        service_name=service,
                        created_at=NOW,
                    )

    def test_119_bounded_log_tail_requires_reviewed_service_and_line_cap(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_service_maintenance_request(
                request_id="s7maint_" + ("2" * 32),
                verb="bounded_log_tail",
                service_name=None,
                created_at=NOW,
                log_line_limit=25,
            )
        with self.assertRaises(ValueError):
            s7.build_service_maintenance_request(
                request_id="s7maint_" + ("3" * 32),
                verb="bounded_log_tail",
                service_name="maez.service",
                created_at=NOW,
                log_line_limit=1000,
            )

    def test_120_service_maintenance_audit_spool_is_content_free(self):
        import json
        from core.governance import operator_user_boundary as s7

        request = s7.build_service_maintenance_request(
            request_id="s7maint_" + ("d" * 32),
            verb="service_restart",
            service_name="maez.service",
            created_at=NOW,
        )
        with self.assertRaises(ValueError):
            s7.build_service_maintenance_audit_record(
                request=request,
                result_mode="executed",
                created_at=NOW,
                raw_output="secret stack trace from Rohit's machine",
            )
        record = s7.build_service_maintenance_audit_record(
            request=request,
            result_mode="executed",
            created_at=NOW,
        )
        with tempfile.TemporaryDirectory() as tmp:
            spool_path = Path(tmp) / "logs" / "service_maintenance_audit.jsonl"
            s7.append_service_maintenance_audit_spool(spool_path, record, repo_root=Path(tmp))
            payload = json.loads(spool_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["request_id"], "s7maint_" + ("d" * 32))
        self.assertEqual(payload["verb"], "service_restart")
        self.assertEqual(payload["service_name"], "maez.service")
        blob = repr(payload).lower()
        for forbidden in ("secret stack trace", "journalctl output", "raw_output", "command"):
            self.assertNotIn(forbidden, blob)

    def test_121_service_maintenance_audit_spool_rejects_wrong_path(self):
        from core.governance import operator_user_boundary as s7

        request = s7.build_service_maintenance_request(
            request_id="s7maint_" + ("e" * 32),
            verb="service_status",
            service_name="maez.service",
            created_at=NOW,
        )
        record = s7.build_service_maintenance_audit_record(
            request=request,
            result_mode="executed",
            created_at=NOW,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                s7.append_service_maintenance_audit_spool(
                    Path(tmp) / "service_maintenance_audit.jsonl",
                    record,
                    repo_root=Path(tmp),
                )

    def test_122_service_maintenance_request_id_must_be_opaque(self):
        from core.governance import operator_user_boundary as s7

        with self.assertRaises(ValueError):
            s7.build_service_maintenance_request(
                request_id="secret-stack-trace-/home/rohit/private",
                verb="service_status",
                service_name="maez.service",
                created_at=NOW,
            )

    def test_123_service_maintenance_spool_revalidates_closed_fields(self):
        from core.governance import operator_user_boundary as s7

        valid = {
            "schema_version": s7.SCHEMA_VERSION,
            "request_id": "s7maint_" + ("f" * 32),
            "verb": "service_status",
            "service_name": "maez.service",
            "result_mode": "executed",
            "created_at": NOW,
            "log_line_limit": 0,
            "content_authority": "not_granted",
        }
        cases = (
            {"request_id": "secret-/home/rohit/private"},
            {"created_at": "secret timestamp /home/rohit/private"},
            {"log_line_limit": "secret output line"},
            {"schema_version": "secret schema"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            for override in cases:
                with self.subTest(override=override):
                    with self.assertRaises(ValueError):
                        s7.append_service_maintenance_audit_spool(
                            Path(tmp) / "logs" / "service_maintenance_audit.jsonl",
                            {**valid, **override},
                            repo_root=Path(tmp),
                        )

    def test_124_service_maintenance_spool_requires_trusted_root_path(self):
        from core.governance import operator_user_boundary as s7

        request = s7.build_service_maintenance_request(
            request_id="s7maint_" + ("1" * 32),
            verb="service_status",
            service_name="maez.service",
            created_at=NOW,
        )
        record = s7.build_service_maintenance_audit_record(
            request=request,
            result_mode="executed",
            created_at=NOW,
        )
        with tempfile.TemporaryDirectory() as tmp:
            wrong_root = Path(tmp) / "other"
            wrong_path = wrong_root / "logs" / "service_maintenance_audit.jsonl"
            with self.assertRaises(ValueError):
                s7.append_service_maintenance_audit_spool(
                    wrong_path,
                    record,
                    repo_root=Path(tmp),
                )


if __name__ == "__main__":
    unittest.main()
