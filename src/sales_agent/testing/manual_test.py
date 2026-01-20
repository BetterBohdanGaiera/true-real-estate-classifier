#!/usr/bin/env python3
"""
Manual Testing Script for Telegram Agent.

Resets test prospect to 'new' status and optionally starts daemon for manual testing.
This provides a streamlined workflow for manual testing where Claude can correctly
identify test accounts and initiate the conversation.

Usage:
    # Reset and start daemon
    PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py

    # Reset only (without starting daemon)
    PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py --reset-only

    # Reset and clean Telegram chat history
    PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py --clean-chat
"""
import asyncio
import argparse
import json
import subprocess
import sys
from pathlib import Path

# Setup paths before any sales_agent imports
# PROJECT_ROOT is the Classifier directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Add src directory to Python path for package imports
_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Add telegram skills directory to path for telegram_fetch import
# telegram_fetch remains in .claude/skills/telegram/scripts/
_SKILLS_TELEGRAM_SCRIPTS = PROJECT_ROOT / ".claude/skills/telegram/scripts"
if str(_SKILLS_TELEGRAM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILLS_TELEGRAM_SCRIPTS))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment from project root
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv()

from sales_agent.crm import ProspectManager
from sales_agent.telegram.telegram_service import create_telegram_service
from sales_agent.scheduling.scheduled_action_manager import (
    cancel_pending_for_prospect,
    close_pool,
)

console = Console()

# Paths
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
TEST_ACCOUNTS_FILE = CONFIG_DIR / "test_accounts.json"
PROSPECTS_FILE = CONFIG_DIR / "prospects.json"


