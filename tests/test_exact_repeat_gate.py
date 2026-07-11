# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Behavioral gates for Vision Slice 7's dormant exact-repeat comparator."""

from __future__ import annotations

import ast
import builtins
import collections.abc
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone, tzinfo
from unittest.mock import patch

from core.body import atspi_sensor
import core.body.exact_repeat_gate as exact_repeat_gate
from core.body.exact_repeat_gate import (
    COMPARISON_MODES,
    DIMENSIONS,
    OUTCOME_AUTHORITY,
    PRIOR_DISPOSITIONS,
    PRIOR_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SOFT_ATSPI_REASONS,
    STATES,
    ChangeTokens,
    CurrentEnvelope,
    GateDecision,
    GatePrior,
    advance_prior,
    evaluate,
)
from core.vision_contract.geometry import CropBox, WindowGeometry


NOW = datetime(2026, 7, 11, 18, 0, tzinfo=timezone.utc)


def forbidden_gate_imports(source: str) -> list[str]:
    """Return gate imports outside the structural allowlist."""
    tree = ast.parse(source)
    allowed_imports = {
        "__future__",
        "dataclasses",
        "datetime",
        "types",
        "typing",
        "core.body.atspi_sensor",
    }
    allowed_atspi_symbols = {
        "EXCLUDED_REASONS",
        "REFUSAL_REASONS",
        "SCHEMA_VERSION",
        "SLICE4_REFUSAL_REASONS",
        "SLICE4_SCHEMA_VERSION",
    }
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    violations = imported_modules - allowed_imports
    violations.update(
        f"core.body.atspi_sensor.{alias.name}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "core.body.atspi_sensor"
        for alias in node.names
        if alias.name not in allowed_atspi_symbols
    )
    return sorted(violations)


def forbidden_atspi_calls(source: str) -> list[str]:
    """Return every call made through the constants-only AT-SPI namespace."""
    tree = ast.parse(source)
    return sorted(
        f"atspi_sensor.{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "atspi_sensor"
    )


def gate_import_references(source: str) -> bool:
    """Return whether source statically or dynamically imports the gate."""
    tree = ast.parse(source)
    importlib_aliases = {"importlib"}
    import_module_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "importlib"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            import_module_aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "import_module"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "core.body.exact_repeat_gate" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module in {"core.body.exact_repeat_gate", "exact_repeat_gate"}:
                return True
            if node.module in {None, "core.body"} and any(
                alias.name == "exact_repeat_gate" for alias in node.names
            ):
                return True
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target = node.args[0]
        if not isinstance(target, ast.Constant) or target.value != "core.body.exact_repeat_gate":
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            return True
        if isinstance(node.func, ast.Name) and node.func.id in import_module_aliases:
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in importlib_aliases
        ):
            return True
    return False


def _immutable_literal_container(value: ast.expr) -> bool:
    return isinstance(value, (ast.Tuple, ast.List, ast.Set)) and all(
        _immutable_global_expression(item) for item in value.elts
    )


def _immutable_global_expression(value: ast.expr) -> bool:
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.Tuple):
        return all(_immutable_global_expression(item) for item in value.elts)
    if (
        isinstance(value, ast.Subscript)
        and isinstance(value.value, ast.Name)
        and value.value.id == "Literal"
    ):
        return True
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.keywords:
        return False
    if value.func.id == "frozenset" and len(value.args) <= 1:
        return not value.args or _immutable_literal_container(value.args[0])
    if value.func.id != "MappingProxyType" or len(value.args) != 1:
        return False
    mapping = value.args[0]
    return isinstance(mapping, ast.Dict) and all(
        key is not None and _immutable_global_expression(key) and _immutable_global_expression(item)
        for key, item in zip(mapping.keys, mapping.values, strict=True)
    )


def mutable_global_lines(source: str) -> list[int]:
    """Return module assignments not proven to be explicitly immutable."""
    tree = ast.parse(source)
    violations = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if node.value is None or not _immutable_global_expression(node.value):
            violations.append(node.lineno)
    return violations


class RaisingTimezone(tzinfo):
    def utcoffset(self, value: datetime | None) -> timedelta | None:
        raise RuntimeError("timezone backend failed")

    def dst(self, value: datetime | None) -> timedelta | None:
        return None


def geometry(*, x: int = 100, serial: int = 41) -> WindowGeometry:
    return WindowGeometry(
        x=x,
        y=50,
        width=1200,
        height=800,
        display_id="DP-1",
        display_width=1920,
        display_height=1080,
        scale_numerator=2,
        scale_denominator=1,
        display_config_serial=serial,
        coordinate_space="display_local_native_device_pixels",
    )


def fact(
    value: str = "private literal",
    *,
    kind: str = "text",
    region: CropBox = CropBox(101, 52, 110, 62),
) -> atspi_sensor.AccessibilityFact:
    return atspi_sensor.AccessibilityFact(kind=kind, value=value, region=region)


def reading(
    *facts: atspi_sensor.AccessibilityFact,
    now: datetime = NOW,
    window_geometry: WindowGeometry | None = None,
    included_nodes: int = 2,
    excluded_nodes: tuple[tuple[str, int], ...] = (
        ("not_visible", 2),
        ("not_showing", 1),
    ),
) -> atspi_sensor.AccessibilityReading:
    return atspi_sensor.AccessibilityReading(
        state="available",
        timestamp=now,
        facts=facts or (fact(),),
        geometry=window_geometry or geometry(),
        included_nodes=included_nodes,
        excluded_nodes=excluded_nodes,
    )


