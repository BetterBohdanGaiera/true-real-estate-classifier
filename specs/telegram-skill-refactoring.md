# Plan: Refactor Telegram Skill into Atomic Components

## Task Description

The current `.claude/skills/telegram` skill has grown from a simple message-fetching utility into a full-fledged real estate sales automation system with 7,400+ lines of code across 19 Python modules. This violates the "one skill = one capability" principle and makes the skill difficult to maintain, understand, and compose with other skills.

The refactoring will extract the core application logic into a proper `src/` directory structure while keeping only atomic, single-purpose skills in `.claude/skills/`.

## Objective

Transform the monolithic telegram skill into:
1. A proper Python application in `src/` for the core sales agent daemon
2. Multiple atomic skills (telegram, sales-calendar, prospect-management) that each serve a single, focused purpose
3. Clear separation between "Claude Code skills" (operator tools) and "application code" (the sales automation system)

## Problem Statement

### Current State
The telegram skill contains:
- **Telegram I/O utilities** (telegram_fetch.py, telegram_service.py, bot_send.py) - 1,400+ lines
- **Sales agent brain** (telegram_agent.py, knowledge_loader.py) - 1,000+ lines
- **CRM/Prospect management** (prospect_manager.py, models.py) - 500+ lines
- **Calendar/Scheduling** (sales_calendar.py, scheduling_tool.py, scheduled_action_manager.py, scheduler_service.py) - 1,700+ lines
- **Daemon orchestration** (run_daemon.py) - 700+ lines
- **Testing infrastructure** (conversation_simulator.py, test_scenarios.py, conversation_evaluator.py) - 1,400+ lines

### Why This Is Wrong
1. **Not a skill** - Skills are meant to provide Claude Code with capabilities. This is an autonomous application.
2. **Too many concerns** - Mixes Telegram I/O, LLM reasoning, CRM, scheduling, knowledge management
3. **Wrong location** - Production code shouldn't live in `.claude/skills/`
4. **Violates atomicity** - A skill should do ONE thing well

### What Skills Should Be
Per meta-skill documentation:
- One capability per skill
- Max ~500 lines in SKILL.md body
- Focused on giving Claude Code a specific tool
- Examples: "PDF form filling", "Telegram message fetching", "Git commit generation"

## Solution Approach

### Architecture Decision: Skills vs Application

| Component | Should Be | Why |
|-----------|-----------|-----|
| telegram_fetch.py | **Skill** | Generic Telegram I/O - useful standalone |
| telegram_agent.py | **Application** | Business logic specific to sales agent |
| prospect_manager.py | **Could be skill OR app** | Generic CRM ops could be skill, but tightly coupled to sales logic |
| sales_calendar.py | **Application** | Business-specific sales calendar |
| run_daemon.py | **Application** | The main application entry point |
| knowledge_loader.py | **Application** | Specific to Bali real estate knowledge base |
| scheduled_action_manager.py | **Application** | Business-specific scheduled actions |
| Testing infrastructure | **Application** | Test harness for the sales agent |

### Proposed Structure

