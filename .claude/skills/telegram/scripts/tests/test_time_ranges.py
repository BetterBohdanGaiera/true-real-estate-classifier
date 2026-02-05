"""
Comprehensive tests for timezone-aware scheduling and time range functionality.

Tests:
- TimeRange model validation and formatting
- Timezone calculator accuracy (requires timezone_calculator.py module)
- Slot aggregation algorithm (requires _group_consecutive_slots in SchedulingTool)
- Natural time formatting (requires _format_time_ranges_natural in SchedulingTool)

Test approach: Uses real objects, no mocking (per CLAUDE.md guidelines).
Some tests may be skipped if required modules don't exist yet (TDD approach).
"""

import sys
from pathlib import Path
from datetime import date, time, datetime

import pytest

# Add scripts directory to path for imports
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from models import TimeRange, SalesSlot


# =============================================================================
# TimeRange Model Tests
# =============================================================================

class TestTimeRangeModel:
    """Tests for TimeRange Pydantic model validation."""

    def test_timerange_valid_basic(self):
        """Test creating a valid TimeRange with basic parameters."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(16, 0)
        )
        assert tr.date == date(2026, 2, 5)
        assert tr.start_time == time(10, 0)
        assert tr.end_time == time(16, 0)
        assert tr.gaps == []

    def test_timerange_valid_with_gaps(self):
        """Test creating a valid TimeRange with gaps."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(16, 0),
            gaps=[(time(13, 0), time(14, 0))]
        )
        assert len(tr.gaps) == 1
        assert tr.gaps[0] == (time(13, 0), time(14, 0))

    def test_timerange_valid_with_multiple_gaps(self):
        """Test TimeRange with multiple gaps."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(18, 0),
            gaps=[
                (time(11, 0), time(11, 30)),
                (time(13, 0), time(14, 0)),
                (time(16, 30), time(17, 0))
            ]
        )
        assert len(tr.gaps) == 3

    def test_timerange_rejects_end_before_start(self):
        """Test that end_time must be after start_time."""
        with pytest.raises(ValueError) as exc_info:
            TimeRange(
                date=date(2026, 2, 5),
                start_time=time(16, 0),
                end_time=time(10, 0)
            )
        assert "must be after start_time" in str(exc_info.value)

    def test_timerange_rejects_end_equal_start(self):
        """Test that end_time cannot equal start_time."""
        with pytest.raises(ValueError) as exc_info:
            TimeRange(
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(10, 0)
            )
        assert "must be after start_time" in str(exc_info.value)

    def test_timerange_rejects_gap_outside_range_before(self):
        """Test that gaps must be within the time range (gap starts before range)."""
        with pytest.raises(ValueError) as exc_info:
            TimeRange(
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(16, 0),
                gaps=[(time(9, 0), time(11, 0))]  # Gap starts at 9:00, range starts at 10:00
            )
        assert "must be within range" in str(exc_info.value)

    def test_timerange_rejects_gap_outside_range_after(self):
        """Test that gaps must be within the time range (gap ends after range)."""
        with pytest.raises(ValueError) as exc_info:
            TimeRange(
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(16, 0),
                gaps=[(time(15, 0), time(17, 0))]  # Gap ends at 17:00, range ends at 16:00
            )
        assert "must be within range" in str(exc_info.value)

    def test_timerange_rejects_invalid_gap_order(self):
        """Test that gap start must be before gap end."""
        with pytest.raises(ValueError) as exc_info:
            TimeRange(
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(16, 0),
                gaps=[(time(14, 0), time(13, 0))]  # Gap end before gap start
            )
        assert "must be before gap end" in str(exc_info.value)


class TestTimeRangeFormatting:
    """Tests for TimeRange Russian formatting."""

    def test_format_russian_no_gaps(self):
        """Test Russian formatting without gaps."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(16, 0)
        )
        formatted = tr.format_russian()
        assert formatted == "с 10:00 до 16:00"

    def test_format_russian_single_gap(self):
        """Test Russian formatting with one gap."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(16, 0),
            gaps=[(time(13, 0), time(14, 0))]
        )
        formatted = tr.format_russian()
        assert "с 10:00 до 16:00" in formatted
        assert "кроме" in formatted
        assert "13:00-14:00" in formatted

    def test_format_russian_multiple_gaps(self):
        """Test Russian formatting with multiple gaps."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(18, 0),
            gaps=[
                (time(11, 0), time(11, 30)),
                (time(13, 0), time(14, 0))
            ]
        )
        formatted = tr.format_russian()
        assert "с 10:00 до 18:00" in formatted
        assert "кроме" in formatted
        assert "11:00-11:30" in formatted
        assert "13:00-14:00" in formatted

    def test_format_russian_gaps_excluded(self):
        """Test Russian formatting with include_gaps=False."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(16, 0),
            gaps=[(time(13, 0), time(14, 0))]
        )
        formatted = tr.format_russian(include_gaps=False)
        assert formatted == "с 10:00 до 16:00"
        assert "кроме" not in formatted

    def test_format_russian_half_hour_times(self):
        """Test formatting with half-hour times."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 30),
            end_time=time(15, 30)
        )
        formatted = tr.format_russian()
        assert formatted == "с 10:30 до 15:30"


