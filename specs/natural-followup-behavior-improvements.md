# Plan: Natural Follow-up Behavior Improvements

## Task Description
Improve the smart follow-up system to behave more naturally and fluently. The current implementation has three issues:
1. Follow-ups repeat the exact same message stored in `message_template` without considering conversation evolution
2. When scheduling a follow-up via tool use, the agent doesn't always confirm to the user that it will text them at the desired time
3. When the user responds with short acknowledgments like "ok", the agent responds immediately instead of pausing like a human would

## Objective
Make the follow-up system feel natural by:
1. Ensuring follow-ups regenerate messages based on current context (only ~5% of conversations need scheduled follow-ups)
2. Always confirming scheduled follow-up times to users
3. Handling acknowledgment messages ("ok", "понял", thumbs up) with human-like pauses or reactions instead of immediate responses

## Problem Statement

### Issue 1: Static Message Templates
- **Location**: `run_daemon.py:520` - Uses stored `message_template` verbatim
- **Problem**: When the agent schedules a follow-up, it stores a pre-written message. Hours or days later, this exact message is sent without considering:
  - Changes in conversation context
  - Information the client may have provided since scheduling
  - The natural evolution of a conversation
- **Current Code**:
  ```python
  message = action.payload.get("message_template")  # Uses static template
  if not message:
      # Fallback only if template is missing
      context = self.prospect_manager.get_conversation_context(...)
      response = await self.agent.generate_follow_up(...)
  ```

### Issue 2: Missing Follow-up Confirmation
- **Location**: `run_daemon.py:327` - Only sends confirmation if `action.message` exists
- **Problem**: Claude sometimes returns only a `tool_use` block without accompanying text, resulting in no confirmation to the user
- **Current Code**:
  ```python
  if action.message:  # May be None if Claude didn't include text
      result = await self.service.send_message(...)
  ```

### Issue 3: No Acknowledgment Handling
- **Location**: `telegram_agent.py:267-272` - Only handles spam as "wait"
- **Problem**: The agent doesn't differentiate between substantive responses and simple acknowledgments. When a user says "ok" after the agent asks a question, the agent fires another message instead of waiting for the actual answer
- **Current System Prompt**:
  ```
  ## Когда НЕ Отвечать
  - Спам или нерелевантные сообщения → верни action="wait"
  ```
  Missing: handling for "ok", "понял", "хорошо", emoji acknowledgments

## Solution Approach

### Approach 1: Intent-Based Follow-ups (Lazy Generation)
Instead of storing the exact message to send, store the **intent** of the follow-up. At execution time, regenerate a fresh message based on current conversation state.

**Benefits**:
- Messages are always contextually relevant
- Handles conversation evolution naturally
- More human-like follow-up behavior

### Approach 2: Guaranteed Confirmation
Add a fallback confirmation message when the agent uses the schedule_followup tool but doesn't include text.

**Benefits**:
- User always knows their request was understood
- Consistent UX

### Approach 3: Acknowledgment Detection in System Prompt
Add explicit instructions for handling short acknowledgments, teaching the agent to return `action="wait"` for these messages.

**Benefits**:
- No code changes required (prompt-only solution)
- Agent learns to pause naturally
- Respects conversational turn-taking

## Relevant Files

### Files to Modify

- `.claude/skills/telegram/scripts/telegram_agent.py`
  - Lines 30-64: Update `SCHEDULE_FOLLOWUP_TOOL` schema to use `follow_up_intent` instead of `message_template`
  - Lines 213-227: Update follow-up scheduling instructions
  - Lines 267-272: Add acknowledgment handling instructions
  - Lines 367: Change prompt opening to remove response bias
  - Lines 408-446: Update `generate_follow_up()` to accept intent parameter

- `.claude/skills/telegram/scripts/run_daemon.py`
  - Lines 299-344: Update schedule_followup handler to store intent, add fallback confirmation
  - Lines 519-534: Change to always regenerate messages using stored intent as context

