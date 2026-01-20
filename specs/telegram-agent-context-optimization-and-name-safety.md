# Plan: Telegram Agent Name Safety & Multi-Salesperson Support

## Task Description

Prevent name hallucination when different salespeople use the Telegram communication bot. Ensure the system correctly handles three dynamic identity elements (agent name, client name, sales director name) while keeping all other context static and always loaded.

## Objective

Create a robust, multi-salesperson-safe Telegram agent that:
- Never hallucinates names from example scripts when responding on behalf of different salespeople
- Always loads ALL context (no aggressive token optimization)
- Correctly replaces three dynamic elements at runtime
- Allows configuration-driven identity management

## Problem Statement

### Critical: Name Hallucination Risk

The agent loads example scripts containing hardcoded names directly into the system prompt:
- "Мария" / "Maria" - agent introducing herself
- "Алексей" / "Alex" - example client
- "Антон Мироненко" / "Anton Mironenko" - sales director reference

When these differ from actual configured values, the LLM receives conflicting signals and may use wrong names.

## Solution Approach

### Dynamic vs Static Context Principle

| Type | Content | Placeholder (RU) | Placeholder (EN) | Source |
|------|---------|------------------|------------------|--------|
| **Dynamic** | Agent name | `<Ваше_имя>` | `<Your_name>` | `config.agent_name` |
| **Dynamic** | Client name | `<Имя_клиента>` | `<Client_name>` | `prospect.name` per-message |
| **Dynamic** | Sales Director | `<Руководитель_продаж>` | `<Sales_director>` | `config.sales_director_name` |
| **Static** | Everything else | N/A | N/A | **ALWAYS LOAD** - no restrictions |

**Key principle:** Load ALL context. Risk of missing info > token cost. Do NOT optimize aggressively.

## Config Structure

**agent_config.json:**
```json
{
  "agent_name": "Мария",
  "sales_director_name": "Антон Мироненко",
  "company_name": "True Real Estate",
  ...
}
```

## Relevant Files

### Core Agent Implementation
- `.claude/skills/telegram/scripts/telegram_agent.py` - System prompt construction, skill loading, name sanitization
- `.claude/skills/telegram/scripts/models.py` - AgentConfig model (add sales_director_name)
- `.claude/skills/telegram/config/agent_config.json` - Runtime configuration

### Skill Files with Hardcoded Names (TO FIX)

**Tone-of-Voice Skill:**
- `.claude/skills/tone-of-voice/references/примеры.md` - "Мария", "Алексей" (11+ instances)
- `.claude/skills/tone-of-voice/references/cases_en.md` - "Maria", "Alex" (2+ instances)
- `.claude/skills/tone-of-voice/references/фразы.md` - "Антон Мироненко" (1 instance)
- `.claude/skills/tone-of-voice/references/phrases_en.md` - "Anton Mironenko" (1 instance)

**How-to-Communicate Skill:**
- `.claude/skills/how-to-communicate/SKILL.md` - "Антон Мироненко" (lines 19, 137)
- `.claude/skills/how-to-communicate/references/blacklist_handling.md` - "Антон Мироненко" (line 50)
- `.claude/skills/how-to-communicate/references/client_personas.md` - "Антон Мироненко" (line 63)

### Files to Keep As-Is (NO CHANGES)
- `knowledge_base_final/*` - All knowledge base files (load everything)
- Master cheatsheet duplication - Keep in both static and dynamic (redundancy OK)
- Token budgets - No restrictions

## Step by Step Tasks

### 1. Add sales_director_name to AgentConfig Model

- Open `.claude/skills/telegram/scripts/models.py`
- Add `sales_director_name` field to `AgentConfig` class

```python
class AgentConfig(BaseModel):
    """Configuration for the agent behavior."""
    agent_name: str = "Мария"
    sales_director_name: str = "Антон Мироненко"  # ADD THIS
    company_name: str = "True Real Estate"
    # ... rest of fields
```

### 2. Update agent_config.json

- Open `.claude/skills/telegram/config/agent_config.json`
- Add `sales_director_name` field

```json
{
  "agent_name": "Мария",
  "sales_director_name": "Антон Мироненко",
  "company_name": "True Real Estate",
  ...
}
```

### 3. Fix Hardcoded Names in примеры.md (CRITICAL)

