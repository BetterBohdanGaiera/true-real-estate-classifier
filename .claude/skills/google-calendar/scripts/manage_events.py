#!/usr/bin/env python3
"""Google Calendar Event Management CLI.

CLI tool for creating, updating, and deleting events.

Usage:
    # Create event (with time)
    uv run python manage_events.py create \
        --summary "Team Meeting" \
        --start "2026-01-06T14:00:00" \
        --end "2026-01-06T15:00:00" \
        --account work

    # Create all-day event
    uv run python manage_events.py create \
        --summary "Day Off" \
        --start "2026-01-10" \
        --end "2026-01-11" \
        --account personal

    # Update event
    uv run python manage_events.py update \
        --event-id "abc123" \
        --summary "Team Meeting (Updated)" \
        --account work

    # Delete event
    uv run python manage_events.py delete \
        --event-id "abc123" \
        --account work

    # Use ADC
    uv run python manage_events.py create \
        --summary "Test" \
        --start "2026-01-06T10:00:00" \
        --end "2026-01-06T11:00:00" \
        --adc
"""

import argparse
import json
import sys
from pathlib import Path

from calendar_client import CalendarClient, ADCCalendarClient


def cmd_create(args):
    """Create event."""
    if args.adc:
        client = ADCCalendarClient()
    else:
        if not args.account:
            print("❌ --account or --adc required", file=sys.stderr)
            sys.exit(1)
        base_path = Path(__file__).parent.parent
        client = CalendarClient(args.account, base_path)

    attendees = args.attendees.split(",") if args.attendees else None

    result = client.create_event(
        summary=args.summary,
        start=args.start,
        end=args.end,
        description=args.description,
        location=args.location,
        attendees=attendees,
        timezone=args.timezone,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ Event created successfully")
        print(f"   Title: {result['summary']}")
        print(f"   Time: {result['start']} ~ {result['end']}")
        print(f"   ID: {result['id']}")
        print(f"   Link: {result['html_link']}")


def cmd_update(args):
    """Update event."""
    if args.adc:
        client = ADCCalendarClient()
    else:
        if not args.account:
            print("❌ --account or --adc required", file=sys.stderr)
            sys.exit(1)
        base_path = Path(__file__).parent.parent
        client = CalendarClient(args.account, base_path)

    result = client.update_event(
        event_id=args.event_id,
        summary=args.summary,
        start=args.start,
        end=args.end,
        description=args.description,
        location=args.location,
        timezone=args.timezone,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ Event updated successfully")
        print(f"   Title: {result['summary']}")
        print(f"   Time: {result['start']} ~ {result['end']}")
        print(f"   ID: {result['id']}")
        print(f"   Link: {result['html_link']}")


def cmd_delete(args):
    """Delete event."""
    if args.adc:
        client = ADCCalendarClient()
    else:
        if not args.account:
            print("❌ --account or --adc required", file=sys.stderr)
            sys.exit(1)
        base_path = Path(__file__).parent.parent
        client = CalendarClient(args.account, base_path)

    result = client.delete_event(event_id=args.event_id)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ Event deleted successfully")
        print(f"   ID: {result['id']}")


def main():
    parser = argparse.ArgumentParser(description="Google Calendar event management")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # create command
    create_parser = subparsers.add_parser("create", help="Create event")
    create_parser.add_argument("--summary", "-s", required=True, help="Event title")
    create_parser.add_argument("--start", required=True, help="Start time (ISO format)")
    create_parser.add_argument("--end", required=True, help="End time (ISO format)")
    create_parser.add_argument("--description", "-d", help="Description")
    create_parser.add_argument("--location", "-l", help="Location")
    create_parser.add_argument("--attendees", help="Attendees (comma-separated)")
    create_parser.add_argument("--account", "-a", help="Account")
    create_parser.add_argument("--adc", action="store_true", help="Use ADC")
    create_parser.add_argument("--timezone", default="Asia/Seoul", help="Timezone")
    create_parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    # update command
    update_parser = subparsers.add_parser("update", help="Update event")
    update_parser.add_argument("--event-id", required=True, help="Event ID")
    update_parser.add_argument("--summary", "-s", help="New title")
    update_parser.add_argument("--start", help="New start time")
    update_parser.add_argument("--end", help="New end time")
    update_parser.add_argument("--description", "-d", help="New description")
    update_parser.add_argument("--location", "-l", help="New location")
    update_parser.add_argument("--account", "-a", help="Account")
    update_parser.add_argument("--adc", action="store_true", help="Use ADC")
    update_parser.add_argument("--timezone", default="Asia/Seoul", help="Timezone")
    update_parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete event")
    delete_parser.add_argument("--event-id", required=True, help="Event ID")
    delete_parser.add_argument("--account", "-a", help="Account")
    delete_parser.add_argument("--adc", action="store_true", help="Use ADC")
    delete_parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "create":
            cmd_create(args)
        elif args.command == "update":
            cmd_update(args)
        elif args.command == "delete":
            cmd_delete(args)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
