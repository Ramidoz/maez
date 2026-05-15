# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
iphone_ingest.py — Accept structured signals from iOS Shortcuts.

Maez uses these to know the owner better over time: location, health, focus
mode, battery, currently-playing music, workouts, manual notes.

Auth: shared secret in X-Maez-Token header
(MAEZ_IPHONE_INGEST_TOKEN in config/secrets.local.env or systemd credentials).
Store: logs/signals/YYYY-MM-DD.jsonl — one line per signal, for daemon to
pick up and fold into context / memory.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("maez.iphone")

try:
    from core.infra import paths as _paths

    SIGNALS_DIR = _paths.logs_dir() / "signals"
except Exception:
    SIGNALS_DIR = Path(__file__).resolve().parent.parent / "logs" / "signals"
SIGNALS_LOCK = threading.Lock()
MAX_SIGNAL_BYTES = 64 * 1024  # reject oversized payloads

# Narrow set of signal kinds we accept. Keeps schema tight, rejects drift.
VALID_KINDS = frozenset(
    {
        # Rhythm & presence (the big 3 — highest signal)
        "location",  # {lat, lon, place?, arrived?: true|false}
        "focus_mode",  # {mode: "work"|"sleep"|"dnd"|"personal"|"off", active: bool}
        "arrive_home",  # {}
        "leave_home",  # {}
        "arrive_work",  # {}
        "leave_work",  # {}
        # Body state (warmth & care)
        "sleep",  # {bedtime, wake, duration_hours, quality?}
        "workout",  # {type, duration_min, distance_km?, calories?}
        "health",  # {steps?, heart_rate?, active_energy?}
        "heart_rate_spike",  # {bpm, context?}  — one-shot, not continuous
        "mindfulness",  # {duration_min, app?}
        # Inner life (user-initiated, highest signal per byte)
        "manual_note",  # {text}
        "mood_check",  # {rating: 1-5, emoji?, note?}
        "intention",  # {when: "morning"|"evening", text}
        "reflection",  # {text}  — longer-form end-of-day
        # Context (ambient tone)
        "weather",  # {conditions, temp_c, place}
        "commute",  # {mode: "drive"|"transit"|"walk", duration_min, from?, to?}
        "with_people",  # {names: [...]}  — manual tagging
        "reading",  # {title, author?, highlight?}
        "media_context",  # {kind: "podcast"|"audiobook", title, app?}
        # Lower signal (keep for completeness)
        "battery",  # {level: 0-100, charging: bool}
        "now_playing",  # {title, artist?, app?}
        # Escape hatch
        "custom",  # {name, ...}
    }
)


def _token_ok(provided: str | None) -> bool:
    expected = os.environ.get("MAEZ_IPHONE_INGEST_TOKEN", "")
    if not expected or not provided:
        return False
    # constant-time compare
    return hmac.compare_digest(provided.strip(), expected)


def ingest(payload: dict[str, Any], provided_token: str | None) -> tuple[dict, int]:
    """Validate + persist one signal. Returns (response_json, http_status)."""
    if not _token_ok(provided_token):
        return {"error": "unauthorized"}, 401

    if not isinstance(payload, dict):
        return {"error": "payload must be object"}, 400

    kind = payload.get("kind")
    if not isinstance(kind, str):
        return {
            "error": "kind must be a string",
            "hint": "in Shortcuts: make the 'kind' value a Text field, not a Dictionary. Example: kind=manual_note (plain text).",
            "received_type": type(kind).__name__,
        }, 400
    if kind not in VALID_KINDS:
        return {"error": f"unknown kind; valid: {sorted(VALID_KINDS)}"}, 400

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return {"error": "data must be object"}, 400

    serialized = json.dumps(data, ensure_ascii=False)
    if len(serialized) > MAX_SIGNAL_BYTES:
        return {"error": "payload too large"}, 413

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "data": data,
        "source": "ios_shortcuts",
    }
    # Honor client-provided timestamp if it looks reasonable (ISO8601 string).
    client_ts = payload.get("timestamp")
    if isinstance(client_ts, str) and len(client_ts) < 40:
        entry["client_timestamp"] = client_ts

    try:
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        fname = datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"
        path = SIGNALS_DIR / fname
        with SIGNALS_LOCK:
            with path.open("a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("signal write failed: %s", e)
        return {"error": "storage failed"}, 500

    return {"ok": True, "kind": kind}, 200
