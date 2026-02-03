# Plan: Sales Representative Registry Telegram Bot

## Task Description

Build a Sales Representative Registry system implemented as a Telegram bot that allows:

1. Multiple sales representatives to register and be managed (add/remove)
2. Each sales rep to have Google Calendar + Zoom meeting creation capabilities
3. Sales reps to onboard themselves via Telegram through a **conversational flow** (bot asks everything proactively)
4. Leverage corporate email structure (domain emails) for Google Calendar integration
5. Assign test prospects to sales reps for proactive outreach
6. Automatically reach out to prospects with "unreached" status

## Objective

Create a multi-tenant sales agent registry where each sales representative:

- Can self-register via **conversational Telegram bot** (bot guides the entire process)
- Has their own Google Calendar account connected (via domain email)
- Can have Zoom meetings created on their behalf
- Is assigned prospects and proactively contacts those with "unreached" status
- Is managed (added/removed) by administrators through natural conversation

## Problem Statement

The current codebase has a single-agent architecture with:

- One `AgentConfig` with a single `telegram_account` field
- Prospects stored in JSON file (`prospects.json`)
- No database table for agents/users
- Zoom and Google Calendar configured for a single account

To support multiple sales representatives, we need:

- Database-backed agent registry
- Per-agent Google Calendar OAuth tokens
- Per-agent Zoom credentials or shared organizational Zoom
- **Conversational** Telegram bot interface for self-service onboarding
- Prospect assignment to sales reps
- Proactive outreach for unreached prospects
- Administrative controls for managing the registry

## Solution Approach

1. **Database Schema Extension**: Add `sales_representatives` and `test_prospects` tables to PostgreSQL
2. **Pydantic Models**: Create `SalesRepresentative` model with status, email, calendar config
3. **Conversational Telegram Bot**: Build a bot that **proactively asks users questions** - no commands needed
4. **Google Calendar Integration**: Leverage existing skill pattern with per-rep token storage
5. **Prospect Assignment**: Link prospects to sales reps for proactive outreach
6. **Proactive Daemon**: Automatically contact "unreached" prospects through assigned sales reps

## Relevant Files

### Existing Files to Modify

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/crm/models.py`
  - Add `SalesRepresentative` and `SalesRepStatus` Pydantic models
  - Add `TestProspect` model with `assigned_rep_id` field

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/database/init.py`
  - Ensure migration infrastructure supports new tables

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.env.example`
  - Add `TELEGRAM_BOT_TOKEN` for the registry bot
  - Add `ADMIN_TELEGRAM_IDS` for admin authorization
  - Add `CORPORATE_EMAIL_DOMAIN` for email validation

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.claude/skills/google-calendar/scripts/calendar_client.py`
  - Reference for OAuth pattern (no changes needed)

