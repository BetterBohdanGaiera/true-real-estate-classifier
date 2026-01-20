# Plan: Telegram Classifier Production Deployment

## Task Description

Полный план деплоймента Telegram классификатора для True Real Estate с функционалом:
- AI-агент на Claude для общения с клиентами
- Назначение звонков в Google Calendar и Zoom
- Отложенные сообщения и follow-ups
- Scheduled action manager для долгосрочного планирования
- Daemon для непрерывной работы

## Objective

Задеплоить функционал классификатора на один аккаунт с полным сохранением состояния scheduled actions через перезапуски и гарантированной доставкой follow-up сообщений.

## Problem Statement

Система должна:
1. Работать непрерывно 24/7 с автоматическим восстановлением
2. Сохранять scheduled actions в PostgreSQL для переживания перезапусков
3. Выполнять follow-ups точно по расписанию ("напиши через 2 часа", "свяжись на следующей неделе")
4. Отменять pending actions когда клиент отвечает
5. Интегрироваться с Google Calendar и Zoom для создания встреч

## Solution Approach

Трехфазный подход:
1. **Phase 1**: Инфраструктура (PostgreSQL, переменные окружения, миграции)
2. **Phase 2**: Daemon hardening (процесс-супервизор, health checks, graceful shutdown)
3. **Phase 3**: Интеграция Zoom/Calendar (реальные API вместо mock mode)

---

## Relevant Files

### Критически важные файлы (Core System)

- `src/sales_agent/daemon.py` - Главный daemon, оркестрирует все компоненты (743 строки)
- `src/sales_agent/agent/telegram_agent.py` - Claude AI агент с инструментом `schedule_followup` (688 строк)
- `src/sales_agent/scheduling/scheduler_service.py` - APScheduler wrapper для delayed actions (400 строк)
- `src/sales_agent/scheduling/scheduled_action_manager.py` - PostgreSQL CRUD для scheduled_actions (540 строк)
- `src/sales_agent/crm/prospect_manager.py` - JSON-based CRM для проспектов (407 строк)
- `src/sales_agent/crm/models.py` - Pydantic модели: Prospect, ScheduledAction, AgentAction (143 строки)

### Telegram интеграция

- `src/sales_agent/telegram/telegram_service.py` - Telegram wrapper с typing simulation (283 строки)
- `.claude/skills/telegram/scripts/telegram_fetch.py` - Telethon client для message fetching (933 строки)

### Scheduling и Calendar

- `src/sales_agent/scheduling/sales_calendar.py` - Mock calendar с slot management (479 строк)
- `src/sales_agent/scheduling/scheduling_tool.py` - Mock Zoom booking tool (262 строки)
- `.claude/skills/zoom/scripts/zoom_meetings.py` - РЕАЛЬНЫЙ Zoom API client (651 строка) - **НЕ ИНТЕГРИРОВАН**
- `.claude/skills/google-calendar/scripts/calendar_client.py` - РЕАЛЬНЫЙ Google Calendar client (674 строки) - **НЕ ИНТЕГРИРОВАН**

### База данных и миграции

- `src/sales_agent/migrations/001_scheduled_actions.sql` - Миграция для таблицы scheduled_actions (88 строк)

### Конфигурация

- `.env.example` - Шаблон переменных окружения (147 строк)
- `src/sales_agent/config/agent_config.json` - Конфигурация агента (27 строк)
- `src/sales_agent/config/prospects.json` - База проспектов JSON (55 строк)
- `src/sales_agent/config/sales_slots.json` - Конфигурация слотов (16 строк)
- `pyproject.toml` - Dependencies и entry points (51 строка)

### New Files

- `src/sales_agent/database/__init__.py` - Database module init
- `src/sales_agent/database/init.py` - Database initialization and migration runner
- `src/sales_agent/zoom/__init__.py` - Zoom module init
- `src/sales_agent/zoom/zoom_service.py` - Zoom booking service wrapper
- `deployment/systemd/telegram-agent.service` - Systemd unit file
- `deployment/docker/Dockerfile` - Docker containerization
- `deployment/docker/docker-compose.yml` - Docker compose for full stack
- `scripts/validate_config.py` - Configuration validation script
- `scripts/run_migrations.py` - Migration runner script

