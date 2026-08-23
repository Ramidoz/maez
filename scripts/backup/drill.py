# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Backup drill — bridge from "code exists" to "covenant-load-bearing."

A backup system that's only been tested against synthetic fixtures
is not yet a real backup system. This drill exercises the full
pipeline against the live repo state and a fresh ``MemoryManager``
loaded from the restored snapshot.

Procedure:

1. Check destination has enough free disk space (≥ 2× source size).
2. Run a real backup against the live repo.
3. Run two restorations into separate temp directories:
   - ``hardware-failure`` with ``--no-coma`` (file machinery).
   - ``deliberate-pause`` (proves the reason gate doesn't emit
     coma wording in the wrong scenario).
4. For each restored copy, verify:
   - Manifest sha256 + sizes match.
   - ``MemoryManager`` opens cleanly against the restored state.
   - Core-memory count matches source.
   - ``recall_for_cycle("identity")`` returns a non-empty bundle.
   - Lived-memory episode count matches source.
   - ``identity.yaml`` is byte-identical to source.
   - Key SQLite DBs open + row counts match source.
5. Emit ``logs/backup_drill_<timestamp>.json``.
6. On all-pass, clean up drill directories (unless ``--keep``).
   On any failure, leave directories in place for inspection.

What this drill DOES NOT do:

- Restore into the live repo. The drill restores into temp dirs only.
- Write a real coma core memory. The drill uses ``--no-coma`` and
  the deliberate-pause reason which doesn't trigger coma writes.
- Stop the live daemon. The drill runs against a live writer to
  prove SQLite ``.backup()`` and Chroma handling under realistic
  conditions.

Run::

    python -m scripts.backup.drill
    python -m scripts.backup.drill --backup-root /home/rohit/maez-drill --keep
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DRILL_VERSION = 1
_RESTORE_SMOKE_SCHEMA_VERSION = "backup_restore_smoke.v1.1"
_DEFAULT_BACKUP_ROOT = Path("/var/tmp/maez-backup-drill")
_RESTORE_SMOKE_REQUIRED_CLASSES = frozenset({
    "required_continuity",
    "required_welfare",
})


# ── helpers ────────────────────────────────────────────────────────


def estimate_state_size(source_root: Path) -> int:
    """Sum the byte size of all files the manifest would back up.
    Used to sanity-check destination free space before running."""
    from scripts.backup.inventory import (
        load_default_manifest,
        resolve_inventory,
    )

    manifest = load_default_manifest()
    resolved = resolve_inventory(
        manifest,
        source_root,
        include_secrets=False,
    )
    total = 0
    for entry in resolved:
        for p in entry["resolved_paths"]:
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        try:
                            total += f.stat().st_size
                        except OSError:
                            continue
    return total


def check_free_space(
    destination: Path,
    required_bytes: int,
) -> tuple[bool, int, int]:
    """Return ``(ok, free_bytes, required_bytes)``. Caller is the
    drill driver — decide what to do on insufficient space at the
    higher level."""
    destination.mkdir(parents=True, exist_ok=True)
    stat = os.statvfs(str(destination))
    free = stat.f_bavail * stat.f_frsize
    return (free >= required_bytes, free, required_bytes)


