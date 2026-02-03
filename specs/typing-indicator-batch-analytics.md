# Plan: Typing Indicator & Batch Analytics

## Task Description

Implement two enhancements to the message batching system:

1. **Typing Indicator During Buffer Wait**: Show Telegram typing indicator ("typing...") while the message buffer is active, giving prospects visual feedback that the agent is "reading" their messages before responding.

2. **Batch Analytics**: Track detailed metrics about message batching to enable optimization of timeout configuration and provide visibility into system behavior.

## Objective

When this plan is complete:
- Prospects see a continuous typing indicator from the moment they send a message until the agent responds
- All batch processing metrics are persisted to the database for analysis
- Operators can view real-time batch statistics in the daemon console
- Historical data enables data-driven tuning of batch timeout values

## Problem Statement

**Typing Indicator Issue:**
Currently, typing simulation only occurs right before sending a message (in `TelegramService._simulate_typing()`). During the 3-8 second buffer wait time while accumulating messages, the prospect sees no activity from the agent. This creates an awkward silent period that doesn't match human behavior.

**Analytics Issue:**
Batch processing statistics (`messages_batched`, `batches_processed`) are tracked in-memory but:
- Lost on daemon restart
- No granular data (batch sizes, wait times, flush reasons)
- Cannot analyze patterns to optimize timeout configuration
- No visibility into force-flush frequency due to limits

## Solution Approach

### Typing Indicator Architecture

Implement a **BackgroundTypingManager** that:
1. Starts continuous typing when first message is buffered
2. Refreshes typing action every 4 seconds (Telegram expires at ~5s)
3. Stops typing when buffer flushes and response is about to be sent
4. Uses asyncio.create_task() pattern from MessageBuffer

```
[First Message Arrives]
    → Start typing indicator task
    → Buffer message, start debounce timer

[More Messages Arrive]
    → Continue typing (task already running)
    → Reset debounce timer

[Timer Expires / Limits Hit]
    → Stop typing indicator task
    → Flush buffer → Process → Send response
```

### Analytics Architecture

Implement a **BatchAnalyticsManager** that:
1. Records every batch event to database with detailed metrics
2. Tracks flush reasons (timeout, max_messages, max_wait, shutdown)
3. Computes and displays aggregate statistics
4. Enables historical trend analysis

## Relevant Files

### Core Files to Modify

- **`src/sales_agent/messaging/message_buffer.py`** (lines 48-417)
  - Add callback hooks for buffer lifecycle events
  - Track flush reason for analytics
  - Emit timing metrics on flush

- **`src/sales_agent/daemon.py`** (lines 233-312, 656-668, 1146-1249)
  - Initialize typing manager with buffer callbacks
  - Add analytics recording in `_process_message_batch()`
  - Update status table with analytics metrics

- **`src/sales_agent/telegram/telegram_service.py`** (lines 114-133)
  - Extract typing logic for reuse by BackgroundTypingManager
  - Add method for continuous typing with refresh

- **`src/sales_agent/crm/models.py`** (lines 141-164)
  - Add analytics configuration fields
  - Add typing indicator configuration

### New Files to Create

- **`src/sales_agent/telegram/typing_manager.py`** (NEW)
  - BackgroundTypingManager class
  - Per-prospect typing task management
  - Auto-refresh every 4 seconds

- **`src/sales_agent/analytics/__init__.py`** (NEW)
  - Package initialization

- **`src/sales_agent/analytics/models.py`** (NEW)
  - BatchEvent Pydantic model
  - FlushReason enum
  - Analytics aggregation models

- **`src/sales_agent/analytics/batch_analytics_manager.py`** (NEW)
  - Database persistence for batch events
  - Aggregate statistics computation
  - Query methods for analysis

- **`src/sales_agent/migrations/006_batch_analytics.sql`** (NEW)
  - batch_events table schema
  - Indexes for time-range queries

### Reference Files

- **`src/sales_agent/scheduling/scheduled_action_manager.py`** (lines 46-87)
  - Connection pooling pattern to follow for analytics manager

