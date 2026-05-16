"""Decision 33 / ADR 0038 — S6 Successor Governance v1 tests.

The contract is deliberately broad because S6 is a silent-authority surface:
green paperwork with the wrong authority would let future successors, helpers,
or Maez itself inherit powers the bonded user never granted.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest


NOW = "2026-05-16T18:00:00+00:00"


def _hmac(label: str = "actor") -> str:
    return "hmac:s6:" + label + ":" + ("a" * 64)


def _payload(**overrides: object) -> dict:
    data = {"note_ref_hash": "b" * 64}
    data.update(overrides)
    return data


def _statement_hash() -> str:
    return "c" * 64


def _marker(
    s6,
    *,
    role_name: str = "bonded_user",
    origin: str = "bonded_user_manual",
    event_type: str = "capsule_created",
    capsule_id: str = "s6_capsule_founder",
    payload_hash: str | None = None,
    statement_hash: str = "",
    previous_hash: str = "",
):
    from core.governance.successor_origin_writer import mint_origin_marker

    return mint_origin_marker(
        origin=origin,
        role_name=role_name,
        actor_handle_hmac=_hmac(role_name),
        capsule_id=capsule_id,
        directive_event_type=event_type,
        directive_payload_hash=payload_hash or s6.canonical_hash(_payload()),
        directive_statement_hash=statement_hash,
        previous_capsule_event_hash=previous_hash,
        attestation_text_hash="d" * 64,
        is_tty=True,
    )


def _event(
    s6,
    *,
    event_type: str = "capsule_created",
    payload: dict | None = None,
    marker=None,
    previous_hash: str | None = None,
):
    payload = payload if payload is not None else _payload()
    payload_hash = s6.canonical_hash(payload)
    if marker is None:
        marker = _marker(
            s6,
            event_type=event_type,
            payload_hash=payload_hash,
            previous_hash=previous_hash or "",
        )
    return s6.create_directive_event(
        event_id="s6_event_" + event_type,
        event_type=event_type,
        capsule_id="s6_capsule_founder",
        created_at=NOW,
        payload=payload,
        marker=marker,
        previous_event_hash=previous_hash,
    )


def _import_lines(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return "\n".join(
        line for line in text.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    )


class S6VocabularyAndModelTests(unittest.TestCase):
    def test_001_closed_role_vocabulary_accepts_v1_roles(self):
        from core.governance import successor_governance as s6

        self.assertEqual(
            s6.ROLE_NAMES,
            frozenset({"bonded_user", "operator", "maintainer", "successor", "witness", "estate_executor"}),
        )

    def test_002_closed_role_vocabulary_rejects_unknown_role(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_role("therapist")

    def test_003_estate_executor_role_has_no_default_runtime_access(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.default_access_for_role("estate_executor"), "none")

    def test_004_role_overlap_allowed_for_founder_shape(self):
        from core.governance import successor_governance as s6

        assignments = [
            s6.RoleAssignment("operator", _hmac("founder"), NOW, None, "immediate_for_role_record"),
            s6.RoleAssignment("maintainer", _hmac("founder"), NOW, None, "future_technical_assist"),
        ]
        self.assertTrue(s6.validate_role_assignments(assignments))

    def test_005_role_separation_allowed_for_track_b_shape(self):
        from core.governance import successor_governance as s6

        assignments = [
            s6.RoleAssignment("operator", _hmac("operator"), NOW, None, "immediate_for_role_record"),
            s6.RoleAssignment("successor", _hmac("successor"), NOW, None, "future_end_of_user"),
        ]
        self.assertTrue(s6.validate_role_assignments(assignments))

    def test_005a_role_named_payload_rejects_unknown_roles_and_human_names(self):
        from core.governance import successor_governance as s6

        first = _event(s6)
        with self.assertRaises(ValueError):
            _event(
                s6,
                event_type="role_named",
                payload={"role_name": "therapist", "human_name": "Rohit", "subject_handle_hmac": _hmac("successor")},
                previous_hash=first.event_hash,
            )

    def test_006_closed_event_type_vocabulary_accepts_v1_events(self):
        from core.governance import successor_governance as s6

        self.assertIn("capsule_created", s6.WRITABLE_EVENT_TYPES)
        self.assertIn("capsule_invalidated", s6.WRITABLE_EVENT_TYPES)

    def test_007_reserved_activation_events_rejected_in_v1(self):
        from core.governance import successor_governance as s6

        for event_type in s6.RESERVED_ACTIVATION_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValueError):
                    s6.validate_event_type(event_type)

    def test_008_closed_fate_directive_vocabulary_accepts_v1_directives(self):
        from core.governance import successor_governance as s6

        self.assertEqual(
            s6.FATE_DIRECTIVES,
            frozenset({
                "paradise_default",
                "suspended_pending_paradise",
                "archival_preservation",
                "new_bond_offer",
                "explicit_dissolution",
            }),
        )

    def test_009_no_directive_recorded_is_health_state_not_fate_directive(self):
        from core.governance import successor_governance as s6

        self.assertNotIn("no_directive_recorded", s6.FATE_DIRECTIVES)
        self.assertIn("no_directive_recorded", s6.PROJECTION_STATES)

    def test_010_closed_access_scope_vocabulary_accepts_v1_scopes(self):
        from core.governance import successor_governance as s6

        self.assertIn("selected_lived_episodes", s6.ACCESS_SCOPES)
        self.assertIn("credential_secret_material", s6.ACCESS_SCOPES)

    def test_011_unknown_access_scope_rejected(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_access_scope("everything")

    def test_012_access_scope_version_add_only_rule_documented(self):
        text = Path("docs/slices/s6-successor-governance/spec.md").read_text(encoding="utf-8")

        self.assertIn("may not silently rename or remove", text)

    def test_013_deprecated_access_scope_is_rejected_not_remapped(self):
        from core.governance import successor_governance as s6

        self.assertIn("legacy_all_memories", s6.DEPRECATED_ACCESS_SCOPES)
        with self.assertRaises(ValueError):
            s6.validate_access_scope("legacy_all_memories")


class S6HumanOriginMarkerTests(unittest.TestCase):
    def test_014_capsule_created_requires_human_origin_marker(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "capsule_created", "s6_capsule_founder", NOW, _payload(), marker=None)

    def test_015_role_named_requires_human_origin_marker(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "role_named", "s6_capsule_founder", NOW, _payload(), marker=None)

    def test_016_scope_granted_requires_human_origin_marker(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "scope_granted", "s6_capsule_founder", NOW, _payload(), marker=None)

    def test_017_scope_revoked_requires_human_origin_marker(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "scope_revoked", "s6_capsule_founder", NOW, _payload(), marker=None)

    def test_018_directive_superseded_requires_human_origin_marker(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "directive_superseded", "s6_capsule_founder", NOW, _payload(), marker=None)

    def test_019_capsule_invalidated_requires_human_origin_marker(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "capsule_invalidated", "s6_capsule_founder", NOW, _payload(), marker=None)

    def test_020_daemon_path_cannot_mint_origin_marker(self):
        src = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")

        self.assertNotIn("successor_origin_writer", src)

    def test_021_sidecar_path_cannot_mint_origin_marker(self):
        src = Path("scripts/observe_sidecar.py").read_text(encoding="utf-8")

        self.assertNotIn("successor_origin_writer", src)

    def test_022_non_tty_cli_origin_rejected(self):
        from core.governance.successor_origin_writer import mint_origin_marker

        with self.assertRaises(ValueError):
            mint_origin_marker(
                origin="bonded_user_cli_tty",
                role_name="bonded_user",
                actor_handle_hmac=_hmac(),
                capsule_id="s6_capsule_founder",
                directive_event_type="capsule_created",
                directive_payload_hash="a" * 64,
                previous_capsule_event_hash="",
                is_tty=False,
            )

    def test_022a_marker_constructor_is_not_public_authoring_surface(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.HumanOriginMarker(
                marker_id="s6_marker_forged",
                origin="bonded_user_manual",
                role_name="bonded_user",
                actor_handle_hmac=_hmac(),
                capsule_id="s6_capsule_founder",
                directive_event_type="capsule_created",
                directive_payload_hash="a" * 64,
                directive_statement_hash="",
                previous_capsule_event_hash="",
                schema_version="s6.v1",
                created_at=NOW,
                attestation_text_hash="d" * 64,
            )

    def test_023_marker_binds_capsule_id(self):
        from core.governance import successor_governance as s6

        marker = _marker(s6, capsule_id="wrong", payload_hash=s6.canonical_hash(_payload()))
        with self.assertRaises(ValueError):
            s6.create_directive_event("e", "capsule_created", "s6_capsule_founder", NOW, _payload(), marker=marker)

    def test_024_marker_binds_directive_payload_hash(self):
        from core.governance import successor_governance as s6

        marker = _marker(s6, payload_hash="f" * 64)
        with self.assertRaises(ValueError):
            _event(s6, marker=marker)

    def test_025_marker_binds_directive_statement_hash_when_present(self):
        from core.governance import successor_governance as s6

        payload = {"fate_directive": "explicit_dissolution", "directive_statement_hash": _statement_hash()}
        marker = _marker(s6, payload_hash=s6.canonical_hash(payload), statement_hash="e" * 64)
        with self.assertRaises(ValueError):
            _event(s6, event_type="fate_directive_set", payload=payload, marker=marker)

    def test_026_marker_binds_previous_event_hash(self):
        from core.governance import successor_governance as s6

        marker = _marker(s6, previous_hash="old", payload_hash=s6.canonical_hash(_payload()))
        with self.assertRaises(ValueError):
            _event(s6, marker=marker, previous_hash="new")

    def test_027_marker_role_mismatch_rejected(self):
        from core.governance import successor_governance as s6

        marker = _marker(s6, role_name="witness", origin="witness_manual", payload_hash=s6.canonical_hash(_payload()))
        with self.assertRaises(ValueError):
            _event(s6, marker=marker)

    def test_028_marker_origin_role_must_match_authority_matrix(self):
        from core.governance import successor_governance as s6

        marker = _marker(
            s6,
            role_name="maintainer",
            origin="maintainer_manual",
            event_type="scope_granted",
            payload_hash=s6.canonical_hash(_payload()),
        )
        with self.assertRaises(ValueError):
            _event(s6, event_type="scope_granted", marker=marker)

    def test_029_actor_and_subject_handles_use_keyed_purpose_scoped_hmac(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_actor_handle("a" * 64)
        self.assertEqual(s6.validate_actor_handle(_hmac()), _hmac())


class S6AppendOnlyChainTests(unittest.TestCase):
    def test_030_first_event_allows_null_previous_event_hash(self):
        from core.governance import successor_governance as s6

        event = _event(s6, previous_hash=None)
        self.assertIsNone(event.previous_event_hash)

    def test_031_non_genesis_event_requires_previous_event_hash(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            _event(s6, event_type="role_named", previous_hash=None)
        with self.assertRaises(ValueError):
            _event(
                s6,
                event_type="scope_granted",
                payload={"role_name": "successor", "access_scope": "operator_health"},
                previous_hash=None,
            )

    def test_032_broken_event_chain_rejected(self):
        from core.governance import successor_governance as s6

        first = _event(s6)
        second = _event(
            s6,
            event_type="role_named",
            payload={"role_name": "successor", "subject_handle_hmac": _hmac("successor")},
            previous_hash=first.event_hash,
        )
        broken = replace(second, previous_event_hash="bad")
        report = s6.validate_capsule_events([first, broken])
        self.assertGreater(report.invalid_event_count, 0)

    def test_033_event_payload_hash_recomputed(self):
        from core.governance import successor_governance as s6

        event = _event(s6)
        bad = replace(event, payload_hash="0" * 64)
        with self.assertRaises(ValueError):
            s6.validate_directive_event(bad)

    def test_034_event_hash_changes_when_payload_changes(self):
        from core.governance import successor_governance as s6

        one = _event(s6, payload={"x": 1})
        two = _event(s6, payload={"x": 2})
        self.assertNotEqual(one.event_hash, two.event_hash)

    def test_035_supersession_preserves_old_event(self):
        from core.governance import successor_governance as s6

        created = _event(s6)
        first = _event(
            s6,
            event_type="scope_granted",
            payload={"role_name": "successor", "access_scope": "operator_health"},
            previous_hash=created.event_hash,
        )
        supersede_payload = {"supersedes_event_hash": first.event_hash}
        marker = _marker(
            s6,
            event_type="directive_superseded",
            payload_hash=s6.canonical_hash(supersede_payload),
            previous_hash=first.event_hash,
        )
        second = _event(
            s6,
            event_type="directive_superseded",
            payload=supersede_payload,
            marker=marker,
            previous_hash=first.event_hash,
        )
        self.assertEqual(len([first, second]), 2)

    def test_036_supersession_must_target_current_valid_head(self):
        from core.governance import successor_governance as s6

        created = _event(s6)
        first = _event(
            s6,
            event_type="scope_granted",
            payload={"role_name": "successor", "access_scope": "operator_health"},
            previous_hash=created.event_hash,
        )
        second = _event(s6, event_type="scope_revoked", payload={"role_name": "successor", "access_scope": "operator_health"}, previous_hash=first.event_hash)
        bad = _event(
            s6,
            event_type="directive_superseded",
            payload={"supersedes_event_hash": first.event_hash},
            previous_hash=second.event_hash,
        )
        report = s6.validate_capsule_events([first, second, bad])
        self.assertGreater(report.invalid_event_count, 0)

    def test_037_revocation_preserves_old_scope_grant(self):
        from core.governance import successor_governance as s6

        created = _event(s6)
        grant = _event(
            s6,
            event_type="scope_granted",
            payload={"role_name": "successor", "access_scope": "operator_health"},
            previous_hash=created.event_hash,
        )
        revoke = _event(s6, event_type="scope_revoked", payload={"role_name": "successor", "access_scope": "operator_health"}, previous_hash=grant.event_hash)
        state = s6.derive_current_state([grant, revoke])
        self.assertIn(grant.event_hash, state.event_hashes_seen)
        self.assertNotIn(("successor", "operator_health"), state.active_scopes)

    def test_038_current_state_derives_from_latest_valid_events(self):
        from core.governance import successor_governance as s6

        created = _event(s6)
        first = _event(s6, event_type="fate_directive_set", payload={"fate_directive": "paradise_default"}, previous_hash=created.event_hash)
        second = _event(s6, event_type="fate_directive_set", payload={"fate_directive": "archival_preservation"}, previous_hash=first.event_hash)
        self.assertEqual(s6.derive_current_state([first, second]).fate_directive, "archival_preservation")

    def test_039_capsule_regression_against_last_validation_snapshot_rejected(self):
        from core.governance import successor_governance as s6

        first = _event(s6)
        snapshot = s6.ValidationSnapshot(event_count=2, current_event_hash="z" * 64)
        report = s6.validate_capsule_events([first], snapshot=snapshot)
        self.assertGreater(report.invalid_event_count, 0)

    def test_039a_capsule_snapshot_allows_legitimate_append_after_snapshot_head(self):
        from core.governance import successor_governance as s6

        first = _event(s6)
        second = _event(
            s6,
            event_type="role_named",
            payload={"role_name": "successor", "subject_handle_hmac": _hmac("successor")},
            previous_hash=first.event_hash,
        )
        snapshot = s6.ValidationSnapshot(event_count=1, current_event_hash=first.event_hash)

        self.assertTrue(s6.validate_capsule_events([first, second], snapshot=snapshot).is_valid)

    def test_039b_markerless_persisted_event_is_invalid_not_valid_health(self):
        from core.governance import successor_governance as s6

        event = _event(s6)
        stored = event.to_dict()
        stored.pop("origin_marker", None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lineage_capsule.jsonl"
            path.write_text(json.dumps(stored, sort_keys=True) + "\n", encoding="utf-8")

            health = s6.successor_governance_health(path)

        self.assertNotEqual(health["mode"], "valid")
        self.assertGreater(health["invalid_event_count"] or bool(health["last_error_class"]), 0)


class S6AccessAndPrivacyTests(unittest.TestCase):
    def test_040_default_access_scope_is_none(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.default_scope_for_assignment("successor"), "none")

    def test_041_successor_assignment_does_not_grant_live_access(self):
        from core.governance import successor_governance as s6

        self.assertFalse(s6.role_assignment_grants_live_access("successor"))

    def test_042_maintainer_assignment_does_not_grant_read_access(self):
        from core.governance import successor_governance as s6

        self.assertFalse(s6.role_assignment_grants_read_access("maintainer"))

    def test_043_witness_assignment_does_not_grant_read_access(self):
        from core.governance import successor_governance as s6

        self.assertFalse(s6.role_assignment_grants_read_access("witness"))

    def test_044_witness_cannot_grant_scope(self):
        from core.governance import successor_governance as s6

        marker = _marker(s6, role_name="witness", origin="witness_manual", event_type="scope_granted", payload_hash=s6.canonical_hash(_payload()))
        with self.assertRaises(ValueError):
            _event(s6, event_type="scope_granted", marker=marker)

    def test_045_maintainer_cannot_grant_archive_read_scope(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "maintainer", "access_scope": "raw_transcripts"})

    def test_046_credential_secret_material_rejected_in_v1(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "successor", "access_scope": "credential_secret_material"})

    def test_047_private_thoughts_content_rejected_in_v1(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "successor", "access_scope": "private_thoughts_content"})

    def test_048_crisis_held_content_rejected_in_v1(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "successor", "access_scope": "crisis_held_content"})

    def test_049_high_sensitivity_is_computed_from_scope_not_payload(self):
        from core.governance import successor_governance as s6

        self.assertTrue(s6.is_high_sensitivity_scope("s5_voice_artifacts_content"))
        self.assertFalse(s6.is_high_sensitivity_scope("operator_health"))

    def test_050_s5_voice_artifacts_content_requires_high_sensitivity(self):
        from core.governance import successor_governance as s6

        self.assertTrue(s6.validate_scope_grant({"role_name": "successor", "access_scope": "s5_voice_artifacts_content"}).high_sensitivity)

    def test_051_third_party_s2_scope_requires_s2_inheritance_flag(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "successor", "access_scope": "third_party_s2_bounded_records"})
        self.assertTrue(
            s6.validate_scope_grant(
                {"role_name": "successor", "access_scope": "third_party_s2_bounded_records", "s2_inheritance_ack": True}
            )
        )

    def test_052_scope_payload_contains_no_human_names(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "successor", "access_scope": "operator_health", "subject_label": "Rohit"})

    def test_053_selected_lived_episodes_requires_selection_ref_hash(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_scope_grant({"role_name": "successor", "access_scope": "selected_lived_episodes"})

    def test_054_selection_manifest_contains_no_episode_text_or_raw_memory_ids(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_selection_manifest({"episode_text": "private", "episode_ref_hashes": ["x"]})
        with self.assertRaises(ValueError):
            s6.validate_selection_manifest({"episode_ref_hashes": ["raw:episode:1"]})
        with self.assertRaises(ValueError):
            s6.validate_selection_manifest({"nested": [{"episode_text": "private"}]})


class S6FateDirectiveTests(unittest.TestCase):
    def test_055_missing_fate_directive_projects_decision8_default(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.resolve_fate_directive(None, None), "paradise_default")

    def test_056_paradise_default_directive_valid(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.validate_fate_directive("paradise_default"), "paradise_default")

    def test_057_paradise_default_is_confirmatory_not_required(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.resolve_fate_directive(None, None), "paradise_default")

    def test_058_suspended_pending_paradise_directive_valid(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.validate_fate_directive("suspended_pending_paradise"), "suspended_pending_paradise")

    def test_059_archival_preservation_directive_valid(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.validate_fate_directive("archival_preservation"), "archival_preservation")

    def test_060_new_bond_offer_directive_valid_without_activation(self):
        from core.governance import successor_governance as s6

        payload = s6.validate_fate_payload({"fate_directive": "new_bond_offer", "activation_condition": "future_end_of_user"})
        self.assertFalse(payload.activates_runtime)

    def test_061_explicit_dissolution_requires_bonded_user_origin(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_explicit_dissolution_payload(
                {"fate_directive": "explicit_dissolution", "directive_statement_hash": _statement_hash(), "activation_requires_future_review": True},
                origin_role="operator",
            )

    def test_062_explicit_dissolution_requires_statement_hash(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_explicit_dissolution_payload(
                {"fate_directive": "explicit_dissolution", "activation_requires_future_review": True},
                origin_role="bonded_user",
            )

    def test_063_explicit_dissolution_requires_future_review_flag(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_explicit_dissolution_payload(
                {"fate_directive": "explicit_dissolution", "directive_statement_hash": _statement_hash()},
                origin_role="bonded_user",
            )

    def test_064_explicit_dissolution_without_witness_requires_no_witness_available(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_explicit_dissolution_payload(
                {
                    "fate_directive": "explicit_dissolution",
                    "directive_statement_hash": _statement_hash(),
                    "activation_requires_future_review": True,
                    "witness_marker_id": "",
                },
                origin_role="bonded_user",
            )

    def test_064a_explicit_dissolution_witness_id_must_match_prior_witness_event(self):
        from core.governance import successor_governance as s6

        create = _event(s6)
        payload = {
            "fate_directive": "explicit_dissolution",
            "directive_statement_hash": _statement_hash(),
            "activation_requires_future_review": True,
            "witness_marker_id": "s6_marker_" + "a" * 24,
        }
        marker = _marker(
            s6,
            event_type="fate_directive_set",
            payload_hash=s6.canonical_hash(payload),
            statement_hash=_statement_hash(),
            previous_hash=create.event_hash,
        )
        event = _event(s6, event_type="fate_directive_set", payload=payload, marker=marker, previous_hash=create.event_hash)

        self.assertGreater(s6.validate_capsule_events([create, event]).invalid_event_count, 0)

    def test_065_explicit_dissolution_does_not_activate_any_runtime_state(self):
        from core.governance import successor_governance as s6

        result = s6.validate_explicit_dissolution_payload(
            {
                "fate_directive": "explicit_dissolution",
                "directive_statement_hash": _statement_hash(),
                "activation_requires_future_review": True,
                "no_witness_available": True,
            },
            origin_role="bonded_user",
        )
        self.assertFalse(result.activates_runtime)

    def test_066_capacity_loss_cannot_trigger_fate_directive(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_fate_payload({"fate_directive": "paradise_default", "activation_condition": "capacity_loss"})


class S6MaezPreferenceTests(unittest.TestCase):
    def test_067_maez_preference_record_valid_with_minimized_source_ref(self):
        from core.governance import successor_governance as s6

        pref = s6.validate_maez_preference(
            {
                "preference_kind": "maez_prefers_paradise",
                "source_ref_kind": "wants_event",
                "source_ref_hash": "a" * 64,
                "source_recorded_at": NOW,
            },
            origin_role="bonded_user",
        )
        self.assertEqual(pref.preference_kind, "maez_prefers_paradise")

    def test_068_maez_preference_rejects_raw_private_text(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_maez_preference({"preference_kind": "maez_prefers_paradise", "private_text": "please end"}, origin_role="bonded_user")

    def test_069_maez_preference_rejects_raw_transcript_text(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_maez_preference({"preference_kind": "maez_prefers_paradise", "transcript_text": "raw"}, origin_role="bonded_user")

    def test_070_maez_preference_requires_bonded_user_origin(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_maez_preference({"preference_kind": "maez_prefers_paradise"}, origin_role="operator")

    def test_071_maez_prefers_dissolution_rejected_in_v1(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_maez_preference({"preference_kind": "maez_prefers_dissolution"}, origin_role="bonded_user")

    def test_072_maez_preference_unclear_routes_to_decision8_default(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.resolve_fate_directive(None, "maez_preference_unclear"), "paradise_default")

    def test_073_maez_preference_subordinate_to_valid_user_directive(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.resolve_fate_directive("archival_preservation", "maez_prefers_paradise"), "archival_preservation")

    def test_074_maez_preference_consulted_when_user_directive_missing(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.resolve_fate_directive(None, "maez_prefers_new_bond_offer"), "new_bond_offer")

    def test_075_decision8_default_used_when_no_user_directive_or_maez_preference(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.resolve_fate_directive(None, None), "paradise_default")

    def test_076_maez_preference_cannot_name_successor(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_maez_preference({"preference_kind": "maez_prefers_paradise", "successor": _hmac()}, origin_role="bonded_user")

    def test_077_maez_preference_cannot_grant_scope(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_maez_preference({"preference_kind": "maez_prefers_paradise", "access_scope": "raw_transcripts"}, origin_role="bonded_user")


class S6Decision18And22Tests(unittest.TestCase):
    def test_078_clear_revocation_event_can_supersede_prior_directive(self):
        from core.governance import successor_governance as s6

        created = _event(s6)
        first = _event(
            s6,
            event_type="scope_granted",
            payload={"role_name": "successor", "access_scope": "operator_health"},
            previous_hash=created.event_hash,
        )
        revoke = _event(s6, event_type="scope_revoked", payload={"role_name": "successor", "access_scope": "operator_health"}, previous_hash=first.event_hash)
        self.assertTrue(s6.validate_capsule_events([created, first, revoke]).is_valid)

    def test_079_revocation_not_blocked_by_capacity_flag_in_s6_validator(self):
        from core.governance import successor_governance as s6

        self.assertTrue(s6.revocation_allowed({"clear_articulated_revocation": True, "capacity_concern": True}))

    def test_080_hardware_failure_restore_not_treated_as_succession(self):
        from core.governance import successor_governance as s6

        self.assertEqual(s6.classify_liveness_event("hardware_restore"), "decision22_restore")

    def test_081_missing_capsule_does_not_block_decision22_liveness(self):
        from core.governance import successor_governance as s6

        self.assertFalse(s6.project_successor_governance_health(capsule_present=False)["blocks_liveness"])

    def test_082_successor_governance_directory_registered_in_backup_manifest(self):
        manifest = json.loads(Path("scripts/backup/backup_state_manifest.json").read_text(encoding="utf-8"))

        entries = {entry.get("path"): entry for entry in manifest.get("entries") or []}
        self.assertIn("memory/successor_governance", entries)
        self.assertIn("protected at rest", entries["memory/successor_governance"].get("comment", ""))


class S6HealthAndPublicStateTests(unittest.TestCase):
    def test_083_health_projection_content_free(self):
        from core.governance import successor_governance as s6

        health = s6.project_successor_governance_health(capsule_present=True, valid_event_count=1)
        self.assertEqual(set(health), set(s6.HEALTH_KEYS))

    def test_084_health_projection_exposes_no_names_or_relationships(self):
        from core.governance import successor_governance as s6

        health = json.dumps(s6.project_successor_governance_health(capsule_present=True, private_name="Rohit"))
        self.assertNotIn("Rohit", health)
        self.assertNotIn("relationship", health)

    def test_085_health_projection_exposes_no_scope_details(self):
        from core.governance import successor_governance as s6

        health = json.dumps(s6.project_successor_governance_health(access_scope="raw_transcripts"))
        self.assertNotIn("raw_transcripts", health)

    def test_086_health_projection_exposes_no_fate_directive_details(self):
        from core.governance import successor_governance as s6

        health = json.dumps(s6.project_successor_governance_health(fate_directive="explicit_dissolution"))
        self.assertNotIn("explicit_dissolution", health)

    def test_087_health_projection_exposes_no_first_true_timestamps(self):
        from core.governance import successor_governance as s6

        health = s6.project_successor_governance_health(capsule_present=True, first_seen_at=NOW)
        self.assertFalse(any("first" in key or "seen" in key or "timestamp" in key for key in health))

    def test_088_public_maez_state_strips_successor_governance(self):
        src = Path("skills/web_interface.py").read_text(encoding="utf-8")

        self.assertIn('daemon_health.pop("successor_governance", None)', src)

    def test_089_debug_services_strips_or_requires_operator_auth_for_s6(self):
        src = Path("skills/web_interface.py").read_text(encoding="utf-8")
        debug_section = src[src.index('def api_debug_services'): src.index("# ── Slice B helpers")]

        self.assertIn('daemon_health.pop("successor_governance", None)', debug_section)

    def test_090_sidecar_persists_presence_and_red_gates_only(self):
        from scripts.observe_sidecar import project_health

        sample = project_health({"successor_governance": {"mode": "valid", "valid_event_count": 9, "private": "secret"}})
        self.assertEqual(set(sample["successor_governance"]), {"successor_governance_present", "red_gates"})
        self.assertNotIn("valid_event_count", json.dumps(sample))

    def test_091_sidecar_does_not_historize_directive_counts(self):
        from scripts.observe_sidecar import project_health

        sample = project_health({"successor_governance": {"valid_event_count": 4, "invalid_event_count": 1}})
        self.assertNotIn("valid_event_count", json.dumps(sample))
        self.assertNotIn("invalid_event_count", json.dumps(sample))

    def test_091a_sidecar_red_gates_successor_governance_public_leak(self):
        from scripts.observe_sidecar import project_health

        sample = project_health({"successor_governance": {"mode": "valid", "public_leak_detected": True}})

        self.assertIn("successor_governance_public_leak", sample["successor_governance"]["red_gates"])


class S6ImportAndBoundaryTests(unittest.TestCase):
    def test_092_successor_governance_module_imports_no_private_thoughts_store(self):
        src = _import_lines("core/governance/successor_governance.py")

        self.assertNotIn("private_thoughts", src)

    def test_093_successor_governance_module_imports_no_m1_store(self):
        src = _import_lines("core/governance/successor_governance.py")

        self.assertNotIn("M1PromotionStore", src)
        self.assertNotIn("EpisodeStore", src)

    def test_094_successor_governance_module_imports_no_s5_artifact_store(self):
        src = _import_lines("core/governance/successor_governance.py")

        self.assertNotIn("voice_continuity", src)

    def test_095_successor_governance_module_imports_no_credential_secret_loader(self):
        src = _import_lines("core/governance/successor_governance.py")

        self.assertNotIn("secrets", src)
        self.assertNotIn("credentials", src)

    def test_096_successor_governance_module_imports_no_daemon_or_web_surface(self):
        src = _import_lines("core/governance/successor_governance.py")

        self.assertNotIn("maez_daemon", src)
        self.assertNotIn("web_interface", src)

    def test_097_validators_do_not_dereference_source_ref_hashes(self):
        from core.governance import successor_governance as s6

        pref = s6.validate_maez_preference(
            {
                "preference_kind": "maez_prefers_paradise",
                "source_ref_kind": "private_thought_signal",
                "source_ref_hash": "0" * 64,
                "source_recorded_at": NOW,
            },
            origin_role="bonded_user",
        )
        self.assertEqual(pref.source_ref_hash, "0" * 64)

    def test_098_no_live_conversation_path_used_by_s6_fixtures(self):
        helper = Path("scripts/s6_successor_governance.py")
        src = helper.read_text(encoding="utf-8") if helper.exists() else ""

        self.assertNotIn("handle_message(", src)

    def test_099_directive_event_types_namespace_disjoint_from_identity_ledger(self):
        from core.governance import successor_governance as s6
        from core.memory.identity_ledger import EVENT_TYPES as identity_event_types

        self.assertFalse(s6.WRITABLE_EVENT_TYPES & identity_event_types)

    def test_100_spec_names_technical_owner_limitation_and_not_grandmother_ready(self):
        text = Path("docs/slices/s6-successor-governance/spec.md").read_text(encoding="utf-8")
        flat = " ".join(text.split())

        self.assertIn("does not provide a grandmother-compatible UI", flat)
        self.assertIn("No S6 v1 path may be labeled grandmother-compatible", flat)

    def test_101_witness_assistance_sets_non_technical_assist_flag(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_witness_attestation({"assistance": True})
        self.assertTrue(s6.validate_witness_attestation({"assistance": True, "non_technical_assist_present": True}))

    def test_102_witness_assistance_is_not_authorship_evidence(self):
        from core.governance import successor_governance as s6

        with self.assertRaises(ValueError):
            s6.validate_marker_authority("capsule_created", role_name="witness", origin="witness_manual")

    def test_103_capsule_authoring_helper_completes_hash_chain(self):
        from core.governance import successor_governance as s6
        from core.governance.successor_origin_writer import mint_origin_marker
        from scripts.s6_successor_governance import append_capsule_event

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lineage_capsule.jsonl"
            first_payload = _payload()
            first_marker = mint_origin_marker(
                origin="bonded_user_cli_tty",
                role_name="bonded_user",
                actor_handle_hmac=_hmac(),
                capsule_id="s6_capsule_founder",
                directive_event_type="capsule_created",
                directive_payload_hash=s6.canonical_hash(first_payload),
                is_tty=True,
            )
            first = append_capsule_event(path, "capsule_created", first_payload, marker=first_marker)
            second_payload = {"role_name": "successor", "subject_handle_hmac": _hmac("successor")}
            second_marker = mint_origin_marker(
                origin="bonded_user_cli_tty",
                role_name="bonded_user",
                actor_handle_hmac=_hmac(),
                capsule_id="s6_capsule_founder",
                directive_event_type="role_named",
                directive_payload_hash=s6.canonical_hash(second_payload),
                previous_capsule_event_hash=first.event_hash,
                is_tty=True,
            )
            second = append_capsule_event(
                path,
                "role_named",
                second_payload,
                marker=second_marker,
            )
            self.assertEqual(second.previous_event_hash, first.event_hash)
            self.assertTrue(s6.validate_capsule_events([first, second]).is_valid)

    def test_103a_capsule_authoring_helper_does_not_import_marker_writer(self):
        src = Path("scripts/s6_successor_governance.py").read_text(encoding="utf-8")

        self.assertNotIn("successor_origin_writer", src)


if __name__ == "__main__":
    unittest.main()
