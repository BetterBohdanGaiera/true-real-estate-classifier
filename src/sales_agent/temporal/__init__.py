"""
Temporal module - Timezone detection and conversation timing.

This module provides temporal awareness for the sales agent, including:
- TimezoneDetector: Estimate client timezone from message patterns
- PauseDetector: Detect long conversation gaps and suggest appropriate greetings
- estimate_timezone: Function to estimate timezone from message timestamps
- detect_pause: Function to detect conversation pauses and suggest greetings

The default timezone for Russian-speaking prospects is Europe/Moscow (UTC+3).

Example usage:
    from sales_agent.temporal import (
        detect_pause,
        estimate_timezone,
        TimezoneDetector,
        PauseDetector,
        PauseType,
        ConversationGap,
        TimezoneEstimate,
    )

    # Detect conversation pause
    gap = detect_pause(
        last_contact=datetime(2024, 1, 1, 12, 0),
        last_response=datetime(2024, 1, 1, 10, 0),
        now=datetime(2024, 1, 5, 12, 0)
    )
    print(f"Pause type: {gap.pause_type}, Greeting: {gap.suggested_greeting}")

    # Estimate timezone from message patterns
    estimate = estimate_timezone(
        message_timestamps=[datetime(2024, 1, 1, 12, 0), datetime(2024, 1, 2, 14, 0)]
    )
    print(f"Timezone: {estimate.timezone}, Confidence: {estimate.confidence}")
"""

from .timezone_detector import (
    TimezoneDetector,
    TimezoneEstimate,
    estimate_timezone,
    COMMON_TIMEZONES,
    DEFAULT_TIMEZONE,
    DEFAULT_UTC_OFFSET,
)
from .pause_detector import (
    PauseDetector,
    PauseType,
    ConversationGap,
    detect_pause,
    PAUSE_THRESHOLDS,
)

__all__ = [
    # Timezone detection
    "TimezoneDetector",
    "TimezoneEstimate",
    "estimate_timezone",
    "COMMON_TIMEZONES",
    "DEFAULT_TIMEZONE",
    "DEFAULT_UTC_OFFSET",
    # Pause detection
    "PauseDetector",
    "PauseType",
    "ConversationGap",
    "detect_pause",
    "PAUSE_THRESHOLDS",
]
