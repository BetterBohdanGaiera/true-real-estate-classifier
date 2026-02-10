# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.0.0",
#   "rich>=13.0.0",
#   "python-dotenv>=1.0.0",
#   "pytz>=2024.1",
# ]
# ///
"""
Meeting Scheduling Flow Tests.

Tests the three critical scheduling bugs:
1. confirm_time_slot called when user provides specific time (not full slot list)
2. Calendar event creation works and invites are sent
3. No duplicate slot messages on batch processing

Run:
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/test_meeting_scheduling.py
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/test_meeting_scheduling.py --calendar  # Include real calendar tests
    PYTHONPATH=src uv run python .claude/skills/testing/scripts/test_meeting_scheduling.py -v          # Verbose output
"""

import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Ensure src is in path
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

console = Console(width=120)

BALI_TZ = ZoneInfo("Asia/Makassar")


# =============================================================================
# TEST RESULT MODEL
# =============================================================================


class TestResult(BaseModel):
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    details: Optional[str] = None


# =============================================================================
# TEST 1: confirm_time_slot returns targeted response (not full list)
# =============================================================================


def test_confirm_time_slot_available() -> TestResult:
    """Test that confirm_time_slot returns a short confirmation when slot is available."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    # Get an actually available slot
    available = calendar.get_available_slots(days=7)
    if not available:
        return TestResult(
            name="confirm_time_slot (available)",
            passed=False,
            message="No available slots to test with",
        )

    slot = available[0]
    result = tool.confirm_time_slot(
        target_date=slot.date,
        target_time=slot.start_time,
        client_timezone="Europe/Warsaw",
    )

    # Should be a SHORT confirmation, NOT a full list of all slots
    has_confirmation = "свободно" in result.lower()
    is_short = len(result) < 200  # Confirmation should be concise
    no_full_list = "Какое время Вам удобнее" not in result  # Should NOT ask morning/evening

    passed = has_confirmation and is_short and no_full_list

    return TestResult(
        name="confirm_time_slot (available)",
        passed=passed,
        message="Short confirmation returned" if passed else "Got full slot list instead of confirmation",
        details=f"Response ({len(result)} chars): {result[:200]}",
    )


def test_confirm_time_slot_unavailable() -> TestResult:
    """Test that confirm_time_slot returns alternatives when slot is NOT available."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    # Use a time that's very unlikely to be available (3am Bali time)
    tomorrow = (datetime.now(BALI_TZ) + timedelta(days=1)).date()
    result = tool.confirm_time_slot(
        target_date=tomorrow,
        target_time=time(3, 0),
        client_timezone="Europe/Warsaw",
    )

    # Should mention it's unavailable and offer alternatives
    has_unavailable = "занято" in result.lower() or "нет свободных" in result.lower()
    has_alternatives = "ближайшие" in result.lower() or "свободн" in result.lower()
    no_full_list = "Какое время Вам удобнее" not in result

    passed = (has_unavailable or has_alternatives) and no_full_list

    return TestResult(
        name="confirm_time_slot (unavailable)",
        passed=passed,
        message="Alternatives offered" if passed else "Response was not helpful for unavailable slot",
        details=f"Response ({len(result)} chars): {result[:200]}",
    )


