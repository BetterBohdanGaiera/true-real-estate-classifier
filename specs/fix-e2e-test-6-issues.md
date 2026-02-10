# Fix 6 E2E Automated Conversation Test Issues

## Objective
Fix 6 issues discovered during E2E automated Telegram conversation testing. The test validates agent behaviors across 5 phases: initial contact, wait behavior, communication quality, timezone-aware scheduling, and calendar booking.

## Issues Summary
1. Replace @bohdanpytaichuk with @buddah_lucid as permanent test prospect
2. Agent proposes Zoom too fast after learning budget - needs BANT qualification
3. Capitalized day names in scheduling slots look robotic
4. Agent response timeout too short for check_availability action
5. Test script sends message too early in Phase 2 (breaks wait behavior test)
6. Test script should delete all messages before starting (clean slate)

---

## Issue 1: Update Default Test Prospect Config

**Problem:** @bohdanpytaichuk (telegram_id: 7836623698) is no longer accessible. Replace with @buddah_lucid (telegram_id: 8503958942) everywhere.

**Files to modify:**
- `CLAUDE.md` - Update Manual Testing section
- `.claude/commands/telegram_conversation_automatic_test.md` - Update variables
- `.claude/commands/telegram_conversation_manual_test.md` - Update variables
- `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Already uses buddah_lucid session but references bohdanpytaichuk for prospect lookup

**Changes:**
1. `CLAUDE.md` lines 42-49: Replace @bohdanpytaichuk/7836623698 with @buddah_lucid/8503958942
2. `telegram_conversation_automatic_test.md` lines 16-17: Change TEST_PROSPECT_USERNAME and TEST_PROSPECT_TELEGRAM_ID
3. `telegram_conversation_manual_test.md` line 15: Change TEST_PROSPECT_USERNAME
4. `run_e2e_auto_test.py`: The script already uses `session_name="buddah_lucid"` and checks for `"buddah_lucid"` in prospects.json (line 395). No changes needed in the test script itself for this issue.

---

## Issue 2: Agent Proposes Zoom Too Fast (BANT Qualification)

**Problem:** After the prospect shares their budget ($300k), the agent immediately proposes a Zoom call. It should first qualify the lead with 2-3 BANT questions (Timeline, Authority, specific preferences like apartment vs villa).

**File to modify:**
- `.claude/skills/telegram/config/agent_system_prompt.md` - Add BANT qualification gate before scheduling

**Changes:**
Add a new section after "## Твоя Задача" enforcing BANT qualification before proposing a Zoom call:

```markdown
## Квалификация Перед Zoom (ОБЯЗАТЕЛЬНО!)

КРИТИЧЕСКИ ВАЖНО: НЕ предлагай Zoom-звонок, пока не собрал минимум 2-3 из следующих данных:
- Budget (Бюджет): Сколько готов вложить?
- Authority (Полномочия): Принимает ли решение самостоятельно?
- Need (Потребность): Что конкретно ищет? (тип недвижимости, локация, цель - инвестиции/для себя)
- Timeline (Сроки): Когда планирует покупку?

ЗАПРЕЩЕНО предлагать созвон после одного только бюджета!

Правильный flow:
1. Клиент назвал бюджет → спроси про тип (апартаменты/вилла) и цель (инвестиция/для жизни)
2. Клиент ответил про тип → спроси про сроки или локацию
3. Есть 2-3 ответа из BANT → ТЕПЕРЬ можно предложить Zoom

ПЛОХО:
Клиент: "Бюджет 300к"
Ты: "Давайте созвонимся в Zoom!" ← ЗАПРЕЩЕНО! Ты ещё не знаешь что ему нужно

ХОРОШО:
Клиент: "Бюджет 300к"
Ты: "Хороший бюджет. Вы рассматриваете апартаменты или виллу? И для инвестиций или для жизни?"
Клиент: "Апартаменты, для инвестиций"
Ты: "Когда планируете покупку?"
Клиент: "В ближайшие 3 месяца"
Ты: "Отлично, у нас есть несколько проектов под ваш запрос. Предлагаю созвониться на 20 минут..."
```

---

## Issue 3: Capitalize Day Names in Slots

**Problem:** The scheduling tool outputs "Завтра (11 февраля)" and "Четверг (12 февраля)" with capital first letters. This looks robotic. Day names should be lowercase: "завтра (11 февраля)", "четверг (12 февраля)".

**File to modify:**
- `src/telegram_sales_bot/scheduling/tool.py` - `_format_date_russian()` method (lines 175-197) and `RUSSIAN_WEEKDAYS` dict (lines 79-87)

**Changes:**
1. Change `RUSSIAN_WEEKDAYS` values to lowercase:
   ```python
   RUSSIAN_WEEKDAYS = {
       0: "понедельник",
       1: "вторник",
       2: "среда",
       3: "четверг",
       4: "пятница",
       5: "суббота",
       6: "воскресенье"
   }
   ```
2. Change `_format_date_russian()` return values to use lowercase:
   - `"Сегодня (...)"` → `"сегодня (...)"`
   - `"Завтра (...)"` → `"завтра (...)"`
   - Weekday names already lowercase from dict change

3. Also update `confirm_time_slot()` (line 1022) which uses `_format_date_russian()` in "К сожалению, ..." message - since it now returns lowercase, the sentence beginning will be handled by the agent's natural language. The "К сожалению, " prefix already handles the sentence start.

---

## Issue 4: Agent Response Timeout for check_availability

**Problem:** When the agent calls `check_availability`, the daemon processes it synchronously: it calls `scheduling_tool.get_available_times()` or `confirm_time_slot()`, then sends the message. The issue is that the **test script** waits only 90s for responses in Phase 4, but the agent's LLM generation + calendar API lookup can take longer.

Looking at daemon.py, there is no explicit timeout on the `check_availability` handling. The latency comes from:
1. LLM generation time (agent decides `check_availability`)
2. Calendar API call (`get_available_slots_from_calendar`)
3. Formatting and sending

**Files to modify:**
- `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Increase Phase 4 response timeouts from 90s to 120s for scheduling-related responses

