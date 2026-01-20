# Plan: Telegram Communicator Audit Review

## Task Description
Comprehensive audit of the Telegram communicator/agent implementation to verify:
- Whether all components are used optimally
- Whether all needed context is included
- Context quality assessment
- Identification of any strange or suboptimal behaviors

## Objective
Document the current state of the Telegram agent, identify any issues or optimization opportunities, and provide actionable recommendations for improvement.

## Problem Statement
The Telegram agent is a critical sales automation component that uses Claude AI to communicate with prospects. We need to ensure that:
1. The forking/spawning architecture is correct and efficient
2. All necessary context is included in AI prompts
3. Context quality is high and token-efficient
4. No strange behaviors or bugs exist in the implementation

## Solution Approach
This is an **audit/review task** (not an implementation task). The findings below document the current state and provide recommendations.

---

## Relevant Files

### Core Implementation Files

- **`.claude/skills/telegram/scripts/run_daemon.py`** (506 lines)
  - Main entry point and daemon orchestration
  - Event handler registration at lines 133-305
  - Agent initialization at lines 104-112
  - Message processing pipeline

- **`.claude/skills/telegram/scripts/telegram_agent.py`** (496 lines)
  - Claude AI integration and prompt construction
  - System prompt building at lines 118-232
  - Response generation at lines 261-337
  - Skill loading mechanism at lines 66-116

- **`.claude/skills/telegram/scripts/knowledge_loader.py`** (353 lines)
  - Knowledge base loading and topic detection
  - Token-aware context injection at lines 193-261
  - Topic keyword matching at lines 120-142

- **`.claude/skills/telegram/scripts/prospect_manager.py`** (303 lines)
  - Prospect state management and conversation history
  - Context retrieval at lines 244-260

- **`.claude/skills/telegram/scripts/telegram_service.py`** (217 lines)
  - Telegram API wrapper with human-like behavior
  - Message sending with typing simulation

- **`.claude/skills/telegram/scripts/models.py`** (104 lines)
  - Pydantic data models for prospects, actions, config

### Configuration Files

- **`.claude/skills/telegram/config/agent_config.json`** - Agent persona, timing, knowledge settings
- **`.claude/skills/telegram/config/sales_slots.json`** - Calendar template configuration
- **`.claude/skills/telegram/config/sales_slots_data.json`** - Dynamic slot availability
- **`.claude/skills/telegram/config/prospects.json`** - Prospect database

### Skill Files

- **`.claude/skills/tone-of-voice/SKILL.md`** + `references/` - HOW to communicate (style, 7 principles)
- **`.claude/skills/how-to-communicate/SKILL.md`** + `references/` - WHAT to communicate (BANT, scripts)

### Knowledge Base

- **`knowledge_base_final/00_MASTER_CHEATSHEET.md`** through **`11_CLIENT_TEMPLATES.md`** - 12 topic files

---

## Audit Findings

### 1. Architecture Assessment: SINGLE-PROCESS DAEMON ✅

**Finding**: The Telegram agent does NOT fork or spawn subprocesses. It uses a single-threaded async architecture.

**Architecture Flow**:
```
asyncio.run(main())
    └── TelegramDaemon()
        └── TelegramAgent (single instance, reused)
            └── Anthropic API calls per message
```

**Components**:
| Component | Pattern | Status |
|-----------|---------|--------|
| Agent Spawning | None - single instance | ✅ Correct |
| Subprocess Calls | None found | ✅ Correct |
| Task Creation | Direct awaits, no `create_task()` | ✅ Correct |
| Parallel Execution | None - sequential processing | ✅ Appropriate for use case |
| Message Handling | Event-driven via Telethon | ✅ Correct |

**Assessment**: The architecture is appropriate for a single-bot Telegram agent. No forking is needed as the system handles one message at a time with rate limiting.

---

### 2. Context Inclusion Assessment

**Finding**: The agent includes extensive context from multiple sources.

