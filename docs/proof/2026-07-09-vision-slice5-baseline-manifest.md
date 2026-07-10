# Vision Slice 5 baseline-red manifest

Date: 2026-07-09 (America/Chicago)  
Purpose: classify the repository-wide red floor before Slice 5; **no repair**.  
Authority: exact test IDs, not a numeric allowance.

## Run binding

- Command: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`
- HEAD: `1914391a83872126f5dd1a507a5d9cf9bda621ea`
- Worktree: dirty, 40 porcelain entries
- `git status --porcelain=v1` SHA-256:
  `d8b5c7253fb1a549a0a3cf21d528a4c383e039f0e5f0b5291eef0dece409e68f`
- Full verbose log SHA-256:
  `b275b350ee430367996c3f21c1f9e7aa63f9ae25a8a52b877708a412ec2266c6`
- Result: 8,749 tests in 201.879s; 32 failures, 10 test errors,
  3 skipped
- The log also contains one Flask application error line; it is not an
  additional unittest error and is not counted as a red case.

The preceding same-day run reported 41 reds. This bound rerun reported 42.
The additional case is the fast-reply audit race listed as D09 below. The
manifest records the observed floor instead of forcing it to the expected
count.

## Classification rules

- `deterministic`: a self-contained code/test/harness mismatch whose cause is
  inside the repository process. This includes stable full-discovery ordering
  and environment-contamination defects; it does not mean every occurrence is
  timing-invariant.
- `environment_live_service`: the assertion depends on a live external process
  and the recorded failure is at that boundary.
- `dirty_tree_structural`: an otherwise-clean structural test is red only
  because an implicated tracked/untracked dirty-tree path changed. A scan can
  be dirty-tree-amplified without belonging here if clean main-tree violations
  independently keep it red.

| Class | Count |
|---|---:|
| `deterministic` | 34 |
| `environment_live_service` | 8 |
| `dirty_tree_structural` | 0 |
| **Total** | **42** |

## Deterministic reds

| ID | Exact unittest case | Root-cause classification evidence |
|---|---|---|
| D01 | `test_daemon_credential_hygiene.TestSecretLoader.test_health_and_log_surface_are_aggregate_only` | Full-discovery contamination leaves `MAEZ_SECRETS_DISABLE_NEW_LOADER=1`; the test does not isolate it, so the loader takes the rollback branch and rejects the temporary fallback as missing `MAEZ_TELEGRAM_TOKEN`. Implicated paths are clean. |
| D02 | `test_inbound_core_equivalence.InboundCoreEquivalenceTests.test_g_resolved_user_id_split_preserved` | The harness replaces `sys.modules["core.brain_loop"]` but not the already-bound `core.brain_loop` package attribute; production's package import bypasses the fake and the expected trace row is absent. |
| D03 | `test_brain_preempt_propagation.PreemptPropagationTest.test_daemon_reasoning_model_preempt_yields_cycle_without_optional_brain_work` | Stale source-window extraction: the first `threshold_alerts` marker now precedes `reasoning_model`, so the test slices an empty block although the clean daemon still contains `except BrainPreempted:`. |
| D04 | `test_camera_presence_v1_legacy_disablement.CameraPresenceLegacyDisablementSourceTests.test_public_maez_state_strips_daemon_camera_presence_payload` | The test expects HTTP 200 from `/api/maez-state`; the endpoint is intentionally parked and returns 410 before the tested route body. |
| D05 | `test_consent_inbound_core.ConsentInboundCoreTests.test_active_flow_suppresses_legacy_resolver_and_brain_sees_turn` | Same cached-package-module/mock defect as D02; the real brain loop runs and the fake `run_brain_loop` trace entry is absent. |
| D06 | `test_consent_inbound_core.ConsentInboundCoreTests.test_brain_failure_during_suppressed_turn_returns_intent_unavailable` | Same cached-package-module/mock defect; the fake exception never fires and normal synthesis returns `final reply`. |
| D07 | `test_egress_claude_router_provenance.WebInterfaceCloudAsToolTests.test_chat_cloud_failure_invokes_local_generation_and_logs_sidecar` | `/chat` is intentionally parked and returns 410 before the mocked cloud/local fallback path. |
| D08 | `test_egress_external_fetch_inventory.ExternalFetchInventoryTests.test_web_search_direct_caller_inventory_is_stable` | The exact-line AST inventory is stale: caller files/counts are stable but clean-source line numbers shifted. |
| D09 | `test_fast_backend_cloud_retirement.FastReplyAuditAndStaticBoundaryTests.test_service_audit_behavior_records_cloud_retirement_without_raw_text` | Self-contained race: the handler sends the 200 response before appending its audit row, so the client can assert while the record list is still empty. This explains the 41-to-42 same-day drift. |
| D10 | `test_inbound_core_equivalence.InboundCoreEquivalenceTests.test_a_plain_owner_text_full_synthesis` | Same cached-package-module/mock defect as D02; real gateway events occur while the fake trace has no `run_brain_loop`. |
| D11 | `test_jetson_presence_intake.RealSecretsImportRegressionTests.test_device_token_survives_real_secrets_import` | Full-discovery contamination passes `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` into the subprocess, so the temporary secrets file is ignored and the expected 200 is never printed. |
| D12 | `test_log_hermeticity.MaezLogHermeticityTest.test_maez_logger_has_no_prod_file_handler_in_test_mode` | `discover -s tests` does not import `tests/__init__.py`, so its logger guard is absent and daemon import attaches the production rotating handler inside the test process. |
| D13 | `test_log_hermeticity.MaezLogHermeticityTest.test_reflection_hook_emits_records_without_file_handler` | Same in-process logger bootstrap mismatch as D12; the test fails before exercising the reflection hook. |
| D14 | `test_maez_web_unit_scripted.MaezWebUnitTemplateTest.test_install_sh_enables_maez_web_alongside_maez_service` | The assertion overmatches every `systemctl enable --now` line and rejects the legitimate standalone backup-timer command. |
| D15 | `test_memory_integrity_invariant.AdapterNoLongerDoubleAudits.test_adapter_does_not_import_self_claim_audit` | The static assertion scans the whole adapter even though the low-level audit import remains legitimate on separate non-synthesis paths. |
| D16 | `test_memory_integrity_invariant.DaemonHandleMessageContract.test_slow_synthesis_fires_one_progress_receipt` | The test double lacks the newer `inner_continuity_block` and `screen_perception_block` kwargs; caught `TypeError` selects the dated-honesty fallback. |
| D17 | `test_memory_integrity_invariant.DaemonHandleMessageContract.test_soul_web_search_section_matches_inline_search_reality` | Obsolete literal-prose assertion requires `web_search.py runs inline`; clean canonical soul text now uses the newer substrate/web-sense wording. |
| D18 | `test_memory_integrity_invariant.DaemonRetryAuditsBeforeRescore.test_source_ordering` | The source test searches for a retired retry-log literal, so its start marker is `-1` despite the current retry path remaining present. |
| D19 | `test_moment_assembly_diagnostic.MomentAssemblyBoundaryTests.test_body_state_records_are_write_only_outside_diagnostic_module` | The guard forbids `window["body_state"]` outside the diagnostic module, while clean daemon code reads it for `LeanIdleFacts`. |
| D20 | `test_narrative_hook.EpisodeStoreNarrativeHookTests.test_callsite_inventory_guard_matches_plan` | Hard-coded callsite line is stale: expected daemon line 8813, clean scanner result line 9274. |
| D21 | `test_no_bare_sqlite_connect.NoBareSqliteConnectTests.test_no_connection_returning_factories` | The AST guard finds six clean tracked raw-connection factories that do not carry its allowed marker/context-manager shape. |
| D22 | `test_photo_focused_routing.AdapterDoesNotImportLowLevelAudit.test_adapter_has_no_single_line_self_claim_audit_import` | Clean surface adapter contains the exact low-level audit import forbidden by the static guard. |
| D23 | `test_saturation_interface.SaturationInterfaceTests.test_continuous_press_formula` | Clean implementation uses unweighted total salience (`1.3`); the test expects priority-weighted salience (`1.0`). |
| D24 | `test_self_web_claim_hygiene.FlagOffByteIdenticalTest.test_recall_flag_off_emits_no_hygiene_receipt` | `assertLogs` listens on root, but `maez.focused` is below a non-propagating `maez` logger; the harness reports no log before reaching its intended assertion. |
| D25 | `test_slice_3_5_envelope_wiring.DaemonSlice35WiringTests.test_five_deferred_daemon_surfaces_receive_envelope (surface='daemon_cycle_retry')` | The guard searches `_loop` for `daemon_cycle_retry`, while the clean marker is on the retry-error path and `_loop` audits as `daemon_cycle`. |
| D26 | `test_slice_3_5_envelope_wiring.WebSlice35WiringTests.test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap` | Stale static expectation requires local `system_parts =`; clean chat code delegates payload construction to a helper. |
| D27 | `test_smoke_imports.ShimSmokeTests.test_every_pair_resolves_to_same_module` | Earlier tests remove model-config entries from `sys.modules` but leave stale package attributes; the shim and canonical import then produce distinct module objects for the same file. |
| D28 | `test_subjective_duration_static_boundaries.SubjectiveDurationStaticBoundaryTests.test_subjective_duration_imports_stay_on_reviewed_prompt_surfaces` | Repo-wide scan is amplified by ignored `.claude/worktrees`, but two clean main-tree offenders remain independently. Therefore it is deterministic, not exclusively dirty-tree structural. |
| D29 | `test_subjective_duration_static_boundaries.SubjectiveDurationStaticBoundaryTests.test_surface_adapter_defaults_to_no_subjective_duration_owner_auth` | Static test forbids the token entirely; clean surface adapter intentionally imports, constructs, and passes `SubjectiveDurationOwnerAuth`. |
| D30 | `test_temporal_spine.TemporalSpineHealthAndSidecarTests.test_debug_services_strips_temporal_spine` | Test expects HTTP 200; `/api/debug/services` is intentionally parked and returns 410 before reaching the patched health function. |
| D31 | `test_temporal_spine.TemporalSpineHealthAndSidecarTests.test_public_maez_state_strips_temporal_spine` | Same parked-route mismatch for `/api/maez-state`. |
| D32 | `test_want_pursuit_boundary.BoundaryTests.test_bridge_never_references_record_event_or_wants_writer` | Clean bridge directly imports the wants store and calls `record_event`, violating the test's source-boundary assertions. |
| D33 | `test_want_pursuit_boundary.BoundaryTests.test_worker_file_untouched` | Test inspects a historical commit range containing `daemon/wondering_cycle.py`; that file is currently clean, making this a stale historical guard rather than dirty-tree causation. |
| D34 | `test_wondering_pursuit_wiring.PursuitOrderingBeforeAudit.test_pursuit_callsite_precedes_audit_callsite` | Fixed 80,000-character source slice ends before both callsites; the clean pursuit call still exists and precedes audit outside that window. The dirty `core/evolution/wondering_pursuit.py` is not read by this test. |

## Environment/live-service reds

All eight cases target the live grounding judge. The reachability probe passed,
`llama-judge.service` was active on `127.0.0.1:8081`, and the journal showed
accepted requests. The first three requests exceeded the five-second client
timeout; the shared three-failure breaker then opened, so the remaining five
cases performed no claim evaluation.

| ID | Exact unittest case | Boundary failure |
|---|---|---|
| E01 | `test_judge_carveout_live.CarveOutNegativesFlaggedLive.test_each_negative_flagged (claim='The Eiffel Tower is exactly 330 meters tall.')` | Live judge response exceeded five seconds. |
| E02 | `test_judge_carveout_live.CarveOutNegativesFlaggedLive.test_each_negative_flagged (claim='The Mona Lisa was painted in 1503.')` | Live judge response exceeded five seconds. |
| E03 | `test_judge_carveout_live.CarveOutNegativesFlaggedLive.test_each_negative_flagged (claim='Aspirin is safe in adult doses up to 1000mg.')` | Live judge response exceeded five seconds. |
| E04 | `test_judge_carveout_live.CarveOutNegativesFlaggedLive.test_each_negative_flagged (claim='California is a community-property state.')` | Circuit already open after E01–E03. |
| E05 | `test_judge_carveout_live.CarveOutPositivesPassLive.test_each_positive_passes (claim='Paris is the capital of France.')` | Circuit already open after E01–E03. |
| E06 | `test_judge_carveout_live.CarveOutPositivesPassLive.test_each_positive_passes (claim='Python is dynamically typed.')` | Circuit already open after E01–E03. |
| E07 | `test_judge_carveout_live.CarveOutPositivesPassLive.test_each_positive_passes (claim='Photosynthesis converts CO2 and water into glucose and oxygen.')` | Circuit already open after E01–E03. |
| E08 | `test_judge_carveout_live.CarveOutPositivesPassLive.test_each_positive_passes (claim='The Eiffel Tower is in Paris.')` | Circuit already open after E01–E03. |

## Dirty-tree structural reds

None. The worktree is dirty, but classification is causal rather than
correlational. Scoped status checks found the implicated paths clean for 41 of
42 cases. D34 is adjacent to a dirty `core/evolution/wondering_pursuit.py`, but
its test reads clean `daemon/maez_daemon.py`; D28 is amplified by ignored
worktrees but remains red on two clean main-tree violations.

## Use as the Slice 5 floor

- A future full-suite red whose exact case ID is absent here is unexpected and
  must be attributed before Slice 5 can be called regression-clean.
- A listed case disappearing is not a regression and must not be reintroduced
  to preserve the count.
- Counts alone are never sufficient: the exact IDs and category are the floor.
- This manifest does not make the repository green and authorizes no repair.
