# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter: xAI direct API (paid Grok API access).

NOT a Grok subscription proxy — X Premium+ doesn't expose a CLI.
This adapter uses api.x.ai with an API key (billed per token,
separately from any X Premium subscription).

Use this adapter when you want direct billing for Grok-specific
models rather than going through OpenRouter's `x-ai/grok-*` route.

Claims: models starting with `grok-`. Authentication: XAI_API_KEY.
"""
from __future__ import annotations

import os

from core.subscription_proxy.adapters.http_forward import HttpForwardAdapter


class XaiApiAdapter(HttpForwardAdapter):
    name = "xai"
    BASE_URL = os.environ.get(
        "MAEZ_XAI_BASE_URL", "https://api.x.ai/v1",
    )
    API_KEY_ENV = "XAI_API_KEY"

    DEFAULT = os.environ.get("MAEZ_XAI_DEFAULT_MODEL", "grok-4")

    def handles_model(self, model: str) -> bool:
        if not model:
            return False
        return model.lower().startswith("grok-")

    def default_model(self) -> str:
        return self.DEFAULT
