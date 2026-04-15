"""
core/builder_mode_capture.py — A-core #3, Step 5.

Narrow-scope git-diff capture for builder-mode sessions. Shoots a
short summary of what's changed on the watched paths and logs it
as a direct_edit event in audit_log.db. Two trigger points:

  1. Daemon startup, if a builder-mode session is currently active
     (state file exists). Uses a diff hash stored in the state file
     to avoid duplicate/noisy entries on repeated restarts.
  2. Session end, called from cmd_exit (CLI) and _handle_builder_exit
     (Telegram) before closing the session. Always captures, no hash
     comparison — session end happens once per session.

What this module is NOT (by intentional scope discipline):
  - A general git introspection layer
  - A patch-blob capture surface — diff summary only, not full hunks
  - A continuous file-system watcher
  - A commit logger (commits are captured at restart / session-end
    like any other working-directory change)

If you're tempted to make it broader, stop. This is one of 7 Steps
in A-core #3 and its job is narrow by design.

Watched paths:
  - core/          (Maez's brain)
  - skills/        (surfaces)
  - daemon/        (life cycle)
  - config/soul.md (personality)
  - config/policies.yaml (decision pipeline policy)

Tests and docs are deliberately excluded — they shape what we verify
about Maez, not who Maez is. Step 6 will add soul.md-specific hash
watching on top of the daemon's existing soul watcher.

Diff summary shape (not full patches):
    core/audit_log.py (+45, -3)
    skills/telegram_voice.py (+196, -0)
    config/soul.md (+12, -8)
    core/builder_mode_perception.py (new)

Just the file-level stat. the owner can pull full diffs from git when
needed; Maez's perception only needs to know shape and intent.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Optional

from core.audit_log import AuditLog


# -------------------------------------------------------------------- #
#  Watched paths                                                         #
# -------------------------------------------------------------------- #

WATCHED_PATHS: list[str] = [
    "core/",
    "skills/",
    "daemon/",
    "config/soul.md",
    "config/policies.yaml",
]


# Sentinel session_id used for direct_edit events that do not belong
# to a real user-initiated builder session — e.g. the dream state
# writing an autonomous soul note. See A-core #3 Step 6. Events
# tagged with this sentinel are queryable via recent_direct_edits
# (session_id=AUTONOMOUS_SESSION_ID) and grouped under a single
# virtual "always-open" session that has no session_start or
# session_end rows.
AUTONOMOUS_SESSION_ID: str = "autonomous"


def read_active_session_id(state_file: Path) -> Optional[str]:
    """Read the shared state file and return the currently-active
    builder session_id, or None if no session is active. Used by
    the daemon soul watcher (and other producers) to decide whether
    to tag events with a real session or the autonomous sentinel.

    Defensive: missing file, empty file, unreadable file → returns
    None. Does not raise.
    """
    if not state_file.exists():
        return None
    try:
        content = state_file.read_text().strip()
    except OSError:
        return None
    if not content:
        return None
    first_line = content.splitlines()[0].strip()
    return first_line or None


# -------------------------------------------------------------------- #
#  Primitive: capture a diff summary on the watched paths               #
# -------------------------------------------------------------------- #

def capture_git_diff_summary(
    repo_root: Path,
    watched_paths: Optional[list[str]] = None,
    *,
    timeout_s: float = 10.0,
) -> tuple[str, str, list[str]]:
    """Run `git diff --numstat HEAD` on the given watched paths and
    return a formatted summary.

    Returns:
        (summary, diff_hash, paths)

        summary:   Human-readable multi-line text. Empty string if
                   there are no changes or if git failed.
        diff_hash: Stable SHA-256 over the raw git output bytes.
                   Used for duplicate detection (daemon restart case).
                   For an empty diff, returns the hash of empty bytes.
        paths:     List of file paths touched. Empty if no changes.

    Does not raise. Any git invocation failure is swallowed and
    returns ("", "", []) so the caller can distinguish "no changes"
    from "git failed" by checking whether summary is empty AND
    diff_hash is empty.
    """
    if watched_paths is None:
        watched_paths = WATCHED_PATHS

    args = ["git", "-C", str(repo_root), "diff", "--numstat", "HEAD", "--"] + watched_paths
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "", "", []

    if result.returncode != 0:
        return "", "", []

    raw_diff = result.stdout

    # Also collect untracked files within the watched paths. `git diff`
    # does not include untracked paths, but a new file in core/ is
    # exactly the kind of change this feature needs to see.
    raw_status = ""
    untracked_entries: list[str] = []
    try:
        status_args = ["git", "-C", str(repo_root), "status", "--porcelain", "--"] + watched_paths
        status_result = subprocess.run(
            status_args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if status_result.returncode == 0:
            raw_status = status_result.stdout
            for sline in status_result.stdout.splitlines():
                if not sline:
                    continue
                flag = sline[:2]
                status_path = sline[3:].strip()
                if flag.strip() == "??":
                    untracked_entries.append(status_path)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Hash covers BOTH diff output and status output so the duplicate-
    # suppression logic picks up untracked-file changes, not just
    # tracked-file edits. Without this, adding a new file wouldn't
    # invalidate the last_diff_hash and a daemon restart would miss
    # the new file.
    hash_input = (raw_diff + "\n---\n" + raw_status).encode("utf-8")
    diff_hash = hashlib.sha256(hash_input).hexdigest()

    # Short-circuit: empty diff AND no untracked files → nothing to show.
    if not raw_diff.strip() and not untracked_entries:
        return "", diff_hash, []

    lines = []
    paths: list[str] = []
    for line in raw_diff.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        paths.append(path)
        if added == "-" and deleted == "-":
            # Binary file — git shows "-\t-\tpath"
            lines.append(f"  {path} (binary)")
        else:
            lines.append(f"  {path} (+{added}, -{deleted})")

    for path in untracked_entries:
        if path not in paths:
            paths.append(path)
            lines.append(f"  {path} (new, untracked)")

    summary = "\n".join(lines)
    return summary, diff_hash, paths


# -------------------------------------------------------------------- #
#  Daemon startup helper                                                 #
# -------------------------------------------------------------------- #

def capture_startup_diff_if_active(
    *,
    repo_root: Path,
    state_file: Path,
    audit_log: AuditLog,
    now: Optional[float] = None,
) -> Optional[str]:
    """Call on daemon startup. If a builder-mode session is active
    (state file exists), capture the current git diff on watched
    paths, compare to the last_diff_hash stored in state, and log a
    direct_edit event only if the diff has changed since last seen.

    Returns:
        session_id if an event was logged, None otherwise.

    Duplicate detection:
        The first call writes `last_diff_hash=<hex>` to the state
        file. Subsequent calls that compute the same hash skip the
        logging and return None. This prevents repeated daemon
        restarts with no intervening edits from producing noisy
        duplicate entries.

    The state file format is extended with one optional field:
        <session_id>
        reason=<text>
        opened_at=<unix ts>
        last_diff_hash=<hex>           # added by this function

    CLI and Telegram write the first three fields on enter and
    ignore the fourth on exit (they only read session_id + opened_at).
    This function is the only writer for the hash field.
    """
    if not state_file.exists():
        return None

    try:
        content = state_file.read_text().strip()
    except OSError:
        return None

    if not content:
        return None

    lines = content.splitlines()
    session_id = lines[0].strip()
    if not session_id:
        return None

    state: dict[str, str] = {"session_id": session_id}
    for line in lines[1:]:
        if "=" in line:
            k, v = line.split("=", 1)
            state[k.strip()] = v.strip()

    last_hash = state.get("last_diff_hash", "")

    summary, new_hash, paths = capture_git_diff_summary(repo_root)

    # No diff → nothing to log, state file unchanged
    if not summary:
        return None

    # Same diff as last capture → skip (duplicate suppression)
    if new_hash == last_hash:
        return None

    # Log the direct_edit event
    audit_log.log_direct_edit(
        session_id=session_id,
        paths=paths,
        diff_summary=summary,
        commit_hash=None,
        reason="daemon startup diff capture",
    )

    # Rewrite state file preserving the original fields and adding
    # the new hash. Use the same format CLI/Telegram produce so
    # cross-surface reads stay clean.
    new_lines = [session_id]
    if "reason" in state:
        new_lines.append(f"reason={state['reason']}")
    if "opened_at" in state:
        new_lines.append(f"opened_at={state['opened_at']}")
    new_lines.append(f"last_diff_hash={new_hash}")
    state_file.write_text("\n".join(new_lines) + "\n")

    return session_id


# -------------------------------------------------------------------- #
#  Session-end helper                                                    #
# -------------------------------------------------------------------- #

def capture_session_end_diff(
    *,
    repo_root: Path,
    session_id: str,
    audit_log: AuditLog,
    reason: str = "session end diff capture",
) -> bool:
    """Call from cmd_exit (CLI) / _handle_builder_exit (Telegram)
    before closing the session. Captures the current git diff on
    watched paths and logs a direct_edit event if non-empty.

    Returns True if an event was logged, False if the diff was
    empty or git failed.

    No hash comparison here — session end happens once per session,
    so there is no "duplicate" to worry about.
    """
    summary, _hash, paths = capture_git_diff_summary(repo_root)
    if not summary:
        return False

    audit_log.log_direct_edit(
        session_id=session_id,
        paths=paths,
        diff_summary=summary,
        commit_hash=None,
        reason=reason,
    )
    return True


# -------------------------------------------------------------------- #
#  Self-test                                                             #
# -------------------------------------------------------------------- #

if __name__ == "__main__":
    import tempfile
    import os
    import shutil

    print("=== builder_mode_capture self-test ===\n")

    # Create a temporary git repo to test against
    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = Path(tmp_root_str)

        def run(cmd: list[str]) -> str:
            return subprocess.run(
                cmd, cwd=tmp_root, capture_output=True, text=True, check=True
            ).stdout

        # Init git repo
        run(["git", "init", "-q", "-b", "main"])
        run(["git", "config", "user.email", "test@maez.local"])
        run(["git", "config", "user.name", "test"])

        # Create watched-path structure + a baseline commit
        (tmp_root / "core").mkdir()
        (tmp_root / "skills").mkdir()
        (tmp_root / "daemon").mkdir()
        (tmp_root / "config").mkdir()
        (tmp_root / "tests").mkdir()  # not watched — used to test filter
        (tmp_root / "core" / "foo.py").write_text("print('foo')\n")
        (tmp_root / "skills" / "bar.py").write_text("print('bar')\n")
        (tmp_root / "config" / "soul.md").write_text("You are Maez.\n")
        (tmp_root / "tests" / "should_be_ignored.py").write_text("not watched\n")
        run(["git", "add", "-A"])
        run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "baseline"])

        # Sanity: baseline = no diff
        summary, diff_hash, paths = capture_git_diff_summary(tmp_root)
        assert summary == "", f"expected empty summary, got {summary!r}"
        assert diff_hash != "", "empty diff should still have a hash"
        assert paths == []
        print("  ✓ clean working tree → empty summary, non-empty hash")

        # Modify a watched file → should appear in diff summary
        (tmp_root / "core" / "foo.py").write_text("print('foo modified')\n")
        summary, diff_hash, paths = capture_git_diff_summary(tmp_root)
        assert "core/foo.py" in summary, f"expected core/foo.py in summary: {summary}"
        assert "+1" in summary and "-1" in summary
        assert diff_hash != ""
        assert "core/foo.py" in paths
        print("  ✓ modified watched file surfaces in summary")

        # Modify an IGNORED file → should NOT appear
        (tmp_root / "tests" / "should_be_ignored.py").write_text("still not watched\n")
        summary, diff_hash, paths = capture_git_diff_summary(tmp_root)
        assert "tests/" not in summary, f"tests/ should not be in summary: {summary}"
        assert not any("tests/" in p for p in paths)
        print("  ✓ non-watched path changes are filtered out")

        # Add a new (untracked) file in a watched path → should appear as "new"
        (tmp_root / "core" / "new_module.py").write_text("new file\n")
        summary, diff_hash, paths = capture_git_diff_summary(tmp_root)
        assert "new_module.py" in summary
        assert "(new" in summary
        print("  ✓ new untracked file in watched path surfaces as 'new'")

        # Hash stability: same state → same hash
        summary1, h1, _ = capture_git_diff_summary(tmp_root)
        summary2, h2, _ = capture_git_diff_summary(tmp_root)
        # Note: h1/h2 only cover `git diff`, not the untracked file status
        # pass, so they should be equal for the same diff state.
        assert h1 == h2, f"hash should be stable: {h1} vs {h2}"
        print("  ✓ hash stable across identical captures")

        # Hash changes when diff changes
        (tmp_root / "skills" / "bar.py").write_text("print('bar changed')\n")
        _, h3, _ = capture_git_diff_summary(tmp_root)
        assert h3 != h1
        print("  ✓ hash changes when diff changes")

        # ---------------------------------------------------------- #
        #  capture_startup_diff_if_active — daemon restart scenarios  #
        # ---------------------------------------------------------- #
        print("\n--- startup capture tests ---")

        # Fresh temp DB for audit_log
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = Path(tf.name)
        db_path.unlink()
        audit = AuditLog(db_path)

        # Fresh temp state file
        state_file = tmp_root / "builder_mode_current.txt"

        # No state file → no-op
        result = capture_startup_diff_if_active(
            repo_root=tmp_root, state_file=state_file, audit_log=audit,
        )
        assert result is None
        print("  ✓ no state file → no-op")

        # Open a session via AuditLog (as the CLI would)
        session_id = audit.start_direct_edit_session(
            reason="test startup capture", source="cli",
        )
        state_file.write_text(
            f"{session_id}\n"
            f"reason=test startup capture\n"
            f"opened_at={time.time()}\n"
        )

        # First startup capture → should log because diff is non-empty
        # and no last_hash stored
        result = capture_startup_diff_if_active(
            repo_root=tmp_root, state_file=state_file, audit_log=audit,
        )
        assert result == session_id, f"expected session_id {session_id}, got {result}"
        print("  ✓ first startup with active session + diff → logged")

        # Verify the event landed
        events = audit.recent_direct_edits(session_id=session_id)
        edit_events = [e for e in events if e["action"] == "direct_edit"]
        assert len(edit_events) == 1, f"expected 1 edit event, got {len(edit_events)}"
        print("  ✓ event lands in audit_log with session_id binding")

        # State file should now contain last_diff_hash
        state_content = state_file.read_text()
        assert "last_diff_hash=" in state_content
        print("  ✓ state file updated with last_diff_hash after first capture")

        # Second startup with IDENTICAL diff → duplicate suppression
        result = capture_startup_diff_if_active(
            repo_root=tmp_root, state_file=state_file, audit_log=audit,
        )
        assert result is None, f"expected None (duplicate), got {result}"
        edit_events = [e for e in audit.recent_direct_edits(session_id=session_id)
                       if e["action"] == "direct_edit"]
        assert len(edit_events) == 1, f"no duplicate should be logged, got {len(edit_events)}"
        print("  ✓ repeated restart with no new edits → no duplicate event")

        # Make another change → startup capture should log a new event
        (tmp_root / "daemon" / "m.py").write_text("daemon change\n")
        result = capture_startup_diff_if_active(
            repo_root=tmp_root, state_file=state_file, audit_log=audit,
        )
        assert result == session_id, "new diff should produce a new event"
        edit_events = [e for e in audit.recent_direct_edits(session_id=session_id)
                       if e["action"] == "direct_edit"]
        assert len(edit_events) == 2, f"expected 2 edit events, got {len(edit_events)}"
        print("  ✓ new diff after restart → second event logged")

        # ---------------------------------------------------------- #
        #  capture_session_end_diff                                    #
        # ---------------------------------------------------------- #
        print("\n--- session end capture tests ---")

        # Non-empty diff → always logs
        logged = capture_session_end_diff(
            repo_root=tmp_root,
            session_id=session_id,
            audit_log=audit,
            reason="test session end",
        )
        assert logged is True
        edit_events = [e for e in audit.recent_direct_edits(session_id=session_id)
                       if e["action"] == "direct_edit"]
        assert len(edit_events) == 3, f"expected 3 edit events, got {len(edit_events)}"
        print("  ✓ session-end capture logs direct_edit event")

        # Commit everything and try again — empty diff, no event
        run(["git", "add", "-A"])
        run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "wip"])
        logged = capture_session_end_diff(
            repo_root=tmp_root,
            session_id=session_id,
            audit_log=audit,
            reason="test clean session end",
        )
        assert logged is False, "clean tree at session end → no event"
        edit_events = [e for e in audit.recent_direct_edits(session_id=session_id)
                       if e["action"] == "direct_edit"]
        assert len(edit_events) == 3, f"still 3 edit events, got {len(edit_events)}"
        print("  ✓ clean tree at session end → no event")

        # ---------------------------------------------------------- #
        #  read_active_session_id + AUTONOMOUS_SESSION_ID             #
        # ---------------------------------------------------------- #
        print("\n--- session state helper tests ---")

        missing = tmp_root / "no_such_file.txt"
        assert read_active_session_id(missing) is None
        print("  ✓ missing state file → None")

        empty_file = tmp_root / "empty.txt"
        empty_file.write_text("")
        assert read_active_session_id(empty_file) is None
        print("  ✓ empty state file → None")

        valid = tmp_root / "valid.txt"
        valid.write_text("ed797d4f4f4abe2470917197\nreason=test\nopened_at=123.0\n")
        assert read_active_session_id(valid) == "ed797d4f4f4abe2470917197"
        print("  ✓ valid state file → session_id")

        assert AUTONOMOUS_SESSION_ID == "autonomous"
        print("  ✓ AUTONOMOUS_SESSION_ID constant is 'autonomous'")

        # Cleanup
        db_path.unlink(missing_ok=True)
        print("\n=== builder_mode_capture self-test complete ===")
