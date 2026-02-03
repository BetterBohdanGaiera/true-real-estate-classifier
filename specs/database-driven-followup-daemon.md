# Plan: Database-Driven Follow-up System with Centralized Polling Daemon

## Task Description

Переосмыслить текущий подход к follow-up сообщениям. Вместо того чтобы использовать `asyncio.sleep()` внутри одного демона для задержек (5/10/20/30 минут), создать централизованную систему на основе базы данных, где:

1. Статус follow-up хранится в базе данных с точным временем исполнения (`scheduled_for`)
2. Отдельный "follow-up daemon" пуллит базу данных каждые N секунд
3. Когда наступает время (`scheduled_for <= NOW()`), демон подтягивает и отправляет сообщение
4. Система хорошо работает в Docker-окружении (переживает рестарты контейнеров)

## Objective

Создать надежную, централизованную систему follow-up сообщений, которая:
- Использует PostgreSQL как единый источник правды для статуса scheduled actions
- Работает через database polling вместо in-memory asyncio tasks
- Корректно работает при рестартах Docker контейнеров
- Масштабируется на несколько инстансов демонов (без дублирования сообщений)

## Problem Statement

**Текущая архитектура (проблема в Docker):**

Текущая система использует `asyncio.sleep(delay_seconds)` внутри `SchedulerService`:
```python
# scheduler_service.py, lines 209-221
async def delayed_execute():
    try:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)  # <-- ПРОБЛЕМА: in-memory delay
        await self._execute_action(action.id)
    except asyncio.CancelledError:
        pass
```

**Проблемы:**
1. **Docker restart** - при рестарте контейнера все in-memory asyncio tasks теряются
2. **Точность времени** - если демон рестартовал через 3 минуты из 5, задержка начинается заново
3. **Множественные инстансы** - нет механизма для предотвращения дублирования при scale
4. **Отладка** - сложно понять, какие follow-ups запланированы и когда выполнятся

**Текущий workaround (startup recovery):**
При старте демон пытается восстановить pending actions:
```python
# scheduler_service.py, lines 329-393
async def _recover_pending_actions(self) -> None:
    pending_actions = await get_pending_actions()
    for action in pending_actions:
        if scheduled_for <= now:
            # Overdue - execute immediately
            await self._execute_action(action.id)
        else:
            # Future - reschedule with asyncio.sleep
            await self.schedule_action(action)  # <-- Снова in-memory!
```

Этот workaround работает, но:
- Все еще использует in-memory asyncio tasks
- При коротких интервалах (5-30 минут) и частых рестартах - неточности

## Solution Approach

### New Architecture: Database Polling Daemon

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     TELEGRAM AGENT CONTAINER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     tool_use: schedule_followup    ┌────────────────┐ │
│  │  TelegramAgent  │ ──────────────────────────────────▶│ PostgreSQL DB  │ │
│  │  (Claude LLM)   │                                    │                │ │
│  └─────────────────┘     INSERT INTO scheduled_actions  │ scheduled_     │ │
│                          (prospect_id, scheduled_for,   │ actions table  │ │
│                           status='pending', payload)    └────────────────┘ │
│                                                                  ▲         │
│                                                                  │         │
│  ┌─────────────────────────────────────────────────────────────┐│         │
│  │              FOLLOW-UP POLLING DAEMON (New)                 ││         │
│  │                                                             ││         │
│  │  while True:                                                ││         │
│  │      actions = SELECT * FROM scheduled_actions              ││         │
│  │                WHERE status = 'pending'                     ││         │
│  │                AND scheduled_for <= NOW()                   │◀─────────┘ │
│  │                ORDER BY scheduled_for ASC                   │          │
│  │                FOR UPDATE SKIP LOCKED  # <-- Prevents dupes │          │
│  │                                                             │          │
│  │      for action in actions:                                 │          │
│  │          execute_action(action)                             │          │
│  │          UPDATE status = 'executed'                         │          │
│  │                                                             │          │
│  │      await asyncio.sleep(POLL_INTERVAL)  # e.g., 30 seconds│          │
│  └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Changes

1. **No more in-memory asyncio tasks for delays** - все timing через database polling
2. **`FOR UPDATE SKIP LOCKED`** - PostgreSQL-native locking для предотвращения дублирования
3. **Single polling interval** - проверка базы каждые N секунд (configurable, default 30s)
4. **Stateless daemon** - демон не хранит state в памяти, можно рестартовать в любой момент
5. **Transaction-based execution** - атомарные операции: claim action → execute → mark done

### Database Schema Enhancement

