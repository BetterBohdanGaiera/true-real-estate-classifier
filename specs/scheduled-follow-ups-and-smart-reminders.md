# Plan: Scheduled Follow-ups and Smart Reminders System

## Task Description
Implement a production-ready scheduled follow-up and reminder system for the Telegram sales agent. The system should:
1. Parse natural language time expressions ("in 2 hours", "tomorrow", "on Sunday") via LLM + tool calling
2. Persist scheduled actions in a database that survives daemon restarts
3. Proactively execute scheduled follow-ups at the designated time
4. Cancel pending follow-ups if the client messages first
5. Be production-ready with no job loss on deployment/restart

## Objective
Enable the sales agent to understand and remember time-based follow-up requests from conversations, schedule them persistently, and execute them proactively - while intelligently canceling follow-ups when clients respond before the scheduled time.

## Problem Statement
The current Telegram agent has a basic follow-up system (`auto_follow_up_hours: 24`) that:
- Uses a fixed 24-hour interval (not conversational)
- Cannot parse natural language time requests ("text me in 2 hours")
- Has no persistent job storage (jobs lost on daemon restart)
- Uses polling loop instead of proper job scheduling
- Cannot cancel follow-ups when client responds first

This limits the agent's ability to have natural conversations about timing and reduces reliability for production deployment.

## Solution Approach

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM DAEMON (run_daemon.py)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌───────────────────┐    ┌─────────────────────────┐   │
│  │   Telethon  │───▶│  Message Handler  │───▶│   TelegramAgent (LLM)   │   │
│  │   Client    │    │  (incoming msg)   │    │   + schedule_followup   │   │
│  └─────────────┘    └───────────────────┘    │      TOOL CALLING       │   │
│                              │               └─────────────────────────┘   │
│                              │                           │                  │
│                              ▼                           ▼                  │
│                     ┌────────────────┐         ┌───────────────────┐       │
│                     │ Cancel pending │         │ Create scheduled  │       │
│                     │ follow-ups for │         │ action via        │       │
│                     │ this prospect  │         │ ScheduledAction   │       │
│                     └────────────────┘         │ Manager           │       │
│                                                └───────────────────┘       │
│                                                          │                  │
│  ┌──────────────────────────────────────────────────────┼──────────────┐   │
│  │                    APScheduler (AsyncIOScheduler)     │              │   │
│  │                                                       ▼              │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              PostgreSQL Job Store                           │   │   │
│  │  │  ┌───────────────────────────────────────────────────────┐  │   │   │
│  │  │  │  scheduled_actions table                              │  │   │   │
│  │  │  │  - id (UUID)                                          │  │   │   │
│  │  │  │  - prospect_id                                        │  │   │   │
│  │  │  │  - action_type (follow_up, reminder, pre_meeting)     │  │   │   │
│  │  │  │  - scheduled_for (TIMESTAMPTZ)                        │  │   │   │
│  │  │  │  - status (pending, executed, cancelled)              │  │   │   │
│  │  │  │  - payload (JSONB - message template, context)        │  │   │   │
│  │  │  │  - created_at, updated_at                             │  │   │   │
│  │  │  └───────────────────────────────────────────────────────┘  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  Job executes at scheduled_for ──▶ process_scheduled_action()      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

1. **APScheduler 4.x with PostgreSQL JobStore**: Production-ready scheduler with built-in persistence, async-first design, and failure resilience. Survives daemon restarts without job loss.

2. **LLM Tool Calling for Date Parsing**: Claude extracts time expressions via a `schedule_followup` tool that:
   - Parses natural language ("in 2 hours", "tomorrow morning", "on Sunday")
   - Returns structured datetime
   - Handles timezone (Bali UTC+8)
   - No external date parsing library needed (LLM is the parser)

3. **PostgreSQL for Persistence**: Reuses existing `DATABASE_URL` connection (already used by ADW system). Single source of truth for scheduled actions.

4. **Client Response Cancellation**: When a client messages, all their pending follow-ups are automatically cancelled.

