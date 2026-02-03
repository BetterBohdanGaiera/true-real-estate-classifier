---
name: scheduling
description: Follow-ups & calendar slots management. Use for scheduling delayed actions, managing calendar availability, coordinating Zoom bookings, and executing database-driven scheduled actions. Docker-safe with persistence.
---

# Scheduling Service

Database-driven scheduling for follow-ups, reminders, and calendar coordination. All scheduled actions persist across daemon restarts using PostgreSQL as the single source of truth.

## Prerequisites

1. **PostgreSQL Database**: Ensure DATABASE_URL is set in `.env`
2. **Migrations Applied**: Run migrations to create `scheduled_actions` table
3. **Python Dependencies**: asyncpg, pydantic, python-dotenv, rich

```bash
# Verify database connection
PYTHONPATH=src uv run python -c "from sales_agent.scheduling import scheduled_action_manager; print('OK')"
```

## Quick Start

### 1. Run the Scheduler Daemon

The scheduler daemon polls the database for due actions and executes them:

```bash
# Run scheduler as part of the main daemon
PYTHONPATH=src uv run python src/sales_agent/daemon.py

# Or run standalone follow-up polling daemon
PYTHONPATH=src uv run python src/sales_agent/scheduling/followup_polling_daemon.py
```

### 2. Check Pending Actions

```bash
PYTHONPATH=src uv run python -c "
import asyncio
from sales_agent.scheduling import scheduled_action_manager

async def check():
    actions = await scheduled_action_manager.get_pending_actions()
    for a in actions:
        print(f'{a.id[:8]}... | {a.prospect_id} | {a.scheduled_for} | {a.action_type}')

asyncio.run(check())
"
```

## Commands

### Scheduler Service Operations

```bash
# View scheduler health check
PYTHONPATH=src uv run python -c "
from sales_agent.scheduling import SchedulerService
from sales_agent.crm.models import ScheduledAction

async def noop(action): pass
service = SchedulerService(execute_callback=noop)
print(service.health_check())
"
```

### Scheduled Action Management

```bash
# Create a scheduled action (for testing)
PYTHONPATH=src uv run python -c "
import asyncio
from datetime import datetime, timedelta, timezone
from sales_agent.scheduling import scheduled_action_manager
from sales_agent.crm.models import ScheduledActionType

async def create():
    action = await scheduled_action_manager.create_scheduled_action(
        prospect_id='test_123',
        action_type=ScheduledActionType.FOLLOW_UP,
        scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2),
        payload={'message_template': 'Test follow-up', 'reason': 'testing'}
    )
    print(f'Created: {action.id}')

asyncio.run(create())
"

# Cancel all pending actions for a prospect
PYTHONPATH=src uv run python -c "
import asyncio
from sales_agent.scheduling import scheduled_action_manager

async def cancel():
    count = await scheduled_action_manager.cancel_pending_for_prospect(
        prospect_id='test_123',
        reason='manual_cancel'
    )
    print(f'Cancelled: {count} actions')

asyncio.run(cancel())
"

# Reset stale processing actions (crash recovery)
PYTHONPATH=src uv run python -c "
import asyncio
from sales_agent.scheduling import scheduled_action_manager

async def reset():
    count = await scheduled_action_manager.reset_stale_processing(stale_after_seconds=600)
    print(f'Reset: {count} stale actions')

asyncio.run(reset())
"
```

### Calendar Slot Management

```bash
# View available time slots
PYTHONPATH=src uv run python -c "
from pathlib import Path
from sales_agent.scheduling import SalesCalendar

config_path = Path('src/sales_agent/config/sales_slots.json')
calendar = SalesCalendar(config_path)

for slot in calendar.get_available_slots(days=3)[:5]:
    print(f'{slot.id} | {slot.date} {slot.start_time} | Available: {slot.is_available}')
"

# Book a slot
PYTHONPATH=src uv run python -c "
from pathlib import Path
from sales_agent.scheduling import SalesCalendar

config_path = Path('src/sales_agent/config/sales_slots.json')
calendar = SalesCalendar(config_path)

slots = calendar.get_available_slots(days=3)
if slots:
    result = calendar.book_slot(slots[0].id, prospect_id='test_prospect')
    print(f'Booked: {result.success} - {result.message}')
"

# Get formatted availability message (for agent responses)
PYTHONPATH=src uv run python -c "
from pathlib import Path
from sales_agent.scheduling import SalesCalendar

config_path = Path('src/sales_agent/config/sales_slots.json')
calendar = SalesCalendar(config_path)
print(calendar.format_available_slots_for_message(max_slots=5))
"
```

### Calendar-Aware Scheduling (Google Calendar Integration)

When a sales rep has connected their Google Calendar, the scheduler filters availability based on real calendar events:

