#!/usr/bin/env python3
"""
Quick validation script for smart follow-ups system.
Tests the complete flow: create action -> schedule -> execute -> verify.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Setup paths
SCRIPTS_DIR = Path(__file__).parent
SKILLS_BASE = SCRIPTS_DIR.parent.parent
PROJECT_ROOT = SKILLS_BASE.parent.parent

# Load environment
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv()

# Add src to path for imports
_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from sales_agent.crm.models import ScheduledAction, ScheduledActionType, ScheduledActionStatus
from sales_agent.scheduling.scheduled_action_manager import (
    create_scheduled_action,
    get_pending_actions,
    get_by_id,
    cancel_pending_for_prospect,
    mark_executed,
    close_pool,
)
from sales_agent.scheduling import SchedulerService

console = Console()

# Track if action was executed
execution_log = []


async def mock_execute_callback(action: ScheduledAction):
    """Mock execution callback that logs when action fires."""
    execution_log.append({
        "action_id": action.id,
        "executed_at": datetime.now(timezone.utc),
        "prospect_id": action.prospect_id,
        "message": action.payload.get("message_template", "No message")
    })
    console.print(f"\n[bold green]ACTION EXECUTED![/bold green]")
    console.print(f"  Action ID: {action.id}")
    console.print(f"  Prospect: {action.prospect_id}")
    console.print(f"  Message: {action.payload.get('message_template', 'N/A')[:50]}...")


async def test_database_connection():
    """Test 1: Verify database connection works."""
    console.print("\n[bold cyan]Test 1: Database Connection[/bold cyan]")

    try:
        # Try to get pending actions (will create connection pool)
        actions = await get_pending_actions()
        console.print(f"  [green]>[/green] Connected to database")
        console.print(f"  [dim]Found {len(actions)} existing pending actions[/dim]")
        return True
    except Exception as e:
        console.print(f"  [red]x[/red] Connection failed: {e}")
        return False


async def test_crud_operations():
    """Test 2: Test CRUD operations on scheduled_actions."""
    console.print("\n[bold cyan]Test 2: CRUD Operations[/bold cyan]")

    test_prospect_id = "TEST_PROSPECT_999"

    try:
        # Create
        scheduled_for = datetime.now(timezone.utc) + timedelta(hours=1)
        action = await create_scheduled_action(
            prospect_id=test_prospect_id,
            action_type=ScheduledActionType.FOLLOW_UP,
            scheduled_for=scheduled_for,
            payload={
                "message_template": "Test follow-up message",
                "reason": "CRUD test"
            }
        )
        console.print(f"  [green]>[/green] Created action: {action.id[:8]}...")

        # Read
        fetched = await get_by_id(action.id)
        assert fetched is not None, "Failed to fetch created action"
        assert fetched.prospect_id == test_prospect_id
        console.print(f"  [green]>[/green] Read action successfully")

        # Get pending
        pending = await get_pending_actions(prospect_id=test_prospect_id)
        assert len(pending) >= 1, "No pending actions found"
        console.print(f"  [green]>[/green] Found {len(pending)} pending action(s)")

        # Cancel
        cancelled = await cancel_pending_for_prospect(test_prospect_id, "test_cleanup")
        console.print(f"  [green]>[/green] Cancelled {cancelled} action(s)")

        # Verify cancelled
        fetched_after = await get_by_id(action.id)
        assert fetched_after.status == "cancelled", f"Expected cancelled, got {fetched_after.status}"
        console.print(f"  [green]>[/green] Verified cancellation")

        return True
    except Exception as e:
        console.print(f"  [red]x[/red] CRUD test failed: {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


async def test_quick_schedule(delay_seconds: int = 60):
    """Test 3: Schedule an action and wait for execution."""
    console.print(f"\n[bold cyan]Test 3: Quick Schedule ({delay_seconds}s delay)[/bold cyan]")

    test_prospect_id = "TEST_QUICK_SCHEDULE"
    execution_log.clear()

    try:
        # Create scheduler service
        scheduler = SchedulerService(execute_callback=mock_execute_callback)
        await scheduler.start()
        console.print(f"  [green]>[/green] Scheduler started")

        # Create action scheduled for N seconds from now
        scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        action = await create_scheduled_action(
            prospect_id=test_prospect_id,
            action_type=ScheduledActionType.FOLLOW_UP,
            scheduled_for=scheduled_for,
            payload={
                "message_template": f"Quick test message - scheduled for {scheduled_for.isoformat()}",
                "reason": "Quick validation test"
            }
        )
        console.print(f"  [green]>[/green] Created action: {action.id[:8]}...")
        console.print(f"  [dim]Scheduled for: {scheduled_for.strftime('%H:%M:%S')} UTC[/dim]")

        # Schedule with APScheduler
        job_id = await scheduler.schedule_action(action)
        console.print(f"  [green]>[/green] Scheduled with APScheduler")

        # Wait for execution
        console.print(f"\n[yellow]Waiting {delay_seconds} seconds for execution...[/yellow]")
        console.print("[dim]You should see 'ACTION EXECUTED!' when it fires[/dim]\n")

        wait_start = datetime.now()
        max_wait = delay_seconds + 30  # Extra buffer

        while (datetime.now() - wait_start).total_seconds() < max_wait:
            if execution_log:
                # Action executed!
                console.print(f"\n[bold green]> Action executed successfully![/bold green]")

                exec_info = execution_log[0]
                scheduled_time = action.scheduled_for
                actual_time = exec_info["executed_at"]

                # Handle timezone-aware comparison
                if scheduled_time.tzinfo is None:
                    scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

                delay = (actual_time - scheduled_time).total_seconds()

                console.print(f"  Scheduled: {scheduled_time.strftime('%H:%M:%S')} UTC")
                console.print(f"  Executed:  {actual_time.strftime('%H:%M:%S')} UTC")
                console.print(f"  Delay:     {delay:.1f} seconds")

                # Cleanup
                await cancel_pending_for_prospect(test_prospect_id, "test_complete")
                await scheduler.stop()

                return True

            # Show countdown
            elapsed = int((datetime.now() - wait_start).total_seconds())
            remaining = delay_seconds - elapsed
            if remaining > 0 and elapsed % 15 == 0:
                console.print(f"[dim]  ... {remaining}s remaining[/dim]")

            await asyncio.sleep(1)

        # Timeout
        console.print(f"[red]x Timeout - action did not execute within {max_wait}s[/red]")
        await cancel_pending_for_prospect(test_prospect_id, "test_timeout")
        await scheduler.stop()
        return False

    except Exception as e:
        console.print(f"  [red]x[/red] Schedule test failed: {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


async def test_cancellation():
    """Test 4: Test that cancellation prevents execution."""
    console.print("\n[bold cyan]Test 4: Cancellation Prevents Execution[/bold cyan]")

    test_prospect_id = "TEST_CANCELLATION"
    execution_log.clear()

    try:
        # Create scheduler
        scheduler = SchedulerService(execute_callback=mock_execute_callback)
        await scheduler.start()

        # Schedule action for 30 seconds
        scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=30)
        action = await create_scheduled_action(
            prospect_id=test_prospect_id,
            action_type=ScheduledActionType.FOLLOW_UP,
            scheduled_for=scheduled_for,
            payload={"message_template": "This should be cancelled"}
        )
        await scheduler.schedule_action(action)
        console.print(f"  [green]>[/green] Created and scheduled action")

        # Cancel immediately (simulating client response)
        cancelled = await cancel_pending_for_prospect(test_prospect_id, "client_responded")
        console.print(f"  [green]>[/green] Cancelled {cancelled} action(s)")

        # Wait briefly
        await asyncio.sleep(2)

        # Verify no execution
        if not execution_log:
            console.print(f"  [green]>[/green] Confirmed: cancelled action was not executed")
            await scheduler.stop()
            return True
        else:
            console.print(f"  [red]x[/red] Action was executed despite cancellation!")
            await scheduler.stop()
            return False

    except Exception as e:
        console.print(f"  [red]x[/red] Cancellation test failed: {e}")
        return False


async def main():
    """Run all validation tests."""
    console.print(Panel.fit(
        "[bold]Smart Follow-ups Quick Validation[/bold]\n"
        "Testing database, CRUD, scheduling, and cancellation",
        title="Test Suite"
    ))

    results = {}

    # Test 1: Database connection
    results["database"] = await test_database_connection()
    if not results["database"]:
        console.print("\n[red bold]Cannot proceed without database connection[/red bold]")
        await close_pool()
        return

    # Test 2: CRUD operations
    results["crud"] = await test_crud_operations()

    # Test 3: Quick schedule (use command line arg for delay)
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    results["schedule"] = await test_quick_schedule(delay_seconds=delay)

    # Test 4: Cancellation
    results["cancellation"] = await test_cancellation()

    # Summary
    console.print("\n" + "="*50)
    console.print("[bold]Test Summary[/bold]")
    console.print("="*50)

    all_passed = True
    for test_name, passed in results.items():
        status = "[green]> PASS[/green]" if passed else "[red]x FAIL[/red]"
        console.print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    console.print("="*50)
    if all_passed:
        console.print("[bold green]All tests passed![/bold green]")
    else:
        console.print("[bold red]Some tests failed[/bold red]")

    # Cleanup
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