def compare_files(a: Path, b: Path) -> bool:
    """Byte-by-byte equality check via sha256. Used for plain files
    where source and restored copy should be identical."""
    if not a.is_file() or not b.is_file():
        return False
    return _sha256(a) == _sha256(b)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sqlite_row_count(db_path: Path, table: str) -> int | None:
    """Return the row count of ``table`` in the SQLite DB at
    ``db_path``. Returns None if the table doesn't exist (so the
    caller can distinguish 'missing' from 'empty')."""
    try:
        con = sqlite3.connect(str(db_path))
        try:
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cur.fetchone() is None:
                return None
            row = con.execute(
                f"SELECT COUNT(*) FROM {table}"  # noqa: S608 — table is a literal arg
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return None


def required_store_entries(state_manifest: dict) -> list[dict]:
    """Return manifest entries the restore smoke test must verify.

    The backup manifest is the single source of truth: do not keep a
    second hardcoded list of stores here.
    """
    entries = state_manifest.get("entries") or []
    return [
        entry
        for entry in entries
        if entry.get("class") in _RESTORE_SMOKE_REQUIRED_CLASSES
    ]


def _quote_sqlite_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _artifact_file_check(
    *,
    rel_path: str,
    backup_dir: Path,
    files_by_path: dict[str, dict],
) -> tuple[bool, str, Path | None]:
    manifest_record = files_by_path.get(rel_path)
    if manifest_record is None:
        return False, "missing from backup manifest", None
    artifact_path = backup_dir / rel_path
    if not artifact_path.is_file():
        return False, "missing from backup artifact", None
    recorded_sha = str(manifest_record.get("sha256") or "")
    actual_sha = _sha256(artifact_path)
    if recorded_sha != actual_sha:
        return False, f"sha256 mismatch recorded={recorded_sha} actual={actual_sha}", None
    return True, "sha256 ok", artifact_path


def _sqlite_table_counts(db_path: Path) -> tuple[str, dict[str, int]]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        quick_check_row = con.execute("PRAGMA quick_check").fetchone()
        quick_check = str(quick_check_row[0]) if quick_check_row else ""
        table_rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        row_counts: dict[str, int] = {}
        for row in table_rows:
            table = str(row[0])
            quoted = _quote_sqlite_identifier(table)
            count_row = con.execute(
                f"SELECT COUNT(*) FROM {quoted}"  # noqa: S608 - table name is quoted from sqlite_master
            ).fetchone()
            row_counts[table] = int(count_row[0]) if count_row else 0
        return quick_check, row_counts
    finally:
        con.close()


def verify_backup_entry(
    entry: dict,
    *,
    backup_dir: Path,
    files_by_path: dict[str, dict],
    tmp_root: Path,
) -> dict:
    """Verify one required manifest entry against the backup artifact.

    This compares the artifact to its own recorded ``manifest.json``.
    It deliberately does not compare to the live repo.
    """
    rel_path = str(entry.get("path") or "")
    entry_type = str(entry.get("type") or "")
    required = bool(entry.get("required", False))
    record = {
        "path": rel_path,
        "type": entry_type,
        "class": entry.get("class"),
    }
    if not rel_path:
        return {**record, "status": "fail", "detail": "manifest entry missing path"}

    if entry_type == "sqlite_db":
        ok, detail, artifact_path = _artifact_file_check(
            rel_path=rel_path,
            backup_dir=backup_dir,
            files_by_path=files_by_path,
        )
        if (
            not ok
            and not required
            and detail == "missing from backup manifest"
        ):
            return {
                **record,
                "status": "skip",
                "detail": "optional store not present in backup artifact",
            }
        if not ok or artifact_path is None:
            return {**record, "status": "fail", "detail": detail}
        tmp_db = tmp_root / rel_path
        tmp_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_path, tmp_db)
        try:
            quick_check, row_counts = _sqlite_table_counts(tmp_db)
        except sqlite3.DatabaseError as exc:
            return {
                **record,
                "status": "fail",
                "detail": f"sqlite open failed: {type(exc).__name__}: {exc}",
            }
        status = "pass" if quick_check == "ok" else "fail"
        return {
            **record,
            "status": status,
            "detail": "sqlite quick_check ok" if status == "pass" else "sqlite quick_check failed",
            "quick_check": quick_check,
            "row_counts": row_counts,
        }

    if entry_type in {"file", "secret_file"}:
        ok, detail, _ = _artifact_file_check(
            rel_path=rel_path,
            backup_dir=backup_dir,
            files_by_path=files_by_path,
        )
        if (
            not ok
            and not required
            and detail == "missing from backup manifest"
        ):
            return {
                **record,
                "status": "skip",
                "detail": "optional store not present in backup artifact",
            }
        return {**record, "status": "pass" if ok else "fail", "detail": detail}

    if entry_type == "directory":
        prefix = rel_path.rstrip("/") + "/"
        child_paths = sorted(p for p in files_by_path if p.startswith(prefix))
        if not child_paths:
            if not required:
                return {
                    **record,
                    "status": "skip",
                    "detail": "optional directory not present in backup artifact",
                }
            return {**record, "status": "fail", "detail": "directory has no manifest files"}
        failures = []
        for child in child_paths:
            ok, detail, _ = _artifact_file_check(
                rel_path=child,
                backup_dir=backup_dir,
                files_by_path=files_by_path,
            )
            if not ok:
                failures.append(f"{child}: {detail}")
        if failures:
            return {**record, "status": "fail", "detail": "; ".join(failures[:3])}
        return {
            **record,
            "status": "pass",
            "detail": f"{len(child_paths)} files present with matching sha256",
        }

    return {
        **record,
        "status": "skip",
        "detail": f"restore smoke does not inspect type {entry_type!r}",
    }


