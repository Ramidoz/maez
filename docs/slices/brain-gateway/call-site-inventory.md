# Brain Gateway Call-Site Inventory

Date: 2026-06-01

Source command:

```bash
rg -n "_llm_client\.chat\(|\bllm_client\.chat\(" daemon core skills --glob '*.py' --glob '!tests/**'
```

This table is the risk surface for the Brain Gateway slice. Rows marked
foreground/background are the paths that must traverse the gateway with a
non-neutral `BrainPurpose`. Neutral rows are deliberately outside this slice's
owner-reply/autonomous-cycle boundary.

| file:line | enclosing function | BrainPurpose | class | reason | covering test |
|---|---|---:|---|---|---|
| `skills/surface/maez_adapter.py:455-468` | `MaezSurfaceAdapter._handle_message_impl` | `owner_reply` | foreground | Owner Telegram tool/intent planning via `run_brain_loop` before visible reply. Purpose must cross `run_in_executor`. | `tests.test_brain_gateway_routing.RoutingTest.test_owner_executor_handoff_preserves_foreground_purpose` |
| `skills/surface/maez_adapter.py:491-502` | `MaezSurfaceAdapter._handle_message_impl` | `owner_reply` | foreground | Owner Telegram final daemon reply via `handle_message`; purpose must cross `run_in_executor`. | `tests.test_brain_gateway_routing.RoutingTest.test_owner_executor_handoff_preserves_foreground_purpose` |
| `core/brain/brain_loop.py:2157` | `run_brain_loop` | inherited, normally `owner_reply` | foreground / dual-caller-safe | Jarvis/tool planner gates an owner-visible reply. Inherits current purpose rather than hardcoding. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_owner_path` |
| `daemon/maez_daemon.py:4805` | `MaezDaemon.handle_message` | `owner_reply` | foreground | Legacy/final synthesis for owner-visible reply. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_owner_path` |
| `core/routing/focused_cognition.py:797` | `focused_synthesize` | inherited, normally `owner_recall` | foreground / dual-caller-safe | Focused recall synthesis for owner-visible dated/continuity recall. Uses injected `chat_fn`; daemon passes foreground gateway wrapper. | `tests.test_brain_gateway_routing.RoutingTest.test_focused_recall_uses_owner_recall_purpose` |
| `core/brain/conversation_controller.py:1160` | `propose_next_step_from_probe` | inherited, normally `owner_reply` | foreground / dual-caller-safe | Owner tool/recovery planning helper; can be called during owner turn, so must inherit caller purpose. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_owner_path` |
| `core/decision/decision_pipeline.py:1221` | `DecisionPipeline._s7_voice_raw_response_for_card` | inherited | neutral / foreground if owner path | S7 guarded self-mod voice consultation. Not part of recall No-Go path, but if invoked under owner turn must inherit purpose. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |
| `core/decision/decision_pipeline.py:1256` | `DecisionPipeline._s7_semantic_reader_attempt_for_voice_response` | inherited | neutral / foreground if owner path | S7 semantic reader. Same inherited-purpose rule as above. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |
| `skills/telegram_voice.py:3931` | `TelegramVoice._handle_message` | `voice_reply` | foreground | Owner private voice reply path. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_owner_path` |
| `daemon/maez_daemon.py:5595` | `MaezDaemon._handle_voice_command` | `voice_reply` | foreground | Legacy voice streaming path uses raw HTTP and `_ollama_lock`; must be wrapped/retired by gateway or documented as excluded if dead. | `tests.test_brain_gateway_routing.RoutingTest.test_no_owner_cycle_backend_bypass` |
| `skills/telegram_voice.py:3404` | `TelegramVoice._synthesize_recovery_reply` | `owner_reply` | foreground | Owner-visible Telegram recovery reply. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_owner_path` |
| `daemon/maez_daemon.py:3493` | `MaezDaemon._reason` | `daemon_cycle_generation` | background | Primary autonomous cognition cycle generation; measured source of slot contention. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `daemon/maez_daemon.py:3522` | `MaezDaemon._reason` | `daemon_cycle_retry` | background | Retry inside the primary cycle; must not fire for `BrainPreempted`. | `tests.test_brain_preempt_propagation.PreemptPropagationTest.test_daemon_cycle_preempt_does_not_retry` |
| `daemon/maez_daemon.py:7168` | `MaezDaemon._loop` retry block | `daemon_cycle_retry` | background | Corrective retry after cycle scoring/audit; holds `_ollama_lock` today. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `daemon/maez_daemon.py:2801` | `MaezDaemon._check_proactive_opinion` | `daemon_cycle_rewrite` | background | Autonomous proactive-opinion generation, not owner-triggered. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `daemon/wondering_cycle.py:144` | `_call_llm` | `daemon_cycle_generation` | background | Autonomous wondering advancement; already skip-when-lock-busy today. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `core/evolution/dream_state.py:346` | `DreamState.run_dream_cycle` | `daemon_cycle_generation` | background | Autonomous dream/reflection state. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `core/memory/continuity.py:336` | `_generate_resume_instructions` | inherited, normally background | dual-caller-safe | Restart/resume instruction generation; autonomous today, but helper must inherit caller purpose if reused. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |
| `core/cognition/audit.py:195` | `_summarize` | inherited, cycle->`daemon_cycle_audit_judge` | dual-caller-safe | Audit summarizer may run under cycle or owner surfaces; must inherit caller purpose. Broad `except Exception` must not swallow `BrainPreempted`. | `tests.test_brain_preempt_propagation.PreemptPropagationTest.test_nested_audit_preempt_surfaces` |
| `core/cognition/audit.py:344` | `_judge` | inherited, cycle->`daemon_cycle_audit_judge` | dual-caller-safe | Audit judge may run under cycle or owner surfaces; must inherit caller purpose. Broad `except Exception` must not swallow `BrainPreempted`. | `tests.test_brain_preempt_propagation.PreemptPropagationTest.test_nested_audit_preempt_surfaces` |
| `core/cognition/grounding_judge.py:670` | `judge` | inherited | dual-caller-safe | Grounding judge fallback uses primary brain when no dedicated judge is configured; foreground recall uses foreground purpose, cycle/audit uses background. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |
| `core/learning/error_classifier.py:200` | docstring example only | none | neutral | Documentation/example, not executable call site. | n/a |
| `daemon/maez_daemon.py:5776` | `_send_morning_briefing` | neutral | neutral | Owner-visible outbound briefing, but not on owner-message -> reply path and not the measured autonomous cycle contention path for recall. Future gateway expansion candidate. | `tests.test_brain_gateway_routing.RoutingTest.test_neutral_paths_do_not_preempt` |
| `daemon/maez_daemon.py:6449` | `_write_journal_entry` | neutral | neutral | Nightly journal; autonomous but not the ~60s cycle path in the No-Go. Future expansion candidate. | `tests.test_brain_gateway_routing.RoutingTest.test_neutral_paths_do_not_preempt` |
| `daemon/maez_daemon.py:6627` | `_write_developmental_heartbeat` | neutral | neutral | Daily heartbeat; autonomous but not the measured cycle path. Future expansion candidate. | `tests.test_brain_gateway_routing.RoutingTest.test_neutral_paths_do_not_preempt` |
| `skills/telegram_public.py:459` | `TelegramPublic._handle_message` | neutral | neutral | Public Telegram surface, not owner-private recall gate. | n/a |
| `skills/web_interface.py:6709` | `chat` route | neutral | neutral | Web surface local reply; outside first slice's Telegram/daemon recall gate. Future foreground candidate. | n/a |
| `skills/web_interface.py:6727` | `chat` route fallback | neutral | neutral | Web fallback reply; outside first slice. | n/a |
| `skills/self_mod_dialog.py:838` | `classify_reply` | neutral | neutral | S7/self-mod dialog path; outside recall No-Go. | n/a |
| `skills/self_mod_dialog.py:1004` | `generate_opening_turn` | neutral | neutral | S7/self-mod dialog path; outside recall No-Go. | n/a |
| `skills/self_mod_dialog.py:1127` | `generate_response_turn` | neutral | neutral | S7/self-mod dialog path; outside recall No-Go. | n/a |
| `skills/card_reply_classifier.py:559` | `classify_reply` | neutral | neutral | Approval-card reply classifier; outside first slice unless invoked under owner path with inherited purpose later. | n/a |
| `skills/github_publish.py:150` | `_generate_commit_message` | neutral | neutral | GitHub publish helper, not owner reply or cycle. | n/a |
| `core/routing/fast_backend_local.py:162` | `generate` | inherited | dual-caller-safe | Backend abstraction used by callers; should inherit purpose from gateway/client context rather than hardcode. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |

## Broad-except sweep notes

The following classified or dual-caller paths have broad `except Exception`
near the brain call and must let `BrainPreempted` outrank generic handling:

- `daemon/maez_daemon.py:3499` and `3528` (`_reason` generation + retry).
- `daemon/maez_daemon.py:7248` retry block under `_loop`.
- `core/cognition/audit.py:205` and `354`.
- `core/cognition/grounding_judge.py` broad judge-unavailable path around the fallback.
- `core/memory/continuity.py:347`.
- `core/brain/brain_loop.py:2164`.
- `core/brain/conversation_controller.py:1174`.
- `daemon/wondering_cycle.py:154`.
- `core/evolution/dream_state.py:353`.
- `skills/telegram_voice.py:3416` and `3946`.
- `skills/surface/maez_adapter.py:476` and `504` around executor-dispatched owner paths.

Every listed broad handler either catches `BrainPreempted` first or re-raises it
after Task 5.
