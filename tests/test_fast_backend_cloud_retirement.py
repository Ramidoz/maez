from __future__ import annotations

import ast
import importlib
import json
import logging
import os
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib import request


ROOT = Path(__file__).resolve().parent.parent


class _StubBackend:
    def __init__(self, *, name: str, available: bool = True, result=None):
        self.name = name
        self._available = available
        self._result = result

    def is_available(self):
        return self._available

    def generate(self, prompt, *, max_tokens=256, temperature=0.4, timeout_s=30.0):
        if self._result is not None:
            return self._result
        from core.routing.fast_backend_local import BackendResult

        return BackendResult(
            success=True,
            text="local visible reply",
            backend_name=self.name,
            model_call_ms=1,
        )


@dataclass
class _Prompt:
    text: str
    truncated: bool = False
    used_perception_sources: list[str] | None = None
    skipped_perception_sources: list[str] | None = None

    @property
    def char_count(self) -> int:
        return len(self.text)

    def __post_init__(self):
        self.used_perception_sources = self.used_perception_sources or []
        self.skipped_perception_sources = self.skipped_perception_sources or []


def _envelope():
    source = SimpleNamespace(age_ms=0, freshness_state="fresh")
    return SimpleNamespace(
        screen=source,
        system_state=source,
        calendar=source,
        sources=set(),
    )


class FastBackendRetirementRouterTests(unittest.TestCase):
    def test_cloud_policy_is_retired_for_prior_cloud_eligible_scopes(self):
        from core.routing import fast_backend_router as router

        for scope in ("owner.draft", "rohit.draft", "unmapped_scope"):
            with self.subTest(scope=scope):
                decision = router.decide_policy(scope, router.POLICY_CLOUD)
                self.assertEqual(decision.requested_policy, router.POLICY_CLOUD)
                self.assertEqual(decision.effective_policy, router.POLICY_LOCAL)
                self.assertFalse(decision.allow_cloud)
                self.assertTrue(decision.downgraded)
                self.assertIn("fast_lane_cloud_retired", " ".join(decision.reasons))

    def test_cloud_request_routes_local_without_checking_cloud_availability(self):
        from core.routing import fast_backend_router as router

        local = _StubBackend(name="local-retired")
        with mock.patch.object(router, "_local", return_value=local), mock.patch(
            "core.routing.fast_backend_cloud.CloudBackend.is_available",
            side_effect=AssertionError("fast-lane must not check cloud availability"),
        ):
            result, selection, decision = router.generate(
                "identity:\n  You are Maez\n\ncurrent_message:\n  hello",
                policy=router.POLICY_CLOUD,
                trust_scope="owner.draft",
            )

        self.assertTrue(result.success)
        self.assertEqual(selection.name, "local-retired")
        self.assertEqual(decision.effective_policy, router.POLICY_LOCAL)
        self.assertIn("fast_lane_cloud_retired", " ".join(decision.reasons))

    def test_auto_local_unavailable_does_not_probe_or_select_cloud(self):
        from core.routing import fast_backend_router as router

        with mock.patch.object(
            router,
            "_local",
            return_value=_StubBackend(name="local-down", available=False),
        ), mock.patch(
            "core.routing.fast_backend_cloud.CloudBackend.is_available",
            side_effect=AssertionError("auto/local-down must not probe cloud"),
        ):
            result, selection, decision = router.generate(
                "identity:\n  You are Maez\n\ncurrent_message:\n  hello",
                policy=router.POLICY_AUTO,
                trust_scope="owner.draft",
            )

        self.assertFalse(result.success)
        self.assertEqual(selection.name, "none")
        self.assertTrue(selection.policy_denied)
        self.assertFalse(decision.allow_cloud)
        self.assertIn("fast_lane_cloud_retired", " ".join(decision.reasons))


