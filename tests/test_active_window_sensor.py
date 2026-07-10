# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Behavioral gate for Slice 4 active-window identity + geometry."""

from __future__ import annotations

import ast
import inspect
import json
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core.body.active_window_sensor import (
    COORDINATE_SPACE,
    SCHEMA_VERSION,
    ActiveWindowReading,
    read_compositor_snapshot,
    sample_active_window,
)
from core.vision_contract.frozen_frame import CropBox as HarnessCropBox
from core.vision_contract.geometry import CropBox
from scripts.active_window_geometry_probe import _call_timeout_ms, normalize_display_state
import scripts.active_window_geometry_probe as probe_module
import core.body.active_window_sensor as sensor_module


class SharedCropBoxContractTests(unittest.TestCase):
    def test_slice_3_and_slice_4_share_one_frozen_crop_box_type(self):
        self.assertIs(HarnessCropBox, CropBox)
        crop = CropBox(left=10, top=20, right=110, bottom=220)
        with self.assertRaises(FrozenInstanceError):
            crop.left = 0


_NOW = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)


def _payload(
    *,
    window: dict[str, object] | None = None,
    displays: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "status": "ok",
        "display_config_serial": 41,
        "window": window
        or {
            "title": "private plan.md",
            "class": "Code",
            "x": -1909,
            "y": 10,
            "width": 100,
            "height": 50,
            "monitor": 1,
        },
        "displays": displays
        or [
            {
                "display_id": "DP-1",
                "x": -1920,
                "y": 0,
                "logical_width": 1920,
                "logical_height": 1080,
                "native_width": 3840,
                "native_height": 2160,
                "scale": "2",
            }
        ],
    }


def _sample(payload: dict[str, object], *, privacy_state: str | None = None):
    return sample_active_window(
        now=_NOW,
        probe_fn=lambda _timeout: payload,
        privacy_fn=lambda: privacy_state,
    )