#### System Prompt (Static - Built Once)
| Component | Included | Token Limit |
|-----------|----------|-------------|
| Tone-of-voice skill | ✅ Always | Unbounded |
| How-to-communicate skill | ✅ Always | Unbounded |
| Master cheatsheet | ✅ Always | Unbounded |
| Scheduling instructions | ✅ Always | Hardcoded |
| Identity & persona | ✅ Always | Hardcoded |

#### User Prompt (Dynamic - Per Message)
| Component | Included | Token Limit |
|-----------|----------|-------------|
| Prospect name | ✅ Always | N/A |
| Prospect status | ✅ Always | N/A |
| Prospect context | ✅ Always | N/A |
| Message count | ✅ Always | N/A |
| Conversation history | ✅ Always | ⚠️ **UNBOUNDED** |
| Incoming message | ✅ Always | N/A |
| Knowledge base context | ✅ Conditional | 4000 tokens max |

**Code Reference** (`telegram_agent.py:299-337`):
```python
user_prompt = f"""Клиент написал сообщение. Нужно ответить.

Информация о клиенте:
- Имя: {prospect.name}
- Статус: {prospect.status}
- Контекст: {prospect.context}
- Кол-во сообщений от нас: {prospect.message_count}

История переписки:
{conversation_context if conversation_context else "Это первый ответ клиента."}

НОВОЕ сообщение от клиента:
"{incoming_message}"

{knowledge_context}
```

---

### 3. Context Quality Assessment

#### Excellent Practices ✅

1. **Dual-Skill Architecture**: Clear separation of HOW (tone-of-voice) vs WHAT (how-to-communicate)
2. **Token-Aware Knowledge Injection**: Uses tiktoken with cl100k_base encoding
3. **Intelligent Truncation**: Boundary-aware (paragraph > sentence > character)
4. **Priority-Based Loading**: Topics loaded in relevance order
5. **Name Placeholder System**: Dynamic `<Ваше_имя>`, `<Имя_клиента>` replacement
6. **Pydantic Models**: All data validated with type safety

#### Issues Found ⚠️

**ISSUE #1: Conversation History Unbounded (HIGH PRIORITY)**

- **Location**: `telegram_agent.py:308` and `prospect_manager.py:244-260`
- **Problem**: `conversation_context` passed directly to API without token limiting
- **Risk**: Long conversations (10+ exchanges) could overflow token budget
- **Impact**: API errors, truncated responses, or hallucinations

**Current Code** (`prospect_manager.py:244-260`):
```python
def get_conversation_context(self, telegram_id: int | str, limit: int = 20) -> str:
    """Get formatted conversation history for LLM context."""
    messages = prospect.conversation_history[-limit:]  # 20 message limit only
    # No token awareness!
```

**ISSUE #2: Simple Keyword Matching (LOW PRIORITY)**

- **Location**: `knowledge_loader.py:120-142`
- **Problem**: Topic detection uses substring matching
- **Risk**: "region" matches "regional", possible false positives
- **Impact**: Slightly suboptimal topic selection

**ISSUE #3: No Context Metrics (LOW PRIORITY)**

- **Location**: N/A - missing feature
- **Problem**: No visibility into system prompt size or token usage
- **Risk**: Hard to debug context-related issues
- **Impact**: Difficult to optimize without data

---

### 4. Strange Behaviors Assessment

**Finding**: No strange behaviors detected. The implementation is clean and follows good practices.

**Verified Working Correctly**:
- ✅ Rate limiting (3 messages/day/prospect)
- ✅ Working hours respect
- ✅ Escalation keyword detection
- ✅ Human-like typing simulation and delays
- ✅ Graceful shutdown (SIGTERM/SIGINT handling)
- ✅ Prospect state persistence (JSON)
- ✅ Name placeholder sanitization
- ✅ JSON response parsing with fallback escalation

---

## Step by Step Tasks

