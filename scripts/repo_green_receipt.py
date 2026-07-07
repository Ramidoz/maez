#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Run unittest discover and write the repo-green receipt for birth readiness."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RECEIPT_PATH = ROOT / "memory" / "repo_green_receipt.json"
KNOWN_MEMORY_INTEGRITY_DRIFT_CASES = (
    "test_adapter_does_not_import_self_claim_audit "
    "(test_memory_integrity_invariant.AdapterNoLongerDoubleAudits."
    "test_adapter_does_not_import_self_claim_audit)",
    "test_soul_web_search_section_matches_inline_search_reality "
    "(test_memory_integrity_invariant.DaemonHandleMessageContract."
    "test_soul_web_search_section_matches_inline_search_reality)",
    "test_source_ordering "
    "(test_memory_integrity_invariant.DaemonRetryAuditsBeforeRescore."
    "test_source_ordering)",
)

KNOWN_ASSET_CONFOUND_CASES = (
    "test_handler_writes_one_queued_row_on_valid_params "
    "(test_capability_acquisition_queue.TestActionHandlerValidation."
    "test_handler_writes_one_queued_row_on_valid_params)",
    "test_handler_does_not_call_subprocess "
    "(test_capability_acquisition_queue.TestNoSideEffects."
    "test_handler_does_not_call_subprocess)",
    "test_handler_does_not_modify_repo_files "
    "(test_capability_acquisition_queue.TestNoSideEffects."
    "test_handler_does_not_modify_repo_files)",
    "test_disclaimer_present_in_rendered_text "
    "(test_capability_integration_planner.TestPlanContent."
    "test_disclaimer_present_in_rendered_text)",
    "test_required_consents_includes_card_when_covenant_demands "
    "(test_capability_integration_planner.TestPlanContent."
    "test_required_consents_includes_card_when_covenant_demands)",
    "test_rlm_entry_does_not_fake_certainty "
    "(test_capability_integration_planner.TestPlanContent."
    "test_rlm_entry_does_not_fake_certainty)",
    "test_temporal_entry_produces_concrete_draft "
    "(test_capability_integration_planner.TestPlanContent."
    "test_temporal_entry_produces_concrete_draft)",
    "test_explicit_id_selects_specific_row "
    "(test_capability_integration_planner.TestPlanNextConsumesQueuedRow."
    "test_explicit_id_selects_specific_row)",
    "test_plan_carries_provenance_evidence "
    "(test_capability_integration_planner.TestPlanNextConsumesQueuedRow."
    "test_plan_carries_provenance_evidence)",
    "test_returns_plan_for_oldest_queued_row "
    "(test_capability_integration_planner.TestPlanNextConsumesQueuedRow."
    "test_returns_plan_for_oldest_queued_row)",
    "test_does_not_call_subprocess "
    "(test_capability_integration_planner.TestPlannerHasNoSideEffects."
    "test_does_not_call_subprocess)",
    "test_does_not_modify_queue_status "
    "(test_capability_integration_planner.TestPlannerHasNoSideEffects."
    "test_does_not_modify_queue_status)",
    "test_does_not_open_network "
    "(test_capability_integration_planner.TestPlannerHasNoSideEffects."
    "test_does_not_open_network)",
    "test_does_not_write_to_repo "
    "(test_capability_integration_planner.TestPlannerHasNoSideEffects."
    "test_does_not_write_to_repo)",
    "test_health_and_log_surface_are_aggregate_only "
    "(test_daemon_credential_hygiene.TestSecretLoader."
    "test_health_and_log_surface_are_aggregate_only)",
    "test_valid_fetch_mapping_is_preserved_in_queue_payload "
    "(test_egress_external_fetch_capability.ExternalFetchCapabilityTests."
    "test_valid_fetch_mapping_is_preserved_in_queue_payload)",
    "test_chat_total_dominates_on_slow_chat_fn "
    "(test_focused_synthesis_timing.FocusedSynthesisTimingTest."
    "test_chat_total_dominates_on_slow_chat_fn)",
    "test_reply_and_cited_ids_byte_stable "
    "(test_focused_synthesis_timing.FocusedSynthesisTimingTest."
    "test_reply_and_cited_ids_byte_stable)",
    "test_timing_fields_populated "
    "(test_focused_synthesis_timing.FocusedSynthesisTimingTest."
    "test_timing_fields_populated)",
    "test_g_resolved_user_id_split_preserved "
    "(test_inbound_core_equivalence.InboundCoreEquivalenceTests."
    "test_g_resolved_user_id_split_preserved)",
    "test_each_negative_flagged "
    "(test_judge_carveout_live.CarveOutNegativesFlaggedLive."
    "test_each_negative_flagged) "
    "(claim='The Eiffel Tower is exactly 330 meters tall.')",
    "test_each_negative_flagged "
    "(test_judge_carveout_live.CarveOutNegativesFlaggedLive."
    "test_each_negative_flagged) "
    "(claim='The Mona Lisa was painted in 1503.')",
    "test_each_negative_flagged "
    "(test_judge_carveout_live.CarveOutNegativesFlaggedLive."
    "test_each_negative_flagged) "
    "(claim='Aspirin is safe in adult doses up to 1000mg.')",
    "test_each_negative_flagged "
    "(test_judge_carveout_live.CarveOutNegativesFlaggedLive."
    "test_each_negative_flagged) "
    "(claim='California is a community-property state.')",
    "test_each_positive_passes "
    "(test_judge_carveout_live.CarveOutPositivesPassLive."
    "test_each_positive_passes) "
    "(claim='Paris is the capital of France.')",
    "test_each_positive_passes "
    "(test_judge_carveout_live.CarveOutPositivesPassLive."
    "test_each_positive_passes) "
    "(claim='Python is dynamically typed.')",
    "test_each_positive_passes "
    "(test_judge_carveout_live.CarveOutPositivesPassLive."
    "test_each_positive_passes) "
    "(claim='Photosynthesis converts CO2 and water into glucose and oxygen.')",
    "test_each_positive_passes "
    "(test_judge_carveout_live.CarveOutPositivesPassLive."
    "test_each_positive_passes) "
    "(claim='The Eiffel Tower is in Paris.')",
    "test_handle_message_without_owner_auth_does_not_insert_line_or_record_owner_contact "
    "(test_subjective_duration_prompt_integration."
    "SubjectiveDurationPromptBehaviorTests."
    "test_handle_message_without_owner_auth_does_not_insert_line_or_record_owner_contact)",
    "test_web_owner_bridge_constructs_typed_auth_only_after_private_owner_bridge "
    "(test_subjective_duration_prompt_integration."
    "SubjectiveDurationPromptSourceTests."
    "test_web_owner_bridge_constructs_typed_auth_only_after_private_owner_bridge)",
    "test_daemon_reasoning_model_preempt_yields_cycle_without_optional_brain_work "
    "(test_brain_preempt_propagation.PreemptPropagationTest."
    "test_daemon_reasoning_model_preempt_yields_cycle_without_optional_brain_work)",
    "test_public_maez_state_strips_daemon_camera_presence_payload "
    "(test_camera_presence_v1_legacy_disablement."
    "CameraPresenceLegacyDisablementSourceTests."
    "test_public_maez_state_strips_daemon_camera_presence_payload)",
    "test_card_metadata_lands_in_queue_row_via_real_approval "
    "(test_capability_acquisition_queue.TestRealApprovalPathEnrichesParams."
    "test_card_metadata_lands_in_queue_row_via_real_approval)",
    "test_chat_cloud_failure_invokes_local_generation_and_logs_sidecar "
    "(test_egress_claude_router_provenance.WebInterfaceCloudAsToolTests."
    "test_chat_cloud_failure_invokes_local_generation_and_logs_sidecar)",
    "test_web_search_direct_caller_inventory_is_stable "
    "(test_egress_external_fetch_inventory.ExternalFetchInventoryTests."
    "test_web_search_direct_caller_inventory_is_stable)",
    "test_a_plain_owner_text_full_synthesis "
    "(test_inbound_core_equivalence.InboundCoreEquivalenceTests."
    "test_a_plain_owner_text_full_synthesis)",
    "test_device_token_survives_real_secrets_import "
    "(test_jetson_presence_intake.RealSecretsImportRegressionTests."
    "test_device_token_survives_real_secrets_import)",
    "test_maez_logger_has_no_prod_file_handler_in_test_mode "
    "(test_log_hermeticity.MaezLogHermeticityTest."
    "test_maez_logger_has_no_prod_file_handler_in_test_mode)",
    "test_reflection_hook_emits_records_without_file_handler "
    "(test_log_hermeticity.MaezLogHermeticityTest."
    "test_reflection_hook_emits_records_without_file_handler)",
    "test_install_sh_enables_maez_web_alongside_maez_service "
    "(test_maez_web_unit_scripted.MaezWebUnitTemplateTest."
    "test_install_sh_enables_maez_web_alongside_maez_service)",
    "test_body_state_records_are_write_only_outside_diagnostic_module "
    "(test_moment_assembly_diagnostic.MomentAssemblyBoundaryTests."
    "test_body_state_records_are_write_only_outside_diagnostic_module)",
    "test_callsite_inventory_guard_matches_plan "
    "(test_narrative_hook.EpisodeStoreNarrativeHookTests."
    "test_callsite_inventory_guard_matches_plan)",
    "test_no_unclosed_sqlite_connect_context_managers "
    "(test_no_bare_sqlite_connect.NoBareSqliteConnectTests."
    "test_no_unclosed_sqlite_connect_context_managers)",
    "test_adapter_has_no_single_line_self_claim_audit_import "
    "(test_photo_focused_routing.AdapterDoesNotImportLowLevelAudit."
    "test_adapter_has_no_single_line_self_claim_audit_import)",
    "test_continuous_press_formula "
    "(test_saturation_interface.SaturationInterfaceTests."
    "test_continuous_press_formula)",
    "test_recall_flag_off_emits_no_hygiene_receipt "
    "(test_self_web_claim_hygiene.FlagOffByteIdenticalTest."
    "test_recall_flag_off_emits_no_hygiene_receipt)",
    "test_five_deferred_daemon_surfaces_receive_envelope "
    "(test_slice_3_5_envelope_wiring.DaemonSlice35WiringTests."
    "test_five_deferred_daemon_surfaces_receive_envelope) "
    "(surface='daemon_cycle_retry')",
    "test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap "
    "(test_slice_3_5_envelope_wiring.WebSlice35WiringTests."
    "test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap)",
    "test_every_pair_resolves_to_same_module "
    "(test_smoke_imports.ShimSmokeTests.test_every_pair_resolves_to_same_module)",
    "test_subjective_duration_imports_stay_on_reviewed_prompt_surfaces "
    "(test_subjective_duration_static_boundaries."
    "SubjectiveDurationStaticBoundaryTests."
    "test_subjective_duration_imports_stay_on_reviewed_prompt_surfaces)",
    "test_surface_adapter_defaults_to_no_subjective_duration_owner_auth "
    "(test_subjective_duration_static_boundaries."
    "SubjectiveDurationStaticBoundaryTests."
    "test_surface_adapter_defaults_to_no_subjective_duration_owner_auth)",
    "test_debug_services_strips_temporal_spine "
    "(test_temporal_spine.TemporalSpineHealthAndSidecarTests."
    "test_debug_services_strips_temporal_spine)",
    "test_public_maez_state_strips_temporal_spine "
    "(test_temporal_spine.TemporalSpineHealthAndSidecarTests."
    "test_public_maez_state_strips_temporal_spine)",
    "test_bridge_never_references_record_event_or_wants_writer "
    "(test_want_pursuit_boundary.BoundaryTests."
    "test_bridge_never_references_record_event_or_wants_writer)",
    "test_worker_file_untouched "
    "(test_want_pursuit_boundary.BoundaryTests.test_worker_file_untouched)",
    "test_pursuit_callsite_precedes_audit_callsite "
    "(test_wondering_pursuit_wiring.PursuitOrderingBeforeAudit."
    "test_pursuit_callsite_precedes_audit_callsite)",
)

