"""Google Calendar API Client.

Client for querying calendars from multiple Google accounts.
Uses stored refresh tokens to call API without re-authentication.

Environment Variables:
    GOOGLE_CALENDAR_SKILL_PATH: Skill root path (default: parent of parent of this file)
    GOOGLE_CALENDAR_TIMEOUT: API request timeout in seconds (default: 30)
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import google.auth
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import httplib2

# Load settings from environment variables
DEFAULT_TIMEOUT = int(os.environ.get("GOOGLE_CALENDAR_TIMEOUT", "30"))


class CalendarClient:
    """Calendar client for a single Google account."""

    SCOPES = ["https://www.googleapis.com/auth/calendar"]  # Read/write permissions

    def __init__(
        self,
        account_name: str,
        base_path: Optional[Path] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Args:
            account_name: Account identifier (e.g., 'work', 'personal')
            base_path: Skill root path (env var GOOGLE_CALENDAR_SKILL_PATH or default)
            timeout: API request timeout (seconds)
        """
        self.account_name = account_name
        self.timeout = timeout

        # Path priority: argument > environment variable > default
        if base_path:
            self.base_path = base_path
        elif os.environ.get("GOOGLE_CALENDAR_SKILL_PATH"):
            self.base_path = Path(os.environ["GOOGLE_CALENDAR_SKILL_PATH"])
        else:
            self.base_path = Path(__file__).parent.parent

        self.creds = self._load_credentials()

    def _load_credentials(self):
        """Load and refresh credentials from stored refresh token."""
        token_path = self.base_path / f"accounts/{self.account_name}.json"

        if not token_path.exists():
            raise FileNotFoundError(
                f"Token for account '{self.account_name}' not found. "
                f"Please run setup_auth.py --account {self.account_name} first"
            )

        with open(token_path) as f:
            token_data = json.load(f)

        # Check if ADC format (has client_id but no type)
        if "client_id" in token_data and "type" not in token_data:
            # gcloud ADC format - includes quota project
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=self.SCOPES,
            )
            # Set quota project (if present)
            quota_project = token_data.get("quota_project_id")
            if quota_project:
                creds = creds.with_quota_project(quota_project)
        else:
            # Standard OAuth token format
            creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)

        # Auto-refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(token_path, "w") as f:
                json.dump(json.loads(creds.to_json()), f, indent=2)

        return creds

    def get_events(
        self,
        days: int = 7,
        calendar_id: str = "primary",
        max_results: int = 100,
    ) -> list[dict]:
        """Fetch events for the next N days.

        Args:
            days: Number of days to query
            calendar_id: Calendar ID (default: primary)
            max_results: Maximum number of results

        Returns:
            List of events (dict list)
        """
        # Build service with credentials
        service = build("calendar", "v3", credentials=self.creds)

        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days)).isoformat() + "Z"

        events = []
        page_token = None

        while True:
            result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                    pageToken=page_token,
                )
                .execute()
            )

            for event in result.get("items", []):
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))

                events.append(
                    {
                        "account": self.account_name,
                        "id": event.get("id"),
                        "summary": event.get("summary", "(No title)"),
                        "start": start,
                        "end": end,
                        "all_day": "date" in event["start"],
                        "location": event.get("location"),
                        "description": event.get("description"),
                        "attendees": [
                            a.get("email") for a in event.get("attendees", [])
                        ],
                        "status": event.get("status"),
                        "html_link": event.get("htmlLink"),
                    }
                )

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return events

    def list_calendars(self) -> list[dict]:
        """List all available calendars."""
        service = build("calendar", "v3", credentials=self.creds)

        calendars = []
        page_token = None

        while True:
            result = (
                service.calendarList().list(pageToken=page_token).execute()
            )

            for cal in result.get("items", []):
                calendars.append(
                    {
                        "id": cal.get("id"),
                        "summary": cal.get("summary"),
                        "primary": cal.get("primary", False),
                        "access_role": cal.get("accessRole"),
                    }
                )

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return calendars

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None,
        calendar_id: str = "primary",
        timezone: str = "Asia/Seoul",
    ) -> dict:
        """Create a new event.

        Args:
            summary: Event title
            start: Start time (ISO format: 2024-01-15T09:00:00 or 2024-01-15)
            end: End time (ISO format)
            description: Event description
            location: Location
            attendees: List of attendee emails
            calendar_id: Calendar ID (default: primary)
            timezone: Timezone (default: Asia/Seoul)

        Returns:
            Created event info
        """
        service = build("calendar", "v3", credentials=self.creds)

        # Check if all-day event (no T means all-day)
        is_all_day = "T" not in start

        event = {
            "summary": summary,
        }

        if is_all_day:
            event["start"] = {"date": start}
            event["end"] = {"date": end}
        else:
            event["start"] = {"dateTime": start, "timeZone": timezone}
            event["end"] = {"dateTime": end, "timeZone": timezone}

        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]

        result = service.events().insert(calendarId=calendar_id, body=event).execute()

        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
            "start": result["start"].get("dateTime", result["start"].get("date")),
            "end": result["end"].get("dateTime", result["end"].get("date")),
            "html_link": result.get("htmlLink"),
            "status": "created",
        }

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        calendar_id: str = "primary",
        timezone: str = "Asia/Seoul",
    ) -> dict:
        """Update an existing event.

        Args:
            event_id: Event ID to update
            summary: New title (None to keep current)
            start: New start time (None to keep current)
            end: New end time (None to keep current)
            description: New description (None to keep current)
            location: New location (None to keep current)
            calendar_id: Calendar ID
            timezone: Timezone

        Returns:
            Updated event info
        """
        service = build("calendar", "v3", credentials=self.creds)

        # Get existing event
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Update only changed fields
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location

        if start is not None:
            is_all_day = "T" not in start
            if is_all_day:
                event["start"] = {"date": start}
            else:
                event["start"] = {"dateTime": start, "timeZone": timezone}

        if end is not None:
            is_all_day = "T" not in end
            if is_all_day:
                event["end"] = {"date": end}
            else:
                event["end"] = {"dateTime": end, "timeZone": timezone}

        result = (
            service.events()
            .update(calendarId=calendar_id, eventId=event_id, body=event)
            .execute()
        )

        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
            "start": result["start"].get("dateTime", result["start"].get("date")),
            "end": result["end"].get("dateTime", result["end"].get("date")),
            "html_link": result.get("htmlLink"),
            "status": "updated",
        }

    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict:
        """Delete an event.

        Args:
            event_id: Event ID to delete
            calendar_id: Calendar ID

        Returns:
            Deletion result
        """
        service = build("calendar", "v3", credentials=self.creds)

        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        return {
            "id": event_id,
            "status": "deleted",
        }