5. **Pydantic Models**: All scheduled action data uses typed models for validation and serialization.

## Relevant Files

### Existing Files to Modify

- `.claude/skills/telegram/scripts/run_daemon.py`
  - Add APScheduler initialization and lifecycle management
  - Add scheduled action processing in message handler
  - Cancel pending follow-ups on client response
  - Register scheduler jobs for pending actions on startup

- `.claude/skills/telegram/scripts/telegram_agent.py`
  - Add `schedule_followup` tool definition for Claude
  - Update system prompt with scheduling instructions
  - Parse tool calls from LLM response

- `.claude/skills/telegram/scripts/models.py`
  - Add `ScheduledAction` Pydantic model
  - Add `ScheduledActionStatus` enum
  - Add `ScheduleFollowupTool` input model

- `pyproject.toml`
  - Add `apscheduler>=4.0.0a5` dependency
  - Add `sqlalchemy[asyncio]>=2.0.0` for APScheduler job store

### New Files to Create

- `.claude/skills/telegram/scripts/scheduled_action_manager.py`
  - `ScheduledActionManager` class for CRUD operations
  - PostgreSQL persistence via asyncpg
  - Methods: create, get_pending, cancel_for_prospect, mark_executed

- `.claude/skills/telegram/scripts/scheduler_service.py`
  - APScheduler initialization and configuration
  - Job handlers for each action type
  - Startup recovery (reschedule pending actions from DB)

- `.claude/skills/telegram/config/scheduler_config.json`
  - Scheduler configuration (timezone, retry policy, cleanup settings)

### Database Migration

- `migrations/001_create_scheduled_actions.sql`
  - Create `scheduled_actions` table
  - Create indexes for efficient querying

## Implementation Phases

### Phase 1: Foundation (Database + Models)
1. Create database table for scheduled actions
2. Define Pydantic models for scheduled actions
3. Implement ScheduledActionManager with asyncpg
4. Add unit tests for persistence layer

### Phase 2: Core Implementation (APScheduler + Tool Calling)
1. Add APScheduler dependency and configuration
2. Create scheduler service with PostgreSQL job store
3. Implement `schedule_followup` tool for Claude
4. Update TelegramAgent to handle tool calls
5. Wire scheduler into daemon lifecycle

### Phase 3: Integration & Polish
1. Add client response cancellation logic
2. Implement startup recovery (reschedule pending jobs)
3. Add graceful shutdown handling
4. Create pre-meeting reminder scheduling (auto-schedule on booking)
5. Add logging and monitoring
6. Integration tests with full flow

## Step by Step Tasks

### 1. Add Dependencies to pyproject.toml
- Add `apscheduler>=4.0.0a5` to dependencies
- Add `sqlalchemy[asyncio]>=2.0.0` for APScheduler PostgreSQL support
- Run `uv sync` to install

### 2. Create Database Migration for Scheduled Actions
- Create `migrations/001_create_scheduled_actions.sql` with:
  ```sql
  CREATE TABLE IF NOT EXISTS scheduled_actions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      prospect_id VARCHAR(255) NOT NULL,
      action_type VARCHAR(50) NOT NULL,  -- 'follow_up', 'reminder', 'pre_meeting_reminder'
      scheduled_for TIMESTAMPTZ NOT NULL,
      status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'executed', 'cancelled'
      payload JSONB DEFAULT '{}',  -- message template, context, etc.
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      executed_at TIMESTAMPTZ,
      cancelled_at TIMESTAMPTZ,
      cancel_reason VARCHAR(255)
  );

  CREATE INDEX idx_scheduled_actions_prospect ON scheduled_actions(prospect_id);
  CREATE INDEX idx_scheduled_actions_pending ON scheduled_actions(scheduled_for)
      WHERE status = 'pending';
  CREATE INDEX idx_scheduled_actions_status ON scheduled_actions(status);
  ```
- Document manual migration execution in CLAUDE.md

