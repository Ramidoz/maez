import json
import tempfile
import unittest
from pathlib import Path


RAW_A = "123e4567-e89b-12d3-a456-426614174000"


class NarrativeCoverageTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.db = self.root / "lived_episodes.db"
        from core.memory.episodes import EpisodeStore
        from core.memory.narrative import NarrativeStore

        self.episodes = EpisodeStore(self.db)
        self.narrative = NarrativeStore(self.db)

    def tearDown(self):
        self._td.cleanup()

    def _episode(self, title: str) -> str:
        return self.episodes.add(
            title=title,
            summary=title,
            participants=("Maez",),
            source_memory_ids=[f"raw-{title}"],
            source_kind="raw_observation",
        )

    def _chapter(self, members: list[str]) -> str:
        return self.episodes.add(
            title="chapter",
            summary="chapter",
            participants=("Maez",),
            source_memory_ids=members,
            source_kind="thread_reflection",
        )

    def test_coverage_marks_episode_covered_only_by_active_chapter_strings(self):
        from core.memory.narrative import narrative_coverage

        covered = self._episode("covered")
        uncovered = self._episode("uncovered")
        chapter = self._chapter([covered])
        self.narrative.upsert_link(
            link_type="strings",
            from_episode_id=chapter,
            to_episode_id=covered,
            trust="derived",
            evidence_ids=[covered],
            detector_version="v0",
        )

        coverage = narrative_coverage(
            episode_store=self.episodes,
            narrative_store=self.narrative,
        )

        self.assertTrue(coverage[covered]["covered"])
        self.assertEqual(coverage[covered]["covering_chapters"], [chapter])
        self.assertFalse(coverage[uncovered]["covered"])
        self.assertEqual(coverage[uncovered]["covering_chapters"], [])
        self.assertNotIn(chapter, coverage, "chapter episodes do not need chapter coverage")

    def test_shadow_artifact_writes_only_the_artifact_file(self):
        from scripts.narrative_coverage_shadow import write_coverage_shadow_artifact

        covered = self._episode("covered")
        chapter = self._chapter([covered])
        self.narrative.upsert_link(
            link_type="strings",
            from_episode_id=chapter,
            to_episode_id=covered,
            trust="derived",
            evidence_ids=[covered],
            detector_version="v0",
        )
        before = {path.relative_to(self.root) for path in self.root.rglob("*") if path.is_file()}
        artifact = self.root / "proof" / "coverage.json"

        write_coverage_shadow_artifact(
            artifact,
            episode_store=self.episodes,
            narrative_store=self.narrative,
        )

        after = {path.relative_to(self.root) for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after - before, {Path("proof/coverage.json")})
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["candidates"][0]["episode_id"], covered)
        self.assertEqual(payload["candidates"][0]["covering_chapter"], chapter)

    def test_no_deweight_or_archive_api_exists_in_narrative_module(self):
        import core.memory.narrative as narrative

        for name in ("archive_covered", "deweight_covered", "cool_covered"):
            self.assertFalse(hasattr(narrative, name), name)


if __name__ == "__main__":
    unittest.main()
