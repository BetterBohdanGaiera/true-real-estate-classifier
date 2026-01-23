# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-api-python-client>=2.0.0",
#   "google-auth>=2.0.0",
#   "google-auth-oauthlib>=1.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///
"""
Calendar Connector - Google Calendar OAuth integration for sales reps.

Handles per-rep Google Calendar authentication and token storage.
Each sales rep can connect their own Google Calendar account.

Token Storage:
    ~/.sales_registry/calendar_tokens/{telegram_id}.json

Usage:
    from sales_agent.registry.calendar_connector import CalendarConnector

    connector = CalendarConnector()

    # Generate OAuth URL for a rep
    auth_url = connector.get_auth_url(telegram_id=123456)

    # Complete OAuth flow with code
    success = await connector.complete_auth(telegram_id=123456, code="...")

    # Get rep's calendar events
    events = connector.get_events(telegram_id=123456, days=7)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv

load_dotenv()


# Token storage directory
TOKENS_DIR = Path.home() / ".sales_registry" / "calendar_tokens"

# Google OAuth configuration
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Manual code entry


class CalendarConnector:
    """
    Google Calendar connector for per-rep OAuth.

    Handles OAuth flow and token management for individual sales reps.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tokens_dir: Optional[Path] = None,
    ):
        """
        Initialize the calendar connector.

        Args:
            client_id: Google OAuth client ID. Defaults to GOOGLE_CLIENT_ID env var.
            client_secret: Google OAuth client secret. Defaults to GOOGLE_CLIENT_SECRET env var.
            tokens_dir: Directory for storing tokens. Defaults to ~/.sales_registry/calendar_tokens/
        """
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        self.tokens_dir = tokens_dir or TOKENS_DIR

        # Ensure tokens directory exists
        self.tokens_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        """Check if Google Calendar integration is configured."""
        return bool(self.client_id and self.client_secret)

    def _get_token_path(self, telegram_id: int) -> Path:
        """Get the token file path for a telegram user."""
        return self.tokens_dir / f"{telegram_id}.json"

    def is_connected(self, telegram_id: int) -> bool:
        """Check if a rep has connected their calendar."""
        token_path = self._get_token_path(telegram_id)
        return token_path.exists()

    def get_auth_url(self, telegram_id: int) -> str:
        """
        Generate the OAuth authorization URL for a rep.

        Args:
            telegram_id: Telegram ID of the rep.

        Returns:
            OAuth authorization URL to redirect the user to.

        Raises:
            RuntimeError: If Google OAuth is not configured.
        """
        if not self.enabled:
            raise RuntimeError(
                "Google Calendar integration not configured. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
            )

        params = {
            "client_id": self.client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": str(telegram_id),  # Include telegram_id for verification
        }

        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def complete_auth(self, telegram_id: int, code: str) -> bool:
        """
        Complete the OAuth flow with the authorization code.

        Args:
            telegram_id: Telegram ID of the rep.
            code: Authorization code from Google OAuth.

        Returns:
            True if authentication successful, False otherwise.
        """
        if not self.enabled:
            return False

        try:
            # Import here to avoid dependency issues
            import httpx

            # Exchange code for tokens
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": REDIRECT_URI,
                    },
                )

                if response.status_code != 200:
                    return False

                token_data = response.json()

            # Save tokens
            token_path = self._get_token_path(telegram_id)
            with open(token_path, "w") as f:
                json.dump(token_data, f, indent=2)

            return True

        except Exception:
            return False

    def _load_credentials(self, telegram_id: int):
        """Load credentials for a rep, refreshing if needed."""
        token_path = self._get_token_path(telegram_id)

        if not token_path.exists():
            return None

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            with open(token_path) as f:
                token_data = json.load(f)

            creds = Credentials(
                token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=SCOPES,
            )

            # Refresh if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                new_token_data = {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": list(creds.scopes),
                }
                with open(token_path, "w") as f:
                    json.dump(new_token_data, f, indent=2)

            return creds

        except Exception:
            return None

    def get_events(
        self,
        telegram_id: int,
        days: int = 7,
        calendar_id: str = "primary",
        max_results: int = 50,
    ) -> list[dict]:
        """
        Get calendar events for a rep.

        Args:
            telegram_id: Telegram ID of the rep.
            days: Number of days to fetch events for.
            calendar_id: Calendar ID to query.
            max_results: Maximum number of events to return.

        Returns:
            List of event dictionaries, or empty list if not connected.
        """
        creds = self._load_credentials(telegram_id)
        if not creds:
            return []

        try:
            from googleapiclient.discovery import build

            service = build("calendar", "v3", credentials=creds)

            now = datetime.utcnow()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(days=days)).isoformat() + "Z"

            result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                )
                .execute()
            )

            events = []
            for event in result.get("items", []):
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))

                events.append({
                    "id": event.get("id"),
                    "summary": event.get("summary", "(No title)"),
                    "start": start,
                    "end": end,
                    "all_day": "date" in event["start"],
                    "location": event.get("location"),
                    "html_link": event.get("htmlLink"),
                })

            return events

        except Exception:
            return []

    def disconnect(self, telegram_id: int) -> bool:
        """
        Disconnect a rep's calendar (remove tokens).

        Args:
            telegram_id: Telegram ID of the rep.

        Returns:
            True if disconnected, False if not connected.
        """
        token_path = self._get_token_path(telegram_id)
        if token_path.exists():
            token_path.unlink()
            return True
        return False

    def get_busy_slots(
        self,
        telegram_id: int,
        date: datetime,
        timezone: str = "Asia/Makassar",
    ) -> list[tuple[datetime, datetime]]:
        """
        Get busy time slots for a rep on a specific date.

        Args:
            telegram_id: Telegram ID of the rep.
            date: Date to check.
            timezone: Timezone for the events.

        Returns:
            List of (start, end) tuples for busy periods.
        """
        events = self.get_events(
            telegram_id=telegram_id,
            days=1,
        )

        busy_slots = []
        for event in events:
            if event.get("all_day"):
                continue

            try:
                start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))

                # Filter for the specific date
                if start.date() == date.date():
                    busy_slots.append((start, end))
            except (ValueError, KeyError):
                continue

        return busy_slots


# Singleton instance for convenience
_connector: Optional[CalendarConnector] = None


def get_connector() -> CalendarConnector:
    """Get or create the global calendar connector instance."""
    global _connector
    if _connector is None:
        _connector = CalendarConnector()
    return _connector