class GeometryPublicationTests(unittest.TestCase):
    def test_v2_declares_process_memory_focus_binding(self):
        self.assertTrue(hasattr(sensor_module, "FocusBinding"))

    def test_v2_reading_has_additive_binding_field(self):
        self.assertIn("binding", {item.name for item in fields(ActiveWindowReading)})

    def test_focus_binding_is_validated_and_redacted_from_repr(self):
        binding_type = sensor_module.FocusBinding
        for pid, window_id in ((0, "actor"), (-1, "actor"), (True, "actor"), (7, "")):
            with self.subTest(pid=pid, window_id=window_id), self.assertRaises(ValueError):
                binding_type(pid=pid, window_id=window_id)

        binding = binding_type(pid=4242, window_id="private-actor-9")
        self.assertNotIn("private-actor-9", repr(binding))

    def test_focus_binding_window_id_is_bounded_and_control_free(self):
        binding_type = sensor_module.FocusBinding
        for window_id in ("x" * 257, "actor\n9", "actor\x009"):
            with self.subTest(window_id=repr(window_id)), self.assertRaises(ValueError):
                binding_type(pid=4242, window_id=window_id)

    def test_binding_is_optional_and_never_projected(self):
        geometry = _sample(_payload()).geometry
        binding = sensor_module.FocusBinding(pid=4242, window_id="private-actor-9")
        reading = ActiveWindowReading(
            state="available",
            timestamp=_NOW,
            app_class="Code",
            geometry=geometry,
            binding=binding,
        )

        serialized = json.dumps(reading.to_receipt(), sort_keys=True)
        self.assertNotIn("private-actor-9", repr(reading))
        self.assertNotIn("private-actor-9", serialized)
        self.assertNotIn("4242", serialized)
        self.assertNotIn("binding", serialized)

    def test_exact_probe_snapshot_constructs_process_memory_binding(self):
        payload = _payload()
        payload["window"] = {
            **payload["window"],
            "pid": 4242,
            "id": "private-actor-9",
        }

        reading = _sample(payload)

        self.assertIsNotNone(reading.binding)
        self.assertEqual(reading.binding.pid, 4242)
        self.assertEqual(reading.binding.window_id, "private-actor-9")

    def test_binding_shape_is_closed_by_reading_state(self):
        binding = sensor_module.FocusBinding(pid=4242, window_id="private-actor-9")
        with self.assertRaises(ValueError):
            ActiveWindowReading(
                state="available",
                timestamp=_NOW,
                app_class="Code",
                geometry=_sample(_payload()).geometry,
                binding="not-a-binding",
            )
        with self.assertRaises(ValueError):
            ActiveWindowReading(
                state="refused",
                timestamp=_NOW,
                reason="compositor_unreachable",
                binding=binding,
            )

    def test_negative_global_origin_becomes_display_local_native_pixels(self):
        reading = _sample(_payload())

        self.assertEqual(reading.state, "available")
        self.assertEqual(reading.app_class, "Code")
        geometry = reading.geometry
        self.assertIsNotNone(geometry)
        self.assertEqual(
            (geometry.x, geometry.y, geometry.width, geometry.height),
            (22, 20, 200, 100),
        )
        self.assertEqual(geometry.crop_box, CropBox(22, 20, 222, 120))
        self.assertEqual(geometry.coordinate_space, COORDINATE_SPACE)
        self.assertEqual(geometry.display_id, "DP-1")
        self.assertEqual((geometry.scale_numerator, geometry.scale_denominator), (2, 1))
        self.assertEqual((geometry.display_width, geometry.display_height), (3840, 2160))
        self.assertEqual(geometry.display_config_serial, 41)

    def test_fractional_hidpi_uses_floor_left_top_and_ceil_right_bottom(self):
        payload = _payload(
            window={
                "title": "private",
                "class": "Code",
                "x": 1,
                "y": 1,
                "width": 2,
                "height": 2,
            },
            displays=[
                {
                    "display_id": "eDP-1",
                    "x": 0,
                    "y": 0,
                    "logical_width": 8,
                    "logical_height": 8,
                    "native_width": 10,
                    "native_height": 10,
                    "scale": "1.25",
                }
            ],
        )

        geometry = _sample(payload).geometry

        self.assertEqual(geometry.crop_box, CropBox(1, 1, 4, 4))
        self.assertEqual((geometry.x, geometry.y, geometry.width, geometry.height), (1, 1, 3, 3))
        self.assertEqual((geometry.scale_numerator, geometry.scale_denominator), (5, 4))

    def test_slice5_can_retain_private_fractional_origin_calibration(self):
        from scripts.atspi_window_probe import WindowCalibration, native_region

        calibrated_geometry = sensor_module.WindowGeometry(
            x=1, y=1, width=6, height=11, display_id="eDP-1",
            display_width=100, display_height=100, scale_numerator=5,
            scale_denominator=4, display_config_serial=41,
            coordinate_space=COORDINATE_SPACE,
        )
        calibration = WindowCalibration(logical_x=1, logical_y=1)
        self.assertEqual(
            native_region((0, 0, 4, 8), calibrated_geometry, calibration),
            CropBox(1, 1, 7, 12),
        )

    def test_schema_is_versioned_and_values_are_frozen(self):
        reading = _sample(_payload())

        self.assertEqual(SCHEMA_VERSION, "active_window_geometry.v2")
        self.assertEqual(reading.schema_version, SCHEMA_VERSION)
        with self.assertRaises(FrozenInstanceError):
            reading.state = "refused"
        with self.assertRaises(FrozenInstanceError):
            reading.geometry.x = 0