### 3. Create ScheduledAction Pydantic Models
- Add to `models.py`:
  ```python
  class ScheduledActionStatus(str, Enum):
      PENDING = "pending"
      EXECUTED = "executed"
      CANCELLED = "cancelled"

  class ScheduledActionType(str, Enum):
      FOLLOW_UP = "follow_up"
      REMINDER = "reminder"
      PRE_MEETING_REMINDER = "pre_meeting_reminder"

  class ScheduledAction(BaseModel):
      id: UUID
      prospect_id: str
      action_type: ScheduledActionType
      scheduled_for: datetime
      status: ScheduledActionStatus = ScheduledActionStatus.PENDING
      payload: dict = Field(default_factory=dict)
      created_at: datetime = Field(default_factory=datetime.now)
      updated_at: datetime = Field(default_factory=datetime.now)
      executed_at: Optional[datetime] = None
      cancelled_at: Optional[datetime] = None
      cancel_reason: Optional[str] = None

  class ScheduleFollowupToolInput(BaseModel):
      """Input schema for schedule_followup tool call."""
      follow_up_time: datetime  # When to follow up (UTC)
      message_template: str  # Template for follow-up message
      reason: str  # Why scheduling this follow-up
  ```

### 4. Create ScheduledActionManager Class
- Create new file `.claude/skills/telegram/scripts/scheduled_action_manager.py`
- Implement:
  ```python
  class ScheduledActionManager:
      def __init__(self, database_url: str):
          ...

      async def create_scheduled_action(
          self,
          prospect_id: str,
          action_type: ScheduledActionType,
          scheduled_for: datetime,
          payload: dict
      ) -> ScheduledAction:
          """Create a new scheduled action in the database."""

      async def get_pending_actions(
          self,
          prospect_id: Optional[str] = None
      ) -> list[ScheduledAction]:
          """Get all pending actions, optionally filtered by prospect."""

      async def cancel_pending_for_prospect(
          self,
          prospect_id: str,
          reason: str = "client_responded"
      ) -> int:
          """Cancel all pending actions for a prospect. Returns count cancelled."""

      async def mark_executed(self, action_id: UUID) -> bool:
          """Mark an action as executed."""

      async def get_overdue_actions(self) -> list[ScheduledAction]:
          """Get actions that should have run but haven't (for recovery)."""
  ```

### 5. Create APScheduler Service
- Create new file `.claude/skills/telegram/scripts/scheduler_service.py`
- Implement:
  ```python
  from apscheduler import AsyncScheduler
  from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
  from apscheduler.triggers.date import DateTrigger

  class SchedulerService:
      def __init__(
          self,
          database_url: str,
          action_manager: ScheduledActionManager,
          daemon: "TelegramDaemon"  # Reference for callbacks
      ):
          self.database_url = database_url
          self.action_manager = action_manager
          self.daemon = daemon
          self.scheduler: Optional[AsyncScheduler] = None

      async def start(self):
          """Initialize and start the scheduler."""
          datastore = SQLAlchemyDataStore(self.database_url)
          self.scheduler = AsyncScheduler(data_store=datastore)

          # Recover pending actions from database
          await self._recover_pending_actions()

          await self.scheduler.start_in_background()

      async def stop(self):
          """Gracefully stop the scheduler."""
          if self.scheduler:
              await self.scheduler.stop()

      async def schedule_follow_up(
          self,
          action: ScheduledAction
      ) -> str:
          """Schedule a follow-up action. Returns job ID."""
          job = await self.scheduler.add_schedule(
              self._execute_follow_up,
              trigger=DateTrigger(run_time=action.scheduled_for),
              id=str(action.id),
              args=[action.id]
          )
          return job.id

      async def cancel_job(self, job_id: str):
          """Cancel a scheduled job."""
          await self.scheduler.remove_schedule(job_id)

      async def _execute_follow_up(self, action_id: UUID):
          """Execute a scheduled follow-up."""
          action = await self.action_manager.get_by_id(action_id)
          if not action or action.status != ScheduledActionStatus.PENDING:
              return  # Already cancelled or executed

          # Execute the follow-up via daemon
          await self.daemon.execute_scheduled_action(action)

          # Mark as executed
          await self.action_manager.mark_executed(action_id)

      async def _recover_pending_actions(self):
          """On startup, reschedule any pending actions from DB."""
          pending = await self.action_manager.get_pending_actions()
          for action in pending:
              if action.scheduled_for > datetime.now(timezone.utc):
                  await self.schedule_follow_up(action)
              else:
                  # Overdue - execute immediately
                  await self._execute_follow_up(action.id)
  ```

