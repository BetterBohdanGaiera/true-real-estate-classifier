"""
Conversation pause detection.

This module detects gaps in conversation and provides metadata about
conversation pauses (duration, pause type, who sent last message).
The AI agent is responsible for generating all conversational text,
including any greetings or acknowledgments of time gaps.
"""
from datetime import datetime, timezone, timezone, timedelta
from dataclasses import dataclass
from typing import Optional
from enum import Enum

import pytz

class PauseType(str, Enum):
    """Types of conversation pauses based on duration."""
    NONE = "none"           # < 1 hour - no pause, normal flow
    SHORT = "short"         # 1-4 hours - brief pause
    MEDIUM = "medium"       # 4-24 hours - same day pause
    LONG = "long"           # 1-3 days - notable gap
    VERY_LONG = "very_long" # 3-7 days - significant absence
    DORMANT = "dormant"     # > 7 days - conversation went cold

# Pause type thresholds in hours
PAUSE_THRESHOLDS = {
    PauseType.NONE: 1.0,
    PauseType.SHORT: 4.0,
    PauseType.MEDIUM: 24.0,
    PauseType.LONG: 72.0,      # 3 days
    PauseType.VERY_LONG: 168.0, # 7 days
}

@dataclass
class ConversationGap:
    """Detected conversation gap with context."""
    pause_type: PauseType
    hours: float
    last_message_from: str  # "agent", "prospect", or "none"
    suggested_greeting: Optional[str]

def detect_pause(
    last_contact: Optional[datetime],
    last_response: Optional[datetime],
    now: Optional[datetime] = None
) -> ConversationGap:
    """
    Detect conversation pause and return gap metadata.

    Analyzes the gap between now and the last activity in the conversation,
    considering who sent the last message. Returns metadata only; the AI
    agent is responsible for generating any greeting or acknowledgment text.

    Args:
        last_contact: When agent last sent a message to prospect
        last_response: When prospect last responded to agent
        now: Current time (defaults to datetime.now())

    Returns:
        ConversationGap with pause type and duration metadata
    """
    if now is None:
        now = datetime.now()

    # Make sure 'now' is timezone-naive or handle appropriately
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    # Normalize timestamps to naive datetime for comparison
    if last_contact is not None and last_contact.tzinfo is not None:
        last_contact = last_contact.replace(tzinfo=None)
    if last_response is not None and last_response.tzinfo is not None:
        last_response = last_response.replace(tzinfo=None)

    # Determine last activity and who sent it
    if last_response and last_contact:
        if last_response > last_contact:
            last_activity = last_response
            last_from = "prospect"
        else:
            last_activity = last_contact
            last_from = "agent"
    elif last_response:
        last_activity = last_response
        last_from = "prospect"
    elif last_contact:
        last_activity = last_contact
        last_from = "agent"
    else:
        # No conversation history
        return ConversationGap(
            pause_type=PauseType.NONE,
            hours=0.0,
            last_message_from="none",
            suggested_greeting=None
        )

    # Calculate hours since last activity
    delta = now - last_activity
    hours = delta.total_seconds() / 3600.0

    # Determine pause type based on duration
    if hours < PAUSE_THRESHOLDS[PauseType.NONE]:
        pause_type = PauseType.NONE
    elif hours < PAUSE_THRESHOLDS[PauseType.SHORT]:
        pause_type = PauseType.SHORT
    elif hours < PAUSE_THRESHOLDS[PauseType.MEDIUM]:
        pause_type = PauseType.MEDIUM
    elif hours < PAUSE_THRESHOLDS[PauseType.LONG]:
        pause_type = PauseType.LONG
    elif hours < PAUSE_THRESHOLDS[PauseType.VERY_LONG]:
        pause_type = PauseType.VERY_LONG
    else:
        pause_type = PauseType.DORMANT

    return ConversationGap(
        pause_type=pause_type,
        hours=hours,
        last_message_from=last_from,
        suggested_greeting=None
    )

