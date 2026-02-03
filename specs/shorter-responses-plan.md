# Plan: Shorter Responses Implementation

## Objective
Update sales agent communication to generate shorter, more concise responses (1-3 sentences) across all touchpoints: skills, system prompt, and scheduling instructions.

## Current State Analysis

### 1. tone-of-voice/SKILL.md
- Currently has 79 lines with comprehensive guidelines
- **Issue:** No explicit brevity instruction
- Need to add: "Відповідай максимально коротко, 1-3 речення"

### 2. how-to-communicate/SKILL.md
- Currently has 163 lines with call methodologies
- **Issue:** Examples show longer message structures
- Need to add: Concise response principle

### 3. telegram_agent.py `_build_system_prompt()` (line 174)
- Current rule at line 287: "Отвечай КОРОТКО и по делу (2-5 предложений обычно достаточно)"
- **Issue:** 2-5 sentences is still too long
- Change to: "Відповідай максимально коротко, 1-3 речення"

### 4. Scheduling Instructions (lines 197-253)
- Follow-up examples at lines 249-252 are already short
- **Issue:** Intent descriptions could be shorter
- Need to simplify follow-up confirmation templates

## Implementation Plan

### Task 1: Update tone-of-voice/SKILL.md
**File:** `.claude/skills/tone-of-voice/SKILL.md`
**Changes:**
- Add new principle after line 35 (before "## Быстрая Проверка"):
```markdown
## Стиль Відповідей

**КРИТИЧНО ВАЖЛИВО:** Відповідай максимально коротко, 1-3 речення.
- Кожне повідомлення має бути лаконічним
- Один вопрос за раз
- Без зайвих пояснень
```

### Task 2: Update how-to-communicate/SKILL.md
**File:** `.claude/skills/how-to-communicate/SKILL.md`
**Changes:**
- Add brevity principle after line 80 (after "12. НИКОГДА не продавай на выдуманной информации"):
```markdown
### 13. Відповідай максимально коротко (1-3 речення)

Кожне повідомлення — максимум 1-3 речення. Ніяких довгих пояснень. Один вопрос за раз. Клиенты цінують лаконічність.
```
- Update checklist to add brevity check

### Task 3: Update telegram_agent.py system prompt
**File:** `src/sales_agent/agent/telegram_agent.py`
**Changes:**
- Line 287: Change from:
  `"- Отвечай КОРОТКО и по делу (2-5 предложений обычно достаточно)"`
  To:
  `"- **КРИТИЧНО:** Відповідай максимально коротко, 1-3 речення. Це обов'язкова вимога!"`

### Task 4: Update scheduling instructions
**File:** `src/sales_agent/agent/telegram_agent.py`
**Changes:**
- Lines 230-232: Simplify follow-up intent examples
- Lines 249-252: Already short, keep as-is

## Files to Modify

1. `.claude/skills/tone-of-voice/SKILL.md` - Add brevity section
2. `.claude/skills/how-to-communicate/SKILL.md` - Add principle #13
3. `src/sales_agent/agent/telegram_agent.py` - Update system prompt (line 287)

## Acceptance Criteria

1. All three files contain explicit "1-3 речення" instruction
2. System prompt clearly states brevity as critical requirement
3. Skills reinforce concise communication pattern
4. No breaking changes to existing functionality
