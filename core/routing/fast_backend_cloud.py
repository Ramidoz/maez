# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/fast_backend_cloud.py — Session 11d, staging-only.

Cloud backend for the fast reply prototype. Conformant with the Backend
protocol in core/fast_backend_router.py.

Hard contract:
  • Cloud is OFF by default. The router only invokes it if the operator
    explicitly enables cloud fallback via env var.
  • Direct provider credentials are no longer used here. Calls route through
    core.routing.claude_tier so the subscription proxy egress shadow gate sees
    every cloud-bound prompt.
  • Maez never sends raw private archives, full memory dumps, soul notes,
    proposal evidence, or any daemon-owned long-term state through this
    backend. The fast prompt builder produces the only payload allowed
    here, and it is intentionally tiny (~3KB target, 6KB hard cap).

Env vars:
  MAEZ_CLOUD_BACKEND_ENABLED   "1" to enable; anything else → disabled
  MAEZ_CLOUD_PROVIDER          "anthropic" (default) | "openai"
  ANTHROPIC_API_KEY / OPENAI_API_KEY are not read by this backend; the
  subscription proxy owns provider credentials.
  MAEZ_CLOUD_MODEL             optional override (defaults below)

Default models are the cheapest current-gen "small" tier — this is the
fast lane, not the deep lane:
  anthropic → claude-haiku-4-5-20251001
  openai    → gpt-4o-mini

Staging-only:
  • Not imported by daemon/maez_daemon.py
  • Not registered with maez.service
  • Only invoked by core.fast_backend_router (Session 11d)
"""

from __future__ import annotations

import os
import time
from typing import Optional

from core.fast_backend_local import BackendResult


# ── env-gated config ──────────────────────────────────────────────────
ENV_ENABLED  = 'MAEZ_CLOUD_BACKEND_ENABLED'
ENV_PROVIDER = 'MAEZ_CLOUD_PROVIDER'
ENV_MODEL    = 'MAEZ_CLOUD_MODEL'

PROVIDER_ANTHROPIC = 'anthropic'
PROVIDER_OPENAI    = 'openai'

DEFAULT_PROVIDER = PROVIDER_ANTHROPIC
DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: 'claude-haiku-4-5-20251001',
    PROVIDER_OPENAI:    'gpt-4o-mini',
}

DEFAULT_MAX_TOKENS  = 256
DEFAULT_TEMPERATURE = 0.4
DEFAULT_TIMEOUT_S   = 25.0

# Hard cap on prompt size sent to cloud — defense-in-depth on top of the
# fast_prompt_builder's HARD_CAP_CHARS (6000). If a caller somehow assembles
# something larger, we refuse to send it.
CLOUD_PROMPT_HARD_CAP_CHARS = 6500


def _provider() -> str:
    p = (os.environ.get(ENV_PROVIDER) or DEFAULT_PROVIDER).strip().lower()
    if p not in (PROVIDER_ANTHROPIC, PROVIDER_OPENAI):
        return DEFAULT_PROVIDER
    return p


def _enabled() -> bool:
    return (os.environ.get(ENV_ENABLED) or '').strip() == '1'


def _model() -> str:
    override = os.environ.get(ENV_MODEL)
    if override:
        return override.strip()
    return DEFAULT_MODELS[_provider()]


def _backend_name_for(provider: str, model: str) -> str:
    return f'cloud-{provider}-{model}'


def _api_key_for(provider: str) -> Optional[str]:
    # Compatibility helper for older imports. Direct provider credentials are
    # no longer the availability gate for this backend.
    if provider == PROVIDER_ANTHROPIC:
        return os.environ.get('ANTHROPIC_API_KEY')
    if provider == PROVIDER_OPENAI:
        return os.environ.get('OPENAI_API_KEY')
    return None


# ── Backend protocol class ─────────────────────────────────────────────
class CloudBackend:
    """Cloud backend (Anthropic or OpenAI). Disabled unless env-gated on."""

    @property
    def name(self) -> str:
        return _backend_name_for(_provider(), _model())

    def is_available(self) -> bool:
        if not _enabled():
            return False
        try:
            from core.routing import claude_tier
            return claude_tier.is_online()
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> BackendResult:
        provider = _provider()
        model    = _model()
        name     = _backend_name_for(provider, model)
        t0       = time.perf_counter()
        _ = (max_tokens, temperature)

        # Disabled / unconfigured paths — return clean failures, never raise.
        if not _enabled():
            return BackendResult(
                success=False, text='', backend_name=name,
                model_call_ms=0,
                error=(
                    f'cloud backend disabled (set {ENV_ENABLED}=1 to enable for staging)'
                ),
            )

        # Defense-in-depth size check
        if len(prompt) > CLOUD_PROMPT_HARD_CAP_CHARS:
            return BackendResult(
                success=False, text='', backend_name=name,
                model_call_ms=0,
                error=(
                    f'cloud prompt exceeds hard cap '
                    f'({len(prompt)} > {CLOUD_PROMPT_HARD_CAP_CHARS}) — refusing to send'
                ),
            )

        from core.egress.provenance import ProvenancedText
        from core.routing import claude_tier

        try:
            reply = claude_tier.call(
                prompt=ProvenancedText.owner_message_context(
                    prompt,
                    source_ref="core.routing.fast_backend_cloud:prompt",
                ),
                model=model,
                caller="fast_backend_cloud/generate",
                timeout_s=timeout_s,
            )
        except Exception as e:
            return BackendResult(
                success=False, text='', backend_name=name,
                model_call_ms=int((time.perf_counter() - t0) * 1000),
                error=f'proxy cloud call failed: {e!r}',
            )
        return BackendResult(
            success=True, text=reply.reply.strip(), backend_name=name,
            model_call_ms=int((time.perf_counter() - t0) * 1000),
            raw_status=200,
        )

    def __repr__(self) -> str:
        en = 'enabled' if _enabled() else 'disabled'
        return f'CloudBackend(provider={_provider()}, model={_model()}, {en})'
