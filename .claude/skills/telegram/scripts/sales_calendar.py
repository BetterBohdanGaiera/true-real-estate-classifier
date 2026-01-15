"""
Sales Calendar Manager for Telegram Agent.

Manages sales team availability and slot booking with mock slot generation.
Provides available time slots and handles bookings with JSON persistence.
"""
import json
import random
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Optional

from models import SalesSlot, SchedulingResult


# Working hours in Bali time (UTC+8)
WORKING_HOURS = [10, 11, 14, 15, 16, 17, 18]  # Hours only
SLOT_DURATION_MINUTES = 30
DEFAULT_DAYS_AHEAD = 7
AVAILABILITY_PROBABILITY = 0.7  # 70% chance a slot is available


class SalesCalendar:
    """Manages sales team availability and slot booking."""

    def __init__(self, config_path: Path):
        """
        Initialize calendar with config file path.

        Config contains: working hours, timezone, salesperson name, etc.
        Loads existing slots from JSON or generates new ones.

        Args:
            config_path: Path to the sales_slots.json configuration file.
        """
        self.config_path = Path(config_path)
        self.data_path = self.config_path.parent / "sales_slots_data.json"
        self._config: dict = {}
        self._slots: list[SalesSlot] = []

        self._load_config()
        self._load_slots()
        self.refresh_slots()

    def _load_config(self) -> dict:
        """
        Load calendar configuration from JSON.

        Returns:
            Configuration dictionary with calendar settings.
        """
        if not self.config_path.exists():
            # Create default config
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config = self._get_default_config()
            self._save_config()
        else:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)

        return self._config

    def _get_default_config(self) -> dict:
        """
        Get default configuration values.

        Returns:
            Default configuration dictionary.
        """
        return {
            "salesperson": "Эксперт True Real Estate",
            "timezone": "Asia/Makassar",
            "working_hours": {"start": "10:00", "end": "19:00"},
            "slot_duration_minutes": 30,
            "break_between_slots_minutes": 15,
            "days_ahead": 7,
            "blocked_dates": [],
            "pre_booked": []
        }

    def _save_config(self) -> None:
        """Save configuration to JSON file."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def _load_slots(self) -> list[SalesSlot]:
        """
        Load slots from JSON file if exists.

        Returns:
            List of SalesSlot objects loaded from persistence.
        """
        if not self.data_path.exists():
            self._slots = []
            return self._slots

        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._slots = []
            for slot_data in data.get("slots", []):
                slot = SalesSlot(
                    id=slot_data["id"],
                    date=date.fromisoformat(slot_data["date"]),
                    start_time=time.fromisoformat(slot_data["start_time"]),
                    end_time=time.fromisoformat(slot_data["end_time"]),
                    salesperson=slot_data.get("salesperson", self._config.get("salesperson", "Эксперт True Real Estate")),
                    is_available=slot_data.get("is_available", True),
                    booked_by=slot_data.get("booked_by")
                )
                self._slots.append(slot)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Handle corrupted data file gracefully
            print(f"Warning: Could not load slots data: {e}. Generating fresh slots.")
            self._slots = []

        return self._slots

    def _save_slots(self) -> None:
        """Save current slots to JSON file."""
        data = {
            "last_generated": datetime.now().isoformat(),
            "slots": [
                {
                    "id": slot.id,
                    "date": slot.date.isoformat(),
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "salesperson": slot.salesperson,
                    "is_available": slot.is_available,
                    "booked_by": slot.booked_by
                }
                for slot in self._slots
            ]
        }

        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def generate_mock_slots(self, days_ahead: int = 7) -> list[SalesSlot]:
        """
        Generate mock availability slots for next N days.

        Rules:
        - Weekdays only (Monday-Friday)
        - Hours: 10:00, 11:00, 14:00, 15:00, 16:00, 17:00, 18:00 UTC+8 (Bali time)
        - Duration: 30 minutes each
        - Random availability: 70% available, 30% pre-booked
        - Slot ID format: "YYYYMMDD_HHMM" (e.g., "20260115_1400")

        Args:
            days_ahead: Number of days ahead to generate slots for.

        Returns:
            List of generated SalesSlot objects.
        """
        salesperson = self._config.get("salesperson", "Эксперт True Real Estate")
        blocked_dates = self._config.get("blocked_dates", [])
        blocked_dates_set = {date.fromisoformat(d) if isinstance(d, str) else d for d in blocked_dates}

        generated_slots: list[SalesSlot] = []
        today = date.today()

        for day_offset in range(days_ahead):
            current_date = today + timedelta(days=day_offset)

            # Skip weekends (0=Monday, 6=Sunday)
            if current_date.weekday() >= 5:
                continue

            # Skip blocked dates
            if current_date in blocked_dates_set:
                continue

            for hour in WORKING_HOURS:
                # Create slot ID in format YYYYMMDD_HHMM
                slot_id = f"{current_date.strftime('%Y%m%d')}_{hour:02d}00"

                # Calculate end time (30 minutes after start)
                start_time = time(hour=hour, minute=0)
                end_time = time(hour=hour, minute=SLOT_DURATION_MINUTES)

                # Random availability: 70% chance available, 30% pre-booked
                is_available = random.random() < AVAILABILITY_PROBABILITY
                booked_by = None if is_available else "mock_prospect_123"

                slot = SalesSlot(
                    id=slot_id,
                    date=current_date,
                    start_time=start_time,
                    end_time=end_time,
                    salesperson=salesperson,
                    is_available=is_available,
                    booked_by=booked_by
                )
                generated_slots.append(slot)

        return generated_slots

    def get_available_slots(
        self,
        from_date: Optional[date] = None,
        days: int = 7
    ) -> list[SalesSlot]:
        """
        Get all available (not booked) slots starting from date.

        If from_date is None, start from today.
        Returns only slots where is_available=True and booked_by=None.

        Args:
            from_date: Start date for filtering slots. Defaults to today.
            days: Number of days to include in the result.

        Returns:
            List of available SalesSlot objects within the specified range.
        """
        if from_date is None:
            from_date = date.today()

        end_date = from_date + timedelta(days=days)

        available_slots = [
            slot for slot in self._slots
            if slot.is_available
            and slot.booked_by is None
            and from_date <= slot.date < end_date
        ]

        # Sort by date and time
        available_slots.sort(key=lambda s: (s.date, s.start_time))

        return available_slots

    def book_slot(self, slot_id: str, prospect_id: str) -> SchedulingResult:
        """
        Book a slot for a prospect.

        Args:
            slot_id: The ID of the slot to book (format: "YYYYMMDD_HHMM").
            prospect_id: The prospect's telegram_id to associate with the booking.

        Returns:
            SchedulingResult with:
            - success: bool indicating if booking succeeded
            - message: Human-readable result message
            - slot: The booked SalesSlot if successful
            - error: Error description if booking failed
        """
        slot = self.get_slot_by_id(slot_id)

        if slot is None:
            return SchedulingResult(
                success=False,
                message="Слот не найден.",
                slot=None,
                error=f"Slot with ID '{slot_id}' not found."
            )

        if not slot.is_available:
            return SchedulingResult(
                success=False,
                message="Этот слот уже занят. Пожалуйста, выберите другое время.",
                slot=slot,
                error=f"Slot '{slot_id}' is already booked by {slot.booked_by}."
            )

        if slot.booked_by is not None:
            return SchedulingResult(
                success=False,
                message="Этот слот уже забронирован.",
                slot=slot,
                error=f"Slot '{slot_id}' is already booked."
            )

        # Book the slot
        slot.is_available = False
        slot.booked_by = prospect_id

        # Update the slot in our internal list
        for i, s in enumerate(self._slots):
            if s.id == slot_id:
                self._slots[i] = slot
                break

        self._save_slots()

        # Format date and time for message
        formatted_date = slot.date.strftime("%d.%m.%Y")
        formatted_time = slot.start_time.strftime("%H:%M")

        return SchedulingResult(
            success=True,
            message=f"Отлично! Звонок назначен на {formatted_date} в {formatted_time} (время Бали, UTC+8).",
            slot=slot,
            error=None
        )

    def cancel_booking(self, slot_id: str) -> SchedulingResult:
        """
        Cancel a booking and make slot available again.

        Args:
            slot_id: The ID of the slot to cancel.

        Returns:
            SchedulingResult indicating success or failure.
        """
        slot = self.get_slot_by_id(slot_id)

        if slot is None:
            return SchedulingResult(
                success=False,
                message="Слот не найден.",
                slot=None,
                error=f"Slot with ID '{slot_id}' not found."
            )

        if slot.is_available and slot.booked_by is None:
            return SchedulingResult(
                success=False,
                message="Этот слот не был забронирован.",
                slot=slot,
                error=f"Slot '{slot_id}' was not booked."
            )

        # Cancel the booking
        previous_booker = slot.booked_by
        slot.is_available = True
        slot.booked_by = None

        # Update the slot in our internal list
        for i, s in enumerate(self._slots):
            if s.id == slot_id:
                self._slots[i] = slot
                break

        self._save_slots()

        return SchedulingResult(
            success=True,
            message="Бронирование отменено. Слот снова доступен.",
            slot=slot,
            error=None
        )

    def get_slot_by_id(self, slot_id: str) -> Optional[SalesSlot]:
        """
        Retrieve a specific slot by ID.

        Args:
            slot_id: The slot ID to search for.

        Returns:
            The SalesSlot if found, None otherwise.
        """
        for slot in self._slots:
            if slot.id == slot_id:
                return slot
        return None

    def refresh_slots(self) -> None:
        """
        Refresh slots - remove past slots and generate new ones.

        Maintains a rolling 7-day window.
        Call this periodically or on calendar access.
        """
        today = date.today()
        days_ahead = self._config.get("days_ahead", DEFAULT_DAYS_AHEAD)

        # Check if we need to refresh
        # Keep slots that are still in the future and preserve bookings
        future_slots = [s for s in self._slots if s.date >= today]

        # Check if we have enough future slots
        end_date = today + timedelta(days=days_ahead)
        existing_dates = {s.date for s in future_slots}

        # Check if all days in our window are covered
        needs_generation = False
        for day_offset in range(days_ahead):
            check_date = today + timedelta(days=day_offset)
            if check_date.weekday() < 5 and check_date not in existing_dates:
                needs_generation = True
                break

        if not future_slots or needs_generation:
            # Preserve any booked slots
            booked_slots = [s for s in future_slots if not s.is_available or s.booked_by is not None]

            # Generate new slots
            new_slots = self.generate_mock_slots(days_ahead)

            # Merge: keep booked slots, add new available slots for missing dates/times
            booked_ids = {s.id for s in booked_slots}
            merged_slots = booked_slots.copy()

            for new_slot in new_slots:
                if new_slot.id not in booked_ids:
                    merged_slots.append(new_slot)

            self._slots = merged_slots
            self._save_slots()
        else:
            # Just update to remove past slots
            self._slots = future_slots
            self._save_slots()

    def get_slots_by_date(self, target_date: date) -> list[SalesSlot]:
        """
        Get all slots for a specific date.

        Args:
            target_date: The date to get slots for.

        Returns:
            List of SalesSlot objects for that date.
        """
        return [s for s in self._slots if s.date == target_date]

    def get_booked_slots(self, prospect_id: Optional[str] = None) -> list[SalesSlot]:
        """
        Get all booked slots, optionally filtered by prospect.

        Args:
            prospect_id: If provided, only return slots booked by this prospect.

        Returns:
            List of booked SalesSlot objects.
        """
        if prospect_id:
            return [s for s in self._slots if s.booked_by == prospect_id]
        return [s for s in self._slots if not s.is_available or s.booked_by is not None]

    def format_available_slots_for_message(self, max_slots: int = 5) -> str:
        """
        Format available slots as a human-readable message.

        Useful for presenting options to prospects.

        Args:
            max_slots: Maximum number of slots to include in the message.

        Returns:
            Formatted string with available times.
        """
        available = self.get_available_slots(days=7)[:max_slots]

        if not available:
            return "К сожалению, в ближайшие дни нет свободных слотов. Напишите нам, и мы найдём удобное время."

        lines = ["Доступные слоты для звонка (время Бали, UTC+8):"]

        # Group by date
        by_date: dict[date, list[SalesSlot]] = {}
        for slot in available:
            if slot.date not in by_date:
                by_date[slot.date] = []
            by_date[slot.date].append(slot)

        for d in sorted(by_date.keys()):
            # Format date nicely (e.g., "Четверг, 16 января")
            day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            month_names = ["января", "февраля", "марта", "апреля", "мая", "июня",
                          "июля", "августа", "сентября", "октября", "ноября", "декабря"]

            day_name = day_names[d.weekday()]
            month_name = month_names[d.month - 1]
            date_str = f"{day_name}, {d.day} {month_name}"

            times = [s.start_time.strftime("%H:%M") for s in by_date[d]]
            lines.append(f"  {date_str}: {', '.join(times)}")

        return "\n".join(lines)
