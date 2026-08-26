# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Owner decision 2026-08-26 (#1, explicit yes): maez-web must SEE the
ledger activation flag. Verified 2026-08-24: the unit loaded no
EnvironmentFile while the birth checklist lands MAEZ_LEDGER_WRITES=1 in
model.env — post-birth web turns would have been silently omitted."""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


class WebLedgerEnvDropinTests(unittest.TestCase):
    def test_repo_carries_the_dropin(self):
        dropin = _REPO / "systemd" / "maez-web.service.d" / "40-ledger-writes.conf"
        self.assertTrue(dropin.exists(), "the drop-in is deployment source of truth")
        text = dropin.read_text()
        self.assertIn("EnvironmentFile=-%h/.config/maez/model.env", text)
        self.assertIn("[Service]", text)

    def test_installed_copy_matches_repo(self):
        installed = Path.home() / ".config/systemd/user/maez-web.service.d/40-ledger-writes.conf"
        if not installed.exists():
            self.skipTest("not installed on this host (repo copy is the contract)")
        repo = (_REPO / "systemd" / "maez-web.service.d" / "40-ledger-writes.conf").read_text()
        self.assertEqual(installed.read_text(), repo, "installed drop-in drifted from repo")


if __name__ == "__main__":
    unittest.main()
