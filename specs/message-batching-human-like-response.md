# Plan: Message Batching for Human-Like Responses

## Task Description

Реализовать механизм группировки (batching) входящих сообщений от пользователя, чтобы агент мог ждать завершения "пачки" сообщений и отвечать одним комплексным ответом на все сообщения сразу. Это имитирует человеческое поведение, когда человек дочитывает все сообщения собеседника перед тем, как ответить.

**Проблема со скриншота:**
- Пользователь отправил "Инвестицию" (17:52)
- Затем сразу "Слушай, а можешь мне через 5 минут написать?" (17:53)
- Бот ответил на каждое сообщение отдельно:
  - "Хорошо, напишу через 5 минут! 👍" (на второе)
  - "Отлично! Для инвестиций в Чангу и Улувату..." (на первое)

Это выглядит неестественно - человек бы прочитал оба сообщения и ответил одним сообщением, адресовав обе темы.

## Objective

Реализовать систему буферизации входящих сообщений с таймером ожидания, которая:
1. Накапливает сообщения от одного пользователя в течение определенного окна ожидания
2. При получении нового сообщения сбрасывает таймер (debounce pattern)
3. После истечения таймера отправляет все накопленные сообщения агенту как единый контекст
4. Агент отвечает одним комплексным сообщением на всю "пачку"

## Problem Statement

Текущая архитектура обрабатывает каждое входящее сообщение независимо через event handler `handle_incoming()` в daemon.py. При получении сообщения:
1. Сразу записывается в историю
2. Отменяются pending follow-ups
3. Рассчитывается reading delay
4. Генерируется ответ через Claude API
5. Отправляется ответ

Это приводит к:
- Множественным ответам на серию быстрых сообщений
- Потере контекста между сообщениями
- Неестественному поведению бота

## Solution Approach

Реализовать **debounce-паттерн** для входящих сообщений:

1. **Message Buffer** - in-memory структура для накопления сообщений по prospect_id
2. **Debounce Timer** - asyncio task с configurable timeout (default: 3-5 секунд)
3. **Message Aggregator** - объединение текстов сообщений перед отправкой агенту
4. **Modified Event Handler** - буферизация вместо немедленной обработки

### Алгоритм:

```
┌─────────────────────┐
│ Incoming Message    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Add to Buffer       │
│ for prospect_id     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────┐
│ Timer exists?       │─YES→│ Cancel old timer │
│ for prospect_id     │     │ Start new timer  │
└──────────┬──────────┘     └──────────────────┘
           │ NO
           ▼
┌─────────────────────┐
│ Start new timer     │
│ (batch_timeout sec) │
└──────────┬──────────┘
           │
           │ Timer expires
           ▼
┌─────────────────────┐
│ Flush buffer        │
│ Process all msgs    │
│ Clear buffer        │
└─────────────────────┘
```

## Relevant Files

Используй эти файлы для выполнения задачи:

### Core Files to Modify

- **`src/sales_agent/daemon.py`** (lines 245-400)
  - Текущий event handler `handle_incoming()` - основное место изменений
  - Добавить message buffer и timer management
  - Модифицировать логику обработки для batch processing

- **`src/sales_agent/crm/models.py`** (lines 125-156)
  - Добавить конфигурационные поля для batch settings в `AgentConfig`
  - `batch_timeout_seconds: tuple[float, float]` - диапазон ожидания
  - `batch_enabled: bool` - включить/выключить функционал

- **`src/sales_agent/config/agent_config.json`** (lines 1-33)
  - Добавить runtime конфигурацию для batching
  - Default values для timeout

### Supporting Files to Reference

- **`src/sales_agent/agent/telegram_agent.py`** (lines 387-464)
  - Метод `generate_response()` - нужно адаптировать для multiple messages
  - System prompt может потребовать обновления для batch context

- **`src/sales_agent/telegram/telegram_service.py`** (lines 73-112)
  - Delay calculation logic - понадобится для reading delay на batch

