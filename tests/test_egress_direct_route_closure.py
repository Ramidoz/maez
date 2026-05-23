from __future__ import annotations

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
    def test_cloud_backend_is_retired_tombstone_not_proxy_route(self):
        from core.routing import fast_backend_cloud

        with mock.patch(
            "core.routing.claude_tier.call",
            side_effect=AssertionError("retired fast backend must not call proxy"),
        ) as m_call:
            backend = fast_backend_cloud.CloudBackend()
            with self.assertLogs("core.routing.fast_backend_cloud", level="WARNING"):
                with self.assertRaises(fast_backend_cloud.FastLaneCloudRetiredError):
                    backend.generate("Public fast-lane prompt", timeout_s=2.0)

        self.assertFalse(m_call.called)


if __name__ == "__main__":
    unittest.main()
