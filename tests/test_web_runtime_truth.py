from __future__ import annotations

import os
import unittest
from unittest import mock


class WebRuntimeTruthTests(unittest.TestCase):
    def setUp(self):
        with mock.patch.dict(
            os.environ,
            {
                "MAEZ_IPHONE_INGEST_TOKEN": "test-token",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
            },
            clear=False,
        ):
            from skills import web_interface as wi

        self.wi = wi
        self.client = wi.app.test_client()

    def _runtime_snapshot(self):
        return {
            "schema_version": "maez_runtime_services.v0",
            "overall": "degraded",
            "services": {
                "primary_brain": {
                    "status": "healthy",
                    "configured": True,
                    "required_by": ["always"],
                    "degraded_reasons": [],
                },
                "support_verifier": {
                    "status": "degraded",
                    "configured": True,
                    "required_by": ["MAEZ_SUPPORT_GATE_ENABLED"],
                    "degraded_reasons": ["contract_unhealthy"],
                },
                "search_body": {
                    "status": "asleep",
                    "configured": False,
                    "required_by": [],
                    "degraded_reasons": [],
                },
            },
        }

    def test_services_api_returns_runtime_service_truth_not_systemctl_list(self):
        with mock.patch(
            "core.infra.runtime_services.runtime_services_snapshot_cached",
            return_value=self._runtime_snapshot(),
        ):
            response = self.client.get("/api/v1/services")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["runtime_services"]["schema_version"], "maez_runtime_services.v0")
        self.assertEqual(payload["runtime_services"]["overall"], "degraded")
        self.assertEqual(payload["services"]["support_verifier"]["status"], "degraded")
        self.assertEqual(
            payload["services"]["support_verifier"]["degraded_reasons"],
            ["contract_unhealthy"],
        )
        self.assertNotIn("sub", payload["services"]["support_verifier"])

    def test_now_body_summary_leads_with_runtime_contract_status(self):
        with (
            mock.patch(
                "core.infra.runtime_services.runtime_services_snapshot_cached",
                return_value=self._runtime_snapshot(),
            ),
            mock.patch.object(self.wi, "_tail_log_lines", return_value=[]),
            mock.patch(
                "core.infra.body_capabilities.body_capabilities",
                return_value={
                    "binaries": {"rg": True, "wmctrl": False},
                    "services": {"brain": True},
                    "desktop_session_reachable": False,
                    "sudo_passwordless": False,
                },
            ),
            mock.patch(
                "core.infra.capability_registry.describe",
                return_value={
                    "services": {
                        "maez": "active",
                        "llama-server": "active",
                    },
                    "memory_counts": {"raw": 1, "daily": 0, "core": 0},
                },
            ),
            mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True),
        ):
            response = self.client.get("/api/v1/now")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()["body"]
        self.assertEqual(body["runtime_services"]["overall"], "degraded")
        self.assertIn("support verifier is degraded", body["summary"])
        self.assertIn("primary brain is healthy", body["summary"])
        self.assertNotIn("talk to 2 live services", body["summary"])

    def test_public_maez_state_carries_runtime_service_truth_without_replacing_legacy_shape(self):
        with (
            mock.patch(
                "core.infra.runtime_services.runtime_services_snapshot_cached",
                return_value=self._runtime_snapshot(),
            ) as runtime_snapshot,
            mock.patch.object(self.wi.memory, "memory_stats", return_value={"raw": 0, "daily": 0, "core": 0, "total": 0}),
            mock.patch.object(self.wi.accounts, "count", return_value=1),
            mock.patch.object(self.wi, "_daemon_health", return_value={"ok": True}),
            mock.patch.object(self.wi, "_model_state", return_value={}),
            mock.patch.object(self.wi, "_soul_state", return_value={}),
            mock.patch.object(self.wi, "_thunder_state", return_value={}),
        ):
            response = self.client.get("/api/maez-state")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["runtime_services"]["schema_version"], "maez_runtime_services.v0")
        self.assertEqual(payload["runtime_services"]["overall"], "degraded")
        self.assertIn("services", payload)
        runtime_snapshot.assert_called_once()

    def test_public_journal_reads_runtime_services_not_only_legacy_service_map(self):
        from pathlib import Path

        page = Path("ui/project-planner.html").read_text()

        self.assertIn("state.runtime_services", page)
        self.assertIn("runtimeOverall", page)
        self.assertIn("visionRuntime", page)
        self.assertIn("body unknown", page)
        self.assertNotIn("all services up", page)
        self.assertNotIn("state.services && state.services.llama_server_vision", page)
        self.assertNotIn("svc.llama_server_vision === 'active'", page)
        self.assertNotIn("Vision</span> <span class=\"v\">active</span>", page)


if __name__ == "__main__":
    unittest.main()
