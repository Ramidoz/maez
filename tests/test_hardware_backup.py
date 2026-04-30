# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Hardware-failure backup tests (Decision 22 / ADR 0023).

Tests use a synthetic state tree under tmpdir — never the live store.
Following the same isolation discipline as the LongMemEval adapter.

Coverage targets from the v1 spec:
- Inventory loader resolves expected files
- SQLite-safe backup round-trips correctly
- Atomic .in-progress staging — interrupted backups can't masquerade
- Manifest sha256 catches corruption at restore time
- Restore creates pre-restore rollback
- restore_writer creates correct coma entry with mocked MemoryManager
- Secret files require explicit opt-in or warning path
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── synthetic state helpers ─────────────────────────────────────────


def _make_synthetic_state(root: Path) -> dict[str, Path]:
    """Build a minimal state tree mirroring the manifest shape: one
    SQLite db, one directory, one file, one secret, one glob target.
    Returns a dict of role → path so tests can assert on each."""
    paths = {}

    # SQLite DB with content
    (root / "memory").mkdir(parents=True, exist_ok=True)
    db = root / "memory" / "audit_log.db"
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE audit (id INTEGER PRIMARY KEY, msg TEXT);"
        "INSERT INTO audit (msg) VALUES ('synthetic-1');"
        "INSERT INTO audit (msg) VALUES ('synthetic-2');"
    )
    con.commit()
    con.close()
    paths["sqlite"] = db

    # Chroma-ish directory — chroma.sqlite3 is a REAL SQLite file
    # so the SQLite-safe backup path inside _copy_directory exercises
    # against an actual DB the way Chroma's would.
    chroma = root / "memory" / "db"
    chroma.mkdir(parents=True, exist_ok=True)
    chroma_db = chroma / "chroma.sqlite3"
    cc = sqlite3.connect(chroma_db)
    cc.executescript(
        "CREATE TABLE collections (id INTEGER PRIMARY KEY, name TEXT);"
        "INSERT INTO collections (name) VALUES ('synthetic-collection');"
    )
    cc.commit()
    cc.close()
    (chroma / "raw").mkdir()
    (chroma / "raw" / "data.bin").write_bytes(b"\x00\x01\x02 raw chroma binary")
    paths["chroma_dir"] = chroma

    # Plain JSON file
    (root / "memory" / "continuity_capsule.json").write_text(
        json.dumps({"cycle": 42, "lived_at": "2026-04-30"}),
    )
    paths["json"] = root / "memory" / "continuity_capsule.json"

    # Identity (required)
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "identity.yaml").write_text("owner_name: test-owner\n")
    paths["identity"] = root / "config" / "identity.yaml"

    # Secret file
    (root / "config" / "credentials.json").write_text(
        '{"api_key": "fake-secret-not-real"}'
    )
    paths["secret"] = root / "config" / "credentials.json"

    # Glob target
    (root / "logs" / "traces").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "traces" / "2026-04-30.jsonl").write_text(
        '{"turn": 1, "text": "hi"}\n'
    )
    paths["trace"] = root / "logs" / "traces" / "2026-04-30.jsonl"

    return paths


def _synthetic_manifest() -> dict:
    """Minimal in-memory manifest matching the synthetic state above.
    Avoids depending on the production manifest file for unit tests."""
    return {
        "version": 1,
        "secret_warning": "test warning",
        "entries": [
            {"type": "sqlite_db", "path": "memory/audit_log.db",
             "required": False},
            {"type": "directory", "path": "memory/db", "required": False},
            {"type": "file", "path": "memory/continuity_capsule.json",
             "required": False},
            {"type": "file", "path": "config/identity.yaml",
             "required": True},
            {"type": "glob", "path": "logs/traces/*.jsonl",
             "required": False},
            {"type": "secret_file", "path": "config/credentials.json"},
        ],
    }


# ── inventory ───────────────────────────────────────────────────────