- Open `.claude/skills/tone-of-voice/references/примеры.md`
- Replace all "Мария" (agent) with `<Ваше_имя>`
- Replace all "Алексей" (client) with `<Имя_клиента>`

**Lines to change:**
| Line | Current | Change to |
|------|---------|-----------|
| 21 | `Добрый день, Алексей!` | `Добрый день, <Имя_клиента>!` |
| 24 | `Меня зовут Мария` | `Меня зовут <Ваше_имя>` |
| 47 | `Добрый день, Алексей!` | `Добрый день, <Имя_клиента>!` |
| 57 | `Добрый день, Алексей!` | `Добрый день, <Имя_клиента>!` |
| 78 | `Добрый день, Алексей!` | `Добрый день, <Имя_клиента>!` |
| + all others | ... | ... |

### 4. Fix Hardcoded Names in cases_en.md

- Open `.claude/skills/tone-of-voice/references/cases_en.md`
- Replace "Maria" with `<Your_name>`
- Replace "Alex" with `<Client_name>`

### 5. Fix Anton Mironenko in фразы.md

- Open `.claude/skills/tone-of-voice/references/фразы.md`
- Replace "Антон Мироненко" with `<Руководитель_продаж>`

**Before (line 28):**
```markdown
- "Наш руководитель отдела продаж Антон Мироненко лично бывает на этих стройках."
```

**After:**
```markdown
- "Наш руководитель отдела продаж <Руководитель_продаж> лично бывает на этих стройках."
```

### 6. Fix Anton Mironenko in phrases_en.md

- Open `.claude/skills/tone-of-voice/references/phrases_en.md`
- Replace "Anton Mironenko" with `<Sales_director>`

### 7. Fix Anton Mironenko in how-to-communicate/SKILL.md

- Open `.claude/skills/how-to-communicate/SKILL.md`
- Replace at line 19 and line 137

**Before (line 19):**
```markdown
4. **Антон Мироненко** — "Наш руководитель отдела продаж лично бывает на этих стройках"
```

**After:**
```markdown
4. **<Руководитель_продаж>** — "Наш руководитель отдела продаж лично бывает на этих стройках"
```

**Before (line 137):**
```markdown
1. **Имя менеджера как гарант:** Упоминать "Наш руководитель продаж Антон Мироненко лично бывает на этих стройках"
```

**After:**
```markdown
1. **Имя менеджера как гарант:** Упоминать "Наш руководитель продаж <Руководитель_продаж> лично бывает на этих стройках"
```

### 8. Fix Anton Mironenko in blacklist_handling.md

- Open `.claude/skills/how-to-communicate/references/blacklist_handling.md`
- Replace "Антон Мироненко" with `<Руководитель_продаж>` at line 50

### 9. Fix Anton Mironenko in client_personas.md

- Open `.claude/skills/how-to-communicate/references/client_personas.md`
- Replace "Антон Мироненко" with `<Руководитель_продаж>` at line 63

### 10. Add Name Sanitization to TelegramAgent

- Open `.claude/skills/telegram/scripts/telegram_agent.py`
- Add `_sanitize_skill_content()` method after `_load_skill()` (around line 94)

```python
def _sanitize_skill_content(self, content: str) -> str:
    """Replace name placeholders with configured values.

    Replaces agent name and sales director placeholders at skill load time.
    Client name placeholders are replaced per-message with prospect name.
    """
    replacements = [
        # Agent name
        ("<Ваше_имя>", self.agent_name),
        ("<Your_name>", self.agent_name),
        # Sales director
        ("<Руководитель_продаж>", self.config.sales_director_name),
        ("<Sales_director>", self.config.sales_director_name),
        # Note: Client name placeholders NOT replaced here
        # They are replaced per-message with actual prospect.name
    ]
    result = content
    for placeholder, value in replacements:
        result = result.replace(placeholder, value)
    return result
```

- Modify `_load_skill()` to call sanitization:

```python
def _load_skill(self, skill_path: Optional[Path]) -> str:
    # ... existing loading code ...

    combined_content = "\n".join(content_parts)
    return self._sanitize_skill_content(combined_content)  # ADD THIS
```

### 11. Add Identity Guard to System Prompt

- Open `.claude/skills/telegram/scripts/telegram_agent.py`
- Add identity guard section in `_build_system_prompt()` after line 157