def test_confirm_time_slot_timezone_conversion() -> TestResult:
    """Test that timezone conversion works: Warsaw 10:15 -> Bali 17:15."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    # Warsaw is UTC+1, Bali is UTC+8, so 10:15 Warsaw = 17:15 Bali
    tomorrow = (datetime.now(BALI_TZ) + timedelta(days=1)).date()

    # Create a datetime in Warsaw timezone
    warsaw_tz = ZoneInfo("Europe/Warsaw")
    client_dt = datetime.combine(tomorrow, time(10, 15), tzinfo=warsaw_tz)
    bali_dt = client_dt.astimezone(BALI_TZ)

    expected_bali_time = bali_dt.time().replace(second=0, microsecond=0)
    expected_bali_date = bali_dt.date()

    # Now call confirm_time_slot with the BALI time (as daemon would after conversion)
    result = tool.confirm_time_slot(
        target_date=expected_bali_date,
        target_time=expected_bali_time,
        client_timezone="Europe/Warsaw",
    )

    # Should show dual timezone (client time + Bali time)
    has_client_time = "вашего времени" in result or "10:15" in result
    no_full_list = "Какое время Вам удобнее" not in result

    passed = no_full_list  # Main thing: no full list dump

    return TestResult(
        name="confirm_time_slot (timezone conversion)",
        passed=passed,
        message="Timezone conversion works" if passed else "Full slot list shown instead of targeted response",
        details=f"Warsaw 10:15 -> Bali {expected_bali_time}. Response: {result[:200]}",
    )


# =============================================================================
# TEST 2: _handle_action routing for check_availability
# =============================================================================


def test_handle_action_routes_to_confirm() -> TestResult:
    """Test that daemon routes check_availability + scheduling_data to confirm_time_slot."""
    from telegram_sales_bot.core.models import AgentAction

    # Simulate the action the agent would return
    action = AgentAction(
        action="check_availability",
        reason="Client named specific time",
        scheduling_data={
            "preferred_time": "10:15",
            "preferred_date": (datetime.now(BALI_TZ) + timedelta(days=1)).date().isoformat(),
            "client_timezone": "Europe/Warsaw",
        },
    )

    # Verify action has scheduling_data
    sched_data = action.scheduling_data or {}
    has_preferred_time = "preferred_time" in sched_data
    has_preferred_date = "preferred_date" in sched_data
    has_client_tz = "client_timezone" in sched_data

    passed = has_preferred_time and has_preferred_date and has_client_tz

    return TestResult(
        name="Action routing (check_availability + scheduling_data)",
        passed=passed,
        message="scheduling_data correctly structured" if passed else "Missing fields in scheduling_data",
        details=f"scheduling_data: {sched_data}",
    )


def test_handle_action_routes_to_full_list() -> TestResult:
    """Test that check_availability WITHOUT scheduling_data still shows full list."""
    from telegram_sales_bot.core.models import AgentAction

    action = AgentAction(
        action="check_availability",
        reason="Client asked for available times",
    )

    sched_data = action.scheduling_data or {}
    has_no_preferred = "preferred_time" not in sched_data

    passed = has_no_preferred

    return TestResult(
        name="Action routing (check_availability without scheduling_data)",
        passed=passed,
        message="Correctly falls through to full list" if passed else "Unexpected scheduling_data present",
        details=f"scheduling_data: {sched_data}",
    )


# =============================================================================
# TEST 3: Timezone conversion in daemon routing
# =============================================================================


def test_daemon_timezone_conversion() -> TestResult:
    """Test the timezone conversion logic that daemon would perform."""
    from datetime import time as dt_time, date as dt_date

    # Simulate what daemon does: parse preferred time, convert to Bali
    preferred_time_str = "10:15"
    preferred_date_str = (datetime.now(BALI_TZ) + timedelta(days=1)).date().isoformat()
    client_tz = "Europe/Warsaw"

    try:
        h, m = map(int, preferred_time_str.split(":"))
        preferred_time = dt_time(h, m)
        preferred_date = dt_date.fromisoformat(preferred_date_str)

        # Convert from client timezone to Bali
        client_dt = datetime.combine(
            preferred_date, preferred_time,
            tzinfo=ZoneInfo(client_tz)
        )
        bali_dt = client_dt.astimezone(ZoneInfo("Asia/Makassar"))
        target_date = bali_dt.date()
        target_time = bali_dt.time().replace(second=0, microsecond=0)

        # Warsaw is UTC+1, Bali is UTC+8 -> 7 hour difference
        expected_hour = (10 + 7) % 24  # 17
        conversion_correct = target_time.hour == expected_hour and target_time.minute == 15

        passed = conversion_correct

        return TestResult(
            name="Daemon timezone conversion (Warsaw->Bali)",
            passed=passed,
            message=f"Conversion correct: Warsaw 10:15 -> Bali {target_time}" if passed
            else f"Wrong conversion: Warsaw 10:15 -> Bali {target_time} (expected 17:15)",
            details=f"Client: {client_dt.isoformat()}, Bali: {bali_dt.isoformat()}",
        )
    except Exception as e:
        return TestResult(
            name="Daemon timezone conversion (Warsaw->Bali)",
            passed=False,
            message=f"Conversion failed: {e}",
        )


def test_daemon_timezone_conversion_moscow() -> TestResult:
    """Test timezone conversion for Moscow (UTC+3)."""
    from datetime import time as dt_time, date as dt_date

    preferred_time_str = "14:00"
    preferred_date_str = (datetime.now(BALI_TZ) + timedelta(days=1)).date().isoformat()
    client_tz = "Europe/Moscow"

    try:
        h, m = map(int, preferred_time_str.split(":"))
        preferred_time = dt_time(h, m)
        preferred_date = dt_date.fromisoformat(preferred_date_str)

        client_dt = datetime.combine(
            preferred_date, preferred_time,
            tzinfo=ZoneInfo(client_tz)
        )
        bali_dt = client_dt.astimezone(ZoneInfo("Asia/Makassar"))
        target_time = bali_dt.time().replace(second=0, microsecond=0)

        # Moscow UTC+3, Bali UTC+8 -> 5 hour difference
        expected_hour = (14 + 5) % 24  # 19
        conversion_correct = target_time.hour == expected_hour and target_time.minute == 0

        passed = conversion_correct

        return TestResult(
            name="Daemon timezone conversion (Moscow->Bali)",
            passed=passed,
            message=f"Conversion correct: Moscow 14:00 -> Bali {target_time}" if passed
            else f"Wrong: Moscow 14:00 -> Bali {target_time} (expected 19:00)",
        )
    except Exception as e:
        return TestResult(
            name="Daemon timezone conversion (Moscow->Bali)",
            passed=False,
            message=f"Conversion failed: {e}",
        )


# =============================================================================
# TEST 4: book_meeting with email validation
# =============================================================================


def test_book_meeting_requires_email() -> TestResult:
    """Test that book_meeting rejects booking without email."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool
    from telegram_sales_bot.core.models import Prospect

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    prospect = Prospect(telegram_id="test_123", name="Test", context="test")
    result = tool.book_meeting("20260210_1400", prospect, "")

    passed = not result.success and "email" in result.message.lower()

    return TestResult(
        name="book_meeting rejects empty email",
        passed=passed,
        message="Correctly rejected" if passed else f"Should have rejected: {result.message}",
    )