### 6. Add schedule_followup Tool to TelegramAgent
- Update `telegram_agent.py` to include tool definition in Claude API call:
  ```python
  SCHEDULE_FOLLOWUP_TOOL = {
      "name": "schedule_followup",
      "description": """Schedule a follow-up message to the client at a specific time.
      Use this when the client says things like:
      - "напиши мне через 2 часа" (text me in 2 hours)
      - "свяжись завтра" (contact me tomorrow)
      - "в воскресенье" (on Sunday)
      - "через неделю" (in a week)

      Parse the natural language time expression and convert to a specific datetime.
      Consider the current time and Bali timezone (UTC+8).
      """,
      "input_schema": {
          "type": "object",
          "properties": {
              "follow_up_time": {
                  "type": "string",
                  "format": "date-time",
                  "description": "ISO 8601 datetime when to follow up (UTC)"
              },
              "message_template": {
                  "type": "string",
                  "description": "Template for the follow-up message to send"
              },
              "reason": {
                  "type": "string",
                  "description": "Brief explanation of why this follow-up is scheduled"
              }
          },
          "required": ["follow_up_time", "message_template", "reason"]
      }
  }
  ```
- Update `generate_response()` to pass tools parameter to Claude API
- Handle tool_use blocks in response

### 7. Update System Prompt with Scheduling Instructions
- Add to system prompt in `telegram_agent.py`:
  ```
  ## Планирование follow-up
  Когда клиент просит связаться позже:
  - "напиши через 2 часа" → используй schedule_followup tool
  - "завтра утром" → schedule_followup на 10:00 следующего дня
  - "в воскресенье" → schedule_followup на ближайшее воскресенье 10:00

  Текущее время (UTC+8 Бали): {current_time}

  При планировании follow-up:
  1. Подтверди клиенту: "Отлично, напишу вам {когда}!"
  2. Используй schedule_followup tool с точным временем
  3. Сообщение follow-up должно быть полезным (micro-insight)
  ```

### 8. Integrate Scheduler into Daemon Lifecycle
- Update `run_daemon.py`:
  - Add scheduler_service initialization in `initialize()`
  - Add scheduler start in `run()`
  - Add scheduler stop in `shutdown()`
  - Remove old polling-based follow-up loop (or make it backup)

### 9. Add Client Response Cancellation Logic
- In message handler (`handle_incoming`), after recording response:
  ```python
  # Cancel any pending follow-ups for this prospect
  cancelled_count = await self.action_manager.cancel_pending_for_prospect(
      prospect_id=str(prospect.telegram_id),
      reason="client_responded"
  )
  if cancelled_count > 0:
      console.print(f"[dim]Cancelled {cancelled_count} pending follow-ups for {prospect.name}[/dim]")
      # Also cancel APScheduler jobs
      for action in cancelled_actions:
          await self.scheduler_service.cancel_job(str(action.id))
  ```

### 10. Implement Pre-Meeting Reminder Auto-Scheduling
- After successful meeting booking, automatically schedule:
  - 24-hour reminder
  - 1-hour reminder (optional)
  ```python
  # In handle_incoming, after successful schedule action:
  if result.success and result.slot:
      meeting_time = datetime.combine(result.slot.date, result.slot.start_time)
      meeting_time = meeting_time.replace(tzinfo=ZoneInfo("Asia/Makassar"))  # UTC+8

      # Schedule 24h reminder
      reminder_24h = meeting_time - timedelta(hours=24)
      await self.action_manager.create_scheduled_action(
          prospect_id=str(prospect.telegram_id),
          action_type=ScheduledActionType.PRE_MEETING_REMINDER,
          scheduled_for=reminder_24h,
          payload={
              "slot_id": slot_id,
              "reminder_type": "24h",
              "meeting_time": meeting_time.isoformat()
          }
      )
  ```