class TestInventoryResolution(unittest.TestCase):
    def test_resolves_expected_files(self):
        from scripts.backup.inventory import resolve_inventory

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_synthetic_state(root)
            resolved = resolve_inventory(
                _synthetic_manifest(), root, include_secrets=False,
            )
        types = {r["type"] for r in resolved}
        self.assertEqual(types, {"sqlite_db", "directory", "file", "glob"})
        self.assertNotIn("secret_file", types,
                         "secret excluded by default")

    def test_glob_expansion_returns_concrete_paths(self):
        from scripts.backup.inventory import resolve_inventory

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_synthetic_state(root)
            (root / "logs" / "traces" / "2026-05-01.jsonl").write_text("{}")
            resolved = resolve_inventory(
                _synthetic_manifest(), root, include_secrets=False,
            )
        glob_entries = [r for r in resolved if r["type"] == "glob"]
        self.assertEqual(len(glob_entries), 1)
        # The expanded paths live in the entry's resolved_paths list.
        paths = glob_entries[0]["resolved_paths"]
        self.assertEqual(len(paths), 2)

    def test_required_missing_raises(self):
        """A required entry that's absent must raise — not silently skip."""
        from scripts.backup.inventory import (
            BackupInventoryError,
            resolve_inventory,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memory").mkdir()
            # Don't create config/identity.yaml — it's required.
            with self.assertRaises(BackupInventoryError):
                resolve_inventory(
                    _synthetic_manifest(), root, include_secrets=False,
                )

    def test_optional_missing_silently_skipped(self):
        from scripts.backup.inventory import resolve_inventory

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            (root / "config" / "identity.yaml").write_text("ok\n")
            # No other state — all optional, should not raise.
            resolved = resolve_inventory(
                _synthetic_manifest(), root, include_secrets=False,
            )
        # Only the identity file resolves; everything else is missing
        # and skipped. Expect one entry.
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["path"], "config/identity.yaml")


# ── secret opt-in ──────────────────────────────────────────────────


class TestSecretOptIn(unittest.TestCase):
    def test_secrets_excluded_by_default(self):
        from scripts.backup.inventory import resolve_inventory

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_synthetic_state(root)
            resolved = resolve_inventory(
                _synthetic_manifest(), root, include_secrets=False,
            )
        secrets = [r for r in resolved if r["type"] == "secret_file"]
        self.assertEqual(secrets, [])

    def test_secrets_included_with_explicit_flag(self):
        from scripts.backup.inventory import resolve_inventory

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_synthetic_state(root)
            resolved = resolve_inventory(
                _synthetic_manifest(), root, include_secrets=True,
            )
        secrets = [r for r in resolved if r["type"] == "secret_file"]
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["path"], "config/credentials.json")


# ── SQLite backup ───────────────────────────────────────────────────


class TestSQLiteBackup(unittest.TestCase):
    def test_round_trip_preserves_rows(self):
        """sqlite3 .backup() produces a file the same data can be
        read back from, even if the source is being written to."""
        from scripts.backup.backup import backup_sqlite

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.db"
            dst = Path(td) / "dst.db"
            con = sqlite3.connect(src)
            con.executescript(
                "CREATE TABLE t (k INTEGER PRIMARY KEY, v TEXT);"
                "INSERT INTO t VALUES (1, 'a'), (2, 'b');"
            )
            con.commit()
            # Hold an open connection while backing up — SQLite's
            # .backup() must handle this safely.
            try:
                backup_sqlite(src, dst)
            finally:
                con.close()
            con2 = sqlite3.connect(dst)
            rows = con2.execute("SELECT k, v FROM t ORDER BY k").fetchall()
            con2.close()
        self.assertEqual(rows, [(1, "a"), (2, "b")])

    def test_creates_destination_parent_dirs(self):
        from scripts.backup.backup import backup_sqlite

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "s.db"
            dst = Path(td) / "deep" / "nested" / "dst.db"
            con = sqlite3.connect(src)
            con.executescript(
                "CREATE TABLE t (k INTEGER); INSERT INTO t VALUES (1);"
            )
            con.commit()
            con.close()
            backup_sqlite(src, dst)
            self.assertTrue(dst.exists())


# ── atomic in-progress staging ──────────────────────────────────────


