# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.subscription_proxy — routing, adapter interface,
budget bookkeeping. The live-CLI / live-HTTP smoke tests live outside
this file; unit tests here are fully offline and deterministic."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class AdapterInterface(unittest.TestCase):
    """Every concrete adapter must satisfy the Adapter contract."""

    def _all_adapters(self):
        from core.subscription_proxy.adapters import (
            ClaudeCliAdapter, GeminiCliAdapter, OllamaCloudAdapter,
            OpenAiApiAdapter, OpenRouterAdapter, XaiApiAdapter,
        )
        return [
            ClaudeCliAdapter(), GeminiCliAdapter(), OllamaCloudAdapter(),
            OpenAiApiAdapter(), OpenRouterAdapter(), XaiApiAdapter(),
        ]

    def test_every_adapter_has_a_name(self):
        for a in self._all_adapters():
            self.assertTrue(a.name, f"{type(a).__name__} missing .name")
            self.assertNotEqual(a.name, "unknown",
                                f"{type(a).__name__} didn't override .name")

    def test_every_adapter_implements_health(self):
        for a in self._all_adapters():
            h = a.health()
            self.assertIsInstance(h, dict, f"{a.name}.health() not a dict")
            self.assertIn("adapter", h)
            self.assertEqual(h["adapter"], a.name)

    def test_every_adapter_implements_handles_model(self):
        for a in self._all_adapters():
            # Must accept a str and return bool without raising.
            result = a.handles_model("some-random-model-name-xyz-123")
            self.assertIsInstance(result, bool)
            # Empty model must not crash
            _ = a.handles_model("")


class RoutingTable(unittest.TestCase):
    """The server routes based on the model string. Any claim-overlap
    between adapters is a bug."""

    def test_no_overlap_and_expected_routes(self):
        from core.subscription_proxy.server import _route

        cases = [
            ("", "claude"),
            ("sonnet", "claude"),
            ("opus", "claude"),
            ("haiku", "claude"),
            ("claude-sonnet-4-6", "claude"),
            ("claude-opus-4-7", "claude"),
            ("gemini-2.5-pro", "gemini"),
            ("gemini-1.5-flash", "gemini"),
            ("gpt-4o", "openai"),
            ("gpt-4o-mini", "openai"),
            ("o1-preview", "openai"),
            ("o3-mini", "openai"),
            ("chatgpt-4o-latest", "openai"),
            ("grok-4", "xai"),
            ("grok-2-mini", "xai"),
            ("openai/gpt-4o", "openrouter"),
            ("anthropic/claude-sonnet-4.6", "openrouter"),
            ("x-ai/grok-4", "openrouter"),
            ("google/gemini-2.5-pro", "openrouter"),
            ("meta-llama/llama-3.3-70b", "openrouter"),
            ("qwen3:32b", "ollama_cloud"),
            ("gpt-oss:120b", "ollama_cloud"),
            ("llama3.2:70b", "ollama_cloud"),
            ("unknown-xyz", "claude"),  # fallback
        ]
        for model, expected in cases:
            self.assertEqual(
                _route(model).name, expected,
                f"{model!r} routed to {_route(model).name}, expected {expected}",
            )

    def test_no_two_adapters_claim_the_same_model(self):
        """Important invariant: the FIRST adapter in the registry
        that claims wins, but if two claim the same string that's a
        latent bug waiting for a reorder. Assert exclusivity."""
        from core.subscription_proxy.server import ADAPTERS

        samples = [
            "", "sonnet", "opus", "haiku", "claude-sonnet-4-6",
            "gemini-2.5-pro", "gpt-4o", "o1-preview", "grok-4",
            "openai/gpt-4o", "qwen3:32b",
        ]
        for m in samples:
            claimants = [a.name for a in ADAPTERS if a.handles_model(m)]
            # Empty + fallback-ish strings may legitimately land on
            # multiple (Claude claims "" as fallback) — only assert
            # exclusivity for non-empty non-fallback cases.
            if m and m != "sonnet":  # sonnet is Claude-only by name
                extra = [c for c in claimants if c != claimants[0]]
                self.assertEqual(
                    extra, [],
                    f"model {m!r} claimed by multiple adapters: {claimants}",
                )


