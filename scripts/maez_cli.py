#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
scripts/maez_cli.py — Builder-mode CLI for Maez (A-core #3, Step 2).

A deliberately minimal command-line entry point for the owner to enter
and exit Developer Mode without going through Telegram. The shell is
the resilience fallback: if Telegram is down, if the bot token rotates,
if the polling thread dies, the owner can still mark his builder-mode
sessions from a terminal.

What this CLI is:
  - A two-command interface: `enter` and `exit`
  - UID-bound (refuses to run as anything other than UID 1000)
  - Interactive confirmation on `enter` (must type the exact phrase)
  - Writes session records to memory/audit_log.db via AuditLog
  - Persists the current session_id to daemon/builder_mode_current.txt
    so `exit` can find the active session without the user having
    to remember the hex id

What this CLI is NOT (by intentional scope discipline — do not extend
without explicit agreement from the owner first):
  - A general Maez control plane
  - A way to start/stop/restart maez.service
  - A way to inspect audit logs, memory, or anything else
  - A way to configure Maez
  - A wrapper around git, systemd, or any other tool
  - A PWA or webapp or dashboard

If you find yourself adding a third subcommand, STOP. Builder mode
is step 2 of 7 in Track A item #3, and its job is narrowly defined
by design — enter, exit, bind to the user, create a clean session
record that later steps (#3 synthetic event, #4 telegram handler,
#5 git-diff capture, #6 soul.md hash events, #7 daemon startup
read) can surface to Maez.

Usage:
    # Enter builder mode
    .venv/bin/python3 scripts/maez_cli.py enter --reason "rewriting sudo handling"

    # Exit the current session
    .venv/bin/python3 scripts/maez_cli.py exit

    # Exit a specific session explicitly (override state file)
    .venv/bin/python3 scripts/maez_cli.py exit --session-id <hex>

    # Non-interactive (bypass the typed-phrase confirmation)
    .venv/bin/python3 scripts/maez_cli.py enter --reason "..." --yes
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Project root import — the CLI discovers its own location and walks
# up to find the maez/ directory, then imports core.audit_log from
# there. This keeps the CLI portable to different install paths
# without hardcoding /home/rohit/maez.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.audit_log import (  # noqa: E402 — must come after sys.path insert
    AuditLog,
    DIRECT_EDIT_SOURCE_CLI,
    DIRECT_EDIT_SESSION_START,
    DIRECT_EDIT_SESSION_END,
)


# -------------------------------------------------------------------- #
#  Constants                                                             #
# -------------------------------------------------------------------- #

# UID binding — refuse to run as anyone other than the owner. Root is
# explicitly refused even though root can do anything else on the
# system. Builder mode is the owner's personal mode, not root's.
EXPECTED_UID = 1000

# State file for the currently-active session. Written on `enter`,
# read by `exit`, deleted on successful close. Lives in daemon/
# alongside other runtime state files (maez.pid, pending_actions.json,
# last_shutdown). Added to .gitignore — runtime state, not source.
STATE_FILE = PROJECT_ROOT / "daemon" / "builder_mode_current.txt"

# The exact phrase the user has to type at the interactive
# confirmation prompt. `yes | maez-cli enter ...` does NOT bypass
# this because `yes` only outputs the string "y", not the full
# phrase. Intentional accident-resistance.
CONFIRM_PHRASE = "enter builder mode"


# -------------------------------------------------------------------- #
#  Helpers                                                               #
# -------------------------------------------------------------------- #

def _fail(msg: str, code: int = 1) -> None:
    """Print an error to stderr and exit."""
    print(f"maez-cli: {msg}", file=sys.stderr)
    sys.exit(code)


def _check_uid() -> None:
    """Refuse to run if not the owner. Root is explicitly refused."""
    uid = os.getuid()
    if uid != EXPECTED_UID:
        if uid == 0:
            _fail(
                "refusing to run as root. Builder mode is the owner's "
                "personal mode, not root's. Run as your user account."
            )
        _fail(
            f"refusing to run as uid={uid}. Builder mode is bound "
            f"to uid={EXPECTED_UID}. Run as the owner's user account."
        )


def _read_state() -> dict | None:
    """Read the current session state file. Returns None if no
    session is active (file missing or empty)."""
    if not STATE_FILE.exists():
        return None
    try:
        content = STATE_FILE.read_text().strip()
    except OSError as e:
        _fail(f"could not read state file {STATE_FILE}: {e}")
    if not content:
        return None
    # Format: one session_id per line, optional metadata on following
    # lines as key=value. Minimal.
    lines = content.splitlines()
    session_id = lines[0].strip()
    meta = {}
    for line in lines[1:]:
        if "=" in line:
            k, v = line.split("=", 1)
            meta[k.strip()] = v.strip()
    return {"session_id": session_id, **meta}