- **`src/sales_agent/crm/prospect_manager.py`** (lines 148-220)
  - Методы записи сообщений - нужно адаптировать для batch recording

### New Files to Create

- **`src/sales_agent/messaging/message_buffer.py`** (NEW)
  - Класс `MessageBuffer` для управления буфером сообщений
  - Debounce timer logic
  - Thread-safe operations

## Implementation Phases

### Phase 1: Foundation - Message Buffer Class

Создать отдельный модуль для управления буфером сообщений:
- In-memory storage с prospect_id как ключом
- Asyncio timer management
- Callback mechanism для flush events

### Phase 2: Core Implementation - Daemon Integration

Интегрировать buffer в daemon:
- Модифицировать event handler для буферизации
- Реализовать flush callback с batch processing
- Сохранить совместимость с существующей логикой

### Phase 3: Integration & Polish

- Обновить конфигурацию
- Адаптировать agent prompt для batch context
- Тестирование различных сценариев

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### 1. Create MessageBuffer Class

- Создать новый файл `src/sales_agent/messaging/__init__.py`
- Создать файл `src/sales_agent/messaging/message_buffer.py`
- Реализовать класс `MessageBuffer`:
  ```python
  class BufferedMessage:
      """Single buffered message."""
      message_id: int
      text: str
      timestamp: datetime

  class MessageBuffer:
      """Manages message batching with debounce timer."""

      def __init__(self,
                   timeout_range: tuple[float, float] = (3.0, 5.0),
                   flush_callback: Callable = None):
          self._buffers: dict[str, list[BufferedMessage]] = {}
          self._timers: dict[str, asyncio.Task] = {}
          self._timeout_range = timeout_range
          self._flush_callback = flush_callback

      async def add_message(self, prospect_id: str, message: BufferedMessage) -> None:
          """Add message to buffer and reset timer."""

      async def _start_timer(self, prospect_id: str) -> None:
          """Start or reset debounce timer."""

      async def _flush_buffer(self, prospect_id: str) -> None:
          """Flush buffer and call callback with all messages."""

      def get_buffer_size(self, prospect_id: str) -> int:
          """Get current buffer size for prospect."""

      async def cancel_timer(self, prospect_id: str) -> None:
          """Cancel timer without flushing (e.g., on shutdown)."""
  ```

### 2. Add Configuration Fields

- В `src/sales_agent/crm/models.py` добавить в `AgentConfig`:
  ```python
  # Message batching configuration
  batch_enabled: bool = True
  batch_timeout_short: tuple[float, float] = (2.0, 3.0)   # <50 chars last msg
  batch_timeout_medium: tuple[float, float] = (3.0, 5.0)  # 50-200 chars
  batch_timeout_long: tuple[float, float] = (5.0, 8.0)    # >200 chars
  batch_max_messages: int = 10  # Safety limit
  batch_max_wait_seconds: float = 30.0  # Maximum total wait time
  ```

- В `src/sales_agent/config/agent_config.json` добавить defaults:
  ```json
  "batch_enabled": true,
  "batch_timeout_short": [2.0, 3.0],
  "batch_timeout_medium": [3.0, 5.0],
  "batch_timeout_long": [5.0, 8.0],
  "batch_max_messages": 10,
  "batch_max_wait_seconds": 30.0
  ```

### 3. Modify Daemon Event Handler

- В `src/sales_agent/daemon.py`:
  - Добавить import для MessageBuffer
  - Инициализировать buffer в `__init__` с flush callback
  - Создать новый метод `_process_message_batch()`
  - Модифицировать `handle_incoming()` для буферизации:

  ```python
  # В __init__:
  self.message_buffer = None  # Initialized in initialize()

  # В initialize():
  self.message_buffer = MessageBuffer(
      timeout_range=self.config.batch_timeout_medium,
      flush_callback=self._process_message_batch
  )

  # В handle_incoming():
  # Instead of immediate processing:
  if self.config.batch_enabled:
      buffered_msg = BufferedMessage(
          message_id=event.id,
          text=event.text,
          timestamp=datetime.now()
      )
      await self.message_buffer.add_message(
          str(prospect.telegram_id),
          buffered_msg
      )
      console.print(f"[dim]Buffered message, waiting for more...[/dim]")
      return  # Don't process immediately
  else:
      # Original immediate processing
      ...
  ```