---

## Implementation Phases

### Phase 1: Foundation - Database & Infrastructure

**Цель**: Обеспечить надежное хранение scheduled actions и конфигурации

1. Настроить PostgreSQL (NeonDB или локальный)
2. Запустить миграцию `001_scheduled_actions.sql`
3. Добавить автоматический migration runner
4. Добавить валидацию конфигурации при старте
5. Перенести .env credentials из git

### Phase 2: Core Implementation - Daemon Hardening

**Цель**: Обеспечить непрерывную работу 24/7 с автовосстановлением

1. Добавить database init check при запуске daemon
2. Имплементировать graceful shutdown с закрытием pool
3. Добавить systemd/Docker для автоперезапуска
4. Добавить rate limiting для overdue actions при recovery
5. Исправить race condition в cancellation (отмена in-memory tasks)
6. Добавить retry mechanism для failed actions

### Phase 3: Integration & Polish - Zoom/Calendar

**Цель**: Заменить mock mode на реальные API

1. Интегрировать Zoom API client в daemon
2. Интегрировать Google Calendar для синхронизации слотов
3. Добавить pre-meeting reminders (24 часа до встречи)
4. Добавить отправку Zoom link через Telegram
5. Добавить health checks и мониторинг

---

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### 1. Setup PostgreSQL Database

- Создать PostgreSQL database (рекомендуется NeonDB для простоты)
- Получить DATABASE_URL connection string
- Добавить в `.env` файл:
  ```
  DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
  ```
- НЕ коммитить `.env` в git (добавить в `.gitignore`)

### 2. Run Database Migrations

- Выполнить миграцию вручную:
  ```bash
  psql $DATABASE_URL -f src/sales_agent/migrations/001_scheduled_actions.sql
  ```
- Проверить создание таблицы:
  ```sql
  SELECT * FROM scheduled_actions LIMIT 1;
  ```

### 3. Create Migration Runner Script

- Создать `scripts/run_migrations.py`:
  ```python
  # Читает все .sql файлы из migrations/ и выполняет по порядку
  # Трекает выполненные миграции чтобы не перезапускать
  ```
- Добавить tracking table: `schema_migrations(version, applied_at)`

### 4. Add Database Initialization to Daemon

- Модифицировать `daemon.py` метод `initialize()`:
  - Проверить DATABASE_URL до запуска
  - Проверить доступность базы данных
  - Вызвать migration runner если нужно
  - Fail-fast если база недоступна

### 5. Implement Proper Connection Pool Cleanup

- В `daemon.py` метод `shutdown()`:
  - Добавить вызов `close_pool()` из scheduled_action_manager
  - Добавить логирование закрытия соединений
- В `scheduled_action_manager.py`:
  - Увеличить pool size для production (min=5, max=20)
  - Добавить command_timeout=10

### 6. Fix In-Memory Task Cancellation

- В `daemon.py` после `cancel_pending_for_prospect()`:
  - Получить список cancelled action IDs
  - Вызвать `scheduler_service.cancel_action(action_id)` для каждого
  - Это остановит asyncio tasks до scheduled time

### 7. Add Rate Limiting for Overdue Actions

- В `scheduler_service.py` метод `_recover_pending_actions()`:
  - Добавить `await asyncio.sleep(5)` между overdue executions
  - Это предотвратит flooding Telegram API при массовом recovery

### 8. Add Retry Mechanism for Failed Actions

- Добавить колонку в миграцию:
  ```sql
  ALTER TABLE scheduled_actions ADD COLUMN retry_count INT DEFAULT 0;
  ALTER TABLE scheduled_actions ADD COLUMN last_error TEXT;
  ```
- В `scheduler_service.py` метод `_execute_action()`:
  - При ошибке: increment retry_count, log error
  - Если retry_count < 3: reschedule с exponential backoff (1min, 5min, 15min)
  - Если retry_count >= 3: mark as 'failed' (новый status)

### 9. Create Process Supervisor Configuration

