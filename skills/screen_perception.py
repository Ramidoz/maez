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


def _capture_screenshot() -> Optional[str]:
    """
    Capture a screenshot, downscale to max dim VISION_MAX_DIM, return as
    base64 PNG string. Tries scrot first, then gnome-screenshot, then
    ImageMagick import. Returns None if all methods fail.

    Session 11r: added PIL downscaling to prevent the vision server from
    OOMing on the vision-encoder's image tensor allocation. Full 2560×1440
    frames need ~1.9 GB of VRAM to encode; 1024-max-dim needs ~500 MB.
    Activity/application detection doesn't need full resolution.
    """
    tmp = tempfile.mktemp(suffix='.png')

    methods = [
        ['scrot', '-z', tmp],
        ['gnome-screenshot', '-f', tmp],
        ['import', '-window', 'root', tmp],
    ]

    for cmd in methods:
        try:
            result = subprocess.run(
                cmd,
                env=DISPLAY_ENV,
                capture_output=True,
                timeout=SCREENSHOT_TIMEOUT
            )
            if result.returncode == 0 and os.path.exists(tmp):
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
                        cmd[0], img.size[0], img.size[1],
                    )
                    return data
                except Exception as e:
                    # PIL unavailable or resize failed — fall back to raw bytes
                    logger.debug("PIL downscale failed (%s) — sending full-res", e)
                    with open(tmp, 'rb') as f:
                        data = base64.b64encode(f.read()).decode()
                    return data
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            continue
        except Exception as e:
            logger.debug("Screenshot method %s failed: %s", cmd[0], e)
            continue
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

    return None


def _parse_vision_response(text: str) -> dict:
    """Parse gemma4's structured response into fields."""
    result = {
        "activity": "unknown",
        "application": "unknown",
        "detail": "none",
        "focus_level": "unknown",
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

    return result


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

        return ScreenObservation(
            activity=parsed['activity'],
            application=parsed['application'],
            detail=parsed['detail'],
            focus_level=parsed['focus_level'],
            raw_response=raw,
            timestamp=timestamp,
            success=True,
            state="ok",
        )

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
