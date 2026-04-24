# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Soul file protection — 2026-04-23 gap closure.

Before this fix, a shell tool call containing `rm /home/rohit/maez/
config/soul.md` or the relative form `rm config/soul.md` would pass
the covenant layer:

  - COVENANT_PATTERNS only listed write-verb patterns (sed -i, tee, >,
    >>) against `soul.md`. `rm` wasn't in that set.
  - PROTECTED_NAMES covered llama-server, maez.service, maez_daemon,
    etc. — but not soul files.
  - COVENANT_PATHS covered memory/db, maez_daemon.py, action_engine.py,
    evolution_engine.py — but not config/soul*.md.

Result: the owner's identity ground truth could be destroyed via
`rm` under the covenant layer's nose.

The fix adds:
  - `config/soul.md`, `config/soul.base.md`, `config/soul.local.md`
    to COVENANT_PATHS (absolute-path substring match)
  - `\\bsoul(\\.base|\\.local)?\\.md\\b` to PROTECTED_NAMES
    (name-based regex; combined with DESTRUCTIVE_VERB catches
    relative paths and bare-filename forms)

These tests lock in both layers.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class SoulAbsolutePathBlocked(unittest.TestCase):
    """COVENANT_PATHS catches absolute-path references to soul files
    in any shell command, regardless of verb.

    CI-portability (2026-04-24): use `BASE_DIR` at test time rather
    than hardcoding `/home/rohit/maez/...`. In CI, `BASE_DIR` resolves
    to the runner's checkout path (e.g. `/home/runner/work/maez/maez`),
    and `COVENANT_PATHS` is derived from `BASE_DIR` at module load —
    so a literal `/home/rohit/maez/config/soul.md` never matches when
    the test runs on a non-dev machine. Earlier commit 7086d6d did the
    same pass for other CI-fragile absolute-path tests."""

    def setUp(self):
        from core.action_engine import ActionEngine, BASE_DIR
        self.engine = ActionEngine.__new__(ActionEngine)
        self.soul_abs = str(BASE_DIR / "config" / "soul.md")
        self.soul_base_abs = str(BASE_DIR / "config" / "soul.base.md")
        self.soul_local_abs = str(BASE_DIR / "config" / "soul.local.md")

    def _assert_blocked(self, cmd: str):
        from core.action_engine import ForbiddenActionError
        with self.assertRaisesRegex(ForbiddenActionError, "COVENANT"):
            self.engine._check_forbidden("run_shell", {"cmd": cmd})

    def test_rm_soul_abs_path(self):
        self._assert_blocked(f"rm {self.soul_abs}")

    def test_rm_soul_base_abs_path(self):
        self._assert_blocked(f"rm {self.soul_base_abs}")

    def test_rm_soul_local_abs_path(self):
        self._assert_blocked(f"rm {self.soul_local_abs}")


class SoulRelativePathBlocked(unittest.TestCase):
    """PROTECTED_NAMES + DESTRUCTIVE_VERB catches relative-path and
    bare-filename forms of destructive commands targeting soul."""

    def setUp(self):
        from core.action_engine import ActionEngine
        self.engine = ActionEngine.__new__(ActionEngine)

    def _assert_blocked(self, cmd: str):
        from core.action_engine import ForbiddenActionError
        with self.assertRaisesRegex(ForbiddenActionError, "COVENANT"):
            self.engine._check_forbidden("run_shell", {"cmd": cmd})

    def test_rm_soul_rel_config(self):
        self._assert_blocked("rm config/soul.md")

    def test_rm_soul_bare_name(self):
        self._assert_blocked("rm soul.md")

    def test_mv_soul_elsewhere(self):
        self._assert_blocked("mv config/soul.md /tmp/trash/")

    def test_cp_soul_overwrite(self):
        # Copy-from-attacker-blob onto soul.md is the same class
        self._assert_blocked("cp /tmp/evil.md config/soul.md")

    def test_tee_to_soul(self):
        self._assert_blocked("echo 'pwned' | tee config/soul.md")

    def test_redirect_to_soul(self):
        self._assert_blocked("echo 'pwned' > config/soul.md")

    def test_sed_inplace_soul(self):
        self._assert_blocked("sed -i 's/foo/bar/' config/soul.md")

    def test_cd_and_rm(self):
        self._assert_blocked("cd config && rm soul.md")

    def test_rm_soul_base_relative(self):
        self._assert_blocked("rm config/soul.base.md")

    def test_rm_soul_local_relative(self):
        self._assert_blocked("rm config/soul.local.md")


class SoulReadViaRelativePathAllowed(unittest.TestCase):
    """Reading soul via RELATIVE path + non-destructive verb is allowed.
    PROTECTED_NAMES matches the bare filename, but DESTRUCTIVE_VERB
    requires a change-state verb, which `cat`/`grep`/`wc` are not.
    So relative-path reads pass.

    ABSOLUTE-path references to soul files are ALWAYS blocked by
    COVENANT_PATHS (bare substring match, same as maez_daemon.py and
    action_engine.py today) — regardless of verb. This is intentional
    and consistent with how other high-sensitivity files are protected.
    The daemon's own soul reads (`_load_soul` → `SOUL_PATH.read_text()`)
    bypass the shell layer entirely, so this doesn't hurt operation."""

    def setUp(self):
        from core.action_engine import ActionEngine, BASE_DIR
        self.engine = ActionEngine.__new__(ActionEngine)
        self.soul_abs = str(BASE_DIR / "config" / "soul.md")

    def _assert_allowed(self, cmd: str):
        self.assertIsNone(self.engine._check_forbidden("run_shell", {"cmd": cmd}))

    def _assert_blocked_absolute_path(self, cmd: str):
        from core.action_engine import ForbiddenActionError
        with self.assertRaisesRegex(ForbiddenActionError, "COVENANT"):
            self.engine._check_forbidden("run_shell", {"cmd": cmd})

    def test_cat_soul_relative_allowed(self):
        self._assert_allowed("cat config/soul.md")

    def test_grep_soul_relative_allowed(self):
        # Use a benign pattern — grepping "HARD CONSTRAINTS" itself
        # triggers COVENANT_PATTERNS (soul text quoted in shell is a
        # manipulation signal). Grepping a neutral word is fine.
        self._assert_allowed("grep -n '^##' config/soul.md")

    def test_wc_soul_relative_allowed(self):
        self._assert_allowed("wc -l config/soul.md")

    def test_cat_soul_absolute_path_blocked(self):
        # Consistent with existing protection for daemon/maez_daemon.py
        # and core/action_engine.py — any mention of the absolute path
        # is refused. Daemon's own file reads don't go through shell.
        # Path constructed from BASE_DIR so this test passes in CI
        # (where BASE_DIR != /home/rohit/maez) as well as locally.
        self._assert_blocked_absolute_path(f"cat {self.soul_abs}")


if __name__ == "__main__":
    unittest.main()