class ADCCalendarClient:
    """Calendar client using Application Default Credentials.

    Uses account authenticated via gcloud auth application-default login.
    Can be used immediately without separate token file.
    """

    SCOPES = ["https://www.googleapis.com/auth/calendar"]  # Read/write permissions

    def __init__(self, account_name: str = "default", timeout: int = DEFAULT_TIMEOUT):
        """
        Args:
            account_name: Account identifier (for display)
            timeout: API request timeout (seconds)
        """
        self.account_name = account_name
        self.timeout = timeout
        self.creds, self.project = google.auth.default(scopes=self.SCOPES)

    def get_events(
        self,
        days: int = 7,
        calendar_id: str = "primary",
        max_results: int = 100,
    ) -> list[dict]:
        """Fetch events for the next N days."""
        http = httplib2.Http(timeout=self.timeout)
        http = google.auth.transport.requests.AuthorizedSession(self.creds)
        service = build("calendar", "v3", credentials=self.creds)

        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days)).isoformat() + "Z"

        events = []
        page_token = None

        while True:
            result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                    pageToken=page_token,
                )
                .execute()
            )

            for event in result.get("items", []):
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))

                events.append(
                    {
                        "account": self.account_name,
                        "id": event.get("id"),
                        "summary": event.get("summary", "(No title)"),
                        "start": start,
                        "end": end,
                        "all_day": "date" in event["start"],
                        "location": event.get("location"),
                        "description": event.get("description"),
                        "attendees": [
                            a.get("email") for a in event.get("attendees", [])
                        ],
                        "status": event.get("status"),
                        "html_link": event.get("htmlLink"),
                    }
                )

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return events

    def list_calendars(self) -> list[dict]:
        """List all available calendars."""
        service = build("calendar", "v3", credentials=self.creds)

        calendars = []
        page_token = None

        while True:
            result = service.calendarList().list(pageToken=page_token).execute()

            for cal in result.get("items", []):
                calendars.append(
                    {
                        "id": cal.get("id"),
                        "summary": cal.get("summary"),
                        "primary": cal.get("primary", False),
                        "access_role": cal.get("accessRole"),
                    }
                )

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return calendars

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None,
        calendar_id: str = "primary",
        timezone: str = "Asia/Seoul",
    ) -> dict:
        """Create a new event."""
        service = build("calendar", "v3", credentials=self.creds)

        is_all_day = "T" not in start
        event = {"summary": summary}

        if is_all_day:
            event["start"] = {"date": start}
            event["end"] = {"date": end}
        else:
            event["start"] = {"dateTime": start, "timeZone": timezone}
            event["end"] = {"dateTime": end, "timeZone": timezone}

        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]

        result = service.events().insert(calendarId=calendar_id, body=event).execute()

        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
            "start": result["start"].get("dateTime", result["start"].get("date")),
            "end": result["end"].get("dateTime", result["end"].get("date")),
            "html_link": result.get("htmlLink"),
            "status": "created",
        }

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        calendar_id: str = "primary",
        timezone: str = "Asia/Seoul",
    ) -> dict:
        """Update an existing event."""
        service = build("calendar", "v3", credentials=self.creds)

        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location

        if start is not None:
            is_all_day = "T" not in start
            if is_all_day:
                event["start"] = {"date": start}
            else:
                event["start"] = {"dateTime": start, "timeZone": timezone}

        if end is not None:
            is_all_day = "T" not in end
            if is_all_day:
                event["end"] = {"date": end}
            else:
                event["end"] = {"dateTime": end, "timeZone": timezone}

        result = (
            service.events()
            .update(calendarId=calendar_id, eventId=event_id, body=event)
            .execute()
        )

        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
            "start": result["start"].get("dateTime", result["start"].get("date")),
            "end": result["end"].get("dateTime", result["end"].get("date")),
            "html_link": result.get("htmlLink"),
            "status": "updated",
        }

    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict:
        """Delete an event."""
        service = build("calendar", "v3", credentials=self.creds)

        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        return {
            "id": event_id,
            "status": "deleted",
        }