- Создать `deployment/systemd/telegram-agent.service`:
  ```ini
  [Unit]
  Description=Telegram Sales Agent Daemon
  After=network.target postgresql.service

  [Service]
  Type=simple
  User=sales_agent
  WorkingDirectory=/path/to/Classifier
  ExecStart=/path/to/uv run python src/sales_agent/daemon.py
  Restart=always
  RestartSec=5
  Environment=PYTHONUNBUFFERED=1

  [Install]
  WantedBy=multi-user.target
  ```

### 10. Create Docker Configuration

- Создать `deployment/docker/Dockerfile`:
  ```dockerfile
  FROM python:3.12-slim
  WORKDIR /app
  RUN pip install uv
  COPY pyproject.toml uv.lock ./
  RUN uv sync
  COPY src/ ./src/
  COPY .claude/skills/ ./.claude/skills/
  CMD ["uv", "run", "python", "src/sales_agent/daemon.py"]
  ```

### 11. Create Configuration Validation Script

- Создать `scripts/validate_config.py`:
  - Проверить все required env vars (ANTHROPIC_API_KEY, DATABASE_URL)
  - Проверить Telegram credentials в `~/.telegram_dl/`
  - Проверить database connectivity
  - Проверить API keys validity (test API calls)
  - Exit с clear error messages если что-то missing

### 12. Integrate Zoom API Client

- Создать `src/sales_agent/zoom/__init__.py` и `zoom_service.py`:
  ```python
  class ZoomBookingService:
      def create_meeting(self, topic, start_time, duration, invitees) -> str:
          # Calls .claude/skills/zoom/scripts/zoom_meetings.py logic
          # Returns Zoom join URL
  ```
- Модифицировать `scheduling_tool.py`:
  - Принимать optional `zoom_service` в constructor
  - Если zoom_service есть: создавать реальные meetings
  - Возвращать реальный `zoom_url` вместо `None`

### 13. Update Daemon for Real Zoom Integration

- В `daemon.py` метод `initialize()`:
  - Инициализировать ZoomBookingService (если credentials есть)
  - Передать в SchedulingTool
- При booking:
  - Создавать реальный Zoom meeting
  - Отправлять join link клиенту в Telegram

### 14. Add Pre-Meeting Reminders

- После успешного booking в `daemon.py`:
  - Создать scheduled action типа `PRE_MEETING_REMINDER`
  - scheduled_for = meeting_time - 24 hours
  - payload содержит meeting details и Zoom URL
- В `execute_scheduled_action()`:
  - Handle `PRE_MEETING_REMINDER` action type
  - Отправить напоминание с Zoom link

### 15. Integrate Google Calendar (Optional)

- Импортировать CalendarClient из `.claude/skills/google-calendar/`
- В `SalesCalendar`:
  - Читать реальные слоты из Google Calendar
  - При booking создавать event в Calendar
  - Sync availability с реальным календарем

### 16. Add Health Check Endpoint

- Создать simple HTTP endpoint (FastAPI или aiohttp):
  - `/health` - returns 200 if daemon is running
  - `/metrics` - returns stats (messages_sent, meetings_scheduled, etc.)
- Использовать для Docker health checks и мониторинга

### 17. Clean Up Legacy Code

- Удалить дублирующийся daemon в `.claude/skills/telegram/scripts/run_daemon.py`
- Обновить все imports чтобы использовать `src/sales_agent/`
- Убрать unused files и TODO comments

### 18. Production Environment Setup

- Создать production `.env` (не в git!)
- Настроить log rotation
- Настроить backup strategy для PostgreSQL
- Настроить мониторинг и alerts

---

## Testing Strategy

### Unit Tests

1. **ScheduledActionManager tests**:
   - Test create/read/update/cancel operations
   - Test concurrent access (asyncpg pool)
   - Test recovery of pending actions

2. **SchedulerService tests**:
   - Test scheduling and execution
   - Test cancellation
   - Test overdue action handling

3. **TelegramAgent tests**:
   - Test schedule_followup tool parsing
   - Test natural time expression parsing
   - Test response generation

### Integration Tests

