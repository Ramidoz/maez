"""Backend adapters for the Maez subscription proxy.

Each adapter wraps one backend (subscription CLI or API-key service)
and conforms to the Adapter interface in base.py. The server registers
adapters in a priority order and routes requests to the first adapter
that claims the requested model name.

Two adapter families:

  1. Subscription CLI adapters — wrap a vendor CLI that consumes a
     subscription quota (Claude Max, Google One AI Premium). The CLI
     handles OAuth; we just drive its --print/-p mode.

  2. HTTP-forward adapters — forward requests to an OpenAI-compatible
     HTTP endpoint with an API key (OpenRouter, Ollama Cloud, direct
     OpenAI, direct xAI, …). Per-token billing.

Adding a new backend:
  • For a new subscription CLI: subclass Adapter in base.py, implement
    call/handles_model/health, then register in server.ADAPTERS.
  • For a new HTTP service: subclass HttpForwardAdapter, override
    BASE_URL / API_KEY_ENV / handles_model, then register.
"""
from core.subscription_proxy.adapters.base import Adapter, CallResult  # noqa: F401
from core.subscription_proxy.adapters.claude_cli import ClaudeCliAdapter  # noqa: F401
from core.subscription_proxy.adapters.gemini_cli import GeminiCliAdapter  # noqa: F401
from core.subscription_proxy.adapters.http_forward import HttpForwardAdapter  # noqa: F401
from core.subscription_proxy.adapters.ollama_cloud import OllamaCloudAdapter  # noqa: F401
from core.subscription_proxy.adapters.openai_api import OpenAiApiAdapter  # noqa: F401
from core.subscription_proxy.adapters.openrouter import OpenRouterAdapter  # noqa: F401
from core.subscription_proxy.adapters.xai_api import XaiApiAdapter  # noqa: F401
