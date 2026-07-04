import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock


RAW_A = "123e4567-e89b-12d3-a456-426614174000"
RAW_B = "123e4567-e89b-12d3-a456-426614174001"


class NarrativeReaderTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "lived_episodes.db"
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore

        self.episodes = EpisodeStore(self.db)
        self.narrative = NarrativeStore(self.db)

    def tearDown(self):
        self._td.cleanup()

    def test_show_renders_evidence_and_trust_filter(self):
        from scripts.narrative_spine import render_show

        self.narrative.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=[RAW_A],
            detector_version="v0",
        )
        self.narrative.upsert_link(
            link_type="strings",
            from_episode_id="ep-a",
            to_episode_id="ep-c",
            trust="confirmed",
            evidence_ids=["proposal:nprop-1"],
            detector_version="weave:v0",
        )

        rendered = render_show(self.narrative, "ep-a", trust_filter="derived")

        self.assertIn("same_thread", rendered)
        self.assertIn("trust=derived", rendered)
        self.assertIn(RAW_A, rendered)
        self.assertNotIn("ep-c", rendered)

    def test_timeline_derives_follows_order_without_storing_follows(self):
        from scripts.narrative_spine import render_timeline

        ep_late = self.episodes.add(
            title="late",
            summary="late",
            participants=("Maez",),
            source_memory_ids=["raw-late"],
            source_kind="raw_observation",
            occurred_at="2026-07-03T12:00:00+00:00",
        )
        ep_early = self.episodes.add(
            title="early",
            summary="early",
            participants=("Maez",),
            source_memory_ids=["raw-early"],
            source_kind="raw_observation",
            occurred_at="2026-07-03T11:00:00+00:00",
        )

        rendered = render_timeline(self.episodes, [ep_late, ep_early])

        self.assertLess(rendered.index(ep_early), rendered.index(ep_late))
        with closing(sqlite3.connect(self.db)) as con:
            rows = con.execute("SELECT link_type FROM narrative_links").fetchall()
        self.assertNotIn(("follows",), rows)

    def test_recall_seam_flag_off_is_inert_even_if_store_factory_would_fail(self):
        from core.memory.narrative_readers import thread_neighbor_candidates

        def boom():
            raise AssertionError("flag-off recall seam must not open narrative store")

        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_RECALL": "0"}):
            self.assertEqual(
                thread_neighbor_candidates(
                    recalled_episode_ids=["ep-a"],
                    existing_candidate_ids={"ep-a"},
                    episode_store=self.episodes,
                    narrative_store_factory=boom,
                ),
                [],
            )

    def test_recall_seam_returns_thread_neighbors_without_rank_fields(self):
        from core.memory.narrative_readers import thread_neighbor_candidates

        ep_a = self.episodes.add(
            title="anchor",
            summary="anchor",
            participants=("Maez",),
            source_memory_ids=["raw-anchor"],
            source_kind="raw_observation",
        )
        ep_b = self.episodes.add(
            title="neighbor",
            summary="neighbor",
            participants=("Maez",),
            source_memory_ids=["raw-neighbor"],
            source_kind="raw_observation",
        )
        self.narrative.upsert_link(
            link_type="same_thread",
            from_episode_id=ep_a,
            to_episode_id=ep_b,
            trust="derived",
            evidence_ids=[RAW_B],
            detector_version="v0",
        )

        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_RECALL": "1"}):
            candidates = thread_neighbor_candidates(
                recalled_episode_ids=[ep_a],
                existing_candidate_ids={ep_a},
                episode_store=self.episodes,
                narrative_store_factory=lambda: self.narrative,
            )

        self.assertEqual([candidate["id"] for candidate in candidates], [ep_b])
        self.assertNotIn("score", candidates[0])
        self.assertNotIn("boost", candidates[0])

    def test_presence_seam_renders_content_light_open_threads_only_when_flagged(self):
        from core.memory.narrative_readers import format_open_threads_block

        self.narrative.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=[RAW_A],
            detector_version="v0",
        )

        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_PRESENCE": "0"}):
            self.assertEqual(format_open_threads_block(lambda: self.narrative), "")
        with mock.patch.dict("os.environ", {"MAEZ_NARRATIVE_PRESENCE": "1"}):
            block = format_open_threads_block(lambda: self.narrative)

        self.assertIn("OPEN NARRATIVE THREADS", block)
        self.assertIn("2 linked episodes", block)
        self.assertNotIn("anchor", block)
        self.assertNotIn("neighbor", block)

    def test_spine_script_runs_from_repo_root(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/narrative_spine.py",
                "--db",
                str(self.db),
                "threads",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No narrative threads", result.stdout)


if __name__ == "__main__":
    unittest.main()
