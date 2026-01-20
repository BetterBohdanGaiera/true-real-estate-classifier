#!/usr/bin/env python3
"""
Telegram Agent Daemon.
Long-running service that handles prospect outreach and conversations.
Integrates with scheduling system for Zoom meeting bookings.
"""
import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from telethon import events

# Add telegram skills directory to path for telegram_fetch import
# telegram_fetch remains in .claude/skills/telegram/scripts/
_SKILLS_TELEGRAM_SCRIPTS = Path(__file__).parent.parent.parent / ".claude/skills/telegram/scripts"
sys.path.insert(0, str(_SKILLS_TELEGRAM_SCRIPTS))

from telegram_fetch import get_client

# Import from new package structure
from sales_agent.telegram import TelegramService
from sales_agent.telegram.telegram_service import is_private_chat
from sales_agent.agent import TelegramAgent, KnowledgeLoader
from sales_agent.crm import ProspectManager, AgentConfig, ProspectStatus, ScheduledActionType
from sales_agent.scheduling import (
    SalesCalendar,
    SchedulingTool,
    SchedulerService,
    scheduled_action_manager,
)

# Import specific functions from scheduled_action_manager
from sales_agent.scheduling.scheduled_action_manager import (
    create_scheduled_action,
    cancel_pending_for_prospect,
    get_by_id as get_action_by_id,
)

console = Console()

# Configuration paths
# SCRIPT_DIR is src/sales_agent/
SCRIPT_DIR = Path(__file__).parent
# CONFIG_DIR is src/sales_agent/config/
CONFIG_DIR = SCRIPT_DIR / "config"
PROSPECTS_FILE = CONFIG_DIR / "prospects.json"
AGENT_CONFIG_FILE = CONFIG_DIR / "agent_config.json"
# Skills directories remain in .claude/skills/
SKILLS_DIR = SCRIPT_DIR.parent.parent / ".claude/skills"
TONE_OF_VOICE_DIR = SKILLS_DIR / "tone-of-voice"
HOW_TO_COMMUNICATE_DIR = SKILLS_DIR / "how-to-communicate"
# Knowledge base is at project root
KNOWLEDGE_BASE_DIR = SCRIPT_DIR.parent.parent / "knowledge_base_final"
SALES_CALENDAR_CONFIG = CONFIG_DIR / "sales_slots.json"


