# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Restore-drill timer units.

The scheduled restore drill is welfare infrastructure: failures must be
visible as failed systemd units, and the installer must not leave unresolved
template placeholders in the rendered unit files.
"""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _render(template_text: str) -> str:
    return (
        template_text.replace("__MAEZ_HOME__", "/home/test/maez")
        .replace("__MAEZ_USER__", "testuser")
        .replace("__MAEZ_UID__", "4242")
        .replace("__MAEZ_HOME_USER__", "/home/test")
    )


class RestoreDrillTimerTests(unittest.TestCase):
    def test_service_template_runs_restore_smoke_and_surfaces_failure(self):
        path = REPO_ROOT / "scripts" / "maez-backup-drill.template.service"
        self.assertTrue(path.is_file(), "restore drill service template must exist")
        text = path.read_text(encoding="utf-8")
        rendered = _render(text)

        self.assertIn("After=maez-backup.service", text)
        self.assertIn("-m scripts.backup.drill --smoke", rendered)
        self.assertIn("MAEZ_BACKUP_ROOT=/home/test/maez-backups", rendered)
        self.assertIn("StandardOutput=append:/home/test/maez/logs/backup_drill.log", rendered)
        self.assertIn("StandardError=append:/home/test/maez/logs/backup_drill.log", rendered)
        self.assertIn("non-zero exit marks the service failed", text)
        self.assertNotIn("__MAEZ_", rendered)

    def test_timer_template_runs_daily_after_midnight_backup(self):
        path = REPO_ROOT / "scripts" / "maez-backup-drill.template.timer"
        self.assertTrue(path.is_file(), "restore drill timer template must exist")
        text = path.read_text(encoding="utf-8")
        rendered = _render(text)

        self.assertIn("OnCalendar=*-*-* 03:00:00", text)
        self.assertIn("Persistent=true", text)
        self.assertIn("Unit=maez-backup-drill.service", text)
        self.assertNotIn("__MAEZ_", rendered)

    def test_install_sh_renders_template_timers_and_home_user_placeholder(self):
        text = (REPO_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

        self.assertIn("*.template.service", text)
        self.assertIn("*.template.timer", text)
        self.assertIn("__MAEZ_HOME_USER__", text)
        self.assertIn("MAEZ_HOME_USER=", text)

    def test_install_sh_enables_restore_drill_timer_without_enabling_backup_timer(self):
        text = (REPO_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

        self.assertIn("systemctl --user enable --now maez-backup-drill.timer", text)
        self.assertIn("sudo systemctl enable --now maez-backup-drill.timer", text)
        self.assertNotIn("enable --now maez-backup.timer", text)


if __name__ == "__main__":
    unittest.main()
