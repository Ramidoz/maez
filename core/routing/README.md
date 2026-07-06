# core/routing

Model selection, backend routing, recall routing, self-status replies,
and prompt-shape helpers. This inventory is intentionally current-state
oriented; pre-Phase-3 shim paths still exist, but new code should use the
modules in this package directly.

| Module | Role |
|---|---|
| [`attribution_render.py`](attribution_render.py) | Per-turn receipt rendering for "why this reply" / owner-facing attribution. |
| [`brain_gateway.py`](brain_gateway.py) | Gateway helpers around brain calls. |
| [`cancellable_brain_call.py`](cancellable_brain_call.py) | Interruptible/cancellable model-call wrapper. |
| [`claude_tier.py`](claude_tier.py) | Typed client for Claude (via `core.subscription_proxy`). Models the four fail modes (`Unavailable / Capped / AdapterError / BadRequest`). |
| [`context_compressor.py`](context_compressor.py) | Trims prompt context when the trip risks exceeding the model's window. Preserves system + recent turns. |
| [`evidence_state.py`](evidence_state.py) | Evidence-state helpers for search/grounding paths. |
| [`explicit_memory_question.py`](explicit_memory_question.py) | Matcher for explicit memory/recall requests. |
| [`fast_backend_cloud.py`](fast_backend_cloud.py) | Retired fast-lane cloud tombstone. Direct `CloudBackend.generate(...)` raises before egress; cloud is available through `claude_tier.py` / `claude_router` only. |
| [`fast_backend_local.py`](fast_backend_local.py) | Local-backend probe + generator. `is_available()` decides which backend to ping based on `active_backend()`. |
| [`fast_backend_router.py`](fast_backend_router.py) | Two-stage policy + selector. Stage 1 decides *what's allowed* (local / auto only after fast-backend cloud retirement) per trust-scope rule; stage 2 picks the actual local backend by availability. `BackendSelection.policy_denied` distinguishes policy refusal from outage. |
| [`focused_cognition.py`](focused_cognition.py) | Bounded working-set assembly and focused synthesis over selected evidence. |
| [`identity_reply.py`](identity_reply.py) | Narrow identity/self-status reply helpers. |
| [`llm_client.py`](llm_client.py) | Thin HTTP client for the local inference backend. `active_backend()` returns `llamacpp` or `ollama` based on env + reachability. |
| [`memory_fresh_conflict.py`](memory_fresh_conflict.py) | Detects conflicts between recalled memory and fresh evidence. |
| [`model_config.py`](model_config.py) | Single source of truth for which local model is the primary, judge, summariser. Reads `MAEZ_PRIMARY_MODEL` / `MAEZ_JUDGE_MODEL` / friends from `.env`. |
| [`observation/`](observation/) | Routing-observation learner/prior store. |
| [`observation_class.py`](observation_class.py) | Request/observation classification vocabulary. |
| [`photo_contradiction.py`](photo_contradiction.py) | Photo/vision contradiction handling helpers. |
| [`protected_refusal_followup.py`](protected_refusal_followup.py) | Follow-up handling for protected refusal paths. |
| [`recall_outcome.py`](recall_outcome.py) | Recall outcome and reply-path state. |
| [`recall_receipt.py`](recall_receipt.py) | Receipt helpers for recall decisions. |
| [`recall_self_status.py`](recall_self_status.py) | Self-status phrasing for recall stack state. |
| [`recall_shadow.py`](recall_shadow.py) | Shadow comparison/receipt machinery for recall modes. |
| [`recall_stack_config.py`](recall_stack_config.py) | Resolves legacy/triad recall stack posture. |
| [`recent_activity_status.py`](recent_activity_status.py) | Narrow status replies for recent activity / casual presence. |
| [`reply_mode.py`](reply_mode.py) | Reply-mode vocabulary. |
| [`routing_comprehension.py`](routing_comprehension.py) | Compact explanation of which route answered and why. |
| [`search_context.py`](search_context.py) | Shared search-context constants/helpers. |
| [`self_capability_question.py`](self_capability_question.py) | Narrow matcher/reply for capability questions. |
| [`self_card.py`](self_card.py) | Self-card assembly helpers. |
| [`self_card_time.py`](self_card_time.py) | Felt-time/self-card time-line helpers. |
| [`temporal_cue.py`](temporal_cue.py) | Absolute-date cue/window helpers for temporal recall precedence. |
| [`veto_ledger.py`](veto_ledger.py) | Veto/proven-wrong receipt ledger. |
| [`web_containment.py`](web_containment.py) | Web-context containment helpers. |

## Policy rules

Defined in `fast_backend_router.RULE_*`:

- `MAEZ_LOCAL_ONLY` — trust scope `rohit` by default: never cloud.
- `MAEZ_CLOUD_ALLOWED_FOR_DRAFTING` — legacy rule name retained for
  compatibility; fast-lane cloud is retired, so these scopes are
  local-first with no cloud fallback.
- `EXTERNAL_GUESTS_LOCAL_ONLY` — any non-owner scope: local only,
  fail loud if they ask for cloud.
- `DEFAULT` — local-first with no cloud fallback.

## Invariants

- **Fast lane is local-only.** `fast_backend_router` must not select
  `CloudBackend`, and `CloudBackend.generate(...)` is an always-raise
  tombstone if reached directly.
- **Cloud consults belong to the main loop.** Cloud-capable reasoning
  routes through `claude_router` / `claude_tier` as cloud-as-tool, not
  through the fast-lane router.
- **Policy-deny must be distinguishable from outage.** (10-B1 fix.)
  `BackendSelection.policy_denied=True` means "refused by rule";
  false + `backend is None` means "backend unreachable." Callers
  must handle these differently or they'll silently bypass
  policy in an outage.
- **`active_backend` resolved once per probe.** `fast_backend_local
  .is_available()` reads `active_backend()` at the top and drives
  both the llamacpp and Ollama branches from that single decision
  — not mid-function. (10-M2 fix.)

## Public surface

- `fast_backend_router.generate(prompt, policy, trust_scope, ...) -> BackendResult`
- `fast_backend_router.decide_policy(trust_scope, requested_policy) -> PolicyDecision`
- `fast_backend_router.select_backend(decision) -> BackendSelection`
- `fast_backend_local.generate(prompt, max_tokens, temperature, timeout_s)`
- `fast_backend_local.is_available() -> bool`
- `claude_tier.call(model, messages, ...) -> ClaudeResult`
- `llm_client.active_backend() -> str`
- `context_compressor.compress(messages, budget_tokens) -> list[Msg]`

## Legacy import paths

Pre-Phase-3 paths (`core.model_config`, `core.llm_client`,
`core.fast_backend_*`, `core.context_compressor`, `core.claude_tier`)
are shims.
