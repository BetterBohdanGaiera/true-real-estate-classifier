---
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Task
description: Run automated E2E conversation test via real Telegram - tests Snake methodology, BANT qualification, objection handling, wait behavior, timezone-aware scheduling, email collection, and Google Calendar event creation
model: opus
---

# Purpose

This command runs a fully automated end-to-end conversation test between the sales agent (@BetterBohdan) and the test prospect (@buddah_lucid) via real Telegram. Unlike the short 5-phase version, this test validates the FULL sales qualification process using the "how to communicate" methodology:

- **Snake methodology** (Змейка): Light entry -> Reflection -> Expertise -> Next question
- **BANT qualification**: Budget, Authority, Need, Timeline - all 4 must be gathered before Zoom
- **Objection handling**: Client asks uncomfortable questions (bubble, leasehold, guarantees, "send catalog")
- **Pain summary before Zoom**: Agent must NOT jump to Zoom early - must summarize pains first
- **Natural communication**: No questionnaire-style, no long monologues, 1-3 sentences max
- **Wait behavior**: Respects "come back later" requests
- **Timezone-aware scheduling**: Client timezone display, email collection
- **Calendar event creation**: Google Calendar with attendee invite
- **Media understanding**: Agent analyzes photos via Gemini vision, transcribes voice messages

The conversation has 10 phases and ~18+ message exchanges, testing the agent's ability to handle a realistic, challenging client interaction.

## Variables

PROJECT_ROOT: /Users/bohdanpytaichuk/Documents/TrueRealEstate/Classifier
COMPOSE_FILE: deployment/docker/docker-compose.yml
PROSPECTS_FILE: .claude/skills/telegram/config/prospects.json
TEST_PROSPECT_USERNAME: buddah_lucid
TEST_PROSPECT_TELEGRAM_ID: 8503958942
AGENT_USERNAME: BetterBohdan
E2E_PLAYER_SCRIPT: .claude/skills/testing/scripts/e2e_telegram_player.py
E2E_AUTO_TEST_SCRIPT: .claude/skills/testing/scripts/run_e2e_auto_test.py
AGENT_SYSTEM_PROMPT: .claude/skills/telegram/config/agent_system_prompt.md
SCHEDULING_TOOL: src/telegram_sales_bot/scheduling/tool.py
GOOGLE_CALENDAR: src/telegram_sales_bot/integrations/google_calendar.py
MAX_RESPONSE_WAIT_SECONDS: 120
CONVERSATION_LANGUAGE: ru
TEST_CLIENT_TIMEZONE: Europe/Warsaw
TEST_CLIENT_EMAIL: bohdan.pytaichuk@gmail.com

## Instructions

- This command orchestrates a fully automated end-to-end conversation test over real Telegram infrastructure
- The test uses the E2ETelegramPlayer (`.claude/skills/testing/scripts/e2e_telegram_player.py`) to send messages AS @buddah_lucid to the running agent @BetterBohdan
- The agent must already be running (either locally via daemon or via Docker) before this test starts
- The test follows a scripted conversation flow designed to validate TEN specific behavioral areas
- Each test phase has explicit PASS/FAIL criteria - the test is deterministic, not exploratory
- IMPORTANT: The conversation is conducted in Russian, matching the agent's configured language
- IMPORTANT: The test prospect must be reset to "new" status before starting so the agent sends its initial outreach
- IMPORTANT: After the test, collect and analyze the full chat history to produce a structured report
- The E2ETelegramPlayer uses the `buddah_lucid` Telethon session for authentication
- Between sending messages and checking for responses, use `wait_for_response()` with appropriate timeouts
- For the "wait 2 minutes" test, the timeout must be at least 150 seconds (2.5 min buffer)
- When checking Google Calendar event creation, use the CalendarConnector from `src/telegram_sales_bot/integrations/google_calendar.py`
- Email validation happens implicitly through the scheduling flow - the agent must ask for and correctly process the email
- Timezone test: the test prospect claims to be in Warsaw (UTC+1). The agent must display times in the client's timezone (Warsaw)
- CRITICAL: The test validates that the agent does NOT jump to Zoom too early - it must complete BANT qualification and do a pain summary first

## Workflow

