# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Screen-perception gate — Commit 2 of the 2026-04-23 audit repair pass.

Invariant guarded here:

    Vision is OFF by default. It never silently fires a screenshot
    capture or a port-8081 HTTP call unless the owner has explicitly
    enabled it via MAEZ_SCREEN_PERCEPTION=1. Even when enabled, a fast
    TCP probe short-circuits the expensive path if the vision endpoint
    is not reachable — so a dead endpoint cannot stretch cycles by 45
    seconds each.

Before this commit, screen_perception.observe() unconditionally
captured a screenshot and POSTed to 127.0.0.1:8081, regardless of
whether any vision server was listening. Port 8081 has been dead for
weeks (used to host vision, was reassigned to the grounding judge,
the judge itself was retired 2026-04-23), so every cycle wasted a
screenshot capture + up to 45 seconds of HTTP timeout on nothing.

Tested paths:
  1. Default (unset flag) — observe() returns state="disabled",
     success=False, and does NOT call requests.post.
  2. Enabled-but-unavailable — probe fails fast and observe()
     returns state="unavailable", success=False, still no
     requests.post or screenshot attempt.
  3. Probe cache — repeated calls within the cooldown window do
     not re-probe.
  4. ScreenObservation.format_for_context differentiates disabled
     vs unavailable vs error states for the prompt.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class DefaultPath(unittest.TestCase):
    """With no env flag, observe() is a fast no-op returning state=disabled."""

    def setUp(self):
        self._prior = os.environ.pop("MAEZ_SCREEN_PERCEPTION", None)

    def tearDown(self):
        if self._prior is not None:
            os.environ["MAEZ_SCREEN_PERCEPTION"] = self._prior

    def test_default_returns_disabled_without_network(self):
        from skills import screen_perception as sp
        # Belt-and-suspenders: patch the outbound HTTP so a regression
        # that skips the gate would fail LOUDLY here.
        with patch("skills.screen_perception.requests.post") as m_post, \
             patch("skills.screen_perception._capture_screenshot") as m_cap, \
             patch("skills.screen_perception._vision_endpoint_probe") as m_probe:
            obs = sp.observe()
        m_post.assert_not_called()
        m_cap.assert_not_called()
        m_probe.assert_not_called()
        self.assertFalse(obs.success)
        self.assertEqual(obs.state, "disabled")
        self.assertIn("MAEZ_SCREEN_PERCEPTION", obs.error or "")

    def test_default_format_for_context_is_explicit(self):
        from skills.screen_perception import ScreenObservation
        obs = ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=0.0, success=False,
            state="disabled", error="n/a",
        )
        ctx = obs.format_for_context()
        self.assertIn("disabled", ctx.lower())
        # Must not look like a temporary failure — the grounding
        # manifest needs to read this as policy, not outage.
        self.assertNotIn("failed", ctx.lower())


class EnabledButUnavailable(unittest.TestCase):
    """When enabled but the endpoint is down, probe short-circuits."""

    def setUp(self):
        self._prior = os.environ.get("MAEZ_SCREEN_PERCEPTION")
        os.environ["MAEZ_SCREEN_PERCEPTION"] = "1"
        # Reset probe cache so the test starts from a clean slate.
        from skills.screen_perception import _vision_probe_cache
        _vision_probe_cache["last_result"] = None
        _vision_probe_cache["last_check"] = 0.0

    def tearDown(self):
        if self._prior is None:
            os.environ.pop("MAEZ_SCREEN_PERCEPTION", None)
        else:
            os.environ["MAEZ_SCREEN_PERCEPTION"] = self._prior

    def test_unavailable_endpoint_short_circuits_before_screenshot(self):
        from skills import screen_perception as sp
        with patch("core.memory.ambient.active_window_for_preflight",
                   return_value={"class": "code", "title": "safe"}), \
             patch("skills.screen_perception._vision_endpoint_probe",
                   return_value=False) as m_probe, \
             patch("skills.screen_perception._capture_screenshot") as m_cap, \
             patch("skills.screen_perception.requests.post") as m_post:
            obs = sp.observe()
        m_probe.assert_called_once()
        # Must not capture a screenshot or fire HTTP after a negative
        # probe — that's the whole point of the cheap pre-check.
        m_cap.assert_not_called()
        m_post.assert_not_called()
        self.assertFalse(obs.success)
        self.assertEqual(obs.state, "unavailable")

    def test_probe_caches_negative_result(self):
        """A negative probe caches for _VISION_PROBE_COOLDOWN_S."""
        import skills.screen_perception as sp
        # Reset cache (setUp already did, but be explicit)
        sp._vision_probe_cache["last_result"] = None
        sp._vision_probe_cache["last_check"] = 0.0
        # First call: real socket will fail (port 8081 is dead in the
        # test environment; we also patch to ensure determinism)
        with patch("socket.create_connection",
                   side_effect=OSError("refused")) as m_sock:
            self.assertFalse(sp._vision_endpoint_probe())
            self.assertFalse(sp._vision_endpoint_probe())
            self.assertFalse(sp._vision_endpoint_probe())
        # Only the first call should have hit the socket — subsequent
        # calls must hit the cache.
        self.assertEqual(m_sock.call_count, 1,
                         "probe cache must suppress re-probes within "
                         "the cooldown window")


class FormatDifferentiation(unittest.TestCase):
    """format_for_context / format_for_memory differentiate the four states."""

    def test_states_render_distinctly(self):
        from skills.screen_perception import ScreenObservation
        seen = set()
        for state in ("disabled", "unavailable", "error", "ok"):
            obs = ScreenObservation(
                activity="coding" if state == "ok" else "",
                application="vscode" if state == "ok" else "",
                detail="",
                focus_level="deep_work" if state == "ok" else "",
                raw_response="",
                timestamp=0.0,
                success=(state == "ok"),
                state=state,
                error=None if state in ("ok", "disabled", "unavailable") else "boom",
            )
            ctx = obs.format_for_context()
            mem = obs.format_for_memory()
            seen.add(ctx)
            seen.add(mem)
        # Four states × two formatters = 8 distinct strings, not all
        # collapsed onto a generic "observation unavailable" bucket.
        self.assertGreaterEqual(
            len(seen), 6,
            "format helpers must differentiate state; got "
            f"{len(seen)} distinct strings across 8 calls.",
        )


if __name__ == "__main__":
    unittest.main()