```bash
# Get calendar-aware availability (requires connected Google Calendar)
PYTHONPATH=src uv run python -c "
from sales_agent.scheduling.calendar_aware_scheduler import CalendarAwareScheduler
from sales_agent.registry.calendar_connector import CalendarConnector

connector = CalendarConnector()
rep_telegram_id = 123456789  # Replace with actual rep ID

if connector.is_connected(rep_telegram_id):
    scheduler = CalendarAwareScheduler(
        calendar_connector=connector,
        telegram_id=rep_telegram_id
    )
    slots = scheduler.get_available_slots(days=7)
    for slot in slots[:5]:
        print(f'{slot.date} {slot.start_time}-{slot.end_time}')
else:
    print('Calendar not connected for this rep')
"
```

### Scheduling Tool (Agent Interface)

The SchedulingTool provides the interface for the LLM agent to book meetings:

```bash
# Test scheduling tool
PYTHONPATH=src uv run python src/sales_agent/scheduling/scheduling_tool.py
```

## Architecture Notes

### Database-Driven Design (Docker-Safe)

The scheduling system uses PostgreSQL as the single source of truth:

- **No in-memory state**: All scheduled actions are stored in `scheduled_actions` table
- **Docker restart safe**: Actions persist across daemon restarts
- **Recovery on startup**: Stale "processing" actions are reset to "pending"
- **Row-level locking**: `FOR UPDATE SKIP LOCKED` prevents duplicate execution

### Polling Daemon Flow

```
FollowUpPollingDaemon
         |
         v
[Poll every 30s] --> claim_due_actions(limit=10)
         |                    |
         |              (FOR UPDATE SKIP LOCKED)
         v                    v
   Execute action      Update status -> 'processing'
         |
         v
   mark_executed()  --> Update status -> 'executed'
```

### Action Status Lifecycle

```
pending --> processing --> executed
    |                        |
    +-----> cancelled <------+
            (on client response or manual cancel)
```

### Components

| Module | Purpose |
|--------|---------|
| `scheduler_service.py` | High-level wrapper for scheduling operations |
| `followup_polling_daemon.py` | Database polling and action execution loop |
| `scheduled_action_manager.py` | CRUD operations for scheduled_actions table |
| `sales_calendar.py` | Mock slot generation and booking management |
| `calendar_aware_scheduler.py` | Google Calendar integration bridge |
| `scheduling_tool.py` | LLM agent interface for booking meetings |

### Config Files

| File | Purpose |
|------|---------|
| `config/sales_slots.json` | Calendar configuration (working hours, timezone) |
| `config/sales_slots_data.json` | Persisted slot data (auto-generated) |

### Polling Configuration

Default polling settings (configurable via `FollowUpPollingConfig`):

| Setting | Default | Description |
|---------|---------|-------------|
| `poll_interval_seconds` | 30 | How often to check for due actions |
| `batch_size` | 10 | Max actions to claim per poll |
| `preemptive_window_seconds` | 5 | Claim actions up to N seconds before due |

### Integration Points

- **Telegram Agent**: Schedules follow-ups via `create_scheduled_action()`
- **Google Calendar**: `CalendarAwareScheduler` filters slots by busy periods
- **Zoom Service**: `SchedulingTool` creates Zoom meetings when booking slots
- **CRM Models**: Uses `ScheduledAction`, `SalesSlot`, `SchedulingResult` from models

## Validation Commands

```bash
# Verify scheduling module imports
PYTHONPATH=src uv run python -c "
from sales_agent.scheduling import (
    SalesCalendar,
    SchedulingTool,
    SchedulerService,
    FollowUpPollingDaemon,
    scheduled_action_manager,
)
print('All scheduling imports OK')
"

# Check database connection for scheduled actions
PYTHONPATH=src uv run python -c "
import asyncio
from sales_agent.scheduling.scheduled_action_manager import get_pool

async def check():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval('SELECT COUNT(*) FROM scheduled_actions')
        print(f'Scheduled actions in database: {result}')

asyncio.run(check())
"

# Verify calendar config exists
ls -la src/sales_agent/config/sales_slots*.json
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Database connection fails | Exponential backoff (max 5 minutes) |
| Action execution fails | Logged, continues with next action |
| Daemon crashes during processing | Reset stale actions on next startup |
| Google Calendar unavailable | Falls back to mock slot generation |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ZOOM_ACCOUNT_ID` | No | For Zoom meeting creation |
| `ZOOM_CLIENT_ID` | No | For Zoom meeting creation |
| `ZOOM_CLIENT_SECRET` | No | For Zoom meeting creation |

## Related Skills

- **google-calendar**: Google Calendar OAuth and event management
- **zoom**: Zoom meeting creation and management
- **register-sales**: Sales rep registration with calendar connection
- **telegram**: Main daemon that uses scheduler for follow-ups