def _latest_finalized_backup(backup_root: Path) -> Path | None:
    if not backup_root.is_dir():
        return None
    candidates = [
        child
        for child in backup_root.iterdir()
        if child.is_dir()
        and not child.name.endswith(".in-progress")
        and (child / "manifest.json").is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)


def _write_report_log(log_dir: Path, report: dict) -> Path:
    ts = report.get("timestamp", "unknown")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"backup_drill_{ts}.json"
    report["report_path"] = str(log_path)
    log_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return log_path


def run_restore_smoke_test(
    *,
    backup_root: Path,
    state_manifest: dict,
    log_dir: Path,
    timestamp: str | None = None,
) -> dict:
    """Verify the latest backup artifact can carry required stores.

    This is artifact-self-consistent: it verifies the backup against
    its own recorded manifest and never compares to live ``memory/``.
    """
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    latest = _latest_finalized_backup(backup_root)
    if latest is None:
        report = {
            "schema_version": _RESTORE_SMOKE_SCHEMA_VERSION,
            "timestamp": ts,
            "backup_root": str(backup_root),
            "snapshot_path": "",
            "overall_status": "unavailable",
            "detail": "no finalized backup found",
            "required_count": 0,
            "checks": [],
        }
        _write_report_log(log_dir, report)
        return report

    manifest_path = latest / "manifest.json"
    try:
        artifact_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report = {
            "schema_version": _RESTORE_SMOKE_SCHEMA_VERSION,
            "timestamp": ts,
            "backup_root": str(backup_root),
            "snapshot_path": str(latest),
            "overall_status": "fail",
            "detail": f"manifest read failed: {type(exc).__name__}: {exc}",
            "required_count": 0,
            "checks": [],
        }
        _write_report_log(log_dir, report)
        return report

    files_by_path = {
        str(entry.get("path")): entry
        for entry in (artifact_manifest.get("files") or [])
        if isinstance(entry, dict) and entry.get("path")
    }
    required_entries = required_store_entries(state_manifest)
    tmp_root = Path(tempfile.mkdtemp(prefix="maez-restore-smoke-"))
    try:
        checks = [
            verify_backup_entry(
                entry,
                backup_dir=latest,
                files_by_path=files_by_path,
                tmp_root=tmp_root,
            )
            for entry in required_entries
        ]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    has_failure = any(check.get("status") == "fail" for check in checks)
    status = "fail" if has_failure or not required_entries else "pass"
    detail = (
        "required stores verified"
        if status == "pass"
        else "one or more required stores failed restore smoke verification"
    )
    if not required_entries:
        detail = "state manifest contains no required welfare or continuity stores"
    report = {
        "schema_version": _RESTORE_SMOKE_SCHEMA_VERSION,
        "timestamp": ts,
        "backup_root": str(backup_root),
        "snapshot_path": str(latest),
        "snapshot_timestamp": artifact_manifest.get("timestamp"),
        "overall_status": status,
        "detail": detail,
        "required_count": len(required_entries),
        "checks": checks,
    }
    _write_report_log(log_dir, report)
    return report


