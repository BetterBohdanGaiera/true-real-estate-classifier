# Plan: Test Smart Follow-ups Quick Validation

## Task Description
Validate the smart follow-ups and delayed action system by running the database migration and testing with a 1-2 minute scheduled follow-up to quickly verify the entire flow works end-to-end.

## Objective
Confirm that:
1. Database migration runs successfully on Neon PostgreSQL
2. ScheduledActionManager can create/read/cancel actions
3. SchedulerService schedules and executes actions
4. TelegramDaemon properly handles the schedule_followup action
5. Actions execute at the scheduled time (within ~1 minute accuracy)

## Relevant Files

### Existing Files to Use
- `.claude/skills/telegram/migrations/001_scheduled_actions.sql` - Database migration
- `.claude/skills/telegram/scripts/scheduled_action_manager.py` - Database CRUD
- `.claude/skills/telegram/scripts/scheduler_service.py` - APScheduler service
- `.claude/skills/telegram/scripts/run_daemon.py` - Main daemon with integration
- `.claude/skills/telegram/scripts/models.py` - Pydantic models
- `.env` - Contains DATABASE_URL for Neon PostgreSQL

### New Files to Create
- `.claude/skills/telegram/scripts/test_scheduled_actions.py` - Quick validation script

## Step by Step Tasks

### 1. Verify DATABASE_URL is Set
- Check `.env` file contains `DATABASE_URL` with Neon connection string
- Ensure connection string has `?sslmode=require` for Neon
- Test connection with a simple query

### 2. Run Database Migration
- Execute the migration SQL file against Neon database
- Verify table `scheduled_actions` was created
- Verify indexes were created

### 3. Create Quick Validation Script
Create `.claude/skills/telegram/scripts/test_scheduled_actions.py` that:
- Tests ScheduledActionManager CRUD operations
- Tests SchedulerService scheduling (1-minute delay)
- Logs execution when action fires
- Cleans up test data after completion

