# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
identity.py — who this Maez belongs to, where they are, what policies apply.

Reads config/identity.yaml (per-user, gitignored). Falls back to the shipped
template if the personal file is missing. Falls back to safe defaults if
neither exists — an unconfigured Maez stays local, never routes externally,
never ingests signals, and addresses its user as "Friend".

No new code should hardcode "the owner", "<OWNER_CITY>", or any other personal
identifier. Always ask through this module.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import yaml

from core import paths

logger = logging.getLogger("maez.identity")

# Conservative defaults if no identity file is loadable at all.
_DEFAULTS = {
    "owner": {
        "display_name": "Friend",
        "user_id": "owner",
        "home_place": "Somewhere",
        "home_lat": 0.0,
        "home_lon": 0.0,
        "timezone": "UTC",
    },
    "policies": {
        "jarvis_tier": False,
        "signal_ingest": False,
        "proactive_messages": True,
    },
}

_cache: dict[str, Any] | None = None
_cache_mtime: float = 0.0
_lock = threading.Lock()


def _merge(base: dict, override: dict) -> dict:
    """Shallow-recursive merge: override wins for leaves."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_raw() -> dict[str, Any]:
    """Load identity.yaml (personal) falling back to template, then defaults."""
    candidates = [
        paths.identity_file(),
        paths.config_dir() / "identity.template.yaml",
    ]
    merged = dict(_DEFAULTS)
    for path in candidates:
        try:
            if path.exists():
                with path.open() as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    merged = _merge(merged, data)
                    logger.debug("identity loaded from %s", path)
                    break
        except Exception as e:
            logger.warning("failed to read %s: %s", path, e)
    return merged


def _get() -> dict[str, Any]:
    """Return identity dict, reloading if the underlying file changed."""
    global _cache, _cache_mtime
    with _lock:
        personal = paths.identity_file()
        try:
            mtime = personal.stat().st_mtime if personal.exists() else 0.0
        except OSError:
            mtime = 0.0
        if _cache is None or mtime != _cache_mtime:
            _cache = _load_raw()
            _cache_mtime = mtime
        return _cache


def reload() -> None:
    """Force a re-read of identity.yaml on next access."""
    global _cache, _cache_mtime
    with _lock:
        _cache = None
        _cache_mtime = 0.0


# ── owner accessors ────────────────────────────────────────────────────
def display_name() -> str:
    return str(_get().get("owner", {}).get("display_name") or "Friend")


def user_profile_id() -> str:
    return str(_get().get("owner", {}).get("user_id") or "owner")


def home_coords() -> tuple[float, float, str]:
    owner = _get().get("owner", {}) or {}
    try:
        lat = float(owner.get("home_lat") or 0.0)
        lon = float(owner.get("home_lon") or 0.0)
    except (TypeError, ValueError):
        lat, lon = 0.0, 0.0
    place = str(owner.get("home_place") or "Somewhere")
    return lat, lon, place


def timezone() -> str:
    return str(_get().get("owner", {}).get("timezone") or "UTC")


# ── policy accessors ───────────────────────────────────────────────────
def has_policy(name: str) -> bool:
    return bool(_get().get("policies", {}).get(name, False))


def jarvis_tier() -> bool:
    return has_policy("jarvis_tier")


def signal_ingest() -> bool:
    return has_policy("signal_ingest")


def proactive_messages() -> bool:
    return has_policy("proactive_messages")


# ── diagnostics ────────────────────────────────────────────────────────
def describe() -> dict[str, Any]:
    """Return the current identity for `maez doctor` output."""
    lat, lon, place = home_coords()
    return {
        "display_name":   display_name(),
        "user_id":        user_profile_id(),
        "place":          place,
        "coords":         {"lat": lat, "lon": lon},
        "timezone":       timezone(),
        "policies": {
            "jarvis_tier":        jarvis_tier(),
            "signal_ingest":      signal_ingest(),
            "proactive_messages": proactive_messages(),
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(describe(), indent=2))