- **`src/sales_agent/scheduling/followup_polling_daemon.py`** (lines 107-217)
  - asyncio.create_task() pattern for background typing

## Implementation Phases

### Phase 1: Foundation - Typing Manager & Buffer Hooks

Create the BackgroundTypingManager and add lifecycle callbacks to MessageBuffer:
- Typing manager with auto-refresh loop
- Buffer callbacks: on_buffer_active, on_flush
- Integration in daemon initialization

### Phase 2: Core Implementation - Analytics Infrastructure

Build the analytics data layer:
- Database migration for batch_events table
- Pydantic models for batch analytics
- BatchAnalyticsManager with async database operations
- Integration in daemon._process_message_batch()

### Phase 3: Integration & Polish

Connect all components and add visibility:
- Enhanced status table with analytics metrics
- Shutdown summary with batch statistics
- Configuration options for analytics
- Error handling and graceful degradation

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### 1. Create BackgroundTypingManager Class

- Create new file `src/sales_agent/telegram/typing_manager.py`
- Implement BackgroundTypingManager class:
  ```python
  class BackgroundTypingManager:
      """Manages continuous typing indicators during message processing."""

      def __init__(self, client: TelegramClient, config: AgentConfig):
          self._client = client
          self._config = config
          self._typing_tasks: dict[str, asyncio.Task] = {}
          self._refresh_interval = 4.0  # seconds (Telegram expires at ~5s)

      async def start_typing(self, prospect_id: str, entity) -> None:
          """Start continuous typing indicator for a prospect."""
          if not self._config.typing_simulation:
              return

          if prospect_id in self._typing_tasks:
              return  # Already typing

          async def typing_loop():
              try:
                  while True:
                      await self._client(SetTypingRequest(
                          peer=entity,
                          action=SendMessageTypingAction()
                      ))
                      await asyncio.sleep(self._refresh_interval)
              except asyncio.CancelledError:
                  raise
              except Exception:
                  pass  # Typing is non-critical

          self._typing_tasks[prospect_id] = asyncio.create_task(typing_loop())

      async def stop_typing(self, prospect_id: str) -> None:
          """Stop typing indicator for a prospect."""
          if prospect_id in self._typing_tasks:
              self._typing_tasks[prospect_id].cancel()
              try:
                  await self._typing_tasks[prospect_id]
              except asyncio.CancelledError:
                  pass
              del self._typing_tasks[prospect_id]

      async def stop_all(self) -> None:
          """Stop all typing indicators (for shutdown)."""
          for prospect_id in list(self._typing_tasks.keys()):
              await self.stop_typing(prospect_id)
  ```

### 2. Add Lifecycle Callbacks to MessageBuffer

- Modify `src/sales_agent/messaging/message_buffer.py`:
- Add callback parameters to __init__:
  ```python
  def __init__(
      self,
      timeout_range: tuple[float, float] = (3.0, 5.0),
      flush_callback: Optional[FlushCallback] = None,
      max_messages: int = 10,
      max_wait_seconds: float = 30.0,
      # NEW: Lifecycle callbacks
      on_buffer_active: Optional[Callable[[str], Awaitable[None]]] = None,
      on_flush: Optional[Callable[[str, int, float, str], Awaitable[None]]] = None,
  ):
      # ... existing init ...
      self._on_buffer_active = on_buffer_active
      self._on_flush = on_flush
  ```
- Call on_buffer_active when first message added:
  ```python
  if prospect_id not in self._buffers:
      self._buffers[prospect_id] = []
      self._first_message_time[prospect_id] = message.timestamp
      if self._on_buffer_active:
          await self._on_buffer_active(prospect_id)
  ```
- Track flush reason and call on_flush:
  ```python
  # In _flush_buffer(), before calling flush_callback:
  elapsed = (datetime.now() - self._first_message_time.get(prospect_id, datetime.now())).total_seconds()
  if self._on_flush:
      await self._on_flush(prospect_id, len(messages), elapsed, flush_reason)
  ```
