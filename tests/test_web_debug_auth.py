from __future__ import annotations

import os
import sys
import unittest
from unittest import mock


class WebDebugAuthTests(unittest.TestCase):
    def _web_interface(self):
        sys.modules.pop("skills.web_interface", None)
        with (
            mock.patch.dict(
                os.environ,
                {"MAEZ_IPHONE_INGEST_TOKEN": "test-token"},
                clear=False,
            ),
            mock.patch("core.infra.secrets.load_ordinary_config_for_process"),
            mock.patch("core.infra.secrets.load_secrets_for_process"),
        ):
            from skills import web_interface as wi

        return wi

    def test_test_t_does_not_authorize_debug_memory_view(self):
        wi = self._web_interface()

        response = wi.app.test_client().get("/api/debug/memory-view?test_t=1")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_debug_auth_resolves_token_to_full_owner_record(self):
        wi = self._web_interface()
        client = wi.app.test_client()
        client.set_cookie("maez_token", "tok")

        with (
            mock.patch.object(
                wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ) as get_by_token,
            mock.patch.object(
                wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ) as get_user_record,
            mock.patch.object(wi, "_service_state_cached", return_value="active"),
            mock.patch.object(wi, "_daemon_health", return_value={"status": "alive"}),
        ):
            response = client.get("/api/debug/services")

        self.assertEqual(response.status_code, 200)
        get_by_token.assert_called_once_with("tok")
        get_user_record.assert_called_once_with("owner")

    def test_debug_auth_rejects_token_record_private_owner_spoof(self):
        wi = self._web_interface()
        client = wi.app.test_client()
        client.set_cookie("maez_token", "tok")

        with (
            mock.patch.object(
                wi.accounts,
                "get_by_token",
                return_value={
                    "uuid": "owner",
                    "display_name": "Rohit",
                    "private_owner_bridge": True,
                },
            ),
            mock.patch.object(wi.accounts, "get_user_record", return_value={}),
        ):
            response = client.get("/api/debug/services")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_debug_auth_rejects_owner_token_in_query_string(self):
        wi = self._web_interface()
        client = wi.app.test_client()

        with (
            mock.patch.object(
                wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            mock.patch.object(
                wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
            mock.patch.object(wi, "_service_state_cached", return_value="active"),
            mock.patch.object(wi, "_daemon_health", return_value={"status": "alive"}),
        ):
            response = client.get("/api/debug/services?web_token=tok")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_private_planner_and_analytics_reject_query_token(self):
        wi = self._web_interface()
        client = wi.app.test_client()

        with (
            mock.patch.object(
                wi.accounts,
                "get_by_token",
                return_value={"uuid": "owner", "display_name": "Rohit"},
            ),
            mock.patch.object(
                wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
        ):
            for path in (
                "/api/analytics-summary?web_token=tok",
                "/api/planner-board?web_token=tok",
            ):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_private_planner_and_analytics_reject_non_owner_cookie(self):
        wi = self._web_interface()
        client = wi.app.test_client()
        client.set_cookie("maez_token", "tok")

        with (
            mock.patch.object(
                wi.accounts,
                "get_by_token",
                return_value={"uuid": "guest", "display_name": "Guest"},
            ),
            mock.patch.object(wi.accounts, "get_user_record", return_value={}),
        ):
            for path in ("/api/analytics-summary", "/api/planner-board"):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json()["error"], "owner_auth_required")

    def test_private_planner_and_analytics_accept_owner_cookie(self):
        wi = self._web_interface()
        client = wi.app.test_client()
        client.set_cookie("maez_token", "tok")

        with (
            mock.patch.object(
                wi.accounts,
                "get_by_token",
                return_value={
                    "uuid": "owner",
                    "display_name": "Rohit",
                    "username": "rohit",
                },
            ),
            mock.patch.object(
                wi.accounts,
                "get_user_record",
                return_value={"private_owner_bridge": True},
            ),
            mock.patch.object(wi, "_load_analytics_events", return_value=[]),
            mock.patch.object(
                wi,
                "_load_planner_board",
                return_value={"updated_at": "2026-06-17T00:00:00Z", "items": []},
            ),
        ):
            analytics = client.get("/api/analytics-summary")
            planner = client.get("/api/planner-board")

        self.assertEqual(analytics.status_code, 200)
        self.assertEqual(planner.status_code, 200)


if __name__ == "__main__":
    unittest.main()
