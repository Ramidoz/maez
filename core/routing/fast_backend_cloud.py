# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/fast_backend_cloud.py — retired fast-lane cloud backend tombstone.

DEPRECATED = True. See docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md.
Retired on 2026-05-23 because the fast lane is now local-only; cloud remains
available through the main-loop claude-router cloud-as-tool path.

Hard contract:
  - CloudBackend.generate(...) always raises before any egress-capable step.
  - The router must not select this backend for fast-lane calls.
  - The module remains in-tree for one canonicalize cycle so hidden callers
    fail loudly instead of quietly re-opening cloud egress.

Env vars:
  MAEZ_CLOUD_BACKEND_ENABLED is ignored by generate(...). The constant remains
  for compatibility with older imports and diagnostics.
  MAEZ_CLOUD_PROVIDER          "anthropic" (default) | "openai"
  ANTHROPIC_API_KEY / OPENAI_API_KEY are not read by this backend; the
  subscription proxy owns provider credentials on the claude-router path.
  MAEZ_CLOUD_MODEL             optional override (defaults below)

Compatibility constants remain so older imports fail gracefully while the
module is present as a tombstone.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from core.fast_backend_local import BackendResult


logger = logging.getLogger(__name__)


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

DEPRECATED = True
RETIREMENT_SPEC = "docs/slices/privacy-egress-fast-backend-cloud-retirement/spec.md"
RETIREMENT_DATE = "2026-05-23"
RETIREMENT_REASON = (
    "fast-lane cloud path retired; cloud remains available through "
    "main-loop claude-router cloud-as-tool path"
)
EVENT_FAST_LANE_CLOUD_RETIRED_REFUSED = "fast_lane_cloud_retired_refused"


class FastLaneCloudRetiredError(RuntimeError):
    """Raised when retired fast-lane cloud egress is invoked directly."""

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
    """Retired fast-lane cloud backend tombstone."""

    @property
    def name(self) -> str:
        return _backend_name_for(_provider(), _model())

    def is_available(self) -> bool:
        return False

    def generate(
        self,
        prompt: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> BackendResult:
        _ = (max_tokens, temperature, timeout_s)
        try:
            logger.warning(
                "%s %s",
                EVENT_FAST_LANE_CLOUD_RETIRED_REFUSED,
                {
                    "event": EVENT_FAST_LANE_CLOUD_RETIRED_REFUSED,
                    "backend": "fast_backend_cloud",
                    "deprecated": True,
                    "retirement_spec": RETIREMENT_SPEC,
                    "retirement_date": RETIREMENT_DATE,
                    "prompt_chars": len(prompt or ""),
                },
            )
        except Exception:
            pass
        raise FastLaneCloudRetiredError(
            f"fast-lane cloud backend is retired by {RETIREMENT_SPEC}; "
            "use claude_router cloud-as-tool for cloud consults"
        )

    def __repr__(self) -> str:
        return "CloudBackend(DEPRECATED=True, retired=fast_lane_cloud_retired)"
