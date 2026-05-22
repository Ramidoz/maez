from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.subscription_proxy.adapters.base import CallResult


class _Adapter:
    name = "shadow_test"

    def __init__(self):
        self.prompts: list[str] = []

    def handles_model(self, model: str) -> bool:
        return model == "shadow-test"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt: str, system_prompt: str | None, model: str):
        self.prompts.append(prompt)
        return CallResult(
            reply="ok",
            model_used=model,
            input_toks=1,
            output_toks=1,
        )


class SubscriptionProxyEgressShadowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "test-egress-key",
            },
            clear=False,
        )
        self._env.start()
        from core.subscription_proxy import server

        importlib.reload(server)
        self.server = server
        self.adapter = _Adapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop()
        self._env.stop()
        self._tmp.cleanup()

    async def test_shadow_mode_records_decision_without_mutating_adapter_payload(self):
        from starlette.requests import Request

        body = (
            b'{"model":"shadow-test","stream":false,"messages":['
            b'{"role":"user","content":"Owner said email rohit@example.com and memory_id_123"}]}'
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"shadow-test")],
            },
            receive,
        )

        response = await self.server.chat_completions(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.adapter.prompts,
            ["Owner said email rohit@example.com and memory_id_123"],
            "shadow mode must not mutate the adapter payload",
        )
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT prompt_preview, egress_decision, egress_reason_codes, "
                "egress_content_digest FROM calls"
            ).fetchone()

        self.assertIsNotNone(row)
        prompt_preview, decision, reason_codes, digest = row
        self.assertNotIn("rohit@example.com", prompt_preview)
        self.assertNotIn("memory_id_123", prompt_preview)
        self.assertEqual(decision, "redact")
        self.assertIn("minimized_private_context", reason_codes)
        self.assertTrue(digest.startswith("hmac-sha256:"))


if __name__ == "__main__":
    unittest.main()