- Track flush_reason in _start_timer() and force flush scenarios

### 3. Create Analytics Data Models

- Create new directory `src/sales_agent/analytics/`
- Create `src/sales_agent/analytics/__init__.py`:
  ```python
  """Analytics module for batch processing metrics."""
  from .models import BatchEvent, FlushReason
  from .batch_analytics_manager import BatchAnalyticsManager

  __all__ = ["BatchEvent", "FlushReason", "BatchAnalyticsManager"]
  ```
- Create `src/sales_agent/analytics/models.py`:
  ```python
  from datetime import datetime
  from enum import Enum
  from typing import Optional
  from pydantic import BaseModel

  class FlushReason(str, Enum):
      TIMEOUT = "timeout"
      MAX_MESSAGES = "max_messages"
      MAX_WAIT = "max_wait"
      SHUTDOWN = "shutdown"
      MANUAL = "manual"

  class BatchEvent(BaseModel):
      """Analytics event for a processed message batch."""
      prospect_id: str
      message_count: int
      total_characters: int
      buffer_duration_seconds: float
      flush_reason: FlushReason
      processing_duration_seconds: Optional[float] = None
      response_length: Optional[int] = None
      sales_rep_id: Optional[str] = None
      created_at: datetime = None

      def __init__(self, **data):
          if data.get('created_at') is None:
              data['created_at'] = datetime.now()
          super().__init__(**data)
  ```

### 4. Create Database Migration for Analytics

- Create `src/sales_agent/migrations/006_batch_analytics.sql`:
  ```sql
  -- Batch Analytics - Captures metrics for message batching
  CREATE TABLE IF NOT EXISTS batch_events (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      prospect_id VARCHAR(255) NOT NULL,
      message_count INT NOT NULL,
      total_characters INT NOT NULL,
      buffer_duration_seconds FLOAT NOT NULL,
      flush_reason VARCHAR(50) NOT NULL,
      processing_duration_seconds FLOAT,
      response_length INT,
      sales_rep_id UUID REFERENCES sales_representatives(id),
      created_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Indexes for efficient querying
  CREATE INDEX IF NOT EXISTS idx_batch_events_prospect
      ON batch_events(prospect_id);

  CREATE INDEX IF NOT EXISTS idx_batch_events_created
      ON batch_events(created_at);

  CREATE INDEX IF NOT EXISTS idx_batch_events_reason
      ON batch_events(flush_reason, created_at);
  ```

### 5. Implement BatchAnalyticsManager

