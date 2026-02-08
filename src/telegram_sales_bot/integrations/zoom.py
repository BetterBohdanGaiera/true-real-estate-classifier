"""
Zoom Booking Service.

Wrapper around Zoom API client for creating meetings.
Integrates with the Telegram agent for scheduling calls.

Uses Server-to-Server OAuth with credentials from ~/.zoom_credentials/credentials.json.
The credentials file should contain:
    {
        "account_id": "...",
        "client_id": "...",
        "client_secret": "..."
    }

Example:
    >>> from telegram_sales_bot.integrations.zoom import ZoomBookingService
    >>> from datetime import datetime, timezone, timezone
    >>>
    >>> service = ZoomBookingService()
    >>> if service.enabled:
    ...     url = service.create_meeting(
    ...         topic="Sales Call",
    ...         start_time=datetime(2026, 1, 25, 14, 0),
    ...         duration=30,
    ...         invitee_email="client@example.com"
    ...     )
    ...     print(f"Meeting URL: {url}")
"""

import json
import time
from datetime import datetime, timezone, timezone
from pathlib import Path
from typing import Optional

import requests

# Zoom API configuration
CREDENTIALS_DIR = Path.home() / ".zoom_credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

BASE_URL = "https://api.zoom.us/v2"
TOKEN_URL = "https://zoom.us/oauth/token"

# Default timezone for Bali
DEFAULT_TIMEZONE = "Asia/Makassar"

def _load_credentials() -> Optional[dict]:
    """
    Load Zoom API credentials from file.

    Returns:
        Dictionary with account_id, client_id, client_secret if valid,
        None if credentials file doesn't exist or is invalid.
    """
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            creds = json.load(f)
        required = ["account_id", "client_id", "client_secret"]
        if all(k in creds for k in required):
            return creds
    except (json.JSONDecodeError, IOError):
        pass
    return None

def _get_access_token(creds: dict) -> Optional[str]:
    """
    Get access token using Server-to-Server OAuth.

    Uses token caching to avoid unnecessary API calls.
    Token is cached in ~/.zoom_credentials/token.json.

    Args:
        creds: Dictionary with account_id, client_id, client_secret.

    Returns:
        Access token string if successful, None if authentication fails.
    """
    # Check for cached token
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, encoding="utf-8") as f:
                token_data = json.load(f)
            # Check if token is still valid (with 5 min buffer)
            if token_data.get("expires_at", 0) > time.time() + 300:
                return token_data.get("access_token")
        except (json.JSONDecodeError, IOError):
            pass

    # Request new token
    auth = (creds["client_id"], creds["client_secret"])
    params = {
        "grant_type": "account_credentials",
        "account_id": creds["account_id"]
    }

    try:
        resp = requests.post(TOKEN_URL, auth=auth, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()

        # Cache token
        token_data = {
            "access_token": data["access_token"],
            "expires_at": time.time() + data.get("expires_in", 3600)
        }
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f)

        return data["access_token"]
    except requests.RequestException:
        return None

