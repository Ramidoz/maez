# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Owner-curated alias seeding tests (Step 5g).

Reads a YAML file describing canonical entities + aliases and
upserts them into the Step-5e EntityIndex. No mentions are
created — alias seeding adds the resolution layer, not evidence.
No LLM, no network, no subprocess.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


_SAMPLE_YAML = textwrap.dedent(
    """
    entities:
      - canonical_name: "Maya Ananthan"
        kind: "person"
        aliases: ["Maya"]
        notes: "test fixture"
      - canonical_name: "Maya Anjali"
        kind: "person"
        aliases: ["Maya", "Anjali"]
      - canonical_name: "Track A"
        kind: "project"
        aliases: ["Track A readiness"]
    """
).strip()


def _write_yaml(td: Path, body: str = _SAMPLE_YAML) -> Path:
    p = td / "aliases.yaml"
    p.write_text(body)
    return p


def _fresh_index(td: Path):
    from core.memory.entity_index import EntityIndex
    return EntityIndex(td / "ix.db")


# ── schema validation ────────────────────────────────────────────


class TestLoadSeedFile(unittest.TestCase):
    def test_loads_well_formed_file(self):
        from core.memory.entity_alias_seed import load_seed_file

        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td))
            entries = load_seed_file(path)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0].canonical_name, "Maya Ananthan")
            self.assertEqual(entries[0].kind, "person")
            self.assertEqual(list(entries[0].aliases), ["Maya"])
            self.assertEqual(entries[2].kind, "project")

    def test_missing_canonical_name_fails(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = textwrap.dedent("""
        entities:
          - kind: "person"
            aliases: ["x"]
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_missing_kind_fails(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = textwrap.dedent("""
        entities:
          - canonical_name: "Foo Bar"
            aliases: ["foo"]
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_non_string_alias_fails(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = textwrap.dedent("""
        entities:
          - canonical_name: "Foo"
            kind: "person"
            aliases: [42]
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_empty_alias_string_fails(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = textwrap.dedent("""
        entities:
          - canonical_name: "Foo"
            kind: "person"
            aliases: ["", "ok"]
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_duplicate_canonical_in_file_errors(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = textwrap.dedent("""
        entities:
          - canonical_name: "Foo Bar"
            kind: "person"
            aliases: ["foo"]
          - canonical_name: "Foo Bar"
            kind: "person"
            aliases: ["bar"]
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_invalid_yaml_fails_cleanly(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = "entities: [\n  not: valid:: yaml: ::"
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_top_level_must_be_mapping(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = "- just\n- a list"
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)

    def test_missing_entities_key_fails(self):
        from core.memory.entity_alias_seed import (
            SeedFileError, load_seed_file,
        )

        body = "other: thing"
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SeedFileError):
                load_seed_file(path)


# ── seed: dry-run ─────────────────────────────────────────────────


class TestSeedDryRun(unittest.TestCase):
    def test_dry_run_writes_nothing_but_reports_counts(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            report = seed_aliases(ix=ix, entries=entries)  # write=False
            with ix._connect() as con:
                n_entities = con.execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0]
            self.assertEqual(
                n_entities,
                0,
            )
            with ix._connect() as con:
                n_aliases = con.execute(
                    "SELECT COUNT(*) FROM aliases"
                ).fetchone()[0]
            self.assertEqual(
                n_aliases,
                0,
            )
            self.assertEqual(report.entities_seen, 3)
            self.assertEqual(report.entities_created, 3)
            self.assertEqual(report.entities_existing, 0)
            self.assertGreater(report.aliases_added, 0)
            self.assertEqual(report.aliases_existing, 0)


# ── seed: write + idempotent ─────────────────────────────────────


class TestSeedWrite(unittest.TestCase):
    def test_write_creates_entities_and_aliases(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            seed_aliases(ix=ix, entries=entries, write=True)

            with ix._connect() as con:
                ent_rows = con.execute(
                    "SELECT canonical_name, kind FROM entities"
                ).fetchall()
            self.assertEqual(len(ent_rows), 3)
            kinds = sorted(r["kind"] for r in ent_rows)
            self.assertEqual(kinds, ["person", "person", "project"])

            with ix._connect() as con:
                ali_rows = con.execute(
                    "SELECT alias, normalized_alias FROM aliases"
                ).fetchall()
            self.assertGreater(len(ali_rows), 0)
            # 'Maya' present twice (one per entity).
            mayas = [r for r in ali_rows if r["normalized_alias"] == "maya"]
            self.assertEqual(len(mayas), 2)

    def test_rerun_is_idempotent(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            seed_aliases(ix=ix, entries=entries, write=True)
            with ix._connect() as con:
                n_ent = con.execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0]
            with ix._connect() as con:
                n_ali = con.execute(
                    "SELECT COUNT(*) FROM aliases"
                ).fetchone()[0]
            r2 = seed_aliases(ix=ix, entries=entries, write=True)
            with ix._connect() as con:
                n_ent_after = con.execute(
                    "SELECT COUNT(*) FROM entities"
                ).fetchone()[0]
            self.assertEqual(
                n_ent_after, n_ent,
            )
            with ix._connect() as con:
                n_ali_after = con.execute(
                    "SELECT COUNT(*) FROM aliases"
                ).fetchone()[0]
            self.assertEqual(
                n_ali_after, n_ali,
            )
            self.assertEqual(r2.entities_created, 0)
            self.assertEqual(r2.entities_existing, 3)
            self.assertEqual(r2.aliases_added, 0)
            self.assertGreater(r2.aliases_existing, 0)


# ── ambiguity preserved through find_entities ─────────────────────


class TestAmbiguousAliasSplitConfidence(unittest.TestCase):
    def test_two_entities_share_alias_split_confidence(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            seed_aliases(ix=ix, entries=entries, write=True)
            matches = ix.find_entities("Maya")
            self.assertEqual(len(matches), 2)
            for m in matches:
                self.assertAlmostEqual(m.confidence, 0.5, places=4)

    def test_unique_alias_full_confidence(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            seed_aliases(ix=ix, entries=entries, write=True)
            matches = ix.find_entities("Anjali")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].confidence, 1.0)


# ── ambiguous_aliases_after_seed metric ──────────────────────────


class TestAmbiguousAliasesMetric(unittest.TestCase):
    def test_metric_counts_aliases_shared_by_2plus_entities(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            report = seed_aliases(ix=ix, entries=entries, write=True)
            # Only "Maya" is shared (Maya Ananthan + Maya Anjali).
            self.assertEqual(report.ambiguous_aliases_after_seed, 1)


# ── example file is not private ──────────────────────────────────


class TestExampleFileIsNotPrivate(unittest.TestCase):
    """The committed example file must not contain the owner's
    actual name, repo handle, or other private signal — those go
    in the gitignored config/entity_aliases.local.yaml."""

    EXAMPLE_PATH = _REPO / "docs" / "entity_aliases.example.yaml"
    PRIVATE_TOKENS = (
        "rohit", "ananthan", "ramidoz", "alienware",
    )

    def test_example_file_exists(self):
        self.assertTrue(self.EXAMPLE_PATH.is_file())

    def test_example_file_loads_clean(self):
        from core.memory.entity_alias_seed import load_seed_file
        entries = load_seed_file(self.EXAMPLE_PATH)
        self.assertGreater(len(entries), 0)

    def test_example_file_has_no_private_names(self):
        text = self.EXAMPLE_PATH.read_text().lower()
        for tok in self.PRIVATE_TOKENS:
            self.assertNotIn(
                tok, text,
                f"example alias file leaked private token {tok!r}",
            )


# ── safety: no subprocess / no network ───────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 subprocess, "Popen",
                 side_effect=AssertionError("no Popen"),
             ):
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            seed_aliases(ix=ix, entries=entries, write=True)

    def test_no_network(self):
        from core.memory.entity_alias_seed import (
            load_seed_file, seed_aliases,
        )

        def boom(*a, **kw):
            raise AssertionError("alias seed must not open sockets")

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(socket, "socket", boom):
            tdp = Path(td)
            entries = load_seed_file(_write_yaml(tdp))
            ix = _fresh_index(tdp)
            seed_aliases(ix=ix, entries=entries, write=True)


# ── gitignore covers the local file ───────────────────────────────


class TestGitignoreCoversLocalAliasFile(unittest.TestCase):
    def test_local_alias_path_is_gitignored(self):
        gi = _REPO / ".gitignore"
        self.assertTrue(gi.is_file())
        text = gi.read_text()
        self.assertIn("config/entity_aliases.local.yaml", text)


if __name__ == "__main__":
    unittest.main()
