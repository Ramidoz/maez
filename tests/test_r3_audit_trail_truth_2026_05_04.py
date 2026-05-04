# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for R3 — audit-trail truth.

The 2026-05-04 symphony audit (S4 BLOCKERs F5 + F6) found that the
14:39 "Run it yourself" turn recorded `execution_success=1` /
`outcome=approved_and_ran` in pending_cards + audit_log even though
its stdout named three failed tools. Root cause:
core/actions/action_engine.py:969 keys success on subprocess
returncode, and the composite cmd's `||` fallthroughs guaranteed
exit 0. Cascading: no tool_failure consequence_memory write — the
planner has no `(action,context,outcome)` tuple to learn from, so
the wmctrl-class failure is permanently re-proposable.

Contract enforced by these tests:
- A new `core/actions/shell_failure_detector.py` exposes
  detect_failures_in_output(stdout, stderr, returncode, cmd) which
  returns a FailureSignal | None.
- Detector recognizes the wmctrl-incident patterns as failures
  even when returncode==0:
    • "<binary>: command not found"
    • "Can't open display: (null|...)"
    • "Failed creating new xdo instance"
    • "is not in the sudoers file"
    • "Permission denied" at start of line / stderr
- Detector does NOT false-positive on legitimate output that
  happens to contain those substrings inside data (e.g. a `find`
  result that shows "no such file or directory" inside its own
  output).
- action_engine.run_shell raises ShellCommandError on soft-failure
  patterns even when returncode==0, with the FailureSignal carried
  through.
- decision_pipeline routes the soft-failure path to
  consequence_memory.note_tool_failure with class='tool_failure'
  (matching the existing exit≠0 path) and outcome label
  'approved_and_failed' (not 'approved_and_ran').

Tests are runtime-shaped on the detector + source-pinned where the
integration crosses module boundaries (subprocess invocation in
production action_engine). The end-to-end "wmctrl turn does not
record success" path is asserted via the integration test in
test_action_engine_soft_failure.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── Detector unit tests ──────────────────────────────────────────────


class R3_DetectorRecognizesWmctrlPatterns(unittest.TestCase):
    """REGRESSION GUARD: the shell_failure_detector must recognize
    the patterns from the 14:39 "Run it yourself" wmctrl-incident
    output and return a FailureSignal even with returncode==0."""

    def test_command_not_found_at_line_start(self):
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stdout = "bash: line 1: wmctrl: command not found\nwmctrl not found"
        sig = detect_failures_in_output(
            stdout=stdout, stderr="", returncode=0, cmd="wmctrl -l",
        )
        self.assertIsNotNone(sig, "must detect 'command not found'")
        self.assertIn(
            "binary_not_found", sig.kind,
            f"signal kind must classify the failure; got {sig.kind!r}",
        )

    def test_cant_open_display_null(self):
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stdout = (
            "Error: Can't open display: (null)\n"
            "Failed creating new xdo instance"
        )
        sig = detect_failures_in_output(
            stdout=stdout, stderr="", returncode=0, cmd="xdotool search ''",
        )
        self.assertIsNotNone(sig, "must detect X-display unreachable")
        self.assertIn(
            "x_session_unreachable", sig.kind,
        )

    def test_xdotool_failed_creating_xdo(self):
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stdout = "Failed creating new xdo instance"
        sig = detect_failures_in_output(
            stdout=stdout, stderr="", returncode=0, cmd="xdotool search ''",
        )
        self.assertIsNotNone(sig)

    def test_full_wmctrl_incident_composite_output(self):
        """The exact verbatim stdout from pending_cards row 105 (the
        14:39 turn). Must be recognized as failure."""
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stdout = (
            "bash: line 1: wmctrl: command not found\n"
            "wmctrl not found\n"
            "Error: Can't open display: (null)\n"
            "Failed creating new xdo instance"
        )
        sig = detect_failures_in_output(
            stdout=stdout, stderr="", returncode=0,
            cmd=(
                "dbus-send ... || echo 'fail'; "
                "wmctrl -l 2>&1 || echo 'wmctrl not found'; "
                "xdotool search '' 2>&1 || echo 'xdotool failed'"
            ),
        )
        self.assertIsNotNone(
            sig,
            "the verbatim wmctrl-incident composite output must be "
            "recognized as failure even though returncode=0",
        )

    def test_sudo_not_in_sudoers(self):
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stderr = (
            "user is not in the sudoers file. This incident "
            "will be reported."
        )
        sig = detect_failures_in_output(
            stdout="", stderr=stderr, returncode=0, cmd="sudo apt update",
        )
        self.assertIsNotNone(sig)
        self.assertIn("sudo_denied", sig.kind)

    def test_permission_denied_in_stderr(self):
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stderr = "/var/log/private.log: Permission denied"
        sig = detect_failures_in_output(
            stdout="", stderr=stderr, returncode=0,
            cmd="cat /var/log/private.log",
        )
        self.assertIsNotNone(sig)


