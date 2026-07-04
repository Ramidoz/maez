import tempfile
import unittest
from pathlib import Path
from unittest import mock


RAW_A = "123e4567-e89b-12d3-a456-426614174000"
RAW_B = "123e4567-e89b-12d3-a456-426614174001"


class _RecordingStore:
    def __init__(self):
        self.calls = []

    def add(self, **kwargs):
        self.calls.append(kwargs)
        return f"ep-recorded-{len(self.calls)}"


class NarrativeChapterTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "lived_episodes.db"

    def tearDown(self):
        self._td.cleanup()

    def test_thread_chapter_refuses_to_write_without_every_member_cited(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.reflection import Reflection, persist_thread_chapters

        store = EpisodeStore(self.db)

        with self.assertRaisesRegex(ValueError, "cite every thread member"):
            persist_thread_chapters(
                [Reflection("This thread has a shape.", ("ep-a", "ep-b"))],
                thread_member_ids=["ep-a", "ep-b", "ep-c"],
                episode_store=store,
            )

        self.assertEqual(store.list_active(), [])

    def test_thread_chapter_writes_as_thread_reflection_with_all_member_ids(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.reflection import Reflection, persist_thread_chapters

        store = EpisodeStore(self.db)

        ids = persist_thread_chapters(
            [Reflection("This thread has a shape.", ("ep-a", "ep-b", "ep-c"))],
            thread_member_ids=["ep-a", "ep-b", "ep-c"],
            episode_store=store,
        )

        self.assertEqual(len(ids), 1)
        row = store.get(ids[0])
        self.assertEqual(row["source_kind"], "thread_reflection")
        self.assertEqual(row["source_memory_ids"], ["ep-a", "ep-b", "ep-c"])
        self.assertEqual(row["authorship"], "thread_reflection_synthesis")

    def test_non_thread_reflection_persistence_is_unchanged_by_chapter_flag(self):
        from core.memory.reflection import Reflection, persist_reflections

        reflection = Reflection("A normal reflection.", ("core-1",))
        off_store = _RecordingStore()
        on_store = _RecordingStore()

        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_REFLECTION": "0"}):
            persist_reflections([reflection], episode_store=off_store)
        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_REFLECTION": "1"}):
            persist_reflections([reflection], episode_store=on_store)

        self.assertEqual(off_store.calls, on_store.calls)
        self.assertEqual(off_store.calls[0]["source_kind"], "reflection")

    def test_thread_chapter_produces_strings_edges_through_ordinary_episode_hook(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore
        from core.memory.reflection import Reflection, persist_thread_chapters

        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_SPINE": "1"}):
            store = EpisodeStore(self.db)
            chapter_ids = persist_thread_chapters(
                [Reflection("This thread has a shape.", ("ep-a", "ep-b"))],
                thread_member_ids=["ep-a", "ep-b"],
                episode_store=store,
            )

        links = NarrativeStore(self.db).links_for(chapter_ids[0])
        self.assertEqual([link["link_type"] for link in links], ["strings", "strings"])
        self.assertEqual(
            {link["to_episode_id"] for link in links},
            {"ep-a", "ep-b"},
        )

    def test_thread_selector_requires_min_members_and_skips_existing_chapters(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore
        from core.memory.reflection import select_threads_for_chapters

        narrative = NarrativeStore(self.db)
        narrative.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=[RAW_A],
            detector_version="v0",
        )
        narrative.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-b",
            to_episode_id="ep-c",
            trust="derived",
            evidence_ids=[RAW_B],
            detector_version="v0",
        )
        store = EpisodeStore(self.db)
        store.add(
            title="chapter",
            summary="chapter",
            participants=("Maez",),
            source_memory_ids=["ep-a", "ep-b", "ep-c"],
            source_kind="thread_reflection",
            importance=4,
        )

        self.assertEqual(
            select_threads_for_chapters(
                narrative_store=narrative,
                episode_store=store,
                min_members=3,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
