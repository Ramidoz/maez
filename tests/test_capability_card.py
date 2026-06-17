from __future__ import annotations

import os
import unittest

from core.cognition import capability_card as cc


class _Env(unittest.TestCase):
    def setUp(self):
        for k in ("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "MAEZ_SURFACE_PARITY_ENABLED"):
            os.environ.pop(k, None)
            self.addCleanup(lambda k=k: os.environ.pop(k, None))
        cc.reset_card_cache()
        self.addCleanup(cc.reset_card_cache)


class FlagTests(_Env):
    def test_default_off_returns_empty(self):
        self.assertEqual(cc.capability_prompt_block(), "")

    def test_flag_helper(self):
        self.assertFalse(cc.evidence_precedence_enabled())
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        self.assertTrue(cc.evidence_precedence_enabled())

    def test_flag_zero_is_off(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "0"
        self.assertFalse(cc.evidence_precedence_enabled())
        self.assertEqual(cc.capability_prompt_block(), "")


class CardTests(_Env):
    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_renders_all_registry_entries_and_precedence_lines(self):
        card = cc.capability_prompt_block(
            registry=(
                ("web sense", lambda: "searxng healthy"),
                ("felt time", lambda: "built, not yet attached"),
            )
        )
        self.assertIn("YOUR LIVE BODY (live/cached substrate probe):", card)
        self.assertIn("web sense: searxng healthy", card)
        self.assertIn("felt time: built, not yet attached", card)
        self.assertIn("outranks any MEMORY of your former", card)
        self.assertNotIn("just now", card)

    def test_probe_failure_is_unknown_never_absent(self):
        def _boom():
            raise RuntimeError("probe died")

        card = cc.capability_prompt_block(
            registry=(
                ("web sense", _boom),
                ("recall", lambda: "on"),
            )
        )
        self.assertIn("web sense: unknown (probe error)", card)
        self.assertIn("recall: on", card)

    def test_cache_ttl_30s(self):
        calls = {"n": 0}

        def _probe():
            calls["n"] += 1
            return "on"

        reg = (("recall", _probe),)
        cc.capability_prompt_block(registry=reg)
        cc.capability_prompt_block(registry=reg)
        self.assertEqual(calls["n"], 1)
        cc.reset_card_cache()
        cc.capability_prompt_block(registry=reg)
        self.assertEqual(calls["n"], 2)

    def test_default_registry_uses_singleton_backend(self):
        class _Counting:
            instances = 0

            def __init__(self):
                _Counting.instances += 1

            def health(self):
                return "healthy"

        from unittest import mock

        with (
            mock.patch.object(cc, "_BACKEND", None),
            mock.patch("core.search.searxng_client.SearxngBackend", _Counting),
        ):
            cc.reset_card_cache()
            cc.capability_prompt_block()
            cc.reset_card_cache()
            cc.capability_prompt_block()
        self.assertEqual(_Counting.instances, 1)


class FeltTimeProbeTests(_Env):
    def test_flag_off_returns_exact_legacy_string(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)

        card = cc.capability_prompt_block()

        self.assertIn("felt time: built, not yet attached", card)

    def test_flag_on_reports_attached(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"

        card = cc.capability_prompt_block()

        self.assertIn("felt time: attached", card)
        self.assertNotIn("not yet attached", card)

    def test_flag_zero_is_not_attached(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "0"

        card = cc.capability_prompt_block()

        self.assertIn("felt time: built, not yet attached", card)

    def test_no_unconditional_static_entry_remains(self):
        import inspect

        src = inspect.getsource(cc)
        self.assertNotIn('("felt time", lambda: "built, not yet attached")', src)


if __name__ == "__main__":
    unittest.main()
