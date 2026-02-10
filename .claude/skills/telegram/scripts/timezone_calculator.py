"""
Timezone calculation utilities for accurate timezone conversions.

Provides Python-based timezone calculations to replace LLM arithmetic.
Uses zoneinfo library (Python 3.9+) for accurate DST-aware conversions.
"""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional


# Default Bali timezone constant (UTC+8, no DST)
BALI_TZ = "Asia/Makassar"

# Russian time period names for natural formatting
TIME_PERIODS_RU = {
    "morning_early": "рано утром",      # 5-7
    "morning": "утра",                   # 7-12
    "day": "дня",                        # 12-17
    "evening": "вечера",                 # 17-22
    "night": "ночи",                     # 22-5
}


def _get_time_period_suffix(hour: int) -> str:
    """
    Get Russian time period suffix for an hour.

    Args:
        hour: Hour in 24h format (0-23)

    Returns:
        Russian suffix like "утра", "дня", "вечера", "ночи"
    """
    if 5 <= hour < 7:
        return TIME_PERIODS_RU["morning_early"]
    elif 7 <= hour < 12:
        return TIME_PERIODS_RU["morning"]
    elif 12 <= hour < 17:
        return TIME_PERIODS_RU["day"]
    elif 17 <= hour < 22:
        return TIME_PERIODS_RU["evening"]
    else:
        return TIME_PERIODS_RU["night"]


def get_timezone_offset(timezone: str, at_time: Optional[datetime] = None) -> Optional[int]:
    """
    Get UTC offset in hours for a timezone at a specific time.

    Handles DST by using the provided datetime or current time.

    Args:
        timezone: IANA timezone string (e.g., "Europe/Warsaw", "Asia/Makassar")
        at_time: Optional datetime to check offset at (for DST). Defaults to now.

    Returns:
        UTC offset in hours (can be fractional for 30-min offsets),
        or None if timezone is invalid

    Examples:
        >>> get_timezone_offset("Asia/Makassar")
        8
        >>> get_timezone_offset("Europe/Warsaw")  # Winter
        1
        >>> get_timezone_offset("Europe/Warsaw", datetime(2026, 7, 1))  # Summer DST
        2
    """
    try:
        tz = ZoneInfo(timezone)

        # Use provided time or current time
        if at_time is None:
            at_time = datetime.now(tz)
        elif at_time.tzinfo is None:
            # Make naive datetime timezone-aware
            at_time = at_time.replace(tzinfo=tz)
        else:
            # Convert to target timezone
            at_time = at_time.astimezone(tz)

        # Get UTC offset in seconds, convert to hours
        offset_seconds = at_time.utcoffset().total_seconds()
        offset_hours = offset_seconds / 3600

        # Return as int if whole number, otherwise float
        if offset_hours == int(offset_hours):
            return int(offset_hours)
        return offset_hours

    except (KeyError, ValueError, AttributeError):
        # Unknown timezone or invalid input
        return None


def calculate_time_difference(
    tz1: str,
    tz2: str,
    at_time: Optional[datetime] = None
) -> Optional[int]:
    """
    Calculate hour difference between two timezones.

    Returns how many hours ahead tz2 is compared to tz1.
    Positive means tz2 is ahead (east), negative means behind (west).

    Args:
        tz1: First timezone (e.g., "Europe/Warsaw")
        tz2: Second timezone (e.g., "Asia/Makassar")
        at_time: Optional datetime for DST-aware calculation

    Returns:
        Hour difference (tz2 - tz1), or None if either timezone is invalid

    Examples:
        >>> calculate_time_difference("Europe/Warsaw", "Asia/Makassar")
        7  # Bali is 7 hours ahead of Warsaw in winter
        >>> calculate_time_difference("Asia/Makassar", "Europe/Moscow")
        -5  # Moscow is 5 hours behind Bali
        >>> calculate_time_difference("America/New_York", "Europe/London")
        5  # London is 5 hours ahead of NYC in winter
    """
    offset1 = get_timezone_offset(tz1, at_time)
    offset2 = get_timezone_offset(tz2, at_time)

    if offset1 is None or offset2 is None:
        return None

    difference = offset2 - offset1

    # Return as int if whole number
    if difference == int(difference):
        return int(difference)
    return difference


