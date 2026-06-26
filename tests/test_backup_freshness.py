import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.health.backup_freshness import backup_freshness


_REQ = {"memory/salience_ledger.db", "memory/subjective_duration.db"}


def _now() -> datetime:
    return datetime(2026, 6, 26, 2, 0, 0, tzinfo=timezone.utc)


def _mkbackup(root: str, name: str, files: list[str], *, in_progress: bool = False) -> Path:
    parent = Path(root) / ".in-progress" if in_progress else Path(root)
    d = parent / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(
        json.dumps({
            "timestamp": name,
            "files": [{"path": p} for p in files],
        }),
        encoding="utf-8",
    )
    return d


class BackupFreshnessTest(unittest.TestCase):
    def _root(self) -> str:
        return tempfile.mkdtemp()

    def test_fresh_when_recent_and_complete(self):
        root = self._root()
        _mkbackup(
            root,
            "2026-06-26T01-17-03",
            ["memory/salience_ledger.db", "memory/subjective_duration.db"],
        )
        self.assertEqual(
            backup_freshness(backup_root=root, required_paths=_REQ, now=_now()),
            "fresh",
        )

    def test_coverage_gap_when_recent_but_missing_store(self):
        root = self._root()
        _mkbackup(root, "2026-06-26T01-17-03", ["memory/salience_ledger.db"])
        self.assertEqual(
            backup_freshness(backup_root=root, required_paths=_REQ, now=_now()),
            "coverage_gap",
        )

    def test_stale_when_old(self):
        root = self._root()
        _mkbackup(
            root,
            "2026-06-25T00-00-00",
            ["memory/salience_ledger.db", "memory/subjective_duration.db"],
        )
        self.assertEqual(
            backup_freshness(backup_root=root, required_paths=_REQ, now=_now()),
            "stale",
        )

    def test_unavailable_when_no_finalized_backup(self):
        root = self._root()
        _mkbackup(root, "2026-06-26T01-50-00", ["memory/salience_ledger.db"], in_progress=True)
        self.assertEqual(
            backup_freshness(backup_root=root, required_paths=_REQ, now=_now()),
            "unavailable",
        )

    def test_inprogress_is_never_counted(self):
        root = self._root()
        _mkbackup(
            root,
            "2026-06-26T01-17-03",
            ["memory/salience_ledger.db", "memory/subjective_duration.db"],
        )
        _mkbackup(root, "2026-06-26T01-55-00", ["memory/salience_ledger.db"], in_progress=True)
        self.assertEqual(
            backup_freshness(backup_root=root, required_paths=_REQ, now=_now()),
            "fresh",
        )

    def test_required_directory_is_covered_by_child_files(self):
        root = self._root()
        _mkbackup(
            root,
            "2026-06-26T01-17-03",
            ["memory/db/chroma.sqlite3", "memory/salience_ledger.db"],
        )
        self.assertEqual(
            backup_freshness(
                backup_root=root,
                required_paths={"memory/db", "memory/salience_ledger.db"},
                now=_now(),
            ),
            "fresh",
        )


if __name__ == "__main__":
    unittest.main()
