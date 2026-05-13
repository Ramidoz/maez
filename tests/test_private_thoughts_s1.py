# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S1 private-thoughts producer + bounded-reader tests.

These tests pin the first post-scaffold shape:

- producers write through a minimal contextual-integrity envelope;
- raw private-thought content stays private;
- the bounded reader returns derived signals plus trace ids, not text.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sqlite3

from core.infra.private_thoughts import PrivateThoughts


class TestPrivateThoughtsS1(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.db_path = Path(self._td.name) / "private_thoughts.db"
        self.store = PrivateThoughts(db_path=self.db_path)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_record_signal_writes_contextual_integrity_envelope(self) -> None:
        thought_id = self.store.record_signal(
            content="The audit held a daemon thought for being too ungrounded.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader", "audit_trace"),
            context_extra={"cycle": 42},
            memory_phase="lived",
        )

        row = self.store.get_thought(thought_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["provenance"], "audit_held")
        self.assertEqual(row["memory_phase"], "lived")
        self.assertEqual(row["context"]["source"], "audit_rail")
        self.assertEqual(row["context"]["subject"], "maez_output")
        self.assertEqual(row["context"]["consent_tier"], "owner_private")
        self.assertEqual(row["context"]["retention"], "until_reviewed")
        self.assertEqual(
            row["context"]["allowed_flows"],
            ["private_reader", "audit_trace"],
        )
        self.assertEqual(row["context"]["extra"], {"cycle": 42})

    def test_record_signal_requires_contextual_integrity_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "source"):
            self.store.record_signal(
                content="A held concern with no source.",
                provenance="audit_held",
                source="",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader",),
            )

        with self.assertRaisesRegex(ValueError, "allowed_flows"):
            self.store.record_signal(
                content="A held concern with no allowed flow.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=(),
            )

    def test_record_thought_rejects_producer_provenance_bypass(self) -> None:
        with self.assertRaisesRegex(ValueError, "record_signal"):
            self.store.record_thought(
                content="Producer-shaped row with no envelope.",
                provenance="audit_held",
                context={},
            )

    def test_record_thought_internal_flag_cannot_bypass_signal_api(self) -> None:
        with self.assertRaises(TypeError):
            self.store.record_thought(
                content="Producer-shaped row with a fake internal flag.",
                provenance="audit_held",
                context={},
                _allow_producer_provenance=True,  # type: ignore[call-arg]
            )

    def test_record_signal_rejects_non_string_allowed_flows(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowed_flows"):
            self.store.record_signal(
                content="A held concern with a non-string flow.",
                provenance="audit_held",
                source="audit_rail",
                subject="maez_output",
                consent_tier="owner_private",
                retention="until_reviewed",
                allowed_flows=("private_reader", 123),  # type: ignore[list-item]
            )

    def test_bounded_reader_returns_signals_without_raw_content(self) -> None:
        crisis_id = self.store.record_signal(
            content="This looks like a crisis signal, but it must route to humans.",
            provenance="crisis_signal_held",
            source="telegram",
            subject="bonded_user_state",
            consent_tier="owner_private",
            retention="until_routed",
            allowed_flows=("private_reader", "crisis_channel"),
        )
        rupture_id = self.store.record_signal(
            content="A possible rupture is forming and should be repaired later.",
            provenance="rupture_unhealed",
            source="delayed_reflection",
            subject="bond_state",
            consent_tier="owner_private",
            retention="until_repaired",
            allowed_flows=("private_reader", "rupture_repair"),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertTrue(derived["bounded"])
        self.assertEqual(derived["limit"], 10)
        self.assertEqual(derived["counts"]["crisis_signal_held"], 1)
        self.assertEqual(derived["counts"]["rupture_unhealed"], 1)
        self.assertEqual(derived["signals"]["crisis_awareness"], "present")
        self.assertEqual(derived["signals"]["unhealed_rupture"], "present")
        self.assertEqual(
            derived["trace_ids"]["crisis_signal_held"],
            [crisis_id],
        )
        self.assertEqual(
            derived["trace_ids"]["rupture_unhealed"],
            [rupture_id],
        )
        self.assertNotIn("content", str(derived).lower())
        self.assertNotIn("route to humans", str(derived))

    def test_bounded_reader_does_not_call_raw_recent_reader(self) -> None:
        self.store.record_signal(
            content="Raw text should not be materialized by derived_signals.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        def _raw_reader_forbidden(*_args, **_kwargs):
            raise AssertionError("derived_signals must not materialize raw content")

        self.store.recent = _raw_reader_forbidden  # type: ignore[method-assign]

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(derived["counts"]["audit_held"], 1)
        self.assertEqual(derived["signals"]["audit_held_awareness"], "present")

    def test_bounded_reader_requires_private_reader_flow(self) -> None:
        hidden_id = self.store.record_signal(
            content="This row does not allow the private reader.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("audit_trace",),
        )
        visible_id = self.store.record_signal(
            content="This row allows the private reader.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(derived["counts"]["audit_held"], 1)
        self.assertEqual(derived["trace_ids"]["audit_held"], [visible_id])
        self.assertNotIn(hidden_id, derived["trace_ids"]["audit_held"])

    def test_bounded_reader_ignores_malformed_existing_producer_rows(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO private_thoughts "
                "(ts, content, provenance, context_json, memory_phase) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    1.0,
                    "Malformed row created outside the API.",
                    "audit_held",
                    "{}",
                    "gestation",
                ),
            )
            malformed_id = int(cur.lastrowid)

        visible_id = self.store.record_signal(
            content="Well-formed row created through the producer API.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(derived["counts"]["audit_held"], 1)
        self.assertEqual(derived["trace_ids"]["audit_held"], [visible_id])
        self.assertNotIn(malformed_id, derived["trace_ids"]["audit_held"])

    def test_bounded_reader_ignores_partially_malformed_context(self) -> None:
        bad_context = {
            "source": None,
            "subject": "",
            "consent_tier": "owner_private",
            "retention": "until_reviewed",
            "allowed_flows": ["private_reader", 123],
        }
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO private_thoughts "
                "(ts, content, provenance, context_json, memory_phase) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    1.0,
                    "Partially malformed row created outside the API.",
                    "audit_held",
                    json.dumps(bad_context),
                    "gestation",
                ),
            )
            malformed_id = int(cur.lastrowid)

        visible_id = self.store.record_signal(
            content="Well-formed row created through the producer API.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertEqual(derived["counts"]["audit_held"], 1)
        self.assertEqual(derived["trace_ids"]["audit_held"], [visible_id])
        self.assertNotIn(malformed_id, derived["trace_ids"]["audit_held"])

    def test_bounded_reader_ignores_unknown_provenance_rows(self) -> None:
        context = {
            "source": "foreign_writer",
            "subject": "maez_output",
            "consent_tier": "owner_private",
            "retention": "until_reviewed",
            "allowed_flows": ["private_reader"],
        }
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO private_thoughts "
                "(ts, content, provenance, context_json, memory_phase) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    1.0,
                    "Unknown provenance row created outside the API.",
                    "unknown_external",
                    json.dumps(context),
                    "gestation",
                ),
            )
            unknown_id = int(cur.lastrowid)

        visible_id = self.store.record_signal(
            content="Well-formed row created through the producer API.",
            provenance="audit_held",
            source="audit_rail",
            subject="maez_output",
            consent_tier="owner_private",
            retention="until_reviewed",
            allowed_flows=("private_reader",),
        )

        derived = self.store.derived_signals(limit=10)

        self.assertNotIn("unknown_external", derived["counts"])
        self.assertNotIn("unknown_external", derived["trace_ids"])
        self.assertEqual(derived["trace_ids"]["audit_held"], [visible_id])
        self.assertNotIn(unknown_id, derived["trace_ids"]["audit_held"])


if __name__ == "__main__":
    unittest.main()