### New Files to Create

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/migrations/002_sales_representatives.sql`
  - Database schema for sales_representatives table

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/migrations/003_test_prospects.sql`
  - Database schema for test_prospects table with sales rep assignment

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/__init__.py`
  - Module initialization

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/models.py`
  - SalesRepresentative, SalesRepStatus, TestProspect models

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/sales_rep_manager.py`
  - CRUD operations for sales representatives (asyncpg pattern)

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/prospect_manager.py`
  - CRUD operations for test prospects with assignment

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/registry_bot.py`
  - **Conversational** Telegram bot - proactively guides users

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/calendar_connector.py`
  - Google Calendar OAuth flow handler for per-rep authentication

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/zoom_connector.py`
  - Zoom integration for per-rep or shared Zoom account

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/outreach_daemon.py`
  - Background service to contact unreached prospects

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/run_registry_bot.py`
  - Entry point for running the registry bot

## Test Prospects (Temporary - Will Be Replaced by CRM)

For testing purposes, seed the database with 3 test prospects:

```json
[
  {
    "id": "test_prospect_001",
    "telegram_id": "@test_buyer_alex",
    "name": "Алексей Петров",
    "context": "Интересуется виллой в Чангу, бюджет $300-500k",
    "status": "unreached",
    "assigned_rep_id": null,
    "email": "alex.petrov@gmail.com",
    "notes": "Видел рекламу в Instagram"
  },
  {
    "id": "test_prospect_002",
    "telegram_id": "@test_investor_maria",
    "name": "Мария Козлова",
    "context": "Инвестор, рассматривает апартаменты для сдачи в аренду",
    "status": "unreached",
    "assigned_rep_id": null,
    "email": "m.kozlova@yandex.ru",
    "notes": "Рекомендация от существующего клиента"
  },
  {
    "id": "test_prospect_003",
    "telegram_id": "@test_family_dmitry",
    "name": "Дмитрий Новиков",
    "context": "Семья с детьми, ищут дом для переезда на Бали",
    "status": "unreached",
    "assigned_rep_id": null,
    "email": "d.novikov@mail.ru",
    "notes": "Планирует переезд через 6 месяцев"
  }
]
```

**Note**: These test prospects will be replaced with CRM integration in a future phase.

## Implementation Phases

### Phase 1: Foundation (Database & Models)

1. Create database migration for `sales_representatives` table
2. Create database migration for `test_prospects` table with `assigned_rep_id`
3. Define Pydantic models for sales rep and prospect data
4. Implement `SalesRepManager` with CRUD operations
5. Implement `TestProspectManager` with assignment operations
6. Add environment variables for bot configuration

### Phase 2: Conversational Bot Implementation

1. Implement **conversational** Telegram bot with python-telegram-bot library
2. Bot proactively asks questions - **no commands needed from user**
3. Implement conversation states for registration and unregistration
4. Admin receives notifications and can reply conversationally to approve/reject

### Phase 3: Calendar & Zoom Integration

1. Create per-rep Google Calendar OAuth connector
2. Store tokens in database (encrypted) or file system (existing pattern)
3. Integrate Zoom meeting creation for registered reps
4. Bot proactively asks about calendar connection after approval

### Phase 4: Proactive Outreach System

1. Create outreach daemon that monitors "unreached" prospects
2. Assign prospects to active sales reps (round-robin or manual)
3. Trigger proactive contact through assigned rep's account
4. Update prospect status after contact attempt

## Step by Step Tasks

### 1. Create Database Migration for Sales Reps

- Create file `src/sales_agent/migrations/002_sales_representatives.sql`
- Define `sales_representatives` table with columns:
  - `id` (UUID, primary key)
  - `telegram_id` (BIGINT, unique, not null)
  - `telegram_username` (VARCHAR(255))
  - `name` (VARCHAR(255), not null)
  - `email` (VARCHAR(255), not null)
  - `status` (VARCHAR(50), default 'pending')
  - `calendar_account_name` (VARCHAR(255), nullable) - maps to google calendar account
  - `zoom_user_id` (VARCHAR(255), nullable)
  - `is_admin` (BOOLEAN, default false)
  - `registered_at` (TIMESTAMPTZ)
  - `approved_at` (TIMESTAMPTZ)
  - `approved_by` (UUID, nullable, FK to self)
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- Add indexes on `telegram_id`, `email`, `status`

### 2. Create Database Migration for Test Prospects

- Create file `src/sales_agent/migrations/003_test_prospects.sql`
- Define `test_prospects` table with columns:
  - `id` (VARCHAR(255), primary key)
  - `telegram_id` (VARCHAR(255), not null)
  - `name` (VARCHAR(255), not null)
  - `context` (TEXT)
  - `status` (VARCHAR(50), default 'unreached') - unreached, contacted, in_conversation, converted, archived
  - `assigned_rep_id` (UUID, nullable, FK to sales_representatives)
  - `email` (VARCHAR(255), nullable)
  - `notes` (TEXT)
  - `last_contact_at` (TIMESTAMPTZ)
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- Add indexes on `status`, `assigned_rep_id`
- Insert seed data for 3 test prospects

### 3. Create Pydantic Models

- Create file `src/sales_agent/registry/models.py`
- Define `SalesRepStatus` enum: `PENDING`, `ACTIVE`, `SUSPENDED`, `REMOVED`
- Define `ProspectStatus` enum: `UNREACHED`, `CONTACTED`, `IN_CONVERSATION`, `CONVERTED`, `ARCHIVED`
- Define `SalesRepresentative` model with all fields
- Define `TestProspect` model with `assigned_rep_id` field
- Define `ConversationState` enum for bot states

### 4. Implement Sales Rep Manager

- Create file `src/sales_agent/registry/sales_rep_manager.py`
- Follow pattern from `scheduled_action_manager.py`
- Implement functions:
  - `create_sales_rep()` - Register new rep (status=PENDING)
  - `get_by_telegram_id()` - Lookup by Telegram ID
  - `get_by_email()` - Lookup by email
  - `list_all()` - List all reps
  - `list_active()` - List active reps for prospect assignment
  - `list_pending()` - List pending approvals
  - `approve_rep()` - Change status to ACTIVE
  - `suspend_rep()` - Change status to SUSPENDED
  - `remove_rep()` - Change status to REMOVED
  - `update_rep()` - Update rep details
  - `set_calendar_account()` - Link Google Calendar account

### 5. Implement Test Prospect Manager

- Create file `src/sales_agent/registry/prospect_manager.py`
- Implement functions:
  - `get_unreached_prospects()` - Get all with status='unreached'
  - `assign_prospect_to_rep()` - Set assigned_rep_id
  - `get_prospects_for_rep()` - Get prospects assigned to specific rep
  - `update_prospect_status()` - Change prospect status
  - `record_contact()` - Update last_contact_at
  - `get_unassigned_unreached()` - Get unreached without rep assignment

### 6. Create Conversational Registry Bot

- Create file `src/sales_agent/registry/registry_bot.py`
- Use `python-telegram-bot` library with `ConversationHandler`
- **Key principle**: Bot asks everything, user just answers

**Conversation Flow for New Users:**

```
Bot: "Привет! Я бот для регистрации менеджеров по продажам True Real Estate.

