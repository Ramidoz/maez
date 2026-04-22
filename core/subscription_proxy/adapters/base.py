# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Adapter interface for subscription-backed LLM providers.

Each backend (Claude, Gemini, OpenAI, etc.) implements this interface.
The proxy's server.py discovers registered adapters, asks each whether
it handles a given model name, and forwards the call to the first
match.

Design notes:
  - Adapters are ASYNC so a busy backend (slow CLI cold start) doesn't
    block the FastAPI event loop.
  - Each adapter owns its own supported-model list. The proxy does NOT
    maintain a global model registry — backends are authoritative over
    their own capabilities.
  - Adapters do NOT own budget state. That's shared across the proxy
    (one table per adapter) so a single caller can't starve another
    backend's quota.
  - Adapters SHOULD expose health() cheaply (sub-second). It's called
    from /health to surface auth state.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CallResult:
    """What an adapter returns from a successful call.

    reply       — the assistant's text response
    meta        — arbitrary provider-specific metadata (usage counts,
                  costs, session IDs, etc.) surfaced in the trajectory
                  log and in the /v1/chat/completions response when
                  relevant. Never load-bearing on the happy path.
    input_toks  — best-effort prompt token count for OpenAI response
    output_toks — best-effort completion token count
    model_used  — the exact provider-side model identifier invoked
                  (may differ from the requested alias)
    """
    reply: str
    meta: dict = field(default_factory=dict)
    input_toks: Optional[int] = None
    output_toks: Optional[int] = None
    model_used: Optional[str] = None


class Adapter(ABC):
    """Base class every subscription-backend adapter inherits from.

    Subclasses MUST set `name` (short identifier used in routing,
    budget keys, and trajectory log) and implement `call`,
    `handles_model`, and `health`.
    """

    name: str = "unknown"

    @abstractmethod
    async def call(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
    ) -> CallResult:
        """Run a one-shot completion. Must raise RuntimeError (or a
        subclass) on failure — the server catches that and returns a
        502 with the message. Must NOT consume budget on failure;
        the server handles trajectory logging."""
        raise NotImplementedError

    @abstractmethod
    def handles_model(self, model: str) -> bool:
        """Return True if this adapter should serve the given model
        identifier. Called during routing; case-insensitive matching
        is the adapter's responsibility. The FIRST adapter in the
        server's registration order that returns True wins."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict:
        """Quick (< 1s, no network) liveness + auth check. Returned
        as-is under `/health` and per-backend sections of `/budget`."""
        raise NotImplementedError

    def default_model(self) -> str:
        """Fallback model identifier when the caller doesn't supply
        one. Override if your backend has a cheap/fast default
        (most do — sonnet for Claude, flash for Gemini, etc.)."""
        return ""