class FastReplyRetirementTests(unittest.TestCase):
    def test_empty_reply_retry_degrades_locally_without_cloud_fallback(self):
        from core.routing.fast_backend_local import BackendResult
        from skills import fast_reply_prototype as fast_reply

        first = BackendResult(True, "", "local-empty", 1)
        cloud = BackendResult(True, "CLOUD SHOULD NOT SPEAK", "cloud-retired", 2)

        with mock.patch.object(
            fast_reply,
            "build_envelope",
            return_value=_envelope(),
        ), mock.patch.object(
            fast_reply,
            "build_fast_prompt",
            return_value=_Prompt("identity:\n  You are Maez\n\ncurrent_message:\n  hi"),
        ), mock.patch.object(
            fast_reply.fast_backend_router,
            "generate",
            side_effect=[
                (
                    first,
                    SimpleNamespace(reason="initial local empty"),
                    fast_reply.fast_backend_router.decide_policy("owner.draft", "auto"),
                ),
                (
                    cloud,
                    SimpleNamespace(reason="cloud retry"),
                    fast_reply.fast_backend_router.decide_policy("owner.draft", "cloud"),
                ),
            ],
        ) as m_generate, mock.patch.object(
            fast_reply.fast_backend_local,
            "generate",
            return_value=BackendResult(True, "", "local-empty-retry", 1),
        ):
            result = fast_reply.fast_reply(
                "hi",
                trust_scope="owner.draft",
                backend="auto",
                cache=object(),
            )

        self.assertEqual(m_generate.call_count, 1)
        self.assertEqual(result.reply_text, fast_reply.DEGRADED_REPLY_TEXT)
        self.assertEqual(result.metrics.retry_strategy, "degraded_fallback")
        self.assertNotEqual(result.reply_text, "CLOUD SHOULD NOT SPEAK")

    def test_compact_identity_never_reaches_cloud_for_cloud_or_auto_local_down(self):
        from core.routing.fast_backend_local import BackendResult
        from skills import fast_reply_prototype as fast_reply

        identity_prompt = (
            "identity:\n"
            "  You are Maez, a persistent local AI companion built by the owner.\n\n"
            "current_message:\n  hi"
        )

        def _run(policy: str):
            with mock.patch.object(
                fast_reply,
                "build_envelope",
                return_value=_envelope(),
            ), mock.patch.object(
                fast_reply,
                "build_fast_prompt",
                return_value=_Prompt(identity_prompt),
            ), mock.patch.dict(
                "os.environ",
                {"MAEZ_CLOUD_BACKEND_ENABLED": "1"},
                clear=False,
            ), mock.patch(
                "core.routing.claude_tier.is_online",
                return_value=True,
            ), mock.patch(
                "core.routing.claude_tier.call",
                side_effect=AssertionError("identity-bearing fast prompt reached cloud"),
            ), mock.patch.object(
                fast_reply.fast_backend_local,
                "generate",
                return_value=BackendResult(False, "", "local-down", 1, error="down"),
            ), mock.patch.object(
                fast_reply.fast_backend_router,
                "_local",
                return_value=_StubBackend(name="local-down", available=False),
            ):
                return fast_reply.fast_reply(
                    "hi",
                    trust_scope="owner.draft",
                    backend=policy,
                    cache=object(),
                )

        for policy in ("cloud", "auto"):
            with self.subTest(policy=policy):
                result = _run(policy)
                self.assertFalse(result.success)
                self.assertIn("fast_lane_cloud_retired", " ".join(result.metrics.policy_reasons))

    def test_retirement_reason_code_only_marks_cloud_request_or_suppressed_auto(self):
        from core.routing.fast_backend_local import BackendResult
        from skills import fast_reply_prototype as fast_reply

        prompt = _Prompt("identity:\n  You are Maez\n\ncurrent_message:\n  hi")

        def _run(policy: str, *, local_available: bool = True):
            backend = _StubBackend(
                name="local-ok" if local_available else "local-down",
                available=local_available,
                result=BackendResult(
                    local_available,
                    "visible local reply" if local_available else "",
                    "local-ok" if local_available else "local-down",
                    1,
                    error="" if local_available else "down",
                ),
            )
            with mock.patch.object(
                fast_reply,
                "build_envelope",
                return_value=_envelope(),
            ), mock.patch.object(
                fast_reply,
                "build_fast_prompt",
                return_value=prompt,
            ), mock.patch.object(
                fast_reply.fast_backend_router,
                "_local",
                return_value=backend,
            ):
                return fast_reply.fast_reply(
                    "hi",
                    trust_scope="owner.draft",
                    backend=policy,
                    cache=object(),
                )

        local_result = _run("local")
        self.assertEqual(local_result.metrics.retirement_reason_code, "")

        auto_local_available = _run("auto")
        self.assertEqual(auto_local_available.metrics.retirement_reason_code, "")

        cloud_requested = _run("cloud")
        self.assertEqual(
            cloud_requested.metrics.retirement_reason_code,
            "fast_lane_cloud_retired",
        )

        auto_local_down = _run("auto", local_available=False)
        self.assertEqual(
            auto_local_down.metrics.retirement_reason_code,
            "fast_lane_cloud_retired",
        )


