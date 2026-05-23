from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
WEB_INTERFACE_SRC = ROOT / "skills" / "web_interface.py"
CLAUDE_ROUTER_SRC = ROOT / "skills" / "claude_router.py"


def _make_response(body: dict):
    raw = json.dumps(body).encode("utf-8")
    resp = mock.MagicMock()
    resp.status = 200
    resp.read.return_value = raw
    resp.__enter__ = mock.MagicMock(return_value=resp)
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


class ClaudeTierMultiPartTests(unittest.TestCase):
    def test_call_messages_carries_role_aware_provenance_without_collapse(self):
        from core.egress.provenance import ProvenancedText
        from core.routing import claude_tier

        response = _make_response({
            "choices": [{"message": {"content": "ok"}, "index": 0}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            "model": "sonnet",
        })
        captured: dict = {}

        def _capture(req, timeout):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return response

        messages = [
            claude_tier.CloudMessage(
                role="assistant",
                content=ProvenancedText.model_output(
                    "prior external reasoning",
                    source_ref="test:assistant_history",
                ),
            ),
            claude_tier.CloudMessage(
                role="user",
                content=ProvenancedText.public_fact(
                    "public question",
                    source_ref="test:public_user",
                ),
            ),
        ]
        with mock.patch("urllib.request.urlopen", side_effect=_capture):
            reply = claude_tier.call_messages(
                system_prompt=ProvenancedText.system_bounded_query(
                    "Task only.", source_ref="test:system"
                ),
                messages=messages,
                caller="test/multipart",
            )

        self.assertEqual(reply.reply, "ok")
        body = captured["body"]
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "assistant", "user"])
        parts = body["maez_egress_segments"]["parts"]
        self.assertIn("system", parts)
        self.assertIn("assistant_history", parts)
        self.assertIn("user", parts)
        self.assertEqual(parts["assistant_history"][-1]["origin_class"], "model_output")
        self.assertEqual(parts["user"][0]["origin_class"], "public_fact")
        self.assertNotEqual(
            "".join(span["text"] for span in parts["assistant_history"]),
            "".join(span["text"] for span in parts["user"]),
        )

    def test_legacy_call_shape_still_works(self):
        from core.routing import claude_tier

        response = _make_response({
            "choices": [{"message": {"content": "legacy ok"}, "index": 0}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            "model": "sonnet",
        })
        with mock.patch("urllib.request.urlopen", return_value=response):
            reply = claude_tier.call(prompt="legacy prompt", caller="legacy")

        self.assertEqual(reply.reply, "legacy ok")


class ClaudeRouterProvenanceTests(unittest.TestCase):
    def test_call_claude_preserves_supplied_provenance_parts(self):
        from core.claude_tier import TierReply
        from core.egress.provenance import ProvenancedText
        from skills import claude_router

        fake = TierReply("cloud text", "claude-sonnet-4-6", 4, 5, {})
        with mock.patch(
            "core.routing.claude_tier.call_messages",
            return_value=fake,
        ) as m_call:
            result = claude_router.call_claude(
                system=ProvenancedText.system_bounded_query(
                    "Task only.", source_ref="test:system"
                ),
                messages=[
                    {
                        "role": "user",
                        "content": ProvenancedText.public_fact(
                            "public premise", source_ref="test:public"
                        ),
                    },
                    {
                        "role": "user",
                        "content": ProvenancedText.memory(
                            "owner memory", source_ref="test:memory"
                        ),
                    },
                ],
                tier="sonnet",
            )

        self.assertEqual(result["content"], "cloud text")
        kwargs = m_call.call_args.kwargs
        self.assertEqual(kwargs["caller"], "claude_router/call_claude")
        sent = kwargs["messages"]
        self.assertEqual([m.content.spans[0].origin_class for m in sent], ["public_fact", "memory"])

    def test_public_task_shaped_router_call_can_allow(self):
        from core.egress.gate import EgressRequest, decide_egress
        from core.egress.provenance import ProvenancedText
        from core.routing.claude_tier import CloudMessage

        system = ProvenancedText.system_bounded_query(
            "Answer the task. Do not assume identity.",
            source_ref="test:task_system",
        )
        messages = [
            CloudMessage(
                role="user",
                content=ProvenancedText.public_fact(
                    "What is Python?", source_ref="test:public_fact"
                ),
            )
        ]
        segments = system.to_egress_segments()
        for msg in messages:
            segments.extend(msg.content.to_egress_segments())

        decision = decide_egress(
            EgressRequest(
                call_class="cloud_model_inference",
                destination="subscription_proxy:claude",
                caller="claude_router/call_claude",
                request_id="allow-public",
                segments=segments,
            )
        )

        self.assertEqual(decision.decision, "allow")
        self.assertIn("non_private_allowed", decision.reason_codes)

    def test_memory_and_lived_recall_router_spans_stay_minimizable(self):
        from core.egress.gate import EgressRequest, decide_egress
        from core.egress.provenance import ProvenancedText

        memory = ProvenancedText.memory("Owner memory", source_ref="memory:owner")
        lived = ProvenancedText.lived_store("Lived recall", source_ref="lived:ep")
        decision = decide_egress(
            EgressRequest(
                call_class="cloud_model_inference",
                destination="subscription_proxy:claude",
                caller="claude_router/call_claude",
                request_id="redact-private",
                segments=memory.to_egress_segments() + lived.to_egress_segments(),
            )
        )

        self.assertEqual(decision.decision, "redact")
        self.assertIn("minimized_private_context", decision.reason_codes)

    def test_raw_soul_in_cloud_system_prompt_blocks_as_a2_regression(self):
        from core.egress.gate import EgressRequest, decide_egress
        from core.egress.provenance import ProvenancedText

        system = ProvenancedText.reserved_raw(
            "raw soul material",
            origin_class="soul",
            source_ref="test:raw_soul",
        )
        user = ProvenancedText.public_fact(
            "public question",
            source_ref="test:public",
        )
        decision = decide_egress(
            EgressRequest(
                call_class="cloud_model_inference",
                destination="subscription_proxy:claude",
                caller="claude_router/call_claude",
                request_id="raw-soul-regression",
                segments=system.to_egress_segments() + user.to_egress_segments(),
            )
        )

        self.assertEqual(decision.decision, "block")
        self.assertIn("reserved_denied_raw", decision.reason_codes)

    def test_raw_strings_stay_legacy_conservative_not_public_by_content(self):
        from core.claude_tier import TierReply
        from skills import claude_router

        fake = TierReply("cloud text", "claude-sonnet-4-6", 1, 1, {})
        with mock.patch(
            "core.routing.claude_tier.call_messages",
            return_value=fake,
        ) as m_call:
            claude_router.call_claude(
                system="Task only.",
                messages=[{"role": "user", "content": "https://example.com public-looking"}],
                tier="sonnet",
            )

        sent = m_call.call_args.kwargs["messages"]
        self.assertEqual(sent[0].content.spans[0].origin_class, "unclassified")

    def test_aggregate_collapse_regression(self):
        from core.claude_tier import TierReply
        from core.egress.provenance import ProvenancedText
        from skills import claude_router

        fake = TierReply("cloud text", "claude-sonnet-4-6", 1, 1, {})
        with mock.patch(
            "core.routing.claude_tier.call_messages",
            return_value=fake,
        ) as m_call:
            claude_router.call_claude(
                system=ProvenancedText.system_bounded_query(
                    "Task.", source_ref="system:test"
                ),
                messages=[
                    {"role": "user", "content": ProvenancedText.public_fact("A", source_ref="p")},
                    {"role": "assistant", "content": ProvenancedText.model_output("B", source_ref="m")},
                    {"role": "user", "content": ProvenancedText.memory("C", source_ref="mem")},
                ],
                tier="sonnet",
            )

        sent = m_call.call_args.kwargs["messages"]
        self.assertEqual(len(sent), 3)
        self.assertEqual([m.content.text for m in sent], ["A", "B", "C"])

    def test_no_wrap_maez_voice_shell_remains(self):
        src = CLAUDE_ROUTER_SRC.read_text(encoding="utf-8")
        self.assertNotIn("def wrap_maez_voice", src)


class WebInterfaceCloudAsToolTests(unittest.TestCase):
    def _source(self) -> str:
        return WEB_INTERFACE_SRC.read_text(encoding="utf-8")

    def test_web_interface_has_provenance_payload_builder_at_insertion_points(self):
        src = self._source()
        self.assertIn("build_claude_router_cloud_payload", src)
        self.assertIn("ProvenancedText.memory", src)
        self.assertIn("ProvenancedText.lived_store", src)
        self.assertIn("ProvenancedText.owner_message_context", src)

    def test_raw_soul_is_not_used_in_cloud_system_prompt_or_reply_persistence(self):
        src = self._source()
        external_start = src.index("if route_external:")
        external_end = src.index("# 2026-04-23 memory-integrity contract", external_start)
        external_block = src[external_start:external_end]
        self.assertNotIn("SOUL", external_block)
        self.assertNotIn("wrap_maez_voice", external_block)
        self.assertNotIn("model_id=used_source", src)
        self.assertIn("model_id=MODEL", src)

    def test_structured_envelope_and_raw_history_stay_conservative(self):
        src = self._source()
        self.assertIn("classify_envelope_for_cloud_provenance", src)
        self.assertIn("history stays conservative", src)
        self.assertNotIn("render_envelope_for_prompt(_evidence_envelope)).system_bounded_query", src)

    def test_cloud_output_enters_local_context_as_model_output(self):
        src = self._source()
        self.assertIn("ProvenancedText.model_output", src)
        self.assertIn("cloud_consult", src)
        self.assertIn("local Maez runtime path", src)

    def test_cloud_failure_keeps_local_reply_path_always_running(self):
        src = self._source()
        external_start = src.index("if route_external:")
        local_start = src.index("try:\n        # Local path", external_start)
        external_block = src[external_start:local_start]
        self.assertIn("cloud_optional", external_block)
        self.assertNotIn("falling back local", external_block)


class ProxyTelemetryHygieneRegression(unittest.TestCase):
    def test_proxy_span_bundle_telemetry_remains_keyed_and_non_raw_for_model_output(self):
        from core.egress.gate import (
            EgressRequest,
            EgressSegment,
            decide_egress,
            decision_to_telemetry,
        )

        canary = "SYNTH_MODEL_OUTPUT_CANARY_R42"
        decision = decide_egress(
            EgressRequest(
                call_class="cloud_model_inference",
                destination="subscription_proxy:claude",
                caller="claude_router/call_claude",
                request_id="telemetry-model-output",
                segments=[
                    EgressSegment(
                        text=canary,
                        origin_class="model_output",
                        source_ref="claude_router:cloud_consult",
                        redaction_allowed=True,
                    )
                ],
            )
        )
        telemetry = decision_to_telemetry(decision, key=b"test-key")
        rendered = json.dumps(telemetry, sort_keys=True)

        self.assertNotIn(canary, rendered)
        self.assertTrue(telemetry["content_digest"].startswith("hmac-sha256:"))


if __name__ == "__main__":
    unittest.main()