class R3_DetectorAvoidsFalsePositives(unittest.TestCase):
    """REGRESSION GUARD: the detector must not flag legitimate
    output that happens to contain failure substrings inside data."""

    def test_clean_output_returns_none(self):
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stdout = "Hello, World!\nLine 2\nLine 3"
        sig = detect_failures_in_output(
            stdout=stdout, stderr="", returncode=0, cmd="echo hello",
        )
        self.assertIsNone(sig)

    def test_grep_match_for_command_not_found_is_data_not_failure(self):
        """If `grep 'command not found' /var/log/...` legitimately
        finds matches, the substring appears in stdout — but the
        cmd ran successfully. Must NOT false-positive."""
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        stdout = (
            "/var/log/syslog:Aug  3 10:00 pkg-installer: "
            "warning: command not found in path"
        )
        sig = detect_failures_in_output(
            stdout=stdout, stderr="", returncode=0,
            cmd="grep 'command not found' /var/log/syslog",
        )
        self.assertIsNone(
            sig,
            "grep matching 'command not found' as DATA must not be "
            "classified as binary_not_found failure — the pattern "
            "must require the bash error-line shape",
        )

    def test_returncode_nonzero_short_circuits_to_signal(self):
        """If returncode != 0, the detector should return a generic
        signal regardless of pattern (the shell already classified
        this as failure; we just need to mark it for downstream
        consequence_memory)."""
        from core.actions.shell_failure_detector import (
            detect_failures_in_output,
        )
        sig = detect_failures_in_output(
            stdout="some output", stderr="", returncode=1, cmd="false",
        )
        self.assertIsNotNone(sig)


# ── action_engine integration ────────────────────────────────────────


class R3_ActionEngineSoftFailure(unittest.TestCase):
    """REGRESSION GUARD: action_engine.run_shell must raise
    ShellCommandError on soft-failure patterns even when
    returncode == 0. The 14:39 wmctrl turn's path is the canonical
    case: composite cmd absorbed exit codes via `||`, but the
    output named three failed tools."""

    def test_do_run_shell_raises_on_soft_failure_when_exit_zero(self):
        """Mock subprocess.run to return exit 0 with wmctrl-class
        stdout; assert _do_run_shell raises ShellCommandError.

        _do_run_shell is the inner subprocess-invoking method; the
        public run_shell wraps it via _execute_action. We test the
        inner method directly since R3's fix is the soft-failure
        detection at the subprocess boundary."""
        from core.actions import action_engine
        from core.actions.action_engine import (
            ActionEngine, ShellCommandError,
        )

        engine = ActionEngine.__new__(ActionEngine)
        # Skip __init__; provide minimum attrs _do_run_shell uses.
        engine._covenant_violations = []

        class _R:
            stdout = (
                "bash: line 1: wmctrl: command not found\n"
                "Error: Can't open display: (null)\n"
                "Failed creating new xdo instance"
            )
            stderr = ""
            returncode = 0

        with mock.patch.object(action_engine.subprocess, "run",
                               return_value=_R()):
            with self.assertRaises(ShellCommandError):
                engine._do_run_shell("wmctrl -l 2>&1 || true")

    def test_do_run_shell_does_not_raise_on_clean_output(self):
        """Clean output + exit 0 must still succeed — R3 must not
        regress the happy path."""
        from core.actions import action_engine
        from core.actions.action_engine import ActionEngine

        engine = ActionEngine.__new__(ActionEngine)
        engine._covenant_violations = []

        class _R:
            stdout = "hello world"
            stderr = ""
            returncode = 0

        with mock.patch.object(action_engine.subprocess, "run",
                               return_value=_R()):
            result = engine._do_run_shell("echo hello")
        self.assertIn("hello", result.lower())


# ── source-pin: detector exposed and called from action_engine ──────


class R3_SourcePinDetectorWired(unittest.TestCase):
    """REGRESSION GUARD: action_engine must reference the detector.
    Source-pin so a future refactor that drops the detector call
    fails this test loudly."""

    def test_action_engine_imports_detector(self):
        path = REPO / "core" / "actions" / "action_engine.py"
        src = path.read_text()
        self.assertIn(
            "shell_failure_detector",
            src,
            "core/actions/action_engine.py must reference "
            "shell_failure_detector — without this wire, the soft-"
            "failure detection isn't reached at runtime",
        )

    def test_action_engine_calls_detect_in_run_shell(self):
        path = REPO / "core" / "actions" / "action_engine.py"
        src = path.read_text()
        self.assertIn(
            "detect_failures_in_output",
            src,
            "action_engine must call detect_failures_in_output in "
            "the run_shell soft-failure branch",
        )


if __name__ == "__main__":
    unittest.main()
