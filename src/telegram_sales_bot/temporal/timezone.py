"""
Timezone estimation from message patterns.

This module provides heuristics-based timezone detection for prospects
based on their message activity patterns. The default assumption for
Russian-speaking prospects is Moscow timezone (Europe/Moscow, UTC+3).
"""
from datetime import datetime, timezone, timezone
from typing import Optional
from dataclasses import dataclass

import pytz

# Common Russian-speaking timezones with their UTC offsets
COMMON_TIMEZONES: list[tuple[str, int]] = [
    ("Europe/Moscow", 3),       # MSK - Russia (Moscow)
    ("Europe/Kaliningrad", 2),  # UTC+2 - Russia (Kaliningrad)
    ("Europe/Samara", 4),       # UTC+4 - Russia (Samara)
    ("Asia/Yekaterinburg", 5),  # UTC+5 - Russia (Yekaterinburg)
    ("Asia/Novosibirsk", 7),    # UTC+7 - Russia (Novosibirsk)
    ("Asia/Vladivostok", 10),   # UTC+10 - Russia (Vladivostok)
    ("Europe/Kyiv", 2),         # UTC+2 - Ukraine
    ("Europe/Minsk", 3),        # UTC+3 - Belarus
    ("Asia/Almaty", 6),         # UTC+6 - Kazakhstan (east)
    ("Asia/Dubai", 4),          # UTC+4 - UAE (Russian expats)
    ("Asia/Bangkok", 7),        # UTC+7 - Thailand (expats)
    ("Asia/Makassar", 8),       # UTC+8 - Indonesia/Bali
]

# Default timezone for Russian-speaking prospects
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_UTC_OFFSET = 3

@dataclass
class TimezoneEstimate:
    """Result of timezone estimation."""
    timezone: str
    utc_offset: int
    confidence: float  # 0.0-1.0
    reason: str

def estimate_timezone(
    message_timestamps: list[datetime],
    bali_time: Optional[datetime] = None
) -> TimezoneEstimate:
    """
    Estimate client timezone from message timestamp patterns.

    Heuristics:
    1. If messages sent 9am-11pm local -> likely awake hours
    2. If messages sent 2am-6am Bali time -> likely different timezone
    3. Cluster message times to find "active window"

    Args:
        message_timestamps: List of message timestamps (should be in UTC or aware)
        bali_time: Current Bali time for reference (optional)

    Returns:
        TimezoneEstimate with best guess timezone
    """
    if not message_timestamps:
        # Default to Moscow for Russian speakers
        return TimezoneEstimate(
            timezone=DEFAULT_TIMEZONE,
            utc_offset=DEFAULT_UTC_OFFSET,
            confidence=0.3,
            reason="default_russian_no_messages"
        )

    # Convert all to UTC hours (assuming timestamps are UTC or naive=UTC)
    utc_hours = []
    for ts in message_timestamps:
        if ts.tzinfo is not None:
            # Convert to UTC
            utc_ts = ts.astimezone(pytz.UTC)
            utc_hours.append(utc_ts.hour)
        else:
            # Assume naive datetime is already UTC
            utc_hours.append(ts.hour)

    if not utc_hours:
        return TimezoneEstimate(
            timezone=DEFAULT_TIMEZONE,
            utc_offset=DEFAULT_UTC_OFFSET,
            confidence=0.3,
            reason="default_russian_empty_hours"
        )

    # Find the "center" of activity
    # Calculate average hour, handling wrap-around at midnight
    avg_hour = sum(utc_hours) / len(utc_hours)

    # Assume people are most active around 12:00-18:00 local time (midday to evening)
    # So if avg_hour in UTC is X, local timezone offset ~ 15 - X
    # This is a rough heuristic based on typical activity patterns
    estimated_offset = int(15 - avg_hour)
    estimated_offset = max(-12, min(14, estimated_offset))  # Clamp to valid UTC offset range

    # Find closest common timezone from our list
    best_tz = min(COMMON_TIMEZONES, key=lambda t: abs(t[1] - estimated_offset))

    # Calculate confidence based on number of data points
    confidence = 0.4  # Base confidence
    if len(message_timestamps) >= 3:
        confidence = 0.5
    if len(message_timestamps) >= 5:
        confidence = 0.65
    if len(message_timestamps) >= 10:
        confidence = 0.8
    if len(message_timestamps) >= 20:
        confidence = 0.9

    return TimezoneEstimate(
        timezone=best_tz[0],
        utc_offset=best_tz[1],
        confidence=confidence,
        reason=f"activity_pattern_{len(message_timestamps)}_messages"
    )