```
Classifier/
├── src/
│   └── sales_agent/                    # The actual application
│       ├── __init__.py
│       ├── agent/                      # LLM-powered agent
│       │   ├── __init__.py
│       │   ├── telegram_agent.py       # Core agent logic
│       │   └── knowledge_loader.py     # Knowledge base integration
│       ├── crm/                        # Customer relationship management
│       │   ├── __init__.py
│       │   ├── models.py               # Pydantic models
│       │   └── prospect_manager.py     # Prospect CRUD
│       ├── scheduling/                 # Scheduling subsystem
│       │   ├── __init__.py
│       │   ├── sales_calendar.py       # Availability management
│       │   ├── scheduling_tool.py      # Booking operations
│       │   ├── scheduled_action_manager.py  # DB persistence
│       │   └── scheduler_service.py    # APScheduler wrapper
│       ├── telegram/                   # Telegram integration (app-specific)
│       │   ├── __init__.py
│       │   ├── telegram_service.py     # Human-like message sending
│       │   └── bot_send.py             # Bot API fallback
│       ├── testing/                    # Testing infrastructure
│       │   ├── __init__.py
│       │   ├── conversation_simulator.py
│       │   ├── test_scenarios.py
│       │   └── conversation_evaluator.py
│       ├── config/                     # Configuration (move from skills)
│       │   ├── agent_config.json
│       │   ├── prospects.json
│       │   ├── sales_slots.json
│       │   └── sales_slots_data.json
│       └── daemon.py                   # Main entry point (was run_daemon.py)
│
├── .claude/skills/
│   ├── telegram/                       # ATOMIC: Telegram message I/O only
│   │   ├── SKILL.md                    # Focused on fetch/send/search
│   │   └── scripts/
│   │       └── telegram_fetch.py       # The CLI tool
│   │
│   ├── sales-agent-daemon/             # NEW: Skill to run/manage the sales agent
│   │   └── SKILL.md                    # Start/stop/status of the daemon
│   │
│   ├── tone-of-voice/                  # KEEP: Communication style (already atomic)
│   ├── how-to-communicate/             # KEEP: Sales methodology (already atomic)
│   └── ... (other existing skills)
```

### Alternative Approaches Considered

**Option A: Keep everything as skills, split into many skills**
- Pros: All functionality accessible to Claude Code
- Cons: Not how skills are meant to work; daemon shouldn't be a skill

**Option B: Move everything to src/, create thin skill wrappers**
- Pros: Proper separation; clean architecture
- Cons: More work; need to update imports throughout

**Option C (Recommended): Hybrid approach**
- Keep `telegram` skill atomic (just the fetch/send CLI)
- Move business logic to `src/sales_agent/`
- Create new `sales-agent-daemon` skill for running the daemon
- This matches the actual use pattern

## Relevant Files

### Files to Move to `src/sales_agent/`

- `.claude/skills/telegram/scripts/telegram_agent.py` → `src/sales_agent/agent/telegram_agent.py`
- `.claude/skills/telegram/scripts/knowledge_loader.py` → `src/sales_agent/agent/knowledge_loader.py`
- `.claude/skills/telegram/scripts/models.py` → `src/sales_agent/crm/models.py`
- `.claude/skills/telegram/scripts/prospect_manager.py` → `src/sales_agent/crm/prospect_manager.py`
- `.claude/skills/telegram/scripts/sales_calendar.py` → `src/sales_agent/scheduling/sales_calendar.py`
- `.claude/skills/telegram/scripts/scheduling_tool.py` → `src/sales_agent/scheduling/scheduling_tool.py`
- `.claude/skills/telegram/scripts/scheduled_action_manager.py` → `src/sales_agent/scheduling/scheduled_action_manager.py`
- `.claude/skills/telegram/scripts/scheduler_service.py` → `src/sales_agent/scheduling/scheduler_service.py`
- `.claude/skills/telegram/scripts/telegram_service.py` → `src/sales_agent/telegram/telegram_service.py`
- `.claude/skills/telegram/scripts/bot_send.py` → `src/sales_agent/telegram/bot_send.py`
- `.claude/skills/telegram/scripts/run_daemon.py` → `src/sales_agent/daemon.py`
- `.claude/skills/telegram/scripts/conversation_simulator.py` → `src/sales_agent/testing/conversation_simulator.py`
- `.claude/skills/telegram/scripts/test_scenarios.py` → `src/sales_agent/testing/test_scenarios.py`
- `.claude/skills/telegram/scripts/conversation_evaluator.py` → `src/sales_agent/testing/conversation_evaluator.py`
- `.claude/skills/telegram/scripts/run_conversation_tests.py` → `src/sales_agent/testing/run_conversation_tests.py`
- `.claude/skills/telegram/config/*` → `src/sales_agent/config/`
- `.claude/skills/telegram/migrations/` → `src/sales_agent/migrations/`

### Files to Keep in Telegram Skill

- `.claude/skills/telegram/SKILL.md` (rewrite to be focused)
- `.claude/skills/telegram/scripts/telegram_fetch.py` (the atomic CLI tool)
- `.claude/skills/telegram/scripts/setup_telegram.py` (setup helper)
- `.claude/skills/telegram/scripts/auth.py` (auth utilities)