def load_test_config() -> dict:
    """
    Load test accounts configuration.

    Returns:
        dict: Test configuration with test_prospects list

    Raises:
        SystemExit: If test config file is not found
    """
    if not TEST_ACCOUNTS_FILE.exists():
        console.print(f"[red]Error: Test config not found at {TEST_ACCOUNTS_FILE}[/red]")
        console.print("\n[yellow]Please create the test config file with the following structure:[/yellow]")
        console.print("""
{
  "test_prospects": [
    {
      "telegram_id": "@username",
      "name": "Test User Name",
      "description": "Test account for manual testing"
    }
  ]
}
""")
        sys.exit(1)

    with open(TEST_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


async def reset_test_prospect(clean_chat: bool = False) -> dict:
    """
    Reset test prospect to 'new' status.

    This function performs the following:
    1. Loads test account configuration
    2. Resets the prospect status to 'new' and clears conversation history
    3. Cancels any pending scheduled actions from the database
    4. Optionally deletes agent messages from Telegram chat

    Args:
        clean_chat: If True, also delete agent messages from Telegram

    Returns:
        dict with reset status including:
            - telegram_id: The prospect's telegram ID
            - name: The prospect's name
            - agent_message_ids: List of message IDs that were in history
            - deleted_count: Number of messages deleted from Telegram (if clean_chat=True)
    """
    # Load config
    test_config = load_test_config()

    if not test_config.get("test_prospects"):
        console.print("[red]Error: No test prospects defined in config[/red]")
        sys.exit(1)

    test_prospect = test_config["test_prospects"][0]
    telegram_id = test_prospect["telegram_id"]

    console.print(f"[cyan]Resetting test prospect: {test_prospect['name']} ({telegram_id})[/cyan]")

    # Initialize ProspectManager
    if not PROSPECTS_FILE.exists():
        console.print(f"[red]Error: Prospects file not found at {PROSPECTS_FILE}[/red]")
        sys.exit(1)

    prospect_manager = ProspectManager(PROSPECTS_FILE)

    # Check if prospect exists
    if not prospect_manager.is_prospect(telegram_id):
        console.print(f"[yellow]Warning: Prospect {telegram_id} not found in prospects.json[/yellow]")
        console.print("[dim]  The prospect may need to be added first.[/dim]")
        return {
            "telegram_id": telegram_id,
            "name": test_prospect["name"],
            "agent_message_ids": [],
            "deleted_count": 0,
            "error": "Prospect not found"
        }

    # Reset in ProspectManager
    try:
        agent_message_ids = prospect_manager.reset_prospect(telegram_id)
        console.print(f"[green]>[/green] Prospect reset to 'new' status")
        console.print(f"[dim]  Found {len(agent_message_ids)} agent messages in history[/dim]")
    except ValueError as e:
        console.print(f"[red]Error resetting prospect: {e}[/red]")
        return {
            "telegram_id": telegram_id,
            "name": test_prospect["name"],
            "agent_message_ids": [],
            "deleted_count": 0,
            "error": str(e)
        }

    # Clear pending scheduled actions
    try:
        cancelled = await cancel_pending_for_prospect(
            str(telegram_id),
            reason="manual_test_reset"
        )
        if cancelled > 0:
            console.print(f"[green]>[/green] Cancelled {cancelled} pending scheduled action(s)")
        else:
            console.print(f"[dim]  No pending scheduled actions to cancel[/dim]")
    except RuntimeError as e:
        # RuntimeError is raised when DATABASE_URL is not set
        console.print(f"[yellow]![/yellow] Could not cancel scheduled actions: {e}")
        console.print(f"[dim]  (This is OK if DATABASE_URL is not configured)[/dim]")
    except Exception as e:
        console.print(f"[yellow]![/yellow] Could not cancel scheduled actions: {e}")
        console.print(f"[dim]  (This is OK if DATABASE_URL is not configured)[/dim]")

    # Clean Telegram chat if requested
    deleted_count = 0
    if clean_chat and agent_message_ids:
        console.print(f"[cyan]Cleaning Telegram chat history...[/cyan]")
        try:
            service = await create_telegram_service()
            deleted_count = await service.delete_conversation_messages(
                telegram_id,
                agent_message_ids
            )
            console.print(f"[green]>[/green] Deleted {deleted_count} agent message(s) from Telegram")
            await service.client.disconnect()
        except Exception as e:
            console.print(f"[yellow]![/yellow] Could not delete Telegram messages: {e}")
    elif clean_chat and not agent_message_ids:
        console.print(f"[dim]  No agent messages to delete from Telegram[/dim]")

    return {
        "telegram_id": telegram_id,
        "name": test_prospect["name"],
        "agent_message_ids": agent_message_ids,
        "deleted_count": deleted_count
    }


async def start_test_session(clean_chat: bool = False) -> None:
    """
    Reset test prospect and start daemon for manual testing.

    This function:
    1. Resets the test prospect to 'new' status
    2. Starts the daemon subprocess
    3. Provides instructions for the user

    Args:
        clean_chat: If True, also delete agent messages from Telegram
    """
    console.print(Panel.fit(
        "[bold]Manual Test Session[/bold]\n"
        "Resetting test prospect and starting daemon",
        title="Telegram Agent Test",
        width=60
    ))

    # Reset prospect
    result = await reset_test_prospect(clean_chat=clean_chat)

    if result.get("error"):
        console.print(f"\n[yellow]Warning: {result['error']}[/yellow]")
        console.print("[dim]Continuing with daemon start anyway...[/dim]")

    console.print("\n[bold green]Test prospect ready![/bold green]")
    console.print(f"Prospect: {result['name']} ({result['telegram_id']})")
    console.print("Status: NEW (initial message will be sent)")

    # Start daemon
    console.print("\n[cyan]Starting daemon...[/cyan]")
    daemon_script = SCRIPT_DIR.parent / "daemon.py"

    if not daemon_script.exists():
        console.print(f"[red]Error: Daemon script not found at {daemon_script}[/red]")
        sys.exit(1)

    console.print(Panel.fit(
        "[bold]Daemon will now start[/bold]\n\n"
        "The initial message will be sent to the test prospect.\n"
        "Respond via Telegram to test the conversation flow.\n\n"
        "Press Ctrl+C to stop the daemon.",
        title="Instructions",
        width=60
    ))

    # Close database pool before starting subprocess
    try:
        await close_pool()
    except Exception:
        pass  # Pool may not have been initialized

    # Run daemon (blocks until stopped)
    subprocess.run([sys.executable, str(daemon_script)], check=False)


def main() -> None:
    """CLI entry point for manual testing script."""
    parser = argparse.ArgumentParser(
        description="Manual testing script for Telegram Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reset test prospect and start daemon
  uv run python src/sales_agent/testing/manual_test.py

  # Reset only (without starting daemon)
  uv run python src/sales_agent/testing/manual_test.py --reset-only

  # Reset and clean Telegram chat history
  uv run python src/sales_agent/testing/manual_test.py --clean-chat

  # Reset only with chat cleanup
  uv run python src/sales_agent/testing/manual_test.py --reset-only --clean-chat
"""
    )
    parser.add_argument(
        "--reset-only",
        action="store_true",
        help="Reset prospect without starting daemon"
    )
    parser.add_argument(
        "--clean-chat",
        action="store_true",
        help="Also delete agent messages from Telegram chat"
    )

    args = parser.parse_args()

    if args.reset_only:
        # Just reset, don't start daemon
        asyncio.run(reset_test_prospect(clean_chat=args.clean_chat))
        console.print("\n[green]Reset complete![/green]")
        console.print("Run without --reset-only to start the daemon.")

        # Close database pool
        try:
            asyncio.run(close_pool())
        except Exception:
            pass
    else:
        # Full test session
        asyncio.run(start_test_session(clean_chat=args.clean_chat))


if __name__ == "__main__":
    main()
