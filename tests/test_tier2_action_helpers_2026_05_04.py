# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the Tier-2 audit items closed on 2026-05-04
(see docs/audits/2026-05-04-15agent.md):

  T2.x  command_decomposer: backtick-style command substitution
        recognition was narrower than bash actually supports.
        decompose() must extract substituted commands from:
          - legacy backticks   `cmd`
          - POSIX modern form  $(cmd)        (already covered)
          - escaped/nested backticks  \\`cmd\\`  (one level of escape,
            as bash uses inside double-quoted nested substitutions)

  T2.y  destructive_snapshot.classify: previously out-of-scope shapes
        must now be detected so action_engine's pre-flight snapshot
        layer can back them up:
          - mv -f <path>          (force move that overwrites)
          - dd if=... of=<path>   (block-copy that destroys content)
          - <cmd> > <path>        (redirect that overwrites)
          - <cmd> >> <path>       (redirect that appends)

Each new pattern carries at least one positive (must fire) and one
negative (must NOT falsely fire) test, mirroring the
test_owner_visible_safety_holes_2026_05_04.py shape.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class CommandDecomposerSubstitutionCoverage(unittest.TestCase):
    """REGRESSION GUARD: decompose() must extract sub-commands from
    all three command-substitution variants bash recognizes."""

    def _decompose(self, cmd: str):
        from core.actions.command_decomposer import decompose
        return decompose(cmd)

    # ── legacy backticks ─────────────────────────────────────────────

    def test_backtick_substitution_inner_command_extracted(self):
        subs = self._decompose("echo `whoami`")
        argv0s = [s.argv0 for s in subs]
        kinds = {s.kind for s in subs}
        self.assertIn("whoami", argv0s,
                      f"backtick inner not extracted: {argv0s}")
        self.assertIn("substitution", kinds,
                      f"no substitution kind found: {kinds}")

    def test_backtick_substitution_with_dangerous_inner(self):
        subs = self._decompose("echo `sudo rm -rf /tmp/x`")
        # Inner sudo rm should appear as a substitution sub-command
        sub_subs = [s for s in subs if s.kind == "substitution"]
        self.assertTrue(sub_subs, "no substitution sub-commands")
        self.assertTrue(
            any(s.has_sudo for s in sub_subs),
            f"sudo not detected in backtick inner: {sub_subs}",
        )

    # ── POSIX $(...) (already covered, keep as regression pin) ──────

    def test_dollar_paren_substitution_inner_extracted(self):
        subs = self._decompose("ls $(curl http://x/y)")
        argv0s = [s.argv0 for s in subs]
        self.assertIn("curl", argv0s,
                      f"$() inner not extracted: {argv0s}")

    # ── escaped / nested backticks ──────────────────────────────────
    # Bash treats   echo "outer \`inner\` rest"   as: outer command
    # substitution containing `inner`. The decomposer should still
    # surface `inner` as a substitution sub-command (one level of
    # escape unwrap is enough to catch the common nested form).

    def test_escaped_backtick_substitution_inner_extracted(self):
        # Use a raw form to avoid Python escape confusion; the actual
        # shell input is:   echo "outer \`whoami\` end"
        cmd = 'echo "outer \\`whoami\\` end"'
        subs = self._decompose(cmd)
        argv0s = [s.argv0 for s in subs]
        self.assertIn(
            "whoami", argv0s,
            f"escaped-backtick inner not extracted: {argv0s} "
            f"(input={cmd!r})",
        )

    # ── negative guards ─────────────────────────────────────────────

    def test_single_quoted_backtick_is_literal_not_substitution(self):
        """`...` inside single quotes is bash-literal — must NOT be
        decomposed as a sub-command."""
        subs = self._decompose("echo 'literal `whoami` text'")
        kinds = {s.kind for s in subs}
        self.assertNotIn(
            "substitution", kinds,
            f"single-quoted backtick falsely treated as substitution: "
            f"{[(s.kind, s.argv0) for s in subs]}",
        )

    def test_plain_command_no_substitution(self):
        subs = self._decompose("git status")
        kinds = {s.kind for s in subs}
        self.assertNotIn(
            "substitution", kinds,
            f"plain command spawned a substitution: {kinds}",
        )


