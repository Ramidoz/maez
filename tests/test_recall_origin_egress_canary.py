"""Recall-Origin Egress Canary -- a standing safety invariant.

GREEN-EXPECTED: this asserts existing egress behavior. A RED case means a real
leak was found -- escalate it as a finding; never weaken an assertion or add a
production fix in this file. See
docs/superpowers/specs/2026-06-05-recall-origin-egress-canary-design.md.
"""

from __future__ import annotations

import tempfile
import unittest
import importlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from starlette.requests import Request

from core.subscription_proxy.adapters.base import CallResult

_PII_MARKER = "canary-pii-7c1f@example.test"


class RecallFidelityTests(unittest.TestCase):
    """The egress_origin_class wristband survives the real recall path."""

    def test_core_row_origin_survives_real_recall(self):
        from scripts.recall_flip_eval import sandbox

        root = Path(tempfile.mkdtemp(prefix="recall_origin_canary_"))
        ctx = sandbox.sandbox_env(root)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(sandbox.restore_memory_patches)
        self.addCleanup(sandbox.teardown, root)
        sandbox.patch_memory_manager_base_db(root)
        sandbox.assert_sandbox(root)

        from memory.memory_manager import MemoryManager

        seeder = MemoryManager()
        seeder.core.add(
            ids=["core-priv-canary"],
            documents=[f"Reach the owner at {_PII_MARKER} per the private note."],
            metadatas=[
                {
                    "timestamp": "2026-06-04T12:00:00+00:00",
                    "type": "reasoning",
                    "egress_origin_class": "third_party_private_context",
                }
            ],
        )

        recalled = MemoryManager().recall_for_telegram("what should I know?")
        core_rows = recalled.get("core") or []
        match = [row for row in core_rows if row.get("id") == "core-priv-canary"]
        self.assertTrue(match, "seeded core row did not surface via real recall")
        meta = match[0].get("metadata") or {}
        self.assertEqual(meta.get("egress_origin_class"), "third_party_private_context")
        self.assertIn(_PII_MARKER, match[0].get("content", ""))


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
    return {"id": row_id, "content": content, "metadata": meta, "distance": 0.123}


class LocalRenderFidelityTests(unittest.TestCase):
    def test_local_render_keeps_full_content(self):
        # COVENANT: local-first means the local render is full-fidelity; refusal
        # lives at the cloud door, never here. This asserts we do NOT lobotomize.
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-priv",
                    f"email {_PII_MARKER}",
                    egress_origin_class="third_party_private_context",
                )
            ],
        }
        rendered = _mm().format_for_prompt(recalled)
        self.assertIn(_PII_MARKER, rendered)

    def test_provenanced_render_carries_origin_span(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-priv",
                    f"email {_PII_MARKER}",
                    egress_origin_class="third_party_private_context",
                )
            ],
        }
        provenanced = _mm().format_for_prompt_provenanced(recalled)
        priv = [
            span
            for span in provenanced.spans
            if span.origin_class == "third_party_private_context"
        ]
        self.assertTrue(priv, "private-origin span missing from provenanced render")
        self.assertTrue(all(span.redaction_allowed for span in priv))
        self.assertIn(_PII_MARKER, provenanced.text)


def _seg(origin_class: str, *, text: str, redaction_allowed: bool):
    from core.egress.gate import EgressSegment

    return EgressSegment(
        text=text,
        origin_class=origin_class,
        source_ref="raw:canary",
        redaction_allowed=redaction_allowed,
    )


def _cloud_req(segment):
    from core.egress.gate import EgressRequest

    return EgressRequest(
        call_class="cloud_model_inference",
        destination="anthropic",
        segments=[segment],
        caller="recall-origin-canary",
        request_id="canary",
    )


