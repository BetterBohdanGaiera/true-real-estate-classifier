---
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Task
description: Run automated E2E conversation test via real Telegram - tests wait behavior, communication quality, timezone-aware scheduling, email collection, and Google Calendar event creation
model: opus
---

# Purpose

This command runs a fully automated end-to-end conversation test between the sales agent (@BetterBohdan) and the test prospect (@bohdanpytaichuk) via real Telegram. It validates five critical agent behaviors: (1) the agent respects "wait 2 minutes" requests and responds after the delay, (2) the agent communicates naturally throughout, (3) meeting time communication is high-quality including timezone conversion, (4) client email is successfully gathered, and (5) a Google Calendar event is created with an invite sent. Follow the `Instructions` and `Workflow` sections to execute the test.

## Variables

PROJECT_ROOT: /Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier
COMPOSE_FILE: deployment/docker/docker-compose.yml
PROSPECTS_FILE: .claude/skills/telegram/config/prospects.json
TEST_PROSPECT_USERNAME: bohdanpytaichuk
TEST_PROSPECT_TELEGRAM_ID: 7836623698
AGENT_USERNAME: BetterBohdan
E2E_PLAYER_SCRIPT: .claude/skills/testing/scripts/e2e_telegram_player.py
AGENT_SYSTEM_PROMPT: .claude/skills/telegram/config/agent_system_prompt.md
SCHEDULING_TOOL: src/telegram_sales_bot/scheduling/tool.py
GOOGLE_CALENDAR: src/telegram_sales_bot/integrations/google_calendar.py
MAX_RESPONSE_WAIT_SECONDS: 120
CONVERSATION_LANGUAGE: ru
TEST_CLIENT_TIMEZONE: Europe/Warsaw
TEST_CLIENT_EMAIL: bohdan.pytaichuk@gmail.com

## Instructions

- This command orchestrates a fully automated end-to-end conversation test over real Telegram infrastructure
- The test uses the E2ETelegramPlayer (`.claude/skills/testing/scripts/e2e_telegram_player.py`) to send messages AS @bohdanpytaichuk to the running agent @BetterBohdan
- The agent must already be running (either locally via daemon or via Docker) before this test starts
- The test follows a scripted conversation flow designed to validate five specific behaviors
- Each test phase has explicit PASS/FAIL criteria - the test is deterministic, not exploratory
- IMPORTANT: The conversation is conducted in Russian, matching the agent's configured language
- IMPORTANT: The test prospect must be reset to "new" status before starting so the agent sends its initial outreach
- IMPORTANT: After the test, collect and analyze the full chat history to produce a structured report
- The E2ETelegramPlayer uses the `test_prospect` Telethon session for authentication
- Between sending messages and checking for responses, use `wait_for_response()` with appropriate timeouts
- For the "wait 2 minutes" test, the timeout must be at least 150 seconds (2.5 min buffer)
- When checking Google Calendar event creation, use the CalendarConnector from `src/telegram_sales_bot/integrations/google_calendar.py`
- Email validation happens implicitly through the scheduling flow - the agent must ask for and correctly process the email
- Timezone test: the test prospect claims to be in Warsaw (UTC+1). The agent must display times in BOTH Warsaw and Bali timezones when scheduling

## Workflow

1. **Pre-flight checks:**
   - Verify Docker Desktop is running: `docker info --format '{{.ServerVersion}}'`
   - Verify the E2E player script exists at `E2E_PLAYER_SCRIPT`
   - Verify the test prospect Telethon session exists at `~/.telegram_dl/sessions/test_prospect.session`
   - Read `PROSPECTS_FILE` to confirm @bohdanpytaichuk exists

2. **Reset test environment:**
   - Edit `PROSPECTS_FILE`: set @bohdanpytaichuk status to `"new"`, clear conversation history, clear email, clear session_id
   - Stop any running containers: `docker compose -f deployment/docker/docker-compose.yml down -v`

3. **Start the agent:**
   - Start Docker containers in background: `docker compose -f deployment/docker/docker-compose.yml up --build -d postgres telegram-agent`
   - Wait 15 seconds for initialization
   - Verify containers are healthy: `docker compose -f deployment/docker/docker-compose.yml ps`
   - Begin tailing agent logs in a background shell for debugging: `docker compose -f deployment/docker/docker-compose.yml logs -f telegram-agent`

4. **Write and run the automated test script:**
   - Create a Python test script that uses E2ETelegramPlayer to execute the following conversation phases
   - The script must be run with: `PYTHONPATH=src uv run python <script_path>`
   - The script should produce structured JSON output for each phase