def _write_state(session_id: str, reason: str, opened_at: float) -> None:
    """Persist the currently-active session so exit can find it."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"{session_id}\n"
        f"reason={reason}\n"
        f"opened_at={opened_at}\n"
    )
    STATE_FILE.write_text(content)


def _clear_state() -> None:
    """Remove the state file on successful exit."""
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def _confirm_interactive() -> bool:
    """Prompt the user to type the confirmation phrase. Returns True
    if they typed the exact phrase, False otherwise. `yes | ...` does
    not bypass this because `yes` only emits single characters."""
    print()
    print(f"  You are about to enter BUILDER MODE.")
    print(f"  Every direct edit you make will be logged to Maez's audit log")
    print(f"  until you run `maez-cli exit`.")
    print()
    print(f"  To confirm, type the exact phrase: {CONFIRM_PHRASE}")
    print()
    try:
        typed = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return typed == CONFIRM_PHRASE


# -------------------------------------------------------------------- #
#  Commands                                                              #
# -------------------------------------------------------------------- #

def cmd_enter(args: argparse.Namespace) -> int:
    """Open a new builder-mode session."""
    _check_uid()

    # Refuse if a session is already active. Prevents accidental
    # double-entry; the user has to explicitly exit the current
    # session before opening a new one.
    existing = _read_state()
    if existing is not None:
        print(f"  A builder-mode session is already active:")
        print(f"    session_id: {existing['session_id']}")
        if "reason" in existing:
            print(f"    reason:     {existing['reason']}")
        if "opened_at" in existing:
            try:
                opened_ts = float(existing["opened_at"])
                age = time.time() - opened_ts
                print(f"    age:        {int(age // 60)}m {int(age % 60)}s")
            except ValueError:
                pass
        print()
        print(f"  Run `maez-cli exit` first to close it, then try again.")
        return 1

    reason = args.reason.strip()
    if not reason:
        _fail("--reason must be non-empty. Builder mode requires a stated reason.")

    # Interactive confirmation unless --yes was passed
    if not args.yes:
        if not _confirm_interactive():
            print("  Confirmation failed. Builder mode not entered.")
            return 1

    # Open the session via AuditLog
    audit = AuditLog()
    session_id = audit.start_direct_edit_session(
        reason=reason,
        source=DIRECT_EDIT_SOURCE_CLI,
    )

    opened_at = time.time()
    _write_state(session_id, reason, opened_at)

    print()
    print(f"  Session opened: {session_id}")
    print(f"  Reason: {reason}")
    print(f"  Source: {DIRECT_EDIT_SOURCE_CLI}")
    print()
    print(f"  Builder mode is now ACTIVE. All direct edits should be")
    print(f"  captured by the logger and surfaced to Maez by later")
    print(f"  Track A #3 steps (git-diff capture on restart, soul.md")
    print(f"  hash events, daemon startup read).")
    print()
    print(f"  When you are done, run:  maez-cli exit")
    print()
    return 0


def cmd_exit(args: argparse.Namespace) -> int:
    """Close the current (or a specified) builder-mode session."""
    _check_uid()

    # Resolve which session to close. Priority: explicit --session-id,
    # then the state file. If neither exists, there is no active session.
    if args.session_id:
        session_id = args.session_id.strip()
        state_driven = False
    else:
        state = _read_state()
        if state is None:
            _fail(
                "no active builder-mode session. Either run `enter` "
                "first or pass --session-id <hex> explicitly."
            )
        session_id = state["session_id"]
        state_driven = True

    # Compute session duration if we have opened_at from the state file
    duration_str = None
    if state_driven:
        state = _read_state() or {}
        if "opened_at" in state:
            try:
                opened_ts = float(state["opened_at"])
                dur = time.time() - opened_ts
                hours = int(dur // 3600)
                minutes = int((dur % 3600) // 60)
                seconds = int(dur % 60)
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except ValueError:
                pass

    audit = AuditLog()

    # A-core #3 Step 5: capture any git diff on watched paths before
    # closing the session, so Maez gets a final direct_edit event
    # recording the state of the working directory at session end.
    # Always captures (no hash comparison — session end is once per
    # session). No-op if the diff is empty or git failed.
    diff_logged = False
    try:
        from core.builder_mode_capture import capture_session_end_diff
        diff_logged = capture_session_end_diff(
            repo_root=PROJECT_ROOT,
            session_id=session_id,
            audit_log=audit,
            reason="session end diff capture (cli)",
        )
    except Exception as e:
        print(f"  (warning: session-end diff capture failed: {e})", file=sys.stderr)

    audit.end_direct_edit_session(session_id=session_id)

    # Clear state file only if this was the state-tracked session.
    # If the user passed --session-id manually, we don't touch the
    # state file (there might be another session the user is tracking).
    if state_driven:
        _clear_state()

    print()
    print(f"  Session closed: {session_id}")
    if duration_str:
        print(f"  Duration: {duration_str}")
    if diff_logged:
        print(f"  Final diff captured as direct_edit event.")
    print(f"  Builder mode is now INACTIVE.")
    print()
    return 0


# -------------------------------------------------------------------- #
#  Entry point                                                           #
# -------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="maez-cli",
        description="Minimal CLI for Maez builder mode (A-core #3, Step 2).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # enter
    p_enter = subparsers.add_parser(
        "enter",
        help="Enter builder mode (opens a new session)",
    )
    p_enter.add_argument(
        "--reason",
        "-r",
        required=True,
        help="Why you are entering builder mode. Required. Stored in "
             "the session record and surfaced to Maez.",
    )
    p_enter.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the interactive confirmation prompt. Use sparingly.",
    )

    # exit
    p_exit = subparsers.add_parser(
        "exit",
        help="Exit builder mode (closes the active or specified session)",
    )
    p_exit.add_argument(
        "--session-id",
        "-s",
        default=None,
        help="Explicit session_id to close. If omitted, the CLI reads "
             "the currently-active session from daemon/builder_mode_current.txt.",
    )

    args = parser.parse_args()
    if args.command == "enter":
        return cmd_enter(args)
    elif args.command == "exit":
        return cmd_exit(args)
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
