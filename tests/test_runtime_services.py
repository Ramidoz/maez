from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock


class RuntimeServiceSnapshotTests(unittest.TestCase):
    def setUp(self):
        try:
            from core.infra import runtime_services as rs
        except ImportError:
            return
        rs.invalidate_cache()
        self.addCleanup(rs.invalidate_cache)

    def _healthy_fakes(self):
        return {
            "unit_probe": lambda name, scope="user", timeout_s=0.35: {
                "name": name,
                "scope": scope,
                "load_state": "loaded",
                "active_state": "active",
                "enabled_state": "enabled",
            },
            "port_probe": lambda host, port, timeout_s=0.35: True,
            "http_json": lambda method, url, payload=None, timeout_s=0.35: {
                "ok": True,
                "json": {
                    "status": "ok",
                    "contract": "minicheck_support.v1",
                    "data": [],
                },
                "latency_ms": 1,
            },
            "model_alias": lambda default=None, timeout_s=0.35: "qwen36-27b",
        }

    def test_snapshot_shape_includes_v0_services(self):
        from core.infra import runtime_services as rs

        with mock.patch.dict("os.environ", {}, clear=True):
            snap = rs.runtime_services_snapshot(**self._healthy_fakes())

        self.assertEqual(snap["schema_version"], "maez_runtime_services.v0")
        self.assertIn(snap["overall"], {"healthy", "degraded", "unknown"})
        for key in (
            "primary_brain",
            "maez_daemon",
            "maez_web",
            "search_body",
            "support_verifier",
            "subscription_proxy",
            "vision_body",
            "overclaim_judge",
        ):
            self.assertIn(key, snap["services"])

    def test_support_verifier_asleep_when_flags_off(self):
        from core.infra import runtime_services as rs

        with mock.patch.dict("os.environ", {}, clear=True):
            service = rs.runtime_services_snapshot(**self._healthy_fakes())[
                "services"
            ]["support_verifier"]

        self.assertFalse(service["configured"])
        self.assertEqual(service["required_by"], [])
        self.assertEqual(service["status"], "asleep")

    def test_support_verifier_degraded_when_required_but_contract_fails(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        fakes["http_json"] = lambda method, url, payload=None, timeout_s=0.35: {
            "ok": True,
            "json": {"unexpected": True},
            "latency_ms": 2,
        }

        with mock.patch.dict(
            "os.environ",
            {"MAEZ_SUPPORT_GATE_ENABLED": "1"},
            clear=True,
        ):
            snap = rs.runtime_services_snapshot(**fakes)
        service = snap["services"]["support_verifier"]

        self.assertEqual(service["status"], "degraded")
        self.assertIn("contract_unhealthy", service["degraded_reasons"])
        self.assertEqual(snap["overall"], "degraded")

    def test_support_verifier_healthy_only_with_contract_fields(self):
        from core.infra import runtime_services as rs

        with mock.patch.dict(
            "os.environ",
            {"MAEZ_SUPPORT_GATE_ENABLED": "1"},
            clear=True,
        ):
            service = rs.runtime_services_snapshot(**self._healthy_fakes())[
                "services"
            ]["support_verifier"]

        self.assertEqual(service["status"], "healthy")
        self.assertTrue(service["contract"]["ok"])
        self.assertEqual(service["contract"]["status"], "ok")
        self.assertEqual(
            service["contract"]["contract_name"],
            "minicheck_support.v1",
        )

    def test_support_verifier_contract_uses_content_free_health_route(self):
        from core.infra import runtime_services as rs

        calls = []

        def _http_json(method, url, payload=None, timeout_s=0.35):
            calls.append((method, url, payload))
            return {
                "ok": True,
                "json": {
                    "status": "ok",
                    "contract": "minicheck_support.v1",
                },
                "latency_ms": 3,
            }

        fakes = self._healthy_fakes()
        fakes["http_json"] = _http_json
        with mock.patch.dict("os.environ", {"MAEZ_SUPPORT_GATE_ENABLED": "1"}, clear=True):
            service = rs.runtime_services_snapshot(**fakes)["services"]["support_verifier"]

        self.assertEqual(service["status"], "healthy")
        self.assertIn(("GET", "http://127.0.0.1:8083/health", None), calls)
        self.assertNotIn(("POST", "http://127.0.0.1:8083/support", mock.ANY), calls)

    def test_support_verifier_rejects_invalid_health_contract(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        fakes["http_json"] = lambda method, url, payload=None, timeout_s=0.35: {
            "ok": True,
            "json": {"verdict": "banana", "score": None},
            "latency_ms": 2,
        }

        with mock.patch.dict("os.environ", {"MAEZ_SUPPORT_GATE_ENABLED": "1"}, clear=True):
            service = rs.runtime_services_snapshot(**fakes)["services"]["support_verifier"]

        self.assertEqual(service["status"], "degraded")
        self.assertFalse(service["contract"]["ok"])
        self.assertIn("contract_unhealthy", service["degraded_reasons"])

    def test_search_body_required_does_not_issue_search_query(self):
        from core.infra import runtime_services as rs

        calls = []

        def _http_json(method, url, payload=None, timeout_s=0.35):
            calls.append(url)
            return {"ok": True, "json": {}, "latency_ms": 1}

        fakes = self._healthy_fakes()
        fakes["http_json"] = _http_json
        with mock.patch.dict("os.environ", {"MAEZ_SEARCH_AS_SENSE_ENABLED": "1"}, clear=True):
            service = rs.runtime_services_snapshot(**fakes)["services"]["search_body"]

        self.assertEqual(service["status"], "healthy")
        self.assertEqual(service["contract"]["kind"], "tcp_liveness_only")
        self.assertFalse(any("/search" in url for url in calls), calls)

    def test_optional_services_do_not_degrade_overall_when_asleep(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        fakes["port_probe"] = lambda host, port, timeout_s=0.35: port != 11438

        with mock.patch.dict("os.environ", {}, clear=True):
            snap = rs.runtime_services_snapshot(**fakes)

        self.assertEqual(snap["services"]["subscription_proxy"]["status"], "asleep")
        self.assertEqual(snap["overall"], "healthy")

    def test_primary_brain_degraded_when_served_model_alias_is_unknown(self):
        from core.infra import runtime_services as rs

        fakes = self._healthy_fakes()
        fakes["model_alias"] = lambda default=None, timeout_s=0.35: "unknown"

        with mock.patch.dict("os.environ", {}, clear=True):
            snap = rs.runtime_services_snapshot(**fakes)

        service = snap["services"]["primary_brain"]
        self.assertEqual(service["status"], "degraded")
        self.assertFalse(service["contract"]["ok"])
        self.assertIn("contract_unhealthy", service["degraded_reasons"])

    def test_web_owner_core_requires_maez_web_service(self):
        from core.infra import runtime_services as rs

        with mock.patch.dict("os.environ", {"MAEZ_WEB_OWNER_CORE": "1"}, clear=True):
            service = rs.runtime_services_snapshot(**self._healthy_fakes())[
                "services"
            ]["maez_web"]

        self.assertTrue(service["configured"])
        self.assertIn("MAEZ_WEB_OWNER_CORE", service["required_by"])

    def test_daemon_contract_can_skip_recursive_self_health_call(self):
        from core.infra import runtime_services as rs

        calls = []

        def _http_json(method, url, payload=None, timeout_s=0.35):
            calls.append(url)
            return {
                "ok": True,
                "json": {"verdict": "SUPPORTED", "score": 0.99},
                "latency_ms": 1,
            }

        fakes = self._healthy_fakes()
        fakes["http_json"] = _http_json
        with mock.patch.dict("os.environ", {}, clear=True):
            service = rs.runtime_services_snapshot(
                **fakes,
                probe_daemon_http_contract=False,
            )["services"]["maez_daemon"]

        self.assertEqual(service["contract"]["kind"], "in_process_daemon")
        self.assertTrue(service["contract"]["ok"])
        self.assertNotIn("http://127.0.0.1:11435/health", calls)

    def test_http_json_reads_complete_response_body_before_parsing(self):
        from core.infra import runtime_services as rs

        payload = {
            "status": "ok",
            "contract": "large-health-payload",
            "padding": "x" * 6000,
        }
        raw = json.dumps(payload).encode("utf-8")
        read_sizes = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def read(self, size=-1):
                read_sizes.append(size)
                if size is None or size < 0:
                    return raw
                return raw[:size]

        with mock.patch("urllib.request.urlopen", return_value=_Response()):
            result = rs._http_json("GET", "http://127.0.0.1:11435/health")

        self.assertTrue(result["ok"])
        self.assertEqual(result["json"]["contract"], "large-health-payload")
        self.assertEqual(read_sizes, [-1])

    def test_unit_probe_handles_timeout_and_missing_systemctl(self):
        from core.infra import runtime_services as rs

        timeout = rs._parse_systemctl_show(
            "",
            timed_out=True,
            unit="x.service",
            scope="user",
        )
        missing = rs._parse_systemctl_show(
            None,
            timed_out=False,
            unit="x.service",
            scope="user",
        )

        self.assertEqual(timeout["load_state"], "unknown")
        self.assertEqual(timeout["active_state"], "unknown")
        self.assertEqual(missing["load_state"], "unknown")
        self.assertEqual(missing["active_state"], "unknown")

    def test_daemon_contract_uses_fast_operator_health_not_slow_health(self):
        from core.infra import runtime_services as rs

        seen_urls = []

        def recording_http_json(method, url, payload=None, timeout_s=0.35):
            seen_urls.append(url)
            # model reality: the slow /health would hang/fail; /operator/health is fast & ok
            if url.rstrip("/").endswith("11435/health"):
                return {"ok": False, "json": {}, "latency_ms": 4000}   # slow /health -> would-be timeout
            return {"ok": True, "json": {"status": "ok"}, "latency_ms": 5}

        fakes = self._healthy_fakes()
        fakes["http_json"] = recording_http_json
        with mock.patch.dict("os.environ", {}, clear=True):
            snap = rs.runtime_services_snapshot(timeout_s=0.35, **fakes)
        # the daemon contract probes the FAST operator endpoint...
        self.assertTrue(any("/operator/health" in u for u in seen_urls), seen_urls)
        # ...and NEVER the slow /health (so it cannot false-degrade on /health latency)
        self.assertFalse(any(u.rstrip("/").endswith("11435/health") for u in seen_urls), seen_urls)
        # ...so a healthy daemon reads healthy even though the modeled /health is slow/failing
        self.assertEqual(snap["services"]["maez_daemon"]["status"], "healthy")

    def test_probe_main_exits_two_on_degraded_required_service(self):
        from scripts import maez_runtime_services_probe as probe

        degraded = {
            "schema_version": "maez_runtime_services.v0",
            "overall": "degraded",
            "services": {"support_verifier": {"status": "degraded"}},
        }
        with mock.patch.object(
            probe,
            "runtime_services_snapshot",
            return_value=degraded,
        ), redirect_stdout(StringIO()):
            self.assertEqual(probe.main([]), 2)


if __name__ == "__main__":
    unittest.main()
