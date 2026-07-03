import tempfile
import unittest
from pathlib import Path

from core.learning.scar_tissue import ScarSidecar
from core.memory.episodes import EpisodeStore


class ScarBackfillExhibitTests(unittest.TestCase):
    def _stores(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        self.addCleanup(td.cleanup)
        return (
            EpisodeStore(str(root / "episodes.db")),
            ScarSidecar(root / "scars.db"),
        )

    def test_default_exhibits_are_the_four_reviewed_keep_rows(self):
        from scripts.scar_backfill_exhibits import DEFAULT_EXHIBITS

        self.assertEqual(
            [f"{ex.tier}/{ex.row_id}" for ex in DEFAULT_EXHIBITS],
            [
                "daily/daily-2026-04-23-683a9a68",
                "daily/daily-2026-04-25-86e9538d",
                "daily/daily-2026-04-29-16ffa8d5",
                "core/core-1c54344acced",
            ],
        )

    def test_list_exhibits_prints_four_rows_and_mutates_nothing(self):
        from scripts.scar_backfill_exhibits import render_exhibit_list

        episodes, sidecar = self._stores()
        before = episodes.active_count_and_newest_time()

        rendered = render_exhibit_list()

        self.assertIn("daily/daily-2026-04-23-683a9a68", rendered)
        self.assertIn("core/core-1c54344acced", rendered)
        self.assertIn("would become scar episode", rendered)
        self.assertEqual(before, episodes.active_count_and_newest_time())
        self.assertIsNone(sidecar.active_episode("exhibit:core/core-1c54344acced"))

    def test_apply_owner_approved_creates_four_scar_episodes_and_archives_originals(self):
        from scripts.scar_backfill_exhibits import DEFAULT_EXHIBITS, apply_exhibit_backfill

        episodes, sidecar = self._stores()
        archived = []

        result = apply_exhibit_backfill(
            episode_store=episodes,
            sidecar=sidecar,
            owner_approved=True,
            archive_original=lambda ref: archived.append(f"{ref.tier}/{ref.row_id}"),
            now_iso="2026-07-02T12:00:00+00:00",
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(archived, [f"{ex.tier}/{ex.row_id}" for ex in DEFAULT_EXHIBITS])
        active = episodes.list_active()
        self.assertEqual(len(active), 4)
        for ex in DEFAULT_EXHIBITS:
            with self.subTest(exhibit=ex.row_ref):
                dedup = f"exhibit:{ex.row_ref}"
                episode_id = sidecar.active_episode(dedup)
                self.assertIsNotNone(episode_id)
                episode = episodes.get(episode_id)
                self.assertEqual(episode["source_kind"], "scar")
                self.assertEqual(episode["authorship"], "scar_detector")
                self.assertEqual(episode["memory_voice"], "external_to_maez")
                self.assertEqual(episode["source_memory_ids"], [dedup])
                self.assertIn("A3 curation", episode["summary"])
                self.assertIn(dedup, episode["summary"])

    def test_apply_requires_owner_approval(self):
        from scripts.scar_backfill_exhibits import apply_exhibit_backfill

        episodes, sidecar = self._stores()
        with self.assertRaises(PermissionError):
            apply_exhibit_backfill(
                episode_store=episodes,
                sidecar=sidecar,
                owner_approved=False,
                archive_original=lambda _ref: None,
            )
        self.assertEqual(episodes.active_count_and_newest_time()[0], 0)

    def test_apply_preflights_original_rows_before_writing_any_episode(self):
        from scripts.scar_backfill_exhibits import apply_exhibit_backfill

        episodes, sidecar = self._stores()
        archived = []

        def missing_original(_ref):
            raise KeyError("missing hot row")

        with self.assertRaises(KeyError):
            apply_exhibit_backfill(
                episode_store=episodes,
                sidecar=sidecar,
                owner_approved=True,
                require_original=missing_original,
                archive_original=lambda ref: archived.append(f"{ref.tier}/{ref.row_id}"),
            )

        self.assertEqual(episodes.active_count_and_newest_time()[0], 0)
        self.assertEqual(archived, [])

    def test_second_apply_refuses_before_duplication_or_archive(self):
        from scripts.scar_backfill_exhibits import apply_exhibit_backfill

        episodes, sidecar = self._stores()
        archived = []
        apply_exhibit_backfill(
            episode_store=episodes,
            sidecar=sidecar,
            owner_approved=True,
            archive_original=lambda ref: archived.append(f"{ref.tier}/{ref.row_id}"),
            now_iso="2026-07-02T12:00:00+00:00",
        )

        with self.assertRaises(RuntimeError):
            apply_exhibit_backfill(
                episode_store=episodes,
                sidecar=sidecar,
                owner_approved=True,
                archive_original=lambda ref: archived.append(f"second:{ref.tier}/{ref.row_id}"),
                now_iso="2026-07-02T12:00:01+00:00",
            )

        self.assertEqual(episodes.active_count_and_newest_time()[0], 4)
        self.assertFalse(any(item.startswith("second:") for item in archived))


if __name__ == "__main__":
    unittest.main()