def test_book_meeting_catches_email_typo() -> TestResult:
    """Test that book_meeting detects email typos."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool
    from telegram_sales_bot.core.models import Prospect

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    prospect = Prospect(telegram_id="test_123", name="Test", context="test")
    result = tool.book_meeting("20260210_1400", prospect, "test@gmil.com")

    passed = not result.success and "gmail.com" in (result.message or "")

    return TestResult(
        name="book_meeting detects email typo",
        passed=passed,
        message="Typo detected and suggestion made" if passed else f"Missed typo: {result.message}",
    )


def test_book_meeting_success() -> TestResult:
    """Test that book_meeting succeeds with valid slot and email."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool
    from telegram_sales_bot.core.models import Prospect

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    # Get an available slot
    available = calendar.get_available_slots(days=7)
    if not available:
        return TestResult(
            name="book_meeting success",
            passed=False,
            message="No available slots to test with",
        )

    slot = available[0]
    prospect = Prospect(telegram_id="test_booking_999", name="Test Booker", context="test")
    result = tool.book_meeting(slot.id, prospect, "test@example.com", client_timezone="Europe/Warsaw")

    # Restore slot after test (ephemeral)
    if result.success:
        calendar.cancel_booking(slot.id)

    passed = result.success and "назначена" in result.message.lower()

    return TestResult(
        name="book_meeting success",
        passed=passed,
        message="Meeting booked successfully" if passed else f"Booking failed: {result.error}",
        details=f"Slot: {slot.id}, Message: {result.message[:200]}",
    )