### 4. Implement Batch Processing Method

- Создать метод `_process_message_batch()` в TelegramDaemon:
  ```python
  async def _process_message_batch(
      self,
      prospect_id: str,
      messages: list[BufferedMessage]
  ) -> None:
      """Process a batch of messages from one prospect."""

      # 1. Get prospect
      prospect = self.prospect_manager.get_prospect(int(prospect_id))

      # 2. Record ALL messages in history
      for msg in messages:
          self.prospect_manager.record_response(
              prospect.telegram_id,
              msg.message_id,
              msg.text
          )

      # 3. Cancel pending follow-ups (once, not per message)
      await cancel_pending_for_prospect(prospect_id, reason="client_responded")

      # 4. Aggregate messages for AI
      combined_text = self._aggregate_messages(messages)

      # 5. Calculate reading delay for TOTAL text
      total_length = sum(len(m.text) for m in messages)
      reading_delay = self._calculate_batch_reading_delay(total_length)
      await asyncio.sleep(reading_delay)

      # 6. Get context and generate SINGLE response
      context = self.prospect_manager.get_conversation_context(prospect.telegram_id)
      action = await self.agent.generate_response(
          prospect,
          combined_text,  # All messages as one
          context
      )

      # 7. Handle action (same as before)
      ...
  ```

### 5. Create Message Aggregation Logic

- Добавить метод `_aggregate_messages()`:
  ```python
  def _aggregate_messages(self, messages: list[BufferedMessage]) -> str:
      """Combine multiple messages into single context for AI."""
      if len(messages) == 1:
          return messages[0].text

      # Format multiple messages with timestamps
      lines = []
      for i, msg in enumerate(messages, 1):
          time_str = msg.timestamp.strftime("%H:%M")
          lines.append(f"[{time_str}] {msg.text}")

      return "\n".join(lines)
  ```

### 6. Adapt Agent for Batch Context

- В `src/sales_agent/agent/telegram_agent.py` обновить user prompt в `generate_response()`:
  ```python
  # Detect if this is a batch (multiple messages)
  is_batch = "\n[" in incoming_message and "]\n" in incoming_message

  if is_batch:
      user_prompt = f"""Клиент написал НЕСКОЛЬКО сообщений подряд.
      Прочитай ВСЕ сообщения и ответь ОДНИМ сообщением, адресовав все темы.

      Сообщения клиента:
      {incoming_message}

      История переписки:
      {conversation_context}

      ВАЖНО: Не отвечай на каждое сообщение отдельно. Напиши ОДИН ответ,
      который охватывает все темы из сообщений клиента.
      """
  else:
      # Original single message prompt
      ...
  ```

### 7. Handle Edge Cases

- Добавить safety limits:
  - Maximum messages in buffer (default: 10)
  - Maximum total wait time (default: 30 seconds)
  - Graceful shutdown - flush all buffers before exit

- В `_start_timer()` проверять limits:
  ```python
  # Force flush if buffer is too large
  if len(self._buffers[prospect_id]) >= self._max_messages:
      await self._flush_buffer(prospect_id)
      return

  # Force flush if waiting too long
  first_msg_time = self._buffers[prospect_id][0].timestamp
  if (datetime.now() - first_msg_time).total_seconds() > self._max_wait_seconds:
      await self._flush_buffer(prospect_id)
      return
  ```

### 8. Update Shutdown Sequence

- В `daemon.py` метод shutdown:
  ```python
  async def shutdown(self) -> None:
      """Graceful shutdown."""
      # Flush all pending message buffers before shutdown
      if self.message_buffer:
          for prospect_id in list(self.message_buffer._buffers.keys()):
              await self.message_buffer._flush_buffer(prospect_id)

      # Rest of shutdown logic...
  ```

### 9. Add Logging and Monitoring

