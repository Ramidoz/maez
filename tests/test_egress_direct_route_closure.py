from __future__ import annotations

import os
import unittest
from unittest import mock


class DirectClaudeRouterClosureTests(unittest.TestCase):
    def test_call_claude_routes_through_subscription_proxy_with_provenance(self):
        from core.claude_tier import TierReply
        from core.egress.provenance import ProvenancedText
        from skills import claude_router

        fake = TierReply(
            reply="proxy reply",
            model_used="claude-sonnet-4-6",
            input_tokens=11,
            output_tokens=7,
            raw={},
        )

        with mock.patch.object(
            claude_router,
            "_get_client",
            side_effect=AssertionError("direct Anthropic client bypassed proxy"),
            create=True,
        ), mock.patch(
            "core.routing.claude_tier.call_messages",
            return_value=fake,
        ) as m_call:
            result = claude_router.call_claude(
                system="Public system instruction.",
                messages=[
                    {"role": "user", "content": "Explain a public Python error."}
                ],
                tier="sonnet",
            )

        self.assertEqual(result["content"], "proxy reply")
        self.assertEqual(result["model"], "claude-sonnet-4-6")
        self.assertEqual(
            result["usage"],
            {"input_tokens": 11, "output_tokens": 7},
        )
        kwargs = m_call.call_args.kwargs
        self.assertEqual(kwargs["model"], "sonnet")
        self.assertEqual(kwargs["caller"], "claude_router/call_claude")
        self.assertIsInstance(kwargs["system_prompt"], ProvenancedText)
        self.assertEqual(len(kwargs["messages"]), 1)
        self.assertIsInstance(kwargs["messages"][0].content, ProvenancedText)
        self.assertEqual(
            kwargs["system_prompt"].spans[0].origin_class,
            "system_bounded_query",
        )
        self.assertEqual(
            kwargs["messages"][0].content.spans[0].origin_class,
            "unclassified",
        )


class FastBackendCloudClosureTests(unittest.TestCase):
    def test_cloud_backend_routes_through_proxy_without_provider_api_key(self):
        from core.claude_tier import TierReply
        from core.egress.provenance import ProvenancedText
        from core.routing import fast_backend_cloud

        fake = TierReply(
            reply="fast proxy reply",
            model_used="claude-haiku-4-5-20251001",
            input_tokens=5,
            output_tokens=3,
            raw={},
        )
        env = {
            fast_backend_cloud.ENV_ENABLED: "1",
            fast_backend_cloud.ENV_PROVIDER: fast_backend_cloud.PROVIDER_ANTHROPIC,
        }
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""},
            clear=False,
        ), mock.patch(
            "core.routing.claude_tier.is_online",
            return_value=True,
        ), mock.patch(
            "core.routing.claude_tier.call",
            return_value=fake,
        ) as m_call:
            backend = fast_backend_cloud.CloudBackend()
            self.assertTrue(backend.is_available())
            result = backend.generate("Public fast-lane prompt", timeout_s=2.0)

        self.assertTrue(result.success)
        self.assertEqual(result.text, "fast proxy reply")
        self.assertEqual(result.raw_status, 200)
        kwargs = m_call.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(kwargs["caller"], "fast_backend_cloud/generate")
        self.assertIsInstance(kwargs["prompt"], ProvenancedText)
        self.assertEqual(
            kwargs["prompt"].spans[0].origin_class,
            "owner_message_context",
        )


if __name__ == "__main__":
    unittest.main()
