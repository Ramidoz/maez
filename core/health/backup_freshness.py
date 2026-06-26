"""Read-only backup freshness classification.

Fresh means the latest finalized backup is recent and covers every required
state path. Errors fail soft to ``unavailable`` so the operator rail never
reports a false green.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


FRESH_MAX_AGE_H = 13
_TS_FMT = "%Y-%m-%dT%H-%M-%S"


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.strptime(value[:19], _TS_FMT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_path_covered(required_path: str, backed_paths: set[str]) -> bool:
    if required_path in backed_paths:
        return True
    prefix = required_path.rstrip("/") + "/"
    return any(path.startswith(prefix) for path in backed_paths)


def backup_freshness(*, backup_root, required_paths, now=None) -> str:
    now_dt = now or datetime.now(timezone.utc)
    root = Path(backup_root)
    if not root.is_dir():
        return "unavailable"

    try:
        finalized = [
            path
            for path in root.iterdir()
            if path.is_dir()
            and path.name != ".in-progress"
            and (path / "manifest.json").is_file()
        ]
    except OSError:
        return "unavailable"
    if not finalized:
        return "unavailable"

    latest = max(finalized, key=lambda path: path.name)
    try:
        manifest = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unavailable"

    ts = _parse_ts(str(manifest.get("timestamp") or latest.name))
    if ts is None:
        return "unavailable"
    if ts > now_dt:
        return "unavailable"

    age_h = (now_dt - ts).total_seconds() / 3600.0
    if age_h >= FRESH_MAX_AGE_H:
        return "stale"

    backed_paths = {
        str(file.get("path"))
        for file in manifest.get("files") or ()
        if isinstance(file, dict) and file.get("path")
    }
    if any(not _is_path_covered(path, backed_paths) for path in set(required_paths)):
        return "coverage_gap"
    return "fresh"