Текущая схема уже подходит, но добавим advisory lock поддержку:
```sql
-- No schema changes needed!
-- scheduled_actions table already has:
-- - id UUID PRIMARY KEY
-- - prospect_id VARCHAR(255)
-- - scheduled_for TIMESTAMPTZ
-- - status VARCHAR(20)
-- - payload JSONB

-- New query pattern uses PostgreSQL row-level locking:
SELECT * FROM scheduled_actions
WHERE status = 'pending' AND scheduled_for <= NOW()
ORDER BY scheduled_for ASC
FOR UPDATE SKIP LOCKED
LIMIT 10;
```

## Relevant Files

### Files to Modify

1. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/scheduling/scheduler_service.py`**
   - Remove asyncio.sleep-based scheduling
   - Convert to database polling loop
   - Add `FOR UPDATE SKIP LOCKED` query support

2. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/scheduling/scheduled_action_manager.py`**
   - Add `claim_due_actions()` function with row locking
   - Add transaction support for atomic claim-execute-complete

3. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/daemon.py`**
   - Simplify scheduler initialization (no more asyncio task management)
   - Update `execute_scheduled_action()` to work with polling model

4. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/crm/models.py`**
   - Add `FollowUpPollingConfig` Pydantic model for configuration

5. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/config/agent_config.json`**
   - Add polling interval configuration

6. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/deployment/docker/docker-compose.yml`**
   - Add environment variables for polling configuration

### New Files to Create

1. **`/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/scheduling/followup_polling_daemon.py`**
   - Standalone polling daemon class
   - Can run as separate process or integrated into main daemon

## Implementation Phases

### Phase 1: Foundation - Database Polling Functions
- Add `claim_due_actions()` with `FOR UPDATE SKIP LOCKED`
- Add transaction wrapper for atomic operations
- Add configuration model for polling settings

### Phase 2: Polling Daemon Implementation
- Create `FollowUpPollingDaemon` class
- Implement main polling loop with configurable interval
- Add graceful shutdown handling

### Phase 3: Integration & Migration
- Update `SchedulerService` to use polling instead of asyncio tasks
- Update daemon.py integration
- Add Docker configuration

### Phase 4: Testing & Validation
- Test Docker restart scenarios
- Test concurrent execution prevention
- Verify timing accuracy

## Step by Step Tasks

### 1. Add Database Claim Function with Row Locking

**File: `src/sales_agent/scheduling/scheduled_action_manager.py`**

Add new function for atomic action claiming:
```python
async def claim_due_actions(
    limit: int = 10,
    max_delay_seconds: int = 60,
) -> list[ScheduledAction]:
    """
    Claim due actions for execution with row-level locking.

    Uses FOR UPDATE SKIP LOCKED to prevent multiple workers
    from claiming the same action. Returns only actions that
    were successfully claimed.

    Args:
        limit: Maximum number of actions to claim per call
        max_delay_seconds: Include actions scheduled up to N seconds in future
                          (allows slight preemptive claiming for accuracy)

    Returns:
        List of claimed ScheduledAction objects
    """
```

- Add `FOR UPDATE SKIP LOCKED` query pattern
- Add transaction with immediate status update to 'processing'
- Add rollback on execution failure

### 2. Add Polling Configuration Model

**File: `src/sales_agent/crm/models.py`**

Add configuration for polling daemon:
```python
class FollowUpPollingConfig(BaseModel):
    """Configuration for follow-up polling daemon."""
    poll_interval_seconds: int = 30  # How often to check for due actions
    batch_size: int = 10  # Max actions to process per poll
    preemptive_window_seconds: int = 5  # Claim actions up to N seconds early
    execution_timeout_seconds: int = 300  # Max time for single action execution
    max_retries: int = 3  # Retry failed actions N times
    retry_delay_seconds: int = 60  # Wait between retries
```

### 3. Create Polling Daemon Class

**File: `src/sales_agent/scheduling/followup_polling_daemon.py`**

Create standalone polling daemon:
```python
class FollowUpPollingDaemon:
    """
    Database-driven follow-up execution daemon.

    Polls the scheduled_actions table at regular intervals
    and executes due actions. Uses PostgreSQL row-level locking
    to prevent duplicate execution across multiple instances.
    """

    def __init__(
        self,
        execute_callback: Callable[[ScheduledAction], Awaitable[None]],
        config: FollowUpPollingConfig = None,
    ):
        ...

    async def start(self) -> None:
        """Start the polling loop."""
        ...

    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        ...

    async def _poll_and_execute(self) -> int:
        """Single poll iteration. Returns number of actions executed."""
        ...
```

- Implement clean polling loop
- Add metrics/stats tracking
- Add error handling with exponential backoff
- Add health check method