### 1. Add Conversation History Token Limiting (HIGH PRIORITY)

**Why**: Prevents token overflow in long conversations

- Add `max_conversation_tokens: int = 3000` to `AgentConfig` model in `models.py:96`
- Add `"max_conversation_tokens": 3000` to `agent_config.json`
- Implement `_truncate_conversation_history()` method in `telegram_agent.py`
- Apply truncation before API call at `telegram_agent.py:308`
- Truncate from beginning (keep recent messages for relevance)
- Add truncation marker `[История обрезана...]` for transparency

### 2. Add Context Metrics Method (LOW PRIORITY)

**Why**: Enables visibility into prompt sizes for debugging

- Add `get_context_metrics()` method to `TelegramAgent` class
- Return dict with system_prompt_tokens, component flags, and token limits
- Optionally log metrics on agent initialization

### 3. Improve Topic Detection Accuracy (LOW PRIORITY)

**Why**: Reduces false positive topic matches

- Consider word boundary matching instead of substring
- Or implement stemming for Russian language keywords
- Current impact is minimal - only suggestion

---

## Acceptance Criteria

- [x] Architecture is appropriate (single-process daemon - CONFIRMED)
- [x] All needed context is included (skills, knowledge, history - CONFIRMED)
- [ ] Conversation history has token protection (NEEDS IMPLEMENTATION)
- [x] No strange behaviors detected (CONFIRMED)
- [x] Knowledge base injection is token-aware (CONFIRMED with 4000 token limit)
- [x] Name placeholders work correctly (CONFIRMED)
- [x] Escalation keywords trigger properly (CONFIRMED)

---

## Validation Commands

Execute these commands to validate the implementation:

```bash
# Check agent configuration
cat .claude/skills/telegram/config/agent_config.json | uv run python -m json.tool

# Verify skill files exist
ls -la .claude/skills/tone-of-voice/
ls -la .claude/skills/how-to-communicate/

# Verify knowledge base files exist
ls -la knowledge_base_final/

# Run agent with verbose logging (if implemented)
cd .claude/skills/telegram/scripts && uv run python -c "
from telegram_agent import TelegramAgent
from pathlib import Path
agent = TelegramAgent(
    tone_of_voice_path=Path('../../tone-of-voice'),
    how_to_communicate_path=Path('../../how-to-communicate'),
    knowledge_base_path=Path('../../../../knowledge_base_final')
)
print(f'System prompt length: {len(agent.system_prompt)} chars')
"
```

---

## Summary

### What's Working Excellently ✅

1. **Architecture**: Single-process async daemon is appropriate
2. **Context Sources**: All relevant context is included (skills, knowledge, history, prospect data)
3. **Knowledge Management**: Token-aware with intelligent truncation
4. **Name Safety**: Placeholder system prevents hardcoded names
5. **Human Simulation**: Typing delays and rate limiting
6. **Configuration**: Well-structured JSON configs

### What Needs Improvement ⚠️

| Issue | Priority | Effort | Impact |
|-------|----------|--------|--------|
| Conversation history unbounded | HIGH | Low | Prevents token overflow |
| No context metrics | LOW | Low | Better debugging |
| Substring keyword matching | LOW | Medium | Marginal accuracy improvement |

### Recommendation

Implement **Issue #1 (conversation history token limiting)** as a quick win. The fix is straightforward:
1. Add config field for `max_conversation_tokens`
2. Add truncation method that keeps recent messages
3. Apply before API call

The other issues are low priority enhancements that can be addressed later.

---

## Notes

- All paths in agent_config.json are relative to `.claude/skills/telegram/config/`
- Token counting uses tiktoken with cl100k_base encoding (Claude standard)
- The daemon runs with `asyncio.run(main())` - not as a background service
- Mock Zoom scheduling is used (no actual Zoom API integration)
- If implementing conversation history truncation, use `tiktoken` for accurate token counting
