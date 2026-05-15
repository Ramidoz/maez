"""Calendar v1 content-free health contract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class CalendarV1HealthTests(unittest.TestCase):
    def test_disabled_health_is_content_free(self):
        from core.information_limb.calendar_v1 import build_calendar_health

        health = build_calendar_health(mode="disabled")

        self.assertEqual(health["mode"], "disabled")
        self.assertEqual(health["connector_state"], "disabled")
        self.assertEqual(health["source_kind"], "calendar.event")
        encoded = json.dumps(health, sort_keys=True)
        for forbidden in (
            "title",
            "location",
            "description",
            "attendee",
            "organizer",
            "conference",
            "source_id",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_v1_without_oauth_is_unavailable_not_legacy(self):
        from core.information_limb.calendar_v1 import build_calendar_health

        health = build_calendar_health(mode="v1", auth_ready=False)

        self.assertEqual(health["mode"], "v1")
        self.assertEqual(health["connector_state"], "auth_unavailable")
        self.assertEqual(health["error_class"], "auth_access_expired")
        self.assertEqual(health["event_count"], 0)

    def test_connector_state_override_is_content_free(self):
        from core.information_limb.calendar_v1 import build_calendar_health

        health = build_calendar_health(
            mode="v1",
            connector_state_override="source_unavailable",
            error_class="calendar_store_schema_mismatch",
        )

        self.assertEqual(health["connector_state"], "source_unavailable")
        self.assertEqual(health["error_class"], "calendar_store_schema_mismatch")
        self.assertEqual(health["event_count"], 0)
