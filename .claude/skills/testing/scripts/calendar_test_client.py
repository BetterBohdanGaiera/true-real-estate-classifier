# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.0.0",
#   "google-api-python-client>=2.0.0",
#   "google-auth>=2.0.0",
# ]
# ///
"""
Calendar Test Client - Manages [TEST] calendar events for E2E testing.

Creates real Google Calendar events with [TEST] prefix for validation,
tracks created events, and provides cleanup on test completion.

Usage:
    from calendar_test_client import CalendarTestClient, TestCalendarEvent

    client = CalendarTestClient()
    event = client.create_test_event(
        summary="Meeting with John",
        start=datetime.now(),
        end=datetime.now() + timedelta(hours=1),
        timezone="Asia/Makassar",
        attendees=["john@example.com"],
    )
    # ... run tests ...
    client.cleanup_all_test_events()
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

# Setup logging
logger = logging.getLogger(__name__)

# Setup paths for imports - add google-calendar skill to path
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
GOOGLE_CAL_SCRIPTS = SKILLS_BASE / "google-calendar" / "scripts"

if str(GOOGLE_CAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GOOGLE_CAL_SCRIPTS))

from calendar_client import CalendarClient


# =============================================================================
# DATA MODELS
# =============================================================================


class TestCalendarEvent(BaseModel):
    """
    Represents a test calendar event created during testing.

    Attributes:
        id: Google Calendar event ID.
        summary: Event title (includes [TEST] prefix).
        start: Event start time.
        end: Event end time.
        timezone: Event timezone (e.g., "Asia/Makassar").
        attendees: List of attendee email addresses.
        zoom_url: Optional Zoom meeting URL embedded in description.
        description: Optional event description.
        html_link: Google Calendar link to the event.
    """

    id: str
    summary: str
    start: datetime
    end: datetime
    timezone: str
    attendees: list[str] = []
    zoom_url: Optional[str] = None
    description: Optional[str] = None
    html_link: Optional[str] = None


# =============================================================================
# CALENDAR TEST CLIENT
# =============================================================================


class CalendarTestClient:
    """
    Manages test calendar events with [TEST] prefix.

    Key responsibilities:
    - Create events with [TEST] prefix for easy identification
    - Track all created events for cleanup
    - Validate event properties after creation
    - Clean up all [TEST] events after test suite

    Example:
        client = CalendarTestClient()
        event = client.create_test_event(
            summary="Meeting with John",
            start=datetime.now(),
            end=datetime.now() + timedelta(hours=1),
            timezone="Asia/Makassar",
            attendees=["john@example.com"],
        )
        # ... run tests ...
        client.cleanup_all_test_events()
    """

    TEST_PREFIX = "[TEST]"
    BALI_TIMEZONE = "Asia/Makassar"  # UTC+8, no DST

    def __init__(self, account: str = "personal"):
        """
        Initialize CalendarTestClient.

        Args:
            account: Google account name for CalendarClient (default: "personal").
        """
        self.client = CalendarClient(account)
        self.created_events: list[str] = []  # Track event IDs for cleanup
        self.account = account
        logger.info(f"CalendarTestClient initialized with account: {account}")

    def create_test_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        timezone: str = "Asia/Makassar",
        attendees: Optional[list[str]] = None,
        zoom_url: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TestCalendarEvent:
        """
        Create a test event with [TEST] prefix.

        Args:
            summary: Event title (will be prefixed with [TEST]).
            start: Event start time.
            end: Event end time.
            timezone: Event timezone (default: Bali/Makassar, UTC+8).
            attendees: List of attendee email addresses.
            zoom_url: Optional Zoom meeting URL to embed in description.
            description: Optional event description.

        Returns:
            TestCalendarEvent with created event details.

        Raises:
            Exception: If Google Calendar API call fails.

        Example:
            >>> event = client.create_test_event(
            ...     summary="Sales Call",
            ...     start=datetime(2024, 2, 15, 10, 0),
            ...     end=datetime(2024, 2, 15, 11, 0),
            ...     attendees=["prospect@example.com"],
            ...     zoom_url="https://zoom.us/j/123456789",
            ... )
            >>> print(f"Created: {event.summary}")
        """
        test_summary = f"{self.TEST_PREFIX} {summary}"

        # Build description with Zoom link if provided
        full_description = description or ""
        if zoom_url:
            if full_description:
                full_description += f"\n\nJoin Zoom: {zoom_url}"
            else:
                full_description = f"Join Zoom: {zoom_url}"

        try:
            result = self.client.create_event(
                summary=test_summary,
                start=start.isoformat() if isinstance(start, datetime) else start,
                end=end.isoformat() if isinstance(end, datetime) else end,
                description=full_description or None,
                location="Zoom" if zoom_url else None,
                attendees=attendees,
                timezone=timezone,
            )

            self.created_events.append(result["id"])
            logger.info(f"Created test event: {test_summary} (ID: {result['id']})")

            # Parse start time from result
            start_parsed = self._parse_datetime(result["start"])
            end_parsed = self._parse_datetime(result["end"])

            return TestCalendarEvent(
                id=result["id"],
                summary=result["summary"],
                start=start_parsed,
                end=end_parsed,
                timezone=timezone,
                attendees=attendees or [],
                zoom_url=zoom_url,
                description=full_description or None,
                html_link=result.get("html_link"),
            )

        except Exception as e:
            logger.error(f"Failed to create test event '{test_summary}': {e}")
            raise

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """
        Parse datetime string from Google Calendar API response.

        Args:
            datetime_str: ISO format datetime string (may include timezone).

        Returns:
            datetime object (timezone-naive).
        """
        if "T" in datetime_str:
            # Remove timezone info for parsing (handle both Z and +HH:MM formats)
            clean_str = datetime_str.replace("Z", "")
            if "+" in clean_str:
                clean_str = clean_str.split("+")[0]
            elif clean_str.count("-") > 2:
                # Handle negative timezone offset like -08:00
                parts = clean_str.rsplit("-", 1)
                if ":" in parts[-1]:
                    clean_str = parts[0]
            return datetime.fromisoformat(clean_str)
        else:
            # All-day event (date only)
            return datetime.fromisoformat(datetime_str)

    def get_event(self, event_id: str) -> Optional[dict]:
        """
        Fetch an event by ID to validate its properties.

        Args:
            event_id: Google Calendar event ID.

        Returns:
            Event dict if found, None otherwise.
        """
        try:
            events = self.client.get_events(days=30)
            for event in events:
                if event["id"] == event_id:
                    return event
            return None
        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None

    def get_test_events(self, days: int = 7) -> list[dict]:
        """
        Get all [TEST] events from the calendar.

        Args:
            days: Number of days to look ahead.

        Returns:
            List of events with [TEST] prefix.
        """
        try:
            events = self.client.get_events(days=days)
            test_events = [
                e for e in events if e.get("summary", "").startswith(self.TEST_PREFIX)
            ]
            logger.info(f"Found {len(test_events)} [TEST] events in next {days} days")
            return test_events
        except Exception as e:
            logger.error(f"Failed to get test events: {e}")
            return []

    def cleanup_all_test_events(self) -> int:
        """
        Delete all [TEST] events created during this session.

        Returns:
            Number of events deleted.
        """
        deleted = 0
        for event_id in self.created_events:
            try:
                self.client.delete_event(event_id)
                deleted += 1
                logger.debug(f"Deleted event: {event_id}")
            except Exception as e:
                logger.warning(f"Failed to delete event {event_id}: {e}")
                # Event may already be deleted

        logger.info(f"Cleaned up {deleted}/{len(self.created_events)} session events")
        self.created_events.clear()
        return deleted

    def cleanup_all_test_prefix_events(self, days: int = 60) -> int:
        """
        Delete ALL events with [TEST] prefix (full cleanup).

        Use this for cleaning up orphaned test events from previous runs.

        Args:
            days: Number of days to look ahead for cleanup.

        Returns:
            Number of events deleted.
        """
        try:
            events = self.client.get_events(days=days)
            deleted = 0

            for event in events:
                if event.get("summary", "").startswith(self.TEST_PREFIX):
                    try:
                        self.client.delete_event(event["id"])
                        deleted += 1
                        logger.debug(f"Deleted [TEST] event: {event['summary']}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete event {event['id']}: {e}"
                        )

            logger.info(f"Full cleanup: deleted {deleted} [TEST] events")
            return deleted

        except Exception as e:
            logger.error(f"Failed during full cleanup: {e}")
            return 0

    def check_slot_available(
        self,
        start: datetime,
        end: datetime,
    ) -> bool:
        """
        Check if a time slot is available (no conflicts).

        Args:
            start: Slot start time.
            end: Slot end time.

        Returns:
            True if slot is available, False if there's a conflict.
        """
        try:
            events = self.client.get_events(days=7)

            for event in events:
                if event.get("all_day"):
                    continue

                event_start = self._parse_datetime(event["start"])
                event_end = self._parse_datetime(event["end"])

                # Check for overlap: start1 < end2 AND start2 < end1
                if start < event_end and end > event_start:
                    logger.debug(
                        f"Slot conflict with event: {event.get('summary')} "
                        f"({event_start} - {event_end})"
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to check slot availability: {e}")
            return False  # Assume not available on error

    def verify_event_exists(self, event_id: str) -> bool:
        """
        Verify that an event exists in the calendar.

        Args:
            event_id: Google Calendar event ID.

        Returns:
            True if event exists, False otherwise.
        """
        event = self.get_event(event_id)
        return event is not None

    def get_session_event_count(self) -> int:
        """
        Get the number of events created in this session.

        Returns:
            Number of tracked events.
        """
        return len(self.created_events)


# =============================================================================
# CLI FOR MANUAL TESTING
# =============================================================================


def main():
    """CLI entry point for manual testing."""
    import argparse

    # Setup logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Calendar Test Client CLI - Manage [TEST] calendar events"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up all [TEST] events from calendar",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all [TEST] events",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create a sample test event",
    )
    parser.add_argument(
        "--account",
        default="personal",
        help="Google account name (default: personal)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look ahead (default: 7)",
    )

    args = parser.parse_args()

    try:
        client = CalendarTestClient(account=args.account)

        if args.cleanup:
            deleted = client.cleanup_all_test_prefix_events(days=60)
            print(f"Deleted {deleted} [TEST] events")

        elif args.list:
            events = client.get_test_events(days=args.days)
            print(f"Found {len(events)} [TEST] events:")
            for event in events:
                print(f"  - {event['summary']}")
                print(f"    Start: {event['start']}")
                print(f"    ID: {event['id']}")

        elif args.create:
            # Create a sample test event for tomorrow
            start = datetime.now() + timedelta(days=1)
            start = start.replace(hour=10, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)

            event = client.create_test_event(
                summary="Sample Meeting",
                start=start,
                end=end,
                timezone="Asia/Makassar",
            )
            print(f"Created event: {event.summary}")
            print(f"  ID: {event.id}")
            print(f"  Start: {event.start}")
            print(f"  End: {event.end}")
            if event.html_link:
                print(f"  Link: {event.html_link}")

        else:
            parser.print_help()

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(
            "Please ensure you have set up Google Calendar authentication. "
            "See .claude/skills/google-calendar/SKILL.md for setup instructions."
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
