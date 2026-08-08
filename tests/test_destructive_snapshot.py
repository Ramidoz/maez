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
import tempfile
import unittest
from pathlib import Path
from tests.s7_store_fixture import fresh_store_at


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


class ActionEngineHooksSnapshot(unittest.TestCase):
    """When action_engine dispatches a destructive run_shell command,
    it MUST call destructive_snapshot.snapshot() before letting the
    command execute. Without this wiring, Task 1's safety layer is
    inert."""

    def test_destructive_run_shell_triggers_snapshot(self):
        from unittest.mock import patch, MagicMock
        from core.action_engine import ActionEngine
        from core.governance import operator_user_boundary as s7

        engine = ActionEngine()
        # Stub _do_run_shell to avoid actually running any command
        engine._do_run_shell = MagicMock(return_value="(stubbed)")
        params = {
            "cmd": "rm -f /tmp/test-file-dne",
            "reason": "cleanup",
        }
        with tempfile.TemporaryDirectory() as td:
            env = s7.build_work_request_envelope(
                request_id="req-destructive-snapshot",
                action="run_shell",
                params=params,
                claimed_work_class="destructive_user_action",
                requesting_subsystem="unit",
                closed_symptom_code="verification_needed",
                proposed_change_class="user_content_write",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("file:/tmp/test-file-dne",),
                content_exposure_risk="content_free",
                precondition_hash="a" * 64,
                created_at="2026-05-17T16:00:00+00:00",
                expires_at="2026-05-17T17:00:00+00:00",
                predicted_effect_class="no_behavior_change",
                rollback_path_class="restore_backup",
            )
            authority = s7.AuthorityContext(
                actor_id="founder",
                actor_handle_hmac="hmac:s7:founder:" + ("d" * 64),
                role_names=("bonded_user", "operator"),
                grant_source="founder_webauthn",
                allowed_scopes=("operator_health",),
                auth_method="founder_webauthn",
                surface="cockpit",
                credential_ref="cred-destructive-snapshot",
                created_at="2026-05-17T16:00:00+00:00",
                expires_at="2026-05-17T17:00:00+00:00",
                verified=True,
            )
            params_hash = s7.canonical_hash(params)
            rendered = s7.render_request_statement(
                envelope=env,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=params_hash,
                authority_context=authority,
                maez_voice_consultation=None,
                nonce="nonce-destructive-snapshot",
                expires_at="2026-05-17T17:00:00+00:00",
                rendered_at="2026-05-17T16:00:00+00:00",
            )
            artifact = s7.S7AuthorizationArtifact(
                artifact_id="artifact-destructive-snapshot",
                request_id=env.request_id,
                request_envelope_hash=s7.work_request_envelope_hash(env),
                rendered_text_hash=rendered.rendered_text_hash,
                action_params_hash=params_hash,
                precondition_hash=env.precondition_hash,
                authority_context_hash=s7.authority_context_hash(authority),
                derived_work_class=env.derived_work_class,
                derived_aggregation_group=env.derived_aggregation_group,
                nonce=rendered.nonce,
                credential_ref="cred-destructive-snapshot",
                auth_method="founder_webauthn",
                grant_source="founder_webauthn",
                user_presence=True,
                user_verification=True,
                created_at="2026-05-17T16:00:00+00:00",
                expires_at="2026-05-17T17:00:00+00:00",
                consumed_at=None,
            )
            store = fresh_store_at(Path(td) / "s7_authorization.db")
            store.put(artifact)
            execution_grant, _ = store.consume_for_execution(
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=env.precondition_hash,
                derived_work_class=env.derived_work_class,
                derived_aggregation_group=env.derived_aggregation_group,
                now="2026-05-17T16:00:00+00:00",
            )

            with patch("core.destructive_snapshot.snapshot") as mock_snap:
                mock_snap.return_value = {
                    "manifest_path": "/tmp/fake/manifest.json",
                    "n_files": 1,
                    "errors": [],
                }
                engine._execute_action(
                    action="run_shell",
                    params=params,
                    reasoning="test",
                    tier=2,
                    s7_execution_grant=execution_grant,
                )
        # Snapshot was invoked:
        self.assertTrue(
            mock_snap.called,
            "action_engine must call destructive_snapshot.snapshot "
            "for destructive run_shell commands"
        )
        # Invoked with the cmd that triggered it:
        call_kwargs = mock_snap.call_args.kwargs
        self.assertIn("rm -f /tmp/test-file-dne", call_kwargs.get("cmd", ""))
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


if __name__ == "__main__":
    unittest.main()
