# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 1.5 — Telegram adapter periodic batch-dict sweeper.

The TelegramAdapter holds three paired dicts that map per-sender / per-album
keys to a (MessageEvent, asyncio.Task) pair:

  - _pending_text_batches  + _pending_text_batch_tasks
  - _pending_photo_batches + _pending_photo_batch_tasks
  - _media_group_events    + _media_group_tasks

Each pair self-evicts on its happy path inside the corresponding
``_flush_*`` function's ``finally`` block. Exception / race residue
(silently-crashed flush task, late album member arriving 6h after the
album, etc.) bypasses that finally and the entry sits forever, with the
dicts growing as O(unique_senders + unique_albums).

Slice 1.5 introduces a periodic sweeper that:
  - runs as an asyncio task started at adapter init and cancelled on stop()
  - sweeps every ``MAEZ_TELEGRAM_SWEEP_INTERVAL_S`` (default 60s)
  - evicts entries whose ``last_touched_at`` is older than
    ``MAEZ_TELEGRAM_BATCH_TTL_S`` (default 300s)
  - cancels any non-done task on the way out
  - logs INFO on benign residue, WARNING when the task was still live
    (signal that a flush silently crashed)
  - both env vars use the slice-1.2/1.3 safe-fallback parsing posture:
    bad value → default + WARNING

These tests pin the contract BEFORE the sweeper exists, so they MUST
fail until slice 1.5 ships.

The implementer is free to choose names, but tests reference these
attributes / methods and the implementer must match them:

  - adapter._batch_sweep_task                  : the periodic asyncio.Task
  - adapter._evict_stale_batches(now=...)      : awaitable, one-tick sweep
  - adapter._sweep_interval_s                  : resolved interval (float)
  - adapter._batch_ttl_s                       : resolved TTL (float)
  - adapter._batch_last_touched: Dict[str, Dict[str, float]]
        keyed first by which-dict ("text" | "photo" | "media_group"),
        then by the same key as the corresponding pending-* dict, value
        is monotonic-or-wall timestamp seconds. The implementer may also
        store last_touched_at on the MessageEvent itself; the tests probe
        the public _batch_last_touched dict for determinism.

If the implementer prefers a different storage shape, these tests are
the contract — change the storage to satisfy them, not the other way.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from skills.surface.platform_config import PlatformConfig  # noqa: E402
from skills.surface.telegram_adapter import TelegramAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_NOW = 1_000_000.0  # arbitrary fixed clock anchor for deterministic tests


def _make_adapter() -> TelegramAdapter:
    """Construct a bare adapter — no network, no real bot."""
    return TelegramAdapter(PlatformConfig())


async def _done_task() -> None:
    """An immediately-completed task (happy-path residue)."""
    return None


async def _never_completes() -> None:
    """A task that hangs forever — simulates a silently-crashed flush
    that was awaiting something that never arrives. The sweep must
    cancel it before evicting."""
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        raise


def _make_done_task() -> asyncio.Task:
    t = asyncio.create_task(_done_task())
    return t


def _make_undone_task() -> asyncio.Task:
    return asyncio.create_task(_never_completes())


def _seed_text(adapter, key, *, age_s, task):
    adapter._pending_text_batches[key] = object()  # MessageEvent stand-in
    adapter._pending_text_batch_tasks[key] = task
    adapter._batch_last_touched.setdefault("text", {})[key] = _NOW - age_s


def _seed_photo(adapter, key, *, age_s, task):
    adapter._pending_photo_batches[key] = object()
    adapter._pending_photo_batch_tasks[key] = task
    adapter._batch_last_touched.setdefault("photo", {})[key] = _NOW - age_s


