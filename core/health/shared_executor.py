# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Process-wide shared ThreadPoolExecutor for the daemon (slice 1.6).

The 12 ``run_in_executor(None, ...)`` call sites in skills/surface/
maez_adapter.py and skills/telegram_voice.py used Python's default
thread pool (``min(32, cpu_count + 4)``) which under sustained load
fills with idle workers that never reap. The slice 1.1 thread audit
attributed ~150-200 of the 330 leaked-threads-per-43-min hang to this
class of leak.

This module provides:

  * ``get_shared_executor()`` — process-wide singleton, lazily
    initialized, max_workers bounded (default 8) via env var.

  * ``run_llm_in_executor(loop, fn, *, timeout_s=...)`` — wraps the
    LLM call sites with ``asyncio.wait_for`` so the awaiter is
    BOUNDED even though the worker thread itself can't be cancelled
    (Python limitation: sync code in a thread runs to completion
    regardless of asyncio task cancellation). Without this wrapper,
    a wedged llama.cpp would fill the pool with N stuck workers and
    every awaiter would block forever — making slice 1.6 alone
    WORSE than the unbounded default. The wrapper ensures the
    daemon's reply path moves on after timeout_s; the stuck thread
    is reaped on process exit.

  * ``shutdown_shared_executor(wait, cancel_futures)`` — daemon stop()
    integration. Default ``cancel_futures=True`` because running LLM
    calls can't be cancelled mid-flight in Python; the queued futures
    can.

Thread-safe. Per-process state. Restart resets.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger("core.health.shared_executor")

__all__ = [
    "get_shared_executor",
    "shutdown_shared_executor",
    "is_initialized",
    "run_llm_in_executor",
    "LLM_CALL_TIMEOUT_S",
]

_DEFAULT_MAX_WORKERS = 8
_DEFAULT_LLM_CALL_TIMEOUT_S = 120.0
_THREAD_NAME_PREFIX = "maez-shared"


def _parse_positive_int_env(name: str, default: int) -> int:
    """Parse a positive int env var with safe-fallback + WARNING.
    Same posture as slice 1.2/1.3/1.4 env parsing — a typo on a
    survivability knob must not crash daemon import.
    """
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("%s=%r is invalid; using %d", name, raw, default)
        return default
    if value < 1:
        logger.warning("%s=%r must be >= 1; using %d", name, raw, default)
        return default
    return value


def _parse_positive_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("%s=%r is invalid; using %.1fs", name, raw, default)
        return default
    if value <= 0:
        logger.warning(
            "%s=%r must be positive; using %.1fs", name, raw, default,
        )
        return default
    return value


# Read at module import; tests reload to pick up new env values.
LLM_CALL_TIMEOUT_S = _parse_positive_float_env(
    "MAEZ_LLM_CALL_TIMEOUT_S", _DEFAULT_LLM_CALL_TIMEOUT_S,
)


# ── singleton state ───────────────────────────────────────────────────

_lock = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None


def get_shared_executor() -> ThreadPoolExecutor:
    """Return the process-wide singleton. Lazily initialized.

    Bound by ``MAEZ_SHARED_EXECUTOR_MAX_WORKERS`` (default 8). The
    bound is set at first-call time; subsequent env-var changes do
    NOT take effect until ``shutdown_shared_executor`` clears the
    singleton.
    """
    global _executor
    with _lock:
        if _executor is None:
            workers = _parse_positive_int_env(
                "MAEZ_SHARED_EXECUTOR_MAX_WORKERS",
                _DEFAULT_MAX_WORKERS,
            )
            _executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix=_THREAD_NAME_PREFIX,
            )
            logger.debug(
                "shared executor initialized (max_workers=%d)", workers,
            )
        return _executor


def is_initialized() -> bool:
    """Whether the singleton has been constructed."""
    with _lock:
        return _executor is not None


def shutdown_shared_executor(
    wait: bool = True,
    cancel_futures: bool = False,
) -> None:
    """Tear down the singleton; clear the module-level ref so a future
    ``get_shared_executor()`` call returns a fresh instance.

    For daemon stop() integration, prefer ``cancel_futures=True``
    so QUEUED futures are dropped (running LLM calls can't be
    cancelled in Python; they'll be reaped on process exit).
    """
    global _executor
    with _lock:
        ex = _executor
        _executor = None
    if ex is not None:
        ex.shutdown(wait=wait, cancel_futures=cancel_futures)


# ── LLM-site wrapper ─────────────────────────────────────────────────

async def run_llm_in_executor(
    loop: asyncio.AbstractEventLoop,
    fn: Callable[[], Any],
    *args: Any,
    timeout_s: Optional[float] = None,
) -> Any:
    """Run ``fn`` in the shared executor with an asyncio-side timeout.

    .. WARNING::
        **NOT WIRED INTO PRODUCTION** as of slice 1.6 follow-up.

        Initial slice 1.6 used this helper at LLM-bearing call sites
        but that introduced a worse problem: the awaiter times out
        while the worker thread keeps running. Several of the
        affected call sites (run_brain_loop, jarvis_loop,
        pipe.handle_reply, etc.) write durable state — memory rows,
        approval cards, intermediate Telegram sends — AFTER the
        surface has already given up. Result: ghost turns where the
        user gets "internal error" + a stale follow-up message
        appears 3 minutes later from the abandoned worker.

        Root fix requires either (a) per-call deadlines INSIDE the
        LLM client (the pattern slice 1.1 used for proposal_intent
        and slice 1.2 for the grounding judge) extended to brain_loop
        and jarvis_loop, OR (b) turn-generation tokens that workers
        check before writing side effects.

        Until one of those lands, production sites use plain
        ``loop.run_in_executor(get_shared_executor(), fn)`` —
        pool-bounded, no awaiter timeout. That preserves the slice
        1.6 leak fix without introducing the ghost-turn risk.

    The worker thread itself can NOT be cancelled (Python sync code
    runs to completion). This wrapper bounds only the AWAITER. On
    timeout, logs a WARNING and raises ``asyncio.TimeoutError`` to
    the caller; the worker keeps running.
    """
    if timeout_s is None:
        timeout_s = LLM_CALL_TIMEOUT_S
    fut = loop.run_in_executor(
        get_shared_executor(),
        (lambda: fn(*args)) if args else fn,
    )
    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.warning(
            "LLM call exceeded %.1fs timeout; awaiter freed but worker "
            "thread may still be running (unkillable Python sync code). "
            "Pool budget remains consumed until the call returns.",
            timeout_s,
        )
        raise