- Create `src/sales_agent/analytics/batch_analytics_manager.py`:
  ```python
  """Batch analytics manager - Persists and queries batch metrics."""
  import asyncpg
  from datetime import datetime, timedelta
  from typing import Optional
  from sales_agent.analytics.models import BatchEvent, FlushReason

  _pool: Optional[asyncpg.Pool] = None

  async def get_pool() -> asyncpg.Pool:
      """Get or create connection pool."""
      global _pool
      if _pool is None:
          import os
          from dotenv import load_dotenv
          load_dotenv()
          _pool = await asyncpg.create_pool(
              os.getenv("DATABASE_URL"),
              min_size=1,
              max_size=3
          )
      return _pool

  async def record_batch_event(event: BatchEvent) -> str:
      """Record a batch event and return its ID."""
      pool = await get_pool()
      async with pool.acquire() as conn:
          row = await conn.fetchrow(
              """
              INSERT INTO batch_events (
                  prospect_id, message_count, total_characters,
                  buffer_duration_seconds, flush_reason,
                  processing_duration_seconds, response_length,
                  sales_rep_id, created_at
              ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
              RETURNING id
              """,
              event.prospect_id,
              event.message_count,
              event.total_characters,
              event.buffer_duration_seconds,
              event.flush_reason.value,
              event.processing_duration_seconds,
              event.response_length,
              event.sales_rep_id,
              event.created_at,
          )
          return str(row['id'])

  async def get_batch_stats(hours: int = 24) -> dict:
      """Get aggregate batch statistics for the last N hours."""
      pool = await get_pool()
      async with pool.acquire() as conn:
          since = datetime.now() - timedelta(hours=hours)
          row = await conn.fetchrow(
              """
              SELECT
                  COUNT(*) as total_batches,
                  SUM(message_count) as total_messages,
                  AVG(message_count) as avg_batch_size,
                  AVG(buffer_duration_seconds) as avg_buffer_duration,
                  AVG(processing_duration_seconds) as avg_processing_duration
              FROM batch_events
              WHERE created_at >= $1
              """,
              since
          )

          reason_counts = await conn.fetch(
              """
              SELECT flush_reason, COUNT(*) as count
              FROM batch_events
              WHERE created_at >= $1
              GROUP BY flush_reason
              """,
              since
          )

          return {
              "total_batches": row['total_batches'] or 0,
              "total_messages": row['total_messages'] or 0,
              "avg_batch_size": float(row['avg_batch_size'] or 0),
              "avg_buffer_duration": float(row['avg_buffer_duration'] or 0),
              "avg_processing_duration": float(row['avg_processing_duration'] or 0),
              "flush_reasons": {r['flush_reason']: r['count'] for r in reason_counts},
          }

  async def close_pool() -> None:
      """Close the connection pool."""
      global _pool
      if _pool:
          await _pool.close()
          _pool = None
  ```

### 6. Add Analytics Configuration to AgentConfig

- Modify `src/sales_agent/crm/models.py`:
- Add after existing batch config fields:
  ```python
  # Analytics configuration
  analytics_enabled: bool = True
  analytics_retention_days: int = 30
  ```

### 7. Integrate Typing Manager in Daemon

- Modify `src/sales_agent/daemon.py`:
- Add imports:
  ```python
  from sales_agent.telegram.typing_manager import BackgroundTypingManager
  from sales_agent.telegram.entity_resolver import resolve_entity
  ```
- Add to __init__:
  ```python
  self.typing_manager = None
  self._prospect_entities: dict[str, any] = {}  # Cache resolved entities
  ```
- In initialize(), after creating service:
  ```python
  # Initialize typing manager
  self.typing_manager = BackgroundTypingManager(self.client, self.config)
  ```
- Create typing callback methods:
  ```python
  async def _on_buffer_active(self, prospect_id: str) -> None:
      """Start typing indicator when buffer becomes active."""
      if prospect_id not in self._prospect_entities:
          entity, _ = await resolve_entity(self.client, prospect_id)
          self._prospect_entities[prospect_id] = entity

      entity = self._prospect_entities.get(prospect_id)
      if entity:
          await self.typing_manager.start_typing(prospect_id, entity)
          console.print(f"[dim]Started typing indicator for {prospect_id}[/dim]")

  async def _on_buffer_flush(self, prospect_id: str, msg_count: int,
                             duration: float, reason: str) -> None:
      """Stop typing and record analytics when buffer flushes."""
      await self.typing_manager.stop_typing(prospect_id)
      console.print(f"[dim]Stopped typing for {prospect_id} ({reason})[/dim]")
  ```
- Update MessageBuffer initialization:
  ```python
  self.message_buffer = MessageBuffer(
      timeout_range=self.config.batch_timeout_medium,
      flush_callback=self._process_message_batch,
      max_messages=self.config.batch_max_messages,
      max_wait_seconds=self.config.batch_max_wait_seconds,
      on_buffer_active=self._on_buffer_active,
      on_flush=self._on_buffer_flush,
  )
  ```

### 8. Add Analytics Recording to Batch Processing

