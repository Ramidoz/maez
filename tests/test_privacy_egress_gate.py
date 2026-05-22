from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PrivacyEgressGateTests(unittest.TestCase):
    def test_raw_string_payload_blocks_as_unclassified(self):
        from core.egress.gate import decide_egress

        decision = decide_egress("raw prompt")

        self.assertEqual(decision.decision, "block")
        self.assertIn("unclassified", decision.reason_codes)
        self.assertEqual(decision.sanitized_text(), "")

    def test_source_attached_downgrade_attempt_blocks(self):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress

        req = EgressRequest(
            call_class="cloud_model_inference",
            destination="subscription_proxy:claude",
            caller="test",
            request_id="req-1",
            segments=[
                EgressSegment(
                    text="private memory text",
                    origin_class="system_bounded_query",
                    source_ref="memory:ep-private",
                    redaction_allowed=True,
                    asserted_origin_class="memory",
                )
            ],
        )

        decision = decide_egress(req)

        self.assertEqual(decision.decision, "block")
        self.assertIn("origin_downgrade", decision.reason_codes)

    def test_reserved_denied_raw_blocks_for_cloud_model_inference(self):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress

        req = EgressRequest(
            call_class="cloud_model_inference",
            destination="subscription_proxy:claude",
            caller="test",
            request_id="req-2",
            segments=[
                EgressSegment(
                    text="Maez private diary line",
                    origin_class="private_thoughts",
                    source_ref="private_thoughts:1",
                    redaction_allowed=False,
                )
            ],
        )

        decision = decide_egress(req)

        self.assertEqual(decision.decision, "block")
        self.assertIn("reserved_denied_raw", decision.reason_codes)
        self.assertEqual(decision.sanitized_text(), "")

    def test_minimizable_private_context_redacts_for_cloud_shadow(self):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress

        req = EgressRequest(
            call_class="cloud_model_inference",
            destination="subscription_proxy:claude",
            caller="test",
            request_id="req-3",
            segments=[
                EgressSegment(
                    text="Owner said email rohit@example.com and memory_id_123",
                    origin_class="owner_message_context",
                    source_ref="telegram:ctx",
                    redaction_allowed=True,
                )
            ],
        )

        decision = decide_egress(req)

        self.assertEqual(decision.decision, "redact")
        self.assertIn("minimized_private_context", decision.reason_codes)
        sanitized = decision.sanitized_text()
        self.assertNotIn("rohit@example.com", sanitized)
        self.assertNotIn("memory_id_123", sanitized)

    def test_non_private_system_query_allows_for_cloud(self):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress

        req = EgressRequest(
            call_class="cloud_model_inference",
            destination="subscription_proxy:claude",
            caller="test",
            request_id="req-4",
            segments=[
                EgressSegment(
                    text="Summarize public weather facts.",
                    origin_class="system_bounded_query",
                    source_ref="system:query",
                    redaction_allowed=False,
                )
            ],
        )

        decision = decide_egress(req)

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.sanitized_text(), "Summarize public weather facts.")

    def test_telemetry_never_records_raw_bonded_payload_or_bare_hash(self):
        from core.egress.gate import (
            EgressRequest,
            EgressSegment,
            decide_egress,
            decision_to_telemetry,
        )

        secret = "tiny private line"
        req = EgressRequest(
            call_class="cloud_model_inference",
            destination="subscription_proxy:claude",
            caller="test",
            request_id="req-5",
            segments=[
                EgressSegment(
                    text=secret,
                    origin_class="memory",
                    source_ref="memory:ep-secret",
                    redaction_allowed=True,
                )
            ],
        )

        decision = decide_egress(req)
        telemetry = decision_to_telemetry(decision, key=b"local-test-key")
        bare_sha = hashlib.sha256(secret.encode("utf-8")).hexdigest()

        rendered = repr(telemetry)
        self.assertNotIn(secret, rendered)
        self.assertNotIn(bare_sha, rendered)
        self.assertIn("content_digest", telemetry)
        self.assertEqual(telemetry["decision"], "redact")

    def test_telemetry_key_file_is_local_and_0600_when_env_absent(self):
        from core.egress.gate import load_or_create_telemetry_key

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "egress_telemetry.key"
            with mock.patch.dict(os.environ, {}, clear=True):
                key = load_or_create_telemetry_key(path)

            self.assertEqual(len(key), 32)
            self.assertEqual(path.read_bytes(), key)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
