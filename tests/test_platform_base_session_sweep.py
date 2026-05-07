# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Failing tests for slice 1.5 — `_active_sessions` idle eviction sweep.

These tests pin the spec for an idle-session sweeper that prevents
`BasePlatformAdapter._active_sessions` from leaking when handlers raise
before reaching cleanup, or when sessions intentionally outlive a single
turn (the "leave populated for drain" path).

Spec recap:
- A periodic asyncio task on the platform base, started at init/start,
  cancelled at stop.
- Sweeps every `MAEZ_SESSION_SWEEP_INTERVAL_S` (default 600s).
- Eviction criteria — ALL must hold:
    1. `last_touched_at` older than `MAEZ_SESSION_TTL_S` (default 86400s).
    2. The session's interrupt event is NOT set.
    3. The session_key is NOT referenced by a live `_background_tasks` task.
- INFO log on eviction. WARNING when criteria 2 or 3 blocks an
  otherwise-stale session (the "wedged interrupt" signal).
- Sweep accepts an injectable `now=` clock for deterministic tests.

These tests are EXPECTED TO FAIL until production code lands.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import unittest
from pathlib import Path
from typing import Any, Dict, Optional
from unittest import mock

_REPO = Path(__file__).resolve().parents[1]

from skills.surface.platform_base import BasePlatformAdapter
from skills.surface import Platform, PlatformConfig


# ---------------------------------------------------------------------------
# Minimal concrete adapter so we can instantiate BasePlatformAdapter without
# pulling in a network surface. Implements only the abstract methods.
# ---------------------------------------------------------------------------
class _StubAdapter(BasePlatformAdapter):
    async def connect(self) -> bool:  # pragma: no cover - shape only
        return True

    async def disconnect(self) -> None:  # pragma: no cover
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None):  # pragma: no cover
        return None

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:  # pragma: no cover
        return {"name": chat_id, "type": "dm"}


def _make_adapter() -> _StubAdapter:
    cfg = PlatformConfig(enabled=True, token="dummy", extra={})
    return _StubAdapter(cfg, Platform.TELEGRAM)


def _seed_session(
    adapter: _StubAdapter,
    key: str,
    *,
    age_s: float,
    is_set: bool = False,
    now: Optional[float] = None,
) -> asyncio.Event:
    """Insert a session into `_active_sessions` with a fabricated touch time."""
    if now is None:
        now = time.time()
    ev = asyncio.Event()
    if is_set:
        ev.set()
    # The implementer is expected to record `last_touched_at` either as an
    # attribute on the event or via a parallel dict. We set both forms so the
    # test does not over-pin the storage shape; whichever the impl reads must
    # see the seeded value.
    setattr(ev, "last_touched_at", now - age_s)
    adapter._active_sessions[key] = ev
    last_touched = getattr(adapter, "_active_session_touched_at", None)
    if isinstance(last_touched, dict):
        last_touched[key] = now - age_s
    else:
        # Pre-create the parallel dict in case the impl uses it.
        adapter._active_session_touched_at = {key: now - age_s}
    return ev