### 11. Add execute_scheduled_action Method to Daemon
- Add method to `TelegramDaemon`:
  ```python
  async def execute_scheduled_action(self, action: ScheduledAction):
      """Execute a scheduled action (called by scheduler)."""
      prospect = self.prospect_manager.get_prospect(action.prospect_id)
      if not prospect:
          console.print(f"[yellow]Prospect {action.prospect_id} not found, skipping action[/yellow]")
          return

      if action.action_type == ScheduledActionType.FOLLOW_UP:
          await self._execute_follow_up(prospect, action)
      elif action.action_type == ScheduledActionType.PRE_MEETING_REMINDER:
          await self._execute_pre_meeting_reminder(prospect, action)

  async def _execute_follow_up(self, prospect: Prospect, action: ScheduledAction):
      """Execute a scheduled follow-up."""
      message = action.payload.get("message_template", "")
      if not message:
          # Generate follow-up message via agent
          context = self.prospect_manager.get_conversation_context(prospect.telegram_id)
          response = await self.agent.generate_follow_up(prospect, context)
          message = response.message

      if message:
          result = await self.service.send_message(prospect.telegram_id, message)
          if result.get("sent"):
              self.stats["messages_sent"] += 1
              self.prospect_manager.record_agent_message(
                  prospect.telegram_id,
                  result["message_id"],
                  message
              )
              console.print(f"[green]→ Scheduled follow-up sent to {prospect.name}[/green]")

  async def _execute_pre_meeting_reminder(self, prospect: Prospect, action: ScheduledAction):
      """Send pre-meeting reminder."""
      meeting_time = action.payload.get("meeting_time")
      reminder_type = action.payload.get("reminder_type", "24h")

      if reminder_type == "24h":
          message = f"Напоминаем: завтра у нас запланирована встреча в Zoom. Ссылку пришлём за час до встречи!"
      else:
          message = f"Встреча через час! Подготовьте вопросы, будем рады обсудить все детали."

      await self.service.send_message(prospect.telegram_id, message)
  ```

### 12. Add Graceful Shutdown and Recovery
- Ensure scheduler gracefully shuts down on SIGTERM/SIGINT
- Add startup recovery for overdue actions
- Add health check for scheduler status

### 13. Create Configuration File
- Create `.claude/skills/telegram/config/scheduler_config.json`:
  ```json
  {
      "timezone": "Asia/Makassar",
      "retry_policy": {
          "max_retries": 3,
          "retry_delay_seconds": 60
      },
      "cleanup": {
          "keep_executed_days": 30,
          "keep_cancelled_days": 7
      },
      "reminders": {
          "pre_meeting_24h": true,
          "pre_meeting_1h": false
      }
  }
  ```

### 14. Add Logging and Monitoring
- Add structured logging for scheduled action lifecycle
- Log: created, executed, cancelled, failed
- Add stats to daemon status table
- Consider adding webhook for escalation on repeated failures

### 15. Write Tests
- Unit tests for ScheduledActionManager CRUD operations
- Unit tests for date parsing in agent tool calls
- Integration test: schedule → execute flow
- Integration test: schedule → client responds → cancel flow
- Test startup recovery with pending actions

### 16. Update Documentation
- Document scheduler configuration options
- Add deployment notes for DATABASE_URL requirement
- Document migration steps

## Testing Strategy

### Unit Tests
1. **ScheduledActionManager**: Test CRUD operations with test database
2. **SchedulerService**: Test job scheduling, cancellation, recovery
3. **Tool Parsing**: Test various natural language time expressions:
   - "через 2 часа" → +2 hours from now
   - "завтра" → tomorrow 10:00
   - "в воскресенье" → next Sunday 10:00
   - "на следующей неделе" → Monday next week