def _seed_media_group(adapter, key, *, age_s, task):
    adapter._media_group_events[key] = object()
    adapter._media_group_tasks[key] = task
    adapter._batch_last_touched.setdefault("media_group", {})[key] = _NOW - age_s


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class BatchSweepBehavior(unittest.IsolatedAsyncioTestCase):
    """Slice 1.5 sweeper behavior — these all fail until shipped."""

    async def asyncTearDown(self) -> None:
        # Drain any tasks the tests created; isolation hygiene.
        # (The sweep should already have done this, but tests that fail
        # before the sweep runs need cleanup too.)
        await asyncio.sleep(0)

    # ------- core eviction -------------------------------------------------

    async def test_sweep_evicts_stale_text_batch(self):
        adapter = _make_adapter()
        key = "chat:42:user:7"
        task = _make_done_task()
        await asyncio.sleep(0)  # let the done-task settle
        _seed_text(adapter, key, age_s=600, task=task)

        with self.assertLogs("skills.surface.telegram_adapter", level="INFO") as cap:
            await adapter._evict_stale_batches(now=_NOW)

        self.assertNotIn(key, adapter._pending_text_batches)
        self.assertNotIn(key, adapter._pending_text_batch_tasks)
        # Some INFO line must reference the eviction.
        self.assertTrue(
            any("evict" in r.getMessage().lower() for r in cap.records),
            f"expected INFO log about eviction, got: {[r.getMessage() for r in cap.records]}",
        )

    async def test_sweep_keeps_fresh_text_batch(self):
        adapter = _make_adapter()
        key = "chat:42:user:7"
        task = _make_done_task()
        await asyncio.sleep(0)
        _seed_text(adapter, key, age_s=60, task=task)

        await adapter._evict_stale_batches(now=_NOW)

        self.assertIn(key, adapter._pending_text_batches)
        self.assertIn(key, adapter._pending_text_batch_tasks)

    async def test_sweep_evicts_stale_photo_batch(self):
        adapter = _make_adapter()
        key = "chat:9:user:3"
        task = _make_done_task()
        await asyncio.sleep(0)
        _seed_photo(adapter, key, age_s=600, task=task)

        await adapter._evict_stale_batches(now=_NOW)

        self.assertNotIn(key, adapter._pending_photo_batches)
        self.assertNotIn(key, adapter._pending_photo_batch_tasks)

    async def test_sweep_evicts_stale_media_group_orphan(self):
        adapter = _make_adapter()
        key = "media_group_id:abc123"
        task = _make_done_task()
        await asyncio.sleep(0)
        _seed_media_group(adapter, key, age_s=600, task=task)

        await adapter._evict_stale_batches(now=_NOW)

        self.assertNotIn(key, adapter._media_group_events)
        self.assertNotIn(key, adapter._media_group_tasks)

    # ------- task lifecycle on eviction ------------------------------------

    async def test_sweep_warning_on_active_task(self):
        """Stale entry whose task is still .done() is False = silently
        crashed flush. Must evict AND log WARNING (operator signal)."""
        adapter = _make_adapter()
        key = "chat:42:user:7"
        task = _make_undone_task()
        try:
            _seed_text(adapter, key, age_s=600, task=task)

            with self.assertLogs(
                "skills.surface.telegram_adapter", level="WARNING"
            ) as cap:
                await adapter._evict_stale_batches(now=_NOW)

            self.assertNotIn(key, adapter._pending_text_batches)
            self.assertNotIn(key, adapter._pending_text_batch_tasks)
            self.assertTrue(task.cancelled() or task.done())
            self.assertTrue(
                any(r.levelno >= logging.WARNING for r in cap.records),
                "expected WARNING when active task is swept",
            )
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BaseException):
                pass

    async def test_sweep_cancels_undone_task_before_evict(self):
        adapter = _make_adapter()
        key = "chat:1:user:1"
        task = _make_undone_task()
        try:
            _seed_text(adapter, key, age_s=600, task=task)

            await adapter._evict_stale_batches(now=_NOW)

            # task.cancel() called → task ends in cancelled state.
            self.assertTrue(
                task.cancelled() or task.done(),
                "sweep must cancel non-done tasks before evicting",
            )
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BaseException):
                pass

    # ------- robustness ----------------------------------------------------

    async def test_sweep_handles_empty_dicts(self):
        adapter = _make_adapter()
        # No seeding. Must be a clean no-op.
        await adapter._evict_stale_batches(now=_NOW)
        self.assertEqual(adapter._pending_text_batches, {})
        self.assertEqual(adapter._pending_photo_batches, {})
        self.assertEqual(adapter._media_group_events, {})

    # ------- env override + safe-fallback (slice 1.2/1.3 posture) ----------

    def test_sweep_interval_env_override(self):
        with patch.dict(os.environ, {"MAEZ_TELEGRAM_SWEEP_INTERVAL_S": "10"}, clear=False):
            adapter = _make_adapter()
            self.assertEqual(adapter._sweep_interval_s, 10.0)

        # Bad value → default + WARNING
        with patch.dict(os.environ, {"MAEZ_TELEGRAM_SWEEP_INTERVAL_S": "abc"}, clear=False):
            with self.assertLogs(
                "skills.surface.telegram_adapter", level="WARNING"
            ) as cap:
                adapter = _make_adapter()
            self.assertEqual(adapter._sweep_interval_s, 60.0)
            self.assertTrue(
                any("MAEZ_TELEGRAM_SWEEP_INTERVAL_S" in r.getMessage() for r in cap.records),
                "expected WARNING naming the offending env var",
            )

    def test_sweep_ttl_env_override(self):
        with patch.dict(os.environ, {"MAEZ_TELEGRAM_BATCH_TTL_S": "120"}, clear=False):
            adapter = _make_adapter()
            self.assertEqual(adapter._batch_ttl_s, 120.0)

        with patch.dict(os.environ, {"MAEZ_TELEGRAM_BATCH_TTL_S": "not-a-number"}, clear=False):
            with self.assertLogs(
                "skills.surface.telegram_adapter", level="WARNING"
            ) as cap:
                adapter = _make_adapter()
            self.assertEqual(adapter._batch_ttl_s, 300.0)
            self.assertTrue(
                any("MAEZ_TELEGRAM_BATCH_TTL_S" in r.getMessage() for r in cap.records),
                "expected WARNING naming the offending env var",
            )

    # ------- lifecycle: start/stop -----------------------------------------

    async def test_sweep_task_cancelled_on_adapter_stop(self):
        """The periodic sweep task — created via
        ``_ensure_batch_sweep_started()`` (called from __init__ when a
        loop exists, OR from connect() in production) — must be
        cancelled by stop(). After stop(), it's .done().

        Note on lifecycle: __init__'s call to the helper succeeds here
        because IsolatedAsyncioTestCase has a running loop. In
        production the adapter is constructed synchronously, init's
        call defers, and connect() does the load-bearing start. See
        StartedOutsideEventLoop test class for that scenario.
        """
        adapter = _make_adapter()
        sweep_task = adapter._batch_sweep_task
        self.assertIsNotNone(
            sweep_task,
            "in test context (running loop), init must create the "
            "periodic sweep task via _ensure_batch_sweep_started()",
        )
        self.assertFalse(sweep_task.done(), "sweep task should be running after init")

        await adapter.stop()

        # Give the loop a beat to register the cancellation.
        for _ in range(10):
            if sweep_task.done():
                break
            await asyncio.sleep(0.01)

        self.assertTrue(
            sweep_task.done(),
            "stop() must cancel the periodic sweep task",
        )