### New Files to Create

- `src/sales_agent/__init__.py`
- `src/sales_agent/agent/__init__.py`
- `src/sales_agent/crm/__init__.py`
- `src/sales_agent/scheduling/__init__.py`
- `src/sales_agent/telegram/__init__.py`
- `src/sales_agent/testing/__init__.py`
- `.claude/skills/sales-agent-daemon/SKILL.md`

## Implementation Phases

### Phase 1: Foundation
1. Create `src/sales_agent/` directory structure with all `__init__.py` files
2. Move configuration files to `src/sales_agent/config/`
3. Update `.gitignore` if needed

### Phase 2: Core Implementation
1. Move Python modules to their new locations
2. Update all import statements to reflect new package structure
3. Update relative path references (config files, knowledge base, etc.)
4. Create proper `__init__.py` exports for clean imports

### Phase 3: Integration & Polish
1. Rewrite `.claude/skills/telegram/SKILL.md` to be atomic (Telegram I/O only)
2. Create new `.claude/skills/sales-agent-daemon/SKILL.md`
3. Update `pyproject.toml` to include the new package
4. Test that both the skill and the application work correctly
5. Clean up any orphaned files

## Step by Step Tasks

### 1. Create Directory Structure
- Create `src/sales_agent/` with subdirectories: `agent/`, `crm/`, `scheduling/`, `telegram/`, `testing/`, `config/`, `migrations/`
- Create `__init__.py` in each directory
- Move `config/` contents from `.claude/skills/telegram/config/` to `src/sales_agent/config/`
- Move `migrations/` from `.claude/skills/telegram/migrations/` to `src/sales_agent/migrations/`

### 2. Move CRM Module
- Move `models.py` to `src/sales_agent/crm/models.py`
- Move `prospect_manager.py` to `src/sales_agent/crm/prospect_manager.py`
- Update imports in both files
- Export key classes from `src/sales_agent/crm/__init__.py`

### 3. Move Scheduling Module
- Move `sales_calendar.py` to `src/sales_agent/scheduling/`
- Move `scheduling_tool.py` to `src/sales_agent/scheduling/`
- Move `scheduled_action_manager.py` to `src/sales_agent/scheduling/`
- Move `scheduler_service.py` to `src/sales_agent/scheduling/`
- Update all internal imports between these files
- Export key classes from `src/sales_agent/scheduling/__init__.py`

### 4. Move Telegram Integration Module
- Move `telegram_service.py` to `src/sales_agent/telegram/`
- Move `bot_send.py` to `src/sales_agent/telegram/`
- Update imports
- Export from `src/sales_agent/telegram/__init__.py`

### 5. Move Agent Module
- Move `telegram_agent.py` to `src/sales_agent/agent/`
- Move `knowledge_loader.py` to `src/sales_agent/agent/`
- Update imports to reference new locations of models, scheduling, etc.
- Update paths to knowledge_base_final and skills directories
- Export from `src/sales_agent/agent/__init__.py`

### 6. Move Testing Module
- Move `conversation_simulator.py` to `src/sales_agent/testing/`
- Move `test_scenarios.py` to `src/sales_agent/testing/`
- Move `conversation_evaluator.py` to `src/sales_agent/testing/`
- Move `run_conversation_tests.py` to `src/sales_agent/testing/`
- Move `test_scheduled_actions.py` to `src/sales_agent/testing/`
- Update all imports
- Export from `src/sales_agent/testing/__init__.py`

### 7. Move Main Daemon
- Move `run_daemon.py` to `src/sales_agent/daemon.py`
- Update all imports to use the new package structure
- Ensure config paths are updated (use Path relative to module or config directory)

### 8. Update Paths Throughout
- Replace all hardcoded `.claude/skills/telegram/` paths with dynamic resolution
- Update paths to `tone-of-voice` and `how-to-communicate` skills (still in `.claude/skills/`)
- Update paths to `knowledge_base_final/` (still at project root)
- Ensure config file paths work from the new location