class ExclusionAndRefusalTests(unittest.TestCase):
    def _assert_content_blind_refusal(self, reading, reason: str) -> None:
        self.assertIn(reading.state, {"excluded", "refused"})
        self.assertEqual(reading.reason, reason)
        self.assertIsNone(reading.app_class)
        self.assertIsNone(reading.geometry)
        self.assertEqual(
            reading.to_receipt(),
            {
                "schema_version": SCHEMA_VERSION,
                "state": reading.state,
                "timestamp": "2026-07-09T12:00:00+00:00",
                "refusal_reason": reason,
            },
        )

    def test_sensitive_window_is_excluded_before_geometry_is_published(self):
        reading = _sample(
            _payload(
                window={
                    "title": "Vault",
                    "class": "Bitwarden",
                    "x": 0,
                    "y": 0,
                    "width": 800,
                    "height": 600,
                },
                displays=[
                    {
                        "display_id": "eDP-1",
                        "x": 0,
                        "y": 0,
                        "logical_width": 1920,
                        "logical_height": 1080,
                        "native_width": 1920,
                        "native_height": 1080,
                        "scale": "1",
                    }
                ],
            )
        )

        self._assert_content_blind_refusal(reading, "sensitive_window")

    def test_missing_class_is_excluded_even_when_title_is_present(self):
        payload = _payload()
        payload["window"] = {
            "title": "ordinary document",
            "class": "",
            "x": 0,
            "y": 0,
            "width": 10,
            "height": 10,
        }

        self._assert_content_blind_refusal(_sample(payload), "class_unavailable")

    def test_missing_none_whitespace_or_wrong_type_class_is_excluded(self):
        for value in (None, "   ", 7):
            with self.subTest(value=value):
                payload = _payload()
                payload["window"] = {
                    "title": "ordinary document",
                    "class": value,
                    "x": 0,
                    "y": 0,
                    "width": 10,
                    "height": 10,
                }
                self._assert_content_blind_refusal(_sample(payload), "class_unavailable")

    def test_compositor_unreachable_is_typed_refusal(self):
        self._assert_content_blind_refusal(
            _sample({"status": "compositor_unreachable"}),
            "compositor_unreachable",
        )

    def test_probe_status_vocabulary_is_closed_and_typed(self):
        for reason in (
            "compositor_protocol_invalid",
            "unsupported_session",
            "geometry_unavailable",
            "display_unavailable",
            "display_config_changed",
        ):
            with self.subTest(reason=reason):
                self._assert_content_blind_refusal(_sample({"status": reason}), reason)
        self._assert_content_blind_refusal(
            _sample({"status": "private title in error"}),
            "compositor_protocol_invalid",
        )

    def test_missing_geometry_is_typed_refusal(self):
        payload = _payload()
        payload["window"] = {"title": "private", "class": "Code"}

        self._assert_content_blind_refusal(_sample(payload), "geometry_unavailable")

    def test_degenerate_bounds_refuse_instead_of_defaulting(self):
        payload = _payload()
        payload["window"] = {
            "title": "private",
            "class": "Code",
            "x": 0,
            "y": 0,
            "width": 0,
            "height": 10,
        }

        self._assert_content_blind_refusal(_sample(payload), "degenerate_bounds")

    def test_off_screen_bounds_refuse_instead_of_clamping(self):
        payload = _payload(
            window={
                "title": "private",
                "class": "Code",
                "x": 1900,
                "y": 100,
                "width": 100,
                "height": 100,
            },
            displays=[
                {
                    "display_id": "eDP-1",
                    "x": 0,
                    "y": 0,
                    "logical_width": 1920,
                    "logical_height": 1080,
                    "native_width": 1920,
                    "native_height": 1080,
                    "scale": "1",
                }
            ],
        )

        self._assert_content_blind_refusal(_sample(payload), "off_screen_bounds")

    def test_cross_display_window_refuses_one_display_one_scale_lie(self):
        displays = [
            {
                "display_id": "DP-1",
                "x": 0,
                "y": 0,
                "logical_width": 100,
                "logical_height": 100,
                "native_width": 100,
                "native_height": 100,
                "scale": "1",
            },
            {
                "display_id": "DP-2",
                "x": 100,
                "y": 0,
                "logical_width": 100,
                "logical_height": 100,
                "native_width": 200,
                "native_height": 200,
                "scale": "2",
            },
        ]
        payload = _payload(
            window={
                "title": "private",
                "class": "Code",
                "x": 90,
                "y": 10,
                "width": 20,
                "height": 20,
            },
            displays=displays,
        )

        self._assert_content_blind_refusal(_sample(payload), "cross_display_bounds")

    def test_missing_or_invalid_scale_refuses(self):
        payload = _payload()
        payload["displays"][0]["scale"] = "0"

        self._assert_content_blind_refusal(_sample(payload), "scale_unavailable")

    def test_display_count_is_bounded_before_geometry_matching(self):
        display = _payload()["displays"][0]
        payload = _payload(displays=[dict(display) for _ in range(17)])

        self._assert_content_blind_refusal(_sample(payload), "display_unavailable")

    def test_pause_and_curtain_refuse_before_compositor_probe(self):
        for privacy_state in ("paused", "curtain_drawn"):
            with self.subTest(privacy_state=privacy_state):
                probe = mock.Mock(side_effect=AssertionError("privacy must win"))
                reading = sample_active_window(
                    now=_NOW,
                    probe_fn=probe,
                    privacy_fn=lambda state=privacy_state: state,
                )

                self._assert_content_blind_refusal(reading, privacy_state)
                probe.assert_not_called()

    def test_privacy_transition_during_probe_discards_snapshot(self):
        privacy = mock.Mock(side_effect=[None, "curtain_drawn"])

        reading = sample_active_window(
            now=_NOW,
            probe_fn=lambda _timeout: _payload(),
            privacy_fn=privacy,
        )

        self._assert_content_blind_refusal(reading, "curtain_drawn")
        self.assertEqual(privacy.call_count, 2)

    def test_privacy_transition_during_validation_blocks_publication(self):
        privacy = mock.Mock(side_effect=[None, None, "paused"])

        reading = sample_active_window(
            now=_NOW,
            probe_fn=lambda _timeout: _payload(),
            privacy_fn=privacy,
        )

        self._assert_content_blind_refusal(reading, "paused")
        self.assertEqual(privacy.call_count, 3)


