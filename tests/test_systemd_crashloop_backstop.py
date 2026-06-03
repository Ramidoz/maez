# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Systemd must bound liveness-triggered restart loops and alert the owner."""

from __future__ import annotations

import ast
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


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

    def test_alert_script_resolves_recipient_from_ordinary_config_env(self):
        from scripts import maez_crashloop_alert

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            (root / "config" / ".env").write_text(
                "MAEZ_TELEGRAM_USER_ID=owner-from-dotenv\n"
                "MAEZ_DEV_TOKEN=must-not-load-from-dotenv\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {"MAEZ_HOME": str(root), "MAEZ_DEV_TOKEN": "token-from-unit"},
                clear=True,
            ):
                self.assertTrue(
                    maez_crashloop_alert._ensure_notifier_recipient_env(root)
                )
                self.assertEqual(os.environ["MAEZ_TELEGRAM_USER_ID"], "owner-from-dotenv")
                self.assertEqual(os.environ["MAEZ_DEV_TOKEN"], "token-from-unit")

    def test_alert_script_falls_back_to_identity_yaml_recipient(self):
        from scripts import maez_crashloop_alert

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            (root / "config" / "identity.yaml").write_text(
                textwrap.dedent(
                    """
                    owner:
                      telegram_user_id: "owner-from-identity"
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {"MAEZ_HOME": str(root), "MAEZ_DEV_TOKEN": "token-from-unit"},
                clear=True,
            ):
                self.assertTrue(
                    maez_crashloop_alert._ensure_notifier_recipient_env(root)
                )
                self.assertEqual(
                    os.environ["MAEZ_TELEGRAM_USER_ID"], "owner-from-identity"
                )

    def test_alert_script_reports_unready_when_recipient_is_unresolvable(self):
        from scripts import maez_crashloop_alert

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()

            with mock.patch.dict(
                os.environ,
                {"MAEZ_HOME": str(root), "MAEZ_DEV_TOKEN": "token-from-unit"},
                clear=True,
            ):
                self.assertFalse(
                    maez_crashloop_alert._ensure_notifier_recipient_env(root)
                )
                self.assertNotIn("MAEZ_TELEGRAM_USER_ID", os.environ)

    def test_alert_main_resolves_recipient_before_sending_card(self):
        from scripts import maez_crashloop_alert

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            (root / "config" / ".env").write_text(
                "MAEZ_TELEGRAM_USER_ID=owner-from-dotenv\n",
                encoding="utf-8",
            )

            with (
                mock.patch.dict(
                    os.environ,
                    {"MAEZ_HOME": str(root), "MAEZ_DEV_TOKEN": "token-from-unit"},
                    clear=True,
                ),
                mock.patch.object(
                    maez_crashloop_alert,
                    "MAEZ_HOME",
                    root,
                ),
                mock.patch.object(
                    maez_crashloop_alert,
                    "_unit_properties",
                    return_value={"ActiveState": "failed", "Result": "start-limit-hit"},
                ),
                mock.patch.object(
                    maez_crashloop_alert,
                    "send_service_card",
                ) as send_card,
            ):
                self.assertEqual(maez_crashloop_alert.main(["maez.service"]), 0)
                self.assertEqual(os.environ["MAEZ_TELEGRAM_USER_ID"], "owner-from-dotenv")
                send_card.assert_called_once()


if __name__ == "__main__":
    unittest.main()
