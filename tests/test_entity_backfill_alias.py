# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Alias-aware entity-index backfill tests (Step 5h).

Extends Step-5f deterministic backfill with a second pass that
walks the alias table from Step-5g. The load-bearing rule: alias
hits whose span overlaps an extractor-recorded span are dropped.
Without that rule, owner-curated alias seeding inflates the index
with duplicate / wrong-entity mentions and makes the cross-session
metric look better while making recall worse.
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


def _seed_index_with_alex(td: Path):
    """Single unambiguous alias 'Alex' → 'Alex Rivera'."""
    from core.memory.entity_index import EntityIndex

    ix = EntityIndex(td / "ix.db")
    rivera = ix.upsert_entity(
        "Alex Rivera", kind="person", aliases=["Alex"],
    )
    return ix, rivera


def _seed_index_with_two_mayas(td: Path):
    """Two entities both aliased 'Maya' — ambiguity."""
    from core.memory.entity_index import EntityIndex

    ix = EntityIndex(td / "ix.db")
    a = ix.upsert_entity(
        "Maya Ananthan", kind="person", aliases=["Maya"],
    )
    b = ix.upsert_entity(
        "Maya Anjali", kind="person", aliases=["Maya"],
    )
    return ix, a, b


# ── alias triggers a mention for the canonical entity ─────────────


