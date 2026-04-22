# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter: OpenRouter — unified API for 100+ models.

Why it's the best "many providers, one integration" option:
  - Single API key covers OpenAI, Anthropic, Google, xAI (Grok),
    Meta, Mistral, and many open-model hosts.
  - OpenAI-compatible wire format → near-zero adapter logic.
  - Pay-as-you-go billing; prepay credits on openrouter.ai.
  - Useful fallback when the Claude subscription is capped for the
    day, or for models nobody else proxies (Grok in particular has
    no clean local path).

Model routing: OpenRouter uses `<provider>/<model>` format, e.g.
  - openai/gpt-4o
  - anthropic/claude-sonnet-4.7
  - x-ai/grok-4
  - google/gemini-2.5-pro

We claim any model string containing a '/' — no other adapter uses
that shape. Callers should send the OpenRouter-native model id
verbatim; we pass it through unmodified.

Authentication:
  Set OPENROUTER_API_KEY in the environment. The adapter refuses
  calls (loud RuntimeError) if the env var is missing.
"""
from __future__ import annotations

import os

from core.subscription_proxy.adapters.http_forward import HttpForwardAdapter


class OpenRouterAdapter(HttpForwardAdapter):
    name = "openrouter"
    BASE_URL = os.environ.get(
        "MAEZ_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1",
    )
    API_KEY_ENV = "OPENROUTER_API_KEY"

    # Default when caller sends empty model. Cheap + fast: a small
    # OpenAI-tier model. Override via env if you want GPT-4o or Claude.
    DEFAULT = os.environ.get(
        "MAEZ_OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o-mini",
    )

    def handles_model(self, model: str) -> bool:
        # OpenRouter model ids always contain a provider/ prefix. If
        # the caller explicitly names one, route here.
        if not model:
            return False
        return "/" in model

    def default_model(self) -> str:
        return self.DEFAULT
