"""
CRM module - Customer relationship management for prospects.

This module provides Pydantic models and management utilities for
tracking prospects through the sales pipeline.
"""
from .models import (
    Prospect,
    ProspectStatus,
    ScheduledAction,
    ScheduledActionStatus,
    ScheduledActionType,
    ConversationMessage,
    AgentAction,
    AgentConfig,
    HumanPolishConfig,
    SalesSlot,
    SchedulingResult,
    ScheduleFollowupToolInput,
)
from .prospect_manager import ProspectManager

__all__ = [
    # Models
    "Prospect",
    "ProspectStatus",
    "ScheduledAction",
    "ScheduledActionStatus",
    "ScheduledActionType",
    "ConversationMessage",
    "AgentAction",
    "AgentConfig",
    "HumanPolishConfig",
    "SalesSlot",
    "SchedulingResult",
    "ScheduleFollowupToolInput",
    # Manager
    "ProspectManager",
]
