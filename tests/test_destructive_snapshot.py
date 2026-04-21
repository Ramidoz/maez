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