- Добавить Rich console output для отслеживания batching:
  ```python
  console.print(f"[dim]Buffered: {len(messages)} msgs from {prospect.name}[/dim]")
  console.print(f"[dim]Batch timeout: {timeout:.1f}s[/dim]")
  console.print(f"[cyan]Processing batch of {len(messages)} messages[/cyan]")
  ```

- Добавить stats tracking:
  ```python
  self.stats["messages_batched"] = 0
  self.stats["batches_processed"] = 0
  ```

### 10. Validate Implementation

- Проверить работу с тестовым prospect @bohdanpytaichuk:
  1. Отправить одно сообщение - должно обработаться после timeout
  2. Отправить 2-3 сообщения быстро - должны сгруппироваться
  3. Отправить сообщения с большим интервалом - должны обработаться раздельно
  4. Проверить graceful shutdown
  5. Проверить edge cases (max messages, max wait time)

## Testing Strategy

### Unit Tests

1. **MessageBuffer tests:**
   - Add single message - verify buffer content
   - Add multiple messages - verify aggregation
   - Timer reset on new message
   - Force flush on max messages
   - Force flush on max wait time
   - Cancel timer without flush

2. **Message aggregation tests:**
   - Single message - no formatting
   - Multiple messages - proper formatting with timestamps

### Integration Tests

1. **Daemon batch processing:**
   - Mock Telegram events
   - Verify batch callback is called
   - Verify correct message count in batch

2. **End-to-end flow:**
   - Send test messages via manual_test.py
   - Verify single response to multiple messages
   - Verify response addresses all topics

### Manual Testing

Using test prospect @bohdanpytaichuk:
1. Send: "Привет"
2. Wait 1 second
3. Send: "Интересует инвестиция"
4. Wait 1 second
5. Send: "Бюджет 300к"
6. Verify: Single response addressing all three points

## Acceptance Criteria

1. **Batching works correctly:**
   - Messages within timeout window are grouped
   - Messages outside window are processed separately
   - Timer resets correctly on each new message

2. **Agent responds appropriately:**
   - Single response to message batch
   - Response addresses all topics from batch
   - Natural language flow maintained

3. **Configuration is flexible:**
   - Timeout values configurable via agent_config.json
   - Feature can be disabled via batch_enabled=false
   - Safety limits prevent runaway buffering

4. **Edge cases handled:**
   - Graceful shutdown flushes buffers
   - Max message limit triggers immediate flush
   - Max wait time triggers immediate flush

5. **Backward compatibility:**
   - With batch_enabled=false, behavior identical to current
   - No breaking changes to existing API

## Validation Commands

Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/sales_agent/messaging/message_buffer.py` - Verify buffer module compiles
- `uv run python -m py_compile src/sales_agent/daemon.py` - Verify daemon compiles with changes
- `PYTHONPATH=src uv run python -c "from sales_agent.messaging import MessageBuffer; print('OK')"` - Test import
- `PYTHONPATH=src uv run python src/sales_agent/testing/manual_test.py` - Run manual test to verify batching

## Notes

### New Dependencies

Никаких новых зависимостей не требуется - используем только стандартные asyncio и dataclasses.

### Configuration Considerations

Timeout values должны быть балансом между:
- **Слишком короткий** (< 2s): сообщения не успевают сгруппироваться
- **Слишком длинный** (> 10s): неестественная задержка ответа

Рекомендуемые defaults:
- Short messages: 2-3 секунды
- Medium messages: 3-5 секунд
- Long messages: 5-8 секунд

### Performance Considerations

- In-memory buffer - легковесное решение
- Asyncio tasks - не блокируют event loop
- При перезапуске daemon'а buffered messages будут потеряны (acceptable trade-off)

### Future Improvements

1. **Persistent buffer** - сохранение в Redis/DB для reliability
2. **Smart batching** - определение "конца мысли" по пунктуации
3. **Typing indicator** - показывать "typing..." пока buffer активен
4. **Analytics** - метрики по размерам батчей для оптимизации timeout
