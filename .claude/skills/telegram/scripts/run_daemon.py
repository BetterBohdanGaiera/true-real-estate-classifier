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

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from telegram_fetch import get_client
from telegram_service import TelegramService, is_private_chat
from telegram_agent import TelegramAgent
from prospect_manager import ProspectManager
from models import AgentConfig, ProspectStatus
from knowledge_loader import KnowledgeLoader
from sales_calendar import SalesCalendar
from scheduling_tool import SchedulingTool

console = Console()

# Configuration paths
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
PROSPECTS_FILE = CONFIG_DIR / "prospects.json"
AGENT_CONFIG_FILE = CONFIG_DIR / "agent_config.json"
TONE_OF_VOICE_DIR = SCRIPT_DIR.parent.parent / "tone-of-voice"
HOW_TO_COMMUNICATE_DIR = SCRIPT_DIR.parent.parent / "how-to-communicate"
KNOWLEDGE_BASE_DIR = SCRIPT_DIR.parent.parent.parent.parent / "knowledge_base_final"
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
        self.running = False
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "escalations": 0,
            "meetings_scheduled": 0,
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
                    topic = action.scheduling_data.get("topic", "Консультация по недвижимости на Бали")

                    if not slot_id:
                        console.print(f"[red]Schedule action missing slot_id[/red]")
                        return

                    # Book the meeting
                    result = self.scheduling_tool.book_zoom_call(
                        slot_id=slot_id,
                        prospect=prospect,
                        topic=topic
                    )

                    if result.success:
                        # Send confirmation with Zoom link
                        confirmation = f"{result.message}\n\n🔗 Ссылка на встречу: {result.zoom_url}"
                        await self.service.send_message(
                            prospect.telegram_id,
                            confirmation
                        )

                        # Update prospect status
                        self.prospect_manager.update_status(
                            prospect.telegram_id,
                            ProspectStatus.ZOOM_SCHEDULED
                        )

                        # Update stats
                        self.stats["meetings_scheduled"] += 1

                        console.print(f"[green]✓ Meeting scheduled for {prospect.name}: {slot_id}[/green]")
                    else:
                        # Send error message
                        await self.service.send_message(
                            prospect.telegram_id,
                            result.message
                        )
                        console.print(f"[red]✗ Scheduling failed: {result.error}[/red]")

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

        if self.client:
            await self.client.disconnect()
            console.print("[green]Disconnected from Telegram[/green]")

        console.print(Panel.fit(
            f"[bold]Final Stats[/bold]\n"
            f"Messages Sent: {self.stats['messages_sent']}\n"
            f"Messages Received: {self.stats['messages_received']}\n"
            f"Meetings Scheduled: {self.stats['meetings_scheduled']}\n"
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
