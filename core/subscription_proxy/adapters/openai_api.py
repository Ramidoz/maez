# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter: OpenAI direct API (paid ChatGPT API access).

NOT a ChatGPT *subscription* proxy — OpenAI doesn't offer a CLI that
consumes ChatGPT Plus/Pro quota. This adapter uses api.openai.com with
an API key (billed per token, separately from any ChatGPT subscription).

Use this adapter when:
  - You want direct access to an OpenAI model without OpenRouter's
    small markup.
  - You need a feature OpenRouter doesn't passthrough cleanly (e.g.
    assistants API, specific fine-tuned model).

Otherwise, prefer OpenRouter (`openai/gpt-4o`) for unified billing.

Claims: models starting with `gpt-`, `o1-`, `o3-`, `o4-`, or
`chatgpt-`. Authentication: OPENAI_API_KEY.
"""
from __future__ import annotations

import os
import re

from core.subscription_proxy.adapters.http_forward import HttpForwardAdapter

_OPENAI_PREFIX_RE = re.compile(
    r"^(gpt-|o1-|o3-|o4-|chatgpt-)", re.IGNORECASE,
)


class OpenAiApiAdapter(HttpForwardAdapter):
    name = "openai"
    BASE_URL = os.environ.get(
        "MAEZ_OPENAI_BASE_URL", "https://api.openai.com/v1",
    )
    API_KEY_ENV = "OPENAI_API_KEY"

    DEFAULT = os.environ.get("MAEZ_OPENAI_DEFAULT_MODEL", "gpt-4o-mini")

    def handles_model(self, model: str) -> bool:
        return bool(model) and bool(_OPENAI_PREFIX_RE.match(model))

    def default_model(self) -> str:
        return self.DEFAULT
