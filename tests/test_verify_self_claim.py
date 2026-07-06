# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for the forensic self-claim verifier (Step 5u).

Mocks each store as a fresh tmp DB / in-memory chroma so the
tests are deterministic and don't touch production state. Only
the verifier's per-store search functions are exercised — the
public ``verify_phrase`` aggregator is verified end-to-end on
the same fixtures.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_UNSEAL_ARGS = {
    "actor": "test-operator",
    "s7_receipt_ref": "s7:test",
    "reason": "unit test diagnostic",
}

_VERIFY_UNSEAL_ARGS = {
    "private_unseal_actor": "test-operator",
    "private_unseal_s7_receipt_ref": "s7:test",
    "private_unseal_reason": "unit test diagnostic",
}


def _seed_private_thoughts(td: Path):
    db = td / "memory" / "private_thoughts.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE private_thoughts ("
            "thought_id TEXT, ts TEXT, content TEXT, "
            "provenance TEXT, context_json TEXT, memory_phase TEXT)"
        )
        con.execute(
            "INSERT INTO private_thoughts VALUES (?,?,?,?,?,?)",
            (
                "th-1",
                "2026-04-22T10:00",
                "the noise was a hemorrhage today",
                "internal",
                "{}",
                "Track A",
            ),
        )
        con.execute(
            "INSERT INTO private_thoughts VALUES (?,?,?,?,?,?)",
            (
                "th-2",
                "2026-04-23T10:00",
                "quiet today, things are calm",
                "internal",
                "{}",
                "Track A",
            ),
        )
        con.commit()
    finally:
        con.close()
    return db


def _seed_fast_conversation(td: Path):
    db = td / "memory" / "fast_conversation_log.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE fast_turns ("
            "id INTEGER, trust_scope TEXT, role TEXT, text TEXT, "
            "created_at REAL)"
        )
        con.execute(
            "INSERT INTO fast_turns VALUES (?,?,?,?,?)",
            (1, "rohit", "user", "what do you think about hemorrhage?", 1745000000.0),
        )
        con.execute(
            "INSERT INTO fast_turns VALUES (?,?,?,?,?)",
            (2, "rohit", "maez", "I called it a hemorrhage in my journal", 1745000060.0),
        )
        con.execute(
            "INSERT INTO fast_turns VALUES (?,?,?,?,?)",
            (3, "rohit", "maez", "today is calmer", 1745086400.0),
        )
        con.commit()
    finally:
        con.close()
    return db


def _seed_lived_episodes(td: Path):
    db = td / "memory" / "lived_episodes.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE episodes ("
            "id TEXT, created_at TEXT, occurred_at TEXT, "
            "title TEXT, summary TEXT, "
            "participants_json TEXT, emotional_tone TEXT, "
            "importance INTEGER, open_loop TEXT, "
            "source_memory_ids_json TEXT, source_kind TEXT, "
            "status TEXT, authorship TEXT, memory_voice TEXT)"
        )
        con.execute(
            "INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "ep-1",
                "2026-04-22T10:00",
                "2026-04-22T09:00",
                "the hemorrhage day",
                "logged 2860 errors today",
                "[]",
                None,
                5,
                None,
                "[]",
                "system",
                "active",
                None,
                "first_person",
            ),
        )
        con.commit()
    finally:
        con.close()
    return db


def _seed_wonderings(td: Path):
    db = td / "memory" / "wonderings.db"
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE wonderings ("
            "id TEXT, created_at REAL, question TEXT, "
            "status TEXT, advance_count INTEGER, deferral_count INTEGER, "
            "pending_card_id TEXT, last_advanced REAL, source TEXT, "
            "conclusion TEXT, last_pursuit_at REAL, pursuit_count INTEGER)"
        )
        con.execute(
            "INSERT INTO wonderings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "w-1",
                1745000000.0,
                "is the hemorrhage over?",
                "open",
                0,
                0,
                None,
                None,
                "self",
                None,
                None,
                0,
            ),
        )
        con.commit()
    finally:
        con.close()
    return db


# ── per-store tests ──────────────────────────────────────────────


class TestPrivateThoughtsSearch(unittest.TestCase):
    def test_finds_phrase_in_content(self):
        from scripts.verify_self_claim import _search_private_thoughts

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            _seed_private_thoughts(tdp)
            hits = _search_private_thoughts(
                phrase="hemorrhage",
                repo_root=tdp,
                top_n=10,
                **_UNSEAL_ARGS,
            )
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].store, "private_thoughts")
            self.assertIn("hemorrhage", hits[0].snippet.lower())

    def test_private_thoughts_search_records_forensic_audit(self):
        from scripts.verify_self_claim import _search_private_thoughts

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            _seed_private_thoughts(tdp)
            hits = _search_private_thoughts(
                phrase="hemorrhage",
                repo_root=tdp,
                top_n=10,
                **_UNSEAL_ARGS,
            )

            self.assertEqual(len(hits), 1)
            receipt_db = tdp / "memory" / "unseal_receipts.db"
            receipt_con = sqlite3.connect(receipt_db)
            try:
                receipt_row = receipt_con.execute(
                    "SELECT actor, s7_receipt_ref, scope_kind, scope_detail, reason "
                    "FROM unseal_receipts"
                ).fetchone()
            finally:
                receipt_con.close()
            self.assertEqual(receipt_row[0], "test-operator")
            self.assertEqual(receipt_row[1], "s7:test")
            self.assertEqual(receipt_row[2], "query")
            self.assertEqual(receipt_row[3], "like:hemorrhage")
            self.assertEqual(receipt_row[4], "unit test diagnostic")
            audit_db = tdp / "memory" / "audit_log.db"
            con = sqlite3.connect(audit_db)
            try:
                row = con.execute(
                    "SELECT action, policy_rule_id, params_json FROM audit_log"
                ).fetchone()
            finally:
                con.close()
            self.assertEqual(row[0], "private_thoughts.verify_self_claim_search")
            self.assertEqual(
                row[1],
                "S1A1_PRIVATE_THOUGHTS_FORENSIC_AUDIT",
            )
            params = json.loads(row[2])
            self.assertEqual(params["returned_hit_count"], 1)
            self.assertIn("returned_handles_sha256", params)

    def test_no_db_returns_empty(self):
        from scripts.verify_self_claim import _search_private_thoughts

        with tempfile.TemporaryDirectory() as td:
            hits = _search_private_thoughts(
                phrase="anything",
                repo_root=Path(td),
                top_n=10,
                **_UNSEAL_ARGS,
            )
            self.assertEqual(hits, [])


