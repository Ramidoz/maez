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
        with self.assertRaisesRegex(CalendarPolicyError, "fallback"):
            validate_requested_scope("https://www.googleapis.com/auth/calendar.events.readonly")
        self.assertEqual(
            validate_requested_scope(
                "https://www.googleapis.com/auth/calendar.events.readonly",
                allow_fallback=True,
            ),
            "https://www.googleapis.com/auth/calendar.events.readonly",
        )
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
            "organizer": {"self": True},
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
                "organizer": {"self": True},
                "start": {"dateTime": "2026-06-15T12:00:00Z"},
                "end": {"dateTime": "2026-06-15T13:00:00Z"},
            },
            selection=CalendarSelection(calendar_id="primary", owned=True),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "outside_forward_window")

    def test_ongoing_event_overlapping_forward_window_is_accepted(self):
        from core.information_limb.calendar_connector_policy import (
            CalendarSelection,
            normalize_provider_event,
        )

        result = normalize_provider_event(
            {
                "id": "evt_123",
                "updated": "2026-05-15T12:00:00Z",
                "summary": "Lunch",
                "organizer": {"self": True},
                "start": {"dateTime": "2026-05-15T11:30:00Z"},
                "end": {"dateTime": "2026-05-15T12:30:00Z"},
            },
            selection=CalendarSelection(calendar_id="primary", owned=True),
            now=datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(result.accepted)

    def test_provider_ownership_evidence_required(self):
        from core.information_limb.calendar_connector_policy import (
            CalendarSelection,
            normalize_provider_event,
        )

        result = normalize_provider_event(
            {
                "id": "evt_123",
                "updated": "2026-05-15T12:00:00Z",
                "summary": "Lunch",
                "organizer": {"self": False},
                "creator": {"self": False},
                "start": {"dateTime": "2026-05-16T12:00:00Z"},
                "end": {"dateTime": "2026-05-16T12:30:00Z"},
            },
            selection=CalendarSelection(calendar_id="primary", owned=True),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "non_owned_event")

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
                "organizer": {"self": True},
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
        self.assertNotIn("description_present", facts)
        encoded = json.dumps(result.to_dict(), sort_keys=True)
        for forbidden in (
            "Sarah",
            "sarah@example",
            "divorce",
            "raw body",
            "Coffee",
            "home address",
            "description",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_attendee_handle_is_event_lineage_scoped_hmac_not_people_key(self):
        from core.information_limb.calendar_connector_policy import attendee_audit_handle

        h1 = attendee_audit_handle(
            attendee_identity="sarah@example.test",
            source_instance_id="primary",
            external_event_id="evt_1",
            purpose="audit_continuity",
            hmac_key="test-hmac-key",
        )
        h2 = attendee_audit_handle(
            attendee_identity="sarah@example.test",
            source_instance_id="primary",
            external_event_id="evt_2",
            purpose="audit_continuity",
            hmac_key="test-hmac-key",
        )

        self.assertNotEqual(h1, h2)
        self.assertTrue(h1.startswith("attendee_hmac:"))
        self.assertNotIn("sarah", h1)
        self.assertNotIn("evt_1", h1)

    def test_attendee_handle_requires_purpose_and_strong_key(self):
        from core.information_limb.calendar_connector_policy import (
            CalendarPolicyError,
            attendee_audit_handle,
        )

        with self.assertRaisesRegex(CalendarPolicyError, "purpose"):
            attendee_audit_handle(
                attendee_identity="sarah@example.test",
                source_instance_id="primary",
                external_event_id="evt_1",
                purpose="",
                hmac_key="test-hmac-key",
            )
        with self.assertRaisesRegex(CalendarPolicyError, "hmac"):
            attendee_audit_handle(
                attendee_identity="sarah@example.test",
                source_instance_id="primary",
                external_event_id="evt_1",
                purpose="audit_continuity",
                hmac_key="",
            )


if __name__ == "__main__":
    unittest.main()