- `.claude/skills/telegram/scripts/models.py`
  - Lines 138-143: Update `ScheduleFollowupToolInput` model to use `follow_up_intent`

### Files for Reference (No Changes)

- `.claude/skills/telegram/scripts/scheduled_action_manager.py` - Database persistence (payload is JSONB, no schema change needed)
- `.claude/skills/telegram/scripts/scheduler_service.py` - Execution timing logic
- `.claude/skills/telegram/scripts/prospect_manager.py` - Conversation context retrieval

## Implementation Phases

### Phase 1: Acknowledgment Handling (System Prompt Changes)
Low-risk, high-impact. Teaches the agent when NOT to respond.

### Phase 2: Guaranteed Confirmation
Medium-risk. Ensures users always get feedback when scheduling.

### Phase 3: Intent-Based Follow-ups
Higher complexity. Changes the follow-up generation architecture.

## Step by Step Tasks

### 1. Add Acknowledgment Handling to System Prompt
Update `telegram_agent.py` to teach the agent to pause on acknowledgments.

**In `_build_system_prompt()` method (around line 267):**

Add after "Когда НЕ Отвечать" section:

```python
## Когда ПОДОЖДАТЬ (action="wait")

Если клиент отправил короткое подтверждение БЕЗ новой информации:
- "ок", "ok", "хорошо", "понял", "ладно", "принял", "да", "угу", "ага"
- Эмодзи: 👍, 👌, ✅, 🙏, 😊
- Просто подтверждение получения (без вопроса или деталей)

В таких случаях:
- НЕ отвечай сразу, верни action="wait"
- Дай клиенту время написать следующее сообщение
- Особенно если ты только что задала вопрос и ждёшь ответа

Пример:
Ты: "Какой у вас бюджет на покупку?"
Клиент: "ок, сейчас посмотрю"
→ action="wait" (клиент подтвердил, что ответит - жди)

Ты: "Какой у вас бюджет на покупку?"
Клиент: "около 500к"
→ action="reply" (это ответ, продолжай диалог)
```

- Edit file: `.claude/skills/telegram/scripts/telegram_agent.py`
- Insert after line 272 (after spam handling)
- Rationale: Explicit instructions help the LLM differentiate acknowledgments from substantive responses

### 2. Update User Prompt to Remove Response Bias
Change the prompt from demanding a response to being analytical.

**In `generate_response()` method (line 367):**

Change from:
```python
user_prompt = f"""Клиент написал сообщение. Нужно ответить.
```

To:
```python
user_prompt = f"""Клиент написал сообщение. Проанализируй и реши, нужно ли отвечать.
```

- Edit file: `.claude/skills/telegram/scripts/telegram_agent.py`
- Line 367
- Rationale: Removes implicit bias toward always responding

### 3. Update Schedule Followup Tool Schema
Change `message_template` to `follow_up_intent` to store intent rather than verbatim message.

**In `SCHEDULE_FOLLOWUP_TOOL` (lines 30-64):**

Change the input schema:
```python
SCHEDULE_FOLLOWUP_TOOL = {
    "name": "schedule_followup",
    "description": """Schedule a follow-up message to be sent at a specific time in the future.

Use this tool when the client asks to be contacted later with phrases like:
- "напиши через 2 часа" (write in 2 hours)
- "свяжись завтра" (contact tomorrow)
- "в воскресенье" (on Sunday)
- "через неделю" (in a week)

Parse the time expression from the client's message and convert it to an exact datetime.

IMPORTANT:
- Always confirm the scheduled time to the client in your response text
- Use ISO 8601 format for follow_up_time (e.g., "2026-01-20T10:00:00+08:00")
- The follow_up_intent should describe WHAT to follow up about, not the exact message""",
    "input_schema": {
        "type": "object",
        "properties": {
            "follow_up_time": {
                "type": "string",
                "description": "ISO 8601 datetime when to send the follow-up (e.g., '2026-01-20T10:00:00+08:00')"
            },
            "follow_up_intent": {
                "type": "string",
                "description": "Brief description of what to follow up about (e.g., 'check if still interested in Canggu villa', 'remind about budget discussion'). NOT the exact message."
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation of why this follow-up is scheduled"
            }
        },
        "required": ["follow_up_time", "follow_up_intent", "reason"]
    }
}
```

