from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from starlette.requests import Request

from core.subscription_proxy.adapters.base import CallResult

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _mm():
    from memory.memory_manager import MemoryManager

    return MemoryManager.__new__(MemoryManager)


def _raw_row(row_id: str, content: str, *, egress_origin_class: str | None = None):
    meta = {
        "cycle": 7,
        "timestamp": "2026-06-04T12:00:00+00:00",
        "type": "reasoning",
    }
    if egress_origin_class:
        meta["egress_origin_class"] = egress_origin_class
    return {
        "id": row_id,
        "content": content,
        "metadata": meta,
        "distance": 0.123,
    }


class ProvenancedRecallRendererTests(unittest.TestCase):
    def test_provenanced_text_matches_existing_string_renderer(self):
        recalled = {
            "core": [{"id": "core-a", "content": "core continuity", "metadata": {}}],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                ),
                _raw_row("raw-ordinary", "ordinary memory"),
            ],
        }
        mm = _mm()

        text = mm.format_for_prompt(recalled, max_chars=8000)
        provenanced = mm.format_for_prompt_provenanced(recalled, max_chars=8000)

        self.assertEqual(provenanced.text, text)

    def test_owner_account_row_gets_owner_account_span(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                )
            ],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)
        owner_spans = [
            span for span in provenanced.spans
            if "OWNER_ACCOUNT_MEMORY_CANARY" in span.text
        ]

        self.assertTrue(owner_spans)
        self.assertTrue(
            all(span.origin_class == "owner_account_context" for span in owner_spans)
        )
        self.assertTrue(all(not span.redaction_allowed for span in owner_spans))

    def test_mixed_recall_uses_per_row_spans(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                ),
                _raw_row("raw-ordinary", "ORDINARY_MEMORY_CANARY"),
            ],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)
        owner_origins = {
            span.origin_class
            for span in provenanced.spans
            if "OWNER_ACCOUNT_MEMORY_CANARY" in span.text
        }
        ordinary_origins = {
            span.origin_class
            for span in provenanced.spans
            if "ORDINARY_MEMORY_CANARY" in span.text
        }

        self.assertEqual(owner_origins, {"owner_account_context"})
        self.assertEqual(ordinary_origins, {"memory"})
        self.assertIn("owner_account_context", {s.origin_class for s in provenanced.spans})
        self.assertIn("memory", {s.origin_class for s in provenanced.spans})

    def test_legacy_rows_have_no_owner_account_span(self):
        recalled = {
            "core": [{"id": "core-a", "content": "legacy core", "metadata": {}}],
            "daily": [],
            "raw": [_raw_row("raw-ordinary", "legacy raw")],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)

        self.assertNotIn(
            "owner_account_context",
            {span.origin_class for span in provenanced.spans},
        )
        self.assertIn("memory", {span.origin_class for span in provenanced.spans})


class _NeverCalledAdapter:
    name = "owner_memory_canary"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "owner-memory-test"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt)
        return CallResult(
            reply="must never be produced",
            model_used=model,
            input_toks=1,
            output_toks=1,
        )


def _make_proxy_request(body: dict):
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "headers": [(b"x-maez-caller", b"owner-memory-canary")],
        },
        receive,
    )


class OwnerAccountMemoryCanaryProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "owner-memory-canary-test",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
                "MAEZ_IPHONE_INGEST_TOKEN": "dummy",
            },
            clear=False,
        )
        self._env.start()
        from core.subscription_proxy import server

        importlib.reload(server)
        self.server = server
        self.adapter = _NeverCalledAdapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop()
        self._env.stop()
        self._tmp.cleanup()

    async def test_owner_account_memory_recalled_to_cloud_is_refused(self):
        from core.routing import claude_tier
        from skills.web_interface import build_claude_router_cloud_payload

        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                )
            ],
        }
        owner_memory = _mm().format_for_prompt_provenanced(recalled)
        system_prompt, web_messages = build_claude_router_cloud_payload(
            owner_bridge=True,
            message="can you reason about this?",
            history=[{"role": "user", "content": "can you reason about this?"}],
            owner_memory=owner_memory,
        )
        cloud_messages = [
            claude_tier.CloudMessage(role=m["role"], content=m["content"])
            for m in web_messages
        ]

        captured: dict = {}

        def _capture_payload(*, body_payload, model, caller, timeout_s=None):
            captured["body"] = body_payload
            from core.claude_tier import TierReply

            return TierReply("not used", model, 1, 1, {})

        with mock.patch(
            "core.routing.claude_tier._post_chat_payload",
            side_effect=_capture_payload,
        ):
            claude_tier.call_messages(
                system_prompt=system_prompt,
                messages=cloud_messages,
                model="owner-memory-test",
                caller="owner-memory-canary",
            )

        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(_make_proxy_request(captured["body"]))

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])

        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, egress_shadow_mode, "
                "prompt_preview, egress_origin_classes FROM calls"
            ).fetchone()

        self.assertIsNotNone(row)
        decision, reasons, shadow_mode, prompt_preview, origin_classes = row
        self.assertEqual(decision, "block")
        self.assertIn("owner_account_context_blocked_default", reasons)
        self.assertEqual(shadow_mode, 0)
        self.assertIn("owner_account_context", origin_classes)
        self.assertNotIn("OWNER_ACCOUNT_MEMORY_CANARY", prompt_preview or "")


if __name__ == "__main__":
    unittest.main()