- Modify `_process_message_batch()` in daemon.py:
- Add timing and analytics:
  ```python
  async def _process_message_batch(
      self,
      prospect_id: str,
      messages: list[BufferedMessage]
  ) -> None:
      start_time = datetime.now()

      # ... existing processing code ...

      # After successful response, record analytics
      if self.config.analytics_enabled:
          try:
              from sales_agent.analytics import BatchAnalyticsManager, BatchEvent, FlushReason

              processing_duration = (datetime.now() - start_time).total_seconds()
              total_chars = sum(len(m.text) for m in messages)

              event = BatchEvent(
                  prospect_id=prospect_id,
                  message_count=len(messages),
                  total_characters=total_chars,
                  buffer_duration_seconds=buffer_duration,  # From flush callback
                  flush_reason=FlushReason(flush_reason),
                  processing_duration_seconds=processing_duration,
                  response_length=len(action.response) if action.response else 0,
                  sales_rep_id=str(self.rep_telegram_id) if self.rep_telegram_id else None,
              )
              await BatchAnalyticsManager.record_batch_event(event)
          except Exception as e:
              console.print(f"[yellow]Analytics recording failed: {e}[/yellow]")
  ```

### 9. Update Shutdown to Stop Typing and Close Analytics

- Modify shutdown() method:
  ```python
  async def shutdown(self) -> None:
      """Gracefully shutdown the daemon."""
      self.running = False
      console.print("[yellow]Shutting down...[/yellow]")

      # Stop all typing indicators
      if self.typing_manager:
          await self.typing_manager.stop_all()
          console.print("[green]Typing indicators stopped[/green]")

      # Flush all pending message buffers
      if self.message_buffer:
          pending = self.message_buffer.get_all_pending_prospect_ids()
          if pending:
              console.print(f"[cyan]Flushing {len(pending)} pending buffer(s)...[/cyan]")
              await self.message_buffer.flush_all()

      # Close analytics pool
      try:
          from sales_agent.analytics.batch_analytics_manager import close_pool
          await close_pool()
          console.print("[green]Analytics connections closed[/green]")
      except Exception:
          pass

      # ... rest of existing shutdown ...
  ```

### 10. Enhance Status Table with Analytics

- Update `_create_status_table()` method:
  ```python
  def _create_status_table(self) -> Table:
      table = Table(title="Telegram Agent Status")
      table.add_column("Metric", style="cyan")
      table.add_column("Value", style="green")

      # ... existing metrics ...

      # Add batch analytics section
      if self.config.analytics_enabled:
          try:
              import asyncio
              from sales_agent.analytics.batch_analytics_manager import get_batch_stats
              stats = asyncio.get_event_loop().run_until_complete(get_batch_stats(hours=24))

              table.add_row("", "")  # Separator
              table.add_row("[bold]Batch Analytics (24h)[/bold]", "")
              table.add_row("  Avg Batch Size", f"{stats['avg_batch_size']:.1f} msgs")
              table.add_row("  Avg Buffer Duration", f"{stats['avg_buffer_duration']:.1f}s")
              table.add_row("  Avg Processing Time", f"{stats['avg_processing_duration']:.1f}s")

              reasons = stats.get('flush_reasons', {})
              if reasons:
                  reason_str = ", ".join(f"{k}:{v}" for k, v in reasons.items())
                  table.add_row("  Flush Reasons", reason_str)
          except Exception:
              pass

      return table
  ```

### 11. Run Database Migration

- The migration will run automatically on daemon startup via existing migration runner
- Verify migration by checking database:
  ```sql
  SELECT * FROM schema_migrations WHERE name = '006_batch_analytics.sql';
  ```

### 12. Validate Implementation

- Test typing indicator:
  - Send message to agent
  - Verify typing indicator appears immediately
  - Verify it continues during buffer wait
  - Verify it stops when response is sent

- Test analytics:
  - Send multiple test messages
  - Query database for batch_events
  - Verify metrics are recorded correctly
  - Check status table shows analytics

## Testing Strategy

### Unit Tests

1. **BackgroundTypingManager tests:**
   - Start typing creates task
   - Stop typing cancels task
   - Auto-refresh sends SetTypingRequest every 4 seconds
   - Multiple start calls don't create duplicate tasks
   - stop_all cleans up all tasks

