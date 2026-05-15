"""Calendar v1 connector-policy contract.

This is offline by design: no OAuth, no Google client, no live Calendar data.
It pins the policy surface that the future connector must obey before any
provider payload can reach the noncanonical store.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class CalendarV1ConnectorPolicyTests(unittest.TestCase):
    def test_default_scope_is_owned_events_readonly_and_calendar_readonly_rejects(self):
        from core.information_limb.calendar_connector_policy import (
            DEFAULT_GOOGLE_SCOPE,
            CalendarPolicyError,
            validate_requested_scope,
        )

        self.assertEqual(
            DEFAULT_GOOGLE_SCOPE,
            "https://www.googleapis.com/auth/calendar.events.owned.readonly",
        )
        self.assertEqual(validate_requested_scope(DEFAULT_GOOGLE_SCOPE), DEFAULT_GOOGLE_SCOPE)
        with self.assertRaisesRegex(CalendarPolicyError, "calendar.readonly"):
            validate_requested_scope("https://www.googleapis.com/auth/calendar.readonly")

    def test_non_primary_or_non_owned_event_rejects_content_free(self):
        from core.information_limb.calendar_connector_policy import (
            CalendarSelection,
            normalize_provider_event,
        )

        event = {
            "id": "evt_123",
            "updated": "2026-05-15T12:00:00Z",
            "summary": "Coffee with Sarah re: her divorce",
            "start": {"dateTime": "2026-05-16T12:00:00Z"},
            "end": {"dateTime": "2026-05-16T12:30:00Z"},
        }

        shared = normalize_provider_event(
            event,
            selection=CalendarSelection(calendar_id="shared", owned=False),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        self.assertFalse(shared.accepted)
        self.assertEqual(shared.reason, "non_primary_calendar")
        self.assertNotIn("Sarah", json.dumps(shared.to_dict()))

        delegated = normalize_provider_event(
            event,
            selection=CalendarSelection(calendar_id="primary", owned=False),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        self.assertFalse(delegated.accepted)
        self.assertEqual(delegated.reason, "non_owned_event")

    def test_out_of_forward_horizon_rejects_visible_read_model(self):
        from core.information_limb.calendar_connector_policy import (
            CalendarSelection,
            normalize_provider_event,
        )

        result = normalize_provider_event(
            {
                "id": "evt_123",
                "updated": "2026-05-15T12:00:00Z",
                "summary": "Dinner",
                "start": {"dateTime": "2026-06-15T12:00:00Z"},
                "end": {"dateTime": "2026-06-15T13:00:00Z"},
            },
            selection=CalendarSelection(calendar_id="primary", owned=True),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "outside_forward_window")

    def test_description_dropped_and_title_location_redacted(self):
        from core.information_limb.calendar_connector_policy import (
            CalendarSelection,
            normalize_provider_event,
        )

        result = normalize_provider_event(
            {
                "id": "evt_123",
                "updated": "2026-05-15T12:00:00Z",
                "summary": "Coffee with Sarah re: her divorce",
                "location": "Sarah home address",
                "description": "raw body text must be ignored",
                "attendees": [{"email": "sarah@example.test", "displayName": "Sarah"}],
                "start": {"dateTime": "2026-05-16T12:00:00Z"},
                "end": {"dateTime": "2026-05-16T12:30:00Z"},
            },
            selection=CalendarSelection(calendar_id="primary", owned=True),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

        self.assertTrue(result.accepted)
        facts = result.facts
        self.assertEqual(facts["safe_title_token"], "[redacted third-party calendar detail]")
        self.assertEqual(facts["safe_location_token"], "[redacted third-party calendar detail]")
        self.assertEqual(facts["description_present"], True)
        encoded = json.dumps(result.to_dict(), sort_keys=True)
        for forbidden in (
            "Sarah",
            "sarah@example",
            "divorce",
            "raw body",
            "Coffee",
            "home address",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_attendee_handle_is_event_lineage_scoped_hmac_not_people_key(self):
        from core.information_limb.calendar_connector_policy import attendee_audit_handle

        h1 = attendee_audit_handle(
            attendee_identity="sarah@example.test",
            source_instance_id="primary",
            external_event_id="evt_1",
            hmac_key="test-hmac-key",
        )
        h2 = attendee_audit_handle(
            attendee_identity="sarah@example.test",
            source_instance_id="primary",
            external_event_id="evt_2",
            hmac_key="test-hmac-key",
        )

        self.assertNotEqual(h1, h2)
        self.assertTrue(h1.startswith("attendee_hmac:"))
        self.assertNotIn("sarah", h1)
        self.assertNotIn("evt_1", h1)


if __name__ == "__main__":
    unittest.main()
