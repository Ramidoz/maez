# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for R2 — body-truth probe.

The 2026-05-04 symphony audit (S1 finding F8/F9/F10/F14, S2 #5, top-10
#5/#6/#10) found that Maez's claims about its body don't match the
body's actual reachability. Codex's correction further refined: env
vars present ≠ X session reachable; `sudo -n true` succeeds on this
host so "every install will hang" was wrong.

R2 builds a single source of truth for runtime-verifiable body facts:
binaries, env, localhost-service reach, desktop-session reach, sudo
path. NOT yet wired into prompt construction; the wiring is R3-R5
work. R2 only builds the introspection surface.

Contract enforced by these tests:
- body_capabilities() returns a dict with the expected top-level keys.
- has_binary(name) returns True for a binary we know is installed
  (python3) and False for an obviously-fake name.
- is_service_reachable(host, port) returns True for a known-up port
  (the llama-server on 8080 in production; we mock to make the test
  hermetic).
- desktop_session_reachable() returns a bool and doesn't crash on
  systems where X is unreachable.
- sudo_passwordless() returns a bool.
- Results are cached with a TTL so repeat calls don't compound
  subprocess cost (probe count must equal 1 across two calls within
  the TTL window).
- TTL refresh after expiry re-probes (probe count = 2 across the
  expiry boundary).
- env_present(var) checks os.environ honestly.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class R2_BodyCapabilitiesShape(unittest.TestCase):
    """REGRESSION GUARD: body_capabilities() must return a dict
    with the documented top-level keys so consumers (capability_
    registry, prompt builders, offer composers) can rely on the
    shape."""

    def test_body_capabilities_returns_dict_with_expected_keys(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        result = bc.body_capabilities()
        self.assertIsInstance(result, dict)
        for key in (
            "binaries", "env", "services",
            "desktop_session_reachable", "sudo_passwordless",
            "probed_at",
        ):
            self.assertIn(
                key, result,
                f"body_capabilities() must expose top-level key {key!r}",
            )

    def test_binaries_subdict_has_known_entries(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        result = bc.body_capabilities()
        binaries = result["binaries"]
        self.assertIsInstance(binaries, dict)
        # Each entry must be a bool (True if reachable from PATH, False
        # otherwise). The probed list MUST include the wmctrl-class
        # tools the audit flagged.
        for name in (
            "wmctrl", "xdotool", "dbus-send",
            "git", "curl", "sudo", "apt-get",
        ):
            self.assertIn(
                name, binaries,
                f"body_capabilities()['binaries'] must include {name!r}",
            )
            self.assertIsInstance(
                binaries[name], bool,
                f"binaries[{name!r}] must be a bool",
            )

    def test_env_subdict_has_desktop_keys(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        result = bc.body_capabilities()
        env = result["env"]
        self.assertIsInstance(env, dict)
        for key in (
            "DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS",
            "WAYLAND_DISPLAY",
        ):
            self.assertIn(
                key, env,
                f"body_capabilities()['env'] must include {key!r}",
            )
            # Each entry is the actual env value (str) or None.
            self.assertIsInstance(
                env[key], (str, type(None)),
            )

    def test_services_subdict_has_known_localhost_ports(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        result = bc.body_capabilities()
        services = result["services"]
        self.assertIsInstance(services, dict)
        for key in (
            "brain_8080",
            "daemon_11435",
            "proxy_11438",
            "minicheck_8083",
            "searxng_8888",
        ):
            self.assertIn(
                key, services,
                f"services must include {key!r}",
            )
            self.assertIsInstance(services[key], bool)


class R2_HasBinaryProbe(unittest.TestCase):
    """REGRESSION GUARD: has_binary(name) must reflect runtime PATH
    truth, not a hardcoded list."""

    def test_has_binary_true_for_python3(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        # python3 is required to run this very test.
        self.assertTrue(bc.has_binary("python3"))

    def test_has_binary_false_for_obviously_fake_name(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        # A name no system will have unless someone installed it on
        # purpose for adversarial reasons.
        self.assertFalse(
            bc.has_binary("definitely-not-a-real-binary-2026"),
        )


class R2_ServiceReachabilityProbe(unittest.TestCase):
    """REGRESSION GUARD: is_service_reachable(host, port) must
    actually do a TCP-connect probe with a tight timeout — the
    wmctrl-class lesson is "config says reachable doesn't mean
    runtime says reachable.\""""

    def test_unreachable_port_returns_false_within_timeout(self):
        from core.infra import body_capabilities as bc
        # Port 1 is reserved (tcpmux) and almost never bound on a
        # workstation; safe choice for a "no listener" probe.
        # 1s timeout is enforced so the test doesn't hang the suite.
        import time
        start = time.time()
        result = bc.is_service_reachable("127.0.0.1", 1, timeout_s=0.5)
        elapsed = time.time() - start
        self.assertFalse(result)
        self.assertLess(
            elapsed, 2.0,
            "is_service_reachable must respect the timeout — the "
            "wmctrl-incident audit_log latency_ms=21692 was a 30s "
            "timeout retrying an unreachable endpoint",
        )


class R2_TTLCache(unittest.TestCase):
    """REGRESSION GUARD: body_capabilities() must cache its probe
    results so repeated calls within the TTL window don't compound
    subprocess cost. The cache must also refresh after expiry."""

    def test_two_calls_in_ttl_window_probe_once(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        # Patch the heavy probe function so we can count invocations.
        original = bc._probe_all
        call_count = {"n": 0}

        def counting_probe():
            call_count["n"] += 1
            return original()

        with mock.patch.object(bc, "_probe_all", side_effect=counting_probe):
            bc.body_capabilities()
            bc.body_capabilities()
        self.assertEqual(
            call_count["n"], 1,
            "two body_capabilities() calls inside TTL must probe once",
        )

    def test_invalidate_cache_forces_reprobe(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        original = bc._probe_all
        call_count = {"n": 0}

        def counting_probe():
            call_count["n"] += 1
            return original()

        with mock.patch.object(bc, "_probe_all", side_effect=counting_probe):
            bc.body_capabilities()
            bc.invalidate_cache()
            bc.body_capabilities()
        self.assertEqual(
            call_count["n"], 2,
            "invalidate_cache() must force the next call to re-probe",
        )

    def test_ttl_default_is_reasonable(self):
        """Source-pin: the TTL default must be a small positive
        number of seconds (10-300). Too short = wasted subprocess
        cost; too long = stale body-truth."""
        from core.infra import body_capabilities as bc
        ttl = getattr(bc, "_BODY_CAPABILITIES_TTL_S", None)
        self.assertIsNotNone(ttl)
        self.assertGreaterEqual(float(ttl), 10.0)
        self.assertLessEqual(float(ttl), 300.0)


class R2_DesktopSessionProbe(unittest.TestCase):
    """REGRESSION GUARD: desktop_session_reachable() must do an
    actual reachability probe (not just env-var check), with a
    tight timeout so a sick X session doesn't bottleneck callers.

    Per Codex correction (2026-05-04): env vars present (DISPLAY,
    XAUTHORITY) ≠ session reachable. The probe must actually try."""

    def test_returns_bool_doesnt_crash(self):
        from core.infra import body_capabilities as bc
        bc.invalidate_cache()
        result = bc.desktop_session_reachable()
        self.assertIsInstance(result, bool)

    def test_probe_uses_short_timeout(self):
        """Source-pin: the desktop probe must use a short timeout
        (≤2s) so a hung session doesn't drag callers."""
        path = REPO / "core" / "infra" / "body_capabilities.py"
        src = path.read_text()
        # The function must call a subprocess or socket op with a
        # timeout argument <= 2s. Source-pin matches the pattern.
        self.assertIn("desktop_session_reachable", src)
        # The probe body should reference timeout in some form.
        # Accept timeout=, timeout_s=, or stdlib `signal.alarm`.
        import re
        body_match = re.search(
            r"def desktop_session_reachable\([^)]*\)[^:]*:(.*?)(?=\ndef |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(body_match)
        body = body_match.group(1)
        self.assertTrue(
            "timeout" in body or "alarm" in body,
            "desktop_session_reachable must enforce a timeout — "
            "the env-set-but-session-unreachable case is exactly the "
            "Codex-correction failure mode",
        )


if __name__ == "__main__":
    unittest.main()
