"""Calendar v1 Google sync request construction.

Offline request builders only. These tests pin the request-shape constraints
from Decision 28 before any Google client or OAuth flow is introduced.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class CalendarV1SyncRequestTests(unittest.TestCase):
    def test_initial_request_uses_primary_owned_scope_shape_without_description_field(self):
        from core.information_limb.calendar_sync_requests import build_initial_events_request

        now = datetime(2026, 5, 15, tzinfo=timezone.utc)
        request = build_initial_events_request(
            calendar_id="primary",
            now=now,
        )

        self.assertEqual(request["calendarId"], "primary")
        self.assertEqual(request["singleEvents"], True)
        self.assertEqual(request["orderBy"], "startTime")
        self.assertEqual(request["showDeleted"], True)
        self.assertEqual(request["timeMin"], "2026-05-15T00:00:00Z")
        self.assertEqual(request["timeMax"], "2026-05-29T00:00:00Z")
        fields = request["fields"]
        self.assertIn("items(id,updated,status,summary,location,start,end,attendees", fields)
        self.assertNotIn("description", fields)
        self.assertNotIn("conferenceData", fields)
        self.assertNotIn("attachments", fields)

    def test_incremental_request_never_combines_sync_token_with_query_filters(self):
        from core.information_limb.calendar_sync_requests import build_incremental_events_request

        request = build_incremental_events_request(calendar_id="primary", sync_token="sync_123")

        self.assertEqual(request["calendarId"], "primary")
        self.assertEqual(request["syncToken"], "sync_123")
        self.assertEqual(request["singleEvents"], True)
        self.assertEqual(request["showDeleted"], True)
        forbidden = {
            "timeMin",
            "timeMax",
            "orderBy",
            "q",
            "iCalUID",
            "privateExtendedProperty",
            "sharedExtendedProperty",
            "updatedMin",
        }
        self.assertTrue(forbidden.isdisjoint(request))

    def test_sync_token_is_required_and_content_free(self):
        from core.information_limb.calendar_sync_requests import (
            CalendarSyncRequestError,
            build_incremental_events_request,
        )

        with self.assertRaisesRegex(CalendarSyncRequestError, "sync token"):
            build_incremental_events_request(calendar_id="primary", sync_token="")


if __name__ == "__main__":
    unittest.main()
