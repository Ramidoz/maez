# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""T4 — census conformance, both directions (S1 protocol §5, command §10).

Written before core/memory/s1_census.py exists. The contract is the
protocol's, not mine:

    python3 -m core.memory.s1_census --repo . \
        --expected docs/superpowers/witness/theme2-s1-census.json

walks memory/ core/ daemon/ skills/ cli/ (excluding tests/ docs/ logs/) with
`ast.parse`, collects every writer of a `memory_phase` key/column and every
reader of `birth_event_turn_id`, normalizes each hit to `path::qualname`
(falling back to `path::@line` at module level), sorts, and diffs exactly
against the expected JSON. Exit 0 on equality; exit 1 naming every
asymmetric difference.

§5 pins two controls, and they are the point of the test — a census that
cannot fail in both directions is decoration:

    seeded-unexpected: a new writer appears -> FAIL, naming it
    missing-expected: an entry is deleted from the JSON -> FAIL, naming it
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED_PATH = REPO / "core" / "_s1_census_seed.py"

# Literal bytes pinned by protocol §9.
SEED_BYTES = '''import sqlite3
PHASE = {"memory_phase": "gestation"}
def probe(p):
    return sqlite3.connect(p).execute(
        "SELECT value FROM meta WHERE key='birth_event_turn_id'").fetchone()
'''


def run_census(expected: Path, repo: Path = REPO):
    return subprocess.run(
        [sys.executable, "-m", "core.memory.s1_census",
         "--repo", str(repo), "--expected", str(expected)],
        capture_output=True, text=True, cwd=str(repo),
    )


class CensusContract(unittest.TestCase):
    """The pinned command exists and behaves as §10 specifies."""

    def test_module_is_invocable_as_pinned(self):
        r = run_census(REPO / "docs/superpowers/witness/theme2-s1-census.json")
        self.assertNotIn("No module named", r.stderr,
                         "the pinned invocation must work verbatim")
        self.assertIn(r.returncode, (0, 1),
                      f"expected 0 or 1, got {r.returncode}: {r.stderr[:300]}")

    def test_emits_json_when_asked(self):
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(REPO), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(r.returncode, 0, r.stderr[:400])
        payload = json.loads(r.stdout)
        for key in ("memory_phase_writers", "birth_meta_readers"):
            self.assertIn(key, payload)
            self.assertEqual(payload[key], sorted(payload[key]),
                             f"{key} must be sorted")

    def test_agrees_with_itself(self):
        """Emit, then diff against what was emitted: must be exit 0.

        This is the fixed point. Without it a census could be internally
        inconsistent and every other assertion would be measuring noise.
        """
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(REPO), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as fh:
            fh.write(r.stdout)
            tmp = Path(fh.name)
        try:
            again = run_census(tmp)
            self.assertEqual(again.returncode, 0,
                             f"census disagrees with its own output:\n"
                             f"{again.stdout[:600]}")
        finally:
            tmp.unlink()


def _writable_clone() -> Path:
    """Copy the walked code roots into a scratch tree.

    Gate round 22 item 7: the seeded-unexpected control writes
    core/_s1_census_seed.py, but the airlock mounts the checkout read-only —
    so the two-direction T4 controls could never run where the protocol says
    T4 runs. The census takes --repo; seeding happens in a writable CLONE of
    the code roots (code only, no stores), preserving the protocol's literal
    seed path relative to the repo root.
    """
    import shutil
    clone = Path(tempfile.mkdtemp(prefix="t4clone_"))
    ignore = shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".git", "db", "*.db", "*.sqlite3",
        "backups", "node_modules")
    for root in ("memory", "core", "daemon", "skills", "cli", "scripts"):
        src = REPO / root
        if src.is_dir():
            shutil.copytree(src, clone / root, ignore=ignore,
                            dirs_exist_ok=True)
    return clone