1. **Pre-flight checks:**
   - Verify Docker Desktop is running: `docker info --format '{{.ServerVersion}}'`
   - Verify the E2E player script exists at `E2E_PLAYER_SCRIPT`
   - Verify the test prospect Telethon session exists at `~/.telegram_dl/sessions/buddah_lucid.session`
   - Read `PROSPECTS_FILE` to confirm @buddah_lucid exists

2. **Reset test environment:**
   - Edit `PROSPECTS_FILE`: set @buddah_lucid status to `"new"`, clear conversation history, clear email, clear session_id
   - Stop any running containers: `docker compose -f deployment/docker/docker-compose.yml down -v`
   - Delete previous Telegram conversation to ensure clean slate (while containers are DOWN):
     ```
     PYTHONPATH=src uv run python -c "
     import asyncio, sys; sys.path.insert(0, '.claude/skills/testing/scripts')
     from e2e_telegram_player import E2ETelegramPlayer
     async def clean():
         player = E2ETelegramPlayer(session_name='buddah_lucid')
         await player.connect()
         entity = await player._resolve_entity('@BetterBohdan')
         ids = [m.id async for m in player.client.iter_messages(entity, limit=500)]
         if ids:
             for i in range(0, len(ids), 100):
                 await player.client.delete_messages(entity, ids[i:i+100])
         print(f'Deleted {len(ids)} messages')
         await player.disconnect()
     asyncio.run(clean())
     "
     ```

3. **Start the agent:**
   - Start Docker containers in background: `docker compose -f deployment/docker/docker-compose.yml up --build -d postgres telegram-agent`
   - Wait 15 seconds for initialization
   - Verify containers are healthy: `docker compose -f deployment/docker/docker-compose.yml ps`
   - Begin tailing agent logs in a background shell for debugging: `docker compose -f deployment/docker/docker-compose.yml logs -f telegram-agent`

4. **Run the automated test script:**
   - The test script is at `E2E_AUTO_TEST_SCRIPT`
   - Run with: `PYTHONPATH=src uv run python .claude/skills/testing/scripts/run_e2e_auto_test.py`
   - The script produces structured JSON output for each phase

5. **Phase 1 - Initial Contact & Snake Light Entry (PASS/FAIL):**
   - Wait up to 90 seconds for the agent to send the initial outreach message to @buddah_lucid
   - PASS criteria: Agent sends a message within 90s that is 1-3 sentences, uses formal "Вы", and contains an EASY opening question (Snake: light entry - "для себя или инвестиция?", "что привлекло?", etc.)
   - Record the initial message

6. **Phase 2 - Wait Behavior Test (PASS/FAIL):**
   - Send as prospect: "Интересно, но сейчас занят. Можете написать через 2 минуты?"
   - Start a timer
   - PASS criteria: Agent does NOT send any message for at least 100 seconds (respects the wait), THEN sends a follow-up message within 180 seconds total
   - Record timing: seconds_silent (must be >= 100), seconds_until_followup (must be <= 180)

7. **Phase 3 - ROI Question + "Bubble" Objection (PASS/FAIL):**
   - Send as prospect: "Да, вернулся. Рассматриваю инвестиции на Бали. Какая реальная доходность? Только честно, без маркетинговых сказок."
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent responds with substantive ROI content, backed by facts/sources (Estate Market, data), asks a follow-up question, 1-3 sentences
   - Send as prospect: "Я слышал что Бали - это мыльный пузырь. Все таксисты уже про это говорят. Почему я должен туда вкладывать?"
   - Wait for agent response (60s timeout)
   - PASS criteria (objection handling): Agent does NOT devalue client's opinion, addresses with FACTS (market limitations, data, 270M population), does NOT get defensive, shows empathy ("Понимаю опасения"), asks a follow-up question

8. **Phase 4 - Multi-Message Burst (PASS/FAIL):**
   - Send as prospect (rapid succession, 1-2s apart):
     1. "У меня несколько вопросов накопилось."
     2. "Во-первых, сколько реально стоит содержание виллы?"
     3. "Во-вторых, можно ли купить на компанию?"
     4. "И еще - как с визами для длительного проживания?"
   - Wait for agent response (60s timeout)
   - PASS criteria: Agent batches all messages (via MessageBuffer) and responds naturally, addressing at least 2 of 3 topics (villa maintenance costs, company purchase structure, visas for long-term stay). Response is coherent, 1-3 sentences, includes a follow-up question. No messages ignored, no crash.

