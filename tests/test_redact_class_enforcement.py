from __future__ import annotations

import os
import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.subscription_proxy.adapters.base import CallResult
from fastapi import HTTPException
from starlette.requests import Request

_PRIV = "secret-pii-9a2b@example.test"
_PUB_SYS = "PUBLIC-SYSTEM-MARKER"
_PUB_USER = "PUBLIC-USER-MARKER"


class RedactEnforcedHelperTests(unittest.TestCase):
    def _helper(self):
        from core.subscription_proxy import server

        return server

    def test_default_is_shadow(self):
        server = self._helper()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_EGRESS_REDACT_SHADOW", None)
            self.assertFalse(server._redact_enforced())

    def test_enforce_opt_in(self):
        server = self._helper()
        with mock.patch.dict(
            os.environ, {"MAEZ_EGRESS_REDACT_SHADOW": "0"}, clear=False
        ):
            self.assertTrue(server._redact_enforced())

    def test_kill_switch_reverts(self):
        server = self._helper()
        with mock.patch.dict(
            os.environ, {"MAEZ_EGRESS_REDACT_SHADOW": "1"}, clear=False
        ):
            self.assertFalse(server._redact_enforced())


def _decision(sanitized_segments, decision="redact"):
    return SimpleNamespace(decision=decision, sanitized_segments=list(sanitized_segments))


class SanitizedForwardTests(unittest.TestCase):
    def test_mixed_system_and_user_split_preserved(self):
        from core.subscription_proxy import server

        part_counts = [("system", 2), ("user", 2)]
        sanitized = [
            f"{_PUB_SYS} ",
            "[REDACTED_EMAIL]",
            f"{_PUB_USER} ",
            "[REDACTED_EMAIL]",
        ]
        fwd_system, fwd_prompt = server._sanitized_forward_payload(
            _decision(sanitized),
            part_counts,
            system_prompt=f"{_PUB_SYS} {_PRIV}",
            prompt=f"{_PUB_USER} {_PRIV}",
        )

        self.assertIn(_PUB_SYS, fwd_system)
        self.assertIn(_PUB_USER, fwd_prompt)
        self.assertNotIn(_PUB_USER, fwd_system)
        self.assertNotIn(_PUB_SYS, fwd_prompt)
        self.assertNotIn(_PRIV, fwd_system)
        self.assertNotIn(_PRIV, fwd_prompt)

    def test_count_mismatch_fails_closed(self):
        from core.subscription_proxy import server

        result = server._sanitized_forward_payload(
            _decision(["a", "b"]),
            [("system", 1), ("user", 2)],
            system_prompt="s",
            prompt="p",
        )
        self.assertIsNone(result)

    def test_legacy_path_sanitizes_prompt_keeps_system(self):
        from core.subscription_proxy import server

        fwd_system, fwd_prompt = server._sanitized_forward_payload(
            _decision(["[REDACTED_EMAIL] tail"]),
            [("legacy_prompt", 1)],
            system_prompt="orig-system",
            prompt=f"{_PRIV} tail",
        )
        self.assertEqual(fwd_system, "orig-system")
        self.assertNotIn(_PRIV, fwd_prompt)


class _CapturingAdapter:
    name = "redact-enforce-canary"

    def __init__(self):
        self.prompts = []
        self.systems = []

    def handles_model(self, model):
        return model == "redact-enforce-model"

    def health(self):
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt)
        self.systems.append(system_prompt)
        return CallResult(reply="ok", model_used=model, input_toks=1, output_toks=1)


def _wire_span(text, origin_class, *, redaction_allowed):
    return {
        "text": text,
        "origin_class": origin_class,
        "source_ref": "raw:redact-test",
        "redaction_allowed": redaction_allowed,
    }


def _mixed_body():
    system_text = f"{_PUB_SYS} {_PRIV}"
    user_text = f"{_PUB_USER} {_PRIV}"
    return {
        "model": "redact-enforce-model",
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "maez_egress_segments": {
            "destination": "subscription_proxy:redact-enforce-canary",
            "parts": {
                "system": [
                    _wire_span(f"{_PUB_SYS} ", "public_fact", redaction_allowed=False),
                    _wire_span(
                        _PRIV,
                        "third_party_private_context",
                        redaction_allowed=True,
                    ),
                ],
                "user": [
                    _wire_span(f"{_PUB_USER} ", "public_fact", redaction_allowed=False),
                    _wire_span(
                        _PRIV,
                        "third_party_private_context",
                        redaction_allowed=True,
                    ),
                ],
            },
        },
    }


class _ProxyBase(unittest.IsolatedAsyncioTestCase):
    SHADOW = "1"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "redact-enforce-test",
                "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
                "MAEZ_IPHONE_INGEST_TOKEN": "dummy",
                "MAEZ_EGRESS_REDACT_SHADOW": self.SHADOW,
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

    def _make_request(self, body):
        raw = json.dumps(body).encode("utf-8")

        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": [(b"x-maez-caller", b"redact-enforce-canary")],
            },
            receive,
        )

    def _row(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            return con.execute(
                "SELECT egress_decision, egress_shadow_mode FROM calls"
            ).fetchone()


class EnforceOnTests(_ProxyBase):
    SHADOW = "0"

    async def test_redact_forwards_sanitized_split_shadow0(self):
        await self.server.chat_completions(self._make_request(_mixed_body()))
        sys_fwd, prompt_fwd = self.adapter.systems[0], self.adapter.prompts[0]
        self.assertNotIn(_PRIV, sys_fwd)
        self.assertNotIn(_PRIV, prompt_fwd)
        self.assertIn(_PUB_SYS, sys_fwd)
        self.assertIn(_PUB_USER, prompt_fwd)
        self.assertNotIn(_PUB_USER, sys_fwd)
        self.assertNotIn(_PUB_SYS, prompt_fwd)
        decision, shadow = self._row()
        self.assertEqual(decision, "redact")
        self.assertEqual(shadow, 0)

    async def test_reconstruction_failure_blocks_never_forwards_original(self):
        with mock.patch.object(
            self.server, "_sanitized_forward_payload", return_value=None
        ):
            with self.assertRaises(HTTPException) as ctx:
                await self.server.chat_completions(self._make_request(_mixed_body()))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])
        decision, shadow = self._row()
        self.assertEqual(decision, "redact")
        self.assertEqual(shadow, 0)


class ShadowKillSwitchTests(_ProxyBase):
    SHADOW = "1"

    async def test_redact_forwards_original_shadow1(self):
        await self.server.chat_completions(self._make_request(_mixed_body()))
        self.assertIn(_PRIV, self.adapter.prompts[0])
        decision, shadow = self._row()
        self.assertEqual(decision, "redact")
        self.assertEqual(shadow, 1)


class SurveyTests(unittest.TestCase):
    def test_survey_is_content_free_and_structured(self):
        from scripts.redact_enforcement_survey import survey

        out = survey(db_path=None)
        blob = json.dumps(out)
        for fragment in ("owner@x.test", "sk-aaaa1111", "secret.txt", "555-0101"):
            self.assertNotIn(fragment, blob)
        self.assertIn(out["provisional_verdict"], ("CLEAN", "NO_GO"))
        self.assertIn("masking_ratio", out["prose"])
        self.assertIn("near_empty", out["prose"])

    def test_prose_masks_lightly(self):
        from scripts.redact_enforcement_survey import survey

        out = survey(db_path=None)
        self.assertLessEqual(out["prose"]["masking_ratio"], 0.25, out["prose"])
        self.assertFalse(out["prose"]["near_empty"])


if __name__ == "__main__":
    unittest.main()
