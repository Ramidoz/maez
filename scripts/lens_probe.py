"""Content-free Lens v0 probe for the live graphical session.

Reports which active-window and capture routes work no-prompt on this body.
Prints route names, booleans, and image byte sizes only; never screen content.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.memory import ambient  # noqa: E402
import skills.screen_perception as sp  # noqa: E402


def main() -> int:
    print("session_type:", sp._session_type())
    print("active_window_present:", ambient.active_window() is not None)
    for candidate in sp._capture_candidates():
        tmp = tempfile.mktemp(suffix=".png")
        try:
            ok = bool(candidate["fn"](tmp))
            size = os.path.getsize(tmp) if ok and os.path.exists(tmp) else 0
            print(f"capture[{candidate['name']}]: ok={ok} bytes={size}")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