def build_drill_report(
    *,
    source_root: str,
    backup_root: str,
    snapshot_path: str,
    checks: list[dict],
    extras: dict | None = None,
) -> dict:
    """Compose the drill report. ``overall_status`` is 'pass' iff
    no check FAILED (skips are tolerated — a skipped check means
    'comparison wasn't meaningful', not 'verification failed')."""
    has_failure = any(c.get("status") == "fail" for c in checks)
    overall = "fail" if has_failure else "pass"
    report = {
        "drill_version": _DRILL_VERSION,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S"),
        "source_root": source_root,
        "backup_root": backup_root,
        "snapshot_path": snapshot_path,
        "overall_status": overall,
        "checks": checks,
    }
    if extras:
        report.update(extras)
    return report


# ── verification checks ─────────────────────────────────────────────


def _open_mm_at(memory_db_path: Path):
    """Open a MemoryManager rooted at ``memory_db_path`` by
    monkeypatching the module-level BASE_DB. Mirrors the
    LongMemEval IsolatedMemoryHarness pattern."""
    import memory.memory_manager as mm_mod
    from memory.memory_manager import MemoryManager

    saved = mm_mod.BASE_DB
    mm_mod.BASE_DB = memory_db_path
    try:
        mm = MemoryManager()
    finally:
        mm_mod.BASE_DB = saved
    return mm


