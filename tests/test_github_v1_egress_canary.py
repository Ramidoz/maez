from __future__ import annotations

import importlib
import json
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from starlette.requests import Request

from core.subscription_proxy.adapters.base import CallResult


class _RecallCollection:
    def __init__(self):
        self._rows = []

    def add(self, *, ids, documents, metadatas):
        for mem_id, doc, meta in zip(ids, documents, metadatas, strict=False):
            self._rows.append(
                {
                    "id": mem_id,
                    "document": doc,
                    "metadata": dict(meta or {}),
                }
            )

    def count(self):
        return len(self._rows)

    def get(self, ids=None, include=None, limit=None, where=None):
        rows = list(self._rows)
        if ids is not None:
            wanted = set(ids)
            rows = [row for row in rows if row["id"] in wanted]
        if where:
            rows = [
                row
                for row in rows
                if all(row["metadata"].get(k) == v for k, v in where.items())
            ]
        if limit is not None:
            rows = rows[:limit]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["document"] for row in rows],
            "metadatas": [dict(row["metadata"]) for row in rows],
        }

    def query(self, *, query_texts, n_results):
        query = (query_texts[0] if query_texts else "").lower()
        terms = {term for term in re.findall(r"[a-z0-9]+", query) if len(term) > 2}

        def distance(row):
            content = row["document"].lower()
            hits = sum(1 for term in terms if term in content)
            return 1.0 - min(0.9, hits * 0.2)

        rows = sorted(self._rows, key=distance)[:n_results]
        return {
            "ids": [[row["id"] for row in rows]],
            "documents": [[row["document"] for row in rows]],
            "metadatas": [[dict(row["metadata"]) for row in rows]],
            "distances": [[distance(row) for row in rows]],
        }


def _memory_manager_with_fake_collections():
    from memory.memory_manager import MemoryManager

    mm = MemoryManager.__new__(MemoryManager)
    mm.core = _RecallCollection()
    mm.daily = _RecallCollection()
    mm.raw = _RecallCollection()
    return mm


class _NeverCalledAdapter:
    name = "github_v1_canary"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "github-v1-canary"

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
            "headers": [(b"x-maez-caller", b"github-v1-canary")],
        },
        receive,
    )


class GithubV1EgressCanaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "github-v1-canary-test",
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

    async def test_ingested_repo_count_memory_recalled_to_cloud_is_refused(self):
        from core.information_limb import github_v1
        from core.routing import claude_tier
        from skills.web_interface import build_claude_router_cloud_payload

        memory = _memory_manager_with_fake_collections()
        github_v1.admit_repo_count_to_body(
            memory=memory,
            repo_count=7,
            count_field="public_repos",
            ingest_record_id="ir-1",
            fetch_batch_id="fb-1",
        )
        recalled = memory.recall_for_telegram("GitHub public repositories owner profile")
        self.assertEqual(len(recalled["raw"]), 1)
        self.assertEqual(
            recalled["raw"][0]["metadata"].get("egress_origin_class"),
            "owner_account_context",
        )
        owner_memory = memory.format_for_prompt_provenanced(recalled)
        self.assertIn("GitHub reports 7 public repositories", owner_memory.text)
        self.assertIn("owner_account_context", {span.origin_class for span in owner_memory.spans})

        system_prompt, web_messages = build_claude_router_cloud_payload(
            owner_bridge=True,
            message="how many repos?",
            history=[{"role": "user", "content": "how many repos?"}],
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
                model="github-v1-canary",
                caller="github-v1-canary",
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
        self.assertNotIn("GitHub reports 7", prompt_preview or "")


if __name__ == "__main__":
    unittest.main()
