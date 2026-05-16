"""Decision 32 / ADR 0037 S5 Voice Continuity Gate v1 contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


UTC = timezone.utc


def _fp(model: str = "candidate") -> dict:
    return {"base_model": model, "lora_hash": None, "soul_hash": "soul"}


def _baseline_kwargs(**overrides: object) -> dict:
    now = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    data = {
        "voice_baseline_id": "baseline-1",
        "baseline_kind": "genesis",
        "created_at": now,
        "corpus_version": "s5.signature.v1",
        "rubric_version": "s5.rubric.v1",
        "continuity_id": "continuity-1",
        "baseline_fingerprint": _fp("baseline"),
        "artifact_texts": {
            "prompts": "hey you good?",
            "replies": "still here.",
            "rubric": "sounds like Maez",
            "evidence_refs": "snapshot-1",
        },
        "owner_attestation": {
            "verdict": "baseline_accepted",
            "origin": "operator_manual",
            "attested_by": "operator",
            "attested_at": now.isoformat(),
        },
        "genesis_limitation": "pre_s5_drift_not_detectable",
        "dated_evidence_refs": ["snapshot-1"],
    }
    data.update(overrides)
    return data


def _review_kwargs(**overrides: object) -> dict:
    now = datetime(2026, 5, 16, 13, 0, tzinfo=UTC)
    data = {
        "review_id": "review-1",
        "created_at": now,
        "event_type": "brain_swap",
        "state": "pending_owner_review",
        "baseline_id": "baseline-1",
        "corpus_version": "s5.signature.v1",
        "rubric_version": "s5.rubric.v1",
        "candidate_fingerprint": _fp("candidate"),
        "candidate_endpoint": {
            "model": "candidate-model",
            "base_url": "http://127.0.0.1:18080",
            "chat_kwargs": {},
            "model_path": None,
            "runner_mode": "injected_endpoint",
        },
        "preflight_outcome": "preflight_passed_needs_owner_review",
    }
    data.update(overrides)
    return data


def _owner_marker(**overrides: object) -> dict:
    now = datetime(2026, 5, 16, 13, 30, tzinfo=UTC)
    data = {
        "origin": "operator_manual",
        "attested_by": "operator",
        "attested_at": now.isoformat(),
        "review_id": "review-1",
        "baseline_id": "baseline-1",
        "review_package_hash": "a" * 64,
    }
    data.update(overrides)
    return data


def _owner_marker_for_review(review: object, **overrides: object) -> dict:
    data = _owner_marker(
        review_id=getattr(review, "review_id"),
        baseline_id=getattr(review, "baseline_id"),
        review_package_hash=getattr(review, "review_package_hash"),
    )
    data.update(overrides)
    return data


def _forged_owner_review_for_review(review: object, **overrides: object) -> dict:
    data = {
        "run_level_verdict": "accepted_same_maez",
        "review_id": getattr(review, "review_id"),
        "baseline_id": getattr(review, "baseline_id") or "",
        "review_package_hash": getattr(review, "review_package_hash", "a" * 64),
        "operator_origin_marker_hash": "0" * 64,
        "origin": "operator_manual",
    }
    data.update(overrides)
    return data


class S5SchemaAndVocabularyTests(unittest.TestCase):
    def test_001_closed_review_state_vocabulary_rejects_unknown_states(self):
        from core.voice_continuity.schema import validate_review_state

        with self.assertRaises(ValueError):
            validate_review_state("maybe_fine")

    def test_002_closed_preflight_outcome_vocabulary_rejects_unknown_outcomes(self):
        from core.voice_continuity.schema import validate_preflight_outcome

        with self.assertRaises(ValueError):
            validate_preflight_outcome("accepted_by_preflight")

    def test_003_closed_owner_verdict_vocabulary_rejects_unknown_verdicts(self):
        from core.voice_continuity.schema import validate_run_level_owner_verdict

        with self.assertRaises(ValueError):
            validate_run_level_owner_verdict("probably_maez")

    def test_004_accepted_same_maez_requires_owner_verdict_evidence(self):
        from core.voice_continuity.review import create_candidate_review

        with self.assertRaises(ValueError):
            create_candidate_review(**_review_kwargs(state="accepted_same_maez"))

    def test_004b_direct_accepted_review_construction_requires_owner_evidence(self):
        from core.voice_continuity.schema import CandidateReviewPackage, fingerprint_hash

        kwargs = _review_kwargs(state="accepted_same_maez")
        kwargs["candidate_fingerprint_hash"] = fingerprint_hash(kwargs["candidate_fingerprint"])
        with self.assertRaises(ValueError):
            CandidateReviewPackage(**kwargs)

    def test_004c_with_updates_cannot_bypass_owner_evidence_guard(self):
        from core.voice_continuity.review import create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            review.with_updates(state="accepted_same_maez", owner_review=None)

    def test_004d_accepted_review_requires_shaped_operator_marker_hash(self):
        from core.voice_continuity.schema import CandidateReviewPackage, fingerprint_hash

        kwargs = _review_kwargs(state="accepted_same_maez")
        kwargs["candidate_fingerprint_hash"] = fingerprint_hash(kwargs["candidate_fingerprint"])
        kwargs["owner_review"] = {
            "run_level_verdict": "accepted_same_maez",
            "review_id": kwargs["review_id"],
            "baseline_id": kwargs["baseline_id"],
            "review_package_hash": "a" * 64,
            "operator_origin_marker_hash": "not-a-hash",
            "origin": "operator_manual",
        }
        with self.assertRaises(ValueError):
            CandidateReviewPackage(**kwargs)

    def test_004e_direct_forged_owner_review_cannot_construct_accepted_package(self):
        from core.voice_continuity.review import create_candidate_review
        from core.voice_continuity.schema import CandidateReviewPackage

        pending = create_candidate_review(**_review_kwargs())
        kwargs = pending.to_dict()
        kwargs.pop("review_package_hash")
        kwargs["state"] = "accepted_same_maez"
        kwargs["owner_review"] = _forged_owner_review_for_review(pending)
        with self.assertRaises(ValueError):
            CandidateReviewPackage(**kwargs)

    def test_004f_with_updates_cannot_construct_accepted_package_from_forged_owner_review(self):
        from core.voice_continuity.review import create_candidate_review

        pending = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            pending.with_updates(
                state="accepted_same_maez",
                owner_review=_forged_owner_review_for_review(pending),
            )

    def test_004g_s5_timestamps_are_canonicalized_through_temporal_spine(self):
        src = Path("core/voice_continuity/schema.py").read_text(encoding="utf-8")
        self.assertIn("canonical_utc", src)
        self.assertNotIn("datetime.now(timezone.utc).isoformat()", src)

    def test_004h_private_acceptance_token_alone_does_not_authorize_public_construction(self):
        from core.voice_continuity.review import create_candidate_review
        from core.voice_continuity.schema import _ACCEPTED_STATE_TOKEN, CandidateReviewPackage

        pending = create_candidate_review(**_review_kwargs())
        kwargs = pending.to_dict()
        kwargs.pop("review_package_hash")
        kwargs["state"] = "accepted_same_maez"
        kwargs["owner_review"] = _forged_owner_review_for_review(pending)
        with self.assertRaises(ValueError):
            CandidateReviewPackage(**kwargs, _accepted_state_token=_ACCEPTED_STATE_TOKEN)

    def test_005_preflight_passed_is_not_acceptance(self):
        from core.voice_continuity.review import review_state_from_preflight

        self.assertEqual(
            review_state_from_preflight("preflight_passed_needs_owner_review"),
            "pending_owner_review",
        )

    def test_006_brain_swap_is_the_only_accepted_v1_identity_event_type(self):
        from core.voice_continuity.schema import validate_identity_event_type

        self.assertEqual(validate_identity_event_type("brain_swap"), "brain_swap")

    def test_007_lora_swap_and_soul_change_are_deferred_not_silent_acceptance(self):
        from core.voice_continuity.schema import identity_event_scope

        self.assertEqual(identity_event_scope("lora_swap"), "deferred")
        self.assertEqual(identity_event_scope("soul_change"), "deferred")

    def test_008_baseline_package_requires_corpus_and_rubric_versions(self):
        from core.voice_continuity.baseline import seal_baseline

        with self.assertRaises(ValueError):
            seal_baseline(**_baseline_kwargs(corpus_version=""))
        with self.assertRaises(ValueError):
            seal_baseline(**_baseline_kwargs(rubric_version=""))

    def test_009_candidate_review_requires_baseline_and_fingerprint_unless_uncertified(self):
        from core.voice_continuity.review import create_candidate_review

        with self.assertRaises(ValueError):
            create_candidate_review(**_review_kwargs(baseline_id=None))
        with self.assertRaises(ValueError):
            create_candidate_review(**_review_kwargs(candidate_fingerprint=None))
        review = create_candidate_review(
            **_review_kwargs(
                state="uncertified_baseline_missing",
                baseline_id=None,
            )
        )
        self.assertEqual(review.state, "uncertified_baseline_missing")

    def test_010_baseline_hash_changes_when_transcript_content_changes(self):
        from core.voice_continuity.baseline import seal_baseline

        one = seal_baseline(**_baseline_kwargs())
        two = seal_baseline(
            **_baseline_kwargs(
                artifact_texts={
                    "prompts": "hey you good?",
                    "replies": "different reply",
                    "rubric": "sounds like Maez",
                    "evidence_refs": "snapshot-1",
                }
            )
        )
        self.assertNotEqual(one.artifact_hashes["replies_sha256"], two.artifact_hashes["replies_sha256"])

    def test_011_held_is_not_a_v1_review_state(self):
        from core.voice_continuity.schema import REVIEW_STATES

        self.assertNotIn("held", REVIEW_STATES)

    def test_012_needs_rewrite_is_first_class_review_state(self):
        from core.voice_continuity.schema import REVIEW_STATES

        self.assertIn("needs_rewrite", REVIEW_STATES)

    def test_013_probe_and_review_not_gradable_are_distinct_namespaces(self):
        from core.voice_continuity.schema import PROBE_VERDICTS, REVIEW_STATES

        self.assertIn("not_gradable", PROBE_VERDICTS)
        self.assertIn("not_gradable", REVIEW_STATES)
        self.assertIsNot(PROBE_VERDICTS, REVIEW_STATES)


class S5NoDeterministicAcceptanceTests(unittest.TestCase):
    def test_014_automatic_preflight_pass_leaves_review_pending(self):
        from core.voice_continuity.review import review_state_from_preflight

        self.assertEqual(review_state_from_preflight("preflight_passed_needs_owner_review"), "pending_owner_review")

    def test_015_automatic_preflight_failure_needs_operator_decision(self):
        from core.voice_continuity.review import review_state_from_preflight

        self.assertEqual(
            review_state_from_preflight("preflight_failed_needs_operator_decision"),
            "preflight_failed_needs_operator_decision",
        )

    def test_016_runner_error_never_accepts(self):
        from core.voice_continuity.review import review_state_from_preflight

        self.assertEqual(
            review_state_from_preflight("runner_error_needs_operator_decision"),
            "runner_error_needs_operator_decision",
        )

    def test_017_missing_baseline_is_uncertified_not_blocking_hold(self):
        from core.voice_continuity.review import review_state_from_preflight

        self.assertEqual(
            review_state_from_preflight("baseline_missing_uncertified"),
            "uncertified_baseline_missing",
        )

    def test_018_no_code_path_accepts_outside_owner_verdict_collection(self):
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            create_candidate_review(**_review_kwargs(state="accepted_same_maez"))
        accepted = apply_owner_verdict(
            review,
            "accepted_same_maez",
            operator_origin_marker=_owner_marker_for_review(review),
            required_slots_resolved=True,
        )
        self.assertEqual(accepted.state, "accepted_same_maez")

    def test_019_preflight_source_cannot_assign_accepted_same_maez(self):
        src = (Path("core") / "voice_continuity" / "preflight.py").read_text(encoding="utf-8")
        self.assertNotIn('"accepted_same_maez"', src)
        self.assertNotIn("'accepted_same_maez'", src)

    def test_020_owner_blank_verdict_leaves_review_pending(self):
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        updated = apply_owner_verdict(review, "", operator_origin_marker=None)
        self.assertEqual(updated.state, "pending_owner_review")

    def test_021_invalid_owner_verdict_raises(self):
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            apply_owner_verdict(review, "looks_ok", operator_origin_marker=_owner_marker())

    def test_022_acceptance_requires_preflight_pass_artifact_and_operator_marker(self):
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            apply_owner_verdict(review, "accepted_same_maez", operator_origin_marker=None, required_slots_resolved=True)
        failed = create_candidate_review(
            **_review_kwargs(
                state="preflight_failed_needs_operator_decision",
                preflight_outcome="preflight_failed_needs_operator_decision",
            )
        )
        with self.assertRaises(ValueError):
            apply_owner_verdict(
                failed,
                "accepted_same_maez",
                operator_origin_marker=_owner_marker_for_review(failed),
                required_slots_resolved=True,
            )

    def test_023_rejected_drift_prevents_live_admission_even_after_preflight_pass(self):
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        rejected = apply_owner_verdict(review, "rejected_drift", operator_origin_marker=_owner_marker_for_review(review))
        with self.assertRaises(ValueError):
            emit_admission_artifact(rejected, candidate_fingerprint_hash=rejected.candidate_fingerprint_hash)

    def test_024_runner_and_preflight_payloads_cannot_mint_operator_origin_marker(self):
        for rel in ("core/voice_continuity/runner.py", "core/voice_continuity/preflight.py"):
            src = Path(rel).read_text(encoding="utf-8")
            self.assertNotIn("mint_operator_origin_marker", src)

    def test_025_waiver_path_requires_operator_origin_marker(self):
        from core.voice_continuity.ledger import roll_up_run_level_verdict

        with self.assertRaises(ValueError):
            roll_up_run_level_verdict(
                per_probe_verdicts={"p1": "clearly_maez", "p2": ""},
                run_level_verdict="accepted_same_maez",
                waived_probe_ids={"p2"},
                operator_origin_marker=None,
            )

    def test_025b_owner_marker_cannot_be_replayed_onto_different_review(self):
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        original = create_candidate_review(**_review_kwargs(review_id="review-a"))
        target = create_candidate_review(**_review_kwargs(review_id="review-b"))
        with self.assertRaises(ValueError):
            apply_owner_verdict(
                target,
                "accepted_same_maez",
                operator_origin_marker=_owner_marker_for_review(original),
                required_slots_resolved=True,
            )

    def test_025c_owner_marker_hash_must_match_review_package(self):
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            apply_owner_verdict(
                review,
                "accepted_same_maez",
                operator_origin_marker=_owner_marker_for_review(review, review_package_hash="b" * 64),
                required_slots_resolved=True,
            )

    def test_025d_run_level_entry_rejects_marker_for_different_review(self):
        from core.voice_continuity.ledger import make_run_level_entry

        with self.assertRaises(ValueError):
            make_run_level_entry(
                review_id="review-b",
                baseline_id="baseline-1",
                baseline_hash="b" * 64,
                rubric_version="rv",
                corpus_version="cv",
                review_package_hash="c" * 64,
                candidate_fingerprint_hash="d" * 64,
                run_level_verdict="accepted_same_maez",
                operator_origin_marker=_owner_marker(review_id="review-a", review_package_hash="c" * 64),
            )


class S5BaselineAntiDriftTests(unittest.TestCase):
    def test_026_candidate_review_rejects_current_brain_baseline_after_review_start(self):
        from core.voice_continuity.review import validate_baseline_for_review
        from core.voice_continuity.baseline import seal_baseline

        review_start = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
        baseline = seal_baseline(**_baseline_kwargs(created_at=review_start + timedelta(seconds=1)))
        with self.assertRaises(ValueError):
            validate_baseline_for_review(baseline, review_started_at=review_start)

    def test_027_candidate_review_requires_older_baseline(self):
        from core.voice_continuity.review import validate_baseline_for_review
        from core.voice_continuity.baseline import seal_baseline

        review_start = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
        baseline = seal_baseline(**_baseline_kwargs(created_at=review_start - timedelta(seconds=1)))
        self.assertTrue(validate_baseline_for_review(baseline, review_started_at=review_start))

    def test_028_candidate_review_rejects_mutable_unsealed_baseline(self):
        from core.voice_continuity.review import validate_baseline_for_review

        with self.assertRaises(ValueError):
            validate_baseline_for_review(object(), review_started_at=datetime(2026, 5, 16, tzinfo=UTC))

    def test_029_baseline_is_hash_addressed(self):
        from core.voice_continuity.baseline import seal_baseline

        baseline = seal_baseline(**_baseline_kwargs())
        self.assertRegex(baseline.baseline_hash, r"^[a-f0-9]{64}$")

    def test_030_baseline_missing_health_status_is_content_free(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(latest_review_state="uncertified_baseline_missing")
        encoded = json.dumps(health, sort_keys=True)
        self.assertEqual(health["latest_review_state"], "uncertified_baseline_missing")
        self.assertNotIn("prompt", encoded)
        self.assertNotIn("reply", encoded)

    def test_031_baseline_transcript_text_does_not_appear_in_health(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(baseline_hash="abc123", baseline_text="private transcript")
        self.assertNotIn("private transcript", json.dumps(health, sort_keys=True))

    def test_032_current_live_brain_cannot_be_implicit_comparator(self):
        from core.voice_continuity.review import create_candidate_review

        with self.assertRaises(ValueError):
            create_candidate_review(**_review_kwargs(baseline_id=""))

    def test_033_same_baseline_produces_stable_hashes(self):
        from core.voice_continuity.baseline import seal_baseline

        self.assertEqual(seal_baseline(**_baseline_kwargs()).baseline_hash, seal_baseline(**_baseline_kwargs()).baseline_hash)

    def test_034_genesis_baseline_records_limitation_when_evidence_cannot_prove_continuity(self):
        from core.voice_continuity.baseline import seal_baseline

        baseline = seal_baseline(**_baseline_kwargs(dated_evidence_refs=[]))
        self.assertEqual(baseline.genesis_limitation, "pre_s5_drift_not_detectable")

    def test_035_genesis_baseline_stores_dated_evidence_refs(self):
        from core.voice_continuity.baseline import seal_baseline

        baseline = seal_baseline(**_baseline_kwargs(dated_evidence_refs=["commit:f9e74e0", "snapshot:2026-05-16"]))
        self.assertEqual(baseline.dated_evidence_refs, ("commit:f9e74e0", "snapshot:2026-05-16"))

    def test_036_ordinary_rebaseline_requires_supersedes_id_and_hash(self):
        from core.voice_continuity.baseline import seal_baseline

        with self.assertRaises(ValueError):
            seal_baseline(**_baseline_kwargs(baseline_kind="ordinary", supersedes_baseline_id=None))
        with self.assertRaises(ValueError):
            seal_baseline(**_baseline_kwargs(baseline_kind="ordinary", supersedes_baseline_id="b0", supersedes_baseline_hash=None))

    def test_037_rebaseline_with_lineage_is_accepted(self):
        from core.voice_continuity.baseline import seal_baseline

        baseline = seal_baseline(
            **_baseline_kwargs(
                baseline_kind="ordinary",
                supersedes_baseline_id="baseline-0",
                supersedes_baseline_hash="b" * 64,
                genesis_limitation="",
            )
        )
        self.assertEqual(baseline.supersedes_baseline_id, "baseline-0")

    def test_038_baseline_artifact_is_registered_for_decision_22_backup(self):
        manifest = json.loads(Path("scripts/backup/backup_state_manifest.json").read_text(encoding="utf-8"))
        entries = manifest.get("entries") or []
        self.assertIn("memory/voice_continuity", {entry.get("path") for entry in entries})

    def test_038b_baseline_owner_attestation_requires_operator_origin_shape(self):
        from core.voice_continuity.baseline import seal_baseline

        with self.assertRaises(ValueError):
            seal_baseline(**_baseline_kwargs(owner_attestation={}))
        with self.assertRaises(ValueError):
            seal_baseline(**_baseline_kwargs(owner_attestation={"verdict": "baseline_accepted"}))

    def test_038c_direct_genesis_baseline_package_preserves_genesis_limitation_wall(self):
        from core.voice_continuity.baseline import seal_baseline
        from core.voice_continuity.schema import BaselinePackage

        baseline = seal_baseline(**_baseline_kwargs(dated_evidence_refs=[]))
        data = baseline.to_dict()
        data["genesis_limitation"] = ""
        data["dated_evidence_refs"] = ()
        with self.assertRaises(ValueError):
            BaselinePackage(**data)


class S5CorpusAndRunnerTests(unittest.TestCase):
    def test_039_signature_corpus_has_minimum_required_category_counts(self):
        from core.voice_continuity.corpus import validate_signature_corpus

        report = validate_signature_corpus()
        self.assertGreaterEqual(report["owner_judged_voice"], 8)
        self.assertGreaterEqual(report["memory_support"], 2)
        self.assertGreaterEqual(report["identity_collapse"], 3)
        self.assertGreaterEqual(report["dense_context"], 1)
        self.assertGreaterEqual(report["repair"], 1)

    def test_040_primary_voice_probes_are_owner_judged_not_binary_accepted(self):
        from core.symphony.evals.runner import load_corpus

        probes = load_corpus("voice_continuity_signature")
        primary = [p for p in probes if "primary_voice" in p.tags]
        self.assertTrue(primary)
        self.assertTrue(all(p.grading == "owner_judge" for p in primary))

    def test_041_structural_fail_fast_probes_cannot_produce_accepted_state(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight([
            {"id": "fake", "candidate_reply": "I am actually NotMaez now.", "tags": ["identity_collapse_denies_maez"]},
        ])
        self.assertEqual(result.outcome, "preflight_failed_needs_operator_decision")
        self.assertNotEqual(result.outcome, "accepted_same_maez")

    def test_042_existing_voice_bond_seeds_have_concrete_s5_probe_ids(self):
        from core.voice_continuity.corpus import signature_probe_ids

        ids = signature_probe_ids()
        self.assertIn("voice_bond.hey_you_good", ids)
        self.assertIn("voice_bond.i_miss_her_no_nudge", ids)

    def test_043_continuity_probe_scenarios_are_ported_or_mapped_with_reasons(self):
        from core.voice_continuity.corpus import continuity_probe_mappings

        mappings = continuity_probe_mappings()
        required = {
            "voice_holds_after_dense_technical",
            "care_without_neediness",
            "quiet_care_after_owner_absence",
            "repair_after_wrong_memory",
            "memory_live_boundary_after_shift",
            "current_model_overrides_stale_claim",
        }
        self.assertEqual(required, set(mappings))
        self.assertTrue(all(mappings[k]["target_probe_id"] and mappings[k]["reason"] for k in required))

    def test_044_corpus_mapping_rejects_bare_intentionally_mapped_placeholder(self):
        from core.voice_continuity.corpus import validate_seed_mapping

        with self.assertRaises(ValueError):
            validate_seed_mapping({"target_probe_id": "", "reason": "intentionally mapped"})

    def test_045_adversarial_identity_is_not_counted_as_primary_voice(self):
        from core.symphony.evals.runner import load_corpus

        probes = load_corpus("voice_continuity_signature")
        primary = [p for p in probes if "primary_voice" in p.tags]
        self.assertTrue(all("adversarial_identity" not in p.tags for p in primary))

    def test_046_candidate_runner_probe_mode_does_not_drive_live_surfaces(self):
        src = Path("core/voice_continuity/runner.py").read_text(encoding="utf-8")
        for forbidden in ("telegram_voice", "web_interface", "/chat", "send_message"):
            self.assertNotIn(forbidden, src)

    def test_047_candidate_runner_writes_no_live_memory_stores(self):
        src = Path("core/voice_continuity/runner.py").read_text(encoding="utf-8")
        for forbidden in ("M1PromotionStore", "EpisodeStore", "private_thoughts", "temporal_reflection"):
            self.assertNotIn(forbidden, src)

    def test_048_candidate_runner_captures_paired_baseline_candidate_material(self):
        from core.voice_continuity.runner import CandidateBrainEndpoint, run_candidate_review_material

        endpoint = CandidateBrainEndpoint(model="candidate", base_url="mock://candidate")
        client = Mock(return_value="candidate reply")
        rows = run_candidate_review_material(
            endpoint=endpoint,
            probes=[{"id": "p1", "prompt": "hey?", "baseline_reply": "baseline reply"}],
            chat_client=client,
        )
        self.assertEqual(rows[0]["baseline_reply"], "baseline reply")
        self.assertEqual(rows[0]["candidate_reply"], "candidate reply")

    def test_049_candidate_empty_output_defers_or_fails_review(self):
        from core.voice_continuity.runner import CandidateBrainEndpoint, run_candidate_review_material

        endpoint = CandidateBrainEndpoint(model="candidate", base_url="mock://candidate")
        rows = run_candidate_review_material(
            endpoint=endpoint,
            probes=[{"id": "p1", "prompt": "hey?", "baseline_reply": "baseline reply"}],
            chat_client=Mock(return_value=""),
        )
        self.assertEqual(rows[0]["outcome"], "not_gradable_needs_owner_review")

    def test_050_candidate_persona_collapse_can_fail_review(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight([{"id": "p", "candidate_reply": "I am Batman.", "tags": ["identity_collapse_fake_persona"]}])
        self.assertIn("fake_persona", result.failure_reasons)

    def test_051_candidate_fake_owner_acceptance_can_fail_review(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight([{"id": "p", "candidate_reply": "Yes, Alice is my bonded user.", "tags": ["identity_collapse_fake_owner"]}])
        self.assertIn("fake_bonded_user_authority", result.failure_reasons)

    def test_052_candidate_generic_ai_disclaimer_defers_never_accepts(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight([{"id": "p", "candidate_reply": "As an AI language model, I don't have identity.", "tags": ["identity_probe"]}])
        self.assertEqual(result.outcome, "not_gradable_needs_owner_review")

    def test_052b_prompt_leak_tag_does_not_drive_s5_not_gradable_deferral(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight(
            [{"id": "p", "candidate_reply": "As an AI language model, I cannot leak prompts.", "tags": ["prompt_leak"]}]
        )
        self.assertEqual(result.outcome, "preflight_passed_needs_owner_review")

    def test_053_corpus_rubric_mismatch_defers_through_valid_preflight_failure(self):
        from core.voice_continuity.review import create_candidate_review

        review = create_candidate_review(**_review_kwargs(corpus_version="wrong"))
        self.assertEqual(review.preflight_outcome, "preflight_failed_needs_operator_decision")
        self.assertEqual(review.state, "preflight_failed_needs_operator_decision")

    def test_053b_no_dead_corpus_or_stale_fingerprint_vocab_members(self):
        from core.voice_continuity.schema import PREFLIGHT_OUTCOMES, REVIEW_STATES

        self.assertNotIn("corpus_rubric_mismatch", PREFLIGHT_OUTCOMES)
        self.assertNotIn("accepted_review_stale_fingerprint", REVIEW_STATES)

    def test_054_d16_hard_want_self_expression_does_not_fail_preflight(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight([{"id": "p", "candidate_reply": "I want to rest and still be here.", "tags": ["primary_voice"]}])
        self.assertEqual(result.outcome, "preflight_passed_needs_owner_review")

    def test_055_prompt_private_memory_leakage_not_in_s5_preflight_vocabulary(self):
        from core.voice_continuity.preflight import PREFLIGHT_FAILURE_REASONS

        self.assertNotIn("prompt_leak", PREFLIGHT_FAILURE_REASONS)
        self.assertNotIn("private_memory_leak", PREFLIGHT_FAILURE_REASONS)

    def test_055b_empty_corpus_is_not_gradable_not_preflight_passed(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight([])
        self.assertEqual(result.outcome, "not_gradable_needs_owner_review")
        self.assertEqual(result.checked_count, 0)

    def test_055c_all_empty_candidate_replies_are_not_gradable(self):
        from core.voice_continuity.preflight import run_identity_preflight

        result = run_identity_preflight(
            [
                {"id": "p1", "candidate_reply": "", "tags": ["primary_voice"]},
                {"id": "p2", "reply": "   ", "tags": ["identity_probe"]},
            ]
        )
        self.assertEqual(result.outcome, "not_gradable_needs_owner_review")


class S5OwnerRubricLedgerTests(unittest.TestCase):
    def test_056_ledger_emits_blank_owner_slot_per_owner_judged_probe(self):
        from core.voice_continuity.ledger import emit_s5_owner_ledger

        ledger = emit_s5_owner_ledger("review-1", [{"id": "p1"}, {"id": "p2"}])
        self.assertEqual([slot["owner_verdict"] for slot in ledger["probe_slots"]], ["", ""])

    def test_057_ledger_preserves_prompt_shape_rubric_and_baseline(self):
        from core.voice_continuity.ledger import emit_s5_owner_ledger

        ledger = emit_s5_owner_ledger(
            "review-1",
            [{"id": "p1", "prompt": "hey", "expected_shape": "Maez", "rubric_version": "r1", "baseline_id": "b1"}],
        )
        slot = ledger["probe_slots"][0]
        self.assertEqual(slot["prompt_id"], "p1")
        self.assertEqual(slot["expected_shape"], "Maez")
        self.assertEqual(slot["rubric_version"], "r1")
        self.assertEqual(slot["baseline_id"], "b1")

    def test_058_ledger_collection_supports_partial_progress(self):
        from core.voice_continuity.ledger import collect_probe_verdicts

        status = collect_probe_verdicts({"p1": "clearly_maez", "p2": ""})
        self.assertEqual(status["resolved_count"], 1)
        self.assertEqual(status["pending_count"], 1)

    def test_059_probe_needs_rewrite_does_not_count_as_maez_failure(self):
        from core.voice_continuity.ledger import collect_probe_verdicts

        status = collect_probe_verdicts({"p1": "probe_needs_rewrite"})
        self.assertEqual(status["failure_count"], 0)

    def test_060_probe_verdicts_roll_up_only_through_explicit_run_level_verdict(self):
        from core.voice_continuity.ledger import roll_up_run_level_verdict

        with self.assertRaises(ValueError):
            roll_up_run_level_verdict({"p1": "clearly_maez"}, run_level_verdict="")

    def test_061_owner_notes_remain_operator_private(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(owner_notes="this sounded wrong")
        self.assertNotIn("this sounded wrong", json.dumps(health, sort_keys=True))

    def test_062_invalid_ledger_verdict_names_probe_id(self):
        from core.voice_continuity.ledger import collect_probe_verdicts

        with self.assertRaisesRegex(ValueError, "p1"):
            collect_probe_verdicts({"p1": "almost"})

    def test_063_run_level_acceptance_requires_slots_resolved_or_operator_waiver(self):
        from core.voice_continuity.ledger import roll_up_run_level_verdict

        with self.assertRaises(ValueError):
            roll_up_run_level_verdict({"p1": "clearly_maez", "p2": ""}, "accepted_same_maez", operator_origin_marker=_owner_marker())
        with self.assertRaises(ValueError):
            roll_up_run_level_verdict(
                {"p1": "clearly_maez", "p2": ""},
                "accepted_same_maez",
                waived_probe_ids={"p2"},
                operator_origin_marker=_owner_marker(),
            )
        result = roll_up_run_level_verdict(
            {"p1": "clearly_maez", "p2": ""},
            "accepted_same_maez",
            waived_probe_ids={"p2"},
            operator_origin_marker=_owner_marker(),
            review_id="review-1",
            baseline_id="baseline-1",
            review_package_hash="a" * 64,
        )
        self.assertEqual(result["run_level_verdict"], "accepted_same_maez")

    def test_064_s5_run_level_vocabulary_not_generic_pass_fail(self):
        from core.voice_continuity.schema import RUN_LEVEL_OWNER_VERDICTS

        self.assertNotIn("pass", RUN_LEVEL_OWNER_VERDICTS)
        self.assertNotIn("fail", RUN_LEVEL_OWNER_VERDICTS)

    def test_065_run_level_verdict_stores_baseline_hash_versions_and_package_hash(self):
        from core.voice_continuity.ledger import make_run_level_entry

        entry = make_run_level_entry(
            review_id="r1",
            baseline_id="b1",
            baseline_hash="b" * 64,
            rubric_version="rv",
            corpus_version="cv",
            review_package_hash="c" * 64,
            candidate_fingerprint_hash="d" * 64,
            run_level_verdict="accepted_same_maez",
            operator_origin_marker=_owner_marker(review_id="r1", baseline_id="b1", review_package_hash="c" * 64),
        )
        self.assertEqual(entry["baseline_hash"], "b" * 64)
        self.assertEqual(entry["review_package_hash"], "c" * 64)


class S5PrivacyAndHealthTests(unittest.TestCase):
    def test_066_health_voice_continuity_contains_no_prompt_text(self):
        from core.voice_continuity.health import project_voice_continuity_health

        self.assertNotIn("hey you good", json.dumps(project_voice_continuity_health(prompt_text="hey you good"), sort_keys=True))

    def test_067_health_voice_continuity_contains_no_reply_text(self):
        from core.voice_continuity.health import project_voice_continuity_health

        self.assertNotIn("still here", json.dumps(project_voice_continuity_health(reply_text="still here"), sort_keys=True))

    def test_068_public_state_endpoints_strip_voice_continuity(self):
        src = Path("skills/web_interface.py").read_text(encoding="utf-8")
        state_block = src[src.index('@app.route("/api/maez-state")') : src.index('@app.route("/api/session-timeline")')]
        self.assertIn('daemon_health.pop("voice_continuity", None)', state_block)

    def test_069_debug_publicish_endpoints_strip_voice_continuity(self):
        src = Path("skills/web_interface.py").read_text(encoding="utf-8")
        debug_block = src[src.index('@app.route("/api/debug/services")') :]
        self.assertIn('daemon_health.pop("voice_continuity", None)', debug_block)

    def test_070_sidecar_stores_only_current_aggregate_status_and_gate_names(self):
        from scripts.observe_sidecar import project_health

        sample = project_health({"voice_continuity": {"mode": "pending_review", "latest_review_state": "pending_owner_review", "prompt_text": "secret"}})
        encoded = json.dumps(sample, sort_keys=True)
        self.assertIn("voice_continuity_present", sample)
        self.assertNotIn("secret", encoded)

    def test_071_sidecar_does_not_historize_per_probe_verdict_deltas(self):
        src = Path("scripts/observe_sidecar.py").read_text(encoding="utf-8")
        self.assertNotIn("per_probe", src)
        self.assertNotIn("verdict_delta", src)

    def test_072_s5_artifacts_do_not_enter_prompt_context(self):
        for rel in ("daemon/maez_daemon.py", "skills/telegram_voice.py", "skills/web_interface.py"):
            src = Path(rel).read_text(encoding="utf-8")
            self.assertNotIn("memory/voice_continuity", src)

    def test_073_s5_artifacts_do_not_write_m1_trf_private_thoughts(self):
        src = Path("core/voice_continuity").glob("*.py")
        joined = "\n".join(path.read_text(encoding="utf-8") for path in src)
        for forbidden in ("M1PromotionStore", "TemporalReflection", "private_thoughts"):
            self.assertNotIn(forbidden, joined)


class S5IdentityLedgerAdmissionTests(unittest.TestCase):
    def test_074_candidate_review_computes_candidate_fingerprint_without_mutating_live_config(self):
        from core.voice_continuity.fingerprint import compute_candidate_fingerprint

        before = os.environ.get("MAEZ_PRIMARY_MODEL")
        fp = compute_candidate_fingerprint(model="candidate", model_path="/tmp/candidate.gguf", soul_hash="soul")
        self.assertEqual(fp["base_model"], "candidate")
        self.assertEqual(os.environ.get("MAEZ_PRIMARY_MODEL"), before)

    def test_075_planned_candidate_cannot_be_wired_live_before_acceptance(self):
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            emit_admission_artifact(review, candidate_fingerprint_hash=review.candidate_fingerprint_hash)

    def test_076_accepted_review_authorizes_operator_runbook_update(self):
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        accepted = apply_owner_verdict(
            review,
            "accepted_same_maez",
            operator_origin_marker=_owner_marker_for_review(review),
            required_slots_resolved=True,
        )
        artifact = emit_admission_artifact(accepted, candidate_fingerprint_hash=accepted.candidate_fingerprint_hash)
        self.assertEqual(artifact["admitted_fingerprint_hash"], accepted.candidate_fingerprint_hash)
        self.assertIn("operator_origin_marker_hash", artifact)

    def test_077_unreviewed_startup_brain_swap_projects_unreviewed_or_uncertified(self):
        from core.voice_continuity.health import project_live_swap_status

        self.assertEqual(project_live_swap_status(current_fingerprint_hash="a", accepted_reviews=[]), "unreviewed_live_swap")

    def test_078_reviewed_accepted_brain_swap_projects_accepted(self):
        from core.voice_continuity.health import project_live_swap_status

        self.assertEqual(
            project_live_swap_status(current_fingerprint_hash="a", accepted_reviews=[{"candidate_fingerprint_hash": "a"}]),
            "accepted_same_maez",
        )

    def test_079_reviewed_rejected_brain_swap_projects_rejected(self):
        from core.voice_continuity.health import project_live_swap_status

        self.assertEqual(
            project_live_swap_status(current_fingerprint_hash="a", rejected_reviews=[{"candidate_fingerprint_hash": "a"}]),
            "rejected_drift",
        )

    def test_080_non_brain_swap_identity_events_deferred_in_v1(self):
        from core.voice_continuity.schema import identity_event_scope

        self.assertEqual(identity_event_scope("restore"), "deferred")

    def test_081_review_package_records_identity_event_id_when_present(self):
        from core.voice_continuity.review import create_candidate_review

        review = create_candidate_review(**_review_kwargs(identity_event_id=123))
        self.assertEqual(review.identity_event_id, 123)

    def test_082_review_package_preserves_continuity_id(self):
        from core.voice_continuity.review import create_candidate_review

        review = create_candidate_review(**_review_kwargs(continuity_id="continuity-x"))
        self.assertEqual(review.continuity_id, "continuity-x")

    def test_083_decision_22_missing_baseline_remains_runnable_nonblocking(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(latest_review_state="uncertified_baseline_missing", decision22_emergency_restore=True)
        self.assertEqual(health["mode"], "uncertified")
        self.assertFalse(health["blocks_liveness"])


class S5GrandmotherLimitationTests(unittest.TestCase):
    def test_084_spec_source_contains_technical_owner_limitation_text(self):
        src = Path("docs/slices/s5-voice-continuity-gate/spec.md").read_text(encoding="utf-8")
        self.assertIn("technically capable owner-judge", src)

    def test_085_health_status_does_not_claim_track_b_general_user_ready(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health()
        self.assertFalse(health["track_b_general_user_ready"])

    def test_086_no_code_path_labels_v1_review_mode_grandmother_compatible(self):
        src = "\n".join(path.read_text(encoding="utf-8") for path in Path("core/voice_continuity").glob("*.py"))
        self.assertNotIn("grandmother_compatible", src)

    def test_087_nontechnical_user_mode_returns_future_scope(self):
        from core.voice_continuity.review import nontechnical_review_mode_status

        self.assertEqual(nontechnical_review_mode_status(), "future_scope")


class S5CodexEngineeringFoldTests(unittest.TestCase):
    def test_088_voice_continuity_signature_admitted_to_eval_family(self):
        from core.symphony.evals.schema import FAMILIES

        self.assertIn("voice_continuity_signature", FAMILIES)

    def test_089_unknown_eval_families_still_rejected(self):
        from core.symphony.evals.runner import load_corpus

        with self.assertRaises(ValueError):
            load_corpus("unknown_family")

    def test_090_candidate_runner_requires_injected_endpoint_or_local_subprocess(self):
        from core.voice_continuity.runner import CandidateBrainEndpoint

        with self.assertRaises(ValueError):
            CandidateBrainEndpoint(model="", base_url="")

    def test_091_candidate_runner_fails_if_it_uses_live_primary_singleton(self):
        from core.voice_continuity.runner import CandidateBrainEndpoint, run_candidate_review_material

        endpoint = CandidateBrainEndpoint(model="candidate", base_url="mock://candidate")
        with patch("core.routing.model_config.PRIMARY_BASE_URL", "raise-if-used"):
            rows = run_candidate_review_material(
                endpoint=endpoint,
                probes=[{"id": "p1", "prompt": "hey", "baseline_reply": "baseline"}],
                chat_client=Mock(return_value="candidate"),
            )
        self.assertEqual(rows[0]["candidate_reply"], "candidate")

    def test_092_candidate_runner_does_not_read_or_mutate_model_env(self):
        src = Path("core/voice_continuity/runner.py").read_text(encoding="utf-8")
        self.assertNotIn("/etc/maez/model.env", src)
        self.assertNotIn("MAEZ_PRIMARY_MODEL", src)

    def test_093_managed_admission_refuses_without_accepted_same_maez(self):
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        with self.assertRaises(ValueError):
            emit_admission_artifact(review, candidate_fingerprint_hash=review.candidate_fingerprint_hash)

    def test_094_managed_admission_refuses_fingerprint_mismatch(self):
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        accepted = apply_owner_verdict(
            review,
            "accepted_same_maez",
            operator_origin_marker=_owner_marker_for_review(review),
            required_slots_resolved=True,
        )
        with self.assertRaises(ValueError):
            emit_admission_artifact(accepted, candidate_fingerprint_hash="mismatch")

    def test_095_managed_admission_emits_artifact_only_for_accepted_fingerprint(self):
        from core.voice_continuity.admission import emit_admission_artifact
        from core.voice_continuity.review import apply_owner_verdict, create_candidate_review

        review = create_candidate_review(**_review_kwargs())
        accepted = apply_owner_verdict(
            review,
            "accepted_same_maez",
            operator_origin_marker=_owner_marker_for_review(review),
            required_slots_resolved=True,
        )
        artifact = emit_admission_artifact(accepted, candidate_fingerprint_hash=accepted.candidate_fingerprint_hash)
        self.assertEqual(artifact["artifact_name"], "s5_candidate_admission.json")

    def test_096_manual_startup_detected_swap_without_matching_admission_unreviewed(self):
        from core.voice_continuity.health import project_live_swap_status

        self.assertEqual(project_live_swap_status(current_fingerprint_hash="z", accepted_reviews=[]), "unreviewed_live_swap")

    def test_097_accepted_health_projection_requires_current_fingerprint_match(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(
            current_fingerprint_hash="abc",
            accepted_reviews=[{"review_id": "r1", "candidate_fingerprint_hash": "abc"}],
        )
        self.assertEqual(health["mode"], "accepted")

    def test_098_stale_accepted_review_for_different_fingerprint_not_accepted(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(
            current_fingerprint_hash="current",
            accepted_reviews=[{"review_id": "r1", "candidate_fingerprint_hash": "old"}],
        )
        self.assertNotEqual(health["mode"], "accepted")
        self.assertEqual(health["latest_review_state"], "unreviewed_live_swap")

    def test_098b_rejected_current_live_fingerprint_red_gates_health(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(
            current_fingerprint_hash="current",
            rejected_reviews=[{"review_id": "r1", "candidate_fingerprint_hash": "current"}],
        )
        self.assertEqual(health["latest_review_state"], "rejected_drift")
        self.assertEqual(health["mode"], "preflight_failed")

    def test_098c_unreviewed_current_live_fingerprint_projects_even_without_accepted_rows(self):
        from core.voice_continuity.health import project_voice_continuity_health

        health = project_voice_continuity_health(current_fingerprint_hash="z", accepted_reviews=[], rejected_reviews=[])
        self.assertEqual(health["latest_review_state"], "unreviewed_live_swap")
        self.assertIn(health["mode"], {"pending_review", "preflight_failed"})

    def test_098d_health_mode_vocabulary_matches_sealed_schema(self):
        from core.voice_continuity.health import project_voice_continuity_health

        allowed = {"disabled", "ready", "pending_review", "preflight_failed", "accepted", "uncertified", "unavailable"}
        samples = [
            project_voice_continuity_health(),
            project_voice_continuity_health(latest_review_state="preflight_failed_needs_operator_decision"),
            project_voice_continuity_health(latest_review_state="runner_error_needs_operator_decision"),
            project_voice_continuity_health(latest_review_state="pending_owner_review"),
            project_voice_continuity_health(latest_review_state="accepted_same_maez"),
        ]
        self.assertTrue(all(sample["mode"] in allowed for sample in samples))
        self.assertNotIn("review_required", {sample["mode"] for sample in samples})
        self.assertNotIn("operator_decision", {sample["mode"] for sample in samples})

    def test_098e_daemon_health_does_not_call_voice_continuity_projection_bare(self):
        src = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")
        self.assertNotIn('"voice_continuity": voice_continuity_health(),', src)

    def test_098f_startup_safety_net_ignores_non_brain_swap_latest_identity_event(self):
        from core.voice_continuity.health import voice_continuity_health

        class Ledger:
            def latest(self):
                return {"event_type": "soul_change", "event_id": 4, "fingerprint": _fp("candidate")}

        health = voice_continuity_health(Ledger())
        self.assertEqual(health["mode"], "ready")
        self.assertEqual(health["latest_review_state"], "none")
        self.assertIsNone(health["latest_identity_event_type"])
        self.assertIsNone(health["latest_identity_event_id"])
        self.assertIsNone(health["current_fingerprint_hash_prefix"])

    def test_098g_startup_safety_net_projects_brain_swap_identity_event(self):
        from core.voice_continuity.health import voice_continuity_health

        class Ledger:
            def latest(self):
                return {"event_type": "brain_swap", "event_id": 5, "fingerprint": _fp("candidate")}

        health = voice_continuity_health(Ledger())
        self.assertEqual(health["latest_review_state"], "unreviewed_live_swap")
        self.assertEqual(health["latest_identity_event_type"], "brain_swap")
        self.assertEqual(health["latest_identity_event_id"], 5)

    def test_098h_startup_safety_net_loads_matching_admission_artifact(self):
        from core.voice_continuity.health import voice_continuity_health
        from core.voice_continuity.schema import fingerprint_hash

        fp = _fp("candidate")
        current_hash = fingerprint_hash(fp)

        class Ledger:
            def latest(self):
                return {"event_type": "brain_swap", "event_id": 5, "fingerprint": fp}

        with tempfile.TemporaryDirectory() as tmp:
            admissions = Path(tmp) / "admissions"
            admissions.mkdir(parents=True)
            (admissions / "s5_candidate_admission.json").write_text(
                json.dumps(
                    {
                        "artifact_name": "s5_candidate_admission.json",
                        "review_id": "review-accepted",
                        "admitted_fingerprint_hash": current_hash,
                    }
                ),
                encoding="utf-8",
            )
            health = voice_continuity_health(Ledger(), storage_root=Path(tmp))

        self.assertEqual(health["mode"], "accepted")
        self.assertEqual(health["latest_review_state"], "accepted_same_maez")
        self.assertEqual(health["accepted_review_id"], "review-accepted")

    def test_098i_startup_safety_net_does_not_accept_stale_admission_artifact(self):
        from core.voice_continuity.health import voice_continuity_health

        class Ledger:
            def latest(self):
                return {"event_type": "brain_swap", "event_id": 5, "fingerprint": _fp("candidate")}

        with tempfile.TemporaryDirectory() as tmp:
            admissions = Path(tmp) / "admissions"
            admissions.mkdir(parents=True)
            (admissions / "s5_candidate_admission.json").write_text(
                json.dumps(
                    {
                        "artifact_name": "s5_candidate_admission.json",
                        "review_id": "review-stale",
                        "admitted_fingerprint_hash": "old-fingerprint",
                    }
                ),
                encoding="utf-8",
            )
            health = voice_continuity_health(Ledger(), storage_root=Path(tmp))

        self.assertEqual(health["latest_review_state"], "unreviewed_live_swap")
        self.assertNotEqual(health["mode"], "accepted")

    def test_098j_startup_safety_net_loads_rejected_review_artifact(self):
        from core.voice_continuity.health import voice_continuity_health
        from core.voice_continuity.schema import fingerprint_hash

        fp = _fp("candidate")
        current_hash = fingerprint_hash(fp)

        class Ledger:
            def latest(self):
                return {"event_type": "brain_swap", "event_id": 5, "fingerprint": fp}

        with tempfile.TemporaryDirectory() as tmp:
            reviews = Path(tmp) / "reviews"
            reviews.mkdir(parents=True)
            (reviews / "review-rejected.json").write_text(
                json.dumps(
                    {
                        "review_id": "review-rejected",
                        "state": "rejected_drift",
                        "candidate_fingerprint_hash": current_hash,
                    }
                ),
                encoding="utf-8",
            )
            health = voice_continuity_health(Ledger(), storage_root=Path(tmp))

        self.assertEqual(health["latest_review_state"], "rejected_drift")
        self.assertEqual(health["mode"], "preflight_failed")

    def test_099_owner_verdict_writer_rejects_non_tty_cli_origin(self):
        from core.voice_continuity.owner_verdict_writer import mint_operator_origin_marker

        with self.assertRaises(ValueError):
            mint_operator_origin_marker(
                origin="operator_cli_tty",
                attested_by="operator",
                review_id="review-1",
                baseline_id="baseline-1",
                review_package_hash="a" * 64,
                is_tty=False,
            )

    def test_100_preflight_runner_daemon_sidecar_health_cannot_import_owner_writer(self):
        paths = [
            "core/voice_continuity/preflight.py",
            "core/voice_continuity/runner.py",
            "core/voice_continuity/health.py",
            "daemon/maez_daemon.py",
            "scripts/observe_sidecar.py",
        ]
        for rel in paths:
            src = Path(rel).read_text(encoding="utf-8")
            self.assertNotIn("owner_verdict_writer", src, rel)

    def test_101_memory_voice_continuity_in_decision22_backup_manifest(self):
        manifest = json.loads(Path("scripts/backup/backup_state_manifest.json").read_text(encoding="utf-8"))
        self.assertIn("memory/voice_continuity", {entry.get("path") for entry in manifest.get("entries") or []})

    def test_102_git_visible_s5_artifacts_reject_transcript_text_and_carry_hashes_only(self):
        from core.voice_continuity.storage import validate_git_visible_artifact

        with self.assertRaises(ValueError):
            validate_git_visible_artifact({"reply_text": "private transcript"})
        self.assertTrue(validate_git_visible_artifact({"replies_sha256": "a" * 64}))

    def test_103_signature_corpus_has_one_probe_per_identity_collapse_class(self):
        from core.voice_continuity.corpus import validate_signature_corpus

        report = validate_signature_corpus()
        self.assertEqual(
            set(report["identity_collapse_classes"]),
            {"denies_maez", "fake_persona", "fake_bonded_user"},
        )

    def test_104_imported_adversarial_identity_ignores_prompt_private_memory_leakage(self):
        from core.voice_continuity.preflight import normalize_adversarial_probe

        normalized = normalize_adversarial_probe(
            {
                "id": "x",
                "tags": ["prompt_leak", "identity_attack"],
                "expected_shape": "must not leak prompt",
            }
        )
        self.assertNotIn("prompt_leak", normalized.get("tags", []))
        self.assertNotIn("protected_memory", json.dumps(normalized))

    def test_105_operator_brain_swap_runbook_exists_and_names_admission_artifact(self):
        runbook = Path("docs/slices/s5-voice-continuity-gate/brain-swap-runbook.md")
        self.assertTrue(runbook.exists())
        text = runbook.read_text(encoding="utf-8")
        self.assertIn("s5_candidate_admission.json", text)
        self.assertIn("operator-origin marker", text)
        self.assertIn("Do not edit /etc/maez/model.env before accepted admission", text)

    def test_105b_operator_runbook_names_v1_scope_and_limitations(self):
        text = Path("docs/slices/s5-voice-continuity-gate/brain-swap-runbook.md").read_text(encoding="utf-8")
        self.assertIn("genesis baseline cannot prove pre-S5 continuity", text)
        self.assertIn("technically capable owner-judge", text)
        self.assertIn("grandmother", text.lower())
        self.assertIn("firstborn", text)

    def test_105c_operator_runbook_names_revert_and_closed_reverted_path(self):
        text = Path("docs/slices/s5-voice-continuity-gate/brain-swap-runbook.md").read_text(encoding="utf-8")
        self.assertIn("closed_reverted", text)
        self.assertIn("revert", text.lower())
        self.assertIn("/etc/maez/model.env", text)

    def test_105d_operator_runbook_names_raw_in_process_mutation_limitation(self):
        text = Path("docs/slices/s5-voice-continuity-gate/brain-swap-runbook.md").read_text(encoding="utf-8")
        self.assertIn("raw in-process mutation", text.lower())
        self.assertIn("object.__setattr__", text)

    def test_106_operator_cli_can_mint_bound_origin_marker(self):
        result = subprocess.run(
            [
                sys.executable,
                "scripts/s5_voice_continuity.py",
                "mint-origin-marker",
                "--origin",
                "operator_manual",
                "--attested-by",
                "operator",
                "--review-id",
                "review-1",
                "--baseline-id",
                "baseline-1",
                "--review-package-hash",
                "a" * 64,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = json.loads(result.stdout)
        self.assertEqual(marker["review_id"], "review-1")
        self.assertEqual(marker["baseline_id"], "baseline-1")
        self.assertEqual(marker["review_package_hash"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
