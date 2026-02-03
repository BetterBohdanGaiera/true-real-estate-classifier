# Plan: Docker Deployment with Registered Sales Representatives - Local Testing E2E

## Task Description
Deploy the full sales agent system via Docker where registered sales representatives can receive Telegram messages from prospects and respond using AI-powered tone-of-voice and communication methodology. The system must handle Google Calendar availability checking and Zoom meeting scheduling. Before Docker deployment, we must validate the entire flow locally end-to-end.

## Objective
When this plan is complete:
1. A registered sales representative's Telegram account will be running as a daemon inside Docker
2. When a prospect sends a message to this rep's Telegram, the AI agent responds following all tone-of-voice and communication guidelines
3. The agent can check Google Calendar availability and schedule Zoom meetings
4. The entire flow is first validated locally before Docker deployment

## Problem Statement
The codebase has all the individual components built (Telegram daemon, AI agent with tone-of-voice skills, Google Calendar connector, Zoom service, sales rep registry, Docker compose stack). However, the end-to-end flow of a **registered sales rep** receiving and responding to messages with full AI capabilities has not been tested locally, and the Docker deployment needs adjustments to support per-rep mode with calendar and Zoom integration.

Currently:
- The daemon supports `--rep-telegram-id` for per-rep mode (`daemon.py:72,843-850`)
- Sales rep registration exists (`register_rep.py`) with Telegram session, Calendar OAuth, Zoom verification
- Docker compose runs 4 services but the telegram-agent only uses the default `user.session`
- Calendar connector has per-rep token storage but isn't wired into the scheduling tool
- The scheduling tool uses mock slots (`sales_calendar.py`) instead of real Google Calendar availability

## Solution Approach
Phase the work into three stages:
1. **Local Testing First**: Register a test sales rep, validate Telegram session, Calendar OAuth, and Zoom credentials locally
2. **Wire Real Calendar into Scheduling**: Integrate `CalendarConnector.get_busy_slots()` with `SchedulingTool` so meeting slots respect real Google Calendar availability
3. **Docker Deployment**: Update Docker compose to support per-rep daemon instances with proper credential mounting

## Relevant Files
Use these files to complete the task:

### Core Daemon & Agent
- `src/sales_agent/daemon.py` - Main daemon with per-rep mode support (line 72: `rep_telegram_id` param, lines 111-129: per-rep initialization)
- `src/sales_agent/agent/telegram_agent.py` - AI agent with system prompt, skill loading, and action routing
- `src/sales_agent/agent/knowledge_loader.py` - Topic-based knowledge injection

### Telegram Session Management
- `src/sales_agent/telegram/telegram_fetch.py` - `get_client_for_rep()` (lines 118-155), `create_session()` (lines 158-193)
- `src/sales_agent/telegram/telegram_service.py` - Human-like message delivery with delays

### Sales Rep Registration
- `.claude/skills/register-sales/scripts/register_rep.py` - 5-step registration flow
- `.claude/skills/register-sales/scripts/setup_calendar.py` - Google Calendar OAuth setup
- `.claude/skills/register-sales/scripts/verify_zoom.py` - Zoom credential verification
- `.claude/skills/register-sales/scripts/list_reps.py` - List registered reps
- `src/sales_agent/registry/sales_rep_manager.py` - Database CRUD for sales reps
- `src/sales_agent/registry/models.py` - Pydantic models for SalesRepresentative

### Calendar & Scheduling
- `src/sales_agent/registry/calendar_connector.py` - Per-rep Google Calendar OAuth and availability checking
- `src/sales_agent/scheduling/sales_calendar.py` - Mock slot generation (needs real calendar integration)
- `src/sales_agent/scheduling/scheduling_tool.py` - Meeting booking with Zoom integration
- `src/sales_agent/config/sales_slots.json` - Working hours and timezone config