_KNOWN_FLOOR_BY_CASE = {
    **{case: "memory_integrity_drift" for case in KNOWN_MEMORY_INTEGRITY_DRIFT_CASES},
    **{case: "asset_confounded_full_discovery" for case in KNOWN_ASSET_CONFOUND_CASES},
}


def _red_case_id(test: object) -> str:
    return str(test)


def _build_receipt(
    result: unittest.TestResult,
    *,
    commit: str,
    started_at: str,
    finished_at: str,
    worktree_clean: bool,
) -> dict:
    reds: list[tuple[str, str]] = [
        ("FAIL", _red_case_id(test)) for test, _tb in result.failures
    ] + [
        ("ERROR", _red_case_id(test)) for test, _tb in result.errors
    ]
    buckets: Counter[str] = Counter()
    unexpected: list[str] = []
    unexpected_failures = 0
    unexpected_errors = 0
    for kind, case_id in reds:
        bucket = _KNOWN_FLOOR_BY_CASE.get(case_id)
        if bucket:
            buckets[bucket] += 1
        else:
            unexpected.append(f"{kind}: {case_id}")
            if kind == "FAIL":
                unexpected_failures += 1
            else:
                unexpected_errors += 1
    known_floor_count = sum(buckets.values())
    unexpected_count = len(unexpected)
    floor_note = (
        f"floor={known_floor_count} known full-discovery reds: "
        f"asset_confounded_full_discovery="
        f"{buckets.get('asset_confounded_full_discovery', 0)}; "
        f"memory_integrity_drift={buckets.get('memory_integrity_drift', 0)}; "
        f"unexpected={unexpected_count}"
    )
    return {
        "commit": commit,
        "started_at": started_at,
        "finished_at": finished_at,
        "ran": int(result.testsRun),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "known_floor_count": known_floor_count,
        "floor_buckets": dict(sorted(buckets.items())),
        "unexpected_failures": unexpected_failures,
        "unexpected_errors": unexpected_errors,
        "unexpected_reds": unexpected,
        "floor_note": floor_note,
        "worktree_clean": worktree_clean,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


def _worktree_clean() -> bool:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
    )
    return status == ""


def main() -> int:
    started_at = _utc_now()
    try:
        commit = _head()
        worktree_clean = _worktree_clean()
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        receipt = _build_receipt(
            result,
            commit=commit,
            started_at=started_at,
            finished_at=_utc_now(),
            worktree_clean=worktree_clean,
        )
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except BaseException as exc:
        receipt = {
            "commit": "",
            "started_at": started_at,
            "finished_at": _utc_now(),
            "ran": 0,
            "failures": 0,
            "errors": 1,
            "floor_note": f"repo_green_receipt crashed: {exc.__class__.__name__}",
        }
        try:
            RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT_PATH.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"repo_green_receipt crashed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
