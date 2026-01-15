"""
Scheduling Tool for Telegram Agent.

Provides methods for the LLM agent to check availability and book Zoom meetings.
Integrates SalesCalendar with Zoom API to enable scheduling capabilities.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional
import sys

# Import Zoom API functions from zoom skill
_ZOOM_SCRIPTS_PATH = Path(__file__).parent.parent.parent / "zoom" / "scripts"
sys.path.insert(0, str(_ZOOM_SCRIPTS_PATH))
from zoom_meetings import load_credentials, get_access_token, BASE_URL
import requests

from sales_calendar import SalesCalendar
from models import SalesSlot, SchedulingResult, Prospect


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
    Tool for scheduling Zoom meetings via calendar integration.

    Provides methods for the Telegram agent to:
    - Query available time slots in human-readable Russian format
    - Book Zoom meetings for confirmed slots
    - Handle errors gracefully with informative messages

    Example usage:
        calendar = SalesCalendar(Path("config/sales_slots.json"))
        tool = SchedulingTool(calendar)

        # Get availability
        availability_text = tool.get_available_times(days=3)
        print(availability_text)

        # Book meeting
        prospect = Prospect(telegram_id="@user123", name="Алексей", context="Villa inquiry")
        result = tool.book_zoom_call(
            slot_id="20260116_1400",
            prospect=prospect,
            topic="Консультация по виллам в Чангу"
        )
    """

    def __init__(self, calendar: SalesCalendar):
        """
        Initialize SchedulingTool with a SalesCalendar instance.

        Zoom credentials are loaded from ~/.zoom_credentials/credentials.json
        when needed (lazy loading for graceful degradation).

        Args:
            calendar: SalesCalendar instance managing slot availability
        """
        self.calendar = calendar
        self._zoom_credentials = None

    def _load_zoom_credentials(self) -> Optional[dict]:
        """
        Load Zoom credentials lazily.

        Returns:
            Credentials dict if available, None otherwise
        """
        if self._zoom_credentials is None:
            self._zoom_credentials = load_credentials()
        return self._zoom_credentials

    def _format_date_russian(self, target_date: date) -> str:
        """
        Format date in Russian with relative terms.

        Examples:
            - If today: "Сегодня (15 января)"
            - If tomorrow: "Завтра (16 января)"
            - Otherwise: "Пятница (17 января)"

        Args:
            target_date: The date to format

        Returns:
            Human-readable Russian date string
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
        """
        Format a single time slot for display.

        Args:
            slot: The SalesSlot to format

        Returns:
            Formatted time range string, e.g., "10:00-10:30"
        """
        start = slot.start_time.strftime("%H:%M")
        end = slot.end_time.strftime("%H:%M")
        return f"{start}-{end}"

    def get_available_times(
        self,
        preferred_date: Optional[date] = None,
        days: int = 3
    ) -> str:
        """
        Get available time slots formatted for LLM/user consumption.

        Returns a human-readable Russian text listing available slots grouped
        by date, with relative date names (today, tomorrow) where applicable.

        Args:
            preferred_date: If specified, start from this date. Defaults to today.
            days: Number of days to show slots for. Defaults to 3.

        Returns:
            Formatted string in Russian, either listing available slots or
            a message indicating no slots are available.

        Example output:
            \"\"\"
            Доступные слоты для встречи:

            **Завтра (16 января)**
            - 10:00-10:30
            - 14:00-14:30
            - 16:00-16:30

            **Пятница (17 января)**
            - 11:00-11:30
            - 15:00-15:30
            \"\"\"
        """
        # Get available slots from calendar
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

            # Sort slots by start time
            day_slots = sorted(slots_by_date[slot_date], key=lambda s: s.start_time)
            for slot in day_slots:
                time_str = self._format_time_slot(slot)
                lines.append(f"- {time_str}")

            lines.append("")  # Empty line between dates

        return "\n".join(lines).rstrip()

    def _create_zoom_meeting(
        self,
        slot: SalesSlot,
        topic: str,
        prospect_name: str
    ) -> Optional[str]:
        """
        Create a Zoom meeting using the API.

        Uses Server-to-Server OAuth to create a scheduled meeting.
        Meeting is configured for 30-minute duration in Bali timezone.

        Args:
            slot: The SalesSlot to create a meeting for
            topic: Meeting agenda/description
            prospect_name: Name of the prospect for the meeting title

        Returns:
            The Zoom join URL if successful, None if failed
        """
        # Load credentials
        creds = self._load_zoom_credentials()
        if not creds:
            return None

        # Get access token
        access_token = get_access_token(creds)
        if not access_token:
            return None

        # Prepare request headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Combine date and time to create ISO datetime
        meeting_datetime = datetime.combine(slot.date, slot.start_time)
        start_time_iso = meeting_datetime.isoformat()

        # Calculate duration in minutes
        start_dt = datetime.combine(slot.date, slot.start_time)
        end_dt = datetime.combine(slot.date, slot.end_time)
        duration_minutes = int((end_dt - start_dt).total_seconds() / 60)

        # Prepare meeting payload
        payload = {
            "topic": f"Консультация: {prospect_name}",
            "type": 2,  # Scheduled meeting
            "start_time": start_time_iso,
            "duration": duration_minutes,
            "timezone": "Asia/Makassar",  # Bali timezone (UTC+8)
            "agenda": topic,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "mute_upon_entry": True,
                "auto_recording": "none"
            }
        }

        try:
            response = requests.post(
                f"{BASE_URL}/users/me/meetings",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 201:
                meeting_data = response.json()
                return meeting_data.get("join_url")
            else:
                # Log error for debugging
                print(f"Zoom API error ({response.status_code}): {response.text}",
                      file=sys.stderr)
                return None

        except requests.RequestException as e:
            print(f"Zoom API request failed: {e}", file=sys.stderr)
            return None

    def book_zoom_call(
        self,
        slot_id: str,
        prospect: Prospect,
        topic: str = "Консультация по недвижимости на Бали"
    ) -> SchedulingResult:
        """
        Book a slot and create corresponding Zoom meeting.

        Performs the following steps:
        1. Validates the slot exists and is available
        2. Books the slot in the calendar (marks as unavailable)
        3. Creates a Zoom meeting via the API
        4. Returns SchedulingResult with Zoom URL

        If Zoom creation fails, the calendar booking is rolled back.

        Args:
            slot_id: The ID of the slot to book (format: "YYYYMMDD_HHMM")
            prospect: The Prospect booking the meeting
            topic: Meeting topic/agenda. Defaults to generic real estate consultation.

        Returns:
            SchedulingResult containing:
            - success: True if both calendar booking and Zoom creation succeeded
            - message: Confirmation message in Russian
            - slot: The booked SalesSlot
            - zoom_url: The join URL
            - error: Error message if failed

        Example:
            result = tool.book_zoom_call(
                slot_id="20260116_1400",
                prospect=prospect,
                topic="Консультация по виллам в Чангу"
            )
            if result.success:
                print(f"Booked: {result.zoom_url}")
        """
        # Step 1: Book slot in calendar
        booking_result = self.calendar.book_slot(
            slot_id=slot_id,
            prospect_id=str(prospect.telegram_id)
        )

        if not booking_result.success:
            return booking_result

        # Step 2: Get the booked slot
        booked_slot = booking_result.slot
        if not booked_slot:
            return SchedulingResult(
                success=False,
                message="Не удалось получить информацию о забронированном слоте.",
                error="Slot booking succeeded but slot data not returned"
            )

        # Step 3: Create Zoom meeting
        zoom_url = self._create_zoom_meeting(
            slot=booked_slot,
            topic=topic,
            prospect_name=prospect.name
        )

        if not zoom_url:
            # Rollback calendar booking if Zoom fails
            self.calendar.cancel_booking(slot_id)
            return SchedulingResult(
                success=False,
                message="Не удалось создать Zoom-встречу. Пожалуйста, попробуйте позже.",
                error="Zoom meeting creation failed"
            )

        # Step 4: Return success result
        formatted_date = self._format_date_russian(booked_slot.date)
        time_str = booked_slot.start_time.strftime("%H:%M")

        confirmation_message = (
            f"Отлично! Встреча назначена на {formatted_date} в {time_str}.\n\n"
            f"Ссылка на Zoom: {zoom_url}\n\n"
            f"Наш эксперт свяжется с вами в назначенное время."
        )

        return SchedulingResult(
            success=True,
            message=confirmation_message,
            slot=booked_slot,
            zoom_url=zoom_url
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

        Args:
            target_date: The date to search
            target_time: The start time to match

        Returns:
            The matching SalesSlot if found and available, None otherwise
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

    # Get the config path
    config_path = Path(__file__).parent.parent / "config" / "sales_slots.json"

    # Initialize calendar and tool
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    # Test availability formatting
    print("=== Available Times ===")
    availability = tool.get_available_times(days=3)
    print(availability)
    print()

    # Test date formatting
    print("=== Date Formatting ===")
    today = date.today()
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=5)

    print(f"Today: {tool._format_date_russian(today)}")
    print(f"Tomorrow: {tool._format_date_russian(tomorrow)}")
    print(f"Next week: {tool._format_date_russian(next_week)}")
