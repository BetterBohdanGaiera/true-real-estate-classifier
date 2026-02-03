"""
Telegram skill - Main sales agent daemon and Telegram integration.

This package provides the core Telegram sales agent functionality:
- TelegramDaemon: Long-running service for prospect outreach
- TelegramAgent: Claude-powered agent for conversations
- TelegramService: Telegram API wrapper with human-like behavior
- ProspectManager: Manages prospects and conversation states
- KnowledgeLoader: Loads and manages knowledge base context
- SalesCalendar: Manages sales team availability
- SchedulingTool: Meeting scheduling functionality
- SchedulerService: APScheduler wrapper for delayed actions
- Various models for data structures

Usage:
    from telegram.scripts import TelegramDaemon, TelegramAgent, TelegramService
    from telegram.scripts import Prospect, ProspectStatus, AgentConfig
"""

# Try package-style imports first, fall back to direct imports
try:
    # Core daemon and agent
    from .daemon import TelegramDaemon
    from .telegram_agent import TelegramAgent, SCHEDULE_FOLLOWUP_TOOL
    from .telegram_service import (
        TelegramService,
        create_telegram_service,
        is_private_chat,
        is_group_or_channel,
    )

    # Telegram fetch utilities
    from .telegram_fetch import (
        get_client,
        load_config,
        is_configured,
        get_setup_instructions,
        get_status,
        get_chat_type,
        format_message,
        list_chats,
        fetch_recent,
        search_messages,
        resolve_entity,
        edit_message,
        send_message as telegram_send_message,
        download_media,
        fetch_unread,
        format_output,
        fetch_thread_messages,
        CONFIG_DIR,
        CONFIG_FILE,
        SESSION_FILE,
    )

    # Bot send utilities
    from .bot_send import (
        send_message as bot_send_message,
        get_chat_id_from_db,
        list_contacts,
        format_for_telegram,
    )

    # Knowledge and prospect management
    from .knowledge_loader import KnowledgeLoader, TOPIC_FILES, TOPIC_NAMES
    from .prospect_manager import ProspectManager

    # Scheduling
    from .sales_calendar import SalesCalendar
    from .scheduling_tool import SchedulingTool, RUSSIAN_MONTHS, RUSSIAN_WEEKDAYS
    from .scheduler_service import SchedulerService

    # Scheduled action manager functions
    from .scheduled_action_manager import (
        create_scheduled_action,
        get_pending_actions,
        cancel_pending_for_prospect,
        get_by_id as get_action_by_id,
        mark_executed,
        close_pool,
        get_pool,
        get_connection,
    )

    # Models
    from .models import (
        Prospect,
        ProspectStatus,
        AgentConfig,
        AgentAction,
        SalesSlot,
        SchedulingResult,
        ConversationMessage,
        ScheduledAction,
        ScheduledActionStatus,
        ScheduledActionType,
        FollowUpPollingConfig,
        ScheduleFollowupToolInput,
    )

    # Conversation testing
    from .conversation_evaluator import ConversationAssessment
    from .conversation_simulator import (
        PersonaDefinition,
        ConversationTurn,
        ConversationOutcome,
        ConversationResult,
    )

except ImportError:
    # Direct imports when running scripts directly
    from daemon import TelegramDaemon
    from telegram_agent import TelegramAgent, SCHEDULE_FOLLOWUP_TOOL
    from telegram_service import (
        TelegramService,
        create_telegram_service,
        is_private_chat,
        is_group_or_channel,
    )

    from telegram_fetch import (
        get_client,
        load_config,
        is_configured,
        get_setup_instructions,
        get_status,
        get_chat_type,
        format_message,
        list_chats,
        fetch_recent,
        search_messages,
        resolve_entity,
        edit_message,
        send_message as telegram_send_message,
        download_media,
        fetch_unread,
        format_output,
        fetch_thread_messages,
        CONFIG_DIR,
        CONFIG_FILE,
        SESSION_FILE,
    )

    from bot_send import (
        send_message as bot_send_message,
        get_chat_id_from_db,
        list_contacts,
        format_for_telegram,
    )

    from knowledge_loader import KnowledgeLoader, TOPIC_FILES, TOPIC_NAMES
    from prospect_manager import ProspectManager

    from sales_calendar import SalesCalendar
    from scheduling_tool import SchedulingTool, RUSSIAN_MONTHS, RUSSIAN_WEEKDAYS
    from scheduler_service import SchedulerService

    from scheduled_action_manager import (
        create_scheduled_action,
        get_pending_actions,
        cancel_pending_for_prospect,
        get_by_id as get_action_by_id,
        mark_executed,
        close_pool,
        get_pool,
        get_connection,
    )

    from models import (
        Prospect,
        ProspectStatus,
        AgentConfig,
        AgentAction,
        SalesSlot,
        SchedulingResult,
        ConversationMessage,
        ScheduledAction,
        ScheduledActionStatus,
        ScheduledActionType,
        FollowUpPollingConfig,
        ScheduleFollowupToolInput,
    )

    from conversation_evaluator import ConversationAssessment
    from conversation_simulator import (
        PersonaDefinition,
        ConversationTurn,
        ConversationOutcome,
        ConversationResult,
    )


__all__ = [
    # Core daemon and agent
    "TelegramDaemon",
    "TelegramAgent",
    "SCHEDULE_FOLLOWUP_TOOL",

    # Telegram service
    "TelegramService",
    "create_telegram_service",
    "is_private_chat",
    "is_group_or_channel",

    # Telegram fetch utilities
    "get_client",
    "load_config",
    "is_configured",
    "get_setup_instructions",
    "get_status",
    "get_chat_type",
    "format_message",
    "list_chats",
    "fetch_recent",
    "search_messages",
    "resolve_entity",
    "edit_message",
    "telegram_send_message",
    "download_media",
    "fetch_unread",
    "format_output",
    "fetch_thread_messages",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "SESSION_FILE",

    # Bot send utilities
    "bot_send_message",
    "get_chat_id_from_db",
    "list_contacts",
    "format_for_telegram",

    # Knowledge and prospect management
    "KnowledgeLoader",
    "TOPIC_FILES",
    "TOPIC_NAMES",
    "ProspectManager",

    # Scheduling
    "SalesCalendar",
    "SchedulingTool",
    "RUSSIAN_MONTHS",
    "RUSSIAN_WEEKDAYS",
    "SchedulerService",

    # Scheduled action manager functions
    "create_scheduled_action",
    "get_pending_actions",
    "cancel_pending_for_prospect",
    "get_action_by_id",
    "mark_executed",
    "close_pool",
    "get_pool",
    "get_connection",

    # Models
    "Prospect",
    "ProspectStatus",
    "AgentConfig",
    "AgentAction",
    "SalesSlot",
    "SchedulingResult",
    "ConversationMessage",
    "ScheduledAction",
    "ScheduledActionStatus",
    "ScheduledActionType",
    "FollowUpPollingConfig",
    "ScheduleFollowupToolInput",

    # Conversation testing
    "ConversationAssessment",
    "PersonaDefinition",
    "ConversationTurn",
    "ConversationOutcome",
    "ConversationResult",
]