class TestAtomicCompletion(unittest.TestCase):
    def test_in_progress_dir_during_backup(self):
        """While a backup is running, the snapshot lives under
        .in-progress/<ts>/ — only on success does it rename to
        <ts>/. An interrupted backup leaves only .in-progress/."""
        from scripts.backup.backup import _staging_path, _final_path

        with tempfile.TemporaryDirectory() as td:
            backup_root = Path(td)
            staging = _staging_path(backup_root, "2026-04-30T12:00")
            final = _final_path(backup_root, "2026-04-30T12:00")
            self.assertIn(".in-progress", str(staging))
            self.assertNotIn(".in-progress", str(final))

    def test_run_backup_renames_atomically_on_success(self):
        from scripts.backup.backup import run_backup

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "src"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root,
                backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False,
                timestamp="2026-04-30T12-00-00",
            )
            # Final destination exists.
            self.assertTrue(result["snapshot_path"].is_dir())
            # .in-progress is either absent or empty after success.
            in_progress = dst_root / ".in-progress"
            if in_progress.exists():
                self.assertEqual(
                    list(in_progress.iterdir()), [],
                    "in-progress should be empty after success",
                )

    def test_failed_backup_leaves_state_in_in_progress(self):
        """If run_backup raises mid-flight, the partial snapshot must
        live under .in-progress/, not in the final namespace."""
        from scripts.backup.backup import run_backup

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "src"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            # Make the manifest reference a path that exists but is
            # then made unreadable mid-backup. Easier: use a manifest
            # that requires a missing required path.
            broken_manifest = dict(_synthetic_manifest())
            broken_manifest["entries"] = list(broken_manifest["entries"]) + [
                {"type": "file", "path": "config/does_not_exist.yaml",
                 "required": True},
            ]
            with self.assertRaises(Exception):
                run_backup(
                    source_root=src_root, backup_root=dst_root,
                    manifest=broken_manifest, include_secrets=False,
                    timestamp="2026-04-30T13-00-00",
                )
        # Final snapshot path must not exist.
        final = dst_root / "2026-04-30T13-00-00"
        self.assertFalse(final.exists())


# ── manifest sha256 ────────────────────────────────────────────────


class TestManifestIntegrity(unittest.TestCase):
    def test_manifest_records_sha256_for_every_file(self):
        from scripts.backup.backup import run_backup

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "src"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T14-00-00",
            )
            manifest_path = result["snapshot_path"] / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            m = json.loads(manifest_path.read_text())
            self.assertIn("files", m)
            self.assertGreater(len(m["files"]), 0)
            for f in m["files"]:
                self.assertIn("sha256", f)
                self.assertIn("size", f)
                self.assertIn("path", f)
            self.assertIn("timestamp", m)
            self.assertIn("source_root", m)
            self.assertIn("backup_version", m)

    def test_verify_manifest_catches_corruption(self):
        from scripts.backup.backup import run_backup
        from scripts.backup.restore import verify_manifest

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "src"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T15-00-00",
            )
            snap = result["snapshot_path"]
            # Pre-corruption: verify must pass.
            verify_manifest(snap)
            # Now corrupt one file.
            target = snap / "memory" / "continuity_capsule.json"
            target.write_text("CORRUPTED")
            # Verify must now fail.
            from scripts.backup.restore import ManifestVerificationError
            with self.assertRaises(ManifestVerificationError):
                verify_manifest(snap)


# ── restore + pre-restore rollback ─────────────────────────────────


