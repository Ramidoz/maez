# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.capability_registry.

The registry answers "what do I actually have?" for Maez. These tests
lock in the shape of the answer so the self-description surface stays
truthful across refactors.
"""
from __future__ import annotations

import unittest
from unittest import mock

from core.capability_registry import (
    describe, prompt_snippet, grounded_vocab,
)


class DescribeShape(unittest.TestCase):
    def test_describe_returns_expected_sections(self):
        d = describe()
        for key in ("modules", "services", "schedules",
                    "disabled_features", "recent_activity", "home"):
            self.assertIn(key, d, f"missing section: {key}")

    def test_modules_contains_core_and_daemon(self):
        d = describe()
        self.assertIn("core", d["modules"])
        self.assertIn("daemon", d["modules"])

    def test_schedules_include_load_bearing_cadences(self):
        s = describe()["schedules"]
        self.assertEqual(s["reasoning_cycle_seconds"], 30)
        self.assertEqual(s["daily_consolidation_hour_local"], 3)
        self.assertEqual(s["nightly_journal_hour_local"], 23)

    def test_disabled_features_lists_vision(self):
        """llama-server-vision was explicitly paused by the user. The
        registry must carry this so the model doesn't re-assert
        vision capability."""
        d = describe()
        self.assertIn("llama-server-vision", d["disabled_features"])

    def test_services_include_user_scope_units(self):
        from core.infra import capability_registry as cr

        def fake_check_output(cmd, **_kwargs):
            if "--user" in cmd:
                return (
                    "maez.service loaded active running Maez daemon\n"
                    "minicheck-verifier.service loaded active running MiniCheck verifier\n"
                ).encode("utf-8")
            return b""

        with mock.patch.object(cr.subprocess, "check_output", side_effect=fake_check_output):
            services = cr._list_services()

        self.assertEqual(services["maez"], "active")
        self.assertEqual(services["minicheck-verifier"], "active")

    def test_user_scope_active_wins_over_system_scope_inactive(self):
        from core.infra import capability_registry as cr

        def fake_check_output(cmd, **_kwargs):
            if "--user" in cmd:
                return b"maez-web.service loaded active running Maez web\n"
            return b"maez-web.service loaded inactive dead Maez web system\n"

        with mock.patch.object(cr.subprocess, "check_output", side_effect=fake_check_output):
            services = cr._list_services()

        self.assertEqual(services["maez-web"], "active")


class PromptSnippet(unittest.TestCase):
    def test_snippet_is_nonempty_and_bounded(self):
        # Upper bound covers the capability block + fabrication memory
        # + residue + self-model blocks, all of which may be appended.
        # Raised from 2500 as organism blocks (residue, self-model)
        # were added 2026-04-20 — still under 4000 chars total so it
        # won't dominate the context window.
        s = prompt_snippet()
        self.assertGreater(len(s), 200, "snippet too sparse")
        self.assertLess(len(s), 4000,
            "snippet too long — would bloat every turn's context")

    def test_snippet_mentions_instruction_block(self):
        """The load-bearing part of the snippet is the INSTRUCTION that
        tells the model to default to uncertainty. If that's missing,
        the registry is decorative, not load-bearing."""
        s = prompt_snippet()
        self.assertIn("INSTRUCTION", s)
        self.assertTrue(
            "uncertainty" in s.lower() or "don't have that recorded" in s.lower(),
            "snippet missing the default-to-uncertainty instruction"
        )

    def test_snippet_mentions_disabled_features(self):
        """The model must see that vision is paused — otherwise it may
        still claim to process images."""
        s = prompt_snippet()
        self.assertIn("llama-server-vision", s)

    def test_snippet_mentions_30_second_cycle(self):
        """The 30s cycle is the one schedule fact most often fabricated
        away from (as '3AM cycles', 'nightly' etc.). Lock it in."""
        s = prompt_snippet()
        self.assertIn("30-second", s)

    def test_snippet_renders_runtime_body_status_not_legacy_active_buckets(self):
        """Self-description should use the runtime body registry, not raw
        systemd active/inactive buckets that flatten asleep/degraded organs."""
        from core.infra import capability_registry as cr

        runtime = {
            "schema_version": "maez_runtime_services.v0",
            "overall": "degraded",
            "services": {
                "primary_brain": {
                    "status": "healthy",
                    "configured": True,
                    "required_by": ["always"],
                    "degraded_reasons": [],
                },
                "support_verifier": {
                    "status": "degraded",
                    "configured": True,
                    "required_by": ["MAEZ_SUPPORT_GATE_ENABLED"],
                    "degraded_reasons": ["contract_unhealthy"],
                },
                "search_body": {
                    "status": "asleep",
                    "configured": False,
                    "required_by": [],
                    "degraded_reasons": [],
                },
            },
        }

        with (
            mock.patch.object(cr, "_list_services", return_value={"maez": "active"}),
            mock.patch.object(
                cr,
                "_runtime_services_for_prompt",
                return_value=runtime,
            ),
        ):
            s = prompt_snippet()

        self.assertIn("Runtime services: overall degraded.", s)
        self.assertIn("primary_brain=healthy", s)
        self.assertIn("support_verifier=degraded (contract_unhealthy)", s)
        self.assertIn("search_body=asleep", s)
        self.assertNotIn("Services active:", s)
        self.assertNotIn("Services inactive/stopped:", s)


class GroundedVocab(unittest.TestCase):
    def test_vocab_is_frozenset(self):
        v = grounded_vocab()
        self.assertIsInstance(v, frozenset)

    def _has_maez_systemd_units(self):
        """True if this host has at least one systemd unit starting
        with 'maez' — the registry reads live units via systemctl."""
        import shutil
        import subprocess
        if not shutil.which("systemctl"):
            return False
        try:
            r = subprocess.run(
                ["systemctl", "list-unit-files", "maez*"],
                capture_output=True, text=True, timeout=5,
            )
            return "maez" in (r.stdout or "")
        except Exception:
            return False

    def test_vocab_contains_live_services(self):
        if not self._has_maez_systemd_units():
            self.skipTest(
                "No maez-prefixed systemd units on this host — "
                "expected on CI or a fresh clone. Install the daemon "
                "via scripts/install.sh to exercise this check."
            )
        v = grounded_vocab()
        self.assertTrue(
            any(t.startswith("maez") for t in v),
            f"no maez-prefixed token in registry vocab: {sorted(v)}"
        )

    def test_vocab_has_split_service_parts(self):
        """Services like 'maez-web' are split into 'maez' + 'web' so the
        audit detector grounds bare-token references without needing the
        full hyphenated form."""
        if not self._has_maez_systemd_units():
            self.skipTest("No maez-prefixed systemd units on this host")
        v = grounded_vocab()
        self.assertIn("maez", v)
        # web service is always present when daemon is installed
        self.assertIn("web", v)


# RegistryFeedsAudit removed 2026-04-21 with the regex detectors.
# The v2 judge doesn't consume the capability registry as a vocabulary;
# grounding is semantic per-response. Registry is still populated and
# surfaced elsewhere — this test just asserted a coupling that no longer
# exists.


if __name__ == "__main__":
    unittest.main()
