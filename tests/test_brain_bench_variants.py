import json
import os
import sys
import unittest

from scripts.brain_bench.variants import (
    ConfigSource,
    VariantConfigError,
    load_variants,
    resolve_judge_endpoint,
    validate_endpoint,
)


def _ops_config(**overrides):
    data = {
        "api_family": "ollama",
        "topology": "reuse_endpoint",
        "bind_host_verified": True,
        "live_daemon_disturbance": False,
        "gpu_contention": "low",
        "startup_health": "ok",
        "streaming_support": True,
        "restart_recovery": "clean",
    }
    data.update(overrides)
    return data


class EndpointValidationTests(unittest.TestCase):
    def test_accepts_loopback_http_with_port(self):
        self.assertEqual(validate_endpoint("http://127.0.0.1:11434"), 11434)
        self.assertEqual(validate_endpoint("http://localhost:8081"), 8081)
        self.assertEqual(validate_endpoint("http://[::1]:11434"), 11434)

    def test_rejects_sneaky_urls(self):
        for bad in (
            "https://127.0.0.1:11434",
            "http://127.0.0.1",
            "http://u:p@127.0.0.1:11434",
            "http://127.0.0.1:11434/?x=1",
            "http://127.0.0.1:11434/#f",
            "http://127.0.0.1:11434/api/chat",
            "http://127.0.0.1:11434/v1/chat/completions",
            "http://10.0.0.5:11434",
            "http://example.com:11434",
        ):
            with self.assertRaises(VariantConfigError, msg=bad):
                validate_endpoint(bad)

    def test_judge_endpoint_uses_same_validator(self):
        with self.assertRaises(VariantConfigError):
            resolve_judge_endpoint("https://127.0.0.1:8081")
        with self.assertRaises(VariantConfigError):
            resolve_judge_endpoint("http://127.0.0.1:8081/api/chat")
        self.assertEqual(resolve_judge_endpoint("http://127.0.0.1:8081"), 8081)


class RegistryTests(unittest.TestCase):
    def test_loads_validates_and_records_source_and_hash(self):
        raw = json.dumps(
            [
                {
                    "label": "current",
                    "base_url": "http://127.0.0.1:11434/",
                    "model": "local-model",
                    "chat_kwargs": {"temperature": 0.2},
                    "draft_model": "draft-local",
                    "ops": _ops_config(),
                }
            ]
        )

        registry = load_variants(raw, source=ConfigSource.FILE)
        variant = registry[0]

        self.assertEqual(variant.label, "current")
        self.assertEqual(variant.base_url, "http://127.0.0.1:11434")
        self.assertEqual(variant.port, 11434)
        self.assertEqual(variant.chat_kwargs["temperature"], 0.2)
        self.assertEqual(variant.draft_model, "draft-local")
        self.assertEqual(variant.ops_evidence.gpu_contention.value, "low")
        self.assertEqual(registry.variant_config_source, ConfigSource.FILE)
        self.assertRegex(registry.variant_config_hash, r"^[0-9a-f]{64}$")

        reordered = json.dumps(json.loads(raw), sort_keys=True, indent=2)
        self.assertEqual(
            registry.variant_config_hash,
            load_variants(reordered, source=ConfigSource.FILE).variant_config_hash,
        )

    def test_rejects_non_loopback_variant(self):
        with self.assertRaises(VariantConfigError):
            load_variants(
                json.dumps(
                    [
                        {
                            "label": "x",
                            "base_url": "http://10.0.0.5:11434",
                            "model": "m",
                        }
                    ]
                )
            )

    def test_ops_evidence_rejects_free_strings(self):
        with self.assertRaises(VariantConfigError):
            load_variants(
                json.dumps(
                    [
                        {
                            "label": "x",
                            "base_url": "http://127.0.0.1:11434",
                            "model": "m",
                            "ops": _ops_config(gpu_contention="FABRICATED_SENTINEL"),
                        }
                    ]
                )
            )

    def test_missing_or_empty_config_fails_closed(self):
        for raw in (None, "", "[]"):
            with self.assertRaises(VariantConfigError):
                load_variants(raw)

    def test_no_model_config_fallback(self):
        os.environ["MAEZ_PRIMARY_MODEL"] = "must-not-be-used"
        sys.modules.pop("core.routing.model_config", None)
        try:
            with self.assertRaises(VariantConfigError):
                load_variants(None)
            self.assertNotIn("core.routing.model_config", sys.modules)
        finally:
            os.environ.pop("MAEZ_PRIMARY_MODEL", None)

    def test_ops_evidence_is_required_not_defaulted_clean(self):
        with self.assertRaises(VariantConfigError):
            load_variants(
                json.dumps(
                    [
                        {
                            "label": "x",
                            "base_url": "http://127.0.0.1:11434",
                            "model": "m",
                        }
                    ]
                )
            )

    def test_rejects_duplicate_labels_and_missing_fields(self):
        with self.assertRaises(VariantConfigError):
            load_variants(
                json.dumps(
                    [
                        {"label": "dup", "base_url": "http://127.0.0.1:1", "model": "m1"},
                        {"label": "dup", "base_url": "http://127.0.0.1:2", "model": "m2"},
                    ]
                )
            )
        with self.assertRaises(VariantConfigError):
            load_variants(json.dumps([{"label": "missing"}]))


if __name__ == "__main__":
    unittest.main()
