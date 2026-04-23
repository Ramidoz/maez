# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
maez_surface_paths.py — local replacement for Hermes' `hermes_constants`
module. The vendored platform layer calls `get_hermes_dir(...)` to
resolve cache directories for images, audio, video, and documents.
Map those to Maez's memory tree under `memory/surface/cache/`.
"""
from __future__ import annotations

import os
from pathlib import Path

_MAEZ_SURFACE_ROOT = Path(
    os.environ.get("MAEZ_SURFACE_CACHE_ROOT", "/home/rohit/maez/memory/surface")
)


def get_surface_cache_dir(subpath: str, legacy_name: str = "") -> Path:
    """Return (and create) a cache directory under the Maez surface tree.

    Called by the vendored platform base code — `legacy_name` was the
    second positional arg upstream (used when migrating from the
    original layout) and is accepted for signature compatibility but
    not used here."""
    path = _MAEZ_SURFACE_ROOT / subpath
    path.mkdir(parents=True, exist_ok=True)
    return path


# Keep the upstream name as an alias so vendored call sites resolve
# without edits.
get_hermes_dir = get_surface_cache_dir