class CloudBackendTombstoneTests(unittest.TestCase):
    def test_cloud_backend_generate_raises_before_any_egress_capable_step(self):
        from core.routing import fast_backend_cloud

        self.assertTrue(fast_backend_cloud.DEPRECATED)
        with mock.patch.object(
            fast_backend_cloud,
            "_enabled",
            side_effect=AssertionError("_enabled must not be consulted before tombstone"),
        ), mock.patch(
            "core.routing.claude_tier.call",
            side_effect=AssertionError("proxy call must not be reachable"),
        ):
            with self.assertLogs("core.routing.fast_backend_cloud", level="WARNING"):
                with self.assertRaises(fast_backend_cloud.FastLaneCloudRetiredError):
                    fast_backend_cloud.CloudBackend().generate(
                        "SECRET_CANARY_FAST_BACKEND_CLOUD_RETIREMENT"
                    )

    def test_tombstone_logs_content_free_local_event(self):
        from core.routing import fast_backend_cloud

        canary = "SECRET_CANARY_FAST_BACKEND_CLOUD_RETIREMENT"
        logger_name = "core.routing.fast_backend_cloud"
        logging.getLogger(logger_name).setLevel(logging.WARNING)
        with self.assertLogs(logger_name, level="WARNING") as captured:
            with self.assertRaises(fast_backend_cloud.FastLaneCloudRetiredError):
                fast_backend_cloud.CloudBackend().generate(canary)

        rendered = "\n".join(captured.output)
        self.assertIn("fast_lane_cloud_retired_refused", rendered)
        self.assertIn("prompt_chars", rendered)
        self.assertNotIn(canary, rendered)

    def test_tombstone_creates_no_fast_backend_proxy_db_rows(self):
        canary = "SECRET_CANARY_FAST_BACKEND_CLOUD_RETIREMENT"
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "subscription_proxy.db"
            with mock.patch.dict(
                os.environ,
                {
                    "MAEZ_SUBSCRIPTION_PROXY_DB": str(db_path),
                    "MAEZ_EGRESS_TELEMETRY_KEY": "test-egress-key",
                },
                clear=False,
            ):
                from core.subscription_proxy import server
                from core.routing import fast_backend_cloud

                importlib.reload(server)
                try:
                    with self.assertLogs(
                        "core.routing.fast_backend_cloud",
                        level="WARNING",
                    ):
                        with self.assertRaises(fast_backend_cloud.FastLaneCloudRetiredError):
                            fast_backend_cloud.CloudBackend().generate(canary)

                    if db_path.exists():
                        with sqlite3.connect(db_path) as con:
                            row = con.execute(
                                "SELECT COUNT(*) FROM calls WHERE caller = ?",
                                ("fast_backend_cloud/generate",),
                            ).fetchone()
                        count = int(row[0]) if row else 0
                    else:
                        count = 0
                    self.assertEqual(count, 0)
                finally:
                    importlib.reload(server)