```python
#!/usr/bin/env python3
"""
Quick validation script for smart follow-ups system.
Tests the complete flow: create action → schedule → execute → verify.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv()

from models import ScheduledAction, ScheduledActionType, ScheduledActionStatus
from scheduled_action_manager import (
    create_scheduled_action,
    get_pending_actions,
    get_by_id,
    cancel_pending_for_prospect,
    mark_executed,
    close_pool,
)
from scheduler_service import SchedulerService

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
    console.print(f"[bold green]🎉 ACTION EXECUTED![/bold green]")
    console.print(f"  Action ID: {action.id}")
    console.print(f"  Prospect: {action.prospect_id}")
    console.print(f"  Message: {action.payload.get('message_template', 'N/A')}")


async def test_database_connection():
    """Test 1: Verify database connection works."""
    console.print("\n[bold cyan]Test 1: Database Connection[/bold cyan]")

    try:
        # Try to get pending actions (will create connection pool)
        actions = await get_pending_actions()
        console.print(f"  [green]✓[/green] Connected to database")
        console.print(f"  [dim]Found {len(actions)} existing pending actions[/dim]")
        return True
    except Exception as e:
        console.print(f"  [red]✗[/red] Connection failed: {e}")
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
        console.print(f"  [green]✓[/green] Created action: {action.id}")

        # Read
        fetched = await get_by_id(action.id)
        assert fetched is not None, "Failed to fetch created action"
        assert fetched.prospect_id == test_prospect_id
        console.print(f"  [green]✓[/green] Read action successfully")

        # Get pending
        pending = await get_pending_actions(prospect_id=test_prospect_id)
        assert len(pending) >= 1, "No pending actions found"
        console.print(f"  [green]✓[/green] Found {len(pending)} pending action(s)")

        # Cancel
        cancelled = await cancel_pending_for_prospect(test_prospect_id, "test_cleanup")
        console.print(f"  [green]✓[/green] Cancelled {cancelled} action(s)")

        # Verify cancelled
        fetched_after = await get_by_id(action.id)
        assert fetched_after.status == "cancelled", f"Expected cancelled, got {fetched_after.status}"
        console.print(f"  [green]✓[/green] Verified cancellation")

        return True
    except Exception as e:
        console.print(f"  [red]✗[/red] CRUD test failed: {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


async def test_quick_schedule(delay_seconds: int = 60):
    """Test 3: Schedule an action and wait for execution."""
    console.print(f"\n[bold cyan]Test 3: Quick Schedule ({delay_seconds}s delay)[/bold cyan]")

    test_prospect_id = "TEST_QUICK_SCHEDULE"

    try:
        # Create scheduler service
        scheduler = SchedulerService(execute_callback=mock_execute_callback)
        await scheduler.start()
        console.print(f"  [green]✓[/green] Scheduler started")

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
        console.print(f"  [green]✓[/green] Created action: {action.id}")
        console.print(f"  [dim]Scheduled for: {scheduled_for.strftime('%H:%M:%S')} UTC[/dim]")

        # Schedule with APScheduler
        job_id = await scheduler.schedule_action(action)
        console.print(f"  [green]✓[/green] Scheduled with APScheduler (job: {job_id})")

        # Wait for execution
        console.print(f"\n[yellow]⏳ Waiting {delay_seconds} seconds for execution...[/yellow]")
        console.print("[dim]You should see '🎉 ACTION EXECUTED!' when it fires[/dim]\n")

        wait_start = datetime.now()
        max_wait = delay_seconds + 30  # Extra buffer

        while (datetime.now() - wait_start).total_seconds() < max_wait:
            if execution_log:
                # Action executed!
                console.print(f"\n[bold green]✓ Action executed successfully![/bold green]")

                exec_info = execution_log[0]
                scheduled_time = action.scheduled_for
                actual_time = exec_info["executed_at"]
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
            if remaining > 0 and elapsed % 10 == 0:
                console.print(f"[dim]  ... {remaining}s remaining[/dim]")

            await asyncio.sleep(1)

        # Timeout
        console.print(f"[red]✗ Timeout - action did not execute within {max_wait}s[/red]")
        await cancel_pending_for_prospect(test_prospect_id, "test_timeout")
        await scheduler.stop()
        return False

    except Exception as e:
        console.print(f"  [red]✗[/red] Schedule test failed: {e}")
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
        console.print(f"  [green]✓[/green] Created and scheduled action")

        # Cancel immediately (simulating client response)
        cancelled = await cancel_pending_for_prospect(test_prospect_id, "client_responded")
        console.print(f"  [green]✓[/green] Cancelled {cancelled} action(s)")

        # Wait briefly
        await asyncio.sleep(2)

        # Verify no execution
        if not execution_log:
            console.print(f"  [green]✓[/green] Confirmed: cancelled action was not executed")
            await scheduler.stop()
            return True
        else:
            console.print(f"  [red]✗[/red] Action was executed despite cancellation!")
            await scheduler.stop()
            return False

    except Exception as e:
        console.print(f"  [red]✗[/red] Cancellation test failed: {e}")
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
        return

    # Test 2: CRUD operations
    results["crud"] = await test_crud_operations()

    # Test 3: Quick schedule (use command line arg for delay)
    import sys
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
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        console.print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    console.print("="*50)
    if all_passed:
        console.print("[bold green]All tests passed! 🎉[/bold green]")
    else:
        console.print("[bold red]Some tests failed[/bold red]")

    # Cleanup
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Run the Migration
- Execute: `psql $DATABASE_URL -f .claude/skills/telegram/migrations/001_scheduled_actions.sql`
- If psql not available, use the Python script to run migration

### 5. Run Validation Tests
- Execute quick test with 60 second delay: `uv run python .claude/skills/telegram/scripts/test_scheduled_actions.py 60`
- For faster test (90 seconds total): `uv run python .claude/skills/telegram/scripts/test_scheduled_actions.py 60`
- Watch for "🎉 ACTION EXECUTED!" message

### 6. Verify Results
- All 4 tests should pass:
  - Database Connection
  - CRUD Operations
  - Quick Schedule (action executes at scheduled time)
  - Cancellation (cancelled actions don't execute)

## Acceptance Criteria
- [ ] Database migration runs without errors
- [ ] `scheduled_actions` table exists with correct schema
- [ ] ScheduledActionManager can create, read, and cancel actions
- [ ] SchedulerService schedules action and executes at correct time
- [ ] Cancelled actions are NOT executed
- [ ] All 4 validation tests pass

## Validation Commands
```bash
# 1. Verify DATABASE_URL is set
grep DATABASE_URL .env

# 2. Run migration (if psql available)
psql $DATABASE_URL -f .claude/skills/telegram/migrations/001_scheduled_actions.sql

# 3. Verify table exists
psql $DATABASE_URL -c "\d scheduled_actions"

# 4. Run validation tests (60 second delay)
uv run python .claude/skills/telegram/scripts/test_scheduled_actions.py 60

# 5. Quick syntax check
uv run python -m py_compile .claude/skills/telegram/scripts/test_scheduled_actions.py
```

## Notes

### Neon PostgreSQL Setup
- Neon requires `?sslmode=require` in connection string
- Free tier supports this use case

**Connection String (add to `.env`):**
```bash
DATABASE_URL=postgresql://neondb_owner:npg_y6fiMl2aGbZu@ep-holy-base-ah5rapyz-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

**Quick setup:**
```bash
echo 'DATABASE_URL=postgresql://neondb_owner:npg_y6fiMl2aGbZu@ep-holy-base-ah5rapyz-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require' >> .env
```

### Test Timing
- Default test uses 60 second delay
- Pass argument to change: `python test_scheduled_actions.py 90` for 90 seconds
- Total test time ≈ delay + 30 seconds buffer

### If psql Not Available
Run migration via Python:
```python
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    with open(".claude/skills/telegram/migrations/001_scheduled_actions.sql") as f:
        await conn.execute(f.read())
    await conn.close()
    print("Migration complete!")

asyncio.run(run_migration())
```

### Dependencies
All dependencies should already be installed from previous implementation:
- `apscheduler>=4.0.0a5`
- `sqlalchemy[asyncio]>=2.0.0`
- `asyncpg>=0.29.0`
