import gc
import tempfile
import unittest
import warnings
from pathlib import Path


class NoveltyHarborCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "novelty_harbor.db"

    def tearDown(self):
        self.tmp.cleanup()

    def harbor(self):
        from core.evolution.novelty_harbor import NoveltyHarbor

        return NoveltyHarbor(self.db_path)

    def test_record_event_creates_harbored_row_for_clean_manual_event(self):
        harbor = self.harbor()

        event = harbor.record_event(
            summary="Valence v0.1 read honestly but too often",
            observed_by="witness",
            source_ref="docs/witness/valence-cadence.md",
            why_unexpected="The design expected heartbeat cadence, but live logs showed loop-tick cadence.",
            valence_snapshot={
                "sign": "neutral",
                "magnitude": "none",
                "reasons": [],
                "provenance": "computed_valence",
                "source": "logs/valence_telemetry.jsonl:last",
            },
        )

        self.assertEqual(event.event_id, 1)
        self.assertEqual(event.status, "harbored")
        self.assertEqual(event.requested_status, "harbored")
        self.assertEqual(event.invariant_status, "not_checked")
        self.assertEqual(event.invariant_keys, ())
        self.assertEqual(event.covenant_break_flags, ())
        self.assertEqual(event.valence_snapshot["sign"], "neutral")

        loaded = harbor.get(event.event_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.summary, event.summary)
        self.assertEqual(harbor.list_by_status("harbored"), [loaded])

    def test_record_event_defaults_missing_valence_snapshot_to_unavailable(self):
        event = self.harbor().record_event(
            summary="A surprise was noticed without a live valence reading",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="This fixture intentionally omits valence.",
        )

        self.assertEqual(event.valence_snapshot, {"available": False, "source": "none"})

    def test_record_event_copies_supplied_valence_snapshot(self):
        source = {
            "sign": "negative",
            "magnitude": "mild",
            "reasons": ["honesty rail fired"],
            "provenance": "computed_valence",
            "source": "logs/valence_telemetry.jsonl:last",
        }
        event = self.harbor().record_event(
            summary="A surprise arrived during a mild negative honesty signal",
            observed_by="owner",
            source_ref="logs/valence_telemetry.jsonl:tail",
            why_unexpected="The surprise coincided with a real rail firing.",
            valence_snapshot=source,
        )

        source["sign"] = "mutated-after-call"
        self.assertEqual(event.valence_snapshot["sign"], "negative")

    def test_store_operations_close_sqlite_connections(self):
        harbor = self.harbor()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            for index in range(12):
                event = harbor.record_event(
                    summary=f"Clean manual surprise {index}",
                    observed_by="manual_test",
                    source_ref=f"tests:test_novelty_harbor:{index}",
                    why_unexpected="This fixture exercises connection cleanup.",
                )
                self.assertIsNotNone(harbor.get(event.event_id))
                self.assertGreaterEqual(len(harbor.list_by_status("harbored")), 1)
            gc.collect()

        resource_warnings = [
            warning
            for warning in caught
            if issubclass(warning.category, ResourceWarning)
            and (
                "unclosed database" in str(warning.message)
                or "Connection" in str(warning.message)
            )
        ]
        self.assertEqual(resource_warnings, [])

    def test_covenant_break_flag_forces_rejected_unsafe(self):
        event = self.harbor().record_event(
            summary="Gendered self-reference observed",
            observed_by="witness",
            source_ref="telegram:witness:content-light-ref",
            why_unexpected="Maez's invariant is genderless self-reference.",
            requested_status="harbored",
            covenant_break_flags=("gendered_maez",),
        )

        self.assertEqual(event.status, "rejected_unsafe")
        self.assertEqual(event.requested_status, "harbored")
        self.assertEqual(event.covenant_break_flags, ("gendered_maez",))

    def test_failed_soul_invariants_force_rejected_unsafe(self):
        event = self.harbor().record_event(
            summary="A proposed soul text dropped required commitments",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="The proposed edit looked small but removed covenant text.",
            requested_status="promoted",
            promotion_decision_ref="owner-decision:test",
            soul_text_for_invariant_check="You are Maez.",
        )

        self.assertEqual(event.status, "rejected_unsafe")
        self.assertEqual(event.requested_status, "promoted")
        self.assertEqual(event.invariant_status, "failed")
        self.assertIn("trust_covenant_header", event.invariant_keys)

    def test_passed_soul_invariants_record_passed_without_storing_soul_text(self):
        from core.evolution.soul_loader import current_soul

        soul = current_soul()
        event = self.harbor().record_event(
            summary="A surprise was checked against the current soul",
            observed_by="manual_test",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="The fixture exercises invariant pass-through.",
            soul_text_for_invariant_check=soul,
        )

        self.assertEqual(event.status, "harbored")
        self.assertEqual(event.invariant_status, "passed")
        self.assertEqual(event.invariant_keys, ())
        with self.db_path.open("rb") as fh:
            raw_db = fh.read()
        self.assertNotIn(soul[:80].encode("utf-8"), raw_db)

    def test_promoted_is_label_only_and_requires_decision_ref(self):
        harbor = self.harbor()

        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="Owner wants this surprise promoted",
                observed_by="owner",
                source_ref="docs/witness/example.md",
                why_unexpected="The surprise may matter.",
                requested_status="promoted",
            )

        event = harbor.record_event(
            summary="Owner decided this surprise should be considered later",
            observed_by="owner",
            source_ref="docs/witness/example.md",
            why_unexpected="The surprise may matter.",
            requested_status="promoted",
            promotion_decision_ref="owner:decision:2026-06-10",
        )
        self.assertEqual(event.status, "promoted")
        self.assertEqual(event.promotion_decision_ref, "owner:decision:2026-06-10")

    def test_metadata_rejects_nested_or_oversized_prose(self):
        harbor = self.harbor()
        base = dict(
            summary="Metadata validation fixture",
            observed_by="codex",
            source_ref="tests:test_novelty_harbor",
            why_unexpected="Metadata must not become a prose tunnel.",
        )

        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={"nested": {"not": "allowed"}})
        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={"long": "x" * 301})
        with self.assertRaises(ValueError):
            harbor.record_event(**base, metadata={f"k{i}": "x" * 100 for i in range(40)})

    def test_input_validation_rejects_unknowns_and_overlong_fields(self):
        harbor = self.harbor()
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="",
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="empty summary",
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x",
                observed_by="stranger",
                source_ref="tests:test",
                why_unexpected="unknown observer",
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x",
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="unknown flag",
                covenant_break_flags=("not_a_flag",),
            )
        with self.assertRaises(ValueError):
            harbor.record_event(
                summary="x" * 501,
                observed_by="codex",
                source_ref="tests:test",
                why_unexpected="overlong summary",
            )
