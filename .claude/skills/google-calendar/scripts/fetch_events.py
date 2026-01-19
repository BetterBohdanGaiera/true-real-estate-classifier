#!/usr/bin/env python3
"""Google Calendar Event Fetch CLI.

Called by subagents to return events from a specific account as JSON.

Usage:
    # ADC (Application Default Credentials) - simplest method
    uv run python fetch_events.py --adc --days 7

    # Specific account query
    uv run python fetch_events.py --account work --days 7

    # All accounts query (combined)
    uv run python fetch_events.py --all --days 7

    # List calendars
    uv run python fetch_events.py --adc --list-calendars
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from calendar_client import CalendarClient, ADCCalendarClient, fetch_all_events, get_all_accounts


def format_event_for_display(event: dict, tz: ZoneInfo = None) -> str:
    """Format event for human-readable display."""
    if tz is None:
        tz = ZoneInfo("Asia/Seoul")

    start = event["start"]
    end = event["end"]
    account = event["account"]
    summary = event["summary"]

    # Parse time
    if event.get("all_day"):
        time_str = "All day"
    else:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(tz)
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone(tz)
        time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"

    # Account-specific icon
    icon = "🔵" if account == "work" else "🟢"

    return f"[{time_str}] {icon} {summary} ({account})"


def main():
    parser = argparse.ArgumentParser(
        description="Google Calendar event query"
    )
    parser.add_argument(
        "--account",
        "-a",
        help="Account identifier (e.g., work, personal)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Query events from all accounts",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Number of days to query (default: 7)",
    )
    parser.add_argument(
        "--list-calendars",
        action="store_true",
        help="List calendars",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Output in human-readable format",
    )
    parser.add_argument(
        "--adc",
        action="store_true",
        help="Use Application Default Credentials (gcloud auth application-default login)",
    )

    args = parser.parse_args()
    base_path = Path(__file__).parent.parent

    # ADC mode
    if args.adc:
        try:
            client = ADCCalendarClient(account_name="gcloud")

            # Calendar list
            if args.list_calendars:
                calendars = client.list_calendars()
                if args.json or not args.pretty:
                    print(json.dumps(calendars, ensure_ascii=False, indent=2))
                else:
                    print("📋 ADC account calendars:\n")
                    for cal in calendars:
                        primary = " (primary)" if cal["primary"] else ""
                        print(f"  - {cal['summary']}{primary}")
                        print(f"    ID: {cal['id']}")
                return

            # Event query
            events = client.get_events(days=args.days)

            if args.json or not args.pretty:
                print(json.dumps(events, ensure_ascii=False, indent=2))
            else:
                print(f"📅 ADC account - events for next {args.days} days\n")

                # Group by date
                events_by_date = {}
                for event in events:
                    start = event["start"]
                    if "T" in start:
                        date = start.split("T")[0]
                    else:
                        date = start
                    events_by_date.setdefault(date, []).append(event)

                for date in sorted(events_by_date.keys()):
                    dt = datetime.fromisoformat(date)
                    print(f"### {dt.strftime('%Y-%m-%d (%a)')}")
                    for event in events_by_date[date]:
                        print(f"  {format_event_for_display(event)}")
                    print()

                print(f"📊 Total {len(events)} events")

        except Exception as e:
            print(f"❌ ADC error: {e}", file=sys.stderr)
            print("Please run gcloud auth application-default login", file=sys.stderr)
            sys.exit(1)
        return

    # Check account list
    accounts = get_all_accounts(base_path)
    if not accounts:
        print("❌ No registered accounts.", file=sys.stderr)
        print("Please register an account first with setup_auth.py:", file=sys.stderr)
        print("  uv run python setup_auth.py --account work", file=sys.stderr)
        sys.exit(1)

    # Query all accounts
    if args.all:
        result = fetch_all_events(days=args.days, base_path=base_path)

        if args.json or not args.pretty:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"📅 Events for next {args.days} days\n")

            # Group by date
            events_by_date = {}
            for event in result["events"]:
                start = event["start"]
                if "T" in start:
                    date = start.split("T")[0]
                else:
                    date = start
                events_by_date.setdefault(date, []).append(event)

            for date in sorted(events_by_date.keys()):
                dt = datetime.fromisoformat(date)
                print(f"### {dt.strftime('%Y-%m-%d (%a)')}")
                for event in events_by_date[date]:
                    print(f"  {format_event_for_display(event)}")
                print()

            # Summary
            print(f"📊 Total {result['total']} events")
            for account in result["accounts"]:
                count = len([e for e in result["events"] if e["account"] == account])
                print(f"   - {account}: {count}")

            if result["conflicts"]:
                print(f"\n⚠️  {len(result['conflicts'])} conflicts:")
                for conflict in result["conflicts"]:
                    e1, e2 = conflict["event1"], conflict["event2"]
                    print(f"   - {e1['summary']} ({e1['account']}) ↔ {e2['summary']} ({e2['account']})")

            if result["errors"]:
                print("\n❌ Errors:")
                for account, error in result["errors"].items():
                    print(f"   - {account}: {error}")

        return

    # Query specific account
    if not args.account:
        parser.print_help()
        print()
        print(f"Registered accounts: {', '.join(accounts)}")
        return

    if args.account not in accounts:
        print(f"❌ Account '{args.account}' is not registered.", file=sys.stderr)
        print(f"Registered accounts: {', '.join(accounts)}", file=sys.stderr)
        sys.exit(1)

    try:
        client = CalendarClient(args.account, base_path)

        # Calendar list
        if args.list_calendars:
            calendars = client.list_calendars()
            if args.json:
                print(json.dumps(calendars, ensure_ascii=False, indent=2))
            else:
                print(f"📋 '{args.account}' account calendars:\n")
                for cal in calendars:
                    primary = " (primary)" if cal["primary"] else ""
                    print(f"  - {cal['summary']}{primary}")
                    print(f"    ID: {cal['id']}")
            return

        # Event query
        events = client.get_events(days=args.days)

        if args.json or not args.pretty:
            print(json.dumps(events, ensure_ascii=False, indent=2))
        else:
            print(f"📅 '{args.account}' account - events for next {args.days} days\n")
            for event in events:
                print(f"  {format_event_for_display(event)}")
            print(f"\nTotal {len(events)} events")

    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
