# Plan: Smart Follow-ups and Delayed Action System

## Task Description
Implement intelligent follow-up scheduling for the Telegram sales agent where:
1. Client says "напиши через неделю" → bot remembers and messages at the right time
2. If client messages first OR human operator connects → bot does NOT send the follow-up
3. Any action can be "remembered for later" and auto-triggered at the scheduled time

## Objective
Enable the Telegram agent to understand natural language time expressions, persist scheduled actions, execute them automatically, and intelligently cancel them when the client responds first or a human takes over the conversation.

## Problem Statement
The current Telegrazm agent has limitations:
- Fixed 24-hour follow-up interval (not conversational)
- Cannot parse "напиши через 2 часа", "свяжись в воскресенье"
- No persistent job storage (lost on daemon restart)
- Uses 5-minute polling loop instead of proper scheduling
- No detection of human operator takeover
- Cannot cancel follow-ups when client responds first

## Solution Approach

### Scheduler Technology Selection

Based on research, here are the viable options:

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **APScheduler 4.x** | Async-first, PostgreSQL persistence, no extra infra | Alpha version (4.0.0a5) | **RECOMMENDED** |
| **Celery + Redis** | Battle-tested, distributed | Requires Redis, overkill for scale | Not recommended |
| **RQ (Redis Queue)** | Simple, lightweight | Requires Redis | Not recommended |
| **Temporal** | Enterprise-grade workflows | Heavy, complex setup | Not recommended |
| **Windmill** | Visual workflows, self-hosted | External service, overkill | Not recommended |
| **Procrastinate** | PostgreSQL-native, async | Less mature than APScheduler | Alternative |
| **PgQueuer** | PostgreSQL-native, lightweight | Very new library | Alternative |

**Decision: APScheduler 4.x with PostgreSQL JobStore**
- Reuses existing DATABASE_URL (no new infrastructure)
- Async-first design matches codebase patterns
- Survives daemon restarts with PostgreSQL persistence
- Mature library with active development

### Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM DAEMON                                     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐                    ┌──────────────────────────────┐  │
│  │  Telethon       │  incoming message  │  TelegramAgent (Claude LLM)  │  │
│  │  Client         │───────────────────▶│  + schedule_followup TOOL    │  │
│  └─────────────────┘                    └──────────────────────────────┘  │
│          │                                          │                      │
│          │                                          │ tool_use response    │
│          ▼                                          ▼                      │
│  ┌─────────────────────────┐           ┌───────────────────────────────┐  │
│  │  ON CLIENT RESPONSE:    │           │  ScheduledActionManager       │  │
│  │  1. Cancel ALL pending  │           │  - create_scheduled_action()  │  │
│  │     follow-ups          │           │  - cancel_pending_for_prospect│  │
│  │  2. Check human_active  │           │  - mark_executed()            │  │
│  │     flag                │           └───────────────────────────────┘  │
│  └─────────────────────────┘                        │                      │
│                                                     ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    APScheduler (AsyncScheduler)                      │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  PostgreSQL DataStore (reuses DATABASE_URL)                   │  │  │
│  │  │                                                               │  │  │
│  │  │  scheduled_actions table:                                     │  │  │
│  │  │  - id, prospect_id, action_type, scheduled_for               │  │  │
│  │  │  - status (pending/executed/cancelled)                       │  │  │
│  │  │  - payload (JSONB: message_template, context, metadata)      │  │  │
│  │  │  - human_override_check (boolean)                            │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  At scheduled_for time:                                              │  │
│  │  1. Check if status == 'pending'                                    │  │
│  │  2. Check if human_active for prospect                              │  │
│  │  3. If OK → execute action → send message                           │  │
│  │  4. Mark as executed                                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **LLM Tool Calling for Time Parsing**: Claude parses "через неделю", "завтра утром" via `schedule_followup` tool - no external date library needed

2. **Human Override Detection**: New `human_active` flag on Prospect model - when human takes over, all bot actions pause

3. **Cancel on Client Response**: When client sends ANY message, cancel all pending follow-ups for that prospect

4. **Persistent Actions**: PostgreSQL table survives daemon restarts, APScheduler recovers pending jobs on startup

5. **Pre-execution Validation**: Before sending, re-check: Is prospect still active? Did human take over? Is action still pending?

## Relevant Files

### Existing Files to Modify

- `.claude/skills/telegram/scripts/models.py`
  - Add `ScheduledAction`, `ScheduledActionStatus`, `ScheduledActionType` models
  - Add `human_active` field to `Prospect` model
  - Add `schedule_followup` action type to `AgentAction`

