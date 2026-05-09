# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 4c.5c — cold recall activation substrate tests."""

from __future__ import annotations

import dataclasses
import io
import logging
import unittest
from contextlib import redirect_stdout
from typing import get_type_hints
from unittest.mock import patch

from core.memory.recall_projection import ProjectionCandidate


class ActivationDecisionContractTests(unittest.TestCase):
    def test_activation_decision_shape_is_exactly_three_plain_fields(self):
        from core.memory.recall_activation import ActivationDecision

        fields = dataclasses.fields(ActivationDecision)
        self.assertEqual(
            [(field.name, get_type_hints(ActivationDecision)[field.name]) for field in fields],
            [
                ("candidate_id", str),
                ("ordering_bump", int),
                ("recall_continuity_hint", str),
            ],
        )

    def test_activation_decision_rejects_rich_or_invalid_values(self):
        from core.memory.recall_activation import ActivationDecision

        with self.assertRaisesRegex(TypeError, "candidate_id"):
            ActivationDecision(
                candidate_id={"id": "candidate-1"},
                ordering_bump=1,
                recall_continuity_hint="same-thread",
            )
        with self.assertRaisesRegex(TypeError, "ordering_bump"):
            ActivationDecision(
                candidate_id="candidate-1",
                ordering_bump=True,
                recall_continuity_hint="same-thread",
            )
        with self.assertRaisesRegex(ValueError, "ordering_bump"):
            ActivationDecision(
                candidate_id="candidate-1",
                ordering_bump=2,
                recall_continuity_hint="same-thread",
            )
        with self.assertRaisesRegex(ValueError, "recall_continuity_hint"):
            ActivationDecision(
                candidate_id="candidate-1",
                ordering_bump=1,
                recall_continuity_hint="",
            )

    def test_activation_decision_serializes_without_extra_fields(self):
        from core.memory.recall_activation import ActivationDecision

        decision = ActivationDecision(
            candidate_id="candidate-1",
            ordering_bump=1,
            recall_continuity_hint="same-thread",
        )
        self.assertEqual(
            dataclasses.asdict(decision),
            {
                "candidate_id": "candidate-1",
                "ordering_bump": 1,
                "recall_continuity_hint": "same-thread",
            },
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            decision.ordering_bump = 0


class ProjectionActivationConfigTests(unittest.TestCase):
    def test_activation_decision_schema_version_is_module_level_only(self):
        from core.memory import recall_activation
        from core.memory.recall_activation import ActivationDecision

        self.assertEqual(recall_activation.ACTIVATION_DECISION_SCHEMA_VERSION, 1)
        self.assertNotIn(
            "schema_version",
            [field.name for field in dataclasses.fields(ActivationDecision)],
        )

    def test_positive_activation_env_var_is_default_false(self):
        from core.memory.recall_activation_config import (
            MAEZ_PROJECTION_ACTIVATION_ENABLED,
            projection_activation_enabled,
        )

        cases = [
            ({}, False),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: ""}, False),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "0"}, False),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "false"}, False),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "FALSE"}, False),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "maybe"}, False),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "1"}, True),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "true"}, True),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "yes"}, True),
            ({MAEZ_PROJECTION_ACTIVATION_ENABLED: "on"}, True),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                self.assertIs(projection_activation_enabled(env), expected)

    def test_startup_log_records_disabled_once_at_warning_level(self):
        from core.memory.recall_activation import LOGGER_NAME
        from core.memory.recall_activation_config import log_activation_startup_state

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger(LOGGER_NAME)
        old_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        try:
            with patch.dict("os.environ", {}, clear=True):
                log_activation_startup_state()
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)

        payload = stream.getvalue()
        self.assertIn("activation_state=disabled", payload)
        self.assertIn("level=warning", payload)
        self.assertIn("MAEZ_PROJECTION_ACTIVATION_ENABLED", payload)


class DecideActivationColdContractTests(unittest.TestCase):
    def test_decide_activation_is_cold_disabled_noop(self):
        from core.memory.recall_activation import decide_activation

        candidate = ProjectionCandidate(
            candidate_id="candidate-1",
            candidate_kind="self_history",
            text="raw memory text",
            source_ids=("turn-1",),
            continuity_key="same-thread",
            continuity_key_basis="source_metadata",
            timestamp=1.0,
            lifecycle_stage="gestation",
            trust_scope="owner_private",
        )

        with patch.dict("os.environ", {"MAEZ_PROJECTION_ACTIVATION_ENABLED": "1"}):
            self.assertIsNone(decide_activation([candidate]))

    def test_decide_activation_signature_uses_projection_candidate_iterable(self):
        from core.memory.recall_activation import decide_activation

        hints = get_type_hints(decide_activation)
        self.assertEqual(
            str(hints["candidates"]),
            "typing.Iterable[core.memory.recall_projection.ProjectionCandidate]",
        )
        self.assertEqual(
            str(hints["return"]),
            "typing.Optional[core.memory.recall_activation.ActivationDecision]",
        )


class RecallActivationDocsTests(unittest.TestCase):
    def test_rulebook_locks_activation_bounds_and_forbidden_shapes(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parent.parent
            / "docs"
            / "governance"
            / "MEMORY_PROJECTION_RULES.md"
        ).read_text(encoding="utf-8")
        self.assertIn("MAEZ_PROJECTION_ACTIVATION_ENABLED", text)
        self.assertIn("recall_continuity_hint", text)
        self.assertIn("owner-private only", text)
        self.assertIn("non-proactive only", text)
        self.assertIn("at most one activation decision per recall", text)
        self.assertIn("Forbidden Activation Shapes", text)
        self.assertIn("Any change to the three-field ActivationDecision lock requires an ADR", text)
        self.assertNotIn("continuity_marker", text)


if __name__ == "__main__":
    with redirect_stdout(None):
        unittest.main()