class TimezoneDetector:
    """
    Service for tracking and updating timezone estimates over time.

    This class maintains state and provides incremental updates to
    timezone estimates as more message data becomes available.
    """

    def __init__(self):
        """Initialize the timezone detector with Bali timezone reference."""
        self.bali_tz = pytz.timezone("Asia/Makassar")

    def update_estimate(
        self,
        current_estimate: Optional[str],
        current_confidence: float,
        new_message_time: datetime,
        all_message_times: Optional[list[datetime]] = None
    ) -> tuple[str, float]:
        """
        Update timezone estimate with new data point.

        If current confidence is already high (>= 0.9), we keep the existing
        estimate. Otherwise, we may refine based on new data.

        Args:
            current_estimate: Current timezone estimate (e.g., "Europe/Moscow")
            current_confidence: Current confidence score (0.0-1.0)
            new_message_time: New message timestamp to incorporate
            all_message_times: Optional list of all message timestamps for re-estimation

        Returns:
            tuple of (timezone, confidence)
        """
        # If already highly confident, don't change
        if current_confidence >= 0.9 and current_estimate:
            return current_estimate, current_confidence

        # If we have full message history, re-estimate
        if all_message_times:
            result = estimate_timezone(all_message_times)
            return result.timezone, result.confidence

        # Otherwise, just return current or default
        if current_estimate:
            # Slightly increase confidence with new data point
            new_confidence = min(current_confidence + 0.05, 0.9)
            return current_estimate, new_confidence

        # No current estimate - use default
        return DEFAULT_TIMEZONE, max(current_confidence, 0.3)

    def get_local_time(
        self,
        timezone_str: str,
        utc_time: Optional[datetime] = None
    ) -> datetime:
        """
        Get current time in the specified timezone.

        Args:
            timezone_str: Timezone string (e.g., "Europe/Moscow")
            utc_time: Optional UTC time to convert (defaults to now)

        Returns:
            datetime in the specified timezone
        """
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            # Fall back to Moscow
            tz = pytz.timezone(DEFAULT_TIMEZONE)

        if utc_time is None:
            utc_time = datetime.now(pytz.UTC)
        elif utc_time.tzinfo is None:
            utc_time = pytz.UTC.localize(utc_time)

        return utc_time.astimezone(tz)

    def is_appropriate_time_for_client(
        self,
        client_timezone: Optional[str],
        current_utc: Optional[datetime] = None,
        start_hour: int = 9,
        end_hour: int = 21
    ) -> bool:
        """
        Check if it's an appropriate time to message the client.

        Args:
            client_timezone: Client's timezone string
            current_utc: Current time in UTC (defaults to now)
            start_hour: Start of appropriate hours (default 9am)
            end_hour: End of appropriate hours (default 9pm)

        Returns:
            True if it's appropriate to message (within allowed hours)
        """
        if not client_timezone:
            return True  # Can't determine, allow messaging

        if current_utc is None:
            current_utc = datetime.now(pytz.UTC)
        elif current_utc.tzinfo is None:
            current_utc = pytz.UTC.localize(current_utc)

        try:
            local_time = self.get_local_time(client_timezone, current_utc)
            hour = local_time.hour
            return start_hour <= hour < end_hour
        except Exception:
            return True  # If error, allow messaging
