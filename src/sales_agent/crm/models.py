"""
Pydantic models for Telegram Agent.
"""
from datetime import datetime, date, time
from enum import Enum
from typing import Literal, Optional
from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class ProspectStatus(str, Enum):
    """Status of a prospect in the pipeline."""
    NEW = "new"  # Just added, not yet contacted
    CONTACTED = "contacted"  # Initial message sent
    IN_CONVERSATION = "in_conversation"  # Actively chatting
    ZOOM_SCHEDULED = "zoom_scheduled"  # Meeting scheduled
    CONVERTED = "converted"  # Became a client
    ARCHIVED = "archived"  # No longer active


class ScheduledActionStatus(str, Enum):
    """Status of a scheduled action."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ScheduledActionType(str, Enum):
    """Type of scheduled action."""
    FOLLOW_UP = "follow_up"
    PRE_MEETING_REMINDER = "pre_meeting_reminder"


class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    id: int
    sender: Literal["agent", "prospect"]
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)


class Prospect(BaseModel):
    """A prospect to reach out to."""
    telegram_id: int | str  # @username or numeric ID
    name: str
    context: str  # Why we're contacting them (e.g., "Interested in villa in Canggu")
    status: ProspectStatus = ProspectStatus.NEW
    first_contact: Optional[datetime] = None
    last_contact: Optional[datetime] = None
    last_response: Optional[datetime] = None  # When they last responded
    message_count: int = 0  # Total messages sent by agent
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    notes: str = ""  # Additional notes
    email: Optional[str] = None  # Client email for meeting invite
    human_active: bool = False  # True when human operator has taken over

    class Config:
        use_enum_values = True


class ProspectInput(BaseModel):
    """Validated user input for adding a new prospect."""
    telegram_id: str
    name: str = Field(min_length=2, max_length=100)
    context: str = Field(min_length=10, max_length=1000)
    notes: str = Field(default="", max_length=2000)
    email: Optional[str] = None

    @field_validator('telegram_id')
    @classmethod
    def validate_telegram_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Telegram ID cannot be empty")
        if v.startswith('@'):
            if len(v) < 6:
                raise ValueError("Username too short (min 5 chars after @)")
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v.strip()):
            raise ValueError(f"Invalid email format: {v}")
        return v.strip().lower()


class SalesSlot(BaseModel):
    """A time slot for sales meetings."""
    id: str  # Format: "YYYYMMDD_HHMM"
    date: date
    start_time: time
    end_time: time
    salesperson: str = "Эксперт True Real Estate"
    is_available: bool = True
    booked_by: Optional[str] = None  # prospect telegram_id or None

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat()
        }


class SchedulingResult(BaseModel):
    """Result of a scheduling operation (booking or cancellation)."""
    success: bool
    message: str
    slot: Optional[SalesSlot] = None
    zoom_url: Optional[str] = None  # Zoom meeting URL if created
    error: Optional[str] = None


class AgentAction(BaseModel):
    """Action to take after processing a message."""
    action: Literal["reply", "wait", "escalate", "schedule", "check_availability", "schedule_followup"]
    message: Optional[str] = None
    reason: Optional[str] = None  # Why this action was chosen
    scheduling_data: Optional[dict] = None  # For scheduling actions: {"slot_id": "...", "topic": "..."}


class AgentConfig(BaseModel):
    """Configuration for the agent behavior."""
    agent_name: str = "Мария"  # Who is writing
    telegram_account: Optional[str] = None  # @username this bot operates as
    sales_director_name: str = "Антон Мироненко"  # Sales director name for templates
    company_name: str = "True Real Estate"
    response_delay_range: tuple[float, float] = (2.0, 5.0)  # Seconds
    # Length-based delay configuration (seconds)
    delay_short: tuple[float, float] = (1.0, 2.0)  # <50 chars
    delay_medium: tuple[float, float] = (3.0, 5.0)  # 50-200 chars
    delay_long: tuple[float, float] = (5.0, 10.0)  # >200 chars
    # Reading delay configuration (seconds) - simulates reading incoming message
    reading_delay_short: tuple[float, float] = (2.0, 4.0)    # <50 chars incoming
    reading_delay_medium: tuple[float, float] = (4.0, 8.0)   # 50-200 chars incoming
    reading_delay_long: tuple[float, float] = (8.0, 15.0)    # >200 chars incoming
    max_messages_per_day_per_prospect: Optional[int] = None  # None means no limit
    working_hours: Optional[tuple[int, int]] = None  # e.g., (9, 21) for 9am-9pm

    # Fields for skill and knowledge integration
    tone_of_voice_path: Optional[Path] = None
    how_to_communicate_path: Optional[Path] = None
    knowledge_base_path: Optional[Path] = None
    sales_calendar_path: Optional[Path] = None
    include_knowledge_base: bool = True
    max_knowledge_tokens: int = 4000  # Token limit for KB context

    escalation_keywords: list[str] = Field(default_factory=lambda: [
        "call", "phone", "urgent", "срочно", "позвони", "звонок"
    ])
    escalation_notify: Optional[str] = None  # Telegram ID to notify
    typing_simulation: bool = True  # Simulate typing indicator
    auto_follow_up_hours: int = 24  # Hours before follow-up if no response


class ScheduledAction(BaseModel):
    """A scheduled action to be executed later."""
    id: Optional[str] = None  # UUID, generated by database
    prospect_id: str  # telegram_id
    action_type: ScheduledActionType
    scheduled_for: datetime
    status: ScheduledActionStatus = ScheduledActionStatus.PENDING
    payload: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None

    class Config:
        use_enum_values = True


class ScheduleFollowupToolInput(BaseModel):
    """Input schema for schedule_followup tool."""
    follow_up_time: str  # ISO 8601 datetime string
    follow_up_intent: str  # Changed from message_template - describes WHAT to follow up about
    reason: str
