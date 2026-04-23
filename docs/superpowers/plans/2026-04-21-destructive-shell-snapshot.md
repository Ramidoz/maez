# Pre-flight Snapshot for Destructive Shell Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before any destructive shell command runs via `ActionEngine._execute_action`, snapshot the files it will affect into `memory/backups/pre_destructive/<request_id>/` with a JSON manifest, so the owner can recover from "I approved a destructive card in good faith" events.

**Architecture:** A new module `core/destructive_snapshot.py` exposes pure functions: `classify(cmd) -> tuple[is_destructive, affected_files]`, `snapshot(request_id, cmd, reason, files) -> manifest_path`, `list_recent(days=7) -> [manifests]`, `restore(request_id, dry_run=True|False) -> {restored|previewed: [paths]}`. The action_engine's `_execute_action` calls `classify` at the top of `_do_run_shell`-adjacent dispatch; if destructive, calls `snapshot` before letting the command proceed. Snapshots land under `memory/backups/pre_destructive/<request_id>/<mirrored_path>` with a sibling `manifest.json`. A tiny CLI entry point (`python -m core.destructive_snapshot restore <request_id>`) lets the owner recover without Maez's tool surface being involved. Scope intentionally narrow: detect and snapshot the 4 command classes actually observed or obviously high-risk (`git checkout -- <paths>`, `git reset --hard`, `rm <paths>`, `truncate <path>`). Other destructive shapes (`mv -f` over existing, `dd of=`, redirect-to-existing) are out of scope for this MVP and will be queued as follow-ups once we observe them.

**Tech Stack:** Python 3.12 stdlib (`pathlib`, `shutil`, `json`, `shlex`, `hashlib`), unittest.

---

## Scope boundary

**In:**
- New module `core/destructive_snapshot.py` — pure-function detection + snapshot + restore.
- Integration into `core/action_engine.py::_execute_action` — pre-flight runs for `run_shell` action type only.
- CLI restore entry point — `.venv/bin/python -m core.destructive_snapshot restore <request_id>` and `list`.
- Unit tests for all detection / snapshot / restore paths.