- Edit file: `.claude/skills/telegram/scripts/telegram_agent.py`
- Lines 30-64
- Rationale: Stores intent rather than verbatim message, enabling context-aware regeneration

### 4. Update System Prompt Scheduling Instructions
Update the follow-up planning section to match new intent-based approach.

**In scheduling instructions (around lines 213-227):**

Update to:
```python
## Планирование follow-up

Текущее время (Бали, UTC+8): {current_bali_time}

Когда клиент просит связаться позже, используй tool schedule_followup:
- "напиши через 2 часа" → schedule_followup с временем +2 часа от текущего
- "завтра" → schedule_followup на завтра 10:00
- "в воскресенье" → ближайшее воскресенье 10:00
- "через неделю" → +7 дней, 10:00

ОБЯЗАТЕЛЬНО:
1. Подтверди клиенту время в тексте ответа: "Хорошо, напишу вам [когда]!"
2. Вызови schedule_followup с точным временем в ISO 8601 формате
3. В follow_up_intent опиши О ЧЁМ напомнить (не сам текст сообщения!)

Пример follow_up_intent:
- "уточнить интерес к вилле в Чангу после паузы"
- "напомнить о консультации по финансам"
- "проверить готовность к Zoom звонку"

ВАЖНО: follow_up сообщения будут генерироваться ЗАНОВО в момент отправки,
с учётом актуального контекста разговора. Укажи только намерение.
```

- Edit file: `.claude/skills/telegram/scripts/telegram_agent.py`
- Lines 213-227
- Rationale: Explains new intent-based approach to the LLM

### 5. Add Fallback Confirmation in Daemon
Ensure users always get confirmation when scheduling follow-ups.

**In schedule_followup handler (around lines 326-340):**

Change from:
```python
if action.message:
    result = await self.service.send_message(...)
```

To:
```python
# Always send confirmation - use agent's text or generate fallback
confirmation = action.message
if not confirmation:
    # Generate fallback confirmation with formatted time
    bali_tz = pytz.timezone("Asia/Makassar")
    scheduled_local = scheduled_for.astimezone(bali_tz)
    formatted_time = scheduled_local.strftime("%d.%m в %H:%M")
    confirmation = f"Хорошо, напишу вам {formatted_time}! 👍"

result = await self.service.send_message(
    prospect.telegram_id,
    confirmation
)
```

- Edit file: `.claude/skills/telegram/scripts/run_daemon.py`
- Lines 326-340
- Add import: `import pytz` (if not already present)
- Rationale: User always gets feedback that their request was understood

### 6. Update Payload Storage for Intent
Change what we store when scheduling a follow-up.

**In schedule_followup handler (around lines 306-316):**

Change from:
```python
payload={
    "message_template": action.scheduling_data.get("message_template"),
    "reason": action.scheduling_data.get("reason"),
    "conversation_context": context[:1000]
}
```

To:
```python
payload={
    "follow_up_intent": action.scheduling_data.get("follow_up_intent"),
    "reason": action.scheduling_data.get("reason"),
    "original_context_snapshot": context[:1000]  # For reference, not for sending
}
```

- Edit file: `.claude/skills/telegram/scripts/run_daemon.py`
- Lines 306-316
- Rationale: Stores intent instead of static message

### 7. Update Follow-up Execution to Always Regenerate
Change execution to always generate a fresh message using stored intent.

**In `execute_scheduled_action()` method (around lines 519-534):**

Change from:
```python
message = action.payload.get("message_template")

if not message:
    # Fallback: generate fresh follow-up message
    context = self.prospect_manager.get_conversation_context(prospect.telegram_id)
    response = await self.agent.generate_follow_up(prospect, context)
    ...
```

