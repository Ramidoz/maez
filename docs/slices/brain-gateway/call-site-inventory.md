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
| `daemon/maez_daemon.py:5595` | `MaezDaemon.handle_voice_stream` | `voice_reply` | foreground | Legacy voice path is routed through `llm_client.chat` under gateway purpose; raw HTTP/`_ollama_lock` side door retired. | `tests.test_brain_gateway_routing.RoutingTest.test_voice_stream_has_no_raw_backend_side_door` |
| `skills/telegram_voice.py:3404` | `TelegramVoice._synthesize_recovery_reply` | `owner_reply` | foreground | Owner-visible Telegram recovery reply. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_owner_path` |
| `daemon/maez_daemon.py:3493` | `MaezDaemon._reason` | `daemon_cycle_generation` | background | Primary autonomous cognition cycle generation; measured source of slot contention. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `daemon/maez_daemon.py:3522` | `MaezDaemon._reason` | `daemon_cycle_retry` | background | Retry inside the primary cycle; must not fire for `BrainPreempted`. | `tests.test_brain_preempt_propagation.PreemptPropagationTest.test_daemon_cycle_preempt_does_not_retry` |
| `daemon/maez_daemon.py:7168` | `MaezDaemon._loop` retry block | `daemon_cycle_retry` | background | Corrective retry after cycle scoring/audit; enters BrainGateway directly, no legacy lock gate. | `tests.test_brain_gateway_routing.RoutingTest.test_old_dnd_and_ollama_lock_are_not_brain_lane_mechanisms` |
| `daemon/maez_daemon.py:2801` | `MaezDaemon._check_proactive_opinion` | `daemon_cycle_rewrite` | background | Autonomous proactive-opinion generation, not owner-triggered. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `daemon/wondering_cycle.py:144` | `_call_llm` | `daemon_cycle_generation` | background | Autonomous wondering advancement; enters BrainGateway as background and yields by preemption, not lock-busy skip. | `tests.test_brain_gateway_routing.RoutingTest.test_old_dnd_and_ollama_lock_are_not_brain_lane_mechanisms` |
| `core/evolution/dream_state.py:346` | `DreamState.run_dream_cycle` | `daemon_cycle_generation` | background | Autonomous dream/reflection state. | `tests.test_brain_gateway_routing.RoutingTest.test_zero_neutral_on_cycle_path` |
| `core/memory/continuity.py:336` | `_generate_resume_instructions` | inherited, normally background | dual-caller-safe | Restart/resume instruction generation; autonomous today, but helper must inherit caller purpose if reused. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |
| `core/cognition/audit.py:195` | `_summarize` | inherited, cycle->`daemon_cycle_audit_judge` | dual-caller-safe | Audit summarizer may run under cycle or owner surfaces; must inherit caller purpose. Broad `except Exception` must not swallow `BrainPreempted`. | `tests.test_brain_preempt_propagation.PreemptPropagationTest.test_nested_audit_preempt_surfaces` |
| `core/cognition/audit.py:344` | `_judge` | inherited, cycle->`daemon_cycle_audit_judge` | dual-caller-safe | Audit judge may run under cycle or owner surfaces; must inherit caller purpose. Broad `except Exception` must not swallow `BrainPreempted`. | `tests.test_brain_preempt_propagation.PreemptPropagationTest.test_nested_audit_preempt_surfaces` |
| `core/cognition/grounding_judge.py:670` | `judge` | inherited | dual-caller-safe | Grounding judge fallback uses primary brain when no dedicated judge is configured; foreground recall uses foreground purpose, cycle/audit uses background. | `tests.test_brain_gateway_routing.RoutingTest.test_dual_caller_helpers_inherit_current_purpose` |
| `core/learning/error_classifier.py:200` | docstring example only | none | neutral | Documentation/example, not executable call site. | n/a |
| `daemon/maez_daemon.py:5776` | `_send_morning_briefing` | `daemon_cycle_generation` | background | Owner-visible outbound briefing; routed as background so owner foreground can preempt it. | `tests.test_brain_gateway_routing.RoutingTest.test_old_dnd_and_ollama_lock_are_not_brain_lane_mechanisms` |
| `daemon/maez_daemon.py:6449` | `_write_journal_entry` | `daemon_cycle_generation` | background | Nightly journal; routed as background so owner foreground can preempt it. | `tests.test_brain_gateway_routing.RoutingTest.test_old_dnd_and_ollama_lock_are_not_brain_lane_mechanisms` |
| `daemon/maez_daemon.py:6627` | `_write_developmental_heartbeat` | `daemon_cycle_generation` | background | Daily heartbeat; routed as background so owner foreground can preempt it. | `tests.test_brain_gateway_routing.RoutingTest.test_old_dnd_and_ollama_lock_are_not_brain_lane_mechanisms` |
| `skills/telegram_public.py:459` | `TelegramPublic._handle_message` | `owner_reply` | foreground | Public Telegram visible reply; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
| `skills/web_interface.py:6709` | `chat` route | `owner_reply` | foreground | Web surface local reply; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
| `skills/web_interface.py:6727` | `chat` route fallback | `owner_reply` | foreground | Web fallback reply; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
| `skills/self_mod_dialog.py:838` | `classify_reply` | `owner_reply` | foreground | S7/self-mod dialog visible path; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
| `skills/self_mod_dialog.py:1004` | `generate_opening_turn` | `owner_reply` | foreground | S7/self-mod dialog visible path; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
| `skills/self_mod_dialog.py:1127` | `generate_response_turn` | `owner_reply` | foreground | S7/self-mod dialog visible path; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
| `skills/card_reply_classifier.py:559` | `classify_reply` | `owner_reply` | foreground | Approval-card reply classifier; routed through foreground owner lane. | `tests.test_brain_gateway_routing.RoutingTest.test_llm_client_buffered_chat_uses_gateway_and_current_purpose` |
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

## Recorded follow-up

The legacy `handle_voice_stream` raw HTTP path was a Brain Gateway side door, so
this slice routes it through `llm_client.chat` under `voice_reply`. That closes
the no-bypass invariant, but it also buffers the full reply before sentence/TTS
handling instead of preserving token-synchronous first audio. Treat a streaming
gateway for voice as the follow-up if owner-facing voice latency needs to regain
that shape.
