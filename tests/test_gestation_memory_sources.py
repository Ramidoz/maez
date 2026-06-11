import hashlib
import json
import sqlite3
import subprocess
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution import gestation_memory as gm

REPO = Path(__file__).resolve().parents[1]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DocSourceTests(unittest.TestCase):
    def setUp(self):
        self.path = "docs/superpowers/specs/2026-06-10-gestation-memory-v0-design.md"
        self.commit = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        content = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{self.commit}:{self.path}"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout
        self.excerpt = next(
            line for line in content.splitlines() if "baby book" in line
        )

    def test_valid_doc_source_resolves(self):
        src = {
            "kind": "doc",
            "ref": self.path,
            "commit": self.commit,
            "excerpt_hash": _sha(self.excerpt),
        }
        ok, _ = gm.validate_source(src, repo_root=REPO, excerpt=self.excerpt)
        self.assertTrue(ok)

    def test_doc_source_rejects_mutable_commit_name(self):
        src = {
            "kind": "doc",
            "ref": self.path,
            "commit": "HEAD",
            "excerpt_hash": _sha(self.excerpt),
        }
        ok, reason = gm.validate_source(src, repo_root=REPO, excerpt=self.excerpt)
        self.assertFalse(ok)
        self.assertIn("full commit", reason)

    def test_doc_excerpt_hash_mismatch_rejected(self):
        src = {
            "kind": "doc",
            "ref": self.path,
            "commit": self.commit,
            "excerpt_hash": _sha("a line that is not in the file"),
        }
        ok, reason = gm.validate_source(
            src, repo_root=REPO, excerpt="a line that is not in the file"
        )
        self.assertFalse(ok)
        self.assertIn("excerpt", reason)

    def test_commit_source_resolves(self):
        src = {"kind": "commit", "ref": self.commit}
        ok, _ = gm.validate_source(src, repo_root=REPO)
        self.assertTrue(ok)

    def test_commit_source_rejects_mutable_ref(self):
        ok, reason = gm.validate_source({"kind": "commit", "ref": "HEAD"}, repo_root=REPO)
        self.assertFalse(ok)
        self.assertIn("full commit", reason)

    def test_bad_commit_rejected(self):
        ok, _ = gm.validate_source(
            {"kind": "commit", "ref": "0" * 40}, repo_root=REPO
        )
        self.assertFalse(ok)

    def test_witness_note_is_not_structural(self):
        self.assertFalse(
            gm.is_structural({"kind": "witness_note", "ref": "I saw it"})
        )
        self.assertTrue(gm.is_structural({"kind": "commit", "ref": self.commit}))


class LedgerRowHashTests(unittest.TestCase):
    def test_canonical_row_hash_is_byte_defined(self):
        row = {
            "event_id": 7,
            "ts": 1.5,
            "event_type": "restart",
            "continuity_id": "c1",
            "parent_continuity_id": None,
            "severity": "info",
            "reason": "ok",
            "evidence_json": '{"b":2,"a":1}',
            "fingerprint_json": '{"z":9}',
        }
        h = gm.canonical_ledger_row_hash(row)
        obj = {
            "event_id": 7,
            "ts": 1.5,
            "event_type": "restart",
            "continuity_id": "c1",
            "parent_continuity_id": None,
            "severity": "info",
            "reason": "ok",
            "evidence": {"a": 1, "b": 2},
            "fingerprint": {"z": 9},
        }
        expected = hashlib.sha256(
            json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(h, expected)

    def test_canonical_hash_rejects_missing_column(self):
        row = {
            "event_id": 7,
            "ts": 1.5,
            "event_type": "restart",
            "continuity_id": "c1",
            "parent_continuity_id": None,
            "severity": "info",
            "reason": "ok",
            "evidence_json": "{}",
        }
        with self.assertRaises(ValueError):
            gm.canonical_ledger_row_hash(row)

    def test_canonical_hash_requires_json_objects(self):
        row = {
            "event_id": 7,
            "ts": 1.5,
            "event_type": "restart",
            "continuity_id": "c1",
            "parent_continuity_id": None,
            "severity": "info",
            "reason": "ok",
            "evidence_json": "[]",
            "fingerprint_json": "{}",
        }
        with self.assertRaises(ValueError):
            gm.canonical_ledger_row_hash(row)


class LedgerRowSourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "identity_ledger.db"
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "CREATE TABLE identity_ledger ("
                "event_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "ts REAL NOT NULL, event_type TEXT NOT NULL, "
                "continuity_id TEXT NOT NULL, parent_continuity_id TEXT, "
                "severity TEXT NOT NULL, reason TEXT NOT NULL, "
                "evidence_json TEXT NOT NULL, fingerprint_json TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO identity_ledger "
                "(event_id, ts, event_type, continuity_id, parent_continuity_id, "
                "severity, reason, evidence_json, fingerprint_json) "
                "VALUES (7, 1.5, 'gestation_boot', 'c1', NULL, 'same', 'seed', "
                "'{\"b\":2,\"a\":1}', '{\"z\":9}')"
            )
            conn.commit()

    def tearDown(self):
        self._tmp.cleanup()

    def _source(self, event_id=7, digest=None):
        row = {
            "event_id": 7,
            "ts": 1.5,
            "event_type": "gestation_boot",
            "continuity_id": "c1",
            "parent_continuity_id": None,
            "severity": "same",
            "reason": "seed",
            "evidence_json": '{"b":2,"a":1}',
            "fingerprint_json": '{"z":9}',
        }
        return {
            "kind": "ledger_row",
            "ref": event_id,
            "excerpt_hash": digest or gm.canonical_ledger_row_hash(row),
        }

    def test_valid_ledger_row_source_resolves_read_only(self):
        ok, reason = gm.validate_source(
            self._source(), repo_root=REPO, ledger_db=self.db
        )
        self.assertTrue(ok, reason)

    def test_ledger_row_wrong_hash_rejected(self):
        ok, reason = gm.validate_source(
            self._source(digest="deadbeef"), repo_root=REPO, ledger_db=self.db
        )
        self.assertFalse(ok)
        self.assertIn("hash", reason)

    def test_ledger_row_missing_row_rejected(self):
        ok, reason = gm.validate_source(
            self._source(event_id=99), repo_root=REPO, ledger_db=self.db
        )
        self.assertFalse(ok)
        self.assertIn("not found", reason)

    def test_nonexistent_ledger_db_is_not_created(self):
        missing = Path(self._tmp.name) / "missing.db"
        ok, reason = gm.validate_source(
            self._source(), repo_root=REPO, ledger_db=missing
        )
        self.assertFalse(ok)
        self.assertIn("source validation error", reason)
        self.assertFalse(missing.exists())