To:
```python
# Always regenerate message fresh using current context + stored intent
follow_up_intent = action.payload.get("follow_up_intent", "general check-in")
original_reason = action.payload.get("reason", "scheduled follow-up")

# Get fresh conversation context
context = self.prospect_manager.get_conversation_context(prospect.telegram_id)

# Generate contextual follow-up with intent guidance
response = await self.agent.generate_follow_up(
    prospect,
    context,
    follow_up_intent=follow_up_intent
)

if response.action == "reply" and response.message:
    message = response.message
elif response.action == "wait":
    console.print(f"[yellow]Agent decided not to follow up with {prospect.name}: {response.reason}[/yellow]")
    return
else:
    console.print(f"[yellow]Unexpected action from follow-up generation: {response.action}[/yellow]")
    return
```

- Edit file: `.claude/skills/telegram/scripts/run_daemon.py`
- Lines 519-534
- Rationale: Always generates fresh, contextual message

### 8. Update generate_follow_up Method Signature
Add optional `follow_up_intent` parameter.

**In `generate_follow_up()` method (lines 408-446):**

Change signature and update prompt:
```python
async def generate_follow_up(
    self,
    prospect: Prospect,
    conversation_context: str = "",
    follow_up_intent: str = ""
) -> AgentAction:
    """Generate a follow-up message for a non-responsive prospect.

    Args:
        prospect: The prospect to follow up with
        conversation_context: Recent conversation history
        follow_up_intent: Optional intent/topic for the follow-up (from scheduled action)
    """

    follow_up_number = prospect.message_count

    # Build intent context if provided
    intent_guidance = ""
    if follow_up_intent:
        intent_guidance = f"""
Запланированная цель follow-up:
"{follow_up_intent}"

Учитывай эту цель, но адаптируй сообщение под ТЕКУЩИЙ контекст разговора.
Если цель уже неактуальна (например, клиент уже ответил на вопрос),
напиши что-то более подходящее или верни action="wait".
"""

    user_prompt = f"""Клиент не отвечает. Нужно написать follow-up сообщение.

Информация о клиенте:
- Имя: {prospect.name}
- Контекст: {prospect.context}
- Уже отправлено сообщений: {prospect.message_count}
- Последний контакт: {prospect.last_contact}

История переписки:
{conversation_context if conversation_context else "Пока только наше первое сообщение."}

{intent_guidance}

Это будет {follow_up_number + 1}-е сообщение.

Правила:
- 2-е сообщение: мягкое напоминание + предложение консультации
- 3-е сообщение: проявление заботы + вопрос об актуальности
- 4+ сообщение: возможно, стоит остановиться (верни action="wait")

ВАЖНО: Сообщение должно быть естественным и учитывать ТЕКУЩИЙ контекст,
а не просто повторять предыдущие сообщения.

Верни JSON с решением.
"""
    # ... rest of method unchanged
```

- Edit file: `.claude/skills/telegram/scripts/telegram_agent.py`
- Lines 408-446
- Rationale: Enables passing intent from scheduled actions while maintaining backward compatibility

### 9. Update Pydantic Model (Optional)
Update the input model for type safety.

**In `models.py` (lines 138-143):**

Change from:
```python
class ScheduleFollowupToolInput(BaseModel):
    """Input schema for schedule_followup tool call."""
    follow_up_time: datetime
    message_template: str
    reason: str
```

To:
```python
class ScheduleFollowupToolInput(BaseModel):
    """Input schema for schedule_followup tool call."""
    follow_up_time: datetime
    follow_up_intent: str  # Changed from message_template
    reason: str
```

- Edit file: `.claude/skills/telegram/scripts/models.py`
- Lines 138-143
- Rationale: Type consistency with new schema

## Testing Strategy

### Manual Testing Scenarios

1. **Acknowledgment Handling Test**
   - Send a question to the user
   - Have user respond "ok" or 👍
   - Verify agent returns `action="wait"` (no immediate response)
   - Have user send actual answer
   - Verify agent responds normally

