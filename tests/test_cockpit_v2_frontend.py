import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "web" / "cockpit" / "v2"


def _bundle() -> tuple[str, str, str]:
    return (
        (V2 / "index.html").read_text(encoding="utf-8"),
        (V2 / "sim.jsx").read_text(encoding="utf-8"),
        (V2 / "terminal-ui.jsx").read_text(encoding="utf-8"),
    )


class CockpitV2FrontendWiringTests(unittest.TestCase):
    def test_v2_shell_has_no_cdn_dependency(self):
        index, _sim, _ui = _bundle()

        self.assertNotIn("https://", index)
        self.assertNotIn("https://unpkg.com", index)
        self.assertNotIn('src="https://', index)
        self.assertIn('/cockpit/v2/vendor/react.development.js', index)
        self.assertIn('/cockpit/v2/vendor/react-dom.development.js', index)
        self.assertIn('/cockpit/v2/vendor/babel.min.js', index)
        for name in ("react.development.js", "react-dom.development.js", "babel.min.js"):
            self.assertGreater((V2 / "vendor" / name).stat().st_size, 10_000)

    def test_operability_surfaces_use_v2_endpoints_and_no_v1_card_fallback(self):
        _index, sim, ui = _bundle()

        for endpoint in (
            "/api/v2/cockpit/state",
            "/api/v2/cockpit/memory-room",
            "/api/v2/cockpit/receipts-room",
            "/api/v2/cockpit/approvals",
            "/api/v2/cockpit/connectors",
        ):
            self.assertIn(endpoint, sim)
        self.assertNotIn("/api/v1/cards", sim)
        self.assertNotIn("approveQueued", sim)
        self.assertNotIn(": sim.state.approvals", ui)

    def test_unavailable_panels_are_explicit_not_mock_fallbacks(self):
        _index, _sim, ui = _bundle()

        for text in (
            "Memory room unavailable",
            "Receipts room unavailable",
            "Approvals data unavailable",
            "Connectors data unavailable",
            "Registry unavailable",
        ):
            self.assertIn(text, ui)
        for mocky in (
            "Queue is empty. Maez is well-behaved.",
            "Waiting for /api/v2/cockpit/memory-room.",
            "Waiting for /api/v2/cockpit/receipts-room.",
        ):
            self.assertNotIn(mocky, ui)

    def test_write_controls_show_tier_confirmation_predicted_effect_and_receipt(self):
        _index, sim, ui = _bundle()
        combined = "\n".join((sim, ui))

        for text in (
            "decision_tier",
            "required_confirmation",
            "typed confirmation",
            "Predicted effect",
            "receipt after action",
            "lastWriteReceipt",
            "receipt_id",
            "outcome",
            "final_card_status",
        ):
            self.assertIn(text, combined)

    def test_local_storage_is_only_ui_preference_not_truth_source(self):
        index, sim, ui = _bundle()
        combined = "\n".join((index, sim, ui))
        local_storage_lines = [
            line.strip()
            for line in combined.splitlines()
            if "localStorage" in line
        ]
        self.assertTrue(local_storage_lines)
        joined = "\n".join(local_storage_lines)
        self.assertIn("maez.cockpit.surface", joined)
        self.assertIn("maez.cockpit.dashboardMode", joined)
        forbidden_truth_keys = re.compile(
            r"localStorage\.[gs]etItem\([^)]*(?:MAEZ_|flag|organ|memory|receipt|state|truth)",
            re.IGNORECASE,
        )
        self.assertIsNone(forbidden_truth_keys.search(joined))

    def test_new_surfaces_are_in_navigation(self):
        index, _sim, ui = _bundle()

        self.assertIn("{ id: 'approvals'", index)
        self.assertIn("{ id: 'connectors'", index)
        self.assertIn("surface === 'approvals'", index)
        self.assertIn("surface === 'connectors'", index)
        self.assertIn("function ApprovalsQueueSurface", ui)
        self.assertIn("function ConnectorsSurface", ui)


if __name__ == "__main__":
    unittest.main()