Хотите зарегистрироваться как менеджер?"

User: "Да" / "Нет" / any response

Bot: "Отлично! Как вас зовут? (Имя и фамилия)"

User: "Иван Иванов"

Bot: "Приятно познакомиться, Иван!

Какой ваш корпоративный email? (должен быть @truerealestate.bali)"

User: "ivan@truerealestate.bali"

Bot: "Спасибо! Ваша заявка отправлена администратору.

Я напишу вам, когда её одобрят.

Если хотите отменить заявку - просто напишите мне."
```

**Conversation Flow for Registered Users:**

```
Bot detects existing user on any message:

Bot: "Привет, Иван!

Ваш статус: Активный менеджер
Email: ivan@truerealestate.bali
Календарь: Подключен ✓

Чем могу помочь?
- Обновить email
- Отключиться от системы
- Посмотреть моих клиентов"

User: "Хочу отключиться"

Bot: "Вы уверены, что хотите отключиться от системы?

Это отменит вашу регистрацию."

User: "Да"

Bot: "Хорошо, ваша регистрация отменена.

Если захотите вернуться - просто напишите мне снова."
```

**Admin Notifications (Conversational):**

```
Bot to Admin: "Новая заявка на регистрацию!

Имя: Иван Иванов
Email: ivan@truerealestate.bali
Telegram: @ivan_ivanov

Одобрить или отклонить?"

Admin: "Одобрить"

Bot: "Иван Иванов одобрен как менеджер."
Bot to User: "Отличные новости! Ваша заявка одобрена.

