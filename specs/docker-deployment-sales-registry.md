# Implementation Plan: Docker Deployment for Sales Registry

## 1. Current State Analysis

### What Exists and Works

| Component | Status | Notes |
|-----------|--------|-------|
| `registry/models.py` | Complete | SalesRepresentative, TestProspect, UserSession, ConversationState |
| `registry/sales_rep_manager.py` | Complete | Full CRUD with asyncpg pool |
| `registry/prospect_manager.py` | Complete | Assignment, status tracking, round-robin support |
| `registry/registry_bot.py` | Complete | Conversational flow, auto-approve registration |
| `registry/run_registry_bot.py` | Complete | Entry point with graceful shutdown |
| `registry/outreach_daemon.py` | Complete | Background prospect assignment loop |
| `registry/calendar_connector.py` | Complete | Google OAuth for per-rep calendars |
| `migrations/002_sales_representatives.sql` | Complete | Table with indexes |
| `migrations/003_test_prospects.sql` | Complete | Table + 3 seed prospects |
| `daemon.py` | Complete | Single-agent Telegram daemon |
| `docker-compose.yml` | Partial | PostgreSQL + telegram-agent only |
| `Dockerfile` | Partial | Single daemon only |

### What's Missing

1. **No Docker service for registry_bot** - Bot runs standalone, not in docker-compose
2. **No Docker service for outreach_daemon** - Runs separately, not orchestrated
3. **Single Telegram account limitation** - Current architecture uses one `~/.telegram_dl/user.session`
4. **Multi-rep outreach gap** - OutreachDaemon notifies via bot but cannot message AS the rep
5. **No per-rep Telegram session management** - No way to store multiple Telethon sessions
6. **Integration gap** - Registry bot and outreach daemon don't coordinate with main daemon

---

## 2. Architecture Decision: Bot-Only Approach (Phase 1)

For local Docker testing, we use a **Bot-Only Approach**:
- Registry bot handles all communication
- Reps receive notifications, but bot sends outreach messages
- Pros: No multi-session complexity
- Cons: Messages come from "bot" not rep's account

This lets us test:
1. Rep registration
2. Prospect assignment
3. Outreach notifications
4. Basic qualification flow (via bot)

---

## 3. Docker Services Design

### Phase 1: Three-Service Architecture (MVP)

```yaml
services:
  postgres:           # Existing - no changes
  registry-bot:       # NEW - Handles rep registration
  outreach-daemon:    # NEW - Assigns prospects, triggers outreach
```

### New Service: registry-bot

```yaml
registry-bot:
  build:
    context: ../..
    dockerfile: deployment/docker/Dockerfile.registry
  container_name: registry-bot
  depends_on:
    postgres:
      condition: service_healthy
  environment:
    DATABASE_URL: postgresql://sales_agent:${POSTGRES_PASSWORD:-changeme}@postgres:5432/sales_agent
    REGISTRY_BOT_TOKEN: ${REGISTRY_BOT_TOKEN}
    CORPORATE_EMAIL_DOMAIN: ${CORPORATE_EMAIL_DOMAIN:-truerealestate.bali}
    TZ: Asia/Makassar
  env_file:
    - ../../.env
  restart: unless-stopped
  networks:
    - telegram-agent-network
```

### New Service: outreach-daemon

```yaml
outreach-daemon:
  build:
    context: ../..
    dockerfile: deployment/docker/Dockerfile.outreach
  container_name: outreach-daemon
  depends_on:
    postgres:
      condition: service_healthy
    registry-bot:
      condition: service_started
  environment:
    DATABASE_URL: postgresql://sales_agent:${POSTGRES_PASSWORD:-changeme}@postgres:5432/sales_agent
    REGISTRY_BOT_TOKEN: ${REGISTRY_BOT_TOKEN}
    OUTREACH_INTERVAL_SECONDS: ${OUTREACH_INTERVAL_SECONDS:-300}
    MAX_PROSPECTS_PER_REP: ${MAX_PROSPECTS_PER_REP:-5}
    TZ: Asia/Makassar
  env_file:
    - ../../.env
  restart: unless-stopped
  networks:
    - telegram-agent-network
```

