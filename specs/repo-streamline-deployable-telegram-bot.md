# Plan: Streamline & Refactor Repo into Deployable Telegram Sales Bot

## Task Description
Refactor the entire repository from a fragmented `.claude/skills/`-based architecture into a clean, deployable Telegram sales bot with Google Calendar, Zoom, scheduling, tone-of-voice, and knowledge base integrations. The current code is scattered across 23+ Claude Code skills directories, with massive code duplication, dead code, `sys.path` hacking, JSON-file state management, and broken Docker configs. The end goal is a single deployable Python package.

## Objective
Transform the codebase into a proper Python package (`src/telegram_sales_bot/`) that can be deployed via Docker with `uv run` -- no Claude Code skill infrastructure, no `sys.path` manipulation, no JSON-file state, proper package imports, and a working Docker deployment.

## Problem Statement
The bot currently works but is fragile and undeployable due to:

1. **No proper Python package** -- Code lives in `.claude/skills/telegram/scripts/` with `sys.path` hacking to reach 7 sibling skill directories
2. **Massive code duplication** -- 4 files duplicated between `scheduling/` and `telegram/` skills (diverged versions), 5 files duplicated between `telegram/` and `testing/` skills
3. **Dead code** -- 5+ unused modules (~2,140 lines): `run_daemon.py`, `context_summarizer.py`, `fact_extractor.py`, `email_validator.py`, `timezone_calculator.py`, `bot_send.py`
4. **JSON-file state** -- `prospects.json` and `sales_slots_data.json` hold mutable runtime state in config directories (no concurrency, no scaling)
5. **Broken Docker configs** -- `Dockerfile.registry` and `Dockerfile.outreach` copy non-existent `src/` directory, inconsistent PYTHONPATH, `.dockerignore` excludes needed skills
6. **Wrong scheduling architecture** -- Daemon uses in-memory APScheduler (loses state on restart) while a Docker-safe polling daemon was built but never wired in
7. **SQL injection** -- `scheduled_action_manager.py` uses string interpolation for SQL INTERVAL
8. **Hardcoded paths** -- `bot_send.py` has `/Users/server/...` paths, `telegram_fetch.py` has personal Obsidian vault path
9. **Unrelated code** -- `adws/`, `scripts/`, 10 developer-tool skills (PDF, DOCX, video, etc.) bloat the repo
10. **10 developer-tool skills** polluting the project that have nothing to do with the bot

## Solution Approach
Three-phase refactoring:
1. **Phase 1: Clean** -- Remove dead code, unrelated directories, duplicate files
2. **Phase 2: Extract** -- Create proper `src/telegram_sales_bot/` Python package from scattered skills
3. **Phase 3: Deploy** -- Fix Docker configuration, adopt polling-based scheduler, migrate JSON state to PostgreSQL

## Relevant Files

### Core Bot Files (to extract into package)
- `.claude/skills/telegram/scripts/daemon.py` -- Main bot runner (1000+ lines), orchestrates everything
- `.claude/skills/telegram/scripts/telegram_agent.py` -- Claude AI agent, builds prompts, parses responses (825 lines)
- `.claude/skills/telegram/scripts/telegram_service.py` -- Telethon wrapper with humanized sending (355 lines)
- `.claude/skills/telegram/scripts/telegram_fetch.py` -- Telethon client creation and entity resolution (1015 lines, needs splitting)
- `.claude/skills/telegram/scripts/models.py` -- All Pydantic models (361 lines, single source of truth)
- `.claude/skills/telegram/scripts/prospect_manager.py` -- JSON-based prospect CRM (559 lines, needs DB migration)
- `.claude/skills/telegram/scripts/knowledge_loader.py` -- Topic detection and knowledge loading (353 lines)
- `.claude/skills/telegram/scripts/message_buffer.py` -- Message batching with debounce (423 lines)
- `.claude/skills/telegram/scripts/pause_detector.py` -- Conversation gap detection (283 lines)
- `.claude/skills/telegram/scripts/timezone_detector.py` -- Client timezone estimation (237 lines)
- `.claude/skills/telegram/scripts/phrase_tracker.py` -- Anti-repetition tracking (176 lines)
- `.claude/skills/telegram/scripts/scheduling_tool.py` -- Meeting booking orchestrator (963 lines, AUTHORITATIVE version)
- `.claude/skills/telegram/scripts/sales_calendar.py` -- Slot generation and booking (479 lines)
- `.claude/skills/telegram/scripts/scheduled_action_manager.py` -- DB CRUD for scheduled actions (539 lines, needs enhancement)

