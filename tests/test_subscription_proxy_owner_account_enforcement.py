# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 1 ENFORCEMENT at the live cloud chokepoint.

Unlike the deliberate shadow rollout of the other gate classes, owner_account_context
is born-enforced: when decide_egress blocks it, the subscription proxy must NOT call
the adapter — personal-account data never reaches the cloud model. This is the
integration witness that the gate decision is acted on, not merely logged.

(The gate returning block for owner_account_context is unit-proven in
tests/test_egress_owner_account_firewall.py. This proves the proxy honors it.)
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from core.subscription_proxy.adapters.base import CallResult

_CANARY = "OWNER_ACCOUNT_CANARY_R42"


class _Adapter:
    name = "shadow_test"

    def __init__(self):
        self.prompts: list[str] = []
        self.system_prompts: list[str | None] = []

    def handles_model(self, model: str) -> bool:
        return model == "shadow-test"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt: str, system_prompt: str | None, model: str):
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)
        return CallResult(
            reply="this reply should never be produced",
            model_used=model,
            input_toks=1,
            output_toks=1,
        )


class OwnerAccountEgressEnforcementTests(unittest.IsolatedAsyncioTestCase):
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

    def _owner_account_request(self):
        from starlette.requests import Request

        body = json.dumps(
            {
                "model": "shadow-test",
                "stream": False,
                "maez_egress_segments": {
                    "schema_version": "maez-egress-provenance-v1",
                    "parts": {
                        "user": [
                            {
                                "text": _CANARY,
                                "origin_class": "owner_account_context",
                                "source_ref": "owner_account.reddit.saved:1",
                                "redaction_allowed": True,
                            }
                        ],
                    },
                },
                "messages": [{"role": "user", "content": _CANARY}],
            }
        ).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"enforce-test")],
            },
            receive,
        )

    async def test_owner_account_block_is_enforced_adapter_not_called(self):
        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(self._owner_account_request())
        self.assertEqual(ctx.exception.status_code, 403)
        # The adapter was NEVER called — personal-account data did not reach the cloud.
        self.assertEqual(self.adapter.prompts, [])
        self.assertNotIn(_CANARY, json.dumps(self.adapter.prompts))

    async def test_owner_account_block_records_content_free_enforced_telemetry(self):
        try:
            await self.server.chat_completions(self._owner_account_request())
        except HTTPException:
            pass
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, egress_shadow_mode, "
                "prompt_preview, reply_preview, egress_origin_classes FROM calls"
            ).fetchone()
        self.assertIsNotNone(row, "the blocked call must still record content-free telemetry")
        decision, reasons, shadow_mode, prompt_preview, reply_preview, origin_classes = row
        self.assertEqual(decision, "block")
        self.assertIn("owner_account_context_blocked_default", reasons)
        # ENFORCED, not shadow — the whole point of this slice.
        self.assertEqual(shadow_mode, 0)
        self.assertIn("owner_account_context", origin_classes)
        # content-free: the canary text never lands in the record.
        self.assertNotIn(_CANARY, prompt_preview or "")
        self.assertNotIn(_CANARY, reply_preview or "")


if __name__ == "__main__":
    unittest.main()
