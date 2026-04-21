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
    def __init__(self, trace) -> None:
        self._trace = trace

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
            gen = self._trace.generation(
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
            span = self._trace.span(
                name=f"tool:{name}",
                input=params,
                metadata={"ok": ok, **(metadata or {})},
            )
            span.end(output=output)
        except Exception as e:
            logger.debug("langfuse tool_call failed: %s", e)

    def event(self, name: str, payload: Optional[dict] = None) -> None:
        try:
            self._trace.event(name=name, metadata=payload or {})
        except Exception as e:
            logger.debug("langfuse event failed: %s", e)

    def update(
        self, *, output: Any = None, metadata: Optional[dict] = None
    ) -> None:
        try:
            self._trace.update(
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

    trace = None
    try:
        trace = client.trace(
            name=name,
            input=input,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug("langfuse trace creation failed: %s", e)
        yield _NoopTurn()
        return

    try:
        yield _ActiveTurn(trace)
    finally:
        try:
            client.flush()
        except Exception as e:
            logger.debug("langfuse flush failed: %s", e)