---

## 4. Implementation Steps

### Step 1: Create Dockerfile.registry

Based on existing Dockerfile pattern:
- Entry point: `uv run python src/sales_agent/registry/run_registry_bot.py`
- Include python-telegram-bot dependency

### Step 2: Create Dockerfile.outreach

Based on existing Dockerfile pattern:
- Entry point: `uv run python src/sales_agent/registry/outreach_daemon.py`
- Same dependencies as registry bot

### Step 3: Update docker-compose.yml

Add two new services:
1. `registry-bot` - Handles Telegram bot for rep registration
2. `outreach-daemon` - Background prospect assignment

### Step 4: Update .env.example

Add new environment variables:
```bash
# Registry Bot Configuration
REGISTRY_BOT_TOKEN=your_telegram_bot_token
CORPORATE_EMAIL_DOMAIN=truerealestate.bali

# Outreach Daemon Configuration
OUTREACH_INTERVAL_SECONDS=300
MAX_PROSPECTS_PER_REP=5
OUTREACH_ENABLED=true
```

### Step 5: Ensure python-telegram-bot is installed

Update Dockerfile to use `uv sync --frozen --all-extras` or move dependency to main.

---

## 5. Testing Strategy

### Local Docker Testing Workflow

1. **Setup:**
   ```bash
   cp .env.example .env
   # Edit .env with real values (REGISTRY_BOT_TOKEN, etc.)
   ```

2. **Build:**
   ```bash
   docker-compose -f deployment/docker/docker-compose.yml build
   ```

3. **Start All Services:**
   ```bash
   docker-compose -f deployment/docker/docker-compose.yml up -d
   ```

4. **Test Registration Flow:**
   - Open Telegram, find registry bot
   - Send any message, complete registration
   - Verify: `docker exec telegram-agent-db psql -U sales_agent -c "SELECT * FROM sales_representatives;"`

5. **Test Prospect Assignment:**
   - Wait for outreach cycle (5 minutes default)
   - Check: `docker exec telegram-agent-db psql -U sales_agent -c "SELECT name, assigned_rep_id FROM test_prospects;"`

---

## 6. Acceptance Criteria

### Phase 1 Complete When:

1. **Docker Services Running:**
   - `postgres`, `registry-bot`, `outreach-daemon` all healthy
   - No crashes or error loops

2. **Registration Flow Works:**
   - New Telegram user can complete registration
   - User stored in database with status=active

3. **Prospect Assignment Works:**
   - Outreach daemon assigns unreached prospects to active reps
   - Rep receives Telegram notification about new prospect

4. **Local Docker Testing:**
   - `docker-compose up -d` starts all services
   - Data persists across restarts

---

## 7. File Changes Summary

### New Files to Create:

| File | Purpose |
|------|---------|
| `deployment/docker/Dockerfile.registry` | Registry bot container |
| `deployment/docker/Dockerfile.outreach` | Outreach daemon container |

### Files to Modify:

| File | Changes |
|------|---------|
| `deployment/docker/docker-compose.yml` | Add registry-bot and outreach-daemon services |
| `.env.example` | Add REGISTRY_BOT_TOKEN, OUTREACH_* variables |

---

## Critical Files for Implementation

- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/deployment/docker/docker-compose.yml` - Add registry-bot and outreach-daemon services
- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/deployment/docker/Dockerfile` - Reference pattern for new Dockerfiles
- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/run_registry_bot.py` - Entry point for registry-bot service
- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/src/sales_agent/registry/outreach_daemon.py` - Entry point for outreach-daemon service
- `/Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier/.env.example` - Add environment variables