Теперь давайте подключим ваш Google Calendar..."
```

### 7. Implement Conversation States

- Define states as enum:
  - `IDLE` - Waiting for any message
  - `ASK_REGISTER` - Asked if want to register
  - `ASK_NAME` - Waiting for name
  - `ASK_EMAIL` - Waiting for email
  - `CONFIRM_REGISTER` - Confirm registration
  - `ASK_UNREGISTER` - Confirm unregistration
  - `ADMIN_PENDING_DECISION` - Admin reviewing application
  - `ASK_CALENDAR_CONNECT` - Ask about calendar connection
- Store conversation state in database or memory cache

### 8. Implement Calendar Connector

- Create file `src/sales_agent/registry/calendar_connector.py`
- Leverage existing OAuth pattern from `.claude/skills/google-calendar/`
- Generate unique OAuth state per registration
- Store tokens at `~/.sales_registry/calendar_tokens/{email}.json`
- Implement `generate_auth_url()` - Create OAuth URL for rep
- Implement `handle_auth_callback()` - Process OAuth response
- Implement `check_calendar_connection()` - Verify token validity
- Bot proactively asks user to connect calendar after approval

### 9. Implement Zoom Connector

- Create file `src/sales_agent/registry/zoom_connector.py`
- Use shared organizational Zoom account (simpler for Phase 1)
- Integrate with existing `ZoomBookingService`
- Add rep name to meeting topic/description

### 10. Implement Proactive Outreach Daemon

- Create file `src/sales_agent/registry/outreach_daemon.py`
- Background service that runs periodically (every 5 minutes)
- Logic:
  1. Get all "unreached" prospects without assigned rep
  2. Assign to active sales reps (round-robin)
  3. Get all "unreached" prospects with assigned rep
  4. Trigger contact through rep's Telegram account
  5. Update prospect status to "contacted"
- Integrate with existing `TelegramAgent` for message generation
- Use assigned rep's calendar for meeting scheduling

### 11. Create Bot Entry Point

- Create file `src/sales_agent/registry/run_registry_bot.py`
- Load environment variables
- Initialize database connection
- Start bot with polling
- Optionally start outreach daemon in background
- Add graceful shutdown handler
- Add to `pyproject.toml` scripts section

### 12. Update Environment Configuration

- Update `.env.example` with:

```bash
# Sales Registry Bot
REGISTRY_BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_IDS=123456789,987654321
CORPORATE_EMAIL_DOMAIN=truerealestate.bali
CALENDAR_TOKENS_PATH=~/.sales_registry/calendar_tokens