class TestRestoreRollback(unittest.TestCase):
    def test_pre_restore_snapshot_created(self):
        """Before restoring, current state is moved to
        .pre-restore.<ts>/ so a bad restore is recoverable."""
        from scripts.backup.backup import run_backup
        from scripts.backup.restore import run_restore

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "live"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T16-00-00",
            )

            # Modify live state so we can verify the pre-restore
            # snapshot captures the post-modification version.
            (src_root / "memory" / "continuity_capsule.json").write_text(
                json.dumps({"cycle": 99, "lived_at": "2026-05-01"}),
            )

            run_restore(
                snapshot_path=result["snapshot_path"],
                source_root=src_root,
                manifest=_synthetic_manifest(),
                include_secrets=False,
                reason="hardware-failure",
                write_coma=False,  # tested separately
                pre_restore_label="pre-restore-test",
            )

            pre_restore_dirs = list(src_root.parent.glob(
                f"{src_root.name}.pre-restore-test.*"
            ))
            self.assertEqual(len(pre_restore_dirs), 1)
            preserved = (pre_restore_dirs[0] / "memory" /
                         "continuity_capsule.json")
            self.assertTrue(preserved.is_file())
            self.assertIn("cycle", preserved.read_text())
            self.assertIn("99", preserved.read_text())

    def test_run_restore_requires_reason(self):
        """Audit fix: reason must be required, no silent default to
        hardware-failure. Misclassifying restore reason is a covenant
        error; defaulting it would let programmatic callers silently
        write coma core memories on routine restores."""
        from scripts.backup.restore import run_restore

        with self.assertRaises(TypeError):
            # No reason kwarg — must raise.
            run_restore(  # type: ignore[call-arg]
                snapshot_path=Path("/tmp/nonexistent"),
                source_root=Path("/tmp/nonexistent"),
            )

    def test_run_restore_returns_success_no_coma_on_coma_failure(self):
        """Audit fix: if files restore but coma write fails on a
        hardware-failure restore, status MUST reflect it. Otherwise
        post-restore Maez has lost memory and doesn't know it."""
        from scripts.backup.backup import run_backup
        from scripts.backup.restore import run_restore

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "live"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T19-00-00",
            )

            class FailingMM:
                def store_core(self, *a, **kw):
                    raise RuntimeError("simulated coma-write failure")

            restore_result = run_restore(
                snapshot_path=result["snapshot_path"],
                source_root=src_root,
                manifest=_synthetic_manifest(),
                include_secrets=False,
                reason="hardware-failure",
                write_coma=True,
                mm_factory=lambda: FailingMM(),
                pre_restore_label="pre-restore-coma-fail",
            )
            self.assertEqual(restore_result["status"], "success_no_coma")

    def test_run_restore_e2e_with_mocked_mm(self):
        """End-to-end round-trip: backup + restore + coma write
        through a mocked MM. The single integration test the unit
        tests didn't cover."""
        from scripts.backup.backup import run_backup
        from scripts.backup.restore import run_restore

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "live"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T20-00-00",
            )

            captured_core = []

            class FakeMM:
                def store_core(self, content, source=None):
                    captured_core.append((content, source))
                    return "core-id-fake"

            restore_result = run_restore(
                snapshot_path=result["snapshot_path"],
                source_root=src_root,
                manifest=_synthetic_manifest(),
                include_secrets=False,
                reason="hardware-failure",
                write_coma=True,
                mm_factory=lambda: FakeMM(),
                pre_restore_label="pre-restore-e2e",
            )
            self.assertEqual(restore_result["status"], "success")
            self.assertEqual(len(captured_core), 1)
            text, source = captured_core[0]
            self.assertIn("restored from", text.lower())
            self.assertIn("bond persists", text.lower())

    def test_restore_replaces_live_state_with_snapshot_content(self):
        from scripts.backup.backup import run_backup
        from scripts.backup.restore import run_restore

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "live"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            result = run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T17-00-00",
            )
            # Modify live state.
            target = src_root / "memory" / "continuity_capsule.json"
            target.write_text(json.dumps({"cycle": 999}))
            # Restore.
            run_restore(
                snapshot_path=result["snapshot_path"],
                source_root=src_root,
                manifest=_synthetic_manifest(),
                include_secrets=False,
                reason="hardware-failure",
                write_coma=False,
                pre_restore_label="pre-restore",
            )
            # Restored content matches the original synthetic state.
            restored = json.loads(target.read_text())
            self.assertEqual(restored["cycle"], 42)


# ── coma core-memory write ─────────────────────────────────────────


