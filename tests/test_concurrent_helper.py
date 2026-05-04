# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Self-tests for tests/_helpers/concurrent.py.

The helper exists to make race-condition fixes testable
deterministically. Bugs in the helper would propagate to every
test that depends on it, so self-tests come first. Per TDD
discipline: RED → GREEN → land. No production imports.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class RunTwoThreads(unittest.TestCase):
    """``run_two_threads`` is the workhorse: launch two functions
    concurrently, optionally barrier-synchronized at start, capture
    exceptions from both, return both results, and time-out cleanly
    if either hangs."""

    def test_both_functions_execute_and_return_results(self):
        from tests._helpers.concurrent import run_two_threads
        a, b = run_two_threads(lambda: "alpha", lambda: "beta")
        self.assertTrue(a.ok)
        self.assertTrue(b.ok)
        self.assertEqual(a.return_value, "alpha")
        self.assertEqual(b.return_value, "beta")
        self.assertIsNone(a.exception)
        self.assertIsNone(b.exception)

    def test_exception_in_one_thread_captured_other_completes(self):
        from tests._helpers.concurrent import run_two_threads

        def boom():
            raise RuntimeError("from thread A")

        a, b = run_two_threads(boom, lambda: 42)
        self.assertFalse(a.ok)
        self.assertTrue(b.ok)
        self.assertIsInstance(a.exception, RuntimeError)
        self.assertEqual(str(a.exception), "from thread A")
        self.assertEqual(b.return_value, 42)

    def test_exception_in_both_captured_independently(self):
        from tests._helpers.concurrent import run_two_threads

        def boom_a():
            raise ValueError("A")

        def boom_b():
            raise KeyError("B")

        a, b = run_two_threads(boom_a, boom_b)
        self.assertFalse(a.ok)
        self.assertFalse(b.ok)
        self.assertIsInstance(a.exception, ValueError)
        self.assertIsInstance(b.exception, KeyError)

    def test_timeout_raises_timeouterror(self):
        """If either thread doesn't complete within ``timeout``, the
        helper must raise TimeoutError — never silently let the test
        process hang."""
        from tests._helpers.concurrent import run_two_threads

        def hang():
            time.sleep(2.0)

        with self.assertRaises(TimeoutError):
            run_two_threads(hang, lambda: 1, timeout=0.2)

    def test_barrier_synchronizes_start(self):
        """barrier=True should mean both threads cross the start
        line within a few ms of each other. We probe via shared
        mutable state — both threads append their start time, and
        the spread must be small even if function A would otherwise
        get a head start from being launched first."""
        from tests._helpers.concurrent import run_two_threads

        starts: list[float] = []
        starts_lock = __import__("threading").Lock()

        def fn_a():
            with starts_lock:
                starts.append(time.monotonic())
            time.sleep(0.05)
            return "a"

        def fn_b():
            with starts_lock:
                starts.append(time.monotonic())
            time.sleep(0.05)
            return "b"

        run_two_threads(fn_a, fn_b, barrier=True, timeout=2.0)
        self.assertEqual(len(starts), 2)
        spread = abs(starts[1] - starts[0])
        # Without a barrier, fn_a almost always starts ~milliseconds
        # before fn_b. With a barrier, the spread should be sub-10ms.
        self.assertLess(
            spread, 0.05,
            f"barrier did not synchronize start: spread={spread:.4f}s",
        )

    def test_barrier_false_does_not_block(self):
        """With barrier=False, the helper still works; threads just
        start in launch order without synchronization."""
        from tests._helpers.concurrent import run_two_threads

        a, b = run_two_threads(
            lambda: "x", lambda: "y", barrier=False, timeout=1.0,
        )
        self.assertEqual((a.return_value, b.return_value), ("x", "y"))


class Interleave(unittest.TestCase):
    """``Interleave`` lets a test force a specific step-by-step
    ordering between two threads — the precondition for testing
    most race-condition fixes deterministically."""

    def test_steps_complete_in_required_order(self):
        from tests._helpers.concurrent import Interleave, run_two_threads

        events = Interleave(n_steps=4)
        order: list[str] = []
        order_lock = __import__("threading").Lock()

        def add(label):
            with order_lock:
                order.append(label)

        def thread_a():
            events.wait(0)              # gate: B has started
            add("a1")
            events.step(1)              # signal: A did first action
            events.wait(2)              # gate: B did its middle
            add("a2")
            events.step(3)              # signal: A done

        def thread_b():
            events.step(0)              # I'm here
            add("b1")
            events.wait(1)              # gate: A did first
            add("b2")
            events.step(2)              # signal: B middle done
            events.wait(3)              # gate: A done

        run_two_threads(thread_a, thread_b, barrier=True, timeout=3.0)
        self.assertEqual(order, ["b1", "a1", "b2", "a2"])

    def test_wait_times_out_if_step_never_signaled(self):
        """If a test mis-wires its interleave (e.g., forgets a
        ``step(n)`` call), the ``wait(n)`` must time out rather
        than hang indefinitely."""
        from tests._helpers.concurrent import Interleave

        events = Interleave(n_steps=2)
        with self.assertRaises(TimeoutError):
            events.wait(0, timeout=0.2)

    def test_step_out_of_range_raises(self):
        from tests._helpers.concurrent import Interleave
        events = Interleave(n_steps=2)
        with self.assertRaises(IndexError):
            events.step(5)
        with self.assertRaises(IndexError):
            events.wait(-1)


class NoProductionImports(unittest.TestCase):
    """The helper module must not import anything from production
    code. A bug in core/ should not be able to break tests via the
    helper, and a helper change should never have a runtime effect."""

    def test_helper_module_has_no_production_imports(self):
        import ast
        helper_path = (
            Path(__file__).resolve().parent
            / "_helpers" / "concurrent.py"
        )
        tree = ast.parse(helper_path.read_text())
        forbidden_roots = {"core", "daemon", "skills", "memory"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    self.assertNotIn(
                        root, forbidden_roots,
                        f"helper imports {alias.name!r} — must "
                        f"not depend on production code",
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".", 1)[0]
                    self.assertNotIn(
                        root, forbidden_roots,
                        f"helper imports from {node.module!r} — "
                        f"must not depend on production code",
                    )


if __name__ == "__main__":
    unittest.main()