### Integration Tests
1. **Full Flow Test**: Message with time request → tool call → scheduled action created → job executes → message sent
2. **Cancellation Test**: Schedule follow-up → client responds → action cancelled → no message sent
3. **Recovery Test**: Create pending action → restart daemon → action still executes at scheduled time
4. **Pre-Meeting Reminder Test**: Book meeting → reminders auto-scheduled → reminders sent at correct times

### Edge Cases
- Client provides ambiguous time ("вечером") - should ask for clarification or use default
- Client provides past time - should handle gracefully
- Multiple pending follow-ups for same prospect - all should cancel on response
- Daemon crashes mid-execution - job should retry on restart
- Timezone handling across DST changes (Bali doesn't have DST, but good to test)

## Acceptance Criteria
- [ ] Agent correctly parses natural language time expressions via tool calling
- [ ] Scheduled actions persist in PostgreSQL and survive daemon restart
- [ ] Scheduled follow-ups execute at the designated time (±1 minute)
- [ ] All pending follow-ups for a prospect are cancelled when client responds
- [ ] Pre-meeting reminders are automatically scheduled when meetings are booked
- [ ] Graceful shutdown preserves all pending jobs
- [ ] Startup recovery processes overdue actions
- [ ] All tests pass
- [ ] No data loss on deployment/restart

## Validation Commands
Execute these commands to validate the task is complete:

- `uv run python -c "from apscheduler import AsyncScheduler; print('APScheduler installed')"` - Verify APScheduler is installed
- `uv run python -m py_compile .claude/skills/telegram/scripts/scheduled_action_manager.py` - Verify syntax
- `uv run python -m py_compile .claude/skills/telegram/scripts/scheduler_service.py` - Verify syntax
- `uv run pytest tests/test_scheduled_actions.py -v` - Run scheduled action tests
- `uv run python .claude/skills/telegram/scripts/run_daemon.py --dry-run` - Test daemon initialization

## Notes

### Dependencies to Add
```toml
# In pyproject.toml
dependencies = [
    # ... existing ...
    "apscheduler>=4.0.0a5",  # Async scheduler with PostgreSQL support
    "sqlalchemy[asyncio]>=2.0.0",  # For APScheduler job store
]
```

### Database Requirements
- PostgreSQL database (reuse existing DATABASE_URL from ADW system)
- Run migration manually: `psql $DATABASE_URL -f migrations/001_create_scheduled_actions.sql`
- No Alembic needed (manual migrations consistent with existing pattern)

### Production Considerations
1. **Persistence**: APScheduler 4.x with PostgreSQL job store survives restarts
2. **Scalability**: Single scheduler instance per deployment (use leader election for multi-node)
3. **Monitoring**: Add Prometheus metrics or log aggregation for job execution tracking
4. **Failure Handling**: APScheduler handles retries; add alerting for repeated failures
5. **Timezone**: All times stored in UTC, converted to Bali time (UTC+8) for display

### Alternative Approaches Considered
1. **Celery + Redis**: More complex setup, overkill for current scale
2. **RQ (Redis Queue)**: Requires Redis infrastructure
3. **Custom polling loop**: Not production-ready, jobs lost on restart
4. **External scheduler (cron)**: Harder to manage dynamic schedules
5. **Dagster**: Too heavy for this use case, designed for data pipelines

APScheduler 4.x was chosen because:
- Async-first design matches existing codebase
- PostgreSQL job store reuses existing database
- No additional infrastructure (Redis, RabbitMQ) needed
- Mature library with active maintenance
- Supports dynamic schedule creation at runtime

### Sources
- [APScheduler Documentation](https://apscheduler.readthedocs.io/en/master/)
- [APScheduler 4.0 Migration Guide](https://apscheduler.readthedocs.io/en/master/migration.html)
- [Python Job Scheduling Overview](https://research.aimultiple.com/python-job-scheduling/)
- [Scheduling Tasks: APScheduler vs Celery Beat](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat)
- [PgQueuer - PostgreSQL Job Queue](https://github.com/janbjorge/pgqueuer)
- [Procrastinate - PostgreSQL Task Queue](https://procrastinate.readthedocs.io/)