### Scheduling (consolidate from scheduling skill)
- `.claude/skills/scheduling/scripts/scheduler_service.py` -- Docker-safe polling-based scheduler (399 lines, BETTER version)
- `.claude/skills/scheduling/scripts/followup_polling_daemon.py` -- Database polling loop (362 lines, UNIQUE)
- `.claude/skills/scheduling/scripts/calendar_aware_scheduler.py` -- Google Calendar slot filtering (247 lines, UNIQUE)
- `.claude/skills/scheduling/scripts/scheduled_action_manager.py` -- Enhanced with row-level locking (707 lines, has `claim_due_actions`)

### External Integrations (to consolidate)
- `.claude/skills/zoom/scripts/zoom_service.py` -- Zoom meeting creation (USED by bot)
- `.claude/skills/register-sales/scripts/calendar_connector.py` -- Per-rep Google Calendar OAuth (USED by bot)
- `.claude/skills/register-sales/scripts/sales_rep_manager.py` -- Sales rep DB CRUD (USED by registry bot)
- `.claude/skills/register-sales/scripts/registry_models.py` -- Registry Pydantic models
- `.claude/skills/register-sales/scripts/registry_bot.py` -- Registry Telegram bot
- `.claude/skills/register-sales/scripts/outreach_daemon.py` -- Prospect assignment daemon
- `.claude/skills/register-sales/scripts/run_registry_bot.py` -- Registry entry point
- `.claude/skills/register-sales/scripts/test_prospect_manager.py` -- DB-backed prospect CRUD
- `.claude/skills/humanizer/scripts/natural_timing.py` -- Response timing (216 lines)
- `.claude/skills/humanizer/scripts/typo_injector.py` -- Optional typo injection (146 lines)
- `.claude/skills/eleven-labs/scripts/voice_transcriber.py` -- Voice message transcription
- `.claude/skills/database/scripts/init.py` -- Database init and migration runner

### Knowledge & Tone (to include as data)
- `.claude/skills/tone-of-voice/` -- 8 communication principles, 230+ phrase templates
- `.claude/skills/how-to-communicate/` -- Sales methodology (Zmeyeka, BANT, objection scripts)
- `knowledge_base_final/` -- 12 structured topic files for context injection

### Config & Deployment
- `deployment/docker/Dockerfile` -- Main agent Dockerfile (needs fixing)
- `deployment/docker/docker-compose.yml` -- Multi-service Docker composition
- `deployment/docker/Dockerfile.registry` -- Registry bot (BROKEN, copies non-existent src/)
- `deployment/docker/Dockerfile.outreach` -- Outreach daemon (BROKEN, same issue)
- `.dockerignore` -- Excludes google-calendar but docker-compose mounts it
- `pyproject.toml` -- Dependencies (needs python-telegram-bot in core)
- `.claude/skills/database/migrations/` -- 7 SQL migration files

### Dead Code (to remove)
- `.claude/skills/telegram/scripts/run_daemon.py` -- Superseded by daemon.py
- `.claude/skills/telegram/scripts/context_summarizer.py` -- Not imported anywhere
- `.claude/skills/telegram/scripts/fact_extractor.py` -- Not imported anywhere
- `.claude/skills/telegram/scripts/email_validator.py` -- Duplicate of scheduling_tool.py
- `.claude/skills/telegram/scripts/timezone_calculator.py` -- Only used in tests
- `.claude/skills/telegram/scripts/bot_send.py` -- Legacy with hardcoded paths to different machine
- `.claude/skills/telegram/scripts/conversation_simulator.py` -- Duplicate (testing/ has newer)
- `.claude/skills/telegram/scripts/conversation_evaluator.py` -- Duplicate
- `.claude/skills/telegram/scripts/test_scenarios.py` -- Duplicate
- `.claude/skills/telegram/scripts/run_conversation_tests.py` -- Duplicate
- `.claude/skills/telegram/scripts/test_scheduled_actions.py` -- Duplicate
- `scripts/run_migrations.py` -- Points to non-existent `src/sales_agent/migrations/`