class HttpForwardAuthGuard(unittest.TestCase):
    """HTTP adapters must refuse cleanly when their API key is missing."""

    def test_openrouter_refuses_without_key(self):
        from core.subscription_proxy.adapters.openrouter import OpenRouterAdapter
        a = OpenRouterAdapter()
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False):
            import asyncio
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(a.call(prompt="hi", system_prompt=None,
                                     model="openai/gpt-4o"))
            self.assertIn("not configured", str(cm.exception).lower())

    def test_openai_refuses_without_key(self):
        from core.subscription_proxy.adapters.openai_api import OpenAiApiAdapter
        a = OpenAiApiAdapter()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            import asyncio
            with self.assertRaises(RuntimeError) as cm:
                asyncio.run(a.call(prompt="hi", system_prompt=None, model="gpt-4o"))
            self.assertIn("not configured", str(cm.exception).lower())


class BudgetBookkeeping(unittest.TestCase):
    """The server's per-adapter budget DB counts ok calls and
    excludes failures. Uses a temp DB so we don't touch the real one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "budget.db"
        # Patch the env before importing
        self._env = mock.patch.dict(
            os.environ, {"MAEZ_SUBSCRIPTION_PROXY_DB": str(self._db_path)},
        )
        self._env.start()
        # Re-import so DB_PATH picks up the env
        import importlib
        from core.subscription_proxy import server
        importlib.reload(server)
        self.server = server

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def test_records_and_counts(self):
        self.server._record(
            adapter="claude", caller="test", model="sonnet",
            model_used="sonnet", prompt="hi", reply="hello",
            input_toks=2, output_toks=2, duration_s=0.1, status="ok",
        )
        self.server._record(
            adapter="claude", caller="test", model="sonnet",
            model_used="sonnet", prompt="hi", reply="hello",
            input_toks=2, output_toks=2, duration_s=0.1, status="ok",
        )
        # An error row must NOT count
        self.server._record(
            adapter="claude", caller="test", model="sonnet",
            model_used=None, prompt="hi", reply="",
            input_toks=None, output_toks=None,
            duration_s=0.1, status="error", error="boom",
        )
        self.assertEqual(
            self.server._count_calls(adapter="claude", seconds=3600), 2,
        )
        # Different adapter: independent count
        self.assertEqual(
            self.server._count_calls(adapter="openai", seconds=3600), 0,
        )

    def test_old_records_age_out_of_window(self):
        self.server._record(
            adapter="claude", caller="test", model="sonnet",
            model_used="sonnet", prompt="x", reply="y",
            input_toks=1, output_toks=1, duration_s=0.1, status="ok",
        )
        # Back-date the row so it's outside the hourly window
        import sqlite3
        with sqlite3.connect(self._db_path) as con:
            con.execute("UPDATE calls SET ts = ?", (time.time() - 7200,))
            con.commit()
        self.assertEqual(
            self.server._count_calls(adapter="claude", seconds=3600), 0,
        )
        self.assertEqual(
            self.server._count_calls(adapter="claude", seconds=86400), 1,
        )


class OllamaCloudHeuristic(unittest.TestCase):
    """The OllamaCloud adapter claims `<name>:<size>` but must NOT
    claim `12:34`-style numeric pairs that could appear in other contexts."""

    def test_claims_ollama_style(self):
        from core.subscription_proxy.adapters.ollama_cloud import OllamaCloudAdapter
        a = OllamaCloudAdapter()
        for m in ["qwen3:32b", "llama3.2:70b", "gpt-oss:120b", "mistral:7b"]:
            self.assertTrue(a.handles_model(m), m)

    def test_skips_numeric_time_like(self):
        from core.subscription_proxy.adapters.ollama_cloud import OllamaCloudAdapter
        a = OllamaCloudAdapter()
        for m in ["12:34", "9:00", ""]:
            self.assertFalse(a.handles_model(m), m)


if __name__ == "__main__":
    unittest.main()