class ZoomBookingService:
    """
    Service for creating Zoom meetings.

    Uses Server-to-Server OAuth with credentials from ~/.zoom_credentials/credentials.json.

    Attributes:
        credentials: Zoom API credentials (account_id, client_id, client_secret).
        enabled: Whether Zoom integration is enabled (credentials available).

    Example:
        >>> service = ZoomBookingService()
        >>> if service.enabled:
        ...     url = service.create_meeting(
        ...         topic="Consultation - Real Estate",
        ...         start_time=datetime(2026, 1, 25, 14, 0),
        ...         duration=30,
        ...         invitee_email="client@example.com"
        ...     )
        ...     print(f"Meeting URL: {url}")
    """

    def __init__(self) -> None:
        """
        Initialize Zoom booking service.

        Automatically loads credentials from ~/.zoom_credentials/credentials.json.
        If credentials are not available, the service will be disabled (enabled=False).
        """
        self.credentials = _load_credentials()
        self.enabled = self.credentials is not None

    def create_meeting(
        self,
        topic: str,
        start_time: datetime,
        duration: int = 30,
        invitee_email: Optional[str] = None,
        invitee_name: Optional[str] = None,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> Optional[str]:
        """
        Create a Zoom meeting.

        Args:
            topic: Meeting topic/title (e.g., "Sales Consultation").
            start_time: Meeting start time as a datetime object.
            duration: Meeting duration in minutes (default: 30).
            invitee_email: Optional invitee email for calendar invite reference.
            invitee_name: Optional invitee name for meeting agenda.
            timezone: Timezone for the meeting (default: Asia/Makassar for Bali).

        Returns:
            Zoom join URL if successful (e.g., "https://zoom.us/j/123456789"),
            None if meeting creation fails or service is not enabled.

        Example:
            >>> from datetime import datetime, timezone, timezone
            >>> service = ZoomBookingService()
            >>> url = service.create_meeting(
            ...     topic="Consultation - John Doe",
            ...     start_time=datetime(2026, 1, 25, 14, 0),
            ...     duration=30,
            ...     invitee_email="john@example.com"
            ... )
            >>> print(url)  # https://zoom.us/j/123456789...
        """
        if not self.enabled:
            return None

        try:
            # Get access token
            access_token = _get_access_token(self.credentials)
            if not access_token:
                return None

            # Format start time for Zoom API (ISO 8601)
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")

            # Create meeting payload
            payload = {
                "topic": topic,
                "type": 2,  # Scheduled meeting
                "start_time": start_time_str,
                "duration": duration,
                "timezone": timezone,
                "settings": {
                    "host_video": True,
                    "participant_video": True,
                    "join_before_host": False,
                    "mute_upon_entry": False,
                    "waiting_room": True,
                    "audio": "both",
                    "auto_recording": "none",
                }
            }

            # Add agenda with invitee info if provided
            if invitee_email or invitee_name:
                invitee_display = invitee_name or invitee_email
                payload["agenda"] = f"Meeting with {invitee_display}"

            # Make API call
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"{BASE_URL}/users/me/meetings",
                headers=headers,
                json=payload,
                timeout=10,
            )

            if response.status_code == 201:
                meeting_data = response.json()
                return meeting_data.get("join_url")
            else:
                # Log error for debugging
                print(f"Zoom API error: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            print(f"Failed to create Zoom meeting: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error creating Zoom meeting: {e}")
            return None

    def check_setup(self) -> dict:
        """
        Check Zoom integration setup status.

        Returns:
            Dictionary with setup status information:
            - credentials_file_exists: bool
            - credentials_valid: bool
            - authenticated: bool
            - user_email: str (if authenticated)

        Example:
            >>> service = ZoomBookingService()
            >>> status = service.check_setup()
            >>> print(status)
            {'credentials_file_exists': True, 'credentials_valid': True, 'authenticated': True, 'user_email': 'user@company.com'}
        """
        status = {
            "credentials_dir": str(CREDENTIALS_DIR),
            "credentials_file_exists": CREDENTIALS_FILE.exists(),
            "credentials_valid": False,
            "authenticated": False,
        }

        if self.credentials:
            status["credentials_valid"] = True
            token = _get_access_token(self.credentials)
            if token:
                status["authenticated"] = True
                # Try to get user info to verify token works
                try:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    }
                    response = requests.get(
                        f"{BASE_URL}/users/me",
                        headers=headers,
                        timeout=10,
                    )
                    if response.status_code == 200:
                        user_data = response.json()
                        status["user_email"] = user_data.get("email", "unknown")
                        status["user_id"] = user_data.get("id")
                except requests.RequestException:
                    pass

        return status

# Simple test
if __name__ == "__main__":
    from datetime import timedelta

    print("=== Zoom Booking Service Test ===\n")

    service = ZoomBookingService()

    print("1. Checking setup status...")
    status = service.check_setup()
    for key, value in status.items():
        print(f"   {key}: {value}")
    print()

    print(f"2. Service enabled: {service.enabled}")
    print()

    if service.enabled:
        print("3. Creating test meeting...")
        # Schedule meeting for tomorrow at 2 PM
        meeting_time = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        url = service.create_meeting(
            topic="Test Meeting - Sales Consultation",
            start_time=meeting_time,
            duration=30,
            invitee_email="test@example.com",
            invitee_name="Test Client"
        )
        if url:
            print(f"   Meeting created successfully!")
            print(f"   Join URL: {url}")
        else:
            print("   Failed to create meeting")
    else:
        print("3. Skipping meeting creation (service not enabled)")
        print("\n   To enable Zoom integration:")
        print(f"   1. Create directory: mkdir -p {CREDENTIALS_DIR}")
        print(f"   2. Create credentials file: {CREDENTIALS_FILE}")
        print('   3. Add credentials: {"account_id": "...", "client_id": "...", "client_secret": "..."}')
