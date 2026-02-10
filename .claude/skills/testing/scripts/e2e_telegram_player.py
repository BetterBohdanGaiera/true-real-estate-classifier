"""
E2E Telegram Player for stress testing.

Real Telegram integration that sends messages AS the test prospect (@buddah_lucid)
to the agent (@BetterBohdan), replacing the mock PersonaPlayer for E2E tests.

Uses Telethon client with a separate session from the agent's session.

Usage:
    >>> player = E2ETelegramPlayer()
    >>> await player.connect()
    >>> msg_id = await player.send_message("@BetterBohdan", "Hello!")
    >>> response = await player.wait_for_response("@BetterBohdan", timeout=30.0)
    >>> await player.disconnect()
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import User, Message
from telethon.tl.functions.messages import SetTypingRequest, ReadHistoryRequest
from telethon.tl.types import SendMessageTypingAction

# Setup paths for skill imports
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent

# Add telegram skill scripts to path
TELEGRAM_SCRIPTS = SKILLS_BASE / "telegram/scripts"
if str(TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_SCRIPTS))

from telegram_fetch import (
    load_config,
    CONFIG_DIR,
    is_configured,
)

# SESSIONS_DIR is CONFIG_DIR - sessions are stored alongside config
SESSIONS_DIR = CONFIG_DIR


class E2ETelegramPlayer:
    """
    Real Telegram integration for E2E stress testing.

    Sends messages as the test prospect to the agent, enabling full E2E
    conversation testing with real Telegram infrastructure.

    Attributes:
        client: Telethon TelegramClient for the test prospect account
        session_name: Name of the Telethon session file
        last_message_id: ID of the last message received (for polling)

    Example:
        >>> player = E2ETelegramPlayer(session_name="test_prospect")
        >>> await player.connect()
        >>>
        >>> # Send a message to the agent
        >>> msg_id = await player.send_message("@BetterBohdan", "Interested in property")
        >>>
        >>> # Wait for agent response
        >>> response = await player.wait_for_response("@BetterBohdan", timeout=60.0)
        >>> if response:
        ...     print(f"Agent replied: {response}")
        >>>
        >>> # Stress test: rapid fire messages
        >>> msg_ids = await player.send_batch(
        ...     "@BetterBohdan",
        ...     ["Question 1?", "Question 2?", "Question 3?"],
        ...     [0.3, 0.3, 0.0]
        ... )
        >>>
        >>> await player.disconnect()
    """

    def __init__(
        self,
        session_name: str = "test_prospect",
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ):
        """
        Initialize E2E Telegram player for stress testing.

        Args:
            session_name: Telethon session file name (default: "test_prospect").
                          Session file will be loaded from ~/.telegram_dl/sessions/{session_name}.session
            api_id: Telegram API ID. If None, loaded from env TELEGRAM_API_ID
                    or ~/.telegram_dl/config.json
            api_hash: Telegram API hash. If None, loaded from env TELEGRAM_API_HASH
                      or ~/.telegram_dl/config.json

        Raises:
            RuntimeError: If Telegram is not configured and credentials are not provided
        """
        self.session_name = session_name
        self._last_message_ids: dict[str, int] = {}  # Per-chat last seen message ID
        self._entity_cache: dict[str, User] = {}  # Cache resolved entities

        # Load credentials
        if api_id is None or api_hash is None:
            # Try environment variables first
            env_api_id = os.getenv("TELEGRAM_API_ID")
            env_api_hash = os.getenv("TELEGRAM_API_HASH")

            if env_api_id and env_api_hash:
                api_id = int(env_api_id)
                api_hash = env_api_hash
            else:
                # Fall back to config file
                if not is_configured():
                    raise RuntimeError(
                        "Telegram not configured. Provide api_id/api_hash "
                        "or set TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables, "
                        "or configure ~/.telegram_dl/config.json"
                    )
                config = load_config()
                api_id = config.get("api_id")
                api_hash = config.get("api_hash")

        if not api_id or not api_hash:
            raise RuntimeError("Could not load Telegram API credentials")

        # Determine session path
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_path = SESSIONS_DIR / f"{session_name}.session"

        # Initialize Telethon client
        self.client = TelegramClient(str(session_path), api_id, api_hash)
        self._connected = False

    async def connect(self) -> None:
        """
        Connect to Telegram.

        Raises:
            RuntimeError: If session is not authorized (need to run auth script first)

        Example:
            >>> player = E2ETelegramPlayer()
            >>> await player.connect()
            >>> print("Connected as test prospect")
        """
        await self.client.connect()

        if not await self.client.is_user_authorized():
            raise RuntimeError(
                f"Test prospect session '{self.session_name}' not authorized. "
                "Run the authentication script first:\n"
                "\n"
                "  from telethon import TelegramClient\n"
                "  import os\n"
                "\n"
                "  api_id = int(os.getenv('TELEGRAM_API_ID'))\n"
                "  api_hash = os.getenv('TELEGRAM_API_HASH')\n"
                "\n"
                f"  client = TelegramClient('~/.telegram_dl/sessions/{self.session_name}', api_id, api_hash)\n"
                "  await client.start()  # Will prompt for phone + code\n"
                "  await client.disconnect()\n"
            )

        self._connected = True

    async def disconnect(self) -> None:
        """
        Disconnect from Telegram.

        Clears entity cache and resets connection state.

        Example:
            >>> await player.disconnect()
            >>> print("Disconnected")
        """
        self._entity_cache.clear()
        self._last_message_ids.clear()
        self._connected = False
        await self.client.disconnect()

    async def _resolve_entity(self, agent_telegram_id: str) -> User:
        """
        Resolve agent telegram ID to Telethon entity.

        Supports both @username format and numeric IDs.
        Results are cached to avoid repeated API calls.

        Args:
            agent_telegram_id: Agent's telegram ID (@username or numeric string)

        Returns:
            Resolved Telethon entity (User)

        Raises:
            ValueError: If entity cannot be resolved
        """
        # Check cache first
        if agent_telegram_id in self._entity_cache:
            return self._entity_cache[agent_telegram_id]

        entity = None

        # Try username format
        if agent_telegram_id.startswith("@") or not agent_telegram_id.lstrip("-").isdigit():
            try:
                username = agent_telegram_id if agent_telegram_id.startswith("@") else f"@{agent_telegram_id}"
                entity = await self.client.get_entity(username)
            except Exception:
                pass

        # Try numeric ID
        if entity is None and agent_telegram_id.lstrip("-").isdigit():
            try:
                entity = await self.client.get_entity(int(agent_telegram_id))
            except Exception:
                pass

        if entity is None:
            raise ValueError(f"Could not resolve telegram ID: {agent_telegram_id}")

        # Cache for future use
        self._entity_cache[agent_telegram_id] = entity
        return entity

    async def _simulate_typing(
        self,
        entity: User,
        message: str,
        chars_per_second: float = 15.0,
    ) -> None:
        """
        Simulate typing indicator for realistic behavior.

        Duration is based on message length, clamped to reasonable bounds.

        Args:
            entity: Telethon entity to show typing to
            message: Message being "typed" (for duration calculation)
            chars_per_second: Typing speed (default: 15 chars/sec for realistic human)
        """
        # Calculate typing duration: human types ~15-20 chars/second
        typing_duration = len(message) / chars_per_second

        # Clamp to reasonable bounds: min 0.5s, max 4s
        typing_duration = max(0.5, min(typing_duration, 4.0))

        try:
            await self.client(SetTypingRequest(
                peer=entity,
                action=SendMessageTypingAction()
            ))
            await asyncio.sleep(typing_duration)
        except Exception:
            # Typing simulation is not critical, ignore errors
            pass

    async def send_message(
        self,
        agent_telegram_id: str,
        message: str,
        simulate_typing: bool = True,
    ) -> int:
        """
        Send a message to the agent.

        Args:
            agent_telegram_id: Agent's telegram ID (@username or numeric)
            message: Text to send
            simulate_typing: Whether to show typing indicator first (default: True)

        Returns:
            Message ID of sent message

        Raises:
            RuntimeError: If not connected
            ValueError: If agent_telegram_id cannot be resolved

        Example:
            >>> player = E2ETelegramPlayer()
            >>> await player.connect()
            >>> msg_id = await player.send_message("@BetterBohdan", "Hello!")
            >>> print(f"Sent message {msg_id}")
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Resolve entity
        entity = await self._resolve_entity(agent_telegram_id)

        # Optionally show typing indicator
        if simulate_typing:
            await self._simulate_typing(entity, message)

        # Send message
        msg = await self.client.send_message(entity, message)

        return msg.id

    async def wait_for_response(
        self,
        agent_telegram_id: str,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Optional[str]:
        """
        Wait for agent to respond, polling for new messages.

        Tracks the last seen message ID to detect new messages from the agent.
        Marks messages as read after receiving them for realistic simulation.

        Args:
            agent_telegram_id: Agent's telegram ID
            timeout: Max seconds to wait (default: 60.0)
            poll_interval: How often to check for new messages in seconds (default: 1.0)

        Returns:
            Agent's response text, or None if timeout

        Raises:
            RuntimeError: If not connected

        Example:
            >>> response = await player.wait_for_response("@BetterBohdan", timeout=30.0)
            >>> if response:
            ...     print(f"Agent said: {response}")
            ... else:
            ...     print("No response within timeout")
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # Resolve entity
        entity = await self._resolve_entity(agent_telegram_id)

        # Get current last message ID for this chat
        current_last_id = self._last_message_ids.get(agent_telegram_id, 0)

        # If we haven't tracked this chat yet, get the current latest message ID
        if current_last_id == 0:
            async for msg in self.client.iter_messages(entity, limit=1):
                current_last_id = msg.id
                break
            self._last_message_ids[agent_telegram_id] = current_last_id

        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout:
            # Poll for new messages
            try:
                async for msg in self.client.iter_messages(entity, limit=10):
                    # Check if this is a new message from the agent (not us)
                    if msg.id > current_last_id:
                        # Get our own user ID to filter out our messages
                        me = await self.client.get_me()

                        # Check if message is from the agent (not from us)
                        if msg.sender_id != me.id:
                            # Update last seen message ID
                            self._last_message_ids[agent_telegram_id] = msg.id

                            # Mark as read for realistic simulation
                            try:
                                await self.client(ReadHistoryRequest(
                                    peer=entity,
                                    max_id=msg.id
                                ))
                            except Exception:
                                pass  # Read acknowledgment is not critical

                            return msg.text or ""
                    break  # Only check the most recent messages
            except Exception as e:
                # Log error but continue polling
                pass

            await asyncio.sleep(poll_interval)

        return None  # Timeout

    async def send_batch(
        self,
        agent_telegram_id: str,
        messages: list[str],
        delays: list[float],
    ) -> list[int]:
        """
        Send multiple messages with controlled delays for stress testing.

        Useful for simulating rapid-fire messages or testing the agent's
        ability to handle message batching.

        Args:
            agent_telegram_id: Agent's telegram ID
            messages: List of messages to send
            delays: List of delays (in seconds) AFTER each message.
                    If shorter than messages, last delay is used for remaining.
                    If longer, extra delays are ignored.

        Returns:
            List of message IDs in order they were sent

        Raises:
            RuntimeError: If not connected
            ValueError: If messages list is empty

        Example:
            >>> # Rapid fire: 3 messages within 1 second
            >>> msg_ids = await player.send_batch(
            ...     "@BetterBohdan",
            ...     ["Question 1?", "Question 2?", "Question 3?"],
            ...     [0.3, 0.3, 0.0]  # Short delays between messages
            ... )
            >>> print(f"Sent {len(msg_ids)} messages")

            >>> # Simulating impatient user
            >>> msg_ids = await player.send_batch(
            ...     "@BetterBohdan",
            ...     ["Hello?", "Are you there?", "???"],
            ...     [5.0, 3.0, 0.0]  # Decreasing patience
            ... )
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        if not messages:
            raise ValueError("Messages list cannot be empty")

        message_ids: list[int] = []

        for i, message in enumerate(messages):
            # Send message (no typing simulation for stress test - we want to be fast)
            msg_id = await self.send_message(
                agent_telegram_id,
                message,
                simulate_typing=False  # Skip typing for rapid fire
            )
            message_ids.append(msg_id)

            # Wait specified delay before next message (if not the last one)
            if i < len(messages) - 1:
                # Get delay: use corresponding delay or last available delay
                delay_idx = min(i, len(delays) - 1)
                delay = delays[delay_idx] if delay_idx >= 0 and delays else 0.0

                if delay > 0:
                    await asyncio.sleep(delay)

        return message_ids

    async def get_me(self) -> dict:
        """
        Get info about the authenticated test prospect account.

        Returns:
            Dict with account info: id, username, first_name, last_name

        Raises:
            RuntimeError: If not connected

        Example:
            >>> info = await player.get_me()
            >>> print(f"Logged in as: {info['first_name']} (@{info['username']})")
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        me = await self.client.get_me()
        return {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
        }

    async def get_chat_history(
        self,
        agent_telegram_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Get recent messages from the conversation with the agent.

        Useful for debugging and verifying conversation state.

        Args:
            agent_telegram_id: Agent's telegram ID
            limit: Maximum number of messages to retrieve (default: 20)

        Returns:
            List of message dicts with: id, sender, text, date, is_from_agent

        Raises:
            RuntimeError: If not connected

        Example:
            >>> history = await player.get_chat_history("@BetterBohdan", limit=10)
            >>> for msg in history:
            ...     sender = "Agent" if msg['is_from_agent'] else "You"
            ...     print(f"{sender}: {msg['text']}")
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        entity = await self._resolve_entity(agent_telegram_id)
        me = await self.client.get_me()

        messages = []
        async for msg in self.client.iter_messages(entity, limit=limit):
            messages.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "is_from_agent": msg.sender_id != me.id,
                "text": msg.text or "",
                "date": msg.date.isoformat() if msg.date else None,
            })
            await asyncio.sleep(0.05)  # Light rate limiting

        return messages


# =============================================================================
# Session Setup Helper
# =============================================================================

async def create_test_prospect_session(
    session_name: str = "test_prospect",
    phone: Optional[str] = None,
) -> dict:
    """
    Create a new Telethon session for the test prospect account.

    This is a one-time setup function. Telethon will prompt for the
    verification code interactively in the terminal.

    Args:
        session_name: Name for the session file (default: "test_prospect")
        phone: Phone number with country code (e.g., '+79123456789').
               If None, will be prompted interactively.

    Returns:
        Dict with account info: id, username, first_name, last_name

    Example:
        >>> # Run once to set up the test prospect session
        >>> info = await create_test_prospect_session(
        ...     session_name="test_prospect",
        ...     phone="+79123456789"
        ... )
        >>> print(f"Session created for: {info['first_name']}")
    """
    # Load config
    if not is_configured():
        raise RuntimeError(
            "Telegram not configured. "
            "Set up ~/.telegram_dl/config.json first."
        )

    config = load_config()
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")

    if not api_id or not api_hash:
        raise RuntimeError("Could not load Telegram API credentials from config")

    # Create session directory if needed
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_path = SESSIONS_DIR / f"{session_name}.session"

    print(f"Creating session at: {session_path}")

    # Initialize client
    client = TelegramClient(str(session_path), api_id, api_hash)

    # start() will interactively prompt for phone and verification code
    if phone:
        await client.start(phone=phone)
    else:
        await client.start()

    me = await client.get_me()
    info = {
        "id": me.id,
        "username": me.username,
        "first_name": me.first_name,
        "last_name": me.last_name,
    }

    await client.disconnect()

    print(f"Session created successfully for: {info['first_name']} (@{info['username']})")
    return info


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    async def test_player():
        """Quick test of the E2E Telegram player."""
        print("Initializing E2E Telegram Player...")

        player = E2ETelegramPlayer(session_name="test_prospect")

        try:
            await player.connect()

            me = await player.get_me()
            print(f"Connected as: {me['first_name']} (@{me['username']})")

            # Get recent history with agent
            print("\nRecent conversation with @BetterBohdan:")
            history = await player.get_chat_history("@BetterBohdan", limit=5)
            for msg in reversed(history):
                sender = "Agent" if msg['is_from_agent'] else "You"
                text = msg['text'][:50] + "..." if len(msg['text']) > 50 else msg['text']
                print(f"  [{sender}]: {text}")

            print("\nPlayer initialized successfully!")

        except RuntimeError as e:
            print(f"Error: {e}")
        finally:
            await player.disconnect()

    async def setup_session(phone: Optional[str] = None):
        """Set up a new test prospect session."""
        try:
            await create_test_prospect_session(
                session_name="test_prospect",
                phone=phone
            )
        except Exception as e:
            print(f"Error creating session: {e}")

    parser = argparse.ArgumentParser(
        description="E2E Telegram Player for stress testing"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Create new test prospect session (interactive auth)"
    )
    parser.add_argument(
        "--phone",
        type=str,
        help="Phone number for session setup (with country code)"
    )

    args = parser.parse_args()

    if args.setup:
        asyncio.run(setup_session(args.phone))
    else:
        asyncio.run(test_player())
