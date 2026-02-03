---
name: database
description: PostgreSQL database management and migrations. Use for initializing the database, running schema migrations, or troubleshooting database connectivity issues.
---

# Database Management

PostgreSQL initialization and schema migrations for the sales agent system. This skill provides commands for setting up the database, running migrations, and understanding the schema structure.

## Prerequisites

- PostgreSQL database running (NeonDB recommended for production)
- `DATABASE_URL` environment variable set in `.env` file

```
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
```

## Usage

### Initialize Database and Run All Migrations

Run this command to verify database connectivity and apply all pending migrations:

```bash
PYTHONPATH=src uv run python src/sales_agent/database/init.py
```

This performs:
1. Verifies `DATABASE_URL` is set
2. Tests database connectivity with timeout
3. Scans `src/sales_agent/migrations/` for `.sql` files
4. Applies any pending migrations in alphabetical order
5. Records applied migrations in `schema_migrations` table

The init script is **idempotent** - safe to run multiple times. Already-applied migrations are skipped automatically.

### Run Migrations Manually (psql)

Individual migrations can be applied directly via `psql`:

```bash
psql $DATABASE_URL -f src/sales_agent/migrations/001_scheduled_actions.sql
```

## Migration System

### Migration Numbering Convention

Migrations use a numbered prefix format: `NNN_description.sql`

- **001-004**: Core tables (scheduled_actions, sales_representatives, test_prospects, sessions)
- **005-006**: Schema enhancements (processing status, test results)
- Future migrations: Continue with `007_`, `008_`, etc.

Migrations are applied in **alphabetical order** by filename, so the numbered prefix ensures correct ordering.

### Schema Tracking

Applied migrations are tracked in the `schema_migrations` table:

```sql
SELECT * FROM schema_migrations ORDER BY applied_at;
```

## Database Schema Overview

### Core Tables

| Table | Purpose | Created By |
|-------|---------|------------|
| `scheduled_actions` | Follow-up actions, reminders, delayed messages | 001 |
| `sales_representatives` | Sales rep registry with profile and status | 002 |
| `test_prospects` | Test leads for training and validation | 003 |
| `test_results` | Automated stress test results | 006 |
| `test_assessments` | Detailed quality assessments for tests | 006 |
| `schema_migrations` | Migration tracking (auto-created) | init.py |

## Migration Details

### 001_scheduled_actions.sql

**Purpose**: Creates the `scheduled_actions` table for storing delayed actions (follow-ups, reminders, pre-meeting notifications).

**Key Columns**:
- `id` (UUID): Primary key
- `prospect_id` (VARCHAR): Telegram ID of prospect
- `action_type` (VARCHAR): Type: `follow_up`, `reminder`, `pre_meeting`
- `scheduled_for` (TIMESTAMPTZ): When to execute (UTC)
- `status` (VARCHAR): `pending`, `processing`, `executed`, `cancelled`
- `payload` (JSONB): Action-specific data (message template, context)

**Indexes**:
- `idx_scheduled_actions_prospect`: Fast lookup by prospect_id
- `idx_scheduled_actions_pending`: Partial index for pending jobs

---

### 002_sales_representatives.sql

**Purpose**: Creates the `sales_representatives` table for managing sales team registration via the Registry Bot.

**Key Columns**:
- `id` (UUID): Primary key
- `telegram_id` (BIGINT): Telegram user ID (unique)
- `telegram_username` (VARCHAR): @username without @
- `name` (VARCHAR): Full name
- `email` (VARCHAR): Corporate email
- `status` (VARCHAR): `pending`, `active`, `suspended`, `removed`
- `is_admin` (BOOLEAN): Admin privileges flag
- `calendar_account_name` (VARCHAR): Google Calendar account

**Indexes**:
- `idx_sales_reps_telegram_id`: Fast lookup by Telegram ID
- `idx_sales_reps_status`: Filter by status

---

### 003_test_prospects.sql

**Purpose**: Creates the `test_prospects` table for assigning test leads to sales reps for practice and validation. Includes seed data with 3 test prospects.