**Changes:**
In `run_phase_4()`:
- Line 283: `timeout=90.0` → `timeout=120.0` (response after "давайте созвонимся")
- Line 302: `timeout=90.0` → `timeout=120.0` (response after email)
- Line 329: `timeout=90.0` → `timeout=120.0` (response after time proposal)

---

## Issue 5: Test Script Sends Message Too Early in Phase 2

**Problem:** In Phase 2 (wait behavior), after the prospect sends "Можете написать через 2 минуты?", the test script detects the agent's acknowledgment ("Хорошо, через 2 минуты напишу!") and then Phase 3 immediately starts by sending "Да, вернулся...". This breaks the wait test because:
- The agent acknowledged at 32.3s (premature - issue in itself)
- Then the test immediately sends the next message, so the agent never gets to actually wait and send a scheduled follow-up

**Current flow (broken):**
1. Prospect: "Можете написать через 2 минуты?"
2. Agent: "Хорошо, через 2 минуты напишу!" (at 32s - too early, BUT this is the followup confirmation, not a premature response to the content)
3. Test immediately proceeds to Phase 3: "Да, вернулся..."

**Correct flow:**
1. Prospect: "Можете написать через 2 минуты?"
2. Agent: "Хорошо, через 2 минуты напишу!" (this is the acknowledgment + schedule_followup action)
3. Test WAITS SILENTLY for ~120-180s for the agent's scheduled follow-up message
4. Agent sends follow-up: "Привет! Как обещал(а), пишу..." (after ~2 minutes)
5. Test detects follow-up, PASS, then proceeds to Phase 3

**File to modify:**
- `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Rewrite `run_phase_2()`

**Changes:**
Rewrite Phase 2 logic:
1. Send "Можете написать через 2 минуты?"
2. Wait for first agent response (timeout 60s) - this should be the acknowledgment like "Хорошо, через 2 минуты!"
3. Record acknowledgment, start timer
4. Now WAIT PASSIVELY for 180s for the scheduled follow-up message (NO sending from prospect side)
5. The follow-up must arrive between 100-180s after the acknowledgment
6. PASS: acknowledgment received + follow-up received between 100-180s
7. FAIL: no acknowledgment, or no follow-up, or follow-up too early (< 100s)
8. Phase 3 starts AFTER Phase 2 completes (no "Да, вернулся..." message - Phase 3 has its own messages)

---

## Issue 6: Delete All Messages Before Test (Clean Slate)

**Problem:** Old messages from previous test runs remain in the chat, which can confuse the agent's conversation context. Need to delete all messages before starting.

**File to modify:**
- `.claude/skills/testing/scripts/run_e2e_auto_test.py` - Add cleanup step in `main()` before Phase 1

**Changes:**
Add a `cleanup_chat()` function that:
1. Uses the E2ETelegramPlayer to get full chat history (limit=100)
2. Deletes all messages from BOTH sides (prospect's own messages using `client.delete_messages`, and agent messages using `client.delete_messages` with `revoke=True`)
3. Called in `main()` right after `player.connect()` and before Phase 1

Note: Telethon's `client.delete_messages()` can delete messages in a private chat. For messages the user sent, they can delete for both sides. For messages received from others, deletion only removes from the user's side. This is fine for test isolation - the key is that the prospect's view is clean, and the agent daemon reads from prospects.json conversation_history which gets reset separately.

---

## File Modification Summary

| File | Issue(s) | Type |
|------|----------|------|
| `CLAUDE.md` | #1 | Edit |
| `.claude/commands/telegram_conversation_automatic_test.md` | #1 | Edit |
| `.claude/commands/telegram_conversation_manual_test.md` | #1 | Edit |
| `.claude/skills/telegram/config/agent_system_prompt.md` | #2 | Edit |
| `src/telegram_sales_bot/scheduling/tool.py` | #3 | Edit |
| `.claude/skills/testing/scripts/run_e2e_auto_test.py` | #4, #5, #6 | Edit |

**Total files to modify:** 6

## Batching Strategy

**Batch 1 (parallel, no dependencies):**
- `CLAUDE.md` (Issue #1)
- `.claude/commands/telegram_conversation_automatic_test.md` (Issue #1)
- `.claude/commands/telegram_conversation_manual_test.md` (Issue #1)
- `.claude/skills/telegram/config/agent_system_prompt.md` (Issue #2)
- `src/telegram_sales_bot/scheduling/tool.py` (Issue #3)
- `.claude/skills/testing/scripts/run_e2e_auto_test.py` (Issues #4, #5, #6)

All files can be modified in parallel since they have no code dependencies between changes.

## Acceptance Criteria

1. All references to @bohdanpytaichuk/7836623698 replaced with @buddah_lucid/8503958942
2. Agent system prompt includes BANT qualification gate requiring 2-3 qualification questions before Zoom proposal
3. `_format_date_russian()` and `RUSSIAN_WEEKDAYS` output lowercase day names
4. Test script Phase 4 uses 120s timeouts for scheduling responses
5. Test script Phase 2 waits passively for agent's scheduled follow-up (no premature prospect message)
6. Test script deletes all messages in chat before starting Phase 1