class SessionSweepTests(unittest.IsolatedAsyncioTestCase):
    """Slice 1.5 — idle eviction of `_active_sessions` entries."""

    async def asyncSetUp(self) -> None:
        # Strip env overrides so defaults are deterministic.
        self._env_patch = mock.patch.dict(
            os.environ,
            {k: v for k, v in os.environ.items()
             if not k.startswith("MAEZ_SESSION_")},
            clear=False,
        )
        self._env_patch.start()
        for k in ("MAEZ_SESSION_SWEEP_INTERVAL_S", "MAEZ_SESSION_TTL_S"):
            os.environ.pop(k, None)
        self.adapter = _make_adapter()

    async def asyncTearDown(self) -> None:
        try:
            await self.adapter.cancel_background_tasks()
        except Exception:
            pass
        # Stop sweep task if started.
        stop = getattr(self.adapter, "stop", None)
        if stop is not None:
            try:
                await stop()
            except Exception:
                pass
        self._env_patch.stop()

    # -------------------------------------------------------------- core paths
    async def test_sweep_evicts_idle_session(self) -> None:
        now = 1_000_000.0
        key = "telegram:dm:42"
        _seed_session(self.adapter, key, age_s=25 * 3600, is_set=False, now=now)
        self.assertIn(key, self.adapter._active_sessions)

        sweep = getattr(self.adapter, "_sweep_idle_sessions", None)
        self.assertIsNotNone(
            sweep, "BasePlatformAdapter must expose `_sweep_idle_sessions`"
        )

        with self.assertLogs(level="INFO") as cap:
            result = sweep(now=now)
            if asyncio.iscoroutine(result):
                await result

        self.assertNotIn(key, self.adapter._active_sessions)
        self.assertTrue(
            any("evict" in r.getMessage().lower() or "idle" in r.getMessage().lower()
                for r in cap.records),
            f"Expected INFO log on eviction; got {[r.getMessage() for r in cap.records]}",
        )

    async def test_sweep_keeps_recent_session(self) -> None:
        now = 1_000_000.0
        key = "telegram:dm:42"
        _seed_session(self.adapter, key, age_s=23 * 3600, is_set=False, now=now)

        sweep = getattr(self.adapter, "_sweep_idle_sessions", None)
        self.assertIsNotNone(sweep)

        result = sweep(now=now)
        if asyncio.iscoroutine(result):
            await result

        self.assertIn(key, self.adapter._active_sessions,
                      "Recent sessions must NOT be evicted")

    async def test_sweep_skips_session_with_set_event(self) -> None:
        now = 1_000_000.0
        key = "telegram:dm:wedged"
        _seed_session(self.adapter, key, age_s=25 * 3600, is_set=True, now=now)

        sweep = getattr(self.adapter, "_sweep_idle_sessions", None)
        self.assertIsNotNone(sweep)

        with self.assertLogs(level="WARNING") as cap:
            result = sweep(now=now)
            if asyncio.iscoroutine(result):
                await result

        self.assertIn(key, self.adapter._active_sessions,
                      "Sessions with set interrupt events must NOT be evicted")
        self.assertTrue(
            any(r.levelno >= logging.WARNING for r in cap.records),
            "Wedged-but-set sessions must emit WARNING",
        )

    async def test_sweep_skips_session_with_active_background_task(self) -> None:
        now = 1_000_000.0
        key = "telegram:dm:busy"
        _seed_session(self.adapter, key, age_s=25 * 3600, is_set=False, now=now)

        # Fabricate a live background task referencing this session_key.
        async def _slow():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                return

        task = asyncio.create_task(_slow(), name=f"process:{key}")
        # Tag the task so the sweeper can correlate by attribute, and also
        # register it on the adapter's tracked set as production does.
        setattr(task, "session_key", key)
        self.adapter._background_tasks.add(task)

        try:
            sweep = getattr(self.adapter, "_sweep_idle_sessions", None)
            self.assertIsNotNone(sweep)

            with self.assertLogs(level="WARNING") as cap:
                result = sweep(now=now)
                if asyncio.iscoroutine(result):
                    await result

            self.assertIn(key, self.adapter._active_sessions,
                          "Sessions with live background tasks must NOT be evicted")
            self.assertTrue(
                any(r.levelno >= logging.WARNING for r in cap.records),
                "Active-task block must emit WARNING",
            )
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def test_sweep_handles_empty_active_sessions(self) -> None:
        sweep = getattr(self.adapter, "_sweep_idle_sessions", None)
        self.assertIsNotNone(sweep)

        # Should be a quiet no-op.
        result = sweep(now=time.time())
        if asyncio.iscoroutine(result):
            await result

        self.assertEqual(self.adapter._active_sessions, {})

    # ----------------------------------------------------------- env overrides
    async def test_sweep_interval_env_override(self) -> None:
        with mock.patch.dict(os.environ, {"MAEZ_SESSION_SWEEP_INTERVAL_S": "42"}):
            adapter = _make_adapter()
            interval = getattr(adapter, "_session_sweep_interval_s", None)
            self.assertEqual(interval, 42,
                             "MAEZ_SESSION_SWEEP_INTERVAL_S must override default")

        # Bogus value falls back to default safely.
        with mock.patch.dict(os.environ, {"MAEZ_SESSION_SWEEP_INTERVAL_S": "not-a-number"}):
            adapter = _make_adapter()
            interval = getattr(adapter, "_session_sweep_interval_s", None)
            self.assertEqual(interval, 600,
                             "Bad env value must fall back to 600s default")

    async def test_sweep_ttl_env_override(self) -> None:
        with mock.patch.dict(os.environ, {"MAEZ_SESSION_TTL_S": "3600"}):
            adapter = _make_adapter()
            ttl = getattr(adapter, "_session_ttl_s", None)
            self.assertEqual(ttl, 3600,
                             "MAEZ_SESSION_TTL_S must override default")

        with mock.patch.dict(os.environ, {"MAEZ_SESSION_TTL_S": "garbage"}):
            adapter = _make_adapter()
            ttl = getattr(adapter, "_session_ttl_s", None)
            self.assertEqual(ttl, 86400,
                             "Bad env value must fall back to 86400s default")

    # -------------------------------------------------------- lifecycle wiring
    async def test_sweep_task_cancelled_on_stop(self) -> None:
        start = getattr(self.adapter, "start", None)
        stop = getattr(self.adapter, "stop", None)
        self.assertIsNotNone(start, "BasePlatformAdapter must expose `start`")
        self.assertIsNotNone(stop, "BasePlatformAdapter must expose `stop`")

        result = start()
        if asyncio.iscoroutine(result):
            await result

        sweep_task = getattr(self.adapter, "_session_sweep_task", None)
        self.assertIsNotNone(sweep_task, "start() must spawn `_session_sweep_task`")
        self.assertFalse(sweep_task.done(),
                         "Sweep task must be live after start()")

        result = stop()
        if asyncio.iscoroutine(result):
            await result

        # Allow the cancellation to settle.
        for _ in range(10):
            if sweep_task.done():
                break
            await asyncio.sleep(0.01)

        self.assertTrue(sweep_task.done(),
                        "stop() must cancel the periodic sweep task")

    async def test_evicted_session_can_be_re_created_cleanly(self) -> None:
        now = 1_000_000.0
        key = "telegram:dm:reborn"
        _seed_session(self.adapter, key, age_s=25 * 3600, is_set=False, now=now)

        sweep = getattr(self.adapter, "_sweep_idle_sessions", None)
        self.assertIsNotNone(sweep)
        result = sweep(now=now)
        if asyncio.iscoroutine(result):
            await result
        self.assertNotIn(key, self.adapter._active_sessions)

        # Re-seed the same key as a fresh entry — production code re-creates
        # via `_active_sessions[session_key] = asyncio.Event()` on next turn.
        # No exception, no leftover state.
        new_event = asyncio.Event()
        self.adapter._active_sessions[key] = new_event
        self.assertIs(self.adapter._active_sessions[key], new_event)
        self.assertFalse(new_event.is_set())

        # And it must be sweep-eligible again on the same rules.
        setattr(new_event, "last_touched_at", now - 25 * 3600)
        touched = getattr(self.adapter, "_active_session_touched_at", None)
        if isinstance(touched, dict):
            touched[key] = now - 25 * 3600

        result = sweep(now=now)
        if asyncio.iscoroutine(result):
            await result
        self.assertNotIn(key, self.adapter._active_sessions,
                         "Re-created session must be sweep-eligible on the same rules")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
