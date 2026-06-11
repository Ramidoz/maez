import sqlite3
import hashlib
import subprocess
import unittest
from contextlib import closing
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
        with closing(sqlite3.connect(self.db)) as c:
            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("gestation_claims", names)
        self.assertIn("gestation_claim_supersessions", names)

    def test_gestation_claims_update_is_aborted(self):
        with closing(sqlite3.connect(self.db)) as c:
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
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "INSERT OR REPLACE INTO gestation_claims "
                    "(claim_id, created_at, claim_text, claim_kind, type, "
                    "confidence, scar, sources_json, observed_by, metadata_json) "
                    "VALUES (1,1.0,'z','fact','milestone','witnessed',0,'[]','owner','{}')"
                )

    def test_supersessions_update_is_aborted(self):
        with closing(sqlite3.connect(self.db)) as c:
            c.execute(
                "INSERT INTO gestation_claim_supersessions "
                "(old_claim_id, replacement_claim_id, created_at) VALUES (1,2,1.0)"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "UPDATE gestation_claim_supersessions "
                    "SET old_claim_id=9 WHERE supersession_id=1"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute(
                    "INSERT OR REPLACE INTO gestation_claim_supersessions "
                    "(supersession_id, old_claim_id, replacement_claim_id, created_at) "
                    "VALUES (1,9,2,1.0)"
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


class SupersedeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.excerpt = _doc_source()

    def tearDown(self):
        self._tmp.cleanup()

    def _claim(self, text):
        return self.gm.record_claim(
            claim_text=text,
            claim_kind="fact",
            type="milestone",
            confidence="documented",
            sources=[self.src],
            source_excerpts={0: self.excerpt},
            observed_by="claude",
        )

    def test_supersede_appends_edge_and_leaves_old_row_byte_identical(self):
        old = self._claim("We believed the bridge wrote the ledger.")
        before = self.gm.get(old.claim_id)
        new = self._claim("Corrected: the bridge writes no ledger.")
        self.gm.supersede(old.claim_id, new.claim_id)
        after = self.gm.get(old.claim_id)
        self.assertEqual(before, after)
        active_ids = {claim.claim_id for claim in self.gm.list_active()}
        self.assertNotIn(old.claim_id, active_ids)
        self.assertIn(new.claim_id, active_ids)

    def test_both_claims_persist_after_supersede(self):
        old = self._claim("old")
        new = self._claim("new")
        self.gm.supersede(old.claim_id, new.claim_id)
        self.assertIsNotNone(self.gm.get(old.claim_id))
        self.assertIsNotNone(self.gm.get(new.claim_id))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.excerpt = _doc_source()

    def tearDown(self):
        self._tmp.cleanup()

    def _claim(self, text, kind, typ, conf, scar=False):
        return self.gm.record_claim(
            claim_text=text,
            claim_kind=kind,
            type=typ,
            confidence=conf,
            sources=[self.src],
            source_excerpts={0: self.excerpt},
            observed_by="claude",
            scar=scar,
        )

    def test_facts_and_interpretations_in_separate_sections(self):
        self._claim("A fact happened.", "fact", "milestone", "documented")
        self._claim("A meaning we drew.", "interpretation", "milestone", "inferred")
        self._claim(
            "It went wrong then was fixed.",
            "fact",
            "no_go",
            "documented",
            scar=True,
        )
        out = self.gm.render()
        self.assertIn("What happened", out)
        self.assertIn("What went wrong", out)
        self.assertIn("Interpretations", out)
        self.assertLess(out.index("A fact happened."), out.index("Interpretations"))
        self.assertLess(out.index("Interpretations"), out.index("A meaning we drew."))
        self.assertLess(
            out.index("What went wrong"), out.index("It went wrong then was fixed.")
        )

    def test_every_rendered_claim_carries_a_source(self):
        self._claim("A fact happened.", "fact", "milestone", "documented")
        out = self.gm.render()
        self.assertIn("2026-06-10-gestation-memory-v0-design.md", out)


class CliTests(unittest.TestCase):
    def test_render_subcommand_runs_on_empty_db(self):
        from core.evolution import gestation_memory

        with TemporaryDirectory() as td:
            rc = gestation_memory.main(["render", "--db", str(Path(td) / "g.db")])
            self.assertEqual(rc, 0)