- `.claude/skills/telegram/scripts/telegram_agent.py`
  - Add `SCHEDULE_FOLLOWUP_TOOL` definition for Claude API
  - Add `tools` parameter to `messages.create()` calls
  - Update system prompt with scheduling instructions and current time
  - Handle `tool_use` blocks in response parsing

- `.claude/skills/telegram/scripts/run_daemon.py`
  - Initialize `SchedulerService` and `ScheduledActionManager`
  - Add scheduler lifecycle (start/stop)
  - Add cancellation logic in `handle_incoming()`
  - Add `execute_scheduled_action()` method
  - Add human takeover detection

- `.claude/skills/telegram/scripts/prospect_manager.py`
  - Add `set_human_active()` / `clear_human_active()` methods
  - Add `is_human_active()` check
  - Update `should_follow_up()` to respect human_active flag

- `pyproject.toml`
  - Add `apscheduler>=4.0.0a5`
  - Add `sqlalchemy[asyncio]>=2.0.0`

### New Files to Create

- `.claude/skills/telegram/scripts/scheduled_action_manager.py`
  - PostgreSQL CRUD for scheduled_actions table
  - Uses asyncpg (consistent with existing ADW patterns)

- `.claude/skills/telegram/scripts/scheduler_service.py`
  - APScheduler wrapper with PostgreSQL DataStore
  - Job handlers for each action type
  - Startup recovery for pending actions

- `.claude/skills/telegram/migrations/001_scheduled_actions.sql`
  - Database migration for scheduled_actions table

## Implementation Phases

### Phase 1: Foundation (Database + Models)
- Create database migration
- Add Pydantic models for scheduled actions
- Add `human_active` flag to Prospect
- Implement ScheduledActionManager

### Phase 2: Scheduler Integration
- Add APScheduler dependencies
- Create SchedulerService
- Wire into daemon lifecycle
- Implement startup recovery

### Phase 3: Tool Calling + Agent Integration
- Add `schedule_followup` tool to Claude API calls
- Update system prompt with time/timezone context
- Parse tool_use responses
- Connect tool calls to scheduler

### Phase 4: Smart Cancellation
- Cancel on client response
- Cancel on human takeover
- Pre-execution validation checks

## Step by Step Tasks

### 1. Add Dependencies
- Add to `pyproject.toml`:
  ```toml
  "apscheduler>=4.0.0a5",
  "sqlalchemy[asyncio]>=2.0.0",
  ```
- Run `uv sync`

### 2. Create Database Migration
- Create `.claude/skills/telegram/migrations/001_scheduled_actions.sql`:
  ```sql
  CREATE TABLE IF NOT EXISTS scheduled_actions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      prospect_id VARCHAR(255) NOT NULL,
      action_type VARCHAR(50) NOT NULL,
      scheduled_for TIMESTAMPTZ NOT NULL,
      status VARCHAR(20) DEFAULT 'pending',
      payload JSONB DEFAULT '{}',
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      executed_at TIMESTAMPTZ,
      cancelled_at TIMESTAMPTZ,
      cancel_reason VARCHAR(255)
  );

  CREATE INDEX idx_scheduled_actions_prospect ON scheduled_actions(prospect_id);
  CREATE INDEX idx_scheduled_actions_pending ON scheduled_actions(scheduled_for)
      WHERE status = 'pending';
  ```
- Run migration: `psql $DATABASE_URL -f migrations/001_scheduled_actions.sql`

### 3. Add Pydantic Models to models.py
- Add enums: `ScheduledActionStatus`, `ScheduledActionType`
- Add `ScheduledAction` model
- Add `ScheduleFollowupToolInput` model for tool schema
- Add `human_active: bool = False` to `Prospect` model
- Add `"schedule_followup"` to `AgentAction.action` Literal type

### 4. Create ScheduledActionManager
- Create `.claude/skills/telegram/scripts/scheduled_action_manager.py`
- Methods:
  - `create_scheduled_action(prospect_id, action_type, scheduled_for, payload)`
  - `get_pending_actions(prospect_id=None)`
  - `cancel_pending_for_prospect(prospect_id, reason)`
  - `mark_executed(action_id)`
  - `get_by_id(action_id)`
- Use asyncpg connection pool pattern from `adws/adw_modules/adw_database.py`

### 5. Create SchedulerService
- Create `.claude/skills/telegram/scripts/scheduler_service.py`
- Initialize APScheduler with SQLAlchemy DataStore
- Methods:
  - `start()` - init scheduler, recover pending actions
  - `stop()` - graceful shutdown
  - `schedule_action(action: ScheduledAction)` - add job
  - `cancel_action(action_id)` - remove job
  - `_execute_action(action_id)` - job handler
  - `_recover_pending_actions()` - startup recovery

