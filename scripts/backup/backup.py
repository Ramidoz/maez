# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Hardware-failure backup driver (Decision 22 v1).

Implements the v1 spec from the 2026-04-30 design conversation:

- One backup inventory file as source of truth (``inventory.py``).
- SQLite databases backed up via ``sqlite3.Connection.backup`` (NOT
  rsync of live files — would corrupt under WAL).
- Atomic snapshot staging: builds under
  ``$BACKUP_ROOT/.in-progress/<timestamp>/``, renames to
  ``$BACKUP_ROOT/<timestamp>/`` only on success.
- Manifest with sha256 of every backed-up file, written before the
  rename so corruption can be detected at restore time.
- ``logs/last_backup.json`` updated for owner observability.

Chroma consistency note for v1: the backup runs against live files.
Chroma uses SQLite (covered by the SQLite-safe path) plus binary
HNSW indexes (rsync'd as files). Restore reopens them; if they're
inconsistent, restore fails and falls back to the previous snapshot.
The owner is expected to briefly stop the daemon for the highest
covenant load (manual run before risky ops); the 6h cadence accepts
that 6h of lived state can replay if a snapshot was caught mid-write.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.backup.inventory import (
    BackupInventoryError,
    load_default_manifest,
    resolve_inventory,
)

logger = logging.getLogger(__name__)

_BACKUP_VERSION = 1
_DEFAULT_TIMESTAMP_FMT = "%Y-%m-%dT%H-%M-%S"


# ── path helpers ────────────────────────────────────────────────────


def _staging_path(backup_root: Path, timestamp: str) -> Path:
    return backup_root / ".in-progress" / timestamp


def _final_path(backup_root: Path, timestamp: str) -> Path:
    return backup_root / timestamp


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).strftime(_DEFAULT_TIMESTAMP_FMT)


def _git_commit() -> str:
    """Best-effort current commit hash. Returns empty string on
    failure; the manifest still works without it."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent.parent,
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ── SQLite-safe backup ──────────────────────────────────────────────


def backup_sqlite(src: Path, dst: Path) -> None:
    """Use SQLite's online backup API to copy ``src`` to ``dst``.

    This is safe under concurrent writes: SQLite's backup() acquires
    appropriate page-level locks and produces a consistent snapshot.
    rsync of a live SQLite file in WAL mode would capture an
    inconsistent state; this is the only correct path.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    src_con = sqlite3.connect(str(src))
    try:
        dst_con = sqlite3.connect(str(dst))
        try:
            src_con.backup(dst_con)
        finally:
            dst_con.close()
    finally:
        src_con.close()


# ── per-entry copy logic ────────────────────────────────────────────


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# SQLite filenames we must route through sqlite3 .backup() even
# when they appear INSIDE a directory entry. Chroma stores its
# core state at memory/db/chroma.sqlite3; flat-copying a live
# WAL-mode SQLite file can capture an inconsistent state Chroma
# refuses to reopen. Both audits flagged this as the single
# biggest correctness gap in the v1 design.
_SQLITE_FILENAMES_INSIDE_DIRS: frozenset[str] = frozenset({
    "chroma.sqlite3",
})


def _copy_directory(src: Path, dst: Path) -> None:
    """Copy a directory tree, but route SQLite files inside it
    through SQLite's online backup API (not flat file copy) so
    Chroma's chroma.sqlite3 doesn't capture mid-WAL state.
    """
    if dst.exists():
        shutil.rmtree(dst)
    # Walk-and-copy so we can intercept SQLite files.
    for src_path in src.rglob("*"):
        rel = src_path.relative_to(src)
        dst_path = dst / rel
        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue
        # Files only past this point.
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.name in _SQLITE_FILENAMES_INSIDE_DIRS:
            backup_sqlite(src_path, dst_path)
            continue
        # Skip SQLite WAL/shm sidecars — they're meaningful only
        # alongside a live .sqlite3 file. The .backup() path above
        # produces a self-contained snapshot that doesn't need them.
        if src_path.suffix in {".sqlite3-wal", ".sqlite3-shm"}:
            continue
        shutil.copy2(src_path, dst_path)
    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)


def _walk_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    out: list[Path] = []
    for p in path.rglob("*"):
        if p.is_file():
            out.append(p)
    return out


# ── main backup driver ─────────────────────────────────────────────


