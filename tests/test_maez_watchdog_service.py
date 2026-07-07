from __future__ import annotations

import subprocess
import unittest
from unittest.mock import Mock, patch

from skills import maez_watchdog


class MaezWatchdogLivenessTests(unittest.TestCase):
    def test_active_requires_systemd_active_and_http_health(self):
        with (
            patch.object(maez_watchdog.subprocess, "run") as run,
            patch.object(maez_watchdog.requests, "get") as get,
        ):
            run.return_value = subprocess.CompletedProcess(
                ["systemctl"], 0, stdout="active\n", stderr="",
            )
            response = Mock()
            response.json.return_value = {
                "route": "/operator/health",
                "service_mode": "running",
            }
            get.return_value = response

            self.assertTrue(maez_watchdog.is_maez_active())

        get.assert_called_once_with(maez_watchdog.OPERATOR_HEALTH_URL, timeout=3)
        self.assertEqual(
            maez_watchdog.OPERATOR_HEALTH_URL,
            "http://127.0.0.1:11435/operator/health",
        )

    def test_active_is_false_when_systemd_active_but_health_probe_fails(self):
        with (
            patch.object(maez_watchdog.subprocess, "run") as run,
            patch.object(maez_watchdog.requests, "get") as get,
        ):
            run.return_value = subprocess.CompletedProcess(
                ["systemctl"], 0, stdout="active\n", stderr="",
            )
            get.side_effect = maez_watchdog.requests.Timeout("health timed out")

            self.assertFalse(maez_watchdog.is_maez_active())

    def test_active_is_false_when_operator_health_reports_degraded_service(self):
        with (
            patch.object(maez_watchdog.subprocess, "run") as run,
            patch.object(maez_watchdog.requests, "get") as get,
        ):
            run.return_value = subprocess.CompletedProcess(
                ["systemctl"], 0, stdout="active\n", stderr="",
            )
            response = Mock()
            response.json.return_value = {
                "route": "/operator/health",
                "service_mode": "degraded",
            }
            get.return_value = response

            self.assertFalse(maez_watchdog.is_maez_active())

    def test_cycle_count_uses_full_health_payload_only_for_recovery_detail(self):
        with patch.object(maez_watchdog.requests, "get") as get:
            response = Mock()
            response.json.return_value = {"status": "alive", "cycle_count": 42}
            get.return_value = response

            self.assertEqual(maez_watchdog.get_cycle_count(), "42")

        get.assert_called_once_with(maez_watchdog.FULL_HEALTH_URL, timeout=3)
        self.assertEqual(maez_watchdog.FULL_HEALTH_URL, "http://127.0.0.1:11435/health")


if __name__ == "__main__":
    unittest.main()
