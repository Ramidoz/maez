# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""shell_failure_detector.py — recognize tool-failure patterns in
shell command output even when the subprocess returncode is 0.

R3 from the 2026-05-04 symphony audit. The 14:39 "Run it yourself"
turn (S4 BLOCKERs F5 + F6) demonstrated that a composite shell
command with `||` fallthroughs absorbs every individual tool
failure into exit 0. Today's action_engine keys success on
`returncode != 0`, so:

  - pending_cards records `execution_success=1` for a turn whose
    stdout names three failed tools.
  - audit_log records `outcome=approved_and_ran` (it should be
    `approved_and_failed`).
  - consequence_memory writes nothing — the planner can re-propose
    the same wmctrl/xdotool combo indefinitely with no learning
    signal.

This module closes that gap. It scans (stdout, stderr, returncode,
cmd) for unambiguous tool-failure markers — patterns that signify
the COMMAND ITSELF failed rather than data-level matches. Conservative
by design: false positives degrade the action-engine's success path
and are worse than missing a long-tail failure shape. The patterns
are anchored (line-start, error-prefix shapes) so a `grep 'command
not found' /var/log/...` legitimately finding the substring inside
data does NOT trip the detector.

Public API:
  detect_failures_in_output(stdout, stderr, returncode, cmd)
      -> FailureSignal | None

The signal carries:
  - .kind:  one of {"binary_not_found", "x_session_unreachable",
                    "sudo_denied", "permission_denied",
                    "nonzero_exit"} (extensible)
  - .marker: the exact substring matched (for telemetry / consequence
             memory)
  - .source: "stdout" or "stderr"

Caller (action_engine.run_shell) raises ShellCommandError carrying
the signal so decision_pipeline / consequence_memory write the
right outcome label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FailureSignal:
    """A detected tool-failure pattern in shell output.

    Carries enough context that downstream telemetry
    (consequence_memory, audit_log, cockpit) can attribute the
    failure to a specific class without re-scanning the output."""
    kind: str
    marker: str
    source: str  # "stdout" | "stderr" | "returncode"


# Pattern definitions — each is (compiled_regex, kind). Patterns are
# ANCHORED to the bash error-line shape (start-of-line, optional
# prefix like "bash: line N:" or a path:lineno:) so data-level matches
# inside `grep` output don't trip them.
#
# REGEX SHAPES the patterns require:
#   - "command not found" must follow a binary name + ": " at
#     line-start OR after a "bash: line N:" prefix. Example:
#       "bash: line 1: wmctrl: command not found"
#       "wmctrl: command not found"
#   - "Can't open display" / "Failed creating new xdo" must appear
#     anywhere — these are unambiguous X-session failure markers
#     emitted by xdotool / xrandr / etc. and don't appear in
#     legitimate data.
#   - "is not in the sudoers file" / "must be a member of" are sudo
#     refusal markers — unambiguous.

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Binary-not-found patterns. Two distinct shapes — both must
    # match because bash emits both forms depending on context.
    #
    # Shape 1: "bash: line N: <name>: command not found"
    #          (composite cmd via `bash -c`, the wmctrl-incident shape)
    # Shape 2: "/usr/bin/<bin>: command not found"
    #          (path-prefixed; some shells / wrappers emit this)
    # Shape 3: "<bin>: command not found"
    #          (bare — what e.g. `wmctrl -l` produces directly when
    #           wmctrl isn't on PATH and bash didn't add a `bash:
    #           line N:` prefix)
    #
    # All three are anchored at line-start AND require `command not
    # found` to be at the line's terminal position so a `grep` /
    # `cat` finding the substring inside data does NOT trip. The
    # bare shape (#3) requires the line to start with a binary-name
    # word (\w + [\w.-]*) so a timestamp-prefixed log line
    # "2024-05-04 wmctrl: command not found" doesn't match.
    (
        re.compile(
            r"(?m)^bash:\s+line\s+\d+:\s+[\w./-]+:\s+command not found\s*$",
        ),
        "binary_not_found",
    ),
    (
        re.compile(
            r"(?m)^/[\w./-]+:\s+command not found\s*$",
        ),
        "binary_not_found",
    ),
    (
        re.compile(
            r"(?m)^[\w][\w.-]*:\s+command not found\s*$",
        ),
        "binary_not_found",
    ),
    # X session unreachable — xdotool / xrandr / xprop emit this
    # very specific message. Not data-shaped.
    (
        re.compile(r"Error:\s*Can't open display:", re.IGNORECASE),
        "x_session_unreachable",
    ),
    (
        re.compile(r"Failed creating new xdo instance"),
        "x_session_unreachable",
    ),
    # Sudo refusal — unambiguous.
    (
        re.compile(r"is not in the sudoers file", re.IGNORECASE),
        "sudo_denied",
    ),
    (
        re.compile(r"sudo:\s+a password is required", re.IGNORECASE),
        "sudo_denied",
    ),
    # Permission denied — must be at line-start to avoid matching
    # legitimate `find` output or man-page text. The `(?m)^` anchors
    # to the start of any line; combined with the "Permission
    # denied" terminal phrase, this catches `cat /var/log/x:
    # Permission denied` shape and similar.
    (
        re.compile(
            r"(?m)^(?:[\w./-]+:\s+|cat:\s+|ls:\s+|cp:\s+|mv:\s+|rm:\s+)?"
            r"[^:\n]*:\s+Permission denied\s*$",
        ),
        "permission_denied",
    ),
]


def detect_failures_in_output(
    *,
    stdout: str,
    stderr: str,
    returncode: int,
    cmd: str,  # noqa: ARG001 — kept for telemetry shape; unused today
) -> FailureSignal | None:
    """Scan shell output for tool-failure markers.

    Returns a FailureSignal on first match, or None if no failure
    pattern matched and returncode == 0. If returncode != 0 we
    short-circuit to a generic 'nonzero_exit' signal so downstream
    consequence_memory still gets a row even when the existing
    returncode-based path already raised.

    Conservative: only patterns that unambiguously indicate the
    COMMAND ITSELF failed are matched. Data-level substring
    coincidence (e.g. `grep 'command not found' /var/log/syslog`)
    is filtered by anchoring patterns to the bash error-line shape.
    """
    if returncode != 0:
        return FailureSignal(
            kind="nonzero_exit",
            marker=f"exit={returncode}",
            source="returncode",
        )

    for source_name, text in (("stderr", stderr or ""),
                              ("stdout", stdout or "")):
        if not text:
            continue
        for pattern, kind in _PATTERNS:
            m = pattern.search(text)
            if m:
                return FailureSignal(
                    kind=kind,
                    marker=m.group(0)[:200],
                    source=source_name,
                )
    return None