def convert_time(
    dt: datetime,
    from_tz: str,
    to_tz: str
) -> Optional[datetime]:
    """
    Convert datetime from one timezone to another.

    Args:
        dt: Datetime to convert (can be naive or aware)
        from_tz: Source timezone (e.g., "Europe/Warsaw")
        to_tz: Target timezone (e.g., "Asia/Makassar")

    Returns:
        Converted datetime in target timezone, or None if conversion fails

    Examples:
        >>> dt = datetime(2026, 2, 5, 14, 0)  # 14:00
        >>> result = convert_time(dt, "Europe/Warsaw", "Asia/Makassar")
        >>> result.hour
        21  # 21:00 Bali time (7 hours ahead in winter)
    """
    try:
        source_tz = ZoneInfo(from_tz)
        target_tz = ZoneInfo(to_tz)

        # If datetime is naive, assume it's in source timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=source_tz)
        else:
            # First convert to source timezone if not already
            dt = dt.astimezone(source_tz)

        # Convert to target timezone
        return dt.astimezone(target_tz)

    except (KeyError, ValueError, AttributeError):
        # Unknown timezone or conversion error
        return None


def convert_time_only(
    t: time,
    on_date: date,
    from_tz: str,
    to_tz: str
) -> Optional[time]:
    """
    Convert a time object from one timezone to another on a specific date.

    Useful when you have just a time (not datetime) and need to convert it.

    Args:
        t: Time to convert
        on_date: Date for the conversion (needed for DST calculations)
        from_tz: Source timezone
        to_tz: Target timezone

    Returns:
        Converted time in target timezone, or None if conversion fails

    Examples:
        >>> convert_time_only(time(10, 0), date(2026, 2, 5), "Asia/Makassar", "Europe/Warsaw")
        time(3, 0)  # 10:00 Bali = 3:00 Warsaw in winter
    """
    dt = datetime.combine(on_date, t)
    converted = convert_time(dt, from_tz, to_tz)

    if converted is None:
        return None

    return converted.time()


def format_dual_timezone_range(
    start: time,
    end: time,
    target_date: date,
    client_tz: str,
    bali_tz: str = BALI_TZ
) -> str:
    """
    Format time range in both client and Bali timezones naturally.

    Takes Bali times as input and converts to client timezone for display.

    Args:
        start: Start time in Bali timezone
        end: End time in Bali timezone
        target_date: Date of the range
        client_tz: Client's timezone (e.g., "Europe/Warsaw")
        bali_tz: Bali timezone (default: "Asia/Makassar")

    Returns:
        Formatted string like "с 10 до 12 дня по Бали (3-5 утра по вашему времени)"
        or just "с 10 до 12 дня по Бали" if conversion fails

    Examples:
        >>> format_dual_timezone_range(
        ...     time(10, 0), time(12, 0), date(2026, 2, 5), "Europe/Warsaw"
        ... )
        'с 10 до 12 дня по Бали (3-5 утра по вашему времени)'
    """
    # Format Bali times
    bali_start_hour = start.hour
    bali_end_hour = end.hour
    bali_period = _get_time_period_suffix(bali_start_hour)

    # Build Bali time string
    bali_str = f"с {bali_start_hour} до {bali_end_hour} {bali_period} по Бали"

    # Try to convert to client timezone
    client_start = convert_time_only(start, target_date, bali_tz, client_tz)
    client_end = convert_time_only(end, target_date, bali_tz, client_tz)

    if client_start is None or client_end is None:
        return bali_str

    # Format client times
    client_start_hour = client_start.hour
    client_end_hour = client_end.hour
    client_period = _get_time_period_suffix(client_start_hour)

    # Handle date change detection
    # If converting from Bali to a western timezone, time may be earlier (previous day)
    start_dt = datetime.combine(target_date, start)
    client_start_dt = convert_time(start_dt, bali_tz, client_tz)

    date_note = ""
    if client_start_dt and client_start_dt.date() != target_date:
        if client_start_dt.date() < target_date:
            date_note = " (предыдущий день)"
        else:
            date_note = " (следующий день)"

    client_str = f"{client_start_hour}-{client_end_hour} {client_period}"

    return f"{bali_str} ({client_str} по вашему времени{date_note})"


