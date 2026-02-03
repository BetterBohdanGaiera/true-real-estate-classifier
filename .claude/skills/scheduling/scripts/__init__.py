"""
Scheduling module - Sales calendar, Zoom booking, and scheduled actions.

This module provides:
- SalesCalendar: Manages sales team availability and slot booking
- SchedulingTool: Tool for the LLM agent to check availability and book meetings
- SchedulerService: Database polling daemon wrapper for scheduling delayed actions
- FollowUpPollingDaemon: Core polling daemon for executing due actions
- scheduled_action_manager: Database operations for scheduled follow-ups and reminders

The scheduling system is Docker-safe: uses database polling instead of in-memory
asyncio tasks, so scheduled actions survive daemon restarts.

Example usage:
    from scheduling import (
        SalesCalendar,
        SchedulingTool,
        SchedulerService,
        scheduled_action_manager,
    )

    # Initialize calendar and scheduling tool
    calendar = SalesCalendar(config_path)
    scheduling_tool = SchedulingTool(calendar)

    # Get available times
    availability = scheduling_tool.get_available_times(days=3)

    # Schedule a delayed action (Docker-safe via database polling)
    async def execute_action(action):
        # Execute the action
        pass

    scheduler = SchedulerService(execute_callback=execute_action)
    await scheduler.start()  # Starts database polling daemon
"""

import sys
from pathlib import Path

# Add scheduling skill scripts to path for intra-module imports
SCHEDULING_SCRIPTS = Path(__file__).parent
if str(SCHEDULING_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCHEDULING_SCRIPTS))

# Add telegram skill scripts to path for model imports
TELEGRAM_SCRIPTS = Path(__file__).parent.parent.parent / "telegram/scripts"
if str(TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_SCRIPTS))

from sales_calendar import SalesCalendar
from scheduling_tool import SchedulingTool
from scheduler_service import SchedulerService
from followup_polling_daemon import FollowUpPollingDaemon
import scheduled_action_manager

__all__ = [
    "SalesCalendar",
    "SchedulingTool",
    "SchedulerService",
    "FollowUpPollingDaemon",
    "scheduled_action_manager",
]