class AtspiProjectionTests(unittest.TestCase):
    def projection(self, value: atspi_sensor.AccessibilityReading) -> str:
        return atspi_sensor.accessibility_projection_sha256(value)

    def test_projection_pins_canonical_payload(self):
        first = fact("alpha", kind="name", region=CropBox(101, 52, 110, 62))
        second = fact("beta", region=CropBox(111, 52, 120, 62))
        value = reading(second, first)
        expected_payload = {
            "projection_schema_version": "atspi_projection.v1",
            "sensor_schema_version": "atspi_accessibility.v1",
            "support": "atspi_state_bounds_only",
            "occlusion_checked": False,
            "included_nodes": 2,
            "excluded_nodes": [["not_showing", 1], ["not_visible", 2]],
            "facts": [
                [
                    "name",
                    5,
                    hashlib.sha256(b"alpha").hexdigest(),
                    101,
                    52,
                    110,
                    62,
                ],
                [
                    "text",
                    4,
                    hashlib.sha256(b"beta").hexdigest(),
                    111,
                    52,
                    120,
                    62,
                ],
            ],
        }
        expected = hashlib.sha256(
            json.dumps(expected_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(self.projection(value), expected)

    def test_equivalent_traversal_and_exclusion_order_has_same_projection(self):
        first = fact("alpha")
        second = fact("beta", region=CropBox(111, 52, 120, 62))
        left = reading(first, second)
        right = reading(
            second,
            first,
            excluded_nodes=(("not_showing", 1), ("not_visible", 2)),
        )
        self.assertEqual(self.projection(left), self.projection(right))

    def test_duplicate_fact_is_preserved(self):
        duplicate = fact("same")
        self.assertNotEqual(
            self.projection(reading(duplicate, duplicate)),
            self.projection(reading(duplicate)),
        )

    def test_fact_literal_kind_region_and_counts_change_projection(self):
        baseline = reading(fact("alpha"))
        changes = (
            reading(fact("bravo")),
            reading(fact("alpha", kind="name")),
            reading(fact("alpha", region=CropBox(102, 52, 111, 62))),
            reading(fact("alpha"), included_nodes=3),
            reading(fact("alpha"), excluded_nodes=(("not_visible", 1),)),
        )
        for changed in changes:
            with self.subTest(changed=changed):
                self.assertNotEqual(self.projection(baseline), self.projection(changed))

    def test_timestamp_and_geometry_do_not_change_projection(self):
        baseline = reading(fact("alpha"))
        changed = reading(
            fact("alpha"),
            now=datetime(2026, 7, 12, 1, 0, tzinfo=timezone.utc),
            window_geometry=geometry(x=101, serial=42),
        )
        self.assertEqual(self.projection(baseline), self.projection(changed))

    def test_refused_and_excluded_readings_cannot_mint_projection(self):
        blocked = (
            atspi_sensor.AccessibilityReading.refused("atspi_unreachable", NOW),
            atspi_sensor.AccessibilityReading.refused("excluded_path", NOW, excluded=True),
        )
        for value in blocked:
            with self.subTest(state=value.state), self.assertRaises(ValueError):
                self.projection(value)

    def test_refusal_vocabularies_are_public_immutable_aliases(self):
        self.assertIsInstance(atspi_sensor.OWN_REFUSAL_REASONS, frozenset)
        self.assertIsInstance(atspi_sensor.SLICE4_REFUSAL_REASONS, frozenset)
        self.assertIsInstance(atspi_sensor.EXCLUDED_REASONS, frozenset)
        self.assertEqual(
            atspi_sensor.REFUSAL_REASONS,
            atspi_sensor.OWN_REFUSAL_REASONS | atspi_sensor.SLICE4_REFUSAL_REASONS,
        )


class ContractTests(unittest.TestCase):
    DIGESTS = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)

    def tokens(self, **changes: object) -> ChangeTokens:
        values: dict[str, object] = {
            "active_crop_sha256": self.DIGESTS[0],
            "atspi_projection_sha256": self.DIGESTS[1],
            "geometry_sha256": self.DIGESTS[2],
            "focus_capture_sha256": self.DIGESTS[3],
            "comparison_mode": "full",
            "degraded_reason": None,
        }
        values.update(changes)
        return ChangeTokens(**values)

    def test_versions_and_closed_vocabularies_are_pinned(self):
        self.assertEqual(SCHEMA_VERSION, "vision_exact_repeat_gate.v1")
        self.assertEqual(PRIOR_SCHEMA_VERSION, "vision_exact_repeat_prior.v1")
        self.assertEqual(
            DIMENSIONS,
            (
                "active_crop_sha256",
                "atspi_projection_sha256",
                "geometry_sha256",
                "focus_capture_sha256",
                "comparison_mode",
            ),
        )
        self.assertEqual(COMPARISON_MODES, frozenset({"full", "crop_only"}))
        self.assertEqual(
            SOFT_ATSPI_REASONS,
            frozenset(
                {
                    "atspi_unreachable",
                    "atspi_protocol_invalid",
                    "identity_scan_exceeded",
                    "window_binding_unavailable",
                    "window_binding_ambiguous",
                    "bounds_unresolvable",
                    "no_visible_nodes",
                    "field_limit_exceeded",
                }
            ),
        )
        self.assertEqual(
            STATES,
            frozenset({"changed", "unchanged", "unavailable", "refused", "excluded"}),
        )
        self.assertEqual(
            PRIOR_DISPOSITIONS,
            frozenset({"absent", "valid", "unavailable", "incompatible"}),
        )

    def test_change_tokens_enforce_digest_and_mode_shape(self):
        self.tokens()
        self.tokens(
            comparison_mode="crop_only",
            atspi_projection_sha256=None,
            degraded_reason="atspi_unreachable",
        )
        invalid_changes = (
            {"active_crop_sha256": "A" * 64},
            {"geometry_sha256": "a" * 63},
            {"focus_capture_sha256": 7},
            {"comparison_mode": "semantic"},
            {"atspi_projection_sha256": None},
            {"degraded_reason": "atspi_unreachable"},
            {
                "comparison_mode": "crop_only",
                "atspi_projection_sha256": "b" * 64,
                "degraded_reason": "atspi_unreachable",
            },
            {
                "comparison_mode": "crop_only",
                "atspi_projection_sha256": None,
                "degraded_reason": None,
            },
            {
                "comparison_mode": "crop_only",
                "atspi_projection_sha256": None,
                "degraded_reason": "focus_changed",
            },
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.tokens(**changes)

    def test_values_are_frozen(self):
        tokens = self.tokens()
        values = (
            tokens,
            CurrentEnvelope(state="available", tokens=tokens),
            GatePrior(tokens=tokens),
            GateDecision(
                state="changed",
                reading_warranted=True,
                suppression_class=None,
                observed_at=NOW,
                reason="first_observation",
                comparison_mode="full",
                changed_dimensions=("first_observation",),
                candidate_prior=GatePrior(tokens=tokens),
            ),
        )
        for value in values:
            with self.subTest(value=type(value).__name__), self.assertRaises(FrozenInstanceError):
                value.state = "mutated"

    def test_digest_bearing_fields_and_candidates_are_hidden_from_repr(self):
        tokens = self.tokens()
        prior = GatePrior(tokens=tokens)
        envelope = CurrentEnvelope(state="available", tokens=tokens)
        decision = GateDecision(
            state="changed",
            reading_warranted=True,
            suppression_class=None,
            observed_at=NOW,
            reason="first_observation",
            comparison_mode="full",
            changed_dimensions=("first_observation",),
            candidate_prior=prior,
        )
        for value in (tokens, prior, envelope, decision):
            with self.subTest(value=type(value).__name__):
                rendered = repr(value)
                for digest in self.DIGESTS:
                    self.assertNotIn(digest, rendered)
                self.assertNotIn("tokens=", rendered)
                self.assertNotIn("candidate_prior=", rendered)

    def test_current_envelope_keeps_unvalidated_block_reason_private(self):
        private_reason = "arbitrary private upstream literal"
        malformed = CurrentEnvelope(
            state="state_swapped",
            reason=private_reason,
            source_lane="unknown_lane",
            source_schema_version="unknown_schema",
        )
        self.assertNotIn(private_reason, repr(malformed))
        self.assertNotIn("tokens=", repr(malformed))

    def test_gate_decision_enforces_closed_field_shapes(self):
        prior = GatePrior(tokens=self.tokens())
        GateDecision(
            state="changed",
            reading_warranted=True,
            suppression_class=None,
            observed_at=NOW,
            reason="signal_delta",
            comparison_mode="full",
            changed_dimensions=("active_crop_sha256", "geometry_sha256"),
            candidate_prior=prior,
            prior_disposition="valid",
        )
        GateDecision(
            state="changed",
            reading_warranted=True,
            suppression_class=None,
            observed_at=NOW,
            reason="first_observation",
            comparison_mode="full",
            changed_dimensions=("first_observation",),
            candidate_prior=prior,
        )
        GateDecision(
            state="unavailable",
            reading_warranted=True,
            suppression_class=None,
            observed_at=None,
            reason="timestamp_unavailable",
        )
        invalid_fields = (
            {"observed_at": None},
            {"observed_at": "2026-07-11T18:00:00Z"},
            {"observed_at": datetime(2026, 7, 11, 18, 0)},
            {"comparison_mode": "semantic"},
            {"changed_dimensions": ["active_crop_sha256"]},
            {"changed_dimensions": ("pixel_similarity",)},
            {"changed_dimensions": ("active_crop_sha256", "active_crop_sha256")},
            {"changed_dimensions": ("geometry_sha256", "active_crop_sha256")},
            {"changed_dimensions": ("first_observation", "active_crop_sha256")},
            {"candidate_prior": self.tokens()},
            {"prior_disposition": "corrupt"},
        )
        for changes in invalid_fields:
            values = {
                "state": "changed",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "first_observation",
            }
            values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                GateDecision(**values)

    def test_gate_decision_contains_raising_timezone(self):
        explosive = datetime(2026, 7, 11, 18, 0, tzinfo=RaisingTimezone())

        with self.assertRaises(ValueError):
            GateDecision(
                state="unavailable",
                reading_warranted=True,
                suppression_class=None,
                observed_at=explosive,
                reason="digest_unavailable",
            )

    def test_gate_decision_rejects_impossible_state_combinations(self):
        tokens = self.tokens()
        candidate = GatePrior(tokens=tokens)
        valid_changed = {
            "state": "changed",
            "reading_warranted": True,
            "suppression_class": None,
            "observed_at": NOW,
            "reason": "first_observation",
            "comparison_mode": "full",
            "changed_dimensions": ("first_observation",),
            "candidate_prior": candidate,
        }
        invalid_changed = (
            {"changed_dimensions": ()},
            {"candidate_prior": None},
            {"comparison_mode": None},
        )
        for changes in invalid_changed:
            values = valid_changed | changes
            with self.subTest(state="changed", changes=changes), self.assertRaises(ValueError):
                GateDecision(**values)

        invalid_non_changed = (
            {
                "state": "unchanged",
                "reading_warranted": False,
                "suppression_class": "economy",
                "comparison_mode": None,
            },
            {
                "state": "unchanged",
                "reading_warranted": False,
                "suppression_class": "economy",
                "comparison_mode": "full",
                "candidate_prior": candidate,
            },
            {
                "state": "unchanged",
                "reading_warranted": False,
                "suppression_class": "economy",
                "comparison_mode": "full",
                "changed_dimensions": ("active_crop_sha256",),
            },
            {
                "state": "refused",
                "reading_warranted": False,
                "suppression_class": "no_authority",
                "comparison_mode": "full",
            },
            {
                "state": "excluded",
                "reading_warranted": False,
                "suppression_class": "privacy",
                "candidate_prior": candidate,
            },
            {
                "state": "refused",
                "reading_warranted": False,
                "suppression_class": "no_authority",
                "changed_dimensions": ("geometry_sha256",),
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "changed_dimensions": ("geometry_sha256",),
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "candidate_prior": candidate,
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "comparison_mode": "full",
                "candidate_prior": GatePrior(
                    tokens=tokens, schema_version="vision_exact_repeat_prior.v0"
                ),
            },
        )
        for values in invalid_non_changed:
            with self.subTest(values=values), self.assertRaises(ValueError):
                GateDecision(observed_at=NOW, **values)

    def test_gate_decision_valid_block_metadata_is_hidden_from_repr(self):
        decision = GateDecision(
            state="refused",
            reading_warranted=False,
            suppression_class="no_authority",
            observed_at=NOW,
            reason="atspi_unreachable",
            upstream_lane="slice5",
            upstream_schema_version="atspi_accessibility.v1",
        )
        rendered = repr(decision)
        for literal in ("atspi_unreachable", "slice5", "atspi_accessibility.v1"):
            self.assertNotIn(literal, rendered)

    def test_gate_decision_rejects_forged_reason_and_upstream_combinations(self):
        candidate = GatePrior(tokens=self.tokens())
        forged = (
            {
                "state": "excluded",
                "reading_warranted": False,
                "suppression_class": "privacy",
                "observed_at": NOW,
                "reason": "private literal",
                "upstream_lane": "slice5",
                "upstream_schema_version": "atspi_accessibility.v1",
            },
            {
                "state": "unchanged",
                "reading_warranted": False,
                "suppression_class": "economy",
                "observed_at": NOW,
                "reason": "sensitive_window",
                "comparison_mode": "full",
                "upstream_lane": "slice4",
                "upstream_schema_version": "active_window_geometry.v2",
            },
            {
                "state": "changed",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "exact_repeat",
                "comparison_mode": "full",
                "changed_dimensions": ("active_crop_sha256",),
                "candidate_prior": candidate,
            },
        )

        constructed = []
        for fields in forged:
            with self.subTest(state=fields["state"]), self.assertRaises(ValueError):
                constructed.append(GateDecision(**fields))
        self.assertEqual(constructed, [])

    def test_gate_decision_rejects_reason_specific_shape_forgeries_before_advance(self):
        candidate = GatePrior(tokens=self.tokens())
        forged = (
            {
                "state": "changed",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "first_observation",
                "comparison_mode": "full",
                "changed_dimensions": ("active_crop_sha256",),
                "candidate_prior": candidate,
                "prior_disposition": "absent",
            },
            {
                "state": "changed",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "first_observation",
                "comparison_mode": "full",
                "changed_dimensions": ("first_observation",),
                "candidate_prior": candidate,
                "prior_disposition": "valid",
            },
            {
                "state": "changed",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "signal_delta",
                "comparison_mode": "full",
                "changed_dimensions": ("active_crop_sha256",),
                "candidate_prior": candidate,
                "prior_disposition": "absent",
            },
            {
                "state": "changed",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "signal_delta",
                "comparison_mode": "full",
                "changed_dimensions": ("first_observation",),
                "candidate_prior": candidate,
                "prior_disposition": "valid",
            },
            {
                "state": "unchanged",
                "reading_warranted": False,
                "suppression_class": "economy",
                "observed_at": NOW,
                "reason": "exact_repeat",
                "comparison_mode": "full",
                "prior_disposition": "absent",
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": None,
                "reason": "timestamp_unavailable",
                "comparison_mode": "full",
                "candidate_prior": candidate,
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "timestamp_unavailable",
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "current_protocol_invalid",
                "comparison_mode": "full",
                "candidate_prior": candidate,
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "digest_unavailable",
                "comparison_mode": "full",
                "candidate_prior": candidate,
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "prior_unavailable",
                "prior_disposition": "unavailable",
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "prior_unavailable",
                "comparison_mode": "full",
                "candidate_prior": candidate,
                "prior_disposition": "absent",
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "prior_schema_incompatible",
                "prior_disposition": "incompatible",
            },
            {
                "state": "unavailable",
                "reading_warranted": True,
                "suppression_class": None,
                "observed_at": NOW,
                "reason": "prior_schema_incompatible",
                "comparison_mode": "full",
                "candidate_prior": candidate,
                "prior_disposition": "absent",
            },
        )

        constructed = []
        for fields in forged:
            with self.subTest(reason=fields["reason"]), self.assertRaises(ValueError):
                constructed.append(GateDecision(**fields))
        committed = [
            advance_prior(None, decision, downstream_succeeded=True)
            for decision in constructed
            if advance_prior(None, decision, downstream_succeeded=True) is not None
        ]
        self.assertEqual(constructed, [])
        self.assertEqual(committed, [])

    def test_outcome_authority_table_is_closed_and_constructor_enforced(self):
        expected = {
            "changed": (True, None),
            "unchanged": (False, "economy"),
            "unavailable": (True, None),
            "refused": (False, "no_authority"),
            "excluded": (False, "privacy"),
        }
        self.assertEqual(dict(OUTCOME_AUTHORITY), expected)
        tokens = self.tokens()
        for state, (reading_warranted, suppression_class) in expected.items():
            with self.subTest(state=state):
                shape = {}
                if state == "changed":
                    shape = {
                        "reason": "first_observation",
                        "comparison_mode": "full",
                        "changed_dimensions": ("first_observation",),
                        "candidate_prior": GatePrior(tokens=tokens),
                    }
                elif state == "unchanged":
                    shape = {
                        "reason": "exact_repeat",
                        "comparison_mode": "full",
                        "prior_disposition": "valid",
                    }
                elif state == "unavailable":
                    shape = {"reason": "digest_unavailable"}
                elif state == "refused":
                    shape = {
                        "reason": "atspi_unreachable",
                        "upstream_lane": "slice5",
                        "upstream_schema_version": "atspi_accessibility.v1",
                    }
                elif state == "excluded":
                    shape = {
                        "reason": "excluded_path",
                        "upstream_lane": "slice5",
                        "upstream_schema_version": "atspi_accessibility.v1",
                    }
                GateDecision(
                    state=state,
                    reading_warranted=reading_warranted,
                    suppression_class=suppression_class,
                    observed_at=NOW,
                    **shape,
                )

        invalid = (
            ("changed", False, None),
            ("changed", 1, None),
            ("unchanged", False, None),
            ("unavailable", True, "economy"),
            ("refused", True, "no_authority"),
            ("excluded", False, "economy"),
            ("unknown", True, None),
        )
        for state, reading_warranted, suppression_class in invalid:
            with self.subTest(state=state), self.assertRaises(ValueError):
                GateDecision(
                    state=state,
                    reading_warranted=reading_warranted,
                    suppression_class=suppression_class,
                    observed_at=NOW,
                )

        with self.assertRaises(ValueError):
            GateDecision(
                state="changed",
                reading_warranted=True,
                suppression_class=None,
                observed_at=NOW,
                schema_version="vision_exact_repeat_gate.v2",
            )

    def test_prior_advancement_symbol_is_public(self):
        self.assertTrue(callable(evaluate))
        self.assertTrue(callable(advance_prior))


class EvaluationTests(unittest.TestCase):
    DIGESTS = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)

    def tokens(self, **changes: object) -> ChangeTokens:
        values: dict[str, object] = {
            "active_crop_sha256": self.DIGESTS[0],
            "atspi_projection_sha256": self.DIGESTS[1],
            "geometry_sha256": self.DIGESTS[2],
            "focus_capture_sha256": self.DIGESTS[3],
            "comparison_mode": "full",
            "degraded_reason": None,
        }
        values.update(changes)
        return ChangeTokens(**values)

    def envelope(self, tokens: object) -> CurrentEnvelope:
        return CurrentEnvelope(state="available", tokens=tokens)

    def test_no_prior_is_changed_first_observation_with_current_candidate(self):
        tokens = self.tokens()

        decision = evaluate(self.envelope(tokens), None, observed_at=NOW)

        self.assertEqual(decision.state, "changed")
        self.assertTrue(decision.reading_warranted)
        self.assertIsNone(decision.suppression_class)
        self.assertEqual(decision.observed_at, NOW)
        self.assertEqual(decision.reason, "first_observation")
        self.assertEqual(decision.comparison_mode, "full")
        self.assertEqual(decision.changed_dimensions, ("first_observation",))
        self.assertEqual(decision.candidate_prior, GatePrior(tokens=tokens))
        self.assertEqual(decision.prior_disposition, "absent")

    def test_exact_repeat_is_economy_unchanged_without_candidate(self):
        tokens = self.tokens()

        decision = evaluate(self.envelope(tokens), GatePrior(tokens=tokens), observed_at=NOW)

        self.assertEqual(decision.state, "unchanged")
        self.assertFalse(decision.reading_warranted)
        self.assertEqual(decision.suppression_class, "economy")
        self.assertEqual(decision.reason, "exact_repeat")
        self.assertEqual(decision.comparison_mode, "full")
        self.assertEqual(decision.changed_dimensions, ())
        self.assertIsNone(decision.candidate_prior)
        self.assertEqual(decision.prior_disposition, "valid")

    def test_each_single_axis_delta_is_reported_in_canonical_order(self):
        prior_tokens = self.tokens()
        changes = {
            "active_crop_sha256": "e" * 64,
            "atspi_projection_sha256": "e" * 64,
            "geometry_sha256": "e" * 64,
            "focus_capture_sha256": "e" * 64,
        }
        for dimension, value in changes.items():
            with self.subTest(dimension=dimension):
                current_tokens = self.tokens(**{dimension: value})
                decision = evaluate(
                    self.envelope(current_tokens),
                    GatePrior(tokens=prior_tokens),
                    observed_at=NOW,
                )
                self.assertEqual(decision.state, "changed")
                self.assertEqual(decision.reason, "signal_delta")
                self.assertEqual(decision.changed_dimensions, (dimension,))
                self.assertEqual(decision.candidate_prior, GatePrior(tokens=current_tokens))
                self.assertEqual(decision.prior_disposition, "valid")

    def test_full_and_crop_only_transitions_change_mode_and_atspi_availability(self):
        full = self.tokens()
        crop_only = self.tokens(
            comparison_mode="crop_only",
            atspi_projection_sha256=None,
            degraded_reason="atspi_unreachable",
        )
        for current, prior in ((crop_only, full), (full, crop_only)):
            with self.subTest(current_mode=current.comparison_mode):
                decision = evaluate(
                    self.envelope(current), GatePrior(tokens=prior), observed_at=NOW
                )
                self.assertEqual(decision.state, "changed")
                self.assertEqual(
                    decision.changed_dimensions,
                    ("atspi_projection_sha256", "comparison_mode"),
                )
                self.assertEqual(decision.comparison_mode, current.comparison_mode)

    def test_identical_crop_only_tokens_repeat_for_every_closed_soft_reason(self):
        for reason in SOFT_ATSPI_REASONS:
            with self.subTest(reason=reason):
                tokens = self.tokens(
                    comparison_mode="crop_only",
                    atspi_projection_sha256=None,
                    degraded_reason=reason,
                )
                decision = evaluate(
                    self.envelope(tokens), GatePrior(tokens=tokens), observed_at=NOW
                )
                self.assertEqual(decision.state, "unchanged")
                self.assertEqual(decision.comparison_mode, "crop_only")
                self.assertEqual(decision.changed_dimensions, ())

    def test_malformed_current_tokens_fail_open_as_digest_unavailable(self):
        prior = GatePrior(tokens=self.tokens())
        malformed_values = (None, {}, object())
        for malformed in malformed_values:
            with self.subTest(kind=type(malformed).__name__):
                decision = evaluate(self.envelope(malformed), prior, observed_at=NOW)
                self.assertEqual(decision.state, "unavailable")
                self.assertTrue(decision.reading_warranted)
                self.assertIsNone(decision.suppression_class)
                self.assertEqual(decision.reason, "digest_unavailable")
                self.assertIsNone(decision.candidate_prior)

    def test_corrupted_digest_payloads_fail_open_as_digest_unavailable(self):
        corruptions = (
            ("active_crop_sha256", "A" * 64),
            ("geometry_sha256", "a" * 63),
            ("focus_capture_sha256", 7),
        )
        for field_name, invalid_value in corruptions:
            with self.subTest(field_name=field_name):
                corrupted = self.tokens()
                object.__setattr__(corrupted, field_name, invalid_value)

                decision = evaluate(self.envelope(corrupted), None, observed_at=NOW)

                self.assertEqual(decision.state, "unavailable")
                self.assertTrue(decision.reading_warranted)
                self.assertIsNone(decision.suppression_class)
                self.assertEqual(decision.reason, "digest_unavailable")
                self.assertIsNone(decision.candidate_prior)

    def test_invalid_prior_fails_open_with_valid_current_candidate(self):
        current = self.tokens()
        for prior in ({}, object()):
            with self.subTest(kind=type(prior).__name__):
                decision = evaluate(self.envelope(current), prior, observed_at=NOW)
                self.assertEqual(decision.state, "unavailable")
                self.assertEqual(decision.reason, "prior_unavailable")
                self.assertEqual(decision.candidate_prior, GatePrior(tokens=current))
                self.assertEqual(decision.prior_disposition, "unavailable")

    def test_wrong_version_prior_fails_open_with_valid_current_candidate(self):
        current = self.tokens()
        prior = GatePrior(tokens=current, schema_version="vision_exact_repeat_prior.v0")

        decision = evaluate(self.envelope(current), prior, observed_at=NOW)

        self.assertEqual(decision.state, "unavailable")
        self.assertEqual(decision.reason, "prior_schema_incompatible")
        self.assertEqual(decision.candidate_prior, GatePrior(tokens=current))
        self.assertEqual(decision.prior_disposition, "incompatible")

    def test_missing_or_invalid_timestamp_is_honestly_unavailable(self):
        current = self.envelope(self.tokens())
        invalid_times = (None, "2026-07-11T18:00:00Z", datetime(2026, 7, 11, 18, 0))
        for invalid_time in invalid_times:
            with self.subTest(value=invalid_time):
                decision = evaluate(current, None, observed_at=invalid_time)
                self.assertEqual(decision.state, "unavailable")
                self.assertTrue(decision.reading_warranted)
                self.assertEqual(decision.reason, "timestamp_unavailable")
                self.assertIsNone(decision.observed_at)
                self.assertIsNone(decision.candidate_prior)

        omitted = evaluate(current, None)
        self.assertEqual(omitted.reason, "timestamp_unavailable")
        self.assertIsNone(omitted.observed_at)

    def test_timestamp_failure_contains_timezone_errors_and_classifies_prior(self):
        current = self.envelope(self.tokens())
        valid_prior = GatePrior(tokens=self.tokens())
        incompatible_prior = GatePrior(
            tokens=self.tokens(), schema_version="vision_exact_repeat_prior.v0"
        )
        priors = (
            (None, "absent"),
            (valid_prior, "valid"),
            (incompatible_prior, "incompatible"),
            ({}, "unavailable"),
        )
        invalid_times = (
            None,
            datetime(2026, 7, 11, 18, 0, tzinfo=RaisingTimezone()),
        )
        for invalid_time in invalid_times:
            for prior, expected_disposition in priors:
                with self.subTest(
                    time_kind=type(invalid_time).__name__,
                    prior_disposition=expected_disposition,
                ):
                    decision = evaluate(current, prior, observed_at=invalid_time)
                    self.assertEqual(decision.state, "unavailable")
                    self.assertEqual(decision.reason, "timestamp_unavailable")
                    self.assertIsNone(decision.observed_at)
                    self.assertIsNone(decision.candidate_prior)
                    self.assertEqual(decision.prior_disposition, expected_disposition)

    def test_only_timestamp_unavailable_may_have_no_observed_at(self):
        invalid_cases = (
            {"state": "changed", "reason": "", "observed_at": None},
            {
                "state": "unavailable",
                "reason": "digest_unavailable",
                "observed_at": None,
            },
            {
                "state": "changed",
                "reason": "timestamp_unavailable",
                "observed_at": None,
            },
        )
        for values in invalid_cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                GateDecision(
                    reading_warranted=True,
                    suppression_class=None,
                    **values,
                )

    def test_domain_swap_does_not_change_comparison_policy(self):
        first_prior = self.tokens()
        first_current = self.tokens(active_crop_sha256="e" * 64)
        second_prior = self.tokens(
            active_crop_sha256="1" * 64,
            atspi_projection_sha256="2" * 64,
            geometry_sha256="3" * 64,
            focus_capture_sha256="4" * 64,
        )
        second_current = self.tokens(
            active_crop_sha256="5" * 64,
            atspi_projection_sha256="2" * 64,
            geometry_sha256="3" * 64,
            focus_capture_sha256="4" * 64,
        )

        decisions = (
            evaluate(
                self.envelope(first_current),
                GatePrior(tokens=first_prior),
                observed_at=NOW,
            ),
            evaluate(
                self.envelope(second_current),
                GatePrior(tokens=second_prior),
                observed_at=NOW,
            ),
        )
        policy_fields = (
            "state",
            "reading_warranted",
            "suppression_class",
            "reason",
            "comparison_mode",
            "changed_dimensions",
            "prior_disposition",
        )
        self.assertEqual(
            tuple(getattr(decisions[0], field) for field in policy_fields),
            tuple(getattr(decisions[1], field) for field in policy_fields),
        )

    def test_evaluate_does_not_mutate_inputs(self):
        current_tokens = self.tokens(active_crop_sha256="e" * 64)
        prior_tokens = self.tokens()
        current = self.envelope(current_tokens)
        prior = GatePrior(tokens=prior_tokens)
        before = (current, prior, current_tokens, prior_tokens)

        evaluate(current, prior, observed_at=NOW)

        self.assertEqual((current, prior, current_tokens, prior_tokens), before)


class RefusalAndPriorTests(unittest.TestCase):
    DIGESTS = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)

    def tokens(self, **changes: object) -> ChangeTokens:
        values: dict[str, object] = {
            "active_crop_sha256": self.DIGESTS[0],
            "atspi_projection_sha256": self.DIGESTS[1],
            "geometry_sha256": self.DIGESTS[2],
            "focus_capture_sha256": self.DIGESTS[3],
            "comparison_mode": "full",
            "degraded_reason": None,
        }
        values.update(changes)
        return ChangeTokens(**values)

    def envelope(self, tokens: object) -> CurrentEnvelope:
        return CurrentEnvelope(state="available", tokens=tokens)

    def blocked(
        self,
        *,
        lane: str,
        schema: str,
        reason: str,
        state: str,
        tokens: object = None,
    ) -> CurrentEnvelope:
        return CurrentEnvelope(
            state=state,
            tokens=tokens,
            reason=reason,
            source_lane=lane,
            source_schema_version=schema,
        )

    def test_all_slice4_and_slice5_blocked_reasons_propagate_exactly(self):
        slice4_excluded = atspi_sensor.SLICE4_REFUSAL_REASONS & atspi_sensor.EXCLUDED_REASONS
        lanes = (
            (
                "slice4",
                "active_window_geometry.v2",
                atspi_sensor.SLICE4_REFUSAL_REASONS,
                slice4_excluded,
            ),
            (
                "slice5",
                "atspi_accessibility.v1",
                atspi_sensor.REFUSAL_REASONS,
                atspi_sensor.EXCLUDED_REASONS,
            ),
        )
        prior = GatePrior(tokens=self.tokens())

        for lane, schema, reasons, excluded_reasons in lanes:
            for reason in reasons:
                state = "excluded" if reason in excluded_reasons else "refused"
                with self.subTest(lane=lane, reason=reason, state=state):
                    decision = evaluate(
                        self.blocked(
                            lane=lane,
                            schema=schema,
                            reason=reason,
                            state=state,
                        ),
                        prior,
                        observed_at=NOW,
                    )
                    self.assertEqual(decision.state, state)
                    self.assertEqual(decision.reason, reason)
                    self.assertEqual(decision.upstream_lane, lane)
                    self.assertEqual(decision.upstream_schema_version, schema)
                    self.assertFalse(decision.reading_warranted)
                    self.assertEqual(
                        decision.suppression_class,
                        "privacy" if state == "excluded" else "no_authority",
                    )
                    self.assertIsNone(decision.comparison_mode)
                    self.assertEqual(decision.changed_dimensions, ())
                    self.assertIsNone(decision.candidate_prior)
                    self.assertEqual(decision.prior_disposition, "valid")

    def test_malformed_blocked_envelopes_fail_open_as_current_protocol_invalid(self):
        malformed = (
            self.blocked(
                lane="slice6",
                schema="atspi_accessibility.v1",
                reason="atspi_unreachable",
                state="refused",
            ),
            self.blocked(
                lane="slice4",
                schema="active_window_geometry.v1",
                reason="paused",
                state="refused",
            ),
            self.blocked(
                lane="slice5",
                schema="atspi_accessibility.v2",
                reason="atspi_unreachable",
                state="refused",
            ),
            self.blocked(
                lane="slice4",
                schema="active_window_geometry.v2",
                reason="atspi_unreachable",
                state="refused",
            ),
            self.blocked(
                lane="slice5",
                schema="atspi_accessibility.v1",
                reason="invented_reason",
                state="refused",
            ),
            self.blocked(
                lane="slice4",
                schema="active_window_geometry.v2",
                reason="sensitive_window",
                state="refused",
            ),
            self.blocked(
                lane="slice5",
                schema="atspi_accessibility.v1",
                reason="atspi_unreachable",
                state="excluded",
            ),
            self.blocked(
                lane="slice5",
                schema="atspi_accessibility.v1",
                reason="excluded_path",
                state="excluded",
                tokens=self.tokens(),
            ),
        )

        for current in malformed:
            with self.subTest(current=current):
                decision = evaluate(current, None, observed_at=NOW)
                self.assertEqual(decision.state, "unavailable")
                self.assertTrue(decision.reading_warranted)
                self.assertIsNone(decision.suppression_class)
                self.assertEqual(decision.reason, "current_protocol_invalid")
                self.assertIsNone(decision.candidate_prior)

    def test_blocked_protocol_precedes_token_validation(self):
        blocked_with_invalid_tokens = self.blocked(
            lane="slice5",
            schema="atspi_accessibility.v1",
            reason="excluded_path",
            state="excluded",
            tokens=object(),
        )

        decision = evaluate(blocked_with_invalid_tokens, None, observed_at=NOW)

        self.assertEqual(decision.reason, "current_protocol_invalid")
        self.assertNotEqual(decision.reason, "digest_unavailable")

    def test_available_envelope_forbids_blocked_only_metadata_before_comparison(self):
        tokens = self.tokens()
        prior = GatePrior(tokens=tokens)
        poisoned_metadata = (
            {"reason": "atspi_unreachable"},
            {"source_lane": "slice5"},
            {"source_schema_version": "atspi_accessibility.v1"},
            {
                "reason": "atspi_unreachable",
                "source_lane": "slice5",
                "source_schema_version": "atspi_accessibility.v1",
            },
        )

        for metadata in poisoned_metadata:
            with self.subTest(metadata=metadata):
                decision = evaluate(
                    CurrentEnvelope(state="available", tokens=tokens, **metadata),
                    prior,
                    observed_at=NOW,
                )
                self.assertEqual(decision.state, "unavailable")
                self.assertTrue(decision.reading_warranted)
                self.assertIsNone(decision.suppression_class)
                self.assertEqual(decision.reason, "current_protocol_invalid")
                self.assertNotEqual(decision.state, "unchanged")
                self.assertNotEqual(decision.suppression_class, "economy")
                self.assertIsNone(decision.candidate_prior)

    def test_real_signal_change_uses_design_reason(self):
        prior = GatePrior(tokens=self.tokens())
        current = self.tokens(active_crop_sha256="e" * 64)

        decision = evaluate(self.envelope(current), prior, observed_at=NOW)

        self.assertEqual(decision.state, "changed")
        self.assertEqual(decision.reason, "signal_delta")

    def test_failed_refused_or_excluded_downstream_does_not_poison_stillness(self):
        prior_a = GatePrior(tokens=self.tokens())
        tokens_b = self.tokens(active_crop_sha256="e" * 64)

        for downstream_label in ("failed", "refused", "excluded"):
            with self.subTest(downstream_label=downstream_label):
                first = evaluate(self.envelope(tokens_b), prior_a, observed_at=NOW)
                after_failure = advance_prior(prior_a, first, downstream_succeeded=False)
                second = evaluate(
                    self.envelope(tokens_b),
                    after_failure,
                    observed_at=NOW + timedelta(seconds=1),
                )
                self.assertEqual(first.state, "changed")
                self.assertEqual(first.reason, "signal_delta")
                self.assertEqual(after_failure, prior_a)
                self.assertEqual(second.state, "changed")
                self.assertEqual(second.reason, "signal_delta")

    def test_only_exact_success_commits_candidate_and_other_decisions_retain_prior(self):
        prior_a = GatePrior(tokens=self.tokens())
        tokens_b = self.tokens(active_crop_sha256="e" * 64)
        changed = evaluate(self.envelope(tokens_b), prior_a, observed_at=NOW)
        unchanged = evaluate(self.envelope(prior_a.tokens), prior_a, observed_at=NOW)

        self.assertEqual(
            advance_prior(prior_a, changed, downstream_succeeded=True),
            GatePrior(tokens=tokens_b),
        )
        self.assertEqual(advance_prior(prior_a, unchanged, downstream_succeeded=True), prior_a)

    def test_upstream_block_invalidates_prior_and_next_valid_sample_is_first(self):
        prior_a = GatePrior(tokens=self.tokens())
        tokens_b = self.tokens(active_crop_sha256="e" * 64)
        blocks = (
            self.blocked(
                lane="slice4",
                schema="active_window_geometry.v2",
                reason="sensitive_window",
                state="excluded",
            ),
            self.blocked(
                lane="slice5",
                schema="atspi_accessibility.v1",
                reason="atspi_unreachable",
                state="refused",
            ),
        )

        for current in blocks:
            with self.subTest(state=current.state):
                blocked_decision = evaluate(current, prior_a, observed_at=NOW)
                cleared = advance_prior(prior_a, blocked_decision, downstream_succeeded=False)
                next_decision = evaluate(
                    self.envelope(tokens_b),
                    cleared,
                    observed_at=NOW + timedelta(seconds=1),
                )
                self.assertIsNone(cleared)
                self.assertEqual(next_decision.state, "changed")
                self.assertEqual(next_decision.reason, "first_observation")
                self.assertEqual(next_decision.prior_disposition, "absent")

    def test_advance_prior_rejects_non_contract_inputs(self):
        prior = GatePrior(tokens=self.tokens())
        decision = evaluate(self.envelope(prior.tokens), prior, observed_at=NOW)
        invalid_calls = (
            ({}, decision, False),
            (prior, object(), False),
            (prior, decision, 1),
            (prior, decision, None),
            (prior, decision, "true"),
        )

        for previous, candidate_decision, downstream_succeeded in invalid_calls:
            with (
                self.subTest(
                    previous=type(previous).__name__,
                    decision=type(candidate_decision).__name__,
                    downstream_succeeded=downstream_succeeded,
                ),
                self.assertRaises(ValueError),
            ):
                advance_prior(
                    previous,
                    candidate_decision,
                    downstream_succeeded=downstream_succeeded,
                )