class ReceiptAndBoundaryTests(unittest.TestCase):
    def test_success_receipt_is_content_light_and_never_carries_title(self):
        secret_title = "Re confidential salary -- Roadmap"
        payload = _payload()
        payload["window"]["title"] = secret_title

        reading = _sample(payload)
        receipt = reading.to_receipt()
        serialized = json.dumps(receipt, sort_keys=True)

        self.assertEqual(
            set(receipt),
            {
                "schema_version",
                "state",
                "timestamp",
                "refusal_reason",
                "app_class",
                "geometry",
            },
        )
        self.assertNotIn("title", {field.name for field in fields(ActiveWindowReading)})
        self.assertNotIn(secret_title, repr(reading))
        self.assertNotIn(secret_title, serialized)
        self.assertNotIn('"title"', serialized)

    def test_refusal_reason_runtime_allowlist_blocks_content(self):
        with self.assertRaises(ValueError):
            ActiveWindowReading(
                state="refused",
                timestamp=_NOW,
                reason="private title in refusal",
            )

    def test_one_probe_snapshot_drives_exclusion_and_geometry(self):
        probe = mock.Mock(return_value=_payload())

        reading = sample_active_window(
            now=_NOW,
            probe_fn=probe,
            privacy_fn=lambda: None,
        )

        self.assertEqual(reading.state, "available")
        probe.assert_called_once()

    def test_new_sensor_has_no_capture_service_or_admission_surface(self):
        root = Path(__file__).resolve().parents[1]
        sensor_path = root / "core" / "body" / "active_window_sensor.py"
        probe_path = root / "scripts" / "active_window_geometry_probe.py"
        source = sensor_path.read_text(encoding="utf-8") + probe_path.read_text(encoding="utf-8")
        for forbidden in (
            "screenshot",
            "ImageGrab",
            "llama-vision.service",
            "systemctl",
            "MAEZ_SCREEN_PERCEPTION",
            "daemon.maez_daemon",
            "core.cognition",
            "write_memory",
            "prompt_block",
        ):
            self.assertNotIn(forbidden, source)

    def test_only_dormant_atspi_helper_imports_the_dormant_sensor(self):
        root = Path(__file__).resolve().parents[1]
        callers = []
        for top in ("core", "daemon", "skills", "scripts"):
            for path in (root / top).rglob("*.py"):
                if path.name == "active_window_sensor.py":
                    continue
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except (OSError, SyntaxError, UnicodeDecodeError):
                    continue
                for node in ast.walk(tree):
                    imported = False
                    if isinstance(node, ast.Import):
                        imported = any(
                            alias.name == "core.body.active_window_sensor"
                            for alias in node.names
                        )
                    elif isinstance(node, ast.ImportFrom):
                        imported = (
                            node.module == "core.body.active_window_sensor"
                            or node.module == "core.body"
                            and any(
                                alias.name == "active_window_sensor"
                                for alias in node.names
                            )
                        )
                    if imported:
                        callers.append(str(path.relative_to(root)))
                        break
        self.assertEqual(callers, ["scripts/atspi_window_probe.py"])

    def test_sensor_and_probe_import_allowlists_exclude_admission_surfaces(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "core/body/active_window_sensor.py": {
                "__future__",
                "json",
                "math",
                "os",
                "subprocess",
                "unicodedata",
                "collections.abc",
                "dataclasses",
                "decimal",
                "datetime",
                "fractions",
                "pathlib",
                "typing",
                "core.vision_contract.geometry",
                "core.vision_contract.screen_privacy",
                "skills.screen_perception",
            },
            "scripts/active_window_geometry_probe.py": {
                "__future__",
                "json",
                "os",
                "sys",
                "decimal",
                "gi.repository",
            },
        }
        for relative, allowed in expected.items():
            with self.subTest(relative=relative):
                tree = ast.parse((root / relative).read_text(encoding="utf-8"))
                imports = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module)
                self.assertEqual(imports - allowed, set())


