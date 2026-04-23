# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.self_dev_scheduler — candidate enumeration, pick
policy, run orchestrator. All backend and filesystem access is mocked
so the tests are offline."""
from __future__ import annotations

import unittest
from unittest import mock


class SkipPatterns(unittest.TestCase):
    def test_default_skips_init_and_tests(self):
        from core.self_dev_scheduler import _matches_any, _skip_globs
        sk = _skip_globs()
        self.assertTrue(_matches_any("core/__init__.py", sk))
        self.assertTrue(_matches_any("tests/test_foo.py", sk))
        self.assertTrue(_matches_any("training/x.py", sk))
        self.assertTrue(_matches_any("web/ui.py", sk))
        self.assertFalse(_matches_any("core/self_dev.py", sk))
        self.assertFalse(_matches_any("memory/memory_manager.py", sk))


class Pick(unittest.TestCase):
    def _mock_age(self, ages: dict[str, float | None]):
        """Return a side_effect function mapping paths to ages."""
        def _inner(rel_path):
            return ages.get(rel_path)
        return _inner

    def test_never_reviewed_wins_over_recent(self):
        from core import self_dev_scheduler as sch
        cands = ["a.py", "b.py", "c.py"]
        # a reviewed 200h ago (>168h min), b reviewed 10h ago (recent),
        # c never reviewed → c should win
        ages = {"a.py": 200 * 3600, "b.py": 10 * 3600, "c.py": None}
        with mock.patch.object(sch, "_age_of_last_review",
                                side_effect=self._mock_age(ages)):
            picked = sch.pick_next(cands)
        self.assertEqual(picked, "c.py")

    def test_recent_candidates_all_skipped(self):
        from core import self_dev_scheduler as sch
        cands = ["a.py", "b.py"]
        # Both reviewed within min age → nothing to do
        ages = {"a.py": 10 * 3600, "b.py": 20 * 3600}
        with mock.patch.object(sch, "_age_of_last_review",
                                side_effect=self._mock_age(ages)):
            picked = sch.pick_next(cands)
        self.assertIsNone(picked)

    def test_oldest_wins_among_eligible(self):
        from core import self_dev_scheduler as sch
        cands = ["a.py", "b.py", "c.py"]
        # All > min age, c is oldest
        ages = {"a.py": 200 * 3600, "b.py": 300 * 3600, "c.py": 400 * 3600}
        with mock.patch.object(sch, "_age_of_last_review",
                                side_effect=self._mock_age(ages)):
            picked = sch.pick_next(cands)
        self.assertEqual(picked, "c.py")

    def test_empty_candidates_returns_none(self):
        from core import self_dev_scheduler as sch
        self.assertIsNone(sch.pick_next([]))

    def test_deterministic_tiebreak_by_path(self):
        from core import self_dev_scheduler as sch
        cands = ["z.py", "a.py", "m.py"]
        # All never reviewed (inf age). Sort should break the tie via
        # path name so the pick is reproducible.
        ages = {"z.py": None, "a.py": None, "m.py": None}
        with mock.patch.object(sch, "_age_of_last_review",
                                side_effect=self._mock_age(ages)):
            picked = sch.pick_next(cands)
        self.assertEqual(picked, "a.py")


class BudgetGate(unittest.TestCase):
    """run_once() must yield to owner when Claude budget is low."""

    def _patch_candidates(self, paths):
        from core import self_dev_scheduler as sch
        return mock.patch.object(
            sch, "enumerate_candidates", return_value=paths,
        )

    def _patch_age(self):
        from core import self_dev_scheduler as sch
        # All never-reviewed so pick_next always selects something.
        return mock.patch.object(
            sch, "_age_of_last_review", return_value=None,
        )

    def _patch_budget(self, claude_budget):
        return mock.patch(
            "core.claude_tier.budget",
            return_value={"claude": claude_budget},
        )

    def test_yields_when_hourly_low(self):
        from core import self_dev_scheduler as sch
        low = {
            "hourly_remaining": 2, "hourly_used": 8, "hourly_cap": 10,
            "daily_remaining": 20, "daily_used": 10, "daily_cap": 30,
        }
        with self._patch_candidates(["core/foo.py"]), \
             self._patch_age(), \
             self._patch_budget(low), \
             mock.patch("core.self_dev.review_module") as m_review:
            rc = sch.run_once()
        self.assertEqual(rc, 0)
        m_review.assert_not_called()  # yielded

    def test_yields_when_daily_low(self):
        from core import self_dev_scheduler as sch
        low = {
            "hourly_remaining": 10, "hourly_used": 0, "hourly_cap": 10,
            "daily_remaining": 5, "daily_used": 25, "daily_cap": 30,
        }
        with self._patch_candidates(["core/foo.py"]), \
             self._patch_age(), \
             self._patch_budget(low), \
             mock.patch("core.self_dev.review_module") as m_review:
            rc = sch.run_once()
        self.assertEqual(rc, 0)
        m_review.assert_not_called()

    def test_runs_when_budget_healthy(self):
        from core import self_dev_scheduler as sch
        from core.self_dev import ReviewResult

        healthy = {
            "hourly_remaining": 10, "hourly_used": 0, "hourly_cap": 10,
            "daily_remaining": 25, "daily_used": 5, "daily_cap": 30,
        }
        fake_result = ReviewResult(
            target_ref="module:core/foo.py", diff_size_chars=1000,
            overall="clean", concerns=[], model_used="sonnet",
            input_tokens=10, output_tokens=20,
        )
        with self._patch_candidates(["core/foo.py"]), \
             self._patch_age(), \
             self._patch_budget(healthy), \
             mock.patch("core.self_dev.review_module",
                         return_value=fake_result) as m_review:
            rc = sch.run_once()
        self.assertEqual(rc, 0)
        m_review.assert_called_once()
        # Caller label flows through for trajectory-log slicing
        kwargs = m_review.call_args.kwargs
        self.assertEqual(kwargs["caller"], "self_dev/scheduled")


class FailSafe(unittest.TestCase):
    def test_review_failure_does_not_raise(self):
        from core import self_dev_scheduler as sch
        healthy = {
            "hourly_remaining": 10, "hourly_used": 0, "hourly_cap": 10,
            "daily_remaining": 25, "daily_used": 5, "daily_cap": 30,
        }
        with mock.patch.object(sch, "enumerate_candidates",
                                return_value=["core/foo.py"]), \
             mock.patch.object(sch, "_age_of_last_review", return_value=None), \
             mock.patch("core.claude_tier.budget",
                         return_value={"claude": healthy}), \
             mock.patch("core.self_dev.review_module",
                         side_effect=RuntimeError("backend down")):
            # MUST NOT RAISE
            rc = sch.run_once()
        self.assertEqual(rc, 0)

    def test_empty_candidate_set(self):
        from core import self_dev_scheduler as sch
        with mock.patch.object(sch, "enumerate_candidates", return_value=[]):
            rc = sch.run_once()
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
