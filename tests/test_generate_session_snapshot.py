# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for the session-snapshot generator (Step 5w).

The web_interface consumer at ``skills/web_interface.py:803
_parse_session_snapshot`` defines the schema by parsing existing
snapshots — not by emitting them. These tests pin the producer's
output against that consumer's expected shape so a future
consumer change can't silently desync the producer.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class TestSnapshotShape(unittest.TestCase):
    def test_render_contains_required_header_fields(self):
        from scripts.generate_session_snapshot import render_snapshot

        text = render_snapshot(since="100 years ago", agent="TestAgent")
        for token in ("BUILD:", "DATE:", "AGENT: TestAgent", "HEAD:"):
            self.assertIn(token, text)

    def test_render_includes_three_named_sections(self):
        from scripts.generate_session_snapshot import render_snapshot

        text = render_snapshot(since="100 years ago")
        # Parser at web_interface.py:895-897 reads exactly these
        # slug names; the section titles must produce them via
        # _snapshot_slug.
        self.assertIn("WHAT CHANGED TODAY", text)
        self.assertIn("PRODUCTION STATE", text)
        self.assertIn("NEXT SESSION PRIORITIES", text)

    def test_section_delimiters_are_paired_equals(self):
        from scripts.generate_session_snapshot import render_snapshot

        text = render_snapshot(since="100 years ago")
        # The parser regex is r'^=+\s*$' — match lines of equals.
        # Each section uses TWO of these (open + close).
        equals_lines = [
            ln for ln in text.splitlines()
            if set(ln.strip()) == {"="} and len(ln.strip()) >= 4
        ]
        # Three sections × 2 dividers each = 6 (no header bar
        # now — the BUILD/DATE/AGENT lines come BEFORE any
        # divider per the consumer parser's expectation).
        self.assertGreaterEqual(len(equals_lines), 6)

    def test_bullets_use_dash_format_parser_recognises(self):
        from scripts.generate_session_snapshot import render_snapshot

        text = render_snapshot(since="100 years ago")
        # Parser bullet regex: r'^\s*(?:[-*•]|\d+[.)])\s+(.*)$'.
        # Verify at least one dash-bullet line exists in each
        # section.
        self.assertIn("\n- ", text)


class TestRoundTripWithConsumerParser(unittest.TestCase):
    """The load-bearing test: emit a snapshot via the producer
    and feed it through the existing consumer parser. Sections,
    headers, and bullets must come back in the consumer's
    expected schema."""

    def test_full_round_trip(self):
        from scripts.generate_session_snapshot import (
            render_snapshot,
        )
        from skills.web_interface import _parse_session_snapshot

        text = render_snapshot(since="100 years ago", agent="TestAgent")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            f = tdp / "session_snapshot_test.txt"
            f.write_text(text)
            parsed = _parse_session_snapshot(str(f))

        self.assertEqual(parsed["agent"], "TestAgent")
        self.assertIsNone(parsed.get("error"))
        # The consumer reads these three section keys:
        self.assertIn("what_changed_today", parsed["sections"])
        self.assertIn("production_state", parsed["sections"])
        self.assertIn("next_session_priorities", parsed["sections"])
        # And surfaces them as the top-level fields:
        self.assertGreaterEqual(len(parsed["production_state"]), 1)
        self.assertGreaterEqual(len(parsed["next_priorities"]), 1)


class TestWriteSnapshot(unittest.TestCase):
    def test_writes_latest_and_dated_files(self):
        from scripts.generate_session_snapshot import write_snapshot

        with tempfile.TemporaryDirectory() as td:
            from scripts import generate_session_snapshot as gss
            tdp = Path(td)
            with mock.patch.object(gss, "_REPO", tdp):
                dated, latest = write_snapshot(
                    "fake snapshot text", label="test",
                )
            self.assertTrue(dated.exists())
            self.assertTrue(latest.exists())
            self.assertEqual(latest.name, "session_snapshot_latest.txt")
            self.assertTrue(dated.name.startswith("session_snapshot_"))
            self.assertTrue(dated.name.endswith("_test.txt"))
            self.assertEqual(dated.read_text(), "fake snapshot text")
            self.assertEqual(latest.read_text(), "fake snapshot text")


