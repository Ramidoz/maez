from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.body.desktop_presence_state import DesktopPresenceState


_NOW = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)


class DesktopAttentionShadowTests(unittest.TestCase):
    def _path(self, td: str) -> Path:
        return Path(td) / "desktop_attention_shadow_signatures.json"

    def test_default_signature_path_is_distinct_runtime_cache_not_memory(self):
        from core.cognition.desktop_attention_shadow import default_signature_path

        path = default_signature_path()
        self.assertIn(".local/state/maez", str(path))
        self.assertTrue(str(path).endswith("desktop_attention_shadow_signatures.json"))
        self.assertNotIn("world_window_signatures.json", str(path))
        self.assertNotIn("/memory/", str(path))

    def test_flag_off_returns_none_and_creates_no_cache(self):
        from core.cognition.desktop_attention_shadow import (
            maybe_collect_desktop_attention_shadow,
        )

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(
                    sensor_state="available",
                    app_class="code",
                    sampled_at=_NOW,
                ),
                enabled=False,
                signature_path=path,
            )
            self.assertIsNone(result)
            self.assertFalse(path.exists())

    def test_cold_start_records_signature_but_emits_no_entry(self):
        from core.cognition.desktop_attention_shadow import (
            maybe_collect_desktop_attention_shadow,
        )

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(
                    sensor_state="available",
                    app_class="code",
                    sampled_at=_NOW,
                ),
                enabled=True,
                signature_path=path,
            )
            self.assertIsNotNone(result)
            self.assertTrue(result.cold_start)
            self.assertEqual(result.entries, ())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "desktop_attention_shadow.v0")
            self.assertIn("active_surface", payload["signatures"])
            self.assertNotIn("code", path.read_text(encoding="utf-8"))

    def test_changed_app_class_emits_directionless_shadow_only(self):
        from core.cognition.desktop_attention_shadow import (
            maybe_collect_desktop_attention_shadow,
        )

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(
                    sensor_state="available",
                    app_class="code",
                    sampled_at=_NOW,
                ),
                enabled=True,
                signature_path=path,
            )
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(
                    sensor_state="available",
                    app_class="signal",
                    sampled_at=_NOW,
                ),
                enabled=True,
                signature_path=path,
            )
            self.assertFalse(result.cold_start)
            self.assertEqual(len(result.entries), 1)
            entry = result.entries[0]
            self.assertEqual(entry.field, "active_surface")
            self.assertEqual(entry.phrase, "active surface changed")
            rendered = repr(result) + json.dumps(result.receipt_payload(), sort_keys=True)
            self.assertNotIn("code", rendered)
            self.assertNotIn("signal", rendered)
            self.assertNotIn("communication", rendered)
            self.assertNotIn("focused-work", rendered)
            self.assertNotIn("to ", rendered.lower())
            self.assertNotIn("from ", rendered.lower())

    def test_same_app_class_emits_no_shadow(self):
        from core.cognition.desktop_attention_shadow import (
            maybe_collect_desktop_attention_shadow,
        )

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            state = DesktopPresenceState(
                sensor_state="available",
                app_class="code",
                sampled_at=_NOW,
            )
            maybe_collect_desktop_attention_shadow(state, enabled=True, signature_path=path)
            result = maybe_collect_desktop_attention_shadow(
                state,
                enabled=True,
                signature_path=path,
            )
            self.assertEqual(result.entries, ())

    def test_unavailable_sensor_returns_label_without_cache_or_delta(self):
        from core.cognition.desktop_attention_shadow import (
            maybe_collect_desktop_attention_shadow,
        )

        with tempfile.TemporaryDirectory() as td:
            path = self._path(td)
            result = maybe_collect_desktop_attention_shadow(
                DesktopPresenceState(
                    sensor_state="unavailable",
                    reason="no_active_window",
                    sampled_at=_NOW,
                ),
                enabled=True,
                signature_path=path,
            )
            self.assertFalse(result.cold_start)
            self.assertEqual(len(result.entries), 1)
            self.assertEqual(
                result.entries[0].phrase,
                "desktop attention sense unavailable",
            )
            self.assertFalse(path.exists())

    def test_module_imports_no_command_or_downstream_writers(self):
        src = Path("core/cognition/desktop_attention_shadow.py").read_text(
            encoding="utf-8"
        )
        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        forbidden = {
            "core.actions.action_engine",
            "core.actions.tool_loop",
            "core.evolution.drive_driven_curiosity",
            "core.evolution.wonderings",
            "core.evolution.wants",
            "core.cognition.salience_ledger",
            "core.cognition.fresh_moment_receipts",
            "core.infra.private_thoughts",
            "core.memory.lived_memory",
            "core.memory.memory_manager",
            "core.llm_client",
        }
        self.assertTrue(forbidden.isdisjoint(imported), imported)


if __name__ == "__main__":
    unittest.main()