def format_time_with_both_zones(
    bali_time: time,
    target_date: date,
    client_tz: str,
    bali_tz: str = BALI_TZ
) -> str:
    """
    Format a single time in both Bali and client timezones.

    Args:
        bali_time: Time in Bali timezone
        target_date: Date for conversion
        client_tz: Client's timezone
        bali_tz: Bali timezone (default: "Asia/Makassar")

    Returns:
        Formatted string like "14:00 по Бали (7:00 утра по вашему времени)"
        or just "14:00 по Бали" if conversion fails

    Examples:
        >>> format_time_with_both_zones(time(14, 0), date(2026, 2, 5), "Europe/Warsaw")
        '14:00 по Бали (7:00 утра по вашему времени)'
    """
    bali_str = f"{bali_time.strftime('%H:%M')} по Бали"

    client_time = convert_time_only(bali_time, target_date, bali_tz, client_tz)

    if client_time is None:
        return bali_str

    client_hour = client_time.hour
    client_period = _get_time_period_suffix(client_hour)

    # Handle date change
    start_dt = datetime.combine(target_date, bali_time)
    client_dt = convert_time(start_dt, bali_tz, client_tz)

    date_note = ""
    if client_dt and client_dt.date() != target_date:
        if client_dt.date() < target_date:
            date_note = " предыдущего дня"
        else:
            date_note = " следующего дня"

    client_str = f"{client_time.strftime('%H:%M')} {client_period}{date_note}"

    return f"{bali_str} ({client_str} по вашему времени)"


def get_city_name_from_timezone(timezone: str) -> Optional[str]:
    """
    Extract city name from IANA timezone string for display.

    Args:
        timezone: IANA timezone string (e.g., "Europe/Warsaw", "America/New_York")

    Returns:
        City name in Russian or transliterated, or None if invalid

    Examples:
        >>> get_city_name_from_timezone("Europe/Warsaw")
        'Варшаве'
        >>> get_city_name_from_timezone("Europe/Moscow")
        'Москве'
    """
    # Common timezone to Russian city name mappings (in dative case for "по")
    city_names = {
        "Europe/Moscow": "Москве",
        "Europe/Warsaw": "Варшаве",
        "Europe/Kiev": "Киеве",
        "Europe/Kyiv": "Киеве",
        "Europe/Berlin": "Берлине",
        "Europe/Paris": "Парижу",
        "Europe/London": "Лондону",
        "Europe/Prague": "Праге",
        "Europe/Vienna": "Вене",
        "Europe/Rome": "Риму",
        "Europe/Madrid": "Мадриду",
        "Europe/Amsterdam": "Амстердаму",
        "Europe/Brussels": "Брюсселю",
        "Europe/Helsinki": "Хельсинки",
        "Europe/Stockholm": "Стокгольму",
        "Europe/Oslo": "Осло",
        "Europe/Copenhagen": "Копенгагену",
        "Europe/Athens": "Афинам",
        "Europe/Istanbul": "Стамбулу",
        "Europe/Bucharest": "Бухаресту",
        "Europe/Sofia": "Софии",
        "Europe/Budapest": "Будапешту",
        "Europe/Minsk": "Минску",
        "Europe/Vilnius": "Вильнюсу",
        "Europe/Riga": "Риге",
        "Europe/Tallinn": "Таллину",
        "Asia/Dubai": "Дубаю",
        "Asia/Almaty": "Алматы",
        "Asia/Tashkent": "Ташкенту",
        "Asia/Bangkok": "Бангкоку",
        "Asia/Singapore": "Сингапуру",
        "Asia/Hong_Kong": "Гонконгу",
        "Asia/Tokyo": "Токио",
        "Asia/Seoul": "Сеулу",
        "Asia/Shanghai": "Шанхаю",
        "Asia/Jakarta": "Джакарте",
        "Asia/Makassar": "Бали",
        "America/New_York": "Нью-Йорку",
        "America/Los_Angeles": "Лос-Анджелесу",
        "America/Chicago": "Чикаго",
        "America/Toronto": "Торонто",
        "America/Vancouver": "Ванкуверу",
        "Australia/Sydney": "Сиднею",
        "Australia/Melbourne": "Мельбурну",
    }

    if timezone in city_names:
        return city_names[timezone]

    # Fallback: extract city from timezone string
    try:
        parts = timezone.split("/")
        if len(parts) >= 2:
            city = parts[-1].replace("_", " ")
            return city
    except (AttributeError, IndexError):
        pass

    return None


