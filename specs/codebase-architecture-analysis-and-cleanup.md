# Plan: Skills-First Architecture Consolidation

## Task Description

Consolidate the codebase into a **skills-first architecture** where:

- All core logic lives in `.claude/skills/`
- `src/` directory is deleted
- Communication behavior is defined by skills (tone-of-voice, how-to-communicate)
- Integrations (Zoom, Google Calendar, Telegram) are organized as skills

## Objective

Create a clean, skills-based architecture where Claude Code skills are the primary organizing principle. The Telegram bot logic and smart communication modules are defined and orchestrated through skills.

## Problem Statement

Currently the codebase has functionality scattered between:

- `.claude/skills/` - Original implementation + documentation skills
- `src/sales_agent/` - Migrated production code (14 modules)

This creates confusion. The solution is to consolidate everything into skills and delete src/.

---

## Current State Analysis

### What's in src/sales_agent/ (to be migrated to skills)

| Module | Purpose | Lines | Target Skill |
|--------|---------|-------|--------------|
| `agent/` | Claude AI agent, knowledge loading | ~500 | `telegram/` |
| `telegram/` | Telethon client, message sending | ~400 | `telegram/` |
| `crm/` | Prospect state, JSON storage | ~300 | `telegram/` |
| `scheduling/` | Follow-ups, calendar slots | ~1500 | `google-calendar/` + new `scheduling/` |
| `messaging/` | Message batching/debounce | ~200 | `telegram/` |
| `database/` | PostgreSQL init/migrations | ~400 | new `database/` |
| `media/` | Voice transcription | ~150 | `eleven-labs/` |
| `temporal/` | Timezone, pause detection | ~100 | `telegram/` |
| `context/` | Phrase variation, fact extraction | ~200 | `telegram/` |
| `humanizer/` | Natural timing, typos | ~150 | new `humanizer/` |
| `zoom/` | Zoom meeting booking | ~200 | `zoom/` |
| `registry/` | Sales rep management | ~600 | `register-sales/` |
| `testing/` | Conversation simulation | ~1000 | new `testing/` |
| `daemon.py` | Main entry point | ~1400 | `telegram/` |

### What's Already in Skills (keep/enhance)

| Skill | Current State | Action |
|-------|---------------|--------|
| `telegram/` | 19 scripts (older versions) | Update with latest from src/ |
| `tone-of-voice/` | Documentation only | Keep as-is (defines HOW to communicate) |
| `how-to-communicate/` | Documentation only | Keep as-is (defines WHAT to say - BANT, Zmeyeka) |
| `zoom/` | Zoom API scripts | Merge src/zoom/ into this |
| `google-calendar/` | Calendar API scripts | Merge scheduling logic |
| `register-sales/` | Rep registration | Merge src/registry/ into this |
| `eleven-labs/` | Audio transcription | Merge src/media/ into this |
| `zoom-calendar-meeting/` | Composition skill | Keep as-is |
| `manual-testing/` | Test workflow docs | Merge src/testing/ into this |

---

## Target Architecture

