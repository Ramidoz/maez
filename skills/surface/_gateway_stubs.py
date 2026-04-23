# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
_gateway_stubs.py — no-op implementations of the Hermes `gateway/*`
modules that the vendored platform code reaches for via lazy imports
but that Maez doesn't need.

Three capability areas are stubbed here:

  1. `gateway.status.*` — Hermes writes a runtime-status JSON file and
     enforces a process-wide lock to prevent two gateways from polling
     the same bot token. For Maez, systemd + the daemon's own locks
     cover this; we no-op the status writes and always-grant the
     lock (the lock's purpose — "only one gateway per token" — is
     enforced at the Maez systemd level, not at library level).

  2. `gateway.sticker_cache.*` — sticker caching for Telegram. Maez
     doesn't send stickers; stubs raise a clean "not supported" error
     if the code path is ever reached.

  3. Anything else we later discover — add here rather than re-vendor
     a full upstream module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


# ── gateway.status stubs ────────────────────────────────────────────────

def write_runtime_status(
    *args: Any,
    **kwargs: Any,
) -> None:
    """No-op. Upstream writes a JSON status file for external health
    monitoring. Maez has its own health endpoint + cognition.log for
    this purpose, so we don't need the status file."""
    return None


def acquire_scoped_lock(
    scope: str,
    identity: str,
    *args: Any,
    **kwargs: Any,
) -> tuple[bool, dict]:
    """Upstream acquires a filesystem lock to ensure only one gateway
    process polls a given bot token. Maez's systemd service model
    already guarantees a single daemon instance, so we always return
    (True, {}) meaning "acquired, no prior holder". If an operator
    ever runs two Maez daemons against the same token, that's a
    systemd / supervision issue, not a library one.

    Upstream caller signature:
        acquired, existing = acquire_scoped_lock(scope, identity, metadata=...)
    """
    return (True, {})


def release_scoped_lock(*args: Any, **kwargs: Any) -> None:
    """Paired no-op with acquire_scoped_lock."""
    return None


# ── gateway.sticker_cache stubs ─────────────────────────────────────────

def get_cached_sticker_path(*args: Any, **kwargs: Any) -> Optional[Path]:
    """No-op — Maez doesn't cache stickers. If the sticker path is
    ever requested, returning None lets the caller fall through to
    the 'sticker not available' branch."""
    return None


def cache_sticker(*args: Any, **kwargs: Any) -> Optional[Path]:
    """No-op."""
    return None


def sticker_cache_dir(*args: Any, **kwargs: Any) -> Optional[Path]:
    """No-op."""
    return None


# ── hermes_cli.commands stubs ───────────────────────────────────────────

def should_bypass_active_session(*args: Any, **kwargs: Any) -> bool:
    """Upstream returns True when the user is in an active CLI
    session and the Telegram side should defer. Maez has no such
    coupling between CLI and Telegram; always return False (never
    bypass)."""
    return False


def telegram_menu_commands(*args: Any, **kwargs: Any) -> tuple[list, int]:
    """Upstream returns `(menu_commands, hidden_count)` — a list of
    (name, description) tuples for Telegram's `setMyCommands`, plus
    how many were hidden by the 100-command cap. Maez's CLI doesn't
    push menu entries through the surface layer, so we return
    `([], 0)` — no commands to register, none hidden."""
    return ([], 0)


# ── hermes_cli.providers stubs ──────────────────────────────────────────

def get_label(*args: Any, **kwargs: Any) -> str:
    """Upstream returns a human-readable label for the current LLM
    provider. Maez doesn't expose provider switching through the
    surface layer; return an empty string."""
    return ""


# ── hermes_constants stubs ──────────────────────────────────────────────

def get_hermes_home(*args: Any, **kwargs: Any) -> Path:
    """Upstream returns the Hermes runtime home directory. For
    Maez, this is the memory/surface directory (same root as
    maez_surface_paths.get_surface_cache_dir)."""
    from skills.surface.maez_surface_paths import _MAEZ_SURFACE_ROOT
    _MAEZ_SURFACE_ROOT.mkdir(parents=True, exist_ok=True)
    return _MAEZ_SURFACE_ROOT