class TestAliasCreatesCanonicalMention(unittest.TestCase):
    def test_alex_alias_resolves_to_alex_rivera(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix, rivera = _seed_index_with_alex(tdp)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="Alex called yesterday",
                summary="we caught up",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            rows = ix._connect().execute(
                "SELECT entity_id, confidence FROM entity_mentions "
                "WHERE session_id = ?", (ep_id,),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["entity_id"], rivera)
            # Unique alias = full confidence.
            self.assertEqual(rows[0]["confidence"], 1.0)


# ── ambiguous alias creates two mentions at split confidence ──────


class TestAmbiguousAliasCreatesSplitMentions(unittest.TestCase):
    def test_two_entities_each_get_a_split_confidence_mention(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix, a, b = _seed_index_with_two_mayas(tdp)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="I saw Maya at the store",
                summary="quiet moment",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            report = backfill(episodes=ep, ix=ix, write=True)
            rows = ix._connect().execute(
                "SELECT entity_id, confidence FROM entity_mentions "
                "WHERE session_id = ?", (ep_id,),
            ).fetchall()
            ents = sorted(r["entity_id"] for r in rows)
            self.assertEqual(ents, sorted([a, b]))
            for r in rows:
                self.assertAlmostEqual(r["confidence"], 0.5, places=4)
            # Counted as ambiguous in the report.
            self.assertEqual(report.ambiguous_alias_mentions, 2)


# ── word boundary: "Ann" must not match "Annapurna" ───────────────


class TestWordBoundary(unittest.TestCase):
    def test_alias_ann_does_not_match_annapurna(self):
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            ann_eid = ix.upsert_entity(
                "Ann Petrov", kind="person", aliases=["Ann"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="Annapurna mountain trip",
                summary="we trekked Annapurna",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            rows = ix._connect().execute(
                "SELECT entity_id FROM entity_mentions "
                "WHERE session_id = ? AND entity_id = ?",
                (ep_id, ann_eid),
            ).fetchall()
            self.assertEqual(rows, [])

    def test_alias_ann_matches_at_word_boundary(self):
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            ann_eid = ix.upsert_entity(
                "Ann Petrov", kind="person", aliases=["Ann"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="quiet morning",
                summary="I met Ann at the cafe and we talked",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            rows = ix._connect().execute(
                "SELECT entity_id FROM entity_mentions "
                "WHERE session_id = ? AND entity_id = ?",
                (ep_id, ann_eid),
            ).fetchall()
            self.assertEqual(len(rows), 1)


# ── longer-alias priority ────────────────────────────────────────


class TestLongerAliasPriority(unittest.TestCase):
    def test_track_a_wins_over_track(self):
        """Two aliases applicable to the same span: longer wins.
        'Track A' matches the full span; 'Track' inside it is
        dropped by overlap with the longer-alias's recorded span."""
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            track_a_id = ix.upsert_entity(
                "Track A", kind="project", aliases=["Track A"],
            )
            other_id = ix.upsert_entity(
                "Track Bicycle Co", kind="organization",
                aliases=["Track"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="quiet morning",
                summary="we discussed Track A at the meeting",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            ents = sorted(r["entity_id"] for r in ix._connect().execute(
                "SELECT entity_id FROM entity_mentions "
                "WHERE session_id = ?", (ep_id,),
            ).fetchall())
            self.assertIn(track_a_id, ents)
            self.assertNotIn(other_id, ents)


# ── overlap rule: extractor wins over alias ──────────────────────


class TestExtractorWinsOnOverlap(unittest.TestCase):
    def test_maya_alias_dropped_inside_maya_ananthan_span(self):
        """The pushback case: extractor finds 'Maya Ananthan' as a
        canonical entity; alias 'Maya' lookup must NOT also produce
        a mention for the OTHER Maya entity from inside that span."""
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            ananthan_id = ix.upsert_entity(
                "Maya Ananthan", kind="person",
            )
            anjali_id = ix.upsert_entity(
                "Maya Anjali", kind="person", aliases=["Maya"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="Maya Ananthan called yesterday",
                summary="we talked",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            rows = ix._connect().execute(
                "SELECT entity_id FROM entity_mentions "
                "WHERE session_id = ?", (ep_id,),
            ).fetchall()
            ents = {r["entity_id"] for r in rows}
            # Only the canonical match should produce a mention.
            self.assertIn(ananthan_id, ents)
            self.assertNotIn(anjali_id, ents)

    def test_alias_kept_when_outside_extractor_span(self):
        """Alias 'Maya' OUTSIDE any 'Maya Ananthan' span is still
        recorded — the overlap rule is span-local, not
        document-wide."""
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            ix.upsert_entity("Maya Ananthan", kind="person")
            anjali_id = ix.upsert_entity(
                "Maya Anjali", kind="person", aliases=["Maya"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep_id = ep.add(
                title="lunch with Maya",
                summary="separately, Maya Ananthan also messaged",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            rows = ix._connect().execute(
                "SELECT entity_id FROM entity_mentions "
                "WHERE session_id = ? AND entity_id = ?",
                (ep_id, anjali_id),
            ).fetchall()
            # Anjali alias hit in title is outside any extractor span
            # (title has no multi-token capitalized run because 'Maya'
            # alone isn't extractable). Should be kept.
            self.assertEqual(len(rows), 1)


# ── report shape: alias-aware fields ─────────────────────────────


class TestReportFields(unittest.TestCase):
    def test_report_has_split_deterministic_vs_alias_counts(self):
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            ix.upsert_entity(
                "Alex Rivera", kind="person", aliases=["Alex"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            # episode 1: deterministic only ('New York' multi-token)
            ep.add(
                title="trip to New York",
                summary="we walked around",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            # episode 2: alias-only ('Alex' single token)
            ep.add(
                title="Alex called",
                summary="we caught up",
                participants=["rohit"],
                source_memory_ids=["m-2"],
                source_kind="conversation",
                occurred_at="2026-04-13T09:00:00+00:00",
            )
            report = backfill(episodes=ep, ix=ix, write=True)
            self.assertGreaterEqual(report.deterministic_mentions_new, 1)
            self.assertGreaterEqual(report.alias_mentions_new, 1)
            # Totals are the sum.
            self.assertEqual(
                report.new_mentions,
                report.deterministic_mentions_new
                + report.alias_mentions_new,
            )

    def test_alias_matches_by_alias_is_dict_keyed_by_surface(self):
        """alias_matches_by_alias counts ALIAS-DRIVEN matches only.
        Aliases that overlap an extractor span are dropped (per the
        load-bearing overlap rule) and don't appear here — that's
        what makes the metric honest."""
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix = EntityIndex(tdp / "ix.db")
            ix.upsert_entity(
                "Alex Rivera", kind="person", aliases=["Alex"],
            )
            # Realistic alias shape: a phrase the extractor cannot
            # catch (lowercase) for an entity whose canonical name
            # the extractor *can* catch when it appears verbatim.
            ix.upsert_entity(
                "Track A", kind="project", aliases=["the roadmap"],
            )
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="Alex meeting",
                summary="we discussed the roadmap at length",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            ep.add(
                title="follow-up",
                summary="Alex pinged again",
                participants=["rohit"],
                source_memory_ids=["m-2"],
                source_kind="conversation",
                occurred_at="2026-04-13T09:00:00+00:00",
            )
            report = backfill(episodes=ep, ix=ix, write=True)
            self.assertIsInstance(report.alias_matches_by_alias, dict)
            # 'Alex' matched in 2 episodes; 'the roadmap' in 1.
            self.assertEqual(report.alias_matches_by_alias["Alex"], 2)
            self.assertEqual(
                report.alias_matches_by_alias["the roadmap"], 1,
            )


# ── idempotency + dry-run preserved ──────────────────────────────


class TestIdempotencyAndDryRun(unittest.TestCase):
    def test_rerun_idempotent_for_alias_mentions(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix, _ = _seed_index_with_alex(tdp)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="Alex called",
                summary="x",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)
            n_before = ix._connect().execute(
                "SELECT COUNT(*) FROM entity_mentions"
            ).fetchone()[0]
            r2 = backfill(episodes=ep, ix=ix, write=True)
            n_after = ix._connect().execute(
                "SELECT COUNT(*) FROM entity_mentions"
            ).fetchone()[0]
            self.assertEqual(n_before, n_after)
            self.assertEqual(r2.alias_mentions_new, 0)
            self.assertGreaterEqual(r2.alias_mentions_existing, 1)

    def test_dry_run_writes_no_alias_mentions(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix, _ = _seed_index_with_alex(tdp)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="Alex called",
                summary="x",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            report = backfill(episodes=ep, ix=ix)  # write=False default
            n = ix._connect().execute(
                "SELECT COUNT(*) FROM entity_mentions"
            ).fetchone()[0]
            self.assertEqual(n, 0)
            # Report still computes the would-be counts.
            self.assertGreaterEqual(report.alias_mentions_new, 1)


# ── safety: no subprocess / no network ───────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 subprocess, "Popen",
                 side_effect=AssertionError("no Popen"),
             ):
            tdp = Path(td)
            ix, _ = _seed_index_with_alex(tdp)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="Alex called",
                summary="x",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)

    def test_no_network(self):
        from core.memory.entity_backfill import backfill
        from core.memory.episodes import EpisodeStore

        def boom(*a, **kw):
            raise AssertionError("no sockets")

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(socket, "socket", boom):
            tdp = Path(td)
            ix, _ = _seed_index_with_alex(tdp)
            ep = EpisodeStore(str(tdp / "lived.db"))
            ep.add(
                title="Alex called",
                summary="x",
                participants=["rohit"],
                source_memory_ids=["m-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            backfill(episodes=ep, ix=ix, write=True)


if __name__ == "__main__":
    unittest.main()
