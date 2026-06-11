import sqlite3
import hashlib
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution.gestation_memory import GestationMemory

REPO = Path(__file__).resolve().parents[1]


def _doc_source():
    path = "docs/superpowers/specs/2026-06-10-gestation-memory-v0-design.md"
    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    content = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{commit}:{path}"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    excerpt = next(line for line in content.splitlines() if "baby book" in line)
    h = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    return {"kind": "doc", "ref": path, "commit": commit, "excerpt_hash": h}, excerpt


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "g.db"
        self.gm = GestationMemory(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tables_exist(self):
        with sqlite3.connect(self.db) as c:
            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("gestation_claims", names)
        self.assertIn("gestation_claim_supersessions", names)

    def test_gestation_claims_update_is_aborted(self):
        with sqlite3.connect(self.db) as c:
            c.execute(
                "INSERT INTO gestation_claims "
                "(created_at, claim_text, claim_kind, type, confidence, scar, "
                " sources_json, observed_by, metadata_json) "
                "VALUES (1.0,'x','fact','milestone','witnessed',0,'[]','owner','{}')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "UPDATE gestation_claims SET claim_text='y' WHERE claim_id=1"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM gestation_claims WHERE claim_id=1")

    def test_supersessions_update_is_aborted(self):
        with sqlite3.connect(self.db) as c:
            c.execute(
                "INSERT INTO gestation_claim_supersessions "
                "(old_claim_id, replacement_claim_id, created_at) VALUES (1,2,1.0)"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "UPDATE gestation_claim_supersessions "
                    "SET old_claim_id=9 WHERE supersession_id=1"
                )


class RecordClaimTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.excerpt = _doc_source()

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_fact_stored(self):
        claim = self.gm.record_claim(
            claim_text="The spec calls this a baby book made from receipts.",
            claim_kind="fact",
            type="milestone",
            confidence="documented",
            sources=[self.src],
            source_excerpts={0: self.excerpt},
            observed_by="claude",
        )
        self.assertEqual(self.gm.get(claim.claim_id).claim_text, claim.claim_text)

    def test_witness_note_only_rejected(self):
        with self.assertRaises(ValueError):
            self.gm.record_claim(
                claim_text="x",
                claim_kind="fact",
                type="milestone",
                confidence="witnessed",
                sources=[{"kind": "witness_note", "ref": "I saw it"}],
                observed_by="claude",
            )

    def test_inferred_fact_rejected(self):
        with self.assertRaises(ValueError):
            self.gm.record_claim(
                claim_text="x",
                claim_kind="fact",
                type="milestone",
                confidence="inferred",
                sources=[self.src],
                source_excerpts={0: self.excerpt},
                observed_by="claude",
            )

    def test_inferred_interpretation_accepted(self):
        claim = self.gm.record_claim(
            claim_text="Maez learned to try without declaring victory.",
            claim_kind="interpretation",
            type="milestone",
            confidence="inferred",
            sources=[self.src],
            source_excerpts={0: self.excerpt},
            observed_by="claude",
        )
        self.assertEqual(claim.confidence, "inferred")

    def test_doc_excerpt_mismatch_rejected(self):
        bad = dict(self.src, excerpt_hash="deadbeef")
        with self.assertRaises(ValueError):
            self.gm.record_claim(
                claim_text="x",
                claim_kind="fact",
                type="milestone",
                confidence="documented",
                sources=[bad],
                source_excerpts={0: self.excerpt},
                observed_by="claude",
            )