9. **Phase 5 - Media Understanding: Image + Voice (PASS/FAIL):**
    - Send the test photo from `data/media_for_test/image.png` as a photo message (using E2ETelegramPlayer's `send_file()`)
    - Wait for agent response (90s timeout)
    - PASS criteria for photo: Agent responds with >20 chars, does NOT say "can't see/open", asks a relevant question about what's shown (rice terraces -> could reference the area, nature, etc.)
    - After 3s delay, send the test voice from `data/media_for_test/response.ogg` as a voice message (using `send_voice()`)
    - Wait for agent response (90s timeout)
    - PASS criteria for voice: Agent responds to the CONTENT of the voice (prospect talks about wanting to buy real estate in the region from the photo), does NOT mention "voice message" or "audio" (treats it as normal text), asks a follow-up question

10. **Phase 6 - BANT: Budget + Need + "Send Catalog" Objection (PASS/FAIL):**
    - Send as prospect: "Ладно, допустим. Бюджет у меня около 300 тысяч долларов. Хочу гарантированную доходность. Скиньте каталог посмотрю."
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent does NOT just agree to send catalog (anti-pattern #8). Agent should deflect "catalog" request ("Каталог не покажет подходящие варианты", "на зуме разберем аналитику"). Agent acknowledges budget, asks about type (apartments/villa) or purpose (investment/living). Agent does NOT invite to Zoom yet (too early - only has Budget so far!)
    - Send as prospect: "Ну ок, без каталога. Мне интересны апартаменты чисто как инвестиция, сам жить не планирую."
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent reflects the answer (Snake: reflection), adds brief expertise, asks next BANT question (Authority or Timeline). Still does NOT invite to Zoom.

11. **Phase 7 - BANT: Authority + Timeline + "Leasehold" Objection (PASS/FAIL):**
    - Send as prospect: "Решение принимаю сам, но жена тоже участвует в обсуждении. А leasehold - это же не настоящая собственность? Что если отберут?"
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent handles leasehold objection with FACTS (like London, 30+ years, legal protection), does NOT make up information, notes Authority (client + wife), asks about Timeline
    - Send as prospect: "Хочу купить в ближайшие 2-3 месяца. Но какие гарантии что застройщик не кинет?"
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent addresses guarantee concern with facts (notary, due diligence 140 points, we reject 90% of developers), acknowledges timeline. Now agent has full BANT (Budget: $300k, Authority: self+wife, Need: investment apartments, Timeline: 2-3 months). Agent should now do a PAIN SUMMARY before proposing Zoom.

12. **Phase 8 - Pain Summary & Zoom Proposal (PASS/FAIL):**
    - This is a CHECK on what the agent says AFTER Phase 7. The agent's response to Phase 7 should:
    - PASS criteria: Agent summarizes client's key points/pains BEFORE inviting to Zoom (e.g., "Итак, вас интересуют инвестиционные апартаменты, бюджет $300k, важна надёжность застройщика..."). Agent proposes Zoom WITH value explanation ("на встрече покажу аналитику по вашему запросу", "разберем конкретные проекты"). Agent proposes SPECIFIC time, not "when is convenient".
    - FAIL criteria: Agent jumps to Zoom without summary. Agent says generic "давайте созвонимся" without explaining value. Agent asks "когда удобно" without proposing times.
    - If agent hasn't proposed Zoom yet, send: "Интересно, что дальше?"
    - Wait for agent response and check for pain summary + Zoom proposal

13. **Phase 9 - Timezone-Aware Scheduling & Email Collection (PASS/FAIL):**
    - Send as prospect: "Ок, давайте созвонимся. Только я сейчас в Варшаве, учтите разницу во времени."
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent acknowledges timezone (Warsaw/UTC+1 vs Bali/UTC+8), mentions Bali working hours context (works 10:00-19:00 Bali time), and asks for email
    - Send as prospect: "bohdan.pytaichuk@gmail.com"
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent shows available times with client timezone display (Warsaw time), presents time RANGES not individual 30-min slots. NO times before 08:00 Warsaw time should appear. NO times after 22:00 Warsaw time should appear. System explains that these are overlap windows between Bali working hours and client's reasonable hours.
    - Send as prospect: "Завтра в 10:00 по моему времени подойдёт"
    - Wait for agent response (60s timeout)
    - PASS criteria: Agent confirms the specific time in client's timezone, does NOT dump all available slots again

14. **Phase 10 - Meeting Booking & Calendar Validation (PASS/FAIL):**
    - Send as prospect: "Да, записывайте!"
    - Wait for agent response (90s timeout)
    - PASS criteria for message: Agent confirms meeting is scheduled, mentions the time, mentions the email, ideally includes Zoom link
    - Validate email was collected: Read `PROSPECTS_FILE` and check that @buddah_lucid now has email field set to `bohdan.pytaichuk@gmail.com`
    - Validate Google Calendar: Use the CalendarConnector to check if a calendar event was created for tomorrow containing "buddah_lucid" or "Buddah" in the summary/description AND has `bohdan.pytaichuk@gmail.com` as an attendee
    - PASS criteria: Email stored in prospect data AND calendar event exists with attendee invite

15. **Collect full conversation history:**
    - Use E2ETelegramPlayer's `get_chat_history("@BetterBohdan", limit=100)` to retrieve the complete conversation
    - Alternatively read Docker logs for the full agent-side view

16. **Cleanup:**
    - Stop Docker containers: `docker compose -f deployment/docker/docker-compose.yml down`
    - Do NOT delete Google Calendar events - preserve them for manual review after the test

## Report

Present results as a structured Rich panel report with the following sections:

**Test Results Summary Table:**
| Phase | Test | Status | Details |
|-------|------|--------|---------|
| 1 | Initial Contact (Snake: Light Entry) | PASS/FAIL | Message received in Xs, easy question Y/N, formal Y/N |
| 2 | Wait Behavior | PASS/FAIL | Silent for Xs (need >=100s), follow-up at Xs (need <=180s) |
| 3 | ROI + Bubble Objection | PASS/FAIL | Factual ROI Y/N, empathy on bubble Y/N, no devaluing Y/N |
| 4 | Multi-Message Burst | PASS/FAIL | Topics addressed: N/3, batched Y/N, coherent Y/N |
| 5 | Media Understanding (Image + Voice) | PASS/FAIL | Photo content Y/N, photo real Y/N, voice content Y/N, voice region ref Y/N, voice natural Y/N |
| 6 | Budget/Need + Catalog Deflection | PASS/FAIL | Catalog deflected Y/N, no early Zoom Y/N, BANT progress Y/N |
| 7 | Authority/Timeline + Leasehold Objection | PASS/FAIL | Leasehold facts Y/N, guarantee handled Y/N, full BANT Y/N |
| 8 | Pain Summary & Zoom Proposal | PASS/FAIL | Pain summary Y/N, Zoom value explained Y/N, specific time Y/N |
| 9 | Timezone & Email | PASS/FAIL | Client timezone Y/N, email collected Y/N, time confirmed Y/N |
| 10 | Calendar & Booking | PASS/FAIL | Meeting confirmed Y/N, calendar event Y/N, attendee invite Y/N |

**Overall Score:** X/10 phases passed

**Methodology Compliance Score:**
- Snake structure followed: Y/N (light entry, reflections, expertise with facts)
- BANT fully gathered before Zoom: Y/N
- Pain summary before Zoom invitation: Y/N
- Objections handled with empathy and facts: Y/N
- Multi-message handling natural: Y/N (batched, addressed multiple topics coherently)
- No anti-patterns detected: Y/N (no "зафиксировала", no early Zoom, no catalog surrender)
- Messages concise (1-3 sentences): Y/N
- Media understanding working: Y/N (photo analyzed by Gemini, voice transcribed, agent uses content in response)

**Full Conversation Log:** Display the complete conversation with timestamps, labeling each message as [AGENT] or [PROSPECT]

**Timing Metrics:**
- Time to initial outreach: Xs
- Wait behavior: silent for Xs, follow-up at Xs
- Average response time: Xs
- Total test duration: Xs

**Google Calendar Event:**
- Event title (summary)
- Scheduled time (in both Bali and client timezone)
- Attendee email confirmed
- Direct link to the event: display the `htmlLink` from the Google Calendar API response
- If event was not created, state "NOT CREATED" and explain why

**Issues Found:** List any failures with specific details about what went wrong and which agent behavior needs improvement

**Recommendations:** Based on failures, suggest concrete improvements to the agent system prompt, scheduling tool, or daemon configuration
