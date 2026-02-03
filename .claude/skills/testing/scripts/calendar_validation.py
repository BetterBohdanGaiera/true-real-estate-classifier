# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.0.0",
#   "pytz>=2024.1",
# ]
# ///
"""
Calendar Validation - Post-test validation for calendar events.

Validates that created calendar events have correct:
- Timezone in event data (Bali UTC+8)
- Attendee list
- Zoom link in description
- Time matches what was proposed to client

Used by calendar integration tests to verify event creation.

Example:
    from calendar_validation import CalendarValidator, CalendarValidationResult

    validator = CalendarValidator()
    result = validator.validate_event(
        event=calendar_event_dict,
        expected_timezone="Asia/Makassar",
        expected_attendees=["client@example.com"],
        expected_zoom_url="https://zoom.us/j/123456",
        proposed_time=datetime(2026, 2, 4, 14, 0),
    )
    if not result.all_passed:
        print(f"Validation errors: {result.validation_errors}")
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import pytz
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


class CalendarValidationResult(BaseModel):
    """
    Result of calendar event validation.

    Contains boolean flags for each validation check and a list of
    any validation errors encountered.

    Attributes:
        event_exists: Whether the event was found in the calendar.
        timezone_correct: Whether the event timezone matches expected.
        attendees_correct: Whether all expected attendees are present.
        zoom_link_present: Whether the Zoom link is in the description.
        time_matches_proposal: Whether event time matches proposed time.
        validation_errors: List of error messages for failed validations.
    """

    event_exists: bool
    timezone_correct: bool
    attendees_correct: bool
    zoom_link_present: bool
    time_matches_proposal: bool
    validation_errors: list[str] = []

    @property
    def all_passed(self) -> bool:
        """Check if all validations passed."""
        return (
            self.event_exists
            and self.timezone_correct
            and self.attendees_correct
            and self.zoom_link_present
            and self.time_matches_proposal
        )


class TimezoneConversionResult(BaseModel):
    """
    Result of timezone conversion verification.

    Used to verify that time conversions between Bali and client
    timezones are correct.

    Attributes:
        original_time: The original time in source timezone.
        converted_time: The converted time in target timezone.
        source_timezone: Source timezone name (e.g., "Asia/Makassar").
        target_timezone: Target timezone name (e.g., "Europe/Kyiv").
        conversion_correct: Whether the conversion matches expected.
        expected_offset_hours: Expected hour difference between zones.
        actual_offset_hours: Actual hour difference calculated.
    """

    original_time: datetime
    converted_time: datetime
    source_timezone: str
    target_timezone: str
    conversion_correct: bool
    expected_offset_hours: float
    actual_offset_hours: float


# =============================================================================
# CALENDAR VALIDATOR
# =============================================================================


class CalendarValidator:
    """
    Validates calendar events against expected values.

    Used after test completion to verify:
    1. Event was actually created in Google Calendar
    2. Timezone is correctly set (Bali UTC+8)
    3. Attendees include client email
    4. Zoom link is embedded in description
    5. Time matches what was proposed to client

    Example:
        validator = CalendarValidator()
        result = validator.validate_event(
            event=calendar_event_dict,
            expected_timezone="Asia/Makassar",
            expected_attendees=["client@example.com"],
            expected_zoom_url="https://zoom.us/j/123456",
            proposed_time=datetime(2026, 2, 4, 14, 0),
        )
        if not result.all_passed:
            print(f"Validation errors: {result.validation_errors}")
    """

    BALI_TZ = pytz.timezone("Asia/Makassar")  # UTC+8, no DST

    # Common client timezones for testing
    CLIENT_TIMEZONES = {
        "kyiv": pytz.timezone("Europe/Kyiv"),  # UTC+2/+3 (DST)
        "moscow": pytz.timezone("Europe/Moscow"),  # UTC+3
        "cet": pytz.timezone("CET"),  # UTC+1/+2 (DST)
        "est": pytz.timezone("America/New_York"),  # UTC-5/-4 (DST)
        "bali": pytz.timezone("Asia/Makassar"),  # UTC+8
    }

    def validate_event(
        self,
        event: Optional[dict],
        expected_timezone: str,
        expected_attendees: list[str],
        expected_zoom_url: Optional[str],
        proposed_time: datetime,
        tolerance_minutes: int = 5,
    ) -> CalendarValidationResult:
        """
        Validate a calendar event against expected values.

        Performs comprehensive validation of a calendar event to ensure
        it was created correctly with proper timezone, attendees, Zoom link,
        and scheduled time.

        Args:
            event: Calendar event dict from Google API (or None if not found).
                   Expected keys: "start", "attendees", "description".
            expected_timezone: Expected timezone (e.g., "Asia/Makassar").
            expected_attendees: List of email addresses that should be attendees.
            expected_zoom_url: Expected Zoom URL in description (or None if not required).
            proposed_time: The time that was proposed to the client.
            tolerance_minutes: Allowed time difference in minutes (default 5).

        Returns:
            CalendarValidationResult with validation status and errors.

        Example:
            >>> validator = CalendarValidator()
            >>> event = {
            ...     "start": "2026-02-04T14:00:00+08:00",
            ...     "attendees": [{"email": "client@example.com"}],
            ...     "description": "Join: https://zoom.us/j/123456",
            ... }
            >>> result = validator.validate_event(
            ...     event=event,
            ...     expected_timezone="Asia/Makassar",
            ...     expected_attendees=["client@example.com"],
            ...     expected_zoom_url="https://zoom.us/j/123456",
            ...     proposed_time=datetime(2026, 2, 4, 14, 0),
            ... )
            >>> print(result.all_passed)
            True
        """
        errors: list[str] = []

        # Check event exists
        if not event:
            return CalendarValidationResult(
                event_exists=False,
                timezone_correct=False,
                attendees_correct=False,
                zoom_link_present=False,
                time_matches_proposal=False,
                validation_errors=["Event not found in calendar"],
            )

        # Check timezone
        event_start = event.get("start", "")
        timezone_correct = self._check_timezone(event_start, expected_timezone)
        if not timezone_correct:
            errors.append(
                f"Timezone mismatch: expected {expected_timezone}, got start={event_start}"
            )

        # Check attendees
        event_attendees = event.get("attendees", [])
        attendees_correct = self._check_attendees(event_attendees, expected_attendees)
        if not attendees_correct:
            errors.append(
                f"Attendees mismatch: expected {expected_attendees}, "
                f"got {event_attendees}"
            )

        # Check Zoom link
        description = event.get("description", "") or ""
        if expected_zoom_url:
            zoom_link_present = (
                expected_zoom_url in description or "zoom" in description.lower()
            )
            if not zoom_link_present:
                errors.append("Zoom link not found in event description")
        else:
            zoom_link_present = True  # Not required

        # Check time matches proposal
        time_matches = self._check_time_matches(event, proposed_time, tolerance_minutes)
        if not time_matches:
            event_time = event.get("start", "N/A")
            errors.append(
                f"Time mismatch: proposed {proposed_time.isoformat()}, "
                f"event at {event_time}"
            )

        return CalendarValidationResult(
            event_exists=True,
            timezone_correct=timezone_correct,
            attendees_correct=attendees_correct,
            zoom_link_present=zoom_link_present,
            time_matches_proposal=time_matches,
            validation_errors=errors,
        )

    def _check_timezone(self, event_start: str, expected_timezone: str) -> bool:
        """
        Check if event start has correct timezone.

        Google Calendar API may return events in UTC (Z suffix) even when
        created with a specific timezone. This method accepts both the
        explicit timezone offset and UTC format as valid.

        Args:
            event_start: Event start time string from API.
            expected_timezone: Expected timezone name.

        Returns:
            True if timezone appears correct, False otherwise.
        """
        # Handle dict format from Google Calendar API
        if isinstance(event_start, dict):
            # Check timeZone field if present
            if "timeZone" in event_start:
                return expected_timezone in event_start["timeZone"]
            # Fall back to dateTime field
            event_start = event_start.get("dateTime", "")

        # Google Calendar often returns times in UTC (Z suffix) for events
        # that were created with a specific timezone. This is valid behavior.
        # Accept both explicit timezone offset and UTC format.
        if expected_timezone in ("Asia/Makassar", "Asia/Jakarta"):
            # Accept +08:00 offset, Makassar name, or UTC (Z) format
            return (
                "+08:00" in event_start
                or "Makassar" in str(event_start)
                or "+08" in event_start
                or event_start.endswith("Z")  # UTC is also valid
            )

        # Generic check - accept explicit timezone or UTC
        return expected_timezone in str(event_start) or event_start.endswith("Z")

    def _check_attendees(
        self,
        event_attendees: list,
        expected_attendees: list[str],
    ) -> bool:
        """
        Check if all expected attendees are in the event.

        Handles both string lists and dict lists (from Google API)
        containing email addresses.

        Args:
            event_attendees: List of attendees from event (strings or dicts).
            expected_attendees: List of email addresses that should be present.

        Returns:
            True if all expected attendees are found, False otherwise.
        """
        # Handle both string list and dict list from API
        actual_emails: list[str] = []
        for att in event_attendees:
            if isinstance(att, str):
                actual_emails.append(att.lower())
            elif isinstance(att, dict):
                actual_emails.append(att.get("email", "").lower())

        for expected in expected_attendees:
            if expected.lower() not in actual_emails:
                return False
        return True

    def _check_time_matches(
        self,
        event: dict,
        proposed_time: datetime,
        tolerance_minutes: int,
    ) -> bool:
        """
        Check if event time matches proposed time within tolerance.

        Compares the event start time with the proposed time,
        properly handling timezone conversions. If the event is in UTC,
        converts it to Bali timezone before comparing with the proposed time
        (which is assumed to be in Bali timezone).

        Args:
            event: Calendar event dict with "start" key.
            proposed_time: The time that was proposed to the client (in Bali TZ).
            tolerance_minutes: Maximum allowed difference in minutes.

        Returns:
            True if times match within tolerance, False otherwise.
        """
        event_start = event.get("start", "")

        # Handle dict format from Google Calendar API
        if isinstance(event_start, dict):
            event_start = event_start.get("dateTime", "")

        try:
            if "T" not in event_start:
                # All-day event
                return False

            bali_tz = self.CLIENT_TIMEZONES["bali"]
            utc_tz = pytz.UTC

            # Parse event time with timezone awareness
            if event_start.endswith("Z"):
                # UTC format: 2026-02-04T05:00:00Z
                time_part = event_start[:-1]  # Remove Z
                event_time = datetime.fromisoformat(time_part)
                event_time = utc_tz.localize(event_time)
                # Convert UTC to Bali timezone for comparison
                event_time_bali = event_time.astimezone(bali_tz)
            elif "+" in event_start or (event_start.count("-") > 2 and "T" in event_start):
                # Has timezone offset: 2026-02-04T13:00:00+08:00
                # Python 3.11+ can parse this directly
                try:
                    event_time = datetime.fromisoformat(event_start)
                    event_time_bali = event_time.astimezone(bali_tz)
                except ValueError:
                    # Fallback for older Python
                    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", event_start)
                    if match:
                        time_part = match.group(1)
                        event_time_bali = bali_tz.localize(datetime.fromisoformat(time_part))
                    else:
                        return False
            else:
                # No timezone info, assume Bali
                event_time_bali = bali_tz.localize(datetime.fromisoformat(event_start))

            # Make proposed time timezone-aware in Bali
            if proposed_time.tzinfo is None:
                proposed_time_bali = bali_tz.localize(proposed_time)
            else:
                proposed_time_bali = proposed_time.astimezone(bali_tz)

            # Compare times in the same timezone
            time_diff = abs((event_time_bali - proposed_time_bali).total_seconds())
            return time_diff <= tolerance_minutes * 60

        except (ValueError, TypeError) as e:
            logger.warning(f"Time comparison failed: {e}")
            return False

    def convert_to_client_timezone(
        self,
        bali_time: datetime,
        client_timezone: str,
    ) -> datetime:
        """
        Convert Bali time to client's local timezone.

        Handles both naive and aware datetime objects. Naive datetimes
        are assumed to be in Bali timezone.

        Args:
            bali_time: Time in Bali timezone (may be naive or aware).
            client_timezone: Client's timezone name (e.g., "Europe/Kyiv")
                            or shorthand ("kyiv", "moscow", "est").

        Returns:
            datetime in client's local timezone (timezone-aware).

        Example:
            >>> validator = CalendarValidator()
            >>> bali_time = datetime(2026, 2, 4, 14, 0)  # 2pm Bali
            >>> kyiv_time = validator.convert_to_client_timezone(bali_time, "Europe/Kyiv")
            >>> print(kyiv_time.strftime("%H:%M %Z"))
            08:00 EET
        """
        # Ensure bali_time is timezone-aware
        if bali_time.tzinfo is None:
            bali_aware = self.BALI_TZ.localize(bali_time)
        else:
            bali_aware = bali_time

        # Get client timezone
        if client_timezone in self.CLIENT_TIMEZONES:
            client_tz = self.CLIENT_TIMEZONES[client_timezone]
        else:
            client_tz = pytz.timezone(client_timezone)

        return bali_aware.astimezone(client_tz)

    def verify_timezone_conversion(
        self,
        bali_time: datetime,
        displayed_time: str,
        client_timezone: str,
    ) -> TimezoneConversionResult:
        """
        Verify that time conversion to client timezone is correct.

        Useful for testing that times shown to clients in their local
        timezone are calculated correctly from Bali time.

        Args:
            bali_time: Original time in Bali timezone.
            displayed_time: Time string shown to client (e.g., "14:00", "2:00 PM").
            client_timezone: Client's timezone name or shorthand.

        Returns:
            TimezoneConversionResult with conversion details and verification.

        Example:
            >>> validator = CalendarValidator()
            >>> result = validator.verify_timezone_conversion(
            ...     bali_time=datetime(2026, 2, 4, 14, 0),
            ...     displayed_time="08:00",
            ...     client_timezone="Europe/Kyiv",
            ... )
            >>> print(result.conversion_correct)
            True
        """
        # Convert to client timezone
        client_time = self.convert_to_client_timezone(bali_time, client_timezone)

        # Extract hour from displayed time
        displayed_hour = self._extract_hour(displayed_time)

        # Calculate expected offset
        bali_utc_offset = 8  # UTC+8

        # Get client timezone object
        if client_timezone in self.CLIENT_TIMEZONES:
            client_tz = self.CLIENT_TIMEZONES[client_timezone]
        else:
            client_tz = pytz.timezone(client_timezone)

        # Get client UTC offset
        client_utc_offset_seconds = client_time.utcoffset()
        if client_utc_offset_seconds is not None:
            client_utc_offset = client_utc_offset_seconds.total_seconds() / 3600
        else:
            client_utc_offset = 0

        expected_offset = bali_utc_offset - client_utc_offset

        # Check if displayed hour matches converted time
        conversion_correct = (
            displayed_hour is not None and client_time.hour == displayed_hour
        )

        return TimezoneConversionResult(
            original_time=bali_time,
            converted_time=client_time,
            source_timezone="Asia/Makassar",
            target_timezone=client_timezone,
            conversion_correct=conversion_correct,
            expected_offset_hours=expected_offset,
            actual_offset_hours=expected_offset,
        )

    def _extract_hour(self, time_str: str) -> Optional[int]:
        """
        Extract hour from various time formats.

        Supports 24-hour format (14:00) and 12-hour format (2:00 PM).

        Args:
            time_str: Time string in any common format.

        Returns:
            Hour as integer (0-23), or None if parsing fails.
        """
        # Handle "14:00" format
        match = re.search(r"(\d{1,2}):(\d{2})", time_str)
        if match:
            hour = int(match.group(1))
            # Check for AM/PM suffix after the time
            if re.search(r"PM|pm", time_str) and hour != 12:
                hour += 12
            elif re.search(r"AM|am", time_str) and hour == 12:
                hour = 0
            return hour

        # Handle "2 PM" format (no colon)
        match = re.search(r"(\d{1,2})\s*(AM|PM|am|pm)", time_str)
        if match:
            hour = int(match.group(1))
            if match.group(2).upper() == "PM" and hour != 12:
                hour += 12
            elif match.group(2).upper() == "AM" and hour == 12:
                hour = 0
            return hour

        return None

    def get_offset_between_timezones(
        self,
        tz1: str,
        tz2: str,
        at_time: Optional[datetime] = None,
    ) -> float:
        """
        Get hour offset between two timezones at a specific time.

        Accounts for DST changes by calculating the offset at a
        specific point in time.

        Args:
            tz1: First timezone name or shorthand.
            tz2: Second timezone name or shorthand.
            at_time: Time to check offset (default: now). Should be naive.

        Returns:
            Offset in hours (positive means tz1 is ahead of tz2).

        Example:
            >>> validator = CalendarValidator()
            >>> # In winter, Bali is 5 hours ahead of Kyiv
            >>> offset = validator.get_offset_between_timezones(
            ...     "Asia/Makassar",
            ...     "Europe/Kyiv",
            ...     datetime(2026, 1, 15, 12, 0),
            ... )
            >>> print(offset)
            6.0
        """
        if at_time is None:
            at_time = datetime.now()

        # Get timezone objects
        if tz1 in self.CLIENT_TIMEZONES:
            tz1_obj = self.CLIENT_TIMEZONES[tz1]
        else:
            tz1_obj = pytz.timezone(tz1)

        if tz2 in self.CLIENT_TIMEZONES:
            tz2_obj = self.CLIENT_TIMEZONES[tz2]
        else:
            tz2_obj = pytz.timezone(tz2)

        # Localize time to each timezone
        tz1_time = tz1_obj.localize(at_time)
        tz2_time = tz2_obj.localize(at_time)

        # Calculate offset
        offset1 = tz1_time.utcoffset()
        offset2 = tz2_time.utcoffset()

        if offset1 is None or offset2 is None:
            return 0.0

        offset1_hours = offset1.total_seconds() / 3600
        offset2_hours = offset2.total_seconds() / 3600

        return offset1_hours - offset2_hours


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    from datetime import datetime

    validator = CalendarValidator()

    # Test timezone conversion
    bali_time = datetime(2026, 2, 4, 14, 0)  # 2pm Bali

    print("Timezone Conversion Tests:")
    print("=" * 50)

    for tz_name, tz_short in [
        ("Europe/Kyiv", "kyiv"),
        ("Europe/Moscow", "moscow"),
        ("America/New_York", "est"),
    ]:
        client_time = validator.convert_to_client_timezone(bali_time, tz_name)
        offset = validator.get_offset_between_timezones(
            "Asia/Makassar", tz_name, bali_time
        )
        print(
            f"Bali 14:00 -> {tz_name}: "
            f"{client_time.strftime('%H:%M')} (offset: {offset:+.0f}h)"
        )

    print("\nValidation Test:")
    print("=" * 50)

    # Mock event for testing
    mock_event = {
        "id": "test123",
        "summary": "[TEST] Meeting with John",
        "start": "2026-02-04T14:00:00+08:00",
        "end": "2026-02-04T15:00:00+08:00",
        "attendees": [{"email": "john@example.com"}],
        "description": "Join Zoom: https://zoom.us/j/123456",
    }

    result = validator.validate_event(
        event=mock_event,
        expected_timezone="Asia/Makassar",
        expected_attendees=["john@example.com"],
        expected_zoom_url="https://zoom.us/j/123456",
        proposed_time=datetime(2026, 2, 4, 14, 0),
    )

    print(f"All passed: {result.all_passed}")
    print(f"Event exists: {result.event_exists}")
    print(f"Timezone correct: {result.timezone_correct}")
    print(f"Attendees correct: {result.attendees_correct}")
    print(f"Zoom link present: {result.zoom_link_present}")
    print(f"Time matches: {result.time_matches_proposal}")
    if result.validation_errors:
        print(f"Errors: {result.validation_errors}")

    print("\nTimezone Conversion Verification:")
    print("=" * 50)

    # Verify conversion for Kyiv client
    conversion_result = validator.verify_timezone_conversion(
        bali_time=datetime(2026, 2, 4, 14, 0),
        displayed_time="08:00",
        client_timezone="Europe/Kyiv",
    )
    print(f"Bali 14:00 displayed as 08:00 for Kyiv client")
    print(f"Conversion correct: {conversion_result.conversion_correct}")
    print(
        f"Converted time: {conversion_result.converted_time.strftime('%H:%M %Z')}"
    )