class StartedOutsideEventLoop(unittest.TestCase):
    """Behavioral regression for the slice 1.5 follow-up production bug.

    Production constructs TelegramAdapter synchronously (no event loop
    running) BEFORE scheduling connect() on the daemon's loop. The
    original slice 1.5 implementation only created _batch_sweep_task
    in __init__; with no loop available, ``asyncio.create_task``
    raised, the warning was logged, and the task silently never ran
    in production — even though IsolatedAsyncioTestCase tests passed.

    This test directly reproduces that scenario:
      1. Construct in sync context. Assert _batch_sweep_task is None.
      2. Enter an event loop, call _ensure_batch_sweep_started().
         Assert task is now alive.
      3. Stop the adapter; assert task is done.

    A regression that drops connect()'s call to the helper (or
    reverts to init-only creation) fails this test directly.
    """

    def test_sync_construct_then_async_start(self):
        # Phase 1: sync construction, no event loop.
        adapter = TelegramAdapter(PlatformConfig())
        self.assertIsNone(
            adapter._batch_sweep_task,
            "synchronous construction outside an event loop must not "
            "have created the sweep task; the deferred-start helper "
            "is the only correct path here",
        )

        # Phase 2: enter a loop and call the helper directly. This
        # mirrors what connect() does in production after the daemon
        # establishes its event loop.
        async def _start_then_stop():
            adapter._ensure_batch_sweep_started()
            self.assertIsNotNone(
                adapter._batch_sweep_task,
                "after entering a loop and calling the helper, the "
                "task must be created — this is the production path",
            )
            self.assertFalse(
                adapter._batch_sweep_task.done(),
                "newly-created sweep task must be alive",
            )
            # Idempotency check: calling again should not duplicate.
            existing = adapter._batch_sweep_task
            adapter._ensure_batch_sweep_started()
            self.assertIs(
                adapter._batch_sweep_task, existing,
                "_ensure_batch_sweep_started must be idempotent — a "
                "second call when the task is already running must "
                "NOT create a new task",
            )
            # Phase 3: stop cleanly.
            await adapter.stop()
            self.assertTrue(
                existing.done(),
                "stop() must cancel the sweep task",
            )

        asyncio.run(_start_then_stop())

        # After stop(), the helper resets the task ref to None.
        self.assertIsNone(
            adapter._batch_sweep_task,
            "stop() must reset _batch_sweep_task to None so a "
            "subsequent connect() can re-start cleanly",
        )


if __name__ == "__main__":
    unittest.main()
