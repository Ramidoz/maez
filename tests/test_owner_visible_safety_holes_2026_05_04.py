# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the owner-visible safety holes the
2026-05-04 15-agent audit surfaced (T1.6 + T1.10):

  T1.6  fast_backend_router: when policy enforces LOCAL-only and
        local is unavailable, BackendSelection must carry
        policy_denied=True so the retry path can refuse to fall
        back to cloud. Without this, `maez_local_only` scope
        would silently leak to cloud.

  T1.10 action_classifier: SELF_MODIFICATION classification must
        fire on:
          - relative-path editor invocations from the maez root
            (`vim daemon/maez_daemon.py`)
          - sed -i in-place edits of soul / brain / safety files
          - dd writes targeting maez surfaces
          - editor commands against newly-enumerated core surfaces
            (core/safety/, core/decision/, core/brain/brain_loop,
            etc.)

(T1.13 has its own dedicated regression guard at
tests/test_telegram_reply_audit_coverage.py.)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class T1_6_PolicyDeniedOnLocalOnlyUnavailable(unittest.TestCase):
    """REGRESSION GUARD for T1.6: fast_backend_router must set
    policy_denied=True when LOCAL is forbidden by policy AND local
    backend is unavailable. The retry path uses this flag to
    distinguish 'policy refused' from 'transient unavailable'.
    Privacy-violation hole if not set."""

    def test_policy_local_with_unavailable_local_sets_policy_denied(self):
        from core.routing import fast_backend_router as fbr

        class _StubBackend:
            name = "local-stub"
            def is_available(self):
                return False

        decision = fbr.PolicyDecision(
            trust_scope="owner",
            rule_fired="maez_local_only",
            requested_policy=fbr.POLICY_LOCAL,
            effective_policy=fbr.POLICY_LOCAL,
            allow_cloud=False,
            downgraded=False,
        )

        # Stub local & cloud factories
        original_local = fbr._local
        original_cloud = fbr._cloud
        try:
            fbr._local = lambda: _StubBackend()
            fbr._cloud = lambda: _StubBackend()
            sel = fbr.select_backend(decision)
        finally:
            fbr._local = original_local
            fbr._cloud = original_cloud

        self.assertEqual(sel.name, "none")
        self.assertTrue(
            sel.policy_denied,
            "POLICY_LOCAL + local-unavailable must set "
            "policy_denied=True to prevent silent cloud fallback",
        )

    def test_source_level_policy_denied_in_local_branch(self):
        """Source-level: the LOCAL-unavailable branch in
        fast_backend_router.select_backend must set
        policy_denied=True. AST-style check pins the contract so a
        future refactor can't drop it."""
        path = REPO / "core" / "routing" / "fast_backend_router.py"
        src = path.read_text()
        # Find the section between 'if eff == POLICY_LOCAL:' and
        # the next 'if eff == POLICY_CLOUD:' — that's the
        # POLICY_LOCAL branch.
        local_start = src.index("if eff == POLICY_LOCAL:")
        local_end = src.index("if eff == POLICY_CLOUD:", local_start)
        local_branch = src[local_start:local_end]
        self.assertIn(
            "policy_denied=True", local_branch,
            "fast_backend_router POLICY_LOCAL branch must set "
            "policy_denied=True on the local-unavailable return",
        )


class T1_10_SelfModClassifierExpanded(unittest.TestCase):
    """REGRESSION GUARD for T1.10: action_classifier SELF_MODIFICATION
    must fire on the patterns the audit identified as bypass risks."""

    def _classify(self, cmd: str):
        from core.actions.action_classifier import classify_command
        return classify_command(cmd)

    def test_relative_path_editor_invocation(self):
        """`vim daemon/maez_daemon.py` from inside maez root —
        the path is relative but still touches a brain file."""
        result = self._classify("vim daemon/maez_daemon.py")
        self.assertEqual(
            result.category.value, "SELF_MODIFICATION",
            f"got {result.category}, reason={result.reason}",
        )

    def test_nano_relative_brain_path(self):
        result = self._classify("nano core/brain/brain_loop.py")
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_sed_inplace_on_safety_file(self):
        result = self._classify(
            "sed -i 's/foo/bar/' core/safety/canaries.py"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_dd_targeting_soul(self):
        result = self._classify(
            "dd if=/tmp/x of=/home/rohit/maez/config/soul.md"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_editor_against_decision_pipeline(self):
        result = self._classify(
            "code core/decision/decision_pipeline.py"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_editor_against_action_engine_relative(self):
        result = self._classify(
            "vi core/actions/action_engine.py"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_editor_against_self_dev_subpackage(self):
        result = self._classify(
            "nano core/self_dev/scheduler.py"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_editor_against_identity_config(self):
        result = self._classify(
            "vim config/identity.yaml"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_existing_absolute_path_still_works(self):
        """REGRESSION GUARD: the original test from the codebase
        (line 632 of action_classifier.py self-test) must still pass."""
        result = self._classify(
            "vim /home/rohit/maez/daemon/maez_daemon.py"
        )
        self.assertEqual(result.category.value, "SELF_MODIFICATION")

    def test_unrelated_editor_command_does_not_falsely_fire(self):
        """A `vim /tmp/notes.txt` is NOT self-modification. False
        positives would be annoying without being load-bearing
        (the dialog is a soft-gate, not a hard block) but worth
        pinning."""
        result = self._classify("vim /tmp/notes.txt")
        # Could be CODE_EXECUTION or SHELL_OBSERVATION; just must
        # NOT be SELF_MODIFICATION.
        self.assertNotEqual(
            result.category.value, "SELF_MODIFICATION",
            f"vim /tmp/notes.txt false-positive: {result.reason}",
        )


if __name__ == "__main__":
    unittest.main()
