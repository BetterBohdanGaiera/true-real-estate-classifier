"""
Scheduling Tool for Telegram Agent.

Provides methods for the LLM agent to check availability and book meetings.
Integrates with Zoom API for meeting creation and Google Calendar for invitations.
Email validation with typo detection. Timezone-aware scheduling.
"""

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from sales_calendar import SalesCalendar
from models import SalesSlot, SchedulingResult, Prospect, TimeRange


# Bali timezone constant (UTC+8)
BALI_TZ = ZoneInfo("Asia/Makassar")

# Common email domain typo mappings
EMAIL_DOMAIN_TYPOS = {
    # Gmail typos
    "gmil.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.ru": None,  # Valid domain, no suggestion
    # Yahoo typos
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yhoo.com": "yahoo.com",
    "yahoo.co": "yahoo.com",
    "yahoo.con": "yahoo.com",
    # Hotmail typos
    "hotmial.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotamil.com": "hotmail.com",
    "hotmail.co": "hotmail.com",
    "hotmail.con": "hotmail.com",
    # Outlook typos
    "outloo.com": "outlook.com",
    "outlok.com": "outlook.com",
    "outloock.com": "outlook.com",
    "outlook.co": "outlook.com",
    "outlook.con": "outlook.com",
    # Mail.ru typos
    "mai.ru": "mail.ru",
    "maill.ru": "mail.ru",
    "mail.r": "mail.ru",
    "mail.ru": None,  # Valid domain
    # Yandex typos
    "yandex.r": "yandex.ru",
    "yandex.ru": None,  # Valid domain
    "yandx.ru": "yandex.ru",
}


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


def validate_email_with_suggestions(email: str) -> tuple[bool, str, Optional[str]]:
    """
    Validate email with typo detection for common domains.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message, suggested_correction)
        - is_valid: True if email passes validation
        - error_message: Error description if invalid, empty string if valid
        - suggested_correction: Suggested correct email if typo detected, None otherwise
    """
    if not email or not email.strip():
        return False, "Email address is required", None

    email = email.strip().lower()

    # Basic format validation
    if "@" not in email:
        return False, "Email must contain @ symbol", None

    parts = email.split("@")
    if len(parts) != 2:
        return False, "Invalid email format", None

    local_part, domain = parts

    if not local_part:
        return False, "Email local part cannot be empty", None

    if not domain:
        return False, "Email domain cannot be empty", None

    if "." not in domain:
        return False, "Email domain must contain a dot", None

    # Check for common domain typos
    if domain in EMAIL_DOMAIN_TYPOS:
        suggested_domain = EMAIL_DOMAIN_TYPOS[domain]
        if suggested_domain is not None:
            suggested_email = f"{local_part}@{suggested_domain}"
            return False, f"Possible typo in domain", suggested_email

    # Additional validation for suspicious patterns
    if domain.endswith(".con"):
        suggested = email[:-4] + ".com"
        return False, "Possible typo: .con instead of .com", suggested

    if domain.endswith(".co") and not domain.endswith(".co.uk"):
        # Could be .com typo but also valid domains like .co, .co.jp
        pass  # Don't flag as error

    return True, "", None


