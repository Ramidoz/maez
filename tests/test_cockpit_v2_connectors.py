import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _paths(root: Path):
    from core.cockpit.connectors import CockpitConnectorPaths

    return CockpitConnectorPaths(
        registry_file=root / "config" / "connector_registry.json",
        receipt_log=root / "logs" / "cockpit_connector_receipts.jsonl",
    )


def _write_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "connectors": [
                    {
                        "id": "calendar",
                        "label": "Calendar",
                        "state": "disconnected",
                        "tier": "T2",
                        "granted_scopes": ["calendar.readonly"],
                        "last_activity": "never",
                        "intake_bus": "core.intake_bus.admit",
                    },
                    {
                        "id": "unknown",
                        "label": "Unknown",
                        "state": "disconnected",
                        "tier": "unclassified",
                        "granted_scopes": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )


class CockpitV2ConnectorsTests(unittest.TestCase):
    def test_connector_list_absent_registry_is_unavailable_and_creates_no_file(self):
        from core.cockpit.connectors import build_connectors_room

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            room = build_connectors_room(_paths(root))
            created = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

        self.assertEqual(created, [])
        self.assertEqual(room["status"], "unavailable")
        self.assertEqual(room["reason"], "connector_registry_absent")
        self.assertEqual(room["connectors"], [])

    def test_connector_list_reads_registry_and_renders_intake_bus_doorway(self):
        from core.cockpit.connectors import build_connectors_room

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _write_registry(paths.registry_file)

            room = build_connectors_room(paths)

        calendar = room["connectors"][0]
        self.assertEqual(room["status"], "ok")
        self.assertEqual(calendar["id"], "calendar")
        self.assertEqual(calendar["connection_state"], "disconnected")
        self.assertEqual(calendar["granted_scopes"], ["calendar.readonly"])
        self.assertEqual(room["intake_bus"]["doorway"], "core.intake_bus.admit")
        self.assertFalse(room["intake_bus"]["bypass_allowed"])
        self.assertIn("immune doorway", room["intake_bus"]["description"])

    def test_connect_disconnect_is_t2_typed_confirmed_and_receipted(self):
        from core.cockpit.connectors import apply_connector_action

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _write_registry(paths.registry_file)

            refused = apply_connector_action(
                "calendar",
                "connect",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
            )
            self.assertFalse(paths.receipt_log.exists())

            applied = apply_connector_action(
                "calendar",
                "connect",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                typed_confirmation="CONNECT calendar",
            )
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(refused["status"], "refused")
        self.assertEqual(refused["reason"], "typed_confirmation_required")
        self.assertEqual(refused["required_confirmation"], "CONNECT calendar")
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["tier"], "T2")
        self.assertEqual(receipt["connector_id"], "calendar")
        self.assertEqual(receipt["action"], "connect")
        self.assertEqual(receipt["intake_bus"], "core.intake_bus.admit")

    def test_unclassified_connector_cannot_be_connected(self):
        from core.cockpit.connectors import apply_connector_action

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _write_registry(paths.registry_file)
            result = apply_connector_action(
                "unknown",
                "connect",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                typed_confirmation="CONNECT unknown",
            )

            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "connector_unclassified")

    def test_no_connector_attach_path_routes_around_intake_bus(self):
        source = (Path(__file__).resolve().parents[1] / "core" / "cockpit" / "connectors.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("core.intake_bus.admit", source)
        for forbidden in (
            "memory.store(",
            "MemoryManager(",
            "EpisodeStore(",
            "lived_episodes",
            "raw_memory",
        ):
            self.assertNotIn(forbidden, source)

    def test_v2_route_is_owner_private_and_uses_connector_guard(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _write_registry(paths.registry_file)
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), (
                mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)
            ), mock.patch.object(wi, "_cockpit_connector_paths", return_value=paths):
                response = wi.app.test_client().post(
                    "/api/v2/cockpit/connectors/calendar",
                    json={
                        "action": "connect",
                        "confirm_click_token": "confirm",
                        "typed_confirmation": "CONNECT calendar",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "applied")

    def test_v2_ui_exposes_connectors_room_without_intake_bypass(self):
        index = Path("web/cockpit/v2/index.html").read_text(encoding="utf-8")
        sim = Path("web/cockpit/v2/sim.jsx").read_text(encoding="utf-8")
        ui = Path("web/cockpit/v2/terminal-ui.jsx").read_text(encoding="utf-8")
        combined = "\n".join((index, sim, ui))

        self.assertIn("ConnectorsSurface", index)
        self.assertIn("surface === 'connectors'", index)
        self.assertIn("/api/v2/cockpit/connectors", sim)
        self.assertIn("connectorsRoom", sim)
        self.assertIn("function ConnectorsSurface", ui)
        self.assertIn("immune doorway", ui)
        for forbidden in ("memory.store(", "EpisodeStore(", "raw_memory"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
