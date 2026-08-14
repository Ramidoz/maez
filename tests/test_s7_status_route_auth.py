"""Full-body audit: /internal/s7/webauthn/status was the ONE internal S7
route without the channel check, and the cockpit proxied it tokenless --
credential recovery mode and active credential count, unauthenticated."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_daemon_status_route_requires_internal_channel():
    source = (REPO / "daemon" / "maez_daemon.py").read_text()
    match = re.search(
        r"@app\.route\(\"/internal/s7/webauthn/status\".*?def s7_webauthn_status\(\):(.*?)@app\.route",
        source,
        re.S,
    )
    assert match is not None
    body = match.group(1)
    assert "_s7_internal_channel_trusted(request)" in body
    assert "s7_internal_channel_untrusted" in body


def test_web_status_proxy_sends_the_token():
    source = (REPO / "skills" / "web_interface.py").read_text()
    match = re.search(
        r"def _s7_cockpit_status_proxy\(\):(.*?)\n@app\.route|def _s7_cockpit_status_proxy\(\):(.*?)\ndef ",
        source,
        re.S,
    )
    assert match is not None
    body = match.group(1) or match.group(2)
    assert "S7_INTERNAL_CHANNEL_TOKEN" in body
    assert "X-Maez-S7-Internal-Channel" in body
    # No token, no probe -- same refusal shape as every other proxy.
    assert "s7_internal_channel_untrusted" in body
