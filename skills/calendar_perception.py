"""
calendar_perception.py — Google Calendar awareness for Maez

Fetches Rohit's upcoming events directly from Google Calendar API using
stored OAuth2 credentials. Returns structured context for injection into
Maez's reasoning prompt every N cycles.

Maez uses this to:
- Know what is coming up in the next 8 hours
- Alert Rohit before meetings via Telegram (15min and 5min warnings)
- Reason about whether to interrupt based on schedule
- Understand the shape and weight of Rohit's day
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger("maez")

TOKEN_PATH = '/home/rohit/maez/config/token.json'
CREDS_PATH = '/home/rohit/maez/config/credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

LOOKAHEAD_HOURS = 8
ALERT_MINUTES_BEFORE = [15, 5]


@dataclass
class CalendarEvent:
    title: str
    start_time: datetime
    end_time: datetime
    location: str
    description: str
    event_id: str

    @property
    def minutes_until(self) -> float:
        now = datetime.now(timezone.utc)
        return (self.start_time - now).total_seconds() / 60

    @property
    def is_now(self) -> bool:
        now = datetime.now(timezone.utc)
        return self.start_time <= now <= self.end_time

    def format_for_context(self) -> str:
        mins = self.minutes_until
        if self.is_now:
            timing = "HAPPENING NOW"
        elif mins < 0:
            timing = f"ended {abs(int(mins))}m ago"
        elif mins < 60:
            timing = f"in {int(mins)}m"
        else:
            timing = f"in {mins/60:.1f}h"
        loc = f" @ {self.location}" if self.location else ""
        return f"  - {self.title}{loc} — {timing}"


@dataclass
class CalendarSnapshot:
    events: list = field(default_factory=list)
    current_event: Optional[CalendarEvent] = None
    next_event: Optional[CalendarEvent] = None
    fetched_at: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None

    def format_for_context(self) -> str:
        if not self.success:
            return f"[CALENDAR] Unavailable: {self.error}"
        if not self.events:
            return "[CALENDAR] Nothing scheduled in the next 8 hours."
        lines = ["[CALENDAR]"]
        if self.current_event:
            lines.append(f"  IN MEETING NOW: {self.current_event.title}")
        upcoming = [e for e in self.events if not e.is_now]
        if upcoming:
            lines.append("  Upcoming:")
            for e in upcoming[:5]:
                lines.append(e.format_for_context())
        return "\n".join(lines)

    def format_for_memory(self) -> str:
        if not self.success or not self.events:
            return "Calendar: nothing scheduled upcoming."
        titles = [e.title for e in self.events[:3]]
        return f"Calendar: {', '.join(titles)} scheduled upcoming."

    def get_alert_events(self, already_alerted: set) -> list:
        """Return (event, threshold_minutes, cache_key) tuples needing alerts."""
        alerts = []
        for event in self.events:
            if event.is_now:
                continue
            mins = event.minutes_until
            for threshold in ALERT_MINUTES_BEFORE:
                key = (event.event_id, threshold)
                if key in already_alerted:
                    continue
                if threshold - 2 <= mins <= threshold + 2:
                    alerts.append((event, threshold, key))
        return alerts


def _get_credentials() -> Optional[Credentials]:
    """Load and refresh OAuth2 credentials."""
    try:
        if not os.path.exists(TOKEN_PATH):
            logger.error("Token not found at %s. Run auth flow first.", TOKEN_PATH)
            return None

        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, 'w') as f:
                    f.write(creds.to_json())
                logger.debug("OAuth token refreshed")
            else:
                logger.error("Credentials invalid and cannot be refreshed")
                return None

        return creds
    except Exception as e:
        logger.error("Credential error: %s", e)
        return None


def _fetch_events(creds: Credentials) -> list:
    """Fetch upcoming events from Google Calendar API."""
    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(hours=LOOKAHEAD_HOURS)).isoformat()

    result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime',
        maxResults=20,
    ).execute()

    raw_events = result.get('items', [])
    events = []

    for item in raw_events:
        try:
            start_raw = item['start'].get('dateTime', item['start'].get('date'))
            end_raw = item['end'].get('dateTime', item['end'].get('date'))

            if 'T' not in start_raw:
                start_dt = datetime.fromisoformat(start_raw).replace(tzinfo=timezone.utc)
                end_dt = datetime.fromisoformat(end_raw).replace(tzinfo=timezone.utc)
            else:
                start_dt = datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_raw.replace('Z', '+00:00'))

            events.append(CalendarEvent(
                title=item.get('summary', 'Untitled'),
                start_time=start_dt,
                end_time=end_dt,
                location=item.get('location', ''),
                description=item.get('description', '')[:200],
                event_id=item.get('id', ''),
            ))
        except Exception as e:
            logger.debug("Skipping malformed event: %s", e)
            continue

    return events


def observe(force_refresh: bool = False) -> CalendarSnapshot:
    """Main entry point. Returns a CalendarSnapshot, never raises."""
    global _cache, _cache_time

    now = time.time()
    if not force_refresh and _cache is not None and (now - _cache_time) < 300:
        return _cache

    try:
        creds = _get_credentials()
        if creds is None:
            snap = CalendarSnapshot(success=False, error="OAuth credentials unavailable")
        else:
            events = _fetch_events(creds)
            current = next((e for e in events if e.is_now), None)
            upcoming = [e for e in events if not e.is_now and e.minutes_until > 0]
            snap = CalendarSnapshot(
                events=events,
                current_event=current,
                next_event=upcoming[0] if upcoming else None,
                success=True,
            )
    except HttpError as e:
        snap = CalendarSnapshot(success=False, error=f"Google API error: {e}")
    except Exception as e:
        snap = CalendarSnapshot(success=False, error=str(e))

    _cache = snap
    _cache_time = now
    return snap


# Module-level cache
_cache: Optional[CalendarSnapshot] = None
_cache_time: float = 0


def test():
    """Quick test."""
    print("Testing calendar perception...")
    snap = observe(force_refresh=True)
    print(f"Success: {snap.success}")
    if snap.error:
        print(f"Error: {snap.error}")
    print(f"Events found: {len(snap.events)}")
    print()
    print(snap.format_for_context())
    if snap.events:
        print()
        for e in snap.events[:5]:
            print(f"  {e.title}: {e.minutes_until:.0f}m away")
    return snap.success


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    ok = test()
    sys.exit(0 if ok else 1)
