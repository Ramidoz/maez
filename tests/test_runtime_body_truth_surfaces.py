import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from unittest import mock
from skills import web_interface as W

_FAKE_SNAP = {
    "schema_version": "maez_runtime_services.v0",
    "overall": "degraded",
    "services": {
        "maez_daemon": {"status": "healthy", "degraded_reasons": []},
        "primary_brain": {"status": "healthy", "degraded_reasons": []},
        "search_body": {"status": "asleep", "degraded_reasons": []},
    },
}

class ApiV1Services(unittest.TestCase):
    def test_returns_v0_schema_and_services(self):
        with mock.patch.object(W, "_runtime_services_state", return_value=_FAKE_SNAP):
            client = W.app.test_client()
            r = client.get("/api/v1/services")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["runtime_services"]["schema_version"], "maez_runtime_services.v0")
        self.assertEqual(body["services"]["maez_daemon"]["status"], "healthy")
