# Plan: Temporal Intelligence - Timezone, Offline & Long Pauses

## Task Description
Add temporal awareness to the sales agent: detect client timezone, handle offline periods, and recognize long conversation pauses. Currently the agent has no awareness of time context in the client's location or conversation gaps.

## Objective
Enable the sales agent to:
1. Detect/estimate client timezone for appropriate communication timing
2. Handle offline periods (don't spam while client is sleeping)
3. Recognize long conversation pauses and adapt greeting accordingly
4. Parse time expressions relative to client timezone ("завтра в 10" means client's 10am)

## Problem Statement
Current gaps:
- **Timezone**: Agent works in Bali time (UTC+8), but "напиши завтра в 10" could mean client's timezone
- **Offline periods**: Agent sends follow-up at 3 AM client time → poor experience
- **Long pauses**: Client returns after 3 days → agent continues as if conversation just happened
- No "Рад что вернулись!" or context reset for long gaps

## Solution Approach
1. Estimate timezone from client's message timestamps and patterns
2. Store timezone in Prospect model
3. Add conversation gap detection in message handler
4. Add "welcome back" prompt for long gaps
5. Parse relative time expressions with timezone awareness

## Relevant Files

### Existing Files to Modify
- `src/sales_agent/crm/models.py` - Add timezone and last_active fields to Prospect
- `src/sales_agent/crm/prospect_manager.py` - Add timezone detection logic
- `src/sales_agent/daemon.py` - Add pause detection, timezone-aware scheduling
- `src/sales_agent/agent/telegram_agent.py` - Add prompts for long pauses
- `src/sales_agent/scheduling/scheduler_service.py` - Timezone-aware scheduling

### New Files to Create
- `src/sales_agent/temporal/__init__.py` - Temporal utilities module
- `src/sales_agent/temporal/timezone_detector.py` - Timezone estimation
- `src/sales_agent/temporal/pause_detector.py` - Conversation gap detection

## Implementation Phases

### Phase 1: Foundation
- Add timezone field to Prospect model
- Create temporal module structure
- Add gap calculation utilities

### Phase 2: Core Implementation
- Implement timezone estimation from message patterns
- Implement pause detection
- Add "welcome back" prompt generation

### Phase 3: Integration
- Timezone-aware follow-up scheduling
- Client timezone in agent context
- Parse time expressions with timezone

## Step by Step Tasks

### 1. Update Prospect Model with Timezone
- In `src/sales_agent/crm/models.py`, add to Prospect:
```python
class Prospect(BaseModel):
    # ... existing fields ...
    estimated_timezone: Optional[str] = None  # e.g., "Europe/Moscow", "UTC+3"
    timezone_confidence: float = 0.0  # 0.0-1.0 confidence score
    typical_active_hours: Optional[tuple[int, int]] = None  # e.g., (9, 23)
    last_seen_online: Optional[datetime] = None
```

### 2. Create Temporal Module
- Create `src/sales_agent/temporal/__init__.py`:
```python
"""
Temporal module - Timezone detection and conversation timing.

Provides:
- TimezoneDetector: Estimate client timezone from message patterns
- PauseDetector: Detect long conversation gaps
- format_relative_time: Format time relative to client timezone
"""
from .timezone_detector import TimezoneDetector, estimate_timezone
from .pause_detector import PauseDetector, ConversationGap

__all__ = [
    "TimezoneDetector",
    "estimate_timezone",
    "PauseDetector",
    "ConversationGap",
]
```

### 3. Implement Timezone Detector
- Create `src/sales_agent/temporal/timezone_detector.py`:
```python
"""Timezone estimation from message patterns."""
from datetime import datetime, time
from typing import Optional
from dataclasses import dataclass

import pytz

# Common Russian-speaking timezones
COMMON_TIMEZONES = [
    ("Europe/Moscow", 3),      # MSK
    ("Europe/Kaliningrad", 2), # UTC+2
    ("Europe/Samara", 4),      # UTC+4
    ("Asia/Yekaterinburg", 5), # UTC+5
    ("Asia/Novosibirsk", 7),   # UTC+7
    ("Asia/Vladivostok", 10),  # UTC+10
    ("Europe/Kiev", 2),        # Ukraine
    ("Europe/Minsk", 3),       # Belarus
    ("Asia/Almaty", 6),        # Kazakhstan
    ("Asia/Dubai", 4),         # UAE (expats)
    ("Asia/Bangkok", 7),       # Thailand (expats)
    ("Asia/Bali", 8),          # Indonesia
]

@dataclass
class TimezoneEstimate:
    """Result of timezone estimation."""
    timezone: str
    utc_offset: int
    confidence: float
    reason: str

def estimate_timezone(
    message_timestamps: list[datetime],
    bali_time: datetime
) -> TimezoneEstimate:
    """
    Estimate client timezone from message timestamp patterns.

    Heuristics:
    1. If messages sent 9am-11pm local → likely awake hours
    2. If messages sent 2am-6am Bali time → likely different timezone
    3. Cluster message times to find "active window"

    Args:
        message_timestamps: List of message timestamps (UTC)
        bali_time: Current Bali time for reference

    Returns:
        TimezoneEstimate with best guess
    """
    if not message_timestamps:
        # Default to Moscow for Russian speakers
        return TimezoneEstimate(
            timezone="Europe/Moscow",
            utc_offset=3,
            confidence=0.3,
            reason="default_russian"
        )

    # Convert all to UTC hours
    utc_hours = [ts.hour for ts in message_timestamps]

    # Find the "center" of activity
    # If messages cluster around certain hours, estimate timezone
    avg_hour = sum(utc_hours) / len(utc_hours)

    # Assume people are most active around 12:00-18:00 local time
    # So if avg_hour in UTC is X, local timezone offset ≈ 15 - X
    estimated_offset = int(15 - avg_hour)
    estimated_offset = max(-12, min(14, estimated_offset))  # Clamp to valid range

    # Find closest common timezone
    best_tz = min(COMMON_TIMEZONES, key=lambda t: abs(t[1] - estimated_offset))

    confidence = 0.5  # Base confidence
    if len(message_timestamps) >= 5:
        confidence = 0.7
    if len(message_timestamps) >= 10:
        confidence = 0.85

    return TimezoneEstimate(
        timezone=best_tz[0],
        utc_offset=best_tz[1],
        confidence=confidence,
        reason=f"activity_pattern_{len(message_timestamps)}_messages"
    )

class TimezoneDetector:
    """Service for tracking and updating timezone estimates."""

    def __init__(self):
        self.bali_tz = pytz.timezone("Asia/Makassar")

    def update_estimate(
        self,
        current_estimate: Optional[str],
        current_confidence: float,
        new_message_time: datetime
    ) -> tuple[str, float]:
        """
        Update timezone estimate with new data point.

        Returns:
            (timezone, confidence) tuple
        """
        # Placeholder - full implementation would track patterns over time
        if current_confidence >= 0.9:
            return current_estimate, current_confidence

        # For now, return current or default
        return current_estimate or "Europe/Moscow", max(current_confidence, 0.3)
```

### 4. Implement Pause Detector
- Create `src/sales_agent/temporal/pause_detector.py`:
```python
"""Conversation pause detection."""
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class PauseType(str, Enum):
    """Types of conversation pauses."""
    NONE = "none"           # < 1 hour
    SHORT = "short"         # 1-4 hours
    MEDIUM = "medium"       # 4-24 hours
    LONG = "long"           # 1-3 days
    VERY_LONG = "very_long" # 3-7 days
    DORMANT = "dormant"     # > 7 days

@dataclass
class ConversationGap:
    """Detected conversation gap."""
    pause_type: PauseType
    hours: float
    last_message_from: str  # "agent" or "prospect"
    suggested_greeting: Optional[str]

def detect_pause(
    last_contact: Optional[datetime],
    last_response: Optional[datetime],
    now: Optional[datetime] = None
) -> ConversationGap:
    """
    Detect conversation pause and suggest appropriate greeting.

    Args:
        last_contact: When agent last sent message
        last_response: When prospect last responded
        now: Current time (defaults to now)

    Returns:
        ConversationGap with pause type and suggested greeting
    """
    now = now or datetime.now()

    # Determine last activity
    if last_response and last_contact:
        last_activity = max(last_response, last_contact)
        last_from = "prospect" if last_response > last_contact else "agent"
    elif last_response:
        last_activity = last_response
        last_from = "prospect"
    elif last_contact:
        last_activity = last_contact
        last_from = "agent"
    else:
        return ConversationGap(
            pause_type=PauseType.NONE,
            hours=0,
            last_message_from="none",
            suggested_greeting=None
        )

    hours = (now - last_activity).total_seconds() / 3600

    # Determine pause type
    if hours < 1:
        pause_type = PauseType.NONE
        greeting = None
    elif hours < 4:
        pause_type = PauseType.SHORT
        greeting = None  # Normal conversation flow
    elif hours < 24:
        pause_type = PauseType.MEDIUM
        greeting = None  # Same day, no special greeting
    elif hours < 72:  # 3 days
        pause_type = PauseType.LONG
        if last_from == "agent":
            greeting = None  # We wrote last, just continue
        else:
            greeting = "Добрый день! Продолжаем наш разговор?"
    elif hours < 168:  # 7 days
        pause_type = PauseType.VERY_LONG
        greeting = "Рад снова вас слышать! Мы общались о недвижимости на Бали."
    else:
        pause_type = PauseType.DORMANT
        greeting = "Здравствуйте! Давно не общались. Всё ещё актуален вопрос с недвижимостью на Бали?"

    return ConversationGap(
        pause_type=pause_type,
        hours=hours,
        last_message_from=last_from,
        suggested_greeting=greeting
    )

class PauseDetector:
    """Service for detecting and handling conversation pauses."""

    def should_add_greeting(self, gap: ConversationGap) -> bool:
        """Check if we should add a special greeting for this gap."""
        return gap.pause_type in [
            PauseType.LONG,
            PauseType.VERY_LONG,
            PauseType.DORMANT
        ] and gap.suggested_greeting is not None

    def is_potentially_sleeping(
        self,
        client_timezone: str,
        current_utc: datetime
    ) -> bool:
        """
        Check if it's likely sleeping hours for the client.

        Args:
            client_timezone: Client's timezone string
            current_utc: Current time in UTC

        Returns:
            True if likely sleeping (23:00-07:00 local time)
        """
        import pytz

        try:
            tz = pytz.timezone(client_timezone)
            local_time = current_utc.astimezone(tz)
            hour = local_time.hour
            return hour >= 23 or hour < 7
        except:
            return False  # If can't determine, assume awake
```

### 5. Update Daemon with Pause Detection
- In `src/sales_agent/daemon.py`, at start of `handle_incoming`:
```python
from sales_agent.temporal import detect_pause, PauseDetector

# Detect conversation pause
gap = detect_pause(
    prospect.last_contact,
    prospect.last_response,
    datetime.now()
)

if gap.pause_type.value not in ["none", "short"]:
    console.print(f"[dim]Conversation gap: {gap.hours:.1f} hours ({gap.pause_type.value})[/dim]")
```

### 6. Add Pause Context to Agent Prompt
- In `telegram_agent.py`, when generating response, include gap info:
```python
# In generate_response, add to user_prompt:
gap_context = ""
if gap and gap.pause_type.value not in ["none", "short"]:
    gap_context = f"""
КОНТЕКСТ: Прошло {gap.hours:.0f} часов с последнего сообщения.
Тип паузы: {gap.pause_type.value}
{f'Предлагаемое приветствие: "{gap.suggested_greeting}"' if gap.suggested_greeting else ''}

Учитывай этот контекст в своём ответе. Если пауза была долгой,
можешь мягко напомнить о чём шла речь.
"""
```

### 7. Timezone-aware Follow-up Scheduling
- In scheduler_service, when executing follow-up, check sleeping hours:
```python
# Before sending follow-up:
if pause_detector.is_potentially_sleeping(prospect.estimated_timezone, datetime.utcnow()):
    # Reschedule to morning
    console.print(f"[yellow]Client likely sleeping, rescheduling to morning[/yellow]")
    # Calculate 9 AM in client's timezone
    # Reschedule action
```

### 8. Update Working Hours Check
- Add client timezone awareness to working hours:
```python
def is_appropriate_time_for_client(
    client_timezone: Optional[str],
    current_utc: datetime
) -> bool:
    """Check if it's appropriate to message client now."""
    if not client_timezone:
        return True  # Can't determine, allow

    try:
        tz = pytz.timezone(client_timezone)
        local_time = current_utc.astimezone(tz)
        hour = local_time.hour
        # Appropriate: 9:00 - 21:00 local time
        return 9 <= hour < 21
    except:
        return True
```

### 9. Validate Implementation
- Test pause detection with various gaps
- Test timezone estimation
- Test sleeping hours detection
- Test follow-up rescheduling

## Testing Strategy

### Unit Tests
- Test detect_pause() with various time gaps
- Test estimate_timezone() with message patterns
- Test is_potentially_sleeping() with various timezones

### Integration Tests
1. Create prospect, wait 3 days, send message → verify greeting
2. Schedule follow-up for 3 AM client time → verify rescheduled
3. Multiple messages → verify timezone estimate improves

### Edge Cases
- New prospect with no history
- Prospect with only one message
- Edge of timezone boundaries
- Daylight saving time transitions

## Acceptance Criteria
- [ ] Conversation pauses > 24h trigger appropriate greeting context
- [ ] Client timezone estimated from message patterns
- [ ] Follow-ups not sent during client sleeping hours (23:00-07:00)
- [ ] Agent receives gap context in prompt for long pauses
- [ ] Timezone stored in prospect model
- [ ] "Рад снова вас слышать!" for 3+ day gaps

## Validation Commands
```bash
# Test temporal module
uv run python -c "from sales_agent.temporal import detect_pause, estimate_timezone; print('OK')"

# Test pause detection
uv run python -c "
from datetime import datetime, timedelta
from sales_agent.temporal.pause_detector import detect_pause

gap = detect_pause(
    datetime.now() - timedelta(days=3),
    datetime.now() - timedelta(days=4),
    datetime.now()
)
print(f'Pause: {gap.pause_type}, Greeting: {gap.suggested_greeting}')
"

# Compile check
uv run python -m py_compile src/sales_agent/temporal/*.py
```

## Notes
- Timezone estimation is heuristic - may not be 100% accurate
- Default to Moscow timezone for Russian speakers
- Store confidence score to improve over time
- Consider asking client timezone directly if uncertainty high
- Respect sleeping hours even for scheduled follow-ups
- Daylight saving time changes may affect timezone offsets