### 4. Refactor SchedulerService to Use Polling

**File: `src/sales_agent/scheduling/scheduler_service.py`**

Remove asyncio.sleep-based scheduling, delegate to polling daemon:
```python
class SchedulerService:
    """
    Scheduler service using database polling.

    Instead of managing asyncio tasks, simply writes to database
    and lets the polling daemon handle execution.
    """

    def __init__(self, execute_callback):
        self.polling_daemon = FollowUpPollingDaemon(
            execute_callback=execute_callback,
        )

    async def schedule_action(self, action: ScheduledAction) -> str:
        """
        Schedule an action. Simply ensures it's in the database.
        The polling daemon will execute it when due.
        """
        # Action should already be created in DB by this point
        # Just log and return
        console.print(f"[cyan]Action {action.id} scheduled for {action.scheduled_for}[/cyan]")
        return action.id

    async def start(self) -> None:
        """Start the polling daemon."""
        await self.polling_daemon.start()

    async def stop(self) -> None:
        """Stop the polling daemon."""
        await self.polling_daemon.stop()
```

- Remove `_scheduled_tasks` dictionary
- Remove `asyncio.sleep` based delays
- Remove `_recover_pending_actions` (no longer needed - polling handles this)

### 5. Update Agent Config

**File: `src/sales_agent/config/agent_config.json`**

Add polling configuration:
```json
{
  "followup_polling": {
    "poll_interval_seconds": 30,
    "batch_size": 10,
    "preemptive_window_seconds": 5,
    "max_retries": 3
  }
}
```

### 6. Update daemon.py Integration

**File: `src/sales_agent/daemon.py`**

Simplify scheduler integration:
- Remove asyncio task management code
- Update initialization to pass config
- Ensure `execute_scheduled_action` callback is compatible

### 7. Update Docker Configuration

**File: `deployment/docker/docker-compose.yml`**

Add environment variables:
```yaml
environment:
  - FOLLOWUP_POLL_INTERVAL_SECONDS=30
  - FOLLOWUP_BATCH_SIZE=10
  - FOLLOWUP_MAX_RETRIES=3
```

### 8. Add Action Processing Status

**File: `src/sales_agent/scheduling/scheduled_action_manager.py`**

Add new status and functions:
```python
# Add 'processing' status to handle in-flight actions
class ScheduledActionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"  # New: claimed but not yet executed
    EXECUTED = "executed"
    CANCELLED = "cancelled"

async def mark_processing(action_id: str) -> bool:
    """Mark action as being processed (claimed by worker)."""
    ...

async def reset_stale_processing(stale_after_seconds: int = 600) -> int:
    """Reset actions stuck in 'processing' status back to 'pending'."""
    ...
```

### 9. Add Database Migration for Processing Status

**File: `src/sales_agent/migrations/005_add_processing_status.sql`**

```sql
-- Add processing status support (if not already valid value)
-- No DDL changes needed since status is VARCHAR, just update queries

-- Add started_processing_at column for timeout detection
ALTER TABLE scheduled_actions
ADD COLUMN IF NOT EXISTS started_processing_at TIMESTAMPTZ;

-- Index for polling query performance
CREATE INDEX IF NOT EXISTS idx_scheduled_actions_polling
ON scheduled_actions (scheduled_for, status)
WHERE status IN ('pending', 'processing');
```

### 10. Write Tests

Create test file `src/sales_agent/testing/test_followup_polling.py`:
- Test database claim with row locking
- Test concurrent execution prevention (simulate 2 workers)
- Test Docker restart scenario (stop mid-poll, restart, verify no duplication)
- Test timing accuracy (schedule for +1 minute, verify executes within ±5s)

### 11. Update Documentation

Update comments and docstrings to reflect new architecture:
- Remove references to asyncio.sleep-based scheduling
- Document polling approach and configuration
- Add troubleshooting guide for Docker deployments

## Testing Strategy

### Unit Tests

1. **`test_claim_due_actions`**
   - Test that `FOR UPDATE SKIP LOCKED` prevents double claiming
   - Test batch size limit
   - Test preemptive window

2. **`test_polling_loop`**
   - Test normal poll cycle
   - Test graceful shutdown mid-poll
   - Test error recovery

3. **`test_status_transitions`**
   - pending → processing → executed
   - pending → processing → cancelled (on client response)
   - processing → pending (on timeout/crash recovery)

### Integration Tests

1. **Docker Restart Simulation**
   - Schedule action for +2 minutes
   - Restart container after 1 minute
   - Verify action executes within expected window

2. **Concurrent Worker Test**
   - Start 2 daemon instances
   - Schedule 10 actions for immediate execution
   - Verify each action executed exactly once