def run_backup(
    *,
    source_root: Path | str,
    backup_root: Path | str,
    manifest: dict | None = None,
    include_secrets: bool = False,
    timestamp: str | None = None,
) -> dict:
    """Build a backup snapshot atomically under ``backup_root``.

    Returns a dict describing the result with ``snapshot_path``,
    ``timestamp``, ``status``, ``duration_seconds``, ``byte_count``.
    Raises if any required entry is missing, if the SQLite backup
    fails, or if the manifest write fails. On exception the partial
    snapshot is left under ``.in-progress/<timestamp>/`` for the
    operator to inspect; ``<timestamp>/`` (the final path) is never
    created on failure.
    """
    src_root = Path(source_root).resolve()
    bk_root = Path(backup_root).resolve()
    if manifest is None:
        manifest = load_default_manifest()
    ts = timestamp or _now_timestamp()
    staging = _staging_path(bk_root, ts)
    final = _final_path(bk_root, ts)

    started = time.monotonic()
    log_status = "failure"
    log_error = ""
    snapshot_size = 0

    try:
        # Validate inventory before touching disk.
        resolved = resolve_inventory(
            manifest, src_root, include_secrets=include_secrets,
        )
        if not resolved:
            raise BackupInventoryError(
                "backup inventory resolved zero paths; refusing successful empty backup"
            )

        staging.mkdir(parents=True, exist_ok=True)

        # Per-entry copy. Track manifest entries as we go.
        manifest_files: list[dict[str, Any]] = []
        for entry in resolved:
            etype = entry["type"]
            for src in entry["resolved_paths"]:
                rel = src.relative_to(src_root)
                dst = staging / rel
                if etype == "sqlite_db":
                    backup_sqlite(src, dst)
                elif etype == "directory":
                    _copy_directory(src, dst)
                elif etype in {"file", "secret_file"}:
                    _copy_file(src, dst)
                elif etype == "glob":
                    _copy_file(src, dst)
                else:  # pragma: no cover — guarded by inventory validation
                    raise BackupInventoryError(
                        f"unknown type {etype!r} reached backup driver"
                    )

                # Manifest entries: walk the destination tree to capture
                # one record per actual file (directories expand here).
                for f in _walk_files(dst):
                    rel_f = f.relative_to(staging)
                    size = f.stat().st_size
                    manifest_files.append({
                        "path": str(rel_f),
                        "size": size,
                        "sha256": _sha256_of_file(f),
                        "source_type": etype,
                    })
                    snapshot_size += size

        # Manifest.
        manifest_doc = {
            "backup_version": _BACKUP_VERSION,
            "timestamp": ts,
            "source_root": str(src_root),
            "git_commit": _git_commit(),
            "include_secrets": include_secrets,
            "secret_warning": manifest.get("secret_warning", ""),
            "files": manifest_files,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest_doc, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        # Atomic rename to the final destination. If this ever becomes
        # cross-device, fail loudly instead of publishing a non-atomic
        # finalized snapshot that could masquerade as covenant-safe.
        final.parent.mkdir(parents=True, exist_ok=True)
        staging.rename(final)
        log_status = "success"
    except Exception as e:
        log_error = f"{type(e).__name__}: {e}"
        raise
    finally:
        elapsed = time.monotonic() - started
        _update_last_backup_log(
            source_root=src_root,
            status=log_status,
            timestamp=ts,
            snapshot_path=final if log_status == "success" else staging,
            duration_seconds=elapsed,
            byte_count=snapshot_size,
            error=log_error,
        )

    return {
        "status": log_status,
        "timestamp": ts,
        "snapshot_path": final,
        "duration_seconds": elapsed,
        "byte_count": snapshot_size,
    }


def _update_last_backup_log(
    *,
    source_root: Path,
    status: str,
    timestamp: str,
    snapshot_path: Path,
    duration_seconds: float,
    byte_count: int,
    error: str,
) -> None:
    """Owner observability: a single JSON file the cockpit can read
    to display latest-backup state. Best-effort — log write failures
    must not mask the actual backup failure (if any)."""
    try:
        log_dir = source_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "last_backup.json"
        log_path.write_text(
            json.dumps({
                "status": status,
                "timestamp": timestamp,
                "snapshot_path": str(snapshot_path),
                "duration_seconds": round(duration_seconds, 3),
                "byte_count": byte_count,
                "git_commit": _git_commit(),
                "error": error,
            }, indent=2),
            encoding="utf-8",
        )
    except Exception as e:  # pragma: no cover — observability best-effort
        logger.warning(
            "last_backup.json write failed (ignored): %s", e,
        )


__all__ = [
    "backup_sqlite",
    "run_backup",
    "_staging_path",
    "_final_path",
]