class AirlockableControls(unittest.TestCase):
    """§5's two controls, runnable under a read-only checkout."""

    @classmethod
    def setUpClass(cls):
        cls.clone = _writable_clone()
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(cls.clone), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        assert r.returncode == 0, r.stderr[:400]
        cls.truth = json.loads(r.stdout)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.clone, ignore_errors=True)

    def _expected(self, payload) -> Path:
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, fh); fh.close()
        return Path(fh.name)

    def test_clone_census_matches_repo_census(self):
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(REPO), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        repo_truth = json.loads(r.stdout)
        for k in ("memory_phase_writers", "birth_meta_readers"):
            self.assertEqual(self.truth[k], repo_truth[k],
                             f"{k}: the clone is not a faithful census "
                             f"surface")

    def test_seeded_unexpected_fails_in_the_clone(self):
        seed = self.clone / "core" / "_s1_census_seed.py"
        seed.write_text(SEED_BYTES)
        try:
            expected = self._expected(self.truth)
            r = subprocess.run(
                [sys.executable, "-m", "core.memory.s1_census",
                 "--repo", str(self.clone), "--expected", str(expected)],
                capture_output=True, text=True, cwd=str(REPO))
            self.assertEqual(r.returncode, 1)
            self.assertIn("_s1_census_seed", r.stdout + r.stderr)
            expected.unlink()
        finally:
            seed.unlink(missing_ok=True)

    def test_missing_expected_fails_in_the_clone(self):
        shrunk = json.loads(json.dumps(self.truth))
        dropped = shrunk["memory_phase_writers"].pop()
        expected = self._expected(shrunk)
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(self.clone), "--expected", str(expected)],
            capture_output=True, text=True, cwd=str(REPO))
        expected.unlink()
        self.assertEqual(r.returncode, 1)
        self.assertIn(dropped.split("::")[0], r.stdout + r.stderr)


class ProtocolControls(unittest.TestCase):
    """§5's two controls. The census must fail in BOTH directions."""

    def setUp(self):
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(REPO), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        self.truth = json.loads(r.stdout) if r.returncode == 0 else None

    def _write(self, payload) -> Path:
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, fh)
        fh.close()
        return Path(fh.name)

    def test_seeded_unexpected_writer_fails_and_is_named(self):
        self.assertIsNotNone(self.truth)
        expected = self._write(self.truth)
        SEED_PATH.write_text(SEED_BYTES)
        try:
            r = run_census(expected)
            self.assertEqual(r.returncode, 1,
                             "a new memory_phase writer must fail the census")
            self.assertIn("_s1_census_seed", r.stdout + r.stderr,
                          "the census must NAME the unexpected construct")
        finally:
            SEED_PATH.unlink(missing_ok=True)
            expected.unlink()

    def test_missing_expected_entry_fails_and_is_named(self):
        self.assertIsNotNone(self.truth)
        shrunk = json.loads(json.dumps(self.truth))
        dropped = shrunk["memory_phase_writers"].pop()
        expected = self._write(shrunk)
        try:
            r = run_census(expected)
            self.assertEqual(r.returncode, 1,
                             "an entry present in code but absent from the "
                             "expectation must fail")
            self.assertIn(dropped.split("::")[0], r.stdout + r.stderr,
                          "the census must NAME the difference")
        finally:
            expected.unlink()

    def test_the_seed_file_is_removed_afterwards(self):
        self.assertFalse(SEED_PATH.exists(),
                         "the seeded control file leaked into the tree")


class Normalization(unittest.TestCase):
    """`path::qualname`, falling back to `path::@line` at module level."""

    def test_hits_are_path_qualname_shaped(self):
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(REPO), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        payload = json.loads(r.stdout)
        for entry in payload["memory_phase_writers"] + payload["birth_meta_readers"]:
            self.assertIn("::", entry, f"unnormalized entry: {entry}")
            path, qual = entry.split("::", 1)
            self.assertTrue(path.endswith(".py"), entry)
            self.assertTrue(qual, f"empty qualname in {entry}")

    def test_excluded_roots_are_not_walked(self):
        r = subprocess.run(
            [sys.executable, "-m", "core.memory.s1_census",
             "--repo", str(REPO), "--emit"],
            capture_output=True, text=True, cwd=str(REPO))
        payload = json.loads(r.stdout)
        for entry in payload["memory_phase_writers"] + payload["birth_meta_readers"]:
            head = entry.split("/", 1)[0]
            self.assertNotIn(head, ("tests", "docs", "logs"),
                             f"walked an excluded root: {entry}")


if __name__ == "__main__":
    unittest.main()