### Zoom Integration
- `src/sales_agent/zoom/zoom_service.py` - Server-to-Server OAuth, meeting creation
- `src/sales_agent/zoom/__init__.py` - ZoomBookingService export

### Tone of Voice & Communication
- `.claude/skills/tone-of-voice/SKILL.md` - 7 core communication principles
- `.claude/skills/tone-of-voice/references/` - Phrase templates, structures, case scripts (RU/EN)
- `.claude/skills/how-to-communicate/SKILL.md` - 13 communication principles, Zmeyka/BANT methodology
- `.claude/skills/how-to-communicate/references/` - Objection scripts, lead classes, success patterns

### Docker Deployment
- `deployment/docker/docker-compose.yml` - 4-service stack (postgres, telegram-agent, registry-bot, outreach-daemon)
- `deployment/docker/Dockerfile` - Main daemon Dockerfile
- `deployment/docker/Dockerfile.registry` - Registry bot Dockerfile
- `deployment/docker/Dockerfile.outreach` - Outreach daemon Dockerfile
- `.dockerignore` - Build context exclusions (has `.md` exclusion bug)

### Database
- `src/sales_agent/migrations/002_sales_representatives.sql` - Sales reps table
- `src/sales_agent/migrations/004_sales_rep_sessions.sql` - Session columns (telegram_phone, session_name, session_ready, agent_name, calendar_connected)
- `src/sales_agent/database/` - Database initialization and connection management

### Configuration
- `.env.example` - All environment variables (missing POSTGRES_PASSWORD, ZOOM credentials)
- `src/sales_agent/config/agent_config.json` - Agent identity and settings
- `src/sales_agent/config/prospects.json` - Prospect list (currently empty)

### New Files
- `src/sales_agent/scheduling/calendar_aware_scheduler.py` - Bridge between CalendarConnector and SchedulingTool for real availability
- `deployment/docker/docker-compose.per-rep.yml` - Docker compose override for per-rep daemon instances

## Implementation Phases

### Phase 1: Foundation - Local Environment Setup & Rep Registration
Set up local environment with database, register a test sales rep with Telegram session, Google Calendar OAuth, and Zoom credentials. Validate each integration independently.

### Phase 2: Core Implementation - Wire Real Calendar & Fix Integration Gaps
Integrate CalendarConnector with SchedulingTool so availability reflects real Google Calendar. Fix `.env.example` gaps, fix `.dockerignore` `.md` exclusion bug, and ensure per-rep daemon mode works end-to-end locally.

### Phase 3: Integration & Polish - Docker Deployment & E2E Validation
Update Docker compose for per-rep mode, fix Docker-specific issues (non-root user, startup optimization), and validate the full flow in Docker containers.

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