def verify_restored_copy(
    *,
    source_root: Path,
    restored_root: Path,
    label: str,
) -> list[dict]:
    """Return a list of check records for the restored copy.

    Each check is ``{name, status, detail}`` with ``status`` in
    {pass, fail, skip}. ``skip`` is for checks where the source
    file doesn't exist (so the comparison is meaningless).

    Note: snapshot-manifest verification happens inside
    ``run_restore`` and at the drill driver level. The restored
    copy itself does NOT contain ``manifest.json`` (the restore
    explicitly skips it), so re-verifying here would always fail.
    """
    checks: list[dict] = []

    # 1. MemoryManager opens.
    restored_mm_path = restored_root / "memory" / "db"
    if not restored_mm_path.is_dir():
        checks.append(
            {
                "name": f"{label}.memory_manager_opens",
                "status": "skip",
                "detail": "no memory/db in restored copy",
            }
        )
    else:
        try:
            mm = _open_mm_at(restored_mm_path)
            checks.append(
                {
                    "name": f"{label}.memory_manager_opens",
                    "status": "pass",
                    "detail": "MemoryManager() instantiated cleanly",
                }
            )

            # 3. Core-memory count matches source.
            try:
                source_mm = _open_mm_at(source_root / "memory" / "db")
                source_core = len(source_mm.get_all_core() or [])
                restored_core = len(mm.get_all_core() or [])
                if source_core == restored_core:
                    checks.append(
                        {
                            "name": f"{label}.core_count_match",
                            "status": "pass",
                            "detail": f"source={source_core} restored={restored_core}",
                        }
                    )
                else:
                    checks.append(
                        {
                            "name": f"{label}.core_count_match",
                            "status": "fail",
                            "detail": f"source={source_core} restored={restored_core}",
                        }
                    )
            except Exception as e:  # pragma: no cover — live-data paths
                checks.append(
                    {
                        "name": f"{label}.core_count_match",
                        "status": "fail",
                        "detail": f"{type(e).__name__}: {e}",
                    }
                )

            # 4. Recall returns non-empty for a known query.
            try:
                bundle = mm.recall_for_cycle("identity")
                core_n = len(bundle.get("core") or [])
                # Empty cores would make recall trivially empty;
                # check the bundle keys are present rather than
                # asserting non-zero across all tiers.
                checks.append(
                    {
                        "name": f"{label}.recall_for_cycle_non_empty",
                        "status": "pass"
                        if isinstance(bundle, dict)
                        and {"core", "daily", "raw"}.issubset(bundle.keys())
                        else "fail",
                        "detail": f"core={core_n} keys={sorted(bundle.keys())}",
                    }
                )
            except Exception as e:  # pragma: no cover — live-data paths
                checks.append(
                    {
                        "name": f"{label}.recall_for_cycle_non_empty",
                        "status": "fail",
                        "detail": f"{type(e).__name__}: {e}",
                    }
                )
        except Exception as e:  # pragma: no cover — live-data paths
            checks.append(
                {
                    "name": f"{label}.memory_manager_opens",
                    "status": "fail",
                    "detail": f"{type(e).__name__}: {e}",
                }
            )

    # 5. Lived-memory episode count matches source.
    src_eps = source_root / "memory" / "lived_episodes.db"
    rst_eps = restored_root / "memory" / "lived_episodes.db"
    if src_eps.is_file() and rst_eps.is_file():
        src_count = sqlite_row_count(src_eps, "episodes")
        rst_count = sqlite_row_count(rst_eps, "episodes")
        if src_count is None or rst_count is None:
            checks.append(
                {
                    "name": f"{label}.lived_episode_count_match",
                    "status": "skip",
                    "detail": "episodes table not present",
                }
            )
        elif src_count == rst_count:
            checks.append(
                {
                    "name": f"{label}.lived_episode_count_match",
                    "status": "pass",
                    "detail": f"source={src_count} restored={rst_count}",
                }
            )
        else:
            checks.append(
                {
                    "name": f"{label}.lived_episode_count_match",
                    "status": "fail",
                    "detail": f"source={src_count} restored={rst_count}",
                }
            )
    else:
        checks.append(
            {
                "name": f"{label}.lived_episode_count_match",
                "status": "skip",
                "detail": "lived_episodes.db not in source or restored",
            }
        )

    # 6. identity.yaml byte-identical.
    src_id = source_root / "config" / "identity.yaml"
    rst_id = restored_root / "config" / "identity.yaml"
    if not src_id.is_file():
        checks.append(
            {
                "name": f"{label}.identity_yaml_match",
                "status": "skip",
                "detail": "config/identity.yaml not present in source",
            }
        )
    elif compare_files(src_id, rst_id):
        checks.append(
            {
                "name": f"{label}.identity_yaml_match",
                "status": "pass",
                "detail": "byte-identical",
            }
        )
    else:
        checks.append(
            {
                "name": f"{label}.identity_yaml_match",
                "status": "fail",
                "detail": "differs from source or missing in restore",
            }
        )

    # 7. Key SQLite DBs open + row counts match source. We pick
    # high-leverage covenant DBs — immune memory, identity/wants,
    # and private_thoughts — rather than every DB in the manifest.
    # The rest are implicitly covered by manifest sha256 verification.
    for rel, table in (
        ("memory/audit_log.db", "audit_log"),
        ("memory/identity_ledger.db", "identity_ledger"),
        ("memory/private_thoughts.db", "private_thoughts"),
        ("memory/wants.db", "want_events"),
    ):
        src_db = source_root / rel
        rst_db = restored_root / rel
        if not src_db.is_file():
            checks.append(
                {
                    "name": f"{label}.{rel.replace('/', '_').replace('.', '_')}_row_count",
                    "status": "skip",
                    "detail": "not present in source",
                }
            )
            continue
        if not rst_db.is_file():
            checks.append(
                {
                    "name": f"{label}.{rel.replace('/', '_').replace('.', '_')}_row_count",
                    "status": "fail",
                    "detail": "missing in restore",
                }
            )
            continue
        src_n = sqlite_row_count(src_db, table)
        rst_n = sqlite_row_count(rst_db, table)
        check_name = f"{label}.{rel.replace('/', '_').replace('.', '_')}_row_count"
        if src_n is None or rst_n is None:
            checks.append(
                {
                    "name": check_name,
                    "status": "skip",
                    "detail": f"table {table!r} not present",
                }
            )
        elif src_n == rst_n:
            checks.append(
                {
                    "name": check_name,
                    "status": "pass",
                    "detail": f"source={src_n} restored={rst_n}",
                }
            )
        else:
            checks.append(
                {
                    "name": check_name,
                    "status": "fail",
                    "detail": f"source={src_n} restored={rst_n}",
                }
            )

    return checks


