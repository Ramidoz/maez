# core/routing

Model selection + backend routing + redaction. Seven modules that
decide which LLM answers a given prompt and keep the policy gates
honest.

| Module | Role |
|---|---|
| [`model_config.py`](model_config.py) | Single source of truth for which local model is the primary, judge, summariser. Reads `MAEZ_PRIMARY_MODEL` / `MAEZ_JUDGE_MODEL` / friends from `.env`. |
| [`llm_client.py`](llm_client.py) | Thin HTTP client for the local inference backend. `active_backend()` returns `llamacpp` or `ollama` based on env + reachability. |
| [`fast_backend_router.py`](fast_backend_router.py) | Two-stage policy + selector. Stage 1 decides *what's allowed* (local / auto only after fast-backend cloud retirement) per trust-scope rule; stage 2 picks the actual local backend by availability. `BackendSelection.policy_denied` distinguishes policy refusal from outage. |
| [`fast_backend_local.py`](fast_backend_local.py) | Local-backend probe + generator. `is_available()` decides which backend to ping based on `active_backend()`. |
| [`fast_backend_cloud.py`](fast_backend_cloud.py) | Retired fast-lane cloud tombstone. Direct `CloudBackend.generate(...)` raises before egress; cloud is available through `claude_tier.py` / `claude_router` only. |
| [`context_compressor.py`](context_compressor.py) | Trims prompt context when the trip risks exceeding the model's window. Preserves system + recent turns. |
| [`claude_tier.py`](claude_tier.py) | Typed client for Claude (via `core.subscription_proxy`). Models the four fail modes (`Unavailable / Capped / AdapterError / BadRequest`). |

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