class ProbeAdapterTests(unittest.TestCase):
    def test_adapter_invokes_fixed_system_python_helper_without_shell(self):
        completed = mock.Mock(returncode=0, stdout=json.dumps(_payload()), stderr="")
        with mock.patch("subprocess.run", return_value=completed) as run:
            payload = read_compositor_snapshot(timeout=1.25)

        self.assertEqual(payload["status"], "ok")
        command = run.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/python3")
        self.assertTrue(command[1].endswith("scripts/active_window_geometry_probe.py"))
        self.assertEqual(command[2], "1250")
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs["timeout"], 1.25)
        self.assertIs(run.call_args.kwargs["capture_output"], True)

    def test_adapter_timeout_and_malformed_output_fail_closed(self):
        with mock.patch(
            "subprocess.run",
            side_effect=TimeoutError("late"),
        ):
            self.assertEqual(
                read_compositor_snapshot(timeout=0.1),
                {"status": "compositor_unreachable"},
            )
        with mock.patch(
            "subprocess.run",
            return_value=mock.Mock(returncode=0, stdout="not json", stderr=""),
        ):
            self.assertEqual(
                read_compositor_snapshot(timeout=0.1),
                {"status": "compositor_protocol_invalid"},
            )

    def test_adapter_rejects_malformed_or_extreme_timeout_without_spawning(self):
        for timeout in ("1", True, 0, -1, float("nan"), float("inf"), 1e308):
            with self.subTest(timeout=timeout), mock.patch("subprocess.run") as run:
                self.assertEqual(
                    read_compositor_snapshot(timeout=timeout),
                    {"status": "compositor_unreachable"},
                )
                run.assert_not_called()


