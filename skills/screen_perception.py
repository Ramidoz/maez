"""
screen_perception.py — Screen awareness for Maez

Captures a screenshot of Rohit's display and uses gemma4:26b's native vision
to understand what he is working on. Returns a structured description that
gets injected into every reasoning cycle.

Called by the daemon every N cycles. Runs asynchronously so it never blocks
the reasoning loop.
"""

import base64
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("maez")

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"
SCREENSHOT_TIMEOUT = 10   # seconds for screenshot capture
VISION_TIMEOUT = 45       # seconds for gemma4 vision call

# Display environment — needed because maez.service has no DISPLAY by default
DISPLAY_ENV = {
    **os.environ,
    "DISPLAY": os.environ.get("DISPLAY", ":1"),
    "XAUTHORITY": os.environ.get("XAUTHORITY", "/run/user/1000/gdm/Xauthority"),
}

VISION_PROMPT = """You are Maez, an AI agent observing what your user Rohit is \
currently doing on his computer. Analyze this screenshot and respond with a \
structured, factual description.

Respond in this exact format:
ACTIVITY: [one line — what Rohit appears to be doing right now]
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

    def format_for_context(self) -> str:
        """Format for injection into Maez reasoning prompt."""
        if not self.success:
            return f"[SCREEN] Observation unavailable: {self.error}"
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
        if not self.success:
            return f"Screen observation failed: {self.error}"
        return (
            f"Screen observation: {self.activity}. "
            f"App: {self.application}. "
            f"Detail: {self.detail}. "
            f"Focus level: {self.focus_level}."
        )


def _capture_screenshot() -> Optional[str]:
    """
    Capture a screenshot and return as base64 string.
    Tries scrot first, then gnome-screenshot, then ImageMagick import.
    Returns None if all methods fail.
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
                with open(tmp, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                os.unlink(tmp)
                logger.debug("Screenshot captured via %s", cmd[0])
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
    Main entry point. Capture screen and analyze with gemma4:26b vision.
    Always returns a ScreenObservation — never raises.
    """
    timestamp = time.time()

    # Capture screenshot
    img_b64 = _capture_screenshot()
    if img_b64 is None:
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            error="Screenshot capture failed — no display method succeeded"
        )

    # Call gemma4 vision
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [{
                    "role": "user",
                    "content": VISION_PROMPT,
                    "images": [img_b64]
                }],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 4096,
                }
            },
            timeout=VISION_TIMEOUT
        )

        if resp.status_code != 200:
            return ScreenObservation(
                activity="", application="", detail="", focus_level="",
                raw_response="", timestamp=timestamp, success=False,
                error=f"Ollama returned {resp.status_code}: {resp.text[:200]}"
            )

        raw = resp.json()['message']['content']
        parsed = _parse_vision_response(raw)

        return ScreenObservation(
            activity=parsed['activity'],
            application=parsed['application'],
            detail=parsed['detail'],
            focus_level=parsed['focus_level'],
            raw_response=raw,
            timestamp=timestamp,
            success=True
        )

    except requests.Timeout:
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            error="Vision call timed out after 45s"
        )
    except Exception as e:
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
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
    sys.path.insert(0, '/home/rohit/maez')
    logging.basicConfig(level=logging.DEBUG)
    success = test()
    sys.exit(0 if success else 1)
