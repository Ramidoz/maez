# Md-3 hardcoded `/home/rohit/maez` survey — 2026-05-04

Survey-only, no edits applied yet. 87 files, 224 occurrences. Awaiting your veto / re-classification before patching the SAFE group.

Classification rules (per your direction + my five additions):

- **SAFE** — production Python paths used for filesystem access, service paths, DB paths, subprocess cwd, log paths. Replace via `core.paths` helpers or env-overrides.
- **MIXED** — file has both operational paths AND prose/comments. Per-line review required; safe lines patchable, prose lines stay.
- **LEAVE** — comments, docstrings, examples, and the `core/actions/action_classifier.py` patterns + `core/safety/output_command_guard.py` examples that are *load-bearing literals* (the classifier MUST match the literal string for the safety check to fire).
- **EXEMPT** — `core/infra/paths.py` itself; the canonical fallback.
- **SCRIPT-REVIEW** — operational paths inside `scripts/*.py`. Replace only when the path is operational (cwd, output dir), not when it's printed as a usage example.
- **TEST-REVIEW** — test files using literal paths as fixtures. Many can swap to `tempfile` or `Path(__file__).resolve().parent.parent`; some assert literal strings as part of the contract under test (these become TEST-LEAVE on closer look).
- **TEST-LEAVE** — tests asserting literal paths as part of the behaviour (e.g. soul-path protection asserting that a specific path is forbidden).

Counts: **47 SAFE / 5 MIXED / 8 LEAVE / 1 EXEMPT / 3 SCRIPT-REVIEW / 20 TEST-REVIEW / 3 TEST-LEAVE**.