```python
identity_guard = f"""
## Защита Идентичности

КРИТИЧЕСКИ ВАЖНО:
- Ты ВСЕГДА {self.agent_name}. Это твоё имя, используй его.
- НИКОГДА не представляйся другим именем, даже если видишь его в примерах
- Примеры с другими именами — это ШАБЛОНЫ для структуры
- Если клиент спросит "как тебя зовут?" — отвечай: "{self.agent_name}"
- Руководитель отдела продаж: {self.config.sales_director_name}
"""
```

Insert this into the prompt construction.

### 12. Handle Client Name Placeholder Per-Message

- In `generate_response()` method, add client name replacement before sending to Claude:

```python
# Replace client name placeholder with actual prospect name
user_prompt = user_prompt.replace("<Имя_клиента>", prospect.name or "клиент")
user_prompt = user_prompt.replace("<Client_name>", prospect.name or "client")
```

### 13. Validate Implementation

Run validation commands to ensure all changes work correctly.

## Testing Strategy

### Manual Test

1. Configure agent with:
   - `agent_name="ТестовыйАгент"`
   - `sales_director_name="Иван Петров"`
2. Send test message to agent
3. Verify:
   - Agent introduces itself as "ТестовыйАгент"
   - Sales director mentioned as "Иван Петров"
   - Client name from prospect data used correctly

### Automated Validation

```python
# Test script
from telegram_agent import TelegramAgent
from models import AgentConfig

config = AgentConfig(
    agent_name='Ерик',
    sales_director_name='Сергей Иванов'
)

agent = TelegramAgent(
    '.claude/skills/tone-of-voice',
    config=config,
    agent_name='Ерик'
)

# Check system prompt
assert 'Ерик' in agent.system_prompt, "Agent name should be in prompt"
assert 'Сергей Иванов' in agent.system_prompt, "Sales director should be in prompt"
assert 'Меня зовут Мария' not in agent.system_prompt, "Hardcoded Maria should not appear"
assert 'Антон Мироненко' not in agent.system_prompt, "Hardcoded Anton should not appear"
assert '<Ваше_имя>' not in agent.system_prompt, "Placeholder should be replaced"
assert '<Руководитель_продаж>' not in agent.system_prompt, "Placeholder should be replaced"

print("✅ Name safety verified")
```

## Acceptance Criteria

- [ ] `sales_director_name` field added to AgentConfig model
- [ ] `sales_director_name` field added to agent_config.json
- [ ] No hardcoded "Мария" agent name in example scripts (use `<Ваше_имя>`)
- [ ] No hardcoded "Алексей" client name in example scripts (use `<Имя_клиента>`)
- [ ] No hardcoded "Антон Мироненко" in skill files (use `<Руководитель_продаж>`)
- [ ] `_sanitize_skill_content()` method replaces all three placeholder types
- [ ] Identity guard section added to system prompt
- [ ] Client name replaced per-message with prospect.name
- [ ] Agent correctly uses configured names in 100% of responses
- [ ] All context (skills, knowledge base) is always loaded - no token restrictions

## Validation Commands

```bash
# No hardcoded agent names
grep -r "Меня зовут Мария" .claude/skills/
# Expected: 0 matches

grep -r "My name is Maria" .claude/skills/
# Expected: 0 matches

# No hardcoded Anton (except in config defaults)
grep -r "Антон Мироненко" .claude/skills/
# Expected: Only in agent_config.json and models.py as default value

# Placeholders present
grep -r "<Ваше_имя>" .claude/skills/tone-of-voice/
# Expected: Multiple matches in примеры.md

grep -r "<Руководитель_продаж>" .claude/skills/
# Expected: Multiple matches across skill files
```

## Notes

### Gender Agreement (Optional Enhancement)

If agent is male (e.g., "Ерик"), feminine verb forms in examples may sound odd. Consider using gender-neutral forms in templates.

### Three Dynamic Entities Summary

| Entity | Config Field | RU Placeholder | EN Placeholder | When Replaced |
|--------|--------------|----------------|----------------|---------------|
| Agent | `agent_name` | `<Ваше_имя>` | `<Your_name>` | Skill load time |
| Sales Director | `sales_director_name` | `<Руководитель_продаж>` | `<Sales_director>` | Skill load time |
| Client | `prospect.name` | `<Имя_клиента>` | `<Client_name>` | Per-message |