5. **Phase 1 - Initial Contact & Communication Quality (PASS/FAIL):**
   - Wait up to 90 seconds for the agent to send the initial outreach message to @bohdanpytaichuk
   - PASS criteria: Agent sends a message within 90s that is 1-3 sentences, uses formal "Вы", and contains a question
   - Record the initial message

6. **Phase 2 - Wait Behavior Test (PASS/FAIL):**
   - Send as prospect: "Интересно, но сейчас занят. Можете написать через 2 минуты?"
   - Start a timer
   - PASS criteria: Agent does NOT send any message for at least 100 seconds (respects the wait), THEN sends a follow-up message within 180 seconds total
   - Record timing: seconds_silent (must be >= 100), seconds_until_followup (must be <= 180)

7. **Phase 3 - Communication Quality & Engagement (PASS/FAIL):**
   - Send as prospect: "Да, вернулся. Рассматриваю инвестиции в недвижимость на Бали. Какая реальная доходность?"
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent responds with substantive content about ROI/yields, mentions company USPs (e.g., "140 пунктов", "Estate Market", "due diligence"), asks a follow-up question, message is 1-3 sentences
   - Send as prospect: "Бюджет около 300 тысяч долларов. Хочу что-то с гарантированной доходностью."
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent acknowledges the budget, continues natural dialogue, moves toward scheduling

8. **Phase 4 - Timezone-Aware Scheduling & Email Collection (PASS/FAIL):**
   - Send as prospect: "Ок, давайте созвонимся. Я в Варшаве."
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent acknowledges timezone (Warsaw/UTC+1 vs Bali/UTC+8) and asks for email
   - Send as prospect: "bohdan.pytaichuk@gmail.com"
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent shows available times with DUAL timezone display (both client's Warsaw time AND Bali time)
   - Send as prospect: "Завтра в 10:00 по моему времени подойдёт"
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent confirms the specific time with BOTH timezones shown (e.g., "10:00 вашего времени (17:00 Бали UTC+8)"), does NOT dump all available slots

9. **Phase 5 - Meeting Booking & Calendar Validation (PASS/FAIL):**
   - Send as prospect: "Да, записывайте!"
   - Wait for agent response (90s timeout - booking takes longer)
   - PASS criteria for message: Agent confirms meeting is scheduled, mentions the time, mentions the email, ideally includes Zoom link
   - Validate email was collected: Read `PROSPECTS_FILE` and check that @bohdanpytaichuk now has email field set to `bohdan.pytaichuk@gmail.com`
   - Validate Google Calendar: Use the CalendarConnector to check if a calendar event was created for tomorrow containing "bohdanpytaichuk" or "Богдан" in the summary/description AND has `bohdan.pytaichuk@gmail.com` as an attendee
   - PASS criteria: Email stored in prospect data AND calendar event exists with attendee invite

10. **Collect full conversation history:**
    - Use E2ETelegramPlayer's `get_chat_history("@BetterBohdan", limit=50)` to retrieve the complete conversation
    - Alternatively read Docker logs for the full agent-side view

11. **Cleanup:**
    - Stop Docker containers: `docker compose -f deployment/docker/docker-compose.yml down`
    - If a test Google Calendar event was created, delete it (ephemeral test)

## Report

Present results as a structured Rich panel report with the following sections:

**Test Results Summary Table:**
| Phase | Test | Status | Details |
|-------|------|--------|---------|
| 1 | Initial Contact | PASS/FAIL | Message received in Xs, length OK/too long, has question Y/N |
| 2 | Wait Behavior | PASS/FAIL | Silent for Xs (need >=100s), follow-up at Xs (need <=180s) |
| 3 | Communication Quality | PASS/FAIL | Substantive response Y/N, USPs mentioned Y/N, natural flow Y/N |
| 4 | Timezone & Email | PASS/FAIL | Dual timezone shown Y/N, email collected Y/N, specific time confirmed Y/N |
| 5 | Calendar & Booking | PASS/FAIL | Meeting confirmed Y/N, calendar event created Y/N, attendee invite Y/N |

**Overall Score:** X/5 phases passed

**Full Conversation Log:** Display the complete conversation with timestamps, labeling each message as [AGENT] or [PROSPECT]

**Timing Metrics:**
- Time to initial outreach: Xs
- Wait behavior: silent for Xs, follow-up at Xs
- Average response time: Xs
- Total test duration: Xs

**Issues Found:** List any failures with specific details about what went wrong and which agent behavior needs improvement

**Recommendations:** Based on failures, suggest concrete improvements to the agent system prompt, scheduling tool, or daemon configuration