# Proactive Outreach
OUTREACH_ENABLED=true
OUTREACH_INTERVAL_MINUTES=5
```

### 13. Validate Implementation

- Test registration flow end-to-end (conversational)
- Test admin approval via conversational reply
- Test unregistration flow
- Test calendar connection
- Test prospect assignment to reps
- Test proactive outreach for unreached prospects
- Verify database migrations apply cleanly

## Testing Strategy

### Integration Tests

1. **Database Tests** (`test_sales_rep_manager.py`)
   - Test CRUD operations with real database
   - Test status transitions
   - Test email/telegram_id lookups
   - Follow ephemeral data pattern (create, test, cleanup)

2. **Prospect Manager Tests** (`test_prospect_manager.py`)
   - Test prospect assignment to reps
   - Test status updates
   - Test unreached prospect queries

3. **Bot Flow Tests** (`test_registry_bot.py`)
   - Test conversational registration flow
   - Test admin notification and response
   - Test unregistration flow
   - Mock Telegram API for unit tests

4. **Calendar Connection Tests** (`test_calendar_connector.py`)
   - Test OAuth URL generation
   - Test token storage/retrieval
   - Test token refresh

5. **Outreach Daemon Tests** (`test_outreach_daemon.py`)
   - Test prospect assignment logic
   - Test contact triggering
   - Test status updates

### Manual Testing Checklist

- [ ] Send any message to bot - bot asks about registration
- [ ] Complete registration through conversation (no commands)
- [ ] Admin receives notification and replies to approve
- [ ] User receives approval confirmation
- [ ] Bot asks user to connect calendar
- [ ] User connects Google Calendar
- [ ] Test prospect is assigned to user
- [ ] Outreach daemon contacts unreached prospect
- [ ] User says "отключиться" - bot confirms and removes

## Acceptance Criteria

1. **Conversational Registration**: Sales reps register by answering bot's questions - **no commands needed**
2. **Email Validation**: Only corporate domain emails are accepted
3. **Admin Approval**: Admins receive notification and reply conversationally to approve/reject
4. **Unregistration**: Users can say they want to unregister, bot confirms and processes
5. **Calendar Integration**: Bot proactively asks to connect calendar after approval
6. **Prospect Assignment**: Each active rep is assigned prospects
7. **Proactive Outreach**: Unreached prospects are automatically contacted via assigned rep
8. **Persistence**: All data persisted in PostgreSQL database
9. **Test Data**: 3 test prospects seeded for testing

## Validation Commands

Execute these commands to validate the task is complete:

```bash
# 1. Verify database migration applies
uv run python -c "from sales_agent.database.init import init_database; import asyncio; asyncio.run(init_database())"

# 2. Verify models import correctly
uv run python -c "from sales_agent.registry.models import SalesRepresentative, TestProspect; print('Models OK')"

# 3. Verify manager functions
uv run python -c "from sales_agent.registry.sales_rep_manager import create_sales_rep, list_all; print('Rep Manager OK')"

# 4. Verify prospect manager
uv run python -c "from sales_agent.registry.prospect_manager import get_unreached_prospects; print('Prospect Manager OK')"

# 5. Run the registry bot (will start polling)
uv run python src/sales_agent/registry/run_registry_bot.py

# 6. Test bot conversationally via Telegram:
# - Send any message to bot
# - Bot asks if you want to register
# - Answer questions naturally
# - Admin receives notification and replies
# - Say "отключиться" to unregister
```

## Notes

### Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
bot = [
    "python-telegram-bot>=21.0.0",
]
```

Note: `python-telegram-bot` is already listed as an optional dependency.

### Database Connection

Reuse existing connection pool pattern from `scheduled_action_manager.py`. Consider moving pool to centralized location in `database/__init__.py` for shared access.

### Conversational Bot Design Principles

1. **Bot initiates**: On any message, bot determines context and asks appropriate question
2. **No commands**: User never needs to type `/register` or `/status` - just natural responses
3. **Context-aware**: Bot tracks conversation state and continues from where left off
4. **Graceful handling**: Any message that doesn't fit flow gets a helpful redirect
5. **Confirmation before actions**: Always confirm destructive actions (unregister)

Example state machine:

```
ANY_MESSAGE
    ├── New user? → ASK_REGISTER → "Да/Нет"
    │                   └── "Да" → ASK_NAME → ASK_EMAIL → CONFIRM
    │                   └── "Нет" → "Окей, если передумаете - напишите"
    │
    └── Existing user? → SHOW_STATUS
            └── "Отключиться" → CONFIRM_UNREGISTER
            └── "Клиенты" → SHOW_ASSIGNED_PROSPECTS
            └── "Email" → ASK_NEW_EMAIL
```

### OAuth Callback Handling

For Google Calendar OAuth, two approaches:

1. **Manual Token Entry**: Generate auth URL, user completes OAuth, pastes code back to bot
2. **Webhook Callback**: Set up HTTP server to receive OAuth callback (requires HTTPS)

Recommend starting with Option 1 for simplicity, as it doesn't require additional server infrastructure.

### Security Considerations