2. **MessageBuffer callback tests:**
   - on_buffer_active called on first message only
   - on_flush called with correct metrics
   - flush_reason tracked correctly

3. **BatchAnalyticsManager tests:**
   - record_batch_event inserts to database
   - get_batch_stats returns correct aggregates
   - Connection pool reuse works

### Integration Tests

1. **Typing indicator flow:**
   - Mock Telegram client
   - Verify SetTypingRequest called on buffer active
   - Verify continued refresh during wait
   - Verify stop on flush

2. **Analytics recording flow:**
   - Test database with real PostgreSQL
   - Verify batch event inserted
   - Verify all fields populated correctly

### Manual Testing

Using test prospect @bohdanpytaichuk:
1. Start daemon: `PYTHONPATH=src uv run python src/sales_agent/daemon.py`
2. Send message from test account
3. Verify typing indicator appears in Telegram
4. Verify typing continues during buffer wait (3-5 seconds)
5. Verify response is received
6. Check database: `SELECT * FROM batch_events ORDER BY created_at DESC LIMIT 5;`
7. Check status table shows analytics metrics

## Acceptance Criteria

1. **Typing indicator works correctly:**
   - Shows immediately when first message buffered
   - Continues throughout buffer wait period
   - Automatically refreshes (no timeout)
   - Stops when response is about to be sent
   - Disabled when typing_simulation=false

2. **Analytics are recorded:**
   - Every batch flush creates database record
   - All metrics captured (count, chars, duration, reason)
   - Processing duration measured accurately
   - Rep ID tracked when in per-rep mode

3. **Statistics are visible:**
   - Status table shows 24h analytics
   - Shutdown summary includes batch stats
   - Flush reason distribution visible

4. **Error handling is robust:**
   - Typing failures don't crash daemon
   - Analytics failures don't block message processing
   - Graceful degradation when database unavailable

5. **Configuration is flexible:**
   - analytics_enabled toggle works
   - typing_simulation toggle respected
   - Can run without database (analytics disabled)

## Validation Commands

Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/sales_agent/telegram/typing_manager.py` - Verify typing manager compiles
- `uv run python -m py_compile src/sales_agent/analytics/batch_analytics_manager.py` - Verify analytics manager compiles
- `PYTHONPATH=src uv run python -c "from sales_agent.telegram.typing_manager import BackgroundTypingManager; print('OK')"` - Test typing import
- `PYTHONPATH=src uv run python -c "from sales_agent.analytics import BatchAnalyticsManager; print('OK')"` - Test analytics import
- `PYTHONPATH=src uv run python -c "from sales_agent.daemon import TelegramDaemon; print('OK')"` - Test daemon import
- `PYTHONPATH=src uv run python src/sales_agent/daemon.py` - Run daemon and test manually

## Notes

### Dependencies

No new external dependencies required:
- asyncio (standard library)
- asyncpg (already installed for scheduled_actions)
- Telethon (already installed)
- Pydantic (already installed)

### Configuration Recommendations

**Typing refresh interval**: 4 seconds is optimal
- Telegram typing status expires after ~5 seconds
- 4 second refresh provides margin for network latency
- Could be made configurable if needed

**Analytics retention**: Consider adding a cleanup job
- Default 30 days retention
- Could add periodic DELETE for old records
- Or use PostgreSQL partitioning for large-scale

### Performance Considerations

**Typing manager impact**: Minimal
- One asyncio task per active conversation
- SetTypingRequest is lightweight API call
- Tasks automatically cleaned up

**Analytics impact**: Low
- Async database writes don't block processing
- Connection pooling minimizes overhead
- Batch stats query is simple aggregation

### Future Improvements

1. **Typing indicator for reading delay**: Also show typing during reading delay, not just buffer wait
2. **Analytics dashboard**: Create web UI for viewing batch analytics trends
3. **ML-based timeout tuning**: Use analytics to automatically adjust timeout values
4. **Alerting**: Notify if force-flush rate exceeds threshold