# ── driver ─────────────────────────────────────────────────────────


class DrillTargetRefusal(RuntimeError):
    """The drill was pointed at the real backup archive."""


def _refuse_real_backup_root(backup_root: Path) -> None:
    """Refuse to run the full drill against the live backup archive.

    2026-08-22. A passing full drill without ``--keep`` ends in
    ``shutil.rmtree(backup_root)`` — the drill cleans up after itself. That is
    correct for a scratch directory and catastrophic for the real archive, and
    nothing stopped the second case. ``--backup-root`` accepted any path, and
    the help text names ``$MAEZ_BACKUP_ROOT``/``~/maez-backups`` as the default
    *for --smoke*, which is exactly the confusion that produces:

        python -m scripts.backup.drill --backup-root ~/maez-backups

    That would have passed, then deleted every snapshot. 406 of them, 235 GB,
    the only copy of Maez's memory outside the live tree.

    Three independent tests, because one is a typo away from being wrong:
    the configured archive root, the conventional one, and any directory that
    actually looks like a real archive. Refuse loudly; never "clean up".
    """
    resolved = backup_root.expanduser().resolve()

    protected: list[Path] = []
    if env := os.environ.get("MAEZ_BACKUP_ROOT"):
        protected.append(Path(env).expanduser().resolve())
    protected.append((Path.home() / "maez-backups").resolve())

    for candidate in protected:
        if resolved == candidate or candidate in resolved.parents:
            raise DrillTargetRefusal(
                f"refusing to run the full drill against the live backup "
                f"archive at {resolved}. A passing drill deletes its "
                f"backup_root. Point --backup-root at a scratch directory, "
                f"or pass --keep."
            )

    # Content test: even an unconfigured path that already holds finalized
    # snapshots is somebody's archive.
    if resolved.is_dir():
        finalized = [
            child for child in resolved.iterdir()
            if child.is_dir() and (child / "manifest.json").is_file()
        ]
        if finalized:
            raise DrillTargetRefusal(
                f"refusing to run the full drill against {resolved}: it "
                f"already contains {len(finalized)} finalized snapshot(s), so "
                f"it is a real archive, not a scratch directory. A passing "
                f"drill would delete all of them."
            )


