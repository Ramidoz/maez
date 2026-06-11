import hashlib
import json
import subprocess
import unittest
from pathlib import Path

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
