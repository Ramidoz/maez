# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Connection-FACTORY stores must not leak FDs either (the 'hose shape').

`pending_cards` and `self_mod_dialog` expose a `_conn()` that callers use as
`with self._conn() as conn:`. The old `_conn()` returned a RAW connection, so the
caller's `with conn:` only committed — never closed — leaking one handle per call
(the same footgun as the direct sites, just routed through a factory; Codex caught
this). `_conn()` is now a `@contextmanager` that yields, commits, and closes.

These probes call the factory many times WITHOUT forcing gc and assert handles
stay bounded.
"""

from __future__ import annotations

import glob
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.actions.action_engine import ActionTrustTracker  # noqa: E402
from core.decision.pending_cards import PendingCardStore  # noqa: E402
from core.memory.episodes import EpisodeStore  # noqa: E402
from memory.quality_tracker import QualityTracker  # noqa: E402
from skills.self_mod_dialog import SelfModDialogStore  # noqa: E402
from skills.user_accounts import UserAccounts  # noqa: E402


def _open_handles_to(db_path: Path) -> int:
    target = str(db_path)
    n = 0
    for fd in glob.glob(f"/proc/{os.getpid()}/fd/*"):
        try:
            if os.readlink(fd).startswith(target):
                n += 1
        except OSError:
            pass
    return n


class SqliteFactoryFdLeakTests(unittest.TestCase):
    def _probe(self, store, db: Path) -> int:
        baseline = _open_handles_to(db)
        for _ in range(30):
            with store._conn() as conn:  # NO gc.collect()
                conn.execute("SELECT 1")
        return _open_handles_to(db) - baseline

    def test_pending_cards_conn_factory_does_not_leak(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "cards.db"
        growth = self._probe(PendingCardStore(db_path=db), db)
        self.assertLessEqual(growth, 2, f"pending_cards _conn leaked {growth} handles over 30 uses")

    def test_self_mod_dialog_conn_factory_does_not_leak(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "selfmod.db"
        growth = self._probe(SelfModDialogStore(db_path=db), db)
        self.assertLessEqual(growth, 2, f"self_mod_dialog _conn leaked {growth} handles over 30 uses")

    def _probe_named(self, store, db: Path, factory_name: str) -> int:
        baseline = _open_handles_to(db)
        factory = getattr(store, factory_name)
        for _ in range(30):
            with factory() as conn:  # NO gc.collect()
                conn.execute("SELECT 1")
        return _open_handles_to(db) - baseline

    def test_action_trust_conn_factory_does_not_leak(self):
        # Hot path: ActionTrustTracker._conn (Pattern A — `with f() as c:`
        # callers that previously committed-but-never-closed).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "trust.db"
        growth = self._probe_named(ActionTrustTracker(db_path=str(db)), db, "_conn")
        self.assertLessEqual(growth, 2, f"action_engine _conn leaked {growth} handles over 30 uses")

    def test_episodes_connect_factory_does_not_leak(self):
        # Pattern B (close-only) — callers previously used closing(f()).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "episodes.db"
        growth = self._probe_named(EpisodeStore(db_path=str(db)), db, "_connect")
        self.assertLessEqual(growth, 2, f"episodes _connect leaked {growth} handles over 30 uses")

    def test_user_accounts_conn_factory_does_not_leak(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "accounts.db"
        growth = self._probe_named(UserAccounts(db_path=str(db)), db, "_conn")
        self.assertLessEqual(growth, 2, f"user_accounts _conn leaked {growth} handles over 30 uses")

    def test_quality_tracker_conn_factory_does_not_leak(self):
        # memory/quality_tracker is imported by core.actions.action_engine at
        # import time and is hot enough to show ResourceWarnings in ordinary
        # action tests (Codex caught this leak the first guard pass missed).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "quality.db"
        growth = self._probe_named(QualityTracker(db_path=str(db)), db, "_get_conn")
        self.assertLessEqual(growth, 2, f"quality_tracker _get_conn leaked {growth} handles over 30 uses")


if __name__ == "__main__":
    unittest.main()
