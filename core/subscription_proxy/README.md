# Maez Subscription Proxy

Localhost OpenAI-compatible HTTP endpoint that routes `/v1/chat/completions`
requests to pluggable backend adapters — subscription CLIs (Claude Max,
Google One AI Premium) and API-key services (OpenRouter, OpenAI, xAI,
Ollama Cloud).

**Listens on `127.0.0.1:11438` only.** Any tool speaking OpenAI-compat
(Maez self-dev, Qwen Code, Cline, Aider, Continue, curl) can point at
it and get routed to the right backend automatically.

## Why this exists

Rohit holds one Claude Max 5× subscription and will add more
subscriptions over time. The subscription is consumed through the
`claude` CLI's auth; tools that want to reach it via an HTTP API can't
go through `api.anthropic.com` (that's metered, not subscription). The
proxy wraps the CLI in an OpenAI-compatible shell so every tool gets
subscription-backed Claude without re-implementing auth.

The same proxy also wraps plain HTTP-API providers — OpenRouter is the
big one (one key, 100+ models including Grok and the OpenAI catalog).
Adding more is a single file.

## Architecture

```
                   ┌────────────────────────────────────┐
Tool (Maez,        │ core/subscription_proxy/server.py  │
Qwen Code, ...) ──▶│  ┌────────────┐  ┌──────────────┐ │
                   │  │  routing   │  │ budget + log │ │
                   │  └─────┬──────┘  └──────────────┘ │
                   └────────┼────────────────────────────┘
                            │
              ┌─────────────┼─────────────────────┐
              │             │                     │
              ▼             ▼                     ▼
       ClaudeCliAdapter  OpenRouterAdapter  (future adapters)
       (subprocess)      (HTTP forward)
```

Two adapter families:

| Family | Base class | Auth | Examples |
|---|---|---|---|
| CLI subprocess | `Adapter` | OAuth via CLI | `ClaudeCliAdapter`, `GeminiCliAdapter` |
| HTTP forward | `HttpForwardAdapter` | Bearer API key | `OpenRouterAdapter`, `OpenAiApiAdapter`, `XaiApiAdapter`, `OllamaCloudAdapter` |

## Model routing

The server picks an adapter based on the `model` string in the request.
No overlap — each string claims exactly one adapter:

| Pattern | Adapter | Example |
|---|---|---|
| `<provider>/<model>` | OpenRouter | `openai/gpt-4o` |
| `<name>:<size>` | Ollama Cloud | `qwen3:32b` |
| `grok-*` | xAI direct | `grok-4` |
| `gemini-*` | Gemini CLI (subscription) | `gemini-2.5-pro` |
| `gpt-*`, `o1-*`, `o3-*`, `chatgpt-*` | OpenAI direct | `gpt-4o-mini` |
| `sonnet`, `opus`, `haiku`, `claude-*` | Claude CLI (subscription) | `sonnet` |
| empty / unknown | Claude CLI (fallback) | — |

## Configuration

All via environment variables. Set in `/home/rohit/maez/config/.env` so
the systemd service picks them up.

| Variable | Purpose | Default |
|---|---|---|
| `MAEZ_SUBSCRIPTION_PROXY_PORT` | bind port | `11438` |
| `MAEZ_SUBSCRIPTION_PROXY_DB` | budget + trajectory log | `memory/subscription_proxy.db` |
| `MAEZ_CLAUDE_BIN` | path to `claude` | `/home/rohit/.local/bin/claude` |
| `MAEZ_GEMINI_BIN` | path to `gemini` | `gemini` (from PATH) |
| `OPENROUTER_API_KEY` | OpenRouter key | — (required to use) |
| `OPENAI_API_KEY` | OpenAI direct key | — (required to use) |
| `XAI_API_KEY` | xAI direct key | — (required to use) |
| `OLLAMA_API_KEY` | Ollama Cloud key | — (required to use) |
| `MAEZ_<ADAPTER>_HOURLY_CAP` | per-adapter hourly cap | see `DEFAULT_CAPS` |
| `MAEZ_<ADAPTER>_DAILY_CAP` | per-adapter daily cap | see `DEFAULT_CAPS` |

Subscription adapters default to tight caps (10/hr, 30/day) because
their quota is shared with Rohit's interactive use. API adapters
default to looser caps (30/hr, 100/day) because the backpressure is
spend, not calls.

## Endpoints

### `POST /v1/chat/completions`
OpenAI-compatible. `stream` not yet supported — set `stream: false`
or omit.

Optional header `X-Maez-Caller: <name>` labels the trajectory log so
you can see which tool spent which calls.

### `GET /health`
Returns the adapter list with per-adapter configuration status.

### `GET /budget`
Returns per-adapter hourly/daily usage and remaining capacity. Call
this before an expensive batch so you can back off early.

## Adding a new backend

For a **new subscription CLI**:
1. Create `adapters/<name>_cli.py` subclassing `Adapter`.
2. Implement `call`, `handles_model`, `health`. Copy `claude_cli.py`
   as a template.
3. Register it in `server.py`'s `ADAPTERS` list.
4. Add a default caps entry and (optionally) a test case.

For a **new HTTP-API service**:
1. Create `adapters/<name>_api.py` subclassing `HttpForwardAdapter`.
2. Set `BASE_URL`, `API_KEY_ENV`, and override `handles_model`.
   See `openrouter.py` as a 30-line template.
3. Register and add caps.

Routing is first-match-wins by adapter order in `server.ADAPTERS`.
Keep the most specific claimers at the top, most general at the
bottom; run `tests/test_subscription_proxy.py` to verify no overlap.

## Safety

- **127.0.0.1 only.** Never expose on an external interface. This is
  single-user, single-machine infrastructure.
- **Personal use only.** Wrapping your own subscription for your own
  tools on your own machine is intended use. Proxying to other users,
  exposing on a network, or reselling is not.
- **No auth layer.** Anyone with shell access can already run the
  wrapped CLIs directly — adding auth would be security theater.
- **Fail-loud budget gates.** When a cap is reached the proxy returns
  HTTP 429 with the exact cap and usage. No silent degradation.
- **`--tools ""` for CLI adapters.** Prevents tool fan-out; one request
  = one message against subscription quota.
