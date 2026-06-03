# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Entity index tests (Step 5e — MSEL prerequisite).

This is the substrate-only slice: a durable entity sidecar plus a
deterministic query-expansion skeleton. There is NO LLM extraction,
NO consolidation-time change, NO production recall wiring. Tests
must enforce both the positive contract (dedup, ambiguity-aware
confidence, recency-ordered expansion) AND the negative contract
(no subprocess, no network, no mutation of unrelated stores).
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


# ── normalization ─────────────────────────────────────────────────


class TestNormalizeEntityName(unittest.TestCase):
    def test_lowercases(self):
        from core.memory.entity_index import normalize_entity_name
        self.assertEqual(
            normalize_entity_name("Maya Ananthan"), "maya ananthan",
        )

    def test_collapses_whitespace(self):
        from core.memory.entity_index import normalize_entity_name
        self.assertEqual(
            normalize_entity_name("  Maya   Ananthan\n"),
            "maya ananthan",
        )

    def test_strips_trailing_punctuation(self):
        from core.memory.entity_index import normalize_entity_name
        self.assertEqual(
            normalize_entity_name("Maya, Ananthan."), "maya ananthan",
        )

    def test_unicode_nfc_normalized(self):
        """Two equivalent unicode encodings of 'José' should
        normalize to the same string. Without NFC, café ≠ café and
        dedup breaks."""
        from core.memory.entity_index import normalize_entity_name
        a = normalize_entity_name("José")  # composed é
        b = normalize_entity_name("José")  # decomposed e + ́
        self.assertEqual(a, b)

    def test_idempotent(self):
        from core.memory.entity_index import normalize_entity_name
        once = normalize_entity_name("Maya Ananthan")
        twice = normalize_entity_name(once)
        self.assertEqual(once, twice)

    def test_empty_input_returns_empty(self):
        from core.memory.entity_index import normalize_entity_name
        self.assertEqual(normalize_entity_name(""), "")


# ── deterministic extractor ───────────────────────────────────────


class TestExtractor(unittest.TestCase):
    def test_two_consecutive_capitalized_tokens_emitted(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "I think Maya Ananthan called yesterday.",
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].surface, "Maya Ananthan")
        self.assertEqual(out[0].normalized, "maya ananthan")
        self.assertEqual(out[0].kind, "unknown")

    def test_place_name_emitted(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "we walked around New York for hours",
        )
        surfaces = [c.surface for c in out]
        self.assertIn("New York", surfaces)

    def test_three_token_name_emitted(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "I met John F Kennedy at the diner",
        )
        surfaces = [c.surface for c in out]
        self.assertIn("John F Kennedy", surfaces)

    def test_single_word_not_emitted_by_default(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "Maya called yesterday. We talked for hours.",
        )
        # No multi-word run; nothing should come out without an
        # allowlist.
        self.assertEqual(out, [])

    def test_sentence_start_stopword_skipped(self):
        """'The Hospital' is a multi-word capitalized run, but
        'The' is a junk start — the extractor should not emit
        'The Hospital'."""
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities("The Hospital was busy.")
        surfaces = [c.surface for c in out]
        self.assertNotIn("The Hospital", surfaces)

    def test_today_tomorrow_starts_skipped(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "Tomorrow Maya Ananthan will arrive.",
        )
        surfaces = [c.surface for c in out]
        # 'Tomorrow Maya' must not be emitted as a junk-start run;
        # 'Maya Ananthan' is fine because the run starts at 'Maya'.
        self.assertNotIn("Tomorrow Maya", surfaces)
        self.assertIn("Maya Ananthan", surfaces)

    def test_known_entities_allowlist_emits_singletons(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "Maya called yesterday.",
            known_entities=["Maya"],
        )
        surfaces = [c.surface for c in out]
        self.assertIn("Maya", surfaces)

    def test_known_entities_no_match_returns_empty(self):
        from core.memory.entity_index import extract_deterministic_entities
        out = extract_deterministic_entities(
            "she called yesterday.",
            known_entities=["Maya"],
        )
        self.assertEqual(out, [])

    def test_candidate_carries_spans(self):
        from core.memory.entity_index import extract_deterministic_entities
        text = "I think Maya Ananthan called."
        out = extract_deterministic_entities(text)
        self.assertEqual(len(out), 1)
        c = out[0]
        self.assertEqual(text[c.span_start:c.span_end], "Maya Ananthan")
        self.assertGreater(c.confidence, 0.0)
        self.assertLessEqual(c.confidence, 1.0)


# ── upsert / dedup ────────────────────────────────────────────────


