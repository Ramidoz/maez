# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
screen_perception.py — Screen awareness for Maez

Captures a screenshot of the owner's display and uses a dedicated vision model
(Qwen2.5-VL-3B via llama-server-vision.service on port 8081) to understand
what he is working on. Returns a structured description that gets injected
into every reasoning cycle.

Called by the daemon every N cycles. Runs asynchronously so it never blocks
the reasoning loop.

Session 11r: migrated from ollama gemma4 mmproj to dedicated Qwen2.5-VL-3B
server. The old gemma4 path used `/api/chat` with `images=[base64]` (ollama
native format). The new path uses OpenAI-compat `/v1/chat/completions` on
127.0.0.1:8081 with the multimodal message shape
`content: [{type: text, ...}, {type: image_url, image_url: {url: ...}}]`.

Also downsamples screenshots to max-dim 1024 before sending — Qwen2.5-VL's
vision tower needs ~1.88 GB to process a 2560×1440 image but only ~500 MiB
for 1024×576. 1024 is plenty of resolution for "what app is open and what
is the user doing" — that's a 480p task at worst.
"""

import base64
import io
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("maez")

VISION_URL = "http://127.0.0.1:8081/v1/chat/completions"
VISION_MODEL = "qwen2.5-vl-3b"
VISION_MAX_DIM = 1024     # downscale screenshots to max side = 1024 px
SCREENSHOT_TIMEOUT = 10   # seconds for screenshot capture
VISION_TIMEOUT = 45       # seconds for vision call

# 2026-04-23 Commit 2: vision-server availability probe.
# Port 8081 has been dead for weeks (used to host a multimodal endpoint,
# was later reassigned to the retired grounding judge, now has nothing
# bound). `observe()` must not call requests.post() there when:
#   - MAEZ_SCREEN_PERCEPTION is unset or "0" (hard default: vision off)
#   - the host:port probe fails (fast-fail before screenshot capture)
# Probe result is cached with backoff so we don't hammer the port.
_VISION_PROBE_HOST = "127.0.0.1"
_VISION_PROBE_PORT = 8081
_VISION_PROBE_TIMEOUT_S = 1.0      # fast: 1-second TCP connect
_VISION_PROBE_COOLDOWN_S = 300.0   # 5 minutes of "unavailable" before re-probing
_vision_probe_cache: dict = {"last_result": None, "last_check": 0.0}

# Display environment — needed because maez.service has no DISPLAY by default
DISPLAY_ENV = {
    **os.environ,
    "DISPLAY": os.environ.get("DISPLAY", ":1"),
    "XAUTHORITY": os.environ.get("XAUTHORITY", "/run/user/1000/gdm/Xauthority"),
}

VISION_PROMPT = """You are Maez, an AI agent observing what your user the owner is \
currently doing on his computer. Analyze this screenshot and respond with a \
structured, factual description.

Respond in this exact format:
ACTIVITY: [one line — what the owner appears to be doing right now]
APPLICATION: [the primary application visible]
DETAIL: [any specific detail worth noting — file names, error messages, code language, website, terminal commands visible, etc. Write 'none' if nothing notable]
FOCUS_LEVEL: [deep_work | browsing | idle | entertainment | system_task]
THIRD_PARTY: [yes | no — is private content authored by OTHER people visible, such as a message, email, chat, or call from someone other than the owner? Answer yes if unsure.]

