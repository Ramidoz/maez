from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch


class DigestionEndpointGuardTest(unittest.TestCase):
    def test_loopback_and_unix_endpoints_are_allowed(self):
        from core.routing.digestion_endpoint_guard import (
            check_digestion_endpoint_locality,
        )

        for endpoint, expected_endpoint in [
            ("http://127.0.0.1:8080", "http://127.0.0.1:8080/v1"),
            ("http://localhost:8080/v1", "http://localhost:8080/v1"),
            ("http://[::1]:8080/v1", "http://[::1]:8080/v1"),
            ("unix:///tmp/maez-primary.sock", "unix:///tmp/maez-primary.sock"),
        ]:
            with self.subTest(endpoint=endpoint):
                with patch.dict(
                    os.environ,
                    {
                        "MAEZ_LLM_BACKEND": "llamacpp",
                        "MAEZ_LLAMACPP_URL": "",
                        "MAEZ_PRIMARY_BASE_URL": endpoint,
                    },
                    clear=False,
                ):
                    result = check_digestion_endpoint_locality()

                self.assertTrue(result.allowed)
                self.assertEqual(result.refusal_code, "")
                self.assertEqual(result.endpoint, expected_endpoint)

    def test_lan_ip_endpoint_refuses_without_raising(self):
        from core.routing.digestion_endpoint_guard import (
            check_digestion_endpoint_locality,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_LLAMACPP_URL": "",
                "MAEZ_PRIMARY_BASE_URL": "http://192.168.1.44:8080/v1",
            },
            clear=False,
        ):
            result = check_digestion_endpoint_locality()

        self.assertFalse(result.allowed)
        self.assertEqual(result.refusal_code, "non_local_endpoint")
        self.assertIn("192.168.1.44", result.reason)

    def test_remote_hostname_endpoint_refuses_without_raising(self):
        from core.routing.digestion_endpoint_guard import (
            check_digestion_endpoint_locality,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_LLAMACPP_URL": "",
                "MAEZ_PRIMARY_BASE_URL": "https://api.openai.com/v1",
            },
            clear=False,
        ):
            result = check_digestion_endpoint_locality()

        self.assertFalse(result.allowed)
        self.assertEqual(result.refusal_code, "non_local_endpoint")
        self.assertIn("api.openai.com", result.reason)

    def test_environment_endpoint_is_re_evaluated_between_calls(self):
        from core.routing.digestion_endpoint_guard import (
            check_digestion_endpoint_locality,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_LLAMACPP_URL": "",
                "MAEZ_PRIMARY_BASE_URL": "http://127.0.0.1:8080",
            },
            clear=False,
        ):
            first = check_digestion_endpoint_locality()
            os.environ["MAEZ_PRIMARY_BASE_URL"] = "https://remote.example/v1"
            second = check_digestion_endpoint_locality()

        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.endpoint, "https://remote.example/v1")

    def test_absent_llamacpp_url_uses_primary_base_for_active_endpoint(self):
        from core.routing.digestion_endpoint_guard import (
            check_digestion_endpoint_locality,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_PRIMARY_BASE_URL": "https://primary-remote.example/v1",
            },
            clear=False,
        ):
            os.environ.pop("MAEZ_LLAMACPP_URL", None)
            result = check_digestion_endpoint_locality()

        self.assertFalse(result.allowed)
        self.assertEqual(result.endpoint, "https://primary-remote.example/v1")
        self.assertIn("primary-remote.example", result.reason)

    def test_active_llamacpp_endpoint_takes_precedence_over_primary_base(self):
        from core.routing.digestion_endpoint_guard import (
            check_digestion_endpoint_locality,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_LLAMACPP_URL": "https://remote-llama.example/v1",
                "MAEZ_PRIMARY_BASE_URL": "http://127.0.0.1:8080",
            },
            clear=False,
        ):
            result = check_digestion_endpoint_locality()

        self.assertFalse(result.allowed)
        self.assertEqual(result.endpoint, "https://remote-llama.example/v1")
        self.assertIn("remote-llama.example", result.reason)

    def test_llamacpp_stream_path_uses_same_call_time_endpoint_as_guard(self):
        from core.routing import llm_client
        from core.routing.digestion_endpoint_guard import (
            resolve_active_backend_endpoint,
        )

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_LLAMACPP_URL": "http://127.0.0.1:9099/v1",
                "MAEZ_PRIMARY_BASE_URL": "https://remote-primary.example/v1",
            },
            clear=False,
        ):
            _backend, endpoint = resolve_active_backend_endpoint()
            with patch.object(
                llm_client,
                "_connect_llamacpp_socket",
                return_value=object(),
            ) as fake_connect:
                llm_client._start_llamacpp_stream(
                    model="m",
                    messages=[],
                    temperature=0.0,
                    max_tokens=1,
                    extra_body={},
                )

        self.assertEqual(endpoint, "http://127.0.0.1:9099/v1")
        self.assertEqual(fake_connect.call_args.args[0], endpoint)

    def test_llamacpp_stream_normalizes_primary_fallback_to_openai_v1(self):
        from core.routing import llm_client

        with patch.dict(
            os.environ,
            {
                "MAEZ_LLM_BACKEND": "llamacpp",
                "MAEZ_PRIMARY_BASE_URL": "http://127.0.0.1:8080",
            },
            clear=False,
        ):
            os.environ.pop("MAEZ_LLAMACPP_URL", None)
            with patch.object(
                llm_client,
                "_connect_llamacpp_socket",
                return_value=object(),
            ) as fake_connect:
                llm_client._start_llamacpp_stream(
                    model="m",
                    messages=[],
                    temperature=0.0,
                    max_tokens=1,
                    extra_body={},
                )

        self.assertEqual(fake_connect.call_args.args[0], "http://127.0.0.1:8080/v1")

    def test_guard_module_does_not_expose_or_reference_direct_chat(self):
        import core.routing.digestion_endpoint_guard as guard

        source = Path(guard.__file__).read_text(encoding="utf-8")

        self.assertFalse(hasattr(guard, "chat_direct"))
        self.assertNotIn("chat_direct", source)


if __name__ == "__main__":
    unittest.main()
