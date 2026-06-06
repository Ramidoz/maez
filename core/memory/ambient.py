# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
ambient.py — on-demand pull of the owner's current context.

Called by the daemon whenever it needs to ground a response in NOW, instead of
relying on periodic pushes from the phone. Pulls from:

  • logs/signals/YYYY-MM-DD.jsonl   — last known iPhone state (per kind)
  • open-meteo.com                   — weather (no API key needed)
  • xdotool                          — currently-active desktop window

All pulls cheap, best-effort, failures degrade gracefully. Nothing here blocks
the daemon's reasoning loop — a pull that fails returns None for that field.
"""
from __future__ import annotations

import ast
import json
import logging
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import paths as _paths

logger = logging.getLogger("maez.ambient")

SIGNALS_DIR: Path = _paths.signals_dir()

# Fallback coords if no recent location signal from the phone.
# The phone is the source of truth when available. Defaults here are
# sentinel (0, 0) — override via MAEZ_HOME_LAT / MAEZ_HOME_LON in .env
# to set your own home location, or rely on iPhone signal pulses.
FALLBACK_LAT = float(os.environ.get("MAEZ_HOME_LAT", "0.0"))
FALLBACK_LON = float(os.environ.get("MAEZ_HOME_LON", "0.0"))
LOCATION_FRESHNESS_HOURS = float(os.environ.get("MAEZ_LOCATION_FRESHNESS_HOURS", "12"))

# Open-Meteo WMO weather codes → human strings (subset of most common)
_WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "rain showers", 81: "heavy rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm w/ hail", 99: "severe thunderstorm",
}

# ── signals reader ─────────────────────────────────────────────────────
def _signal_files_desc() -> list[Path]:
    """Return signal JSONL files newest-first. Crosses day boundaries."""
    if not SIGNALS_DIR.exists():
        return []
    return sorted(SIGNALS_DIR.glob("*.jsonl"), reverse=True)


def latest_signal(kind: str | None = None, max_age_days: int = 7) -> dict | None:
    """Return the most recent signal matching `kind` (or any kind if None).

    Scans newest day-file first, walks backward up to max_age_days.
    Returns the parsed entry dict, or None if no match found.
    """
    cutoff = (datetime.now(timezone.utc).timestamp() - max_age_days * 86400)
    for path in _signal_files_desc():
        try:
            lines = path.read_text().splitlines()
        except Exception as e:
            logger.debug("signal read %s failed: %s", path, e)
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if kind and entry.get("kind") != kind:
                continue
            # age-check
            ts = entry.get("timestamp")
            if ts:
                try:
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts_dt.timestamp() < cutoff:
                        return None  # everything older is older still
                except Exception:
                    pass
            return entry
    return None


def latest_per_kind(max_age_days: int = 2) -> dict[str, dict]:
    """Latest signal of EACH kind within window. Used for ambient snapshot."""
    seen: dict[str, dict] = {}
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
    for path in _signal_files_desc():
        try:
            lines = path.read_text().splitlines()
        except Exception:
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            k = entry.get("kind")
            if not k or k in seen:
                continue
            ts = entry.get("timestamp")
            if ts:
                try:
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts_dt.timestamp() < cutoff:
                        continue
                except Exception:
                    pass
            seen[k] = entry
    return seen


# ── weather pull ───────────────────────────────────────────────────────
def current_coords() -> tuple[float, float, str]:
    """Where is the owner RIGHT NOW? Prefers recent phone location, falls back to env.

    Returns (lat, lon, source) where source describes provenance for logging.
    """
    loc = latest_signal("location", max_age_days=1)
    if loc:
        data = loc.get("data") or {}
        lat, lon = data.get("lat"), data.get("lon")
        ts = loc.get("timestamp")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and ts:
            try:
                age_h = (datetime.now(timezone.utc).timestamp()
                         - datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()) / 3600
                if age_h <= LOCATION_FRESHNESS_HOURS:
                    return float(lat), float(lon), f"phone({age_h:.1f}h old)"
            except Exception:
                pass
    return FALLBACK_LAT, FALLBACK_LON, "fallback(.env default)"


def current_weather(lat: float | None = None, lon: float | None = None,
                    timeout: float = 3.0) -> dict | None:
    """Open-Meteo current weather. No API key. Returns None on failure.

    If lat/lon omitted, uses current_coords() — which tracks the owner as he travels.
    """
    source = None
    if lat is None or lon is None:
        lat, lon, source = current_coords()
    try:
        q = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        url = f"https://api.open-meteo.com/v1/forecast?{q}"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read())
        cur = data.get("current") or {}
        code = cur.get("weather_code")
        return {
            "temp_c": cur.get("temperature_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "code": code,
            "conditions": _WMO.get(code, f"code:{code}"),
            "timezone": data.get("timezone"),
            "coords": {"lat": lat, "lon": lon, "source": source or "explicit"},
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.debug("weather pull failed: %s", e)
        return None


# ── desktop active window ──────────────────────────────────────────────
def _session_is_wayland() -> bool:
    return (
        os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )


def _parse_focused_window_dbus(raw: str) -> dict | None:
    """Normalize Focused Window D-Bus output to title/class or None.

    `gdbus call` prints the method result as a Python-ish tuple whose first
    element is a JSON string, e.g. ('{"title":"...","wm_class":"..."}',).
    Tests also feed raw JSON directly. Keep only the read nerve's useful fields;
    action-affordance metadata from the extension is deliberately discarded.
    """
    if not raw:
        return None

    text = raw.strip()
    obj = None
    if text.startswith("("):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, tuple) and parsed and isinstance(parsed[0], str):
                obj = json.loads(parsed[0])
        except Exception:
            obj = None

    if obj is None:
        try:
            obj = json.loads(text)
        except Exception:
            return None

    if not isinstance(obj, dict) or not obj:
        return None

    title = obj.get("title") or ""
    klass = obj.get("class") or obj.get("wm_class") or ""
    if not title and not klass:
        return None

    out: dict[str, Any] = {"title": str(title), "class": str(klass)}
    for key in ("pid", "id"):
        if key in obj:
            out[key] = obj[key]
    return out


_parse_window_calls_focused = _parse_focused_window_dbus


def _wayland_active_window(timeout: float = 1.0) -> dict | None:
    """Try existing no-prompt focused-window routes on Wayland.

    Does not install or enable a GNOME extension. If no already-present route
    answers, return None so screen preflight fails safe.
    """
    if not shutil.which("gdbus"):
        return None
    try:
        out = subprocess.check_output(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Shell",
                "--object-path",
                "/org/gnome/shell/extensions/FocusedWindow",
                "--method",
                "org.gnome.shell.extensions.FocusedWindow.Get",
            ],
            timeout=timeout,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return _parse_focused_window_dbus(out)
    except Exception:
        return None


def _raw_active_window(timeout: float = 1.0) -> dict | None:
    """Raw focused-window read: title/class for internal surface selection only."""
    if _session_is_wayland():
        return _wayland_active_window(timeout)
    if not shutil.which("xdotool"):
        return None
    try:
        env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
        wid = subprocess.check_output(
            ["xdotool", "getactivewindow"], env=env, timeout=timeout, text=True
        ).strip()
        name = subprocess.check_output(
            ["xdotool", "getwindowname", wid], env=env, timeout=timeout, text=True
        ).strip()
        # xdotool doesn't expose class directly; use xprop instead.
        wm_class = ""
        if shutil.which("xprop"):
            try:
                out = subprocess.check_output(
                    ["xprop", "-id", wid, "WM_CLASS"], env=env, timeout=timeout, text=True
                )
                # Format: WM_CLASS(STRING) = "instance", "class"
                if "=" in out:
                    wm_class = out.split("=", 1)[1].strip().strip('"').split('", "')[-1].strip().strip('"')
            except Exception:
                pass
        return {"title": name, "class": wm_class}
    except Exception as e:
        logger.debug("active_window failed: %s", e)
        return None


def active_window_for_preflight(timeout: float = 1.0) -> dict | None:
    """Title-bearing focused-window read for the exclusion gate only.

    The title is used to decide whether the screen eye should avert. It must
    not be persisted, injected, or egressed via general ambient surfaces.
    """
    return _raw_active_window(timeout)


def active_window(timeout: float = 1.0) -> dict | None:
    """Class-only focused-window read for ambient/dashboard/web consumers."""
    raw = _raw_active_window(timeout)
    if not raw:
        return None
    return {"class": raw.get("class", "")}


# ── combined snapshot ──────────────────────────────────────────────────
def ambient_context() -> dict[str, Any]:
    """One-shot snapshot used by daemon when grounding a reply in NOW."""
    lat, lon, source = current_coords()
    return {
        "now": datetime.now(timezone.utc).isoformat(),
        "coords_source": source,
        "weather": current_weather(lat, lon),
        "active_window": active_window(),
        "signals_latest": latest_per_kind(),
    }


# ── CLI ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(json.dumps(ambient_context(), indent=2, ensure_ascii=False))