### Unrelated Directories (to remove from repo)
- `adws/` -- Completely independent AI Developer Workflows framework
- `scripts/` -- Standalone knowledge extraction pipeline (except run_migrations.py which is stale)
- `.claude/skills/pdf/`, `docx/`, `video-processor/`, `video-analysis/`, `brand-agency/`, `meta-skill/`, `cloudflare-manager/`, `fork-terminal/`, `fetching-library-docs/`, `frontend-design/` -- Developer tools, not bot code

### New Files
- `src/telegram_sales_bot/__init__.py` -- Clean package init
- `src/telegram_sales_bot/core/` -- daemon, agent, service, models
- `src/telegram_sales_bot/scheduling/` -- Consolidated scheduling with polling daemon
- `src/telegram_sales_bot/integrations/` -- Zoom, Google Calendar, ElevenLabs
- `src/telegram_sales_bot/temporal/` -- Message buffer, pause detection, timezone
- `src/telegram_sales_bot/knowledge/` -- Knowledge loader, tone-of-voice data
- `src/telegram_sales_bot/registry/` -- Sales rep registration subsystem
- `src/telegram_sales_bot/cli/` -- Setup utilities, telegram fetch CLI

## Implementation Phases

### Phase 1: Foundation (Clean & Remove)
Remove dead code, duplicate files, unrelated directories. Fix critical security issue. This phase involves NO structural changes to the working bot -- only deletion of unused/duplicate code.

### Phase 2: Core Implementation (Extract & Package)
Create proper `src/telegram_sales_bot/` Python package structure. Move all essential bot code from `.claude/skills/` into the package with proper imports. Consolidate duplicated scheduling code. Adopt the Docker-safe polling scheduler.

### Phase 3: Integration & Polish (Deploy & Test)
Fix Docker configurations to use new package structure. Migrate JSON state to PostgreSQL. Update pyproject.toml. Validate with existing tests.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom.