Be precise and factual. Do not speculate beyond what is visible."""


@dataclass
class ScreenObservation:
    activity: str
    application: str
    detail: str
    focus_level: str
    raw_response: str
    timestamp: float
    success: bool
    error: Optional[str] = None
    # 2026-04-23 Commit 2: explicit state classification so the daemon's
    # grounding manifest can distinguish "temporarily broken" from
    # "deliberately off." Values:
    #   "ok"           — success=True, observation is real
    #   "disabled"     — MAEZ_SCREEN_PERCEPTION is unset/0, by owner policy
    #   "paused"       — owner pause file present; no capture attempted
    #   "excluded"     — sensitive active window; no capture attempted
    #   "unavailable"  — vision endpoint probe failed, backing off
    #   "error"        — screenshot or vision call failed at runtime
    state: str = "error"
    third_party_content_present: bool = False
    egress_origin_class: str = "owner_screen_context"

    def format_for_context(self) -> str:
        """Format for injection into Maez reasoning prompt."""
        if self.state == "disabled":
            return (
                "[SCREEN] disabled by policy "
                "(set MAEZ_SCREEN_PERCEPTION=1 and run a vision server "
                "on 127.0.0.1:8081 to enable)"
            )
        if self.state == "paused":
            return "[SCREEN] paused by owner (no capture)"
        if self.state == "excluded":
            return "[SCREEN] excluded — sensitive app in focus (not captured)"
        if self.state == "unavailable":
            return "[SCREEN] unavailable — vision endpoint not reachable"
        if not self.success:
            return f"[SCREEN] Observation failed: {self.error}"
        age_seconds = int(time.time() - self.timestamp)
        return (
            f"[SCREEN — {age_seconds}s ago]\n"
            f"  Activity: {self.activity}\n"
            f"  Application: {self.application}\n"
            f"  Detail: {self.detail}\n"
            f"  Focus: {self.focus_level}"
        )

    def format_for_memory(self) -> str:
        """Format for storage in raw memory archive."""
        if self.state == "disabled":
            return "Screen observation: disabled by policy."
        if self.state == "unavailable":
            return "Screen observation: vision endpoint unavailable."
        if not self.success:
            return f"Screen observation failed: {self.error}"
        return (
            f"Screen observation: {self.activity}. "
            f"App: {self.application}. "
            f"Detail: {self.detail}. "
            f"Focus level: {self.focus_level}."
        )


def _is_enabled() -> bool:
    """Return True iff the owner has explicitly enabled screen perception.

    Default OFF. The only way to turn it on is set MAEZ_SCREEN_PERCEPTION=1
    (or any non-"0", non-empty value) in the environment. Matches ADR 0009
    and the current config/model_state.json (vision_model=null)."""
    val = os.environ.get("MAEZ_SCREEN_PERCEPTION", "").strip().lower()
    return val not in ("", "0", "false", "no", "off")


def _pause_file() -> str:
    return os.environ.get(
        "MAEZ_SCREEN_PAUSE_FILE",
        os.path.expanduser("~/.config/maez/screen_perception.paused"),
    )


def _is_paused() -> bool:
    # Deterministic, no-restart control: touch the file to close the eye,
    # remove it to reopen.
    return os.path.exists(_pause_file())


_GNOME_DESKTOPS = ("gnome", "ubuntu:gnome")
_WLROOTS_DESKTOPS = ("sway", "hyprland", "wlroots", "river", "wayfire")


def _session_type() -> str:
    """Honest display/session classification for lens selection."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").strip().lower()
    if session_type == "x11" or (not session_type and os.environ.get("DISPLAY")):
        return "x11"
    if session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        if any(name in desktop for name in _GNOME_DESKTOPS):
            return "wayland-gnome"
        if any(name in desktop for name in _WLROOTS_DESKTOPS):
            return "wayland-wlroots"
    return "unknown"


_DEFAULT_EXCLUDE = (
    "keepassxc",
    "bitwarden",
    "1password",
    "gnome-keyring",
    "signal",
    "whatsapp",
    "telegram",
    "slack",
    "zoom",
    "meet.google",
    "teams",
    "bank",
    "chase",
    "wellsfargo",
    "fidelity",
    "vanguard",
    "mychart",
    "health",
    "patient",
)


def _exclusion_terms() -> tuple[str, ...]:
    extra = os.environ.get("MAEZ_SCREEN_EXCLUDE", "")
    extra_terms = tuple(term.strip().lower() for term in extra.split(",") if term.strip())
    return _DEFAULT_EXCLUDE + extra_terms


def _is_excluded_active_window() -> bool:
    """Return True when the active window is sensitive or undetermined.

    Lens v0 fail-safe: if the focused window cannot be read, do not capture.
    The never-looked guarantee must hold even when the window is unknown.
    """
    from core.memory.ambient import active_window

    win = active_window()
    if not win:
        return True
    haystack = f"{win.get('class', '')} {win.get('title', '')}".lower()
    return any(term in haystack for term in _exclusion_terms())


def _vision_endpoint_probe() -> bool:
    """Fast TCP-connect probe for the vision endpoint.

    Returns True iff the host:port accepts a TCP connection within
    _VISION_PROBE_TIMEOUT_S. Caches the negative result for
    _VISION_PROBE_COOLDOWN_S so the daemon doesn't re-probe every
    cycle when the server is known-dead.
    """
    import socket
    now = time.time()
    cached = _vision_probe_cache.get("last_result")
    last = _vision_probe_cache.get("last_check", 0.0)
    # Only honor the cached NEGATIVE result (cached == False). A cached
    # positive is stale immediately — probe fresh so we don't fire a
    # 45-second HTTP timeout into a port that went down since last check.
    if cached is False and (now - last) < _VISION_PROBE_COOLDOWN_S:
        return False
    try:
        with socket.create_connection(
            (_VISION_PROBE_HOST, _VISION_PROBE_PORT),
            timeout=_VISION_PROBE_TIMEOUT_S,
        ):
            pass
        _vision_probe_cache["last_result"] = True
        _vision_probe_cache["last_check"] = now
        return True
    except OSError:
        _vision_probe_cache["last_result"] = False
        _vision_probe_cache["last_check"] = now
        return False