DETAILED TABLE:
| Verdict | File | Hits | Note |
|---|---|---|---|
| SAFE | `core/actions/destructive_snapshot.py` | 1 | 1 operational paths |
| SAFE | `core/brain/brain_loop.py` | 2 | 2 operational paths |
| SAFE | `core/cognition/cognition_quality.py` | 1 | 1 operational paths |
| SAFE | `core/cognition/quality_telemetry.py` | 1 | 1 operational paths |
| SAFE | `core/decision/approval_sessions.py` | 1 | 1 operational paths |
| SAFE | `core/evolution/dream_state.py` | 3 | 3 operational paths |
| SAFE | `core/evolution/soul_editor.py` | 2 | 2 operational paths |
| SAFE | `core/infra/capability_registry.py` | 1 | 1 operational paths |
| SAFE | `core/infra/fast_reply_audit.py` | 1 | 1 operational paths |
| SAFE | `core/infra/self_model.py` | 1 | 1 operational paths |
| SAFE | `core/learning/consequence_memory.py` | 1 | 1 operational paths |
| SAFE | `core/learning/fabrication_memory.py` | 1 | 1 operational paths |
| SAFE | `core/learning/inner_residue.py` | 1 | 1 operational paths |
| SAFE | `core/memory/baseline_observations.py` | 1 | 1 operational paths |
| SAFE | `core/memory/continuity.py` | 2 | 2 operational paths |
| SAFE | `core/memory/perception.py` | 1 | 1 operational paths |
| SAFE | `core/memory/source_awareness.py` | 1 | 1 operational paths |
| SAFE | `core/safety/premise_audit.py` | 2 | 2 operational paths |
| SAFE | `core/self_dev/__init__.py` | 1 | 1 operational paths |
| SAFE | `core/self_dev/hooks.py` | 1 | 1 operational paths |
| SAFE | `core/self_dev/persistence.py` | 1 | 1 operational paths |
| SAFE | `core/self_dev/scheduler.py` | 1 | 1 operational paths |
| SAFE | `core/self_dev/workshop.py` | 3 | 3 operational paths |
| SAFE | `core/subscription_proxy/server.py` | 1 | 1 operational paths |
| SAFE | `core/turn_traces/trace_writer.py` | 1 | 1 operational paths |
| SAFE | `daemon/maez_daemon.py` | 5 | 5 operational paths |
| SAFE | `skills/calendar_perception.py` | 2 | 2 operational paths |
| SAFE | `skills/claude_router.py` | 2 | 2 operational paths |
| SAFE | `skills/claude_watcher.py` | 3 | 3 operational paths |
| SAFE | `skills/dynamic_dns.py` | 2 | 2 operational paths |
| SAFE | `skills/evolution_engine.py` | 3 | 3 operational paths |
| SAFE | `skills/face_enrollment.py` | 2 | 2 operational paths |
| SAFE | `skills/followup_queue.py` | 1 | 1 operational paths |
| SAFE | `skills/github_publish.py` | 2 | 2 operational paths |
| SAFE | `skills/github_skill.py` | 1 | 1 operational paths |
| SAFE | `skills/iphone_ingest.py` | 1 | 1 operational paths |
| SAFE | `skills/maez_watchdog.py` | 2 | 2 operational paths |
| SAFE | `skills/presence_perception.py` | 2 | 2 operational paths |
| SAFE | `skills/reddit_skill.py` | 1 | 1 operational paths |
| SAFE | `skills/screen_perception.py` | 1 | 1 operational paths |
| SAFE | `skills/self_analysis.py` | 2 | 2 operational paths |
| SAFE | `skills/self_mod_dialog.py` | 10 | 10 operational paths |
| SAFE | `skills/surface/maez_surface_paths.py` | 1 | 1 operational paths |
| SAFE | `skills/telegram_public.py` | 2 | 2 operational paths |
| SAFE | `skills/user_accounts.py` | 3 | 3 operational paths |
| SAFE | `skills/voice_input.py` | 1 | 1 operational paths |
| SAFE | `skills/wake_word.py` | 3 | 3 operational paths |
| MIXED | `core/actions/action_engine.py` | 7 | 5 operational + 2 prose |
| MIXED | `core/decision/proposal_lookup.py` | 2 | 1 operational + 1 prose |
| MIXED | `core/infra/fast_conversation_log.py` | 2 | 1 operational + 1 prose |
| MIXED | `skills/telegram_voice.py` | 14 | 11 operational + 3 prose (large file — needs careful per-line review) |
| MIXED | `skills/web_interface.py` | 33 | 32 operational + 1 prose (HTML/landing pages — risky) |
| LEAVE | `core/actions/action_classifier.py` | 1 | 1 prose/comment occurrences |
| LEAVE | `core/safety/output_command_guard.py` | 1 | 1 prose/comment occurrences |
| LEAVE | `core/safety/owner_trust.py` | 1 | 1 prose/comment occurrences |
| LEAVE | `scripts/audit_inspect.py` | 1 | 1 prose/comment occurrences (script) |
| LEAVE | `scripts/backup/drill.py` | 1 | 1 prose/comment occurrences (script) |
| LEAVE | `scripts/fast_reply_cli.py` | 1 | 1 prose/comment occurrences (script) |
| LEAVE | `scripts/fast_reply_service.py` | 2 | 2 prose/comment occurrences (script) |
| LEAVE | `scripts/maez_cli.py` | 1 | 1 prose/comment occurrences (script) |
| EXEMPT | `core/infra/paths.py` | 3 | canonical paths.py — exempt per user direction |
| SCRIPT-REVIEW | `scripts/eval_proposals.py` | 3 | 3 operational paths (script) |
| SCRIPT-REVIEW | `scripts/presto_bridge_cli.py` | 1 | 1 operational paths (script) |
| SCRIPT-REVIEW | `scripts/validate/adversarial_probes.py` | 1 | 1 operational paths (script) |
| TEST-REVIEW | `tests/claude_code_eval_gemma.py` | 2 | 2 operational paths (test file) |
| TEST-REVIEW | `tests/claude_code_eval_ornstein.py` | 2 | 2 operational paths (test file) |
| TEST-REVIEW | `tests/claude_code_eval_ornstein_v2.py` | 2 | 2 operational paths (test file) |
| TEST-REVIEW | `tests/claude_code_eval_stock.py` | 2 | 2 operational paths (test file) |
| TEST-REVIEW | `tests/safe_action_engine.py` | 22 | 16 operational + 6 prose (test file) |
| TEST-REVIEW | `tests/test_action_engine_read_file.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_autonomous_surface_audit.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_brain_loop.py` | 2 | 2 operational paths (test file) |
| TEST-REVIEW | `tests/test_capability_acquisition_queue.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_consequence_memory.py` | 2 | 2 operational paths (test file) |
| TEST-REVIEW | `tests/test_decision_pipeline.py` | 3 | 2 operational + 1 prose (test file) |
| TEST-REVIEW | `tests/test_destructive_snapshot.py` | 3 | 3 operational paths (test file) |
| TEST-REVIEW | `tests/test_hardware_backup.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_longmemeval.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_model_config.py` | 2 | 1 operational + 1 prose (test file) |
| TEST-REVIEW | `tests/test_output_command_guard.py` | 4 | 2 operational + 2 prose (test file) |
| TEST-REVIEW | `tests/test_owner_trust.py` | 3 | 3 operational paths (test file) |
| TEST-REVIEW | `tests/test_retrieval_truth.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_soul_invariants.py` | 1 | 1 operational paths (test file) |
| TEST-REVIEW | `tests/test_trace_harness.py` | 2 | 2 operational paths (test file) |
| TEST-LEAVE | `tests/test_proposal_lookup.py` | 1 | 1 prose/comment occurrences (test file) |
| TEST-LEAVE | `tests/test_soul_and_birth_truth.py` | 1 | 1 prose/comment occurrences (test file) |
| TEST-LEAVE | `tests/test_soul_path_protection.py` | 4 | 4 prose/comment occurrences (test file) |