### 6. Add schedule_followup Tool to TelegramAgent
- Define tool schema:
  ```python
  SCHEDULE_FOLLOWUP_TOOL = {
      "name": "schedule_followup",
      "description": """Schedule a follow-up message for later.
      Use when client says: "напиши через 2 часа", "свяжись завтра",
      "в воскресенье", "через неделю".
      Parse the time expression and convert to UTC datetime.
      Current time (Bali UTC+8): {current_time}""",
      "input_schema": {
          "type": "object",
          "properties": {
              "follow_up_time": {"type": "string", "format": "date-time"},
              "message_template": {"type": "string"},
              "reason": {"type": "string"}
          },
          "required": ["follow_up_time", "message_template", "reason"]
      }
  }
  ```
- Add `tools=[SCHEDULE_FOLLOWUP_TOOL]` to Claude API calls
- Inject current Bali time into system prompt

### 7. Handle Tool Use Responses
- Update `_parse_response()` in telegram_agent.py:
  ```python
  for block in response.content:
      if block.type == "tool_use" and block.name == "schedule_followup":
          return AgentAction(
              action="schedule_followup",
              message=block.input.get("message_template"),
              reason=block.input.get("reason"),
              scheduling_data=block.input
          )
  ```

### 8. Integrate Scheduler into Daemon
- In `TelegramDaemon.__init__()`:
  - Add `self.scheduler_service = None`
  - Add `self.action_manager = None`
- In `initialize()`:
  - Create ScheduledActionManager
  - Create SchedulerService
- In `run()`:
  - Call `await self.scheduler_service.start()`
- In `shutdown()`:
  - Call `await self.scheduler_service.stop()`

### 9. Add Client Response Cancellation
- In `handle_incoming()` after recording response:
  ```python
  # Cancel pending follow-ups when client responds
  cancelled = await self.action_manager.cancel_pending_for_prospect(
      str(prospect.telegram_id),
      reason="client_responded"
  )
  if cancelled > 0:
      console.print(f"[dim]Cancelled {cancelled} pending follow-ups[/dim]")
  ```

### 10. Add Human Takeover Detection
- Add method `mark_human_active(telegram_id)` to prospect_manager
- Add method `clear_human_active(telegram_id)` to prospect_manager
- Add CLI command or admin API to toggle human takeover
- Before executing scheduled action, check `is_human_active()`

### 11. Handle schedule_followup Action in Daemon
- In `handle_incoming()`, after agent returns action:
  ```python
  if action.action == "schedule_followup" and action.scheduling_data:
      scheduled_action = await self.action_manager.create_scheduled_action(
          prospect_id=str(prospect.telegram_id),
          action_type=ScheduledActionType.FOLLOW_UP,
          scheduled_for=datetime.fromisoformat(action.scheduling_data["follow_up_time"]),
          payload={
              "message_template": action.scheduling_data.get("message_template"),
              "reason": action.scheduling_data.get("reason"),
              "conversation_context": context
          }
      )
      await self.scheduler_service.schedule_action(scheduled_action)
      console.print(f"[cyan]Scheduled follow-up for {prospect.name} at {scheduled_action.scheduled_for}[/cyan]")
  ```

### 12. Implement execute_scheduled_action
- Add to TelegramDaemon:
  ```python
  async def execute_scheduled_action(self, action: ScheduledAction):
      prospect = self.prospect_manager.get_prospect(action.prospect_id)
      if not prospect:
          return  # Prospect deleted

      # Pre-execution checks
      if self.prospect_manager.is_human_active(prospect.telegram_id):
          await self.action_manager.cancel_pending_for_prospect(
              action.prospect_id, "human_active"
          )
          return

      # Generate or use template message
      message = action.payload.get("message_template")
      if not message:
          context = self.prospect_manager.get_conversation_context(prospect.telegram_id)
          response = await self.agent.generate_follow_up(prospect, context)
          message = response.message

      # Send message
      result = await self.service.send_message(prospect.telegram_id, message)
      if result.get("sent"):
          self.prospect_manager.record_agent_message(
              prospect.telegram_id, result["message_id"], message
          )
          console.print(f"[green]→ Scheduled follow-up sent to {prospect.name}[/green]")
  ```