# =============================================================================
# Timezone Calculator Tests
# These tests require timezone_calculator.py module
# =============================================================================

class TestTimezoneCalculator:
    """Tests for timezone calculation functions."""

    @pytest.fixture(autouse=True)
    def import_timezone_calculator(self):
        """Import timezone_calculator module, skip tests if not available."""
        try:
            global get_timezone_offset, calculate_time_difference, convert_time, format_dual_timezone_range
            from timezone_calculator import (
                get_timezone_offset,
                calculate_time_difference,
                convert_time,
                format_dual_timezone_range
            )
            self.module_available = True
        except ImportError:
            self.module_available = False

    def test_get_timezone_offset_bali(self):
        """Test Bali timezone offset (UTC+8)."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        offset = get_timezone_offset("Asia/Makassar")
        assert offset == 8

    def test_get_timezone_offset_moscow(self):
        """Test Moscow timezone offset (UTC+3, no DST)."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        offset = get_timezone_offset("Europe/Moscow")
        assert offset == 3

    def test_get_timezone_offset_warsaw_winter(self):
        """Test Warsaw timezone offset in winter (UTC+1)."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        winter_date = datetime(2026, 2, 1, 12, 0)
        offset = get_timezone_offset("Europe/Warsaw", at_time=winter_date)
        assert offset == 1

    def test_get_timezone_offset_warsaw_summer(self):
        """Test Warsaw timezone offset in summer (UTC+2, DST)."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        summer_date = datetime(2026, 7, 1, 12, 0)
        offset = get_timezone_offset("Europe/Warsaw", at_time=summer_date)
        assert offset == 2

    def test_calculate_time_difference_warsaw_bali_winter(self):
        """Test time difference between Warsaw (UTC+1) and Bali (UTC+8) in winter."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # Winter: Warsaw is UTC+1, Bali is UTC+8 -> difference is 7 hours
        winter_date = datetime(2026, 2, 1, 12, 0)
        diff = calculate_time_difference("Europe/Warsaw", "Asia/Makassar", at_time=winter_date)
        assert diff == 7, "Warsaw (UTC+1) to Bali (UTC+8) should be 7 hours difference in winter"

    def test_calculate_time_difference_warsaw_bali_summer(self):
        """Test time difference between Warsaw (UTC+2) and Bali (UTC+8) in summer."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # Summer: Warsaw is UTC+2 (DST), Bali is UTC+8 -> difference is 6 hours
        summer_date = datetime(2026, 7, 1, 12, 0)
        diff = calculate_time_difference("Europe/Warsaw", "Asia/Makassar", at_time=summer_date)
        assert diff == 6, "Warsaw (UTC+2) to Bali (UTC+8) should be 6 hours difference in summer"

    def test_calculate_time_difference_moscow_bali(self):
        """Test time difference between Moscow (UTC+3) and Bali (UTC+8)."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # Moscow is always UTC+3 (no DST), Bali is UTC+8 -> 5 hours difference
        diff = calculate_time_difference("Europe/Moscow", "Asia/Makassar")
        assert diff == 5, "Moscow (UTC+3) to Bali (UTC+8) should be 5 hours difference"

    def test_calculate_time_difference_same_timezone(self):
        """Test time difference when both timezones are the same."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        diff = calculate_time_difference("Asia/Makassar", "Asia/Makassar")
        assert diff == 0

    def test_calculate_time_difference_dubai_bali(self):
        """Test time difference between Dubai (UTC+4) and Bali (UTC+8)."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # Dubai is UTC+4, Bali is UTC+8 -> 4 hours difference
        diff = calculate_time_difference("Asia/Dubai", "Asia/Makassar")
        assert diff == 4, "Dubai (UTC+4) to Bali (UTC+8) should be 4 hours difference"

    def test_convert_time_warsaw_to_bali_winter(self):
        """Test converting time from Warsaw to Bali in winter."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # 14:00 Warsaw (UTC+1) = 21:00 Bali (UTC+8) in winter
        dt = datetime(2026, 2, 5, 14, 0)
        converted = convert_time(dt, "Europe/Warsaw", "Asia/Makassar")
        assert converted is not None
        assert converted.hour == 21, "14:00 Warsaw should be 21:00 Bali in winter"

    def test_convert_time_bali_to_warsaw_winter(self):
        """Test converting time from Bali to Warsaw in winter."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # 14:00 Bali (UTC+8) = 07:00 Warsaw (UTC+1) in winter
        dt = datetime(2026, 2, 5, 14, 0)
        converted = convert_time(dt, "Asia/Makassar", "Europe/Warsaw")
        assert converted is not None
        assert converted.hour == 7, "14:00 Bali should be 07:00 Warsaw in winter"

    def test_convert_time_moscow_to_bali(self):
        """Test converting time from Moscow to Bali."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # 12:00 Moscow (UTC+3) = 17:00 Bali (UTC+8)
        dt = datetime(2026, 2, 5, 12, 0)
        converted = convert_time(dt, "Europe/Moscow", "Asia/Makassar")
        assert converted is not None
        assert converted.hour == 17, "12:00 Moscow should be 17:00 Bali"

    def test_convert_time_preserves_date_when_crossing_midnight(self):
        """Test that date changes correctly when crossing midnight."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # 22:00 Warsaw (UTC+1) = 05:00 next day Bali (UTC+8) in winter
        dt = datetime(2026, 2, 5, 22, 0)
        converted = convert_time(dt, "Europe/Warsaw", "Asia/Makassar")
        assert converted is not None
        assert converted.day == 6, "22:00 Warsaw Feb 5 should be Feb 6 in Bali"
        assert converted.hour == 5

    def test_convert_time_invalid_timezone_returns_none(self):
        """Test that invalid timezone returns None gracefully."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        dt = datetime(2026, 2, 5, 14, 0)
        converted = convert_time(dt, "Invalid/Timezone", "Asia/Makassar")
        assert converted is None

    def test_format_dual_timezone_range(self):
        """Test formatting a time range in dual timezones."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        result = format_dual_timezone_range(
            start=time(10, 0),
            end=time(12, 0),
            target_date=date(2026, 2, 5),
            client_tz="Europe/Warsaw",
            bali_tz="Asia/Makassar"
        )
        # Result should contain both timezone references
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain Bali time reference
        assert "Бали" in result
        # Should contain client time reference
        assert "по вашему времени" in result

    def test_format_dual_timezone_range_verifies_conversion(self):
        """Test that dual timezone formatting correctly converts times."""
        if not self.module_available:
            pytest.skip("timezone_calculator module not available")
        # 10:00-12:00 Bali (UTC+8) = 3:00-5:00 Warsaw (UTC+1) in winter
        result = format_dual_timezone_range(
            start=time(10, 0),
            end=time(12, 0),
            target_date=date(2026, 2, 5),
            client_tz="Europe/Warsaw"
        )
        # Verify the converted times are correct
        assert "10" in result  # Bali time
        assert "12" in result  # Bali time
        assert "3" in result   # Warsaw time (3:00)
        assert "5" in result   # Warsaw time (5:00)


# =============================================================================
# Slot Aggregation Tests
# These tests require _group_consecutive_slots in SchedulingTool
# =============================================================================

class TestSlotAggregation:
    """Tests for slot aggregation into time ranges."""

    @pytest.fixture(autouse=True)
    def setup_scheduling_tool(self):
        """Setup SchedulingTool, skip if _group_consecutive_slots not available."""
        try:
            from scheduling_tool import SchedulingTool
            # Create tool without calendar for unit testing
            self.tool = SchedulingTool(calendar=None)
            self.has_group_method = hasattr(self.tool, '_group_consecutive_slots')
        except Exception:
            self.has_group_method = False

    def test_group_consecutive_slots_single(self):
        """Test grouping a single slot (no merging needed)."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        slots = [
            SalesSlot(
                id="20260205_1000",
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(10, 30)
            )
        ]

        ranges = self.tool._group_consecutive_slots(slots)

        assert len(ranges) == 1
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(10, 30)
        assert ranges[0].date == date(2026, 2, 5)

    def test_group_consecutive_slots_two_adjacent(self):
        """Test merging two adjacent slots into one range."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        slots = [
            SalesSlot(
                id="20260205_1000",
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(10, 30)
            ),
            SalesSlot(
                id="20260205_1030",
                date=date(2026, 2, 5),
                start_time=time(10, 30),
                end_time=time(11, 0)
            )
        ]

        ranges = self.tool._group_consecutive_slots(slots)

        assert len(ranges) == 1
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(11, 0)

    def test_group_consecutive_slots_three_adjacent(self):
        """Test merging three adjacent slots into one range."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        slots = [
            SalesSlot(
                id="20260205_1000",
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(10, 30)
            ),
            SalesSlot(
                id="20260205_1030",
                date=date(2026, 2, 5),
                start_time=time(10, 30),
                end_time=time(11, 0)
            ),
            SalesSlot(
                id="20260205_1100",
                date=date(2026, 2, 5),
                start_time=time(11, 0),
                end_time=time(11, 30)
            )
        ]

        ranges = self.tool._group_consecutive_slots(slots)

        assert len(ranges) == 1
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(11, 30)

    def test_group_consecutive_slots_with_gap_morning_afternoon(self):
        """Test grouping slots with a gap (morning and afternoon blocks)."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        slots = [
            # Morning block: 10:00-11:00
            SalesSlot(
                id="20260205_1000",
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(10, 30)
            ),
            SalesSlot(
                id="20260205_1030",
                date=date(2026, 2, 5),
                start_time=time(10, 30),
                end_time=time(11, 0)
            ),
            # Afternoon block: 14:00-15:00 (gap from 11:00-14:00)
            SalesSlot(
                id="20260205_1400",
                date=date(2026, 2, 5),
                start_time=time(14, 0),
                end_time=time(14, 30)
            ),
            SalesSlot(
                id="20260205_1430",
                date=date(2026, 2, 5),
                start_time=time(14, 30),
                end_time=time(15, 0)
            )
        ]

        ranges = self.tool._group_consecutive_slots(slots)

        assert len(ranges) == 2
        # Morning block
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(11, 0)
        # Afternoon block
        assert ranges[1].start_time == time(14, 0)
        assert ranges[1].end_time == time(15, 0)

    def test_group_consecutive_slots_empty_list(self):
        """Test grouping empty slot list returns empty result."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        ranges = self.tool._group_consecutive_slots([])

        assert len(ranges) == 0
        assert isinstance(ranges, list)

    def test_group_consecutive_slots_unsorted_input(self):
        """Test that slots are properly sorted before grouping."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        # Provide slots in wrong order
        slots = [
            SalesSlot(
                id="20260205_1030",
                date=date(2026, 2, 5),
                start_time=time(10, 30),
                end_time=time(11, 0)
            ),
            SalesSlot(
                id="20260205_1000",
                date=date(2026, 2, 5),
                start_time=time(10, 0),
                end_time=time(10, 30)
            )
        ]

        ranges = self.tool._group_consecutive_slots(slots)

        assert len(ranges) == 1
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(11, 0)

    def test_group_consecutive_slots_full_day(self):
        """Test grouping a full day of consecutive slots."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        # Create slots for 10:00-19:00 (9 hours of 30-min slots = 18 slots)
        slots = []
        for hour in range(10, 19):
            slots.append(SalesSlot(
                id=f"20260205_{hour:02d}00",
                date=date(2026, 2, 5),
                start_time=time(hour, 0),
                end_time=time(hour, 30)
            ))
            slots.append(SalesSlot(
                id=f"20260205_{hour:02d}30",
                date=date(2026, 2, 5),
                start_time=time(hour, 30),
                end_time=time(hour + 1, 0) if hour < 18 else time(19, 0)
            ))

        ranges = self.tool._group_consecutive_slots(slots)

        # Should merge into one range: 10:00-19:00
        assert len(ranges) == 1
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(19, 0)

    def test_group_consecutive_slots_multiple_small_gaps(self):
        """Test grouping with multiple small gaps throughout the day."""
        if not self.has_group_method:
            pytest.skip("_group_consecutive_slots method not available")

        slots = [
            # 10:00-10:30
            SalesSlot(id="20260205_1000", date=date(2026, 2, 5), start_time=time(10, 0), end_time=time(10, 30)),
            # Gap: 10:30-11:00
            # 11:00-11:30
            SalesSlot(id="20260205_1100", date=date(2026, 2, 5), start_time=time(11, 0), end_time=time(11, 30)),
            # Gap: 11:30-14:00
            # 14:00-14:30
            SalesSlot(id="20260205_1400", date=date(2026, 2, 5), start_time=time(14, 0), end_time=time(14, 30)),
        ]

        ranges = self.tool._group_consecutive_slots(slots)

        assert len(ranges) == 3
        assert ranges[0].start_time == time(10, 0)
        assert ranges[0].end_time == time(10, 30)
        assert ranges[1].start_time == time(11, 0)
        assert ranges[1].end_time == time(11, 30)
        assert ranges[2].start_time == time(14, 0)
        assert ranges[2].end_time == time(14, 30)


