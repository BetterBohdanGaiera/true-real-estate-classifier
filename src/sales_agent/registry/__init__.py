"""
Sales Representative Registry Module.

This module provides:
- Self-service registration for sales reps via Telegram bot
- Auto-approval registration flow (no admin needed)
- Google Calendar integration per rep
- Test prospect assignment and management
- Proactive outreach daemon

Main Components:
- RegistryBot: Telegram bot for conversational registration
- SalesRepManager: CRUD operations for sales representatives
- ProspectManager: Test prospect assignment and tracking
- CalendarConnector: Google Calendar OAuth integration
- OutreachDaemon: Background task for proactive outreach
"""

from sales_agent.registry.models import (
    SalesRepStatus,
    ProspectStatus,
    SalesRepresentative,
    TestProspect,
    ConversationState,
)

__all__ = [
    "SalesRepStatus",
    "ProspectStatus",
    "SalesRepresentative",
    "TestProspect",
    "ConversationState",
]