class TelegramDaemon:
    """Main daemon that orchestrates the agent."""

    def __init__(self):
        self.client = None
        self.service = None
        self.agent = None
        self.prospect_manager = None
        self.config = None
        self.knowledge_loader = None
        self.sales_calendar = None
        self.scheduling_tool = None
        self.scheduler_service = None
        self.action_manager = None  # Not used directly, but signals intent
        self.running = False
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "escalations": 0,
            "meetings_scheduled": 0,
            "scheduled_followups": 0,
            "started_at": None
        }

    async def initialize(self) -> None:
        """Initialize all components."""
        console.print("[bold blue]Initializing Telegram Agent Daemon...[/bold blue]")

        # Load config
        self.config = self._load_config()
        console.print(f"  [green]✓[/green] Config loaded")

        # Initialize Telegram client
        self.client = await get_client()
        self.service = TelegramService(self.client, self.config)
        console.print(f"  [green]✓[/green] Telegram connected")

        # Get account info
        me = await self.service.get_me()
        console.print(f"  [green]✓[/green] Logged in as: {me['first_name']} (@{me['username']})")

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

        # Initialize scheduling tool
        self.scheduling_tool = SchedulingTool(self.sales_calendar)
        console.print(f"  [green]✓[/green] Scheduling tool ready")

        # Initialize scheduled action manager (imports are module-level functions)
        console.print(f"  [green]✓[/green] Scheduled action manager ready")

        # Initialize scheduler service
        self.scheduler_service = SchedulerService(
            execute_callback=self.execute_scheduled_action
        )
        console.print(f"  [green]✓[/green] Scheduler service initialized")

        # Initialize Claude agent with ALL skills
        self.agent = TelegramAgent(
            tone_of_voice_path=TONE_OF_VOICE_DIR,
            how_to_communicate_path=HOW_TO_COMMUNICATE_DIR,
            knowledge_base_path=KNOWLEDGE_BASE_DIR,
            config=self.config,
            agent_name=self.config.agent_name
        )
        console.print(f"  [green]✓[/green] Claude agent ready (with tone-of-voice + how-to-communicate + knowledge base)")

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

    def _register_handlers(self) -> None:
        """Register Telegram event handlers."""

        @self.client.on(events.NewMessage(incoming=True))
        async def handle_incoming(event):
            """Handle incoming messages."""
            # Only process private messages
            if not event.is_private:
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

            self.stats["messages_received"] += 1
            console.print(f"\n[cyan]← Received from {prospect.name}:[/cyan] {event.text[:100]}...")

            # Record the response
            self.prospect_manager.record_response(
                prospect.telegram_id,
                event.id,
                event.text
            )

            # Cancel pending follow-ups when client responds
            try:
                cancelled = await cancel_pending_for_prospect(
                    str(prospect.telegram_id),
                    reason="client_responded"
                )
                if cancelled > 0:
                    console.print(f"[dim]Cancelled {cancelled} pending follow-up(s)[/dim]")
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

            # Generate response
            try:
                action = await self.agent.generate_response(
                    prospect,
                    event.text,
                    context
                )

                console.print(f"[dim]Agent decision: {action.action} - {action.reason}[/dim]")

                # Handle check_availability action
                if action.action == "check_availability":
                    # Get available slots
                    availability_text = self.scheduling_tool.get_available_times(days=3)

                    # Send availability to user
                    await self.service.send_message(
                        prospect.telegram_id,
                        availability_text
                    )

                    console.print(f"[cyan]→ Sent availability to {prospect.name}[/cyan]")

                    # Update prospect to show we're in scheduling mode
                    self.prospect_manager.update_status(
                        prospect.telegram_id,
                        ProspectStatus.IN_CONVERSATION
                    )

                # Handle schedule action
                elif action.action == "schedule" and action.scheduling_data:
                    slot_id = action.scheduling_data.get("slot_id")
                    client_email = action.scheduling_data.get("email", "")
                    topic = action.scheduling_data.get("topic", "Консультация по недвижимости на Бали")

                    if not slot_id:
                        console.print(f"[red]Schedule action missing slot_id[/red]")
                        return

                    # STRICT: Email is REQUIRED for booking
                    if not client_email or not client_email.strip():
                        error_msg = "Для записи на встречу нужен email. На какой адрес отправить приглашение?"
                        await self.service.send_message(prospect.telegram_id, error_msg)
                        console.print(f"[yellow]⚠ Schedule rejected - no email provided[/yellow]")
                        return

                    # Store email in prospect record
                    self.prospect_manager.update_prospect_email(prospect.telegram_id, client_email.strip())

                    # Book the meeting (mock mode - no actual Zoom call)
                    result = self.scheduling_tool.book_meeting(
                        slot_id=slot_id,
                        prospect=prospect,
                        client_email=client_email.strip(),
                        topic=topic
                    )

                    if result.success:
                        # Send confirmation (no Zoom link in mock mode)
                        await self.service.send_message(
                            prospect.telegram_id,
                            result.message
                        )

                        # Update prospect status
                        self.prospect_manager.update_status(
                            prospect.telegram_id,
                            ProspectStatus.ZOOM_SCHEDULED
                        )

                        # Update stats
                        self.stats["meetings_scheduled"] += 1

                        console.print(f"[green]✓ Meeting scheduled for {prospect.name}: {slot_id} (email: {client_email})[/green]")
                    else:
                        # Send error message
                        await self.service.send_message(
                            prospect.telegram_id,
                            result.message
                        )
                        console.print(f"[red]✗ Scheduling failed: {result.error}[/red]")

                # Handle schedule_followup action
                elif action.action == "schedule_followup" and action.scheduling_data:
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
                                "original_context_snapshot": context[:1000]  # For reference, not for sending
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
                        if confirmation:
                            reasoning_patterns = ["Клиент ", "Это запрос", "schedule_followup", "нужно использовать", "follow-up" if len(confirmation) > 80 else ""]
                            if any(p and p in confirmation for p in reasoning_patterns):
                                console.print(f"[yellow]Detected leaked reasoning in confirmation, using fallback[/yellow]")
                                confirmation = None

                        if not confirmation:
                            # Calculate human-friendly time description
                            import pytz
                            bali_tz = pytz.timezone("Asia/Makassar")
                            now = datetime.now(bali_tz)
                            scheduled_local = scheduled_for.astimezone(bali_tz)

                            delta = scheduled_local - now
                            minutes = int(delta.total_seconds() / 60)

                            # Generate natural time expression
                            if minutes <= 5:
                                time_expr = "через 5 минут"
                            elif minutes <= 10:
                                time_expr = "минут через 10"
                            elif minutes <= 15:
                                time_expr = "минут через 15"
                            elif minutes <= 30:
                                time_expr = "через полчаса"
                            elif minutes <= 60:
                                time_expr = "через час"
                            elif minutes <= 120:
                                time_expr = "через пару часов"
                            elif scheduled_local.date() == now.date():
                                # Same day - round to nearest half hour
                                rounded_hour = scheduled_local.hour
                                rounded_min = 30 if scheduled_local.minute >= 15 and scheduled_local.minute < 45 else 0
                                if scheduled_local.minute >= 45:
                                    rounded_hour += 1
                                    rounded_min = 0
                                time_expr = f"около {rounded_hour}:{rounded_min:02d}"
                            elif (scheduled_local.date() - now.date()).days == 1:
                                time_expr = "завтра"
                            else:
                                # Fallback to day of week
                                days_ru = ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу", "в воскресенье"]
                                time_expr = days_ru[scheduled_local.weekday()]

                            confirmation = f"Хорошо, напишу {time_expr}! 👍"

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
                        console.print(f"[green]→ Sent to {prospect.name}:[/green] {action.message[:100]}...")
                    else:
                        console.print(f"[red]Failed to send: {result.get('error')}[/red]")

                # Handle escalate action
                elif action.action == "escalate":
                    self.stats["escalations"] += 1
                    console.print(f"[yellow]⚠ Escalated: {action.reason}[/yellow]")

                    # Notify if configured
                    if self.config.escalation_notify:
                        await self.service.notify_escalation(
                            self.config.escalation_notify,
                            prospect.name,
                            action.reason,
                            event.text
                        )

            except Exception as e:
                console.print(f"[red]Error processing message: {e}[/red]")

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
                        console.print(f"[green]→ Initial message sent to {prospect.name}[/green]")
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
                        console.print(f"[green]→ Follow-up sent to {prospect.name}[/green]")

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
            if action.status != "pending":
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

            if response.action == "reply" and response.message:
                message = response.message
            elif response.action == "wait":
                console.print(f"[yellow]Agent decided not to follow up with {prospect.name}: {response.reason}[/yellow]")
                return
            elif response.action == "schedule_followup":
                # Agent tried to recursively schedule - use the text message if safe
                console.print(f"[yellow]Agent tried to reschedule - using message text instead[/yellow]")
                reasoning_patterns = ["Клиент ", "Это запрос", "schedule", "follow-up", "нужно использ"]
                if response.message and not any(p in response.message for p in reasoning_patterns):
                    message = response.message
                else:
                    # Generate default follow-up message
                    message = f"Привет! Как обещал(а), пишу. {follow_up_intent or 'Как у вас дела?'}"
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

        # Stop scheduler
        if self.scheduler_service:
            await self.scheduler_service.stop()
            console.print("[green]Scheduler stopped[/green]")

        if self.client:
            await self.client.disconnect()
            console.print("[green]Disconnected from Telegram[/green]")

        console.print(Panel.fit(
            f"[bold]Final Stats[/bold]\n"
            f"Messages Sent: {self.stats['messages_sent']}\n"
            f"Messages Received: {self.stats['messages_received']}\n"
            f"Meetings Scheduled: {self.stats['meetings_scheduled']}\n"
            f"Scheduled Follow-ups: {self.stats.get('scheduled_followups', 0)}\n"
            f"Escalations: {self.stats['escalations']}",
            title="Session Summary"
        ))


async def main():
    """Main entry point."""
    daemon = TelegramDaemon()

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
