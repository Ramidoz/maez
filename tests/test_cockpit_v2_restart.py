import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock


class FakeRunner:
    def __init__(
        self,
        *,
        pre_pid: str = "111",
        post_pid: str = "222",
        active: str = "active",
        restart_returncode: int = 0,
        log_tail: str = "",
    ):
        self.pre_pid = pre_pid
        self.post_pid = post_pid
        self.active = active
        self.restart_returncode = restart_returncode
        self.log_tail = log_tail
        self.commands = []
        self._pid_reads = 0

    def __call__(self, cmd):
        from core.cockpit.restart import CommandResult

        self.commands.append(tuple(cmd))
        if cmd[:4] == ["systemctl", "show", "-p", "MainPID"]:
            self._pid_reads += 1
            return CommandResult(
                stdout=self.pre_pid if self._pid_reads == 1 else self.post_pid
            )
        if cmd[:2] == ["systemctl", "restart"]:
            return CommandResult(returncode=self.restart_returncode)
        if cmd[:2] == ["systemctl", "is-active"]:
            return CommandResult(
                returncode=0 if self.active == "active" else 3,
                stdout=self.active,
            )
        if cmd[:2] == ["journalctl", "-u"]:
            return CommandResult(stdout=self.log_tail)
        raise AssertionError(cmd)


class CockpitV2RestartTests(unittest.TestCase):
    @staticmethod
    def _now():
        return datetime(2026, 7, 4, 22, 30, tzinfo=UTC)

    def _paths(self, root: Path):
        from core.cockpit.restart import CockpitRestartPaths

        return CockpitRestartPaths(
            receipt_log=root / "logs" / "cockpit_restart_receipts.jsonl"
        )

    def test_restart_refuses_without_typed_confirmation(self):
        from core.cockpit.restart import restart_service

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            runner = FakeRunner()
            result = restart_service(
                "maez.service",
                paths=paths,
                owner_authenticated=True,
                cockpit_v2_enabled=True,
                typed_confirmation="restart",
                runner=runner,
                now=self._now,
            )

            self.assertEqual(runner.commands, [])
            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "typed_confirmation_required")
        self.assertEqual(result["required_confirmation"], "restart maez.service")

    def test_restart_receipt_contains_pre_and_post_pid(self):
        from core.cockpit.restart import restart_service

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = restart_service(
                "maez.service",
                paths=paths,
                owner_authenticated=True,
                cockpit_v2_enabled=True,
                typed_confirmation="restart maez.service",
                runner=FakeRunner(pre_pid="123", post_pid="456"),
                now=self._now,
            )
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "restarted")
        self.assertTrue(result["receipt_id"].startswith("cockpit-restart-"))
        self.assertEqual(result["pre_pid"], 123)
        self.assertEqual(result["post_pid"], 456)
        self.assertEqual(receipt["receipt_id"], result["receipt_id"])
        self.assertEqual(receipt["pre_pid"], 123)
        self.assertEqual(receipt["post_pid"], 456)
        self.assertEqual(receipt["service"], "maez.service")

    def test_simulated_segv_log_line_is_surfaced(self):
        from core.cockpit.restart import restart_service

        log_tail = (
            "maez[123]: booting\n"
            "kernel: maez[123]: segfault at 0 ip 0x1\n"
            "systemd-coredump[9]: Process 123 dumped core\n"
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = restart_service(
                "maez.service",
                paths=self._paths(root),
                owner_authenticated=True,
                cockpit_v2_enabled=True,
                typed_confirmation="restart maez.service",
                runner=FakeRunner(log_tail=log_tail),
                now=self._now,
            )
            receipt = json.loads(
                (root / "logs" / "cockpit_restart_receipts.jsonl").read_text(
                    encoding="utf-8"
                )
            )

        hints = result["boot_witness"]["hints"]
        self.assertTrue(hints["segv_detected"])
        self.assertTrue(hints["coredump_detected"])
        self.assertIn("segfault", "\n".join(hints["matching_lines"]))
        self.assertIn("dumped core", "\n".join(hints["matching_lines"]))
        self.assertEqual(receipt["boot_witness"]["log_tail"], log_tail)
        self.assertEqual(receipt["boot_witness"]["hints"], hints)

    def test_failed_restart_renders_failed_not_pending_success(self):
        from core.cockpit.restart import restart_service

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = restart_service(
                "maez.service",
                paths=paths,
                owner_authenticated=True,
                cockpit_v2_enabled=True,
                typed_confirmation="restart maez.service",
                runner=FakeRunner(
                    post_pid="0",
                    active="failed",
                    restart_returncode=1,
                    log_tail="maez.service: Main process exited, status=11/SEGV\n",
                ),
                now=self._now,
            )
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "failed")
        self.assertNotEqual(result["status"], "pending")
        self.assertEqual(result["active_state"], "failed")
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["active_state"], "failed")

    def test_runner_exception_renders_failed_receipt(self):
        from core.cockpit.restart import CommandResult, restart_service

        calls = []

        def runner(cmd):
            calls.append(tuple(cmd))
            if cmd[:4] == ["systemctl", "show", "-p", "MainPID"]:
                return CommandResult(stdout="123")
            if cmd[:2] == ["systemctl", "restart"]:
                raise TimeoutError("restart timed out")
            raise AssertionError(cmd)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = restart_service(
                "maez.service",
                paths=paths,
                owner_authenticated=True,
                cockpit_v2_enabled=True,
                typed_confirmation="restart maez.service",
                runner=runner,
                now=self._now,
            )
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertIn(("systemctl", "restart", "maez.service"), calls)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["active_state"], "unknown")
        self.assertIn("restart timed out", result["boot_witness"]["error"])
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("restart timed out", receipt["boot_witness"]["error"])

    def test_flag_write_handler_does_not_call_restart(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import inspect
        import skills.web_interface as wi

        source = inspect.getsource(wi.api_cockpit_v2_flag_write)
        write_source = (
            Path(__file__).resolve().parents[1] / "core" / "cockpit" / "writes.py"
        ).read_text(encoding="utf-8")

        for forbidden in ("restart_service", "_cockpit_restart_paths", "systemctl"):
            self.assertNotIn(forbidden, source)
            self.assertNotIn(forbidden, write_source)

    def test_v2_restart_route_uses_injected_runner(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            runner = FakeRunner(pre_pid="100", post_pid="101")
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), (
                mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)
            ), mock.patch.object(wi, "_cockpit_restart_paths", return_value=paths), (
                mock.patch.object(wi, "_cockpit_restart_runner", return_value=runner)
            ):
                response = wi.app.test_client().post(
                    "/api/v2/cockpit/restart",
                    json={
                        "service": "maez.service",
                        "typed_confirmation": "restart maez.service",
                    },
                )
            body = response.get_json()
            response.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "restarted")
        self.assertEqual(body["pre_pid"], 100)
        self.assertEqual(body["post_pid"], 101)
        self.assertIn(("systemctl", "restart", "maez.service"), runner.commands)

    def test_v2_restart_route_refuses_when_shell_flag_off(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        runner = FakeRunner()
        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "0"}, clear=False), (
            mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)
        ), mock.patch.object(wi, "_cockpit_restart_runner", return_value=runner):
            response = wi.app.test_client().post(
                "/api/v2/cockpit/restart",
                json={
                    "service": "maez.service",
                    "typed_confirmation": "restart maez.service",
                },
            )
        body = response.get_json()
        response.close()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(body["reason"], "cockpit_v2_off")
        self.assertEqual(runner.commands, [])


if __name__ == "__main__":
    unittest.main()
