# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""body_capabilities.py — runtime-verifiable source of truth for
what Maez actually has access to in its own systemd-managed body.

R2 from the 2026-05-04 symphony audit. Companion to
core/infra/capability_registry.py: the registry tracks abstract
capability state (services, modules, schedules) at the file-system
and systemd layer. THIS module probes the actual reachability of
runtime resources — binaries on PATH, environment variables visible
to the daemon process, localhost services answering on TCP, the X
desktop session, the sudo path.

The Firefox-tabs incident exposed the gap this fills: Maez offered
`wmctrl` and `xdotool` despite neither being installed (`wmctrl`)
or reachable (X session unreachable from the systemd unit even
though `DISPLAY` is set). Codex's gatekeeper correction further
sharpened: env-var-set ≠ session-reachable. The probe must actually
try, with a tight timeout.

This module DOES NOT modify prompt construction, offer composition,
or the action engine — those are R3-R5 wiring tasks. R2 only builds
the introspection surface so downstream consumers have a single
honest source of truth to consult.

Usage:
    from core.infra import body_capabilities as bc
    info = bc.body_capabilities()  # cached for TTL window
    if not bc.has_binary("wmctrl"):
        # don't suggest wmctrl in the offer
        ...
    if not bc.is_service_reachable("127.0.0.1", 8081):
        # don't claim the judge endpoint
        ...

Cache:
    body_capabilities() caches its full probe for
    _BODY_CAPABILITIES_TTL_S seconds. invalidate_cache() forces a
    re-probe (used by tests + after a known capability change like
    `apt install <binary>`).
"""
from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import time
from typing import Any, Optional

logger = logging.getLogger("maez.body_capabilities")

# Cache TTL — short enough that capability changes (binary installed,
# service started, sudo configured) become visible within a minute;
# long enough that per-cycle prompt construction doesn't compound the
# subprocess cost. The TTL itself is env-overridable for tests.
_BODY_CAPABILITIES_TTL_S = float(
    os.environ.get("MAEZ_BODY_CAPABILITIES_TTL_S", "60"),
)

# The known list of binaries Maez might claim or suggest. Probed on
# every cache miss. Keep the list bounded — adding speculative names
# inflates cache-miss cost.
_BINARIES_TO_PROBE = (
    # Desktop / window-management — the wmctrl class
    "wmctrl", "xdotool", "dbus-send",
    # Version control
    "git",
    # Network
    "curl", "wget",
    # Privilege escalation
    "sudo",
    # Package managers
    "apt-get", "apt", "snap", "flatpak", "pip",
    # Common shell utilities Maez references
    "jq", "rg", "fd", "tree",
    # Process / file inspection
    "ps", "ss", "lsof",
)

# Localhost services Maez talks to. Each tuple: (key, host, port).
_SERVICES_TO_PROBE = (
    ("brain_8080", "127.0.0.1", 8080),    # primary llama-server
    ("ollama_11434", "127.0.0.1", 11434),  # alt brain
    ("daemon_11435", "127.0.0.1", 11435),  # daemon REST
    ("daemon_ws_11436", "127.0.0.1", 11436),  # daemon WebSocket
    ("web_11437", "127.0.0.1", 11437),    # web cockpit
    ("proxy_11438", "127.0.0.1", 11438),  # subscription proxy
    ("minicheck_8083", "127.0.0.1", 8083),  # support verifier
    ("searxng_8888", "127.0.0.1", 8888),  # local search backend
)

# Env vars relevant to desktop / X / Wayland / DBus reach.
_ENV_VARS_TO_PROBE = (
    "DISPLAY", "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "WAYLAND_DISPLAY",
    "XDG_RUNTIME_DIR",
    "USER", "HOME",
)

# ── cache state ──────────────────────────────────────────────────────

_cache: Optional[dict[str, Any]] = None
_cache_ts: float = 0.0


def invalidate_cache() -> None:
    """Force the next body_capabilities() call to re-probe."""
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


# ── individual probes ────────────────────────────────────────────────

def has_binary(name: str) -> bool:
    """Return True iff `name` resolves on PATH (shutil.which).
    Direct probe — does NOT consult the cache, so tests / one-off
    consumers can ask without forcing a full body_capabilities()
    refresh. shutil.which is cheap (no subprocess)."""
    if not name:
        return False
    return shutil.which(name) is not None


def is_service_reachable(
    host: str, port: int, *, timeout_s: float = 0.5,
) -> bool:
    """TCP-connect probe. Returns True iff a socket connect to
    (host, port) succeeds within timeout_s.

    The wmctrl-incident audit_log latency_ms=21692 was a 30s
    timeout retrying an unreachable endpoint — this function
    enforces a short default (0.5s) so probes are fast even when
    the listener is dead."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        sock.connect((host, port))
        return True
    except (OSError, socket.timeout):
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def env_present(var: str) -> bool:
    """Return True iff the environment variable is set AND non-empty."""
    return bool(os.environ.get(var))