### 1. Verify Local Environment Prerequisites
- Ensure `.env` file exists with `ANTHROPIC_API_KEY`, `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Verify Zoom credentials exist at `~/.zoom_credentials/credentials.json` with `account_id`, `client_id`, `client_secret`
- Verify Telegram config exists at `~/.telegram_dl/config.json` with `api_id` and `api_hash`
- Run `uv sync` to ensure all dependencies installed
- Run database migrations:
  ```bash
  psql $DATABASE_URL -f src/sales_agent/migrations/001_scheduled_actions.sql
  psql $DATABASE_URL -f src/sales_agent/migrations/002_sales_representatives.sql
  psql $DATABASE_URL -f src/sales_agent/migrations/003_test_prospects.sql
  psql $DATABASE_URL -f src/sales_agent/migrations/004_sales_rep_sessions.sql
  ```

### 2. Register a Test Sales Representative
- Run the registration script:
  ```bash
  PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/register_rep.py
  ```
- Provide: Name, email, phone number for the test rep's Telegram account
- Complete Telegram phone verification (enter OTP code)
- Complete Google Calendar OAuth (open browser, authorize, paste code)
- Verify Zoom credentials
- Confirm rep saved to database
- Verify with:
  ```bash
  PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/list_reps.py
  ```

### 3. Add Test Prospect to prospects.json
- Add `@bohdanpytaichuk` (Telegram ID: 7836623698) as a prospect in `src/sales_agent/config/prospects.json` with status `"new"`
- This ensures the daemon knows to respond to messages from the test prospect
- Format:
  ```json
  {
    "prospects": [
      {
        "telegram_id": 7836623698,
        "username": "@bohdanpytaichuk",
        "name": "Богдан",
        "status": "new",
        "conversation_history": []
      }
    ]
  }
  ```

### 4. Test Per-Rep Daemon Locally (Without Calendar Integration)
- Get the registered rep's Telegram ID from the database
- Start the daemon in per-rep mode:
  ```bash
  PYTHONPATH=src uv run python src/sales_agent/daemon.py --rep-telegram-id <REP_TELEGRAM_ID>
  ```
- Verify:
  - Daemon starts without errors
  - Shows "Per-rep mode: <name> (@<username>)"
  - Telegram connected to the correct account
  - Claude agent initialized with tone-of-voice + how-to-communicate + knowledge base
- Send a test message from `@bohdanpytaichuk` to the rep's Telegram account
- Verify the AI responds following tone-of-voice guidelines (short, 1-3 sentences, formal "Вы")
- Test scheduling: ask about meeting availability, verify mock slots are shown
- Test follow-up: verify `schedule_followup` tool works

### 5. Create Calendar-Aware Scheduling Bridge
- Create `src/sales_agent/scheduling/calendar_aware_scheduler.py` that:
  - Takes a `CalendarConnector` and a rep's `telegram_id`
  - Provides `get_available_slots()` that returns slots from working hours MINUS Google Calendar busy slots
  - Falls back to mock slots if calendar not connected
- Wire this into `SchedulingTool.__init__()` as an optional `calendar_connector` parameter
- When `calendar_connector` is provided and rep has calendar connected:
  - `get_available_times()` filters out busy slots from Google Calendar
  - Returns only genuinely free time slots
- When not provided: falls back to existing mock slot behavior (backward compatible)

### 6. Wire Calendar Connector into Per-Rep Daemon
- In `daemon.py`, when in per-rep mode and rep has `calendar_connected=True`:
  - Initialize `CalendarConnector` with env vars
  - Pass it to `SchedulingTool` constructor
  - Log: "Real calendar integration enabled for <rep_name>"
- When calendar not connected: use existing mock slots, log warning

### 7. Test Calendar-Integrated Scheduling Locally
- Start per-rep daemon with calendar integration
- Send message from test prospect: "Хочу записаться на консультацию"
- Verify:
  - Shown availability reflects REAL Google Calendar (busy slots excluded)
  - Agent asks for email before booking
  - After providing email and selecting slot, Zoom meeting is created
  - Confirmation message includes Zoom link
- Test edge case: when all working hour slots are busy on Calendar

### 8. Fix .env.example - Add Missing Variables
- Add `POSTGRES_PASSWORD` under Docker Deployment section
- Add Zoom credentials section:
  ```
  # Zoom Integration (optional)
  # Credentials stored at ~/.zoom_credentials/credentials.json
  # ZOOM_ACCOUNT_ID=your_zoom_account_id
  # ZOOM_CLIENT_ID=your_zoom_client_id
  # ZOOM_CLIENT_SECRET=your_zoom_client_secret
  ```

### 9. Fix .dockerignore - Allow .md Files in Knowledge Base and Skills
- Change the `.md` exclusion from a blanket `*.md` to more targeted exclusions:
  ```
  # Exclude docs but keep knowledge base and skill references
  /docs/*.md
  /specs/*.md
  /follow_up.md
  CHANGELOG.md
  CONTRIBUTING.md
  LICENSE.md
  # Keep: knowledge_base_final/*.md, .claude/skills/**/*.md, CLAUDE.md
  ```
- This ensures Docker images built standalone (without compose volume mounts) contain the knowledge base and skill references

### 10. Update Docker Compose for Per-Rep Mode
- Add environment variable `REP_TELEGRAM_ID` to the telegram-agent service:
  ```yaml
  environment:
    REP_TELEGRAM_ID: ${REP_TELEGRAM_ID:-}
  ```
- Update the CMD in Dockerfile to support optional `--rep-telegram-id`:
  - Option A: Use an entrypoint script that conditionally adds the flag
  - Option B: Override command in docker-compose.yml:
    ```yaml
    command: >
      sh -c "if [ -n '$$REP_TELEGRAM_ID' ]; then
        python src/sales_agent/daemon.py --rep-telegram-id $$REP_TELEGRAM_ID;
      else
        python src/sales_agent/daemon.py;
      fi"
    ```
- Mount per-rep Telegram sessions:
  ```yaml
  volumes:
    - ${HOME}/.telegram_dl:/root/.telegram_dl:rw
    # Mount Google Calendar tokens for per-rep calendar integration
    - ${HOME}/.sales_registry:/root/.sales_registry:ro
  ```

### 11. Fix Docker Build Issues
- In `deployment/docker/Dockerfile`:
  - Remove redundant `COPY src/sales_agent/migrations/` (line 87) - already in `COPY src/`
  - Change `CMD ["uv", "run", "python", ...]` to `CMD ["python", "src/sales_agent/daemon.py"]` (venv is already on PATH)
  - Uncomment non-root user creation (lines 92-95), ensure `/root/.telegram_dl` and `/root/.sales_registry` are accessible
- Apply same fixes to `Dockerfile.registry` and `Dockerfile.outreach`

### 12. Build and Test Docker Deployment
- Build images:
  ```bash
  docker-compose -f deployment/docker/docker-compose.yml build
  ```
- Verify knowledge base files are present in image:
  ```bash
  docker run --rm telegram-agent ls -la /app/knowledge_base_final/
  docker run --rm telegram-agent ls -la /app/.claude/skills/tone-of-voice/references/
  ```
- Start stack with per-rep mode:
  ```bash
  REP_TELEGRAM_ID=<id> POSTGRES_PASSWORD=securepass docker-compose -f deployment/docker/docker-compose.yml up -d
  ```
- Verify all services healthy:
  ```bash
  docker-compose -f deployment/docker/docker-compose.yml ps
  docker-compose -f deployment/docker/docker-compose.yml logs -f telegram-agent
  ```

### 13. E2E Validation in Docker
- From `@bohdanpytaichuk` Telegram account, send a message to the registered rep's account
- Verify:
  - AI responds within reasonable time (2-15 seconds depending on message length)
  - Response follows tone-of-voice (short, 1-3 sentences, formal "Вы", no em-dashes)
  - Agent uses BANT/Zmeyka methodology to qualify the prospect
  - When prospect asks about meeting, shows real calendar availability
  - Email is required before booking
  - Zoom meeting link is included in confirmation
  - Follow-up scheduling works (agent schedules and sends delayed follow-ups)
- Test escalation: send message with escalation keyword ("позвони")
- Test language: send message in English, verify agent responds appropriately

### 14. Validate Final State
- Run `docker-compose ps` to verify all 4 services running
- Check logs for any errors: `docker-compose logs --tail=50`
- Run list_reps to verify database state:
  ```bash
  PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/list_reps.py
  ```
- Verify scheduled follow-ups persist in database after container restart:
  ```bash
  docker-compose restart telegram-agent
  # Follow-ups should recover from database after restart
  ```

## Testing Strategy

### Unit Tests
- Test `calendar_aware_scheduler.py` with mocked busy slots to verify filtering logic
- Test `.dockerignore` fix by building image and verifying file presence

### Integration Tests
- Test `CalendarConnector.get_busy_slots()` returns real events from Google Calendar
- Test `ZoomBookingService.create_meeting()` creates a real Zoom meeting
- Test per-rep daemon initialization with database-stored rep data

### E2E Tests (Manual)
1. **Happy Path**: Prospect messages rep → AI responds → asks about needs → suggests meeting → prospect provides email → books meeting → Zoom link sent
2. **Follow-up Path**: Prospect doesn't respond → AI schedules follow-up → follow-up sent after delay
3. **Escalation Path**: Prospect asks to call → agent escalates
4. **Calendar Conflict**: All slots busy → agent communicates unavailability
5. **Docker Restart**: Container restarts → pending follow-ups recover from DB

## Acceptance Criteria
- [ ] A registered sales rep's Telegram account responds to incoming messages via AI
- [ ] AI responses follow tone-of-voice guidelines (short, formal, no em-dashes)
- [ ] AI uses BANT/Zmeyka qualification methodology
- [ ] Meeting availability reflects real Google Calendar (busy slots excluded)
- [ ] Zoom meeting links are created and included in booking confirmations
- [ ] Follow-up messages are scheduled and delivered automatically
- [ ] All services run in Docker containers with proper health checks
- [ ] `.dockerignore` allows knowledge base and skill `.md` files in the image
- [ ] `.env.example` documents all required variables including POSTGRES_PASSWORD
- [ ] Docker containers restart gracefully and recover scheduled actions from database
- [ ] Per-rep mode works both locally (`--rep-telegram-id`) and in Docker (`REP_TELEGRAM_ID` env var)

## Validation Commands
Execute these commands to validate the task is complete:

- `uv sync` - Verify all dependencies install
- `PYTHONPATH=src uv run python -c "from sales_agent.daemon import TelegramDaemon; print('OK')"` - Verify daemon imports
- `PYTHONPATH=src uv run python -c "from sales_agent.scheduling.calendar_aware_scheduler import CalendarAwareScheduler; print('OK')"` - Verify new calendar bridge imports
- `PYTHONPATH=src uv run python .claude/skills/register-sales/scripts/list_reps.py` - Verify reps in database
- `docker-compose -f deployment/docker/docker-compose.yml build` - Verify Docker images build
- `docker run --rm telegram-agent ls /app/knowledge_base_final/` - Verify knowledge base in Docker image
- `docker run --rm telegram-agent ls /app/.claude/skills/tone-of-voice/references/` - Verify skill references in Docker image
- `docker-compose -f deployment/docker/docker-compose.yml ps` - Verify all services running
- `docker-compose -f deployment/docker/docker-compose.yml logs --tail=20 telegram-agent` - Verify no errors in agent logs

## Notes
- **Interactive Registration**: The `register_rep.py` script requires interactive terminal input for Telegram phone verification and Google Calendar OAuth. It cannot be automated without additional work.
- **Telegram Session Files**: Sessions at `~/.telegram_dl/sessions/` contain authentication tokens. These MUST be mounted as read-write volumes in Docker since Telethon updates session files.
- **Google Calendar Tokens**: Stored at `~/.sales_registry/calendar_tokens/{telegram_id}.json`. Must be mounted in Docker containers.
- **Zoom Shared Account**: Zoom uses Server-to-Server OAuth with a single shared account. All reps create meetings under the same Zoom account.
- **python-telegram-bot Dependency**: The `registry-bot` and `outreach-daemon` services require the `[bot]` optional dependency. Their Dockerfiles use `uv sync --frozen --no-dev --all-extras` to include it.
- **Timezone**: All scheduling uses `Asia/Makassar` (UTC+8, Bali time). This is set via `TZ` environment variable in Docker compose.
- **New Library**: No new libraries needed. `CalendarConnector` already exists in `src/sales_agent/registry/calendar_connector.py`.
- **Backward Compatibility**: The calendar-aware scheduling is opt-in. When no `calendar_connector` is provided, the existing mock slot behavior is preserved.