class TestUpsertEntity(unittest.TestCase):
    def test_returns_id_and_persists(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity("Maya Ananthan", kind="person")
            self.assertTrue(eid)
            row = ix.get_entity(eid)
            self.assertEqual(row["canonical_name"], "Maya Ananthan")
            self.assertEqual(row["normalized_name"], "maya ananthan")
            self.assertEqual(row["kind"], "person")

    def test_dedupes_on_normalized_name(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            a = ix.upsert_entity("Maya Ananthan", kind="person")
            b = ix.upsert_entity("maya  ananthan", kind="person")
            c = ix.upsert_entity("Maya Ananthan.", kind="person")
            self.assertEqual(a, b)
            self.assertEqual(a, c)

    def test_different_kinds_are_separate_entities(self):
        """'Boston' the place and 'Boston' the band can coexist."""
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            place = ix.upsert_entity("Boston", kind="place")
            band = ix.upsert_entity("Boston", kind="organization")
            self.assertNotEqual(place, band)

    def test_alias_dedup_per_entity(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity(
                "Maya Ananthan", kind="person", aliases=["Maya"],
            )
            ix.add_alias(eid, "Maya")  # idempotent
            ix.add_alias(eid, "maya")  # normalizes to same — dedup
            aliases = ix.list_aliases(eid)
            self.assertEqual(
                sorted(a.lower() for a in aliases), ["maya"],
            )


# ── mention dedup ────────────────────────────────────────────────


class TestMentionDedup(unittest.TestCase):
    def test_mention_is_idempotent_on_entity_session_source(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity("Maya Ananthan", kind="person")
            mid_a = ix.add_mention(
                entity_id=eid, session_id="ep-1", source_id="mem-1",
                source_kind="conversation", observed_at="2026-04-12T09:00:00+00:00",
                snippet="Maya called", confidence=0.9,
            )
            mid_b = ix.add_mention(
                entity_id=eid, session_id="ep-1", source_id="mem-1",
                source_kind="conversation", observed_at="2026-04-13T09:00:00+00:00",
                snippet="ignored on dup", confidence=0.5,
            )
            self.assertEqual(mid_a, mid_b)
            self.assertEqual(len(ix.list_mentions(eid)), 1)

    def test_different_source_id_in_same_session_is_separate_mention(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity("Maya Ananthan", kind="person")
            ix.add_mention(
                entity_id=eid, session_id="ep-1", source_id="mem-1",
                source_kind="conversation", observed_at="2026-04-12T09:00:00+00:00",
                snippet="a", confidence=0.9,
            )
            ix.add_mention(
                entity_id=eid, session_id="ep-1", source_id="mem-2",
                source_kind="conversation", observed_at="2026-04-12T09:30:00+00:00",
                snippet="b", confidence=0.9,
            )
            self.assertEqual(len(ix.list_mentions(eid)), 2)


# ── find_entities + alias ambiguity ──────────────────────────────


class TestFindEntities(unittest.TestCase):
    def test_canonical_match_returns_single_entity_full_confidence(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity(
                "Maya Ananthan", kind="person", aliases=["Maya"],
            )
            matches = ix.find_entities("Maya Ananthan")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].entity_id, eid)
            self.assertEqual(matches[0].confidence, 1.0)

    def test_alias_unique_to_one_entity_full_confidence(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity(
                "Maya Ananthan", kind="person", aliases=["Maya"],
            )
            matches = ix.find_entities("Maya")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].entity_id, eid)
            self.assertEqual(matches[0].confidence, 1.0)

    def test_ambiguous_alias_lowers_confidence(self):
        """Two entities both have 'Maya' as an alias. find_entities
        returns BOTH at confidence 0.5 — half each."""
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            a = ix.upsert_entity(
                "Maya Ananthan", kind="person", aliases=["Maya"],
            )
            b = ix.upsert_entity(
                "Maya Anjali", kind="person", aliases=["Maya"],
            )
            matches = ix.find_entities("Maya")
            ids = sorted(m.entity_id for m in matches)
            self.assertEqual(ids, sorted([a, b]))
            for m in matches:
                self.assertAlmostEqual(m.confidence, 0.5, places=4)

    def test_no_match_returns_empty(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            self.assertEqual(ix.find_entities("nobody"), [])

    def test_empty_query_returns_empty(self):
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            ix.upsert_entity("Maya Ananthan", kind="person")
            self.assertEqual(ix.find_entities(""), [])
            self.assertEqual(ix.find_entities("   "), [])


# ── expand_query ─────────────────────────────────────────────────


class TestExpandQuery(unittest.TestCase):
    def _setup_with_two_sessions(self):
        from core.memory.entity_index import EntityIndex
        ix = EntityIndex(":memory:")
        self.addCleanup(ix.close)
        eid = ix.upsert_entity(
            "Maya Ananthan", kind="person", aliases=["Maya"],
        )
        ix.add_mention(
            entity_id=eid, session_id="ep-old", source_id="mem-old",
            source_kind="conversation",
            observed_at="2026-01-15T09:00:00+00:00",
            snippet="we talked about Maya", confidence=0.9,
        )
        ix.add_mention(
            entity_id=eid, session_id="ep-recent", source_id="mem-recent",
            source_kind="conversation",
            observed_at="2026-04-20T09:00:00+00:00",
            snippet="Maya called today", confidence=0.95,
        )
        return ix, eid

    def test_canonical_match_pulls_session_ids(self):
        from core.memory.entity_index import expand_query
        ix, eid = self._setup_with_two_sessions()
        out = expand_query("when did Maya Ananthan call?", ix=ix)
        self.assertEqual(out.original_query, "when did Maya Ananthan call?")
        self.assertIn(eid, [e.entity_id for e in out.matched_entities])
        self.assertIn("ep-old", out.session_ids)
        self.assertIn("ep-recent", out.session_ids)
        self.assertIn("mem-old", out.source_ids)
        self.assertIn("mem-recent", out.source_ids)

    def test_alias_match_pulls_session_ids(self):
        from core.memory.entity_index import expand_query
        ix, _ = self._setup_with_two_sessions()
        out = expand_query("how is Maya?", ix=ix)
        self.assertEqual(set(out.session_ids), {"ep-old", "ep-recent"})

    def test_results_ordered_most_recent_first(self):
        from core.memory.entity_index import expand_query
        ix, _ = self._setup_with_two_sessions()
        out = expand_query("Maya", ix=ix)
        self.assertEqual(
            out.session_ids[:2], ["ep-recent", "ep-old"],
        )

    def test_limit_caps_to_most_recent_n(self):
        from core.memory.entity_index import EntityIndex, expand_query
        ix = EntityIndex(":memory:")
        self.addCleanup(ix.close)
        eid = ix.upsert_entity(
            "Maya Ananthan", kind="person", aliases=["Maya"],
        )
        for i in range(5):
            ix.add_mention(
                entity_id=eid,
                session_id=f"ep-{i:02d}",
                source_id=f"mem-{i:02d}",
                source_kind="conversation",
                observed_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
                snippet="x", confidence=0.9,
            )
        out = expand_query("Maya", ix=ix, limit_sessions=2)
        # Ordered most-recent-first: ep-04, ep-03 only.
        self.assertEqual(out.session_ids, ["ep-04", "ep-03"])

    def test_no_match_returns_empty_expansion(self):
        from core.memory.entity_index import expand_query
        ix, _ = self._setup_with_two_sessions()
        out = expand_query("nobody mentioned", ix=ix)
        self.assertEqual(out.matched_entities, [])
        self.assertEqual(out.session_ids, [])
        self.assertEqual(out.source_ids, [])
        self.assertEqual(out.confidence, 0.0)

    def test_empty_query_returns_empty_expansion(self):
        from core.memory.entity_index import expand_query
        ix, _ = self._setup_with_two_sessions()
        out = expand_query("", ix=ix)
        self.assertEqual(out.session_ids, [])
        self.assertEqual(out.confidence, 0.0)

    def test_confidence_is_max_of_matched_entity_confidences(self):
        from core.memory.entity_index import EntityIndex, expand_query
        ix = EntityIndex(":memory:")
        self.addCleanup(ix.close)
        ix.upsert_entity(
            "Maya Ananthan", kind="person", aliases=["Maya"],
        )
        ix.upsert_entity(
            "Maya Anjali", kind="person", aliases=["Maya"],
        )
        # Ambiguous alias → each entity at 0.5 → max = 0.5.
        out = expand_query("Maya", ix=ix)
        self.assertAlmostEqual(out.confidence, 0.5, places=4)

    def test_explanation_is_present_and_human_readable(self):
        from core.memory.entity_index import expand_query
        ix, _ = self._setup_with_two_sessions()
        out = expand_query("Maya", ix=ix)
        self.assertIn("Maya", out.explanation)
        self.assertTrue(len(out.explanation) > 0)


class TestExpandQueryNaturalText(unittest.TestCase):
    """REGRESSION GUARD: 2026-05-02 zero-fires investigation found
    `_scan_query_for_matches` only fed Capital-case tokens to
    `find_entities`. Natural Telegram traffic uses lowercase
    ("how is maez doing"), so 1,190 messages over 7 days produced
    zero `entity_expansion fired` log lines despite the substrate
    being live. The data layer (`find_entities`) IS case-insensitive
    on canonical / alias / normalized lookup; the bug was in candidate
    surface generation. Tests cover each natural-text shape."""

    def _ix_with_maez_and_rohit(self):
        from core.memory.entity_index import EntityIndex
        ix = EntityIndex(":memory:")
        self.addCleanup(ix.close)
        eid_maez = ix.upsert_entity(
            "Maez", kind="project", aliases=["the Maez"],
        )
        eid_rohit = ix.upsert_entity("Rohit", kind="person")
        return ix, eid_maez, eid_rohit

    def test_lowercase_canonical_in_natural_question(self):
        from core.memory.entity_index import expand_query
        ix, eid_maez, _ = self._ix_with_maez_and_rohit()
        out = expand_query("how is maez doing today", ix=ix)
        self.assertIn(
            eid_maez, [e.entity_id for e in out.matched_entities],
            "lowercase canonical 'maez' inside a natural question "
            "must match — production traffic is overwhelmingly lowercase",
        )

    def test_lowercase_alias_in_natural_question(self):
        from core.memory.entity_index import expand_query
        ix, eid_maez, _ = self._ix_with_maez_and_rohit()
        out = expand_query("any update from the maez today?", ix=ix)
        self.assertIn(eid_maez, [e.entity_id for e in out.matched_entities])

    def test_lowercase_canonical_with_punctuation(self):
        from core.memory.entity_index import expand_query
        ix, eid_maez, _ = self._ix_with_maez_and_rohit()
        out = expand_query("maez? what's going on", ix=ix)
        self.assertIn(eid_maez, [e.entity_id for e in out.matched_entities])

    def test_multiple_lowercase_entities(self):
        from core.memory.entity_index import expand_query
        ix, eid_maez, eid_rohit = self._ix_with_maez_and_rohit()
        out = expand_query("did rohit ask maez anything", ix=ix)
        ids = [e.entity_id for e in out.matched_entities]
        self.assertIn(eid_maez, ids)
        self.assertIn(eid_rohit, ids)

    def test_capital_case_still_works(self):
        """Make sure adding lowercase support doesn't regress the
        existing capital-case path."""
        from core.memory.entity_index import expand_query
        ix, eid_maez, _ = self._ix_with_maez_and_rohit()
        out = expand_query("how is Maez doing today", ix=ix)
        self.assertIn(eid_maez, [e.entity_id for e in out.matched_entities])

    def test_stopwords_alone_dont_match(self):
        """Don't false-positive on common short tokens like 'a', 'is',
        'how' — they shouldn't get fed to find_entities and silently
        bind to some unrelated entity."""
        from core.memory.entity_index import expand_query
        ix, _, _ = self._ix_with_maez_and_rohit()
        out = expand_query("how is it doing today", ix=ix)
        self.assertEqual(out.matched_entities, [])

    def test_unicode_lowercase_diacritic(self):
        """Reviewer follow-up: ASCII-only `[a-zA-Z]` would drop
        lowercase diacritics. \\w with re.UNICODE picks them up so an
        entity registered with non-ASCII letters reaches the data
        layer regardless of whether the surface arrived capitalized."""
        from core.memory.entity_index import EntityIndex, expand_query
        ix = EntityIndex(":memory:")
        self.addCleanup(ix.close)
        eid = ix.upsert_entity("José", kind="person")
        out = expand_query("did josé call today", ix=ix)
        self.assertIn(eid, [e.entity_id for e in out.matched_entities])


# ── side-effect freedom ──────────────────────────────────────────


class TestNoNetworkOrSubprocess(unittest.TestCase):
    def test_no_subprocess(self):
        from core.memory.entity_index import (
            EntityIndex, expand_query, extract_deterministic_entities,
            normalize_entity_name,
        )
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess allowed"),
             ), mock.patch.object(
                 subprocess, "Popen",
                 side_effect=AssertionError("no Popen allowed"),
             ):
            ix = EntityIndex(Path(td) / "ix.db")
            normalize_entity_name("Maya Ananthan")
            extract_deterministic_entities("Maya Ananthan called")
            eid = ix.upsert_entity(
                "Maya Ananthan", kind="person", aliases=["Maya"],
            )
            ix.add_mention(
                entity_id=eid, session_id="ep-1", source_id="mem-1",
                source_kind="conversation",
                observed_at="2026-04-20T09:00:00+00:00",
                snippet="x", confidence=0.9,
            )
            expand_query("Maya", ix=ix)

    def test_no_network(self):
        from core.memory.entity_index import EntityIndex, expand_query

        def boom(*a, **kw):
            raise AssertionError("entity_index must not open sockets")

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(socket, "socket", boom):
            ix = EntityIndex(Path(td) / "ix.db")
            eid = ix.upsert_entity("Maya Ananthan", kind="person")
            ix.add_mention(
                entity_id=eid, session_id="ep-1", source_id="mem-1",
                source_kind="conversation",
                observed_at="2026-04-20T09:00:00+00:00",
                snippet="x", confidence=0.9,
            )
            expand_query("Maya Ananthan", ix=ix)


if __name__ == "__main__":
    unittest.main()
