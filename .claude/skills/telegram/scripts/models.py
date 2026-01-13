"""
Pydantic models for Telegram Agent.
"""
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ProspectStatus(str, Enum):
    """Status of a prospect in the pipeline."""
    NEW = "new"  # Just added, not yet contacted
    CONTACTED = "contacted"  # Initial message sent
    IN_CONVERSATION = "in_conversation"  # Actively chatting
    ZOOM_SCHEDULED = "zoom_scheduled"  # Meeting scheduled
    CONVERTED = "converted"  # Became a client
    ARCHIVED = "archived"  # No longer active


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

    class Config:
        use_enum_values = True


class AgentAction(BaseModel):
    """Action to take after processing a message."""
    action: Literal["reply", "wait", "escalate"]
    message: Optional[str] = None
    reason: Optional[str] = None  # Why this action was chosen


class AgentConfig(BaseModel):
    """Configuration for the agent behavior."""
    agent_name: str = "Мария"  # Who is writing
    company_name: str = "True Real Estate"
    response_delay_range: tuple[float, float] = (2.0, 5.0)  # Seconds
    max_messages_per_day_per_prospect: int = 3
    working_hours: Optional[tuple[int, int]] = None  # e.g., (9, 21) for 9am-9pm
    escalation_keywords: list[str] = Field(default_factory=lambda: [
        "call", "phone", "urgent", "срочно", "позвони", "звонок"
    ])
    escalation_notify: Optional[str] = None  # Telegram ID to notify
    typing_simulation: bool = True  # Simulate typing indicator
    auto_follow_up_hours: int = 24  # Hours before follow-up if no response
