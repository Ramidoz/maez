# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Backup inventory resolver — reads ``backup_state_manifest.json``
and resolves each entry against a source root, expanding globs and
filtering secrets per the caller's opt-in.

This module is the single source of truth for "what gets backed up."
Hardcoding paths in the backup script would mean the list drifts
silently when stateful files are added or removed elsewhere; reading
the manifest at runtime forces the conversation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


_MANIFEST_PATH = Path(__file__).resolve().parent / "backup_state_manifest.json"

_VALID_TYPES: frozenset[str] = frozenset({
    "sqlite_db", "directory", "file", "glob", "secret_file",
})


class BackupInventoryError(Exception):
    """Raised when a required inventory entry is missing or the
    manifest itself is malformed."""


def load_default_manifest() -> dict:
    """Read the canonical manifest shipped with the backup package."""
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def resolve_inventory(
    manifest: dict,
    source_root: Path | str,
    *,
    include_secrets: bool,
) -> list[dict]:
    """Resolve a manifest into a concrete list of entries against the
    given ``source_root``.

    Each returned entry includes the original metadata plus:
    - ``resolved_paths``: list of repo-relative ``Path`` objects.
      For sqlite_db / file / secret_file → exactly one path (if it
      exists). For directory → exactly one path. For glob → zero or
      more matched paths.

    Behavior:
    - Required entries that are missing raise ``BackupInventoryError``.
    - Optional entries that are missing are silently skipped (omitted
      from the result).
    - Secret entries are excluded unless ``include_secrets=True`` —
      the caller is expected to display the manifest's
      ``secret_warning`` to the operator before flipping that flag.
    """
    root = Path(source_root)
    entries = manifest.get("entries") or []
    if not isinstance(entries, list):
        raise BackupInventoryError(
            "manifest 'entries' must be a list"
        )

    out: list[dict] = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise BackupInventoryError(
                f"manifest entry #{i} must be an object"
            )
        etype = e.get("type")
        if etype not in _VALID_TYPES:
            raise BackupInventoryError(
                f"manifest entry #{i} has invalid type {etype!r}; "
                f"expected one of {sorted(_VALID_TYPES)}"
            )
        rel = e.get("path")
        if not isinstance(rel, str) or not rel:
            raise BackupInventoryError(
                f"manifest entry #{i} missing 'path'"
            )
        required = bool(e.get("required", False))

        # Secret gate.
        if etype == "secret_file" and not include_secrets:
            continue

        # Resolve.
        if etype == "glob":
            matches = sorted(root.glob(rel))
            if not matches:
                if required:
                    raise BackupInventoryError(
                        f"required glob {rel!r} matched nothing under "
                        f"{root}"
                    )
                continue
            resolved = list(matches)
        else:
            target = root / rel
            if not target.exists():
                if required:
                    raise BackupInventoryError(
                        f"required path {rel!r} does not exist under "
                        f"{root}"
                    )
                continue
            resolved = [target]

        out.append({
            **e,
            "resolved_paths": resolved,
        })
    return out


__all__ = [
    "BackupInventoryError",
    "load_default_manifest",
    "resolve_inventory",
]