3. **Client Response Cancellation**
   - Schedule action for +5 minutes
   - Client responds after 2 minutes
   - Verify action cancelled, never executed

### Manual Validation

1. **Quick Validation (2 minutes)**
   ```bash
   # Schedule action for +1 minute
   # Watch logs for "Polling..." messages every 30s
   # Verify action executes at scheduled time
   ```

2. **Docker Restart Test**
   ```bash
   docker-compose restart telegram-agent
   # Verify pending actions still execute after restart
   ```

## Acceptance Criteria

- [ ] Follow-up actions execute within ±30 seconds of scheduled time
- [ ] Docker container restart does not cause missed follow-ups
- [ ] Docker container restart does not cause duplicate messages
- [ ] Multiple daemon instances don't execute the same action twice
- [ ] Actions can be cancelled even while 'processing'
- [ ] Stale 'processing' actions are automatically recovered
- [ ] Polling interval is configurable via environment variable
- [ ] All existing tests still pass
- [ ] New polling tests pass

## Validation Commands

```bash
# Verify syntax of new files
uv run python -m py_compile src/sales_agent/scheduling/followup_polling_daemon.py
uv run python -m py_compile src/sales_agent/scheduling/scheduled_action_manager.py

# Run database migration
psql $DATABASE_URL -f src/sales_agent/migrations/005_add_processing_status.sql

# Run tests
PYTHONPATH=src uv run pytest src/sales_agent/testing/test_followup_polling.py -v

# Manual test: Schedule quick follow-up
PYTHONPATH=src uv run python -c "
import asyncio
from datetime import datetime, timezone, timedelta
from sales_agent.scheduling.scheduled_action_manager import create_scheduled_action
from sales_agent.crm.models import ScheduledActionType

async def test():
    action = await create_scheduled_action(
        prospect_id='7836623698',  # Test prospect
        action_type=ScheduledActionType.FOLLOW_UP,
        scheduled_for=datetime.now(timezone.utc) + timedelta(minutes=1),
        payload={'follow_up_intent': 'Quick test follow-up'}
    )
    print(f'Created action {action.id} scheduled for {action.scheduled_for}')

asyncio.run(test())
"

# Start daemon and watch for execution
PYTHONPATH=src uv run python src/sales_agent/daemon.py
```

## Notes

### Why Database Polling Over In-Memory Tasks?

| Aspect | In-Memory (current) | Database Polling (new) |
|--------|---------------------|------------------------|
| Restart survival | Lost on restart | Persisted |
| Timing accuracy | Drift if restarted | Always accurate |
| Scalability | Single instance | Multiple instances OK |
| Debugging | Hard to inspect | Query database |
| Complexity | Lower | Slightly higher |

### PostgreSQL `FOR UPDATE SKIP LOCKED`

This PostgreSQL feature is key to the solution:
```sql
SELECT * FROM scheduled_actions
WHERE status = 'pending' AND scheduled_for <= NOW()
FOR UPDATE SKIP LOCKED
LIMIT 10;
```

- `FOR UPDATE` - locks selected rows until transaction ends
- `SKIP LOCKED` - if a row is already locked by another transaction, skip it instead of waiting
- Result: Multiple workers can poll simultaneously without conflicts

### Poll Interval Considerations

- **30 seconds (recommended)**: Good balance of responsiveness and DB load
- **10 seconds**: More responsive but higher DB load
- **60 seconds**: Lower DB load but less precise timing

For critical real-time follow-ups, consider 15-30 seconds.
For batch processing scenarios, 60+ seconds is fine.

### Backward Compatibility

The new system is backward compatible:
1. Existing `scheduled_actions` records work without migration
2. `status = 'pending'` semantics unchanged
3. Existing API (`create_scheduled_action`, `cancel_pending_for_prospect`) unchanged
4. Daemon.py callback interface unchanged

### Docker Health Check

Add health check that verifies polling is working:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from sales_agent.scheduling.followup_polling_daemon import FollowUpPollingDaemon; print('OK')" || exit 1
```

### Monitoring Recommendations

Add logging for observability:
```python
# On each poll:
logger.info(f"Poll cycle: found {len(due_actions)} due actions, executed {executed_count}")

# On execution:
logger.info(f"Executed action {action.id} for prospect {action.prospect_id}, latency={latency_ms}ms")

# On error:
logger.error(f"Failed to execute action {action.id}: {error}")
```

Consider adding Prometheus metrics:
- `followup_actions_executed_total` (counter)
- `followup_poll_cycle_duration_seconds` (histogram)
- `followup_pending_actions_count` (gauge)