### 9. Rewrite Telegram Skill SKILL.md
- Remove all documentation about the sales agent
- Focus ONLY on:
  - Fetching messages
  - Searching messages
  - Sending messages
  - Downloading attachments
  - Editing messages
- Keep it under 300 lines
- Remove scripts that are no longer in the skill directory

### 10. Create Sales Agent Daemon Skill
- Create `.claude/skills/sales-agent-daemon/SKILL.md`
- Document how to:
  - Start the daemon: `uv run python -m sales_agent.daemon`
  - Check status
  - View logs
  - Configure the agent
- Keep it focused on daemon operations

### 11. Update pyproject.toml
- Add `src` to Python path or configure as package
- Ensure `sales_agent` can be imported as a module

### 12. Clean Up Old Skill Directory
- Remove moved files from `.claude/skills/telegram/scripts/`
- Remove moved directories (config/, migrations/)
- Keep only: `SKILL.md`, `scripts/telegram_fetch.py`, `scripts/setup_telegram.py`, `scripts/auth.py`
- Remove logs/ directory from skill

### 13. Validate Everything Works
- Run the daemon: `uv run python -m sales_agent.daemon`
- Test the telegram skill: `uv run python .claude/skills/telegram/scripts/telegram_fetch.py list`
- Run existing tests if any
- Verify config files are found correctly

## Testing Strategy

### Unit Tests
- Test that all imports resolve correctly after the move
- Test that config files are loaded from the new location
- Test that knowledge base paths resolve correctly

### Integration Tests
- Test the daemon starts without errors
- Test the telegram skill can fetch messages independently
- Test the sales agent can process a mock message

### Manual Validation
- Start the daemon and verify it connects to Telegram
- Use the telegram skill to send a test message
- Verify scheduled actions still work with the database

## Acceptance Criteria

1. **Telegram skill is atomic**: The `.claude/skills/telegram/` directory contains ONLY Telegram I/O utilities (fetch, send, search)
2. **Sales agent is a proper app**: All business logic lives in `src/sales_agent/` with proper package structure
3. **New skill exists**: `.claude/skills/sales-agent-daemon/` provides daemon control operations
4. **No broken imports**: All modules can be imported without errors
5. **Daemon works**: `uv run python -m sales_agent.daemon` starts the sales automation system
6. **Skill works**: The telegram skill commands work independently
7. **Config preserved**: All JSON configuration files are preserved and accessible
8. **Knowledge base accessible**: Agent can still load context from `knowledge_base_final/`
9. **Skills still referenced**: Agent still loads tone-of-voice and how-to-communicate skills

## Validation Commands

Execute these commands to validate the task is complete:

- `python -c "from sales_agent.crm.models import Prospect; print('CRM models OK')"` - Verify CRM module imports
- `python -c "from sales_agent.scheduling.sales_calendar import SalesCalendar; print('Scheduling OK')"` - Verify scheduling module imports
- `python -c "from sales_agent.agent.telegram_agent import TelegramAgent; print('Agent OK')"` - Verify agent module imports
- `python -c "from sales_agent.daemon import main; print('Daemon OK')"` - Verify daemon module imports
- `uv run python .claude/skills/telegram/scripts/telegram_fetch.py --help` - Verify telegram skill still works
- `ls -la src/sales_agent/config/` - Verify config files moved correctly
- `wc -l .claude/skills/telegram/SKILL.md` - Verify SKILL.md is under 300 lines
- `ls .claude/skills/sales-agent-daemon/SKILL.md` - Verify new skill exists

## Notes

### Dependencies
- No new dependencies required
- Existing dependencies in `pyproject.toml` are sufficient

### Breaking Changes
- Anyone importing from `.claude/skills/telegram/scripts/` will need to update imports
- Daemon start command changes from `python .claude/skills/telegram/scripts/run_daemon.py` to `python -m sales_agent.daemon`

### Future Considerations
- Consider extracting `prospect_manager.py` as a separate `prospect-crm` skill if it proves useful standalone
- Consider creating a `sales-calendar` skill if calendar operations are needed independently
- The testing infrastructure could become its own skill for conversation simulation
