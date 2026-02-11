#!/usr/bin/env python3
"""
Telegram Agent Daemon.
Long-running service that handles prospect outreach and conversations.
Integrates with scheduling system for Zoom meeting bookings.
"""
import argparse
import asyncio
import json
import random
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from telethon import events

# Package imports
from telegram_sales_bot.core.client import get_client, get_client_for_rep
from telegram_sales_bot.core.service import TelegramService, is_private_chat
from telegram_sales_bot.core.cli_agent import CLITelegramAgent
from telegram_sales_bot.knowledge.loader import KnowledgeLoader
from telegram_sales_bot.prospects.manager import ProspectManager
from telegram_sales_bot.core.models import AgentConfig, ProspectStatus, ScheduledActionType
from telegram_sales_bot.temporal.message_buffer import MessageBuffer, BufferedMessage
from telegram_sales_bot.temporal.pause_detector import detect_pause, PauseDetector
from telegram_sales_bot.temporal.timezone import estimate_timezone, TimezoneEstimate
from telegram_sales_bot.scheduling.scheduler import SchedulerService
from telegram_sales_bot.scheduling.calendar import SalesCalendar
from telegram_sales_bot.scheduling.tool import SchedulingTool
from telegram_sales_bot.database.init import init_database
from telegram_sales_bot.integrations.elevenlabs import VoiceTranscriber
from telegram_sales_bot.integrations.media_detector import detect_media_type
from telegram_sales_bot.integrations.google_calendar import CalendarConnector
from telegram_sales_bot.integrations.zoom import ZoomBookingService
from telegram_sales_bot.scheduling.db import (
    create_scheduled_action,
    cancel_pending_for_prospect,
    get_by_id as get_action_by_id,
    get_pending_actions,
    close_pool,
)

console = Console()

# Configuration paths - resolve for Docker (/app/config) or local development
PACKAGE_DIR = Path(__file__).parent.parent  # src/telegram_sales_bot/
if Path("/app/config").exists():
    # Docker: config is mounted at /app/config
    CONFIG_DIR = Path("/app/config")
else:
    # Local: config is in .claude/skills/telegram/config/
    PROJECT_ROOT = PACKAGE_DIR.parent.parent  # project root
    CONFIG_DIR = PROJECT_ROOT / ".claude" / "skills" / "telegram" / "config"

PROSPECTS_FILE = CONFIG_DIR / "prospects.json"
AGENT_CONFIG_FILE = CONFIG_DIR / "agent_config.json"
SALES_CALENDAR_CONFIG = CONFIG_DIR / "sales_slots.json"

# Knowledge, tone-of-voice, and methodology are inside the package
KNOWLEDGE_BASE_DIR = PACKAGE_DIR / "knowledge" / "base"
TONE_OF_VOICE_DIR = PACKAGE_DIR / "knowledge" / "tone"
HOW_TO_COMMUNICATE_DIR = PACKAGE_DIR / "knowledge" / "methodology"