def is_valid_timezone(timezone: str) -> bool:
    """
    Check if a timezone string is valid.

    Args:
        timezone: IANA timezone string to validate

    Returns:
        True if timezone is valid, False otherwise

    Examples:
        >>> is_valid_timezone("Europe/Warsaw")
        True
        >>> is_valid_timezone("Invalid/Timezone")
        False
    """
    try:
        ZoneInfo(timezone)
        return True
    except (KeyError, ValueError):
        return False


# Simple tests when run directly
if __name__ == "__main__":
    print("=== Timezone Calculator Tests ===\n")

    # Test 1: Get timezone offset
    print("1. Timezone offsets:")
    print(f"   Asia/Makassar (Bali): UTC+{get_timezone_offset('Asia/Makassar')}")
    print(f"   Europe/Warsaw (winter): UTC+{get_timezone_offset('Europe/Warsaw')}")
    print(f"   Europe/Moscow: UTC+{get_timezone_offset('Europe/Moscow')}")
    print(f"   America/New_York: UTC{get_timezone_offset('America/New_York')}")

    # Test 2: Time difference
    print("\n2. Time differences:")
    diff = calculate_time_difference("Europe/Warsaw", "Asia/Makassar")
    print(f"   Warsaw -> Bali: {diff} hours (Bali is {diff} hours ahead)")
    diff = calculate_time_difference("Asia/Makassar", "Europe/Moscow")
    print(f"   Bali -> Moscow: {diff} hours (Moscow is {abs(diff)} hours behind)")

    # Test 3: Convert time
    print("\n3. Time conversion:")
    dt = datetime(2026, 2, 5, 14, 0)
    converted = convert_time(dt, "Europe/Warsaw", "Asia/Makassar")
    print(f"   14:00 Warsaw -> {converted.strftime('%H:%M')} Bali")

    dt = datetime(2026, 2, 5, 10, 0)
    converted = convert_time(dt, "Asia/Makassar", "Europe/Warsaw")
    print(f"   10:00 Bali -> {converted.strftime('%H:%M')} Warsaw")

    # Test 4: Format dual timezone range
    print("\n4. Dual timezone formatting:")
    result = format_dual_timezone_range(
        time(10, 0), time(12, 0), date(2026, 2, 5), "Europe/Warsaw"
    )
    print(f"   10:00-12:00 Bali for Warsaw client:")
    print(f"   '{result}'")

    result = format_dual_timezone_range(
        time(20, 0), time(22, 0), date(2026, 2, 5), "Europe/Warsaw"
    )
    print(f"   20:00-22:00 Bali for Warsaw client:")
    print(f"   '{result}'")

    # Test 5: Single time formatting
    print("\n5. Single time formatting:")
    result = format_time_with_both_zones(time(14, 0), date(2026, 2, 5), "Europe/Warsaw")
    print(f"   14:00 Bali: '{result}'")

    # Test 6: Timezone validation
    print("\n6. Timezone validation:")
    print(f"   Europe/Warsaw valid: {is_valid_timezone('Europe/Warsaw')}")
    print(f"   Invalid/Zone valid: {is_valid_timezone('Invalid/Zone')}")

    # Test 7: City names
    print("\n7. City names:")
    print(f"   Europe/Warsaw: {get_city_name_from_timezone('Europe/Warsaw')}")
    print(f"   Europe/Moscow: {get_city_name_from_timezone('Europe/Moscow')}")
    print(f"   Asia/Makassar: {get_city_name_from_timezone('Asia/Makassar')}")

    print("\n=== All tests completed ===")