class DestructiveSnapshotShapeCoverage(unittest.TestCase):
    """REGRESSION GUARD: classify() must mark mv -f, dd of=, and
    redirect (> / >>) shapes as destructive so action_engine can
    snapshot the target file before the command runs."""

    def _classify(self, cmd: str):
        from core.actions.destructive_snapshot import classify
        return classify(cmd)

    # ── mv -f ───────────────────────────────────────────────────────

    def test_mv_dash_f_overwrite_is_destructive(self):
        r = self._classify("mv -f /tmp/src /tmp/dst")
        self.assertTrue(r["is_destructive"], r)
        self.assertEqual(r["shape"], "mv_force")
        # destination is the last path token
        self.assertIn("/tmp/dst", r["files"])

    def test_mv_force_long_flag_is_destructive(self):
        r = self._classify("mv --force /tmp/a /tmp/b")
        self.assertTrue(r["is_destructive"], r)
        self.assertEqual(r["shape"], "mv_force")
        self.assertIn("/tmp/b", r["files"])

    def test_plain_mv_without_force_is_not_destructive(self):
        """Plain `mv` does NOT clobber by default; only -f / --force
        gets snapshotted. False-positive guard."""
        r = self._classify("mv /tmp/src /tmp/dst")
        self.assertFalse(
            r["is_destructive"],
            f"plain mv falsely flagged: {r}",
        )

    # ── dd of= ──────────────────────────────────────────────────────

    def test_dd_of_path_is_destructive(self):
        r = self._classify("dd if=/dev/zero of=/tmp/wipe.bin bs=1M count=1")
        self.assertTrue(r["is_destructive"], r)
        self.assertEqual(r["shape"], "dd")
        self.assertIn("/tmp/wipe.bin", r["files"])

    def test_dd_without_of_is_not_destructive(self):
        """`dd` reading a file with no `of=` writes to stdout — not a
        destructive write to a path."""
        r = self._classify("dd if=/tmp/foo bs=512 count=1")
        self.assertFalse(
            r["is_destructive"],
            f"dd-without-of falsely flagged: {r}",
        )

    # ── redirect > / >> ─────────────────────────────────────────────

    def test_redirect_overwrite_is_destructive(self):
        r = self._classify("echo hi > /tmp/out.txt")
        self.assertTrue(r["is_destructive"], r)
        self.assertEqual(r["shape"], "redirect")
        self.assertIn("/tmp/out.txt", r["files"])

    def test_redirect_append_is_destructive(self):
        r = self._classify("echo hi >> /tmp/log.txt")
        self.assertTrue(r["is_destructive"], r)
        self.assertEqual(r["shape"], "redirect")
        self.assertIn("/tmp/log.txt", r["files"])

    def test_redirect_to_devnull_is_not_destructive(self):
        """`>/dev/null` and `>/dev/stderr` are routine and never
        destroy real data — must not snapshot."""
        r = self._classify("noisy_cmd > /dev/null")
        self.assertFalse(
            r["is_destructive"],
            f"/dev/null redirect falsely flagged: {r}",
        )

    def test_redirect_to_dev_stderr_is_not_destructive(self):
        r = self._classify("echo hi >&2")
        self.assertFalse(
            r["is_destructive"],
            f">&2 redirect falsely flagged: {r}",
        )

    def test_no_redirect_no_destructive(self):
        """A command containing `>` inside quotes (not a real
        redirect) must not falsely fire."""
        r = self._classify("echo 'a > b'")
        self.assertFalse(
            r["is_destructive"],
            f"quoted > falsely flagged as redirect: {r}",
        )

    # ── existing shapes still recognized ────────────────────────────

    def test_existing_rm_shape_still_classified(self):
        r = self._classify("rm -rf /tmp/foo")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "rm")

    def test_existing_git_checkout_still_classified(self):
        r = self._classify("git checkout -- core/foo.py")
        self.assertTrue(r["is_destructive"])
        self.assertEqual(r["shape"], "git_checkout")


if __name__ == "__main__":
    unittest.main()