class SchedulingTool:
    """
    Tool for scheduling meetings via calendar integration.

    Integrates with Zoom API for meeting creation and Google Calendar
    for event creation with attendee invitations.
    Email validation includes typo detection for common domains.
    All times are handled in Bali timezone (UTC+8).
    """

    def __init__(
        self,
        calendar: SalesCalendar,
        zoom_service=None,
        calendar_connector=None,
        rep_telegram_id: Optional[int] = None
    ):
        """
        Initialize SchedulingTool with a SalesCalendar instance.

        Args:
            calendar: SalesCalendar instance managing slot availability
            zoom_service: Optional ZoomBookingService for creating Zoom meetings
            calendar_connector: Optional CalendarClient for Google Calendar integration
            rep_telegram_id: Optional Telegram ID of the sales rep
        """
        self.calendar = calendar
        self.zoom_service = zoom_service
        self.calendar_connector = calendar_connector
        self.rep_telegram_id = rep_telegram_id

    def _format_date_russian(self, target_date: date) -> str:
        """
        Format date in Russian with relative terms.

        Uses Bali timezone for "today" calculation.

        Examples:
            - If today: "Сегодня (15 января)"
            - If tomorrow: "Завтра (16 января)"
            - Otherwise: "Пятница (17 января)"
        """
        # Use Bali timezone for "today" calculation
        today = datetime.now(BALI_TZ).date()
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
        """Format a single time slot for display (Bali time only)."""
        start = slot.start_time.strftime("%H:%M")
        end = slot.end_time.strftime("%H:%M")
        return f"{start}-{end}"

    def _convert_to_client_timezone(
        self,
        dt: datetime,
        client_tz: str
    ) -> Optional[datetime]:
        """
        Convert a datetime to client's timezone.

        Args:
            dt: Datetime to convert (assumed to be in Bali timezone if naive)
            client_tz: Client's timezone as IANA string (e.g., "Europe/Moscow")

        Returns:
            Converted datetime in client timezone, or None if conversion fails.
        """
        try:
            client_timezone = ZoneInfo(client_tz)

            # If datetime is naive, assume it's in Bali timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BALI_TZ)

            return dt.astimezone(client_timezone)
        except (KeyError, ValueError, Exception):
            # Unknown timezone or conversion error
            return None

    def _format_dual_timezone(
        self,
        dt: datetime,
        client_tz: str
    ) -> str:
        """
        Format time in both client's timezone and Bali timezone.

        Args:
            dt: Datetime to format (assumed to be in Bali timezone if naive)
            client_tz: Client's timezone as IANA string

        Returns:
            Formatted string like "14:00 вашего времени (10:00 Бали UTC+8)"
            or just "10:00 (Бали UTC+8)" if conversion fails.
        """
        # Ensure datetime has Bali timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BALI_TZ)

        bali_time_str = dt.strftime("%H:%M")

        # Try to convert to client timezone
        client_dt = self._convert_to_client_timezone(dt, client_tz)

        if client_dt is not None:
            client_time_str = client_dt.strftime("%H:%M")
            return f"{client_time_str} вашего времени ({bali_time_str} Бали UTC+8)"
        else:
            # Fallback to Bali time only
            return f"{bali_time_str} (Бали UTC+8)"

    def _format_time_slot_dual_timezone(
        self,
        slot: SalesSlot,
        client_tz: str
    ) -> str:
        """
        Format a time slot with both client and Bali timezone.

        Args:
            slot: SalesSlot to format
            client_tz: Client's timezone as IANA string

        Returns:
            Formatted string with dual timezone display.
        """
        # Create datetime for start and end times
        start_dt = datetime.combine(slot.date, slot.start_time, tzinfo=BALI_TZ)
        end_dt = datetime.combine(slot.date, slot.end_time, tzinfo=BALI_TZ)

        bali_start = slot.start_time.strftime("%H:%M")
        bali_end = slot.end_time.strftime("%H:%M")

        # Try to convert to client timezone
        client_start = self._convert_to_client_timezone(start_dt, client_tz)
        client_end = self._convert_to_client_timezone(end_dt, client_tz)

        if client_start is not None and client_end is not None:
            client_start_str = client_start.strftime("%H:%M")
            client_end_str = client_end.strftime("%H:%M")
            return f"{client_start_str}-{client_end_str} вашего времени ({bali_start}-{bali_end} Бали UTC+8)"
        else:
            # Fallback to Bali time only
            return f"{bali_start}-{bali_end} (Бали UTC+8)"

    def _group_consecutive_slots(
        self,
        slots: list[SalesSlot]
    ) -> list[TimeRange]:
        """
        Group consecutive available slots into time ranges.

        Merges slots that are adjacent (end_time of one == start_time of next)
        into contiguous TimeRange objects. This transforms individual 30-minute
        slots into human-readable time ranges.

        Args:
            slots: List of SalesSlot objects (all should be same date for best results)

        Returns:
            List of TimeRange objects representing merged availability

        Examples:
            Slots: [10:00-10:30, 10:30-11:00, 14:00-14:30]
            Result: [TimeRange(10:00-11:00), TimeRange(14:00-14:30)]

            Slots: [10:00-10:30, 10:30-11:00, 11:00-11:30]
            Result: [TimeRange(10:00-11:30)]

            Slots: [] (empty)
            Result: []
        """
        if not slots:
            return []

        # Sort by date first, then by start_time
        sorted_slots = sorted(slots, key=lambda s: (s.date, s.start_time))

        # Group consecutive slots
        ranges = []
        current_range_start = sorted_slots[0].start_time
        current_range_end = sorted_slots[0].end_time
        current_date = sorted_slots[0].date

        for i in range(1, len(sorted_slots)):
            slot = sorted_slots[i]

            # Check if same date and consecutive (no gap)
            if slot.date == current_date and slot.start_time == current_range_end:
                # Consecutive slot - extend current range
                current_range_end = slot.end_time
            else:
                # Gap found or different date - save current range and start new one
                ranges.append(TimeRange(
                    date=current_date,
                    start_time=current_range_start,
                    end_time=current_range_end
                ))
                current_range_start = slot.start_time
                current_range_end = slot.end_time
                current_date = slot.date

        # Add final range
        ranges.append(TimeRange(
            date=current_date,
            start_time=current_range_start,
            end_time=current_range_end
        ))

        return ranges

    def _convert_time_range_to_client_tz(
        self,
        time_range: TimeRange,
        client_tz: str
    ) -> str:
        """
        Convert a TimeRange to client's timezone and format naturally.

        Args:
            time_range: TimeRange object in Bali timezone
            client_tz: Client's timezone as IANA string (e.g., "Europe/Moscow")

        Returns:
            Formatted string like "с 3:00 до 5:00" in client's timezone
        """
        # Create datetimes for start and end in Bali timezone
        start_dt = datetime.combine(
            time_range.date,
            time_range.start_time,
            tzinfo=BALI_TZ
        )
        end_dt = datetime.combine(
            time_range.date,
            time_range.end_time,
            tzinfo=BALI_TZ
        )

        # Convert to client timezone
        client_start = self._convert_to_client_timezone(start_dt, client_tz)
        client_end = self._convert_to_client_timezone(end_dt, client_tz)

        if client_start is None or client_end is None:
            # Fallback to Bali time
            return time_range.format_russian(include_gaps=False)

        # Format in Russian style: "с HH:MM до HH:MM"
        start_str = client_start.strftime("%H:%M")
        end_str = client_end.strftime("%H:%M")

        return f"с {start_str} до {end_str}"

    def _get_timezone_display_name(self, timezone_str: str) -> str:
        """
        Get a human-readable display name for a timezone.

        Args:
            timezone_str: IANA timezone string (e.g., "Europe/Moscow")

        Returns:
            Human-readable name like "Москва UTC+3" or "Варшава UTC+1"
        """
        # Common timezone display names for Russian speakers
        timezone_names = {
            "Europe/Moscow": "Москва",
            "Europe/Warsaw": "Варшава",
            "Europe/Kyiv": "Киев",
            "Europe/Minsk": "Минск",
            "Europe/Berlin": "Берлин",
            "Europe/Paris": "Париж",
            "Europe/London": "Лондон",
            "Asia/Dubai": "Дубай",
            "Asia/Bangkok": "Бангкок",
            "Asia/Singapore": "Сингапур",
            "Asia/Tokyo": "Токио",
            "America/New_York": "Нью-Йорк",
            "America/Los_Angeles": "Лос-Анджелес",
        }

        try:
            tz = ZoneInfo(timezone_str)
            now = datetime.now(tz)
            offset = now.utcoffset()
            if offset:
                total_seconds = offset.total_seconds()
                hours = int(total_seconds // 3600)
                sign = "+" if hours >= 0 else ""
                offset_str = f"UTC{sign}{hours}"
            else:
                offset_str = "UTC"

            # Get display name or extract city from IANA string
            if timezone_str in timezone_names:
                city_name = timezone_names[timezone_str]
            else:
                # Extract city from "Region/City" format
                city_name = timezone_str.split("/")[-1].replace("_", " ")

            return f"{city_name} {offset_str}"
        except (KeyError, ValueError):
            return timezone_str

    def _filter_slots_by_client_hours(
        self,
        slots: list[SalesSlot],
        client_timezone: str,
        min_hour: int = 8,
        max_hour: int = 22
    ) -> list[SalesSlot]:
        """
        Filter out slots that fall outside reasonable hours in client's timezone.

        Nobody wants to schedule a meeting at 3am their time. This method filters
        out slots that would be too early or too late in the client's local time.

        Args:
            slots: List of SalesSlot objects (in Bali timezone)
            client_timezone: Client's timezone (e.g., "Europe/Warsaw")
            min_hour: Minimum acceptable hour in client timezone (default: 8 = 8am)
            max_hour: Maximum acceptable hour in client timezone (default: 22 = 10pm)

        Returns:
            Filtered list of slots that fall within acceptable client hours

        Example:
            If min_hour=8 and client is in Warsaw (UTC+1) while Bali is UTC+8:
            - Slot at 10:00 Bali = 03:00 Warsaw → EXCLUDED (before 8am)
            - Slot at 15:00 Bali = 08:00 Warsaw → INCLUDED (exactly 8am)
            - Slot at 16:00 Bali = 09:00 Warsaw → INCLUDED
        """
        if not slots or not client_timezone:
            return slots

        try:
            client_tz = ZoneInfo(client_timezone)
        except (KeyError, ValueError):
            # Invalid timezone, return all slots
            return slots

        filtered_slots = []
        for slot in slots:
            # Create datetime in Bali timezone
            slot_dt_bali = datetime.combine(slot.date, slot.start_time, tzinfo=BALI_TZ)

            # Convert to client timezone
            slot_dt_client = slot_dt_bali.astimezone(client_tz)
            client_hour = slot_dt_client.hour

            # Check if within acceptable hours
            if min_hour <= client_hour < max_hour:
                filtered_slots.append(slot)

        return filtered_slots

    def _format_time_ranges_natural(
        self,
        ranges: list[TimeRange],
        client_timezone: Optional[str] = None
    ) -> str:
        """
        Format time ranges using natural language.

        Follows tone-of-voice guidelines for natural time offering.
        Shows availability in Bali timezone first, then optionally
        in client's timezone. Ends with a natural question to guide
        the prospect toward making a choice.

        Args:
            ranges: List of TimeRange objects to format
            client_timezone: Optional client timezone for dual-timezone display

        Returns:
            Formatted Russian text with natural phrasing

        Example output (without client timezone):
            "Свободное время на этой неделе по Бали:
            - Завтра: с 10:00 до 12:00, с 14:00 до 16:00
            - Понедельник: с 16:00 до 19:00

            Какое время Вам удобнее - утро или вечер?"

        Example output (with client timezone):
            "Свободное время на этой неделе по Бали:
            - Завтра: с 10:00 до 12:00, с 14:00 до 16:00
            - Понедельник: с 16:00 до 19:00

            По вашему времени (Москва UTC+3) это:
            - Завтра: с 5:00 до 7:00, с 9:00 до 11:00
            - Понедельник: с 11:00 до 14:00

            Какое время Вам удобнее - утро или вечер?"
        """
        if not ranges:
            return "К сожалению, нет свободных слотов."

        # Group ranges by date
        ranges_by_date: dict[date, list[TimeRange]] = {}
        for r in ranges:
            if r.date not in ranges_by_date:
                ranges_by_date[r.date] = []
            ranges_by_date[r.date].append(r)

        # Build output - Bali timezone section
        lines = ["Свободное время на этой неделе по Бали:"]

        for slot_date in sorted(ranges_by_date.keys()):
            date_header = self._format_date_russian(slot_date)
            day_ranges = ranges_by_date[slot_date]

            # Format ranges for this day: "с 10:00 до 12:00, с 14:00 до 16:00"
            range_strs = [r.format_russian(include_gaps=False) for r in day_ranges]
            ranges_text = ", ".join(range_strs)

            lines.append(f"- {date_header}: {ranges_text}")

        # Add client timezone section if provided
        if client_timezone:
            tz_display_name = self._get_timezone_display_name(client_timezone)
            lines.append("")
            lines.append(f"По вашему времени ({tz_display_name}) это:")

            for slot_date in sorted(ranges_by_date.keys()):
                date_header = self._format_date_russian(slot_date)
                day_ranges = ranges_by_date[slot_date]

                # Convert each range to client timezone
                converted_strs = []
                for r in day_ranges:
                    converted = self._convert_time_range_to_client_tz(r, client_timezone)
                    converted_strs.append(converted)

                ranges_text = ", ".join(converted_strs)
                lines.append(f"- {date_header}: {ranges_text}")

        # Add natural closing question following tone-of-voice guidelines
        lines.append("")
        lines.append("Какое время Вам удобнее - утро или вечер?")

        return "\n".join(lines)

    def get_available_times(
        self,
        preferred_date: Optional[date] = None,
        days: int = 3,
        client_timezone: Optional[str] = None,
        use_ranges: bool = True
    ) -> str:
        """
        Get available time slots formatted for user consumption.

        Returns human-readable Russian text listing available slots.
        When use_ranges=True (default), displays merged time ranges for natural
        communication. When use_ranges=False, displays individual 30-min slots
        (old behavior for backward compatibility).

        When client_timezone is provided, times are shown in both
        client's local time and Bali time.

        Args:
            preferred_date: Start date for availability check (default: today in Bali)
            days: Number of days to check
            client_timezone: Optional client timezone for dual-timezone display
            use_ranges: Whether to merge slots into ranges (default: True)

        Returns:
            Formatted string with available slots or ranges.
        """
        # Use Bali timezone for "today" calculation
        bali_today = datetime.now(BALI_TZ).date()
        from_date = preferred_date or bali_today

        available_slots = self.calendar.get_available_slots(
            from_date=from_date,
            days=days
        )

        # Filter out past slots for today using Bali timezone
        now_bali = datetime.now(BALI_TZ)
        if from_date == bali_today:
            available_slots = [
                slot for slot in available_slots
                if slot.date > bali_today or
                (slot.date == bali_today and slot.start_time > now_bali.time())
            ]

        # Filter out slots that are too early/late in client's timezone
        # Nobody wants a meeting at 3am their time!
        if client_timezone:
            available_slots = self._filter_slots_by_client_hours(
                available_slots,
                client_timezone,
                min_hour=8,   # No earlier than 8am client time
                max_hour=22   # No later than 10pm client time
            )

        if not available_slots:
            return f"К сожалению, нет свободных слотов в ближайшие {days} дней."

        # NEW: Use range-based formatting for natural communication
        if use_ranges:
            # Group slots by date first
            slots_by_date: dict[date, list[SalesSlot]] = {}
            for slot in available_slots:
                if slot.date not in slots_by_date:
                    slots_by_date[slot.date] = []
                slots_by_date[slot.date].append(slot)

            # Merge consecutive slots into ranges for each date
            all_ranges = []
            for slot_date in sorted(slots_by_date.keys()):
                day_slots = slots_by_date[slot_date]
                day_ranges = self._group_consecutive_slots(day_slots)
                all_ranges.extend(day_ranges)

            # Format naturally using tone-of-voice guidelines
            return self._format_time_ranges_natural(all_ranges, client_timezone)

        # OLD: Keep existing individual slot display for backward compatibility
        # Group slots by date
        slots_by_date_old: dict[date, list[SalesSlot]] = {}
        for slot in available_slots:
            if slot.date not in slots_by_date_old:
                slots_by_date_old[slot.date] = []
            slots_by_date_old[slot.date].append(slot)

        # Sort dates and build output
        sorted_dates = sorted(slots_by_date_old.keys())

        # Header message varies based on timezone awareness
        if client_timezone:
            lines = [
                "Доступные слоты для встречи:",
                "(время указано в вашем часовом поясе и по Бали UTC+8)",
                ""
            ]
        else:
            lines = [
                "Доступные слоты для встречи (время по Бали UTC+8):",
                ""
            ]

        for slot_date in sorted_dates:
            date_header = self._format_date_russian(slot_date)
            lines.append(f"**{date_header}**")

            day_slots = sorted(slots_by_date_old[slot_date], key=lambda s: s.start_time)
            for slot in day_slots:
                if client_timezone:
                    time_str = self._format_time_slot_dual_timezone(slot, client_timezone)
                else:
                    time_str = self._format_time_slot(slot)
                lines.append(f"- {time_str}")

            lines.append("")

        return "\n".join(lines).rstrip()

    def book_meeting(
        self,
        slot_id: str,
        prospect: Prospect,
        client_email: str,
        topic: str = "Консультация по недвижимости на Бали",
        client_timezone: Optional[str] = None
    ) -> SchedulingResult:
        """
        Book a slot for a meeting with Zoom and Google Calendar integration.

        Creates actual Zoom meeting when credentials available.
        Creates Google Calendar event with attendee invitation.
        Validates email with typo detection.

        Args:
            slot_id: The ID of the slot to book (format: "YYYYMMDD_HHMM")
            prospect: The Prospect booking the meeting
            client_email: Client's email address - REQUIRED for invite
            topic: Meeting topic/agenda
            client_timezone: Optional client timezone for time display

        Returns:
            SchedulingResult with success/failure, confirmation message, and zoom_url
        """
        # STRICT EMAIL VALIDATION - NO EMAIL = NO BOOKING
        if not client_email or not client_email.strip():
            return SchedulingResult(
                success=False,
                message="Для записи на встречу нужен email. На какой адрес отправить приглашение?",
                error="Email is required for booking"
            )

        # Validate email with typo detection
        client_email = client_email.strip()
        is_valid, error_msg, suggestion = validate_email_with_suggestions(client_email)

        if not is_valid:
            if suggestion:
                # Typo detected, suggest correction
                return SchedulingResult(
                    success=False,
                    message=f"Вы имели в виду {suggestion}? Пожалуйста, подтвердите email адрес.",
                    error=f"Email validation failed: {error_msg}. Suggested: {suggestion}"
                )
            else:
                # Invalid email format
                return SchedulingResult(
                    success=False,
                    message="Пожалуйста, укажите корректный email адрес.",
                    error=f"Invalid email format: {error_msg}"
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

        # Create datetime for meeting
        meeting_start = datetime.combine(
            booked_slot.date,
            booked_slot.start_time,
            tzinfo=BALI_TZ
        )
        meeting_end = datetime.combine(
            booked_slot.date,
            booked_slot.end_time,
            tzinfo=BALI_TZ
        )

        # Try to create Zoom meeting
        zoom_url = None
        if self.zoom_service and hasattr(self.zoom_service, 'create_meeting'):
            try:
                if hasattr(self.zoom_service, 'enabled') and self.zoom_service.enabled:
                    zoom_url = self.zoom_service.create_meeting(
                        topic=f"{topic} - {prospect.name}",
                        start_time=meeting_start,
                        duration=30,
                        invitee_email=client_email,
                        invitee_name=prospect.name,
                        timezone="Asia/Makassar"
                    )
            except Exception as e:
                # Log error but continue with booking
                print(f"Failed to create Zoom meeting: {e}")
                zoom_url = None

        # Try to create Google Calendar event
        calendar_created = False
        if self.calendar_connector and zoom_url:
            try:
                # Format times for Google Calendar (ISO 8601)
                start_iso = meeting_start.strftime("%Y-%m-%dT%H:%M:%S")
                end_iso = meeting_end.strftime("%Y-%m-%dT%H:%M:%S")

                description = (
                    f"Консультация по недвижимости на Бали\n\n"
                    f"Клиент: {prospect.name}\n"
                    f"Email: {client_email}\n\n"
                    f"Zoom: {zoom_url}"
                )

                self.calendar_connector.create_event(
                    summary=f"Консультация: {prospect.name}",
                    start=start_iso,
                    end=end_iso,
                    description=description,
                    location=zoom_url,
                    attendees=[client_email],
                    timezone="Asia/Makassar"
                )
                calendar_created = True
            except Exception as e:
                # Log error but continue
                print(f"Failed to create Google Calendar event: {e}")
                calendar_created = False

        # Format confirmation message based on what was actually created
        formatted_date = self._format_date_russian(booked_slot.date)
        time_str = booked_slot.start_time.strftime("%H:%M")

        # Add client timezone display if available
        if client_timezone:
            client_time = self._format_dual_timezone(meeting_start, client_timezone)
            time_display = client_time
        else:
            time_display = f"{time_str} (Бали UTC+8)"

        if zoom_url and calendar_created:
            # Full integration success - Zoom meeting created and calendar invite sent
            confirmation_message = (
                f"Отлично! Встреча назначена на {formatted_date} в {time_display}.\n\n"
                f"Ссылка на Zoom:\n{zoom_url}\n\n"
                f"Приглашение отправлено на {client_email}."
            )
        elif zoom_url and not calendar_created:
            # Zoom created but calendar failed
            confirmation_message = (
                f"Отлично! Встреча назначена на {formatted_date} в {time_display}.\n\n"
                f"Ссылка на Zoom:\n{zoom_url}\n\n"
                f"Сохраните ссылку - приглашение на {client_email} будет отправлено отдельно."
            )
        else:
            # No Zoom integration - fallback message
            confirmation_message = (
                f"Отлично! Встреча назначена на {formatted_date} в {time_display}.\n\n"
                f"Ссылка на Zoom будет отправлена на {client_email} за день до встречи.\n\n"
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
    tool = SchedulingTool(calendar)

    print("=== Available Times (Bali timezone only) ===")
    availability = tool.get_available_times(days=3)
    print(availability)
    print()

    print("=== Available Times (with Moscow timezone) ===")
    availability_tz = tool.get_available_times(days=3, client_timezone="Europe/Moscow")
    print(availability_tz)
    print()

    print("=== Test Email Validation ===")
    test_emails = [
        "test@gmail.com",     # Valid
        "test@gmil.com",      # Typo
        "test@gmai.com",      # Typo
        "test@hotmial.com",   # Typo
        "test@yaho.com",      # Typo
        "invalid-email",      # Invalid
        "",                   # Empty
    ]
    for email in test_emails:
        valid, error, suggestion = validate_email_with_suggestions(email)
        status = "VALID" if valid else "INVALID"
        sugg_str = f" -> suggested: {suggestion}" if suggestion else ""
        print(f"  {email}: {status}{sugg_str}")
    print()

    print("=== Test Booking WITHOUT Email ===")
    prospect = Prospect(telegram_id="test", name="Тест", context="test")
    result = tool.book_meeting("20260116_1400", prospect, "")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print()

    print("=== Test Booking WITH Typo Email ===")
    result = tool.book_meeting("20260116_1400", prospect, "test@gmil.com")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print()

    print("=== Test Booking WITH Valid Email ===")
    slots = calendar.get_available_slots()
    if slots:
        result = tool.book_meeting(slots[0].id, prospect, "test@example.com")
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Zoom URL: {result.zoom_url}")