```
.claude/skills/
├── telegram/                    # CORE: Telegram bot + smart communication
│   ├── SKILL.md                 # Skill definition
│   ├── scripts/
│   │   ├── daemon.py            # Main entry point
│   │   ├── telegram_agent.py    # Claude AI agent
│   │   ├── telegram_service.py  # Telethon client
│   │   ├── telegram_fetch.py    # Message fetching
│   │   ├── bot_send.py          # Bot API sending
│   │   ├── prospect_manager.py  # Prospect state (JSON)
│   │   ├── models.py            # Pydantic models
│   │   ├── knowledge_loader.py  # Load tone-of-voice & how-to-communicate
│   │   ├── message_buffer.py    # Batching/debounce
│   │   ├── temporal.py          # Timezone/pause handling
│   │   ├── context.py           # Phrase variation
│   │   └── auth.py              # Telegram auth setup
│   └── config/
│       ├── prospects.json
│       └── agent_config.json
│
├── tone-of-voice/               # HOW to communicate (style guide)
│   ├── SKILL.md
│   └── references/
│       └── *.md                 # Communication style docs
│
├── how-to-communicate/          # WHAT to say (methodology)
│   ├── SKILL.md
│   └── references/
│       └── *.md                 # BANT, Zmeyeka, scripts
│
├── scheduling/                  # NEW: Follow-ups & calendar slots
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── scheduler_service.py
│   │   ├── scheduled_action_manager.py
│   │   ├── sales_calendar.py
│   │   └── scheduling_tool.py
│   └── config/
│       └── sales_slots.json
│
├── humanizer/                   # NEW: Natural timing & typos
│   ├── SKILL.md
│   └── scripts/
│       ├── natural_timing.py
│       └── typo_injector.py
│
├── database/                    # NEW: PostgreSQL management
│   ├── SKILL.md
│   ├── scripts/
│   │   └── init.py
│   └── migrations/
│       └── *.sql
│
├── zoom/                        # Zoom integration (existing)
│   ├── SKILL.md
│   └── scripts/
│       ├── zoom_service.py      # Merged from src/zoom/
│       └── zoom_meetings.py
│
├── google-calendar/             # Calendar integration (existing)
│   ├── SKILL.md
│   └── scripts/
│       └── *.py
│
├── register-sales/              # Sales rep management (existing)
│   ├── SKILL.md
│   └── scripts/
│       ├── register_rep.py
│       ├── sales_rep_manager.py # Merged from src/registry/
│       ├── outreach_daemon.py   # Merged from src/registry/
│       └── registry_bot.py
│
├── eleven-labs/                 # Voice transcription (existing)
│   ├── SKILL.md
│   └── scripts/
│       └── voice_transcriber.py # Merged from src/media/
│
├── testing/                     # NEW: Conversation testing
│   ├── SKILL.md
│   └── scripts/
│       ├── conversation_simulator.py
│       ├── conversation_evaluator.py
│       ├── test_scenarios.py
│       ├── stress_test_runner.py
│       └── manual_test.py
│
└── zoom-calendar-meeting/       # Composition skill (existing)
    └── SKILL.md
```

---

## Relevant Files

### Files to Migrate (src/ → skills/)

