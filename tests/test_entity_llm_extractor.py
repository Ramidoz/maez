# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Offline LLM entity extraction tests (Step 5m).

The extractor calls a local LLM (llama.cpp / ollama via the
existing routing.llm_client) once per episode, parses conservative
JSON, hallucination-checks each entity against the source text,
and (when ``--write``) populates the entity index. Tests inject a
fake ``extract_fn`` so the LLM round-trip is deterministic and
offline; the production path uses the same shape via
``llm_client.chat``.
"""

from __future__ import annotations

import json
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


def _episodes(td: Path, items):
    from core.memory.episodes import EpisodeStore

    ep = EpisodeStore(str(td / "lived.db"))
    ids = []
    for i, (title, summary) in enumerate(items):
        ids.append(ep.add(
            title=title, summary=summary,
            participants=["rohit"],
            source_memory_ids=[f"mem-{i}"],
            source_kind="conversation",
            occurred_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
        ))
    return ep, ids


def _fake_extractor(per_episode_response: dict[str, str]):
    """Returns an extract_fn closure: keyed by exact ``title`` so a
    test can craft per-episode LLM responses without depending on
    the prompt body."""
    def _fn(text: str, *, episode: dict, **_) -> str:
        return per_episode_response.get(
            episode["title"], "[]",
        )
    return _fn


# ── valid extraction → entities + mentions ───────────────────────


class TestValidExtractionPlansEntitiesAndMentions(unittest.TestCase):
    def test_valid_json_yields_entities_and_mentions(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, ids = _episodes(Path(td), [
                ("Maya Ananthan started school",
                 "Maya seemed nervous"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya seemed nervous",
                    "confidence": 0.9,
                },
            ])
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": response,
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            ents = ix._connect().execute(
                "SELECT canonical_name, kind FROM entities"
            ).fetchall()
            self.assertEqual(len(ents), 1)
            self.assertEqual(ents[0]["canonical_name"], "Maya Ananthan")
            self.assertEqual(ents[0]["kind"], "person")
            ali = ix._connect().execute(
                "SELECT alias FROM aliases"
            ).fetchall()
            self.assertEqual([r["alias"] for r in ali], ["Maya"])
            mentions = ix._connect().execute(
                "SELECT session_id, source_id, source_kind FROM "
                "entity_mentions"
            ).fetchall()
            self.assertEqual(len(mentions), 1)
            self.assertEqual(mentions[0]["session_id"], ids[0])
            self.assertEqual(
                mentions[0]["source_id"], ids[0],
                "source_id must equal session_id (== episode_id) "
                "per the Step-5f provenance rule",
            )
            self.assertGreaterEqual(report.entities_new, 1)
            self.assertGreaterEqual(report.mentions_new, 1)


# ── invalid JSON → warning, no crash ─────────────────────────────


class TestInvalidJsonHandled(unittest.TestCase):
    def test_invalid_json_increments_parse_failures(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan started school", "x"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": "not valid json {{",
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            self.assertEqual(report.parse_failures, 1)
            self.assertEqual(report.entities_new, 0)
            self.assertEqual(report.mentions_new, 0)

    def test_empty_array_response_no_entities(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("dinner", "we cooked together"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            extract_fn = _fake_extractor({"dinner": "[]"})
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            self.assertEqual(report.entities_new, 0)
            self.assertEqual(report.parse_failures, 0)


# ── hallucination check ──────────────────────────────────────────


class TestHallucinationCheck(unittest.TestCase):
    """Canonical name OR an alias must appear in the episode text
    (case-insensitive, word-boundary). Otherwise the LLM
    fabricated; reject with the rejection counter incremented."""

    def test_canonical_absent_from_text_rejected(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("dinner", "we cooked together"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Sarah Connor",
                    "kind": "person",
                    "aliases": [],
                    "evidence_quote": "fabricated",
                    "confidence": 0.95,
                },
            ])
            extract_fn = _fake_extractor({"dinner": response})
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            self.assertEqual(report.entities_new, 0)
            self.assertGreaterEqual(report.rejected_hallucinated, 1)

    def test_alias_present_canonical_absent_accepted(self):
        """Owner-supplied canonical (e.g. "Maya Ananthan") may not
        appear verbatim, but if an alias does, the entity is
        grounded enough to keep."""
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("classroom dynamics", "Maya seemed nervous"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya seemed nervous",
                    "confidence": 0.9,
                },
            ])
            extract_fn = _fake_extractor({
                "classroom dynamics": response,
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            self.assertEqual(report.entities_new, 1)
            self.assertEqual(report.rejected_hallucinated, 0)


# ── low-confidence rejection ─────────────────────────────────────


class TestConfidenceThreshold(unittest.TestCase):
    def test_below_threshold_rejected(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan started school", "Maya was happy"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya was happy",
                    "confidence": 0.3,  # below default threshold
                },
            ])
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": response,
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
                min_confidence=0.5,
            )
            self.assertEqual(report.entities_new, 0)
            self.assertGreaterEqual(report.rejected_low_confidence, 1)

    def test_at_or_above_threshold_accepted(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan started school", "Maya was happy"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya was happy",
                    "confidence": 0.5,
                },
            ])
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": response,
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
                min_confidence=0.5,
            )
            self.assertEqual(report.entities_new, 1)


# ── dry-run + idempotency ────────────────────────────────────────


class TestDryRunAndIdempotency(unittest.TestCase):
    def test_dry_run_writes_nothing_but_reports_counts(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan started school", "Maya was happy"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya was happy",
                    "confidence": 0.9,
                },
            ])
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": response,
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn,  # write=False
            )
            n_ent = ix._connect().execute(
                "SELECT COUNT(*) FROM entities"
            ).fetchone()[0]
            n_men = ix._connect().execute(
                "SELECT COUNT(*) FROM entity_mentions"
            ).fetchone()[0]
            self.assertEqual(n_ent, 0)
            self.assertEqual(n_men, 0)
            # Dry-run report still computes the would-write counts.
            self.assertGreaterEqual(report.entities_new, 1)
            self.assertGreaterEqual(report.mentions_new, 1)

    def test_rerun_idempotent(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan started school", "Maya was happy"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya was happy",
                    "confidence": 0.9,
                },
            ])
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": response,
            })
            batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            n_ent_before = ix._connect().execute(
                "SELECT COUNT(*) FROM entities"
            ).fetchone()[0]
            n_men_before = ix._connect().execute(
                "SELECT COUNT(*) FROM entity_mentions"
            ).fetchone()[0]
            r2 = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            self.assertEqual(
                ix._connect().execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0], n_ent_before,
            )
            self.assertEqual(
                ix._connect().execute(
                    "SELECT COUNT(*) FROM entity_mentions"
                ).fetchone()[0], n_men_before,
            )
            self.assertEqual(r2.entities_new, 0)
            self.assertEqual(r2.mentions_new, 0)


# ── --limit ──────────────────────────────────────────────────────


class TestLimit(unittest.TestCase):
    def test_limit_caps_episodes_processed(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                (f"Maya Ananthan note {i}", "Maya was happy")
                for i in range(5)
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya was happy",
                    "confidence": 0.9,
                },
            ])
            extract_fn = lambda text, *, episode, **_: response  # noqa: E731

            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn,
                write=True, limit=2,
            )
            self.assertEqual(report.episodes_scanned, 2)


# ── safety ──────────────────────────────────────────────────────


class TestNoSubprocessNoNetwork(unittest.TestCase):
    def test_no_subprocess_no_socket_with_mocked_extract_fn(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan started school", "Maya"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = json.dumps([
                {
                    "canonical_name": "Maya Ananthan",
                    "kind": "person",
                    "aliases": ["Maya"],
                    "evidence_quote": "Maya",
                    "confidence": 0.9,
                },
            ])
            extract_fn = _fake_extractor({
                "Maya Ananthan started school": response,
            })
            batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )


# ── JSON in prose: extract first array ───────────────────────────


class TestJsonExtractionFromProse(unittest.TestCase):
    """Local LLMs often wrap JSON in prose ('Sure, here is the JSON:
    [...]'). The extractor should locate the first JSON array in
    the response and parse that, not give up on prose framing."""

    def test_json_array_inside_prose_parsed(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_llm_extractor import batch_extract

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _episodes(Path(td), [
                ("Maya Ananthan note", "Maya seemed happy"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            response = (
                "Sure, here is the JSON:\n"
                + json.dumps([
                    {
                        "canonical_name": "Maya Ananthan",
                        "kind": "person",
                        "aliases": ["Maya"],
                        "evidence_quote": "Maya seemed happy",
                        "confidence": 0.9,
                    },
                ])
                + "\n\nLet me know if you need more."
            )
            extract_fn = _fake_extractor({
                "Maya Ananthan note": response,
            })
            report = batch_extract(
                episodes=ep, ix=ix, extract_fn=extract_fn, write=True,
            )
            self.assertEqual(report.entities_new, 1)


if __name__ == "__main__":
    unittest.main()