def desktop_session_reachable(*, timeout_s: float = 1.5) -> bool:
    """Return True iff Maez's process can actually reach an X / Wayland
    desktop session. This is NOT the same as DISPLAY/XAUTHORITY being
    set in the environment (per Codex correction 2026-05-04 — env-set
    ≠ session-reachable; the maez.service unit has DISPLAY=:1 and
    XAUTHORITY set but X session reach still fails).

    Probe: try `xdotool getmouselocation` (cheap, requires X reach)
    with a tight timeout. Falls back to False on any non-zero exit
    or missing binary. Wayland-only environments (no DISPLAY, only
    WAYLAND_DISPLAY) return False because xdotool doesn't reach
    Wayland; that's a known limitation worth surfacing.
    """
    if not has_binary("xdotool"):
        return False
    if not env_present("DISPLAY"):
        return False
    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation"],
            capture_output=True, timeout=timeout_s,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def sudo_passwordless(*, timeout_s: float = 1.0) -> bool:
    """Return True iff `sudo -n true` exits 0 — i.e. we have a sudo
    path that doesn't require an interactive password.

    Per Codex correction 2026-05-04: this returns True on the
    current host; the original audit's "every install will hang"
    claim was wrong. The probe is here so future-Maez or future-
    deployments don't assume sudo is configured the same way."""
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True, timeout=timeout_s,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


# ── full snapshot ────────────────────────────────────────────────────

def _probe_all() -> dict[str, Any]:
    """Run every probe and return a snapshot dict. Called on cache
    miss; do NOT call this directly from hot paths — go through
    body_capabilities() which caches."""
    binaries = {name: has_binary(name) for name in _BINARIES_TO_PROBE}
    env = {var: os.environ.get(var) for var in _ENV_VARS_TO_PROBE}
    services = {
        key: is_service_reachable(host, port)
        for key, host, port in _SERVICES_TO_PROBE
    }
    desktop_ok = desktop_session_reachable()
    sudo_ok = sudo_passwordless()
    return {
        "binaries": binaries,
        "env": env,
        "services": services,
        "desktop_session_reachable": desktop_ok,
        "sudo_passwordless": sudo_ok,
        "probed_at": time.time(),
    }


def body_capabilities() -> dict[str, Any]:
    """Return the current body-capabilities snapshot.

    Cached for _BODY_CAPABILITIES_TTL_S seconds. Subsequent calls
    inside the TTL window return the cached dict without re-probing
    (cheap — a single dict lookup). Pass invalidate_cache() before
    a known capability change (e.g. after `apt install <pkg>`) to
    force a re-probe on the next call.
    """
    global _cache, _cache_ts
    now = time.time()
    if (
        _cache is not None
        and (now - _cache_ts) < _BODY_CAPABILITIES_TTL_S
    ):
        return _cache
    snapshot = _probe_all()
    _cache = snapshot
    _cache_ts = now
    return snapshot


def is_capability_runnable(name: str) -> bool:
    """Convenience predicate: True iff a named capability is
    runtime-runnable from this body. Currently delegates to
    has_binary() for binary-shaped capabilities. Future R3+ work
    can extend with per-tool composite checks (e.g.
    `xdotool_runnable = has_binary('xdotool') AND
     desktop_session_reachable()`)."""
    return has_binary(name)