class FastReplyAuditAndStaticBoundaryTests(unittest.TestCase):
    def test_service_audit_behavior_records_cloud_retirement_without_raw_text(self):
        from core.infra.fast_prompt_builder import BuiltPrompt
        from scripts import fast_reply_service as service
        from skills.fast_reply_prototype import (
            FastReplyMetrics,
            FastReplyResult,
        )

        message_canary = "SECRET_REQUEST_CANARY_FAST_RETIREMENT"
        reply_canary = "SECRET_REPLY_CANARY_FAST_RETIREMENT"
        records: list[dict] = []
        metrics = FastReplyMetrics(
            prompt_chars=123,
            backend_name="local-ok",
            backend_success=True,
            model_call_ms=1,
            total_ms=2,
            policy_rule="maez_cloud_allowed_for_drafting",
            policy_requested="cloud",
            policy_effective="local",
            policy_downgraded=True,
            retirement_reason_code="fast_lane_cloud_retired",
        )
        fake_result = FastReplyResult(
            reply_text=reply_canary,
            success=True,
            metrics=metrics,
            envelope=_envelope(),
            prompt=BuiltPrompt(text="prompt text", char_count=123),
        )
        payload = json.dumps({
            "message": message_canary,
            "trust_scope": "owner.draft",
            "backend": "cloud",
        }).encode("utf-8")

        server = service._make_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        try:
            with mock.patch.object(
                service,
                "_rate_limiter",
                service._RateLimiter(),
            ), mock.patch.object(
                service,
                "get_cache",
                return_value=object(),
            ), mock.patch.object(
                service,
                "get_log",
                return_value=object(),
            ), mock.patch.object(
                service,
                "fast_reply",
                return_value=fake_result,
            ) as m_fast_reply, mock.patch.object(
                service,
                "_audit_append_safe",
                side_effect=records.append,
            ):
                thread.start()
                url = f"http://127.0.0.1:{server.server_port}{service.ENDPOINT}"
                req = request.Request(
                    url,
                    data=payload,
                    headers={"content-type": "application/json"},
                    method="POST",
                )
                with request.urlopen(req, timeout=3) as response:
                    body = json.loads(response.read().decode("utf-8"))
        finally:
            server.server_close()
            thread.join(timeout=3)

        self.assertTrue(body["success"])
        self.assertEqual(body["reply"], reply_canary)
        m_fast_reply.assert_called_once()
        self.assertEqual(m_fast_reply.call_args.kwargs["backend"], "cloud")
        self.assertEqual(len(records), 1)
        row = records[0]
        self.assertEqual(row["event"], "reply")
        self.assertEqual(row["policy_requested"], "cloud")
        self.assertEqual(row["policy_effective"], "local")
        self.assertTrue(row["policy_downgraded"])
        self.assertEqual(
            row["retirement_reason_code"],
            "fast_lane_cloud_retired",
        )
        self.assertNotIn("prompt", row)
        self.assertNotIn("reply", row)
        self.assertNotIn("response_text", row)
        rendered = json.dumps(row, sort_keys=True)
        self.assertNotIn(message_canary, rendered)
        self.assertNotIn(reply_canary, rendered)

    def test_claude_router_cloud_as_tool_path_still_uses_proxy_tier(self):
        from core.claude_tier import TierReply
        from skills import claude_router

        fake = TierReply(
            reply="main-loop cloud evidence",
            model_used="claude-sonnet-4-6",
            input_tokens=4,
            output_tokens=3,
            raw={},
        )
        with mock.patch(
            "core.routing.claude_tier.call_messages",
            return_value=fake,
        ) as m_call:
            result = claude_router.call_claude(
                system="Answer as an external reasoning tool.",
                messages=[
                    {"role": "user", "content": "Summarize a public fact."}
                ],
                tier="sonnet",
            )

        self.assertEqual(result["content"], "main-loop cloud evidence")
        self.assertEqual(m_call.call_args.kwargs["caller"], "claude_router/call_claude")

    def test_backend_call_is_test_only_in_production_call_sites(self):
        for relative in ("scripts/fast_reply_service.py", "scripts/fast_reply_cli.py"):
            path = ROOT / relative
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name != "fast_reply":
                    continue
                keywords = {kw.arg for kw in node.keywords if kw.arg}
                self.assertNotIn("backend_call", keywords, f"{relative} passes backend_call")

        prototype = (ROOT / "skills" / "fast_reply_prototype.py").read_text(encoding="utf-8")
        self.assertIn("test/bench-only", prototype)

    def test_cloud_modules_do_not_import_fast_prompt_identity_builders(self):
        for relative in (
            "core/routing/fast_backend_cloud.py",
            "core/routing/fast_backend_router.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("compact_identity", source)
            self.assertNotIn("COMPACT_IDENTITY", source)
            self.assertNotIn("build_fast_prompt", source)


if __name__ == "__main__":
    unittest.main()
