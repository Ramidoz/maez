# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter: Ollama Cloud (hosted inference tier from Ollama).

Pay-as-you-go. OpenAI-compatible endpoint. Signup at https://ollama.com.

Model naming: Ollama uses `<name>:<size-tag>` convention
(e.g. `gpt-oss:120b`, `qwen3:32b`, `llama3.2:70b`). We claim any model
string containing `:`.  Not ambiguous with other adapters:
  - `/` → OpenRouter
  - `:` → Ollama Cloud
  - prefix → Claude/Gemini/OpenAI/xAI

Authentication: set OLLAMA_API_KEY.
"""
from __future__ import annotations

import os

from core.subscription_proxy.adapters.http_forward import HttpForwardAdapter


class OllamaCloudAdapter(HttpForwardAdapter):
    name = "ollama_cloud"
    BASE_URL = os.environ.get(
        "MAEZ_OLLAMA_CLOUD_BASE_URL", "https://ollama.com/api",
    )
    API_KEY_ENV = "OLLAMA_API_KEY"

    DEFAULT = os.environ.get(
        "MAEZ_OLLAMA_CLOUD_DEFAULT_MODEL", "qwen3:32b",
    )

    def handles_model(self, model: str) -> bool:
        if not model:
            return False
        # Ollama's naming convention. Avoid false positives on HH:MM-ish
        # strings by requiring a non-numeric char on each side.
        if ":" not in model:
            return False
        left, right = model.split(":", 1)
        return bool(left) and bool(right) and not left.isdigit()

    def default_model(self) -> str:
        return self.DEFAULT