class TestFastConversationSearch(unittest.TestCase):
    def test_only_maez_role_returned(self):
        from scripts.verify_self_claim import _search_fast_conversation

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tdp_mem = tdp / "memory"
            tdp_mem.mkdir()
            _seed_fast_conversation(tdp)
            hits = _search_fast_conversation(
                phrase="hemorrhage",
                repo_root=tdp,
                top_n=10,
            )
            # User row also contains 'hemorrhage' but is excluded
            # by the role='maez' filter — that's the point.
            self.assertEqual(len(hits), 1)
            self.assertIn("journal", hits[0].snippet.lower())


class TestLivedEpisodesSearch(unittest.TestCase):
    def test_finds_in_title_or_summary(self):
        from scripts.verify_self_claim import _search_lived_episodes

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "memory").mkdir()
            _seed_lived_episodes(tdp)
            hits = _search_lived_episodes(
                phrase="hemorrhage",
                repo_root=tdp,
                top_n=10,
            )
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].store, "lived_episodes")
            self.assertIn(
                "first_person",
                hits[0].extra["memory_voice"],
            )


class TestWonderingsSearch(unittest.TestCase):
    def test_finds_in_question(self):
        from scripts.verify_self_claim import _search_wonderings

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "memory").mkdir()
            _seed_wonderings(tdp)
            hits = _search_wonderings(
                phrase="hemorrhage",
                repo_root=tdp,
                top_n=10,
            )
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].store, "wonderings")


# ── aggregator ──────────────────────────────────────────────────


class TestVerifyPhraseAggregator(unittest.TestCase):
    def test_aggregates_across_stores(self):
        from scripts.verify_self_claim import verify_phrase

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "memory").mkdir()
            _seed_private_thoughts(tdp)
            _seed_fast_conversation(tdp)
            _seed_lived_episodes(tdp)
            _seed_wonderings(tdp)
            hits = verify_phrase(
                "hemorrhage",
                repo_root=tdp,
                # exclude chroma — needs MemoryManager init + real
                # data. The store-level functions are tested above;
                # the aggregator only orchestrates.
                stores=[
                    "private_thoughts",
                    "fast_conversation",
                    "lived_episodes",
                    "wonderings",
                ],
                top_n=10,
                **_VERIFY_UNSEAL_ARGS,
            )
            stores = sorted({h.store for h in hits})
            self.assertEqual(
                stores,
                [
                    "fast_conversation",
                    "lived_episodes",
                    "private_thoughts",
                    "wonderings",
                ],
            )
            # 1 hit per store in the fixtures.
            self.assertEqual(len(hits), 4)

    def test_empty_phrase_returns_empty(self):
        from scripts.verify_self_claim import verify_phrase

        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                verify_phrase("", repo_root=Path(td), stores=[]),
                [],
            )

    def test_unknown_store_silently_ignored(self):
        from scripts.verify_self_claim import verify_phrase

        with tempfile.TemporaryDirectory() as td:
            hits = verify_phrase(
                "x",
                repo_root=Path(td),
                stores=["bogus"],
            )
            self.assertEqual(hits, [])


# ── excerpt + CLI ───────────────────────────────────────────────


class TestExcerpt(unittest.TestCase):
    def test_centred_window(self):
        from scripts.verify_self_claim import _excerpt

        text = "a" * 100 + " hemorrhage " + "b" * 100
        out = _excerpt(text, "hemorrhage", window=40)
        self.assertIn("hemorrhage", out)
        self.assertLessEqual(len(out), 80)


class TestCli(unittest.TestCase):
    def test_main_runs_clean_with_no_hits(self):
        from scripts.verify_self_claim import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "memory").mkdir()
            # All searchers return empty against an empty repo_root.
            # Force the CLI to use this empty root by patching _REPO
            # through verify_phrase — easiest via mocking sys.path
            # and the module-level constant.
            from scripts import verify_self_claim as vsc

            with (
                mock.patch.object(vsc, "_REPO", tdp),
                mock.patch.object(sys, "stdout", io.StringIO()) as out,
                mock.patch.object(sys, "stderr", io.StringIO()),
            ):
                rc = main(
                    [
                        "phrase-that-doesnt-exist",
                        "--store",
                        "private_thoughts",
                        "--store",
                        "fast_conversation",
                        "--actor",
                        "test-operator",
                        "--s7-receipt-ref",
                        "s7:test",
                        "--reason",
                        "unit test diagnostic",
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertIn("0 hit(s)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
