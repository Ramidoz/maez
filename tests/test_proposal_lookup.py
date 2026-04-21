# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.proposal_lookup — the SQLite-backed structured
lookup that replaces `grep -r proposal 25 /home/rohit/maez/` with a
direct query against the two proposal stores.

Observed trigger 2026-04-20: Maez received a stale-proposal reminder
for candidate #25, the user asked 'what is proposal #25?', and the
brain_loop grepped the filesystem (hit vocab.json noise). This tool
gives the planner a dedicated lookup path."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


def _make_evolution_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            state TEXT,
            weakness_description TEXT,
            target_file TEXT,
            diff_text TEXT,
            justification TEXT,
            cognition_evidence TEXT,
            rejection_reason TEXT,
            rollback_reason TEXT,
            rollback_layer TEXT,
            cooldown_key TEXT,
            pre_patch_hash TEXT,
            post_patch_hash TEXT,
            backup_path TEXT,
            pre_patch_score_avg REAL,
            post_patch_score_avg REAL,
            created_at TEXT,
            validated_at TEXT,
            applied_at TEXT,
            resolved_at TEXT
        )
    """)
    for r in rows:
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        conn.execute(
            f"INSERT INTO candidates ({cols}) VALUES ({placeholders})",
            tuple(r.values()),
        )
    conn.commit()
    conn.close()


def _make_dream_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE dream_proposals (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            insight TEXT,
            status TEXT,
            applied_at TEXT,
            reject_reason TEXT,
            proposal_type TEXT,
            target_section TEXT,
            proposed_new_body TEXT,
            unified_diff TEXT
        )
    """)
    for r in rows:
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        conn.execute(
            f"INSERT INTO dream_proposals ({cols}) VALUES ({placeholders})",
            tuple(r.values()),
        )
    conn.commit()
    conn.close()


class LookupReturnsEvolutionCandidate(unittest.TestCase):
    def test_found_in_evolution_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [{
                "id": 25,
                "state": "validated",
                "target_file": "core/cognition_quality.py",
                "weakness_description": "topic concentration on browser_usage",
                "diff_text": "--- a/core/cognition_quality.py\n+++ b/core/cognition_quality.py\n@@ -70,7 +70,7 @@\n-POLICY_EXPLORATORY_THRESHOLD = 0.7\n+POLICY_EXPLORATORY_THRESHOLD = 0.6",
                "created_at": "2026-04-19T19:14:30",
            }])
            _make_dream_db(dream_path, [])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(25)

            self.assertTrue(result["found"], f"expected found=True; got {result}")
            self.assertIn("evolution_candidates", result["sources"])
            summary = result["summary"]
            self.assertIn("25", summary)
            self.assertIn("validated", summary)
            self.assertIn("core/cognition_quality.py", summary)
            self.assertIn("POLICY_EXPLORATORY_THRESHOLD", summary)


class LookupReturnsDreamProposal(unittest.TestCase):
    def test_found_in_dream_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [])
            _make_dream_db(dream_path, [{
                "id": 7,
                "created_at": "2026-04-18T09:00:00",
                "insight": "I've been quiet on weekends — consider gentler tone.",
                "status": "pending",
                "proposal_type": "soul_note",
                "target_section": "voice.weekend",
            }])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(7)

            self.assertTrue(result["found"])
            self.assertIn("dream_proposals", result["sources"])
            self.assertIn("7", result["summary"])
            self.assertIn("gentler", result["summary"])


class LookupHandlesMissingId(unittest.TestCase):
    def test_id_absent_from_both_dbs(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [])
            _make_dream_db(dream_path, [])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(999)

            self.assertFalse(result["found"])
            self.assertEqual(result["sources"], [])
            self.assertIn("not found", result["summary"].lower())


class LookupFailsOpenOnMissingDb(unittest.TestCase):
    def test_missing_db_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "nope-evo.db")
            dream_path = os.path.join(tmp, "nope-dream.db")

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(25)

            self.assertFalse(result["found"])
            self.assertIn("not found", result["summary"].lower())


class LookupFoundInBothDbs(unittest.TestCase):
    def test_id_present_in_both_sources_reports_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [{
                "id": 3, "state": "validated",
                "target_file": "core/foo.py",
                "weakness_description": "x",
                "diff_text": "diff",
                "created_at": "2026-04-19T00:00:00",
            }])
            _make_dream_db(dream_path, [{
                "id": 3, "status": "pending",
                "insight": "something",
                "proposal_type": "soul_note",
                "target_section": "voice",
                "created_at": "2026-04-19T00:00:00",
            }])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(3)

            self.assertTrue(result["found"])
            self.assertIn("evolution_candidates", result["sources"])
            self.assertIn("dream_proposals", result["sources"])


class LookupValidatesInput(unittest.TestCase):
    def test_non_integer_id_returns_not_found(self):
        from core import proposal_lookup
        result = proposal_lookup.lookup("twenty-five")
        self.assertFalse(result["found"])
        self.assertIn("invalid", result["summary"].lower())


if __name__ == "__main__":
    unittest.main()