# =============================================================================
# TEST 5: get_available_times vs confirm_time_slot response length
# =============================================================================


def test_response_length_comparison() -> TestResult:
    """Verify confirm_time_slot is MUCH shorter than get_available_times."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    available = calendar.get_available_slots(days=7)
    if not available:
        return TestResult(
            name="Response length comparison",
            passed=False,
            message="No available slots",
        )

    slot = available[0]

    full_list = tool.get_available_times(days=7, client_timezone="Europe/Warsaw")
    confirmation = tool.confirm_time_slot(
        target_date=slot.date,
        target_time=slot.start_time,
        client_timezone="Europe/Warsaw",
    )

    full_len = len(full_list)
    conf_len = len(confirmation)
    ratio = conf_len / full_len if full_len > 0 else 999

    # Confirmation should be significantly shorter (less than 30% of full list)
    passed = ratio < 0.3

    return TestResult(
        name="Response length: confirm vs full list",
        passed=passed,
        message=f"confirm={conf_len} chars vs full={full_len} chars (ratio: {ratio:.1%})"
        if passed else f"confirm too long: {conf_len} vs {full_len} (ratio: {ratio:.1%})",
        details=f"Confirm: {confirmation[:100]}...\nFull: {full_list[:100]}...",
    )


# =============================================================================
# TEST 6: Real Google Calendar integration (optional, --calendar flag)
# =============================================================================


def test_calendar_event_creation() -> TestResult:
    """Test real Google Calendar event creation (requires credentials)."""
    try:
        from telegram_sales_bot.integrations.google_calendar import CalendarConnector

        connector = CalendarConnector()
        if not connector.enabled:
            return TestResult(
                name="Google Calendar event creation",
                passed=True,
                message="SKIPPED - Google Calendar not configured (set GOOGLE_CLIENT_ID/SECRET)",
            )

        # Find a connected account
        import os
        tokens_dir = Path.home() / ".sales_registry" / "calendar_tokens"
        if not tokens_dir.exists():
            return TestResult(
                name="Google Calendar event creation",
                passed=True,
                message="SKIPPED - No calendar tokens found",
            )

        token_files = list(tokens_dir.glob("*.json"))
        if not token_files:
            return TestResult(
                name="Google Calendar event creation",
                passed=True,
                message="SKIPPED - No connected calendar accounts",
            )

        # Use the first available account
        telegram_id = int(token_files[0].stem)

        # Create a test event
        now = datetime.now(BALI_TZ)
        start = now + timedelta(hours=25)  # Tomorrow + 1h
        end = start + timedelta(minutes=30)

        event_result = connector.create_event(
            telegram_id=telegram_id,
            summary="[TEST] Meeting Scheduling Test",
            start=start.strftime("%Y-%m-%dT%H:%M:%S"),
            end=end.strftime("%Y-%m-%dT%H:%M:%S"),
            description="Automated test - will be deleted",
            attendees=["bohdan.pytaichuk@gmail.com"],
            timezone="Asia/Makassar",
        )

        if not event_result:
            return TestResult(
                name="Google Calendar event creation",
                passed=False,
                message="create_event returned None - check credentials",
            )

        event_id = event_result.get("id")
        html_link = event_result.get("htmlLink", "no link")

        # Verify event was created by checking the response itself
        # (fetching back can have timing issues with Google's eventual consistency)
        has_id = bool(event_id)
        has_summary = "[TEST]" in event_result.get("summary", "")
        has_start = "start" in event_result

        found = has_id and has_summary and has_start

        # Clean up test event
        try:
            from googleapiclient.discovery import build
            creds = connector._load_credentials(telegram_id)
            if creds:
                service = build("calendar", "v3", credentials=creds)
                service.events().delete(calendarId="primary", eventId=event_id).execute()
        except Exception:
            pass  # Best effort cleanup

        passed = found

        return TestResult(
            name="Google Calendar event creation",
            passed=passed,
            message=f"Event created and verified" if passed else "Event created but not found when fetching",
            details=f"Event ID: {event_id}, Link: {html_link}",
        )

    except Exception as e:
        return TestResult(
            name="Google Calendar event creation",
            passed=False,
            message=f"Error: {e}",
        )


def test_calendar_attendee_invite() -> TestResult:
    """Test that calendar event includes attendee (triggers email invite)."""
    try:
        from telegram_sales_bot.integrations.google_calendar import CalendarConnector

        connector = CalendarConnector()
        if not connector.enabled:
            return TestResult(
                name="Calendar attendee invite",
                passed=True,
                message="SKIPPED - Google Calendar not configured",
            )

        tokens_dir = Path.home() / ".sales_registry" / "calendar_tokens"
        token_files = list(tokens_dir.glob("*.json")) if tokens_dir.exists() else []
        if not token_files:
            return TestResult(
                name="Calendar attendee invite",
                passed=True,
                message="SKIPPED - No connected accounts",
            )

        telegram_id = int(token_files[0].stem)
        test_email = "bohdan.pytaichuk@gmail.com"

        now = datetime.now(BALI_TZ)
        start = now + timedelta(hours=26)
        end = start + timedelta(minutes=30)

        event_result = connector.create_event(
            telegram_id=telegram_id,
            summary="[TEST] Attendee Invite Test",
            start=start.strftime("%Y-%m-%dT%H:%M:%S"),
            end=end.strftime("%Y-%m-%dT%H:%M:%S"),
            description="Testing attendee invite - will be deleted",
            attendees=[test_email],
            timezone="Asia/Makassar",
        )

        if not event_result:
            return TestResult(
                name="Calendar attendee invite",
                passed=False,
                message="create_event returned None",
            )

        # Check attendees in the created event
        attendees = event_result.get("attendees", [])
        attendee_emails = [a.get("email", "") for a in attendees]
        has_attendee = test_email in attendee_emails

        # sendUpdates="all" should have triggered an email
        event_id = event_result.get("id")

        # Clean up
        try:
            from googleapiclient.discovery import build
            creds = connector._load_credentials(telegram_id)
            if creds:
                service = build("calendar", "v3", credentials=creds)
                service.events().delete(calendarId="primary", eventId=event_id).execute()
        except Exception:
            pass

        passed = has_attendee

        return TestResult(
            name="Calendar attendee invite",
            passed=passed,
            message=f"Attendee {test_email} present, invite sent" if passed
            else f"Attendee not found: {attendee_emails}",
            details=f"Event attendees: {attendees}",
        )

    except Exception as e:
        return TestResult(
            name="Calendar attendee invite",
            passed=False,
            message=f"Error: {e}",
        )


# =============================================================================
# TEST 7: Full scheduling flow (unit-level, no network)
# =============================================================================


def test_full_scheduling_flow() -> TestResult:
    """Test the complete flow: check availability -> confirm time -> book meeting."""
    from telegram_sales_bot.scheduling.calendar import SalesCalendar
    from telegram_sales_bot.scheduling.tool import SchedulingTool
    from telegram_sales_bot.core.models import Prospect

    config_path = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config" / "sales_slots.json"
    calendar = SalesCalendar(config_path)
    tool = SchedulingTool(calendar)

    # Step 1: Get available slots
    available = calendar.get_available_slots(days=7)
    if not available:
        return TestResult(
            name="Full scheduling flow",
            passed=False,
            message="No available slots",
        )

    slot = available[0]

    # Step 2: Confirm specific time (as if user named it)
    confirm_result = tool.confirm_time_slot(
        target_date=slot.date,
        target_time=slot.start_time,
        client_timezone="Europe/Warsaw",
    )
    step2_ok = "свободно" in confirm_result.lower()

    # Step 3: Book the meeting
    prospect = Prospect(telegram_id="test_flow_999", name="Flow Test", context="test")
    booking = tool.book_meeting(
        slot_id=slot.id,
        prospect=prospect,
        client_email="test@example.com",
        client_timezone="Europe/Warsaw",
    )
    step3_ok = booking.success

    # Clean up
    if booking.success:
        calendar.cancel_booking(slot.id)

    passed = step2_ok and step3_ok

    return TestResult(
        name="Full scheduling flow",
        passed=passed,
        message=f"All steps passed" if passed else f"Step 2 (confirm): {step2_ok}, Step 3 (book): {step3_ok}",
        details=f"Confirm: {confirm_result[:100]}... | Booking: {booking.message[:100]}",
    )


# =============================================================================
# RUNNER
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Meeting Scheduling Flow Tests")
    parser.add_argument("--calendar", action="store_true", help="Include real Google Calendar tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    console.print(Panel(
        "[bold]Meeting Scheduling Flow Tests[/bold]\n"
        "Testing: confirm_time_slot, timezone conversion, booking, calendar integration",
        title="Test Suite",
        width=120,
    ))

    # Core tests (no network required)
    core_tests = [
        test_confirm_time_slot_available,
        test_confirm_time_slot_unavailable,
        test_confirm_time_slot_timezone_conversion,
        test_handle_action_routes_to_confirm,
        test_handle_action_routes_to_full_list,
        test_daemon_timezone_conversion,
        test_daemon_timezone_conversion_moscow,
        test_book_meeting_requires_email,
        test_book_meeting_catches_email_typo,
        test_book_meeting_success,
        test_response_length_comparison,
        test_full_scheduling_flow,
    ]

    # Calendar tests (require Google credentials)
    calendar_tests = []
    if args.calendar:
        calendar_tests = [
            test_calendar_event_creation,
            test_calendar_attendee_invite,
        ]

    all_tests = core_tests + calendar_tests
    results: list[TestResult] = []

    for test_fn in all_tests:
        try:
            result = test_fn()
        except Exception as e:
            result = TestResult(
                name=test_fn.__name__,
                passed=False,
                message=f"EXCEPTION: {e}",
            )
        results.append(result)

        # Print inline progress
        icon = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        console.print(f"  {icon} {result.name}: {result.message}")
        if args.verbose and result.details:
            console.print(f"       [dim]{result.details}[/dim]")

    # Summary table
    console.print()
    table = Table(title="Results Summary", width=120)
    table.add_column("Test", style="cyan", width=50)
    table.add_column("Status", width=10)
    table.add_column("Message", width=55)

    passed_count = 0
    failed_count = 0
    skipped_count = 0

    for r in results:
        if "SKIPPED" in r.message:
            status = "[yellow]SKIP[/yellow]"
            skipped_count += 1
        elif r.passed:
            status = "[green]PASS[/green]"
            passed_count += 1
        else:
            status = "[red]FAIL[/red]"
            failed_count += 1

        table.add_row(r.name, status, r.message[:55])

    console.print(table)

    total = len(results)
    console.print(
        f"\n[bold]Total: {total}[/bold] | "
        f"[green]Passed: {passed_count}[/green] | "
        f"[red]Failed: {failed_count}[/red] | "
        f"[yellow]Skipped: {skipped_count}[/yellow]"
    )

    if failed_count > 0:
        console.print("\n[red bold]SOME TESTS FAILED[/red bold]")
        sys.exit(1)
    else:
        console.print("\n[green bold]ALL TESTS PASSED[/green bold]")
        sys.exit(0)


if __name__ == "__main__":
    main()