**From src/sales_agent/agent/ → .claude/skills/telegram/scripts/**

- `telegram_agent.py` - Claude AI agent with tool calling
- `knowledge_loader.py` - Loads tone-of-voice and how-to-communicate

**From src/sales_agent/telegram/ → .claude/skills/telegram/scripts/**

- `telegram_service.py` - Telethon client wrapper
- `telegram_fetch.py` - Message fetching utilities
- `bot_send.py` - Bot API for sending

**From src/sales_agent/crm/ → .claude/skills/telegram/scripts/**

- `prospect_manager.py` - Prospect state management
- `models.py` - Pydantic models

**From src/sales_agent/scheduling/ → .claude/skills/scheduling/scripts/**

- `scheduler_service.py` - Follow-up scheduler
- `scheduled_action_manager.py` - Database operations
- `sales_calendar.py` - Calendar slot generation
- `scheduling_tool.py` - LLM tool for booking

**From src/sales_agent/humanizer/ → .claude/skills/humanizer/scripts/**

- `natural_timing.py` - Reading/response delays
- `typo_injector.py` - Optional typo generation

**From src/sales_agent/database/ → .claude/skills/database/scripts/**

- `init.py` - Database initialization

**From src/sales_agent/migrations/ → .claude/skills/database/migrations/**

- All `*.sql` files

**From src/sales_agent/zoom/ → .claude/skills/zoom/scripts/**

- `zoom_service.py` - Zoom booking service

**From src/sales_agent/media/ → .claude/skills/eleven-labs/scripts/**

- `voice_transcriber.py` - ElevenLabs integration

**From src/sales_agent/registry/ → .claude/skills/register-sales/scripts/**

- `sales_rep_manager.py` - Sales rep database operations
- `prospect_manager.py` → `test_prospect_manager.py`
- `outreach_daemon.py` - Prospect assignment daemon
- `run_registry_bot.py` - Telegram bot for registration

**From src/sales_agent/testing/ → .claude/skills/testing/scripts/**

- `conversation_simulator.py`
- `conversation_evaluator.py`
- `test_scenarios.py`
- `stress_test_runner.py`
- `manual_test.py`

**Main daemon:**

- `src/sales_agent/daemon.py` → `.claude/skills/telegram/scripts/daemon.py`

### New Skills to Create

1. `.claude/skills/scheduling/SKILL.md`
2. `.claude/skills/humanizer/SKILL.md`
3. `.claude/skills/database/SKILL.md`
4. `.claude/skills/testing/SKILL.md`

---

## Step by Step Tasks

### 1. Create New Skill Directories

- Create `.claude/skills/scheduling/` with SKILL.md and scripts/
- Create `.claude/skills/humanizer/` with SKILL.md and scripts/
- Create `.claude/skills/database/` with SKILL.md and scripts/ and migrations/
- Create `.claude/skills/testing/` with SKILL.md and scripts/

### 2. Migrate telegram Skill Scripts

- Copy latest versions from src/sales_agent/ to .claude/skills/telegram/scripts/
- Update imports to use relative paths within skill
- Ensure daemon.py works as main entry point
- Move config/ files from src/sales_agent/config/ to skill

### 3. Migrate scheduling Logic

- Copy src/sales_agent/scheduling/*.py to .claude/skills/scheduling/scripts/
- Update imports
- Copy sales_slots.json to skill config/

### 4. Migrate humanizer Logic

- Copy src/sales_agent/humanizer/*.py to .claude/skills/humanizer/scripts/
- Update imports

### 5. Migrate database Logic

- Copy src/sales_agent/database/*.py to .claude/skills/database/scripts/
- Copy src/sales_agent/migrations/*.sql to .claude/skills/database/migrations/
- Update paths in init.py

### 6. Migrate zoom Logic

- Merge src/sales_agent/zoom/zoom_service.py into .claude/skills/zoom/scripts/
- Update imports

### 7. Migrate media Logic

- Merge src/sales_agent/media/voice_transcriber.py into .claude/skills/eleven-labs/scripts/
- Update imports

### 8. Migrate registry Logic

- Copy src/sales_agent/registry/*.py to .claude/skills/register-sales/scripts/
- Rename prospect_manager.py to test_prospect_manager.py to avoid confusion
- Update imports

### 9. Migrate testing Logic

- Copy src/sales_agent/testing/*.py to .claude/skills/testing/scripts/
- Update imports

### 10. Update Skill SKILL.md Files

- Update .claude/skills/telegram/SKILL.md with new entry points
- Create SKILL.md for each new skill directory
- Document how skills interact with each other

### 11. Delete src/ Directory

- After verifying all functionality works from skills
- Remove entire src/sales_agent/ directory
- Update any remaining references

### 12. Update Root Scripts

- Update scripts/run_migrations.py to use .claude/skills/database/
- Update scripts/validate_config.py to check skill paths
- Update any other root scripts

---

## Acceptance Criteria

1. **All code lives in .claude/skills/** - No production code in src/
2. **Telegram daemon runs from skill** - `uv run python .claude/skills/telegram/scripts/daemon.py`
3. **Communication style defined by skills** - tone-of-voice and how-to-communicate are loaded by telegram skill
4. **Integrations work** - Zoom, Google Calendar, ElevenLabs all functional
5. **src/ directory deleted** - Clean removal after migration verified

---

## Validation Commands

```bash
# Run telegram daemon from skill
uv run python .claude/skills/telegram/scripts/daemon.py

# Run database migrations from skill
uv run python .claude/skills/database/scripts/init.py

# Run registry bot from skill
uv run python .claude/skills/register-sales/scripts/registry_bot.py

# Run manual test from skill
uv run python .claude/skills/testing/scripts/manual_test.py

# Verify src/ is deleted
test ! -d src/sales_agent && echo "src/ deleted successfully"
```

---

## Notes

### Import Strategy for Skills

Since skills are not a Python package, use relative imports within each skill:

```python
# Inside .claude/skills/telegram/scripts/daemon.py
from .telegram_agent import TelegramAgent
from .prospect_manager import ProspectManager
from .models import Prospect, AgentConfig
```

Or use sys.path manipulation:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

### Skill Dependencies

Skills can reference other skills by path:

```python
# In telegram skill, load tone-of-voice
tone_path = Path(__file__).parent.parent.parent / "tone-of-voice" / "references"
```

### Environment Variables

All skills share the same .env file in project root:

- `ANTHROPIC_API_KEY`
- `DATABASE_URL`
- `TELETHON_API_ID` / `TELETHON_API_HASH`
- `ZOOM_*` credentials
- `GOOGLE_*` credentials
- `ELEVENLABS_API_KEY`