class TelegramDaemon:
    """Main daemon that orchestrates the agent."""

    def __init__(self, rep_telegram_id: int = None):
        self.rep_telegram_id = rep_telegram_id
        self.client = None
        self.service = None
        self.voice_transcriber: Optional[VoiceTranscriber] = None
        self.agent = None
        self.prospect_manager = None
        self.config = None
        self.knowledge_loader = None
        self.sales_calendar = None
        self.scheduling_tool = None
        self.scheduler_service = None
        self.action_manager = None  # Not used directly, but signals intent
        self.bot_user_id = None  # Telegram ID of the bot account
        self.bot_username = None  # Username of the bot account
        self.message_buffer = None  # Initialized in initialize()
        self.running = False
        self._offered_slots: dict[str, list[str]] = {}  # prospect_id -> offered slot_ids
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "escalations": 0,
            "meetings_scheduled": 0,
            "scheduled_followups": 0,
            "messages_batched": 0,
            "batches_processed": 0,
            "started_at": None
        }

    async def initialize(self) -> None:
        """Initialize all components."""
        console.print("[bold blue]Initializing Telegram Agent Daemon...[/bold blue]")

        # Initialize database first (required for scheduled actions)
        try:
            await init_database()
        except RuntimeError as e:
            console.print(f"[red bold]Database initialization failed: {e}[/red bold]")
            raise

        # Load config
        self.config = self._load_config()
        console.print(f"  [green]✓[/green] Config loaded")

        # Per-rep mode: load rep from database and override config
        if self.rep_telegram_id:
            # Import here to avoid circular dependencies
            from telegram_sales_bot.registry.rep_manager import get_by_telegram_id
            rep = await get_by_telegram_id(self.rep_telegram_id)
            if not rep:
                raise RuntimeError(f"Sales rep with telegram_id={self.rep_telegram_id} not found in database")
            if not rep.telegram_session_ready:
                raise RuntimeError(
                    f"Telegram session for {rep.name} (@{rep.telegram_username}) is not ready. "
                    "Run the register-sales skill to authenticate first."
                )
            # Override config with rep-specific values
            if rep.agent_name:
                self.config.agent_name = rep.agent_name
            self.config.telegram_account = f"@{rep.telegram_username}"
            console.print(f"  [green]✓[/green] Per-rep mode: {rep.name} (@{rep.telegram_username})")

            # Initialize Telegram client for this rep
            self.client = await get_client_for_rep(rep.telegram_session_name)
        else:
            # Default mode: use user.session
            self.client = await get_client()

        self.service = TelegramService(self.client, self.config)
        console.print(f"  [green]✓[/green] Telegram connected")

        # Get account info
        me = await self.service.get_me()
        self.bot_user_id = me['id']
        self.bot_username = me.get('username')
        console.print(f"  [green]✓[/green] Logged in as: {me['first_name']} (@{self.bot_username})")

        # Validate bot is logged into correct account
        if self.config.telegram_account:
            expected_username = self.config.telegram_account.lstrip('@').lower()
            actual_username = (self.bot_username or '').lower()
            if actual_username != expected_username:
                console.print(f"[red bold]ERROR: Bot logged in as @{self.bot_username} but config expects @{expected_username}[/red bold]")
                raise RuntimeError(f"Account mismatch: logged in as @{self.bot_username}, expected @{expected_username}")

        # Initialize prospect manager
        self.prospect_manager = ProspectManager(PROSPECTS_FILE)
        prospects = self.prospect_manager.get_all_prospects()
        console.print(f"  [green]✓[/green] Prospects loaded: {len(prospects)}")

        # Initialize knowledge loader
        if KNOWLEDGE_BASE_DIR.exists():
            self.knowledge_loader = KnowledgeLoader(KNOWLEDGE_BASE_DIR)
            console.print(f"  [green]✓[/green] Knowledge base loaded")
        else:
            console.print(f"  [yellow]⚠[/yellow] Knowledge base not found at {KNOWLEDGE_BASE_DIR}")

        # Initialize sales calendar
        self.sales_calendar = SalesCalendar(SALES_CALENDAR_CONFIG)
        available_slots = len(self.sales_calendar.get_available_slots())
        console.print(f"  [green]✓[/green] Sales calendar initialized ({available_slots} slots available)")

        # Initialize Calendar Connector (optional)
        calendar_connector = None
        if self.rep_telegram_id:
            from telegram_sales_bot.registry.rep_manager import get_by_telegram_id
            rep = await get_by_telegram_id(self.rep_telegram_id)
            if rep and rep.calendar_connected:
                calendar_connector = CalendarConnector()
                if calendar_connector.enabled:
                    console.print(f"  [green]✓[/green] Real calendar integration enabled for {rep.name}")
                else:
                    console.print(f"  [yellow]⚠[/yellow] Google Calendar credentials not configured (using mock slots)")
                    calendar_connector = None
            elif rep:
                console.print(f"  [yellow]⚠[/yellow] Calendar not connected for {rep.name} (using mock slots)")
        else:
            try:
                calendar_connector = CalendarConnector()
                if calendar_connector.enabled:
                    console.print(f"  [green]✓[/green] Google Calendar integration enabled")
                else:
                    console.print(f"  [yellow]⚠[/yellow] Google Calendar credentials not configured (using mock slots)")
                    calendar_connector = None
            except Exception:
                console.print(f"  [yellow]⚠[/yellow] Google Calendar module not available (using mock slots)")
                calendar_connector = None

        # Initialize Zoom booking service (optional)
        zoom_service = None
        try:
            zoom_service = ZoomBookingService()
            if zoom_service.enabled:
                console.print(f"  [green]✓[/green] Zoom integration enabled")
            else:
                console.print(f"  [yellow]⚠[/yellow] Zoom credentials not found (mock mode)")
                zoom_service = None
        except Exception:
            console.print(f"  [yellow]⚠[/yellow] Zoom module not available (mock mode)")

        # Initialize scheduling tool with optional calendar connector and Zoom service
        # Use rep_telegram_id if in per-rep mode, otherwise use bot's own ID for calendar ops
        effective_rep_id = self.rep_telegram_id or self.bot_user_id
        self.scheduling_tool = SchedulingTool(
            self.sales_calendar,
            zoom_service=zoom_service,
            calendar_connector=calendar_connector,
            rep_telegram_id=effective_rep_id
        )
        console.print(f"  [green]✓[/green] Scheduling tool ready (calendar rep_id={effective_rep_id})")

        # Initialize scheduled action manager (imports are module-level functions)
        console.print(f"  [green]✓[/green] Scheduled action manager ready")

        # Initialize scheduler service
        self.scheduler_service = SchedulerService(
            execute_callback=self.execute_scheduled_action
        )
        console.print(f"  [green]✓[/green] Scheduler service initialized")

        # Initialize Claude CLI agent with ALL skills
        self.agent = CLITelegramAgent(
            tone_of_voice_path=TONE_OF_VOICE_DIR,
            how_to_communicate_path=HOW_TO_COMMUNICATE_DIR,
            knowledge_base_path=KNOWLEDGE_BASE_DIR,
            config=self.config,
            agent_name=self.config.agent_name
        )

        # Restore sessions from prospect data
        for prospect in prospects:
            if hasattr(prospect, 'session_id') and prospect.session_id:
                self.agent.sessions[str(prospect.telegram_id)] = prospect.session_id

        console.print(f"  [green]✓[/green] Claude CLI agent ready (model: {self.config.cli_model})")

        # Initialize voice transcriber (optional - requires ELEVENLABS_API_KEY)
        try:
            self.voice_transcriber = VoiceTranscriber()
            console.print(f"  [green]✓[/green] Voice transcription enabled (ElevenLabs)")
        except ValueError as e:
            self.voice_transcriber = None
            console.print(f"  [yellow]![/yellow] Voice transcription disabled: {e}")

        # Initialize message buffer with flush callback
        self.message_buffer = MessageBuffer(
            timeout_range=self.config.batch_timeout_medium,
            flush_callback=self._process_message_batch,
            max_messages=self.config.batch_max_messages,
            max_wait_seconds=self.config.batch_max_wait_seconds
        )
        batch_status = "enabled" if self.config.batch_enabled else "disabled"
        console.print(f"  [green]✓[/green] Message buffer initialized (batching {batch_status})")

        # Register message handler
        self._register_handlers()
        console.print(f"  [green]✓[/green] Message handlers registered")

    def _load_config(self) -> AgentConfig:
        """Load agent configuration."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        if AGENT_CONFIG_FILE.exists():
            with open(AGENT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return AgentConfig(**data)
        else:
            # Create default config
            config = AgentConfig()
            with open(AGENT_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
            return config

    def _aggregate_messages(self, messages: list[BufferedMessage]) -> str:
        """Combine multiple messages into single context for AI.

        If single message: return as-is
        If multiple: format with timestamps
        """
        if len(messages) == 1:
            return messages[0].text

        # Format multiple messages with timestamps
        lines = []
        for msg in messages:
            time_str = msg.timestamp.strftime("%H:%M")
            lines.append(f"[{time_str}] {msg.text}")

        return "\n".join(lines)

    def _calculate_batch_reading_delay(self, total_length: int) -> float:
        """Calculate reading delay for batched messages.

        Uses same logic as TelegramService but for total batch length.
        """
        if total_length < 50:
            delay_range = self.config.reading_delay_short
        elif total_length <= 200:
            delay_range = self.config.reading_delay_medium
        else:
            delay_range = self.config.reading_delay_long

        return random.uniform(*delay_range)

    async def _process_message_batch(
        self,
        prospect_id: str,
        messages: list[BufferedMessage]
    ) -> None:
        """Process a batch of messages from one prospect.

        Called by MessageBuffer when timer expires.
        """
        # 1. Get prospect
        prospect = self.prospect_manager.get_prospect(int(prospect_id))
        if not prospect:
            console.print(f"[red]Unknown prospect {prospect_id} in batch[/red]")
            return

        console.print(f"\n[cyan]Processing batch of {len(messages)} message(s) from {prospect.name}[/cyan]")

        # Update stats
        self.stats["batches_processed"] += 1
        self.stats["messages_batched"] += len(messages)

        # 2. Messages already recorded in handle_incoming, so skip re-recording

        # 3. Cancel pending follow-ups (once, not per message)
        try:
            pending_actions = await get_pending_actions(str(prospect.telegram_id))
            pending_ids = [action.id for action in pending_actions]

            cancelled = await cancel_pending_for_prospect(
                str(prospect.telegram_id),
                reason="client_responded"
            )

            if self.scheduler_service and pending_ids:
                for action_id in pending_ids:
                    await self.scheduler_service.cancel_action(action_id)

            if cancelled > 0:
                console.print(f"[dim]Cancelled {cancelled} pending follow-up(s)[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not cancel actions: {e}[/yellow]")

        # 4. Check rate limits
        messages_today = self.prospect_manager.get_messages_sent_today(prospect.telegram_id)
        if not self.agent.check_rate_limit(prospect, messages_today):
            console.print(f"[yellow]Rate limit reached for {prospect.name}, skipping batch[/yellow]")
            return

        # 5. Check working hours
        if not self.agent.is_within_working_hours():
            console.print(f"[yellow]Outside working hours, skipping batch[/yellow]")
            return

        # 6. Aggregate messages for AI
        combined_text = self._aggregate_messages(messages)

        # 7. Calculate reading delay for TOTAL text
        total_length = sum(len(m.text) for m in messages)
        reading_delay = self._calculate_batch_reading_delay(total_length)
        console.print(f"[dim]Reading delay: {reading_delay:.1f}s for {total_length} total chars[/dim]")
        await asyncio.sleep(reading_delay)

        # 8. Get context and generate SINGLE response
        context = self.prospect_manager.get_conversation_context(prospect.telegram_id)

        try:
            action = await self.agent.generate_response(
                prospect,
                combined_text,  # All messages as one
                context
            )

            console.print(f"[dim]Agent decision: {action.action} - {action.reason}[/dim]")

            # 9. Handle action (same logic as non-batched handle_incoming)
            await self._handle_action(prospect, action, context)

        except Exception as e:
            console.print(f"[red]Error processing batch: {e}[/red]")

    def _resolve_client_timezone(
        self, prospect, agent_client_tz: Optional[str] = None, label: str = ""
    ) -> Optional[str]:
        """
        Resolve client timezone with priority: agent-provided > stored > heuristic.

        When the agent provides a timezone (from the client explicitly naming a city),
        it is stored with confidence=1.0 and overrides everything else.

        Args:
            prospect: Prospect object with estimated_timezone and timezone_confidence
            agent_client_tz: Timezone string from scheduling_data.client_timezone
            label: Context label for logging (e.g., "for booking")

        Returns:
            IANA timezone string or None if no timezone could be determined
        """
        log_suffix = f" {label}" if label else ""

        if agent_client_tz:
            # Agent explicitly provided timezone (client stated their city)
            self.prospect_manager.update_prospect_timezone(
                prospect.telegram_id,
                agent_client_tz,
                1.0
            )
            prospect.estimated_timezone = agent_client_tz
            prospect.timezone_confidence = 1.0
            console.print(f"[blue]Using agent-provided timezone{log_suffix}: {agent_client_tz} (confidence: 1.0)[/blue]")
            return agent_client_tz

        if prospect.estimated_timezone and prospect.timezone_confidence >= 0.7:
            console.print(f"[dim]Using stored timezone{log_suffix}: {prospect.estimated_timezone}[/dim]")
            return prospect.estimated_timezone

        # Fall back to heuristic estimation
        message_timestamps = [
            msg.timestamp for msg in prospect.conversation_history
            if msg.timestamp and msg.sender == "prospect"
        ]
        if message_timestamps:
            tz_estimate = estimate_timezone(message_timestamps)
            if tz_estimate.confidence > 0.7:
                self.prospect_manager.update_prospect_timezone(
                    prospect.telegram_id,
                    tz_estimate.timezone,
                    tz_estimate.confidence
                )
                prospect.estimated_timezone = tz_estimate.timezone
                prospect.timezone_confidence = tz_estimate.confidence
                console.print(
                    f"[blue]Detected timezone{log_suffix}: {tz_estimate.timezone} "
                    f"(confidence: {tz_estimate.confidence:.2f})[/blue]"
                )
                return tz_estimate.timezone
            else:
                console.print(
                    f"[dim]Timezone estimate low confidence{log_suffix}: {tz_estimate.timezone} "
                    f"({tz_estimate.confidence:.2f})[/dim]"
                )

        return None

    async def _handle_action(self, prospect, action, context):
        """Handle agent action (extracted from handle_incoming for reuse)."""
        # Handle check_availability action
        if action.action == "check_availability":
            sched_data = action.scheduling_data or {}
            preferred_time_str = sched_data.get("preferred_time")
            preferred_date_str = sched_data.get("preferred_date")

            # Resolve timezone: agent-provided > stored > heuristic
            client_tz = self._resolve_client_timezone(
                prospect,
                agent_client_tz=sched_data.get("client_timezone"),
            )

            # Persist email early if provided in scheduling_data (Issue 3 fix)
            sched_email = sched_data.get("email")
            if sched_email and sched_email.strip():
                self.prospect_manager.update_prospect_email(
                    prospect.telegram_id, sched_email.strip()
                )
                console.print(f"[blue]Email persisted from check_availability: {sched_email.strip()}[/blue]")

            # Initialize offered_ids before branching
            offered_ids = []

            if preferred_time_str and preferred_date_str:
                # User provided a SPECIFIC time - use confirm_time_slot instead of full list
                try:
                    from datetime import time as dt_time, date as dt_date
                    from zoneinfo import ZoneInfo

                    # Parse the preferred time and date
                    h, m = map(int, preferred_time_str.split(":"))
                    preferred_time = dt_time(h, m)
                    preferred_date = dt_date.fromisoformat(preferred_date_str)

                    # Convert from client timezone to Bali timezone if needed
                    if client_tz:
                        from datetime import datetime as dt_datetime
                        client_dt = dt_datetime.combine(
                            preferred_date, preferred_time,
                            tzinfo=ZoneInfo(client_tz)
                        )
                        bali_dt = client_dt.astimezone(ZoneInfo("Asia/Makassar"))
                        target_date = bali_dt.date()
                        target_time = bali_dt.time().replace(second=0, microsecond=0)
                    else:
                        # No client timezone - assume Bali time
                        target_date = preferred_date
                        target_time = preferred_time

                    console.print(
                        f"[blue]Confirming specific time: {preferred_time_str} "
                        f"({preferred_date_str}) client TZ={client_tz} -> "
                        f"Bali {target_date} {target_time}[/blue]"
                    )

                    availability_text, offered_ids = self.scheduling_tool.confirm_time_slot(
                        target_date=target_date,
                        target_time=target_time,
                        client_timezone=client_tz
                    )
                except (ValueError, KeyError) as e:
                    console.print(f"[yellow]Failed to parse preferred time: {e}, falling back to full list[/yellow]")
                    availability_text, offered_ids = self.scheduling_tool.get_available_times(
                        days=7,
                        client_timezone=client_tz
                    )
            else:
                # No specific time - show all available slots
                availability_text, offered_ids = self.scheduling_tool.get_available_times(
                    days=7,
                    client_timezone=client_tz
                )

            # Track offered slots for validation when booking (Issue 5 fix)
            self._offered_slots[str(prospect.telegram_id)] = offered_ids
            if offered_ids:
                console.print(f"[dim]Tracking {len(offered_ids)} offered slots for {prospect.name}: {offered_ids[:3]}...[/dim]")

            # Send availability to user
            result = await self.service.send_message(
                prospect.telegram_id,
                availability_text
            )

            # Record in conversation history so agent knows what was shown
            if result.get("sent"):
                self.stats["messages_sent"] += 1
                self.prospect_manager.record_agent_message(
                    prospect.telegram_id,
                    result["message_id"],
                    availability_text
                )

            console.print(f"[cyan]-> Sent availability to {prospect.name}[/cyan]")

            # Update prospect to show we're in scheduling mode
            self.prospect_manager.update_status(
                prospect.telegram_id,
                ProspectStatus.IN_CONVERSATION
            )

        # Handle schedule action
        elif action.action == "schedule" and action.scheduling_data:
            slot_id = action.scheduling_data.get("slot_id")

            # Validate slot_id was actually offered to client
            prospect_key = str(prospect.telegram_id)
            offered = self._offered_slots.get(prospect_key, [])
            if offered and slot_id not in offered:
                if len(offered) == 1:
                    # Only ONE slot was offered - safe to auto-correct
                    console.print(
                        f"[yellow]WARNING: Agent tried to book slot {slot_id} which was NOT offered. "
                        f"Auto-correcting to the only offered slot: {offered[0]}[/yellow]"
                    )
                    slot_id = offered[0]
                else:
                    # MULTIPLE slots were offered - ask client to choose
                    console.print(
                        f"[yellow]WARNING: Agent tried to book slot {slot_id} which was NOT offered. "
                        f"Multiple alternatives exist ({len(offered)} slots) - asking client to choose.[/yellow]"
                    )
                    # Re-send alternatives to client
                    alt_texts = []
                    for alt_id in offered[:3]:
                        # Extract time from slot ID format YYYYMMDD_HHMM
                        try:
                            time_part = alt_id.split("_")[1]
                            h, m = int(time_part[:2]), int(time_part[2:])
                            from datetime import time as dt_time, date as dt_date, datetime as dt_datetime
                            from zoneinfo import ZoneInfo
                            date_part = alt_id.split("_")[0]
                            slot_date = dt_date(int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8]))
                            slot_time = dt_time(h, m)
                            # Convert to client timezone if available
                            client_tz_for_display = action.scheduling_data.get("client_timezone") or prospect.estimated_timezone
                            if client_tz_for_display:
                                bali_dt = dt_datetime.combine(slot_date, slot_time, tzinfo=ZoneInfo("Asia/Makassar"))
                                client_dt = bali_dt.astimezone(ZoneInfo(client_tz_for_display))
                                alt_texts.append(client_dt.strftime("%H:%M"))
                            else:
                                alt_texts.append(f"{h:02d}:{m:02d}")
                        except Exception:
                            alt_texts.append(alt_id)

                    clarify_msg = f"На какое именно время записать - {', '.join(alt_texts[:-1])} или {alt_texts[-1]}?" if len(alt_texts) > 1 else f"Записать на {alt_texts[0]}?"
                    send_result = await self.service.send_message(prospect.telegram_id, clarify_msg)
                    if send_result.get("sent"):
                        self.stats["messages_sent"] += 1
                        self.prospect_manager.record_agent_message(
                            prospect.telegram_id,
                            send_result["message_id"],
                            clarify_msg
                        )
                    return  # Don't proceed with booking - wait for client to choose

            client_email = action.scheduling_data.get("email", "")
            topic = action.scheduling_data.get("topic", "Консультация по недвижимости на Бали")

            if not slot_id:
                console.print(f"[red]Schedule action missing slot_id[/red]")
                return

            # STRICT: Email is REQUIRED for booking
            if not client_email or not client_email.strip():
                error_msg = "Для записи на встречу нужен email. На какой адрес отправить приглашение?"
                send_result = await self.service.send_message(prospect.telegram_id, error_msg)
                # Record so agent knows email was requested
                if send_result.get("sent"):
                    self.stats["messages_sent"] += 1
                    self.prospect_manager.record_agent_message(
                        prospect.telegram_id,
                        send_result["message_id"],
                        error_msg
                    )
                console.print(f"[yellow]Schedule rejected - no email provided[/yellow]")
                return

            # Resolve timezone: agent-provided > stored > heuristic
            client_tz = self._resolve_client_timezone(
                prospect,
                agent_client_tz=action.scheduling_data.get("client_timezone"),
                label="for booking",
            )

            # Store email in prospect record
            self.prospect_manager.update_prospect_email(prospect.telegram_id, client_email.strip())

            # Book the meeting (client_tz can be used for future timezone-aware features)
            booking_result = self.scheduling_tool.book_meeting(
                slot_id=slot_id,
                prospect=prospect,
                client_email=client_email.strip(),
                topic=topic,
                client_timezone=client_tz
            )

            if booking_result.success:
                # Send confirmation
                send_result = await self.service.send_message(
                    prospect.telegram_id,
                    booking_result.message
                )

                # Record confirmation in history
                if send_result.get("sent"):
                    self.stats["messages_sent"] += 1
                    self.prospect_manager.record_agent_message(
                        prospect.telegram_id,
                        send_result["message_id"],
                        booking_result.message
                    )

                # Update prospect status
                self.prospect_manager.update_status(
                    prospect.telegram_id,
                    ProspectStatus.ZOOM_SCHEDULED
                )

                # Update stats
                self.stats["meetings_scheduled"] += 1

                console.print(f"[green]Meeting scheduled for {prospect.name}: {slot_id} (email: {client_email})[/green]")
            else:
                # Send error message
                send_result = await self.service.send_message(
                    prospect.telegram_id,
                    booking_result.message
                )
                # Record error in history
                if send_result.get("sent"):
                    self.stats["messages_sent"] += 1
                    self.prospect_manager.record_agent_message(
                        prospect.telegram_id,
                        send_result["message_id"],
                        booking_result.message
                    )
                console.print(f"[red]Scheduling failed: {booking_result.error}[/red]")

        # Handle schedule_followup action
        elif action.action == "schedule_followup" and action.scheduling_data:
            await self._handle_schedule_followup(prospect, action, context)

        # Handle reply action
        elif action.action == "reply" and action.message:
            # Send response
            result = await self.service.send_message(
                prospect.telegram_id,
                action.message
            )

            if result.get("sent"):
                self.stats["messages_sent"] += 1
                self.prospect_manager.record_agent_message(
                    prospect.telegram_id,
                    result["message_id"],
                    action.message
                )
                console.print(f"[green]-> Sent to {prospect.name}:[/green] {action.message[:100]}...")
            else:
                console.print(f"[red]Failed to send: {result.get('error')}[/red]")

        # Handle escalate action
        elif action.action == "escalate":
            self.stats["escalations"] += 1
            console.print(f"[yellow]Escalated: {action.reason}[/yellow]")

            # Notify if configured
            if self.config.escalation_notify:
                last_message_text = getattr(prospect, 'last_message_text', '')
                await self.service.notify_escalation(
                    self.config.escalation_notify,
                    prospect.name,
                    action.reason,
                    last_message_text
                )

        # Persist CLI session ID for conversation continuity
        self._persist_session(prospect)

    def _persist_session(self, prospect) -> None:
        """Save the CLI session ID from the agent to the prospect data."""
        prospect_id = str(prospect.telegram_id)
        session_id = self.agent.sessions.get(prospect_id)
        if session_id:
            self.prospect_manager.update_prospect_field(
                prospect.telegram_id, "session_id", session_id
            )

    async def _handle_schedule_followup(self, prospect, action, context):
        """Handle schedule_followup action."""
        try:
            # Parse scheduled time from ISO 8601
            follow_up_time_str = action.scheduling_data.get("follow_up_time")
            scheduled_for = datetime.fromisoformat(follow_up_time_str)

            # Create scheduled action in database
            scheduled_action = await create_scheduled_action(
                prospect_id=str(prospect.telegram_id),
                action_type=ScheduledActionType.FOLLOW_UP,
                scheduled_for=scheduled_for,
                payload={
                    "follow_up_intent": action.scheduling_data.get("follow_up_intent"),
                    "reason": action.scheduling_data.get("reason"),
                    "original_context_snapshot": context[:1000]
                }
            )

            # Schedule with APScheduler
            await self.scheduler_service.schedule_action(scheduled_action)

            # Update stats
            self.stats["scheduled_followups"] += 1

            console.print(f"[cyan]Scheduled follow-up for {prospect.name} at {scheduled_for.strftime('%Y-%m-%d %H:%M')}[/cyan]")

            # Always send confirmation - use agent's text or generate fallback
            confirmation = action.message

            # SAFETY: Check for leaked reasoning in confirmation
            # If the confirmation is suspiciously long (>120 chars) for what should be
            # a 1-sentence acknowledgment, it likely contains leaked reasoning
            if confirmation and len(confirmation) > 120:
                console.print(f"[yellow]Confirmation too long ({len(confirmation)} chars), using fallback[/yellow]")
                confirmation = None

            if not confirmation:
                confirmation = "Хорошо, напишу позже!"

            result = await self.service.send_message(
                prospect.telegram_id,
                confirmation
            )

            if result.get("sent"):
                self.stats["messages_sent"] += 1
                self.prospect_manager.record_agent_message(
                    prospect.telegram_id,
                    result["message_id"],
                    confirmation
                )
                console.print(f"[green]-> Confirmation sent to {prospect.name}[/green]")

        except Exception as e:
            console.print(f"[red]Failed to schedule follow-up: {e}[/red]")

    def _register_handlers(self) -> None:
        """Register Telegram event handlers."""

        @self.client.on(events.NewMessage(incoming=True))
        async def handle_incoming(event):
            """Handle incoming messages."""
            # Only process private messages
            if not event.is_private:
                return

            # Verify message is sent TO this bot's account (defense in depth)
            if self.config.telegram_account:
                expected_username = self.config.telegram_account.lstrip('@').lower()
                if self.bot_username and self.bot_username.lower() != expected_username:
                    # Config mismatch - bot logged into wrong account
                    console.print(f"[red]Warning: Bot logged in as @{self.bot_username} but config expects @{expected_username}[/red]")
                    return

            sender = await event.get_sender()
            if not sender:
                return

            sender_id = sender.id
            sender_name = sender.first_name or "Unknown"

            # Check if this is a known prospect
            if not self.prospect_manager.is_prospect(sender_id):
                # Also check by username
                if sender.username and not self.prospect_manager.is_prospect(f"@{sender.username}"):
                    # Unknown sender - ignore
                    return

            # Get prospect
            prospect = self.prospect_manager.get_prospect(sender_id)
            if not prospect:
                prospect = self.prospect_manager.get_prospect(f"@{sender.username}")
            if not prospect:
                return

            # Detect media type BEFORE accessing event.text (prevents crash on None)
            media_result = detect_media_type(event)
            message_text = event.text or ""

            # Handle voice messages - transcribe to text
            if media_result.media_type == "voice" and self.voice_transcriber:
                try:
                    console.print(f"[cyan]Transcribing voice from {prospect.name}...[/cyan]")
                    transcription = await self.voice_transcriber.transcribe_telegram_voice(
                        self.client, event.message
                    )
                    message_text = transcription.text
                    console.print(f"[green]Transcribed:[/green] {message_text[:100]}...")
                except Exception as e:
                    console.print(f"[yellow]Transcription failed: {e}[/yellow]")
                    message_text = "[Голосовое сообщение]"

            # Handle other media types
            elif media_result.has_media and not message_text:
                if media_result.media_type == "sticker":
                    emoji = media_result.file_name or ""
                    message_text = f"[Стикер: {emoji}]"
                elif media_result.media_type == "photo":
                    message_text = "[Фото]"
                elif media_result.media_type == "video":
                    message_text = "[Видео]"
                elif media_result.media_type == "document":
                    message_text = "[Документ]"
                else:
                    message_text = f"[{media_result.media_type}]"

            # Safe logging
            display_text = message_text[:100] if message_text else "[пустое сообщение]"
            console.print(f"\n[cyan]<- Received from {prospect.name}:[/cyan] {display_text}...")

            self.stats["messages_received"] += 1

            # Detect conversation pause
            gap = detect_pause(
                prospect.last_contact,
                prospect.last_response,
                datetime.now()
            )
            if gap.hours >= 24:
                console.print(f"[dim]Conversation gap: {gap.hours:.0f}h ({gap.pause_type.value})[/dim]")

            # Record the response (using processed message_text, not event.text)
            self.prospect_manager.record_response(
                prospect.telegram_id,
                event.id,
                message_text
            )

            # Buffer message if batching enabled
            if self.config.batch_enabled:
                buffered_msg = BufferedMessage(
                    message_id=event.id,
                    text=message_text,
                    timestamp=datetime.now()
                )
                await self.message_buffer.add_message(
                    str(prospect.telegram_id),
                    buffered_msg
                )
                console.print(f"[dim]Buffered message from {prospect.name}, waiting for more...[/dim]")
                return  # Don't process immediately - _process_message_batch will handle it

            # Cancel pending follow-ups when client responds
            try:
                # First, get pending action IDs before cancelling in database
                pending_actions = await get_pending_actions(str(prospect.telegram_id))
                pending_ids = [action.id for action in pending_actions]

                # Cancel in database
                cancelled = await cancel_pending_for_prospect(
                    str(prospect.telegram_id),
                    reason="client_responded"
                )

                # Also cancel in-memory asyncio tasks in scheduler
                if self.scheduler_service and pending_ids:
                    for action_id in pending_ids:
                        await self.scheduler_service.cancel_action(action_id)

                if cancelled > 0:
                    console.print(f"[dim]Cancelled {cancelled} pending follow-up(s) (DB + in-memory)[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not cancel actions: {e}[/yellow]")

            # Check rate limits
            messages_today = self.prospect_manager.get_messages_sent_today(prospect.telegram_id)
            if not self.agent.check_rate_limit(prospect, messages_today):
                console.print(f"[yellow]Rate limit reached for {prospect.name}, skipping[/yellow]")
                return

            # Check working hours
            if not self.agent.is_within_working_hours():
                console.print(f"[yellow]Outside working hours, skipping[/yellow]")
                return

            # Get conversation context
            context = self.prospect_manager.get_conversation_context(prospect.telegram_id)

            # Simulate reading delay (proportional to incoming message length)
            reading_delay = self.service._calculate_reading_delay(message_text)
            console.print(f"[dim]Reading delay: {reading_delay:.1f}s for {len(message_text)} chars[/dim]")
            await asyncio.sleep(reading_delay)

            # Generate response
            try:
                action = await self.agent.generate_response(
                    prospect,
                    message_text,
                    context
                )

                console.print(f"[dim]Agent decision: {action.action} - {action.reason}[/dim]")

                await self._handle_action(prospect, action, context)

            except Exception as e:
                console.print(f"[red]Error processing message: {e}[/red]")

        @self.client.on(events.MessageEdited(incoming=True))
        async def handle_message_edited(event):
            """Handle edited messages from prospects."""
            if not event.is_private:
                return
            sender = await event.get_sender()
            if not sender:
                return
            prospect = self.prospect_manager.get_prospect(sender.id)
            if not prospect:
                return
            console.print(f"[yellow]Edited by {prospect.name}:[/yellow] {(event.text or '')[:50]}...")
            self.prospect_manager.mark_message_edited(
                prospect.telegram_id,
                event.id,
                new_text=event.text or "",
                edited_at=datetime.now()
            )

        @self.client.on(events.MessageDeleted)
        async def handle_message_deleted(event):
            """Handle deleted messages."""
            for msg_id in event.deleted_ids:
                for prospect in self.prospect_manager.get_all_prospects():
                    if self.prospect_manager.has_message(prospect.telegram_id, msg_id):
                        console.print(f"[red]Deleted msg {msg_id} by {prospect.name}[/red]")
                        self.prospect_manager.mark_message_deleted(prospect.telegram_id, msg_id)
                        break

    async def process_new_prospects(self) -> None:
        """Send initial messages to new prospects."""
        new_prospects = self.prospect_manager.get_new_prospects()

        if not new_prospects:
            return

        console.print(f"\n[bold]Processing {len(new_prospects)} new prospects...[/bold]")

        for prospect in new_prospects:
            # Check rate limits
            messages_today = self.prospect_manager.get_messages_sent_today(prospect.telegram_id)
            if not self.agent.check_rate_limit(prospect, messages_today):
                console.print(f"[yellow]Rate limit for {prospect.name}, skipping[/yellow]")
                continue

            # Check working hours
            if not self.agent.is_within_working_hours():
                console.print(f"[yellow]Outside working hours, skipping new outreach[/yellow]")
                break

            try:
                console.print(f"[cyan]Generating initial message for {prospect.name}...[/cyan]")

                # Generate initial message
                action = await self.agent.generate_initial_message(prospect)
                self._persist_session(prospect)

                if action.action == "escalate":
                    console.print(f"[red]CLI agent error for {prospect.name}: {action.reason}[/red]")
                    continue

                if action.action == "reply" and action.message:
                    # Send message
                    result = await self.service.send_message(
                        prospect.telegram_id,
                        action.message
                    )

                    if result.get("sent"):
                        self.stats["messages_sent"] += 1
                        self.prospect_manager.mark_contacted(
                            prospect.telegram_id,
                            result["message_id"],
                            action.message
                        )
                        console.print(f"[green]-> Initial message sent to {prospect.name}[/green]")
                    else:
                        console.print(f"[red]Failed: {result.get('error')}[/red]")

                # Small delay between prospects
                await asyncio.sleep(5)

            except Exception as e:
                console.print(f"[red]Error with {prospect.name}: {e}[/red]")

    async def process_follow_ups(self) -> None:
        """Send follow-up messages to non-responsive prospects."""
        active_prospects = self.prospect_manager.get_active_prospects()

        for prospect in active_prospects:
            if not self.prospect_manager.should_follow_up(
                prospect.telegram_id,
                hours=self.config.auto_follow_up_hours
            ):
                continue

            # Check rate limits
            messages_today = self.prospect_manager.get_messages_sent_today(prospect.telegram_id)
            if not self.agent.check_rate_limit(prospect, messages_today):
                continue

            if not self.agent.is_within_working_hours():
                break

            try:
                console.print(f"[cyan]Generating follow-up for {prospect.name}...[/cyan]")

                context = self.prospect_manager.get_conversation_context(prospect.telegram_id)
                action = await self.agent.generate_follow_up(prospect, context)
                self._persist_session(prospect)

                if action.action == "reply" and action.message:
                    result = await self.service.send_message(
                        prospect.telegram_id,
                        action.message
                    )

                    if result.get("sent"):
                        self.stats["messages_sent"] += 1
                        self.prospect_manager.record_agent_message(
                            prospect.telegram_id,
                            result["message_id"],
                            action.message
                        )
                        console.print(f"[green]-> Follow-up sent to {prospect.name}[/green]")

                elif action.action == "wait":
                    console.print(f"[dim]Skipping follow-up for {prospect.name}: {action.reason}[/dim]")

                await asyncio.sleep(5)

            except Exception as e:
                console.print(f"[red]Error with follow-up for {prospect.name}: {e}[/red]")

    async def execute_scheduled_action(self, action_from_scheduler):
        """
        Execute a scheduled action when it's due.

        Called by SchedulerService when a scheduled time arrives.

        Args:
            action_from_scheduler: ScheduledAction object from scheduler
        """
        try:
            # Fetch fresh action from database to verify it wasn't cancelled
            action = await get_action_by_id(action_from_scheduler.id)

            if not action:
                console.print(f"[yellow]Scheduled action {action_from_scheduler.id} not found[/yellow]")
                return

            # Check if already executed or cancelled
            if action.status not in ("pending", "processing"):
                console.print(f"[dim]Skipping {action.status} action {action.id}[/dim]")
                return

            # Get prospect
            prospect = self.prospect_manager.get_prospect(action.prospect_id)
            if not prospect:
                console.print(f"[yellow]Prospect {action.prospect_id} not found for scheduled action[/yellow]")
                return

            # Pre-execution checks

            # Check if human has taken over
            if self.prospect_manager.is_human_active(prospect.telegram_id):
                await cancel_pending_for_prospect(
                    action.prospect_id,
                    reason="human_active"
                )
                console.print(f"[yellow]Cancelled action for {prospect.name} - human is active[/yellow]")
                return

            # Always regenerate message fresh using current context + stored intent
            follow_up_intent = action.payload.get("follow_up_intent") or action.payload.get("message_template", "")  # Backward compat
            original_reason = action.payload.get("reason", "scheduled follow-up")

            # Get fresh conversation context
            context = self.prospect_manager.get_conversation_context(prospect.telegram_id)

            # Generate contextual follow-up with intent guidance
            response = await self.agent.generate_follow_up(
                prospect,
                context,
                follow_up_intent=follow_up_intent
            )
            self._persist_session(prospect)

            if response.action == "reply" and response.message:
                message = response.message
            elif response.action == "wait":
                console.print(f"[yellow]Agent decided not to follow up with {prospect.name}: {response.reason}[/yellow]")
                return
            elif response.action == "schedule_followup":
                # Agent tried to recursively schedule - use the text message if reasonable
                console.print(f"[yellow]Agent tried to reschedule - using message text instead[/yellow]")
                if response.message and len(response.message) <= 200:
                    message = response.message
                else:
                    message = "Привет! Как дела?"
            else:
                console.print(f"[yellow]Unexpected action from follow-up generation: {response.action}[/yellow]")
                return

            # Send message
            result = await self.service.send_message(prospect.telegram_id, message)

            if result.get("sent"):
                self.stats["messages_sent"] += 1
                self.prospect_manager.record_agent_message(
                    prospect.telegram_id,
                    result["message_id"],
                    message
                )
                console.print(f"[green]Scheduled follow-up sent to {prospect.name}[/green]")
            else:
                console.print(f"[red]Failed to send scheduled message: {result.get('error')}[/red]")

        except Exception as e:
            console.print(f"[red]Error executing scheduled action: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def _create_status_table(self) -> Table:
        """Create a status table for display."""
        table = Table(title="Telegram Agent Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        if self.stats["started_at"]:
            uptime = datetime.now() - self.stats["started_at"]
            table.add_row("Uptime", str(uptime).split('.')[0])

        table.add_row("Messages Sent", str(self.stats["messages_sent"]))
        table.add_row("Messages Received", str(self.stats["messages_received"]))
        table.add_row("Messages Batched", str(self.stats.get("messages_batched", 0)))
        table.add_row("Batches Processed", str(self.stats.get("batches_processed", 0)))
        table.add_row("Meetings Scheduled", str(self.stats["meetings_scheduled"]))
        table.add_row("Scheduled Follow-ups", str(self.stats.get("scheduled_followups", 0)))
        table.add_row("Escalations", str(self.stats["escalations"]))

        if self.prospect_manager:
            table.add_row("Total Prospects", str(len(self.prospect_manager.get_all_prospects())))
            table.add_row("New Prospects", str(len(self.prospect_manager.get_new_prospects())))
            table.add_row("Active Conversations", str(len(self.prospect_manager.get_active_prospects())))

        return table

    async def run(self) -> None:
        """Run the daemon."""
        self.running = True
        self.stats["started_at"] = datetime.now()

        console.print(Panel.fit(
            "[bold green]Telegram Agent Daemon Started[/bold green]\n"
            "Press Ctrl+C to stop",
            title="Status"
        ))

        # Start scheduler
        await self.scheduler_service.start()
        console.print("[green]Scheduler started and ready[/green]")

        # Initial processing
        await self.process_new_prospects()
        await self.process_follow_ups()

        # Main loop
        check_interval = 60 * 5  # Check for follow-ups every 5 minutes
        last_check = datetime.now()

        try:
            while self.running:
                # Print status periodically
                if (datetime.now() - last_check).total_seconds() >= check_interval:
                    console.print(self._create_status_table())
                    await self.process_follow_ups()
                    last_check = datetime.now()

                # Keep event loop running
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            console.print("\n[yellow]Shutdown requested...[/yellow]")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the daemon."""
        self.running = False
        console.print("[yellow]Shutting down...[/yellow]")

        # Flush all pending message buffers before shutdown
        if self.message_buffer:
            pending = self.message_buffer.get_all_pending_prospect_ids()
            if pending:
                console.print(f"[cyan]Flushing {len(pending)} pending buffer(s)...[/cyan]")
                await self.message_buffer.flush_all()
                console.print("[green]Message buffers flushed[/green]")

        # Stop scheduler
        if self.scheduler_service:
            await self.scheduler_service.stop()
            console.print("[green]Scheduler stopped[/green]")

        # Close database connection pool
        try:
            await close_pool()
            console.print("[green]Database connections closed[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Error closing database pool: {e}[/yellow]")

        if self.client:
            await self.client.disconnect()
            console.print("[green]Disconnected from Telegram[/green]")

        console.print(Panel.fit(
            f"[bold]Final Stats[/bold]\n"
            f"Messages Sent: {self.stats['messages_sent']}\n"
            f"Messages Received: {self.stats['messages_received']}\n"
            f"Meetings Scheduled: {self.stats['meetings_scheduled']}\n"
            f"Scheduled Follow-ups: {self.stats.get('scheduled_followups', 0)}\n"
            f"Messages Batched: {self.stats.get('messages_batched', 0)}\n"
            f"Batches Processed: {self.stats.get('batches_processed', 0)}\n"
            f"Escalations: {self.stats['escalations']}",
            title="Session Summary"
        ))

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Telegram Agent Daemon")
    parser.add_argument(
        '--rep-telegram-id',
        type=int,
        default=None,
        help='Run daemon for a specific sales rep (by Telegram ID)',
    )
    args = parser.parse_args()

    daemon = TelegramDaemon(rep_telegram_id=args.rep_telegram_id)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        daemon.running = False

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await daemon.initialize()
        await daemon.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red bold]Fatal error: {e}[/red bold]")
        raise

if __name__ == "__main__":
    asyncio.run(main())
