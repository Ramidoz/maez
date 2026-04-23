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
import os
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
        # Phase 2 additions — fields that used to be hardcoded across
        # modules. All optional; leave blank when unknown.
        "git_handle": "",
        "telegram_user_id": "",
        "machine_profile": "",
    },
    "policies": {
        "jarvis_tier": False,
        "signal_ingest": False,
        "proactive_messages": True,
    },
}


# Environment variable overrides. When set, they win over identity.yaml
# and the defaults — useful for CI / containers / scripted installs
# where editing a YAML file is awkward. Each field accepts a list of
# env keys tried in order so pre-existing names (e.g.
# MAEZ_TELEGRAM_USER_ID) stay valid alongside the new MAEZ_OWNER_* scheme.
_ENV_OVERRIDES: dict[str, tuple[str, ...]] = {
    "display_name":      ("MAEZ_OWNER_NAME",),
    "user_id":           ("MAEZ_OWNER_USER_ID",),
    "git_handle":        ("MAEZ_OWNER_GIT_HANDLE",),
    "telegram_user_id":  ("MAEZ_OWNER_TELEGRAM_ID", "MAEZ_TELEGRAM_USER_ID"),
    "machine_profile":   ("MAEZ_MACHINE_PROFILE",),
    "home_place":        ("MAEZ_OWNER_HOME_PLACE",),
    "timezone":          ("MAEZ_OWNER_TIMEZONE",),
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
def _owner_field(field: str, default: str = "") -> str:
    """Read an owner field, letting any of the MAEZ_OWNER_* env vars
    win if set. Env keys are tried in order — the first non-empty one
    wins — so a new canonical name and a legacy alias can co-exist."""
    for env_key in _ENV_OVERRIDES.get(field, ()):
        v = os.environ.get(env_key)
        if v:
            return v
    return str(_get().get("owner", {}).get(field) or default)


def display_name() -> str:
    return _owner_field("display_name", "Friend")


def user_profile_id() -> str:
    return _owner_field("user_id", "owner")


def git_handle() -> str:
    """GitHub/GitLab handle for the owner. Empty string when unknown.
    Used anywhere code needs to post commits / file issues against the
    owner's account. Do not hardcode — always read through this.
    """
    return _owner_field("git_handle", "")


def telegram_user_id() -> str:
    """Numeric Telegram user ID the daemon DMs. Empty string when the
    Telegram surface is not in use. Readers should treat empty as
    'no Telegram owner configured' and skip push notifications.
    """
    return _owner_field("telegram_user_id", "")


def machine_profile() -> str:
    """Short human-readable string describing the host hardware, e.g.
    'Alienware R16 + RTX 4090, Ubuntu 24.04'. Used in logs / perception
    summaries. Empty string when unknown — consumers must tolerate that.
    """
    return _owner_field("machine_profile", "")


def home_coords() -> tuple[float, float, str]:
    owner = _get().get("owner", {}) or {}
    try:
        lat = float(owner.get("home_lat") or 0.0)
        lon = float(owner.get("home_lon") or 0.0)
    except (TypeError, ValueError):
        lat, lon = 0.0, 0.0
    place = _owner_field("home_place", "Somewhere")
    return lat, lon, place


def timezone() -> str:
    return _owner_field("timezone", "UTC")


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
        "display_name":      display_name(),
        "user_id":           user_profile_id(),
        "git_handle":        git_handle(),
        "telegram_user_id":  telegram_user_id(),
        "machine_profile":   machine_profile(),
        "place":             place,
        "coords":            {"lat": lat, "lon": lon},
        "timezone":          timezone(),
        "policies": {
            "jarvis_tier":        jarvis_tier(),
            "signal_ingest":      signal_ingest(),
            "proactive_messages": proactive_messages(),
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(describe(), indent=2))