def get_all_accounts(base_path: Optional[Path] = None) -> list[str]:
    """Return all registered account names."""
    base_path = base_path or Path(__file__).parent.parent
    accounts_dir = base_path / "accounts"

    if not accounts_dir.exists():
        return []

    return [
        f.stem
        for f in accounts_dir.glob("*.json")
        if f.stem not in ("credentials",)
    ]


def fetch_all_events(days: int = 7, base_path: Optional[Path] = None) -> dict:
    """Fetch and integrate events from all accounts.

    Args:
        days: Number of days to query
        base_path: Skill root path

    Returns:
        {
            "accounts": ["work", "personal"],
            "events": [...],
            "errors": {"account_name": "error message"},
            "total": 10,
            "conflicts": [...]
        }
    """
    accounts = get_all_accounts(base_path)
    all_events = []
    errors = {}

    for account in accounts:
        try:
            client = CalendarClient(account, base_path)
            events = client.get_events(days=days)
            all_events.extend(events)
        except Exception as e:
            errors[account] = str(e)

    # Sort by time
    all_events.sort(key=lambda x: x["start"])

    # Detect conflicts
    conflicts = detect_conflicts(all_events)

    return {
        "accounts": accounts,
        "events": all_events,
        "errors": errors,
        "total": len(all_events),
        "conflicts": conflicts,
    }


def detect_conflicts(events: list[dict]) -> list[dict]:
    """Detect scheduling conflicts between events.

    Args:
        events: Time-sorted list of events

    Returns:
        List of conflicting event pairs
    """
    conflicts = []

    for i, event1 in enumerate(events):
        if event1.get("all_day"):
            continue

        for event2 in events[i + 1 :]:
            if event2.get("all_day"):
                continue

            # Same account = not a conflict
            if event1["account"] == event2["account"]:
                continue

            # Compare times
            start1 = datetime.fromisoformat(event1["start"].replace("Z", "+00:00"))
            end1 = datetime.fromisoformat(event1["end"].replace("Z", "+00:00"))
            start2 = datetime.fromisoformat(event2["start"].replace("Z", "+00:00"))
            end2 = datetime.fromisoformat(event2["end"].replace("Z", "+00:00"))

            # If event2 starts after event1 ends, no more comparisons needed
            if start2 >= end1:
                break

            # Check overlap
            if start1 < end2 and start2 < end1:
                conflicts.append(
                    {
                        "event1": {
                            "account": event1["account"],
                            "summary": event1["summary"],
                            "start": event1["start"],
                            "end": event1["end"],
                        },
                        "event2": {
                            "account": event2["account"],
                            "summary": event2["summary"],
                            "start": event2["start"],
                            "end": event2["end"],
                        },
                    }
                )

    return conflicts
