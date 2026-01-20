"""
Scheduling Tool for Telegram Agent.

Provides methods for the LLM agent to check availability and book meetings.
Supports both mock mode (no Zoom) and real Zoom meeting creation.
Email is REQUIRED for booking - no email = no booking.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from .sales_calendar import SalesCalendar
from sales_agent.crm.models import SalesSlot, SchedulingResult, Prospect

# Import ZoomBookingService (optional - gracefully handle if not available)
try:
    from sales_agent.zoom import ZoomBookingService
except ImportError:
    ZoomBookingService = None


# Russian month names for date formatting
RUSSIAN_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря"
}

# Russian weekday names
RUSSIAN_WEEKDAYS = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}


class SchedulingTool:
    """
    Tool for scheduling meetings via calendar integration.

    Supports both mock mode (no Zoom) and real Zoom meeting creation.
    Email is REQUIRED for booking - no email = no booking.
    """

    def __init__(
        self,
        calendar: SalesCalendar,
        zoom_service: Optional['ZoomBookingService'] = None
    ):
        """
        Initialize SchedulingTool with a SalesCalendar instance.

        Args:
            calendar: SalesCalendar instance managing slot availability
            zoom_service: Optional ZoomBookingService for real meeting creation.
                         If None, operates in mock mode (no actual Zoom meetings).
        """
        self.calendar = calendar
        self.zoom_service = zoom_service

        # Log mode
        if self.zoom_service and self.zoom_service.enabled:
            from rich.console import Console
            Console().print("[green]SchedulingTool: Zoom integration ENABLED[/green]")
        else:
            from rich.console import Console
            Console().print("[yellow]SchedulingTool: Mock mode (no Zoom)[/yellow]")

    def _format_date_russian(self, target_date: date) -> str:
        """
        Format date in Russian with relative terms.

        Examples:
            - If today: "Сегодня (15 января)"
            - If tomorrow: "Завтра (16 января)"
            - Otherwise: "Пятница (17 января)"
        """
        today = date.today()
        day_num = target_date.day
        month_name = RUSSIAN_MONTHS[target_date.month]

        if target_date == today:
            return f"Сегодня ({day_num} {month_name})"
        elif target_date == today + timedelta(days=1):
            return f"Завтра ({day_num} {month_name})"
        else:
            weekday_name = RUSSIAN_WEEKDAYS[target_date.weekday()]
            return f"{weekday_name} ({day_num} {month_name})"

    def _format_time_slot(self, slot: SalesSlot) -> str:
        """Format a single time slot for display."""
        start = slot.start_time.strftime("%H:%M")
        end = slot.end_time.strftime("%H:%M")
        return f"{start}-{end}"

    def get_available_times(
        self,
        preferred_date: Optional[date] = None,
        days: int = 3
    ) -> str:
        """
        Get available time slots formatted for user consumption.

        Returns human-readable Russian text listing available slots.
        """
        from_date = preferred_date or date.today()
        available_slots = self.calendar.get_available_slots(
            from_date=from_date,
            days=days
        )

        # Filter out past slots for today
        now = datetime.now()
        if from_date == date.today():
            available_slots = [
                slot for slot in available_slots
                if slot.date > date.today() or
                (slot.date == date.today() and slot.start_time > now.time())
            ]

        if not available_slots:
            return f"К сожалению, нет свободных слотов в ближайшие {days} дней."

        # Group slots by date
        slots_by_date: dict[date, list[SalesSlot]] = {}
        for slot in available_slots:
            if slot.date not in slots_by_date:
                slots_by_date[slot.date] = []
            slots_by_date[slot.date].append(slot)

        # Sort dates and build output
        sorted_dates = sorted(slots_by_date.keys())
        lines = ["Доступные слоты для встречи:", ""]

        for slot_date in sorted_dates:
            date_header = self._format_date_russian(slot_date)
            lines.append(f"**{date_header}**")

            day_slots = sorted(slots_by_date[slot_date], key=lambda s: s.start_time)
            for slot in day_slots:
                time_str = self._format_time_slot(slot)
                lines.append(f"- {time_str}")

            lines.append("")

        return "\n".join(lines).rstrip()

    def book_meeting(
        self,
        slot_id: str,
        prospect: Prospect,
        client_email: str,
        topic: str = "Консультация по недвижимости на Бали"
    ) -> SchedulingResult:
        """
        Book a slot for a meeting.

        Creates a real Zoom meeting if zoom_service is provided and enabled,
        otherwise operates in mock mode (no actual Zoom meeting).

        IMPORTANT: client_email is REQUIRED. Without email, booking will fail.

        Args:
            slot_id: The ID of the slot to book (format: "YYYYMMDD_HHMM")
            prospect: The Prospect booking the meeting
            client_email: Client's email address - REQUIRED for invite
            topic: Meeting topic/agenda

        Returns:
            SchedulingResult with success/failure and confirmation message
        """
        # STRICT EMAIL VALIDATION - NO EMAIL = NO BOOKING
        if not client_email or not client_email.strip():
            return SchedulingResult(
                success=False,
                message="Для записи на встречу нужен email. На какой адрес отправить приглашение?",
                error="Email is required for booking"
            )

        # Basic email format validation
        client_email = client_email.strip()
        if "@" not in client_email or "." not in client_email:
            return SchedulingResult(
                success=False,
                message="Пожалуйста, укажите корректный email адрес.",
                error="Invalid email format"
            )

        # Book slot in calendar
        booking_result = self.calendar.book_slot(
            slot_id=slot_id,
            prospect_id=str(prospect.telegram_id)
        )

        if not booking_result.success:
            return booking_result

        booked_slot = booking_result.slot
        if not booked_slot:
            return SchedulingResult(
                success=False,
                message="Не удалось получить информацию о слоте.",
                error="Slot booking succeeded but slot data not returned"
            )

        # Format confirmation message
        formatted_date = self._format_date_russian(booked_slot.date)
        time_str = booked_slot.start_time.strftime("%H:%M")

        # Create Zoom meeting if service is available
        zoom_url = None
        if self.zoom_service and self.zoom_service.enabled:
            from datetime import datetime as dt
            meeting_time = dt.combine(booked_slot.date, booked_slot.start_time)
            zoom_url = self.zoom_service.create_meeting(
                topic=topic,
                start_time=meeting_time,
                duration=30,
                invitee_email=client_email,
                invitee_name=prospect.name
            )
            if zoom_url:
                from rich.console import Console
                Console().print(f"[green]Created Zoom meeting: {zoom_url}[/green]")

        # Format confirmation message based on whether we have a real Zoom URL
        if zoom_url:
            confirmation_message = (
                f"Отлично! Встреча назначена на {formatted_date} в {time_str}.\n\n"
                f"Ссылка на Zoom: {zoom_url}\n\n"
                f"Приглашение также отправлено на {client_email}.\n"
                f"Наш эксперт свяжется с вами в назначенное время."
            )
        else:
            confirmation_message = (
                f"Отлично! Встреча назначена на {formatted_date} в {time_str}.\n\n"
                f"Ссылка на Zoom будет отправлена на {client_email} за день до встречи.\n\n"
                f"Наш эксперт свяжется с вами в назначенное время."
            )

        return SchedulingResult(
            success=True,
            message=confirmation_message,
            slot=booked_slot,
            zoom_url=zoom_url  # Now contains actual URL if Zoom service is enabled
        )

    def get_slot_by_time(
        self,
        target_date: date,
        target_time: time
    ) -> Optional[SalesSlot]:
        """
        Find a slot by date and time.

        Useful when the user specifies a time like "завтра в 14:00"
        and you need to find the corresponding slot ID.
        """
        available_slots = self.calendar.get_available_slots(
            from_date=target_date,
            days=1
        )

        for slot in available_slots:
            if slot.date == target_date and slot.start_time == target_time:
                return slot

        return None


# Simple test
if __name__ == "__main__":
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "config" / "sales_slots.json"

    calendar = SalesCalendar(config_path)

    # Try to initialize with Zoom service if available
    zoom_service = None
    if ZoomBookingService:
        zoom_service = ZoomBookingService()
        if not zoom_service.enabled:
            zoom_service = None

    tool = SchedulingTool(calendar, zoom_service=zoom_service)

    print("=== Available Times ===")
    availability = tool.get_available_times(days=3)
    print(availability)
    print()

    print("=== Test Booking WITHOUT Email ===")
    prospect = Prospect(telegram_id="test", name="Тест", context="test")
    result = tool.book_meeting("20260116_1400", prospect, "")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print()

    print("=== Test Booking WITH Email ===")
    slots = calendar.get_available_slots()
    if slots:
        result = tool.book_meeting(slots[0].id, prospect, "test@example.com")
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        if result.zoom_url:
            print(f"Zoom URL: {result.zoom_url}")