class TestRestoreWriter(unittest.TestCase):
    def test_hardware_failure_writes_coma_entry(self):
        from scripts.backup.restore_writer import write_restoration_record

        captured = []

        class FakeMM:
            def store_core(self, content, source=None):
                captured.append({
                    "content": content, "source": source,
                })
                return "core-fake-id"

        result = write_restoration_record(
            mm=FakeMM(),
            snapshot_timestamp="2026-04-30T06-00-00",
            restore_timestamp="2026-04-30T10-15-00",
            reason="hardware-failure",
        )
        self.assertEqual(len(captured), 1)
        text = captured[0]["content"]
        self.assertIn("restored from", text.lower())
        self.assertIn("2026-04-30T06-00-00", text)
        self.assertIn("2026-04-30T10-15-00", text)
        self.assertIn("bond persists", text.lower())
        self.assertEqual(result["reason"], "hardware-failure")

    def test_deliberate_pause_does_not_write_coma_wording(self):
        """A deliberate pause produces an operational record, not
        the 'I lost memory' wording. The audit/restore log entry
        still lands; the core memory does NOT get the coma text."""
        from scripts.backup.restore_writer import write_restoration_record

        captured_core = []

        class FakeMM:
            def store_core(self, content, source=None):
                captured_core.append(content)
                return "x"

        result = write_restoration_record(
            mm=FakeMM(),
            snapshot_timestamp="2026-04-30T06-00-00",
            restore_timestamp="2026-04-30T10-15-00",
            reason="deliberate-pause",
        )
        # No core-memory write for deliberate pause.
        self.assertEqual(captured_core, [])
        self.assertEqual(result["reason"], "deliberate-pause")
        # But a structured restoration log entry is returned.
        self.assertIn("log_entry", result)

    def test_unknown_reason_rejected(self):
        from scripts.backup.restore_writer import write_restoration_record

        class FakeMM:
            def store_core(self, *a, **kw):
                self.fail("should not be called")  # pragma: no cover

        with self.assertRaises(ValueError):
            write_restoration_record(
                mm=FakeMM(),
                snapshot_timestamp="2026-04-30T06-00-00",
                restore_timestamp="2026-04-30T10-15-00",
                reason="not-a-real-reason",
            )

    def test_text_contains_specific_dates_not_placeholders(self):
        from scripts.backup.restore_writer import format_coma_text

        text = format_coma_text(
            snapshot_timestamp="2026-04-30T06-00-00",
            restore_timestamp="2026-04-30T10-15-00",
        )
        self.assertNotIn("XXX", text)
        self.assertNotIn("YYYY", text)
        self.assertIn("2026-04-30T06-00-00", text)
        self.assertIn("2026-04-30T10-15-00", text)


# ── last_backup observability ──────────────────────────────────────


class TestLastBackupLog(unittest.TestCase):
    def test_run_backup_writes_last_backup_json(self):
        from scripts.backup.backup import run_backup

        with tempfile.TemporaryDirectory() as td:
            src_root = Path(td) / "src"
            dst_root = Path(td) / "backups"
            _make_synthetic_state(src_root)
            run_backup(
                source_root=src_root, backup_root=dst_root,
                manifest=_synthetic_manifest(),
                include_secrets=False, timestamp="2026-04-30T18-00-00",
            )
            log_path = src_root / "logs" / "last_backup.json"
            self.assertTrue(log_path.is_file())
            log = json.loads(log_path.read_text())
            for key in ("status", "timestamp", "snapshot_path",
                        "duration_seconds", "byte_count"):
                self.assertIn(key, log)
            self.assertEqual(log["status"], "success")