### 13. Update System Prompt
- Add to system prompt in telegram_agent.py:
  ```
  ## Планирование follow-up

  Текущее время (Бали, UTC+8): {current_bali_time}

  Когда клиент просит связаться позже, используй tool schedule_followup:
  - "напиши через 2 часа" → schedule_followup с временем +2 часа
  - "завтра" → schedule_followup на завтра 10:00
  - "в воскресенье" → ближайшее воскресенье 10:00
  - "через неделю" → +7 дней, 10:00

  Всегда:
  1. Подтверди клиенту время: "Хорошо, напишу вам [когда]!"
  2. Вызови schedule_followup с точным временем (UTC)
  3. В message_template укажи полезный контент для follow-up
  ```

### 14. Add Pre-Meeting Reminder Auto-Scheduling (Optional)
- After successful Zoom booking, auto-schedule:
  - 24-hour reminder
  - 1-hour reminder (optional)

### 15. Write Tests
- Test ScheduledActionManager CRUD
- Test time parsing via Claude tool
- Test cancellation on client response
- Test human takeover blocking
- Test startup recovery

### 16. Update Configuration
- Add scheduler settings to agent_config.json:
  ```json
  {
      "scheduler_timezone": "Asia/Makassar",
      "default_followup_hour": 10,
      "pre_meeting_reminder_hours": [24, 1]
  }
  ```

## Testing Strategy

### Unit Tests
- ScheduledActionManager: CRUD with test database
- Time parsing: Various Russian expressions via mock Claude responses
- Cancellation logic: Proper status updates

### Integration Tests
1. **Full Flow**: Message → tool call → action created → job executes → message sent
2. **Cancel on Response**: Schedule → client responds → action cancelled
3. **Human Takeover**: Schedule → human active → action blocked
4. **Recovery**: Create pending → restart daemon → action executes

### Test Scenarios
```python
# Test 1: "напиши через 2 часа"
# Expected: Schedule follow-up 2 hours from now

# Test 2: "свяжись завтра утром"
# Expected: Schedule for tomorrow 10:00 Bali time

# Test 3: Schedule follow-up, then client messages
# Expected: Follow-up cancelled, no message sent

# Test 4: Human marks conversation as active
# Expected: All pending follow-ups blocked
```

## Acceptance Criteria
- [ ] Agent parses Russian time expressions via tool calling
- [ ] Scheduled actions persist in PostgreSQL
- [ ] Follow-ups execute at scheduled time (±1 min)
- [ ] Client response cancels ALL pending follow-ups
- [ ] Human takeover blocks scheduled actions
- [ ] Daemon restart recovers pending actions
- [ ] No duplicate messages sent
- [ ] Graceful shutdown preserves jobs

## Validation Commands
```bash
# Verify dependencies installed
uv run python -c "from apscheduler import AsyncScheduler; print('OK')"

# Verify syntax
uv run python -m py_compile .claude/skills/telegram/scripts/scheduled_action_manager.py
uv run python -m py_compile .claude/skills/telegram/scripts/scheduler_service.py

# Run tests
uv run pytest tests/test_scheduled_actions.py -v

# Test daemon initialization
uv run python .claude/skills/telegram/scripts/run_daemon.py --help
```

## Notes

### Dependencies
```toml
# pyproject.toml additions
"apscheduler>=4.0.0a5",
"sqlalchemy[asyncio]>=2.0.0",
```

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection (already exists for ADW)
- No new environment variables needed

### Timezone Handling
- Store all times in UTC in database
- Bali timezone: `Asia/Makassar` (UTC+8, no DST)
- Inject current Bali time into system prompt for LLM parsing

### Human Takeover UX
Options for marking human takeover:
1. Telegram command: `/human_active @username`
2. Admin panel toggle
3. Auto-detect: If message sent from different Telegram session
4. Keyword in message: "HUMAN:" prefix

### Alternatives Researched
- **Windmill** (github.com/windmill-labs/windmill): Visual workflow engine, good for complex pipelines but overkill for simple scheduling
- **Temporal**: Enterprise workflow orchestration, too heavy
- **Celery**: Requires Redis/RabbitMQ infrastructure
- **RQ**: Requires Redis
- **Procrastinate**: PostgreSQL-native alternative to APScheduler, newer
- **PgQueuer**: Very lightweight PostgreSQL queue, experimental

APScheduler chosen for: PostgreSQL reuse, async support, maturity, no extra infrastructure.

### Sources
- [APScheduler Documentation](https://apscheduler.readthedocs.io/en/master/)
- [Python Job Scheduling Overview](https://research.aimultiple.com/python-job-scheduling/)
- [APScheduler vs Celery Beat](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat)
- [Windmill Labs](https://github.com/windmill-labs/windmill)
- [Procrastinate](https://procrastinate.readthedocs.io/)
- [Task Queues - Full Stack Python](https://www.fullstackpython.com/task-queues.html)
