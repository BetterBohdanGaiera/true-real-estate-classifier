"""
Calendar-Aware Scheduler - Bridge between mock slots and Google Calendar availability.

Combines SalesCalendar working hour slots with CalendarConnector busy periods
to produce filtered availability that reflects real Google Calendar events.

When a sales rep has connected their Google Calendar, this scheduler will
exclude any time slots that overlap with existing calendar events. If the
calendar is not connected, it falls back to providing all working hour slots.

Usage:
    from telegram_sales_bot.integrations.google_calendar import CalendarConnector
    from calendar_aware_scheduler import CalendarAwareScheduler

    connector = CalendarConnector()
    scheduler = CalendarAwareScheduler(
        calendar_connector=connector,
        telegram_id=123456789
    )

    # Get available slots for next 7 days
    slots = scheduler.get_available_slots(days=7)
    for slot in slots:
        print(f"{slot.date} {slot.start_time}-{slot.end_time}")
"""

from datetime import datetime, timezone, timezone, date, time, timedelta
from pathlib import Path
from typing import Optional

from rich.console import Console

# Add telegram skill scripts to path for model imports

from telegram_sales_bot.core.models import SalesSlot

# Try to import CalendarConnector (gracefully handle if not available)
try:
    from telegram_sales_bot.integrations.google_calendar import CalendarConnector
except ImportError:
    CalendarConnector = None

# Working hours in Bali time (UTC+8)
WORKING_HOURS = [10, 11, 14, 15, 16, 17, 18]
SLOT_DURATION_MINUTES = 30

console = Console()

class CalendarAwareScheduler:
    """
    Bridge between SalesCalendar mock slots and Google Calendar real availability.

    Filters mock working hour slots to exclude Google Calendar busy periods.
    When a rep has connected their Google Calendar via CalendarConnector,
    this scheduler fetches busy periods for each day and removes any
    working hour slots that overlap with those events.

    If the calendar is not connected for the given rep, all working hour
    slots are returned without filtering (fallback behavior).
    """

    def __init__(
        self,
        calendar_connector: 'CalendarConnector',
        telegram_id: int,
        working_hours: list[int] | None = None,
        timezone: str = "Asia/Makassar",
        salesperson: str = "Эксперт True Real Estate",
    ):
        """
        Initialize calendar-aware scheduler.

        Args:
            calendar_connector: CalendarConnector instance for querying
                Google Calendar busy periods.
            telegram_id: Telegram ID of the sales rep whose calendar
                should be checked.
            working_hours: List of working hour integers representing
                the start hour of each slot window. Defaults to
                [10, 11, 14, 15, 16, 17, 18] (Bali working hours).
            timezone: IANA timezone string for interpreting slot times.
                Defaults to "Asia/Makassar" (Bali, UTC+8).
            salesperson: Display name for the salesperson attributed
                to generated slots.
        """
        self.calendar_connector = calendar_connector
        self.telegram_id = telegram_id
        self.working_hours = working_hours if working_hours is not None else WORKING_HOURS
        self.timezone = timezone
        self.salesperson = salesperson

    def get_available_slots(
        self,
        from_date: Optional[date] = None,
        days: int = 7,
    ) -> list[SalesSlot]:
        """
        Get available slots filtered by Google Calendar busy periods.

        Algorithm:
            1. Generate working hour slots for each weekday in the date range
               (30-minute duration per slot).
            2. For each day, fetch Google Calendar busy slots via the
               CalendarConnector.
            3. Filter out any working hour slots that overlap with busy
               periods.
            4. Return the filtered list of SalesSlot objects.

        If the calendar is not connected for this rep, all generated
        working hour slots are returned without Google Calendar filtering.

        Args:
            from_date: Start date for slot generation. Defaults to today
                if not provided.
            days: Number of days ahead to generate and check slots for.
                Defaults to 7.

        Returns:
            List of SalesSlot objects that do not overlap with any
            Google Calendar events. Sorted by date and start time.
        """
        if from_date is None:
            from_date = date.today()

        # Check if calendar is connected for this rep
        calendar_connected = self.calendar_connector.is_connected(self.telegram_id)

        if not calendar_connected:
            console.print(
                f"[yellow]Calendar not connected for rep {self.telegram_id}, "
                f"using all working hours[/yellow]"
            )

        available_slots: list[SalesSlot] = []

        for day_offset in range(days):
            current_date = from_date + timedelta(days=day_offset)

            # Skip weekends (Monday=0, Sunday=6)
            if current_date.weekday() >= 5:
                continue

            # Generate working hour slots for this day
            day_slots = self._generate_day_slots(current_date)

            if not calendar_connected:
                # No calendar connected - return all working hour slots
                available_slots.extend(day_slots)
                continue

            # Fetch busy periods from Google Calendar for this day
            try:
                busy_slots = self.calendar_connector.get_busy_slots(
                    telegram_id=self.telegram_id,
                    date=datetime.combine(current_date, time(0, 0)),
                    timezone=self.timezone,
                )
            except Exception as e:
                console.print(
                    f"[red]Error fetching calendar for {current_date}: {e}. "
                    f"Using all working hours for this day.[/red]"
                )
                available_slots.extend(day_slots)
                continue

            # Filter out slots that overlap with busy periods
            for slot in day_slots:
                slot_start = datetime.combine(slot.date, slot.start_time)
                slot_end = datetime.combine(slot.date, slot.end_time)

                if self._is_slot_available(slot_start, slot_end, busy_slots):
                    available_slots.append(slot)

        # Sort by date and start time for consistent ordering
        available_slots.sort(key=lambda s: (s.date, s.start_time))

        return available_slots

    def _generate_day_slots(self, target_date: date) -> list[SalesSlot]:
        """
        Generate working hour slots for a single day.

        Creates one SalesSlot per working hour with 30-minute duration.
        Slot IDs follow the format "YYYYMMDD_HHMM".

        Args:
            target_date: The date to generate slots for.

        Returns:
            List of SalesSlot objects for all working hours on that date.
        """
        slots: list[SalesSlot] = []

        for hour in self.working_hours:
            slot_id = f"{target_date.strftime('%Y%m%d')}_{hour:02d}00"
            start_time = time(hour=hour, minute=0)
            end_time = time(hour=hour, minute=SLOT_DURATION_MINUTES)

            slot = SalesSlot(
                id=slot_id,
                date=target_date,
                start_time=start_time,
                end_time=end_time,
                salesperson=self.salesperson,
                is_available=True,
                booked_by=None,
            )
            slots.append(slot)

        return slots

    def _is_slot_available(
        self,
        slot_start: datetime,
        slot_end: datetime,
        busy_slots: list[tuple[datetime, datetime]],
    ) -> bool:
        """
        Check if a time slot is available (doesn't overlap with any busy slot).

        A slot overlaps with a busy period when:
            slot_start < busy_end AND slot_end > busy_start

        This covers all overlap cases: partial overlap at start, partial
        overlap at end, full containment in either direction, and exact match.

        Args:
            slot_start: Start datetime of the candidate slot.
            slot_end: End datetime of the candidate slot.
            busy_slots: List of (start, end) datetime tuples representing
                busy periods from Google Calendar.

        Returns:
            True if the slot does not overlap with any busy period,
            False if it overlaps with at least one.
        """
        for busy_start, busy_end in busy_slots:
            if slot_start < busy_end and slot_end > busy_start:
                return False
        return True
