# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
paths.py — single source of truth for filesystem locations.

Every Maez file that reads or writes the filesystem should go through this
module. Nothing should ever hardcode "/home/rohit/maez/..." in new code.

On the owner's machine today, all defaults resolve to the existing layout so
nothing moves and nothing breaks. On a friend's future install, one
environment variable (`MAEZ_HOME`) redirects everything.

Environment overrides (all optional):
    MAEZ_HOME    root of the Maez installation       default: /home/rohit/maez
    MAEZ_CONFIG  location of config files            default: $MAEZ_HOME/config
    MAEZ_DATA    location of data (memory/logs/etc.) default: $MAEZ_HOME
    MAEZ_CACHE   cache directory                     default: $MAEZ_HOME/.cache

Path categories:
    code/     shipped with the repo (core, skills, daemon, ui, cli)
    config/   user-personalized (soul.local.md, identity.yaml, .env)
    data/     personal state (memory DBs, signals, trajectories, logs)
    cache/    disposable regenerables (compiled caches, HF downloads)
    models/   downloaded model files — often on a different disk
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_HOME = "/home/rohit/maez"


# ── core locations ─────────────────────────────────────────────────────
def home() -> Path:
    """Root of the Maez installation. Overridable via $MAEZ_HOME."""
    return Path(os.environ.get("MAEZ_HOME", _DEFAULT_HOME))


def config_dir() -> Path:
    """Where user-personalized config lives. Overridable via $MAEZ_CONFIG."""
    override = os.environ.get("MAEZ_CONFIG")
    return Path(override) if override else home() / "config"


def data_dir() -> Path:
    """Where Maez stores its persistent state. Overridable via $MAEZ_DATA."""
    override = os.environ.get("MAEZ_DATA")
    return Path(override) if override else home()


def cache_dir() -> Path:
    """Disposable caches (HF downloads, compiled artifacts). Overridable via $MAEZ_CACHE."""
    override = os.environ.get("MAEZ_CACHE")
    return Path(override) if override else home() / ".cache"


# ── code directories (always under home, not data) ─────────────────────
def core_dir() -> Path:
    return home() / "core"


def skills_dir() -> Path:
    return home() / "skills"


def daemon_dir() -> Path:
    return home() / "daemon"


def ui_dir() -> Path:
    return home() / "ui"


def cli_dir() -> Path:
    return home() / "cli"


def docs_dir() -> Path:
    return home() / "docs"


# ── data directories (can live on a different disk via $MAEZ_DATA) ─────
def memory_dir() -> Path:
    return data_dir() / "memory"


def memory_db_dir() -> Path:
    return memory_dir() / "db"


def logs_dir() -> Path:
    return data_dir() / "logs"


def snapshots_dir() -> Path:
    return logs_dir() / "snapshots"


def signals_dir() -> Path:
    return logs_dir() / "signals"


def trajectories_dir() -> Path:
    return logs_dir() / "trajectories"


def maez_notes_path() -> Path:
    """Persistent scratch notepad. Gitignored, local-only."""
    return logs_dir() / "maez_notes.md"


def wonderings_db() -> Path:
    """Sqlite DB for the daemon's exploratory-mind state.
    Mirrors dream_proposals.db — personal, gitignored."""
    return memory_dir() / "wonderings.db"


# ── training + models (often on a separate volume) ─────────────────────
def training_dir() -> Path:
    return home() / "training"


def models_dir() -> Path:
    return home() / "models"


# ── key files ──────────────────────────────────────────────────────────
def env_file() -> Path:
    return config_dir() / ".env"


def soul_base_path() -> Path:
    """Shippable universal SOUL template."""
    return config_dir() / "soul.base.md"


def soul_local_path() -> Path:
    """Per-user SOUL additions (dream proposals, personal mutations)."""
    return config_dir() / "soul.local.md"


def soul_combined_path() -> Path:
    """Legacy single-file SOUL. Still read by code that hasn't been
    retrofitted to the base+local layering yet."""
    return config_dir() / "soul.md"


def identity_file() -> Path:
    return config_dir() / "identity.yaml"


def user_profiles_file() -> Path:
    return config_dir() / "user_profiles.yaml"


# ── convenience ────────────────────────────────────────────────────────
_ENSURED = False


def ensure_dirs() -> None:
    """Create the standard directory tree if missing.

    Idempotent. Safe to call multiple times. Caches its result so repeated
    invocations are free after the first.
    """
    global _ENSURED
    if _ENSURED:
        return
    for d in (
        home(), config_dir(), data_dir(), cache_dir(),
        memory_dir(), memory_db_dir(),
        logs_dir(), snapshots_dir(), signals_dir(), trajectories_dir(),
        training_dir(), models_dir(),
    ):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # non-fatal; caller will see the issue on actual access
    _ENSURED = True


# ── diagnostics ────────────────────────────────────────────────────────
def describe() -> dict[str, str]:
    """Return all resolved paths as a dict. Useful for `maez doctor`."""
    return {
        "home":             str(home()),
        "config":           str(config_dir()),
        "data":             str(data_dir()),
        "cache":            str(cache_dir()),
        "core":             str(core_dir()),
        "skills":           str(skills_dir()),
        "daemon":           str(daemon_dir()),
        "ui":               str(ui_dir()),
        "cli":              str(cli_dir()),
        "docs":             str(docs_dir()),
        "memory":           str(memory_dir()),
        "memory_db":        str(memory_db_dir()),
        "logs":             str(logs_dir()),
        "snapshots":        str(snapshots_dir()),
        "signals":          str(signals_dir()),
        "trajectories":     str(trajectories_dir()),
        "training":         str(training_dir()),
        "models":           str(models_dir()),
        "env_file":         str(env_file()),
        "soul_base":        str(soul_base_path()),
        "soul_local":       str(soul_local_path()),
        "soul_combined":    str(soul_combined_path()),
        "identity":         str(identity_file()),
        "user_profiles":    str(user_profiles_file()),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(describe(), indent=2))