class ReceiptAndContainmentTests(unittest.TestCase):
    RECEIPT_KEYS = {
        "schema_version",
        "state",
        "timestamp",
        "reading_warranted",
        "suppression_class",
        "comparison_mode",
        "degraded",
        "changed_dimensions",
        "compared_dimension_count",
        "reason",
        "upstream_lane",
        "upstream_schema_version",
        "prior_disposition",
    }
    DIGESTS = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)

    def tokens(self, **changes: object) -> ChangeTokens:
        values: dict[str, object] = {
            "active_crop_sha256": self.DIGESTS[0],
            "atspi_projection_sha256": self.DIGESTS[1],
            "geometry_sha256": self.DIGESTS[2],
            "focus_capture_sha256": self.DIGESTS[3],
            "comparison_mode": "full",
            "degraded_reason": None,
        }
        values.update(changes)
        return ChangeTokens(**values)

    def decision(
        self,
        *,
        observed_at: datetime = NOW,
        tokens: ChangeTokens | None = None,
    ) -> GateDecision:
        current = tokens or self.tokens()
        return evaluate(
            CurrentEnvelope(state="available", tokens=current), None, observed_at=observed_at
        )

    def test_receipt_pins_exact_public_projection_for_full_comparison(self):
        receipt = self.decision().to_receipt()

        self.assertEqual(set(receipt), self.RECEIPT_KEYS)
        self.assertEqual(
            receipt,
            {
                "schema_version": "vision_exact_repeat_gate.v1",
                "state": "changed",
                "timestamp": "2026-07-11T18:00:00+00:00",
                "reading_warranted": True,
                "suppression_class": None,
                "comparison_mode": "full",
                "degraded": False,
                "changed_dimensions": ["first_observation"],
                "compared_dimension_count": 5,
                "reason": "first_observation",
                "upstream_lane": "",
                "upstream_schema_version": "",
                "prior_disposition": "absent",
            },
        )

    def test_receipt_normalizes_timestamp_and_only_timestamp_unavailable_uses_null(self):
        offset_time = datetime(
            2026,
            7,
            11,
            13,
            0,
            tzinfo=timezone(timedelta(hours=-5)),
        )
        self.assertEqual(
            self.decision(observed_at=offset_time).to_receipt()["timestamp"],
            "2026-07-11T18:00:00+00:00",
        )

        unavailable = evaluate(
            CurrentEnvelope(state="available", tokens=self.tokens()),
            None,
            observed_at=None,
        )
        receipt = unavailable.to_receipt()
        self.assertEqual(receipt["reason"], "timestamp_unavailable")
        self.assertIsNone(receipt["timestamp"])
        self.assertIsNone(receipt["comparison_mode"])
        self.assertFalse(receipt["degraded"])
        self.assertEqual(receipt["compared_dimension_count"], 0)

    def test_receipt_counts_full_crop_only_and_non_comparison_dimensions(self):
        crop_only = self.tokens(
            comparison_mode="crop_only",
            atspi_projection_sha256=None,
            degraded_reason="atspi_unreachable",
        )
        cases = (
            (self.decision(), False, 5),
            (self.decision(tokens=crop_only), True, 4),
            (
                evaluate(
                    CurrentEnvelope(
                        state="excluded",
                        reason="excluded_path",
                        source_lane="slice5",
                        source_schema_version="atspi_accessibility.v1",
                    ),
                    None,
                    observed_at=NOW,
                ),
                False,
                0,
            ),
        )
        for decision, degraded, dimension_count in cases:
            with self.subTest(state=decision.state, mode=decision.comparison_mode):
                receipt = decision.to_receipt()
                self.assertEqual(set(receipt), self.RECEIPT_KEYS)
                self.assertIs(receipt["degraded"], degraded)
                self.assertEqual(receipt["compared_dimension_count"], dimension_count)

    def test_receipt_excludes_private_tokens_candidates_literals_and_event_fields(self):
        receipt = self.decision().to_receipt()
        serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))

        for digest in self.DIGESTS:
            self.assertNotIn(digest, serialized)
        for forbidden in (
            "tokens",
            "candidate_prior",
            "private literal",
            "narration",
            "heartbeat",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_receipt_semantics_ignore_explicit_time_and_same_time_json_is_identical(self):
        first = self.decision(observed_at=NOW).to_receipt()
        second = self.decision(observed_at=NOW + timedelta(hours=7)).to_receipt()
        first_semantics = {key: value for key, value in first.items() if key != "timestamp"}
        second_semantics = {key: value for key, value in second.items() if key != "timestamp"}
        self.assertEqual(first_semantics, second_semantics)

        left = json.dumps(
            self.decision(observed_at=NOW).to_receipt(),
            sort_keys=True,
            separators=(",", ":"),
        )
        right = json.dumps(
            self.decision(observed_at=NOW).to_receipt(),
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(left, right)

    def test_gate_module_has_no_forbidden_import_or_action_surface(self):
        module_path = Path(__file__).resolve().parents[1] / "core/body/exact_repeat_gate.py"
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertEqual(forbidden_gate_imports(source), [])

        forbidden_calls = {
            "open",
            "write",
            "write_text",
            "write_bytes",
            "touch",
            "mkdir",
            "unlink",
            "remove",
            "rename",
            "replace",
            "run",
            "popen",
            "system",
            "socket",
            "urlopen",
            "request",
            "getenv",
            "capture",
            "screenshot",
            "ocr",
            "vlm",
            "route",
            "dispatch",
            "publish",
            "emit",
            "act",
            "admit",
            "admission",
            "wire",
            "wiring",
            "runtime",
        }
        called_names = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id.lower())
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr.lower())
        self.assertTrue(called_names.isdisjoint(forbidden_calls))
        forbidden_surface_names = {
            "filesystem",
            "network",
            "subprocess",
            "service",
            "capture",
            "reader",
            "ocr",
            "vlm",
            "daemon",
            "cognition",
            "prompt",
            "memory",
            "routing",
            "action",
            "flag",
            "admit",
            "admission",
            "wire",
            "wiring",
            "runtime",
        }
        identifiers = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
        identifiers.update(
            node.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        )
        self.assertTrue(identifiers.isdisjoint(forbidden_surface_names))
        self.assertEqual(forbidden_atspi_calls(source), [])
        self.assertNotIn("MAEZ_SCREEN_PERCEPTION", source)

    def test_import_checker_rejects_parent_package_admission_imports(self):
        synthetic_sources = (
            "from core.body import admission\n",
            "from core.body import daemon\n",
        )
        for source in synthetic_sources:
            with self.subTest(source=source):
                self.assertEqual(forbidden_gate_imports(source), ["core.body"])

    def test_import_checker_rejects_direct_atspi_function_imports(self):
        allowed_constants = (
            "EXCLUDED_REASONS",
            "REFUSAL_REASONS",
            "SCHEMA_VERSION",
            "SLICE4_REFUSAL_REASONS",
            "SLICE4_SCHEMA_VERSION",
        )
        for constant_name in allowed_constants:
            with self.subTest(constant_name=constant_name):
                self.assertEqual(
                    forbidden_gate_imports(f"from core.body.atspi_sensor import {constant_name}\n"),
                    [],
                )

        function_names = (
            "read_atspi_packet",
            "sample",
            "accessibility_projection_sha256",
        )
        for function_name in function_names:
            source = f"from core.body.atspi_sensor import {function_name}\n{function_name}()\n"
            with self.subTest(function_name=function_name):
                self.assertEqual(
                    forbidden_gate_imports(source),
                    [f"core.body.atspi_sensor.{function_name}"],
                )

    def test_gate_module_has_no_mutable_globals(self):
        module_path = Path(__file__).resolve().parents[1] / "core/body/exact_repeat_gate.py"
        self.assertEqual(mutable_global_lines(module_path.read_text(encoding="utf-8")), [])

        runtime_violations = []
        mutable_runtime_types = (
            collections.abc.MutableMapping,
            collections.abc.MutableSequence,
            collections.abc.MutableSet,
            bytearray,
        )
        for name, value in vars(exact_repeat_gate).items():
            if name.startswith("_") or inspect.ismodule(value) or inspect.isroutine(value):
                continue
            if isinstance(value, type) or isinstance(value, types.MappingProxyType):
                continue
            if isinstance(value, mutable_runtime_types):
                runtime_violations.append(name)
        self.assertEqual(runtime_violations, [])

    def test_mutable_global_checker_rejects_qualified_and_unknown_constructors(self):
        synthetic_sources = (
            "VALUE = collections.deque()\n",
            "VALUE = custom.Factory()\n",
        )
        for source in synthetic_sources:
            with self.subTest(source=source):
                self.assertEqual(mutable_global_lines(source), [1])

    def test_atspi_constants_may_be_read_but_atspi_functions_may_not_be_called(self):
        self.assertEqual(
            forbidden_atspi_calls("atspi_sensor.read_atspi_packet()\n"),
            ["atspi_sensor.read_atspi_packet"],
        )

    def test_no_production_module_imports_the_dormant_gate(self):
        root = Path(__file__).resolve().parents[1]
        gate_path = root / "core/body/exact_repeat_gate.py"
        importers = []
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if path == gate_path or relative.parts[0] in {"tests", ".venv"}:
                continue
            if gate_import_references(path.read_text(encoding="utf-8")):
                importers.append(str(relative))
        self.assertEqual(importers, [])

    def test_caller_scanner_rejects_relative_aliased_and_dynamic_gate_imports(self):
        synthetic_sources = (
            "from .exact_repeat_gate import evaluate\n",
            "from . import exact_repeat_gate\n",
            "import core.body.exact_repeat_gate as gate\n",
            '__import__("core.body.exact_repeat_gate")\n',
            'importlib.import_module("core.body.exact_repeat_gate")\n',
            'import importlib as il\nil.import_module("core.body.exact_repeat_gate")\n',
            'import importlib\nimportlib.import_module("core.body.exact_repeat_gate")\n',
            ('from importlib import import_module as im\nim("core.body.exact_repeat_gate")\n'),
            ('from importlib import import_module\nimport_module("core.body.exact_repeat_gate")\n'),
        )
        for source in synthetic_sources:
            with self.subTest(source=source):
                self.assertTrue(gate_import_references(source))

    def test_evaluation_and_receipt_create_no_files_or_writer_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            previous_cwd = Path.cwd()
            try:
                os.chdir(temporary_root)
                with (
                    patch.object(builtins, "open") as open_mock,
                    patch.object(os, "open") as os_open_mock,
                    patch.object(os, "mkdir") as os_mkdir_mock,
                    patch.object(Path, "open") as path_open_mock,
                    patch.object(Path, "mkdir") as path_mkdir_mock,
                    patch.object(Path, "touch") as touch_mock,
                    patch.object(Path, "write_text") as write_text_mock,
                    patch.object(Path, "write_bytes") as write_bytes_mock,
                    patch.object(subprocess, "run") as subprocess_run_mock,
                    patch.object(subprocess, "Popen") as subprocess_popen_mock,
                ):
                    self.decision().to_receipt()
                for writer in (
                    open_mock,
                    os_open_mock,
                    os_mkdir_mock,
                    path_open_mock,
                    path_mkdir_mock,
                    touch_mock,
                    write_text_mock,
                    write_bytes_mock,
                    subprocess_run_mock,
                    subprocess_popen_mock,
                ):
                    self.assertEqual(writer.call_count, 0)
            finally:
                os.chdir(previous_cwd)
            self.assertEqual(list(temporary_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
