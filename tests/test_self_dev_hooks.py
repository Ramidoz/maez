# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.self_dev_hooks — policy decisions + orchestrator.
All git and claude_tier calls are mocked so the tests are offline
and deterministic."""
from __future__ import annotations

import unittest
from unittest import mock


class _PolicyFixture(unittest.TestCase):
    """Shared fixture: fast valid SHA, pretend budget is healthy."""

    HEALTHY_BUDGET = {
        "claude": {
            "hourly_remaining": 8, "hourly_used": 2, "hourly_cap": 10,
            "daily_remaining": 25, "daily_used": 5, "daily_cap": 30,
        }
    }

    VALID_SHA = "abc123def4567890abc123def4567890abc123de"

    def _mock_ok_git(self, diff: str):
        """Build a side_effect function for _git() that returns
        `diff` for `show` calls and a resolved SHA for `rev-parse`."""
        def _inner(args, **kwargs):
            if args[0] == "rev-parse":
                return self.VALID_SHA + "\n"
            if args[0] == "show":
                return diff
            return ""
        return _inner


class DecideHappyPath(_PolicyFixture):
    def test_normal_small_commit_passes(self):
        from core import self_dev_hooks
        diff = (
            "diff --git a/core/foo.py b/core/foo.py\n"
            "+def x(): pass\n"
        )
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(diff),
        ), mock.patch("core.claude_tier.budget",
                         return_value=self.HEALTHY_BUDGET):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertTrue(d.should_review, d.reason)
        self.assertEqual(d.reason, "policy pass")
        self.assertGreater(d.diff_chars, 0)
        self.assertEqual(d.hourly_remaining, 8)


class DecideSkipCases(_PolicyFixture):
    def test_empty_diff_skips(self):
        from core import self_dev_hooks
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(""),
        ):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertFalse(d.should_review)
        self.assertIn("boring-only", d.reason.lower())

    def test_lockfile_only_diff_skips(self):
        """diff that only touches package-lock.json has zero
        significant size → skip.

        self-dev review on a063b35 (concern #43) fix: diffs used by
        `git show` include a full commit-header preamble (Author,
        Date, commit message) before the first `diff --git`. The
        old implementation counted those header chars as
        significant, which meant lockfile-only commits with any
        commit message > 0 chars (effectively all of them) silently
        exceeded the zero-significant threshold and DID fire a
        review. Test with a realistic git-show preamble to regress
        the bug.
        """
        from core import self_dev_hooks
        diff = (
            "commit abc123def4567890abc123def4567890abc123de\n"
            "Author: Rohit Ananthan <rohit@example.com>\n"
            "Date:   Wed Apr 22 18:00:00 2026 -0500\n"
            "\n"
            "    chore: bump lockfile\n"
            "\n"
            "    keeps dependencies fresh.\n"
            "\n"
            "diff --git a/package-lock.json b/package-lock.json\n"
            "+a lot of lockfile churn here\n"
            "+more of it\n"
        )
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(diff),
        ):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertFalse(d.should_review,
                         f"lockfile-only commit with commit-header "
                         f"preamble must NOT trigger review (pre-fix "
                         f"bug). reason: {d.reason}")
        self.assertIn("boring-only", d.reason.lower())

    def test_lockfile_with_non_boring_file_still_fires(self):
        """Sanity: if a commit touches BOTH a lockfile AND a real
        Python file, the non-boring diff content counts and the
        review should fire. Regresses the over-correction risk of
        the boring-filter fix."""
        from core import self_dev_hooks
        diff = (
            "commit abc123def4567890abc123def4567890abc123de\n"
            "Author: R <r@example.com>\n"
            "Date:   Wed Apr 22 18:00:00 2026 -0500\n"
            "\n"
            "    feat: actual change + lockfile bump\n"
            "\n"
            "diff --git a/package-lock.json b/package-lock.json\n"
            "+lockfile junk\n"
            "diff --git a/core/real.py b/core/real.py\n"
            "+def actual_function():\n"
            "+    return 1\n"
        )
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(diff),
        ), mock.patch(
            "core.claude_tier.budget",
            return_value={"claude": self.HEALTHY_BUDGET["claude"]},
        ):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertTrue(d.should_review,
                         f"commit with non-boring Python changes "
                         f"must trigger review even if it also "
                         f"touches a lockfile. reason: {d.reason}")

    def test_oversized_diff_skips(self):
        from core import self_dev_hooks
        big_diff = (
            "diff --git a/core/huge.py b/core/huge.py\n"
            + ("+" + "x" * 100 + "\n") * 2000  # 200k+ chars
        )
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(big_diff),
        ), mock.patch("core.claude_tier.budget",
                         return_value=self.HEALTHY_BUDGET):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertFalse(d.should_review)
        self.assertIn("cap", d.reason.lower())

    def test_low_hourly_budget_yields(self):
        from core import self_dev_hooks
        diff = "diff --git a/core/x.py b/core/x.py\n+foo\n"
        low_budget = {
            "claude": {
                "hourly_remaining": 1, "hourly_used": 9, "hourly_cap": 10,
                "daily_remaining": 20, "daily_used": 10, "daily_cap": 30,
            }
        }
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(diff),
        ), mock.patch("core.claude_tier.budget", return_value=low_budget):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertFalse(d.should_review)
        self.assertIn("yield", d.reason.lower())
        self.assertIn("hourly", d.reason.lower())

    def test_low_daily_budget_yields(self):
        from core import self_dev_hooks
        diff = "diff --git a/core/x.py b/core/x.py\n+foo\n"
        low_budget = {
            "claude": {
                "hourly_remaining": 10, "hourly_used": 0, "hourly_cap": 10,
                "daily_remaining": 2, "daily_used": 28, "daily_cap": 30,
            }
        }
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(diff),
        ), mock.patch("core.claude_tier.budget", return_value=low_budget):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertFalse(d.should_review)
        self.assertIn("yield", d.reason.lower())
        self.assertIn("daily", d.reason.lower())

    def test_proxy_unreachable_fails_closed(self):
        """Any exception from the budget probe → skip. We never
        fire on an unknowable budget."""
        from core import self_dev_hooks
        diff = "diff --git a/core/x.py b/core/x.py\n+foo\n"
        with mock.patch.object(
            self_dev_hooks, "_git",
            side_effect=self._mock_ok_git(diff),
        ), mock.patch(
            "core.claude_tier.budget",
            side_effect=RuntimeError("proxy down"),
        ):
            d = self_dev_hooks.decide(self.VALID_SHA)
        self.assertFalse(d.should_review)
        self.assertIn("proxy", d.reason.lower())

    def test_unresolved_sha_skips(self):
        from core import self_dev_hooks
        def _git(args, **_):
            raise RuntimeError("bad ref")
        with mock.patch.object(self_dev_hooks, "_git", side_effect=_git):
            d = self_dev_hooks.decide("notasha")
        self.assertFalse(d.should_review)
        self.assertIn("unresolved", d.reason.lower())


class RunPostCommitOrchestrator(_PolicyFixture):
    def test_skip_does_not_call_review(self):
        from core import self_dev_hooks
        with mock.patch.object(
            self_dev_hooks, "decide",
            return_value=self_dev_hooks.PolicyDecision(
                should_review=False, reason="test skip",
            ),
        ), mock.patch("core.self_dev.review") as m_review:
            rc = self_dev_hooks.run_post_commit(self.VALID_SHA)
        self.assertEqual(rc, 0)
        m_review.assert_not_called()

    def test_review_called_when_policy_passes(self):
        from core import self_dev_hooks
        from core.self_dev import Concern, ReviewResult

        fake_result = ReviewResult(
            target_ref=self.VALID_SHA,
            diff_size_chars=500,
            overall="fine",
            concerns=[Concern(file="x", line=1, severity="minor", text="t")],
            model_used="sonnet",
            input_tokens=10, output_tokens=20,
        )
        with mock.patch.object(
            self_dev_hooks, "decide",
            return_value=self_dev_hooks.PolicyDecision(
                should_review=True, reason="pass", diff_chars=500,
                hourly_remaining=5, daily_remaining=20,
            ),
        ), mock.patch("core.self_dev.review",
                         return_value=fake_result) as m_review:
            rc = self_dev_hooks.run_post_commit(self.VALID_SHA)
        self.assertEqual(rc, 0)
        m_review.assert_called_once()
        call_kwargs = m_review.call_args.kwargs
        self.assertEqual(call_kwargs["target_ref"], self.VALID_SHA)
        self.assertEqual(call_kwargs["caller"], "self_dev/post-commit")
        self.assertTrue(call_kwargs["persist"])

    def test_review_exception_swallowed(self):
        """A backend failure during review MUST NOT kill the hook —
        the hook is backgrounded but still should exit cleanly for
        the journal record."""
        from core import self_dev_hooks
        with mock.patch.object(
            self_dev_hooks, "decide",
            return_value=self_dev_hooks.PolicyDecision(
                should_review=True, reason="pass",
            ),
        ), mock.patch(
            "core.self_dev.review", side_effect=RuntimeError("boom"),
        ):
            rc = self_dev_hooks.run_post_commit(self.VALID_SHA)
        self.assertEqual(rc, 0)  # exits clean


class ProactiveNotification(_PolicyFixture):
    """_maybe_notify fires send_dev when a review produces
    notify-worthy concerns, stays silent otherwise."""

    def _result(self, concerns):
        from core.self_dev import ReviewResult
        return ReviewResult(
            target_ref="abc123",
            diff_size_chars=100,
            overall="test",
            concerns=concerns,
            model_used="sonnet",
            input_tokens=1, output_tokens=1,
        )

    def test_no_worthy_concerns_does_not_notify(self):
        from core import self_dev_hooks
        from core.self_dev import Concern
        with mock.patch("skills.dev_notifier.send_dev") as m_send:
            self_dev_hooks._maybe_notify(
                self.VALID_SHA,
                self._result([
                    Concern(file="a", line=1, severity="nit", text="n"),
                    Concern(file="a", line=2, severity="minor", text="m"),
                ]),
            )
        m_send.assert_not_called()

    def test_blocker_triggers_notification(self):
        from core import self_dev_hooks
        from core.self_dev import Concern
        with mock.patch("skills.dev_notifier.send_dev") as m_send:
            self_dev_hooks._maybe_notify(
                self.VALID_SHA,
                self._result([
                    Concern(file="core/a.py", line=42, severity="blocker",
                             text="null pointer",
                             suggestion="add a guard"),
                ]),
            )
        m_send.assert_called_once()
        msg = m_send.call_args.args[0]
        self.assertIn("1 concern(s)", msg)
        self.assertIn("blocker", msg)
        self.assertIn(self.VALID_SHA[:12], msg)
        self.assertIn("core/a.py:42", msg)
        self.assertIn("null pointer", msg)
        self.assertIn("add a guard", msg)

    def test_many_concerns_truncated_with_hint(self):
        from core import self_dev_hooks
        from core.self_dev import Concern
        many = [
            Concern(file=f"x{i}.py", line=i, severity="major",
                     text=f"issue {i}")
            for i in range(7)
        ]
        with mock.patch("skills.dev_notifier.send_dev") as m_send:
            self_dev_hooks._maybe_notify(
                self.VALID_SHA, self._result(many),
            )
        msg = m_send.call_args.args[0]
        self.assertIn("7 concern(s)", msg)
        # Only first 3 concerns shown verbatim
        self.assertIn("x0.py", msg)
        self.assertIn("x1.py", msg)
        self.assertIn("x2.py", msg)
        self.assertNotIn("x3.py", msg)  # not in the excerpt
        self.assertIn("and 4 more", msg)

    def test_notify_failure_is_swallowed(self):
        """send_dev exceptions must not propagate — the hook is
        already backgrounded and must exit clean."""
        from core import self_dev_hooks
        from core.self_dev import Concern
        with mock.patch("skills.dev_notifier.send_dev",
                         side_effect=RuntimeError("bot down")):
            # Must not raise
            self_dev_hooks._maybe_notify(
                self.VALID_SHA,
                self._result([
                    Concern(file="a", line=1, severity="blocker", text="t"),
                ]),
            )


class HookScriptRendering(unittest.TestCase):
    def test_render_hook_contains_expected_invocation(self):
        from core.self_dev_hooks import render_hook_script
        script = render_hook_script(
            python_bin="/test/python",
            repo_root="/test/repo",
            log_path="/test/log",
        )
        self.assertIn("#!/bin/sh", script)
        self.assertIn("core.self_dev_hooks run", script)
        self.assertIn("/test/python", script)
        self.assertIn("/test/repo", script)
        self.assertIn("/test/log", script)
        # Must end with `exit 0` so the hook doesn't block the commit
        # even if the backgrounded invocation syntax fails parsing on
        # some obscure shell. Defense-in-depth.
        self.assertIn("exit 0", script)
        # Must disown so the background job survives shell exit.
        self.assertIn("disown", script)


if __name__ == "__main__":
    unittest.main()
