import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backup.drill import (
    required_store_entries,
    run_restore_smoke_test,
    verify_backup_entry,
)


def _mkdb(path: Path, table: str, rows: int) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute(f'CREATE TABLE "{table}"(id INTEGER)')
        con.executemany(f'INSERT INTO "{table}" VALUES (?)', [(i,) for i in range(rows)])
        con.commit()
    finally:
        con.close()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RestoreSmokeTest(unittest.TestCase):
    def _backup(
        self,
        *,
        parent: Path | None = None,
        name: str = "2026-06-26T03-59-05",
    ) -> Path:
        root = (parent or Path(tempfile.mkdtemp())) / name
        root.mkdir(parents=True)
        (root / "memory").mkdir()
        db = root / "memory" / "salience_ledger.db"
        _mkdb(db, "salience_ledger", 7)
        (root / "manifest.json").write_text(
            json.dumps({
                "timestamp": "2026-06-26T03-59-05",
                "files": [
                    {
                        "path": "memory/salience_ledger.db",
                        "sha256": _sha(db),
                        "source_type": "sqlite_db",
                    }
                ],
            }),
            encoding="utf-8",
        )
        return root

    def _state_manifest(self) -> dict:
        return {
            "entries": [
                {
                    "type": "sqlite_db",
                    "path": "memory/salience_ledger.db",
                    "class": "required_welfare",
                },
            ]
        }

    def test_selects_required_welfare_and_continuity(self):
        state_manifest = {
            "entries": [
                {
                    "type": "sqlite_db",
                    "path": "memory/salience_ledger.db",
                    "class": "required_welfare",
                },
                {
                    "type": "sqlite_db",
                    "path": "memory/lived_episodes.db",
                    "class": "required_continuity",
                },
                {
                    "type": "sqlite_db",
                    "path": "memory/site_analytics.db",
                    "class": "optional_observability",
                },
            ]
        }
        paths = {entry["path"] for entry in required_store_entries(state_manifest)}
        self.assertEqual(paths, {"memory/salience_ledger.db", "memory/lived_episodes.db"})

    def test_sqlite_entry_present_hash_and_quickcheck(self):
        backup_dir = self._backup()
        manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
        files_by_path = {entry["path"]: entry for entry in manifest["files"]}
        record = verify_backup_entry(
            {
                "type": "sqlite_db",
                "path": "memory/salience_ledger.db",
                "class": "required_welfare",
            },
            backup_dir=backup_dir,
            files_by_path=files_by_path,
            tmp_root=Path(tempfile.mkdtemp()),
        )
        self.assertEqual(record["status"], "pass")
        self.assertEqual(record["quick_check"], "ok")
        self.assertEqual(record["row_counts"]["salience_ledger"], 7)

    def test_missing_required_store_fails(self):
        backup_dir = self._backup()
        record = verify_backup_entry(
            {
                "type": "sqlite_db",
                "path": "memory/subjective_duration.db",
                "class": "required_welfare",
                "required": True,
            },
            backup_dir=backup_dir,
            files_by_path={},
            tmp_root=Path(tempfile.mkdtemp()),
        )
        self.assertEqual(record["status"], "fail")

    def test_missing_optional_welfare_store_skips(self):
        backup_dir = self._backup()
        record = verify_backup_entry(
            {
                "type": "sqlite_db",
                "path": "memory/fresh_moment_receipts.db",
                "class": "required_welfare",
                "required": False,
            },
            backup_dir=backup_dir,
            files_by_path={},
            tmp_root=Path(tempfile.mkdtemp()),
        )
        self.assertEqual(record["status"], "skip")
        self.assertIn("not present", record["detail"])

    def test_smoke_passes_when_only_optional_welfare_store_is_absent(self):
        root = Path(tempfile.mkdtemp())
        backup_root = root / "backups"
        backup_root.mkdir()
        self._backup(parent=backup_root, name="2026-06-26T03-59-05")
        state_manifest = {
            "entries": [
                {
                    "type": "sqlite_db",
                    "path": "memory/salience_ledger.db",
                    "class": "required_welfare",
                    "required": True,
                },
                {
                    "type": "sqlite_db",
                    "path": "memory/fresh_moment_receipts.db",
                    "class": "required_welfare",
                    "required": False,
                },
            ]
        }

        report = run_restore_smoke_test(
            backup_root=backup_root,
            state_manifest=state_manifest,
            log_dir=root / "logs",
            timestamp="2026-06-26T05-00-00",
        )

        self.assertEqual(report["overall_status"], "pass")
        checks = {check["path"]: check for check in report["checks"]}
        self.assertEqual(checks["memory/salience_ledger.db"]["status"], "pass")
        self.assertEqual(checks["memory/fresh_moment_receipts.db"]["status"], "skip")

    def test_sha256_mismatch_fails(self):
        backup_dir = self._backup()
        manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
        files_by_path = {
            entry["path"]: {**entry, "sha256": "deadbeef"} for entry in manifest["files"]
        }
        record = verify_backup_entry(
            {
                "type": "sqlite_db",
                "path": "memory/salience_ledger.db",
                "class": "required_welfare",
            },
            backup_dir=backup_dir,
            files_by_path=files_by_path,
            tmp_root=Path(tempfile.mkdtemp()),
        )
        self.assertEqual(record["status"], "fail")
        self.assertIn("sha256", record["detail"].lower())

    def test_smoke_run_writes_report_for_latest_finalized_backup(self):
        root = Path(tempfile.mkdtemp())
        backup_root = root / "backups"
        backup_root.mkdir()
        self._backup(parent=backup_root, name="2026-06-26T03-59-05")
        latest = self._backup(parent=backup_root, name="2026-06-26T04-59-05")
        report = run_restore_smoke_test(
            backup_root=backup_root,
            state_manifest=self._state_manifest(),
            log_dir=root / "logs",
            timestamp="2026-06-26T05-00-00",
        )

        self.assertEqual(report["overall_status"], "pass")
        self.assertEqual(report["snapshot_path"], str(latest))
        self.assertEqual(report["required_count"], 1)
        self.assertEqual(report["checks"][0]["row_counts"]["salience_ledger"], 7)
        self.assertTrue(Path(report["report_path"]).is_file())

    def test_smoke_ignores_newer_in_progress_backup(self):
        root = Path(tempfile.mkdtemp())
        backup_root = root / "backups"
        backup_root.mkdir()
        finalized = self._backup(parent=backup_root, name="2026-06-26T03-59-05")
        in_progress = backup_root / "2026-06-26T04-59-05.in-progress"
        in_progress.mkdir()
        (in_progress / "manifest.json").write_text(
            json.dumps({"timestamp": "bad", "files": []}),
            encoding="utf-8",
        )

        report = run_restore_smoke_test(
            backup_root=backup_root,
            state_manifest=self._state_manifest(),
            log_dir=root / "logs",
            timestamp="2026-06-26T05-00-00",
        )

        self.assertEqual(report["overall_status"], "pass")
        self.assertEqual(report["snapshot_path"], str(finalized))

    def test_smoke_reports_unavailable_when_no_finalized_backup(self):
        root = Path(tempfile.mkdtemp())
        backup_root = root / "backups"
        backup_root.mkdir()
        report = run_restore_smoke_test(
            backup_root=backup_root,
            state_manifest=self._state_manifest(),
            log_dir=root / "logs",
            timestamp="2026-06-26T05-00-00",
        )

        self.assertEqual(report["overall_status"], "unavailable")
        self.assertIn("no finalized", report["detail"])
        self.assertTrue(Path(report["report_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