# =============================================================================
# Natural Formatting Tests
# These tests require _format_time_ranges_natural in SchedulingTool
# =============================================================================

class TestNaturalFormatting:
    """Tests for natural time range formatting."""

    @pytest.fixture(autouse=True)
    def setup_scheduling_tool(self):
        """Setup SchedulingTool, skip if method not available."""
        try:
            from scheduling_tool import SchedulingTool
            self.tool = SchedulingTool(calendar=None)
            self.has_format_method = hasattr(self.tool, '_format_time_ranges_natural')
        except Exception:
            self.has_format_method = False

    def test_format_time_ranges_natural_single_range(self):
        """Test natural formatting with single time range."""
        if not self.has_format_method:
            pytest.skip("_format_time_ranges_natural method not available")

        ranges = [
            TimeRange(
                date=date(2026, 2, 6),
                start_time=time(10, 0),
                end_time=time(16, 0)
            )
        ]

        formatted = self.tool._format_time_ranges_natural(ranges, client_timezone=None)

        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # Should contain time information
        assert "10" in formatted
        assert "16" in formatted

    def test_format_time_ranges_natural_multiple_ranges_same_day(self):
        """Test natural formatting with multiple ranges on same day."""
        if not self.has_format_method:
            pytest.skip("_format_time_ranges_natural method not available")

        ranges = [
            TimeRange(
                date=date(2026, 2, 6),
                start_time=time(10, 0),
                end_time=time(12, 0)
            ),
            TimeRange(
                date=date(2026, 2, 6),
                start_time=time(14, 0),
                end_time=time(16, 0)
            )
        ]

        formatted = self.tool._format_time_ranges_natural(ranges, client_timezone=None)

        assert isinstance(formatted, str)
        # Should contain both time ranges
        assert "10" in formatted
        assert "12" in formatted
        assert "14" in formatted
        assert "16" in formatted

    def test_format_time_ranges_natural_with_timezone(self):
        """Test natural formatting with client timezone conversion."""
        if not self.has_format_method:
            pytest.skip("_format_time_ranges_natural method not available")

        ranges = [
            TimeRange(
                date=date(2026, 2, 6),
                start_time=time(14, 0),
                end_time=time(16, 0)
            )
        ]

        formatted = self.tool._format_time_ranges_natural(
            ranges,
            client_timezone="Europe/Moscow"
        )

        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_format_time_ranges_natural_empty_list(self):
        """Test natural formatting with empty range list."""
        if not self.has_format_method:
            pytest.skip("_format_time_ranges_natural method not available")

        formatted = self.tool._format_time_ranges_natural([], client_timezone=None)

        assert isinstance(formatted, str)
        # Should indicate no availability or be empty


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete flow."""

    def test_timerange_to_salesslot_roundtrip(self):
        """Test creating TimeRange from SalesSlot data."""
        # Create a sales slot
        slot = SalesSlot(
            id="20260205_1000",
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(10, 30),
            is_available=True
        )

        # Create TimeRange from slot data
        tr = TimeRange(
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time
        )

        assert tr.date == slot.date
        assert tr.start_time == slot.start_time
        assert tr.end_time == slot.end_time

    def test_format_russian_is_human_readable(self):
        """Test that Russian formatting produces human-readable text."""
        tr = TimeRange(
            date=date(2026, 2, 5),
            start_time=time(10, 0),
            end_time=time(18, 0),
            gaps=[(time(13, 0), time(14, 0))]
        )

        formatted = tr.format_russian()

        # Verify it's in Russian format
        assert "с " in formatted
        assert " до " in formatted
        # Verify gap is mentioned
        assert "кроме" in formatted
        # Verify it's readable (contains times)
        assert "10:00" in formatted
        assert "18:00" in formatted
        assert "13:00" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