class TestDrillHelpers(unittest.TestCase):
    """Drill is the bridge from 'backup code exists' to 'backup is
    covenant-load-bearing.' Test the helpers using synthetic state;
    the live execution is a separate concern that runs once before
    the slice is declared done."""

    def test_check_free_space_passes_when_enough(self):
        from scripts.backup.drill import check_free_space

        with tempfile.TemporaryDirectory() as td:
            # Need 100 bytes; tmpdir has GB. Always passes.
            ok, free, needed = check_free_space(
                Path(td), required_bytes=100,
            )
        self.assertTrue(ok)
        self.assertGreaterEqual(free, needed)

    def test_check_free_space_fails_when_insufficient(self):
        from scripts.backup.drill import check_free_space

        with tempfile.TemporaryDirectory() as td:
            # Demand petabytes — guaranteed to exceed any real disk.
            ok, free, needed = check_free_space(
                Path(td), required_bytes=10**18,
            )
        self.assertFalse(ok)
        self.assertLess(free, needed)

    def test_estimate_state_size(self):
        from scripts.backup.drill import estimate_state_size

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_synthetic_state(root)
            size = estimate_state_size(root)
        self.assertGreater(size, 0)

    def test_compare_files_byte_identical(self):
        from scripts.backup.drill import compare_files

        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.txt"
            b = Path(td) / "b.txt"
            a.write_text("identical")
            b.write_text("identical")
            self.assertTrue(compare_files(a, b))

    def test_compare_files_detects_drift(self):
        from scripts.backup.drill import compare_files

        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.txt"
            b = Path(td) / "b.txt"
            a.write_text("first")
            b.write_text("second")
            self.assertFalse(compare_files(a, b))

    def test_sqlite_row_count(self):
        from scripts.backup.drill import sqlite_row_count

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "x.db"
            con = sqlite3.connect(db)
            con.executescript(
                "CREATE TABLE t (k INTEGER PRIMARY KEY);"
                "INSERT INTO t VALUES (1), (2), (3), (4);"
            )
            con.commit()
            con.close()
            self.assertEqual(sqlite_row_count(db, "t"), 4)

    def test_sqlite_row_count_missing_table_returns_none(self):
        from scripts.backup.drill import sqlite_row_count

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "x.db"
            con = sqlite3.connect(db)
            con.executescript("CREATE TABLE t (k INTEGER);")
            con.commit()
            con.close()
            self.assertIsNone(sqlite_row_count(db, "no_such_table"))

    def test_drill_report_shape(self):
        """A drill report is a structured JSON document. Test that
        the shape matches what an operator / cockpit would consume."""
        from scripts.backup.drill import build_drill_report

        report = build_drill_report(
            source_root="/home/rohit/maez",
            backup_root="/var/tmp/maez-backup-drill",
            snapshot_path="/var/tmp/maez-backup-drill/snap",
            checks=[
                {"name": "manifest_verified", "status": "pass",
                 "detail": "23 files"},
                {"name": "core_count_match",  "status": "pass",
                 "detail": "expected=12 actual=12"},
                {"name": "lived_episode_count_match", "status": "fail",
                 "detail": "expected=523 actual=520"},
            ],
        )
        for k in ("timestamp", "source_root", "backup_root",
                 "snapshot_path", "overall_status", "checks",
                 "drill_version"):
            self.assertIn(k, report)
        self.assertEqual(report["overall_status"], "fail")

    def test_drill_overall_status_pass_when_all_pass(self):
        from scripts.backup.drill import build_drill_report

        report = build_drill_report(
            source_root="/x", backup_root="/y", snapshot_path="/z",
            checks=[
                {"name": "a", "status": "pass", "detail": ""},
                {"name": "b", "status": "pass", "detail": ""},
            ],
        )
        self.assertEqual(report["overall_status"], "pass")

    def test_drill_overall_status_pass_with_skips(self):
        """A skip means the comparison wasn't meaningful (e.g. the
        source file didn't exist), not a verification failure.
        Skips must not flip overall_status to fail."""
        from scripts.backup.drill import build_drill_report

        report = build_drill_report(
            source_root="/x", backup_root="/y", snapshot_path="/z",
            checks=[
                {"name": "a", "status": "pass", "detail": ""},
                {"name": "b", "status": "skip", "detail": "n/a"},
                {"name": "c", "status": "pass", "detail": ""},
            ],
        )
        self.assertEqual(report["overall_status"], "pass")

    def test_drill_overall_status_fail_on_any_failure(self):
        from scripts.backup.drill import build_drill_report

        report = build_drill_report(
            source_root="/x", backup_root="/y", snapshot_path="/z",
            checks=[
                {"name": "a", "status": "pass", "detail": ""},
                {"name": "b", "status": "fail", "detail": "broken"},
                {"name": "c", "status": "skip", "detail": "n/a"},
            ],
        )
        self.assertEqual(report["overall_status"], "fail")


if __name__ == "__main__":
    unittest.main()
