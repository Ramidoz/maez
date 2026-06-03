# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 1 of the Personal Data Limb Runtime: the egress firewall.

Personal-account-derived data (origin_class="owner_account_context") must block
cloud_model_inference by default — categorically, regardless of redaction_allowed.
This is the lock installed before any ingestion tags data with this class.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.egress.gate import (  # noqa: E402
    EgressRequest,
    EgressSegment,
    decide_egress,
    decision_to_telemetry,
)

_KEY = b"k" * 32


def _cloud_request(segments: list[EgressSegment], request_id: str = "r") -> EgressRequest:
    return EgressRequest(
        call_class="cloud_model_inference",
        destination="openai",
        segments=segments,
        caller="test_owner_account_firewall",
        request_id=request_id,
    )


class OwnerAccountEgressFirewallTests(unittest.TestCase):
    def test_owner_account_blocks_cloud_even_when_redaction_allowed(self):
        # redaction_allowed=True must NOT downgrade an owner-account block.
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text="a saved reddit post that reveals something personal",
                        origin_class="owner_account_context",
                        source_ref="owner_account.reddit.saved:abc123",
                        redaction_allowed=True,
                    )
                ],
                request_id="r1",
            )
        )
        self.assertEqual(decision.decision, "block")
        self.assertIn("owner_account_context_blocked_default", decision.reason_codes)
        self.assertEqual(decision.sanitized_segments, [])

    def test_mixed_public_and_owner_account_blocks_whole_request(self):
        # A public segment alongside an owner-account segment must BLOCK the whole
        # request — never "redact the private part and send the rest".
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text="today's weather is sunny",
                        origin_class="public_fact",
                        source_ref="weather",
                        redaction_allowed=True,
                    ),
                    EgressSegment(
                        text="my gmail thread with a family member",
                        origin_class="owner_account_context",
                        source_ref="owner_account.gmail.thread:1",
                        redaction_allowed=True,
                    ),
                ],
                request_id="r2",
            )
        )
        self.assertEqual(decision.decision, "block")
        self.assertEqual(decision.sanitized_segments, [])
        self.assertEqual(decision.sanitized_text(), "")

    def test_owner_account_block_telemetry_is_content_free(self):
        secret = "private detail: appointment at 4pm with Dr. Real Name"
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text=secret,
                        origin_class="owner_account_context",
                        source_ref="owner_account.calendar.event:9",
                        redaction_allowed=True,
                    )
                ],
                request_id="r3",
            )
        )
        telemetry = decision_to_telemetry(decision, key=_KEY)
        encoded = json.dumps(telemetry)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("Dr. Real Name", encoded)
        self.assertNotIn("appointment", encoded)
        # the class NAME and the decision/reason are fine (not content)
        self.assertEqual(telemetry["decision"], "block")
        self.assertIn("owner_account_context", telemetry["origin_classes"])
        self.assertIn("owner_account_context_blocked_default", telemetry["reason_codes"])

    def test_existing_minimizable_private_context_still_redacts(self):
        # Regression guard: the new rule must NOT change existing private-context
        # handling. 'memory' is MINIMIZABLE_PRIVATE_CONTEXT — with redaction_allowed
        # it still REDACTS (not blocks).
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text="a lived memory about the owner",
                        origin_class="memory",
                        source_ref="lived:1",
                        redaction_allowed=True,
                    )
                ],
                request_id="r4",
            )
        )
        self.assertEqual(decision.decision, "redact")
        self.assertNotIn("owner_account_context_blocked_default", decision.reason_codes)


if __name__ == "__main__":
    unittest.main()
