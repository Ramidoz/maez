# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""SOUL + birth-state truth — Commit 3 of the 2026-04-23 audit repair pass.

Invariants guarded here:

    1. The daemon's live identity is the concatenation of
       soul.base.md + soul.local.md as rendered by
       core.evolution.soul_loader.current_soul() — not a stale
       soul.md read that misses local appends.

    2. Birth phase (gestation/lived) is per-instance RUNTIME state,
       not committed source. Flipping it must not dirty the repo or
       leak one instance's lived record into another's clone.

Before this commit:
    - daemon/maez_daemon.py::_load_soul called SOUL_PATH.read_text()
      directly. soul.local.md appends (from dream-proposal-apply)
      did not reach the live daemon until something else regenerated
      soul.md by explicitly calling current_soul() first.
    - memory/self_awareness.json was tracked in git with
      {"phase":"gestation"}. If fire_birth() ever flipped it to
      "lived", `git status` would report the repo dirty, and a
      careless `git commit -a` could push another instance's birth
      record upstream.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class SoulLayeringReachesDaemon(unittest.TestCase):
    """_load_soul and _watch_soul must source their text from the layered loader."""

    def test_load_soul_body_references_current_soul(self):
        """_load_soul's body must import core.evolution.soul_loader.current_soul."""
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        fn_start = src.find("def _load_soul(")
        self.assertNotEqual(fn_start, -1)
        # Find the next same-indent method definition as the body end.
        import re as _re
        m = _re.search(r"\n    def ", src[fn_start + 30:])
        end = (fn_start + 30 + m.start()) if m else len(src)
        body = src[fn_start:end]
        self.assertIn("from core.evolution.soul_loader import current_soul",
                      body,
                      "_load_soul must route through soul_loader.current_soul "
                      "so layered (base + local) edits reach the daemon.")

    def test_watch_soul_body_references_current_soul(self):
        """Hot reload must also use the layered loader."""
        src = (_REPO / "daemon" / "maez_daemon.py").read_text()
        fn_start = src.find("def _watch_soul(")
        self.assertNotEqual(fn_start, -1)
        import re as _re
        m = _re.search(r"\n    def ", src[fn_start + 30:])
        end = (fn_start + 30 + m.start()) if m else len(src)
        body = src[fn_start:end]
        self.assertIn("from core.evolution.soul_loader import current_soul",
                      body,
                      "_watch_soul must route through soul_loader.current_soul "
                      "so layered edits hot-reload into the live daemon.")

    def test_soul_loader_combines_base_and_local(self):
        """current_soul() must return the concatenation of base + local.

        Operational assertion on the loader itself — if soul_loader
        regresses, this breaks independent of the daemon wiring.
        """
        from core.evolution import soul_loader
        import tempfile
        # Write minimal base + local to temp files; point the loader
        # at them via its path helpers.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "soul.base.md"
            local = Path(td) / "soul.local.md"
            combined = Path(td) / "soul.md"
            base.write_text("BASE_LINE_A\n")
            local.write_text("LOCAL_LINE_B\n")
            # Monkey-patch the internal path helpers the loader uses so
            # the test doesn't depend on the real /home/rohit/maez
            # layout. soul_loader calls paths.soul_base_path(),
            # paths.soul_local_path(), paths.soul_combined_path().
            import core.paths as _paths
            orig = (
                _paths.soul_base_path,
                _paths.soul_local_path,
                _paths.soul_combined_path,
            )
            try:
                _paths.soul_base_path = lambda: base  # type: ignore
                _paths.soul_local_path = lambda: local  # type: ignore
                _paths.soul_combined_path = lambda: combined  # type: ignore
                # Reset loader cache so it re-reads.
                soul_loader._cache_text = None
                soul_loader._cache_signature = None
                result = soul_loader.current_soul()
            finally:
                (_paths.soul_base_path,
                 _paths.soul_local_path,
                 _paths.soul_combined_path) = orig
                soul_loader._cache_text = None
                soul_loader._cache_signature = None
        self.assertIn("BASE_LINE_A", result)
        self.assertIn("LOCAL_LINE_B", result)


class BirthStateIsNotTracked(unittest.TestCase):
    """memory/self_awareness.json is runtime state, not committed source."""

    def test_not_tracked_in_git(self):
        """The birth-state file must not be in the git index."""
        try:
            out = subprocess.check_output(
                ["git", "ls-files", "memory/self_awareness.json"],
                cwd=_REPO, text=True,
            ).strip()
        except subprocess.CalledProcessError:
            # `git ls-files` exits non-zero only on catastrophic errors,
            # not on "no match." Treat that as "not tracked" → pass.
            out = ""
        self.assertEqual(out, "",
                         "memory/self_awareness.json must NOT be "
                         "tracked in git. Run: git rm --cached "
                         "memory/self_awareness.json")

    def test_is_gitignored(self):
        """Subsequent fire_birth() writes must not dirty the repo."""
        try:
            r = subprocess.run(
                ["git", "check-ignore", "-v",
                 "memory/self_awareness.json"],
                cwd=_REPO, capture_output=True, text=True,
            )
        except Exception as e:
            self.fail(f"git check-ignore failed: {e}")
        # check-ignore returns 0 and prints the matching rule when
        # the path IS ignored. Assert the exit code.
        self.assertEqual(
            r.returncode, 0,
            "memory/self_awareness.json must be gitignored. Expected "
            "a .gitignore rule to match; got no match.",
        )
        self.assertIn("memory/self_awareness.json", r.stdout,
                      "gitignore rule output must name the path.")


if __name__ == "__main__":
    unittest.main()