1. **Database integration**:
   - Use ephemeral test database
   - Test migrations on clean database
   - Test full action lifecycle

2. **Telegram integration**:
   - Use test prospect account
   - Test message sending/receiving
   - Test typing simulation

### End-to-End Tests

1. **Follow-up scenario**:
   - Client says "напиши через 5 минут"
   - Agent schedules follow-up
   - Wait 5 minutes
   - Verify follow-up sent

2. **Cancellation scenario**:
   - Schedule follow-up for 10 minutes
   - Client responds after 2 minutes
   - Verify follow-up cancelled

3. **Recovery scenario**:
   - Schedule follow-up
   - Kill daemon process
   - Restart daemon
   - Verify follow-up still executed

---

## Acceptance Criteria

1. **Daemon runs 24/7**: Автоматический перезапуск через systemd/Docker при crash
2. **Scheduled actions persist**: Follow-ups сохраняются в PostgreSQL и переживают перезапуски
3. **Natural time parsing**: Агент понимает "завтра", "через 2 часа", "на следующей неделе"
4. **Cancellation works**: При ответе клиента все pending follow-ups отменяются
5. **Recovery works**: При старте daemon выполняет overdue actions и reschedules future ones
6. **Zoom meetings created**: При booking создается реальный Zoom meeting с join URL
7. **No data loss**: Все conversation history и prospect data сохраняются
8. **Graceful shutdown**: При SIGTERM корректно закрываются connections и сохраняется state

---

## Validation Commands

Execute these commands to validate the task is complete:

- `uv run python scripts/validate_config.py` - Проверить все credentials и connections
- `psql $DATABASE_URL -c "SELECT COUNT(*) FROM scheduled_actions"` - Проверить таблицу существует
- `uv run python -c "from sales_agent.scheduling.scheduled_action_manager import get_pool; import asyncio; asyncio.run(get_pool())"` - Проверить database connection
- `uv run python src/sales_agent/daemon.py --dry-run` - Проверить daemon startup (если добавлен флаг)
- `systemctl status telegram-agent` - Проверить systemd service (если настроен)
- `docker ps | grep telegram-agent` - Проверить Docker container (если настроен)
- `curl http://localhost:8080/health` - Проверить health endpoint (если добавлен)

---

## Notes

### Что уже работает

1. **Telegram integration**: Telethon client полностью функционален
2. **Claude AI agent**: Генерирует ответы с schedule_followup tool
3. **PostgreSQL scheduled_actions**: Таблица создана, CRUD работает
4. **APScheduler integration**: SchedulerService реализован с recovery
5. **Human takeover**: human_active flag блокирует автоматизацию
6. **Working hours**: Ограничение времени работы агента

### Что требует внимания

1. **Zoom/Calendar mock mode**: Реальные API clients существуют но НЕ интегрированы
2. **JSON prospect storage**: Не идеально для production, но работает для одного аккаунта
3. **In-memory task tracking**: asyncio tasks теряются при crash (но PostgreSQL сохраняет)
4. **No retry mechanism**: Failed actions не ретраятся

### Зависимости для установки

```bash
uv add asyncpg          # PostgreSQL async driver (уже есть)
uv add apscheduler      # Job scheduling (уже есть)
uv add aiohttp          # Для health check endpoint (опционально)
```

### Переменные окружения (REQUIRED)

```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

### Переменные окружения (OPTIONAL - для Zoom/Calendar)

```
ZOOM_ACCOUNT_ID=...
ZOOM_CLIENT_ID=...
ZOOM_CLIENT_SECRET=...
```

### Credential Storage Locations

- Telegram: `~/.telegram_dl/config.json` и `~/.telegram_dl/user.session`
- Google Calendar: `.claude/skills/google-calendar/accounts/*.json`
- Zoom: `~/.zoom_credentials/credentials.json`

### Priority Order

1. **CRITICAL**: PostgreSQL setup + migration (без этого scheduled actions не работают)
2. **HIGH**: Daemon hardening (systemd/Docker) для 24/7 работы
3. **MEDIUM**: Zoom integration (mock mode работает для MVP)
4. **LOW**: Google Calendar sync (можно использовать mock slots)
