"""Tests for core/health/shared_executor.py (slice 1.6 primitive).

These tests are written BEFORE the implementation (TDD). They are
expected to fail with ImportError until core/health/shared_executor.py
is created.

Spec recap:
    - get_shared_executor() returns a process-wide singleton
      ThreadPoolExecutor with max_workers=8 by default.
    - MAEZ_SHARED_EXECUTOR_MAX_WORKERS env var overrides; invalid /
      non-positive values fall back to 8 with a WARNING.
    - run_llm_in_executor(loop, fn, *, timeout_s=None) wraps a sync
      LLM call with asyncio.wait_for so the awaiter is bounded even
      when the worker thread itself can't be cancelled. Default
      timeout from MAEZ_LLM_CALL_TIMEOUT_S env (default 120s).
    - shutdown_shared_executor(wait, cancel_futures) tears down the
      singleton and clears the module-level ref.
    - is_initialized() reports whether the singleton currently exists.
    - Worker threads use a stable name prefix ("maez-shared").

Slice 1.1 motivation: 12 run_in_executor(None, ...) call sites leak
threads into Python's default pool (min(32, cpu+4), never reaped).
This primitive bounds that to 6 named, shutdown-able workers.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock


def _import_module():
    """Import (or re-import) the shared_executor module fresh.

    We re-import inside each test so that env-var patches applied via
    ``mock.patch.dict(os.environ, ...)`` are observed by module-level
    code paths that read the environment.
    """
    import importlib
    import sys

    name = "core.health.shared_executor"
    if name in sys.modules:
        del sys.modules[name]
    return importlib.import_module(name)


class SharedExecutorTests(unittest.TestCase):
    """Behavioural tests for the shared executor singleton."""

    def setUp(self) -> None:
        # Ensure we always start from a clean slate.
        try:
            mod = _import_module()
            mod.shutdown_shared_executor(wait=True)
        except Exception:
            # Module may not exist yet (pre-implementation); that's the
            # whole point. Tests will surface the ImportError.
            pass

    def tearDown(self) -> None:
        # Never leak the executor across tests.
        try:
            mod = _import_module()
            mod.shutdown_shared_executor(wait=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 1. Singleton identity
    # ------------------------------------------------------------------
    def test_singleton_identity(self) -> None:
        mod = _import_module()
        a = mod.get_shared_executor()
        b = mod.get_shared_executor()
        self.assertIs(a, b)
        self.assertIsInstance(a, ThreadPoolExecutor)

    # ------------------------------------------------------------------
    # 2. Lazy initialization
    # ------------------------------------------------------------------
    def test_lazy_initialization(self) -> None:
        mod = _import_module()
        self.assertFalse(mod.is_initialized())
        mod.get_shared_executor()
        self.assertTrue(mod.is_initialized())

    # ------------------------------------------------------------------
    # 3. Default max_workers == 6
    # ------------------------------------------------------------------
    def test_max_workers_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_SHARED_EXECUTOR_MAX_WORKERS", None)
            mod = _import_module()
            ex = mod.get_shared_executor()
            self.assertEqual(ex._max_workers, 8)

    # ------------------------------------------------------------------
    # 4. Env override
    # ------------------------------------------------------------------
    def test_max_workers_env_override(self) -> None:
        with mock.patch.dict(
            os.environ, {"MAEZ_SHARED_EXECUTOR_MAX_WORKERS": "4"}
        ):
            mod = _import_module()
            ex = mod.get_shared_executor()
            self.assertEqual(ex._max_workers, 4)

    # ------------------------------------------------------------------
    # 5. Invalid env -> fallback + WARNING
    # ------------------------------------------------------------------
    def test_max_workers_env_invalid_falls_back(self) -> None:
        with mock.patch.dict(
            os.environ, {"MAEZ_SHARED_EXECUTOR_MAX_WORKERS": "abc"}
        ):
            with self.assertLogs(
                "core.health.shared_executor", level=logging.WARNING
            ) as cm:
                mod = _import_module()
                ex = mod.get_shared_executor()
            self.assertEqual(ex._max_workers, 8)
            self.assertTrue(
                any("WARNING" in r or "abc" in r or "fallback" in r.lower()
                    for r in cm.output),
                f"expected a warning about invalid env, got: {cm.output}",
            )

    # ------------------------------------------------------------------
    # 6. Zero env -> fallback + WARNING
    # ------------------------------------------------------------------
    def test_max_workers_env_zero_falls_back(self) -> None:
        with mock.patch.dict(
            os.environ, {"MAEZ_SHARED_EXECUTOR_MAX_WORKERS": "0"}
        ):
            with self.assertLogs(
                "core.health.shared_executor", level=logging.WARNING
            ) as cm:
                mod = _import_module()
                ex = mod.get_shared_executor()
            self.assertEqual(ex._max_workers, 8)
            self.assertTrue(cm.output, "expected a WARNING log entry")

    # ------------------------------------------------------------------
    # 7. Negative env -> fallback + WARNING
    # ------------------------------------------------------------------
    def test_max_workers_env_negative_falls_back(self) -> None:
        with mock.patch.dict(
            os.environ, {"MAEZ_SHARED_EXECUTOR_MAX_WORKERS": "-3"}
        ):
            with self.assertLogs(
                "core.health.shared_executor", level=logging.WARNING
            ) as cm:
                mod = _import_module()
                ex = mod.get_shared_executor()
            self.assertEqual(ex._max_workers, 8)
            self.assertTrue(cm.output, "expected a WARNING log entry")

    # ------------------------------------------------------------------
    # 8. Thread name prefix
    # ------------------------------------------------------------------
    def test_thread_name_prefix(self) -> None:
        mod = _import_module()
        ex = mod.get_shared_executor()

        def _capture() -> str:
            return threading.current_thread().name

        name = ex.submit(_capture).result(timeout=2.0)
        self.assertTrue(
            name.startswith("maez-shared"),
            f"expected worker name to start with 'maez-shared', got: {name!r}",
        )

    # ------------------------------------------------------------------
    # 9. Shutdown clears singleton; next call returns a fresh instance
    # ------------------------------------------------------------------
    def test_shutdown_clears_singleton(self) -> None:
        mod = _import_module()
        ex1 = mod.get_shared_executor()
        self.assertTrue(mod.is_initialized())

        mod.shutdown_shared_executor(wait=True)
        self.assertFalse(mod.is_initialized())

        ex2 = mod.get_shared_executor()
        self.assertIsNot(ex1, ex2)
        self.assertTrue(mod.is_initialized())

    # ------------------------------------------------------------------
    # 10. Default shutdown waits for pending tasks
    # ------------------------------------------------------------------
    def test_shutdown_with_pending_tasks_waits_by_default(self) -> None:
        mod = _import_module()
        ex = mod.get_shared_executor()

        result_box: dict[str, bool] = {}

        def _slow() -> None:
            time.sleep(0.05)
            result_box["done"] = True

        fut = ex.submit(_slow)
        mod.shutdown_shared_executor()  # default: wait=True
        self.assertTrue(fut.done(), "future should have completed before shutdown returned")
        self.assertTrue(result_box.get("done"), "task must have run to completion")
        self.assertFalse(mod.is_initialized())

    # ------------------------------------------------------------------
    # 11. cancel_futures=True drops pending work
    # ------------------------------------------------------------------
    def test_shutdown_cancel_futures_drops_pending(self) -> None:
        mod = _import_module()
        ex = mod.get_shared_executor()

        # Saturate the worker pool so subsequent submissions queue.
        gate = threading.Event()

        def _block() -> None:
            gate.wait(timeout=2.0)

        # Fill all worker slots.
        running = [ex.submit(_block) for _ in range(ex._max_workers)]
        # This one should sit in the queue and be cancellable.
        pending = ex.submit(_block)

        t0 = time.monotonic()
        mod.shutdown_shared_executor(wait=False, cancel_futures=True)
        elapsed = time.monotonic() - t0

        # Should return promptly (we asked not to wait).
        self.assertLess(elapsed, 0.5, f"shutdown took too long: {elapsed:.3f}s")
        # The queued future must have been cancelled.
        self.assertTrue(
            pending.cancelled() or pending.done(),
            "pending future should be cancelled or already resolved",
        )

        # Release blocked workers so they can exit cleanly.
        gate.set()
        for f in running:
            try:
                f.result(timeout=2.0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 12. Concurrent get_shared_executor() — no double-init race
    # ------------------------------------------------------------------
    def test_concurrent_get_shared_executor_returns_same_instance(self) -> None:
        mod = _import_module()
        N = 16
        barrier = threading.Barrier(N)
        results: list[ThreadPoolExecutor] = []
        results_lock = threading.Lock()

        def _race() -> None:
            barrier.wait(timeout=2.0)
            ex = mod.get_shared_executor()
            with results_lock:
                results.append(ex)

        threads = [threading.Thread(target=_race) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        self.assertEqual(len(results), N)
        first = results[0]
        for r in results[1:]:
            self.assertIs(r, first, "all racing callers must observe the same singleton")

    # ------------------------------------------------------------------
    # 13. Works as the executor argument to loop.run_in_executor
    # ------------------------------------------------------------------
    def test_can_be_used_with_run_in_executor(self) -> None:
        mod = _import_module()

        async def _drive() -> str:
            loop = asyncio.get_running_loop()
            ex = mod.get_shared_executor()
            return await loop.run_in_executor(
                ex, lambda: threading.current_thread().name
            )

        name = asyncio.run(_drive())
        self.assertTrue(
            name.startswith("maez-shared"),
            f"run_in_executor should dispatch onto a maez-shared worker, got: {name!r}",
        )

    # ------------------------------------------------------------------
    # 14-17. run_llm_in_executor — bounded await for unkillable LLM
    # threads (CRITICAL #1 from slice 1.6 adversarial review).
    # ------------------------------------------------------------------
    def test_run_llm_in_executor_propagates_result(self) -> None:
        from unittest import mock as _mock  # noqa: F401 - already imported above
        mod = _import_module()

        async def _drive() -> str:
            loop = asyncio.get_running_loop()
            return await mod.run_llm_in_executor(
                loop, lambda: "OK", timeout_s=5.0,
            )

        self.assertEqual(asyncio.run(_drive()), "OK")

    def test_run_llm_in_executor_timeout_raises(self) -> None:
        """A long-running fn beyond timeout_s raises TimeoutError —
        the worker thread is still busy, but the awaiter is freed."""
        mod = _import_module()

        async def _drive() -> None:
            loop = asyncio.get_running_loop()
            with self.assertRaises(asyncio.TimeoutError):
                await mod.run_llm_in_executor(
                    loop, lambda: time.sleep(5), timeout_s=0.05,
                )

        asyncio.run(_drive())

    def test_run_llm_in_executor_default_timeout_env_overridable(
        self,
    ) -> None:
        with mock.patch.dict(os.environ, {"MAEZ_LLM_CALL_TIMEOUT_S": "30"}):
            mod = _import_module()
            self.assertEqual(mod.LLM_CALL_TIMEOUT_S, 30.0)

        with mock.patch.dict(os.environ, {"MAEZ_LLM_CALL_TIMEOUT_S": "abc"}):
            with self.assertLogs(
                "core.health.shared_executor", level="WARNING",
            ) as cap:
                mod = _import_module()
            self.assertEqual(mod.LLM_CALL_TIMEOUT_S, 120.0)
            self.assertTrue(
                any("MAEZ_LLM_CALL_TIMEOUT_S" in r.getMessage()
                    for r in cap.records),
                f"expected WARNING naming MAEZ_LLM_CALL_TIMEOUT_S; "
                f"got {[r.getMessage() for r in cap.records]}",
            )

    def test_run_llm_in_executor_logs_warning_on_timeout(self) -> None:
        """Operator signal: when the wrapper times out, log a WARNING
        noting the worker thread may still be running. The thread is
        unkillable in Python; the warning is how operators see that
        the pool is being held by a stuck call."""
        mod = _import_module()

        async def _drive() -> None:
            loop = asyncio.get_running_loop()
            try:
                await mod.run_llm_in_executor(
                    loop, lambda: time.sleep(5), timeout_s=0.05,
                )
            except asyncio.TimeoutError:
                pass

        with self.assertLogs(
            "core.health.shared_executor", level="WARNING",
        ) as cap:
            asyncio.run(_drive())

        self.assertTrue(
            any("timed out" in r.getMessage().lower()
                or "timeout" in r.getMessage().lower()
                for r in cap.records),
            f"expected WARNING about timeout; got "
            f"{[r.getMessage() for r in cap.records]}",
        )


if __name__ == "__main__":
    unittest.main()