class PauseDetector:
    """
    Service for detecting and handling conversation pauses.

    Provides utility methods for working with conversation gaps,
    including greeting recommendations and sleeping hours detection.
    """

    def should_add_greeting(self, gap: ConversationGap) -> bool:
        """
        Check if we should add a special greeting for this gap.

        Always returns False because the AI agent is responsible for
        generating all conversational text, including greetings.
        Use get_pause_context_for_agent() to provide the agent with
        pause metadata so it can decide how to acknowledge the gap.

        Args:
            gap: The detected conversation gap

        Returns:
            Always False - greeting text generation is delegated to the AI agent
        """
        return False

    def get_pause_context_for_agent(self, gap: ConversationGap) -> Optional[str]:
        """
        Generate context string for the agent about the conversation gap.

        Provides pause metadata (duration, type, last sender) so the AI agent
        can decide how to acknowledge the time gap in its response. Does NOT
        include any suggested greeting text -- the agent generates all
        conversational content.

        Args:
            gap: The detected conversation gap

        Returns:
            Context string for agent, or None if no special context needed
        """
        if gap.pause_type in [PauseType.NONE, PauseType.SHORT]:
            return None

        context_parts = [
            f"KONTEKST PAUZY: Proshlo {gap.hours:.0f} chasov s poslednego soobshcheniya.",
            f"Tip pauzy: {gap.pause_type.value}",
            f"Posledneye soobshcheniye ot: {'klienta' if gap.last_message_from == 'prospect' else 'agenta' if gap.last_message_from == 'agent' else 'nikogo'}",
            "Consider acknowledging the time gap in your response.",
        ]

        return "\n".join(context_parts)

    def is_potentially_sleeping(
        self,
        client_timezone: str,
        current_utc: Optional[datetime] = None,
        sleep_start_hour: int = 23,
        sleep_end_hour: int = 7
    ) -> bool:
        """
        Check if it's likely sleeping hours for the client.

        Args:
            client_timezone: Client's timezone string (e.g., "Europe/Moscow")
            current_utc: Current time in UTC (defaults to now)
            sleep_start_hour: Hour when sleep period starts (default 23:00)
            sleep_end_hour: Hour when sleep period ends (default 07:00)

        Returns:
            True if likely sleeping (between sleep_start_hour and sleep_end_hour local time)
        """
        if current_utc is None:
            current_utc = datetime.now(pytz.UTC)
        elif current_utc.tzinfo is None:
            current_utc = pytz.UTC.localize(current_utc)

        try:
            tz = pytz.timezone(client_timezone)
            local_time = current_utc.astimezone(tz)
            hour = local_time.hour
            # Sleeping hours wrap around midnight
            if sleep_start_hour > sleep_end_hour:
                # e.g., 23:00 - 07:00
                return hour >= sleep_start_hour or hour < sleep_end_hour
            else:
                # e.g., 00:00 - 06:00 (unlikely but handle it)
                return sleep_start_hour <= hour < sleep_end_hour
        except Exception:
            return False  # If can't determine, assume awake

    def get_next_appropriate_time(
        self,
        client_timezone: str,
        current_utc: Optional[datetime] = None,
        target_hour: int = 9
    ) -> datetime:
        """
        Get the next appropriate time to contact the client.

        If it's currently sleeping hours, returns the next morning
        at target_hour in the client's timezone.

        Args:
            client_timezone: Client's timezone string
            current_utc: Current time in UTC (defaults to now)
            target_hour: Hour to schedule contact (default 9am)

        Returns:
            datetime (timezone-aware) for next appropriate contact time
        """
        if current_utc is None:
            current_utc = datetime.now(pytz.UTC)
        elif current_utc.tzinfo is None:
            current_utc = pytz.UTC.localize(current_utc)

        try:
            tz = pytz.timezone(client_timezone)
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone("Europe/Moscow")

        local_time = current_utc.astimezone(tz)

        # If it's before target_hour today, schedule for today
        # Otherwise, schedule for tomorrow
        if local_time.hour < target_hour:
            next_time = local_time.replace(
                hour=target_hour,
                minute=0,
                second=0,
                microsecond=0
            )
        else:
            # Schedule for tomorrow
            next_day = local_time + timedelta(days=1)
            next_time = next_day.replace(
                hour=target_hour,
                minute=0,
                second=0,
                microsecond=0
            )

        return next_time