**Key Columns**:
- `id` (VARCHAR): String ID (e.g., `test_001`)
- `telegram_id` (VARCHAR): @username of prospect
- `name` (VARCHAR): Full name
- `context` (TEXT): Background on prospect interest
- `status` (VARCHAR): `unreached`, `contacted`, `in_conversation`, `converted`, `archived`
- `assigned_rep_id` (UUID): FK to sales_representatives

**Seed Data**: 3 Russian-speaking test prospects with varying buyer profiles.

---

### 004_sales_rep_sessions.sql

**Purpose**: Adds columns to `sales_representatives` for multi-account Telegram support and per-rep calendar tracking.

**Added Columns**:
- `telegram_phone` (VARCHAR): Phone used for Telethon auth
- `telegram_session_name` (VARCHAR): Session file name (maps to `~/.telegram_dl/sessions/{name}.session`)
- `telegram_session_ready` (BOOLEAN): Whether auth succeeded
- `agent_name` (VARCHAR): Display name for agent messages
- `calendar_connected` (BOOLEAN): Whether Google Calendar OAuth is complete

---

### 005_add_processing_status.sql

**Purpose**: Adds support for `processing` status in scheduled_actions to prevent duplicate execution with the polling daemon.

**Added Columns**:
- `started_processing_at` (TIMESTAMPTZ): When action entered processing status (for timeout detection)

**Added Indexes**:
- `idx_scheduled_actions_polling`: Partial index for `pending` and `processing` actions

**Use Case**: The polling daemon uses row-level locking (`SELECT ... FOR UPDATE SKIP LOCKED`) and this status enables detection of stale/stuck actions for recovery.

---

### 006_test_results.sql

**Purpose**: Creates tables for storing automated stress test results and quality assessments.

**Tables Created**:

**`test_results`**: Stores complete results from each automated conversation test.
- `scenario_name` (VARCHAR): Test scenario name
- `persona_id` (VARCHAR): Simulated persona identifier
- `outcome` (VARCHAR): `zoom_scheduled`, `follow_up_proposed`, `client_refused`, `escalated`, `inconclusive`
- `overall_score` (INTEGER): Quality score 0-100
- `total_turns` (INTEGER): Conversation turn count
- `call_scheduled` (BOOLEAN): Key success metric

**`test_assessments`**: Detailed quality assessments linked to test results.
- `personalization_score`, `questions_score`, `value_first_score` (0-10 each)
- `bant_coverage` (JSONB): Budget/Authority/Need/Timeline discovery tracking
- `zmeyka_adherence`, `objection_handling` (0-10)
- Quality checks: `zoom_close_attempt`, `message_length_appropriate`, `formal_language`, `no_forbidden_topics`

## Troubleshooting

### Connection Errors

```
RuntimeError: DATABASE_URL environment variable is not set
```
**Fix**: Add `DATABASE_URL` to your `.env` file.

```
Cannot connect to database server
```
**Fix**: Verify host/port in DATABASE_URL, check network connectivity, ensure database server is running.

### Migration Errors

```
Migration XXX_name.sql failed: relation already exists
```
**Fix**: Migration was partially applied. Check `schema_migrations` table and manually add the migration name if the schema is correct.

### Viewing Applied Migrations

```sql
-- Check what migrations have been applied
SELECT * FROM schema_migrations ORDER BY applied_at;

-- Check table structure
\d+ scheduled_actions
\d+ sales_representatives
```

## Architecture Notes

- **Daemon Integration**: `init_database()` is called during daemon startup in `daemon.py`
- **Async Support**: All database operations use `asyncpg` for async PostgreSQL access
- **Transaction Safety**: Each migration runs in a transaction for atomicity
- **Rich Output**: Uses Rich library for formatted console output
- **NeonDB Compatible**: Designed for NeonDB serverless PostgreSQL

## Programmatic Usage

```python
from sales_agent.database import init_database

# In your daemon's initialize() method:
await init_database()
```

Or import specific functions:

```python
from sales_agent.database.init import (
    check_database_connection,
    run_migrations,
    get_applied_migrations,
)

# Check connectivity
if await check_database_connection():
    applied = await run_migrations()
    print(f"Applied {applied} migrations")
```
