# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb v0.1 — owner-account provenance survives to the egress chokepoint.

The producer (github_skill) must emit ProvenancedText(owner_account_context),
and that span must reach the real subscription-proxy path and be refused (403,
adapter not called). No "tag then flatten": the witness is the door refusing it.
"""

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

from core.subscription_proxy.adapters.base import CallResult

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class OwnerAccountFactoryTests(unittest.TestCase):
    def test_factory_emits_owner_account_context_span_not_downgraded(self):
        from core.egress.provenance import ProvenancedText

        pt = ProvenancedText.owner_account_context(
            "private repo: secret-thing",
            source_ref="github:user_repos",
        )
        self.assertEqual(len(pt.spans), 1)
        span = pt.spans[0]
        self.assertEqual(span.origin_class, "owner_account_context")
        self.assertFalse(span.redaction_allowed)
        self.assertEqual(span.text, "private repo: secret-thing")
        self.assertEqual(pt.text, "private repo: secret-thing")


class GithubProducerTests(unittest.TestCase):
    def _skill_with_canary(self):
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = True
        skill.username = "CANARY_USER"
        skill._cache = {}
        skill._cache_time = {}
        skill.cache_ttl = 300
        skill.token = "x"
        skill.get_user_repos = lambda: [
            {
                "name": "CANARY_REPO",
                "private": True,
                "language": "Python",
                "updated_at": "2026-06-01T00:00:00Z",
                "description": "CANARY_DESC",
            }
        ]
        skill.get_recent_commits = lambda name, limit=1: []
        skill.get_user_activity = lambda: ["Pushed to CANARY_REPO: CANARY_MSG"]
        skill.get_trending_ai_repos = lambda n=5: []
        return skill

    def test_get_context_block_returns_owner_account_provenanced_text(self):
        from core.egress.provenance import ProvenancedText

        block = self._skill_with_canary().get_context_block()
        self.assertIsInstance(block, ProvenancedText)
        self.assertTrue(block.spans)
        self.assertTrue(
            all(s.origin_class == "owner_account_context" for s in block.spans)
        )
        self.assertIn("CANARY_REPO", block.text)
        self.assertIn("[GITHUB]", block.text)

    def test_disabled_skill_returns_empty_provenanced_text(self):
        from core.egress.provenance import ProvenancedText
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = False
        block = skill.get_context_block()
        self.assertIsInstance(block, ProvenancedText)
        self.assertFalse(block)
        self.assertEqual(block.text, "")


class DaemonDualViewTests(unittest.TestCase):
    """Daemon local paths use .text; the ProvenancedText handle remains intact."""

    def test_github_injection_uses_text_view_for_local_paths(self):
        import inspect
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon)
        self.assertIn("self._last_github_block.text", src)
        self.assertNotIn("{self._last_github_block}", src)
        self.assertNotIn("self._last_github_block,", src)


class _NeverCalledAdapter:
    name = "shadow_test"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "shadow-test"

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


class GithubCanaryReachesProxyAndIsRefused(unittest.IsolatedAsyncioTestCase):
    """Producer spans hit the proxy path and the door refuses them."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "github-canary-test",
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

    def _github_block_with_canary(self):
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = True
        skill.username = "CANARY_USER"
        skill._cache = {}
        skill._cache_time = {}
        skill.cache_ttl = 300
        skill.token = "x"
        skill.get_user_repos = lambda: [
            {
                "name": "GH_CANARY_42",
                "private": True,
                "language": "Python",
                "updated_at": "2026-06-01T00:00:00Z",
                "description": "secret",
            }
        ]
        skill.get_recent_commits = lambda name, limit=1: []
        skill.get_user_activity = lambda: []
        skill.get_trending_ai_repos = lambda n=5: []
        return skill.get_context_block()

    def _proxy_request(self, block, *, redaction_allowed: bool | None = None):
        from starlette.requests import Request

        wire = block.to_wire()
        if redaction_allowed is not None:
            for span in wire:
                span["redaction_allowed"] = redaction_allowed
        body = json.dumps(
            {
                "model": "shadow-test",
                "stream": False,
                "maez_egress_segments": {
                    "schema_version": "maez-egress-provenance-v1",
                    "parts": {"user": wire},
                },
                "messages": [{"role": "user", "content": block.text}],
            }
        ).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"github-canary")],
            },
            receive,
        )

    async def test_github_owner_account_canary_is_refused_at_proxy(self):
        block = self._github_block_with_canary()
        self.assertTrue(
            all(s.origin_class == "owner_account_context" for s in block.spans)
        )
        self.assertIn("GH_CANARY_42", block.text)

        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(self._proxy_request(block))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])
        self.assertNotIn("GH_CANARY_42", json.dumps(self.adapter.prompts))

    async def test_block_holds_with_redaction_allowed_and_records_content_free(self):
        block = self._github_block_with_canary()
        try:
            await self.server.chat_completions(
                self._proxy_request(block, redaction_allowed=True)
            )
        except HTTPException:
            pass
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
        self.assertNotIn("GH_CANARY_42", prompt_preview or "")


if __name__ == "__main__":
    unittest.main()
