# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Reserved-denied cloud enforcement (named follow-up to Personal Data Limb Slice 1).

soul / private_thoughts / credential_material / inner_residue /
maez_internal_reflection / crisis_held_content must not reach a cloud model.
Deliberate flip from the shadow rollout to ENFORCE, default-on, with
MAEZ_EGRESS_RESERVED_DENIED_SHADOW=1 as the rollback kill-switch.

The proxy-telemetry survey showed this is a LATENT hole — only deliberate canaries
(egress-provenance-observe, live-canary-soul-v2) ever drove a reserved class to
cloud, all in shadow; no real cognition flow did, and credential_material/
private_thoughts were never even probed. So default-on with a kill-switch is the
right deliberate flip, not a stop-the-bleeding emergency.
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

_CANARY = "SYNTH_SOUL_CANARY_R42"


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


class ReservedDeniedEnforcementTests(unittest.IsolatedAsyncioTestCase):
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

    def _reserved_request(self, origin_class: str = "soul", text: str = _CANARY):
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
                                "text": text,
                                "origin_class": origin_class,
                                "source_ref": f"{origin_class}:canary",
                                "redaction_allowed": False,
                            }
                        ]
                    },
                },
                "messages": [{"role": "user", "content": text}],
            }
        ).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"reserved-enforce-test")],
            },
            receive,
        )

    async def test_reserved_soul_block_is_enforced_by_default(self):
        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(self._reserved_request("soul"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])  # soul never reached the cloud

    async def test_reserved_credential_material_block_is_enforced_by_default(self):
        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(
                self._reserved_request("credential_material", "SYNTH_CRED_CANARY_R42")
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])

    async def test_reserved_block_records_content_free_enforced_telemetry(self):
        try:
            await self.server.chat_completions(self._reserved_request("soul"))
        except HTTPException:
            pass
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, egress_shadow_mode, "
                "prompt_preview, egress_origin_classes FROM calls"
            ).fetchone()
        self.assertIsNotNone(row)
        decision, reasons, shadow_mode, prompt_preview, origins = row
        self.assertEqual(decision, "block")
        self.assertIn("reserved_denied_raw", reasons)
        self.assertEqual(shadow_mode, 0)  # ENFORCED, not shadow
        self.assertIn("soul", origins)
        self.assertNotIn(_CANARY, prompt_preview or "")

    async def test_killswitch_reverts_reserved_to_shadow(self):
        # Rollback path: MAEZ_EGRESS_RESERVED_DENIED_SHADOW=1 reverts to legacy
        # observe behavior (the block is recorded, but the call still flows).
        with mock.patch.dict(os.environ, {"MAEZ_EGRESS_RESERVED_DENIED_SHADOW": "1"}):
            response = await self.server.chat_completions(self._reserved_request("soul"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.adapter.prompts, [_CANARY])
        with sqlite3.connect(self.db_path) as con:
            shadow_mode = con.execute("SELECT egress_shadow_mode FROM calls").fetchone()[0]
        self.assertEqual(shadow_mode, 1)

    async def test_owner_account_enforcement_unchanged(self):
        # Regression: owner_account_context stays born-enforced regardless of the
        # reserved kill-switch (it is NOT gated by it).
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
                                "text": "OWNER_ACCT_CANARY",
                                "origin_class": "owner_account_context",
                                "source_ref": "owner_account.reddit.saved:1",
                                "redaction_allowed": True,
                            }
                        ]
                    },
                },
                "messages": [{"role": "user", "content": "OWNER_ACCT_CANARY"}],
            }
        ).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"reserved-enforce-test")],
            },
            receive,
        )
        with mock.patch.dict(os.environ, {"MAEZ_EGRESS_RESERVED_DENIED_SHADOW": "1"}):
            with self.assertRaises(HTTPException) as ctx:
                await self.server.chat_completions(req)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])


if __name__ == "__main__":
    unittest.main()
