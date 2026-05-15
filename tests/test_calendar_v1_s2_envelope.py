"""Calendar v1 canonical S2 envelope contract.

Calendar is the first information limb under Decision 27 / ADR 0032. This
test pins the inheritance boundary: connectors may report provider facts, but
they cannot mint S2 authority fields or invent Calendar-specific envelope
aliases.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _minimal_envelope() -> dict:
    from core.information_limb.calendar_s2_envelope import (
        CANONICAL_S2_REQUIRED_FIELDS,
    )

    envelope = {field: f"value:{field}" for field in CANONICAL_S2_REQUIRED_FIELDS}
    envelope.update(
        {
            "schema_version": "calendar.s2.v1",
            "source_kind": "calendar.event",
            "confidence": "provider_confirmed",
            "facts": {"safe_title_token": "[calendar event]"},
            "granted_flow_ids": ["calendar_direct_answer"],
            "requested_flow_ids": ["calendar_direct_answer"],
            "provenance": {"provider": "google_calendar"},
        }
    )
    return envelope


class CalendarS2EnvelopeTests(unittest.TestCase):
    def test_required_fields_match_calendar_spec_inheritance_ledger(self):
        from core.information_limb.calendar_s2_envelope import (
            CANONICAL_S2_REQUIRED_FIELDS,
        )

        self.assertEqual(len(CANONICAL_S2_REQUIRED_FIELDS), 34)
        self.assertIn("decision2_consent_tier", CANONICAL_S2_REQUIRED_FIELDS)
        self.assertIn("source_handle_telemetry", CANONICAL_S2_REQUIRED_FIELDS)
        self.assertIn("promotion_eligibility_provenance_handle", CANONICAL_S2_REQUIRED_FIELDS)

    def test_missing_canonical_field_rejects_record(self):
        from core.information_limb.calendar_s2_envelope import (
            CalendarS2EnvelopeError,
            validate_calendar_s2_envelope,
        )

        envelope = _minimal_envelope()
        envelope.pop("decision2_consent_tier")

        with self.assertRaisesRegex(CalendarS2EnvelopeError, "missing"):
            validate_calendar_s2_envelope(envelope)

    def test_calendar_specific_aliases_are_rejected(self):
        from core.information_limb.calendar_s2_envelope import (
            CalendarS2EnvelopeError,
            validate_calendar_s2_envelope,
        )

        envelope = _minimal_envelope()
        envelope["consent_tier"] = "tier_3"

        with self.assertRaisesRegex(CalendarS2EnvelopeError, "alias"):
            validate_calendar_s2_envelope(envelope)

    def test_connector_payload_cannot_supply_s2_authority_fields(self):
        from core.information_limb.calendar_s2_envelope import (
            CalendarS2EnvelopeError,
            validate_connector_calendar_payload,
        )

        with self.assertRaisesRegex(CalendarS2EnvelopeError, "connector authority"):
            validate_connector_calendar_payload(
                {
                    "id": "provider-event-id",
                    "updated": "2026-05-15T12:00:00Z",
                    "decision2_consent_tier": "tier_3",
                }
            )
        with self.assertRaisesRegex(CalendarS2EnvelopeError, "connector authority"):
            validate_connector_calendar_payload(
                {
                    "id": "provider-event-id",
                    "updated": "2026-05-15T12:00:00Z",
                    "granted_flow_ids": ["calendar_direct_answer"],
                }
            )

    def test_valid_minimal_calendar_s2_envelope_is_accepted_content_free(self):
        from core.information_limb.calendar_s2_envelope import (
            validate_calendar_s2_envelope,
        )

        accepted = validate_calendar_s2_envelope(_minimal_envelope())

        self.assertIs(accepted, True)


if __name__ == "__main__":
    unittest.main()
