import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock


class CockpitV2WriteTests(unittest.TestCase):
    def _paths(self, root: Path):
        from core.cockpit.writes import CockpitWritePaths

        return CockpitWritePaths(
            env_file=root / "model.env",
            receipt_log=root / "logs" / "cockpit_write_receipts.jsonl",
        )

    @staticmethod
    def _now():
        return datetime(2026, 7, 4, 21, 30, tzinfo=UTC)

    def test_t1_write_appends_env_line_and_receipt(self):
        from core.cockpit.writes import apply_flag_write

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = apply_flag_write(
                "MAEZ_BODY_LEGIBILITY",
                "1",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                now=self._now,
            )

            env_text = paths.env_file.read_text(encoding="utf-8")
            env_lines = env_text.splitlines()
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["receipt_id"].startswith("cockpit-write-"))
        self.assertEqual(env_lines[0], "# 2026-07-04 cockpit-v2: MAEZ_BODY_LEGIBILITY=1")
        self.assertTrue(env_lines[1].startswith("# Witness: Set MAEZ_BODY_LEGIBILITY=1"))
        self.assertTrue(env_lines[2].startswith("# Revert: Set MAEZ_BODY_LEGIBILITY=0"))
        self.assertEqual(env_lines[3], "MAEZ_BODY_LEGIBILITY=1")
        self.assertEqual(receipt["receipt_id"], result["receipt_id"])
        self.assertEqual(receipt["flag"], "MAEZ_BODY_LEGIBILITY")
        self.assertEqual(receipt["tier"], "T1")
        self.assertEqual(result["process_state"]["requires_restart"], True)
        self.assertIn("restart", result["process_state"]["warning"])

    def test_t2_write_refuses_without_typed_confirmation(self):
        from core.cockpit.writes import apply_flag_write

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = apply_flag_write(
                "MAEZ_INTERACTION_PREFERENCES",
                "1",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                now=self._now,
            )

            self.assertFalse(paths.env_file.exists())
            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "typed_confirmation_required")
        self.assertEqual(result["required_confirmation"], "MAEZ_INTERACTION_PREFERENCES=1")

    def test_t2_write_succeeds_with_typed_confirmation_and_receipt(self):
        from core.cockpit.writes import apply_flag_write

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = apply_flag_write(
                "MAEZ_INTERACTION_PREFERENCES",
                "1",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                typed_confirmation="MAEZ_INTERACTION_PREFERENCES=1",
                now=self._now,
            )

            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["receipt_id"])
        self.assertEqual(receipt["receipt_id"], result["receipt_id"])
        self.assertEqual(receipt["confirmation_kind"], "typed")

    def test_t3_write_refuses_and_points_to_ceremony_route(self):
        from core.cockpit.writes import apply_flag_write

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = apply_flag_write(
                "S7_LIVE_WEBAUTHN_CEREMONY",
                "1",
                paths=self._paths(root),
                owner_authenticated=True,
                confirm_click_token="confirm",
                typed_confirmation="S7_LIVE_WEBAUTHN_CEREMONY=1",
                now=self._now,
            )

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "ceremony_only")
        self.assertEqual(result["ceremony"], "S7_CEREMONY")
        self.assertEqual(result["ceremony_route"], "/api/v1/s7/webauthn")

    def test_flag_off_v2_refuses_write_without_touching_files(self):
        from core.cockpit.writes import apply_flag_write

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = apply_flag_write(
                "MAEZ_BODY_LEGIBILITY",
                "1",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                cockpit_v2_enabled=False,
                now=self._now,
            )

            self.assertFalse(paths.env_file.exists())
            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "cockpit_v2_off")

    def test_multiline_value_is_rejected_before_env_write(self):
        from core.cockpit.writes import apply_flag_write

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            result = apply_flag_write(
                "MAEZ_BODY_LEGIBILITY",
                "1\nS7_LIVE_WEBAUTHN_CEREMONY=1",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                now=self._now,
            )

            self.assertFalse(paths.env_file.exists())
            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "invalid_value")

    def test_write_module_has_no_direct_substrate_store_writes(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "core"
            / "cockpit"
            / "writes.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "MemoryManager",
            "EpisodeStore",
            "write_soul",
            "core.memory",
            "lived_episodes",
            "soul.local",
        ):
            self.assertNotIn(forbidden, source)

    def test_v2_route_writes_when_flag_on_and_owner_authenticated(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), (
                mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)
            ), mock.patch.object(wi, "_cockpit_write_paths", return_value=paths):
                response = wi.app.test_client().post(
                    "/api/v2/cockpit/flags/MAEZ_BODY_LEGIBILITY",
                    json={"value": "1", "confirm_click_token": "confirm"},
                )
            body = response.get_json()
            response.close()

            env_text = paths.env_file.read_text(encoding="utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "applied")
        self.assertIn("receipt_id", body)
        self.assertIn("MAEZ_BODY_LEGIBILITY=1", env_text)

    def test_v2_route_refuses_when_shell_flag_off(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = self._paths(root)
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "0"}, clear=False), (
                mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)
            ), mock.patch.object(wi, "_cockpit_write_paths", return_value=paths):
                response = wi.app.test_client().post(
                    "/api/v2/cockpit/flags/MAEZ_BODY_LEGIBILITY",
                    json={"value": "1", "confirm_click_token": "confirm"},
                )
            body = response.get_json()
            response.close()

            self.assertFalse(paths.env_file.exists())
            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(body["reason"], "cockpit_v2_off")

    def test_route_passes_real_gate_values_into_write_helper(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import inspect
        import skills.web_interface as wi

        source = inspect.getsource(wi.api_cockpit_v2_flag_write)

        self.assertIn("owner_authenticated=_owner_private_auth_ok()", source)
        self.assertIn(
            'cockpit_v2_enabled=strict_env_flag("MAEZ_COCKPIT_V2")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