**Out:**
- Exposing `restore_snapshot` as a Maez-facing tool (no ACTION_TIERS entry, no brain_loop allowed-set, no tool manifest entry). Restoration is an owner-only CLI action in MVP. Rationale: Maez proposing to restore after destroying is a new failure mode; keep human-only for now.
- Detection of `mv -f`, `cp -f`, `dd of=`, `truncate -s 0`, shell redirect `>`. Add when observed.
- Auto-restore on error. Manifest gives the *ability* to restore; restoration is deliberate owner action.
- Changes to card UI framing / destructive classification (that's fix B in the parent plan, separate).

## Command shapes classified as destructive in this MVP

| Shape | Regex / matcher | Affected files |
|---|---|---|
| `git checkout -- <paths>` | `git\s+(?:-C\s+\S+\s+)?checkout\s+--\s+` | the `<paths>` listed after `--`. Resolve relative paths against `-C <dir>` if present, else CWD. |
| `git restore <paths>` | `git\s+(?:-C\s+\S+\s+)?restore\s+` (no `--staged` flag) | the paths listed |
| `git reset --hard` | `git\s+(?:-C\s+\S+\s+)?reset\s+--hard` | **all** currently-modified tracked files (use `git diff --name-only` at snapshot time) |
| `rm <paths>` / `rm -[rf]+ <paths>` | `(?<!\w)rm(?:\s+-[a-zA-Z]+)*\s+` | path args that exist on disk; recurse for directories when `-r` is present |
| `truncate <path>` | `truncate(?:\s+-[a-zA-Z]\S*)*\s+\S+` | the last non-flag arg (target path) |

**Important narrow:** commands that redirect writes (`echo x > /path`, `tee /path`) are NOT covered in this MVP. They're destructive but the parse surface is wider. We'll add a second classifier in a follow-up.

**Important safety:** if classification errors or can't parse affected files, we **fail open** — log a warning, skip snapshot, let the command run. Snapshot failures must never block a legitimate command.

## File layout

- `memory/backups/pre_destructive/<request_id>/manifest.json`
- `memory/backups/pre_destructive/<request_id>/files/<mirrored_abs_path>` — e.g. `/home/rohit/maez/core/cognition_quality.py` → `files/home/rohit/maez/core/cognition_quality.py`

Manifest schema:
```json
{
  "request_id": "<uuid-ish>",
  "ts": 1776748265.34,
  "cmd": "git -C /home/rohit/maez checkout -- core/cognition_quality.py",
  "reason": "Revert the local file to match the approved proposal #25",
  "shape": "git_checkout",
  "files": [
    {
      "original_path": "/home/rohit/maez/core/cognition_quality.py",
      "snapshot_path": "files/home/rohit/maez/core/cognition_quality.py",
      "sha256": "...",
      "size_bytes": 12345,
      "existed_pre_snapshot": true
    }
  ]
}
```

Files that didn't exist pre-command (e.g. would have been created by a redirect — out of scope here anyway) get `existed_pre_snapshot: false` and no copy is made; the manifest still records the intent so restore can choose to delete the post-command file.

---

## Task 1: `core/destructive_snapshot.py` — pure functions

**Files:**
- Create: `core/destructive_snapshot.py`
- Create: `tests/test_destructive_snapshot.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_destructive_snapshot.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.destructive_snapshot — the pre-flight safety
layer that snapshots files before destructive shell commands run.

Observed 2026-04-20: user approved a card proposing
`git checkout -- core/cognition_quality.py` as a 'preparation' step.
The checkout ran, unstaged local changes were destroyed, no backup
path existed. This module closes the gap."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class ClassifyDestructiveCommands(unittest.TestCase):
    """classify(cmd) -> {is_destructive: bool, shape: str, files: [paths]}"""

    def test_git_checkout_with_paths(self):
        from core.destructive_snapshot import classify
        r = classify("git -C /home/rohit/maez checkout -- core/cognition_quality.py")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "git_checkout")
        self.assertEqual(
            r["files"],
            ["/home/rohit/maez/core/cognition_quality.py"],
        )

    def test_git_checkout_multiple_paths(self):
        from core.destructive_snapshot import classify
        r = classify("git checkout -- foo.py bar.py")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "git_checkout")
        # paths are relative to CWD; returned as-provided (caller resolves)
        self.assertIn("foo.py", r["files"])
        self.assertIn("bar.py", r["files"])

    def test_git_restore_paths(self):
        from core.destructive_snapshot import classify
        r = classify("git restore path/to/file.py")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "git_restore")
        self.assertIn("path/to/file.py", r["files"])

    def test_git_reset_hard(self):
        from core.destructive_snapshot import classify
        r = classify("git -C /home/rohit/maez reset --hard HEAD~1")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "git_reset_hard")
        # files list is the special sentinel — caller resolves via
        # `git diff --name-only` at snapshot time.
        self.assertEqual(r["files"], ["<git-modified-tracked>"])

    def test_rm_single_path(self):
        from core.destructive_snapshot import classify
        r = classify("rm /tmp/foo.txt")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "rm")
        self.assertEqual(r["files"], ["/tmp/foo.txt"])

    def test_rm_recursive_with_flags(self):
        from core.destructive_snapshot import classify
        r = classify("rm -rf /tmp/foo /tmp/bar")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "rm")
        self.assertEqual(sorted(r["files"]), ["/tmp/bar", "/tmp/foo"])

    def test_truncate(self):
        from core.destructive_snapshot import classify
        r = classify("truncate -s 0 /home/rohit/log.txt")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "truncate")
        self.assertEqual(r["files"], ["/home/rohit/log.txt"])

    def test_non_destructive_passes(self):
        from core.destructive_snapshot import classify
        for cmd in (
            "git status --short",
            "git log --oneline -5",
            "ls /tmp",
            "cat /etc/hostname",
            "systemctl is-active maez",
            "git add core/foo.py",  # add is not destructive
            "git restore --staged foo.py",  # --staged is index-only, not working-tree
        ):
            r = classify(cmd)
            self.assertFalse(
                r["is_destructive"],
                f"expected non-destructive: {cmd!r} -> {r}"
            )

    def test_unparseable_returns_safe_unknown(self):
        """Garbage input must never raise. Classify returns
        is_destructive=False so callers don't snapshot random things,
        but the caller can still log/warn if it wanted to."""
        from core.destructive_snapshot import classify
        r = classify("")
        self.assertFalse(r["is_destructive"])
        r = classify(None)  # type: ignore
        self.assertFalse(r["is_destructive"])


class SnapshotWritesAndReads(unittest.TestCase):
    """snapshot(request_id, cmd, reason, files, *, root=tmp) writes
    files + manifest. restore(...) round-trips them."""

    def test_snapshot_copies_files_and_writes_manifest(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src" / "hello.py"
            src.parent.mkdir(parents=True)
            src.write_text("original content\n")

            backup_root = Path(tmp) / "backups"
            result = ds.snapshot(
                request_id="test-123",
                cmd=f"git checkout -- {src}",
                reason="test",
                files=[str(src)],
                root=str(backup_root),
            )

            manifest_path = Path(result["manifest_path"])
            self.assertTrue(manifest_path.exists())
            data = json.loads(manifest_path.read_text())
            self.assertEqual(data["request_id"], "test-123")
            self.assertEqual(len(data["files"]), 1)
            entry = data["files"][0]
            self.assertEqual(entry["original_path"], str(src))
            self.assertTrue(entry["existed_pre_snapshot"])
            # snapshot file exists:
            snap = manifest_path.parent / entry["snapshot_path"]
            self.assertTrue(snap.exists())
            self.assertEqual(snap.read_text(), "original content\n")

    def test_snapshot_handles_missing_file_gracefully(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "nope" / "does-not-exist.py"
            backup_root = Path(tmp) / "backups"
            result = ds.snapshot(
                request_id="test-456",
                cmd=f"rm {fake}",
                reason="test",
                files=[str(fake)],
                root=str(backup_root),
            )
            data = json.loads(Path(result["manifest_path"]).read_text())
            self.assertEqual(len(data["files"]), 1)
            self.assertFalse(data["files"][0]["existed_pre_snapshot"])


class RestoreRoundTrips(unittest.TestCase):
    def test_dry_run_does_not_touch_files(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src" / "hello.py"
            src.parent.mkdir(parents=True)
            src.write_text("v1\n")
            backup_root = Path(tmp) / "backups"
            ds.snapshot(
                request_id="r1",
                cmd=f"git checkout -- {src}",
                reason="test",
                files=[str(src)],
                root=str(backup_root),
            )
            # destroy the working tree:
            src.write_text("v2-overwritten\n")

            preview = ds.restore(
                request_id="r1", dry_run=True, root=str(backup_root)
            )
            self.assertEqual(preview["mode"], "dry_run")
            self.assertEqual(len(preview["files"]), 1)
            # file was NOT touched:
            self.assertEqual(src.read_text(), "v2-overwritten\n")

    def test_live_restore_writes_files_back(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src" / "hello.py"
            src.parent.mkdir(parents=True)
            src.write_text("v1\n")
            backup_root = Path(tmp) / "backups"
            ds.snapshot(
                request_id="r2",
                cmd=f"git checkout -- {src}",
                reason="test",
                files=[str(src)],
                root=str(backup_root),
            )
            src.write_text("v2-overwritten\n")

            result = ds.restore(
                request_id="r2", dry_run=False, root=str(backup_root)
            )
            self.assertEqual(result["mode"], "applied")
            # file was restored:
            self.assertEqual(src.read_text(), "v1\n")

    def test_restore_missing_request_id_returns_empty(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            r = ds.restore(
                request_id="nonexistent",
                dry_run=True,
                root=str(Path(tmp) / "nope"),
            )
            self.assertEqual(r["mode"], "not_found")
            self.assertEqual(r["files"], [])


class ListRecentSnapshots(unittest.TestCase):
    def test_list_empty_root(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            r = ds.list_recent(days=7, root=str(Path(tmp) / "nope"))
            self.assertEqual(r, [])

    def test_list_returns_recent_manifests_newest_first(self):
        from core import destructive_snapshot as ds
        with tempfile.TemporaryDirectory() as tmp:
            backup_root = Path(tmp) / "backups"
            src = Path(tmp) / "x.py"
            src.write_text("x\n")
            for rid in ("old", "mid", "new"):
                ds.snapshot(
                    request_id=rid, cmd=f"rm {src}", reason="t",
                    files=[str(src)], root=str(backup_root),
                )
            listed = ds.list_recent(days=7, root=str(backup_root))
            # newest first — they may have identical ts in fast machines,
            # so just assert all three are present with required fields:
            ids = [m["request_id"] for m in listed]
            self.assertIn("old", ids)
            self.assertIn("mid", ids)
            self.assertIn("new", ids)
            for m in listed:
                self.assertIn("ts", m)
                self.assertIn("cmd", m)
                self.assertIn("n_files", m)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify RED**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_destructive_snapshot -v
```

Expected: every test errors with `ModuleNotFoundError: No module named 'core.destructive_snapshot'`. That's correct — feature absent.

- [ ] **Step 3: Implement `core/destructive_snapshot.py`**

Create `core/destructive_snapshot.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""destructive_snapshot.py — pre-flight snapshot layer for destructive
shell commands.

Context 2026-04-20: owner approved an action card proposing
`git checkout -- core/cognition_quality.py` as a "preparation step"
for applying an evolution proposal. Checkout ran, unstaged local
edits were destroyed, no backup path existed. `write_any_file` has
auto-backup; destructive shell commands did not. This module closes
the gap.

Scope:
  - classify(cmd) → {is_destructive, shape, files}
  - snapshot(request_id, cmd, reason, files, *, root=...) → {manifest_path}
  - list_recent(days=7, *, root=...) → [manifest summaries]
  - restore(request_id, dry_run=True, *, root=...) → {mode, files}

Shape coverage (MVP): git_checkout, git_restore, git_reset_hard, rm,
truncate. Other destructive shapes (`mv -f`, `dd of=`, redirect `>`)
are out of scope and will be added when observed.

Safety policy:
  - Parse errors never raise — return is_destructive=False.
  - Snapshot failures never block the command — the action_engine
    caller logs the failure and proceeds.
  - Restore is human-driven via CLI, not exposed as a Maez action.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shlex
import shutil
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("maez.destructive_snapshot")

_DEFAULT_ROOT = "/home/rohit/maez/memory/backups/pre_destructive"

# Regexes for each destructive shape. Ordered — more specific first.
_GIT_PREFIX = r"git\s+(?:-C\s+\S+\s+)?"
_RE_GIT_CHECKOUT = re.compile(
    rf"{_GIT_PREFIX}checkout\s+--\s+(?P<paths>.+)$"
)
# restore with --staged is index-only (not destructive to working tree)
_RE_GIT_RESTORE = re.compile(
    rf"{_GIT_PREFIX}restore\s+(?!--staged)(?:--(?!staged)\S+\s+)*(?P<paths>.+)$"
)
_RE_GIT_RESET_HARD = re.compile(
    rf"{_GIT_PREFIX}reset\s+--hard\b"
)
# rm <flags> <paths> — non-flag tokens after rm are the paths
_RE_RM = re.compile(r"(?<!\w)rm\b(?P<rest>.*)$")
_RE_TRUNCATE = re.compile(r"(?<!\w)truncate\b(?P<rest>.*)$")


def _git_cwd(cmd: str) -> str | None:
    """Extract `-C <dir>` from a git command if present."""
    m = re.search(r"git\s+-C\s+(\S+)", cmd)
    return m.group(1) if m else None


def _resolve_paths(paths: list[str], base: str | None) -> list[str]:
    """Resolve path tokens against a `-C` base if given. Preserve
    absolute paths untouched."""
    out: list[str] = []
    for p in paths:
        p = p.strip().strip('"').strip("'")
        if not p:
            continue
        if p.startswith("/") or base is None:
            out.append(p)
        else:
            out.append(str(Path(base) / p))
    return out


def classify(cmd: Any) -> dict:
    """Classify a shell command. Returns a dict with:
      - is_destructive: bool
      - shape: str ("git_checkout"|"git_restore"|"git_reset_hard"|
                    "rm"|"truncate"|"")
      - files: list[str] — absolute paths when determinable, or the
                raw tokens; "<git-modified-tracked>" sentinel for
                git reset --hard (resolved by caller at snapshot time).
    Never raises."""
    default = {"is_destructive": False, "shape": "", "files": []}
    if not cmd or not isinstance(cmd, str):
        return default
    s = cmd.strip()
    if not s:
        return default

    # git reset --hard
    if _RE_GIT_RESET_HARD.search(s):
        return {
            "is_destructive": True,
            "shape": "git_reset_hard",
            "files": ["<git-modified-tracked>"],
        }

    # git checkout -- <paths>
    m = _RE_GIT_CHECKOUT.search(s)
    if m:
        try:
            paths = shlex.split(m.group("paths"))
        except ValueError:
            return default
        return {
            "is_destructive": True,
            "shape": "git_checkout",
            "files": _resolve_paths(paths, _git_cwd(s)),
        }

    # git restore <paths> (excludes --staged)
    m = _RE_GIT_RESTORE.search(s)
    if m:
        try:
            toks = shlex.split(m.group("paths"))
        except ValueError:
            return default
        # drop any remaining --flag tokens
        toks = [t for t in toks if not t.startswith("-")]
        if not toks:
            return default
        return {
            "is_destructive": True,
            "shape": "git_restore",
            "files": _resolve_paths(toks, _git_cwd(s)),
        }

    # rm
    m = _RE_RM.search(s)
    if m:
        try:
            toks = shlex.split(m.group("rest"))
        except ValueError:
            return default
        paths = [t for t in toks if not t.startswith("-")]
        if not paths:
            return default
        return {
            "is_destructive": True,
            "shape": "rm",
            "files": paths,
        }

    # truncate
    m = _RE_TRUNCATE.search(s)
    if m:
        try:
            toks = shlex.split(m.group("rest"))
        except ValueError:
            return default
        # truncate flags may consume args (-s N) — last non-flag is path
        non_flags: list[str] = []
        skip_next = False
        for t in toks:
            if skip_next:
                skip_next = False
                continue
            if t == "-s":
                skip_next = True
                continue
            if t.startswith("-"):
                continue
            non_flags.append(t)
        if not non_flags:
            return default
        return {
            "is_destructive": True,
            "shape": "truncate",
            "files": non_flags,
        }

    return default


def _mirror_path(original: str) -> str:
    """Return the mirrored relative path for a snapshot. Preserves
    the absolute path structure under `files/` so restoration is
    unambiguous."""
    p = original
    if p.startswith("/"):
        p = p[1:]
    return f"files/{p}"


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(
    *,
    request_id: str,
    cmd: str,
    reason: str,
    files: list[str],
    root: str | None = None,
    shape: str = "",
) -> dict:
    """Copy `files` into backup/<request_id>/ + write manifest.
    Returns {manifest_path, n_files, errors}. Never raises —
    returns an error list if anything went wrong."""
    root_path = Path(root or _DEFAULT_ROOT)
    dir_path = root_path / request_id
    files_root = dir_path / "files"
    errors: list[str] = []
    entries: list[dict] = []
    try:
        files_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {
            "manifest_path": None, "n_files": 0,
            "errors": [f"mkdir failed: {e}"],
        }
    for orig in files:
        if orig == "<git-modified-tracked>":
            # Caller resolves this at snapshot time by running
            # git diff --name-only; if caller didn't resolve it,
            # record the sentinel so restore can skip it.
            entries.append({
                "original_path": orig,
                "snapshot_path": None,
                "sha256": None,
                "size_bytes": 0,
                "existed_pre_snapshot": False,
                "note": "sentinel-not-resolved",
            })
            continue
        src = Path(orig)
        snap_rel = _mirror_path(orig)
        snap = dir_path / snap_rel
        try:
            snap.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"mkdir for {orig}: {e}")
            continue
        if src.exists() and src.is_file():
            try:
                shutil.copy2(str(src), str(snap))
                entries.append({
                    "original_path": str(src),
                    "snapshot_path": snap_rel,
                    "sha256": _sha256_of(snap),
                    "size_bytes": snap.stat().st_size,
                    "existed_pre_snapshot": True,
                })
            except Exception as e:
                errors.append(f"copy {orig}: {e}")
                entries.append({
                    "original_path": str(src),
                    "snapshot_path": None,
                    "sha256": None,
                    "size_bytes": 0,
                    "existed_pre_snapshot": True,
                    "note": f"copy_failed: {e}",
                })
        else:
            # File didn't exist pre-command (e.g. `rm` of a missing path,
            # or a sentinel). Record intent for restore to handle.
            entries.append({
                "original_path": str(src),
                "snapshot_path": None,
                "sha256": None,
                "size_bytes": 0,
                "existed_pre_snapshot": False,
            })
    manifest = {
        "request_id": request_id,
        "ts": time.time(),
        "cmd": cmd,
        "reason": reason,
        "shape": shape,
        "files": entries,
    }
    manifest_path = dir_path / "manifest.json"
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    except Exception as e:
        errors.append(f"manifest write: {e}")
        return {"manifest_path": None, "n_files": len(entries),
                "errors": errors}
    return {
        "manifest_path": str(manifest_path),
        "n_files": len(entries),
        "errors": errors,
    }


def list_recent(*, days: int = 7, root: str | None = None) -> list[dict]:
    """Return manifest summaries newest first. `days` caps age."""
    root_path = Path(root or _DEFAULT_ROOT)
    if not root_path.exists():
        return []
    cutoff = time.time() - (days * 86400)
    out: list[dict] = []
    for child in root_path.iterdir():
        m = child / "manifest.json"
        if not m.exists():
            continue
        try:
            data = json.loads(m.read_text())
        except Exception:
            continue
        if data.get("ts", 0) < cutoff:
            continue
        out.append({
            "request_id": data.get("request_id"),
            "ts": data.get("ts"),
            "cmd": data.get("cmd"),
            "shape": data.get("shape"),
            "n_files": len(data.get("files", [])),
            "manifest_path": str(m),
        })
    out.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    return out


def restore(
    *,
    request_id: str,
    dry_run: bool = True,
    root: str | None = None,
) -> dict:
    """Restore files from a snapshot. `dry_run=True` previews only."""
    root_path = Path(root or _DEFAULT_ROOT)
    m_path = root_path / request_id / "manifest.json"
    if not m_path.exists():
        return {"mode": "not_found", "files": []}
    try:
        data = json.loads(m_path.read_text())
    except Exception as e:
        return {"mode": "error", "error": str(e), "files": []}

    actions: list[dict] = []
    for entry in data.get("files", []):
        if not entry.get("existed_pre_snapshot"):
            continue
        snap_rel = entry.get("snapshot_path")
        if not snap_rel:
            continue
        snap = root_path / request_id / snap_rel
        target = Path(entry["original_path"])
        if not snap.exists():
            actions.append({"target": str(target), "status": "snap_missing"})
            continue
        actions.append({
            "target": str(target),
            "snapshot": str(snap),
            "status": "would_restore" if dry_run else "restored",
        })
        if not dry_run:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(snap), str(target))
            except Exception as e:
                actions[-1]["status"] = f"restore_failed: {e}"

    return {
        "mode": "dry_run" if dry_run else "applied",
        "files": actions,
    }


# ── CLI ────────────────────────────────────────────────────────────────

def _cli_list(days: int = 7) -> int:
    rows = list_recent(days=days)
    if not rows:
        print("(no pre-destructive snapshots in the last "
              f"{days} days)")
        return 0
    for r in rows:
        ts = time.strftime("%Y-%m-%d %H:%M:%S",
                           time.localtime(r.get("ts", 0)))
        print(f"{r.get('request_id', '?')}  {ts}  "
              f"shape={r.get('shape', '?')}  files={r.get('n_files', 0)}")
        print(f"    cmd: {r.get('cmd', '')[:100]}")
    return 0


def _cli_restore(request_id: str, dry_run: bool = True) -> int:
    r = restore(request_id=request_id, dry_run=dry_run)
    mode = r.get("mode")
    if mode == "not_found":
        print(f"no snapshot for request_id {request_id!r}")
        return 1
    print(f"mode: {mode}")
    for f in r.get("files", []):
        print(f"  {f.get('status', '?'):20s}  {f.get('target', '?')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage:")
        print("  python -m core.destructive_snapshot list [days]")
        print("  python -m core.destructive_snapshot preview <request_id>")
        print("  python -m core.destructive_snapshot restore <request_id>")
        return 0
    cmd = argv[0]
    if cmd == "list":
        days = int(argv[1]) if len(argv) > 1 else 7
        return _cli_list(days=days)
    if cmd == "preview" and len(argv) >= 2:
        return _cli_restore(argv[1], dry_run=True)
    if cmd == "restore" and len(argv) >= 2:
        return _cli_restore(argv[1], dry_run=False)
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Verify GREEN**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_destructive_snapshot -v
```

Expected: all ~14 tests pass.

- [ ] **Step 5: Smoke-test the CLI against the real backup dir**

```bash
cd /home/rohit/maez && .venv/bin/python -m core.destructive_snapshot list
```

Expected: `(no pre-destructive snapshots in the last 7 days)` — the backup dir doesn't exist yet and/or is empty. This confirms the CLI works and doesn't crash on empty state.

- [ ] **Step 6: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: previous-count + ~14 new = ~200 tests OK, minus the 1 pre-existing `test_fix6_followups` unrelated error.

- [ ] **Step 7: Commit**

```bash
cd /home/rohit/maez && git add core/destructive_snapshot.py tests/test_destructive_snapshot.py && git commit -m "feat(destructive_snapshot): pre-flight backup for destructive shell commands

Observed 2026-04-20: owner approved a card proposing
\`git checkout -- core/cognition_quality.py\` as a preparation step.
The checkout ran, unstaged local edits were destroyed, no backup
path existed. write_any_file has auto-backup; destructive shell
commands did not.

Adds classify/snapshot/list_recent/restore for these shapes:
git_checkout, git_restore, git_reset_hard (sentinel), rm, truncate.
CLI entry point: python -m core.destructive_snapshot {list|preview|restore} <id>

Next task wires classify+snapshot into ActionEngine._execute_action."
```

Only those two files.

---

## Task 2: Hook snapshot into ActionEngine

**Files:**
- Modify: `core/action_engine.py::_execute_action` (add pre-flight snapshot call)
- Append to: `tests/test_destructive_snapshot.py` (integration test via action engine mock)

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_destructive_snapshot.py` BEFORE the `if __name__ == "__main__":` line:

```python
class ActionEngineHooksSnapshot(unittest.TestCase):
    """When action_engine dispatches a destructive run_shell command,
    it MUST call destructive_snapshot.snapshot() before letting the
    command execute. Without this wiring, Task 1's safety layer is
    inert."""

    def test_destructive_run_shell_triggers_snapshot(self):
        from unittest.mock import patch, MagicMock
        from core.action_engine import ActionEngine

        engine = ActionEngine()
        # Stub _do_run_shell to avoid actually running any command
        engine._do_run_shell = MagicMock(return_value="(stubbed)")

        with patch("core.destructive_snapshot.snapshot") as mock_snap:
            mock_snap.return_value = {
                "manifest_path": "/tmp/fake/manifest.json",
                "n_files": 1,
                "errors": [],
            }
            engine._execute_action(
                action="run_shell",
                params={
                    "cmd": "rm /tmp/test-file-dne",
                    "reason": "cleanup",
                },
                reasoning="test",
                tier=2,
            )
        # Snapshot was invoked:
        self.assertTrue(
            mock_snap.called,
            "action_engine must call destructive_snapshot.snapshot "
            "for destructive run_shell commands"
        )
        # Invoked with the cmd that triggered it:
        call_kwargs = mock_snap.call_args.kwargs
        self.assertIn("rm /tmp/test-file-dne", call_kwargs.get("cmd", ""))
        self.assertEqual(call_kwargs.get("shape"), "rm")

    def test_non_destructive_run_shell_skips_snapshot(self):
        from unittest.mock import patch, MagicMock
        from core.action_engine import ActionEngine

        engine = ActionEngine()
        engine._do_run_shell = MagicMock(return_value="clean")

        with patch("core.destructive_snapshot.snapshot") as mock_snap:
            engine._execute_action(
                action="run_shell",
                params={
                    "cmd": "git status --short",
                    "reason": "probe",
                },
                reasoning="test",
                tier=0,
            )
        self.assertFalse(
            mock_snap.called,
            "non-destructive run_shell must NOT invoke snapshot"
        )
```

- [ ] **Step 2: Verify RED**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_destructive_snapshot.ActionEngineHooksSnapshot -v
```

Expected: `test_destructive_run_shell_triggers_snapshot` fails on the `self.assertTrue(mock_snap.called)` assertion — snapshot was not invoked. `test_non_destructive_run_shell_skips_snapshot` may PASS trivially (nothing calls snapshot yet) — that's OK.

- [ ] **Step 3: Hook into `_execute_action`**

In `core/action_engine.py`, find `def _execute_action` (around L655). Immediately BEFORE the `try:` block that dispatches via `getattr(self, f"_do_{action}")` (around L674), insert:

```python
        # Pre-flight snapshot for destructive shell commands. Fails
        # open — a snapshot error must not block the command. See
        # core/destructive_snapshot.py.
        if action == "run_shell":
            try:
                from core import destructive_snapshot as _ds
                _cmd_str = (params or {}).get("cmd", "") if isinstance(params, dict) else ""
                _cls = _ds.classify(_cmd_str)
                if _cls.get("is_destructive"):
                    _files = _cls.get("files", [])
                    # Resolve git reset --hard sentinel by running git
                    # diff --name-only at snapshot time. Other shapes
                    # provide concrete paths already.
                    if _files == ["<git-modified-tracked>"]:
                        import subprocess
                        import re as _re
                        _cwd_match = _re.search(r"git\s+-C\s+(\S+)", _cmd_str)
                        _cwd = _cwd_match.group(1) if _cwd_match else "/home/rohit/maez"
                        try:
                            _out = subprocess.check_output(
                                ["git", "-C", _cwd, "diff", "--name-only"],
                                timeout=5.0,
                            ).decode("utf-8", errors="replace")
                            _files = [str(_ds.Path(_cwd) / p) for p in _out.splitlines() if p.strip()]
                        except Exception:
                            _files = []
                    _ds.snapshot(
                        request_id=action_id or "unknown",
                        cmd=_cmd_str,
                        reason=reasoning or "",
                        files=_files,
                        shape=_cls.get("shape", ""),
                    )
            except Exception as _snap_err:
                import logging as _lg
                _lg.getLogger("maez.action_engine").warning(
                    "pre-flight snapshot failed (continuing): %s",
                    _snap_err,
                )
```

This block:
- Only runs for `action == "run_shell"` (other actions don't take arbitrary shell).
- Fails completely open — any exception is logged and the command proceeds.
- Resolves the `<git-modified-tracked>` sentinel for `git reset --hard` by running `git diff --name-only` at snapshot time.

- [ ] **Step 4: Verify GREEN**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_destructive_snapshot -v
```

Expected: all tests pass, including the two new `ActionEngineHooksSnapshot` tests.

- [ ] **Step 5: Live sanity check with real snapshot**

```bash
cd /home/rohit/maez && .venv/bin/python -c "
from core.action_engine import ActionEngine
from unittest.mock import MagicMock
e = ActionEngine()
e._do_run_shell = MagicMock(return_value='stubbed')
# This should create a snapshot of /tmp/snapshot-test.txt before 'running' the rm:
import pathlib
f = pathlib.Path('/tmp/snapshot-test.txt')
f.write_text('original content for snapshot test\n')
e._execute_action('run_shell', {'cmd': 'rm /tmp/snapshot-test.txt'}, 'test', tier=2, action_id='live-test-001')
print('snapshot should exist at memory/backups/pre_destructive/live-test-001/')
"
cd /home/rohit/maez && ls -la memory/backups/pre_destructive/live-test-001/files/tmp/ 2>&1
cd /home/rohit/maez && cat memory/backups/pre_destructive/live-test-001/manifest.json 2>&1 | head -20
```

Expected:
- The snapshot dir exists with `snapshot-test.txt` inside.
- `manifest.json` contains the cmd + the file entry.

Then clean up:

```bash
rm -rf /home/rohit/maez/memory/backups/pre_destructive/live-test-001 /tmp/snapshot-test.txt
```

- [ ] **Step 6: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: all tests OK (plus pre-existing unrelated error).

- [ ] **Step 7: Deploy + smoke**

```bash
sudo systemctl restart maez.service && sleep 4 && systemctl is-active maez && journalctl -u maez --since '10 seconds ago' --no-pager | grep -E 'surface v2 live|Cycle 1|ERROR|destructive_snapshot' | head -10
```

Expected: `active`, `surface v2 live`, `Cycle 1` running, no errors referencing `destructive_snapshot`.

- [ ] **Step 8: Commit**

```bash
cd /home/rohit/maez && git add core/action_engine.py tests/test_destructive_snapshot.py && git commit -m "feat(action_engine): pre-flight snapshot for destructive run_shell commands

Wires core.destructive_snapshot.{classify,snapshot} into
_execute_action so that any destructive run_shell (git checkout --,
git restore, git reset --hard, rm, truncate) snapshots the affected
files into memory/backups/pre_destructive/<request_id>/ before the
command runs. Manifest + per-file copy + sha256.

Fails open: snapshot errors log a warning and the command proceeds.
A failure in observability/safety backstop must never block the
command the owner approved.

Recovery: python -m core.destructive_snapshot {list|preview|restore} <id>

Last night would have been recoverable with this shipped."
```

Only those two files.

---

## Self-review

**Spec coverage:**
- ✅ Detection for 5 destructive shapes (git checkout, git restore, git reset --hard, rm, truncate).
- ✅ Snapshot + manifest persistence with per-file sha256.
- ✅ List + restore (dry-run and live) with CLI.
- ✅ Hook into action_engine for run_shell only.
- ✅ Fails open — snapshot errors never block the command.
- ❌ Not in scope (deliberate): mv -f, dd of=, shell redirect `>`, auto-expose as Maez action. Documented in the scope boundary.

**Placeholder scan:** every code block is complete, no TBDs. One heredoc-style CLI smoke-test has tmp paths that auto-clean.

**Type consistency:** `classify` returns `{is_destructive: bool, shape: str, files: list[str]}` — tests assert those keys. `snapshot` returns `{manifest_path, n_files, errors}` — tests assert manifest file. `restore` returns `{mode, files}` — tests assert mode transitions.

**Known risk note:** `shlex.split` on arbitrary LLM-emitted cmd strings can fail on unbalanced quotes. `classify` catches `ValueError` and returns non-destructive as a fail-safe. Action engine will simply not snapshot malformed commands — they'll fail at shell-exec with the usual shell error. Acceptable.

Plan is self-contained. Ready to ship via subagent-driven development.
