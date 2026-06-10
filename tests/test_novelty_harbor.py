import tempfile
import unittest
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
