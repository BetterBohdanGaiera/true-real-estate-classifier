"""
Sales Representative Registry Scripts.

This module provides:
- Self-service registration for sales reps via Telegram bot
- Auto-approval registration flow (no admin needed)
- Google Calendar integration per rep
- Test prospect assignment and management
- Proactive outreach daemon

Main Components:
- RegistryBot: Telegram bot for conversational registration
- sales_rep_manager: CRUD operations for sales representatives
- test_prospect_manager: Test prospect assignment and tracking
- CalendarConnector: Google Calendar OAuth integration
- OutreachDaemon: Background task for proactive outreach

Migrated from src/sales_agent/registry/
"""

from .registry_models import (
    SalesRepStatus,
    ProspectStatus,
    SalesRepresentative,
    TestProspect,
    ConversationState,
    UserSession,
)

__all__ = [
    "SalesRepStatus",
    "ProspectStatus",
    "SalesRepresentative",
    "TestProspect",
    "ConversationState",
    "UserSession",
]
