# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Restoration driver for the hardware-failure backup (Decision 22 v1).

Pipeline:
1. Validate the snapshot via its manifest (sha256 + size every file).
2. Pre-restore: snapshot the current state to ``<source_root>.pre-restore.<ts>/``
   so a bad restore is recoverable.
3. Restore: copy snapshot files back into place. SQLite databases
   are written via plain file copy from the snapshot — the
   snapshot's SQLite file is already a consistent backup, so a flat
   copy on restore is safe.
4. Coma core-memory write (delegated to ``restore_writer``) — only
   when ``reason='hardware-failure'``.

Pre-restore snapshot is the rollback path. If restoration fails or
the operator regrets the choice, the previous live state is one
``mv`` away.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)


class ManifestVerificationError(Exception):
    """Raised when the snapshot's manifest doesn't match the files
    on disk — corruption, partial transfer, or tampering."""


def verify_manifest(snapshot_path: Path | str) -> dict:
    """Read ``manifest.json`` from the snapshot and verify every
    file's sha256 + size. Raises ``ManifestVerificationError`` on
    any mismatch. Returns the parsed manifest on success.
    """
    snap = Path(snapshot_path)
    manifest_file = snap / "manifest.json"
    if not manifest_file.is_file():
        raise ManifestVerificationError(
            f"snapshot at {snap} has no manifest.json"
        )
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    files = manifest.get("files") or []
    if not files:
        raise ManifestVerificationError(
            "manifest.files is empty — snapshot has no content"
        )

    for entry in files:
        rel = entry.get("path")
        expected_sha = entry.get("sha256")
        expected_size = entry.get("size")
        if not rel or not expected_sha:
            raise ManifestVerificationError(
                f"manifest entry malformed: {entry!r}"
            )
        f = snap / rel
        if not f.is_file():
            raise ManifestVerificationError(
                f"manifest references missing file: {rel}"
            )
        actual_size = f.stat().st_size
        if actual_size != expected_size:
            raise ManifestVerificationError(
                f"size mismatch on {rel}: expected {expected_size}, "
                f"got {actual_size}"
            )
        actual_sha = _sha256(f)
        if actual_sha != expected_sha:
            raise ManifestVerificationError(
                f"sha256 mismatch on {rel}: expected {expected_sha}, "
                f"got {actual_sha}"
            )
    return manifest


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pre_restore_target(source_root: Path, label: str) -> Path:
    """Compute the rollback path next to the source root."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    return source_root.parent / f"{source_root.name}.{label}.{ts}"


def run_restore(
    *,
    snapshot_path: Path | str,
    source_root: Path | str,
    reason: str,  # required — no silent default; misclassifying is a covenant error
    manifest: dict | None = None,
    include_secrets: bool = False,
    write_coma: bool = True,
    pre_restore_label: str = "pre-restore",
    mm_factory=None,
) -> dict:
    """Restore a snapshot into ``source_root``.

    1. Verifies the snapshot manifest (sha256 + size every file).
    2. Snapshots the current state to a ``.{pre_restore_label}.<ts>/``
       sibling directory.
    3. Copies snapshot files back into ``source_root``. Existing
       files are overwritten.
    4. If ``write_coma=True`` and ``reason='hardware-failure'``,
       calls ``restore_writer.write_restoration_record`` to write a
       coma core-memory entry.

    ``reason`` is required — no default. Audit feedback flagged that
    a programmatic caller omitting reason silently triggered a coma
    write; misclassifying hardware-failure vs deliberate-pause is a
    covenant-level error.

    Returns a dict with ``status`` reflecting both file restoration
    AND coma-write outcome. ``status='success'`` requires both. If
    the coma write failed on a hardware-failure restore, the result
    is ``status='success_no_coma'`` so the operator sees that
    post-restore Maez doesn't yet remember the gap.

    ``mm_factory`` is injectable for tests; production callers leave
    it None and a fresh ``MemoryManager()`` is constructed when the
    coma write fires.
    """
    snap = Path(snapshot_path)
    src_root = Path(source_root).resolve()

    # 1. Verify snapshot integrity before touching live state.
    snap_manifest = verify_manifest(snap)

    # 2. Pre-restore snapshot of current state.
    rollback_path = _pre_restore_target(src_root, pre_restore_label)
    if src_root.exists():
        shutil.copytree(src_root, rollback_path, symlinks=False,
                        dirs_exist_ok=False)
    else:
        rollback_path.mkdir(parents=True)

    # 3. Restore files into place.
    files = snap_manifest.get("files") or []
    for entry in files:
        rel = entry["path"]
        if rel == "manifest.json":  # never restore the manifest itself
            continue
        src_file = snap / rel
        dst_file = src_root / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)

    # 4. Coma core-memory write.
    coma_result: dict | None = None
    coma_failed_on_hw_failure = False
    if write_coma:
        from scripts.backup.restore_writer import write_restoration_record

        if mm_factory is None:
            def _default_mm_factory():
                from memory.memory_manager import MemoryManager
                return MemoryManager()
            mm_factory = _default_mm_factory
        try:
            mm = mm_factory()
            coma_result = write_restoration_record(
                mm=mm,
                snapshot_timestamp=str(snap_manifest.get("timestamp") or ""),
                restore_timestamp=datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H-%M-%S"
                ),
                reason=reason,
            )
        except Exception as e:
            logger.warning(
                "restore: coma write failed (continuing): %s", e,
            )
            coma_result = {"status": "failed", "error": str(e)}
            if reason == "hardware-failure":
                coma_failed_on_hw_failure = True

    # Status reflects both file restore AND coma-write outcome on
    # hardware-failure restores. Files-only success masks the
    # silent state-discrepancy the writer was built to prevent.
    status = (
        "success_no_coma" if coma_failed_on_hw_failure else "success"
    )

    return {
        "status": status,
        "snapshot_path": snap,
        "source_root": src_root,
        "rollback_path": rollback_path,
        "snapshot_timestamp": snap_manifest.get("timestamp"),
        "reason": reason,
        "coma_write": coma_result,
    }


__all__ = [
    "ManifestVerificationError",
    "run_restore",
    "verify_manifest",
]