class MutterNormalizationTests(unittest.TestCase):
    def test_three_dbus_calls_share_one_bounded_parent_timeout(self):
        self.assertEqual(_call_timeout_ms(1000), 250)
        self.assertEqual(_call_timeout_ms(2), 1)

    def test_current_mode_becomes_display_bounds_scale_and_id(self):
        specs = ("DP-1", "vendor", "product", "serial")
        resources = (
            77,
            [
                (
                    specs,
                    [
                        (
                            "3840x2160@60",
                            3840,
                            2160,
                            60.0,
                            2.0,
                            [1.0, 2.0],
                            {"is-current": True},
                        )
                    ],
                    {},
                )
            ],
            [(-1920, 0, 2.0, 0, False, [specs], {})],
            {"layout-mode": 1},
        )

        serial, displays = normalize_display_state(resources)

        self.assertEqual(serial, 77)
        self.assertEqual(
            displays,
            [
                {
                    "display_id": "DP-1",
                    "x": -1920,
                    "y": 0,
                    "logical_width": 1920,
                    "logical_height": 1080,
                    "native_width": 3840,
                    "native_height": 2160,
                    "scale": "2.0",
                }
            ],
        )

    def test_rotated_monitor_swaps_native_dimensions_before_scaling(self):
        specs = ("eDP-1", "vendor", "product", "serial")
        resources = (
            3,
            [
                (
                    specs,
                    [("mode", 2400, 1600, 60.0, 1.25, [1.25], {"is-current": True})],
                    {},
                )
            ],
            [(0, 0, 1.25, 1, True, [specs], {})],
            {"layout-mode": 1},
        )

        _serial, displays = normalize_display_state(resources)

        self.assertEqual(
            (
                displays[0]["logical_width"],
                displays[0]["logical_height"],
                displays[0]["native_width"],
                displays[0]["native_height"],
            ),
            (1280, 1920, 1600, 2400),
        )

    def test_missing_current_mode_refuses_normalization(self):
        specs = ("DP-1", "vendor", "product", "serial")
        resources = (
            1,
            [(specs, [("mode", 100, 100, 60.0, 1.0, [1.0], {})], {})],
            [(0, 0, 1.0, 0, True, [specs], {})],
            {"layout-mode": 1},
        )

        with self.assertRaises(ValueError):
            normalize_display_state(resources)

    def test_physical_or_unknown_layout_mode_refuses(self):
        specs = ("DP-1", "vendor", "product", "serial")
        base = (
            1,
            [
                (
                    specs,
                    [("mode", 200, 200, 60.0, 2.0, [2.0], {"is-current": True})],
                    {},
                )
            ],
            [(0, 0, 2.0, 0, True, [specs], {})],
        )
        for layout_mode in (2, "1"):
            with self.subTest(layout_mode=layout_mode), self.assertRaises(ValueError):
                normalize_display_state((*base, {"layout-mode": layout_mode}))

    def test_transform_is_closed_to_mutters_declared_domain(self):
        specs = ("DP-1", "vendor", "product", "serial")
        for transform in (-1, 8, 9):
            resources = (
                1,
                [
                    (
                        specs,
                        [("mode", 100, 100, 60.0, 1.0, [1.0], {"is-current": True})],
                        {},
                    )
                ],
                [(0, 0, 1.0, transform, True, [specs], {})],
                {"layout-mode": 1},
            )
            with self.subTest(transform=transform), self.assertRaises(ValueError):
                normalize_display_state(resources)

    def test_absent_layout_mode_uses_mutters_documented_logical_default(self):
        specs = ("DP-1", "vendor", "product", "serial")
        resources = (
            1,
            [
                (
                    specs,
                    [("mode", 200, 100, 60.0, 2.0, [2.0], {"is-current": True})],
                    {},
                )
            ],
            [(0, 0, 2.0, 0, True, [specs], {})],
            {},
        )

        _serial, displays = normalize_display_state(resources)

        self.assertEqual(
            (displays[0]["logical_width"], displays[0]["logical_height"]),
            (100, 50),
        )