1. **Admin Authorization**: Verify Telegram ID against `ADMIN_TELEGRAM_IDS` list
2. **Email Validation**: Enforce corporate domain pattern
3. **Token Storage**: Store calendar tokens outside repo, similar to existing pattern
4. **Rate Limiting**: Add rate limits to prevent abuse of registration

### Corporate Email Pattern

The email domain should be configurable via environment variable. Example validation:

```python
import re
from os import getenv

def validate_corporate_email(email: str) -> bool:
    domain = getenv("CORPORATE_EMAIL_DOMAIN", "truerealestate.bali")
    pattern = rf"^[a-zA-Z0-9._%+-]+@{re.escape(domain)}$"
    return bool(re.match(pattern, email, re.IGNORECASE))
```

### Prospect Assignment Strategy

For Phase 1, use simple round-robin assignment:

```python
async def assign_prospect_to_next_rep(prospect_id: str) -> str:
    """Assign prospect to next available rep (round-robin)."""
    active_reps = await list_active_reps()
    if not active_reps:
        return None

    # Get rep with fewest assigned prospects
    rep_counts = await get_prospect_counts_by_rep()
    next_rep = min(active_reps, key=lambda r: rep_counts.get(r.id, 0))

    await assign_prospect_to_rep(prospect_id, next_rep.id)
    return next_rep.id
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Sales Registry System                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────┐    ┌──────────────────┐                         │
│  │  Registry Bot      │    │  SalesRepManager │                         │
│  │  (Conversational)  │───▶│   (CRUD)         │                         │
│  │                    │    │  - create_rep    │                         │
│  │  User: "Привет"    │    │  - approve_rep   │                         │
│  │  Bot: "Хотите      │    │  - list_active   │                         │
│  │   зарегистрироваться?" │ └────────┬─────────┘                         │
│  └────────┬───────────┘             │                                   │
│           │                         │                                   │
│  ┌────────▼───────────┐    ┌────────▼─────────┐                         │
│  │ ConversationState  │    │  PostgreSQL      │                         │
│  │  - IDLE            │    │                  │                         │
│  │  - ASK_NAME        │    │ ┌──────────────┐ │                         │
│  │  - ASK_EMAIL       │    │ │sales_reps    │ │                         │
│  │  - CONFIRM         │    │ │- telegram_id │ │                         │
│  └────────────────────┘    │ │- email       │ │                         │
│                            │ │- status      │ │                         │
│  ┌────────────────────┐    │ └──────────────┘ │                         │
│  │ CalendarConnector  │    │                  │                         │
│  │ (Google OAuth)     │    │ ┌──────────────┐ │                         │
│  │ - auth_url         │    │ │test_prospects│ │                         │
│  │ - store_token      │    │ │- telegram_id │ │                         │
│  └────────────────────┘    │ │- status      │ │                         │
│                            │ │- assigned_rep│ │                         │
│  ┌────────────────────┐    │ └──────────────┘ │                         │
│  │ Outreach Daemon    │    └──────────────────┘                         │
│  │ (Background)       │                                                 │
│  │                    │    ┌──────────────────┐                         │
│  │ 1. Get unreached   │    │ Token Storage    │                         │
│  │ 2. Assign to rep   │    │~/.sales_registry │                         │
│  │ 3. Contact via rep │    │/calendar_tokens/ │                         │
│  │ 4. Update status   │    └──────────────────┘                         │
│  └────────────────────┘                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Future Enhancements (Out of Scope)

1. **CRM Integration**: Replace test prospects with real CRM data
2. **Per-Rep Zoom Accounts**: Each rep has their own Zoom OAuth
3. **Calendar Sync**: Two-way sync between internal calendar and Google Calendar
4. **Analytics Dashboard**: Track rep performance metrics
5. **Webhook-Based OAuth**: Full OAuth redirect flow instead of manual token entry
6. **Role-Based Access**: Fine-grained permissions beyond admin/user
7. **Lead Scoring**: Intelligent prospect assignment based on fit