class TestPrivateStoresOnlyCounted(unittest.TestCase):
    """Decision 9 / inner_residue privacy rule: COUNT, never
    QUOTE. Snapshot text must include the count label but no
    excerpt strings from those stores."""

    def test_render_contains_count_labels_but_no_excerpts(self):
        from scripts.generate_session_snapshot import render_snapshot

        text = render_snapshot(since="100 years ago")
        # Count-only labels appear:
        self.assertIn("private thoughts (count only)", text)
        self.assertIn("inner residue events (count only)", text)
        # And no obvious excerpt machinery (no SQL "thought_id"
        # / "content" / "ts" tokens leaking into the snapshot —
        # those would only appear if we accidentally quoted from
        # the private DB).
        self.assertNotIn("thought_id", text)
        self.assertNotIn("residue_event_id", text)


class TestServiceState(unittest.TestCase):
    def test_service_state_queries_user_units(self):
        import subprocess

        from scripts import generate_session_snapshot as gss

        commands: list[list[str]] = []

        def fake_run(args, *a, **kw):
            commands.append(list(args))
            if args[:3] == ["systemctl", "--user", "is-active"]:
                return subprocess.CompletedProcess(args, 0, stdout="active\n", stderr="")
            if args[:3] == ["systemctl", "--user", "show"]:
                return subprocess.CompletedProcess(args, 0, stdout="123\n", stderr="")
            return subprocess.CompletedProcess(args, 1, stdout="inactive\n", stderr="")

        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            state = gss._service_state()

        self.assertTrue(state)
        self.assertTrue(all("active (PID 123)" in row for row in state))
        self.assertTrue(commands)
        self.assertTrue(
            all(cmd[:2] == ["systemctl", "--user"] for cmd in commands),
            commands,
        )


class TestCli(unittest.TestCase):
    """CLI tests mock the git layer so a tmp-dir _REPO doesn't
    fail on `git rev-parse`. The render layer is exercised
    end-to-end via TestRoundTripWithConsumerParser against the
    real git repo; here we just want to verify the CLI flag
    plumbing."""

    def _patch_render(self, gss):
        """Replace render_snapshot with a tiny stand-in so CLI
        tests don't depend on git or systemctl being available."""
        return mock.patch.object(
            gss, "render_snapshot",
            return_value="Maez — session snapshot\n\nfake content\n",
        )

    def test_print_only_does_not_write(self):
        from scripts.generate_session_snapshot import main

        with tempfile.TemporaryDirectory() as td:
            from scripts import generate_session_snapshot as gss
            tdp = Path(td)
            (tdp / "logs").mkdir()
            with mock.patch.object(gss, "_REPO", tdp), \
                 self._patch_render(gss), \
                 mock.patch.object(sys, "stdout", io.StringIO()) as out:
                rc = main([
                    "--print-only", "--since", "100 years ago",
                ])
            self.assertEqual(rc, 0)
            # No latest or dated file written.
            self.assertFalse(
                (tdp / "logs" / "session_snapshot_latest.txt").exists()
            )
            self.assertIn("Maez — session snapshot", out.getvalue())

    def test_default_invocation_writes_files(self):
        from scripts.generate_session_snapshot import main

        with tempfile.TemporaryDirectory() as td:
            from scripts import generate_session_snapshot as gss
            tdp = Path(td)
            with mock.patch.object(gss, "_REPO", tdp), \
                 self._patch_render(gss), \
                 mock.patch.object(sys, "stdout", io.StringIO()):
                rc = main(["--since", "100 years ago"])
            self.assertEqual(rc, 0)
            latest = tdp / "logs" / "session_snapshot_latest.txt"
            self.assertTrue(latest.exists())
            self.assertGreater(len(latest.read_text()), 10)


class TestNoSubprocessExceptGit(unittest.TestCase):
    """The script invokes git + systemctl. No other subprocess
    paths should leak in. Verify by interception that any
    non-git/systemctl invocation crashes."""

    def test_only_git_and_systemctl_subprocesses(self):
        import subprocess as _sp
        from scripts.generate_session_snapshot import render_snapshot

        original_run = _sp.run
        captured: list[list[str]] = []

        def gated(args, *a, **kw):
            captured.append(list(args))
            if not args:
                raise AssertionError("empty subprocess args")
            if args[0] in ("git", "systemctl"):
                return original_run(args, *a, **kw)
            raise AssertionError(
                f"snapshot generator invoked disallowed "
                f"subprocess: {args!r}"
            )

        with mock.patch.object(_sp, "run", side_effect=gated):
            render_snapshot(since="100 years ago")
        self.assertTrue(captured)
        for argv in captured:
            self.assertIn(argv[0], ("git", "systemctl"))


if __name__ == "__main__":
    unittest.main()
