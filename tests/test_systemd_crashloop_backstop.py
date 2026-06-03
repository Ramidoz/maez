# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Systemd must bound liveness-triggered restart loops and alert the owner."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


class MaezServiceCrashloopBackstopTests(unittest.TestCase):
    def test_maez_template_bounds_restart_loop_and_routes_onfailure_alert(self):
        text = Path("scripts/maez.template.service").read_text(encoding="utf-8")

        self.assertIn("StartLimitIntervalSec=10min", text)
        self.assertIn("StartLimitBurst=3", text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn("RestartSec=10", text)
        self.assertIn("OnFailure=maez-crashloop-alert@%N.service", text)

    def test_crashloop_alert_service_is_oneshot_and_uses_local_notifier_script(self):
        text = Path("scripts/maez-crashloop-alert@.template.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("Type=oneshot", text)
        self.assertIn("EnvironmentFile=-__MAEZ_HOME__/config/secrets.local.env", text)
        self.assertIn("EnvironmentFile=-/home/__MAEZ_USER__/.config/maez/model.env", text)
        self.assertIn(
            "ExecStart=__MAEZ_HOME__/.venv/bin/python "
            "__MAEZ_HOME__/scripts/maez_crashloop_alert.py %i",
            text,
        )
        self.assertNotIn("Restart=on-failure", text)

    def test_alert_script_is_content_free_and_uses_service_card_notifier(self):
        path = Path("scripts/maez_crashloop_alert.py")
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        string_literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

        self.assertIn("from skills.dev_notifier import send_service_card", text)
        self.assertIn("unit = _normalize_unit", text)
        self.assertIn("NRestarts", text)
        self.assertIn("Result", text)
        self.assertNotIn("journalctl", text)
        self.assertFalse(
            any("maez.log" in value for value in string_literals),
            "alert script must not read or forward daemon log content",
        )


if __name__ == "__main__":
    unittest.main()