def _run_capture_cmd(cmd, tmp: str) -> bool:
    """Run a capture command and return True iff it wrote an image file."""
    try:
        result = subprocess.run(
            cmd,
            env=DISPLAY_ENV,
            capture_output=True,
            timeout=SCREENSHOT_TIMEOUT,
        )
        return (
            result.returncode == 0
            and os.path.exists(tmp)
            and os.path.getsize(tmp) > 0
        )
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        logger.debug("capture command %s failed: %s", cmd[0], e)
        return False


def _capture_gnome_shell_dbus(tmp: str) -> bool:
    return False


def _capture_portal_noprompt(tmp: str) -> bool:
    return False


def _capture_candidates() -> list[dict]:
    """Ordered no-prompt-only capture candidates for the current session."""
    session = _session_type()
    if session == "wayland-gnome":
        return [
            {"name": "gnome-shell-dbus", "fn": _capture_gnome_shell_dbus},
            {"name": "portal", "fn": _capture_portal_noprompt},
        ]
    if session == "wayland-wlroots":
        return [
            {"name": "grim", "fn": lambda tmp: _run_capture_cmd(["grim", tmp], tmp)}
        ]
    return [
        {"name": "scrot", "fn": lambda tmp: _run_capture_cmd(["scrot", "-z", tmp], tmp)},
        {
            "name": "gnome-screenshot",
            "fn": lambda tmp: _run_capture_cmd(["gnome-screenshot", "-f", tmp], tmp),
        },
        {
            "name": "import",
            "fn": lambda tmp: _run_capture_cmd(["import", "-window", "root", tmp], tmp),
        },
    ]


def _capture_screenshot() -> Optional[str]:
    """
    Capture a screenshot, downscale to max dim VISION_MAX_DIM, return as
    base64 PNG string. Returns None if all session-appropriate candidates fail.

    Session 11r: added PIL downscaling to prevent the vision server from
    OOMing on the vision-encoder's image tensor allocation. Full 2560×1440
    frames need ~1.9 GB of VRAM to encode; 1024-max-dim needs ~500 MB.
    Activity/application detection doesn't need full resolution.
    """
    tmp = tempfile.mktemp(suffix='.png')

    try:
        for candidate in _capture_candidates():
            if candidate["fn"](tmp):
                # Downscale via PIL before base64-encoding
                try:
                    from PIL import Image
                    img = Image.open(tmp)
                    img.thumbnail((VISION_MAX_DIM, VISION_MAX_DIM), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format='PNG', optimize=True)
                    data = base64.b64encode(buf.getvalue()).decode()
                    logger.debug(
                        "Screenshot captured via %s (downscaled to %dx%d)",
                        candidate["name"], img.size[0], img.size[1],
                    )
                    return data
                except Exception as e:
                    # PIL unavailable or resize failed — fall back to raw bytes
                    logger.debug("PIL downscale failed (%s) — sending full-res", e)
                    with open(tmp, 'rb') as f:
                        data = base64.b64encode(f.read()).decode()
                    return data

        return None
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass


def _parse_vision_response(text: str) -> dict:
    """Parse gemma4's structured response into fields."""
    result = {
        "activity": "unknown",
        "application": "unknown",
        "detail": "none",
        "focus_level": "unknown",
        "third_party": "",
    }

    for line in text.strip().split('\n'):
        line = line.strip()
        if line.startswith('ACTIVITY:'):
            result['activity'] = line[9:].strip()
        elif line.startswith('APPLICATION:'):
            result['application'] = line[12:].strip()
        elif line.startswith('DETAIL:'):
            result['detail'] = line[7:].strip()
        elif line.startswith('FOCUS_LEVEL:'):
            result['focus_level'] = line[12:].strip()
        elif line.startswith('THIRD_PARTY:'):
            result['third_party'] = line[12:].strip().lower()

    return result


_THIRD_PARTY_APP_HINTS = (
    "signal",
    "whatsapp",
    "telegram",
    "slack",
    "mail",
    "thunderbird",
    "gmail",
    "outlook",
    "messages",
    "discord",
)