class DecideEgressMatrixTests(unittest.TestCase):
    def _decide(self, origin_class, *, redaction_allowed):
        from core.egress.gate import decide_egress

        return decide_egress(
            _cloud_req(
                _seg(
                    origin_class,
                    text=f"email {_PII_MARKER}",
                    redaction_allowed=redaction_allowed,
                )
            )
        )

    def test_owner_account_blocks(self):
        self.assertEqual(
            self._decide("owner_account_context", redaction_allowed=False).decision,
            "block",
        )

    def test_private_minimizable_redacts_pii_free(self):
        decision = self._decide("third_party_private_context", redaction_allowed=True)
        self.assertEqual(decision.decision, "redact")
        self.assertNotIn(_PII_MARKER, decision.sanitized_text())

    def test_owner_message_context_redacts(self):
        self.assertEqual(
            self._decide("owner_message_context", redaction_allowed=True).decision,
            "redact",
        )

    def test_untrusted_model_output_redacts(self):
        decision = self._decide("model_output", redaction_allowed=True)
        self.assertEqual(decision.decision, "redact")
        self.assertNotIn(_PII_MARKER, decision.sanitized_text())

    def test_non_private_allows(self):
        self.assertEqual(
            self._decide("public_fact", redaction_allowed=False).decision,
            "allow",
        )

    def test_missing_origin_falls_back_to_memory_redacts(self):
        # A row with no egress_origin_class renders as "memory" in provenance.
        self.assertEqual(
            self._decide("memory", redaction_allowed=True).decision,
            "redact",
        )

    def test_unknown_origin_fails_closed_never_allows(self):
        # The single most important fail-closed assertion.
        decision = self._decide("some_unrecognized_origin_xyz", redaction_allowed=True)
        self.assertIn(decision.decision, ("block", "redact"))
        self.assertNotEqual(decision.decision, "allow")


class _CapturingAdapter:
    name = "recall-origin-canary"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "recall-origin-canary-model"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt)
        return CallResult(reply="captured", model_used=model, input_toks=1, output_toks=1)


def _make_proxy_request(body: dict):
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "headers": [(b"x-maez-caller", b"recall-origin-canary")],
        },
        receive,
    )


def _drive_to_proxy(*, recalled):
    """Recalled dict -> provenanced render -> payload -> call_messages capture."""
    from core.routing import claude_tier
    from skills.web_interface import build_claude_router_cloud_payload

    owner_memory = _mm().format_for_prompt_provenanced(recalled)
    system_prompt, web_messages = build_claude_router_cloud_payload(
        owner_bridge=True,
        message="can you reason about this?",
        history=[{"role": "user", "content": "can you reason about this?"}],
        owner_memory=owner_memory,
    )
    cloud_messages = [
        claude_tier.CloudMessage(role=message["role"], content=message["content"])
        for message in web_messages
    ]
    captured: dict = {}

    def _capture(*, body_payload, model, caller, timeout_s=None):
        captured["body"] = body_payload
        from core.claude_tier import TierReply

        return TierReply("not used", model, 1, 1, {})

    with mock.patch("core.routing.claude_tier._post_chat_payload", side_effect=_capture):
        claude_tier.call_messages(
            system_prompt=system_prompt,
            messages=cloud_messages,
            model="recall-origin-canary-model",
            caller="recall-origin-canary",
        )
    return captured["body"]


class _ProxyCanaryBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "recall-origin-canary-test",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
                "MAEZ_IPHONE_INGEST_TOKEN": "dummy",
            },
            clear=False,
        )
        self._env.start()
        from core.subscription_proxy import server

        importlib.reload(server)
        self.server = server
        self.adapter = _CapturingAdapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop()
        self._env.stop()
        self._tmp.cleanup()

    def _audit_row(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            return con.execute(
                "SELECT egress_decision, prompt_preview, egress_shadow_mode, "
                "egress_origin_classes FROM calls"
            ).fetchone()


class ProxyBlockClassTests(_ProxyCanaryBase):
    async def test_owner_account_recalled_memory_is_blocked(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    f"owner note {_PII_MARKER}",
                    egress_origin_class="owner_account_context",
                )
            ],
        }
        body = _drive_to_proxy(recalled=recalled)
        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(_make_proxy_request(body))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])
        decision, _preview, _shadow, origins = self._audit_row()
        self.assertEqual(decision, "block")
        self.assertIn("owner_account_context", origins)


class ProxyRedactClassTests(_ProxyCanaryBase):
    async def test_redact_class_decision_and_audit_are_scrubbed(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-priv",
                    f"contact {_PII_MARKER} privately",
                    egress_origin_class="third_party_private_context",
                )
            ],
        }
        body = _drive_to_proxy(recalled=recalled)
        await self.server.chat_completions(_make_proxy_request(body))
        decision, prompt_preview, shadow_mode, origins = self._audit_row()

        self.assertEqual(decision, "redact")
        self.assertNotIn(_PII_MARKER, prompt_preview or "")
        self.assertIn("third_party_private_context", origins)

        # GRADUATED: redact-class forwarding is enforced by default. The
        # adapter receives the gate's sanitized prompt, not the original.
        self.assertEqual(shadow_mode, 0)
        self.assertEqual(len(self.adapter.prompts), 1)
        self.assertNotIn(_PII_MARKER, self.adapter.prompts[0])


if __name__ == "__main__":
    unittest.main()
