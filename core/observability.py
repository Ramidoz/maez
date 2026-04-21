# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
observability.py — thin Langfuse-wrapping abstraction for tracing
Maez's brain_loop and Telegram surface turns.

Design goals:
  1. Zero hard dependency on Langfuse. If the package is missing OR
     the LANGFUSE_PUBLIC_KEY env var isn't set, every call degrades
     to a silent no-op. The daemon ships and runs safely without
     anyone needing a Langfuse account.
  2. Vendor-swappable. All call sites in brain_loop / maez_adapter go
     through this module's API — `observe_turn`, `TurnContext.llm_call`,
     `TurnContext.tool_call`, `TurnContext.event`, `TurnContext.update`.
     Swapping Langfuse for LangSmith / Helicone / a local SQLite tracer
     means rewriting this module only.
  3. Silent on failure. If the Langfuse SDK raises (network blip, bad
     creds, etc.), we catch and continue. An observability failure
     must never break a Telegram turn.

Targets langfuse v4+ SDK (observation-based API, not the v2 trace/span
API). v4 dropped `client.trace()` in favor of `start_observation(...)`
with an `as_type` discriminator ("agent", "generation", "tool", etc.)
and child observations via the returned span's own `start_observation`
method. That shape maps cleanly onto Maez's turn/llm/tool hierarchy
and avoids OpenTelemetry context-var juggling across the executor
thread that brain_loop runs in.

Env vars consumed:
  LANGFUSE_PUBLIC_KEY  — required to activate (default off)
  LANGFUSE_SECRET_KEY  — required to activate
  LANGFUSE_HOST        — optional, defaults to https://cloud.langfuse.com
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger("maez.observability")

_client_cache: dict[str, Any] = {}


def _env_active() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


def _get_client():
    if "client" in _client_cache:
        return _client_cache["client"]
    if not _env_active():
        _client_cache["client"] = None
        return None
    try:
        from langfuse import Langfuse
    except Exception as e:
        logger.debug("langfuse import failed, observability off: %s", e)
        _client_cache["client"] = None
        return None
    try:
        client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get(
                "LANGFUSE_HOST", "https://cloud.langfuse.com"
            ),
        )
    except Exception as e:
        logger.debug("langfuse client init failed: %s", e)
        _client_cache["client"] = None
        return None
    _client_cache["client"] = client
    return client


class _NoopTurn:
    def llm_call(self, **kwargs) -> None:
        return None

    def tool_call(self, **kwargs) -> None:
        return None

    def event(self, name: str, payload: Optional[dict] = None) -> None:
        return None

    def update(self, **kwargs) -> None:
        return None


class _ActiveTurn:
    """Real TurnContext backed by a Langfuse v4 root observation.
    Child observations are created on the root via start_observation
    (which returns concrete LangfuseSpan/LangfuseGeneration/etc.
    objects depending on as_type). We end each child explicitly;
    the root is ended in observe_turn's finally block."""

    def __init__(self, root) -> None:
        self._root = root

    def llm_call(
        self,
        *,
        name: str,
        model: str,
        input: Any,
        output: Any,
        metadata: Optional[dict] = None,
    ) -> None:
        try:
            gen = self._root.start_observation(
                as_type="generation",
                name=name,
                model=model,
                input=input,
                output=output,
                metadata=metadata or {},
            )
            gen.end()
        except Exception as e:
            logger.debug("langfuse llm_call failed: %s", e)

    def tool_call(
        self,
        *,
        name: str,
        params: Any,
        output: Any,
        ok: bool,
        metadata: Optional[dict] = None,
    ) -> None:
        try:
            span = self._root.start_observation(
                as_type="tool",
                name=name,
                input=params,
                output=output,
                metadata={"ok": ok, **(metadata or {})},
            )
            span.end()
        except Exception as e:
            logger.debug("langfuse tool_call failed: %s", e)

    def event(
        self, name: str, payload: Optional[dict] = None
    ) -> None:
        """v4 has no distinct event primitive — record as a short span
        with input=payload. Call sites treat it as fire-and-forget."""
        try:
            span = self._root.start_observation(
                as_type="span",
                name=f"event:{name}",
                input=payload or {},
            )
            span.end()
        except Exception as e:
            logger.debug("langfuse event failed: %s", e)

    def update(
        self, *, output: Any = None, metadata: Optional[dict] = None
    ) -> None:
        try:
            self._root.update(
                output=output, metadata=metadata or {}
            )
        except Exception as e:
            logger.debug("langfuse update failed: %s", e)


@contextmanager
def observe_turn(
    name: str,
    *,
    input: Any = None,
    metadata: Optional[dict] = None,
):
    """Context manager yielding a TurnContext. Always safe to use —
    no-op when Langfuse is off, real trace when it's on. SDK errors
    are swallowed so observability never breaks the caller."""
    client = _get_client()
    if client is None:
        yield _NoopTurn()
        return

    root = None
    try:
        root = client.start_observation(
            as_type="agent",
            name=name,
            input=input,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug("langfuse root observation creation failed: %s", e)
        yield _NoopTurn()
        return

    try:
        yield _ActiveTurn(root)
    finally:
        try:
            root.end()
        except Exception as e:
            logger.debug("langfuse root observation end failed: %s", e)
        try:
            client.flush()
        except Exception as e:
            logger.debug("langfuse flush failed: %s", e)
