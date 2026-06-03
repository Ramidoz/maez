# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Entity-index deterministic backfill tests (Step 5f).

Walks the existing lived-memory EpisodeStore, runs the Step-5e
deterministic extractor over each episode's title + summary +
open_loop, and populates the Step-5e entity index. Read-only over
lived memory; only writes ``memory/entity_index.db``. No LLM, no
network, no subprocess.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


def _seed_episodes(td: Path) -> "tuple":
    """Seed an EpisodeStore with three episodes that exercise the
    interesting backfill paths: multi-word capitalized name in the
    title, place name in the summary, and an episode with no
    extractable entities at all (sparsity path)."""
    from core.memory.episodes import EpisodeStore

    ep = EpisodeStore(str(td / "lived_episodes.db"))
    e1 = ep.add(
        title="Maya Ananthan started school",
        summary="we discussed Maya Ananthan starting at the new school",
        participants=["rohit"],
        source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at="2026-04-12T09:00:00+00:00",
    )
    e2 = ep.add(
        title="trip to New York",
        summary="walked around New York for hours; great trip",
        participants=["rohit"],
        source_memory_ids=["mem-2"],
        source_kind="conversation",
        occurred_at="2026-04-20T09:00:00+00:00",
    )
    # No extractable entities — neither title nor summary has a
    # multi-token capitalized run. Backfill should report this in
    # ``episodes_with_zero_entities``.
    e3 = ep.add(
        title="quiet morning",
        summary="we drank tea and watched the rain",
        participants=["rohit"],
        source_memory_ids=["mem-3"],
        source_kind="conversation",
        occurred_at="2026-04-21T09:00:00+00:00",
    )
    return ep, (e1, e2, e3)


def _fresh_index(td: Path):
    from core.memory.entity_index import EntityIndex
    return EntityIndex(td / "entity_index.db")


# ── happy path ─────────────────────────────────────────────────────


