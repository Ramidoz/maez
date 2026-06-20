import importlib.util
import pathlib
import unittest
from unittest import mock

_SPEC = importlib.util.spec_from_file_location(
    "minicheck_verifier_service",
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "minicheck_verifier_service.py",
)


class ServiceShapeTests(unittest.TestCase):
    def _load(self):
        mod = importlib.util.module_from_spec(_SPEC)
        _SPEC.loader.exec_module(mod)
        return mod

    def test_handle_support_maps_predict_to_json(self):
        mod = self._load()
        with mock.patch.object(mod, "_predict", return_value=("SUPPORTED", 0.91)):
            body = mod.handle_support({"evidence": "ev", "claim": "cl"})
        self.assertEqual(body, {"verdict": "SUPPORTED", "score": 0.91})

    def test_handle_support_missing_fields(self):
        mod = self._load()
        body = mod.handle_support({})
        self.assertIn("error", body)

    def test_health_payload_matches_runtime_services_contract(self):
        mod = self._load()
        self.assertEqual(
            mod.health_payload(),
            {"status": "ok", "contract": "minicheck_support.v1"},
        )

    def test_module_loads_without_touching_model(self):
        self._load()


if __name__ == "__main__":
    unittest.main()