def _looks_third_party(parsed: dict) -> bool:
    flag = (parsed.get("third_party") or "").strip().lower()
    app = (parsed.get("application") or "").strip().lower()
    if any(hint in app for hint in _THIRD_PARTY_APP_HINTS):
        return True
    if flag in ("no", "false"):
        return False
    # Fail-safe: missing, uncertain, or unrecognized means minimize.
    return True


def _apply_screen_governance(
    parsed: dict,
    *,
    timestamp: float,
    raw: str,
) -> ScreenObservation:
    third_party = _looks_third_party(parsed)
    detail = parsed.get("detail") or "none"
    origin = "owner_screen_context"
    if third_party:
        detail = "[minimized: third-party content present]"
        origin = "third_party_private_context"
    return ScreenObservation(
        activity=parsed.get("activity") or "unknown",
        application=parsed.get("application") or "unknown",
        detail=detail,
        focus_level=parsed.get("focus_level") or "unknown",
        raw_response=raw,
        timestamp=timestamp,
        success=True,
        state="ok",
        third_party_content_present=third_party,
        egress_origin_class=origin,
    )


def observe() -> ScreenObservation:
    """
    Main entry point. Capture screen and analyze with a vision LLM.
    Always returns a ScreenObservation — never raises.

    2026-04-23 Commit 2: two-stage gate before the expensive work:
      1. Feature flag `MAEZ_SCREEN_PERCEPTION` must be truthy. Default
         is OFF — vision is deliberately paused per ADR 0009 until a
         multimodal endpoint is re-provisioned.
      2. Fast TCP probe to the vision endpoint. If the port is dead,
         back off with cached result so we don't waste a screenshot
         capture + 45-second HTTP timeout on every cycle.
    """
    timestamp = time.time()

    if _is_paused():
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="paused",
            error="screen perception paused by owner",
        )

    # Stage 1: explicit opt-in. Default off — no screenshot, no probe,
    # no network call. Matches the owner's current body state (no
    # vision endpoint running) and prevents the per-cycle 45-second
    # timeout loop observed 2026-04-23.
    if not _is_enabled():
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="disabled",
            error="screen perception disabled (MAEZ_SCREEN_PERCEPTION unset)",
        )

    if _is_excluded_active_window():
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="excluded",
            error="sensitive app in focus (preflight exclusion)",
        )

    # Stage 2: fast availability probe. If the vision endpoint isn't
    # accepting connections, don't bother capturing a screenshot.
    # Caches a negative result for _VISION_PROBE_COOLDOWN_S so we
    # aren't re-probing every 60 seconds when the port is known dead.
    if not _vision_endpoint_probe():
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="unavailable",
            error=(
                f"vision endpoint {_VISION_PROBE_HOST}:"
                f"{_VISION_PROBE_PORT} not reachable"
            ),
        )

    # Capture screenshot
    img_b64 = _capture_screenshot()
    if img_b64 is None:
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="error",
            error="Screenshot capture failed — no display method succeeded"
        )

    # Call the dedicated Qwen2.5-VL-3B vision server (Session 11r).
    # OpenAI-compat endpoint on port 8081, multimodal message shape.
    try:
        resp = requests.post(
            VISION_URL,
            json={
                "model": VISION_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                        }},
                    ],
                }],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            timeout=VISION_TIMEOUT,
        )

        if resp.status_code != 200:
            return ScreenObservation(
                activity="", application="", detail="", focus_level="",
                raw_response="", timestamp=timestamp, success=False,
                state="error",
                error=f"Vision server returned {resp.status_code}: {resp.text[:200]}",
            )

        raw = resp.json()['choices'][0]['message']['content']
        parsed = _parse_vision_response(raw)
        return _apply_screen_governance(parsed, timestamp=timestamp, raw=raw)

    except requests.Timeout:
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="error",
            error="Vision call timed out after 45s"
        )
    except Exception as e:
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="error",
            error=str(e)
        )


def test():
    """Quick test — run directly to verify everything works."""
    print("Testing screen perception...")
    obs = observe()
    if obs.success:
        print("\nSUCCESS")
        print(obs.format_for_context())
        print(f"\nMemory format: {obs.format_for_memory()}")
    else:
        print(f"\nFAILED: {obs.error}")
    return obs.success


if __name__ == '__main__':
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    logging.basicConfig(level=logging.DEBUG)
    success = test()
    sys.exit(0 if success else 1)