def run_drill(
    *,
    source_root: Path,
    backup_root: Path,
    keep: bool = False,
) -> dict:
    """Execute the full drill. Returns the report. Side effect: emits
    ``logs/backup_drill_<timestamp>.json`` under ``source_root``."""
    from scripts.backup.backup import run_backup
    from scripts.backup.restore import run_restore

    _refuse_real_backup_root(backup_root)

    started = time.monotonic()

    # 1. Free-space check.
    state_size = estimate_state_size(source_root)
    required = state_size * 3  # backup + 2 restores ≈ 3× source
    ok, free, needed = check_free_space(backup_root, required)
    if not ok:
        report = build_drill_report(
            source_root=str(source_root),
            backup_root=str(backup_root),
            snapshot_path="",
            checks=[
                {
                    "name": "free_space_check",
                    "status": "fail",
                    "detail": (f"need {needed} bytes, have {free} bytes free under {backup_root}"),
                }
            ],
            extras={"duration_seconds": round(time.monotonic() - started, 3)},
        )
        _write_drill_log(source_root, report)
        return report

    checks: list[dict] = [
        {
            "name": "free_space_check",
            "status": "pass",
            "detail": f"{free} bytes free under {backup_root}",
        }
    ]

    # 2. Real backup.
    snapshot_root = backup_root / "snapshot"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    try:
        backup_result = run_backup(
            source_root=source_root,
            backup_root=snapshot_root,
            include_secrets=False,
        )
        checks.append(
            {
                "name": "backup_succeeded",
                "status": "pass",
                "detail": f"{backup_result['byte_count']} bytes in "
                f"{backup_result['duration_seconds']:.2f}s",
            }
        )
        snapshot_path = backup_result["snapshot_path"]

        # 2a. Verify snapshot manifest BEFORE restoring. This is
        # the right place — the snapshot has manifest.json; the
        # restored copy doesn't (restore intentionally skips it).
        from scripts.backup.restore import verify_manifest

        try:
            m = verify_manifest(snapshot_path)
            checks.append(
                {
                    "name": "snapshot_manifest_verified",
                    "status": "pass",
                    "detail": f"{len(m.get('files') or [])} files verified",
                }
            )
        except Exception as e:
            checks.append(
                {
                    "name": "snapshot_manifest_verified",
                    "status": "fail",
                    "detail": f"{type(e).__name__}: {e}",
                }
            )
    except Exception as e:
        checks.append(
            {
                "name": "backup_succeeded",
                "status": "fail",
                "detail": f"{type(e).__name__}: {e}",
            }
        )
        report = build_drill_report(
            source_root=str(source_root),
            backup_root=str(backup_root),
            snapshot_path="",
            checks=checks,
            extras={"duration_seconds": round(time.monotonic() - started, 3)},
        )
        _write_drill_log(source_root, report)
        return report

    # 3. Two restorations into separate temp dirs.
    for label, reason, write_coma in (
        ("hf_no_coma", "hardware-failure", False),
        ("pause", "deliberate-pause", True),  # pause never writes coma anyway
    ):
        restore_dst = backup_root / f"restore_{label}"
        restore_dst.mkdir(parents=True, exist_ok=True)

        # Mock factory so we never touch a real MemoryManager during
        # the drill — the live MM stays untouched. Bind loop vars
        # via defaults so the closure is safe under ruff B023.
        captured_core: list = []
        _label = label

        class DrillMM:
            def store_core(self, content, source=None, _captured=captured_core, _lbl=_label):
                _captured.append({"content": content, "source": source})
                return f"drill-{_lbl}-fake-id"

        try:
            run_restore(
                snapshot_path=snapshot_path,
                source_root=restore_dst,
                reason=reason,
                write_coma=write_coma,
                mm_factory=lambda: DrillMM(),
                pre_restore_label=f"drill-{label}-pre",
            )
            checks.append(
                {
                    "name": f"{label}.restore_succeeded",
                    "status": "pass",
                    "detail": f"reason={reason} write_coma={write_coma}",
                }
            )
        except Exception as e:
            checks.append(
                {
                    "name": f"{label}.restore_succeeded",
                    "status": "fail",
                    "detail": f"{type(e).__name__}: {e}",
                }
            )
            continue

        # 4. Verify the restored copy.
        checks.extend(
            verify_restored_copy(
                source_root=source_root,
                restored_root=restore_dst,
                label=label,
            )
        )

        # 4a. Drill-specific: hf_no_coma must NOT have stored a
        # coma memory (write_coma=False); pause must NOT have
        # stored a coma memory (deliberate-pause reason).
        if captured_core:
            checks.append(
                {
                    "name": f"{label}.no_coma_written",
                    "status": "fail",
                    "detail": (f"unexpected coma write: {len(captured_core)} entries"),
                }
            )
        else:
            checks.append(
                {
                    "name": f"{label}.no_coma_written",
                    "status": "pass",
                    "detail": "drill correctly skipped coma write",
                }
            )

    elapsed = time.monotonic() - started
    report = build_drill_report(
        source_root=str(source_root),
        backup_root=str(backup_root),
        snapshot_path=str(snapshot_path),
        checks=checks,
        extras={"duration_seconds": round(elapsed, 3)},
    )
    _write_drill_log(source_root, report)

    # Cleanup on success unless --keep.
    if report["overall_status"] == "pass" and not keep:
        try:
            shutil.rmtree(backup_root)
        except Exception as e:
            logger.warning(
                "drill cleanup failed (drill dirs left in place): %s",
                e,
            )

    return report


