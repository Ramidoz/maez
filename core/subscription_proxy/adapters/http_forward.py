# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""HTTP-forward adapter base — for backends that already speak
OpenAI-compatible /v1/chat/completions.

Use cases:
  - OpenRouter: one API key, 100+ models (GPT, Claude, Gemini, Grok,
    Llama, etc.). Pay-as-you-go. Cheapest/simplest way to reach
    ChatGPT-class and Grok-class models.
  - Ollama Cloud: Ollama's hosted inference tier.
  - Direct OpenAI / xAI / Mistral APIs when you hold keys for those.

Why separate from subscription-CLI adapters:
  - No subprocess, no auth-via-OAuth flow — just HTTP with a bearer
    token from env.
  - Authentication state = "is the env var set?". No interactive
    flow, no token refresh — the API key is long-lived.
  - Budget naturally expressed as USD-spent, not call-count. This
    base records both so the proxy's budget guard can use whichever
    is meaningful to the user.

Concrete adapters (OpenRouterAdapter, etc.) subclass this and override
the bare minimum: BASE_URL, API_KEY_ENV, supported-model matchers,
and optionally a model alias map.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from typing import Optional

from core.subscription_proxy.adapters.base import Adapter, CallResult

logger = logging.getLogger("maez.subscription_proxy.http")


class HttpForwardAdapter(Adapter):
    """Subclass me. At minimum override name, BASE_URL, API_KEY_ENV,
    and handles_model(). Optionally override model alias handling."""

    BASE_URL: str = ""          # e.g. "https://openrouter.ai/api/v1"
    API_KEY_ENV: str = ""       # env var holding the API key
    TIMEOUT_S: float = 120.0

    def _api_key(self) -> Optional[str]:
        key = os.environ.get(self.API_KEY_ENV, "").strip()
        return key or None

    def health(self) -> dict:
        return {
            "adapter": self.name,
            "base_url": self.BASE_URL,
            "configured": bool(self._api_key()),
            "api_key_env": self.API_KEY_ENV,
            "auth_mode": f"Bearer token from ${self.API_KEY_ENV}",
        }

    def handles_model(self, model: str) -> bool:
        # Subclasses override with their own model-prefix rules.
        # Default: match nothing — forces explicit claim per adapter.
        return False

    def resolve_model(self, requested: str) -> str:
        # Subclasses can override to map aliases. Default: pass through.
        return requested or self.default_model()

    async def call(self, *, prompt: str, system_prompt: Optional[str],
                    model: str) -> CallResult:
        api_key = self._api_key()
        if not api_key:
            raise RuntimeError(
                f"{self.name} adapter not configured — set "
                f"${self.API_KEY_ENV}"
            )

        resolved = self.resolve_model(model)
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": resolved,
            "messages": messages,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")

        def _do_request() -> dict:
            req = urllib.request.Request(
                f"{self.BASE_URL.rstrip('/')}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "maez-subscription-proxy/0.1",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT_S) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")[:500]
                raise RuntimeError(f"{self.name} HTTP {e.code}: {err_body}")
            except urllib.error.URLError as e:
                raise RuntimeError(f"{self.name} URL error: {e.reason}")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"{self.name} produced unparseable JSON: {e}; "
                    f"head={raw[:200]!r}"
                )

        # urllib is sync — offload to a thread so we don't block the
        # FastAPI event loop on a slow backend.
        data = await asyncio.to_thread(_do_request)

        # OpenAI-compat response shape
        try:
            reply = (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(
                f"{self.name} returned unexpected shape: {data!r}"[:400]
            )

        usage = data.get("usage") or {}
        return CallResult(
            reply=reply,
            meta={"raw_usage": usage, "id": data.get("id")},
            input_toks=usage.get("prompt_tokens"),
            output_toks=usage.get("completion_tokens"),
            model_used=resolved,
        )
