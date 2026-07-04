import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from tests.test_narrative_detectors import RAW_ID


def _tables(path: Path) -> set[str]:
    with closing(sqlite3.connect(path)) as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


class EpisodeStoreNarrativeHookTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "lived_episodes.db"

    def tearDown(self):
        self._td.cleanup()

    def test_flag_off_adds_episode_without_narrative_tables(self):
        from core.memory.episodes import EpisodeStore

        with mock.patch.dict(os.environ, {"MAEZ_NARRATIVE_SPINE": "0"}, clear=False):
            store = EpisodeStore(str(self.db))
            store.add(
                title="old",
                summary="old",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )
            store.add(
                title="new",
                summary="new",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )

        self.assertNotIn("narrative_links", _tables(self.db))

    def test_flag_on_writes_links_through_store_seam(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore

        with mock.patch.dict(os.environ, {"MAEZ_NARRATIVE_SPINE": "1"}, clear=False):
            store = EpisodeStore(str(self.db))
            first = store.add(
                title="old",
                summary="old",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )
            second = store.add(
                title="new",
                summary="new",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )

        links = NarrativeStore(self.db).links_for(second)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["link_type"], "same_thread")
        self.assertEqual({links[0]["from_episode_id"], links[0]["to_episode_id"]}, {first, second})
        self.assertEqual(links[0]["trust"], "derived")

    def test_flag_gate_uses_house_strict_parser(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore

        with mock.patch.dict(os.environ, {"MAEZ_NARRATIVE_SPINE": "yes"}, clear=False):
            store = EpisodeStore(str(self.db))
            first = store.add(
                title="old",
                summary="old",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )
            second = store.add(
                title="new",
                summary="new",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )

        links = NarrativeStore(self.db).links_for(second)
        self.assertEqual(len(links), 1)
        self.assertEqual({links[0]["from_episode_id"], links[0]["to_episode_id"]}, {first, second})

    def test_hook_links_superseded_existing_episode_for_order_independence(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore

        with mock.patch.dict(os.environ, {"MAEZ_NARRATIVE_SPINE": "1"}, clear=False):
            store = EpisodeStore(str(self.db))
            first = store.add(
                title="old",
                summary="old",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )
            successor = store.add(
                title="successor",
                summary="successor",
                participants=["Maez"],
                source_memory_ids=["raw-successor"],
                source_kind="telegram_exchange",
            )
            store.supersede(first, reason="test supersession", superseded_by=successor)
            second = store.add(
                title="new",
                summary="new",
                participants=["Maez"],
                source_memory_ids=[RAW_ID],
                source_kind="telegram_exchange",
            )

        links = NarrativeStore(self.db).links_for(second)
        self.assertEqual(len(links), 1)
        self.assertEqual({links[0]["from_episode_id"], links[0]["to_episode_id"]}, {first, second})

    def test_hook_exception_cannot_break_episode_write(self):
        from core.memory.episodes import EpisodeStore

        def boom(_episode):
            raise RuntimeError("narrative unavailable")

        store = EpisodeStore(str(self.db), narrative_hook=boom)
        ep_id = store.add(
            title="still writes",
            summary="still writes",
            participants=["Maez"],
            source_memory_ids=["raw-1"],
            source_kind="reflection",
        )

        self.assertIsNotNone(store.get(ep_id))

    def test_callsite_inventory_guard_matches_plan(self):
        from scripts.validate.narrative_callsite_inventory import production_episode_add_calls

        calls = production_episode_add_calls(Path(__file__).resolve().parent.parent)
        self.assertEqual(
            calls,
            [
                "core/learning/scar_tissue.py:402",
                "core/memory/m1_lived_episode_promotion.py:752",
                "core/memory/reflection.py:263",
                "core/memory/reflection.py:332",
                "daemon/maez_daemon.py:8813",
                "scripts/memory_reflection/nightly_lived_memory.py:156",
                "scripts/scar_backfill_exhibits.py:168",
            ],
        )


if __name__ == "__main__":
    unittest.main()