### 1. Remove Dead Code from telegram/scripts/
- Delete `.claude/skills/telegram/scripts/run_daemon.py` (superseded by daemon.py)
- Delete `.claude/skills/telegram/scripts/context_summarizer.py` (not imported by any production module)
- Delete `.claude/skills/telegram/scripts/fact_extractor.py` (not imported by any production module)
- Delete `.claude/skills/telegram/scripts/email_validator.py` (duplicate of scheduling_tool.py's version)
- Delete `.claude/skills/telegram/scripts/bot_send.py` (legacy artifact with hardcoded paths to `/Users/server/`)
- Evaluate `.claude/skills/telegram/scripts/timezone_calculator.py` -- delete if not needed after consolidating timezone logic

### 2. Remove Duplicate Files from telegram/scripts/
- Delete `.claude/skills/telegram/scripts/conversation_simulator.py` (testing/ has newer version with calendar metrics)
- Delete `.claude/skills/telegram/scripts/conversation_evaluator.py` (testing/ has version with proper try/except imports)
- Delete `.claude/skills/telegram/scripts/test_scenarios.py` (testing/ has maintained version)
- Delete `.claude/skills/telegram/scripts/run_conversation_tests.py` (testing/ has better path setup)
- Delete `.claude/skills/telegram/scripts/test_scheduled_actions.py` (testing/ has authoritative version)

### 3. Fix Critical Security Issue
- In `.claude/skills/telegram/scripts/scheduled_action_manager.py` line ~461: Replace SQL string interpolation `INTERVAL '%s days' % days` with parameterized query approach (e.g., `WHERE updated_at < NOW() - make_interval(days => $3)` with `days` as parameter)
- Also fix in `.claude/skills/scheduling/scripts/scheduled_action_manager.py` if same pattern exists

### 4. Remove Unrelated Directories
- Move `adws/` out of the repo (or delete -- it has zero dependencies on bot code)
- Move `scripts/` out of the repo (knowledge extraction pipeline, not bot runtime; `run_migrations.py` is stale)
- Move `data/` out of the repo (training assets, not needed at runtime)
- Archive or remove `visualization/` (static HTML diagram)
- Delete stale files: `simulation-results.md`, `stress-output.txt`, `stress-test-results-2026-01-30.md`, `task.md`

### 5. Remove Developer-Tool Skills
- Delete these `.claude/skills/` directories (they are Claude Code developer tools with zero bot integration):
  - `pdf/`, `docx/`, `video-processor/`, `video-analysis/`, `brand-agency/`, `meta-skill/`, `cloudflare-manager/`, `fork-terminal/`, `fetching-library-docs/`, `frontend-design/`
- Keep: `telegram/`, `scheduling/`, `database/`, `register-sales/`, `zoom/`, `google-calendar/`, `humanizer/`, `tone-of-voice/`, `how-to-communicate/`, `testing/`, `eleven-labs/`
- Merge `manual-testing/` into `testing/` (it's a thin wrapper)
- Keep `zoom-calendar-meeting/` as documentation or merge into `zoom/`

### 6. Create Package Structure
- Create `src/telegram_sales_bot/` directory tree:
  ```
  src/telegram_sales_bot/
  ├── __init__.py
  ├── core/
  │   ├── __init__.py
  │   ├── daemon.py          ← from telegram/scripts/daemon.py
  │   ├── agent.py           ← from telegram/scripts/telegram_agent.py
  │   ├── service.py         ← from telegram/scripts/telegram_service.py
  │   ├── client.py          ← library parts from telegram/scripts/telegram_fetch.py
  │   └── models.py          ← from telegram/scripts/models.py
  ├── prospects/
  │   ├── __init__.py
  │   └── manager.py         ← from telegram/scripts/prospect_manager.py
  ├── scheduling/
  │   ├── __init__.py
  │   ├── tool.py            ← from telegram/scripts/scheduling_tool.py (AUTHORITATIVE)
  │   ├── calendar.py        ← from telegram/scripts/sales_calendar.py
  │   ├── db.py              ← MERGED from both scheduled_action_manager.py (telegram features + scheduling row-locking)
  │   ├── scheduler.py       ← from scheduling/scripts/scheduler_service.py (POLLING version)
  │   ├── polling_daemon.py  ← from scheduling/scripts/followup_polling_daemon.py
  │   └── calendar_aware.py  ← from scheduling/scripts/calendar_aware_scheduler.py
  ├── integrations/
  │   ├── __init__.py
  │   ├── zoom.py            ← from zoom/scripts/zoom_service.py
  │   ├── google_calendar.py ← from register-sales/scripts/calendar_connector.py
  │   └── elevenlabs.py      ← from eleven-labs/scripts/voice_transcriber.py
  ├── temporal/
  │   ├── __init__.py
  │   ├── message_buffer.py  ← from telegram/scripts/message_buffer.py
  │   ├── pause_detector.py  ← from telegram/scripts/pause_detector.py
  │   ├── timezone.py        ← from telegram/scripts/timezone_detector.py
  │   └── phrase_tracker.py  ← from telegram/scripts/phrase_tracker.py
  ├── humanizer/
  │   ├── __init__.py
  │   ├── timing.py          ← from humanizer/scripts/natural_timing.py
  │   └── typos.py           ← from humanizer/scripts/typo_injector.py
  ├── knowledge/
  │   ├── __init__.py
  │   ├── loader.py          ← from telegram/scripts/knowledge_loader.py
  │   ├── base/              ← from knowledge_base_final/ (12 topic .md files)
  │   ├── tone/              ← from tone-of-voice/references/ (.md files)
  │   └── methodology/       ← from how-to-communicate/references/ (.md files)
  ├── registry/
  │   ├── __init__.py
  │   ├── models.py          ← from register-sales/scripts/registry_models.py
  │   ├── rep_manager.py     ← from register-sales/scripts/sales_rep_manager.py
  │   ├── prospect_db.py     ← from register-sales/scripts/test_prospect_manager.py
  │   ├── bot.py             ← from register-sales/scripts/registry_bot.py
  │   ├── outreach.py        ← from register-sales/scripts/outreach_daemon.py
  │   └── runner.py          ← from register-sales/scripts/run_registry_bot.py
  ├── database/
  │   ├── __init__.py
  │   ├── init.py            ← from database/scripts/init.py
  │   └── migrations/        ← from database/migrations/ (7 .sql files)
  ├── cli/
  │   ├── __init__.py
  │   ├── fetch.py           ← CLI parts extracted from telegram_fetch.py
  │   ├── setup.py           ← from telegram/scripts/setup_telegram.py
  │   └── auth.py            ← from telegram/scripts/auth.py
  └── config/
      ├── agent_config.json  ← from telegram/config/ (externalize hardcoded values)
      └── sales_slots.json   ← from telegram/config/
  ```

### 7. Update All Imports to Package-Style
- Replace all `sys.path` manipulation in daemon.py (lines 24-37) with proper `from telegram_sales_bot.scheduling import ...` imports
- Replace all `sys.path` hacks in telegram_service.py, scheduling scripts, etc.
- Replace the 277-line `__init__.py` dual-import pattern with clean relative imports
- Update all `try/except ImportError` fallback patterns to simple relative imports
- Remove all `sys.path.insert()` calls across the codebase

### 8. Adopt Docker-Safe Polling Scheduler
- Replace `telegram/scripts/scheduler_service.py` (APScheduler + asyncio.sleep) with `scheduling/scripts/scheduler_service.py` (FollowUpPollingDaemon + database polling)
- Merge `claim_due_actions()`, `mark_processing()`, `reset_stale_processing()` from scheduling's `scheduled_action_manager.py` into the consolidated `scheduling/db.py`
- Include `followup_polling_daemon.py` in the package
- Remove `apscheduler>=4.0.0a5` dependency from pyproject.toml
- Wire daemon.py to use the polling-based SchedulerService

### 9. Clean Up Hardcoded Values and Legacy Code
- Remove `VAULT_PATH = Path.home() / 'Brains' / 'brain'` and all Obsidian integration from telegram_fetch.py
- Remove `MessageHandler` unused class from telegram_service.py
- Remove `__main__` test block from telegram_agent.py (lines 764-824)
- Fix transliterated Russian greetings in pause_detector.py to proper Cyrillic
- Externalize `agent_name`, `telegram_account` from agent_config.json to environment variables
- Remove the stale `scripts/run_migrations.py` that points to non-existent `src/sales_agent/migrations/`

### 10. Update pyproject.toml
- Add `python-telegram-bot>=21.0.0` to core dependencies (currently only in optional `bot` extras)
- Remove `apscheduler>=4.0.0a5` (replaced by polling daemon)
- Add package definition: `[project] name = "telegram-sales-bot"` with `src` layout
- Ensure all required dependencies are listed: `anthropic`, `telethon`, `asyncpg`, `pydantic`, `python-dotenv`, `rich`, `tiktoken`, `httpx`, `google-api-python-client`, `google-auth`, `requests`, `pytz`
- Add entry points for the daemons

### 11. Fix Docker Configuration
- Update `deployment/docker/Dockerfile`:
  - Change COPY commands to use `src/telegram_sales_bot/` instead of `.claude/skills/` directories
  - Update PYTHONPATH to just `/app/src`
  - Update CMD to `python -m telegram_sales_bot.core.daemon`
- Update `deployment/docker/Dockerfile.registry`:
  - Copy `src/telegram_sales_bot/` instead of non-existent `src/` old layout
  - Update PYTHONPATH and CMD
- Update `deployment/docker/Dockerfile.outreach`:
  - Same fixes as Dockerfile.registry
- Update `deployment/docker/docker-compose.yml`:
  - Update volume mounts to reflect new package structure
  - Fix config mount paths
- Update `.dockerignore`:
  - Remove exclusion of `.claude/skills/google-calendar/` (or update volume mounts)
  - Add exclusions for removed directories (`adws/`, `scripts/`, `data/`, etc.)

### 12. Update CLAUDE.md and Documentation
- Update `CLAUDE.md` to reflect new `src/telegram_sales_bot/` package structure
- Update manual testing instructions to use new paths
- Update PYTHONPATH references
- Keep `.claude/skills/testing/` as-is (it's the test framework, update import paths only)

### 13. Validate Everything Works
- Run `uv run python -m py_compile src/telegram_sales_bot/core/daemon.py` for all key modules
- Run `uv run python -c "from telegram_sales_bot.core import daemon"` to verify package imports
- Run existing tests from `.claude/skills/testing/` to verify nothing broke
- Test Docker build: `docker build -f deployment/docker/Dockerfile .`
- Verify database migrations still apply

## Testing Strategy
1. **Import Validation** -- Verify all modules compile and import correctly without `sys.path` hacking
2. **Unit Tests** -- Run existing tests from `.claude/skills/testing/scripts/` with updated import paths
3. **Behavior Tests** -- Run `run_behavior_tests.py` to verify message batching, wait handling, Zoom scheduling
4. **Scheduled Actions** -- Run `test_scheduled_actions.py` to verify the new polling-based scheduler handles CRUD + execution
5. **Docker Build** -- Verify all three Dockerfiles build successfully
6. **Manual E2E** -- Reset test prospect, start daemon from new package, verify initial outreach message sends and responses work

## Acceptance Criteria
- [ ] All bot code lives in `src/telegram_sales_bot/` with proper `__init__.py` files
- [ ] Zero `sys.path.insert()` calls in any production code
- [ ] Zero JSON-file state management in production (prospects.json usage documented for migration)
- [ ] SQL injection in scheduled_action_manager.py is fixed
- [ ] All dead code removed (~2,140 lines): run_daemon.py, context_summarizer.py, fact_extractor.py, email_validator.py, bot_send.py
- [ ] All duplicate files removed: 5 files from telegram/scripts/ that exist in testing/
- [ ] 4 scheduling files consolidated into single authoritative versions
- [ ] Polling-based scheduler replaces APScheduler-based version
- [ ] Developer-tool skills (10 directories) removed from repo
- [ ] `adws/`, `scripts/`, `data/` directories removed
- [ ] All three Dockerfiles build successfully
- [ ] `docker-compose up` starts all services
- [ ] Existing tests pass with updated import paths
- [ ] `pyproject.toml` has all required dependencies as core (not optional)

## Validation Commands
Execute these commands to validate the task is complete:

- `uv run python -m py_compile src/telegram_sales_bot/core/daemon.py` -- Verify main daemon compiles
- `uv run python -m py_compile src/telegram_sales_bot/core/agent.py` -- Verify agent compiles
- `uv run python -m py_compile src/telegram_sales_bot/scheduling/scheduler.py` -- Verify polling scheduler compiles
- `uv run python -c "from telegram_sales_bot.core.models import Prospect, SalesSlot, ScheduledAction"` -- Verify models import
- `uv run python -c "from telegram_sales_bot.scheduling import SchedulerService"` -- Verify scheduling imports
- `uv run python -c "from telegram_sales_bot.integrations.zoom import ZoomBookingService"` -- Verify zoom imports
- `uv run python -c "from telegram_sales_bot.humanizer.timing import NaturalTiming"` -- Verify humanizer imports
- `docker build -f deployment/docker/Dockerfile -t telegram-agent .` -- Verify Docker build
- `docker build -f deployment/docker/Dockerfile.registry -t registry-bot .` -- Verify registry Docker build
- `PYTHONPATH=src uv run python -m telegram_sales_bot.database.init` -- Verify DB init works
- `grep -r "sys.path" src/telegram_sales_bot/ | wc -l` -- Should output 0 (no sys.path hacking)

## Notes
- The `.claude/skills/` directory can remain for Claude Code skill metadata (SKILL.md files) but all Python code should live in `src/telegram_sales_bot/`
- The testing framework (`.claude/skills/testing/`) should stay as-is but update its import paths to use the new package
- Knowledge base files (tone-of-voice, how-to-communicate, knowledge_base_final) should be copied into the package's `knowledge/` directory so they're self-contained
- The `google-calendar` skill's `calendar_client.py` is NOT used by the bot (it uses `CalendarConnector` from register-sales). Keep it only if needed for operator CLI usage
- CalendarConnector has `calendar.readonly` scope -- the bot's `scheduling_tool.py` attempts `create_event()` which requires read-write scope. This is a pre-existing bug that needs fixing (upgrade scope to `calendar` instead of `calendar.readonly`)
- `datetime.utcnow()` is deprecated in Python 3.12+ -- replace with `datetime.now(timezone.utc)` during migration
- After removal of `apscheduler`, remove it from `uv.lock` by running `uv lock`