2. **Follow-up Scheduling Confirmation Test**
   - Have user say "напиши мне через 2 часа"
   - Verify user receives confirmation like "Хорошо, напишу вам в 14:30!"
   - Verify this works even if Claude only returns tool_use block

3. **Intent-Based Follow-up Test**
   - Schedule a follow-up with intent "check interest in Canggu villa"
   - Wait for follow-up execution
   - Verify message is freshly generated, not a static template
   - Verify message references current conversation context

4. **Context Evolution Test**
   - Schedule follow-up about topic A
   - Before follow-up fires, have conversation evolve to topic B
   - Verify follow-up adapts to new context or decides not to send

### Edge Cases

- User responds immediately after scheduling (follow-up should be cancelled)
- Multiple follow-ups scheduled for same prospect
- Follow-up fires when prospect status changed to ZOOM_SCHEDULED
- Human operator takes over before follow-up fires

## Acceptance Criteria

- [ ] Agent returns `action="wait"` for acknowledgment messages ("ok", "понял", 👍, etc.)
- [ ] User ALWAYS receives confirmation when scheduling a follow-up
- [ ] Scheduled follow-ups generate fresh messages based on current context
- [ ] Stored payload contains `follow_up_intent` instead of `message_template`
- [ ] Follow-up messages are contextually relevant, not repetitive
- [ ] Backward compatibility: existing scheduled actions with `message_template` still work
- [ ] Agent can decide NOT to follow up if context changed significantly

## Validation Commands

Execute these commands to validate the task is complete:

```bash
# 1. Syntax check all modified files
uv run python -m py_compile .claude/skills/telegram/scripts/telegram_agent.py
uv run python -m py_compile .claude/skills/telegram/scripts/run_daemon.py
uv run python -m py_compile .claude/skills/telegram/scripts/models.py

# 2. Verify agent initialization works
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.claude/skills/telegram/scripts')))
from telegram_agent import TelegramAgent, SCHEDULE_FOLLOWUP_TOOL
print('Tool schema:', SCHEDULE_FOLLOWUP_TOOL['input_schema']['properties'].keys())
assert 'follow_up_intent' in SCHEDULE_FOLLOWUP_TOOL['input_schema']['properties'], 'Missing follow_up_intent'
print('OK: Tool schema updated correctly')
"

# 3. Verify system prompt contains acknowledgment handling
uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path('.claude/skills/telegram/scripts')))
from telegram_agent import TelegramAgent
from models import AgentConfig
agent = TelegramAgent(
    tone_of_voice_path=Path('.claude/skills/tone-of-voice'),
    config=AgentConfig()
)
assert 'ПОДОЖДАТЬ' in agent.system_prompt or 'подтверждение' in agent.system_prompt, 'Missing acknowledgment instructions'
print('OK: System prompt contains acknowledgment handling')
"

# 4. Run daemon in dry-run mode (if available)
# uv run python .claude/skills/telegram/scripts/run_daemon.py --dry-run
```

## Notes

### Backward Compatibility
- Existing scheduled actions with `message_template` in payload will still work
- The execution code should check for both `message_template` (legacy) and `follow_up_intent` (new)
- Add fallback: `follow_up_intent = action.payload.get("follow_up_intent") or action.payload.get("message_template", "")`

### Performance Considerations
- Fresh message generation means one additional Claude API call per scheduled follow-up
- This is acceptable given follow-ups are rare events (~5% of conversations)
- Trade-off is worth it for improved message quality

### Monitoring
- Consider adding logging to track:
  - How often acknowledgments trigger `action="wait"`
  - Follow-up regeneration success rate
  - Fallback confirmation usage frequency

### Related Documentation
- Previous specs: `specs/scheduled-follow-ups-and-smart-reminders.md`
- Test plan: `specs/test-smart-followups-quick-validation.md`

### Dependencies
- No new dependencies required
- Uses existing `pytz` for timezone formatting in fallback confirmation
