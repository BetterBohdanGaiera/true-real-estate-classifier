"""
Scheduling module - Sales calendar, Zoom booking, and scheduled actions.

This module provides:
- SalesCalendar: Manages sales team availability and slot booking
- SchedulingTool: Tool for the LLM agent to check availability and book meetings
- SchedulerService: APScheduler wrapper for scheduling delayed actions
- scheduled_action_manager: Database operations for scheduled follow-ups and reminders

Example usage:
    from sales_agent.scheduling import (
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

    # Schedule a delayed action
    async def execute_action(action):
        # Execute the action
        pass

    scheduler = SchedulerService(execute_callback=execute_action)
    await scheduler.start()
"""

from .sales_calendar import SalesCalendar
from .scheduling_tool import SchedulingTool
from .scheduler_service import SchedulerService
from . import scheduled_action_manager

__all__ = [
    "SalesCalendar",
    "SchedulingTool",
    "SchedulerService",
    "scheduled_action_manager",
]
