# Plan: Tone of Voice + Dynamic Delays + User Input Collection

## Overview

Three interconnected improvements to the Telegram sales agent:

1. **Tone of Voice** - shorter responses, replace em-dashes with short dashes
2. **Dynamic Message Delays** - reading delay proportional to incoming message length
3. **User Input Collection** - document all required config inputs

## Files to Modify

### Task 1: Tone of Voice (Em-dash replacement + brevity)

**Batch 1 - Skill files (parallel):**
- `.claude/skills/tone-of-voice/SKILL.md` - add anti-dash rule
- `.claude/skills/tone-of-voice/references/фразы.md` - replace em-dashes
- `.claude/skills/tone-of-voice/references/структуры.md` - replace em-dashes
- `.claude/skills/tone-of-voice/references/примеры.md` - replace em-dashes
- `.claude/skills/tone-of-voice/references/phrases_en.md` - replace em-dashes
- `.claude/skills/tone-of-voice/references/cases_en.md` - replace em-dashes
- `.claude/skills/how-to-communicate/SKILL.md` - replace em-dashes
- `.claude/skills/how-to-communicate/references/*` - 9 files with em-dashes

**Batch 2 - Agent code:**
- `src/sales_agent/agent/telegram_agent.py` - add post-processing `_sanitize_output()` + add dash rule to system prompt

### Task 2: Dynamic Reading Delays

- `src/sales_agent/crm/models.py` - add reading_delay config fields
- `src/sales_agent/config/agent_config.json` - add reading delay values
- `src/sales_agent/telegram/telegram_service.py` - add `_calculate_reading_delay()` method
- `src/sales_agent/daemon.py` - integrate reading delay before generate_response()

### Task 3: User Input Collection

- `src/sales_agent/crm/models.py` - add ProspectInput validation model
- `docs/configuration-guide.md` - comprehensive config documentation

## Dependency Graph

- All Task 1 skill files can be modified in parallel
- Task 1 agent code (telegram_agent.py) is independent
- Task 2 models.py and agent_config.json can be parallel
- Task 2 telegram_service.py depends on models.py
- Task 2 daemon.py depends on telegram_service.py
- Task 3 models.py is independent (different section than Task 2)
- Task 3 docs is independent

## Build Strategy

Batch 1: All em-dash replacements in skill files + models.py (reading delay + ProspectInput) + agent_config.json + docs
Batch 2: telegram_agent.py (sanitize output) + telegram_service.py (reading delay method) + daemon.py (integrate reading delay)