class TestBackfillExtractsExpectedEntities(unittest.TestCase):
    def test_extracts_multi_word_names_and_places(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ids = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            report = backfill(episodes=ep, ix=ix, write=True)

            with ix._connect() as con:
                _rows = con.execute(
                    "SELECT normalized_name FROM entities"
                ).fetchall()
            ix_normalized = sorted(
                row["normalized_name"]
                for row in _rows
            )
            self.assertIn("maya ananthan", ix_normalized)
            self.assertIn("new york", ix_normalized)
            self.assertEqual(report.new_entities, 2)
            self.assertGreaterEqual(report.new_mentions, 2)

    def test_mention_provenance_is_episode_level(self):
        """source_id must equal session_id (== episode_id) for every
        backfilled mention. Title/summary text is consolidator-level;
        no source_memory_id can be honestly attributed."""
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, ids = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)

            with ix._connect() as con:
                rows = con.execute(
                    "SELECT session_id, source_id, source_kind FROM "
                    "entity_mentions"
                ).fetchall()
            self.assertGreater(len(rows), 0)
            for r in rows:
                self.assertEqual(r["session_id"], r["source_id"])
                self.assertIn(r["session_id"], ids)
                self.assertEqual(r["source_kind"], "episode")

    def test_observed_at_uses_occurred_at_when_present(self):
        """Step-5c convention: occurred_at if present, else
        created_at. Verify by checking the recorded observed_at
        equals the seeded occurred_at."""
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ids = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                rows = con.execute(
                    "SELECT session_id, observed_at FROM entity_mentions"
                ).fetchall()
            seen = {r["session_id"]: r["observed_at"] for r in rows}
            # The two seeded occurred_at values; both should appear.
            seeded = {"2026-04-12T09:00:00+00:00", "2026-04-20T09:00:00+00:00"}
            self.assertTrue(seeded.issubset(set(seen.values())))

    def test_observed_at_falls_back_to_created_at(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep = EpisodeStore(str(tdp / "lived.db"))
            eid = ep.add(
                title="Maya Ananthan visited",
                summary="she came over",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at=None,  # forces fallback
            )
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                row = con.execute(
                    "SELECT observed_at FROM entity_mentions "
                    "WHERE session_id = ?", (eid,),
                ).fetchone()
            # Whatever the fallback resolved to, it must be a
            # non-empty ISO-ish string (the episode's created_at).
            self.assertTrue(row["observed_at"])
            self.assertIn("T", row["observed_at"])

    def test_kind_is_unknown_for_all_backfilled_entities(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                rows = con.execute(
                    "SELECT kind FROM entities"
                ).fetchall()
            self.assertGreater(len(rows), 0)
            for r in rows:
                self.assertEqual(r["kind"], "unknown")


# ── snippet convention ────────────────────────────────────────────


class TestSnippetRule(unittest.TestCase):
    def test_title_hit_uses_full_title(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                rows = con.execute(
                    "SELECT snippet FROM entity_mentions "
                    "WHERE snippet LIKE '%Maya Ananthan%'"
                ).fetchall()
            # Maya appears in BOTH title and summary of e1 — at
            # least one snippet should be the full title.
            self.assertTrue(
                any(r["snippet"] == "Maya Ananthan started school"
                    for r in rows),
                "expected the title-hit snippet to be the full title",
            )

    def test_summary_hit_uses_60_char_window(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="quiet morning",
                summary=(
                    "I had a long conversation today and Maya Ananthan "
                    "told me about her week at the school and how "
                    "everyone has been doing"
                ),
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                row = con.execute(
                    "SELECT snippet FROM entity_mentions"
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertIn("Maya Ananthan", row["snippet"])
            # 60-char window centred on the span — actual length
            # depends on text bounds, but should be ≤ ~70 chars.
            self.assertLessEqual(len(row["snippet"]), 80)


# ── idempotency + dry-run ─────────────────────────────────────────


class TestIdempotency(unittest.TestCase):
    def test_rerun_is_safe_no_duplicate_rows(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                ent_before = con.execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0]
                men_before = con.execute(
                    "SELECT COUNT(*) FROM entity_mentions"
                ).fetchone()[0]
            report = backfill(episodes=ep, ix=ix, write=True)
            with ix._connect() as con:
                ent_after = con.execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0]
                men_after = con.execute(
                    "SELECT COUNT(*) FROM entity_mentions"
                ).fetchone()[0]
            self.assertEqual(ent_before, ent_after)
            self.assertEqual(men_before, men_after)
            self.assertEqual(report.new_entities, 0)
            self.assertEqual(report.new_mentions, 0)
            self.assertGreater(report.already_present_entities, 0)
            self.assertGreater(report.already_present_mentions, 0)


class TestDryRun(unittest.TestCase):
    def test_dry_run_default_writes_nothing(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            report = backfill(episodes=ep, ix=ix)  # write=False default
            with ix._connect() as con:
                _ent_count = con.execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0]
            self.assertEqual(
                _ent_count,
                0,
            )
            with ix._connect() as con:
                _men_count = con.execute(
                    "SELECT COUNT(*) FROM entity_mentions"
                ).fetchone()[0]
            self.assertEqual(
                _men_count,
                0,
            )
            # Report still computes "would-insert" counts honestly.
            self.assertGreater(report.new_entities, 0)
            self.assertGreater(report.new_mentions, 0)


# ── report shape ──────────────────────────────────────────────────


class TestReportMetrics(unittest.TestCase):
    def test_episodes_with_zero_entities_counted(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)  # third episode is empty
            ix = _fresh_index(tdp)
            report = backfill(episodes=ep, ix=ix, write=True)
            self.assertEqual(report.episodes_scanned, 3)
            self.assertEqual(report.episodes_with_zero_entities, 1)

    def test_entities_in_2plus_sessions_counted(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="Maya Ananthan visited",
                summary="x",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            ep.add(
                title="another day",
                summary="Maya Ananthan called again",
                participants=["rohit"],
                source_memory_ids=["m-2"],
                source_kind="conversation",
                occurred_at="2026-04-15T09:00:00+00:00",
            )
            ep.add(
                title="trip to New York",
                summary="just one mention",
                participants=["rohit"],
                source_memory_ids=["m-3"],
                source_kind="conversation",
                occurred_at="2026-04-20T09:00:00+00:00",
            )
            ix = _fresh_index(tdp)
            report = backfill(episodes=ep, ix=ix, write=True)
            # Maya in 2 sessions; New York in 1.
            self.assertEqual(report.entities_in_2plus_sessions, 1)

    def test_mentions_per_entity_distribution(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            report = backfill(episodes=ep, ix=ix, write=True)
            self.assertGreaterEqual(report.mentions_per_entity_max, 1)
            self.assertGreaterEqual(report.mentions_per_entity_median, 1.0)

    def test_top_entities_by_mention_count(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            report = backfill(episodes=ep, ix=ix, write=True)
            self.assertLessEqual(len(report.top_entities), 20)
            # Each top entry should carry name + mention count.
            for row in report.top_entities:
                self.assertIn("canonical_name", row)
                self.assertIn("mention_count", row)
                self.assertIn("distinct_sessions", row)


# ── safety: no mutation of lived memory; no subprocess/network ───


class TestBackfillIsReadOnlyOverEpisodes(unittest.TestCase):
    def test_episodes_db_unchanged(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ep_path = tdp / "lived_episodes.db"
            before_mtime = ep_path.stat().st_mtime_ns
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)
            # Reading via SQLite shouldn't bump the mtime, but
            # verify no INSERT/UPDATE has changed the row count.
            with ep._connect() as con:
                n = con.execute(
                    "SELECT COUNT(*) FROM episodes"
                ).fetchone()[0]
            self.assertEqual(n, 3)
            after_mtime = ep_path.stat().st_mtime_ns
            self.assertEqual(before_mtime, after_mtime)


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("backfill must not subprocess"),
             ), mock.patch.object(
                 subprocess, "Popen",
                 side_effect=AssertionError("backfill must not Popen"),
             ):
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)

    def test_no_network(self):
        from core.memory.entity_backfill import backfill

        def boom(*a, **kw):
            raise AssertionError("backfill must not open sockets")

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(socket, "socket", boom):
            tdp = Path(td)
            ep, _ = _seed_episodes(tdp)
            ix = _fresh_index(tdp)
            backfill(episodes=ep, ix=ix, write=True)


if __name__ == "__main__":
    unittest.main()