class MutterProbeEntrypointTests(unittest.TestCase):
    class _Reply:
        def __init__(self, value):
            self.value = value

        def unpack(self):
            return self.value

    def _fake_gio(self, display_states, window, *, focused_values=None):
        calls = []
        sessions = []
        states = iter(display_states)
        reply = self._Reply

        class Bus:
            def call_sync(_self, dest, path, interface, method, *args):
                calls.append((dest, path, interface, method, args))
                if interface == probe_module.DISPLAY_INTERFACE:
                    return reply(next(states))
                if interface == probe_module.FOCUSED_INTERFACE:
                    values = (
                        focused_values
                        if focused_values is not None
                        else (json.dumps(window),)
                    )
                    return reply(values)
                raise AssertionError("unexpected D-Bus interface")

        def bus_get_sync(session, _cancellable):
            sessions.append(session)
            return Bus()

        gio = types.SimpleNamespace(
            BusType=types.SimpleNamespace(SESSION="session"),
            DBusCallFlags=types.SimpleNamespace(NO_AUTO_START="no-auto-start"),
            bus_get_sync=bus_get_sync,
        )
        gi = types.ModuleType("gi")
        repository = types.ModuleType("gi.repository")
        repository.Gio = gio
        gi.repository = repository
        return {"gi": gi, "gi.repository": repository}, calls, sessions

    @staticmethod
    def _display_state(serial=1, *, native_width=100):
        specs = ("DP-1", "vendor", "product", "serial")
        return (
            serial,
            [
                (
                    specs,
                    [
                        (
                            "mode",
                            native_width,
                            100,
                            60.0,
                            1.0,
                            [1.0],
                            {"is-current": True},
                        )
                    ],
                    {},
                )
            ],
            [(0, 0, 1.0, 0, True, [specs], {})],
            {"layout-mode": 1},
        )

    @staticmethod
    def _window():
        return {
            "title": "private",
            "wm_class": "Code",
            "x": 1,
            "y": 2,
            "width": 10,
            "height": 20,
            "monitor": 0,
        }

    def test_display_state_brackets_exactly_one_focused_window_get(self):
        modules, calls, sessions = self._fake_gio(
            [self._display_state(9), self._display_state(9)], self._window()
        )
        with mock.patch.dict(sys.modules, modules):
            payload = probe_module.probe(900)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(sessions, ["session"])
        self.assertEqual(
            [(call[0], call[1], call[2], call[3]) for call in calls],
            [
                (
                    probe_module.DISPLAY_DEST,
                    probe_module.DISPLAY_PATH,
                    probe_module.DISPLAY_INTERFACE,
                    "GetCurrentState",
                ),
                (
                    probe_module.FOCUSED_DEST,
                    probe_module.FOCUSED_PATH,
                    probe_module.FOCUSED_INTERFACE,
                    "Get",
                ),
                (
                    probe_module.DISPLAY_DEST,
                    probe_module.DISPLAY_PATH,
                    probe_module.DISPLAY_INTERFACE,
                    "GetCurrentState",
                ),
            ],
        )
        for _dest, _path, _interface, _method, args in calls:
            self.assertEqual(args[-3], "no-auto-start")
            self.assertEqual(args[-2], 225)
            self.assertIsNone(args[-1])

    def test_probe_has_explicit_in_process_binding_mode(self):
        self.assertIn("include_binding", inspect.signature(probe_module.probe).parameters)

    def test_binding_identity_stays_in_explicit_in_process_packet_only(self):
        window = {**self._window(), "pid": 4242, "id": "private-actor-9"}
        modules, _calls, _sessions = self._fake_gio(
            [self._display_state(9), self._display_state(9)], window
        )
        with mock.patch.dict(sys.modules, modules):
            ordinary = probe_module.probe(900)

        modules, _calls, _sessions = self._fake_gio(
            [self._display_state(9), self._display_state(9)], window
        )
        with mock.patch.dict(sys.modules, modules):
            in_process = probe_module.probe(900, include_binding=True)

        self.assertNotIn("pid", ordinary["window"])
        self.assertNotIn("id", ordinary["window"])
        self.assertEqual(in_process["window"].get("pid"), 4242)
        self.assertEqual(in_process["window"].get("id"), "private-actor-9")

    def test_display_reconfiguration_around_window_read_refuses(self):
        modules, _calls, _sessions = self._fake_gio(
            [self._display_state(1), self._display_state(2)], self._window()
        )
        with mock.patch.dict(sys.modules, modules):
            payload = probe_module.probe(900)

        self.assertEqual(payload, {"status": "display_config_changed"})

    def test_same_serial_but_changed_display_geometry_refuses(self):
        modules, _calls, _sessions = self._fake_gio(
            [
                self._display_state(1, native_width=100),
                self._display_state(1, native_width=200),
            ],
            self._window(),
        )
        with mock.patch.dict(sys.modules, modules):
            payload = probe_module.probe(900)

        self.assertEqual(payload, {"status": "display_config_changed"})

    def test_malformed_display_packet_is_protocol_invalid_not_unreachable(self):
        malformed = (1, [None], [], {"layout-mode": 1})
        modules, _calls, _sessions = self._fake_gio([malformed], self._window())
        with mock.patch.dict(sys.modules, modules):
            payload = probe_module.probe(900)

        self.assertEqual(payload, {"status": "compositor_protocol_invalid"})

    def test_malformed_focused_window_packets_are_protocol_invalid(self):
        malformed_values = (
            ("one", "two"),
            ("not json",),
            (json.dumps([]),),
        )
        for values in malformed_values:
            with self.subTest(values=values):
                modules, _calls, _sessions = self._fake_gio(
                    [self._display_state(1)],
                    self._window(),
                    focused_values=values,
                )
                with mock.patch.dict(sys.modules, modules):
                    payload = probe_module.probe(900)

                self.assertEqual(
                    payload, {"status": "compositor_protocol_invalid"}
                )

    def test_direct_terminal_execution_refuses_title_bearing_probe(self):
        terminal = mock.Mock()
        terminal.isatty.return_value = True
        with (
            mock.patch.object(probe_module.sys, "stdout", terminal),
            mock.patch.object(probe_module, "probe") as probe,
        ):
            probe_module.main(["1000"])

        probe.assert_not_called()
        self.assertIn("interactive_output_refused", terminal.write.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