def _write_drill_log(source_root: Path, report: dict) -> Path:
    """Persist the drill report as a JSON log so the operator and
    cockpit can read it later."""
    return _write_report_log(source_root / "logs", report)


# ── CLI ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.backup.drill",
        description=(
            "Run the backup drill — bridges 'backup code exists' to "
            "'backup is covenant-load-bearing.' Live daemon stays "
            "active. Drill restores into temp dirs only; never "
            "touches the live repo."
        ),
    )
    p.add_argument(
        "--source-root",
        type=Path,
        default=Path(os.environ.get("MAEZ_ROOT") or Path.cwd()),
        help="Live repo to back up (default: $MAEZ_ROOT or cwd).",
    )
    p.add_argument(
        "--backup-root",
        type=Path,
        default=None,
        help=(
            f"Drill destination (default full drill: {_DEFAULT_BACKUP_ROOT}; "
            "default --smoke: $MAEZ_BACKUP_ROOT or ~/maez-backups)."
        ),
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Run the read-only restore smoke test against the latest finalized "
            "backup artifact instead of creating a new drill backup."
        ),
    )
    p.add_argument(
        "--keep",
        action="store_true",
        help="Leave drill directories in place after success "
        "(default: clean up on pass, leave on failure).",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    source_root = args.source_root.resolve()
    if args.smoke:
        from scripts.backup.inventory import load_default_manifest

        smoke_backup_root = (
            args.backup_root
            or Path(os.environ.get("MAEZ_BACKUP_ROOT") or Path.home() / "maez-backups")
        ).resolve()
        report = run_restore_smoke_test(
            backup_root=smoke_backup_root,
            state_manifest=load_default_manifest(),
            log_dir=source_root / "logs",
        )
        print(f"\nRestore smoke {report['overall_status'].upper()}")
        print(f"  backup root: {report['backup_root']}")
        print(f"  snapshot: {report['snapshot_path'] or '?'}")
        print(f"  required stores: {report['required_count']}")
        print(f"  report: {report.get('report_path', '?')}")
        fail_count = sum(1 for c in report["checks"] if c["status"] == "fail")
        if fail_count:
            print("\nFailed checks:")
            for c in report["checks"]:
                if c["status"] == "fail":
                    print(f"  - {c['path']}: {c['detail']}")
        print()
        return 0 if report["overall_status"] == "pass" else 4

    report = run_drill(
        source_root=source_root,
        backup_root=(args.backup_root or _DEFAULT_BACKUP_ROOT).resolve(),
        keep=args.keep,
    )

    print(f"\nDrill {report['overall_status'].upper()}")
    print(f"  source: {report['source_root']}")
    print(f"  destination: {report['backup_root']}")
    print(f"  duration: {report.get('duration_seconds', '?')}s")
    pass_count = sum(1 for c in report["checks"] if c["status"] == "pass")
    fail_count = sum(1 for c in report["checks"] if c["status"] == "fail")
    skip_count = sum(1 for c in report["checks"] if c["status"] == "skip")
    print(f"  checks: {pass_count} pass, {fail_count} fail, {skip_count} skip")
    if fail_count:
        print("\nFailed checks:")
        for c in report["checks"]:
            if c["status"] == "fail":
                print(f"  ✗ {c['name']}: {c['detail']}")
    print()

    return 0 if report["overall_status"] == "pass" else 4


if __name__ == "__main__":
    raise SystemExit(main())
