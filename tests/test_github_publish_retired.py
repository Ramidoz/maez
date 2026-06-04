# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""v0.1: the journal path must not perform an unattended GitHub publish / push.

Public exposure is a deliberate owner action, not a cron.
"""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class JournalDoesNotAutoPublishTests(unittest.TestCase):
    def test_write_journal_entry_does_not_call_publish_nightly(self):
        from daemon.maez_daemon import MaezDaemon

        src = inspect.getsource(MaezDaemon._write_journal_entry)
        self.assertNotIn("publish_nightly", src)
        self.assertNotIn("GitHubPublisher", src)

    def test_daemon_module_has_no_unattended_publish_call(self):
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon)
        self.assertNotIn("publisher.publish_nightly()", src)
        self.assertNotIn("GitHubPublisher().publish_nightly()", src)


if __name__ == "__main__":
    unittest.main()
