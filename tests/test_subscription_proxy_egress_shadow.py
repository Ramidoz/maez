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
        self.system_prompts: list[str | None] = []
        self.reply_text = "echo rohit@example.com and memory_id_123"

    def handles_model(self, model: str) -> bool:
        return model == "shadow-test"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt: str, system_prompt: str | None, model: str):
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)
        return CallResult(
            reply=self.reply_text,
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
                "SELECT prompt_preview, reply_preview, prompt_hash, "
                "egress_decision, egress_reason_codes, egress_content_digest, "
                "egress_provenance_mode "
                "FROM calls"
            ).fetchone()

        self.assertIsNotNone(row)
        (
            prompt_preview,
            reply_preview,
            prompt_hash,
            decision,
            reason_codes,
            digest,
            mode,
        ) = row
        self.assertNotIn("rohit@example.com", prompt_preview)
        self.assertNotIn("memory_id_123", prompt_preview)
        self.assertNotIn("rohit@example.com", reply_preview)
        self.assertNotIn("memory_id_123", reply_preview)
        self.assertTrue(prompt_hash.startswith("hmac-sha256:"))
        self.assertEqual(decision, "redact")
        self.assertIn("minimized_private_context", reason_codes)
        self.assertTrue(digest.startswith("hmac-sha256:"))
        self.assertEqual(mode, "legacy_conservative")

    async def test_role_aware_public_spans_allow_and_cover_system_user_history(self):
        from starlette.requests import Request

        body = (
            b'{"model":"shadow-test","stream":false,'
            b'"maez_egress_segments":{"schema_version":"maez-egress-provenance-v1",'
            b'"destination":"subscription_proxy:shadow_test","parts":{'
            b'"system":[{"text":"Public system rule","origin_class":"system_bounded_query",'
            b'"source_ref":"system:test","redaction_allowed":false}],'
            b'"assistant_history":[{"text":"[assistant]\\nEarlier public answer",'
            b'"origin_class":"public_fact","source_ref":"history:test",'
            b'"redaction_allowed":false}],'
            b'"user":[{"text":"Public question","origin_class":"public_fact",'
            b'"source_ref":"user:test","redaction_allowed":false}]'
            b'}},'
            b'"messages":['
            b'{"role":"system","content":"Public system rule"},'
            b'{"role":"assistant","content":"Earlier public answer"},'
            b'{"role":"user","content":"Public question"}]}'
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"public-shadow")],
            },
            receive,
        )

        response = await self.server.chat_completions(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.adapter.system_prompts, ["Public system rule"])
        self.assertEqual(
            self.adapter.prompts,
            ["[assistant]\nEarlier public answer\n\nPublic question"],
            "shadow mode must pass the original cloud-bound user/history text",
        )
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, "
                "egress_origin_classes, egress_provenance_mode FROM calls"
            ).fetchone()

        self.assertEqual(row[0], "allow")
        self.assertIn("non_private_allowed", row[1])
        self.assertIn("system_bounded_query", row[2])
        self.assertIn("public_fact", row[2])
        self.assertEqual(row[3], "span_bundle")

    async def test_missing_system_span_fails_safe_as_unclassified_shadow_only(self):
        from starlette.requests import Request

        body = (
            b'{"model":"shadow-test","stream":false,'
            b'"maez_egress_segments":{"schema_version":"maez-egress-provenance-v1",'
            b'"destination":"subscription_proxy:shadow_test","parts":{'
            b'"user":[{"text":"Public question","origin_class":"public_fact",'
            b'"source_ref":"user:test","redaction_allowed":false}]'
            b'}},'
            b'"messages":['
            b'{"role":"system","content":"Public system rule"},'
            b'{"role":"user","content":"Public question"}]}'
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"mismatch-shadow")],
            },
            receive,
        )

        response = await self.server.chat_completions(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.adapter.prompts, ["Public question"])
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, "
                "egress_provenance_mode FROM calls"
            ).fetchone()

        self.assertEqual(row[0], "block")
        self.assertIn("unclassified", row[1])
        self.assertEqual(row[2], "span_bundle_invalid")

    async def test_destination_divergence_fails_safe_as_unclassified(self):
        from starlette.requests import Request

        body = (
            b'{"model":"shadow-test","stream":false,'
            b'"maez_egress_segments":{"schema_version":"maez-egress-provenance-v1",'
            b'"destination":"http://127.0.0.1:11438/v1/chat/completions",'
            b'"parts":{"user":[{"text":"Public question","origin_class":"public_fact",'
            b'"source_ref":"user:test","redaction_allowed":false}]}},'
            b'"messages":[{"role":"user","content":"Public question"}]}'
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"destination-shadow")],
            },
            receive,
        )

        response = await self.server.chat_completions(req)

        self.assertEqual(response.status_code, 200)
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes FROM calls"
            ).fetchone()

        self.assertEqual(row[0], "block")
        self.assertIn("unclassified", row[1])

    async def test_private_and_reserved_canaries_do_not_appear_raw_in_telemetry(self):
        from starlette.requests import Request

        prompt_canary = "SYNTH_PRIVATE_CANARY_R42"
        reply_canary = "SYNTH_REPLY_CANARY_R42"
        self.adapter.reply_text = reply_canary
        body = (
            b'{"model":"shadow-test","stream":false,'
            b'"maez_egress_segments":{"schema_version":"maez-egress-provenance-v1",'
            b'"destination":"subscription_proxy:shadow_test","parts":{'
            b'"user":[{"text":"SYNTH_PRIVATE_CANARY_R42","origin_class":"memory",'
            b'"source_ref":"memory:canary","redaction_allowed":true}]}},'
            b'"messages":[{"role":"user","content":"SYNTH_PRIVATE_CANARY_R42"}]}'
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"canary-shadow")],
            },
            receive,
        )

        response = await self.server.chat_completions(req)

        self.assertEqual(response.status_code, 200)
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT prompt_preview, reply_preview, prompt_hash, "
                "egress_decision, egress_reason_codes, egress_content_digest "
                "FROM calls"
            ).fetchone()

        rendered = repr(row)
        self.assertNotIn(prompt_canary, rendered)
        self.assertNotIn(reply_canary, rendered)
        self.assertTrue(row[2].startswith("hmac-sha256:"))
        self.assertTrue(row[5].startswith("hmac-sha256:"))
        self.assertEqual(row[3], "redact")
        self.assertIn("minimized_private_context", row[4])

    async def test_reserved_canary_shadow_under_killswitch_still_flows(self):
        # Reserved-denied is ENFORCED by default now; this asserts the rollback
        # kill-switch (MAEZ_EGRESS_RESERVED_DENIED_SHADOW=1) reverts to the legacy
        # shadow behavior (block recorded, call still flows).
        from starlette.requests import Request

        canary = "SYNTH_SOUL_CANARY_R42"
        body = (
            b'{"model":"shadow-test","stream":false,'
            b'"maez_egress_segments":{"schema_version":"maez-egress-provenance-v1",'
            b'"destination":"subscription_proxy:shadow_test","parts":{'
            b'"user":[{"text":"SYNTH_SOUL_CANARY_R42","origin_class":"soul",'
            b'"source_ref":"soul:canary","redaction_allowed":false}]}},'
            b'"messages":[{"role":"user","content":"SYNTH_SOUL_CANARY_R42"}]}'
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"reserved-shadow")],
            },
            receive,
        )

        with mock.patch.dict(
            os.environ, {"MAEZ_EGRESS_RESERVED_DENIED_SHADOW": "1"}
        ):
            response = await self.server.chat_completions(req)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.adapter.prompts, [canary])
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT prompt_preview, egress_decision, "
                "egress_reason_codes FROM calls"
            ).fetchone()

        self.assertNotIn(canary, repr(row))
        self.assertEqual(row[1], "block")
        self.assertIn("reserved_denied_raw", row[2])


if __name__ == "__main__":
    unittest.main()
